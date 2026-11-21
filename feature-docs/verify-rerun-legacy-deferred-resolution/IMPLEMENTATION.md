# Implementation Plan: verify-rerun-legacy-deferred-resolution

## Overview

The develop skill's subsection 「#### verify pass による deferred 指摘の解決」 is extended so that a verify re-run on a workflow.yaml whose verify step lacks round / passed_ids follows the same procedure, and its mapping rule is restated; a scenario test pins the path from that re-run to a proceed result of merge-preflight.py. No script changes.

## Technology Stack

- **Language**: Python 3, standard library only (unittest) for every test.
- **Procedure text**: Markdown in Japanese, matching the existing develop SKILL.md.
- **New dependencies**: none. No license entry is needed (project.license: none).

## Layer Structure

| Layer | Members | Responsibility |
|-------|---------|----------------|
| Procedure | em-workflow/skills/develop/SKILL.md, subsection 「#### verify pass による deferred 指摘の解決」 | The orchestrator's instructions: when round / passed_ids are written, when findings are mapped to passed IDs, when the resolution script runs |
| Script (unchanged) | em-workflow/scripts/resolve-verified-findings.py, em-workflow/scripts/merge-preflight.py | Resolve mapped findings; judge merge readiness |
| Test | tests/test_verify_pass_resolution_procedure.py (existing), tests/test_verify_rerun_legacy_resolution.py (new) | Pin the procedure text; run the scripts as child processes against a temporary git repository |

Allowed dependency directions: tests read the procedure text or run the scripts as child processes. Neither the procedure nor the scripts depend on the tests. No test imports a script as a module.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Legacy re-run procedure (the develop SKILL.md subsection) | Defines what the orchestrator records and runs when verify is re-run on a workflow.yaml whose verify step lacks round and/or passed_ids | Pre: the verify step has no round (read as 0) and/or no passed_ids (read as the empty set), per workflow-schema.md 「`round` and `passed_ids`」. Post: one workflow.yaml write records result, round 1 and passed_ids (the IDs passed in this round). When result is pass: deferred critical/high findings with category spec in the latest review round are mapped to passed IDs under the mapping rule (Cross-task Design Decision D3), a mapping file holding each mapped stable_id and its criterion ID is written, resolve-verified-findings.py runs on it, and the result is committed to the integration branch. When result is not pass: no mapping and no script run | task0001 (writes it), task0002 (simulates the orchestrator's side of it in the fixture) |
| resolve-verified-findings.py (existing, unchanged) | Sets the resolution of mapped findings in the latest review round record | Pre: verify round is 1 or more, and every criterion ID in the mapping file is in passed_ids. Post: each mapped finding has resolution fixed and a verify_resolution field. Its command-line shape and mapping-file format are the script's own; the tests follow them as the script and tests/test_resolve_verified_findings.py define them | task0001 (referenced by the procedure text), task0002 (run as a child process) |
| merge-preflight.py (existing, unchanged) | Merge pre-check | Returns unresolved_findings while the latest review round holds a critical/high finding whose resolution is neither fixed nor declined; returns proceed once no such finding remains and its other checks pass | task0002 (run as a child process) |

## Conventions

- Tests import the standard library only, run scripts as child processes with the running interpreter, and use a git repository in a temporary directory as the fixture, in the same shape as tests/test_resolve_verified_findings.py.
- Every git command and script run in a test targets the temporary repository. No test writes to the real repository or to user-level git configuration.
- In the develop SKILL.md verify phase, category vocabulary is written without backticks, and no text writes gate_id, AskUserQuestion or batch-policies.yaml (NFR2).
- This repository is exempt from per-commit version handling: no task changes a plugin version (NFR4).
- Report and fixture file names follow skills/plan-writing/SKILL.md 「Report Artifact Names」; no new file takes a matching name.

## Cross-task Design Decisions

### D1: The legacy case is handled by the procedure, not by the scripts

- Decision: resolve-verified-findings.py keeps its round of 1 or more guard, and merge-preflight.py keeps its judgment. A legacy workflow.yaml satisfies the guard because the re-run adds one to the absent round (read as 0) and writes passed_ids in the same write as result.
- Rationale: FR2 / FR6 forbid script changes; the existing guard and its tests stay valid.
- Affected tasks: task0001, task0002.

### D2: The re-run is the same procedure, not a separate branch

- Decision: the subsection states that a re-run on a legacy workflow.yaml runs the same steps as any verify round, in interactive and batch mode alike, adding no gate, no question and no batch non-packet gate (NFR3). The legacy read rule of workflow-schema.md is cited, not restated or changed.
- Rationale: one procedure keeps the existing fixed phrases (NFR2) valid and gives the scenario test one sequence to follow.
- Affected tasks: task0001, task0002.

### D3: Mapping rule — the claim decides, add-ons do not

- Decision: a finding is mapped to a passed criterion ID only when its claim is that criterion ID's miss itself. Cause analysis, fix suggestions and scope judgments written alongside that claim do not prevent the mapping. A finding is not mapped when its correspondence is ambiguous, when it also claims the miss of another criterion that has not passed or another defect, or when the ID merely appears in its body. This replaces the exclusion 「未達そのもの以外の内容を含む指摘は対応づけない」.
- Rationale: FR3; a finding that states a criterion miss together with its cause is the typical shape of a deferred spec finding.
- Affected tasks: task0001 writes the rule; task0002's fixture finding has the shape the rule maps (one criterion miss with a cause-analysis add-on), so the scenario is consistent with the rule.

### D4: The re-run trigger is outside this feature

- Decision: neither task describes or tests returning verify to pending. The scenario test starts from the stuck state (all steps completed or skipped) and records the re-run's result directly.
- Rationale: A5.
- Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| merge-preflight.py has checks besides the review-findings check that the fixture does not satisfy, so proceed is not reached | Medium | High | task0002 builds the fixture to satisfy those checks as the script defines them; changing the script is not an option (FR6). If proceed cannot be reached without a script change, the implementer reports a plan deviation |
| Another test or document outside the Scope pins the old exclusion phrase | Low | Medium | Each task runs the full test suite; a failure in an out-of-scope file is reported as a plan deviation, not fixed silently |
| The loosened mapping rule lets a finding that hides another unresolved defect be set fixed | Medium | High | THREAT-MODEL.md TM-1 |
| Instruction-shaped text in a finding body steers the mapping | Low | High | THREAT-MODEL.md TM-2 |
| Reading YAML fixtures without third-party libraries | Medium | Low | task0002 follows the reading approach of tests/test_resolve_verified_findings.py |

## Open Questions

- None.
