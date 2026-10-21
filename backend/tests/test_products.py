def test_list_products_pagination(client):
    response = client.get("/api/v1/products?page=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["page"] == 1
    assert data["limit"] == 5
    assert len(data["items"]) == 5


def test_filter_by_category(client):
    response = client.get("/api/v1/products?category=laptop")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert item["category"].lower() == "laptop"


def test_filter_by_price_range(client):
    response = client.get("/api/v1/products?min_price=40000&max_price=80000")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert 40000 <= item["price"] <= 80000


def test_get_product_detail_success(client):
    response = client.get("/api/v1/products/LAP-001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "LAP-001"
    assert "Lenovo" in data["brand"]
    assert "specs" in data
    assert data["specs"]["ram_gb"] == 8


def test_get_product_detail_not_found(client):
    response = client.get("/api/v1/products/NONEXISTENT-999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_catalog_contains_50_generalised_records_across_categories(client):
    """Verifies that the catalog contains 50 generalised records spanning all 5 categories."""
    response = client.get("/api/v1/products?limit=100")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 50
    assert len(data["items"]) == 50

    categories = {p["category"] for p in data["items"]}
    assert categories == {"laptop", "smartphone", "tablet", "monitor", "headphones"}

    # Verify new product detail retrieval for different categories
    res_lap = client.get("/api/v1/products/LAP-017")
    assert res_lap.status_code == 200
    assert res_lap.json()["name"] == "ASUS ROG Zephyrus G16 (RTX 4070)"

    res_mon = client.get("/api/v1/products/MON-005")
    assert res_mon.status_code == 200
    assert "ViewFinity" in res_mon.json()["name"]

    res_aud = client.get("/api/v1/products/AUD-004")
    assert res_aud.status_code == 200
    assert "Sennheiser" in res_aud.json()["brand"]

