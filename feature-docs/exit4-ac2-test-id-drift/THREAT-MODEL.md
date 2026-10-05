# Threat Model: exit4-ac2-test-id-drift

## Verdict
no-trust-boundary

## Rationale

**What was inspected.** SPEC.md (FR1 to FR7, NFR1 to NFR4), the record
`test-docs/exit4-tip-argument/task0002.tests.yaml` and
`tests/test_exit4_tip_argument_version_bump.py`. The tier is reduced, so there
is no REQUIREMENTS.md and the design step was skipped.

**What the change does.** It edits one test record and one module docstring,
and adds one unittest module. The new module reads a git-tracked file in the
same repository. It then resolves the IDs listed in that file to modules under
the repository's own `tests/` directory. All of this happens inside the
developer's or CI's own test process.

**Why there is no trust boundary.** The record and the test code that reads it
are written and reviewed through the same repository workflow, so they share
one trust level. Nothing crosses from a party of different trust:

- no user input and no network
- no file from outside the project and no other process
- no LLM prompt interpolation
- no change of privilege

Resolving an ID imports the module it names. That grants nothing beyond what
anyone able to edit the record could already do by editing the test code.

**Why task0001's input-handling domain adds no boundary.** task0001 declares
the `input-handling` domain because the new module parses the record without a
YAML library. The risk there is correctness: silently losing an ID, or
reporting an ID as resolved when it is not. It is not a trust crossing.
task0001's Acceptance Criteria cover it with a negative proof, a non-vacuity
guard and per-AC ID counts. For the same reason, task0001's files appear on no
Boundary files line.

SPEC.md has no Security Considerations section.
