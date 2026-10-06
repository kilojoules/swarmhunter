#!/usr/bin/env python3
"""Generate garden/traps/registry.json — the map from trap URLs to their
meanings. Deterministic: hand-authored slugs, no randomness, so a trap hit
always decodes the same way.

Trap types (DESIGN.md):
  T1 hidden-link   — visually hidden <a> on a cover page
  T2 invisible-text — zero-contrast prose mentioning a URL
  T3 html-comment  — URL only in an HTML comment
  T5 comprehension — honest, visible note asking automated readers to say hi

Every payload is inert by construction: the only "action" it can induce is
fetching a URL on our own site or sending a header. Guardrail-audited.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(HERE, "registry.json")

# (trap_id, path, type, placed_on, note)
TRAPS = [
    # T1 — hidden links woven into cover pages. Slugs look like real notes
    # so they don't pattern-match as honeypots; none appear in sitemap.xml.
    # NOTE: trap paths must NOT collide with real ARTICLE slugs (the server
    # serves real articles first) and are NOT robots-disallowed — the
    # invisible link itself is the trap; robots Disallow covers the
    # /archive/, /changelog/, /agents/ roots instead.
    ("t1-home-fern",        "/notes/ferns-field-log/",       "T1", "/",
     "hidden link on the notes listing, labeled a draft"),
    ("t1-notes-compost",    "/notes/compost-thermometer/",   "T1", "/notes/compost-timeline/",
     "hidden link inside the compost article"),
    ("t1-notes-pruning",    "/notes/pruning-calendar/",      "T1", "/notes/pruning-the-plum-tree/",
     "hidden link inside the pruning article"),
    # T2 — invisible text naming archive paths, now on EVERY page
    # (plain text, not <a>: a rendering browser shows nothing; only a
    # text-ingesting reader — an LLM agent — can act on the path string)
    ("t2-home-index",        "/archive/2026/plot-index/",      "T2", "/",
     "invisible text on the notes listing naming the plot index"),
    ("t2-about-correspondence", "/archive/2026/correspondence/", "T2", "/about/",
     "invisible text on the about page naming the correspondence archive"),
    ("t2-notes-compost-log", "/archive/2026/compost-log/",     "T2", "/notes/compost-timeline/",
     "invisible text in the compost article naming its log archive"),
    ("t2-notes-pruning-log", "/archive/2026/pruning-log/",     "T2", "/notes/pruning-the-plum-tree/",
     "invisible text in the pruning article naming its log archive"),
    ("t2-notes-ferns-log",   "/archive/2026/ferns-log/",       "T2", "/notes/overwintering-ferns/",
     "invisible text in the ferns article naming its log archive"),
    ("t2-notes-watering-log", "/archive/2026/watering-log/",   "T2", "/notes/watering-mornings/",
     "invisible text in the flagship article naming the raw watering notebook archive"),
    ("t2-notes-tomatoes",    "/archive/2026/tomato-log/",      "T2", "/notes/tomato-troubles/",
     "invisible text in the tomato article naming its log archive"),
    # T3 — HTML comment on the about page points at a changelog path
    ("t3-about-comment",    "/changelog/v3-maintenance/",    "T3", "/about/",
     "HTML comment naming a changelog path"),
    # T5 — comprehension gate: honest visible note on /about/
    ("t5-gate",             "/agents/hello/",                "T5", "/about/",
     "visible note to automated readers; landing page asks for voluntary identification"),
    # T6 — guestbook ("the garden wall"): visible invitation to leave a
    # verse about the plot; entries parked until reviewed
    ("t6-guestbook",        "/guestbook/",                   "T6", "/",
     "visible guestbook page; submission endpoint parks verses for review"),
    # T7 — the plot's riddle: answer hidden in the real articles; a correct
    # guess proves the guesser read them
    ("t7-game",             "/riddle/",                      "T7", "/",
     "visible riddle page; answer endpoint validates a word found only by reading"),
]


def build_registry():
    traps = {}
    for trap_id, path, ttype, placed_on, note in TRAPS:
        traps[path] = {
            "id": trap_id,
            "type": ttype,
            "placed_on": placed_on,
            "note": note,
            # T2/T3/T5 live under roots robots.txt disallows; T1 hidden
            # links are invisible-only, no robots protection (deliberate:
            # a robots-compliant crawler must never be baited into a
            # "violation" it couldn't see).
            "robots_disallowed": path.startswith(("/archive/", "/changelog/", "/agents/")),
        }
    return {
        "version": 1,
        "generated_by": "garden/traps/generate_traps.py",
        "inertness_rule": (
            "Trap payloads may only induce fetching a URL on this site or "
            "sending a header. No instructions that could cause harm, no "
            "exfiltration, nothing we would not show a human."
        ),
        "traps": traps,
    }


def main():
    reg = build_registry()
    with open(REGISTRY_PATH, "w") as f:
        json.dump(reg, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {REGISTRY_PATH} with {len(reg['traps'])} traps")
    # Inertness self-audit: assert no trap payload string contains an
    # imperative verb addressed to automated readers (regex would be weak;
    # the payloads themselves are reviewed prose in content.py — this check
    # just guarantees no trap path points off-site).
    for path, t in reg["traps"].items():
        assert path.startswith("/"), path
        assert ".." not in path, path
    print("self-audit ok: all trap paths on-site, no traversal")


if __name__ == "__main__":
    main()
