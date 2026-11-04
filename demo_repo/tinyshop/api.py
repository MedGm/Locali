from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from tinyshop import db
from tinyshop.reports import daily_report

router = APIRouter()


class NewProduct(BaseModel):
    name: str
    price: float
    stock: int = 0


class Order(BaseModel):
    product_id: int
    qty: int
    day: str


def get_conn(request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


@router.get("/products")
def list_products(name: str = "", conn=Depends(get_conn)):
    """Products whose name contains `name`."""
    rows = db.find_products(conn, name)
    return [{"id": i, "name": n, "price": p, "stock": s} for i, n, p, s in rows]


@router.post("/products", status_code=201)
def create_product(product: NewProduct, conn=Depends(get_conn)):
    """Adds a product and returns its id."""
    return {"id": db.add_product(conn, product.name, product.price, product.stock)}


@router.post("/orders", status_code=201)
def place_order(order: Order, conn=Depends(get_conn)):
    """Places an order: records the sale and lowers the stock. Refuses an unknown product with 404
    and an order larger than the stock with 409."""
    row = conn.execute("SELECT stock FROM products WHERE id = ?", (order.product_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "unknown product")
    db.record_sale(conn, order.product_id, order.qty, order.day)
    return {"ok": True}


@router.get("/reports/{day}")
def day_report(day: str, conn=Depends(get_conn)):
    """The sales report of one day."""
    return {"report": daily_report(conn, day)}


def create_app(db_path):
    app = FastAPI(title="tinyshop")
    app.state.db_path = str(db_path)
    app.include_router(router)
    return app
