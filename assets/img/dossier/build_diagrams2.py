"""Three NEW exhibits for cv_dossier.html v2 (dossier_v2_plan.md VISUALS):
request-lifecycle sequence diagram, RAG/PageIndex retrieval pipeline, and
the honest CI/CD flowchart. Reuses the shared textbook matplotlib style and
the box()/arrow() helpers from notes/assets/img/ch08/build_diagrams.py.

Run:
    cd /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI
    uv run python notes/assets/img/dossier/build_diagrams2.py

Every label is sourced from code/docs read directly, never invented:
  - request lifecycle: agent/graph.py build_graph()/run_agent(), app/api/main.py
    POST /api/agent/ask + GET /api/agent/stream (module docstring).
  - RAG pipeline: agent/tier3_retrieval.py module docstring (wiki_query.py
    tokens/score_pages/expand; pageindex_query.py search_tree/get_context);
    wiki/.wiki/audit.json (21 pages/106 edges); knowledge/index/pageindex.json
    (23 pages/69 nodes, counted directly).
  - CI/CD: Dockerfile (2-stage build), DATA_SETUP.md, .github/workflows/pages.yml,
    wiki/memory/log.md 2026-07-20 entry (Actions billing-locked -> gh-pages
    branch + explicit POST /pages/builds trigger), notes/assets/check_notes.py
    + verify_math.py (the local pre-push gate).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import apply_textbook_style, COLORS  # noqa: E402

apply_textbook_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402

OUT = Path(__file__).resolve().parent


def box(ax, xy, w, h, text, fc="white", ec=COLORS["accent"], fontsize=8.6,
        textcolor="#1a1a1a", lw=1.3, zorder=3, ls="-"):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=zorder, linestyle=ls)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fontsize, color=textcolor, zorder=zorder + 1, linespacing=1.35)
    return p


def arrow(ax, p0, p1, color="#555555", lw=1.4, style="-|>",
          connectionstyle="arc3,rad=0.0", ls="-"):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                         color=color, lw=lw, linestyle=ls, zorder=2,
                         connectionstyle=connectionstyle, shrinkA=2, shrinkB=2)
    ax.add_patch(a)


# =============================================================================
# Exhibit D.request-lifecycle -- one question, start to finish
# =============================================================================
def fig_request_lifecycle():
    fig, ax = plt.subplots(figsize=(11.8, 10.4))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 19.6)
    ax.axis("off")

    ax.text(6.2, 19.45, "Request lifecycle: one question, end to end (agent/graph.py + app/api/main.py)",
            ha="center", va="top", fontsize=9.2, style="italic", color="#4a4a4a")

    # lifelines (5 actors)
    actors = [
        (0.9, "Browser\n(Copilot tab)"),
        (3.3, "FastAPI\nPOST /api/agent/ask"),
        (5.7, "LangGraph\nrouter node"),
        (8.1, "Tool/Tier node\n(1 of 6) or REASONED"),
        (10.6, "narrator +\nguard stack"),
    ]
    bot_y = 0.9
    top_box_y = 18.35
    for x, label in actors:
        box(ax, (x - 0.95, top_box_y), 1.9, 0.75, label, fc="#f0f0f0", ec="#555555", fontsize=7.6)
        ax.plot([x, x], [bot_y, top_box_y], color="#bbbbbb", lw=1.0, ls=":", zorder=1)

    x_browser, x_api, x_router, x_tool, x_narr = [a[0] for a in actors]

    # (y_center, xa, xb, label, box_height_if_selfloop)
    steps = [
        (16.9, x_browser, x_api, "1. question text (POST /api/agent/ask)", None),
        (16.0, x_api, x_router, "2. get_graph().invoke(state) -- START -> router", None),
        (14.75, x_router, x_router,
         "3. decide_route(question): 1 LLM call, temp=0\n(Gemma-4-31B, fallback DeepSeek-V4-Flash)", 0.95),
        (13.35, x_router, x_tool,
         "4. pydantic-validated route + args\n(parse/validation failure -> refusal, not a guess)", None),
        (11.85, x_tool, x_tool,
         "5a. Tier-1: frozen engine call  |  5b. Tier-2: LLM writes pandas,\n"
         "sandbox EXECUTES it  |  5c. Tier-3: deterministic retrieval\n"
         "(no LLM)  |  5d. REASONED: retrieval + rerun_ecl baseline", 1.25),
        (10.15, x_tool, x_narr, "6. tool_result JSON (numbers/passages)", None),
        (9.05, x_narr, x_narr, "7. LLM narrates OVER the JSON only", 0.7),
        (7.55, x_narr, x_narr,
         "8. guard check: spelled-number + verbatim-number\n[+ citation, Tier-3/REASONED] -- ANY miss -> deterministic\n"
         "fallback (tool's own headline / passage listing)", 1.15),
        (6.0, x_narr, x_api, "9. {answer, mode, trace}", None),
        (4.65, x_api, x_api,
         "10. append trace -> outputs/agent_log/agent_runs.jsonl\n(+ tool_calls.jsonl per validated call)", 0.95),
        (3.15, x_api, x_browser,
         "11. JSON response (or SSE via GET /api/agent/stream:\nlive {node:...} trace events as they land)", None),
    ]
    for y, xa, xb, label, loop_h in steps:
        if xa == xb:
            box(ax, (xa - 2.15, y - loop_h / 2), 4.3, loop_h, label, fc="#fbfbf5",
                ec=COLORS["gray"], fontsize=6.9, ls="--")
        else:
            arrow(ax, (xa, y), (xb, y), color=COLORS["accent"] if xb > xa else COLORS["good"])
            mid = (xa + xb) / 2
            ax.text(mid, y + 0.16, label, ha="center", va="bottom", fontsize=6.9, color="#333333")

    ax.text(6.2, 1.15,
            "Source: agent/graph.py build_graph()/run_agent() module docstring; app/api/main.py §13-14 (endpoint docstring).",
            ha="center", va="bottom", fontsize=7.2, color="#777777", style="italic")

    fig.savefig(OUT / "02_request_lifecycle.png")
    plt.close(fig)
    print("wrote", OUT / "02_request_lifecycle.png")


# =============================================================================
# Exhibit D.rag -- vectorless PageIndex + wiki retrieval pipeline (Tier-3)
# =============================================================================
def fig_rag_pipeline():
    fig, ax = plt.subplots(figsize=(11.6, 7.6))
    ax.set_xlim(0, 12.6)
    ax.set_ylim(-0.35, 8.6)
    ax.axis("off")

    ax.text(6.3, 8.45,
            "Tier-3 retrieval: two deterministic, vectorless passes -- NO LLM anywhere below this line (agent/tier3_retrieval.py)",
            ha="center", va="top", fontsize=8.8, style="italic", color="#4a4a4a")

    box(ax, (4.9, 7.35), 2.8, 0.7, "user question\n(verbatim, never a router paraphrase)",
        fc="#f7f5ee", ec=COLORS["gray"], fontsize=8.0)

    # left branch: wiki
    box(ax, (0.3, 5.9), 5.6, 0.85,
        "wiki_query.tokens(question) -> score_pages(graph, wiki/, tokens)\n(typed link graph, lexical seed scoring)",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=7.6)
    box(ax, (0.3, 4.7), 5.6, 0.85,
        "wiki_query.expand(graph, seeds, hops=1)\n1-hop graph expansion over 21 pages / 106 edges (wiki/.wiki/audit.json)",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=7.6)
    box(ax, (0.3, 3.5), 5.6, 0.85,
        "wiki passages, cited “<page path>#<heading>”\n(heading text read verbatim off the page's own parsed heading list)",
        fc="#dfeaf9", ec=COLORS["accent"], fontsize=7.4)

    # right branch: pageindex
    box(ax, (6.7, 5.9), 5.6, 0.85,
        "pageindex_query.search_tree(question, tree, top=k)\noffline keyword scoring over the parsed section tree",
        fc="#f4f2fc", ec="#6c4fb5", fontsize=7.6)
    box(ax, (6.7, 4.7), 5.6, 0.85,
        "pageindex_query.get_context(node_ids, tree, pages)\n23-page / 69-node IFRS9 knowledge-corpus tree (knowledge/index/pageindex.json)",
        fc="#f4f2fc", ec="#6c4fb5", fontsize=7.6)
    box(ax, (6.7, 3.5), 5.6, 0.85,
        "notes passages, cited “notes §<section> p<start>-<end>”\n(section number + page range read straight off the loaded tree)",
        fc="#e9e2f9", ec="#6c4fb5", fontsize=7.4)

    arrow(ax, (5.5, 7.35), (3.1, 6.75))
    arrow(ax, (6.9, 7.35), (9.5, 6.75))
    arrow(ax, (3.1, 5.9), (3.1, 5.55))
    arrow(ax, (9.5, 5.9), (9.5, 5.55))
    arrow(ax, (3.1, 4.7), (3.1, 4.35))
    arrow(ax, (9.5, 4.7), (9.5, 4.35))

    box(ax, (2.6, 2.15), 7.4, 0.85,
        "query_model_docs(question) -> {question, passages, tool_call_id}\n"
        "MERGES both passage lists -- same question + files => identical passages every time",
        fc="#fff7e6", ec=COLORS["orange"], fontsize=7.3)
    arrow(ax, (3.1, 3.5), (4.6, 3.04), connectionstyle="arc3,rad=-0.15")
    arrow(ax, (9.5, 3.5), (8.0, 3.04), connectionstyle="arc3,rad=0.15")

    box(ax, (2.6, 1.0), 7.4, 0.85,
        "narrator: LLM cites + quotes ONLY from passages\n"
        "guard: >=1 citation string verbatim in the answer AND every number traces to a passage",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=7.2)
    arrow(ax, (6.3, 2.15), (6.3, 1.85))

    box(ax, (2.6, 0.0), 7.4, 0.75,
        "on ANY guard miss: deterministic_docs_narration()\na plain citation-listed passage dump, never a silent guess",
        fc="#fdecea", ec=COLORS["warn"], fontsize=7.2, ls="--")
    arrow(ax, (6.3, 1.0), (6.3, 0.75), color=COLORS["warn"], ls=":")

    fig.savefig(OUT / "03_rag_pipeline.png")
    plt.close(fig)
    print("wrote", OUT / "03_rag_pipeline.png")


# =============================================================================
# Exhibit D.cicd -- the honest CI/CD flowchart (no Actions overclaim)
# =============================================================================
def fig_cicd():
    fig, ax = plt.subplots(figsize=(11.6, 8.0))
    ax.set_xlim(0, 12.6)
    ax.set_ylim(0, 11.4)
    ax.axis("off")

    ax.text(6.3, 11.25,
            "Deploy pipeline as actually practiced -- GitHub Actions is billing-locked on this account (wiki/memory/log.md, 2026-07-20)",
            ha="center", va="top", fontsize=8.6, style="italic", color="#4a4a4a")

    box(ax, (4.3, 10.15), 4.0, 0.75, "local commit", fc="#f0f0f0", ec="#555555", fontsize=8.6)

    box(ax, (2.9, 8.85), 6.8, 1.05,
        "PRE-PUSH LOCAL GATE (manual, not an Actions job):\n"
        "uv run pytest tests/ -q  (665 collected)   +   check_notes.py (7 checks/file)   +   verify_math.py (real MathJax render)",
        fc="#fbfbf5", ec=COLORS["gray"], fontsize=7.6, ls="--")
    arrow(ax, (6.3, 10.15), (6.3, 9.9))

    box(ax, (4.3, 7.7), 4.0, 0.7, "git push origin main", fc="#f0f0f0", ec="#555555", fontsize=8.4)
    arrow(ax, (6.3, 8.85), (6.3, 8.4))

    # branch to two deploy targets
    arrow(ax, (5.4, 7.7), (2.6, 6.85), connectionstyle="arc3,rad=-0.2")
    arrow(ax, (7.2, 7.7), (9.9, 6.85), connectionstyle="arc3,rad=0.2")

    # left: HF Space
    box(ax, (0.2, 5.9), 4.8, 0.85, "push to HF Space git remote\n(Docker SDK repo, separate from GitHub)",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=7.6)
    box(ax, (0.2, 4.65), 4.8, 0.95,
        "HF-side Docker BUILD (not GitHub Actions):\nstage 1 node:22-alpine npm run build (SPA)\nstage 2 python:3.13-slim + requirements.docker.txt",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=7.3)
    box(ax, (0.2, 3.5), 4.8, 0.85,
        "RUNNING_BUILDING -> RUNNING_APP_STARTING -> RUNNING\n(recorded stall/failure cases: ch10 Exhibit 10.2)",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=6.8)
    box(ax, (0.2, 2.35), 4.8, 0.85, "live app: huggingface.co/spaces/\nPreetomsorkar/ifrs9-ecl-copilot",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=7.6)
    for y0, y1 in [(5.9, 5.6), (4.65, 4.35), (3.5, 3.2)]:
        arrow(ax, (2.6, y0), (2.6, y1))

    # right: GitHub Pages
    box(ax, (7.6, 5.9), 4.8, 0.85, "assemble _site/ (notes/* + outputs/mdd/*)\nvia .github/workflows/pages.yml steps",
        fc="#fdf1e3", ec=COLORS["orange"], fontsize=7.4)
    box(ax, (7.6, 4.65), 4.8, 0.95,
        "committed pages.yml would auto-fire on push\nto main -- Actions is BILLING-LOCKED here,\nso it does NOT run automatically",
        fc="#fdecea", ec=COLORS["warn"], fontsize=7.0, ls="--")
    box(ax, (7.6, 3.5), 4.8, 0.85,
        "REAL mechanism: content pushed to the gh-pages branch\n"
        "+ an EXPLICIT POST /pages/builds trigger\n(the source-flip alone never queues a build)",
        fc="#fdf1e3", ec=COLORS["orange"], fontsize=6.8)
    box(ax, (7.6, 2.35), 4.8, 0.85, "live site: metaphorpritam.github.io/\nIFRS9_ECL_Agentic_AI/",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=7.6)
    for y0, y1 in [(5.9, 5.6), (4.65, 4.35), (3.5, 3.2)]:
        arrow(ax, (10.0, y0), (10.0, y1), color=COLORS["orange"])

    ax.text(6.3, 1.6,
            "Both paths are gated by the SAME local pre-push checks -- there is no separate\n"
            "server-side CI test run; a red local gate is the only thing that blocks either deploy.",
            ha="center", va="top", fontsize=7.6, color="#4a4a4a")

    fig.savefig(OUT / "04_cicd_flowchart.png")
    plt.close(fig)
    print("wrote", OUT / "04_cicd_flowchart.png")


if __name__ == "__main__":
    fig_request_lifecycle()
    fig_rag_pipeline()
    fig_cicd()
