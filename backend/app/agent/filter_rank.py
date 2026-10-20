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

            # 5. RAM check
            if min_ram_gb is not None:
                prod_ram = specs.get("ram_gb", 0)
                if prod_ram < min_ram_gb:
                    violations["insufficient_ram"] += 1
                    continue

            # 6. GPU check
            if requires_gpu is True:
                gpu_type = specs.get("gpu_type", "").lower()
                # Unified memory on Apple silicon is treated as capable for general compute, but for CUDA local ML dedicated NVIDIA is preferred
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
        """
        specs = product.specs or {}
        intended_uses = product.intended_uses or []
        user_uses = [u.lower() for u in state.get("primary_uses", [])]
        preferences = state.get("preferences", {})
        budget_max = state.get("budget_max")

        score_breakdown = {
            "use_case_score": 0.0,
            "portability_score": 0.0,
            "battery_score": 0.0,
            "value_score": 0.0,
            "rating_score": 0.0,
        }

        # 1. Use-Case Fit (up to 40 pts)
        use_matches = 0
        for u in user_uses:
            if u in intended_uses:
                use_matches += 1

        if user_uses:
            match_ratio = use_matches / len(user_uses)
            score_breakdown["use_case_score"] += match_ratio * 30.0
        else:
            score_breakdown["use_case_score"] += 15.0  # neutral

        # Extra bonus for machine learning hardware
        if "machine_learning" in user_uses:
            vram = specs.get("vram_gb", 0)
            if vram >= 6:
                score_breakdown["use_case_score"] += 10.0
            elif specs.get("gpu_type") == "unified":
                score_breakdown["use_case_score"] += 8.0

        # 2. Portability Score (up to 20 pts)
        weight_kg = specs.get("weight_kg", 2.0)
        portability_requested = preferences.get("portability", False)

        if weight_kg <= 1.35:
            base_port = 20.0
        elif weight_kg <= 1.65:
            base_port = 15.0
        elif weight_kg <= 2.15:
            base_port = 8.0
        else:
            base_port = 2.0

        # Amplify portability weight if customer specified campus mobility
        score_breakdown["portability_score"] = base_port * (1.2 if portability_requested else 0.8)

        # 3. Battery Life Score (up to 15 pts)
        battery_hours = specs.get("battery_life_hours", 6.0)
        if battery_hours >= 14.0:
            score_breakdown["battery_score"] = 15.0
        elif battery_hours >= 9.0:
            score_breakdown["battery_score"] = 12.0
        elif battery_hours >= 6.5:
            score_breakdown["battery_score"] = 8.0
        else:
            score_breakdown["battery_score"] = 4.0

        # 4. Value / Budget Utilization (up to 15 pts)
        if budget_max and budget_max > 0:
            # Reward maximizing specs within budget
            price_ratio = product.price / budget_max
            if 0.70 <= price_ratio <= 1.0:
                score_breakdown["value_score"] = 15.0
            elif 0.50 <= price_ratio < 0.70:
                score_breakdown["value_score"] = 12.0
            else:
                score_breakdown["value_score"] = 8.0
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
                2
            )
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

        # Top product is the highest overall scorer
        top_1 = scored[0]

        # For Top 2, select a product that offers a meaningful alternative
        # e.g., if Top 1 is heavy/high-performance, look for the highest scoring portable or alternative option
        top_1_weight = top_1[0].specs.get("weight_kg", 2.0)
        top_2 = scored[1]

        # Check if there is another strong contender with a distinctly different strength (e.g. much lighter, or larger battery)
        for candidate in scored[1:4]:
            cand_weight = candidate[0].specs.get("weight_kg", 2.0)
            if abs(cand_weight - top_1_weight) >= 0.4:
                top_2 = candidate
                break

        return [top_1, top_2]
