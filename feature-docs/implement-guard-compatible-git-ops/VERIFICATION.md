# Verification Document: implement-guard-compatible-git-ops

## Overview

**Feature**: implement-guard-compatible-git-ops / **SPEC.md**: `feature-docs/implement-guard-compatible-git-ops/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/implement-guard-compatible-git-ops/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` and `project.components.hooks.build_command` are empty).
- Plugin invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .` — Expected: exit code 0.

## Test Verification

- Command (main): `python3 -m unittest discover -s tests` — Expected: exit code 0, no failures or errors.
- Command (hooks): `python3 em-workflow/hooks/tests/run-destructive-guard.py` — Expected: exit code 0, final line reports every case passed.
- Coverage target: not measured (documentation + test-only change); every acceptance criterion maps to at least one scenario below.

### Test Scenarios from SPEC.md

TS-1 to TS-8 are SPEC.md's scenarios. TS-9 to TS-17 are derived from SPEC.md's Success Criteria (AC-1 to AC-4, AC-8) and Non-Functional Requirements so that every requirement has a verifying scenario.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Case table: `git -C` at the integration worktree, `reset --hard em-workflow/some-feature/integration` | destructive-guard verdict `allow` | Unit (case table) |
| TS-2 | Case table: same refresh shape with a `refs/heads/`-prefixed target, and with a `"$BRANCH"` target | verdict `deny` for both (contrast) | Unit (case table) |
| TS-3 | Case table: `git -C` at the integration worktree, `branch -d em-workflow/some-feature/task0001` | verdict `allow` | Unit (case table) |
| TS-4 | Case table: `git worktree remove` of `.../em-workflow/some-feature/task0001`, no force flag | verdict `allow` | Unit (case table) |
| TS-5 | Case table: existing case `git reset --hard HEAD~1` | still `deny` | Unit (case table) |
| TS-6 | Extraction test: refresh commands from implement-phase.md / phase-state.md / SKILL.md / create-spec-phase.md and the I.2.b step 4 commands, placeholders expanded | no command is `deny` or `ask` | Integration |
| TS-7 | Extraction test: an in-scope site from which zero commands are extracted | the test fails, naming the site | Integration (negative proof) |
| TS-8 | Extraction test: each exclusion-list site (I.2.a resume guard clean re-attempt, I.2.c route-back cleanup) | not extracted, not a failure cause; each entry still resolves in the document | Integration |
| TS-9 | implement-phase.md I.2.b step 4 wording (AC-1) | no `git branch -D`; `git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` after the unchanged `git worktree remove "$WT_ROOT/{T}"`; forced-deletion rationale removed; non-forced rationale present | Unit (document) |
| TS-10 | implement-phase.md I.2.b step 4 failure rule (AC-2) | states no forced deletion on failure, branch left, branch name in wake-phase report | Unit (document) |
| TS-11 | implement-phase.md Branch & Worktree Model literal-target rule (AC-3) | rule present once, naming all five excluded forms; every refresh site literal intact | Unit (document) |
| TS-12 | implement-phase.md "Every workflow artifact" bullet (AC-4) | states Write tool, no Bash heredoc, no heredoc in the Bash call running `commit-docs.sh` | Unit (document) |
| TS-13 | Plugin manifests (AC-8) | `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json` both read `0.2.9`; em-review entry unchanged | Unit |
| TS-14 | Hook logic unchanged (NFR1) | the feature's diff against `workflow.implement.base_commit` contains no change to `em-workflow/hooks/destructive-guard.py` and no path outside the repository | Integration (diff check) |
| TS-15 | Existing case table preserved (NFR2) | `TestCaseTableDiscipline` in `tests/test_destructive_guard_command_substitution.py` passes | Unit |
| TS-16 | Extraction test hygiene (NFR3) | standard library `unittest` only; `CLAUDE_BATCH` removed for the hook child process; no file written; no real `~/.claude` state read | Unit |
| TS-17 | Existing anchor tests (NFR4, NFR5) | `test_tip_capture_idiom_uniformity`, `test_exit4_tip_argument_consistency`, `test_routeback_reset_scope_consistency`, `test_implement_routeback_gate`, `test_recycled_task_id_consistency` all pass | Unit |

## Code Quality Verification

- Format: none configured (`format_command` is empty for both components).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | I.2.b step 4 uses `git -C {integration_worktree} branch -d ...` after `git worktree remove`, no `git branch -D` | TS-9, TS-6 |
| AC-2 | I.2.b step 4 states no forced deletion on failure, branch kept and reported | TS-10 |
| AC-3 | Refresh literals intact at every in-scope site; literal-target rule in Branch & Worktree Model | TS-11, TS-6 |
| AC-4 | Artifact-write rule (Write tool, no heredoc with `commit-docs.sh`) | TS-12 |
| AC-5 | FR5 allow cases and deny contrast cases present; hook runner passes | TS-1, TS-2, TS-3, TS-4, TS-5, hooks test command |
| AC-6 | Extraction test covers every in-scope site; deferred sites on a named exclusion list | TS-6, TS-7, TS-8 |
| AC-7 | `python3 -m unittest discover -s tests` passes | main test command |
| AC-8 | Both manifests at the same new version | TS-13 |
| AC-9 | Deferred sites recorded in SPEC as known unaddressed | SPEC.md "Out of Scope (Known Unaddressed)" lists both sites (manual read); TS-8 for the test-side list |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-9 (wording), TS-6 (step 4 commands pass the hook), TS-3 / TS-4 (fixed shapes) |
| FR2 | task0001 | TS-10 |
| FR3 | task0001 | TS-11 (rule + literals), TS-6 (extracted refresh commands), TS-1 / TS-2 (fixed shapes) |
| FR4 | task0001 | TS-12 |
| FR5 | task0002 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| FR6 | task0001 | TS-6, TS-7, TS-8 |
| FR7 | task0001 | TS-8; SPEC.md Out of Scope section (manual read) |
| FR8 | task0001, task0002 | TS-13 |
| NFR1 | task0001, task0002 | TS-14 |
| NFR2 | task0002 | TS-5, TS-15 |
| NFR3 | task0001 | TS-16 |
| NFR4 | task0001 | TS-17 |
| NFR5 | task0001 | TS-17 |

## Manual Testing (E2E Not Possible)

- [ ] Read SPEC.md "Out of Scope (Known Unaddressed)": both deferred sites (I.2.a resume guard clean re-attempt, I.2.c route-back cleanup) are listed with their commands (AC-9).
- [ ] Read the rewritten I.2.b step 4 and the two Branch & Worktree Model additions as a whole: the text reads as one consistent rule set with the surrounding protocol (no contradiction with the exit-4 recovery bullet or the batch-mode paragraph).

## Security Verification

- Destructive-command guard strength is kept: TS-2 (non-literal refresh targets stay `deny`), TS-5 (existing `reset --hard` deny unchanged), TS-14 (hook logic unchanged).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build / invariants | 1 | 1 | 0 | 0 |
| Case table (TS-1 to TS-5) | 5 | 5 | 0 | 0 |
| Extraction test (TS-6 to TS-8) | 3 | 3 | 0 | 0 |
| Document wording (TS-9 to TS-12) | 4 | 4 | 0 | 0 |
| Version (TS-13) | 1 | 1 | 0 | 0 |
| NFR checks (TS-14 to TS-17) | 4 | 4 | 0 | 0 |
| Manual reading | 2 | 0 | 0 | 2 |
