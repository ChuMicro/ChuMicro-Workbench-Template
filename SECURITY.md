# Security Policy

## What this covers

This repo is a template: starter files, docs, and a thin `run.py`
launcher.  The code that actually opens serial ports, flashes
firmware, and talks to the network lives in the ChuMicro packages
the template installs (`chumicro-workspace`, `chumicro-deploy`, the
device libraries).  A vulnerability in those belongs upstream; report
it through the [ChuMicro security policy](https://github.com/ChuMicro/ChuMicro/blob/main/SECURITY.md).

What belongs here: a problem in the template itself.  The most likely
shape is a credential leak path, since a workbench holds real wifi
passwords and broker auth in `secrets.toml`.  If a shipped file, a
doc, or a default would steer those into git or otherwise expose
them, that is exactly the kind of report this policy wants.

## Reporting

Report privately through GitHub's private vulnerability reporting:

**[Report a vulnerability](https://github.com/ChuMicro/ChuMicro-Workbench-Template/security/advisories/new)**

Please do not open a public issue for a security bug.  ChuMicro is
maintained by one person, so there is no formal response-time
promise: you get an acknowledgment, a reproduction attempt, and
either a fix or an explanation.

## Credentials in your own workbench

The template's defenses you should not undo in your fork:
`secrets.toml`, `settings.toml`, `workspace.yml`, `devices.yml`, and
TLS material (`*.pem`, `*.key`, ...) are gitignored.  Keep them that
way, and keep credentials out of `project_config.toml`, which is
versioned.
