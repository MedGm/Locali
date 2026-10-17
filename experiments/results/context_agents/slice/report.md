# Run slice

## Findings

- bug: 2
- quality: 6
- security: 23

Model review findings whose quoted line did not exist (dropped): 6

## Tests added

- tests/test_locali_needs_restock.py
- tests/test_locali_bulk_discount.py

## Suspected bugs (generated tests that failed; check the test before the code)

- tinyshop/inventory.py::total_units: assert 9 == 12
- tinyshop/inventory.py::total_units: assert 50 == 60
- tinyshop/inventory.py::total_units: assert 0 == 10
- tinyshop/pricing.py::line_total: assert 1000000000000.0 == 100000000000.0

## Fixes

- tests/test_pricing.py::test_discount: fixed in 1 attempt(s), tinyshop/pricing.py::apply_discount

## Docstrings

- tinyshop/auth.py::create_staff
- tinyshop/auth.py::check_login
- tinyshop/db.py::connect
- tinyshop/db.py::add_product
- tinyshop/db.py::record_sale
- tinyshop/db.py::sales_for_day
- tinyshop/inventory.py::remove_stock
- tinyshop/inventory.py::restock_list
- tinyshop/reports.py::daily_report
- tinyshop/reports.py::best_seller

## Patches (each one is reviewed and applied on its own)

- 879d927ffebc [fix] Fix apply_discount in tinyshop/pricing.py: validation passed
- 786b0205bf64 [tests] Regression tests for needs_restock (they record what the code does now): validation passed
- fecea817d182 [tests] Regression tests for bulk_discount (they record what the code does now): validation passed
- 14a8a0847473 [docs] Docstrings for create_staff, check_login in tinyshop/auth.py: validation passed
- ec18854f67a9 [docs] Docstrings for connect, add_product, record_sale, sales_for_day in tinyshop/db.py: validation passed
- 43e2d809f448 [docs] Docstrings for remove_stock, restock_list in tinyshop/inventory.py: validation passed
- 896f1982f838 [docs] Docstrings for daily_report, best_seller in tinyshop/reports.py: validation passed

## DevOps summary

Merge readiness: not ready

Blockers:

- 3 hard-coded secret(s): tinyshop/settings.py:8, tinyshop/settings.py:9, tinyshop/settings.py:10
- 6 high-severity security finding(s) from the static tools
- requirements.txt: reqeusts looks like requests (possible typosquat)
- 1 test(s) fail on the current code

Warnings:

- 4 suspected bug(s) from generated tests, not confirmed
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
