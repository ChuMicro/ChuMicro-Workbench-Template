"""System-state snapshot every board reports, regardless of what it does.

Uptime, free RAM, free storage, CPU temperature, battery, reset
reason.  None of it is device-specific, all of it is worth having
on every board, and each field is optional: a probe that the
runtime or the board cannot answer is left out of the dict rather
than reported as a zero or a fake.  A consumer keys on presence.

Every probe is wrapped because the failure modes differ per
runtime and per board, and none of them justify taking a board
offline.  CircuitPython raises ``AttributeError`` for a missing
``cpu.temperature``, MicroPython on some ports raises ``OSError``
from ``statvfs``, and a board with no battery divider simply has
no pin to read.

Usage::

    from face_status import snapshot
    mqtt.publish(face.topic("status"), json.dumps(snapshot(boot_ms)))
"""

_BYTES_PER_KIB = 1024


def _uptime_ms(boot_ticks_ms):
    """Milliseconds since *boot_ticks_ms*, or None if not supplied.

    Uses the same monotonic tick source the runner schedules on, so
    the number stays consistent with handler timing.  ``ticks_diff``
    handles the platform tick rollover that plain subtraction gets
    wrong on MicroPython.
    """
    if boot_ticks_ms is None:
        return None
    try:
        from chumicro_timing import ticks_diff, ticks_ms
        return ticks_diff(ticks_ms(), boot_ticks_ms)
    except (ImportError, OSError):
        return None


def _free_ram_bytes():
    """Free heap in bytes.

    ``gc.mem_free()`` exists on CircuitPython and MicroPython but
    not CPython, where the number has no equivalent meaning and the
    field is simply absent.  Collect first so the figure reflects
    reclaimable memory rather than uncollected garbage.
    """
    try:
        import gc
        gc.collect()
        return gc.mem_free()
    except (ImportError, AttributeError):
        return None


def _free_storage_bytes():
    """Free bytes on the root filesystem.

    Block size times available blocks, from ``statvfs``.  Absent on
    runtimes without ``os.statvfs`` and on ports that raise for a
    read-only or unmounted root.
    """
    try:
        import os
        stats = os.statvfs("/")
        return stats[0] * stats[3]
    except (ImportError, AttributeError, OSError):
        return None


def _cpu_celsius():
    """On-die temperature in Celsius.

    Present on RP2040 / RP2350 and the ESP32 family under
    CircuitPython.  This is die temperature, not ambient: useful as
    a trend and a thermal alarm, not as a room thermometer.
    """
    try:
        import microcontroller
        return float(microcontroller.cpu.temperature)
    except (ImportError, AttributeError, RuntimeError, OSError):
        return None


def _reset_reason():
    """Why the board last restarted, as a lowercase string.

    Worth reporting on every board: a board silently power-cycling
    or tripping its watchdog looks identical to a healthy one in
    the state topic alone, and this is the field that tells them
    apart.
    """
    try:
        import microcontroller
        return str(microcontroller.cpu.reset_reason).rsplit(".", 1)[-1].lower()
    except (ImportError, AttributeError):
        pass
    try:
        import machine
        return str(machine.reset_cause())
    except (ImportError, AttributeError):
        return None


def snapshot(boot_ticks_ms=None, *, battery_volts=None, extra=None):
    """Return the current system state as a flat dict.

    Args:
        boot_ticks_ms: ``ticks_ms()`` captured at boot.  Supply it to
            get ``uptime_ms``; omit and the field is absent.
        battery_volts: Pack voltage, when the board has a divider to
            read one.  The caller reads it because the pin and the
            divider ratio are per-board wiring, not something this
            module can discover.
        extra: Additional fields merged into the result.  For state
            that is system-ish but board-specific (a link RSSI, an
            enclosure thermistor).

    Returns:
        A dict carrying only the fields this board could answer.
    """
    fields = {
        "uptime_ms": _uptime_ms(boot_ticks_ms),
        "free_ram_bytes": _free_ram_bytes(),
        "free_storage_bytes": _free_storage_bytes(),
        "cpu_celsius": _cpu_celsius(),
        "reset_reason": _reset_reason(),
        "battery_volts": battery_volts,
    }
    result = {key: value for key, value in fields.items() if value is not None}
    if extra:
        result.update(extra)
    return result
