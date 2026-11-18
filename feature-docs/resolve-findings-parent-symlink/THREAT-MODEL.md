# Threat Model: resolve-findings-parent-symlink

## Verdict
threats-identified

## Rationale
Inspected: the `--feature-dir` argument of `em-workflow/scripts/resolve-verified-findings.py`, the
file-system entries the script resolves from it (the feature directory's final element, its
`reviews` entry, the round records inside `reviews`), the moment those entries are checked versus
the moment they are read or replaced, and what the script prints. Tier: full. task0001 declares
`input-handling` and `external-io`, so every boundary touching the script is analysed at deep
depth.

The verdict holds because a party that can place entries in the repository (or change them while
the script runs) controls whether those entries are directories, symbolic links or special files,
and the script replaces a review round record based on them; a redirected replacement rewrites
another feature's deferred findings and lets that feature pass the merge preflight.

Considered and not recorded as threats:
- Symbolic links in ancestors of the feature directory are outside the analysed boundary by
  decision (FR5); they do not let one feature's run choose another feature's `reviews` entry.
- `workflow.yaml` and the mapping file are only read, never written (SPEC Assumptions). A link
  there can only feed inputs that the same party could already write into the feature's own
  files, so it adds no capability.
- The eligibility rules, the YAML safe-load discipline and the mapping-file validation are
  unchanged by this feature and stay governed by the earlier feature's own analysis.

## Trust Boundaries

### TB-1: repository file-system entries to the round-record replacement
Crossing: directory entries under `feature-docs/` whose kind (directory, symbolic link, FIFO,
regular file) is set by any party that can place files in the repository or change them during a
run, consumed by the script that the orchestrator runs to read and replace the latest review round
record.
Boundary files: em-workflow/scripts/resolve-verified-findings.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | `reviews` is a symbolic link to another feature's `reviews` (or to a directory outside the repository, or dangling), so the replacement lands in another feature's round record and its deferred findings become `fixed` (FR1) | TM-1 | `reviews` is opened relative to the opened feature-directory handle, as a directory, without following a link; a link is rejected as `invalid-round-record` before anything is written | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Tampering | The final element of `--feature-dir` is a symbolic link to another feature directory, including when the argument ends in one or more `/` so that a plain no-follow open would still traverse the link (FR2, FR7) | TM-2 | Trailing separators are removed from the argument, then the final element is opened as a directory without following a link; any failure is `invalid-workflow`, raised before `workflow.yaml` is read | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Tampering | After the script has checked `reviews`, the path entry `reviews` is swapped for a link to another feature's `reviews`, so any later path-based operation (listing, mode lookup, temporary file creation, rename, cleanup) follows the swap (FR3) | TM-3 | Every operation after `reviews` is opened is made relative to the held `reviews` handle: listing, record check and read, mode lookup, exclusive no-follow creation of the temporary file, rename with both names relative to that handle, and removal of the temporary file on failure | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Tampering | Between the record pre-check and its open, the round record is swapped for a link to another feature's record, so the read (and the mode taken for the rewrite) follow the link (FR8) | TM-4 | The record is opened read-only without following a link relative to the `reviews` handle; the opened handle must be a regular file; the content and the mode are taken from that handle, with the existing size bound | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Denial of service | The round record is a FIFO; opening it waits for a writer that never comes and stalls the run (FR8, SPEC AC10) | TM-5 | The no-follow status pre-check rejects every round record that is not a regular file as `invalid-round-record` before any open is attempted | task0001 AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 |

### TB-2: script output to the orchestrator
Crossing: the script's stdout and stderr, read and recorded by the orchestrator (an LLM-driven
agent); the new rejection paths deal with link targets and locations chosen by the party in TB-1,
some outside the repository.
Boundary files: em-workflow/scripts/resolve-verified-findings.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | A new rejection path writes a path, a link target or operating-system error text (which can name locations outside the repository) to the output instead of the error code alone (NFR4) | TM-6 | Every new failure is mapped to an existing error code; stdout stays empty on failure and stderr carries exactly one line holding only the code | task0001 AC-7 | VERIFICATION.md Performance / Security Verification, TM-6 |
