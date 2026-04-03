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
import extra_streamlit_components as stx
from db import sign_in, sign_up, sign_out, load_profile, save_profile, set_profile_public, get_public_profile, search_profiles, get_session_from_tokens

load_dotenv()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
TMDB_READ_TOKEN = os.environ.get("TMDB_READ_TOKEN", "")

missing = [k for k, v in {"GEMINI_API_KEY": GEMINI_KEY, "TMDB_READ_TOKEN": TMDB_READ_TOKEN}.items() if not v]
if missing:
    st.error(f"Missing environment variables: {', '.join(missing)}")
    st.stop()

BASE_URL = os.environ.get("WATCHWISE_URL", "").rstrip("/")
if not BASE_URL:
    try:
        _host = st.context.headers.get("host", "")
        BASE_URL = f"https://{_host}" if _host and "localhost" not in _host else "http://localhost:8501"
    except Exception:
        BASE_URL = "http://localhost:8501"
BASE_URL = BASE_URL.rstrip("/")

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Watchwise",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Cookie manager — must be instantiated before any other rendering
cookie_manager = stx.CookieManager(key="ww_cookies")

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

/* Sign out as a text link */
div:has(> [data-testid="stButton"] > button[kind="primary"]:not([id*="home_nav"])):has(+ div + div p) button,
[data-testid="stButton"]:has(button[kind="primary"]) + * {
    display: none;
}
.signout-link .stButton > button {
    background: transparent !important;
    color: #555 !important;
    border: none !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.03em !important;
    padding: 0 0 !important;
    width: auto !important;
    text-decoration: underline !important;
    text-align: right !important;
    min-height: 0 !important;
    height: auto !important;
}
.signout-link .stButton > button:hover {
    color: #d22323 !important;
    background: transparent !important;
}

.search-result-btn .stButton > button {
    background: transparent !important; color: #e8e2d8 !important;
    border: none !important; border-bottom: 1px solid #1e1e26 !important;
    border-radius: 0 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important; letter-spacing: 0.01em !important;
    padding: 0.5rem 0.8rem !important;
    text-align: left !important; width: 100% !important;
}
.search-result-btn .stButton > button:hover {
    background: #1a1a20 !important; color: #fff !important;
    border-bottom-color: #2c2c38 !important;
}

/* Home button — red but DM Sans not Bebas */
[data-testid="stButton"][id*="home_nav"] > button,
div:has(> [data-testid="stButton"] button[kind="secondary"]#home_nav) button {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.04em !important;
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
    "loading":                False,
    "do_api":                 False,
    "profile_loaded_from_db": False,
    "skip_db_load":           False,
    "unsaved":                False,
    "auth_open":              False,
    "search_open":            False,
    "search_key":             0,
    # Sharing
    "profile_is_public":      True,
    "profile_slug":           None,
    # Watch Together
    "friend_profile":         None,   # dict with taste_profile, username, meta
    "watch_together":         False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Cookie helpers ────────────────────────────────────────────────────────────
def save_auth_cookie(access_token: str, refresh_token: str, email: str):
    """Persist session tokens in browser cookies (30-day expiry)."""
    import datetime
    exp = datetime.datetime.now() + datetime.timedelta(days=30)
    cookie_manager.set("ww_access_token",  access_token,  expires_at=exp)
    cookie_manager.set("ww_refresh_token", refresh_token, expires_at=exp)
    cookie_manager.set("ww_email",         email,         expires_at=exp)

def clear_auth_cookie():
    for name in ("ww_access_token", "ww_refresh_token", "ww_email"):
        try:
            cookie_manager.delete(name)
        except Exception:
            pass

# ── Restore session from cookie on every page load ────────────────────────────
if not st.session_state.user_email:
    _cat = cookie_manager.get("ww_access_token")
    _crt = cookie_manager.get("ww_refresh_token")
    if _cat and _crt:
        try:
            result = get_session_from_tokens(_cat, _crt)
            if result["user"]:
                st.session_state.user_email = result["user"].email
        except Exception:
            clear_auth_cookie()

# ─────────────────────────────────────────────────────────────────────────────
#  DB LOAD — once per session if signed in
# ─────────────────────────────────────────────────────────────────────────────
user_email = st.session_state.user_email

if user_email and not st.session_state.profile_loaded_from_db and not st.session_state.skip_db_load:
    try:
        saved = load_profile(user_email)
        if saved and saved.get("taste_profile"):
            st.session_state.taste_profile       = saved["taste_profile"]
            st.session_state.imdb_summary        = saved["imdb_summary"]
            st.session_state.enriched_films      = saved["enriched_films"]
            st.session_state.profile_meta        = saved.get("profile_meta") or {}
            st.session_state.profile_is_public   = saved.get("is_public", False)
            st.session_state.profile_slug        = saved.get("slug")
            st.session_state.zip_loaded          = True
    except Exception:
        pass
    st.session_state.profile_loaded_from_db = True

# ── Handle signout query param ────────────────────────────────────────────────
if st.query_params.get("signout"):
    clear_auth_cookie()
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.query_params.clear()
    st.rerun()

EXAMPLES = [
    "A romantic comedy with heart",
    "Foreign murder mystery under 90 minutes",
    "Female-directed drama from the last 10 years",
    "Underrated 80s sci-fi I've probably never heard of",
    "A great documentary to watch tonight",
    "Slow-burn psychological horror, not gore",
]

LOADER_HTML = """
<div class="ww-loader">
  <div class="ww-dot"></div><div class="ww-dot"></div><div class="ww-dot"></div>
</div>
<p class="ww-loader-label">Finding your next favorite film…</p>
"""

# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def parse_and_enrich_zip(uploaded_zip):
    """Parse a Letterboxd ZIP, enrich with TMDB, and store in session state.
    Returns True on success, False on parse error."""
    with st.spinner("Parsing your Letterboxd export…"):
        try:
            data = parse_letterboxd_zip(uploaded_zip)
            st.session_state.parsed_data = data
        except Exception as e:
            st.error(f"ZIP parse error: {e}")
            return False

    data    = st.session_state.parsed_data
    ratings = data.get("ratings", [])
    enriched, hits = [], 0

    if ratings:
        n        = min(100, len(ratings))
        progress = st.progress(0, text=f"Fetching TMDB data for {n} films…")
        seen_set, idx = set(), 0
        for film in ratings:
            if idx >= n:
                break
            name, year = film["name"], film["year"]
            if name.lower() in seen_set:
                continue
            seen_set.add(name.lower())
            meta     = fetch_film_metadata(name, year, TMDB_READ_TOKEN)
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
    return True


def run_recommendations(query: str, loader_slot, friend_taste_profile: str | None = None):
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
            friend_taste_profile=friend_taste_profile,
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
#  NAVBAR  (single row, renders on ALL pages before st.stop)
# ─────────────────────────────────────────────────────────────────────────────
_display_name = (
    st.session_state.profile_slug
    or (st.session_state.profile_meta or {}).get("username")
    or user_email or ""
)
shared_slug_check = st.query_params.get("u")

if user_email:
    _logo_col, _search_col, _auth_col = st.columns([1.2, 2.5, 2])
else:
    _logo_col, _, _btn_col = st.columns([1.2, 3.5, 0.8])

with _logo_col:
    _back = f"← @{shared_slug_check}" if shared_slug_check else ""
    st.markdown(
        f'<a href="{BASE_URL}" target="_self" style="text-decoration:none">'
        f'<span style="font-family:\'Bebas Neue\',sans-serif;font-size:2.2rem;'
        f'letter-spacing:0.08em;color:#fff;line-height:1">'
        f'WATCHWISE<span class="rec-dot" style="width:11px;height:11px"></span>'
        f'</span></a>',
        unsafe_allow_html=True,
    )

if user_email:
    with _search_col:
        search_query = st.text_input(
            "search_users",
            placeholder="🔍  Find a user to watch together…",
            label_visibility="collapsed",
            key=f"user_search_box_{st.session_state.search_key}",
        )
    with _auth_col:
        _text_col, _home_col = st.columns([1.4, 1])
        with _text_col:
            st.markdown(
                f'<div style="text-align:right;padding-top:4px">'
                f'<span style="font-size:0.72rem;color:#666">Signed in as '
                f'<span style="color:#aaa">@{_display_name}</span></span><br>'
                f'<a href="?signout=1" target="_self" style="font-size:0.68rem;'
                f'color:#555;text-decoration:underline">Sign out</a>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _home_col:
            if st.button("HOME 👽", key="home_nav"):
                st.session_state.search_key += 1
                st.query_params.clear()
                st.rerun()

    if search_query and search_query.strip():
        _results = search_profiles(search_query.strip())
        _, _sc, _ = st.columns([1.2, 2.5, 2])
        with _sc:
            if _results:
                st.markdown(
                    '<div style="background:#111116;border:1px solid #2c2c38;'
                    'border-radius:4px;margin-top:-12px;overflow:hidden">',
                    unsafe_allow_html=True,
                )
                for _r in _results:
                    st.markdown('<div class="search-result-btn">', unsafe_allow_html=True)
                    if st.button(
                        f"@{_r['username']}  ·  {_r['ratings_count']} rated",
                        key=f"sr_{_r['slug']}",
                    ):
                        st.session_state.search_key += 1
                        st.query_params["u"] = _r["slug"]
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.caption("No users found.")
else:
    with _btn_col:
        if not st.session_state.auth_open:
            st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
            if st.button("Sign in", key="open_auth"):
                st.session_state.auth_open = not st.session_state.auth_open
                st.rerun()

st.markdown("<hr style='border-color:#1e1e26;margin:0.4rem 0 1rem'>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  SHARED PROFILE VIEW  (?u=username)
# ─────────────────────────────────────────────────────────────────────────────
shared_slug = st.query_params.get("u")
if shared_slug:
    my_username = (st.session_state.profile_meta or {}).get("username", "")
    viewing_own = my_username.lower() == shared_slug.lower()

    # ── Nav bar on shared profile page ───────────────────────────────────────
    if viewing_own:
        st.info("This is your own shareable profile link. Others will see it like this:")

    try:
        fp = get_public_profile(shared_slug)
    except Exception:
        fp = None

    if not fp:
        st.error(f"Profile **@{shared_slug}** not found or isn't public yet.")
        st.stop()

    fmeta       = fp.get("profile_meta") or {}
    fname       = fp["username"]
    frating     = fmeta.get("ratings_count", 0)
    fwatched    = fmeta.get("watched_count", 0)
    fwatchlist  = fmeta.get("watchlist_count", 0)
    flist_names = fmeta.get("list_names", [])

    fpills = " ".join(
        f'<span class="list-pill">{n.replace("-"," ").title()}</span>'
        for n in flist_names
    ) if flist_names else ""

    st.markdown(f"""
    <div class="profile-bar">
      <p class="profile-bar-name">@{fname}</p>
      <p class="profile-bar-sub">
        <span>{frating}</span> rated &nbsp;·&nbsp;
        <span>{fwatched}</span> watched &nbsp;·&nbsp;
        <span>{fwatchlist}</span> watchlist
      </p>
      <div style="margin-top:4px">{fpills}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Watch Together toggle (only if viewer has their own profile loaded) ──
    has_my_profile = bool(st.session_state.taste_profile)
    watch_together = False
    if has_my_profile and not viewing_own:
        wt_col, _ = st.columns([2, 3])
        with wt_col:
            watch_together = st.toggle(
                f"🍿 Watch Together mode — blend your taste with @{fp['username']}",
                key="wt_toggle",
            )
        if watch_together:
            st.success(f"Recommendations will now consider both your taste and @{fp['username']}'s.")
    elif not has_my_profile and not viewing_own:
        st.caption("💡 Upload your own Letterboxd export on the home page to enable Watch Together mode.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Two-column layout for shared profile ─────────────────────────────────
    sleft, sright = st.columns([2, 3], gap="large")
    sloader = sright.empty()

    with sleft:
        if watch_together:
            st.markdown(f'<p class="label">What should you two watch?</p>', unsafe_allow_html=True)
        else:
            st.markdown(f'<p class="label">What should @{fp["username"]} watch?</p>', unsafe_allow_html=True)

        sq = st.text_area(
            "shared_query",
            placeholder='e.g. "Something slow-burn and atmospheric" or "A great horror-comedy"',
            height=120,
            label_visibility="collapsed",
            key="shared_query_box",
        )

        if st.button("🎬  Get Recommendations", key="shared_get_recs"):
            if sq.strip():
                sloader.markdown(LOADER_HTML, unsafe_allow_html=True)
                try:
                    recs, _ = get_recommendations(
                        query=sq.strip(),
                        taste_profile=fp["taste_profile"],
                        imdb_summary=fp.get("imdb_summary"),
                        friend_taste_profile=st.session_state.taste_profile if watch_together else None,
                        api_key=GEMINI_KEY,
                    )
                    st.session_state["shared_recs"] = recs
                except Exception as e:
                    st.error(f"Error: {e}")
                finally:
                    sloader.empty()
                st.rerun()

        st.markdown("---")
        shared_recs_for_note = st.session_state.get("shared_recs")
        if shared_recs_for_note:
            _, taste_note_left = parse_rec_blocks(shared_recs_for_note)
            if taste_note_left:
                st.markdown(taste_note_left)

    with sright:
        st.markdown('<p class="label">Recommendations</p>', unsafe_allow_html=True)
        shared_recs = st.session_state.get("shared_recs")
        if shared_recs:
            blocks, _ = parse_rec_blocks(shared_recs)
            for block in blocks:
                try:
                    result     = fetch_poster_and_providers(block["title"], block["year"], TMDB_READ_TOKEN)
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
                st.markdown("<hr style='border-color:#1e1e26;margin:0.4rem 0'>", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="recs-empty">
              <p class="recs-empty-title">LIGHTS · CAMERA · ASK</p>
              <p class="recs-empty-sub">Type a query on the left and hit <strong>Get Recommendations</strong>.</p>
            </div>
            """, unsafe_allow_html=True)

    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
#  AUTH PANEL
# ─────────────────────────────────────────────────────────────────────────────

# ── Auth panel (shown when Sign in is clicked) ────────────────────────────────
if not user_email and st.session_state.auth_open:
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        _, xcol = st.columns([5, 1])
        with xcol:
            st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
            if st.button("✕", key="close_auth"):
                st.session_state.auth_open = False
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        mode = st.session_state.auth_mode

        if mode == "login":
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
                        save_auth_cookie(result["session"].access_token, result["session"].refresh_token, result["user"].email)
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
            st.markdown('<div class="ghost-btn" style="max-width:420px;margin:0.5rem auto">', unsafe_allow_html=True)
            if st.button("Create Account →", key="switch_to_signup"):
                st.session_state.auth_mode = "signup"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        else:  # signup
            st.markdown('<p class="auth-title">Create Account</p>', unsafe_allow_html=True)

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
                        st.session_state.profile_loaded_from_db = True
                        st.session_state.auth_mode  = "upload_required"
                        if result.get("session"):
                            save_auth_cookie(result["session"].access_token, result["session"].refresh_token, result["user"].email)
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="ghost-btn" style="max-width:420px;margin:0.5rem auto">', unsafe_allow_html=True)
            if st.button("← Back to Sign In", key="switch_to_login"):
                st.session_state.auth_mode = "login"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        if mode == "upload_required":
            st.markdown('<p class="auth-title">One Last Step</p>', unsafe_allow_html=True)
            st.markdown(
                '<p class="auth-sub">Upload your Letterboxd export to build your taste profile. '
                'This is what makes Watchwise actually good.</p>',
                unsafe_allow_html=True,
            )
            st.caption("letterboxd.com → Settings → Import & Export → Export Your Data — or go directly to [letterboxd.com/data/export/](https://letterboxd.com/data/export/)")
            onboard_zip = st.file_uploader("ZIP", type=["zip"], label_visibility="collapsed", key="onboard_zip")
            if st.button("⚙️  Build My Taste Profile", key="onboard_parse"):
                if not onboard_zip:
                    st.error("Please upload your Letterboxd ZIP first.")
                else:
                    success = parse_and_enrich_zip(onboard_zip)
                    if success:
                        _slug = st.session_state.profile_meta.get("username", "")
                        try:
                            save_profile(
                                email=st.session_state.user_email,
                                username=_slug,
                                taste_profile=st.session_state.taste_profile,
                                enriched_films=st.session_state.enriched_films or [],
                                imdb_summary=st.session_state.imdb_summary or "",
                                profile_meta=st.session_state.profile_meta,
                                is_public=True,
                                slug=_slug,
                            )
                            st.session_state.profile_slug      = _slug
                            st.session_state.profile_is_public = True
                            st.session_state.unsaved           = False
                        except Exception:
                            st.session_state.unsaved = True
                        st.session_state.auth_open = False
                        st.session_state.auth_mode = "login"
                        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
#  UPLOAD / PROFILE
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.zip_loaded:
    with st.expander("📦  Upload your Letterboxd Export", expanded=False):
        st.caption("letterboxd.com → Settings → Import & Export → Export Your Data — or go directly to [letterboxd.com/data/export/](https://letterboxd.com/data/export/)")
        uploaded_zip = st.file_uploader("ZIP", type=["zip"], label_visibility="collapsed")
        load_btn = st.button("⚙️  Parse & Enrich Profile")

    if load_btn:
        if not uploaded_zip:
            st.error("Please upload your Letterboxd ZIP first.")
        else:
            success = parse_and_enrich_zip(uploaded_zip)
            if success:
                st.session_state.unsaved = True
                st.rerun()

else:
    # Profile bar
    if st.session_state.parsed_data:
        data    = st.session_state.parsed_data
        profile = data["profile"]
        username       = profile.get("username") or "User"
        name_str       = username
        ratings_count  = len(data["ratings"])
        watched_count  = len(data["watched"])
        watchlist_count = len(data["watchlist"])
        list_names     = list(data["lists"].keys())[:8]
    else:
        meta           = st.session_state.profile_meta or {}
        username       = meta.get("username") or "User"
        name_str       = username
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
      <p class="profile-bar-name">@{name_str}</p>
      <p class="profile-bar-sub">
        <span>{ratings_count}</span> rated &nbsp;·&nbsp;
        <span>{watched_count}</span> watched &nbsp;·&nbsp;
        <span>{watchlist_count}</span> watchlist
      </p>
      <div style="margin-top:4px">{pills_html}</div>
    </div>
    """, unsafe_allow_html=True)

    bcol1, bcol2 = st.columns([1, 2])
    with bcol1:
        if st.button("↺  Upload new Letterboxd data", key="reupload"):
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
                    _slug = st.session_state.profile_slug or st.session_state.profile_meta.get("username", "")
                    save_profile(
                        email=user_email,
                        username=st.session_state.profile_meta.get("username", ""),
                        taste_profile=st.session_state.taste_profile,
                        enriched_films=st.session_state.enriched_films or [],
                        imdb_summary=st.session_state.imdb_summary or "",
                        profile_meta=st.session_state.profile_meta,
                        is_public=True,
                        slug=_slug,
                    )
                    st.session_state.profile_slug      = _slug
                    st.session_state.profile_is_public = True
                    st.session_state.unsaved           = False
                    st.success("✓ Saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
        elif not user_email and st.session_state.get("unsaved"):
            st.caption("Sign in to save your profile")
        elif user_email and not st.session_state.get("unsaved"):
            _slug = st.session_state.profile_slug or (st.session_state.profile_meta or {}).get("username", "")
            if _slug:
                share_url = f"{BASE_URL}/?u={_slug}"
                st.markdown(
                    f'<p style="font-size:0.72rem;color:#555;margin:0 0 4px 0;'
                    f'letter-spacing:0.06em;text-transform:uppercase">Share your profile:</p>'
                    f'<div style="display:inline-flex;align-items:center;gap:8px;'
                    f'background:#1a1a20;border:1px solid #2c2c38;border-radius:4px;'
                    f'padding:6px 12px">'
                    f'<span style="color:#d22323;font-size:0.85rem">🔗</span>'
                    f'<a href="{share_url}" target="_blank" style="color:#c8c2b8;'
                    f'font-size:0.78rem;font-family:monospace;text-decoration:none;'
                    f'letter-spacing:0.01em">{share_url}</a>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

st.markdown("<hr>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TWO-COLUMN LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
#
# Three-stage flow so examples disappear BEFORE Gemini blocks the thread:
#   Stage 0  normal render  — examples + query visible
#   Stage 1  loading=True, do_api=False  — loader visible, script ends fast,
#            browser commits this render, then immediately reruns
#   Stage 2  loading=True, do_api=True   — loader still shown, API runs,
#            browser shows Stage 1's committed render the whole time
#   Stage 3  loading=False, results set  — results render
#
left, right = st.columns([2, 3], gap="large")

if st.session_state.loading:
    # Stages 1 & 2 — show loader, no examples
    with left:
        st.markdown(
            '<p style="color:#555;font-size:0.85rem;padding-top:1rem">Hang tight…</p>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<p class="label">Recommendations</p>', unsafe_allow_html=True)
        st.markdown(LOADER_HTML, unsafe_allow_html=True)

    if not st.session_state.do_api:
        # Stage 1: fast render just committed the loader — queue the API call
        st.session_state.do_api = True
        st.rerun()
    else:
        # Stage 2: browser is showing Stage 1's loader — now run the API
        query_to_run = st.session_state.pending_query
        st.session_state.pending_query = ""
        friend_tp = (st.session_state.friend_profile or {}).get("taste_profile") \
            if st.session_state.watch_together else None
        try:
            watched_set = get_watched_set(st.session_state.parsed_data) \
                if st.session_state.parsed_data else None
            recs, replaced = get_recommendations(
                query=query_to_run,
                taste_profile=st.session_state.taste_profile,
                imdb_summary=st.session_state.imdb_summary,
                watched_set=watched_set,
                conversation_history=st.session_state.get("chat_history") or None,
                friend_taste_profile=friend_tp,
                api_key=GEMINI_KEY,
            )
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
            st.session_state.chat_history.append({"role": "user",      "content": query_to_run})
            st.session_state.chat_history.append({"role": "assistant", "content": recs})
            st.session_state.recommendations = recs
            st.session_state.replaced        = replaced
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                import re as _re
                delay = _re.search(r"retryDelay.*?(\d+)s", err)
                delay_str = f" Try again in {delay.group(1)} seconds." if delay else ""
                st.warning(f"⚠️ Gemini quota reached.{delay_str}")
            else:
                st.error(f"Gemini error: {e}")
        finally:
            st.session_state.loading = False
            st.session_state.do_api  = False
        st.rerun()

else:
    # Stage 0 / Stage 3 — normal render
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
                        st.session_state.pending_query = query.strip()
                        st.session_state.loading       = True
                        st.session_state.do_api        = False
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
                st.session_state.pending_query = query.strip()
                st.session_state.loading       = True
                st.session_state.do_api        = False
                st.rerun()

        st.markdown("---")

        if st.session_state.recommendations and st.session_state.zip_loaded:
            _, taste_note = parse_rec_blocks(st.session_state.recommendations)
            if taste_note:
                st.markdown(taste_note)
        elif not st.session_state.recommendations:
            st.markdown('<div class="examples-block">', unsafe_allow_html=True)
            st.markdown('<p class="label" style="font-size:0.75rem">Quick examples</p>', unsafe_allow_html=True)
            cols = st.columns(2)
            for i, ex in enumerate(EXAMPLES):
                with cols[i % 2]:
                    st.markdown('<div class="example-btn">', unsafe_allow_html=True)
                    if st.button(ex, key=f"ex__{ex}"):
                        st.session_state.pending_query = ex
                        st.session_state.loading       = True
                        st.session_state.do_api        = False
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<p class="label">Recommendations</p>', unsafe_allow_html=True)

        if st.session_state.recommendations:
            blocks, taste_note = parse_rec_blocks(st.session_state.recommendations)

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
                    result     = fetch_poster_and_providers(block["title"], block["year"], TMDB_READ_TOKEN)
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