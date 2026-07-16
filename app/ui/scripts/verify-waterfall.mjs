#!/usr/bin/env node
// Build-time regression check for the WaterfallChart historical-mode bug
// (FINAL_SPEC.md §0.2 / §8.2): the default (historical) view sets `hist` to
// the RAW GET /api/ecl/waterfall payload ({components, period_t0, ...}),
// which must be adapted with `adaptWaterfallRows()` before it can reach
// `buildWaterfallOption()` — that adapter shapes it into
// `{start, steps, end}`. Skipping the adapter (the original bug) renders an
// EMPTY chart because `buildWaterfallOption` reads `wf.start`/`wf.steps`/
// `wf.end`, none of which exist on the raw payload.
//
// This script feeds a REAL captured payload (verbatim from
// docs/api_contract.md's GET /api/ecl/waterfall example, t0=20/t1=40)
// through the exact adapter + option builder the UI uses, and asserts:
//   1. the adapter output has the {start, steps, end} shape;
//   2. buildWaterfallOption() returns non-empty series data for both
//      series (the invisible base stack and the visible movement bars);
//   3. the raw-payload-without-adapter path would have been empty (proves
//      this check actually catches the historical regression class).
//
// Run via `npm run verify:waterfall` (wired into `npm run build` as a
// prebuild step — see package.json).

import { adaptWaterfallRows } from '../src/api.js';
import { buildWaterfallOption } from '../src/charts/waterfallOption.js';

// Verbatim captured payload — docs/api_contract.md, GET
// /api/ecl/waterfall?t0=20&t1=40 (real engine numbers, not invented).
const CAPTURED_PAYLOAD = {
  tool: 'decompose_waterfall',
  t0: 20,
  t1: 40,
  period_t0: '2005Q1',
  period_t1: '2010Q1',
  opening_allowance: 24538544.76,
  closing_allowance: 1032613371.19,
  components: [
    { component: 'opening', amount: 24538544.76, n_loans: 8662, kind: 'level' },
    { component: 'stage_migration', amount: 3879319.76, n_loans: 498, kind: 'delta' },
    { component: 'remeasurement', amount: 26010644.52, n_loans: 1948, kind: 'delta' },
    { component: 'derecognitions', amount: -21177011.65, n_loans: 6714, kind: 'delta' },
    { component: 'new_loans', amount: 999361873.81, n_loans: 11915, kind: 'delta' },
    { component: 'closing', amount: 1032613371.19, n_loans: 13863, kind: 'level' },
  ],
  identity_gap: 0.0,
  amounts_in: 'USD',
  headline:
    'allowance waterfall t=20 (2005Q1) -> t=40 (2010Q1): opening $24.5m, stage migration ' +
    '+3.9m, remeasurement +26.0m, derecognitions -21.2m, new loans +999.4m, closing $1,032.6m',
  tool_call_id: 'tc-000001',
};

let failures = 0;
const check = (label, cond) => {
  if (cond) {
    console.log(`  PASS  ${label}`);
  } else {
    console.error(`  FAIL  ${label}`);
    failures += 1;
  }
};

console.log('verify-waterfall: historical-mode adapter + buildWaterfallOption regression check');

// --- 1. the FIXED path: raw payload -> adaptWaterfallRows -> {start,steps,end}
const wf = adaptWaterfallRows(
  CAPTURED_PAYLOAD.components,
  'Opening allowance',
  'Closing allowance',
);

check('adapter output has start/steps/end shape', !!(wf && wf.start && wf.end && Array.isArray(wf.steps)));
check('adapter start value matches opening_allowance / 1e6', Math.abs(wf.start.value_m - CAPTURED_PAYLOAD.opening_allowance / 1e6) < 1e-6);
check('adapter end value matches closing_allowance / 1e6', Math.abs(wf.end.value_m - CAPTURED_PAYLOAD.closing_allowance / 1e6) < 1e-6);
check('adapter carries the 4 delta steps', wf.steps.length === 4);

const built = buildWaterfallOption(wf);
const series = built.option?.series ?? [];
check('option has exactly 2 series (base + movement)', series.length === 2);
const movementData = series[1]?.data ?? [];
check('movement series is non-empty', movementData.length > 0);
check('movement series has one datum per category (6: opening + 4 steps + closing)', movementData.length === 6);
check(
  'every movement datum carries a finite rendered value',
  movementData.every((d) => typeof d.value === 'number' && Number.isFinite(d.value)),
);
check('option.xAxis.data is non-empty (categories present)', (built.option.xAxis?.data ?? []).length === 6);

// --- 2. prove this check actually catches the regression: feeding the RAW
// (un-adapted) payload straight to buildWaterfallOption must fail/blow up
// or produce an empty/garbage chart — this is the exact bug that shipped.
let regressionCaught = false;
try {
  const brokenOption = buildWaterfallOption(CAPTURED_PAYLOAD);
  const brokenSeries = brokenOption.option?.series?.[1]?.data ?? [];
  // The raw payload has no .start/.steps/.end -> wf.steps is undefined ->
  // the for-loop over wf.steps throws, OR (if defensively guarded) yields
  // no movement bars. Either shape counts as "caught".
  regressionCaught = brokenSeries.length === 0;
} catch {
  regressionCaught = true;
}
check('un-adapted raw payload does NOT produce a populated chart (proves the bug is real)', regressionCaught);

console.log(failures === 0 ? '\nverify-waterfall: OK' : `\nverify-waterfall: ${failures} check(s) FAILED`);
process.exit(failures === 0 ? 0 : 1);
