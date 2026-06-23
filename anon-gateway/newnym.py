#!/usr/bin/env python3
"""
Shim HTTP NEWNYM — expose la rotation d'identité Tor sur HTTP.

Argus appelle `POST http://anon-gateway:9052/newnym` (cf. settings.TOR_CONTROL_URL)
pour obtenir un nouveau circuit Tor (nouvelle IP de sortie). Ce shim relaie le
signal au control port Tor (127.0.0.1:9051) en parlant le protocole texte.
"""
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 9051


def signal_newnym() -> bool:
    try:
        with socket.create_connection((CONTROL_HOST, CONTROL_PORT), timeout=5) as s:
            s.sendall(b'AUTHENTICATE ""\r\n')
            if b"250" not in s.recv(1024):
                return False
            s.sendall(b"SIGNAL NEWNYM\r\n")
            ok = b"250" in s.recv(1024)
            s.sendall(b"QUIT\r\n")
            return ok
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.rstrip("/") == "/newnym":
            ok = signal_newnym()
            self._send(200 if ok else 502,
                       b'{"renewed": true}' if ok else b'{"renewed": false}')
        else:
            self._send(404, b'{"error": "not found"}')

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/health"):
            self._send(200, b'{"status": "ok"}')
        else:
            self._send(404, b'{"error": "not found"}')

    def log_message(self, *args):  # silencieux
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9052), Handler).serve_forever()
