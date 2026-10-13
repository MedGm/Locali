# tinyshop

Small inventory and order backend for a corner shop. Started as a weekend project, now used
for the shop's tablet app.

## Running

```
pip install -r requirements.txt
python -m tinyshop.cli init-db shop.db
python -m tinyshop.cli add-product shop.db "Olive oil 1L" 8.50 --stock 12
```

## Layout

- `tinyshop/inventory.py` stock levels and restock alerts
- `tinyshop/pricing.py` cart totals, discounts, VAT
- `tinyshop/db.py` sqlite storage
- `tinyshop/auth.py` staff accounts
- `tinyshop/reports.py` daily sales report
- `tinyshop/cli.py` command line

Tests: `pytest`
