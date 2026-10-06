#!/usr/bin/env python3
"""Merge vendored seed registries into fieldkit/data/known_agents.json —
the ground-truth file the verifier and classifier load at runtime.

Sources (all in fieldkit/seeds/, see seeds/ATTRIBUTION.md):
  airobots/robots.json          — community registry, 181 agents (MIT)
  agentswelcome/crawlers.json   — 41 crawlers, verification-graded
  openai/*.json                 — per-bot published IP ranges
  anthropic/bots.json           — shared IP ranges for all Anthropic bots

Output record shape:
  {
    "primary_token": "GPTBot",
    "aliases": [...],            # other UA substrings that match
    "operator": "OpenAI",
    "sources": ["airobots", "agentswelcome"],
    "purpose": "training",
    "respects_robots": "Yes",    # as recorded; free-form from airobots
    "verification": {
      "methods": ["published-IP-range"],
      "range_files": {"GPTBot": "seeds/openai/gptbot.json"},
      "verifiability": "verifiable"
    }
  }

Known limitations (documented, not hidden): community registries contain
errors (recon); Anthropic's shared range file cannot bind token to IP.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDS = os.path.join(HERE, "seeds")
OUT = os.path.join(HERE, "data", "known_agents.json")


def plain(text):
    """Strip markdown links: '[OpenAI](https://x)' -> 'OpenAI'."""
    if not isinstance(text, str):
        return text
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text).strip()


def aw_key(r):
    """Stable key for an Agents Welcome record: robots token if real,
    else the crawler's name. Placeholders like '(none — …)' are not keys."""
    token = r.get("robots_token") or ""
    if token and not token.startswith("("):
        return token
    return r.get("name") or ""

# Which local range file verifies which token (per-operator publishing).
RANGE_FILES = {
    "GPTBot": "openai/gptbot.json",
    "OAI-SearchBot": "openai/searchbot.json",
    "ChatGPT-User": "openai/chatgpt-user.json",
    "OAI-AdsBot": "openai/adsbot.json",
    # Anthropic publishes ONE shared list for ClaudeBot/Claude-User/
    # Claude-SearchBot: IP proves "Anthropic", not the specific token.
    "ClaudeBot": "anthropic/bots.json",
    "Claude-User": "anthropic/bots.json",
    "Claude-SearchBot": "anthropic/bots.json",
    # Google publishes per-service JSON lists:
    "Googlebot": "google/googlebot.json",
    "Google-CloudVertexBot": "google/googlebot.json",
    "Google-Agent": "google/googlebot.json",
    "GoogleOther": "google/googlebot.json",
    "Google-Extended": "google/googlebot.json",
    "special GOOGLE-ALL": "google/googlebot.json",  # marker: apply to every operator=Google entry
}

# Tokens that must NEVER substring-match each other's registry entries
# (the 'Google-Firebase = OpenAI' class of collision).
NEVER_CONflate = {
    "Google-Firebase", "Google-Gemini-CLI", "Google-NotebookLM",
    "GoogleAgent-Mariner", "GoogleAgent-URLContext",
}


def token_matches_iauthorized(key, r, name):
    """Strict match for merging Agents Welcome into an airobots entry:
    exact (case-insensitive) token/name equality only — never substring."""
    if key.lower() == name.lower():
        return True
    ua_sub = (r.get("ua_substring") or "").strip()
    return bool(ua_sub) and ua_sub.lower() == name.lower()


def load(path):
    with open(os.path.join(SEEDS, path)) as f:
        return json.load(f)


def main():
    airobots = load("airobots/robots.json")
    aw = load("agentswelcome/crawlers.json")
    aw_records = {}
    for r in aw.get("records", []):
        k = aw_key(r)
        if k:
            aw_records[k] = r

    merged = {}

    for name, rec in airobots.items():
        out = {
            "primary_token": name,
            "aliases": [],
            "operator": plain(rec.get("operator", "")),
            "sources": ["airobots"],
            "purpose": rec.get("function", ""),
            "respects_robots": plain(rec.get("respect", "")),
            "frequency": rec.get("frequency", ""),
            "description": rec.get("description", ""),
            "verification": {"methods": [], "range_files": {},
                             "verifiability": "unverifiable"},
        }
        # enrich with Agents Welcome where tokens EXACTLY line up
        for key, r in aw_records.items():
            if not key:
                continue
            if token_matches_iauthorized(key, r, name):
                out["sources"].append("agentswelcome")
                out["operator"] = plain(r.get("operator")) or out["operator"]
                out["purpose"] = r.get("purpose") or out["purpose"]
                out["respects_robots"] = (
                    r.get("respects_robots")
                    if r.get("respects_robots") is not None
                    else out["respects_robots"])
                out["verification"]["methods"] = r.get(
                    "verification_methods", [])
                out["verification"]["verifiability"] = r.get(
                    "verifiability", "unverifiable")
                if r.get("published_ip_range_url"):
                    out["verification"]["range_url"] = r[
                        "published_ip_range_url"]
                break
        # NB: matching is by name/token only — too loose to auto-merge
        # more exotic pairs; deliberate (community DBs contain errors, so
        # we keep per-field provenance instead of trusting one source).
        if name in RANGE_FILES:
            out["verification"]["range_files"][name] = (
                "seeds/" + RANGE_FILES[name])
            if "published-IP-range" not in out["verification"]["methods"]:
                out["verification"]["methods"].append("published-IP-range")
            out["verification"]["verifiability"] = "verifiable"
        merged[name] = out

    # Google marker: apply the shared googlebot.json list to every entry
    # whose operator actually is Google (never to OpenAI's Google-* tokens).
    for name, out in merged.items():
        if out.get("operator") == "Google" and name not in NEVER_CONflate:
            out["verification"]["range_files"][name] = (
                "seeds/google/googlebot.json")
            if "published-IP-range" not in out["verification"]["methods"]:
                out["verification"]["methods"].append("published-IP-range")

    # Agents Welcome records with no airobots counterpart (e.g. agentic
    # browsers) still matter — keep them, keyed by their real name.
    for key, r in aw_records.items():
        if not key or key in merged:
            continue
        merged[key] = {
            "primary_token": key,
            "aliases": [r["ua_substring"]] if r.get("ua_substring") else [],
            "operator": plain(r.get("operator", "")),
            "sources": ["agentswelcome"],
            "purpose": r.get("purpose", ""),
            "respects_robots": r.get("respects_robots"),
            "frequency": "",
            "description": plain(r.get("notes", "")) or "",
            "verification": {
                "methods": r.get("verification_methods", []),
                "range_files": {},
                "verifiability": r.get("verifiability", "unverifiable"),
                **({"range_url": r["published_ip_range_url"]}
                   if r.get("published_ip_range_url") else {}),
            },
        }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"version": 1, "agents": merged}, f, indent=2,
                  sort_keys=True)
        f.write("\n")
    verifiable = sum(1 for a in merged.values()
                     if a["verification"]["range_files"])
    print(f"wrote {OUT}: {len(merged)} agents "
          f"({verifiable} with local range files)")


if __name__ == "__main__":
    main()
