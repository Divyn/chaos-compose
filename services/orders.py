"""Orders service: returns where a customer's order is."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

_ORDERS = {"1042": {"order": "1042", "status": "out for delivery"}}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        order_id = self.path.rsplit("/", 1)[-1]
        body = json.dumps(_ORDERS.get(order_id, {"ok": True})).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    print("orders up on 8002")
    HTTPServer(("", 8002), _Handler).serve_forever()
