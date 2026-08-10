---
name: add-new-project
description: Scaffold a new project in this ChuMicro workbench, wire its config + credentials, and verify the first deploy.  Use when the user says "make a new project", "add an X app", or asks to start a new program from scratch.
---

# Add a new project

A project is one deployable program, a directory under `projects/`
with an `app.py` defining `def run(): ...` and a
`project_config.toml` for its knobs.  This skill walks through
scaffolding one and getting to the first successful deploy.

## 1. Pick a name

Project directory names must be valid Python identifiers: letters,
digits, underscores; **no hyphens**, no dots, no leading digit.
The runtime imports `projects.<name>.app`, so anything Python can't
import breaks deploy.

If the user typed `back-porch`, suggest `back_porch`.  If they
typed `1sensor`, suggest `sensor_one` or similar.

`python3 run.py new <name>` rejects invalid names up-front with a
clear message.  That's a fast way to validate.

## 2. Scaffold

```bash
python3 run.py new my_project
```

Copies `projects/_template/` into `projects/my_project/`.  The
template typically ships:

- `app.py`: minimal `def run(): print("hello")` placeholder.
- `project_config.toml`: empty config sections matching the
  libraries the template imports.

Open both and edit:

- `app.py`: write the actual logic.  Most networked projects
  follow the pattern in `projects/example_sensor/app.py`: build
  services with `from_config`, register them with a `Runner`, wire
  a `wifi.on_state_change` callback to kick off connect, schedule
  periodic work with `runner.add_periodic(...)`, and drive the main
  loop with `runner.run_until(...)` (which parks the CPU in
  `runner.wait()` between events).
- `project_config.toml`: fill in per-project knobs (sample
  period, mqtt topic, sensor pins, etc.).  This file is versioned
  with the project, so keep credentials out of it.  They belong in
  the workbench's gitignored `secrets.toml` (step 3).

## 3. Wire credentials

Workbench-wide credentials (wifi password, broker auth) live in
the gitignored `secrets.toml` at the workbench root.  `setup`
materialises that file from the chumicro-workspace package's
canonical starter on first run; open it and fill in your values:

```toml
# secrets.toml: gitignored; workbench-wide credentials + device defaults
[wifi]
ssid = "YourNetwork"
password = "your-actual-passphrase"

[mqtt.broker]
host = "broker.example.com"
port = 1883

[mqtt.broker.auth]
username = "device-user"
password = "your-broker-password"
```

The deploy-time deep-merge is two layers: `secrets.toml` →
`projects/<name>/project_config.toml`.  Per-project values win at
any key.  The merged dict is then flattened to dotted keys
(`wifi.ssid`, `mqtt.broker.host`) and shipped to the device as
`/runtime_config.msgpack`.  Neither `secrets.toml` nor per-project
`project_config.toml` lands on the device.  Only the merged + flat
msgpack does.

## 4. First deploy

```bash
python3 run.py deploy my_project
```

If a default device is set in `devices.yml` (`defaults.micropython`
or `defaults.circuitpython`), the deploy fires against that
board.  Otherwise add `--device <id>`.

Watch the output.  On success you'll see:

```
deploy: staged N files
deploy: executing entrypoint
<your project's stdout here>
```

If the deploy fails, **load the `deploy-and-debug` skill**.
Don't guess at fixes.

## 5. Follow the output

After deploy, the entrypoint runs forever (most projects drive a
`runner.run_until(...)` loop that never completes on its own).  To
deploy *and* follow the board's output in one step:

```bash
python3 run.py deploy my_project --tail       # deploy, then tail 30s
python3 run.py deploy my_project --tail 60    # override the window
```

`--tail` is convenient for "did the heartbeat fire?" sanity checks.
To poke at variables on a board that's already running, open an
interactive REPL (`repl` never stages code, use `deploy` for that):

```bash
python3 run.py repl              # interactive (Ctrl-X to exit)
python3 run.py repl --tail 30    # standalone tail, no deploy
```

## Rules

- **Scaffold sources**: `python3 run.py new <name>` copies
  `projects/_template/`; `new <name> --from <path>` copies any
  existing tree instead (`--from examples/wifi_only`, `--from
  projects/other_project`).  To rename an existing project, use
  `python3 run.py rename --project OLD NEW`, not a hand `mv`.
- **Don't edit `projects/_template/`**: it's tool-owned and
  `update` will rewrite it.  If the user wants a different
  template starter, that's an upstream change.
- **Run `python3 run.py test`** if the user has tests under
  `projects/<name>/tests/` before reporting the work done.
- **Surface the deploy output** to the user.  Don't summarize
  the success message unless they ask.  The full deploy log
  contains diagnostics future agents (or human re-runs) might
  need.
