import html
import json
import time

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from graph_agent import build_app
from mock_db import init

st.set_page_config(page_title="Support Agent", page_icon="🎧", layout="wide")

CUSTOMERS = [1, 2, 3, 4, 5]
WRITE_TOOLS = {"cancel_order", "initiate_refund"}

# sidebar ke quick buttons ke liye
QUICK = [
    "Order 5 ka status batao",
    "Cancel order 5",
    "Refund Rs 500 for order 1",
    "Cancel order 3",
]

# ---------- styling ----------
st.markdown(
    """
<style>
#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 1.6rem; max-width: 1250px;}

/* top banner */
.hero {
    background: linear-gradient(120deg, #4F46E5 0%, #7C3AED 100%);
    color: white; padding: 22px 28px; border-radius: 16px;
    margin-bottom: 18px; box-shadow: 0 8px 24px rgba(79,70,229,.25);
}
.hero h1 {margin: 0; font-size: 1.7rem; font-weight: 700; color: white;}
.hero p {margin: 4px 0 0 0; opacity: .85; font-size: .95rem;}
.chip {
    display: inline-block; background: rgba(255,255,255,.18);
    padding: 3px 12px; border-radius: 999px; font-size: .8rem; margin-top: 10px;
}

/* metric cards */
div[data-testid="stMetric"] {
    background: white; border: 1px solid #E2E8F0; border-radius: 14px;
    padding: 12px 16px; box-shadow: 0 1px 3px rgba(15,23,42,.05);
}

/* chat bubbles */
div[data-testid="stChatMessage"] {
    background: white; border: 1px solid #E2E8F0; border-radius: 14px;
    padding: 12px 16px; box-shadow: 0 1px 3px rgba(15,23,42,.04);
}

/* approval card */
.approval {
    background: #FFFBEB; border: 1px solid #FCD34D; border-left: 5px solid #F59E0B;
    border-radius: 12px; padding: 14px 18px; margin: 10px 0;
}
.approval h4 {margin: 0 0 6px 0; color: #92400E; font-size: 1rem;}
.approval code {background: #FEF3C7; color: #78350F; padding: 2px 8px; border-radius: 6px;}

/* tool trace cards */
.tcard {
    background: white; border: 1px solid #E2E8F0; border-radius: 12px;
    padding: 10px 14px; margin-bottom: 10px;
}
.tname {font-weight: 600; font-size: .92rem; color: #0F172A;}
.badge {
    display: inline-block; font-size: .68rem; font-weight: 700; letter-spacing: .04em;
    padding: 2px 8px; border-radius: 999px; margin-left: 8px; text-transform: uppercase;
}
.b-read {background: #DBEAFE; color: #1E40AF;}
.b-write {background: #FEF3C7; color: #92400E;}
.b-ok {background: #DCFCE7; color: #166534;}
.b-err {background: #FEE2E2; color: #991B1B;}
.b-wait {background: #E0E7FF; color: #3730A3;}
.targs {
    font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .78rem;
    color: #475569; background: #F1F5F9; border-radius: 8px;
    padding: 6px 10px; margin-top: 6px; word-break: break-all;
}
.tres {font-size: .8rem; color: #334155; margin-top: 6px;}
.empty {color: #94A3B8; font-size: .9rem; padding: 8px 2px;}

/* buttons */
.stButton > button {border-radius: 10px; font-weight: 600;}
section[data-testid="stSidebar"] {border-right: 1px solid #E2E8F0;}
</style>
""",
    unsafe_allow_html=True,
)


def new_session(customer_id):
    # customer badla to naya graph aur naya thread_id
    st.session_state.customer = customer_id
    st.session_state.app = build_app(customer_id)
    st.session_state.config = {
        "configurable": {"thread_id": f"ui-{customer_id}-{time.time()}"}
    }


def trace_card(call, result):
    # ek tool call + uska result ek card mein
    name = call["name"]
    kind = "write" if name in WRITE_TOOLS else "read"
    args = html.escape(json.dumps(call["args"]))

    if result is None:
        status = '<span class="badge b-wait">waiting</span>'
        res_html = ""
    else:
        try:
            data = json.loads(result.content)
            ok = data.get("ok", True) if isinstance(data, dict) else True
            summary = data.get("error") or data.get("message") or "done" if isinstance(data, dict) else "done"
        except Exception:
            ok, summary = True, str(result.content)[:80]
        status = (
            '<span class="badge b-ok">ok</span>' if ok
            else '<span class="badge b-err">error</span>'
        )
        res_html = f'<div class="tres">{html.escape(str(summary))[:140]}</div>'

    return (
        f'<div class="tcard"><span class="tname">{html.escape(name)}</span>'
        f'<span class="badge b-{kind}">{kind}</span>{status}'
        f'<div class="targs">{args}</div>{res_html}</div>'
    )


# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### 🎧 Support Agent")
    st.caption("LangGraph + human approval")
    customer = st.selectbox("Customer", CUSTOMERS)

# pehli baar ya dropdown badla
if st.session_state.get("customer") != customer:
    new_session(customer)

app = st.session_state.app
config = st.session_state.config

# state hi source of truth
snapshot = app.get_state(config)
messages = snapshot.values.get("messages", []) if snapshot.values else []

pending = None
if snapshot.next:
    pending = snapshot.tasks[0].interrupts[0].value["pending"]

with st.sidebar:
    st.markdown("---")
    st.markdown("**Quick prompts**")
    for q in QUICK:
        if st.button(q, key=f"quick-{q}", use_container_width=True, disabled=pending is not None):
            st.session_state.queued = q
            st.rerun()

    st.markdown("---")
    if st.button("Reset DB + chat", use_container_width=True):
        init()  # db fresh
        new_session(customer)
        st.rerun()

# ---------- header + stats ----------
st.markdown(
    f"""
<div class="hero">
  <h1>Customer Support Agent</h1>
  <p>Order status, cancellations and refunds, with human approval before any change.</p>
  <span class="chip">Logged in as customer {customer}</span>
</div>
""",
    unsafe_allow_html=True,
)

tool_calls = [c for m in messages if isinstance(m, AIMessage) for c in (m.tool_calls or [])]
n_msgs = sum(1 for m in messages if isinstance(m, HumanMessage))

s1, s2, s3 = st.columns(3)
s1.metric("Customer", f"#{customer}")
s2.metric("Messages", n_msgs)
s3.metric("Tool calls", len(tool_calls))

st.write("")
col_chat, col_trace = st.columns([2, 1], gap="large")

# ---------- chat ----------
with col_chat:
    if not messages:
        st.info("Kuch poochho ya sidebar ka quick prompt dabao. Cancel aur refund se pehle approval aayega.")

    for m in messages:
        if isinstance(m, HumanMessage):
            st.chat_message("user", avatar="🙋").write(m.content)
        elif isinstance(m, AIMessage) and m.content:
            st.chat_message("assistant", avatar="🎧").write(m.content)

    if pending:
        items = "".join(
            f"<div><code>{html.escape(i['tool'])}({html.escape(json.dumps(i['args']))})</code></div>"
            for i in pending
        )
        st.markdown(
            f'<div class="approval"><h4>Approval required</h4>'
            f"<div>Ye action chalne se pehle aapki haan chahiye:</div>"
            f'<div style="margin-top:8px">{items}</div></div>',
            unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([1, 1, 2])
        answer = None
        if c1.button("✅ Approve", type="primary", use_container_width=True):
            answer = "yes"
        if c2.button("✖ Decline", use_container_width=True):
            answer = "no"

        if answer:
            try:
                with st.spinner("Chal raha hai..."):
                    app.invoke(Command(resume=answer), config)
            except Exception as e:
                st.error(str(e)[:200])
            st.rerun()

# ---------- tool trace ----------
with col_trace:
    st.markdown("#### Tool trace")
    results = {m.tool_call_id: m for m in messages if isinstance(m, ToolMessage)}

    if not tool_calls:
        st.markdown('<div class="empty">Abhi koi tool call nahi hua</div>', unsafe_allow_html=True)
    for call in tool_calls:
        st.markdown(trace_card(call, results.get(call["id"])), unsafe_allow_html=True)

    if pending:
        st.markdown('<span class="badge b-wait">graph paused, approval ka wait</span>', unsafe_allow_html=True)

# ---------- input ----------
# approval pending ho to naya message band
text = st.chat_input("Kuch poochho...", disabled=pending is not None)
text = text or st.session_state.pop("queued", None)

if text:
    try:
        with st.spinner("Soch raha hai..."):
            app.invoke({"messages": [("user", text)]}, config)
    except Exception as e:
        st.error(str(e)[:200])
    st.rerun()