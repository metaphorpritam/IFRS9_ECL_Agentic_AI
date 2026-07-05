# /// script
# requires-python = ">=3.10"
# ///
"""Caption the figures extracted by ingest_notes.py — the LLM-vision hook.

ingest_notes.py writes offline figure cards (anchor + keywords + OCR) but leaves the
caption line as "(uncaptioned — run caption_figures.py)". This script does two jobs:

  --list   List every uncaptioned figure: its caption-id, asset path, anchor, and the
           keyword/OCR context. The AGENT (Claude Code, or a Claude API vision call) reads
           this, looks at each PNG, and writes a one-to-two sentence caption.
  --apply  Read a JSON map {caption_id: "caption text", ...} and rewrite the matching
           figure cards in the corpus in place. Re-running build_pageindex.py then folds
           the captions into the index so tree-search can find figures by what they show.

This keeps captioning OUT of ingest (which stays cheap and offline) while giving a clean,
idempotent merge path. Native-chart cards (no PNG) are listed too — caption them from
their surrounding text/data. Pure stdlib.

Typical Claude Code loop:
    uv run caption_figures.py <corpus_dir> --list > figs.txt
    # agent: read figs.txt, view each asset PNG, build {id: caption} as captions.json
    uv run caption_figures.py <corpus_dir> --apply captions.json

A caption_id is "<corpus-relative .md file>::<Figure N>", e.g.
"lec03_pdf.md::Figure 4" — stable across re-runs as long as the source is unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CARD_RE = re.compile(r"^### (Figure \d+) \((.*?)\)\s*$")
CAPTION_LINE_RE = re.compile(r"^- caption: .*$", re.MULTILINE)
UNCAPTIONED = "(uncaptioned — run caption_figures.py)"


def _iter_md(corpus: Path):
    for mf in sorted(corpus.rglob("*.md")):
        yield mf


def _parse_cards(md_text: str):
    """Yield (figure_label, anchor, card_block_text, start, end) for each figure card."""
    lines = md_text.splitlines(keepends=True)
    # find heading line indices
    idxs = [i for i, ln in enumerate(lines) if CARD_RE.match(ln.rstrip("\n"))]
    for k, i in enumerate(idxs):
        m = CARD_RE.match(lines[i].rstrip("\n"))
        end = idxs[k + 1] if k + 1 < len(idxs) else len(lines)
        # stop at next "## " section if it comes before the next card
        for j in range(i + 1, end):
            if lines[j].startswith("## "):
                end = j
                break
        yield m.group(1), m.group(2), "".join(lines[i:end]), i, end


def cmd_list(corpus: Path, only_uncaptioned: bool) -> int:
    out = []
    for mf in _iter_md(corpus):
        rel = mf.relative_to(corpus).as_posix()
        text = mf.read_text(encoding="utf-8", errors="replace")
        for label, anchor, block, _, _ in _parse_cards(text):
            is_unc = UNCAPTIONED in block
            if only_uncaptioned and not is_unc:
                continue
            cid = f"{rel}::{label}"
            asset = re.search(r"- asset: `([^`]+)`", block)
            kw = re.search(r"- context_keywords: (.+)", block)
            ocr = re.search(r"- ocr_text: (.+)", block)
            kind = re.search(r"- kind: (.+)", block)
            out.append({
                "caption_id": cid,
                "asset": asset.group(1) if asset else None,
                "kind": kind.group(1).strip() if kind else "",
                "anchor": anchor,
                "context_keywords": kw.group(1).strip() if kw else "",
                "ocr_text": ocr.group(1).strip() if ocr else "",
            })
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\n{len(out)} figure(s) listed.", file=sys.stderr)
    return 0


def cmd_apply(corpus: Path, caps_path: Path) -> int:
    caps = json.loads(caps_path.read_text(encoding="utf-8"))
    if not isinstance(caps, dict):
        print("captions file must be a JSON object {caption_id: caption}", file=sys.stderr)
        return 2
    applied = 0
    # group caption_ids by md file
    by_file: dict[str, dict[str, str]] = {}
    for cid, cap in caps.items():
        rel, _, label = cid.partition("::")
        by_file.setdefault(rel, {})[label] = cap
    for rel, labelmap in by_file.items():
        mf = corpus / rel
        if not mf.exists():
            print(f"  warn: {rel} not found — skipping", file=sys.stderr)
            continue
        text = mf.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        # rebuild, replacing caption line inside matching cards
        new_chunks = []
        cursor = 0
        for label, anchor, block, start, end in _parse_cards(text):
            if label not in labelmap:
                continue
            cap = labelmap[label].replace("\n", " ").strip()
            new_block = CAPTION_LINE_RE.sub(f"- caption: {cap}", block, count=1)
            if "- caption:" not in new_block:  # card had none -> append
                new_block = new_block.rstrip("\n") + f"\n- caption: {cap}\n"
            new_chunks.append((start, end, new_block))
            applied += 1
        if not new_chunks:
            continue
        # apply chunk replacements back-to-front to keep indices valid
        for start, end, new_block in sorted(new_chunks, reverse=True):
            lines[start:end] = [new_block if not new_block.endswith("\n")
                                else new_block]
        mf.write_text("".join(lines), encoding="utf-8")
        print(f"  updated {rel}: {len(new_chunks)} caption(s)")
    print(f"\napplied {applied} caption(s). Re-run build_pageindex.py to refresh the index.")
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus_dir")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="list uncaptioned figures as JSON")
    g.add_argument("--list-all", action="store_true", help="list ALL figures as JSON")
    g.add_argument("--apply", metavar="CAPTIONS_JSON", help="merge {id: caption} JSON")
    args = ap.parse_args(argv)
    corpus = Path(args.corpus_dir)
    if not corpus.exists():
        print(f"no such corpus dir: {corpus}", file=sys.stderr)
        return 2
    if args.apply:
        return cmd_apply(corpus, Path(args.apply))
    return cmd_list(corpus, only_uncaptioned=not args.list_all)


if __name__ == "__main__":
    raise SystemExit(main())
