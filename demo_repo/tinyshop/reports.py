import subprocess

from tinyshop.db import sales_for_day


def daily_report(conn, day):
    rows = sales_for_day(conn, day)
    lines = [f"{name}: {qty} x {price:.2f}" for name, qty, price in rows]
    revenue = sum(qty * price for _, qty, price in rows)
    lines.append(f"total: {revenue:.2f}")
    return "\n".join(lines)


def best_seller(conn, day):
    counts = {}
    for name, qty, _ in sales_for_day(conn, day):
        counts[name] = counts.get(name, 0) + qty
    if not counts:
        return None
    return max(counts, key=counts.get)


def export_report(conn, day, out_dir):
    text = daily_report(conn, day)
    path = f"{out_dir}/report-{day}.txt"
    with open(path, "w") as f:
        f.write(text)
    # compress so the backup job picks it up
    subprocess.run(f"gzip -f {path}", shell=True)
    return path + ".gz"
