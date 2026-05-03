from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class SupplierBase(BaseModel):
    name: str
    vat_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierOut(SupplierBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceItemOut(BaseModel):
    id: int
    raw_description: str
    quantity: Optional[float]
    unit: Optional[str]
    unit_price: Optional[float]
    total_price: Optional[float]
    canonical_product_id: Optional[int]

    class Config:
        from_attributes = True


class InvoiceOut(BaseModel):
    id: int
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    total_amount: Optional[float]
    file_name: str
    created_at: datetime
    supplier: SupplierOut
    items: List[InvoiceItemOut] = []

    class Config:
        from_attributes = True


class CanonicalProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None


class CanonicalProductCreate(CanonicalProductBase):
    pass


class CanonicalProductOut(CanonicalProductBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SupplierPrice(BaseModel):
    supplier_id: int
    supplier_name: str
    unit_price: float
    invoice_date: Optional[str]
    invoice_id: int


class ProductComparison(BaseModel):
    product: CanonicalProductOut
    prices: List[SupplierPrice]
    best_price: Optional[float]
    worst_price: Optional[float]


class AssignProductRequest(BaseModel):
    canonical_product_id: Optional[int] = None
    new_product_name: Optional[str] = None
