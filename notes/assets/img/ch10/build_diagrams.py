"""Regenerate Ch.10 (Docker & Deployment) figures.

Run: uv run --no-sync python notes/assets/img/ch10/build_diagrams.py
Source: Dockerfile, .dockerignore, requirements.docker.txt, outputs/gate/
{day4,appv2,stretch,uiv3,mdd_freddie}_gate_report.md, wiki/memory/log.md.
Uses the shared textbook matplotlib style
(.claude/skills/pageindex-plus/assets/matplotlib_setup.py). All three
exhibits are conceptual box-arrow / box-area diagrams -- no underlying data
table to plot from a fixture, per notes/plan/chapters.md's Ch.10 scope
(infra chapter, no derivations).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import apply_textbook_style, COLORS  # noqa: E402

apply_textbook_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle  # noqa: E402

OUT = Path(__file__).resolve().parent


def box(ax, xy, w, h, text, fc="white", ec=COLORS["accent"], fontsize=8.4,
        textcolor="#1a1a1a", lw=1.3, zorder=3, ls="-"):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=zorder, linestyle=ls)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fontsize, color=textcolor, zorder=zorder + 1, linespacing=1.32)
    return p


def arrow(ax, p0, p1, color="#555555", lw=1.4, style="-|>",
          connectionstyle="arc3,rad=0.0", ls="-"):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                         color=color, lw=lw, linestyle=ls, zorder=2,
                         connectionstyle=connectionstyle, shrinkA=2, shrinkB=2)
    ax.add_patch(a)


# =============================================================================
# Exhibit 10.1 -- multi-stage build flowchart
# =============================================================================
def fig_multistage_build():
    fig, ax = plt.subplots(figsize=(11.0, 7.4))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 9.4)
    ax.axis("off")

    ax.text(6.2, 9.25, "Dockerfile -- two build stages, one runtime image (multi-stage build)",
            ha="center", va="top", fontsize=9.2, style="italic", color="#4a4a4a")

    # ---- Stage 1: UI -------------------------------------------------
    box(ax, (0.3, 7.55), 5.6, 0.75, "STAGE 1  --  FROM node:22-alpine AS ui",
        fc="#eaf3ff", ec=COLORS["accent"], fontsize=8.8)
    box(ax, (0.55, 6.35), 2.5, 0.95, "COPY package.json\npackage-lock.json\nRUN npm ci", fc="white", fontsize=7.7)
    box(ax, (3.35, 6.35), 2.3, 0.95, "COPY index.html\nvite.config.js src/\nscripts/", fc="white", fontsize=7.7)
    arrow(ax, (3.05, 6.82), (3.35, 6.82))
    box(ax, (1.3, 5.05), 3.3, 0.85, "RUN npm run build\n(prebuild -> verify:waterfall\n10/10 regression guard)",
        fc="#fff7e6", ec=COLORS["orange"], fontsize=7.7)
    arrow(ax, (2.9, 6.35), (2.9, 5.9))
    box(ax, (1.55, 3.8), 2.8, 0.75, "artifact: /build/dist\n(SPA bundle)", fc="#ecf7ee", ec=COLORS["good"], fontsize=8.0)
    arrow(ax, (2.9, 5.05), (2.9, 4.55))

    # ---- Stage 2: runtime ---------------------------------------------
    box(ax, (6.4, 7.55), 5.7, 0.75, "STAGE 2  --  FROM python:3.13-slim AS runtime", fc="#eaf3ff",
        ec=COLORS["accent"], fontsize=8.8)
    box(ax, (6.65, 6.35), 5.2, 0.95,
        "COPY requirements.docker.txt\nRUN pip install -r ...\n(73 locked pkgs, torch pruned)", fc="white", fontsize=7.7)
    arrow(ax, (9.25, 7.55), (9.25, 7.3))
    box(ax, (6.65, 5.25), 5.2, 0.75, "RUN useradd -m -u 1000 appuser\n(HF Spaces non-root convention)",
        fc="white", fontsize=7.7)
    arrow(ax, (9.25, 6.35), (9.25, 6.0))
    box(ax, (6.65, 3.55), 5.2, 1.45,
        "COPY <allowlist> (explicit, one line per dir)\nengine/ agent/ app/api analysis/\nwiki/ knowledge/{corpus,index}\n.claude/skills/{llm-wiki,pageindex-plus}/scripts\ndata/{ingest,processed/panel.parquet,scenarios}\noutputs/{models, hazard, lgd, staging, eda,\n  vasicek, scenario_ecl, challenger, freddie, mdd}",
        fc="#f4f2fc", ec=COLORS["purple"], fontsize=7.1)
    arrow(ax, (9.25, 5.25), (9.25, 5.0))
    box(ax, (6.65, 2.6), 5.2, 0.7, "COPY --from=ui /build/dist\n-> ./app/ui/dist", fc="#ecf7ee",
        ec=COLORS["good"], fontsize=7.9)
    arrow(ax, (9.25, 3.55), (9.25, 3.3))
    # cross-stage arrow from stage-1 artifact into this COPY --from=ui box
    arrow(ax, (4.35, 4.17), (6.65, 2.95), color=COLORS["good"], connectionstyle="arc3,rad=-0.12")

    box(ax, (6.65, 1.55), 5.2, 0.8, "RUN mkdir outputs/agent_log\n&& chown -R appuser:appuser outputs\nUSER appuser", fc="white", fontsize=7.7)
    arrow(ax, (9.25, 2.6), (9.25, 2.35))
    box(ax, (6.65, 0.35), 5.2, 0.95, "EXPOSE 7860\nCMD uvicorn app.api.main:app\n--host 0.0.0.0 --port 7860 --workers 1",
        fc="#fdecea", ec=COLORS["warn"], fontsize=7.9)
    arrow(ax, (9.25, 1.55), (9.25, 1.3))

    ax.text(6.2, -0.15,
            "Stage 1's node toolchain, npm cache, and node_modules never enter the runtime image -- only /build/dist crosses the stage boundary.",
            ha="center", va="top", fontsize=7.6, color="#555555")

    fig.tight_layout()
    fig.savefig(OUT / "01_multistage_build.png")
    plt.close(fig)
    print("wrote", OUT / "01_multistage_build.png")


# =============================================================================
# Exhibit 10.2 -- deploy pipeline state machine
# =============================================================================
def fig_deploy_state_machine():
    fig, ax = plt.subplots(figsize=(11.2, 7.6))
    ax.set_xlim(0, 12.6)
    ax.set_ylim(0, 9.6)
    ax.axis("off")

    ax.text(6.3, 9.45, "The HF Space deploy pipeline as practiced -- runtime.stage values recorded across five ship sessions",
            ha="center", va="top", fontsize=8.8, style="italic", color="#4a4a4a")

    box(ax, (0.3, 8.0), 3.2, 0.85, "git push / upload_file\n(commit to Space repo)", fc="#eaf3ff",
        ec=COLORS["accent"], fontsize=8.0)
    box(ax, (4.9, 8.0), 3.2, 0.85, "CONFIG_ERROR\n(bad README frontmatter --\nsdk/app_port clobbered)", fc="#fdecea",
        ec=COLORS["warn"], fontsize=7.6)
    arrow(ax, (3.5, 8.42), (4.9, 8.42), color=COLORS["warn"], ls="--")

    box(ax, (0.9, 6.3), 4.0, 0.95, "RUNNING_BUILDING\n(queue -> docker build; log\nmay pin at \"Queued\")", fc="#fff7e6",
        ec=COLORS["orange"], fontsize=8.0)
    arrow(ax, (1.9, 8.0), (2.6, 7.25))

    box(ax, (0.9, 4.75), 4.0, 0.85, "BUILD-time failure\n(\"failed to calculate\nchecksum ... not found\")", fc="#fdecea",
        ec=COLORS["warn"], fontsize=7.5)
    arrow(ax, (2.9, 6.3), (2.9, 5.6), color=COLORS["warn"], ls="--")

    box(ax, (5.9, 6.3), 4.0, 0.95, "RUNNING_APP_STARTING\n(hardware allocation,\ncontainer boot)", fc="#fff7e6",
        ec=COLORS["orange"], fontsize=7.6)
    arrow(ax, (4.9, 6.75), (5.9, 6.75))

    box(ax, (5.9, 4.75), 4.0, 0.85, "RUNTIME_ERROR\n(e.g. .gitattributes clobber ->\nLFS pointer not smudged)", fc="#fdecea",
        ec=COLORS["warn"], fontsize=7.5)
    arrow(ax, (7.9, 6.3), (7.9, 5.6), color=COLORS["warn"], ls="--")

    box(ax, (9.35, 6.3), 3.0, 0.95, "RUNNING\n/api/health 200\nengine_warm: true", fc="#ecf7ee",
        ec=COLORS["good"], fontsize=8.4)
    arrow(ax, (9.9, 6.75), (9.35, 6.75))

    # stall loop from RUNNING_BUILDING back to itself via two remedies
    box(ax, (0.5, 2.65), 3.9, 1.5,
        "factory_reboot=True\nfixes: RUNNING_APP_STARTING\nhardware:null hang (~25min)\ndoes NOT clear a genuine\nqueue backlog", fc="#f4f2fc",
        ec=COLORS["purple"], fontsize=7.5)
    box(ax, (5.2, 2.65), 3.9, 1.5,
        "bump-commit\n(new content-changed push,\nback of the queue)\nfixed the recorded\n7.5h RUNNING_BUILDING stall", fc="#f4f2fc",
        ec=COLORS["purple"], fontsize=7.5)
    arrow(ax, (2.5, 6.3), (2.45, 4.15), connectionstyle="arc3,rad=0.25", color=COLORS["purple"])
    arrow(ax, (2.45, 2.65), (2.5, 6.28), connectionstyle="arc3,rad=0.4", color=COLORS["purple"], ls="--")
    arrow(ax, (7.15, 6.3), (7.15, 4.15), connectionstyle="arc3,rad=-0.25", color=COLORS["purple"])
    arrow(ax, (7.15, 2.65), (7.15, 6.28), connectionstyle="arc3,rad=-0.4", color=COLORS["purple"], ls="--")

    box(ax, (9.35, 4.15), 3.0, 1.1, "domains.stage stays READY\nthroughout a stall --\nold build keeps serving 200,\nzero visitor downtime", fc="#eaf3ff",
        ec=COLORS["accent"], fontsize=7.4)

    ax.text(6.3, 1.9,
            "Recorded cases: stretch gate RUNNING_APP_STARTING hang ~25min -> factory_reboot cleared it. UI v3 gate RUNNING_BUILDING\n"
            "stuck ~2h, factory_reboot did NOT clear it (different failure class) -- resolved only after ~7.5h total by a bump-commit.",
            ha="center", va="top", fontsize=7.6, color="#555555")
    ax.text(6.3, 1.15,
            "Sources: outputs/gate/{stretch,uiv3,appv2,mdd_freddie,macro_interp}_gate_report.md, wiki/memory/log.md.",
            ha="center", va="top", fontsize=7.0, color="#7f8c8d")

    fig.tight_layout()
    fig.savefig(OUT / "02_deploy_state_machine.png")
    plt.close(fig)
    print("wrote", OUT / "02_deploy_state_machine.png")


# =============================================================================
# Exhibit 10.3 -- image contents inventory (treemap-style box diagram)
# =============================================================================
def fig_image_layers():
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 5.9), gridspec_kw={"width_ratios": [1.35, 1]})
    fig.suptitle("What is (and is not) in the runtime image", fontsize=9.6, style="italic",
                 color="#4a4a4a", y=0.985)

    # ---- left: IN the image, area roughly proportional to weight -------
    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("SHIPPED in the image", fontsize=9.2, color=COLORS["good"], pad=8)

    def rect(ax, xy, w, h, text, fc, ec, fontsize=7.6):
        x, y = xy
        ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec, linewidth=1.2, zorder=2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize,
                 color="#1a1a1a", zorder=3, linespacing=1.25)

    # python:3.13-slim base + 73 pinned deps -- the dominant slice
    rect(ax, (0.1, 5.6), 9.8, 4.3, "python:3.13-slim base +\n73 pinned deps\n(requirements.docker.txt,\npandas/numpy/scipy/statsmodels/\nfastapi/langgraph/openai SDK...)\nthe large majority of image weight",
         "#eaf3ff", COLORS["accent"], fontsize=7.9)
    # runtime code
    rect(ax, (0.1, 4.55), 3.15, 0.9, "engine/ agent/\napp/api analysis/", "#f4f2fc", COLORS["purple"])
    # wiki + knowledge (Tier-3)
    rect(ax, (3.4, 4.55), 3.15, 0.9, "wiki/ +\nknowledge/{corpus,index}\n(Tier-3 retrieval)", "#f4f2fc", COLORS["purple"], fontsize=7.2)
    # 2 skill scripts
    rect(ax, (6.7, 4.55), 3.2, 0.9, "2 skill scripts\n(wiki_query/wiki_graph,\npageindex_query)", "#f4f2fc", COLORS["purple"], fontsize=7.2)
    # data
    rect(ax, (0.1, 3.35), 4.7, 1.05, "data/ingest + panel.parquet +\nscenarios/*.csv\n(no data/raw, no other data/processed/*)", "#fff7e6", COLORS["orange"], fontsize=7.4)
    # model cache
    rect(ax, (5.0, 3.35), 4.9, 1.05, "outputs/models/tier1_models.joblib\n88.7 MB (stripped joblib cache,\nwarm start ~9-25s)", "#fff7e6", COLORS["orange"], fontsize=7.4)
    # outputs exhibit dirs
    rect(ax, (0.1, 2.15), 9.8, 1.05,
         "outputs/{variable_dictionary.md, hazard, lgd, staging, eda, vasicek,\nscenario_ecl, challenger, freddie, mdd}  --  markdown reports + PNGs, read-only",
         "#fff7e6", COLORS["orange"], fontsize=7.4)
    # built SPA
    rect(ax, (0.1, 0.95), 9.8, 1.05, "app/ui/dist (built SPA: index.js ~102 KB,\necharts vendor chunk ~515 KB, index CSS ~28 KB)",
         "#ecf7ee", COLORS["good"], fontsize=7.6)

    # ---- right: OUT of the image ---------------------------------------
    ax2 = axes[1]
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 10)
    ax2.axis("off")
    ax2.set_title("EXCLUDED (.dockerignore)", fontsize=9.2, color=COLORS["warn"], pad=8)

    rect(ax2, (0.1, 7.1), 9.8, 2.6, "torch\n(--prune torch from uv export)\nchallenger/-only, ~5 GB CUDA payload,\nno runtime module imports it", "#fdecea", COLORS["warn"], fontsize=8.2)
    rect(ax2, (0.1, 5.6), 9.8, 1.3, "data/raw, data/processed/* (except\npanel.parquet), data/panel, init_docs",
         "#fdecea", COLORS["warn"], fontsize=7.6)
    rect(ax2, (0.1, 4.3), 9.8, 1.1, "tests/ scripts/ docs/ challenger/\nMASTER_PLAN.md uv.lock pyproject.toml",
         "#fdecea", COLORS["warn"], fontsize=7.4)
    rect(ax2, (0.1, 3.0), 9.8, 1.1, "knowledge/{sources,code_map.md,\ncode_fp.json,captions.json}",
         "#fdecea", COLORS["warn"], fontsize=7.4)
    rect(ax2, (0.1, 1.85), 9.8, 0.95, "app/ui/node_modules, app/ui/dist\n(the SOURCE dist, before stage-2 recopies it)",
         "#fdecea", COLORS["warn"], fontsize=7.2)
    rect(ax2, (0.1, 0.5), 9.8, 1.15, ".env .env.* *.key *credentials*\n*.pem  --  never in the build context,\nCI greps saved image layers for key prefixes",
         "#fdecea", COLORS["warn"], fontsize=7.2)

    fig.text(0.5, 0.015,
             "Last full size measurement 1.45 GB (day-4 gate report); not re-measured since.",
             ha="center", va="bottom", fontsize=7.4, color="#555555")

    fig.tight_layout(rect=(0, 0.035, 1, 0.92))
    fig.savefig(OUT / "03_image_layers.png")
    plt.close(fig)
    print("wrote", OUT / "03_image_layers.png")


if __name__ == "__main__":
    fig_multistage_build()
    fig_deploy_state_machine()
    fig_image_layers()
