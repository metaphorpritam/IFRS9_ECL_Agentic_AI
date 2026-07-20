# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
r"""
fix_math_escapes.py — mechanical fix for the visible-backslash MathJax
defect documented in notes/assets/verify_math.py.

ROOT CAUSE (see verify_math.py's docstring for the full derivation): the
chapters' plain `tex-svg.js` MathJax bundle does not expand TeX macros
inside `\text{...}` (no `textmacros` package loaded), so an escaped
underscore `\_` used for a snake_case identifier INSIDE `\text{...}`
renders as a literal backslash glyph followed by an underscore glyph.

TARGET CONVENTION (verified by rendering both forms through
notes/assets/.mathjax_env/render_cli.js before adopting this transform):
  - `\_` INSIDE `\text{...}`   -> BROKEN (visible backslash). FIX: strip
    the backslash, leaving a bare `_`. Inside `\text{...}`, MathJax's base
    `\text` command treats `_` as a literal character, not a subscript
    trigger, so `\text{lifetime_pd_now}` renders identically to the
    intended `lifetime_pd_now` with no visible backslash.
  - `\_` OUTSIDE `\text{...}` (bare math mode, e.g. `$hpi\_growth$`) ->
    ALREADY CLEAN. `\_` is a core TeX macro in ordinary math mode and
    renders as a plain underscore character. This form is common in the
    corpus (e.g. ch06) and must be LEFT ALONE — stripping the backslash
    there would change `_` into a live subscript trigger (a semantically
    different construct), which this script must not do.
  - The SAME root cause generalises beyond the underscore: a corpus-wide
    scan for other escaped special characters inside `\text{...}` found
    two live instances of `\&` (e.g. `\text{...13q R\&S window...}`),
    which fails identically (visible backslash) and was likewise verified
    clean once the backslash is stripped (`\text{...R&S window...}`
    renders a plain "&"). No other escaped special character
    (`\%`, `\$`, `\#`, ...) occurs inside any `\text{...}` in this corpus,
    so the transform below only needs to cover `_` and `&`; if a future
    chapter introduces another one, verify it the same way before adding
    it here.

So the transform is narrowly scoped: within every math span (between the
same delimiters verify_math.py recognises: $$ $$, \[ \], \( \), $ $),
find every `\text{...}` block and replace `\_`/`\&` with `_`/`&`
*inside that block only*. Nothing outside `\text{...}` is touched, and no
math expression is added, removed, or reordered — identifiers only.

Idempotent: a second run finds no `\_`/`\&` left inside any `\text{...}`
block and reports/applies zero changes.

Usage:
    # Dry run (default) — prints every planned change, changes nothing:
    uv run --no-sync notes/assets/fix_math_escapes.py notes/chapters/*.html

    # Apply:
    uv run --no-sync notes/assets/fix_math_escapes.py --apply notes/chapters/*.html
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verify_math import iter_math_spans_raw  # noqa: E402

_TEXT_BLOCK_RE = re.compile(r"\\text\{([^{}]*)\}")
_ESCAPED_SPECIAL_RE = re.compile(r"\\([_&])")


def _fix_text_block(m: re.Match) -> str:
    inner = m.group(1)
    fixed = _ESCAPED_SPECIAL_RE.sub(r"\1", inner)
    return "\\text{" + fixed + "}"


def plan_fixes(html: str) -> list[dict]:
    """Return planned changes as a list of
    {"line", "delim", "before", "after"} — one entry per math span that
    contains at least one `\\text{...}` block with a `\\_` inside it.
    Does not mutate html."""
    changes = []
    for span in iter_math_spans_raw(html):
        raw = html[span["start"] : span["end"]]
        fixed = _TEXT_BLOCK_RE.sub(_fix_text_block, raw)
        if fixed != raw:
            changes.append(
                {
                    "line": span["line"],
                    "delim": span["delim"],
                    "before": raw,
                    "after": fixed,
                    "start": span["start"],
                    "end": span["end"],
                }
            )
    return changes


def apply_fixes(html: str, changes: list[dict]) -> str:
    """Apply planned changes (from plan_fixes, on the SAME html string) by
    rewriting spans back-to-front so earlier offsets stay valid."""
    out = html
    for ch in sorted(changes, key=lambda c: c["start"], reverse=True):
        out = out[: ch["start"]] + ch["after"] + out[ch["end"] :]
    return out


def process_file(path: Path, apply: bool) -> int:
    html = path.read_text(encoding="utf-8")
    changes = plan_fixes(html)
    if not changes:
        print(f"[OK] {path}  (0 change(s))")
        return 0

    print(f"[{'APPLY' if apply else 'DRY-RUN'}] {path}  ({len(changes)} change(s))")
    for ch in changes:
        print(f"    line {ch['line']} ({ch['delim']}):")
        print(f"        before: {ch['before']!r}")
        print(f"        after:  {ch['after']!r}")

    if apply:
        new_html = apply_fixes(html, changes)
        path.write_text(new_html, encoding="utf-8")

    return len(changes)


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    files = [a for a in argv if a != "--apply"]
    if not files:
        print(__doc__)
        return 2

    total = 0
    for arg in files:
        p = Path(arg)
        if not p.is_file():
            print(f"WARN: not a file, skipping: {arg}", file=sys.stderr)
            continue
        total += process_file(p, apply)

    print()
    print(f"TOTAL {'CHANGES APPLIED' if apply else 'PLANNED CHANGES'}: {total}")
    if not apply and total:
        print("(dry run — re-run with --apply to write changes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
