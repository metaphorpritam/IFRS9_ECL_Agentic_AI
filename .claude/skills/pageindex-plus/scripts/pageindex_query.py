#!/usr/bin/env python3
"""Query a PageIndex RAG built by build_pageindex.py.

Vectorless retrieval: render the tree for an LLM to reason over (tree-search), then pull
the full page text of the chosen nodes as cited context. An offline keyword fallback is
included so the index is usable without an LLM. Pure stdlib.

    uv run pageindex_query.py <index_dir> --search "topic words"
    uv run pageindex_query.py <index_dir> --render

As a library:
    from pageindex_query import load, render_tree_for_llm, get_context, search_tree
    tree, pages = load("<index_dir>")
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def load(index_dir: str):
    """Load (tree, pages) from <index_dir>/pageindex.json + pages.jsonl (UTF-8)."""
    d = Path(index_dir)
    with open(d / "pageindex.json", encoding="utf-8") as f:
        tree = json.load(f)
    pages = {}
    with open(d / "pages.jsonl", encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            pages[o["physical_index"]] = o["text"]
    return tree, pages


def render_tree_for_llm(tree, max_summary: int = 220) -> str:
    """Compact text index (node_id, title, pages, summary) for an LLM to reason over."""
    out = [f"DOCUMENT: {tree['doc_name']}", f"({tree['total_pages']} pages)", ""]

    def rec(nodes, depth=0):
        for n in nodes:
            pad = "  " * depth
            s = (n.get("summary") or "").strip()
            if len(s) > max_summary:
                s = s[:max_summary].rsplit(" ", 1)[0] + "…"
            out.append(f"{pad}- id={n['node_id']} | p{n['start_index']}-{n['end_index']} | {n['title']}")
            if s:
                out.append(f"{pad}    {s}")
            rec(n.get("nodes", []), depth + 1)

    rec(tree["structure"])
    return "\n".join(out)


def _index_nodes(tree):
    idx = {}

    def rec(nodes):
        for n in nodes:
            idx[n["node_id"]] = n
            rec(n.get("nodes", []))

    rec(tree["structure"])
    return idx


def get_context(node_ids, tree, pages, max_chars: int = 12000) -> str:
    """Full page text for the chosen nodes, with page markers — answer context."""
    idx = _index_nodes(tree)
    seen, out, total = set(), [], 0
    for nid in node_ids:
        n = idx.get(nid)
        if not n:
            continue
        out.append(f"\n===== [{n['node_id']}] {n['title']} "
                   f"(pages {n['start_index']}-{n['end_index']}) =====")
        for p in range(n["start_index"], n["end_index"] + 1):
            if p in seen:
                continue
            seen.add(p)
            txt = pages.get(p, "")
            if not txt:
                continue
            out.append(f"\n--- page {p} ---\n{txt}")
            total += len(txt)
            if total > max_chars:
                out.append("\n[context truncated]")
                return "\n".join(out)
    return "\n".join(out)


def search_tree(query: str, tree, top: int = 8):
    """Offline keyword fallback: score nodes by term overlap with title+summary."""
    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    hits = []

    def rec(nodes, path):
        for n in nodes:
            blob = (n["title"] + " " + (n.get("summary") or "")).lower()
            score = sum(blob.count(t) for t in terms) + 3 * sum(n["title"].lower().count(t) for t in terms)
            if score:
                hits.append((score, n["node_id"], n["title"], n["start_index"], n["end_index"],
                             " > ".join(path)))
            rec(n.get("nodes", []), path + [n["title"]])

    rec(tree["structure"], [])
    hits.sort(reverse=True)
    return hits[:top]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Query a PageIndex RAG index directory.")
    ap.add_argument("index_dir", help="folder with pageindex.json + pages.jsonl")
    ap.add_argument("--render", action="store_true", help="dump the LLM tree index")
    ap.add_argument("--search", nargs="+", metavar="WORD", help="offline keyword search")
    args = ap.parse_args()
    tree, pages = load(args.index_dir)
    if args.render:
        print(render_tree_for_llm(tree))
    elif args.search:
        q = " ".join(args.search)
        print(f"Query: {q}\n")
        for score, nid, title, s, e, path in search_tree(q, tree):
            print(f"[{score:>3}] id={nid}  p{s}-{e}  {path} > {title}")
    else:
        ap.print_help()
