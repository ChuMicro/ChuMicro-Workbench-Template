# shared/

User-authored helper modules shared between projects in this workspace.

## The default face

`face.py` ships as a starter: `Face(name=...)` is the standard bring-up for a networked project (config + runner + wifi + MQTT wired together, availability last-will, topic routing, periodic system status via `face_status.py`).  `projects/example_sensor/` deliberately writes the same wiring out by hand, so you can see what the face does before leaning on it.

Like everything in `shared/`, these two files are **yours**: edit them freely, and `python3 run.py update` will never touch them.  That also means they never receive upstream fixes.  They are a starting point you own, not a maintained surface.

### Design notes

The source keeps its comments to the contract (these files deploy to the board; prose there costs flash and compile RAM).  The reasoning lives here instead.

**Composition, not a framework.**  Every networked project needs the same six steps: load the runtime config, own the radio, dial the broker, keep the two in step, register both with the runner, and decide what happens when the link is gone for good.  `Face` owns that wiring in one file, so a change to reconnect policy lands once and every project picks it up on its next deploy.  The runner, wifi service, and client stay public attributes: anything the libraries expose is still reachable, and a project that outgrows the defaults builds the pieces itself.  Each piece is also a constructor seam (`config=`, `runner=`, `wifi=`, `mqtt=`), the same default-if-None injection shape the chumicro libraries use, which is how host tests construct a real `Face` around fakes.  The seams import lazily: inject a piece and its libraries are never imported on the host.

**Availability wiring.**  The retained last-will (`OFFLINE`) registers before `connect()` because a will set after CONNACK would not apply until the next reconnect.  `ONLINE`/`offline` are Home Assistant's default `payload_available` / `payload_not_available` values, so a discovery config that omits both keys matches what the board publishes.  This is what makes an entity go unavailable when the board drops off, rather than showing stale state forever.

**Telemetry is dropped, state is republished.**  `publish_telemetry` drops when the broker is away instead of queueing.  A queued sample arrives on reconnect stamped as if it were fresh: a board that lost the broker for half an hour was observed flushing eight stale status snapshots on reconnect before the current one.  Durable state takes the opposite policy, an `on_connect` callback that republishes on every reconnect, because after a broker restart the broker holds no retained state for the device and state topics only publish on change.  A fan nobody touches would stay unavailable forever while the board runs fine.

**Faults print, the loop survives.**  A raising topic handler or service is reported on the serial console (`HANDLER_FAULT` / `SERVICE_FAULT`) and the message dropped.  Anything reachable from the broker is untrusted input, and a bad retained payload must not wedge the boot path.

**`serve_forever` raises at the dead end.**  `WifiService` reaches FAILED only after exhausting its own reconnect policy.  Raising `SystemExit` (instead of returning) hands a board with a hardware watchdog the reset it wants, and leaves the reason on the console for one without.

## Use it like this

Drop a Python file here:

    shared/sensor_helpers.py

Then import it from any project by module name, with no package prefix:

    from sensor_helpers import calibrate

The deploy tooling has `shared/` on its import search path and ships the modules your project imports to the board's `/lib/`, next to the libraries.  (A `from shared.sensor_helpers import ...` form does not resolve on deploy; use the bare module name.)

## When to use shared/ (vs libraries/)

| Use shared/ when... | Use libraries/ when... |
|---|---|
| You wrote it yourself | You wrote it yourself, *and* it deserves its own version + tests + docs |
| Multiple projects in this workspace need it | Multiple workspaces (or eventually PyPI) need it |
| It's small enough that a single file is fine | It's a real library: `pyproject.toml`, `src/`, `tests/` |
| You don't want the ceremony of a full package | You want to publish or distribute it later |

For full chumicro-style library packages: `python3 run.py new --library <name>`.  That command creates `libraries/` the first time it runs.
