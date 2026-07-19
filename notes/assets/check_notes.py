# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
check_notes.py — the shared QA gate for IFRS9 study-notes HTML chapters.

Usage:
    uv run --no-sync notes/assets/check_notes.py <file1.html> [file2.html ...]
    uv run --no-sync notes/assets/check_notes.py notes/chapters/*.html

Checks run per HTML file (see notes/plan/conventions.md "QA gate" for the
full rationale of each):

  1. HTML tag balance          — every non-void opening tag has a matching close.
  2. Every <img> resolves      — data: URIs are fine as-is; relative src must
                                   exist on disk relative to the HTML file.
  3. MathJax delimiter parity  — '$' count is even (after stripping escaped
                                   dollars); '\\[' / '\\]' counts match; '\\(' / '\\)' counts match.
  4. No leftover placeholders  — zero '{{IMG:' (or any '{{...}}') tokens remain.
  5. Every .quiz has answers   — each <div class="quiz"> has >=2 <li> questions
                                   and at least as many <details> (answer reveals)
                                   as <li> questions.
  6. Widget JS parses          — every local <script src="....js"> referenced by
                                   the file (and widgets.js itself, if this run
                                   covers it) parses: `node --check` if node is on
                                   PATH, else a comment-stripping brace/paren/
                                   bracket balance check.

Exit code: 0 if every file PASSes every check, else 1. Prints a per-file
PASS/FAIL line and, on FAIL, the specific failing checks with details.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


# ---------------------------------------------------------------------------
# Check 1 — HTML tag balance
# ---------------------------------------------------------------------------
class _BalanceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in VOID_ELEMENTS:
            return
        self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag: str, attrs) -> None:
        return  # self-closing (<foo/>) — nothing to balance

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_ELEMENTS:
            return
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: closing </{tag}> with nothing open")
            return
        # Pop, tolerating minor mismatches by searching back a short window
        # (browsers do this too); flag if not found nearby.
        for i in range(len(self.stack) - 1, max(-1, len(self.stack) - 6), -1):
            if self.stack[i][0] == tag:
                unclosed = self.stack[i + 1:]
                for utag, uline in unclosed:
                    self.errors.append(f"line {uline}: <{utag}> never closed (before </{tag}> at line {self.getpos()[0]})")
                del self.stack[i:]
                return
        self.errors.append(f"line {self.getpos()[0]}: closing </{tag}> does not match recent open tags")


def check_tag_balance(html: str) -> list[str]:
    p = _BalanceParser()
    p.feed(html)
    errors = list(p.errors)
    for tag, line in p.stack:
        errors.append(f"line {line}: <{tag}> never closed (end of file)")
    return errors


# ---------------------------------------------------------------------------
# Check 2 — every <img> resolves
# ---------------------------------------------------------------------------
def check_img_resolves(html: str, base_dir: Path) -> list[str]:
    errors = []
    for m in re.finditer(r'<img\b[^>]*\bsrc\s*=\s*"([^"]*)"', html, re.IGNORECASE):
        src = m.group(1)
        line = html.count("\n", 0, m.start()) + 1
        if src.startswith("data:"):
            if len(src) < 40:
                errors.append(f"line {line}: <img> data: URI looks truncated/empty ({len(src)} chars)")
            continue
        if src.startswith(("http://", "https://")):
            continue  # remote — not this gate's concern
        candidate = (base_dir / src).resolve()
        if not candidate.is_file():
            errors.append(f"line {line}: <img src=\"{src}\"> does not resolve to a file ({candidate})")
    return errors


# ---------------------------------------------------------------------------
# Check 3 — MathJax delimiter parity
# ---------------------------------------------------------------------------
def check_mathjax_delimiters(html: str) -> list[str]:
    errors = []
    # Strip HTML tags/comments and script/style blocks so stray '$' in CSS/JS
    # (e.g. jQuery-style code, none expected here, but be safe) don't confuse
    # the count. We keep this deliberately simple: MathJax content is prose.
    stripped = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"<style\b[^>]*>.*?</style>", "", stripped, flags=re.DOTALL | re.IGNORECASE)

    # Dollar parity: remove escaped \$ first, then every remaining '$' must pair up.
    dollar_free_of_escapes = stripped.replace("\\$", "")
    dollar_count = dollar_free_of_escapes.count("$")
    if dollar_count % 2 != 0:
        errors.append(f"odd number of unescaped '$' delimiters ({dollar_count}) — inline/display math unbalanced")

    open_br = stripped.count("\\[")
    close_br = stripped.count("\\]")
    if open_br != close_br:
        errors.append(f"'\\[' count ({open_br}) != '\\]' count ({close_br})")

    open_pa = stripped.count("\\(")
    close_pa = stripped.count("\\)")
    if open_pa != close_pa:
        errors.append(f"'\\(' count ({open_pa}) != '\\)' count ({close_pa})")

    return errors


# ---------------------------------------------------------------------------
# Check 4 — no leftover {{...}} placeholders
# ---------------------------------------------------------------------------
def check_no_placeholders(html: str) -> list[str]:
    errors = []
    for m in re.finditer(r"\{\{[A-Za-z0-9_:]+\}\}", html):
        line = html.count("\n", 0, m.start()) + 1
        errors.append(f"line {line}: leftover placeholder {m.group(0)}")
    return errors


# ---------------------------------------------------------------------------
# Check 5 — every .quiz has answers
# ---------------------------------------------------------------------------
def _extract_balanced_divs(html: str, class_needle: str) -> list[str]:
    """Return the inner HTML of every <div class="...class_needle...">...</div>,
    matching nested <div> tags by depth counting."""
    blocks = []
    for m in re.finditer(
        r'<div\b[^>]*\bclass\s*=\s*"[^"]*\b' + re.escape(class_needle) + r'\b[^"]*"[^>]*>',
        html, re.IGNORECASE,
    ):
        start = m.end()
        depth = 1
        pos = start
        for tm in re.finditer(r"<div\b|</div\s*>", html[start:], re.IGNORECASE):
            if tm.group(0).lower().startswith("<div"):
                depth += 1
            else:
                depth -= 1
            if depth == 0:
                pos = start + tm.start()
                break
        blocks.append(html[start:pos])
    return blocks


def check_quiz_answers(html: str) -> list[str]:
    errors = []
    quizzes = _extract_balanced_divs(html, "quiz")
    for i, block in enumerate(quizzes, start=1):
        n_li = len(re.findall(r"<li\b", block, re.IGNORECASE))
        n_details = len(re.findall(r"<details\b", block, re.IGNORECASE))
        if n_li < 2:
            errors.append(f".quiz #{i}: only {n_li} question(s) — need 2-4 'Check yourself' questions")
        if n_li > 4:
            errors.append(f".quiz #{i}: {n_li} question(s) — convention caps 'Check yourself' at 4")
        if n_details < n_li:
            errors.append(f".quiz #{i}: {n_li} question(s) but only {n_details} <details> answer reveal(s)")
    return errors


# ---------------------------------------------------------------------------
# Check 6 — widget JS parses
# ---------------------------------------------------------------------------
def _strip_js_comments_and_strings(js: str) -> str:
    # Remove block comments, line comments, and string/template literal bodies
    # (so braces inside strings don't throw off the balance count). Naive but
    # sufficient for a balance check on hand-written widget code.
    out = []
    i = 0
    n = len(js)
    while i < n:
        two = js[i:i + 2]
        c = js[i]
        if two == "/*":
            end = js.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if two == "//":
            end = js.find("\n", i + 2)
            i = n if end == -1 else end
            continue
        if c in ("'", '"', "`"):
            j = i + 1
            while j < n and js[j] != c:
                if js[j] == "\\":
                    j += 1
                j += 1
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def check_js_parses(js_path: Path) -> list[str]:
    errors: list[str] = []
    node = shutil.which("node")
    if node:
        proc = subprocess.run([node, "--check", str(js_path)], capture_output=True, text=True)
        if proc.returncode != 0:
            errors.append(f"node --check failed: {proc.stderr.strip()}")
        return errors

    # Fallback: comment/string-stripped brace/paren/bracket balance.
    js = js_path.read_text(encoding="utf-8")
    code = _strip_js_comments_and_strings(js)
    pairs = {"{": "}", "(": ")", "[": "]"}
    closers = {v: k for k, v in pairs.items()}
    stack = []
    for idx, ch in enumerate(code):
        if ch in pairs:
            stack.append(ch)
        elif ch in closers:
            if not stack or stack[-1] != closers[ch]:
                line = code.count("\n", 0, idx) + 1
                errors.append(f"line ~{line}: unmatched '{ch}' (brace/paren/bracket balance, node unavailable so this is a heuristic)")
                return errors
            stack.pop()
    if stack:
        errors.append(f"{len(stack)} unclosed opener(s) remaining: {stack} (node unavailable, heuristic check)")
    return errors


def _local_js_srcs(html: str, base_dir: Path) -> list[Path]:
    paths = []
    for m in re.finditer(r'<script\b[^>]*\bsrc\s*=\s*"([^"]+)"', html, re.IGNORECASE):
        src = m.group(1)
        if src.startswith(("http://", "https://")):
            continue
        candidate = (base_dir / src).resolve()
        paths.append(candidate)
    return paths


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def check_file(path: Path) -> dict[str, list[str]]:
    html = path.read_text(encoding="utf-8")
    base_dir = path.parent
    results: dict[str, list[str]] = {}
    results["tag balance"] = check_tag_balance(html)
    results["img resolves"] = check_img_resolves(html, base_dir)
    results["mathjax delimiters"] = check_mathjax_delimiters(html)
    results["no leftover placeholders"] = check_no_placeholders(html)
    results["quiz answers"] = check_quiz_answers(html)

    js_errors: list[str] = []
    checked_js: set[Path] = set()
    for js_path in _local_js_srcs(html, base_dir):
        if js_path in checked_js:
            continue
        checked_js.add(js_path)
        if not js_path.is_file():
            js_errors.append(f"{js_path}: referenced but not found on disk")
            continue
        for e in check_js_parses(js_path):
            js_errors.append(f"{js_path.name}: {e}")
    results["widget js parses"] = js_errors

    return results


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    targets: list[Path] = []
    for arg in argv:
        p = Path(arg)
        if p.is_file():
            targets.append(p)
        else:
            print(f"WARN: not a file, skipping: {arg}", file=sys.stderr)

    # Also standalone-check widgets.js if it was passed directly as a .js arg.
    overall_ok = True
    for path in targets:
        if path.suffix == ".js":
            errors = check_js_parses(path)
            status = "PASS" if not errors else "FAIL"
            print(f"[{status}] {path}  (widget js parses)")
            for e in errors:
                print(f"    - {e}")
            overall_ok = overall_ok and not errors
            continue

        results = check_file(path)
        file_ok = all(not v for v in results.values())
        overall_ok = overall_ok and file_ok
        print(f"[{'PASS' if file_ok else 'FAIL'}] {path}")
        for check_name, errors in results.items():
            mark = "ok" if not errors else f"{len(errors)} issue(s)"
            print(f"    - {check_name}: {mark}")
            for e in errors:
                print(f"        {e}")

    print()
    print("RESULT:", "PASS" if overall_ok else "FAIL")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
