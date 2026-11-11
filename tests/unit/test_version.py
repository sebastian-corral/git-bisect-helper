"""Unit tests for the version string and the `--version` flag."""

from __future__ import annotations

import pytest

from autobisect import __version__
from autobisect.__main__ import main


def test_version_value() -> None:
    """The package version is the expected development version."""
    assert __version__ == "0.1.0.dev0"


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    """`--version` prints `git-autobisect <__version__>` and returns 0."""
    assert main(["--version"]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"git-autobisect {__version__}\n"
    assert captured.err == ""


def test_other_arguments_are_not_implemented(capsys: pytest.CaptureFixture[str]) -> None:
    """Anything but `--version` reports "not implemented yet" on stderr and returns 3."""
    assert main([]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not implemented yet" in captured.err
