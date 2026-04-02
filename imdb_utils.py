"""
imdb_utils.py
Fetches film metadata from the OMDb API (the free IMDB data API).

Get a free API key at: https://www.omdbapi.com/apikey.aspx
Free tier: 1,000 requests/day.
"""

import requests
import time

OMDB_BASE = "https://www.omdbapi.com/"


def fetch_film_metadata(title: str, year: str | None, api_key: str) -> dict | None:
    """
    Fetch a single film's metadata from OMDb.
    Strategy:
      1. Exact title + year match
      2. Exact title match (no year)
      3. Search fallback (s= param) — catches foreign/obscure titles
    """
    params = {"apikey": api_key, "type": "movie"}

    def _get_by_id(imdb_id: str) -> dict | None:
        r = requests.get(OMDB_BASE, params={"i": imdb_id, "apikey": api_key}, timeout=6)
        d = r.json()
        return d if d.get("Response") == "True" else None

    # 1. Exact title + year
    try:
        p = {**params, "t": title}
        if year and str(year).isdigit():
            p["y"] = str(year)
        resp = requests.get(OMDB_BASE, params=p, timeout=6)
        data = resp.json()
        if data.get("Response") == "True":
            return data
    except Exception:
        pass

    # 2. Exact title without year
    try:
        resp2 = requests.get(OMDB_BASE, params={**params, "t": title}, timeout=6)
        data2 = resp2.json()
        if data2.get("Response") == "True":
            return data2
    except Exception:
        pass

    # 3. Search fallback — returns a list, pick the best year match
    try:
        sp = {"s": title, "apikey": api_key, "type": "movie"}
        if year and str(year).isdigit():
            sp["y"] = str(year)
        resp3 = requests.get(OMDB_BASE, params=sp, timeout=6)
        data3 = resp3.json()
        if data3.get("Response") == "True":
            results = data3.get("Search", [])
            if results:
                # Prefer year-matching result, otherwise take first
                best = next(
                    (r for r in results if str(r.get("Year", "")).startswith(str(year))),
                    results[0],
                )
                return _get_by_id(best["imdbID"])
    except Exception:
        pass

    return None


def enrich_films(
    films: list[dict],
    api_key: str,
    max_films: int = 30,
    delay: float = 0.12,
) -> list[dict]:
    """
    Enrich a list of {name, year, rating} dicts with OMDb metadata.

    Args:
        films:      List of film dicts (from letterboxd_parser).
        api_key:    OMDb API key.
        max_films:  Cap to avoid blowing through daily quota.
        delay:      Seconds between requests (be polite to OMDb).

    Returns:
        List of enriched dicts – original fields plus OMDb metadata.
    """
    enriched = []
    seen = set()

    for film in films[:max_films]:
        name = film.get("name", "")
        year = film.get("year", "")
        key  = (name.lower(), str(year))
        if key in seen or not name:
            continue
        seen.add(key)

        meta = fetch_film_metadata(name, year, api_key)
        combined = {
            "title":  name,
            "year":   year,
            "rating": film.get("rating"),
        }
        if meta:
            combined.update({
                "Genre":       meta.get("Genre", "N/A"),
                "Director":    meta.get("Director", "N/A"),
                "Actors":      meta.get("Actors", "N/A"),
                "Runtime":     meta.get("Runtime", "N/A"),
                "Language":    meta.get("Language", "N/A"),
                "Country":     meta.get("Country", "N/A"),
                "Plot":        meta.get("Plot", "N/A"),
                "imdbRating":  meta.get("imdbRating", "N/A"),
                "Rated":       meta.get("Rated", "N/A"),
                "imdbID":      meta.get("imdbID", ""),
            })
        enriched.append(combined)
        time.sleep(delay)

    return enriched


def build_enrichment_summary(enriched_films: list[dict]) -> str:
    """
    Turn enriched film list into a compact text block for the Gemini prompt.
    Only films where OMDb returned metadata contribute to the analysis.
    """
    if not enriched_films:
        return ""

    from collections import Counter

    genres    = Counter()
    languages = Counter()
    directors = Counter()
    countries = Counter()
    hits      = 0

    for film in enriched_films:
        # Only count films that actually have metadata (Genre present and not N/A)
        if not film.get("Genre") or film.get("Genre") == "N/A":
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
        return f"=== IMDB METADATA: 0/{len(enriched_films)} films found in OMDb ==="

    lines = [f"=== IMDB METADATA ANALYSIS ({hits}/{len(enriched_films)} films found) ==="]
    if genres:
        lines.append("Top genres: "    + ", ".join(f"{g} ({c}x)" for g, c in genres.most_common(8)))
    if languages:
        lines.append("Top languages: " + ", ".join(f"{l} ({c}x)" for l, c in languages.most_common(6)))
    if countries:
        lines.append("Top countries: " + ", ".join(f"{c} ({n}x)" for c, n in countries.most_common(6)))
    if directors:
        lines.append("Fav directors: " + ", ".join(f"{d} ({c}x)" for d, c in directors.most_common(5)))

    return "\n".join(lines)
