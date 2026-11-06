# Integration and API tests on demo_repo

The brief asks for unit, integration and API tests. Since this change the test step of the
workflow writes all three (`backend/agents/testgen.py` for unit tests, `backend/agents/flowtests.py`
for the other two):

- **integration tests** for project functions that call functions of another project file, with
  real collaborators and a temporary database instead of mocks (in demo_repo: `daily_report` and
  `best_seller`, built on `db.py`);
- **API tests** for each route of a FastAPI app, through `TestClient` and a `client` fixture that
  builds the app on an empty temporary database (in demo_repo: the new `tinyshop/api.py`).

The rules are the ones of the unit tests: only passing tests are kept, a failed assertion makes
the function a suspect, a crash is only counted, a function with a suspect keeps no tests, and
targets that are or call code the static tools flag as insecure get no tests (here `GET /products`,
which calls the planted SQL injection, and `cli.main`).

`demo_repo` got an HTTP API for this, with a sixth planted bug: `POST /orders` never checks the
stock, although its docstring says an order larger than the stock is refused with 409
(`bug-oversell` in `security/demo_repo_flaws.json`). The earlier agent results
(`../agents_demo_repo`) used the version before it.

Run: the fine-tuned 3B (run D, Q4_K_M, llama.cpp with n-gram lookup) on the laptop CPU, the full
workflow with tools, `experiments/scripts/assistant/agent_eval.py`, 2026-11-04.

## Result

| | First run | **Second run** (fixed prompts) |
|---|---|---|
| Tests kept: unit / integration / API | 1 / 0 / 0 | 1 / **1** / 0 |
| Generated tests that crashed | 47 | 27 |
| Line coverage of demo_repo with the kept tests | 27.7 → 33.7 % | 27.7 → **45.0 %** |
| Planted API bug (`bug-oversell`) | missed | **suspected** |
| Planted bugs: fixed / found / suspected / missed (of 6) | 1 / 3 / 1 / 1 | 1 / 3 / **2** / 0 |
| Wall time, model calls | 19.9 min, 58 | 18.8 min, 57 |

In the second run the model's API test for `POST /orders` ordered more than the stock and expected
409; the code returned 201, so the test failed and `place_order` was reported as a suspected bug:

```
- tinyshop/api.py::place_order: assert 201 == 409
```

That is the planted bug, found by a test the agent wrote from the endpoint's docstring. As with
every suspect, nothing was changed in the code: the report asks a human to check the test first.

## What went wrong first, and the fix

In the first run every integration and API test crashed:

- the API tests built the app once at the top of the file with `create_app(None)`, ignoring the
  instruction to use `tmp_path`, so every request failed with "unable to open database file";
- the integration tests used a fixture that does not exist (`pytest.db_connection`), and the model
  had not been shown how to create a database and add data, only the function under test and the
  functions it calls.

The fixed prompts (second run) give the API tests a ready-made `client` fixture, which the agent
also adds to the file when the answer does not define it, and show the integration tests the whole
module of each function they call (here all of `db.py`). The model was fine-tuned on unit tests
only (T2 format); for these two formats it gets the structure from the prompt.

## Limits

- **No API test was kept.** Every API answer contained at least one wrong expectation, so each
  route became a suspect and kept none of its tests (the rule that protects against tests that
  record a bug as correct). For `place_order` that wrong expectation was the planted bug; for
  `day_report` the model expected the report as a dictionary, where the API returns text.
- **False suspects.** Of the 8 functions reported as suspects, 4 hold a planted bug
  (`needs_restock`, `total_units`, `bulk_discount`, `place_order`). Three come from wrong
  expectations: `daily_report` (the model expected the sales of one product added up),
  `day_report` (a dictionary instead of text) and `create_app` (a test of a `/` route that does not
  exist). `record_sale` (`assert -1 == 5`) is a side effect of the missing stock check: it lowers
  the stock below zero, but the bug was planted in `place_order`, which should refuse the order.
  The report says to check the test before the code.
- One small repository, one run per setting, as for the other agent results.

## Files

- `ft3b-multi/`: the second run: `score.json`, `state.json`, `report.md`, one `.diff` per proposed
  patch, `data/` (the patch records), the model server and evaluation logs.
- `ft3b-multi-first/`: the first run, same files without `data/`.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
