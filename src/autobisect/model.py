"""Shared data model: the verdict enum and the dataclasses every module uses.

What it does: defines ``Verdict`` and the dataclasses of design section 2.
``CheckConfig`` holds every setting that affects the stored result of testing a
commit; ``CommandResult`` is one run of one command; ``CheckResult`` is one check
over all its attempts; ``PerfMeasurement`` is the timed runs of the perf check;
``CommitResult`` is the evaluation of one commit. Each dataclass has ``to_dict()``
and ``from_dict()``, which convert it to and from plain JSON values, so that it can
be written to the session file and, from M2, to the result cache.
Inputs: none; the module only defines types.
Outputs: the types above and ``DEFAULT_CLEAN``.
Errors: every ``from_dict()`` raises ``ValueError`` for data that ``to_dict()``
cannot have produced: not a dict, a missing or unexpected key, or a value of the
wrong type. The message names the class, the key and the value found. Callers
that read files add what to do about it (for example, clear the cache).
"""

from __future__ import annotations

import reprlib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, TypeVar

# The clean command unless --clean replaces it; --no-clean sets CheckConfig.clean to None.
DEFAULT_CLEAN = "git clean -fdx"

_T = TypeVar("_T")


class Verdict(Enum):
    """What a check, or a whole commit, says about a commit.

    The three members are the three answers ``git bisect run`` understands;
    ``errors.verdict_to_exit_code`` gives their exit codes. Each value is the
    member's name in lower case, which is how a verdict is written in JSON.
    """

    GOOD = "good"
    BAD = "bad"
    SKIP = "skip"


@dataclass
class CheckConfig:
    """Every setting that affects the stored result of testing a commit.

    These are the inputs of the result cache key (design section 3.9, ADR-0007),
    so a new setting that can change a stored result belongs here. The perf
    tolerance and the baseline commit are left out on purpose: they are applied
    at run time and are not part of the key (ADR-0009). Fields whose flags arrive
    in a later milestone exist already, with the defaults those flags will have.

    Fields (design sections 1 and 3.1):
        clean: runs first on every commit; ``None`` when ``--no-clean`` disables it.
        setup: runs after clean; a failure skips the commit. ``None``: no setup step.
        build: a failure skips the commit. ``None``: no build step.
        tests: test commands, run in this order; all must pass.
        run: command whose combined stdout and stderr is matched against ``grep``.
        grep: Python regular expression; the commit is bad if the output matches.
        grep_absent: inverts ``grep``: the commit is bad if the output does not match.
        retries: extra attempts per test or grep check (flag from M2).
        flaky_policy: ``strict``, ``any``, ``majority`` or ``skip`` (flag from M2).
        timeout: seconds allowed per command invocation; ``None``: no limit (M2).
        timeout_skip: a timeout skips the commit instead of counting as a failure (M2).
        perf: command whose wall-clock time is measured (flag from M3).
        perf_runs: measured runs per commit (flag from M3).
        perf_warmup: discarded warm-up runs per commit (flag from M3).
    """

    clean: str | None = DEFAULT_CLEAN
    setup: str | None = None
    build: str | None = None
    tests: list[str] = field(default_factory=list)
    run: str | None = None
    grep: str | None = None
    grep_absent: bool = False
    retries: int = 0
    flaky_policy: str = "strict"
    timeout: float | None = None
    timeout_skip: bool = False
    perf: str | None = None
    perf_runs: int = 5
    perf_warmup: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Return this configuration as plain JSON values.

        Inputs: none.
        Outputs: a new dict with one key per field, in field order; ``tests`` is a
        copy of the list.
        Errors: none.
        """
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: object) -> CheckConfig:
        """Rebuild a configuration from the output of ``to_dict()``.

        Inputs: ``data``, a dict as ``to_dict()`` returns it, usually read back with
        ``json.loads``. A whole number is accepted for ``timeout``.
        Outputs: the ``CheckConfig``.
        Errors: ``ValueError`` if ``data`` is not a dict, lacks a field, has an
        unexpected key or holds a value of the wrong type.
        """
        read = _Reader(cls, data)
        return cls(
            clean=read.optional_string("clean"),
            setup=read.optional_string("setup"),
            build=read.optional_string("build"),
            tests=read.string_list("tests"),
            run=read.optional_string("run"),
            grep=read.optional_string("grep"),
            grep_absent=read.boolean("grep_absent"),
            retries=read.integer("retries"),
            flaky_policy=read.string("flaky_policy"),
            timeout=read.optional_number("timeout"),
            timeout_skip=read.boolean("timeout_skip"),
            perf=read.optional_string("perf"),
            perf_runs=read.integer("perf_runs"),
            perf_warmup=read.integer("perf_warmup"),
        )


@dataclass
class CommandResult:
    """The outcome of running one user command once (design section 3.2).

    Fields:
        exit_code: the exit status; -N when the command was ended by signal N, as
            ``subprocess`` reports it.
        duration_s: wall-clock run time in seconds.
        timed_out: True when the command hit the timeout and was killed.
        output: the combined stdout and stderr, kept only when a grep check needs
            it; ``None`` otherwise.
    """

    exit_code: int
    duration_s: float
    timed_out: bool
    output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return this result as plain JSON values.

        Inputs: none.
        Outputs: a new dict with one key per field, in field order.
        Errors: none.
        """
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: object) -> CommandResult:
        """Rebuild a command result from the output of ``to_dict()``.

        Inputs: ``data``, a dict as ``to_dict()`` returns it, usually read back with
        ``json.loads``. A whole number is accepted for ``duration_s``.
        Outputs: the ``CommandResult``.
        Errors: ``ValueError`` if ``data`` is not a dict, lacks a field, has an
        unexpected key or holds a value of the wrong type.
        """
        read = _Reader(cls, data)
        return cls(
            exit_code=read.integer("exit_code"),
            duration_s=read.number("duration_s"),
            timed_out=read.boolean("timed_out"),
            output=read.optional_string("output"),
        )


@dataclass
class CheckResult:
    """The outcome of one check of the pipeline, over all its attempts.

    Fields:
        name: which step this is, for example ``"build"`` or ``"test"``.
        command: the command that was run, as the user gave it.
        verdict: what this check says about the commit.
        passed: number of attempts that passed.
        failed: number of attempts that failed.
        flaky: True when some attempts passed and others failed (design section 3.3).
        timed_out: True when an attempt hit the timeout.
    """

    name: str
    command: str
    verdict: Verdict
    passed: int
    failed: int
    flaky: bool
    timed_out: bool

    def to_dict(self) -> dict[str, Any]:
        """Return this result as plain JSON values.

        Inputs: none.
        Outputs: a new dict with one key per field, in field order; ``verdict`` is
        its string value, such as ``"good"``.
        Errors: none.
        """
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: object) -> CheckResult:
        """Rebuild a check result from the output of ``to_dict()``.

        Inputs: ``data``, a dict as ``to_dict()`` returns it, usually read back with
        ``json.loads``.
        Outputs: the ``CheckResult``.
        Errors: ``ValueError`` if ``data`` is not a dict, lacks a field, has an
        unexpected key or holds a value of the wrong type, including a verdict
        that is not ``"good"``, ``"bad"`` or ``"skip"``.
        """
        read = _Reader(cls, data)
        return cls(
            name=read.string("name"),
            command=read.string("command"),
            verdict=read.verdict("verdict"),
            passed=read.integer("passed"),
            failed=read.integer("failed"),
            flaky=read.boolean("flaky"),
            timed_out=read.boolean("timed_out"),
        )


@dataclass
class PerfMeasurement:
    """The timed runs of the perf command on one commit (M3, design section 3.4).

    This is a measurement, not a verdict: ``perf.final_verdict`` compares it with
    the baseline at run time, so a cached measurement stays valid when the
    tolerance changes.

    Fields:
        runs_s: wall-clock seconds of each measured run, in run order; warm-up runs
            are not included.
        median_s: median of ``runs_s``; ``None`` when the measurement has no median
            (for example, the first run failed).
        spread_pct: (max - min) / median of ``runs_s``, as a percentage; ``None``
            when ``median_s`` is ``None``.
        warmup: number of warm-up runs discarded before measuring.
        failed: True when a run exited non-zero.
        timed_out: True when a run hit the timeout.
    """

    runs_s: list[float]
    median_s: float | None
    spread_pct: float | None
    warmup: int
    failed: bool
    timed_out: bool

    def to_dict(self) -> dict[str, Any]:
        """Return this measurement as plain JSON values.

        Inputs: none.
        Outputs: a new dict with one key per field, in field order; ``runs_s`` is a
        copy of the list.
        Errors: none.
        """
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: object) -> PerfMeasurement:
        """Rebuild a measurement from the output of ``to_dict()``.

        Inputs: ``data``, a dict as ``to_dict()`` returns it, usually read back with
        ``json.loads``. Whole numbers are accepted for the float fields.
        Outputs: the ``PerfMeasurement``.
        Errors: ``ValueError`` if ``data`` is not a dict, lacks a field, has an
        unexpected key or holds a value of the wrong type.
        """
        read = _Reader(cls, data)
        return cls(
            runs_s=read.number_list("runs_s"),
            median_s=read.optional_number("median_s"),
            spread_pct=read.optional_number("spread_pct"),
            warmup=read.integer("warmup"),
            failed=read.boolean("failed"),
            timed_out=read.boolean("timed_out"),
        )


@dataclass
class CommitResult:
    """The evaluation of one commit by the check pipeline.

    Fields:
        sha: the full commit SHA.
        verdict: the verdict of the non-perf checks. A perf verdict is never
            stored: ``perf.final_verdict`` combines this verdict with ``perf`` at
            run time.
        reason: short explanation of the verdict, for reports.
        checks: one ``CheckResult`` per check that ran, in pipeline order.
        perf: the perf measurement; ``None`` when there is no perf check or the
            pipeline stopped before it.
        duration_s: wall-clock seconds the evaluation took.
        cached: True when this result came from the cache, not a fresh run.
        log_path: path of the per-commit log (design section 3.9).
    """

    sha: str
    verdict: Verdict
    reason: str
    checks: list[CheckResult]
    perf: PerfMeasurement | None
    duration_s: float
    cached: bool
    log_path: str

    def to_dict(self) -> dict[str, Any]:
        """Return this result as plain JSON values.

        Inputs: none.
        Outputs: a new dict with one key per field, in field order; ``verdict`` is
        its string value, ``checks`` a list of dicts and ``perf`` a dict or ``None``.
        Errors: none.
        """
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: object) -> CommitResult:
        """Rebuild a commit result from the output of ``to_dict()``.

        Inputs: ``data``, a dict as ``to_dict()`` returns it, usually read back with
        ``json.loads``. A whole number is accepted for ``duration_s``.
        Outputs: the ``CommitResult``, with its checks and perf measurement rebuilt.
        Errors: ``ValueError`` if ``data``, a check or the perf measurement is not a
        dict, lacks a field, has an unexpected key or holds a value of the wrong
        type.
        """
        read = _Reader(cls, data)
        return cls(
            sha=read.string("sha"),
            verdict=read.verdict("verdict"),
            reason=read.string("reason"),
            checks=read.object_list("checks", CheckResult.from_dict),
            perf=read.optional_object("perf", PerfMeasurement.from_dict),
            duration_s=read.number("duration_s"),
            cached=read.boolean("cached"),
            log_path=read.string("log_path"),
        )


# Helpers for the to_dict() and from_dict() methods above.


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert an instance of one of the dataclasses above to plain JSON values.

    Inputs: ``obj``, a dataclass instance from this module.
    Outputs: a new dict with one key per field, in field order. Nested dataclasses
    become dicts, lists are copied, and each ``Verdict`` becomes its string value.
    Errors: none.
    """
    return asdict(obj, dict_factory=_json_object)


def _json_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build the dict for one dataclass in ``dataclasses.asdict``, storing enums by value.

    Inputs: the (field name, value) pairs of one instance, with nested dataclasses
    already converted.
    Outputs: a dict of those pairs in which each ``Enum`` member is replaced by its
    value.
    Errors: none.
    """
    return {key: value.value if isinstance(value, Enum) else value for key, value in items}


def _is_int(value: object) -> bool:
    """Tell whether ``value`` is an integer.

    Inputs: any value.
    Outputs: True for an ``int``; False for anything else, including ``True`` and
    ``False``, which Python counts as integers but JSON does not.
    Errors: none.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    """Tell whether ``value`` is a JSON number.

    Inputs: any value.
    Outputs: True for an ``int`` or a ``float``; False for anything else, including
    ``True`` and ``False``.
    Errors: none.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _describe_keys(label: str, keys: set[Any]) -> str:
    """Describe some dict keys for an error message.

    Inputs: ``label``, such as ``"missing"``; ``keys``, a non-empty set of keys.
    Outputs: ``"<label> key 'a'"`` or ``"<label> keys 'a', 'b'"``, keys sorted.
    Errors: none.
    """
    noun = "key" if len(keys) == 1 else "keys"
    return f"{label} {noun} " + ", ".join(sorted(repr(key) for key in keys))


class _Reader:
    """Typed access to the decoded JSON object that a ``from_dict()`` rebuilds.

    What it does: on creation, checks that the data is a dict whose keys are
    exactly the field names of the dataclass; each method then returns the value
    of one key after checking its type.
    Inputs: the dataclass being rebuilt and the data, usually from ``json.loads``.
    Outputs: the value of each key, of the type the method names.
    Errors: ``ValueError`` starting ``cannot read <class>:``, saying which key is
    missing, unexpected or of the wrong type, and what was found.
    """

    def __init__(self, cls: type, data: object) -> None:
        """Check that ``data`` is a dict with exactly the field names of ``cls``.

        Inputs: ``cls``, a dataclass; ``data``, the value to rebuild it from.
        Outputs: none.
        Errors: ``ValueError`` if ``data`` is not a dict, lacks a field of ``cls``
        or has a key that is not a field of ``cls``.
        """
        self._class_name = cls.__name__
        if not isinstance(data, dict):
            raise self._error(f"expected a JSON object, got {reprlib.repr(data)}")
        names = {f.name for f in fields(cls)}
        problems = []
        missing = names.difference(data)
        if missing:
            problems.append(_describe_keys("missing", missing))
        unexpected = set(data).difference(names)
        if unexpected:
            problems.append(_describe_keys("unexpected", unexpected))
        if problems:
            raise self._error("; ".join(problems))
        self._data: dict[str, Any] = data

    def _error(self, problem: str) -> ValueError:
        """Make the error for a problem with the data.

        Inputs: ``problem``, what is wrong with the data.
        Outputs: a ``ValueError`` reading ``cannot read <class>: <problem>``, for
        the caller to raise.
        Errors: none.
        """
        return ValueError(f"cannot read {self._class_name}: {problem}")

    def _wrong(self, key: str, expected: str, value: object) -> ValueError:
        """Make the error for a value of the wrong type.

        Inputs: ``key``, the field; ``expected``, what it must hold, such as
        ``"a string"``; ``value``, what it holds.
        Outputs: a ``ValueError`` reading ``cannot read <class>: '<key>' must be
        <expected>, got <value>``, with long values shortened, for the caller to
        raise.
        Errors: none.
        """
        return self._error(f"'{key}' must be {expected}, got {reprlib.repr(value)}")

    def string(self, key: str) -> str:
        """Return the string at ``key``.

        Inputs: ``key``, a field name.
        Outputs: the string.
        Errors: ``ValueError`` if the value is not a string.
        """
        value = self._data[key]
        if not isinstance(value, str):
            raise self._wrong(key, "a string", value)
        return value

    def optional_string(self, key: str) -> str | None:
        """Return the string at ``key``, or ``None`` if it is null.

        Inputs: ``key``, a field name.
        Outputs: the string or ``None``.
        Errors: ``ValueError`` if the value is neither a string nor null.
        """
        value = self._data[key]
        if value is not None and not isinstance(value, str):
            raise self._wrong(key, "a string or null", value)
        return value

    def integer(self, key: str) -> int:
        """Return the integer at ``key``.

        Inputs: ``key``, a field name.
        Outputs: the integer.
        Errors: ``ValueError`` if the value is not an integer (``true`` and
        ``false`` are not integers here).
        """
        value = self._data[key]
        if not _is_int(value):
            raise self._wrong(key, "an integer", value)
        return value

    def number(self, key: str) -> float:
        """Return the number at ``key`` as a float.

        Inputs: ``key``, a field name.
        Outputs: the number, converted to ``float`` if it was an integer.
        Errors: ``ValueError`` if the value is not a number.
        """
        value = self._data[key]
        if not _is_number(value):
            raise self._wrong(key, "a number", value)
        return float(value)

    def optional_number(self, key: str) -> float | None:
        """Return the number at ``key`` as a float, or ``None`` if it is null.

        Inputs: ``key``, a field name.
        Outputs: the number, converted to ``float`` if it was an integer, or ``None``.
        Errors: ``ValueError`` if the value is neither a number nor null.
        """
        value = self._data[key]
        if value is None:
            return None
        if not _is_number(value):
            raise self._wrong(key, "a number or null", value)
        return float(value)

    def boolean(self, key: str) -> bool:
        """Return the boolean at ``key``.

        Inputs: ``key``, a field name.
        Outputs: the boolean.
        Errors: ``ValueError`` if the value is not ``true`` or ``false``.
        """
        value = self._data[key]
        if not isinstance(value, bool):
            raise self._wrong(key, "true or false", value)
        return value

    def string_list(self, key: str) -> list[str]:
        """Return the list of strings at ``key``.

        Inputs: ``key``, a field name.
        Outputs: a copy of the list.
        Errors: ``ValueError`` if the value is not a list or an item is not a string.
        """
        value = self._data[key]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise self._wrong(key, "a list of strings", value)
        return list(value)

    def number_list(self, key: str) -> list[float]:
        """Return the list of numbers at ``key`` as floats.

        Inputs: ``key``, a field name.
        Outputs: a new list of the numbers, each converted to ``float``.
        Errors: ``ValueError`` if the value is not a list or an item is not a number.
        """
        value = self._data[key]
        if not isinstance(value, list) or not all(_is_number(item) for item in value):
            raise self._wrong(key, "a list of numbers", value)
        return [float(item) for item in value]

    def verdict(self, key: str) -> Verdict:
        """Return the verdict whose string value is at ``key``.

        Inputs: ``key``, a field name.
        Outputs: the ``Verdict`` member.
        Errors: ``ValueError`` if the value is not ``"good"``, ``"bad"`` or ``"skip"``.
        """
        value = self._data[key]
        if isinstance(value, str):
            for member in Verdict:
                if value == member.value:
                    return member
        allowed = ", ".join(repr(member.value) for member in Verdict)
        raise self._wrong(key, f"one of {allowed}", value)

    def object_list(self, key: str, rebuild: Callable[[object], _T]) -> list[_T]:
        """Return the list at ``key`` with each item rebuilt by ``rebuild``.

        Inputs: ``key``, a field name; ``rebuild``, the ``from_dict`` of the items.
        Outputs: the rebuilt items, in order.
        Errors: ``ValueError`` if the value is not a list, or from ``rebuild``.
        """
        value = self._data[key]
        if not isinstance(value, list):
            raise self._wrong(key, "a list", value)
        return [rebuild(item) for item in value]

    def optional_object(self, key: str, rebuild: Callable[[object], _T]) -> _T | None:
        """Return the value at ``key`` rebuilt by ``rebuild``, or ``None`` if it is null.

        Inputs: ``key``, a field name; ``rebuild``, the ``from_dict`` of the value.
        Outputs: the rebuilt object, or ``None``.
        Errors: ``ValueError`` from ``rebuild``.
        """
        value = self._data[key]
        return None if value is None else rebuild(value)
