# Threat Model: hook-test-bytecode-suppression

## Verdict
no-trust-boundary

## Rationale
Inspected at the full tier:

- SPEC.md FR1–FR3, NFR1–NFR3 and assumptions A-1 to A-4.
- REQUIREMENTS.md 9.1.
- The single planned task, task0001 (domain `external-io`). It modifies
  `tests/test_destructive_guard_extglob_units.py` and
  `tests/test_destructive_guard_lexer_agreement.py`.
- `em-workflow/hooks/destructive-guard.py`, which those helpers load and
  which stays unchanged.

What moves:

- A test process the developer runs loads a file of the same repository,
  the hook, into itself and executes it. This happens today as well.
- The change only switches off one write the interpreter would otherwise
  make. That write puts the compiled form of the same file into
  `em-workflow/hooks/__pycache__/`, a directory of the same repository
  owned by the same user.
- The new tests write a probe module into a test-owned temporary directory
  and load it from there.

Every hand-off has the same user and the same privilege level on both
sides. Nothing crosses from a party of different trust:

- no external or user-supplied input
- no network call or external service
- no file read from outside the project
- no other process: the subprocess paths stay unchanged (SPEC A-2)
- no text placed into an LLM prompt
- no privilege change

The bytecode left in the plugin directory is a distribution-cleanliness
defect (SPEC.md Objectives), not a security threat. The change only removes
a write.

The `external-io` domain of task0001 covers that file-system side effect.
The write stays inside the same user's repository and temporary directory,
so it adds no trust boundary. That is why task0001's files appear in no
Boundary files line.
