#!/usr/bin/env python3
"""Build a vectorless PageIndex RAG from a folder of Markdown/text files.

Reads every *.md / *.markdown / *.txt in <corpus_dir> (sorted, concatenated), paginates
into fixed line-chunks, derives a hierarchical tree from the Markdown ATX headings
(fenced code blocks are skipped so `# comment` is not mistaken for a heading), attaches a
line-precise extractive summary and 1-based page anchors to each node, and writes:

  <index_dir>/pageindex.json   hierarchical tree (PageIndex schema)
  <index_dir>/pages.jsonl      per-page text store ({"physical_index": N, "text": ...})

Pure stdlib.

    uv run build_pageindex.py <corpus_dir> <index_dir> --name "My knowledge base"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")


def first_line(doc: str | None) -> str:
    for ln in (doc or "").strip().splitlines():
        if ln.strip():
            return ln.strip()
    return ""


def summarize(text: str, max_sents: int = 3, max_chars: int = 600) -> str:
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z(#-])", text)
    picked = []
    for s in sents:
        s = s.strip(" -*#").strip()
        if len(s) >= 40:
            picked.append(s)
        if len(picked) >= max_sents:
            break
    summ = " ".join(picked)
    return summ[:max_chars].rsplit(" ", 1)[0] + " ..." if len(summ) > max_chars else summ


def build(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus_dir")
    ap.add_argument("index_dir")
    ap.add_argument("--name", default=None, help="doc_name for the index")
    ap.add_argument("--lines-per-page", type=int, default=30)
    args = ap.parse_args(argv)

    corpus = Path(args.corpus_dir)
    index_dir = Path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    lpp = args.lines_per_page

    srcs = sorted(p for p in corpus.rglob("*")
                  if p.suffix.lower() in {".md", ".markdown", ".txt"})
    if not srcs:
        print(f"no .md/.txt files in {corpus}", file=sys.stderr)
        return 2

    lines: list[str] = []
    for sp in srcs:
        lines += sp.read_text(encoding="utf-8", errors="replace").splitlines()
        lines.append("")

    page_text = ["\n".join(lines[i:i + lpp]).strip() for i in range(0, len(lines), lpp)]
    N = len(page_text)
    with open(index_dir / "pages.jsonl", "w", encoding="utf-8") as f:
        for i, t in enumerate(page_text):
            f.write(json.dumps({"physical_index": i + 1, "text": t}, ensure_ascii=False) + "\n")

    flat: list[tuple[int, str, int, int]] = []  # (depth, title, start_page, start_line)
    in_fence = False
    for ln_no, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            flat.append((len(m.group(1)) - 1, m.group(2).strip(), ln_no // lpp + 1, ln_no))

    if not flat:  # no headings -> one node over the whole corpus
        flat = [(0, args.name or corpus.name, 1, 0)]

    def end_page_for(idx: int) -> int:
        d, _, p, _ = flat[idx]
        for j in range(idx + 1, len(flat)):
            dj, _, pj, _ = flat[j]
            if dj <= d:
                return max(p, pj - 1)
        return N

    def own_text(idx: int) -> str:
        d, _, _, line0 = flat[idx]
        end_line, child_line = len(lines), None
        for j in range(idx + 1, len(flat)):
            dj, _, _, lj = flat[j]
            if dj <= d:
                end_line = lj
                break
            if dj == d + 1 and child_line is None:
                child_line = lj
        return "\n".join(lines[line0 + 1:(child_line if child_line is not None else end_line)])

    counter = {"n": 0}

    def new_id() -> str:
        counter["n"] += 1
        return f"{counter['n']:04d}"

    def make(idx: int):
        d, title, p, _ = flat[idx]
        node = {"title": title, "node_id": new_id(), "start_index": p,
                "end_index": end_page_for(idx), "summary": summarize(own_text(idx)), "nodes": []}
        j = idx + 1
        while j < len(flat):
            dj = flat[j][0]
            if dj <= d:
                break
            if dj == d + 1:
                child, j = make(j)
                node["nodes"].append(child)
            else:
                j += 1
        if not node["nodes"]:
            del node["nodes"]
        return node, j

    roots, i = [], 0
    while i < len(flat):
        if flat[i][0] == min(d for d, *_ in flat):
            node, i = make(i)
            roots.append(node)
        else:
            i += 1

    def count(ns):
        return sum(1 + count(n.get("nodes", [])) for n in ns)

    doc = {
        "doc_name": args.name or corpus.name,
        "doc_description": f"PageIndex RAG built from {len(srcs)} file(s) in {corpus}.",
        "total_pages": N,
        "sources": [str(s) for s in srcs],
        "structure": roots,
    }
    (index_dir / "pageindex.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False),
                                              encoding="utf-8")
    print(f"sources: {len(srcs)} | pages: {N} ({lpp} lines/pg) | "
          f"top-level: {len(roots)} | nodes: {count(roots)}")
    print(f"wrote {index_dir/'pageindex.json'} and {index_dir/'pages.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
