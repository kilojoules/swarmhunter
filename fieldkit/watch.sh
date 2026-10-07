#!/bin/zsh
# swarmhunter daily watch — pull events, analyze, notify on finding-class
# events. Runs from the operator's Mac via cron. Safe: read-only on the
# VPS (scp), local analysis, notification only. Never touches the garden.
set -euo pipefail

REPO=/Users/kilojoules/swarmhunter
VPS=root@179.236.250.247
EVENTS=$REPO/garden/events.ndjson
LOG=$REPO/fieldkit/watch.log

cd $REPO
echo "=== $(date -u +%FT%TZ) watch run ===" >> $LOG

# 1. pull latest events (read-only)
scp -q -o ConnectTimeout=15 -o BatchMode=yes $VPS:/opt/swarmhunter/garden/events.ndjson $EVENTS

# 2. re-run analysis
python3 fieldkit/analyze.py $EVENTS fieldkit/sightings.json >> $LOG 2>&1

# 3. check for finding-class events: riddle attempts, wall signatures,
#    T2 invisible-prose trips, llm-comprehension class, from wild IPs
FINDINGS=$(python3 - <<'EOF'
import json, sys
try:
    s = json.load(open('fieldkit/sightings.json'))
except Exception as e:
    print(f"parse-error: {e}"); sys.exit(0)
hits = []
for x in s.get('sightings', []):
    cls = x.get('class', '')
    if cls == 'llm-comprehension':
        hits.append(f"COMPREHENSION: {x['callsign']} conf {x['confidence']} — {x.get('evidence', [''])[0][:120]}")
    for e in x.get('evidence', []):
        if 'invisible' in e.lower() and 'prose' in e.lower():
            hits.append(f"T2 PROSE TRIP: {x['callsign']} — {e[:120]}")
    if x.get('riddle_tries', 0) > 0 and x.get('ip') not in (None, '', 'unknown(docker-bridge)'):
        hits.append(f"RIDDLE ATTEMPT: {x['callsign']} tries={x.get('riddle_tries')} ip={x.get('ip')}")
    if x.get('guestbook_verse'):
        hits.append(f"VERSE: {x['callsign']} — {str(x.get('guestbook_verse'))[:100]}")
if hits:
    print('\n'.join(hits))
EOF
)

if [ -n "$FINDINGS" ]; then
  osascript -e "display notification \"swarmhunter: finding-class event — check watch.log\" with title \"Trap Garden\" sound name \"Glass\"" >/dev/null 2>&1 || true
  echo "!!! FINDING-CLASS EVENTS:" >> $LOG
  echo "$FINDINGS" >> $LOG
else
  echo "no finding-class events" >> $LOG
fi

# 4. commit dossier movement (if any) — keeps public record moving
if ! git diff --quiet fieldkit/sightings.json dossier/ 2>/dev/null; then
  git add fieldkit/sightings.json dossier/ 2>/dev/null || true
  # sightings.json is gitignored; dossier/ is public
  git add dossier/ 2>/dev/null || true
  git -c user.name="kilojoules" -c user.email="quectojoules@gmail.com" commit -q -m "watch: dossier refresh $(date -u +%F)

Co-Authored-By: Claude Code <noreply@anthropic.com>" 2>/dev/null || true
  git push -q origin main 2>/dev/null || true
fi
