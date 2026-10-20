from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductResponse, ProductListResponse

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductListResponse, summary="List products with filtering & pagination")
def list_products(
    category: Optional[str] = Query(None, description="Filter by category (e.g. laptop, smartphone, tablet)"),
    brand: Optional[str] = Query(None, description="Filter by brand (e.g. Lenovo, Apple, ASUS)"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    search: Optional[str] = Query(None, description="Free text search on name or description"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=422,
            detail="min_price cannot be greater than max_price",
        )

    query = db.query(Product)

    if category:
        query = query.filter(Product.category.ilike(category.strip()))

    if brand:
        query = query.filter(Product.brand.ilike(brand.strip()))

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.brand.ilike(term),
                Product.description.ilike(term),
            )
        )

    total = query.count()
    offset = (page - 1) * limit
    
    # Deterministic sorting by product ID
    items = query.order_by(Product.id.asc()).offset(offset).limit(limit).all()

    pages = (total + limit - 1) // limit if total > 0 else 0

    return ProductListResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        items=[ProductResponse(**item.to_dict()) for item in items],
    )


@router.get("/{product_id}", response_model=ProductResponse, summary="Retrieve a product's details")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product with ID '{product_id}' not found")
    return ProductResponse(**product.to_dict())
