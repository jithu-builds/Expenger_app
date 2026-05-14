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
                        background:#