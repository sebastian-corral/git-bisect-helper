"""Top-level entry point for git-autobisect.

What it does: provides ``main()``, which the launcher and ``python -m autobisect``
call. It runs the tool and turns every error into lines on stderr and an exit
code (design section 4). For now the tool only answers ``--version``; bisecting
comes in later tasks.
Inputs: command-line arguments.
Outputs: text on stdout/stderr and an integer exit code.
Errors: none raised; problems are reported through the exit code.
"""

from __future__ import annotations

import sys

from autobisect import __version__
from autobisect.errors import AutobisectError, Interrupted, RuntimeFailure, UsageError

PROG = "git-autobisect"


def main(argv: list[str] | None = None) -> int:
    """Run git-autobisect and return its exit code.

    Inputs: ``argv`` is the argument list without the program name; ``None``
    means ``sys.argv[1:]``.
    Outputs: the exit code. An ``AutobisectError`` is printed to stderr as
    ``git-autobisect: error: <message>`` and ``hint: <hint>`` (the prefix the
    shim and argparse use) and its ``exit_code`` returned; Ctrl-C
    (``KeyboardInterrupt``) is reported the same way as ``Interrupted`` and
    returns 130; any other exception prints one
    ``git-autobisect: error: internal error: ...`` line to stderr and returns 4.
    Errors: none raised.
    """
    args = sys.argv[1:] if argv is None else argv
    try:
        return _run(args)
    except AutobisectError as exc:
        return _report(exc)
    except KeyboardInterrupt:
        return _report(
            Interrupted("interrupted by Ctrl-C.", "Run the same command again to start over.")
        )
    except Exception as exc:
        print(
            f"{PROG}: error: internal error: {_describe(exc)}"
            f" (this is a bug in {PROG}; please report it)",
            file=sys.stderr,
        )
        return RuntimeFailure.exit_code


def _run(args: list[str]) -> int:
    """Do what the command line asks and return the exit code.

    Inputs: ``args``, the arguments without the program name.
    Outputs: ``--version`` prints ``git-autobisect <version>`` to stdout and
    returns 0.
    Errors: ``UsageError`` for anything else, because bisecting is not
    implemented yet.
    """
    if "--version" in args:
        print(f"{PROG} {__version__}")
        return 0
    raise UsageError(
        f"bisecting is not implemented yet in version {__version__}.",
        f"Only `{PROG} --version` works for now.",
    )


def _report(exc: AutobisectError) -> int:
    """Print an error and its hint to stderr and return its exit code.

    Inputs: ``exc``, the error to report.
    Outputs: writes ``git-autobisect: error: <message>`` and ``hint: <hint>``
    to stderr and returns ``exc.exit_code``.
    Errors: none.
    """
    print(f"{PROG}: error: {exc.message}", file=sys.stderr)
    print(f"hint: {exc.hint}", file=sys.stderr)
    return exc.exit_code


def _describe(exc: BaseException) -> str:
    """Describe an unexpected exception on one line.

    Inputs: ``exc``, any exception.
    Outputs: ``<type>: <message>``, with every run of whitespace in the message,
    newlines included, turned into one space; just ``<type>`` when the message
    is empty.
    Errors: none.
    """
    detail = " ".join(str(exc).split())
    name = type(exc).__name__
    return f"{name}: {detail}" if detail else name


if __name__ == "__main__":
    sys.exit(main())
