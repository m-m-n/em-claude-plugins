# Implementation Plan: destructive-guard-mixed-rm-precedence

## Overview

destructive-guard stops letting a non-rm `ask` swallow a recursive-delete `deny` in the same compound command, whichever comes first. Non-rm asks are held until the scan ends and are compared with the pooled rm decisions before any CLAUDE_BATCH demotion. The case runner gains an optional `rule` key, so a case can pin the reason id as well as the decision.

The feature has two tasks:
- task0001: the hook, the runner, the case table and their tests.
- task0002: the case-format rule document.

## Technology Stack

- **Language**: Python 3, standard library only (the hook, the runner and the tests).
- **Test framework**: the existing case runner (`em-workflow/hooks/tests/run-destructive-guard.py`) and unittest from the standard library.
- **New dependencies**: none. project.license is `none`, so there is no license constraint to check and nothing to record.

## Layer Structure

1. **Hook** (`em-workflow/hooks/destructive-guard.py`). Its stages are:
   - statement scan;
   - collection (the rm record pool, the held non-rm asks, the FR8 exclusions);
   - one resolution step;
   - emission. The CLAUDE_BATCH demotion happens only inside emission.
2. **Case runner** (`em-workflow/hooks/tests/run-destructive-guard.py`). It runs the hook as a child process for each case and compares the decision, and the reason id when the case pins one.
3. **Case table** (`em-workflow/hooks/tests/destructive-guard-cases.json`). Data only.
4. **Rule document** (`.claude/rules/hook-tests.md`). It describes the case format and how to add cases.

Allowed dependencies:
- The runner reaches the hook only as a child process. It never imports it (A6).
- The rule document describes the runner's case format and the hook's verdict precedence. Nothing reads it at run time.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Case format (the optional fourth element of a case) | Sets the situation a case is judged in, and optionally pins the reason id | A case is `[decision, label, command]` or the same three elements plus a fourth element. The fourth element is an object with up to three keys: `cwd` (string), `batch` (boolean) and `rule` (non-empty string). All three are optional. The run ends as a malformed case in each of these situations: another key is present; `cwd` is not a string; `batch` is not a boolean; `rule` is not a string or is empty; the fourth element is not an object; the case has more than four elements. The **reason id** of a verdict is the `<rule>` part of a permissionDecisionReason that starts with `[destructive-guard/<rule>]`. A reason that does not start that way has no reason id. A case with `rule` passes only when both the decision and the reason id equal the expected values. Its FAIL line shows the obtained reason id in addition to what a FAIL line shows today. A case without `rule` is compared on the decision only, as today. Three-element cases and cases with only `cwd` / `batch` get the same result as today | task0001 (implements the runner, writes the cases), task0002 (documents the format) |
| Verdict precedence (behaviour after this feature) | Which verdict the hook emits when several checks reach a decision in one command | 1. A non-rm `deny` is emitted at once and ends the scan (unchanged, A2). 2. Otherwise, when the scan ends (normally or at an early stop), a `deny` among the pooled rm records wins, whatever the segment order. Its reason id is rm-recursive or rm-root and its reason text is the rm reason. The records of a statement where FR8 applies do not compete. 3. Otherwise the asks win in the order the unmodified hook emits them: the first non-rm `ask` in scan order, then the early-stop or unreadable-chunk `ask`, then the PR-merge fallback `ask`, then the rm `ask`. 4. The CLAUDE_BATCH demotion applies only to the verdict that is emitted, after steps 1-3. FR8: in a statement whose own rm deletion operand is a protected self-config path, the self-modification `ask` competes as an ordinary held `ask`, and that statement's rm records are left out | task0001 (implements), task0002 (summarises it in the case-adding guidance) |

## Conventions

- **No new tier, reason id or wording.** Every verdict the hook emits keeps its existing tier, reason id and reason text. The feature changes only which verdict is emitted.
- **New cases** are added at the end of the case table, after the last existing case. Each carries the fourth element with `rule`. Target paths are generic examples (`/home/user/valuable`, `/etc`, `~/.claude/...`), with no machine-specific path. Each label starts with the feature name and the scenario ID it pins.
- **Existing cases**: none is removed, edited or reordered (NFR1). Tests under `tests/` pin prefixes of the case table by count and digest, so insertion anywhere but the end breaks them.
- **Existing source and document pins.** Tests under `tests/` read main()'s comments, several docstrings of the hook, the runner's text and `.claude/rules/hook-tests.md`. When a comment or a document is rewritten, the phrases those tests require stay.
- **Tests.** The hook runs as a child process with PreToolUse JSON on standard input. CLAUDE_BATCH is set only for a case that needs it, and HOME and PATH are set explicitly whenever reason text is compared.
- **Plugin version.** This repository bumps plugin versions in CI. No task changes a version (NFR6).

## Cross-task Design Decisions

### D1: The hook, the runner and the case table form one task

- **Decision.** task0001 covers FR1-FR6, FR8 and the hook and runner parts of FR7. task0002 covers only the `.claude/rules/hook-tests.md` part of FR7.
- **Rationale.**
  - Tasks run fully in parallel, each in its own worktree.
  - The new rule-pinned cases (FR6) pass only with both pieces in place: the runner must accept the `rule` key (FR5), and the hook must be fixed (FR1-FR4, FR8).
  - Split by component, each task would hold a suite it cannot pass in its own worktree.
  - The rule document depends only on the case-format contract above, so it is a separate task.
- **Affected tasks.** task0001, task0002.

### D2: Non-rm asks are held until the scan ends

- **Decision.** Every non-rm `ask` in the statement loop is recorded instead of emitted. One resolution step after the scan applies the verdict precedence above. Non-rm denies keep their immediate exit.
- **Rationale.**
  - The task description offers a smaller alternative: compare the collected rm decisions only at each non-rm exit. That cannot satisfy FR2, because an rm that comes after the `ask` has not been scanned yet at that point.
  - Keeping non-rm denies immediate leaves A2 as it is and adds no new competition between denies.
- **Affected tasks.** task0001 implements it. task0002 describes the result.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing `ask` case turns into `deny`, because a statement after its first `ask` is now scanned and holds a `deny` | Low | Medium: NFR3 permits the change, but the case cannot be edited (NFR1) | The implementer runs the full suite. A changed existing case is reported as a plan deviation and is not edited |
| A held `ask` is lost on some exit path and the command gets `allow` | Low | High (guard bypass) | One resolution step for every path; per-judgment state (THREAT-MODEL.md TM-4) |
| The early-stop handling changes the reason id of a command that has no `deny` | Medium | Medium | Expected reason ids for the no-deny scenarios are recorded from the unmodified hook before editing (task0001 AC-6) |
| The FR8 exclusion is wider or narrower than SPEC.md states | Medium | High | Scenarios that pin both sides of the exclusion (THREAT-MODEL.md TM-3) |
| The continued scan slows evaluation past the hook timeout | Low | High (verdict lost) | The scan budget and the lexer work bound are unchanged, and every case runs under the runner timeout (THREAT-MODEL.md TM-5) |
| Rewritten comments or documents drop a phrase that an existing test pins | Medium | Low | The full unittest suite runs in both tasks |

## Open Questions

None.
