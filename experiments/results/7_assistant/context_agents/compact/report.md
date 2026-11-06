# Run compact

## Findings

- bug: 2
- quality: 14
- security: 26

Model review findings whose quoted line did not exist (dropped): 0

## Tests added

- tests/test_locali_line_total.py
- tests/test_locali_bulk_discount.py

## Suspected bugs (generated tests that failed; check the test before the code)

- tinyshop/db.py::connect: assert 0 == 1
- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::total_units: assert 9 == 10
- tinyshop/inventory.py::total_units: assert 10 == 15
- tinyshop/inventory.py::total_units: assert 0 == 5

## Fixes

- tests/test_pricing.py::test_discount: fixed in 1 attempt(s), tinyshop/pricing.py::apply_discount

## Docstrings

- tinyshop/auth.py::create_staff
- tinyshop/auth.py::check_login
- tinyshop/db.py::add_product
- tinyshop/db.py::record_sale
- tinyshop/db.py::sales_for_day
- tinyshop/inventory.py::remove_stock
- tinyshop/inventory.py::restock_list
- tinyshop/reports.py::daily_report
- tinyshop/reports.py::best_seller

## Patches (each one is reviewed and applied on its own)

- ca11e289991a [fix] Fix apply_discount in tinyshop/pricing.py: validation passed
- 6c4828158d21 [tests] Regression tests for line_total (they record what the code does now): validation passed
- a74aa58146be [tests] Regression tests for bulk_discount (they record what the code does now): validation passed
- 639e94f7346c [docs] Docstrings for create_staff, check_login in tinyshop/auth.py: validation passed
- 62501193d33b [docs] Docstrings for add_product, record_sale, sales_for_day in tinyshop/db.py: validation passed
- 65ae96c0534b [docs] Docstrings for remove_stock, restock_list in tinyshop/inventory.py: validation passed
- faa3fa892656 [docs] Docstrings for daily_report, best_seller in tinyshop/reports.py: validation passed

## DevOps summary

Merge readiness: not ready

Blockers:

- 3 hard-coded secret(s): tinyshop/settings.py:8, tinyshop/settings.py:9, tinyshop/settings.py:10
- 6 high-severity security finding(s) from the static tools
- requirements.txt: reqeusts looks like requests (possible typosquat)
- 1 test(s) fail on the current code

Warnings:

- 5 suspected bug(s) from generated tests, not confirmed
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
