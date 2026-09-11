"""Digital Product Engine: catalog, sales, retention."""
from __future__ import annotations
from sqlalchemy import func

from app.core.audit import audit

KINDS = ("newsletter", "report", "intelligence", "research")


def add_product(db, name: str, kind: str, price: float = 0.0, actor: str = "products"):
    from app.models.phase4 import ProductCatalog
    if kind not in KINDS:
        raise ValueError(f"kind must be {KINDS}")
    row = ProductCatalog(name=name, kind=kind, price=price)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "product.added", "product", row.id, {"name": name})
    return row


def record_sale(db, product_id: int, amount: float = 0.0, retained: bool = True,
                actor: str = "products"):
    from app.models.phase4 import ProductCatalog, ProductSale
    if db.get(ProductCatalog, product_id) is None:
        raise ValueError(f"product {product_id} not found")
    row = ProductSale(product_id=product_id, amount=amount, retained=retained)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, actor, "product.sold", "sale", row.id, {"amount": amount})
    return row


def performance(db) -> list[dict]:
    from app.models.phase4 import ProductCatalog, ProductSale
    out = []
    for p in db.query(ProductCatalog).all():
        sales = db.query(ProductSale).filter(ProductSale.product_id == p.id).all()
        total = sum(float(s.amount or 0) for s in sales)
        ret = ([s for s in sales if s.retained].__len__() / len(sales)) if sales else 0.0
        out.append({"id": p.id, "name": p.name, "kind": p.kind,
                    "sales": len(sales), "revenue": round(total, 2),
                    "retention": round(ret, 3)})
    out.sort(key=lambda d: d["revenue"], reverse=True)
    return out


def totals(db) -> dict:
    from app.models.phase4 import ProductSale
    n, rev = db.query(func.count(ProductSale.id),
                      func.coalesce(func.sum(ProductSale.amount), 0.0)).one()
    return {"sales": int(n or 0), "revenue": round(float(rev or 0), 2)}
