# `telemetry_publisher`

Wifi up, MQTT publish on a heartbeat.  Same shape as
[`periodic_get/`](../periodic_get/) but pushes data via MQTT
instead of pulling via HTTP.

## Why this example exists

MQTT is the canonical protocol for "device → service" telemetry
flows.  This example exercises the full publisher path:
TCP (or TLS) socket → MQTT CONNECT → periodic PUBLISH → ACK.
`MQTTClient.from_config` owns the transport, so a wifi drop
self-heals.  The client rebuilds its connection and re-issues
CONNECT with backoff, and any sample published while it's
reconnecting buffers in the pre-connect queue and flushes on the
next CONNACK (no CONNECTED guard needed in the publisher).

The shipped payload is a trivial JSON sequence counter.  Replace
the `payload` body in the `publish_reading` function with your
real sensor reading once the round-trip works (the
`projects/example_sensor/` reference in this template repo shows
the full version with on-board temperature + persistent boot
counter).

## Try it

```
python3 run.py new my_publisher --from examples/telemetry_publisher
# edit projects/my_publisher/project_config.toml: set broker / topic / cadence
python3 run.py deploy my_publisher --tail 30
```

In another terminal, subscribe to the topic:

```
mosquitto_sub -h broker.hivemq.com -t 'chumicro/example/telemetry'
```

Expected `--tail` output:

```
telemetry_publisher: publishing to chumicro/example/telemetry
telemetry_publisher: wifi at 192.168.0.42
telemetry_publisher: -> chumicro/example/telemetry #0
telemetry_publisher: -> chumicro/example/telemetry #1
...
```

And `mosquitto_sub` showing one JSON line per tick:

```
{"n": 0}
{"n": 1}
{"n": 2}
```

## TLS

Point `[mqtt.broker] port` at `8883` and pass an `ssl_context=` to
`MQTTClient.from_config` in `app.py` to exercise the TLS path.
TLS-on-MicroPython requires a build with `MBEDTLS_PEM_PARSE_C`
enabled (the rp2 default doesn't include it; the chumicro-sockets
adapter handles PEM→DER conversion automatically when a CA bundle
is supplied: check `projects/example_sensor/` for the recipe).

## What it uses

| Library | Why |
|---|---|
| `chumicro-config` | reads the merged `/runtime_config.msgpack` |
| `chumicro-wifi` | sole-supervisor wifi service |
| `chumicro-sockets` | host TCP / TLS for the MQTT transport (via `from_config`) |
| `chumicro-mqtt` | non-blocking MQTT 3.1.1 client (QoS 0 + 1); pre-connect publish queue |
| `chumicro-runner` | tick-shaped scheduler; `add_periodic` + a `while True` loop of `tick()` / `wait()` |

## What's next

For a two-board demo, see
[`two_board_handshake/`](../two_board_handshake/): a client board
POSTs readings to a server board via plain HTTP on the same LAN.
