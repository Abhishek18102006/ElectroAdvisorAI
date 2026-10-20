from app.agent.filter_rank import FilterAndRankingEngine
from app.models.product import Product


def test_hard_constraint_budget_cap():
    # Synthetic products
    p1 = Product(
        id="P1", name="Affordable", category="laptop", price=75000.0, stock=5,
        specs={"ram_gb": 16, "gpu_type": "dedicated"}, intended_uses=["machine_learning"]
    )
    p2 = Product(
        id="P2", name="Expensive", category="laptop", price=85000.0, stock=5,
        specs={"ram_gb": 16, "gpu_type": "dedicated"}, intended_uses=["machine_learning"]
    )

    state = {
        "category": "laptop",
        "budget_max": 80000.0,
        "hard_constraints": {"max_budget": 80000.0},
    }

    eligible, violations = FilterAndRankingEngine.filter_hard_constraints([p1, p2], state)
    assert len(eligible) == 1
    assert eligible[0].id == "P1"
    assert violations["over_budget"] == 1


def test_hard_constraint_ram_and_gpu():
    p1 = Product(
        id="P1", name="Integrated GPU", category="laptop", price=60000.0, stock=5,
        specs={"ram_gb": 16, "gpu_type": "integrated"}, intended_uses=["programming"]
    )
    p2 = Product(
        id="P2", name="Dedicated GPU", category="laptop", price=75000.0, stock=5,
        specs={"ram_gb": 16, "gpu_type": "dedicated"}, intended_uses=["programming", "machine_learning"]
    )

    state = {
        "category": "laptop",
        "budget_max": 80000.0,
        "hard_constraints": {"requires_gpu": True, "min_ram_gb": 16},
    }

    eligible, violations = FilterAndRankingEngine.filter_hard_constraints([p1, p2], state)
    assert len(eligible) == 1
    assert eligible[0].id == "P2"
    assert violations["missing_dedicated_gpu"] == 1


def test_ranking_prefers_portability_when_requested():
    heavy = Product(
        id="HEAVY", name="Heavy Laptop", category="laptop", price=75000.0, stock=5, rating=4.5,
        specs={"ram_gb": 16, "weight_kg": 2.5, "battery_life_hours": 4.5, "gpu_type": "dedicated"},
        intended_uses=["programming"]
    )
    light = Product(
        id="LIGHT", name="Light Laptop", category="laptop", price=75000.0, stock=5, rating=4.5,
        specs={"ram_gb": 16, "weight_kg": 1.3, "battery_life_hours": 10.0, "gpu_type": "dedicated"},
        intended_uses=["programming"]
    )

    state_portable = {
        "category": "laptop",
        "budget_max": 80000.0,
        "primary_uses": ["programming"],
        "preferences": {"portability": True},
    }

    score_heavy, _ = FilterAndRankingEngine.calculate_score(heavy, state_portable)
    score_light, _ = FilterAndRankingEngine.calculate_score(light, state_portable)

    assert score_light > score_heavy
