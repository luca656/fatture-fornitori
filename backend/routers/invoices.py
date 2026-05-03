import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Supplier, Invoice, InvoiceItem, CanonicalProduct
from ..schemas import InvoiceOut
from ..ai_extractor import extract_invoice_data
from ..ai_matcher import match_items_to_products, suggest_product_category

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def _get_or_create_supplier(db: Session, supplier_data: dict) -> Supplier:
    """Find existing supplier by VAT number or name, or create a new one."""
    vat = supplier_data.get("vat_number")
    if vat:
        existing = db.query(Supplier).filter(Supplier.vat_number == vat).first()
        if existing:
            return existing

    name = supplier_data.get("name", "").strip()
    if name:
        existing = db.query(Supplier).filter(Supplier.name == name).first()
        if existing:
            return existing

    supplier = Supplier(
        name=name or "Fornitore sconosciuto",
        vat_number=vat,
        address=supplier_data.get("address"),
        email=supplier_data.get("email"),
        phone=supplier_data.get("phone"),
    )
    db.add(supplier)
    db.flush()
    return supplier


def _process_invoice_file(file_path: str, db: Session) -> Invoice:
    """Extract data from file, match products, and persist everything."""
    extracted = extract_invoice_data(file_path)

    supplier = _get_or_create_supplier(db, extracted.get("supplier", {}))
    inv_data = extracted.get("invoice", {})

    invoice = Invoice(
        supplier_id=supplier.id,
        invoice_number=inv_data.get("invoice_number"),
        invoice_date=inv_data.get("invoice_date"),
        total_amount=inv_data.get("total_amount"),
        file_path=file_path,
        file_name=Path(file_path).name,
    )
    db.add(invoice)
    db.flush()

    raw_items = extracted.get("items", [])

    existing_products = db.query(CanonicalProduct).all()
    existing_list = [
        {"id": p.id, "name": p.name, "description": p.description or "", "unit": p.unit or ""}
        for p in existing_products
    ]

    items_for_matching = [
        {"index": i, "description": item.get("raw_description", ""), "unit": item.get("unit", "")}
        for i, item in enumerate(raw_items)
    ]

    matches = {}
    if items_for_matching:
        try:
            match_results = match_items_to_products(items_for_matching, existing_list)
            for m in match_results:
                matches[m["item_index"]] = m.get("canonical_product_id")
        except Exception:
            pass  # Proceed without matching if AI fails

    for i, item_data in enumerate(raw_items):
        canonical_id = matches.get(i)

        if canonical_id is None:
            desc = item_data.get("raw_description", "Prodotto sconosciuto")
            try:
                category = suggest_product_category(desc, "")
            except Exception:
                category = None

            canonical = CanonicalProduct(
                name=desc,
                unit=item_data.get("unit"),
                category=category,
            )
            db.add(canonical)
            db.flush()
            canonical_id = canonical.id

        unit_price = item_data.get("unit_price")
        total_price = item_data.get("total_price")
        quantity = item_data.get("quantity")

        # Derive unit_price if missing but computable
        if unit_price is None and total_price and quantity and quantity != 0:
            unit_price = round(total_price / quantity, 6)

        inv_item = InvoiceItem(
            invoice_id=invoice.id,
            canonical_product_id=canonical_id,
            raw_description=item_data.get("raw_description", ""),
            quantity=quantity,
            unit=item_data.get("unit"),
            unit_price=unit_price,
            total_price=total_price,
        )
        db.add(inv_item)

    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/", response_model=List[InvoiceOut])
def list_invoices(db: Session = Depends(get_db)):
    return (
        db.query(Invoice)
        .order_by(Invoice.created_at.desc())
        .all()
    )


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    return invoice


@router.post("/upload", response_model=InvoiceOut)
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato non supportato. Usa: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    dest_path = os.path.join(UPLOAD_DIR, file.filename)

    # Avoid overwriting: append counter if file exists
    counter = 1
    stem = Path(file.filename).stem
    while os.path.exists(dest_path):
        dest_path = os.path.join(UPLOAD_DIR, f"{stem}_{counter}{ext}")
        counter += 1

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        invoice = _process_invoice_file(dest_path, db)
    except Exception as e:
        os.remove(dest_path)
        raise HTTPException(status_code=500, detail=f"Errore elaborazione fattura: {str(e)}")

    return invoice


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Fattura non trovata")
    if os.path.exists(invoice.file_path):
        os.remove(invoice.file_path)
    db.delete(invoice)
    db.commit()
    return {"ok": True}
