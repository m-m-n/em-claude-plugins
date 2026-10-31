# Implementation Plan: cd-prefix-canonical-path-only

## Overview
The cd prefix path check of the bash_guard.py hook accepts only canonical
absolute paths below an allowed area that lies inside the main worktree.
The orchestrator hands implementers a worktree_path that is already in that
form, so the hook no longer reproduces Bash's path resolution.

## Technology Stack
- **Language**: Python 3, standard library only (NFR1), for the hook and
  every test module.
- **Documents**: Markdown protocol and procedure documents under
  `em-workflow/references/`, `em-workflow/agents/` and
  `em-workflow/skills/`.
- **New dependencies**: none. (`project.license` is `none`; there is no
  license to record.)

## Layer Structure
| Layer | Members | Responsibility |
|-------|---------|----------------|
| Enforcement | `em-workflow/hooks/bash_guard.py` | Decides the cd prefix allow. Consumer of the canonical form |
| Normative statement | Path item of the Verbatim execution rule in `em-workflow/references/command-execution-protocol.md`, and the `path:` item of the hook's module docstring | The single description of the path condition |
| Producer | `em-workflow/references/implement-phase.md` (Step I.2.a launch) | Produces worktree_path in the canonical form |
| Consumer procedures | `em-workflow/agents/implementer.md`, `em-workflow/skills/worktree-task-workflow/SKILL.md` | Use worktree_path as supplied, as the cd target |
| Verification | `tests/` unittest modules, `test-docs/**/*.tests.yaml` records | Behavior tests, document tests, test records |

Allowed reference directions: consumer procedures and the producer cite the
normative statement by name. The normative statement describes the
enforcement. The enforcement depends on no document.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Canonical worktree path | The form of the directory an implementer cds into with `cd "{worktree_path}" && <approved string>` | Producer precondition: the task's worktree `$WT_ROOT/{T}` exists. Producer postcondition: worktree_path equals the strict realpath of `$WT_ROOT/{T}` (every component exists, links resolved), so it is absolute, has no empty, `.` or `..` component, has no link component, and is an existing directory. Enforcement: allows a cd prefix form only for a path in exactly that form that lies strictly below a resolved area inside the main worktree (SPEC FR1, FR5, FR6). Consumer: uses the value unchanged, with no rewrite, normalization or resolution and no runtime check | task0001 (enforcement), task0002 (producer, consumer procedures) |
| Path-condition statement | The normative wording of the cd prefix path condition | The path item of the Verbatim execution rule in `command-execution-protocol.md` states SPEC FR1, FR2, FR5 and FR6. The hook's module docstring `path:` item states the same conditions. Every other document refers to "the Verbatim execution rule of `references/command-execution-protocol.md`" and does not restate the conditions. The section heading `## Verbatim execution rule` stays as it is | task0001 (writes both statements), task0002 (cites the rule) |

## Conventions
- **Term**: every changed document uses "canonical absolute path" for a path
  that meets SPEC FR1 (a) to (d) (the SPEC glossary term 正規の絶対パス).
  "The area" is the allowed area that `worktree_area()` resolves (SPEC
  glossary).
- **Language**: code, docstrings, protocol text and tests are in English.
  Existing Japanese text keeps its language.
- **Document tests**: slice by heading, normalize whitespace, and assert the
  presence or absence of stable phrases. Never use a line number. Pair
  every absence assertion with a forged-text case that proves the matcher
  fires. This is the convention of the existing document-test modules.
- **Imports**: every new or changed test module checks that it imports only
  the standard library.
- **History stays as is**: the SPEC.md, task plans and other feature-docs of
  past features are not changed (REQUIREMENTS.md as-9). Only their
  `test-docs/**/*.tests.yaml` records change (FR10).

## Cross-task Design Decisions

### D1: One normative statement of the path condition
The path condition is stated in two places that must agree (the protocol's
path item and the hook docstring's `path:` item), and both belong to one
task. Every other document cites the Verbatim execution rule by name. The
procedure documents that task0002 changes cite the rule rather than copying
its conditions, so a change to the conditions touches only the two
statements owned by task0001.
Affected tasks: task0001, task0002.

### D2: The canonical form is produced by the orchestrator, enforced by the hook, and assumed by the implementer
The producer (implement-phase.md) is the only place that canonicalizes. The
hook refuses anything that is not already canonical and never normalizes.
The implementer neither checks nor rewrites the value (REQUIREMENTS.md
as-2). This lets the two tasks run in parallel against the Canonical
worktree path contract above. Neither task needs the other's result to pass
its own tests: the hook tests build canonical paths in their own fixtures,
and the producer tests are document tests.
Affected tasks: task0001, task0002.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing document tests pin wording in the changed documents: the protocol section must still contain "realpath", "double-quoted absolute path" and `.claude/worktrees/em-workflow/` after "below" or "under"; the hook's `cd prefix:` paragraph must keep its statement list; the payload block of implement-phase.md must keep its structure; the implementer cd-chain wording checks still apply | High | Medium | Each task plan names the constraining test modules in its Test Notes. The full suite is the final check of each task |
| Removing the tests of the removed checks drops path forms they exercised | Medium | Medium | The forms that are now refused are kept as silent cases (SPEC TS3, TS4). Only tests of mechanics that no longer exist are removed |
| `$WT_ROOT/{T}` differs from its strict realpath only when `.claude/worktrees/em-workflow` or an ancestor is a link that resolves inside the main worktree, which FR5 allows. In that layout, consumers that treat the worktree path as a plain string see the canonical value where they used to see `$WT_ROOT/{T}`. These consumers are the launch guard (project root found through the `/.claude/worktrees/em-workflow/` segment, journal path derived from the parent directory) and the stale-launched evidence input `--task-worktree` (`$WT_ROOT/{T}`, compared as a plain string with the Agent index entry) | Low | Low (the checks fail closed) | Out of scope of this SPEC. Listed under Open Questions |
| A past feature's test record loses every ID of an acceptance criterion | Medium | Low | The ID is reassigned to a remaining test that verifies the same criterion where one exists. Otherwise the criterion keeps an empty list. `tests/test_tests_yaml_id_resolution.py` must pass |

## Open Questions
- [ ] In a layout where `.claude/worktrees/em-workflow` (or an ancestor) is a
  link that resolves inside the main worktree, the canonical worktree_path
  lacks the `/.claude/worktrees/em-workflow/` segment. The launch guard
  then cannot derive the project root from it, and the stale-launched
  `--task-worktree` value (`$WT_ROOT/{T}`, pinned by
  `tests/test_stale_launched_missing_artifacts_doc_contract.py`) no longer
  equals the recorded worktree as a plain string. Whether those consumers
  should switch to the canonical value is outside this SPEC.
