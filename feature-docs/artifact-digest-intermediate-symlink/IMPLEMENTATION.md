# Implementation Plan: artifact-digest-intermediate-symlink

## Overview
`em-workflow/scripts/artifact-digest.py` changes so that it opens every
component of each path argument without following a symlink. A symlink
anywhere in the path then yields `not_a_regular_file` and no digest (SPEC
FR1–FR6). The script's docstring, the `OPEN_FLAGS` comment and the
"Calculation" section of `em-workflow/references/artifact-digest.md` are
updated to match (FR7). task0001 owns the behaviour and task0002 owns the
documentation text. The two tasks run in parallel.

## Technology Stack
- **Language**: Python 3, standard library only, no child process (NFR1).
- **Documents**: Markdown (`em-workflow/references/artifact-digest.md`) and the
  script's module docstring.
- **Tests**: the repository unittest suite under `tests/`, run with
  `python3 -m unittest discover -s tests`.
- **New dependencies**: none. With no new dependency, there is no license line
  to record (`project.license: none`).

## Layer Structure
| Layer | Artifact | Responsibility | Owner |
|---|---|---|---|
| Script behaviour | `em-workflow/scripts/artifact-digest.py`, except the two text regions in the next row | capability check, component walk, mapping failures to error tokens, hashing, output, exit code | task0001 |
| Script text | the module docstring and the comment attached to `OPEN_FLAGS`, both in the same file | describe the CLI contract below | task0002 |
| Reference contract | the "Calculation" section of `em-workflow/references/artifact-digest.md` | SSOT wording for the calculation, the error tokens and the exit codes | task0002 |
| Behaviour tests | new tests in `tests/test_artifact_digest_script.py` | turn task0001's Acceptance Criteria into tests | task0001 |
| Document tests | new tests in `tests/test_artifact_digest_docs.py` | turn task0002's Acceptance Criteria into tests | task0002 |

Dependency direction: the documentation describes the script's behaviour. No
runtime code reads the documentation.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| artifact-digest.py CLI contract | the behaviour task0001 implements and task0002 documents | see "CLI contract" below | task0001, task0002 |
| `OPEN_FLAGS` module constant | the flag set used to open the final element | Pre: none. Post: after both tasks merge, the name still exists and still means FR1's final-element set (read-only, no-follow, non-blocking, close-on-exec). task0001 owns the value and task0002 owns the attached comment (D2) | task0001, task0002 |

### CLI contract
- **Invocation**: unchanged. The script takes one or more path arguments.
  Relative arguments are walked from the current directory and absolute ones
  from `/` (FR1, A1).
- **Output**: same shape as before (NFR3). One array entry per argument,
  `{path, sha256, error}`, in argument order, printed on stdout. `path` is the
  argument exactly as given (FR4).
- **Error tokens**: the set `missing` / `not_a_regular_file` / `unreadable` is
  unchanged. Each token means what SPEC.md's "Error Codes" table says. One
  meaning widens: `not_a_regular_file` now also covers a path any of whose
  components is a symlink (FR2).
- **Exit codes**: 0 and 1 mean what they meant before. Exit 1 is returned
  whenever any entry carries an error token, and every other argument is
  still hashed. Exit 2 keeps its existing meaning and also covers a platform
  that lacks one of the capabilities the walk needs: descriptor-relative open,
  the no-follow open flag, or the directory-only open flag (FR6). In that case
  no argument is processed, stdout is empty, and stderr carries a message
  naming each missing capability.
- **Invariant**: no failure path produces a digest. Content reached through a
  symlink never puts a digest on stdout (FR2, FR5).

## Conventions
- **Each argument fails closed**: any failure while walking or reading an
  argument becomes that argument's error token, and processing moves on to the
  next argument. No failure path falls back to resolving the whole path (FR5,
  FR6).
- **Existing tests are not edited**: new tests are added as new test methods or
  classes. Existing test methods in `tests/test_artifact_digest_script.py` and
  `tests/test_artifact_digest_docs.py` stay as they are, and
  `tests/test_digest_contract_alignment.py` is not edited (NFR3).
- **Text regions in artifact-digest.py**: owned as set out in D1 and D2.
- **Plugin versions**: neither task edits a plugin version field (NFR4).
- Code comments, docstrings and reference text are written in English.

## Cross-task Design Decisions

### D1: Behaviour and documentation are split by text region
- **Decision**: task0001 changes artifact-digest.py's behaviour and leaves the
  module docstring and the comment attached to `OPEN_FLAGS` byte-identical.
  task0002 changes only those two regions of that file, plus
  `em-workflow/references/artifact-digest.md` and its own test file.
- **Rationale**: all documentation text (the docstring, the comment and the
  reference section) changes together in one worktree. An existing test that
  compares the docstring with the reference document therefore sees a
  consistent pair in both worktrees. The two tasks' edits to the shared file
  also do not overlap.
- **Affected tasks**: task0001, task0002.

### D2: `OPEN_FLAGS` keeps its name and role
- **Decision**: `OPEN_FLAGS` stays the module-level name of the final-element
  flag set from FR1. task0001 owns its value and task0002 owns its comment. If
  task0001 names a flag set for intermediate directories, that set gets its
  own name and its own comment, and task0001 writes both.
- **Rationale**: task0002's comment edit has to land on a constant that still
  exists, with the same role, after the merge.
- **Affected tasks**: task0001, task0002.

### D3: Each task's tests stay in its own test file
- **Decision**: behaviour tests go in `tests/test_artifact_digest_script.py`
  (task0001), and document assertions go in `tests/test_artifact_digest_docs.py`
  (task0002). Neither task edits the other task's test file.
- **Rationale**: no file overlap in tests, and every test passes inside its own
  task's worktree.
- **Affected tasks**: task0001, task0002.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Textual merge conflict in artifact-digest.py | Low | Low | region ownership (D1, D2); any remaining conflict is resolved by the parent-side adoption protocol |
| An existing documentation or alignment test compares the docstring with the reference text, so an edit to only one of them fails | Low | Medium | D1: task0002 changes both texts together and task0001 changes neither |
| Absolute arguments under a symlinked system prefix (`/proc/self/...`, a temp root under a symlinked `/var`) now yield `not_a_regular_file` | Medium | Low | intended fail-closed outcome (A1). The orchestrator passes worktree-relative paths. Tests that expect a digest for an absolute path build it from the fully resolved temp root |
| A platform without the FR6 capabilities can no longer compute digests (exit 2) | Low | Medium | intended (A5); the stderr message names the missing capability |

## Open Questions
- [ ] SPEC.md AC7 names `check-plugin-invariants.py` without a path. This plan
  does not resolve where it lives, because the planner reads only its dispatch
  inputs. task0002 and the verify phase need to find it in the repository and
  run it from there.
