"""Error types of git-autobisect and the exit codes they map to.

What it does: defines ``AutobisectError``, the base of every error that ends a run
with a message, a hint and a set exit code, and one subclass for each error exit
code of the tool (design section 4). Also maps a ``Verdict`` to the exit code
that ``git bisect run`` expects from a check script.
Inputs: none; the module only defines types and a function.
Outputs: ``AutobisectError``; ``NotFound`` (exit 1), ``UsageError`` (exit 3),
``RuntimeFailure`` (exit 4) and ``Interrupted`` (exit 130); and
``verdict_to_exit_code``.
Errors: none of its own.
"""

from __future__ import annotations

from autobisect.model import Verdict

# The exit codes of a check script, as `git bisect run` reads them (design section 4).
_VERDICT_EXIT_CODES = {Verdict.GOOD: 0, Verdict.BAD: 1, Verdict.SKIP: 125}


class AutobisectError(Exception):
    """An error that ends the run with a message, a hint and an exit code.

    ``main()`` prints ``git-autobisect: error: <message>`` and ``hint: <hint>``
    to stderr and returns ``exit_code``. Raise one of the subclasses, which set the exit code;
    the base class uses 4, the code for a runtime error.

    Attributes:
        message: what went wrong.
        hint: what the user can do about it.
        exit_code: the tool's exit code for this kind of error.
    """

    exit_code: int = 4

    def __init__(self, message: str, hint: str) -> None:
        """Store the message and the hint.

        Inputs: ``message`` says what went wrong; ``hint`` says what to do about it.
        Outputs: none.
        Errors: none.
        """
        # Both go to Exception.__init__, so that copy and pickle can rebuild the error.
        super().__init__(message, hint)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        """Return the message alone, without the hint.

        Inputs: none.
        Outputs: ``self.message``.
        Errors: none.
        """
        return self.message


class NotFound(AutobisectError):
    """No passing commit was found within ``--max-back`` or the history (exit 1)."""

    exit_code = 1


class UsageError(AutobisectError):
    """A usage, configuration or validation error (exit 3).

    For example: bad flags, an unknown revision, a good commit that is not an
    ancestor of the bad one, a good commit that fails or a bad commit that passes.
    """

    exit_code = 3


class RuntimeFailure(AutobisectError):
    """A runtime error (exit 4): git failed, clean failed or the check script aborted."""

    exit_code = 4


class Interrupted(AutobisectError):
    """The run was stopped by SIGINT, SIGTERM or SIGHUP (exit 130)."""

    exit_code = 130


def verdict_to_exit_code(verdict: Verdict) -> int:
    """Return the exit code with which a check script reports ``verdict``.

    Inputs: ``verdict``, a ``Verdict``.
    Outputs: 0 for GOOD, 1 for BAD and 125 for SKIP, which ``git bisect run``
    reads as good, bad and skip.
    Errors: ``TypeError`` if ``verdict`` is not a ``Verdict``, for example the
    string ``"good"``; pass ``Verdict.GOOD`` instead.
    """
    if not isinstance(verdict, Verdict):
        raise TypeError(f"expected a Verdict (GOOD, BAD or SKIP), got {verdict!r}")
    return _VERDICT_EXIT_CODES[verdict]
