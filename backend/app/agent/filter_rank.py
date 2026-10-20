from typing import List, Dict, Any, Tuple, Optional
from app.models.product import Product


class FilterAndRankingEngine:
    """
    Implements a strict two-stage recommendation pipeline:
    1. Hard Constraints Filtering: Enforces mandatory rules (budget, category, minimum RAM, required GPU).
    2. Soft Preferences Ranking: Scores compliant products on use-case fit, portability, battery, value, and rating.
    """

    @classmethod
    def filter_hard_constraints(
        cls,
        products: List[Product],
        state: Dict[str, Any]
    ) -> Tuple[List[Product], Dict[str, Any]]:
        """
        Filters products against mandatory customer constraints.
        Returns (eligible_products, rejection_reasons_summary).
        """
        category = state.get("category", "laptop").lower()
        budget_max = state.get("budget_max")
        budget_min = state.get("budget_min")
        hard_constraints = state.get("hard_constraints", {})

        min_ram_gb = hard_constraints.get("min_ram_gb")
        requires_gpu = hard_constraints.get("requires_gpu")
        required_os = hard_constraints.get("required_os")
        user_uses = [u.lower() for u in state.get("primary_uses", [])]

        eligible = []
        violations = {
            "category_mismatch": 0,
            "over_budget": 0,
            "under_budget": 0,
            "insufficient_ram": 0,
            "missing_dedicated_gpu": 0,
            "os_mismatch": 0,
            "out_of_stock": 0,
        }

        for prod in products:
            # 1. Stock check
            if prod.stock <= 0:
                violations["out_of_stock"] += 1
                continue

            # 2. Category check
            if prod.category.lower() != category:
                violations["category_mismatch"] += 1
                continue

            # 3. Maximum Budget check (Hard constraint: strictly enforced)
            if budget_max is not None and prod.price > budget_max:
                violations["over_budget"] += 1
                continue

            # 4. Minimum Budget check
            if budget_min is not None and prod.price < budget_min:
                violations["under_budget"] += 1
                continue

            specs = prod.specs or {}

            # Category-specific hardware checks (only for laptops)
            if category == "laptop":
                # 5. RAM check
                if min_ram_gb is not None:
                    prod_ram = specs.get("ram_gb", 0)
                    if prod_ram < min_ram_gb:
                        violations["insufficient_ram"] += 1
                        continue

                # 6. GPU check
                if requires_gpu is True:
                    gpu_type = specs.get("gpu_type", "").lower()
                    if "gaming" in user_uses:
                        # For gaming, dedicated GPU is strictly mandatory (no Apple unified or integrated)
                        if gpu_type != "dedicated":
                            violations["missing_dedicated_gpu"] += 1
                            continue
                    else:
                        # For general ML / compute, allow dedicated GPU or Apple unified memory (Metal MPS)
                        if gpu_type not in ["dedicated", "unified"]:
                            violations["missing_dedicated_gpu"] += 1
                            continue

                # 7. OS check
                if required_os:
                    prod_os = specs.get("os", "").lower()
                    if required_os.lower() not in prod_os:
                        violations["os_mismatch"] += 1
                        continue

            eligible.append(prod)

        return eligible, violations

    @classmethod
    def calculate_score(
        cls,
        product: Product,
        state: Dict[str, Any]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculates a transparent, multi-dimensional alignment score (0 - 100) for a product.
        Formula matches documentation:
        Score = Use_Case (40) + Portability (20) + Battery (15) + Value (15) + Rating (10) = 100
        """
        specs = product.specs or {}
        intended_uses = product.intended_uses or []
        user_uses = [u.lower() for u in state.get("primary_uses", [])]
        preferences = state.get("preferences", {})
        budget_max = state.get("budget_max")
        category = state.get("category", "laptop")

        score_breakdown = {
            "use_case_score": 0.0,
            "portability_score": 0.0,
            "battery_score": 0.0,
            "value_score": 0.0,
            "rating_score": 0.0,
        }

        # 1. Use-Case Fit (up to 40 pts)
        use_matches = sum(1 for u in user_uses if u in intended_uses)
        if user_uses:
            match_ratio = use_matches / len(user_uses)
            score_breakdown["use_case_score"] = match_ratio * 30.0
        else:
            score_breakdown["use_case_score"] = 20.0

        # Extra bonus for machine learning hardware
        if "machine_learning" in user_uses and category == "laptop":
            vram = specs.get("vram_gb", 0)
            if vram >= 6:
                score_breakdown["use_case_score"] += 10.0
            elif specs.get("gpu_type") == "unified":
                score_breakdown["use_case_score"] += 8.0

        # 2. Portability Score (up to 20 pts)
        weight_kg = specs.get("weight_kg", 2.0)
        portability_requested = preferences.get("portability", False)
        max_weight_target = preferences.get("max_weight_kg", 1.8 if portability_requested else 2.5)

        if weight_kg <= 1.35:
            base_port = 20.0
        elif weight_kg <= 1.65:
            base_port = 16.0
        elif weight_kg <= 2.15:
            base_port = 12.0
        elif weight_kg <= 2.4:
            base_port = 7.0
        else:
            base_port = 2.0

        # Penalty if exceeding explicitly targeted max weight
        if weight_kg > max_weight_target:
            base_port = max(2.0, base_port - 5.0)

        score_breakdown["portability_score"] = min(20.0, base_port)

        # 3. Battery Life Score (up to 15 pts)
        battery_hours = specs.get("battery_life_hours", 6.0)
        if battery_hours >= 14.0:
            score_breakdown["battery_score"] = 15.0
        elif battery_hours >= 9.0:
            score_breakdown["battery_score"] = 12.0
        elif battery_hours >= 6.5:
            score_breakdown["battery_score"] = 9.0
        else:
            score_breakdown["battery_score"] = 4.0

        # 4. Value / Budget Utilization (up to 15 pts)
        if budget_max and budget_max > 0:
            price_ratio = product.price / budget_max
            if 0.70 <= price_ratio <= 1.0:
                score_breakdown["value_score"] = 15.0
            elif 0.50 <= price_ratio < 0.70:
                score_breakdown["value_score"] = 11.0
            else:
                score_breakdown["value_score"] = 7.0
        else:
            score_breakdown["value_score"] = 10.0

        # 5. Rating Score (up to 10 pts)
        score_breakdown["rating_score"] = (product.rating / 5.0) * 10.0

        total_score = min(
            100.0,
            round(
                score_breakdown["use_case_score"]
                + score_breakdown["portability_score"]
                + score_breakdown["battery_score"]
                + score_breakdown["value_score"]
                + score_breakdown["rating_score"],
                2,
            ),
        )

        return total_score, score_breakdown

    @classmethod
    def rank_and_select_top2(
        cls,
        eligible_products: List[Product],
        state: Dict[str, Any]
    ) -> List[Tuple[Product, float, Dict[str, float]]]:
        """
        Ranks compliant products and selects the top 2 products with complementary trade-offs.
        Guarantees that diversity selection does NOT pick an objectively worse/heavier candidate
        when the customer requested portability.
        """
        if not eligible_products:
            return []

        scored = []
        for prod in eligible_products:
            score, breakdown = cls.calculate_score(prod, state)
            scored.append((prod, score, breakdown))

        # Sort descending by total score
        scored.sort(key=lambda x: x[1], reverse=True)

        if len(scored) <= 2:
            return scored

        top_1 = scored[0]
        portability_requested = state.get("preferences", {}).get("portability", False)
        top_1_weight = top_1[0].specs.get("weight_kg", 2.0)

        # Look for the best complementary runner-up
        top_2 = scored[1]  # Default to natural second highest scorer

        if portability_requested:
            # If portability was requested, look for a candidate that is significantly LIGHTER than top 1
            for candidate in scored[1:4]:
                cand_weight = candidate[0].specs.get("weight_kg", 2.0)
                if cand_weight < top_1_weight - 0.25:
                    top_2 = candidate
                    break
        else:
            # If performance or screen is priority, look for a candidate that offers a distinct spec advantage
            top_1_gpu = top_1[0].specs.get("gpu", "")
            for candidate in scored[1:4]:
                cand_gpu = candidate[0].specs.get("gpu", "")
                if cand_gpu != top_1_gpu:
                    top_2 = candidate
                    break

        return [top_1, top_2]
