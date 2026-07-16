# Rationale — THE PRECISION INSTRUMENT

## Why this direction serves the north star

**The north star is a consultant's deliverable that a client's risk committee
will read, plus a lab the client's own analysts will poke at.** Both halves
of that audience are practitioners who already read regulatory/quant
artifacts for a living — Basel disclosures, model validation reports, rating
agency criteria decks. Those documents share a visual grammar: hairlines,
dense tabular figures, units spelled out, nothing decorative. This direction
borrows that grammar on purpose, so the app reads as *one more instrument
this audience already trusts*, not a generic analytics SaaS dashboard that
happens to contain IFRS 9 numbers. The operator judged the prior pass
underwhelming twice; "underwhelming" for this audience usually means "looks
like a demo," and the fastest way out of that is to stop looking like a
demo's visual vocabulary (soft shadows, rounded cards, friendly color) and
start looking like the vocabulary of the documents this audience already
signs off on.

**Every structural device in this direction is a direct expression of "never
a hallucinated number," not just a style choice.** The provenance stamp
(`SOURCE · /api/ecl/summary`) on every panel header, the `⟨ ASK AI ⟩` chip
that only ever appears beside that stamp, the chat dock's `GROUNDED` /
`THINKING` / `OUT OF SCOPE` status word tied to `/api/agent/ask`'s actual
governance states — these turn the north star's anti-hallucination promise
into something the reader can *see* on every panel, not something they have
to take on faith from a README. That is the strongest way this direction
argues for itself: the aesthetic and the governance story are the same
artifact, not aesthetic-then-a-separate-trust-argument.

**The waterfall's explicit no-fake-scale rule is a trust-building move,
not a compromise.** This book's real roll-forward spans ~2.6 orders of
magnitude (derecognitions −$21.2m vs. new loans +$999.4m); a chart that
quietly rescaled or log-transformed to make the small components look
punchier would be lying by omission to exactly the audience most likely to
notice and mark it down for it. Rendering it honestly — tiny floored bars,
a towering new-loans bar, a footnote that says so in plain words — is what
a genuinely rigorous instrument does, and it's a more defensible artifact to
hand a risk committee than a chart that's been "designed" into looking calmer
than the data is.

**Density serves the lab half of the north star directly.** Self-serve
scenario experiments mean a user will be scanning multiple scenario rows,
multiple stage splits, multiple shock deltas in one sitting, often
cross-referencing a stat tile against a table row. Tabular alignment
(the deliberate `tabular-nums`-everywhere call, documented as a departure
from the dataviz skill's default figure guidance) is what lets someone's eye
walk down a column of numbers and compare magnitudes without re-parsing each
one — exactly the operation a scenario lab asks of its user, far more often
than it asks for a single hero number to be admired in isolation.

**Both themes get equal seriousness because the audience genuinely uses
both.** Risk/model-validation analysts run long sessions and frequently
prefer dark terminals; a consultant presenting live in a lit conference room
needs light mode to project cleanly. Validating the categorical order
separately in each mode (§1 of `design_spec.md`) rather than auto-inverting
one from the other means neither mode is the "real" one and the other an
afterthought — which matches how this audience will actually deploy it.

## Where it risks failing

**Coldness for a non-quant reader.** The instrument look optimizes for
practitioners. If the actual reader on the client side is a board member or
a generalist executive rather than a risk analyst, hairline-everywhere,
all-caps micro-labels, and a raw endpoint string in every panel header can
read as *hard to parse* rather than *precise* — the opposite of the
intended effect. The mitigation already in the mock is the plain-language
narrative panel and the `⟨ ASK AI ⟩` disclosure as a translation layer, but
that only works if whoever ships this keeps that panel prominent rather than
treating it as filler beneath the "real" instrument panels — it's easy to
let the prose panel shrink over time as more tiles/tables get added.

**The tabular-nums-everywhere call is a named deviation from the dataviz
skill's own figure guidance, and it can rot.** The skill recommends
proportional figures for a standalone hero/stat-tile number specifically
because tabular spacing looks loose past a handful of digits. This spec caps
stat-tile values at roughly 7 characters to keep that cost invisible today
(`34.0`, `2.03`, `1.035`, `2015Q1`). That constraint is not self-enforcing —
the first time someone adds a stat tile for a longer or more volatile number
(a raw dollar figure without the `m`/`bn` suffix, say), the same treatment
will look ragged, and nothing in the CSS stops that from shipping unless
whoever extends this system re-reads this callout first.

**Zero decoration is a discipline with no slack built in.** No shadow, no
gradient, one reserved accent hue, restrained categorical use — this reads
as rigorous today because it's applied uniformly. The first time a future
requirement wants something to visually "pop" (a promo, an upsell nudge, an
urgent one-off callout) there is no low-risk pattern already living in this
system to reach for, and the path of least resistance is a shadow-and-card
component that doesn't match anything else — which is exactly how the prior,
"underwhelming" look likely accreted in the first place. This direction is
only as good as the next several PRs' willingness to stay inside its
vocabulary (hairline, ink, one accent, status four) instead of borrowing a
generic component from elsewhere.

**All-caps micro-labels at 10–13px trade legibility for density.** Small
all-caps text is measurably harder to read at speed than sentence case,
especially for longer labels or non-native-English readers; this direction
uses it pervasively (tile labels, column headers, tab labels, the AI chip,
provenance stamps) because that repetition is part of what reads as
"instrument." The spec's letter-spacing and minimum-size floor keep it from
getting worse, but it doesn't remove the underlying legibility cost — worth
watching in real usage, not just assuming it's fine because it looks sharp
in a screenshot.

**Raw endpoint strings in the provenance stamp are honest but can read as
noise to a non-technical client user.** `/api/ecl/waterfall?t0=20&t1=40` is
exactly right for a technical reviewer and slightly odd for someone who
doesn't know what a query parameter is. If client feedback says this reads
as clutter rather than rigor, the fix is a friendlier plain-English caption
with the raw endpoint demoted to a tooltip/expand — not dropping the
provenance concept itself, which is too central to the north star to cut.

**The waterfall's honesty has a real interpretability cost.** Flooring the
three sub-threshold components (stage migration, remeasurement,
derecognitions) to the same visible height, because their true heights all
sit under the legibility floor at this scale, makes them look
*approximately equal* to a fast skim even though remeasurement (+$26.0m) is
nearly 7× stage migration (+$3.9m). The direct labels correct this for
anyone who reads them, but a glance-only reader can walk away with the wrong
relative-magnitude impression. If this exhibit becomes one consultants lean
on often, a companion small-multiple ("the three small components, own
scale") is a stronger fix than continuing to widen the floor.

**This exploration surfaced a real bug in the shipped palette that it does
not fix.** `app/ui/src/palette.js`'s current categorical order (`blue, aqua,
yellow, green, violet, red, magenta, orange`) fails the dataviz validator's
hard normal-vision floor (worst adjacent pair ΔE 12.9, below the 15 floor) —
confirmed by running `validate_palette.js` against that exact order (see
`design_spec.md` §1). This design spec uses the order that actually passes.
If this direction is adopted into the real app without also correcting
`palette.js`'s slot order, the shipped app keeps the failing order while
every document in this exploration assumes the passing one — that
correction is a prerequisite, not an assumption this design gets to make on
the app's behalf.

**A concrete engineering trap this mock caught, worth carrying forward
literally:** a `position: fixed` chat dock that renders its full transcript
open by default will, at ordinary viewport heights, sit on top of whatever
real content happens to occupy that screen corner at max scroll — in this
build's first pass, it silently covered the "down" scenario's coverage and
UER-peak figures. The fix used here — collapse to a small pill by default,
expand only on an explicit click, and reserve generous bottom page padding
so the fixed corner never rests over data even when collapsed — needs to
travel with this direction if it's implemented for real, not just exist in
this static mock. (Verified with a headless-browser scroll-to-bottom check,
not just eyeballed — see the QA note in this session's tool history if
reproducing.)
