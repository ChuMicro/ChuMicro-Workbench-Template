"""Fetch a URL every so often, without the rest of the board stopping.

This is the file that runs on the board.  It brings wifi up, then asks
for a URL on a repeating schedule and prints what came back.

``_PeriodicFetcher`` below is where the interesting part lives.  It is an
object with two methods the runner calls: ``check(now_ms)`` answers "do I
want a turn?" and ``handle(now_ms)`` takes one.  Neither of them waits
for the network.  A request that is still in flight simply is not
finished yet, and the fetcher says so and returns, which is why wifi can
drop and reconnect in the gap between two fetches without anything here
noticing.

``Deadline`` keeps track of when the next fetch is due.  It is worth
using rather than subtracting timestamps yourself: the millisecond
counter on these boards wraps around, and ``Deadline`` already handles
that.

What you will see::

    periodic_get: connecting ...
    periodic_get: connected at 10.0.0.42
    periodic_get: GET http://example.com/
      -> status=200 bytes=1256
    periodic_get: GET http://example.com/
      -> status=200 bytes=1256
    ...

Things to change:

* ``project_config.toml`` beside this file holds ``fetch.url`` and
  ``fetch.period_ms``.

Scaffold a copy with
``python3 run.py new <name> --from examples/periodic_get``, then
``python3 run.py deploy <name>``.
"""

from chumicro_config import load_runtime_config
from chumicro_requests import HttpClient
from chumicro_runner import Runner
from chumicro_timing import Deadline
from chumicro_wifi import WifiConfig, WifiService, WifiState


class _PeriodicFetcher:
    """Tick-shaped poller: GET the URL every ``period_ms``.

    State machine: ``idle`` (next-fetch ``Deadline`` approaching),
    ``in flight`` (waiting for `_request.done`).  Each tick advances
    whichever phase is current; never blocks.  The first fetch fires
    immediately, then each completed request re-arms the deadline.
    """

    def __init__(self, *, http_client, url, period_ms, timeout_ms=8_000):
        self._client = http_client
        self._url = url
        self._period_ms = period_ms
        self._timeout_ms = timeout_ms
        self._deadline = None
        self._request = None
        self._count = 0

    def check(self, now_ms):
        if self._request is not None:
            return self._request.done
        return self._deadline is None or self._deadline.expired(now_ms)

    def handle(self, now_ms):
        if self._request is None:
            print(f"periodic_get: GET {self._url}")
            self._request = self._client.get(
                self._url, timeout_ms=self._timeout_ms,
            )
            return
        if self._request.error is not None:
            print(f"  -> error: {self._request.error!r}")
        else:
            response = self._request.result
            print(
                f"  -> status={response.status_code} "
                f"bytes={len(response.body)}",
            )
        self._count += 1
        self._request = None
        self._deadline = Deadline(self._period_ms, now_ms)


def run():
    config = load_runtime_config()

    wifi = WifiService(WifiConfig.from_config(config))

    def report_fault(entry, error):
        print("SERVICE_FAULT", entry.service, repr(error))

    runner = Runner(on_handler_error=report_fault)
    runner.add(wifi)

    print("periodic_get: connecting ...")
    while not wifi.connected:
        now_ms = runner.tick()
        if wifi.state == WifiState.FAILED:
            raise SystemExit(f"wifi failed: {wifi.last_error}")
        runner.wait(now_ms)
    print(f"periodic_get: connected at {wifi.ip}")

    client = HttpClient.from_config(config, radio=wifi.adapter.radio)
    runner.add(client)
    runner.add(_PeriodicFetcher(
        http_client=client,
        url=config.require("fetch.url"),
        period_ms=config.get("fetch.period_ms", 30_000),
    ))

    # The main loop.  tick() gives every registered service one small
    # step; wait() then parks the CPU until the next event or deadline
    # instead of spinning.  It never exits, which is what a board
    # program does: it parks between fetches and wakes for the next one.
    while True:
        now_ms = runner.tick()
        runner.wait(now_ms)
