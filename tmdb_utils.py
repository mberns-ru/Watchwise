"""
tmdb_utils.py
Fetches film metadata from The Movie Database (TMDB) API.
"""

import requests
from collections import Counter

TMDB_BASE     = "https://api.themoviedb.org/3"
TMDB_IMG_FULL = "https://image.tmdb.org/t/p/w342"
TMDB_LOGO_SM  = "https://image.tmdb.org/t/p/w45"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "accept": "application/json"}


# ── Poster + Watch Providers ──────────────────────────────────────────────────

def fetch_poster_and_providers(
    title: str,
    year: str | None,
    token: str,
    country: str = "US",
) -> dict:
    """
    Search for a film, then fetch its poster and streaming providers in one flow.

    Returns:
        {
          "poster_url": str | None,
          "providers":  list[{"name": str, "logo_url": str}]  (flatrate/streaming only)
        }
    """
    h       = _headers(token)
    movie_id = None
    poster_url = None

    for yr in ([year, None] if year else [None]):
        params = {"query": title, "include_adult": False}
        if yr and str(yr).isdigit():
            params["year"] = yr
        try:
            r       = requests.get(f"{TMDB_BASE}/search/movie", params=params, headers=h, timeout=5)
            results = r.json().get("results", [])
            if results:
                # Prefer exact title match
                match = next(
                    (x for x in results[:3] if x.get("title", "").lower() == title.lower()),
                    results[0],
                )
                movie_id = match.get("id")
                path = match.get("poster_path")
                poster_url = f"{TMDB_IMG_FULL}{path}" if path else None
                break
        except Exception:
            pass

    providers = []
    if movie_id:
        try:
            wp = requests.get(
                f"{TMDB_BASE}/movie/{movie_id}/watch/providers",
                headers=h,
                timeout=5,
            ).json()
            region = wp.get("results", {}).get(country, {})
            for p in region.get("flatrate", []):
                logo = p.get("logo_path")
                providers.append({
                    "name":     p.get("provider_name", ""),
                    "logo_url": f"{TMDB_LOGO_SM}{logo}" if logo else None,
                })
        except Exception:
            pass

    return {"poster_url": poster_url, "providers": providers}


# kept for backwards compat
def fetch_poster(title: str, year: str | None, token: str) -> str | None:
    return fetch_poster_and_providers(title, year, token)["poster_url"]


# ── Full metadata fetch ───────────────────────────────────────────────────────

def fetch_film_metadata(title: str, year: str | None, token: str) -> dict | None:
    h = _headers(token)

    def _search(query, yr):
        params = {"query": query, "include_adult": False}
        if yr and str(yr).isdigit():
            params["year"] = str(yr)
        try:
            r = requests.get(f"{TMDB_BASE}/search/movie", params=params, headers=h, timeout=6)
            results = r.json().get("results", [])
            if results:
                exact = [x for x in results
                         if x.get("title", "").lower() == query.lower()
                         or x.get("original_title", "").lower() == query.lower()]
                return exact[0] if exact else results[0]
        except Exception:
            pass
        return None

    result = _search(title, year) or _search(title, None)
    if not result:
        return None

    movie_id = result["id"]
    try:
        detail = requests.get(
            f"{TMDB_BASE}/movie/{movie_id}",
            params={"append_to_response": "credits"},
            headers=h,
            timeout=6,
        ).json()
    except Exception:
        return None

    genres       = ", ".join(g["name"] for g in detail.get("genres", []))
    directors    = [p["name"] for p in detail.get("credits", {}).get("crew", []) if p.get("job") == "Director"]
    cast         = [p["name"] for p in detail.get("credits", {}).get("cast", [])[:5]]
    runtime_min  = detail.get("runtime")
    spoken_langs = detail.get("spoken_languages", [])
    countries    = detail.get("production_countries", [])

    return {
        "Genre":      genres or "N/A",
        "Director":   ", ".join(directors) if directors else "N/A",
        "Actors":     ", ".join(cast) if cast else "N/A",
        "Runtime":    f"{runtime_min} min" if runtime_min else "N/A",
        "Language":   ", ".join(l.get("english_name", l.get("name", "")) for l in spoken_langs) or "N/A",
        "Country":    ", ".join(c.get("name", "") for c in countries) or "N/A",
        "Plot":       detail.get("overview", "N/A") or "N/A",
        "tmdbRating": str(round(detail.get("vote_average", 0), 1)),
        "tmdbID":     str(movie_id),
        "PosterPath": detail.get("poster_path", ""),
        "Popularity": detail.get("popularity", 0),
    }


# ── Enrichment summary ────────────────────────────────────────────────────────

def build_enrichment_summary(enriched_films: list[dict]) -> str:
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
            if g: genres[g] += 1
        for lang in film.get("Language", "").split(","):
            lang = lang.strip()
            if lang and lang != "N/A": languages[lang] += 1
        for d in film.get("Director", "").split(","):
            d = d.strip()
            if d and d != "N/A": directors[d] += 1
        for c in film.get("Country", "").split(","):
            c = c.strip()
            if c and c != "N/A": countries[c] += 1

    if hits == 0:
        return f"=== TMDB METADATA: 0/{len(enriched_films)} films found ==="

    lines = [f"=== TMDB METADATA ANALYSIS ({hits}/{len(enriched_films)} films found) ==="]
    if genres:    lines.append("Top genres: "    + ", ".join(f"{g} ({c}x)" for g, c in genres.most_common(8)))
    if languages: lines.append("Top languages: " + ", ".join(f"{l} ({c}x)" for l, c in languages.most_common(6)))
    if countries: lines.append("Top countries: " + ", ".join(f"{c} ({n}x)" for c, n in countries.most_common(6)))
    if directors: lines.append("Fav directors: " + ", ".join(f"{d} ({c}x)" for d, c in directors.most_common(5)))

    return "\n".join(lines)