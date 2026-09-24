# Implementation Plan: abort-docs-commit-precedence

## Overview

Resolve the one phase-specific-vs-phase-specific stop-point collision (the batch
second-failure abort's terminal status commit exhausting `commit-docs.sh` exit-4
recovery) in favour of `docs-commit-conflict` → `docs_commit_conflict_aborted`,
and define the uncommitted terminal status write that stop leaves, its disposal
at develop's resume entry, and the re-derivation on the next run. The change is
documentation-only: reference prose, SKILL prose, one script comment, new
doc-contract tests and the two version manifests.

## Technology Stack

- **Documents**: Markdown protocol documents under `em-workflow/references/` and `em-workflow/skills/` - the normative text being changed
- **Tests**: Python 3 standard-library `unittest` - doc-contract tests that pin the new statements
- **Manifests**: JSON (`plugin.json`, `marketplace.json`) - plugin version
- **Script**: one Bash script, comment lines only
- **New dependencies**: none. `project.license` is `none`, and no dependency is introduced, so there is nothing to record or check.

## Layer Structure

| Layer | File(s) | Owns |
|-------|---------|------|
| Binding SSOT | `em-workflow/references/batch-terminal-line.md` ('Precedence rule:' paragraph) | Which stop point / reason code the collision binds to, the no-Step-B statement, the retry-success carve-out, and the written-but-uncommitted distinction |
| Worktree-state SSOT | `em-workflow/references/implement-phase.md` (Branch & Worktree Model) | The uncommitted terminal status write at this stop, the named exception to the "never carries uncommitted state across turns" claim, re-derivation on resume, and the `detail` / `resume_conditions` content for this stop |
| Orchestrator procedure | `em-workflow/skills/develop/SKILL.md` (Step A) | The resume-entry refresh that discards the leftover write |
| Script comment | `em-workflow/scripts/commit-docs.sh` (RECOVERY CONTRACT comment) | A pointer only; no rule of its own |
| Doc-contract tests | `tests/` (new modules only) | Pinning each SSOT's new statements |
| Version manifests | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | The em-workflow version |

Allowed reference direction: a document points at the owning SSOT and never
restates its content.

- batch-terminal-line.md → implement-phase.md Branch & Worktree Model (for the leftover write's disposal and the next run's handling)
- implement-phase.md → develop/SKILL.md Step A (for the discard action), and → batch-terminal-line.md Precedence rule (for the binding)
- commit-docs.sh comment → implement-phase.md (for the exception)

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Call-site name | Names the commit that fails at this stop | The exact phrase "Step I.2.c abort-phase terminal status commit" is used wherever a document names this call site. Pre: the existing implement-phase.md wording "Step I.2.c's abort-phase terminal status commit" stays untouched (NFR2). Post: both tasks' new text names the call site with this phrase. | task0001, task0002 |
| Terminal status write | Names the write that stays uncommitted | Written as the pair `implement: failed` / `failed_kind: decision` and called "the terminal status write". Neither task writes it as "`failed_kind` reads `decision`", because that phrase is an existing first-occurrence anchor of the Precedence paragraph. | task0001, task0002 |
| Abort terminal-commit exception | Named exception to the claim that the integration worktree never carries uncommitted state across turns | Label text is exactly "abort terminal-commit exception". Post (task0002): implement-phase.md's Branch & Worktree Model section defines an exception under this label, scoped to exactly this stop. task0001 may cite it only by this label plus "implement-phase.md Branch & Worktree Model", never restating its content. Pre (task0001): the section heading "Branch & Worktree Model" exists at base and is not renamed by either task. | task0001 (cites), task0002 (defines) |
| em-workflow version | Plugin cache refresh | Both tasks set the em-workflow `version` to exactly `0.2.2` in both manifests: a value assignment from 0.2.1, not a relative increment. Post-merge: both manifests read 0.2.2. The two tasks make identical line edits, so the merge has no conflict. | task0001, task0002 |

## Conventions

- **Pointers, not restatement**: each fact has one owning document (Layer Structure). A document that needs another document's fact names the owner and section. It does not repeat the rule.
- **Pinned text is preserved**: every phrase listed in SPEC NFR2 stays byte-for-byte. New sentences are appended after existing ones in the same region, so existing first-occurrence and order assertions keep holding. A new sentence never adds an earlier occurrence of an existing anchor phrase, and never reuses a retired phrase.
- **Terminology in new document text**: "NFR2" in SPEC/REQUIREMENTS means the existing claim "the integration worktree never carries uncommitted state across turns". New document text quotes or paraphrases that claim instead of citing this feature's requirement numbering.
- **Tests**: each task creates its own new test module. No task modifies an existing test module; those modules are the regression guards for NFR1, NFR2 and the version-lockstep check. If an existing test goes red, the fix belongs in the document under change. If the document cannot be fixed that way, report it as a plan deviation.
- **Doc-contract test style (repository convention)**:
  - Read the repository file relative to the test module.
  - Slice only the owned region, by its heading or label.
  - Normalize whitespace (and comment prefixes for the shell script) before phrase matching.
  - Cite requirement and TS IDs in docstrings.
  - Use a verbatim pre-change sample for each negative proof. Capture it from the base revision, never paraphrase or reconstruct it.
- **No executable change**: no executable line of any script changes (NFR4).

## Cross-task Design Decisions

### D1: FR6 and FR7 text lives in implement-phase.md's Branch & Worktree Model

SPEC leaves the location of the re-derivation statement (FR6) and the
`detail` / `resume_conditions` content (FR7) open. Both go into the abort
terminal-commit exception in implement-phase.md's Branch & Worktree Model.
Reasons:

- The I.2.c batch-mode paragraph through the end of I.2.c is byte-frozen (NFR2).
- The exception is where the stop's leftover state is defined.
- A single region gives TS-5 one place to assert.

batch-terminal-line.md's Precedence paragraph states only the binding and the
written-but-uncommitted distinction, and points to the exception.

Affected: task0001 must not state re-derivation or `detail` /
`resume_conditions` content. task0002 owns both.

### D2: Binding and state are split between two SSOTs

- batch-terminal-line.md decides which code the stop binds to (FR1-FR3, FR8).
- implement-phase.md decides what the stop leaves behind and how the next run handles it (FR4, FR6, FR7).
- develop/SKILL.md performs the discard (FR5).

This lets the two tasks run in parallel. The only coupling is the Shared
Components above: the call-site name, the terminal status write term and the
exception label.

Affected: task0001, task0002.

### D3: Both tasks carry the version bump

Both tasks change files under `em-workflow/`. The repository rule
(`.claude/rules/core-plugin-version-bump.md`) and the commit-time version guard
require the bump in the same change as the content, so each task sets the
version itself. The rule is "set to 0.2.2", not "increment", so the two
identical edits merge without conflict and without a double bump (FR10).

Affected: task0001, task0002.

### D4: Separate new test modules

- task0001 creates `tests/test_abort_terminal_commit_precedence.py` (TS-1, TS-2).
- task0002 creates `tests/test_abort_terminal_write_resume.py` (TS-3, TS-4, TS-5, TS-9).

No test module is shared, so neither task's tests read the other task's region.

Affected: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing Precedence-paragraph tests break. They slice from the label to the next blank line, and one checks the order of the route-based `stop-condition-3` restriction before the `failed_kind` restriction by first occurrence. | Medium | High | Append new sentences at the paragraph end with no blank line. Do not reuse existing anchor phrases earlier in the text. Run the full suite. |
| The byte-pinned RECOVERY CONTRACT carve-out sentence (including its line wraps) in commit-docs.sh is disturbed by the comment edit | Medium | Medium | Edit only the step-(1) parenthetical. Keep the carve-out lines and the pinned recapture/refresh phrasing byte-identical. |
| The unconditional resume-entry refresh discards tracked, uncommitted edits a user made by hand in the integration worktree between runs (SPEC a3, irreversible) | Low | Medium | SKILL.md text states that the refresh discards tracked uncommitted changes only and leaves untracked files alone, consistent with the existing "never carries uncommitted state across turns" claim |
| Guards treat the new refresh differently from the existing ones | Low | Medium | The new refresh uses the same command form, targeting the branch name, as the existing integration-worktree refreshes. No hook or script changes. |
| The retry-consumed marker is not actually committed before the abort (a5 unconfirmed), so re-derivation after the discard would grant a retry again | Low | High | task0002 confirms the marker's commit point from implement-phase.md's text before writing FR6. If the marker is not committed there, report a plan deviation instead of weakening FR6. |
| The two tasks bump the version differently | Low | Low | D3: both set exactly 0.2.2 |

## Open Questions

- [ ] a5 (REQUIREMENTS.md 14.2): the exact commit point of the batch retry-consumed marker in `tasks.{T}.notes` is unconfirmed. FR6 relies on it; task0002 verifies it against implement-phase.md while implementing.
