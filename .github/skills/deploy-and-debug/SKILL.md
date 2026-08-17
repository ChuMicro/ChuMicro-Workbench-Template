---
name: deploy-and-debug
description: Deploy a project, follow REPL output, and diagnose common failure modes.  Use when a deploy fails, when the user wants to see what their project is printing on-device, or when a project isn't behaving as expected after a successful deploy.
---

# Deploy and debug

The deploy → REPL → fix cycle is the inner loop of workbench
work.  `chumicro-deploy`'s recovery layer classifies most failures
into precise messages.  Read them before guessing.

## The happy path

```bash
python3 run.py deploy my_project
```

A successful deploy stages the payload, restarts the board into
the new code, and exits.  It does not follow the board's output on
its own (most projects then drive a `runner.run_until(...)` loop
on-device indefinitely).

To deploy *and* follow the board's output in one step, add `--tail`:

```bash
python3 run.py deploy my_project --tail       # deploy, then tail 30s
python3 run.py deploy my_project --tail 60    # override the window
```

To poke at an already-running board (`repl` never stages code):

```bash
python3 run.py repl              # interactive (Ctrl-X to exit)
python3 run.py repl --tail 30    # standalone tail, no deploy
```

## When deploy fails: what the message means

`chumicro-deploy` classifies failures into named kinds.  When
you see one of these, the message itself usually tells you what
to do:

| `DeployFailureKind` | What it means | First fix |
|---|---|---|
| `PORT_UNAVAILABLE` | serial port busy or missing (board unplugged, port held by another tool, board is in bootloader) | close any open REPL / tool against the same port; replug the board; if it's in the bootloader run `python3 run.py install-firmware` first |
| `RAW_REPL_UNRESPONSIVE` | the device's raw REPL didn't respond to the handshake | tap the RESET button or replug; if it persists, soft-reset via REPL Ctrl-D before next deploy |
| `COMMAND_TIMED_OUT` | the board stopped answering part way through a command, usually a wedged USB-CDC serial link | unplug the USB cable and plug it back in; a wedged link does not clear on its own, so a retry without the replug just waits out the same timeout.  If it stays quiet, `python3 run.py reset-board --yes --device <id>` or reflash with `install-firmware` |
| `NO_PYTHON_RUNTIME` | the board answers, but what's on it isn't CircuitPython or MicroPython (Arduino, a raw bootloader, unknown firmware) | flash a runtime first: `python3 run.py install-firmware --device <id> --method <uf2|esptool>` (uf2 for RP2040 / RP2350, esptool for the ESP32 family), then re-run the deploy.  Flashing overwrites whatever the board runs today, so back it up if it matters |
| `MACOS_FSKIT_WEDGED` | macOS's FSKit wedged on a FAT12 error (CP only) | the message prints an exact `sudo killall … && launchctl kickstart -k …` recovery command.  Paste it; if persistent, reboot the Mac |
| `CIRCUITPY_DRIVE_MISSING` | CP flash mode but the CIRCUITPY USB drive isn't mounted (or is mounted but not writable) | wait a few seconds for macOS to mount; check `/Volumes/`; force-eject + replug |
| `FLASH_COPY_FAILED` | rsync to CIRCUITPY balked mid-copy (drive full, payload too big, I/O error) | check free space on `/Volumes/CIRCUITPY*`; trim the deploy or wipe the drive; if I/O errors persist replug |
| `FAT_VOLUME_CORRUPT` | the CIRCUITPY drive's filesystem carries torn directory entries the host can neither read nor delete | reformat the board: `python3 run.py reset-board --yes --device <id>`, which wipes every user file on it.  Don't spend time on in-place repair; `rm` and rsync both fail on torn entries with `Invalid argument` |
| `BOOTSTRAP_EXEC_FAILED` | the staged code raised on import / first run | the message includes the traceback from the device.  Read it before guessing |
| `UNRESOLVED_IMPORT` | an import in the payload points at no deployed file and isn't a known device built-in, so the deploy was refused before staging anything | the message names each importing file and the module it couldn't find.  Fix the typo, move the module somewhere the deploy searches, or wrap a deliberately optional import in `try: import foo` / `except ImportError:` |
| `TRACEBACK_RETURNED` | code deployed cleanly but the entrypoint raised on the device | not retryable by replugging.  Read the traceback in the deploy output and fix the source |
| `INSUFFICIENT_MEMORY` | the inline (RAM-mode) payload exceeds the board's free heap | switch to `deploy_mode: flash` for this device, or split a fat module into smaller files |
| `CONFIGURATION_ERROR` | the device or deploy was misconfigured (wrong runtime, bad device-file entry) | read the message: it points at the specific field; fix `devices.yml` or the CLI flags |

If the failure doesn't match any of these, the deploy output
will include the raw transport error.  Read it carefully before
guessing.

## When the deploy succeeds but the project misbehaves

These are the most common patterns; each maps to a precise fix:

### "messages stop after the first publish" / "boot counter doesn't increment"

The project depends on persistent on-device state (a kvstore
counter, a connection that needs the runtime config msgpack at a
canonical absolute path, etc.) but the device is in **RAM mode**.

In RAM mode the host mounts source as `/remote/` on the device,
so absolute paths like `/runtime_config.msgpack` aren't visible.
Switch to flash mode for this device:

```yaml
# devices.yml
- id: my-board
  ...
  deploy_mode: flash    # add or uncomment this line
```

### "ImportError: no module named X" on boot

The deploy didn't ship `X` to the device.  Read the error's
module path and check:

- Is `X` part of a chumicro library?  The deploy's import-graph
  walker should have picked it up.  If not, surface the gap as
  an upstream issue.
- Is `X` a project-local helper under `projects/<name>/`?  Make sure
  it's imported with the right path (`from . import X` for
  same-dir, or under `shared/` for cross-project code).
- Is `X` an external package?  For device-side code the deploy
  ships, pip installs don't help.  Drop the package's source tree
  under `packages/` so the import-graph walker picks it up.
  (`pyproject.toml`'s deps are host-side only, and that file is
  tool-owned: `update` rewrites it, so re-apply any additions
  from `git diff` afterwards.)

### "wifi connected but mqtt never publishes"

Two common causes:

1. **Broker unreachable from the device's network.**  If the
   broker is on the host (`mosquitto` running locally), the
   device's wifi network must route to the host's LAN IP.  Try
   `mosquitto_pub` from the host targeting the host's own LAN IP
   (not `127.0.0.1`).  If that fails, the broker isn't bound to
   the right interface.

2. **TLS handshake failed silently.**  TLS errors on MicroPython
   can manifest as the connection just stopping.  If the cert
   chain is the problem, the message is "invalid cert"; if the
   device clock is wrong, "validity starts in the future."  Set
   the device RTC after wifi-up (NTP-style) before opening any
   TLS sockets.

### "the project crashes on boot with no clear error"

Connect via REPL and force a soft reset:

```bash
python3 run.py repl
# then Ctrl-D inside the REPL to soft-reboot
```

The boot output will show the traceback.  If the traceback
points at `projects/<name>/app.py`, that's your code.  If it's
under `chumicro_*`, file an upstream issue with the traceback.

### "I can't even tell if the deploy ran"

Add a print at the top of `run()`:

```python
def run():
    print("my_project: boot")
    ...
```

Re-deploy.  If you see `my_project: boot` in the REPL output, the
deploy fired.  If not, the device isn't running your code.
Check the entrypoint (`code.py` on CP, `main.py` on MP).

## Useful diagnostic patterns

These call `mpremote` directly instead of going through `run.py`, which is a deliberate escape hatch for when the tooling itself is what you're diagnosing, not a license to skip `run.py` for everyday work.

```bash
# What's actually on the device's flash?
.venv/bin/python -m mpremote connect <port> fs ls /

# Check the device's runtime config
.venv/bin/python -m mpremote connect <port> fs cat /runtime_config.msgpack | xxd | head

# Run a one-off command to inspect device state
.venv/bin/python -m mpremote connect <port> exec "import sys; print(sys.implementation)"
```

## Rules

- **Read the deploy output before guessing.**  The recovery
  layer's messages are precise; they're usually the answer.
- **Surface the failure to the user verbatim**: don't paraphrase
  errors.  The exact `OSError(...)` or `ImportError: ...` text is
  what diagnostic searches latch onto.
- **Don't repeat-deploy on the same failure.**  If the error
  classifies, fix the root cause; if it doesn't, escalate to the
  user.
- **Try `install-firmware` early** for bootloader-detected /
  no-firmware errors.  Many "broken board" reports turn out to
  be a fresh-flash device with no Python firmware loaded.
