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
