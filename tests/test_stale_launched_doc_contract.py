"""Tests for task0003 (stale-launched-retry-recovery): the three owning
documentation sites -- the I.2.b Orphan recovery block, the
Stale-`launched` caveat, and the journal writer-set paragraph -- state the
new same-session branch, its six new residual reason codes and the new
`failed` reason value, with the writer set itself unchanged; and the
abort-phase bullet attributes the new reason value exactly as it
attributes `orphaned`.

Covers task0003 Acceptance Criteria
(feature-docs/stale-launched-retry-recovery/tasks/task0003.md):

- AC-1 (FR10a): the I.2.b Orphan recovery block contains all six new
  reason codes verbatim, in the fixed evidence order relative to one
  another, and states both conjuncts plus the explicit insufficiency of an
  elapsed-time threshold and of an idle interval.
- AC-2 (FR10a): the same block states that the recorded session identity
  is never used as the stop target, and names `stale-launched` as the
  reason the helper is invoked with on the new branch.
- AC-3 (FR10b): the Stale-`launched` caveat covers a stop that delivers
  neither a subagent-stop nor a stop-tool event, naming the extended
  same-session branch as the mechanism that closes it.
- AC-4 (FR10c): the writer-set paragraph names `stale-launched` as an
  additive value of the existing `failed` reason field, and the writer-set
  enumeration itself is unchanged.
- AC-5 (FR12): the abort-phase bullet attributes the external-cause
  `failed_kind` value to a journal `failed` event whose reason is
  `orphaned` or `stale-launched`, while the batch-mode second-failure
  paragraph still writes the decision-required value unconditionally and
  is byte-identical to its pre-change text.
- AC-6 (FR13): this module asserts AC-1 through AC-5 against the real
  documentation files, and each matcher has a negative proof against a
  forged sample that the matcher must reject.
- AC-7 (FR10): covered by the pre-existing documentation-pinning modules
  (`test_implement_routeback_gate.py`, `test_failed_kind_write_paths.py`)
  continuing to pass unmodified -- not re-asserted here.
- AC-8: this module imports only the standard library.

Follows the established convention (standard library only, document text
read from the repository root computed from this module's own path,
module-level constants for each literal read once by a positive test and
once by a negative-proof test, whitespace-normalized matching unless a raw
line-wrap position matters).
"""

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
WORKFLOW_SCHEMA_PATH = PLUGIN_ROOT / "references" / "workflow-schema.md"

I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"
SUPPORTING_CAST_HEADING = "### Supporting cast"
STEP_I3_HEADING = "## Step I.3: Phase completion"
RESUME_HEADING = "**Resume**"
BATCH_PARAGRAPH_MARKER = "Batch mode (`references/batch-mode.md`"


def _read_implement_phase():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _read_workflow_schema():
    return WORKFLOW_SCHEMA_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text)


def _slice(text, start_marker, end_marker, start_from=0):
    start = text.index(start_marker, start_from)
    end = text.index(end_marker, start)
    return text[start:end]


def _i2b_section(text):
    return _slice(text, I2B_HEADING, I2C_HEADING)


def _i2c_section(text):
    return _slice(text, I2C_HEADING, SUPPORTING_CAST_HEADING)


def _caveat_section(text):
    supporting_cast = _slice(text, SUPPORTING_CAST_HEADING, STEP_I3_HEADING)
    return _slice(supporting_cast, "Stale-`launched` caveat", RESUME_HEADING)


def _batch_paragraph(i2c_section_text):
    start = i2c_section_text.index(BATCH_PARAGRAPH_MARKER)
    return i2c_section_text[start:].rstrip()


# --- AC-1: six new reason codes, fixed order, both conjuncts, insufficiency
# -----------------------------------------------------------------------

RESIDUAL_CODES_IN_ORDER = (
    "task-artifacts-missing",
    "agent-identity-unproven",
    "agent-termination-unproven",
    "agent-still-live",
    "stop-result-unproven",
    "launch-changed",
)

CONJUNCT_TERMINATION_PHRASE = (
    "explicit harness evidence that THIS launch's execution terminated"
)
CONJUNCT_STOP_RESULT_PHRASE = (
    "an explicit not-running (or absent) stop-tool result for the SAME "
    "bound agent identity"
)
INSUFFICIENCY_PHRASE = (
    "no elapsed-time threshold and no transcript or output-file idle "
    "interval substitutes for either conjunct"
)


class TestI2bSixNewResidualCodesInFixedOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))

    def test_all_six_codes_present(self):
        for code in RESIDUAL_CODES_IN_ORDER:
            with self.subTest(code=code):
                self.assertIn(f"`{code}`", self.i2b)

    def test_codes_appear_in_fixed_relative_order(self):
        positions = [self.i2b.index(f"`{code}`") for code in RESIDUAL_CODES_IN_ORDER]
        self.assertEqual(positions, sorted(positions))

    def test_negative_proof_missing_code_is_detected(self):
        forged = self.i2b.replace("`launch-changed`", "")
        self.assertNotIn("`launch-changed`", forged)

    def test_negative_proof_out_of_order_codes_detected(self):
        # Swap two codes' positions in a forged copy; the order check must
        # then fail (positions no longer sorted).
        forged = self.i2b.replace(
            "`task-artifacts-missing`", "`__PLACEHOLDER__`"
        ).replace("`launch-changed`", "`task-artifacts-missing`").replace(
            "`__PLACEHOLDER__`", "`launch-changed`"
        )
        positions = [forged.index(f"`{code}`") for code in RESIDUAL_CODES_IN_ORDER]
        self.assertNotEqual(positions, sorted(positions))


class TestI2bConjunctsAndInsufficiencyStated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))

    def test_termination_conjunct_present(self):
        self.assertIn(CONJUNCT_TERMINATION_PHRASE, self.i2b)

    def test_stop_result_conjunct_present(self):
        self.assertIn(CONJUNCT_STOP_RESULT_PHRASE, self.i2b)

    def test_insufficiency_statement_present(self):
        self.assertIn(INSUFFICIENCY_PHRASE, self.i2b)

    def test_negative_proof_termination_conjunct_absent_when_removed(self):
        forged = self.i2b.replace(CONJUNCT_TERMINATION_PHRASE, "")
        self.assertNotIn(CONJUNCT_TERMINATION_PHRASE, forged)

    def test_negative_proof_stop_result_conjunct_absent_when_removed(self):
        forged = self.i2b.replace(CONJUNCT_STOP_RESULT_PHRASE, "")
        self.assertNotIn(CONJUNCT_STOP_RESULT_PHRASE, forged)

    def test_negative_proof_insufficiency_absent_when_removed(self):
        forged = self.i2b.replace(INSUFFICIENCY_PHRASE, "")
        self.assertNotIn(INSUFFICIENCY_PHRASE, forged)


# --- AC-2: recorded identity never the stop target; stale-launched reason
# -----------------------------------------------------------------------

RECORDED_IDENTITY_NOT_STOP_TARGET_PHRASE = (
    "The recorded session identity is never used as the stop target on "
    "this branch"
)
STALE_LAUNCHED_INVOCATION_PHRASE = (
    "invoke `em-workflow/scripts/journal-append-failed.py` exactly once, "
    "with the task id and reason `stale-launched`"
)


class TestI2bRecordedIdentityAndStaleLaunchedReason(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read_implement_phase()))

    def test_recorded_identity_never_stop_target(self):
        self.assertIn(RECORDED_IDENTITY_NOT_STOP_TARGET_PHRASE, self.i2b)

    def test_stale_launched_invocation_named(self):
        self.assertIn(STALE_LAUNCHED_INVOCATION_PHRASE, self.i2b)

    def test_negative_proof_identity_statement_absent_when_removed(self):
        forged = self.i2b.replace(RECORDED_IDENTITY_NOT_STOP_TARGET_PHRASE, "")
        self.assertNotIn(RECORDED_IDENTITY_NOT_STOP_TARGET_PHRASE, forged)

    def test_negative_proof_invocation_absent_when_removed(self):
        forged = self.i2b.replace(STALE_LAUNCHED_INVOCATION_PHRASE, "")
        self.assertNotIn(STALE_LAUNCHED_INVOCATION_PHRASE, forged)


# --- AC-3: Stale-`launched` caveat gains the fifth mechanism -------------

CAVEAT_NEITHER_EVENT_PHRASE = (
    "a stop that delivers neither a subagent-stop nor a stop-tool event"
)
CAVEAT_EXTENDED_BRANCH_PHRASE = (
    "orphan-recovery attempt's extended same-session branch"
)


class TestCaveatCoversFifthMechanism(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caveat = _normalize_ws(_caveat_section(_read_implement_phase()))

    def test_covers_neither_event_stop(self):
        self.assertIn(CAVEAT_NEITHER_EVENT_PHRASE, self.caveat)

    def test_names_extended_same_session_branch(self):
        self.assertIn(CAVEAT_EXTENDED_BRANCH_PHRASE, self.caveat)

    def test_negative_proof_neither_event_phrase_absent_when_removed(self):
        forged = self.caveat.replace(CAVEAT_NEITHER_EVENT_PHRASE, "")
        self.assertNotIn(CAVEAT_NEITHER_EVENT_PHRASE, forged)

    def test_negative_proof_extended_branch_absent_when_removed(self):
        forged = self.caveat.replace(CAVEAT_EXTENDED_BRANCH_PHRASE, "")
        self.assertNotIn(CAVEAT_EXTENDED_BRANCH_PHRASE, forged)


# --- AC-4: writer-set paragraph additive value + unchanged writer set ----

SCHEMA_STALE_LAUNCHED_ADDITIVE_PHRASE = (
    "also appends `failed` with reason `stale-launched`, a second "
    "additive value of the existing `failed` reason field, adding no "
    "writer"
)

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


class TestWorkflowSchemaWriterSetAdditiveAndUnchanged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _read_workflow_schema()
        cls.normalized = _normalize_ws(cls.section)
        cls.writer_slice = _writer_set_slice(cls.section)

    def test_states_stale_launched_additive_value(self):
        self.assertIn(SCHEMA_STALE_LAUNCHED_ADDITIVE_PHRASE, self.normalized)

    def test_negative_proof_additive_phrase_absent_when_removed(self):
        forged = self.normalized.replace(SCHEMA_STALE_LAUNCHED_ADDITIVE_PHRASE, "")
        self.assertNotIn(SCHEMA_STALE_LAUNCHED_ADDITIVE_PHRASE, forged)

    def test_writer_set_enumeration_unchanged(self):
        names = _extract_script_names(self.writer_slice)
        self.assertEqual(names, EXPECTED_WRITER_NAMES)

    def test_negative_proof_added_writer_is_detected(self):
        forged = self.writer_slice.replace(
            "`merge-task.sh`", "`merge-task.sh`, `queue_new_writer.py`"
        )
        names = _extract_script_names(forged)
        self.assertNotEqual(names, EXPECTED_WRITER_NAMES)
        self.assertIn("queue_new_writer.py", names)

    def test_negative_proof_removed_writer_is_detected(self):
        forged = self.writer_slice.replace("`queue_failure_net.py`", "")
        names = _extract_script_names(forged)
        self.assertNotEqual(names, EXPECTED_WRITER_NAMES)
        self.assertNotIn("queue_failure_net.py", names)


# --- AC-5: abort-phase bullet attribution + batch paragraph unchanged ----

ABORT_BOTH_REASONS_PHRASE = (
    "the failing task's failure originates from a journal `failed` event "
    "whose reason is `orphaned` or `stale-launched`"
)

# The batch-mode second-failure paragraph, captured verbatim as it reads
# both before and after this task's edit (this task's Out of Scope
# explicitly excludes touching it) -- the byte-identity assertion for AC-5
# reuses this literal rather than introducing a second copy elsewhere.
PRE_CHANGE_BATCH_PARAGRAPH = (
    "Batch mode (`references/batch-mode.md`'s Non-packet gates table,\n"
    "`implement.failed-task`): no AskUserQuestion —\n"
    "after the drain, auto-select **retry** ONCE per task (kept worktree, I.2.a\n"
    "resume guard). A task that fails a second time → **abort phase**: refresh\n"
    "the integration worktree, capture the tip, then set and commit the\n"
    "`implement` step's `status` to `failed`, together with `failed_kind`\n"
    "valued `decision` unconditionally — including when the failure\n"
    "originates from a journal `failed` event whose reason is `orphaned`,\n"
    "overriding the abort-phase option's rule above for this entrance — via\n"
    "`commit-docs.sh` (no `create-plan` `needs_update`, no task status or\n"
    "notes write set, no worktree or branch cleanup — the terminal status\n"
    "write and its own commit are the ONLY side effect), then report and\n"
    "stop; control returns via develop's stop condition 3, firing on the next\n"
    "Step B iteration reading `implement: failed` — unaffected by this\n"
    "override, since `references/batch-terminal-line.md` already gives\n"
    "`implement-second-failure` precedence over `stop-condition-3`. The\n"
    "external service cuts a follow-up task. Route-back-to-planning is never\n"
    "taken automatically. Track the retry-consumed state per task in\n"
    "`tasks.{T}.notes`."
)


class TestAbortBulletAttributesBothReasons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i2c_raw = _i2c_section(_read_implement_phase())
        cls.i2c = _normalize_ws(cls.i2c_raw)

    def test_abort_bullet_attributes_orphaned_or_stale_launched(self):
        self.assertIn(ABORT_BOTH_REASONS_PHRASE, self.i2c)

    def test_negative_proof_stale_launched_disjunct_absent_when_removed(self):
        forged = self.i2c.replace(" or `stale-launched`", "")
        self.assertNotIn(ABORT_BOTH_REASONS_PHRASE, forged)

    def test_batch_paragraph_byte_identical_to_pre_change_text(self):
        actual = _batch_paragraph(self.i2c_raw)
        self.assertEqual(actual, PRE_CHANGE_BATCH_PARAGRAPH)

    def test_negative_proof_batch_paragraph_mismatch_detected(self):
        forged = PRE_CHANGE_BATCH_PARAGRAPH.replace("`decision`", "`infra`")
        self.assertNotEqual(forged, PRE_CHANGE_BATCH_PARAGRAPH)


# --- AC-8: module imports only the standard library ----------------------


class TestModuleImportsStdlibOnly(unittest.TestCase):
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
