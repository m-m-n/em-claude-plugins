# Threat Model: sca-requirements-option-value-consumption

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (tier `reduced`: no REQUIREMENTS.md, design step skipped),
the requirements-file option-line reader of
`em-workflow/scripts/scan-dependencies.py` (`_requirements_option_items`, the
abbreviation check, `_pip_requirements_direct_names`) and its test module.

The feature's only input is the text of requirements files in the repository
under review — the reviewed manifest and every file it includes — which the
author of the reviewed change controls. The reader's result decides which
include files are opened and whether a pip advisory is reported as a direct
finding, counted as undetermined, or dropped as transitive. A misread
therefore silently weakens the dependency-security review, so the reader sits
on a trust boundary (TB-1). Depth is `deep` because task0001 declares
`input-handling` and `external-io`.

No other boundary is touched: the feature adds no dependency (standard library
only, NFR1), launches no process, makes no network access, and leaves the
include-confinement path and the pip-audit invocation unchanged (FR6).
Domain consistency: task0001's boundary-implementing file
`em-workflow/scripts/scan-dependencies.py` is listed under TB-1;
`tests/test_scan_dependencies_pip_directness.py` is test-only and implements
no boundary.

## Trust Boundaries

### TB-1: Requirements-file option lines into the option-line reader
Crossing: text of requirements files authored by the change under review
(attacker-influenceable) into the scanner's option-line reader, whose output
selects the files to open and the direct-name set that classifies advisories.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A value-only option in separated form followed by `-c -r X` (e.g. `--trusted-host -c -r deps.txt`) makes the reader take `-c` as a constraint that swallows `-r`; X is never read while the set stays complete, so X's high / critical advisories are silently dropped as transitive (FR1, FR2, FR4) | TM-1 | The separated form of every value-only option consumes the next token, whatever it looks like, as its value and discards it — at top level, in included files and across continuation lines | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, item TM-1 (TS-1, TS-2, TS-11) |
| Tampering | An abbreviation of a value-taking long option (e.g. `--trusted -c -r X`), which pip expands and lets consume the next token, is read as an ignored unknown option, so the same swallowing yields a complete set without X (FR5) | TM-2 | A proper prefix of any value-taking long name (interpreted or value-only, unique or ambiguous) makes the set incomplete without consuming the next token, so the affected advisories are counted in the existing undetermined note | task0001 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, item TM-2 (TS-7, TS-8, TS-9) |
| Tampering | A value token shaped like an editable or an include (`-f "-enamed-pkg"`, `--find-links "-rdeps.txt"`, or an abbreviation's `=` value such as `--trusted=-rdeps.txt`) is interpreted, adding a direct name pip never installs or opening a file pip never reads (FR4, NFR2) | TM-3 | Values of value-only options and of abbreviations are never interpreted: no file is opened, no URL is fetched, no name is added | task0001 AC-2, AC-4 | VERIFICATION.md Performance / Security Verification, item TM-3 (TS-3, TS-4, TS-5, TS-8) |
| Information disclosure | Option values can carry credentials or private hosts (an index URL with an embedded user and token, a trusted host); the new consumption and undetermined paths could echo them into the scan summary or findings, which are written into review records (NFR3) | TM-4 | Consumed and undetermined values are discarded; incompleteness is reported only through the existing fixed-wording pip directness note, with no token text | task0001 AC-7 | VERIFICATION.md Performance / Security Verification, item TM-4 (TS-14) |
