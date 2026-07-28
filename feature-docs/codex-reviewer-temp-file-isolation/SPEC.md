# Feature: codex-reviewer temp-file isolation

## Overview

Parallel `codex-reviewer` subagents share one session scratchpad directory. When
a reviewer writes its Codex prompt to a fixed-name temp file (e.g. `prompt.txt`),
another reviewer launched in the same message can overwrite that file between the
write and the read, so a reviewer sends a different perspective's prompt to Codex
and returns the resulting findings under its own perspective label. This feature
puts a uniqueness rule for scratchpad temp files into the agent definitions
themselves, in both the `em-workflow` and `em-review` plugins.

## Objectives

- Guarantee temp-file uniqueness from the agent definition, not from
  orchestrator prompt text.
- Cover concurrent reviewers of different perspectives AND repeated runs of the
  same perspective.
- Apply the same rule to both plugins' `codex-reviewer` agents.

## User Stories

### US1: Parallel reviewers keep their own prompts

As a review orchestrator, I want each parallel `codex-reviewer` to use its own
temp files, so that the findings I aggregate actually belong to the perspective
they are labeled with.

**Acceptance Criteria:**
- [ ] Each agent definition instructs the agent to create scratchpad temp files
      at a path that cannot collide with a concurrently running sibling.
- [ ] The rule does not depend on any orchestrator-supplied instruction.

### US2: Re-running the same perspective is safe

As a `codex-reviewer` retrying its Codex call, I want a fresh temp path per
attempt, so that a retry never overwrites a still-in-flight earlier attempt of
the same perspective.

**Acceptance Criteria:**
- [ ] The naming rule is explicitly stated to be per-invocation, not
      per-perspective.
- [ ] Using the perspective name alone as the filename is explicitly forbidden.

## Technical Requirements

### Functional Requirements

- **FR1:** `em-workflow/agents/codex-reviewer.md` states that any temp file the
  agent writes into the session scratchpad (Codex prompt, schema copy,
  intermediate output) MUST be created at a per-invocation-unique path.
- **FR2:** `em-review/agents/codex-reviewer.md` carries the same rule, worded
  consistently with FR1.
- **FR3:** The rule names the concrete mechanism to use (`mktemp` with a
  template, which allocates the file atomically and never returns an existing
  path) rather than only stating the property, so an agent following the
  definition produces a compliant path without inventing one.
- **FR4:** The rule explicitly forbids fixed names (`prompt.txt`) and
  perspective-only names (`security-prompt.txt`), naming the collision they
  cause.
- **FR5:** Temp-file creation failure is handled fail-closed: the agent returns
  the standard skip object
  (`{"findings": [], "summary": "skipped: ...", "skipped": true, "source": "codex"}`)
  instead of proceeding with an unwritten or shared path.
- **FR6:** The rule is scoped so that an agent that passes the prompt directly as
  an argument (no temp file at all) remains compliant — uniqueness is required
  only when a temp file is actually used.
- **FR7:** A structural test under `tests/` asserts FR1–FR6 over both agent
  definition files, following the documentation-task test pattern already used
  by `tests/test_review_implement_develop_lock_contracts.py` and
  `tests/test_planner_designer_worktree_docs.py`.

### Non-Functional Requirements

- **NFR1 - Compatibility:** `run_codex_exec.sh` keeps its current interface; no
  prompt-file flag is added and no call site changes its argument shape.
- **NFR2 - Maintainability:** The agent definitions are the single source of
  truth for this rule; it is not duplicated into `review-phase.md` dispatch
  prompts.
- **NFR3 - Security:** Temp paths must not be predictable fixed locations; the
  `mktemp` template supplies the random component.

## Implementation Approach

### Architecture

Documentation-only change to two agent-definition Markdown files. No executable
code is added or modified.

```
em-workflow/agents/codex-reviewer.md   ← temp-file discipline section
em-review/agents/codex-reviewer.md     ← same section, plugin-adjusted
```

### Data Flow

```
perspective skill → prompt assembly (Step 4)
                  → [if a temp file is used] mktemp-created unique path
                  → run_codex_exec.sh readonly ... "$PROMPT"
                  → JSON findings (Step 6)
```

### Dependencies

**Internal Dependencies:**
- `em-workflow/skills/codex-prompting/SKILL.md`: defines prompt block structure;
  unchanged by this feature.
- `em-workflow/references/review-phase.md` Phase R2: the parallel-dispatch rule
  that creates the collision window; unchanged by this feature.

**External Dependencies:**
- `mktemp` (coreutils): already assumed available by the plugins' shell usage.

### File Structure

```
em-workflow/
└── agents/
    └── codex-reviewer.md
em-review/
└── agents/
    └── codex-reviewer.md
```

## Test Scenarios

### Unit Tests
- [ ] `tests/test_codex_reviewer_temp_file_isolation.py` asserts, for BOTH
      `em-workflow/agents/codex-reviewer.md` and
      `em-review/agents/codex-reviewer.md`: a temp-file discipline section
      exists, it names `mktemp` with an `XXXXXX` template, it forbids fixed
      names, it states per-invocation (not per-perspective) uniqueness, and it
      defines the fail-closed skip on creation failure.
- [ ] The same test asserts the `run_codex_exec.sh` invocation line is unchanged
      in both files (no prompt-file flag introduced).
- [ ] `python3 -m unittest discover -s tests` passes with no regressions.

### Integration Tests

Not applicable — there is no runnable integration surface for agent-definition
prose beyond the structural test above.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Not applicable — running a real parallel Codex review requires the Codex
      CLI, which is not installed in this environment.

### Edge Cases
- [ ] Same perspective re-run: the definition states the path is per-invocation,
      so a retry gets a different path.
- [ ] `mktemp` failure: the definition routes to the fail-closed skip object.
- [ ] No temp file used: the rule does not apply, and the agent stays compliant.

### Performance Tests

Not applicable.

## Security Considerations

- **Input Validation:** Unchanged; the diff/file contents remain untrusted input
  per the existing `<grounding_rules>` block.
- **Data Protection:** Temp files stay inside the session scratchpad; the
  `mktemp` random suffix removes the predictable-path exposure of a fixed name.

## Error Handling

| Condition | Handling |
|-----------|----------|
| `mktemp` fails | Return `{"findings": [], "summary": "skipped: scratchpad temp file unavailable", "skipped": true, "source": "codex"}` |

## Success Criteria

- [ ] All functional requirements are implemented
- [ ] All integration test scenarios pass
- [ ] `run_codex_exec.sh` is unmodified in both plugins
- [ ] Both plugins' `plugin.json` versions are bumped by a patch level

## Assumptions

Recorded because this run was executed in batch mode without user dialogue, and
the Codex consultation loop was skipped (the Codex CLI is not installed in this
environment):

- **A1:** The concrete mechanism prescribed is `mktemp` with a template
  (e.g. `mktemp "${TMPDIR:-/tmp}/codex-<perspective>-XXXXXX.txt"`). The task
  description cited PID/`$RANDOM` modification as the ad-hoc recovery used
  during the incident; `mktemp` was chosen instead because it allocates the file
  atomically rather than merely making a collision unlikely.
- **A2:** The change is confined to the two agent-definition files. The
  `review-phase.md` dispatch prompts are deliberately left untouched so the rule
  has one home (NFR2).
- **A3:** Both plugins' `plugin.json` versions get a patch bump, per the
  repository's version-management convention in `CLAUDE.md`.
- **A4:** A structural `unittest` test is added (FR7) even though the task
  description did not ask for one, because the repository already tests
  documentation-only changes this way (`test_review_implement_develop_lock_contracts.py`,
  `test_planner_designer_worktree_docs.py`) and `test/README.md` mandates
  `tests/test_*.py` as the verification surface.

## Open Questions

None.

## References

- Notion task: [https://www.notion.so/3ab3509ec8ee812db0a9c11a44449b72](https://www.notion.so/3ab3509ec8ee812db0a9c11a44449b72)
- REQUIREMENTS.md: `feature-docs/codex-reviewer-temp-file-isolation/REQUIREMENTS.md`
- `em-workflow/references/review-phase.md`
- `em-review/references/review-phase.md`
