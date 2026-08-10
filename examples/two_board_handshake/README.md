# `two_board_handshake/`

The smallest "two physical boards talking to each other" demo.
Two single-project apps, one server and one client, deployed to two
different boards on the same wifi network.

* [`server/`](server/): runs an HTTP server on board A.  Accepts
  JSON readings at `POST /api/sensor`, shows the latest at `GET /`.
* [`client/`](client/): runs on board B.  POSTs a synthetic sine-
  wave reading to the server every 5 seconds.

## Why this example exists

Single-board examples (`hello_world/` → `wifi_only/` →
`periodic_get/` → `telemetry_publisher/`) prove your board can talk
to the wider internet.  This pair proves two of *your* boards can
talk to *each other* over the LAN: a different shape than
client/server-against-the-public-internet, and the smallest pattern
behind every "sensor mesh" / "fleet" / "garden of pi-picos" project.

It's also the first example that demonstrates `chumicro-http-server`
running on a battery-class board.

## Try it (in order)

You'll need two registered devices in `devices.yml`.  Adjust the
device IDs below to match yours (`python3 run.py devices`).

```
# 1. Scaffold both projects from the example trees.
python3 run.py new two_board/server --from examples/two_board_handshake/server
python3 run.py new two_board/client --from examples/two_board_handshake/client

# 2. Deploy the server first; note the IP it prints.
python3 run.py deploy two_board/server --device pi-pico-w-cp --tail 10
# server: wifi at 192.168.0.42
# server: listening on http://192.168.0.42:8080/

# 3. Plug that IP into the client's config:
#    edit projects/two_board/client/project_config.toml
#    -> two_board.server_host = "192.168.0.42"

# 4. Deploy the client to the second board.
python3 run.py deploy two_board/client --device lolin-s2-cp --tail 30
# client: -> POST http://192.168.0.42:8080/api/sensor #0
#   -> status=201
```

You can also hit the server from your laptop while the client is
running, to confirm the round-trip from a third party:

```
curl http://192.168.0.42:8080/api/latest
```

## What's next

Once the round-trip is solid:

* Swap the synthetic sine-wave on the client for a real sensor read
  (BME280, DHT22, an ADC pin).
* Add a second client board posting under a different `sensor_id`.
  The server's `/api/latest` shows whichever posted most recently;
  extend it to a rolling window if you want history.
* Replace the client's HTTP POST with an MQTT publish, the server's
  HTTP server with an MQTT subscriber.  Same hardware, different
  transport.  See `telemetry_publisher/` for the publisher half.

For the full network reference (wifi → sockets → mqtt → kvstore,
with persistent state across resets), see
`projects/example_sensor/` in this template repo.
