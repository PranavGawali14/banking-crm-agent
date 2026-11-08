# 🎬 Demo video script (≈ 8 minutes)

**Setup before recording:** `pip install -r requirements.txt`, delete `data/crm.db` for a fresh start, then open two windows:
1. **Streamlit UI**: `streamlit run src/crm_agent/interfaces/streamlit_app.py` (main demo)
2. **Terminal**: `PYTHONPATH=src python -m crm_agent.interfaces.cli --trace` (shows the live reasoning trace)

Optional: put an `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env` and show the sidebar change from `offline-rules` to the LLM name. Showing both modes makes the graceful-degradation point well.

---

### 0:00 – 0:45 · Intro
- Problem: an RM has hundreds of customers and needs to know *who* to call this month, *what* to offer and *what* to say, without breaking compliance.
- What I built: a conversational agent that plans, calls 11 typed tools, reasons over transaction data with an explainable ML model, and writes compliance-checked messages in the customer's language.
- Mention: it runs fully offline (no API key needed); an LLM is optional.

### 0:45 – 2:00 · Architecture (show the README diagram)
- Interfaces → **CRMAgent orchestrator** (understand → plan → execute → reflect → respond → remember) → **tool registry** → domain logic → repository/SQLite.
- Key point: **the LLM understands and writes; deterministic code decides and plans.** Credit policy is rules, ranking is an explainable model, every step is traced.
- Data: synthetic bank with 300 customers, about 40k transactions, and 3,000 historical campaign outcomes. Life events are planted in transactions; the agent has to discover them.

### 2:00 – 4:00 · Use case 1: the assignment prompt
1. Type: **"Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages."**
2. Open the **reasoning trace**: 9 steps, each with *why* and *result*. Walk the funnel: 300 → 119 high-value → 65 eligible (show rejection reasons) → top 10 by propensity (AUC ≈ 0.9).
3. Point at the "Why now" column (life-event spending, balance dip, loan-page visits) and the offer column (amount sized by income and DTI, rate by credit score).
4. Open two messages:
   - one in **Hindi** (customer's preferred language), formal vs casual greeting by segment;
   - one **re-routed to email** because the customer never opted into WhatsApp. That is the compliance tool at work.
   - Note that no message mentions actual transactions. The model only gets a sanitised brief ("may be planning a big purchase").
5. Follow-ups (memory):
   - **"Only show the ones in Delhi or Mumbai"**: refine merges the filter, plan re-runs.
   - **"Rewrite the messages in Hindi"**: only steps 7–9 run, on the remembered shortlist.
   - **"Why was Kunal Reddy selected?"**: feature contributions, value components, policy check.

### 4:00 – 5:15 · Use case 2: a different product and channel
1. **"Which salaried customers should get a credit card upgrade? Top 5"**: same agent, different product. The trace shows `heuristic:credit_card_premium` (no campaign history, a cold-start prior). Hooks change to dining, travel or shopping rewards.
2. **"Send them as email instead"**: email subjects plus longer format; customers without email consent are re-routed.
3. **"Export this campaign"**: download the CSV (CRM-ready: rank, scores, reasons, offer, message, deliverability).

### 5:15 – 6:30 · Use case 3: customer 360 and self-correction
1. **"Tell me about C0042"**: profile, consented channels, recent behaviour, best-fit product across the catalogue.
2. **"Find fixed deposit prospects among retirees in Chennai and draft SMS messages"**: the high-value filter empties the funnel, so the trace shows **reflection**: *"relaxed cut-off 55 → 40 → 25 and re-ran the plan"*. Hard policy rules are never relaxed. SMS respects DND.
3. *(Optional)* **"What products do we have?"**: the catalogue shows which model backs each product.

### 6:30 – 7:45 · Trade-offs (talk over the README table)
- Deterministic recipes vs. a free ReAct loop: auditability and reproducibility over open-endedness. Tool JSON schemas are ready if we want LLM tool-calling for exploratory questions.
- Logistic regression vs. boosting: explainability for model-risk governance.
- Templates vs. LLM copy: safety, cost and latency vs. fluency. The compliance critic makes LLM output safe (show `tests/test_llm_integration.py`: an unsafe "guaranteed approval" draft is auto-regenerated).
- Limitations: synthetic data, heuristic priors for cold-start products, no real sending (WhatsApp template approval / DLT), single-user state.

### 7:45 – 8:15 · Wrap-up
- `python -m pytest`: 32 tests including "results change when data changes" (no hard-coding) and the LLM-outage fallback.
- Extending: add a product in JSON, or a tool in one class; swap the repository for a real CRM.
