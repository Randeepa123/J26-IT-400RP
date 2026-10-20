"""
test_api.py - tests for the dashboard API (api_server.py) and the dashboard data cache.  Run:  python tests/test_api.py
"""
import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "component3"))
import warnings
warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient

import paths
import api_server as api

C = TestClient(api.app)
P = api.P


def get(url, **params):
    r = C.get(url, params=params)
    assert r.status_code == 200, (url, r.status_code, r.text[:200])
    return r.json()


class TestPlanEndpoints(unittest.TestCase):
    def test_health_and_meta(self):
        self.assertEqual(get("/health")["status"], "ok")
        self.assertIn("hybrid", get("/health")["models"])
        m = get("/meta")[0]
        self.assertAlmostEqual(m["floor_masl"], 204.0); self.assertAlmostEqual(m["reserve_pct"], 20.0)

    def test_plan_shape_and_constraints(self):
        rows = get("/plan")
        self.assertEqual(len(rows), 15)
        for r in rows:
            self.assertLessEqual(r["release_m3s"], r["turbine_cap_m3s"] + 1e-6)
            self.assertGreaterEqual(r["level_masl"], P.floor_level - 1e-6)
            self.assertLessEqual(r["level_masl"], P.FSL + 1e-6)
            self.assertGreaterEqual(r["storage_pct"], -1e-6); self.assertLessEqual(r["storage_pct"], 100 + 1e-6)
            self.assertLessEqual(r["generation_mwh"], P.max_daily_mwh + 1e-6)
        self.assertEqual(rows[0]["day"], 1)
        self.assertEqual(rows[0]["date"], __import__("datetime").date.today().isoformat())      # aligned to today by default
        self.assertEqual(get("/plan", align="forecast")[0]["date"], "2026-10-18")

    def test_inputs_change_the_outputs(self):
        base = get("/plan/summary")[0]
        self.assertAlmostEqual(base["start_storage_pct"], 60.0)
        one = get("/plan/summary", units=1)[0]
        self.assertLess(one["release_m3s"], base["release_m3s"])                                 # fewer units -> lower capacity
        dry = get("/plan/summary", inflow_scale=0.3)[0]
        self.assertLess(dry["plan_energy_mwh"], base["plan_energy_mwh"])                         # drier -> less energy
        hi = get("/plan/summary", storage_pct=95, method="rolling_lp")[0]
        lo = get("/plan/summary", storage_pct=25, method="rolling_lp")[0]
        self.assertGreaterEqual(hi["plan_energy_mwh"], lo["plan_energy_mwh"] - 1)                # more water -> not less energy
        self.assertNotEqual(get("/plan/summary", demand_scale=1.4)[0]["demand_weight"], base["demand_weight"])

    def test_input_clipping_and_no_floor_breach(self):
        s = get("/plan/summary", storage_pct=500, inflow_scale=99, p90_scale=-5, demand_scale=0, units=9, method="nonsense")[0]
        self.assertAlmostEqual(s["start_storage_pct"], 100.0)
        self.assertEqual(s["floor_breach_days"], 0)
        for kw in (dict(storage_pct=0), dict(storage_pct=10, inflow_scale=0.2), dict(units=0)):
            self.assertEqual(get("/plan/summary", **kw)[0]["floor_breach_days"], 0)

    def test_methods_comparison(self):
        rows = get("/plan/methods")
        names = {r["method"] for r in rows}
        self.assertTrue({"Hybrid LP-DQN", "Rolling LP", "DQN"} <= names)
        self.assertTrue(all(r["floor_breach_days"] == 0 for r in rows))

    def test_matches_run_component3(self):
        """The API plan equals the file-based planner for the same inputs."""
        import run_component3 as rc3
        res = rc3.run_plan(str(paths.INFLOW_FORECAST_15D), str(paths.DEMAND_FORECAST_15D), str(paths.DEMAND_5Y_V2),
                           {"date": "2026-10-18", "storage_m3": 0.6 * P.S_max}, str(Path(sys.argv[0]).resolve().parent / "_tmp_api_check"),
                           hybrid=str(paths.MODELS_DIR / "hybrid_selected.zip"), dqn=str(paths.MODELS_DIR / "dqn_selected.zip"))
        s = get("/plan/summary", align="forecast")[0]
        self.assertAlmostEqual(s["release_m3s"], round(res["rec"]["turbine_release_m3s"], 2), places=2)
        self.assertAlmostEqual(s["generation_mwh"], round(res["rec"]["generation_mwh"], 1), places=1)
        import shutil
        shutil.rmtree(Path(sys.argv[0]).resolve().parent / "_tmp_api_check", ignore_errors=True)


class TestOtherEndpoints(unittest.TestCase):
    def test_live_endpoints_respond(self):
        st = get("/live/status")
        self.assertEqual(len(st), 1); self.assertIn(st[0]["inbox_status"], ("VALID", "REJECTED"))
        self.assertIsInstance(get("/live/log"), list)

    def test_tables(self):
        sb = get("/table/scoreboard")
        self.assertEqual(len(sb), 6)
        hy = [r for r in sb if r["method"] == "Hybrid LP-DQN"][0]
        rl = [r for r in sb if r["method"] == "Rolling LP"][0]
        self.assertGreater(hy["episode_score"], rl["episode_score"])
        self.assertEqual(get("/table/constraint_audit")[0]["floor_breach_days"], 0)
        self.assertEqual(C.get("/table/not_a_table").status_code, 404)
        self.assertEqual(len(get("/table/heatmap")), 54)

    def test_scenario_series(self):
        rows = get("/scenario/series", scenario_id="drought_el_nino", metric="storage_pct", methods="hybrid,rolling_lp")
        self.assertEqual(len(rows), 365)
        self.assertTrue({"time", "Hybrid LP-DQN", "Rolling LP"} <= set(rows[0]))
        self.assertEqual(C.get("/scenario/series", params=dict(metric="bad")).status_code, 400)
        self.assertGreater(len(get("/scenario/reference", scenario_id="flood_year")), 300)

    def test_cache_matches_final_report_numbers(self):
        """Dashboard scoreboard == saved evaluation (docs/FINAL_RESULTS_REPORT_V2.md source)."""
        import pandas as pd
        sb = {r["method"]: r for r in get("/table/scoreboard")}
        ref = pd.read_csv(paths.EVALUATION_DIR / "final" / "summary_by_method.csv").set_index("method")
        self.assertAlmostEqual(sb["Hybrid LP-DQN"]["energy_gwh"], ref.loc["hybrid", "energy_gwh"], places=2)
        self.assertAlmostEqual(sb["Rolling LP"]["episode_score"], ref.loc["rolling_lp", "episode_score"], places=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
