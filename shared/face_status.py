"""System-state snapshot every board reports, whatever its job.

Uptime, free RAM, free storage, CPU temperature, battery, reset
reason.  A probe the runtime or board cannot answer leaves its field
out of the dict rather than reporting zero; consumers key on
presence.  Every probe is wrapped because the failure modes differ
per runtime and none of them justify taking a board offline.
"""


def _uptime_ms(boot_ticks_ms):
    """Milliseconds since *boot_ticks_ms*, rollover-safe."""
    if boot_ticks_ms is None:
        return None
    try:
        from chumicro_timing import ticks_diff, ticks_ms
        return ticks_diff(ticks_ms(), boot_ticks_ms)
    except (ImportError, OSError):
        return None


def _free_ram_bytes():
    """Free heap in bytes.  Collects first so the figure means something."""
    try:
        import gc
        gc.collect()
        return gc.mem_free()
    except (ImportError, AttributeError):
        return None


def _free_storage_bytes():
    """Free bytes a user can write on the root filesystem, via ``statvfs``."""
    try:
        import os
        stats = os.statvfs("/")
        # f_frsize * f_bavail: free-block counts are in f_frsize
        # units (not f_bsize, the preferred I/O size, which is 256x
        # larger on some hosts), and f_bavail is what an unprivileged
        # writer actually gets.
        return stats[1] * stats[4]
    except (ImportError, AttributeError, OSError):
        return None


def _cpu_celsius():
    """On-die temperature in Celsius: a trend and an alarm, not ambient."""
    try:
        import microcontroller
        return float(microcontroller.cpu.temperature)
    except (ImportError, AttributeError, RuntimeError, OSError):
        return None


def _reset_reason():
    """Why the board last restarted, as a lowercase string.

    The field that tells a silently power-cycling or watchdog-tripping
    board apart from a healthy one.
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
        boot_ticks_ms: ``ticks_ms()`` captured at boot; omit and
            ``uptime_ms`` is absent.
        battery_volts: Pack voltage, read by the caller (the pin and
            divider ratio are per-board wiring).
        extra: Additional fields merged into the result.

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
