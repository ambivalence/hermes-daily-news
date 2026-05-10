---
name: daily-news-briefing
description: Build a daily news summary agent that collects from RSS feeds across 4 categories (National, International, Business, AI/Tech), delivers summaries via Telegram, and ingests key stories into the wiki knowledge base for long-term contextual awareness.
version: 1.1.0
author: Hermes Agent
tags: [news, rss, cron, briefing, wiki, knowledge-base, current-events]
---

# Daily News Briefing Agent

Build a recurring daily news summary cron job that:
1. Collects news from 20+ RSS feeds across 4 categories
2. Deduplicates and curates top stories (~15 per category, 60 total)
3. Summarizes for the user via Telegram DM
4. Ingests significant stories into the wiki knowledge base for long-term contextual awareness

## Architecture

```
┌──────────────────────────────────────────────┐
│  1. Python Script (cron hook)                 │
│     └─ Fetches 20 RSS feeds → dedupes         │
│     └─ Outputs: /tmp/daily_news_data.json     │
│                                               │
│  2. Cron Agent (runs after script hook)       │
│     ├─ Reads JSON → summarizes 4 categories   │
│     ├─ Delivers briefing via Telegram DM      │
│     └─ Ingests key stories into wiki          │
│                                               │
│  3. Wiki (compounding knowledge base)         │
│     ├─ Entity pages for notable events/people │
│     ├─ Running timeline of narratives         │
│     └─ Grows contextual awareness over time   │
└──────────────────────────────────────────────┘
```

## Script Hook: News Collector

Create `/opt/data/scripts/daily_news_collector.py` — a Python script that fetches, parses, deduplicates, and curates news from RSS feeds.

### Why a Script Hook Instead of Doing It in the Agent Prompt?

The cron agent has limited context. Feeding 200+ raw RSS items would waste tokens on deduplication and parsing. The script pre-processes everything and outputs a clean JSON with ~60 curated items.

### Key Design Decisions

**Use built-in Python modules only** — `xml.etree.ElementTree` + `urllib.request`. PEP 668 blocks `pip install` on many systems, and these built-in modules handle both RSS 2.0 and Atom formats flawlessly.

**Both RSS and Atom parsing** — The script must handle both formats:
- RSS 2.0: `<rss><channel><item>` structure
- Atom: `<feed><entry>` structure with namespaces

**Deduplication** — Deduplicate by URL first, then by title similarity (first 60 chars lowercase). This prevents the same story from appearing from multiple sources.

**Curation** — Cap at MAX_ITEMS_PER_CATEGORY (default: 15) per category.

### RSS Feeds That Work (Tested May 2026)

These all return RSS 2.0 or Atom XML, parseable with ElementTree:

**National:**
- NPR Top News: `https://feeds.npr.org/1001/rss.xml` ✓
- NPR Politics: `https://feeds.npr.org/1014/rss.xml` ✓
- ABC News US: `https://abcnews.go.com/abcnews/usheadlines` ✓
- WSJ US: `https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml` ✓

**International:**
- BBC World: `https://feeds.bbci.co.uk/news/world/rss.xml` ✓
- BBC News: `https://feeds.bbci.co.uk/news/rss.xml` ✓
- NPR World: `https://feeds.npr.org/1002/rss.xml` ✓

**Business:**
- BBC Business: `https://feeds.bbci.co.uk/news/business/rss.xml` ✓
- Bloomberg Markets: `https://feeds.bloomberg.com/markets/news.rss` ✓
- CNBC Top News: `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114` ✓
- WSJ Business: `https://feeds.a.dj.com/rss/RSSMarketsMain.xml` ✓
- NPR Business: `https://feeds.npr.org/1006/rss.xml` ✓

**AI & Technology:**
- BBC Technology: `https://feeds.bbci.co.uk/news/technology/rss.xml` ✓
- TechCrunch: `https://techcrunch.com/feed/` ✓
- Ars Technica: `https://feeds.arstechnica.com/arstechnica/index` ✓
- Wired: `https://www.wired.com/feed/rss` ✓
- MIT Tech Review: `https://www.technologyreview.com/feed/` ✓
- Hacker News: `https://hnrss.org/frontpage` ✓
- NPR Technology: `https://feeds.npr.org/1019/rss.xml` ✓
- The Verge: `https://www.theverge.com/rss/index.xml` ✓

**Feeds that FAIL (not usable):**
- Reuters: returns 404 on their RSS endpoints
- AP News: returns 403 (blocked)
- CNN: returns massive HTML page, not parseable RSS

### Script Output Format

The script writes to `/tmp/daily_news_data.json`:

```json
{
  "meta": {
    "fetched_at": "2026-05-10T09:38:11+00:00",
    "total_feeds": 20,
    "total_items_raw": 444,
    "total_items_final": 60,
    "date": "2026-05-10"
  },
  "categories": {
    "national": {
      "label": "National (U.S.)",
      "items": [
        {
          "title": "Story title",
          "url": "https://...",
          "summary": "First ~500 chars of description (HTML stripped)",
          "source": "Source Name",
          "published": "Date string from feed"
        }
      ],
      "total_raw": 65,
      "total_unique": 62
    },
    "international": { ... },
    "business": { ... },
    "ai_tech": { ... }
  }
}
```

Also writes state to `/opt/data/daily_news_state.json` for tracking consecutive days of operation.

## Cron Job Setup

### Step 1: Create the Script

Save the collector script to `/opt/data/scripts/daily_news_collector.py`. Make sure it:
- Accepts no arguments (cron hook convention)
- Writes to `/tmp/daily_news_data.json`
- Exits with code 0 on success
- Prints JSON status to stdout for the agent to see

### Step 2: Create the Cron Job

```python
cronjob(
    action='create',
    name='Daily News Briefing',
    script='daily_news_collector.py',  # Runs before agent starts
    prompt="""You are a news briefing agent for [user name].

STEP 1 — Read the news data:
Read /tmp/daily_news_data.json (python3 -c "import json; d=json.load(open('/tmp/daily_news_data.json')); print(d['meta']['date'])")

STEP 2 — For each category (national, international, business, ai_tech):
  - Select the 5-7 most important stories
  - For each story, write a tight 1-2 line summary

STEP 3 — Identify notable stories for wiki ingestion:
  - Geopolitical shifts (Iran conflict, Ukraine developments, etc.)
  - Tech policy changes (AI regulation, privacy law changes)
  - Major market moves or economic indicators
  - New product/company launches (for the wiki's AI/VC domain)
  For each notable story, determine if it warrants:
  - A new entity page (notable event, new regulation)
  - An update to an existing page
  - A daily news log entry

STEP 4 — Format the briefing for Telegram:
  - Header: "☀️ Daily News Briefing — [Day], [Date]"
  - Each category gets a header with emoji (🇺🇸 National, 🌍 International, 💼 Business, 🤖 AI & Tech)
  - Bullet format: "• [Source] Story title — 1-line summary. https://raw-url"
  - Links MUST be raw URLs, NOT markdown [text](url) syntax — Telegram does not render markdown links
  - Example: "• [NPR] Iran ceasefire tested — British military reports vessel struck. https://www.npr.org/2026/05/10/nx-s1-5817437"
  - End with "🔍 Worth Watching: [1-2 proactive suggestions]"
  - Then a "📚 [N] stories ingested to wiki" footer if applicable
  - Plain text only, no markdown. Emojis for hierarchy.

STEP 5 — Ingest notable stories to the wiki:
  - Read SCHEMA.md at /opt/data/wiki/SCHEMA.md first
  - Create/update pages as appropriate
  - Update index.md and log.md

STEP 6 — Output the final briefing text as your response.
IMPORTANT: Do not save briefing to a file. Output text directly.
The cron system auto-delivers the output text.""",
    schedule='0 8 * * *',  # 8 AM PT (system local time, NOT UTC)
    deliver='telegram:USER_CHAT_ID'
)
```

### Step 3: Verify Schedule

Check the cron list output to verify the `next_run_at` shows the correct local time:
```python
cronjob(action='list')
```

## Wiki Integration

### Expanding the Wiki Schema for News

Add a `current-events` tag domain to the wiki's SCHEMA.md:

```markdown
## Tag Taxonomy
- current-events: general, national, international, business, ai-tech, policy, geopolitics
```

Create a `daily-briefings/` section in the wiki for tracking what was covered each day:
- `/opt/data/wiki/current-events/` — entity pages for notable news events
- `/opt/data/wiki/log.md` — each daily briefing gets a log entry with key stories

### The "Read More" Architecture

Two approaches for deeper dives on news stories:

**Option A — Links to original sources (recommended for daily briefings)**
- The `url` field in each news item provides a direct link to the full article
- User taps the link to read the original source
- Pros: Zero overhead, user gets full context, no storage cost
- Cons: Paywalls (WSJ, Bloomberg), link rot over time

**Option B — Wiki deep-dive**
- Agent ingests the story into the wiki, then user asks for a synthesis
- Pros: No paywall, contextualized against other wiki knowledge
- Cons: Extra agent work, wiki pollution from ephemeral content, retrieval degradation from page bloat

**Decision framework:** Use Option A for the daily 8 AM bulletin (bullets + links). Use Option B only for stories that pass the two-question threshold (see below) — those get ingested into the wiki and the agent can provide enriched context on demand.

### What to Ingest — The Two-Question Threshold

Not every news item needs a wiki page. Apply the SCHEMA.md threshold (both must be true):
1. **"Will this matter in 2 months?"** — not ephemeral headline noise
2. **"Does it connect to the AI/VC/startup thesis?"** — regulation, model releases, funding rounds, market structure shifts, geopolitics with investment implications

Classification:
- **Skip (links only):** political horse race, crime/weather, celebrity/sports, routine earnings, arts/culture
- **New page:** genuinely new entity or event with lasting significance (new regulation, notable funding round, novel geopolitical development)
- **Update existing entity page:** news about entities already in the wiki (Anthropic, OpenAI, Sequoia portfolio, etc.) — add a Timeline section entry to the entity page

### Pattern: Timeline Section on Entity Pages

When a notable event involves an entity already in the wiki (e.g., OpenAI trial), update the entity page with a **Timeline** section rather than creating a separate current-events page. This keeps the knowledge graph centered on entities and avoids page sprawl.

Example structure:
```markdown
## Timeline
- **May 2026** — Event description with key details and implications.
- **April 2026** — Previous notable event.
- **2025** — Origin event that triggered current situation.
```

### Before Creating, Check Existing Pages

Always read these files before writing new wiki pages:
1. `/opt/data/wiki/SCHEMA.md` — conventions and tag taxonomy
2. `/opt/data/wiki/index.md` — what entities/concepts already exist
3. Relevant entity pages (e.g., `entities/openai.md`) — might need an update instead of a new page

## Key Pitfalls

1. **PEP 668 blocks pip install** — Use built-in Python modules only (`xml.etree.ElementTree`, `urllib.request`). Don't try to install `feedparser` or `newspaper3k`.

2. **RSS XML + Atom both needed** — BBC uses standard RSS, some tech blogs use Atom. Both parsing paths are necessary.

3. **ElementTree.truthiness Deprecation in Python 3.13+** — The `a or b` pattern for Element find results triggers DeprecationWarning. Use explicit `is not None` checks for long-lived scripts.

4. **Script hook must write to /tmp** — The cron agent reads the script hook's stdout, but for structured data, write a JSON file. `/tmp/` is safe for ephemeral data.

5. **20 feeds = 15s runtime** — Set the cron script timeout appropriately (30s minimum). Some feeds are slow to respond.

6. **User-visible times in Pacific** — Cron schedules use system local time (PDT), NOT UTC. Always reference Pacific time in the briefing and schedule.

7. **No markdown in Telegram — raw URLs only** — Telegram does NOT render markdown link syntax `[text](url)`. Links must be bare raw URLs pasted directly into the text. Explicitly forbid markdown in the cron prompt and state the raw URL rule clearly. Use emojis for visual hierarchy instead.

8. **Test delivery format BEFORE scheduling** — Run the cron once with `cronjob(action='run', job_id='...')` and inspect the output file at `/opt/data/cron/output/<job_id>/<timestamp>.md`. Check that:
   - Links are raw URLs, not markdown
   - No markdown formatting snuck in
   - Day of week in header is correct
   - Wiki pages were actually created/updated as expected

9. **Don't overwhelm the wiki — use the two-question threshold** — News is ephemeral. For each story ask: "Will this matter in 2 months?" AND "Does it connect to the AI/VC/startup thesis?" Only wiki if both are true. Classification: skip (links only), new page (genuinely new entity/event), or update existing entity page with Timeline entry.

10. **Prefer updating existing entity pages over creating current-events pages** — When a notable event involves an entity already in the wiki (OpenAI, Anthropic, NVIDIA, Sequoia), add a Timeline section entry to the entity page. This keeps the knowledge graph centered on entities and avoids page sprawl.

11. **Set `deliver='origin'` for Telegram chat delivery** — Use `deliver='origin'` so the cron auto-detects the current chat. If pinned to a specific chat ID (like `telegram:1234567890`), the system delivers directly. Avoid using bare `deliver='local'` unless you plan to use send_message separately.

12. **Cron next_run_at shows an immediate rerun after 'run' — this is normal** — After calling `cronjob(action='run')`, the `next_run_at` will briefly show a near-future timestamp (the re-scheduling tick). The actual daily schedule resumes on the next full cycle. Check the `last_status` field to confirm the run completed successfully.

## GitHub: Tracking and Sharing

The collector script and skill definition can be version-controlled and shared as a public repo:

```bash
# Set up a repo for the news automation
mkdir /tmp/hermes-news-automation
cd /tmp/hermes-news-automation
git init
git branch -m main

# Copy the artifacts (NOT the wiki — contains private strategy content)
cp /opt/data/scripts/daily_news_collector.py .
cp /opt/data/skills/productivity/daily-news-briefing/SKILL.md .

# Create README.md explaining the architecture and setup
# Push to GitHub
git remote add origin https://github.com/YOUR_USER/hermes-daily-news.git
git push -u origin main
```

**IMPORTANT:** Do NOT push the wiki directory (`/opt/data/wiki/`) to a public repo — it likely contains private strategy content, company profiles, and personal research. Only push the standalone collector script and skill definition.

The public repo at https://github.com/ambivalence/hermes-daily-news is a reference implementation.

The script lives at two locations:
- **Development**: `/opt/data/skills/productivity/daily-news-briefing/scripts/daily_news_collector.py` (skill-managed)
- **Runtime**: `/opt/data/scripts/daily_news_collector.py` (cron system expects scripts here)

When building the cron job, ensure the script is copied to `/opt/data/scripts/`:
```bash
cp /opt/data/skills/productivity/daily-news-briefing/scripts/daily_news_collector.py /opt/data/scripts/daily_news_collector.py
```

## Setup Status (May 10, 2026)

- [x] Script built and tested: fetches 60 curated items from 20 feeds in ~15s
- [x] Script written to skill at `/opt/data/skills/productivity/daily-news-briefing/scripts/daily_news_collector.py`
- [x] Script copied to `/opt/data/scripts/daily_news_collector.py` (needed for cron)
- [x] Cron job created (8 AM PT)
- [x] Wiki expanded with current-events schema and news threshold
- [x] Test run successful — briefing delivered, wiki ingestion working
- [x] GitHub: https://github.com/ambivalence/hermes-daily-news

## User Decisions (Final — May 10, 2026)

- **Timing**: Separate 8 AM PT news briefing (existing 7 AM is calendar/weather)
- **Delivery**: Bullets + links to original sources (no markdown, raw URLs)
- **Wiki scope**: Selective ingestion — only stories that are BOTH "will matter in 2 months" AND "connects to AI/VC/startup thesis"
- **GitHub**: Public repo at https://github.com/ambivalence/hermes-daily-news

## Testing Checklist

- [ ] Script runs: `python3 /opt/data/scripts/daily_news_collector.py`
- [ ] Checks: `/tmp/daily_news_data.json` has data, not empty
- [ ] Verify all 4 categories have items, not just 1-2
- [ ] Cron test: `cronjob(action='run', job_id='<id>')`
- [ ] Confirm delivery arrives in Telegram DM
- [ ] Check wiki log: `read_file /opt/data/wiki/log.md` to verify ingestion
- [ ] Verify wiki index updated with any new pages
- [ ] Check next_run_at shows correct local time

## Customization

- **Add/remove feeds**: Edit the CATEGORIES dict in the script
- **Change curation count**: Adjust MAX_ITEMS_PER_CATEGORY
- **Change schedule**: Update the cron job's schedule expression
- **Different categories**: Add new category keys (e.g., "sports", "science")