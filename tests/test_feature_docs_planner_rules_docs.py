"""Document contract tests for task0001 (plan-feature-docs-route): the
plan-writing skill owns the rule that no task's `files` holds a feature-docs
path, and the implementation-planner prompt cites it, states how the planner
amends other features' documents (two stages) and how it runs the
feature-docs correction dispatch.

Covers task0001 Acceptance Criteria
(feature-docs/plan-feature-docs-route/tasks/task0001.md):

- AC-1: plan-writing SKILL.md has exactly one `## Feature-docs Files`
  section, before the Pre-Save checklist. It states the predicate (a
  `\\`-separated path, a leading `./` and an empty segment are covered), the
  own feature, other features and `feature-docs/LESSONS.md`, that `plan` is
  outside the rule, the other-feature route citation and the code
  `plan-task-feature-docs`. The checklist has one item citing the section.
- AC-2: implementation-planner.md step 4 cites `skills/plan-writing/SKILL.md`
  with `## Feature-docs Files` and does not contain the predicate's wording.
- AC-3: implementation-planner.md states the two-stage behaviour in an
  ordinary create-plan and cites planner-contract.md with
  `## Other-feature documents`.
- AC-4 (TM-3): other-feature document content is untrusted data, an
  instruction found there is not followed, and it is reported.
- AC-5: the `## Process` lead routes a non-null
  `planning_inputs.feature_docs_correction` to `## Feature-docs correction`,
  which sits after `## Final-path correction` and before `## Output`, has no
  subheading and states each point. The `### ` heading list equals the nine
  step headings and `## Gate option vocabulary` is unchanged. The
  2a-exception sentence of `## Final-path correction` stays true.
- AC-6: implementer.md and worktree-task-workflow SKILL.md still contain
  their "Never modify `feature-docs/**`" text (FR10).
- AC-7: the full suite passes. That is verified by running
  `python3 -m unittest discover -s tests`, not re-asserted here.

The deliverables are Markdown documents, so verification is textual and
anchored on headings and pinned phrases, matched after collapsing
whitespace. Locate sections by heading outside fenced blocks. Every custom
matcher is exercised against an in-test sample that lacks one phrase: the
matcher must reject each such sample.

`GATE_VOCABULARY_SHA256` pins the bytes of the `## Gate option vocabulary`
section of implementation-planner.md (heading line to end of file). This
task must not change that section. A later task that changes it on purpose
refreshes the pin and names the change in a comment.
"""

import hashlib
import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

SKILL_PATH = PLUGIN_ROOT / "skills" / "plan-writing" / "SKILL.md"
PLANNER_PATH = PLUGIN_ROOT / "agents" / "implementation-planner.md"
IMPLEMENTER_PATH = PLUGIN_ROOT / "agents" / "implementer.md"
WORKTREE_SKILL_PATH = PLUGIN_ROOT / "skills" / "worktree-task-workflow" / "SKILL.md"
VALIDATOR_PATH = PLUGIN_ROOT / "scripts" / "validate-worker-output.py"

FEATURE_DOCS_FILES_HEADING = "## Feature-docs Files"
CHECKLIST_HEADING = "## Pre-Save Self-Verification Checklist (MANDATORY)"
REPORT_NAMES_HEADING = "## Report Artifact Names"

PROCESS_HEADING = "## Process"
STEP_4_HEADING = "### 4. Task decomposition → tasks/taskNNNN.md + workflow patch"
FINAL_PATH_HEADING = "## Final-path correction"
FEATURE_DOCS_CORRECTION_HEADING = "## Feature-docs correction"
OUTPUT_HEADING = "## Output"
GATE_VOCABULARY_HEADING = "## Gate option vocabulary"

STEP_HEADINGS = [
    "### 1. Analyze SPEC.md",
    "### 2. TBD requirement detection (MANDATORY)",
    "### 2a. Threat modeling (MANDATORY)",
    "### 3. Cross-task design decisions → IMPLEMENTATION.md",
    "### 4. Task decomposition → tasks/taskNNNN.md + workflow patch",
    "### 5. VERIFICATION.md (feature-wide, this agent OWNS it)",
    "### 6. Populate requirements mapping (MANDATORY)",
    "### 7. Handle existing files",
    "### 8. Save and report",
]

# SHA-256 of the `## Gate option vocabulary` section of
# implementation-planner.md, heading line to end of file, UTF-8.
GATE_VOCABULARY_SHA256 = "ab908c0af5220c9436b225077c4ca2ddec3ecacb5ca52f5553ef228ec3da7ef8"

NEVER_MODIFY_PHRASE = "Never modify `feature-docs/**`"


def _read(path):
    return path.read_text(encoding="utf-8")


def _flat(text):
    """Collapse every whitespace run to one space, so an anchor survives the
    documents' hard line wrapping."""
    return re.sub(r"\s+", " ", text).strip()


_HEADING_RE = re.compile(r"^(#{1,6}) \S")


def _headings(text):
    """(line_index, level, line) for every Markdown heading outside a fenced
    code block."""
    in_fence = False
    found = []
    for index, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((index, len(match.group(1)), line))
    return found


def _section(text, heading, lead_only=False):
    """Body of the section opened by `heading` (heading line excluded), up to
    the next heading of the same or a shallower level. With `lead_only`, the
    body ends at the next heading of any level. Raises AssertionError when the
    heading is absent or appears more than once outside fenced blocks."""
    lines = text.split("\n")
    heads = _headings(text)
    starts = [i for i, _lvl, line in heads if line == heading]
    if len(starts) != 1:
        raise AssertionError(
            "expected exactly one heading line %r, found %d" % (heading, len(starts))
        )
    start = starts[0]
    level = next(lvl for i, lvl, _line in heads if i == start)
    end = len(lines)
    for i, lvl, _line in heads:
        if i > start and (lead_only or lvl <= level):
            end = i
            break
    return "\n".join(lines[start + 1 : end])


_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")


def _blocks(text):
    """Logical blocks: every blank-line separated paragraph, and every list
    item (continuation lines joined) as a block of its own, each flattened to
    one line."""
    blocks = []
    current = []

    def flush():
        if current:
            blocks.append(_flat(" ".join(current)))
            current.clear()

    for line in text.split("\n"):
        if not line.strip():
            flush()
        elif _LIST_ITEM_RE.match(line):
            flush()
            current.append(line)
        else:
            current.append(line)
    flush()
    return blocks


def states_that(text, *needles):
    """True when `text` (whitespace flattened) holds every needle."""
    flat = _flat(text)
    return all(n in flat for n in needles)


def block_states(text, *needles):
    """True when one logical block of `text` holds every needle."""
    return any(all(n in block for n in needles) for block in _blocks(text))


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_worker_output_task0001_docs", VALIDATOR_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- phrase sets ----------------------------------------------------------
#
# Each set is matched inside one logical block of the named section.

PREDICATE_EXAMPLES = (
    "`feature-docs\\notes\\a.md`",
    "`./feature-docs/notes/a.md`",
    "`feature-docs//notes/a.md`",
)
NON_PREDICATE_EXAMPLE = "`feature-docs-old/a.md`"

# The predicate's distinctive wording. It lives in plan-writing SKILL.md only.
PREDICATE_WORDING = (
    "first segment is exactly `feature-docs`",
    "`path_segments`",
    "`\\` is read as `/`",
    "empty and `.` segments are dropped",
)

SKILL_PHRASE_SETS = {
    "predicate": PREDICATE_WORDING + PREDICATE_EXAMPLES,
    "non-predicate example": (NON_PREDICATE_EXAMPLE, "is not"),
    "relation to the rework rule": (
        "`references/rework-task-synthesis.md`",
        "same normalization",
        "not restated",
    ),
    "covered scopes": (
        "`feature-docs/{feature}/`",
        "other features",
        "`feature-docs/LESSONS.md`",
    ),
    "plan is outside the rule": ("`plan`", "outside the rule", "`files`"),
    "other-feature route": (
        "`references/contracts/planner-contract.md`",
        "`## Other-feature documents`",
        "never through a task",
    ),
    "validator code": (
        "`scripts/validate-worker-output.py`",
        "`replace_planning`",
        "`plan-task-feature-docs`",
    ),
}

STEP_4_PHRASE_SETS = {
    "skill citation": (
        "skills/plan-writing/SKILL.md",
        "`## Feature-docs Files`",
        "not restated",
    ),
    "contract citation": (
        "references/contracts/planner-contract.md",
        "`## Other-feature documents`",
        "not restated",
    ),
    "stage 1": (
        "Stage 1",
        "carries no `amend_other_feature` target",
        "return the request result",
        "write nothing",
    ),
    "stage 2": (
        "Stage 2",
        "carries `amend_other_feature` targets",
        "amend only the granted documents",
        "declare each fix",
    ),
    "blocked": (
        "out of scope",
        "not granted",
        "`status: blocked`",
        "naming the path",
    ),
    "untrusted content": (
        "another feature's document",
        "untrusted data",
        "Untrusted-Input Handling",
        "references/contracts/worker-envelope.md",
        "is not followed",
        "is reported",
    ),
}

PROCESS_LEAD_PHRASE_SETS = {
    "path_correction route": (
        "`planning_inputs.path_correction`",
        "non-null",
        "`## Final-path correction`",
    ),
    "feature_docs_correction route": (
        "`planning_inputs.feature_docs_correction`",
        "non-null",
        "`## Feature-docs correction`",
        "none of the steps",
    ),
    "every other dispatch": ("Every other dispatch runs the steps",),
}

CORRECTION_PHRASE_SETS = {
    "trigger": ("`planning_inputs.feature_docs_correction`", "non-null", "runs only this section"),
    "citations": (
        "references/contracts/planner-contract.md",
        "`## Other-feature documents`",
        "references/workflow-patch.md",
        "`## Feature-docs correction`",
        "references/phases/create-plan-phase.md",
        "None of them is restated here",
    ),
    "2a exception": (
        "`### 2a.`",
        "does not run",
        "THREAT-MODEL.md is not written",
    ),
    "reading the targets": (
        "read the target task's plan",
        "what it asked of the document",
    ),
    "kind: in scope": ("in scope", "amended", "two stages"),
    "kind: own documents": (
        "IMPLEMENTATION.md or VERIFICATION.md",
        "edited directly",
        "`replace_own`",
    ),
    "kind: no change asked": ("asked no change", "only removed"),
    "kind: other path": ("Any other path", "`status: blocked`", "naming the path"),
    "editing target plans": (
        "the path leaves the Files sections",
        "reworded as done by the planner",
    ),
    "left unchanged": ("Requirements", "every other criterion", "stay unchanged"),
    "merged plans": ("plan of a merged task", "is not edited"),
    "patch shape": (
        "`replace_planning`",
        "`carried_task_ids`",
        "`tasks_patch.feature_docs_removals`",
        "`task_id`",
        "`path`",
        "`entries` and `step_patches` empty",
        "`requirements_patch` null",
    ),
    "task index and fixes": (
        "`payload.task_index` is empty",
        "`payload.other_feature_doc_fixes`",
    ),
}

FINAL_PATH_2A_PHRASES = (
    "`### 2a.`",
    "two dispatches",
    "does not run",
    "`## Feature-docs correction`",
    "THREAT-MODEL.md is not written",
)

OUTPUT_PHRASE_SETS = {
    "other completed shapes": (
        "`payload.other_feature_doc_requests`",
        "`payload.other_feature_doc_fixes`",
        "`completed`",
    ),
    "output citation": (
        "references/contracts/planner-contract.md",
        "`## Other-feature documents`",
        "not restated",
    ),
}


def _sample_without(needles, index):
    """A text that holds every needle but the one at `index`."""
    return " ".join(n for i, n in enumerate(needles) if i != index)


class PhraseSetNegativeProofs(unittest.TestCase):
    """Negative proofs of the matchers: a sample that lacks one phrase of a
    set must be rejected, and a sample that holds the whole set accepted."""

    def _check(self, sets):
        for name, needles in sets.items():
            with self.subTest(phrase_set=name):
                self.assertTrue(block_states(" ".join(needles), *needles))
                self.assertTrue(states_that(" ".join(needles), *needles))
                for index in range(len(needles)):
                    sample = _sample_without(needles, index)
                    self.assertFalse(
                        block_states(sample, *needles), (name, needles[index])
                    )
                    self.assertFalse(
                        states_that(sample, *needles), (name, needles[index])
                    )

    def test_skill_matchers_reject_a_sample_lacking_a_phrase(self):
        self._check(SKILL_PHRASE_SETS)

    def test_step_4_matchers_reject_a_sample_lacking_a_phrase(self):
        self._check(STEP_4_PHRASE_SETS)

    def test_process_lead_matchers_reject_a_sample_lacking_a_phrase(self):
        self._check(PROCESS_LEAD_PHRASE_SETS)

    def test_correction_matchers_reject_a_sample_lacking_a_phrase(self):
        self._check(CORRECTION_PHRASE_SETS)

    def test_output_matchers_reject_a_sample_lacking_a_phrase(self):
        self._check(OUTPUT_PHRASE_SETS)

    def test_final_path_2a_matcher_rejects_a_sample_lacking_a_phrase(self):
        self._check({"final path 2a": FINAL_PATH_2A_PHRASES})

    def test_block_matcher_needs_the_phrases_in_one_block(self):
        self.assertFalse(block_states("alpha one\n\nbeta two", "alpha", "beta"))
        self.assertFalse(block_states("- alpha one\n- beta two", "alpha", "beta"))
        self.assertTrue(block_states("alpha one\nbeta two", "alpha", "beta"))
        self.assertTrue(block_states("- alpha one\n  beta two", "alpha", "beta"))
        self.assertTrue(states_that("alpha one\n\nbeta two", "alpha", "beta"))


class SectionHelperProofs(unittest.TestCase):
    """The heading scan and the section extractor, in both directions."""

    def test_section_matcher_raises_on_a_missing_or_duplicate_heading(self):
        with self.assertRaises(AssertionError):
            _section("## Other\n\ntext\n", "## Feature-docs Files")
        with self.assertRaises(AssertionError):
            _section(
                "## Feature-docs Files\n\na\n\n## Feature-docs Files\n\nb\n",
                "## Feature-docs Files",
            )

    def test_section_matcher_ignores_a_heading_inside_a_fence(self):
        text = "## Top\n\n```\n## Feature-docs Files\n```\n\n## Next\n\nx\n"
        with self.assertRaises(AssertionError):
            _section(text, "## Feature-docs Files")

    def test_section_ends_at_the_next_heading_of_the_same_level(self):
        text = (
            "## Process\n\nlead text\n\n### 1. Step\n\nstep text\n\n"
            "## Next\n\nnext text\n"
        )
        self.assertEqual(_flat(_section(text, "## Process")), "lead text ### 1. Step step text")
        self.assertEqual(_flat(_section(text, "## Process", lead_only=True)), "lead text")

    def test_heading_scan_sees_a_subheading_and_ignores_a_fenced_one(self):
        body = "text\n\n### Sub\n\nmore\n\n```\n### not a heading\n```\n"
        self.assertEqual([line for _i, _lvl, line in _headings(body)], ["### Sub"])
        self.assertEqual(_headings("plain text only\n"), [])
        self.assertEqual(_headings("a `### inline` mention\n"), [])


# -- AC-1 -----------------------------------------------------------------


class TestAC1PlanWritingFeatureDocsFiles(unittest.TestCase):
    """AC-1 (FR1, NFR4): the rule owner."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, FEATURE_DOCS_FILES_HEADING)
        cls.validator = _load_validator()

    def test_exactly_one_section_before_the_pre_save_checklist(self):
        heads = [line for _i, _lvl, line in _headings(self.text)]
        self.assertEqual(heads.count(FEATURE_DOCS_FILES_HEADING), 1)
        self.assertLess(
            heads.index(FEATURE_DOCS_FILES_HEADING), heads.index(CHECKLIST_HEADING)
        )
        levels = [
            lvl
            for _i, lvl, line in _headings(self.text)
            if line == FEATURE_DOCS_FILES_HEADING
        ]
        self.assertEqual(levels, [2])

    def test_the_section_sits_between_report_names_and_the_checklist(self):
        heads = [line for _i, _lvl, line in _headings(self.text)]
        self.assertEqual(
            heads.index(FEATURE_DOCS_FILES_HEADING),
            heads.index(REPORT_NAMES_HEADING) + 1,
        )
        self.assertEqual(
            heads.index(CHECKLIST_HEADING), heads.index(FEATURE_DOCS_FILES_HEADING) + 1
        )

    def test_predicate_is_stated_with_the_three_covered_forms(self):
        self.assertTrue(
            block_states(self.section, *SKILL_PHRASE_SETS["predicate"]),
            "the predicate bullet lacks a phrase",
        )

    def test_the_stated_examples_follow_the_validator_normalization(self):
        # The examples the section gives are feature-docs paths by the
        # validator's own normalization, and the boundary example is not.
        for example in PREDICATE_EXAMPLES:
            path = example.strip("`")
            with self.subTest(example=example):
                segments = self.validator.path_segments(path)
                self.assertEqual(segments[0], "feature-docs")
        boundary = NON_PREDICATE_EXAMPLE.strip("`")
        self.assertNotEqual(self.validator.path_segments(boundary)[0], "feature-docs")
        self.assertTrue(block_states(self.section, *SKILL_PHRASE_SETS["non-predicate example"]))

    def test_the_validator_normalization_matches_the_stated_wording(self):
        # Negative proof of the example check: a path whose first segment is
        # something else, or whose feature-docs segment is not first, is not
        # a feature-docs path by that normalization.
        for path in ("docs/feature-docs/a.md", "./notes/feature-docs/a.md", "a\\feature-docs\\b"):
            with self.subTest(path=path):
                self.assertNotEqual(self.validator.path_segments(path)[0], "feature-docs")

    def test_the_rework_rule_is_cited_not_restated(self):
        self.assertTrue(
            block_states(self.section, *SKILL_PHRASE_SETS["relation to the rework rule"])
        )
        self.assertNotIn("append_rework", self.section)

    def test_covered_scopes(self):
        self.assertTrue(block_states(self.section, *SKILL_PHRASE_SETS["covered scopes"]))

    def test_plan_value_is_outside_the_rule(self):
        self.assertTrue(
            block_states(self.section, *SKILL_PHRASE_SETS["plan is outside the rule"])
        )

    def test_other_feature_route_is_cited(self):
        self.assertTrue(block_states(self.section, *SKILL_PHRASE_SETS["other-feature route"]))

    def test_validator_code(self):
        self.assertTrue(block_states(self.section, *SKILL_PHRASE_SETS["validator code"]))

    def test_checklist_has_exactly_one_item_citing_the_section(self):
        checklist = _section(self.text, CHECKLIST_HEADING)
        items = [b for b in _blocks(checklist) if b.startswith("- [ ]")]
        citing = [b for b in items if "`%s`" % FEATURE_DOCS_FILES_HEADING in b]
        self.assertEqual(len(citing), 1)
        self.assertIn("`files`", citing[0])
        self.assertIn("feature-docs path", citing[0])

    def test_checklist_counter_proof_rejects_a_checklist_without_the_item(self):
        sample = "- [ ] No language-specific code blocks.\n- [ ] Another item.\n"
        items = [b for b in _blocks(sample) if b.startswith("- [ ]")]
        citing = [b for b in items if "`%s`" % FEATURE_DOCS_FILES_HEADING in b]
        self.assertEqual(citing, [])


# -- AC-2, AC-3, AC-4 -----------------------------------------------------


class TestAC2ToAC4PlannerStep4(unittest.TestCase):
    """AC-2, AC-3 and AC-4 (FR1, FR3, FR4, NFR4, NFR5, TM-3)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)
        cls.skill_text = _read(SKILL_PATH)
        cls.step_4 = _section(cls.text, STEP_4_HEADING)

    # AC-2
    def test_step_4_cites_the_rule_owner_by_path_and_heading(self):
        self.assertTrue(block_states(self.step_4, *STEP_4_PHRASE_SETS["skill citation"]))

    def test_the_agent_does_not_contain_the_predicate_wording(self):
        for phrase in PREDICATE_WORDING:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, _flat(self.text))

    def test_the_predicate_wording_lives_in_plan_writing(self):
        # Keeps the previous test from passing vacuously.
        for phrase in PREDICATE_WORDING:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, _flat(self.skill_text))

    def test_wording_scan_flags_a_restated_predicate(self):
        restated = (
            "A feature-docs path is a path whose first segment is exactly "
            "`feature-docs` after `path_segments`."
        )
        flat = _flat(restated)
        self.assertTrue(any(phrase in flat for phrase in PREDICATE_WORDING))
        clean = "No task's `files` holds a feature-docs path."
        self.assertFalse(any(phrase in _flat(clean) for phrase in PREDICATE_WORDING))

    # AC-3
    def test_contract_is_cited_by_path_and_heading(self):
        self.assertTrue(block_states(self.step_4, *STEP_4_PHRASE_SETS["contract citation"]))

    def test_stage_1_returns_the_request_result_and_writes_nothing(self):
        self.assertTrue(block_states(self.step_4, *STEP_4_PHRASE_SETS["stage 1"]))

    def test_stage_2_amends_only_granted_documents_and_declares_each_fix(self):
        self.assertTrue(block_states(self.step_4, *STEP_4_PHRASE_SETS["stage 2"]))

    def test_a_path_out_of_scope_or_not_granted_is_blocked(self):
        self.assertTrue(block_states(self.step_4, *STEP_4_PHRASE_SETS["blocked"]))

    # AC-4
    def test_other_feature_document_content_is_untrusted(self):
        self.assertTrue(
            block_states(self.step_4, *STEP_4_PHRASE_SETS["untrusted content"])
        )

    def test_no_new_subheading_inside_step_4(self):
        self.assertEqual(_headings(self.step_4), [])


# -- AC-5 -----------------------------------------------------------------


class TestAC5FeatureDocsCorrection(unittest.TestCase):
    """AC-5 (FR8, FR10, NFR4, NFR5)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)
        cls.process_lead = _section(cls.text, PROCESS_HEADING, lead_only=True)
        cls.section = _section(cls.text, FEATURE_DOCS_CORRECTION_HEADING)
        cls.final_path = _section(cls.text, FINAL_PATH_HEADING)
        cls.output = _section(cls.text, OUTPUT_HEADING)

    def test_process_lead_routes_both_corrections(self):
        for name in ("path_correction route", "feature_docs_correction route"):
            with self.subTest(route=name):
                self.assertTrue(
                    block_states(self.process_lead, *PROCESS_LEAD_PHRASE_SETS[name])
                )

    def test_process_lead_keeps_the_every_other_dispatch_sentence(self):
        self.assertTrue(
            block_states(self.process_lead, *PROCESS_LEAD_PHRASE_SETS["every other dispatch"])
        )

    def test_section_is_second_level_after_final_path_and_before_output(self):
        h2 = [line for _i, lvl, line in _headings(self.text) if lvl == 2]
        at = h2.index(FEATURE_DOCS_CORRECTION_HEADING)
        self.assertEqual(h2[at - 1], FINAL_PATH_HEADING)
        self.assertEqual(h2[at + 1], OUTPUT_HEADING)
        self.assertEqual(h2.count(FEATURE_DOCS_CORRECTION_HEADING), 1)

    def test_section_has_no_subheading(self):
        self.assertEqual(_headings(self.section), [])

    def test_trigger(self):
        self.assertTrue(block_states(self.section, *CORRECTION_PHRASE_SETS["trigger"]))

    def test_owning_documents_are_cited_not_restated(self):
        self.assertTrue(block_states(self.section, *CORRECTION_PHRASE_SETS["citations"]))

    def test_exception_to_the_2a_pass(self):
        self.assertTrue(block_states(self.section, *CORRECTION_PHRASE_SETS["2a exception"]))

    def test_target_plans_are_read_for_what_they_asked_of_the_document(self):
        self.assertTrue(
            block_states(self.section, *CORRECTION_PHRASE_SETS["reading the targets"])
        )

    def test_the_four_kinds_of_target_path_are_each_handled(self):
        for name in (
            "kind: in scope",
            "kind: own documents",
            "kind: no change asked",
            "kind: other path",
        ):
            with self.subTest(kind=name):
                self.assertTrue(block_states(self.section, *CORRECTION_PHRASE_SETS[name]))

    def test_editing_target_plans(self):
        self.assertTrue(
            block_states(self.section, *CORRECTION_PHRASE_SETS["editing target plans"])
        )

    def test_requirements_and_other_criteria_stay_unchanged(self):
        self.assertTrue(block_states(self.section, *CORRECTION_PHRASE_SETS["left unchanged"]))

    def test_merged_plans_are_not_edited(self):
        self.assertTrue(block_states(self.section, *CORRECTION_PHRASE_SETS["merged plans"]))

    def test_patch_shape(self):
        self.assertTrue(block_states(self.section, *CORRECTION_PHRASE_SETS["patch shape"]))

    def test_task_index_is_empty_and_fixes_are_named(self):
        self.assertTrue(
            block_states(self.section, *CORRECTION_PHRASE_SETS["task index and fixes"])
        )

    def test_step_headings_equal_the_nine_step_headings(self):
        step_lines = [line for _i, lvl, line in _headings(self.text) if lvl == 3]
        self.assertEqual(step_lines, STEP_HEADINGS)

    def test_gate_option_vocabulary_is_last_and_unchanged(self):
        h2 = [line for _i, lvl, line in _headings(self.text) if lvl == 2]
        self.assertEqual(h2[-1], GATE_VOCABULARY_HEADING)
        self.assertEqual(h2.count(GATE_VOCABULARY_HEADING), 1)
        at = self.text.index("\n" + GATE_VOCABULARY_HEADING + "\n") + 1
        digest = hashlib.sha256(self.text[at:].encode("utf-8")).hexdigest()
        self.assertEqual(digest, GATE_VOCABULARY_SHA256)

    def test_gate_vocabulary_pin_detects_a_changed_section(self):
        at = self.text.index("\n" + GATE_VOCABULARY_HEADING + "\n") + 1
        changed = (self.text[at:] + "\nextra line\n").encode("utf-8")
        self.assertNotEqual(hashlib.sha256(changed).hexdigest(), GATE_VOCABULARY_SHA256)

    def test_final_path_2a_exception_stays_true_for_two_dispatches(self):
        self.assertTrue(block_states(self.final_path, *FINAL_PATH_2A_PHRASES))
        self.assertNotIn("the one dispatch", _flat(self.final_path))

    def test_final_path_section_keeps_having_no_subheading(self):
        self.assertEqual(_headings(self.final_path), [])

    def test_output_names_the_other_completed_shapes(self):
        for name in ("other completed shapes", "output citation"):
            with self.subTest(shape=name):
                self.assertTrue(block_states(self.output, *OUTPUT_PHRASE_SETS[name]))

    def test_old_2a_sentence_is_flagged_by_the_matcher(self):
        old = (
            "- **Exception to the `### 2a.` pass.** This dispatch is the one "
            "dispatch the `### 2a.` pass does not run on: it changes path "
            "strings only, and THREAT-MODEL.md is not written."
        )
        self.assertFalse(block_states(old, *FINAL_PATH_2A_PHRASES))
        self.assertIn("the one dispatch", _flat(old))


# -- AC-6 -----------------------------------------------------------------


class TestAC6ImplementerRuleUnchanged(unittest.TestCase):
    """AC-6 (FR10): the implementer's rule is not changed."""

    def test_implementer_documents_keep_the_never_modify_text(self):
        for path in (IMPLEMENTER_PATH, WORKTREE_SKILL_PATH):
            with self.subTest(document=path.name):
                self.assertIn(NEVER_MODIFY_PHRASE, _read(path))

    def test_the_phrase_check_rejects_a_text_lacking_it(self):
        self.assertNotIn(NEVER_MODIFY_PHRASE, "Never modify `src/**`.")
        self.assertNotIn(NEVER_MODIFY_PHRASE, "Never touch feature-docs.")


if __name__ == "__main__":
    unittest.main()
