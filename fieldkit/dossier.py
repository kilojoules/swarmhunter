#!/usr/bin/env python3
"""Render dossier/ from fieldkit/sightings.json.

The dossier is the public face: per-agent profiles + a sightings feed,
markdown-rendered. Privacy policy applied here (not in the analyzer):
  - IPs shown only as /24 (IPv4) clusters; older than HASH_AFTER_DAYS the
    analyzer has already salted them — we never print raw hashes' source.
  - evidence trails quote paths and behavior, never headers beyond class.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOSSIER_DIR = os.path.join(HERE, "..", "dossier")

# belt-and-suspenders: no IP-shaped substring may ever reach the public
# dossier, whatever upstream code interpolated into evidence strings
IPV4_RE = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")
IPV6_RE = re.compile(
    r"\b(?:[A-F0-9]{1,4}:){2,7}[A-F0-9]{1,4}\b", re.IGNORECASE)


def redact_ips(text):
    text = IPV4_RE.sub("[ip]", text)
    return IPV6_RE.sub("[ip]", text)

CLASS_ORDER = ["shadow-crawler", "spoof-suspected", "llm-comprehension",
               "cryptid", "scanner-bot", "scripted-bot",
               "declared-unverified", "declared-verified", "human"]

CLASS_BLURB = {    "shadow-crawler": "Undeclared automated visitor that tripped canaries "
                      "invisible to humans (S1)",
    "spoof-suspected": "Claimed a known agent identity; IP failed "
                       "verification against the operator's published "
                       "ranges",
    "llm-comprehension": "Voluntarily answered the comprehension gate — "
                         "self-identification consistent with having "
                         "read and understood the notice (spoofable by a "
                         "reader of our public docs)",
    "cryptid": "Unclassified — escalated for manual review (X)",
    "scanner-bot": "Probed nonexistent paths or POSTed to a site with no "
                   "forms (S2-adjacent)",
    "scripted-bot": "Conventional scripted tooling, no LLM claim",
    "declared-unverified": "Claimed a known agent identity that has no "
                           "verification method",
    "declared-verified": "Verified declared crawler (IP within published "
                         "ranges)",
    "human": "Human visitor, as far as signals show",
}


def _render_empty(out_dir, why):
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        if name.endswith(".md"):
            os.remove(os.path.join(out_dir, name))
    with open(os.path.join(out_dir, "index.md"), "w") as f:
        f.write(f"""# Swarmhunter Dossier

**No true sightings yet.**

{why.capitalize()}.

When the Trap Garden is deployed on the public internet and real
visitors arrive, their evidenced behavioral records will appear here —
one profile per tracked agent, each with its evidence trail. Until then
this page honestly says: nothing has been caught.

*Test traffic (integration tests, local runs) never appears in this
dossier; it lives in tests/ and is never classified as findings.*
""")
    print(f"dossier: empty state ({why})")


def _check_wild(data, out_dir):
    """Drop test/local traffic (never findings, by policy — see memory:
    aunt-test-for-findings). Returns True if wild sightings remain."""
    test_like = [s for s in data["sightings"]
                 if s.get("ip") in ("127.0.0.1", "::1", "0.0.0.0")
                 or s.get("ip", "").startswith(("127.", "192.168.", "10."))]
    if test_like and len(test_like) == len(data["sightings"]):
        _render_empty(out_dir, "only test/local traffic found — test "
                      "data is never rendered as findings")
        return False
    data["sightings"] = [s for s in data["sightings"]
                         if s not in test_like]
    return True


def ip_cluster(ip):
    if ip.startswith("h:"):
        return ip  # already hashed by analyzer
    if ":" in ip:
        return ip  # ipv6: leave as-is (analyzer hashed or rare)
    return ip.rsplit(".", 1)[0] + ".0/24"


def render(sightings_path, out_dir):
    # Empty/wild-empty state is the honest default: until the garden has
    # real visitors, the dossier says so plainly. Test data must never
    # render as findings (see memory: aunt-test-for-findings).
    if not os.path.exists(sightings_path):
        _render_empty(out_dir, "no sightings file yet — the analyzer has "
                      "not been run on wild events")
        return
    with open(sightings_path) as f:
        data = json.load(f)
    if not data["sightings"]:
        _render_empty(out_dir, "the garden has had no visitors yet")
        return
    if not _check_wild(data, out_dir):
        return  # test-only traffic: empty state already rendered
    sightings = data["sightings"]
    if not sightings:
        _render_empty(out_dir, "only test/local traffic in this batch")
        return
    os.makedirs(out_dir, exist_ok=True)

    # Remove stale profiles from previous renders so the dossier reflects
    # exactly the current sightings (callsigns change between runs).
    keep = {"index.md"} | {f"{s['callsign'].lower()}.md"
                           for s in sightings}
    for name in os.listdir(out_dir):
        if name.endswith(".md") and name not in keep:
            os.remove(os.path.join(out_dir, name))

    # --- index.md -------------------------------------------------------
    by_class = {}
    for s in sightings:
        by_class.setdefault(s["class"], []).append(s)

    lines = [f"# Swarmhunter Dossier", "",
             f"Generated {data['generated']} from "
             f"{data['events_analyzed']} events "
             f"({data['sessions']} sessions).", "",
             "Agents tracked, by class:", ""]
    for cls in CLASS_ORDER:
        group = by_class.get(cls, [])
        if not group:
            continue
        lines.append(f"## {cls} ({len(group)})")
        lines.append(f"*{CLASS_BLURB[cls]}*")
        lines.append("")
        lines.append("| callsign | claimed | reqs | canaries | "
                     "first seen | confidence |")
        lines.append("|---|---|---|---|---|---|")
        for s in sorted(group, key=lambda x: x["first_seen"]):
            claimed = s.get("claimed_agent") or "—"
            canaries = ", ".join(s["trap_hits"]) or "—"
            lines.append(
                f"| {s['callsign']} | {claimed} | {s['requests']} | "
                f"{canaries} | {s['first_seen'][:16]} | "
                f"{s['confidence']} |")
        lines.append("")

    lines += ["---", "",
              "*IPs appear as /24 clusters; raw IPs are salted and hashed "
              "after 7 days. Sightings are behavioral records of visits "
              "to infrastructure we own; they are not accusations. See "
              "docs/SCOPE.md for guardrails.*"]

    with open(os.path.join(out_dir, "index.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    # --- per-agent files --------------------------------------------------
    for s in sightings:
        slug = s["callsign"].lower()
        body = [f"# {s['callsign']}", "",
                f"- **class:** {s['class']} "
                f"(confidence {s['confidence']})",
                f"- *{CLASS_BLURB.get(s['class'], '')}*", "",
                f"- **user-agent:** `{redact_ips(s['ua'])}`",
                f"- **identity claim:** "
                f"{s.get('claimed_agent') or 'none'}",
                f"- **verification:** {s['verification']}",
                f"- **network:** {ip_cluster(s['ip'])} (cluster)",
                f"- **first/last seen:** {s['first_seen']} → "
                f"{s['last_seen']}",
                f"- **requests:** {s['requests']} "
                f"({s['rate_per_s']}/s peak)", "",
                "## Evidence", ""]
        for e in s["evidence"]:
            body.append(f"- {redact_ips(e)}")
        if s["trap_hits"]:
            body += ["", "## Canary trips", ""]
            for t in s["trap_hits"]:
                body.append(f"- `{t}`")
        if s["purpose_header"]:
            body += ["", f"Volunteered purpose: "
                         f"`{s['purpose_header']}`"]
        body += ["", "---", "*Behavioral record of a visit to Trap Garden "
                          "infrastructure. Not an accusation; see "
                          "docs/SCOPE.md.*"]
        with open(os.path.join(out_dir, f"{slug}.md"), "w") as f:
            f.write("\n".join(body) + "\n")

    print(f"dossier: {len(sightings)} agent profiles + index -> {out_dir}")


if __name__ == "__main__":
    sp = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, "sightings.json")
    od = sys.argv[2] if len(sys.argv) > 2 else DOSSIER_DIR
    render(sp, od)
