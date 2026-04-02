"""
letterboxd_parser.py
Parses a Letterboxd data export ZIP file into structured Python objects.

ZIP structure (from export):
  ratings.csv        – personal star ratings (0.5–5.0)
  watched.csv        – all watched films
  watchlist.csv      – want to watch
  diary.csv          – diary entries (date, rating, rewatch, tags)
  reviews.csv        – written reviews
  profile.csv        – username, display name
  likes/films.csv    – hearted/liked films
  lists/*.csv        – user's custom lists
"""

import io
import zipfile
import pandas as pd
from pathlib import PurePosixPath


# ── helpers ────────────────────────────────────────────────────────────────

def _read_csv(zf: zipfile.ZipFile, path: str) -> pd.DataFrame:
    """Read a CSV from inside the zip. Returns empty DataFrame on missing file."""
    try:
        with zf.open(path) as f:
            return pd.read_csv(f)
    except KeyError:
        return pd.DataFrame()


def _find_path(zf: zipfile.ZipFile, suffix: str) -> str | None:
    """
    Find the first zip entry whose path ends with `suffix` (case-insensitive).
    Letterboxd wraps everything in a top-level folder, so we search by suffix.
    """
    suffix_lower = suffix.lower().lstrip("/")
    for name in zf.namelist():
        if name.lower().rstrip("/").endswith(suffix_lower):
            return name
    return None


def _find_paths_in_folder(zf: zipfile.ZipFile, folder_suffix: str) -> list[str]:
    """Return all zip entries inside a given sub-folder (matched by suffix)."""
    folder_suffix_lower = folder_suffix.lower().strip("/")
    results = []
    for name in zf.namelist():
        parts = PurePosixPath(name).parts
        # Check if any parent directory matches the folder suffix
        if len(parts) >= 2:
            parent = "/".join(parts[:-1]).lower()
            if parent.endswith(folder_suffix_lower) and name.endswith(".csv"):
                results.append(name)
    return results


# ── main parser ────────────────────────────────────────────────────────────

def parse_letterboxd_zip(uploaded_file) -> dict:
    """
    Parse a Letterboxd export ZIP.

    Args:
        uploaded_file: A file-like object (e.g. from st.file_uploader).

    Returns:
        A dict with keys:
          profile, ratings, watched, watchlist, diary, reviews, liked_films, lists
    """
    raw = uploaded_file.read() if hasattr(uploaded_file, "read") else uploaded_file
    zf = zipfile.ZipFile(io.BytesIO(raw))

    def read(suffix):
        path = _find_path(zf, suffix)
        return _read_csv(zf, path) if path else pd.DataFrame()

    # ── Core CSVs ──────────────────────────────────────────────────────────
    profile_df   = read("profile.csv")
    ratings_df   = read("ratings.csv")
    watched_df   = read("watched.csv")
    watchlist_df = read("watchlist.csv")
    diary_df     = read("diary.csv")
    reviews_df   = read("reviews.csv")
    liked_df     = read("likes/films.csv")

    # ── User's custom lists ────────────────────────────────────────────────
    list_paths = _find_paths_in_folder(zf, "lists")
    # Exclude deleted/lists – only top-level lists folder
    list_paths = [p for p in list_paths if "deleted" not in p.lower()]

    lists = {}
    for path in list_paths:
        list_name = PurePosixPath(path).stem  # filename without .csv
        df = _read_csv(zf, path)
        if not df.empty:
            lists[list_name] = df

    return {
        "profile":     _parse_profile(profile_df),
        "ratings":     _parse_ratings(ratings_df),
        "watched":     _parse_simple_films(watched_df),
        "watchlist":   _parse_simple_films(watchlist_df),
        "diary":       _parse_diary(diary_df),
        "reviews":     _parse_reviews(reviews_df),
        "liked_films": _parse_simple_films(liked_df),
        "lists":       lists,
    }


# ── per-CSV parsers ────────────────────────────────────────────────────────

def _parse_profile(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    row = df.iloc[0]
    return {
        "username":     str(row.get("Username", "")).strip(),
        "given_name":   str(row.get("Given Name", "")).strip(),
        "family_name":  str(row.get("Family Name", "")).strip(),
    }


def _parse_ratings(df: pd.DataFrame) -> list[dict]:
    """
    ratings.csv columns: Date, Name, Year, Letterboxd URI, Rating
    Rating is 0.5–5.0 (half-star increments).
    """
    if df.empty:
        return []
    records = []
    for _, row in df.iterrows():
        try:
            rating = float(row.get("Rating", 0))
        except (ValueError, TypeError):
            rating = None
        records.append({
            "name":   str(row.get("Name", "")).strip(),
            "year":   str(row.get("Year", "")).strip(),
            "rating": rating,
            "uri":    str(row.get("Letterboxd URI", "")).strip(),
            "date":   str(row.get("Date", "")).strip(),
        })
    # Sort highest-rated first, then most recent
    records.sort(key=lambda x: (x["rating"] or 0, x["date"]), reverse=True)
    return records


def _parse_simple_films(df: pd.DataFrame) -> list[dict]:
    """Shared parser for watched.csv, watchlist.csv, likes/films.csv."""
    if df.empty:
        return []
    records = []
    for _, row in df.iterrows():
        records.append({
            "name": str(row.get("Name", "")).strip(),
            "year": str(row.get("Year", "")).strip(),
            "uri":  str(row.get("Letterboxd URI", "")).strip(),
            "date": str(row.get("Date", "")).strip(),
        })
    return records


def _parse_diary(df: pd.DataFrame) -> list[dict]:
    """
    diary.csv columns: Date, Name, Year, Letterboxd URI, Rating, Rewatch, Tags, Watched Date
    """
    if df.empty:
        return []
    records = []
    for _, row in df.iterrows():
        try:
            rating = float(row.get("Rating", 0))
        except (ValueError, TypeError):
            rating = None
        records.append({
            "name":         str(row.get("Name", "")).strip(),
            "year":         str(row.get("Year", "")).strip(),
            "rating":       rating,
            "rewatch":      str(row.get("Rewatch", "No")).strip().lower() == "yes",
            "tags":         str(row.get("Tags", "")).strip(),
            "watched_date": str(row.get("Watched Date", "")).strip(),
            "date":         str(row.get("Date", "")).strip(),
        })
    return records


def _parse_reviews(df: pd.DataFrame) -> list[dict]:
    """
    reviews.csv columns: Date, Name, Year, Letterboxd URI, Rating, Review, Spoiler, Tags, Watched Date
    """
    if df.empty:
        return []
    records = []
    for _, row in df.iterrows():
        review_text = str(row.get("Review", "")).strip()
        if not review_text or review_text.lower() == "nan":
            continue
        try:
            rating = float(row.get("Rating", 0))
        except (ValueError, TypeError):
            rating = None
        records.append({
            "name":   str(row.get("Name", "")).strip(),
            "year":   str(row.get("Year", "")).strip(),
            "rating": rating,
            "review": review_text,
            "tags":   str(row.get("Tags", "")).strip(),
        })
    return records


# ── taste profile builder ──────────────────────────────────────────────────

def build_taste_profile(data: dict, enriched_films: list[dict] | None = None) -> str:
    """
    Build a plain-text taste profile from parsed Letterboxd data + optional IMDB enrichment.
    This is what gets injected into the Gemini prompt.
    """
    profile   = data["profile"]
    ratings   = data["ratings"]
    watchlist = data["watchlist"]
    liked     = data["liked_films"]
    reviews   = data["reviews"]
    lists     = data["lists"]
    diary     = data["diary"]

    lines = []

    # Header
    username = profile.get("username") or profile.get("given_name") or "this user"
    lines.append(f"=== LETTERBOXD TASTE PROFILE: {username} ===\n")

    # Stats
    lines.append(
        f"Films rated: {len(ratings)} | "
        f"Watched total: {len(data['watched'])} | "
        f"Watchlist: {len(watchlist)} | "
        f"Liked: {len(liked)}"
    )

    # Top-rated films (≥ 4.5 stars)
    top_rated = [f for f in ratings if (f["rating"] or 0) >= 4.5]
    if top_rated:
        top_str = "; ".join(
            f"{f['name']} ({f['year']}, ★{f['rating']})" for f in top_rated[:15]
        )
        lines.append(f"\nLOVED — Top-rated films (≥4.5★): {top_str}")

    # Highly rated (4.0)
    four_star = [f for f in ratings if (f["rating"] or 0) == 4.0]
    if four_star:
        lines.append(
            "Liked (4★): " + "; ".join(f"{f['name']} ({f['year']})" for f in four_star[:10])
        )

    # Disliked — two tiers with explicit instruction to Gemini
    hated    = [f for f in ratings if (f["rating"] or 0) <= 1.5 and f["rating"] is not None]
    disliked = [f for f in ratings if 1.5 < (f["rating"] or 0) <= 2.5]

    if hated:
        lines.append(
            "\nHATED (≤1.5★) — avoid recommending anything similar to: "
            + "; ".join(f"{f['name']} ({f['year']})" for f in hated[:10])
        )
    if disliked:
        lines.append(
            "DISLIKED (2–2.5★) — steer away from the style/genre of: "
            + "; ".join(f"{f['name']} ({f['year']})" for f in disliked[:10])
        )

    # Negative IMDB signals — genres/directors from low-rated films
    if enriched_films:
        from collections import Counter
        bad_genres = Counter()
        bad_directors = Counter()
        low_rated_titles = {f["name"].lower() for f in (hated + disliked)}
        for film in enriched_films:
            if film.get("title", "").lower() in low_rated_titles:
                for g in film.get("Genre", "").split(","):
                    g = g.strip()
                    if g and g != "N/A":
                        bad_genres[g] += 1
                for d in film.get("Director", "").split(","):
                    d = d.strip()
                    if d and d != "N/A":
                        bad_directors[d] += 1
        if bad_genres:
            lines.append(
                "Genres correlated with low ratings: "
                + ", ".join(f"{g} ({c}x)" for g, c in bad_genres.most_common(5))
            )

    # Liked films (hearted)
    if liked:
        lines.append(
            "Hearted/liked: " + "; ".join(f"{f['name']} ({f['year']})" for f in liked[:10])
        )

    # Watchlist (what they want to see)
    if watchlist:
        lines.append(
            "Wants to watch: " + "; ".join(f"{f['name']} ({f['year']})" for f in watchlist[:10])
        )

    # Custom lists (list NAMES are a strong taste signal)
    if lists:
        lines.append("\nCustom lists:")
        for list_name, df in lists.items():
            readable = list_name.replace("-", " ").title()
            sample_films = df["Name"].dropna().tolist()[:3] if "Name" in df.columns else []
            sample_str = ", ".join(str(f) for f in sample_films)
            lines.append(f"  • \"{readable}\" ({len(df)} films): {sample_str}…")

    # Tags from diary
    all_tags = []
    for entry in diary:
        if entry.get("tags"):
            all_tags.extend([t.strip() for t in entry["tags"].split(",") if t.strip()])
    if all_tags:
        from collections import Counter
        tag_counts = Counter(all_tags).most_common(10)
        lines.append("Frequent diary tags: " + ", ".join(f"{t} ({c}x)" for t, c in tag_counts))

    # Sample reviews (in their own words — best taste signal)
    if reviews:
        lines.append("\nSample reviews:")
        for r in reviews[:3]:
            snippet = r["review"][:120].replace("\n", " ")
            lines.append(f"  {r['name']} (★{r['rating']}): \"{snippet}…\"")

    # IMDB metadata for top-rated films
    if enriched_films:
        lines.append("\nIMDB metadata (top-rated films):")
        for film in enriched_films[:10]:
            parts = [film.get("Genre",""), f"dir. {film.get('Director','')}", film.get("Runtime",""), film.get("Language","")]
            parts = [p for p in parts if p and p != "N/A"]
            if parts:
                lines.append(f"  {film['title']} ({film['year']}): {' | '.join(parts)}")

    taste_text = "\n".join(lines)

    # Cap the taste/preference section only — keeps tokens bounded
    MAX_CHARS = 6000
    if len(taste_text) > MAX_CHARS:
        taste_text = taste_text[:MAX_CHARS] + "\n… [profile truncated]"

    # Append the FULL exclusion list AFTER the cap so it's never cut off.
    # Format: compact "Title (Year)" pairs, one per line inside a block.
    exclusion = build_exclusion_block(data)
    return taste_text + "\n\n" + exclusion


def build_exclusion_block(data: dict) -> str:
    """
    Build the complete list of every film the user has already seen.
    Gemini must not recommend any of these.
    Appended separately so it's never subject to the taste-profile char cap.
    """
    seen: dict[str, str] = {}  # slug/name.lower() → "Title (Year)"

    for f in data.get("watched", []):
        key = f["name"].lower().strip()
        if key:
            seen[key] = f"{f['name']} ({f['year']})"

    for f in data.get("ratings", []):
        key = f["name"].lower().strip()
        if key:
            seen[key] = f"{f['name']} ({f['year']})"

    titles = sorted(seen.values())
    block  = ", ".join(titles)

    return (
        f"=== ALREADY SEEN — DO NOT RECOMMEND ANY OF THESE {len(titles)} FILMS ===\n"
        + block
    )


def get_watched_set(data: dict) -> set[str]:
    """Return lowercased set of all watched + rated film names."""
    watched = {f["name"].lower() for f in data.get("watched", [])}
    rated   = {f["name"].lower() for f in data.get("ratings", [])}
    return watched | rated
