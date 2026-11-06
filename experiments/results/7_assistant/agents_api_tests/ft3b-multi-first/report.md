# Run ft3b-multi

## Findings

- bug: 10
- quality: 11
- security: 28

Model review findings whose quoted line did not exist (dropped): 2

## Tests added

Unit:
- tests/test_locali_line_total.py
Integration: none
API: none

## Suspected bugs (generated tests that failed; check the test before the code)

- tinyshop/api.py::create_app: assert 404 == 200
- tinyshop/api.py::create_app: AssertionError: assert {'detail': 'Not Found'} == {'message': 'Hello, World!'}
- tinyshop/db.py::record_sale: assert -1 == 5
- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::total_units: AssertionError: assert 7 == 9
- tinyshop/pricing.py::bulk_discount: assert 5 == 0

## Fixes

- tests/test_pricing.py::test_discount: fixed in 1 attempt(s), tinyshop/pricing.py::apply_discount

## Docstrings

- tinyshop/api.py::get_conn
- tinyshop/auth.py::create_staff
- tinyshop/auth.py::check_login
- tinyshop/db.py::connect
- tinyshop/db.py::add_product
- tinyshop/db.py::sales_for_day
- tinyshop/inventory.py::remove_stock
- tinyshop/inventory.py::restock_list
- tinyshop/reports.py::daily_report
- tinyshop/reports.py::best_seller

## Patches (each one is reviewed and applied on its own)

- a5e953a260c1 [fix] Fix apply_discount in tinyshop/pricing.py: validation passed
- 3cae5bde2636 [tests] Regression tests for line_total (they record what the code does now): validation passed
- 74cce64bc97d [docs] Docstrings for get_conn in tinyshop/api.py: validation passed
- d63cd4dd6e1a [docs] Docstrings for create_staff, check_login in tinyshop/auth.py: validation passed
- 2ed7beddce0f [docs] Docstrings for connect, add_product, sales_for_day in tinyshop/db.py: validation passed
- 886d8bcc9ad8 [docs] Docstrings for remove_stock, restock_list in tinyshop/inventory.py: validation passed
- 07a6bc650f49 [docs] Docstrings for daily_report, best_seller in tinyshop/reports.py: validation passed

## DevOps summary

Merge readiness: not ready

Blockers:

- 3 hard-coded secret(s): tinyshop/settings.py:8, tinyshop/settings.py:9, tinyshop/settings.py:10
- 6 high-severity security finding(s) from the static tools
- requirements.txt: reqeusts looks like requests (possible typosquat)
- 1 test(s) fail on the current code

Warnings:

- 7 suspected bug(s) from generated tests, not confirmed
- test coverage is 28%
- no CI workflow

Tests on the current code: 5 passed, 1 failed, coverage 27.7%

CI workflows: none

Suggested workflow (.github/workflows/ci.yml):

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt pytest-cov
      - run: pytest --cov --cov-report=term

  locali-review:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/checkout@v4
        with:
          repository: MedGm/Locali
          path: .locali
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen --project .locali
      - run: uv run --project .locali python -m backend.pr_review --repo . --base "${{ github.event.pull_request.base.sha }}" --head "${{ github.event.pull_request.head.sha }}" --out comment.md
```
