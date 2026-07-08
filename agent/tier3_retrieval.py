"""Tier-3 documentation retrieval over the wiki + IFRS 9 knowledge corpus.

ONE tool, ``query_model_docs(question, k=6)``, for methodology / "how is
this defined" / "why did we choose that" questions — the class of question
Tier-1 (agent/tools_tier1.py) cannot answer because there is no number to
compute, only documentation to read. THE BOUNDARY still holds: the LLM
never invents facts here either. This module does the retrieval
DETERMINISTICALLY (no LLM involved anywhere below); agent/graph.py's
narrator is only allowed to state what the returned passages say, citing
each claim — enforced mechanically by a post-check (see graph.py).

Two sources, reused — not reimplemented — from the two existing skills:

  1. wiki/  (the model-development wiki; typed graph + lexical scoring)
     .claude/skills/llm-wiki/scripts/wiki_query.py — ``tokens``,
     ``score_pages``, ``expand`` — and ``wiki_graph.build_graph`` (re-exported
     by wiki_query). The graph is built once, lazily, and cached at module
     scope (``_wiki_graph()``); same wiki -> same graph -> same ranking.

  2. knowledge/corpus/ (the indexed IFRS9 credit-risk notes)
     .claude/skills/pageindex-plus/scripts/pageindex_query.py — ``load``,
     ``search_tree`` (offline keyword scoring over the PageIndex tree),
     ``get_context`` (full page text for chosen nodes). Loaded once, lazily,
     and cached (``_notes_index()``).

Both scripts are files, not an installed package, so they are loaded via
``importlib.util.spec_from_file_location`` (never copy-pasted).

Citations are REAL anchors, verified at construction time, never invented:

  * wiki passages   -> ``"<page path>#<heading>"``, where ``<page path>`` is
    the page's path relative to wiki/ (e.g. ``pages/ecl-engine.md``) and
    ``<heading>`` is drawn VERBATIM from that exact page's parsed heading
    list (agent/tier3_retrieval never authors a heading string itself — it
    only ever echoes one already found in ``graph["nodes"][i]["headings"]``,
    optionally trimmed at a parenthetical aside, e.g. heading text
    "GATE (frozen 2026-07-05)" -> anchor "GATE"). The passage TEXT is the
    exact lines of the source file between that heading and the next one.
  * notes passages  -> ``"notes §<section> p<start>[-<end>]"``, where
    ``<section>`` is the leading numeral(s) of the PageIndex node's own
    title (e.g. "9.2 Multiple probability-weighted scenarios..." -> "9.2")
    and p<start>-<end> are the node's own ``start_index``/``end_index``
    page numbers — both read straight off the loaded tree, never guessed.

Both retrieval passes are pure functions of (question, the on-disk wiki, the
on-disk knowledge index) — same question, same files => the identical
``passages`` / ``reading_list`` on every call (tests/test_tier3.py pins
this). Only ``tool_call_id`` (an audit sequence number) legitimately varies
call to call.

Audit trail: reuses agent.tools_tier1's own ``_log_call`` — same file
(outputs/agent_log/tool_calls.jsonl), same sequence counter, same lock — so
Tier-1 and Tier-3 calls interleave in one replayable log, exactly as if this
were a fifth Tier-1 tool.
"""

from __future__ import annotations

import importlib.util
import re
import threading
from pathlib import Path
from types import ModuleType

from pydantic import BaseModel, ConfigDict

from agent.tools_tier1 import _log_call

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = PROJECT_ROOT / "wiki"
KNOWLEDGE_INDEX_DIR = PROJECT_ROOT / "knowledge" / "index"

WIKI_QUERY_SCRIPT = (PROJECT_ROOT / ".claude" / "skills" / "llm-wiki"
                     / "scripts" / "wiki_query.py")
PAGEINDEX_QUERY_SCRIPT = (PROJECT_ROOT / ".claude" / "skills"
                         / "pageindex-plus" / "scripts" / "pageindex_query.py")

#: per-passage text cap (characters) — keeps the narrator's context small
#: and bounded, matching the spirit of Tier-1's terse JSON results
MAX_PASSAGE_CHARS = 1600

_NUM_TOKEN_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


# ---------------------------------------------------------------------------
# dynamic import of the two skills' query scripts (files, not packages)
# ---------------------------------------------------------------------------

def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:                 # pragma: no cover
        raise RuntimeError(f"cannot load module spec from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: RLock (not Lock): _wiki_graph()/_notes_index() call _wiki_query_mod()/
#: _pageindex_mod() from inside their own locked block — a plain Lock would
#: deadlock the very first time _wiki_graph() (or _notes_index()) is the
#: FIRST call into this module, before the sub-module is cached.
_INIT_LOCK = threading.RLock()
_WIKI_QUERY_MOD: ModuleType | None = None
_PAGEINDEX_MOD: ModuleType | None = None
_WIKI_GRAPH: dict | None = None
_NOTES_TREE: dict | None = None
_NOTES_PAGES: dict | None = None


def _wiki_query_mod() -> ModuleType:
    global _WIKI_QUERY_MOD
    if _WIKI_QUERY_MOD is None:
        with _INIT_LOCK:
            if _WIKI_QUERY_MOD is None:
                # wiki_query.py does `sys.path.insert(0, <its own dir>)` then
                # `from wiki_graph import build_graph, ...` — loading it via
                # spec_from_file_location still runs that line (its __file__
                # is set correctly), so wiki_graph resolves from the same
                # scripts/ directory without us importing it separately.
                _WIKI_QUERY_MOD = _load_module(WIKI_QUERY_SCRIPT,
                                               "tier3_wiki_query")
    return _WIKI_QUERY_MOD


def _pageindex_mod() -> ModuleType:
    global _PAGEINDEX_MOD
    if _PAGEINDEX_MOD is None:
        with _INIT_LOCK:
            if _PAGEINDEX_MOD is None:
                _PAGEINDEX_MOD = _load_module(PAGEINDEX_QUERY_SCRIPT,
                                              "tier3_pageindex_query")
    return _PAGEINDEX_MOD


def _wiki_graph() -> dict:
    """The wiki's typed graph, built ONCE and cached (module-scope singleton).

    Same wiki/ contents -> the identical graph -> the identical ranking on
    every call, which is what makes ``query_model_docs`` deterministic.
    """
    global _WIKI_GRAPH
    if _WIKI_GRAPH is None:
        with _INIT_LOCK:
            if _WIKI_GRAPH is None:
                _WIKI_GRAPH = _wiki_query_mod().build_graph(WIKI_DIR)
    return _WIKI_GRAPH


def _notes_index() -> tuple[dict, dict]:
    """The PageIndex tree + page text, loaded ONCE and cached."""
    global _NOTES_TREE, _NOTES_PAGES
    if _NOTES_TREE is None:
        with _INIT_LOCK:
            if _NOTES_TREE is None:
                tree, pages = _pageindex_mod().load(str(KNOWLEDGE_INDEX_DIR))
                _NOTES_TREE, _NOTES_PAGES = tree, pages
    return _NOTES_TREE, _NOTES_PAGES


def warm_up() -> None:
    """Build/load both indices now (mirrors tools_tier1.warm_up)."""
    _wiki_graph()
    _notes_index()


# ---------------------------------------------------------------------------
# wiki retrieval: rank pages, then pull the single most relevant heading
# section per page — never the whole page, and never a heading we invented
# ---------------------------------------------------------------------------

_SECTION_TOKEN_CAP = 5      # per-token occurrence cap, mirrors wiki_query's BODY_CAP
_HEADING_HIT_WEIGHT = 2.0   # a heading-TEXT hit outweighs one body-token hit
_DISTINCT_TOKEN_WEIGHT = 10.0  # matching MORE distinct question words beats
                               # repeating the SAME one (a section that only
                               # repeats "ecl" many times is usually just the
                               # page intro, not the section that actually
                               # answers a multi-word question)


def _page_sections(page_path: Path,
                   headings: list[dict]) -> list[tuple[str, int, int]]:
    """[(heading text, start file-line, end file-line)] for one page, in
    heading order — end is the line before the next heading (any level), or
    EOF for the last one. Verbatim from the page's own parsed headings, so
    every (start, end) pair brackets a REAL section of that exact file."""
    ordered = sorted(headings, key=lambda h: h["line"])
    n_lines = len(page_path.read_text(encoding="utf-8").split("\n"))
    out = []
    for i, h in enumerate(ordered):
        start = h["line"]
        end = ordered[i + 1]["line"] - 1 if i + 1 < len(ordered) else n_lines
        out.append((h["text"], start, end))
    return out


def _score_section_text(text: str, q_tokens: list[str]) -> float:
    body = text.lower()
    counts = [min(body.count(t), _SECTION_TOKEN_CAP) for t in q_tokens]
    distinct = sum(1 for c in counts if c > 0)
    return _DISTINCT_TOKEN_WEIGHT * distinct + float(sum(counts))


def _best_section(page_path: Path, headings: list[dict],
                  q_tokens: list[str], heading_hits: dict
                  ) -> tuple[str | None, str]:
    """The (heading, verbatim section text) whose BODY best matches the
    question — not just whichever heading's own TITLE happens to share a
    word, which tends to pick the page's intro over its most relevant
    subsection (e.g. a title heading beats the section that actually
    contains the numbers being asked about). Heading-text hits still add a
    bonus (a heading literally naming the topic is a strong signal); ties
    keep the earliest section, for determinism."""
    if not headings:
        return None, ""
    lines = page_path.read_text(encoding="utf-8").split("\n")
    best_heading, best_text, best_score = None, "", -1.0
    for heading_text, start, end in _page_sections(page_path, headings):
        text = "\n".join(lines[start - 1:end]).strip()
        score = (_score_section_text(text, q_tokens)
                + _HEADING_HIT_WEIGHT * len(heading_hits.get(heading_text, [])))
        if score > best_score:
            best_heading, best_text, best_score = heading_text, text, score
    return best_heading, best_text


def _wiki_anchor(heading_text: str) -> str:
    """Trim a parenthetical aside off a heading for a tidier anchor, e.g.
    'GATE (frozen 2026-07-05)' -> 'GATE'. Always a prefix of a REAL heading."""
    return heading_text.split(" (", 1)[0].strip()


def _wiki_passages(question: str, limit: int) -> tuple[list[dict], list[dict]]:
    wq = _wiki_query_mod()
    graph = _wiki_graph()
    q_tokens = wq.tokens(question)
    if not q_tokens:
        return [], []
    seeds = wq.score_pages(graph, WIKI_DIR, q_tokens)
    if not seeds:
        return [], []
    scores, _via = wq.expand(graph, seeds, hops=1)
    by_id = {n["id"]: n for n in graph["nodes"]}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]

    passages: list[dict] = []
    reading: list[dict] = []
    for nid, sc in ranked:
        n = by_id[nid]
        reading.append({"id": nid, "path": n["path"], "title": n["title"],
                        "score": round(sc, 2)})
        why = seeds.get(nid, (0.0, {}))[1]
        heading_hits = why.get("heading_hits", {}) if why else {}
        headings = n["headings"]
        best, section = _best_section(WIKI_DIR / n["path"], headings,
                                      q_tokens, heading_hits)
        if best is None or not section:
            continue
        # verify the heading is REAL (present in this exact page's parsed
        # headings) before ever citing it — true by construction (_best_
        # section only ever returns a heading it read out of this list),
        # but asserted defensively so the invariant can never silently break
        if not any(h["text"] == best for h in headings):
            continue                                      # pragma: no cover
        citation = f"{n['path']}#{_wiki_anchor(best)}"
        passages.append({
            "source": "wiki",
            "citation": citation,
            "text": section[:MAX_PASSAGE_CHARS],
            "path": n["path"],
            "heading": best,
            "score": round(sc, 2),
        })
    return passages, reading


# ---------------------------------------------------------------------------
# notes-corpus retrieval: pageindex_query.search_tree + get_context
# ---------------------------------------------------------------------------

def _section_number(title: str) -> str | None:
    m = re.match(r"^(\d+(?:\.\d+)*)\b", title.strip())
    return m.group(1) if m else None


def _notes_passages(question: str, limit: int) -> tuple[list[dict], list[dict]]:
    pim = _pageindex_mod()
    tree, pages = _notes_index()
    hits = pim.search_tree(question, tree, top=limit)

    passages: list[dict] = []
    reading: list[dict] = []
    for score, nid, title, start, end, path in hits:
        loc = f"p{start}" if start == end else f"p{start}-{end}"
        reading.append({"node_id": nid, "title": title, "path": path,
                        "pages": loc, "score": score})
        ctx = pim.get_context([nid], tree, pages, max_chars=MAX_PASSAGE_CHARS)
        if not ctx.strip():
            continue
        section = _section_number(title)
        citation = (f"notes §{section} {loc}" if section
                   else f"notes {nid} {loc}")
        passages.append({
            "source": "notes",
            "citation": citation,
            "text": ctx.strip()[:MAX_PASSAGE_CHARS],
            "node_id": nid,
            "title": title,
            "score": score,
        })
    return passages, reading


# ---------------------------------------------------------------------------
# the tool
# ---------------------------------------------------------------------------

def query_model_docs(question: str, k: int = 6) -> dict:
    """Deterministic two-source retrieval for a methodology/knowledge question.

    Splits the ``k`` passage budget roughly in half between the wiki (model
    development: what THIS project's engine does and why) and the notes
    corpus (general IFRS 9 credit-risk methodology). Returns::

        {"passages": [{"source": "wiki"|"notes", "citation": str,
                       "text": str, ...}, ...],
         "reading_list": [...],
         "headline": str, "tool_call_id": "tc-<seq>"}

    Every citation is a REAL, verified anchor (see module docstring). No LLM
    call happens anywhere in this function — retrieval is pure lexical/graph
    scoring over on-disk files, so the same question always returns the
    same passages and reading_list (only ``tool_call_id`` varies).
    """
    q = (question or "").strip()
    if not q:
        raise ValueError("question must be a non-empty string")
    k = max(2, int(k))
    k_wiki = max(1, k // 2)
    k_notes = max(1, k - k_wiki)

    wiki_passages, wiki_reading = _wiki_passages(q, k_wiki)
    notes_passages, notes_reading = _notes_passages(q, k_notes)
    passages = wiki_passages + notes_passages
    reading_list = ([{"source": "wiki", **r} for r in wiki_reading]
                    + [{"source": "notes", **r} for r in notes_reading])

    if passages:
        headline = (f"{len(passages)} documentation passage(s) found for "
                   f"{q!r}: " + "; ".join(p["citation"] for p in passages))
    else:
        headline = (f"no wiki or knowledge-corpus passage matched {q!r} — "
                   f"nothing to cite.")

    result = {
        "tool": "query_model_docs",
        "question": q,
        "k": k,
        "passages": passages,
        "reading_list": reading_list,
        "headline": headline,
    }
    result["tool_call_id"] = _log_call("query_model_docs",
                                       {"question": q, "k": k}, headline)
    return result


# ---------------------------------------------------------------------------
# router-facing argument contract
# ---------------------------------------------------------------------------

class QueryModelDocsArgs(BaseModel):
    """Deliberately EMPTY (extra='forbid'): the router only classifies —
    the retrieval always runs on the user's own original question text
    (agent/graph.py passes ``state["question"]`` verbatim), never a
    router-authored paraphrase. This keeps the router's job identical for
    every route ("classify, don't guess arguments") while guaranteeing the
    text that gets cited back to the user is the text they actually asked."""

    model_config = ConfigDict(extra="forbid")


TIER3_TOOLS = {"query_model_docs": query_model_docs}
TIER3_ARG_MODELS = {"query_model_docs": QueryModelDocsArgs}
