import re, requests
from typing import List, Dict
from html import unescape
from urllib.parse import urljoin
from requests.exceptions import RequestException

DEFAULT_HEADERS = {
    # A normal desktop browser UA helps with basic bot filters
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}

def fetch_html_list(url: str, limit: int = 10, headers: Dict[str, str] | None = None) -> List[Dict]:
    """Best-effort list-page fetcher. Prefer RSS when available.
       Returns [] on 403/429/Network errors so the pipeline continues.
    """
    try:
        r = requests.get(
            url, timeout=12,
            headers={**DEFAULT_HEADERS, **(headers or {})},
            allow_redirects=True,
        )
        # Treat hard blocks as "no items" instead of raising
        if r.status_code in (403, 429):
            return []
        r.raise_for_status()
    except RequestException:
        return []

    page = r.text

    # NOTE: Correct regex (only one backslash before 's').
    # If your previous file had r'<a\\s...>', replace it with r'<a\s...>'
    candidates = re.findall(
        r'<a\s[^>]*href="([^"]+)"[^>]*>([^<]{20,140})</a>', page, flags=re.I
    )

    seen = set()
    out: List[Dict] = []
    for href, text in candidates:
        text = unescape(text).strip()
        if not text or len(text.split()) < 3:
            continue
        if href.startswith("/"):
            href = urljoin(url, href)
        key = (href, text)
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": text, "url": href, "dek": ""})
        if len(out) >= limit:
            break
    return out
