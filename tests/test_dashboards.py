"""
test_dashboards.py - the generated Grafana dashboards are valid and every panel query is answered by the API.  Run:  python tests/test_dashboards.py
Checks: JSON validity, unique panel ids / dashboard uids, datasource wiring, a method colour for every method, and that EVERY query URL
(with the dashboard variables replaced by their default values) returns HTTP 200 and non-empty data from api_server.py.
"""
import re
import sys
import json
import unittest
import warnings
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "component3"))
warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient

import api_server as api

ROOT = Path(__file__).resolve().parents[1]
DASH = sorted((ROOT / "grafana" / "dashboards").glob("*.json"))
C = TestClient(api.app)


def default_vars(d):
    out = {}
    for v in d["templating"]["list"]:
        cur = v["current"]["value"]
        out[v["name"]] = ",".join(cur) if isinstance(cur, list) else str(cur)
    return out


def expand(text, vars_):
    text = re.sub(r"\$\{(\w+):csv\}", lambda m: vars_[m.group(1)], text)
    return re.sub(r"\$\{(\w+)\}", lambda m: vars_[m.group(1)], text)


class TestDashboards(unittest.TestCase):
    def test_three_dashboards_exist_and_parse(self):
        self.assertEqual([p.name for p in DASH], ["1_live_plan.json", "2_results.json", "3_scenario_explorer.json"])
        uids = [json.loads(p.read_text(encoding="utf-8"))["uid"] for p in DASH]
        self.assertEqual(sorted(uids), ["kg-live", "kg-results", "kg-scen"])

    def test_structure(self):
        for p in DASH:
            d = json.loads(p.read_text(encoding="utf-8"))
            ids = [x["id"] for x in d["panels"]]
            self.assertEqual(len(ids), len(set(ids)), p.name)
            self.assertGreater(len(d["panels"]), 5)
            self.assertEqual(len(d["links"]), 3)                                  # navigation to the three dashboards
            for pan in d["panels"]:
                self.assertLessEqual(pan["gridPos"]["x"] + pan["gridPos"]["w"], 24, (p.name, pan["title"]))
                for t in pan.get("targets", []):
                    self.assertEqual(t["datasource"]["uid"], "kukule-api")
                    self.assertTrue(t["url"].startswith("http://host.docker.internal:8765/"))
            # panels never overlap
            boxes = [(x["gridPos"]["x"], x["gridPos"]["y"], x["gridPos"]["w"], x["gridPos"]["h"]) for x in d["panels"]]
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    overlap = a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
                    self.assertFalse(overlap, (p.name, a, b))

    def test_every_query_is_served(self):
        n = 0
        for p in DASH:
            d = json.loads(p.read_text(encoding="utf-8"))
            vars_ = default_vars(d)
            for pan in d["panels"]:
                for t in pan.get("targets", []):
                    path = urlparse(t["url"]).path
                    params = {x["key"]: expand(x["value"], vars_) for x in t["url_options"]["params"]}
                    r = C.get(path, params=params)
                    self.assertEqual(r.status_code, 200, (p.name, pan["title"], path, params, r.text[:120]))
                    data = r.json()
                    if path not in ("/live/log",):                                 # the live log may be empty before the first plan
                        self.assertTrue(len(data) > 0, (p.name, pan["title"], path, params))
                    n += 1
        self.assertGreaterEqual(n, 55)          # all panel queries (59 today)

    def test_method_colours_cover_all_methods(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("bd", ROOT / "grafana" / "build_dashboards.py")
        bd = importlib.util.module_from_spec(spec); spec.loader.exec_module(bd)
        self.assertEqual(set(bd.COL), set(api.METHOD_NAMES.values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
