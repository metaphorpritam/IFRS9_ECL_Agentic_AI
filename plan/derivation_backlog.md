# Derivation backlog — every derivation/example needing full step-by-step expansion

Per the rendering rules: incomplete derivations in the source notes must be EXPANDED — every substitution
shown with intermediate values in LaTeX, every variable defined at first use. This backlog lists each one
with its chapter, fixture, exact golden values to substitute, and what the source notes currently leave
compressed or merely asserted.

---

### D-1. Survival function from hazard — $S(t)=\prod_{k\le t}(1-\lambda_k)$

- **Chapter.** Ch.2 (ECL Mechanics).
- **Source anchor.** A3, s3, the ECL-decomposition THEOREM box.
- **What's compressed.** The theorem states $ECL=\sum_t DF(t)S(t-1)\lambda_t LGD_tEAD_t$ and defines
  $S(t)$ inline as a product, but never derives *why* survival is a product of per-period conditional
  non-default probabilities (independence-of-increments argument for a Markov default process).
- **Fixture / values to substitute.** `tests/fixtures/compute_ecl.py` — hazards λ = {1.5%, 2.0%, 2.2%,
  2.0%, 1.8%} across the 5 years; target `cumulative_pd_5y_pct`. Show $S(1),\dots,S(5)$ individually,
  then $1-S(5)$ = cumulative_pd_5y_pct.
- **Expansion needed.** Derive $S(t)=P(T>t)=\prod_{k=1}^t P(T>k\mid T>k-1)=\prod_{k=1}^t(1-\lambda_k)$
  from the chain rule of conditional probability; then compute each $S(t)$ step with the actual λ values.

### D-2. Full 5-year ECL worked example — every year's substitution

- **Chapter.** Ch.2.
- **Source anchor.** A3, s3, worked example ("5-year amortising loan... EUR 1,000,000...").
- **Fixture / values.** `compute_ecl.py` RESULTS: `ecl_12m_eur`, `ecl_lifetime_eur`,
  `lifetime_over_12m_ratio`, plus the amortisation schedule (principal EUR 1,000,000 repaid EUR 200,000/yr)
  implied by the source text.
- **Expansion needed.** A year-by-year table: outstanding balance → EAD_t → λ_t → S(t-1) → LGD (constant
  35%) → DF(t) at EIR=6% → the per-year expected-loss contribution → running sum to `ecl_lifetime_eur`;
  separately isolate the year-1 term to reproduce `ecl_12m_eur`, then compute the ratio.

### D-3. Cloglog link from continuous-time proportional hazards

- **Chapter.** Ch.3 (Hazard Modelling). **Flagged explicitly in the campaign brief.**
- **Source anchor.** A7, s6.2, "Discrete-time hazard model" THEOREM box.
- **What's compressed.** The notes give $\lambda(t\mid x)=1-\exp(-\exp(x'\beta))$ as *the* cloglog form
  without deriving it from the underlying continuous-time hazard integral.
- **Fixture / values.** No golden fixture (architecture-level result, not a numeric worked example) — use
  `outputs/hazard/fit_stats.md` / `hazard_ratios.md` coefficients as the applied instance after the
  derivation.
- **Expansion needed.** Start from continuous hazard $h(t\mid x)=h_0(t)\exp(x'\beta)$ (Cox proportional
  hazards); integrate over one discrete interval $[t,t+1)$ to get the interval survival probability
  $\exp(-\int_t^{t+1}h_0(u)\exp(x'\beta)\,du)$; assume a piecewise-constant baseline over the interval
  ($\int_t^{t+1}h_0(u)du=\alpha_t$, absorbed as an interval-specific intercept); show
  $1-\exp(-\exp(\alpha_t+x'\beta))$ falls out, i.e. the cloglog link $\text{cloglog}(\lambda)=\log(-\log(1
  -\lambda))=\alpha_t+x'\beta$. Contrast with logit's lack of this continuous-time justification.

### D-4. Merton distance-to-default and PD

- **Chapter.** Ch.3 (Hazard Modelling, corporate/LDP sub-section).
- **Source anchor.** A9, s7.2, "Merton (1974)" THEOREM box.
- **What's compressed.** States $V_T\sim$ lognormal under GBM and default iff $V_T<D$, jumps straight to
  $PD=\Phi(-DD)$ without the intermediate log-transform/Itô step.
- **Fixture / values.** `tests/fixtures/compute_pd.py` — `merton_dd`, `merton_pd_pct`.
- **Expansion needed.** Asset SDE $dV=\mu V\,dt+\sigma_A V\,dW$; solve via Itô to
  $\ln V_T=\ln V_0+(\mu-\tfrac12\sigma_A^2)T+\sigma_A W_T$; standardise
  $Z=\frac{\ln V_T-\ln V_0-(\mu-\frac12\sigma_A^2)T}{\sigma_A\sqrt T}\sim N(0,1)$; define
  $DD=\frac{\ln(V_0/D)+(\mu-\frac12\sigma_A^2)T}{\sigma_A\sqrt T}$; show $P(V_T<D)=P(Z<-DD)=\Phi(-DD)$
  with the actual $V_0,D,\mu,\sigma_A,T$ from the fixture substituted at each step.

### D-5. One-factor Gaussian copula → $PD_{PIT}(Z)$ conditioning formula

- **Chapter.** Ch.5 (Vasicek). **Flagged explicitly in the campaign brief.**
- **Source anchor.** A10, s8.
- **What's compressed.** The notes present $PD_{PIT}(Z)=\Phi\big[(\Phi^{-1}(PD_{TTC})-\sqrt\rho Z)/
  \sqrt{1-\rho}\big]$ as a given formula, not derived from the asset-value representation.
- **Fixture / values.** `tests/fixtures/compute_vasicek.py` — PD_TTC=2%, ρ=0.12,
  `default_threshold_ppf_002`=Φ⁻¹(0.02)=−2.0537, and the 6-point table (Z ∈ {+2,+1,0,−1,−2,−2.5} →
  pd_pit_pct); `expected_pd_pit_gauss_hermite`/`expected_pd_pit_fine_grid` = 0.020000.
- **Expansion needed.** Define $A_i=\sqrt\rho Z+\sqrt{1-\rho}\,\varepsilon_i$, $Z,\varepsilon_i\stackrel{
  iid}{\sim}N(0,1)$; default iff $A_i<\Phi^{-1}(PD_{TTC})$ (calibrated so the unconditional default
  probability is $PD_{TTC}$ — show this calibration step too); condition on $Z$:
  $P(A_i<c\mid Z)=P(\sqrt{1-\rho}\,\varepsilon_i<c-\sqrt\rho Z\mid Z)=\Phi\big(\frac{c-\sqrt\rho Z}{
  \sqrt{1-\rho}}\big)$ using $\varepsilon_i\sim N(0,1)$ independent of $Z$; substitute $c=\Phi^{-1}(PD_{
  TTC})=-2.0537$ and each marked Z to reproduce all 6 table values exactly. Then prove
  $E_Z[PD_{PIT}(Z)]=PD_{TTC}$ by the tower property (unconditional default prob = $E_Z[P(\text{default}
  \mid Z)]$ = definition of $PD_{TTC}$'s calibration), and cross-check numerically against both fixture
  integration methods (Gauss–Hermite vs fine trapezoidal grid) landing on 0.020000.

### D-6. Jensen's inequality applied to ECL

- **Chapter.** Ch.6 (Scenarios & Jensen). **Flagged explicitly in the campaign brief.**
- **Source anchor.** A12, s9.2, THEOREM box, Fig. 6.
- **What's compressed.** States "ECL is a convex function of the macro state... hence
  $E[f(X)]\ge f(E[X])$" without proving Jensen's inequality itself or the convexity claim.
- **Fixture / values.** `tests/fixtures/compute_scenarios.py` — EAD=€100m, LGD=40%, PD_TTC=2%, ρ=0.12,
  $Z=(g-2.0)/1.5$; Upside g=+3.5% w=0.25, Base g=+2.0% w=0.50, Downside g=−2.5% w=0.25; targets
  `weighted_ecl_eurm`, `avg_path_ecl_eurm`, `understatement_pct`, `weighted_over_single_ratio`.
- **Expansion needed.** (a) Prove Jensen's inequality for convex $f$ via the supporting-line/tangent
  argument: for convex $f$, at any point $\mu$ there is a line $\ell(x)=f(\mu)+f'(\mu)(x-\mu)\le f(x)$
  for all $x$; take $\mu=E[X]$, apply expectation to both sides of $\ell(X)\le f(X)$, giving
  $f(E[X])\le E[f(X)]$. (b) Show $PD_{PIT}(Z)$ (from D-5) is convex in $Z$ over the relevant range by
  checking the sign of $\partial^2 PD_{PIT}/\partial Z^2$ (or numerically bracket it using the fixture's 6
  -point table). (c) Chain through $ECL(Z)=EAD\cdot LGD\cdot PD_{PIT}(Z)$ (linear rescaling preserves
  convexity) to conclude $ECL$ is convex in $Z$, hence in $g$. (d) Substitute all three scenarios'
  $g\to Z\to PD_{PIT}\to ECL$ chains with actual numbers, compute the probability-weighted average
  `weighted_ecl_eurm` = $0.25\,ECL_{up}+0.50\,ECL_{base}+0.25\,ECL_{down}$, compute the single-path
  average-growth ECL `avg_path_ecl_eurm` = $ECL(\bar g)$ with $\bar g=0.25(3.5)+0.50(2.0)+0.25(-2.5)$, and
  show the resulting gap is exactly the Jensen inequality's direction (weighted ≥ single-path), reproducing
  `understatement_pct` and `weighted_over_single_ratio`.

### D-7. NCL discounting — every cash flow's PV shown individually

- **Chapter.** Ch.4 (LGD & EAD, NCL sub-section).
- **Source anchor.** A18, s11.3, "Worked example — discounting a realised loss".
- **What's compressed.** The notes give a summary table of discounted values without showing each
  $DF(m)=(1+EIR)^{-m/12}$ computation.
- **Fixture / values.** `tests/fixtures/compute_ncl.py` — default UPB=€200,000, EIR=5.5%; recoveries: REO
  sale €170k@m20, MI €12k@m22, non-MI €2k@m23; expenses: taxes/insurance/maintenance €5k@m10,
  legal/foreclosure €4k@m16. Targets: `df_reo_m20`, `pv_reo_m20`, `df_mi_m22`, `pv_mi_m22`,
  `df_non_mi_m23`, `pv_non_mi_m23`, `df_taxes_m10`, `pv_taxes_m10`, `df_legal_m16`, `pv_legal_m16`, then
  `face_recoveries_eur`, `pv_recoveries_eur`, `pv_expenses_eur`, `face_loss_eur`, `face_severity_pct`,
  `discounted_loss_ncl_pv_eur`, `discounted_lgd_pct`, plus the nominal/accrued-interest comparison keys.
- **Expansion needed.** For each of the 5 cash flows individually: show $DF(m)=(1.055)^{-m/12}$ computed
  at its specific $m$, then $PV=\text{face}\times DF(m)$. Sum the 3 recovery PVs to `pv_recoveries_eur`,
  sum the 2 expense PVs to `pv_expenses_eur`, then `discounted_loss_ncl_pv_eur` = UPB − pv_recoveries +
  pv_expenses (confirm sign convention against the fixture), and `discounted_lgd_pct` =
  discounted_loss/UPB. Contrast against the *face* (undiscounted) severity to show the discounting effect
  is not cosmetic (the notes' own framing).

### D-8. Roll-rate bridge (90→180 DPD conversion, Route 2)

- **Chapter.** Ch.4 (LGD & EAD, 90/180-DPD sub-section).
- **Source anchor.** A19, s11.4, worked example.
- **What's compressed.** States $q_b=\text{fwd}/(\text{fwd}+\text{cure})$ and
  $R=q_{90}q_{120}q_{150}=0.60$ as a given without showing the per-bucket division or the chained
  multiplication.
- **Fixture / values.** `tests/fixtures/compute_rollrate.py` — roll-forward/cure pairs: 0.50/0.12 (90
  DPD), 0.55/0.10 (120 DPD), 0.60/0.08 (150 DPD). Targets: `q_eventual_rollforward_90dpd`,
  `q_eventual_rollforward_120dpd`, `q_eventual_rollforward_150dpd`, `roll_through_rate_R`, `pd_90_pct`,
  `lgd_90_cure_loss_free_pct`, `lgd_90_cure_loss_3pct_pct`, `el_180_pct`, `el_90_cure_loss_free_pct`,
  `el_90_cure_loss_3pct_pct`.
- **Expansion needed.** Compute each $q_b$ individually: $q_{90}=0.50/(0.50+0.12)$, $q_{120}=0.55/(0.55+
  0.10)$, $q_{150}=0.60/(0.60+0.08)$ — show the division and the resulting decimal at each step. Then
  $R=q_{90}\times q_{120}\times q_{150}$ shown as a 3-term product with running partial products, landing
  on 0.60. Then derive `pd_90_pct` from the D180-calibrated PD via $PD_{90}=PD_{180}/R$ (or the fixture's
  actual relationship — confirm direction from the code before writing), and show the two EL_90 cure-loss
  scenarios (loss-free vs 3%-cure-loss) as distinct LGD assumptions multiplied through to EL.

### D-9. Binomial exact backtest and the Jeffreys alternative

- **Chapter.** Ch.7 (Challengers & Validation).
- **Source anchor.** A21, s13.2, calibration-backtest worked example.
- **What's compressed.** States the p-value and critical count as results without deriving the exact
  binomial tail sum or the Jeffreys posterior.
- **Fixture / values.** `tests/fixtures/compute_validation.py` — n=1000, assigned PD=2%, observed d=28.
  Targets: `binomial_backtest_p_value`, `binomial_rejects_at_5pct`, `binomial_critical_count`,
  `jeffreys_p_value`, `jeffreys_rejects_at_5pct`.
- **Expansion needed.** Define $H_0$: true PD ≤ 2% (H₀/H₁ table per the recipe's hypothesis-test format).
  Show $p=P(D\ge 28)=1-\sum_{k=0}^{27}\binom{1000}{k}(0.02)^k(0.98)^{1000-k}$ (state as the survival
  function of Binomial(1000, 0.02), evaluated numerically — cite scipy's implementation, don't hand-expand
  the sum). Derive `binomial_critical_count` as the smallest $d^*$ with $P(D\ge d^*)\le0.05$. For Jeffreys:
  derive the Beta(d+½, n−d+½) posterior from a Beta(½,½) prior and Binomial(n,PD) likelihood (conjugacy),
  then the one-sided test $P(\theta\ge0.02\mid\text{data})$ from the posterior CDF, substituting d=28,
  n=1000.

### D-10. PSI — full band-by-band expansion

- **Chapter.** Ch.7 (Challengers & Validation).
- **Source anchor.** A21, s13.3, "Worked example — PSI" (already partially shown in source, but the sum
  is compressed).
- **Fixture / values.** `tests/fixtures/compute_validation.py` — development shares
  $[0.10,0.25,0.30,0.25,0.10]$ vs current $[0.06,0.20,0.30,0.28,0.16]$; targets `psi_term_band1`…`band5`,
  `psi_total`, `psi_is_stable`.
- **Expansion needed.** For each of the 5 bands, show $(\text{Actual}_i-\text{Expected}_i)\ln(
  \text{Actual}_i/\text{Expected}_i)$ computed individually with the actual numbers substituted
  (e.g. band 1: $(0.06-0.10)\ln(0.06/0.10)$), then sum all 5 terms to `psi_total`, then apply the standard
  PSI stability bands (<0.10 stable / 0.10–0.25 moderate shift / >0.25 significant shift) to justify
  `psi_is_stable`.

### D-11. Gross-up factor across the 4 horizons

- **Chapter.** Ch.2 (ECL Mechanics, horizon sub-section).
- **Source anchor.** A14, s9.4, "grossing up to lifetime" worked example.
- **Fixture / values.** `tests/fixtures/compute_grossup.py` — 7-year loan, hazard PIT-elevated for 3 years
  (R&S window) then reverting to 1.5% TTC; horizons {12,36,60,84} months. Targets per horizon:
  `cum_pd_{m}m_pct`, `gross_up_{m}m_to_life`, `ecl_{m}m`.
- **Expansion needed.** Show the hazard path itself (PIT-elevated λ for months 1–36, then 1.5% flat);
  compute cumulative PD at each of the 4 horizons via the survival-product definition (link back to D-1);
  compute the gross-up ratio $\text{gross\_up}_m=\text{cum\_PD}_{84}/\text{cum\_PD}_m$ individually for
  each horizon; show why the ratio shrinks as $m\to84$ (the reference horizon).

---

## Backlog summary

| # | Derivation | Chapter | Fixture |
|---|---|---|---|
| D-1 | Survival function from hazard | Ch.2 | compute_ecl.py |
| D-2 | Full 5-year ECL worked example | Ch.2 | compute_ecl.py |
| D-3 | Cloglog link from continuous-time hazard | Ch.3 | (none — architecture) |
| D-4 | Merton distance-to-default | Ch.3 | compute_pd.py |
| D-5 | One-factor Gaussian copula → PD_PIT(Z) | Ch.5 | compute_vasicek.py |
| D-6 | Jensen's inequality applied to ECL | Ch.6 | compute_scenarios.py |
| D-7 | NCL discounting, cash-flow by cash-flow | Ch.4 | compute_ncl.py |
| D-8 | Roll-rate bridge (90→180 DPD) | Ch.4 | compute_rollrate.py |
| D-9 | Binomial backtest + Jeffreys | Ch.7 | compute_validation.py |
| D-10 | PSI band-by-band | Ch.7 | compute_validation.py |
| D-11 | Gross-up factor, 4 horizons | Ch.2 | compute_grossup.py |

11 derivations flagged for full step-by-step expansion, spanning all 8 golden-fixture files and 6 of the
13 chapters (Ch.2, Ch.3, Ch.4, Ch.5, Ch.6, Ch.7).
