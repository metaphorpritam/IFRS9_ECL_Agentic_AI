# /// script
# requires-python = ">=3.9"
# ///
"""Lint: flag non-ASCII characters INSIDE $...$ / $$...$$ math spans (learnings §2).

Why: MathJax's SVG renderer has no glyphs for `₹ £ ฿ – ✓ …` — a currency symbol
inside math yields `Math input error`. The fix is to keep the symbol in HTML and
close the math first:   write  `=$ <b>₹150</b>`   not   `$=₹150$`.

Usage:
    python find_nonascii_math.py notes_template.html    # exit 1 if any found
"""
import re
import sys
from pathlib import Path

# display math first so $$ spans aren't parsed as two inline delimiters
SPAN = re.compile(r"\$\$(.+?)\$\$|(?<!\\)\$(.+?)(?<!\\)\$", re.S)
MASK = re.compile(r"(<script\b.*?</script>|<style\b.*?</style>)", re.S | re.I)


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    path = Path(argv[0])
    html = MASK.sub(lambda m: "\x00" * len(m.group(0)),
                    path.read_text(encoding="utf-8"))
    bad = 0
    for m in SPAN.finditer(html):
        body = m.group(1) or m.group(2) or ""
        chars = sorted({c for c in body if ord(c) > 127})
        if not chars:
            continue
        bad += 1
        line = html.count("\n", 0, m.start()) + 1
        snippet = body.strip().replace("\n", " ")[:60]
        names = " ".join(f"{c!r}(U+{ord(c):04X})" for c in chars)
        print(f"  L{line}: non-ASCII in math: {names}  in  ${snippet}$")
    if bad:
        print(f"{bad} math span(s) contain non-ASCII — move the symbol OUT of the "
              f"$...$ (e.g. `=$ <b>₹150</b>`), it will not render inside math.")
        return 1
    print("clean — no non-ASCII characters inside math spans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
