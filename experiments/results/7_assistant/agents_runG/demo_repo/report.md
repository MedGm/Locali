# Run demo_repo

## Findings

- bug: 11
- quality: 17
- security: 25

Model review findings whose quoted line did not exist (dropped): 3

## Tests added

Unit:
- tests/test_locali_line_total.py
Integration:
- tests/test_locali_integration_best_seller.py
API: none

## Suspected bugs (generated tests that failed; check the test before the code)

- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::total_units: AssertionError: assert 7 == 5
- tinyshop/pricing.py::bulk_discount: assert 5 == 10
- tinyshop/api.py::create_product: assert 201 == 409
- tinyshop/api.py::create_product: AssertionError: assert {'ok': True} == {'detail': 'i...icient stock'}
- tinyshop/api.py::place_order: assert 201 == 409
- tinyshop/api.py::place_order: AssertionError: assert {'ok': True} == {'detail': 'i...icient stock'}
- tinyshop/api.py::day_report: AssertionError: assert {'report': 'total: 0.00'} == {'report': {}}
- tinyshop/api.py::day_report: AssertionError: assert {'report': 'a...total: 25.00'} == {'report': {d..., 10, 1): 15}}
- tinyshop/api.py::day_report: AssertionError: assert {'report': 'a...ntotal: 5.00'} == {'report': {d...3, 10, 1): 5}}

## Fixes

- tests/test_pricing.py::test_discount: fixed in 1 attempt(s), tinyshop/pricing.py::apply_discount

## Docstrings

- tinyshop/api.py::get_conn
- tinyshop/api.py::create_app
- tinyshop/auth.py::create_staff
- tinyshop/auth.py::check_login
- tinyshop/db.py::connect
- tinyshop/db.py::add_product
- tinyshop/db.py::record_sale
- tinyshop/db.py::sales_for_day
- tinyshop/inventory.py::remove_stock
- tinyshop/inventory.py::restock_list

## Patches (each one is reviewed and applied on its own)

- c91d7640d3af [fix] Fix apply_discount in tinyshop/pricing.py: validation passed
- 73e42395abd8 [tests] Regression tests for line_total (they record what the code does now): validation passed
- 5575cf153ef2 [tests] Integration tests for best_seller: validation passed
- ed27fabe1d9c [docs] Docstrings for get_conn, create_app in tinyshop/api.py: validation passed
- 09d2d2883a60 [docs] Docstrings for create_staff, check_login in tinyshop/auth.py: validation passed
- dbc8f19d59e2 [docs] Docstrings for connect, add_product, record_sale, sales_for_day in tinyshop/db.py: validation passed
- 3f664cd502a7 [docs] Docstrings for remove_stock, restock_list in tinyshop/inventory.py: validation passed

## DevOps summary

Merge readiness: not ready

Blockers:

- 3 hard-coded secret(s): tinyshop/settings.py:8, tinyshop/settings.py:9, tinyshop/settings.py:10
- 6 high-severity security finding(s) from the static tools
- requirements.txt: reqeusts looks like requests (possible typosquat)
- 1 test(s) fail on the current code

Warnings:

- 11 suspected bug(s) from generated tests, not confirmed
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
