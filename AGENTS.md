# AGENTS.md: workspace conventions

This file is for AI coding agents working inside this workspace.
Tool-owned: `python3 run.py update` will rewrite it.  Skim
[CONTRIBUTING.md](CONTRIBUTING.md) for the human-side framing.

## What this is

A ChuMicro project workspace.  `projects/` are individual deployable
apps, `devices.yml` registers boards, and `python3 run.py <cmd>`
dispatches to the `chumicro-workspace` host CLI.  See the package's
[hosted docs](https://chumicro.github.io/ChuMicro/workspace/stable/)
for the workflow primer.

## Day-to-day commands

| Command | Purpose |
|---|---|
| `python3 run.py setup` | One-time: create `.venv`, install deps, materialize the workbench-owned gitignored `workspace.yml` + `secrets.toml` + `devices.yml` starters from the canonical `chumicro-workspace` payloads. |
| `python3 run.py bootstrap [--demo]` | End-to-end onboarding wizard: pick a port → probe → register → optionally deploy demo.  Skip prompts with a positional device id plus `--address` and `--non-interactive`. |
| `python3 run.py status` | Workspace health snapshot: `workspace.yml` / `secrets.toml` validity, `devices.yml` count, projects-tree summary.  Exit 1 only on errors. |
| `python3 run.py doctor` | Strict sibling of `status`.  Adds Python ≥3.11 check and an AST scan for `def run`. |
| `python3 run.py new <name>` | Scaffold a new project under `projects/<name>/`.  Name may be nested (`upstairs/bedroom_sensor` or dotted `upstairs.bedroom_sensor`); each segment must be a valid Python identifier. |
| `python3 run.py new <name> --from <path>` | Scaffold from an existing tree instead of `projects/_template/`, e.g. `--from examples/wifi_only`. |
| `python3 run.py new <name> --library [--into <dir>]` | Scaffold a chumicro-style library tree (full `src/`, `tests/`, `docs/`, `examples/` layout).  Defaults to `<workspace>/libraries/<name>/`. |
| `python3 run.py projects` | Tree view of every project.  `--flat` for one-line-per-project slash-form output. |
| `python3 run.py discover` | List serial ports the host can see. |
| `python3 run.py add-device <id> --address <port> [--runtime <circuitpython\|micropython>]` | Probe + register a board.  Runtime auto-detected when omitted; only the full runtime names are accepted. |
| `python3 run.py probe` | Read `sys.implementation` from the default device. |
| `python3 run.py devices` | Print every entry in `devices.yml`. |
| `python3 run.py deploy <project>` | Ship a project to the default board.  Name accepts bare / slash / dotted; bare names disambiguate against the live tree. |
| `python3 run.py deploy <project> --device <id>` | Override the default device. |
| `python3 run.py deploy <project> --dry-run` | Print the file map without writing, useful for "did the overlay merge flatten?" debugging. |
| `python3 run.py deploy <project> --all-devices` | Loop over every device in `devices.yml`.  Failures don't abort the loop; exit code reflects whether any failed. |
| `python3 run.py deploy <project> --tail [SECONDS]` | Deploy, then follow the board's serial output for SECONDS (default 30) and exit.  The deploy-then-watch one-liner. |
| `python3 run.py deploy <project> --deploy-mode <ram\|flash>` | Override the device's `deploy_mode` for this run only (`devices.yml` untouched; `requires_flash` pre-flight still applies).  `--force-deploy-mode` also bypasses the pre-flight auto-switch. |
| `python3 run.py deploy <project> --no-wipe` | Additive deploy: reconcile only the entrypoint / state files + `/lib`, leaving other board files in place.  The default is clean-slate: the deploy removes anything that isn't the new payload or a keep-set file (`boot.py`, `boot_out.txt`, `_chu_kv.msgpack`) and evicts a board-resident `settings.toml`. |
| `python3 run.py deploy --all-projects` | Walk `workspace.yml`'s `deploy_targets:` mapping and deploy each project to its declared device(s).  Mutually exclusive with positional names / `--device` / `--runtime` / `--all-devices`. |
| `python3 run.py demo` | Deploy a built-in print-loop payload to the default board (no wifi, ~5s). |
| `python3 run.py repl` | Open an interactive REPL on the board.  Defaults to **line mode** in a TTY: host-side line editor with persistent per-device history, `:edit` opens `$EDITOR` with the recent buffer pre-seeded, `:save NAME` / `:load NAME` / `:snippets` round-trip reusable code, Tab completes against keywords + the on-device namespace (use `:rescan` after a new `import`).  Add `--mode passthrough` for the byte-by-byte mpremote-style flow (raw REPL framing, paste mode). |
| `python3 run.py repl --tail 30` | Standalone tail: stream a running board's output for 30 seconds, then exit.  Does not stage code.  To deploy *and* follow, use `deploy <project> --tail`. |
| `python3 run.py rename --device OLD NEW` | Rename a registered device in `devices.yml`; `--project OLD NEW` renames a project dir instead (slash/dotted paths accepted, namespace dirs auto-created).  One of the two flags is required. |
| `python3 run.py dump-config <project>` | Print the merged, flattened config the device would receive, without deploying.  The first stop for "which layer did this key come from?" |
| `python3 run.py library add <name> [--channel stable]` | Fetch a chumicro library plus its chumicro dependencies into the workspace (stable channel by default; `--channel experimental` tracks pre-release snapshots); `deploy` then ships what the project imports. |
| `python3 run.py deploy <project> --import-graph` | Ship on-device libraries resolved through the import graph (in dev mode, straight from the sibling checkout's `library_sources:`). |
| `python3 run.py preflight` | `lint` then `test` as one gate, honoring `workspace.yml`'s `quality:` knobs. |
| `python3 run.py install-firmware --method uf2` | Auto-derived firmware download + flash. |
| `python3 run.py upgrade-firmware --method esptool` | Same handler, conventionally for re-flashes. |
| `python3 run.py test [paths] [-- pytest-flags]` | Run pytest across `tests/` + `projects/*/tests/`.  Positional paths narrow the run (`test tests`, `test projects/<name>/tests`); pytest option flags go after `--` (`test -- -k boot -x`).  `workspace.yml`'s `quality.coverage_threshold` (when set) prepends `--cov-fail-under=N`. |
| `python3 run.py lint` | Run `ruff check` across the workspace.  `workspace.yml`'s `quality.lint.enabled = false` skips with a hint; `quality.lint.select` prepends `--select <list>`. |
| `python3 run.py update` | Pull tool-owned file refreshes from the canonical workspace template. |

## File ownership

| Path | Who edits | What `update` does |
|---|---|---|
| `projects/<your-name>/` | YOU | leaves alone |
| `devices.yml` | tool (via `add-device` / `rename` / `probe`); gitignored, materialized by `setup` from the chumicro-workspace package's canonical starter | leaves alone |
| `workspace.yml` | YOU, except the `library_sources:` block: in dev mode `setup` re-syncs that block on every run, so never hand-edit it.  Gitignored, materialized by `setup` (workspace machinery only) | leaves alone |
| `secrets.toml` | YOU; gitignored, materialized by `setup` from the chumicro-workspace package's canonical starter: holds wifi password / broker auth + device defaults that flow to the board | leaves alone |
| `quality.toml` | YOU; committed.  The workspace's lint/coverage policy, shared by every clone.  `workspace.yml`'s `quality:` block overrides it per machine | leaves alone |
| `shared/` | YOU (drop `foo.py`, projects import it by bare module name: `from foo import bar`) | leaves alone |
| `packages/` | YOU (manual-drop area; gitignored) | leaves alone |
| `libraries/` | YOU (created + populated by `library add` fetching on-device libraries; `new --library` scaffolds your own packages there.  Absent on a fresh clone; commit it or gitignore it, the trees re-fetch either way) | leaves alone |
| `run.py` | NEVER edit | rewrites |
| `AGENTS.md` | NEVER edit | rewrites |
| `CONTRIBUTING.md` | NEVER edit | rewrites |
| `pyproject.toml` | NEVER edit | rewrites |
| `requirements.txt` | NEVER edit | rewrites |
| `projects/_template/` | NEVER edit | rewrites |
| `.github/skills/` | NEVER edit | rewrites |
| `.github/workflows/` | NEVER edit | rewrites |
| `examples/` | NEVER edit | rewrites |

If the user asks for changes the tool-owned files would need, propose an upstream PR to the [`ChuMicro-Workspace-Template`](https://github.com/ChuMicro/ChuMicro-Workspace-Template) repo rather than editing in place.

**ChuMicro-dev mode:** when a `chumicro-dev.toml` (gitignored) sits next to `run.py`, `setup` pip-installs every library and workbench package from the sibling chumicro checkout it points at as editable, and re-syncs `workspace.yml`'s `library_sources:` block to that checkout.  `deploy --import-graph` then ships on-device libraries straight from the local checkout; the `library add` step is unnecessary in this mode.

## Skills index

Procedural knowledge for common workflows lives under `.github/skills/`.  Read the relevant skill BEFORE the task.  They're tight checklists with the exact commands.

| Skill | When to read it |
|---|---|
| `add-new-project` | The user wants to create a new app (`new <name>`, fill config, first deploy). |
| `register-board` | First-time board onboarding, or when `add-device` errors out. |
| `install-firmware` | A board is fresh from the factory, in bootloader mode, or needs a runtime (re)flashed before it can be registered or deployed to. |
| `deploy-and-debug` | A deploy failed, output is unclear, or the user wants to follow REPL after deploy. |
| `audit-comments` | After writing or reworking any `.py` that deploys to a board (`projects/`, `shared/`): check the prose against the device-source comment budget. |

## Rules of thumb

- **Projects must export `def run(): ...` from `app.py`** (or define `code.py` / `main.py` directly).  When the project ships `app.py` with `run()`, deploy synthesizes a three-line `code.py` (CP) or `main.py` (MP) at the device root that imports `app.run` and calls it.  When the project ships `code.py` / `main.py` itself, deploy ships those as-is.
- **Project names are Python identifiers.**  `python3 run.py new` rejects hyphens / dots / leading-digits / Python-keywords / leading-underscores up-front.  If the user typed a hyphenated name, suggest the underscore version.
- **Credentials live in `secrets.toml` directly** under nested TOML tables (`[wifi] ssid = ...`).  The file is gitignored, so wifi password / broker auth never reaches git.  Per-project `project_config.toml` deep-merges on top.  On-device readers see flat keys (`config["wifi.ssid"]`).  Compose-time flattening produces them.
- **CP boards: do NOT add `CIRCUITPY_WIFI_SSID` to `settings.toml`.**  `chumicro-wifi` owns the radio; CircuitPython's auto-connect supervisor will compete with it.
- **`run_until` / `runner.wait()` is the main-loop contract for networked projects.**  Drive the loop with `runner.run_until(predicate)` (or `run_until()` for run-forever apps).  It ticks then parks the CPU in `runner.wait(now)` until the next event or deadline, which is the *correct* way to idle between events.  Don't suggest a bare `while True: runner.tick()` busy-spin (never parks, a real on-device power cost) or a `time.sleep_ms()` inside the loop (loses MQTT keepalive timing and stalls inbound bytes).  If the user wants deeper power savings, the answer is a different runner shape (deep-sleep + scheduled wake), not a sleep call.
- **Flash mode is the default; RAM mode is opt-in for single-library experiments.**  `chumicro-deploy` ships with `deploy_mode: flash` as the default for project deploys, examples, and most functional tests.  This matches how production deploys behave on the device.  RAM mode (`deploy_mode: ram`) is only useful for quick single-library iteration where state-doesn't-persist-across-resets is actually fine.  Heavier libraries (`chumicro-mqtt` / `chumicro-requests` / `chumicro-http-server` / `chumicro-websockets`) declare `[tool.chumicro] requires_flash = true` in their pyproject; if a project imports any of them and the device is in `ram` mode, the deployer auto-switches to flash and prints why.  Surface this when the user reports "messages stop after first publish" or `OSError: [Errno 2] ENOENT` on `/runtime_config.msgpack`.
- **Run `python3 run.py test` before reporting work as done** when the user has tests under `projects/<name>/tests/` or at the workspace root.

## Device-source style

Everything under `projects/` and `shared/` deploys to the board as raw `.py` source.  There is no mpy-cross step in the pipeline: the board's own compiler parses every byte at import, so comments and docstrings cost flash and compile-time RAM, and a prose-heavy file is the classic `MemoryError`-on-import on a small board.

- **Comment budget: match the chumicro libraries.**  Short contract docstrings (what it does, what it returns, the error semantics), plus a why-comment only where the code cannot say it.  The shipped libraries run about one prose line per three lines of code; a starter file should not exceed that by much.
- **Long-form rationale goes in the nearest README**, never in device source.  READMEs stay on the host.  `shared/README.md`'s design-notes section is the worked example.
- **Write comments in sentences, plainly.**  No em-dashes (use a period, comma, colon, or parentheses).  No decoration, no narration of self-evident code.
- **Run `/audit-comments`** (see the skills index) after writing or reworking a device-deployed file.

## Tests + lint

| Path | What lives there | Run with |
|---|---|---|
| `tests/` | Workspace-level smoke tests (e.g. "every project exposes `run()`"). | `python3 run.py test tests` |
| `projects/<name>/tests/` | Per-project host-side unit tests.  Scaffolded into every new project by `python3 run.py new <name>`. | `python3 run.py test projects/<name>/tests` |
| `projects/<name>/functional_tests/` | Board-facing acceptance tests.  `chumicro-pytest-device` ships them to a registered board and runs them there, but **only when the `functional_tests` path is explicitly targeted**; sweeps ignore these trees entirely.  With no board registered, targeting one collects 0 items and exits 5: register a board first.  See the shipped `projects/example_sensor/functional_tests/` example (its CPython guard is belt-and-suspenders for tooling versions that predate project-tree routing). | `python3 run.py test projects/<name>/functional_tests` |

`python3 run.py test` with no args runs **everything** under `tests/` + `projects/`, except `functional_tests/` trees, which only fire when their path is targeted.

`python3 run.py lint` runs `ruff check` with the workspace's `[tool.ruff]` config (line-length 100, imports sorted, relative-import ban, pyflakes / bugbear / pyupgrade).  Tests + functional tests get the relative-import rule relaxed.  Lint/coverage knobs live in the committed `quality.toml` (`[lint] enabled = false` skips lint; `select = ["E", "F", "I"]` overrides the rule list); `workspace.yml`'s `quality:` block overrides per machine.

Coverage gate: `[tool.coverage.report] fail_under = 85` in `pyproject.toml`, the per-package floor.  Set the workspace's own gate via `coverage_threshold = <N>` in the committed `quality.toml` (forwarded to pytest as `--cov-fail-under`); `workspace.yml`'s `quality:` block overrides per machine, and flags passed after `--` win on conflict (pytest takes the last occurrence).

## Working in a fresh workspace

When you join a session in a workspace that's been freshly cloned:

1. Read `secrets.toml` to see the workspace-wide credentials + device defaults.
2. Read `devices.yml` to see what boards are registered.  If empty, `bootstrap` (the wizard) or `add-device` is the first move.
3. Read `projects/<name>/project_config.toml` for the project the user is working on.
4. If the user is hitting an error, read the full deploy / REPL output before suggesting fixes.  The recovery layer's messages are precise.

## Project rules: non-negotiable

- **Don't fabricate.**  Read code / docs / output instead of guessing.  If you can't verify, say so.
- **Don't edit tool-owned files.**  See the table above.
- **Don't bypass `run.py`.**  All commands go through it (so the workspace's `.venv` and config resolution stay consistent).
- **Don't commit `.scratch/`, `.venv/`, `workspace.yml`, `secrets.toml`, or `devices.yml`.**  All gitignored.
- **No emojis in files unless the user asks.**

## Common pitfalls

- Editing `workspace.yml.example` / `secrets.toml.example`: there aren't any.  Both files are materialized by `setup` from the chumicro-workspace package's canonical starters; just edit the gitignored files directly.
- Running raw `pytest`: the workspace's pytest config wants `python3 run.py test` so the venv + paths resolve right.
- Re-running `setup` thinking it'll "fix" something: it's idempotent and won't overwrite your edits (dev-mode exception: it re-syncs the `library_sources:` block).  If a project's broken, the fix is in your code, not in setup.
- Trying to debug a TLS handshake without setting the device clock: TLS validity-period checks fail with "validity starts in the future" on a fresh board.  NTP after wifi-up, or backdate the cert's notBefore for development.

## When you finish a unit of work

1. Run `python3 run.py test` if the user has tests.
2. Show the user the diff (or the file paths you touched).
3. If you ran a deploy, show the relevant REPL output.
4. Note anything you noticed but didn't change (out-of-scope tweaks the user might want).
