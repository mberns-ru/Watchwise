# 🎬 Watchwise — AI-Backed Movie Suggestions

Personalized, conversational movie recommendations grounded in your Letterboxd export, enriched with TMDB metadata, and powered by Google Gemini 2.5 Flash.

**🔗 Live app:** [watchwise.streamlit.app](https://watchwise.streamlit.app)

---

## What it does

Upload your Letterboxd data export and ask Watchwise what to watch tonight. Instead of relying on what's licensed to a particular streaming service or on opaque "because you watched X" suggestions, Watchwise builds a structured taste profile from your lifetime rating history — your loved films, hated films, custom lists, written reviews, and watchlist — and sends it to Gemini alongside your natural-language query. You get back 5 ranked films, each with a query-fit rationale, a per-user taste rationale referencing your actual ratings or lists, and where to stream it.

Example queries that work well:

- *"A slow-burn psychological horror, not gore"*
- *"Foreign murder mystery under 90 minutes"*
- *"Underrated 80s sci-fi I've probably never heard of"*
- *"More like #3 but less violent"* (follow-up turns work)

---

## Features

- **Letterboxd-grounded recommendations** — your taste profile is built from ratings, watchlist, custom lists, diary tags, reviews, and likes.
- **Multi-turn conversation** — refine recommendations naturally ("shorter", "more obscure", "more like #3").
- **Already-watched exclusion** — your full watch history is sent as a hard exclusion list, with an LLM self-correction loop that catches and replaces any seen films that slip through.
- **Watch Together mode** — visit a friend's public Watchwise profile and toggle blended recommendations that genuinely fit both of your tastes.
- **Community picks** — when other Watchwise users with overlapping taste have loved a film you haven't seen, the model can surface it as a tagged recommendation.
- **Streaming availability** — each recommendation shows current streaming providers via TMDB.
- **Persistent profile** — sign in once with email or Google; your taste profile is saved and loads on every visit.
- **Public profile sharing** — share your taste profile at `watchwise.streamlit.app/?u=<your-username>`.
- **Rewatch toggle** — opt in to allow films you've already watched to be recommended again.

---

## Quick start

```bash
git clone <repo-url>
cd watchwise
pip install -r requirements.txt
streamlit run app.py
```

Then open [localhost:8501](http://localhost:8501) and upload your Letterboxd export ZIP.

---

## API keys needed

| Service | Purpose | Free? | Link |
|---|---|---|---|
| **Google Gemini** | LLM recommendations | ✅ Yes | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| **TMDB** | Film metadata, posters, streaming providers | ✅ Yes | [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) |
| **Supabase** | Auth + persistent profiles | ✅ Free tier | [supabase.com](https://supabase.com) |

Set them as environment variables or via `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY    = "..."
TMDB_READ_TOKEN   = "..."   # the v4 read token, not v3 API key
SUPABASE_URL      = "https://<project>.supabase.co"
SUPABASE_KEY      = "..."
```

---

## Getting your Letterboxd export

1. Go to **letterboxd.com → Settings → Import & Export** — or directly to [letterboxd.com/data/export/](https://letterboxd.com/data/export/)
2. Click **Export Your Data** → download the ZIP
3. Upload it in the Watchwise sidebar (you'll be prompted on first sign-in)

### ZIP structure used

```
letterboxd-{username}-{date}/
├── ratings.csv        ⭐ primary taste signal (personal star ratings 0.5–5.0)
├── watched.csv        full watch history (becomes the exclusion list)
├── watchlist.csv      want-to-watch list
├── diary.csv          diary entries with dates, tags, rewatches
├── reviews.csv        written reviews (in-their-own-words taste signal)
├── profile.csv        username, display name
├── likes/
│   └── films.csv      hearted/liked films
└── lists/
    └── *.csv          custom lists — list NAMES are a rich taste signal
```

---

## Architecture

```
app.py                  Streamlit UI, auth, session state, three-stage loader
letterboxd_parser.py    ZIP → structured data → plain-text taste profile
tmdb_utils.py           TMDB API → genre/director/language enrichment, posters, providers
recommender.py          Gemini orchestration: prompts, multi-turn, self-correction, community picks
db.py                   Supabase auth + persistent profile storage
```

### Data flow

1. **Parse** — ZIP is unpacked in-memory; CSVs read into pandas DataFrames.
2. **Enrich** — up to 100 highest-rated films are looked up via TMDB for genre, director, cast, runtime, language, country, plot, and poster.
3. **Profile** — all data assembled into a structured plain-text taste profile:
   - Loved (≥4.5★), liked (4★), disliked (2–2.5★), hated (≤1.5★) films
   - Hearted films
   - Custom list names (e.g. "bog-heavy-gothic-movies", "femcel-flicks")
   - Diary tags and review snippets
   - TMDB genre/language/director frequency analysis
   - **Full ALREADY SEEN exclusion list** (appended after the cap so it's never truncated)
4. **Recommend** — Gemini 2.5 Flash receives the taste profile + TMDB summary + optional community-picks block + the user's natural-language query, and returns 5 ranked picks with per-user reasoning and a closing taste note. A self-correction loop (max 2 retries) catches any already-seen films and prompts Gemini to replace them.

---

## Tech stack

- **Frontend:** Streamlit
- **LLM:** Google Gemini 2.5 Flash (`gemini-2.5-flash`)
- **Database / Auth:** Supabase (Postgres + Auth, with Google OAuth)
- **Metadata:** TMDB API (search, details, watch providers)
- **Session persistence:** `streamlit-cookies-controller` (30-day cookies)
- **Hosting:** Streamlit Community Cloud

See `requirements.txt` for full package list.

---

## How it's different from streaming-service recommenders

Netflix, Hulu, Disney+, and Prime Video all run recommenders, but they:

- only see what you watched **on that single platform**
- can only recommend titles in **their own licensed catalog**
- optimize for **engagement and retention**, not best fit for what you want tonight
- give **generic "Because you watched X" explanations** that you can't interrogate
- have a brutal **cold-start problem** on new accounts

Watchwise sees your *entire* viewing life across every platform (because Letterboxd is platform-agnostic), has no catalog constraint, has no engagement objective pulling against your interests, gives a per-recommendation rationale referencing your actual ratings or list names, and is fully cold-started from the moment you upload your export.

---

## Roadmap

- [ ] Background re-enrichment to grow the community-picks pool over time
- [ ] Region-aware streaming providers (currently US-only)
- [ ] Embedding-based similarity search for newer/obscure films
- [ ] Export recommendations as a Letterboxd-importable list CSV
- [ ] Move exclusion check from prompt to post-hoc filter to free context budget

## Done

- [x] TMDB integration (replaced OMDb) — poster images, streaming providers, richer metadata
- [x] Conversation mode (multi-turn refinement)
- [x] Google OAuth sign-in
- [x] Persistent profiles
- [x] Public profile sharing
- [x] Watch Together mode
- [x] Community picks via similar-user collaborative filtering

---

*Built for **Special Topics: AI and LLM in Data Science**, Spring 2026.*
