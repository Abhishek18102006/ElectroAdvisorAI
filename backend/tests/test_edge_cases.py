def test_single_turn_complete_requirements(client):
    """If user provides all necessary details in first message, recommend immediately without follow-up."""
    resp_create = client.post("/api/v1/conversations")
    conv_id = resp_create.json()["id"]

    msg = "I need a laptop for programming and machine learning with dedicated GPU under 80000 INR."
    resp = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": msg})
    assert resp.status_code == 200
    decision = resp.json()["decision"]

    assert decision["action"] == "recommend"
    assert len(decision["recommendations"]) == 2
    assert decision["recommendations"][0]["product"]["price"] <= 80000.0


def test_impossible_constraints_honest_no_match(client):
    """When no products satisfy hard constraints, say so honestly without inventing products."""
    resp_create = client.post("/api/v1/conversations")
    conv_id = resp_create.json()["id"]

    # Local ML with dedicated RTX GPU under 20,000 INR is impossible in our catalog
    msg = "I want a laptop for local machine learning experiments with dedicated GPU under 20000 INR."
    resp = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": msg})
    assert resp.status_code == 200
    decision = resp.json()["decision"]

    assert decision["action"] == "no_match"
    assert len(decision["recommendations"]) == 0
    assert "currently no laptop" in decision["message"].lower() or "budget" in decision["message"].lower()


def test_customer_changes_budget_mid_conversation(client):
    """Agent tracks updated requirements when customer changes their mind."""
    resp_create = client.post("/api/v1/conversations")
    conv_id = resp_create.json()["id"]

    # Start with 80k
    client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a programming laptop under 80000."},
    )

    # Change to 50k
    resp_change = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Actually, my budget changed to 50000."},
    )
    decision = resp_change.json()["decision"]
    assert decision["state"]["budget_max"] == 50000.0
    for rec in decision["recommendations"]:
        assert rec["product"]["price"] <= 50000.0


def test_greeting_intent(client):
    """Friendly greeting prompts user without crashing."""
    resp_create = client.post("/api/v1/conversations")
    conv_id = resp_create.json()["id"]

    resp = client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": "Hello!"})
    assert resp.status_code == 200
    decision = resp.json()["decision"]
    assert decision["action"] == "greeting"
    assert "welcome" in decision["message"].lower()


def test_conversation_reset(client):
    """Resetting conversation restores initial state."""
    resp_create = client.post("/api/v1/conversations")
    conv_id = resp_create.json()["id"]

    client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a laptop for gaming under 90000."},
    )

    resp_reset = client.post(f"/api/v1/conversations/{conv_id}/reset")
    assert resp_reset.status_code == 200
    state = resp_reset.json()["state"]
    assert state["budget_max"] is None
    assert state["primary_uses"] == []
