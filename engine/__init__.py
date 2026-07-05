"""IFRS 9 ECL classical engine.

Rung-1 component: discrete-time cloglog hazard PD models with competing-risk
prepayment (engine.hazard). Methodology anchors:
knowledge/sources/ifrs9_credit_risk_notes.md sections 6.2 (discrete-time hazard =
grouped-duration Cox; cause-specific competing risks) and the ECL decomposition
theorem (marginal PD = S(t-1) * lambda_t).
"""

from engine.hazard import (
    HazardModel,
    fit_default_hazard,
    fit_prepay_hazard,
    pd_term_structure,
    predict_hazard,
)

__all__ = [
    "HazardModel",
    "fit_default_hazard",
    "fit_prepay_hazard",
    "predict_hazard",
    "pd_term_structure",
]
