# Phase 1 Completion Report — 2026-10-06

Shipped in one session, per DESIGN.md's Phase 1 checklist. Every item
verified end-to-end by tests/integration_test.py.

## Delivered

- **Trap Garden** (`garden/`) — stdlib-only Python server posing as
  "Mossline, plot 12", a small allotment-gardening notes site. Five trap
  surfaces woven in (T1 hidden links ×3, T2 invisible text, T3 HTML
  comment, T5 comprehension gate + JSON endpoint), robots.txt compliance
  traps, full-fidelity ndjson event log (every request incl. 404/405/501
  and POST bodies — no silent monitoring gaps), cookie sessions.
- **Field Kit** (`fieldkit/`) — 189-agent ground truth merged from four
  registries (ai.robots.txt MIT-vendored + Agents Welcome + OpenAI/
  Anthropic IP range files, all with attribution + sha256 + refresh
  script); verification ladder (token → IP range → verifiability);
  two-pass sessionization; classifier (9 classes, evidence trails,
  explicit confidence); deterministic fingerprinting + callsigns
  (SHADOW-LOAM-1 &c.); dossier renderer with privacy policy (/24
  clusters, salted hashes after 7 days).
- **Dossier** (`dossier/`) — index + per-agent profiles, regenerated
  idempotently (stale profiles removed).
- **Deploy** (`deploy/`) — hardened docker-compose (directory mount so
  events survive; no-new-privileges), Dockerfile, zero pip deps.
- **Tests** (`tests/integration_test.py`) — five visitor personas
  (human w/ cookies, shadow agent same-UA cookie-less, spoofed GPTBot,
  gate responder, masscan scanner) through the real server → analyzer →
  all five classes asserted.

## Verified behaviors worth noting

- Cookie-honoring browser = human; same-UA cookie-less visitor following
  invisible links = shadow-crawler. The cookie distinction is itself a
  signal, handled honestly.
- Verification ladder works: GPTBot claim from a non-OpenAI IP →
  spoof-suspected (0.85). Note the seeds' ranges rotate; re-fetch before
  trusting spoof analysis (fetch_seeds.sh).
- Known limitation (documented in analyze.py): visitors sharing IP+UA
  with no cookies (NAT egress) can merge in the fallback pass.

## Fixes applied during self-review (pre-panel)

- PUT/DELETE/PROPFIND/BREW …: every method now logged (base class was
  silently 501-ing unknown methods).
- `match_agent` substring bug: "VSCode" no longer matches the "Code"
  agent (word-boundary matching).
- Gate evidence wording: "voluntary self-identification", not "proof" —
  header is spoofable by readers of our public docs.
- Dossier renderer removes stale profiles between runs.
- Compose file: directory mount (single-file mount would become a
  directory on first run).

## Fixes from the edge-case verification pass (verified repros)

- **Silent crash gap (real, repro'd):** `GET http://[zz` raised
  ValueError in `urlsplit` before logging — connection reset, zero ndjson
  trace. Now: caught → 400 + log. Same for garbage `Content-Length` on
  POST/PUT (`abc` → treated as empty, still logged). Any other dispatch
  exception → `_log_crash` → 500 + log. Full-fidelity guarantee survives
  bugs by construction now.
- **Early malformed requests (real):** stdlib 400s for unparseable
  request lines were never logged (attributes didn't exist yet).
  `_log_event` is now getattr-safe and the `send_error` hook logs them
  (verified: `GARBAGE\r\n\r\n` → logged, status 400).
- **Cookie regex boundary:** `xmossline_sid=` and 17+-hex values no
  longer match (lookarounds added); fixation impact was already bounded
  (sid only keys log attribution, no auth).
- **`Secure` cookie attribute:** added conditionally (X-Forwarded-Proto
  https or direct TLS socket) — unconditional Secure broke sessions over
  plain HTTP, which the integration test caught as a human-class
  regression before it shipped.

## Awaiting

- Adversarial review panel results (guardrails / correctness /
  credibility / red-team) — fixes to be applied on confirmation.
- Real deployment: needs the user's VPS/domain choice (SCOPE.md open
  question); local run proven, docker config ready.
