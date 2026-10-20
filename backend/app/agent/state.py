from typing import Dict, Any, List, Optional
import copy


def create_initial_state() -> Dict[str, Any]:
    """Creates a fresh, default state dictionary for a new conversation."""
    return {
        "category": "laptop",  # Default electronics category
        "budget_max": None,
        "budget_min": None,
        "primary_uses": [],  # e.g. ["programming", "machine_learning"]
        "hard_constraints": {
            "max_budget": None,
            "min_ram_gb": None,
            "requires_gpu": None,
            "required_os": None,
        },
        "preferences": {
            "portability": False,  # True if user mentioned carrying around campus / lightweight
            "battery_priority": False,
            "ml_environment": None,  # "local" | "cloud"
            "preferred_brands": [],
        },
        "missing_fields": ["primary_use", "budget"],
        "clarifications_asked": [],
        "is_ready_for_recommendation": False,
        "recommended_product_ids": [],
        "turn_count": 0,
        "last_customer_intent": None,
        "contradiction": None,
    }


def set_category(state: Dict[str, Any], new_category: str) -> Dict[str, Any]:

    """Helper to cleanly transition category and reset category-specific constraints."""
    s = copy.deepcopy(state) if state else create_initial_state()
    new_cat_lower = new_category.lower().strip()
    old_cat = s.get("category", "laptop").lower()
    if old_cat != new_cat_lower:
        s["category"] = new_cat_lower
        s["primary_uses"] = []
        s["hard_constraints"] = {
            "max_budget": s.get("budget_max"),
            "min_ram_gb": None,
            "requires_gpu": None,
            "required_os": None,
        }
        s["preferences"] = {
            "portability": False,
            "battery_priority": False,
            "ml_environment": None,
            "preferred_brands": [],
        }
        s["is_ready_for_recommendation"] = False
    else:
        s["category"] = new_cat_lower
    return s


class StateManager:

    """
    Manages and tracks customer requirements across conversation turns.
    Preserves existing requirements while updating any fields the customer modifies or clarifies.
    Handles category transitions and constraint relaxation.
    """

    @staticmethod
    def update_state(current_state: Dict[str, Any], extracted_patch: Dict[str, Any]) -> Dict[str, Any]:
        state = copy.deepcopy(current_state) if current_state else create_initial_state()
        state["turn_count"] = state.get("turn_count", 0) + 1

        # 1. Category Switch Handling
        new_category = extracted_patch.get("category")
        if new_category:
            new_cat_lower = new_category.lower()
            old_cat = state.get("category", "laptop").lower()
            if old_cat != new_cat_lower:
                # Category changed: clear previous category-specific hardware constraints
                state["category"] = new_cat_lower
                state["primary_uses"] = []
                state["hard_constraints"] = {
                    "max_budget": state["budget_max"],
                    "min_ram_gb": None,
                    "requires_gpu": None,
                    "required_os": None,
                }
                state["preferences"] = {
                    "portability": False,
                    "battery_priority": False,
                    "ml_environment": None,
                    "preferred_brands": [],
                }
                state["is_ready_for_recommendation"] = False

        # 2. Update Budget
        if extracted_patch.get("budget_max") is not None:
            state["budget_max"] = float(extracted_patch["budget_max"])
            state["hard_constraints"]["max_budget"] = state["budget_max"]
        if extracted_patch.get("budget_min") is not None:
            state["budget_min"] = float(extracted_patch["budget_min"])

        # 3. Update Contradiction if detected
        if extracted_patch.get("contradiction"):
            state["contradiction"] = extracted_patch["contradiction"]
        else:
            state["contradiction"] = None

        # 4. Update Primary Uses (cumulative unless category changed)
        new_uses = extracted_patch.get("primary_uses", [])
        if new_uses:
            existing_uses = set(state.get("primary_uses", []))
            for u in new_uses:
                existing_uses.add(u.lower())
            state["primary_uses"] = list(existing_uses)

        # 5. Update Preferences (Portability, Battery, ML environment)
        new_pref = extracted_patch.get("preferences", {})
        if new_pref:
            for k, v in new_pref.items():
                if v is not None:
                    state["preferences"][k] = v

        # 6. Hardware Constraints logic: Category and ML-aware
        category = state.get("category", "laptop")
        uses = state.get("primary_uses", [])
        new_hard = extracted_patch.get("hard_constraints", {})
        if new_hard:
            for k, v in new_hard.items():
                if v is not None:
                    state["hard_constraints"][k] = v

        if category == "laptop":
            # Cloud vs Local ML handling
            ml_env = state["preferences"].get("ml_environment")
            if extracted_patch.get("local_ml") is False or ml_env == "cloud":
                state["preferences"]["ml_environment"] = "cloud"
                state["hard_constraints"]["requires_gpu"] = False
                state["hard_constraints"]["min_ram_gb"] = max(state["hard_constraints"].get("min_ram_gb") or 8, 8)
            elif extracted_patch.get("local_ml") is True or ml_env == "local":
                state["preferences"]["ml_environment"] = "local"
                state["hard_constraints"]["requires_gpu"] = True
                state["hard_constraints"]["min_ram_gb"] = 16

            if "gaming" in uses:
                state["hard_constraints"]["requires_gpu"] = True
                state["hard_constraints"]["min_ram_gb"] = max(state["hard_constraints"].get("min_ram_gb") or 8, 8)
            elif "programming" in uses:
                state["hard_constraints"]["min_ram_gb"] = max(state["hard_constraints"].get("min_ram_gb") or 8, 8)
        else:
            # For non-laptops (monitors, headphones, smartphones, tablets), do not enforce laptop RAM/GPU constraints
            state["hard_constraints"]["min_ram_gb"] = None
            state["hard_constraints"]["requires_gpu"] = None

        if extracted_patch.get("last_intent"):
            state["last_customer_intent"] = extracted_patch["last_intent"]

        # 7. Recalculate Missing Fields
        missing = []
        if not state.get("primary_uses"):
            missing.append("primary_use")
        if state.get("budget_max") is None:
            missing.append("budget")
        if (
            category == "laptop"
            and "machine_learning" in state.get("primary_uses", [])
            and not state["preferences"].get("ml_environment")
            and not state["hard_constraints"].get("requires_gpu")
        ):
            missing.append("ml_environment")

        state["missing_fields"] = missing

        # Determine readiness
        has_use = bool(state.get("primary_uses"))
        has_budget = state.get("budget_max") is not None
        ml_ready = True
        if category == "laptop" and "machine_learning" in state.get("primary_uses", []):
            ml_ready = bool(state["preferences"].get("ml_environment") or state["hard_constraints"].get("requires_gpu") is not None)

        state["is_ready_for_recommendation"] = has_use and has_budget and ml_ready

        return state
