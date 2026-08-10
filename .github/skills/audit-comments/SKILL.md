---
name: audit-comments
description: Audit the comments and docstrings in device-deployed Python files (projects/, shared/) against the workbench comment budget.  Use after writing or reworking any .py that ships to a board, or when a file reads as more prose than code.
---

# Audit comments

Files under `projects/` and `shared/` deploy to the board as raw
source.  No mpy-cross step strips anything: the board's compiler
parses every byte at import.  Prose in these files costs flash and
compile-time RAM, so every comment must earn its bytes.

## The budget

The shipped chumicro libraries run about **one prose line per three
lines of code**.  Measure before and after:

```bash
python3 - <<'EOF'
import ast, io, sys, tokenize
path = "shared/face.py"  # target file
src = open(path).read()
doc = sum(
    n.body[0].value.end_lineno - n.body[0].value.lineno + 1
    for n in ast.walk(ast.parse(src))
    if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    and n.body and isinstance(n.body[0], ast.Expr)
    and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)
)
com = len({t.start[0] for t in tokenize.generate_tokens(io.StringIO(src).readline)
           if t.type == tokenize.COMMENT})
blank = sum(1 for line in src.splitlines() if not line.strip())
total = src.count("\n") + 1
code = total - doc - com - blank
print(f"prose={doc + com} code={code} ratio={(doc + com) / max(code, 1):.2f}")
EOF
```

A ratio near 0.3 is the family norm.  Above 1.0 the file is a
comment farm; fix it.

## The test every comment must pass

Read the comment first, then the code.  If the comment did not
prepare you for what the code does, or you had to read the code to
understand the comment, the comment failed.

Then classify each comment and docstring:

- **KEEP**: states the contract (what it does, what it returns, the
  error semantics) or a why the code cannot say.  Leave it.
- **TRIM**: correct, but carrying a removable clause, a narration of
  visible code, or decoration.  Cut the excess.
- **REWRITE**: buried, label-only, or illegible.  Discard it, read
  the code, write a new one from scratch.  Do not salvage word by
  word, and draft the replacement before re-reading the original.
- **DELETE**: restates the line below it, narrates self-evident
  steps, or documents the edit instead of the code.

## Where displaced prose goes

Rationale worth keeping moves to the nearest README (`shared/README.md`,
the project's own README).  READMEs never deploy.  Teaching material
belongs in `examples/` or the hosted docs, not in device source.

## Style sweep

Run the tic regex over the target; hits are candidates for a read,
not automatic verdicts:

```bash
grep -nE '—|→|⇒' <file>
grep -niE 'canonical|idempotent|comprehensive|seamless|robust|leverage|elegant|streamlined|battle-tested|first-class|under the hood|simply put|powerful' <file>
```

Em-dashes are banned in this workbench's prose: replace each with a
period, comma, colon, or parentheses, rewriting so the sentence
reads naturally.  Read every surviving sentence out loud; a sentence
you would not say to a colleague gets rewritten.

## Done means

1. Ratio measured and reported (before and after).
2. Every comment classified; TRIMs and REWRITEs applied.
3. `python3 run.py lint` and `python3 run.py test` still pass.
