"""select_model.py - choose the final DQN / hybrid checkpoint on validation scenarios 20-40 (never used by the
training callback, which scored scenarios 0-20) at two initial-storage levels. Writes outputs/selected_models.json."""
import glob, os, sys, json
import paths
import scenario_generator as sg, rolling_lp as rl
from hydro_core import HydroParams
from dqn_policy import DQNPolicy
from hybrid_policy import HybridPolicy
from train_dqn_v2 import validation_score

kind = sys.argv[1]                       # dqn | hybrid
pat = str(paths.TRAINING_RUNS_DIR / ('[abc]_*' if kind == 'dqn' else 'h*_hyb_*'))
cls = DQNPolicy if kind == 'dqn' else HybridPolicy
p = HydroParams.from_config(); val = sg.load_bank(os.path.join(sg.BANK_DIR, 'val_bank.pkl'))[20:40]
res = []
for d in sorted(glob.glob(pat)):
    for ck in ('dqn_best_val.zip', 'dqn_final.zip'):
        f = os.path.join(d, ck)
        if not os.path.exists(f): continue
        s, m = validation_score(p, cls(f), val, n_scen=20, s0_fracs=(0.5, 1.0))
        res.append((s, f)); print(os.path.basename(d)[:3], ck, round(s, 2), {k: round(v, 1) for k, v in m.items()}, flush=True)
s, m = validation_score(p, rl.RollingLPPolicy(), val, n_scen=20, s0_fracs=(0.5, 1.0)); print('rolling_lp', round(s, 2))
best = max(res); print('SELECTED', best)
path = str(paths.SELECTED_MODELS_JSON)
cur = json.load(open(path)) if os.path.exists(path) else {}
cur[kind] = {'path': paths.rel(best[1]), 'holdout_val_score': best[0], 'rolling_lp_holdout_val_score': s}
json.dump(cur, open(path, 'w'), indent=1)
