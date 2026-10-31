# Implementation Plan: unattended-merge-medium-fixes

## Overview
This plan fixes the five medium findings left by unattended-merge review round 2. Three are in the merge skill's procedure text (FR1 to FR3), one is in the approval comparison of `merge-preflight.py` (FR4), and one is in the repository identity of `merge-pr.py` / `merge-ci-wait.py` (FR5). Every fix gets a recurrence test (FR6). FR7 (split architecture / spec review) belongs to this run's review phase, not to an implement task.

## Technology Stack
- **Language**: Python 3, standard library only (scripts and tests).
- **Test framework**: `unittest`, run by `python3 -m unittest discover -s tests`.
- **Procedure document**: `em-workflow/skills/merge/SKILL.md` (Markdown, Japanese, executed by the agent).
- **External tools**: git and gh, already used. No gh command shape changes except the repository selector value (C1).
- **New dependencies**: none, so no license is recorded (`project.license: none`).

## Layer Structure
1. **Procedure layer**: `skills/merge/SKILL.md`. It calls the decision scripts, issues guard-sensitive operations directly, and holds run values (`repo`, `head_sha`, ...) only in the session.
2. **Decision scripts**: `scripts/merge-preflight.py`, `merge-git.py`, `merge-pr.py`, `merge-ci-wait.py`, `merge-lock.py`. Each prints one JSON object per call and exits 0 for a decision, 1 for an internal failure and 2 for a usage error.
3. **Tools**: git, gh, and `hooks/bash_guard.py --list` (read only, called by preflight).

Allowed direction: procedure → scripts → tools. Scripts never call each other; the only script-to-hook call is preflight → `bash_guard.py --list`. Tests live in `tests/` at the repository root and run scripts as child processes, or read SKILL.md as text.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1: repository identifier (`--repo` value) | The single textual form that names a GitHub repository between `merge-pr.py repo`, the skill and the PR read scripts | Two forms only, segments separated by `/`: `OWNER/NAME` (legacy, still accepted, as-3) and `HOST/OWNER/NAME`. HOST: 1 to 253 characters, only `[A-Za-z0-9.-]`, first character alphanumeric. So no port, no userinfo, no scheme, and never option-shaped. OWNER and NAME: each script keeps its existing owner/name rule. One segment, four or more segments, or an empty segment is malformed. **Accepting side** (`merge-pr.py resolve` / `state`, `merge-ci-wait.py`): a malformed value is a usage error (exit 2, empty stdout, no gh call). An accepted value goes to every gh call verbatim as the repository selector. **Producing side** (`merge-pr.py repo`): the `github` outcome always carries the three-segment form, and only after the host has passed the HOST rule | task0001, task0003, task0004 |
| C2: `merge-pr.py repo` outcome | Decide whether the chosen remote and gh's default repository are the same repository | Outcomes and keys are unchanged: `github` with `repo`; stop `remote_not_github` / `remote_unresolved`; exit 1 on an internal failure. Only two things change: `repo` is the C1 three-segment form, and a host mismatch or a host failing the C1 rule is a `remote_unresolved` stop | task0001 (consumer), task0003 (implementer) |
| C3: `merge-pr.py resolve` / `state` decisions | PR decisions consumed by skill steps 5, 6 and 13 | task0003 changes only the accepted `--repo` forms (C1). The outcome sets (`merged` / `open` / `none` / stop `pr_draft` / `pr_closed` for `resolve`; `merged` / `ready` / stops for `state`), their keys and their precedence stay as they are | task0001 (consumer), task0003 (implementer) |
| C4: `merge-git.py merged` decision | Local-route merged decision, now also called after the lock (FR3) | Unchanged script: `merged` / `not_merged`, stop `base_branch_invalid` / `integration_branch_missing`. No task modifies `merge-git.py` | task0001 (consumer) |

## Conventions
- **Fail-closed (NFR2)**: every case a task cannot decide ends as a stop reason, a usage error or an internal failure. No case resolves toward merging, approving or `github`.
- **Script output**: one JSON object on one stdout line; exit codes 0 / 1 / 2 as today. `detail` echoes only validated values (identifiers, 40-hex SHAs, C1 identifiers) and never echoes rejected text.
- **Recurrence tests (FR6)**: each new test fails against the pre-change file and passes after the change. An existing test that pins the old behavior is rewritten to the new expectation in the same task, never deleted without a replacement. Each task names these tests in its plan.
- **No state (NFR3)**: no task adds a state file or writes workflow.yaml.
- **Literals (NFR4)**: values placed on a command line by the skill come from validated script output, the C1 identifier included.
- **Files no task touches**: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (NFR1), `em-workflow/hooks/bash_guard.py`, `em-workflow/scripts/merge-lock.py`, `em-workflow/hooks/merge_pr_allow.py`, `em-workflow/hooks/tests/destructive-guard-cases.json` (as-6), `em-workflow/scripts/merge-result.py` (as-7), `em-workflow/scripts/merge-git.py`, and everything under `feature-docs/unattended-merge/` (NFR5).
- **Redaction (NFR6)**: commit messages, `feature-docs/unattended-merge-medium-fixes/` and `test-docs/unattended-merge-medium-fixes/` carry no Notion URL and no home-directory absolute path.
- **Language**: SKILL.md text stays in Japanese, matching the existing document; code comments and docstrings stay in English.

## Cross-task Design Decisions

### D1: Host-qualified repository identifier end to end
- **Decision**: `merge-pr.py repo` emits `HOST/OWNER/NAME` (C1). The skill keeps that value as `repo` and passes it to every later `--repo`. `merge-pr.py resolve` / `state` and `merge-ci-wait.py` accept it and give it to gh unchanged. `gh pr create` and `gh pr merge` keep their current forms with no `--repo`; their target is gh's default repository, which C2 has now confirmed down to the host.
- **Rationale**: FR5. Comparing the host only in `repo` would still leave the later reads to gh's default host. Passing the host pins them to the host that was compared.
- **Affected tasks**: task0001 (step 5.1 and the held value), task0003 (producer and `resolve` / `state` acceptance), task0004 (`merge-ci-wait.py` acceptance).

### D2: The legacy form stays accepted
- **Decision**: both accepting scripts keep `OWNER/NAME` (as-3), with the same verbatim pass-through.
- **Rationale**: existing callers and tests keep working, and the three tasks can land in any order without a broken intermediate state.
- **Affected tasks**: task0003, task0004.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The tasks run in parallel, so the skill may pass `HOST/OWNER/NAME` before a script accepts it | Medium | High | C1 is the single contract for all three tasks. TS8 checks both accepting scripts, and the full suite runs in verify |
| Existing tests pin the old behavior and fail after the change (preflight's trailing-blank test, merge-pr's stub request shape and its two-segment `--repo` assertion, the skill doc's resolve-form count and its cd-right-before-merge assertion) | High | Medium | Each owning task rewrites those tests to the new expectation, as named in its plan |
| The FR1 check-then-merge window remains, because the branch-name merge form is kept (as-1) | Low | Medium | The post-merge second-parent check records the residual case in the merged `detail` (THREAT-MODEL TM-5) |
| A revision suffix such as `^` or `~` in a new skill form is globbed by some shell configurations | Medium | Medium | task0001 requires new git forms that carry no shell-special characters |

## Open Questions
- [ ] FR7 has no implementing task. It is an obligation of this run's review phase: run the architecture and spec perspectives over two groups, each split into reviewer-sized targets. One group is the unattended-merge change set (`feature-docs/unattended-merge/reviews/round2.yaml` `scope.changed_files`); the other is this feature's diff. VERIFICATION.md TS9 checks the result.
- [ ] `em-workflow/references/merge-result.md` describes `verification_failed` as a failed or timed-out command only. The step-10 HEAD mismatch already uses this reason, and FR1 adds the tip mismatch. SPEC limits the change set, so this document is left as is.
