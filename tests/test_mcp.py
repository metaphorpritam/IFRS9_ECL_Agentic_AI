"""Tests for agent/mcp_server.py -- the MCP adapter over the Tier-1 tools.

The server is a THIN adapter (module docstring): no engine logic, no LLM,
one wrapper function per tool whose only parameter is typed with the real
``TIER1_ARG_MODELS`` entry. These tests exercise it entirely in-process via
fastmcp's ``Client`` against the in-memory ``agent.mcp_server.mcp`` object
-- no subprocess, no stdio pipe, no network -- and check two contracts:

  1. PARITY: calling a tool through MCP with valid arguments returns
     EXACTLY the same numbers as calling the corresponding
     agent.tools_tier1 function directly (same dict, modulo the
     per-call ``tool_call_id`` -- each call is audited separately so the
     sequence number necessarily differs).
  2. FAILS LOUD, NOT LOOSE: invalid arguments (a weight vector that
     doesn't sum to 1, an unknown macro variable, an inverted snapshot
     order, a rejected extra key) surface as ``fastmcp.exceptions.ToolError``
     -- a clean MCP-level error -- never a raw crash, and never a silently
     wrong answer.

No asyncio test plugin is installed in this project (see tests/test_api.py
for the same convention), so every async fastmcp.Client call is driven
through a small ``asyncio.run`` helper from ordinary sync test functions.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import agent.tools_tier1 as tools
from agent.mcp_server import mcp

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def _redirect_log(tmp_path_factory):
    """Keep the real outputs/agent_log/ audit trail clean during tests."""
    old = tools.LOG_PATH
    tools.LOG_PATH = tmp_path_factory.mktemp("agent_log") / "tool_calls.jsonl"
    yield
    tools.LOG_PATH = old


@pytest.fixture(scope="module")
def state():
    """Warm the engine once for the whole module (joblib warm start)."""
    tools.warm_up()
    return tools._state()


def call_tool(name: str, args: dict) -> dict:
    """One in-process MCP tools/call round trip; returns the result dict."""

    async def _run():
        async with Client(mcp) as client:
            result = await client.call_tool(name, {"args": args})
            return result.data

    return asyncio.run(_run())


def call_tool_expect_error(name: str, args: dict) -> ToolError:
    async def _run():
        async with Client(mcp) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool(name, {"args": args})
            return exc_info.value

    return asyncio.run(_run())


def read_resource(uri: str) -> dict:
    async def _run():
        async with Client(mcp) as client:
            contents = await client.read_resource(uri)
            return json.loads(contents[0].text)

    return asyncio.run(_run())


def _without_id(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "tool_call_id"}


# ---------------------------------------------------------------------------
# 0. server shape
# ---------------------------------------------------------------------------

def test_server_exposes_exactly_the_four_tier1_tools():
    async def _run():
        async with Client(mcp) as client:
            return await client.list_tools()

    listed = asyncio.run(_run())
    assert {t.name for t in listed} == set(tools.TIER1_TOOLS)


def _drop_titles(schema: dict) -> dict:
    """fastmcp prunes cosmetic 'title' keys (prune_titles=True); strip them
    here too so this compares the substantive schema, not that cosmetic."""
    return {k: v for k, v in schema.items() if k != "title"}


def test_tool_schema_is_the_real_pydantic_model_verbatim():
    """The wire schema for each tool is TIER1_ARG_MODELS[name], not a copy."""
    for name, model in tools.TIER1_ARG_MODELS.items():
        mcp_tool = asyncio.run(mcp.get_tool(name))
        wire_defs = mcp_tool.parameters["$defs"][model.__name__]
        real = model.model_json_schema()
        wire_props = {k: _drop_titles(v) for k, v in wire_defs["properties"].items()}
        real_props = {k: _drop_titles(v) for k, v in real["properties"].items()}
        assert wire_props == real_props
        assert wire_defs.get("required", []) == real.get("required", [])


def test_health_resource_reports_engine_facts_without_warming():
    """Reading the health resource must NOT build the heavy engine state."""
    was_warm_before = tools._STATE is not None
    info = read_resource("resource://ifrs9-ecl/health")
    assert info["book_snapshot_t"] == tools.T_SNAP
    assert info["book_period"] == "2015Q1"
    assert info["tier1_cache_version"] == tools.CACHE_VERSION
    assert set(info["tools"]) == set(tools.TIER1_TOOLS)
    assert info["frozen_engine_modules"] == [
        "engine/hazard.py", "engine/lgd.py", "engine/ead.py",
        "engine/staging.py", "engine/ecl.py",
    ]
    # a resource read is bookkeeping only -- it must not warm the engine
    assert (tools._STATE is not None) == was_warm_before
    assert info["engine_warm"] == was_warm_before


# ---------------------------------------------------------------------------
# 1. parity: MCP round trip == direct tools_tier1 call, number for number
# ---------------------------------------------------------------------------

def test_shock_macro_parity(state):
    direct = tools.shock_macro(var="UER", shock=2.0, shape="peak_revert")
    via_mcp = call_tool("shock_macro",
                        {"var": "UER", "shock": 2.0, "shape": "peak_revert"})
    assert _without_id(via_mcp) == _without_id(direct)
    assert via_mcp["tool_call_id"].startswith("tc-")
    assert via_mcp["shocked_allowance"] == direct["shocked_allowance"]


def test_reweight_scenarios_parity(state):
    direct = tools.reweight_scenarios(w_up=0.3, w_base=0.4, w_down=0.3)
    via_mcp = call_tool("reweight_scenarios",
                        {"w_up": 0.3, "w_base": 0.4, "w_down": 0.3})
    assert _without_id(via_mcp) == _without_id(direct)
    assert via_mcp["jensen_ratio"] == direct["jensen_ratio"]


def test_rerun_ecl_parity(state):
    direct = tools.rerun_ecl(segment="high_ltv")
    via_mcp = call_tool("rerun_ecl", {"segment": "high_ltv"})
    assert _without_id(via_mcp) == _without_id(direct)
    assert via_mcp["weighted_allowance"] == direct["weighted_allowance"]


def test_rerun_ecl_parity_default_segment(state):
    """Default field value (segment='all') round-trips through MCP too."""
    direct = tools.rerun_ecl()
    via_mcp = call_tool("rerun_ecl", {})
    assert _without_id(via_mcp) == _without_id(direct)


def test_decompose_waterfall_parity(state):
    direct = tools.decompose_waterfall(t0=10, t1=50)
    via_mcp = call_tool("decompose_waterfall", {"t0": 10, "t1": 50})
    assert _without_id(via_mcp) == _without_id(direct)
    assert via_mcp["identity_gap"] == pytest.approx(0.0, abs=1e-6)


def test_mcp_result_is_json_serialisable(state):
    via_mcp = call_tool("shock_macro", {"var": "GDP", "shock": -1.0})
    json.dumps(via_mcp)


def test_audit_trail_gets_one_line_per_mcp_call(state):
    before = len(_read_log())
    call_tool("rerun_ecl", {"segment": "stage1"})
    after = _read_log()
    assert len(after) == before + 1
    assert after[-1]["tool"] == "rerun_ecl"
    assert after[-1]["args"] == {"segment": "stage1"}


def _read_log() -> list[dict]:
    p = Path(tools.LOG_PATH)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines()
            if line.strip()]


# ---------------------------------------------------------------------------
# 2. invalid arguments surface as MCP errors, never a crash
# ---------------------------------------------------------------------------

def test_reweight_bad_weight_sum_is_mcp_error():
    err = call_tool_expect_error(
        "reweight_scenarios", {"w_up": 0.9, "w_base": 0.9, "w_down": 0.9})
    assert "sum to 1" in str(err)


def test_shock_macro_unknown_var_is_mcp_error():
    err = call_tool_expect_error(
        "shock_macro", {"var": "FX", "shock": 1.0})
    assert "var" in str(err)


def test_shock_macro_out_of_bounds_shock_is_mcp_error():
    err = call_tool_expect_error(
        "shock_macro", {"var": "UER", "shock": 25.0})
    assert "10" in str(err)


def test_rerun_ecl_unknown_segment_is_mcp_error():
    err = call_tool_expect_error("rerun_ecl", {"segment": "stage4"})
    assert "segment" in str(err)


def test_decompose_waterfall_inverted_snapshots_is_mcp_error():
    err = call_tool_expect_error(
        "decompose_waterfall", {"t0": 40, "t1": 20})
    assert "t0" in str(err) or "t1" in str(err)


def test_extra_argument_is_rejected_as_mcp_error():
    err = call_tool_expect_error(
        "shock_macro", {"var": "UER", "shock": 1.0, "sneaky": 1})
    assert "sneaky" in str(err) or "extra" in str(err).lower()


def test_invalid_args_do_not_write_the_audit_trail():
    before = len(_read_log())
    call_tool_expect_error(
        "reweight_scenarios", {"w_up": 0.9, "w_base": 0.9, "w_down": 0.9})
    assert len(_read_log()) == before
