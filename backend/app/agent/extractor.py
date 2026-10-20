import re
import json
import logging
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)


def parse_numeric_budget(text: str) -> Optional[float]:
    """
    Parses natural language budget expressions into a float.
    Handles '80,000', '80k', '₹80000', '1 lakh', '1.5L', 'around 80k', 'under 75000', etc.
    """
    lower = text.lower()

    # Pattern for Lakhs: e.g. 1.2 lakh, 1 lakh, 2 lakhs, 1.5l
    lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b", lower)
    if lakh_match:
        try:
            return float(lakh_match.group(1)) * 100000.0
        except ValueError:
            pass

    # Pattern for 'k' / thousands: e.g. 80k, 80 k, 75k
    k_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*k\b", lower)
    if k_match:
        try:
            return float(k_match.group(1)) * 1000.0
        except ValueError:
            pass

    # Standard numbers: e.g. 80,000 or 80000 or ₹80,000
    # Match numbers typically >= 1000 to avoid matching RAM sizes (e.g., 16 or 32)
    num_matches = re.findall(r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{3})+|\d{4,7})\b", lower)
    if num_matches:
        for m in reversed(num_matches):
            cleaned = m.replace(",", "").replace(" ", "").strip()
            try:
                val = float(cleaned)
                if val >= 5000:  # Reasonable price threshold
                    return val
            except ValueError:
                continue

    return None


class RequirementsExtractor:
    """
    Extracts structured customer requirements, constraints, and preferences
    from messages using an LLM if available, falling back gracefully to a robust
    rule-based / regex parser.
    """

    @classmethod
    def extract_with_rules(cls, text: str, previous_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """High-precision deterministic rule-based extractor."""
        lower = text.lower()
        extracted: Dict[str, Any] = {
            "category": None,
            "budget_max": None,
            "budget_min": None,
            "primary_uses": [],
            "hard_constraints": {},
            "preferences": {},
            "local_ml": None,
            "last_intent": "information_provided",
        }

        # 1. Category extraction
        if any(w in lower for w in ["laptop", "notebook", "macbook", "computer", "pc"]):
            extracted["category"] = "laptop"
        elif any(w in lower for w in ["phone", "smartphone", "mobile", "iphone", "android"]):
            extracted["category"] = "smartphone"
        elif any(w in lower for w in ["tablet", "ipad", "tab"]):
            extracted["category"] = "tablet"
        elif any(w in lower for w in ["monitor", "display", "screen"]):
            extracted["category"] = "monitor"
        elif any(w in lower for w in ["headphone", "earphone", "audio", "airpods"]):
            extracted["category"] = "headphones"

        # 2. Budget extraction
        budget_val = parse_numeric_budget(text)
        if budget_val:
            extracted["budget_max"] = budget_val
            extracted["hard_constraints"]["max_budget"] = budget_val

        # Detect range: "between 50k and 80k"
        range_match = re.search(r"between\s+(\d+k?)\s+and\s+(\d+k?)", lower)
        if range_match:
            b1 = parse_numeric_budget(range_match.group(1))
            b2 = parse_numeric_budget(range_match.group(2))
            if b1 and b2:
                extracted["budget_min"] = min(b1, b2)
                extracted["budget_max"] = max(b1, b2)

        # 3. Primary Uses
        # Note: 'college' alone is context/persona, not an explicit use case
        uses = set()
        if any(w in lower for w in ["machine learning", "ml", "deep learning", "neural", "pytorch", "tensorflow", "cuda", "ai model"]):
            uses.add("machine_learning")
        if any(w in lower for w in ["programming", "coding", "software", "developer", "web dev", "python", "java", "c++", "frontend", "backend"]):
            uses.add("programming")
        if any(w in lower for w in ["gaming", "games", "gamer", "fps", "esports", "fortnite", "gta"]):
            uses.add("gaming")
        if any(w in lower for w in ["general coursework", "coursework", "documents", "assignments", "office work", "basic use", "reading"]):
            uses.add("general_coursework")
        if any(w in lower for w in ["video editing", "photo editing", "premiere", "photoshop", "creative", "rendering", "blender", "design", "animation"]):
            uses.add("creative_work")

        extracted["primary_uses"] = list(uses)

        # 4. Local vs Cloud ML & GPU
        if any(w in lower for w in ["local", "locally", "local experiments", "local models", "local training", "offline"]):
            extracted["local_ml"] = True
            extracted["preferences"]["ml_environment"] = "local"
            extracted["hard_constraints"]["requires_gpu"] = True
            extracted["hard_constraints"]["min_ram_gb"] = 16
        elif any(w in lower for w in ["cloud", "colab", "google colab", "kaggle", "aws", "cloud platforms"]):
            extracted["local_ml"] = False
            extracted["preferences"]["ml_environment"] = "cloud"

        if any(w in lower for w in ["dedicated gpu", "nvidia", "rtx", "geforce"]):
            extracted["hard_constraints"]["requires_gpu"] = True
            extracted["local_ml"] = True
            extracted["preferences"]["ml_environment"] = "local"

        # 5. Portability & Campus mobility
        if any(w in lower for w in ["carry it around campus", "carry around campus", "carry around", "lightweight", "portable", "light weight", "commute", "travel", "backpack"]):
            extracted["preferences"]["portability"] = True
            extracted["preferences"]["max_weight_kg"] = 1.8

        # 6. Battery
        if any(w in lower for w in ["battery", "battery life", "all day", "long lasting"]):
            extracted["preferences"]["battery_priority"] = True

        # 7. Hardware specifications explicitly mentioned
        if re.search(r"\b16\s*gb\b", lower):
            extracted["hard_constraints"]["min_ram_gb"] = 16
        elif re.search(r"\b32\s*gb\b", lower):
            extracted["hard_constraints"]["min_ram_gb"] = 32
        elif re.search(r"\b8\s*gb\b", lower):
            extracted["hard_constraints"]["min_ram_gb"] = 8

        # Brand / OS preferences
        if any(w in lower for w in ["macbook", "macos", "apple"]):
            extracted["preferences"]["preferred_brands"] = ["Apple"]
            extracted["hard_constraints"]["required_os"] = "macOS"
        elif any(w in lower for w in ["windows"]):
            extracted["hard_constraints"]["required_os"] = "Windows"

        # Check for change of mind or update intent
        if any(w in lower for w in ["actually", "instead", "change my budget", "changed my mind", "let's make it", "what if"]):
            extracted["last_intent"] = "requirement_change"

        return extracted

    @classmethod
    async def extract_requirements(
        cls,
        customer_message: str,
        conversation_history: List[Dict[str, Any]],
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Main extraction entry point.
        Attempts LLM extraction if an API key is available, else uses rule-based parsing.
        """
        rule_extracted = cls.extract_with_rules(customer_message, current_state)

        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel("gemini-1.5-flash")
                
                prompt = f"""
                You are a structured entity extractor for an electronics store assistant.
                Current State: {json.dumps(current_state)}
                Customer Message: "{customer_message}"

                Extract any changes or requirements as a valid JSON object matching this schema:
                {{
                    "category": "laptop" | "smartphone" | "tablet" | "monitor" | "headphones" | null,
                    "budget_max": number | null,
                    "budget_min": number | null,
                    "primary_uses": ["programming" | "machine_learning" | "gaming" | "general_coursework" | "creative_work"],
                    "hard_constraints": {{
                        "max_budget": number | null,
                        "min_ram_gb": number | null,
                        "requires_gpu": boolean | null,
                        "required_os": string | null
                    }},
                    "preferences": {{
                        "portability": boolean | null,
                        "battery_priority": boolean | null,
                        "ml_environment": "local" | "cloud" | null
                    }},
                    "local_ml": boolean | null,
                    "last_intent": string
                }}
                Respond ONLY with the JSON object.
                """
                response = await model.generate_content_async(prompt)
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                llm_data = json.loads(raw_text.strip())
                return {**rule_extracted, **{k: v for k, v in llm_data.items() if v is not None}}
            except Exception as e:
                logger.warning(f"LLM extraction encountered an error; falling back to rules: {e}")

        elif settings.OPENAI_API_KEY:
            try:
                import httpx
                headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
                payload = {
                    "model": settings.OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a structured entity extractor for an electronics sales assistant. Output JSON only."},
                        {"role": "user", "content": f"Current State: {json.dumps(current_state)}\nMessage: {customer_message}"}
                    ],
                    "response_format": {"type": "json_object"}
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        llm_data = json.loads(resp.json()["choices"][0]["message"]["content"])
                        return {**rule_extracted, **{k: v for k, v in llm_data.items() if v is not None}}
            except Exception as e:
                logger.warning(f"OpenAI extraction encountered an error; falling back to rules: {e}")

        return rule_extracted
