"""
Substitute {{IMG:KEY}} placeholders in notes_template.html with the actual
base64 strings, then write the final self-contained HTML to the outputs dir.

Run this in the working directory after:
  1. notes_template.html exists (with placeholders)
  2. img_data.py exists (run encode_imgs.py first to produce it)

Usage:
    python build_final.py                      # auto-detects template + output path
    python build_final.py path/to/template.html path/to/output.html
"""
import os
import re
import sys


def build(template_path: str, output_path: str) -> int:
    # Import img_data dynamically — must be on path
    here = os.path.dirname(os.path.abspath(template_path)) or '.'
    sys.path.insert(0, here)
    try:
        from img_data import IMG
    except ImportError:
        raise SystemExit("img_data.py not found — run encode_imgs.py first")

    with open(template_path, encoding="utf-8") as f:
        html = f.read()

    missing = []
    def repl(m):
        key = m.group(1)
        if key not in IMG:
            missing.append(key)
            return f"<!-- MISSING IMG KEY: {key} -->"
        return IMG[key]

    new_html = re.sub(r'\{\{IMG:([^}]+)\}\}', repl, html)

    if missing:
        raise SystemExit(
            f"\nERROR: {len(missing)} image keys not found in img_data.py:\n  "
            + "\n  ".join(sorted(set(missing)))
            + "\nGenerate the missing PNGs, re-run encode_imgs.py, then re-run build_final.py."
        )

    leftover = re.findall(r'\{\{[A-Z_:0-9a-z]+\}\}', new_html)
    if leftover:
        print(f"WARNING: {len(leftover)} non-IMG placeholders still in HTML:",
              file=sys.stderr)
        for p in sorted(set(leftover)):
            print(f"  {p}", file=sys.stderr)
        print("(These may be intentional template fields like {{TITLE}} — "
              "replace them manually before publishing.)", file=sys.stderr)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding="utf-8") as f:
        f.write(new_html)

    print(f"OK   wrote {output_path}")
    print(f"     size: {len(new_html):,} bytes ({len(new_html)/1024/1024:.2f} MB)")
    print(f"     images embedded: {len(IMG)}")
    return len(new_html)


if __name__ == "__main__":
    tpl = sys.argv[1] if len(sys.argv) > 1 else 'notes_template.html'
    out = sys.argv[2] if len(sys.argv) > 2 else '/mnt/user-data/outputs/notes.html'
    build(tpl, out)
