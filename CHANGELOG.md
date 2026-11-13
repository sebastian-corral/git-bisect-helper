# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository skeleton: `bin/git-autobisect` Bash 3.2 shim that locates the Python
  core through symlinks, honours `AUTOBISECT_PYTHON`, and exits 4 with a hint when
  the interpreter is missing, cannot be run, or is older than Python 3.9.
- `git-autobisect --version` (prints `git-autobisect 0.1.0.dev0`).
- Tooling: `make lint` (ruff check, ruff format --check, shellcheck) and
  `make test` (pytest, bats).
- MIT `LICENSE` and a README stub.
- Architecture Decision Records in `docs/adr/`: an index of the ten planned ADRs
  with a copyable template, plus ADR-0001 (language), ADR-0002 (Bash version)
  and ADR-0010 (pipeline order).
- Continuous integration (`.github/workflows/ci.yml`): GitHub Actions runs
  `make lint` and `make test` on every pull request and every push to `main`,
  on `ubuntu-latest` and `macos-latest` with Python 3.9 and the current stable
  Python. The Ubuntu job for Python 3.9 runs on `ubuntu-24.04`, because
  `ubuntu-latest` (26.04) has no 3.9 build. A new push to a pull request
  cancels the run it supersedes; runs on `main` are never cancelled. The README
  shows the CI status badge.
- Shared data model (`src/autobisect/model.py`): the `Verdict` enum (`good`,
  `bad`, `skip`) and the `CheckConfig`, `CommandResult`, `CheckResult`,
  `PerfMeasurement` and `CommitResult` dataclasses from design section 2. Each
  has `to_dict()` and `from_dict()`, which round-trip through JSON;
  `from_dict()` raises `ValueError` for a missing or unexpected key or a value
  of the wrong type. `CheckConfig` already holds every setting that affects a
  stored result, including those whose flags arrive in M2 and M3, with their
  defaults: clean `git clean -fdx`, 0 retries, flaky policy `strict`, no
  timeout, 5 perf runs and 1 warm-up run.
- Error types and exit codes (`src/autobisect/errors.py`): `AutobisectError`
  carries a `message` and a `hint`, and its subclasses `NotFound`,
  `UsageError`, `RuntimeFailure` and `Interrupted` exit with 1, 3, 4 and 130.
  `verdict_to_exit_code()` maps good, bad and skip to 0, 1 and 125, the codes
  `git bisect run` expects from a check script.
- Top-level error handling in `main()`: an `AutobisectError` is printed on
  stderr as `git-autobisect: error: <message>` and `hint: <hint>`, and its
  exit code returned; Ctrl-C returns 130; any other exception prints a
  one-line `git-autobisect: error: internal error: ...` and returns 4. The
  "not implemented yet" message for anything but `--version` now uses this
  format and still exits 3.
- Argument parsing (`src/autobisect/cli.py`): `parse_args(argv)` turns the
  command line into an `Options` object holding `good`, `bad` (default `HEAD`),
  `verbose`, `stat_only` and a `CheckConfig`. The M1 flags exist: `--bad`,
  `--good`, `--clean`, `--no-clean`, `--setup`, `--build`, `--test` (repeatable,
  order kept), `--run`, `--grep`, `--grep-absent`, `--verbose`, `--stat-only`,
  `-h/--help` and `--version`. Command strings and the `--grep` pattern are
  stored exactly as given. Abbreviated flags are not accepted.
- `git-autobisect --help` (or `-h`): a short description, the flags and four
  usage examples.
- Usage errors exit 3 with a hint: no `--build`, `--test` or `--run` check;
  `--run` without `--grep` or the reverse; `--grep-absent` without `--grep`;
  `--clean` together with `--no-clean`; a `--grep` pattern that is not a valid
  Python regular expression; a missing `--good`; and the errors argparse finds
  itself (an unknown flag, a flag without its value), which no longer exit 2.
- An empty or whitespace-only value for `--setup`, `--build`, `--test`, `--run`
  or `--grep` is a usage error too: an empty command always succeeds and an
  empty pattern matches any output, so the result would mean nothing. For an
  empty `--clean`, the hint suggests `--no-clean`.

### Changed

- `main()` now parses the command line first. A valid command line still ends
  with "bisecting is not implemented yet" (exit 3); an invalid one reports its
  own usage error instead.
