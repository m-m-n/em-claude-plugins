# Implementation Plan: implement-guard-compatible-git-ops

## Overview

The implement-phase protocol is changed so that its in-scope git operations (every refresh site and Step I.2.b step 4) pass `destructive-guard` unchanged: step 4 deletes the merged task branch with a non-forced deletion run inside the integration worktree, and the Branch & Worktree Model states the literal refresh-target rule and the artifact-write rule. Drift between protocol text and hook verdicts is detected by two layers: new hook case-table entries and a new document-extraction unittest. The hook's decision logic is not changed.

## Technology Stack

- **Language**: Python 3, standard library only (`unittest` as the test framework) — NFR3.
- **Protocol documents**: Markdown under `em-workflow/references/` and `em-workflow/skills/develop/SKILL.md`.
- **Hook under test**: `em-workflow/hooks/destructive-guard.py` (read-only for this feature, NFR1), exercised through `em-workflow/hooks/tests/run-destructive-guard.py` and through the new unittest.
- **New third-party dependencies**: none. `project.license` is `none`; no license record is required.

## Layer Structure

| Layer | Members | Responsibility |
|-------|---------|----------------|
| Protocol | `em-workflow/references/implement-phase.md`, `em-workflow/references/phase-state.md`, `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/phases/create-spec-phase.md` | Source of the git commands the orchestrator runs. Only `implement-phase.md` is edited by this feature. |
| Guard | `em-workflow/hooks/destructive-guard.py` | Judges a Bash command string. Not edited (NFR1). |
| Verification | `em-workflow/hooks/tests/destructive-guard-cases.json` + its runner; the `tests/` unittest suite | Pins hook verdicts for fixed commands (case table) and for commands extracted from the protocol documents (unittest). |

Dependency direction: the verification layer reads the protocol layer and invokes the guard layer. Nothing in the protocol or guard layer depends on the verification layer.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Guard invocation contract (`em-workflow/hooks/destructive-guard.py`, unchanged) | Returns a verdict for one Bash command | Pre: invoked as a child process with the current Python interpreter, the repository copy of the hook (never an installed copy), stdin = one JSON object with `tool_name` = `Bash` and `tool_input.command` = the command string (no `cwd` key), and `CLAUDE_BATCH` removed from the child environment. Post: exit status 0; stdout is either empty (verdict withheld — reported as `(silent)` by the runner) or one JSON object whose `hookSpecificOutput.permissionDecision` is `allow`, `deny` or `ask`. "Passes the guard" in this feature means: exit 0 AND the verdict is neither `deny` nor `ask` (`allow` and silent both pass). | task0001, task0002 |
| Canonical protocol command shapes (SPEC FR1, FR3, FR5) | The three command shapes this feature pins | Refresh: `git -C {integration_worktree} reset --hard em-workflow/{feature}/integration` — exactly one reset target, the literal integration branch name. Step 4 worktree removal: `git worktree remove "$WT_ROOT/{T}"` (no force flag). Step 4 branch deletion: `git -C {integration_worktree} branch -d "em-workflow/{feature}/{T}"` (non-forced flag, run against the integration worktree). A target that is a shell variable, a captured SHA, `HEAD`, a `refs/heads/`-prefixed name, or omitted is outside the refresh shape and is expected to be denied. | task0001 (protocol text + extraction), task0002 (case table) |
| Concrete sample values | Values substituted for placeholders in tests | Feature slug `some-feature` (matches the validated slug pattern `^[a-z0-9][a-z0-9-]*$`); task id `task0001`; per-feature worktree root of the shape `{root}/.claude/worktrees/em-workflow/some-feature`, with the integration worktree at `{root}/.claude/worktrees/em-workflow/some-feature/integration` and the task worktree at `{root}/.claude/worktrees/em-workflow/some-feature/task0001`. SPEC FR5 fixes `{root}` = `/home/sakura` for the case table; the unittest may use the same root. These are strings only — no path is created or read. | task0001, task0002 |
| Plugin version value | The released version for this change | `em-workflow/.claude-plugin/plugin.json` `version` and the `em-workflow` entry's `version` in `.claude-plugin/marketplace.json` are both exactly `0.2.9` (from `0.2.8`, FR8). The `em-review` entry and every other field of both files are unchanged. | task0001, task0002 |

## Conventions

- **Commit discipline (plugin version guard)**: the user's environment rejects any `git commit` whose staged change touches a file under `em-workflow/` while `em-workflow/.claude-plugin/plugin.json`'s `version` equals the one at `HEAD`, or whose marketplace entry disagrees with it. Therefore every task that edits a file under `em-workflow/` (a) applies the version value above to both manifests, and (b) puts all of its `em-workflow/` edits and the two manifest edits into one single commit. Test files under `tests/` are outside the plugin and may be committed separately. Both tasks write the identical value, so their manifest edits are identical and merge without conflict.
- **Hook logic is read-only**: no task edits `em-workflow/hooks/destructive-guard.py` or anything under `~/.claude/` (NFR1). If a hook verdict differs from what the plan expects, the task reports the observed verdict as a deviation; it never edits the hook or silently changes an expectation.
- **Case table discipline**: case entries keep the `[expected verdict, label, command]` format; existing entries are never removed, reordered or changed; every command string stays unique in the table (NFR2).
- **Test modules**: standard library `unittest` only; discovered by `python3 -m unittest discover -s tests`; repository paths resolved relative to the test file's own location; no file is written, and no real `~/.claude` state is read (NFR3). Documentation assertions follow the repository's existing pattern: section slicing by heading, whitespace normalization for prose that may wrap, and for every matcher asserting new wording a negative proof against a verbatim pre-change sample plus a non-vacuity guard.
- **Existing test anchors (NFR4, NFR5)**: edits to `implement-phase.md` never introduce `reset --hard "$LAUNCH_TIP"`, `reset --hard "$COMPLETION_TIP"`, or any `reset --hard "${var}"` form; add no new `reset --hard` inside any step section (Step I.1 through Step I.3); and leave Step I.2.c's single `git branch -D` and its `git worktree remove --force` wording untouched.

## Cross-task Design Decisions

### D1: Protocol-side fix; hook untouched

- **Decision**: make the protocol's commands fit the existing hook rather than widening the hook (SPEC A-C1, A-C4, NFR1).
- **Rationale**: the hook's detection strength is kept; the hook already allows the literal refresh shape and non-forced cleanup of non-integration targets.
- **Affected tasks**: task0001 (protocol text), task0002 (case table proves the hook's current verdicts).

### D2: Two-layer drift detection

- **Decision**: the case table pins verdicts for fixed, hand-written commands (hook-side regression); the document-extraction unittest pins verdicts for the commands as actually written in the protocol documents (document-side regression). Neither layer replaces the other (SPEC A-C5).
- **Affected tasks**: task0002 (case table), task0001 (extraction unittest).

### D3: Deferred sites stay out of both layers

- **Decision**: I.2.a's resume-guard clean re-attempt and I.2.c's route-back cleanup (forced worktree removal and forced deletion of unmerged branches) are known unaddressed items (SPEC FR7, "Out of Scope (Known Unaddressed)"). No task edits their text, the case table adds no allow case for their forced forms, and the extraction unittest lists them in an explicit, named exclusion list.
- **Affected tasks**: task0001, task0002.

### D4: Version bump carried by every plugin-touching task

- **Decision**: both tasks set the version value above in both manifests (Conventions, commit discipline). task0002 owns the feature's version-bump test module; task0001 applies the same value without a test module of its own.
- **Affected tasks**: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Non-forced deletion inside the integration worktree refuses in a real run (SPEC A1 is unverified) | Low | Medium | FR2: the branch is left and named in the wake-phase report; no forced fallback, so the failure is visible and non-destructive. |
| A spec'd case-table verdict differs from the hook's actual verdict (e.g. a contrast case returns `ask`, an allow case returns silent) | Low | Medium | The runner shows the observed verdict; the task reports it as a deviation instead of editing the hook (NFR1). |
| The extraction unittest passes vacuously (zero commands, wrong section boundary, unexpanded placeholder) | Medium | High | Per-site minimum-count assertion, missing-anchor failure, placeholder-residue failure, each with a negative proof (task0001). |
| New prose breaks an existing anchor test (NFR4/NFR5) | Medium | Medium | Conventions above; the full `tests/` suite is part of every task's acceptance. |
| A commit is rejected by the plugin version guard | Medium | Medium | Commit discipline above (single commit carrying `em-workflow/` edits and the version bump). |

## Open Questions

- [ ] Step I.3's refresh (`implement-phase.md` Step I.3, item 2) is a refresh site with the identical literal but is not enumerated in SPEC FR3's list. This plan includes it in the extraction unittest as an in-scope site (assumption).
- [ ] FR2's leftover-branch notice goes into the wake phase's own report. Under `--batch`, the existing output-suppression rule for step 4's cleanup narration is left unchanged by this plan, so in a batch refill turn the notice is withheld from the main context. Whether batch should surface it elsewhere is not decided by SPEC.
- [ ] FR7's "file a follow-up task" has no implementing task; it is outside what an implementer can do and is expected to be handled at run completion (run report / retrospect).
