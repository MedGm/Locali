# Run file

## Findings

- bug: 1
- quality: 1
- security: 23

Model review findings whose quoted line did not exist (dropped): 1

## Tests added

- tests/test_locali_needs_restock.py

## Suspected bugs (generated tests that failed; check the test before the code)

- tinyshop/db.py::add_product: AssertionError: assert [('Laptop', 2, 1000.0)] == [(1, 2, 1000)]
- tinyshop/db.py::record_sale: AssertionError: assert [('Laptop', 2, 1000.0)] == [(1, 2, 1000)]
- tinyshop/db.py::record_sale: assert -2 == 998
- tinyshop/db.py::sales_for_day: AssertionError: assert [('Laptop', 2, 1000.0)] == [(1, 2, 1000)]
- tinyshop/inventory.py::total_units: assert 9 == 14
- tinyshop/inventory.py::total_units: assert 0 == 5
- tinyshop/pricing.py::line_total: assert 75.87 == 62.08
- tinyshop/pricing.py::line_total: assert 58.97 == 68.97
- tinyshop/pricing.py::line_total: assert 74.5 == 68.45
- tinyshop/pricing.py::bulk_discount: assert 5 == 10

## Fixes

- tests/test_pricing.py::test_discount: fixed in 1 attempt(s), tinyshop/pricing.py::apply_discount

## Docstrings

- tinyshop/auth.py::create_staff
- tinyshop/auth.py::check_login
- tinyshop/db.py::connect
- tinyshop/inventory.py::remove_stock
- tinyshop/inventory.py::restock_list
- tinyshop/reports.py::daily_report
- tinyshop/reports.py::best_seller

## Patches (each one is reviewed and applied on its own)

- 2433f435a09a [fix] Fix apply_discount in tinyshop/pricing.py: validation passed
- 4d9a289d5a50 [tests] Regression tests for needs_restock (they record what the code does now): validation passed
- a09fa1c3ee8b [docs] Docstrings for create_staff, check_login in tinyshop/auth.py: validation passed
- 2f8a7657d0a6 [docs] Docstrings for connect in tinyshop/db.py: validation passed
- 0e25dc25c701 [docs] Docstrings for remove_stock, restock_list in tinyshop/inventory.py: validation passed
- a9571ec65862 [docs] Docstrings for daily_report, best_seller in tinyshop/reports.py: validation passed

## DevOps summary

Merge readiness: not ready

Blockers:

- 3 hard-coded secret(s): tinyshop/settings.py:8, tinyshop/settings.py:9, tinyshop/settings.py:10
- 6 high-severity security finding(s) from the static tools
- requirements.txt: reqeusts looks like requests (possible typosquat)
- 1 test(s) fail on the current code

Warnings:

- 10 suspected bug(s) from generated tests, not confirmed
- test coverage is 35%
- no CI workflow

Tests on the current code: 5 passed, 1 failed, coverage 35.1%

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
