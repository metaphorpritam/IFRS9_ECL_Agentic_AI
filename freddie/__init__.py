"""Rung-3 namespace: Freddie Mac SFLLD scale-up (isolated from the frozen DCR engine).

Nothing under engine/ is imported for write access here; data/processed/panel.parquet
and the five frozen engine modules (hazard, lgd, ead, staging, ecl) are untouched.
See freddie/macro.py for the state-level macro build (the geographic-resolution
upgrade recorded as DCR's documented limitation: rungs 1-2 use only national
macros because the DCR panel carries no state field).
"""
