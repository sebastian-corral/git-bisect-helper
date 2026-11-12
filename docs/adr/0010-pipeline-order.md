# ADR-0010: Pipeline order

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

For each commit that `git bisect` checks out, the tool can run up to six kinds
of step in a temporary worktree: clean, setup, build, tests, an output match
(grep) and a perf measurement. The order has to be fixed and the same for every
commit, or verdicts for different commits are not comparable.

The open question was where clean goes. The default clean command is
`git clean -fdx`, which deletes every untracked and ignored file. Setup typically
creates exactly such files (`node_modules`, a virtualenv, fetched dependencies).
With setup before clean, clean would delete what setup had just installed and
the build would then fail on every commit.

## Decision

The order per commit is:

**clean -> setup -> build -> tests -> grep -> perf**

Clean runs first, so each commit starts from a pristine tree and setup's output
survives until the commit has been judged. The pipeline stops at the first step
that decides the commit. After the last step the worktree is reset
(`git reset --hard`) so that tracked files changed by a build cannot block git's
next checkout.

## Consequences

- Leftovers from the previous commit never affect the next one.
- Setup and a full build run again on every commit, which costs time. Slow
  projects can pass a narrower `--clean` command or `--no-clean`.
- Perf runs last, so it is measured only on commits that got through the
  earlier steps.
- The order is not configurable. What each step's failure or timeout means is
  defined in design section 3.1.
