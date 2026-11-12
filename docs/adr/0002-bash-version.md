# ADR-0002: Bash version

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

ADR-0001 puts the logic in Python, but something has to start it: find the
installed core, pick an interpreter, and give a clear error when Python is
missing or too old. That code runs before we know Python works, so it cannot be
Python. macOS still ships Bash 3.2 as `/bin/bash`; newer versions exist only if
the user installed them.

The options were to require Bash 4+ (an extra install on every Mac), to write
the shim in POSIX `sh` (loses `BASH_SOURCE`, which is how the shim finds its own
location through symlinks), or to stay within Bash 3.2.

## Decision

`bin/git-autobisect` stays Bash 3.2 compatible. This is affordable because the
shim does only three things: locate the core relative to its own real path,
check that the interpreter is Python 3.9 or newer, and `exec` it. Everything
else lives in the Python core.

In practice: no associative arrays, no `mapfile`/`readarray`, no `${var,,}` or
`${var^^}`, no `&>>`, no `declare -g`, and no GNU-only tools (for example
`readlink -f`).

## Consequences

- Works with the stock shell on macOS and on any current Linux; no extra install.
- The shim must stay small. New behaviour goes into the Python core, not the shim.
- shellcheck does not detect Bash 4+ features, so compatibility depends on review
  and on running the bats tests under the system Bash on macOS.
