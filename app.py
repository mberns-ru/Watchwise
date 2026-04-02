"""
app.py — Watchwise: AI-Backed Movie Suggestions
Run: streamlit run app.py
"""

import os
import time
import streamlit as st
from dotenv import load_dotenv
from letterboxd_parser import parse_letterboxd_zip, build_taste_profile, get_watched_set
from tmdb_utils import build_enrichment_summary, fetch_film_metadata, fetch_poster
from recommender import get_recommendations, parse_rec_blocks

load_dotenv()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
TMDB_TOKEN = os.environ.get("TMDB_READ_TOKEN", "")

missing = [k for k, v in {"GEMINI_API_KEY": GEMINI_KEY, "TMDB_READ_TOKEN": TMDB_TOKEN}.items() if not v]
if missing:
    st.error(f"Missing environment variables in .env: {', '.join(missing)}")
    st.code("GEMINI_API_KEY=your_key\nTMDB_READ_TOKEN=your_token", language="bash")
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
/* Hide sidebar entirely */
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden; }

/* ── Text legibility ── */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] ol,
[data-testid="stMarkdownContainer"] ul { color: #e8e2d8 !important; }
[data-testid="stMarkdownContainer"] strong { color: #fff !important; }
[data-testid="stMarkdownContainer"] em    { color: #c8c2b8 !important; }
[data-testid="stCaptionContainer"] p      { color: #888 !important; }
p, li, label { color: #e8e2d8; }
h1,h2,h3,h4  { font-family: 'Bebas Neue', sans-serif; letter-spacing: 0.06em; }

/* ── Inputs ── */
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

/* ── File uploader ── */
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

/* ── Buttons ── */
.stButton > button {
    background: #d22323 !important; color: #fff !important;
    border: none !important; border-radius: 3px !important;
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 0.12em !important; font-size: 1.05rem !important;
    padding: 0.45rem 1.4rem !important;
    width: 100%; transition: background 0.2s;
}
.stButton > button:hover { background: #a81818 !important; }

/* Example buttons */
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

/* ── Header ── */
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

/* ── Profile bar ── */
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

/* ── Expander ── */
[data-testid="stExpander"] summary {
    background: #16161c !important;
    border: 1px solid #2a2a32 !important;
    border-radius: 4px !important;
}
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary svg {
    color: #999 !important;
    fill: #999 !important;
}
.label {
    font-family: 'Bebas Neue', sans-serif; font-size: 0.9rem;
    letter-spacing: 0.18em; color: #d22323;
    text-transform: uppercase; margin-bottom: 4px;
}

/* ── Loading dots ── */
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

/* ── Recs ── */
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
    "parsed_data":     None,
    "enriched_films":  None,
    "imdb_summary":    None,
    "taste_profile":   None,
    "recommendations": None,
    "replaced":        [],
    "zip_loaded":      False,
    "pending_query":   "",
    "auto_run":        False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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
#  HELPER: run recommendations
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
            api_key=GEMINI_KEY,
        )
        st.session_state.recommendations = recs
        st.session_state.replaced        = replaced
    except Exception as e:
        loader_slot.empty()
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            # Extract retry delay if available
            import re
            delay = re.search(r"retryDelay.*?(\d+)s", err)
            delay_str = f" Try again in {delay.group(1)} seconds." if delay else ""
            st.warning(
                f"⚠️ Gemini API quota reached — you've hit the free tier limit for today."
                f"{delay_str}\n\n"
                f"Check your usage at [ai.dev/rate-limit](https://ai.dev/rate-limit)."
            )
        else:
            st.error(f"Gemini error: {e}")
        return
    loader_slot.empty()

# ─────────────────────────────────────────────────────────────────────────────
#  HEADER (full-width, centered)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ww-header">
  <p class="ww-logo">WATCHWISE<span class="rec-dot"></span></p>
  <p class="ww-tagline">AI-Backed Movie Suggestions</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  UPLOAD / PROFILE — full-width above columns
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

            st.session_state.enriched_films  = enriched
            st.session_state.imdb_summary    = build_enrichment_summary(enriched)
            st.session_state.taste_profile   = build_taste_profile(data, enriched)
            st.session_state.zip_loaded      = True
            st.session_state.recommendations = None
            st.rerun()

else:
    data     = st.session_state.parsed_data
    profile  = data["profile"]
    ratings  = data["ratings"]
    lists    = data["lists"]

    username = profile.get("username") or profile.get("given_name") or "User"
    name_str = " ".join(filter(None, [
        profile.get("given_name"), profile.get("family_name")
    ])) or username

    pills_html = " ".join(
        f'<span class="list-pill">{n.replace("-"," ").title()}</span>'
        for n in list(lists.keys())[:8]
    ) if lists else ""

    st.markdown(f"""
    <div class="profile-bar">
      <p class="profile-bar-name">{name_str}</p>
      <p class="profile-bar-sub">@{username} &nbsp;·&nbsp;
        <span>{len(ratings)}</span> rated &nbsp;·&nbsp;
        <span>{len(data['watched'])}</span> watched &nbsp;·&nbsp;
        <span>{len(data['watchlist'])}</span> watchlist
      </p>
      <div style="margin-top:4px">{pills_html}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("↺  Upload a different file", key="reupload"):
        for k in ["parsed_data","enriched_films","imdb_summary","taste_profile","recommendations","replaced"]:
            st.session_state[k] = [] if k == "replaced" else None
        st.session_state.zip_loaded = False
        st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TWO-COLUMN LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
left, right = st.columns([2, 3], gap="large")
loader_slot = right.empty()

with left:
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

    go = st.button("🎬  Get Recommendations")

    if go and query.strip():
        st.session_state.pending_query = ""
        st.session_state.auto_run      = False
        run_recommendations(query, loader_slot)
        st.rerun()

    st.markdown("---")

    # Show examples OR taste note depending on state
    if st.session_state.recommendations and st.session_state.zip_loaded:
        _, taste_note = parse_rec_blocks(st.session_state.recommendations)
        if taste_note:
            st.markdown(taste_note)
    else:
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

# Auto-run from example click
if st.session_state.auto_run and st.session_state.pending_query:
    run_query = st.session_state.pending_query
    st.session_state.auto_run      = False
    st.session_state.pending_query = ""
    run_recommendations(run_query, loader_slot)
    st.rerun()

# ── RIGHT: logo + recommendations ────────────────────────────────────────────
with right:
    st.markdown('<p class="label">Recommendations</p>', unsafe_allow_html=True)

    if st.session_state.recommendations:
        blocks, taste_note = parse_rec_blocks(st.session_state.recommendations)

        for block in blocks:
            try:
                poster_url = fetch_poster(block["title"], block["year"], TMDB_TOKEN)
            except Exception:
                poster_url = None
            col_img, col_text = st.columns([1, 4], gap="medium")
            with col_img:
                if poster_url:
                    st.image(poster_url, use_container_width=True)
                else:
                    st.markdown(
                        '<div style="background:#1e1e26;border-radius:4px;'
                        'aspect-ratio:2/3;display:flex;align-items:center;'
                        'justify-content:center;color:#444;font-size:1.5rem;">🎬</div>',
                        unsafe_allow_html=True,
                    )
            with col_text:
                st.markdown(block["body"])
            st.markdown("<hr style='border-color:#1e1e26;margin:0.4rem 0'>",
                        unsafe_allow_html=True)

        if st.session_state.get("replaced"):
            replaced_str = ", ".join(t.title() for t in st.session_state.replaced)
            st.info(f"♻️ Replaced already-seen film(s): {replaced_str}")

        st.markdown("---")
        if st.button("↺  Clear"):
            st.session_state.recommendations = None
            st.session_state.replaced = []
            st.rerun()
    else:
        st.markdown("""
        <div class="recs-empty">
          <p class="recs-empty-title">LIGHTS · CAMERA · ASK</p>
          <p class="recs-empty-sub">Type a query or pick an example on the left,
          then hit <strong>Get Recommendations</strong>.</p>
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  DEBUG EXPANDERS
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.taste_profile:
    with st.expander("📄 View taste profile sent to Gemini"):
        st.code(st.session_state.taste_profile, language=None)
if st.session_state.imdb_summary:
    with st.expander("🎞️ TMDB metadata summary"):
        st.code(st.session_state.imdb_summary, language=None)