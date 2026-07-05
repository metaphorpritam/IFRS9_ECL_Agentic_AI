# /// script
# requires-python = ">=3.10"
# ///
"""Scaffold a new LLM wiki.

Creates:
    <wiki_dir>/index.md                the LLM-maintained map of content
    <wiki_dir>/pages/                  one .md per concept/module/entity/...
    <wiki_dir>/memory/log.md           append-only session journal
    <wiki_dir>/memory/decisions.md     decision records
    <wiki_dir>/memory/questions.md     open questions
    <wiki_dir>/.wiki/config.json       source roots + code globs (audit scope)

Source roots are stored relative to the wiki directory (e.g. `../src`), so a
wiki that lives inside the project stays portable across machines.

Usage:
    python wiki_init.py <wiki_dir> --name "Pricing Service" \
        --source-root ../src --source-root ../docs --code-glob "**/*.py"

Idempotent: refuses to overwrite an existing config and says so.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

INDEX_TMPL = """---
title: {name} Index
type: concept
status: active
tags: [index]
---

# {name} — wiki index

The catalog of the wiki, and the FIRST thing read both by a fresh session and
at query time. Convention (from Karpathy's llm-wiki pattern): **every page
gets one line here** — a `[[wikilink]]` plus a one-line summary — grouped
under a category heading. Update it on every ingest; the audit flags pages
missing from this file.

## Modules

<!-- - [[Page Title]] — one-line summary -->
(none yet)

## Concepts

<!-- - [[Page Title]] — one-line summary -->
(none yet)

## Decisions & open questions

Tracked in `memory/decisions.md` and `memory/questions.md` (append via
`wiki_log.py`; memory files sit outside the graph by design).
"""

MEMORY_HEADERS = {
    "log.md": "# Session log\n\nAppend-only. One entry per working session — "
              "what was read, what changed, what's next. Newest at the bottom.\n",
    "decisions.md": "# Decision records\n\nAppend-only. One entry per decision: "
                    "context, options, the call, and why.\n",
    "questions.md": "# Open questions\n\nAppend-only additions; strike through "
                    "(~~like this~~) with a pointer to the answer's page when "
                    "resolved.\n",
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wiki_dir")
    ap.add_argument("--name", default="Project")
    ap.add_argument("--source-root", action="append", default=[],
                    help="repeatable; path relative to the wiki dir (e.g. ../src)")
    ap.add_argument("--code-glob", action="append", default=[],
                    help="repeatable; default **/*.py")
    args = ap.parse_args(argv)

    wiki = Path(args.wiki_dir)
    cfg_path = wiki / ".wiki" / "config.json"
    if cfg_path.exists():
        print(f"refuse: {cfg_path} already exists — this wiki is initialised. "
              f"Edit the config directly to change roots/globs.", file=sys.stderr)
        return 1

    for d in (wiki / "pages", wiki / "memory", wiki / ".wiki"):
        d.mkdir(parents=True, exist_ok=True)

    cfg = {
        "name": args.name,
        "source_roots": args.source_root,          # relative to wiki_dir
        "code_globs": args.code_glob or ["**/*.py"],
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    idx = wiki / "index.md"
    if not idx.exists():
        idx.write_text(INDEX_TMPL.format(name=args.name), encoding="utf-8")
    for fn, hdr in MEMORY_HEADERS.items():
        p = wiki / "memory" / fn
        if not p.exists():
            p.write_text(hdr, encoding="utf-8")

    print(f"initialised wiki at {wiki}")
    roots = cfg["source_roots"] or "(none — set some so the audit can check coverage)"
    print(f"  source_roots: {roots}")
    print(f"  code_globs:   {cfg['code_globs']}")
    print("next: compile pages (see references/playbook.md), then run "
          "wiki_graph.py and wiki_audit.py --update-manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
