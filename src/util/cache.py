import json, time, hashlib, os
from typing import List, Dict

# Configuration via environment variables
CACHE_PATH = os.environ.get("SEEN_CACHE_PATH", "data/seen.json")
TTL_SECONDS = int(os.environ.get("SEEN_TTL_SECONDS", str(72*3600)))  # default 72h

# Helpers for cache of seen URLs with timestamps
def _now() -> int:
    return int(time.time())

# Load or initialize the cache
def _load() -> Dict[str, int]:
    if not os.path.exists(CACHE_PATH):
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# Save the cache back to disk
def _save(d: Dict[str, int]) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f)

# Create a hash key for a URL
def url_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()

# Filter items to only those not seen in the last TTL_SECONDS
def filter_new(items: List[dict]) -> List[dict]:
    cache = _load()
    now = _now()

    # purge expired
    expired = [k for k, ts in cache.items() if now - ts > TTL_SECONDS]
    for k in expired:
        cache.pop(k, None)

    fresh = []
    for it in items:
        key = url_key(it["url"])
        if key not in cache:
            cache[key] = now
            fresh.append(it)

    _save(cache)
    return fresh
