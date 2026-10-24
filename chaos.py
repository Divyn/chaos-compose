"""Chaos monkey for a Docker Compose app.

Each round it crashes one random service, then calls the gateway until the
app is whole again, and records how long the app ran degraded.

Run on the Docker host as root: python3 chaos.py [rounds] [gap_seconds] [victims]
victims is a comma separated list of services, menu,orders by default.
"""

import json
import os
import random
import signal
import subprocess
import sys
import time
import urllib.request

_VICTIMS = ["menu", "orders"]
_GATEWAY = "http://localhost:8000/"
_POLL = 0.05
_GIVE_UP = 30.0


def _inspect(container: str, field: str) -> str:
    """Read one field of a container from docker inspect."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{" + field + "}}", container],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _crash(container: str) -> None:
    """Kill the container's main process, the way a real crash would."""
    os.kill(int(_inspect(container, ".State.Pid")), signal.SIGKILL)


def _check() -> str:
    """Call the gateway once. Return whole, degraded or failed."""
    try:
        with urllib.request.urlopen(_GATEWAY, timeout=2) as response:
            home = json.loads(response.read())
    except OSError:
        return "failed"
    whole = not home["menu_stale"] and isinstance(home["order"], dict)
    return "whole" if whole else "degraded"


def _round(victim: str) -> dict:
    """Crash one service and measure until the gateway is whole again."""
    _crash(victim)
    start = time.monotonic()
    counts = {"degraded": 0, "failed": 0}
    while time.monotonic() - start < _GIVE_UP:
        state = _check()
        if state == "whole":
            break
        counts[state] += 1
        time.sleep(_POLL)
    return {
        "victim": victim,
        "seconds": round(time.monotonic() - start, 2),
        **counts,
        "restarts": int(_inspect(victim, ".RestartCount")),
    }


def main() -> None:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
    victims = sys.argv[3].split(",") if len(sys.argv) > 3 else _VICTIMS
    print(f"{'round':<6}{'crashed':<9}{'degraded for':<14}{'degraded':<10}{'failed':<8}{'restarts'}")
    for number in range(1, rounds + 1):
        row = _round(random.choice(victims))
        print(
            f"{number:<6}{row['victim']:<9}{str(row['seconds']) + ' s':<14}"
            f"{row['degraded']:<10}{row['failed']:<8}{row['restarts']}"
        )
        time.sleep(gap)


if __name__ == "__main__":
    main()
