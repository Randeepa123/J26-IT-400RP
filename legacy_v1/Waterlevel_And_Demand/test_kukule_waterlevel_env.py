"""
test_kukule_waterlevel_env.py
=============================
Automated Unit and Integration Test Suite for KukuleWaterLevelEnv (Gymnasium).
Component: Component 3 - Hydropower Generation & Reservoir Release Optimization Subsystem

Test Coverage:
--------------
1. TEST-01: Environment Initialization & Space Specifications (Discrete 11, Box 5)
2. TEST-02: Gymnasium API Compliance (gymnasium.utils.env_checker.check_env)
3. TEST-03: Reset Dynamics & Initial State Verification
4. TEST-04: Step Return Structure, Types, and Normalization
5. TEST-05: Strict Daily Water Balance Mass Conservation (|Residual| < 1e-4 m³)
6. TEST-06: Active Pond Storage Bound Enforcement (0 <= S_t <= S_max)
7. TEST-07: Dynamic Turbine Discharge Limits (0 <= V_turb <= V_turb_max(u_t))
8. TEST-08: Spillway Non-Negativity & Excess Water Spilling
9. TEST-09: Station Electrical Capacity Ceiling Enforcement (E_phys <= 1,680.0 MWh)
10. TEST-10: Insufficient Water Handling (Zero invented water, no negative storage)
11. TEST-11: Full Episode Horizon Termination (Dev: 1461 steps, Test: 365 steps)
12. TEST-12: Deterministic Trajectory Reproducibility (Fixed seed parity)

Author: Antigravity Research Pipeline
Date  : October 2026
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium.utils.env_checker import check_env

from kukule_waterlevel_env import KukuleWaterLevelEnv


class TestKukuleWaterLevelEnv(unittest.TestCase):
    """Rigorous test suite for the Kukule Ganga Gymnasium environment."""

    @classmethod
    def setUpClass(cls):
        """Set up environments for development (training) and test (evaluation) splits."""
        cls.env_dev = KukuleWaterLevelEnv(split="dev")
        cls.env_test = KukuleWaterLevelEnv(split="test")

    def test_01_initialization_and_spaces(self):
        """TEST-01: Verify action space, observation space, and split dimensions."""
        # Action space: Discrete(11) -> 0%, 10%, ..., 100%
        self.assertIsInstance(self.env_dev.action_space, gym.spaces.Discrete)
        self.assertEqual(self.env_dev.action_space.n, 11)

        # Observation space: Box(5,)
        self.assertIsInstance(self.env_dev.observation_space, gym.spaces.Box)
        self.assertEqual(self.env_dev.observation_space.shape, (5,))
        self.assertEqual(self.env_dev.observation_space.dtype, np.float32)

        # Split lengths: Dev = 1461 days (4 years), Test = 365 days (1 year)
        self.assertEqual(self.env_dev.num_steps, 1461, f"Expected 1461 days in dev split, got {self.env_dev.num_steps}")
        self.assertEqual(self.env_test.num_steps, 365, f"Expected 365 days in test split, got {self.env_test.num_steps}")
        print("  [PASS] TEST-01: Initialization & Space Specifications (Discrete 11, Box 5, 1461d Dev / 365d Test)")

    def test_02_gymnasium_api_compliance(self):
        """TEST-02: Verify full adherence to Gymnasium API standards using official check_env."""
        # Use a fresh test split environment to check API compliance quickly
        test_env = KukuleWaterLevelEnv(split="test")
        # check_env will raise an exception or warning if API is violated
        check_env(test_env)
        print("  [PASS] TEST-02: Official Gymnasium check_env passed with 100% API compliance")

    def test_03_reset_dynamics(self):
        """TEST-03: Verify reset behavior, initial storage, and observation validity."""
        obs, info = self.env_dev.reset(seed=42)

        self.assertTrue(self.env_dev.observation_space.contains(obs), "Reset observation outside observation_space bounds!")
        self.assertEqual(self.env_dev.current_step, 0)
        self.assertEqual(self.env_dev.current_storage, self.env_dev.S_max)
        self.assertIn("initial_storage_m3", info)
        self.assertEqual(info["initial_storage_m3"], self.env_dev.S_max)
        self.assertEqual(info["date"], "2021-10-19")
        print(f"  [PASS] TEST-03: Reset Dynamics (S_0 = {info['initial_storage_m3']:,.1f} m³, Valid Observation)")

    def test_04_step_return_structure(self):
        """TEST-04: Verify step outputs structure, types, reward bounds, and info dictionary."""
        self.env_dev.reset(seed=42)
        action = 5  # 50% release
        obs, reward, terminated, truncated, info = self.env_dev.step(action)

        self.assertTrue(self.env_dev.observation_space.contains(obs))
        self.assertIsInstance(reward, float)
        self.assertGreaterEqual(reward, 0.0)
        self.assertLessEqual(reward, 1.0)
        self.assertIsInstance(terminated, bool)
        self.assertIsInstance(truncated, bool)
        self.assertIsInstance(info, dict)

        # Check required diagnostic keys
        required_keys = [
            "step", "date", "inflow_volume_m3", "beginning_storage_m3",
            "turbine_release_m3", "spill_volume_m3", "end_storage_m3",
            "pond_level_masl", "active_storage_pct", "net_head_m",
            "generation_mwh", "operating_units", "water_balance_residual_m3"
        ]
        for k in required_keys:
            self.assertIn(k, info, f"Missing key '{k}' in step info dict")

        print(f"  [PASS] TEST-04: Step Return Structure & Bounded Reward (Reward = {reward:.4f} in [0, 1])")

    def test_05_water_balance_continuity(self):
        """TEST-05: Verify exact daily mass conservation across 100 consecutive random steps."""
        self.env_dev.reset(seed=123)
        max_residual = 0.0

        for _ in range(100):
            action = self.env_dev.action_space.sample()
            obs, reward, terminated, truncated, info = self.env_dev.step(action)

            s_begin = info["beginning_storage_m3"]
            v_in = info["inflow_volume_m3"]
            v_turb = info["turbine_release_m3"]
            v_spill = info["spill_volume_m3"]
            s_end = info["end_storage_m3"]
            v_loss = self.env_dev.daily_evap_m3

            # Exact mass continuity equation: S_t = S_{t-1} + V_in - V_turb - V_spill - V_loss
            expected_end = s_begin + v_in - v_turb - v_spill - v_loss
            residual = abs(s_end - expected_end)
            if residual > max_residual:
                max_residual = residual

            self.assertLess(residual, 1e-4, f"Water balance violated! Residual: {residual:.8f} m³")

        print(f"  [PASS] TEST-05: Daily Mass Conservation (Max residual across 100 steps: {max_residual:.10f} m³ < 1e-4)")

    def test_06_active_storage_bounds(self):
        """TEST-06: Verify storage stays strictly within [0, S_max] across varied actions."""
        self.env_dev.reset(seed=456)
        s_max = self.env_dev.S_max

        for _ in range(150):
            action = self.env_dev.action_space.sample()
            _, _, _, _, info = self.env_dev.step(action)
            s_end = info["end_storage_m3"]

            self.assertGreaterEqual(s_end, 0.0, f"Storage went negative: {s_end} < 0")
            self.assertLessEqual(s_end, s_max + 1e-4, f"Storage exceeded maximum: {s_end} > {s_max}")

        print(f"  [PASS] TEST-06: Active Storage Bounds ([0.0, {s_max:,.1f}] m³ strictly enforced)")

    def test_07_turbine_discharge_limits(self):
        """TEST-07: Verify turbine discharge never exceeds unit hydraulic limit."""
        self.env_dev.reset(seed=789)

        for _ in range(150):
            action = self.env_dev.action_space.sample()
            _, _, _, _, info = self.env_dev.step(action)

            v_turb = info["turbine_release_m3"]
            u_t = info["operating_units"]
            v_turb_max = u_t * self.env_dev.Q_unit_rated * 86400.0

            self.assertGreaterEqual(v_turb, 0.0, f"Turbine release negative: {v_turb}")
            self.assertLessEqual(v_turb, v_turb_max + 1.0, f"Turbine release {v_turb} exceeded capacity {v_turb_max}")

        print("  [PASS] TEST-07: Dynamic Turbine Discharge Limits strictly enforced across 1-unit and 2-unit states")

    def test_08_spillway_non_negativity_and_excess_spill(self):
        """TEST-08: Verify spillway release is non-negative and properly discharges excess water."""
        self.env_dev.reset(seed=101)

        # Force 0% release (action=0) during high-flow days to test mandatory weir spill
        spill_observed = False
        for _ in range(50):
            _, _, _, _, info = self.env_dev.step(0)  # zero turbine release
            v_spill = info["spill_volume_m3"]
            self.assertGreaterEqual(v_spill, 0.0)
            if v_spill > 0.0:
                spill_observed = True
                # When spilling occurs with action=0, storage must be at S_max
                self.assertAlmostEqual(info["end_storage_m3"], self.env_dev.S_max, delta=1.0)

        self.assertTrue(spill_observed, "Expected spillway overflow when holding 0% release over 50 days")
        print("  [PASS] TEST-08: Spillway Non-Negativity & Excess Overflow Handling verified")

    def test_09_station_electrical_capacity_ceiling(self):
        """TEST-09: Verify physical generation never exceeds 70 MW continuous ceiling (1,680 MWh/day)."""
        self.env_dev.reset(seed=202)

        for _ in range(150):
            # Test 100% full-gate release (action=10)
            _, _, _, _, info = self.env_dev.step(10)
            gen = info["generation_mwh"]
            u_t = info["operating_units"]
            max_ceiling = u_t * self.env_dev.unit_cap_mw * 24.0  # 1680 MWh for 2 units, 840 MWh for 1 unit

            self.assertGreaterEqual(gen, 0.0)
            self.assertLessEqual(gen, max_ceiling + 1e-4, f"Generation {gen} exceeded electrical ceiling {max_ceiling}")

        print("  [PASS] TEST-09: Station Electrical Capacity Ceiling strictly respected (Max observed <= 1,680.0 MWh)")

    def test_10_insufficient_water_handling(self):
        """TEST-10: Verify environment caps release at available water and never invents water."""
        # Initialize with nearly empty storage
        env_dry = KukuleWaterLevelEnv(split="test", initial_storage_m3=1000.0)
        env_dry.reset(seed=303)

        # Request 100% release (action=10) on a low-water state
        for _ in range(5):
            _, _, _, _, info = env_dry.step(10)
            # Storage must NEVER become negative
            self.assertGreaterEqual(info["end_storage_m3"], 0.0)
            # Released water must not exceed (starting storage + inflow)
            max_possible = info["beginning_storage_m3"] + info["inflow_volume_m3"]
            self.assertLessEqual(info["turbine_release_m3"] + info["spill_volume_m3"], max_possible + 1e-4)

        print("  [PASS] TEST-10: Insufficient Water Handling (Zero invented water, zero negative storage)")

    def test_11_full_episode_termination(self):
        """TEST-11: Verify episode termination exactly matches the calendar split length."""
        # Test 1-year evaluation split (365 days)
        env_eval = KukuleWaterLevelEnv(split="test")
        env_eval.reset(seed=404)

        done = False
        steps = 0
        while not done:
            _, _, terminated, truncated, _ = env_eval.step(5)
            steps += 1
            done = terminated or truncated

        self.assertEqual(steps, 365, f"Expected exactly 365 steps in test split, got {steps}")
        self.assertTrue(terminated)
        print(f"  [PASS] TEST-11: Full Episode Horizon Termination (Terminated at exactly step {steps}/365)")

    def test_12_reproducibility(self):
        """TEST-12: Verify deterministic identical trajectories with identical seeds."""
        env1 = KukuleWaterLevelEnv(split="test")
        env2 = KukuleWaterLevelEnv(split="test")

        obs1, _ = env1.reset(seed=999)
        obs2, _ = env2.reset(seed=999)
        np.testing.assert_allclose(obs1, obs2, err_msg="Reset observations differ under identical seed")

        actions = [0, 3, 7, 10, 5, 2, 8, 10, 1, 4]
        for a in actions:
            o1, r1, t1, tr1, i1 = env1.step(a)
            o2, r2, t2, tr2, i2 = env2.step(a)

            np.testing.assert_allclose(o1, o2, err_msg="Observations diverged")
            self.assertEqual(r1, r2, "Rewards diverged")
            self.assertEqual(t1, t2, "Termination flags diverged")
            self.assertEqual(i1["end_storage_m3"], i2["end_storage_m3"], "Storage diverged")
            self.assertEqual(i1["generation_mwh"], i2["generation_mwh"], "Generation diverged")

        print("  [PASS] TEST-12: Deterministic Trajectory Reproducibility (Exact parity under identical seeds)")


def run_all_tests():
    """Run full test suite and return success status."""
    print("=" * 75)
    print("RUNNING KUKULE GANGA GYMNASIUM ENVIRONMENT VALIDATION SUITE (12 TESTS)")
    print("=" * 75)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestKukuleWaterLevelEnv)
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    print("\n" + "=" * 75)
    if result.wasSuccessful():
        print(f"ALL {result.testsRun} TESTS PASSED SUCCESSFULLY! ({result.testsRun}/{result.testsRun} PASS)")
    else:
        print(f"VALIDATION FAILED: {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests.")
    print("=" * 75)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
