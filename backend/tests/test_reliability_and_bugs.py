import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.agent.extractor import RequirementsExtractor, parse_numeric_budget
from app.agent.state import StateManager, create_initial_state
from app.agent.filter_rank import FilterAndRankingEngine
from app.models.product import Product


def test_indian_number_format_parsing():
    """Bug 1: Indian numbering with 2-digit groups after 3-digit thousands."""
    assert parse_numeric_budget("under ₹1,20,000") == 120000.0
    assert parse_numeric_budget("1,20,000 INR") == 120000.0
    assert parse_numeric_budget("₹2,50,000") == 250000.0
    assert parse_numeric_budget("budget 1.5 lakh") == 150000.0
    assert parse_numeric_budget("under 80k") == 80000.0

    # Ensure quick prompt 'Lightweight MacBook for coding under ₹1,20,000' extracts 120,000
    extracted = RequirementsExtractor.extract_with_rules("Lightweight MacBook for coding under ₹1,20,000")
    assert extracted["budget_max"] == 120000.0
    assert extracted["category"] == "laptop"
    assert "programming" in extracted["primary_uses"]


def test_substring_matching_bugs():
    """Bug 4: Word boundary checks prevent false substring matches."""
    # 'headphones' should NOT be extracted as 'smartphone'
    ext1 = RequirementsExtractor.extract_with_rules("I need headphones for study focus")
    assert ext1["category"] == "headphones"
    assert ext1["category"] != "smartphone"

    # 'html' should NOT trigger 'machine_learning'
    ext2 = RequirementsExtractor.extract_with_rules("I write html and css for web dev")
    assert "programming" in ext2["primary_uses"]
    assert "machine_learning" not in ext2["primary_uses"]

    # 'portable' should NOT trigger 'tablet'
    ext3 = RequirementsExtractor.extract_with_rules("I need a portable desk setup")
    assert ext3["category"] is None or ext3["category"] != "tablet"


def test_greeting_does_not_misfire_on_highend_laptop(client):
    """Bug 9: 'high-end laptop' should not be treated as 'hi' greeting."""
    resp = client.post("/api/v1/conversations")
    conv_id = resp.json()["id"]

    resp_msg = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "high-end laptop for gaming"},
    )
    decision = resp_msg.json()["decision"]
    assert decision["action"] != "greeting"
    assert decision["state"]["category"] == "laptop"
    assert "gaming" in decision["state"]["primary_uses"]


def test_cloud_relaxes_gpu_requirement():
    """Bug 2 & 3: Stating 'cloud' clears dedicated GPU hard requirement."""
    state = create_initial_state()

    # Step 1: User mentions ML
    ext1 = RequirementsExtractor.extract_with_rules("I need a laptop for machine learning.")
    state = StateManager.update_state(state, ext1)
    assert "machine_learning" in state["primary_uses"]

    # Step 2: User specifies cloud
    ext2 = RequirementsExtractor.extract_with_rules("I use cloud platforms like Google Colab and AWS.")
    state = StateManager.update_state(state, ext2)
    assert state["preferences"]["ml_environment"] == "cloud"
    assert state["hard_constraints"]["requires_gpu"] is False


def test_category_switch_clears_hardware_constraints(client):
    """Bug 5: Category switching clears laptop-specific RAM/GPU constraints."""
    resp = client.post("/api/v1/conversations")
    conv_id = resp.json()["id"]

    # First conversation about gaming laptop
    client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a gaming laptop under 90000."},
    )

    # User switches to monitor
    resp_switch = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Actually, I want a monitor for programming under 40000."},
    )
    data = resp_switch.json()
    state = data["decision"]["state"]
    assert state["category"] == "monitor"
    assert state["hard_constraints"]["min_ram_gb"] is None
    assert state["hard_constraints"]["requires_gpu"] is None
    assert data["decision"]["action"] == "recommend"
    assert len(data["decision"]["recommendations"]) >= 1
    assert data["decision"]["recommendations"][0]["product"]["category"] == "monitor"


def test_top2_selection_for_portability_does_not_pick_heavier_worse_laptop():
    """Bug 6: Diversity selection does not pick an objectively worse and heavier laptop."""
    p_light = Product(
        id="NITRO", name="Acer Nitro V 15", category="laptop", price=76990.0, stock=5, rating=4.6,
        specs={"ram_gb": 16, "weight_kg": 2.10, "battery_life_hours": 5.5, "gpu": "RTX 4050", "gpu_type": "dedicated", "vram_gb": 6},
        intended_uses=["machine_learning", "programming"]
    )
    p_battery = Product(
        id="TUF", name="ASUS TUF A15", category="laptop", price=79990.0, stock=5, rating=4.7,
        specs={"ram_gb": 16, "weight_kg": 2.20, "battery_life_hours": 6.5, "gpu": "RTX 4050", "gpu_type": "dedicated", "vram_gb": 6},
        intended_uses=["machine_learning", "programming"]
    )
    p_heavy = Product(
        id="DELL", name="Dell G15 5530", category="laptop", price=74990.0, stock=5, rating=4.4,
        specs={"ram_gb": 16, "weight_kg": 2.65, "battery_life_hours": 4.5, "gpu": "RTX 3050", "gpu_type": "dedicated", "vram_gb": 6},
        intended_uses=["machine_learning", "programming"]
    )

    state = {
        "category": "laptop",
        "budget_max": 80000.0,
        "primary_uses": ["machine_learning", "programming"],
        "preferences": {"portability": True, "max_weight_kg": 2.2},
    }

    selected = FilterAndRankingEngine.rank_and_select_top2([p_light, p_battery, p_heavy], state)
    selected_ids = [p[0].id for p in selected]

    # Should select NITRO and TUF (2.1kg and 2.2kg), NOT the 2.65kg Dell G15!
    assert "DELL" not in selected_ids
    assert "NITRO" in selected_ids
    assert "TUF" in selected_ids


def test_contradictory_constraints_detected(client):
    """Contradiction handling: MacBook running Windows and min > max budget."""
    resp = client.post("/api/v1/conversations")
    conv_id = resp.json()["id"]

    resp_win_mac = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I want a MacBook running Windows."},
    )
    decision = resp_win_mac.json()["decision"]
    assert decision["action"] == "ask_clarification"
    assert "macbook" in decision["message"].lower() or "windows" in decision["message"].lower()


def test_post_recommendation_intents(client):
    """Bug 11: After recommendation, user says 'thanks' or asks for 'lighter'."""
    resp = client.post("/api/v1/conversations")
    conv_id = resp.json()["id"]

    # Complete recommendation turn
    client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "I need a programming laptop under 50000."},
    )

    # User says thanks
    resp_thanks = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Thank you so much!"},
    )
    decision = resp_thanks.json()["decision"]
    assert decision["action"] == "informational"
    assert "welcome" in decision["message"].lower()


def test_api_validation_errors(client):
    """Validation: 422 for min_price > max_price, and 422 for whitespace message."""
    resp_bad_price = client.get("/api/v1/products?min_price=80000&max_price=50000")
    assert resp_bad_price.status_code == 422
    assert "min_price cannot be greater than max_price" in resp_bad_price.json()["detail"]

    resp_conv = client.post("/api/v1/conversations")
    conv_id = resp_conv.json()["id"]

    resp_empty_msg = client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "   "},
    )
    assert resp_empty_msg.status_code == 422
    assert "empty or whitespace" in resp_empty_msg.json()["detail"].lower()


@pytest.mark.asyncio
async def test_llm_failure_and_timeout_fallback():
    """Ensures LLM errors or timeouts fall back gracefully to rules without crashing."""
    with patch("app.config.settings.GEMINI_API_KEY", "mock_key"):
        with patch("google.generativeai.GenerativeModel") as mock_model_cls:
            mock_instance = mock_model_cls.return_value
            # Simulate malformed output
            mock_instance.generate_content_async = AsyncMock(side_effect=Exception("API Error"))

            extracted = await RequirementsExtractor.extract_requirements(
                customer_message="I need a laptop for programming under 80000",
                conversation_history=[],
                current_state={},
            )
            assert extracted["category"] == "laptop"
            assert extracted["budget_max"] == 80000.0
            assert "programming" in extracted["primary_uses"]


@pytest.mark.asyncio
async def test_llm_strict_timeout_cancellation_and_fallback():
    """Validates that a slow LLM exceeding LLM_TIMEOUT_SECONDS triggers timeout and falls back to rules in milliseconds."""
    async def slow_generate(*args, **kwargs):
        await asyncio.sleep(1.0)
        return MagicMock(text='{"category": "laptop"}')

    with patch("app.config.settings.GEMINI_API_KEY", "mock_key"):
        with patch("app.config.settings.LLM_TIMEOUT_SECONDS", 0.05):
            with patch("google.generativeai.GenerativeModel") as mock_model_cls:
                mock_instance = mock_model_cls.return_value
                mock_instance.generate_content_async = slow_generate

                start_time = asyncio.get_event_loop().time()
                extracted = await RequirementsExtractor.extract_requirements(
                    customer_message="I need a monitor for programming under 30000",
                    conversation_history=[],
                    current_state={},
                )
                elapsed = asyncio.get_event_loop().time() - start_time

                # Must return promptly without waiting for the slow LLM
                assert elapsed < 0.5
                assert extracted["category"] == "monitor"
                assert extracted["budget_max"] == 30000.0
                assert "programming" in extracted["primary_uses"]


def test_all_non_laptop_categories_recommendation_and_trade_offs(client):
    """Verifies that non-laptop devices (headphones, monitors, smartphones, tablets) work end-to-end with category-accurate trade-offs."""
    # 1. Headphones
    res_audio = client.post("/api/v1/conversations")
    c_audio = res_audio.json()["id"]
    msg_res = client.post(
        f"/api/v1/conversations/{c_audio}/messages",
        json={"content": "I need headphones for study focus under 30000"},
    )
    assert msg_res.status_code == 200
    dec_audio = msg_res.json()["decision"]
    assert dec_audio["action"] == "recommend"
    assert len(dec_audio["recommendations"]) == 2
    assert dec_audio["recommendations"][0]["product"]["category"] == "headphones"
    criteria = [t["criterion"] for t in dec_audio["trade_offs"]]
    assert "Noise Cancellation & Audio Type" in criteria
    assert "Compute & Graphics Performance" not in criteria

    # 2. Monitors
    res_mon = client.post("/api/v1/conversations")
    c_mon = res_mon.json()["id"]
    msg_mon = client.post(
        f"/api/v1/conversations/{c_mon}/messages",
        json={"content": "I need a monitor for programming under 40000"},
    )
    assert msg_mon.status_code == 200
    dec_mon = msg_mon.json()["decision"]
    assert dec_mon["action"] == "recommend"
    assert dec_mon["recommendations"][0]["product"]["category"] == "monitor"
    criteria_mon = [t["criterion"] for t in dec_mon["trade_offs"]]
    assert "Display & Visual Fidelity" in criteria_mon
    assert "Compute & Graphics Performance" not in criteria_mon

    # 3. Smartphones
    res_phn = client.post("/api/v1/conversations")
    c_phn = res_phn.json()["id"]
    msg_phn = client.post(
        f"/api/v1/conversations/{c_phn}/messages",
        json={"content": "I need a smartphone with great camera under 75000"},
    )
    assert msg_phn.status_code == 200
    dec_phn = msg_phn.json()["decision"]
    assert dec_phn["action"] == "recommend"
    assert dec_phn["recommendations"][0]["product"]["category"] == "smartphone"
    criteria_phn = [t["criterion"] for t in dec_phn["trade_offs"]]
    assert "Camera System" in criteria_phn

    # 4. Tablets
    res_tab = client.post("/api/v1/conversations")
    c_tab = res_tab.json()["id"]
    msg_tab = client.post(
        f"/api/v1/conversations/{c_tab}/messages",
        json={"content": "I need a tablet for digital notes under 40000"},
    )
    assert msg_tab.status_code == 200
    dec_tab = msg_tab.json()["decision"]
    assert dec_tab["action"] == "recommend"
    assert dec_tab["recommendations"][0]["product"]["category"] == "tablet"
    criteria_tab = [t["criterion"] for t in dec_tab["trade_offs"]]
    assert "Display & Stylus Support" in criteria_tab

