#!/usr/bin/env python3
"""
Daily News Collector Script
Hermes Agent cron hook — fetches RSS/Atom feeds across 4 categories,
deduplicates, ranks, and outputs structured JSON for the agent to summarize.

Output: /tmp/daily_news_data.json (consumed by cron agent)
Also writes: /opt/data/daily_news_state.json (persistent state tracking)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ── Config ──────────────────────────────────────────────────────────────────

MAX_ITEMS_PER_CATEGORY = 15
REQUEST_TIMEOUT = 10  # seconds per feed
USER_AGENT = "Mozilla/5.0 (compatible; HermesAgent-DailyNews/1.0)"

CATEGORIES = {
    "national": {
        "label": "National (U.S.)",
        "feeds": [
            ("NPR Top News", "https://feeds.npr.org/1001/rss.xml"),
            ("NPR Politics", "https://feeds.npr.org/1014/rss.xml"),
            ("WSJ US", "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"),
            ("ABC News US", "https://abcnews.go.com/abcnews/usheadlines"),
        ],
    },
    "international": {
        "label": "International / World",
        "feeds": [
            ("The Guardian World", "https://www.theguardian.com/world/rss"),
            ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
            ("France24", "https://www.france24.com/en/rss"),
            ("NPR World", "https://feeds.npr.org/1002/rss.xml"),
        ],
    },
    "business": {
        "label": "Business & Finance",
        "feeds": [
            ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss"),
            ("CNBC Top News", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
            ("WSJ Business", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
            ("NPR Business", "https://feeds.npr.org/1006/rss.xml"),
            ("The Guardian Business", "https://www.theguardian.com/business/rss"),
        ],
    },
    "ai_tech": {
        "label": "AI & Technology",
        "feeds": [
            ("TechCrunch", "https://techcrunch.com/feed/"),
            ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
            ("Wired", "https://www.wired.com/feed/rss"),
            ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
            ("Hacker News", "https://hnrss.org/frontpage"),
            ("NPR Technology", "https://feeds.npr.org/1019/rss.xml"),
            ("The Verge", "https://www.theverge.com/rss/index.xml"),
            ("VentureBeat", "https://feeds.feedburner.com/venturebeat/SZYF"),
        ],
    },
}


# ── RSS Parsing ─────────────────────────────────────────────────────────────

def parse_rss(content, source_name):
    """Parse RSS XML or Atom feed. Returns list of item dicts."""
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"  [WARN] Parse error for {source_name}: {e}", file=sys.stderr)
        return items

    # Try RSS 2.0 format: <rss><channel><item>...
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            entry = _extract_rss_item(item, source_name)
            if entry:
                items.append(entry)
        return items

    # Try Atom format: <feed><entry>...
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns) or root.findall("entry")
    for entry in entries:
        entry_data = _extract_atom_entry(entry, source_name, ns)
        if entry_data:
            items.append(entry_data)
    return items


def _get_text(element, path, ns=None):
    """Get text content from first matching child element."""
    child = element.find(path, ns) if ns else element.find(path)
    return child.text if child is not None else ""


def _extract_rss_item(item, source_name):
    """Extract data from an RSS 2.0 <item> element."""
    title = _get_text(item, "title")
    link = _get_text(item, "link")
    summary = _get_text(item, "description")
    pub_date = _get_text(item, "pubDate")
    guid = _get_text(item, "guid") or link

    if not title or not link:
        return None

    # Clean summary: strip HTML tags
    summary = re.sub(r"<[^>]+>", "", summary).strip()
    # Truncate long summaries
    if len(summary) > 300:
        summary = summary[:297] + "..."

    return {
        "title": title.strip(),
        "url": link.strip(),
        "summary": summary,
        "source": source_name,
        "published": pub_date.strip() if pub_date else "",
        "guid": guid.strip(),
    }


def _extract_atom_entry(entry, source_name, ns):
    """Extract data from an Atom <entry> element."""
    title = _get_text(entry, "atom:title", ns) or _get_text(entry, "title")
    
    # Atom link is in href attribute
    link_el = entry.find("atom:link", ns)
    if link_el is None:
        link_el = entry.find("link")
    link = ""
    if link_el is not None:
        link = link_el.get("href", "")
    
    summary = _get_text(entry, "atom:summary", ns) or _get_text(entry, "summary") or \
              _get_text(entry, "atom:content", ns) or _get_text(entry, "content")
    
    published = _get_text(entry, "atom:published", ns) or _get_text(entry, "published") or \
                _get_text(entry, "atom:updated", ns) or _get_text(entry, "updated")
    
    # Atom ID is the guid equivalent
    guid = _get_text(entry, "atom:id", ns) or _get_text(entry, "id") or link

    if not title or not link:
        return None

    summary = re.sub(r"<[^>]+>", "", summary).strip()
    if len(summary) > 300:
        summary = summary[:297] + "..."

    return {
        "title": title.strip(),
        "url": link.strip(),
        "summary": summary,
        "source": source_name,
        "published": published.strip() if published else "",
        "guid": guid.strip(),
    }


# ── Feed Fetching ───────────────────────────────────────────────────────────

def fetch_feed(source_name, url):
    """Fetch and parse a single RSS/Atom feed."""
    print(f"  Fetching {source_name}...", file=sys.stderr)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            content = resp.read()
        return parse_rss(content, source_name)
    except HTTPError as e:
        print(f"  [WARN] HTTP {e.code} for {source_name} ({url})", file=sys.stderr)
        return []
    except URLError as e:
        print(f"  [WARN] URL error for {source_name}: {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  [WARN] Failed to fetch {source_name}: {e}", file=sys.stderr)
        return []


# ── Deduplication ───────────────────────────────────────────────────────────

def deduplicate(items):
    """Remove duplicates by URL (preferred) or title similarity."""
    seen_urls = set()
    seen_titles = set()
    unique = []

    for item in items:
        url_key = item["url"].lower().strip().rstrip("/")
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)

        # Also check title similarity for feeds without reliable URLs
        title_key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:60]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        unique.append(item)

    return unique


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("Daily News Collector starting...", file=sys.stderr)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}", file=sys.stderr)

    all_raw = []
    category_results = {}

    for cat_key, cat_config in CATEGORIES.items():
        print(f"\n[{cat_config['label']}]", file=sys.stderr)
        cat_items = []
        for source_name, feed_url in cat_config["feeds"]:
            items = fetch_feed(source_name, feed_url)
            cat_items.extend(items)
            all_raw.extend(items)

        # Deduplicate within category
        cat_items = deduplicate(cat_items)
        # Limit per category
        cat_items = cat_items[:MAX_ITEMS_PER_CATEGORY]
        category_results[cat_key] = {
            "label": cat_config["label"],
            "items": cat_items,
        }
        print(f"  -> {len(cat_items)} items", file=sys.stderr)

    # Deduplicate globally
    all_deduped = deduplicate(all_raw)
    total_final = sum(len(v["items"]) for v in category_results.values())

    output = {
        "meta": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_feeds": sum(len(c["feeds"]) for c in CATEGORIES.values()),
            "total_items_raw": len(all_raw),
            "total_items_final": total_final,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "categories": {},
    }

    for cat_key, cat_data in category_results.items():
        output["categories"][cat_key] = {
            "label": cat_data["label"],
            "items": cat_data["items"],
        }

    # Write output file
    with open("/tmp/daily_news_data.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone! {len(all_raw)} raw -> {total_final} final items written to /tmp/daily_news_data.json", file=sys.stderr)

    # Write state file
    state = {
        "last_fetch": datetime.now(timezone.utc).isoformat(),
        "total_raw": len(all_raw),
        "total_final": total_final,
    }
    with open("/opt/data/daily_news_state.json", "w") as f:
        json.dump(state, f, indent=2)


if __name__ == "__main__":
    main()