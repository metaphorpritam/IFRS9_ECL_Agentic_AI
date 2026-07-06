"""Unit tests for engine/vasicek.py (Vasicek conditioning + Belkin Z-shift).

Three contracts, per the build plan:
  1. the ENGINE functions reproduce the golden Vasicek fixture
     (tests/fixtures/compute_vasicek.py: PD_TTC = 2%, rho = 0.12 ->
     7.34% @ Z=-2, 1.43% @ Z=0, 0.17% @ Z=+2, etc.) -- both against the
     fixture's derived RESULTS (tight) and the notes' printed TARGETS
     (at displayed precision);
  2. the anchor property E_Z[PD_PIT] = PD_TTC holds to < 1e-6 by
     Gauss-Hermite at (2%, 0.12) and (5%, 0.15);
  3. the PIT<->Z round trip invert_z(pit_pd(p, z, rho), p, rho) == z is
     exact over a (p, rho, z) grid -- the fixed-conventions answer to the
     Basson & van Vuuren round-trip caveat quoted in the notes.

Plus the Belkin calibrator on synthetic data with known rho, and loud
domain validation.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from engine.vasicek import (
    RHO_BASEL_RESI,
    RHO_NOTES,
    anchor_check,
    calibrate_rho,
    hybrid_pd,
    invert_z,
    pit_pd,
)
from tests.fixtures import compute_vasicek as fx

# ---------------------------------------------------------------------------
# 1. Golden fixture reproduced through the ENGINE functions
# ---------------------------------------------------------------------------

_FIXTURE_KEYS = {  # Z value -> fixture key (values are in %)
    2.0: "pd_pit_pct_z_plus_2_0",
    1.0: "pd_pit_pct_z_plus_1_0",
    0.0: "pd_pit_pct_z_0_0",
    -1.0: "pd_pit_pct_z_minus_1_0",
    -2.0: "pd_pit_pct_z_minus_2_0",
    -2.5: "pd_pit_pct_z_minus_2_5",
}


@pytest.mark.parametrize("z,key", sorted(_FIXTURE_KEYS.items()))
def test_pit_pd_matches_fixture_results(z, key):
    """Engine pit_pd == the fixture's independently derived value (tight)."""
    engine_pct = pit_pd(fx.PD_TTC, z, fx.RHO) * 100.0
    assert engine_pct == pytest.approx(fx.RESULTS[key], abs=1e-12)


@pytest.mark.parametrize("z,key", sorted(_FIXTURE_KEYS.items()))
def test_pit_pd_matches_notes_targets(z, key):
    """Engine pit_pd matches the notes' printed table at 2 displayed dp."""
    engine_pct = pit_pd(fx.PD_TTC, z, fx.RHO) * 100.0
    assert abs(engine_pct - fx.TARGETS[key]) <= 1e-2


def test_headline_golden_values_inline():
    """The three headline numbers, spelled out: 7.34% / 1.43% / 0.17%."""
    assert pit_pd(0.02, -2.0, 0.12) * 100 == pytest.approx(7.34, abs=1e-2)
    assert pit_pd(0.02, 0.0, 0.12) * 100 == pytest.approx(1.43, abs=1e-2)
    assert pit_pd(0.02, 2.0, 0.12) * 100 == pytest.approx(0.17, abs=1e-2)


# ---------------------------------------------------------------------------
# 2. Anchor property (law of total probability) via Gauss-Hermite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pd_ttc,rho", [
    (0.02, 0.12),               # notes convention (== fixture inputs)
    (0.05, 0.15),               # Basel residential-floor rho
])
def test_anchor_property(pd_ttc, rho):
    expected, err = anchor_check(pd_ttc, rho)
    assert err < 1e-6
    assert expected == pytest.approx(pd_ttc, abs=1e-6)


def test_anchor_matches_fixture_quadrature():
    """Engine GH anchor equals the fixture's own GH computation."""
    expected, _ = anchor_check(fx.PD_TTC, fx.RHO)
    assert expected == pytest.approx(
        fx.RESULTS["expected_pd_pit_gauss_hermite"], abs=1e-12)


def test_reference_rho_constants():
    assert RHO_NOTES == 0.12
    assert RHO_BASEL_RESI == 0.15


# ---------------------------------------------------------------------------
# 3. PIT <-> Z round trip (fixed conventions, both legs in one module)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("p", [0.005, 0.02, 0.05, 0.20])
@pytest.mark.parametrize("rho", [0.05, 0.12, 0.15, 0.30])
def test_round_trip_z(p, rho):
    z = np.linspace(-3.0, 3.0, 13)
    z_back = invert_z(pit_pd(p, z, rho), p, rho)
    np.testing.assert_allclose(z_back, z, atol=1e-9)


def test_round_trip_scalar_and_rate():
    """Scalar round trip both ways: z -> rate -> z and rate -> z -> rate."""
    p, rho, z = 0.02, 0.12, -1.7
    rate = pit_pd(p, z, rho)
    assert invert_z(rate, p, rho) == pytest.approx(z, abs=1e-12)
    z_hat = invert_z(0.0431, p, rho)
    assert pit_pd(p, z_hat, rho) == pytest.approx(0.0431, abs=1e-12)


def test_invert_z_sign_convention():
    """Z = 0 corresponds to the Z=0 CONDITIONAL rate pit_pd(p, 0, rho) --
    NOT to the TTC mean anchor itself (convexity: 1.43% vs 2% in the notes'
    example). Rates above/below that neutral rate give Z < 0 / Z > 0."""
    neutral = pit_pd(0.02, 0.0, 0.12)          # 1.43%, not 2%
    assert invert_z(neutral, 0.02, 0.12) == pytest.approx(0.0, abs=1e-12)
    assert invert_z(0.05, 0.02, 0.12) < 0.0    # downturn
    assert invert_z(0.005, 0.02, 0.12) > 0.0   # boom
    # the anchor rate itself sits ABOVE the neutral rate => small negative Z
    assert invert_z(0.02, 0.02, 0.12) < 0.0


# ---------------------------------------------------------------------------
# Belkin calibration on synthetic data with known rho
# ---------------------------------------------------------------------------

def test_calibrate_rho_recovers_truth():
    rng = np.random.default_rng(8)
    rho_true = 0.12
    z = rng.standard_normal(60)
    z = (z - z.mean()) / z.std(ddof=1)     # sample var exactly 1 (ddof=1)
    anchors = np.full(60, 0.02)
    observed = pit_pd(anchors, z, rho_true)
    res = calibrate_rho(observed, anchors, ddof=1)
    assert res.rho == pytest.approx(rho_true, abs=1e-8)
    assert res.var_z == pytest.approx(1.0, abs=1e-10)
    np.testing.assert_allclose(res.z, z, atol=1e-8)


def test_calibrate_rho_composition_adjusted_anchors():
    """Per-period anchors (the composition-adjusted case) also invert."""
    rng = np.random.default_rng(11)
    rho_true = 0.15
    z = rng.standard_normal(40)
    z = (z - z.mean()) / z.std(ddof=1)
    anchors = np.exp(rng.uniform(np.log(0.01), np.log(0.04), size=40))
    observed = pit_pd(anchors, z, rho_true)
    res = calibrate_rho(observed, anchors)
    assert res.rho == pytest.approx(rho_true, abs=1e-8)
    np.testing.assert_allclose(res.z, z, atol=1e-8)


def test_calibrate_rho_flat_history_raises():
    with pytest.raises(ValueError, match="bracket"):
        calibrate_rho(np.full(20, 0.0200001), np.full(20, 0.02))


# ---------------------------------------------------------------------------
# Hybrid damping + domain validation
# ---------------------------------------------------------------------------

def test_hybrid_pd_endpoints_and_damping():
    z = np.array([-2.0, -1.0, 1.0])
    ttc = 0.02
    # alpha = 0 collapses to the cycle-NEUTRAL (Z=0) PD -- 1.43%, which is
    # Jensen-below the 2% TTC mean anchor, not equal to it
    np.testing.assert_allclose(hybrid_pd(ttc, z, 0.12, alpha=0.0),
                               np.full(3, pit_pd(ttc, 0.0, 0.12)), atol=1e-15)
    np.testing.assert_allclose(hybrid_pd(ttc, z, 0.12, alpha=1.0),
                               pit_pd(ttc, z, 0.12), atol=1e-15)
    # damping pulls strictly toward the anchor in a downturn
    full = pit_pd(ttc, -2.0, 0.12)
    half = hybrid_pd(ttc, -2.0, 0.12, alpha=0.5)
    assert ttc < half < full


@pytest.mark.parametrize("bad_rho", [0.0, 1.0, -0.1, 1.3])
def test_rho_domain_validation(bad_rho):
    with pytest.raises(ValueError, match="rho"):
        pit_pd(0.02, 0.0, bad_rho)


@pytest.mark.parametrize("bad_p", [0.0, 1.0, -0.2, np.nan])
def test_probability_domain_validation(bad_p):
    with pytest.raises(ValueError):
        pit_pd(bad_p, 0.0, 0.12)
    with pytest.raises(ValueError):
        invert_z(bad_p, 0.02, 0.12)


def test_monotonicity_in_z():
    """PD_PIT strictly decreasing in Z (good times compress PDs)."""
    z = np.linspace(-3, 3, 25)
    pd_path = pit_pd(0.02, z, 0.12)
    assert np.all(np.diff(pd_path) < 0)
    # and convex amplification: downturn moves exceed symmetric good moves
    assert (pit_pd(0.02, -2.0, 0.12) - 0.02) > (0.02 - pit_pd(0.02, 2.0, 0.12))


def test_ppf_threshold_matches_notes():
    """Phi^{-1}(0.02) = -2.0537 (the notes' quoted default threshold)."""
    assert norm.ppf(fx.PD_TTC) == pytest.approx(
        fx.TARGETS["default_threshold_ppf_002"], abs=1e-4)
