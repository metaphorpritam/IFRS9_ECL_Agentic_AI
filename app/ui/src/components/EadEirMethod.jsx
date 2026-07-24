import { explainPanelQuestion } from '../api.js';

/**
 * Dossier-v2 propagation: the EAD & EIR method panel body for the Model tab.
 * Static method copy grounded ONLY in the engine/ead.py and engine/ecl.py
 * module docstrings (the same conventions the compute_ecl golden fixtures
 * pin) — the two ECL terms that had no panel of their own until now.
 */
export function buildEadEirExplainQuestion() {
  return explainPanelQuestion({
    panelId: 'ead_eir_method',
    title: 'EAD & EIR method',
    recap:
      'EAD_t is the contractual annuity balance entering quarter t (closed form, quarterly compounding of the note rate), deliberately not prepay-scaled because survival already removes prepaid loans; discounting uses the origination-EIR proxy eir_q = note rate / 400 on this fixed-rate book; Stage 3 is LGD × current balance undiscounted.',
  });
}

export default function EadEirMethod() {
  return (
    <>
      <div class="two-col">
        <div>
          <h3>EAD — contractual amortisation</h3>
          <p class="method-p">
            <b>Closed-form annuity balance.</b> Each loan amortises level-pay with quarterly
            compounding of its note rate (<code>r_q = rate / 400</code>):
          </p>
          <p class="glance-formula method-formula">
            B<sub>k</sub> = B<sub>0</sub> ·{' '}
            <span class="frac">
              <span class="frac-top">(1+r<sub>q</sub>)<sup>n</sup> − (1+r<sub>q</sub>)<sup>k</sup></span>
              <span class="frac-bot">(1+r<sub>q</sub>)<sup>n</sup> − 1</span>
            </span>
            , &nbsp; EAD<sub>t</sub> = B<sub>t−1</sub>
          </p>
          <p class="method-p">
            so EAD₁ is the snapshot balance, the path declines monotonically, hits zero exactly
            at maturity, and is zero beyond the remaining term <i>n</i>.
          </p>
          <p class="method-p">
            <b>The double-counting rule (the one reviewers probe).</b> EAD is the{' '}
            <i>contractual</i> balance and is deliberately <b>not</b> scaled by prepayment
            probabilities: the survival weight S(t−1) is a competing-risks product that already
            removes the prepaid fraction of the book. Scaling EAD too would count prepayment
            twice and understate lifetime ECL.
          </p>
          <p class="method-p">
            <b>Documented fallbacks.</b> A non-positive or float-denormal rate falls back to
            straight-line amortisation (defensive — no live panel row triggers it); loans at or
            past contractual maturity are treated as fully due within one quarter; every term
            loan is level-pay (the panel carries no amortisation-type field). Revolvers use{' '}
            <code>EAD = drawn + CCF · (limit − drawn)</code> — the golden fixture: 5m drawn, 20m
            limit, CCF 0.6 → <b>14.0m</b>.
          </p>
        </div>
        <div>
          <h3>EIR — what discounts the losses</h3>
          <p class="method-p">
            <b>IFRS 9 requires the origination EIR</b>, not the current market rate — the
            allowance measures the loss embedded in <i>this</i> contract, so a rate rally never
            flatters it. On this US fixed-rate book the current note rate coincides with the
            origination rate up to repricing (out of scope), so{' '}
            <code>eir_q = note rate / 400</code> is the disciplined EIR proxy — the same
            RATE_DIVISOR convention that drives the annuity.
          </p>
          <p class="method-p">
            <b>Timing.</b> Losses crystallise at the <i>end</i> of period t, hence the{' '}
            <code>(1+EIR_q)^−t</code> factor on each term of the ECL sum.
          </p>
          <p class="method-p">
            <b>Disclosed approximation.</b> A true EIR would amortise origination fees and
            points into the rate; the panel carries no fee data, so the note-rate proxy is the
            documented simplification.
          </p>
          <p class="method-p">
            <b>Stage 3 is different by design.</b> For credit-impaired loans the default has
            already happened: ECL = LGD × current balance, with no PD and no further
            discounting — the loss crystallises now, and workout-recovery discounting is
            already embedded in the realised <code>lgd_time</code> the LGD model is fitted on.
          </p>
        </div>
      </div>
      <p class="panel-source">
        Grounded in the <code>engine/ead.py</code> and <code>engine/ecl.py</code> module
        docstrings — the same conventions <code>tests/fixtures/compute_ecl.py</code> pins.
      </p>
    </>
  );
}
