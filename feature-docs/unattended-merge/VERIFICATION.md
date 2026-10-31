# Verification Document: unattended-merge

## Overview

**Feature**: unattended-merge / **SPEC.md**: `feature-docs/unattended-merge/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/unattended-merge/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command: `python3 -m unittest -v tests.test_merge_local_route`. Both TS1 cases must report `ok`; a `skipped` TS1 case fails this item.
- Expected: exit code 0 for each command
- Coverage target: no coverage tool is used in this project; every task Acceptance Criterion maps to at least one test

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Local route end to end: temporary repository without a remote, integration branch with a completed workflow.yaml, merge-git subcommands in order (and, in the full-chain case, merge-preflight first), then the skill's main-tree merge and worktree removal emulated | Base has a `--no-ff` merge commit whose second parent is the integration tip; the worktree is gone; both branches remain; both test cases report ok | Integration |
| TS2 | Already merged: base containing the integration tip (merge-git merged); gh stub reporting a MERGED PR (merge-pr resolve) | `merged` reported; no ref, working tree or PR change | Unit |
| TS3 | Precondition: implement pending, verify failed, verify completed with result fail | `precondition_unmet` with the step names in detail | Unit |
| TS4 | Review records: round1 and round2; round2 holds deferred high, declined critical and fixed high | Stops on the deferred high's stable_id only; declined-only passes; no rounds skips the check | Unit |
| TS5 | Remote selection: upstream set / no upstream with one remote / no upstream with several remotes / non-GitHub remote | Upstream remote, the single remote, `remote_unresolved`, `remote_not_github` | Unit |
| TS6 | CI wait: no checks / a failing check / pending until the deadline | `no_checks`, `ci_failed`, `ci_timeout` | Unit |
| TS7 | Base moved: fixture advancing the base before every base-check | `redo` for redo counts 0-2, `base_moving` at 3 | Unit |
| TS8 | Lock exclusivity: another feature's holder alive, a second hold attempted | `lock_busy` immediately; verify with the second token is not `held` | Unit |
| TS9 | destructive-guard allow: canonical gh pr merge from an integration worktree (and a subdirectory) | allow, with and without CLAUDE_BATCH | Unit (hook cases) |
| TS10 | destructive-guard ask/deny: forbidden flags, missing SHA, main-tree working directory, canonical form followed by a dangerous segment | ask without CLAUDE_BATCH, deny with it; the dangerous segment gets its own decision | Unit (hook cases) |
| TS11 | Unapproved commands: `EM_WORKFLOW_APPROVALS` pointing at an empty store | `commands_unapproved` naming each component.field; the store is byte-identical afterwards | Unit |
| TS12 | Result format: every reason code rendered by the output-side function; injection-shaped detail; out-of-vocabulary inputs | Key order, double quotes and escaping match merge-result.md; no extra key; invalid inputs become `internal_error` without echoing the value | Unit |
| TS13 | PR creation route: gh stub reporting no PR | resolve returns `none` with `create_head` = integration branch and `create_base` = base_branch | Unit |
| TS14 | Main working tree: on another branch, detached, or with a tracked modification | `main_tree_not_ready` | Unit |
| TS15 | SKILL.md static contract: placement and frontmatter, usage rule before the first Bash instruction, feature-pattern check, each direct command form, lock lifecycle, conflict procedure, final-message rule; absence of gate_id, AskUserQuestion, while/until and prohibited forms in command forms | All checks pass | Unit (static) |
| TS16 | Target resolution and untrusted fields: invalid feature name, missing integration branch, unreadable/non-mapping/object-tagged workflow.yaml, unsafe base_branch values, instruction-shaped free text | `invalid_feature_name`, `integration_branch_missing`, `record_unreadable`, `base_branch_invalid`; free text changes no verdict | Unit |
| TS17 | PR states: closed-only, draft, conflicting, open with mergeable/unknown, head different from the verified SHA | `pr_closed`, `pr_draft`, `pr_conflicting`, `ready`, `pr_head_moved` | Unit |
| TS18 | Base integration: clean merge, already-contained base, conflicting base, base fetched from a local bare remote | One merge commit with parents (previous tip, integrated base); `up_to_date` without a commit; `conflict` with paths and the merge in progress; previous tip stays an ancestor | Unit |
| TS19 | Integration worktree state and resumption: absent, clean, merge in progress, dirty, another branch, unregistered directory, missing registered directory; merge abort then re-check | `absent`, `clean`, `merge_in_progress`, `worktree_not_clean` for each anomaly; `clean` after the abort | Unit |
| TS20 | Script operation boundary: git logging shim and gh stub logs across the script test modules | No push, PR create/merge, worktree add/remove, rebase, reset, force or write API from any script | Unit |
| TS21 | Result redaction: detail with an absolute path under the supplied project root, a path under the home directory, and a Notion URL | Repository-relative path, `~/...`, `<notion-url>` | Unit |
| TS22 | destructive-guard allow-list strictness: short flags, `--repo` / `-R`, environment prefix, extra tokens, malformed SHA or PR number, `..` traversal and non-feature-shaped working directories | ask without CLAUDE_BATCH, deny with it; never allow | Unit (hook cases) |
| TS23 | Lock identity: holder terminated, stale record from a dead process, second run of the same feature | `lock_lost`; a new hold succeeds after the stale record; the second run gets `lock_busy`, never `held` | Unit |
| TS24 | gh repository match: gh's default repository differs from, or cannot be determined beside, the chosen remote's repository | `remote_unresolved` | Unit |
| TS25 | CI head and call budget: PR head different from the pushed SHA, hanging gh stub, pending past the budget then continued with the returned deadline | `pr_head_moved`; returns within budget; `pending` with the same deadline, then a later outcome | Unit |
| TS26 | Docs and version: README skill table row and destructive-guard hook row; em-workflow descriptions in plugin.json and marketplace.json; em-workflow version compared with `workflow.implement.base_commit` | Merge skill and the limited allow described; version equal in both files, minor one greater, patch zero, major unchanged; other plugins unchanged | Integration (verify-phase inspection with git diff against the base commit) |
| TS27 | Test isolation review: new test modules | Standard-library unittest only; per-test temporary repositories; gh only through PATH stubs; approvals through `EM_WORKFLOW_APPROVALS`; no real network or real `~/.claude`; no bytecode written under `em-workflow/` | Manual (review) |

## Code Quality Verification

- Format: none configured (`format_command` is empty)
- Static analysis: plugin invariants run inside the unittest suite (gate_id coverage must stay satisfied, NFR8)

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Without `--batch`, usage only and no git/gh change | TS15; manual check 1 |
| AC2 | A step not completed/skipped stops with the step name | TS3 |
| AC3 | Deferred high stops with its stable_id; declined-only does not | TS4 |
| AC4 | Local route: `--no-ff` merge commit, worktree removed, branches kept | TS1, TS14 |
| AC5 | Several remotes without upstream, or non-GitHub remote, stop | TS5, TS24 |
| AC6 | Already merged: no integration, push or merge; success | TS2, TS19 |
| AC7 | No PR: push and `gh pr create`, then PR route; pr_url in the result | TS13, TS15; manual check 3 |
| AC8 | Unattributable conflict: worktree clean, not merged | TS15, TS19; manual check 2 |
| AC9 | Unapproved command: nothing run, store unchanged | TS11 |
| AC10 | test_command failure: no push, failed command in the result | TS15; manual check 2 |
| AC11 | No checks → merge; failed or 60-minute timeout → no merge | TS6, TS25 |
| AC12 | Base moved: redo, stop when a 4th redo would be needed | TS7 |
| AC13 | Canonical gh pr merge allowed only from the integration worktree; other shapes ask / deny | TS9, TS10, TS22 |
| AC14 | Every terminal ends with only the contract-conformant result | TS12, TS15 |
| AC15 | Another feature's lock blocks integration and merge | TS8, TS23 |
| AC16 | Both test commands pass | Test Verification commands |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0008 | TS15 |
| FR2 | task0002, task0008 | TS15, TS16 |
| FR3 | task0002, task0003, task0008 | TS16, TS19 |
| FR4 | task0002 | TS3 |
| FR5 | task0002 | TS4 |
| FR6 | task0003, task0004 | TS1, TS5, TS14, TS24 |
| FR7 | task0003, task0004, task0008 | TS2 |
| FR8 | task0004, task0008 | TS13, TS15, TS24 |
| FR9 | task0004 | TS17 |
| FR10 | task0005, task0008 | TS8, TS23 |
| FR11 | task0003 | TS18 |
| FR12 | task0008 | TS15, TS19 |
| FR13 | task0002, task0008 | TS11, TS15 |
| FR14 | task0008 | TS15 |
| FR15 | task0006, task0008 | TS6, TS25 |
| FR16 | task0003, task0008 | TS7 |
| FR17 | task0008 | TS9, TS15 |
| FR18 | task0003, task0008 | TS1, TS14 |
| FR19 | task0003, task0008 | TS1, TS14, TS15 |
| FR20 | task0007 | TS9, TS10, TS22 |
| FR21 | task0001, task0008 | TS12, TS15 |
| FR22 | task0002, task0003, task0004, task0005, task0006, task0008 | TS15, TS20 |
| FR23 | task0007, task0008, task0009 | TS26 |
| NFR1 | task0006, task0008 | TS15, TS25 |
| NFR2 | task0003, task0008 | TS15, TS18, TS20 |
| NFR3 | task0003, task0004, task0008 | TS2, TS19 |
| NFR4 | task0002, task0004, task0008 | TS15, TS16 |
| NFR5 | task0001, task0002, task0003, task0004, task0005, task0006 | TS27 |
| NFR6 | task0007 | TS9, TS10, TS22 |
| NFR7 | task0001, task0008 | TS15, TS21 |
| NFR8 | task0001, task0008 | TS15 |

## Manual Testing (E2E Not Possible)

- [ ] 1. In a disposable repository, invoke `/em-workflow:merge demo` without `--batch`. Only usage text appears; branches, worktrees and PRs are unchanged (AC1).
- [ ] 2. In a disposable repository without a remote, run `/em-workflow:merge --batch <feature>` against three fixtures:
  - a base-side change by a feature whose `feature-docs/` exists: the conflict is resolved, verification runs and the merge happens
  - a conflict with no attributable origin: the worktree is clean and the result is `conflict_unattributable` (AC8)
  - a failing test_command: no merge, and the failed command is in the result (AC10)
- [ ] 3. Against a disposable GitHub repository, run the PR route end to end. Check: PR created with `--head` / `--base`, CI wait, the canonical `gh pr merge` allowed by destructive-guard under CLAUDE_BATCH, `pr_url` and `merge_commit` in the result, and the worktree removed with branches kept (AC7, FR14, FR17). Re-running returns `already_merged` (AC6).
- [ ] 4. Review the final message of each run in checks 2-3: it is only the rendered result and carries no absolute home path or Notion URL (AC14, NFR7).

## Performance / Security Verification

- NFR1: each script invocation returns within 600 s (TS25); the CI wait totals at most 60 minutes per run (TS6)
- TM-1: feature name validated before any Bash call and re-validated by preflight — TS15, TS16
- TM-2: unsafe base_branch values stop `base_branch_invalid` — TS16
- TM-3: workflow.yaml read with safe loading only — TS16
- TM-4: fail-closed precondition and latest-round finding gate — TS3, TS4
- TM-5: approval checked before any verification command, approved strings run verbatim — TS11, TS15
- TM-6: spec / commit / conflicted text treated as data; conflict-step actions limited and followed by verification — TS15; manual check 2
- TM-7: origin attribution requires a pattern-matching name with base-side feature-docs — TS15; manual check 2
- TM-8: exact token allow-list for the canonical gh pr merge — TS9, TS10, TS22
- TM-9: segments after an allowed merge segment are still judged — TS10
- TM-10: working directory normalized; feature and integration segments exact — TS22
- TM-11: gh default repository must equal the chosen remote's repository — TS24
- TM-12: PR head must equal the pushed / verified SHA; merge pinned with `--match-head-commit` — TS17, TS25, TS15
- TM-13: per-call budget, time-limited gh calls, absolute deadline — TS6, TS25
- TM-14: closed vocabularies, single-line escaped values, invalid input → `internal_error` — TS12
- TM-15: redaction of home paths and Notion URLs in the result — TS21
- TM-16: exclusive lock held from integration through merge; busy stops — TS8
- TM-17: per-run token and live-holder check — TS23

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1-TS27) | 27 | 26 | 0 | 1 |
| Success criteria (AC1-AC16) | 16 | 16 | 0 | 4 (also covered manually) |
| Security mitigations (TM-1-TM-17) | 17 | 17 | 0 | 2 (TM-6, TM-7 also manual) |
| Performance (NFR1) | 1 | 1 | 0 | 0 |
| Manual checks | 4 | 0 | 0 | 4 |
