import os

DB_PATH = os.environ.get("TINYSHOP_DB", "shop.db")
VAT_RATE = 0.20
LOW_STOCK_THRESHOLD = 5

# TODO move to env before deploying
SECRET_KEY = "f3b1c9e07a5d4e2b8c6a9d0e1f2a3b4c"
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
BACKUP_BUCKET = "tinyshop-backups"
