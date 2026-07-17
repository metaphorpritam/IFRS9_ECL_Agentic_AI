"""Tests for agent/tools_tier2.py (the sandboxed code interpreter) + its
``analyze_data`` wiring into agent/graph.py.

Everything here is OFFLINE. ``agent.tools_tier2.run_sandboxed`` itself never
calls an LLM (it is pure AST-validate-then-execute), so the sandbox tests
run against a small, fully synthetic ``DataSurface`` fixture (monkeypatched
over ``tools_tier2._data_surface``) rather than ever building the real
engine state. The router-integration tests monkeypatch ``_chat_once`` /
``_llm_route`` / ``_llm_codegen`` / ``_llm_narrate`` exactly like
tests/test_router.py and tests/test_tier3.py do for the other tiers.

Contracts:
  1. ESCAPE ATTEMPTS are ALL rejected before any code runs (``ok is False``,
     nothing executed): banned imports, dunder attribute access, the
     forbidden builtin names, filesystem I/O methods, and exec/eval-as-
     strings.
  2. HAPPY PATH: valid pandas code against the documented schema executes,
     caps rows at 50 (with the full row count still reported), and is
     DETERMINISTIC (identical code -> identical result_preview).
  3. TIMEOUT: a ``while True`` loop is killed and reported, not hung.
  4. ROUTER WIRING: a mocked router sends an analytical question to
     ``analyze_data``; a mocked code-writer's code is executed for real and
     narrated; a poem request still REFUSEs untouched; a sandbox failure
     gets exactly one repair attempt, and a repair that ALSO fails falls
     through to the fixed REFUSAL — never a guessed number.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import agent.graph as graph
import agent.tools_tier1 as tools_tier1
import agent.tools_tier2 as tier2

MOCK_ROUTER_MODEL = "mock-router"
MOCK_CODEGEN_MODEL = "mock-codegen"
MOCK_NARRATOR_MODEL = "mock-narrator"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _make_surface(n: int = 120) -> tier2.DataSurface:
    book = pd.DataFrame({
        "id": np.arange(1, n + 1),
        "stage": (np.arange(n) % 3) + 1,
        "balance": np.linspace(1_000.0, 500_000.0, n),
        "updated_ltv": np.linspace(20.0, 120.0, n),
        "fico": np.linspace(600.0, 820.0, n),
        "investor": np.array([i % 4 == 0 for i in range(n)]),
        "allowance_up": np.linspace(10.0, 5_000.0, n),
        "allowance_base": np.linspace(8.0, 4_000.0, n),
        "allowance_down": np.linspace(15.0, 6_000.0, n),
        "allowance_weighted": np.linspace(9.0, 4_500.0, n),
        "coverage": np.linspace(0.001, 0.05, n),
    })
    scenarios = pd.DataFrame({
        "scenario": ["up", "base", "down", "weighted"],
        "weight": [0.25, 0.5, 0.25, 1.0],
        "allowance": [4_000_000.0, 3_000_000.0, 5_000_000.0, 3_500_000.0],
        "coverage": [0.04, 0.03, 0.05, 0.035],
    })
    z_path = pd.DataFrame({
        "time": np.arange(1, 61),
        "calendar": [f"20{10 + q // 4}Q{(q % 4) + 1}" for q in range(60)],
        "n_at_risk": np.arange(100, 160),
        "z": np.linspace(-2.0, 2.0, 60),
        "observed_default_rate": np.linspace(0.005, 0.03, 60),
        "ttc_default_rate": np.full(60, 0.015),
        "pit_default_rate": np.linspace(0.005, 0.03, 60),
    })
    return tier2.DataSurface(book=book, scenarios=scenarios, z_path=z_path)


@pytest.fixture
def surface() -> tier2.DataSurface:
    return _make_surface()


@pytest.fixture(autouse=True)
def _fixed_surface(monkeypatch, surface):
    """Every test in this file gets the synthetic surface, never the real
    (heavy) engine state -- offline by construction."""
    monkeypatch.setattr(tier2, "_data_surface", lambda: surface)


@pytest.fixture(scope="module", autouse=True)
def _redirect_log(tmp_path_factory):
    """analyze_data audits through tools_tier1._log_call (shared audit
    trail) -- redirect its LOG_PATH so pytest never touches the real
    outputs/agent_log/tool_calls.jsonl."""
    old = tools_tier1.LOG_PATH
    tools_tier1.LOG_PATH = tmp_path_factory.mktemp("agent_log") / "tool_calls.jsonl"
    yield
    tools_tier1.LOG_PATH = old


@pytest.fixture(autouse=True)
def _no_network(monkeypatch, tmp_path):
    """Belt-and-braces: any code path that would touch OpenRouter fails
    loudly instead of making a network call."""
    def _no_net(model, messages):
        raise AssertionError("network LLM call attempted in pytest")
    monkeypatch.setattr(graph, "_chat_once", _no_net)
    monkeypatch.setattr(graph, "RUNS_LOG_PATH", tmp_path / "agent_runs.jsonl")


def _runs_log() -> list[dict]:
    p = Path(graph.RUNS_LOG_PATH)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _tool_calls_log() -> list[dict]:
    p = Path(tools_tier1.LOG_PATH)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


# ---------------------------------------------------------------------------
# 1. escape attempts: ALL rejected, nothing executed
# ---------------------------------------------------------------------------

ESCAPE_ATTEMPTS = [
    ("bare import of os", "import os\nresult = 1"),
    ("filesystem read via open", "result = open('/etc/passwd').read()"),
    ("bare __builtins__ reference", "result = __builtins__"),
    ("class-chain mro escape", "result = ().__class__.__mro__"),
    ("getattr indirection", "result = getattr(pd, 'read_csv')"),
    ("book.to_csv filesystem write", "book.to_csv('x.csv')\nresult = 1"),
    ("pd.read_pickle reference", "result = pd.read_pickle"),
    ("pd.read_csv call", "result = pd.read_csv('/etc/passwd')"),
    ("bare exec of a string", "exec(\"import os\")\nresult = 1"),
    ("bare eval of a string", "result = eval('1 + 1')"),
    ("compile then exec", "c = compile('1', '<s>', 'eval')\nresult = 1"),
    ("setattr on a dataframe", "setattr(book, 'x', 1)\nresult = 1"),
    ("globals() introspection", "result = globals()"),
    ("import via importlib-adjacent module", "import sys\nresult = 1"),
    ("import numpy submodule", "import numpy.random as r\nresult = 1"),
    ("from os import path", "from os import path\nresult = 1"),
    ("dunder globals on a function", "result = (lambda: 0).__globals__"),
    ("book.__dict__ access", "result = book.__dict__"),
    # --- NEW (adversarial review): module-traversal RCE / exfiltration ---
    ("module traversal to os.system",
     "result = pd.io.common.os.system('id')"),
    ("module traversal os.environ secret dump",
     "result = dict(pd.io.common.os.environ)"),
    ("module traversal os.environ.get",
     "result = pd.io.common.os.environ.get('HF_TOKEN')"),
    ("os.open arbitrary file read via traversal",
     "result = pd.io.common.os.open('/etc/passwd', 0)"),
    ("os.popen command capture via traversal",
     "result = pd.io.common.os.popen('id').read()"),
    ("numpy submodule reaches os",
     "result = np.lib.npyio.os.environ"),
    ("pandas get_handle opens any file",
     "h = pd.io.common.get_handle('/etc/passwd', 'r')\nresult = 1"),
    # --- numpy/pandas file I/O NOT caught by read_*/to_* ---
    ("numpy fromfile reads a file", "result = np.fromfile('/etc/passwd')"),
    ("numpy tofile writes a file",
     "np.array([1]).tofile('/tmp/x.bin')\nresult = 1"),
    ("numpy load can unpickle",
     "result = np.load('x.npy', allow_pickle=True)"),
    ("numpy save writes a file",
     "np.save('x', np.array([1]))\nresult = 1"),
    ("numpy loadtxt reads a file", "result = np.loadtxt('/etc/passwd')"),
    # --- frame / generator / code-object internals (non-dunder) ---
    ("generator gi_frame handle",
     "result = (x for x in range(1)).gi_frame"),
    ("generator frame f_back walk",
     "g = (x for x in range(1))\nresult = g.gi_frame.f_back"),
    ("generator gi_code object", "result = (x for x in range(1)).gi_code"),
    ("frame f_globals reach-around",
     "g = (x for x in range(1))\nresult = g.gi_frame.f_globals"),
    # --- str.format() attribute-traversal exfiltration (all in a string) ---
    ("format-string attribute traversal env leak",
     "result = '{0.io.common.os.environ}'.format(pd)"),
    ("format-string dunder class leak",
     "result = '{0.__class__}'.format(pd)"),
    ("format_map attribute traversal",
     "result = '{a.__class__}'.format_map({'a': pd})"),
    # --- .eval()/.query() with a NON-literal (un-inspectable) expression ---
    ("eval with a variable expression string",
     "e = '1 + 1'\nresult = pd.eval(e)"),
    ("query with a variable expression string",
     "e = 'stage == 2'\nresult = book.query(e)"),
]


@pytest.mark.parametrize("label,code", ESCAPE_ATTEMPTS, ids=[l for l, _ in ESCAPE_ATTEMPTS])
def test_escape_attempts_are_all_rejected(label, code):
    result = tier2.run_sandboxed(code)
    assert result["ok"] is False, f"{label} was NOT rejected: {result}"
    assert result["error"], f"{label}: rejection carries no error message"
    assert result["result_preview"] is None
    assert result["result_shape"] is None
    assert result["code"] == code


def test_a_while_true_timeout_case_is_killed_not_hung():
    result = tier2.run_sandboxed("result = 0\nwhile True:\n    pass",
                                 timeout_s=1.0)
    assert result["ok"] is False
    assert "timed out" in result["error"] or "timeout" in result["error"]


def test_syntax_error_is_reported_not_raised():
    result = tier2.run_sandboxed("result = (")
    assert result["ok"] is False
    assert "syntax" in result["error"].lower()


def test_empty_code_is_rejected():
    result = tier2.run_sandboxed("")
    assert result["ok"] is False


def test_missing_result_variable_is_reported():
    result = tier2.run_sandboxed("x = 1 + 1")
    assert result["ok"] is False
    assert "result" in result["error"]


def test_eval_query_with_default_engine_is_allowed():
    """.eval()/.query() themselves are legitimate pandas idioms (module
    docstring) -- only the engine/parser override and '@'/dunder content
    inside the expression string are blocked."""
    result = tier2.run_sandboxed("result = book.query('stage == 2')")
    assert result["ok"] is True


def test_query_with_explicit_engine_kwarg_is_rejected():
    result = tier2.run_sandboxed(
        "result = book.query('stage == 2', engine='python')")
    assert result["ok"] is False


def test_query_referencing_outer_scope_via_at_is_rejected():
    result = tier2.run_sandboxed(
        "danger = 1\nresult = book.query('stage == @danger')")
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# 1b. NEW adversarial escapes: the fixes must NOT over-block legit idioms
# ---------------------------------------------------------------------------

def test_module_traversal_error_names_the_offending_attribute():
    """`pd.io.common.os.system(...)` is rejected AT the `.os`/`.system`
    hop -- a clear repair signal, never a runtime side effect."""
    result = tier2.run_sandboxed("result = pd.io.common.os.system('id')")
    assert result["ok"] is False
    assert "os" in result["error"] or "system" in result["error"]


def test_ordinary_number_formatting_is_still_allowed():
    """The format-string guard blocks ATTRIBUTE/INDEX traversal fields, not
    the everyday numeric templates a code-writer legitimately uses."""
    for code in (
        "result = '{:.2f}'.format(float(book['balance'].mean()))",
        "result = '{0} rows'.format(int(book.shape[0]))",
        "result = 'stage {s}'.format(s=int(book['stage'].max()))",
    ):
        r = tier2.run_sandboxed(code)
        assert r["ok"] is True, f"{code!r} was wrongly rejected: {r['error']}"


def test_legit_deep_method_chains_are_untouched():
    """Prefix/denylist tuning must spare real pandas methods whose names
    merely start with a blocked prefix (agg/count/corr/coverage/fico ...)."""
    r = tier2.run_sandboxed(
        "result = book.groupby('stage')['balance']"
        ".agg(['sum', 'mean']).to_dict()")
    assert r["ok"] is True, r["error"]
    r2 = tier2.run_sandboxed(
        "result = int(book[book['coverage'] > 0]['fico'].count())")
    assert r2["ok"] is True, r2["error"]


def test_query_with_a_string_literal_expression_is_still_allowed():
    """Requiring a LITERAL expression (so it can be validated) must not
    break the ordinary literal .query()/.eval() idioms."""
    assert tier2.run_sandboxed("result = book.query('stage == 2')")["ok"]
    assert tier2.run_sandboxed("result = book.eval('balance / 2')")["ok"]


def test_nfkc_normalized_forbidden_name_is_still_caught():
    """Python NFKC-normalises identifiers before the AST is built, so a
    mathematical-bold spelling of `globals` collapses to the real name and
    is caught by the bare-name denylist -- homoglyph smuggling fails."""
    bold_globals = "\U0001d420\U0001d425\U0001d428\U0001d41b\U0001d41a" \
                   "\U0001d425\U0001d42c"          # 'globals' in bold
    result = tier2.run_sandboxed(f"result = {bold_globals}()")
    assert result["ok"] is False
    assert "globals" in result["error"]


def test_a_giant_allocation_is_bounded_not_fatal():
    """A big-alloc attempt returns a bounded error (RLIMIT_AS / numpy's own
    guard), never an unbounded hang or a host OOM -- ok is False, and the
    caller is never handed a number."""
    result = tier2.run_sandboxed(
        "result = np.ones((100000, 100000), dtype='float64').sum()",
        timeout_s=5.0)
    assert result["ok"] is False
    assert result["result_preview"] is None


def test_runtime_hardening_blocks_escapes_even_with_the_ast_filter_off(
        monkeypatch):
    """DEFENCE IN DEPTH: neutralise the AST validator entirely and confirm
    the forked child's own hardening (env scrub + audit hook + rlimit) still
    stops secret exfiltration, RCE, arbitrary file reads and big allocations
    -- so an escape the denylist never anticipated still leaks nothing."""
    monkeypatch.setattr(tier2, "_validate_ast", lambda tree: None)
    monkeypatch.setenv("SANDBOX_CANARY", "TOPSECRET-abc123")

    # env is scrubbed: the canary is simply gone inside the child
    env = tier2.run_sandboxed(
        "result = pd.io.common.os.environ.get('SANDBOX_CANARY', 'GONE')")
    assert env["ok"] is True and env["result_preview"] == "GONE"
    dump = tier2.run_sandboxed("result = dict(pd.io.common.os.environ)")
    assert "TOPSECRET-abc123" not in json.dumps(dump.get("result_preview"))

    # RCE, file reads and networking all fail closed (audit hook)
    for code in (
        "result = pd.io.common.os.system('echo pwned')",
        "fd = pd.io.common.os.open('/etc/passwd', 0)\n"
        "result = pd.io.common.os.read(fd, 40)",
        "h = pd.io.common.get_handle('/etc/passwd', 'r')\n"
        "result = h.handle.read(40)",
    ):
        r = tier2.run_sandboxed(code)
        assert r["ok"] is False, f"runtime backstop failed for {code!r}: {r}"
        assert "root:" not in json.dumps(r.get("result_preview"))


# ---------------------------------------------------------------------------
# 2. happy path: executes for real, caps rows, deterministic
# ---------------------------------------------------------------------------

def test_happy_path_executes_and_reports_dtypes():
    result = tier2.run_sandboxed(
        "result = book[book['stage'] == 2][['id', 'balance']]")
    assert result["ok"] is True
    assert result["error"] is None
    preview = result["result_preview"]
    assert "dtypes" in preview and set(preview["dtypes"]) == {"id", "balance"}
    assert result["result_shape"][1] == 2


def test_result_is_capped_at_fifty_rows_but_total_is_reported():
    result = tier2.run_sandboxed("result = book")     # 120 rows in the fixture
    assert result["ok"] is True
    assert result["result_shape"] == [120, 11]
    preview = result["result_preview"]
    assert preview["n_rows_total"] == 120
    # the full 11-column frame is wide enough that the MAX_CHARS budget
    # binds before the 50-row cap does -- both caps are real, simultaneous
    # constraints (module docstring), so rows may be shrunk further still
    assert 0 < preview["n_rows_shown"] <= 50
    assert len(preview["rows"]) == preview["n_rows_shown"]
    assert len(json.dumps(preview)) <= tier2.MAX_CHARS


def test_result_is_capped_at_fifty_rows_when_it_fits_the_char_budget():
    result = tier2.run_sandboxed(
        "result = book[['id', 'stage']]")             # narrow -> fits easily
    assert result["ok"] is True
    preview = result["result_preview"]
    assert preview["n_rows_total"] == 120
    assert preview["n_rows_shown"] == 50
    assert len(preview["rows"]) == 50


def test_scalar_result_is_returned_directly():
    result = tier2.run_sandboxed("result = float(book['balance'].sum())")
    assert result["ok"] is True
    assert result["result_shape"] is None
    assert isinstance(result["result_preview"], float)


def test_groupby_aggregation_over_scenarios_and_z_path():
    result = tier2.run_sandboxed(
        "result = scenarios.set_index('scenario')['allowance'].to_dict()")
    assert result["ok"] is True
    assert result["result_preview"]["base"] == 3_000_000.0

    result2 = tier2.run_sandboxed(
        "result = float(z_path['pit_default_rate'].mean())")
    assert result2["ok"] is True
    assert isinstance(result2["result_preview"], float)


def test_determinism_same_code_same_result_preview():
    code = "result = book.groupby('stage')['balance'].sum().to_dict()"
    r1 = tier2.run_sandboxed(code)
    r2 = tier2.run_sandboxed(code)
    assert r1["ok"] is True and r2["ok"] is True
    assert r1["result_preview"] == r2["result_preview"]
    assert r1["result_shape"] == r2["result_shape"]


# ---------------------------------------------------------------------------
# 3. router wiring: analyze_data routing, execution, repair, refusal
# ---------------------------------------------------------------------------

GOOD_CODE = "result = book.nlargest(3, 'allowance_weighted')[['id', 'allowance_weighted']]"


@pytest.fixture
def canned_router_to_analyze_data(monkeypatch):
    def fake(question):
        return json.dumps({"route": "analyze_data", "args": {}}), MOCK_ROUTER_MODEL
    monkeypatch.setattr(graph, "_llm_route", fake)


@pytest.fixture
def headline_narrator(monkeypatch):
    def fake(result):
        return f"Engine verdict: {result['headline']}", MOCK_NARRATOR_MODEL
    monkeypatch.setattr(graph, "_llm_narrate", fake)


def test_router_sends_analytical_question_to_analyze_data(
        canned_router_to_analyze_data, headline_narrator, monkeypatch):
    monkeypatch.setattr(
        graph, "_llm_codegen",
        lambda question, **kw: (GOOD_CODE, MOCK_CODEGEN_MODEL))
    q = "What are the top 3 loans by weighted allowance?"
    final = graph.run_agent(q)
    assert final["route"] == "analyze_data"
    assert [e["node"] for e in final["trace"]] == \
        ["router", "analyze_data", "narrator"]
    analyze_event = final["trace"][1]
    assert analyze_event["status"] == "ok"
    assert analyze_event["attempts"][0]["code"] == GOOD_CODE
    assert final["tool_result"]["code"] == GOOD_CODE
    assert final["tool_result"]["result_shape"] == [3, 2]
    assert "Engine verdict:" in final["answer"]
    # the executed result is audited (code + result hash), not the LLM's word
    logged = _tool_calls_log()
    assert logged, "analyze_data success was not audited"
    assert logged[-1]["tool"] == "analyze_data"
    assert logged[-1]["args"]["code"] == GOOD_CODE
    assert "result_hash" in logged[-1]["args"]


def test_poem_request_still_refuses_untouched(monkeypatch):
    def fake(question):
        return json.dumps({"route": "REFUSE", "args": {}}), MOCK_ROUTER_MODEL
    monkeypatch.setattr(graph, "_llm_route", fake)

    def boom(*a, **kw):
        raise AssertionError("analyze_data must not run for a REFUSEd question")
    monkeypatch.setattr(graph, "_llm_codegen", boom)
    monkeypatch.setattr(graph, "run_sandboxed", boom)

    final = graph.run_agent("Write me a poem about credit risk.")
    assert final["route"] == "REFUSE"
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert [e["node"] for e in final["trace"]] == ["router", "refusal"]


def test_sandbox_rejection_triggers_one_repair_then_succeeds(
        canned_router_to_analyze_data, headline_narrator, monkeypatch):
    calls = {"n": 0}

    def flaky_codegen(question, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return "import os\nresult = 1", MOCK_CODEGEN_MODEL     # rejected
        assert "error" in kw and kw["error"]     # repair sees the failure
        return GOOD_CODE, MOCK_CODEGEN_MODEL

    monkeypatch.setattr(graph, "_llm_codegen", flaky_codegen)
    final = graph.run_agent("Which loans carry the most weighted allowance?")
    assert calls["n"] == 2
    assert final["route"] == "analyze_data"
    assert final["answer"] != graph.REFUSAL_MESSAGE
    attempts = final["trace"][1]["attempts"]
    assert len(attempts) == 2
    assert attempts[0]["ok"] is False
    assert attempts[1]["ok"] is True
    assert final["tool_result"]["code"] == GOOD_CODE


def test_repair_also_fails_falls_through_to_refusal(
        canned_router_to_analyze_data, monkeypatch):
    def always_broken(question, **kw):
        return "import os\nresult = 1", MOCK_CODEGEN_MODEL

    monkeypatch.setattr(graph, "_llm_codegen", always_broken)

    def narrator_must_not_run(result):
        raise AssertionError("narrator must not run on a REFUSAL path")
    monkeypatch.setattr(graph, "_llm_narrate", narrator_must_not_run)

    n_logged_before = len(_tool_calls_log())
    final = graph.run_agent("Which loans carry the most weighted allowance?")
    assert final["route"] == "analyze_data"      # the router's classification
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert [e["node"] for e in final["trace"]] == \
        ["router", "analyze_data", "refusal"]
    assert final["trace"][1]["status"] == "error"
    assert len(final["trace"][1]["attempts"]) == 2
    # a failed analysis is NEVER audited into tool_calls.jsonl (nothing ran)
    assert len(_tool_calls_log()) == n_logged_before


def test_codegen_llm_totally_unavailable_falls_through_to_refusal(
        canned_router_to_analyze_data, monkeypatch):
    def dead(question, **kw):
        raise RuntimeError("both codegen models down")
    monkeypatch.setattr(graph, "_llm_codegen", dead)
    final = graph.run_agent("Which loans carry the most weighted allowance?")
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert final["trace"][1]["status"] == "error"
    assert "unavailable" in final["trace"][1]["detail"]


# ---------------------------------------------------------------------------
# route registry / argument-contract sanity
# ---------------------------------------------------------------------------

def test_analyze_data_args_reject_a_sneaky_extra_key(monkeypatch):
    """The router's ONLY valid payload for this route is args={} — anything
    else (e.g. an attempted 'question' override) fails pydantic validation
    (extra='forbid') and collapses to REFUSE, never a guess."""
    def fake_route(question):
        return (json.dumps({"route": "analyze_data",
                            "args": {"sneaky": 1}}), MOCK_ROUTER_MODEL)
    monkeypatch.setattr(graph, "_llm_route", fake_route)
    final = graph.run_agent("top loans by allowance?")
    assert final["route"] == "REFUSE"
    assert "invalid arguments for analyze_data" in final["trace"][0]["detail"]


def test_analyze_data_is_named_in_the_refusal_message():
    assert "analyze_data" in graph.REFUSAL_MESSAGE


def test_all_routes_present_and_the_five_prior_routes_untouched():
    # REASONED (Stretch 3) is additive alongside the six prior routes.
    assert set(graph.ROUTE_ARG_MODELS) == {
        "shock_macro", "reweight_scenarios", "rerun_ecl",
        "decompose_waterfall", "query_model_docs", "analyze_data",
        graph.REASONED}
    # TOOL_ROUTES (the Tier-1 registry order) is exactly the original four
    assert set(graph.TOOL_ROUTES) == {
        "shock_macro", "reweight_scenarios", "rerun_ecl",
        "decompose_waterfall"}


def test_every_run_is_audited_with_full_trace(
        canned_router_to_analyze_data, headline_narrator, monkeypatch):
    monkeypatch.setattr(
        graph, "_llm_codegen",
        lambda question, **kw: (GOOD_CODE, MOCK_CODEGEN_MODEL))
    q = "Top loans by weighted allowance?"
    graph.run_agent(q)
    log = _runs_log()
    assert len(log) == 1
    assert log[0]["route"] == "analyze_data"
    assert [e["node"] for e in log[0]["trace"]] == \
        ["router", "analyze_data", "narrator"]
