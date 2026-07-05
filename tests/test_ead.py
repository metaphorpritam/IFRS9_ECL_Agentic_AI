"""Tests for engine/ead.py -- contractual EAD profiles and revolver CCF EAD.

The revolver test asserts the compute_ecl section-12 golden fixture THROUGH
the engine function (importing the fixture module's inputs/targets rather
than duplicating them). The profile tests pin the module's documented
conventions: EAD_t = balance entering period t, annuity closed form ==
payment recursion, straight-line fallback, floor-at-1 remaining term, and
the sanity properties (monotone non-increasing, terminal 0 at maturity,
EAD_t <= snapshot balance <= balance * (1 + one quarter's interest)).
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.ead import RATE_DIVISOR, ccf_ead, ead_matrix, ead_profile
from tests.fixtures import compute_ecl as ecl_fx

PANEL = Path(__file__).resolve().parents[1] / "data" / "processed" / "panel.parquet"


# ---------------------------------------------------------------------------
# ccf_ead vs the section-12 golden fixture
# ---------------------------------------------------------------------------

def test_ccf_ead_reproduces_compute_ecl_fixture():
    got = ccf_ead(ecl_fx.DRAWN_M, ecl_fx.LIMIT_M, ecl_fx.CCF)
    assert got == pytest.approx(ecl_fx.RESULTS["revolver_ead_eur_m"])
    assert got == pytest.approx(14.0)   # the notes' printed EUR 14.0m
    assert got / ecl_fx.DRAWN_M == pytest.approx(
        ecl_fx.RESULTS["revolver_ead_over_drawn"])


def test_ccf_ead_overlimit_floors_undrawn_at_zero():
    assert ccf_ead(25.0, 20.0, 0.6) == 25.0


def test_ccf_ead_zero_ccf_is_drawn_only():
    assert ccf_ead(5.0, 20.0, 0.0) == 5.0


def test_ccf_ead_rejects_negative_inputs():
    with pytest.raises(ValueError):
        ccf_ead(-1.0, 20.0, 0.6)
    with pytest.raises(ValueError):
        ccf_ead(5.0, 20.0, -0.1)


# ---------------------------------------------------------------------------
# ead_profile -- annuity convention
# ---------------------------------------------------------------------------

def test_profile_matches_level_payment_recursion():
    balance, rate_pct, n = 200_000.0, 6.5, 20
    prof = ead_profile(balance, rate_pct, n, n + 4)
    r = rate_pct / RATE_DIVISOR
    payment = balance * r / (1.0 - (1.0 + r) ** -n)
    bal, expected = balance, []
    for _ in range(n):
        expected.append(bal)                 # EAD_t = balance entering t
        bal = bal * (1.0 + r) - payment
    assert bal == pytest.approx(0.0, abs=1e-6)          # amortises to zero
    np.testing.assert_allclose(prof[:n], expected, rtol=1e-12)
    assert np.all(prof[n:] == 0.0)                      # zero past maturity


def test_profile_first_period_equals_current_balance():
    assert ead_profile(123_456.78, 7.25, 40, 10)[0] == pytest.approx(123_456.78)


def test_profile_monotone_terminal_and_interest_cap():
    balance, rate_pct, n = 350_000.0, 9.75, 60
    prof = ead_profile(balance, rate_pct, n, n + 1)
    assert np.all(np.diff(prof) <= 1e-9)                # monotone non-increasing
    assert prof[n - 1] > 0.0                            # last quarter still owed
    assert prof[n] == 0.0                               # ~0 at maturity
    # EAD_t (start-of-period balance) never exceeds the snapshot balance,
    # a fortiori never balance grown by one quarter's interest.
    assert prof.max() <= balance * (1.0 + rate_pct / RATE_DIVISOR) + 1e-9
    assert prof.max() <= balance + 1e-9


def test_profile_zero_rate_falls_back_to_straight_line():
    prof = ead_profile(100_000.0, 0.0, 4, 6)
    np.testing.assert_allclose(
        prof, [100_000.0, 75_000.0, 50_000.0, 25_000.0, 0.0, 0.0])


def test_profile_nan_rate_falls_back_to_straight_line():
    np.testing.assert_allclose(ead_profile(80_000.0, np.nan, 4, 4),
                               [80_000.0, 60_000.0, 40_000.0, 20_000.0])


def test_profile_degenerate_tiny_rate_falls_back_not_nan():
    # r_q below float64 epsilon: 1 + r_q rounds to 1, so the annuity form
    # would be 0/0 -> NaN; the engine must route it to the straight-line
    # fallback and never emit non-finite EAD.
    prof = ead_profile(80_000.0, 1e-14, 4, 5)
    assert np.all(np.isfinite(prof))
    np.testing.assert_allclose(
        prof, [80_000.0, 60_000.0, 40_000.0, 20_000.0, 0.0])


def test_profile_remaining_term_floored_at_one():
    # at/past maturity: everything due within one quarter
    for rem in (0, -3):
        prof = ead_profile(50_000.0, 6.0, rem, 3)
        np.testing.assert_allclose(prof, [50_000.0, 0.0, 0.0])


def test_profile_rejects_bad_inputs():
    with pytest.raises(ValueError):
        ead_profile(-1.0, 6.0, 10, 4)
    with pytest.raises(ValueError):
        ead_profile(1.0, 6.0, 10, 0)


# ---------------------------------------------------------------------------
# ead_matrix -- panel hook
# ---------------------------------------------------------------------------

def _toy_snapshot() -> pd.DataFrame:
    return pd.DataFrame({
        "id": [1, 2, 3, 4],
        "time": [40, 40, 40, 40],
        "mat_time": [60, 40, 140, 90],       # rem = 20, 0 (floored to 1), 100, 50
        "balance_time": [200_000.0, 90_000.0, 300_000.0, 0.0],
        "interest_rate_time": [6.5, 8.0, 5.0, 7.0],
    })


def test_ead_matrix_shape_and_row_equivalence():
    snap = _toy_snapshot()
    m = ead_matrix(snap, horizon=24)
    assert m.shape == (4, 24)
    assert list(m.index) == [1, 2, 3, 4]
    assert list(m.columns) == list(range(1, 25))
    # each row must equal the scalar profile with rem = mat_time - time
    for _, row in snap.iterrows():
        np.testing.assert_allclose(
            m.loc[row["id"]].to_numpy(),
            ead_profile(row["balance_time"], row["interest_rate_time"],
                        int(row["mat_time"] - row["time"]), 24),
            rtol=1e-12)


def test_ead_matrix_matured_and_zero_balance_loans():
    m = ead_matrix(_toy_snapshot(), horizon=6)
    # loan 2: matured (rem floored to 1) -> balance due in quarter 1 only
    np.testing.assert_allclose(m.loc[2].to_numpy(),
                               [90_000.0, 0, 0, 0, 0, 0])
    # loan 4: zero balance -> identically zero path
    assert np.all(m.loc[4].to_numpy() == 0.0)


def test_ead_matrix_rejects_missing_columns_and_duplicate_ids():
    snap = _toy_snapshot()
    with pytest.raises(KeyError):
        ead_matrix(snap.drop(columns=["mat_time"]), horizon=4)
    dup = pd.concat([snap, snap.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError):
        ead_matrix(dup, horizon=4)


@pytest.mark.skipif(not PANEL.exists(), reason="panel parquet not built")
def test_ead_matrix_real_panel_snapshot_sanity():
    cols = ["id", "time", "mat_time", "balance_time", "interest_rate_time",
            "terminal_event"]
    panel = pd.read_parquet(PANEL, columns=cols)
    snap = panel[(panel["time"] == 40) & (panel["terminal_event"] == 0)
                 & (panel["balance_time"] > 0)]
    horizon = int((snap["mat_time"] - snap["time"]).clip(lower=1).max()) + 1
    m = ead_matrix(snap, horizon=horizon)
    vals = m.to_numpy()
    bal = snap.set_index("id").loc[m.index, "balance_time"].to_numpy()
    rq = snap.set_index("id").loc[m.index,
                                  "interest_rate_time"].to_numpy() / RATE_DIVISOR
    assert np.all(np.isfinite(vals)) and np.all(vals >= 0.0)
    # EAD_1 is the snapshot balance
    np.testing.assert_allclose(vals[:, 0], bal, rtol=1e-12)
    # monotone non-increasing along every path (float-noise tolerance)
    assert np.all(np.diff(vals, axis=1) <= 1e-6 * np.maximum(bal, 1.0)[:, None])
    # terminal ~0 at maturity: horizon covers every loan's remaining term
    assert np.all(vals[:, -1] == 0.0)
    # spec cap: EAD_t <= balance grown by at most one quarter's interest
    assert np.all(vals.max(axis=1) <= bal * (1.0 + rq) + 1e-6)
