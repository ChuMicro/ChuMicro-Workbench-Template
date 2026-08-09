# packages/

Third-party Python source trees you want your projects to import on the device.

## Use it like this

Drop a package's source tree here, e.g.:

    packages/external_lib/
    ├── __init__.py
    └── ...

Then import it from any project:

    import external_lib

## When to use packages/

- A library doesn't ship to PyPI in any installable form (common for MicroPython-only / CircuitPython-only code).
- You want a vendored copy of an upstream fork.
- You need a third-party package that runs on the device alongside your project.

## Gitignore

This folder is gitignored by default: third-party trees are usually big and license-varied, and you may not want them in your repo.  The `packages/.gitignore` ignores everything in here except this README.  If you do want to commit a specific cached package, override per-folder.  Both the directory *and* its contents need re-including: a bare `!my_pinned_package/` un-ignores the folder while `*` still matches every file inside it, and `git add` silently stages nothing.

```gitignore
# packages/.gitignore
*
!.gitignore
!README.md
!my_pinned_package/
!my_pinned_package/**
```
