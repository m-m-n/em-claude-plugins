# Threat Model: sca-cargo-implicit-workspace-members

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (reduced tier — no REQUIREMENTS.md, no DESIGN.md) and the
feature goal in workflow.yaml. The feature changes how the SCA cargo scan unit
interprets one input, the root `Cargo.toml` of the project under scan, and
what that interpretation lets reach the scan result (findings, the cargo
undetermined count, and the summary text that reviewer agents read).

The root manifest is repository content that a contributor or a pull request
controls, so it crosses a trust boundary into the scanner (TB-1). The single
task declares the `input-handling` domain, which sets this boundary's depth to
deep. cargo-audit's JSON output also enters the same scanner, but this feature
does not change how it is read, so it is not modelled here.

Spoofing, Repudiation and Elevation of privilege do not realistically apply:
the scanner authenticates no party, records no actor-attributed action, and
runs with the invoking user's privileges before and after the change.

Post-decomposition check: task0001 declares `input-handling`; its
implementation file `em-workflow/scripts/scan-dependencies.py` is TB-1's
boundary file. Its other file, the test module, implements no boundary.

## Trust Boundaries

### TB-1: Root Cargo.toml of the scanned project → cargo direct-dependency resolution
Crossing: the text of the root `Cargo.toml` of the project under scan
(repository content outside the scanner's trust) is parsed and decides whether
each cargo-audit advisory becomes a direct finding, is dropped as transitive,
or is counted in the cargo undetermined note; the resulting summary is later
read by reviewer agents.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A root manifest whose `[workspace]` omits `members` or leaves it empty, while a root dependency entry carries `path` (directly, or inherited through `workspace = true`), makes the direct set look complete; an advisory for a crate declared only by an implicit member is then dropped as transitive and appears in no count, hiding a direct vulnerability from the scan result (FR1, FR2, FR4) | TM-1 | Such a manifest marks the direct set incomplete, so an unmatched advisory that is not determined-below-threshold is counted in the existing cargo undetermined note instead of being dropped; workspaces without a path-bearing root entry, and manifests without `[workspace]`, keep today's behavior (FR3) | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification TM-1 (TS-1, TS-2, TS-3, TS-4, TS-6) |
| Information disclosure | A `path` value is chosen by whoever controls the manifest and may be absolute or escape the project with `..`; a fix that resolves or opens it to read member manifests would read files outside the project under scan (NFR2) | TM-2 | Only the presence of the `path` key is used; its value is never resolved, opened or followed, and no new file-open path is added — the root manifest stays the only file read | task0001 AC-1, AC-6 | VERIFICATION.md Performance / Security Verification TM-2 (TS-1, TS-8) |
| Information disclosure | Manifest-derived text (a path value, a dependency key, the manifest path) placed into summary or skip_reason would expose local layout and carry manifest-author text into reviewer agents' prompts (NFR4) | TM-3 | The new incompleteness reaches the result only through the existing fixed token and count of the cargo undetermined note; no new reason text, token or field is introduced | task0001 AC-6 | VERIFICATION.md Performance / Security Verification TM-3 (TS-8) |
| Denial of service | An unexpected shape met by the new path check (a non-string or table `path` value on a root entry or on an inherited `[workspace.dependencies]` entry) raises out of the scan and aborts the SCA axis (NFR3) | TM-4 | The check never raises: it inspects only values already known to be tables, decides by key presence alone, and runs inside the existing never-raise contract of the direct-name resolution | task0001 AC-6 | VERIFICATION.md Performance / Security Verification TM-4 (TS-8) |
