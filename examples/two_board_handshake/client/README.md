# `two_board_handshake/client`

The HTTP-client side of the two-board handshake demo.  Pairs with
the [`server/`](../server/) project running on a *different* physical
board on the same wifi.

## What it does

* Brings wifi up.
* POSTs a JSON payload (`sensor_id` + `value` + `uptime_s` + `sequence`)
  to the server's `/api/sensor` endpoint every `period_ms`
  milliseconds.
* Uses a synthetic sine-wave for the value.  Replace with a real
  sensor read when you have one wired up.
* Self-heals on wifi drops: `HttpClient.from_config` opens a fresh
  connector per request, so a dropped socket doesn't wedge the client.

## Try it

Deploy the server first, note the IP it prints, then update this
project's `project_config.toml` with that IP under
`[two_board] server_host`:

```
python3 run.py new two_board/client --from examples/two_board_handshake/client
# edit projects/two_board/client/project_config.toml: set two_board.server_host
python3 run.py deploy two_board/client --device lolin-s2-cp --tail 30
```

Expected client output:

```
client: connecting to wifi ...
client: wifi at 192.168.0.43
client: posting to http://192.168.0.42:8080/api/sensor every 5000 ms
client: -> POST http://192.168.0.42:8080/api/sensor #0
  -> status=201
client: -> POST http://192.168.0.42:8080/api/sensor #1
  -> status=201
```

If the server's IP is wrong or unreachable, you'll see:

```
  -> error: TimeoutError(...)
```

The loop keeps going.

## What it uses

| Library | Why |
|---|---|
| `chumicro-config` | reads the merged `/runtime_config.msgpack` |
| `chumicro-wifi` | sole-supervisor wifi service |
| `chumicro-sockets` | host TCP for the HTTP client (via `from_config`) |
| `chumicro-requests` | non-blocking HTTP/1.1 client (`HttpClient.from_config`) |
| `chumicro-runner` | tick-shaped scheduler; `tick()` + `wait()` in the `while True` loop park the CPU between posts |
| `chumicro-timing` | `Deadline` for wrap-safe next-post scheduling |

## What's next

Same shape as `periodic_get/`, but talking to your own board on the
LAN instead of a public URL.  Once round-trip is confirmed:

* Swap the synthetic value for a real sensor read (BME280, DHT22, an
  ADC pin, etc.).
* Bump the cadence up to interactive rates (e.g. 100 ms) if your
  network can handle it.
* Add a second client board posting under a different `sensor_id`.
  The server's `/api/latest` shows whichever posted most recently.
