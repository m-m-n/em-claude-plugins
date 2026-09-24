# Implementation Plan: repo-suite-pinned-test-drift

## Overview

Bring the repository suite (`python3 -m unittest discover -s tests`) back to exit code 0. The pinned tests follow the current em-workflow documents, manifests and `review-rules.yaml`. Specific-version pins become form / lower-bound / agreement checks. One phrase of the develop skill is reworded, and em-workflow goes to 0.2.4.

## Technology Stack

- **Language**: Python 3 (repository suite on the standard-library unit-test framework)
- **Key libraries**: standard library only (NFR1). This feature adds no dependency, so no license entry is needed (`project.license: none`).

## Layer Structure

| Layer | Contents | Written by (this feature) | Read by |
|---|---|---|---|
| Pinned artifacts | `em-workflow/skills/develop/SKILL.md`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `em-workflow/references/review-rules.yaml` | task0001 (the first three); `review-rules.yaml` is read-only | repository suite |
| Repository suite | `tests/test_*.py` modules | task0002 – task0005 | verify phase |

Dependency direction: tests read artifacts only. Artifacts never read tests. No modified test module gains an import of another test module.

## Shared Components

The three version rules are a shared semantic contract, not a shared module. Each test module implements them locally inside its own file (see D2).

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Version form rule | Decide whether a version value is well-formed | Accepts a value only if it is a string of exactly three dot-separated components, and each component is a non-empty run of ASCII decimal digits. Everything else is malformed and rejected: two or four components, a non-digit component, a prefix such as "v", a pre-release or build suffix, surrounding whitespace, the empty string, or a non-string value. A rejection is a test failure whose message names the offending value. It is never an uncaught error. | task0003, task0004 |
| Lower-bound comparison | Decide whether a well-formed version is at or above a recorded floor | Precondition: both the version and the floor pass the form rule. The three components are compared as integers, left to right. The version is accepted when it equals or exceeds the floor, so 0.2.10 is above 0.2.9. Strings are never compared. | task0003, task0004 |
| Registry agreement | Decide whether a plugin's manifest and its marketplace entry agree | Takes the version from `<plugin>/.claude-plugin/plugin.json` and the version of that plugin's entry in `.claude-plugin/marketplace.json`. Accepts only when both are well-formed and identical. Neither side is compared with a literal. | task0003 (FR6), task0004 (FR8) |
| develop SKILL.md (artifact) | Pinned text read by the suite | Postcondition of task0001: exactly one phrase changes. On the `--pr` item of 引数処理 (line 106), "AskUserQuestion を出さない" is replaced by a wording without the tool name. Line 4 (argument-hint) stays byte-identical, and so does Step C, including its AskUserQuestion at line 910 and the Non-packet gates reference at lines 918-919. Every other line is also unchanged. task0002's checks pass against the file both before and after task0001. | task0001 (writes), task0002 (reads) |
| em-workflow / marketplace manifests (artifact) | Version and identity data read by the suite | Postcondition of task0001: the em-workflow version is 0.2.4 in both files, and em-review stays 0.5.13 in both. Every other byte of both files is unchanged: keys, key order, whitespace and description. Every non-version digest pinned by the suite therefore stays valid. task0003 and task0004 checks pass at 0.2.3 (before task0001 merges) and at 0.2.4 (after). | task0001 (writes), task0003, task0004 (read) |

## Conventions

- **Matcher / loader separation**: every check this feature changes or creates is a matcher. It receives values that are already loaded (text, a parsed mapping, or a version value) and returns a pass or a fail. Reading the real repository file happens in a separate step. Live-state tests give the matcher loaded data. Negative-proof tests give it forged in-memory data.
- **Hermetic negative proofs (NFR3)**: a negative-proof test never writes, copies or patches a repository file. Forged data exists only in memory while the test runs. Each negative-proof test name states the forged condition and the expected verdict (accept or reject).
- **No current-version literals (NFR2)**: no changed version check compares a value with the current version of any plugin: 0.2.3 or 0.2.4 for em-workflow, and 0.5.13 for em-review. Floors are historical values recorded in the test module, and they are used only through the lower-bound comparison.
- **Names and docstrings state current semantics**: every test method name, constant, docstring and comment this feature touches says what the check now verifies (lower bound, form, agreement, or current definition). Wording that implies a literal bump target or a retired definition is removed. Test method names are kept unless the SPEC asks for a rename (FR6, FR7), so SPEC AC2's test list stays traceable.
- **Standard library only (NFR1)**: no modified module gets a third-party import.
- **Scope discipline**: if a test outside a task's file set fails, the task reports it as a plan deviation with the test id and the pinned value. The task does not edit that test.

## Cross-task Design Decisions

### D1: Tests follow the documents

The `--pr` addition (argument-hint line and Step C wording) and security's always-selected baseline are intended. This feature does not change the SKILL.md argument-hint line, the Step C wording, the `review-rules.yaml` selection rules, or the `plugin.json` description. The test expectations change instead. Affected: task0002, task0004 (FR5), task0005.

### D2: Specific-version pins become form + floor + agreement checks

Versions rise with every plugin change, and this feature bumps em-workflow too. A pinned current value can therefore never stay green. Each matcher applies only the columns its FR defines:

| Matcher | Form | Floor | Agreement | Identity fields exact |
|---|---|---|---|---|
| FR6 (task0003) | yes | 0.2.2 | em-workflow manifest vs entry | — |
| FR7 (task0003) | yes | 0.2.1 | — (each registry is checked on its own) | — |
| FR8 (task0004) | yes | each plugin's recorded floor | per plugin | — |
| FR9 (task0004) | yes | — | — | name, author, category, source |

Negative-proof cases for a matcher (SPEC AC3 / TS2) are the cases of its applicable columns:

- a forged higher version (99.0.0, identical in both registries where agreement applies) is accepted
- a version below the floor is rejected
- a malformed version is rejected
- disagreeing registries are rejected
- an altered identity field is rejected

A case whose column is "—" does not apply to that matcher. Each module implements the rules locally. No shared helper module is added, so the tasks stay inside disjoint file sets and run in parallel.

### D3: Exactly one task bumps, in the same commit as its plugin edit

`.claude/rules/core-plugin-version-bump.md` requires a version bump in the same change as any edit under a plugin directory. A commit guard rejects plugin-content commits that do not bump. task0001 is the only task that edits under `em-workflow/`, so it owns FR11 and commits the SKILL.md phrase change and both version edits together. task0002 – task0005 edit only `tests/`, touch no plugin directory, and do not bump.

### D4: Wrapped phrases are matched after normalizing both sides

Two pinned phrases wrap across source lines:

- the Non-packet gates reference in SKILL.md, lines 918-919 (FR3)
- "Layer 1 settles the value and Layer 2 cannot change it" in the `review-rules.yaml` header comment, which breaks after "cannot" and continues on a line that begins with a comment marker (FR10)

Each check normalizes the expected phrase and the source text the same way before looking for a substring. For SKILL.md this uses the module's existing whitespace-removal helper. For `review-rules.yaml` it removes line-leading comment markers and collapses whitespace, or uses the module's existing normalization if the module already has one. The negative proofs must show two things: a wrapped occurrence is accepted, and a phrase with a missing or altered word is still rejected. Affected: task0002, task0005.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A test outside every task's file set pins the literal 0.2.3 or the phrase "AskUserQuestion を出さない", and starts failing once task0001 merges | Medium | Medium | task0001 compares full-suite results before and after its change and reports any such test as a plan deviation. The verify full run (TS-1) catches the rest. The fix follows D1 / D2. |
| main advances and another feature bumps em-workflow while this feature is in flight | Low | Low | The D2 floors keep the task0003 / task0004 checks green at any higher version. At integration, FR11's value is aligned to a patch above main's version at that time. |
| task0001's rewording reaches Step C's AskUserQuestion (line 910) or the Step C text task0002 pins | Low | Medium | The SKILL.md artifact contract limits the change to line 106. A task0001 acceptance criterion requires the Step C wording test to keep passing. |
| The FR8 module records no separate per-plugin floor | Medium | Low | task0004 turns the value the removed "expected" key held into the floor, under a name that says it is a floor. That value is historical and is used only through the lower-bound comparison, so NFR2 holds. |
| The `plugin.json` description changes in a later feature, and both non-version digest pins fail together | Low | Low | Out of scope. This feature keeps the description unchanged (NFR4). |

## Open Questions

- [ ] Whether any test outside the planned file sets pins 0.2.3 or the replaced phrase is not known at plan time (first risk above).
