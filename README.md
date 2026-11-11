# git-bisect-helper

`git-autobisect` is a wrapper around `git bisect run` that finds the commit which
introduced a regression. It has a thin Bash entry point and a Python 3.9+ core
that uses only the standard library.

**Status:** early development. Only `git-autobisect --version` works so far. The
accepted design is in [docs/design.md](docs/design.md).

## Requirements

- Bash 3.2 or newer
- Python 3.9 or newer (`python3` on `PATH`, or set `AUTOBISECT_PYTHON`)
- git

## Development

```sh
bin/git-autobisect --version
make lint   # ruff check, ruff format --check, shellcheck
make test   # pytest, bats
```

Development needs `ruff`, `shellcheck`, `pytest` and `bats`.

## License

[MIT](LICENSE)
