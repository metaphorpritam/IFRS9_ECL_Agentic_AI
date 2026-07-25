# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
apply_math_overflow_fix.py — idempotent patcher that contains wide MathJax
equations (display AND inline) inside their own horizontal scrollbar, so
the PAGE never scrolls horizontally on narrow viewports.

ROOT CAUSE (reproduced in real Chromium/Playwright before this fix):
MathJax's SVG output renders each display equation as

    <mjx-container class="MathJax" jax="SVG" display="true"><svg ...></svg></mjx-container>

with `display: block` but NO width cap and NO overflow containment in the
project's CSS. The inner <svg> has an explicit pixel width sized to the
equation's natural typeset width (e.g. ch12's longest equation renders at
1049px). When that width exceeds the content column (e.g. 672px at an
800px viewport), the <mjx-container> — and with it, <body> and the whole
page — overflows horizontally and the PAGE gains a horizontal scrollbar.
Measured before this fix: ch12 at 800px viewport had a 315px page-level
overflow (document.documentElement.scrollWidth - clientWidth); ch01/ch03/
ch06 also overflowed at 800px by smaller amounts. This is pre-existing and
independent of the TOC sidebar (notes/assets/js/toc.js).

A second, independent overflow source was found by the same real-browser
sweep: a handful of long INLINE equations (`$...$`, e.g. a chained
implication in ch03 s3.x) render wide enough (848px at an 800px viewport)
to overflow on their own — `mjx-container[jax="SVG"]` without the
`display="true"` attribute computes to plain CSS `display: inline` (set by
MathJax's own injected stylesheet, so the formula flows inside the
paragraph's text), and `overflow`/`max-width` have no effect on a
non-replaced inline box per the CSS spec, so an inline formula wider than
the line simply pushes the page wider with no way to contain it while it
stays `display: inline`. Fix: promote just the outsized-risk inline
containers to `display: inline-block` (still flows inline with the
surrounding text — inline SVG is already an atomic, non-breaking unit on
the line either way) so `max-width`/`overflow-x` take effect exactly as
they do for the display (block) case.

FIX: give every MathJax SVG container (`mjx-container[jax="SVG"]`, inline
or display) `overflow-x: auto` and `max-width: 100%` of its containing
block; the non-display ones additionally get `display: inline-block` so
that constraint actually takes effect (see above). A box with
overflow:auto does not grow to fit an oversized child — it keeps its own
(container-constrained) width and the overflowing content becomes
internally scrollable instead of pushing the page wider. This is the same
containment pattern already used for wide tables (`.table-wrap
{ overflow-x: auto; }` in every chapter's shared <style>). No equation
content is touched — this is CSS only.

Inserts exactly one block,

    <style id="math-overflow-fix">
    mjx-container[jax="SVG"] { ... }
    </style>

immediately before </head> in each target file (the 13 chapters under
notes/chapters/ + notes/index.html — 14 files total). Idempotent AND
update-safe: re-running always syncs the block's content — a file whose
existing `id="math-overflow-fix"` block already matches the current
STYLE_BLOCK is left untouched and reported "unchanged"; one whose block
has drifted (e.g. an older version of this script's CSS) has just that
block replaced in place and is reported "updated"; a file with no marker
yet gets the block inserted and is reported "applied". This patcher never
touches chapter content or equations — only ever that one <style> block,
the same pattern apply_toc.py uses for its one <script> line before
</body>.

Usage:
    cd /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI
    uv run --no-sync notes/assets/apply_math_overflow_fix.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BLOCK_RE = re.compile(
    r'<style\b[^>]*\bid\s*=\s*"math-overflow-fix"[^>]*>.*?</style>\s*',
    re.IGNORECASE | re.DOTALL,
)
HEAD_CLOSE_RE = re.compile(r'</head\s*>', re.IGNORECASE)

STYLE_BLOCK = """<style id="math-overflow-fix">
  /* Math-equation overflow containment (apply_math_overflow_fix.py): MathJax
     SVG output has no built-in width cap, so a wide equation — display
     ($$...$$) OR inline ($...$) — can overflow the content column and force
     the whole PAGE to scroll horizontally at narrow viewports. Give every
     equation its own horizontal scrollbar instead — same containment
     pattern as .table-wrap. Equation content/markup is never touched by
     this rule.
     Inline containers (no [display="true"]) are additionally promoted to
     inline-block: MathJax's own CSS renders them as plain `display:inline`
     so they flow with the surrounding text, but `overflow`/`max-width` do
     not apply to non-replaced inline boxes, so an oversized inline formula
     would otherwise have no way to be contained. inline-block still flows
     inline with the text (the SVG was already a single non-breaking unit
     on the line either way) while letting the containment rules take
     effect. */
  mjx-container[jax="SVG"] {
    max-width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
  }
  mjx-container[jax="SVG"]:not([display="true"]) {
    display: inline-block;
    vertical-align: middle;
  }
  mjx-container[jax="SVG"][display="true"] {
    display: block;
  }
</style>
"""


def target_files(notes_dir: Path) -> list[Path]:
    chapters = sorted((notes_dir / "chapters").glob("ch*.html"))
    files = list(chapters)
    for extra in (notes_dir / "index.html", notes_dir / "cv_dossier.html"):
        if extra.is_file():
            files.append(extra)
    return files


def apply_to_file(html_path: Path) -> str:
    """Returns 'applied', 'updated', or 'unchanged'."""
    text = html_path.read_text(encoding="utf-8")

    existing = BLOCK_RE.search(text)
    if existing:
        if existing.group(0).strip() == STYLE_BLOCK.strip():
            return "unchanged"
        new_text = text[: existing.start()] + STYLE_BLOCK + text[existing.end():]
        html_path.write_text(new_text, encoding="utf-8")
        return "updated"

    matches = list(HEAD_CLOSE_RE.finditer(text))
    if not matches:
        raise ValueError(f"{html_path}: no </head> tag found")
    last = matches[-1]
    new_text = text[: last.start()] + STYLE_BLOCK + text[last.start():]
    html_path.write_text(new_text, encoding="utf-8")
    return "applied"


def main(argv: list[str]) -> int:
    notes_dir = Path(__file__).resolve().parent.parent  # notes/assets/.. = notes/

    files = target_files(notes_dir)
    if not files:
        print("ERROR: no target files found", file=sys.stderr)
        return 2

    counts = {"applied": 0, "updated": 0, "unchanged": 0}
    for f in files:
        status = apply_to_file(f)
        print(f"[{status:9s}] {f.relative_to(notes_dir.parent)}")
        counts[status] += 1

    print()
    print(
        f"RESULT: {counts['applied']} applied, {counts['updated']} updated, "
        f"{counts['unchanged']} unchanged, {len(files)} total"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
