# Threat Model: sca-directness-resolution

## Verdict
threats-identified

## Rationale

Inspected: SPEC.md and REQUIREMENTS.md of this feature at the `full` tier, and the inputs the changed code consumes — Cargo.toml, pyproject.toml and requirements files of the project under review (including every file a requirements include names), the pip-audit / cargo-audit payloads, the availability of tomllib, and the summary / skip_reason text the scan emits. Every task declares `input-handling`, so the manifest boundary (TB-1) is analysed at deep depth; `api-contract` (new summary notes and skip reasons) sets standard depth for TB-2.

The project under review is authored by whoever wrote the change being reviewed, so its manifests are attacker-influenceable, and the scan's summary is read by LLM review agents. Two boundaries therefore exist, and threats realistically apply to both.

Considered and not recorded:
- Scanner payloads (another process) are already consumed today; this feature only adds canonical-form comparison of the reported names and a count — no new sink for payload text, so no new threat at that boundary.
- Canonical-name matching merges only names that the ecosystems themselves treat as the same package, so it gives no new Spoofing path.
- Locating the scan unit's own manifest is unchanged; following requirements includes is the only new file-open path, and it is covered by TB-1.
- No privilege changes, authentication or persisted data are involved; Repudiation and Elevation of privilege do not realistically apply.

## Trust Boundaries

### TB-1: Project manifests into directness resolution
Crossing: Cargo.toml, pyproject.toml and requirements files of the project under review — content and include targets chosen by the change's author — are read and parsed by the SCA axis, which runs with the reviewer's filesystem and network access.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | A requirements include using `..`, an absolute path, or a symlink makes the scan open a file outside the project root (NFR2, FR4) | TM-1 | Each include target is taken relative to the including file and opened only when `_resolve_project_relative` confines it to the project root; a rejected target is never opened and marks the set incomplete | task0003 AC-2 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Information disclosure | A URL include makes the scanning host send a request to an author-chosen location (NFR2) | TM-2 | URL include targets are recognized and never fetched; they mark the set incomplete | task0003 AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Denial of service | Requirements files that include each other make the include walk recurse without end (FR4) | TM-3 | Each file is opened at most once per walk, keyed by its resolved location; a revisit ends that branch without error | task0003 AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Denial of service | Invalid TOML, unexpected value shapes, or unreadable manifests raise an exception that aborts the whole scan and hides every other unit's result (NFR3) | TM-4 | Every read, parse and shape failure inside the three resolvers maps to an incomplete set (or a fixed skip token), never to an exception | task0001 AC-5, task0002 AC-4, task0003 AC-3 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Tampering | A manifest that declares a vulnerable direct dependency in a form the resolver cannot resolve makes the advisory look transitive, so the SCA threshold silently drops it (FR5) | TM-5 | When the direct set is incomplete, an advisory not matched to a resolved name is counted as undetermined and reported in the summary note instead of defaulting to transitive | task0001 AC-4, task0002 AC-3, task0003 AC-5 | VERIFICATION.md Performance / Security Verification, TM-5 |

### TB-2: Scan summary into review-agent prompts
Crossing: the summary and skip_reason strings produced by the scan are interpolated into the context of LLM review agents; any manifest-derived text placed there comes from the change's author.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Package names, include paths or advisory text copied into the new notes or skip reasons carry instruction-shaped text into the reviewers' prompts (NFR4) | TM-6 | The new undetermined notes and the new skip reasons are composed only from fixed tokens and integer counts | task0001 AC-6, task0001 AC-7, task0002 AC-5, task0003 AC-6 | VERIFICATION.md Performance / Security Verification, TM-6 |
