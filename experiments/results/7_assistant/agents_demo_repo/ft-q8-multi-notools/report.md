# Run ft-q8-multi-notools

## Findings

- quality: 14
- security: 6

Model review findings whose quoted line did not exist (dropped): 0

## Tests added

- tests/test_locali_hash_password.py
- tests/test_locali_load_session.py
- tests/test_locali_main.py
- tests/test_locali_find_products.py
- tests/test_locali_needs_restock.py
- tests/test_locali_line_total.py
- tests/test_locali_bulk_discount.py

## Suspected bugs (generated tests that failed; check the test before the code)

- tinyshop/auth.py::hash_password: AssertionError: assert '098f6bcd4621...e4e832627b4f6' == '5f4dcc3b5aa7...e8e3f0e623200'
- tinyshop/db.py::connect: assert 0 == 1
- tinyshop/db.py::find_products: AssertionError: assert 1 == 2
- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::total_units: assert 9 == 10
- tinyshop/inventory.py::total_units: assert 10 == 15
- tinyshop/inventory.py::total_units: assert 0 == 5
- tinyshop/pricing.py::bulk_discount: assert 5 == 10

## Fixes

- tests/test_pricing.py::test_discount: fixed in 1 attempt(s), tinyshop/pricing.py::apply_discount

## Patch

- 70f58cd6b2fe: validation FAILED, awaiting review
