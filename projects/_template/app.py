"""Application entrypoint for this project.

The on-device boot module imports ``projects.<name>.app`` and calls
``run()``.  Anything ``app.py`` does at import time runs on every
boot before ``run()`` is called.  Keep heavyweight setup inside
``run()`` so a slow init doesn't trip the boot watchdog.
"""


def run() -> None:
    """Main loop / one-shot for this project."""
    print("hello from a ChuMicro project")

    # Most projects end with the main loop written out instead.  Build
    # your services, hand them to a Runner, then turn the loop by hand:
    #
    #     from chumicro_runner import Runner
    #
    #     runner = Runner()
    #     runner.add(wifi)                       # your services
    #     runner.add_periodic(read_sensor, period_ms=1000)
    #
    #     while True:
    #         now_ms = runner.tick()   # every service takes one small step
    #         runner.wait(now_ms)      # then the CPU parks until it's needed
    #
    # examples/wifi_only/ is that skeleton filled in and deployable.
