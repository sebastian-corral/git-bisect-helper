"""Command-line parsing: turn the arguments into a validated ``Options``.

What it does: defines ``Options`` and ``parse_args()``, which reads the M1 flags
of design section 1 with argparse and checks that they make sense together.
Later milestones add their flags here.
Inputs: the argument list, without the program name.
Outputs: an ``Options`` holding the revisions, the output flags and a
``CheckConfig``. ``--help`` and ``--version`` print to stdout and raise
``SystemExit(0)``.
Errors: ``UsageError`` (exit 3) with a hint for every problem with the command
line, including the ones argparse finds itself.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

from autobisect import __version__
from autobisect.errors import UsageError
from autobisect.model import DEFAULT_CLEAN, CheckConfig

PROG = "git-autobisect"

_USAGE = "git autobisect --good <rev> [--bad <rev>] <checks> [options]"

_DESCRIPTION = """\
Find the commit that introduced a regression. git-autobisect drives
`git bisect run` in a temporary worktree: on every commit it tests, it runs the
clean, setup and build commands and then your checks, and at the end it shows
the first bad commit.

At least one check is required: --build, --test, or --run with --grep.
Every <cmd> is one argument, run by the shell exactly as written, so quote it.
"""

_EPILOG = """\
Examples:
  # Test regression, known good tag
  git autobisect --good v1.4.0 --bad HEAD --build "make" --test "make test"

  # Install dependencies on every commit, then run two test commands in order
  git autobisect --good v2.0 --setup "npm ci" --test "npm run lint" --test "npm test"

  # Output check: bad if the output matches
  git autobisect --good abc123 --build "make" --run "./app --selftest" --grep "Segmentation fault"

  # Output check, inverted: bad if the output no longer matches
  git autobisect --good abc123 --run "./app --selftest" --grep "All checks passed" --grep-absent

Exit codes: 0 first bad commit found, 2 narrowed to a range only, 3 usage or
validation error, 4 runtime error, 130 interrupted.
"""

_HELP_HINT = f"Run `{PROG} --help` to see the flags and some examples."


@dataclass
class Options:
    """Everything the command line asked for, after validation.

    Fields:
        good: the known-good revision, as given (not yet resolved by git).
        check_config: the clean, setup, build, test and run/grep settings.
        bad: the known-bad revision, as given; ``"HEAD"`` unless ``--bad`` is used.
        verbose: stream command output to stderr as well as the log.
        stat_only: show only ``git show --stat`` for the result, not the patch.
    """

    good: str
    check_config: CheckConfig
    bad: str = "HEAD"
    verbose: bool = False
    stat_only: bool = False


class _Parser(argparse.ArgumentParser):
    """An ``ArgumentParser`` that reports problems as ``UsageError``.

    argparse normally prints the usage and exits with code 2; the tool's exit
    code for a usage error is 3 (design section 4), and ``main()`` prints errors
    in one format.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        """Raise a ``UsageError`` for a problem argparse found.

        Inputs: ``message``, argparse's description of the problem, such as
        ``unrecognized arguments: --frobnicate``.
        Outputs: none; it never returns.
        Errors: always ``UsageError``. When a flag is missing its value, the hint
        explains how to pass a value that starts with ``-``.
        """
        hint = _HELP_HINT
        if "expected one argument" in message:
            hint = (
                "Give the flag a value. If the value itself starts with '-', "
                "join it to the flag with '=', for example --grep=-Werror. " + _HELP_HINT
            )
        raise UsageError(f"{message}.", hint)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the M1 flags of design section 1.

    Inputs: none.
    Outputs: the parser. Abbreviated flags are not accepted, so that a flag
    added in a later milestone can never change what an existing command means.
    Errors: none.
    """
    parser = _Parser(
        prog=PROG,
        usage=_USAGE,
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
        add_help=False,
    )

    revisions = parser.add_argument_group("revisions")
    revisions.add_argument(
        "--good",
        metavar="<rev>",
        help="known-good commit, where the checks pass (required in this version)",
    )
    revisions.add_argument(
        "--bad", metavar="<rev>", default="HEAD", help="known-bad commit (default: HEAD)"
    )

    checks = parser.add_argument_group("checks (at least one of --build, --test, --run)")
    checks.add_argument(
        "--clean",
        metavar="<cmd>",
        help=f"runs first on every commit (default: {DEFAULT_CLEAN})",
    )
    checks.add_argument("--no-clean", action="store_true", help="do not clean between commits")
    checks.add_argument(
        "--setup", metavar="<cmd>", help="runs after clean; a failure skips the commit"
    )
    checks.add_argument("--build", metavar="<cmd>", help="a failure skips the commit")
    checks.add_argument(
        "--test",
        metavar="<cmd>",
        action="append",
        default=[],
        dest="tests",
        help="a failure marks the commit bad; repeatable, run in the order given",
    )
    checks.add_argument(
        "--run", metavar="<cmd>", help="command whose output is searched; needs --grep"
    )
    checks.add_argument(
        "--grep",
        metavar="<pattern>",
        help="Python regular expression: the commit is bad if the combined stdout "
        "and stderr of --run matches it",
    )
    checks.add_argument(
        "--grep-absent",
        action="store_true",
        help="invert --grep: the commit is bad if the output does not match",
    )

    output = parser.add_argument_group("output")
    output.add_argument(
        "--verbose",
        action="store_true",
        help="stream command output to stderr as well as the log",
    )
    output.add_argument(
        "--stat-only",
        action="store_true",
        help="show only `git show --stat` for the first bad commit, not the patch",
    )
    output.add_argument("-h", "--help", action="help", help="show this help and exit")
    output.add_argument(
        "--version",
        action="version",
        version=f"{PROG} {__version__}",
        help="show the version and exit",
    )
    return parser


def parse_args(argv: list[str]) -> Options:
    """Parse and validate the command line.

    Inputs: ``argv``, the arguments without the program name.
    Outputs: the ``Options``. Command strings and the pattern are stored exactly
    as received: never split, stripped or re-quoted. ``--help`` and ``--version``
    print to stdout and raise ``SystemExit(0)`` instead of returning.
    Errors: ``UsageError`` with a hint when a flag is unknown or lacks its value;
    ``--clean`` is combined with ``--no-clean``; a command or the pattern is
    empty or only whitespace; ``--run`` and ``--grep`` are not given together;
    ``--grep-absent`` is given without ``--grep``; there is no ``--build``,
    ``--test`` or ``--run`` check; ``--grep`` is not a valid Python regular
    expression; or ``--good`` is missing.
    """
    args = _build_parser().parse_args(argv)

    if args.clean is not None and args.no_clean:
        raise UsageError(
            "--clean and --no-clean cannot be used together.",
            "Pass --clean <cmd> to replace the clean command, or --no-clean to skip "
            "cleaning, but not both.",
        )
    _check_not_blank(args)
    if args.run is not None and args.grep is None:
        raise UsageError(
            "--run needs --grep.",
            "Add --grep <pattern> to say which output marks a commit as bad, or use "
            "--test <cmd> if the exit status of the command is enough.",
        )
    if args.grep is not None and args.run is None:
        raise UsageError(
            "--grep needs --run.",
            "Add --run <cmd>, the command whose output is searched for the pattern.",
        )
    if args.grep_absent and args.grep is None:
        raise UsageError(
            "--grep-absent needs --grep.",
            "Add --run <cmd> and --grep <pattern>, or remove --grep-absent.",
        )
    if args.build is None and not args.tests and args.run is None:
        raise UsageError(
            "no check was given, so there is nothing to tell a good commit from a bad one.",
            "Pass at least one of --build <cmd>, --test <cmd>, or --run <cmd> with "
            "--grep <pattern>. " + _HELP_HINT,
        )
    if args.grep is not None:
        _check_pattern(args.grep)
    if args.good is None:
        raise UsageError(
            "--good is required in this version.",
            "Pass --good <rev>, a commit where the checks pass. Searching for a good "
            "commit automatically arrives in a later version.",
        )

    if args.no_clean:
        clean = None
    elif args.clean is not None:
        clean = args.clean
    else:
        clean = DEFAULT_CLEAN
    return Options(
        good=args.good,
        bad=args.bad,
        verbose=args.verbose,
        stat_only=args.stat_only,
        check_config=CheckConfig(
            clean=clean,
            setup=args.setup,
            build=args.build,
            tests=list(args.tests),
            run=args.run,
            grep=args.grep,
            grep_absent=args.grep_absent,
        ),
    )


def _check_not_blank(args: argparse.Namespace) -> None:
    """Check that no command and no pattern is empty or only whitespace.

    Inputs: ``args``, the namespace argparse returned.
    Outputs: none.
    Errors: ``UsageError`` naming the first of ``--clean``, ``--setup``,
    ``--build``, ``--test``, ``--run`` and ``--grep`` whose value is blank. An
    empty command always succeeds and an empty pattern matches any output, so
    the result of the bisect would mean nothing. For ``--clean`` the hint
    suggests ``--no-clean``.
    """
    commands = [
        ("--clean", args.clean),
        ("--setup", args.setup),
        ("--build", args.build),
        *(("--test", test) for test in args.tests),
        ("--run", args.run),
    ]
    for flag, value in commands:
        if value is None or value.strip():
            continue
        message = f"{flag} was given {_blank(value)} command."
        if flag == "--clean":
            raise UsageError(
                message,
                "Use --no-clean to skip cleaning, or pass the clean command to run, "
                'for example --clean "make clean".',
            )
        raise UsageError(
            message,
            "An empty command always succeeds, so it says nothing about a commit. "
            f'Pass the command to run, for example {flag} "make", or remove {flag}. '
            "If the value comes from a shell variable, check that the variable is set.",
        )
    if args.grep is not None and not args.grep.strip():
        raise UsageError(
            f"--grep was given {_blank(args.grep)} pattern.",
            "An empty pattern matches any output, so it says nothing about a commit. "
            'Pass the text or regular expression to look for, for example --grep "panic". '
            "To match whitespace itself, write it as \\s or [ ].",
        )


def _blank(value: str) -> str:
    """Describe a blank value for an error message.

    Inputs: ``value``, a string that is empty or only whitespace.
    Outputs: ``"an empty"`` for the empty string, ``"a whitespace-only"`` otherwise.
    Errors: none.
    """
    return "an empty" if value == "" else "a whitespace-only"


def _check_pattern(pattern: str) -> None:
    """Check that the ``--grep`` pattern is a valid Python regular expression.

    Inputs: ``pattern``, as given on the command line.
    Outputs: none.
    Errors: ``UsageError`` naming the pattern and the problem ``re`` reports.
    """
    try:
        re.compile(pattern)
    except re.error as exc:
        raise UsageError(
            f"--grep pattern {pattern!r} is not a valid Python regular expression: {exc}.",
            "Fix the pattern. To match text literally, put a backslash before special "
            "characters such as ( ) [ ] . * + ? or |.",
        ) from exc
