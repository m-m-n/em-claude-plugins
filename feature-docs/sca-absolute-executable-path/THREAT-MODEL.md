# Threat Model: sca-absolute-executable-path

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md / REQUIREMENTS.md (FR1-FR5, NFR1-NFR4, assumptions A1-A3) and
the planned change to `em-workflow/scripts/scan-dependencies.py` — executable
resolution for scan jobs, the scan job's argv[0], and the child process
environment. Tier: full. Both tasks declare `input-handling` and `external-io`,
so both boundaries below are analysed at deep depth.

Trust assumptions: the reviewed repository's content is attacker-influenceable
(a PR author can add any file, including an executable file, anywhere in it).
The reviewer's PATH value, and every absolute PATH entry in it, is the
reviewer's own configuration and is trusted; so is anything reached only
through absolute entries. Empty and relative PATH entries are the weak point:
they are interpreted against a working directory, and the working directories
involved (the runner's own cwd, a nested project directory, the project root)
are inside the reviewed tree.

Two crossings let reviewed-repository files become executed code with the
reviewer's privileges: the runner's own resolution and launch of the scanner
(TB-1) and the PATH the runner hands to the scanner child process (TB-2).
Both realistically apply, so the verdict is `threats-identified`.

Not analysed here by scope decision (SPEC A3): the git invocation and the
task-system entry-point invocations, which this feature leaves unchanged.

Domain / boundary consistency: task0001 and task0002 both modify
`em-workflow/scripts/scan-dependencies.py`, which appears in the Boundary
files of TB-1 (task0001) and TB-2 (task0002). Their new test modules are not
boundary code.

## Trust Boundaries

### TB-1: Reviewed-repository files -> scanner executable resolution and launch
Crossing: executable files placed in the reviewed repository by a PR author
cross into the runner's process-launch path when an empty or relative PATH
entry is interpreted against a working directory in the reviewed tree — at
resolution time against the runner's own working directory, and at launch time
when a relative argv[0] is re-interpreted against the job's working directory
(a nested project directory, an isolation directory, or the project root).
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A PR author adds `services/api/package.json`, `services/api/package-lock.json` and an executable `services/api/tools/npm` (or a `tools/npm` under the runner's cwd). With a relative entry such as `tools` in the reviewer's PATH, the scan resolves or launches the planted file instead of the reviewer's scanner: arbitrary code runs as the reviewer, and the planted binary can also print a forged clean scan result (FR1, FR3; SPEC AC3). | TM-1 | Resolution searches only the absolute entries of the search list (PATH, or the default search path when PATH is unset); empty and relative entries, and any implicit current-directory entry, are never searched; the result is an absolute path or none. Every scan job's argv[0] is that absolute path whatever the job's cwd. A scanner found only under relative or empty entries yields the existing `<ecosystem>_tool_not_found` reason with no plan and no fallback (FR1, FR2, FR3). | task0001 AC-1, AC-3, AC-5 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-3; also TS-1, TS-2, TS-4, TS-9) |

### TB-2: Runner -> scanner child process environment (PATH)
Crossing: the PATH value the runner passes to each scanner child process. A
scanner resolves its own helper programs through that PATH from the job's
working directory, which is inside the reviewed tree for go (the bound project
directory) and pip (the project root).
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | With empty or relative entries carried into the child PATH, a trusted scanner launched by absolute path resolves a helper from the reviewed tree — for example govulncheck resolving `go` from a planted `tools/go` under the bound project directory — so PR-author code runs as the reviewer (FR4). | TM-2 | The child PATH keeps only the caller PATH's absolute entries, unmodified and in their original order; when none remain, or the caller has no PATH, the child environment carries no PATH key. The other pass-through keys and the ecosystem pins are unchanged (FR4, NFR2). | task0002 AC-1, AC-2, AC-4 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-7; also TS-5, TS-6) |
