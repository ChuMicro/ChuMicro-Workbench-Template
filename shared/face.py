"""Default face: standard bring-up for a networked project here.

Every networked project needs the same six steps: load the runtime
config, own the radio, dial the broker, keep the two in step,
register both with the runner, and decide what happens when the
link is gone for good.  ``projects/example_sensor/app.py`` writes
that out by hand on purpose (it is the teaching reference for the
underlying wiring); this module owns it instead, so a change to
wifi or reconnect policy lands in one file and every project picks
it up on its next deploy.

What a project writes::

    from face import Face

    def run():
        face = Face(name="porch_light")
        face.on_topic(face.topic("set"), handle)
        face.runner.add_periodic(publish_state, period_ms=10_000)
        face.add_status()
        face.serve_forever()

The runner, wifi service and client stay public on the returned
object: this is composition, not a framework.  Anything the
libraries expose is still reachable, and a project that outgrows
the defaults can build the pieces itself.

Every service is also a constructor seam (``config=``, ``runner=``,
``wifi=``, ``mqtt=``), the same default-if-None injection shape the
chumicro libraries use.  Host tests construct a real ``Face``
around fakes; on the device the defaults build the real stack.

This file is yours (``shared/`` is user-owned; ``update`` never
touches it): a starter to edit, not a maintained surface.  Deployed
to the board from ``shared/`` alongside the libraries, so ``import
face`` resolves the same on device as on the host.  The module-top
imports resolve on any host with the workspace's ``libraries/``
populated (``conftest.py`` puts them on the path); they are eager
per chumicro's import guidance because none of them are optional.
"""

import json

from chumicro_mqtt import ProtocolState
from chumicro_timing import ticks_ms
from chumicro_wifi import WifiState

DEFAULT_TOPIC_ROOT = "chumicro"

#: Retained payloads on the availability topic.  These are Home
#: Assistant's defaults for ``payload_available`` /
#: ``payload_not_available``, so a discovery config that omits both
#: keys still matches what the board publishes.
ONLINE = "online"
OFFLINE = "offline"


def _report_fault(entry, error):
    """Print a service fault without tearing down the runner.

    A handler that raises would otherwise kill the loop and take
    the whole device offline.  Printing keeps the other services
    ticking and leaves a breadcrumb on the serial console.
    """
    print("SERVICE_FAULT", entry.service, repr(error))


class Face:
    """Config + runner + wifi + MQTT, wired together and ticking.

    Construction brings up every service but does not block: the
    radio and the broker connect across runner ticks once
    :meth:`serve_forever` (or the caller's own tick loop) starts
    turning.  Publishes issued before CONNACK queue and flush on
    connect, so a project never has to gate its own startup on the
    link being up.

    Args:
        name: Device identity.  Becomes the topic namespace and the
            default MQTT client id, so it must be stable across
            reboots and unique on the broker.
        topic_root: First topic segment.  Defaults to
            ``chumicro``, giving ``chumicro/<name>/...``.
        availability: When True (the default), set a retained last
            will on ``<root>/<name>/availability`` and publish
            ONLINE once the broker connection is up.  This is what
            makes a Home Assistant entity go unavailable when the
            board drops off, rather than showing a stale state
            forever.
        config: Mapping-like runtime config.  Defaults to
            ``load_runtime_config()`` (the deployed msgpack).
        runner: A ``Runner``-shaped object.  Defaults to a real one
            wired to :func:`_report_fault`.
        wifi: A ``WifiService``-shaped object.  Defaults to one
            built from the ``wifi.*`` config keys.
        mqtt: An ``MQTTClient``-shaped object.  Defaults to
            ``MQTTClient.from_config`` on the ``mqtt.*`` keys,
            routed through the wifi service's radio.
    """

    def __init__(self, name, *, topic_root=DEFAULT_TOPIC_ROOT, availability=True,
                 config=None, runner=None, wifi=None, mqtt=None):
        # Default construction imports lazily, the same shape the
        # libraries' from_config uses (patterns.md: lazy imports are
        # for DI fallbacks): inject a piece and its libraries are
        # never imported, which is also what lets a host test build
        # a real Face around fakes.
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
            # Client id comes from the ``mqtt.client_id`` config key
            # when set (project_config.toml), else from_config derives
            # a stable per-device id from the hardware UID, so a
            # reconnecting board reclaims its own broker session
            # either way.
            mqtt = MQTTClient.from_config(
                self.config, radio=self.wifi.adapter.radio,
            )
        self.mqtt = mqtt

        self.boot_ticks_ms = ticks_ms()

        self.availability_topic = self.topic("availability") if availability else None
        if self.availability_topic is not None:
            # Registered before connect() so it rides the CONNECT
            # packet; a will set after CONNACK would not apply until
            # the next reconnect.
            self.mqtt.set_will(
                self.availability_topic, OFFLINE, qos=1, retain=True,
            )

        self._on_connect_callbacks = []
        self._topic_handlers = {}
        # The client's callback slots are single-assignment; the
        # Face owns both and fans out, so two components can listen
        # without silently clobbering each other.  Projects that
        # need the raw firehose can still replace mqtt.on_message,
        # at the cost of every on_topic() registration going quiet.
        self.mqtt.on_connect = self._handle_connect
        self.mqtt.on_message = self._dispatch

        self.wifi.on_state_change(self._on_wifi_state)
        self.runner.add(self.wifi)
        self.runner.add(self.mqtt)

    def topic(self, *segments):
        """Build a topic under this device's namespace.

        ``face.topic("fan", "set")`` gives
        ``chumicro/<name>/fan/set``.
        """
        return "/".join((self.topic_root, self.name) + segments)

    def _on_wifi_state(self, _old, new):
        """Keep the client in step with the radio.

        ``hold()`` while the link is down so the client is not
        dialing a dead radio and burning its backoff; ``connect()``
        the moment it returns, which dials immediately rather than
        waiting out the current backoff window.
        """
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
        """Subscribe to *topic* and route its messages to *callback*.

        The callback receives the payload decoded and stripped to
        ``str`` — the shape of every command payload Home Assistant
        sends ("ON", "2", "15").  A callback that raises is reported
        and the message dropped: anything reachable from the broker
        is untrusted input, and a bad retained payload must not be
        able to wedge the boot path.

        ``subscribe`` is a declaration valid in any state, so this
        works before the broker is up and the client replays it on
        every reconnect.  Exact topic match only; a project that
        wants wildcards or binary payloads sets ``mqtt.on_message``
        itself instead (which disables every on_topic route).
        """
        self._topic_handlers[topic] = callback
        self.mqtt.subscribe(topic, qos=qos)

    def _dispatch(self, topic, payload):
        """Route one inbound message to its registered handler."""
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
        """Publish a reading that is only meaningful right now.

        Dropped when the broker is not connected, rather than queued.
        The client's ``when_disconnected`` policy is per-client, so it
        cannot separate the two kinds of message a device publishes:

        * **State** is durable.  It must survive a reconnect, which is
          what :meth:`on_connect` republishing is for.
        * **Telemetry** is a sample of a moment.  Queuing it means
          that on reconnect the broker receives a burst of readings
          that were true minutes ago, stamped as if they arrived now.
          A consumer charting them sees a spray of stale points.

        Observed on hardware: a board that lost the broker for half an
        hour flushed eight stale status snapshots on reconnect before
        the current one.

        Returns:
            True when published, False when dropped.
        """
        if not self.broker_connected:
            return False
        self.mqtt.publish(topic, payload, qos=qos)
        return True

    def add_status(self, *, period_ms=30_000, extra=None, qos=0):
        """Publish the system snapshot on ``topic("status")`` periodically.

        Every device reports the same baseline — uptime, free RAM
        and storage, CPU temperature, reset reason (see
        ``face_status``) — plus the wifi state and whatever *extra*
        returns.  Telemetry, not state: dropped while the broker is
        away rather than queued, for the reasons on
        :meth:`publish_telemetry`.

        Args:
            period_ms: Publish cadence.
            extra: Optional zero-arg callable returning a dict of
                project-specific fields merged into the snapshot.
            qos: QoS for the status publishes.

        Returns:
            The publish function, so a caller can also fire one
            immediately (or a test can drive it directly).
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

        A device must republish its retained state on reconnect, not
        just at boot.  A board that has been up for days and briefly
        loses the broker (broker restart, network blip) comes back
        with the broker holding no retained state for it, and nothing
        else will ever republish: state topics are only written on
        change, and a fan that nobody touches does not change.  Home
        Assistant would show it unavailable indefinitely while the
        board runs perfectly.
        """
        self._on_connect_callbacks.append(callback)

    def _handle_connect(self):
        """Re-announce and let registered callbacks republish.

        Fired by the client after CONNACK, once subscriptions have
        been replayed and the pre-connect queue is drained, so
        anything published here lands after the backlog rather than
        being overtaken by it.
        """
        self.announce()
        for callback in self._on_connect_callbacks:
            callback()

    def announce(self):
        """Publish retained ONLINE on the availability topic.

        Safe to call before the broker is up: the publish queues and
        flushes on CONNACK, which is exactly when it becomes true.
        """
        if self.availability_topic is not None:
            self.mqtt.publish(
                self.availability_topic, ONLINE, qos=1, retain=True,
            )

    def serve_forever(self):
        """Tick until the radio gives up, then raise.

        ``WifiService`` reaches FAILED only after exhausting its own
        reconnect policy, so this is the genuine dead end rather
        than a transient drop.  Raising (instead of returning) hands
        a board with a hardware watchdog the reset it wants, and
        leaves the reason on the console for one without.
        """
        # No announce() here: _handle_connect covers the first connect
        # and every reconnect after it, so announcing again would only
        # publish a duplicate before the link is even up.
        self.runner.run_until(lambda: self.wifi.state == WifiState.FAILED)
        raise SystemExit(f"{self.name}: wifi failed: {self.wifi.last_error}")
