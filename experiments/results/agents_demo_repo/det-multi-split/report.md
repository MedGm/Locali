# Run det-multi-split

## Findings

- bug: 2
- quality: 14
- security: 19

Model review findings whose quoted line did not exist (dropped): 0

## Tests added

- tests/test_locali_line_total.py

## Suspected bugs (generated tests that failed; check the test before the code)

- tinyshop/db.py::connect: assert 0 == 1
- tinyshop/inventory.py::needs_restock: assert False
- tinyshop/inventory.py::total_units: assert 9 == 10
- tinyshop/inventory.py::total_units: assert 10 == 15
- tinyshop/inventory.py::total_units: assert 0 == 5
- tinyshop/pricing.py::bulk_discount: assert 5 == 10

## Fixes

- tests/test_pricing.py::test_discount: fixed in 1 attempt(s), tinyshop/pricing.py::apply_discount

## Patches (each one is reviewed and applied on its own)

- 91bbeb8d61a8 [fix] Fix apply_discount in tinyshop/pricing.py: validation passed
- ea18ae405a45 [tests] Regression tests for line_total (they record what the code does now): validation passed
