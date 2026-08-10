# `wifi_only`

Smallest network-stack example: bring wifi up, log state on a
heartbeat.  Once it's printing `wifi: connected at <ip>`, you've
confirmed every layer between `secrets.toml` and the radio works.

## Why this example exists

Wifi is the layer most likely to surface "config didn't reach the
device" problems: a typo in `secrets.toml`, a missing `password`
field, a `replace-with-your-...` placeholder forgotten on the
user's first deploy.  Running this *before* the higher-level
network examples (HTTP, MQTT) means a failure is unambiguously
about wifi rather than the protocol layer above it.

## Try it

Scaffold your own copy first (the folder here is read-only reference
material), then set your credentials:

```
python3 run.py new my_first_network --from examples/wifi_only
# 1. set [wifi] ssid + password in the workbench's gitignored secrets.toml
# 2. or set ssid per-project in projects/my_first_network/project_config.toml
python3 run.py library add chumicro_wifi     # the libraries app.py imports,
python3 run.py library add chumicro_runner   # fetched once per workbench
python3 run.py deploy my_first_network --tail 30
```

Expected output:

```
wifi_only: connecting ...
wifi: connecting
wifi: connecting
wifi: connected at 192.168.0.42
wifi: connected at 192.168.0.42
...
```

The `connecting → connected` transition can take a few seconds.
If you see repeated `wifi: failed` lines instead, the wifi service
is retrying; check your network name and password in `secrets.toml`
first.  The lower-level cause lands in the service's `last_error`
attribute, which this example prints alongside the failed state.

## What it uses

| Library | Why |
|---|---|
| `chumicro-config` | reads the deployed config back on the device |
| `chumicro-wifi` | the wifi service: state machine + auto-reconnect, sole owner of the radio |
| `chumicro-runner` | the scheduler: `add_periodic` runs the status beacon; `run_until()` parks the CPU between beats |

## What's next

Once `wifi_only` is solid, use the network for something:
[`periodic_get/`](../periodic_get/) fetches a URL on a heartbeat,
[`telemetry_publisher/`](../telemetry_publisher/) publishes over
MQTT, and `projects/example_sensor/` in this template repo is the
full reference (wifi, MQTT, and persistent state in one program).
The index with the recommended order is
[`examples/README.md`](../README.md).
