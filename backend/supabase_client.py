"""
Supabase client — Auth + DB queries.

Required Supabase SQL (run once in the SQL Editor):
─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    date        DATE,
    description TEXT,
    amount      NUMERIC(12, 2),
    category    TEXT,
    source_file TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budgets (
    id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    category      TEXT        NOT NULL,
    monthly_limit NUMERIC(12, 2) NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, category)
);

ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets      ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own transactions"
    ON transactions FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own budgets"
    ON budgets FOR ALL USING (auth.uid() = user_id);
─────────────────────────────────────────────────────
"""

import os
from functools import wraps
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def _secret(key: str) -> str:
    """Read from st.secrets (Streamlit Cloud) or fall back to os.getenv (.env)."""
    try:
        import streamlit as st
        return st.secrets.get(key) or os.getenv(key, "")
    except Exception:
        return os.getenv(key, "")


SUPABASE_URL: str = _secret("SUPABASE_URL")
SUPABASE_KEY: str = _secret("SUPABASE_KEY")
APP_URL: str = _secret("APP_URL") or "http://localhost:8501"

_client: Optional[Client] = None


def get_client() -> Client:
    """Return a lazy-initialised singleton Supabase client.

    Always re-applies the current user's JWT so that Supabase RLS policies
    work correctly.  The singleton loses its auth state when Streamlit
    hot-reloads modules; reading it from session_state each time fixes that.
    """
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_KEY must be set in your .env file."
            )
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Attach the logged-in user's JWT so RLS sees the right auth.uid()
    try:
        import streamlit as st
        token = st.session_state.get("access_token", "")
        if token:
            _client.postgrest.auth(token)
    except Exception:
        pass

    return _client


# ─── Authentication ───────────────────────────────────────────────────────────

def sign_up(email: str, password: str) -> dict:
    try:
        response = get_client().auth.sign_up({
            "email": email,
            "password": password,
            "options": {"email_redirect_to": APP_URL},
        })
        user = response.user
        if user and (user.identities is None or len(user.identities) == 0):
            return {"user": None, "session": None, "error": "User already registered"}
        return {"user": response.user, "session": response.session, "error": None}
    except Exception as exc:
        return {"user": None, "session": None, "error": str(exc)}


def sign_in(email: str, password: str) -> dict:
    try:
        response = get_client().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        return {"user": response.user, "session": response.session, "error": None}
    except Exception as exc:
        return {"user": None, "session": None, "error": str(exc)}


def sign_out() -> None:
    try:
        get_client().auth.sign_out()
    except Exception:
        pass


def reset_password(email: str) -> dict:
    try:
        get_client().auth.reset_password_for_email(
            email,
            options={"redirect_to": APP_URL},
        )
        return {"error": None}
    except Exception as exc:
        return {"error": str(exc)}


def exchange_code_for_session(code: str) -> dict:
    """Exchange a PKCE auth code (from the reset link) for a session."""
    try:
        response = get_client().auth.exchange_code_for_session({"auth_code": code})
        return {"session": response.session, "user": response.user, "error": None}
    except Exception as exc:
        return {"session": None, "user": None, "error": str(exc)}


def set_recovery_session(access_token: str, refresh_token: str) -> dict:
    """Activate a session from implicit-flow tokens (access_token in URL fragment)."""
    try:
        response = get_client().auth.set_session(access_token, refresh_token)
        return {"session": response.session, "error": None}
    except Exception as exc:
        return {"session": None, "error": str(exc)}


def update_user_password(new_password: str) -> dict:
    """Update the current user's password (must be called with an active session)."""
    try:
        get_client().auth.update_user({"password": new_password})
        return {"error": None}
    except Exception as exc:
        return {"error": str(exc)}


# ─── DB Query Decorator ───────────────────────────────────────────────────────

def _db_query(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            msg = str(exc)
            if "JWT expired" in msg or "PGRST303" in msg:
                try:
                    import streamlit as st
                    from components.auth import logout
                    st.toast("⚠️ Your session has expired. Logging you out...", icon="🔒")
                    import time
                    time.sleep(2)
                    logout()
                except Exception:
                    pass
            return {"data": [], "error": msg}
    return wrapper


# ─── Transactions ─────────────────────────────────────────────────────────────

@_db_query
def insert_transactions(user_id: str, transactions: list[dict], source_file: str = "") -> dict:
    if not transactions:
        return {"data": [], "error": None}
    rows = [
        {
            "user_id":     user_id,
            "date":        t.get("date"),
            "description": t.get("description", ""),
            "amount":      float(t.get("amount", 0)),
            "category":    t.get("category", "Other"),
            "source_file": source_file,
        }
        for t in transactions
    ]
    result = (
        get_client()
        .table("transactions")
        .upsert(rows, on_conflict="user_id,date,description,amount")
        .execute()
    )
    return {"data": result.data, "error": None}


@_db_query
def fetch_transactions(user_id: str) -> dict:
    result = (
        get_client()
        .table("transactions")
        .select("*")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .execute()
    )
    return {"data": result.data, "error": None}


def file_already_imported(user_id: str, filename: str) -> bool:
    """Return True if this filename was already imported for this user."""
    try:
        result = (
            get_client()
            .table("transactions")
            .select("id")
            .eq("user_id", user_id)
            .eq("source_file", filename)
            .limit(1)
            .execute()
        )
        return len(result.data) > 0
    except Exception as exc:
        msg = str(exc)
        if "JWT expired" in msg or "PGRST303" in msg:
            try:
                import streamlit as st
                from components.auth import logout
                st.toast("⚠️ Your session has expired. Logging you out...", icon="🔒")
                import time
                time.sleep(2)
                logout()
            except Exception:
                pass
        return False


@_db_query
def delete_transactions(user_id: str) -> dict:
    result = (
        get_client()
        .table("transactions")
        .delete()
        .eq("user_id", user_id)
        .execute()
    )
    return {"data": result.data, "error": None}


@_db_query
def delete_transaction(user_id: str, transaction_id: str) -> dict:
    """Delete a single transaction by UUID."""
    result = (
        get_client()
        .table("transactions")
        .delete()
        .eq("user_id", user_id)
        .eq("id", transaction_id)
        .execute()
    )
    return {"data": result.data, "error": None}


@_db_query
def update_transaction(user_id: str, transaction_id: str, updates: dict) -> dict:
    """Update editable fields (date, description, amount, category) of one transaction."""
    result = (
        get_client()
        .table("transactions")
        .update(updates)
        .eq("user_id", user_id)
        .eq("id", transaction_id)
        .execute()
    )
    return {"data": result.data, "error": None}


# ─── Budgets ──────────────────────────────────────────────────────────────────

@_db_query
def upsert_budget(user_id: str, category: str, monthly_limit: float) -> dict:
    result = (
        get_client()
        .table("budgets")
        .upsert(
            {"user_id": user_id, "category": category, "monthly_limit": monthly_limit},
            on_conflict="user_id,category",
        )
        .execute()
    )
    return {"data": result.data, "error": None}


@_db_query
def fetch_budgets(user_id: str) -> dict:
    result = (
        get_client()
        .table("budgets")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    return {"data": result.data, "error": None}


@_db_query
def delete_budget(user_id: str, category: str) -> dict:
    result = (
        get_client()
        .table("budgets")
        .delete()
        .eq("user_id", user_id)
        .eq("category", category)
        .execute()
    )
    return {"data": result.data, "error": None}

