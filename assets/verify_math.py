# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
r"""
verify_math.py — deep MathJax render-correctness gate for IFRS9 study-notes
chapters. Complements check_notes.py's cheap delimiter-parity check (#3)
with an actual render pass through MathJax, so it catches defect classes
that are invisible to character counting — most importantly the
"visible-backslash" bug documented below.

ROOT CAUSE (verified by rendering through this exact harness — see
notes/assets/.mathjax_env/render_cli.js and the probes that derived it):

    The chapters load MathJax's plain `tex-svg.js` CDN bundle with no
    `packages:` override in `window.MathJax.tex`. That bundle does NOT
    include the `textmacros` extension package. Without it, MathJax's core
    `\text{...}` command does not expand TeX macros inside its argument —
    it inserts the literal characters between the braces verbatim,
    including any backslash. So `\text{lifetime\_pd\_now}` renders as the
    literal glyph sequence  l i f e t i m e \ _ p d \ _ n o w  — a visible
    backslash before every underscore — even though `\_` is a perfectly
    valid escaped-underscore macro in *ordinary* math mode (outside
    `\text{}`), which is why other underscore usage on the same page (e.g.
    `\underbrace{...}_{...}` subscripts, which use a bare `_`, not `\_`)
    renders fine and made this look like an isolated glitch rather than a
    systematic one.

    The clean fix (verified through this harness, see
    notes/assets/fix_math_escapes.py): inside `\text{...}`, drop the
    backslash and leave a bare `_` — MathJax's `\text{}` treats it as a
    literal underscore character (it is not a math-mode subscript trigger
    inside `\text{}`), so `\text{lifetime_pd_now}` renders correctly with
    no visible backslash and no semantic change to the identifier.

HOW THIS HARNESS WORKS:
  1. extract_math_expressions() walks the raw HTML once (script/style
     blocks masked out) and pulls out every math span in document order,
     honouring the SAME delimiter set and precedence as the chapters'
     `window.MathJax.tex` config: display `$$...$$` / `\[...\]`, inline
     `\(...\)` / single `$...$`, with `\$` treated as a literal escaped
     dollar (processEscapes: true) per convention. Extracted expressions
     are HTML-entity-decoded (&lt; -> <, etc.) because that is what
     MathJax actually sees in the browser: it reads the DOM's already-
     decoded textContent, not raw HTML source.
  2. Each expression is rendered by notes/assets/.mathjax_env/render_cli.js,
     which loads the EXACT SAME browser bundle the chapters reference
     (`mathjax@3`'s `es5/tex-svg.js`, vendored via `npm install mathjax@3`
     into notes/assets/.mathjax_env/node_modules/) inside a jsdom window,
     configured with the SAME `window.MathJax = {tex:..., svg:...}` block
     every chapter uses, and calls the bundle's own `MathJax.tex2svg()`.
     This avoids guessing which TeX packages a hand-built config would
     need (an earlier attempt using the standalone `mathjax-full` Node API
     with a manually chosen package list produced false-positive merrors
     on `\tfrac`, `\dfrac`, `\mathbb`, `\iff`, `\blacksquare` — all of
     which the real bundle renders fine).
  3. A file FAILS a given expression if:
       (a) MathJax raised a parse error, or
       (b) an `merror` node appears in the rendered output, or
       (c) the rendered SVG glyph stream contains a literal backslash
           character (data-c="5C") — the visible-backslash defect.

Usage:
    uv run --no-sync notes/assets/verify_math.py notes/chapters/*.html
    uv run --no-sync notes/assets/verify_math.py notes/chapters/ch01_ifrs9_foundations_staging.html

Exit code 0 iff every expression in every file renders clean; else 1.
Requires `node` on PATH and notes/assets/.mathjax_env/node_modules/
populated (`cd notes/assets/.mathjax_env && npm install mathjax@3 jsdom`).
"""
from __future__ import annotations

import html as html_mod
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

RENDER_CLI = Path(__file__).parent / ".mathjax_env" / "render_cli.js"


# ---------------------------------------------------------------------------
# Extraction — shared with check_notes.py's static screen (check 7).
# ---------------------------------------------------------------------------
def _mask_blocks(html: str, tag: str) -> str:
    def _mask(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", _mask, html, flags=re.DOTALL | re.IGNORECASE)


def iter_math_spans_raw(html: str) -> list[dict]:
    """Return every math span in document order as RAW (undecoded) byte
    offsets into `html`: {"start", "end", "display", "line", "delim"},
    where html[start:end] is the exact source text between the delimiters
    (no HTML-entity decoding — useful for precise in-place text editing,
    see fix_math_escapes.py).

    Scans the same way MathJax's own delimiter matcher does: at each
    position, prefer the longest/most-specific opening delimiter ($$ or
    \\[ before $ or \\(), and treat `\\$` as a literal escaped dollar
    (matches `processEscapes: true` in the chapters' MathJax config).
    Script/style bodies are masked (not removed) so offsets/line numbers
    stay correct for the rest of the document.
    """
    masked = _mask_blocks(html, "script")
    masked = _mask_blocks(masked, "style")

    results: list[dict] = []
    i = 0
    n = len(masked)
    while i < n:
        two = masked[i : i + 2]
        if two == "\\$":
            i += 2
            continue
        if two == "\\[":
            end = masked.find("\\]", i + 2)
            if end == -1:
                break
            results.append(
                {"start": i + 2, "end": end, "display": True,
                 "line": masked.count("\n", 0, i) + 1, "delim": "\\[ \\]"}
            )
            i = end + 2
            continue
        if two == "\\(":
            end = masked.find("\\)", i + 2)
            if end == -1:
                break
            results.append(
                {"start": i + 2, "end": end, "display": False,
                 "line": masked.count("\n", 0, i) + 1, "delim": "\\( \\)"}
            )
            i = end + 2
            continue
        if two == "$$":
            end = masked.find("$$", i + 2)
            if end == -1:
                break
            results.append(
                {"start": i + 2, "end": end, "display": True,
                 "line": masked.count("\n", 0, i) + 1, "delim": "$$ $$"}
            )
            i = end + 2
            continue
        if masked[i] == "$":
            j = i + 1
            while j < n:
                if masked[j : j + 2] == "\\$":
                    j += 2
                    continue
                if masked[j] == "$":
                    break
                j += 1
            if j >= n:
                break
            results.append(
                {"start": i + 1, "end": j, "display": False,
                 "line": masked.count("\n", 0, i) + 1, "delim": "$ $"}
            )
            i = j + 1
            continue
        i += 1
    return results


def extract_math_expressions(html: str) -> list[dict]:
    """Return every math span in document order as
    {"expr": str, "display": bool, "line": int, "delim": str}, HTML-entity-
    decoded (&lt; -> <, etc.) because that is what MathJax actually sees in
    the browser: it reads the DOM's already-decoded textContent, not raw
    HTML source. See iter_math_spans_raw() for the undecoded byte offsets.
    """
    return [
        {
            "expr": html_mod.unescape(html[span["start"] : span["end"]]),
            "display": span["display"],
            "line": span["line"],
            "delim": span["delim"],
        }
        for span in iter_math_spans_raw(html)
    ]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def render_batch(exprs: list[dict]) -> list[dict]:
    """Render a list of {"expr","display"} through MathJax via Node. Returns
    one result dict per input, in order (see render_cli.js docstring)."""
    if not exprs:
        return []
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node not found on PATH — verify_math.py requires Node.js")
    if not RENDER_CLI.is_file():
        raise RuntimeError(
            f"{RENDER_CLI} not found — run: cd {RENDER_CLI.parent} && npm install mathjax@3 jsdom"
        )
    payload = json.dumps([{"expr": e["expr"], "display": e["display"]} for e in exprs])
    proc = subprocess.run(
        [node, str(RENDER_CLI)],
        input=payload,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"render_cli.js failed (exit {proc.returncode}): {proc.stderr.strip()}")
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def check_file(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    spans = extract_math_expressions(html)
    if not spans:
        return []
    results = render_batch(spans)
    errors = []
    for span, res in zip(spans, results):
        loc = f"line {span['line']} ({span['delim']})"
        if not res.get("ok"):
            errors.append(f"{loc}: MathJax parse error: {res.get('error')}\n        expr: {span['expr']!r}")
            continue
        if res.get("hasMerror"):
            errors.append(f"{loc}: MathJax rendered an <merror> node\n        expr: {span['expr']!r}")
        if res.get("hasBackslash"):
            errors.append(
                f"{loc}: visible backslash glyph in rendered output "
                f"(rendered as {res.get('glyphText')!r})\n        expr: {span['expr']!r}"
            )
    return errors


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    overall_ok = True
    total_defects = 0
    for arg in argv:
        path = Path(arg)
        if not path.is_file():
            print(f"WARN: not a file, skipping: {arg}", file=sys.stderr)
            continue
        try:
            errors = check_file(path)
        except RuntimeError as e:
            print(f"[ERROR] {path}: {e}", file=sys.stderr)
            overall_ok = False
            continue
        file_ok = not errors
        overall_ok = overall_ok and file_ok
        total_defects += len(errors)
        print(f"[{'PASS' if file_ok else 'FAIL'}] {path}  ({len(errors)} defect(s))")
        for e in errors:
            print(f"    - {e}")

    print()
    print(f"TOTAL DEFECTS: {total_defects}")
    print("RESULT:", "PASS" if overall_ok else "FAIL")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
