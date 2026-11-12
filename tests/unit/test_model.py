"""Unit tests for the shared data model in autobisect.model."""

from __future__ import annotations

import json
import re
from dataclasses import fields
from typing import Any

import pytest

from autobisect.model import (
    DEFAULT_CLEAN,
    CheckConfig,
    CheckResult,
    CommandResult,
    CommitResult,
    PerfMeasurement,
    Verdict,
)

SHA = "0123456789abcdef0123456789abcdef01234567"


def full_config() -> CheckConfig:
    """Return a CheckConfig in which every field differs from its default."""
    return CheckConfig(
        clean="git clean -fdx -e .cache",
        setup="npm ci",
        build="make -j4",
        tests=["make test", "sh -c 'echo \"a b\"; exit 0'"],
        run="./app --selftest",
        grep=r"Segmentation fault|core dumped",
        grep_absent=True,
        retries=11,
        flaky_policy="any",
        timeout=2.5,
        timeout_skip=True,
        perf="./bench.sh",
        perf_runs=10,
        perf_warmup=3,
    )


def flaky_check() -> CheckResult:
    """Return the CheckResult of a flaky test check with a timed-out attempt."""
    return CheckResult(
        name="test",
        command="./stress.sh",
        verdict=Verdict.BAD,
        passed=1,
        failed=2,
        flaky=True,
        timed_out=True,
    )


def measurement() -> PerfMeasurement:
    """Return a successful PerfMeasurement of three runs."""
    return PerfMeasurement(
        runs_s=[1.9, 2.0, 2.1],
        median_s=2.0,
        spread_pct=10.0,
        warmup=1,
        failed=False,
        timed_out=False,
    )


def commit_result() -> CommitResult:
    """Return a CommitResult with two checks and a perf measurement."""
    return CommitResult(
        sha=SHA,
        verdict=Verdict.BAD,
        reason="./stress.sh failed 2 of 3 attempts",
        checks=[
            CheckResult("build", "make", Verdict.GOOD, 1, 0, flaky=False, timed_out=False),
            flaky_check(),
        ],
        perf=measurement(),
        duration_s=12.4,
        cached=False,
        log_path=f".git/autobisect/logs/{SHA}.log",
    )


def changed(obj: Any, **values: Any) -> dict[str, Any]:
    """Return ``obj.to_dict()`` with some values replaced or added."""
    data = obj.to_dict()
    data.update(values)
    return data


def without(obj: Any, *keys: str) -> dict[str, Any]:
    """Return ``obj.to_dict()`` without the given keys."""
    data = obj.to_dict()
    for key in keys:
        del data[key]
    return data


SAMPLES = [
    pytest.param(CheckConfig(), id="CheckConfig-defaults"),
    pytest.param(CheckConfig(clean=None), id="CheckConfig-no-clean"),
    pytest.param(full_config(), id="CheckConfig-every-field-set"),
    pytest.param(CommandResult(exit_code=0, duration_s=0.25, timed_out=False), id="CommandResult"),
    pytest.param(
        CommandResult(exit_code=-9, duration_s=30.0, timed_out=True, output="naïve ✓\nline 2\n"),
        id="CommandResult-with-output",
    ),
    pytest.param(flaky_check(), id="CheckResult"),
    pytest.param(measurement(), id="PerfMeasurement"),
    pytest.param(
        PerfMeasurement(
            runs_s=[], median_s=None, spread_pct=None, warmup=1, failed=True, timed_out=False
        ),
        id="PerfMeasurement-failed",
    ),
    pytest.param(commit_result(), id="CommitResult"),
    pytest.param(
        CommitResult(
            sha=SHA,
            verdict=Verdict.SKIP,
            reason="setup failed",
            checks=[],
            perf=None,
            duration_s=0.5,
            cached=True,
            log_path=f".git/autobisect/logs/{SHA}.log",
        ),
        id="CommitResult-no-checks-no-perf",
    ),
]


def test_verdict_values() -> None:
    """Verdicts are written as their lower-case names."""
    assert [verdict.value for verdict in Verdict] == ["good", "bad", "skip"]


def test_check_config_defaults() -> None:
    """CheckConfig() has every verdict-affecting field, each with its default."""
    config = CheckConfig()
    assert {f.name: getattr(config, f.name) for f in fields(config)} == {
        "clean": "git clean -fdx",
        "setup": None,
        "build": None,
        "tests": [],
        "run": None,
        "grep": None,
        "grep_absent": False,
        "retries": 0,
        "flaky_policy": "strict",
        "timeout": None,
        "timeout_skip": False,
        "perf": None,
        "perf_runs": 5,
        "perf_warmup": 1,
    }
    assert DEFAULT_CLEAN == "git clean -fdx"


def test_check_configs_do_not_share_the_tests_list() -> None:
    """Each CheckConfig() gets its own empty tests list."""
    first = CheckConfig()
    first.tests.append("make test")
    assert CheckConfig().tests == []


def test_full_config_sets_every_field() -> None:
    """The full sample differs from the defaults everywhere, so its round trip checks each field."""
    full, default = full_config(), CheckConfig()
    same = [f.name for f in fields(full) if getattr(full, f.name) == getattr(default, f.name)]
    assert same == []


@pytest.mark.parametrize("obj", SAMPLES)
def test_round_trip_through_json(obj: Any) -> None:
    """to_dict(), then JSON text, then from_dict() gives back an equal object."""
    text = json.dumps(obj.to_dict())
    assert type(obj).from_dict(json.loads(text)) == obj


@pytest.mark.parametrize("obj", SAMPLES)
def test_to_dict_has_one_key_per_field(obj: Any) -> None:
    """to_dict() has exactly the dataclass fields as keys, in field order."""
    assert list(obj.to_dict()) == [f.name for f in fields(obj)]


def test_to_dict_uses_plain_json_values() -> None:
    """to_dict() writes verdicts as strings and nested results as dicts and lists."""
    assert commit_result().to_dict() == {
        "sha": SHA,
        "verdict": "bad",
        "reason": "./stress.sh failed 2 of 3 attempts",
        "checks": [
            {
                "name": "build",
                "command": "make",
                "verdict": "good",
                "passed": 1,
                "failed": 0,
                "flaky": False,
                "timed_out": False,
            },
            {
                "name": "test",
                "command": "./stress.sh",
                "verdict": "bad",
                "passed": 1,
                "failed": 2,
                "flaky": True,
                "timed_out": True,
            },
        ],
        "perf": {
            "runs_s": [1.9, 2.0, 2.1],
            "median_s": 2.0,
            "spread_pct": 10.0,
            "warmup": 1,
            "failed": False,
            "timed_out": False,
        },
        "duration_s": 12.4,
        "cached": False,
        "log_path": f".git/autobisect/logs/{SHA}.log",
    }


def test_to_dict_copies_lists() -> None:
    """Changing a list in the dict from to_dict() leaves the object unchanged."""
    config = full_config()
    config.to_dict()["tests"].append("make lint")
    assert config.tests == full_config().tests


def test_from_dict_reads_whole_numbers_as_floats() -> None:
    """A float field written as a whole number (600 rather than 600.0) reads back as a float."""
    config = CheckConfig.from_dict(changed(CheckConfig(), timeout=600))
    perf = PerfMeasurement.from_dict(
        changed(measurement(), runs_s=[2, 3], median_s=2, spread_pct=50)
    )
    commit = CommitResult.from_dict(changed(commit_result(), duration_s=12))
    command = CommandResult.from_dict(
        {"exit_code": 0, "duration_s": 1, "timed_out": False, "output": None}
    )
    values = [
        config.timeout,
        *perf.runs_s,
        perf.median_s,
        perf.spread_pct,
        commit.duration_s,
        command.duration_s,
    ]
    assert values == [600.0, 2.0, 3.0, 2.0, 50.0, 12.0, 1.0]
    assert all(type(value) is float for value in values)


BAD_DATA = [
    pytest.param(
        CheckResult,
        ["test"],
        "cannot read CheckResult: expected a JSON object, got ['test']",
        id="not-an-object",
    ),
    pytest.param(
        CheckResult,
        without(flaky_check(), "failed"),
        "cannot read CheckResult: missing key 'failed'",
        id="missing-key",
    ),
    pytest.param(
        CheckResult,
        without(flaky_check(), "flaky", "failed"),
        "cannot read CheckResult: missing keys 'failed', 'flaky'",
        id="missing-keys",
    ),
    pytest.param(
        CheckResult,
        changed(flaky_check(), colour="red"),
        "cannot read CheckResult: unexpected key 'colour'",
        id="unexpected-key",
    ),
    pytest.param(
        CheckConfig,
        changed(CheckConfig(), retries="3"),
        "cannot read CheckConfig: 'retries' must be an integer, got '3'",
        id="string-for-integer",
    ),
    pytest.param(
        CheckConfig,
        changed(CheckConfig(), retries=True),
        "'retries' must be an integer, got True",
        id="boolean-for-integer",
    ),
    pytest.param(
        CheckConfig,
        changed(CheckConfig(), perf_runs=5.0),
        "'perf_runs' must be an integer, got 5.0",
        id="float-for-integer",
    ),
    pytest.param(
        CheckResult,
        changed(flaky_check(), name=None),
        "'name' must be a string, got None",
        id="null-for-string",
    ),
    pytest.param(
        CheckConfig,
        changed(CheckConfig(), build=["make"]),
        "'build' must be a string or null, got ['make']",
        id="list-for-optional-string",
    ),
    pytest.param(
        CheckResult,
        changed(flaky_check(), flaky=1),
        "'flaky' must be true or false, got 1",
        id="integer-for-boolean",
    ),
    pytest.param(
        CheckResult,
        changed(flaky_check(), verdict="GOOD"),
        "'verdict' must be one of 'good', 'bad', 'skip', got 'GOOD'",
        id="unknown-verdict",
    ),
    pytest.param(
        CheckConfig,
        changed(CheckConfig(), tests="make test"),
        "'tests' must be a list of strings, got 'make test'",
        id="string-for-list",
    ),
    pytest.param(
        CheckConfig,
        changed(CheckConfig(), tests=["make test", 3]),
        "'tests' must be a list of strings, got ['make test', 3]",
        id="bad-item-in-list",
    ),
    pytest.param(
        CheckConfig,
        changed(CheckConfig(), timeout="600"),
        "'timeout' must be a number or null, got '600'",
        id="string-for-number",
    ),
    pytest.param(
        CommandResult,
        {"exit_code": 0, "duration_s": False, "timed_out": False, "output": None},
        "'duration_s' must be a number, got False",
        id="boolean-for-number",
    ),
    pytest.param(
        PerfMeasurement,
        changed(measurement(), runs_s=[1.9, None]),
        "'runs_s' must be a list of numbers, got [1.9, None]",
        id="bad-number-in-list",
    ),
    pytest.param(
        CommitResult,
        changed(commit_result(), checks={}),
        "cannot read CommitResult: 'checks' must be a list, got {}",
        id="object-for-list",
    ),
    pytest.param(
        CommitResult,
        changed(commit_result(), checks=[{"name": "build"}]),
        "cannot read CheckResult: missing keys 'command', 'failed'",
        id="bad-nested-check",
    ),
    pytest.param(
        CommitResult,
        changed(commit_result(), perf=[2.0]),
        "cannot read PerfMeasurement: expected a JSON object, got [2.0]",
        id="bad-nested-perf",
    ),
]


@pytest.mark.parametrize(("cls", "data", "message"), BAD_DATA)
def test_from_dict_rejects_what_to_dict_cannot_produce(cls: Any, data: Any, message: str) -> None:
    """from_dict() raises ValueError naming the class, the key and the value found."""
    with pytest.raises(ValueError, match=re.escape(message)):
        cls.from_dict(data)
