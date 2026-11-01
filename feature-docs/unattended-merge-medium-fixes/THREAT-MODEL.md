# Threat Model: unattended-merge-medium-fixes

## Verdict
threats-identified

## Rationale

**Inspected**: SPEC.md, REQUIREMENTS.md, the four task plans (tier: full; design step skipped), and the current text of `em-workflow/skills/merge/SKILL.md`, `em-workflow/scripts/merge-preflight.py`, `em-workflow/scripts/merge-pr.py`, `em-workflow/scripts/merge-ci-wait.py`, `em-workflow/hooks/bash_guard.py` (read only, unchanged) and their tests. The feature changes how the unattended merge decides what is approved, which repository it talks to, and what commit it merges, so the analysis covers every input whose handling the feature changes:
- verification command strings compared against the approval store (FR4)
- repository identity answered by gh for the remote and for gh's default (FR5)
- the `--repo` value handed back to the scripts by the skill (FR5)
- the integration branch ref between verification and the local merge (FR1)
- concurrent merge runs of the same feature around lock acquisition (FR3)

**Depth**: deep where the domains auth (task0002), input-handling (task0002, task0003, task0004) or external-io (task0001, task0003, task0004) apply. No task declares data-persistence.

**Not boundaries**:
- FR2 (a standalone `cd` into the worktree before the HEAD check) moves no data between parties. The defect it fixes fails closed (`verification_failed`), so it is a correctness and availability fix, not a threat.
- The merged `detail` note added by FR1 is fixed text plus validated 40-hex SHAs, rendered by the unchanged `merge-result.py` (as-7). The existing result-boundary protections of unattended-merge apply unchanged.
- The local git configuration and remote definitions are owned by the user who runs the skill.

**Residual risk (FR1)**: the branch-name merge form is kept (as-1), so the window between the tip check and the merge is narrowed, not closed. The post-merge second-parent check makes the residual case visible in the result instead of silent.

**Relation to unattended-merge**: TM-2 refines unattended-merge's TM-11 (host added to the identity), and TM-1 adjusts the comparison under its TM-5. That document is not modified (NFR5).

**Consistency**: every task that declares auth, input-handling or external-io has at least one file on a `Boundary files` line below. Test files are not boundary files.

## Trust Boundaries

### TB-1: Repository-controlled verification commands → approval comparison
Crossing: build / test / e2e command strings from workflow.yaml on the integration branch tip (repository content), compared by merge-preflight.py against the user-owned approval store that `bash_guard.py --list` reports. The comparison authorizes unattended execution.
Boundary files: em-workflow/scripts/merge-preflight.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Relaxing the exact match lets a command that differs from the approved string by more than leading/trailing blanks pass. Examples: a trailing line break, an embedded CR or line break, or different inner whitespace (FR4, NFR2) | TM-1 | Only the trim FR4 names is applied, and only for the comparison. That trim is identical to bash_guard's `approved_for()`. The line-break / CR check stays on the raw value, inner whitespace is compared exactly, and the emitted command is the original string, so the hook judges the exact string that runs | task0002 AC-1, AC-2, AC-3 | VERIFICATION.md TM-1 (TS4, TS5) |

### TB-2: gh repository answers → repository identity decision
Crossing: repository data from an external service, through gh, into `merge-pr.py repo`. One answer is for the chosen remote's URL; the other is for gh's own default repository, which `gh pr create` / `gh pr merge` target.
Boundary files: em-workflow/scripts/merge-pr.py
Depth: deep (external-io, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A repository on another host with the same owner/name passes as the chosen remote's repository. The push and the PR operations then reach different hosts (FR5) | TM-2 | Host and owner/name are taken from gh's answer on both sides and compared case-insensitively. Either mismatch stops `remote_unresolved`, with both host-qualified identifiers in `detail`. The `github` outcome carries `HOST/OWNER/NAME` | task0003 AC-1, AC-2 | VERIFICATION.md TM-2 (TS6, TS7) |
| Tampering | A host text from gh's answer with a port, userinfo or other characters reaches script output and later command lines (FR5, NFR4) | TM-3 | The host must satisfy the host rule of IMPLEMENTATION.md C1; otherwise stop `remote_unresolved` without echoing the rejected text. A missing or non-string URL field is an internal failure. Nothing is emitted before validation | task0003 AC-3 | VERIFICATION.md TM-3 (TS7) |

### TB-3: `--repo` argument → PR read scripts → gh
Crossing: the `--repo` value the agent session places on the command line (taken from an earlier script output, in a session that also reads untrusted text) into `merge-pr.py resolve` / `state` and `merge-ci-wait.py`. Those scripts hand it to gh as the repository and host selector.
Boundary files: em-workflow/scripts/merge-pr.py, em-workflow/scripts/merge-ci-wait.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A malformed or option-shaped `--repo` value selects an unintended host or repository, or is read by gh as an option (FR5, NFR4) | TM-4 | Both scripts accept only the two forms of IMPLEMENTATION.md C1. Anything else is a usage error (exit 2, empty stdout) before any gh call. An accepted value is passed to gh verbatim | task0003 AC-4, AC-5; task0004 AC-1, AC-3 | VERIFICATION.md TM-4 (TS8) |

### TB-4: Integration branch ref → local merge into base
Crossing: the integration branch ref in the shared repository. Processes outside the run can advance it after verification. The skill's local merge resolves it by name in the main working tree (FR1).
Boundary files: em-workflow/skills/merge/SKILL.md
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A commit added to the integration branch after verification is merged into the base branch unverified (FR1) | TM-5 | Right before the merge, the integration branch tip must equal `head_sha`; otherwise end `verification_failed` without merging. After the merge, HEAD's second parent is compared with `head_sha`, and a mismatch or unreadable parent is recorded in the merged `detail` | task0001 AC-1, AC-2 | VERIFICATION.md TM-5 (TS1) |

### TB-5: Concurrent merge runs of the same feature → post-lock decision
Crossing: the base branch and PR state another merge run of the same feature can change between this run's merged decision and its lock acquisition.
Boundary files: em-workflow/skills/merge/SKILL.md
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A later run takes the lock after an earlier run already merged. It then integrates again, adds redundant merge commits to the base or reports a wrong result (FR3) | TM-6 | After `held`, the merged decision is repeated with the same scripts before step 7. merged ends `already_merged` after stopping the hold task. stop ends with its reason after stopping the hold task. A PR route `none` is `internal_error` | task0001 AC-4, AC-5 | VERIFICATION.md TM-6 (TS3) |
