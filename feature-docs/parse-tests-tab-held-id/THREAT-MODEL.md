# Threat Model: parse-tests-tab-held-id

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (tier `reduced`, so there is no REQUIREMENTS.md; the
design step is skipped) and the record check
`tests/test_tests_yaml_id_resolution.py`, whose tests-block parser decides
which test IDs of a record reach resolution. The records it reads
(`test-docs/{feature}/{task}.tests.yaml`) are written by implementer agents,
and the record check is the gate that judges what those records claim, so
record text crosses a trust boundary into the check (TB-1). The only task
declares `input-handling`, which sets TB-1 to deep analysis.

The defect this feature fixes is a realistic integrity threat at that
boundary: record content can make a readable ID silently drop out of
resolution (TM-1). This feature does not change the resolution stage (the
syntax gate before any import, resolution without execution), nor the rule
that every tab line is reported, so no other STRIDE category applies.

## Trust Boundaries

### TB-1: Implementer-written test record → record check
Crossing: the text of a test record written by an implementer agent crosses
into the record check, which decides from it which test IDs reach resolution
and which errors the record's single failure lists.
Boundary files: tests/test_tests_yaml_id_resolution.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | In a tests block, a tab line at or shallower than the items' depth followed by a deeper line (with or without a tab) takes back the readable ID written before the tab line, so that ID is never resolved and its resolution error is missing from the record's failure; the record still fails on its tab error, but the failure no longer lists every error at once (FR3, FR4) | TM-1 | After every tab line in the item loop no ID is held, so a deeper line that follows a tab line takes nothing back; only a tab line deeper than the items, directly after a readable ID, takes that ID back; every tab line stays reported as a tab error whatever its depth, so a record holding a tab line never passes (FR1, FR2) | task0001 AC-3 (with AC-1 and AC-2) | VERIFICATION.md, Performance / Security Verification: TM-1 |
