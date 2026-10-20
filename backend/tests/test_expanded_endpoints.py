import pytest


def test_get_categories(client):
    response = client.get("/api/v1/categories")
    assert response.status_code == 200
    data = response.json()
    assert "total_categories" in data
    assert data["total_categories"] > 0
    categories = {c["name"]: c for c in data["categories"]}
    assert "laptop" in categories
    assert categories["laptop"]["count"] >= 10
    assert categories["laptop"]["min_price"] > 0
    assert categories["laptop"]["max_price"] >= categories["laptop"]["min_price"]
    assert len(categories["laptop"]["brands"]) > 0


def test_compare_products_success(client):
    response = client.get("/api/v1/products/compare?ids=LAP-001,LAP-004")
    assert response.status_code == 200
    data = response.json()
    assert data["product_ids"] == ["LAP-001", "LAP-004"]
    assert len(data["products"]) == 2
    assert "comparison_matrix" in data
    assert "price" in data["comparison_matrix"]
    assert "weight_kg" in data["comparison_matrix"]
    assert "ram_gb" in data["comparison_matrix"]
    assert len(data["key_differences"]) > 0


def test_compare_products_validation_and_errors(client):
    # Less than 2 IDs
    res1 = client.get("/api/v1/products/compare?ids=LAP-001")
    assert res1.status_code == 422

    # Non-existent ID
    res2 = client.get("/api/v1/products/compare?ids=LAP-001,FAKE-999")
    assert res2.status_code == 404


def test_put_requirements_override(client):
    conv_res = client.post("/api/v1/conversations")
    conv_id = conv_res.json()["id"]

    override_payload = {
        "budget_max": 75000.0,
        "min_ram_gb": 16,
        "requires_gpu": True,
        "portability_important": True,
        "notes": "Prefer lightweight build with high battery",
    }
    res = client.put(f"/api/v1/conversations/{conv_id}/requirements", json=override_payload)
    assert res.status_code == 200
    data = res.json()
    state = data["state"]
    assert state["budget_max"] == 75000.0
    assert state["hard_constraints"]["max_budget"] == 75000.0
    assert state["hard_constraints"]["min_ram_gb"] == 16
    assert state["hard_constraints"]["requires_gpu"] is True
    assert state["preferences"]["portability_important"] is True


def test_feedback_submission(client):
    conv_res = client.post("/api/v1/conversations")
    conv_id = conv_res.json()["id"]

    feedback_payload = {
        "rating": "thumbs_up",
        "purchase_intent": True,
        "selected_product_id": "LAP-001",
        "comment": "Perfect recommendation for my college coursework",
    }
    res = client.post(f"/api/v1/conversations/{conv_id}/feedback", json=feedback_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "received"
    assert data["conversation_id"] == conv_id
    assert data["feedback"]["rating"] == "thumbs_up"
    assert data["feedback"]["purchase_intent"] is True


def test_debug_endpoint(client):
    conv_res = client.post("/api/v1/conversations")
    conv_id = conv_res.json()["id"]

    # Send a message first
    client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Laptop for coding under 80000"},
    )

    debug_res = client.get(f"/api/v1/conversations/{conv_id}/debug")
    assert debug_res.status_code == 200
    data = debug_res.json()
    assert data["conversation_id"] == conv_id
    assert "catalog_diagnostics" in data
    assert data["catalog_diagnostics"]["total_catalog_products"] >= 23
    assert data["catalog_diagnostics"]["category"] == "laptop"
    assert data["catalog_diagnostics"]["passing_hard_filters_count"] > 0
    assert len(data["catalog_diagnostics"]["top_candidates"]) > 0


def test_delete_conversation(client):
    conv_res = client.post("/api/v1/conversations")
    conv_id = conv_res.json()["id"]

    # Delete conversation
    del_res = client.delete(f"/api/v1/conversations/{conv_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify conversation is gone
    get_res = client.get(f"/api/v1/conversations/{conv_id}")
    assert get_res.status_code == 404
