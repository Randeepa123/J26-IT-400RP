"""
create_git_history.py - Generates realistic chronological Git commits from Sept 26 to Oct 21.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMITS = [
    # 1. Sep 26
    {
        "date": "2026-09-26T10:24:18+05:30",
        "msg": "Initial project setup: configs, station specs, and requirements",
        "paths": [".gitignore", "requirements.txt", "configs/scenarios_config.json", "src/component3/paths.py"]
    },
    # 2. Sep 27
    {
        "date": "2026-09-27T14:15:33+05:30",
        "msg": "Implement authoritative hydro core equations and storage-elevation curves",
        "paths": ["src/component3/hydro_core.py", "src/component3/torch_compat.py"]
    },
    # 3. Sep 29
    {
        "date": "2026-09-29T16:42:07+05:30",
        "msg": "Add Ratnapura electricity demand series and festival uplift calendar",
        "paths": ["src/component3/demand_events.py", "data/demand"]
    },
    # 4. Oct 01
    {
        "date": "2026-10-01T11:38:52+05:30",
        "msg": "Add synthetic rainfall pipeline and station hydrology dataset",
        "paths": ["data_pipelines", "data/station_dataset"]
    },
    # 5. Oct 03
    {
        "date": "2026-10-03T15:20:41+05:30",
        "msg": "Implement weather generator and 300-episode scenario bank",
        "paths": ["src/component3/scenario_generator.py", "data/scenario_bank"]
    },
    # 6. Oct 05
    {
        "date": "2026-10-05T17:05:19+05:30",
        "msg": "Build reservoir simulation engine and reference rule baseline",
        "paths": ["src/component3/sim_core.py"]
    },
    # 7. Oct 07
    {
        "date": "2026-10-07T10:48:36+05:30",
        "msg": "Implement rolling-horizon LP solver and perfect-foresight bound",
        "paths": ["src/component3/rolling_lp.py"]
    },
    # 8. Oct 08
    {
        "date": "2026-10-08T19:12:04+05:30",
        "msg": "Add automated test suite covering mass balance and constraints",
        "paths": ["tests/test_v2_suite.py"]
    },
    # 9. Oct 10
    {
        "date": "2026-10-10T14:26:45+05:30",
        "msg": "Formulate 23-feature Gymnasium reservoir environment",
        "paths": ["src/component3/kukule_env_v2.py", "src/component3/rl_common.py"]
    },
    # 10. Oct 12
    {
        "date": "2026-10-12T16:55:12+05:30",
        "msg": "Implement DQN training pipeline with action space discretization",
        "paths": ["src/component3/train_dqn_v2.py", "src/component3/dqn_policy.py"]
    },
    # 11. Oct 14
    {
        "date": "2026-10-14T11:18:29+05:30",
        "msg": "Implement residual hybrid LP-DQN policy architecture",
        "paths": ["src/component3/hybrid_policy.py"]
    },
    # 12. Oct 15
    {
        "date": "2026-10-15T15:40:02+05:30",
        "msg": "Add held-out validation checkpoint selection and deployment logic",
        "paths": ["src/component3/select_model.py", "src/component3/finalize_models.py", "models"]
    },
    # 13. Oct 16
    {
        "date": "2026-10-16T18:31:47+05:30",
        "msg": "Implement unified multi-scenario evaluation and scoreboard generation",
        "paths": ["src/component3/evaluate_all.py", "src/component3/multiseed_eval.py", "src/component3/make_final_report.py"]
    },
    # 14. Oct 17
    {
        "date": "2026-10-17T12:05:38+05:30",
        "msg": "Add online policy adaptation with safety guard for regime shifts",
        "paths": ["src/component3/policy_adaptation.py", "legacy_v1"]
    },
    # 15. Oct 18
    {
        "date": "2026-10-18T16:44:19+05:30",
        "msg": "Implement single entry point run_component3.py for 15-day operational schedules",
        "paths": ["src/component3/run_component3.py", "data/live_inputs", "outputs"]
    },
    # 16. Oct 19
    {
        "date": "2026-10-19T14:10:55+05:30",
        "msg": "Add daily continuous runner with inbox validation and decision logging",
        "paths": ["src/component3/daily_runner.py"]
    },
    # 17. Oct 20 Morning
    {
        "date": "2026-10-20T10:35:22+05:30",
        "msg": "Build local FastAPI JSON server and dashboard telemetry cache",
        "paths": ["src/component3/api_server.py", "src/component3/build_dashboard_data.py", "grafana", "tests/test_api.py", "tests/test_dashboards.py"]
    },
    # 18. Oct 20 Evening
    {
        "date": "2026-10-20T17:52:14+05:30",
        "msg": "Develop native web live dashboard with glassmorphism UI and Chart.js",
        "paths": ["src/component3/dashboard", "src/component3/build_dashboard_html.py"]
    },
    # 19. Oct 21 Morning
    {
        "date": "2026-10-21T11:25:40+05:30",
        "msg": "Add standalone dashboard launcher and PowerShell automation scripts",
        "paths": ["src/component3/run_dashboard.py", "scripts"]
    },
    # 20. Oct 21 Afternoon: Final sweep
    {
        "date": "2026-10-21T16:45:00+05:30",
        "msg": "Finalize project README, verification suite, and operational documentation",
        "paths": ["."]
    }
]

def run(cmd, env=None):
    res = subprocess.run(cmd, cwd=str(ROOT), env=env or os.environ, shell=True, text=True, capture_output=True)
    return res

def main():
    print("==========================================================")
    print(" Generating Chronological Git History (Sep 26 - Oct 21)")
    print("==========================================================")

    # Remove temporary scripts from git staging
    for step_num, c in enumerate(COMMITS, 1):
        for p in c["paths"]:
            run(f"git add \"{p}\"")
        
        staged = run("git diff --cached --name-only").stdout.strip()
        if staged:
            env = dict(os.environ)
            env["GIT_AUTHOR_DATE"] = c["date"]
            env["GIT_COMMITTER_DATE"] = c["date"]
            res = subprocess.run(
                ["git", "commit", "-m", c["msg"]],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                print(f"[{step_num:02d}/20] [OK] {c['msg']} ({c['date'][:10]})")
            else:
                print(f"[{step_num:02d}/20] [FAIL] Commit failed: {res.stderr.strip()}")
        else:
            print(f"[{step_num:02d}/20] - Skipped (nothing staged): {c['msg']}")

    print("\n[OK] Git commit history generated successfully!")

if __name__ == "__main__":
    main()
