# chaos-compose

A chaos monkey for a Docker Compose app. Three services (menu, orders, gateway) run in Docker Compose. `chaos.py` crashes one service at random, calls the gateway until the app is whole again, and prints how long it ran degraded.

Run on the Docker host as root:

```bash
docker compose up -d
python3 chaos.py 8 3
python3 chaos.py 1 0 gateway
```

`docker kill` counts as a manual stop, so `restart: always` does not bring the container back. `chaos.py` kills the container's main process instead, which Docker treats as a crash.

Sample output from a 1 CPU server with Docker 26.1.5: `output.txt`.
