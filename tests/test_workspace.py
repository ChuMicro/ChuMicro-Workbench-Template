"""Workspace-level smoke tests.

Covers properties of the workspace that aren't tied to a single
project: every ``projects/<name>/app.py`` and ``examples/**/app.py``
exposes a ``run`` callable; ``workspace.yml`` (machinery) and
``secrets.toml`` (device config) parse cleanly.

This file is YOUR territory.  Edit freely.  ``chumicro-workspace
update`` will not touch it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = WORKSPACE_ROOT / "projects"
EXAMPLES_DIR = WORKSPACE_ROOT / "examples"


def _app_directories(base_dir: Path) -> list[Path]:
    """Return every directory under *base_dir* with an ``app.py``.

    Projects may be nested (``projects/garage/sensors/door_open/``),
    so this walks the whole tree rather than one level.  Skips
    ``_template/`` (the scaffold source), anything under an
    underscore-prefixed directory, and any directory that doesn't
    define ``app.py`` yet (a partial scaffold, or a bare namespace
    directory holding nested projects).
    """
    if not base_dir.is_dir():
        return []
    return sorted(
        app_path.parent
        for app_path in base_dir.rglob("app.py")
        if not any(
            part.startswith("_")
            for part in app_path.parent.relative_to(base_dir).parts
        )
    )


def _tree_id(base_dir: Path, app_dir: Path) -> str:
    """Slash-form name (``garage/sensors/door_open``) for test ids."""
    return "/".join(app_dir.relative_to(base_dir).parts)


def _load_app_module(base_dir: Path, app_dir: Path):
    """Load a directory's ``app.py`` directly via importlib.

    Avoids needing the on-device ``workspace_runtime`` boot module
    in the test path; we want a host-side smoke test, not a real
    boot.  A module-level import of a chumicro device library that
    isn't importable on this host yet (fresh clone, ``library add``
    not run) skips rather than fails: the code may be fine on the
    device, and the skip message names the fix.
    """
    dotted = ".".join(app_dir.relative_to(base_dir).parts)
    spec = importlib.util.spec_from_file_location(
        f"{base_dir.name}.{dotted}.app", app_dir / "app.py",
    )
    if spec is None or spec.loader is None:  # pragma: no cover
        pytest.fail(f"could not load spec for {app_dir / 'app.py'}")
    module = importlib.util.module_from_spec(spec)
    # The project directory joins sys.path for the load, mirroring
    # the device, where the project's files sit at the filesystem
    # root: an app.py that does ``from fan_driver import ...`` at
    # module level must smoke-load the same way it boots.  Sibling
    # modules imported during the load are evicted afterwards so two
    # projects with same-named siblings can't poison each other
    # through the sys.modules cache.
    sys.path.insert(0, str(app_dir))
    modules_before = set(sys.modules)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as error:
        if error.name is not None and error.name.startswith("chumicro"):
            pytest.skip(
                f"{_tree_id(base_dir, app_dir)}: imports {error.name} at "
                f"module level, which isn't installed on this host.  Run "
                f"`python3 run.py library add {error.name}` (or enable "
                f"chumicro-dev mode) to host-test this code.",
            )
        raise
    finally:
        sys.path.remove(str(app_dir))
        for name in set(sys.modules) - modules_before:
            loaded = sys.modules[name]
            loaded_file = getattr(loaded, "__file__", None)
            if loaded_file and Path(loaded_file).parent == app_dir:
                del sys.modules[name]
    return module


@pytest.mark.parametrize(
    "project_dir",
    _app_directories(PROJECTS_DIR),
    ids=lambda path: _tree_id(PROJECTS_DIR, path),
)
def test_project_app_exposes_run(project_dir: Path) -> None:
    """Every project's ``app.py`` must expose a ``run`` callable.

    The on-device ``workspace_runtime.boot()`` calls
    ``projects.<name>.app.run()`` after wiring config / wifi / etc.
    A project without ``run`` won't boot, so we catch the regression
    here at host-side test time.
    """
    module = _load_app_module(PROJECTS_DIR, project_dir)
    assert hasattr(module, "run"), (
        f"{project_dir.name}/app.py must define run(): the on-device "
        f"boot module imports it and calls run()"
    )
    assert callable(module.run), (
        f"{project_dir.name}/app.py: run must be callable"
    )


@pytest.mark.parametrize(
    "example_dir",
    _app_directories(EXAMPLES_DIR),
    ids=lambda path: _tree_id(EXAMPLES_DIR, path),
)
def test_example_app_exposes_run(example_dir: Path) -> None:
    """Every shipped example must import cleanly and expose ``run``.

    The examples are scaffold sources (``new --from examples/...``),
    so a broken example becomes a broken first project.  On a host
    where the chumicro libraries are importable (chumicro-dev mode,
    or after ``library add``), this also exercises every example's
    module-level imports against the live library APIs, a tripwire
    for examples silently rotting as the libraries move.  Hosts
    without the libraries skip via the loader.
    """
    module = _load_app_module(EXAMPLES_DIR, example_dir)
    assert callable(getattr(module, "run", None)), (
        f"examples/{_tree_id(EXAMPLES_DIR, example_dir)}/app.py must "
        f"define a run() callable: it's a scaffold source for new "
        f"projects"
    )


def test_shared_face_imports() -> None:
    """The shipped default face must track the library APIs.

    ``shared/face.py`` imports the chumicro libraries at module top,
    so on hosts that have them (chumicro-dev mode, or after
    ``library add``) this catches the starter silently rotting as
    the libraries move.  Hosts without the libraries skip, matching
    the app smoke tests above.
    """
    try:
        import face
    except ModuleNotFoundError as error:
        if error.name is not None and error.name.startswith("chumicro"):
            pytest.skip(
                f"face.py imports {error.name}, which isn't installed on "
                f"this host.  Run `python3 run.py library add {error.name}` "
                f"(or enable chumicro-dev mode) to host-test the face.",
            )
        raise
    assert hasattr(face, "Face"), "shared/face.py must export Face"


def test_shared_dir_on_import_path() -> None:
    """The root ``conftest.py`` puts ``shared/`` on ``sys.path``.

    A project imports a ``shared/foo.py`` helper by its bare module name
    (``from foo import bar``); the host test run resolves that only
    because ``shared/`` sits on the import path, matching the device,
    where deploy stages ``shared/`` modules into ``/lib``.  Assert the
    directory is on ``sys.path`` so a regression surfaces here rather
    than as a confusing ImportError while loading a project's ``app.py``.
    """
    shared_dir = WORKSPACE_ROOT / "shared"
    assert str(shared_dir) in sys.path


def test_workspace_yml_parses() -> None:
    """``workspace.yml`` must parse as YAML.

    Catches a yanked-comma or stray-tab regression before deploy
    time, where the same parse failure would surface as a confusing
    "deploy failed" message instead.
    """
    workspace_yml = WORKSPACE_ROOT / "workspace.yml"
    if not workspace_yml.is_file():
        pytest.skip("workspace.yml not present yet")
    # ruamel.yaml is the workspace's shipped YAML dependency (the
    # tooling round-trips workspace.yml with it); PyYAML is not
    # installed, so parse with the library we actually have.
    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(workspace_yml.read_text()) or {}
    assert isinstance(data, dict), "workspace.yml must be a mapping at the root"


def test_secrets_toml_parses() -> None:
    """``secrets.toml`` must parse as TOML.

    Same shape as ``test_workspace_yml_parses``: surface a malformed
    secrets file at host-side test time rather than as a cryptic
    deploy-time error.
    """
    secrets_toml = WORKSPACE_ROOT / "secrets.toml"
    if not secrets_toml.is_file():
        pytest.skip("secrets.toml not present yet")
    import tomllib

    data = tomllib.loads(secrets_toml.read_text())
    assert isinstance(data, dict), "secrets.toml must be a table at the root"
