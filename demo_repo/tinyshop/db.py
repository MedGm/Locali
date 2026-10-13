import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    day TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS staff (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL
);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def add_product(conn, name, price, stock=0):
    cur = conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", (name, price, stock))
    conn.commit()
    return cur.lastrowid


def find_products(conn, name):
    query = f"SELECT id, name, price, stock FROM products WHERE name LIKE '%{name}%'"
    return conn.execute(query).fetchall()


def record_sale(conn, product_id, qty, day):
    conn.execute("INSERT INTO sales (product_id, qty, day) VALUES (?, ?, ?)", (product_id, qty, day))
    conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, product_id))
    conn.commit()


def sales_for_day(conn, day):
    return conn.execute(
        "SELECT p.name, s.qty, p.price FROM sales s JOIN products p ON p.id = s.product_id WHERE s.day = ?",
        (day,),
    ).fetchall()
