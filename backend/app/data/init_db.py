import logging
from app.database import engine, SessionLocal, Base
from app.models.product import Product
from app.models.conversation import Conversation, Message
from app.data.seed_data import PRODUCTS_CATALOG

logger = logging.getLogger(__name__)


def init_db(drop_all: bool = False):
    """Initializes tables and populates with seed products if table is empty."""
    if drop_all:
        logger.info("Dropping existing database tables...")
        Base.metadata.drop_all(bind=engine)

    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        count = db.query(Product).count()
        if count == 0:
            logger.info("Database empty. Seeding %d products...", len(PRODUCTS_CATALOG))
            for item in PRODUCTS_CATALOG:
                prod = Product(
                    id=item["id"],
                    name=item["name"],
                    brand=item["brand"],
                    category=item["category"],
                    price=item["price"],
                    currency=item.get("currency", "INR"),
                    rating=item.get("rating", 4.5),
                    stock=item.get("stock", 10),
                    specs=item.get("specs", {}),
                    intended_uses=item.get("intended_uses", []),
                    features=item.get("features", []),
                    pros=item.get("pros", []),
                    cons=item.get("cons", []),
                    description=item.get("description", ""),
                    image_url=item.get("image_url", ""),
                )
                db.add(prod)
            db.commit()
            logger.info("Successfully seeded database.")
        else:
            logger.info("Database already contains %d products. Skipping seeding.", count)
    except Exception as e:
        db.rollback()
        logger.error("Error during database seeding: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
