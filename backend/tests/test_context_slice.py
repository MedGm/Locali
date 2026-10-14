import ast
from pathlib import Path

from backend.context_slice import slice_function

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"


def test_slice_keeps_target_used_imports_and_constants():
    out = slice_function(DEMO, "tinyshop/pricing.py", "with_vat")
    assert "def with_vat(total):" in out
    assert "from tinyshop.settings import VAT_RATE" in out
    assert "def apply_discount" not in out  # unrelated function in the same file
    ast.parse(out.replace("# --- ", "# "))


def test_slice_follows_calls_into_other_repo_modules():
    out = slice_function(DEMO, "tinyshop/reports.py", "daily_report")
    assert "def daily_report(conn, day):" in out
    assert "def sales_for_day(conn, day):" in out  # imported from tinyshop/db.py
    assert "def export_report" not in out
    assert "import subprocess" not in out  # not used by daily_report


def test_slice_includes_same_file_helpers_transitively():
    out = slice_function(DEMO, "tinyshop/inventory.py", "restock_list")
    assert "def needs_restock" in out
    assert "LOW_STOCK_THRESHOLD" in out
    assert "def total_units" not in out


def test_slice_is_much_smaller_than_the_files_it_draws_from():
    out = slice_function(DEMO, "tinyshop/reports.py", "daily_report")
    whole = (DEMO / "tinyshop/reports.py").read_text() + (DEMO / "tinyshop/db.py").read_text()
    assert len(out) < 0.6 * len(whole)
