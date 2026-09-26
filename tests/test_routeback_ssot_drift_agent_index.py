"""Tests for task0001 (routeback-ssot-drift): document-contract tests for
the workflow-schema.md agents.jsonl paragraph (section A of the task plan)
and the queue_agent_index.py module docstring (section B).

Covers task0001 Acceptance Criteria
(feature-docs/routeback-ssot-drift/tasks/task0001.md):

- AC-1 (FR1): within the whitespace-normalized agents.jsonl paragraph,
  `queue_taskstop_net.py`, `queue_failure_net.py`, "Orchestrator-side read"
  and an orphan-recovery reference are present together with a citation of
  `implement-phase.md`, and the sole-reader sentence form is absent.
- AC-2 (FR2): "exists solely to make a stop resolvable back to a task" is
  absent from workflow-schema.md, and the paragraph states that the index
  resolves a stop or a recovery check back to a task and its worktree.
- AC-3 (FR3): "its absence only degrades the stop-tool recorder to a
  no-op" is absent from workflow-schema.md; the paragraph states that an
  absent or stale index makes the Orchestrator-side lookup unresolvable
  and leads to Residual ending in the gate-rejected terminal, states that
  orphan recovery stops without naming the `no-agent-entry` code, and cites the I.2.b Recovery / Residual block;
  `stale-agent-entry` remains absent from the file.
- AC-4 (FR4): the paragraph names the stop-side rule with owners
  `queue_taskstop_net.py` and IMPLEMENTATION.md's Agent index contract,
  and the Orchestrator-side read with owner `implement-phase.md`; it
  contains "two or more distinct (agents.jsonl, task) pairs" and "the
  selected entry names no usable candidate", and states that the two
  "ambiguous" conditions are different.
- AC-5 (FR5): the queue_agent_index.py module docstring does not contain
  "Its only job is to record", names the three readers of AC-1 and the
  purpose of AC-2. (The "diff confined to the module docstring" half of
  AC-5, and AC-7's file-set confinement, are checked by inspecting the
  diff against the task base rather than by a unit test here -- recorded
  in this task's own tests.yaml, per Test Notes.)
- AC-6 (FR8, FR9): covered by
  tests/test_implement_routeback_gate.py's TestPluginVersionBumpedInLockstep
  (task0001's Scope names that class, not this module).
- AC-7 (NFR1, NFR2, NFR3): the full suite passing and every A.5 retained
  phrase surviving are this module's own retention tests below, plus the
  full-suite run recorded in this task's tests.yaml.

This is a documentation task (Test Notes: unit-level document-contract
assertions). Content assertions compare against a whitespace-normalized
copy of the paragraph/docstring (IMPLEMENTATION.md Conventions: Text
normalization) so line-wrap choices in the prose never make an assertion
brittle. Presence assertions for new wording are scoped to the paragraph
or docstring they are about; absence assertions for removed phrases run
over the whole file/source (IMPLEMENTATION.md Conventions: Assertion
scope).

Pre-change excerpts below are copied verbatim from this task's base commit
(c7dadf91, "docs(routeback-ssot-drift): implement phase start"), before
this task edited anything, via `git show HEAD:<path>`. They are used only
for the negative proofs required by IMPLEMENTATION.md Conventions.

Matcher -> negative-proof inventory:

- test_names_stop_tool_recorder, test_names_failure_net_fallback_condition,
  test_names_orchestrator_side_read_and_orphan_recovery_reference,
  test_cites_implement_phase_md_for_readers -> new wording ->
  TestNegativeProofs.test_new_reader_wording_absent_from_pre_change_paragraph
- test_old_sole_reader_form_absent -> absence of removed phrase ->
  TestNegativeProofs.test_old_sole_reader_form_present_in_pre_change_paragraph
  (non-vacuity guard)
- test_new_purpose_phrase_present -> new wording ->
  TestNegativeProofs.test_new_purpose_phrase_absent_from_pre_change_paragraph
- test_old_purpose_phrase_absent_from_file -> absence of removed phrase ->
  TestNegativeProofs.test_old_purpose_phrase_present_in_pre_change_paragraph
  (non-vacuity guard)
- test_new_absence_orchestrator_unresolvable_present,
  test_new_absence_residual_outcome_present, test_no_agent_entry_token_present,
  test_cites_i2b_recovery_residual_block_for_absence_behavior -> new wording
  -> TestNegativeProofs.test_new_absence_wording_absent_from_pre_change_paragraph
- test_old_absence_degrades_phrase_absent_from_file -> absence of removed
  phrase -> TestNegativeProofs.test_old_absence_degrades_phrase_present_in_pre_change_paragraph
  (non-vacuity guard)
- test_stale_agent_entry_token_absent_from_file -> regression guard
  (existing coverage: tests/test_implement_routeback_gate.py's
  TestI2bOrphanRecoveryD7Binding also asserts this; this test adds the
  same proof scoped to this task's own module), no separate proof needed
- test_stop_side_owners_present, test_stop_side_ambiguous_definition_present,
  test_orchestrator_side_owner_present,
  test_orchestrator_side_ambiguous_definition_present,
  test_two_ambiguous_conditions_stated_as_different -> new wording ->
  TestNegativeProofs.test_two_read_rule_wording_absent_from_pre_change_paragraph
- test_opening_clause_retained, test_no_status_semantics_phrase_retained,
  test_session_id_exception_phrase_retained,
  test_i2b_recovery_residual_citation_form_retained_verbatim -> RETENTION
  matcher -> TestNegativeProofs's matching
  test_*_retention_matcher_is_not_vacuous
- test_module_docstring_old_only_job_phrase_absent -> absence of removed
  phrase -> TestNegativeProofs.test_old_only_job_phrase_present_in_pre_change_docstring
  (non-vacuity guard)
- test_module_docstring_names_readers, test_module_docstring_states_purpose,
  test_module_docstring_retains_mapping_description -> new wording (first
  two) / retention (third) ->
  TestNegativeProofs.test_new_docstring_wording_absent_from_pre_change_docstring
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_SCHEMA_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "workflow-schema.md"
)
AGENT_INDEX_HOOK_PATH = REPO_ROOT / "em-workflow" / "hooks" / "queue_agent_index.py"

AGENTS_JSONL_OPENING_CLAUSE = (
    "The same worktree-root directory also holds `agents.jsonl`, the agent"
)
STATUS_SEMANTICS_HEADING = "## Status semantics"


def _read_workflow_schema():
    return WORKFLOW_SCHEMA_PATH.read_text(encoding="utf-8")


def _read_agent_index_hook_source():
    return AGENT_INDEX_HOOK_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so line wrapping never breaks an assertion
    (IMPLEMENTATION.md Conventions: Text normalization)."""
    return re.sub(r"\s+", " ", text)


def _agents_jsonl_paragraph(full_text):
    """Slice the agents.jsonl paragraph: from the opening clause up to the
    `## Status semantics` heading (task0001 Design D)."""
    start = full_text.index(AGENTS_JSONL_OPENING_CLAUSE)
    end = full_text.index(STATUS_SEMANTICS_HEADING, start)
    return full_text[start:end]


def _module_docstring(source_text):
    """Read the module docstring from the hook's source text, without
    importing or running the hook (task0001 Design D)."""
    first = source_text.index('"""')
    second = source_text.index('"""', first + 3)
    return source_text[first + 3 : second]


# --- Pre-change excerpts (verbatim, base commit c7dadf91, before this
# task's edit; `git show HEAD:<path>`). Used only for negative proofs. ---

PRE_CHANGE_AGENTS_JSONL_PARAGRAPH = (
    "The same worktree-root directory also holds `agents.jsonl`, the agent\n"
    "index — a separate diagnostic mapping, per launch, from a candidate list of\n"
    "harness agent-identifier strings (the exact identifier field the harness's\n"
    "launch response carries is unverified, so `queue_agent_index.py` records\n"
    "every candidate it can recover rather than a single one) to the\n"
    "em-workflow task identity that launched it, written by\n"
    "`queue_agent_index.py` at launch and read by `queue_taskstop_net.py` at\n"
    "stop. It is NOT part of the journal contract above and must never be\n"
    "treated as a second authoritative state file: it carries no status\n"
    "semantics of its own, may be absent or stale, and its absence only\n"
    "degrades the stop-tool recorder to a no-op. The sole exception to \"no\n"
    "status semantics of its own\" is the session identity (`session_id`) it\n"
    "also carries per launch:\n"
    "`em-workflow/references/implement-phase.md`'s I.2.b Recovery / Residual\n"
    "block (cited here, not restated) reads it — a comparison value only, never\n"
    "a status value and never a match candidate on the stop side — to judge\n"
    "whether the launching session is provably gone. `journal.jsonl` alone is\n"
    "the authoritative raw-event record; `agents.jsonl` exists solely to make a\n"
    "stop resolvable back to a task. Full contract (candidate-list format,\n"
    "matching rule, staleness/supersede rule): IMPLEMENTATION.md's Agent index\n"
    "contract."
)

PRE_CHANGE_DOCSTRING_PARAGRAPH = (
    "Its only job is to record, in the feature's agent index (`agents.jsonl`,\n"
    "sibling of `journal.jsonl`), the mapping from the harness's own agent\n"
    "identifier to the em-workflow task it just launched, so that a later\n"
    "`TaskStop` can be resolved back to a task and its journal (Agent index\n"
    "contract, IMPLEMENTATION.md). It never writes `journal.jsonl`, never decides\n"
    "anything about task state, and never blocks the tool call -- it is\n"
    "diagnostic plumbing only (IMPLEMENTATION.md, Layer Structure)."
)

# --- Pinned literals (each defined once, referenced by name). ---

# AC-1 / FR1: readers.
READER_STOP_TOOL_RECORDER = "`queue_taskstop_net.py`"
READER_FAILURE_NET = "`queue_failure_net.py`"
FAILURE_NET_FALLBACK_CONDITION_PHRASE = (
    "used only when no assignment block is found"
)
ORCHESTRATOR_SIDE_READ_LABEL = "Orchestrator-side read"
ORPHAN_RECOVERY_REFERENCE_PHRASE = "orphan-recovery evidence chain"
IMPLEMENT_PHASE_CITATION = "implement-phase.md"
OLD_SOLE_READER_FORM = "read by `queue_taskstop_net.py` at stop."

# AC-2 / FR2: purpose.
NEW_PURPOSE_PHRASE = (
    "resolves a stop or a recovery check back to a task and its worktree"
)
OLD_PURPOSE_PHRASE = "exists solely to make a stop resolvable back to a task"

# AC-3 / FR3: absence behavior.
OLD_ABSENCE_DEGRADES_PHRASE = (
    "its absence only degrades the stop-tool recorder to a no-op"
)
NEW_ABSENCE_ORCHESTRATOR_UNRESOLVABLE_PHRASE = (
    "makes the Orchestrator-side lookup unresolvable"
)
NEW_ABSENCE_RESIDUAL_OUTCOME_PHRASE = (
    "leads to Residual (journal unchanged, task stays in-flight, "
    "route-back gate blocks, gate-rejected terminal)"
)
NO_AGENT_ENTRY_TOKEN = "`no-agent-entry`"
ORPHAN_RECOVERY_STOP_PHRASE = (
    "when the index has no entry for the task, orphan recovery stops"
)
I2B_RECOVERY_RESIDUAL_CITATION = (
    "em-workflow/references/implement-phase.md`'s I.2.b Recovery / "
    "Residual block"
)
STALE_AGENT_ENTRY_TOKEN = "stale-agent-entry"

# AC-4 / FR4: two read rules.
STOP_SIDE_OWNERS_PHRASE = (
    "owned by `queue_taskstop_net.py` and IMPLEMENTATION.md's Agent index "
    "contract"
)
STOP_SIDE_AMBIGUOUS_DEFINITION = "two or more distinct (agents.jsonl, task) pairs"
ORCHESTRATOR_SIDE_OWNER_PHRASE = (
    "owned by `implement-phase.md`'s Orchestrator-side read"
)
ORCHESTRATOR_SIDE_AMBIGUOUS_DEFINITION = "the selected entry names no usable candidate"
AMBIGUOUS_CONDITIONS_DIFFERENT_PHRASE = '"ambiguous" conditions are different'

# NFR2: retained verbatim (task0001 Design A.5).
RETAINED_OPENING_CLAUSE_PHRASE = AGENTS_JSONL_OPENING_CLAUSE
RETAINED_NO_STATUS_SEMANTICS_PHRASE = (
    "it carries no status semantics of its own, may be absent or stale"
)
RETAINED_SESSION_ID_EXCEPTION_PHRASE = (
    'The sole exception to "no status semantics of its own" is the '
    "session identity"
)

# AC-5 / FR5: docstring.
OLD_DOCSTRING_ONLY_JOB_PHRASE = "Its only job is to record"
DOCSTRING_MAPPING_PHRASE = (
    "the mapping from the harness's own agent identifier to the "
    "em-workflow task it just launched"
)


class TestAgentsJsonlParagraphReaders(unittest.TestCase):
    """AC-1 (FR1): the paragraph names every reader implement-phase.md
    defines, citing it instead of restating its rules, and the sole-reader
    sentence form no longer appears."""

    @classmethod
    def setUpClass(cls):
        cls.paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )
        cls.whole_file = _normalize_ws(_read_workflow_schema())

    def test_names_stop_tool_recorder(self):
        self.assertIn(READER_STOP_TOOL_RECORDER, self.paragraph)

    def test_names_failure_net_fallback_condition(self):
        self.assertIn(READER_FAILURE_NET, self.paragraph)
        self.assertIn(FAILURE_NET_FALLBACK_CONDITION_PHRASE, self.paragraph)

    def test_names_orchestrator_side_read_and_orphan_recovery_reference(self):
        self.assertIn(ORCHESTRATOR_SIDE_READ_LABEL, self.paragraph)
        self.assertIn(ORPHAN_RECOVERY_REFERENCE_PHRASE, self.paragraph)

    def test_cites_implement_phase_md_for_readers(self):
        self.assertIn(IMPLEMENT_PHASE_CITATION, self.paragraph)

    def test_old_sole_reader_form_absent(self):
        self.assertNotIn(OLD_SOLE_READER_FORM, self.whole_file)


class TestAgentsJsonlParagraphPurpose(unittest.TestCase):
    """AC-2 (FR2): the index resolves a stop or a recovery check back to a
    task and its worktree; the old sole-purpose-is-a-stop phrasing is
    gone."""

    @classmethod
    def setUpClass(cls):
        cls.paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )
        cls.whole_file = _normalize_ws(_read_workflow_schema())

    def test_new_purpose_phrase_present(self):
        self.assertIn(NEW_PURPOSE_PHRASE, self.paragraph)

    def test_old_purpose_phrase_absent_from_file(self):
        self.assertNotIn(OLD_PURPOSE_PHRASE, self.whole_file)


class TestAgentsJsonlParagraphAbsenceBehavior(unittest.TestCase):
    """AC-3 (FR3): an absent or stale index makes the Orchestrator-side
    lookup unresolvable and leads to Residual ending in the gate-rejected
    terminal; orphan recovery stops (the `no-agent-entry` code itself stays
    out of the file); the old
    stop-tool-recorder-only degradation phrasing is gone; `stale-agent-entry`
    stays out of the file."""

    @classmethod
    def setUpClass(cls):
        cls.paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )
        cls.whole_file = _normalize_ws(_read_workflow_schema())

    def test_old_absence_degrades_phrase_absent_from_file(self):
        self.assertNotIn(OLD_ABSENCE_DEGRADES_PHRASE, self.whole_file)

    def test_new_absence_orchestrator_unresolvable_present(self):
        self.assertIn(
            NEW_ABSENCE_ORCHESTRATOR_UNRESOLVABLE_PHRASE, self.paragraph
        )

    def test_new_absence_residual_outcome_present(self):
        self.assertIn(NEW_ABSENCE_RESIDUAL_OUTCOME_PHRASE, self.paragraph)

    def test_orphan_recovery_stop_stated_without_reason_code(self):
        # Residual reason codes live only in implement-phase.md; the
        # schema states the stop without naming the code.
        self.assertIn(ORPHAN_RECOVERY_STOP_PHRASE, self.paragraph)
        self.assertNotIn(NO_AGENT_ENTRY_TOKEN, self.whole_file)

    def test_cites_i2b_recovery_residual_block_for_absence_behavior(self):
        self.assertIn(I2B_RECOVERY_RESIDUAL_CITATION, self.paragraph)

    def test_stale_agent_entry_token_absent_from_file(self):
        self.assertNotIn(STALE_AGENT_ENTRY_TOKEN, self.whole_file)


class TestAgentsJsonlParagraphTwoReadRules(unittest.TestCase):
    """AC-4 (FR4): the paragraph names both read rules with their owners,
    and states that their "ambiguous" conditions are different
    conditions."""

    @classmethod
    def setUpClass(cls):
        cls.paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )

    def test_stop_side_owners_present(self):
        self.assertIn(STOP_SIDE_OWNERS_PHRASE, self.paragraph)

    def test_stop_side_ambiguous_definition_present(self):
        self.assertIn(STOP_SIDE_AMBIGUOUS_DEFINITION, self.paragraph)

    def test_orchestrator_side_owner_present(self):
        self.assertIn(ORCHESTRATOR_SIDE_OWNER_PHRASE, self.paragraph)

    def test_orchestrator_side_ambiguous_definition_present(self):
        self.assertIn(ORCHESTRATOR_SIDE_AMBIGUOUS_DEFINITION, self.paragraph)

    def test_two_ambiguous_conditions_stated_as_different(self):
        self.assertIn(AMBIGUOUS_CONDITIONS_DIFFERENT_PHRASE, self.paragraph)


class TestAgentsJsonlParagraphRetainedWording(unittest.TestCase):
    """NFR2 (task0001 Design A.5): these phrases survive the rewrite
    exactly (whitespace normalized)."""

    @classmethod
    def setUpClass(cls):
        cls.paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )

    def test_opening_clause_retained(self):
        self.assertIn(RETAINED_OPENING_CLAUSE_PHRASE, self.paragraph)

    def test_no_status_semantics_phrase_retained(self):
        self.assertIn(RETAINED_NO_STATUS_SEMANTICS_PHRASE, self.paragraph)

    def test_session_id_exception_phrase_retained(self):
        self.assertIn(RETAINED_SESSION_ID_EXCEPTION_PHRASE, self.paragraph)

    def test_i2b_recovery_residual_citation_form_retained_verbatim(self):
        self.assertIn(I2B_RECOVERY_RESIDUAL_CITATION, self.paragraph)


class TestModuleDocstringContent(unittest.TestCase):
    """AC-5 (FR5): the module docstring no longer claims the index's only
    job is to record the mapping; it names the same three readers as AC-1
    and the same purpose as AC-2, citing implement-phase.md /
    workflow-schema.md rather than restating their rules."""

    @classmethod
    def setUpClass(cls):
        cls.docstring = _normalize_ws(
            _module_docstring(_read_agent_index_hook_source())
        )

    def test_module_docstring_old_only_job_phrase_absent(self):
        self.assertNotIn(OLD_DOCSTRING_ONLY_JOB_PHRASE, self.docstring)

    def test_module_docstring_names_readers(self):
        self.assertIn(READER_STOP_TOOL_RECORDER, self.docstring)
        self.assertIn(READER_FAILURE_NET, self.docstring)
        self.assertIn(ORCHESTRATOR_SIDE_READ_LABEL, self.docstring)

    def test_module_docstring_states_purpose(self):
        self.assertIn(NEW_PURPOSE_PHRASE, self.docstring)

    def test_module_docstring_retains_mapping_description(self):
        self.assertIn(DOCSTRING_MAPPING_PHRASE, self.docstring)


class TestNegativeProofs(unittest.TestCase):
    """Proof that the matchers above fail meaningfully, per the
    tdd-testing discipline (a test that can never fail is not a test),
    demonstrated against this task's own pre-change excerpts
    (IMPLEMENTATION.md Conventions: Negative proofs)."""

    def test_old_sole_reader_form_present_in_pre_change_paragraph(self):
        # non-vacuity guard: proves the excerpt genuinely contains the
        # removed phrase.
        pre = _normalize_ws(PRE_CHANGE_AGENTS_JSONL_PARAGRAPH)
        self.assertIn(OLD_SOLE_READER_FORM, pre)

    def test_new_reader_wording_absent_from_pre_change_paragraph(self):
        pre = _normalize_ws(PRE_CHANGE_AGENTS_JSONL_PARAGRAPH)
        self.assertNotIn(READER_FAILURE_NET, pre)
        self.assertNotIn(FAILURE_NET_FALLBACK_CONDITION_PHRASE, pre)
        self.assertNotIn(ORCHESTRATOR_SIDE_READ_LABEL, pre)
        self.assertNotIn(ORPHAN_RECOVERY_REFERENCE_PHRASE, pre)

    def test_old_purpose_phrase_present_in_pre_change_paragraph(self):
        pre = _normalize_ws(PRE_CHANGE_AGENTS_JSONL_PARAGRAPH)
        self.assertIn(OLD_PURPOSE_PHRASE, pre)

    def test_new_purpose_phrase_absent_from_pre_change_paragraph(self):
        pre = _normalize_ws(PRE_CHANGE_AGENTS_JSONL_PARAGRAPH)
        self.assertNotIn(NEW_PURPOSE_PHRASE, pre)

    def test_old_absence_degrades_phrase_present_in_pre_change_paragraph(self):
        pre = _normalize_ws(PRE_CHANGE_AGENTS_JSONL_PARAGRAPH)
        self.assertIn(OLD_ABSENCE_DEGRADES_PHRASE, pre)

    def test_new_absence_wording_absent_from_pre_change_paragraph(self):
        pre = _normalize_ws(PRE_CHANGE_AGENTS_JSONL_PARAGRAPH)
        self.assertNotIn(NEW_ABSENCE_ORCHESTRATOR_UNRESOLVABLE_PHRASE, pre)
        self.assertNotIn(NEW_ABSENCE_RESIDUAL_OUTCOME_PHRASE, pre)
        self.assertNotIn(NO_AGENT_ENTRY_TOKEN, pre)

    def test_two_read_rule_wording_absent_from_pre_change_paragraph(self):
        pre = _normalize_ws(PRE_CHANGE_AGENTS_JSONL_PARAGRAPH)
        self.assertNotIn(STOP_SIDE_OWNERS_PHRASE, pre)
        self.assertNotIn(STOP_SIDE_AMBIGUOUS_DEFINITION, pre)
        self.assertNotIn(ORCHESTRATOR_SIDE_OWNER_PHRASE, pre)
        self.assertNotIn(ORCHESTRATOR_SIDE_AMBIGUOUS_DEFINITION, pre)
        self.assertNotIn(AMBIGUOUS_CONDITIONS_DIFFERENT_PHRASE, pre)

    def test_opening_clause_retention_matcher_is_not_vacuous(self):
        paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )
        stripped = paragraph.replace(RETAINED_OPENING_CLAUSE_PHRASE, "")
        self.assertNotIn(RETAINED_OPENING_CLAUSE_PHRASE, stripped)

    def test_no_status_semantics_retention_matcher_is_not_vacuous(self):
        paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )
        stripped = paragraph.replace(RETAINED_NO_STATUS_SEMANTICS_PHRASE, "")
        self.assertNotIn(RETAINED_NO_STATUS_SEMANTICS_PHRASE, stripped)

    def test_session_id_exception_retention_matcher_is_not_vacuous(self):
        paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )
        stripped = paragraph.replace(RETAINED_SESSION_ID_EXCEPTION_PHRASE, "")
        self.assertNotIn(RETAINED_SESSION_ID_EXCEPTION_PHRASE, stripped)

    def test_i2b_citation_retention_matcher_is_not_vacuous(self):
        paragraph = _normalize_ws(
            _agents_jsonl_paragraph(_read_workflow_schema())
        )
        stripped = paragraph.replace(I2B_RECOVERY_RESIDUAL_CITATION, "")
        self.assertNotIn(I2B_RECOVERY_RESIDUAL_CITATION, stripped)

    def test_old_only_job_phrase_present_in_pre_change_docstring(self):
        pre = _normalize_ws(PRE_CHANGE_DOCSTRING_PARAGRAPH)
        self.assertIn(OLD_DOCSTRING_ONLY_JOB_PHRASE, pre)

    def test_new_docstring_wording_absent_from_pre_change_docstring(self):
        pre = _normalize_ws(PRE_CHANGE_DOCSTRING_PARAGRAPH)
        self.assertNotIn(READER_FAILURE_NET, pre)
        self.assertNotIn(ORCHESTRATOR_SIDE_READ_LABEL, pre)
        self.assertNotIn(NEW_PURPOSE_PHRASE, pre)


if __name__ == "__main__":
    unittest.main()
