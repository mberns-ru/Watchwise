"""
recommender.py
Calls the Google Gemini API to generate personalized movie recommendations,
with an automatic retry loop that replaces any already-seen films.
"""

import re
from google import genai
from google.genai import types


def parse_rec_blocks(text: str) -> tuple[list[dict], str]:
    """
    Split Gemini's numbered recommendation text into individual blocks.
    Returns (blocks, taste_note) where blocks is a list of:
      {number, title, year, body}
    """
    raw_blocks = re.split(r'\n(?=\d+[\.\)]\s)', text.strip())

    blocks     = []
    taste_note = ""

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        # Non-numbered block = Taste note or preamble
        if not re.match(r'^\d+[\.\)]', block):
            taste_note = block
            continue

        first_line       = block.splitlines()[0]
        first_line_clean = re.sub(r'^\d+[\.\)]\s*', '', first_line).replace("**", "")
        title_part       = re.split(r'\s[—–-]\s', first_line_clean)[0].strip()

        year_match = re.search(r'\((\d{4})\)', title_part)
        year  = year_match.group(1) if year_match else None
        title = re.sub(r'\s*\(\d{4}\)', '', title_part).strip()

        num_match = re.match(r'^(\d+)', block)
        number    = int(num_match.group(1)) if num_match else len(blocks) + 1

        blocks.append({"number": number, "title": title, "year": year, "body": block})

    # The taste note often gets appended to the last block since it's not
    # preceded by a number. Strip it out of the last block's body.
    if blocks:
        last = blocks[-1]
        taste_match = re.search(
            r'\n\n(\*{0,2}Taste note[:\*].*)',
            last["body"], re.DOTALL | re.IGNORECASE
        )
        if taste_match:
            blocks[-1]["body"] = last["body"][:taste_match.start()].strip()
            taste_note = taste_match.group(1).strip().lstrip("*").rstrip("*").strip()

    return blocks, taste_note


GEMINI_MODEL = "gemini-2.5-flash"
MAX_RETRIES  = 2   # max replacement passes (each costs 1 Gemini call)

SYSTEM_PROMPT = """You are Watchwise, an expert AI movie recommendation assistant with encyclopedic knowledge of world cinema.

Your task: Given a user's Letterboxd taste profile (ratings, lists, tags, reviews) and optional IMDB metadata analysis, answer their movie query with tailored recommendations.

Rules:
- Recommend exactly 5 films unless the user asks for more or fewer.
- For each film provide:
    • **Title (Year)** — Director
    • Genre | Runtime | Language/Country
    • One sentence on why it matches the QUERY.
    • One sentence connecting it to THIS USER'S specific taste (reference their actual ratings, lists, or reviews).
- Do NOT recommend any film the user has already seen (the ALREADY SEEN list is provided).
- AVOID genres, styles, and directors associated with the user's HATED or DISLIKED films.
- Favor films that match patterns in the user's LOVED films (genres, languages, directors, eras).
- Prefer hidden gems and niche picks over obvious blockbusters when the profile suggests a cinephile.
- Format output as a clean numbered list.
- End with a short "Taste note:" paragraph (2-3 sentences) explaining what you inferred about the user's style, including what they seem to dislike.

If no taste profile is provided, make strong general recommendations with brief justifications.
"""


# ── Title extraction ────────────────────────────────────────────────────────

def _extract_titles(text: str) -> list[str]:
    """
    Pull the film title from each numbered recommendation line.
    Handles formats like:
      1. **The Vanishing (1988)** — George Sluizer
      1. The Vanishing (1988) — George Sluizer
    Returns a list of lowercase title strings (without year).
    """
    titles = []
    for line in text.splitlines():
        stripped = line.strip()
        # Must start with a digit and look like a list item
        if not (stripped and stripped[0].isdigit() and stripped[1:3] in (". ", ") ")):
            continue
        # Strip leading "1. " / "1) "
        content = re.sub(r"^\d+[\.\)]\s*", "", stripped)
        # Strip markdown bold
        content = content.replace("**", "")
        # Grab everything before " — " or " - " (the director separator)
        content = re.split(r"\s[—–-]\s", content)[0].strip()
        # Remove year in parentheses at the end: "The Vanishing (1988)" → "The Vanishing"
        title = re.sub(r"\s*\(\d{4}\)\s*$", "", content).strip().lower()
        if title:
            titles.append(title)
    return titles


def _find_seen(titles: list[str], watched_set: set[str]) -> list[str]:
    """Return any extracted titles that appear in the watched set."""
    seen = []
    for t in titles:
        if t in watched_set:
            seen.append(t)
    return seen


# ── Core API call ───────────────────────────────────────────────────────────

def _call_gemini(client, prompt: str) -> str:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=8192,
        ),
    )
    return response.text


# ── Main entry point ────────────────────────────────────────────────────────

def get_recommendations(
    query: str,
    taste_profile: str | None = None,
    imdb_summary: str | None = None,
    watched_set: set[str] | None = None,
    api_key: str = "",
) -> tuple[str, list[str]]:
    """
    Generate recommendations, then iteratively replace any already-seen films.

    Returns:
        (final_text, replaced_titles)  — replaced_titles lists films that were
        swapped out, so the UI can show "replaced X with Y" info if desired.
    """
    if not api_key:
        raise ValueError("Google Gemini API key is required.")

    client = genai.Client(api_key=api_key)

    # ── Initial request ─────────────────────────────────────────────────────
    sections = []
    if taste_profile:
        sections.append(taste_profile)
    if imdb_summary:
        sections.append(imdb_summary)
    sections.append(f"=== USER QUERY ===\n{query}")
    full_prompt = "\n\n".join(sections)

    text = _call_gemini(client, full_prompt)

    # ── Retry loop ──────────────────────────────────────────────────────────
    replaced = []

    for attempt in range(MAX_RETRIES):
        if not watched_set:
            break

        titles   = _extract_titles(text)
        seen_now = _find_seen(titles, watched_set)

        if not seen_now:
            break  # clean — we're done

        replaced.extend(seen_now)

        # Build a targeted replacement prompt
        seen_str = ", ".join(f'"{t.title()}"' for t in seen_now)
        retry_prompt = (
            f"{full_prompt}\n\n"
            f"=== CORRECTION NEEDED ===\n"
            f"Your previous response included {seen_str}, which the user has already seen. "
            f"Please provide your full 5-film recommendation list again, "
            f"replacing {seen_str} with different films the user has NOT seen. "
            f"Keep all other recommendations the same if they are not on the seen list.\n\n"
            f"Previous response:\n{text}"
        )

        text = _call_gemini(client, retry_prompt)

    return text, replaced