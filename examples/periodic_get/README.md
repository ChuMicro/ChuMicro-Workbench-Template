# `periodic_get`

Wifi up, then GET a configured URL on a heartbeat.  Smallest
example that exercises the upper-layer network stack
(`chumicro-sockets` + `chumicro-requests`) on top of
`chumicro-wifi`.

## Why this example exists

Once `wifi_only/` confirms wifi credentials work, the next
question is "can I actually move bytes through the network
stack?"  This project answers it: every `period_ms` it issues an
HTTP GET, prints the status code + body size, and waits for the
next tick.  Failures (DNS error, timeout, server gone) print a
descriptive error and the loop continues.  Wifi reconnects keep
working in the gap between requests.

## Try it

```
python3 run.py new my_fetcher --from examples/periodic_get
# edit projects/my_fetcher/project_config.toml: set fetch.url to a real URL
python3 run.py deploy my_fetcher --tail 60
```

Expected output:

```
periodic_get: connecting ...
periodic_get: connected at 192.168.0.42
periodic_get: GET http://example.com/
  -> status=200 bytes=1256
periodic_get: GET http://example.com/
  -> status=200 bytes=1256
...
```

If the URL doesn't reach (DNS fail, timeout), you'll see:

```
periodic_get: GET http://example.com/
  -> error: TimeoutError(...)
```

The loop keeps going.

## What it uses

| Library | Why |
|---|---|
| `chumicro-config` | reads the merged `/runtime_config.msgpack` |
| `chumicro-wifi` | sole-supervisor wifi service |
| `chumicro-sockets` | host TCP for the HTTP client |
| `chumicro-requests` | non-blocking HTTP/1.1 client (`HttpClient.from_config`) |
| `chumicro-runner` | tick-shaped scheduler; `tick()` + `wait()` in the `while True` loop park the CPU between fetches |
| `chumicro-timing` | `Deadline` for wrap-safe next-fetch scheduling |

## What's next

Once `periodic_get` is solid, the natural follow-on is
[`telemetry_publisher/`](../telemetry_publisher/): same shape,
but publishes the data via MQTT instead of pulling via HTTP.
