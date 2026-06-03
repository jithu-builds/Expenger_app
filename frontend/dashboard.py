"""
Dashboard page — PDF upload, transaction processing, spending charts,
and manual edit / delete of individual transactions.
"""

import os
import tempfile
from datetime import date as _date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


from backend.ai_engine import extract_transactions_from_markdown
from backend.document_parser import parse_pdf_to_markdown
from backend.supabase_client import (
    delete_transaction,
    delete_transactions,
    fetch_transactions,
    file_already_imported,
    insert_transactions,
    update_transaction,
)

CATEGORY_COLORS = {
    "Food & Dining":  "#BD866A",   # terracotta
    "Transport":      "#7AA0C4",   # dusty sky
    "Shopping":       "#C9A860",   # warm gold
    "Entertainment":  "#C97B7B",   # muted rose
    "Utilities":      "#7B9E87",   # sage green
    "Rent & Housing": "#A07850",   # deep amber
    "Healthcare":     "#B07090",   # mauve
    "Income":         "#8FB87A",   # light sage
    "Transfer":       "#A89880",   # cream-muted
    "Subscriptions":  "#89685F",   # dark terracotta
    "Other":          "#6B5C50",   # cream-dim
}

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#A89880", size=12),
    margin=dict(t=10, b=10, l=10, r=10),
)


def _load_transactions() -> list[dict]:
    with st.spinner("Loading your transactions…"):
        result = fetch_transactions(st.session_state.user_id)
    if result["error"]:
        st.error(f"Could not load transactions: {result['error']}")
        return []
    st.session_state.transactions = result["data"]
    return result["data"]


def _process_uploaded_pdf(uploaded_file) -> None:
    suffix   = os.path.splitext(uploaded_file.name)[-1] or ".pdf"
    tmp_path = ""

    progress_bar = st.progress(0, text="Starting…")
    status_box   = st.empty()

    def update(pct: int, msg: str) -> None:
        progress_bar.progress(pct, text=msg)
        status_box.info(msg)

    try:
        update(5,  "📁 Preparing file…")
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        update(15, "📤 Uploading PDF to Reducto…")
        markdown_text = parse_pdf_to_markdown(tmp_path)
        update(45, f"📄 Text extracted — {len(markdown_text):,} characters.")

        update(55, "🤖 Asking Expenger AI to identify transactions…")
        transactions = extract_transactions_from_markdown(markdown_text)
        update(80, f"✅ Found {len(transactions)} transactions.")

        if not transactions:
            progress_bar.empty(); status_box.empty()
            st.warning("No transactions were found in this document.")
            return

        update(88, "💾 Saving to database…")
        result = insert_transactions(
            user_id=st.session_state.user_id,
            transactions=transactions,
            source_file=uploaded_file.name,
        )

        if result["error"]:
            progress_bar.empty(); status_box.empty()
            st.error(f"Database error: {result['error']}")
            return

        update(100, "🎉 All done!")
        progress_bar.empty(); status_box.empty()

        st.success(f"Imported **{len(transactions)}** transactions from **{uploaded_file.name}**.")
        with st.expander("Preview extracted transactions", expanded=True):
            st.dataframe(pd.DataFrame(transactions), use_container_width=True, hide_index=True)

        _load_transactions()
        st.rerun()

    except Exception as exc:
        progress_bar.empty(); status_box.empty()
        st.error(f"Processing failed: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _get_color_sequence(categories: list[str]) -> list[str]:
    default_colors = list(CATEGORY_COLORS.values())
    return [CATEGORY_COLORS.get(c, default_colors[i % len(default_colors)])
            for i, c in enumerate(categories)]


def _render_charts(df: pd.DataFrame) -> None:
    expenses = df[df["amount"] < 0].copy()
    expenses["amount_abs"] = expenses["amount"].abs()

    if expenses.empty:
        st.info("No expense transactions to chart yet.")
        return

    cat_totals = (
        expenses.groupby("category")["amount_abs"]
        .sum().reset_index()
        .rename(columns={"amount_abs": "Total Spent"})
        .sort_values("Total Spent", ascending=False)
    )
    categories  = cat_totals["category"].tolist()
    color_seq   = _get_color_sequence(categories)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Spending by Category")
        fig = px.pie(
            cat_totals, names="category", values="Total Spent",
            hole=0.45, color="category",
            color_discrete_map=CATEGORY_COLORS,
        )
        fig.update_traces(
            textposition="inside", textinfo="percent+label",
            textfont_size=11,
            marker=dict(line=dict(color="#1a1512", width=2)),
        )
        fig.update_layout(**PLOT_LAYOUT, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Category Breakdown")
        fig = go.Figure(go.Bar(
            x=cat_totals["Total Spent"],
            y=cat_totals["category"],
            orientation="h",
            text=[f"${v:,.0f}" for v in cat_totals["Total Spent"]],
            textposition="outside",
            textfont=dict(color="#F4ECDC", size=11),
            marker_color=color_seq,
            marker_line_width=0,
        ))
        fig.update_layout(
            **PLOT_LAYOUT,
            yaxis=dict(categoryorder="total ascending", tickfont=dict(color="#A89880")),
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                       tickfont=dict(color="#6B5C50")),
            bargap=0.3,
        )
        st.plotly_chart(fig, use_container_width=True)

    if "date" in df.columns and df["date"].notna().any():
        st.subheader("Monthly Spending Trend")
        trend = expenses.copy()
        trend["date"] = pd.to_datetime(trend["date"], errors="coerce")
        trend = trend.dropna(subset=["date"])
        trend["month"] = trend["date"].dt.to_period("M").astype(str)
        monthly = trend.groupby(["month", "category"])["amount_abs"].sum().reset_index()

        if not monthly.empty:
            fig = px.bar(
                monthly, x="month", y="amount_abs", color="category",
                labels={"amount_abs": "Amount ($)", "month": "Month", "category": ""},
                color_discrete_map=CATEGORY_COLORS,
            )
            fig.update_layout(
                **PLOT_LAYOUT,
                xaxis=dict(tickfont=dict(color="#A89880")),
                yaxis=dict(gridcolor="rgba(244,236,220,0.05)", tickfont=dict(color="#7a6b60")),
                legend=dict(
                    title=dict(text=""),
                    bgcolor="rgba(34,28,24,0.85)",
                    bordercolor="rgba(244,236,220,0.1)",
                    borderwidth=1,
                    font=dict(color="#A89880", size=11),
                    itemsizing="constant",
                    orientation="h",
                    x=0.5, xanchor="center",
                    y=-0.22, yanchor="top",
                ),
                bargap=0.2,
            )
            fig.update_layout(margin=dict(t=10, b=90, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)


# ── Add transaction dialog ────────────────────────────────────────────────────

@st.dialog("Add Transaction")
def _manual_entry_dialog() -> None:
    c1, c2 = st.columns(2)
    with c1:
        date_str = st.text_input("Date", value=_date.today().strftime("%Y-%m-%d"),
                                 placeholder="YYYY-MM-DD")
        txn_type = st.selectbox("Type", ["Expense", "Income"])
    with c2:
        desc   = st.text_input("Description", placeholder="e.g. Grocery store, Salary")
        amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, format="%.2f")

    category = st.selectbox("Category", list(CATEGORY_COLORS.keys()))

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Save Transaction", type="primary", use_container_width=True):
        try:
            _date.fromisoformat(date_str)
        except ValueError:
            st.error("Invalid date — use YYYY-MM-DD format.")
            st.stop()
        if not desc.strip():
            st.error("Description is required.")
        else:
            signed_amount = -abs(amount) if txn_type == "Expense" else abs(amount)
            result = insert_transactions(
                user_id=st.session_state.user_id,
                transactions=[{
                    "date":        date_str,
                    "description": desc.strip(),
                    "amount":      signed_amount,
                    "category":    category,
                }],
                source_file="manual",
            )
            if result["error"]:
                st.error(f"Could not save: {result['error']}")
            else:
                st.session_state.pop("transactions", None)
                st.rerun()


# ── Edit transaction dialog ───────────────────────────────────────────────────

@st.dialog("Edit Transaction")
def _edit_transaction_dialog(txn: dict) -> None:
    txn_id = txn.get("id", "")

    c1, c2 = st.columns(2)
    with c1:
        current_date = str(txn.get("date", _date.today().strftime("%Y-%m-%d")))[:10]
        date_str = st.text_input("Date", value=current_date, placeholder="YYYY-MM-DD")
        current_amt = float(txn.get("amount", 0))
        txn_type = st.selectbox(
            "Type",
            ["Expense", "Income"],
            index=0 if current_amt <= 0 else 1,
        )
    with c2:
        desc = st.text_input("Description", value=txn.get("description", ""))
        amount = st.number_input(
            "Amount ($)", min_value=0.01, step=0.01, format="%.2f",
            value=abs(current_amt) or 0.01,
        )

    cats = list(CATEGORY_COLORS.keys())
    current_cat = txn.get("category", "Other")
    cat_idx = cats.index(current_cat) if current_cat in cats else 0
    category = st.selectbox("Category", cats, index=cat_idx)

    st.markdown("<br>", unsafe_allow_html=True)
    save_col, del_col = st.columns([3, 1])

    with save_col:
        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            try:
                _date.fromisoformat(date_str)
            except ValueError:
                st.error("Invalid date — use YYYY-MM-DD format.")
                st.stop()
            if not desc.strip():
                st.error("Description is required.")
                st.stop()
            signed_amount = -abs(amount) if txn_type == "Expense" else abs(amount)
            res = update_transaction(
                st.session_state.user_id,
                txn_id,
                {
                    "date":        date_str,
                    "description": desc.strip(),
                    "amount":      signed_amount,
                    "category":    category,
                },
            )
            if res["error"]:
                st.error(f"Could not update: {res['error']}")
            else:
                st.session_state.pop("transactions", None)
                st.rerun()

    with del_col:
        if st.button("🗑️ Delete", use_container_width=True):
            st.session_state["_confirm_delete_id"] = txn_id
            st.rerun()


# ── Delete confirmation dialog ────────────────────────────────────────────────

@st.dialog("Confirm Delete")
def _confirm_delete_dialog(txn_id: str, desc: str) -> None:
    st.warning(f"Are you sure you want to delete **\"{desc}\"**? This cannot be undone.")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Yes, delete", type="primary", use_container_width=True):
            res = delete_transaction(st.session_state.user_id, txn_id)
            if res["error"]:
                st.error(f"Could not delete: {res['error']}")
            else:
                st.session_state.pop("transactions", None)
                st.session_state.pop("_confirm_delete_id", None)
                st.rerun()
    with col_no:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("_confirm_delete_id", None)
            st.rerun()


# ── Clear all confirmation dialog ─────────────────────────────────────────────

@st.dialog("Clear All Transactions")
def _confirm_clear_all_dialog() -> None:
    st.error("🚨 **Warning:** This will permanently delete ALL transactions in your account. This action cannot be undone.")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Yes, clear all data", type="primary", use_container_width=True):
            res = delete_transactions(st.session_state.user_id)
            if res["error"]:
                st.error(f"Could not clear: {res['error']}")
            else:
                st.session_state.pop("transactions", None)
                st.session_state.pop("_confirm_clear_all", None)
                st.rerun()
    with col_no:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("_confirm_clear_all", None)
            st.rerun()


# ── Manage transactions section ───────────────────────────────────────────────

def _render_manage_section(df: pd.DataFrame) -> None:
    if df.empty or "id" not in df.columns:
        return

    st.caption("Select a transaction from the list to edit its details or remove it.")

    # Build display labels
    def _label(row: pd.Series) -> str:
        date_part = str(row.get("date", ""))[:10]
        desc_part = str(row.get("description", ""))[:40]
        amt       = row.get("amount", 0)
        sign      = "-" if float(amt) < 0 else "+"
        return f"{date_part}  ·  {desc_part}  ·  {sign}${abs(float(amt)):,.2f}"

    labels = df.apply(_label, axis=1).tolist()
    ids    = df["id"].tolist()

    selected_idx = st.selectbox(
        "Choose transaction",
        range(len(labels)),
        format_func=lambda i: labels[i],
        label_visibility="collapsed",
    )

    if selected_idx is not None:
        row    = df.iloc[selected_idx]
        txn_id = ids[selected_idx]
        txn    = row.to_dict()

        col_edit, col_del, _ = st.columns([1, 1, 4])
        with col_edit:
            if st.button("✏️  Edit", key="btn_edit", use_container_width=True):
                _edit_transaction_dialog(txn)
        with col_del:
            if st.button("🗑️  Delete", key="btn_del", use_container_width=True):
                _confirm_delete_dialog(txn_id, str(txn.get("description", "")))




# ── Scroll helper (robust across Streamlit versions) ─────────────────────────

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


# ── Month filter helper ───────────────────────────────────────────────────────

def _build_month_options(df: pd.DataFrame) -> list[str]:
    """Return sorted list of 'YYYY-MM' strings present in df, newest first."""
    if df.empty or "date" not in df.columns:
        return []
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    months = sorted(dates.dt.to_period("M").astype(str).unique(), reverse=True)
    return months


def _filter_by_month(df: pd.DataFrame, month: str) -> pd.DataFrame:
    """Return rows whose date falls in the given 'YYYY-MM' period."""
    if month == "All Time" or df.empty or "date" not in df.columns:
        return df
    dates = pd.to_datetime(df["date"], errors="coerce")
    mask  = dates.dt.to_period("M").astype(str) == month
    return df[mask].copy()


def _fmt_month(m: str) -> str:
    """'2026-04' → 'April 2026'"""
    try:
        return pd.Period(m, freq="M").strftime("%B %Y")
    except Exception:
        return m


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    # ── Scroll to top ─────────────────────────────────────────────────────────
    st.iframe(_SCROLL_JS, height=1)

    # ── Pending delete confirmation (survives rerun) ───────────────────────────
    if "_confirm_delete_id" in st.session_state:
        pending_id   = st.session_state["_confirm_delete_id"]
        txns         = st.session_state.get("transactions", [])
        pending_desc = next(
            (t.get("description", "") for t in txns if t.get("id") == pending_id), ""
        )
        _confirm_delete_dialog(pending_id, pending_desc)

    if st.session_state.get("_confirm_clear_all", False):
        _confirm_clear_all_dialog()

    # ── Load transactions (always from cache first) ────────────────────────────
    if "transactions" not in st.session_state:
        _load_transactions()
    transactions = st.session_state.get("transactions", [])

    df_full = pd.DataFrame(transactions) if transactions else pd.DataFrame()
    if not df_full.empty:
        df_full["amount"] = pd.to_numeric(df_full["amount"], errors="coerce").fillna(0)

    if st.session_state.pop("scroll_to_manage", False):
        st.iframe(
            """<script>
            setTimeout(function() {
                try {
                    var els = window.parent.document.getElementsByClassName('manage-section-anchor');
                    if (els.length) els[0].scrollIntoView({behavior:'smooth', block:'start'});
                } catch(e) {}
            }, 250);
            </script>""",
            height=1,
        )

    # ── Header row ─────────────────────────────────────────────────────────────
    title_col, add_col, manage_col = st.columns([3, 1.2, 1.4])
    with title_col:
        st.title("📊 Dashboard")
    with add_col:
        st.markdown("<div style='padding-top:1.1rem'>", unsafe_allow_html=True)
        if st.button("➕ Add Transaction", type="primary", use_container_width=True):
            _manual_entry_dialog()
        st.markdown("</div>", unsafe_allow_html=True)
    with manage_col:
        st.markdown("<div style='padding-top:1.1rem'>", unsafe_allow_html=True)
        if st.button("✏️ Manage Transactions", use_container_width=True,
                     help="Edit or delete existing transactions"):
            st.session_state.show_manage = not st.session_state.get("show_manage", False)
            st.session_state.scroll_to_manage = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Upload section ─────────────────────────────────────────────────────────
    st.subheader("Upload Bank Statement")
    st.markdown(
        """
        <div style="background:rgba(122,160,196,0.07);border:1px solid rgba(122,160,196,0.2);
                    border-radius:12px;padding:0.75rem 1rem;margin-bottom:0.75rem;
                    font-size:0.82rem;color:#A89880;line-height:1.7">
            <b style="color:#7AA0C4">📋 Requirements:</b>
            &nbsp; PDF format only &nbsp;·&nbsp;
            Text-selectable (not a scanned image) &nbsp;·&nbsp;
            Any bank's statement layout is supported &nbsp;·&nbsp;
            Max recommended size: 20 MB
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Select a PDF bank statement",
        type=["pdf"],
        key="pdf_uploader",
        label_visibility="collapsed",
    )

    # Reject non-PDFs (drag-and-drop edge case)
    if uploaded_file is not None and not uploaded_file.name.lower().endswith(".pdf"):
        st.error("❌ Only PDF files are supported. Please upload a bank statement in PDF format.")
        uploaded_file = None

    # Enforce 20 MB limit
    if uploaded_file is not None and uploaded_file.size > 20 * 1024 * 1024:
        size_mb = uploaded_file.size / (1024 * 1024)
        st.error(f"❌ File too large ({size_mb:.1f} MB). Please upload a PDF under 20 MB.")
        uploaded_file = None

    if uploaded_file is not None:
        col_btn, col_info, _ = st.columns([1, 3, 2])
        with col_info:
            st.markdown(
                f"<div style='padding:0.55rem 0;color:#D4C4A8;font-size:0.875rem'>"
                f"📄 <b style='color:#F4ECDC'>{uploaded_file.name}</b> "
                f"({uploaded_file.size / 1024:.1f} KB) ready to upload</div>",
                unsafe_allow_html=True,
            )
        with col_btn:
            upload_clicked = st.button(
                "⬆️ Upload & Process", type="primary", use_container_width=True
            )

        if upload_clicked:
            st.session_state.pop("last_uploaded_file", None)
            already_imported = file_already_imported(
                st.session_state.user_id, uploaded_file.name
            )
            if already_imported:
                st.warning(
                    f"**{uploaded_file.name}** was already imported. "
                    "Duplicate rows will be skipped automatically."
                )
                col_yes, col_no, _ = st.columns([1, 1, 4])
                with col_yes:
                    if st.button("Import anyway", key="confirm_reimport"):
                        _process_uploaded_pdf(uploaded_file)
                with col_no:
                    if st.button("Cancel", key="cancel_reimport"):
                        st.rerun()
            else:
                _process_uploaded_pdf(uploaded_file)

    st.divider()

    # ── No data yet ────────────────────────────────────────────────────────────
    if df_full.empty:
        st.info("No transactions yet. Upload a PDF statement above to get started.")
        return

    # ── Month filter ───────────────────────────────────────────────────────────
    month_options = ["All Time"] + _build_month_options(df_full)

    filter_col, _ = st.columns([2, 5])
    with filter_col:
        selected_month = st.selectbox(
            "📅  Filter by month",
            month_options,
            format_func=lambda m: m if m == "All Time" else _fmt_month(m),
            key="dash_month_filter",
        )

    df = _filter_by_month(df_full, selected_month)

    if df.empty:
        st.info(f"No transactions found for {_fmt_month(selected_month)}.")
        return

    # ── Metrics ────────────────────────────────────────────────────────────────
    st.subheader(
        "Your Transactions"
        if selected_month == "All Time"
        else f"Transactions — {_fmt_month(selected_month)}"
    )

    total_income   = df[df["amount"] > 0]["amount"].sum()
    total_expenses = df[df["amount"] < 0]["amount"].abs().sum()
    net            = total_income - total_expenses

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Transactions",   len(df))
    k2.metric("Total Income",   f"${total_income:,.2f}")
    k3.metric("Total Expenses", f"${total_expenses:,.2f}")
    k4.metric("Net",            f"${net:,.2f}")

    st.divider()
    _render_charts(df)

    # ── Manage Transactions — anchor + panel sit ABOVE the transactions table ──
    st.markdown('<div class="manage-section-anchor"></div>', unsafe_allow_html=True)

    if st.session_state.get("show_manage"):
        st.subheader("✏️ Manage Transactions")
        if df_full.empty:
            st.info("No transactions to manage yet.")
        else:
            _render_manage_section(df_full)
        st.divider()

    col_lbl, col_clear = st.columns([3.8, 1.8])
    with col_lbl:
        st.subheader("All Transactions")
    with col_clear:
        st.markdown("<div style='padding-top:0.3rem'>", unsafe_allow_html=True)
        if st.button(
            "🗑️ Clear All Transactions",
            key="btn_clear_all_table",
            use_container_width=True,
            disabled=df_full.empty,
            help="Wipe out all transaction records",
        ):
            st.session_state["_confirm_clear_all"] = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    display_cols = [c for c in ["date", "description", "amount", "category", "source_file"]
                    if c in df.columns]
    st.dataframe(
        df[display_cols].sort_values("date", ascending=False, na_position="last"),
        use_container_width=True,
        hide_index=True,
    )
