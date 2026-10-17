# Held-Out Evaluation Report: Kukule Ganga Deep Q-Network (DQN)

**Subsystem:** Hydropower Generation and Reservoir Release Optimization Subsystem (Component 3)  
**Target Station:** Kukule Ganga Power Station, Sabaragamuwa Province, Sri Lanka  
**Evaluated Model:** `dqn_kukule_final.zip`  
**Model Location:** `G:\SLIIT\Research\Kukule_Ganga Demo\Waterlevel_And_Demand\outputs\dqn\run_50000steps_20261020_114852\dqn_kukule_final.zip`  
**Evaluation Window:** `2025-10-19` to `2026-10-18` (365 calendar days, Held-Out Test Split)  
**Evaluation Mode:** Strictly Deterministic Greedy Inference (`deterministic=True`)  
**Data Isolation:** Strictly zero training, fine-tuning, or hyperparameter updates on test period.

---

## 1. Executive Summary & Verdict

The Deep Q-Network (DQN) agent trained for 50,000 timesteps exclusively on the Development Split (`2021-10-19` to `2025-10-18`) was evaluated across the complete 365-day held-out test split.

### Key Performance Numbers:
* **Total Physical Electrical Generation:** **233.2666 GWh** (Mean daily: **639.09 MWh/day**)
* **Annual Station Capacity Factor:** **38.04 %**
* **Total Water Dispatched through Turbines:** **537.3513 MCM**
* **Total Spillway Overflow:** **372.7846 MCM**
* **Terminal Reservoir Storage ($S_T$):** **0.0000 MCM** (Drawdown $\Delta S = -1.6700\text{ MCM}$)
* **Turbine Water Conversion Productivity:** **434.10 MWh/MCM**

---

## 2. Side-by-Side Benchmark Scorecard

| metric_name | reference_rule_curve | dqn_agent | omniscient_lp_ceiling | dqn_vs_ref_diff | dqn_vs_ref_pct | dqn_vs_lp_diff | engineering_interpretation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Calendar Evaluation Days | 365.00 | 365.00 | 365.00 | 0.00 | +0.0% | 0.00 | Identical 1-year test horizon |
| Initial Storage S_0 (MCM) | 1.67 | 1.67 | 1.67 | 0.00 | +0.0% | 0.00 | All models start at full pondage (1.67 MCM) |
| Terminal Storage S_T (MCM) | 0.22 | 0.00 | 1.67 | -0.22 | -100.0% | -1.67 | LP enforces S_T >= 1.67; Reference ends depleted at 0.22 |
| Net Storage Change ΔS (MCM) | -1.45 | -1.67 | 0.00 | -0.22 | N/A | -1.67 | Water borrowed from / retained in storage |
| Turbine Release Volume (MCM) | 577.96 | 537.35 | 572.30 | -40.60 | -7.03% | -34.95 | Total volume routed through turbines |
| Spillway Overflow Volume (MCM) | 331.96 | 372.78 | 336.17 | 40.82 | +12.30% | 36.62 | Uncaptured weir overflow |
| Evaluated Physical Generation (GWh) | 245.17 | 233.27 | 249.17 | -11.90 | -4.86% | -15.90 | Exact non-linear physical generation |
| Capacity Factor (%) | 39.98 | 38.04 | 40.63 | -1.94 | -1.94% | -2.59 | Annual capacity factor based on 70 MW rating |
| Turbine Water Productivity (MWh/MCM) | 424.20 | 434.10 | 435.39 | 9.90 | +2.33% | -1.29 | Conversion efficiency: higher head yields higher MWh/MCM |
| Terminal Stored Potential Energy (GWh) | 0.09 | 0.00 | 0.71 | -0.09 | N/A | -0.71 | Value of water preserved for subsequent cycle |
| Total System Energy Equivalent (GWh) | 245.26 | 233.27 | 249.88 | -12.00 | -4.89% | -16.62 | Generation + Terminal Potential Energy |

---

## 3. Physical Feasibility & Mass Balance Audit

1. **Daily Water Balance Continuity:**
   * Maximum daily mass continuity residual: **`0.0000000100 m³`** (strictly within $10^{-4}	ext{ m³}$ tolerance).
   * Cumulative 365-day volumetric balance error: **`0.0000 m³`**.
2. **Physical Boundary Checks:**
   * Active Storage Bounds $[0.0, 1.67\text{ MCM}]$: **0 Violations** (100% compliant).
   * Dynamic Turbine Discharge Limits: **0 Violations** (Releases strictly bounded by operational units $u_t$).
   * Continuous Electrical Capacity Ceiling ($1,680.0\text{ MWh/day}$): **0 Violations**.
3. **Statutory Environmental Flow Compliance ($2.0\text{ m³}/\text{s}$):**
   * Total unmet downstream release: **1,209,600.0 m³** across **7 days**.

---

## 4. Policy Behavior Analysis

### What the Agent Learned:
* **Generation Consistency:** The DQN agent successfully learned to operate the powerhouse across a full 365-day unseen hydrological cycle, generating **233.27 GWh** (95.1% of the tuned reference policy).
* **Turbine Loading:** During high-flow periods, the agent consistently selected actions near full capacity ($90\%-100\%$), avoiding unnecessary throttling during peak runoff.

### Gaps Observed in Initial 50k-Step Policy:
* **Elevated Spillway Overflow:** The agent discharged **372.78 MCM** over the weir, compared to $331.96\text{ MCM}$ for the reference policy and $336.17\text{ MCM}$ for the LP. Because the initial reward function ($R = E_{\text{phys}} / 1680.0$) contains no direct spill penalty, the agent did not learn to pre-drain storage ahead of high-flow days to absorb excess water.
* **Terminal Storage Drawdown:** The agent ended the year at **0.00 MCM** ($0.0\%$ of active capacity). Without a terminal storage penalty or potential-based reward shaping, the agent harvested stored water during late-season dry spells without leaving reserve pondage for the subsequent hydrological cycle.

---

## 5. Fair Comparison Disclosures

1. **Comparison with Reference Rule Curve:**
   * The Reference Policy generated **245.17 GWh** vs. DQN's **233.27 GWh** (Difference: **-11.90 GWh**).
   * Both policies operate **strictly causally** without future inflow lookahead.
   * The Reference Policy achieves higher generation because its deterministic heuristic incorporates a dedicated buffer threshold ($S_{\text{target}} = 0.35 S_{\max}$) that preserves higher operating head during low flows.
2. **Comparison with Omniscient LP:**
   * The Linear Program generated **249.17 GWh** with full terminal storage preservation ($S_T = 1.67\text{ MCM}$).
   * As audited, the LP has **perfect foresight of future inflows** across the entire time horizon, enabling optimal pre-flood storage releases that causal real-time policies cannot safely execute.
   * The LP represents the **Theoretical Performance Ceiling**, not a deployable real-time controller.

---

## 6. Generated Visualizations

* **Generation Comparison Chart:** `G:\SLIIT\Research\Kukule_Ganga Demo\Waterlevel_And_Demand\outputs\dqn\run_50000steps_20261020_114852\eval_test_20261020_115912\dqn_vs_baselines_generation.png`
* **Storage Trajectory Chart:** `G:\SLIIT\Research\Kukule_Ganga Demo\Waterlevel_And_Demand\outputs\dqn\run_50000steps_20261020_114852\eval_test_20261020_115912\dqn_vs_baselines_storage.png`
* **Water Allocation & Release Chart:** `G:\SLIIT\Research\Kukule_Ganga Demo\Waterlevel_And_Demand\outputs\dqn\run_50000steps_20261020_114852\eval_test_20261020_115912\dqn_vs_baselines_releases.png`

---

*Report certified by Antigravity Research Pipeline — Component 3 Optimization Subsystem.*
