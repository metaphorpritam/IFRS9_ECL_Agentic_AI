"""Tests for engine/ecl.py -- the ECL kernel and the movement decomposition.

(a) The kernel reproduces the compute_ecl section-3 golden fixture THROUGH
    the engine functions (importing the fixture module's inputs, never
    duplicating values): 5-year amortising loan, annual hazards
    [1.5, 2.0, 2.2, 2.0, 1.8]%, LGD 35%, EAD 1,000,000 - 200,000*(t-1),
    EIR 6% -> 12m ECL 4,952.83 and lifetime ECL 16,571.39 within one unit
    of the last printed digit -- proving the engine implements
    ECL = sum_t S(t-1)*lambda_t*LGD_t*EAD_t*(1+EIR)^-t.
(b) The movement decomposition components sum exactly to closing - opening,
    with the documented sequential attribution verified on hand examples.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.ecl import (
    ALLOWANCE_COLS,
    WATERFALL_COMPONENTS,
    ecl_schedule,
    ecl_totals,
    movement_decomposition,
    reported_allowance,
)
from tests.fixtures import compute_ecl as fx


# ---------------------------------------------------------------------------
# (a) the section-3 golden fixture through the ENGINE functions
# ---------------------------------------------------------------------------

def _fixture_schedule() -> pd.DataFrame:
    """Engine schedule from the fixture module's own inputs (annual periods)."""
    years = np.arange(1, fx.HAZARDS.size + 1)
    ead = fx.PRINCIPAL - fx.REPAYMENT * (years - 1)   # balance after t-1 pmts
    return ecl_schedule(fx.HAZARDS, fx.LGD_LOAN, ead, fx.EIR_LOAN)


def test_engine_reproduces_fixture_12m_and_lifetime():
    e12, life = ecl_totals(_fixture_schedule(), periods_12m=1)
    # exact against the fixture's derived values ...
    assert e12 == pytest.approx(fx.RESULTS["ecl_12m_eur"], rel=1e-12)
    assert life == pytest.approx(fx.RESULTS["ecl_lifetime_eur"], rel=1e-12)
    # ... and within one unit of the last printed digit of the notes' targets
    assert abs(e12 - fx.TARGETS["ecl_12m_eur"]) <= 0.01        # 4,952.83
    assert abs(life - fx.TARGETS["ecl_lifetime_eur"]) <= 0.01  # 16,571.39
    assert life / e12 == pytest.approx(
        fx.RESULTS["lifetime_over_12m_ratio"], rel=1e-12)      # the 3.35x jump


def test_engine_reproduces_fixture_row_by_row():
    sched = _fixture_schedule()
    for t in range(1, fx.HAZARDS.size + 1):
        row = sched.loc[sched["period"] == t].iloc[0]
        assert row["survival_start"] == pytest.approx(
            fx.RESULTS[f"survival_start_year_{t}"], rel=1e-12)
        assert row["marginal_pd"] == pytest.approx(
            fx.RESULTS[f"marginal_pd_year_{t}"], rel=1e-12)
        assert row["discount"] == pytest.approx(
            fx.RESULTS[f"discount_factor_year_{t}"], rel=1e-12)
        assert row["ecl"] == pytest.approx(
            fx.RESULTS[f"ecl_year_{t}_eur"], rel=1e-12)


def test_fixture_cumulative_pd_from_engine_survival():
    sched = _fixture_schedule()
    cum_pd = float(sched["marginal_pd"].sum())
    assert cum_pd * 100.0 == pytest.approx(
        fx.RESULTS["cumulative_pd_5y_pct"], rel=1e-12)


# ---------------------------------------------------------------------------
# kernel conventions beyond the fixture
# ---------------------------------------------------------------------------

def test_competing_prepayment_enters_survival_and_lowers_ecl():
    lam_d = np.array([0.02, 0.02, 0.02])
    lam_p = np.array([0.10, 0.10, 0.10])
    base = ecl_schedule(lam_d, 0.4, 100.0, 0.05)
    comp = ecl_schedule(lam_d, 0.4, 100.0, 0.05, hazard_prepay=lam_p)
    # hand-checked competing-risk survival: S(1) = 1 - 0.02 - 0.10
    assert comp["survival_start"].iloc[1] == pytest.approx(0.88, rel=1e-12)
    assert comp["survival_start"].iloc[2] == pytest.approx(0.88**2, rel=1e-12)
    # prepayment survival strictly reduces lifetime ECL
    assert comp["ecl"].sum() < base["ecl"].sum()


def test_quarterly_12m_window_sums_first_four_quarters():
    lam = np.full(8, 0.01)
    sched = ecl_schedule(lam, 0.5, 1000.0, 0.06 / 4)
    e12, life = ecl_totals(sched, periods_12m=4)
    assert e12 == pytest.approx(float(sched["ecl"].iloc[:4].sum()), rel=1e-15)
    assert life == pytest.approx(float(sched["ecl"].sum()), rel=1e-15)
    assert e12 < life


def test_lgd_above_one_is_allowed_never_clipped():
    # beyond-EAD workout costs: LGD may exceed 1 (engine/lgd.py loading)
    sched = ecl_schedule(np.array([1.0]), 1.2, 100.0, 0.0)
    assert sched["ecl"].iloc[0] == pytest.approx(120.0, rel=1e-12)


def test_schedule_input_validation():
    with pytest.raises(ValueError):
        ecl_schedule(np.array([0.01, 0.01]), 0.4, np.array([1.0]), 0.05)
    with pytest.raises(ValueError):
        ecl_schedule(np.array([-0.01]), 0.4, 100.0, 0.05)
    with pytest.raises(ValueError):
        ecl_schedule(np.array([0.01]), -0.4, 100.0, 0.05)
    with pytest.raises(ValueError):
        ecl_schedule(np.array([0.01]), 0.4, 100.0, -1.5)
    with pytest.raises(ValueError):
        ecl_schedule(np.array([]), 0.4, 100.0, 0.05)
    with pytest.raises(ValueError):
        ecl_totals(_fixture_schedule(), periods_12m=0)


# ---------------------------------------------------------------------------
# (b) movement decomposition
# ---------------------------------------------------------------------------

def _frame(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=ALLOWANCE_COLS)


def _amounts(wf: pd.DataFrame) -> dict[str, float]:
    return dict(zip(wf["component"], wf["amount"]))


def test_reported_allowance_stage_mapping():
    df = _frame([(1, 1, 10.0, 30.0), (2, 2, 5.0, 25.0), (3, 3, 40.0, 40.0)])
    np.testing.assert_allclose(reported_allowance(df), [10.0, 25.0, 40.0])


def test_decomposition_components_sum_exactly_to_closing_minus_opening():
    a0 = _frame([
        (1, 1, 10.0, 30.0),    # survives, migrates 1 -> 2, re-marked
        (2, 2, 5.0, 25.0),     # survives, stays 2, re-marked
        (3, 1, 2.0, 6.0),      # derecognised (prepaid)
        (4, 3, 50.0, 50.0),    # derecognised (default resolved)
    ])
    a1 = _frame([
        (1, 2, 12.0, 45.0),
        (2, 2, 4.0, 20.0),
        (5, 1, 3.0, 9.0),      # new loan
    ])
    wf = movement_decomposition(a0, a1)
    amt = _amounts(wf)
    assert list(wf["component"]) == WATERFALL_COMPONENTS
    assert amt["opening"] == pytest.approx(10.0 + 25.0 + 2.0 + 50.0)
    assert amt["closing"] == pytest.approx(45.0 + 20.0 + 3.0)
    delta = sum(amt[c] for c in ("stage_migration", "remeasurement",
                                 "derecognitions", "new_loans"))
    assert delta == pytest.approx(amt["closing"] - amt["opening"], abs=1e-9)


def test_decomposition_sequential_attribution_hand_example():
    # one surviving loan, Stage 1 -> Stage 2, marks also move
    a0 = _frame([(1, 1, 10.0, 30.0)])
    a1 = _frame([(1, 2, 12.0, 45.0)])
    amt = _amounts(movement_decomposition(a0, a1))
    # stage migration FIRST, at t0 marks: lifetime_0 - 12m_0 = 30 - 10
    assert amt["stage_migration"] == pytest.approx(20.0)
    # re-measurement second, at the migrated stage: lifetime_1 - lifetime_0
    assert amt["remeasurement"] == pytest.approx(15.0)
    assert amt["derecognitions"] == 0.0 and amt["new_loans"] == 0.0
    assert amt["opening"] == pytest.approx(10.0)
    assert amt["closing"] == pytest.approx(45.0)


def test_decomposition_pure_remark_has_zero_stage_effect():
    a0 = _frame([(1, 1, 10.0, 30.0)])
    a1 = _frame([(1, 1, 14.0, 33.0)])
    amt = _amounts(movement_decomposition(a0, a1))
    assert amt["stage_migration"] == 0.0
    assert amt["remeasurement"] == pytest.approx(4.0)   # 12m_1 - 12m_0


def test_decomposition_portfolio_only_components():
    a0 = _frame([(1, 2, 5.0, 25.0)])
    a1 = _frame([(2, 1, 3.0, 9.0)])
    amt = _amounts(movement_decomposition(a0, a1))
    assert amt["derecognitions"] == pytest.approx(-25.0)
    assert amt["new_loans"] == pytest.approx(3.0)
    assert amt["stage_migration"] == 0.0 and amt["remeasurement"] == 0.0
    assert amt["closing"] == pytest.approx(
        amt["opening"] - 25.0 + 3.0, abs=1e-12)


def test_decomposition_counts_and_labels():
    a0 = _frame([(1, 1, 10.0, 30.0), (2, 2, 5.0, 25.0), (3, 1, 2.0, 6.0)])
    a1 = _frame([(1, 2, 12.0, 45.0), (2, 2, 4.0, 20.0), (5, 1, 3.0, 9.0)])
    wf = movement_decomposition(a0, a1, label_t0="t=20", label_t1="t=40")
    n = dict(zip(wf["component"], wf["n_loans"]))
    assert n["opening"] == 3 and n["closing"] == 3
    assert n["stage_migration"] == 1        # only loan 1 changed stage
    assert n["remeasurement"] == 2          # both surviving loans re-marked
    assert n["derecognitions"] == 1 and n["new_loans"] == 1
    assert wf.attrs["label_t0"] == "t=20" and wf.attrs["label_t1"] == "t=40"


def test_decomposition_rejects_bad_frames():
    good = _frame([(1, 1, 10.0, 30.0)])
    dup = _frame([(1, 1, 10.0, 30.0), (1, 2, 5.0, 25.0)])
    with pytest.raises(ValueError):
        movement_decomposition(dup, good)
    with pytest.raises(KeyError):
        movement_decomposition(good.drop(columns=["stage"]), good)
