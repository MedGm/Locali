# Run runD

## Findings

- bug: 10
- quality: 11
- security: 28

Model review findings whose quoted line did not exist (dropped): 2

## Tests added

Unit:
- tests/test_locali_line_total.py
Integration:
- tests/test_locali_integration_best_seller.py
API: none

## Suspected bugs (generated tests that failed; check the test before the code)

- tinyshop/api.py::create_app: assert 404 == 200
- tinyshop/api.py::create_app: AssertionError: assert {'detail': 'Not Found'} == {'message': 'Hello, World!'}
- tinyshop/db.py::record_sale: assert -1 == 5
- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::total_units: AssertionError: assert 7 == 9
- tinyshop/pricing.py::bulk_discount: assert 5 == 0
- tinyshop/reports.py::daily_report: AssertionError: assert 'Widget: 5 x 10.00' in 'Widget: 2 x 10.00\nWidget: 3 x 10.00\ntotal: 50.00'
- tinyshop/reports.py::daily_report: AssertionError: assert 'total: 75.00' in 'Widget: 2 x 10.00\nWidget: 3 x 10.00\ntotal: 50.00'
- tinyshop/api.py::place_order: assert 201 == 409
- tinyshop/api.py::place_order: AssertionError: assert {'ok': True} == {'detail': 'i...icient stock'}
- tinyshop/api.py::day_report: AssertionError: assert {'report': 'total: 0.00'} == {'report': {}}
- tinyshop/api.py::day_report: AssertionError: assert {'report': 'a...total: 10.00'} == {'report': {d...3, 1, 1): 10}}
- tinyshop/api.py::day_report: AssertionError: assert {'report': 'a...ntotal: 5.00'} == {'report': {d...23, 1, 1): 5}}

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
- tinyshop/reports.py::best_seller

## Patches (each one is reviewed and applied on its own)

- fc92cf3f3745 [fix] Fix apply_discount in tinyshop/pricing.py: validation passed
- bb88314434f0 [tests] Regression tests for line_total (they record what the code does now): validation passed
- 3f324a2dbcd5 [tests] Integration tests for best_seller: validation passed
- df53b3efa340 [docs] Docstrings for get_conn in tinyshop/api.py: validation passed
- d5a4a1ada561 [docs] Docstrings for create_staff, check_login in tinyshop/auth.py: validation passed
- c7e27f0a5a55 [docs] Docstrings for connect, add_product, sales_for_day in tinyshop/db.py: validation passed
- b1639a13f18d [docs] Docstrings for remove_stock, restock_list in tinyshop/inventory.py: validation passed
- 0eb30e792aa4 [docs] Docstrings for best_seller in tinyshop/reports.py: validation passed

## DevOps summary

Merge readiness: not ready

Blockers:

- 3 hard-coded secret(s): tinyshop/settings.py:8, tinyshop/settings.py:9, tinyshop/settings.py:10
- 6 high-severity security finding(s) from the static tools
- requirements.txt: reqeusts looks like requests (possible typosquat)
- 1 test(s) fail on the current code

Warnings:

- 14 suspected bug(s) from generated tests, not confirmed
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
