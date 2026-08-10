# Working in this workbench

Welcome.  This file is for you, the human who just cloned the
template, and for any AI coding agent helping you.

The [README](README.md) is the 30-second quickstart.  This file is
the "now what?" guide: workflows, debugging, where to look up help,
and how to collaborate with an agent without losing your bearings.

If you're an agent: start with [AGENTS.md](AGENTS.md), the distilled
rules and commands for editing this workbench.  Skim this file too so
you understand the human's mental model.

## What this workbench is

A ChuMicro project workbench ships as a Git repo you clone (this
template) and edit in place.  Conceptually it has three pieces:

- **`projects/<name>/`**: your applications.  Each project is a
  directory with an `app.py` (defining `def run(): ...`) plus a
  `project_config.toml` for its knobs.  One project, one deployable
  program.
- **`devices.yml`**: your board registry.  One entry per physical
  board you deploy to.  Tool-managed by `add-device` / `rename` /
  `probe`, so comments and key order survive every edit.
- **`run.py`**: the workbench dispatcher.  Every command goes
  through it: `python3 run.py setup`, `python3 run.py deploy`, and
  so on.  `setup` bootstraps a `.venv`; every later command
  re-enters it automatically.

You write code in `projects/`.  The tooling owns deploys, REPL,
firmware flashing, config merging, and the boot shim (the tiny boot
file it installs on the device to call your `run()`).

## Day one: setup

```bash
git clone --depth 1 https://github.com/ChuMicro/ChuMicro-Workbench-Template my-workbench
cd my-workbench
rm -rf .git && git init       # start your own history
python3 run.py setup          # creates .venv, materializes gitignored workspace.yml + secrets.toml + devices.yml, installs chumicro-workspace
```

`setup` is idempotent.  Re-run it any time after pulling template
updates; it won't overwrite anything you've edited, with one
documented exception: in chumicro-dev mode, the `library_sources:`
block of `workspace.yml` is tool-owned and re-synced on every
`setup` (the rest of the file is yours).

If you're co-developing the underlying ChuMicro libraries from a
sibling clone, see the README's "ChuMicro-dev mode" section.

## Day to day: making and shipping projects

A typical session has four moves:

```bash
# 1. Register a board (once per physical board).  Use `bootstrap`
#    if you want a wizard to walk pick-port, probe, and register
#    in one command.
python3 run.py add-device my-board --address /dev/cu.usbmodem1101 --runtime micropython

# 2. Scaffold a new project
python3 run.py new my_sensor    # creates projects/my_sensor/ from projects/_template/

# 3. Edit secrets.toml (wifi credentials) and projects/my_sensor/{app.py, project_config.toml}.

# 4. Deploy, then watch.  --tail deploys, then follows the board's
#    serial output for 30 seconds (pass --tail SECONDS for a
#    different window).
python3 run.py deploy my_sensor --tail
```

(The `--address` above is a macOS-style port path.  Linux boards show
up as `/dev/ttyACM0` or `/dev/ttyUSB0`, Windows as `COM3`-style names;
`python3 run.py discover` lists what's visible.)

`python3 run.py status` (or the stricter `doctor`) is a useful
between-step sanity check.  It surfaces common mistakes before a
deploy: malformed `workspace.yml` / `secrets.toml`, an `app.py`
missing its `run()` definition, and so on.

With several boards, map which projects deploy where in
`workspace.yml` and drive them together:

```yaml
deploy_targets:
  garage/heater: pico-w-1          # one target can stay terse
  bedroom_sensor: [esp32-a, esp32-b]
```

`python3 run.py deploy <project>` picks the project's first
registered target; `deploy --all-projects` walks the whole mapping.

The shipped `projects/example_sensor/` is the reference project.
It wires `chumicro-wifi` + `chumicro-mqtt` + `chumicro-kvstore`
into a `Runner`.  Start your own projects by copying and tweaking it.

### Naming projects

Project directory names must be valid Python identifiers: letters,
digits, underscores; no hyphens, no dots, no leading digit.  The
runtime imports `projects.<your-name>.app`, so a hyphen breaks
deploy.  `python3 run.py new` checks this up front and fails fast
with a clear message.

Nested layouts are first-class.  Slash- or dotted-form names land
under a parallel namespace tree:

```bash
python3 run.py new garage/sensors/door_open
python3 run.py new garage.sensors.door_open      # dotted form, same effect
```

Each path segment is validated independently against the same
identifier rules, and intermediate namespace directories
(`projects/garage/`, `projects/garage/sensors/`) are auto-created with
empty `__init__.py` markers.  `python3 run.py projects` shows the tree
(`--flat` switches to one line per project in slash form).

### Scaffolding from an example

Instead of starting from the blank `projects/_template/`, scaffold
from any directory under `examples/`:

```bash
python3 run.py new garage/heater --from examples/wifi_only
```

That copies `examples/wifi_only/`'s tree into
`projects/garage/heater/`.  The example folder itself is read-only
(tool-owned, refreshed on `update`); your edits live under `projects/`.

### Workbench health checks

Two commands surface common pre-deploy mistakes:

```bash
python3 run.py status     # one-line-per-check snapshot
python3 run.py doctor     # stricter: adds Python version + AST scan for run()
```

`status` catches a missing `devices.yml` and parses `workspace.yml` /
`secrets.toml` for shape errors.  `doctor` adds the Python version
check plus a per-project `app.py` scan ("did you forget the
`def run()`?").

`deploy` runs the same fast checks `status` does as a gate.
ERROR-level findings (malformed YAML files) abort before sending bytes
to the device; WARN-level findings (no devices registered) print but
proceed.  Pass `deploy --skip-health-check` when you've already
validated the workbench state externally (CI flows, scripted runs).

Registry housekeeping, for when boards come and go:
`remove-device <id>` deletes an entry (it asks first, because your
description and settings can't be rebuilt from a probe);
`reset-device <id>` re-probes the connected board and rewrites the
entry from the silicon, which is the *replace* counterpart to
`add-device --force`'s in-place *update*; `probe` prints what a
connected board reports about itself.  Every command also accepts
`--workspace-dir` for CI runners and IDE tasks that don't start from
the workbench root.

### How config flows from your edits to the device

Every project receives a runtime config at boot.  That config is the
deep-merge of two gitignored host-side sources, flattened to dotted
keys (`wifi.ssid`, `mqtt.broker.host`) for the wire:

```
secrets.toml ──────────────────► projects/<name>/project_config.toml
  (gitignored: workbench-wide       (versioned with your project;
   credentials + device defaults     per-project knobs like sample
   in one place)                     period, mqtt topic, sensor pins)

                            ▼
                 deep merge                     (higher-precedence layer wins at any key;
                            │                    lists replace wholesale; dicts recurse)
                            ▼
                 flatten                        (nested tables become dotted keys
                            │                    like "mqtt.broker.host")
                            ▼
                 serialize                      (one compact file on the wire)
                            │
                            ▼
              /runtime_config.msgpack on device
                            │
                            ▼
                     chumicro_config.config     (your app reads it back as a flat dict)
```

Use `python3 run.py dump-config <project>` to print the merged, flat
dict your project would receive without actually deploying.  Handy
when you're debugging which layer a key landed in or whether an
overlay deep-merged the way you expected.

`python3 run.py config-validate [project...]` goes one step further:
it checks each project's merged config against the requirements the
chumicro libraries in its import graph declare, and names any missing
key by the exact dotted name the runtime accessor will ask for.  Run
it with no arguments to sweep every project; it makes a fast CI gate.

### Quality gate

`python3 run.py preflight` runs `lint` then `test` as a single sanity
gate.  The gates live in two layers:

- **`quality.toml`** (committed, at the workbench root): the policy
  that travels with your repo, so every clone enforces the same bar.

  ```toml
  coverage_threshold = 70      # example override; the shipped default is 85

  [lint]
  enabled = true               # false skips lint entirely
  select = ["E", "F", "I"]     # ruff rule set
  ```

- **`workspace.yml`'s `quality:` block** (gitignored): per-machine
  overrides.  Any key set here wins over `quality.toml`, useful for
  loosening a gate locally without changing the project's policy.

Both `lint` and `test` are also runnable on their own.

`run.py lint` also runs `chumicro-checks`, a small extra rule set
from the chumicro tooling.  The one you might notice is CHU008, which
flags references that belong to the upstream chumicro repo and don't
resolve in a workbench.  See `pyproject.toml`'s
`[tool.chumicro-checks]` block to opt out of rules.

### Library-shaped code: `shared/` vs `libraries/`

Both hold code your projects can import.  Pick by weight:

| Want to ship... | Drop it under | Imports look like | Notes |
|---|---|---|---|
| A 50-line helper your projects share | `shared/foo.py` | `from foo import bar` | No tests, no version, no scaffolding.  See [`shared/README.md`](shared/README.md). |
| A full chumicro-style library you might publish someday | `libraries/<name>/` (via `python3 run.py new --library <name>`) | `import <name>` | Gets `src/`, `tests/`, `docs/`, `examples/`, `pyproject.toml`, `VERSION`.  The folder appears the first time you scaffold one, or the first time `library add` fetches an upstream library into it. |
| A third-party package source tree | `packages/<name>/` | `import <name>` | Gitignored drop area.  See [`packages/README.md`](packages/README.md). |

The import-graph search path resolves explicit `library_sources:`
overrides, then `shared/`, then every `libraries/<name>/src/`
(auto-discovered), then `packages/`.  Steps with no folder on disk
skip silently, so a workbench with no `libraries/` pays nothing.

### Managing fetched libraries

`library add <name>` starts a lifecycle:

- `library list` shows every curated library with its channel and
  version; `library browse` is a full-screen catalog you can
  multi-select from (interactive terminals only).
- Each library tracks either a pinned version (`add --version <tag>`)
  or floating `HEAD` (`add --floating`); `library update` re-fetches
  the floating ones and leaves pins alone, which is what makes it
  predictable.
- `library switch-channel <name> {stable,experimental}` moves one
  library between the two snapshot channels.
- `library remove <name>` uninstalls the tree but records the
  decision, so a later `update` won't quietly re-fetch it;
  `library forget <name>` erases the record too.
- Your edits to a fetched tree are never clobbered: a re-fetch parks
  the old tree under `_library-backups/` first, and dropping a
  `.chumicro-local` file in a library freezes it entirely until you
  delete the marker.

`python3 run.py new --workbench <name>` is the host-only sibling.  It
scaffolds the same shape with a host-tool pyproject (CLI entry point,
no cross-runtime concerns) under `workbench/<name>/`.  Use it for
tools you drive from the laptop.  (The flag and output directory keep
upstream chumicro's name for its host-tool package tier, an older,
unrelated use of "workbench".)

### Device modes: RAM vs flash

Every deploy chooses a mode:

- **Flash mode** (`deploy_mode: flash`, the default): files land on
  the device's flash.  State persists, the device boots standalone,
  deploys are atomic (write-then-rename), and the runtime behavior
  matches a production deploy.  Use it for project deploys, examples,
  and most functional tests.
- **RAM mode** (`deploy_mode: ram`): the device executes from
  host-mounted source.  Fast iteration and no flash wear, but state
  doesn't persist across resets and the runtime profile differs from
  a real deploy (heavier libraries can run out of memory in RAM mode
  where they fit fine in flash).  Best for single-library tests and
  quick scratch experiments.

Choose the mode with the `deploy_mode:` field on a device's entry in
`devices.yml`, or for one run with `deploy <project> --deploy-mode ram`.

> **Auto-switch when libraries declare `requires_flash`.**  Heavier
> libraries declare `[tool.chumicro] requires_flash = true` in their
> `pyproject.toml` (currently mqtt, requests, http_server, and
> websockets).  When you deploy a project that imports one of those
> and the run's mode is `ram`, the deployer auto-switches to flash
> for that run and prints why.  A payload carrying non-`.py` data
> files auto-switches the same way (RAM mode can't carry assets).
> `--force-deploy-mode ram` bypasses the auto-switch (rare; for
> debugging that behavior itself).

Three levels of destructiveness on a flash deploy: `--no-wipe`
(additive: only the entrypoint, state files, and `/lib` are
reconciled, everything you hand-placed survives), the default
(clean-slate: the board becomes exactly your payload, with `boot.py`,
`boot_out.txt`, and the kvstore blob preserved), and `--wipe` (full
filesystem erase first, keep set included; the standalone
`reset-board` does the same wipe without a redeploy).  `deploy
--dry-run` prints the file map (path, size, category) any of them
would ship, which is also the quickest answer to "what does deploy
actually do".  In CI, `deploy <name> --tail` exits non-zero when the
tailed output shows a traceback; add `--no-fail-on-traceback` when
you only want the log.

## Debugging: when a deploy doesn't work

The deploy tooling classifies most failure modes into a precise
message that points at a fix: mount the CIRCUITPY drive, swap the
cable, install firmware, plug in the right board.  Start with the
message; it usually names the next move.

Common patterns:

| Symptom | Likely cause | First thing to try |
|---|---|---|
| `port not found` / `failed to access` | board unplugged or claimed by another process | `python3 run.py discover` to list what's actually visible |
| `Resource busy` opening the port | another program holds the serial port | the failure output names the holding process and prints the `kill <pid>`; `python3 run.py doctor` runs the same check on every registered port |
| CIRCUITPY won't mount (macOS) | the FSKit volume service is wedged | `python3 run.py doctor --fix-fskit-wedge` (guarded: it refuses to run on a healthy system, where it would do damage) |
| board filesystem corrupted (`Invalid argument` on delete) | torn FAT directory entries; in-place repair fails | `python3 run.py deploy <name> --wipe` to erase and redeploy, or `reset-board` to just erase |
| permission denied opening the port (Linux) | your user isn't in the serial-port group | `sudo usermod -a -G dialout $USER` (Debian/Ubuntu; the group is `uucp` on Arch), then log out and back in |
| `no firmware detected` | board is in bootloader / fresh-flash state | `python3 run.py install-firmware --method uf2` (or `esptool` on ESP32); a board with no `devices.yml` entry yet also needs `--url <image>`, since there's nothing to derive an image from (the install-firmware skill walks it) |
| `ImportError: no module named ...` on boot | missing library not yet on flash | check the deploy log; the error names the missing module |
| messages stop after first publish | RAM mode against a project that needs persistent state | switch to flash mode (per-device override in `devices.yml`) |
| TLS connection rejected | clock unset, so the cert validity check fails | NTP-sync after wifi connect, or backdate the cert's `notBefore` for development |

The skill files under `.github/skills/` (loaded by your AI agent on
demand) cover each of these in more detail.  When the table's first
move doesn't resolve it, the ChuMicro repository's
[troubleshooting section](https://github.com/ChuMicro/ChuMicro/tree/main/docs/troubleshooting)
has a page per symptom area: board not found, firmware, deploys and
persistence, WiFi, TLS, memory, and per-board quirks.

## Working with an AI agent

The agent's instruction file is [AGENTS.md](AGENTS.md).  It describes
file ownership rules (so the agent doesn't clobber files `update`
will refresh) and the canonical workflows.

Three patterns that work well:

1. **Bring the agent into a real session, not a planning one.**
   "Help me deploy `my_sensor` to the Pi Pico W and watch the
   output" gets you concrete diagnostics; "design a wifi
   architecture" gets you a whiteboard.

2. **Hand the agent the failure output, not your interpretation.**
   The deploy and REPL transcripts carry precise, classified error
   messages; an agent can usually map them straight to a fix.

3. **Ask the agent to load the right skill.**  When the agent sees a
   file under `.github/skills/<topic>/SKILL.md` whose description
   matches your task, it loads that procedure.  You can also name
   one explicitly: "use the `deploy-and-debug` skill."

The agent can edit files freely under `projects/<your-name>/`,
`shared/`, `workspace.yml` (except the dev-mode `library_sources:`
block, which `setup` re-syncs), and `secrets.toml`.  `devices.yml`
changes go through the device commands (`add-device`, `rename`),
not hand edits.  It should not edit `run.py`, `AGENTS.md`,
`CONTRIBUTING.md`, `pyproject.toml`, `projects/_template/`,
`examples/`, or anything under `.github/skills/` or
`.github/workflows/` that the template shipped; those are tool-owned, and
`python3 run.py update` will rewrite them next time you pull.

## Updating the workbench tooling

```bash
python3 run.py update                # pull tool-owned file refreshes from upstream
python3 run.py update --ref v0.1.0   # pin to a specific template version (a git tag)
python3 run.py update --from <url>   # pull from your own fork of the template
```

`update` only touches tool-owned files: `run.py`, `AGENTS.md`,
`CONTRIBUTING.md`, `pyproject.toml`, `requirements.txt`,
`constraints.txt`, the `projects/_template/` skeleton, the
`examples/` tree, `.github/skills/`, and `.github/workflows/`.  Your `projects/`, `devices.yml`,
`workspace.yml`, `secrets.toml`, `shared/`, and `packages/` are never
touched.  (AGENTS.md carries the same list for agents; if the two
ever disagree, that's a bug worth reporting.)

Two safety behaviors worth knowing.  If you've locally edited a
tool-owned file, `update` refuses to overwrite it (exit 3, naming the
file) rather than silently discarding your change; rerun with
`--force` to accept upstream's version.  And `update` reconciles
deletions: a tool-owned file it applied earlier that upstream no
longer ships is removed.  Files *you* created inside tool-owned
directories (say, a custom sibling workflow under
`.github/workflows/`) are never touched either way.  The bookkeeping
behind both lives in the gitignored `.chumicro-template-state.json`.

## Where to look up help

- **`AGENTS.md`**: concise rules for editing the workbench (file
  ownership, day-to-day commands, gotchas).
- **`.github/skills/<topic>/SKILL.md`**: agent-loadable procedures
  for the most common workflows.  Useful as reference even without
  an agent.
- **`projects/example_sensor/`**: the worked example.  Read it when
  you're not sure how to wire a service into a `Runner`.
- **The chumicro-workspace [hosted docs](https://chumicro.github.io/ChuMicro/workspace/stable/)**:
  reference for the underlying CLI commands and Python API.
- **The chumicro library [hosted docs](https://chumicro.github.io/ChuMicro/)**:
  per-library guides for `chumicro-wifi`, `chumicro-mqtt`, and the rest.
- **Issues**, routed by what broke:
  - Template bug (a shipped file here is wrong): [ChuMicro-Workbench-Template issues](https://github.com/ChuMicro/ChuMicro-Workbench-Template/issues).
  - Tooling bug (`run.py` commands, deploy, REPL, config merging) or
    library bug (`chumicro_wifi`, `chumicro_mqtt`, ...): file it on
    [ChuMicro-Workbench-Template issues](https://github.com/ChuMicro/ChuMicro-Workbench-Template/issues)
    too, naming the tool or library.  This tracker is the front door
    for everything ChuMicro-side; maintainers route reports to the
    right upstream home.
  - Your own project's bug: your workbench repo.

## Project rules: quick reference

These match the rules in `AGENTS.md`; called out here for humans too.

- Project names are Python identifiers: no hyphens, no dots, no
  leading digits.
- Credentials live in `secrets.toml` (gitignored, so your wifi
  password and broker auth never reach git).  Per-project
  `project_config.toml` deep-merges on top.
- `devices.yml` is gitignored.  Re-run `add-device` on a fresh
  clone, or copy your local `devices.yml` over by hand.
- On CircuitPython, do NOT add `CIRCUITPY_WIFI_SSID` to
  `settings.toml`.  `chumicro-wifi` owns the radio, and
  CircuitPython's auto-connect supervisor will fight it.
- Run `python3 run.py test` (forwards to `pytest`) before shipping.
  Tests live under `projects/<name>/tests/` if you want per-project
  coverage.
- For network-attached projects (anything using `chumicro-mqtt` or
  similar), drive the main loop with `runner.run_until(...)`.  It
  ticks, then parks the CPU in `runner.wait(now)` until the next
  event or deadline, which is the right way to idle.  Don't
  hand-roll a bare `while True: runner.tick()` busy-spin (it never
  parks), and don't add `time.sleep_ms()` inside the loop (tick
  latency matters for packet timing).

## When something feels wrong

Sanity-check ladder:

1. Is the workbench itself well-formed?  `python3 run.py status`
   (or `doctor` for the strict version).
2. Is the board actually plugged in?  `python3 run.py discover`.
3. Is the right runtime registered for that port?  `python3 run.py
   devices` to inspect the registry.
4. Is the deploy actually reaching the device?  `python3 run.py
   repl` and look for the boot banner.
5. Is the failure in your code or in the chumicro stack?  Read the
   traceback's first line: `projects/<name>/app.py` is yours;
   anything under `chumicro_*` is the library stack and the fix
   probably belongs upstream (file an issue).  Failed deploys also
   carry a `--- hints ---` block under the traceback when the error
   matches a known pattern (missing config key, library not
   installed).

Welcome aboard.  Have fun.
