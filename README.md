# chaos-compose

A small chaos monkey for apps that run in Docker Compose. It crashes one service at random, keeps calling the app while the service is down, and tells you two things: how long the app ran degraded, and whether the user ever got an error.

Netflix's [Chaos Monkey](https://github.com/Netflix/chaosmonkey) needs Spinnaker, and [Chaos Mesh](https://chaos-mesh.org/docs/) needs Kubernetes. If your services run in Docker Compose, this repo shows how to do the same with Python and the Docker command line. Only the Python standard library is used, so there is nothing to install apart from Docker.

## The example app

The example is the home screen of a food delivery app. It shows the restaurant's menu and where your order is. Three services build it:

| Service | Port | What it returns |
| --- | --- | --- |
| `menu` | 8001 (inside Docker only) | Three dishes: Masala Dosa ₹90, Idli Vada ₹70, Filter Coffee ₹30 |
| `orders` | 8002 (inside Docker only) | Order 1042, "out for delivery" |
| `gateway` | 8000 (open on the host) | The home screen, built from the other two |

```
phone app  -->  gateway :8000  -->  menu :8001
                               -->  orders :8002
```

The app talks only to the gateway, so only the gateway opens a port. A healthy call looks like this:

```bash
curl -s localhost:8000
```

```json
{"menu": [{"dish": "Masala Dosa", "price": 90}, {"dish": "Idli Vada", "price": 70}, {"dish": "Filter Coffee", "price": 30}], "menu_stale": false, "order": {"order": "1042", "status": "out for delivery"}}
```

## How the gateway handles a failure

The gateway gives each service half a second to answer (`_TIMEOUT = 0.5` in `services/gateway.py`).

- **Menu service down:** the gateway sends the last menu it saw and sets `"menu_stale": true`. A menu does not change every second, so an old menu is better than an empty screen.
- **Orders service down:** the gateway sends `"order": "status unavailable"`.

So the user always gets a home screen, as long as the gateway itself is up.

## How the chaos script works

`chaos.py` runs on the Docker host. Each round it:

1. Picks a service at random (`menu` or `orders` by default).
2. Crashes it by killing the container's main process with `SIGKILL`. It reads the process ID with `docker inspect -f "{{.State.Pid}}"`.
3. Calls the gateway again and again, 50 milliseconds apart, and sorts each answer:
   - **whole:** a fresh menu and a real order
   - **degraded:** the gateway used a fallback
   - **failed:** the gateway did not answer
4. Stops when the answer is whole again, or after 30 seconds, and prints one row.

### Why it does not use `docker kill`

Every service has `restart: always` in `docker-compose.yml`, which tells Docker to start the container again if it stops. But `docker kill` counts as stopping the container by hand. Docker's [restart policy docs](https://docs.docker.com/engine/containers/start-containers-automatically/) say a manually stopped container is restarted only when the Docker daemon restarts or you start the container again. So the container stays down and the restart is never tested:

```
$ docker kill menu && sleep 3 && docker compose ps -a
menu Exited (137) 3 seconds ago
```

Killing the process inside the container looks like a real crash to Docker, and the restart policy brings it back:

```
$ kill -9 $(docker inspect -f "{{.State.Pid}}" orders) && sleep 2 && docker inspect -f "{{.State.Status}} restarts={{.RestartCount}}" orders
running restarts=1
```

## Requirements

- A Linux machine with Docker and Docker Compose. Tested on Debian 13 with Docker 26.1.5 and Docker Compose 2.26.1, on a server with 1 CPU and 458 MB of memory.
- Python 3 on the host to run `chaos.py`. The services use the `python:3.13-alpine` image.
- Root, or a user allowed to kill the container's processes. `chaos.py` sends the signal from the host.

On Docker Desktop for Mac or Windows the containers run inside a virtual machine, so the process IDs from `docker inspect` are not processes on your machine and `chaos.py` cannot kill them. Run it on a Linux host.

## Run it

```bash
git clone https://github.com/Divyn/chaos-compose.git
cd chaos-compose
docker compose up -d
curl -s localhost:8000
sudo python3 chaos.py 8 3
```

Arguments, all optional:

```
python3 chaos.py [rounds] [gap_seconds] [victims]
```

| Argument | Default | Meaning |
| --- | --- | --- |
| `rounds` | 5 | How many crashes to run |
| `gap_seconds` | 3 | Seconds to wait between rounds |
| `victims` | `menu,orders` | Comma separated services to pick from |

Stop everything with `docker compose down`.

## Reading the output

```
round crashed  degraded for  degraded  failed  restarts
1     orders   0.86 s        4         0       1
```

| Column | Meaning |
| --- | --- |
| `crashed` | The service that was killed this round |
| `degraded for` | Seconds from the crash until the gateway answered whole again |
| `degraded` | Calls that got a fallback answer |
| `failed` | Calls that got no answer at all. This is what the user sees as an error |
| `restarts` | Docker's restart count for that container so far |

## Results from one run

From `python3 chaos.py 8 3` on the server above. The full output, with the other runs below, is in [output.txt](output.txt).

```
round crashed  degraded for  degraded  failed  restarts
1     orders   0.86 s        4         0       1
2     orders   0.88 s        6         0       2
3     orders   1.08 s        8         0       3
4     menu     0.76 s        4         0       1
5     orders   1.46 s        16        0       4
6     orders   2.27 s        30        0       5
7     orders   3.88 s        58        0       6
8     menu     0.82 s        4         0       2
```

- `failed` is 0 in every round, so the fallbacks kept the user from ever seeing an error.
- Each crash of `orders` took longer to recover from than the last: 0.86, 0.88, 1.08, 1.46, 2.27 and 3.88 seconds.

## What to watch out for

**Restarts get slower when a service keeps crashing.** Docker adds a delay before each restart. It starts at 100 milliseconds, doubles every time, and stops growing at 1 minute. It resets to 100 milliseconds once the container stays up for 10 seconds ([docker run reference](https://docs.docker.com/reference/cli/docker/container/run/)). That is the growing recovery time for `orders` above. In round 8, `menu` recovered in 0.82 seconds because it had been up for more than 10 seconds since its last crash. With 12 seconds between rounds, every round recovered in under 1 second:

```
$ python3 chaos.py 4 12
round crashed  degraded for  degraded  failed  restarts
1     orders   0.84 s        3         0       1
2     menu     0.85 s        5         0       1
3     orders   0.76 s        4         0       2
4     menu     0.77 s        4         0       2
```

So when a service crashes again and again, your fallback has to hold for longer each time.

**The gateway is a single point of failure.** The fallbacks live inside the gateway, so nothing protects the user when the gateway itself goes down:

```
$ python3 chaos.py 1 0 gateway
round crashed  degraded for  degraded  failed  restarts
1     gateway  1.44 s        0         6       1
```

All 6 calls failed for 1.44 seconds. Include the gateway in your tests too.

**One machine at a time.** `chaos.py` kills processes on the machine it runs on. If your services run on more than one machine, run one copy on each machine.

## Use it on your own app

1. Set `restart: always` on each service in your compose file.
2. Change `_VICTIMS` in `chaos.py` to your service names. They must match `container_name` in the compose file, or pass the real container names as the third argument.
3. Change `_GATEWAY` to the address your users call.
4. Change `_check` so it knows what a whole, degraded and failed answer look like in your app.

## Files

| File | What it does |
| --- | --- |
| `docker-compose.yml` | Runs the three services with `restart: always` |
| `services/menu.py` | Menu service |
| `services/orders.py` | Orders service |
| `services/gateway.py` | Gateway, with the timeout and the fallbacks |
| `chaos.py` | The chaos monkey |
| `output.txt` | Real output from every run shown here |
