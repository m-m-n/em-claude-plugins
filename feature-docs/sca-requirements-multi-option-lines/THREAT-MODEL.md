# Threat Model: sca-requirements-multi-option-lines

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (tier `reduced`: no REQUIREMENTS.md, design step skipped) for the change to how `em-workflow/scripts/scan-dependencies.py` reads option lines of pip requirements files when deciding which packages are direct dependencies. The requirements files belong to the scanned project, so their content is attacker-influenceable. The resolver turns that content into file opens, and its result (direct-name set plus completeness flag) decides whether a high / critical advisory is reported or discarded as transitive. The scan summary is then read by the em-workflow orchestrator. task0001 declares `input-handling` and `external-io`, so TB-1 is analysed at deep depth; TB-2 carries only the summary and is analysed at standard depth.

Not re-analysed, because this feature does not change them: the pip-audit advisory input, and requirements lines that do not start with `-` (SPEC A5).

Numbering: SPEC.md cites TB-1 and TM-1 / TM-2 / TM-4 / TM-5 / TM-6 from the threat model under which pip directness resolution was first planned. This document reuses those numbers for the same threat classes so the citations resolve here. TM-3 covers the fail-closed handling of uninterpretable option lines, which this feature introduces.

## Trust Boundaries

### TB-1: Scanned project's requirements files → pip directness resolver
Crossing: text of requirements files from the scanned project (option lines, include targets, editable values) into the scanner process, which turns include targets into file opens and the parsed result into the direct-name set and completeness flag that decide whether advisories are reported.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | An include found at a non-leading position on an option line (a `..` path or an absolute path), or an abbreviated long-option token, makes the scanner open a file outside the project root and pull local file content into the scan (NFR3, FR1, FR6) | TM-1 | Every include target, whatever its token position, passes the existing project-root containment rule before any open; an outside-root target is not opened and marks the set incomplete; an abbreviated long-option token is never resolved to a file | task0001 AC-4, AC-6 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Information disclosure | A mid-line include naming a URL, or a URL editable value, makes the scanner send an outbound request to an attacker-chosen host (NFR3, FR1, FR5) | TM-2 | URL include targets are never fetched at any token position and mark the set incomplete; editable values are only passed to the existing name extraction, never fetched | task0001 AC-4, AC-5 | VERIFICATION.md Performance / Security Verification: TM-2 |
| Tampering | An option line the scanner cannot interpret (unsplittable because of an unclosed quote or trailing escape, an include with no value, an abbreviated or ambiguous `--requirement` / `--editable` prefix, an editable value yielding no name) is neither followed nor flagged, so complete stays true while declared names are missing and their high / critical advisories are discarded as transitive (FR3, FR4, FR5, FR6, FR8) | TM-3 | Fail closed: such a line contributes no names and marks the set incomplete, so advisories that match no declared name and are at or above the threshold or of unknown severity are counted under the existing `pip_directness_undetermined` note | task0001 AC-3, AC-5, AC-6 | VERIFICATION.md Performance / Security Verification: TM-3 |
| Denial of service | A crafted option line aborts or hangs the scan: the splitter's failure on an unclosed quote or trailing escape escapes the resolver as an exception, or mid-line includes that repeat a target or form a cycle between files are re-opened without bound (FR1, FR3, NFR2) | TM-4 | Split failures are contained inside the resolver (the line contributes nothing and marks the set incomplete); every include token, whatever its position, goes through the existing at-most-once open rule, so no exception escapes and resolution terminates | task0001 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification: TM-4 |
| Tampering | An include or editable placed after another option on the same line (after `-c`, after `--index-url`, a second `-r`, the `--requirement=` and attached `-r` forms, a non-leading `-e`) is skipped because only the leading option is examined; the set stays empty or partial with complete true, and the included packages' high / critical advisories are silently discarded as transitive. This is the reported defect (FR1, FR2, FR5, FR8) | TM-5 | The whole option line is tokenized and every include and editable token is acted on regardless of position; constraint tokens are consumed without opening their target or changing completeness | task0001 AC-1, AC-2, AC-5 | VERIFICATION.md Performance / Security Verification: TM-5 |

### TB-2: Scanner summary → downstream readers
Crossing: the scan summary leaves the scanner and is read by the em-workflow orchestrator, an LLM agent that takes it into its own context, and by humans; anything copied from a requirements file into it is attacker-authored text crossing into that reader.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | The new failure paths copy the splitter's error text, the raw option line, or a resolved path name (including an outside-root target) into the summary, exposing file-system layout and carrying attacker-authored text into the orchestrator's context (NFR4, FR8) | TM-6 | An incomplete set is reported only through the existing `pip_directness_undetermined` note, built from its fixed token and a count; no new note token is added | task0001 AC-7 | VERIFICATION.md Performance / Security Verification: TM-6 |
