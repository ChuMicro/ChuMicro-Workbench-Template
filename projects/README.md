# projects/

Your applications.  One directory per deployable program; everything
in here is yours, and `python3 run.py update` never touches it.

## What a project is

A directory with two files at minimum:

- `app.py` defining `def run(): ...`.  The deploy tooling installs a
  three-line boot file on the device that imports `app.run` and calls
  it.  (A project may instead ship its own `code.py` / `main.py`, and
  deploy sends those as-is.)
- `project_config.toml` for the project's knobs (sample period, MQTT
  topic, pins).  At deploy time it deep-merges on top of the
  workbench-wide `secrets.toml` and lands on the device as one flat
  config dict; `python3 run.py dump-config <name>` shows the merged
  result.  Credentials stay in `secrets.toml` (gitignored), never in
  this file (versioned).

`python3 run.py new <name>` scaffolds one from `_template/`;
`--from examples/<example>` starts from a worked example instead.

## Naming

Names must be valid Python identifiers (the runtime imports
`projects.<name>.app`, so hyphens break deploys).  Nested layouts are
first-class: `python3 run.py new garage/sensors/door_open` (or the
dotted form) creates a namespace tree, and `python3 run.py projects`
shows it.

## The two shipped directories

- `_template/`: the blank scaffold `new` copies.  Tool-owned: `update`
  refreshes it.
- `example_sensor/`: the worked reference (wifi to MQTT heartbeat with
  a persistent boot counter).  The README's ten steps deploy it.

## Tests: three kinds, two speeds

| Where | What | How it runs |
|---|---|---|
| `<name>/tests/` | Host-side unit tests for the project's logic, scaffolded by `new`. | `python3 run.py test projects/<name>/tests`, and every plain `test` sweep. |
| `<name>/functional_tests/` | Board-facing acceptance tests. | Only when the path is targeted explicitly: `python3 run.py test projects/<name>/functional_tests`.  Sweeps skip these trees; with no board registered the run collects nothing and exits 5. |
| `../tests/` (workbench root) | Cross-project smoke tests ("every app.py exposes `run()`"). | Every sweep. |

Keeping fast host tests and slow board tests in separately-named
directories is what lets `python3 run.py test` stay safe to run on
every change.
