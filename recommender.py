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
        blocks.append({"number": number, "title": title, "year": year, "body": block})

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


GEMINI_MODEL = "gemini-2.5-flash"
MAX_RETRIES  = 2

SYSTEM_PROMPT = """You are Watchwise, an expert AI movie recommendation assistant with encyclopedic knowledge of world cinema.

Your task: Given a user's Letterboxd taste profile and optional TMDB metadata analysis, answer their movie query with tailored recommendations. In conversation mode, use prior exchanges as context to refine your suggestions.

Rules:
- Recommend exactly 5 films unless the user asks for more or fewer.
- For each film provide:
    • **Title (Year)** — Director
    • Genre | Runtime | Language/Country
    • One sentence on why it matches the QUERY.
    • One sentence connecting it to THIS USER'S specific taste (reference their actual ratings, lists, or reviews).
- Do NOT recommend any film the user has already seen (the ALREADY SEEN list is provided).
- AVOID genres, styles, and directors associated with the user's HATED or DISLIKED films.
- In conversation mode: if the user says "more like #3" or "make them more obscure", adjust accordingly while keeping the taste profile in mind.
- Prefer hidden gems and niche picks over obvious blockbusters when the profile suggests a cinephile.
- Format output as a clean numbered list.
- End with a short "Taste note:" paragraph (2-3 sentences) explaining what you inferred about the user's style.

If no taste profile is provided, make strong general recommendations with brief justifications.
"""


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


def _call_gemini(client, contents) -> str:
    """contents can be a plain string OR a list of role/parts dicts for multi-turn."""
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
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
    api_key: str = "",
) -> tuple[str, list[str]]:
    """
    Generate recommendations with optional conversation history for multi-turn mode.

    conversation_history is a list of:
      {"role": "user" | "assistant", "content": str}
    representing prior exchanges in the session (NOT including the current query).

    Returns (final_text, replaced_titles).
    """
    if not api_key:
        raise ValueError("Google Gemini API key is required.")

    client = genai.Client(api_key=api_key)

    # Build the context prefix (taste profile + TMDB summary)
    context_parts = []
    if taste_profile:
        context_parts.append(taste_profile)
    if imdb_summary:
        context_parts.append(imdb_summary)
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

    text = _call_gemini(client, full_prompt)

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
            # Append correction as a new user message
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
        text = _call_gemini(client, full_prompt)

    return text, replaced