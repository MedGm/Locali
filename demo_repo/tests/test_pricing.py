from tinyshop.pricing import apply_discount, cart_total, with_vat


def test_cart_total():
    assert cart_total([(2.50, 2), (1.20, 3)]) == 8.60


def test_vat():
    assert with_vat(10.0) == 12.0


def test_discount():
    assert apply_discount(50.0, 10) == 45.0
