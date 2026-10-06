#!/bin/sh
# Refresh vendored seed data (run before trusting spoof analysis).
# Field Kit ground truth is only as fresh as these files; OpenAI/Anthropic
# ranges rotate. After fetching, rebuild:
#   python3 fieldkit/build_known_agents.py
set -e
cd "$(dirname "$0")"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

fetch() { # fetch <url> <dest>
  echo "fetching $1"
  curl -sSL -A "$UA" -o "$2.tmp" "$1" && mv "$2.tmp" "$2" || {
    echo "FAILED: $1 (left .tmp removed)"; rm -f "$2.tmp"; return 1; }
}

fetch https://raw.githubusercontent.com/ai-robots-txt/ai.robots.txt/main/robots.json seeds/airobots/robots.json
fetch https://agentswelcome.dev/api/crawlers seeds/agentswelcome/crawlers.json
fetch https://openai.com/gptbot.json      seeds/openai/gptbot.json
fetch https://openai.com/searchbot.json   seeds/openai/searchbot.json
fetch https://openai.com/chatgpt-user.json seeds/openai/chatgpt-user.json
fetch https://openai.com/adsbot.json      seeds/openai/adsbot.json
fetch https://claude.com/crawling/bots.json seeds/anthropic/bots.json

echo
echo "done. now rebuild ground truth:"
echo "  python3 fieldkit/build_known_agents.py"
