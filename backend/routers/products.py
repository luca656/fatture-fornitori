from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from ..database import get_db
from ..models import CanonicalProduct, InvoiceItem, Invoice, Supplier
from ..schemas import (
    CanonicalProductOut,
    CanonicalProductCreate,
    ProductComparison,
    SupplierPrice,
    AssignProductRequest,
)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/", response_model=List[CanonicalProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(CanonicalProduct).order_by(CanonicalProduct.name).all()


@router.get("/comparison", response_model=List[ProductComparison])
def get_price_comparison(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return all canonical products with prices from each supplier."""
    query = db.query(CanonicalProduct)
    if category:
        query = query.filter(CanonicalProduct.category == category)
    products = query.order_by(CanonicalProduct.name).all()

    result = []
    for product in products:
        items = (
            db.query(InvoiceItem)
            .join(Invoice)
            .join(Supplier)
            .filter(InvoiceItem.canonical_product_id == product.id)
            .filter(InvoiceItem.unit_price.isnot(None))
            .all()
        )

        if not items:
            continue

        prices = []
        seen_supplier_ids = set()
        for item in items:
            sid = item.invoice.supplier_id
            # Keep only the most recent price per supplier
            if sid in seen_supplier_ids:
                continue
            seen_supplier_ids.add(sid)
            prices.append(
                SupplierPrice(
                    supplier_id=sid,
                    supplier_name=item.invoice.supplier.name,
                    unit_price=item.unit_price,
                    invoice_date=item.invoice.invoice_date,
                    invoice_id=item.invoice_id,
                )
            )

        if not prices:
            continue

        all_prices = [p.unit_price for p in prices]
        result.append(
            ProductComparison(
                product=product,
                prices=prices,
                best_price=min(all_prices),
                worst_price=max(all_prices),
            )
        )

    return result


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = (
        db.query(CanonicalProduct.category)
        .filter(CanonicalProduct.category.isnot(None))
        .distinct()
        .all()
    )
    return sorted([r[0] for r in rows if r[0]])


@router.get("/{product_id}", response_model=ProductComparison)
def get_product_comparison(product_id: int, db: Session = Depends(get_db)):
    product = db.query(CanonicalProduct).filter(CanonicalProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")

    items = (
        db.query(InvoiceItem)
        .join(Invoice)
        .join(Supplier)
        .filter(InvoiceItem.canonical_product_id == product_id)
        .filter(InvoiceItem.unit_price.isnot(None))
        .order_by(Invoice.invoice_date.desc())
        .all()
    )

    prices = [
        SupplierPrice(
            supplier_id=item.invoice.supplier_id,
            supplier_name=item.invoice.supplier.name,
            unit_price=item.unit_price,
            invoice_date=item.invoice.invoice_date,
            invoice_id=item.invoice_id,
        )
        for item in items
    ]

    all_prices = [p.unit_price for p in prices]
    return ProductComparison(
        product=product,
        prices=prices,
        best_price=min(all_prices) if all_prices else None,
        worst_price=max(all_prices) if all_prices else None,
    )


@router.post("/", response_model=CanonicalProductOut)
def create_product(data: CanonicalProductCreate, db: Session = Depends(get_db)):
    product = CanonicalProduct(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=CanonicalProductOut)
def update_product(product_id: int, data: CanonicalProductCreate, db: Session = Depends(get_db)):
    product = db.query(CanonicalProduct).filter(CanonicalProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(CanonicalProduct).filter(CanonicalProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    db.delete(product)
    db.commit()
    return {"ok": True}


@router.post("/items/{item_id}/assign")
def assign_item_to_product(
    item_id: int,
    data: AssignProductRequest,
    db: Session = Depends(get_db),
):
    """Manually assign an invoice item to a canonical product."""
    item = db.query(InvoiceItem).filter(InvoiceItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Articolo non trovato")

    if data.canonical_product_id:
        product = db.query(CanonicalProduct).filter(
            CanonicalProduct.id == data.canonical_product_id
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail="Prodotto canonico non trovato")
        item.canonical_product_id = data.canonical_product_id
    elif data.new_product_name:
        new_product = CanonicalProduct(name=data.new_product_name, unit=item.unit)
        db.add(new_product)
        db.flush()
        item.canonical_product_id = new_product.id
    else:
        raise HTTPException(status_code=400, detail="Fornire canonical_product_id o new_product_name")

    db.commit()
    return {"ok": True, "canonical_product_id": item.canonical_product_id}


@router.post("/{product_a_id}/merge/{product_b_id}")
def merge_products(product_a_id: int, product_b_id: int, db: Session = Depends(get_db)):
    """Merge product B into product A (all items of B are reassigned to A)."""
    product_a = db.query(CanonicalProduct).filter(CanonicalProduct.id == product_a_id).first()
    product_b = db.query(CanonicalProduct).filter(CanonicalProduct.id == product_b_id).first()
    if not product_a or not product_b:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    if product_a_id == product_b_id:
        raise HTTPException(status_code=400, detail="Non puoi unire un prodotto con se stesso")

    db.query(InvoiceItem).filter(
        InvoiceItem.canonical_product_id == product_b_id
    ).update({"canonical_product_id": product_a_id})
    db.delete(product_b)
    db.commit()
    return {"ok": True, "merged_into": product_a_id}
