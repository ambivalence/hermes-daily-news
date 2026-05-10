# Hermes Daily News Briefing

A self-contained news automation system for [Hermes Agent](https://github.com/NousResearch/hermes-agent). Fetches, deduplicates, and curates news from 20+ RSS feeds across 4 categories, delivers a daily Telegram briefing, and selectively ingests high-significance stories into a persistent wiki knowledge base.

## Architecture

```
┌────────────────────────────────────────────┐
│ 1. Python Script (cron hook)               │
│    └─ Fetches 20 RSS feeds → dedupes       │
│    └─ Outputs: /tmp/daily_news_data.json   │
│                                             │
│ 2. Cron Agent (runs after script hook)     │
│    ├─ Reads JSON → summarizes 4 categories  │
│    ├─ Delivers briefing via Telegram        │
│    └─ Ingests key stories into wiki         │
│                                             │
│ 3. Wiki (optional compounding knowledge)    │
│    ├─ Entity pages for notable events       │
│    ├─ Only stores what passes threshold     │
│    └─ Grows contextual awareness over time  │
└────────────────────────────────────────────┘
```

## What's Included

- **`daily_news_collector.py`** — Standalone Python script (no dependencies beyond stdlib) that fetches, parses RSS 2.0 + Atom, deduplicates by URL and title similarity, and curates top stories per category.
- **`SKILL.md`** — Hermes Agent skill definition with full setup instructions, cron configuration, and wiki integration patterns.

## News Sources

**National:** NPR, WSJ, ABC News  
**International:** BBC World, BBC News, NPR World  
**Business:** Bloomberg, CNBC, WSJ, BBC Business  
**AI & Tech:** TechCrunch, Ars Technica, Wired, MIT Tech Review, Hacker News, The Verge, BBC Technology

## Key Design Decisions

### Why a Script Hook Instead of Raw Feed Processing?
The cron agent has limited context. Feeding 200+ raw RSS items would waste tokens on deduplication and parsing. The script pre-processes everything into clean JSON with ~60 curated items.

### Wiki Ingestion Threshold
Not every news item is worth remembering. Only stories that pass both tests get wiki-ified:
1. **"Will this matter in 2 months?"** — not ephemeral headline noise
2. **"Does it connect to the AI/VC/startup thesis?"** — regulation, model releases, funding rounds, market structure, geopolitics with investment implications

### Why No Pip Dependencies?
PEP 668 blocks `pip install` on many systems. The script uses only `xml.etree.ElementTree` + `urllib.request` — both Python stdlib.

## Cron Setup

```python
cronjob(
    action='create',
    name='Daily News Briefing',
    script='daily_news_collector.py',
    prompt="...",  # See SKILL.md for full prompt
    schedule='0 8 * * *',  # 8 AM PT
    deliver='origin'  # or explicit telegram:CHAT_ID
)
```

## License

MIT — use it, fork it, share it.
