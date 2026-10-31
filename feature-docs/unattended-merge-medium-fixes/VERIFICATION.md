# Verification Document: unattended-merge-medium-fixes

## Overview
**Feature**: unattended-merge-medium-fixes / **SPEC.md**: `feature-docs/unattended-merge-medium-fixes/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/unattended-merge-medium-fixes/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty).
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors.
- Focused run: `python3 -m unittest tests.test_merge_skill_doc tests.test_merge_preflight tests.test_merge_pr tests.test_merge_ci_wait`
- Coverage target: not measured (no coverage tool is configured in `project.components`). FR6 requires instead that each fix has a test that fails before it and passes after it.

### Test Scenarios from SPEC.md
TS1 to TS8 are SPEC.md's scenarios. TS9 to TS13 are added here so that FR7 and the non-functional requirements also have a verifying item.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | FR1, SKILL.md step 13.3: before the `git merge` block, the integration branch tip is compared with `head_sha`, and a mismatch ends `verification_failed`. After the merge, the second parent is checked, and a mismatch adds a note to the `merged` detail | `tests/test_merge_skill_doc.py` asserts the order, the outcomes and the `detail` rule exception; the tests fail on the pre-change SKILL.md | Unit (document) |
| TS2 | FR2, SKILL.md step 10: the block immediately before the `git status` / `git rev-parse HEAD` blocks is `cd "<worktree_path>"`, and the check is stated to run when `commands` is empty | `tests/test_merge_skill_doc.py` passes; fails on the pre-change SKILL.md | Unit (document) |
| TS3 | FR3, SKILL.md step 6: after `held` and before step 7's `worktree-state`, `merge-git.py merged` and `merge-pr.py resolve` re-decide. merged stops the hold task and takes the already-merged path; stop and PR `none` are handled as FR3 states | `tests/test_merge_skill_doc.py` passes; fails on the pre-change SKILL.md | Unit (document) |
| TS4 | FR4: a `test_command` with leading/trailing blanks and a trimmed approval entry proceeds, with the original command in the output. `make a` + line break, and an inner-whitespace difference, stay `commands_unapproved` | `tests/test_merge_preflight.py` passes; the trailing-blank case fails on the pre-change script | Unit |
| TS5 | FR4: for commands with leading/trailing blanks, bash_guard.py's own approval decision and preflight's verdict agree under the same approval store | `tests/test_merge_preflight.py` passes; fails on the pre-change script | Integration (child processes) |
| TS6 | FR5: the remote resolves to ghe.example/acme/service and gh's default to github.com/acme/service (the reproduction case) | `merge-pr.py repo` stops `remote_unresolved` naming both identifiers | Unit (stubbed gh) |
| TS7 | FR5: host and owner/name match, letter case aside | `github` with `HOST/OWNER/NAME`; a malformed host stops `remote_unresolved` without echoing it; a missing URL field is an internal failure | Unit (stubbed gh) |
| TS8 | FR5: `merge-pr.py resolve` / `state` and `merge-ci-wait.py` take `--repo HOST/OWNER/NAME` | Passed to gh verbatim; `OWNER/NAME` still accepted; malformed values exit 2 with empty stdout and no gh call | Unit (stubbed gh) |
| TS9 | FR7: the review phase runs architecture and spec over (a) the unattended-merge change set (`feature-docs/unattended-merge/reviews/round2.yaml` `scope.changed_files`) and (b) this feature's diff, split into reviewer-sized targets | In this feature's `reviews/roundN.yaml`, every architecture and spec run for every split target of both groups is `completed`; none is `skipped` with `review_data_too_large` | Manual (record inspection) |
| TS10 | NFR1: the version fields are untouched | The diff from `workflow.implement.base_commit` to the integration tip changes no `version` in `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` | Integration (diff check) |
| TS11 | NFR5, as-6, as-7: the out-of-scope files are untouched | The same diff changes nothing under `feature-docs/unattended-merge/`, and none of `em-workflow/hooks/bash_guard.py`, `em-workflow/scripts/merge-lock.py`, `em-workflow/hooks/merge_pr_allow.py`, `em-workflow/hooks/tests/destructive-guard-cases.json`, `em-workflow/scripts/merge-result.py` | Integration (diff check) |
| TS12 | NFR6: redaction | The commit messages of the diff range and the files under `feature-docs/unattended-merge-medium-fixes/` and `test-docs/unattended-merge-medium-fixes/` contain no Notion URL and no home-directory absolute path | Integration (text search) |
| TS13 | NFR3, NFR4: the new SKILL forms of steps 6, 10 and 13.3 keep the skill's invariants | The existing document tests pass over the new forms: literal-only forms, known command heads, timeout of at most 600 s, the closed script-call set, no command form naming workflow.yaml or redirecting to a file | Unit (document) |

## Code Quality Verification
- Format: none (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Local route: a tip that moved after verification ends `verification_failed` without merging; a second parent different from `head_sha` keeps `merged` with a note in `detail` | TS1 |
| AC2 | Step 10 has a standalone `cd "<worktree_path>"` right before the HEAD check, which runs even when `commands` is empty | TS2 |
| AC3 | Step 6 re-decides after `held`; merged stops the lock and takes the already-merged path | TS3 |
| AC4 | `test_command` `'make test '` with store `'make test'` proceeds and keeps `'make test '`; `'make a\n'` stays `commands_unapproved` | TS4, TS5 |
| AC5 | The ghe.example / github.com case stops `remote_unresolved`; a full match returns `github` with `HOST/OWNER/NAME` | TS6, TS7 (plus TS8 for the consumers) |
| AC6 | `python3 -m unittest discover -s tests` passes | Test Verification command |
| AC7 | architecture / spec reviews complete for every split target of both groups; no `review_data_too_large` skip remains | TS9 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001 | TS2 |
| FR3 | task0001 | TS3 |
| FR4 | task0002 | TS4, TS5 |
| FR5 | task0001, task0003, task0004 | TS6, TS7, TS8 |
| FR6 | task0001, task0002, task0003, task0004 | TS1, TS2, TS3, TS4, TS5, TS6, TS7, TS8 (each fails on the pre-change file) |
| FR7 | none (review-phase obligation) | TS9 |
| NFR1 | task0001, task0002, task0003, task0004 | TS10 |
| NFR2 | task0001, task0002, task0003, task0004 | TS1, TS3, TS4, TS6, TS7, TS8 |
| NFR3 | task0001 | TS13 |
| NFR4 | task0001, task0003, task0004 | TS7, TS8, TS13 |
| NFR5 | task0001, task0002, task0003, task0004 | TS11 |
| NFR6 | task0001, task0002, task0003, task0004 | TS12 |

## Manual Testing (E2E Not Possible)
- [ ] TS9: inspect this feature's review round records as stated in the TS9 row.
- [ ] M2: read SKILL.md steps 6, 10 and 13.3 and the already-merged path end to end. Every terminal after the lock stops the hold task before rendering. The new re-decision, tip check and second-parent check read as one consistent flow with the existing step numbering and the result-value tables.

## Performance / Security Verification
- TM-1: approval compares only the FR4 trim of the command, with the line-break / CR check on the raw value, an exact inner match and the original command emitted. Checked by TS4 (trailing-blank proceed, line-break and inner-whitespace stops) and TS5 (agreement with bash_guard.py).
- TM-2: host and owner/name are both compared, case-insensitively, from gh's answers; a mismatch stops `remote_unresolved` and the output is `HOST/OWNER/NAME`. Checked by TS6 (cross-host case) and TS7 (match and case-insensitive match).
- TM-3: a host failing the C1 host rule stops `remote_unresolved` without echoing it; a missing URL field is an internal failure. Checked by TS7 (malformed-host and missing-URL cases).
- TM-4: only the two C1 `--repo` forms are accepted, verbatim, before any gh call; others exit 2. Checked by TS8 (both accepting scripts).
- TM-5: the integration tip is checked against `head_sha` right before the local merge, and the second parent right after it. Checked by TS1.
- TM-6: the merged decision is repeated after `held`, with lock-stop-first handling of merged / stop / none. Checked by TS3.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit / integration tests (TS1 to TS8, TS13) | 9 | 9 | 0 | 0 |
| Full test suite (AC6) | 1 | 1 | 0 | 0 |
| Change-set checks (TS10 to TS12) | 3 | 3 | 0 | 0 |
| Security (TM-1 to TM-6) | 6 | 6 | 0 | 0 |
| Manual (TS9, M2) | 2 | 0 | 0 | 2 |
| **Total** | 21 | 19 | 0 | 2 |
