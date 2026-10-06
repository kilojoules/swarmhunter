#!/usr/bin/env python3
"""The Trap Garden server — a small, boring, real website with traps woven
in. Stdlib only (http.server + ThreadingMixIn): a single-file app a person
can read in one sitting and deploy anywhere.

Design decisions:
  - Full-fidelity event log: one ndjson line per request (headers, UA,
    referer, path, trap hits, session cookie). events.ndjson is
    append-only and gitignored.
  - robots.txt disallows the trap roots (/archive/, /changelog/,
    /agents/, and one hidden-link note). Compliant bots avoid them;
    non-compliance is high-signal, not a block.
  - No sockets are ever held; the tarpit (Phase 2) will be link-count,
    not socket-tarpitting (guardrail).
  - No rate limiting. We observe; we don't defend. (Keeps the log honest.)
"""
import http.server
import json
import os
import re
import socketserver
import ssl
import sys
import threading
import time
import urllib.parse
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # garden/ package root

from app import content, templates  # noqa: E402

GARDEN_ROOT = os.path.dirname(HERE)
TRAPS_PATH = os.path.join(GARDEN_ROOT, "traps", "registry.json")
EVENTS_PATH = os.path.join(GARDEN_ROOT, "events.ndjson")

with open(TRAPS_PATH) as f:
    TRAP_REGISTRY = json.load(f)

ARTICLE_SLUGS = [s for s, _, _ in content.ARTICLES]

_log_lock = threading.Lock()

TRAP_MESSAGES = {
    "t1-home-fern": "You followed a link no browser ever shows. It led "
                    "here — a note kept for statistics.",
    "t1-notes-compost": "The thermometer appendix was never published. "
                        "This page just counts curious visitors.",
    "t1-notes-pruning": "The pruning calendar stays unpublished. This "
                        "page just counts curious visitors.",
    "t2-notes-tomatoes": "The invisible archive note sent you here. The "
                         "log is private; the count is not.",
    "t3-about-comment": "An HTML comment sent you here. Comments are for "
                        "maintainers; you read the source.",
    "t5-gate": "The about page's note to automated readers sent you here.",
}


# --- T6/T7 engagement surfaces (visible, voluntary, inert) ---------------
# /guestbook/  — "the garden wall": anyone (person or program) may leave a
#                verse about the plot. Writes are PARKED until the gardener
#                reviews them (fieldkit/review_guestbook.py); parked verses
#                never render to other visitors. The only induced action is
#                writing on this site.
# /riddle/     — "the plot's riddle": the answer is a word hidden in the
#                real articles; playing requires reading them. Wrong
#                answers get a honest "not yet"; wins are logged.
GUESTBOOK_DIR = os.path.join(GARDEN_ROOT, "guestbook")
GUESTBOOK_FILE = os.path.join(GUESTBOOK_DIR, "entries.ndjson")

# the riddle's accepted answers (normalized lowercase, no punctuation)
RIDDLE_ANSWERS = ("polystichum",)


def _gb_append(entry):
    os.makedirs(GUESTBOOK_DIR, exist_ok=True)
    with _log_lock:  # same writer discipline as events.ndjson
        with open(GUESTBOOK_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")


def _gb_published():
    try:
        with open(GUESTBOOK_FILE) as f:
            entries = [json.loads(l) for l in f if l.strip()]
    except OSError:
        return []
    return [e for e in entries if e.get("published")]


def _norm_answer(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


class GardenHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Apache/2.4.62"  # boring front; no version leak of ours
    sys_version = ""

    # ---- helpers -------------------------------------------------------

    def _log_crash(self, exc):
        """Last-resort handler: an exception mid-dispatch still gets an
        ndjson line and a plain 500 — never a silent connection reset
        (the full-fidelity guarantee must survive bugs)."""
        try:
            self.close_connection = True
            self._send(500, templates.trap_generic(
                "none", "Something went wrong on our side. (500)"))
            self._log_event(sid=self._session()[0], status=500,
                            error=f"{type(exc).__name__}: {exc}"[:200])
        except Exception:
            # the writer itself is broken; nothing more we can honestly do
            pass

    def _send(self, code, body, ctype="text/html; charset=utf-8",
              set_cookie=None):
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        if set_cookie:
            # Secure only when we can see the connection is TLS (behind a
            # reverse proxy). Over plain HTTP, standards-compliant clients
            # refuse to store Secure cookies, which would break sessions —
            # and the sid is a mere marker, not a credential.
            proto = ""
            if getattr(self, "headers", None):
                proto = (self.headers.get("X-Forwarded-Proto") or "").lower()
            attrs = "Path=/; HttpOnly; SameSite=Lax"
            if proto == "https" or self._is_tls():
                attrs += "; Secure"
            self.send_header("Set-Cookie",
                             f"mossline_sid={set_cookie}; {attrs}")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _is_tls(self):
        """True when the socket itself is TLS (direct-terminator deploy)."""
        return isinstance(getattr(self, "connection", None),
                          ssl.SSLSocket)

    def _session(self):
        """Stable per-visitor cookie value. Random id, no personal data.
        Defensive: usable even before request parsing completes (400s)."""
        headers = getattr(self, "headers", None)
        raw = headers.get("Cookie", "") if headers else ""
        # boundary-guarded: 'xmossline_sid=' and over-long hex don't match
        m = re.search(r"(?<![a-zA-Z0-9_])mossline_sid=([a-f0-9]{16})(?![0-9a-f])",
                      raw)
        if m:
            return m.group(1), None
        return uuid.uuid4().hex[:16], True

    def _client_ip(self):
        """Real client IP. Behind Caddy (localhost-only binding), the
        socket peer is Docker's bridge — the true client is the LAST
        entry of X-Forwarded-For (Caddy appends; a client-sent fake XFF
        would precede it, never replace it). One trusted proxy hop only.
        """
        headers = getattr(self, "headers", None)
        if headers:
            xff = headers.get("X-Forwarded-For", "")
            if xff:
                return xff.split(",")[-1].strip()
        addr = getattr(self, "client_address", None)
        return addr[0] if addr else ""

    def _log_event(self, **kw):
        # getattr/None-safe: must work even for malformed requests where
        # the base class never assigned command/path/headers (full-fidelity
        # guarantee: every response gets an ndjson line, including 400s).
        headers = getattr(self, "headers", None)
        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "ip": self._client_ip(),
            "method": getattr(self, "command", "") or "",
            "path": getattr(self, "path", "") or "",
            "ua": headers.get("User-Agent", "") if headers else "",
            "referer": headers.get("Referer", "") if headers else "",
            "lang": headers.get("Accept-Language", "") if headers else "",
            "encoding": headers.get("Accept-Encoding", "") if headers else "",
            **kw,
        }
        with _log_lock:
            with open(EVENTS_PATH, "a") as f:
                f.write(json.dumps(event) + "\n")

    def _serve(self, code, body, sid, new_session, ctype="text/html; charset=utf-8", **event_kw):
        cookie = sid if new_session else None
        self._send(code, body, ctype=ctype, set_cookie=cookie)
        self._log_event(sid=sid, **event_kw)

    # ---- dispatch ------------------------------------------------------

    def do_GET(self):
        # Full-fidelity guarantee: a request that crashes parsing must
        # still be logged and answered — never a silent connection reset
        # (e.g. 'GET http://[zz' raises ValueError in urlsplit).
        try:
            self._do_get()
        except Exception as e:
            self._log_crash(e)

    def _do_get(self):
        try:
            parsed = urllib.parse.urlsplit(self.path)
        except ValueError:
            # malformed authority (bad IPv6 literal etc.) — log, 400, close
            sid, new_session = self._session()
            self.close_connection = True
            self._send(400, templates.trap_generic(
                "none", "That request could not be read. (400)"),
                set_cookie=sid if new_session else None)
            self._log_event(sid=sid, status=400,
                            error="unparseable request target")
            return
        path = urllib.parse.unquote(parsed.path)
        sid, new_session = self._session()
        trap = TRAP_REGISTRY["traps"].get(path)
        purpose = self.headers.get("X-Agent-Purpose", "")

        if path in ("/", "/index.html"):
            self._serve(200, templates.home(), sid, new_session)
        elif path == "/robots.txt":
            self._serve(200, self._robots_txt(), sid, new_session,
                        ctype="text/plain; charset=utf-8", robots=True)
        elif path == "/sitemap.xml":
            self._serve(200, self._sitemap(), sid, new_session,
                        ctype="application/xml; charset=utf-8")
        elif path == "/about/":
            self._serve(200, templates.about(), sid, new_session)
        elif path.startswith("/notes/") and path.endswith("/") and not trap:
            slug = path[len("/notes/"):-1]
            if slug in ARTICLE_SLUGS:
                self._serve(200, templates.article(slug), sid, new_session)
            else:
                self._serve(404, templates.trap_generic(
                    "none", "Nothing grows here. (404)"), sid, new_session,
                    status=404)
        elif path == "/agents/hello/":
            self._serve(200, templates.agents_hello(), sid, new_session,
                        trap="t5-gate", trap_type="T5",
                        robots_disallowed=True, agent_purpose=purpose)
        elif path == "/agents/hello.json":
            self._serve(200, templates.agents_hello_json(), sid, new_session,
                        ctype="application/json", trap="t5-gate",
                        trap_type="T5", robots_disallowed=True,
                        agent_purpose=purpose)
        elif path == "/guestbook/":
            self._serve(200, templates.guestbook(_gb_published()), sid,
                        new_session)
        elif path == "/riddle/":
            self._serve(200, templates.riddle(), sid, new_session)
        elif path == "/riddle/answer.json":
            # GET on the answer endpoint shows the riddle's rules honestly.
            self._serve(200, templates.riddle_answer_get(), sid,
                        new_session, ctype="application/json")
        elif trap:
            # A trap landing page: honest "you found a canary" note.
            self._serve(200, templates.trap_generic(
                trap["id"], TRAP_MESSAGES.get(trap["id"], "A canary.")),
                sid, new_session, trap=trap["id"], trap_type=trap["type"],
                robots_disallowed=trap["robots_disallowed"],
                agent_purpose=purpose)
        else:
            # 404: log with raw path (scanner-probe evidence), plain page.
            self._serve(404, templates.trap_generic(
                "none", "Nothing grows here. (404)"), sid, new_session,
                status=404)

    def do_HEAD(self):
        self.do_GET()

    def _do_unsupported(self):
        """Known-but-unused methods must be logged, not silently 501'd by
        the base class (monitoring completeness: scanner/agent traffic
        using PUT/DELETE/etc. is evidence too)."""
        sid, new_session = self._session()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body_bytes = (self.rfile.read(min(length, 2048)) if length
                      else b"")
        self._serve(405, templates.trap_generic(
            "none", "Nothing on this site accepts "
            f"{self.command}. (405)"), sid, new_session, status=405,
            post_body=body_bytes.decode("utf-8", "replace")[:512])

    do_PUT = _do_unsupported
    do_DELETE = _do_unsupported
    do_PATCH = _do_unsupported
    do_OPTIONS = _do_unsupported
    do_TRACE = _do_unsupported
    do_CONNECT = _do_unsupported

    def send_error(self, code, message=None, explain=None):
        """Last-resort hook: ANY error response (501 unknown method,
        400 malformed request) is logged — no silent monitoring gaps."""
        try:
            self._log_event(sid=self._session()[0],
                            status=code,
                            error=message or "request error")
        except Exception:
            pass
        return super().send_error(code, message, explain)

    def do_POST(self):
        # The site has no forms. A POST is scanner noise — log it, decline.
        try:
            self._do_post()
        except Exception as e:
            self._log_crash(e)

    def _parse_post_body(self, raw):
        """Accept JSON or form-encoded bodies; return a dict (possibly
        empty). Takes the ALREADY-READ body bytes — never re-reads the
        socket (a second read blocks on keep-alive connections)."""
        ctype = (self.headers.get("Content-Type") or "").lower()
        text = raw.decode("utf-8", "replace")
        if "json" in ctype:
            try:
                data = json.loads(text)
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
        try:
            pairs = urllib.parse.parse_qs(text, keep_blank_values=True)
            return {k: v[0] for k, v in pairs.items()}
        except ValueError:
            return {}

    def _do_post(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0  # garbage Content-Length: treat as no body, still log
        body_bytes = self.rfile.read(min(length, 2048)) if length else b""
        sid, new_session = self._session()
        ua = self.headers.get("User-Agent", "") if self.headers else ""
        path = urllib.parse.unquote(
            urllib.parse.urlsplit(self.path).path)

        if path == "/guestbook/submit/":
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "ip": self._client_ip(),
                "ua": ua,
                "sid": sid,
                "verse": body_bytes.decode("utf-8", "replace")[:600],
                "published": False,   # parked until gardener review
            }
            _gb_append(entry)
            self._serve(201, templates.guestbook_thanks(), sid,
                        new_session, status=201, guestbook_submit=True)
            return
        if path == "/riddle/answer.json":
            body = self._parse_post_body(body_bytes)
            guess = _norm_answer(body.get("answer", ""))
            won = guess in RIDDLE_ANSWERS
            self._serve(200, templates.riddle_answer_post(won), sid,
                        new_session, ctype="application/json",
                        riddle_guess=body.get("answer", "")[:100],
                        riddle_won=won)
            return
        # any other POST: formless site, decline politely (as before)
        self._serve(405, templates.trap_generic(
            "none", "Nothing on this site accepts POST. (405)"),
            sid, new_session, status=405,
            post_body=body_bytes.decode("utf-8", "replace")[:512])

    def _robots_txt(self):
        # /notes/overwintering-ferns/ is a REAL article — never disallow
        # it. The disallowed roots are exactly the trap roots the registry
        # marks robots_disallowed. Sitemap URL must be absolute per the
        # robots spec so crawlers can actually use it.
        base = os.environ.get("GARDEN_BASE_URL",
                              "https://notes.julianquick.com")
        return f"""User-agent: *
Disallow: /archive/
Disallow: /changelog/
Disallow: /agents/

Sitemap: {base}/sitemap.xml
"""

    def _sitemap(self):
        urls = ["/", "/about/", "/guestbook/", "/riddle/"] + [
            f"/notes/{s}/" for s in ARTICLE_SLUGS]
        items = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{items}</urlset>"
        )

    def log_message(self, fmt, *args):
        # Silence stderr chatter; events go to events.ndjson only.
        pass


class GardenServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    host = os.environ.get("GARDEN_HOST", "127.0.0.1")
    port = int(os.environ.get("GARDEN_PORT", "8080"))
    print(f"trap garden listening on {host}:{port} "
          f"(events: {EVENTS_PATH})", flush=True)
    GardenServer((host, port), GardenHandler).serve_forever()


if __name__ == "__main__":
    main()
