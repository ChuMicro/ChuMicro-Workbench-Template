---
name: install-firmware
description: Flash CircuitPython or MicroPython onto a board that is fresh from the factory, stuck in bootloader mode, or due for a runtime upgrade.  Use when `discover` / `add-device` reports no firmware, when the board shows up as a UF2 drive instead of a serial port, or when the user asks to install or upgrade the runtime.
---

# Install firmware

A board can't join the workbench until it runs CircuitPython or
MicroPython.  `python3 run.py install-firmware` downloads a firmware
image and flashes it; `upgrade-firmware` is an alias of the same flow
(flashing over existing firmware *is* an upgrade, the tool doesn't
branch).  This skill walks through picking the method, getting the
image, and verifying the board comes back.

## 1. Figure out what state the board is in

```bash
python3 run.py discover     # serial ports the host can see
ls /Volumes/               # macOS: look for RPI-RP2 / <BOARD>BOOT drives
```

Three states matter:

| State | What you see | What it means |
|---|---|---|
| Python REPL reachable | board listed by `discover`, `probe` answers | firmware present, this is the *upgrade* path |
| UF2 bootloader | a mass-storage drive with `INFO_UF2.TXT` (e.g. `RPI-RP2`) | no runtime (or user held BOOTSEL); flash with `--method uf2` |
| Serial opens, no probe response | port exists but probing hangs | usually an ESP32-family chip with no Python firmware; flash with `--method esptool`, typically with `--erase` on first flash |

`python3 run.py bootstrap` (the onboarding wizard) runs this
classification for you and prints the exact next command.  For a
board in an unknown state, starting there is usually faster than
diagnosing by hand.

## 2. Pick the method

- **`--method uf2`**: RP2040 / RP2350 and other boards with a UF2
  bootloader.  The board must be *in* the bootloader (hold BOOTSEL
  while plugging in, or double-tap reset on many boards) so its UF2
  drive is mounted.  If the drive mounts somewhere unusual, point at
  it with `--bootloader-drive <path>`.
- **`--method esptool`**: ESP32 family (ESP32-S2, S3, C3, ...).
  Flashes over serial, no bootloader drive involved.  Add `--erase`
  to erase the flash before writing (recommended for a first flash or
  a runtime *switch*, e.g. MicroPython → CircuitPython); `--offset`
  overrides the write offset (default `0x0`) for images that document
  a different one.

## 3. Flash

For a board already registered in `devices.yml`, the firmware URL is
derived automatically from the entry's hardware fields (CircuitPython:
latest stable for the board id; MicroPython: a curated machine→board
map; or the entry's `hardware.firmware_source` override):

```bash
python3 run.py install-firmware --method uf2 --device <id>
python3 run.py install-firmware --method uf2 --device <id> --allow-prerelease   # CP only: include -rc/-beta builds
```

For a fresh board with no entry to derive from, pass the image URL
explicitly (get it from the board's page on circuitpython.org/downloads
or micropython.org/download):

```bash
python3 run.py install-firmware --method uf2 --url <firmware-url>
python3 run.py install-firmware --method esptool --erase --url <firmware-url>
```

The flash prints progress milestones.  A multi-MB download plus write
can take a minute, so silence does not mean it hung unless a minute
has passed with no new milestone.

## 4. Verify the board came back

After flashing, the board reboots into the new runtime and
re-enumerates as a serial port (give macOS a few seconds):

```bash
python3 run.py discover                  # port is back?
python3 run.py add-device <id> --address <port>   # fresh board: register it now
python3 run.py probe --device <id>       # registered board: confirm runtime + version
```

Re-running `add-device` for an existing id after a runtime *switch*
prompts before overwriting the `hardware:` block.  That's expected;
confirm it, since the runtime really did change.

## Related: wiping without reflashing

If the goal is a clean filesystem rather than new firmware (flash
filled up with stage residue, hand-edited `boot.py` misbehaving),
don't reflash.  Wipe:

```bash
python3 run.py reset-board --device <id> --yes
```

That erases every user file the runtime can see (including
`settings.toml` and `boot.py`) without touching the firmware or
deploying anything.  It refuses to run without `--yes`, and it's a
no-op for devices configured in RAM/mount mode.

## Common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `--url omitted and no device entry to derive from` | fresh board, nothing registered | pass `--url` explicitly, or register the board first if it's probe-able |
| uf2 flash can't find the bootloader drive | board isn't in bootloader mode, or the drive mounted late | re-enter the bootloader (BOOTSEL / double-tap reset), wait for the drive, or pass `--bootloader-drive <path>` |
| esptool flash fails to connect | port held by another process, or the chip isn't in download mode | close open REPL/tools on the port; hold the board's BOOT button while resetting, then retry |
| flashed OK but the port never comes back | board booted into a runtime that exposes no CDC serial, or needs a replug | replug the board; check `/Volumes/CIRCUITPY` (CP boards mount a drive even when serial is slow to appear) |
| download fails with a 404 | derived/typed URL points at a build that moved | pass a fresh `--url` from the board's official download page |

## Rules

- **Don't guess `--method`.**  uf2 vs esptool is a property of the
  chip family; a wrong method fails confusingly rather than safely.
  If unsure, run `bootstrap` and let the classifier name it.
- **Read the failure message before retrying.**  Flash errors carry
  their own recovery guidance (bootloader-mode steps, missing
  esptool, wrapped download errors).  Surface it to the user
  verbatim.
- **`reset-board` is destructive.**  Never pass `--yes` on the
  user's behalf without confirming they understand every user file
  on the board is erased.
- **After a runtime switch, re-probe.**  `devices.yml` caches the
  runtime + firmware version; a board flashed from MicroPython to
  CircuitPython (or vice versa) needs `add-device` re-run so deploys
  target it correctly.
