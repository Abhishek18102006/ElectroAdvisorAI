# ElectroAdvisor AI — Live Interview & Demo Guide (Day 3 Prep)

This document is prepared to guide the candidate through the **Google Meet live interview and technical defense** (Assessment Section 9).

---

## 🎯 1. Executive Summary & Elevator Pitch (1–2 minutes)

> "Hi everyone. For this assessment, I built **ElectroAdvisor**, an AI sales assistant for electronics.
> Rather than building a naive LLM wrapper that hallucinates specs or a rigid sequential chatbot questionnaire, I built an **orchestrated stateful recommendation agent** backed by the **FARM stack (FastAPI, React, SQLite)**.
>
> The core design principle is **separation of concerns**:
> 1. The **NLP layer** (LLM or regex engine) extracts structured requirements from natural conversation.
> 2. The **State Manager** tracks conversational memory, distinguishing hard constraints from soft preferences, and updates them when the customer changes their mind.
> 3. The **Decision Orchestrator** decides if enough information exists to recommend products. If not, it asks a single focused follow-up; if yes, it avoids redundant questioning.
> 4. The **Application Logic** enforces hard constraints (e.g., strict budget ceilings and GPU needs) in deterministic Python code. The LLM is never allowed to execute arbitrary SQL or override budget rules.
> 5. The **Ranking Engine** scores eligible products on use-case fit, campus portability, and battery endurance, recommending the top 2 products with explicit trade-offs grounded in real database records."

---

## 🖥 2. Live Demo Script (Step-by-Step)

### Demo Part 1: The Assessment Benchmark (Multi-Turn)
Open `http://127.0.0.1:5173` in your browser. Point to the **Active Requirements Inspector** on the right side.

1. **Turn 1:**
   - **User Input:** *"I need a laptop for college."*
   - **Observe:** State inspector locks `Category: Laptop`. Notice that `primary_use` is missing.
   - **Agent Response:** *"What will you mainly use it for: general coursework, programming, gaming, creative work, or machine learning?"* (Asks a focused question, does not ask for budget yet).

2. **Turn 2:**
   - **User Input:** *"Programming and machine learning. My budget is limited."*
   - **Observe:** State inspector adds `primary_uses: ["programming", "machine_learning"]`. Budget is noted as limited but numeric amount is missing.
   - **Agent Response:** *"What is your approximate budget? And do you need to run models locally, or will you mostly use cloud platforms?"*

3. **Turn 3:**
   - **User Input:** *"Around ₹80,000. Mostly local experiments, and I carry it around campus."*
   - **Observe:** State inspector updates `Max Budget: ₹80,000`, `Local ML: True`, `Requires GPU: True (CUDA)`, `RAM >= 16GB`, `Campus Portability: True`.
   - **Agent Response:** Delivers the **Top 2 models** strictly under ₹80,000 with 16GB RAM and RTX GPUs:
     - **Option 1:** *Acer Nitro V 15* (₹76,990) with RTX 4050 6GB.
     - **Option 2:** *ASUS TUF Gaming A15* (₹79,990) with RTX 4050 6GB and 90Wh battery.
   - **Trade-Off Matrix:** Displays side-by-side comparison across Graphics Compute, Portability, Battery Endurance, and Price.
   - **Crucial point to highlight to interviewers:** The agent did **not** ask an unnecessary 4th question because requirements were clear!

---

### Demo Part 2: Edge Cases & Mind-Changing Mid-Conversation
1. **Customer Changing Their Mind (Lowering Budget):**
   - **User Input:** *"Actually, my budget changed to ₹60,000."*
   - **Observe:** State inspector immediately updates `Max Budget: ₹60,000`.
   - **Agent Response:** Because `local_ml: True` (demanding a dedicated GPU) remains in memory, and dedicated GPU laptops in our catalog start at ₹74,990, the agent outputs an **honest no-match explanation** with dynamic recommendations:
     > *"Specifically, laptops with your required hardware specifications start at ₹74,990 (Dell G15 5530), whereas your maximum budget is set to ₹60,000.*  
     > *1. If you run models via cloud platforms (Google Colab, Kaggle, AWS), you can choose a non-GPU laptop like ASUS Vivobook 15 at ₹48,990.*  
     > *2. If local CUDA training is mandatory, consider adjusting your budget to around ₹75,000.*"
   - **Follow-up Interaction (Cloud Relaxation):**
     - User replies: *"I will use cloud platforms instead."*
     - The agent relaxes the dedicated GPU hard requirement, keeps 16GB RAM for programming, and recommends the **ASUS Vivobook 15** (₹48,990) within the ₹60,000 budget!
2. **Impossible / Contradictory Constraints:**
   - **User Input:** *"I need a gaming laptop with an RTX 4090 and 32GB RAM under ₹30,000."*
   - **Agent Response:** Immediate honest `no_match` response explaining that flagship RTX 4090 configurations cost significantly more, offering concrete suggestions rather than hallucinating nonexistent products.
3. **Database Catalog & Architecture Modals:**
   - Click the **"Catalog"** button in the header to demonstrate the **50 generalised seeded database records** with instant search and category filtering across laptops, smartphones, tablets, monitors, and headphones.
   - Click the **"Architecture"** button to show the embedded Mermaid and ASCII diagrams.

---

## 🛠 3. Technical Architecture Deep-Dive (Code Questions)

### Q: Why not let the LLM generate SQL queries directly?
> **Answer:** *"Allowing an LLM to generate raw SQL poses critical security risks (SQL injection) and reliability problems (syntax variations, hallucinated table names, or unbounded queries). In ElectroAdvisor, tool execution is strictly controlled via parameterized SQLAlchemy ORM queries in `app/agent/tools.py`. The LLM only extracts structured parameters (budget, category, minimum RAM), which are validated before querying."*

### Q: How are hard constraints distinguished from soft preferences?
> **Answer:** *"We use a two-stage pipeline in `app/agent/filter_rank.py`:*
> - *Stage 1 (Hard Filtering): Products that violate mandatory constraints (e.g. `price > budget_max`, missing dedicated GPU for local ML) are disqualified in Python code.*
> - *Stage 2 (Soft Preference Ranking): The remaining eligible candidates are scored using a normalized multi-factor utility function (0–100 points) balancing use-case fit, campus portability, battery life, and budget efficiency.*
> *This guarantees that no product violating a hard constraint can ever be recommended regardless of its soft score."*

### Q: How do you handle LLM timeouts vs. API key tireout/exhaustion?
> **Answer:** *"As recommended by mentor review, we focus strictly on LLM timeout guarantees rather than over-engineering key rotation/tireout. We enforce a configurable `LLM_TIMEOUT_SECONDS=5.0` via `asyncio.wait_for`. If Gemini or OpenAI stalls or exceeds 5s, the coroutine is cancelled immediately, logged, and seamlessly falls back to deterministic rule extraction without degrading user experience or blocking the response."*

### Q: How does the system handle multi-turn state persistence?
> **Answer:** *"In `app/agent/state.py`, the `StateManager` maintains an immutable snapshot of conversation requirements. When a user speaks, the entity patch is merged onto the existing state. If a field is updated (like a new budget), it overwrites the old value; but previous context (like use cases or portability) is preserved."*

### Q: Does the application work if an external LLM API is unavailable?
> **Answer:** *"Yes. While it integrates with Google Gemini and OpenAI if API keys are provided in `.env`, it includes a built-in deterministic regex/rule-based NLP parser in `app/agent/extractor.py`. This ensures that automated tests (`pytest`), local evaluation, and offline demos function with 100% reliability."*

---

## ⚡ 4. Live Coding / Debugging Practice (Interview Scenarios)

If the interviewer asks you to make a small change live during the meeting, here is where to go:

1. **"Add a new product to the catalog"**:
   - Go to `backend/app/data/seed_data.py`, add a dictionary entry to `PRODUCTS_CATALOG`.
   - Run `python -m app.data.init_db` to re-seed.
2. **"Change the maximum weight threshold for portability"**:
   - Go to `backend/app/agent/filter_rank.py` in `calculate_score` and adjust the `weight_kg` thresholds.
3. **"Add an extra filter parameter to the products API"**:
   - Go to `backend/app/api/products.py`, add a query parameter to `list_products`, and bind it with `query.filter(...)`.
4. **"Run the test suite"**:
   - Run `cd backend && .\.venv\Scripts\python.exe -m pytest` in PowerShell. All 40 tests pass in ~2.1s.
5. **"Verify Headless Browser & Playwright E2E"**:
   - Run `cd frontend && npm run test:e2e`. Playwright launches headless Chromium, verifies external connectivity and local bundle rendering with 100% success.
