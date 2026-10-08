"""
test_v2_suite.py - automated tests for the Component 3 v2 stack (hydro_core, demand_events,
scenario_generator, sim_core, rolling_lp, kukule_env_v2). Run:  python test_v2_suite.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "component3"))
import numpy as np
import pandas as pd

import hydro_core as hc
import demand_events as de
import scenario_generator as sg
import sim_core as sm
import rolling_lp as rl
import rl_common as rc
from kukule_env_v2 import KukuleEnvV2, N_ACTIONS

P = hc.HydroParams.from_config()
BANK = sg.load_bank(str(Path(sg.BANK_DIR) / "val_bank.pkl"))
SUITE = sg.load_stress_suite()


class TestCore(unittest.TestCase):
    def test_config_floor_and_reserve(self):
        self.assertAlmostEqual(P.floor_level, 204.0); self.assertAlmostEqual(P.MOL, 204.0)
        self.assertGreaterEqual(P.S_reserve, P.S_floor); self.assertGreaterEqual(P.S_terminal, P.S_reserve)
        self.assertAlmostEqual(P.elevation(0.0), 204.0, places=6); self.assertAlmostEqual(P.elevation(P.S_max), 206.0, places=6)

    def test_step_mass_balance_and_bounds(self):
        rng = np.random.default_rng(0)
        S = 0.4 * P.S_max
        for _ in range(2000):
            v_in = float(rng.choice([0.0, 1e5, 1e6, 3e6, 3e7]))
            d = P.step(S, v_in, int(rng.integers(0, 3)), int(rng.integers(1, 13)), float(rng.uniform(0, 5e6)), 1.0)
            resid = abs(d["end_storage_m3"] - (S + v_in - P.evap_m3 - d["mandatory_release_m3"]
                                               - d["turbine_release_m3"] - d["spill_volume_m3"]))
            if S + v_in - P.evap_m3 >= 0:
                self.assertLess(resid, 1e-4)
            self.assertGreaterEqual(d["end_storage_m3"], P.S_floor - 1e-6)
            self.assertLessEqual(d["end_storage_m3"], P.S_max + 1e-6)
            self.assertLessEqual(d["turbine_release_m3"], d["turbine_cap_m3"] + 1e-6)
            self.assertLessEqual(d["generation_mwh"], P.max_daily_mwh + 1e-6)
            S = d["end_storage_m3"]

    def test_mandatory_release_served_first(self):
        d = P.step(1e6, 5e5, 2, 6, 1e9, 1.0)
        self.assertAlmostEqual(d["mandatory_release_m3"], P.mandatory_m3(6), places=3)
        self.assertEqual(d["unmet_mandatory_m3"], 0.0)

    def test_reserve_enforced_for_turbines(self):
        rng = np.random.default_rng(1)
        S = 0.6 * P.S_max
        for _ in range(1500):
            v_in = float(rng.choice([0.0, 2e5, 1e6, 3e6]))
            d = P.step(S, v_in, 2, int(rng.integers(1, 13)), 9e9, 1.0)       # always request max release
            w1 = max(0.0, S + v_in - P.evap_m3) - d["mandatory_release_m3"]
            self.assertGreaterEqual(d["end_storage_m3"], min(P.S_reserve, w1) - 1e-6)   # never pulled below reserve
            S = d["end_storage_m3"]

    def test_spill_split(self):
        d = P.step(P.S_max, 1e8, 2, 6, 1e9, 1.0)       # flood: turbines at cap -> all spill unavoidable
        self.assertGreater(d["spill_volume_m3"], 0); self.assertAlmostEqual(d["spill_avoidable_m3"], 0.0, places=3)
        d = P.step(P.S_max, 3e6, 2, 6, 0.0, 1.0)       # turbines idle while pond full -> avoidable spill
        self.assertGreater(d["spill_avoidable_m3"], 0)


class TestDemand(unittest.TestCase):
    def test_festival_uplift(self):
        self.assertGreater(de.event_multiplier("2025-05-12")[0], 1.1)       # Vesak
        self.assertGreater(de.event_multiplier("2025-12-25")[0], 1.1)       # Christmas
        self.assertLess(de.event_multiplier("2026-04-14")[0], 0.9)          # Avurudu suppression
        w = de.calendar_demand_weights(pd.date_range("2027-01-01", periods=365))
        self.assertGreaterEqual(w.min(), 0.8); self.assertLessEqual(w.max(), 1.5)

    def test_v2_demand_file(self):
        df = pd.read_csv(sg.DEMAND_V2_PATH, parse_dates=["date"])
        xmas = df[(df.date.dt.month == 12) & (df.date.dt.day.isin([24, 25, 26]))]
        self.assertGreater(xmas.demand_weight.mean(), 1.03)                  # festive uplift on average
        d25 = df[(df.date.dt.month == 12) & (df.date.dt.day == 25)]
        self.assertTrue((d25.daily_energy_consumption_mwh > d25.daily_energy_consumption_mwh_v1).all())
        ves = df[df.event_label == "vesak"]
        self.assertGreater(ves.demand_weight.mean(), 1.03)


class TestScenarios(unittest.TestCase):
    def test_hydrology_matches_dataset(self):
        self.assertLess(sg.verify_hydrology_reproduces_dataset(), 1e-3)

    def test_regime_statistics(self):
        d = SUITE["drought_el_nino"]; n = SUITE["test_year_real_sim"]; f = SUITE["flood_year"]
        self.assertLess(d.inflow_m3[:365].mean(), 0.6 * n.inflow_m3[:365].mean())
        self.assertGreater(f.inflow_m3[:365].max(), 1.5 * n.inflow_m3[:365].max())
        self.assertLess(SUITE["double_outage"].units[:365].min(), 1)
        self.assertGreater(SUITE["wide_forecast_spread"].fc90.mean() / SUITE["wide_forecast_spread"].fc50.mean(),
                           1.5 * n.fc90.mean() / n.fc50.mean())
        self.assertAlmostEqual(SUITE["forecast_bias_high"].fc50.mean() / n.fc50.mean(), 1.4 / 1.0, delta=0.4)

    def test_shapes_and_ranges(self):
        for s in BANK[:5] + list(SUITE.values()):
            self.assertEqual(s.fc50.shape, (len(s.dates), sg.H_FC)); self.assertEqual(len(s.inflow_m3), len(s.dates))
            self.assertTrue(np.isfinite(s.fc50).all() and np.isfinite(s.fc90).all())
            self.assertTrue((s.fc90 >= s.fc50 - 1e-3).all())
            self.assertGreaterEqual(s.units.min(), 0); self.assertLessEqual(s.units.max(), 2)


class TestEnv(unittest.TestCase):
    def setUp(self):
        self.env = KukuleEnvV2(P, BANK, seed=3)

    def test_gym_check_env(self):
        from stable_baselines3.common.env_checker import check_env
        check_env(self.env, warn=True)

    def test_floor_and_bounds_any_action_sequence(self):
        for mode in ("rand", 0, 10):
            obs, _ = self.env.reset(seed=11)
            done, n = False, 0
            while not done:
                a = int(self.env.np_random.integers(0, N_ACTIONS)) if mode == "rand" else mode
                obs, r, term, trunc, info = self.env.step(a)
                done = term or trunc; n += 1
                self.assertGreaterEqual(info["end_storage_m3"], P.S_floor - 1e-6)
                self.assertLessEqual(info["end_storage_m3"], P.S_max + 1e-6)
                self.assertTrue(np.isfinite(obs).all() and np.isfinite(r))
                self.assertTrue(((obs > -5) & (obs < 5)).all())
            self.assertEqual(n, 365); self.assertTrue(trunc and not term)

    def test_reset_reproducible(self):
        a, _ = self.env.reset(seed=5); b, _ = self.env.reset(seed=5)
        np.testing.assert_allclose(a, b)

    def test_no_future_leakage_in_observation(self):
        sc = BANK[0]
        t = 100
        o1 = rc.build_obs(P, sc, t, 0.5 * P.S_max, 0, 365)
        import copy
        sc2 = copy.deepcopy(sc)
        sc2.inflow_m3[t:] = sc2.inflow_m3[t:] * 7.0           # change TODAY and the whole future of true inflow
        o2 = rc.build_obs(P, sc2, t, 0.5 * P.S_max, 0, 365)
        np.testing.assert_allclose(o1, o2)                     # observation uses only the past + forecasts

    def test_episode_start_variety(self):
        starts = {(self.env.reset()[1]["scenario"], self.env.reset()[1]["start"]) for _ in range(30)}
        self.assertGreater(len(starts), 10)


class TestPolicies(unittest.TestCase):
    def test_rolling_lp_constraints_and_reserve(self):
        s = SUITE["test_year_real_sim"]
        df, m = sm.simulate(P, s, rl.RollingLPPolicy(), 0, 365, S0=0.5 * P.S_max)
        self.assertEqual(m["floor_breach_days"], 0); self.assertEqual(m["mass_balance_violation_days"], 0)
        self.assertEqual(m["unmet_mandatory_days"], 0)
        ref, mr = sm.simulate(P, s, sm.ReferenceRulePolicy(gauge=True), 0, 365, S0=0.5 * P.S_max)
        self.assertLessEqual(m["reserve_breach_pct"], 1.0)                  # reserve is a hard operating limit

    def test_omniscient_is_upper_bound_on_adjusted_energy(self):
        s = SUITE["test_year_real_sim"]
        _, mo = sm.simulate(P, s, rl.OmniscientLPPolicy(), 0, 365, S0=0.5 * P.S_max)
        _, mr = sm.simulate(P, s, rl.RollingLPPolicy(), 0, 365, S0=0.5 * P.S_max)
        self.assertGreaterEqual(mo["storage_adjusted_energy_gwh"], mr["storage_adjusted_energy_gwh"] - 0.5)
        self.assertEqual(mo["projected_actions"], 0)

    def test_policies_are_causal(self):
        s = SUITE["test_year_real_sim"]
        import copy
        s2 = copy.deepcopy(s)
        s2.inflow_m3[200:] = s2.inflow_m3[200:] * 5.0         # alter the future after day 200
        a, _ = sm.simulate(P, s, rl.RollingLPPolicy(), 0, 150, S0=0.5 * P.S_max)
        b, _ = sm.simulate(P, s2, rl.RollingLPPolicy(), 0, 150, S0=0.5 * P.S_max)
        np.testing.assert_allclose(a["request_m3"].values, b["request_m3"].values)


class TestDailyRunner(unittest.TestCase):
    """Daily / continuous mode: planning, change detection, input validation, log, latest-plan preservation."""

    def setUp(self):
        import tempfile, daily_runner as dr
        self.dr = dr
        self.tmp = tempfile.mkdtemp()
        self.inbox, self.root = str(Path(self.tmp) / "in"), str(Path(self.tmp) / "out")
        dr.init_demo(self.inbox)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, **kw):
        return self.dr.run_once(self.inbox, self.root, settle=0.0, quiet=True, **kw)

    def _edit_state(self, **kv):
        import json
        f = Path(self.inbox) / "state.json"
        d = json.loads(f.read_text()); d.update(kv); f.write_text(json.dumps(d))

    def test_plan_unchanged_replan_and_log(self):
        self.assertEqual(self._run(), "PLANNED")
        for name in ("recommendation.json", "schedule_rolling_lp.csv", "status_report.html"):
            self.assertTrue((Path(self.root) / "latest" / name).exists())
        self.assertEqual(self._run(), "UNCHANGED")                       # same inputs -> no re-plan
        self._edit_state(storage_m3=900000)
        self.assertEqual(self._run(), "PLANNED")                         # changed inputs -> re-plan
        self.assertEqual(self._run(force=True), "PLANNED")               # forced
        log = pd.read_csv(Path(self.root) / "decision_log.csv")
        self.assertEqual(list(log.status), ["PLANNED", "PLANNED", "PLANNED"])
        self.assertEqual(len(list((Path(self.root) / "history").iterdir())), 3)

    def test_bad_inputs_rejected_and_previous_plan_kept(self):
        import json
        self.assertEqual(self._run(), "PLANNED")
        before = (Path(self.root) / "latest" / "recommendation.json").read_text()
        self._edit_state(storage_m3=99999999)                            # physically impossible
        self.assertEqual(self._run(), "REJECTED")
        self._edit_state(storage_m3=900000, date="2025-01-01")           # stale state
        self.assertEqual(self._run(), "REJECTED")
        (Path(self.inbox) / "inflow_forecast.csv").write_text("date,foo\n2026-10-18,1\n")   # broken forecast
        self._edit_state(date="2026-10-18")
        self.assertEqual(self._run(), "REJECTED")
        self.assertEqual((Path(self.root) / "latest" / "recommendation.json").read_text(), before)
        log = pd.read_csv(Path(self.root) / "decision_log.csv")
        self.assertEqual(list(log.status), ["PLANNED", "REJECTED", "REJECTED", "REJECTED"])
        st = json.loads((Path(self.root) / "status.json").read_text())
        self.assertTrue(st["last_rejection_reason"])

    def test_missing_state_rejected(self):
        (Path(self.inbox) / "state.json").unlink()
        self.assertEqual(self._run(), "REJECTED")

    def test_short_units_list_is_padded(self):
        self._edit_state(units_available=[2, 1])
        self.assertEqual(self._run(), "PLANNED")                         # used to mis-size the unit array


if __name__ == "__main__":
    unittest.main(verbosity=2)
