# Rationale — The Modern Risk Platform

## Why this direction serves the north star

**The product's job is "consultant's deliverable + client's lab."** Both
halves of that sentence are load-bearing, and this direction was built to
answer each literally rather than decoratively:

- **"Consultant's deliverable"** means the first screen has to survive
  being screen-shared to a bank's Head of Credit Risk without an
  apologetic "ignore the placeholder styling." A crisp fintech dashboard —
  one accent, tight type hierarchy, hairline borders instead of shadows-on-
  shadows — reads as the same visual register as the tools that audience
  already trusts (risk platforms, trading terminals, the Stripe/Linear
  school of dense-but-calm SaaS). It does not read as a student project or
  a chatbot demo with charts bolted on. The KPI row leads with the four
  numbers a credit committee actually asks for first (allowance, coverage,
  Jensen gap, population) — not a hero illustration.
- **"Client's lab"** means the same screen has to invite poking at
  scenarios, not just admire them. The scenario table's Δ-vs-base pills
  and the waterfall's "adds/reduces" legend are both small nudges toward
  "what if" thinking — they show *why* a number moved before the client
  has even asked the agent, which lowers the activation energy for asking
  the harder follow-up question.
- **"Agent front-and-centre, data-grounded, never hallucinated."** This is
  where the direction does the most work, and it's the part I'd defend
  hardest in a design review. Three concrete decisions carry it:
  1. The AI-explain icon is **on every panel and every stat tile**, not
     tucked into a hamburger menu — the agent is positioned as commentary
     on *this specific number*, not a general-purpose sidebar.
  2. Every canned answer in `preview.html` is built from **numbers already
     in `docs/api_contract.md`'s own worked examples** — the Jensen
     explanation literally states `$34.0m` vs `$32.9m` = 1.035x using the
     `allowance_at_average_path` field that ships in the contract today.
     Nothing is invented to make the mock look smart. When this becomes
     real, that's exactly the discipline `/api/agent/ask` already enforces
     (Tier-1/2/3 routing, refusal-over-guessing) — the UI is just making
     that discipline *visible* via the citation chip, not introducing it.
  3. The **citation chip** (`⚙ decompose_waterfall(t0=20, t1=40)`) is the
     single most important pixel in this file. A client who has been
     burned by a hallucinating chatbot before will look for exactly this —
     proof the sentence they're reading came from a tool call, not a
     guess. Putting it in every agent surface, styled identically whether
     the answer is a stat-tile aside or a full chat reply, trains the eye
     that "this app always shows its work."
- **Refusal as a feature, not a failure** (§4.5) matters more here than in
  a generic dashboard: an IFRS 9 tool that visibly *can't* be tricked into
  answering outside its remit is a stronger trust signal to a risk
  committee than one that always has an answer. Styling refusal in the
  same neutral gray as a normal agent message (never `--critical`) was a
  deliberate choice to avoid teaching users that asking a boundary
  question is an error on their part.
- **Dark-first** matches how this artifact will actually be used — a
  consultant driving a laptop in a dim conference room or presenting on a
  shared screen where a blazing-white dashboard is the thing everyone
  complains about. The light variant is not an afterthought (every hex
  above was picked and contrast-checked for light first, then dark — see
  `design_spec.md` §1.3.1) but dark is the one that gets the demo.

## Where it risks failing

I'd rather flag these now than have them surface as "wait, why does this
look off" in a later review.

1. **Blue means two different things on the same screen, and that's a real
   tension, not just a nitpick.** The single saturated accent (`--accent`)
   drives buttons, links, the active tab, and focus rings — i.e. "the
   brand, the primary, the confident thing to click." The waterfall chart
   reuses the *same* blue for "this component increased the allowance."
   For allowance, an increase is not good news — it's more provision,
   which is prudentially conservative but capital-costly. A client who has
   internalized "blue = go/good" from the buttons all page could
   subconsciously read the waterfall's blue bars the same way. The
   mitigation in the spec (never label direction with color alone — every
   bar carries a signed number, and the legend says "adds to / reduces,"
   never "increase/decrease" or "good/bad") should hold, but it's worth
   watching in a real usability pass, and it's the one place I'd consider
   a deliberate palette *exception* if a reviewer pushes back — e.g.
   swapping the waterfall's increase color to violet (categorical slot 7,
   validated, not otherwise used in this UI) to fully decouple it from the
   button/link accent. I didn't make that swap here because it would
   spend a second hue on a job blue already does correctly per the
   dataviz reference palette's own diverging pair, and because "adds/
   reduces" language does most of the disambiguation work already — but a
   real client session is the actual test, not my judgment call.
2. **The t=20→t=40 waterfall window is a rhetorical accident, not a
   considered choice, and it's extreme.** I used the exact worked example
   from `docs/api_contract.md` because the brief asked for the real
   published numbers — but `new_loans` at +$999.4m against a `stage_
   migration` of +$3.9m is a 250:1 ratio, driven by the fact that this
   window spans 2005Q1→2010Q1, during which the book grew roughly 60%
   (8,662 → 13,863 loans) on top of ordinary quarter-over-quarter
   remeasurement noise. That's a legitimate data point, but it is not what
   a credit committee usually wants from "the allowance bridge" — they
   typically want the *most recent* quarter's movement (something like
   t=59→t=60), which would show remeasurement, migration, and
   derecognition at comparable, readable magnitudes with no flooring
   needed at all. Shipping the long-window example as the *default* view
   would be a mistake — it should be a) a specific, clearly labeled
   drill-down ("cumulative movement since 2005"), with b) the default
   Executive-tab waterfall instead defaulting to the latest single-quarter
   window, where the minimum-segment-height rule in §5.2 is unlikely to
   ever trigger. I flagged the flooring/disclosure mechanism precisely
   *because* I anticipated this data would ship looking like this if the
   default window isn't reconsidered — the visual trick papers over a
   presentation-window choice, it doesn't fix it.
3. **Status color on the scenario table quietly assumes "lower allowance
   is good."** That's true from a pure capital/earnings-volatility lens,
   but a policy reviewer, an auditor, or a regulator might read "up
   scenario = green" as the model being incentivized to look optimistic —
   IFRS 9 explicitly worries about under-provisioning. The color choice is
   defensible (it's describing dispersion around a base case, not
   endorsing optimism) but it's exactly the kind of thing a Big-4 reviewer
   would ask about in a walkthrough, and the honest answer has to be "this
   is the range of outcomes, colored by direction, not a recommendation" —
   worth a line in the real client-facing copy, not just this rationale.
4. **One accent, one hue family, everywhere is a legibility win and a
   monotony risk.** With only blue as the "alive" color against a mostly
   achromatic dark shell, a screen with many simultaneous states (several
   AI-explain answers open, several table-view toggles active) starts to
   look uniformly blue-flecked rather than drawing the eye to what's
   actually new. The categorical palette (8 hues) exists precisely for
   when the Model/Policy tabs need to tell distinct series apart — I did
   not reach for it here because the Executive tab has no multi-series
   identity job today, but if a future Executive-tab widget *does* need
   more than one "kind" of highlight, this direction's discipline (only
   ever one saturated accent for UI chrome) will start to chafe, and the
   honest fix is "pull from categorical slot 2+ for that one widget," not
   "add a second accent."
5. **Contrast math was done for the states shown; it wasn't fuzzed across
   every possible state.** The 4.5:1/3:1 checks in `design_spec.md` §1.3.1
   cover the specific pairs this mock actually uses (button fills, delta
   pills, level-bar labels). A real implementation with more color
   combinations (e.g. a warning-status stat tile, a serious-status
   sparkline) needs the same contrast(a,b) check run against *that*
   specific pairing before shipping — the discipline generalizes, the
   numbers don't.
6. **The chat dock's `position: fixed` placement needs a real scroll-
   container test, not just a Playwright full-page screenshot.** (It
   checks out on an actual scrolled viewport — verified during this pass —
   but a fixed dock at the corner of a *taller* Executive tab, once Model/
   Policy tab content is added, deserves a fresh look for any dense table
   whose last rows might sit under it.)
