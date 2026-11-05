"""Document contract tests for task0004 (subagent-report-write-block): the
final-path correction contract and the validator call sites.

Covers task0004 Acceptance Criteria
(feature-docs/subagent-report-write-block/tasks/task0004.md):

- AC-1: `TestPatchFieldAndPermissionStates` -- workflow-patch.md defines
  `path_corrections` and the permission states; `All eighteen rules apply`
  and the protocol-error sentence stay as they are.
- AC-2: `TestFinalPathCorrectionConditions` -- the section states the five
  conditions, the not-applied rule and condition 5's comparison.
- AC-3: `TestFinalPathCorrectionOwnershipAndApplication` -- ownership, the
  handling of references in tests, the application effects, and the
  route-back re-planning.
- AC-4: `TestSchemaFailedEntryRestorationAndMarker` -- workflow-schema.md
  carries the Failed-entry restoration paragraph and the notes marker, with
  the pinned sentences of the record unchanged.
- AC-5: `TestValidatorCallSites` -- create-plan-phase.md's canonical
  invocation and rework-task-synthesis.md Section 10 pass the two base
  values; section 9 and Section 12 list the new checks.
- AC-6: `TestFinalPathCorrectionDispatchSection` -- `## 13. Final-path
  correction dispatch` states the dispatch, the record, the restart rule
  and the failure outcome.

Convention: standard library `unittest` only; every assertion reads the
section it concerns (never the whole document) on whitespace-normalized
text; every new-wording matcher has a negative proof against a synthetic
pre-change wording. No test writes under `em-workflow/`.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PATCH_DOC = PLUGIN_ROOT / "references" / "workflow-patch.md"
SCHEMA_DOC = PLUGIN_ROOT / "references" / "workflow-schema.md"
CREATE_PLAN_DOC = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
REWORK_DOC = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"

SECTION_HEADING = "## Final-path correction"
OWNERSHIP_HEADING = "## Ownership boundary"
RECOVERY_HEADING = "## Interrupted authorization-spend recovery"
RULES_HEADING = "## Application rules (in order)"
DISPATCH_HEADING = "## 13. Final-path correction dispatch"
ROUTEBACK_HEADING = "## `routeback_failed_journal_line`"
MARKER_HEADING = "## `tasks.{T}.notes` marker"
SIBLING_HEADING = "## Sibling artifacts"
STEP_A6_HEADING = "`## Step A.6: failed からの入口`"
FENCE = "`" * 3


# ---------------------------------------------------------------------------
# Wording constants: each is read by its positive test and its negative proof
# ---------------------------------------------------------------------------

ALL_EIGHTEEN = "All eighteen rules apply, in order, to every patch:"
PROTOCOL_ERROR_SENTENCE = (
    "A `replace_all` received while any task is `in_progress` or `failed` is a "
    "protocol error on BOTH paths above. Neither this protocol-error rule nor "
    "the Initial-planning path's floor condition above changes as a result of "
    "the Re-planning path's widening."
)
OLD_TWO_PATHS_INTRO = (
    "`replace_all` is permitted through exactly two paths; a patch matching "
    "neither is rejected:"
)
OLD_VERBATIM_END = (
    "a `merged` task keeps its `status`, its `branch` and its `files` across "
    "the patch without either field entering the `preserve` vocabulary."
)
OLD_NOTES_LINE = (
    "    notes: null                    # set on failure (reason; feeds re-planning)"
)
OLD_CANONICAL_BLOCK = (
    "python3 scripts/validate-worker-output.py \\\n"
    "    --kind worker-result \\\n"
    "    --digest-source {digest-source.json} \\\n"
    "    --dry-run-apply\n"
)
OLD_ROUTEBACK_TAIL = (
    "**Readers.** I.2.a selection, I.2.b step 1 reconcile and "
    "`queue_stop_guard.py` read it. `references/implement-phase.md` owns how "
    "they use it and is not restated here."
)

RESTORATION_LABEL = "**Failed-entry restoration.**"
WRITER_SENTENCE = (
    "**Writer.** The orchestrator is the sole writer, inside Step I.2.c's "
    "route-back write set. A reset task with no journal event gets no record. "
    "Scripts, hooks and worker patches never write it."
)
LIFECYCLE_SENTENCE = (
    "**Lifecycle.** It is not rewritten by the I.2.a launch-state commit, "
    "I.2.b step 3, a retry or a terminal-status write. It is overwritten only "
    "by a later route-back of the same task. Nothing clears it."
)
MARKER_LITERAL = "report-name-write-rejected:"

CONDITION_CODES = (
    "path-correction-in-flight",
    "path-correction-merged",
    "path-correction-old-path",
    "path-correction-new-path",
    "path-correction-content",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _has(text, *needles):
    flat = _norm(text)
    return all(_norm(n) in flat for n in needles)


def _missing(text, needles):
    """The needles the normalized text does not hold."""
    flat = _norm(text)
    return [n for n in needles if n not in flat]


def _lines_outside_fences(text):
    """[(offset, line)] for every line that is not inside a fenced block."""
    out = []
    in_fence = False
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(FENCE):
            in_fence = not in_fence
        elif not in_fence:
            out.append((offset, line))
        offset += len(line)
    return out


def _h2_headings(text):
    return [
        line.rstrip("\n")
        for _offset, line in _lines_outside_fences(text)
        if line.startswith("## ")
    ]


def _h2_section(text, heading):
    """Text from the `heading` line up to the next `## ` heading outside a
    fenced block (or the end of the document). Raises when absent."""
    heads = [
        (offset, line.rstrip("\n"))
        for offset, line in _lines_outside_fences(text)
        if line.startswith("## ")
    ]
    for i, (offset, line) in enumerate(heads):
        if line == heading:
            end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
            return text[offset:end]
    raise AssertionError("heading not found: %r" % heading)


def _between(text, start, end):
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


def _paragraph_with(text, *tokens):
    """The first blank-line-separated paragraph (normalized) that holds
    every token."""
    for para in re.split(r"\n\s*\n", text):
        flat = _norm(para)
        if all(t in flat for t in tokens):
            return flat
    raise AssertionError("no paragraph holds %r" % (tokens,))


def _sentence_with(text, *tokens):
    """The first sentence of the normalized text that holds every token."""
    flat = _norm(text)
    for sent in re.split(r"(?<=[.:;])\s+", flat):
        if all(t in sent for t in tokens):
            return sent
    raise AssertionError("no sentence holds %r" % (tokens,))


def _numbered_items(text):
    """{n: normalized item text} for a `1.`-style list at column 0, with
    indented continuation lines."""
    items = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m:
            current = int(m.group(1))
            items[current] = m.group(2)
        elif current is not None and line.startswith("   ") and line.strip():
            items[current] += " " + line.strip()
        else:
            current = None
    return {n: _norm(t) for n, t in items.items()}


def _bullets(text):
    """Top-level `- ` bullets (normalized), continuation lines joined."""
    return [_norm(b) for b in re.split(r"\n(?=- )", text) if b.startswith("- ")]


def _patch_text():
    return _read(PATCH_DOC)


def _correction_section():
    return _h2_section(_patch_text(), SECTION_HEADING)


def _permission_text():
    return _between(
        _patch_text(),
        "### `replace_all` permission conditions",
        "### Re-planning task-id allocation",
    )


def _allocation_text():
    return _between(
        _patch_text(), "### Re-planning task-id allocation", "### `append` requirements"
    )


# -- matchers that have a negative proof ------------------------------------


def _correction_entry_sentence_defects(permission_text):
    """What is wrong with the sentence after the protocol-error sentence that
    names the correction entry. Empty when it is right."""
    flat = _norm(permission_text)
    pinned = _norm(PROTOCOL_ERROR_SENTENCE)
    if pinned not in flat:
        return ["the protocol-error sentence is missing or changed"]
    after = flat.split(pinned, 1)[1]
    try:
        sentence = _sentence_with(after, "`## Final-path correction`")
    except AssertionError:
        return ["no sentence after it names the section"]
    return [
        "sentence lacks %r" % n
        for n in (
            "correction entry",
            "`failed` task is not a protocol error",
            "`in_progress`",
        )
        if n not in sentence
    ]


def _two_paths_intro_defects(permission_text):
    try:
        intro = _paragraph_with(permission_text, "exactly two paths")
    except AssertionError:
        return ["the 'exactly two paths' sentence is missing"]
    return [
        "intro lacks %r" % n
        for n in (
            "`## Final-path correction`",
            "`tasks_patch.path_corrections`",
            "a patch matching none of these is rejected",
        )
        if n not in intro
    ]


def _verbatim_pointer_defects(allocation_text):
    flat = _norm(allocation_text)
    if _norm(OLD_VERBATIM_END) not in flat:
        return ["the carried-verbatim text is missing or changed"]
    after = flat.split(_norm(OLD_VERBATIM_END), 1)[1]
    try:
        sentence = _sentence_with(after, "`## Final-path correction`")
    except AssertionError:
        return ["no sentence after the verbatim text names the section"]
    return [
        "sentence lacks %r" % n for n in ("exception", "verbatim") if n not in sentence
    ]


def _canonical_block_defects(block):
    defects = []
    for needle in (
        "--target-repo {integration worktree}",
        "--base-commit {integration tip}",
        "--digest-source {digest-source.json}",
    ):
        if needle not in block:
            defects.append("block lacks %r" % needle)
    flag_lines = [l for l in block.splitlines() if l.strip().startswith("--")]
    for line in flag_lines[:-1]:
        if not line.rstrip().endswith("\\"):
            defects.append("flag line does not continue: %r" % line)
    if not flag_lines or flag_lines[-1].strip() != "--dry-run-apply":
        defects.append("the last flag is not --dry-run-apply")
    return defects


def _notes_line_defects(structure_text):
    lines = structure_text.splitlines()
    idx = [i for i, l in enumerate(lines) if l.lstrip().startswith("notes: null")]
    if len(idx) != 1:
        return ["expected one notes line, found %d" % len(idx)]
    window = _norm(" ".join(lines[idx[0] : idx[0] + 4]))
    defects = [
        "window lacks %r" % n
        for n in (
            "set on failure (reason; feeds re-planning)",
            MARKER_LITERAL,
            MARKER_HEADING,
        )
        if n not in window
    ]
    branch = [i for i, l in enumerate(lines) if l.lstrip().startswith("branch:")]
    if not branch or branch[0] <= idx[0]:
        defects.append("the branch line no longer follows the notes line")
    return defects


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------


class TestPatchFieldAndPermissionStates(unittest.TestCase):
    """AC-1 (TS-22, TM-6)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _patch_text()
        cls.tasks_patch = _between(
            cls.text, "## `tasks_patch`", "### `replace_all` permission conditions"
        )
        cls.permission = _permission_text()
        cls.allocation = _allocation_text()
        cls.section = _correction_section()

    def test_tasks_patch_describes_the_field_and_its_shape(self):
        para = _paragraph_with(self.tasks_patch, "`tasks_patch.path_corrections`")
        self.assertEqual(
            _missing(
                para,
                (
                    "`replace_planning`",
                    "`task_id`",
                    "`old_path`",
                    "`new_path`",
                    "non-empty list of mappings",
                    "`carried_task_ids`",
                    "`## Final-path correction`",
                ),
            ),
            [],
        )

    def test_section_states_the_field_shape_rules(self):
        para = _paragraph_with(
            self.section, "exactly `task_id`, `old_path` and `new_path`"
        )
        self.assertEqual(
            _missing(
                para,
                (
                    "non-empty list of mappings",
                    "`replace_planning` only",
                    "listed in `carried_task_ids`",
                    "differs from `old_path`",
                    "`path-correction-shape`",
                ),
            ),
            [],
        )

    def test_the_correction_entry_state(self):
        rows = [
            l for l in self.section.splitlines() if "`implement` is `failed`" in l
        ]
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(
            _missing(
                rows[0],
                (
                    "`create-plan` is `completed`",
                    "Admitted",
                    "carry-over and `preserve` obligations of the Re-planning path apply",
                    "A `failed` task is permitted",
                    "an `in_progress` task stays rejected as `replace-all-not-permitted`",
                    "`step_patches` must be empty",
                    "`path-correction-step-patches`",
                ),
            ),
            [],
        )

    def test_the_replanning_path_state_includes_route_back(self):
        rows = [l for l in self.section.splitlines() if l.startswith("| The Re-planning path")]
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(
            _missing(rows[0], ("route back", "Admitted", "that path's existing rules")),
            [],
        )

    def test_the_initial_planning_path_state_is_rejected(self):
        rows = [l for l in self.section.splitlines() if l.startswith("| The Initial-planning path")]
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(
            _missing(rows[0], ("Rejected", "`path-correction-not-permitted`")), []
        )

    def test_a_replace_all_without_the_field_behaves_as_before(self):
        self.assertTrue(
            _has(
                self.section,
                "A `replace_all` without `path_corrections` behaves as before in every state.",
            )
        )

    def test_all_eighteen_rules_sentence_is_unchanged_and_there_are_eighteen(self):
        rules = _h2_section(self.text, RULES_HEADING)
        self.assertEqual(rules.count(ALL_EIGHTEEN), 1)
        numbers = sorted(int(m.group(1)) for m in re.finditer(r"^(\d+)\. ", rules, re.M))
        self.assertEqual(numbers, list(range(1, 19)))

    def test_protocol_error_sentence_is_unchanged_and_the_correction_entry_is_named(self):
        self.assertEqual(_correction_entry_sentence_defects(self.permission), [])

    def test_exactly_two_paths_wording_admits_the_section(self):
        self.assertEqual(_two_paths_intro_defects(self.permission), [])
        self.assertNotIn(_norm(OLD_TWO_PATHS_INTRO), _norm(self.permission))

    def test_both_existing_path_bullets_are_still_present(self):
        self.assertIn("- **Initial-planning path**", self.permission)
        self.assertIn("- **Re-planning path**", self.permission)

    def test_verbatim_text_points_at_the_section(self):
        self.assertEqual(_verbatim_pointer_defects(self.allocation), [])

    def test_section_sits_directly_before_ownership_boundary_and_adds_no_numbered_rule(self):
        heads = _h2_headings(self.text)
        self.assertEqual(heads.count(SECTION_HEADING), 1)
        self.assertEqual(heads.index(OWNERSHIP_HEADING) - heads.index(SECTION_HEADING), 1)
        self.assertLess(heads.index(RECOVERY_HEADING), heads.index(SECTION_HEADING))
        self.assertNotRegex(self.section, r"(?m)^19\. ")

    # -- negative proofs ----------------------------------------------------

    def test_negative_pre_change_permission_text_is_rejected_by_the_matchers(self):
        pre_change = PROTOCOL_ERROR_SENTENCE + "\n\n" + OLD_TWO_PATHS_INTRO
        self.assertNotEqual(_correction_entry_sentence_defects(pre_change), [])
        self.assertNotEqual(_two_paths_intro_defects(pre_change), [])

    def test_negative_pre_change_allocation_text_is_rejected_by_the_matcher(self):
        self.assertNotEqual(_verbatim_pointer_defects(OLD_VERBATIM_END), [])

    def test_negative_a_changed_protocol_error_sentence_is_rejected(self):
        changed = PROTOCOL_ERROR_SENTENCE.replace("BOTH paths", "either path")
        self.assertNotEqual(_correction_entry_sentence_defects(changed), [])

    def test_matchers_hold_on_the_unchanged_anchors(self):
        # Non-vacuity: the pre-change samples are the live text minus the new
        # sentences, so the anchors they share with the live text are real.
        self.assertIn(_norm(PROTOCOL_ERROR_SENTENCE), _norm(self.permission))
        self.assertIn(_norm(OLD_VERBATIM_END), _norm(self.allocation))


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------


class TestFinalPathCorrectionConditions(unittest.TestCase):
    """AC-2 (TS-10, TM-4, TM-5)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _correction_section()
        cls.conditions = _between(cls.section, "**Conditions.**", "**Comparison")
        cls.items = _numbered_items(cls.conditions)
        cls.comparison = _between(cls.section, "**Comparison", "**Ownership.**")

    def test_five_conditions_are_numbered_in_order(self):
        self.assertEqual(sorted(self.items), [1, 2, 3, 4, 5])

    def test_each_condition_carries_its_validator_code(self):
        for number, code in enumerate(CONDITION_CODES, start=1):
            self.assertTrue(self.items[number].startswith("`%s`" % code), self.items[number])

    def test_condition_1_no_task_in_flight(self):
        self.assertEqual(
            _missing(self.items[1], ("No task is in flight", "`in_progress`", "`launched`")),
            [],
        )

    def test_condition_2_target_is_not_merged(self):
        self.assertEqual(
            _missing(
                self.items[2],
                ("target task's `status`", "last journal event", "`merged`"),
            ),
            [],
        )

    def test_condition_3_old_path(self):
        self.assertEqual(
            _missing(
                self.items[3],
                (
                    "`old_path` is in the target task's `files`",
                    "a matching name",
                    "no entry at the base commit",
                ),
            ),
            [],
        )

    def test_condition_4_new_path(self):
        self.assertEqual(
            _missing(
                self.items[4],
                (
                    "`new_path` is not a matching name",
                    "application rule 7",
                    "no entry at the base commit",
                ),
            ),
            [],
        )

    def test_condition_5_limited_to_path_strings(self):
        self.assertEqual(
            _missing(
                self.items[5],
                (
                    "limited to replacing path strings",
                    "does not change the meaning of requirements or acceptance criteria",
                ),
            ),
            [],
        )

    def test_all_conditions_are_required_and_a_failing_correction_is_not_applied(self):
        self.assertTrue(_has(self.conditions, "All five are required"))
        sentence = _sentence_with(self.conditions, "is not applied")
        self.assertIn("any condition", sentence)
        self.assertTrue(_has(self.conditions, "`workflow.yaml` is not changed"))

    def test_base_inputs_are_stated(self):
        self.assertEqual(
            _missing(
                self.conditions,
                (
                    "integration worktree",
                    "full commit ID",
                    "`--target-repo`",
                    "`--base-commit`",
                    "`--journal`",
                    "execution error (exit 2), never a pass",
                ),
            ),
            [],
        )

    def test_comparison_documents_and_normalization(self):
        self.assertEqual(
            _missing(
                self.comparison,
                (
                    "IMPLEMENTATION.md, VERIFICATION.md and each target task's plan",
                    "the version at the base commit and the current version",
                    "a single left-to-right pass",
                    "replaces each old path by its new path",
                    "each old file name by its new file name",
                    "longer match first",
                    "The two results must be equal",
                    "the current version must not contain an old path",
                ),
            ),
            [],
        )

    def test_comparison_set_exclusions(self):
        self.assertEqual(
            _missing(
                self.comparison,
                (
                    "A document absent at the base commit is outside the set",
                    "New task plans under `entries` are outside the set",
                ),
            ),
            [],
        )

    def test_negative_a_document_without_the_section_fails_the_locator(self):
        with self.assertRaises(AssertionError):
            _h2_section("# Doc\n\n## Ownership boundary\n\ntext\n", SECTION_HEADING)

    def test_negative_a_conditions_list_missing_one_is_detected(self):
        forged = re.sub(r"(?m)^5\. .*\n(   .*\n)*", "", self.conditions)
        self.assertEqual(sorted(_numbered_items(forged)), [1, 2, 3, 4])


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------


class TestFinalPathCorrectionOwnershipAndApplication(unittest.TestCase):
    """AC-3 (FR5)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _correction_section()
        cls.ownership = _between(cls.section, "**Ownership.**", "**References in tests.**")
        cls.references = _between(cls.section, "**References in tests.**", "**Application.**")
        cls.application = _between(cls.section, "**Application.**", "**Where it applies.**")
        cls.where = cls.section[cls.section.index("**Where it applies.**") :]

    def test_ownership(self):
        self.assertEqual(
            _missing(
                self.ownership,
                (
                    "`implementation-planner` corrects the plan documents and proposes "
                    "`files` through `path_corrections`",
                    "the orchestrator applies the patch to `workflow.yaml`",
                    "The implementer and `rework-planner` do not correct the plan",
                ),
            ),
            [],
        )

    def test_references_in_tests(self):
        self.assertEqual(
            _missing(
                self.references,
                (
                    "An unmerged reference is corrected by that task's implementer",
                    "following the corrected plan",
                    "A merged reference is corrected by a new task",
                    "registered under `entries` in the same correction",
                ),
            ),
            [],
        )

    def test_application_effects(self):
        self.assertEqual(
            _missing(
                self.application,
                (
                    "`files` entry equal to `old_path` is replaced by `new_path` at "
                    "the same list position",
                    "`notes` is set to null",
                    "every other field is copied verbatim",
                ),
            ),
            [],
        )

    def test_applies_in_replanning_entered_through_route_back(self):
        self.assertEqual(
            _missing(
                self.where,
                (
                    "re-planning entered through route back",
                    "carries a task that is not `merged`",
                    "corrects it through the same field",
                ),
            ),
            [],
        )

    def test_section_cites_the_naming_rule_without_restating_the_regex(self):
        self.assertIn("`## Report Artifact Names`", self.section)
        self.assertNotIn("REPORT|SUMMARY", self.section)

    def test_negative_ownership_matcher_rejects_an_implementer_that_corrects(self):
        forged = _norm(self.ownership).replace(
            "The implementer and `rework-planner` do not correct the plan",
            "The implementer corrects the plan",
        )
        self.assertNotEqual(
            _missing(forged, ("The implementer and `rework-planner` do not correct the plan",)),
            [],
        )

    def test_negative_application_matcher_rejects_a_kept_notes_value(self):
        forged = _norm(self.application).replace("`notes` is set to null", "`notes` is kept")
        self.assertNotEqual(_missing(forged, ("`notes` is set to null",)), [])


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------


class TestSchemaFailedEntryRestorationAndMarker(unittest.TestCase):
    """AC-4 (TS-13)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_DOC)
        cls.record = _h2_section(cls.text, ROUTEBACK_HEADING)
        cls.marker = _h2_section(cls.text, MARKER_HEADING)
        cls.structure = _h2_section(cls.text, "## Full structure")

    def test_restoration_paragraph_names_the_second_write_site(self):
        para = _paragraph_with(self.record, RESTORATION_LABEL)
        self.assertEqual(
            _missing(
                para,
                (
                    STEP_A6_HEADING,
                    "the one other write site of this record",
                    "the orchestrator's as well",
                    "writes the same record",
                    "under the Value, Line counting and Canonical form rules above",
                    "when that line is not null",
                ),
            ),
            [],
        )

    def test_restoration_paragraph_names_itself_as_the_exception(self):
        para = _paragraph_with(self.record, RESTORATION_LABEL)
        self.assertEqual(
            _missing(
                para,
                ("the one exception to the **Writer** and **Lifecycle** statements above",),
            ),
            [],
        )

    def test_pinned_writer_and_lifecycle_sentences_are_unchanged(self):
        flat = _norm(self.record)
        self.assertIn(_norm(WRITER_SENTENCE), flat)
        self.assertIn(_norm(LIFECYCLE_SENTENCE), flat)

    def test_restoration_paragraph_sits_after_the_pinned_ones(self):
        flat = _norm(self.record)
        self.assertLess(flat.index(_norm(LIFECYCLE_SENTENCE)), flat.index(RESTORATION_LABEL))
        self.assertLess(flat.index(_norm(OLD_ROUTEBACK_TAIL)), flat.index(RESTORATION_LABEL))

    def test_restoration_paragraph_does_not_restate_the_classification(self):
        for marker in ("unlaunched", "carve-out", "three-condition"):
            self.assertNotIn(marker, self.record)

    def test_marker_section_is_between_the_record_section_and_sibling_artifacts(self):
        heads = _h2_headings(self.text)
        self.assertEqual(heads.count(MARKER_HEADING), 1)
        self.assertLess(heads.index(ROUTEBACK_HEADING), heads.index(MARKER_HEADING))
        self.assertLess(heads.index(MARKER_HEADING), heads.index(SIBLING_HEADING))

    def test_marker_section_defines_the_marker(self):
        self.assertEqual(
            _missing(
                self.marker,
                (
                    "begins with the literal `%s`" % MARKER_LITERAL,
                    "followed by the target path and the rejection text",
                    "The target path is repository-relative",
                    "writes the marker only in the wake commit",
                    "`references/implement-phase.md`",
                    "clears `notes` to null",
                    "`references/workflow-patch.md`",
                ),
            ),
            [],
        )

    def test_notes_line_of_the_structure_points_at_the_marker_section(self):
        self.assertEqual(_notes_line_defects(self.structure), [])

    # -- negative proofs ----------------------------------------------------

    def test_negative_pre_change_notes_line_is_rejected_by_the_matcher(self):
        pre_change = OLD_NOTES_LINE + "\n    branch: em-workflow/{feature}/task0001\n"
        self.assertNotEqual(_notes_line_defects(pre_change), [])

    def test_negative_pre_change_record_section_has_no_restoration_paragraph(self):
        with self.assertRaises(AssertionError):
            _paragraph_with(OLD_ROUTEBACK_TAIL, RESTORATION_LABEL)

    def test_negative_pre_change_schema_has_no_marker_section(self):
        with self.assertRaises(AssertionError):
            _h2_section("## `routeback_failed_journal_line`\n\ntext\n", MARKER_HEADING)


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------


class TestValidatorCallSites(unittest.TestCase):
    """AC-5 (FR4)."""

    @classmethod
    def setUpClass(cls):
        cls.plan = _read(CREATE_PLAN_DOC)
        cls.sec9 = _between(
            cls.plan, "## 9. Planning invariants", "## 10. Atomic patch application"
        )
        cls.canonical = _between(
            cls.sec9, "**Canonical validator invocation**", "The `--digest-source` file holds"
        )
        cls.after_canonical = cls.sec9[cls.sec9.index("The `--digest-source` file holds") :]
        cls.implemented = _between(
            cls.sec9, "mechanically implements only the", "The following are named as planning"
        )
        cls.rework = _read(REWORK_DOC)
        cls.rw10 = _between(
            cls.rework, "## 10. Workflow state transition", "## 11. Invariants"
        )
        cls.rw12 = _between(cls.rework, "## 12. Validation", "## 13. Execution adapter")

    def test_canonical_invocation_passes_the_two_base_values(self):
        block = self.canonical.split(FENCE)[1]
        self.assertEqual(_canonical_block_defects(block), [])

    def test_the_orchestrator_resolves_the_tip_just_before_validating(self):
        sentence = _sentence_with(self.after_canonical, "`--base-commit`", "just before")
        self.assertEqual(
            _missing(
                sentence,
                (
                    "The orchestrator resolves `--base-commit`",
                    "full commit ID",
                    "tip of the integration branch",
                    "just before it validates",
                ),
            ),
            [],
        )
        self.assertTrue(
            _has(self.after_canonical, "`--target-repo` is the integration worktree.")
        )

    def test_the_two_values_are_read_only_for_a_matching_name(self):
        sentence = _sentence_with(self.after_canonical, "read only when")
        self.assertEqual(
            _missing(sentence, ("`## Report Artifact Names`", "`skills/plan-writing/SKILL.md`")),
            [],
        )
        self.assertTrue(_has(self.after_canonical, "exits 2 and does not pass"))

    def test_section_9_lists_the_new_name_check(self):
        hits = [b for b in _bullets(self.implemented) if "`report-name-new-file`" in b]
        self.assertEqual(len(hits), 1, hits)
        self.assertEqual(
            _missing(
                hits[0],
                (
                    "`## Report Artifact Names`",
                    "`tasks_patch.entries`",
                    "not a regular file at the base commit",
                    "`--dry-run-apply`",
                    "carried tasks that are not `merged`",
                    "`--target-repo`",
                    "`--base-commit`",
                ),
            ),
            [],
        )
        self.assertNotIn("REPORT|SUMMARY", hits[0])

    def test_section_9_lists_the_correction_checks(self):
        hits = [b for b in _bullets(self.implemented) if "`tasks_patch.path_corrections`" in b]
        self.assertEqual(len(hits), 1, hits)
        self.assertEqual(
            _missing(
                hits[0],
                (
                    "`references/workflow-patch.md`",
                    "`## Final-path correction`",
                    "`--dry-run-apply`",
                    "`--journal`",
                    "`path-correction-in-flight`",
                    "`path-correction-content`",
                ),
            ),
            [],
        )

    def test_existing_section_9_bullets_are_kept(self):
        self.assertEqual(
            _missing(
                self.implemented,
                (
                    "Every task plan has a non-empty Acceptance Criteria section.",
                    "A task's `files` and its task plan's Files section agree as a union.",
                    "`scenario-id-form`",
                ),
            ),
            [],
        )

    def test_rework_section_10_step_3_passes_the_two_values(self):
        head = self.rw10[: self.rw10.index("**Verify-sourced rework**")]
        step3 = _numbered_items(head)[3]
        self.assertEqual(
            _missing(
                step3,
                (
                    "validates and applies rework-planner's patch",
                    "The validation passes `--target-repo` (the integration worktree)",
                    "`--base-commit` (the full commit ID of the tip of the integration branch",
                    "the same two values as the canonical invocation of "
                    "`references/phases/create-plan-phase.md` section 9",
                ),
            ),
            [],
        )

    def test_rework_section_12_lists_the_name_check(self):
        hits = [b for b in _bullets(self.rw12) if "`report-name-new-file`" in b]
        self.assertEqual(len(hits), 1, hits)
        self.assertEqual(
            _missing(
                hits[0],
                (
                    "`## Report Artifact Names`",
                    "`append_rework`",
                    "not a regular file at the base commit",
                    "Section 10 step 3",
                ),
            ),
            [],
        )
        self.assertNotIn("REPORT|SUMMARY", hits[0])

    # -- negative proofs ----------------------------------------------------

    def test_negative_pre_change_invocation_is_rejected_by_the_matcher(self):
        self.assertNotEqual(_canonical_block_defects(OLD_CANONICAL_BLOCK), [])

    def test_negative_a_block_with_a_broken_continuation_is_rejected(self):
        block = self.canonical.split(FENCE)[1].replace(
            "--base-commit {integration tip} \\", "--base-commit {integration tip}"
        )
        self.assertNotEqual(_canonical_block_defects(block), [])

    def test_negative_a_bullet_list_without_the_new_bullets_has_no_hit(self):
        old = _bullets(
            "- Every task plan has a non-empty Acceptance Criteria section.\n"
            "- A task's `files` and its task plan's Files section agree as a union.\n"
        )
        self.assertEqual([b for b in old if "`report-name-new-file`" in b], [])
        self.assertEqual([b for b in old if "`tasks_patch.path_corrections`" in b], [])


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------


class TestFinalPathCorrectionDispatchSection(unittest.TestCase):
    """AC-6 (TS-14)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_DOC)
        cls.section = _h2_section(cls.text, DISPATCH_HEADING)

    def test_section_is_the_last_one_and_follows_section_12(self):
        heads = _h2_headings(self.text)
        self.assertEqual(heads[-1], DISPATCH_HEADING)
        self.assertTrue(heads[-2].startswith("## 12. "), heads[-2])
        self.assertEqual(heads.count(DISPATCH_HEADING), 1)

    def test_it_names_where_it_is_run_from_and_cites_the_patch_contract(self):
        self.assertEqual(
            _missing(
                self.section,
                (
                    "`skills/develop/SKILL.md`'s %s" % STEP_A6_HEADING,
                    "`scripts/report-name-entry.py` returns `dispatch`",
                    "`references/workflow-patch.md`'s `## Final-path correction`",
                ),
            ),
            [],
        )

    def test_pre_dispatch(self):
        para = _paragraph_with(self.section, "**Pre-dispatch.**")
        self.assertEqual(
            _missing(
                para,
                (
                    "clean-worktree precondition",
                    "scope verification",
                    "`references/phases/create-spec-phase.md`",
                ),
            ),
            [],
        )

    def test_dispatch(self):
        para = _paragraph_with(self.section, "**Dispatch.**")
        self.assertEqual(
            _missing(
                para,
                (
                    '`Task(subagent_type="em-workflow:implementation-planner")`',
                    "`planning_inputs.path_correction`",
                    "`write_policy` of `references/contracts/planner-contract.md`",
                    "`tasks/` in `allowed_write_roots`",
                ),
            ),
            [],
        )

    def test_record_and_restart_rule(self):
        para = _paragraph_with(self.section, "**Record.**")
        self.assertEqual(
            _missing(
                para,
                (
                    "`phase-state/create-plan.yaml`",
                    "a new `request_id`",
                    "the next unused `patch_id`",
                    "`create-plan` step stays `completed`",
                    "Resume decision table does not re-enter this run",
                    "an interrupted correction restarts from Step A.6",
                ),
            ),
            [],
        )

    def test_validation(self):
        para = _paragraph_with(self.section, "**Validation.**")
        self.assertEqual(
            _missing(para, ("canonical invocation of section 9", "plus `--journal`")), []
        )

    def test_failure_outcome(self):
        para = _paragraph_with(self.section, "**Failure outcome.**")
        self.assertEqual(
            _missing(
                para,
                (
                    "Any result other than `completed`",
                    "any validator exit other than 0",
                    "any stale result ends the dispatch",
                    "the worker's writes are discarded",
                    "`workflow.yaml` is not changed",
                ),
            ),
            [],
        )

    def test_apply(self):
        para = _paragraph_with(self.section, "**Apply.**")
        self.assertEqual(
            _missing(
                para,
                (
                    "the artifact commit comes first",
                    "`skills/develop/SKILL.md`'s %s" % STEP_A6_HEADING,
                    "one Write in one commit, after the artifact commit",
                    "cannot leave corrected `files` with `implement: failed`",
                ),
            ),
            [],
        )

    def test_section_does_not_restate_the_naming_regex(self):
        self.assertNotIn("REPORT|SUMMARY", self.section)

    def test_negative_pre_change_document_has_no_section_13(self):
        with self.assertRaises(AssertionError):
            _h2_section("## 12. Declared change set derivation\n\ntext\n", DISPATCH_HEADING)

    def test_negative_a_failure_paragraph_that_keeps_the_writes_is_rejected(self):
        para = _paragraph_with(self.section, "**Failure outcome.**")
        forged = para.replace("the worker's writes are discarded", "the worker's writes are kept")
        self.assertNotEqual(_missing(forged, ("the worker's writes are discarded",)), [])


# ---------------------------------------------------------------------------
# Deliverable content (NFR6, NFR3)
# ---------------------------------------------------------------------------


class TestNewTextCarriesNoForbiddenContent(unittest.TestCase):
    """NFR6: no Notion URL and no absolute path under a home directory in the
    text this task adds; NFR3: the regex stays in plan-writing."""

    def test_new_sections_have_no_notion_url_home_path_or_regex(self):
        schema_record = _h2_section(_read(SCHEMA_DOC), ROUTEBACK_HEADING)
        restoration = _paragraph_with(schema_record, RESTORATION_LABEL)
        new_text = "\n".join(
            [
                _correction_section(),
                _h2_section(_read(CREATE_PLAN_DOC), DISPATCH_HEADING),
                _h2_section(_read(SCHEMA_DOC), MARKER_HEADING),
                restoration,
            ]
        )
        self.assertNotRegex(new_text, r"notion\.(so|site)")
        self.assertNotRegex(new_text, r"/home/|/Users/|~/")
        self.assertNotIn("REPORT|SUMMARY", new_text)
        self.assertNotIn("(REPORT", new_text)


if __name__ == "__main__":
    unittest.main()
