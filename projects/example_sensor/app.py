"""Publish the board's own temperature over MQTT, and count its reboots.

This is the file that runs on the board, and it is the one to copy when
you start your own project: it wires up wifi, an MQTT connection, and a
little bit of storage that survives a reset, and then it just runs.

What it does, in order: bump a boot counter that lives in flash, bring
wifi up, connect to the broker, and publish a temperature reading every
few seconds forever.

What you will see::

    sensor: boot #4
    (then nothing but readings arriving at your broker)

Things to change:

* ``project_config.toml`` beside this file holds the broker address, the
  topic, and how often to publish.
* Wifi credentials do not live here.  They are in the workspace's
  ``secrets.toml``, which is gitignored so a password never reaches a
  commit.
* ``read_celsius`` returns a fixed 20.0 on a board with no temperature
  sensor.  Swap in your own sensor there.

The wifi callback below is worth reading twice.  When the link drops it
tells the MQTT client to stop dialing, and when the link returns it tells
it to reconnect.  That pair is all the reconnect handling this project
needs.
"""

import json


def read_celsius():
    try:
        import microcontroller
        return float(microcontroller.cpu.temperature)
    except (ImportError, AttributeError, RuntimeError):
        return 20.0  # sensorless board: fixed synthetic reading


def run():
    # Import device libraries inside run() so app.py stays importable on
    # a bare host (fresh clone, `library add` not run yet): the workspace
    # smoke test can then always assert run() exists instead of skipping
    # the whole module.  On hosts with the libraries present, and on the
    # device, top-level imports would work just as well.
    from chumicro_config import load_runtime_config
    from chumicro_kvstore import KVStore
    from chumicro_mqtt import MQTTClient
    from chumicro_runner import Runner
    from chumicro_wifi import WifiConfig, WifiService, WifiState

    config = load_runtime_config()
    topic = config.require("sensor.topic")

    kv = KVStore()
    boot_count = kv.get("boot_count", 0) + 1
    kv["boot_count"] = boot_count
    kv.commit()
    print(f"sensor: boot #{boot_count}")

    wifi = WifiService(WifiConfig.from_config(config))
    mqtt = MQTTClient.from_config(config, radio=wifi.adapter.radio)

    # The app owns the wifi<->mqtt coordination: hold() while the link
    # is down so the client doesn't dial a dead radio, connect() the
    # moment it's back (an immediate dial, no backoff wait).
    def on_wifi_state(_old, new):
        if new == WifiState.CONNECTED:
            mqtt.connect()
        else:
            mqtt.hold()

    wifi.on_state_change(on_wifi_state)

    seq = 0

    def publish_reading(now_ms):
        nonlocal seq
        seq += 1
        payload = json.dumps(
            {"boot": boot_count, "celsius": read_celsius(), "n": seq})
        mqtt.publish(topic, payload, qos=1)  # queues until CONNECTED, flushes on CONNACK

    def report_fault(entry, error):
        print("SERVICE_FAULT", entry.service, repr(error))

    runner = Runner(on_handler_error=report_fault)
    runner.add(wifi)
    runner.add(mqtt)
    runner.add_periodic(publish_reading,
                        period_ms=config.require("sensor.publish_period_ms"))

    # The main loop.  tick() gives every registered service one small
    # step; wait() then parks the CPU until the next event or deadline
    # instead of spinning.  It never ends, which is what a board program
    # does.
    while True:
        now_ms = runner.tick()
        runner.wait(now_ms)
