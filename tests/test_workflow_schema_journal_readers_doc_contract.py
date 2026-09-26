"""Tests for task0005 (routeback-deferred-findings): workflow-schema.md
records `merge-unverified` as a third additive value of the journal's
`failed` reason field without adding a writer, states the complete
`agents.jsonl` reader set and what an absent or stale index costs, and
keeps its Status semantics unconditional.

Covers task0005 Acceptance Criteria
(feature-docs/routeback-deferred-findings/tasks/task0005.md):

- AC-1 (FR7, NFR1): the writer-set paragraph names `merge-unverified` as a
  third additive value of the existing `failed` reason field, written by
  the same helper, invoked only from the I.2.b step 1 ancestor-check
  branch, adding no writer; the backtick-quoted .py/.sh names between "Its
  writer set is unambiguous" and "outside this one exception" equal
  exactly the five writers.
- AC-2 (FR7): the paragraph no longer states the helper is invoked only by
  the orphan-recovery attempt; the four pre-existing phrases still match;
  the `failed_kind` definition is byte-identical to its pre-change
  capture.
- AC-3 (FR6): the Status semantics bullet still states the unconditional
  resolution rule and carries no carve-out clause.
- AC-4 (FR8): the agents.jsonl paragraph names all four readers and states
  the not-live-determination cost for a stale `launched` task, citing
  implement-phase.md I.2.b, without restating the Orchestrator-side read
  rule's own wording.
- AC-5 (FR8): the three narrow pre-change phrases (single reader, narrow
  absence cost, narrow purpose) are absent, each proven against a
  verbatim pre-change sample with a retained-anchor guard; the two R2
  item 4 phrases still match.
- AC-6 (NFR4): workflow-schema.md contains none of the sixteen SC6
  residual reason codes.
- AC-7 (FR10, NFR8): this module imports only the standard library; the
  existing schema pins in test_implement_routeback_gate.py and
  test_stale_launched_doc_contract.py pass unmodified; the full suite
  passes.

Convention (IMPLEMENTATION.md Convention 6): standard library only,
whitespace-normalized matching unless byte identity is the point,
module-level constants for every literal read by its positive test and by
its negative proof, each absence assertion paired with a negative proof
against a verbatim pre-change sample plus a retained-anchor guard.
"""

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
WORKFLOW_SCHEMA_PATH = PLUGIN_ROOT / "references" / "workflow-schema.md"


def _read_workflow_schema():
    return WORKFLOW_SCHEMA_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def _slice(text, start_marker, end_marker, start_from=0):
    start = text.index(start_marker, start_from)
    end = text.index(end_marker, start)
    return text[start:end]


# ===========================================================================
# AC-1: writer-set paragraph names `merge-unverified`; writer set unchanged
# ===========================================================================

WRITER_SET_START_MARKER = "Its writer set is unambiguous"
WRITER_SET_END_MARKER = "outside this one exception"

EXPECTED_WRITER_NAMES = frozenset(
    {
        "merge-task.sh",
        "queue_launch_guard.py",
        "queue_failure_net.py",
        "queue_taskstop_net.py",
        "journal-append-failed.py",
    }
)

_BACKTICK_NAME_RE = re.compile(r"`([\w./-]+)`")


def _writer_set_slice(text):
    return _slice(text, WRITER_SET_START_MARKER, WRITER_SET_END_MARKER) + (
        WRITER_SET_END_MARKER
    )


def _extract_script_names(slice_text):
    names = set()
    for match in _BACKTICK_NAME_RE.findall(slice_text):
        basename = match.rsplit("/", 1)[-1]
        if basename.endswith(".py") or basename.endswith(".sh"):
            names.add(basename)
    return names


MERGE_UNVERIFIED_SENTENCE_PHRASE = (
    "The same helper, invoked only from "
    "`em-workflow/references/implement-phase.md`'s I.2.b step 1 "
    "ancestor-check branch (cited here, not restated), also writes "
    "`failed` with reason `merge-unverified`, a third additive value of "
    "the existing `failed` reason field, adding no writer."
)

MERGE_UNVERIFIED_CITATION_PHRASE = (
    "`em-workflow/references/implement-phase.md`'s I.2.b step 1 "
    "ancestor-check branch"
)

MERGE_UNVERIFIED_ADDITIVE_PHRASE = (
    "a third additive value of the existing `failed` reason field"
)


class TestWriterSetNamesMergeUnverifiedReason(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = _read_workflow_schema()
        cls.writer_slice = _writer_set_slice(cls.raw)
        cls.normalized = _normalize_ws(cls.raw)

    def test_states_merge_unverified_sentence(self):
        self.assertIn(MERGE_UNVERIFIED_SENTENCE_PHRASE, self.normalized)

    def test_citation_phrase_present(self):
        self.assertIn(MERGE_UNVERIFIED_CITATION_PHRASE, self.normalized)

    def test_additive_phrase_present(self):
        self.assertIn(MERGE_UNVERIFIED_ADDITIVE_PHRASE, self.normalized)

    def test_negative_proof_sentence_absent_when_removed(self):
        forged = self.normalized.replace(MERGE_UNVERIFIED_SENTENCE_PHRASE, "")
        self.assertNotIn(MERGE_UNVERIFIED_SENTENCE_PHRASE, forged)

    def test_writer_set_enumeration_still_exactly_five(self):
        names = _extract_script_names(self.writer_slice)
        self.assertEqual(names, EXPECTED_WRITER_NAMES)

    def test_negative_proof_added_writer_name_is_detected(self):
        forged = self.writer_slice.replace(
            "`merge-task.sh`", "`merge-task.sh`, `queue_new_writer.py`"
        )
        names = _extract_script_names(forged)
        self.assertNotEqual(names, EXPECTED_WRITER_NAMES)
        self.assertIn("queue_new_writer.py", names)

    def test_negative_proof_removed_writer_name_is_detected(self):
        forged = self.writer_slice.replace("`queue_failure_net.py`", "")
        names = _extract_script_names(forged)
        self.assertNotEqual(names, EXPECTED_WRITER_NAMES)
        self.assertNotIn("queue_failure_net.py", names)

    def test_negative_proof_recover_orphaned_task_forged_is_detected(self):
        forged = self.writer_slice + " `recover-orphaned-task.py`"
        names = _extract_script_names(forged)
        self.assertNotEqual(names, EXPECTED_WRITER_NAMES)
        self.assertIn("recover-orphaned-task.py", names)

    def test_no_extraneous_script_name_in_live_span(self):
        self.assertNotIn(
            "recover-orphaned-task.py", _extract_script_names(self.writer_slice)
        )


# ===========================================================================
# AC-2: orphan invocation no longer exclusive; retained phrases; failed_kind
# ===========================================================================

OLD_ORPHAN_ONLY_PHRASE = (
    "invoked only by the orchestrator's I.2.b orphan-recovery attempt"
)

# Verbatim pre-change excerpt (this task's base commit, before the edit).
PRE_CHANGE_ORPHAN_INVOCATION_SAMPLE = (
    "exception, `em-workflow/scripts/journal-append-failed.py`: invoked "
    "only by the orchestrator's I.2.b orphan-recovery attempt "
    "(`em-workflow/references/implement-phase.md`'s I.2.b Recovery / "
    "Residual block — cited here as the owning section, not restated), "
    "it appends `failed` with reason `orphaned`, an additive value of "
    "the existing `failed` reason field (no existing event name or "
    "reason is renamed or removed)."
)

RETAINED_ORPHANED_ADDITIVE_PHRASE = (
    "an additive value of the existing `failed` reason field"
)
RETAINED_STALE_LAUNCHED_SENTENCE_PHRASE = (
    "also appends `failed` with reason `stale-launched`, a second "
    "additive value of the existing `failed` reason field, adding no "
    "writer"
)
RETAINED_NO_RENAME_PHRASE = (
    "no existing event name or reason is renamed or removed"
)
RETAINED_RECOVERY_RESIDUAL_CITATION_PHRASE = (
    "`em-workflow/references/implement-phase.md`'s I.2.b Recovery / "
    "Residual block"
)

# Verbatim pre-change capture of the `failed_kind` section (byte-identical
# check; this task never touches it -- IMPLEMENTATION.md Convention 5).
PRE_CHANGE_FAILED_KIND_SECTION = "## `failed_kind`\n\n`failed_kind` belongs to the `implement` step of `workflow` and carries a\nclosed two-value vocabulary and no other value: an external-cause value\nand a decision-required value.\n\n- `infra` — the failure's cause is external to the implementation: the\n  implementer was orphaned, or a harness failure occurred. Which concrete\n  failures are attributed to this value today is\n  `references/implement-phase.md`'s to state, not restated here; a\n  failure that carries no external-cause signal reads as the\n  decision-required value below (fail-closed).\n- `decision` — the failure is in the implementation itself, or the plan\n  needs to be revisited.\n\nThis document is the single owner of the field's meaning, its\nrequired-ness and its permitted values; every other document cites this\nsection by repository-relative path instead of restating it.\n\n**Required-ness.** The field is REQUIRED on every write that sets the\n`implement` step's `status` to `failed`. Three write paths make such a\nwrite; they are owned by `references/implement-phase.md`, which this\nsection cites without restating which value each path writes.\n\n**Lifecycle.** The field is set only by the same write that sets `status`\nto `failed`; it is held for exactly as long as that `failed` status; it is\nreturned to null by the same write set that moves the `implement` step off\n`failed`. No separate write and no separate commit exists for the set or\nfor the clear.\n\n**Missing-value compatibility.** An `implement` `failed` carrying no\n`failed_kind` reads as the `decision` value. No migration runs. This\ncompatibility rule does not weaken the required-ness above for the write\npaths that are in scope.\n\n"


def _failed_kind_section(raw_text):
    anchor = "## Command approval store"
    start = raw_text.index("## `failed_kind`", raw_text.index(anchor))
    end = raw_text.index("## `completed_at_commit`", start)
    return raw_text[start:end]


class TestOrphanInvocationNoLongerExclusive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normalized = _normalize_ws(_read_workflow_schema())

    def test_old_orphan_only_phrase_matcher_flags_pre_change_sample(self):
        self.assertIn(
            OLD_ORPHAN_ONLY_PHRASE,
            _normalize_ws(PRE_CHANGE_ORPHAN_INVOCATION_SAMPLE),
        )

    def test_old_orphan_only_phrase_absent_from_live_document(self):
        self.assertNotIn(OLD_ORPHAN_ONLY_PHRASE, self.normalized)

    def test_retained_phrases_still_match(self):
        for phrase in (
            RETAINED_ORPHANED_ADDITIVE_PHRASE,
            RETAINED_STALE_LAUNCHED_SENTENCE_PHRASE,
            RETAINED_NO_RENAME_PHRASE,
            RETAINED_RECOVERY_RESIDUAL_CITATION_PHRASE,
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)


class TestFailedKindSectionByteIdentical(unittest.TestCase):
    def test_failed_kind_section_unchanged(self):
        actual = _failed_kind_section(_read_workflow_schema())
        self.assertEqual(actual, PRE_CHANGE_FAILED_KIND_SECTION)

    def test_negative_proof_mismatch_is_detected(self):
        forged = PRE_CHANGE_FAILED_KIND_SECTION.replace("`decision`", "`infra`")
        self.assertNotEqual(forged, PRE_CHANGE_FAILED_KIND_SECTION)


# ===========================================================================
# AC-3: Status semantics bullet stays unconditional (pinned)
# ===========================================================================

STATUS_BULLET_START_MARKER = "`tasks.*.status` transitions"
STATUS_BULLET_END_MARKER = "- A task is DONE only when its branch is merged into"

STATUS_BULLET_CORE_PHRASE = (
    "A `failed` task resolves ONLY by retry or by routing back to planning"
)
CARVEOUT_MARKERS = ("except", "unless", "not met", "exception")


def _status_bullet(raw_text):
    return _slice(raw_text, STATUS_BULLET_START_MARKER, STATUS_BULLET_END_MARKER)


class TestStatusSemanticsBulletUnconditional(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bullet = _normalize_ws(_status_bullet(_read_workflow_schema()))

    def test_core_resolution_phrase_present(self):
        self.assertIn(STATUS_BULLET_CORE_PHRASE, self.bullet)

    def test_no_carveout_markers_present(self):
        lowered = self.bullet.lower()
        for marker in CARVEOUT_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, lowered)

    def test_negative_proof_forged_exception_clause_is_detected(self):
        forged = (
            self.bullet + " except when the plan explicitly waives this rule"
        ).lower()
        self.assertTrue(any(marker in forged for marker in CARVEOUT_MARKERS))


# ===========================================================================
# AC-4 / AC-5: agents.jsonl paragraph -- readers, cost, purpose
# ===========================================================================

AGENTS_PARAGRAPH_START_MARKER = (
    "The same worktree-root directory also holds `agents.jsonl`"
)
AGENTS_PARAGRAPH_END_MARKER = "## Status semantics"


def _agents_paragraph(raw_text):
    return _slice(
        raw_text, AGENTS_PARAGRAPH_START_MARKER, AGENTS_PARAGRAPH_END_MARKER
    )


READER_TASKSTOP_PHRASE = "`queue_taskstop_net.py` at stop"
READER_FAILURE_NET_PHRASE = "`queue_failure_net.py`'s agent-index fallback"
READER_ORCHESTRATOR_PHRASE = (
    "the orchestrator's I.2.b step 1 Agent index lookup and Recovery"
)
READER_RECOVER_ORPHANED_PHRASE = "`em-workflow/scripts/recover-orphaned-task.py`"

NOT_LIVE_UNRESOLVED_PHRASE = (
    "leaves I.2.b step 1's not-live determination unresolved for a stale "
    "`launched` task"
)
I2B_CITATION_PHRASE = "`em-workflow/references/implement-phase.md`'s I.2.b"

ORCHESTRATOR_READ_WORDING_MOST_RECENT = "most recently appended entry"
ORCHESTRATOR_READ_WORDING_FIRST_RECORDED = "first-recorded candidate"

# Verbatim pre-change capture of the agents.jsonl paragraph (whitespace
# collapsed at capture time -- byte identity is not the point here).
PRE_CHANGE_AGENTS_PARAGRAPH_SAMPLE = "The same worktree-root directory also holds `agents.jsonl`, the agent index — a separate diagnostic mapping, per launch, from a candidate list of harness agent-identifier strings (the exact identifier field the harness's launch response carries is unverified, so `queue_agent_index.py` records every candidate it can recover rather than a single one) to the em-workflow task identity that launched it, written by `queue_agent_index.py` at launch and read by `queue_taskstop_net.py` at stop. It is NOT part of the journal contract above and must never be treated as a second authoritative state file: it carries no status semantics of its own, may be absent or stale, and its absence only degrades the stop-tool recorder to a no-op. The sole exception to \"no status semantics of its own\" is the session identity (`session_id`) it also carries per launch: `em-workflow/references/implement-phase.md`'s I.2.b Recovery / Residual block (cited here, not restated) reads it — a comparison value only, never a status value and never a match candidate on the stop side — to judge whether the launching session is provably gone. `journal.jsonl` alone is the authoritative raw-event record; `agents.jsonl` exists solely to make a stop resolvable back to a task. Full contract (candidate-list format, matching rule, staleness/supersede rule): IMPLEMENTATION.md's Agent index contract."

OLD_READER_NARROW_PHRASE = "read by `queue_taskstop_net.py` at stop"
OLD_ABSENCE_NARROW_PHRASE = (
    "its absence only degrades the stop-tool recorder to a no-op"
)
OLD_PURPOSE_NARROW_PHRASE = (
    "`agents.jsonl` exists solely to make a stop resolvable back to a task"
)

RETAINED_NO_STATUS_SEMANTICS_PHRASE = (
    "it carries no status semantics of its own, may be absent or stale"
)
RETAINED_SESSION_ID_EXCEPTION_PHRASE = (
    'The sole exception to "no status semantics of its own" is the '
    "session identity"
)


class TestAgentsJsonlNamesFourReadersAndRecoveryCost(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paragraph = _normalize_ws(_agents_paragraph(_read_workflow_schema()))

    def test_all_four_readers_named(self):
        for phrase in (
            READER_TASKSTOP_PHRASE,
            READER_FAILURE_NET_PHRASE,
            READER_ORCHESTRATOR_PHRASE,
            READER_RECOVER_ORPHANED_PHRASE,
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.paragraph)

    def test_not_live_determination_unresolved_stated_and_cited(self):
        self.assertIn(NOT_LIVE_UNRESOLVED_PHRASE, self.paragraph)
        self.assertIn(I2B_CITATION_PHRASE, self.paragraph)

    def test_does_not_restate_orchestrator_read_rule_wording(self):
        self.assertNotIn(ORCHESTRATOR_READ_WORDING_MOST_RECENT, self.paragraph)
        self.assertNotIn(ORCHESTRATOR_READ_WORDING_FIRST_RECORDED, self.paragraph)

    def test_negative_proof_orchestrator_read_wording_forged_is_detected(self):
        forged = self.paragraph + " " + ORCHESTRATOR_READ_WORDING_MOST_RECENT
        self.assertIn(ORCHESTRATOR_READ_WORDING_MOST_RECENT, forged)
        forged2 = self.paragraph + " " + ORCHESTRATOR_READ_WORDING_FIRST_RECORDED
        self.assertIn(ORCHESTRATOR_READ_WORDING_FIRST_RECORDED, forged2)


class TestAgentsJsonlNarrowPhrasesReplaced(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paragraph = _normalize_ws(_agents_paragraph(_read_workflow_schema()))

    def test_old_reader_narrow_phrase_matcher_flags_pre_change_sample(self):
        self.assertIn(OLD_READER_NARROW_PHRASE, PRE_CHANGE_AGENTS_PARAGRAPH_SAMPLE)

    def test_old_reader_narrow_phrase_absent_from_live_document(self):
        self.assertNotIn(OLD_READER_NARROW_PHRASE, self.paragraph)

    def test_old_absence_narrow_phrase_matcher_flags_pre_change_sample(self):
        self.assertIn(OLD_ABSENCE_NARROW_PHRASE, PRE_CHANGE_AGENTS_PARAGRAPH_SAMPLE)

    def test_old_absence_narrow_phrase_absent_from_live_document(self):
        self.assertNotIn(OLD_ABSENCE_NARROW_PHRASE, self.paragraph)

    def test_old_purpose_narrow_phrase_matcher_flags_pre_change_sample(self):
        self.assertIn(OLD_PURPOSE_NARROW_PHRASE, PRE_CHANGE_AGENTS_PARAGRAPH_SAMPLE)

    def test_old_purpose_narrow_phrase_absent_from_live_document(self):
        self.assertNotIn(OLD_PURPOSE_NARROW_PHRASE, self.paragraph)

    def test_retained_anchor_present_in_both_sample_and_live(self):
        # Retained-anchor guard: proves the absence checks above are not
        # vacuous -- the sample and the live paragraph are the same region.
        self.assertIn(
            RETAINED_NO_STATUS_SEMANTICS_PHRASE, PRE_CHANGE_AGENTS_PARAGRAPH_SAMPLE
        )
        self.assertIn(RETAINED_NO_STATUS_SEMANTICS_PHRASE, self.paragraph)

    def test_kept_phrases_of_r2_item4_still_match(self):
        for phrase in (
            RETAINED_NO_STATUS_SEMANTICS_PHRASE,
            RETAINED_SESSION_ID_EXCEPTION_PHRASE,
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.paragraph)


# ===========================================================================
# AC-6: no SC6 residual reason code anywhere in workflow-schema.md
# ===========================================================================

# The closed sixteen-value SC6 set (em-workflow/scripts/recover-orphaned-
# task.py's REASON_* constants), backtick-quoted exactly as the codes are
# written wherever they appear (implement-phase.md, never here).
SC6_RESIDUAL_REASON_CODES = frozenset(
    {
        "`no-agent-entry`",
        "`stale-agent-entry`",
        "`no-session-id`",
        "`invalid-session-id`",
        "`current-session-unknown`",
        "`same-session`",
        "`transcripts-dir-missing`",
        "`transcript-unreadable`",
        "`transcript-active`",
        "`journal-not-launched`",
        "`task-artifacts-missing`",
        "`agent-identity-unproven`",
        "`agent-termination-unproven`",
        "`agent-still-live`",
        "`stop-result-unproven`",
        "`launch-changed`",
    }
)


class TestNoSC6ResidualCodeInWorkflowSchema(unittest.TestCase):
    def test_exactly_sixteen_codes_in_closed_set(self):
        self.assertEqual(len(SC6_RESIDUAL_REASON_CODES), 16)

    def test_no_sc6_code_present_in_live_document(self):
        text = _read_workflow_schema()
        for code in SC6_RESIDUAL_REASON_CODES:
            with self.subTest(code=code):
                self.assertNotIn(code, text)

    def test_negative_proof_forged_code_is_detected(self):
        text = _read_workflow_schema()
        forged = text + "\n`launch-changed`\n"
        self.assertIn("`launch-changed`", forged)


# ===========================================================================
# AC-7: module imports only the standard library
# ===========================================================================


class TestModuleImportsOnlyStandardLibrary(unittest.TestCase):
    def test_module_uses_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"ast", "re", "unittest", "pathlib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {node.module}")


if __name__ == "__main__":
    unittest.main()
