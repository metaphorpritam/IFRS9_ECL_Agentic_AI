#!/usr/bin/env python3
"""Generate a Markdown **code map** of a repo by static (AST) analysis, for indexing.

Catalogues: the code directory tree (.py / .ipynb); per file the module docstring, imports
(stdlib / third-party / local), classes (with methods), functions (signature + one-line
doc), and detected data sources; the local-module **dependency hierarchy** (imports); the
function **call graph** (who calls whom, plus a reverse "called-by" / impact map); the
third-party **library usage** map; and a per-file **structural fingerprint**. Pure stdlib;
does not execute the scanned code.

    uv run scan_code.py --root <repo> --dirs src pkg --out corpus/code_map.md

Incremental change classification (optional):
  --fingerprints code_fp.json   read previous fingerprints (if present) and write fresh
                                ones. Each file is classified NONE / COSMETIC / STRUCTURAL
                                by comparing *signatures* (exports, params, imports), not
                                raw bytes — so a comment-only edit is COSMETIC and a caller
                                can skip re-analysing it. The classification is printed and
                                also written into the code map's fingerprint section.

The call graph resolves three things statically (best-effort, no execution):
  * bare calls            foo(...)            -> local function `foo`
  * method calls          self.bar(...)       -> method `bar` on the enclosing class
  * qualified calls       mod.baz(...)        -> `baz` when `mod` is a known local module
Unresolved/builtin calls are ignored. This is intentionally conservative: edges shown are
ones we can attribute with confidence, which is what makes the impact map trustworthy.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

STDLIB = set(getattr(sys, "stdlib_module_names", set()))
_DATA_EXTS = (".csv", ".hdf", ".h5", ".nc", ".zip", ".parquet", ".xlsx", ".xls", ".json",
              ".jsonl", ".tif", ".tiff", ".pdf", ".pptx", ".html", ".txt", ".db", ".sqlite")


def first_line(doc: str | None) -> str:
    for ln in (doc or "").strip().splitlines():
        if ln.strip():
            return ln.strip()
    return ""


def signature(node) -> str:
    try:
        args = ast.unparse(node.args)
    except Exception:
        args = "..."
    ret = ""
    if getattr(node, "returns", None) is not None:
        try:
            ret = f" -> {ast.unparse(node.returns)}"
        except Exception:
            ret = ""
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({args}){ret}"


def arg_names(node) -> list[str]:
    """Flat list of parameter names for fingerprinting (order-sensitive)."""
    a = node.args
    names = [p.arg for p in (a.posonlyargs + a.args)]
    if a.vararg:
        names.append("*" + a.vararg.arg)
    names += [p.arg for p in a.kwonlyargs]
    if a.kwarg:
        names.append("**" + a.kwarg.arg)
    return names


def looks_like_data(s: str) -> bool:
    low = s.lower()
    if low.startswith(("http://", "https://", "s3://", "ftp://", "/vsizip/")):
        return True
    if "data/" in low or "data\\" in low:
        return True
    return low.endswith(_DATA_EXTS)


def import_base(mod: str) -> str:
    return mod.lstrip(".").split(".")[0]


# --------------------------------------------------------------------------- call extraction
def _called_names(fn_node):
    """Yield (kind, payload) for calls inside a function body.

    kind ∈ {"bare","self","qual"}:
      bare  foo()         -> ("bare", "foo")
      self  self.bar()    -> ("self", "bar")
      qual  mod.baz()     -> ("qual", ("mod","baz"))
    """
    for n in ast.walk(fn_node):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Name):
            yield ("bare", f.id)
        elif isinstance(f, ast.Attribute):
            val = f.value
            if isinstance(val, ast.Name) and val.id == "self":
                yield ("self", f.attr)
            elif isinstance(val, ast.Name):
                yield ("qual", (val.id, f.attr))


def scan_python(text: str):
    tree = ast.parse(text)
    doc = first_line(ast.get_docstring(tree))
    imports: list[str] = []
    classes: list[tuple] = []
    functions: list[tuple] = []
    data: set[str] = set()

    # fingerprint pieces + call sites, collected as we walk top-level defs
    fp_funcs: list[str] = []     # "name(param,param)"
    fp_classes: list[str] = []   # "Class.method(param)"
    calls: dict[str, list] = {}  # defining qualname in this file -> list of (kind,payload)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append("." * node.level + (node.module or ""))
        elif isinstance(node, ast.ClassDef):
            methods = []
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not b.name.startswith("_"):
                        methods.append(b.name)
                    qual = f"{node.name}.{b.name}"
                    fp_classes.append(f"{qual}({','.join(arg_names(b))})")
                    calls[qual] = list(_called_names(b))
            classes.append((node.name, methods, first_line(ast.get_docstring(node))))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append((signature(node), first_line(ast.get_docstring(node))))
            fp_funcs.append(f"{node.name}({','.join(arg_names(node))})")
            calls[node.name] = list(_called_names(node))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and looks_like_data(node.value):
            data.add(node.value.strip()[:140])

    # structural fingerprint: sorted signatures + sorted import bases (NOT raw text)
    fp_imports = sorted({import_base(m) for m in imports if import_base(m)})
    sig_blob = "|".join(sorted(fp_funcs) + sorted(fp_classes) + ["imp:" + ",".join(fp_imports)])
    struct_hash = hashlib.sha256(sig_blob.encode("utf-8")).hexdigest()[:16]

    return {"doc": doc, "imports": imports, "classes": classes, "functions": functions,
            "data": sorted(data), "calls": calls,
            "fp": {"struct_hash": struct_hash, "funcs": sorted(fp_funcs),
                   "classes": sorted(fp_classes), "imports": fp_imports}}


def notebook_to_python(text: str) -> str:
    nb = json.loads(text)
    return "\n\n".join("".join(c.get("source", [])) for c in nb.get("cells", [])
                       if c.get("cell_type") == "code")


# --------------------------------------------------------------------------- change classify
def classify_change(prev_fp: dict | None, new_fp: dict, content_hash: str,
                    prev_content_hash: str | None) -> str:
    """NONE / COSMETIC / STRUCTURAL / NEW, comparing signatures not raw bytes."""
    if prev_content_hash is not None and prev_content_hash == content_hash:
        return "NONE"
    if prev_fp is None:
        return "NEW"
    if prev_fp.get("struct_hash") == new_fp.get("struct_hash"):
        return "COSMETIC"   # bytes changed but signatures/imports identical
    return "STRUCTURAL"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--dirs", nargs="+", default=["."])
    ap.add_argument("--out", required=True)
    ap.add_argument("--fingerprints", default=None,
                    help="path to a JSON fingerprint store; enables NONE/COSMETIC/STRUCTURAL "
                         "change classification across runs")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    root = Path(args.root).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    for d in args.dirs:
        base = root / d
        if base.exists():
            files += sorted(base.rglob("*.py")) + sorted(base.rglob("*.ipynb"))
    files = [f for f in files if "__pycache__" not in f.parts and ".ipynb_checkpoints" not in f.parts]

    local_mods = {f.stem for f in files}
    scanned: dict[str, dict] = {}
    content_hashes: dict[str, str] = {}
    for f in files:
        rel = f.relative_to(root).as_posix()
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            content_hashes[rel] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]
            scanned[rel] = scan_python(notebook_to_python(text) if f.suffix == ".ipynb" else text)
        except Exception as e:  # noqa: BLE001
            scanned[rel] = {"error": f"{type(e).__name__}: {e}", "doc": "", "imports": [],
                            "classes": [], "functions": [], "data": [], "calls": {},
                            "fp": {"struct_hash": "", "funcs": [], "classes": [], "imports": []}}

    # ---- import dependency hierarchy ----
    deps: dict[str, set] = {}
    libs: dict[str, set] = {}
    for rel, info in scanned.items():
        stem = Path(rel).stem
        deps.setdefault(stem, set())
        for mod in info["imports"]:
            base = import_base(mod)
            if not base:
                continue
            if base in local_mods and base != stem:
                deps[stem].add(base)
            elif base not in local_mods and base not in STDLIB:
                libs.setdefault(base, set()).add(rel)

    # ---- call graph: resolve calls to known local definitions ----
    func_owner: dict[str, set] = {}     # bare function name -> {file_rel}
    method_owner: dict[str, set] = {}   # method name        -> {file_rel::Class}
    for rel, info in scanned.items():
        if info.get("error"):
            continue
        for q in info["calls"]:
            if "." in q:
                cls, meth = q.split(".", 1)
                method_owner.setdefault(meth, set()).add(f"{rel}::{cls}")
            else:
                func_owner.setdefault(q, set()).add(rel)

    call_edges: dict[str, set] = {}     # caller "file::qual" -> {callee "file::qual"}
    called_by: dict[str, set] = {}
    for rel, info in scanned.items():
        if info.get("error"):
            continue
        local_import_names = {b for b in (import_base(m) for m in info["imports"]) if b in local_mods}
        for caller_q, sites in info["calls"].items():
            caller = f"{rel}::{caller_q}"
            for kind, payload in sites:
                callees: set[str] = set()
                if kind == "bare" and payload in func_owner:
                    callees = {f"{r}::{payload}" for r in func_owner[payload]}
                elif kind == "self":
                    if "." in caller_q:
                        cls = caller_q.split(".", 1)[0]
                        tgt = f"{rel}::{cls}"
                        if payload in method_owner and tgt in method_owner[payload]:
                            callees = {f"{rel}::{cls}.{payload}"}
                    if not callees and payload in method_owner:
                        callees = {f"{o.split('::')[0]}::{o.split('::')[1]}.{payload}"
                                   for o in method_owner[payload]}
                elif kind == "qual":
                    modname, fn = payload
                    if modname in local_import_names and fn in func_owner:
                        callees = {f"{r}::{fn}" for r in func_owner[fn] if Path(r).stem == modname}
                        if not callees and fn in func_owner:
                            callees = {f"{r}::{fn}" for r in func_owner[fn]}
                for c in callees:
                    if c == caller:
                        continue
                    call_edges.setdefault(caller, set()).add(c)
                    called_by.setdefault(c, set()).add(caller)

    # ---- fingerprint change classification (optional) ----
    fp_report: dict[str, str] = {}
    if args.fingerprints:
        fp_path = Path(args.fingerprints)
        prev_store = {"files": {}}
        if fp_path.exists():
            try:
                prev_store = json.loads(fp_path.read_text(encoding="utf-8"))
            except Exception:
                prev_store = {"files": {}}
        new_store = {"files": {}}
        for rel, info in scanned.items():
            prev = prev_store.get("files", {}).get(rel)
            prev_fp = prev.get("fp") if prev else None
            prev_ch = prev.get("content_hash") if prev else None
            fp_report[rel] = classify_change(prev_fp, info["fp"], content_hashes.get(rel, ""), prev_ch)
            new_store["files"][rel] = {"content_hash": content_hashes.get(rel, ""), "fp": info["fp"]}
        for rel in prev_store.get("files", {}):
            if rel not in scanned:
                fp_report[rel] = "DELETED"
        fp_path.write_text(json.dumps(new_store, indent=2, ensure_ascii=False), encoding="utf-8")

    # ===================================================================== render markdown
    L: list[str] = ["# Code map (auto-generated)\n",
                    "> Generated by `scan_code.py` (static analysis). Regenerate when the code changes.\n",
                    "## Code directory tree\n", "```text"]
    L += [f.relative_to(root).as_posix() for f in files]
    L.append("```\n")

    L.append("## Module dependency hierarchy (local imports)\n")
    for stem in sorted(deps):
        ds = sorted(deps[stem])
        L.append(f"- `{stem}` → " + (", ".join(f"`{x}`" for x in ds) if ds else "(no local imports)"))
    L.append("")
    rev: dict[str, set] = {}
    for stem, ds in deps.items():
        for d in ds:
            rev.setdefault(d, set()).add(stem)
    if rev:
        L.append("Imported-by (reverse):\n")
        for stem in sorted(rev):
            L.append(f"- `{stem}` ← " + ", ".join(f"`{x}`" for x in sorted(rev[stem])))
        L.append("")

    # ---- call graph section ----
    L.append("## Function call graph (resolved local calls)\n")
    if call_edges:
        L.append("Calls (caller → callee):\n")
        for caller in sorted(call_edges):
            L.append(f"- `{caller}` → " + ", ".join(f"`{c}`" for c in sorted(call_edges[caller])))
        L.append("")
        L.append("Called-by (reverse — **impact map**: who breaks if you change the callee):\n")
        for callee in sorted(called_by):
            L.append(f"- `{callee}` ← " + ", ".join(f"`{c}`" for c in sorted(called_by[callee])))
        L.append("")
    else:
        L.append("_No local function-call edges resolved._\n")

    L.append("## Third-party libraries used\n")
    for lib in sorted(libs):
        L.append(f"- **{lib}** — " + ", ".join(sorted(libs[lib])))
    L.append("")

    # ---- fingerprint / change-classification section ----
    if args.fingerprints:
        L.append("## Structural fingerprints & change classification\n")
        L.append("Per file: a `struct_hash` over signatures (function params, class methods, "
                 "import bases) — not raw bytes. Change level vs the previous run:\n")
        order = {"STRUCTURAL": 0, "NEW": 1, "COSMETIC": 2, "DELETED": 3, "NONE": 4}
        for rel in sorted(fp_report, key=lambda r: (order.get(fp_report[r], 9), r)):
            level = fp_report[rel]
            sh = scanned.get(rel, {}).get("fp", {}).get("struct_hash", "")
            L.append(f"- `{rel}` — **{level}**" + (f"  `{sh}`" if sh else ""))
        L.append("")
        L.append("> STRUCTURAL = signatures/imports changed (re-index this file and its "
                 "callers). COSMETIC = bytes changed but signatures identical (safe to skip "
                 "re-analysis). NONE = identical. NEW / DELETED as named.\n")

    L.append("## File catalogue\n")
    for rel, info in scanned.items():
        L.append(f"### {rel}\n")
        if info.get("error"):
            L.append(f"*parse error: {info['error']}*\n")
            continue
        if info["doc"]:
            L.append(f"_{info['doc']}_\n")
        stem = Path(rel).stem
        thirdp = sorted({import_base(m) for m in info["imports"]
                         if import_base(m) and import_base(m) not in STDLIB and import_base(m) not in local_mods})
        loc = sorted({import_base(m) for m in info["imports"] if import_base(m) in local_mods and import_base(m) != stem})
        std = sorted({import_base(m) for m in info["imports"] if import_base(m) in STDLIB})
        L.append(f"**Imports** — third-party: {', '.join(thirdp) or '—'} · "
                 f"local: {', '.join(loc) or '—'} · stdlib: {', '.join(std) or '—'}\n")
        if info["classes"]:
            L.append("**Classes:**")
            for name, methods, doc in info["classes"]:
                ms = f" (methods: {', '.join(methods)})" if methods else ""
                L.append(f"- `{name}`{ms}" + (f" — {doc}" if doc else ""))
            L.append("")
        if info["functions"]:
            L.append("**Functions:**")
            for sigtext, doc in info["functions"]:
                L.append(f"- `{sigtext}`" + (f" — {doc}" if doc else ""))
            L.append("")
        if info["data"]:
            L.append("**Data sources / paths referenced:**")
            L += [f"- `{d}`" for d in info["data"]]
            L.append("")

    out.write_text("\n".join(L), encoding="utf-8")
    n_edges = sum(len(v) for v in call_edges.values())
    print(f"scanned {len(files)} files | local modules {len(local_mods)} | "
          f"third-party libs {len(libs)} | call edges {n_edges}")
    if args.fingerprints:
        from collections import Counter
        c = Counter(fp_report.values())
        print("change levels: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
