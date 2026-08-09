# my-workspace

A clone-and-go project layout for boards running [ChuMicro](https://chumicro.github.io/ChuMicro/) libraries.  Your code lives on your laptop, in version control, with your editor and your tests; the tooling ships it to the board when you ask.  Recommended even if you only have one project on one board.

> Rename this directory and this README's title to whatever you want to call your workspace.  This is your repo now.

After the quickstart below, read [CONTRIBUTING.md](CONTRIBUTING.md).  Despite the name, it's the day-to-day user guide: the debugging table, how config reaches the device, RAM vs flash deploys, health checks, and how to work with an AI agent here.

## Why a workspace instead of editing on the device

When you mount a CircuitPython board and edit files on the `CIRCUITPY` drive, every save writes to the board's FAT filesystem.  Three things go wrong over time:

* **Flash wear.**  Boards typically have 2 to 4 MB of flash with modest erase-cycle budgets.  Save-on-every-keystroke editing eats through it faster than you'd think.
* **Corruption.**  FAT isn't crash-safe.  An interrupted write (host suspending, cable jiggling, board resetting mid-save) leaves files truncated, and worst case the drive stops mounting.
* **Lost work.**  When the drive does hiccup, files you thought were saved may be gone.

A workspace keeps your code out of that blast radius.  You edit and version it like any Python project, run lint and tests against it on your laptop, and deploy it to the board deliberately.  A deploy makes the board exactly match your project, atomically; while you iterate, RAM mode runs your code with no flash writes at all.

## Quickstart

```bash
# Option A: clone this template
git clone --depth 1 https://github.com/ChuMicro/ChuMicro-Workspace-Template my-workspace
cd my-workspace
rm -rf .git && git init                 # start your own history

# Option B: GitHub UI -> "Use this template" -> clone the resulting repo

# Then, with the workspace cloned and a board plugged in:
python3 run.py setup                    # creates .venv, installs the tooling, materializes workspace.yml + secrets.toml + devices.yml
python3 run.py bootstrap                # wizard: finds the port, detects CircuitPython vs MicroPython, registers the board
python3 run.py new my_project --from examples/wifi_only   # scaffolds projects/my_project/ from the wifi starter
# Edit secrets.toml (your wifi name + password); tweak projects/my_project/{project_config.toml, app.py} if you like
python3 run.py library add chumicro_wifi   # once per chumicro library your app imports...
python3 run.py library add chumicro_runner # ...including chumicro_runner, which drives the main loop
python3 run.py deploy my_project
```

No board on hand yet?  Everything except `bootstrap` and `deploy` works without one: `setup`, `new`, the config commands, and the test tooling all run on the laptop alone, so you can set up the workspace and write your project first and plug in hardware later.

If `setup` itself fails, the usual causes are a Python older than 3.11 (`python3 --version`), no network to reach PyPI, or a half-built venv from an interrupted run; delete `.venv/` and rerun `python3 run.py setup`, which is safe and idempotent at any time.

Two prerequisites the wizard will tell you about if they're missing: the board must already run CircuitPython or MicroPython (`python3 run.py install-firmware --method uf2`, or `--method esptool` for ESP32-style boards, can flash one onto a fresh board), and Python 3.11+ on the laptop.  Hardware-wise that means RP2040 / RP2350 and ESP32-family boards are the well-worn paths (they're what the chumicro libraries target and what the firmware tooling auto-derives images for); other boards those runtimes support generally work with a manually supplied firmware image.  `setup` is self-bootstrapping beyond that: it creates `.venv/`, installs `chumicro-workspace`, and re-enters the venv on every later command, so you never activate anything.

Prefer explicit registration over the wizard?  `python3 run.py add-device my-board --address /dev/cu.usbmodem1101 --runtime micropython` (that's a macOS port path; on Linux boards show up as `/dev/ttyACM0` or `/dev/ttyUSB0`, on Windows as `COM3`-style names, and `python3 run.py discover` lists what's visible).

Once you have more than one project or board, name the target: `python3 run.py deploy <project>` picks the project (the bare form only works while exactly one exists, and the shipped `example_sensor` means your first scaffold is already the second), and `--device <id>` picks the board.  `python3 run.py projects` and `python3 run.py devices` list what's registered.

For the full workflow walkthrough, including multi-board and multi-project flows once you've outgrown a single project, see the [chumicro-workspace hosted docs](https://chumicro.github.io/ChuMicro/workspace/stable/) (use the version selector in the docs header to read the pre-release `experimental/` docs instead).

<details>
<summary>What a deploy does to the board's filesystem (and how to opt out)</summary>

Deploys are clean-slate by default: each one reconciles the board's filesystem to the project's payload.  Anything that isn't the new payload or a device-required file (`boot.py`, `boot_out.txt`, the persistent kvstore blob) is removed, and a board-resident `settings.toml` is evicted because it competes with config-driven wifi.  This means hand-installing libraries with `circup` or `mip` and then running a default deploy can wipe them.  Either let `library add` + `deploy` own the board's `/lib`, or pass `--no-wipe` to leave hand-managed files in place.

</details>

## Bring an AI coding agent

This workspace is built so an agent can do the driving.  [AGENTS.md](AGENTS.md) gives it the rules (which files it may edit, which the tooling owns), and the skill files under `.github/skills/` give it step-by-step procedures for the workflows that eat an evening: registering a board, flashing firmware onto one in an unknown state, deploying and debugging.

So this is a realistic prompt here: "I just plugged in a board and I don't know what state it's in.  Get CircuitPython onto it and set up a project that blinks the LED."  The agent can discover the port, flash the runtime, register the board, scaffold the project, deploy it, and read the serial output back to you; every step is a `run.py` command whose failure messages name the fix.  [CONTRIBUTING.md](CONTRIBUTING.md#working-with-an-ai-agent) has patterns for doing this without losing your bearings.

## Layout

- `projects/<name>/`: your projects.  Each is a directory with an `app.py` defining `def run()` plus a `project_config.toml` for its knobs.  Names may be nested (`projects/garage/sensors/door_open/`); `python3 run.py projects` shows the tree.
  - `projects/_template/`: the blank project copied by `python3 run.py new`.
  - `projects/example_sensor/`: a worked example (wifi to MQTT heartbeat with a persistent boot counter).  See the walkthrough below.
- `examples/`: read-only worked demos.  Scaffold a real project from one with `python3 run.py new <name> --from examples/<example>`; [`examples/README.md`](examples/README.md) is the index.  This folder is tool-owned: `python3 run.py update` rewrites it from upstream.
- `devices.yml`: your board registry, gitignored, created by `setup`.  Managed by the device commands (`bootstrap`, `add-device`, `rename`, `probe`), so comments and key order survive edits.
- `workspace.yml`: gitignored, created by `setup`.  Host-only workspace settings (`library_sources`, `deploy_targets`, `quality`).  Never reaches a device.
- `secrets.toml`: gitignored, created by `setup`.  Workspace-wide credentials (wifi password, broker auth) and device defaults that flow into the deployed config.  Per-project `project_config.toml` values override it.
- `quality.toml`: committed.  The workspace's lint and coverage gates, shared by every clone of your repo; `workspace.yml`'s `quality:` block overrides it per machine.
- `shared/`: helper modules shared between projects.  Drop `foo.py` here and any project can `from foo import bar`; the deploy ships it to the board alongside the libraries.  See [`shared/README.md`](shared/README.md).
- `packages/`: gitignored drop area for third-party Python source trees your projects import on the device.  See [`packages/README.md`](packages/README.md).
- `libraries/`: not present on a fresh clone.  `python3 run.py library add <name>` creates it and fetches the on-device chumicro libraries your projects import; `python3 run.py new --library <name>` scaffolds your own library packages there.  The fetched trees are your clone's copy of upstream code, re-fetchable at any time, so commit them for a self-contained repo or add `libraries/` to your `.gitignore` if you'd rather re-fetch.

## Worked example: `example_sensor`

The shipped `projects/example_sensor/` exercises the full stack: wifi, sockets, MQTT, persistent storage, and the deploy tooling.  Boot to first heartbeat on a plugged-in board:

```bash
# 1. Bootstrap the workspace (one-time, after clone)
python3 run.py setup

# 2. Tell the workspace about your board (or use the explicit add-device form)
python3 run.py bootstrap

# 3. Fill in your wifi credentials (the file is gitignored; open and edit)
$EDITOR secrets.toml   # set [wifi] ssid + password to your network's name and password

# 4. Look over the project's own settings.  The defaults publish to a
#    free public MQTT broker, so you can leave this file as-is for a
#    first run.  (An MQTT broker is a small server that relays
#    messages between devices; broker.hivemq.com is public and needs
#    no signup, which also means anything you publish there is
#    visible to anyone.  Swap in your own broker when it matters.)
$EDITOR projects/example_sensor/project_config.toml

# 5. Optional: sanity-check the merged config before deploying.
#    Prints the dict that ends up on the device.
python3 run.py dump-config example_sensor

# 6. Pull the chumicro libraries this project uses into the workspace.
#    `library add <name>` fetches the named library plus its chumicro
#    dependencies; the deploy in step 7 ships the ones the project
#    imports to the board's /lib/ from the stable channel
#    (pass --channel experimental to track pre-release snapshots).
#    (Skip this step entirely in chumicro-dev mode; see the note below.)
python3 run.py library add chumicro_runner
python3 run.py library add chumicro_mqtt
python3 run.py library add chumicro_wifi
python3 run.py library add chumicro_kvstore

# 7. Deploy, then watch. --tail follows the board's serial output
#    after a successful deploy (30 seconds by default; pass
#    --tail SECONDS to change), then exits.
python3 run.py deploy example_sensor --tail
```

Subscribe to the topic from any MQTT client and you should see one JSON message every 5 seconds carrying the boot counter, the on-board temperature reading, and a sequence number.  With the `mosquitto` tools installed (`brew install mosquitto` / `apt install mosquitto-clients`):

```bash
mosquitto_sub -h broker.hivemq.com -t 'chumicro/example/temperature'
```

Reset the board and the boot counter increments: `chumicro-kvstore` persisted it across the reset.

`projects/example_sensor/app.py` is short on purpose.  It's the reference for wiring `WifiService` + `MQTTClient` + `KVStore` into a `Runner`; copy and tweak rather than starting from scratch.

<details>
<summary>Installing libraries without the workspace tooling (air-gapped or custom-registry rigs)</summary>

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

The mechanism only applies to deploys driven through this workspace's `python3 run.py deploy`.  `circup` and `mip` resolve dependencies on their own; install through them directly and the on-device file set is whatever they decide.

</details>

<details>
<summary>ChuMicro-dev mode: co-developing the chumicro libraries alongside the workspace</summary>

Co-developing chumicro libraries or `chumicro-workspace` from a sibling source checkout (or a fork)?  Drop a `chumicro-dev.toml` next to `run.py`:

```toml
chumicro_path = "../chumicro"
```

When the file is present, `python3 run.py setup` pip-installs every library and workbench package found in your chumicro checkout as editable, before installing the workspace's own dependencies.  Edits to your chumicro checkout flow into the workspace immediately; no rebuild, no republish.  Delete the file to revert to the PyPI install path.  `chumicro-dev.toml` is gitignored, since contributors keep their checkouts in different places.

In dev mode, `setup` also maintains a `library_sources:` block in `workspace.yml`, mapping every chumicro library in the sibling checkout to its `src/` directory.  That block is tool-owned: every `setup` re-syncs it to match the checkout, so don't hand-edit it (the rest of `workspace.yml` is yours).  `deploy --import-graph` reads the block and ships the on-device libraries straight from your local checkout, with no `circup` / `mip` round-trip and no `library add` step.

</details>

## License

MIT, for the template and everything it scaffolds.  See [LICENSE](LICENSE).
