# Feature: build-format-both-excluded-tests

## Overview

When both the approved build command and the approved format command fall
outside the cd-prefix form, the implementer procedure documents state which
rule decides the `tests` field of the implementer report. A new document
test verifies that statement.

## Objectives

- State in the procedure documents which rule decides the implementer
  report's `tests` when both the approved build and format commands fall
  outside the cd-prefix form.
- Add a document test that verifies that statement.

## Acceptance Criteria

- [ ] AC1: Step 3 of `em-workflow/agents/implementer.md` contains exactly one
  sentence stating that not running the format command does not override a
  `tests: "fail"` decided by another rule, and that sentence cites the case
  where the build command also falls outside the cd-prefix form (FR1, FR2).
- [ ] AC2: The "Command execution gate" section of
  `em-workflow/skills/worktree-task-workflow/SKILL.md` contains exactly one
  sentence with the same statement as AC1 (FR1, FR2).
- [ ] AC3: The existing sentences about the format, build and test commands,
  the deny bullet of the gate section, and the field set of the Step 7 JSON
  block are unchanged (FR2).
- [ ] AC4: A document test checks the case where build and format both fall
  outside the cd-prefix form, and its matcher is paired with false-sentence
  cases (FR3).
- [ ] AC5: The tests listed in NFR1 pass without modification, and
  `python3 -m unittest discover -s tests` passes in full (NFR1-NFR3, NFR5).
- [ ] AC6: The plugin version is unchanged (NFR4).

## Technical Requirements

### Functional Requirements

- **FR1:** Not running the format command does not override another rule's
  `tests: "fail"`. Add to Step 3 ("Step 3: Verify the worktree") of
  `em-workflow/agents/implementer.md` and to the "Command execution gate"
  section of `em-workflow/skills/worktree-task-workflow/SKILL.md` a statement
  that not running the format command does not override a `tests: "fail"`
  that another rule decides. Within the same sentence, cite as an example
  the case where the build command also falls outside the cd-prefix form.
- **FR2:** Add as a separate sentence. The FR1 statement is added as a
  sentence separate from the existing sentence about the format command.
  The existing sentences about the format, build and test commands, and the
  deny bullet of the gate section, are not changed. The handling of
  `status` (merged / failed) and the field set of the Step 7 JSON block are
  not changed either.
- **FR3:** Document test. Add a document test under `tests/`. It extracts
  the two sections by heading, normalizes whitespace, matches per sentence,
  and confirms that each of the two sections contains exactly one FR1
  sentence. The matcher requires the following three within the same
  sentence: the format command not being run; not overriding a
  `tests: "fail"` decided by another rule; the case where the build command
  also falls outside the cd-prefix form. A missing heading fails the test.
  The matcher is paired with sentences it must accept and false sentences it
  must reject. The false sentences include at least these three:
  - a sentence stating that even when build and format both fall outside
    the cd-prefix form, `tests` follows the result of the test command;
  - a sentence that does not mention the build case;
  - the existing format sentence itself.

### Non-Functional Requirements

- **NFR1 - Existing document tests pass unchanged:** The following tests
  pass without modification:
  `tests/test_implementer_cd_prefix_build_format_docs.py`,
  `tests/test_implementer_cd_prefix_exclusion_docs.py`,
  `tests/test_cd_prefix_operator_exclusion_docs.py`,
  `tests/test_cd_prefix_exception_docs.py`,
  `tests/test_implementer_cd_chain_docs.py`,
  `tests/test_worktree_skill_instruction_source.py`,
  `tests/test_implementer_untrusted_data_rule.py`.
- **NFR2 - No match against existing matchers:** The new sentence does not
  match any existing matcher. To that end:
  - (a) Do not put `project_commands.format` and
    "the report sets `tests: \"fail\"`" in the same sentence (this would
    violate `test_ac2_no_sentence_sets_fail_for_the_format_case`).
  - (b) Do not include all of the phrases `find_format_sentences` requires
    (the format sentence stays exactly one).
  - (c) Do not include all of the phrases `find_build_sentences` requires
    (the build sentence stays exactly one).
  - (d) Do not include the full set of phrases `find_test_command_sentences`
    requires (`project_commands.test`, `tests: "fail"`, `notes`, "not run",
    "baseline", "does not cover").
  - (e) Do not use "Run nothing, set" in the gate section.
  - (f) Do not write `$'`, `$"`, `${` (except `${CLAUDE_PLUGIN_ROOT}`) or `#`
    in either section.
  - (g) Do not include, when compared in lowercase, "unclosed",
    "trailing backslash", "parenthes", "command substitution" or "backtick".
- **NFR3 - Existing wording constraints:** Neither document contains a
  sentence that has both `separate` and `cd` (judged at word boundaries), a
  sentence that has "chain" (substring match), `&&` and never / not / don't
  together, or a sentence containing "may reset" / "may have reset". Step 3
  does not contain "Step 4". The gate section does not contain
  "Untrusted input", and does not contain "byte", "identical to" or
  "equal to the line" other than "(byte-for-byte)". The fixed existing
  sentences in Step 3 and in the gate section each remain exactly one
  sentence.
- **NFR4 - Version unchanged:** The plugin version is not changed.
- **NFR5 - Test execution:** Tests use only the standard library `unittest`,
  and `python3 -m unittest discover -s tests` passes in full.

## Implementation Approach

### Files Changed

- `em-workflow/agents/implementer.md` — Step 3 ("Step 3: Verify the
  worktree"): add the FR1 sentence as a separate sentence (FR1, FR2).
- `em-workflow/skills/worktree-task-workflow/SKILL.md` — "Command execution
  gate" section: add the FR1 sentence as a separate sentence (FR1, FR2).
- `tests/` — add a new document test module (FR3). Existing modules are not
  modified (NFR1).

### Dependencies

**Internal Dependencies:**
- Existing document tests listed in NFR1 and their matchers
  (`find_format_sentences`, `find_build_sentences`,
  `find_test_command_sentences`,
  `test_ac2_no_sentence_sets_fail_for_the_format_case`): the new sentence
  must not match them (NFR2, NFR3).

**External Dependencies:**
- Python standard library `unittest` only (NFR5).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1: Step 3 of implementer.md and the gate section of SKILL.md each
  contain exactly one new sentence (AC1, AC2).
- [ ] TS2: The matcher does not match the false sentence stating that even
  when build and format both fall outside the cd-prefix form, `tests`
  follows the result of the test command (AC4).
- [ ] TS3: The matcher does not match the false sentence that does not
  mention the build case, nor the existing format sentence (the same
  wording as GOOD_FORMAT) (AC4).
- [ ] TS4: For a document whose heading name has been changed, section
  extraction fails; the test never passes with an empty string (FR3).
- [ ] TS5: `python3 -m unittest discover -s tests` passes in full, including
  the seven modules in NFR1 (AC3, AC5).

### Integration Tests

None.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] Build, format and test all fall outside the cd-prefix form: the build
  rule and the test rule make `tests` "fail". Not running format does not
  override this.
- [ ] Format falls outside the cd-prefix form and the hook denies another
  command: the deny rule makes `tests` "fail". Not running format does not
  override this.
- [ ] Only format falls outside the cd-prefix form: per the existing format
  sentence, `tests` follows the result of the test command.
- [ ] The build / format command is an empty string: that command does not
  exist, so FR1 does not apply.

## Assumptions

- **A1:** The existing format sentence (the sentence containing
  "the report's `tests` follows the result of the test command") is kept
  unchanged. Because `find_format_sentences` rejects that sentence when
  "the report sets `tests: \"fail\"`" appears in it, the new statement is a
  separate sentence.
- **A2:** The document test is added as a new module under `tests/`.
  Existing modules are not modified, per NFR1.
- **A3:** The only required example of "another rule" in the new sentence is
  the case where the build command falls outside the cd-prefix form.
  Whether to add other examples, such as a hook deny, is left to the writer
  within the wording constraints (NFR2, NFR3).
- **A4:** The design step is skipped.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1-AC6 are satisfied

## Open Questions

None.
