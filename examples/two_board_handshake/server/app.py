"""One board talking to another: the side that listens.

This is the file that runs on the board playing server.  It brings wifi
up, prints the address it ended up with, and then answers requests: it
takes readings the other board POSTs to ``/api/sensor``, and serves a
small status page at ``/`` plus the latest reading as JSON at
``/api/latest``.

You need two boards on the same wifi for this one.  Deploy this side
first, watch the serial output for the line that prints its IP, and put
that IP into the client's ``project_config.toml``.

The latest reading is kept in memory, so a reset forgets it.  That is
fine here: the client keeps posting.

What you will see::

    server: connecting to wifi ...
    server: wifi at 10.0.0.42
    server: listening on http://10.0.0.42:8080/
    server: configure the client's two_board.server_host = '10.0.0.42'
    server: <- sensor=sensor-1 value=21.4

Things to change:

* ``project_config.toml`` beside this file holds ``http_server.bind_port``
  if 8080 clashes with something on your network.

Scaffold a copy with
``python3 run.py new two_board/server --from examples/two_board_handshake/server``,
then ``python3 run.py deploy two_board/server``.
"""

from chumicro_config import load_runtime_config
from chumicro_http_server import HttpServer, build_response
from chumicro_runner import Runner
from chumicro_timing import ticks_ms
from chumicro_wifi import WifiConfig, WifiService, WifiState


class _SensorState:
    """Latest sensor reading received from the client board."""

    __slots__ = ("received_at_ms", "sensor_id", "value")

    received_at_ms: int | None
    sensor_id: str | None
    value: float | None

    def __init__(self) -> None:
        self.sensor_id = None
        self.value = None
        self.received_at_ms = None


def _register_routes(server: HttpServer, state: _SensorState) -> None:
    @server.route("/")
    def index(_request):
        if state.value is None:
            body = (
                "<html><body><h1>two_board_handshake</h1>"
                "<p>No readings yet; waiting for client POST.</p>"
                "</body></html>"
            )
        else:
            body = (
                "<html><body><h1>two_board_handshake</h1>"
                f"<p>Latest from <b>{state.sensor_id}</b>:"
                f" <b>{state.value}</b></p>"
                f"<p>Received at: {state.received_at_ms} ms</p>"
                "</body></html>"
            )
        return build_response(200, html=body)

    @server.route("/api/latest")
    def latest(_request):
        return build_response(200, json={
            "sensor_id": state.sensor_id,
            "value": state.value,
            "received_at_ms": state.received_at_ms,
        })

    @server.route("/api/sensor", methods=["POST"])
    def sensor(request):
        payload = request.json()
        state.sensor_id = payload.get("sensor_id", "unknown")
        state.value = payload.get("value")
        state.received_at_ms = ticks_ms()
        print(f"server: <- sensor={state.sensor_id} value={state.value}")
        return build_response(201, json={"ok": True})


def run() -> None:
    config = load_runtime_config()
    bind_port = config.get("http_server.bind_port", 8080)

    wifi = WifiService(WifiConfig.from_config(config))

    def report_fault(entry, error):
        print("SERVICE_FAULT", entry.service, repr(error))

    runner = Runner(on_handler_error=report_fault)
    runner.add(wifi)

    print("server: connecting to wifi ...")
    while not wifi.connected:
        now_ms = runner.tick()
        if wifi.state == WifiState.FAILED:
            raise SystemExit(f"wifi failed: {wifi.last_error}")
        runner.wait(now_ms)
    print(f"server: wifi at {wifi.ip}")
    print(f"server: listening on http://{wifi.ip}:{bind_port}/")
    print(f"server: configure the client's two_board.server_host = {wifi.ip!r}")

    state = _SensorState()
    server = HttpServer.from_config(config, radio=wifi.adapter.radio)
    _register_routes(server, state)
    runner.add(server)

    # The main loop.  tick() gives every registered service one small
    # step; wait() then parks the CPU until the next event or deadline
    # instead of spinning.  It never exits, which is what a board
    # program does: it parks between requests and wakes on the next one.
    while True:
        now_ms = runner.tick()
        runner.wait(now_ms)
