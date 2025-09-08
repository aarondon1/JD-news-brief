import os, yaml, time, argparse
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv

from src.ingest.rss import fetch_rss
from src.ingest.html_list import fetch_html_list
from src.summarize.sonar import SonarSummarizer
from src.util.cache import filter_new, mark_seen
from src.format.html import render_html, render_text
from src.senders.discord import send_discord
# from src.senders.whatsapp_cloud import send_whatsapp_brief  # enable later


# ------------------------------- keyword filter -------------------------------

def _parse_keywords(s: str | None) -> List[str]:
    if not s:
        return []
    raw = [x.strip().lower() for x in s.replace(";", ",").split(",")]
    return [x for x in raw if x]

def _should_keep(item: Dict, includes: List[str], excludes: List[str]) -> bool:
    text = f"{item.get('title','')} {item.get('dek','')}".lower()
    if excludes and any(x in text for x in excludes):
        return False
    if includes:
        return any(x in text for x in includes)
    return True

def _apply_keyword_filter(items: List[Dict], include_s: str | None, exclude_s: str | None) -> List[Dict]:
    includes = _parse_keywords(include_s) if include_s is not None else []
    excludes = _parse_keywords(exclude_s) if exclude_s is not None else []

    # Defaults only if both are empty/omitted
    if not includes and include_s is None:
        includes = _parse_keywords("Fed,CPI,earnings")
    if not excludes and exclude_s is None:
        excludes = _parse_keywords("opinion")

    return [it for it in items if _should_keep(it, includes, excludes)]


# --------------------------------- logging ------------------------------------

def _now_local():
    tz_name = os.getenv("TZ")
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(tz_name))
        except Exception:
            pass
    return datetime.now()

def _log_brief(plaintext: str, outdir: str = "data") -> str:
    os.makedirs(outdir, exist_ok=True)
    stamp = _now_local().strftime("%Y%m%d_%H%M%S")
    day = _now_local().strftime("%Y%m%d")
    path = os.path.join(outdir, f"brief-{day}.txt")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n=== Run {stamp} ===\n")
        f.write(plaintext.strip() + "\n")
    return path


# --------------------------------- ingest -------------------------------------

def load_feeds(path: str = "feeds.yml") -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def collect_items(feeds: List[Dict], per_source: int, debug: bool = False) -> List[Dict]:
    items: List[Dict] = []
    for f in feeds:
        t = f.get("type", "rss")
        url = f["url"]
        name = f["name"]
        try:
            got = fetch_rss(url, per_source) if t == "rss" else fetch_html_list(url, per_source)
            for g in got:
                g["source"] = name
                items.append(g)
        except Exception as e:
            if debug:
                print(f"[ingest] skipped {name} ({url}) due to: {e}")
            continue
    return items

def _limit_total(items: List[Dict], max_total: int | None) -> List[Dict]:
    if not max_total or max_total <= 0:
        return items
    return items[:max_total]


# --------------------------------- CLI args -----------------------------------

def _parse_args():
    p = argparse.ArgumentParser(description="Morning brief runner")
    p.add_argument("--max-per-source", type=int, default=None, help="Override MAX_ITEMS_PER_SOURCE")
    p.add_argument("--max-total", type=int, default=None, help="Cap total items after filtering/dedupe")
    p.add_argument("--include", type=str, default=None, help="Comma/semicolon list of include keywords")
    p.add_argument("--exclude", type=str, default=None, help="Comma/semicolon list of exclude keywords")
    p.add_argument("--ignore-cache", action="store_true", help="Bypass dedupe (send even if seen before)")
    p.add_argument("--no-filter", action="store_true", help="Disable keyword filtering")
    p.add_argument("--dry-run", action="store_true", help="Do everything except send to Discord/WhatsApp")
    p.add_argument("--debug", action="store_true", help="Verbose debug logging to stdout")
    return p.parse_args()


# ----------------------------------- main -------------------------------------

def main():
    load_dotenv()
    args = _parse_args()
    debug = args.debug or bool(os.getenv("DEBUG"))

    # Defaults from env, CLI overrides if provided
    per_source = args.max_per_source or int(os.getenv("MAX_ITEMS_PER_SOURCE", "5"))
    include_env = os.getenv("INCLUDE_KEYWORDS")
    exclude_env = os.getenv("EXCLUDE_KEYWORDS")

    # Identify run source (helps in Discord + logs)
    event = os.getenv("GITHUB_EVENT_NAME", "")
    run_tag = "AUTO (schedule)" if event == "schedule" else ("MANUAL (dispatch)" if event == "workflow_dispatch" else "LOCAL")

    # 1) ingest
    feeds = load_feeds()
    if debug:
        print(f"[config] run_tag={run_tag} per_source={per_source}")
        print(f"[config] feeds= {[f['name'] for f in feeds]}")

    raw = collect_items(feeds, per_source, debug=debug)
    if debug:
        print(f"[counts] ingested={len(raw)}")

    # 2) keyword filter
    if args.no_filter:
        filtered = raw
        if debug:
            print("[filter] disabled via --no-filter")
    else:
        include_s = args.include if args.include is not None else include_env
        exclude_s = args.exclude if args.exclude is not None else exclude_env
        if debug:
            print(f"[filter] include={include_s} exclude={exclude_s}")
        filtered = _apply_keyword_filter(raw, include_s, exclude_s)

    if debug:
        print(f"[counts] after_filter={len(filtered)}")
        for it in filtered[:5]:
            print(f"  • {it.get('title','')[:90]}  [{it.get('source','')}]")

    # 3) dedupe or bypass
    if args.ignore_cache:
        fresh = filtered
        if debug:
            print("[dedupe] bypassed via --ignore-cache")
    else:
        fresh = filter_new(filtered)
        if debug:
            print(f"[dedupe] kept={len(fresh)} (cache applied)")

    # 4) optional cap on total items (before summarization to save tokens)
    capped = _limit_total(fresh, args.max_total)
    if debug:
        print(f"[counts] after_cap={len(capped)} (max_total={args.max_total})")

    # even if we bypassed de-dupe, record these as seen so subsequent runs don’t repeat
    if args.ignore_cache and capped:
        try:
            mark_seen(capped)
            if debug:
                print(f"[dedupe] marked {len(capped)} items as seen (post-bypass)")
        except Exception as e:
            if debug:
                print(f"[dedupe] mark_seen failed: {e}")

    if not capped:
        msg = f"[{run_tag}]\nMorning Brief — no new items passed filters."
        _log_brief(msg)
        if debug:
            print(msg)
        # Don’t send an empty brief to Discord; comment the next line if you DO want a heartbeat
        # if not args.dry_run: send_discord(msg)
        return

    # 5) summarize
    summarizer = SonarSummarizer()
    summarized: List[Dict] = []
    for idx, it in enumerate(capped, 1):
        if debug:
            print(f"[summ] {idx}/{len(capped)}: {it.get('title','')[:100]}  [{it.get('source','')}]")
        summary = summarizer.summarize_one(
            it.get("title", ""), it.get("dek", ""), it.get("source", "")
        )
        summarized.append({
            "title": it.get("title", ""),
            "url": it["url"],
            "source": it["source"],
            "summary": summary,
        })
        time.sleep(0.2)

    # 6) render
    html_body = render_html(summarized)
    text_body = render_text(summarized)
    text_body = f"[{run_tag}]\n" + text_body  # tag the run type for quick visibility

    # 7) deliver (unless dry-run)
    if not args.dry_run:
        if debug:
            print(f"[send] discord chars={len(text_body)}")
        send_discord(text_body)
        # send_whatsapp_brief(text_body)  # enable later

    # 8) log
    log_path = _log_brief(text_body)
    print(f"Wrote brief to: {log_path}")


if __name__ == "__main__":
    main()


# Local examples:
# uv run python -m src.main --max-per-source 6 --max-total 20 --include "Fed,CPI,earnings,ECB" --exclude "opinion"
# uv run python -m src.main --ignore-cache --max-per-source 5 --max-total 25
# uv run python -m src.main --dry-run --max-per-source 4 --max-total 16 --debug
