from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.product import Product
from app.schemas.product import CategoryItem, CategoryListResponse

router = APIRouter(prefix="/categories", tags=["Categories & Taxonomy"])


@router.get("", response_model=CategoryListResponse, summary="Fetch distinct product categories with price ranges & brand metadata")
def list_categories(db: Session = Depends(get_db)):
    """
    Returns distinct product categories, item counts, price boundaries, and brand lists.
    Optimizes frontend filter chips, dropdown menus, and hybrid UI controls without full-table scans.
    """
    products = db.query(Product).all()

    category_map = {}
    for p in products:
        cat = p.category.lower().strip()
        if cat not in category_map:
            category_map[cat] = {
                "name": cat,
                "display_name": cat.replace("_", " ").title(),
                "count": 0,
                "min_price": float(p.price),
                "max_price": float(p.price),
                "brands": set(),
            }
        category_map[cat]["count"] += 1
        category_map[cat]["min_price"] = min(category_map[cat]["min_price"], float(p.price))
        category_map[cat]["max_price"] = max(category_map[cat]["max_price"], float(p.price))
        if p.brand:
            category_map[cat]["brands"].add(p.brand)

    items = [
        CategoryItem(
            name=c["name"],
            display_name=c["display_name"],
            count=c["count"],
            min_price=c["min_price"],
            max_price=c["max_price"],
            brands=sorted(list(c["brands"])),
        )
        for c in sorted(category_map.values(), key=lambda x: x["name"])
    ]

    return CategoryListResponse(
        total_categories=len(items),
        categories=items,
    )
