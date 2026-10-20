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
