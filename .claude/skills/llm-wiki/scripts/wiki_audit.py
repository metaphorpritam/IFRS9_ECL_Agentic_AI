# /// script
# requires-python = ">=3.10"
# ///
"""Audit the wiki: is it healthy, current, and complete?

ERRORS (exit 1):
  broken_links        wikilinks / typed links that resolve to no page
  missing_frontmatter page lacks required `title:` or `type:`
  missing_sources     a `sources:`/`code:` path that no longer exists on disk
  stale_pages         a source/code file changed since the manifest was updated

WARNINGS (exit 0, or 1 with --strict):
  unhashed_sources    referenced source never recorded — run --update-manifest
  orphans             pages with no edges at all (index/session excluded)
  uncovered_sources   files under config source_roots no page references
  todos               TODO / FIXME / XXX / ??? markers inside pages
  duplicates          two pages claim the same title/alias key
  unknown_type        `type:` outside the schema's page-type set

`--update-manifest` re-hashes every referenced, existing source into
`.wiki/source_manifest.json` — run it at the END of a compile session to
declare "the wiki reflects the sources as of now". Staleness is then measured
against that declaration. Results also land in `.wiki/audit.json`.

Usage:
    python wiki_audit.py <wiki_dir>                     # audit
    python wiki_audit.py <wiki_dir> --update-manifest   # declare current
    python wiki_audit.py <wiki_dir> --strict            # warnings fail too
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_graph import build_graph, PAGE_TYPES  # noqa: E402

DOC_EXTS = {".md", ".markdown", ".txt", ".pdf", ".pptx", ".xlsx", ".xls",
            ".docx", ".html", ".htm", ".ipynb"}
SKIP_DIRS = {".git", ".wiki", ".venv", "venv", "node_modules", "__pycache__",
             ".idea", ".vscode"}
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX)\b|\?\?\?")


def _hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def norm_source(raw: str, wiki: Path):
    """(canonical_key, resolved_path). Anchor (#...) stripped. Keys are posix
    paths relative to the wiki's parent when possible, so manifests stay
    portable across machines."""
    body = raw.split("#", 1)[0].strip()
    if not body:
        return None, None
    p = Path(body)
    resolved = (p if p.is_absolute() else (wiki / p)).resolve()
    try:
        key = resolved.relative_to(wiki.parent.resolve()).as_posix()
    except ValueError:
        key = resolved.as_posix()
    return key, resolved


def scan_roots(cfg: dict, wiki: Path):
    """All doc/code files under the configured source roots -> {key: path}."""
    found: dict[str, Path] = {}
    for root_s in cfg.get("source_roots", []):
        root = (wiki / root_s).resolve()
        if not root.is_dir():
            print(f"  warn: configured source root missing: {root_s} "
                  f"({root})", file=sys.stderr)
            continue
        globs = list(cfg.get("code_globs", [])) or []
        matched: set[Path] = set()
        for g in globs:
            matched.update(root.glob(g))
        for p in root.rglob("*"):
            if p.suffix.lower() in DOC_EXTS:
                matched.add(p)
        for p in sorted(matched):
            if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
                continue
            try:
                key = p.resolve().relative_to(wiki.parent.resolve()).as_posix()
            except ValueError:
                key = p.resolve().as_posix()
            found[key] = p
    return found


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wiki_dir")
    ap.add_argument("--update-manifest", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)

    wiki = Path(args.wiki_dir).resolve()
    cfg_path = wiki / ".wiki" / "config.json"
    cfg = {}
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    else:
        print(f"  warn: no {cfg_path.name} — coverage check disabled "
              f"(run wiki_init.py)", file=sys.stderr)

    graph = build_graph(wiki)
    for w in graph["warnings"]:
        print(f"  warn: {w}", file=sys.stderr)
    nodes = {n["id"]: n for n in graph["nodes"]}

    # referenced sources across all pages: key -> (resolved, [page ids])
    referenced: dict[str, dict] = {}
    for n in graph["nodes"]:
        for raw in list(n["sources"]) + list(n["code"]):
            key, resolved = norm_source(raw, wiki)
            if key is None:
                continue
            rec = referenced.setdefault(key, {"resolved": resolved, "pages": []})
            rec["pages"].append(n["id"])

    mani_path = wiki / ".wiki" / "source_manifest.json"
    manifest = {"updated": None, "files": {}}
    if mani_path.exists():
        try:
            manifest = json.loads(mani_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  warn: manifest unreadable ({e}) — treating as empty",
                  file=sys.stderr)

    if args.update_manifest:
        files, missing = {}, []
        for key, rec in sorted(referenced.items()):
            if rec["resolved"] and rec["resolved"].exists():
                files[key] = _hash(rec["resolved"])
            else:
                missing.append(key)
        manifest = {"updated": datetime.now(timezone.utc)
                    .isoformat(timespec="seconds"), "files": files}
        mani_path.parent.mkdir(parents=True, exist_ok=True)
        mani_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        print(f"manifest: hashed {len(files)} referenced source(s) -> {mani_path}")
        for k in missing:
            print(f"  NOT hashed (missing on disk): {k}", file=sys.stderr)

    errors: dict[str, list] = {k: [] for k in
                               ("broken_links", "missing_frontmatter",
                                "missing_sources", "stale_pages")}
    warns: dict[str, list] = {k: [] for k in
                              ("unhashed_sources", "orphans",
                               "uncovered_sources", "todos", "duplicates",
                               "unknown_type", "index_gaps")}

    for u in graph["unresolved"]:
        errors["broken_links"].append(
            f"{nodes[u['src']]['path']}:{u['line']} —{u['type']}→ "
            f"'{u['target_text']}'")
    for n in graph["nodes"]:
        if not n["title"] or not n["type"]:
            errors["missing_frontmatter"].append(
                f"{n['path']}: missing " +
                ("title" if not n["title"] else "type"))
        elif n["type"] not in PAGE_TYPES:
            warns["unknown_type"].append(f"{n['path']}: type '{n['type']}'")
        if (n["in_degree"] + n["out_degree"] == 0
                and n["id"] != "index" and n["type"] != "session"):
            warns["orphans"].append(f"{n['path']} ({n['title']})")
        try:
            body = (wiki / n["path"]).read_text(encoding="utf-8")
            for ln, line in enumerate(body.split("\n"), 1):
                if TODO_RE.search(line):
                    warns["todos"].append(
                        f"{n['path']}:{ln}: {line.strip()[:70]}")
        except Exception as e:
            print(f"  warn: {n['path']} unreadable in TODO scan — {e}",
                  file=sys.stderr)

    for key, rec in sorted(referenced.items()):
        pages = ",".join(sorted(set(rec["pages"])))
        if rec["resolved"] is None or not rec["resolved"].exists():
            errors["missing_sources"].append(f"{key}  (referenced by {pages})")
            continue
        old = manifest.get("files", {}).get(key)
        if old is None:
            warns["unhashed_sources"].append(f"{key}  (referenced by {pages})")
        elif _hash(rec["resolved"]) != old:
            errors["stale_pages"].append(
                f"{key} changed since manifest — re-compile page(s): {pages}")

    # index.md must catalog every page (link + one-line summary) — that is
    # how query-time navigation works without RAG. Flag pages it never links.
    if "index" in nodes:
        linked = {e["dst"] for e in graph["edges"] if e["src"] == "index"}
        for n in graph["nodes"]:
            if n["id"] != "index" and n["id"] not in linked:
                warns["index_gaps"].append(
                    f"{n['path']} ({n['title']}) — add a [[link]] + one-line "
                    f"summary to index.md")

    for d in graph["duplicates"]:
        warns["duplicates"].append(
            f"'{d['key']}' ({d['kind']}) claimed by: {', '.join(d['ids'])}")

    if cfg.get("source_roots"):
        scanned = scan_roots(cfg, wiki)
        unc = sorted(set(scanned) - set(referenced))
        for k in unc[:20]:
            warns["uncovered_sources"].append(k)
        if len(unc) > 20:
            warns["uncovered_sources"].append(f"... +{len(unc) - 20} more")

    n_err = sum(len(v) for v in errors.values())
    n_warn = sum(len(v) for v in warns.values())
    report = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "errors": errors, "warnings": warns,
              "counts": {"errors": n_err, "warnings": n_warn,
                         "pages": graph["pages"], "edges": len(graph["edges"])}}
    out = wiki / ".wiki" / "audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                   encoding="utf-8")

    print(f"\naudit: {graph['pages']} pages, {len(graph['edges'])} edges — "
          f"{n_err} error(s), {n_warn} warning(s) -> {out}")
    for group, title in ((errors, "ERROR"), (warns, "warn")):
        for name, items in group.items():
            if not items:
                continue
            print(f"  {title} {name} ({len(items)}):")
            for it in items:
                print(f"    - {it}")
    if n_err == 0 and n_warn == 0:
        print("  clean.")
    return 1 if (n_err or (args.strict and n_warn)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
