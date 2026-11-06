# Scripts

Run from the repository root, for example `uv run python experiments/scripts/report/report_figures.py`.

| Folder | What is in it |
|---|---|
| `report/` | the README charts (`report_figures.py`), the paper's figures, the tables, `export_results.py` (the web app's Results page), `log_to_mlflow.py`, and `reproduce.sh`, which rebuilds the tables from a clean checkout |
| `stats/` | the paired tests (`paired_compare.py`), the correction for many tests (`multiple_comparisons.py`), the pre-registered analysis (`repair_prereg.py`), the real-bug benchmark checks, the capability study |
| `assistant/` | the whole assistant on the demo project (`agent_eval.py`), the attack cases (`redteam.py`, `redteam_model.py`), repair with feedback |
| `laptop/` | the long laptop runs: baselines, quantization ladder, guessing ahead, run E's check |
