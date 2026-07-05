# /// script
# requires-python = ">=3.9"
# ///
"""Escape currency dollars for MathJax: `$50` -> `\\$50` (learnings §2).

Why: with `inlineMath: [['$','$']]` a bare `$50` in prose pairs with the NEXT `$`
on the page and MathJax renders the text between them as math -> `Math input error`.
`processEscapes: true` (now set in template.html) makes `\\$` render as a literal
dollar — this script inserts those escapes mechanically so it never depends on
hand-editing.

Rules (deliberately conservative):
  * Only `$` immediately followed by a digit is a candidate (currency form).
  * SKIP if the character AFTER the number is a math-continuation char
    ( \\ ^ _ { = + ( $ ) — that `$` is genuinely opening math like `$50^2$`.
  * SKIP inside <script>/<style> blocks (masked before matching).
  * Idempotent: `\\$50` is never double-escaped.

Usage:
    python escape_currency.py notes_template.html            # rewrite in place
    python escape_currency.py notes_template.html --check    # report, exit 1 if changes needed
    python escape_currency.py notes_template.html --list     # triage every $<digit> occurrence
"""
import re
import sys
from pathlib import Path

MATH_CONT = set("\\^_{=+($")
CANDIDATE = re.compile(r"(?<!\\)\$(?=\d)")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
MASK = re.compile(r"(<script\b.*?</script>|<style\b.*?</style>)", re.S | re.I)


def _mask(html: str):
    """Replace script/style blocks with same-length placeholders so offsets hold."""
    saved = []

    def repl(m):
        saved.append(m.group(0))
        return "\x00" * len(m.group(0))

    return MASK.sub(repl, html), saved


def find_escapes(html: str):
    """Return sorted offsets of `$` chars that should become `\\$`."""
    masked, _ = _mask(html)
    offs = []
    for m in CANDIDATE.finditer(masked):
        num = NUMBER.match(masked, m.end())
        end = num.end() if num else m.end()
        nxt = masked[end] if end < len(masked) else ""
        if nxt in MATH_CONT:
            continue  # real math continues — leave the delimiter alone
        offs.append(m.start())
    return offs


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    path = Path(argv[0])
    mode = argv[1] if len(argv) > 1 else "--fix"
    html = path.read_text(encoding="utf-8")

    if mode == "--list":
        masked, _ = _mask(html)
        for m in re.finditer(r"(\\?)\$(\d[\d,]*(?:\.\d+)?)", masked):
            tag = "escaped" if m.group(1) else "RAW"
            line = masked.count("\n", 0, m.start()) + 1
            ctx = html[max(0, m.start() - 30):m.end() + 20].replace("\n", " ")
            print(f"  L{line:>5} [{tag:7}] …{ctx}…")
        return 0

    offs = find_escapes(html)
    if mode == "--check":
        for o in offs:
            line = html.count("\n", 0, o) + 1
            print(f"  L{line}: unescaped currency: …{html[max(0, o-25):o+15]!r}…")
        print(f"{len(offs)} unescaped currency dollar(s)"
              + ("" if offs else " — clean"))
        return 1 if offs else 0

    for o in reversed(offs):  # right-to-left so offsets stay valid
        html = html[:o] + "\\" + html[o:]
    path.write_text(html, encoding="utf-8")
    print(f"OK escaped {len(offs)} currency dollar(s) in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
