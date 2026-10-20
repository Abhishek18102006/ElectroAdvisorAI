import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.data.seed_data import PRODUCTS_CATALOG
from app.models.product import Product

# Use in-memory SQLite for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
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
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
