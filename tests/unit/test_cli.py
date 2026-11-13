"""Unit tests for autobisect.cli and for the way main() uses it."""

from __future__ import annotations

import shlex

import pytest

from autobisect import __version__
from autobisect.__main__ import main
from autobisect.cli import Options, parse_args
from autobisect.errors import UsageError
from autobisect.model import DEFAULT_CLEAN, CheckConfig

# The smallest valid command line; tests add the flags they are about.
MINIMAL = ["--good", "v1.4.0", "--test", "make test"]

# A command with spaces, both kinds of quotes, semicolons and other shell syntax.
AWKWARD = """  sh -c 'echo "a  b"; exit 1' ; make  test && echo it\\'s > "out file" | cat  """


def usage_error(argv: list[str]) -> UsageError:
    """Parse ``argv``, which must be rejected, and return the ``UsageError`` raised."""
    with pytest.raises(UsageError) as raised:
        parse_args(argv)
    return raised.value


def test_defaults() -> None:
    """With only --good and one check, everything else has its default."""
    options = parse_args(MINIMAL)
    assert options == Options(
        good="v1.4.0",
        bad="HEAD",
        verbose=False,
        stat_only=False,
        check_config=CheckConfig(tests=["make test"]),
    )
    assert options.check_config.clean == DEFAULT_CLEAN
    assert options.check_config.setup is None
    assert options.check_config.build is None
    assert options.check_config.run is None
    assert options.check_config.grep is None
    assert options.check_config.grep_absent is False


def test_good_and_bad() -> None:
    """--good and --bad are stored as given."""
    options = parse_args(["--good", "v1.4.0", "--bad", "feature~3", "--test", "make test"])
    assert options.good == "v1.4.0"
    assert options.bad == "feature~3"


def test_clean_replaces_the_default() -> None:
    """--clean sets the clean command."""
    assert parse_args([*MINIMAL, "--clean", "make distclean"]).check_config.clean == (
        "make distclean"
    )


def test_no_clean_disables_cleaning() -> None:
    """--no-clean sets the clean command to None."""
    assert parse_args([*MINIMAL, "--no-clean"]).check_config.clean is None


def test_setup() -> None:
    """--setup sets the setup command."""
    assert parse_args([*MINIMAL, "--setup", "npm ci"]).check_config.setup == "npm ci"


def test_build_alone_is_a_check() -> None:
    """--build sets the build command and is enough of a check on its own."""
    config = parse_args(["--good", "v1.4.0", "--build", "make"]).check_config
    assert config.build == "make"
    assert config.tests == []


def test_run_and_grep_are_a_check() -> None:
    """--run and --grep set the output check and are enough on their own."""
    config = parse_args(
        ["--good", "abc123", "--run", "./app --selftest", "--grep", "Segmentation fault"]
    ).check_config
    assert config.run == "./app --selftest"
    assert config.grep == "Segmentation fault"
    assert config.grep_absent is False


def test_grep_absent() -> None:
    """--grep-absent inverts the output check."""
    config = parse_args(
        ["--good", "abc123", "--run", "./app", "--grep", "ok", "--grep-absent"]
    ).check_config
    assert config.grep_absent is True


def test_verbose() -> None:
    """--verbose sets verbose and leaves stat_only alone."""
    options = parse_args([*MINIMAL, "--verbose"])
    assert options.verbose is True
    assert options.stat_only is False


def test_stat_only() -> None:
    """--stat-only sets stat_only and leaves verbose alone."""
    options = parse_args([*MINIMAL, "--stat-only"])
    assert options.stat_only is True
    assert options.verbose is False


def test_all_flags_together() -> None:
    """Every M1 flag can be combined, in any position."""
    options = parse_args(
        [
            "--stat-only",
            "--run",
            "./app",
            "--test",
            "make test",
            "--bad",
            "v2.0",
            "--grep",
            "panic",
            "--setup",
            "npm ci",
            "--verbose",
            "--build",
            "make",
            "--clean",
            "make clean",
            "--good",
            "v1.0",
            "--grep-absent",
        ]
    )
    assert options == Options(
        good="v1.0",
        bad="v2.0",
        verbose=True,
        stat_only=True,
        check_config=CheckConfig(
            clean="make clean",
            setup="npm ci",
            build="make",
            tests=["make test"],
            run="./app",
            grep="panic",
            grep_absent=True,
        ),
    )


def test_later_milestone_settings_keep_their_defaults() -> None:
    """Settings whose flags arrive later have the defaults of CheckConfig."""
    config = parse_args(MINIMAL).check_config
    default = CheckConfig()
    assert config.retries == default.retries
    assert config.flaky_policy == default.flaky_policy
    assert config.timeout is None
    assert config.timeout_skip is False
    assert config.perf is None


def test_repeated_test_keeps_order() -> None:
    """--test may be repeated; the commands are kept in the order given."""
    options = parse_args(
        ["--test", "c", "--good", "v1", "--test", "a", "--build", "make", "--test", "b"]
    )
    assert options.check_config.tests == ["c", "a", "b"]


def test_repeated_test_keeps_duplicates() -> None:
    """The same test command given twice is stored twice."""
    assert parse_args(["--good", "v1", "--test", "t", "--test", "t"]).check_config.tests == [
        "t",
        "t",
    ]


def test_each_parse_gets_its_own_test_list() -> None:
    """The tests of one parse do not leak into the next one."""
    first = parse_args(["--good", "v1", "--test", "a"])
    second = parse_args(["--good", "v1", "--test", "b"])
    assert first.check_config.tests == ["a"]
    assert second.check_config.tests == ["b"]


@pytest.mark.parametrize("flag", ["--clean", "--setup", "--build", "--test", "--run"])
def test_command_is_stored_byte_for_byte(flag: str) -> None:
    """A command with spaces, quotes and semicolons is stored unchanged."""
    argv = [*MINIMAL, "--run", "./app", "--grep", "x"]
    config = parse_args([*argv, flag, AWKWARD]).check_config
    stored = {
        "--clean": config.clean,
        "--setup": config.setup,
        "--build": config.build,
        "--test": config.tests[-1],
        "--run": config.run,
    }[flag]
    assert stored == AWKWARD


def test_command_given_with_equals_is_stored_byte_for_byte() -> None:
    """`--test=<cmd>` stores everything after the first `=`, unchanged."""
    command = "X=1 make test; echo 'a=b'"
    config = parse_args(["--good", "v1", f"--test={command}"]).check_config
    assert config.tests == [command]


def test_pattern_is_stored_byte_for_byte() -> None:
    """The --grep pattern is stored unchanged, spaces and backslashes included."""
    pattern = r"  ^error\[E\d+\]: 'x';  $"
    config = parse_args(["--good", "v1", "--run", "./app", "--grep", pattern]).check_config
    assert config.grep == pattern


def test_value_starting_with_dash_needs_equals() -> None:
    """A value that looks like a flag is rejected with a hint, and works with `=`."""
    error = usage_error(["--good", "v1", "--run", "make", "--grep", "-Werror"])
    assert "--grep" in error.message
    assert "--grep=-Werror" in error.hint
    config = parse_args(["--good", "v1", "--run", "make", "--grep=-Werror"]).check_config
    assert config.grep == "-Werror"


def test_at_sign_is_not_expanded() -> None:
    """An argument starting with `@` is a plain value, not a file of arguments."""
    assert parse_args(["--good", "@{-1}", "--test", "make test"]).good == "@{-1}"


# A valid command line with an output check, to which a blank value is added.
WITH_RUN = [*MINIMAL, "--run", "./app", "--grep", "panic"]

BLANK_COMMANDS = [
    pytest.param(flag, value, id=f"{flag} {value!r}")
    for flag in ["--setup", "--build", "--test", "--run"]
    for value in ["", "   ", " \t\n"]
]


@pytest.mark.parametrize(("flag", "value"), BLANK_COMMANDS)
def test_blank_command_is_rejected(flag: str, value: str) -> None:
    """An empty or whitespace-only command is a usage error that names the flag."""
    error = usage_error([*WITH_RUN, flag, value])
    kind = "an empty" if value == "" else "a whitespace-only"
    assert error.exit_code == 3
    assert error.message == f"{flag} was given {kind} command."
    assert "An empty command always succeeds" in error.hint
    assert f"or remove {flag}" in error.hint


@pytest.mark.parametrize("value", ["", "   ", " \t\n"])
def test_blank_clean_suggests_no_clean(value: str) -> None:
    """An empty or whitespace-only --clean is a usage error whose hint is --no-clean."""
    error = usage_error([*MINIMAL, "--clean", value])
    kind = "an empty" if value == "" else "a whitespace-only"
    assert error.exit_code == 3
    assert error.message == f"--clean was given {kind} command."
    assert error.hint.startswith("Use --no-clean to skip cleaning")


@pytest.mark.parametrize("value", ["", "   ", " \t\n"])
def test_blank_pattern_is_rejected(value: str) -> None:
    """An empty or whitespace-only --grep pattern is a usage error."""
    error = usage_error([*MINIMAL, "--run", "./app", "--grep", value])
    kind = "an empty" if value == "" else "a whitespace-only"
    assert error.exit_code == 3
    assert error.message == f"--grep was given {kind} pattern."
    assert "An empty pattern matches any output" in error.hint
    assert "\\s or [ ]" in error.hint


def test_blank_test_among_valid_ones_is_rejected() -> None:
    """One blank --test is rejected even when the other test commands are fine."""
    error = usage_error(["--good", "v1", "--test", "make test", "--test", "", "--test", "x"])
    assert error.message == "--test was given an empty command."


def test_blank_command_given_with_equals_is_rejected() -> None:
    """`--build=` is an empty command too."""
    assert usage_error([*MINIMAL, "--build="]).message == "--build was given an empty command."


def test_blank_test_does_not_count_as_a_check() -> None:
    """A lone blank --test reports the blank command, not a missing check."""
    assert usage_error(["--good", "v1", "--test", " "]).message == (
        "--test was given a whitespace-only command."
    )


def test_surrounding_whitespace_is_kept() -> None:
    """A command with leading and trailing spaces is valid and stored unchanged."""
    assert parse_args(["--good", "v1", "--test", "  make test  "]).check_config.tests == [
        "  make test  "
    ]


USAGE_ERRORS = [
    pytest.param(
        ["--good", "v1"],
        "no check was given",
        "--build <cmd>, --test <cmd>, or --run <cmd> with --grep <pattern>",
        id="no check",
    ),
    pytest.param(
        ["--good", "v1", "--setup", "npm ci", "--clean", "make clean"],
        "no check was given",
        "--build <cmd>, --test <cmd>, or --run <cmd> with --grep <pattern>",
        id="setup and clean are not checks",
    ),
    pytest.param([], "no check was given", "Pass at least one of", id="no arguments"),
    pytest.param(
        ["--good", "v1", "--run", "./app"],
        "--run needs --grep.",
        "Add --grep <pattern>",
        id="run without grep",
    ),
    pytest.param(
        ["--good", "v1", "--test", "t", "--run", "./app"],
        "--run needs --grep.",
        "Add --grep <pattern>",
        id="run without grep, with another check",
    ),
    pytest.param(
        ["--good", "v1", "--grep", "panic"],
        "--grep needs --run.",
        "Add --run <cmd>",
        id="grep without run",
    ),
    pytest.param(
        ["--good", "v1", "--test", "t", "--grep", "panic"],
        "--grep needs --run.",
        "Add --run <cmd>",
        id="grep without run, with another check",
    ),
    pytest.param(
        ["--good", "v1", "--test", "t", "--grep-absent"],
        "--grep-absent needs --grep.",
        "Add --run <cmd> and --grep <pattern>, or remove --grep-absent",
        id="grep-absent without grep",
    ),
    pytest.param(
        [*MINIMAL, "--clean", "make clean", "--no-clean"],
        "--clean and --no-clean cannot be used together.",
        "but not both",
        id="clean with no-clean",
    ),
    pytest.param(
        [*MINIMAL, "--no-clean", "--clean", "make clean"],
        "--clean and --no-clean cannot be used together.",
        "but not both",
        id="no-clean before clean",
    ),
    pytest.param(
        ["--good", "v1", "--run", "./app", "--grep", "Segfault ("],
        "--grep pattern 'Segfault (' is not a valid Python regular expression",
        "put a backslash before special characters",
        id="invalid regex",
    ),
    pytest.param(
        ["--test", "make test"],
        "--good is required in this version.",
        "Searching for a good commit automatically arrives in a later version",
        id="missing good",
    ),
    pytest.param(
        [*MINIMAL, "--frobnicate"],
        "unrecognized arguments: --frobnicate.",
        "git-autobisect --help",
        id="unknown flag",
    ),
    pytest.param(
        [*MINIMAL, "--retries", "3"],
        "unrecognized arguments: --retries 3.",
        "git-autobisect --help",
        id="later-milestone flag",
    ),
    pytest.param(
        [*MINIMAL, "--verb"],
        "unrecognized arguments: --verb.",
        "git-autobisect --help",
        id="abbreviated flag",
    ),
    pytest.param(
        [*MINIMAL, "src/parser"],
        "unrecognized arguments: src/parser.",
        "git-autobisect --help",
        id="positional argument",
    ),
    pytest.param(
        ["--good", "v1", "--test"],
        "argument --test: expected one argument.",
        "Give the flag a value",
        id="flag without its value",
    ),
]


@pytest.mark.parametrize(("argv", "message", "hint"), USAGE_ERRORS)
def test_usage_errors(argv: list[str], message: str, hint: str) -> None:
    """Each invalid command line raises UsageError (exit 3) with its message and hint."""
    error = usage_error(argv)
    assert error.exit_code == 3
    assert message in error.message
    assert hint in error.hint


def test_invalid_regex_error_says_what_is_wrong() -> None:
    """The invalid-regex message includes the problem that `re` reports."""
    error = usage_error(["--good", "v1", "--run", "./app", "--grep", "a(b"])
    assert "unterminated subpattern" in error.message


def test_usage_error_is_printed_by_main(capsys: pytest.CaptureFixture[str]) -> None:
    """main() prints a usage error and its hint to stderr and returns 3."""
    assert main(["--good", "v1", "--run", "./app"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "git-autobisect: error: --run needs --grep.",
        "hint: Add --grep <pattern> to say which output marks a commit as bad, or use "
        "--test <cmd> if the exit status of the command is enough.",
    ]


def test_argparse_error_exits_3_not_2(capsys: pytest.CaptureFixture[str]) -> None:
    """A problem argparse finds itself returns 3 from main(), in the tool's error format."""
    assert main([*MINIMAL, "--frobnicate"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(
        "git-autobisect: error: unrecognized arguments: --frobnicate.\nhint: "
    )


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_exits_0_with_examples(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    """--help prints the description, every flag and the examples to stdout and exits 0."""
    with pytest.raises(SystemExit) as raised:
        parse_args([flag])
    assert raised.value.code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Find the commit that introduced a regression" in captured.out
    assert "Examples:" in captured.out
    examples = [
        line for line in captured.out.splitlines() if line.startswith("  git autobisect --good ")
    ]
    assert len(examples) >= 3
    for name in [
        "--bad",
        "--good",
        "--clean",
        "--no-clean",
        "--setup",
        "--build",
        "--test",
        "--run",
        "--grep",
        "--grep-absent",
        "--verbose",
        "--stat-only",
        "-h, --help",
        "--version",
    ]:
        assert f"\n  {name}" in captured.out


def test_help_examples_are_valid_command_lines(capsys: pytest.CaptureFixture[str]) -> None:
    """Every example in --help is accepted by parse_args."""
    with pytest.raises(SystemExit):
        parse_args(["--help"])
    examples = [
        line.strip()
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("  git autobisect --good ")
    ]
    assert examples
    for example in examples:
        assert isinstance(parse_args(shlex.split(example)[2:]), Options)


def test_help_wins_over_other_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    """main() returns 0 for --help even when the rest of the command line is incomplete."""
    assert main(["--test", "make test", "--help"]) == 0
    captured = capsys.readouterr()
    assert "Examples:" in captured.out
    assert captured.err == ""


def test_version_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    """--version prints the version to stdout and exits 0."""
    with pytest.raises(SystemExit) as raised:
        parse_args(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out == f"git-autobisect {__version__}\n"
