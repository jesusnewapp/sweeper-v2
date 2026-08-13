#!/usr/bin/env python3
"""Authenticated JSON bridge for Web Sweeper desktop and mobile clients."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from controller import SweeperController


def response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


def handler_factory(controller: SweeperController, token: str):
    class Handler(BaseHTTPRequestHandler):
        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
            return bool(token) and hmac.compare_digest(supplied, token)

        def do_OPTIONS(self) -> None:  # noqa: N802
            response(self, 204, {})

        def do_GET(self) -> None:  # noqa: N802
            if not self._authorized():
                response(self, 401, {"error": "unauthorized"})
            elif self.path == "/api/status":
                response(self, 200, controller.status())
            else:
                response(self, 404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorized():
                response(self, 401, {"error": "unauthorized"})
                return
            length = min(int(self.headers.get("Content-Length", "0")), 65536)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/action":
                    result = controller.action(str(payload.get("action", "")), str(payload.get("lane", "")))
                    response(self, 202, result)
                elif self.path == "/api/preferences":
                    controller.save_preferences(payload)
                    response(self, 200, {"saved": True})
                else:
                    response(self, 404, {"error": "not found"})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                response(self, 400, {"error": str(error)})

        def log_message(self, pattern: str, *args: object) -> None:
            print(f"{self.client_address[0]} {pattern % args}")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--cert", type=Path)
    parser.add_argument("--key", type=Path)
    args = parser.parse_args()
    token = os.environ.get("WEB_SWEEPER_TOKEN", "")
    if not token:
        raise SystemExit("WEB_SWEEPER_TOKEN is required")
    if args.host not in {"127.0.0.1", "::1", "localhost"} and not (args.cert and args.key):
        raise SystemExit("non-loopback mobile access requires --cert and --key (HTTPS)")
    server = ThreadingHTTPServer((args.host, args.port), handler_factory(SweeperController(args.config), token))
    if args.cert and args.key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    scheme = "https" if args.cert else "http"
    print(f"Web Sweeper controller listening on {scheme}://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
