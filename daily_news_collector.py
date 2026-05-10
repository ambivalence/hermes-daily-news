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
            ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
            ("BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
            ("NPR World", "https://feeds.npr.org/1002/rss.xml"),
        ],
    },
    "business": {
        "label": "Business & Finance",
        "feeds": [
            ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
            ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss"),
            ("CNBC Top News", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
            ("WSJ Business", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
            ("NPR Business", "https://feeds.npr.org/1006/rss.xml"),
        ],
    },
    "ai_tech": {
        "label": "AI & Technology",
        "feeds": [
            ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
            ("TechCrunch", "https://techcrunch.com/feed/"),
            ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
            ("Wired", "https://www.wired.com/feed/rss"),
            ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
            ("Hacker News", "https://hnrss.org/frontpage"),
            ("NPR Technology", "https://feeds.npr.org/1019/rss.xml"),
            ("The Verge", "https://www.theverge.com/rss/index.xml"),
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

    # Try RSS 2.0 format: 