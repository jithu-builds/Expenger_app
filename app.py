"""
AI Insights page.

Layout order (most actionable → least):
  1. 💡 Recommendations  ← moved to top
  2. 📊 Spending Health Score
  3. ⚠️ Budget Alerts
  4. 📈 End-of-Month Predictions
  5. 💬 AI Chat
"""

import plotly.graph_objects as go
import streamlit as st

from backend.ai_engine import answer_finance_question, generate_spending_insights
from backend.supabase_client import fetch_budgets, fetch_transactions

# ── Colour helpers ────────────────────────────────────────────────────────────

SEVERITY_STYLE = {
    "high":   ("🔴", "#ef4444", "rgba(239,68,68,0.1)"),
    "medium": ("🟡", "#f59e0b", "rgba(245,158,11,0.1)"),
    "low":    ("🟢", "#22c55e", "rgba(34,197,94,0.1)"),
}

CHAT_CSS = """
<style>
/* ── AI Insights page extras ── */
@keyframes ai-shimmer {
    0%   { opacity: 0.5; }
    50%  { opacity: 1;   }
    100% { opacity: 0.5; }
}
.ai-loading-card {
    position: fixed;
    inset: 0;
    z-index: 99999;
    text-align: center;
    background: #1a1512;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
}
.ai-loading-steps {
    display: flex; justify-content: center; align-items: center;
    gap: 0.75rem; flex-wrap: wrap; margin-top: 1.5rem;
}
.ai-step-chip {
    background: rgba(122,160,196,0.1);
    border: 1px solid rgba(122,160,196,0.25);
    border-radius: 99px; padding: 6px 16px;
    font-size: 0.78rem; color: #7AA0C4; font-weight: 600;
    animation: ai-shimmer 2s ease-in-out infinite;
}
.ai-step-chip:nth-child(2) { animation-delay: 0.4s; }
.ai-step-chip:nth-child(3) { animation-delay: 0.8s; }
.ai-step-chip:nth-child(4) { animation-delay: 1.2s; }

/* ── Rec card — sky-blue left border, gold category tag ── */
.rec-card {
    background: #221c18;
    border: 1px solid rgba(122,160,196,0.15);
    border-left: 3px solid #7AA0C4;
    border-radius: 14px; padding: 1.1rem 1.25rem;
    margin-bottom: 0.65rem;
    display: flex; justify-content: space-between;
    align-items: flex-start; gap: 1rem;
}
.rec-card-body { flex: 1; }
.rec-card-title { font-weight: 700; color: #F4ECDC; margin-bottom: 4px; }
.rec-card-detail { font-size: 0.875rem; color: #A89880; line-height: 1.55; }
.rec-card-cat {
    font-size: 0.72rem; color: #C9A860; margin-top: 6px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;
}
.rec-card-savings { text-align: center; min-width: 80px; }
.rec-savings-label {
    font-size: 0.65rem; color: #6B5C50; text-transform: uppercase;
    letter-spacing: 0.1em; margin-bottom: 2px;
}
.rec-savings-value { font-size: 1.2rem; font-weight: 800; color: #7B9E87; }

/* ── Chat section — gold top border ── */
.chat-header {
    display: flex; align-items: center; gap: 12px;
    padding: 1.25rem 1.5rem;
    background: linear-gradient(135deg, #221c18, #1e1813);
    border: 1px solid rgba(244,236,220,0.07);
    border-top: 2px solid rgba(201,168,96,0.4);
    border-bottom: none;
    border-radius: 16px 16px 0 0;
}
.chat-header-icon { font-size: 1.5rem; line-height: 1; }
.chat-header-title { font-size: 1rem; font-weight: 700; color: #F4ECDC; }
.chat-header-sub { font-size: 0.78rem; color: #A89880; }

.chat-examples {
    display: flex; flex-wrap: wrap; gap: 0.5rem;
    margin-bottom: 1rem;
}
.chat-empty-state {
    text-align: center; padding: 2rem 1rem;
    color: #3a2f28; font-size: 0.875rem;
}

/* ── Prediction rows ── */
.pred-row {
    background: #221c18;
    border: 1px solid rgba(244,236,220,0.07);
    border-radius: 14px; padding: 1rem 1.25rem;
    margin-bottom: 0.6rem;
}
.pred-meta {
    display: flex; justify-content: space-between;
    align-items: center; margin-bottom: 8px;
}
.pred-title { font-weight: 600; color: #F4ECDC; }
.pred-reason { font-size: 0.78rem; color: #A89880; }
.pred-numbers { display: flex; gap: 2rem; margin-bottom: 10px; }
.pred-num-group { }
.pred-num-label {
    font-size: 0.68rem; color: #6B5C50; text-transform: uppercase;
    letter-spacing: 0.08em; margin-bottom: 2px;
}
.pred-num-value { font-size: 1.05rem; font-weight: 700; color: #C9A860; }
.pred-bar-wrap {
    background: rgba(244,236,220,0.06);
    border-radius: 99px; height: 6px; overflow: hidden;
}
.pred-bar-fill {
    height: 100%; border-radius: 99px; transition: width 0.4s;
}

/* ── Alert cards ── */
.alert-card {
    border-radius: 14px; padding: 1rem 1.1rem; margin-bottom: 0.5rem;
}
.alert-cat {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.07em; margin-bottom: 6px;
}
.alert-msg { font-size: 0.875rem; color: #ede0cc; line-height: 1.5; }
</style>
"""

EXAMPLE_QUESTIONS = [
    "Where can I cut back most?",
    "How much did I spend on food?",
    "Am I on track with my budget?",
    "What's my biggest expense this month?",
]


def _score_color(score: int) -> str:
    if score >= 75: return "#22c55e"
    if score >= 50: return "#f59e0b"
    return "#ef4444"


def _score_label(score: int) -> str:
    if score >= 80: return "Excellent"
    if score >= 65: return "Good"
    if score >= 50: return "Fair"
    if score >= 30: return "Needs Attention"
    return "Over Budget"


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_data() -> tuple[list[dict], list[dict]]:
    with st.spinner("Loading your financial data…"):
        t = fetch_transactions(st.session_state.user_id)
        b = fetch_budgets(st.session_state.user_id)
    transactions = t["data"] if not t["error"] else []
    budgets      = b["data"] if not b["error"] else []
    st.session_state.transactions = transactions
    return transactions, budgets


# ── Loading state ─────────────────────────────────────────────────────────────

def _show_loading_card() -> None:
    st.markdown(
        """
        <div class="ai-loading-card">
            <div style="font-size:4rem;margin-bottom:1.25rem;
                        filter:drop-shadow(0 0 20px rgba(122,160,196,0.5))">🤖</div>
            <h3 style="color:#F4ECDC;font-size:1.5rem;font-weight:800;
                       margin-bottom:0.5rem;letter-spacing:-0.3px">
                Expenger AI is analysing your finances
            </h3>
            <p style="color:#A89880;font-size:0.9rem;max-width:420px;
                      margin:0 auto 1.5rem;line-height:1.6">
                Reading your transactions, calculating patterns,
                and generating personalised insights…
            </p>
            <div class="ai-loading-steps">
                <span class="ai-step-chip">📊 Reading transactions</span>
                <span class="ai-step-chip">🏷️ Analysing categories</span>
                <span class="ai-step-chip">📈 Calculating trends</span>
                <span class="ai-step-chip">💡 Generating insights</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Section renderers ─────────────────────────────────────────────────────────

def _render_recommendations(recommendations: list[dict]) -> None:
    if not recommendations:
        st.markdown(
            """
            <div style="text-align:center;padding:1.5rem;color:#5c4e46;font-size:0.875rem;
                        background:#221c18;border-radius:14px;border:1px solid rgba(244,236,220,0.06)">
                🎉 No specific recommendations right now — your spending looks healthy!
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for rec in recommendations:
        savings = float(rec.get("estimated_savings", 0))
        cat     = rec.get("category", "")
        title   = rec.get("title", "")
        detail  = rec.get("detail", "")

        savings_html = (
            f'<div class="rec-card-savings">'
            f'<div class="rec-savings-label">Save up to</div>'
            f'<div class="rec-savings-value">${savings:,.0f}</div>'
            f'</div>'
            if savings > 0 else ""
        )

        st.markdown(
            f"""
            <div class="rec-card">
                <div class="rec-card-body">
                    <div class="rec-card-title">💡 {title}</div>
                    <div class="rec-card-detail">{detail}</div>
                    <div class="rec-card-cat">{cat}</div>
                </div>
                {savings_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_health_score(score: int, summary: str) -> None:
    color = _score_color(score)
    label = _score_label(score)

    col_score, col_summary = st.columns([1, 3])

    with col_score:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "", "font": {"size": 36, "color": color}},
            gauge={
                "axis":      {"range": [0, 100], "tickcolor": "#475569", "tickwidth": 1},
                "bar":       {"color": color, "thickness": 0.25},
                "bgcolor":   "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0,  30], "color": "rgba(239,68,68,0.15)"},
                    {"range": [30, 65], "color": "rgba(245,158,11,0.12)"},
                    {"range": [65,100], "color": "rgba(34,197,94,0.12)"},
                ],
            },
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#b8a898"),
            height=200,
            margin=dict(t=20, b=0, l=20, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(
            f"<p style='text-align:center;font-size:1rem;font-weight:800;color:{color};"
            f"margin-top:-12px;letter-spacing:-0.2px'>{label}</p>",
            unsafe_allow_html=True,
        )

    with col_summary:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="background:#221c18;border:1px solid rgba(244,236,220,0.07);
                        border-left:3px solid {color};border-radius:14px;
                        padding:1.1rem 1.3rem;">
                <p style="color:#D4C4A8;font-size:0.95rem;margin:0;line-height:1.6">{summary}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_alerts(alerts: list[dict]) -> None:
    if not alerts:
        st.markdown(
            """
            <div style="text-align:center;padding:1rem;color:#5c4e46;font-size:0.875rem;
                        background:#221c18;border-radius:14px;border:1px solid rgba(244,236,220,0.06)">
                ✅ No budget alerts — you're on track across all categories.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    cols = st.columns(min(len(alerts), 3))
    for i, alert in enumerate(alerts):
        icon, color, bg = SEVERITY_STYLE.get(alert.get("severity", "low"), SEVERITY_STYLE["low"])
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="alert-card" style="background:{bg};border:1px solid {color}33">
                    <div class="alert-cat" style="color:{color}">{icon} {alert.get('category','')}</div>
                    <div class="alert-msg">{alert.get('message','')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_predictions(predictions: list[dict]) -> None:
    if not predictions:
        st.markdown(
            """
            <div style="text-align:center;padding:1rem;color:#5c4e46;font-size:0.875rem;
                        background:#221c18;border-radius:14px;border:1px solid rgba(244,236,220,0.06)">
                Not enough data to generate predictions yet.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for pred in predictions:
        cat       = pred.get("category", "")
        spent     = float(pred.get("spent_so_far", 0))
        predicted = float(pred.get("predicted_monthly_total", 0))
        budget    = pred.get("budget")
        exceed    = pred.get("will_exceed", False)
        reason    = pred.get("reason", "")

        budget_val  = float(budget) if budget else None
        pct         = min((predicted / budget_val * 100), 100) if budget_val else None
        bar_color   = "#ef4444" if exceed else "#BD866A"
        status_icon = "⚠️" if exceed else "✅"

        budget_html = (
            f'<div class="pred-num-group">'
            f'<div class="pred-num-label">Budget</div>'
            f'<div class="pred-num-value" style="color:#A89880">${budget_val:,.2f}</div>'
            f'</div>'
            if budget_val else ""
        )
        bar_html = (
            f'<div class="pred-bar-wrap">'
            f'<div class="pred-bar-fill" style="width:{pct:.1f}%;background:{bar_color}"></div>'
            f'</div>'
            if pct is not None else ""
        )

        st.markdown(
            f"""
            <div class="pred-row">
                <div class="pred-meta">
                    <span class="pred-title">{status_icon} {cat}</span>
                    <span class="pred-reason">{reason}</span>
                </div>
                <div class="pred-numbers">
                    <div class="pred-num-group">
                        <div class="pred-num-label">Spent so far</div>
                        <div class="pred-num-value">${spent:,.2f}</div>
                    </div>
                    <div class="pred-num-group">
                        <div class="pred-num-label">Predicted total</div>
                        <div class="pred-num-value" style="color:{'#ef4444' if exceed else '#f59e0b'}">${predicted:,.2f}</div>
                    </div>
                    {budget_html}
                </div>
                {bar_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── Chat section ──────────────────────────────────────────────────────────────

_SCROLL_TO_CHAT_JS = """
<script>
setTimeout(function() {
    try {
        var el = window.parent.document.querySelector('.chat-section-anchor');
        if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch(e) {}
}, 80);
</script>
"""

_SCROLL_TO_BOTTOM_JS = """
<script>
(function() {
    function scrollBottom() {
        try {
            var p = window.parent;
            p.scrollTo(0, p.document.body.scrollHeight);
            ['section.main',
             '[data-testid="stMainBlockContainer"]',
             '[data-testid="stAppViewBlockContainer"]',
             '[data-testid="stMain"]'].forEach(function(s) {
                var el = p.document.querySelector(s);
                if (el) el.scrollTop = el.scrollHeight;
            });
        } catch(e) {}
    }
    setTimeout(scrollBottom, 200);
    setTimeout(scrollBottom, 500);
    setTimeout(scrollBottom, 900);
})();
</script>
"""


def _render_chat(transactions: list[dict]) -> None:
    # Invisible anchor — JS scrolls to this when user submits a question
    st.markdown('<div class="chat-section-anchor"></div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="chat-header">
            <div class="chat-header-icon">💬</div>
            <div>
                <div class="chat-header-title">Ask Expenger AI</div>
                <div class="chat-header-sub">Ask anything about your spending, budgets, or financial habits</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # ── Example question chips ────────────────────────────────────────────────
    if not st.session_state.chat_messages:
        st.markdown(
            "<p style='color:#5c4e46;font-size:0.8rem;margin:1rem 0 0.5rem;"
            "font-weight:600;text-transform:uppercase;letter-spacing:0.08em'>"
            "Try asking:</p>",
            unsafe_allow_html=True,
        )
        chip_cols = st.columns(len(EXAMPLE_QUESTIONS))
        for i, q in enumerate(EXAMPLE_QUESTIONS):
            with chip_cols[i]:
                if st.button(q, key=f"chip_{i}", use_container_width=True):
                    st.session_state.chat_prefill = q
                    st.session_state.scroll_to_chat = True
                    st.rerun()

    # Handle pre-filled question from chip click
    prefill_prompt = st.session_state.pop("chat_prefill", None)

    # If a chip was clicked, scroll to chat on this render
    if st.session_state.pop("scroll_to_chat", False):
        st.iframe(_SCROLL_TO_CHAT_JS, height=1)

    # Show existing messages
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input — scroll to chat section as soon as user submits
    prompt = st.chat_input("Ask anything about your spending…") or prefill_prompt
    if prompt:
        # Scroll to chat section immediately when user submits
        st.iframe(_SCROLL_TO_CHAT_JS, height=1)

        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    reply = answer_finance_question(
                        prompt, transactions,
                        chat_history=st.session_state.chat_messages[:-1],
                    )
                except Exception as exc:
                    reply = f"Error: {exc}"
            st.markdown(reply)
        # Scroll to bottom AFTER response renders so user sees the latest reply
        st.iframe(_SCROLL_TO_BOTTOM_JS, height=1)
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})

    if st.session_state.chat_messages:
        if st.button("🗑️ Clear chat history"):
            st.session_state.chat_messages = []
            st.rerun()


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    # Scroll to top on tab switch — called repeatedly to beat Streamlit's lazy render
    st.iframe(
        """<script>
        (function(){
            function doScroll(){
                try {
                    var p = window.parent;
                    p.scrollTo(0, 0);
                    p.document.documentElement.scrollTop = 0;
                    p.document.body.scrollTop = 0;
                    ['section.main','[data-testid="stMainBlockContainer"]',
                     '[data-testid="stAppViewBlockContainer"]',
                     '[data-testid="stMain"]','.main'].forEach(function(s){
                        var el = p.document.querySelector(s);
                        if (el) el.scrollTop = 0;
                    });
                } catch(e) {}
            }
            doScroll();
            setTimeout(doScroll, 150);
            setTimeout(doScroll, 400);
            setTimeout(doScroll, 800);
        })();
        </script>""",
        height=1,
    )

    st.markdown(CHAT_CSS, unsafe_allow_html=True)

    # Header row
    hdr_col, btn_col = st.columns([5, 1])
    with hdr_col:
        st.title("🧠 AI Insights")
        st.caption("Powered by Expenger AI · Personalised analysis of your spending patterns.")
    with btn_col:
        st.markdown("<div style='padding-top:1.1rem'>", unsafe_allow_html=True)
        refresh = st.button("🔄 Refresh", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    transactions, budgets = _load_data()

    if not transactions:
        st.markdown(
            """
            <div style="text-align:center;padding:4rem 2rem 2rem;background:#221c18;
                        border:1px solid rgba(244,236,220,0.07);border-radius:20px;margin:1rem 0">
                <div style="font-size:3rem;margin-bottom:1rem">📂</div>
                <h3 style="color:#F4ECDC;margin-bottom:0.5rem">No transaction data yet</h3>
                <p style="color:#A89880;margin-bottom:0">Upload a bank statement from the Dashboard to unlock AI insights.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Place button centered below the card
        _, btn_col, _ = st.columns([1.2, 1.5, 1.2])
        with btn_col:
            if st.button("Upload PDF", type="primary", use_container_width=True):
                st.session_state.nav_page = "📊  Dashboard"
                st.rerun()
        return

    cache_key = f"insights_{st.session_state.user_id}"

    if cache_key not in st.session_state or refresh:
        load_slot = st.empty()
        with load_slot.container():
            _show_loading_card()
        try:
            generated = generate_spending_insights(transactions, budgets)
            st.session_state[cache_key] = generated
        except Exception as exc:
            load_slot.empty()
            st.error(f"Could not generate insights: {exc}")
            return
        load_slot.empty()
        # Rerun so the fresh render starts from the top.
        # Insights are cached — the loading block won't run again.
        st.rerun()

    insights = st.session_state.get(cache_key)
    if not insights:
        return

    # ── Rate-limit banner — show friendly message, still render chat ──────────
    if insights.get("_rate_limited"):
        st.markdown(
            f"""
            <div style="background:rgba(201,168,96,0.08);border:1px solid rgba(201,168,96,0.25);
                        border-left:3px solid #C9A860;border-radius:14px;padding:1.1rem 1.3rem;
                        margin-bottom:1.5rem">
                <div style="font-weight:700;color:#C9A860;margin-bottom:4px">
                    ⚠️ Gemini API quota reached
                </div>
                <div style="color:#D4C4A8;font-size:0.875rem;line-height:1.6">
                    {insights["summary"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Clear cache so next Refresh retries the API
        st.session_state.pop(cache_key, None)
        _render_chat(transactions)
        return

    # ── 1. Recommendations (most actionable — shown first) ────────────────────
    st.subheader("💡 Recommendations")
    st.caption("Specific actions based on your actual transaction patterns.")
    _render_recommendations(insights.get("recommendations", []))

    st.divider()

    # ── 2. Spending Health Score ──────────────────────────────────────────────
    st.subheader("📊 Spending Health Score")
    _render_health_score(
        insights.get("health_score", 50),
        insights.get("summary", ""),
    )

    st.divider()

    # ── 3. Budget Alerts ──────────────────────────────────────────────────────
    st.subheader("⚠️ Budget Alerts")
    _render_alerts(insights.get("alerts", []))

    st.divider()

    # ── 4. End-of-Month Predictions ───────────────────────────────────────────
    st.subheader("📈 End-of-Month Predictions")
    st.caption("Based on your spending pace so far this month.")
    _render_predictions(insights.get("predictions", []))

    st.divider()

    # ── 5. AI Chat ────────────────────────────────────────────────────────────
    _render_chat(transactions)