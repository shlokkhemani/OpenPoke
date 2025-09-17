#!/usr/bin/env python3
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Optional

# Ensure top-level package imports work when running as module
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from openrouter_client import stream_chat_completion


def _parse_body_length(handler: BaseHTTPRequestHandler) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except Exception:
        length = 0
    if length > 0:
        data = handler.rfile.read(length)
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return {}
    return {}


def _messages_from_request(body: dict, query: dict):
    # POST body preferred
    msgs = body.get("messages")
    if isinstance(msgs, list):
        return msgs
    # Fallback for GET: build from prompt param
    prompt = None
    for key in ("prompt", "q", "text"):
        if key in query:
            vals = query.get(key) or []
            if vals:
                prompt = vals[0]
                break
    if prompt:
        return [{"role": "user", "content": str(prompt)}]
    return []


class ChatHandler(BaseHTTPRequestHandler):
    server_version = "OpenPokePy/0.1"

    def do_OPTIONS(self):
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        self._handle_chat()

    def do_POST(self):
        self._handle_chat()

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _handle_chat(self):
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/chat":
            self.send_response(404)
            self._send_cors()
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        query = parse_qs(parsed.query)
        body = _parse_body_length(self) if self.command == "POST" else {}

        api_key = body.get("api_key") or os.getenv("OPENROUTER_API_KEY", "")
        model = body.get("model") or (query.get("model") or [os.getenv("OPENROUTER_MODEL", "openrouter/auto")])[0]
        system = body.get("system") or (query.get("system") or [""])[0]
        messages = _messages_from_request(body, query)

        if not api_key:
            self.send_response(400)
            self._send_cors()
            self.end_headers()
            self.wfile.write(b"Missing api_key")
            return
        if not messages:
            self.send_response(400)
            self._send_cors()
            self.end_headers()
            self.wfile.write(b"Missing messages or prompt")
            return

        # Start SSE response
        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        # Close connection when streaming completes so client status resets
        self.send_header("Connection", "close")
        self.end_headers()

        def send_event(data: str):
            try:
                self.wfile.write(b"data: ")
                self.wfile.write(data.encode("utf-8"))
                self.wfile.write(b"\n\n")
                self.wfile.flush()
            except Exception:
                raise

        try:
            stream = stream_chat_completion(
                model=model,
                messages=messages,
                system=system,
                api_key=api_key,
            )
            for delta in stream:
                if delta.get("type") == "content":
                    # Emit OpenAI-like delta
                    chunk = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": delta.get("text", "")},
                                "finish_reason": None,
                            }
                        ],
                    }
                    send_event(json.dumps(chunk))
                elif delta.get("type") == "event" and delta.get("event") == "done":
                    send_event("[DONE]")
                    try:
                        self.wfile.flush()
                    except Exception:
                        pass
                    # ensure server closes connection for this request
                    self.close_connection = True
                    break
                # tool_call deltas are ignored for simple chat
        except Exception as e:
            err = {"error": str(e)}
            try:
                send_event(json.dumps(err))
            finally:
                return


def run(host: str = "0.0.0.0", port: Optional[int] = None):
    if port is None:
        port = int(
            os.environ.get("OPENPOKE_PORT")
            or os.environ.get("PY_PORT")
            or os.environ.get("PORT")
            or 8001
        )
    httpd = HTTPServer((host, port), ChatHandler)
    print(f"Python chat server listening on http://{host}:{port}/chat")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    # Allow overriding host/port via env and CLI
    env_host = os.getenv("OPENPOKE_HOST", "0.0.0.0")
    try:
        env_port = int(os.getenv("OPENPOKE_PORT", "8001"))
    except ValueError:
        env_port = 8000

    parser = argparse.ArgumentParser(description="OpenPoke Python chat server")
    parser.add_argument("--host", default=env_host, help=f"Host to bind (default: {env_host})")
    parser.add_argument("--port", type=int, default=env_port, help=f"Port to bind (default: {env_port})")
    args = parser.parse_args()

    try:
        run(host=args.host, port=args.port)
    except OSError as e:
        msg = str(e)
        if "Address already in use" in msg or getattr(e, "errno", None) in (48, 98):
            print(
                f"Port {args.port} is already in use. Choose another with --port or set OPENPOKE_PORT."
            )
        raise
