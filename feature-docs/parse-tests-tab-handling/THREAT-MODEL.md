# Threat Model: parse-tests-tab-handling

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR5, NFR1-NFR3, assumptions A1-A4) at the `reduced`
tier (no REQUIREMENTS.md, design step skipped), and the record check's
tests-block parser in `tests/test_tests_yaml_id_resolution.py` together with
how its output reaches the check's pass/fail decision and its resolver.
task0001 declares `input-handling`, so TB-1 is analysed at deep depth.

The record files under `test-docs/` are written by implementer agents and are
the input the record check exists to gate. This change only alters how the
parser treats lines that carry a tab in their indentation. FR2 removes the
`tests key has neither a value nor items` error for a tests block made only of
tab lines; an AC with no IDs and no errors passes the record check as an empty
list, so after FR2 the tab errors are the only thing that keeps such a record
failing. That is the recorded Tampering threat.

Categories considered at TB-1 without a row:
- Elevation of privilege: IDs read on the new paths (FR1, FR4) are returned to
  the unchanged resolver, which already gates every ID before any import; the
  change adds no other route from record text to an import.
- Denial of service: the change adds no unbounded iteration; each tab line is
  consumed once.
- Spoofing, Repudiation, Information disclosure: no identity, audit trail or
  secret is involved; error lines carry line numbers and fixed reasons only.

## Trust Boundaries

### TB-1: test record file -> record check parser
Crossing: the text of a `test-docs/**/*.tests.yaml` record, written by an
implementer agent (another process, LLM-generated content), read by the record
check in the test process, which decides from it whether the record passes and
which IDs it resolves.
Boundary files: tests/test_tests_yaml_id_resolution.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A record whose tests block holds only tab-indented lines (FR2, A4), or whose tab lines hide or cut items (FR1, FR3, FR4), is read as an empty or shorter list with no error, so the record check passes a record whose claimed tests were never verified (A1). | TM-1 | Every tab line inside a tests block, wherever it sits (before the first item, deeper than the item, at the item's depth), yields its own `tab in indentation` error for the AC; dropping the `neither a value nor items` error never leaves a tab-only tests block without an error, so the per-record test fails. | task0001 AC-2, AC-6 | VERIFICATION.md, Performance / Security Verification: TM-1 |
