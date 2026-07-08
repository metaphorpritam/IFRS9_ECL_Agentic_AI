"""Tier-2: a sandboxed pandas code interpreter over the warmed Tier-1 state.

THE BOUNDARY (unchanged, extended): the LLM never does arithmetic itself.
Tier-1 (agent/tools_tier1.py) lets the LLM parameterise four FIXED engine
calls. Tier-2 goes one step further for long-tail analytical questions the
four fixed tools cannot answer ("which vintage drives the increase", "top 10
loans by allowance", "average LTV of Stage 2 loans", ...): the LLM may WRITE
pandas CODE, but the numbers shown to the user come from EXECUTING that code
in this sandbox against read-only copies of the already-engine-computed t=60
book -- never from the LLM's own arithmetic, and the code is always shown in
the agent trace for audit.

Data surface (the ONLY names available inside sandboxed code, besides ``pd``
and ``np``) -- built ONCE, lazily, from ``agent.tools_tier1``'s warmed
``EngineState`` (no refits: every column below is read straight off already-
fitted/already-run engine outputs), then handed to sandboxed code as FRESH
COPIES on every call (mutating one call's ``book`` can never leak into the
next):

  book  -- one row per non-payoff loan at the t=60 reporting date:
    id                 int    loan id
    stage              int    IFRS 9 stage, 1/2/3 (scenario-invariant)
    balance            float  outstanding balance, USD
    updated_ltv        float  current updated LTV, percent (may be NaN)
    fico               float  origination FICO score (may be NaN)
    investor           bool   investor-occupancy origination
    allowance_up       float  reported allowance under the 'up' scenario, USD
    allowance_base     float  reported allowance under the 'base' scenario
    allowance_down     float  reported allowance under the 'down' scenario
    allowance_weighted float  50/25/25-weighted reported allowance, USD
    coverage           float  allowance_weighted / balance (NaN if balance==0)

  scenarios -- one row per scenario (four rows: up, base, down, weighted):
    scenario  str    'up' | 'base' | 'down' | 'weighted'
    weight    float  adopted scenario weight (1.0 for the 'weighted' row)
    allowance float  total book reported allowance under that scenario, USD
    coverage  float  allowance / total book balance

  z_path -- one row per panel quarter, t = 1..60 (the reporting-date history,
  NOT the 40q scenario projection -- module docstring of tools_tier1 for
  that):
    time                 int    panel clock quarter, 1..60
    calendar              str    calendar quarter label, e.g. '2000Q2'
    n_at_risk             int    loans at risk that quarter
    z                     float  recovered systematic factor at the
                                 calibrated rho (engine.vasicek.calibrate_rho)
    observed_default_rate float  observed quarterly default rate
    ttc_default_rate      float  composition-adjusted through-the-cycle
                                 (TTC) anchor default rate
    pit_default_rate      float  Vasicek point-in-time default rate implied
                                 by z and the TTC anchor at the calibrated rho

Sandbox (``run_sandboxed``)
----------------------------
1. ``ast.parse`` the code, then walk every node BEFORE any execution:
     * imports: only bare ``import pandas`` / ``import numpy`` (any alias)
       or ``from pandas import ...`` / ``from numpy import ...`` -- anything
       else (``os``, ``sys``, ``pandas.io.xxx``, ...) is rejected.
     * every dunder attribute (``__class__``, ``__mro__``, ``__globals__``,
       ``__builtins__``, ...) is rejected outright -- this is what stops
       ``().__class__.__mro__``-style sandbox escapes.
     * the bare names ``exec``, ``eval``, ``compile``, ``open``, ``input``,
       ``breakpoint``, ``globals``, ``locals``, ``vars``, ``getattr``,
       ``setattr``, ``delattr``, ``__import__`` are rejected wherever they
       appear (belt): they are ALSO simply absent from the restricted
       ``__builtins__`` handed to ``exec`` (suspenders), so even an AST
       pattern this walk fails to anticipate still hits a plain
       ``NameError`` at runtime, never the real builtin.
     * any attribute name starting with ``read_`` (pandas/numpy file I/O:
       ``read_csv``, ``read_pickle``, ``read_parquet``, ...) is rejected;
       so is any attribute starting with ``to_`` EXCEPT the five in-memory,
       no-I/O conversions ``to_dict``/``to_list``/`to_numpy``/`to_frame``/
       ``to_series`` (``to_csv``, ``to_pickle``, ``to_sql``, ... are
       filesystem/network writes and stay blocked).
     * ``DataFrame.eval`` / ``.query`` ARE allowed (useful, common pandas
       idioms) -- but only at their DEFAULT engine/parser (a keyword
       argument named ``engine`` or ``parser`` on the call is rejected), and
       their string-literal expression argument may not contain ``@`` (the
       syntax pandas' expression parser uses to reach OUTER-scope Python
       variables -- this is the one way an eval/query STRING, whose
       contents this AST walk cannot itself inspect as code, could reach
       past the dataframe's own columns) or a ``__`` substring. The default
       engine's own expression grammar additionally only accepts
       arithmetic/comparison/boolean expressions over column names and
       literals -- it has no Call/Attribute/Import syntax of its own -- so
       this is a defence-in-depth belt on top of that.
   Any violation raises ``SandboxViolation``, caught and reported as
   ``{"ok": False, "error": ...}`` -- nothing is ever executed.
2. Passing validation, the code runs in a FORKED child process (hard
   isolation: a runaway ``while True`` cannot touch the parent's memory, and
   is killed outright on timeout) with a restricted ``exec`` namespace:
   ``{"pd": pandas, "np": numpy, "book": <copy>, "scenarios": <copy>,
   "z_path": <copy>, "__builtins__": <the small whitelist above>}``.
   ``multiprocessing.get_context("fork")`` is used deliberately over
   ``"spawn"``: this repo's dependency import alone (pandas + numpy) costs
   several SECONDS on this filesystem (cold interpreter start over a slow
   mount), which "spawn" would re-pay on every single sandboxed call by
   re-importing everything in a fresh interpreter; "fork" instead clones the
   ALREADY-warm parent process's memory (its imports, its already-built data
   surface) in milliseconds via copy-on-write, with no re-import and no
   pickling of the (possibly large) book/scenarios/z_path frames across a
   pipe. The known fork-after-threads hazard (a lock held by some OTHER
   parent thread at the instant of fork can wedge the child if it ever
   needs that same lock) is accepted here because the child does nothing
   but exec the validated code and put one result on a
   ``multiprocessing.Queue`` -- it starts no threads of its own and calls
   nothing that is a documented culprit (e.g. the logging module) between
   fork and exit. If this sandbox is ever moved to a deployment where that
   risk is unacceptable, switching ``_FORK_CONTEXT`` to
   ``multiprocessing.get_context("spawn")`` is a one-line change (the
   worker function and its arguments are already top-level and picklable).
3. Hard timeout: ``process.join(timeout_s)``; a still-alive process is
   ``.terminate()``-d, given one grace second, then ``.kill()``-ed. Either
   way the call returns ``{"ok": False, "error": "...timed out..."}`` --
   never hangs the caller.
4. The child's ``result`` variable (mandatory; its absence is an error) is
   summarised: DataFrames/Series are capped at ``MAX_ROWS`` rows AND the
   whole rendering at ``MAX_CHARS`` characters (dtypes are always included,
   even when the rows are truncated), so a stray unbounded query can never
   blow up the narrator's context.

Router route ``analyze_data`` (agent/graph.py, additive): classifies a
long-tail analytical question here; a temperature-0 code-writer LLM call
generates the pandas code against the schema documented above; this module
executes it; on rejection or a runtime error the router gets exactly ONE
repair attempt (the code + the error handed back to the code-writer); still
failing, the question falls through to the fixed REFUSAL path -- never a
guessed or hallucinated number. Every SUCCESSFUL run is audited via
``agent.tools_tier1._log_call`` (question, code, and a hash of the executed
result) into the same ``outputs/agent_log/tool_calls.jsonl`` as Tier-1/Tier-3.
"""

from __future__ import annotations

import ast
import builtins as _builtins_module
import json
import multiprocessing as mp
import os
import string as _string
import sys
import sysconfig
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# data surface: built ONCE from agent.tools_tier1's warmed EngineState
# ---------------------------------------------------------------------------

#: the panel-clock reporting snapshot -- same as agent.tools_tier1.T_SNAP
_T_SNAP = 60


@dataclass
class DataSurface:
    """The three read-only frames exposed to sandboxed code (module docstring)."""

    book: pd.DataFrame
    scenarios: pd.DataFrame
    z_path: pd.DataFrame


_SURFACE: DataSurface | None = None
_SURFACE_LOCK = threading.Lock()


def _build_book(state) -> pd.DataFrame:
    """Per-loan t=60 book: stage/balance/LTV/FICO/investor + per-scenario
    and weighted allowance + coverage -- all read off the CACHED per-loan
    scenario ECL books in ``state.books`` (no re-run)."""
    base = (state.books["base"][["id", "stage", "balance", "ecl_reported"]]
            .rename(columns={"ecl_reported": "allowance_base"}))
    up = (state.books["up"][["id", "ecl_reported"]]
          .rename(columns={"ecl_reported": "allowance_up"}))
    down = (state.books["down"][["id", "ecl_reported"]]
            .rename(columns={"ecl_reported": "allowance_down"}))
    seg = state.segments[["id", "investor_orig_time", "updated_ltv"]]
    fico = (state.panel.loc[state.panel["time"] == _T_SNAP,
                            ["id", "FICO_orig_time"]]
            .drop_duplicates("id"))

    df = (base.merge(up, on="id", how="left", validate="one_to_one")
          .merge(down, on="id", how="left", validate="one_to_one")
          .merge(seg, on="id", how="left", validate="one_to_one")
          .merge(fico, on="id", how="left", validate="one_to_one"))

    w = state.sset.weights
    df["allowance_weighted"] = (w["up"] * df["allowance_up"]
                                + w["base"] * df["allowance_base"]
                                + w["down"] * df["allowance_down"])
    bal = df["balance"].to_numpy(dtype=float)
    df["coverage"] = np.where(bal > 0,
                              df["allowance_weighted"].to_numpy(dtype=float)
                              / np.where(bal > 0, bal, np.nan),
                              np.nan)
    df["investor"] = df["investor_orig_time"] == 1
    df = df.rename(columns={"FICO_orig_time": "fico"})
    df = df[["id", "stage", "balance", "updated_ltv", "fico", "investor",
             "allowance_up", "allowance_base", "allowance_down",
             "allowance_weighted", "coverage"]]
    return df.sort_values("id").reset_index(drop=True)


def _build_scenarios(state) -> pd.DataFrame:
    """One row per scenario (up/base/down/weighted): weight, total
    allowance, book-wide coverage -- read off ``state.scenario_totals``
    (no re-run)."""
    w = state.sset.weights
    rows = [{"scenario": n, "weight": float(w[n]),
             "allowance": float(state.scenario_totals[n]),
             "coverage": float(state.scenario_totals[n] / state.balance)}
            for n in ("up", "base", "down")]
    weighted = sum(w[n] * state.scenario_totals[n] for n in ("up", "base", "down"))
    rows.append({"scenario": "weighted", "weight": 1.0,
                "allowance": float(weighted),
                "coverage": float(weighted / state.balance)})
    return pd.DataFrame(rows)


def _build_z_path(state) -> pd.DataFrame:
    """60-quarter recovered-Z / PD series with calendar labels.

    ``observed_vs_ttc_rates`` is a PREDICT pass of the already-fitted
    default hazard (no fit), and ``pit_pd`` is a closed-form Vasicek
    transform -- neither refits anything.
    """
    from engine.satellite import observed_vs_ttc_rates
    from engine.scenarios import panel_time_to_period
    from engine.vasicek import pit_pd

    tab = observed_vs_ttc_rates(state.panel, state.models["default"],
                                state.macro_means)
    z = np.asarray(state.res.z, dtype=float)
    ttc = tab["expected_ttc"].to_numpy(dtype=float)
    pit = np.asarray(pit_pd(ttc, z, state.res.rho), dtype=float)
    times = tab.index.to_numpy()
    calendar = [str(panel_time_to_period(int(t))) for t in times]
    return pd.DataFrame({
        "time": times.astype(int),
        "calendar": calendar,
        "n_at_risk": tab["n_at_risk"].to_numpy(dtype=int),
        "z": z,
        "observed_default_rate": tab["observed"].to_numpy(dtype=float),
        "ttc_default_rate": ttc,
        "pit_default_rate": pit,
    }).reset_index(drop=True)


def _data_surface() -> DataSurface:
    """Lazy singleton (module scope), built from tools_tier1's warmed state.

    Tests monkeypatch this function directly to avoid ever building the real
    engine state -- see tests/test_tier2.py.
    """
    global _SURFACE
    if _SURFACE is None:
        with _SURFACE_LOCK:
            if _SURFACE is None:
                from agent.tools_tier1 import _state
                state = _state()
                _SURFACE = DataSurface(book=_build_book(state),
                                       scenarios=_build_scenarios(state),
                                       z_path=_build_z_path(state))
    return _SURFACE


def warm_up() -> None:
    """Build the Tier-2 data surface now (mirrors tools_tier1.warm_up)."""
    _data_surface()


# ---------------------------------------------------------------------------
# AST validation (BEFORE any execution -- the module docstring)
# ---------------------------------------------------------------------------

class SandboxViolation(ValueError):
    """Raised by ``_validate_ast``; always caught in ``run_sandboxed`` and
    turned into ``{"ok": False, "error": str(exc)}`` -- never propagates."""


#: only these two top-level modules may be imported inside sandboxed code
#: (pd/np are already provided in the exec namespace -- this whitelist only
#: matters for a redundant `import pandas as pd`-style line)
ALLOWED_IMPORT_MODULES = {"pandas", "numpy"}

#: bare identifiers that are never allowed to appear, ANYWHERE, in sandboxed
#: code -- belt; these are ALSO simply absent from SAFE_BUILTINS (suspenders)
FORBIDDEN_NAMES = frozenset({
    "exec", "eval", "compile", "open", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "__import__", "__builtins__", "__builtin__", "memoryview",
})

#: the only .to_*() methods that do NOT touch the filesystem/network
SAFE_TO_METHODS = frozenset({"to_dict", "to_list", "to_numpy", "to_frame",
                             "to_series"})

#: pandas expression-evaluation methods that ARE allowed (module docstring)
EVAL_QUERY_METHODS = frozenset({"eval", "query"})

#: kwargs on .eval()/.query() that would move them off their DEFAULT engine
FORBIDDEN_EVAL_QUERY_KWARGS = frozenset({"engine", "parser", "local_dict",
                                         "global_dict", "resolvers",
                                         "level"})

#: str methods that interpolate an object's ATTRIBUTES/ITEMS into a template
#: -- ``"{0.io.common.os.environ}".format(pd)`` reaches os.environ entirely
#: inside a string literal the attribute walk above can never see, so the
#: literal template is inspected here instead (module docstring)
FORMAT_METHODS = frozenset({"format", "format_map"})

#: leaf attribute names that reach the OS / other modules / interpreter
#: internals through a chain the dunder+read_/to_ filters do not catch --
#: e.g. ``pd.io.common.os.system`` / ``np.lib.npyio.os`` / ``pd.io.common.
#: get_handle`` / ``np.fromfile``. A denylist is deliberately DEFENCE IN
#: DEPTH (nice pre-execution error + a clean repair signal); the forked
#: child's runtime hardening (``_harden_child``: env scrub + audit hook +
#: address-space cap) is the PATH-INDEPENDENT backstop that also stops
#: whatever this list fails to anticipate.
FORBIDDEN_ATTRS = frozenset({
    # module handles reachable off pandas/numpy submodules
    "os", "sys", "subprocess", "builtins", "importlib", "imp", "ctypes",
    "socket", "posix", "nt", "pty", "shutil", "pathlib", "tempfile", "glob",
    "pickle", "cPickle", "marshal", "runpy", "pdb", "codeop", "sysconfig",
    "site", "webbrowser", "signal", "resource", "mmap", "fcntl",
    "multiprocessing", "asyncio", "gc", "inspect", "traceback", "linecache",
    "_thread", "threading",
    # os process / env primitives
    "system", "popen", "fork", "forkpty", "execv", "execve", "execvp",
    "execvpe", "execl", "execle", "execlp", "spawnl", "spawnle", "spawnlp",
    "spawnv", "spawnve", "spawnvp", "posix_spawn", "posix_spawnp",
    "startfile", "putenv", "getenv", "unsetenv", "environ", "environb",
    "setuid", "setgid", "open",
    # frame / import-machinery / introspection reach-arounds
    # (NB: no 'stack' -- DataFrame.stack() is a legit reshape; inspect/
    # traceback, the only ways to reach frame stacks, are blocked by name)
    "getframe", "_getframe", "currentframe", "getouterframes",
    "getmembers", "getsource", "getmodule", "mro", "subclasses",
    "attrgetter", "methodcaller", "import_module", "find_spec", "modules",
    "meta_path", "path_hooks", "path_importer_cache",
    # pandas/numpy file I/O NOT already caught by the read_*/to_* rule
    "fromfile", "tofile", "load", "save", "savez", "savez_compressed",
    "loadtxt", "savetxt", "genfromtxt", "memmap", "fromregex", "DataSource",
    "get_handle", "ExcelWriter", "HDFStore",
})

#: attribute-name PREFIXES that expose frame / generator / coroutine /
#: async-generator / traceback / code-object internals (``gi_frame``,
#: ``f_back``, ``f_globals``, ``f_builtins``, ``cr_frame``, ``tb_frame``,
#: ``co_consts``, ...) -- a running generator's frame walks straight back to
#: the child worker's real-``__builtins__`` globals, so the whole family is
#: blocked. The trailing underscore is load-bearing: it spares legitimate
#: pandas methods/columns (``count``, ``corr``, ``cov``, ``coverage``,
#: ``fico``, ``first``, ``agg``, ...) that merely start with the same letters.
FORBIDDEN_ATTR_PREFIXES = ("f_", "gi_", "cr_", "ag_", "tb_", "co_")


def _validate_format_string(fmt: str, method: str) -> None:
    """Reject a ``str.format``/``format_map`` TEMPLATE that reaches into an
    argument's attributes or items (``{0.a.b}`` / ``{0[k]}``) or names a
    dunder -- the one way a format call could exfiltrate through a string
    literal the attribute walk cannot see."""
    if "__" in fmt:
        raise SandboxViolation(
            f".{method}(...) template may not contain '__' in sandboxed code")
    try:
        fields = list(_string.Formatter().parse(fmt))
    except Exception as exc:                              # malformed template
        raise SandboxViolation(
            f".{method}(...) template is malformed: {exc}")
    for _literal, field_name, _spec, _conv in fields:
        if field_name and ("." in field_name or "[" in field_name):
            raise SandboxViolation(
                f".{method}(...) template field {field_name!r} performs "
                f"attribute/index access, which is not allowed in "
                f"sandboxed code")


def _eval_query_expr_node(node: ast.Call) -> ast.AST | None:
    """The expression argument of a .eval()/.query() call: the first
    positional, else an ``expr=`` keyword. ``None`` if neither is present."""
    if node.args:
        return node.args[0]
    for kw in node.keywords:
        if kw.arg == "expr":
            return kw.value
    return None


def _validate_ast(tree: ast.AST) -> None:
    """Walk EVERY node of the parsed code; raise SandboxViolation on the
    first violation found. See the module docstring for the full policy."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORT_MODULES:
                    raise SandboxViolation(
                        f"import of {alias.name!r} is not allowed in "
                        f"sandboxed code (only pandas/numpy)")
        elif isinstance(node, ast.ImportFrom):
            if node.module not in ALLOWED_IMPORT_MODULES:
                raise SandboxViolation(
                    f"'from {node.module} import ...' is not allowed in "
                    f"sandboxed code (only pandas/numpy)")
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                raise SandboxViolation(
                    f"use of {node.id!r} is not allowed in sandboxed code")
        elif isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__"):
                raise SandboxViolation(
                    f"dunder attribute access ('.{attr}') is not allowed "
                    f"in sandboxed code")
            if attr in FORBIDDEN_ATTRS or attr.startswith(
                    FORBIDDEN_ATTR_PREFIXES):
                raise SandboxViolation(
                    f"attribute access '.{attr}' is not allowed in "
                    f"sandboxed code (frame/module/OS-escape surface)")
            if attr.startswith("read_") or (attr.startswith("to_")
                                            and attr not in SAFE_TO_METHODS):
                raise SandboxViolation(
                    f"I/O method '.{attr}(...)' is not allowed in "
                    f"sandboxed code (read_*/to_* touch the filesystem; "
                    f"only {sorted(SAFE_TO_METHODS)} are safe in-memory "
                    f"conversions)")
        elif isinstance(node, ast.Call):
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr in EVAL_QUERY_METHODS:
                for kw in node.keywords:
                    if kw.arg in FORBIDDEN_EVAL_QUERY_KWARGS:
                        raise SandboxViolation(
                            f".{func.attr}(...) must use its default "
                            f"engine/parser in sandboxed code (got "
                            f"{kw.arg!r} override)")
                expr = _eval_query_expr_node(node)
                # the expression MUST be a string literal, so its contents can
                # actually be inspected here -- a variable expression
                # (``e = '...'; df.query(e)``) would sail straight past the
                # @/dunder check below and reach the engine unvalidated.
                if not (isinstance(expr, ast.Constant)
                        and isinstance(expr.value, str)):
                    raise SandboxViolation(
                        f".{func.attr}(...) expression must be a string "
                        f"literal in sandboxed code (so its contents can be "
                        f"validated before execution)")
                if "@" in expr.value or "__" in expr.value:
                    raise SandboxViolation(
                        f".{func.attr}(...) expression string may not "
                        f"reference outer-scope variables ('@...') or dunder "
                        f"names in sandboxed code")
            elif func.attr in FORMAT_METHODS and isinstance(
                    func.value, ast.Constant) and isinstance(
                    func.value.value, str):
                _validate_format_string(func.value.value, func.attr)


# ---------------------------------------------------------------------------
# restricted execution namespace
# ---------------------------------------------------------------------------

#: everything the code-writer LLM is told it may use -- deliberately small
_SAFE_BUILTIN_NAMES = (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter",
    "float", "frozenset", "int", "len", "list", "map", "max", "min",
    "print", "range", "reversed", "round", "set", "slice", "sorted", "str",
    "sum", "tuple", "zip", "True", "False", "None",
    "ValueError", "TypeError", "KeyError", "IndexError", "StopIteration",
    "ZeroDivisionError", "ArithmeticError", "Exception",
)

SAFE_BUILTINS = {name: getattr(_builtins_module, name)
                 for name in _SAFE_BUILTIN_NAMES
                 if hasattr(_builtins_module, name)}


def _restricted_globals(surface: DataSurface) -> dict:
    return {
        "__builtins__": dict(SAFE_BUILTINS),
        "pd": pd,
        "np": np,
        "book": surface.book.copy(deep=True),
        "scenarios": surface.scenarios.copy(deep=True),
        "z_path": surface.z_path.copy(deep=True),
    }


# ---------------------------------------------------------------------------
# result summarisation (caps: module docstring)
# ---------------------------------------------------------------------------

MAX_ROWS = 50
MAX_CHARS = 5000


def _jsonable(v: Any) -> Any:
    """Best-effort JSON-safe conversion of a single scalar value."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, pd.Period)):
        return str(v)
    if isinstance(v, float) and not np.isfinite(v):
        return str(v)          # 'nan'/'inf'/'-inf' -- json.dumps chokes else
    return v


def _shrink_list_to_char_budget(preview: dict, list_key: str,
                                count_keys: tuple[str, ...]) -> None:
    """Mutates ``preview[list_key]`` in place, halving it until the WHOLE
    preview renders within MAX_CHARS (or only one element is left) -- this
    keeps the structured preview (dtypes, counts, ...) intact even when the
    row cap alone would still overflow the character budget, rather than
    collapsing the entire result to an opaque truncated string."""
    items = preview.get(list_key) or []
    while len(items) > 1 \
            and len(json.dumps(preview, default=str)) > MAX_CHARS:
        items = items[:max(1, len(items) // 2)]
        preview[list_key] = items
        for ck in count_keys:
            if ck in preview:
                preview[ck] = len(items)


def _summarize_result(result: Any) -> tuple[Any, list[int] | None]:
    """(result_preview, result_shape) for the 'result' variable, capped at
    <=MAX_ROWS rows AND <=MAX_CHARS rendered characters (rows are shrunk
    further, never the reverse, if 50 rows still overflow the character
    budget), with dtypes always summarised for tabular results (module
    docstring)."""
    if isinstance(result, pd.DataFrame):
        capped = result.head(MAX_ROWS)
        rows = [{c: _jsonable(v) for c, v in row.items()}
                for row in capped.to_dict(orient="records")]
        preview = {
            "dtypes": {c: str(t) for c, t in result.dtypes.items()},
            "rows": rows,
            "n_rows_total": int(len(result)),
            "n_rows_shown": int(len(capped)),
        }
        _shrink_list_to_char_budget(preview, "rows", ("n_rows_shown",))
        shape = list(result.shape)
    elif isinstance(result, pd.Series):
        capped = result.head(MAX_ROWS)
        preview = {
            "dtype": str(result.dtype),
            "name": result.name,
            "index": [_jsonable(i) for i in capped.index],
            "values": [_jsonable(v) for v in capped.to_numpy().tolist()],
            "n_rows_total": int(len(result)),
            "n_rows_shown": int(len(capped)),
        }
        _shrink_list_to_char_budget(preview, "values", ("n_rows_shown",))
        preview["index"] = preview["index"][:len(preview["values"])]
        shape = [int(len(result))]
    elif isinstance(result, np.ndarray):
        flat = result.reshape(-1) if result.ndim > 1 else result
        capped = flat[:MAX_ROWS]
        preview = {
            "dtype": str(result.dtype),
            "values": [_jsonable(v) for v in capped.tolist()],
            "n_total": int(flat.size),
            "n_shown": int(capped.size),
        }
        _shrink_list_to_char_budget(preview, "values", ("n_shown",))
        shape = list(result.shape)
    elif isinstance(result, dict):
        items = list(result.items())[:MAX_ROWS]
        preview = {str(k): _jsonable(v) for k, v in items}
        shape = [len(result)]
    elif isinstance(result, (list, tuple)):
        capped = list(result)[:MAX_ROWS]
        preview = [_jsonable(v) for v in capped]
        shape = [len(result)]
    else:
        preview = _jsonable(result)
        shape = None

    text = json.dumps(preview, default=str)
    if len(text) > MAX_CHARS:
        preview = text[:MAX_CHARS] + "...<truncated>"
    return preview, shape


# ---------------------------------------------------------------------------
# the forked child worker + run_sandboxed
# ---------------------------------------------------------------------------

#: fork (not spawn): module docstring explains why -- warm-process reuse on
#: a filesystem where cold pandas/numpy import costs multiple SECONDS
_FORK_CONTEXT = mp.get_context("fork")

#: default hard wall-clock budget for one sandboxed execution
DEFAULT_TIMEOUT_S = 5.0

#: extra address space the child may use ON TOP OF the footprint it inherits
#: from the warmed parent -- a belt on the wall-clock timeout so a fast
#: ``np.ones((100000, 100000))`` / ``'a' * 10**10`` fails with MemoryError
#: instead of thrashing the host toward the OOM killer (which could take the
#: PARENT down). The ceiling is RELATIVE (baseline + this headroom), never an
#: absolute value: the full app's warmed parent already maps GiBs of virtual
#: memory (matplotlib / statsmodels / BLAS arenas), and an absolute cap below
#: that baseline would strangle every allocation in the child, even a trivial
#: ``Series.sum()``.
_CHILD_AS_HEADROOM_BYTES = 2 * 1024 ** 3


def _current_address_space_bytes() -> int | None:
    """The virtual size the child inherits from the parent (Linux /proc),
    used to size RLIMIT_AS relative to that baseline. Read before the audit
    hook is installed, so this open() is unrestricted. ``None`` off Linux ->
    the cap is skipped (the wall-clock timeout still bounds a runaway)."""
    try:
        with open("/proc/self/statm") as fh:
            pages = int(fh.read().split()[0])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return None


def _compute_import_safe_prefixes() -> tuple[str, ...]:
    """Directories the forked child may still READ from -- Python's own
    interpreter / stdlib / site-packages trees, so pandas' lazy internal
    imports (e.g. pyarrow on ``.query`` under pandas 3.x) keep working while
    EVERY other path (the project tree with its ``.env``, ``/etc``, ``/proc/
    self/environ``, the user's home) is refused. Deliberately does NOT
    include ``sys.path`` entries like the repo root or ``''`` -- those are
    exactly where secrets live. Computed in the parent, inherited by fork."""
    cands: set[str] = set()
    for p in (sys.base_prefix, sys.prefix, sys.base_exec_prefix,
              sys.exec_prefix):
        if p:
            cands.add(p)
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        try:
            path = sysconfig.get_path(key)
        except Exception:
            path = None
        if path:
            cands.add(path)
    out = set()
    for c in cands:
        a = os.path.abspath(c)
        out.add(a if a.endswith(os.sep) else a + os.sep)
    return tuple(sorted(out))


#: import-machinery read allowlist for the child's file-open audit gate
_IMPORT_SAFE_PREFIXES = _compute_import_safe_prefixes()

#: audit-event name prefixes the child blocks outright -- process spawning,
#: networking, native-code loading, env mutation, filesystem mutation. These
#: are the ACTUAL damage/exfil primitives, so blocking them closes the hole
#: no matter which attribute chain or frame walk reached ``os``/``subprocess``
#: /``socket``/``ctypes`` in the first place.
_BLOCKED_AUDIT_PREFIXES = (
    "os.system", "os.exec", "os.spawn", "os.posix_spawn", "os.fork",
    "os.forkpty", "os.startfile", "os.putenv", "os.unsetenv", "os.setuid",
    "os.setgid", "os.symlink", "os.link", "os.rename", "os.replace",
    "os.remove", "os.unlink", "os.rmdir", "os.mkdir", "os.makedirs",
    "os.chmod", "os.chown", "os.chdir", "os.truncate", "os.kill",
    "os.killpg", "os.chroot", "os.chflags",
    "subprocess.", "socket.", "ctypes.", "pty.", "winreg.", "shutil.",
    "webbrowser.", "_posixsubprocess.", "fcntl.", "resource.setrlimit",
)


def _check_open_event(args: tuple) -> None:
    """Audit gate for the 'open' event: refuse every WRITE, and every READ
    outside Python's own import paths -- so ``.env``/``/etc/passwd``/``/proc/
    self/environ`` are unreadable while pandas' internal imports still load."""
    path = args[0] if args else None
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else None
    if isinstance(mode, str) and any(c in mode for c in "wax+"):
        raise PermissionError("file writes are not permitted in the sandbox")
    if isinstance(flags, int) and (flags & (os.O_WRONLY | os.O_RDWR
                                            | os.O_CREAT | os.O_APPEND
                                            | os.O_TRUNC)):
        raise PermissionError("file writes are not permitted in the sandbox")
    if isinstance(path, int):
        return                       # opening through an already-open fd
    try:
        resolved = os.path.abspath(os.fspath(path))
    except TypeError:
        raise PermissionError("file access is not permitted in the sandbox")
    if not resolved.startswith(_IMPORT_SAFE_PREFIXES):
        raise PermissionError(
            f"reading {resolved!r} is not permitted in the sandbox "
            f"(only Python's own import paths are readable)")


def _sandbox_audit_hook(event: str, args: tuple) -> None:
    """Un-removable process-wide audit hook installed in the child. Raises
    on any dangerous event; the raise turns the offending line into an
    ordinary caught exception -> ``{"ok": False, ...}``."""
    if event == "open":
        _check_open_event(args)
        return
    for prefix in _BLOCKED_AUDIT_PREFIXES:
        if event.startswith(prefix):
            raise PermissionError(
                f"operation {event!r} is not permitted in the sandbox")


def _harden_child() -> None:
    """Lock the forked child down BEFORE any user code runs. Three
    path-independent layers on top of the AST filter:

    1. cap the address space so a giant allocation fails fast (belt on the
       wall-clock timeout);
    2. SCRUB the environment -- no secret (HF_TOKEN, OPENROUTER/GOOGLE/GROQ/
       FRED API keys) is reachable via ``os.environ`` or a format-string
       gadget once it is gone;
    3. install an audit hook (done LAST, so step 2's unsetenv events do not
       trip it) that blocks file writes, reads outside the import tree, and
       every process/network/native-code primitive.
    """
    try:
        import resource
        baseline = _current_address_space_bytes()
        if baseline is not None:
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            want = baseline + _CHILD_AS_HEADROOM_BYTES
            if hard != resource.RLIM_INFINITY:
                want = min(want, hard)
            # never LOWER an already-tighter soft limit
            if soft == resource.RLIM_INFINITY or want < soft:
                resource.setrlimit(resource.RLIMIT_AS, (want, hard))
    except Exception:
        pass                         # non-POSIX / restricted: best effort
    try:
        os.environ.clear()
    except Exception:
        pass
    try:
        sys.addaudithook(_sandbox_audit_hook)
    except Exception:
        pass


def _child_worker(code: str, surface: DataSurface, queue) -> None:
    """Runs ENTIRELY inside the forked child process. Never raises across
    the process boundary -- always puts exactly one JSON-safe dict."""
    try:
        _harden_child()
        restricted = _restricted_globals(surface)
        compiled = compile(code, "<sandbox>", "exec")
        exec(compiled, restricted, restricted)          # noqa: S102 (validated)
        if "result" not in restricted:
            queue.put({"ok": False, "result_preview": None,
                      "result_shape": None,
                      "error": "code did not assign a 'result' variable"})
            return
        preview, shape = _summarize_result(restricted["result"])
        queue.put({"ok": True, "result_preview": preview,
                  "result_shape": shape, "error": None})
    except BaseException as exc:                        # noqa: BLE001
        queue.put({"ok": False, "result_preview": None, "result_shape": None,
                  "error": f"{type(exc).__name__}: {exc}"})


_PANDAS_WARMED = False


def _ensure_pandas_warm() -> None:
    """Trigger pandas' lazy internal imports (e.g. pyarrow / the computation
    stack pulled in by ``.query``/``.eval``) ONCE in the parent, so the
    forked child inherits them warm and does not have to open library files
    at all -- keeps the child's read-only 'open' gate (``_check_open_event``)
    almost entirely idle in the common case."""
    global _PANDAS_WARMED
    if _PANDAS_WARMED:
        return
    _PANDAS_WARMED = True
    try:
        df = pd.DataFrame({"_w": [1, 2, 3]})
        df.query("_w > 1")
        df.eval("_w + 1")
        df.groupby("_w")["_w"].sum()
        pd.eval("1 + 1")
    except Exception:
        pass


def run_sandboxed(code: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """AST-validate, then execute ``code`` in an isolated forked child.

    Returns ``{"code": code, "ok": bool, "result_preview": ..., "result_
    shape": ..., "error": str | None}``. ``ok`` is False (never an
    exception) for: a syntax error, any AST-policy violation (module
    docstring), a runtime exception inside the sandboxed code, a missing
    ``result`` assignment, or a timeout.
    """
    out = {"code": code, "ok": False, "result_preview": None,
           "result_shape": None, "error": None}

    if not isinstance(code, str) or not code.strip():
        out["error"] = "code must be a non-empty string"
        return out

    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        out["error"] = f"syntax error: {exc}"
        return out

    try:
        _validate_ast(tree)
    except SandboxViolation as exc:
        out["error"] = str(exc)
        return out

    surface = _data_surface()
    _ensure_pandas_warm()
    queue = _FORK_CONTEXT.Queue()
    proc = _FORK_CONTEXT.Process(target=_child_worker,
                                 args=(code, surface, queue))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(1.0)
        if proc.is_alive():                              # pragma: no cover
            proc.kill()
            proc.join()
        out["error"] = (f"execution exceeded the {timeout_s:g}s sandbox "
                        f"timeout and was terminated")
        return out

    try:
        # a short GET-with-timeout, not queue.empty(): Queue.empty() can
        # race the child's feeder thread flushing its last item into the
        # pipe even though proc.join() above has already returned (the
        # child's OS-level exit is what join() waits on, not the queue's
        # internal bookkeeping) -- get(timeout=...) blocks just long enough
        # for that flush without ever hanging the caller.
        out.update(queue.get(timeout=1.0))
    except Exception:
        out["error"] = (f"sandboxed process exited without a result "
                        f"(exit code {proc.exitcode})")
    return out


# ---------------------------------------------------------------------------
# router-facing argument contract (mirrors tier3_retrieval.QueryModelDocsArgs)
# ---------------------------------------------------------------------------

class AnalyzeDataArgs(BaseModel):
    """Deliberately EMPTY (extra='forbid'): the router only classifies --
    the question text itself drives the code-writer LLM call in
    agent/graph.py, never a router-authored paraphrase (same rationale as
    tier3_retrieval.QueryModelDocsArgs)."""

    model_config = ConfigDict(extra="forbid")


TIER2_ARG_MODELS = {"analyze_data": AnalyzeDataArgs}
