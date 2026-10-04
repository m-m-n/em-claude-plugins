# Threat Model: sca-scanner-project-config-isolation

## Verdict
threats-identified

## Rationale

**What was inspected.** SPEC.md and REQUIREMENTS.md at the full tier. The design step was skipped, so there is no DESIGN.md. The feature changes two things:

- how axis-2 npm and cargo scans consume files that the PR author controls (REQUIREMENTS.md 2.2 separates the reviewer from the PR author);
- where the scan places temporary copies of those files.

**Depth.** task0001 declares `input-handling` and `external-io`, so TB-1 and TB-2 are analysed at deep depth. TB-3 is analysed at standard depth. task0001's production files appear in the Boundary files lines below; its test files are not boundary implementations. task0002 declares none of the four depth-adjusting domains: it changes documentation and adds guard tests only.

**Categories not recorded.** Spoofing, Repudiation and Elevation of privilege have no rows. The scanners run with the reviewer's own privileges both before and after this change, and no identity, credential or audit trail crosses any boundary below.

**Vector without a mitigation.** Configuration planted by another local account in an ancestor of the system temp directory was considered. No SPEC.md / REQUIREMENTS.md requirement addresses that vector, so no mitigation is recorded here. It is listed under IMPLEMENTATION.md Open Questions.

## Trust Boundaries

### TB-1: Reviewed project tree → scan inputs and scanner configuration discovery
Crossing: files under the reviewed project root that the PR author can write cross into two readers:

- the scan script's copy step;
- the npm and cargo-audit child processes, through configuration discovery from their working directory.

The files concerned are manifests, lockfiles, symlinks among them, `.npmrc` and `.cargo/audit.toml`.
Boundary files: em-workflow/scripts/scan-dependencies.py, em-workflow/references/vuln-scanners.yaml
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A project-level `.npmrc` sets proxy / TLS / CA / registry options that npm reads from its working directory. The audit traffic is redirected, and a forged clean advisory response is accepted as a completed scan (FR1, FR12). | TM-1 | npm runs with cwd set to a per-group isolation directory outside the reviewed tree. The directory contains only copies of `package.json` and the selected anchor, so no project `.npmrc` is on the cwd or ancestor path. | task0001 AC-1 | VERIFICATION.md TM-1 (TS-1) |
| Tampering | A project-level `.cargo/audit.toml` read from the working directory suppresses advisories through its ignore list, or swaps the advisory database through its url / path settings (FR2, FR12). | TM-2 | cargo-audit runs from a per-group isolation directory outside the reviewed tree, with `--file` pointing at the copied `Cargo.lock` and no `--url` / `--db`. No project `.cargo/audit.toml` is on the cwd or ancestor path (FR3). | task0001 AC-2 | VERIFICATION.md TM-2 (TS-3) |
| Tampering | A copy source is redirected or replaced (a symlink or a non-regular file) so that the copy step feeds the scanner data other than what the binding check accepted (FR5). | TM-3 | Each copy source is re-validated at copy time with the binding check's own rule. Only regular-file content is copied, and an allowed same-directory symlink is copied as a regular file holding its target's content. A failed validation is an isolation failure. | task0001 AC-3 | VERIFICATION.md TM-3 (TS-10) |
| Tampering | The isolation directory lands inside the reviewed tree. This happens when the temp parent resolves into the tree, through an environment-selected temp location, the process-wide override, or a symlink. The project's `.npmrc` / `.cargo/audit.toml` are then back on the scanner's ancestor path, and the scan writes into the tree (FR6, NFR2). | TM-4 | The temp parent's real path is checked before creation and the isolation directory's real path is checked after creation. Containment in the real project root, or equality with it, is an isolation failure, and the scanner is not launched. | task0001 AC-4 | VERIFICATION.md TM-4 (TS-5) |
| Tampering | The PR author induces an isolation failure, for example with an uncopyable input. The runner would then fall back to executing inside the tree, re-exposing project configuration, or report the unit as a clean completed scan (FR7). | TM-5 | An isolation failure makes the unit `not_completed` with `npm_isolation_failed` / `cargo_isolation_failed`. The scanner is never launched for that unit, and there is no fallback to in-tree execution. | task0001 AC-5 | VERIFICATION.md TM-5 (TS-5, TS-6) |
| Denial of service | One group's isolation failure, planted by the PR author, aborts the whole run and suppresses the findings of every other group (FR7). | TM-6 | Only the failing unit is affected. The other groups are still scanned, and completed groups' findings stay in the result alongside the failure reason. | task0001 AC-5 | VERIFICATION.md TM-6 (TS-6) |

### TB-2: Shared temporary area → isolation directory
Crossing: the isolation directory and the copies inside it live in the system temporary area, which other local accounts on the same host can also write to and list.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Another local account pre-creates a predictable directory, or swaps the copied inputs before the scanner reads them (FR8). | TM-7 | One new, uniquely named directory is created per scan group, with owner-only access from the moment of creation. | task0001 AC-3, AC-6 | VERIFICATION.md TM-7 (TS-4, TS-7) |
| Information disclosure | Another local account reads the copied manifests and lockfiles, including copies left behind after a tool failure, a timeout or a copy failure (FR8). | TM-8 | Access to the directory is owner-only. The directory is removed recursively after success, tool failure, timeout and a copy failure part-way through. | task0001 AC-6 | VERIFICATION.md TM-8 (TS-7) |

### TB-3: Scan result → review output
Crossing: `skip_reason` and summary text produced by the scan flow into the review round records and into the prompts of downstream review and rework agents.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | A failure reason that embeds filesystem paths carries two things into review output: the reviewer's local directory layout and directory names chosen by the PR author (NFR3). | TM-9 | `skip_reason` and summary carry only the fixed tokens. No path and no filesystem exception text reaches them. | task0001 AC-5 | VERIFICATION.md TM-9 (TS-6) |
