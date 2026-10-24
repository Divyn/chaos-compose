"""Gateway: the one address the app calls. It joins the menu and the order.

If the menu service is down, it serves the last menu it saw and marks it stale.
If the orders service is down, it says the order status is unavailable.
"""

import json
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

_TIMEOUT = 0.5
_last_menu: list | None = None


def _fetch(url: str) -> object | None:
    """Call another service. Return None if it does not answer in time."""
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as response:
            return json.loads(response.read())
    except OSError:
        return None


def _home() -> dict:
    """Build the home screen from both services, falling back where one is down."""
    global _last_menu
    menu = _fetch("http://menu:8001/menu")
    order = _fetch("http://orders:8002/orders/1042")
    stale = menu is None
    if menu is not None:
        _last_menu = menu
    return {
        "menu": menu if menu is not None else _last_menu,
        "menu_stale": stale,
        "order": order if order is not None else "status unavailable",
    }


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps(_home()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    print("gateway up on 8000")
    HTTPServer(("", 8000), _Handler).serve_forever()
