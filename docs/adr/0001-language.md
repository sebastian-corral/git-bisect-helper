# ADR-0001: Language

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

The tool must run unmodified on macOS and Linux with nothing to install beyond
what a developer machine already has. Three options were compared:

| Option | For | Against |
|---|---|---|
| A. Pure Bash | Single file, no interpreter needed | No JSON, integer-only maths, no reliable timeouts or cleanup, hard to unit test |
| B. Bash + awk | Single file; awk adds decimal maths | awk differs between macOS and Linux; JSON, timeouts, cleanup and testing still weak |
| C. Bash shim + Python core | All of the needs below, from the standard library | Install is a directory; needs `python3` |

## Decision

Option C: a Python 3.9+ core that uses only the standard library, started by a
thin Bash shim (ADR-0002). Python gives us JSON output, decimal maths for perf
figures, subprocess timeouts and process groups, `try`/`finally` cleanup, pytest
unit tests, and identical behaviour on macOS and Linux.

The minimum is 3.9 because that is the `python3` in Apple's Command Line Tools.
Python 3.9 reached end-of-life in October 2025; the minimum will be raised once
Apple ships a newer version.

Rules that follow:

- every module starts with `from __future__ import annotations`;
- no 3.10+ syntax or APIs (no `match`, no `zip(strict=...)`, and so on);
- no pip runtime dependencies;
- CI runs on 3.9 and on the current stable Python.

## Consequences

- Installation copies a directory (`PREFIX/lib/git-autobisect/`) plus the shim,
  not a single file.
- `python3` 3.9+ must be present; the shim checks this and exits 4 with a hint.
- We support an end-of-life Python and give up newer language features until the
  minimum rises. Raising it needs a new ADR and a change to the shim's check.
- CI tests Python 3.9 on Ubuntu 24.04 because `ubuntu-latest` (26.04) has no 3.9
  build.
