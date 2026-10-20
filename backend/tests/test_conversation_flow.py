def test_full_assessment_example_conversation_flow(client):
    # Step 1: Create a conversation
    resp_create = client.post("/api/v1/conversations")
    assert resp_create.status_code == 201
    conv_id = resp_create.json()["id"]

    # Turn 1: Customer: "I need a laptop for college."
    resp_turn_1 = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a laptop for college."},
    )
    assert resp_turn_1.status_code == 200
    t1_data = resp_turn_1.json()
    assert t1_data["decision"]["action"] == "ask_clarification"
    assert "primary_use" in t1_data["decision"]["missing_info"]
    assert "mainly use it for" in t1_data["agent_message"]["content"].lower()

    # Turn 2: Customer: "Programming and machine learning. My budget is limited."
    resp_turn_2 = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Programming and machine learning. My budget is limited."},
    )
    assert resp_turn_2.status_code == 200
    t2_data = resp_turn_2.json()
    assert t2_data["decision"]["action"] == "ask_clarification"
    assert "budget" in t2_data["decision"]["missing_info"]
    assert "budget" in t2_data["agent_message"]["content"].lower()

    # Turn 3: Customer: "Around 80,000. Mostly local experiments, and I carry it around campus."
    resp_turn_3 = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Around 80,000. Mostly local experiments, and I carry it around campus."},
    )
    assert resp_turn_3.status_code == 200
    t3_data = resp_turn_3.json()
    decision = t3_data["decision"]

    # The agent should now use these requirements to search, filter, rank, and explain suitable products!
    # No more questions asked!
    assert decision["action"] == "recommend"
    assert len(decision["recommendations"]) == 2
    assert len(decision["trade_offs"]) >= 2

    # Verify both recommendations strictly adhere to the 80,000 INR budget cap
    rec1 = decision["recommendations"][0]["product"]
    rec2 = decision["recommendations"][1]["product"]
    assert rec1["price"] <= 80000.0
    assert rec2["price"] <= 80000.0

    # Verify both recommendations have specs appropriate for local ML (dedicated RTX GPU or 16GB RAM)
    assert rec1["specs"]["ram_gb"] >= 16
    assert rec2["specs"]["ram_gb"] >= 16
    assert rec1["specs"]["gpu_type"] in ["dedicated", "unified"]
    assert rec2["specs"]["gpu_type"] in ["dedicated", "unified"]

    # Verify conversation history retrieval endpoint
    resp_history = client.get(f"/api/v1/conversations/{conv_id}")
    assert resp_history.status_code == 200
    hist_data = resp_history.json()
    assert len(hist_data["messages"]) == 6  # 3 customer + 3 agent
    assert hist_data["state"]["budget_max"] == 80000.0
    assert hist_data["state"]["is_ready_for_recommendation"] is True
