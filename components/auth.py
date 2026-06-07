"""
Authentication UI — dialog-based login/signup + cookie-based session persistence.

Session survives browser refresh by storing user_id, user_email, and
access_token in browser cookies via extra-streamlit-components.

st.session_state keys written on success:
    logged_in    → bool
    user_id      → str
    user_email   → str
    access_token → str
"""

import json
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as _stc

from components.session_store import get_cm as _cm

from backend.supabase_client import sign_in, sign_up, sign_out, reset_password


COOKIE_EXPIRY = datetime.now() + timedelta(days=7)
_SESSION_COOKIE = "ft_session"  # single cookie — avoids duplicate key='set' error


# ─── Cookie helpers ───────────────────────────────────────────────────────────

def save_session_to_cookies(user_id: str, email: str, token: str) -> None:
    """Write session cookie via CookieManager."""
    data = json.dumps({"user_id": user_id, "email": email, "token": token})
    try:
        _cm().set(_SESSION_COOKIE, data, expires_at=COOKIE_EXPIRY)
    except Exception:
        pass


def restore_session_from_cookies() -> bool:
    if st.session_state.get("logged_in"):
        return True

    cm = _cm()
    raw = cm.get(_SESSION_COOKIE)
    if not raw:
        return False

    try:
        data    = raw if isinstance(raw, dict) else json.loads(raw)
        user_id = data.get("user_id")
        email   = data.get("email")
        token   = data.get("token", "")
    except (json.JSONDecodeError, AttributeError, TypeError):
        return False

    if user_id and email:
        st.session_state.logged_in    = True
        st.session_state.user_id      = user_id
        st.session_state.user_email   = email
        st.session_state.access_token = token
        return True

    return False


def clear_session_cookies() -> None:
    cm = _cm()
    try:
        cm.delete(_SESSION_COOKIE)
    except Exception:
        pass


# ─── Session state init ───────────────────────────────────────────────────────

def _init_session() -> None:
    for key, val in {
        "logged_in": False, "user_id": None,
        "user_email": None, "access_token": None,
    }.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _persist_session(result: dict) -> None:
    user    = result["user"]
    session = result["session"]
    token   = session.access_token if session else ""

    st.session_state.logged_in    = True
    st.session_state.user_id      = str(user.id)
    st.session_state.user_email   = user.email
    st.session_state.access_token = token
    st.session_state._logged_out  = False
    st.session_state._auth_open   = False  # allow cookie restore again after login
    save_session_to_cookies(str(user.id), user.email, token)


# ─── Logout ───────────────────────────────────────────────────────────────────

def logout() -> None:
    sign_out()
    clear_session_cookies()
    st.session_state.clear()
    st.session_state.logged_in = False
    # Use components.html() — unlike st.markdown(), it actually executes JS.
    # window.parent accesses the top Streamlit frame to delete the real cookie,
    # then forces a clean page reload so no stale session state survives.
    _stc.html(
        f"""<script>
        window.parent.document.cookie = '{_SESSION_COOKIE}=; Max-Age=0; path=/;';
        setTimeout(function() {{ window.parent.location.href = '/'; }}, 150);
        </script>""",
        height=1,
    )
    st.stop()


# ─── Form handlers ────────────────────────────────────────────────────────────

def _go_to_dashboard() -> None:
    """Close the dialog and go to dashboard natively."""
    st.session_state.show_auth = False
    st.session_state._auth_open = False
    st.session_state.auth_mode = None
    st.rerun()


def _handle_sign_in(email: str, password: str) -> None:
    if not email or not password:
        st.error("Please enter both email and password.")
        return
    with st.spinner("Signing in…"):
        result = sign_in(email, password)
    if result["error"]:
        st.error(f"Login failed — {result['error']}")
        return
    _persist_session(result)
    _go_to_dashboard()


def _handle_sign_up(email: str, password: str, confirm: str) -> None:
    if not email or not password or not confirm:
        st.error("All fields are required.")
        return
    if password != confirm:
        st.error("Passwords do not match.")
        return
    if len(password) < 6:
        st.error("Password must be at least 6 characters.")
        return
    with st.spinner("Creating your account…"):
        result = sign_up(email, password)
    if result["error"]:
        st.error(f"Sign-up failed — {result['error']}")
        return
    if result["session"] is None:
        st.success("Account created! Check your inbox to confirm, then log in.")
    else:
        _persist_session(result)
        _go_to_dashboard()


def _handle_reset(email: str) -> None:
    if not email:
        st.error("Please enter your email address.")
        return
    with st.spinner("Sending reset link…"):
        result = reset_password(email)
    if result["error"]:
        st.error(f"Could not send reset email — {result['error']}")
        return
    st.success("✅ Password reset link sent! Check your inbox.")


# ─── Dialog CSS (injected inside the dialog) ─────────────────────────────────

_DIALOG_CSS = """
<style>
/* ── Backdrop: heavy blur + dark vignette ── */
@keyframes fs-backdrop-in {
    from { opacity: 0; }
    to   { opacity: 1; }
}
@keyframes fs-dialog-in {
    from { opacity: 0; transform: translateY(28px) scale(0.96); }
    to   { opacity: 1; transform: translateY(0)    scale(1);    }
}

[data-testid="stDialog"] > div {
    background: rgba(8,5,3,0.62) !important;
    backdrop-filter: blur(22px) saturate(160%) !important;
    -webkit-backdrop-filter: blur(22px) saturate(160%) !important;
    animation: fs-backdrop-in 0.25s ease forwards;
}
[data-testid="stDialog"] [data-testid="stModalDialog"] {
    background: #221c18 !important;
    border: 1px solid rgba(244,236,220,0.09) !important;
    border-radius: 22px !important;
    box-shadow: 0 48px 96px rgba(0,0,0,0.7), 0 0 0 1px rgba(244,236,220,0.04) !important;
    animation: fs-dialog-in 0.32s cubic-bezier(0.34, 1.46, 0.64, 1) forwards;
}
/* Gold shimmer line at top of dialog */
[data-testid="stDialog"] [data-testid="stModalDialog"]::before {
    content: '';
    position: absolute; top: 0; left: 8%; right: 8%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(201,168,96,0.65), transparent);
}
[data-testid="stDialog"] h2,
[data-testid="stDialog"] [data-testid="stDialogTitle"],
[data-testid="stDialog"] header { display: none !important; }

/* Inputs inside dialog — sky-blue focus */
[data-testid="stDialog"] label { color: #A89880 !important; font-size: 0.75rem !important; font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; }
[data-testid="stDialog"] input {
    background: #2c2318 !important;
    border-color: rgba(244,236,220,0.1) !important;
    color: #F4ECDC !important; border-radius: 10px !important;
}
[data-testid="stDialog"] input:focus {
    border-color: rgba(122,160,196,0.6) !important;
    box-shadow: 0 0 0 3px rgba(122,160,196,0.15) !important;
}

/* Logo block */
.auth-dialog-logo { text-align: center; padding: 0.5rem 0 1rem; }
.auth-dialog-logo .icon {
    font-size: 2.2rem; display: block; margin-bottom: 0.4rem;
    filter: drop-shadow(0 0 18px rgba(201,168,96,0.7));
}
.auth-dialog-logo h3 {
    font-size: 2.2rem !important; font-weight: 900 !important;
    color: #F4ECDC !important; letter-spacing: -1px !important;
    margin: 0 0 0.2rem !important;
}
.auth-dialog-logo .sub {
    font-size: 0.65rem; color: #6B5C50; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.16em;
}

/* Divider */
.auth-divider {
    height: 1px; margin: 0.75rem 0 1rem;
    background: linear-gradient(to right, transparent, rgba(201,168,96,0.2), transparent);
}

/* Forgot password button — plain text link style */
[data-testid="stDialog"] [data-testid="stButton"]:has(button[kind="secondary"]),
[data-testid="stDialog"] div:has(> button[data-testid="baseButton-secondary"]) { text-align: left; }
[data-testid="stDialog"] button[data-testid="baseButton-secondary"][key="forgot_pw"],
[data-testid="stDialog"] .stButton:has(button[key="forgot_pw"]) button {
    background: none !important; border: none !important;
    box-shadow: none !important; color: #7AA0C4 !important;
    font-size: 0.78rem !important; font-weight: 500 !important;
    padding: 0 0.1rem !important; min-height: unset !important;
    text-decoration: underline !important; text-underline-offset: 3px !important;
}
[data-testid="stDialog"] .stButton:has(button[key="forgot_pw"]) button:hover {
    color: #A8C4DC !important; transform: none !important; box-shadow: none !important;
}

/* Footer note */
.auth-footer {
    text-align: center; margin-top: 0.75rem;
    font-size: 0.72rem; color: #6B5C50;
}

/* Hide "Press Enter to submit form" hint on password field */
[data-testid="InputInstructions"] { display: none !important; }

/* Tab active = gold */
[data-testid="stDialog"] .stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #C9A860 0%, #A88040 100%) !important;
    color: #1a1512 !important;
    box-shadow: 0 4px 14px rgba(201,168,96,0.35) !important;
}
[data-testid="stDialog"] .stTabs [data-baseweb="tab"] {
    color: #6B5C50 !important;
}
</style>
"""


# ─── Auth dialog ──────────────────────────────────────────────────────────────

@st.dialog(" ", width="small")
def show_auth_dialog() -> None:
    _init_session()
    # Default to login if auth_mode isn't explicitly set (prevents reset mode
    # persisting across dialog opens when user closes without completing reset)
    if not st.session_state.get("auth_mode"):
        st.session_state.auth_mode = "login"
    st.markdown(_DIALOG_CSS, unsafe_allow_html=True)

    # Brand header
    st.markdown(
        """
        <div class="auth-dialog-logo">
            <h3>Expenger</h3>
            <div class="sub">AI Expense Manager</div>
        </div>
        <div class="auth-divider"></div>
        """,
        unsafe_allow_html=True,
    )

    # ── Reset password mode ────────────────────────────────────────────────────
    if st.session_state.get("auth_mode") == "reset":
        st.markdown(
            "<p style='font-size:0.85rem;color:#A89880;"
            "margin-bottom:1rem'>Enter your email and we'll send you a reset link.</p>",
            unsafe_allow_html=True,
        )
        with st.form("reset_form"):
            email     = st.text_input("Email", placeholder="you@example.com", key="reset_email")
            submitted = st.form_submit_button("Send Reset Link →", use_container_width=True)
        if submitted:
            _handle_reset(email)

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("← Back to Log In", key="back_to_login", use_container_width=False):
            st.session_state.auth_mode = "login"
            st.session_state._auth_trigger = True
            st.rerun(scope="app")

        st.markdown(
            "<div class='auth-footer'>🔒 Secured by Supabase Auth · Data never shared</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Normal mode: Log In / Sign Up tabs ────────────────────────────────────
    tab_login, tab_signup = st.tabs(["  Log In  ", "  Sign Up  "])

    with tab_login:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            email    = st.text_input("Email",    placeholder="you@example.com", key="li_email")
            password = st.text_input("Password", placeholder="••••••••", type="password", key="li_pass")
            st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Log In →", use_container_width=True)
        if submitted:
            _handle_sign_in(email, password)

        # Forgot password link
        if st.button("Forgot password?", key="forgot_pw"):
            st.session_state.auth_mode = "reset"
            st.session_state._auth_trigger = True
            st.rerun(scope="app")

    with tab_signup:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        with st.form("signup_form"):
            email   = st.text_input("Email",            placeholder="you@example.com",   key="su_email")
            pw      = st.text_input("Password",         placeholder="Min. 6 characters", type="password", key="su_pass")
            st.caption("🔒 Password must contain at least 6 characters, including: lowercase, uppercase, numbers, and special characters (e.g. !@#$).")
            confirm = st.text_input("Confirm Password", placeholder="Repeat password",   type="password", key="su_confirm")
            st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Create Account →", use_container_width=True)
        if submitted:
            _handle_sign_up(email, pw, confirm)

    st.markdown(
        "<div class='auth-footer'>🔒 Secured by Supabase Auth · Data never shared</div>",
        unsafe_allow_html=True,
    )