"""IFRS 9 ECL classical engine.

Rung-1 components: discrete-time cloglog hazard PD models with competing-risk
prepayment (engine.hazard) and contractual EAD profiles + revolver CCF EAD
(engine.ead). Methodology anchors:
knowledge/sources/ifrs9_credit_risk_notes.md sections 6.2 (discrete-time hazard =
grouped-duration Cox; cause-specific competing risks), the ECL decomposition
theorem (marginal PD = S(t-1) * lambda_t), and section 12 (CCF EAD). The EAD
path is CONTRACTUAL (never prepay-scaled): the competing-risk survival S(t)
already carries prepayment -- see engine/ead.py's CRITICAL docstring section.

engine.lgd adds the two-stage workout LGD (cure logit x fractional-logit
severity with an explicit beyond-EAD excess-loss loading), notes section 10.

engine.staging adds IFRS 9 SICR staging (notes section 2.2): the RELATIVE
lifetime-PD deterioration test -- lifetime PD over the remaining life NOW vs
the PD projected for the SAME window at initial recognition -- with the
doubling-convention ratio trigger, an annualised absolute add-on, a probation
cure rule, and an (inert-on-DCR, loudly documented) 30-DPD backstop hook.

engine.ecl completes the deterministic engine: the ECL sum
ECL = sum_t S(t-1)*lambda_t*LGD_t*EAD_t*(1+EIR)^-t (compute_ecl section-3
golden convention; 12m AND lifetime always computed, reported per IFRS 9
stage) and the sequential allowance movement decomposition (opening ->
stage migration -> re-measurement -> derecognitions -> new loans ->
closing).
"""

from engine.ead import ccf_ead, ead_matrix, ead_profile
from engine.ecl import (
    EclConfig,
    crosscheck_lgd_grid,
    ecl_for_snapshot,
    ecl_schedule,
    ecl_totals,
    movement_decomposition,
    reported_allowance,
)
from engine.hazard import (
    HazardModel,
    fit_default_hazard,
    fit_prepay_hazard,
    pd_term_structure,
    predict_hazard,
)
from engine.lgd import (
    LgdModels,
    fit_lgd_models,
    predict_components,
    predict_lgd,
)
from engine.staging import (
    StagingConfig,
    assign_stages,
    build_macro_map,
    crosscheck_term_structure,
    lifetime_pd_table,
    origination_covariates,
    quantitative_sicr,
)

__all__ = [
    "HazardModel",
    "fit_default_hazard",
    "fit_prepay_hazard",
    "predict_hazard",
    "pd_term_structure",
    "ead_profile",
    "ead_matrix",
    "ccf_ead",
    "LgdModels",
    "fit_lgd_models",
    "predict_lgd",
    "predict_components",
    "StagingConfig",
    "assign_stages",
    "build_macro_map",
    "crosscheck_term_structure",
    "lifetime_pd_table",
    "origination_covariates",
    "quantitative_sicr",
    "EclConfig",
    "crosscheck_lgd_grid",
    "ecl_for_snapshot",
    "ecl_schedule",
    "ecl_totals",
    "movement_decomposition",
    "reported_allowance",
]
