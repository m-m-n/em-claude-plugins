# Implementation Plan: sca-directness-resolution

## Overview

Replace the SCA axis's pip and cargo direct-dependency resolution in `em-workflow/scripts/scan-dependencies.py` with tomllib-parsed manifests, include-following requirements resolution and canonical-name matching, and report advisories whose directness cannot be decided as a counts-only summary note instead of treating them as transitive. Three tasks run fully in parallel and all modify the same script; this document pins only what they share.

## Technology Stack

- **Language**: Python 3, standard library only (NFR1).
- **TOML parsing**: tomllib, reached only through the script's existing guarded import.
- **Tests**: unittest modules under `tests/`, run by `python3 -m unittest discover -s tests`.
- **New dependencies**: none. No license to record (`project.license: none`).

## Layer Structure

Inside `scan-dependencies.py`, three layers; dependencies point downward only.

1. **Aggregation** — `run_scan`: sums per-unit counters per ecosystem and composes the summary.
2. **Scan unit and classification** — the per-ecosystem scan-unit code (obtains the direct set, decides skips, invokes the scanner) and the classifiers `normalize_pip` / `normalize_cargo` (turn scanner payload entries into findings and per-unit counters).
3. **Direct-set resolution** — the three resolvers `_cargo_direct_dependency_names`, `_pip_pyproject_direct_names`, `_pip_requirements_direct_names`. Resolvers know nothing about scanners, severities or summaries; classifiers consume their result without knowing which resolver produced it.

Function ownership (who edits what; keeps merge conflicts local):

| Area | task0001 | task0002 | task0003 |
|------|----------|----------|----------|
| Cargo resolver | owns | | |
| `normalize_cargo` | owns | | |
| Cargo scan unit (FR6 skip, count forwarding) | owns | | |
| pyproject resolver | | owns | |
| pip scan unit, FR6 skip | | owns | |
| pip scan unit, count forwarding | | | owns |
| requirements resolver and include following | | | owns |
| `normalize_pip` | | | owns |
| `run_scan` undetermined aggregation (both ecosystems) and notes call | writes per D3 | | writes per D3 |
| Shared Components below | creates if absent | creates if absent | creates if absent |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `DirectNames` (new, module level) | Direct-dependency set of one scan unit: declared names plus completeness | Built from the declared names (as written in the manifest after `package =` / workspace rename resolution; never canonicalized) and a completeness flag. Post: immutable. For every read that existing callers perform on the former plain name collection (membership test, iteration, size, equality with a plain set of the same names) it behaves exactly like an immutable set of those names. Exposes a read-only `complete` (true = every declaration of the manifest was resolved). | task0001, task0002, task0003 |
| Legacy-value rule | How consumers treat a resolver result without completeness | A name collection that has no `complete` attribute is treated as complete. | task0001, task0003 |
| `_requirement_name` (new unless an equivalent already exists) | Package name of one PEP 508 requirement string | Pre: one requirement string with comments and pip options already removed. Post: the name as written when the string begins with a PEP 508 name followed by end of string, whitespace, an extras bracket, a version operator, a parenthesis, a marker separator, a direct-reference marker or a comma; "no name" when the leading token is a URL (contains a scheme separator) or a local path (starts with a dot, a slash or a tilde, contains a path separator, or ends with a wheel or source-archive suffix). Never raises. | task0002, task0003 |
| `canonical_pip_name` (existing, unchanged) | Canonical form: lower-case, every run of hyphen / underscore / dot collapsed to one hyphen | Idempotent; never raises on a string. No task modifies it. | task0001, task0003 |
| Per-unit count `directness_undetermined` | Carries one scan unit's undetermined count from its classifier to `run_scan` | Non-negative integer carried in the same per-unit result from which `run_scan` already reads the pip severity / unpinnable counters. Absent means 0. A skipped unit contributes 0. | task0001, task0003 |
| `_undetermined_directness_notes` (new) | Compose the FR5 notes | Pre: pip count and cargo count, both non-negative integers. Post: the pip note (when the pip count is above 0) followed by the cargo note (when the cargo count is above 0); each note is exactly the FR5 text with N replaced by the count, using `advisory` when N is 1 and `advisories` otherwise, including its leading half-width space; empty when both counts are 0; nothing else. | task0001, task0003 |

Every task listed for a component creates it when its worktree lacks it, exactly per the contract above. After any merge the script holds a single definition: parent-side adoption keeps the parent's definition and the merging task re-expresses its own change against it.

## Conventions

- **Output text (NFR4)**: summary notes and skip reasons carry only fixed tokens and integer counts — never a manifest path, a package or crate name, an include target or advisory text.
- **Failure mapping (NFR3)**: inside a resolver, every read, parse or unexpected-shape failure (missing file, unreadable file, invalid TOML, a scalar where a table or list is expected, a non-string name) makes the result incomplete; no exception leaves the scan. The only new skip reasons are `pip_toml_parser_unavailable` and `cargo_toml_parser_unavailable` (FR6).
- **TOML availability**: decided at call time from the module-level guarded tomllib binding, so a test that replaces that binding with None exercises the unavailable path.
- **Name comparison**: classifiers compare the canonical form of the reported name with the canonical form of each declared name; resolvers never canonicalize.
- **Resolver entry points** keep their current names, so a stand-in in another task's test can replace them by name.
- **Tests**: each task adds its own test module (named in its plan). Scanners are never executed; payloads come from stand-ins, following the way the existing scan-dependencies tests stub them. Fixture projects live in temporary directories created by the test. Existing npm and go tests pass without modification (NFR5). An existing pip or cargo test that encoded the old behavior and has to change is reported as a plan deviation.

## Cross-task Design Decisions

### D1: Completeness travels with the name set

- **Decision**: resolvers return `DirectNames`, which reads like the former plain name collection and adds `complete`.
- **Rationale**: resolvers and classifiers are implemented by different parallel tasks. With this shape a new resolver works with the old classifier (completeness ignored) and a new classifier works with an old resolver (legacy-value rule), so the tasks merge in any order without call-site changes.
- **Affected tasks**: task0001, task0002, task0003.

### D2: One classification rule, applied by both classifiers (FR1, FR5)

For each scanner-reported advisory, in this order:

1. The payload entry states directness itself (cargo `is_direct`) → that decides; the advisory is never undetermined.
2. The canonical reported name equals the canonical form of a declared name → direct; the existing threshold applies.
3. The set is complete → transitive (current behavior).
4. The set is incomplete → when the severity is known and below the threshold, the advisory is dropped and not counted; otherwise it is undetermined: no finding, not transitive, counted exactly once in the unit's `directness_undetermined`, and not counted in any other counter (for example the pip unknown-severity counter).

`normalize_cargo` (task0001) and `normalize_pip` (task0003) each apply this rule. It never changes `skipped` or `skip_reason`.

- **Affected tasks**: task0001, task0003.

### D3: Notes position and order

`run_scan` sums `directness_undetermined` over the pip units and over the cargo units, calls `_undetermined_directness_notes` once with both sums, and appends its output after every pre-existing summary note (pip severity, unpinnable, go). The pip note therefore precedes the cargo note. task0001 and task0003 both write this aggregation and call identically; whichever merges second keeps the parent's version.

- **Affected tasks**: task0001, task0003.

### D4: FR6 skip placement

The tomllib availability check sits in the scan-unit code immediately before the scanner would be invoked, after every existing check that yields `pip_direct_manifest_not_found` or `pip_lockfile_unconvertible`. It applies only when the unit's direct names would come from pyproject.toml (pip, including a lockfile unit whose direct manifest is pyproject.toml) or from Cargo.toml (cargo). Requirements-file units never take it.

- **Affected tasks**: task0001, task0002.

### D5: Seam coverage on the pip path

The pyproject resolver (task0002) and the pip classifier (task0003) live in different tasks. task0002 tests the resolver's names and completeness verdicts; task0003 tests the classifier with an incomplete `DirectNames` supplied by a stand-in for the pyproject resolver. The integrated suite covers the composition (VERIFICATION.md TS-8, TS-20).

- **Affected tasks**: task0002, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| All three tasks edit `scan-dependencies.py`, producing merge conflicts | High | Medium | Function ownership table; shared contracts pinned above; parent-side adoption |
| An existing pip/cargo test asserts an exact summary that now gains an undetermined note | Medium | Low | Reported as a plan deviation; the test is updated, the behavior is not |
| A requirement token that is a local path or archive is read as a package name, leaving the set wrongly complete | Medium | High | `_requirement_name` path / URL / archive rule; TS-13 |
| Editable and path lines now make sets incomplete, so real projects see more undetermined notes | Medium | Low | Intended by FR5: counts only, no finding, `skipped` stays false |

## Open Questions

None.
