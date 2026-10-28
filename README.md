# zero-trace

**Passive, least-privilege network policy generator for Docker Compose microservices.**

Modern microservices often run on flat networks — if one service is
compromised, the attacker can reach every other container. Zero-trace
watches your running compose stack, discovers which services actually talk
to which, and auto-generates the strict firewall/segmentation that blocks
everything else.

## How it works

1. **Capture** — zero-trace injects one `tcpdump` sidecar per service via a
   compose override. Each sidecar uses `network_mode: service:<name>` to
   share a service's network namespace, so it passively records exactly that
   service's traffic. This works on Docker Desktop (macOS/Windows) *and*
   native Linux — no bridge sniffing required.
2. **Engine** — pcaps are parsed (scapy) into normalized flows; container
   IPs are resolved to service names via the Docker API (the
   `com.docker.compose.service` label). TCP SYN-without-ACK identifies the
   listening side, and ACK/SYN-ACK return traffic is folded back into a
   single edge per connection.
3. **Output** — the result is a "least-privilege" reachability graph:
   *exactly what was observed, nothing more*.

## Components

| Path             | Purpose                                                     |
| ---------------- | ----------------------------------------------------------- |
| `app/capture/`   | tcpdump sidecar image + compose override injection         |
| `app/engine/`    | pcap parsing, Docker resolver, reachability graph           |
| `app/generators/`| (next) policy yaml + hardened compose + iptables ruleset    |
| `app/routers/`   | FastAPI dashboard (SSR + live progress)                     |
| `app/service.py` | the profile pipeline (up → capture → teardown → graph)      |
| `env/`           | swappable sample target stack (frontend/auth/orders/db)     |

## Quick start

```bash
uv sync

# web dashboard
uv run zero-trace serve-web           # http://127.0.0.1:8000

# headless capture of the bundled demo stack (45s window)
uv run zero-trace profile --project env --duration 45
```

From the dashboard you can start a profile, watch live progress, browse the
flow table, and view the service topology graph. Projects are swappable:
pass any compose project directory and zero-trace will profile it.

## Status

1. ✅ Repo scaffolding + CLI skeleton
2. ✅ Sample environment + capture-sidecar override injection (verified live)
3. ✅ Pcap parsing → resolver → reachability graph (+ unit tests)
4. ⏳ Policy generators (policy yaml, hardened compose, iptables)
5. ✅ FastAPI web dashboard (SSR + live progress + flow table + graph)
6. ⏳ Traffic exercises, integration test, polish docs

## License

MIT © 2026