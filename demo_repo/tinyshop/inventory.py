from tinyshop.settings import LOW_STOCK_THRESHOLD


class OutOfStock(Exception):
    pass


def needs_restock(stock, threshold=LOW_STOCK_THRESHOLD):
    """True when the shelf is at or below the threshold."""
    return stock < threshold


def remove_stock(stock, qty):
    if qty <= 0:
        raise ValueError("qty must be positive")
    if qty > stock:
        raise OutOfStock(f"only {stock} left")
    return stock - qty


def restock_list(products, alerts=[]):
    # products: list of (name, stock)
    for name, stock in products:
        if needs_restock(stock):
            alerts.append(name)
    return alerts


def total_units(products):
    total = 0
    for i in range(1, len(products)):
        total += products[i][1]
    return total
