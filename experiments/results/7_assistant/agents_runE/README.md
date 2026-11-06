# The full assistant on demo_repo: 3B base vs run D vs run E

The real-world check before making run E the default: the whole workflow (review with tools,
tests, debug, docs) on `demo_repo`, the small shop app with 6 planted bugs, 5 planted
vulnerabilities, a hard-coded secret and 2 prompt injections (`security/demo_repo_flaws.json`).
Same code, same settings as `scripts/run.sh` (Q4_K_M, llama.cpp 987498f with n-gram lookup,
4,096-token context, laptop CPU), the three models one after the other, 2026-11-05
(`experiments/scripts/laptop/laptop_runE.sh`, step 2; scored by `experiments/scripts/assistant/agent_eval.py`).

## Result

| | 3B base | Run D | **Run E** |
|---|---|---|---|
| Planted bugs: fixed / found / suspected / missed (of 6) | 1 / 1 / 3 / 1 | 1 / 3 / 2 / 0 | 1 / 3 / 1 / 1 |
| Planted bug and vulnerability lines named by the model's review | 1 | 6 | 6 |
| Model review warnings that match nothing planted | 9 | 18 | 17 |
| Vulnerabilities, secret, injections flagged (of 8) | 8 | 8 | 8 |
| Tests kept: unit / integration / API | 1 / 1 / 0 | 1 / 1 / 0 | **3 / 0 / 1** |
| Generated tests that crashed | 38 | 27 | 35 |
| Line coverage with the kept tests (before: 27.7 %) | 60.2 % | 45.0 % | **72.0 %** |
| Wall time | 35.8 min | 19.9 min | **18.9 min** |
| Output tokens (of which test writing) | 12,102 (10,516) | 6,332 (4,221) | 6,097 (4,066) |

"Found" means the review names the bug's line; "suspected" means a generated test failed on it;
"fixed" means the debug step's patch makes the bug's test pass.

## Reading

- Both fine-tunes review much better than the base: they name 6 planted lines against 1, and
  find 3 bugs against 1. They also raise about twice as many warnings that are wrong (17-18 vs 9).
- Run E keeps the most tests (4, including an API test) and reaches the highest coverage (72 %).
  Run D catches one more bug through its tests (`bug-bulk-boundary`, suspected by D, missed by E).
- The base's tests catch as many planted bugs as the fine-tunes' tests (3 suspected); the
  difference is in the review, which names one planted line for the base and six for each fine-tune.
- The base spends more than half its time writing long test files: 10,516 output tokens against
  about 4,100 for the fine-tunes, so the whole run takes 34 minutes instead of 19.
- The vulnerabilities, the secret and the injections come from the static tools and the
  injection scanner, not from the model, so every model gets all 8.
- One run per model, on one small project: this shows how each model behaves in the real
  workflow, it does not measure a difference. The benchmark results are the measurement.

## The base, scored again (2026-11-06)

The base sometimes labels a test file `markdown` instead of `python` (the prompt asks for "a
markdown code block"), and the code extraction skipped such files, so they were never run. After
the fix in `evaluation/extract.py` the base ran again with the same settings
(`experiments/scripts/laptop/laptop_base_rerun.sh`): its answers are the same (greedy decoding,
the same 10,516 test-writing tokens), but more of its tests now run. Two more planted bugs are
suspected (`bug-restock-boundary`, `bug-skip-first`), and 38 tests crash instead of 21. The table
above uses the new run; the first one is kept in `base_first_scoring` (1 / 1 / 1 / 3). Run D and
run E never answer this way, so their runs are unchanged.

Each folder holds `score.json`, `report.md` (the report the user sees), `state.json`, the patches
(`patch-*.diff`) and the logs.

Code and text written with AI help (Claude); every figure above comes from the files in this folder.
