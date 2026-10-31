# Feature: codex-consult-output-scratchpad

## Overview

When the orchestrator saves the output of a `run_codex_exec.sh` call (stdout or
stderr) to a file, that file goes into the session scratchpad directory and is
never written under the project root. The rule is stated once, in step 2
("Wrapper invocation") of the Codex consultation procedure in
`em-workflow/references/question-resolution.md`. The develop tier pre-survey
cites it, and structural doc tests pin both documents.

## Objectives

- Output from an orchestrator-side Codex wrapper call that the orchestrator saves to a file goes into the session scratchpad. No untracked file is left in the target project's working tree.
- A test detects a regression of this rule.

## User Stories

None. Requirements are stated as functional and non-functional requirements
with acceptance criteria below.

### Acceptance Criteria

- [ ] **AC-1** (FR1): The step 2 region of question-resolution.md's Codex consultation procedure states that saved wrapper output (stdout/stderr) is placed in the session scratchpad.
- [ ] **AC-2** (FR2): The step 2 region states that saved output is never written under the project root and never through a path relative to the current directory.
- [ ] **AC-3** (FR3): The wrapper invocation line and the `--litellm` variants are byte-for-byte unchanged. The existing `test_codex_procedure_wrapper_invocation` still passes.
- [ ] **AC-4** (FR4): The SKILL.md tier section's step 3 region cites `references/question-resolution.md`'s Codex consultation procedure step 2 and does not restate the rule.
- [ ] **AC-5** (FR5, FR6): The new assertions in `tests/test_question_resolution_doc.py` and `tests/test_develop_tier_staged_procedure.py` pass on the fixed documents. Each negative twin shows that the pre-fix wording of its region does not satisfy the matcher.
- [ ] **AC-6** (NFR2, NFR3): `python3 -m unittest discover -s tests` passes with no regressions.

## Technical Requirements

### Functional Requirements

- **FR1:** Scratchpad placement of saved wrapper output — Step 2 ("Wrapper invocation") of the "Codex consultation procedure" in `em-workflow/references/question-resolution.md` states: when the output of a `run_codex_exec.sh` call (stdout or stderr) is saved to a file, that file is placed in the session scratchpad directory. This rule is defined only here.
- **FR2:** Project-root prohibition — The same step 2 states that the output file is never written under the project root (`{project_root}`). The redirect target is never a path relative to the current directory.
- **FR3:** Invocation form unchanged — These stay unchanged: the wrapper invocation line in step 2 (`"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly -C "{project_root}" "$PROMPT"`), its `--litellm` variants, the 600000 ms timeout, and the exit-code-based chain advance. Saving the output to a file stays optional. The rule applies only when the output is saved.
- **FR4:** Citation from the develop tier pre-survey — In `em-workflow/skills/develop/SKILL.md`, "### tier 決定", step 3 ("3. **Codex 事前調査**") cites the FR1/FR2 rule by naming `references/question-resolution.md` and the Codex consultation procedure's step 2 (Wrapper invocation). It does not restate the rule. The existing step markers ("3. **Codex 事前調査**", "4. **no-work 停止**") and the step's existing sentences stay unchanged.
- **FR5:** Regression test for question-resolution.md — `tests/test_question_resolution_doc.py` gains assertions scoped to the region bounded by "2. **Wrapper invocation.**" and "3. **One turn per call.**". They pin the scratchpad placement (FR1) and the project-root prohibition (FR2). A negative twin shows that the pre-fix step 2 text fails these matchers.
- **FR6:** Regression test for the SKILL.md citation — `tests/test_develop_tier_staged_procedure.py` gains a test class scoped to the region of the tier section bounded by "3. **Codex 事前調査**" and "4. **no-work 停止**", reusing the module's existing locator and `_contains`/`_strip_ws` helpers. It asserts that the region cites `references/question-resolution.md` and its Codex consultation procedure step 2. It also asserts that the region does not restate the rule's own sentence. A negative twin shows that the pre-fix step 3 text fails the citation matcher.

### Non-Functional Requirements

- **NFR1 - No undefined shell variables:** Neither edited text introduces a bare shell variable that the plugin does not define (for example the orchestrator-local `$S`). The scratchpad is named in prose. If a path example contains a variable, that variable uses a guarded default form (`${VAR:-default}`).
- **NFR2 - question-resolution.md test retention:** All existing tests in `tests/test_question_resolution_doc.py` stay green. In particular, the added text contains none of these: 'rate limit', 'rate-limit', '429', the listed provider names, a `task\d{4}` identifier, or a new gate_id literal.
- **NFR3 - SKILL.md test retention:** All existing tests in `tests/test_develop_tier_staged_procedure.py` stay green. In particular, the SKILL.md tier section contains no decimal literal matching `\d+\.\d+`, no 'P(0)', no 'expectation_clear', no 'gate_id: <value>', and no 'AskUserQuestion'. The step markers it indexes are unchanged.
- **NFR4 - Doc redaction:** The added text contains no Notion URL and no absolute path under the user's home directory.
- **NFR5 - Plugin version untouched:** Plugin versions are not touched (the version-bump Action raises the patch on push).
- **NFR6 - Document language:** Each edit uses the language of its surrounding document: English in question-resolution.md, Japanese in SKILL.md.

## Assumptions

- **A-1** (reversible; related question: `create-spec.scope-orchestrator-wrapper-sites`): The codex-reviewer agent definitions (em-workflow and em-review) stay out of scope. They already carry their own temp-file discipline section.
- **A-2** (reversible): "Session scratchpad" means the per-session scratchpad directory that the Claude Code harness provides to the orchestrator. The documents name it in prose and do not define a plugin variable for it.
- **A-3** (reversible): Completion criterion (1) (the phenomenon no longer occurs) is met by the documented rule plus the structural doc tests (criterion 2). No test performs a live Codex run.
- **A-4** (reversible): The wrapper invocation string in question-resolution.md step 2 and the SKILL.md tier step markers are preserved unchanged.

## Implementation Approach

### Architecture

**System Architecture:**

Not applicable. This is a documentation-only change to a reference document
and a skill document, plus structural tests. No UI.

**Component Diagram:**
```
em-workflow/references/question-resolution.md
  Codex consultation procedure, step 2 (Wrapper invocation)
    -- defines the rule (FR1, FR2); invocation form unchanged (FR3)
        ^
        | cited by (FR4)
em-workflow/skills/develop/SKILL.md
  ### tier 決定, step 3 (Codex 事前調査)

tests/test_question_resolution_doc.py        -- pins step 2 region (FR5)
tests/test_develop_tier_staged_procedure.py  -- pins step 3 citation (FR6)
```

### Data Flow

```
Orchestrator → run_codex_exec.sh → stdout / stderr
             → (only if saved to a file) session scratchpad directory
             ✗ never under {project_root}, never a path relative to the current directory
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/question-resolution.md`: owns the rule (Codex consultation procedure, step 2).
- `em-workflow/skills/develop/SKILL.md`: cites the rule from the tier pre-survey step.
- `tests/test_develop_tier_staged_procedure.py`: existing locator and `_contains`/`_strip_ws` helpers are reused by FR6.

**External Dependencies:**
- None.

### File Structure

```
em-workflow/
├── references/
│   └── question-resolution.md        # FR1, FR2, FR3
└── skills/
    └── develop/
        └── SKILL.md                  # FR4
tests/
├── test_question_resolution_doc.py   # FR5
└── test_develop_tier_staged_procedure.py  # FR6
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-consult-output-scratchpad/**`
- `test-docs/codex-consult-output-scratchpad/**`

`feature-docs/codex-consult-output-scratchpad/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-consult-output-scratchpad/**` covers
`test-docs/codex-consult-output-scratchpad/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-consult-output-scratchpad/` directory at all; the declared
`test-docs/codex-consult-output-scratchpad/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (covers AC-1, AC-2 → FR1, FR2): question-resolution.md: extract the region between '2. **Wrapper invocation.**' and '3. **One turn per call.**' and collapse its whitespace. Assert that it contains the scratchpad-placement phrase and the project-root prohibition phrase.
- [ ] **TS-2** (covers AC-5 → FR5, FR6): question-resolution.md negative twin: run the TS-1 matcher against a synthetic copy of the pre-fix step 2 text. Assert that it does not match.
- [ ] **TS-3** (covers AC-4 → FR4): SKILL.md: within `TIER_SECTION`, slice from '3. **Codex 事前調査**' to '4. **no-work 停止**'. Using `_contains`, assert that it names `references/question-resolution.md` and the Codex consultation procedure's step 2. Assert that it does not contain the question-resolution.md rule sentence verbatim.
- [ ] **TS-4** (covers AC-5 → FR5, FR6): SKILL.md negative twin: run the TS-3 citation matcher against a synthetic copy of the pre-fix step 3 text. Assert that it does not match.
- [ ] **TS-5** (covers AC-3, AC-6 → FR3, NFR2, NFR3): Retention: these existing tests still pass. In question-resolution.md: the wrapper-invocation pins and the document-wide negative pins. In `test_develop_tier_staged_procedure.py`: the call-order, AC-6 forbidden-token and locator tests.

**Run command**: `python3 -m unittest discover -s tests`

### Integration Tests

- None.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases

- [ ] The rule covers turns on both harness entries (codex and litellm), including turns after a mid-consultation move from codex to litellm.
- [ ] The rule covers both stdout and stderr files (the reported case left `consult1.out` and `consult1.err`).
- [ ] Non-packet gates in `references/batch-mode.md` (including the per-command approval fallback) reach step 2 by citing the procedure, so they are covered without a separate edit.
- [ ] When the output is not saved to a file at all, the rule imposes nothing.
- [ ] The develop tier pre-survey may save its JSON output. The cited rule applies to that saved file as well.

### Performance Tests

- Not applicable.

## Security Considerations

- **Data Protection:** The added text contains no Notion URL and no absolute path under the user's home directory (NFR4).
- Authentication, authorization, input validation, XSS, SQL injection and CSRF: not applicable.

## Error Handling

Not applicable.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 through AC-6 are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None.

## References

- Codex consultation procedure: `em-workflow/references/question-resolution.md`
- develop skill, tier decision: `em-workflow/skills/develop/SKILL.md`
- Batch-mode non-packet gates: `em-workflow/references/batch-mode.md`
