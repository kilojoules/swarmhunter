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

Phase 1 shipped — Trap Garden (T1–T5 traps, full-fidelity logging),
Field Kit (189-agent ground truth, verification ladder, classifier,
callsigns), dossier renderer, docker deployment. Pipeline verified
end-to-end with simulated personas (tests/); **the dossier honestly
holds zero true sightings** — it stays empty until the garden is
deployed on the public internet and real visitors arrive. See
[docs/SCOPE.md](docs/SCOPE.md) for the plan,
[docs/FIELD-GUIDE.md](docs/FIELD-GUIDE.md) to run it, and
[dossier/index.md](dossier/index.md) for the current record.

## Layout

```
docs/        scope, design, field guides
garden/      the Trap Garden honeypot app   (Phase 1)
fieldkit/    detectors, fingerprinters, tracker   (Phase 1)
dossier/     sightings + generated agent profiles (Phase 1)
deploy/      deployment configs              (Phase 2)
```
