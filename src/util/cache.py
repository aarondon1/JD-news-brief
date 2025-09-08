import json, time, hashlib, os
from typing import List, Dict
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Configuration via environment variables
CACHE_PATH = os.environ.get("SEEN_CACHE_PATH", "data/seen.json")
TTL_SECONDS = int(os.environ.get("SEEN_TTL_SECONDS", str(72*3600)))  # default 72h

def _now() -> int:
    return int(time.time())

def _load() -> Dict[str, int]:
    if not os.path.exists(CACHE_PATH):
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(d: Dict[str, int]) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f)

def _canonicalize(url: str) -> str:
    """Normalize URL so tracking params or http/https noise don't break de-dupe."""
    try:
        u = urlsplit(url.strip())
        scheme = "https" if u.scheme in ("http", "https") else u.scheme
        netloc = u.netloc.lower()
        path = u.path.rstrip("/")
        # drop common tracking params
        drop = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content",
                "ocid","cmpid","sref","srnd","ref"}
        q = [(k, v) for (k, v) in parse_qsl(u.query, keep_blank_values=True)
             if k.lower() not in drop]
        query = urlencode(q, doseq=True)
        return urlunsplit((scheme, netloc, path, query, ""))  # strip fragment
    except Exception:
        return url.strip()

def url_key(url: str) -> str:
    return hashlib.sha256(_canonicalize(url).encode("utf-8")).hexdigest()

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

def mark_seen(items: List[dict]) -> None:
    """Record items as seen without filtering (useful when you 'ignore-cache' but still
    want later runs to de-dupe)."""
    cache = _load()
    now = _now()
    for it in items:
        cache[url_key(it["url"])] = now
    _save(cache)
