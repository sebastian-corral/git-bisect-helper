"""Top-level entry point for git-autobisect.

What it does: provides ``main()``, which the launcher and ``python -m autobisect``
call. For now it only answers ``--version``; bisecting comes in later tasks.
Inputs: command-line arguments.
Outputs: text on stdout/stderr and an integer exit code.
Errors: none raised; problems are reported through the exit code.
"""

from __future__ import annotations

import sys

from autobisect import __version__

PROG = "git-autobisect"
EXIT_OK = 0
EXIT_USAGE = 3


def main(argv: list[str] | None = None) -> int:
    """Run git-autobisect and return its exit code.

    Inputs: ``argv`` is the argument list without the program name; ``None``
    means ``sys.argv[1:]``.
    Outputs: ``--version`` prints ``git-autobisect <version>`` to stdout and
    returns 0. Anything else prints a "not implemented yet" message to stderr
    and returns 3 (usage error).
    Errors: none raised.
    """
    args = sys.argv[1:] if argv is None else argv
    if "--version" in args:
        print(f"{PROG} {__version__}")
        return EXIT_OK
    print(
        f"{PROG}: error: bisecting is not implemented yet in version {__version__}.\n"
        f"{PROG}: Only `{PROG} --version` works for now.",
        file=sys.stderr,
    )
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
