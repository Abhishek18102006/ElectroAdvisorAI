from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductResponse, ProductListResponse, ProductCompareResponse

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


@router.get("/compare", response_model=ProductCompareResponse, summary="Compare multiple products side-by-side")
def compare_products(
    ids: str = Query(..., description="Comma-separated product IDs to compare (e.g. LAP-001,LAP-004)"),
    db: Session = Depends(get_db),
):
    """
    Accepts a list or comma-separated string of product IDs (e.g., ?ids=LAP-001,LAP-004)
    and returns a structured side-by-side specification matrix with key trade-off highlights.
    """
    raw_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if len(raw_ids) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least 2 product IDs are required for side-by-side comparison",
        )

    products = db.query(Product).filter(Product.id.in_(raw_ids)).all()
    found_ids = {p.id for p in products}
    missing_ids = [pid for pid in raw_ids if pid not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Products not found: {', '.join(missing_ids)}",
        )

    # Sort products in the exact order requested
    id_order = {pid: idx for idx, pid in enumerate(raw_ids)}
    ordered_products = sorted(products, key=lambda p: id_order.get(p.id, 999))

    # Build comparison matrix
    spec_fields = [
        ("price", "Price (INR)", lambda p: p.price),
        ("brand", "Brand", lambda p: p.brand),
        ("rating", "Rating", lambda p: p.rating),
        ("category", "Category", lambda p: p.category),
        ("processor", "Processor / CPU", lambda p: (p.specs or {}).get("cpu", "N/A")),
        ("ram_gb", "RAM (GB)", lambda p: (p.specs or {}).get("ram_gb", "N/A")),
        ("storage", "Storage", lambda p: f"{(p.specs or {}).get('storage_gb', '')} GB {(p.specs or {}).get('storage_type', '')}".strip() or "N/A"),
        ("gpu", "Graphics / GPU", lambda p: (p.specs or {}).get("gpu", "N/A")),
        ("display", "Display", lambda p: (p.specs or {}).get("display", "N/A")),
        ("weight_kg", "Weight (kg)", lambda p: (p.specs or {}).get("weight_kg", "N/A")),
        ("battery_life_hours", "Battery Life (hrs)", lambda p: (p.specs or {}).get("battery_life_hours", "N/A")),
        ("os", "Operating System", lambda p: (p.specs or {}).get("os", "N/A")),
    ]

    comparison_matrix = {}
    for key, label, extractor in spec_fields:
        comparison_matrix[key] = {
            "label": label,
            "values": {p.id: extractor(p) for p in ordered_products},
        }

    # Generate key differences summary
    key_differences = []
    p1, p2 = ordered_products[0], ordered_products[1]
    
    price_diff = p1.price - p2.price
    if price_diff > 0:
        key_differences.append(f"{p2.name} is ₹{price_diff:,.0f} more affordable than {p1.name}.")
    elif price_diff < 0:
        key_differences.append(f"{p1.name} is ₹{abs(price_diff):,.0f} more affordable than {p2.name}.")
    else:
        key_differences.append(f"Both products are identically priced at ₹{p1.price:,.0f}.")

    w1 = (p1.specs or {}).get("weight_kg")
    w2 = (p2.specs or {}).get("weight_kg")
    if w1 is not None and w2 is not None:
        if w1 < w2:
            key_differences.append(f"{p1.name} is {w2 - w1:.2f} kg lighter ({w1} kg vs {w2} kg).")
        elif w2 < w1:
            key_differences.append(f"{p2.name} is {w1 - w2:.2f} kg lighter ({w2} kg vs {w1} kg).")

    b1 = (p1.specs or {}).get("battery_life_hours")
    b2 = (p2.specs or {}).get("battery_life_hours")
    if b1 is not None and b2 is not None:
        if b1 > b2:
            key_differences.append(f"{p1.name} delivers {b1 - b2:.1f} hours longer battery life ({b1}h vs {b2}h).")
        elif b2 > b1:
            key_differences.append(f"{p2.name} delivers {b2 - b1:.1f} hours longer battery life ({b2}h vs {b1}h).")

    return ProductCompareResponse(
        product_ids=raw_ids,
        products=[ProductResponse(**item.to_dict()) for item in ordered_products],
        comparison_matrix=comparison_matrix,
        key_differences=key_differences,
    )


@router.get("/{product_id}", response_model=ProductResponse, summary="Retrieve a product's details")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product with ID '{product_id}' not found")
    return ProductResponse(**product.to_dict())

