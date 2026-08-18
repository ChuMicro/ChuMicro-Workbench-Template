# `hello_world`

Trivial first deploy.  Prints a heartbeat once per second for ten
seconds, then exits cleanly.

## Why this example exists

Brand-new boards often surface deploy-pipeline issues: wrong
runtime, board not in `devices.yml`, wifi credentials still set to
`replace-me`.  Running a wifi-free print loop first proves the host
→ device path works *before* you bring the network stack into the
picture.  When `hello_world` reaches its tenth tick, anything else
that breaks is your code, not the deploy.

## Try it

```
python3 run.py new my_first_project --from examples/hello_world
python3 run.py deploy my_first_project --tail 15
```

Expected output:

```
hello from a ChuMicro project
  tick 1/10
  tick 2/10
  ...
hello_world: done
```

## What it uses

| Library | Why |
|---|---|
| `chumicro-timing` | `ticks_ms` plus `Rate`, the non-blocking "is it time yet?" timer that device code uses instead of `time.sleep` |

That's it.  No wifi, no sockets, no MQTT, no I/O.  Pure host
language plus `chumicro-timing`.

## What's next

Once `hello_world` ships, the natural follow-on is
[`wifi_only/`](../wifi_only/): same `while True` loop, but it hands
the loop to a `Runner` and brings the wifi service up with
credentials from the workbench's gitignored `secrets.toml`.
