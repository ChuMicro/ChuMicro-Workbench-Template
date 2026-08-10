# Changelog

Notable changes to the workbench template.  Versions are git tags;
pin a workbench to one with `python3 run.py update --ref v<version>`.

## Unreleased

- Docs now cover the tooling's real surface, grounded in a
  source-level audit of the host packages.  README: a zero-code
  first-contact section (`bootstrap --demo`, `library browse`,
  `deploy-example`) and a capability tour (recovery plans with
  port-holder diagnosis, laptop-side import/async/reset refusals, the
  boot shim, RAM-mode iteration with auto-promotion, clean-slate
  semantics, `--tail` as a CI check, on-device pytest with network
  fixtures, the REPL, fleet deploys, firmware derivation, the library
  channel lifecycle, `dump-config` / `config-validate`).
  CONTRIBUTING: fetched-library lifecycle (pin/float, backups,
  `.chumicro-local`), the three wipe levels plus `--dry-run` and
  `--no-fail-on-traceback`, registry housekeeping
  (`remove-device` / `reset-device` / `probe`), `config-validate`,
  `--workspace-dir`, `update --from`, and three new debugging-table
  rows (port holders, the macOS FSKit wedge, FAT corruption).
  AGENTS: rows for `deploy-example` (with its exit-code contract),
  the `library` lifecycle verbs, `config-validate`, and
  `remove-device` / `reset-device`.
- The template is now **ChuMicro-Workbench-Template** (GitHub rename
  redirect keeps old clone URLs working), and the docs now call the
  repo you fork a *workbench* throughout.  Load-bearing names are
  unchanged: the `chumicro-workspace` package and CLI, the
  `workspace.yml` filename, and the hosted docs path keep their
  spelling until upstream renames them.
- README rebuilt around a ten-step path from clone to a board
  publishing MQTT, absorbing the old quickstart and worked example.
- `constraints.txt` ships with exact pins for the chumicro host
  tooling; CI installs through it via `PIP_CONSTRAINT`, and a CI step
  now runs the `template_zone_docs` ownership-drift checker.
- New docs: `SECURITY.md` (private vulnerability reporting plus the
  credentials-stay-gitignored rules), `CODE_OF_CONDUCT.md` (adopts
  the ChuMicro Contributor Covenant), and `projects/README.md` (the
  project contract, naming rules, and the three test kinds in one
  place).
- Doc corrections: `update`'s refuse-on-local-edit (`--force`) and
  deletion-reconcile behaviors are documented instead of the old
  unconditional "rewrites" claim; `install-firmware` on a
  never-registered board is documented as needing `--url`; the
  `libraries:` table `library add` manages in `workspace.yml` is
  documented; `lint` is documented as ruff plus `chumicro-checks`;
  AGENTS.md gained ownership rows for `constraints.txt` and
  `pyrightconfig.json`; `.gitignore` covers
  `.chumicro-template-state.json`.
- Tooling floor raised to `chumicro-workspace` 0.54.1 (stable): `test
  -- <pytest-flags>` now passes through to pytest, CLI hints and the
  scaffolded library README name `python3 run.py` inside a template
  workbench, the status/doctor glyph column self-aligns, and the
  `new --from` help cites a real example.  AGENTS.md documents the
  restored passthrough form.
- `shared/face.py` + `shared/face_status.py`: a default bring-up
  starter for networked projects (config + runner + wifi + MQTT,
  availability last-will, topic routing, periodic system status),
  with a workbench smoke test that tracks it against the library
  APIs.  `projects/example_sensor/` still writes the same wiring by
  hand as the teaching reference.
- Full-repo audit fixes: `run.py` now prints its "Python 3.11+
  required" message on 3.9/3.10 instead of a raw `tomllib`
  traceback; the venv re-exec works on Windows (paths with spaces,
  live console); the workbench smoke test evicts sibling *packages*
  between project loads, so two projects with same-named packages
  can't contaminate each other (regression test added);
  `face_status` free-storage math uses `f_frsize * f_bavail` (the
  old indices inflated the number 256x on some hosts); face
  `on_connect` callbacks are fault-isolated; the `packages/`
  pinning recipe now actually re-includes files; the boot-counter
  functional test no longer depends on the previous test's cleanup.
- Device-source comment budget: the `shared/` starters slimmed to
  the chumicro libraries' prose density (their design rationale
  moved to `shared/README.md`, which never deploys), a new
  `audit-comments` skill enforces the budget, and AGENTS.md grew a
  device-source style section.
- Docs corrections: the quickstart and `wifi_only` example now
  install `chumicro_runner` (previously a literal follow-through
  reached first deploy with the runner missing); `libraries/`
  provenance and commit-vs-ignore guidance documented; AGENTS.md
  matches the CLI again (`--runtime` full names only, pytest option
  flags don't pass through, boardless functional-test targeting
  collects nothing); CONTRIBUTING's tool-owned list includes
  `requirements.txt` and its issue-routing text no longer claims
  the ChuMicro repo is private; the README names the MIT license.
- Gitignore hardening: `secrets.toml` ignored at any depth (not
  just the root), `settings.toml` ignored (CircuitPython habit
  file; this workbench never uses it), and the TLS block covers
  `*.key` / `*.crt` / `*.p12`.
- Tooling now pins the stable release channel (`requirements.txt`
  carries the stable names; `chumicro-workspace` 0.51.0 defaults
  `library add` to stable), and every channel note in the docs
  matches.
- GA documentation pass: the quickstart scaffolds from the
  `wifi_only` starter so its wifi and secrets steps connect, a
  boardless on-ramp and an "if setup fails" note landed in the
  README, `setup --help` no longer triggers an install, the
  chumicro-dev error messages name their own fix, multi-project and
  multi-board targeting is documented, AGENTS.md matches the real
  CLI flags, and em-dashes are gone repo-wide per the ChuMicro
  docs voice.

## v0.1.0 (2026-07-18)

First tagged release.  The template as of this tag:

- Clone-and-go workbench layout: `run.py` self-bootstrapping
  dispatcher, `projects/` (with `_template/` scaffold source and the
  `example_sensor` reference project), read-only `examples/`
  (hello_world, wifi_only, periodic_get, telemetry_publisher,
  two_board_handshake), `shared/`, `packages/`, committed
  `quality.toml`, and gitignored `workspace.yml` / `secrets.toml` /
  `devices.yml` materialized by `setup`.
- Agent support: `AGENTS.md` conventions plus four skills under
  `.github/skills/`: add-new-project, register-board,
  install-firmware, deploy-and-debug.
- Tooling pinned to the experimental release channel while the first
  stable wave publishes (`requirements.txt` carries the rationale and
  the flip-at-stable note).
- Host-side testing: workbench smoke tests cover every project and
  every shipped example (nested projects included), `conftest.py`
  mirrors the device import search path (`shared/` →
  `libraries/*/src` → `packages/`), and `example_sensor` ships both
  per-project unit tests and a board-routed functional test:
  `python3 run.py test projects/<name>/functional_tests` ships the
  tree to a registered board and runs it there (sweeps leave
  functional trees alone).  Requires the chumicro tooling wave that
  carries project-tree routing; `requirements.txt` pins it.
- Fixed in the run-up to this tag: dev-mode `setup` installs the
  sibling checkout's third-party requirements (fresh dev-mode venvs
  bootstrap cleanly), `run.py lint` survives `library add` (acquired
  library trees are excluded from the workbench ruff sweep), dead
  links and stale channel/behavior claims corrected across the docs,
  one `python3 run.py` spelling everywhere, and an MIT license.
