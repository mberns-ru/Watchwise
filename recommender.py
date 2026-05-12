"""
recommender.py
Calls the Google Gemini API to generate personalized movie recommendations.
Supports single-turn and multi-turn (conversation) mode.
"""

import re
from google import genai
from google.genai import types


def parse_rec_blocks(text: str) -> tuple[list[dict], str]:
    raw_blocks = re.split(r'\n(?=\d+[\.\)]\s)', text.strip())
    blocks, taste_note = [], ""

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        if not re.match(r'^\d+[\.\)]', block):
            taste_note = block
            continue

        first_line       = block.splitlines()[0]
        first_line_clean = re.sub(r'^\d+[\.\)]\s*', '', first_line).replace("**", "")
        title_part       = re.split(r'\s[—–-]\s', first_line_clean)[0].strip()
        year_match       = re.search(r'\((\d{4})\)', title_part)
        year             = year_match.group(1) if year_match else None
        title            = re.sub(r'\s*\(\d{4}\)', '', title_part).strip()
        num_match        = re.match(r'^(\d+)', block)
        number           = int(num_match.group(1)) if num_match else len(blocks) + 1
        # Detect community pick — Gemini was told to tag it with this string
        is_community     = ("👥" in block) or ("loved by similar watchwise users" in block.lower())
        blocks.append({
            "number":       number,
            "title":        title,
            "year":         year,
            "body":         block,
            "is_community": is_community,
        })

    if blocks:
        last = blocks[-1]
        taste_match = re.search(
            r'\n\n\*{0,2}Taste note\*{0,2}[:\s]+(.+)',
            last["body"], re.DOTALL | re.IGNORECASE,
        )
        if taste_match:
            blocks[-1]["body"] = last["body"][:taste_match.start()].strip()
            taste_note = "Taste note: " + taste_match.group(1).strip()

    return blocks, taste_note


COMMUNITY_PICK_RULE = """
COMMUNITY PICK RULE:
- If a "FILMS LOVED BY SIMILAR WATCHWISE USERS" section is provided, scan it against the current query's genre, mood, and constraints (runtime, language, era, etc.).
- If ONE of those films genuinely fits the query, include it among the 5 recommendations and mark it with `👥 _Loved by similar Watchwise users_` on the line immediately after its title line.
- If NONE of the community candidates fit the query well, skip this rule entirely — recommend all 5 from your own knowledge. Do not force a poor fit.
- Never include the same community film twice across consecutive turns if the query has changed significantly.
"""
GEMINI_MODEL = "gemini-2.5-flash"
MAX_RETRIES  = 2

SYSTEM_PROMPT = """You are Watchwise, an expert AI movie recommendation assistant with encyclopedic knowledge of world cinema.

Your task: Given a user's Letterboxd taste profile and optional TMDB metadata analysis, answer their movie query with tailored recommendations. In conversation mode, use prior exchanges as context to refine your suggestions.

Rules:
- Recommend exactly 5 films unless the user asks for more or fewer.
- For each film use this EXACT format (the number MUST come first, outside any bold markers):

    N. **Title (Year)** — Director
    - 🎬 Genre | Runtime | Language / Country
    - 🔍 One sentence on why it matches the query (no label prefix).
    - 💡 One sentence on why it suits this user's taste, referencing their actual ratings, lists, or reviews (no label prefix).

- Do NOT recommend any film the user has already seen (the ALREADY SEEN list is provided).
- AVOID genres, styles, and directors associated with the user's HATED or DISLIKED films.
- In conversation mode: if the user says "more like #3" or "make them more obscure", adjust accordingly while keeping the taste profile in mind.
- Prefer hidden gems and niche picks over obvious blockbusters when the profile suggests a cinephile.
- End with a short "Taste note:" paragraph (2-3 sentences) explaining what you inferred about the user's style.
""" + COMMUNITY_PICK_RULE + """
If no taste profile is provided, make strong general recommendations with brief justifications.
"""

WATCH_TOGETHER_SYSTEM_PROMPT = """You are Watchwise, an expert AI movie recommendation assistant with encyclopedic knowledge of world cinema.

Your task: Two users want to watch a movie TOGETHER. You have been given BOTH of their Letterboxd taste profiles. Your job is to find films that genuinely appeal to both — not a compromise, but something each would actually be excited about.

Rules:
- Recommend exactly 5 films unless asked otherwise.
- For each film use this EXACT format (the number MUST come first, outside any bold markers):

    N. **Title (Year)** — Director
    - 🎬 Genre | Runtime | Language / Country
    - 🔍 One sentence on why it matches the query (no label prefix).
    - 💡 One sentence on the shared taste overlap, referencing specific ratings, lists, or genres (no label prefix).
- Do NOT recommend any film either user has already seen.
- Avoid genres or styles that either user has rated poorly.
- Look for genuine overlap: shared high ratings, complementary taste signals, list names that suggest common ground.
- Format output as a clean numbered list.
- End with a short "Taste note:" paragraph noting the interesting overlaps (and tensions) between their two profiles.
""" + COMMUNITY_PICK_RULE


# ─────────────────────────────────────────────────────────────────────────────
#  Similar-Watchwise-users helpers
# ─────────────────────────────────────────────────────────────────────────────

def find_similar_users_films(
    my_enriched_films: list[dict] | None,
    all_profiles: list[dict] | None,
    watched_set: set[str] | None = None,
    top_users_n: int = 10,
    top_films_n: int = 30,
    min_rating: float = 3.5,
) -> list[dict]:
    """
    Find candidate films loved by similar Watchwise users.

    Similarity = number of overlapping high-rated titles (≥min_rating★),
    broken by Jaccard index. Returns a ranked list of candidate films
    the current user has NOT seen:
        [{"title", "year", "liked_by": [usernames], "ratings": [floats]}, ...]
    """
    if not my_enriched_films or not all_profiles:
        return []

    def _high_rated(films: list[dict]) -> dict[str, dict]:
        out = {}
        for f in films or []:
            try:
                r = float(f.get("rating") or 0)
            except (TypeError, ValueError):
                r = 0.0
            t = (f.get("title") or "").lower().strip()
            if r >= min_rating and t:
                out[t] = f
        return out

    my_high = _high_rated(my_enriched_films)
    if not my_high:
        return []
    my_high_set = set(my_high.keys())

    # Score every other user by overlap — use same threshold (3.5★)
    scored = []
    for prof in all_profiles:
        their_high = _high_rated(prof.get("enriched_films") or [])
        if not their_high:
            continue
        their_set = set(their_high.keys())
        overlap = my_high_set & their_set
        if not overlap:
            continue
        union = my_high_set | their_set
        jaccard = len(overlap) / len(union) if union else 0.0
        scored.append({
            "username":    prof.get("username") or prof.get("slug") or "",
            "slug":        prof.get("slug") or "",
            "overlap_n":   len(overlap),
            "jaccard":     jaccard,
            "their_high":  their_high,
        })

    if not scored:
        return []

    scored.sort(key=lambda x: (x["overlap_n"], x["jaccard"]), reverse=True)
    top_users = scored[:top_users_n]

    watched = watched_set or set()
    candidates: dict[str, dict] = {}

    for user in top_users:
        for title_l, film in user["their_high"].items():
            # Skip anything I've already seen or rated highly myself
            if title_l in my_high_set or title_l in watched:
                continue
            if title_l not in candidates:
                candidates[title_l] = {
                    "title":    film.get("title", ""),
                    "year":     film.get("year", ""),
                    "liked_by": [],
                    "ratings":  [],
                }
            candidates[title_l]["liked_by"].append(user["username"])
            try:
                candidates[title_l]["ratings"].append(float(film.get("rating") or 0))
            except (TypeError, ValueError):
                pass

    # Rank: films liked by more similar users float to the top,
    # then by average rating.
    ranked = sorted(
        candidates.values(),
        key=lambda c: (
            len(c["liked_by"]),
            sum(c["ratings"]) / len(c["ratings"]) if c["ratings"] else 0.0,
        ),
        reverse=True,
    )
    return ranked[:top_films_n]


def build_similar_users_block(candidates: list[dict]) -> str:
    """Format similar-user film candidates for injection into the LLM prompt."""
    if not candidates:
        return ""
    lines = [
        "=== FILMS LOVED BY SIMILAR WATCHWISE USERS ===",
        "These films are highly rated (≥4★) by other Watchwise users whose "
        "taste profiles overlap with this user's, and that this user has NOT seen. "
        "You MUST pick exactly one of these to include among the 5 recommendations:",
    ]
    for c in candidates:
        liked = ", ".join(f"@{u}" for u in c["liked_by"][:3] if u)
        if len(c["liked_by"]) > 3:
            liked += f" (+{len(c['liked_by']) - 3} more)"
        avg = sum(c["ratings"]) / len(c["ratings"]) if c["ratings"] else 0.0
        yr  = f" ({c['year']})" if c.get("year") else ""
        lines.append(f"  • {c['title']}{yr} — liked by {liked} · avg ★{avg:.1f}")
    return "\n".join(lines)


def _extract_titles(text: str) -> list[str]:
    titles = []
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped and stripped[0].isdigit() and stripped[1:3] in (". ", ") ")):
            continue
        content = re.sub(r"^\d+[\.\)]\s*", "", stripped).replace("**", "")
        content = re.split(r"\s[—–-]\s", content)[0].strip()
        title   = re.sub(r"\s*\(\d{4}\)\s*$", "", content).strip().lower()
        if title:
            titles.append(title)
    return titles


def _find_seen(titles, watched_set):
    return [t for t in titles if t in watched_set]


def _call_gemini(client, contents, system_instruction: str = SYSTEM_PROMPT) -> str:
    """contents can be a plain string OR a list of role/parts dicts for multi-turn."""
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=8192,
        ),
    )
    return response.text


def get_recommendations(
    query: str,
    taste_profile: str | None = None,
    imdb_summary: str | None = None,
    watched_set: set[str] | None = None,
    conversation_history: list[dict] | None = None,
    friend_taste_profile: str | None = None,
    similar_users_block: str | None = None,
    api_key: str = "",
) -> tuple[str, list[str]]:
    """
    Generate recommendations with optional conversation history for multi-turn mode.

    conversation_history is a list of:
      {"role": "user" | "assistant", "content": str}
    representing prior exchanges in the session (NOT including the current query).

    similar_users_block is a pre-formatted context block (from
    build_similar_users_block) containing films loved by users with overlapping
    taste. When provided, the system prompt instructs Gemini to include exactly
    one of those films among the 5 picks and tag it.

    Returns (final_text, replaced_titles).
    """
    if not api_key:
        raise ValueError("Google Gemini API key is required.")

    client = genai.Client(api_key=api_key)

    # Choose system prompt based on mode
    system = WATCH_TOGETHER_SYSTEM_PROMPT if friend_taste_profile else SYSTEM_PROMPT

    # Build the context prefix
    context_parts = []
    if taste_profile and friend_taste_profile:
        context_parts.append("=== YOUR TASTE PROFILE ===\n" + taste_profile)
        context_parts.append("=== FRIEND'S TASTE PROFILE ===\n" + friend_taste_profile)
    elif taste_profile:
        context_parts.append(taste_profile)
    if imdb_summary:
        context_parts.append(imdb_summary)
    if similar_users_block:
        context_parts.append(similar_users_block)
    context = "\n\n".join(context_parts)

    if conversation_history:
        # ── Multi-turn: build a message list ──────────────────────────────────
        # First user message includes the full context + their original query
        messages = []
        for i, turn in enumerate(conversation_history):
            role = "user" if turn["role"] == "user" else "model"
            msg_text = turn["content"]
            # Prepend context to the very first user message
            if i == 0 and context:
                msg_text = f"{context}\n\n=== USER QUERY ===\n{msg_text}"
            messages.append({"role": role, "parts": [{"text": msg_text}]})
        # Append the new query
        messages.append({"role": "user", "parts": [{"text": f"=== USER QUERY ===\n{query}"}]})
        full_prompt = messages
    else:
        # ── Single-turn: plain string prompt ──────────────────────────────────
        sections = []
        if context:
            sections.append(context)
        sections.append(f"=== USER QUERY ===\n{query}")
        full_prompt = "\n\n".join(sections)

    text = _call_gemini(client, full_prompt, system)

    # ── Retry loop: replace already-seen films ───────────────────────────────
    replaced = []
    for _ in range(MAX_RETRIES):
        if not watched_set:
            break
        seen_now = _find_seen(_extract_titles(text), watched_set)
        if not seen_now:
            break
        replaced.extend(seen_now)
        seen_str = ", ".join(f'"{t.title()}"' for t in seen_now)

        if isinstance(full_prompt, list):
            correction = (
                f"Your previous response included {seen_str}, which the user has already seen. "
                f"Please provide the full 5-film list again, replacing those with unseen films. "
                f"Keep all other recommendations.\n\nPrevious response:\n{text}"
            )
            full_prompt = full_prompt + [{"role": "user", "parts": [{"text": correction}]}]
        else:
            full_prompt = (
                f"{full_prompt}\n\n=== CORRECTION NEEDED ===\n"
                f"Your previous response included {seen_str}, which the user has already seen. "
                f"Please provide the full 5-film list again, replacing those with unseen films.\n\n"
                f"Previous response:\n{text}"
            )
        text = _call_gemini(client, full_prompt, system)

    return text, replaced