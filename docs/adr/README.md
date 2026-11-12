# Architecture Decision Records

An ADR records one decision that shapes `git-autobisect`: what was decided, why,
and what it costs. Each is short enough to read on one screen. The accepted design
([../design.md](../design.md), section 8) lists the decisions; the ADRs here give
the reasoning. An accepted ADR is not rewritten: to change a decision, add a new
ADR and set the old one's status to `Superseded by ADR-NNNN`.

## Index

| No. | Title | Status | Decision |
|---|---|---|---|
| [0001](0001-language.md) | Language | Accepted | Python 3.9+ stdlib-only core behind a Bash shim |
| [0002](0002-bash-version.md) | Bash version | Accepted | Shim stays Bash 3.2 compatible; it only locates and checks python3 |
| 0003 | Worktree isolation | Planned | Temporary detached worktree; ordered cleanup on every exit path |
| 0004 | Bisect driver | Planned | `git bisect run` with a fixed generated script; user commands are data in a session file |
| 0005 | Command execution | Planned | `/bin/sh -c`, worktree root, scrubbed git env, own process group, group kill |
| 0006 | Flaky policy | Planned | Four policies over per-check attempts with early stop; default strict |
| 0007 | Cache key | Planned | Commit SHA + SHA-256 of every setting that affects a stored result |
| 0008 | Config trust | Planned | Data-only parser; approval remembered by content hash |
| 0009 | Perf measurement | Planned | Wall-clock median after warm-up, strict threshold, drift check |
| [0010](0010-pipeline-order.md) | Pipeline order | Accepted | clean -> setup -> build -> tests -> grep -> perf |

"Planned" means the decision is made in the design but its ADR is not written yet.

## Adding an ADR

1. Copy the template below to `NNNN-short-title.md`, using the number from the index.
2. Fill in every section. Keep it to one screen (about 40 lines).
3. Update the row in the index: link the number and set the status.

## Template

```markdown
# ADR-NNNN: Title

- **Status:** Proposed | Accepted | Superseded by ADR-NNNN
- **Date:** YYYY-MM-DD

## Context

The problem, the constraints, and the options that were considered.

## Decision

What was chosen, stated so that it can be checked.

## Consequences

What this makes easier, what it costs, and what would make us revisit it.
```
