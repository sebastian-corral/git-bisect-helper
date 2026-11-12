"""Unit tests for autobisect.errors and for the error handling in main()."""

from __future__ import annotations

import pickle
from collections.abc import Callable

import pytest

from autobisect import __main__ as entry
from autobisect.errors import (
    AutobisectError,
    Interrupted,
    NotFound,
    RuntimeFailure,
    UsageError,
    verdict_to_exit_code,
)
from autobisect.model import Verdict

ERROR_EXIT_CODES = [
    pytest.param(NotFound, 1, id="NotFound"),
    pytest.param(UsageError, 3, id="UsageError"),
    pytest.param(RuntimeFailure, 4, id="RuntimeFailure"),
    pytest.param(Interrupted, 130, id="Interrupted"),
    pytest.param(AutobisectError, 4, id="AutobisectError"),
]


def raising(exc: BaseException) -> Callable[[list[str]], int]:
    """Return a stand-in for ``_run`` in autobisect.__main__ that raises ``exc``."""

    def run(args: list[str]) -> int:
        """Ignore ``args`` and raise the prepared exception."""
        raise exc

    return run


@pytest.mark.parametrize(("error_class", "code"), ERROR_EXIT_CODES)
def test_error_exit_codes(error_class: type[AutobisectError], code: int) -> None:
    """Each error type is an AutobisectError with its exit code from design section 4."""
    error = error_class("something went wrong.", "Do this about it.")
    assert isinstance(error, AutobisectError)
    assert error.exit_code == code


def test_error_carries_message_and_hint() -> None:
    """An error keeps its message and hint; str() gives the message alone."""
    error = UsageError("--good is required.", "Pass --good <rev>.")
    assert error.message == "--good is required."
    assert error.hint == "Pass --good <rev>."
    assert str(error) == "--good is required."


@pytest.mark.parametrize(("error_class", "code"), ERROR_EXIT_CODES)
def test_error_survives_pickling(error_class: type[AutobisectError], code: int) -> None:
    """Pickling an error keeps its type, message, hint and exit code."""
    copy = pickle.loads(pickle.dumps(error_class("it broke.", "Fix it.")))
    assert type(copy) is error_class
    assert (copy.message, copy.hint, copy.exit_code) == ("it broke.", "Fix it.", code)


@pytest.mark.parametrize(
    ("verdict", "code"),
    [(Verdict.GOOD, 0), (Verdict.BAD, 1), (Verdict.SKIP, 125)],
)
def test_verdict_to_exit_code(verdict: Verdict, code: int) -> None:
    """GOOD, BAD and SKIP map to the exit codes git bisect run reads as good, bad, skip."""
    assert verdict_to_exit_code(verdict) == code


def test_verdict_to_exit_code_rejects_a_string() -> None:
    """A verdict's string value is not a Verdict."""
    with pytest.raises(TypeError, match="expected a Verdict"):
        verdict_to_exit_code("good")


@pytest.mark.parametrize(("error_class", "code"), ERROR_EXIT_CODES)
def test_main_reports_error_and_returns_its_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error_class: type[AutobisectError],
    code: int,
) -> None:
    """main() prints the error and hint lines to stderr and returns the error's exit code."""
    monkeypatch.setattr(entry, "_run", raising(error_class("it broke.", "Fix it.")))
    assert entry.main(["--test", "make test"]) == code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "git-autobisect: error: it broke.\nhint: Fix it.\n"


def test_main_reports_ctrl_c_as_interrupted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """KeyboardInterrupt (Ctrl-C) is reported as an error with a hint and returns 130."""
    monkeypatch.setattr(entry, "_run", raising(KeyboardInterrupt()))
    assert entry.main([]) == 130
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "git-autobisect: error: interrupted by Ctrl-C.\n"
        "hint: Run the same command again to start over.\n"
    )


@pytest.mark.parametrize(
    ("exc", "description"),
    [
        pytest.param(ValueError("bad\n  value"), "ValueError: bad value", id="multi-line-message"),
        pytest.param(RuntimeError(), "RuntimeError", id="no-message"),
    ],
)
def test_main_reports_unexpected_exception_on_one_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exc: Exception,
    description: str,
) -> None:
    """Any other exception prints a one-line internal error and returns 4."""
    monkeypatch.setattr(entry, "_run", raising(exc))
    assert entry.main([]) == 4
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"git-autobisect: error: internal error: {description}"
        " (this is a bug in git-autobisect; please report it)\n"
    )
