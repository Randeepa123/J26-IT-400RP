"""
finalize_models.py - publish the selected checkpoints into models/ and normalise outputs/selected_models.json
(paths stored relative to the project root, forward slashes).  Run after select_model.py:
    python src/component3/finalize_models.py
"""
import json
import shutil

import paths


def main():
    d = json.load(open(paths.SELECTED_MODELS_JSON))
    for k in d:
        p = paths.resolve(d[k]["path"].replace("\\", "/").replace("outputs/dqn_v2/", "outputs/training_runs/"))
        assert p.exists(), p
        d[k]["path"] = paths.rel(p)
    json.dump(d, open(paths.SELECTED_MODELS_JSON, "w"), indent=1)
    paths.MODELS_DIR.mkdir(exist_ok=True)
    shutil.copy2(paths.resolve(d["dqn"]["path"]), paths.MODELS_DIR / "dqn_selected.zip")
    shutil.copy2(paths.resolve(d["hybrid"]["path"]), paths.MODELS_DIR / "hybrid_selected.zip")
    print(json.dumps(d, indent=1))
    print("models/:", sorted(p.name for p in paths.MODELS_DIR.iterdir()))


if __name__ == "__main__":
    main()
