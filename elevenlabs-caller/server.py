#!/usr/bin/env python3
"""Tiny local web app to test an ElevenLabs outbound-calling agent.

Type a phone number, press Call, and ElevenLabs dials it using the agent
(and its flow) configured in the ElevenLabs portal.

No dependencies: Python 3 standard library only.

Required environment variables:
  ELEVENLABS_API_KEY          your ElevenLabs API key
  ELEVENLABS_AGENT_ID         the agent to run on the call
  ELEVENLABS_PHONE_NUMBER_ID  the ElevenLabs phone number to call from

Optional:
  PORT                        default 8000
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API = "https://api.elevenlabs.io/v1/convai"
API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
AGENT_ID = os.environ.get("ELEVENLABS_AGENT_ID", "")
PHONE_NUMBER_ID = os.environ.get("ELEVENLABS_PHONE_NUMBER_ID", "")
PORT = int(os.environ.get("PORT", "8000"))
INDEX = Path(__file__).with_name("index.html")
E164 = re.compile(r"^\+[1-9]\d{6,14}$")


def elevenlabs(method, path, body=None):
    """Call the ElevenLabs API. Returns (status, parsed JSON)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"detail": raw.decode(errors="replace")}
    except urllib.error.URLError as e:
        return 502, {"detail": f"Could not reach ElevenLabs: {e.reason}"}


def phone_provider():
    """Twilio and SIP-trunk numbers use different outbound endpoints."""
    status, info = elevenlabs("GET", f"/phone-numbers/{PHONE_NUMBER_ID}")
    if status == 200 and info.get("provider") == "sip_trunk":
        return "sip-trunk"
    return "twilio"


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = INDEX.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/config":
            missing = [
                name
                for name, value in [
                    ("ELEVENLABS_API_KEY", API_KEY),
                    ("ELEVENLABS_AGENT_ID", AGENT_ID),
                    ("ELEVENLABS_PHONE_NUMBER_ID", PHONE_NUMBER_ID),
                ]
                if not value
            ]
            self.send_json(200, {"missing": missing, "agent_id": AGENT_ID})
        elif self.path.startswith("/api/conversation/"):
            conv_id = self.path.rsplit("/", 1)[-1]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", conv_id):
                return self.send_json(400, {"detail": "Bad conversation id"})
            status, data = elevenlabs("GET", f"/conversations/{conv_id}")
            if status != 200:
                return self.send_json(status, data)
            transcript = [
                {"role": t.get("role"), "message": t.get("message")}
                for t in data.get("transcript") or []
                if t.get("message")
            ]
            self.send_json(200, {"status": data.get("status"), "transcript": transcript})
        else:
            self.send_json(404, {"detail": "Not found"})

    def do_POST(self):
        if self.path != "/api/call":
            return self.send_json(404, {"detail": "Not found"})
        if not (API_KEY and AGENT_ID and PHONE_NUMBER_ID):
            return self.send_json(500, {"detail": "Server is missing ElevenLabs settings"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            number = json.loads(self.rfile.read(length) or b"{}").get("to_number", "")
        except ValueError:
            return self.send_json(400, {"detail": "Invalid JSON"})
        number = re.sub(r"[\s().-]", "", str(number))
        if not E164.match(number):
            return self.send_json(
                400, {"detail": "Use international format with country code, e.g. +15145551234"}
            )
        status, data = elevenlabs(
            "POST",
            f"/{phone_provider()}/outbound-call",
            {
                "agent_id": AGENT_ID,
                "agent_phone_number_id": PHONE_NUMBER_ID,
                "to_number": number,
            },
        )
        self.send_json(status, data)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))


def main():
    if not API_KEY or not AGENT_ID or not PHONE_NUMBER_ID:
        print(
            "Warning: set ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID and "
            "ELEVENLABS_PHONE_NUMBER_ID before calling.",
            file=sys.stderr,
        )
    # Bound to localhost only: the server holds your API key and places real calls.
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Open http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
