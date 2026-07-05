"""GATE tests: the engine's golden values, recreated from the study notes' worked examples.

Each tests/fixtures/compute_*.py derives RESULTS from its worked example's stated inputs and
carries the notes' printed values in TARGETS. A value passes when it matches the target at the
precision the notes display (the notes round/truncate for print). The Phase-3 engine is frozen
only when this suite passes — see MASTER_PLAN.md §3.4/§5.
"""
import importlib
from decimal import Decimal

import pytest

FIXTURE_MODULES = [
    "compute_ecl", "compute_pd", "compute_vasicek", "compute_scenarios",
    "compute_grossup", "compute_ncl", "compute_rollrate", "compute_validation",
]


def _displayed_decimals(target: float) -> int:
    if float(target).is_integer():
        return 0  # trailing ".0" is a float artifact, not displayed precision
    exp = Decimal(str(target)).as_tuple().exponent
    return max(0, -exp) if isinstance(exp, int) else 0


def _cases():
    for mod_name in FIXTURE_MODULES:
        mod = importlib.import_module(f"tests.fixtures.{mod_name}")
        assert set(mod.RESULTS) == set(mod.TARGETS), (
            f"{mod_name}: RESULTS/TARGETS keys diverge")
        for key, target in mod.TARGETS.items():
            yield pytest.param(mod.RESULTS[key], target, id=f"{mod_name}::{key}")


@pytest.mark.parametrize("computed,target", _cases())
def test_golden_value(computed, target):
    # The notes print rounded (sometimes truncated) values; a derived value "matches"
    # when it is within one unit of the target's last displayed digit.
    places = _displayed_decimals(target)
    assert abs(computed - target) <= 10 ** -places, (
        f"computed {computed!r} vs notes' printed {target!r} "
        f"(off by more than one unit in the last of {places} displayed decimals)")
