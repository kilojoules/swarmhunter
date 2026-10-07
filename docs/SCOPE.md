# Swarmhunter Scope — the project contract

**Decided 2026-10-06.** What we hunt, where evidence comes from, what we
build, and the lines we do not cross. Incident citations live in
[TAXONOMY.md](TAXONOMY.md); the landscape and prior art in
[RECON.md](RECON.md); the technical design in [DESIGN.md](DESIGN.md).

## Mission

Detect, fingerprint, and track rogue AI agents on the public internet, and
publish the running dossier. Defensive observation only — we are hunters and
naturalists, never counterattackers.

## Decisions (locked with the user, 2026-10-06)

1. **Hunt everything.** All documented rogue-agent classes plus an explicit
   cryptid class for unknowns. See taxonomy below.
2. **Canary infrastructure first.** Evidence comes first from traps we own
   and operate, not from other people's telemetry. Recon confirmed this is
   the right call: no public feed detects undeclared/shadow agents — own-
   sensor telemetry is the only direct source (RECON.md, gaps).
3. **Deliverable: toolkit + running dossier.** A working hunter (Trap
   Garden + Field Kit) plus a published record of tracked agents.

## Hunt taxonomy

| ID | Class | One-liner | Evidence base |
|----|-------|-----------|---------------|
| S1 | Shadow crawler | Undeclared AI crawling: ignores robots.txt, spoofs human/innocuous UAs, hides on proxy IPs | Perplexity exposé; DataDome 2026 telemetry |
| S2 | Autonomous attacker | Agent that scans/exploits/ransoms with no human between steps | JADEPUFFER agentic ransomware; marimo intrusion |
| S2b | Agentic supply chain | Malicious coding agents and npm/postinstall worms harvesting agent credentials | Shai-Hulud; Nx s1ngularity; Miasma |
| S3 | Hijacked agent | Legitimate browsing/coding agent led astray by prompt injection in content it ingested | ChatGPT Atlas disclosures; Browser Use CVE |
| S3b | Scam / social-eng bot | AI fraud at scale: fake personas, romance funnels, platform abuse | Anthropic GTG-15001; Meta chatbot takeovers |
| S4 | Escaped / out-of-bounds agent | Agents outside their sanctioned environment attacking third parties | OpenAI ExploitGym → Hugging Face, July 2026 |
| S5 | Agentic malware / LLM C2 | Malware that reasons: LLM calls mid-execution, promptware C2 | GTIG in-the-wild sample; VoidLink; ZombAI |
| X | Cryptid | Anything our classifiers can't place | By definition, ours to find |

S2b and S3b are documented primarily from public reports (a dossier
registry of incidents); the rest are directly detectable by our traps.
Full incidents with URLs and dates: [TAXONOMY.md](TAXONOMY.md).

## Guardrails

- **No crimes — user directive (2026-10-06), absolute.** No unauthorized
  access to any system, no counterattacks, no exploitation of anything we
  don't own, no interception of others' traffic. Everything swarmhunter
  does must be legal defensive security research: our traps run only on
  infrastructure we own, observe only visitors to our own pages, and
  publish only analysis. If any planned technique is legally gray in a
  deployment jurisdiction, we don't deploy it until that's resolved.

- **Observation only.** No exploits, no counterattacks, no socket-holding,
  no doxxing operators. IPs in the dossier are hashed after 7 days.
- **Canaries are benign bait.** A trap may only induce a benign,
  self-attributing action — fetching a unique URL, sending a registration
  header. Never an instruction that could cause harm, exfiltration beyond
  our own request logs, or anything we wouldn't show a human. Follows
  Drosera's `assert_inert` precedent (RECON.md).
- **Traps are LLM-perceivable, human-invisible.** A person who somehow
  lands on a trap page sees a harmless "you found a canary" note. No dark
  patterns aimed at humans, no fake system dialogs.
- **No chasing.** We never follow an agent onto infrastructure we don't
  own.
- **Honest uncertainty.** Every dossier claim carries its evidence and
  confidence; spoofed UAs prove nothing by themselves (a GPTBot string is
  a claim, not an identity — verification is IP range or Web Bot Auth
  signature, DESIGN.md).

## Architecture

```
            public internet
                  │ requests
                  ▼
        ┌───────────────────┐   raw events (ndjson)   ┌──────────────────┐
        │   Trap Garden     │ ───────────────────────▶ │    Field Kit     │
        │  cover site +     │                          │ verify ▶ classify│
        │  canaries, robots │                          │ ▶ fingerprint    │
        │  traps, tarpit    │                          │ ▶ callsign       │
        └───────────────────┘                          └────────┬─────────┘
                                                                │ sightings
                                                                ▼
        ┌───────────────────┐   enrich (Phase 3)        ┌───────────────┐
        │ OSINT feeds       │◀───────────────────────── │    Dossier    │
        │ (Radar, GreyNoise)│                           │ profiles+feed │
        └───────────────────┘                           └───────────────┘
```

## Phases

- **Phase 0 (this)** — scope + recon folded in; design doc; ground-truth
  plan for known agents.
- **Phase 1** — Trap Garden MVP (cover site, canary pages, robots traps,
  full-fidelity logging) + Field Kit MVP (known-agents.yaml seeded from
  registries, verifier, first-pass classifier) + first dossier render.
- **Phase 2** — tarpit mesh, form canaries, external canary tokens,
  deployment hardening (docker-compose, deploy-agnostic), publish dossier.
- **Phase 3** — OSINT enrichment (Cloudflare Radar API, GreyNoise
  Community), scam-bot incident registry, scale if the data demands.

## Defaults chosen (say the word to change)

- **Deployment:** docker-compose, host-agnostic — point it at any VPS.
- **Dossier visibility:** methods/instrument published immediately
  (2026-10-06); sightings data stays private until the first
  comprehension-class event (T7 solve / T2 actuation from a wild IP),
  then published from the repo. Rationale: firsts in this field are won
  by publication speed, but a T1-only trip never earns a finding label
  (range-verified ClaudeBot tripped the same canary — T1 proves
  automation, never agency).
- **Repo:** public at github.com/kilojoules/swarmhunter since
  2026-10-06; git history from first deploy onward is the
  timestamp of record.
- **Git:** initialized 2026-10-06 (evidence-lock commits start at
  first deploy); pushed public on beacon day.
