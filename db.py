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
    try:
        client = get_client()
        res = client.auth.sign_up({"email": email, "password": password})
        if res.user:
            return {"user": res.user, "session": res.session, "error": None}
        return {"user": None, "session": None, "error": "Sign-up failed — please try again."}
    except Exception as e:
        return {"user": None, "session": None, "error": str(e)}


def sign_in(email: str, password: str) -> dict:
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


def sign_in_with_google(redirect_url: str) -> dict:
    """Return the Google OAuth redirect URL."""
    try:
        client = get_client()
        res = client.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {"redirect_to": redirect_url},
        })
        return {"url": res.url, "error": None}
    except Exception as e:
        return {"url": None, "error": str(e)}


def get_session_from_tokens(access_token: str, refresh_token: str) -> dict:
    """Exchange OAuth tokens for a session after Google redirect."""
    try:
        client = get_client()
        res = client.auth.set_session(access_token, refresh_token)
        if res.user:
            return {"user": res.user, "error": None}
        return {"user": None, "error": "Could not establish session."}
    except Exception as e:
        return {"user": None, "error": str(e)}


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
            "is_public":      row.get("is_public", False),
            "slug":           row.get("slug"),
        }
    return None


def save_profile(email: str, username: str, taste_profile: str,
                 enriched_films: list, imdb_summary: str,
                 profile_meta: dict | None = None,
                 is_public: bool = False,
                 slug: str | None = None):
    client = get_client()
    client.table("profiles").upsert({
        "user_email":     email,
        "username":       username,
        "taste_profile":  taste_profile,
        "imdb_summary":   imdb_summary,
        "enriched_films": json.dumps(enriched_films),
        "profile_meta":   json.dumps(profile_meta or {}),
        "is_public":      is_public,
        "slug":           slug.lower() if slug else None,
        "updated_at":     "now()",
    }, on_conflict="user_email").execute()


def set_profile_public(email: str, is_public: bool, slug: str | None = None):
    """Toggle a profile's public visibility."""
    client = get_client()
    client.table("profiles").update({
        "is_public": is_public,
        "slug":      slug.lower() if (is_public and slug) else None,
    }).eq("user_email", email).execute()


def get_public_profile(slug: str) -> dict | None:
    """Fetch a public profile by its slug."""
    client = get_client()
    res = (
        client.table("profiles")
        .select("*")
        .eq("slug", slug.lower())
        .eq("is_public", True)
        .execute()
    )
    if res.data:
        row = res.data[0]
        meta = row.get("profile_meta")
        if isinstance(meta, str):
            meta = json.loads(meta)
        return {
            "username":       row.get("username") or slug,
            "taste_profile":  row.get("taste_profile"),
            "imdb_summary":   row.get("imdb_summary"),
            "enriched_films": json.loads(row["enriched_films"])
                               if row.get("enriched_films") else [],
            "profile_meta":   meta or {},
            "slug":           row.get("slug"),
        }
    return None