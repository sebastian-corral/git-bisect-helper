# git-autobisect: design (accepted)

Status: **accepted 11 Nov 2026**, revision 2. Technology: thin Bash 3.2 entry point + Python 3.9+ core, standard library only (ADR-0001, ADR-0002).


---

## 1. CLI

```
git autobisect [--bad <rev>] [--good <rev> | --since <date>] <checks> [options] [-- <paths>...]
```

The "From" column says which milestone adds the flag.

### Revisions

| Flag | Default | From | Meaning |
|---|---|---|---|
| `--bad <rev>` | `HEAD` | M1 | Known-bad commit |
| `--good <rev>` | none | M1 | Known-good commit. Required in M1; from M2, omitting it starts the search |
| `--since <date>` | none | M2 | "It worked around then": the search starts at the last commit before this date. Mutually exclusive with `--good` |
| `--max-back <n>` | `1024` | M2 | Maximum distance (first-parent commits) the search may go back |
| `-- <paths>` | none | M2 | Passed to `git bisect start`; only commits touching these paths are tested |

### Checks (at least one of build/test/run/perf is required)

| Flag | Default | From | Meaning |
|---|---|---|---|
| `--clean <cmd>` | `git clean -fdx` | M1 | Runs first on every commit. `--no-clean` disables it |
| `--setup <cmd>` | none | M1 | Runs after clean. Failure = skip |
| `--build <cmd>` | none | M1 | Failure = skip (125) |
| `--test <cmd>` | none | M1 | Repeatable; run in the order given; all must pass |
| `--run <cmd>` with `--grep <pattern>` | none | M1 | Bad if combined stdout+stderr matches the pattern (Python regex). Both flags required together |
| `--grep-absent` | off | M1 | Inverts: bad if the pattern does **not** match |
| `--perf <cmd>` with `--tolerance <pct>` | none | M3 | Wall-clock regression check. Both required together. Requires `--good` |
| `--perf-runs <n>` | `5` | M3 | Measured runs per commit |
| `--perf-warmup <n>` | `1` | M3 | Discarded warm-up runs per commit |

### Robustness

| Flag | Default | From | Meaning |
|---|---|---|---|
| `--retries <n>` | `0` | M2 | Extra attempts per test/grep check (max attempts = 1 + n) |
| `--flaky-policy <p>` | `strict` | M2 | `strict`, `any`, `majority`, `skip` |
| `--timeout <sec>` | none | M2 | Per command invocation. Decimal allowed |
| `--timeout-skip` | off | M2 | A timeout skips the commit instead of counting as a failure |
| `--no-cache` | off | M2 | Neither read nor write the result cache |
| `--clear-cache` | | M2 | Delete `.git/autobisect/cache/` and exit 0 |

### Output and config

| Flag | From | Meaning |
|---|---|---|
| `--verbose` | M1 | Stream command output to stderr as well as the log |
| `--stat-only` | M1 | Show only `git show --stat`, not the patch |
| `-h, --help`, `--version` | M1 | Usage with examples; version |
| `--report <file>` | M4 | Write the summary as Markdown |
| `--json` | M4 | Print the JSON document on stdout (progress stays on stderr) |
| `--dry-run` | M4 | Print commit count, estimated steps and the plan; run nothing |
| `--trust-config` | M4 | Use `.autobisect.conf` without prompting |
| `--no-config` | M4 | Ignore `.autobisect.conf` |
| `--first-parent`, `--find-fix`, `--jobs <k>` | M5 | Optional |
| `--copy-in <path>` | M5 | Optional, repeatable. Copies the listed untracked files from the user's working copy into the worktree after clean, on every commit. They may contain secrets; they are deleted with the worktree |

### Usage examples

```
# Test regression, known good tag
git autobisect --good v1.4.0 --bad HEAD --build "make" --test "make test"

# Don't know a good commit; it worked about a week ago
git autobisect --since "1 week ago" --setup "npm ci" --test "npm test"

# Intermittent failure (race condition)
git autobisect --good v2.0 --test "./stress.sh" --retries 11 --flaky-policy any

# Output check
git autobisect --good abc123 --build "make" --run "./app --selftest" --grep "Segmentation fault"

# Performance regression, 10 % band
git autobisect --good v3.1 --build "make release" --perf "./bench.sh" --tolerance 10

# Plan only, restricted to a directory
git autobisect --good v1.4.0 --test "make test" --dry-run -- src/parser
```

---

## 2. Architecture

### File layout

```
bin/git-autobisect            Bash 3.2 shim: find python3, check >= 3.9, exec the core
src/__main__.py               launcher so `python3 <dir>` works without PYTHONPATH
src/autobisect/
  __init__.py                 __version__ (single source of the version)
  __main__.py                 main(): top-level error handling, exit-code mapping
  cli.py                      argparse -> Options; merges config under flags
  model.py                    dataclasses and enums shared by all modules
  errors.py                   UsageError(3), RuntimeFailure(4), NotFound(1), Interrupted(130)
  gitutil.py                  the only module that shells out to git
  runner.py                   run one user command: shell, process group, timeout, logging
  worktree.py                 create/remove temp worktree, stale-session cleanup
  session.py                  session file, events log, current-pgid file, per-commit log paths
  pipeline.py                 evaluate_commit(): the ordered checks (BY HAND)
  checkscript.py              hidden `_check` subcommand + generator for the check script
  bisect.py                   validation, git bisect start/run, result extraction, cleanup ordering
  report.py                   progress lines, text summary; later Markdown and JSON
  flaky.py                    attempt counts -> verdict             (BY HAND, M2)
  cache.py                    config hash, read/write cached results (M2)
  search.py                   good-commit search                     (M2)
  perf.py                     median, spread, threshold, drift       (BY HAND, M3)
  github.py                   remote URL -> commit link, PR number   (M4)
  config.py                   parse .autobisect.conf, trust decision (M4)
tests/unit/                   pytest, pure logic
tests/integration/            pytest, throwaway repos, invokes the CLI
tests/e2e/                    bats, through the shim and `make install`
tests/golden/                 expected summary / Markdown / JSON
docs/design.md  docs/adr/  docs/json-schema.md  man/git-autobisect.1
Makefile  pyproject.toml (ruff + pytest config only)  .github/workflows/ci.yml
README.md  CHANGELOG.md  CONTRIBUTING.md  SECURITY.md  LICENSE  CLAUDE.md
```

Installed layout: `PREFIX/bin/git-autobisect`, `PREFIX/lib/git-autobisect/{__main__.py,autobisect/}`, `PREFIX/share/man/man1/git-autobisect.1`.

### Starting the interpreter

- The shim runs `"$python" "$libdir" "$@"`. Running a directory makes Python execute its `__main__.py` with that directory on `sys.path`, so **`PYTHONPATH` is never set** and never leaks into user commands.
- `$python` is `$AUTOBISECT_PYTHON` if set, otherwise `python3` from PATH. Missing or older than 3.9 gives a clear error and exit 4.
- `$libdir` is found relative to the shim's real path: `../lib/git-autobisect` when installed, `../src` in the repo.

### Key interfaces (signatures only)

```python
# model.py
class Verdict(Enum): GOOD, BAD, SKIP
CheckConfig     # commands + retries/policy/timeout/perf settings; everything that affects a verdict
CommandResult   # exit_code, duration_s, timed_out, output (kept only for grep)
CheckResult     # name, command, verdict, passed, failed, flaky, timed_out
PerfMeasurement # runs_s: list[float], median_s, spread_pct, warmup, failed, timed_out   (M3)
CommitResult    # sha, verdict (non-perf checks), reason, checks, perf: PerfMeasurement | None,
                # duration_s, cached, log_path

# runner.py
run_command(cmd: str, cwd: Path, env: dict, timeout: float | None, log: IO, echo: bool,
            on_start: Callable[[int], None] | None = None) -> CommandResult   # on_start receives the pgid

# pipeline.py
evaluate_commit(sha: str, worktree: Path, cfg: CheckConfig, log: IO, *, run=run_command) -> CommitResult

# flaky.py
decide(policy: str, passed: int, failed: int, max_attempts: int) -> Verdict | None   # None = run another attempt

# perf.py
median(xs) -> float;  spread_pct(xs) -> float;  threshold(baseline_s, tolerance_pct) -> float
is_regression(median_s, baseline_s, tolerance_pct) -> bool;  drift_pct(baseline_s, remeasured_s) -> float
final_verdict(result: CommitResult, baseline_s: float | None, tolerance_pct: float | None,
              timeout_skip: bool) -> Verdict

# cache.py
config_hash(cfg: CheckConfig) -> str
load(sha, cfg_hash) -> CommitResult | None;  store(result, cfg_hash) -> None;  clear() -> None
```

### How the parts connect

```
shim -> __main__ -> cli (+config) -> bisect.run()
          bisect: worktree.create -> validate endpoints / search (pipeline, in-process)
                  -> git bisect start -> git bisect run <generated script>   (own process group)
                         generated script -> checkscript._check -> cache -> pipeline -> runner
                  -> read refs/bisect/* -> report -> ordered cleanup -> worktree.remove
```

`pipeline.evaluate_commit` is the single entry point for testing a commit. Validation, the good-commit search and the check script all call it.

---

## 3. Mechanisms

### 3.1 Check pipeline (ADR-0010)

Order per commit: **clean -> setup -> build -> tests -> grep -> perf**. Clean runs first because the default `git clean -fdx` would otherwise delete what setup installed. The pipeline stops at the first step that decides the commit.

| Step | Non-zero exit | Timeout |
|---|---|---|
| clean | abort (tool exit 4) | abort |
| setup | skip | skip |
| build | skip | skip |
| test (each) | failed attempt -> flaky policy | failed attempt, or skip with `--timeout-skip` |
| run/grep | exit code ignored; verdict comes from the output match | failed attempt, or skip with `--timeout-skip` |
| perf | measurement marked failed -> skip | measurement marked timed out -> bad, or skip with `--timeout-skip` |

After the last step the worktree is reset (`git reset --hard`) so tracked files changed by a build cannot block git's next checkout.

### 3.2 How commands are run (ADR-0005)

- Shell: always `/bin/sh -c "<cmd>"`. The command string is passed as one argument, never re-quoted, concatenated or `eval`ed by the tool. Users who need Bash write `bash -c '...'`.
- Working directory: root of the temporary worktree.
- Environment: the user's environment, minus `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_PREFIX`; plus `AUTOBISECT_COMMIT`, `AUTOBISECT_WORKTREE`, `AUTOBISECT_ATTEMPT`. The environment is never written to logs, session files or reports.
- stdin is `/dev/null`. stdout+stderr go to the per-commit log (and to stderr with `--verbose`).
- **Process groups:** every command starts in its own session/process group (`start_new_session=True`; `process_group=` is 3.11+). The whole group is killed (SIGTERM, then SIGKILL after a 5 s grace period) in three cases: on timeout; after the command exits normally, so background children can't run into the next commit; and on interrupt.
- Before a command starts, its pgid is written to `current-pgid` in the session directory, and cleared when the group is gone. This lets the main process kill an orphaned group (see 3.5).

### 3.3 Flaky policy (ADR-0006)

Applies to each test command and the grep check separately. Max attempts = 1 + retries; stop as soon as the outcome is decided.

| Policy | Bad when | Good when | Early stop |
|---|---|---|---|
| `strict` | all attempts fail | any attempt passes | first pass |
| `any` | any attempt fails | all attempts pass | first failure |
| `majority` | failed x 2 > max attempts | passed x 2 >= max attempts (a tie is good) | when the result can't change |
| `skip` | all fail | all pass | first mixed result -> skip |

A check with both passes and failures marks the commit as flaky. Pass/fail counts are recorded per check and per commit. `--flaky-policy any` with `--retries 0` prints a warning.

### 3.4 Perf tolerance band (ADR-0009)

- Metric: wall-clock seconds of the perf command from a monotonic clock. Nothing else in v1.
- Per commit: `perf-warmup` discarded runs, then `perf-runs` measured runs. The pipeline records a **measurement** (runs, median, spread), not a verdict.
- Baseline: the good commit's measurement, taken (or loaded from the cache) during validation and stored in the session file.
- The perf verdict is worked out at run time by `perf.final_verdict`, for fresh results and cache hits alike: threshold = baseline x (1 + tolerance / 100); bad only if median **>** threshold; equal is good.
- Spread = (max - min) / median, as a percentage. If the baseline's spread > tolerance, warn that results are unreliable (the run continues).
- Before bisecting, the bad commit must exceed the threshold, otherwise exit 3 with both numbers shown.
- **Drift check:** after bisecting, the good commit is measured again, fresh (not from the cache). If it has moved from the baseline by more than the tolerance, warn that the machine drifted during the run and suggest rerunning with `--no-cache`. The new measurement replaces the cached one.
- Retries and flaky policy do not apply to perf.
- `--perf` without `--good` is a usage error (exit 3): the search has no baseline to define "passes".

### 3.5 Worktree isolation and cleanup (ADR-0003)

- `tempfile.mkdtemp(prefix="git-autobisect-")` (mode 0700), then `git worktree add --detach <tmp>/wt <bad>`.
- Bisect state (`refs/bisect/*`, `BISECT_LOG`) is per-worktree, so the user's checkout, index, stash and any bisect of their own are untouched. A dirty working tree is not an error.
- Each run records `{pid, worktree}` in `.git/autobisect/sessions/`. At startup, sessions whose pid is dead are cleaned up (covers SIGKILL and power loss).
- All tool state lives under `git rev-parse --git-common-dir`, so it works from a linked worktree.

**Cleanup ordering on SIGINT / SIGTERM / SIGHUP** (also the order on normal exit and errors, minus the waiting):

1. The main process starts `git bisect run` in its own process group, so signals reach it only through the main process. On a signal, main sends SIGTERM to that group.
2. `_check` handles the signal by killing its current command group (TERM, grace, KILL), **does not write a cache entry**, and exits 130, which aborts `git bisect run`.
3. Main waits up to 10 s for `git bisect run` to exit.
4. If it has not exited, main SIGKILLs the bisect group, then SIGKILLs any group still named in `current-pgid`.
5. Only then: `git bisect reset`, `git worktree remove --force`, `git worktree prune`, delete the temp dir and the session record.
6. Exit 130.

During validation and the search, commands run in-process, so main kills the current command group directly and continues from step 5.

### 3.6 Driving git bisect (ADR-0004)

- The generated check script is a two-line `sh` file in the session directory:

```sh
#!/bin/sh
exec '/abs/path/to/python3' '/abs/path/to/lib-dir' _check --session '/tmp/git-autobisect-xyz/session.json'
```

- The interpreter is `sys.executable` of the main process and the lib dir is the directory the running package was loaded from, both absolute and quoted with `shlex.quote`. It never looks up `python3` on PATH and never sets `PYTHONPATH`. It contains **no user commands**; those are data in the session JSON.
- `_check` flow: read session -> cache lookup -> `evaluate_commit` -> cache store -> `final_verdict` -> append an event -> print the progress line to stderr -> exit 0 / 1 / 125.
- Result extraction does not parse git's human-readable output. Candidates = `git rev-list refs/bisect/bad --not <refs/bisect/good-*>` in the worktree. One commit = found; several = range (exit 2).
- All git calls run with `LC_ALL=C`. Revisions are resolved once with `git rev-parse --verify --end-of-options <rev>^{commit}`; only full SHAs are used afterwards.
- Minimum git 2.30, checked at startup.

### 3.7 Validation (before bisecting)

1. Inside a git repo; git version supported; revisions resolve to commits.
2. `git merge-base --is-ancestor <good> <bad>`.
3. Good commit evaluates to GOOD; bad commit evaluates to BAD (perf: outside the band).

Each failure exits 3 with what was found and what to do, for example: "Good commit abc1234 fails `make test` (log: ...). Pick an older commit, or omit --good to search automatically."

**Dirty working copy hint:** if the bad commit passes, the bad revision is the working copy's `HEAD`, and `git status --porcelain` in the user's working copy is non-empty, the hint adds: "Only committed code is tested and your working copy has uncommitted changes. Commit or stash them, then run again."

### 3.8 Good-commit search (M2)

- Candidates are `bad~1, bad~2, bad~4, ...` along first-parent history, up to `--max-back`.
- With `--since`, the first candidate is the last commit before that date; if it fails, doubling continues from there.
- Candidate GOOD -> it becomes the good endpoint. Candidate BAD -> it becomes the new bad endpoint. Candidate SKIP -> try its parent, up to 3 times, then move to the next distance.
- Results go through the cache, so the bisect does not retest them.
- Root commit, shallow-clone boundary or `--max-back` reached without a pass -> exit 1 with the oldest commit tested.

### 3.9 Cache and logs (ADR-0007)

- Path: `.git/autobisect/cache/<config-hash>/<sha>.json`, written atomically (temp file + rename).
- An entry stores the **non-perf verdict** with its reason, attempt counts and timings, plus the **raw perf measurement** (runs, median, spread, failed/timed-out flags). It never stores a perf verdict. The good commit's entry is the cached baseline measurement.
- Config hash = SHA-256 of canonical JSON containing: cache schema version; clean, setup, build, test (ordered list), run, grep, grep-absent; retries, flaky policy, timeout, timeout-skip; perf command, perf runs, perf warm-up.
- Not in the hash: tolerance and the baseline commit (applied at run time), good/bad revisions, paths, output flags, `--max-back`.
- Not detectable: changes to the environment or toolchain. Documented; `--no-cache` and `--clear-cache` are the answer.
- Interrupted or aborted evaluations are never cached.
- Logs: `.git/autobisect/logs/<sha>.log`, mode 0600, overwritten per evaluation, with a header line (timestamp, config hash). A cache hit does not rewrite the log. Logs exist from M1; the cache arrives in M2.

### 3.10 Progress and time estimate

- One stderr line per commit: `[3/~7] a1b2c3d good  12.4s  (2 pass, 0 fail)  ~50s left`.
- Estimate (M4) = ceil(log2(remaining candidates)) x mean duration of uncached commits so far; shown after the first tested commit.

### 3.11 Config trust model (ADR-0008, M4)

- File: `.autobisect.conf` at the top level of the **user's working copy**. Never read from the bisect worktree.
- Format: one `key = value` per line; `#` comments; blank lines ignored. Keys are the long flag names. `test` may repeat. Booleans are `true`/`false`. The value is the raw text after the first `=`, trimmed: no quoting, escapes, interpolation, continuation lines or sections. Unknown keys and revision keys (`good`, `bad`, `since`) are errors (exit 3). Parsed by hand, not with `configparser`.

```
# .autobisect.conf
setup     = npm ci
build     = npm run build
test      = npm test
test      = npm run lint
retries   = 2
timeout   = 600
```

- Interactive run (stdin and stderr are terminals): print the file path and every value, ask `Use this config? [y/N]`. Default is no.
- Approval is remembered by content hash in `.git/autobisect/trusted`; any edit asks again.
- Non-interactive run: the file is ignored, with a one-line notice, unless `--trust-config` is given.
- All-or-nothing. Command-line flags override config values; a `--test` on the command line replaces the config's test list.

### 3.12 GitHub link and PR number (M4)

- Remote: `origin`, else the first remote. Accepts https and ssh GitHub URLs; embedded credentials are stripped.
- Link: `https://github.com/<owner>/<repo>/commit/<sha>`.
- PR number, offline only: from the commit subject (`Merge pull request #N`, or a trailing `(#N)`); otherwise from the first merge commit on the path to bad that contains the commit. No GitHub API.

---

## 4. Exit codes

**Check script** (`git bisect run` contract)

| Code | Meaning |
|---|---|
| 0 | good |
| 1 | bad |
| 125 | skip (setup/build failure, flaky `skip`, `--timeout-skip`, unmeasurable perf) |
| 128 | abort: internal error or clean failure |
| 130 | abort: interrupted |

**Tool**

| Code | Meaning |
|---|---|
| 0 | First bad commit found |
| 1 | Not found: no passing commit within `--max-back` / history |
| 2 | Narrowed to a candidate range only |
| 3 | Usage, config or validation error (bad flags, unknown revision, good not an ancestor, good fails, bad passes) |
| 4 | Runtime error (git failure, clean failure, check script abort, python3 missing/too old from the shim) |
| 130 | Interrupted, after cleanup |

---

## 5. JSON output (schema_version 1, M4)

```json
{
  "schema_version": 1,
  "tool_version": "1.0.0",
  "status": "found | range | not_found | error",
  "exit_code": 0,
  "first_bad": {
    "sha": "...", "short": "...",
    "author_name": "...", "author_email": "...", "author_date": "ISO 8601",
    "subject": "...", "body": "...",
    "url": "https://github.com/... | null", "pr": 123,
    "diff": { "stat": "...", "patch": "... | null" }
  },
  "candidates": [ { "sha": "...", "short": "...", "subject": "..." } ],
  "range": { "good": "sha", "bad": "sha", "commits": 87, "good_source": "given | since | search", "paths": [] },
  "config_hash": "...",
  "checks": { "clean": "...", "setup": null, "build": "...", "test": ["..."], "run": null, "grep": null,
              "grep_absent": false, "retries": 0, "flaky_policy": "strict", "timeout_s": null, "timeout_skip": false },
  "perf": { "command": "...", "runs": 5, "warmup": 1, "tolerance_pct": 10.0,
            "baseline_median_s": 1.92, "spread_pct": 4.1, "threshold_s": 2.112, "unreliable": false,
            "drift": { "remeasured_median_s": 1.95, "drift_pct": 1.6, "exceeded": false } },
  "steps": [ { "sha": "...", "short": "...", "verdict": "good | bad | skip", "reason": "...",
               "phase": "validate | search | bisect | drift", "cached": false, "duration_s": 12.4,
               "attempts": { "passed": 2, "failed": 0 }, "flaky": false, "timed_out": false,
               "perf_median_s": null, "log": ".git/autobisect/logs/<sha>.log" } ],
  "stats": { "steps": 9, "commits_tested": 7, "cache_hits": 2, "skipped": ["sha"], "flaky": ["sha"],
             "retries_used": 3, "duration_s": 84.2 },
  "error": { "message": "...", "hint": "..." }
}
```

`first_bad` is null unless status is `found`; `candidates` is empty unless `range`; `perf` and `error` are null when unused. `patch` is null with `--stat-only`. Documented in `docs/json-schema.md` and pinned by golden tests.

---

## 6. Testing approach

- **Unit (pytest):** cli, config parser, flaky, perf, cache key, exit-code mapping, GitHub URL parsing.
- **Integration (pytest):** a fixture builds throwaway repos with scripted histories and runs the CLI as a subprocess. Flakiness is deterministic (a counter file outside the worktree), never random. Exact tolerance boundaries are unit-tested; integration perf tests use `sleep` with wide margins.
- **End-to-end (bats):** through the shim: python3 missing/too old, `make install`/`uninstall`, one clean regression, a command with spaces, quotes and `;`.
- **Interpreter test (bats):** PATH starts with a directory containing a fake `python3` that exits 1; `AUTOBISECT_PYTHON` points at the real interpreter. The bisect must still succeed, proving the check script does not use PATH.
- **Process-group test:** a check starts a background child that writes a heartbeat file, then sleeps past the timeout. The heartbeat must stop before the next commit starts.
- **Ctrl-C test:** SIGINT to the main pid while a check is sleeping with a background child. Assert: exit 130; working copy, index and `HEAD` unchanged; no worktree or session record left; heartbeat stopped; no cache entry for the interrupted commit; cleanup finished within the bounded wait. A second variant uses a check that ignores SIGTERM to exercise the force-kill path.
- **Golden:** text summary, Markdown report, JSON, with hashes, dates and durations normalised.
- **CI:** ubuntu-latest and macos-latest x Python 3.9 and current stable; ruff, shellcheck, pytest, bats. If macos-latest can't provide 3.9, test 3.9 on Ubuntu only and document it.

---

## 7. Risks and edge cases

**Correctness**
- `any` policy on an intermittent bug can still mark a bad commit good and send the bisect the wrong way. At a 1-in-3 failure rate, 99 % detection needs about 12 attempts. README must say so.
- Default `git clean -fdx` forces a full rebuild on every commit; slow builds need `--no-clean` or a narrower clean command.
- `git clean -fdx` does not remove nested repos or submodule contents; users with submodules need `git submodule update --init` in setup.
- Untracked files from the user's working copy (`.env`, `node_modules`) do not exist in the worktree. Validation catches the resulting failures early; `--copy-in` (M5) is the workaround.
- Perf noise from other load, thermal throttling and cold caches. Warm-up, the spread warning and the drift check mitigate but do not solve it. A cached baseline from another day is the main drift source.
- Commit timestamps are not monotonic, so `--since` picks a starting candidate only.
- Shallow clones and the root commit bound the search.
- Two runs at once in one repo are safe (separate worktrees, atomic cache writes).
- The optional parallel mode cannot use `git bisect run`; it needs its own driver on top of `evaluate_commit`.

**Security**
- The tool exists to run arbitrary commands; the boundary is who supplies them. Command-line commands are trusted; `.autobisect.conf` is not until approved.
- Code inside the commits being tested runs as the user. Bisecting an untrusted repository is running untrusted code.
- Check output is logged as-is. Logs live under `.git/` with mode 0600 and are never embedded in reports; reports list paths only.
- Commit messages and author names are untrusted text: control characters are stripped for terminal output and the Markdown report escapes or fences them.
- Remote URLs may contain tokens; stripped before display.
- `--copy-in` files may contain secrets; they live only in the 0700 temp worktree and are deleted with it.
- A copied `.git` directory could carry a pre-approved `trusted` file. Low risk, documented.

---

## 8. ADRs

| No. | Title | Decision |
|---|---|---|
| 0001 | Language | Python 3.9+ stdlib-only core behind a Bash shim. 3.9 is end-of-life (Oct 2025); the minimum rises once Apple's Command Line Tools ship newer. `from __future__ import annotations`, no 3.10+ features |
| 0002 | Bash version | Shim stays Bash 3.2 compatible; it only locates and checks python3 |
| 0003 | Worktree isolation | Temporary detached worktree; ordered cleanup (wait, force-kill, then reset and remove) on every exit path |
| 0004 | Bisect driver | `git bisect run` with a fixed generated script that pins `sys.executable` and the lib dir; user commands are data in a session file |
| 0005 | Command execution | `/bin/sh -c`, worktree root, scrubbed git env, own process group, group kill on timeout/exit/interrupt |
| 0006 | Flaky policy | Four policies over per-check attempts with early stop; default strict |
| 0007 | Cache key | Commit SHA + SHA-256 of every setting that affects a stored result. Perf entries hold raw measurements; tolerance and baseline are applied at run time and are not in the key |
| 0008 | Config trust | Data-only parser; interactive approval remembered by content hash; ignored non-interactively without `--trust-config` |
| 0009 | Perf measurement | Wall-clock median after warm-up, strict threshold, range-based spread warning, verdict computed at run time, post-run drift check on the good commit |
| 0010 | Pipeline order | clean -> setup -> build -> tests -> grep -> perf |

---

## 9. Resolved decisions

1. `--bad` defaults to `HEAD`.
2. `--since` means "it worked around then" and sets the first search candidate.
3. Clean runs before setup.
4. `--perf` requires `--good`.
5. A perf command that exits non-zero skips the commit.
6. Commands always run under `/bin/sh -c`.
7. Perf metric is wall-clock time only in v1.
8. Spread = (max - min) / median.
9. `--clear-cache` exists.
10. Config approval is remembered by content hash.
11. PR numbers come from offline parsing only.
12. Ctrl-C exits 130.
13. Scenarios in pytest; bats for the shim, install and a small smoke set.
14. "Bad commit passes" exits 3.
15. Minimum git 2.30.
16. Man page is hand-written roff.

---

## 10. Milestone scope by module

| Milestone | Modules |
|---|---|
| M1 (v0.1.0) | shim, launcher, cli (M1 flags), model, errors, gitutil, runner, worktree, session, pipeline (clean/setup/build/test/grep), checkscript, bisect, report (plain text) |
| M2 | flaky, retries and timeouts in the pipeline, cache, search, path filtering |
| M3 | perf, measurement caching, drift check |
| M4 | JSON and Markdown in report, dry run, time estimate, github, config, man page, docs |
| M5 (optional) | `--first-parent`, `--find-fix`, `--copy-in`, parallel testing, Homebrew tap |