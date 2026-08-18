"""Standard bring-up for a networked project: config + runner + wifi + MQTT.

    from face import Face

    def run():
        face = Face(name="porch_light")
        face.on_topic(face.topic("set"), handle)
        face.runner.add_periodic(publish_state, period_ms=10_000)
        face.add_status()
        face.serve_forever()

The runner, wifi service, and client stay public attributes.  Yours
(``update`` never touches it); deploys to the board from ``shared/``.
Design rationale lives in ``shared/README.md``.
"""

import json

from chumicro_mqtt import ProtocolState
from chumicro_timing import ticks_ms
from chumicro_wifi import WifiState

DEFAULT_TOPIC_ROOT = "chumicro"

# Home Assistant's default payload_available / payload_not_available.
ONLINE = "online"
OFFLINE = "offline"


def _report_fault(entry, error):
    """Print a service fault instead of letting it kill the runner loop."""
    print("SERVICE_FAULT", entry.service, repr(error))


class Face:
    """Bring up every service without blocking; links come up across ticks.

    Publishes issued before CONNACK queue and flush on connect.
    *name* is the topic namespace and default client id: stable
    across reboots, unique on the broker.  *availability* wires the
    retained OFFLINE will plus ONLINE on connect at
    ``<root>/<name>/availability``.  *config* / *runner* / *wifi* /
    *mqtt* are injection seams defaulting to the real stack.
    """

    def __init__(self, name, *, topic_root=DEFAULT_TOPIC_ROOT, availability=True,
                 config=None, runner=None, wifi=None, mqtt=None):
        # Defaults import lazily: inject a piece and its libraries are
        # never imported, so host tests build a Face around fakes.
        self.name = name
        self.topic_root = topic_root

        if config is None:
            from chumicro_config import load_runtime_config
            config = load_runtime_config()
        self.config = config

        if runner is None:
            from chumicro_runner import Runner
            runner = Runner(on_handler_error=_report_fault)
        self.runner = runner

        if wifi is None:
            from chumicro_wifi import WifiConfig, WifiService
            wifi = WifiService(WifiConfig.from_config(self.config))
        self.wifi = wifi

        if mqtt is None:
            from chumicro_mqtt import MQTTClient
            # mqtt.client_id config key when set, else a stable
            # per-device id derived from the hardware UID.
            mqtt = MQTTClient.from_config(
                self.config, radio=self.wifi.adapter.radio,
            )
        self.mqtt = mqtt

        self.boot_ticks_ms = ticks_ms()

        self.availability_topic = self.topic("availability") if availability else None
        if self.availability_topic is not None:
            # Before connect(), so the will rides the CONNECT packet.
            self.mqtt.set_will(
                self.availability_topic, OFFLINE, qos=1, retain=True,
            )

        self._on_connect_callbacks = []
        self._topic_handlers = {}
        # The client's callback slots are single-assignment; the Face
        # owns both and fans out.
        self.mqtt.on_connect = self._handle_connect
        self.mqtt.on_message = self._dispatch

        self.wifi.on_state_change(self._on_wifi_state)
        self.runner.add(self.wifi)
        self.runner.add(self.mqtt)

    def topic(self, *segments):
        """``face.topic("fan", "set")`` gives ``chumicro/<name>/fan/set``."""
        return "/".join((self.topic_root, self.name) + segments)

    def _on_wifi_state(self, _old, new):
        # hold() while the link is down, connect() the moment it
        # returns (dials now instead of waiting out the backoff).
        if new == WifiState.CONNECTED:
            self.mqtt.connect()
        else:
            self.mqtt.hold()

    @property
    def broker_connected(self):
        """True while the client is CONNECTED to the broker."""
        return self.mqtt.state == ProtocolState.CONNECTED

    # -- inbound ---------------------------------------------------

    def on_topic(self, topic, callback, *, qos=1):
        """Subscribe to *topic*, routing payloads to *callback* as stripped str.

        A raising callback is reported and the message dropped
        (broker input is untrusted).  Exact match only; replayed on
        every reconnect.  Assigning ``mqtt.on_message`` yourself
        disables these routes.
        """
        self._topic_handlers[topic] = callback
        self.mqtt.subscribe(topic, qos=qos)

    def _dispatch(self, topic, payload):
        handler = self._topic_handlers.get(topic)
        if handler is None:
            return
        try:
            text = payload.decode() if isinstance(payload, bytes) else str(payload)
            handler(text.strip())
        except Exception as error:
            print("HANDLER_FAULT", topic, repr(payload), repr(error))

    # -- outbound --------------------------------------------------

    def publish_telemetry(self, topic, payload, *, qos=0):
        """Publish a now-only reading.  Returns False when dropped.

        Dropped, not queued, while the broker is away: a reconnect
        must not replay stale samples as fresh.  Durable state
        belongs in an :meth:`on_connect` callback instead.
        """
        if not self.broker_connected:
            return False
        self.mqtt.publish(topic, payload, qos=qos)
        return True

    def add_status(self, *, period_ms=30_000, extra=None, qos=0):
        """Publish the ``face_status`` snapshot on ``topic("status")``.

        *extra* is a zero-arg callable returning fields to merge in.
        Telemetry semantics: dropped while the broker is away.
        Returns the publish function so a caller can fire one now.
        """
        from face_status import snapshot

        def publish_status(_now_ms=None):
            fields = {"wifi_state": self.wifi.state}
            if extra is not None:
                fields.update(extra() or {})
            payload = snapshot(self.boot_ticks_ms, extra=fields)
            return self.publish_telemetry(
                self.topic("status"), json.dumps(payload), qos=qos,
            )

        self.runner.add_periodic(publish_status, period_ms=period_ms)
        return publish_status

    # -- broker session --------------------------------------------

    def on_connect(self, callback):
        """Register *callback* to run on every broker (re)connect.

        Republish retained state here: after a broker restart the
        broker holds nothing for this device, and state topics only
        publish on change.
        """
        self._on_connect_callbacks.append(callback)

    def _handle_connect(self):
        # After CONNACK: subscriptions replayed, queue drained.  Each
        # callback is isolated so one raising can't starve the rest.
        self.announce()
        for callback in self._on_connect_callbacks:
            try:
                callback()
            except Exception as error:
                print("CONNECT_FAULT", repr(error))

    def announce(self):
        """Publish retained ONLINE on the availability topic."""
        if self.availability_topic is not None:
            self.mqtt.publish(
                self.availability_topic, ONLINE, qos=1, retain=True,
            )

    def serve_forever(self):
        """Tick and wait, forever.

        ``tick()`` gives every registered service one small step;
        ``wait()`` then parks the CPU until the next event or deadline.
        """
        while True:
            now_ms = self.runner.tick()
            self.runner.wait(now_ms)
