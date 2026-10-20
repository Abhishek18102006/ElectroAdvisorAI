from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.product import Product

router = APIRouter()


@router.get("/health", summary="Health check", tags=["System"])
def check_health(db: Session = Depends(get_db)):
    """
    Performs application health check and verifies database connectivity and product catalogue.
    """
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        products_count = db.query(Product).count()
        return {
            "status": "ok",
            "service": "ElectroAdvisor AI Sales Assistant API",
            "database": "connected",
            "products_count": products_count,
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "ElectroAdvisor AI Sales Assistant API",
            "database": "error",
            "error_detail": str(e),
        }
