"""
Read every PNG in ./img/ and write img_data.py with a dict of base64 strings.

Usage:
    python encode_imgs.py            # default: reads ./img/, writes ./img_data.py
    python encode_imgs.py img/ out.py

The resulting file looks like:
    IMG = {
        '01_amtrak_series': 'iVBORw0KGgoA…',
        '02_partition':     'iVBORw0KGgoA…',
        ...
    }

build_final.py imports this dict to substitute {{IMG:KEY}} placeholders.
"""
import base64
import os
import sys


def encode_directory(img_dir: str, out_path: str) -> int:
    if not os.path.isdir(img_dir):
        raise FileNotFoundError(f"No directory: {img_dir}")

    items = []
    non_png = [fn for fn in sorted(os.listdir(img_dir))
               if fn.lower().endswith(('.jpg', '.jpeg', '.svg', '.gif', '.webp'))]
    if non_png:
        print(f"WARNING: {len(non_png)} non-PNG image(s) IGNORED — this pipeline and "
              f"the template's data:image/png MIME are PNG-only. Convert first: "
              + ", ".join(non_png), file=sys.stderr)
    for fn in sorted(os.listdir(img_dir)):
        if not fn.lower().endswith('.png'):
            continue
        with open(os.path.join(img_dir, fn), 'rb') as f:
            b = base64.b64encode(f.read()).decode('ascii')
        key = os.path.splitext(fn)[0]
        items.append((key, b))
        print(f"  {key}: {len(b):,} chars")

    with open(out_path, 'w', encoding="utf-8") as f:
        f.write("IMG = {\n")
        for k, v in items:
            f.write(f"    '{k}': '{v}',\n")
        f.write("}\n")
    print(f"\nWrote {out_path} with {len(items)} images.")
    return len(items)


if __name__ == "__main__":
    img_dir  = sys.argv[1] if len(sys.argv) > 1 else 'img'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'img_data.py'
    n = encode_directory(img_dir, out_path)
    if n == 0:
        print("WARNING: no PNGs found.", file=sys.stderr)
        sys.exit(1)
