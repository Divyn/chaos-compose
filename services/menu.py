"""Menu service: returns the dishes a restaurant has today."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

_MENU = [
    {"dish": "Masala Dosa", "price": 90},
    {"dish": "Idli Vada", "price": 70},
    {"dish": "Filter Coffee", "price": 30},
]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps(_MENU if self.path == "/menu" else {"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    print("menu up on 8001")
    HTTPServer(("", 8001), _Handler).serve_forever()
