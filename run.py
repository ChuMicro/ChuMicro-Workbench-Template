"""Self-bootstrapping entry point for a ChuMicro workspace.

Tool-owned: ``chumicro-workspace update`` will rewrite this file.
Don't edit; if you need a custom command, extend ``chumicro-workspace``
upstream and re-run ``update`` to pull it in.

Bootstrap flow:

* ``python3 run.py setup`` is the bootstrap *and* the repair entry
  point.  It creates ``.venv/`` if absent, then ALWAYS (re)installs
  ``chumicro-workspace`` + the workspace's pyproject deps and verifies
  the CLI imports before handing off.  Running it against an existing
  venv is safe and idempotent: a venv whose dependencies have drifted
  behind a moved-ahead chumicro-dev checkout (e.g. a new transitive
  dep) self-heals here instead of crashing later at deploy time.
  Mirrors chumicro's ``scripts/prepare_workspace.py``.
* Every other ``python3 run.py <cmd>`` re-execs into the venv and
  dispatches through ``chumicro_workspace.cli``.  If the venv is stale
  it fails fast with a pointer to ``python3 run.py setup`` rather than
  a raw ``ImportError`` traceback.

ChuMicro-dev mode: drop a ``chumicro-dev.toml`` next to this file with::

    chumicro_path = "../chumicro"

When present, ``setup`` pip-installs every library and workbench
package found in your chumicro checkout as editable (plus their
third-party requirements) BEFORE the workspace's own install.  Lets
you co-develop chumicro libraries / chumicro-workspace from a
sibling checkout without publishing to PyPI.
Delete the file (or unset ``chumicro_path``) to revert to the PyPI
path.  ``chumicro-dev.toml`` is gitignored by default.

Requires Python 3.11+ (system or pyenv) for the initial bootstrap.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# tomllib (3.11+) is imported inside the functions that need it: an
# import here would crash 3.9/3.10 interpreters with a raw traceback
# before _check_python_version() can print the real requirement.

WORKSPACE_ROOT = Path(__file__).resolve().parent
VENV_DIR = WORKSPACE_ROOT / ".venv"
CHUMICRO_DEV_FILE = WORKSPACE_ROOT / "chumicro-dev.toml"
MIN_PYTHON = (3, 11)

#: Printed for ``setup --help`` before the first setup has built the
#: venv.  The installed CLI owns the real option list; this preview
#: exists so asking for help is never what triggers the install.
SETUP_HELP = """\
python3 run.py setup: create .venv/ and install the workspace tooling.

Creates .venv/ if absent, installs the ChuMicro tooling (from
requirements.txt, or editable from a sibling chumicro checkout when
chumicro-dev.toml is present), installs the workspace package itself,
then verifies the CLI imports.  Safe to re-run at any time: an
existing venv is repaired in place, never recreated.

This preview covers the bootstrap only.  Once setup has run, the
installed CLI answers `python3 run.py setup --help` with the full
option list."""


def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _running_in_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV_DIR.resolve()
    except OSError:
        return False


def _check_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        major, minor = MIN_PYTHON
        raise SystemExit(
            f"error: Python {major}.{minor}+ required; "
            f"got {sys.version.split()[0]}",
        )


def _read_chumicro_dev_path() -> Path | None:
    """Return the resolved chumicro-checkout path if dev mode is active.

    Reads ``chumicro-dev.toml`` (TOML, ``chumicro_path = "..."``).
    Relative paths resolve against the workspace root.  Returns
    ``None`` when the file is missing or the path key is unset.
    """
    import tomllib

    if not CHUMICRO_DEV_FILE.is_file():
        return None
    data = tomllib.loads(CHUMICRO_DEV_FILE.read_text())
    raw_path = data.get("chumicro_path")
    if not raw_path:
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (WORKSPACE_ROOT / candidate).resolve()
    return candidate


def _workspace_declares_dev_extra() -> bool:
    """Return True when the workspace pyproject declares a ``dev`` extra.

    Read from ``[project.optional-dependencies]`` in
    ``pyproject.toml``.  The template ships a ``dev`` extra (pytest,
    pytest-cov, ruff), so ``setup`` installs ``.[dev]`` and ``run.py
    lint`` / ``run.py test`` have their tools (the chumicro-side dev
    tooling comes from ``requirements.txt``).  A missing or malformed
    pyproject falls back to False so setup degrades to the bare
    editable install rather than crashing.
    """
    import tomllib

    pyproject = WORKSPACE_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return False
    optional = data.get("project", {}).get("optional-dependencies", {})
    return isinstance(optional, dict) and "dev" in optional


def _discover_chumicro_packages(checkout_path: Path) -> list[Path]:
    """Return every package dir under *checkout_path*'s ``libraries/``,
    ``support/``, and ``workbench/`` trees that has a ``pyproject.toml``.

    Order is alphabetical within each tree, libraries first (deploy +
    workspace need the libraries' build deps to resolve), then support
    (the on-device test harness that board-routed functional tests
    stage), then workbench.
    """
    packages: list[Path] = []
    for parent_name in ("libraries", "support", "workbench"):
        parent = checkout_path / parent_name
        if not parent.is_dir():
            continue
        for entry in sorted(parent.iterdir()):
            if entry.is_dir() and (entry / "pyproject.toml").is_file():
                packages.append(entry)
    return packages


def _third_party_requirements(packages: list[Path]) -> list[str]:
    """Collect the non-chumicro runtime requirements of *packages*.

    The editable installs run ``--no-deps`` so pip never tries to
    resolve the chumicro-internal dependencies (e.g. the workspace
    package depending on the deploy package) from PyPI: the sibling
    checkout provides those.  But ``--no-deps`` also skips the real
    third-party requirements (ruamel.yaml, msgpack, pyserial, ...),
    and nothing else installs them, so a fresh dev-mode venv would
    fail the post-install verify gate.  This gathers every non-chumicro
    requirement string across the discovered packages, first-seen
    order, deduplicated, for one explicit install pass.
    """
    import tomllib

    requirements: list[str] = []
    seen: set[str] = set()
    for package_path in packages:
        try:
            data = tomllib.loads((package_path / "pyproject.toml").read_text())
        except (OSError, tomllib.TOMLDecodeError):
            continue
        for requirement in data.get("project", {}).get("dependencies", []):
            if not isinstance(requirement, str):
                continue
            name = requirement.split(";")[0].strip().lower()
            if name.startswith("chumicro"):
                continue
            if requirement not in seen:
                seen.add(requirement)
                requirements.append(requirement)
    return requirements


def _create_venv() -> None:
    print(f"creating .venv at {VENV_DIR}", flush=True)
    subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        check=True,
    )


def _install_workspace(venv_python: Path) -> None:
    """Install (or repair) the workspace into *venv_python*.

    Idempotent and safe to re-run.  This is what makes ``setup`` a
    self-healing bootstrap rather than a one-shot.  In chumicro-dev mode
    the sibling packages are (re)installed editable, then the
    workspace's own pyproject deps resolve normally, which is precisely
    what pulls in any transitive dependency the chumicro checkout has
    grown since the venv was last built.
    """
    print("upgrading pip", flush=True)
    subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--quiet",
            "pip",
        ],
        check=True,
    )
    chumicro_path = _read_chumicro_dev_path()
    if chumicro_path is not None:
        if not chumicro_path.is_dir():
            raise SystemExit(
                f"error: chumicro-dev.toml points at {chumicro_path} "
                "but that path does not exist or is not a directory.\n"
                "chumicro-dev.toml enables co-developing chumicro from a "
                "sibling source checkout.  Fix its chumicro_path, or if "
                "you didn't mean to be in dev mode, delete "
                "chumicro-dev.toml and rerun `python3 run.py setup`.",
            )
        packages = _discover_chumicro_packages(chumicro_path)
        if not packages:
            raise SystemExit(
                f"error: no chumicro packages found under {chumicro_path}. "
                "Expected libraries/<name>/pyproject.toml or "
                "workbench/<name>/pyproject.toml.  Point chumicro_path in "
                "chumicro-dev.toml at a chumicro source checkout, or "
                "delete chumicro-dev.toml and rerun `python3 run.py setup` "
                "to use the published packages instead.",
            )
        print(
            f"chumicro-dev mode: installing {len(packages)} package(s) from "
            f"{chumicro_path}",
            flush=True,
        )
        for package_path in packages:
            print(f"  editable: {package_path.relative_to(chumicro_path)}", flush=True)
            subprocess.run(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--quiet",
                    "--no-deps",
                    "-e",
                    str(package_path),
                ],
                check=True,
            )
        # The editable installs above ran --no-deps (so pip never
        # resolves chumicro-internal deps from PyPI); install the
        # packages' third-party requirements explicitly or a fresh
        # dev-mode venv is missing ruamel.yaml / msgpack / pyserial
        # and the verify gate below can never pass.
        third_party = _third_party_requirements(packages)
        if third_party:
            print(
                f"chumicro-dev mode: installing {len(third_party)} "
                "third-party requirement(s)",
                flush=True,
            )
            subprocess.run(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--quiet",
                    *third_party,
                ],
                check=True,
            )
    else:
        # Regular mode (no chumicro-dev.toml): install the chumicro tooling
        # from requirements.txt, the one-per-line manifest of what a
        # workspace actually runs (chumicro-workspace, -repl, -pytest-device,
        # -checks).  Dev mode skips this: its sibling checkout already
        # provides those packages editable, and pulling the published copies
        # on top would shadow them.
        requirements = WORKSPACE_ROOT / "requirements.txt"
        if requirements.is_file():
            print(f"installing chumicro tooling from {requirements.name}", flush=True)
            subprocess.run(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(requirements),
                ],
                check=True,
            )
    # Install the workspace package itself plus the `dev` extra (pytest /
    # ruff / pytest-cov) when the pyproject declares one, so `run.py lint`
    # and `run.py test` have their tools; fall back to the bare editable
    # install for a deploy-only workspace that skipped the dev tooling.
    if _workspace_declares_dev_extra():
        install_target = f"{WORKSPACE_ROOT}[dev]"
        print("installing workspace (editable) + dependencies + [dev] extra", flush=True)
    else:
        install_target = str(WORKSPACE_ROOT)
        print("installing workspace (editable) + dependencies", flush=True)
    subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-e",
            install_target,
        ],
        check=True,
    )


def _verify_workspace(venv_python: Path) -> None:
    """Refuse to report success until the CLI actually imports.

    A fresh or repaired venv can still be missing a transitive dep
    (classic in chumicro-dev mode, where editable installs are
    ``--no-deps``).  Importing the CLI in the target interpreter catches
    that here, at setup time, instead of as a confusing failure at
    deploy time.  Mirrors prepare_workspace.py's post-install verify
    gate: bootstrap only earns "ready" once the import has passed.
    """
    print("verifying workspace (chumicro_workspace.cli imports)", flush=True)
    result = subprocess.run(
        [str(venv_python), "-c", "import chumicro_workspace.cli"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(
            "error: workspace install did not produce a working CLI "
            "(import of chumicro_workspace.cli failed above).  In "
            "chumicro-dev mode this usually means the sibling chumicro "
            "checkout grew a dependency the editable --no-deps install "
            "skipped; rerun `python3 run.py setup` after it settles, or "
            "delete .venv/ and rerun setup for a clean rebuild.",
        )
    print("verified: CLI imports cleanly", flush=True)


def _reexec_in_venv() -> None:
    venv_python = _venv_python()
    if not venv_python.exists():
        raise SystemExit(
            f"error: venv at {VENV_DIR} is broken "
            f"(no python at {venv_python}); "
            f"delete .venv/ and rerun `python3 run.py setup`.",
        )
    argv = [str(venv_python), __file__, *sys.argv[1:]]
    if sys.platform == "win32":
        # Windows exec* does not replace the process (the shell prompt
        # returns while the child still runs) and joins argv without
        # quoting, so a workspace path with a space splits.  Run the
        # venv interpreter as a child instead.
        raise SystemExit(subprocess.run(argv).returncode)
    os.execv(str(venv_python), argv)


def main() -> int:
    _check_python_version()
    args = sys.argv[1:]
    is_setup = args[:1] == ["setup"]
    wants_help = any(argument in ("-h", "--help") for argument in args)

    if is_setup and wants_help and not VENV_DIR.exists():
        # Asking for help must never be what triggers the install.
        # Without a venv the installed CLI's argparse help is
        # unreachable, so print the shim-level preview instead.
        print(SETUP_HELP)
        return 0

    if is_setup and not wants_help and not _running_in_venv():
        # Bootstrap + self-repair.  Runs once in the outer (system)
        # interpreter; the post-verify re-exec re-enters main() inside
        # the venv where _running_in_venv() short-circuits past this
        # block straight to dispatch (so we never double-install).
        # Reinstalling unconditionally (not just when .venv/ is absent)
        # is what heals a venv whose deps drifted behind a moved-ahead
        # chumicro-dev checkout.
        if not VENV_DIR.exists():
            _create_venv()
        venv_python = _venv_python()
        if not venv_python.exists():
            raise SystemExit(
                f"error: venv at {VENV_DIR} is broken (no python at "
                f"{venv_python}); delete .venv/ and rerun "
                f"`python3 run.py setup`.",
            )
        _install_workspace(venv_python)
        _verify_workspace(venv_python)
        _reexec_in_venv()

    if not VENV_DIR.exists():
        raise SystemExit(
            "error: workspace not set up yet. "
            "Run `python3 run.py setup` first.",
        )
    if not _running_in_venv():
        _reexec_in_venv()
    try:
        from chumicro_workspace.cli import main as workspace_main
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"error: the workspace venv is missing '{exc.name}'; its "
            f"dependencies have drifted (common in chumicro-dev mode "
            f"after the sibling chumicro checkout moves ahead).\n"
            f"Repair it (idempotent, keeps your venv):\n"
            f"    python3 run.py setup",
        ) from exc

    return workspace_main(args)


if __name__ == "__main__":
    sys.exit(main())
