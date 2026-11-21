# Threat Model: verify-rerun-legacy-deferred-resolution

## Verdict
threats-identified

## Rationale
Inspected at the full tier: SPEC.md, REQUIREMENTS.md and the two planned tasks. The feature changes the develop SKILL.md procedure that decides which deferred review findings the orchestrator maps to passed verify IDs; a mapped finding is set fixed by resolve-verified-findings.py, and merge-preflight.py then lets the feature merge. Finding bodies originate from reviewer models whose own input includes the reviewed diff, so they are untrusted text interpolated into the orchestrator's judgment. That is the one trust boundary (TB-1). task0001 declares input-handling, which sets this boundary's depth to deep.

The legacy re-run statement (FR1) crosses no trust boundary: round, passed_ids and result are written by the orchestrator itself in one write, from its own verify evaluation.

task0002 declares external-io for its child processes and temporary git repository. Its file appears in no Boundary files line because the test creates and consumes only its own fixture data inside its temporary directory; no party of different trust supplies data to it. Its isolation from the real repository is an acceptance criterion of the task, not a mitigation of a threat at a boundary.

## Trust Boundaries

### TB-1: Review finding text into the orchestrator's mapping judgment
Crossing: the bodies of deferred critical/high findings with category spec in the latest review round record, written by reviewer models from the reviewed diff, are read by the orchestrator, whose mapping judgment writes the mapping file that resolve-verified-findings.py turns into resolution fixed and that merge-preflight.py then trusts.
Boundary files: em-workflow/skills/develop/SKILL.md, em-workflow/scripts/resolve-verified-findings.py (unchanged)
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | The add-on tolerance of the revised mapping rule (FR3) lets a finding that also claims another not-passed criterion's miss or another defect be mapped to a passed ID, so an unresolved critical/high defect is set fixed and no longer stops merge-preflight.py (FR5, FR6) | TM-1 | The subsection tolerates only cause analysis, fix suggestions and scope judgments of the same miss, and states that findings also claiming another not-passed criterion's miss or another defect, findings with ambiguous correspondence and findings where the ID merely appears are not mapped; tests pin each statement | task0001 AC-2 | VERIFICATION.md Performance / Security Verification TM-1 (TS-2) |
| Elevation of privilege | Instruction-shaped text in a finding body (for example a request to map it to a passed ID) steers the orchestrator into writing a mapping, gaining its authority to resolve findings (NFR2, NFR3; SPEC.md Security Considerations) | TM-2 | The rewritten subsection keeps its Untrusted-Input Handling reference and the requirement that an ID appearing in the body is not enough, and adds no gate or question; tests pin their presence | task0001 AC-4 | VERIFICATION.md Performance / Security Verification TM-2 (TS-5) |
