# /// script
# requires-python = ">=3.10"
# ///
"""Append a dated entry to the wiki's memory files (UTF-8, consistent format).

Kinds:
    log       memory/log.md        what happened this session / what's next
    decision  memory/decisions.md  a call that future sessions must respect
    question  memory/questions.md  an open unknown to resolve later

Entry format (append-only, newest at the bottom):

    ## 2026-07-04 09:12 UTC — tags: pricing, refactor

    <text>

Usage:
    python wiki_log.py <wiki_dir> log "Compiled discount-rules from src/discount.py; next: tax engine" --tags pricing
    python wiki_log.py <wiki_dir> decision "Round half-up everywhere; banker's rounding rejected (spec §4)."
    python wiki_log.py <wiki_dir> question "Where does FX conversion happen relative to discounts?"
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

FILES = {"log": "log.md", "decision": "decisions.md", "question": "questions.md"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wiki_dir")
    ap.add_argument("kind", choices=sorted(FILES))
    ap.add_argument("text")
    ap.add_argument("--tags", default="", help="comma-separated")
    args = ap.parse_args(argv)

    path = Path(args.wiki_dir) / "memory" / FILES[args.kind]
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tags = ", ".join(t.strip() for t in args.tags.split(",") if t.strip())
    head = f"## {stamp}" + (f" — tags: {tags}" if tags else "")
    entry = f"\n{head}\n\n{args.text.strip()}\n"
    prev = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(prev + entry, encoding="utf-8")
    print(f"appended {args.kind} entry -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
