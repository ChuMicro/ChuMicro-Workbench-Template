"""Send a reading to an MQTT broker every few seconds, forever.

This is the file that runs on the board.  It brings wifi up, connects to
a broker, and publishes a small JSON payload on a repeating schedule.

The thing to notice is what is *not* here.  ``publish_reading`` never
checks whether wifi is up or whether the broker is connected; it just
publishes.  If the session is not up yet, the client holds the message
and sends it once it is.  Reconnecting after a drop is not handled here
either, because the client does that on its own.

What you will see::

    telemetry_publisher: publishing to sensors/demo
    telemetry_publisher: wifi at 10.0.0.42
    telemetry_publisher: -> sensors/demo #0
    telemetry_publisher: -> sensors/demo #1
    ...

Things to change:

* ``project_config.toml`` beside this file holds the broker address, the
  topic, and the period.
* Replace the ``{"n": seq}`` payload with a real sensor reading.

For a fuller version with storage that survives a reset, see
``projects/example_sensor/``.

Scaffold a copy with
``python3 run.py new <name> --from examples/telemetry_publisher``,
then ``python3 run.py deploy <name>``.
"""

import json

from chumicro_config import load_runtime_config
from chumicro_mqtt import MQTTClient
from chumicro_runner import Runner
from chumicro_wifi import WifiConfig, WifiService, WifiState


def run():
    config = load_runtime_config()
    topic = config.require("mqtt.topic")
    period_ms = config.get("mqtt.publish_period_ms", 5000)

    wifi = WifiService(WifiConfig.from_config(config))
    mqtt = MQTTClient.from_config(config, radio=wifi.adapter.radio)

    def on_wifi_state(_old, new):
        if new == WifiState.CONNECTED:
            print(f"telemetry_publisher: wifi at {wifi.ip}")
            mqtt.connect()

    wifi.on_state_change(on_wifi_state)

    seq = 0

    def publish_reading(now_ms):
        nonlocal seq
        # Replace this payload with your own sensor reading once the
        # round-trip works.
        payload = json.dumps({"n": seq})
        mqtt.publish(topic, payload, qos=1)  # queues until CONNECTED, flushes on CONNACK
        print(f"telemetry_publisher: -> {topic} #{seq}")
        seq += 1

    def report_fault(entry, error):
        print("SERVICE_FAULT", entry.service, repr(error))

    runner = Runner(on_handler_error=report_fault)
    runner.add(wifi)
    runner.add(mqtt)
    runner.add_periodic(publish_reading, period_ms=period_ms)

    print(f"telemetry_publisher: publishing to {topic}")
    # The main loop.  tick() gives every registered service one small
    # step; wait() then parks the CPU until the next event or deadline
    # instead of spinning.  It never ends, which is what a board program
    # does.
    while True:
        now_ms = runner.tick()
        runner.wait(now_ms)
