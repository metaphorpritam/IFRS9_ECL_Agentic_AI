# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
apply_toc.py — idempotent patcher that wires notes/assets/js/toc.js into
every notes page (the 13 chapters under notes/chapters/ + notes/index.html).

Inserts exactly one line,

    <script src="<relative-path-to-toc.js>" defer></script>

immediately before </body> in each target file, using a path normalized
relative to that file's own directory (chapters/*.html -> "../assets/js/toc.js",
index.html -> "assets/js/toc.js"). Running twice is a no-op: a file already
carrying a <script src="...toc.js"...> tag (any attribute order/spacing) is
left untouched and reported as "skipped".

This patcher never touches chapter content — it only inserts the one script
line before the closing </body> tag. See notes/plan/conventions.md for the
wider notes conventions this campaign follows.

Usage:
    cd /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI
    uv run --no-sync notes/assets/apply_toc.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

TOC_JS_RE = re.compile(r'<script\b[^>]*\bsrc\s*=\s*"[^"]*toc\.js"[^>]*>', re.IGNORECASE)
BODY_CLOSE_RE = re.compile(r'</body\s*>', re.IGNORECASE)


def target_files(notes_dir: Path) -> list[Path]:
    chapters = sorted((notes_dir / "chapters").glob("ch*.html"))
    index = notes_dir / "index.html"
    files = list(chapters)
    if index.is_file():
        files.append(index)
    return files


def relative_toc_src(html_path: Path, toc_js_path: Path) -> str:
    rel = os.path.relpath(toc_js_path, start=html_path.parent)
    return rel.replace(os.sep, "/")


def apply_to_file(html_path: Path, toc_js_path: Path) -> str:
    """Returns 'applied' or 'skipped'."""
    text = html_path.read_text(encoding="utf-8")

    if TOC_JS_RE.search(text):
        return "skipped"

    src = relative_toc_src(html_path, toc_js_path)
    script_line = f'<script src="{src}" defer></script>\n'

    matches = list(BODY_CLOSE_RE.finditer(text))
    if not matches:
        raise ValueError(f"{html_path}: no </body> tag found")
    last = matches[-1]
    new_text = text[: last.start()] + script_line + text[last.start():]
    html_path.write_text(new_text, encoding="utf-8")
    return "applied"


def main(argv: list[str]) -> int:
    notes_dir = Path(__file__).resolve().parent.parent  # notes/assets/.. = notes/
    toc_js_path = notes_dir / "assets" / "js" / "toc.js"
    if not toc_js_path.is_file():
        print(f"ERROR: {toc_js_path} not found", file=sys.stderr)
        return 2

    files = target_files(notes_dir)
    if not files:
        print("ERROR: no target files found", file=sys.stderr)
        return 2

    applied = 0
    skipped = 0
    for f in files:
        status = apply_to_file(f, toc_js_path)
        print(f"[{status:7s}] {f.relative_to(notes_dir.parent)}")
        if status == "applied":
            applied += 1
        else:
            skipped += 1

    print()
    print(f"RESULT: {applied} applied, {skipped} skipped, {len(files)} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
