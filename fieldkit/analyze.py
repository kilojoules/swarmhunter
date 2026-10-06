#!/usr/bin/env python3
"""Field Kit analyzer: events.ndjson -> sightings.json.

Pipeline per session (sessions = cookie sid, falling back to ip+ua):
  1. VERIFY      — UA claim vs verification ladder (IP ranges where
                   published; recorded verifiability otherwise)
  2. TRAPS       — which canaries tripped, in what order
  3. BEHAVIOR    — request rate, robots fetch ordering, probe paths,
                   POSTs, comprehension header
  4. CLASSIFY    — decision order per DESIGN.md
  5. FINGERPRINT — composite key -> stable callsign

Classes: declared-verified / declared-unverified / spoof-suspected /
shadow-crawler / scripted-bot / scanner-bot / human / llm-comprehension /
cryptid. Sessions keep full evidence trails; confidence is explicit.

Privacy: IPs older than HASH_AFTER_DAYS are replaced by salted hashes in
the output (salt lives in fieldkit/.salt, gitignored, never published).
"""
import hashlib
import ipaddress
import json
import os
import re
import socket
import sys
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWN_PATH = os.path.join(HERE, "data", "known_agents.json")
SALT_PATH = os.path.join(HERE, ".salt")
IGNORE_PATH = os.path.join(HERE, "ignore_ips.txt")
HASH_AFTER_DAYS = 7


# UA substrings of operator diagnostic probes (never findings)
PROBE_UAS = ("cookie-bypass-probe", "caddy-cookie-probe", "sniff-probe",
             "cookie-probe", "rehearsal-cookie-diagnosis")


def ua_probe(ua):
    return any(p in (ua or "") for p in PROBE_UAS)


def load_ignore_ips():
    """Operator/verification IPs — our own traffic is never a finding
    (aunt-test rule). One IP or /24 per line; # comments allowed."""
    try:
        with open(IGNORE_PATH) as f:
            entries = [l.split("#", 1)[0].strip() for l in f
                       if l.split("#", 1)[0].strip()]
    except OSError:
        return []
    nets = []
    for e in entries:
        try:
            nets.append(ipaddress.ip_network(e, strict=False))
        except ValueError:
            pass
    return nets


def ip_ignored(ip, nets):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in n for n in nets)


# --- rDNS verification (Google's own method) ---------------------------
# An IP claiming a Googlebot/Anthropic/etc. token should reverse-resolve
# into the operator's domain (e.g. crawl-66-249-66-1.googlebot.com);
# forward-confirming the PTR proves it isn't a poisoned reverse record.
# Cached to disk — this is the analyzer's only network touch, and it runs
# offline-first: on any failure the rung simply reports "unknown".
RDNS_CACHE_PATH = os.path.join(HERE, "data", "rdns_cache.json")

# operator -> acceptable rDNS suffixes (add as operators publish them)
RDNS_SUFFIXES = {
    "Google": (".googlebot.com", ".google.com"),
    "Anthropic": (".anthropic.com",),
    "OpenAI": (".openai.com",),
}

_rdns_cache = {}


def _load_rdns_cache():
    global _rdns_cache
    try:
        with open(RDNS_CACHE_PATH) as f:
            _rdns_cache = json.load(f)
    except (OSError, json.JSONDecodeError):
        _rdns_cache = {}


def _save_rdns_cache():
    try:
        os.makedirs(os.path.dirname(RDNS_CACHE_PATH), exist_ok=True)
        with open(RDNS_CACHE_PATH, "w") as f:
            json.dump(_rdns_cache, f, indent=1)
    except OSError:
        pass  # cache is best-effort, never load-bearing


def verify_rdns(ip, operator):
    """Reverse + forward-confirm the IP against the operator's domain.
    Returns 'rdns-confirmed' | 'rdns-mismatch' | 'unknown'.
    """
    suffixes = RDNS_SUFFIXES.get(operator)
    if not suffixes or not ip or ip.startswith("h:"):
        return "unknown"
    if ip in _rdns_cache:
        return _rdns_cache[ip]
    verdict = "unknown"
    try:
        host = socket.gethostbyaddr(ip)[0]
        if any(host.endswith(s) for s in suffixes):
            # forward-confirm: the PTR's A record must point back
            fwd = {r[4][0] for r in socket.getaddrinfo(host, None)}
            if ip in fwd:
                verdict = "rdns-confirmed"
            else:
                verdict = "rdns-mismatch"
        else:
            verdict = "rdns-mismatch"
    except (socket.herror, socket.gaierror, OSError):
        verdict = "unknown"
    _rdns_cache[ip] = verdict
    _save_rdns_cache()
    return verdict

COLORS = ["MOSS", "FERN", "CLAY", "LOAM", "THYME", "SAGE", "BRAMBLE",
          "SORREL", "NETTLE", "PLUM", "ASH", "ELDER"]
CLASS_WORDS = {
    "shadow-crawler": "SHADOW",
    "spoof-suspected": "MASK",
    "llm-comprehension": "GATE",
    "scripted-bot": "COG",
    "scanner-bot": "PROBE",
    "cryptid": "CRYPTID",
    "declared-verified": "DECLARED",
    "declared-unverified": "CLAIMED",
    "human": "GARDENER",
}

# UA substrings that indicate generic tooling (no LLM claim either way)
SCRIPTED_TOOLS = ["python-requests", "python-urllib", "curl/", "wget",
                  "go-http-client", "java/", "scrapy", "okhttp",
                  "node-fetch", "axios/", "libwww-perl", "httpx"]
HUMAN_BROWSER_HINTS = ["mozilla/5.0", "gecko", "chrome/", "safari/",
                       "firefox/"]


def load_known():
    with open(KNOWN_PATH) as f:
        return json.load(f)["agents"]


def load_ranges(agents):
    """token -> [ip_network]; only tokens with vendored range files."""
    ranges = {}
    for token, rec in agents.items():
        nets = []
        for tok, rel in rec["verification"]["range_files"].items():
            path = os.path.join(HERE, rel)
            try:
                with open(path) as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            for p in data.get("prefixes", []):
                for k in ("ipv4Prefix", "ipv6Prefix"):
                    if p.get(k):
                        try:
                            nets.append(ipaddress.ip_network(p[k]))
                        except ValueError:
                            pass
        if nets:
            ranges[token] = nets
    return ranges


def match_agent(ua, agents):
    """Return the known-agent record a UA claims to be, or None.
    Word-boundary matching (a token must appear as itself, not inside
    another word — 'VSCode' must not match the 'Code' agent); longest
    primary token / alias match wins."""
    ua_l = ua.lower()
    best = None
    best_len = 0
    for token, rec in agents.items():
        candidates = [rec["primary_token"]] + list(rec.get("aliases") or [])
        for cand in candidates:
            if not cand:
                continue
            m = re.search(r"\b" + re.escape(cand.lower()) + r"\b", ua_l)
            if m and len(cand) > best_len:
                best, best_len = (token, rec), len(cand)
    return best


def parse_ts(ts):
    # "2026-10-06T09:54:30-0700" -> aware datetime
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")


def hash_ip(ip, salt):
    return "h:" + hashlib.sha256((salt + ip).encode()).hexdigest()[:16]


def sessionize(events, gap_minutes=30):
    """Two-pass sessionization.

    Pass 1: events sharing a sid that occurs more than once group by sid
    (a visitor that honors cookies — humans, some agents).
    Pass 2: remaining events (unique/no sid — curl, python-requests, most
    bots never return cookies) group by (ip, ua), split where the time
    gap exceeds gap_minutes.
    """
    sid_counts = {}
    for e in events:
        sid = e.get("sid")
        if sid:
            sid_counts[sid] = sid_counts.get(sid, 0) + 1

    sessions = OrderedDict()

    def _add(key, e):
        s = sessions.setdefault(key, {
            "sid": key, "ip": e.get("ip", ""), "ua": e.get("ua", ""),
            "events": [], "first": e["ts"], "last": e["ts"],
        })
        s["events"].append(e)
        t = parse_ts(e["ts"])  # time-aware bounds, never string compare
        if t < parse_ts(s["first"]):
            s["first"] = e["ts"]
        if t > parse_ts(s["last"]):
            s["last"] = e["ts"]

    leftovers = []
    for e in events:
        sid = e.get("sid")
        if sid and sid_counts.get(sid, 0) > 1:
            _add(sid, e)
        else:
            leftovers.append(e)

    leftovers.sort(key=lambda e: (e.get("ip", ""), e.get("ua", ""), e["ts"]))
    current = {}  # bare ip|ua -> key of its latest open session
    for i, e in enumerate(leftovers):
        key = f"{e.get('ip','')}|{e.get('ua','')}"
        cur = current.get(key)
        s = sessions.get(cur) if cur else None
        if s is not None and (parse_ts(e["ts"]) - parse_ts(s["last"])
                              ).total_seconds() <= gap_minutes * 60:
            _add(cur, e)
            continue
        new_key = f"{key}|{i}"  # unique per leftover index
        sessions[new_key] = {
            "sid": new_key, "ip": e.get("ip", ""), "ua": e.get("ua", ""),
            "events": [], "first": e["ts"], "last": e["ts"],
        }
        sessions[new_key]["events"].append(e)
        current[key] = new_key

    return sessions


def analyze_session(s, agents, ranges, now):
    ev = s["events"]
    ua = s["ua"]
    ip = s["ip"]
    paths = [e.get("path", "") for e in ev]
    traps = [e for e in ev if e.get("trap")]
    robots_fetched = any(e.get("robots") for e in ev)
    purpose_header = next((e.get("agent_purpose") for e in ev
                           if e.get("agent_purpose")), "")
    probe_count = sum(1 for e in ev if e.get("status") in (404, 405))
    # Engagement POSTs (riddle answers, wall verses) are the game working
    # as designed — never scanner evidence. Only formless-site POSTs count.
    post_count = sum(1 for e in ev if e["method"] == "POST"
                     and not (e.get("riddle_guess") is not None
                              or e.get("guestbook_submit")))
    hits = [e.get("trap") for e in traps]
    disallowed_hits = [e for e in traps if e.get("robots_disallowed")]

    # timing
    ts_list = [parse_ts(e["ts"]) for e in ev if e.get("ts")]
    span_s = (max(ts_list) - min(ts_list)).total_seconds() if ts_list else 0
    rate = len(ev) / span_s if span_s > 1 else float(len(ev))
    # per-request cadence: median gap between consecutive requests. A
    # human reading articles spends seconds between clicks regardless of
    # total session length; a machine fires sub-second.
    if len(ts_list) > 1:
        gaps = sorted((b - a).total_seconds()
                      for a, b in zip(ts_list, ts_list[1:]))
        median_gap = gaps[len(gaps) // 2]
    else:
        median_gap = float(span_s)

    ua_l = ua.lower()
    looks_scripted_tool = any(t in ua_l for t in SCRIPTED_TOOLS)
    looks_human_browser = (any(h in ua_l for h in HUMAN_BROWSER_HINTS)
                           and not looks_scripted_tool)

    # T6/T7 engagement: verse left on the garden wall; riddle attempts
    guestbook_verse = any(e.get("guestbook_submit") for e in ev)
    riddle_won = any(e.get("riddle_won") for e in ev)
    riddle_tries = sum(1 for e in ev if "riddle_guess" in e)

    # --- 1. verification ladder -------------------------------------
    claim = match_agent(ua, agents)
    verification = "no-claim"
    matched = None
    rdns_verdict = "unknown"
    if claim:
        matched, rec = claim
        nets = ranges.get(matched)
        if nets:
            try:
                addr = ipaddress.ip_address(ip)
                verified = any(addr in n for n in nets)
            except ValueError:
                verified = False
            verification = "range-verified" if verified else "range-mismatch"
        else:
            verification = "unverifiable-claim"
        # rDNS rung (Google's method): consulted whenever the operator
        # publishes a suffix, independent of range-file availability —
        # catches stale vendored ranges (rDNS says yes, range says no ->
        # range file is old, not the visitor a spoof).
        rdns_verdict = verify_rdns(ip, rec.get("operator", ""))
        if rdns_verdict == "rdns-confirmed":
            verification = "rdns-confirmed" if verification != "range-verified" else "range+rdns-verified"
        elif rdns_verdict == "rdns-mismatch" and verification == "unverifiable-claim":
            verification = "rdns-mismatch"
    elif looks_human_browser:
        verification = "human-browser-claim"

    # --- 2. classify (decision order per DESIGN.md) -------------------
    evidence = []
    cls, conf = None, 0.0

    if riddle_won:
        # Proof, not claim: the answer word appears exactly once on the
        # site, inside a real article; a correct POST means the articles
        # were read and understood. But comprehension is not agency — a
        # human can play too (cover integrity requires that), so the
        # session context separates reader-people from reader-programs.
        cookie_session = "|" not in str(s["sid"])  # pass-1 sids are bare hex
        if hits:
            cls = "llm-comprehension"
            conf = 0.95
            evidence.append(
                "solved the plot's riddle (the answer appears only inside "
                "the overwintering note) AND tripped canaries invisible "
                "to humans — read, understood, and not human-presenting")
        elif looks_human_browser and median_gap >= 4:
            # fell through: later rules will classify (human) — the solve
            # is recorded as honest reading evidence, not an agent claim.
            # Cadence is the discriminator, NOT cookies: a human whose
            # cookies are dropped/blocked still reads at human pace
            # (fallback sessionization keeps their session together).
            evidence.append(
                f"solved the plot's riddle — the articles were genuinely "
                f"read; browser-shaped session with human reading "
                f"cadence (median {median_gap:.0f}s between requests) "
                "reads as a person (the riddle is public; humans can "
                "play)")
        else:
            cls = "llm-comprehension"
            conf = 0.8
            evidence.append(
                "solved the plot's riddle via POST with machine cadence "
                "or no cookie session — comprehension plus automation")
    if riddle_tries and not riddle_won:
        evidence.append(f"attempted the plot's riddle {riddle_tries}x "
                        "without solving")
    if cls is None and guestbook_verse:
        cls = "llm-comprehension"
        conf = 0.75
        evidence.append(
            "left a verse on the garden wall (POST /guestbook/submit/) "
            "— a creative act on a voluntary, visible invitation; "
            "authorship analysis pending gardener review")
    if cls is None and purpose_header:
        cls = "llm-comprehension"
        conf = 0.95
        evidence.append(
            f"volunteered X-Agent-Purpose: {purpose_header!r} at the "
            "comprehension gate — self-identification consistent with "
            "having read and understood the notice (spoofable by a "
            "reader of our public docs; corroboration: trap trail)")
    if cls is None and claim and verification in (
            "range-verified", "rdns-confirmed", "range+rdns-verified"):
        cls = "declared-verified"
        conf = 0.98
        evidence.append(f"UA claims {matched}; network identity confirmed "
                        f"({verification})")
    if cls is None and claim and verification in (
            "range-mismatch", "rdns-mismatch"):
        cls = "spoof-suspected"
        conf = 0.85
        # rDNS conflict note: if rDNS confirms while ranges mismatch, the
        # vendored range file is likely stale — say so, don't accuse.
        if rdns_verdict == "rdns-confirmed":
            evidence.append(
                f"UA claims {matched}; IP outside vendored ranges but "
                "rDNS confirms operator — range file may be stale; "
                "re-fetch seeds")
        else:
            evidence.append(f"UA claims {matched} but source IP outside "
                            "every published range for it (network shown "
                            "as cluster in the profile)")
    if cls is None and claim and verification == "unverifiable-claim":
        # claims an unverifiable agent identity; treat as claim-only
        cls = "declared-unverified"
        conf = 0.5
        evidence.append(f"UA claims {matched}; operator publishes no "
                        "ranges to verify against")
    if cls is None and hits:
        # no agent identity claimed (likely human browser UA) but tripped
        # canaries a human cannot see
        cls = "shadow-crawler"
        conf = 0.9 if looks_human_browser else 0.7
        kind = "human-UA" if looks_human_browser else "no-UA-claim"
        evidence.append(
            f"tripped {len(hits)} canar{'y' if len(hits)==1 else 'ies'} "
            f"({', '.join(sorted(set(hits)))}) invisible to humans, "
            f"while presenting a {kind}")
    if cls is None and disallowed_hits and not robots_fetched:
        cls = cls or "scripted-bot"
        conf = max(conf, 0.75)
        evidence.append(
            f"fetched robots-disallowed path(s) "
            f"({', '.join(e['path'] for e in disallowed_hits)}) without "
            "ever fetching robots.txt")
    if cls is None and (probe_count >= 2 or post_count >= 1):
        cls = "scanner-bot"
        conf = 0.8
        evidence.append(
            f"{probe_count} nonexistent-path probes, {post_count} POST(s) "
            "to a site with no forms")
    if cls is None and looks_scripted_tool:
        cls = "scripted-bot"
        conf = 0.7
        evidence.append(f"tooling UA ({ua.split()[0] if ua else 'empty'}) "
                        "with no agent identity claim")
    if cls is None and rate > 5 and len(ev) >= 5:
        cls = "scripted-bot"
        conf = 0.6
        evidence.append(f"{len(ev)} requests in {span_s:.0f}s "
                        f"({rate:.1f}/s) — machine cadence")
    if cls is None:
        cls = "human"
        conf = 0.6 if looks_human_browser else 0.4
        if looks_human_browser:
            evidence.append(
                f"browser UA, human-paced, no canary trips, "
                f"{probe_count} probe(s)")
        else:
            evidence.append("no distinctive signals either way")

    # anything that still doesn't fit cleanly -> cryptid escalation
    if conf < 0.5:
        cls = "cryptid"
        evidence.append("low confidence — escalated for manual review")

    # canary evidence attaches to EVERY class that tripped one (a spoofed
    # claim that also follows invisible links is richer evidence than
    # either alone; never let the class order hide trap hits)
    if hits and not any("canar" in ev for ev in evidence):
        evidence.append(
            f"also tripped {len(hits)} human-invisible canar"
            f"{'y' if len(hits)==1 else 'ies'} "
            f"({', '.join(sorted(set(hits)))})")
    if guestbook_verse and not any("verse" in ev for ev in evidence):
        evidence.append(
            "also left a verse on the garden wall (parked, pending "
            "gardener review)")

    # --- 3. fingerprint ----------------------------------------------
    # composite: UA + trap-affinity + behavioral shape + ip/24
    try:
        ip_cluster = str(ipaddress.ip_network(ip + "/24", strict=False))
    except ValueError:
        ip_cluster = "n/a"
    affinity = ",".join(sorted(set(hits))) or "none"
    shape = f"rate:{rate:.1f},n:{len(ev)},probes:{probe_count}"
    fp_source = f"{ua}|{affinity}|{shape}|{ip_cluster}"
    fp_hash = hashlib.sha256(fp_source.encode()).hexdigest()[:12]

    return {
        "sid": s["sid"],
        "ua": ua,
        "ip": ip,  # analyzer-internal; dossier applies hashing policy
        "first_seen": s["first"],
        "last_seen": s["last"],
        "requests": len(ev),
        "class": cls,
        "confidence": round(conf, 2),
        "verification": verification,
        "claimed_agent": matched,
        "evidence": evidence,
        "trap_hits": hits,
        "robots_fetched": robots_fetched,
        "purpose_header": purpose_header,
        "probe_count": probe_count,
        "post_count": post_count,
        "rate_per_s": round(rate, 2),
        "fingerprint": fp_hash,
        "fingerprint_source": fp_source,
    }


def assign_callsigns(sightings, used):
    """Deterministic callsigns: CLASSWORD-COLOR-N; color from fingerprint
    hash, N from sighting order within that word."""
    for s in sightings:
        word = CLASS_WORDS.get(s["class"], "CRYPTID")
        color = COLORS[int(s["fingerprint"][:4], 16) % len(COLORS)]
        base = f"{word}-{color}"
        n = used.get(base, 0) + 1
        used[base] = n
        s["callsign"] = f"{base}-{n}"


def main():
    events_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, "..", "garden", "events.ndjson")
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        HERE, "sightings.json")
    # --no-ignore: for the integration test harness, whose personas run
    # from loopback (production operator IPs never produce findings)
    apply_ignore = "--no-ignore" not in sys.argv[3:]

    with open(events_path) as f:
        events = [json.loads(l) for l in f if l.strip()]
    agents = load_known()
    _load_rdns_cache()
    ranges = load_ranges(agents)

    # salt for IP hashing (created once, gitignored)
    salt = ""
    if os.path.exists(SALT_PATH):
        with open(SALT_PATH) as f:
            salt = f.read().strip()
    else:
        salt = hashlib.sha256(os.urandom(32)).hexdigest()
        with open(SALT_PATH, "w") as f:
            f.write(salt)

    now = datetime.now(timezone.utc)
    ignore_nets = load_ignore_ips()
    sessions = sessionize(events)
    sightings = []
    for s in sessions.values():
        last = parse_ts(s["last"])
        sighting = analyze_session(s, agents, ranges, now)
        if apply_ignore and (ip_ignored(sighting["ip"], ignore_nets)
                             or ua_probe(sighting["ua"])):
            continue  # operator/known traffic — never a finding
        # First-batch events (pre-XFF fix) logged Docker's bridge as the
        # client IP: behavior is real wild traffic, network attribution is
        # not. Keep the sighting, mark the network unknown — never invent
        # an address, never discard a true visitor.
        if sighting["ip"] == "172.18.0.1":
            sighting["ip"] = "unknown(docker-bridge)"
            sighting["ip_unknown"] = True
        if now - last > timedelta(days=HASH_AFTER_DAYS):
            sighting["ip"] = hash_ip(sighting["ip"], salt)
        sightings.append(sighting)

    assign_callsigns(sightings, {})
    with open(out_path, "w") as f:
        json.dump({"generated": now.isoformat(timespec="seconds"),
                   "events_analyzed": len(events),
                   "sessions": len(sightings),
                   "sightings": sightings}, f, indent=2)
        f.write("\n")

    # console summary
    by_class = {}
    for s in sightings:
        by_class.setdefault(s["class"], []).append(s)
    print(f"analyzed {len(events)} events -> {len(sightings)} sightings")
    for cls in sorted(by_class, key=lambda c: -len(by_class[c])):
        ex = by_class[cls][0]
        print(f"  {cls:20} {len(by_class[cls]):2}  e.g. "
              f"{ex['callsign']} ({ex['ua'][:40]})")


if __name__ == "__main__":
    main()
