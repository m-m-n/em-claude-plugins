# Threat Model: sca-per-project-scan-binding

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md (tier: full; design step skipped), the
`scan` path of em-workflow/scripts/scan-dependencies.py (run_scan,
build_scan_job, build_scan_jobs, the child-environment pins) and
em-workflow/references/vuln-scanners.yaml. The feature's inputs are the
changed-file list and the reviewed project tree — both authored by whoever
wrote the reviewed change, which for em-review can be a third-party pull
request — plus scanner child processes that now start inside nested project
directories, and the skip_reason / summary text that Phase R3a hands to an LLM
evaluator. Depth: task0002 declares input-handling and external-io and task0001
declares external-io, so TB-1 and TB-2 are analysed deep; TB-3 is standard.

Considered and not recorded: denial of service through many project groups
(every launch needs a manifest and an anchor present in the reviewed tree, so
the launch count is bounded by the change the review already processes);
project-level tool configuration inside a bound directory (configuration in the
reviewed tree was already read at the root before this feature, and the
existing registry / userconfig pins apply unchanged); pip paths (pip's
validation and confinement are unchanged, FR10). task0003 changes protocol
wording only and declares none of the four depth domains.

## Trust Boundaries

### TB-1: Reviewed change → scan path resolution
Crossing: changed-file paths and the reviewed project tree (directories, symlinks, manifests, lockfiles), authored by the reviewed change, into scan-dependencies.py's grouping, binding and working-directory selection
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | An absolute or `..`-escaping changed path, or a project directory / anchor / manifest symlinked into another directory, makes a scanner run against — and report on — a dependency tree outside the reviewed project (FR4, FR5, AC-7) | TM-1 | Real-path containment of every changed file, the project directory, the anchor and the required manifest; anchor and manifest must be regular files resolving inside the same project directory; any failure yields `<ecosystem>_project_unbindable` with no launch and no fallback to the root or an ancestor; build_scan_job rejects an absolute or escaping npm / cargo / go target (FR4, FR5, FR6) | task0002 AC-4, AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-5) |
| Tampering | A vulnerable dependency added to a nested project, or to a second project of the same ecosystem, is audited against another project's dependency set (or not at all) while the run reports completion, so it passes the SCA axis unnoticed (FR1, FR3, FR8, AC-15) | TM-2 | One scan unit per verified project group, with the scanner's working directory bound to that group and the finding label taken from the same group; any group that does not complete makes the result skipped with the aggregated reason while completed groups keep their findings (FR1, FR2, FR3, FR6, FR8) | task0002 AC-2, AC-5 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-1, TS-2, TS-4) |

### TB-2: scan-dependencies.py → scanner child process
Crossing: a third-party scanner process launched with a reviewed project directory as its working directory; it can discover configuration and workspace files above that directory (possibly above the project root) and can write into the reviewed tree
Boundary files: em-workflow/scripts/scan-dependencies.py, em-workflow/references/vuln-scanners.yaml
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | npm or go walks up from the bound directory to an ancestor workspace (an npm workspace root, a go.work file — including one above the project root) and audits that workspace instead of the bound project (FR11) | TM-3 | The npm argument vector carries --workspaces=false; the go child environment pins GOWORK=off over any caller value (FR11) | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-7) |
| Tampering | The scanner rewrites the reviewed tree: cargo-audit generates a missing Cargo.lock, go updates go.mod / go.sum while resolving modules (NFR1, AC-5) | TM-4 | A scanner is launched only when the project's anchor lockfile already exists (FR4); the go child environment pins GOFLAGS=-mod=readonly (FR11) | task0001 AC-2; task0002 AC-3 | VERIFICATION.md Performance / Security Verification, TM-4 (TS-7, TS-10) |

### TB-3: Scan result → Phase R3a LLM evaluator input
Crossing: the axis-2 result's skip_reason and summary, built from a run over directory and file names chosen by the reviewed change, passed by Phase R3a into an LLM evaluator's input
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A crafted directory or file name copied into skip_reason or into the summary's not-completed list reaches the evaluator as instruction-shaped text and steers its judgment (FR7, NFR3) | TM-5 | skip_reason and the summary's reason list are composed only from fixed reason tokens (`<ecosystem>_project_unbindable`, `<ecosystem>_tool_not_found` and the other existing tokens), de-duplicated and sorted, never from path text (FR7, NFR3) | task0002 AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 (TS-3, TS-4) |
