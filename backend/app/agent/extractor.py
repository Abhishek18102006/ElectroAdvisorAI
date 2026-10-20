import re
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError
from app.config import settings

logger = logging.getLogger(__name__)


class ExtractedEntities(BaseModel):
    category: Optional[str] = None
    budget_max: Optional[float] = None
    budget_min: Optional[float] = None
    primary_uses: List[str] = Field(default_factory=list)
    hard_constraints: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    local_ml: Optional[bool] = None
    last_intent: str = "information_provided"


def parse_numeric_budget(text: str) -> Optional[float]:
    """
    Parses natural language budget expressions into a float.
    Handles '80,000', '1,20,000', '80k', '₹80000', '1 lakh', '1.5L', 'around 80k', 'under 75000', etc.
    """
    lower = text.lower()

    # Pattern for Lakhs: e.g. 1.2 lakh, 1 lakh, 2 lakhs, 1.5l, 1.2 lac
    lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs|l)\b", lower)
    if lakh_match:
        try:
            return float(lakh_match.group(1)) * 100000.0
        except ValueError:
            pass

    # Pattern for 'k' / thousands: e.g. 80k, 80 k, 120k, 75k
    k_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*k\b", lower)
    if k_match:
        try:
            return float(k_match.group(1)) * 1000.0
        except ValueError:
            pass

    # Indian and Western comma-grouped numbers: e.g. 1,20,000 (Indian) or 80,000 or 80000
    # Group pattern: 1-3 digits followed by groups of 2 or 3 digits
    num_matches = re.findall(r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:,\d{2,3})+|\d{4,7})\b", lower)
    if num_matches:
        for m in reversed(num_matches):
            cleaned = m.replace(",", "").replace(" ", "").strip()
            try:
                val = float(cleaned)
                if val >= 5000:  # Avoid matching RAM or year numbers
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
        """High-precision deterministic rule-based extractor using strict word boundaries."""
        lower = text.lower().strip()
        extracted: Dict[str, Any] = {
            "category": None,
            "budget_max": None,
            "budget_min": None,
            "primary_uses": [],
            "hard_constraints": {},
            "preferences": {},
            "local_ml": None,
            "last_intent": "information_provided",
            "contradiction": None,
        }

        # 1. Category extraction - Check specific compound words first, use word boundaries
        if re.search(r"\b(headphones?|earphones?|airpods?|audio|earbuds?)\b", lower):
            extracted["category"] = "headphones"
        elif re.search(r"\b(laptops?|notebooks?|macbooks?|pc|computers?)\b", lower):
            extracted["category"] = "laptop"
        elif re.search(r"\b(smartphones?|phones?|iphones?|android|mobiles?)\b", lower):
            extracted["category"] = "smartphone"
        elif re.search(r"\b(tablets?|ipads?)\b", lower):
            extracted["category"] = "tablet"
        elif re.search(r"\b(monitors?|displays?|screens?)\b", lower):
            extracted["category"] = "monitor"

        # 2. Budget extraction
        budget_val = parse_numeric_budget(text)
        if budget_val:
            extracted["budget_max"] = budget_val
            extracted["hard_constraints"]["max_budget"] = budget_val

        # Detect range: "between 50k and 80k" or "50000 to 80000"
        range_match = re.search(r"(?:between|from)\s+(\d+k?|\d{4,7})\s+(?:and|to)\s+(\d+k?|\d{4,7})", lower)
        if range_match:
            b1 = parse_numeric_budget(range_match.group(1))
            b2 = parse_numeric_budget(range_match.group(2))
            if b1 and b2:
                if b1 > b2:
                    extracted["contradiction"] = f"Minimum budget (₹{b1:,.0f}) cannot be greater than maximum budget (₹{b2:,.0f})."
                extracted["budget_min"] = min(b1, b2)
                extracted["budget_max"] = max(b1, b2)

        # 3. Primary Uses with strict word boundaries
        uses = set()
        if re.search(r"\b(machine\s*learning|ml|deep\s*learning|neural|pytorch|tensorflow|cuda|ai\s*models?)\b", lower):
            uses.add("machine_learning")
        if re.search(r"\b(programming|coding|software|developer|dev|web\s*dev|python|java|c\+\+|frontend|backend|fullstack)\b", lower):
            uses.add("programming")
        if re.search(r"\b(gaming|games|gamer|fps|esports|fortnite|gta|steam)\b", lower):
            uses.add("gaming")
        if re.search(r"\b(general\s*coursework|coursework|documents|assignments|office\s*work|basic\s*use|reading)\b", lower):
            uses.add("general_coursework")
        if re.search(r"\b(video\s*editing|photo\s*editing|premiere|photoshop|creative|rendering|blender|design|animation)\b", lower):
            uses.add("creative_work")
        if re.search(r"\b(study|study\s*focus|focus|noise\s*cancell?ation|anc|calls|music|travel)\b", lower):
            uses.add("study_focus")
        if re.search(r"\b(note\s*taking|notes|digital\s*notes|drawing|stylus|pen)\b", lower):
            uses.add("digital_notes")
        if re.search(r"\b(photography|camera|photos)\b", lower):
            uses.add("photography")

        extracted["primary_uses"] = list(uses)

        # 4. Local vs Cloud ML & GPU environment
        if re.search(r"\b(local|locally|local\s*experiments?|local\s*models?|local\s*training|offline)\b", lower):
            extracted["local_ml"] = True
            extracted["preferences"]["ml_environment"] = "local"
            extracted["hard_constraints"]["requires_gpu"] = True
            extracted["hard_constraints"]["min_ram_gb"] = 16
        elif re.search(r"\b(cloud|colab|google\s*colab|kaggle|aws|cloud\s*platforms?)\b", lower):
            extracted["local_ml"] = False
            extracted["preferences"]["ml_environment"] = "cloud"
            extracted["hard_constraints"]["requires_gpu"] = False

        if re.search(r"\b(dedicated\s*gpu|nvidia|rtx|geforce)\b", lower):
            extracted["hard_constraints"]["requires_gpu"] = True
            extracted["local_ml"] = True
            extracted["preferences"]["ml_environment"] = "local"

        # 5. Portability & Campus mobility
        if re.search(r"\b(carry\s*(?:it\s*)?around\s*campus|carry\s*around|lightweight|portable|light\s*weight|commute|backpack)\b", lower):
            extracted["preferences"]["portability"] = True
            extracted["preferences"]["max_weight_kg"] = 1.8

        # 6. Battery
        if re.search(r"\b(battery|battery\s*life|all\s*day|long\s*lasting)\b", lower):
            extracted["preferences"]["battery_priority"] = True

        # 7. Hardware specifications explicitly mentioned
        if re.search(r"\b16\s*gb\b", lower):
            extracted["hard_constraints"]["min_ram_gb"] = 16
        elif re.search(r"\b32\s*gb\b", lower):
            extracted["hard_constraints"]["min_ram_gb"] = 32
        elif re.search(r"\b8\s*gb\b", lower):
            extracted["hard_constraints"]["min_ram_gb"] = 8

        # 8. Brand / OS preferences
        if re.search(r"\b(macbook|macos|apple)\b", lower):
            extracted["preferences"]["preferred_brands"] = ["Apple"]
            extracted["hard_constraints"]["required_os"] = "macOS"
        elif re.search(r"\bwindows\b", lower):
            extracted["hard_constraints"]["required_os"] = "Windows"

        # Contradiction check: MacBook running Windows
        if re.search(r"\bmacbooks?\b", lower) and re.search(r"\bwindows\b", lower):
            extracted["contradiction"] = "Apple MacBooks run macOS and do not support native Windows installations on modern Apple Silicon."

        # Check for change of mind or update intent
        if re.search(r"\b(actually|instead|change\s*my\s*budget|changed\s*my\s*mind|let'?s\s*make\s*it|what\s*if)\b", lower):
            extracted["last_intent"] = "requirement_change"
        elif re.search(r"\b(thanks?|thank\s*you|awesome|great|perfect|cool)\b", lower):
            extracted["last_intent"] = "appreciation"
        elif re.search(r"\b(lighter|lightest|cheaper|lowest\s*price|more\s*battery)\b", lower):
            extracted["last_intent"] = "refinement"

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
        Attempts LLM extraction if an API key is available and validates with Pydantic;
        falls back gracefully to deterministic rule-based parsing on timeout or parse failure.
        """
        rule_extracted = cls.extract_with_rules(customer_message, current_state)

        # Check provider configuration
        has_gemini = bool(settings.GEMINI_API_KEY) and settings.LLM_PROVIDER in ["auto", "gemini"]
        has_openai = bool(settings.OPENAI_API_KEY) and settings.LLM_PROVIDER in ["auto", "openai"]

        if has_gemini:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model_name = settings.GEMINI_MODEL or "gemini-1.5-flash"
                model = genai.GenerativeModel(model_name)

                prompt = (
                    "You are a structured entity extractor for an electronics store assistant.\n"
                    f"Current State: {json.dumps(current_state)}\n"
                    f'Customer Message: "{customer_message}"\n\n'
                    "Extract customer requirements as a JSON object matching this schema:\n"
                    "{\n"
                    '  "category": "laptop" | "smartphone" | "tablet" | "monitor" | "headphones" | null,\n'
                    '  "budget_max": number | null,\n'
                    '  "budget_min": number | null,\n'
                    '  "primary_uses": ["programming" | "machine_learning" | "gaming" | "general_coursework" | "creative_work" | "study_focus"],\n'
                    '  "hard_constraints": { "max_budget": number | null, "min_ram_gb": number | null, "requires_gpu": boolean | null, "required_os": string | null },\n'
                    '  "preferences": { "portability": boolean | null, "battery_priority": boolean | null, "ml_environment": "local" | "cloud" | null },\n'
                    '  "local_ml": boolean | null,\n'
                    '  "last_intent": "information_provided" | "requirement_change" | "greeting" | "appreciation" | "refinement"\n'
                    "}\n"
                    "Output valid JSON ONLY without markdown."
                )

                # Enforce strict 7-second timeout
                response = await asyncio.wait_for(model.generate_content_async(prompt), timeout=7.0)
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]

                llm_dict = json.loads(raw_text.strip())

                # Validate LLM output with Pydantic
                validated = ExtractedEntities(**llm_dict)
                validated_dict = validated.model_dump(exclude_none=True)

                # Merge validated LLM attributes over rule defaults
                return {**rule_extracted, **validated_dict}
            except asyncio.TimeoutError:
                logger.warning("Gemini LLM extraction timed out after 7s; falling back to rules.")
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"Malformed LLM output or validation error ({e}); falling back to rules.")
            except Exception as e:
                logger.warning(f"Gemini API error ({e}); falling back to rules.")

        elif has_openai:
            try:
                import httpx
                headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
                payload = {
                    "model": settings.OPENAI_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a structured entity extractor for an electronics sales assistant. Output JSON only matching:\n"
                                "{\n"
                                '  "category": "laptop" | "smartphone" | "tablet" | "monitor" | "headphones" | null,\n'
                                '  "budget_max": number | null,\n'
                                '  "budget_min": number | null,\n'
                                '  "primary_uses": ["programming" | "machine_learning" | "gaming" | "general_coursework" | "creative_work" | "study_focus"],\n'
                                '  "hard_constraints": { "max_budget": number | null, "min_ram_gb": number | null, "requires_gpu": boolean | null, "required_os": string | null },\n'
                                '  "preferences": { "portability": boolean | null, "battery_priority": boolean | null, "ml_environment": "local" | "cloud" | null },\n'
                                '  "local_ml": boolean | null,\n'
                                '  "last_intent": "information_provided" | "requirement_change" | "greeting" | "appreciation" | "refinement"\n'
                                "}"
                            ),
                        },
                        {"role": "user", "content": f"Current State: {json.dumps(current_state)}\nMessage: {customer_message}"},
                    ],
                    "response_format": {"type": "json_object"},
                }
                async with httpx.AsyncClient(timeout=7.0) as client:
                    resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        llm_dict = json.loads(resp.json()["choices"][0]["message"]["content"])
                        validated = ExtractedEntities(**llm_dict)
                        return {**rule_extracted, **validated.model_dump(exclude_none=True)}
            except Exception as e:
                logger.warning(f"OpenAI extraction error ({e}); falling back to rules.")

        # Default: Return rule-based extraction
        return rule_extracted
