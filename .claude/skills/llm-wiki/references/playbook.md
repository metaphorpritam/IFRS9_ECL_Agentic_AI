# Playbook — the loops that make the wiki compound

Four loops. The scripts do the deterministic bookkeeping; the judgment calls
(what deserves a page, what a page should say) are yours.

## 1. The compile loop (per source)

For each source file (a spec, a deck's corpus .md, a code module):

1. **Confirm identity** — read the first page/slide/docstring. Filenames lie.
2. **Decide the touched pages.** A source rarely maps 1:1 to a page; a spec
   might update one `concept` and two `module` pages. Ask "what stable thing
   did I just learn about?" — that thing's page is what you edit.
3. **Update, don't append.** Revise the page as if it had always known this.
   No "Update 2026-07:" paragraphs — history lives in git and `memory/log.md`.
4. **Record provenance**: add the file (with `#anchor` for the section/slide)
   to `sources:` (docs) or `code:` (code).
5. **Cross-link while it's cheap.** Every named thing the page discusses that
   has (or deserves) a page gets a `[[wikilink]]` or a typed edge. If the
   target doesn't exist yet, link anyway — the unresolved report is your
   TODO list of pages to create.
6. **Update `index.md`** for every page created *or meaningfully changed*:
   a `[[wikilink]]` + one-line summary under the right category. This is
   not optional bookkeeping — the index is what query-time navigation
   reads first, and the audit flags pages missing from it.

After the session: `wiki_graph.py` → fix unresolved → `wiki_audit.py
--update-manifest` → `wiki_log.py ... log "..."`.

Per-project conventions (page types you invented, domain naming rules,
your preferred ingest granularity) belong in a `Conventions` section of
`index.md` — co-evolve it with the user the way the original pattern
co-evolves its CLAUDE.md schema. This skill's `schema.md` is the parser
contract; the wiki's own conventions are yours to grow.

### Worked example

Source: `docs/pricing_spec.md` §3 says discounts apply before tax, and
`src/discount.py` implements it. Two pages:

```markdown
--- pages/discount-rules.md ---
---
title: Discount Rules
type: module
status: active
tags: [pricing]
sources: [../docs/pricing_spec.md#3]
code: [../src/discount.py]
links:
  uses: [Pricing Engine]
  implements: [Discount Policy]
---

# Discount Rules

Applies tiered discounts to a priced order **before tax** (spec §3;
see [[Tax Engine]] for ordering). Tiers come from `TIERS` in
`discount.py`; percentage discounts round half-up (see decision
2026-07-04 in memory/decisions.md).

## Order of operations

base price → tier discount → [[Tax Engine|tax]] → total
```

`[[Tax Engine]]` doesn't exist yet — good: the graph run will list it under
unresolved, which is exactly the signal to compile that page next.

## 2. The code loop

For a repo, don't re-derive structure by reading files ad hoc:

1. Run pageindex-plus's `scan_code.py --root <repo> ... --fingerprints
   code_fp.json` — it emits a resolved call graph + reverse "called-by"
   impact map.
2. Compile one `module` page per meaningful unit (package or busy file, not
   every file). The call graph tells you the `uses:` edges for free; the
   impact map tells you what `used-by` should say.
3. Put the actual file paths in `code:` so the audit's hash check flags the
   page the moment the code drifts.
4. On later runs, the fingerprint file classifies changes NONE / COSMETIC /
   STRUCTURAL — only STRUCTURAL changes need a real re-compile; for COSMETIC,
   re-hash the manifest and move on.

## 3. The query loop

```bash
python SKILL_DIR/scripts/wiki_query.py wiki "why is tax applied after discounts?" --explain
```

1. Read the listed pages **top-down**; the `--explain` lines tell you why
   each is there (lexical hits vs graph proximity) — trust but verify.
2. Answer citing `pages/discount-rules.md#Order of operations`-style anchors.
   If the answer needed anything NOT in the wiki, that gap is a finding.
3. **File it back** (this is the compounding step):
   - a synthesis worth keeping (a comparison, an analysis, a connection
     you discovered) → make it a **new page** with its own frontmatter and
     index entry — good answers are pages, not chat history. Non-markdown
     outputs (a Marp deck, a matplotlib chart) live in an `outputs/`
     folder with a small wiki page pointing at them;
   - answer belongs on an existing page → edit that page;
   - it's a judgment call → `wiki_log.py wiki decision "..."` (+ a `decision`
     page if it constrains architecture);
   - still open → `wiki_log.py wiki question "..."`.
4. Re-run `wiki_graph.py` if pages changed.

If the query returns nothing useful twice for the same topic, stop querying
and compile the missing page — retrieval can't find what was never written.

## 4. The audit loop (and what each finding means)

Run `wiki_audit.py wiki` at session end; `--strict` in CI-ish contexts.

| finding | it means | the fix |
|---|---|---|
| broken_links | typo, or a page that wants to exist | fix spelling / compile the page (or park it: `wiki_log.py ... question`) |
| stale_pages | source changed since manifest | re-read just that source, revise the page, `--update-manifest` |
| missing_sources | provenance path gone | file moved/renamed → fix `sources:`; deleted → decide if the page is now historical (`status: superseded`) |
| unhashed_sources | never declared current | run `--update-manifest` after verifying the page matches the source |
| orphans | page nothing links to | link it from `index.md` or a related page — or it didn't deserve a page |
| uncovered_sources | files under the roots no page cites | triage: compile, or consciously ignore (narrow the roots/globs if noise) |
| todos | your own markers | do them or convert to `questions.md` entries |
| duplicates | two pages claim one title/alias | merge, or de-alias the loser |

### The semantic lint pass (you, not the script)

The script audits structure; it cannot read meaning. Periodically (every few
compile sessions, or when the audit is clean but something feels off), run an
LLM lint pass over the pages themselves, looking for exactly these:

- **Contradictions between pages** — two pages asserting incompatible claims.
- **Superseded claims** — statements a newer source has overtaken but the page
  still asserts as current (hash-staleness catches changed *files*, not
  changed *truth* across sources).
- **Concepts mentioned but lacking a page** — beyond unresolved links: things
  discussed in prose that deserve their own node.
- **Missing cross-references** — pages that obviously relate but don't link.
- **Data gaps fillable with a web search** — and note the source when filled.

File every finding: fix the page, create the missing page, or record it via
`wiki_log.py wiki question "..."`. Log the lint pass itself. This is the half
of wiki health the deterministic audit can never do — skipping it is how a
structurally-clean wiki still rots semantically.

Never "fix" an audit by deleting the check's inputs (e.g. dropping
`sources:` to silence staleness) — that converts a visible gap into a silent
one, which is the exact failure mode this whole system exists to kill.

## The combined pipeline (docs + code) — pageindex-plus & scan_code

For a project with both code and reference documents (data dictionary,
academic papers, problem/case docs, past solutions), run three layers:

1. **Docs → corpus.** pageindex-plus `ingest_notes.py <docs> <corpus>`
   extracts text + figures from PDFs/PPTX/XLSX/MD into per-document markdown
   with page/slide/sheet anchors. This is Layer 0 for documents.
2. **Code → map.** pageindex-plus `scan_code.py --root <repo> --fingerprints
   code_fp.json` emits the resolved call graph + reverse impact map. The repo
   itself is Layer 0 for code.
3. **Compile the wiki from both.**
   - Doc-derived pages cite the **corpus** files:
     `sources: [../corpus/deck.pptx.md#Slide 12]`. Staleness then *chains*:
     the original changes → re-ingest rewrites the corpus .md → its hash
     changes → the audit flags exactly this page. Keep the original filename
     in the prose for humans.
   - Code pages cite the real files: `code: [../src/discount.py]`; take the
     `uses:` edges from the call graph instead of re-deriving them.
   - One wiki holds both: `module` pages for code; `concept`/`entity`/
     `source` pages for the data dictionary, each paper, the problem
     statement; past solutions become `decision` pages.
   - **Agent-generated artifacts count too**: plan documents (Claude Code
     plan-mode output, design docs), `CLAUDE.md`/`AGENTS.md`, and session
     handoffs. They differ from external sources in one respect — they are
     *mutable working documents*, not immutable raw truth — but they are
     tracked with the same machinery:
     - `CLAUDE.md` gets a small `source` page with `sources: [../CLAUDE.md]`.
       It is the project's schema layer, so the audit's hash check now flags
       convention drift the moment anyone edits it.
     - Each plan gets a `decision` (or `source`) page citing the plan file;
       when the plan is executed or overtaken, set `status: superseded` and
       link what replaced it. Put the plans directory under `source_roots`
       so unmapped plans surface in `uncovered_sources`.
     - Plan-vs-reality divergence (the plan says X, the code does Y) is a
       prime semantic-lint target — the hash check sees file edits, not
       broken promises.
4. **Outputs.** Typeset HTML study notes render from the *corpus* via
   html-notes-academic (see pageindex-plus's `html_notes_build.md`); the wiki
   is the memory and reasoning layer, not the typeset artifact. A wiki page
   that summarises a built HTML note lists that note under `sources:` too.

## Memory discipline

- Log **every** session, even 2-line ones — the log is what makes a 3-week
  gap or a compacted context recoverable in one read.
- Decisions get logged when made, not when remembered.
- The recovery read order is always: `index.md` → tail of `memory/log.md` →
  `.wiki/audit.json` counts. If that's not enough to resume, the last log
  entry was too thin — write better ones.
