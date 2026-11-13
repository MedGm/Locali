# The full assistant on demo_repo with run G

Run G, the default since 2026-11-12, on the same check as `../agents_runE`: the whole workflow
(review with tools, tests, debug, docs) on `demo_repo`, as `scripts/run.sh` serves it (Q4_K_M,
llama.cpp 987498f with n-gram lookup, 4,096-token context, laptop CPU), 2026-11-13,
`experiments/scripts/laptop/laptop_runG_demo.sh`. Run E's column is its run with the same code
(`../repair_step_runE/demo_repo`, 2026-11-12).

| | Run E | **Run G** |
|---|---|---|
| Planted bugs: fixed / found / suspected / missed (of 6) | 1 / 3 / 1 / 1 | 1 / 3 / 2 / 0 |
| Planted bug and vulnerability lines named by the model's review | 6 | 7 |
| Model review warnings that match nothing planted | 17 | 21 |
| Vulnerabilities, secret, injections flagged (of 8) | 8 | 8 |
| Tests kept: unit / integration / API | 3 / 0 / 1 | 1 / 1 / 0 |
| Generated tests that crashed | 35 | 29 |
| Line coverage with the kept tests (before: 27.7 %) | 72.0 % | 44.8 % |
| Wall time | 21.0 min | 21.5 min |
| Output tokens (of which test writing) | 6,089 (4,066) | 6,312 (3,937) |

## Reading

- Run G leaves no planted bug unseen: `bug-bulk-boundary`, missed by run E, is caught by one of
  its tests, and its review names one more planted line (`tinyshop/pricing.py:16`).
- It keeps two tests where run E kept four, so the coverage ends at 45 % instead of 72 %; that is
  run D's result on the same project (`../agents_runE`). It also raises four more wrong warnings.
- The same single bug has a failing test, so the debug step is called once, and fixes it, as before.
- One run per model on one small project: it shows that the workflow runs with the new default
  and behaves like the earlier ones. It does not rank run G and run E; the benchmarks do that.

`demo_repo/` holds `score.json`, `report.md` (the report the user sees), `state.json`, the patches
and the log.

Code and text written with AI help (Claude); every figure above comes from the files in this folder.
