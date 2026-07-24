import Panel from './Panel.jsx';
import { useExplain } from './ExplainButton.jsx';
import { explainPanelQuestion } from '../api.js';

/**
 * Dossier-v2 propagation: the "Model at a glance" panel at the TOP of the
 * Model tab. One line of the golden ECL convention (engine/ecl.py module
 * docstring / tests/fixtures/compute_ecl.py section 3), then one row per
 * term: a chip that scrolls to the panel where that term is estimated, a
 * one-line meaning, and a per-term AI-explain icon. All copy is static and
 * grounded in the engine docstrings — no numbers, so nothing to go stale.
 */
const TERMS = [
  {
    key: 'survival',
    symbol: 'S(t−1)',
    name: 'Survival to quarter t',
    meaning:
      'Probability the loan is still on the book entering quarter t — the ' +
      'competing-risks product over BOTH hazards, ∏(1 − λ_default − λ_prepay). ' +
      'Prepayment lives here, and only here.',
    anchor: 'panel-hazard',
    anchorLabel: 'Exhibit 1 — hazard coefficients',
  },
  {
    key: 'hazard',
    symbol: 'λ_t',
    name: 'Marginal default hazard',
    meaning:
      'Conditional probability of default in quarter t from the discrete-time ' +
      'cloglog hazard model — the coefficients in Exhibit 1, applied to the ' +
      'scenario macro path.',
    anchor: 'panel-hazard',
    anchorLabel: 'Exhibit 1 — hazard coefficients',
  },
  {
    key: 'lgd',
    symbol: 'LGD_t',
    name: 'Loss given default',
    meaning:
      'Two-stage workout model: a cure-probability logit × a fractional-logit ' +
      'severity for non-cures, plus an excess-loss loading for the LGD>1 tail ' +
      'that clipping would hide.',
    anchor: 'panel-lgd',
    anchorLabel: 'Exhibit 6 — LGD model',
  },
  {
    key: 'ead',
    symbol: 'EAD_t',
    name: 'Exposure at default',
    meaning:
      'Contractual annuity balance entering quarter t — deliberately NOT ' +
      'scaled by prepayment (that is already in S; scaling both would count ' +
      'prepayment twice and understate ECL).',
    anchor: 'panel-ead-eir',
    anchorLabel: 'EAD & EIR method',
  },
  {
    key: 'discount',
    symbol: '(1+EIR_q)^−t',
    name: 'Discounting',
    meaning:
      'Losses crystallise at the END of quarter t and are discounted at the ' +
      'effective interest rate — IFRS 9 requires the origination EIR, proxied ' +
      'here by the note rate (fixed-rate book).',
    anchor: 'panel-ead-eir',
    anchorLabel: 'EAD & EIR method',
  },
];

function scrollToPanel(anchor) {
  document.getElementById(anchor)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function TermRow({ term }) {
  const { button, strip } = useExplain({
    label: `ECL term ${term.symbol}`,
    buildQuestion: () =>
      explainPanelQuestion({
        panelId: 'model_at_a_glance',
        params: { term: term.key },
        title: `ECL term ${term.symbol} (${term.name})`,
        recap: term.meaning,
      }),
  });
  return (
    <li class="glance-term">
      <div class="glance-term-head">
        <button
          type="button"
          class="chip glance-chip"
          data-tip={`Jump to ${term.anchorLabel}`}
          onClick={() => scrollToPanel(term.anchor)}
        >
          {term.symbol}
        </button>
        <div class="glance-term-text">
          <b>{term.name}.</b> {term.meaning}{' '}
          <a
            class="glance-jump"
            href={`#model`}
            onClick={(e) => {
              e.preventDefault();
              scrollToPanel(term.anchor);
            }}
          >
            {term.anchorLabel} ↓
          </a>
        </div>
        <span class="glance-term-actions">{button}</span>
      </div>
      {strip}
    </li>
  );
}

export default function ModelAtAGlance() {
  return (
    <Panel
      title="Model at a glance"
      subtitle="The whole engine is this one sum. Every term is a model you can inspect on this page — click a chip to jump to where it is estimated, or the spark to have the Copilot explain it."
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'model_at_a_glance',
          title: 'Model at a glance',
          recap:
            'The lifetime ECL convention: ECL = sum over t of S(t−1) · λ_t · LGD_t · EAD_t · (1+EIR_q)^−t, with survival including prepayment as a competing risk, contractual-annuity EAD, and discounting at the origination-EIR proxy.',
        })
      }
    >
      <p class="glance-formula" aria-label="ECL formula">
        ECL&nbsp;=&nbsp;Σ<sub>t</sub>&nbsp; S(t−1) · λ<sub>t</sub> · LGD<sub>t</sub> ·
        EAD<sub>t</sub> · (1+EIR<sub>q</sub>)<sup>−t</sup>
      </p>
      <ul class="glance-terms">
        {TERMS.map((t) => (
          <TermRow term={t} key={t.key} />
        ))}
      </ul>
      <p class="panel-source">
        Convention pinned by <code>engine/ecl.py</code> and the{' '}
        <code>tests/fixtures/compute_ecl.py</code> golden fixture (12-month ECL €4,952.83 on
        the worked 5-year example).
      </p>
    </Panel>
  );
}
