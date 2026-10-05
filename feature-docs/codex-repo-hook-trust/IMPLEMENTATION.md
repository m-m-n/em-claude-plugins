# Implementation Plan: codex-repo-hook-trust

## Overview
Establish on Codex 0.160.0 whether hook definitions in the working directory's
Codex configuration execute under the launch routes of the em-workflow and
em-review Codex wrappers, record the evidence, and then either change the
launch of every route on which they execute (pinned by tests) or record in
codex-interactive-guard-hook TB-3 that no route executes them.

## Technology Stack
- **Bash**: the two existing wrapper scripts (em-workflow/scripts/run_codex_exec.sh, em-review/scripts/run_codex_exec.sh)
- **Python 3 standard library (unittest)**: tests under tests/ (NFR2)
- **Codex CLI 0.160.0**: the subject of the investigation and of the real-Codex test; an existing external tool, not a new dependency
- **New dependencies**: none (project.license is none; nothing to record)

## Layer Structure
- **Launch layer** — the two wrapper scripts. Each run assembles exactly one
  codex exec invocation for its route and mode.
- **Test layer** — tests/. Exercises the launch layer only by running the
  wrapper scripts, with a stub codex first on PATH or with the real codex;
  never by reaching into wrapper internals.
- **Record layer** — the findings record
  (feature-docs/codex-repo-hook-trust/HOOK-TRUST-FINDINGS.md) holds the
  evidence; codex-interactive-guard-hook THREAT-MODEL.md TB-3 holds the
  threat-model status and cites the findings record; the wrapper comments
  state the result for their own routes.

Allowed direction: tests depend on the launch layer; TB-3 and the wrapper
comments depend on the findings record; the launch layer depends on neither.

## Vocabulary
- **Route** and **working directory**: as defined in REQUIREMENTS.md section 13.
- **Repository hook**: a hook definition placed in the working directory's
  Codex configuration (any location Codex 0.160.0 reads that the repository
  under review controls).
- **Executing route**: a route on which at least one repository hook ran in
  at least one probe condition (for the --litellm route: trusted or not
  trusted in the user config).
- **Branch E**: at least one route is executing. **Branch N**: no route is
  executing.
- **Protective specification**: whatever the wrapper hands to codex on an
  executing route so that Codex 0.160.0 does not execute repository hooks.

## Shared Components
This feature has one implementation task (see D1), so no component is shared
between concurrently implemented tasks. The row below is the contract any
later rework task of this feature works against.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Findings record (feature-docs/codex-repo-hook-trust/HOOK-TRUST-FINDINGS.md) | Single source of the FR1 evidence, the per-route verdict and the branch taken | Post: states, per route, executing / not executing on positively controlled evidence, and the branch (E or N). Every launch composition, test and TB-3 statement of this feature is consistent with it; a later change that contradicts it updates the record first | task0001 (writer); later rework tasks (readers) |

## Conventions
- **Codex home isolation (NFR1)**: every Codex launch made by the
  investigation or by a test runs with HOME and CODEX_HOME pointed at
  temporary directories. Trust entries, the litellm profile and credentials
  exist only there; the user's real Codex home is neither read nor written.
- **Credentials (NFR5)**: no committed file and no test output carries a
  credential value; records name credentials by variable name only.
- **Wrapper parity (NFR4)**: a launch change on a route both wrappers have
  is made in both, by the same means, in the same change. The --litellm route
  exists only in the em-workflow wrapper.
- **Evidence over absence**: a "not executed" verdict needs a positive
  control showing the same hook definition does run where Codex is known to
  load it; otherwise the verdict is "unobservable", with the reason.
- **Bounded launches**: every real Codex launch has a wall-clock bound and
  leaves no process behind.

## Cross-task Design Decisions

### D1: One task for the whole feature
Every deliverable (findings record, launch change, tests, TB-3 record,
wrapper comments) depends on the FR1 runtime outcome, and tasks run fully in
parallel with no ordering. Splitting would force sibling tasks either to
guess the outcome or to repeat the investigation independently and possibly
disagree. The single task therefore carries eight Acceptance Criteria, one
more than the usual size guideline. Affected: task0001.

### D2: Route classification rule
A route counts as executing when any of its probe conditions executed. FR3
applies only to executing routes (SPEC.md FR3); non-executing routes keep
their launch composition. Affected: task0001 and any rework task touching the
launch.

### D3: TB-3 is updated in both branches
SPEC.md's second Objective closes the TB-3 open item in every case. Branch N
records the FR4 content; Branch E records the launch change and any route on
which the wrapper's guard no longer fires (A1). Affected: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The investigation environment has no credential source usable without the real Codex home, so hook events that need a model turn never fire | Medium | High — a false "not executed" | Positive-control rule; such events are recorded as unobservable; a route with no observable event at all stops the task as a plan deviation |
| The installed codex does not report 0.160.0 | Low | High | The record states the reported version; the task stops as a plan deviation when it is not 0.160.0 |
| The protective specification also keeps the wrapper's own guard from firing | Medium | Medium | A1 priority (repository hooks not executed wins) and a TB-3 record of the affected route |
| The protective specification on the --litellm route also drops the litellm profile the route needs | Medium | High | The post-change probe on that route must show the launch still runs with -p litellm -m MODEL |
| The real-Codex test passes vacuously because the hook never fires in the test environment | Medium | High | A control launch without the specification must create the marker; otherwise the test skips |
| A later Codex version changes which configuration layers it reads | Medium | Medium | Outside this feature; the real-Codex test skips on other versions and the stub test still pins the specification |

## Open Questions
- [ ] Which credential source the investigation uses under NFR1 is an environment fact the implementer establishes; when none exists for a route, that route's model-turn events are recorded as unobservable rather than probed with the real Codex home.
