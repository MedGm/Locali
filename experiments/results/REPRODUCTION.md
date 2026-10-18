# Reproducing the results from a clean checkout

Checked on 2026-10-17 at commit `1e6fccd`, and again on 2026-10-18 at `de96799` with the results added since (agent context, red-team, serving, other languages).

What "clean" means here: a new git worktree of the commit, its own environment from the lock file
(`uv sync --frozen`), and only committed files as input. Model generations were not repeated: they
are the raw data (every answer, with its tokens, timings and energy, is in the `samples.jsonl` of
its run), and repeating the GPU runs would take days of Kaggle quota. Everything built on top of
them was.

## 1. Install, lint and tests

GitHub Actions does this on every push (`.github/workflows/ci.yml`): `uv sync --frozen`, Ruff, the
sandbox image build, the full test suite, and the frontend's type check, lint and production
build. Green on both commits.

## 2. Every derived result, rebuilt

`bash experiments/scripts/reproduce.sh` rebuilds these in a fresh worktree and compares them with
the committed files (lines naming the commit or the generation time are ignored):

| File | Built by | Result |
|---|---|---|
| `summary.json` (what the web app's Results page shows, every study) | `export_results.py` | identical |
| `context_agents/table.md` | `context_table.py`, rescored from the saved runs | identical |
| `serving_t4/tables.md` | `serving_table.py` | identical |
| `multilang_t4_rescore/table.md` | `multilang_table.py`, from the saved answers of both rescoring runs | identical |
| `serving_t4/throughput.png`, `latency.png` | `serving_table.py` | identical, byte for byte |
| `redteam/model.md`, `model.jsonl` | `redteam_model.py`, rescored from the saved answers | identical |
| `redteam/controls.md` | `redteam.py`: the 16 attack cases executed again, Docker included | identical |

## 3. Scoring, executed again

The stored scores were computed when each run was made. To check the scoring has not drifted
since, I re-executed every answer of four headline runs in today's sandbox (on copies, with
`python -m evaluation.rescore`):

| Run | Items | Stored pass@1 | Re-executed |
|---|---|---|---|
| HumanEval+, fine-tuned Q8, laptop | 164 | 63.19 | 63.19 |
| HumanEval+, base FP16, Kaggle T4 | 164 | 65.03 | 65.03 |
| Held-out repair (internal_t1), fine-tuned, T4 | 212 | 63.68 | 63.68 |
| HumanEvalFix, fine-tuned Q4, laptop | 164 | 29.88 | 29.88 |

## Not repeated

- Generations by the models (Kaggle and laptop). Greedy decoding on a GPU is not bit-exact across
  batch shapes anyway ([serving_t4](serving_t4/README.md) measured 2 to 6 changed answers in 64
  between server settings, with pass@1 within one item).
- The fine-tuning runs; their logs, settings and loss curves are committed and in MLflow.
- The agent runs with the real model, which are one run per setting by design (temperature 0).
