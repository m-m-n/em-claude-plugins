# Threat Model: tests-yaml-test-id-resolution

## Verdict
threats-identified

## Rationale
Inspected SPEC.md and REQUIREMENTS.md (FR1 to FR13, NFR1 to NFR4) at the full tier; the design step was skipped, so there is no DESIGN.md. Two trust boundaries exist. TB-1: `tests` strings from every record, written by implementer agents across many features and therefore influenceable through task text, become imports, attribute lookups and loader calls inside the test process (task0001, domain input-handling, so deep). TB-2: this feature's agents rewrite records owned by other features, and verify, rework and retrospect consume those records as the SSOT for acceptance-criterion coverage (task0002, task0003, task0004, domain data-persistence, so deep). task0005 (config-infra) adds rule text to `em-workflow/agents/implementer.md` and `test/README.md` plus a test that reads both as plain text; it adds no input path, no import or execution of content and no privilege change, so it crosses no boundary. No Spoofing or Denial of service row exists: the records carry no identity claim, and they are repository files read once per run.

## Trust Boundaries

### TB-1: Record test IDs into the test process's import and loader machinery
Crossing: `acceptance_tests.*.tests` strings from every record (agent-written data) into module imports, attribute lookups and unittest loader calls inside the `python3 -m unittest discover -s tests` process
Boundary files: `tests/test_tests_yaml_id_resolution.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An ID naming a module outside the test package, such as a standard-library module with import-time side effects, makes the import machinery and the loader run that module's code during every ordinary test run (FR1, FR6) | TM-1 | The SC-1 syntax gate (dot-separated identifiers, first segment `tests`) runs before any import or loader call; an ID that fails it is reported and never imported | task0001 AC-4 | VERIFICATION.md Performance / Security Verification: TM-1 |
| Elevation of privilege | The standard loader calls a resolved callable that is not a test case class, such as a module-level function, and running the loaded suite would execute test bodies, so a crafted ID executes code (FR6) | TM-2 | The SC-1 structural check (module, class derived from the test-case base class, or method defined on such a class outside the base class) gates the loader confirmation; the check calls nothing it resolves and walks the returned suite without running it | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-2 |
| Tampering | Putting the repository root or a fixture root on the module search path for resolution and leaving it there, or leaving fixture `tests` modules cached, changes which modules every later test in the same process imports (FR6) | TM-3 | The module search path is restored to its exact prior value after every check, including on failure; fixture `tests` modules are discarded from the module cache after fixture checks | task0001 AC-6 | VERIFICATION.md Performance / Security Verification: TM-3 |

### TB-2: Unattended rewrite of other features' records
Crossing: this feature's implementer agents into records owned by other features' completed workflows, which verify, rework and retrospect read as the SSOT for acceptance-criterion coverage
Boundary files: `test-docs/**/*.tests.yaml`, `test-docs/tests-yaml-test-id-resolution/id-mapping-range1.md`, `test-docs/tests-yaml-test-id-resolution/id-mapping-range2.md`, `test-docs/tests-yaml-test-id-resolution/id-mapping-range3.md`
Depth: deep (data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Repudiation | An unresolvable ID is deleted or swapped to make the record check pass, and the loss or change of that AC's coverage claim leaves no trace (FR3, AC-3) | TM-4 | Every removed old-ID occurrence gets an SC-3 row with a basis category and evidence (a commit id for renames); the row count equals the diff's removed-occurrence count | task0002 AC-3, task0003 AC-3, task0004 AC-3 | VERIFICATION.md Performance / Security Verification: TM-4 |
| Tampering | The rewrite changes the fields that attest the historical red evidence: `red_confirmed`, `baseline_failures`, `final_failures`, or the existing `red_reason` text (FR2, FR4, AC-4, NFR3) | TM-5 | Changes are limited to `tests` elements plus SC-5 appends, whose parsed pre-existing value stays the exact prefix of the new value; no key is added | task0002 AC-4, task0003 AC-4, task0004 AC-4 | VERIFICATION.md Performance / Security Verification: TM-5 |
