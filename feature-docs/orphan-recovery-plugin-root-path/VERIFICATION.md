# Verification Document: orphan-recovery-plugin-root-path

## Overview
**Feature**: orphan-recovery-plugin-root-path / **SPEC.md**: `feature-docs/orphan-recovery-plugin-root-path/SPEC.md` / **IMPLEMENTATION.md**: none (reduced tier, single task) / **THREAT-MODEL.md**: `feature-docs/orphan-recovery-plugin-root-path/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python standard library, no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the project root)
- Expected: exit code 0, no failures, no errors
- Coverage target: not applicable (documentation-contract change; no coverage tooling configured)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Whitespace-normalized I.2.b contains the three new invocation sentences: the two recovery sentences carry `${CLAUDE_PLUGIN_ROOT}/scripts/recover-orphaned-task.py`, the merge-unverified sentence carries `${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py`, each cites Step I.0 step 4, and the two recovery sentences state `{project_root}` as the working directory | All present; forged sanity (phrase removed) makes each matcher fail | Unit (doc-contract) |
| TS-2 | The three pre-change cwd-relative invocation forms (orphan recovery invoke, same-session re-invoke, merge-unverified orchestrator invoke) are absent from the current document | Absent; each form is present in its verbatim pre-change sample (negative proof), and a retained anchor appears in both sample and document | Unit (doc-contract) |
| TS-3 | `$HOME/.claude/plugins` (and the other fallback search literals) occur in implement-phase.md only inside the Step I.0 section | Whole-document count equals Step I.0 count; a forged insertion into I.2.b is detected | Unit (doc-contract) |
| TS-4 | I.2.b states the resolution-failure outcomes: RECOVER_SCRIPT unresolved means Residual with the journal unchanged; the journal helper unresolved means Helper-failure residue with the journal unchanged | Both statements present, with forged sanity | Unit (doc-contract) |
| TS-5 | Existing pins stay green unchanged: ORPHAN_JOURNAL_HELPER_INVOCATION_PHRASE (script-internal invocation), R5_HELPER_NAMED_AS_EXCEPTION_PHRASE (Journal bullet), and the merge-task.sh / queue_launch_guard.py sha256 guards | All pass without edits to those constants or hashes | Unit (existing suite) |
| TS-6 | Planner-added (SPEC.md defines no scenario for NFR4): the feature diff from the implement base commit to the integration tip leaves `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `em-workflow/scripts/recover-orphaned-task.py`, `em-workflow/references/workflow-schema.md`, `em-workflow/scripts/merge-task.sh` and `em-workflow/hooks/queue_launch_guard.py` untouched | None of these paths appears in the changed-file list | Automated diff check (verify phase) |

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Orphan recovery invocation uses RECOVER_SCRIPT under `${CLAUDE_PLUGIN_ROOT}`, cites Step I.0 step 4, states `{project_root}` cwd in the same sentence | TS-1, TS-3 |
| AC-2 | Same-session re-invocation uses the same RECOVER_SCRIPT and the same cwd | TS-1 |
| AC-3 | merge-unverified invocation uses `${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py`, cites Step I.0 step 4, and keeps the exactly-once / merge-unverified / no-launch-identity meaning | TS-1 |
| AC-4 | Resolution failure: recovery sites become Residual, merge-unverified becomes Helper-failure residue, journal unchanged | TS-4 |
| AC-5 | No cwd-relative orchestrator invocation remains, a test detects it, and the full suite passes including the two updated pins | TS-2, TS-5, Test Verification command |
| AC-6 | FR7 out-of-scope text and recover-orphaned-task.py are unchanged | TS-5, TS-6 |
| SC-suite | `python3 -m unittest discover -s tests` passes | Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3 |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-1 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-1, TS-3 |
| FR6 | task0001 | TS-2, TS-5 |
| FR7 | task0001 | TS-5, TS-6 |
| NFR1 | task0001 | TS-1, TS-3 |
| NFR2 | task0001 | TS-2, TS-5 |
| NFR3 | task0001 | TS-2, TS-5 |
| NFR4 | task0001 | TS-6 |

## Manual Testing (E2E Not Possible)
- [ ] Distribution-configuration check: with em-workflow installed from the marketplace and a project that has no `em-workflow/` directory as the working directory, confirm that `${CLAUDE_PLUGIN_ROOT}/scripts/recover-orphaned-task.py` and `${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py` resolve to existing files in the installed plugin, so the I.2.b text now points at helpers that exist. Not automatable in this repository: its own working directory always contains `em-workflow/`, so the cwd-relative path resolved here even before the fix.

## Performance / Security Verification
- TM-1: the three I.2.b orchestrator invocation sites take the helper only from the plugin install root via Step I.0 step 4, and no cwd-relative invocation form remains — checked by TS-1 (new wording present) and TS-2 (old forms absent), automated.
- TM-2: a helper resolution failure invokes nothing and leaves the journal unchanged (Residual / Helper-failure residue) — checked by TS-4, automated.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Success criteria (AC-1 to AC-6, SC-suite) | 7 | 7 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Manual checks | 1 | 0 | 0 | 1 |
| Total | 16 | 15 | 0 | 1 |
