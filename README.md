# 🎬 Watchwise — AI-Backed Movie Suggestions

Personalized movie recommendations powered by your Letterboxd export, IMDB metadata, and Google Gemini.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## API Keys Needed

| Service | Purpose | Free? | Link |
|---|---|---|---|
| **Google Gemini** | LLM recommendations | ✅ Yes | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| **OMDb API** | IMDB metadata | ✅ Yes (1000/day) | [omdbapi.com/apikey.aspx](https://www.omdbapi.com/apikey.aspx) |

## Getting Your Letterboxd Export

1. Go to **letterboxd.com → Settings → Import & Export**
2. Click **Export Your Data** → download the ZIP
3. Upload it directly in the Watchwise sidebar

## ZIP Structure Used

```
letterboxd-{username}-{date}/
├── ratings.csv        ← ⭐ primary taste signal (personal star ratings 0.5–5.0)
├── watched.csv        ← full watch history
├── watchlist.csv      ← want-to-watch list
├── diary.csv          ← diary entries with dates, tags, rewatches
├── reviews.csv        ← written reviews (in-their-own-words taste signal)
├── profile.csv        ← username, display name
├── likes/
│   └── films.csv      ← hearted/liked films
└── lists/
    └── *.csv          ← custom lists (list NAMES are great taste signals)
```

## Architecture

```
app.py                  Streamlit UI
letterboxd_parser.py    ZIP → structured data → plain-text taste profile
imdb_utils.py           OMDb API → genre/language/director enrichment
recommender.py          Google Gemini → personalized recommendations
```

### Data Flow

1. **Parse** — ZIP is unpacked in-memory; CSVs read into pandas DataFrames
2. **Enrich** — Top-rated films are looked up via OMDb for genre, runtime, language, director, country
3. **Profile** — All data assembled into a structured plain-text taste profile:
   - Top-rated / disliked films
   - Liked films (hearted)
   - Custom list names (very revealing — e.g. "femcel-flicks", "bog-heavy-gothic-movies")
   - Diary tags
   - Sample review text
   - IMDB genre/language/director frequency analysis
4. **Recommend** — Gemini receives the taste profile + query and returns 5 ranked picks with per-user reasoning

## Roadmap

- [ ] JustWatch integration for streaming availability filtering
- [ ] Conversation mode (multi-turn refinement)
- [ ] Export recommendations as a new Letterboxd list CSV
- [ ] Embedding-based similarity search over a film dataset
- [ ] TMDB API for poster images in the results
