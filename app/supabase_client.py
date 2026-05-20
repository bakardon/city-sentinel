import os
from typing import Optional

from supabase import Client, create_client


def _load_env_file() -> None:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = []
    custom = os.getenv("SUPABASE_ENV_FILE")
    if custom:
        candidates.append(custom)
    candidates.append(os.path.join(base_dir, ".env"))
    candidates.append(os.path.join(base_dir, "supabase.env"))
    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    value = line.strip()
                    if not value or value.startswith("#") or "=" not in value:
                        continue
                    key, raw = value.split("=", 1)
                    key = key.strip()
                    raw = raw.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = raw
        except Exception:
            pass


_load_env_file()


def _get_supabase_url() -> Optional[str]:
    return os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PROJECT_URL")


def _get_supabase_key() -> Optional[str]:
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_ANON_PUBLIC_KEY")
    )


def _get_supabase_admin_key() -> Optional[str]:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")


def get_supabase() -> Optional[Client]:
    url = _get_supabase_url()
    key = _get_supabase_key()
    if not url or not key:
        return None
    return create_client(url, key)


def get_supabase_admin() -> Optional[Client]:
    url = _get_supabase_url()
    key = _get_supabase_admin_key()
    if not url or not key:
        return None
    return create_client(url, key)
