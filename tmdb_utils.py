"""
tmdb_utils.py
Fetches film metadata from The Movie Database (TMDB) API.

Docs: https://developer.themoviedb.org/docs
Auth: Bearer token (read access token) — no rate limit concerns for this volume.
"""

import requests
from collections import Counter

TMDB_BASE = "https://api.themoviedb.org/3"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "accept": "application/json"}


def fetch_film_metadata(title: str, year: str | None, token: str) -> dict | None:
    """
    Fetch a single film's metadata from TMDB.

    Strategy:
      1. Search by title + year  → take best match
      2. Search by title only    → take best match
      3. Return None if not found

    Returns a normalized dict with the same keys the rest of the app expects:
      Genre, Director, Actors, Runtime, Language, Country, Plot,
      tmdbRating, tmdbID, PosterPath
    """
    h = _headers(token)

    def _search(query: str, yr: str | None) -> dict | None:
        params = {"query": query, "include_adult": False}
        if yr and str(yr).isdigit():
            params["year"] = str(yr)
        try:
            r = requests.get(f"{TMDB_BASE}/search/movie", params=params, headers=h, timeout=6)
            results = r.json().get("results", [])
            if results:
                # Prefer exact title match, else take highest-popularity result
                exact = [x for x in results
                         if x.get("title", "").lower() == query.lower()
                         or x.get("original_title", "").lower() == query.lower()]
                return exact[0] if exact else results[0]
        except Exception:
            pass
        return None

    # 1. Search with year
    result = _search(title, year)
    # 2. Fallback: search without year
    if not result:
        result = _search(title, None)
    if not result:
        return None

    movie_id = result["id"]

    # Fetch full detail + credits in one call via append_to_response
    try:
        detail_r = requests.get(
            f"{TMDB_BASE}/movie/{movie_id}",
            params={"append_to_response": "credits"},
            headers=h,
            timeout=6,
        )
        detail = detail_r.json()
    except Exception:
        return None

    # ── Extract fields ─────────────────────────────────────────────────────
    genres = ", ".join(g["name"] for g in detail.get("genres", []))

    directors = [
        p["name"] for p in detail.get("credits", {}).get("crew", [])
        if p.get("job") == "Director"
    ]
    director_str = ", ".join(directors) if directors else "N/A"

    cast = [
        p["name"] for p in detail.get("credits", {}).get("cast", [])[:5]
    ]
    actors_str = ", ".join(cast) if cast else "N/A"

    runtime_min = detail.get("runtime")
    runtime_str = f"{runtime_min} min" if runtime_min else "N/A"

    # Primary spoken language (ISO 639-1 → full name via TMDB field)
    spoken_langs = detail.get("spoken_languages", [])
    lang_str = ", ".join(l.get("english_name", l.get("name", "")) for l in spoken_langs) or "N/A"

    countries = detail.get("production_countries", [])
    country_str = ", ".join(c.get("name", "") for c in countries) or "N/A"

    return {
        "Genre":      genres or "N/A",
        "Director":   director_str,
        "Actors":     actors_str,
        "Runtime":    runtime_str,
        "Language":   lang_str,
        "Country":    country_str,
        "Plot":       detail.get("overview", "N/A") or "N/A",
        "tmdbRating": str(round(detail.get("vote_average", 0), 1)),
        "tmdbID":     str(movie_id),
        "PosterPath": detail.get("poster_path", ""),
        "Popularity": detail.get("popularity", 0),
    }


def build_enrichment_summary(enriched_films: list[dict]) -> str:
    """
    Build a compact text block summarising genre/language/director/country
    patterns across the user's top-rated films.
    Only films where TMDB returned metadata contribute.
    """
    if not enriched_films:
        return ""

    genres    = Counter()
    languages = Counter()
    directors = Counter()
    countries = Counter()
    hits      = 0

    for film in enriched_films:
        if not film.get("Genre") or film["Genre"] == "N/A":
            continue
        hits += 1
        for g in film["Genre"].split(","):
            g = g.strip()
            if g:
                genres[g] += 1
        for lang in film.get("Language", "").split(","):
            lang = lang.strip()
            if lang and lang != "N/A":
                languages[lang] += 1
        for d in film.get("Director", "").split(","):
            d = d.strip()
            if d and d != "N/A":
                directors[d] += 1
        for c in film.get("Country", "").split(","):
            c = c.strip()
            if c and c != "N/A":
                countries[c] += 1

    if hits == 0:
        return f"=== TMDB METADATA: 0/{len(enriched_films)} films found ==="

    lines = [f"=== TMDB METADATA ANALYSIS ({hits}/{len(enriched_films)} films found) ==="]
    if genres:
        lines.append("Top genres: "    + ", ".join(f"{g} ({c}x)" for g, c in genres.most_common(8)))
    if languages:
        lines.append("Top languages: " + ", ".join(f"{l} ({c}x)" for l, c in languages.most_common(6)))
    if countries:
        lines.append("Top countries: " + ", ".join(f"{c} ({n}x)" for c, n in countries.most_common(6)))
    if directors:
        lines.append("Fav directors: " + ", ".join(f"{d} ({c}x)" for d, c in directors.most_common(5)))

    return "\n".join(lines)
