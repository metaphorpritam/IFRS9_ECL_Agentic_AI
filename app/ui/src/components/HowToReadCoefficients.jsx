/**
 * Requirement 12 -- the shared "How to read these coefficients" intro panel
 * for both the Model tab (DCR) and the Real Data tab (SFLLD): the link
 * scale, what "1 unit" means, and the 0.01-vs-1pp gotcha, stated once so
 * neither tab has to re-derive it. Plain prose -- no engine numbers -- so
 * it needs no explain-question recap beyond the panel's own title.
 */
export default function HowToReadCoefficients() {
  return (
    <details class="stage-guide">
      <summary>How to read these coefficients</summary>
      <ul>
        <li>
          <b>Link scale.</b> Every model here is a discrete-time <i>cloglog</i>{' '}
          hazard, so <code>exp(coef)</code> is a genuine <b>hazard ratio</b>:
          &gt;1 means the covariate raises the default hazard, &lt;1 means it
          lowers it. A hazard ratio of 1.20 is a 20% relative increase in the
          hazard for +1 unit of the covariate — never a percentage-point
          change in the PD itself.
        </li>
        <li>
          <b>"1 unit" is not always "1".</b> Several covariates are
          pre-scaled for a legible unit — FICO is <code>/100</code> (1 unit
          = 100 points), updated LTV is <code>/10</code> (1 unit = 10pp).
          The <b>Unit</b> line in each row's expanded interpretation states
          exactly what "+1" means before you read the hazard ratio next to
          it.
        </li>
        <li>
          <b>The 0.01-vs-1pp gotcha.</b> The two HPI-growth rows (national
          and, on the Real Data tab, state) are log-growth variables: the
          table's raw hazard ratio is scaled to a full <b>1.0 log-unit</b> —
          roughly 100% quarterly growth, never observed. Reading that number
          as "per 1% growth" overstates the effect by orders of magnitude.
          Each row's <b>Per-unit HR</b> column and worked example instead
          use the economically legible reading — <code>hazard_ratio ** 0.01</code>,
          computed for you, not eyeballed.
        </li>
        <li>
          Click the ▸ next to any row for its full interpretation: the exact
          unit, the transformation, the economic channel (with any stated
          miss against the prior), a computed worked example, and — only for
          macro rows genuinely pulled live from FRED (the state-level rows
          here on the Real Data tab) — a FRED badge with the series ID. The
          national rows on The Model tab are a vendor-premerged series on
          the panel's own anonymized clock, so they carry no FRED badge;
          their <b>Transformation</b> line states how the clock was
          calendar-verified instead.
        </li>
      </ul>
    </details>
  );
}
