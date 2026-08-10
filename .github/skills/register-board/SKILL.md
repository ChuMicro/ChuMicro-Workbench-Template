---
name: register-board
description: Register a physical board in devices.yml so deploys can target it.  Use when the user has a freshly plugged-in board, an empty devices.yml, or `add-device` has surfaced a port or runtime detection issue.
---

# Register a board

`devices.yml` is the workbench's board registry, one entry per
physical board you deploy to.  `python3 run.py deploy` can't ship
without at least one matching entry.  This skill walks through
discovery → adding → verification.

## 1. Discover what the host can see

```bash
python3 run.py discover
```

Lists every serial port the host has noticed.  Output looks like:

```
/dev/cu.usbmodem11401   Pi Pico W
/dev/cu.usbmodem213101  Pi Pico W
/dev/cu.usbmodem211101  Lolin S2 Mini
```

If the user's board isn't here:

- **Cable might be charge-only.**  Try a different USB cable.
  Even a known-working data cable is worth re-plugging.
- **Board might be in bootloader / DFU mode.**  Look for
  `RPI-RP2` or similar mass-storage drives; if so, load the
  `install-firmware` skill and flash a runtime first.
- **macOS may have just lost the port** after an unclean
  unplug.  Pull and re-seat once; if still missing, check
  `ls /dev/cu.*` for clues.

## 2. Pick an id

Convention: `<board-shape>-<runtime>-<location-or-purpose>`.  Examples:

- `pi-pico-w-mp-back-porch`
- `lolin-s2-cp-kitchen`
- `feather-s3-mp-test`

The id is the user's choice.  Anything string-shaped works.  But
`python3 run.py deploy` uses it as the `--device`, so memorable
names pay off.

## 3. Add the entry

```bash
python3 run.py add-device pi-pico-w-mp-back-porch \
    --address /dev/cu.usbmodem213101 \
    --runtime micropython
```

`add-device` does two things:

1. Probes the device over the serial port to capture
   `sys.implementation` (machine + version + UID).  Stores those
   in the `hardware:` block of the entry.  This is the
   "did-the-user-swap-boards" guard.
2. Writes the entry into `devices.yml` preserving comments + key
   order via `ruamel.yaml`.

If `--runtime` is wrong (you said `micropython` but the board's
actually CircuitPython), the probe will surface a clear
mismatch.  Re-run with the correct value.

## 4. It becomes the default automatically

`add-device` sets the first board you register for a runtime as that
runtime's default, so `python3 run.py deploy <project>` targets it
without `--device`.  Adding a second board of the same runtime
leaves the existing default alone.

To change the default later, edit the `defaults:` block in
`devices.yml` directly (there is no `set-default` command):

```yaml
defaults:
  micropython: pi-pico-w-mp-back-porch
  circuitpython: null
  deploy_mode: flash   # default; override to `ram` per-device for unit-style experiments
```

## 5. Verify

```bash
python3 run.py probe                       # uses default
python3 run.py probe --device <id>      # specific board
```

Should print the device's runtime + version + machine + UID.  A
good sanity check before the first deploy.

```bash
python3 run.py devices
```

Shows every entry one-per-line.

## Common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `port not found` / `failed to access` | board unplugged or held by another process | check `lsof <address>` (macOS), close any open REPL/terminal sessions, replug |
| `runtime mismatch: probe says micropython, entry says circuitpython` | `--runtime` was wrong on `add-device` | rerun `add-device` with the right value |
| `no implementation marker` from probe | board hasn't booted into a Python REPL, likely in bootloader, freshly flashed without a `boot.py`, or wedged | run `install-firmware` first; if firmware looks OK, soft-reset the board |
| board flips between `usbmodem...1` and `usbmodem...2` between sessions | macOS sometimes reassigns the port for two physically-identical boards | UID-based matching in `chumicro-deploy` auto-corrects; the warning is informational |

## Rules

- **CIRCUITPY drive paths are resolved at deploy time**: there is
  no `devices.yml` field for them.  `chumicro-deploy` probes
  `microcontroller.cpu.uid` and matches it against `boot_out.txt`
  UID lines on each mounted CIRCUITPY drive, so the right drive is
  auto-selected even when macOS assigns `CIRCUITPY 1` /
  `CIRCUITPY 2` in different orders.
- **Don't edit `devices.yml` while `add-device` is running.**
  The round-trip writer holds an exclusive lock briefly; manual
  edits during that window risk corrupting the file.
- **Re-running `add-device` for an existing id** prompts before
  overwriting the `hardware:` block.  That's the "did you swap
  boards?" guard.  Surface the prompt to the user; don't
  auto-accept.
