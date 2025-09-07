import feedparser, html
from typing import List, Dict

# Fetch and parse RSS feed, return list of items with title, url, dek (brief summary)
def fetch_rss(url: str, limit: int = 10) -> List[Dict]:
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries[:limit]:
        title = html.unescape(getattr(e, "title", "") or "")
        link = getattr(e, "link", "") or ""
        summary = html.unescape(getattr(e, "summary", "") or getattr(e, "description", "") or "")
        out.append({"title": title.strip(), "url": link.strip(), "dek": summary.strip()})
    return out
