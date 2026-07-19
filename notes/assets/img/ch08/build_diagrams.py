"""Regenerate Ch.8 (The Agent) figures.

Run: uv run --no-sync python notes/assets/img/ch08/build_diagrams.py
Source: agent/graph.py, agent/tools_tier1.py, agent/tools_tier2.py,
agent/tier3_retrieval.py, wiki/pages/agent-layer.md. Uses the shared
textbook matplotlib style (.claude/skills/pageindex-plus/assets/matplotlib_setup.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import apply_textbook_style, figsize_for, COLORS  # noqa: E402

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
# Exhibit 8.1 -- three-tier architecture
# =============================================================================
def fig_three_tier():
    fig, ax = plt.subplots(figsize=(11.4, 7.0))
    ax.set_xlim(0, 12.9)
    ax.set_ylim(0, 8.6)
    ax.axis("off")

    ax.text(6.45, 8.45, "THE GOVERNING RULE: the LLM never computes a number or recalls a fact from memory\n"
                       "(agent/graph.py module docstring) -- every number below comes from a source outside the LLM",
            ha="center", va="top", fontsize=8.2, style="italic", color="#4a4a4a")

    # question -> router, centered above the 5-way split below
    box(ax, (4.2, 7.05), 2.0, 0.8, "user\nquestion", fc="#f7f5ee", ec=COLORS["gray"], fontsize=8.6)
    box(ax, (6.5, 7.05), 3.0, 0.8, "ROUTER (LLM)\nclassifies ONLY -- never guesses args\n(pydantic extra='forbid')",
        fc="#fff7e6", ec=COLORS["orange"], fontsize=7.9)
    arrow(ax, (6.2, 7.45), (6.5, 7.45))

    # one row, five boxes: REASONED | TIER-1 | TIER-2 | TIER-3 | REFUSAL -- no
    # vertical crossings, arrows fan straight down from the router like Ex.8.2
    cols = [
        (0.15, "REASONED", "conceptual Qs no\ntool computes:\nTier-3 passages +\nrerun_ecl(all)\nbaseline, LLM\nreasons + cites",
         "#fdf1e3", COLORS["orange"]),
        (2.35, "TIER-1\n(tools_tier1.py)", "4 validated tools:\nshock_macro,\nreweight_scenarios,\nrerun_ecl,\ndecompose_waterfall\n\nnumbers =\nFROZEN ENGINE",
         "#eaf7f1", COLORS["good"]),
        (4.95, "TIER-2\n(tools_tier2.py)", "analyze_data --\nLLM WRITES pandas\ncode; AST-validated,\nthen EXECUTED in a\nforked, hardened\nsandbox\n\nnumbers =\nEXECUTED code",
         "#f4f2fc", "#6c4fb5"),
        (7.55, "TIER-3\n(tier3_retrieval.py)", "query_model_docs --\ndeterministic\nlexical/graph\nretrieval over wiki/\n+ knowledge/index\n\nclaims =\nCITED PASSAGES",
         "#eef3fb", COLORS["accent"]),
        (10.15, "REFUSAL", "no tool fits;\nfixed message\nnaming the 6 tool\nfamilies -- a\nfeature, not an\nerror",
         "#fdecea", COLORS["warn"]),
    ]
    w = 2.35
    y0, h = 3.9, 3.0
    centers = []
    for x0, title, body, fc, ec in cols:
        box(ax, (x0, y0), w, h, f"{title}\n\n{body}", fc=fc, ec=ec, fontsize=7.5)
        centers.append(x0 + w / 2)

    router_bottom = (7.6, 7.05)
    for cx, (x0, title, body, fc, ec) in zip(centers, cols):
        rad = (cx - router_bottom[0]) * 0.09
        arrow(ax, router_bottom, (cx, y0 + h), connectionstyle=f"arc3,rad={rad:.2f}", color=ec)

    # guard stack, spanning all five
    box(ax, (0.15, 2.05), 12.6, 1.35,
        "GUARD STACK (every LLM-touched answer): spelled-number check -> verbatim-number check\n"
        "-> [Tier-3/REASONED only] citation check -> on ANY miss, deterministic template fallback\n"
        "(the tool's own headline / a passage listing) -- never a silently-passed hallucination",
        fc="#fbfbf5", ec=COLORS["gray"], fontsize=8.4, ls="--")
    for cx in centers:
        arrow(ax, (cx, y0), (cx, 3.4), color="#888888", ls=":")

    # audit trail
    box(ax, (0.15, 0.3), 12.6, 1.35,
        "AUDIT TRAIL: every Tier-1/2/3 call -> outputs/agent_log/tool_calls.jsonl ({seq, ts, tool, args, headline})\n"
        "every full run -> outputs/agent_log/agent_runs.jsonl ({question, route, answer, trace}) -- replayable, no LLM prose trusted unlogged",
        fc="#f0f0f0", ec="#666666", fontsize=8.3)
    arrow(ax, (6.45, 2.05), (6.45, 1.65), color="#666666")

    fig.savefig(OUT / "01_three_tier_architecture.png")
    plt.close(fig)


# =============================================================================
# Exhibit 8.2 -- LangGraph state machine
# =============================================================================
def fig_state_machine():
    fig, ax = plt.subplots(figsize=(13.0, 7.4))
    ax.set_xlim(0, 15.0)
    ax.set_ylim(0, 8.4)
    ax.axis("off")

    ax.text(6.6, 8.25, "build_graph() -- eight node kinds, one loop-free pass (agent/graph.py)",
            ha="center", va="top", fontsize=8.6, style="italic", color="#4a4a4a")

    box(ax, (0.2, 6.95), 1.5, 0.75, "START", fc="#f0f0f0", ec="#555555", fontsize=8.6)
    box(ax, (2.2, 6.95), 2.1, 0.75, "router", fc="#fff7e6", ec=COLORS["orange"], fontsize=8.8)
    arrow(ax, (1.7, 7.3), (2.2, 7.3))

    # tool nodes (Tier-1 x4 + Tier-3) -- one row, y0..y0+0.9, x 0.2..8.72
    tools = ["shock_macro", "reweight_\nscenarios", "rerun_ecl", "decompose_\nwaterfall", "query_model_\ndocs"]
    y0 = 5.35
    tool_centers = []
    for i, t in enumerate(tools):
        x = 0.2 + i * 1.72
        box(ax, (x, y0), 1.55, 0.9, t, fc="#eaf7f1", ec=COLORS["good"], fontsize=7.2)
        tool_centers.append(x + 0.775)
        arrow(ax, (3.05, 6.95), (x + 0.775, y0 + 0.9),
              connectionstyle=f"arc3,rad={(-0.30 + i * 0.13):.2f}", color=COLORS["good"])

    box(ax, (0.2, 3.75), 2.4, 0.9, "analyze_data\n(Tier-2 sandbox)", fc="#f4f2fc", ec="#6c4fb5", fontsize=7.6)
    arrow(ax, (2.9, 6.95), (1.2, 4.65), connectionstyle="arc3,rad=0.22", color="#6c4fb5")

    # REASONED / refusal: a SEPARATE column, clear of the tool row entirely
    box(ax, (10.4, 5.6), 2.6, 1.1, "REASONED", fc="#fdf1e3", ec=COLORS["orange"], fontsize=8.6)
    arrow(ax, (5.3, 7.3), (11.5, 6.7), connectionstyle="arc3,rad=-0.2", color=COLORS["orange"])

    box(ax, (10.4, 3.75), 2.6, 1.1, "refusal", fc="#fdecea", ec=COLORS["warn"], fontsize=8.9)
    arrow(ax, (5.3, 7.0), (11.5, 4.85), connectionstyle="arc3,rad=-0.32", color=COLORS["warn"])

    box(ax, (3.2, 2.0), 2.9, 0.9, "narrator", fc="#eef3fb", ec=COLORS["accent"], fontsize=9.0)
    for cx in tool_centers:
        arrow(ax, (cx, y0), (4.2, 2.9), connectionstyle="arc3,rad=0.04", color="#888888", lw=1.0)
    arrow(ax, (1.4, 3.75), (3.9, 2.9), connectionstyle="arc3,rad=-0.18", color="#6c4fb5")

    # repair-still-fails branch does NOT dangle -- it lands on its own small
    # refusal glyph (same terminal semantics as the router's own refusal
    # node: agent/graph.py docstring "refusal (repair also failed) -> END"),
    # then joins the shared END box below. Label sits clear of both the
    # analyze_data box border and the dashed arrow itself.
    box(ax, (0.2, 1.35), 2.4, 0.7, "refusal\n(repair also failed)", fc="#fdecea", ec=COLORS["warn"], fontsize=6.6)
    arrow(ax, (1.05, 3.75), (1.05, 2.05), connectionstyle="arc3,rad=0.0", color="#6c4fb5", ls="--")
    ax.text(1.35, 2.9, "sandbox error,\n1 repair attempt,\nSTILL fails ->", fontsize=6.4, ha="left", va="center", color="#6c4fb5")
    arrow(ax, (1.7, 1.35), (3.35, 0.85), connectionstyle="arc3,rad=-0.2", color=COLORS["warn"])

    box(ax, (3.2, 0.3), 1.6, 0.75, "END", fc="#f0f0f0", ec="#555555", fontsize=8.6)
    arrow(ax, (4.65, 2.0), (4.1, 1.05))

    # REASONED and refusal each get their OWN small END glyph to the RIGHT --
    # avoids a long crossing arrow sweeping back across the whole diagram, and
    # avoids the two END glyphs colliding with each other's source box
    box(ax, (13.3, 5.85), 1.5, 0.6, "END", fc="#f0f0f0", ec="#555555", fontsize=8.0)
    arrow(ax, (13.0, 6.15), (13.3, 6.15), color=COLORS["orange"])
    box(ax, (13.3, 4.0), 1.5, 0.6, "END", fc="#f0f0f0", ec="#555555", fontsize=8.0)
    arrow(ax, (13.0, 4.3), (13.3, 4.3), color=COLORS["warn"])
    ax.text(12.15, 2.0,
            "REASONED / refusal each\nproduce a final answer\ndirectly (skip narrator) --\nsame terminal state as\nthe main END",
            fontsize=6.9, ha="center", color="#555555", style="italic", linespacing=1.4)

    fig.savefig(OUT / "03_langgraph_state_machine.png")
    plt.close(fig)


# =============================================================================
# Exhibit 8.3 -- Tier-2 sandbox hardening pipeline
# =============================================================================
def fig_sandbox_hardening():
    fig, ax = plt.subplots(figsize=(11.6, 8.6))
    ax.set_xlim(0, 13.2)
    ax.set_ylim(0, 10.0)
    ax.axis("off")

    ax.text(6.6, 9.85, "agent/tools_tier2.py -- \"the LLM may write the CODE, never the number\"",
            ha="center", va="top", fontsize=8.8, style="italic", color="#4a4a4a")

    # --- left column: the hardening pipeline, 4 stacked boxes ---
    box(ax, (0.2, 8.3), 5.4, 0.85, "LLM code-writer writes\npandas CODE (not a number)",
        fc="#f7f5ee", ec=COLORS["gray"], fontsize=8.2)
    arrow(ax, (2.9, 8.3), (2.9, 7.75))

    box(ax, (0.2, 6.35), 5.4, 1.4,
        "1. AST WALK (_validate_ast) -- BEFORE execution\nban dunders, exec/eval/open,\nread_*/to_*(except 5 safe methods),\nnon-literal .eval()/.query(), FORBIDDEN_ATTRS\n(os, system, environ, ...) AT EVERY DEPTH of a chain",
        fc="#fdecea", ec=COLORS["warn"], fontsize=7.6)
    ax.text(0.1, 5.6, "REJECTED CODE never executes:\n{ok: false, error: \"...\"}",
            ha="left", fontsize=7.2, color=COLORS["warn"], style="italic")
    arrow(ax, (2.9, 6.35), (2.9, 5.35))

    box(ax, (0.2, 3.95), 5.4, 1.15,
        "2. FORK ISOLATION -- multiprocessing fork\n(copy-on-write); child ONLY: exec(code, restricted)\nwith SAFE_BUILTINS + book/scenarios/z_path COPIES",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=7.6)
    arrow(ax, (2.9, 3.95), (2.9, 2.95))

    box(ax, (0.2, 1.6), 5.4, 1.1,
        "3. CHILD HARDENING (_harden_child)\nBEFORE user code runs: RLIMIT_AS cap,\nos.environ.clear() (no secrets), audit hook blocks\nwrite/exec/network/native-code events",
        fc="#f4f2fc", ec="#6c4fb5", fontsize=7.5)
    arrow(ax, (2.9, 1.6), (2.9, 0.95))

    box(ax, (0.2, 0.15), 5.4, 0.65,
        "4. TIMEOUT + RESULT CAPS\n5.0s wall clock; 50 rows / 5000 chars",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=7.6)

    # --- right column: the RCE catch story, three small stacked boxes ---
    ax.text(9.9, 9.55, "THE RCE CATCH -- adversarial review, App v2 gate\n(wiki/memory/log.md; tests/test_tier2.py)",
            ha="center", va="top", fontsize=8.2, color=COLORS["warn"], weight="bold", linespacing=1.4)

    box(ax, (6.5, 7.55), 6.5, 1.55,
        "THE BUG\npd.io.common.os.system('id') chains through\nFOUR attribute hops; the filter checked only\npd's DIRECT attribute, so the buried .os / .system\nhops inside the chain slipped past unchecked",
        fc="#fff5f0", ec=COLORS["warn"], fontsize=7.6, lw=1.5)
    arrow(ax, (9.75, 7.55), (9.75, 6.9), color=COLORS["warn"])

    box(ax, (6.5, 5.4), 6.5, 1.35,
        "THE FIX\nwalk EVERY ast.Attribute node in a chain,\nat ANY depth -- FORBIDDEN_ATTRS now matches\n'os', 'system', 'environ', ... wherever they\nappear, not just as pd's/np's direct attribute",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=7.6, lw=1.5)
    arrow(ax, (9.75, 5.4), (9.75, 4.75))

    box(ax, (6.5, 2.9), 6.5, 1.7,
        "LIVE, THIS CHAPTER (run_sandboxed):\n\n"
        "run_sandboxed(\"result = pd.io.common.os.system('id')\")\n\n"
        "-> ok=False, error=\"attribute access '.system' is\nnot allowed in sandboxed code (frame/module/\nOS-escape surface)\"",
        fc="#f4f2fc", ec="#6c4fb5", fontsize=7.4, lw=1.5)

    fig.savefig(OUT / "02_sandbox_hardening_pipeline.png")
    plt.close(fig)


# =============================================================================
# Exhibit 8.4 -- guard-pipeline stepper (the number-guard order of operations)
# =============================================================================
def fig_guard_pipeline():
    fig, ax = plt.subplots(figsize=(13.2, 5.1))
    ax.set_xlim(0, 14.6)
    ax.set_ylim(2.3, 9.6)
    ax.axis("off")

    ax.text(7.3, 9.45, "Every LLM narration passes through this pipeline before it is ever shown (agent/graph.py)",
            ha="center", va="top", fontsize=8.6, style="italic", color="#4a4a4a")

    # --- row 1: the linear guard chain, left to right ---
    y1, h1 = 7.55, 1.35
    box(ax, (0.2, y1 + 0.2), 2.3, 0.95, "LLM narration\n(free text)", fc="#f7f5ee", ec=COLORS["gray"], fontsize=8.0)
    box(ax, (2.85, y1), 2.85, h1,
        "1. SPELLED-NUMBER\nCHECK\n_spelled_number_violation()\nmagnitude word OR small word\nwithin 4 tokens of a unit word",
        fc="#fdf1e3", ec=COLORS["orange"], fontsize=7.1)
    box(ax, (6.05, y1), 2.85, h1,
        "2. VERBATIM-NUMBER\nCHECK\n_number_tokens() -- every\ndigit token must equal (or\nplainly round) a JSON number",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=7.1)
    box(ax, (9.25, y1), 2.6, h1,
        "3. CITATION CHECK\n(Tier-3 / REASONED only)\na passage citation string\nappears verbatim in the answer",
        fc="#f4f2fc", ec="#6c4fb5", fontsize=7.1)
    box(ax, (12.2, y1 + 0.15), 2.2, 1.05, "ALL PASS ->\nshown verbatim\nas the answer",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=7.6)

    arrow(ax, (2.5, y1 + 0.67), (2.85, y1 + 0.67))
    arrow(ax, (5.7, y1 + 0.67), (6.05, y1 + 0.67))
    arrow(ax, (8.9, y1 + 0.67), (9.25, y1 + 0.67))
    arrow(ax, (11.85, y1 + 0.67), (12.2, y1 + 0.67), color=COLORS["good"])

    # --- row 2: the shared fallback, fed by a miss at any of the 3 guards ---
    y2 = 5.55
    for cx in (4.275, 7.475, 10.55):
        arrow(ax, (cx, y1), (cx, y2 + 1.15), color=COLORS["warn"], ls=":")
    box(ax, (2.85, y2), 8.0, 1.15,
        "ANY MISS at step 1, 2, or 3 -> DETERMINISTIC FALLBACK\n"
        "(the tool's own engine-authored headline, or a plain passage listing) -- never a silently-shown guess",
        fc="#fdecea", ec=COLORS["warn"], fontsize=7.9)

    # --- row 3: two supplementary panels, side by side, no overlap ---
    arrow(ax, (5.0, y2), (2.6, 4.4), connectionstyle="arc3,rad=0.2", color=COLORS["warn"], ls=":")
    box(ax, (0.2, 2.55), 6.6, 1.85,
        "LIVE-CONFIRMED BYPASS (fixed 2026-07-17)\n\n"
        "the ROUTER LLM verbalised its own subtraction\nas \"tens of millions\" -- zero digit tokens, so step 2\n"
        "(verbatim-number) alone let it through. Step 1\n(_spelled_number_violation) was added to close the\n"
        "hole, wired into ALL THREE narration guards.",
        fc="#fff5f0", ec=COLORS["warn"], fontsize=7.6, lw=1.5)

    box(ax, (7.2, 2.55), 7.2, 1.85,
        "LIVE, THIS CHAPTER (agent.graph.narration_numbers_ok):\n\n"
        "good: \"...to $31.7m, a +4.1% increase...\"          -> PASS\n"
        "bad:  \"...rise to $32.0m under the shock.\"          -> FAIL (32.0 not in JSON)\n"
        "bad:  \"...roughly two hundred million dollars.\"      -> FAIL (spelled-number)\n"
        "bad:  \"...that is a forty-seven percent jump\"        -> FAIL (spelled-number)",
        fc="#fbfbf5", ec=COLORS["gray"], fontsize=7.4, ls="--")

    fig.savefig(OUT / "04_guard_pipeline.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_three_tier()
    fig_state_machine()
    fig_sandbox_hardening()
    fig_guard_pipeline()
    print("wrote:", sorted(p.name for p in OUT.glob("*.png")))
