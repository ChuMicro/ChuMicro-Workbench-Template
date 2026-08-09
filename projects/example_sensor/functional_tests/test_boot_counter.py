"""On-device acceptance for example_sensor's persistence contract.

Run it by targeting this directory (a plain ``python3 run.py test``
sweep leaves ``functional_tests/`` trees alone)::

    python3 run.py test projects/example_sensor/functional_tests

``chumicro-pytest-device`` ships this file to a registered board and
executes it there: the tests below run on the device, not the host.

What it covers: the boot-counter pattern in ``app.py`` assumes a
value written through ``KVStore`` survives into a *fresh* store
instance, the same code path a reboot takes.  That's a hardware
property (NVM / flash substrate behavior), so it belongs on a real
board rather than mocked on the host.

The test uses its own key and removes it afterwards, so the real
``boot_count`` of a deployed example_sensor is left alone.
"""

import sys

if sys.implementation.name == "cpython":
    # Belt-and-suspenders: on-device this never fires (the runtime is
    # micropython / circuitpython there), and a host interpreter only
    # reaches this module on a tooling version that predates
    # project-tree routing.  Skip instead of exercising the host's
    # stand-in backend and calling it hardware coverage.  pytest is
    # imported inside the branch because boards don't ship it.
    import pytest

    pytest.skip(
        "board-facing acceptance: target this functional_tests directory "
        "with a registered board attached; host interpreters skip",
        allow_module_level=True,
    )

from chumicro_kvstore import KVStore  # noqa: E402 (after the host guard, which must run first)

_TEST_KEY = "functional_test_probe"


def test_value_survives_a_fresh_store_instance() -> None:
    """Write + commit, then read the value back through a new KVStore.

    A fresh instance re-reads the persisted substrate, which is how
    ``run()`` sees the previous boot's counter after a reset.
    """
    store = KVStore()
    previous = store.get(_TEST_KEY, 0)
    store[_TEST_KEY] = previous + 1
    store.commit()

    reread = KVStore()
    try:
        assert reread.get(_TEST_KEY) == previous + 1
    finally:
        reread.pop(_TEST_KEY, None)
        reread.commit()


def test_boot_counter_starts_at_default_when_absent() -> None:
    """A missing key falls back to the ``get`` default.

    First-boot behavior: ``run()`` reads ``boot_count`` with a
    default of 0 before writing 1 back.  Clears the probe key first
    rather than trusting the previous test's cleanup: a power loss
    mid-session can leave it persisted, and this test must pass when
    selected alone (``-k starts_at_default``).
    """
    store = KVStore()
    store.pop(_TEST_KEY, None)
    store.commit()
    assert store.get(_TEST_KEY, 0) == 0
