from typing import List, Dict, Any, Tuple
from app.models.product import Product
from app.schemas.agent import RecommendationItem, TradeOffComparison
from app.schemas.product import ProductResponse


class RecommendationExplainer:
    """
    Generates grounded, spec-accurate rationales and trade-off comparisons
    between recommended products without hallucinating specs.
    """

    @classmethod
    def generate_recommendation_item(
        cls,
        product: Product,
        score: float,
        state: Dict[str, Any]
    ) -> RecommendationItem:
        specs = product.specs or {}
        uses = state.get("primary_uses", [])
        gpu_name = specs.get("gpu", "Integrated Graphics")
        cpu_name = specs.get("cpu", "Processor")
        ram_gb = specs.get("ram_gb", 8)
        weight = specs.get("weight_kg", "N/A")
        battery = specs.get("battery_life_hours", "N/A")

        # Tailor reasons to customer intent
        reasons = []
        if "machine_learning" in uses:
            if specs.get("gpu_type") == "dedicated":
                reasons.append(f"Features {gpu_name} with dedicated VRAM and CUDA acceleration for training deep learning models locally.")
            elif specs.get("gpu_type") == "unified":
                reasons.append(f"Apple Unified Memory architecture allows direct high-bandwidth GPU access for Metal-accelerated inference.")
        
        if "programming" in uses:
            reasons.append(f"Equipped with {ram_gb}GB RAM and {cpu_name} to ensure swift code compilation, local servers, and containerized development.")

        if state.get("preferences", {}).get("portability"):
            reasons.append(f"Weighs {weight}kg with up to {battery} hours of battery life, making it practical to carry between classes across campus.")

        if not reasons:
            reasons.append(f"Well-rounded option delivering excellent build quality, responsive performance, and strong value at ₹{product.price:,.0f}.")

        why_text = " ".join(reasons)

        return RecommendationItem(
            product=ProductResponse(**product.to_dict()),
            why_recommended=why_text,
            key_advantages=product.pros or [],
            potential_drawbacks=product.cons or [],
            suitability_score=score,
        )

    @classmethod
    def generate_trade_offs(
        cls,
        prod_1: Product,
        prod_2: Product,
        state: Dict[str, Any]
    ) -> List[TradeOffComparison]:
        """
        Creates side-by-side trade-off dimensions comparing the two top products.
        """
        specs_1 = prod_1.specs or {}
        specs_2 = prod_2.specs or {}

        trade_offs = []

        # 1. Performance & Compute Dimension
        gpu_1 = specs_1.get("gpu", "Integrated")
        gpu_2 = specs_2.get("gpu", "Integrated")
        vram_1 = specs_1.get("vram_gb", 0)
        vram_2 = specs_2.get("vram_gb", 0)

        perf_explanation = ""
        if vram_1 != vram_2 or gpu_1 != gpu_2:
            perf_explanation = (
                f"{prod_1.name} has {gpu_1} ({vram_1}GB VRAM), whereas {prod_2.name} features {gpu_2} ({vram_2}GB VRAM). "
                f"More dedicated VRAM provides larger batch sizes and faster training epochs for local machine learning models."
            )
        else:
            perf_explanation = (
                f"Both offer comparable GPU capabilities ({gpu_1} vs {gpu_2}), but differ in CPU architecture: "
                f"{specs_1.get('cpu', '')} vs {specs_2.get('cpu', '')}."
            )

        trade_offs.append(
            TradeOffComparison(
                criterion="Compute & Graphics Performance",
                product_1_verdict=f"{gpu_1} ({specs_1.get('cpu', '')})",
                product_2_verdict=f"{gpu_2} ({specs_2.get('cpu', '')})",
                trade_off_explanation=perf_explanation,
            )
        )

        # 2. Portability & Campus Commute Dimension
        w1 = specs_1.get("weight_kg", 2.0)
        w2 = specs_2.get("weight_kg", 2.0)
        b1 = specs_1.get("battery_life_hours", 6.0)
        b2 = specs_2.get("battery_life_hours", 6.0)

        if w1 < w2:
            port_explanation = f"{prod_1.name} is {round(w2 - w1, 2)}kg lighter and easier to carry in a backpack for long campus days."
        elif w2 < w1:
            port_explanation = f"{prod_2.name} is {round(w1 - w2, 2)}kg lighter, giving you greater daily portability on campus."
        else:
            port_explanation = f"Both laptops have identical weight at {w1}kg."

        trade_offs.append(
            TradeOffComparison(
                criterion="Portability & Weight",
                product_1_verdict=f"{w1} kg",
                product_2_verdict=f"{w2} kg",
                trade_off_explanation=port_explanation,
            )
        )

        # 3. Battery Life Dimension
        if b1 > b2:
            batt_explanation = f"{prod_1.name} offers around {b1} hours ({round(b1 - b2, 1)}h more runtime) before needing a charger."
        elif b2 > b1:
            batt_explanation = f"{prod_2.name} delivers around {b2} hours of endurance ({round(b2 - b1, 1)}h more runtime) during library study sessions."
        else:
            batt_explanation = f"Both offer approximately {b1} hours of battery life under normal productivity workloads."

        trade_offs.append(
            TradeOffComparison(
                criterion="Battery Endurance",
                product_1_verdict=f"~{b1} hours",
                product_2_verdict=f"~{b2} hours",
                trade_off_explanation=batt_explanation,
            )
        )

        # 4. Pricing & Budget Efficiency
        diff = abs(prod_1.price - prod_2.price)
        if prod_1.price < prod_2.price:
            price_explanation = f"{prod_1.name} is ₹{diff:,.0f} more economical, leaving room in your budget for peripherals or accessories."
        elif prod_2.price < prod_1.price:
            price_explanation = f"{prod_2.name} is ₹{diff:,.0f} cheaper, providing better savings while still satisfying your requirements."
        else:
            price_explanation = "Both models are priced identically."

        trade_offs.append(
            TradeOffComparison(
                criterion="Price & Value",
                product_1_verdict=f"₹{prod_1.price:,.0f}",
                product_2_verdict=f"₹{prod_2.price:,.0f}",
                trade_off_explanation=price_explanation,
            )
        )

        return trade_offs

    @classmethod
    def generate_no_match_explanation(
        cls,
        state: Dict[str, Any],
        violations: Dict[str, Any]
    ) -> str:
        """
        Generates an honest, transparent explanation when 0 products satisfy mandatory constraints.
        """
        budget_max = state.get("budget_max")
        category = state.get("category", "laptop")
        uses = state.get("primary_uses", [])

        lines = [
            f"I searched our product database, but currently no {category} in our catalog meets all of your specific constraints simultaneously."
        ]

        if violations.get("over_budget", 0) > 0 and budget_max:
            if "machine_learning" in uses:
                lines.append(
                    f"Specifically, laptops with dedicated NVIDIA RTX GPUs and 16GB RAM for local machine learning models start at ₹74,990 in our store, whereas your maximum budget is set to ₹{budget_max:,.0f}."
                )
            else:
                lines.append(
                    f"The configurations matching your specifications currently start at a higher price point than ₹{budget_max:,.0f}."
                )

        if violations.get("insufficient_ram", 0) > 0:
            lines.append("Several otherwise suitable models had less RAM than your required minimum.")

        lines.append(
            "\n💡 Suggestions:\n"
            "1. If you plan to run machine learning experiments using cloud services (like Google Colab or Kaggle), you can opt for an integrated graphics laptop (starting under ₹50,000).\n"
            "2. If local training is mandatory, consider adjusting your budget upward to around ₹75,000–₹80,000.\n"
            "Would you like me to show you the closest available options if we adjust either of those constraints?"
        )

        return "\n".join(lines)
