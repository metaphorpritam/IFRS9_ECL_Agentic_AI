# /// script
# requires-python = ">=3.10"
# ///
"""Answer-routing over the wiki: question -> ordered reading list.

No embeddings. Retrieval is (1) lexical seeding — score every page on
title/alias, tag, heading, and body-frequency hits — then (2) typed graph
expansion: neighbours of strong seeds inherit a fraction of their score
(typed frontmatter edges 0.6, body "mentions" 0.4, halved per extra hop).
Deterministic: same wiki + same question => same list.

The output is a READING LIST, not an answer: open the pages top-down, answer
from them citing `page.md#Heading`, then FILE THE ANSWER BACK (update a page,
or record a decision/question via wiki_log.py) so the wiki compounds.

Usage:
    python wiki_query.py <wiki_dir> "how are discounts applied to pricing?"
    ... --top 8 --hops 1 --explain --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki_graph import build_graph, _mask_fences, parse_frontmatter  # noqa: E402

STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is",
        "are", "was", "be", "how", "what", "why", "when", "where", "which",
        "does", "do", "did", "with", "between", "its", "it", "this", "that",
        "into", "about", "we", "i", "you", "our", "my", "can", "should"}

W_TITLE, W_TAG, W_HEAD, W_BODY, BODY_CAP = 4.0, 3.0, 2.0, 1.0, 5
EDGE_W = {"mentions": 0.4}
EDGE_W_DEFAULT = 0.6
HOP_DECAY = 0.5


def _stem(t: str) -> str:
    """Cheap suffix stem so discounts/discount, applies/applied match. Applied
    to BOTH the question and page text, and body matching is substring-based,
    so stems stay consistent."""
    return re.sub(r"(?:ing|ed|es|s)$", "", t) if len(t) > 4 else t


def tokens(s: str) -> list[str]:
    out = []
    for t in re.findall(r"[a-z0-9][a-z0-9_-]*", s.lower()):
        if t in STOP or len(t) <= 1:
            continue
        out.append(_stem(t))
    return out


def score_pages(graph: dict, wiki: Path, q_tokens: list[str]):
    """Return {id: (score, why:dict)} from lexical evidence."""
    out = {}
    qset = set(q_tokens)
    for n in graph["nodes"]:
        title_toks = set(tokens(n["title"])) | set(tokens(n["id"])) \
            | {t for a in n["aliases"] for t in tokens(a)}
        tag_toks = {t for tag in n["tags"] for t in tokens(tag)}
        head_hits = {}
        for h in n["headings"]:
            hit = qset & set(tokens(h["text"]))
            if hit:
                head_hits[h["text"]] = sorted(hit)
        body = ""
        try:
            _, body, _, _, _ = parse_frontmatter(
                (wiki / n["path"]).read_text(encoding="utf-8"), n["path"])
            body = _mask_fences(body).lower()
        except Exception as e:
            print(f"  warn: {n['path']} unreadable while scoring — "
                  f"{type(e).__name__}: {e}", file=sys.stderr)
        t_hit = sorted(qset & title_toks)
        g_hit = sorted(qset & tag_toks)
        b_freq = {t: min(len(re.findall(re.escape(t), body)), BODY_CAP)
                  for t in q_tokens}
        b_score = sum(v for v in b_freq.values())
        score = (W_TITLE * len(t_hit) + W_TAG * len(g_hit)
                 + W_HEAD * sum(len(v) for v in head_hits.values())
                 + W_BODY * b_score)
        if score > 0:
            out[n["id"]] = (score, {
                "title_hits": t_hit, "tag_hits": g_hit,
                "heading_hits": head_hits,
                "body_hits": {t: v for t, v in b_freq.items() if v},
            })
    return out


def expand(graph: dict, seeds: dict, hops: int):
    """Propagate seed scores across edges. Returns {id: (score, via:list)}."""
    adj: dict[str, list[tuple[str, str, str]]] = {}
    for e in graph["edges"]:
        adj.setdefault(e["src"], []).append((e["dst"], e["type"], "→"))
        adj.setdefault(e["dst"], []).append((e["src"], e["type"], "←"))
    scores = {nid: s for nid, (s, _) in seeds.items()}
    via: dict[str, list[str]] = {nid: [] for nid in seeds}
    frontier = dict(scores)
    for hop in range(1, hops + 1):
        nxt: dict[str, float] = {}
        for nid in sorted(frontier):
            for nbr, etype, dirn in sorted(adj.get(nid, [])):
                w = EDGE_W.get(etype, EDGE_W_DEFAULT)
                gain = frontier[nid] * w * (HOP_DECAY ** (hop - 1))
                if gain < 0.05:
                    continue
                if gain > nxt.get(nbr, 0.0):
                    nxt[nbr] = gain
                arrow = (f"{nid} —{etype}→ here" if dirn == "→"
                         else f"{nid} ←{etype}— here")
                via.setdefault(nbr, []).append(f"{arrow} (+{gain:.1f})")
        for nbr, gain in nxt.items():
            scores[nbr] = scores.get(nbr, 0.0) + gain
        frontier = nxt
    return scores, via


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wiki_dir")
    ap.add_argument("question")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--hops", type=int, default=1)
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    wiki = Path(args.wiki_dir)
    graph = build_graph(wiki)
    for w in graph["warnings"]:
        print(f"  warn: {w}", file=sys.stderr)

    q_tokens = tokens(args.question)
    if not q_tokens:
        print("no usable tokens in the question after stop-word removal",
              file=sys.stderr)
        return 1

    seeds = score_pages(graph, wiki, q_tokens)
    if not seeds:
        print("no page matches any question token — the wiki may not cover "
              "this yet. Compile a page for it, then re-query.")
        return 0
    scores, via = expand(graph, seeds, args.hops)
    by_id = {n["id"]: n for n in graph["nodes"]}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:args.top]

    results = []
    for nid, sc in ranked:
        n = by_id[nid]
        why = seeds.get(nid, (0, {}))[1]
        anchors = list(why.get("heading_hits", {}).keys()) if why else []
        results.append({"id": nid, "path": n["path"], "title": n["title"],
                        "type": n["type"], "score": round(sc, 2),
                        "anchors": anchors, "lexical": why,
                        "via": via.get(nid, [])})

    if args.as_json:
        print(json.dumps({"question": args.question, "tokens": q_tokens,
                          "results": results}, indent=2, ensure_ascii=False))
        return 0

    print(f"reading list for: {args.question!r}   (tokens: {', '.join(q_tokens)})")
    for r, item in enumerate(results, 1):
        line = (f"{r:>2}. {item['path']:<38} {item['score']:>6}  "
                f"[{item['type'] or '?'}] {item['title']}")
        print(line)
        if item["anchors"]:
            print(f"      anchors: " + "; ".join(f"#{a}" for a in item["anchors"]))
        if args.explain:
            lex = item["lexical"]
            if lex:
                bits = []
                if lex.get("title_hits"):
                    bits.append("title:" + ",".join(lex["title_hits"]))
                if lex.get("tag_hits"):
                    bits.append("tags:" + ",".join(lex["tag_hits"]))
                if lex.get("body_hits"):
                    bits.append("body:" + ",".join(
                        f"{t}×{v}" for t, v in lex["body_hits"].items()))
                if bits:
                    print("      lexical: " + "  ".join(bits))
            for v in item["via"][:4]:
                print(f"      graph:   {v}")
    print("\nnow: read top-down, answer citing page.md#Heading, then FILE IT "
          "BACK (update the page or wiki_log.py a decision/question) and "
          "re-run wiki_graph.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
