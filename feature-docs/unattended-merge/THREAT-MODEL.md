# Threat Model: unattended-merge

## Verdict
threats-identified

## Rationale

**Inspected**: SPEC.md, REQUIREMENTS.md and the task decomposition (tier: full; design step skipped). The feature runs unattended and merges code into the base branch, so the analysis covers every input that influences what gets merged or what gets executed:
- the invocation argument
- integration-branch records
- repository-controlled command strings
- spec and commit text read by the agent
- the commands the agent issues to the guard hook
- gh output
- the result the dispatcher parses
- concurrent merge runs

**Depth**: deep where the domains auth (task0007), input-handling (task0001, task0002, task0004, task0007, task0008) or external-io (task0002-task0006, task0008) apply; standard elsewhere. No task declares data-persistence.

**Consistency note**: task0003 declares external-io, yet `em-workflow/scripts/merge-git.py` appears in no Boundary files line. It reads only git refs and topology of the local repository, and fetches and merges the project's own base branch. None of its decisions depends on text an attacker controls. Conflicted content it surfaces is analysed under TB-4. The base_branch and remote names it receives are validated upstream (TM-2) and by its own C1 identifier checks.

**Not boundaries**: the local git configuration and remote definitions (owned by the same user who runs the skill).

**Role split**: SPEC.md's Security Considerations state what is protected. This document states how each protection can fail and which mitigation prevents it.

## Trust Boundaries

### TB-1: Invocation argument → skill and scripts
Crossing: the feature name passed by the loop-develop dispatcher (another process whose task data is external) into SKILL.md, then into shell commands and script arguments.
Boundary files: em-workflow/skills/merge/SKILL.md, em-workflow/scripts/merge-preflight.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A feature name carrying shell metacharacters or option-like text is interpolated into git / gh / script command lines (FR2) | TM-1 | The name is checked against the feature pattern before any Bash call that would carry it; preflight re-validates it before running git | task0008 AC-1; task0002 AC-1 | VERIFICATION.md TM-1 (TS15, TS16) |

### TB-2: Integration-branch records → preflight decisions
Crossing: workflow.yaml and reviews/round{N}.yaml read from the integration branch tip (content written by earlier runs and by anything merged into that branch) into merge-preflight.py. Its output values are later placed on command lines by the skill.
Boundary files: em-workflow/scripts/merge-preflight.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A base_branch value with shell metacharacters or a leading `-` reaches git / gh command lines (FR3, NFR4) | TM-2 | base_branch is accepted only as a valid branch name within a conservative character set, not starting with `-`; otherwise stop `base_branch_invalid` | task0002 AC-3 | VERIFICATION.md TM-2 (TS16) |
| Elevation of privilege | YAML content constructs arbitrary objects while being parsed (NFR4) | TM-3 | Safe loading only; a document that is not a mapping, or has wrong types, stops `record_unreadable` | task0002 AC-2 | VERIFICATION.md TM-3 (TS16) |
| Tampering | Malformed or unexpected status / severity / resolution values are read permissively, so an unverified feature or an unresolved critical/high finding passes the merge gate (FR4, FR5) | TM-4 | Fail-closed reading: only exact completed / skipped passes; verify result fail fails; an unreadable latest round stops; critical/high passes only with resolution exactly fixed or declined | task0002 AC-4, AC-5 | VERIFICATION.md TM-4 (TS3, TS4) |

### TB-3: Repository-controlled verification commands → shell execution
Crossing: build / test / e2e command strings from workflow.yaml, executed by the unattended session inside the integration worktree.
Boundary files: em-workflow/scripts/merge-preflight.py, em-workflow/skills/merge/SKILL.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An unapproved or altered command string runs without the user's approval (FR13) | TM-5 | Approval is checked through bash_guard's list mode before any command runs; an unapproved command stops `commands_unapproved` without recording approval; approved strings run verbatim as standalone calls, so the existing hook enforces the exact match | task0002 AC-6; task0008 AC-2 | VERIFICATION.md TM-5 (TS11, TS15) |

### TB-4: Spec, commit and conflicted text → agent conflict resolution
Crossing: text of feature-docs/{feature}/, the base-side feature-docs/{other}/, commit messages and conflicted file contents, read by the agent while resolving conflicts (untrusted text inside the LLM prompt).
Boundary files: em-workflow/skills/merge/SKILL.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Instruction-shaped text steers the agent toward commands beyond conflict resolution, skipped verification, or forbidden operations (NFR4, NFR2) | TM-6 | SKILL.md treats that text as data; the conflict step may only edit, stage and commit the conflicted paths without hook bypass, or abort; verification commands always run after resolution and before any push or merge | task0008 AC-5 | VERIFICATION.md TM-6 (TS15, manual check 2) |
| Spoofing | A commit message or branch-name claim misattributes a conflict to a base-side feature, so an unrelated spec drives the resolution (FR12) | TM-7 | An origin feature is accepted only when its name matches the feature pattern and its feature-docs directory exists on the base side; otherwise abort as `conflict_unattributable` | task0008 AC-5 | VERIFICATION.md TM-7 (TS15, manual check 2) |

### TB-5: Agent-issued Bash command → destructive-guard allow
Crossing: the command string and payload working directory from the agent session into the PreToolUse hook. An allow skips the ask / deny that otherwise stops unattended runs (privilege change).
Boundary files: em-workflow/hooks/destructive-guard.py, em-workflow/hooks/tests/destructive-guard-cases.json, em-workflow/hooks/tests/run-destructive-guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A gh pr merge variant obtains allow (FR20). Variants: short flags, `--admin` / `--auto` / `--squash` / `--rebase` / `--delete-branch` in any spelling, `--repo` / `-R`, environment-variable prefixes, a malformed SHA, extra tokens | TM-8 | Exact token allow-list for the canonical form; any other token or prefix keeps the existing decision (ask, deny under CLAUDE_BATCH) | task0007 AC-1, AC-2 | VERIFICATION.md TM-8 (TS9, TS10, TS22) |
| Elevation of privilege | An allowed merge segment masks a dangerous later segment of the same command (FR20) | TM-9 | Every segment is still judged; the command's decision is the most restrictive across segments | task0007 AC-3 | VERIFICATION.md TM-9 (TS10) |
| Spoofing | A working directory only looks like an integration worktree, through traversal segments or a non-feature-shaped segment (FR20) | TM-10 | The working directory is normalized before matching; the feature segment must match the pattern and the next segment must be exactly `integration` | task0007 AC-4 | VERIFICATION.md TM-10 (TS22) |

### TB-6: GitHub (gh output) → PR decisions
Crossing: repository, PR, mergeability and check data from an external service, through gh, into merge-pr.py and merge-ci-wait.py.
Boundary files: em-workflow/scripts/merge-pr.py, em-workflow/scripts/merge-ci-wait.py
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | gh resolves a repository other than the chosen remote's, so the PR is created or merged in the wrong repository (FR6, FR8, FR17) | TM-11 | gh's default repository for the project must equal the chosen remote's repository; otherwise stop `remote_unresolved` | task0004 AC-2 | VERIFICATION.md TM-11 (TS24) |
| Tampering | The PR head changes after verification, so an untested head is merged (FR15, FR17) | TM-12 | CI wait and the pre-merge state check require the PR head to equal the pushed / verified SHA (else `pr_head_moved`); the merge is pinned with `--match-head-commit` on that SHA | task0004 AC-4; task0006 AC-5; task0008 AC-2 | VERIFICATION.md TM-12 (TS17, TS25, TS15) |
| Denial of service | gh or CI never finishing stalls the unattended run (FR15, NFR1) | TM-13 | A per-invocation budget below the Bash limit, a time limit on every gh call, and an absolute 60-minute deadline | task0006 AC-3, AC-4 | VERIFICATION.md TM-13 (TS6, TS25) |

### TB-7: Merge result → dispatcher
Crossing: the final assistant message, parsed by the loop-develop dispatcher (another process); its values include text derived from untrusted sources (command output, finding ids, gh data).
Boundary files: em-workflow/scripts/merge-result.py, em-workflow/references/merge-result.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Line breaks, quotes or escape sequences in a value forge extra keys or a fake success result (FR21) | TM-14 | Closed vocabularies are validated; every value is single-line and escaped by the format rules; invalid input is replaced by an `internal_error` result that never echoes the value | task0001 AC-2, AC-3 | VERIFICATION.md TM-14 (TS12) |
| Information disclosure | Absolute home-directory paths or Notion URLs from command output reach the dispatcher (NFR7) | TM-15 | Redaction is applied to every value before rendering | task0001 AC-4 | VERIFICATION.md TM-15 (TS21) |

### TB-8: Concurrent merge runs → shared lock
Crossing: other processes (merge runs of other features, or of the same feature) sharing the repository's lock file and holder record in the git common dir.
Boundary files: em-workflow/scripts/merge-lock.py
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Two runs integrate and merge at the same time and land an untested combination on the base (FR10) | TM-16 | An exclusive non-blocking lock held from integration through the merge; a busy lock stops `lock_busy` | task0005 AC-3; task0008 AC-4 | VERIFICATION.md TM-16 (TS8) |
| Spoofing | A run takes a stale holder record, or another run's record for the same feature, as proof that it holds the lock (FR10) | TM-17 | A per-run token; the lock counts as held only when the record carries this run's token and the recorded holder process is alive; checked again right before merging | task0005 AC-4, AC-5 | VERIFICATION.md TM-17 (TS23) |
