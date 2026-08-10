# Your ChuMicro workbench

**The home for every board project you build.  You write a `run()` function on your laptop; one command puts it on the board and follows what it prints.**

The [ChuMicro libraries](https://chumicro.github.io/ChuMicro/) keep a microcontroller working through real life: wifi that reconnects itself, MQTT (the message channel most home-automation software speaks) that rides out network outages, storage that survives a reboot.  This repo is where projects built on them live: your code stays here in git, with your editor and your tests, and the tooling puts a copy on the board whenever you say so.

Here is a whole project.  It reads the chip temperature, publishes it over MQTT, and counts its own reboots.  This is the shipped [`projects/example_sensor/`](projects/example_sensor/), lightly abridged:

```python
# projects/example_sensor/app.py
def run():
    from chumicro_config import load_runtime_config
    from chumicro_kvstore import KVStore
    from chumicro_mqtt import MQTTClient
    from chumicro_runner import Runner
    from chumicro_wifi import WifiConfig, WifiService, WifiState

    config = load_runtime_config()   # your secrets.toml + project_config.toml, merged

    kv = KVStore()                   # storage that survives reboots
    boot_count = kv.get("boot_count", 0) + 1
    kv["boot_count"] = boot_count
    kv.commit()
    print(f"sensor: boot #{boot_count}")

    wifi = WifiService(WifiConfig.from_config(config))
    mqtt = MQTTClient.from_config(config, radio=wifi.adapter.radio)

    def publish_reading(now_ms):
        payload = json.dumps({"boot": boot_count, "celsius": read_celsius()})
        mqtt.publish(config.require("sensor.topic"), payload, qos=1)

    runner = Runner()
    runner.add(wifi)
    runner.add(mqtt)
    runner.add_periodic(publish_reading,
                        period_ms=config.require("sensor.publish_period_ms"))
    runner.run_until(lambda: wifi.state == WifiState.FAILED)   # run forever
```

The code carries only the logic.  Credentials live in the gitignored `secrets.toml`, and the knobs sit in a small file next to the code, so swapping brokers or changing the period is a config edit:

```toml
# projects/example_sensor/project_config.toml
[mqtt.broker]
host = "broker.hivemq.com"    # public test broker; swap for your own

[sensor]
topic = "chumicro/example/temperature"
publish_period_ms = 5000      # one reading every 5 s
```

Deploy it and watch it come up:

```console
$ python3 run.py deploy example_sensor --tail
...
sensor: boot #3
```

One JSON reading every five seconds arrives at the topic.  Two moments you can reproduce at your desk: pull your router's plug, and the board keeps running; plug it back in, and the readings return on their own (the wifi service and the MQTT client handle the reconnecting).  Press the board's reset button, and the next message says `boot #4`; the kvstore kept the count.

> This is a template.  Fork it (or clone it and `git init` fresh), rename the title above, and it's your repo.  The tooling refreshes its own files in place and never touches your projects.

## Before any of that: a board saying hello

The tooling can prove itself before you write or configure anything.  Two commands after cloning, with a board plugged in:

```console
$ python3 run.py setup              # one-time: builds .venv, installs the tooling
$ python3 run.py bootstrap --demo   # finds the port, registers the board, ships a hello
...
Hello from ChuMicro!
...
demo complete!
```

The demo brings its own payload, so it proves the whole chain (port, runtime, deploy, serial capture) in a few seconds, before you've written or configured anything.  From there, `python3 run.py library browse` opens a full-screen catalog of the chumicro libraries, and `python3 run.py deploy-example <library> <example>` ships any library's worked example to the board and drops you into the REPL to watch it run.

Getting from a fresh clone to the temperature-publishing board above is the ten steps below.  After that, [CONTRIBUTING.md](CONTRIBUTING.md) is the day-to-day guide (despite the name): the debugging table, how config reaches the device, health checks, and how to work with an AI agent here.

## Ten steps: zero to a board publishing MQTT

The code above is the shipped example, so the first deploy is a real one: wifi, MQTT, and storage all working before you write a line.

```bash
# 1. Get your copy.  ("Use this template" on GitHub works too.)
git clone --depth 1 https://github.com/ChuMicro/ChuMicro-Workbench-Template my-workbench
cd my-workbench
rm -rf .git && git init      # start your own history

# 2. Bootstrap the tooling: creates .venv, installs the host CLI,
#    materializes the gitignored workspace.yml + secrets.toml + devices.yml.
python3 run.py setup

# 3. (Skip if your board already runs CircuitPython or MicroPython.)
#    A factory-fresh or bootloader-mode board needs a runtime first:
python3 run.py install-firmware --method uf2 --url <firmware-image-url>
#    (--method esptool for ESP32-style boards.  --url is needed the
#    first time, before the board is registered; after that, images
#    can be derived from the registry entry.)

# 4. Plug the board in and register it.  The wizard finds the port,
#    probes CircuitPython vs MicroPython, and records it in devices.yml.
python3 run.py bootstrap

# 5. Put your wifi name + password in secrets.toml (gitignored, so
#    credentials never reach git).
$EDITOR secrets.toml

# 6. Look over the example's own settings.  The defaults publish to
#    broker.hivemq.com, a free public MQTT broker that needs no signup
#    (which also means anything you publish there is visible to anyone;
#    swap in your own broker when it matters).
$EDITOR projects/example_sensor/project_config.toml

# 7. Optional sanity check: print the merged config dict exactly as
#    the device will receive it.
python3 run.py dump-config example_sensor

# 8. Fetch the on-device libraries the example imports (each command
#    pulls the named library plus its chumicro dependencies):
python3 run.py library add chumicro_runner
python3 run.py library add chumicro_mqtt
python3 run.py library add chumicro_wifi
python3 run.py library add chumicro_kvstore

# 9. Deploy, then watch.  --tail follows the board's serial output for
#    30 seconds after the push (pass --tail SECONDS for more).
python3 run.py deploy example_sensor --tail

# 10. See it publish (the readings described up top), then make it
#     yours: scaffold your own project and repeat steps 8-9 for it.
mosquitto_sub -h broker.hivemq.com -t 'chumicro/example/temperature'
python3 run.py new my_project --from examples/wifi_only
```

Small print for the steps: the `mosquitto_sub` client comes with the mosquitto tools (`brew install mosquitto` / `apt install mosquitto-clients`), any MQTT client works; `library add` pulls from the stable channel (`--channel experimental` tracks pre-release snapshots); and in chumicro-dev mode step 8 is skipped entirely (see the dev-mode note under Digging deeper).

Start your own project by copying the example and tweaking it.  Once you've seen the wiring done by hand, `shared/face.py` packages the same bring-up as a reusable starter.

No board on hand yet?  Everything that doesn't touch hardware (`setup`, `new`, the config commands, lint, the test tooling) runs on the laptop alone, so you can build the workbench and write your project first, then plug in.

Prerequisites, which the wizard will also tell you about: Python 3.11+ on the laptop, and a board running CircuitPython or MicroPython (step 3 covers a fresh one).  RP2040 / RP2350 and ESP32-family boards are the well-worn paths; other boards those runtimes support generally work with a manually supplied firmware image.  `setup` is self-bootstrapping: it creates `.venv/`, installs `chumicro-workspace`, and re-enters the venv on every later command, so you never activate anything.  If `setup` itself fails, the usual causes are an older Python, no network to PyPI, or a half-built venv from an interrupted run; delete `.venv/` and rerun, it's idempotent.

Prefer explicit registration over the wizard?  `python3 run.py add-device my-board --address /dev/cu.usbmodem1101 --runtime micropython` (a macOS port path; Linux boards show up as `/dev/ttyACM0` or `/dev/ttyUSB0`, Windows as `COM3`-style names, and `python3 run.py discover` lists what's visible).

Once you have more than one project or board, name the target: `python3 run.py deploy <project>` picks the project (the bare form only works while exactly one exists, and the shipped `example_sensor` means your first scaffold is already the second), and `--device <id>` picks the board.  `python3 run.py projects` and `python3 run.py devices` list what's registered.

For the full workflow walkthrough, including multi-board and multi-project flows, see the [chumicro-workspace hosted docs](https://chumicro.github.io/ChuMicro/workspace/stable/) (the version selector in the docs header reaches the pre-release `experimental/` docs).

<details>
<summary>What a deploy does to the board's filesystem (and how to opt out)</summary>

Deploys are clean-slate by default: each one reconciles the board's filesystem to the project's payload.  Anything that isn't the new payload or a device-required file (`boot.py`, `boot_out.txt`, the persistent kvstore blob) is removed, and a board-resident `settings.toml` is evicted because it competes with config-driven wifi.  This means hand-installing libraries with `circup` or `mip` and then running a default deploy can wipe them.  Either let `library add` + `deploy` own the board's `/lib`, or pass `--no-wipe` to leave hand-managed files in place.

</details>

## What the tooling does for you

The ten steps are the happy path.  Here is what the tooling does around it:

- **A failed deploy tells you the fix.**  The tooling classifies fourteen known failure modes and prints ordered recovery steps for the one you hit.  When the serial port is busy, it runs `lsof` for you, names the process holding the port (Mu, Thonny, a stale `mpremote`), and prints the exact `kill <pid>` to paste.
- **Mistakes fail on the laptop, before any bytes reach the board.**  The deployer walks your imports and refuses to ship code that would `ImportError` on first boot, naming the file and the missing module.  It also catches `async def run()` (which would boot a board that silently does nothing) and a hard reset in the boot path (which would crash-loop it), each with the fix spelled out.
- **You write `app.py`; the boot file writes itself.**  A project shipping `run()` gets a synthesized three-line `code.py` (CircuitPython) or `main.py` (MicroPython) on every deploy, matched to the board's runtime.
- **Only what you import ships.**  The deployer follows your code's imports through `shared/` helpers, workspace libraries, and packages, and stages exactly the files your program reaches.  `deploy --dry-run` prints the full file map with sizes before anything moves.
- **Iterate in RAM, ship to flash.**  `deploy --deploy-mode ram` runs your code over the serial cable with no flash writes at all, so a hundred edit-run cycles cost the board nothing and a reset leaves it clean.  When a project genuinely needs flash (a heavy library declares it, or the payload carries data files), the deploy switches itself and prints why.
- **The board is exactly your project.**  A deploy makes the board's filesystem match your payload, so a stale module from last week is gone before today's run starts.  `boot.py` and the persistent kvstore survive, and a stray `settings.toml` is removed before it can override your wifi config.
- **Watching is part of deploying.**  `deploy <name> --tail` streams the serial output after the push, paints tracebacks red, and exits non-zero if one appears, which makes "does it actually run on hardware" a one-line CI check.
- **Your pytest suite runs on the actual board.**  `run.py test projects/<name>/functional_tests` stages the tests onto the device, runs them in the device runtime, and reports each one as a normal pytest line.  Test fixtures can spin up a real MQTT broker, TCP/UDP/TLS echo servers, and hand the board your LAN address.  With nothing plugged in, the same suites can run in a real MicroPython or CircuitPython interpreter on the laptop, with a small-board heap ceiling so memory pressure stays honest.
- **Tab completion against the board itself.**  `run.py repl` completes against the board's live `dir()`, keeps a persistent history per board, hands multi-line blocks to `$EDITOR`, paints tracebacks red, exits without rebooting the board, and reconnects across an unplug.
- **One board or a fleet.**  Map projects to boards in `workspace.yml`'s `deploy_targets:` and `deploy --all-projects` walks the whole matrix; `--all-devices` fans one project to every registered board.
- **Firmware included.**  `install-firmware` (alias `upgrade-firmware`) flashes CircuitPython or MicroPython over UF2 or esptool, deriving the right image from the board's registry entry, so you rarely hunt for a download URL.
- **Libraries you can pin, float, and edit.**  `library add` fetches a library plus its dependencies from a version-pinned channel (stable or experimental, chosen per library, switchable later).  Your local edits to a fetched library are safe: a re-fetch saves a timestamped backup first, and a marker file freezes a library entirely.
- **Config you can see.**  `dump-config` prints the exact merged dict a project will receive; `config-validate` checks every project's config against the requirements the libraries themselves declare, before a missing key becomes a boot-time crash.

[CONTRIBUTING.md](CONTRIBUTING.md) covers each of these with the exact commands and flags.

## Why a workbench instead of editing on the device

When you mount a CircuitPython board and edit files on the `CIRCUITPY` drive, every save writes to the board's FAT filesystem.  Three things go wrong over time:

* **Flash wear.**  Boards typically have 2 to 4 MB of flash with modest erase-cycle budgets.  Save-on-every-keystroke editing eats through it faster than you'd think.
* **Corruption.**  FAT isn't crash-safe.  An interrupted write (host suspending, cable jiggling, board resetting mid-save) leaves files truncated, and worst case the drive stops mounting.
* **Lost work.**  When the drive does hiccup, files you thought were saved may be gone.

A workbench keeps your code out of that blast radius.  You edit and version it like any Python project, run lint and tests against it on your laptop, and deploy it to the board deliberately.  A deploy makes the board exactly match your project, atomically; while you iterate, RAM mode runs your code with no flash writes at all.

## Bring an AI coding agent

This workbench is built so an agent can do the driving.  [AGENTS.md](AGENTS.md) gives it the rules (which files it may edit, which the tooling owns), and the skill files under `.github/skills/` give it step-by-step procedures for the workflows that eat an evening: registering a board, flashing firmware onto one in an unknown state, deploying and debugging.

So this is a realistic prompt here: "I just plugged in a board and I don't know what state it's in.  Get CircuitPython onto it and set up a project that blinks the LED."  The agent can discover the port, flash the runtime, register the board, scaffold the project, deploy it, and read the serial output back to you; every step is a `run.py` command whose failure messages name the fix.  [CONTRIBUTING.md](CONTRIBUTING.md#working-with-an-ai-agent) has patterns for doing this without losing your bearings.

## Layout

- `projects/<name>/`: your projects.  Each is a directory with an `app.py` defining `def run()` plus a `project_config.toml` for its knobs.  Names may be nested (`projects/garage/sensors/door_open/`); `python3 run.py projects` shows the tree.
  - `projects/_template/`: the blank project copied by `python3 run.py new`.
  - `projects/example_sensor/`: a worked example (wifi to MQTT heartbeat with a persistent boot counter).  The ten steps above deploy it.
- `examples/`: read-only worked demos.  Scaffold a real project from one with `python3 run.py new <name> --from examples/<example>`; [`examples/README.md`](examples/README.md) is the index.  This folder is tool-owned: `python3 run.py update` rewrites it from upstream.
- `devices.yml`: your board registry, gitignored, created by `setup`.  Managed by the device commands (`bootstrap`, `add-device`, `rename`, `probe`), so comments and key order survive edits.
- `workspace.yml`: gitignored, created by `setup`.  Host-only workbench settings (`deploy_targets`, `quality`), plus two tool-managed blocks: the `libraries:` table `library add` maintains and, in dev mode, the `library_sources:` block `setup` re-syncs.  Never reaches a device.
- `secrets.toml`: gitignored, created by `setup`.  Workbench-wide credentials (wifi password, broker auth) and device defaults that flow into the deployed config.  Per-project `project_config.toml` values override it.
- `quality.toml`: committed.  The workbench's lint and coverage gates, shared by every clone of your repo; `workspace.yml`'s `quality:` block overrides it per machine.
- `shared/`: helper modules shared between projects.  Drop `foo.py` here and any project can `from foo import bar`; the deploy ships it to the board alongside the libraries.  See [`shared/README.md`](shared/README.md).
- `packages/`: gitignored drop area for third-party Python source trees your projects import on the device.  See [`packages/README.md`](packages/README.md).
- `libraries/`: not present on a fresh clone.  `python3 run.py library add <name>` creates it and fetches the on-device chumicro libraries your projects import; `python3 run.py new --library <name>` scaffolds your own library packages there.  The fetched trees are your clone's copy of upstream code, re-fetchable at any time, so commit them for a self-contained repo or add `libraries/` to your `.gitignore` if you'd rather re-fetch.

## Digging deeper

<details>
<summary>Installing libraries without the workbench tooling (air-gapped or custom-registry rigs)</summary>

You can install chumicro libraries onto the board directly with the runtime's own package manager instead of `library add` + `deploy` (both resolve transitive chumicro dependencies automatically):

```bash
# CircuitPython: bundle-add once, then install by name
circup bundle-add ChuMicro/ChuMicro-Bundle
circup install chumicro-wifi chumicro-mqtt chumicro-runner \
               chumicro-kvstore chumicro-config

# MicroPython: one mip install per library
mpremote connect /dev/cu.usbmodem1101 mip install \
    github:ChuMicro/ChuMicro-Bundle/chumicro_wifi
mpremote connect /dev/cu.usbmodem1101 mip install \
    github:ChuMicro/ChuMicro-Bundle/chumicro_mqtt
# ... repeat per library
```

(These are the stable-channel bundle paths, matching the channel this
template pins.  For pre-release snapshots swap in
`ChuMicro/ChuMicro-Bundle-Experimental`, and register only one bundle
per machine, never both.)

`circup` uses hyphens (`chumicro-wifi`); `mip` uses the underscore import name (`chumicro_wifi`).  Files land at `/lib/chumicro_<name>/` either way, the same place a `deploy` writes them.  Remember the clean-slate rule above: a later default `deploy` removes hand-installed libraries unless you pass `--no-wipe`.

</details>

<details>
<summary>Bring your own transport: slimming a deploy that doesn't need <code>chumicro-sockets</code></summary>

If your project supplies its own socket (an upstream library wrapper, stdlib `socket.socket`, a hand-rolled fake) instead of letting the library default to `chumicro-sockets`, declare that at the top of your project's `app.py` and the deployer filters the default factory submodule and its `chumicro-sockets` closure out of the on-device file set:

```python
# projects/<name>/app.py
__chumicro_skip_factories__ = (
    "sockets_factory",                          # family form: the sockets_factory stem
    "chumicro_sockets.sockets_factory",         # exact form: the module in full
)
```

Two forms: a bare stem (`"sockets_factory"`) matches the shared `chumicro_sockets.sockets_factory` module by its stem; a dotted path names it in full.  There is one shared factories module now, so both forms resolve to it.

Typos and dead skips both surface loudly.  An unmatched entry fails the deploy with the discovered families named in the message; an entry whose parent library is never imported prints a dead-skip warning so you can prune it.

Calling a library's `from_config(...)` when its factory submodule is missing (skipped at deploy time, or absent from a partial `circup` / `mip` install) raises `RuntimeError` naming the bypass kwarg.  Every networked library takes the same one, `transport_factory=` (mqtt, requests, websockets, http_server, ntp); mqtt and ntp also accept a pre-built `socket=`.  Misuse surfaces at construction time instead of misbehaving silently.

The mechanism only applies to deploys driven through this workbench's `python3 run.py deploy`.  `circup` and `mip` resolve dependencies on their own; install through them directly and the on-device file set is whatever they decide.

</details>

<details>
<summary>ChuMicro-dev mode: co-developing the chumicro libraries alongside the workbench</summary>

Co-developing chumicro libraries or `chumicro-workspace` from a sibling source checkout (or a fork)?  Drop a `chumicro-dev.toml` next to `run.py`:

```toml
chumicro_path = "../chumicro"
```

When the file is present, `python3 run.py setup` pip-installs every library and host-tool package found in your chumicro checkout as editable, before installing the workbench's own dependencies.  Edits to your chumicro checkout flow into the workbench immediately; no rebuild, no republish.  Delete the file to revert to the PyPI install path.  `chumicro-dev.toml` is gitignored, since contributors keep their checkouts in different places.

In dev mode, `setup` also maintains a `library_sources:` block in `workspace.yml`, mapping every chumicro library in the sibling checkout to its `src/` directory.  That block is tool-owned: every `setup` re-syncs it to match the checkout, so don't hand-edit it (the rest of `workspace.yml` is yours).  `deploy --import-graph` reads the block and ships the on-device libraries straight from your local checkout, with no `circup` / `mip` round-trip and no `library add` step.

</details>

## License

MIT, for the template and everything it scaffolds.  See [LICENSE](LICENSE).
