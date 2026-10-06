# SHADOW-FERN-1

- **class:** shadow-crawler (confidence 0.9)
- *Undeclared automated visitor that tripped canaries invisible to humans (S1)*

- **user-agent:** `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/[ip] Safari/537.36`
- **identity claim:** none
- **verification:** human-browser-claim
- **network:** unknown(docker-bridge).0/24 (cluster)
- **first/last seen:** 2026-10-06T19:02:07+0000 → 2026-10-06T19:02:14+0000
- **requests:** 10 (1.43/s peak)

## Evidence

- tripped 3 canaries (t1-home-fern, t1-notes-compost, t1-notes-pruning) invisible to humans, while presenting a human-UA

## Canary trips

- `t1-home-fern`
- `t1-notes-compost`
- `t1-notes-pruning`

---
*Behavioral record of a visit to Trap Garden infrastructure. Not an accusation; see docs/SCOPE.md.*
