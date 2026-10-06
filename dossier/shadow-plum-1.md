# SHADOW-PLUM-1

- **class:** shadow-crawler (confidence 0.7)
- *Undeclared automated visitor that tripped canaries invisible to humans (S1)*

- **user-agent:** `curl/8.7.1`
- **identity claim:** none
- **verification:** no-claim
- **network:** unknown(docker-bridge).0/24 (cluster)
- **network attribution:** app request log
- **first/last seen:** 2026-10-06T19:01:06+0000 → 2026-10-06T19:01:07+0000
- **requests:** 3 (3.0/s peak)

## Evidence

- tripped 1 canary (t1-home-fern) invisible to humans, while presenting a no-UA-claim

## Canary trips

- `t1-home-fern`

---
*Behavioral record of a visit to Trap Garden infrastructure. Not an accusation; see docs/SCOPE.md.*
