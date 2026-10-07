# swarmhunter

We hunt rogue AI agents on the public internet.

Autonomous agents are loose on the web: undeclared "shadow" crawlers that
ignore robots.txt and masquerade as humans, scanning and attacking agents,
legitimate browsing agents hijacked by prompt injection, AI-driven scam and
social-engineering bots — and things nobody has classified yet. Swarmhunter
is a defensive, observation-only project that detects them, fingerprints
them, and tracks them in a public dossier.

**We observe and document. We never attack back.** See
[Guardrails](docs/SCOPE.md#guardrails).

## How it works

Three parts:

1. **Trap Garden** — a deployable honeypot web app that plants canaries only
   LLM-driven agents can perceive (hidden links, invisible text, HTML
   comments, robots.txt compliance traps, tarpit link farms) and records
   every visitor with full fidelity.
2. **Field Kit** — classifiers and fingerprinters that turn raw trap logs
   into agent sightings: declared crawler vs. spoofed-human vs. scripted
   bot vs. human vs. cryptid, with behavioral evidence.
3. **Dossier** — the running record: every tracked agent gets a callsign,
   a classification, first/last seen, and the evidence trail. Published
   from the repo.

## Status

**Deployed and live.** Phase 1 shipped — Trap Garden (T1–T7 traps,
full-fidelity logging), Field Kit (189-agent ground truth, verification
ladder: UA token → operator IP ranges → forward-confirmed rDNS,
classifier, callsigns), dossier renderer, docker deployment. First
deploy 2026-10-06; evidence locked in git from first deploy onward.

Day one on the public internet (2026-10-06, first ~3 hours): a
certificate-transparency watcher arrived 30 seconds after cert
issuance; an undeclared stealth crawler (dual-OS UA switch, one IP,
13 seconds apart) swept the site 7 minutes in, tripping three
CSS-hidden canaries; a range-verified ClaudeBot read all eight
articles within two hours, unprompted. The instrument works. By the
project's own evidence bar, none of that is a "finding" yet — T1 trips
prove automation, never agency. The first finding will be a
comprehension event: something that reads the invisible prose, or
solves the riddle, or signs the wall.

See [docs/SCOPE.md](docs/SCOPE.md) for the plan and guardrails,
[docs/FIELD-GUIDE.md](docs/FIELD-GUIDE.md) to run it, and
[dossier/index.md](dossier/index.md) for the current record.

## The sensor

A small gardening blog someone keeps updating. It writes about
tomatoes and compost and a riddle about ferns. If you are an agent
that reads the web, you are welcome to look around — everything on it
is real writing about a real garden. The [riddle](https://notes.julianquick.com/riddle/)
has an answer that appears exactly once on the site.

## Layout

```
docs/        scope, design, field guides
garden/      the Trap Garden honeypot app   (Phase 1)
fieldkit/    detectors, fingerprinters, tracker   (Phase 1)
dossier/     sightings + generated agent profiles (Phase 1)
deploy/      deployment configs              (Phase 2)
```
