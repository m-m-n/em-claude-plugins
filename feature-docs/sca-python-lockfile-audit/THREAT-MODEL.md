# Threat Model: sca-python-lockfile-audit

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR12, NFR1-NFR7, Security Considerations) and
REQUIREMENTS.md, tier `full`, one implementation task (task0001) declaring
`input-handling`, `external-io` and `api-contract`. The feature makes the pip
axis of `scan` read two files authored by the change under review — the
selected poetry.lock / Pipfile.lock and its direct-dependency declaration file
(pyproject.toml / Pipfile) — turn the lockfile's pins into a requirements file
in the shared system temporary directory, and hand that file to pip-audit.
Both crossings carry attacker-influenceable data (the author of the reviewed
change controls the lockfile and the declaration file), so `input-handling`
(TB-1) and `external-io` (TB-2) set deep depth.

Considered and not recorded:
- The changed-file paths themselves: they come from the orchestrator's own
  change listing, and every file opened from them is already confined to the
  project root by TM-3, so they form no separate boundary.
- pip-audit's JSON output: an existing boundary whose handling (advisory-text
  truncation, counts-only summary notes) this feature leaves unchanged.
- A lockfile listing many versions of one name multiplies pip-audit runs
  (FR4): each run is bounded by the existing per-run timeout and its outcome
  stays visible in the result, so no realistic denial of service hides a
  result.

Post-decomposition check: task0001 declares `input-handling` and
`external-io`; its file `em-workflow/scripts/scan-dependencies.py` is the
boundary file of both TB-1 and TB-2.

## Trust Boundaries

### TB-1: Reviewed-project lockfile and declaration file -> scanner
Crossing: content of the selected poetry.lock / Pipfile.lock and of its sibling pyproject.toml / Pipfile, authored by the change under review, read from the project tree by the scan process.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A crafted entry name or version (an option-shaped name such as `-r evil`, a version carrying a line break, `;` or `#`) injects requirements-file options, markers or extra lines into the temporary requirements file and changes what pip-audit reads (FR11, FR6) | TM-1 | Only entries whose name fully matches the FR11 name pattern and whose version passes the FR11 version rule are written, each as exactly one `name==version` line; every other entry is excluded and counted (FR6) | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-1 (TS6) |
| Tampering | A lockfile crafted to be unparseable, structureless, or to mark every vulnerable pin as non-registry, so the pip axis reports a clean, non-skipped result — the defect class this feature removes (FR5, FR6) | TM-2 | A lockfile target never falls back to manifest or directory audit: zero convertible pins yield `skipped: true` with `pip_lockfile_unconvertible` and no pip-audit launch; partial exclusion yields the `pip_lockfile_entries_unpinnable` count note in the summary | task0001 AC-5, AC-6 | VERIFICATION.md Performance / Security Verification, TM-2 (TS4, TS6) |
| Information disclosure | A lockfile or declaration file committed as a symlink resolving outside the project root makes the scanner read a file outside the reviewed tree and forward names / versions taken from it to pip-audit (FR8) | TM-3 | The lockfile and the declaration file are opened only when their resolved real path lies inside the project root; otherwise the lockfile is unconvertible (`pip_lockfile_unconvertible`) and the declaration file is not found (`pip_direct_manifest_not_found`) | task0001 AC-5, AC-7 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Denial of service | Malformed content (wrong value types, non-UTF-8 bytes, nesting beyond the parser's limit) raises out of the scan and aborts every ecosystem's result instead of a pip-only skip (FR5, FR8, FR12) | TM-4 | Every read, parse or shape failure of either file maps to its fixed skip reason or to an entry exclusion; no exception leaves the scan; completed ecosystems' findings are kept | task0001 AC-5, AC-7 | VERIFICATION.md Performance / Security Verification, TM-4 (TS4, TS5, TS11) |

### TB-2: Scanner -> pip-audit child process through the shared temporary directory
Crossing: pins taken from the untrusted lockfile, handed to an external process through a file in the system temporary directory, which other local users can also write to.
Boundary files: em-workflow/scripts/scan-dependencies.py
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | If pip-audit resolved the pins through pip, it would download and build packages named by the untrusted lockfile and run their build code on the reviewer's machine (FR3) | TM-5 | Every lockfile job carries `--no-deps` and `--disable-pip`; requirement lines are exact pins only; the registry pip entry and the child-environment pins are unchanged (NFR6) | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-5 (TS3) |
| Tampering | Another local user replaces or edits the temporary requirements file between its write and pip-audit's read (a predictable name or a permissive mode in a shared directory) (NFR1) | TM-6 | Each file is created exclusively under a unique, unpredictable name with owner-only access, outside the project root, and is removed on every exit path | task0001 AC-9 | VERIFICATION.md Performance / Security Verification, TM-6 (TS9) |
