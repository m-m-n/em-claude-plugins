# Verification Document: destructive-guard-rm-reason-positions

## Overview
**Feature**: destructive-guard-rm-reason-positions / **SPEC.md**: `feature-docs/destructive-guard-rm-reason-positions/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-rm-reason-positions/IMPLEMENTATION.md`

## Build Verification
- Command: none. project.components defines no build_command; the hook and the tests are Python scripts run directly.
- Expected: not applicable.

## Test Verification
- Commands (from workflow.yaml project.components):
  - hooks: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  - repo-tests: `python3 -m unittest discover -s tests`
  - plugin-invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for each command.
- Coverage target: no coverage tooling is configured. Instead, every scenario below maps to at least one automated test or manual check.

### Test Scenarios from SPEC.md

TS-1 to TS-8 correspond to SPEC.md TS1 to TS8. TS-9 onward are derived from SPEC.md requirements, assumptions and edge cases.

Unless the scenario states otherwise, "HOME fixed" means every case passes HOME and PATH explicitly. The positional designations below are quoted exactly.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (SPEC TS1, AC1) `echo "$(rm -rf /var/x)"; rm -rf /tmp/y` | deny / rm-recursive. The only designation is 1番目のrmの1番目の対象, and 2番目のrm does not occur. | Unit |
| TS-2 | (SPEC TS2, AC2) `bash -c 'rm -rf /var/valuable'; rm -rf /tmp/safe` | deny / rm-recursive. The unsafe target is designated 1番目のrmの1番目の対象. | Unit |
| TS-3 | (SPEC TS3, AC1) `rm -rf $(rm -rf /var/x)` | deny / rm-recursive. The inner target is designated 2番目のrmの1番目の対象, because the outer rm appears first. | Unit |
| TS-4 | (SPEC TS4, AC3) `$(printf rm) rm -rf /tmp/cache; rm -rf /var/valuable` | deny / rm-recursive. The designations are exactly 1番目のrmの1番目の対象 and 2番目のrmの1番目の対象 (`/var/valuable`), and 3番目のrm does not occur. | Unit |
| TS-5 | (SPEC TS5, AC4) `rm -rf -- -cache /tmp/scratch /var/valuable` | deny / rm-recursive. The only designation is 1番目のrmの3番目の対象. | Unit |
| TS-6 | (SPEC TS6, AC5) HOME fixed. `rm -rf /var/a /var/b`, run without gio and with a gio stub on PATH. Also two targets under the fixed HOME with the gio stub. | deny / rm-recursive. 1番目のrmの1番目の対象 and 1番目のrmの2番目の対象 occur once each. Each designation is followed by its own template: mv, mv, and gio trash respectively. No target text appears. | Unit |
| TS-7 | (SPEC TS7, AC6) `python3 em-workflow/hooks/tests/run-destructive-guard.py` | Every existing case passes, and the cases file is unchanged. | Integration |
| TS-8 | (SPEC TS8, AC7) `python3 -m unittest discover -s tests` | Everything passes: the new regression module, `tests/test_destructive_guard_rm_reason.py`, and the existing single-target exact-text pin in `tests/test_destructive_guard_command_substitution.py`. | Integration |
| TS-9 | (NFR1) Each TS-1 to TS-6 command is run twice with the same environment. | stdout is byte-identical between the two runs. | Unit |
| TS-10 | (FR7) Inspect the docstrings of rm_target_designation(), check_rm(), route_substitution_headed_statement(), strongest_rm_decision() and statements(), and the comment at main()'s invocation-numbering site. | They describe the new numbering and none of the stale statements listed in task0001 AC-7 remains. | Unit (source inspection) + review |
| TS-11 | (NFR2, TM-1) Combined reasons, each run with and without CLAUDE_BATCH: one rm with two targets carrying planted instruction text; two rm invocations doing the same; one target carrying a newline plus a forged hook prefix alongside one carrying a control character. | No planted text, forged prefix or target text appears in the reason. Control-character targets carry the fixed control-character sentence. stdout has no raw control character. | Unit |
| TS-12 | (FR1 forms) Three commands: the backtick spelling of TS-1; `bash <<< 'rm -rf /var/a'; rm -rf /tmp/b`; a heredoc fed to bash whose operator line continues with `; rm -rf /tmp/b` and whose body is `rm -rf /var/a`. | deny / rm-recursive. The unsafe target is designated 1番目のrmの1番目の対象, 1番目のrmの1番目の対象 and 2番目のrmの1番目の対象 respectively. | Unit |
| TS-13 | (FR2, assumption A1) Two commands: `$(printf rm) rm -rf /var/cache`; `$(foo) rm -rf /var/x`. | Both deny / rm-recursive. The first designates exactly 1番目のrmの1番目の対象 and 1番目のrmの2番目の対象, once each, and 2番目のrm does not occur. The second designates 1番目のrmの1番目の対象 only. | Unit |
| TS-14 | (FR3, assumptions A2 and A3) Three commands: `rm -rf -- -- /var/x`; `rm -rf - /var/x`; `rm -rf -- -x`. | Designations 1番目のrmの2番目の対象 and 1番目のrmの1番目の対象 respectively. The third command stays allow. | Unit |
| TS-15 | (FR4, assumption A5, FR5) Three commands: `rm -rf / /var/a`; `rm -rf /var/a "$(pwd)/b"`; TS-5's command without gio. | `rm -rf / /var/a`: deny / rm-root, with exactly one template, after 1番目のrmの2番目の対象. `rm -rf /var/a "$(pwd)/b"`: deny / rm-recursive, with exactly one template, between 1番目のrmの1番目の対象 and 1番目のrmの2番目の対象. TS-5's command: the reason equals today's single-target text for 1番目のrmの3番目の対象 with the mv template. | Unit |
| TS-16 | (NFR4) Diff of the feature branch against the implement base commit, restricted to `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. | Neither file is modified. | Manual (git diff) |

## Code Quality Verification
- Format: none configured (format_command is empty).
- Static analysis: none configured. Plugin invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The TS1 command's reason designates `/var/x` as 1番目のrmの1番目の対象 and contains no 2番目のrm; deny / rm-recursive. | TS-1 (TS-3 guards the nested form) |
| AC2 | The TS2 command's reason designates the denied target as 1番目のrmの1番目の対象; verdict and rule unchanged. | TS-2 |
| AC3 | The TS4 command's reason contains no 3番目のrm, and `/var/valuable` is 2番目のrmの1番目の対象; verdict and rule unchanged. | TS-4 |
| AC4 | The TS5 command's reason designates `/var/valuable` as 1番目のrmの3番目の対象; verdict and rule unchanged. | TS-5 |
| AC5 | The combined reason for `rm -rf /var/a /var/b` gives a gio trash or mv template for each position, chosen by HOME and gio, and contains no target text. | TS-6 |
| AC6 | No existing case of run-destructive-guard.py changes its verdict. | TS-7 |
| AC7 | Regression tests for AC1 to AC5 exist under tests/, and `python3 -m unittest discover -s tests` passes. | TS-8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-12 |
| FR2 | task0001 | TS-4, TS-13 |
| FR3 | task0001 | TS-5, TS-14 |
| FR4 | task0001 | TS-6, TS-15 |
| FR5 | task0001 | TS-1 to TS-7, TS-12 to TS-15 (verdict and rule assertions) |
| FR6 | task0001 | TS-8 |
| FR7 | task0001 | TS-10, manual review below |
| NFR1 | task0001 | TS-9 |
| NFR2 | task0001 | TS-6, TS-11 |
| NFR3 | task0001 | TS-8 (new module uses unittest only; HOME and PATH set explicitly) |
| NFR4 | task0001 | TS-16 |

## Manual Testing (E2E Not Possible)
- [ ] Read the combined reasons produced for TS-6 and TS-15. Each template should read as belonging to the designation before it, and the Japanese should read naturally.
- [ ] FR7: read the docstrings and the comment listed in TS-10 against the implemented numbering. This is the positive half that the source-inspection test cannot judge.
- [ ] TS-16: confirm that the feature diff leaves the plugin manifest and the marketplace file untouched.

## Performance / Security Verification
- TM-1: The reason is built only from hook-authored text, and stdout carries no raw control character. Checked by TS-6 (no target text in the combined reason) and TS-11 (planted text, a forged prefix and control characters, with and without CLAUDE_BATCH).
- TM-2: Route merging, deduplication, deferred rendering and `--` renumbering never weaken or drop a decision. Checked in two parts:
  - TS-7: the full case suite, with the cases file unchanged.
  - The verdict and rule assertions of TS-1 to TS-6 and TS-12 to TS-15, pinned against the unmodified hook before editing.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-16) | 16 | 15 | 0 | 1 |
| Security verification (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Additional manual checks (readability, FR7 wording) | 2 | 0 | 0 | 2 |
