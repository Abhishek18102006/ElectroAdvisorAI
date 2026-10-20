from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.models.product import Product


def get_all_categories(db: Session) -> List[str]:
    """Returns a distinct list of available categories in the catalog."""
    results = db.query(Product.category).distinct().all()
    return [r[0] for r in results]


def get_product_by_id(db: Session, product_id: str) -> Optional[Product]:
    """Safe retrieval of a single product by its unique ID."""
    return db.query(Product).filter(Product.id == product_id).first()


def search_catalog_controlled(
    db: Session,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    brand: Optional[str] = None,
    min_ram_gb: Optional[int] = None,
    requires_dedicated_gpu: Optional[bool] = None,
    search_query: Optional[str] = None,
    limit: int = 50,
) -> List[Product]:
    """
    Controlled query tool for retrieving products from the database.
    Does NOT use raw or dynamic SQL. All conditions are bound via SQLAlchemy ORM expressions.
    """
    query = db.query(Product)

    if category:
        query = query.filter(Product.category.ilike(category.strip()))

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if brand:
        query = query.filter(Product.brand.ilike(brand.strip()))

    if search_query:
        term = f"%{search_query.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.brand.ilike(term),
                Product.description.ilike(term),
            )
        )

    products = query.limit(limit).all()

    # In-memory post-filtering on JSON specs if required
    filtered_results = []
    for prod in products:
        specs = prod.specs or {}
        
        # Check RAM constraint
        if min_ram_gb is not None:
            ram = specs.get("ram_gb", 0)
            if ram < min_ram_gb:
                continue

        # Check dedicated GPU constraint
        if requires_dedicated_gpu is True:
            gpu_type = specs.get("gpu_type", "").lower()
            if gpu_type != "dedicated":
                continue

        filtered_results.append(prod)

    return filtered_results
