# Threat Model: self-write-digest-path-normalization

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR4, NFR1-NFR3, Security Considerations) at the
reduced tier (no REQUIREMENTS.md; design step skipped), and the single
task's domains (`input-handling`, `api-contract`). The feature changes how
the orchestrator-run `self-write-digest.py` decides whether a path a worker
created lies under one of `allowed_write_roots`; that decision admits the
path into the self-write set, whose digest changes are excused from the
staleness comparison of `references/contracts/worker-envelope.md` Rule R1.
The path strings name files a worker process created during its dispatch,
so they cross from an untrusted party into the orchestrator's staleness
decision; `input-handling` sets that boundary's depth to deep.

The `worker-envelope.md` edit is contract text only, and the test files run
only inside the test process; neither carries a boundary. `api-contract` is
not one of the four depth domains. At TB-1 only Tampering realistically
applies: the script reads only its input document and returns a decision,
so nothing is disclosed, no privilege changes, and no action needs
attribution. A false stale verdict (the defect this feature fixes) is a
correctness failure a worker can only inflict on its own result, so it gets
no Denial of service row.

## Trust Boundaries

### TB-1: Worker-created path names into the self-write identification
Crossing: the path strings of files created during a worker dispatch (the
worker chooses the names; the orchestrator's scope verification observes
them) together with the dispatch envelope's `allowed_write_roots`, flowing
into `self-write-digest.py`'s allowed-root containment decision, which
decides which changed digest inputs are excused from Rule R1's staleness
comparison.
Boundary files: em-workflow/scripts/self-write-digest.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Because the script normalizes differently from scope validation, the identification judges a path to be inside an allowed root when scope validation's containment refuses it. Examples: a `..` segment written with `\`, a NUL byte, or a root that is empty, absolute, or holds NUL or `..`. The path then enters `self_write_set`, and a change it makes to a tracked input is substituted with the dispatch-time digest instead of being reported stale (FR1; SPEC.md Security Considerations) | TM-1 | The containment decision rejects a side (root or path) that is empty, starts with `/`, contains NUL, or holds a `..` segment with `\` treated as a separator. Otherwise it requires the normalized root's segments to be a strict prefix of the path's segments. The result is the same truth value as `validate-worker-output.py`'s `path_is_contained_in_root` for every (path, root) pair, and root containment still admits `created` changes only | task0001 AC-4 (supported by AC-2, AC-3) | VERIFICATION.md Performance / Security Verification: TM-1 (TS-5) |
