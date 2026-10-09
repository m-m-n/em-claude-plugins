# Threat Model: tests-yaml-id-resolution-gaps

## Verdict
no-trust-boundary

## Rationale
Inspected SPEC.md and REQUIREMENTS.md (FR1-FR8, NFR1-NFR4) at tier `full`; no
DESIGN.md (design step skipped). The feature changes the record checker
`tests/test_tests_yaml_id_resolution.py`, the doc-contract test
`tests/test_tests_yaml_id_rules_docs.py`, `test/README.md` and one record,
`test-docs/tests-yaml-test-id-resolution/task0001.tests.yaml`. Its inputs are
the records under `test-docs/`, the modules under `tests/` that Loader
confirmation imports, and `test/README.md` — all repository-tracked files read
by the same test process (`python3 -m unittest discover -s tests`) that already
imports and runs every module under `tests/`. Loading a module named by a
record therefore grants nothing beyond what the suite already does, and no
network, external service, other process, LLM prompt or privilege change is
involved. No data crosses between parties of different trust.

Domain consistency: task0001, task0002 and task0003 declare `input-handling`
and task0004 declares `external-io`; their files appear in no Boundary files
line because the parsed records and the traversed `test-docs/` tree are
same-trust repository content. Those domains drive robustness review
(fail-closed reporting, no silently skipped record), not a boundary analysis.
