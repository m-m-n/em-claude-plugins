# Threat Model: sca-go-govulncheck-real-output

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR10, NFR1-NFR5, Security Considerations),
REQUIREMENTS.md, and the Go path of `em-workflow/scripts/scan-dependencies.py`
that the feature changes (stream intake, stream reduction, Go normalizer, unit
and run aggregation). Tier: full. The single task (task0001) declares
`input-handling`, `external-io` and `api-contract`; `input-handling` and
`external-io` set deep depth on TB-1 and TB-2.

Three boundaries carry untrusted data: govulncheck stdout, the reviewed
project's go.mod, and the capture that moves from the implementer's machine
into the repository. Misreading the first two fails open (a real advisory
disappears and the run reads clean, which is the defect this feature fixes);
the third can publish machine-local data. The verdict holds because each of
these has at least one realistic STRIDE threat.

Not modeled, with reason: launching govulncheck, the scan's write
containment and the binding check are unchanged by this feature. The one-time
capture run executes a pinned govulncheck version (FR6) on the implementer's
machine; it is not part of the shipped scan path and nothing it produces
except the capture text (TB-3) enters the repository.

## Trust Boundaries

### TB-1: govulncheck stdout into the Go normalization
Crossing: stdout of an external process (govulncheck), carrying advisory text
from the Go vulnerability database, consumed by the scan and forwarded into
the review output that LLM reviewers read.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | Output that is not a completed govulncheck scan (the synthetic single-object payload, a stream without a config object, a stream holding non-object values) is accepted as a completed clean result (FR7, FR9) | TM-1 | Go stdout completes only as a stream of JSON objects holding a top-level object whose `config` value is an object; anything else reports `go_unparseable_output`; empty stdout keeps `go_empty_output` | task0001 AC-2 | VERIFICATION.md Performance / Security Verification TM-1 (TS6) |
| Tampering | Severity data the normalizer cannot interpret (no CVSS v3 vector, CVSS_V4 only, a malformed vector) is treated as below threshold, so a real advisory disappears and the run reads clean (FR1, FR2) | TM-2 | Severity band only from valid CVSS_V3 vectors, highest band wins; with no valid vector the advisory is undetermined and, when direct, is counted into the counts-only `go_severity_undetermined` summary note; never treated as below threshold | task0001 AC-3, AC-4 | VERIFICATION.md Performance / Security Verification TM-2 (TS1, TS3) |
| Tampering | Advisory-sourced text (summary, details, ids, module paths) reaches the summary or skip_reason that downstream LLM reviewers read (NFR3) | TM-3 | Summary notes and skip reasons carry only counts and fixed tokens; advisory strings reach findings only through the existing finding builder (`truncate_untrusted`) | task0001 AC-9 | VERIFICATION.md Performance / Security Verification TM-3 |

### TB-2: the reviewed project's go.mod into the directness resolver
Crossing: a file of the project under review (attacker-influenceable through
the change being reviewed), read by the scan at normalization time.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | go.mod text shaped so that a direct requirement reads as indirect or absent (a trailing comment that merely contains the word indirect, comments or other directives naming the module, quoted paths, block syntax), suppressing the finding (FR3, FR4) | TM-4 | Only require entries (single-line or block) count; an entry is indirect only for the canonical indirect marker comment; other directives and comments contribute nothing; quoted paths are unquoted; module paths compare by exact equality; `stdlib` and `toolchain` are always direct | task0001 AC-5 | VERIFICATION.md Performance / Security Verification TM-4 (TS2, TS4) |
| Tampering | A go.mod that cannot be opened, read or UTF-8 decoded, or that resolves outside the bound project directory, yields an empty direct set, reclassifies every advisory as transitive and reports clean (FR8, NFR4) | TM-5 | go.mod is read only through the existing project-relative confinement as a regular UTF-8 file of the bound directory; any failure makes the unit not completed with `go_direct_manifest_unreadable`; no fallback to an empty direct set | task0001 AC-7 | VERIFICATION.md Performance / Security Verification TM-5 (TS7) |

### TB-3: the capture moving from the implementer's machine into the repository
Crossing: govulncheck output generated on the implementer's machine, which
embeds absolute filesystem paths (home, temp, module-cache and toolchain
directories), committed into the repository.
Boundary files: tests/sca_govulncheck_capture.txt, tests/sca_govulncheck_capture_provenance.md
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | Machine-local absolute paths (user name, home or temp directory layout) are published through the committed capture or provenance note (FR6, NFR2) | TM-6 | Every machine-local absolute path is replaced by a placeholder; a structural test rejects `/home/` and `/tmp/` in either file and any capture string value that begins with `/` | task0001 AC-1 | VERIFICATION.md Performance / Security Verification TM-6 (TS9) |
