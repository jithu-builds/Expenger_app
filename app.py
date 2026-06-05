"""
Expenger — AI Expense Manager · Streamlit entry point.

Run with:
    streamlit run app.py
"""

import streamlit as st
import extra_streamlit_components as stx
from components.session_store import set_cm

st.set_page_config(
    page_title="Expenger",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Create CookieManager ONCE per render and register it in the shared store.
set_cm(stx.CookieManager(key="expenger_cookies"))

# ─── Global CSS ────────────────────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
/*
 * Expenger design tokens
 * -----------------------------------------
 * bg-deep:      #1a1512  page background
 * bg-card:      #221c18  card / surface
 * bg-elevated:  #2c2318  raised / hover
 * accent-terra: #BD866A  primary (terracotta)
 * accent-gold:  #C9A860  numbers / highlights
 * accent-sage:  #7B9E87  positive / income
 * accent-sky:   #7AA0C4  contrast / links
 * accent-rose:  #C97B7B  over-budget / danger
 * cream-bright: #F4ECDC  headings
 * cream-mid:    #D4C4A8  body text
 * cream-muted:  #A89880  secondary
 * cream-dim:    #6B5C50  labels / disabled
 */

/* ── Base ── */
.stApp { background: #1a1512; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e1813 0%, #1a1512 100%) !important;
    border-right: 1px solid rgba(244,236,220,0.07) !important;
}
[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
[data-testid="stSidebar"] .stRadio label {
    display: flex; align-items: center; justify-content: center;
    padding: 0.75rem 1.1rem; border-radius: 12px;
    color: #6B5C50 !important; font-weight: 600; font-size: 1.05rem;
    cursor: pointer; transition: background 0.15s, color 0.15s;
    margin-bottom: 4px; border-left: none; text-align: center; gap: 0;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(201,168,96,0.1); color: #C9A860 !important;
}
[data-testid="stSidebar"] .stRadio label:has(input:checked) {
    background: rgba(201,168,96,0.12) !important;
    color: #C9A860 !important;
    box-shadow: inset 0 0 0 1px rgba(201,168,96,0.3) !important;
}
[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] {
    width: 100%; text-align: center;
}
[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
    margin: 0; line-height: 1.3; text-align: center;
}
[data-testid="stSidebar"] .stRadio input[type="radio"] { display: none !important; }
[data-testid="stSidebar"] .stRadio div[data-baseweb="radio"] { display: none !important; }
[data-testid="stSidebar"] .stRadio label > div:first-child { display: none !important; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
[data-testid="stSidebar"] .stRadio > label { display: none !important; }

/* ── Lock sidebar width — hide drag handle + fix dimensions ── */
[data-testid="stSidebarResizeHandle"],
[data-testid="stSidebarResizeHandle"] > div,
[data-testid="stSidebarResizeHandle"] * {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
    cursor: default !important;
}
/* Force fixed width so browser never enters resize zone */
[data-testid="stSidebar"] {
    min-width: 280px !important;
    max-width: 280px !important;
    width: 280px !important;
    cursor: default !important;
}
/* Neutralise any col-resize cursor on sidebar inner divs */
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {
    cursor: default !important;
}

/* ── Content area ── */
.block-container { padding: 1.75rem 2.5rem 2rem !important; max-width: 1400px; }

/* ── Typography ── */
h1 {
    font-size: 1.75rem !important; font-weight: 800 !important;
    color: #F4ECDC !important; letter-spacing: -0.5px !important;
    margin-bottom: 0.25rem !important;
}
h2 { font-size: 1.2rem !important; font-weight: 700 !important; color: #D4C4A8 !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; color: #A89880 !important; }

/* ── Metric cards — gold value, cream label, subtle top accent ── */
[data-testid="stMetric"] {
    background: #221c18;
    border: 1px solid rgba(244,236,220,0.08);
    border-top: 2px solid rgba(201,168,96,0.4);
    border-radius: 16px; padding: 1.2rem 1.4rem !important;
    transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
}
[data-testid="stMetric"]:hover {
    border-color: rgba(201,168,96,0.5);
    border-top-color: #C9A860;
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(201,168,96,0.1);
}
[data-testid="stMetricLabel"] {
    color: #6B5C50 !important; font-size: 0.75rem !important;
    font-weight: 700 !important; text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
}
[data-testid="stMetricValue"] {
    color: #C9A860 !important; font-size: 1.65rem !important;
    font-weight: 800 !important; letter-spacing: -0.5px !important;
}
[data-testid="stMetricDelta"] { color: #7B9E87 !important; font-weight: 600 !important; }
[data-testid="stMetricDelta"] svg { display: none; }

/* ── Buttons ── */
.stButton button, .stFormSubmitButton button {
    background: linear-gradient(135deg, #BD866A 0%, #89685F 100%) !important;
    color: #F4ECDC !important; border: none !important; border-radius: 10px !important;
    font-weight: 700 !important; font-size: 0.875rem !important;
    padding: 0.55rem 1.3rem !important;
    box-shadow: 0 4px 14px rgba(189,134,106,0.3) !important;
    transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s !important;
}
.stButton button:hover, .stFormSubmitButton button:hover {
    opacity: 0.9 !important; transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(201,168,96,0.35) !important;
}
/* Secondary / outline buttons via Streamlit "secondary" kind */
.stButton button[kind="secondary"] {
    background: rgba(244,236,220,0.05) !important;
    color: #D4C4A8 !important;
    border: 1px solid rgba(244,236,220,0.12) !important;
    box-shadow: none !important;
}
.stButton button[kind="secondary"]:hover {
    background: rgba(201,168,96,0.1) !important;
    color: #C9A860 !important;
    border-color: rgba(201,168,96,0.3) !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton button {
    background: rgba(201,96,96,0.1) !important; color: #C97B7B !important;
    box-shadow: none !important; border: 1px solid rgba(201,96,96,0.2) !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(201,96,96,0.2) !important;
    transform: none !important; box-shadow: none !important;
}

/* ── Inputs ── */
.stTextInput label, .stNumberInput label, .stSelectbox label, .stFileUploader label {
    color: #6B5C50 !important; font-size: 0.75rem !important;
    font-weight: 700 !important; text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
}
.stTextInput input, .stNumberInput input {
    background: #2c2318 !important;
    border: 1px solid rgba(244,236,220,0.09) !important;
    border-radius: 10px !important; color: #F4ECDC !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #7AA0C4 !important;
    box-shadow: 0 0 0 3px rgba(122,160,196,0.18) !important;
}
div[data-baseweb="select"] > div {
    background: #2c2318 !important;
    border: 1px solid rgba(244,236,220,0.09) !important;
    border-radius: 10px !important; color: #F4ECDC !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #221c18 !important;
    border: 2px dashed rgba(122,160,196,0.3) !important;
    border-radius: 16px !important; padding: 1rem !important;
    transition: border-color 0.2s !important;
}
[data-testid="stFileUploader"]:hover { border-color: rgba(122,160,196,0.55) !important; }

/* ── DataFrames ── */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(244,236,220,0.07) !important;
    border-radius: 14px !important; overflow: hidden !important;
}

/* ── Tabs ── sky-blue active ── */
.stTabs [data-baseweb="tab-list"] {
    background: #221c18 !important; border-radius: 14px !important;
    padding: 5px !important; gap: 4px !important;
    border: 1px solid rgba(244,236,220,0.07) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important; color: #6B5C50 !important;
    font-weight: 600 !important; padding: 0.45rem 1.2rem !important;
    font-size: 0.875rem !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #7AA0C4 0%, #5A80A4 100%) !important;
    color: #F4ECDC !important; box-shadow: 0 4px 14px rgba(122,160,196,0.35) !important;
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── Expanders ── */
[data-testid="stExpander"] {
    background: #221c18 !important;
    border: 1px solid rgba(244,236,220,0.07) !important;
    border-radius: 14px !important;
}
[data-testid="stExpander"] summary {
    color: #D4C4A8 !important;
}

/* ── Dividers ── */
hr { border-color: rgba(244,236,220,0.07) !important; margin: 1.5rem 0 !important; }

/* ── Chat messages ── user warm cream, assistant dark ── */
[data-testid="stChatMessage"][data-testid*="user"],
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: rgba(244,236,220,0.05) !important;
    border: 1px solid rgba(244,236,220,0.1) !important;
    border-left: 3px solid #C9A860 !important;
    border-radius: 16px !important; padding: 1rem 1.2rem !important;
    margin-bottom: 0.6rem !important;
}
[data-testid="stChatMessage"] {
    background: #221c18 !important;
    border: 1px solid rgba(244,236,220,0.07) !important;
    border-left: 3px solid #7AA0C4 !important;
    border-radius: 16px !important; padding: 1rem 1.2rem !important;
    margin-bottom: 0.6rem !important;
}
[data-testid="stChatInputTextArea"] {
    background: #2c2318 !important;
    border: 1px solid rgba(122,160,196,0.3) !important;
    border-radius: 12px !important; color: #F4ECDC !important;
}

/* ── Alerts ── colour-coded ── */
.stAlert { border-radius: 12px !important; font-size: 0.875rem !important; }
.stAlert[data-baseweb="notification"][kind="positive"],
div[data-testid="stAlert"][data-baseweb="notification"] {
    border-left: 3px solid #7B9E87 !important;
}

/* ── Caption / small text ── */
.stCaption, [data-testid="stCaptionContainer"] p {
    color: #A89880 !important;
}

/* ── Spinner ── */
.stSpinner [data-testid="stSpinner"] div,
div[data-testid="stSpinner"] > div > div { border-top-color: #C9A860 !important; }

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #7B9E87, #C9A860) !important;
    border-radius: 99px !important;
}

/* ── Info / success / warning native Streamlit boxes ── */
div[data-testid="stInfo"]    { border-left: 3px solid #7AA0C4 !important; }
div[data-testid="stSuccess"] { border-left: 3px solid #7B9E87 !important; }
div[data-testid="stWarning"] { border-left: 3px solid #C9A860 !important; }
div[data-testid="stError"]   { border-left: 3px solid #C97B7B !important; }

/* ── Hide dialog native title bar ── */
[data-testid="stDialog"] h2,
[data-testid="stDialog"] h1,
[data-testid="stDialog"] header,
[data-testid="stDialog"] [data-testid="stDialogTitle"],
[data-testid="stDialog"] [data-testid="stHeadingWithActionElements"] {
    display: none !important;
}
</style>
"""

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Kill sidebar resize handle via JS (CSS alone can't remove drag listeners) ──
st.markdown(
    """
    <script>
    (function() {
        var killHandle = function() {
            var h = document.querySelector('[data-testid="stSidebarResizeHandle"]');
            if (h) {
                h.remove();
                return true;
            }
            return false;
        };
        if (!killHandle()) {
            var obs = new MutationObserver(function(_, o) {
                if (killHandle()) o.disconnect();
            });
            obs.observe(document.documentElement, { childList: true, subtree: true });
        }
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

# ── Full-screen loading overlay ────────────────────────────────────────────────
_loader = st.empty()
_loader.markdown(
    """
    <style>
    #fs-loader {
        position: fixed; inset: 0; background: #1a1512;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        gap: 0.75rem; z-index: 99999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .fsl-icon  { font-size: 3.5rem; animation: fsl-pulse 1.6s ease-in-out infinite; }
    .fsl-title { color: #F4ECDC; font-size: 2.4rem; font-weight: 900;
                 letter-spacing: -1px; margin: 0.25rem 0 0; }
    .fsl-sub   { color: #6B5C50; font-size: 0.85rem; margin: 0 0 1.25rem; }
    .fsl-ring  {
        width: 40px; height: 40px;
        border: 3px solid rgba(201,168,96,0.2);
        border-top-color: #C9A860; border-radius: 50%;
        animation: fsl-spin 0.85s linear infinite;
    }
    @keyframes fsl-spin  { to { transform: rotate(360deg); } }
    @keyframes fsl-pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.1); } }
    </style>
    <div id="fs-loader">
        <p class="fsl-title">Expenger</p>
        <p class="fsl-sub">Loading your workspace…</p>
        <div class="fsl-ring"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    import streamlit.components.v1 as _stc_v1
    from components.auth import logout, restore_session_from_cookies
    from frontend import budgeting, chat_ai, dashboard, landing
    from backend.supabase_client import (
        exchange_code_for_session, set_recovery_session, update_user_password,
    )
except Exception as e:
    _loader.empty()
    st.error(f"Error loading dependencies: {e}")
    st.stop()

_loader.empty()


# ─── Session init ─────────────────────────────────────────────────────────────

def _init_session() -> None:
    for key, val in {
        "logged_in":    False,
        "user_id":      None,
        "user_email":   None,
        "access_token": None,
        "show_auth":    False,
        "nav_page":     "🧠  AI Insights",
    }.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─── Password reset callback ──────────────────────────────────────────────────

@st.dialog("Set New Password", width="small")
def _password_reset_dialog(code: str = "", access_token: str = "", refresh_token: str = "") -> None:
    st.markdown(
        """
        <style>
        [data-testid="stDialog"] h2 { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div style="text-align:center;padding:0.5rem 0 1.25rem">
            <span style="font-size:2rem;filter:drop-shadow(0 0 16px rgba(122,160,196,0.6))">🔑</span>
            <div style="font-size:1.3rem;font-weight:800;
                        color:#F4ECDC;margin:0.4rem 0 0.15rem;letter-spacing:-0.3px">
                Set New Password
            </div>
            <div style="font-size:0.8rem;color:#A89880">
                Choose a strong password for your Expenger account
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Establish a recovery session (run once per dialog open)
    if not st.session_state.get("_recovery_session_set"):
        with st.spinner("Verifying reset link…"):
            if code:
                # PKCE flow — exchange code for session
                result = exchange_code_for_session(code)
                session = result.get("session")
            else:
                # Implicit flow — token arrived directly in URL fragment
                result = set_recovery_session(access_token, refresh_token)
                session = result.get("session")
        if result["error"]:
            st.error(f"Reset link is invalid or expired — {result['error']}")
            if st.button("Request a new link"):
                st.query_params.clear()
                st.rerun(scope="app")
            return
        if session:
            st.session_state.access_token = session.access_token
        st.session_state._recovery_session_set = True

    with st.form("new_password_form"):
        pw      = st.text_input("New Password",     placeholder="Min. 6 characters", type="password")
        confirm = st.text_input("Confirm Password", placeholder="Repeat password",   type="password")
        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("Update Password →", use_container_width=True)

    if submitted:
        if not pw or not confirm:
            st.error("Both fields are required.")
        elif pw != confirm:
            st.error("Passwords do not match.")
        elif len(pw) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            with st.spinner("Updating password…"):
                res = update_user_password(pw)
            if res["error"]:
                st.error(f"Could not update password — {res['error']}")
            else:
                st.success("✅ Password updated! You can now log in.")
                st.session_state._recovery_session_set = False
                st.query_params.clear()


def _handle_recovery_params() -> bool:
    """Check URL for Supabase recovery params. Returns True if recovery flow is active."""
    params = st.query_params

    # PKCE flow: ?code=...
    code = params.get("code")
    if code:
        _password_reset_dialog(code=code)
        return True

    # Implicit flow: ?type=recovery&access_token=... (set by JS fragment redirect below)
    if params.get("type") == "recovery" and params.get("access_token"):
        _password_reset_dialog(
            access_token=params["access_token"],
            refresh_token=params.get("refresh_token", ""),
        )
        return True

    return False


# ─── Sidebar ──────────────────────────────────────────────────────────────────

# AI Insights first — the highlight feature of Expenger
PAGES = {
    "🧠  AI Insights": chat_ai,
    "📊  Dashboard":   dashboard,
    "💰  Budgeting":   budgeting,
}


def _render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            """
            <div style="padding:0.5rem 0.5rem 1rem;text-align:center">
                <div style="display:flex;flex-direction:column;align-items:center;gap:6px;margin-bottom:4px">
                    <div>
                        <div style="font-size:1.65rem;font-weight:900;color:#F4ECDC;
                                    letter-spacing:-0.5px">Expenger</div>
                        <div style="font-size:0.75rem;color:#6B5C50;font-weight:600;
                                    text-transform:uppercase;letter-spacing:0.07em">
                            AI Expense Manager
                        </div>
                    </div>
                </div>
                <div style="font-size:0.78rem;color:#A89880;margin-top:6px;
                            word-break:break-all">
                    {email}
                </div>
            </div>
            """.format(email=st.session_state.user_email or ""),
            unsafe_allow_html=True,
        )
        st.markdown(
            "<hr style='border-color:rgba(244,236,220,0.06);margin:0 0 0.75rem 0'>",
            unsafe_allow_html=True,
        )
        selected = st.radio("nav", list(PAGES.keys()), key="nav_page", label_visibility="collapsed")
        st.markdown("<div style='min-height:200px'></div>", unsafe_allow_html=True)
        st.markdown(
            "<hr style='border-color:rgba(244,236,220,0.06);margin:0 0 0.75rem 0'>",
            unsafe_allow_html=True,
        )
        if st.button("  Log Out", use_container_width=True):
            logout()
    return selected  # type: ignore[return-value]


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    _init_session()

    # Detect Supabase implicit-flow recovery links (#access_token=...&type=recovery).
    # Streamlit can't read URL fragments — JS reads the hash and redirects to clean query params.
    _stc_v1.html(
        """<script>
        (function() {
            var hash = window.parent.location.hash.slice(1);
            if (!hash) return;
            var p = {};
            hash.split('&').forEach(function(s) {
                var i = s.indexOf('=');
                if (i > 0) p[decodeURIComponent(s.slice(0,i))] = decodeURIComponent(s.slice(i+1));
            });
            if (p['type'] === 'recovery' && p['access_token']) {
                window.parent.location.replace(
                    '/?type=recovery'
                    + '&access_token=' + encodeURIComponent(p['access_token'])
                    + '&refresh_token=' + encodeURIComponent(p['refresh_token'] || '')
                );
            }
        })();
        </script>""",
        height=1,
    )

    # Handle Supabase password-reset callback (?code=... in URL)
    if _handle_recovery_params():
        landing.render()
        return

    # Skip cookie auto-login while the auth dialog is open or being triggered.
    # _auth_open persists across reruns until login succeeds (cleared in auth.py).
    explicit_auth = (
        st.query_params.get("show_auth") == "1"
        or st.session_state.get("_auth_open")
    )

    if not st.session_state.logged_in and not explicit_auth:
        restore_session_from_cookies()

    if not st.session_state.logged_in:
        landing.render()  # dialog is triggered from within landing
        return

    # Clear auth flags on successful login
    st.session_state.show_auth = False
    st.session_state.auth_mode = None

    page = _render_sidebar()
    PAGES[page].render()


if __name__ == "__main__":
    main()