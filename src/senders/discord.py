import os, requests, logging

# Send a brief text message to a Discord channel via webhook
def send_discord(content: str) -> None:
    url = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url:
        return
    # Discord hard limit ~2000 chars; we keep it under that
    data = {"content": content[:1800]}
    try:
        requests.post(url, json=data, timeout=10)
    except Exception:
        # best-effort channel
        pass
