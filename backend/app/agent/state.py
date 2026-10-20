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
            "preferred_brands": [],
        },
        "missing_fields": ["primary_use", "budget"],
        "clarifications_asked": [],
        "is_ready_for_recommendation": False,
        "recommended_product_ids": [],
        "turn_count": 0,
        "last_customer_intent": None,
    }


class StateManager:
    """
    Manages and tracks customer requirements across conversation turns.
    Preserves existing requirements while updating any fields the customer modifies or clarifies.
    """

    @staticmethod
    def update_state(current_state: Dict[str, Any], extracted_patch: Dict[str, Any]) -> Dict[str, Any]:
        state = copy.deepcopy(current_state) if current_state else create_initial_state()
        state["turn_count"] = state.get("turn_count", 0) + 1

        # 1. Update Category if explicitly detected
        if extracted_patch.get("category"):
            state["category"] = extracted_patch["category"].lower()

        # 2. Update Budget
        if extracted_patch.get("budget_max") is not None:
            state["budget_max"] = float(extracted_patch["budget_max"])
            state["hard_constraints"]["max_budget"] = state["budget_max"]
        if extracted_patch.get("budget_min") is not None:
            state["budget_min"] = float(extracted_patch["budget_min"])

        # 3. Update Primary Uses (cumulative unless explicitly cleared)
        new_uses = extracted_patch.get("primary_uses", [])
        if new_uses:
            existing_uses = set(state.get("primary_uses", []))
            for u in new_uses:
                existing_uses.add(u.lower())
            state["primary_uses"] = list(existing_uses)

        # 4. Update Hard Constraints (RAM, GPU, OS)
        new_hard = extracted_patch.get("hard_constraints", {})
        if new_hard:
            for k, v in new_hard.items():
                if v is not None:
                    state["hard_constraints"][k] = v

        # Infer hard constraints from uses if not explicitly set
        uses = state.get("primary_uses", [])
        if "machine_learning" in uses:
            is_local = extracted_patch.get("local_ml")
            if is_local is not False:  # Local by default unless specified as cloud
                state["hard_constraints"]["requires_gpu"] = True
                state["hard_constraints"]["min_ram_gb"] = max(state["hard_constraints"].get("min_ram_gb") or 16, 16)
        elif "gaming" in uses:
            state["hard_constraints"]["requires_gpu"] = True
            state["hard_constraints"]["min_ram_gb"] = max(state["hard_constraints"].get("min_ram_gb") or 8, 8)
        elif "programming" in uses:
            state["hard_constraints"]["min_ram_gb"] = max(state["hard_constraints"].get("min_ram_gb") or 8, 8)

        # 5. Update Preferences (Portability, Battery, Brands)
        new_pref = extracted_patch.get("preferences", {})
        if new_pref:
            for k, v in new_pref.items():
                if v is not None:
                    state["preferences"][k] = v

        if extracted_patch.get("last_intent"):
            state["last_customer_intent"] = extracted_patch["last_intent"]

        # 6. Recalculate Missing Fields
        missing = []
        if not state.get("primary_uses"):
            missing.append("primary_use")
        if state.get("budget_max") is None:
            missing.append("budget")

        state["missing_fields"] = missing

        # Determine readiness
        has_use = bool(state.get("primary_uses"))
        has_budget = state.get("budget_max") is not None
        state["is_ready_for_recommendation"] = has_use and has_budget

        return state
