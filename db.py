# db.py
import json
import os
from supabase import create_client


def get_client():
    """Create a Supabase client. Reads env vars at call time so load_dotenv() has already run."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def load_profile(email: str) -> dict | None:
    client = get_client()
    res = client.table("profiles").select("*").eq("user_email", email).execute()
    if res.data:
        row = res.data[0]
        return {
            "username":       row.get("username"),
            "taste_profile":  row.get("taste_profile"),
            "imdb_summary":   row.get("imdb_summary"),
            "enriched_films": json.loads(row["enriched_films"])
                               if row.get("enriched_films") else [],
        }
    return None


def save_profile(email: str, username: str, taste_profile: str,
                 enriched_films: list, imdb_summary: str):
    client = get_client()
    client.table("profiles").upsert({
        "user_email":     email,
        "username":       username,
        "taste_profile":  taste_profile,
        "imdb_summary":   imdb_summary,
        "enriched_films": json.dumps(enriched_films),
        "updated_at":     "now()",
    }, on_conflict="user_email").execute()