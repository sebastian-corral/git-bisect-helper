#!/usr/bin/env bats
# End-to-end tests for the bin/git-autobisect shim.

setup() {
  repo="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  shim="$repo/bin/git-autobisect"
  fake="$BATS_TEST_TMPDIR/fake-python"
  unset AUTOBISECT_PYTHON
}

# Write an executable fake interpreter whose body is the given shell code.
make_fake_python() {
  printf '#!/bin/sh\n%s\n' "$1" >"$fake"
  chmod +x "$fake"
}

@test "--version prints the version and exits 0" {
  run "$shim" --version
  [ "$status" -eq 0 ]
  [ "$output" = "git-autobisect 0.1.0.dev0" ]
}

@test "--version works through a chain of relative and absolute symlinks" {
  mkdir -p "$BATS_TEST_TMPDIR/a" "$BATS_TEST_TMPDIR/b"
  ln -s "$shim" "$BATS_TEST_TMPDIR/a/real"
  ln -s "../a/real" "$BATS_TEST_TMPDIR/b/git-autobisect"
  run "$BATS_TEST_TMPDIR/b/git-autobisect" --version
  [ "$status" -eq 0 ]
  [ "$output" = "git-autobisect 0.1.0.dev0" ]
}

@test "AUTOBISECT_PYTHON that exits 1 gives exit 4 and a hint" {
  make_fake_python 'exit 1'
  AUTOBISECT_PYTHON="$fake" run "$shim" --version
  [ "$status" -eq 4 ]
  [[ "$output" == *"could not be run"* ]]
  [[ "$output" == *"$fake"* ]]
  [[ "$output" == *"Point AUTOBISECT_PYTHON at a Python 3.9+ interpreter"* ]]
}

@test "an interpreter reporting 3.8 gives exit 4 and the too-old error" {
  make_fake_python 'echo 3.8'
  AUTOBISECT_PYTHON="$fake" run "$shim" --version
  [ "$status" -eq 4 ]
  [[ "$output" == *"Python 3.8 is too old"* ]]
  [[ "$output" == *"needs Python 3.9 or newer"* ]]
}

@test "AUTOBISECT_PYTHON pointing at a missing file gives exit 4 and a hint" {
  AUTOBISECT_PYTHON="$BATS_TEST_TMPDIR/does-not-exist" run "$shim" --version
  [ "$status" -eq 4 ]
  [[ "$output" == *"no Python interpreter found"* ]]
  [[ "$output" == *"unset it to use python3 from PATH"* ]]
}

@test "no python3 on PATH gives exit 4 and an install hint" {
  # A PATH holding only the external tools the shim itself needs, and no python3.
  mkdir "$BATS_TEST_TMPDIR/nopython"
  ln -s "$(command -v dirname)" "$(command -v readlink)" "$BATS_TEST_TMPDIR/nopython/"
  bash_path="$(command -v bash)"
  PATH="$BATS_TEST_TMPDIR/nopython" run "$bash_path" "$shim" --version
  [ "$status" -eq 4 ]
  [[ "$output" == *"no Python interpreter found"* ]]
  [[ "$output" == *"Install Python 3.9 or newer"* ]]
}

@test "shim execs the interpreter with libdir and arguments, without PYTHONPATH" {
  # shellcheck disable=SC2016  # the fake interpreter expands these, not this test
  make_fake_python 'if [ "$1" = "-c" ]; then echo 3.12; exit 0; fi
echo "PYTHONPATH=${PYTHONPATH-unset}"
for arg in "$@"; do echo "arg=$arg"; done'
  unset PYTHONPATH
  AUTOBISECT_PYTHON="$fake" run "$shim" --test 'make check; echo "a b"'
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "PYTHONPATH=unset" ]
  [ "${lines[1]}" = "arg=$repo/bin/../src" ]
  [ "${lines[2]}" = "arg=--test" ]
  [ "${lines[3]}" = 'arg=make check; echo "a b"' ]
}
