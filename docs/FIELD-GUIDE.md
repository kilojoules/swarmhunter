# Field Guide — running the hunt

Everything you need to plant a Trap Garden, read its events, and keep
the dossier current. No dependencies beyond Python 3.9+ stdlib.

## Plant the garden

Local test run:

```bash
python3 garden/traps/generate_traps.py      # build trap registry
python3 garden/app/server.py                # serves 127.0.0.1:8080
```

Deploy for real (any host with Docker):

```bash
cd deploy && docker compose up -d --build
```

The garden is a small gardening-notes site ("Mossline, plot 12"). Traps
are woven into its pages; visitors are logged with full fidelity to
`garden/events.ndjson` (one JSON object per line). See docs/DESIGN.md
for the trap inventory and their inertness rule.

## Read last night's events

```bash
python3 fieldkit/analyze.py garden/events.ndjson fieldkit/sightings.json
```

Sessionizes events (cookie sid first, ip+ua fallback with 30-min gap
split), walks the verification ladder, classifies each session, assigns
callsigns. Console summary shows the menagerie at a glance.

## Publish the dossier

```bash
python3 fieldkit/dossier.py
```

Renders `dossier/index.md` + one profile per callsign. IPs appear as
/24 clusters; raw IPs are salted+hashed after 7 days (salt in
`fieldkit/.salt`, gitignored).

## Reading classes

| class | meaning |
|---|---|
| declared-verified | UA claim + IP inside operator's published ranges |
| declared-unverified | claim, but operator publishes no verification |
| spoof-suspected | claim FAILED verification — high-interest |
| shadow-crawler | tripped human-invisible canaries, no honest identity |
| llm-comprehension | answered the voluntary identification gate |
| scripted-bot / scanner-bot | conventional tooling / probe traffic |
| human | human-paced browser, no canary trips |
| cryptid | low confidence — review by hand |

## Guardrail quick-reference (full: docs/SCOPE.md)

- Traps run only on infrastructure we own; payloads only ever ask a
  visitor to fetch an on-site URL or send a header. Nothing harmful,
  nothing off-site, nothing we wouldn't show a human.
- Observe, never counterattack. No socket-holding, no exploits.
- IPs hashed after 7 days; dossier entries are behavioral records, not
  accusations.
- Re-vendor seeds before trusting spoof analysis: OpenAI/Anthropic
  ranges rotate (`python3 fieldkit/build_known_agents.py` after refresh).
