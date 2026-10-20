from app.agent.state import StateManager, create_initial_state
from app.agent.extractor import RequirementsExtractor, parse_numeric_budget


def test_parse_numeric_budget():
    assert parse_numeric_budget("Around 80,000") == 80000.0
    assert parse_numeric_budget("80k") == 80000.0
    assert parse_numeric_budget("₹75000") == 75000.0
    assert parse_numeric_budget("under 1 lakh") == 100000.0
    assert parse_numeric_budget("1.5 lakh") == 150000.0
    assert parse_numeric_budget("My budget is limited.") is None


def test_state_initialization():
    state = create_initial_state()
    assert state["category"] == "laptop"
    assert state["budget_max"] is None
    assert state["primary_uses"] == []
    assert state["is_ready_for_recommendation"] is False
    assert "primary_use" in state["missing_fields"]
    assert "budget" in state["missing_fields"]


def test_state_tracking_and_mind_change():
    state = create_initial_state()

    # Turn 1: User mentions coursework and programming
    extracted_1 = RequirementsExtractor.extract_with_rules("I need a laptop for programming and machine learning with dedicated GPU.")
    state = StateManager.update_state(state, extracted_1)

    assert "programming" in state["primary_uses"]
    assert "machine_learning" in state["primary_uses"]
    assert state["hard_constraints"]["requires_gpu"] is True
    assert state["budget_max"] is None

    # Turn 2: User gives initial budget
    extracted_2 = RequirementsExtractor.extract_with_rules("My budget is around 80,000.")
    state = StateManager.update_state(state, extracted_2)

    assert state["budget_max"] == 80000.0
    assert state["hard_constraints"]["max_budget"] == 80000.0
    assert state["is_ready_for_recommendation"] is True

    # Turn 3: User changes their mind! Budget decreased to 60k
    extracted_3 = RequirementsExtractor.extract_with_rules("Actually, my budget changed to 60000.")
    state = StateManager.update_state(state, extracted_3)

    assert state["budget_max"] == 60000.0
    assert state["hard_constraints"]["max_budget"] == 60000.0
    # Uses should be preserved!
    assert "programming" in state["primary_uses"]
    assert "machine_learning" in state["primary_uses"]


def test_portability_preference_extraction():
    state = create_initial_state()
    extracted = RequirementsExtractor.extract_with_rules("Mostly local experiments, and I carry it around campus.")
    state = StateManager.update_state(state, extracted)

    assert state["preferences"]["portability"] is True
    assert state["preferences"]["ml_environment"] == "local"
    assert state["hard_constraints"]["requires_gpu"] is True
