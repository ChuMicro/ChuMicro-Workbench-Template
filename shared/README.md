# shared/

User-authored helper modules shared between projects in this workspace.

## The default face

`face.py` ships as a starter: `Face(name=...)` is the standard bring-up for a networked project (config + runner + wifi + MQTT wired together, availability last-will, topic routing, periodic system status via `face_status.py`).  `projects/example_sensor/` deliberately writes the same wiring out by hand, so you can see what the face does before leaning on it.

Like everything in `shared/`, these two files are **yours**: edit them freely, and `python3 run.py update` will never touch them.  That also means they never receive upstream fixes — they're a starting point you own, not a maintained surface.

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
