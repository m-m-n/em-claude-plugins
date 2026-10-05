"""Tests for task0006 (prelaunch-inprogress-routeback): the record
`tasks.{T}.routeback_failed_journal_line` has one normative definition in
`workflow-schema.md`, a re-planning `replace_all` carries it verbatim for
carried task ids, and `validate-worker-output.py` rejects any worker
`tasks_patch.entries` entry that tries to set it.

Covers task0006 Acceptance Criteria
(feature-docs/prelaunch-inprogress-routeback/tasks/task0006.md):

- AC-1 (FR11, TM-3): `TestFullStructureListsOptionalField` and
  `TestSectionHeadingAndPlacement` / `TestSectionDefinesTheRecord` -- the
  Full structure tasks block lists the field as optional; the section with
  the exact heading states the meaning, the journal path, the 1-based
  physical-line value, the LF-only counting rule, the canonical form and
  the "absent / null / non-canonical means no record" rule.
- AC-2 (FR11, TM-1): `TestSectionNamesWriterLifecycleAndReaders` -- the
  sole writer, the never-written-by list, the not-rewritten list, the
  overwrite-only-by-route-back rule and the three readers.
- AC-3 (FR12): `TestCarryOverListNamesTheRecord` and
  `TestPreserveVocabularyHasNoRecordEntry` -- the verbatim carry-over list
  has 11 fields including the record; the preserve vocabulary (document and
  validator) has no entry for it.
- AC-4 (FR12): `TestApplyPatchKeepsTheRecordOnCarriedTasks` -- integer,
  absent and `null` all survive a re-planning `replace_all`.
- AC-5 (FR13, TM-1): `TestValidatorRejectsTheRecordInWorkerEntries` -- the
  four mandated cases (replace_all / append x integer / null), plus other
  value shapes, the initial-planning replace_all path and the
  non-dry-run path.
- AC-6 (FR13, NFR3): `TestPatchesWithoutTheKeyStillPass` -- valid patches
  without the key pass for both modes; carried ids are unaffected.
  (Existing fixtures' verdicts and `tests/test_validate_worker_output.py`
  are held by that module, run unmodified.)
- AC-7 (NFR2, NFR3, NFR4): `TestModuleImportsOnlyStandardLibrary`; the
  four named doc-contract modules and the whole suite pass unmodified.

Convention (IMPLEMENTATION.md Conventions, "Test module shape"): standard
library `unittest` only; content assertions on whitespace-normalized text;
every wording literal is a module-level constant read by both its positive
test and its negative proof; every new-wording matcher has a negative proof
against a verbatim pre-change sample captured from the task's base revision
(`git show` of the fork-point), plus a non-vacuity anchor present in both
the sample and the live document. No test writes under `em-workflow/`;
patches and workflows are built in memory.
"""

import ast
import copy
import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
SCHEMA_PATH = PLUGIN_ROOT / "references" / "workflow-schema.md"
PATCH_DOC_PATH = PLUGIN_ROOT / "references" / "workflow-patch.md"
VALIDATOR_PATH = PLUGIN_ROOT / "scripts" / "validate-worker-output.py"

RECORD_FIELD = "routeback_failed_journal_line"
# The validator's error code for a worker entry carrying the record: its
# own stable code, named after the field (the existing field-level codes
# such as `files` / `provenance` follow the same naming).
RECORD_ERROR_CODE = "routeback_failed_journal_line"

SECTION_HEADING = "## `routeback_failed_journal_line`"
FAILED_KIND_HEADING = "## `failed_kind`"
COMPLETED_AT_COMMIT_HEADING = "## `completed_at_commit` (rule R2)"
SIBLING_ARTIFACTS_HEADING = "## Sibling artifacts"

# ---------------------------------------------------------------------------
# Wording constants (each read by its positive test AND its negative proof)
# ---------------------------------------------------------------------------

# Full structure tasks block comment.
FIELD_COMMENT_OPTIONAL = "OPTIONAL"
FIELD_COMMENT_WRITER = "written by the orchestrator at route-back"
FIELD_COMMENT_ABSENT = "absent by default"

# AC-1: meaning, path, value, counting rule, canonical form, no-record rule.
MEANING_PHRASE = "is the route-back reset confirmation record"
JOURNAL_PATH_PHRASE = (
    "`{project_root}/.claude/worktrees/em-workflow/{feature}/journal.jsonl`"
)
VALUE_PHRASE = (
    "The 1-based physical line, in the target file, of the task's last "
    "`failed` event at reset time"
)
LF_ONLY_PHRASE = "Lines are delimited by LF only; a CR is never a delimiter"
FINAL_SEGMENT_PHRASE = (
    "A final non-empty segment with no terminating LF counts as one more line"
)
BLANK_MALFORMED_PHRASE = (
    "Blank lines, malformed lines, lines with an unknown event and lines "
    "with an invalid task id are all counted"
)
CANONICAL_FORM_PHRASE = (
    "An unquoted decimal integer of ASCII digits whose first digit is 1-9"
)
NO_RECORD_PHRASE = (
    "Every reader treats a value that is absent, `null` or not in canonical "
    "form as no record"
)

# AC-2: writer, never-written-by, not-rewritten, overwrite, readers.
SOLE_WRITER_PHRASE = (
    "The orchestrator is the sole writer, inside Step I.2.c's route-back "
    "write set"
)
NO_EVENT_PHRASE = "A reset task with no journal event gets no record"
NEVER_WRITE_PHRASE = "Scripts, hooks and worker patches never write it"
NOT_REWRITTEN_PHRASE = (
    "It is not rewritten by the I.2.a launch-state commit, I.2.b step 3, a "
    "retry or a terminal-status write"
)
OVERWRITE_PHRASE = (
    "It is overwritten only by a later route-back of the same task. Nothing "
    "clears it"
)
READERS_PHRASE = (
    "I.2.a selection, I.2.b step 1 reconcile and `queue_stop_guard.py` read it"
)
IMPLEMENT_PHASE_CITATION_PHRASE = (
    "`references/implement-phase.md` owns how they use it"
)

# The section cites implement-phase.md for the classification and does not
# restate it.
RESTATEMENT_MARKERS = ("unlaunched", "carve-out", "three-condition")

AC1_SECTION_PHRASES = (
    MEANING_PHRASE,
    JOURNAL_PATH_PHRASE,
    VALUE_PHRASE,
    LF_ONLY_PHRASE,
    FINAL_SEGMENT_PHRASE,
    BLANK_MALFORMED_PHRASE,
    CANONICAL_FORM_PHRASE,
    NO_RECORD_PHRASE,
)
AC2_SECTION_PHRASES = (
    SOLE_WRITER_PHRASE,
    NO_EVENT_PHRASE,
    NEVER_WRITE_PHRASE,
    NOT_REWRITTEN_PHRASE,
    OVERWRITE_PHRASE,
    READERS_PHRASE,
    IMPLEMENT_PHASE_CITATION_PHRASE,
)

# ---------------------------------------------------------------------------
# Verbatim pre-change samples (this task's base revision, before any edit;
# captured with `git show` of the fork-point, never reconstructed)
# ---------------------------------------------------------------------------

# workflow-schema.md, Full structure: the `tasks:` block.
BASE_FULL_STRUCTURE_TASKS_BLOCK = """\
tasks:                             # written by implementation-planner; status by orchestrator
  task0001:
    title: {short title}
    plan: tasks/task0001.md        # relative to feature-docs/{feature}/
    files:                         # files the task is EXPECTED to touch
      - src/foo/bar.go             # (planner prediction; feeds review scoping
                                   #   and deviation tracking)
    skills: [backend-impl]         # from references/impl-skills.yaml; may be []
    domains: [data-persistence]    # ⊆ the vocabulary in
                                   # references/review-rules.yaml — that file
                                   # is the domains vocabulary SSOT
    complexity: medium             # low | medium | high (criteria: planner skill)
    requirements: [FR1]            # SPEC.md requirement IDs this task implements
    status: pending                # pending | in_progress | merged | failed
    notes: null                    # set on failure (reason; feeds re-planning)
    branch: em-workflow/{feature}/task0001   # set by orchestrator at dispatch
"""

# workflow-schema.md: from the `failed_kind` section through the line before
# `## Sibling artifacts` (the region the new section is placed in).
BASE_SCHEMA_REGION = """\
## `failed_kind`

`failed_kind` belongs to the `implement` step of `workflow` and carries a
closed two-value vocabulary and no other value: an external-cause value
and a decision-required value.

- `infra` — the failure's cause is external to the implementation: the
  implementer was orphaned, or a harness failure occurred. Which concrete
  failures are attributed to this value today is
  `references/implement-phase.md`'s to state, not restated here; a
  failure that carries no external-cause signal reads as the
  decision-required value below (fail-closed).
- `decision` — the failure is in the implementation itself, or the plan
  needs to be revisited.

This document is the single owner of the field's meaning, its
required-ness and its permitted values; every other document cites this
section by repository-relative path instead of restating it.

**Required-ness.** The field is REQUIRED on every write that sets the
`implement` step's `status` to `failed`. Three write paths make such a
write; they are owned by `references/implement-phase.md`, which this
section cites without restating which value each path writes.

**Lifecycle.** The field is set only by the same write that sets `status`
to `failed`; it is held for exactly as long as that `failed` status; it is
returned to null by the same write set that moves the `implement` step off
`failed`. No separate write and no separate commit exists for the set or
for the clear.

**Missing-value compatibility.** An `implement` `failed` carrying no
`failed_kind` reads as the `decision` value. No migration runs. This
compatibility rule does not weaken the required-ness above for the write
paths that are in scope.

## `completed_at_commit` (rule R2)

**Normative definition**: `completed_at_commit` is the HEAD **immediately
before** the commit that sets a step's `status` to `completed`.

**Applies to all seven `workflow[]` steps** — create-spec, design,
create-plan, implement, review, verify, retrospect — uniformly. A step may
produce zero or more artifact commits before its completion; the
status-completion commit is always a **separate commit** from any of them:

```
… : the step's artifact commit(s) (zero or more)
X  : the last of the above (or, if none, the prior phase's tip)
Y  : workflow.yaml status = completed, completed_at_commit = X
```

`completed_at_commit` always names `X`, never `Y` (the completion commit
itself). For `implement`, `X` is the integration branch tip after every
task has merged (a chain of merge commits, not a single artifact commit).

"""

# workflow-patch.md, Re-planning task-id allocation: the carried-record list.
BASE_CARRY_OVER_SAMPLE = """\
- `tasks_patch.carried_task_ids` — every task id already registered in the
  `workflow.yaml` the patch is applied to. Each carried id's record is
  copied from that `workflow.yaml` **verbatim** — `title`, `plan`, `files`,
  `skills`, `domains`, `complexity`, `requirements`, `status`, `branch`,
  `notes` — and the patch supplies no body for it: a carried id must not
  also be a key of `tasks_patch.entries`.
"""

# Non-vacuity anchors: present in the sample AND in the live document.
TASKS_BLOCK_ANCHOR = "    branch: em-workflow/{feature}/task0001"
CARRY_LIST_ANCHOR = "`requirements`, `status`, `branch`, `notes`"

# The list-parsing rule `tests/test_replanning_carry_over.py` applies to
# workflow-patch.md (the same pattern, not a second parser).
VERBATIM_LIST_PATTERN = (
    r"copied from that `workflow\.yaml` \*\*verbatim\*\* — "
    r"((?:`[a-z_]+`(?:, )?)+)"
)
EXPECTED_CARRIED_FIELD_COUNT = 11


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_ws(text):
    """Collapse whitespace runs (including line-wrap newlines) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def _read_schema():
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _read_patch_doc():
    return PATCH_DOC_PATH.read_text(encoding="utf-8")


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_worker_output", VALIDATOR_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_validator()


def _remove_phrase(text, phrase):
    """Remove `phrase` from raw `text` wherever it sits, whatever whitespace
    (including a line wrap) separates its words."""
    pattern = r"\s+".join(re.escape(word) for word in phrase.split(" "))
    return re.sub(pattern, "", text)


def _section(text, heading):
    """Slice from the exact heading line up to the next `## ` heading (or the
    end of the text). None when no line equals the heading."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line == heading), None)
    if start is None:
        return None
    end = next(
        (j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _require_section(test, schema_text):
    section = _section(schema_text, SECTION_HEADING)
    test.assertIsNotNone(section, "expected the exact-heading section")
    return section


def _live_full_structure_tasks_block(schema_text):
    start_of_full = schema_text.index("## Full structure")
    start = schema_text.index("\ntasks:", start_of_full) + 1
    end = schema_text.index("\nreview:", start)
    return schema_text[start:end]


_FIELD_LINE_RE = re.compile(
    r"^ {4}" + RECORD_FIELD + r":[^\n]*(?:\n[ ]+#[^\n]*)*", re.MULTILINE
)


def _assert_tasks_block_lists_optional_field(test, block):
    """AC-1 matcher: the tasks block carries the field line after `branch`,
    and its comment marks it optional, orchestrator-written and absent by
    default."""
    match = _FIELD_LINE_RE.search(block)
    test.assertIsNotNone(match, "expected a routeback_failed_journal_line field line")
    test.assertGreater(
        match.start(),
        block.index("    branch:"),
        "the field line must come after `branch`",
    )
    comment = _normalize_ws(match.group(0).replace("#", " "))
    for phrase in (
        FIELD_COMMENT_OPTIONAL,
        FIELD_COMMENT_WRITER,
        FIELD_COMMENT_ABSENT,
    ):
        test.assertIn(phrase, comment)


def _assert_section_states(test, schema_text, phrases):
    """AC-1 / AC-2 matcher: the exact-heading section exists and states every
    phrase (whitespace-normalized)."""
    normalized = _normalize_ws(_require_section(test, schema_text))
    for phrase in phrases:
        test.assertIn(phrase, normalized)


def _parse_carry_list(text):
    match = re.search(VERBATIM_LIST_PATTERN, _normalize_ws(text))
    if match is None:
        return None
    return re.findall(r"`([a-z_]+)`", match.group(1))


# ---------------------------------------------------------------------------
# AC-1: Full structure line
# ---------------------------------------------------------------------------


class TestFullStructureListsOptionalField(unittest.TestCase):
    """AC-1 (FR11): the Full structure tasks block lists the field."""

    def test_live_tasks_block_lists_the_field_as_optional(self):
        block = _live_full_structure_tasks_block(_read_schema())
        _assert_tasks_block_lists_optional_field(self, block)

    def test_matcher_fails_on_the_base_revision_tasks_block(self):
        """Negative proof: the same matcher against the pre-change block."""
        with self.assertRaises(AssertionError):
            _assert_tasks_block_lists_optional_field(
                self, BASE_FULL_STRUCTURE_TASKS_BLOCK
            )

    def test_retained_anchor_present_in_sample_and_live_block(self):
        """Non-vacuity guard: sample and live block are the same region."""
        live = _live_full_structure_tasks_block(_read_schema())
        self.assertIn(TASKS_BLOCK_ANCHOR, BASE_FULL_STRUCTURE_TASKS_BLOCK)
        self.assertIn(TASKS_BLOCK_ANCHOR, live)

    def test_matcher_rejects_a_field_line_without_the_optional_comment(self):
        """Negative proof (comment half): a bare field line is not enough."""
        forged = BASE_FULL_STRUCTURE_TASKS_BLOCK + (
            "    " + RECORD_FIELD + ": 7\n"
        )
        with self.assertRaises(AssertionError):
            _assert_tasks_block_lists_optional_field(self, forged)


# ---------------------------------------------------------------------------
# AC-1: section heading and placement
# ---------------------------------------------------------------------------


class TestSectionHeadingAndPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = _read_schema()
        cls.lines = cls.raw.split("\n")

    def test_heading_line_present_exactly_once(self):
        self.assertEqual(self.lines.count(SECTION_HEADING), 1)

    def test_placed_after_completed_at_commit_and_before_sibling_artifacts(self):
        self.assertIn(SECTION_HEADING, self.lines)
        completed = self.lines.index(COMPLETED_AT_COMMIT_HEADING)
        heading = self.lines.index(SECTION_HEADING)
        sibling = self.lines.index(SIBLING_ARTIFACTS_HEADING)
        self.assertLess(completed, heading)
        self.assertLess(heading, sibling)

    def test_not_between_failed_kind_and_completed_at_commit(self):
        self.assertIn(SECTION_HEADING, self.lines)
        failed_kind = self.lines.index(FAILED_KIND_HEADING)
        completed = self.lines.index(COMPLETED_AT_COMMIT_HEADING)
        heading = self.lines.index(SECTION_HEADING)
        self.assertFalse(failed_kind < heading < completed)

    def test_heading_absent_from_base_revision_region(self):
        """Negative proof: the base revision has no such heading."""
        self.assertNotIn(SECTION_HEADING, BASE_SCHEMA_REGION.split("\n"))
        self.assertIsNone(_section(BASE_SCHEMA_REGION, SECTION_HEADING))

    def test_retained_failed_kind_heading_present_in_sample_and_live(self):
        """Non-vacuity guard for the negative proof above."""
        self.assertIn(FAILED_KIND_HEADING, BASE_SCHEMA_REGION.split("\n"))
        self.assertIn(FAILED_KIND_HEADING, self.lines)


# ---------------------------------------------------------------------------
# AC-1: the section defines the record
# ---------------------------------------------------------------------------


class TestSectionDefinesTheRecord(unittest.TestCase):
    """AC-1 (FR11, TM-3)."""

    def test_live_section_states_meaning_path_value_counting_and_canonical_form(
        self,
    ):
        _assert_section_states(self, _read_schema(), AC1_SECTION_PHRASES)

    def test_matcher_fails_on_the_base_revision_region(self):
        """Negative proof: the same matcher against the pre-change region."""
        with self.assertRaises(AssertionError):
            _assert_section_states(self, BASE_SCHEMA_REGION, AC1_SECTION_PHRASES)

    def test_every_ac1_phrase_is_absent_from_the_base_revision_region(self):
        """Negative proof (per phrase): none of the new wording pre-exists."""
        normalized = _normalize_ws(BASE_SCHEMA_REGION)
        for phrase in AC1_SECTION_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, normalized)

    def test_matcher_fails_when_a_phrase_is_removed(self):
        forged = _remove_phrase(_read_schema(), CANONICAL_FORM_PHRASE)
        self.assertNotEqual(forged, _read_schema())
        with self.assertRaises(AssertionError):
            _assert_section_states(self, forged, AC1_SECTION_PHRASES)


# ---------------------------------------------------------------------------
# AC-2: writer, lifecycle, readers
# ---------------------------------------------------------------------------


class TestSectionNamesWriterLifecycleAndReaders(unittest.TestCase):
    """AC-2 (FR11, TM-1)."""

    def test_live_section_states_writer_lifecycle_and_readers(self):
        _assert_section_states(self, _read_schema(), AC2_SECTION_PHRASES)

    def test_matcher_fails_on_the_base_revision_region(self):
        """Negative proof: the same matcher against the pre-change region."""
        with self.assertRaises(AssertionError):
            _assert_section_states(self, BASE_SCHEMA_REGION, AC2_SECTION_PHRASES)

    def test_every_ac2_phrase_is_absent_from_the_base_revision_region(self):
        normalized = _normalize_ws(BASE_SCHEMA_REGION)
        for phrase in AC2_SECTION_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, normalized)

    def test_matcher_fails_when_the_sole_writer_sentence_is_removed(self):
        forged = _remove_phrase(_read_schema(), SOLE_WRITER_PHRASE)
        self.assertNotEqual(forged, _read_schema())
        with self.assertRaises(AssertionError):
            _assert_section_states(self, forged, AC2_SECTION_PHRASES)

    def test_section_cites_implement_phase_without_restating_classification(self):
        section = _normalize_ws(_require_section(self, _read_schema()))
        self.assertIn(IMPLEMENT_PHASE_CITATION_PHRASE, section)
        for marker in RESTATEMENT_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, section.lower())

    def test_restatement_check_detects_a_forged_restatement(self):
        """Negative proof: appending classification wording is detected."""
        section = _normalize_ws(_require_section(self, _read_schema()))
        forged = section + " The task is unlaunched when the three-condition match holds."
        self.assertTrue(
            any(marker in forged.lower() for marker in RESTATEMENT_MARKERS)
        )


# ---------------------------------------------------------------------------
# AC-3: carry-over list and preserve vocabulary
# ---------------------------------------------------------------------------


class TestCarryOverListNamesTheRecord(unittest.TestCase):
    """AC-3 (FR12): workflow-patch.md's verbatim list. (The module-level
    constant of `tests/test_replanning_carry_over.py` equals this parsed
    list; that equality is asserted there.)"""

    def test_live_list_contains_the_record_and_has_eleven_fields(self):
        fields = _parse_carry_list(_read_patch_doc())
        self.assertIsNotNone(fields, "expected the verbatim field-list sentence")
        self.assertIn(RECORD_FIELD, fields)
        self.assertEqual(len(fields), EXPECTED_CARRIED_FIELD_COUNT)
        self.assertEqual(len(set(fields)), EXPECTED_CARRIED_FIELD_COUNT)

    def test_base_revision_sample_lacks_the_record(self):
        """Negative proof: the same parser on the pre-change sample."""
        fields = _parse_carry_list(BASE_CARRY_OVER_SAMPLE)
        self.assertIsNotNone(fields)
        self.assertNotIn(RECORD_FIELD, fields)
        self.assertEqual(len(fields), EXPECTED_CARRIED_FIELD_COUNT - 1)

    def test_retained_anchor_present_in_sample_and_live_list(self):
        """Non-vacuity guard: sample and live sentence are the same region."""
        self.assertIn(CARRY_LIST_ANCHOR, _normalize_ws(BASE_CARRY_OVER_SAMPLE))
        self.assertIn(CARRY_LIST_ANCHOR, _normalize_ws(_read_patch_doc()))

    def test_record_is_inside_the_same_run_as_title_through_notes(self):
        """One comma-separated run: the existing parser reads all of it."""
        fields = _parse_carry_list(_read_patch_doc())
        self.assertEqual(fields[0], "title")
        self.assertIn("notes", fields)


class TestPreserveVocabularyHasNoRecordEntry(unittest.TestCase):
    """AC-3 (FR12): the record never enters the `preserve` vocabulary."""

    PRESERVE_START = "## `preserve` and the mandatory preserve sets"
    PRESERVE_END = "## Application rules (in order)"

    def _preserve_sections_text(self, doc_text):
        start = doc_text.index(self.PRESERVE_START)
        end = doc_text.index(self.PRESERVE_END, start)
        return doc_text[start:end]

    def _assert_no_record_entry(self, section_text):
        self.assertNotIn(RECORD_FIELD, section_text)

    def test_document_preserve_sections_have_no_record_entry(self):
        section = self._preserve_sections_text(_read_patch_doc())
        self._assert_no_record_entry(section)

    def test_document_matcher_detects_a_forged_vocabulary_entry(self):
        """Negative proof: a forged vocabulary line is detected, and the
        slice is the real vocabulary (it still lists the status path)."""
        section = self._preserve_sections_text(_read_patch_doc())
        self.assertIn("tasks.<task_id>.status", section)
        forged = section + "- `tasks.<task_id>." + RECORD_FIELD + "`\n"
        with self.assertRaises(AssertionError):
            self._assert_no_record_entry(forged)

    def test_validator_does_not_allow_the_record_as_a_preserve_path(self):
        self.assertFalse(
            VWO.is_preserve_path_allowed("tasks.task0001." + RECORD_FIELD)
        )
        for pattern in VWO.PRESERVE_PATTERNS:
            self.assertNotIn(RECORD_FIELD, pattern.pattern)
        for exact in VWO.PRESERVE_EXACT:
            self.assertNotIn(RECORD_FIELD, exact)

    def test_validator_check_is_not_vacuous(self):
        """Non-vacuity: the vocabulary check does allow its real entries."""
        self.assertTrue(VWO.is_preserve_path_allowed("tasks.task0001.status"))
        self.assertTrue(VWO.is_preserve_path_allowed("tasks.task0001.branch"))


# ---------------------------------------------------------------------------
# In-memory workflow / patch builders (no committed fixture files)
# ---------------------------------------------------------------------------


def _task(status="merged", **extra):
    record = {
        "branch": "em-workflow/example/taskNNNN",
        "complexity": "low",
        "domains": [],
        "files": ["x.go"],
        "notes": None,
        "plan": "tasks/taskNNNN.md",
        "requirements": ["FR1"],
        "skills": [],
        "status": status,
        "title": "existing",
    }
    record.update(extra)
    return record


def _workflow(tasks, *, create_plan_status="pending", implement_status="pending"):
    return {
        "feature": "example",
        "project": {"license": "MIT"},
        "requirements": {
            "FR1": {"status": "ok", "tasks": [], "tests": [], "title": "x"}
        },
        "schema_version": 1,
        "tasks": tasks,
        "workflow": [
            {"completed_at_commit": "aaa", "id": "create-spec", "status": "completed"},
            {"id": "design", "skipped_reason": "no UI", "status": "skipped"},
            {"id": "create-plan", "status": create_plan_status},
            {"base_commit": "deadbeef", "id": "implement", "status": implement_status},
            {"id": "review", "status": "pending"},
            {"id": "verify", "status": "pending"},
            {"id": "retrospect", "status": "pending"},
        ],
    }


def _digest_source():
    return {
        "answers_digest": "sha256:" + "2" * 64,
        "digest_inputs": {},
        "mode": "interactive",
        "value_inputs": {"task_description": None},
        "worker": "implementation-planner",
        "workflow_blob": "8f17c04",
        "write_policy_digest": "sha256:" + "3" * 64,
    }


def _replanning_phase_state():
    # An unspent, authorized spec_change record: the re-planning path's
    # second re-entry case (workflow-patch.md), so the carry-over checks run.
    return {
        "phase": "rework",
        "feature": "example",
        "spec_change": {
            "consumed": False,
            "origin_kind": "review",
            "origin_id": "abc123",
            "reason": "SPEC changed after implementation to add a missed requirement",
            "recorded_at_commit": "deadbeef",
            "replan_authorized": True,
        },
    }


def _new_entry(**extra):
    entry = {
        "complexity": "medium",
        "domains": [],
        "files": ["src/new.go"],
        "initial_status": "pending",
        "plan": "tasks/task0010.md",
        "requirements": ["FR1"],
        "skills": [],
        "title": "A new task",
    }
    entry.update(extra)
    return entry


def _replace_all_patch(carried_task_ids, entries):
    return {
        "base_input_digest": VWO.normalize_json_sha256(_digest_source()),
        "base_workflow_blob": "8f17c04",
        "operation": "replace_planning",
        "patch_id": "create-plan-p0001",
        "preserve": ["workflow.implement.base_commit"],
        "requirements_patch": None,
        "schema_version": 1,
        "step_patches": [],
        "tasks_patch": {
            "mode": "replace_all",
            "carried_task_ids": carried_task_ids,
            "entries": entries,
        },
    }


def _append_patch(entries, expected_next_task_id="task0010"):
    return {
        "base_input_digest": VWO.normalize_json_sha256(_digest_source()),
        "base_workflow_blob": "8f17c04",
        "operation": "append_rework",
        "patch_id": "rework-p0001",
        "preserve": ["workflow.implement.base_commit"],
        "requirements_patch": None,
        "schema_version": 1,
        "step_patches": [
            {
                "expected": {"status": "completed"},
                "set": {"status": "pending"},
                "step_id": "implement",
            }
        ],
        "tasks_patch": {
            "mode": "append",
            "expected_next_task_id": expected_next_task_id,
            "entries": entries,
        },
    }


def _append_entry(**extra):
    return _new_entry(
        provenance={"review_round": 2, "source": "review", "source_ids": ["abc123"]},
        **extra,
    )


def _validate(patch, workflow, *, phase_state=None, dry_run=True):
    return VWO.validate_workflow_patch(
        patch,
        workflow=workflow,
        digest_source=_digest_source(),
        phase_state=phase_state,
        dry_run=dry_run,
    )


def _replanning_workflow(**task_extra):
    return _workflow({"task0009": _task(**task_extra)})


def _append_workflow(**task_extra):
    return _workflow(
        {"task0009": _task(**task_extra)}, implement_status="completed"
    )


# ---------------------------------------------------------------------------
# AC-4: apply_patch carries the record verbatim
# ---------------------------------------------------------------------------


class TestApplyPatchKeepsTheRecordOnCarriedTasks(unittest.TestCase):
    """AC-4 (FR12): `apply_patch`'s `replace_planning` arm deep-copies each
    carried task's record, so the record survives a re-plan without entering
    the `preserve` vocabulary."""

    def _applied(self):
        workflow = _workflow(
            {
                "task0001": _task(**{RECORD_FIELD: 7}),
                "task0002": _task(),
                "task0003": _task(**{RECORD_FIELD: None}),
            }
        )
        patch = _replace_all_patch(["task0001", "task0002", "task0003"], {})
        return workflow, VWO.apply_patch(workflow, patch)

    def test_carried_task_with_an_integer_record_keeps_the_value(self):
        _, applied = self._applied()
        self.assertEqual(applied["tasks"]["task0001"][RECORD_FIELD], 7)

    def test_carried_task_without_the_key_still_lacks_it(self):
        _, applied = self._applied()
        self.assertNotIn(RECORD_FIELD, applied["tasks"]["task0002"])

    def test_carried_task_with_null_keeps_null(self):
        _, applied = self._applied()
        self.assertIn(RECORD_FIELD, applied["tasks"]["task0003"])
        self.assertIsNone(applied["tasks"]["task0003"][RECORD_FIELD])

    def test_whole_carried_records_are_equal_to_the_pre_apply_records(self):
        workflow, applied = self._applied()
        for task_id in ("task0001", "task0002", "task0003"):
            with self.subTest(task_id=task_id):
                self.assertEqual(applied["tasks"][task_id], workflow["tasks"][task_id])

    def test_applied_workflow_does_not_share_the_record_with_the_original(self):
        workflow, applied = self._applied()
        applied["tasks"]["task0001"][RECORD_FIELD] = 99
        self.assertEqual(workflow["tasks"]["task0001"][RECORD_FIELD], 7)


# ---------------------------------------------------------------------------
# AC-5: the validator rejects the record in worker entries
# ---------------------------------------------------------------------------


class TestValidatorRejectsTheRecordInWorkerEntries(unittest.TestCase):
    """AC-5 (FR13, TM-1): any `tasks_patch.entries` entry carrying the key is
    rejected, whatever its value, under both modes, with a machine-readable
    error whose code names the field. Asserts the error code, never the
    message text."""

    def _replace_all_errors(self, entry):
        patch = _replace_all_patch(["task0009"], {"task0010": entry})
        return _validate(
            patch, _replanning_workflow(), phase_state=_replanning_phase_state()
        )

    def _append_errors(self, entry):
        patch = _append_patch({"task0010": entry})
        return _validate(patch, _append_workflow())

    def _assert_rejected_alone(self, errors):
        codes = [e["code"] for e in errors]
        self.assertEqual(codes, [RECORD_ERROR_CODE])
        for e in errors:
            self.assertIn("message", e)

    def test_replace_all_entry_with_an_integer_record_is_rejected(self):
        errors = self._replace_all_errors(_new_entry(**{RECORD_FIELD: 5}))
        self._assert_rejected_alone(errors)

    def test_replace_all_entry_with_a_null_record_is_rejected(self):
        errors = self._replace_all_errors(_new_entry(**{RECORD_FIELD: None}))
        self._assert_rejected_alone(errors)

    def test_append_entry_with_an_integer_record_is_rejected(self):
        errors = self._append_errors(_append_entry(**{RECORD_FIELD: 5}))
        self._assert_rejected_alone(errors)

    def test_append_entry_with_a_null_record_is_rejected(self):
        errors = self._append_errors(_append_entry(**{RECORD_FIELD: None}))
        self._assert_rejected_alone(errors)

    def test_rejection_is_specific_to_the_key(self):
        """The same patches without the key pass: the rejection above is
        caused by the key, not by the harness."""
        self.assertEqual(self._replace_all_errors(_new_entry()), [])
        self.assertEqual(self._append_errors(_append_entry()), [])

    def test_any_value_shape_is_rejected(self):
        for value in (0, 1, "5", True, [], {}, -3, 2.5):
            with self.subTest(value=value):
                errors = self._replace_all_errors(
                    _new_entry(**{RECORD_FIELD: value})
                )
                self.assertEqual([e["code"] for e in errors], [RECORD_ERROR_CODE])

    def test_initial_planning_replace_all_entry_is_rejected(self):
        """replace_all with no registered task (Initial-planning path)."""
        workflow = _workflow({})
        entry = _new_entry(plan="tasks/task0001.md", **{RECORD_FIELD: 5})
        patch = _replace_all_patch([], {"task0001": entry})
        errors = _validate(patch, workflow)
        self.assertEqual([e["code"] for e in errors], [RECORD_ERROR_CODE])
        control = _replace_all_patch(
            [], {"task0001": _new_entry(plan="tasks/task0001.md")}
        )
        self.assertEqual(_validate(control, workflow), [])

    def test_rejection_does_not_depend_on_dry_run_apply(self):
        patch = _replace_all_patch(
            ["task0009"], {"task0010": _new_entry(**{RECORD_FIELD: 5})}
        )
        errors = VWO.validate_workflow_patch(patch, workflow=_replanning_workflow())
        self.assertIn(RECORD_ERROR_CODE, [e["code"] for e in errors])

    def test_each_offending_entry_is_reported(self):
        patch = _replace_all_patch(
            ["task0009"],
            {
                "task0010": _new_entry(**{RECORD_FIELD: 5}),
                "task0011": _new_entry(plan="tasks/task0011.md", **{RECORD_FIELD: None}),
            },
        )
        errors = _validate(
            patch, _replanning_workflow(), phase_state=_replanning_phase_state()
        )
        self.assertEqual([e["code"] for e in errors], [RECORD_ERROR_CODE] * 2)


# ---------------------------------------------------------------------------
# AC-6: valid patches without the key still pass
# ---------------------------------------------------------------------------


class TestPatchesWithoutTheKeyStillPass(unittest.TestCase):
    """AC-6 (FR13, NFR3)."""

    def test_valid_replace_all_without_the_key_passes(self):
        patch = _replace_all_patch(["task0009"], {"task0010": _new_entry()})
        errors = _validate(
            patch, _replanning_workflow(), phase_state=_replanning_phase_state()
        )
        self.assertEqual(errors, [])

    def test_valid_append_without_the_key_passes(self):
        patch = _append_patch({"task0010": _append_entry()})
        self.assertEqual(_validate(patch, _append_workflow()), [])

    def test_carried_task_holding_a_record_is_unaffected_by_validation(self):
        """Carried ids never reach entry validation: a workflow task that
        carries the record is carried through a re-plan without error."""
        workflow = _replanning_workflow(**{RECORD_FIELD: 7})
        patch = _replace_all_patch(["task0009"], {"task0010": _new_entry()})
        errors = _validate(
            patch, workflow, phase_state=_replanning_phase_state()
        )
        self.assertEqual(errors, [])
        applied = VWO.apply_patch(workflow, patch)
        self.assertEqual(applied["tasks"]["task0009"][RECORD_FIELD], 7)
        self.assertNotIn(RECORD_FIELD, applied["tasks"]["task0010"])

    def test_validate_task_entry_alone_accepts_a_valid_entry(self):
        for mode, entry in (("replace_all", _new_entry()), ("append", _append_entry())):
            with self.subTest(mode=mode):
                self.assertEqual(
                    VWO.validate_task_entry("task0010", entry, mode, None, None), []
                )

    def test_validate_task_entry_alone_rejects_the_key_in_both_modes(self):
        for mode, entry in (
            ("replace_all", _new_entry(**{RECORD_FIELD: 5})),
            ("append", _append_entry(**{RECORD_FIELD: 5})),
        ):
            with self.subTest(mode=mode):
                codes = [
                    e["code"]
                    for e in VWO.validate_task_entry("task0010", entry, mode, None, None)
                ]
                self.assertEqual(codes, [RECORD_ERROR_CODE])


# ---------------------------------------------------------------------------
# AC-7: standard library only
# ---------------------------------------------------------------------------


class TestModuleImportsOnlyStandardLibrary(unittest.TestCase):
    def test_module_uses_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        allowed = {"ast", "copy", "importlib", "re", "unittest", "pathlib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name.split(".")[0], allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn((node.module or "").split(".")[0], allowed)


if __name__ == "__main__":
    unittest.main()
