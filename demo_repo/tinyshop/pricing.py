from tinyshop.settings import VAT_RATE


def line_total(price, qty):
    return round(price * qty, 2)


def cart_total(lines):
    """lines: list of (price, qty)."""
    return round(sum(line_total(p, q) for p, q in lines), 2)


def apply_discount(total, percent):
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(total * (1 + percent / 100), 2)


def with_vat(total):
    return round(total * (1 + VAT_RATE), 2)


def bulk_discount(qty):
    # 5% off from 10 units, 10% from 50
    if qty > 50:
        return 10
    if qty >= 10:
        return 5
    return 0
