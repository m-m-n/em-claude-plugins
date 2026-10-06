# Threat Model: validator-scenario-id-format

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (tier `reduced`: no REQUIREMENTS.md, design step skipped)
and the two planned changes: the scenario ID extraction in
`em-workflow/scripts/validate-worker-output.py` (task0001, domains
`input-handling`, `api-contract`) and the scenario ID rule in
`em-workflow/skills/plan-writing/SKILL.md` (task0002, domain `api-contract`).

The validator reads VERIFICATION.md files and rework_index declarations
written by an LLM worker (rework-planner), and its result decides whether
the orchestrator applies that worker's rework patch. That crossing is TB-1,
analysed at deep depth because task0001 declares `input-handling`. The
SKILL.md edit is project-authored text shipped with the plugin; no data
crosses a trust boundary there, so it has no TB.

At TB-1 only Tampering realistically applies: the change widens which tokens
count as scenario IDs, and the rework_index novelty check depends on those
tokens. Denial of service has no row: the widened rule is one linear
pattern with no nested repetition. The validator changes no identity,
privilege or log record and discloses nothing beyond error strings about
its own inputs, so Spoofing, Repudiation, Information disclosure and
Elevation of privilege have no row.

Domain consistency: task0001 is the only task declaring one of the four
depth domains, and its file `em-workflow/scripts/validate-worker-output.py`
is TB-1's boundary file.

## Trust Boundaries

### TB-1: Worker-written VERIFICATION.md into the worker-output validator
Crossing: VERIFICATION.md content and rework_index `new_scenarios`
declarations written by the rework-planner (LLM worker output) cross into
the validator, whose result gates the orchestrator's application of the
rework patch.
Boundary files: em-workflow/scripts/validate-worker-output.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A rework result declares an ID that already exists in the baseline VERIFICATION.md (in either form) as a new scenario, so a rework task passes the coverage check without adding a verifying scenario; a widened rule applied differently to the baseline and current documents, or one that normalizes forms, would let it through (FR1, FR2) | TM-1 | Novelty is the literal set difference between the IDs extracted from the current and the baseline VERIFICATION.md through the one extraction rule that recognizes both forms; no normalization between forms; an ID present in both is rejected with the existing `is not a new VERIFICATION.md scenario` error | task0001 AC-4 | VERIFICATION.md Performance / Security Verification: TM-1 |
