# Schema — pages, frontmatter grammar, edges, naming

This is the contract between you (the compiling LLM) and the scripts. The
frontmatter parser is deliberately small; anything outside this grammar is
**reported on stderr and ignored**, never guessed at.

## Page types

| type       | one page per...                | typical sources            |
|------------|--------------------------------|----------------------------|
| `concept`  | idea/policy/algorithm/term     | specs, papers, notes       |
| `module`   | code unit (package/file/service)| the code files themselves |
| `entity`   | external thing (API, vendor, dataset, person/team) | docs |
| `decision` | a call that constrains the future | discussion + wiki_log    |
| `question` | an open unknown being tracked  | —                          |
| `source`   | a raw document worth its own page (a big PDF, a case) | it |
| `session`  | (rare) a narrative writeup of one working session | —   |

`index.md` is special: the **catalog**. Every page gets one line — a
`[[wikilink]]` plus a one-line summary — grouped by category, updated on
every ingest. It is the first thing read by a fresh session AND at query
time (read the index, pick pages, drill in — this is what replaces
embedding-RAG at wiki scale). The audit warns about pages missing from it.

## Frontmatter grammar (the exact subset the parser accepts)

```yaml
---
title: Discount Engine            # REQUIRED, scalar
type: module                      # REQUIRED, one of the table above
status: active                    # draft | active | superseded
aliases: [discounts, disc-engine] # inline list...
tags:                             # ...or dash list — both fine
  - pricing
  - core
sources:                          # provenance: files this page compiles.
  - ../docs/pricing_spec.md#3     #   optional #anchor (page/section/slide)
  - ../src/discount.py
code: [../src/discount.py]        # code files (audited for staleness too)
links:                            # typed edges. ONE nested level only.
  uses: [Pricing Engine]          #   inline list form
  implements:                     #   or dash-list form
    - Discount Policy
  relates: [Tax Engine]
---
```

Rules the parser enforces (violations are reported, not guessed):

- Keys are `[A-Za-z_][\w-]*` followed by `:`. Unknown keys are kept in the
  node but only the ones above mean anything.
- Values: scalar, inline `[a, b, c]`, or an indented `- item` dash list.
- `links:` is the only key with a nested level: `edge-type: [targets]` or a
  dash list under the edge type. Deeper nesting is not parsed.
- No multi-line strings, no `key: |` blocks, no anchors/references. If a
  value needs prose, it belongs in the body.
- Paths in `sources:`/`code:` are relative to the **wiki directory** (so
  `../src/...` from `<project>/wiki/`). A trailing `#anchor` is stripped for
  existence/hash checks but kept for humans.

## Links and edges

- **Typed edges** come from `links:` in frontmatter. Edge-type names are
  free-form; the conventional set (use these unless you have a reason):
  `uses`, `used-by`, `implements`, `implemented-by`, `relates`, `part-of`,
  `supersedes`, `answers`, `derived-from`, `contrasts`.
- **Body wikilinks** `[[Target]]`, `[[Target#Heading]]`, `[[Target|label]]`
  become edges of type `mentions` (weighted lower at query time: 0.4 vs 0.6).
- Targets resolve **case-insensitively** against every page's title, its
  aliases, and its filename slug — `[[pricing engine]]`, `[[Pricing
  Engine]]`, and `[[pricing-engine]]` all hit the same page. Unresolvable
  targets land in `graph.json → unresolved` and the audit flags them as
  errors: fix the typo or create the page.
- Wikilinks inside fenced ``` code blocks are ignored (masked before scan).
- Self-links are dropped; duplicate (src, dst, type) triples are deduped.

## Naming

- Filename = slug of the title: `pages/discount-engine.md` for
  "Discount Engine" (`[a-z0-9-]`, no spaces). The node id IS the file stem's
  slug, so renaming a file renames the node.
- One page per stable thing. If a page needs a plural title, it's probably
  two pages.
- Prefer aliasing over duplicating: if people say both "SKU pricing" and
  "price book", one page with an alias, not two pages.

## Memory files (outside the graph, on purpose)

Append-only, one `##`-dated entry each time, written via `wiki_log.py`:

```
## 2026-07-04 09:12 UTC — tags: pricing

Compiled discount-rules from src/discount.py; open question filed on FX order.
```

- `log.md` — what happened, what's next. The tail of this file + `index.md`
  is the whole new-session state restore. The dated `## ` headers make it
  greppable: `grep "^## " memory/log.md | tail -5` shows the last five
  entries without reading the file.
- `decisions.md` — calls that constrain future work. If a decision is big,
  ALSO give it a `decision` page so it enters the graph.
- `questions.md` — open unknowns; strike through with a pointer when
  answered.

## Generated artifacts (never hand-edit)

- `.wiki/graph.json` — nodes, edges, unresolved, duplicates, title index.
- `.wiki/source_manifest.json` — `{key: sha256[:16]}` recorded at the last
  `--update-manifest`; staleness is measured against it.
- `.wiki/audit.json` — the latest audit's findings, machine-readable.

## Layer 0 — raw sources are IMMUTABLE

The wiki is a *derived* artifact. The files it compiles from — whatever
`source_roots` points at, a `raw/` folder of clipped articles, a pageindex-plus
corpus, the repo's own `src/` — are the source of truth: **read them, never
modify them.** Everything in the wiki can be re-derived from them; nothing in
them should ever depend on the wiki. For document corpora, the convention is a
`raw/` directory next to the wiki (Obsidian Web Clipper drops web articles
there as markdown); for code, the repo itself is the raw layer and obviously
isn't quarantined — the immutability rule then means the *wiki work* never
edits code as a side effect of compiling.

## Viewing the wiki (Obsidian)

The page format here — markdown, `[[wikilinks]]`, YAML frontmatter — is
deliberately Obsidian-native. Open the wiki directory as a vault: the graph
view shows hubs and orphans at a glance (it is the visual twin of
`graph.json`), backlinks come free, and the Dataview plugin can query the
frontmatter (`tags`, `type`, `status`) into live tables. Two practical notes:
LLMs can't read markdown with inline images in one pass — read the text first,
then view referenced images separately; and the wiki is just files, so keeping
it in git gives version history and team sharing for free.
