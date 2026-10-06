# Seed data attribution

`fieldkit/seeds/` vendors third-party registry data so swarmhunter works
offline and every classification is reproducible against a known snapshot.

## airobots/

- `robots.json` — from https://github.com/ai-robots-txt/ai.robots.txt
  (community AI-crawler registry). MIT License — see `airobots/LICENSE`
  (Copyright (c) 2024 ai.robots.txt). Fetched 2026-10-06.
  sha256: dc64e84a11f1d88c6eb93b63d8e26545941c0b31e1cf4205f4c2a5caa61c7f8a

## agentswelcome/

- `crawlers.json` — from https://agentswelcome.dev/api/crawlers
  (The AI Crawler Registry). Fetched 2026-10-06 (listed updated 2026-07-06).
  sha256: 6d65f825e67017a0de6b826b273a073169da8ac25331bfb72029be7f455925a2

## openai/

Per-bot published IP ranges from openai.com (`gptbot.json`,
`searchbot.json`, `chatgpt-user.json`, `adsbot.json`). Fetched 2026-10-06;
creationTime inside each file is the authoritative freshness date.
Re-fetch before any spoof-analysis that matters; ranges rotate.

## anthropic/

- `bots.json` — shared published IP list for ClaudeBot / Claude-User /
  Claude-SearchBot from claude.com/crawling/bots.json. Fetched 2026-10-06.
  NOTE: one shared list — IP presence proves "Anthropic", not which bot
  token is authentic (see docs/RECON.md).

Refresh with: `fieldkit/fetch_seeds.sh` (coming Phase 2) or re-run the
fetch and re-vendor. Regenerate ground truth afterwards:
`python3 fieldkit/build_known_agents.py`.
