# Threat Model: large-diff-review-coverage

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md of this feature (tier full), the review
phase protocol, the codex-reviewer agents and review protocols of both plugins,
and the batch reporting document. SPEC.md's Security Considerations defines no
security requirement, but the feature adds three crossings of different trust:
paths and file contents of the reviewed tree read by a new orchestrator-side
script outside the Codex sandbox, untrusted reviewer and LLM output that now
decides whether a perspective counts as reviewed, and repository paths written
into committed round records and reports. Depth is deep where the task domains
`input-handling` and `external-io` touch a boundary (TB-1, TB-2) and standard
for TB-3.

Domain consistency: every task that declares `input-handling`, `external-io` or
`data-persistence` (task0001 to task0005) has its files on a Boundary files line
below. task0005's `data-persistence` domain is covered by
`em-workflow/references/review-phase.md`, which sits on TB-2 and TB-3. task0006
declares none of the four domains.

## Trust Boundaries

### TB-1: Reviewed-tree paths and contents into the measurement script
Crossing: file names and file contents of the reviewed tree (authored by the
change under review) are read by `review-shards.py`, which the orchestrator runs
outside the Codex read-only sandbox, through `git` and direct reads.
Boundary files: em-workflow/scripts/review-shards.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A crafted changed path is read by `git` as an option or as pathspec magic, or a configured external diff or text-conversion driver runs a command while the script measures the diff (FR5) | TM-1 | Paths are revalidated with the Phase R0 step 3 rules (no leading `-`, no NUL / CR / LF, no absolute path or `..`, regular non-symlink file inside project_root) before any read; `git` is started with an argument list and no shell, with an end-of-options separator, literal pathspecs, and external diff, text conversion and color disabled | task0002 AC-6 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Denial of service | A changed path that is a FIFO, a device or a symlink swapped in after Phase R0 blocks or redirects the measurement read (FR5) | TM-2 | Every path is checked as a regular file without following symlinks before it is opened; any other kind ends the run with exit 2 and no output, and the orchestrator aborts the review phase (fail closed) | task0002 AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Denial of service | A change set built to produce many shards multiplies reviewer dispatches without bound (FR6, FR7) | TM-3 | Shards per perspective are capped at floor(24 / selected perspective count); the rest are excess shards, never dispatched and disclosed as unreviewed | task0002 AC-3 | VERIFICATION.md Performance / Security Verification, TM-3 |

### TB-2: Reviewer and LLM output into the completed / unreviewed decision
Crossing: Codex output, litellm reviewer results and reviewer findings (all
untrusted text shaped by the reviewed content) are classified by the reviewer
agents and the orchestrator into completed, skipped, failed, reviewed and
unreviewed.
Boundary files: em-workflow/agents/codex-reviewer.md, em-review/agents/codex-reviewer.md, em-workflow/references/review-protocol.md, em-review/references/review-protocol.md, em-workflow/references/review-phase.md, em-workflow/scripts/review-coverage.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | Reviewed content echoed into Codex output forges a timeout, or a timed-out run whose partial output holds valid JSON passes as a clean review (FR1, FR2) | TM-4 | The timeout decision uses the wrapper exit code 124 alone, checked before any JSON parse; output text never decides it, and partial findings are discarded | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Spoofing | A result's self-reported `source` or a near-match summary avoids or triggers the litellm empty-result rule (FR3) | TM-5 | The rule keys on the harness the orchestrator recorded at dispatch, a findings count of zero, and a byte-exact match on one of the two fixed summaries; the decision is made by `review-coverage.py`, and a script failure counts as failed | task0003 AC-1, task0004 AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 |
| Tampering | Reviewer text claims that files or shards were reviewed, hiding an unreviewed range (FR4, FR13, FR14) | TM-6 | Coverage is computed only from run_id, run status and the shard manifest of each pass; no reviewer-written text is an input to the coverage computation | task0003 AC-7, task0005 AC-4 | VERIFICATION.md Performance / Security Verification, TM-6 |
| Tampering | A spec rescue run, which saw only part of the diff, claims a missing implementation and drives an auto-fix or a rework (FR12) | TM-7 | A missing-implementation finding of a rescue run is recorded `unresolved` with a `resolution_reason` beginning `unverified`, and is excluded from auto-fix candidates and from the residual critical/high count on the evaluator path, the evaluator-failure path and Phase R4 re-review | task0005 AC-1 | VERIFICATION.md Performance / Security Verification, TM-7 |

### TB-3: Repository paths into committed records and reviewer commands
Crossing: paths of the reviewed tree flow into the committed round record, the
Phase R6 report, the batch final result, and the per-shard `diff_cmd_quoted`
that reviewers run verbatim.
Boundary files: em-workflow/references/review-phase.md, em-workflow/references/batch-mode.md, em-workflow/scripts/review-shards.py, em-workflow/scripts/review-coverage.py
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Repudiation | Excess shards and failed shards leave part of the change unreviewed with no trace a human reader sees, so the round reads as fully reviewed (FR7, FR13, FR15) | TM-8 | The round record stores `unreviewed_perspectives` and `partially_reviewed_perspectives` with the exact unreviewed file list and fixed reason tokens; Phase R6 and the batch final result render both from that record | task0005 AC-4, task0006 AC-3, task0006 AC-4 | VERIFICATION.md Performance / Security Verification, TM-8 |
| Information disclosure | An absolute path under a home directory reaches the committed round record or a script output (NFR3) | TM-9 | Script inputs and outputs and the coverage fields hold project-relative paths only; a script rejects an absolute input path with exit 2 | task0002 AC-5, task0003 AC-7, task0005 AC-5 | VERIFICATION.md Performance / Security Verification, TM-9 |
| Tampering | A shard's `diff_cmd_quoted` is assembled from paths re-joined from script output or from unvalidated text, so a reviewer runs an injected command (FR6) | TM-10 | Each shard's `diff_cmd_quoted` is built only from that shard's paths taken from the Phase R0 step 3 validated set, with the same quoting R0 uses; reviewers keep running it verbatim | task0004 AC-2 | VERIFICATION.md Performance / Security Verification, TM-10 |
