# /// script
# requires-python = ">=3.10"
# ///
"""Build `.wiki/graph.json` from the wiki's Markdown pages.

The graph is the machine-readable spine of the wiki: nodes are pages
(`index.md` + `pages/**/*.md`), edges come from two places —

  1. typed links in frontmatter:      links: { uses: [Pricing Engine], ... }
  2. body wikilinks:                  [[Pricing Engine]] / [[Target#H|label]]
     (recorded with edge type "mentions"; fenced ``` code blocks are masked)

Link targets are resolved case-insensitively against every page's title,
aliases, and filename slug. Anything that doesn't resolve is recorded under
`unresolved` (never dropped) — the audit turns those into errors.

Frontmatter is a deliberately small YAML subset parsed with regexes (no
dependency): scalars, inline `[a, b]` lists, `- item` dash lists, and one
nested level under `links:`. The exact grammar is in references/schema.md;
any line the parser cannot understand is REPORTED, not skipped silently.

Usage:
    python wiki_graph.py <wiki_dir>            # writes <wiki_dir>/.wiki/graph.json
    python wiki_graph.py <wiki_dir> --print    # also pretty-print a summary
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PAGE_TYPES = {"concept", "module", "entity", "decision", "question",
              "source", "session"}
LIST_KEYS = {"aliases", "tags", "sources", "code"}   # always coerced to lists

# [[Target]]  [[Target#Heading]]  [[Target|label]]  [[Target#H|label]]
WIKILINK = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")
FENCE = re.compile(r"```.*?```", re.S)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "page"


def _scalar(v: str):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return ([x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
                if inner else [])
    return v.strip("\"'")


def parse_frontmatter(text: str, where: str = "?"):
    """Parse the schema.md YAML subset.

    Returns (meta, body, body_line_offset, fm_edges, warnings) where fm_edges
    is [(edge_type, target, file_line)] collected from the `links:` block.
    """
    warns: list[str] = []
    if not text.startswith("---"):
        return {}, text, 0, [], warns
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?", text, re.S)
    if not m:
        warns.append(f"{where}: frontmatter opened with --- but never closed")
        return {}, text, 0, [], warns
    raw, body = m.group(1), text[m.end():]
    offset = m.group(0).count("\n")          # body line L -> file line offset+L
    lines = raw.split("\n")
    meta: dict = {}
    fm_edges: list[tuple[str, str, int]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        file_line = i + 2                     # line 1 of the file is `---`
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        mm = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not mm:
            warns.append(f"{where}:{file_line}: frontmatter line ignored "
                         f"(unparseable): {line.strip()!r}")
            i += 1
            continue
        key, val = mm.group(1), mm.group(2)
        if val.strip():                       # scalar / inline list on one line
            parsed = _scalar(val)
            if key in LIST_KEYS and not isinstance(parsed, list):
                parsed = [parsed]
            meta[key] = parsed
            i += 1
            continue
        # block value: dash list, or nested edge-types under `links:`
        items: list[str] = []
        nested: dict[str, list[str]] = {}
        j = i + 1
        while j < len(lines) and (lines[j].startswith(" ") or not lines[j].strip()):
            sub = lines[j]
            sub_line = j + 2
            if not sub.strip():
                j += 1
                continue
            dm = re.match(r"^\s+-\s+(.*)$", sub)
            nm = re.match(r"^\s+([A-Za-z_][\w-]*):\s*(.*)$", sub)
            if dm and key != "links":
                items.append(dm.group(1).strip().strip("\"'"))
            elif nm and key == "links":
                etype, eval_ = nm.group(1), nm.group(2)
                if eval_.strip():
                    tv = _scalar(eval_)
                    targets = tv if isinstance(tv, list) else [tv]
                    nested[etype] = targets
                    for t in targets:
                        fm_edges.append((etype, t, sub_line))
                else:                          # dash list under the edge type
                    k = j + 1
                    targets = []
                    while k < len(lines) and re.match(r"^\s+-\s+", lines[k]) \
                            and (len(lines[k]) - len(lines[k].lstrip())
                                 > len(sub) - len(sub.lstrip())):
                        t = re.sub(r"^\s+-\s+", "", lines[k]).strip().strip("\"'")
                        targets.append(t)
                        fm_edges.append((etype, t, k + 2))
                        k += 1
                    nested[etype] = targets
                    j = k - 1
            else:
                warns.append(f"{where}:{sub_line}: frontmatter sub-line ignored: "
                             f"{sub.strip()!r}")
            j += 1
        meta[key] = nested if key == "links" else items
        i = j
    return meta, body, offset, fm_edges, warns


def _mask_fences(body: str) -> str:
    """Blank out fenced code (keep newlines) so [[..]] in code isn't a link."""
    return FENCE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), body)


def collect_pages(wiki_dir: Path):
    files = []
    idx = wiki_dir / "index.md"
    if idx.exists():
        files.append(idx)
    pages_dir = wiki_dir / "pages"
    if pages_dir.is_dir():
        files.extend(sorted(pages_dir.rglob("*.md")))
    return files


def build_graph(wiki_dir: Path) -> dict:
    wiki_dir = Path(wiki_dir)
    warnings: list[str] = []
    nodes: dict[str, dict] = {}
    raw_links: list[tuple[str, str, str, int]] = []   # (src, type, target, line)

    files = collect_pages(wiki_dir)
    if not files:
        warnings.append(f"no pages found under {wiki_dir} "
                        f"(expected index.md and/or pages/*.md)")

    for f in files:
        rel = f.relative_to(wiki_dir).as_posix()
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as e:                          # never a silent skip
            warnings.append(f"{rel}: unreadable — {type(e).__name__}: {e}")
            continue
        meta, body, offset, fm_edges, w = parse_frontmatter(text, rel)
        warnings.extend(w)
        nid = slugify(f.stem)
        if nid in nodes:
            warnings.append(f"{rel}: id collision with {nodes[nid]['path']} "
                            f"(both slugify to '{nid}') — second file ignored")
            continue
        headings = []
        masked = _mask_fences(body)
        for ln, line in enumerate(masked.split("\n"), 1):
            hm = HEADING.match(line)
            if hm:
                headings.append({"line": offset + ln, "text": hm.group(2).strip()})
        nodes[nid] = {
            "id": nid,
            "path": rel,
            "title": meta.get("title") or f.stem,
            "type": meta.get("type", ""),
            "tags": meta.get("tags", []) or [],
            "aliases": meta.get("aliases", []) or [],
            "status": meta.get("status", ""),
            "sources": meta.get("sources", []) or [],
            "code": meta.get("code", []) or [],
            "headings": headings,
            "in_degree": 0,
            "out_degree": 0,
        }
        for etype, target, line in fm_edges:
            raw_links.append((nid, etype, target, line))
        for ln, line in enumerate(masked.split("\n"), 1):
            for wm in WIKILINK.finditer(line):
                raw_links.append((nid, "mentions", wm.group(1).strip(),
                                  offset + ln))

    # ---- title/alias/slug index (case-insensitive) --------------------------
    title_index: dict[str, str] = {}
    duplicates: list[dict] = []

    def claim(key: str, nid: str, kind: str):
        k = key.lower().strip()
        if not k:
            return
        if k in title_index and title_index[k] != nid:
            duplicates.append({"key": key, "ids": sorted({title_index[k], nid}),
                               "kind": kind})
            return
        title_index[k] = nid

    for nid, n in nodes.items():
        claim(n["title"], nid, "title")
        claim(nid, nid, "slug")
        for a in n["aliases"]:
            claim(a, nid, "alias")

    # ---- resolve edges -------------------------------------------------------
    edges, unresolved, seen = [], [], set()
    for src, etype, target, line in raw_links:
        dst = title_index.get(target.lower().strip()) \
            or title_index.get(slugify(target))
        if dst is None:
            unresolved.append({"src": src, "target_text": target,
                               "type": etype, "line": line})
            continue
        if dst == src:
            continue                                   # self-links carry nothing
        key = (src, dst, etype)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"src": src, "dst": dst, "type": etype, "line": line})
        nodes[src]["out_degree"] += 1
        nodes[dst]["in_degree"] += 1

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wiki_dir": str(wiki_dir),
        "pages": len(nodes),
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": sorted(edges, key=lambda e: (e["src"], e["dst"], e["type"])),
        "unresolved": unresolved,
        "duplicates": duplicates,
        "title_index": title_index,
        "warnings": warnings,
    }


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wiki_dir")
    ap.add_argument("--print", action="store_true", dest="pretty",
                    help="print node/edge summary after writing")
    args = ap.parse_args(argv)

    wiki = Path(args.wiki_dir)
    g = build_graph(wiki)
    out = wiki / ".wiki" / "graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")

    for w in g["warnings"]:
        print(f"  warn: {w}", file=sys.stderr)
    print(f"graph: {g['pages']} pages, {len(g['edges'])} edges, "
          f"{len(g['unresolved'])} unresolved link(s), "
          f"{len(g['duplicates'])} duplicate title/alias key(s) -> {out}")
    if g["unresolved"]:
        for u in g["unresolved"]:
            print(f"  unresolved: {u['src']} —{u['type']}→ "
                  f"'{u['target_text']}' (line {u['line']})", file=sys.stderr)
    if args.pretty:
        for n in g["nodes"]:
            print(f"  {n['id']:<28} {n['type'] or '?':<9} "
                  f"in:{n['in_degree']} out:{n['out_degree']}  {n['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
