"""Streamlit chat UI (nice for the demo video).

    streamlit run src/crm_agent/interfaces/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # allow `streamlit run` without install

import streamlit as st  # noqa: E402

from crm_agent.agent.orchestrator import CRMAgent  # noqa: E402
from crm_agent.agent.responder import message_block  # noqa: E402

st.set_page_config(page_title="RM Co-pilot · Agentic CRM", page_icon="🏦", layout="wide")

EXAMPLES = [
    "Find high-value customers likely to convert for a personal loan this month and generate personalized WhatsApp messages.",
    "Only show the ones in Delhi",
    "Rewrite the messages in Hindi",
    "Which customers should get a credit card upgrade? Top 5",
    "Tell me about C0042",
    "Find FD prospects among retirees",
]

if "agent" not in st.session_state:
    st.session_state.agent = CRMAgent()
    st.session_state.history = []  # (role, AgentResponse | str)
agent: CRMAgent = st.session_state.agent

with st.sidebar:
    st.header("🏦 RM Co-pilot")
    st.caption(f"LLM: `{agent.llm.name}` · data as of {agent.ctx.repo.as_of_date} · session `{agent.state.session_id}`")
    st.subheader("Try")
    for ex in EXAMPLES:
        if st.button(ex, width="stretch"):
            st.session_state.pending = ex
    st.subheader("🧠 Memory")
    st.json(agent.state.context_summary(), expanded=False)
    if agent.state.funnel:
        st.write("Funnel", agent.state.funnel)
    if st.button("Reset conversation"):
        agent.reset()
        st.session_state.history = []
        st.rerun()
    with st.expander("🧰 Tools"):
        for s in agent.registry.schemas():
            st.markdown(f"**{s['name']}** – {s['description']}")


def show(resp) -> None:
    if resp.trace:
        with st.expander(f"🧭 Reasoning trace · {len(resp.trace)} steps · goal: {resp.plan.goal if resp.plan else ''}"):
            st.dataframe([{"step": e.step_id, "tool": e.tool, "status": e.status, "why": e.description,
                           "result": e.summary, "ms": e.duration_ms} for e in resp.trace], width="stretch", hide_index=True)
    st.markdown(resp.text)
    for m in resp.messages:
        with st.expander(f"✉️ {m.customer_name} · {m.channel} · {m.language} · {'✅' if m.compliance_passed and m.deliverable else '⚠️'}"):
            st.markdown(message_block(m))
    from crm_agent.config import PROJECT_ROOT

    for path in resp.artifacts:
        full = Path(path) if Path(path).is_absolute() else PROJECT_ROOT / path
        if path.endswith(".csv") and full.exists():
            st.download_button("⬇️ Download campaign CSV", full.read_bytes(), file_name=full.name, key=path)


for role, item in st.session_state.history:
    with st.chat_message(role):
        show(item) if role == "assistant" else st.markdown(item)

query = st.chat_input("Ask about customers, products or outreach…") or st.session_state.pop("pending", None)
if query:
    st.session_state.history.append(("user", query))
    with st.chat_message("user"):
        st.markdown(query)
    with st.chat_message("assistant"):
        with st.spinner("Planning & running tools…"):
            resp = agent.chat(query)
        show(resp)
    st.session_state.history.append(("assistant", resp))
