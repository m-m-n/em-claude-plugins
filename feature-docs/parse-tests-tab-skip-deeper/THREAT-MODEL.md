# Threat Model: parse-tests-tab-skip-deeper

## Verdict
no-applicable-threat

## Rationale
Inspected: SPEC.md (FR1-FR4, NFR1-NFR3, assumptions A1-A5) at the reduced
tier, the single task task0001 (domain `input-handling`, standard depth),
and the code path it changes: the pre-item scan of
`_RecordParser.parse_tests` in `tests/test_tests_yaml_id_resolution.py`.

One trust boundary exists: the text of a test record (written by an
implementer agent under `test-docs/`) crosses into the record check, a
verification gate that must not accept a record whose listed tests cannot be
resolved. No STRIDE category realistically applies to what this feature
changes at that boundary:

- Tampering (a record shaped to pass the gate or to hide a listed test from
  resolution): every record that reaches the changed branch contains a
  leading tab line, which the pre-item scan reports as `tab in indentation`
  before that branch is reached, so such a record fails the record check
  both before and after the change. The change (FR1) only narrows what is
  passed over: it adds readable IDs to the resolution set and removes none,
  and an element on a tab line or a continuation line never becomes an ID
  (A3). Every other path is unchanged (FR2).
- Denial of service: the change adds no input source and no I/O; it reuses
  the existing deeper-line skip, which always advances past the reported
  line.
- Spoofing, Repudiation, Information disclosure, Elevation of privilege:
  the change involves no identity, audit record, secret or privilege.

Domain consistency: task0001 declares `input-handling` because it changes
how record text is parsed. Its file appears in no `Boundary files` line only
because this short form carries none; the boundary described above is the
one that file implements, and no threat applies to it.
