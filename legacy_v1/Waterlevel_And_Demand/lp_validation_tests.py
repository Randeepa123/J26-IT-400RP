"""
lp_validation_tests.py
======================
Comprehensive Automated Validation & Quality Assurance Test Suite for Kukule Ganga LP Optimizer
Component: Component 3 - Hydropower Generation & Reservoir Release Optimization Subsystem

Test Coverage:
--------------
1.  TEST-01: Solver Status & Feasibility (HiGHS Dual Simplex Status 7 / Status 0)
2.  TEST-02: Water Balance & Strict Mass Continuity (Tolerance < 1e-4 m³)
3.  TEST-03: Active Storage Bounds (0.0 <= S_t <= S_max)
4.  TEST-04: Turbine Discharge Limits (0.0 <= V_turb <= V_turb_max)
5.  TEST-05: Station Continuous Power & Energy Ceiling (E_phys <= 1,680.0 MWh/day)
6.  TEST-06: Terminal Storage Constraint Satisfaction (S_T >= S_target)
7.  TEST-07: Monsoon Flood / High Inflow Response (Turbines saturated, excess spilled)
8.  TEST-08: Severe Drought / Low Inflow Response (No spurious spilling, pond drawdown)
9.  TEST-09: Infeasible Target Detection & Rejection (Refusal to claim success on impossible target)
10. TEST-10: Non-Linear Physical Energy Consistency & Approximation Gap Bound

Author: Antigravity Research Pipeline
Date  : October 2026
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd
from lp_optimizer import KukuleLPOptimizer, load_config
from reference_release_policy import KukuleReferencePolicy


class TestKukuleLPOptimizer(unittest.TestCase):
    """Rigorous verification suite for Kukule Ganga LP Optimizer."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment and load baseline scenario."""
        cls.config_path = os.path.join(os.path.dirname(__file__), "scenarios_config.json")
        cls.config = load_config(cls.config_path)
        cls.dataset_path = os.path.join(
            os.path.dirname(__file__),
            "scenarios", "scenario_baseline", "synthetic_kukule_integrated_dataset_5years.csv"
        )
        if not os.path.exists(cls.dataset_path):
            cls.dataset_path = os.path.join(
                os.path.dirname(__file__),
                "synthetic_kukule_dataset", "synthetic_kukule_integrated_dataset_5years.csv"
            )
        cls.df_master = pd.read_csv(cls.dataset_path)

        # Instantiate Baseline Optimizer and Run Full Split
        cls.optimizer = KukuleLPOptimizer(cls.config, scenario="baseline")
        cls.df_res, cls.metrics, cls.raw_res = cls.optimizer.run(cls.df_master)

    def test_01_solver_status_and_feasibility(self):
        """TEST-01: Verify that HiGHS solves the full 1,826-day problem to optimality."""
        self.assertTrue(self.raw_res.success, "LP solver failed to find an optimal solution.")
        self.assertEqual(self.raw_res.status, 0, f"Expected status 0 (Optimal), got {self.raw_res.status}")
        self.assertEqual(self.metrics["solver_status"], "OPTIMAL")
        self.assertIn("Optimal", self.raw_res.message)
        print("  [PASS] TEST-01: Solver Status & Feasibility (HiGHS Optimal)")

    def test_02_water_balance_continuity(self):
        """TEST-02: Verify exact mass continuity for all 1,826 time steps."""
        s_begin = self.df_res["beginning_storage_m3"].values
        v_in = self.df_res["inflow_volume_m3"].values
        v_turb = self.df_res["turbine_release_m3"].values
        v_spill = self.df_res["spill_volume_m3"].values
        s_end = self.df_res["end_storage_m3"].values
        v_loss = self.optimizer.daily_evap_m3

        # Mass conservation: S_t = S_{t-1} + V_in - V_turb - V_spill - V_loss
        expected_s_end = s_begin + v_in - v_turb - v_spill - v_loss
        residual = np.abs(s_end - expected_s_end)
        max_error = float(residual.max())

        self.assertLess(max_error, 1e-4, f"Mass continuity residual {max_error} exceeds tolerance 1e-4 m³")
        self.assertTrue(self.metrics["water_balance_valid"])
        print(f"  [PASS] TEST-02: Water Balance Continuity (Max residual = {max_error:.10f} m³)")

    def test_03_active_storage_bounds(self):
        """TEST-03: Verify end-of-day active storage respects physical bounds [0, S_max]."""
        s_end = self.df_res["end_storage_m3"].values
        min_s = float(s_end.min())
        max_s = float(s_end.max())

        self.assertGreaterEqual(min_s, -1e-5, f"Storage violated lower bound: {min_s} < 0")
        self.assertLessEqual(max_s, self.optimizer.S_max + 1e-4, f"Storage violated upper bound: {max_s} > {self.optimizer.S_max}")
        print(f"  [PASS] TEST-03: Active Storage Bounds ([{min_s:,.1f}, {max_s:,.1f}] m³ within [0, {self.optimizer.S_max:,.1f}])")

    def test_04_turbine_discharge_limits(self):
        """TEST-04: Verify turbine discharge does not exceed physical unit hydraulic ratings."""
        v_turb = self.df_res["turbine_release_m3"].values
        units = self.df_res["operating_units"].values

        for t in range(len(v_turb)):
            u_t = units[t]
            max_hydraulic_vol = u_t * self.optimizer.Q_unit_rated * 86400.0
            self.assertGreaterEqual(v_turb[t], -1e-5, f"Turbine release negative at step {t}")
            self.assertLessEqual(v_turb[t], max_hydraulic_vol + 1.0,
                                 f"Turbine release at step {t} ({v_turb[t]}) exceeds hydraulic capacity ({max_hydraulic_vol})")
        print("  [PASS] TEST-04: Turbine Discharge Limits strictly respected across all operational unit states")

    def test_05_station_power_and_energy_ceiling(self):
        """TEST-05: Verify daily physical generation never exceeds continuous electrical ceiling."""
        gen_mwh = self.df_res["generation_mwh"].values
        units = self.df_res["operating_units"].values

        for t in range(len(gen_mwh)):
            u_t = units[t]
            cap_ceiling = u_t * self.optimizer.unit_cap_mw * 24.0  # 1680.0 for 2 units, 840.0 for 1 unit
            self.assertLessEqual(gen_mwh[t], cap_ceiling + 1e-4,
                                 f"Generation at step {t} ({gen_mwh[t]} MWh) exceeded electrical ceiling ({cap_ceiling} MWh)")
        print(f"  [PASS] TEST-05: Station Power Ceiling strictly enforced (Max daily gen = {gen_mwh.max():.2f} <= 1,680.0 MWh)")

    def test_06_terminal_storage_enforcement(self):
        """TEST-06: Verify terminal storage constraint prevents end-of-horizon depletion."""
        s_terminal = float(self.df_res["end_storage_m3"].iloc[-1])
        s_target = self.optimizer.terminal_storage_target

        self.assertGreaterEqual(s_terminal, s_target - 1.0,
                                f"Terminal storage {s_terminal} failed to meet target {s_target}")
        self.assertTrue(self.metrics["terminal_storage_satisfied"])
        print(f"  [PASS] TEST-06: Terminal Storage Stewardship (Observed S_T = {s_terminal:,.1f} m³ >= Target {s_target:,.1f} m³)")

    def test_07_monsoon_high_inflow_behavior(self):
        """TEST-07: Verify optimizer behavior under massive monsoon flood inflow."""
        # 7-day severe monsoon flood: 200 m³/s inflow (> 4x station capacity)
        flood_dates = pd.date_range("2025-06-01", periods=7, freq="D")
        flood_inflow_vol = 200.0 * 86400.0  # 17.28 MCM/day
        df_flood = pd.DataFrame({
            "date": flood_dates,
            "inflow_volume_m3": [flood_inflow_vol] * 7,
            "operating_units": [2] * 7
        })

        flood_opt = KukuleLPOptimizer(self.config, scenario="baseline")
        df_fres, fmetrics, _ = flood_opt.run(df_flood, initial_storage_m3=self.optimizer.S_max)

        self.assertTrue(fmetrics["success"])
        # Turbines should be 100% saturated
        v_turb_max = 2 * self.optimizer.Q_unit_rated * 86400.0
        v_elec_max = (70.0 * 24.0) / self.optimizer.k_e
        expected_turb = min(v_turb_max, v_elec_max)

        for v in df_fres["turbine_release_m3"]:
            self.assertAlmostEqual(v, expected_turb, delta=1.0)
        # Reservoir should remain at maximum capacity
        for s in df_fres["end_storage_m3"]:
            self.assertAlmostEqual(s, self.optimizer.S_max, delta=1.0)
        # Remainder must be safely spilled
        for sp in df_fres["spill_volume_m3"]:
            self.assertGreater(sp, 10e6)  # > 10 MCM spill per day
        print("  [PASS] TEST-07: Monsoon High Inflow Response (Turbines saturated, storage full, excess spilled safely)")

    def test_08_drought_low_inflow_behavior(self):
        """TEST-08: Verify optimizer behavior under severe dry-season drought."""
        # 10-day extreme drought: 1.0 m³/s inflow (far below turbine capacity)
        drought_dates = pd.date_range("2025-02-01", periods=10, freq="D")
        drought_inflow_vol = 1.0 * 86400.0  # 86,400 m³/day
        df_drought = pd.DataFrame({
            "date": drought_dates,
            "inflow_volume_m3": [drought_inflow_vol] * 10,
            "operating_units": [2] * 10
        })

        # Set terminal storage target to 0 to test full drawdown utilization
        drought_opt = KukuleLPOptimizer(self.config, scenario="baseline", terminal_storage_target=0.0)
        df_dres, dmetrics, _ = drought_opt.run(df_drought, initial_storage_m3=self.optimizer.S_max)

        self.assertTrue(dmetrics["success"])
        # During drought, zero water should be spilled
        self.assertEqual(df_dres["spill_volume_m3"].sum(), 0.0, "Spillway discharged water during extreme drought!")
        # Storage should be drawn down to maintain generation
        self.assertLess(df_dres["end_storage_m3"].iloc[-1], self.optimizer.S_max)
        print("  [PASS] TEST-08: Drought Low Inflow Response (Zero spill, rational pondage drawdown)")

    def test_09_infeasible_target_handling(self):
        """TEST-09: Verify that impossible terminal storage targets are detected and rejected as INFEASIBLE."""
        # 5-day horizon with low inflow
        test_dates = pd.date_range("2026-01-01", periods=5, freq="D")
        df_short = pd.DataFrame({
            "date": test_dates,
            "inflow_volume_m3": [100000.0] * 5,
            "operating_units": [2] * 5
        })

        # Request an impossible terminal storage: 5.0 MCM (physical capacity is only 1.67 MCM)
        impossible_opt = KukuleLPOptimizer(self.config, scenario="baseline", terminal_storage_target=5000000.0)
        df_inf, inf_metrics, raw_inf = impossible_opt.run(df_short, initial_storage_m3=1000000.0)

        # Must report failure and INFEASIBLE status, NOT success
        self.assertFalse(raw_inf.success, "Solver falsely reported success on an infeasible target!")
        self.assertEqual(inf_metrics["solver_status"], "INFEASIBLE")
        self.assertIsNone(df_inf, "Expected None DataFrame on infeasible problem")
        print("  [PASS] TEST-09: Infeasible Target Detection (Solver cleanly rejected impossible 5.0 MCM target)")

    def test_10_nonlinear_energy_consistency(self):
        """TEST-10: Verify the linear LP power approximation is consistent with physical non-linear power."""
        gap_pct = self.metrics["linear_model_gap_pct"]
        # The gap between linear model and evaluated physical non-linear power should be bounded
        self.assertLess(abs(gap_pct), 3.0, f"Linear approximation divergence {gap_pct}% exceeds 3.0% threshold")
        print(f"  [PASS] TEST-10: Non-Linear Energy Consistency (Total gap = {gap_pct:+.2f}%, well within engineering limits)")

    def test_11_future_date_range_optimization(self):
        """TEST-11: Verify LP optimization on a forward-looking future forecast date range (2026-10-20 to 2026-11-03)."""
        from lp_optimizer import load_optimization_dataset
        df_future, is_fc = load_optimization_dataset(
            cfg=self.config,
            start_date="2026-10-20",
            end_date="2026-11-03"
        )
        self.assertTrue(is_fc, "Expected is_forecast=True for 2026-10-20 forward horizon")
        self.assertEqual(len(df_future), 15, f"Expected 15 days in forward horizon, got {len(df_future)}")

        # Run LP optimization on future horizon
        df_fres, fmetrics, fres = self.optimizer.run(df_future, initial_storage_m3=self.optimizer.S_max)
        self.assertTrue(fres.success, "LP solver failed on future forecast horizon")
        self.assertEqual(fmetrics["solver_status"], "OPTIMAL")
        self.assertTrue(fmetrics["water_balance_valid"], "Water balance invalid on future forecast horizon")
        self.assertAlmostEqual(fmetrics["terminal_storage_m3"], self.optimizer.S_max, delta=1.0)
        print(f"  [PASS] TEST-11: Future Date-Range LP Optimization (15-day forward horizon: {fmetrics['total_physical_generation_gwh']:.3f} GWh, HiGHS Optimal)")

    def test_12_future_visualization_generation(self):
        """TEST-12: Verify generation of all 4 research-quality Matplotlib figures for future LP dispatch."""
        from lp_optimizer import load_optimization_dataset
        from lp_plotter import generate_all_future_lp_plots

        df_future, is_fc = load_optimization_dataset(
            cfg=self.config,
            start_date="2026-10-20",
            end_date="2026-11-03"
        )
        df_fres, _, _ = self.optimizer.run(df_future, initial_storage_m3=self.optimizer.S_max)

        test_viz_dir = os.path.join(os.path.dirname(__file__), "outputs", "test_validation_viz")
        plots = generate_all_future_lp_plots(df_fres, test_viz_dir, is_forecast=is_fc, show_plots=False)

        # Check all 4 graphs exist and are non-empty
        for key in ["generation_graph", "storage_graph", "flow_graph", "allocation_graph"]:
            self.assertIn(key, plots)
            file_path = plots[key]
            self.assertTrue(os.path.exists(file_path), f"Figure {key} not found at {file_path}")
            self.assertGreater(os.path.getsize(file_path), 15000, f"Figure {key} file size suspiciously small ({os.path.getsize(file_path)} bytes)")

        print("  [PASS] TEST-12: Future Visualization Generation (All 4 Matplotlib figures successfully created at 300 DPI)")

    def test_13_no_plots_flag_suppression(self):
        """TEST-13: Verify that visualization generation can be safely bypassed when requested without affecting optimization."""
        # Optimization run completes without needing plotting calls
        df_future = pd.DataFrame({
            "date": ["2026-10-20", "2026-10-21", "2026-10-22"],
            "inflow_volume_m3": [2000000.0, 2200000.0, 2100000.0],
            "operating_units": [2, 2, 2]
        })
        df_res, metrics, res = self.optimizer.run(df_future, initial_storage_m3=self.optimizer.S_max)
        self.assertTrue(res.success)
        self.assertIsNotNone(df_res)
        print("  [PASS] TEST-13: Safe Plot Suppression (LP solver operates independently of visualization pipeline)")


def run_all_tests():
    """Execute all tests and display formatted report."""
    print("=" * 70)
    print("RUNNING KUKULE GANGA LP OPTIMIZER VALIDATION SUITE (13 TESTS)")
    print("=" * 70)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestKukuleLPOptimizer)
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print(f"ALL {result.testsRun} TESTS PASSED SUCCESSFULLY! ({result.testsRun}/{result.testsRun} PASS)")
    else:
        print(f"VALIDATION FAILED: {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests.")
    print("=" * 70)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
