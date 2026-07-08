## MCP server: the same four tools, over the Model Context Protocol

`agent/mcp_server.py` exposes the four Tier-1 tools — `shock_macro`,
`reweight_scenarios`, `rerun_ecl`, `decompose_waterfall` — as an MCP server,
so any MCP client (Claude Desktop, an IDE agent, a script using the
`fastmcp`/`mcp` SDK) can call them directly, with no HTTP layer and no
copilot UI in between. It is a **thin adapter only**: every argument schema
is the real pydantic model from `agent/tools_tier1.TIER1_ARG_MODELS`
(bounds, `extra="forbid"`, and every cross-field check — weights summing to
1, shock bounds, `t0 < t1` — run unchanged), and every number in every
response comes straight from the frozen IFRS 9 engine, exactly as it does
through the FastAPI routes or the LangGraph copilot. **One validated model,
three surfaces** (direct Python call, `POST /api/tools/{tool}`, MCP) — same
functions, same numbers, no re-implementation anywhere.

### Run it

```bash
cd IFRS9_ECL_Agentic_AI

# stdio transport (default) -- what an MCP client launches as a subprocess
uv run --no-sync python -m agent.mcp_server

# equivalent, via the fastmcp CLI
uv run --no-sync fastmcp run agent/mcp_server.py:mcp
```

First tool call in a fresh process pays the engine's warm-up cost once
(~9s joblib warm start from `outputs/models/tier1_models.joblib`, or a
~19-50s cold refit if that cache is stale or missing); every call after
that in the same process answers in a fraction of a second. Reading the
`resource://ifrs9-ecl/health` resource is cheap and never triggers this —
poll it to check `engine_warm` before asking a question that needs the
first (slow) call.

### Register in Claude Desktop (or any MCP client)

Add to that client's MCP config (e.g. Claude Desktop's
`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ifrs9-ecl-copilot": {
      "command": "uv",
      "args": [
        "run", "--no-sync",
        "--directory", "/absolute/path/to/IFRS9_ECL_Agentic_AI",
        "python", "-m", "agent.mcp_server"
      ]
    }
  }
}
```

Restart the client; it will list `shock_macro`, `reweight_scenarios`,
`rerun_ecl` and `decompose_waterfall` as tools, plus the
`resource://ifrs9-ecl/health` resource.

### Example question flow

A user asks the client: *"What happens to the allowance if unemployment
rises 2 points, and how much of that is Stage 3?"* The client (its own
LLM, not this server) plans two tool calls:

1. `shock_macro({"args": {"var": "UER", "shock": 2.0, "shape": "peak_revert"}})`
   → reported allowance moves from the base-scenario figure to the shocked
   figure, with the full movement decomposition vs. baseline (the entire
   delta books as `remeasurement` — same book, same stages).
2. `rerun_ecl({"args": {"segment": "stage3"}})`
   → Stage 3's scenario-weighted allowance and share of the total book.

The client's own model narrates the two JSON results; **this server never
narrates and never computes** — it only validates arguments and forwards
to the frozen engine. Every call is additionally appended to
`outputs/agent_log/tool_calls.jsonl`, the same audit trail the LangGraph
copilot and the FastAPI routes share.

### Offline test coverage

`tests/test_mcp.py` calls the server in-process (fastmcp's `Client`
against the in-memory `agent.mcp_server.mcp` object — no subprocess, no
stdio, no network) and checks:

* **parity** — each tool called through MCP with valid arguments returns
  the identical result dict as calling `agent.tools_tier1` directly (same
  numbers, modulo the per-call `tool_call_id`);
* **schema fidelity** — the wire schema for each tool is
  `TIER1_ARG_MODELS[name]`'s own JSON schema, not a hand-copied one;
* **fails loud, not loose** — invalid arguments (bad weight sum, unknown
  macro variable, out-of-bounds shock, inverted snapshot order, a
  forbidden extra key) surface as `fastmcp.exceptions.ToolError`, never a
  crash, and are never written to the audit trail.
