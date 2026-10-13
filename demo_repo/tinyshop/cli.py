import argparse

from tinyshop import db
from tinyshop.reports import daily_report


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tinyshop")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init-db")
    init.add_argument("path")

    add = sub.add_parser("add-product")
    add.add_argument("path")
    add.add_argument("name")
    add.add_argument("price", type=float)
    add.add_argument("--stock", type=int, default=0)

    report = sub.add_parser("report")
    report.add_argument("path")
    report.add_argument("day")

    calc = sub.add_parser("calc")
    calc.add_argument("expr", help="quick price maths, e.g. '8.5*3'")

    args = parser.parse_args(argv)
    if args.cmd == "init-db":
        db.connect(args.path).close()
    elif args.cmd == "add-product":
        conn = db.connect(args.path)
        print(db.add_product(conn, args.name, args.price, args.stock))
    elif args.cmd == "report":
        print(daily_report(db.connect(args.path), args.day))
    elif args.cmd == "calc":
        print(eval(args.expr))


if __name__ == "__main__":
    main()
