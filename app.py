"""
app.py — Watchwise: AI-Backed Movie Suggestions
Run: streamlit run app.py
"""

import os
import time
import streamlit as st
from dotenv import load_dotenv
from letterboxd_parser import parse_letterboxd_zip, build_taste_profile, get_watched_set
from tmdb_utils import build_enrichment_summary, fetch_film_metadata, fetch_poster_and_providers
from recommender import get_recommendations, parse_rec_blocks
from db import sign_in, sign_up, sign_out, load_profile, save_profile

load_dotenv()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
TMDB_TOKEN = os.environ.get("TMDB_READ_TOKEN", "")

missing = [k for k, v in {"GEMINI_API_KEY": GEMINI_KEY, "TMDB_READ_TOKEN": TMDB_TOKEN}.items() if not v]
if missing:
    st.error(f"Missing environment variables: {', '.join(missing)}")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Watchwise",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d0d0f;
    color: #e8e2d8;
    font-family: 'DM Sans', sans-serif;
}
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden; }

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] ol,
[data-testid="stMarkdownContainer"] ul { color: #e8e2d8 !important; }
[data-testid="stMarkdownContainer"] strong { color: #fff !important; }
[data-testid="stMarkdownContainer"] em    { color: #c8c2b8 !important; }
[data-testid="stCaptionContainer"] p      { color: #888 !important; }
p, li, label { color: #e8e2d8; }
h1,h2,h3,h4  { font-family: 'Bebas Neue', sans-serif; letter-spacing: 0.06em; }

.stTextArea textarea, .stTextInput input {
    background: #1a1a20 !important; color: #e8e2d8 !important;
    border: 1px solid #2c2c38 !important; border-radius: 3px !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #d22323 !important;
    box-shadow: 0 0 0 2px rgba(210,35,35,0.15) !important;
}
.stTextArea textarea::placeholder,
.stTextInput input::placeholder { color: #555 !important; opacity:1 !important; }

[data-testid="stFileUploader"] {
    background: #1a1a20; border: 1px dashed #2c2c38;
    border-radius: 6px; padding: 4px;
}
[data-testid="stFileUploader"] button {
    background: #2a2a36 !important; color: #e8e2d8 !important;
    border: 1px solid #3a3a4a !important; border-radius: 3px !important;
    font-family: 'DM Sans', sans-serif !important; font-size: 0.85rem !important;
}
[data-testid="stFileUploader"] button:hover {
    background: #3a3a4a !important; border-color: #d22323 !important;
}
[data-testid="stFileUploader"] p,
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] span { color: #888 !important; }

.stButton > button {
    background: #d22323 !important; color: #fff !important;
    border: none !important; border-radius: 3px !important;
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 0.12em !important; font-size: 1.05rem !important;
    padding: 0.45rem 1.4rem !important;
    width: 100%; transition: background 0.2s;
}
.stButton > button:hover { background: #a81818 !important; }

.example-btn .stButton > button {
    background: transparent !important; color: #b0a898 !important;
    border: 1px solid #2c2c38 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.82rem !important; letter-spacing: 0.02em !important;
    padding: 0.3rem 0.8rem !important;
}
.example-btn .stButton > button:hover {
    background: #1e1e26 !important; border-color: #d22323 !important; color: #fff !important;
}

.ghost-btn .stButton > button {
    background: transparent !important; color: #666 !important;
    border: 1px solid #2c2c38 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.78rem !important; letter-spacing: 0.04em !important;
    padding: 0.25rem 0.8rem !important; width: auto !important;
}
.ghost-btn .stButton > button:hover {
    color: #e8e2d8 !important; border-color: #555 !important;
    background: #1a1a20 !important;
}

/* ── Auth card ── */
.auth-card {
    max-width: 420px; margin: 2rem auto;
    background: #111116; border: 1px solid #222230;
    border-radius: 10px; padding: 2rem 2.4rem;
}
.auth-title {
    font-family: 'Bebas Neue', sans-serif; font-size: 1.6rem;
    color: #fff; letter-spacing: 0.08em; margin: 0 0 0.3rem 0;
}
.auth-sub { font-size: 0.8rem; color: #555; margin-bottom: 1.4rem; }
.auth-toggle { font-size: 0.8rem; color: #555; text-align: center; margin-top: 1rem; }
.auth-toggle a { color: #d22323; cursor: pointer; }

.ww-header { text-align: center; padding: 2rem 0 1rem; }
.ww-logo {
    font-family: 'Bebas Neue', sans-serif; font-size: 5rem;
    line-height:1; color:#fff; letter-spacing:0.08em;
    text-shadow: 0 0 60px rgba(210,35,35,0.35); margin:0;
}
.ww-tagline {
    font-size:0.8rem; letter-spacing:0.22em;
    text-transform:uppercase; color:#555; margin-top:4px;
}
.rec-dot {
    display:inline-block; width:9px; height:9px;
    background:#d22323; border-radius:50%;
    box-shadow:0 0 10px #d22323; margin-left:2px; vertical-align:middle;
}

.profile-bar {
    background: #111116; border: 1px solid #222230;
    border-radius: 8px; padding: 1rem 1.8rem;
    margin-bottom: 1.5rem;
    display: flex; align-items: center; gap: 1.5rem;
    flex-wrap: wrap;
}
.profile-bar-name {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.5rem; color: #fff; margin: 0; letter-spacing: 0.06em;
}
.profile-bar-sub { font-size: 0.75rem; color: #666; }
.profile-bar-sub span { color: #d22323; font-weight:600; }
.list-pill {
    display:inline-block; background:#1f1f28; border:1px solid #2c2c38;
    border-radius:3px; padding:2px 7px; font-size:0.72rem; color:#999; margin:2px;
}

[data-testid="stExpander"] summary {
    background: #16161c !important; border: 1px solid #2a2a32 !important;
    border-radius: 4px !important;
}
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary svg { color: #999 !important; fill: #999 !important; }

.label {
    font-family: 'Bebas Neue', sans-serif; font-size: 0.9rem;
    letter-spacing: 0.18em; color: #d22323;
    text-transform: uppercase; margin-bottom: 4px;
}

@keyframes ww-pulse {
    0%,80%,100% { transform:scale(0.5); opacity:0.25; }
    40%         { transform:scale(1.0); opacity:1; }
}
.ww-loader { display:flex; gap:14px; justify-content:center; padding:3.5rem 0; }
.ww-dot {
    width:16px; height:16px; background:#d22323; border-radius:50%;
    animation: ww-pulse 1.3s infinite ease-in-out;
}
.ww-dot:nth-child(1){animation-delay:0s}
.ww-dot:nth-child(2){animation-delay:0.2s}
.ww-dot:nth-child(3){animation-delay:0.4s}
.ww-loader-label {
    text-align:center; font-size:0.78rem; color:#555;
    letter-spacing:0.12em; text-transform:uppercase; padding-bottom:2rem;
}

.recs-empty {
    background:#13131a; border:1px solid #1e1e26;
    border-radius:5px; padding:3.5rem 1rem; text-align:center;
}
.recs-empty-title { font-family:'Bebas Neue',sans-serif; font-size:2rem; color:#2a2a32; margin:0; }
.recs-empty-sub   { font-size:0.82rem; color:#444; margin-top:6px; }

hr { border-color: #1e1e26; }
.stProgress > div > div { background: #d22323 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
defaults = {
    # Auth
    "user_email":             None,
    "auth_mode":              "login",   # "login" | "signup"
    # Profile
    "parsed_data":            None,
    "enriched_films":         None,
    "imdb_summary":           None,
    "taste_profile":          None,
    "profile_meta":           {},
    # Recs
    "recommendations":        None,
    "replaced":               [],
    # UI
    "zip_loaded":             False,
    "pending_query":          "",
    "auto_run":               False,
    "profile_loaded_from_db": False,
    "skip_db_load":           False,
    "unsaved":                False,
    "auth_open":              False,  # toggles the sign-in panel
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
#  DB LOAD — once per session if signed in
# ─────────────────────────────────────────────────────────────────────────────
user_email = st.session_state.user_email

if user_email and not st.session_state.profile_loaded_from_db and not st.session_state.skip_db_load:
    try:
        saved = load_profile(user_email)
        if saved and saved.get("taste_profile"):
            st.session_state.taste_profile  = saved["taste_profile"]
            st.session_state.imdb_summary   = saved["imdb_summary"]
            st.session_state.enriched_films = saved["enriched_films"]
            st.session_state.profile_meta   = saved.get("profile_meta") or {}
            st.session_state.zip_loaded     = True
    except Exception:
        pass
    st.session_state.profile_loaded_from_db = True

EXAMPLES = [
    "Foreign murder mystery under 90 minutes",
    "Slow-burn psychological horror, not gore",
    "Female-directed drama from the last 10 years",
    "Underrated 80s sci-fi I've probably never heard of",
    "Something funny but genuinely dark",
    "A great documentary to watch tonight",
]

LOADER_HTML = """
<div class="ww-loader">
  <div class="ww-dot"></div><div class="ww-dot"></div><div class="ww-dot"></div>
</div>
<p class="ww-loader-label">Finding your next favorite film…</p>
"""

# ─────────────────────────────────────────────────────────────────────────────
#  HELPER
# ─────────────────────────────────────────────────────────────────────────────
def run_recommendations(query: str, loader_slot):
    loader_slot.markdown(LOADER_HTML, unsafe_allow_html=True)
    try:
        watched_set = get_watched_set(st.session_state.parsed_data) \
            if st.session_state.parsed_data else None
        recs, replaced = get_recommendations(
            query=query.strip(),
            taste_profile=st.session_state.taste_profile,
            imdb_summary=st.session_state.imdb_summary,
            watched_set=watched_set,
            conversation_history=st.session_state.get("chat_history") or None,
            api_key=GEMINI_KEY,
        )
        # Append this exchange to chat history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        st.session_state.chat_history.append({"role": "user",      "content": query.strip()})
        st.session_state.chat_history.append({"role": "assistant", "content": recs})
        st.session_state.recommendations = recs
        st.session_state.replaced        = replaced
    except Exception as e:
        loader_slot.empty()
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            import re
            delay = re.search(r"retryDelay.*?(\d+)s", err)
            delay_str = f" Try again in {delay.group(1)} seconds." if delay else ""
            st.warning(f"⚠️ Gemini quota reached.{delay_str}")
        else:
            st.error(f"Gemini error: {e}")
        return
    loader_slot.empty()

# ─────────────────────────────────────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ww-header">
  <p class="ww-logo">WATCHWISE<span class="rec-dot"></span></p>
  <p class="ww-tagline">AI-Backed Movie Suggestions</p>
</div>
""", unsafe_allow_html=True)

# ── Top-right: auth controls ──────────────────────────────────────────────────
if user_email:
    ucol1, ucol2 = st.columns([6, 1])
    with ucol1:
        st.markdown(
            f'<p style="text-align:right;font-size:0.75rem;color:#555;margin:0">{user_email}</p>',
            unsafe_allow_html=True,
        )
    with ucol2:
        if st.button("Sign out", key="signout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
else:
    _, rbtn = st.columns([6, 1])
    with rbtn:
        st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
        if st.button("Sign in", key="open_auth"):
            st.session_state.auth_open = not st.session_state.auth_open
            st.rerun()

# ── Auth panel (shown when Sign in is clicked) ────────────────────────────────
if not user_email and st.session_state.auth_open:
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        mode = st.session_state.auth_mode

        if mode == "login":
            #st.markdown('<div class="auth-card">', unsafe_allow_html=True)
            st.markdown('<p class="auth-title">Sign In</p>', unsafe_allow_html=True)
            st.markdown('<p class="auth-sub">Welcome back — sign in to load your saved taste profile.</p>', unsafe_allow_html=True)
            email    = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Sign In", key="do_login"):
                if not email or not password:
                    st.error("Please enter your email and password.")
                else:
                    result = sign_in(email.strip(), password)
                    if result["error"]:
                        st.error(result["error"])
                    else:
                        st.session_state.user_email = result["user"].email
                        st.session_state.auth_open  = False
                        # If they uploaded a ZIP before signing in, save it now
                        if st.session_state.get("taste_profile") and st.session_state.get("profile_meta"):
                            try:
                                save_profile(
                                    email=result["user"].email,
                                    username=st.session_state.profile_meta.get("username", ""),
                                    taste_profile=st.session_state.taste_profile,
                                    enriched_films=st.session_state.enriched_films or [],
                                    imdb_summary=st.session_state.imdb_summary or "",
                                    profile_meta=st.session_state.profile_meta,
                                )
                            except Exception:
                                pass
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="ghost-btn" style="max-width:420px;margin:0.5rem auto">', unsafe_allow_html=True)
            if st.button("Create Account →", key="switch_to_signup"):
                st.session_state.auth_mode = "signup"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        else:  # signup
            st.markdown('<div class="auth-card">', unsafe_allow_html=True)
            st.markdown('<p class="auth-title">Create Account</p>', unsafe_allow_html=True)
            st.markdown('<p class="auth-sub">Free forever. Your Letterboxd data stays private.</p>', unsafe_allow_html=True)
            email     = st.text_input("Email", key="signup_email")
            password  = st.text_input("Password", type="password", key="signup_password", help="At least 6 characters.")
            password2 = st.text_input("Confirm password", type="password", key="signup_password2")
            if st.button("Create Account", key="do_signup"):
                if not email or not password:
                    st.error("Please fill in all fields.")
                elif password != password2:
                    st.error("Passwords don't match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    result = sign_up(email.strip(), password)
                    if result["error"]:
                        st.error(result["error"])
                    else:
                        st.session_state.user_email = result["user"].email
                        st.session_state.auth_open  = False
                        st.session_state.profile_loaded_from_db = True  # nothing in DB yet for new account
                        # If they uploaded a ZIP before signing up, save it now
                        if st.session_state.get("taste_profile") and st.session_state.get("profile_meta"):
                            try:
                                save_profile(
                                    email=result["user"].email,
                                    username=st.session_state.profile_meta.get("username", ""),
                                    taste_profile=st.session_state.taste_profile,
                                    enriched_films=st.session_state.enriched_films or [],
                                    imdb_summary=st.session_state.imdb_summary or "",
                                    profile_meta=st.session_state.profile_meta,
                                )
                            except Exception:
                                pass
                        st.success("Account created! Welcome to Watchwise.")
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="ghost-btn" style="max-width:420px;margin:0.5rem auto">', unsafe_allow_html=True)
            if st.button("← Back to Sign In", key="switch_to_login"):
                st.session_state.auth_mode = "login"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  UPLOAD / PROFILE
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.zip_loaded:
    with st.expander("📦  Upload your Letterboxd Export", expanded=False):
        st.caption("letterboxd.com → Settings → Import & Export → Export Your Data")
        uploaded_zip = st.file_uploader("ZIP", type=["zip"], label_visibility="collapsed")
        load_btn = st.button("⚙️  Parse & Enrich Profile")

    if load_btn:
        if not uploaded_zip:
            st.error("Please upload your Letterboxd ZIP first.")
        else:
            with st.spinner("Parsing your Letterboxd export…"):
                try:
                    data = parse_letterboxd_zip(uploaded_zip)
                    st.session_state.parsed_data = data
                except Exception as e:
                    st.error(f"ZIP parse error: {e}")
                    st.stop()

            data     = st.session_state.parsed_data
            ratings  = data.get("ratings", [])
            enriched = []
            hits     = 0

            if ratings:
                n        = min(100, len(ratings))
                progress = st.progress(0, text=f"Fetching TMDB data for {n} films…")
                seen_set = set()
                idx      = 0
                for film in ratings:
                    if idx >= n:
                        break
                    name = film["name"]
                    year = film["year"]
                    if name.lower() in seen_set:
                        continue
                    seen_set.add(name.lower())
                    meta     = fetch_film_metadata(name, year, TMDB_TOKEN)
                    combined = {"title": name, "year": year, "rating": film.get("rating")}
                    if meta:
                        hits += 1
                        combined.update(meta)
                    enriched.append(combined)
                    idx += 1
                    progress.progress(idx / n, text=f"TMDB ({idx}/{n}): {name}…")
                    time.sleep(0.05)
                progress.empty()

            profile = data["profile"]
            lists   = data["lists"]
            profile_meta = {
                "given_name":      profile.get("given_name", ""),
                "family_name":     profile.get("family_name", ""),
                "username":        profile.get("username", ""),
                "ratings_count":   len(ratings),
                "watched_count":   len(data.get("watched", [])),
                "watchlist_count": len(data.get("watchlist", [])),
                "list_names":      list(lists.keys())[:8],
            }

            st.session_state.enriched_films  = enriched
            st.session_state.imdb_summary    = build_enrichment_summary(enriched)
            st.session_state.taste_profile   = build_taste_profile(data, enriched)
            st.session_state.profile_meta    = profile_meta
            st.session_state.zip_loaded      = True
            st.session_state.skip_db_load    = False
            st.session_state.recommendations = None

            st.session_state.unsaved = True   # prompt user to save
            st.rerun()

else:
    # Profile bar
    if st.session_state.parsed_data:
        data    = st.session_state.parsed_data
        profile = data["profile"]
        username       = profile.get("username") or profile.get("given_name") or "User"
        name_str       = " ".join(filter(None, [profile.get("given_name"), profile.get("family_name")])) or username
        ratings_count  = len(data["ratings"])
        watched_count  = len(data["watched"])
        watchlist_count = len(data["watchlist"])
        list_names     = list(data["lists"].keys())[:8]
    else:
        meta           = st.session_state.profile_meta or {}
        username       = meta.get("username") or meta.get("given_name") or "User"
        name_str       = " ".join(filter(None, [meta.get("given_name"), meta.get("family_name")])) or username
        ratings_count  = meta.get("ratings_count", 0)
        watched_count  = meta.get("watched_count", 0)
        watchlist_count = meta.get("watchlist_count", 0)
        list_names     = meta.get("list_names", [])

    pills_html = " ".join(
        f'<span class="list-pill">{n.replace("-"," ").title()}</span>'
        for n in list_names
    ) if list_names else ""

    st.markdown(f"""
    <div class="profile-bar">
      <p class="profile-bar-name">{name_str}</p>
      <p class="profile-bar-sub">@{username} &nbsp;·&nbsp;
        <span>{ratings_count}</span> rated &nbsp;·&nbsp;
        <span>{watched_count}</span> watched &nbsp;·&nbsp;
        <span>{watchlist_count}</span> watchlist
      </p>
      <div style="margin-top:4px">{pills_html}</div>
    </div>
    """, unsafe_allow_html=True)

    bcol1, bcol2 = st.columns([1, 1])
    with bcol1:
        if st.button("↺  Upload a different file", key="reupload"):
            for k in ["parsed_data","enriched_films","imdb_summary","taste_profile",
                      "profile_meta","recommendations","replaced"]:
                st.session_state[k] = [] if k == "replaced" else ({} if k == "profile_meta" else None)
            st.session_state.zip_loaded             = False
            st.session_state.profile_loaded_from_db = True
            st.session_state.skip_db_load           = True
            st.session_state.unsaved                = False
            st.rerun()
    with bcol2:
        if user_email and st.session_state.get("unsaved"):
            if st.button("💾  Save to Profile", key="save_profile_btn"):
                try:
                    save_profile(
                        email=user_email,
                        username=st.session_state.profile_meta.get("username", ""),
                        taste_profile=st.session_state.taste_profile,
                        enriched_films=st.session_state.enriched_films or [],
                        imdb_summary=st.session_state.imdb_summary or "",
                        profile_meta=st.session_state.profile_meta,
                    )
                    st.session_state.unsaved = False
                    st.success("✓ Saved to your account!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        elif user_email and not st.session_state.get("unsaved"):
            st.caption("✓ Saved to your account")
        elif not user_email and st.session_state.get("unsaved"):
            st.caption("Sign in to save your profile")

st.markdown("<hr>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TWO-COLUMN LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
left, right = st.columns([2, 3], gap="large")
loader_slot = right.empty()

with left:
    if st.session_state.get("chat_history"):
        st.markdown('<p class="label">Anything else you want me to consider?</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="label">What are you looking for?</p>', unsafe_allow_html=True)

    query = st.text_area(
        "query",
        value=st.session_state.pending_query,
        placeholder=(
            'e.g. "Find me a foreign murder mystery under 90 minutes"\n\n'
            '"Something slow-burn and atmospheric for a rainy night"\n\n'
            '"A funny horror-comedy I can watch with my roommate"'
        ),
        height=140,
        label_visibility="collapsed",
        key="query_box",
    )

    in_convo = bool(st.session_state.get("chat_history"))

    if in_convo:
        ecol1, ecol2 = st.columns([2, 1])
        with ecol1:
            if st.button("↩  Enter", key="enter_followup"):
                if query.strip():
                    st.session_state.pending_query = ""
                    st.session_state.auto_run      = False
                    run_recommendations(query, loader_slot)
                    st.rerun()
        with ecol2:
            if st.button("✕  Start Over", key="start_over"):
                st.session_state.recommendations = None
                st.session_state.replaced        = []
                st.session_state["chat_history"] = []
                st.rerun()
    else:
        go = st.button("🎬  Get Recommendations", key="get_recs")
        if go and query.strip():
            st.session_state.pending_query = ""
            st.session_state.auto_run      = False
            run_recommendations(query, loader_slot)
            st.rerun()

    st.markdown("---")

    if st.session_state.recommendations and st.session_state.zip_loaded:
        _, taste_note = parse_rec_blocks(st.session_state.recommendations)
        if taste_note:
            st.markdown(taste_note)
    else:
        if st.session_state.recommendations:
            st.markdown("""
            <style>
            @media (max-width: 768px) { .examples-block { display: none !important; } }
            </style>
            """, unsafe_allow_html=True)
        st.markdown('<div class="examples-block">', unsafe_allow_html=True)
        st.markdown('<p class="label" style="font-size:0.75rem">Quick examples</p>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, ex in enumerate(EXAMPLES):
            with cols[i % 2]:
                st.markdown('<div class="example-btn">', unsafe_allow_html=True)
                if st.button(ex, key=f"ex__{ex}"):
                    st.session_state.pending_query = ex
                    st.session_state.auto_run      = True
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.auto_run and st.session_state.pending_query:
    run_query = st.session_state.pending_query
    st.session_state.auto_run      = False
    st.session_state.pending_query = ""
    run_recommendations(run_query, loader_slot)
    st.rerun()

with right:
    st.markdown('<p class="label">Recommendations</p>', unsafe_allow_html=True)

    if st.session_state.recommendations:
        blocks, taste_note = parse_rec_blocks(st.session_state.recommendations)

        # Conversation history: show prior queries as collapsed pills
        history = st.session_state.get("chat_history", [])
        prior_queries = [m["content"] for m in history if m["role"] == "user"][:-1]
        if prior_queries:
            st.markdown(
                '<p style="font-size:0.72rem;color:#555;margin-bottom:4px">Previous queries:</p>',
                unsafe_allow_html=True,
            )
            pills = " ".join(
                f'<span style="background:#1a1a20;border:1px solid #2c2c38;border-radius:3px;'
                f'padding:2px 8px;font-size:0.72rem;color:#888;margin:2px;display:inline-block">{q}</span>'
                for q in prior_queries
            )
            st.markdown(pills, unsafe_allow_html=True)
            st.markdown("<hr style='border-color:#1e1e26;margin:0.5rem 0'>", unsafe_allow_html=True)

        for block in blocks:
            try:
                result     = fetch_poster_and_providers(block["title"], block["year"], TMDB_TOKEN)
                poster_url = result["poster_url"]
                providers  = result["providers"]
            except Exception:
                poster_url = None
                providers  = []
            col_img, col_text = st.columns([1, 4], gap="medium")
            with col_img:
                if poster_url:
                    st.markdown(
                        f'<img src="{poster_url}" style="width:100%;border-radius:4px;">',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div style="background:#1e1e26;border-radius:4px;'
                        'aspect-ratio:2/3;display:flex;align-items:center;'
                        'justify-content:center;color:#444;font-size:1.5rem;">🎬</div>',
                        unsafe_allow_html=True,
                    )
                # Streaming provider logos
                if providers:
                    logos_html = "".join(
                        f'<img src="{p["logo_url"]}" title="{p["name"]}" '
                        f'style="width:24px;height:24px;border-radius:4px;margin:2px" />' if p["logo_url"]
                        else f'<span style="font-size:0.65rem;color:#888">{p["name"]}</span>'
                        for p in providers[:6]
                    )
                    st.markdown(
                        f'<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:2px">{logos_html}</div>',
                        unsafe_allow_html=True,
                    )
            with col_text:
                st.markdown(block["body"])
            st.markdown("<hr style='border-color:#1e1e26;margin:0.4rem 0'>",
                        unsafe_allow_html=True)

        if st.session_state.get("replaced"):
            replaced_str = ", ".join(t.title() for t in st.session_state.replaced)
            st.info(f"♻️ Replaced already-seen film(s): {replaced_str}")


    else:
        st.markdown("""
        <div class="recs-empty">
          <p class="recs-empty-title">LIGHTS · CAMERA · ASK</p>
          <p class="recs-empty-sub">Type a query or pick an example on the left,
          then hit <strong>Get Recommendations</strong>.</p>
        </div>
        """, unsafe_allow_html=True)

if st.session_state.taste_profile:
    with st.expander("📄 View taste profile sent to Gemini"):
        st.code(st.session_state.taste_profile, language=None)
if st.session_state.imdb_summary:
    with st.expander("🎞️ TMDB metadata summary"):
        st.code(st.session_state.imdb_summary, language=None)