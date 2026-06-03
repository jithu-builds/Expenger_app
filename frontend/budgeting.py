"""
Budgeting page — set monthly limits and track actual vs budget.
AI can suggest limits based on spending history.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


from backend.ai_engine import suggest_budgets
from backend.supabase_client import delete_budget, fetch_budgets, fetch_transactions, upsert_budget

CATEGORIES = [
    "Food & Dining", "Transport", "Shopping", "Entertainment",
    "Utilities", "Rent & Housing", "Healthcare", "Subscriptions", "Other",
]

CATEGORY_COLORS = {
    "Food & Dining":  "#BD866A",   # terracotta
    "Transport":      "#7AA0C4",   # dusty sky
    "Shopping":       "#C9A860",   # warm gold
    "Entertainment":  "#C97B7B",   # muted rose
    "Utilities":      "#7B9E87",   # sage green
    "Rent & Housing": "#A07850",   # deep amber
    "Healthcare":     "#B07090",   # mauve
    "Subscriptions":  "#89685F",   # dark terracotta
    "Other":          "#6B5C50",   # cream-dim
}


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    with st.spinner("Loading budget data…"):
        t = fetch_transactions(st.session_state.user_id)
        b = fetch_budgets(st.session_state.user_id)

    txn_df = pd.DataFrame(t["data"] or [])
    bud_df = pd.DataFrame(b["data"] or [])

    if not txn_df.empty:
        txn_df["amount"] = pd.to_numeric(txn_df["amount"], errors="coerce").fillna(0)

    return txn_df, bud_df


_SCROLL_JS = """
<script>
(function() {
    function doScroll() {
        try {
            var p = window.parent;
            p.scrollTo(0, 0);
            p.document.documentElement.scrollTop = 0;
            p.document.body.scrollTop = 0;
            ['section.main',
             '[data-testid="stMainBlockContainer"]',
             '[data-testid="stAppViewBlockContainer"]',
             '[data-testid="stMain"]',
             '.main'].forEach(function(s) {
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
</script>
"""


_BUDGET_CSS = """
<style>
@keyframes bud-panel-in {
    from { opacity: 0; transform: translateY(-10px); max-height: 0; }
    to   { opacity: 1; transform: translateY(0);    max-height: 2000px; }
}
.budget-form-panel {
    animation: bud-panel-in 0.28s cubic-bezier(0.34, 1.3, 0.64, 1) forwards;
    overflow: hidden;
}
</style>
"""

def render() -> None:
    st.iframe(_SCROLL_JS, height=1)
    st.markdown(_BUDGET_CSS, unsafe_allow_html=True)
    st.title("💰 Budgeting")

    txn_df, bud_df = _load_data()
    existing_limits: dict[str, float] = (
        dict(zip(bud_df["category"], bud_df["monthly_limit"]))
        if not bud_df.empty else {}
    )

    # ── AI Budget Suggestions ──────────────────────────────────────────────────
    if not txn_df.empty:
        col_btn, col_note = st.columns([1, 3])
        with col_btn:
            run_ai = st.button("✨ Get AI Budget Suggestions", use_container_width=True)
        with col_note:
            st.caption("Expenger AI will analyse your spending history and suggest realistic monthly limits.")

        if run_ai:
            with st.spinner("🤖 Analysing your spending history…"):
                suggestions = suggest_budgets(txn_df.to_dict("records"))

            if suggestions:
                st.success("AI suggestions ready — review and apply below.")
                # Store in session state so the form can pick them up
                st.session_state["ai_budget_suggestions"] = {
                    s["category"]: float(s["suggested_limit"]) for s in suggestions
                }
                # Show reasoning
                with st.expander("View AI reasoning", expanded=False):
                    for s in suggestions:
                        st.markdown(
                            f"**{s['category']}** → ${s['suggested_limit']:,.2f}/mo  \n"
                            f"<span style='color:#94a3b8;font-size:0.85rem'>{s.get('reasoning','')}</span>",
                            unsafe_allow_html=True,
                        )
            else:
                st.warning("Couldn't generate suggestions — try uploading more transaction data.")

    # ── Set Budgets — button-triggered inline form ────────────────────────────
    if "show_budget_form" not in st.session_state:
        st.session_state.show_budget_form = bud_df.empty  # auto-open when no budgets

    if st.button(
        "⚙️ Set Monthly Budget Limits" if not st.session_state.show_budget_form
        else "✕ Close Budget Editor",
        use_container_width=False,
    ):
        st.session_state.show_budget_form = not st.session_state.show_budget_form
        st.session_state.pop("reset_inputs_to_zero", None)
        st.rerun()

    if st.session_state.show_budget_form:
        st.markdown(
            """
            <div class="budget-form-panel">
            <div style="background:rgba(201,168,96,0.06);border:1px solid rgba(201,168,96,0.18);
                        border-radius:12px;padding:1.2rem 1.4rem 0.6rem;margin:0.75rem 0 1rem">
            """,
            unsafe_allow_html=True,
        )
        ai_suggestions = st.session_state.get("ai_budget_suggestions", {})

        # Action row above the form
        col_actions, _ = st.columns([1.5, 3.5])
        with col_actions:
            if st.button("🧹 Reset All Inputs to Zero", key="btn_reset_zero", use_container_width=True):
                st.session_state["reset_inputs_to_zero"] = True
                st.rerun()

        with st.form("budget_form"):
            st.markdown("Set a **monthly limit** per category. AI suggestions are pre-filled if available.")
            cols = st.columns(3)
            inputs: dict[str, float] = {}

            reset_all = st.session_state.get("reset_inputs_to_zero", False)
            for idx, cat in enumerate(CATEGORIES):
                default = 0.0 if reset_all else (existing_limits.get(cat) or ai_suggestions.get(cat) or 0.0)
                with cols[idx % 3]:
                    inputs[cat] = st.number_input(
                        cat, min_value=0.0, value=float(default),
                        step=50.0, format="%.2f",
                    )

            submitted = st.form_submit_button("💾 Save Budgets", use_container_width=True)

        st.markdown("</div></div>", unsafe_allow_html=True)

        if submitted:
            st.session_state.pop("reset_inputs_to_zero", None)
            errors = []
            with st.spinner("Saving budgets…"):
                for cat, limit in inputs.items():
                    if limit > 0:
                        res = upsert_budget(st.session_state.user_id, cat, limit)
                        if res["error"]:
                            errors.append(f"{cat}: {res['error']}")
                    elif cat in existing_limits:
                        # User set an existing budget to 0 -> remove it from db
                        res = delete_budget(st.session_state.user_id, cat)
                        if res["error"]:
                            errors.append(f"{cat}: {res['error']}")
            if errors:
                st.error("Some budgets failed:\n" + "\n".join(errors))
            else:
                st.success("Budgets saved!")
                if "ai_budget_suggestions" in st.session_state:
                    del st.session_state["ai_budget_suggestions"]
                st.session_state.show_budget_form = False
                st.rerun()

    st.divider()

    # ── Budget vs Actual ──────────────────────────────────────────────────────
    import pandas as _pd
    _month_label = _pd.Timestamp.now().strftime("%B %Y")
    st.subheader(f"Budget vs Actual Spending — {_month_label}")
    st.caption("Showing current-month spending from all sources (PDF imports + manual entries).")

    if bud_df.empty:
        st.info("No budgets set yet. Use the form above or click **Get AI Budget Suggestions**.")
        return

    limits_map = dict(zip(bud_df["category"], bud_df["monthly_limit"]))

    # Actuals — current calendar month only (both PDF and manual sources)
    actuals_map: dict[str, float] = {}
    if not txn_df.empty:
        expenses = txn_df[txn_df["amount"] < 0].copy()
        expenses["amount_abs"] = expenses["amount"].abs()
        if "date" in expenses.columns:
            try:
                expenses["date"] = pd.to_datetime(expenses["date"], errors="coerce")
                today = pd.Timestamp.now()
                this_month = expenses[
                    (expenses["date"].dt.month == today.month) &
                    (expenses["date"].dt.year  == today.year)
                ]
                if not this_month.empty:
                    expenses = this_month
            except Exception:
                pass
        actuals_map = expenses.groupby("category")["amount_abs"].sum().to_dict()

    budgeted_cats = list(limits_map.keys())

    # ── Grouped bar chart ──────────────────────────────────────────────────────
    budgets_vals = [limits_map[c] for c in budgeted_cats]
    actual_vals  = [actuals_map.get(c, 0) for c in budgeted_cats]

    # Per-category colours for both bars — budget = translucent, actual = solid
    def _hex_to_rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    cat_colors     = [CATEGORY_COLORS.get(c, "#BD866A") for c in budgeted_cats]
    budget_fills   = [_hex_to_rgba(col, 0.18) for col in cat_colors]
    budget_borders = cat_colors
    actual_fills   = [
        "#C97B7B" if actual_vals[i] > budgets_vals[i] else _hex_to_rgba(cat_colors[i], 0.85)
        for i in range(len(budgeted_cats))
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Budget", x=budgeted_cats, y=budgets_vals,
        marker_color=budget_fills,
        marker_line=dict(color=budget_borders, width=1.5),
        text=[f"${v:,.0f}" for v in budgets_vals],
        textposition="outside", textfont=dict(color="#A89880", size=10),
    ))
    fig.add_trace(go.Bar(
        name="Actual",
        x=budgeted_cats,
        y=actual_vals,
        marker_color=actual_fills,
        marker_line=dict(
            color=["#C97B7B" if actual_vals[i] > budgets_vals[i] else cat_colors[i]
                   for i in range(len(budgeted_cats))],
            width=0,
        ),
        text=[f"${v:,.0f}" for v in actual_vals],
        textposition="outside", textfont=dict(color="#F4ECDC", size=10),
    ))
    fig.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#A89880"),
        xaxis=dict(tickangle=-25, gridcolor="rgba(244,236,220,0.04)", tickfont=dict(color="#A89880")),
        yaxis=dict(gridcolor="rgba(244,236,220,0.05)", tickprefix="$", tickfont=dict(color="#6B5C50")),
        legend=dict(
            bgcolor="rgba(34,28,24,0.85)", bordercolor="rgba(244,236,220,0.1)",
            borderwidth=1, font=dict(color="#D4C4A8"),
            orientation="h", x=0.5, xanchor="center", y=-0.18, yanchor="top",
        ),
        margin=dict(t=20, b=80),
        bargap=0.25, bargroupgap=0.05,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Status table ──────────────────────────────────────────────────────────
    st.subheader("Category Status")
    rows = []
    for cat in budgeted_cats:
        limit   = limits_map[cat]
        actual  = actuals_map.get(cat, 0.0)
        pct     = (actual / limit * 100) if limit > 0 else 0.0
        remaining = limit - actual
        status  = (
            "🔴 Over budget"    if actual > limit
            else "🟡 Near limit" if pct >= 80
            else "🟢 On track"
        )
        rows.append({
            "Category":       cat,
            "Budget ($)":     round(limit, 2),
            "Spent ($)":      round(actual, 2),
            "Remaining ($)":  round(remaining, 2),
            "Used (%)":       round(pct, 1),
            "Status":         status,
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
