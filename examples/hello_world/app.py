"""Hello-world project: proves the deploy chain works end-to-end.

No wifi, no sensors, no third-party imports: just a ``while True``
print loop, the same shape every other project in this workbench
uses.
Useful as your *first* deploy on a freshly-onboarded board: when
``run`` reaches the ``hello`` print, you know

* the host pushed code to the device;
* the synthesized boot shim imported ``app.run`` cleanly;
* ``run()`` was called.

Anything that breaks before that line is a deploy / boot-shim
problem; anything after is your code.

Scaffold a copy with ``python3 run.py new <name> --from examples/hello_world``,
then ``python3 run.py deploy <name>``.
"""

from chumicro_timing import Rate, ticks_ms


def run() -> None:
    """Print a heartbeat once per second for ten seconds, then exit."""
    print("hello from a ChuMicro project")

    # `Rate` answers one question: "is it time yet?"  It never blocks and
    # it never drifts, so the loop below stays free to do other things
    # between ticks.  That is the whole idea behind ChuMicro, and it is
    # why device code here does not call `time.sleep`.
    beat = Rate(1000, ticks_ms())
    ticks_printed = 0

    # This loop spins: with nothing else registered there is nothing to
    # park for, and it only runs for ten seconds.  Every other example
    # hands its loop to `chumicro_runner`, whose `runner.wait(now_ms)`
    # idles the CPU between events.  Same `while True`, one more line
    # inside it.
    while True:
        now_ms = ticks_ms()

        if beat.due(now_ms):
            ticks_printed += 1
            print(f"  tick {ticks_printed}/10")

        if ticks_printed == 10:
            break

    print("hello_world: done")
