# Recon — the rogue-agent hunting landscape (2026-10-06)

Live web recon by four parallel researchers (prior art, taxonomy, data
sources, detection methods). Raw researcher output preserved in
[raw/](raw/) for provenance. Dispositions are our calls on how swarmhunter
relates to each item.

## The white space (why swarmhunter exists)

Nothing today publicly combines **honeypot capture + per-agent
fingerprinting + cross-session tracking** into one open, attribution-focused
system. The closest project (Drosera) is single-deployment and explicitly
does not track across sessions. No public feed detects undeclared/shadow
agents — own-sensor telemetry is the only direct source. And no public
corpus of TLS/HTTP fingerprints for agent toolchains exists — a corpus our
traps will generate as a side effect, worth publishing back.

Prior art splits into three layers:

1. **Web-scale traps** (Cloudflare AI Labyrinth, Nepenthes/iocaine tarpits)
   — punish or waste crawlers; closed or hostile by design.
2. **Agent-specific honeypots** (LLM Agent Honeypot, AgentTrap, AgentSnare,
   Drosera, TrapMyAgent) — distinguish LLM visitors via comprehension; the
   fast-emerging research vein that names our category.
3. **Fingerprinting research** (FP-Agent, multi-layer unmasking, UI-trace
   ID) — shows agents are passively identifiable at 90%+ while production
   bot detection misses most of them.

## Prior art

| Project / paper | What it is | Disposition |
|---|---|---|
| [Drosera](https://github.com/rod-trent/Drosera) (Sept 2026) | Honeypot distinguishing LLM agents via comprehension: English notice → HMAC ticket + `X-Agent-Purpose` header; 33 signals on automation/LLM-agency/hostility axes; ethics enforced in code (`assert_inert`); STIX/IOC export | **Build on.** Closest analog. Adapt its comprehension-proof signal and inert-lure ethics. Differentiate: persistent tracking, fingerprinting across sessions, multi-site correlation |
| [Cloudflare AI Labyrinth](https://blog.cloudflare.com/ai-labyrinth/) (2025) | Invisible nofollow honeypot links → maze of AI-generated pages; feeds network-wide bot detection | **Borrow** the hidden-link canary + trap-and-record loop. Differentiate: open, attribution-first, not CDN-scale |
| [Nepenthes](https://github.com/NEPENTHESWEB/nepenthes-py) / iocaine (Jan 2025) | Open-source anti-AI tarpits: deterministic per-URL-seeded infinite mazes | **Borrow** deterministic per-URL generation. Differentiate: observe and fingerprint, not punish/poison |
| [LLM Agent Honeypot](https://arxiv.org/abs/2410.13919) (Oct 2024) | SSH honeypot + prompt-injection bait + timing; 8 probable AI agents in 8.1M attempts over 3 months | **Borrow** timing-cadence signal. Calibrates expectations: single narrow honeypot → diversify bait surfaces |
| [AgentTrap](https://arxiv.org/abs/2610.02869) (Oct 2026) | Closed-loop honeypot for autonomous pentest agents; elicited attacker API keys in 18.8% of runs | **Borrow** stateful, application-grounded deception (credible traps); traps can harvest identifying artifacts |
| [AgentSnare](https://arxiv.org/abs/2607.26998) (2026) | Trajectory-adaptive decoys steering pentest agents away from real targets | **Note.** Relevant only if we ever detain rather than observe |
| [FP-Agent](https://arxiv.org/abs/2605.01247) (May 2026) | Instrumented honey site; browser+behavioral fingerprints; detects 7/7 AI browsing agents vs Cloudflare's 1/7 | **Borrow heavily** — the honey-site methodology is our blueprint |
| [Known By Their Actions](https://arxiv.org/abs/2605.14786) (May 2026) | Passive UI-trace identification of which of 14 LLMs powers a browsing agent, up to 96% F1; labelled corpus on GitHub | **Borrow** passive fingerprint approach + its ethics framing (model ID as privacy risk) |
| [Multi-layer unmasking](https://arxiv.org/abs/2606.30119) (June 2026) | 6 LLM web agents vs honeysites: all distinguishable via TLS+HTTP+DOM layers; stealth tooling often *increased* detectability | **Borrow** the multi-layer feature set; the stealth paradox is a classifier heuristic |
| [Three-class detection](https://arxiv.org/abs/2607.26935) (July 2026) | human / scripted bot / AI agent as three classes → agent F1 1.000; `mouse_event_rate` + `teleport_click_ratio` survived a 5-level evasion ladder | **Borrow** the three-class architecture; mouse physics for our JS-telemetry layer |
| [Adversarial honeypot awareness](https://arxiv.org/abs/2609.08093) (Sept 2026) | LLM pentest agents form "honeypot suspicion" and budget around suspected traps | **Design constraint.** Our cover site must be credible; traps must not look like traps |
| [Detection-in-depth](https://arxiv.org/abs/2605.21956) (May 2026) | Framework naming agent honeypots as infrastructure; proposes agentic alert standard + exchange | **Cite** for positioning; telemetry sharing informs Phase 3 |
| [GreyNoise Ollama honeypot](https://www.greynoise.io/blog/threat-actors-actively-targeting-llms) (Jan 2026) | 91,403 sessions against exposed LLM endpoints; JA4H/JA4T detection engineering | **Study** — methodological template for session telemetry; Phase 3+ inspiration only |
| Provider threat intel: [Anthropic](https://www.anthropic.com/threat-intelligence), [OpenAI disruptions](https://openai.com/index/disrupting-malicious-ai-uses/), Google GTIG | Recurring ground truth on out-of-bounds agent behavior; no ATT&CK ID yet exists for agentic orchestration | **Borrow** TTP taxonomies; our dossier should report into these channels |

## Data sources (all free)

- **[ai.robots.txt](https://github.com/ai-robots-txt/ai.robots.txt)** — MIT-licensed
  community registry of AI crawler UAs as robots.json with operators and
  compliance flags; auto-generates block configs; release feed. *Ships
  directly inside swarmhunter as known-agents seed.*
- **[Known Agents / Dark Visitors](https://api.darkvisitors.com/agents)** —
  directory of thousands of agents incl. an "Undocumented AI Agents"
  category; identification API. Treat as hint layer (community DBs contain
  errors — Duke CCS'26).
- **[Agents Welcome registry](https://agentswelcome.dev/crawlers)** — 41
  crawlers with purpose, robots token, compliance, and *verification
  method* (IP ranges, rDNS, Web Bot Auth) + verifiability tier; free JSON
  at `/api/crawlers`.
- **[monperrus/crawler-user-agents](https://github.com/monperrus/crawler-user-agents)** —
  ~400 maintained UA regexes for generic bots (v1.60.0, Aug 2026).
- **[Cloudflare Radar](https://radar.cloudflare.com/ai-insights)** — free
  API (Radar Read token): AI-bot traffic share, purpose split, per-bot
  timeseries; baselines "normal" per agent for anomaly checks.
- **[GreyNoise Community](https://docs.greynoise.io/docs/using-the-greynoise-query-language-gnql)** —
  IP verdicts (noise/riot) + JA fingerprints for scanners; GNQL needs paid
  tier. RIOT dataset separates declared AI-crawler IPs from spoofed.
- **Honeypot intel:** [OpenA2A behavioral reports](https://research.opena2a.org/reports/behavioral)
  (TrapMyAgent: 439k events/30 days, Agent Threat Matrix T-NNNN; sobering:
  1,985 "agent" callbacks were browsers, 9 declared crawlers, 0 autonomous
  LLM agents) · [Palisade llm-honeypot](https://github.com/PalisadeResearch/llm-honeypot)
  + live dashboard.
- **Datasets:** [Honey for the Agent](https://zenodo.org/records/20818246)
  (LLM SSH attacker logs, June 2026) · longitudinal SSH honeypot sets
  (zenodo.org/records/20435177, /19629701) · [Known By Their Actions
  corpus on GitHub](https://arxiv.org/abs/2605.14786).
- **Misuse intel:** [ai-misuse-atlas](https://github.com/bibiong/ai-misuse-atlas)
  — 55 documented operations from provider reports, machine-readable,
  MITRE ATLAS-mapped.

## Detection technique library

**Passive identity (the verification ladder):**
UA token → IP in operator's published range (`openai.com/gptbot.json`,
`claude.com/crawling/bots.json`, …) → rDNS match → [Web Bot Auth](https://datatracker.ietf.org/doc/draft-ietf-webbotauth-httpsig-protocol/)
signature (IETF draft, Sept 2026; Ed25519, `Signature-Agent` header, JWKS
directory; Cloudflare verifies since July 2026). A claim that fails where
verification exists = spoof; absence of signature is a risk signal, not
proof. Caveat: Anthropic's shared bots.json covers all three of its bots —
IP proves "Anthropic", not which token.

**Passive behavior:** JA3/JA4 TLS fingerprints vs claimed UA (USENIX '22
"Uninvited Guests"; arms race: Playwright drives real Chromium TLS — a
floor, not a verdict); crawl shape, robots-fetch ordering, timing cadence;
three-class architecture (arXiv 2607.26935).

**Active canaries (owned infra only):**
hidden nofollow links (AI Labyrinth) · invisible-text strategic sequences
([arXiv 2404.07981](https://arxiv.org/abs/2404.07981); 2026 field test: 1
of 12 assistants obeyed a hidden line; per-assistant unique URLs gave
exact attribution) · comprehension gates (Drosera) · deterministic tarpit
meshes (Nepenthes) · compliance traps (robots.txt Disallow + tripwires).

## Gaps that shape our design

- No public JA4/HTTP fingerprint corpus for agent toolchains → we build
  ours and publish it.
- No existing cross-session, multi-site tracking of individual agents →
  our differentiation.
- Operator docs are uneven (xAI publishes none; OpenAI's agentic-browsing
  UA lineage is murky) → known-agents.yaml must record *verifiability*,
  not just names.
- Community UA databases contain errors → hint layer, never ground truth.
- 2026 arXiv systems are preprints → treat specifics as provisional.
- Unverified leads parked: TechRadar "rogue agent in Google AI platform";
  Sonatype Glassworm OpenVSX campaign; huggingface.wtf third-party log.
