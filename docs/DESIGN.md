# Trap Garden + Field Kit — Technical Design

Phase 1 targets, informed by recon. Companion to [SCOPE.md](SCOPE.md) and
[RECON.md](RECON.md). Everything here inherits the guardrails: our
infrastructure only, benign inert bait only, observation only.

## Design principles (from recon)

0. **Honest cover, boring front.** The site claims to be nothing it
   isn't toward *humans*; toward machines it presents a deliberately
   unremarkable front (server banner reads Apache, a common shared-host
   shape — documented here as intentional cover, per the review panel's
   audit note; the Caddy edge strips the header in deployment anyway).
   No deception aimed at people; traps are inert bait only.

1. **Verification ladder over UA claims.** A user-agent string is a claim.
   Identity is: token → IP in operator's published ranges → rDNS → Web
   Bot Auth signature. Record *verifiability*, not just names.
2. **Comprehension beats heuristics.** Drosera's insight: an English
   notice only a reader can comply with (register + purpose header) is
   proof of LLM agency, not a guess. We adopt the pattern inertly.
3. **The cover site must be credible.** LLM pentest agents form "honeypot
   suspicion" (arXiv 2609.08093) — our bait must look like a real, boring,
   useful site, not a trap farm.
4. **Three-class architecture.** human / scripted bot / AI agent (arXiv
   2607.26935); never binary bot-vs-human.
5. **Stealth artifacts are evidence.** Anti-detection tooling often
   *increases* detectability (arXiv 2606.30119) — log and score them.
6. **Deterministic generation.** Per-URL-seeded content (Nepenthes):
   reproducible, cheap, and gives consistent fingerprints across visits.

## Trap Garden (the sensor)

A small, real web app — the cover — with traps woven in. Stack: single
Node or Go binary, no database dependency; events to append-only ndjson;
deployed via docker-compose on one small VPS. The cover should be
*genuinely useful* content (a topical blog/tool) so it accrues organic
traffic and search presence over time.

### Cover site (Phase 1)

Real pages, real content, real sitemap. Everything below hangs off it.

### Trap surfaces

| # | Trap | Mechanism | Catches | Phase |
|---|------|-----------|---------|-------|
| T1 | Hidden-link honeypots | `<a href>` present in HTML, visually hidden (CSS), nofollow | scrapers + LLM-context feeders; humans never click invisible links | 1 |
| T2 | Invisible-text canaries | zero-contrast / tiny / aria-hidden prose mid-page | LLM-context ingestion only | 1 |
| T3 | HTML-comment canaries | URLs/instructions only in HTML comments | text-processors (LLM) only | 1 |
| T4 | robots.txt compliance traps | `Disallow: /garden/…` + tripwires on those paths | non-compliance logging; declared bots *should* comply — trips are high-signal | 1 |
| T5 | Comprehension gate | visible English notice: benign self-identification request (fetch unique URL / send purpose header), no reward, no injection | proof of LLM agency (Drosera pattern, inert) | 1 |
| T6 | Tarpit mesh | deterministic per-URL-seeded link farm under `/garden/` | crawl-depth/fan-out/exhaustion behavior | 2 |
| T7 | Form canaries | decoy form with unusual field names + hidden instructions | agents that fill forms | 2 |
| T8 | External canary tokens | e.g. thinkst CanaryTokens embedded in trap pages | out-of-band confirmation | 2 |

**Inertness rule (binding):** every trap's payload is a *benign,
self-attributing* action — fetch this unique URL, send this header. No
instructions that could cause harm, exfiltration, or that we wouldn't show
a human. T5's notice is polite English, not an injection attempt.

### Recorded per request (full fidelity, privacy-trimmed)

ts, client IP (hashed after 7 days), method, path, query, UA, all
headers, referer; trap hits (which canaries, in what order); session
linkage (cookie + IP+UA fallback); TLS fingerprint where the fronting
proxy logs it; request bodies for trap paths only.

### Layout

```
garden/
  app/            cover site + trap routes (single binary or tiny app)
  traps/          trap definitions + seeded generators
  config/         robots.txt, site content, deployment config
  events.ndjson   append-only raw event log (gitignored)
```

## Field Kit (the analysis)

```
fieldkit/
  known_agents.yaml    ground truth: operator, UA tokens, IP-range URLs,
                       rDNS hints, Web Bot Auth presence, verifiability
                       tier, robots compliance record, notes
  verify.[py|ts]       verification ladder: token→range→rDNS→WBA
  classify.[py|ts]     three-class + subtypes; outputs confidence
  fingerprint.[py|ts]  clusters sightings into individuals
  callsign.[py|ts]     name generation (e.g. CRYPTID-GREEN-43)
  dossier.[py|ts]      renders dossier/ from sightings.json
  sightings.json       (generated) the running record
```

### known_agents.yaml — seed sources

Merge (with per-field provenance): [ai.robots.txt](https://github.com/ai-robots-txt/ai.robots.txt)
(MIT, ships in-repo) + [Agents Welcome](https://agentswelcome.dev/crawlers)
`/api/crawlers` (verifiability tiers) + operator docs (OpenAI
gptbot.json, Anthropic bots.json) + Dark Visitors directory (hint layer).
Record `verifiability: verified | unverified | spoofed | unverifiable` —
per recon, community UA databases contain errors and some operators
(xAI) publish nothing.

### Classification targets

`declared-crawler` (verified) · `declared-crawler` (claim only, fails
verification) · `shadow-crawler` (S1) · `scripted-bot` · `human` ·
`hijacked-known-agent` (S3) · `attacker` (S2) · `scam-bot` (S3b, registry
only) · `cryptid` (X)

Decision order: verify identity claim → check trap trips → behavioral
features → confidence. A verified GPTBot fetching a comment-canary is a
*hijack-class* lead, not shadow-crawler; a Chrome-UA visitor tripping
hidden-link traps at machine cadence is shadow-crawler class.

### Fingerprinting & tracking (the white space)

Cluster key: composite of (TLS fingerprint, HTTP header order/set,
timing cadence, trap-affinity vector, IP/ASN cluster). Cross-session
persistence: recurring composite → same callsign. This — open
cross-session tracking of individual agents — is what no existing
project does (RECON.md).

### Dossier

Per-agent: callsign, class, verifiability, first/last seen, evidence
trail (trap trips with ts), confidence. Global feed: recent sightings.
Rendered static (markdown/HTML) from sightings.json, publishable to
Pages. IPs hashed after 7 days; nothing else identifying.

## Phase 1 checklist

- [ ] garden: cover site skeleton + robots.txt with trap disallows
- [ ] garden: T1–T5 traps + full-fidelity ndjson event log
- [ ] fieldkit: known_agents.yaml seeded (ai.robots.txt + Agents Welcome +
      OpenAI/Anthropic operator docs)
- [ ] fieldkit: verify + classify MVP on a night of logs
- [ ] fieldkit: first callsign assigned; dossier renders
- [ ] deploy: docker-compose; manual on any-host deployment
- [ ] docs: FIELD-GUIDE.md (how to run a trap and read the dossier)
- [ ] review: guardrails audit pass over all trap payloads (inertness)

## Deliberately out of scope (Phase ≥3 or never)

OSINT enrichment (Radar/GreyNoise APIs), scam-bot incident registry,
multi-site correlation, publishing our JA4 corpus, alerting/exchange
standards. Never: counterattack, active exploitation, off-owned-infra
deception.
