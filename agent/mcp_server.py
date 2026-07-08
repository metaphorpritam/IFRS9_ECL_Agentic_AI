"""MCP server: the four Tier-1 tools exposed over the Model Context Protocol.

THIN ADAPTER, nothing else. This module contains NO engine logic, NO LLM
call, and NO re-declared argument shape: every tool below is a one-line
forwarder onto the already-validated functions in agent/tools_tier1.py, and
every tool's wire schema is the corresponding pydantic model from
``TIER1_ARG_MODELS`` verbatim (registered by wrapping each tool in a
function whose sole parameter is typed ``args: <that model>`` — fastmcp
builds the tool's JSON schema straight from the model, so the model's
Field bounds AND its ``model_validator`` cross-field checks (shock bounds,
weights-sum-to-1, t0 < t1) all run unmodified on every MCP call). THE
GOVERNING RULE of the project holds here too: the LLM on the other end of
this server only routes and narrates; every number in every tool result is
computed by the frozen engine (engine/{hazard,lgd,ead,staging,ecl}.py),
completely unchanged by going through MCP instead of a direct Python call
or the FastAPI routes in app/api/main.py — same functions, same numbers,
three surfaces.

Exposed
-------
Tools   (name == the tools_tier1 function name; args schema ==
         TIER1_ARG_MODELS[name] unmodified):
    shock_macro(args: ShockMacroArgs)
    reweight_scenarios(args: ReweightArgs)
    rerun_ecl(args: RerunEclArgs)
    decompose_waterfall(args: DecomposeWaterfallArgs)

Resource
    resource://ifrs9-ecl/health -- static/cheap engine facts (project
    version, frozen-module list, CACHE_VERSION, the t=60 book date, and
    whether the heavy engine state has been built yet in this process).
    Reading it NEVER triggers the engine build below -- it is pure
    bookkeeping, safe to poll.

Lazy warm-up (module init cost, ~9-19s)
----------------------------------------
tools_tier1's heavy state (fitted hazards + LGD, recovered Z, the fitted
satellite, the scenario set, the four per-loan scenario ECL books) is built
lazily on first use, INSIDE tools_tier1 itself (its module-level
``_state()`` singleton, called by every one of the four tool functions).
This server does not add its own warm-up: the first MCP ``tools/call`` of
ANY of the four tools pays that cost once per process --
joblib-warm-started from outputs/models/tier1_models.joblib (~9s) if the
cache fingerprint matches, or a full refit (~19-50s, per the tools_tier1
module docstring) if it does not. Every subsequent call in the same
process answers in-memory in a fraction of a second. There is deliberately
no eager warm_up() call at import time here: an MCP client that only ever
reads the health resource, or that lists tools without calling one, should
not pay that cost.

Run
---
    uv run --no-sync python -m agent.mcp_server        # stdio (default)

or via the fastmcp CLI:

    uv run --no-sync fastmcp run agent/mcp_server.py:mcp

See outputs/mcp/README_section.md for client registration (Claude Desktop
or any other MCP client) and an example question flow.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from fastmcp import FastMCP

import agent.tools_tier1 as tools
from agent.tools_tier1 import TIER1_ARG_MODELS, TIER1_TOOLS
from engine.scenarios import panel_time_to_period

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: the frozen engine modules this server's numbers ultimately come from
FROZEN_ENGINE_MODULES = (
    "engine/hazard.py", "engine/lgd.py", "engine/ead.py",
    "engine/staging.py", "engine/ecl.py",
)


def _project_version() -> str:
    """Read [project].version from pyproject.toml (no hardcoded drift)."""
    try:
        with (PROJECT_ROOT / "pyproject.toml").open("rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "unknown"


mcp = FastMCP(
    name="ifrs9-ecl-copilot",
    version=_project_version(),
    instructions=(
        "Four validated, deterministic tools over a FROZEN IFRS 9 ECL "
        "engine: shock_macro, reweight_scenarios, rerun_ecl, "
        "decompose_waterfall. Every number returned is computed by the "
        "engine -- never invent or adjust a figure; if a question needs "
        "something none of these four tools compute, say so rather than "
        "estimating. Read resource://ifrs9-ecl/health for book date and "
        "engine status."
    ),
)


# ---------------------------------------------------------------------------
# tool registration: one wrapper per Tier-1 tool, schema == TIER1_ARG_MODELS
# ---------------------------------------------------------------------------

def _make_tool_wrapper(name: str, model: type[BaseModel],
                       fn: Callable[..., dict]) -> Callable[..., dict]:
    """A single-argument forwarder: args -> fn(**args.model_dump()).

    The wrapper's only parameter is annotated with the REAL pydantic model
    (not a hand-copied signature), so fastmcp's generated input schema is
    that model's schema verbatim, and calling through MCP constructs and
    validates an actual instance of it -- Field bounds, ``extra='forbid'``
    and every ``model_validator`` cross-check run exactly as they do for a
    direct Python call, before ``fn`` (the frozen-engine tool) ever runs.
    """

    def wrapper(args: model) -> dict:                     # noqa: ANN001
        return fn(**args.model_dump())

    wrapper.__name__ = name
    wrapper.__doc__ = fn.__doc__
    wrapper.__annotations__ = {"args": model, "return": dict}
    return wrapper


for _name, _fn in TIER1_TOOLS.items():
    mcp.tool(
        _make_tool_wrapper(_name, TIER1_ARG_MODELS[_name], _fn),
        name=_name,
    )
del _name, _fn


# ---------------------------------------------------------------------------
# health/info resource (cheap: never builds the engine state)
# ---------------------------------------------------------------------------

@mcp.resource(
    "resource://ifrs9-ecl/health",
    name="engine_health",
    description=(
        "Static/cheap engine facts: version, frozen-engine status, the "
        "t=60 reporting book date, and whether the heavy engine state has "
        "already been warmed in this process. Never triggers the warm-up."
    ),
    mime_type="application/json",
)
def engine_health() -> dict:
    return {
        "service": "ifrs9-ecl-copilot-mcp",
        "version": _project_version(),
        "frozen_engine_modules": list(FROZEN_ENGINE_MODULES),
        "frozen_note": "engine/{hazard,lgd,ead,staging,ecl}.py are "
                       "read-only, never edited by the agent layer",
        "tier1_cache_version": tools.CACHE_VERSION,
        "book_snapshot_t": tools.T_SNAP,
        "book_period": str(panel_time_to_period(tools.T_SNAP)),
        "tools": list(TIER1_TOOLS),
        "engine_warm": tools._STATE is not None,
        "warm_up_note": (
            "engine state builds lazily on the first tool call in this "
            "process: ~9s joblib warm start if "
            "outputs/models/tier1_models.joblib matches the current "
            "fingerprint, otherwise a ~19-50s cold refit; every "
            "subsequent call in the same process answers in-memory."
        ),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
