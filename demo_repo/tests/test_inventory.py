import pytest

from tinyshop.inventory import OutOfStock, remove_stock, restock_list


def test_remove_stock():
    assert remove_stock(10, 3) == 7


def test_remove_more_than_available():
    with pytest.raises(OutOfStock):
        remove_stock(2, 5)


def test_restock_list():
    assert restock_list([("milk", 1), ("bread", 20)]) == ["milk"]
