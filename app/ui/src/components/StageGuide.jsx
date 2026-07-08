/** Stage -> ECL horizon guide, shared by the waterfall panel and Policy tab. */
export default function StageGuide() {
  return (
    <details class="stage-guide">
      <summary>What do the stages and horizons mean?</summary>
      <ul>
        <li>
          <b>Stage 1 — performing</b> (no significant deterioration since
          origination): allowance = <b>12-month ECL</b> — expected loss from
          defaults possible in the <i>next 4 quarters</i> only:
          Σ S(t−1)·λ<sub>t</sub>·LGD<sub>t</sub>·EAD<sub>t</sub>·(1+EIR)<sup>−t</sup>, t ≤ 4.
        </li>
        <li>
          <b>Stage 2 — significant increase in credit risk</b> (lifetime PD now
          &gt; 2× its at-origination level + 0.5pp add-on): the same sum over the
          <b> full remaining contractual life</b> (up to 40 quarters here) —
          same loan, longer horizon, bigger allowance.
        </li>
        <li>
          <b>Stage 3 — credit-impaired</b> (defaulted): lifetime ECL collapses
          to LGD × current exposure — scenario-invariant by construction.
        </li>
      </ul>
      <p>
        The stage decides the <i>horizon</i>; the engine always computes both
        12-month and lifetime ECL for every loan and reports the one the stage
        prescribes. This book (2015Q1 reporting date) is a calm-quarter book:
        7,803 loans in Stage 1, just 3 in Stage 2, 43 in Stage 3 — so the
        reported allowance is dominated by 12-month ECL, which is exactly where
        scenario weights and macro shocks act.
      </p>
    </details>
  );
}
