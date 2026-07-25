# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
apply_mobile_overflow_fix.py — idempotent patcher that contains wide TABLES
and long CODE runs at phone widths, so the PAGE never scrolls horizontally
on narrow viewports.

ROOT CAUSE (reproduced in real Chromium/Playwright at a 390px viewport,
2026-07-25 adversarial UI review): the notes stylesheets set no horizontal
containment on <table> or on long unbreakable inline <code> spans. A wide
table (worst case: cv_dossier.html's CV card table, natural width 566px)
or a long path/command in <code> (e.g. the six-part pytest --ignore
command) simply pushes <body> wider than the viewport: measured page-level
overflow (documentElement.scrollWidth - clientWidth) before this fix was
232px on cv_dossier.html, 131px on index.html, 186px on ch03 (code spans;
its equations were already contained by apply_math_overflow_fix.py). The
content is CLIPPED for phone readers with no way to reach it.

FIX (all scoped to a max-width:700px media query, so desktop rendering —
which was Playwright-verified panel by panel — is untouched):
  * table          -> display:block + overflow-x:auto: a too-wide table
                      scrolls inside its own box instead of widening the
                      page (rows/cells keep table layout inside).
  * pre            -> overflow-x:auto: command blocks scroll, preserving
                      their formatting rather than wrapping mid-flag.
  * :not(pre)>code -> overflow-wrap:anywhere: a long inline path breaks
                      across lines instead of overflowing.

Same contract as apply_math_overflow_fix.py: inserts one marker <style>
block immediately before </head> in each target (13 chapters + index.html
+ cv_dossier.html). Unchanged block -> "unchanged"; drifted block ->
replaced, "updated"; missing -> inserted, "applied". Never touches content.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

STYLE_ID = "mobile-overflow-fix"

STYLE_BLOCK = """<style id="mobile-overflow-fix">
  /* Phone-width containment (apply_mobile_overflow_fix.py): wide tables and
     long code runs must scroll or wrap INSIDE their own box — the page
     itself never scrolls horizontally. Scoped to narrow viewports only. */
  @media (max-width: 700px) {
    table { display: block; overflow-x: auto; max-width: 100%; }
    pre { overflow-x: auto; max-width: 100%; }
    :not(pre) > code { overflow-wrap: anywhere; }
    /* long unbreakable tokens in prose boxes / definition lists / summaries
       wrap instead of forcing a page pan (ch08 router-tree, ch09 pdoc,
       ch10 gotcha — 390px-viewport bisection, 2026-07-25) */
    summary, dt, dd, .gotcha, .note, .warn, .defn, .thm, .ex,
    .interpretation { overflow-wrap: anywhere; }
    /* interactive tree/diagram widgets keep their layout and scroll as a
       unit rather than wrapping mid-node */
    .widget { overflow-x: auto; max-width: 100%; }
  }
</style>
"""

BLOCK_RE = re.compile(
    r"""<style\s+id=["']""" + STYLE_ID + r"""["']>.*?</style>\n?""",
    re.DOTALL,
)


def patch_file(html_path: Path) -> str:
    text = html_path.read_text(encoding="utf-8")
    existing = BLOCK_RE.search(text)
    if existing:
        if existing.group(0) == STYLE_BLOCK:
            return "unchanged"
        text = BLOCK_RE.sub(lambda _m: STYLE_BLOCK, text, count=1)
        html_path.write_text(text, encoding="utf-8")
        return "updated"
    idx = text.find("</head>")
    if idx == -1:
        raise ValueError(f"{html_path}: no </head> tag found")
    text = text[:idx] + STYLE_BLOCK + text[idx:]
    html_path.write_text(text, encoding="utf-8")
    return "applied"


def main(argv: list[str]) -> int:
    notes_dir = Path(__file__).resolve().parent.parent
    targets = sorted((notes_dir / "chapters").glob("ch*.html"))
    targets += [notes_dir / "index.html", notes_dir / "cv_dossier.html"]
    if argv:
        targets = [Path(a) for a in argv]
    for t in targets:
        print(f"{patch_file(t):>9}  {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
