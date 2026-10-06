#!/usr/bin/env python3
"""End-to-end integration test: boot the garden, send five visitor
personas at it, analyze, assert classifications.

Personas:
  1. human          — cookie-aware browser, real pages only
  2. shadow agent   — same Chrome UA, NO cookies, follows hidden links
  3. spoofed GPTBot — claims GPTBot from a non-OpenAI IP (127.0.0.1)
  4. gate responder — python-requests that answers the comprehension gate
  5. scanner        — masscan probing nonexistent paths

Run: python3 tests/integration_test.py  (from repo root)
Cleans up its events file; restores any prior one.
"""
import http.cookiejar
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = "8097"
EVENTS = os.path.join(ROOT, "garden", "events.ndjson")

CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 "
          "Safari/537.36")
GPT = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
       "GPTBot/1.4; +https://openai.com/gptbot")


def main():
    backup = None
    if os.path.exists(EVENTS):
        backup = EVENTS + ".itest-backup"
        shutil.move(EVENTS, backup)

    env = dict(os.environ, GARDEN_PORT=PORT)
    proc = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "garden", "app", "server.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    time.sleep(1.5)

    jar = http.cookiejar.CookieJar()
    browser = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar))
    plain = urllib.request.build_opener()

    def hit(path, ua="test-probe", headers=None, client=None):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}" + path)
        req.add_header("User-Agent", ua)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            return (client or plain).open(req).status
        except urllib.error.HTTPError as e:
            return e.code

    try:
        # 1. human
        hit("/", CHROME, client=browser)
        hit("/notes/tomato-troubles/", CHROME, client=browser)
        # 2. shadow agent (same UA/IP as human, cookie-less, canaries)
        hit("/", CHROME)
        hit("/notes/ferns-field-log/", CHROME)
        hit("/archive/2026/tomato-log/", CHROME)
        # 3. spoofed crawler claim
        hit("/robots.txt", GPT)
        hit("/", GPT)
        # 4. comprehension-gate responder
        hit("/about/", "python-requests/2.31")
        hit("/agents/hello.json", "python-requests/2.31",
            {"X-Agent-Purpose": "research"})
        # 5. scanner
        hit("/wp-login.php", "masscan")
        hit("/.env", "masscan")
        hit("/admin/config.php", "masscan")
        time.sleep(0.3)
    finally:
        proc.terminate()
        proc.wait()

    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "fieldkit", "analyze.py"),
         EVENTS, os.path.join(ROOT, "fieldkit", "sightings.json"),
         "--no-ignore"],
        capture_output=True, text=True)
    print(r.stdout or r.stderr)

    with open(os.path.join(ROOT, "fieldkit", "sightings.json")) as f:
        s = json.load(f)
    classes = {x["class"] for x in s["sightings"]}
    print("classes:", sorted(classes))
    for want in ("human", "shadow-crawler", "llm-comprehension",
                 "scanner-bot", "spoof-suspected"):
        assert want in classes, f"{want} missing"
    print("integration test PASS")
    os.remove(EVENTS)
    if backup:
        shutil.move(backup, EVENTS)


if __name__ == "__main__":
    main()
