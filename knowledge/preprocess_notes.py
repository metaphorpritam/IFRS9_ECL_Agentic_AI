# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "lxml"]
# ///
"""Pre-process init_docs/ifrs9_credit_risk_notes.html (MASTER_PLAN §3.5).

Outputs:
  knowledge/sources/ifrs9_credit_risk_notes.md   structured markdown, one heading per line
  knowledge/sources/img/figNN.png                the 10 embedded figures, extracted
  <scratch>/worked_examples.md                   every .ex/.thm/.defn box with context (fixture input)
"""
import base64, re, sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

REPO = Path("/mnt/d/Python-UV/IFRS9_ECL_Agentic_AI")
SRC = REPO / "init_docs/ifrs9_credit_risk_notes.html"
OUT_DIR = REPO / "knowledge/sources"
IMG_DIR = OUT_DIR / "img"
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "knowledge"
IMG_DIR.mkdir(parents=True, exist_ok=True)

soup = BeautifulSoup(SRC.read_text(encoding="utf-8"), "lxml")

# ---------- inline conversion ----------
def inline_md(el) -> str:
    parts = []
    for node in el.children if isinstance(el, Tag) else [el]:
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif node.name in ("strong", "b"):
            parts.append("**" + inline_md(node).strip() + "**")
        elif node.name in ("em", "i"):
            parts.append("*" + inline_md(node).strip() + "*")
        elif node.name == "code":
            parts.append("`" + node.get_text() + "`")
        elif node.name == "a":
            href = node.get("href", "")
            txt = inline_md(node).strip()
            parts.append(f"[{txt}]({href})" if href.startswith("http") else txt)
        elif node.name == "br":
            parts.append("  \n")
        elif node.name in ("sub", "sup", "span"):
            parts.append(inline_md(node))
        else:
            parts.append(inline_md(node))
    return "".join(parts)

def table_md(tbl: Tag) -> str:
    rows = tbl.find_all("tr")
    if not rows:
        return ""
    out = []
    for i, tr in enumerate(rows):
        cells = [re.sub(r"\s+", " ", inline_md(td)).strip().replace("|", "\\|")
                 for td in tr.find_all(["th", "td"])]
        out.append("| " + " | ".join(cells) + " |")
        if i == 0:
            out.append("|" + "|".join([" --- "] * len(cells)) + "|")
    return "\n".join(out)

BOX_LABEL = {"defn": "Definition", "thm": "Theorem", "ex": "Worked Example",
             "warn": "Pitfall", "note": "Note", "summary": "Summary"}

fig_counter = 0
fig_records = []   # (n, filename, caption)

consumed_captions = set()

def figure_md(img: Tag) -> str:
    """Handle <img class="fig"> with a sibling <div class="figcap"> caption."""
    global fig_counter
    cap_el = img.find_next_sibling(
        lambda t: isinstance(t, Tag) and t.name == "div" and "figcap" in (t.get("class") or []))
    caption = ""
    if cap_el is not None:
        caption = re.sub(r"\s+", " ", inline_md(cap_el)).strip()
        consumed_captions.add(cap_el)
    src = img.get("src", "")
    m = re.match(r"data:image/(\w+);base64,(.*)", src, re.S)
    if not m:
        return f"*(figure without embedded image: {caption})*"
    fig_counter += 1
    fname = f"fig{fig_counter:02d}.png"
    (IMG_DIR / fname).write_bytes(base64.b64decode(m.group(2)))
    fig_records.append((fig_counter, fname, caption))
    alt = caption.replace("[", "(").replace("]", ")")  # ']' in alt text breaks md image parsers
    return f"![{alt}](img/{fname})\n\n*{caption}*"

# ---------- walk the document ----------
body = soup.body or soup
md_lines = []
examples_out = []          # for worked_examples.md
current_h2 = current_h3 = ""
h2_num = 0
h3_counters = {}

title = soup.find("h1")
md_lines.append("# " + (title.get_text(strip=True) if title else "IFRS 9 Credit Risk Modelling — Complete Study Notes"))
md_lines.append("")

def renumber_h3(text: str, parent_num: int) -> str:
    """Fix stale H3 numbers (duplicate '11.1' bug): force prefix to parent section number."""
    m = re.match(r"^(\d+)\.(\d+)\s+(.*)$", text)
    if not m:
        return text
    h3_counters.setdefault(parent_num, 0)
    h3_counters[parent_num] += 1
    return f"{parent_num}.{h3_counters[parent_num]} {m.group(3)}"

skip_parents = set()
for el in body.find_all(["h2", "h3", "p", "table", "figure", "img", "ul", "ol", "div"]):
    # skip elements inside boxes/figures/tables we already rendered
    if any(p in skip_parents for p in el.parents):
        continue
    if el.name == "h2":
        current_h2 = el.get_text(strip=True)
        m = re.match(r"^(\d+)", current_h2)
        h2_num = int(m.group(1)) if m else h2_num + 1
        anchor = el.get("id", "")
        md_lines += [f"\n## {current_h2}" + (f" {{#{anchor}}}" if anchor else ""), ""]
        current_h3 = ""
    elif el.name == "h3":
        raw = el.get_text(strip=True)
        current_h3 = renumber_h3(raw, h2_num)
        anchor = el.get("id", "")
        md_lines += [f"\n### {current_h3}" + (f" {{#{anchor}}}" if anchor else ""), ""]
    elif el.name == "img":
        if "fig" in (el.get("class") or []):
            md_lines += [figure_md(el), ""]
    elif el.name == "div" and el.get("class"):
        cls = set(el.get("class"))
        if "figcap" in cls:
            if el not in consumed_captions:  # caption with no image (e.g. table caption)
                md_lines += ["*" + re.sub(r"\s+", " ", inline_md(el)).strip() + "*", ""]
            continue
        kind = next((k for k in BOX_LABEL if k in cls), None)
        if kind is None:
            continue  # layout div — children will be visited separately
        skip_parents.add(el)
        inner_parts = []
        for child in el.find_all(["p", "table", "ul", "ol"], recursive=True):
            if child.name == "table":
                inner_parts.append(table_md(child))
            elif child.name in ("ul", "ol"):
                for li in child.find_all("li", recursive=False):
                    inner_parts.append("- " + re.sub(r"\s+", " ", inline_md(li)).strip())
            else:
                inner_parts.append(re.sub(r"\s+", " ", inline_md(child)).strip())
        if not inner_parts:
            inner_parts = [re.sub(r"\s+", " ", inline_md(el)).strip()]
        block = f"**{BOX_LABEL[kind]}.** " + "\n\n".join(p for p in inner_parts if p)
        md_lines += ["> " + block.replace("\n", "\n> "), ""]
        if kind in ("ex", "thm", "defn"):
            examples_out.append(
                f"## [{kind}] {current_h2}" + (f" › {current_h3}" if current_h3 else "") +
                "\n\n" + "\n\n".join(inner_parts) + "\n")
    elif el.name == "figure":
        skip_parents.add(el)
        md_lines += [figure_md(el), ""]
    elif el.name == "table":
        skip_parents.add(el)
        md_lines += [table_md(el), ""]
    elif el.name in ("ul", "ol"):
        skip_parents.add(el)
        for li in el.find_all("li", recursive=False):
            md_lines.append("- " + re.sub(r"\s+", " ", inline_md(li)).strip())
        md_lines.append("")
    elif el.name == "p":
        txt = re.sub(r"\s+", " ", inline_md(el)).strip()
        if txt:
            md_lines += [txt, ""]

out_md = OUT_DIR / "ifrs9_credit_risk_notes.md"
out_md.write_text("\n".join(md_lines), encoding="utf-8")

ex_path = SCRATCH / "worked_examples.md"
ex_path.write_text(
    "# Worked examples / theorems / definitions extracted from ifrs9_credit_risk_notes.html\n\n"
    + "\n".join(examples_out), encoding="utf-8")

print(f"markdown: {out_md}  ({out_md.stat().st_size/1024:.0f} KB, {len(md_lines)} lines)")
print(f"figures : {fig_counter} -> {IMG_DIR}")
print(f"examples: {len(examples_out)} boxes -> {ex_path}")
for n, f, c in fig_records:
    print(f"  fig{n:02d}: {c[:90]}")
