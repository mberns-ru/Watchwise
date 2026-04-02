# db.py
import json
import os
from supabase import create_client


def get_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ── Auth ──────────────────────────────────────────────────────────────────────

def sign_up(email: str, password: str) -> dict:
    """Register a new user. Returns {"user": ..., "error": None} or {"user": None, "error": str}."""
    try:
        client = get_client()
        res = client.auth.sign_up({"email": email, "password": password})
        if res.user:
            return {"user": res.user, "session": res.session, "error": None}
        return {"user": None, "session": None, "error": "Sign-up failed — please try again."}
    except Exception as e:
        return {"user": None, "session": None, "error": str(e)}


def sign_in(email: str, password: str) -> dict:
    """Sign in an existing user."""
    try:
        client = get_client()
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            return {"user": res.user, "session": res.session, "error": None}
        return {"user": None, "session": None, "error": "Invalid email or password."}
    except Exception as e:
        msg = str(e)
        if "Invalid login credentials" in msg:
            return {"user": None, "session": None, "error": "Invalid email or password."}
        return {"user": None, "session": None, "error": msg}


def sign_out(access_token: str):
    try:
        client = get_client()
        client.auth.sign_out()
    except Exception:
        pass


# ── Profile ───────────────────────────────────────────────────────────────────

def load_profile(email: str) -> dict | None:
    client = get_client()
    res = client.table("profiles").select("*").eq("user_email", email).execute()
    if res.data:
        row = res.data[0]
        meta = row.get("profile_meta")
        if isinstance(meta, str):
            meta = json.loads(meta)
        return {
            "username":       row.get("username"),
            "taste_profile":  row.get("taste_profile"),
            "imdb_summary":   row.get("imdb_summary"),
            "enriched_films": json.loads(row["enriched_films"])
                               if row.get("enriched_films") else [],
            "profile_meta":   meta or {},
        }
    return None


def save_profile(email: str, username: str, taste_profile: str,
                 enriched_films: list, imdb_summary: str,
                 profile_meta: dict | None = None):
    client = get_client()
    client.table("profiles").upsert({
        "user_email":     email,
        "username":       username,
        "taste_profile":  taste_profile,
        "imdb_summary":   imdb_summary,
        "enriched_films": json.dumps(enriched_films),
        "profile_meta":   json.dumps(profile_meta or {}),
        "updated_at":     "now()",
    }, on_conflict="user_email").execute()