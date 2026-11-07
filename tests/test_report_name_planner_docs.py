"""Document contract tests for task0003 (subagent-report-write-block): the
planner documents cite the report-artifact naming rule, and
implementation-planner has a defined final-path correction dispatch (TS-17).

Covers task0003 Acceptance Criteria
(feature-docs/subagent-report-write-block/tasks/task0003.md):

- AC-1: implementation-planner.md and rework-planner.md cite
  `## Report Artifact Names` of plan-writing SKILL.md for tasks' `files`,
  task bodies, Acceptance Criteria and VERIFICATION.md, and neither contains
  the regular expression (NFR3).
- AC-2: rework-planner.md and rework-planner-contract.md state the citation,
  and that rework-planner does not run the final-path correction.
- AC-3: implementation-planner.md routes the dispatch from `## Process`, and
  `## Final-path correction` states the trigger, the exception to the
  `### 2a.` pass, the path choice, the path-strings-only limit and the patch
  shape.
- AC-4: the same section states the handling of unmerged and merged
  references in tests, and the correction on a re-planning pass.
- AC-5: planner-contract.md defines `path_correction`, its `value_inputs`
  membership, the `replace_own` targets and the `task_index` rule. The full
  suite passes, which is verified by running
  `python3 -m unittest discover -s tests`, not re-asserted here.

`## Report Artifact Names` itself lives in plan-writing SKILL.md, which is
outside this task, so only the citation string is tested. Every custom
matcher below is exercised against in-test samples in both directions.

The deliverables are Markdown documents, so verification is textual and
anchored on pinned headings, field names and key literals.

final-path-correction-medium-fixes/task0003 (FR8, AC-3) adds
`TestAC3MediumFixesPlannerRules`: `## Final-path correction` also states the
`new_path` form, that only references may be replaced in an unmerged
non-target plan (and only when `write_policy.targets` lists it) and that a
merged task's plan is not edited, which new name replaces a shared bare
name, what `entries` and `requirements_patch` may hold, the canonical plan of
a new task line by line, and that on a re-planning pass the body may change
and no old path or bare old file name may remain. The section still has no
sub-heading. Each matcher has a negative proof against the section as it
stood before.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

PLANNER_AGENT_PATH = PLUGIN_ROOT / "agents" / "implementation-planner.md"
REWORK_AGENT_PATH = PLUGIN_ROOT / "agents" / "rework-planner.md"
PLANNER_CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "planner-contract.md"
REWORK_CONTRACT_PATH = (
    PLUGIN_ROOT / "references" / "contracts" / "rework-planner-contract.md"
)

CITED_HEADING = "## Report Artifact Names"
CITED_FILE = "skills/plan-writing/SKILL.md"

PROCESS_HEADING = "## Process"
FIRST_STEP_HEADING = "### 1. Analyze SPEC.md"
STEP_2A_HEADING = "### 2a. Threat modeling (MANDATORY)"
CORRECTION_HEADING = "## Final-path correction"
PATH_CORRECTION_HEADING = "### path_correction (dispatch-resolved value)"
DIGEST_INPUTS_HEADING = "## digest_inputs"
COMPLETED_PAYLOAD_HEADING = "## `completed` payload"

# `value_inputs` gains the value as a member, and the sentence names the
# condition "present".
VALUE_INPUTS_MEMBER_RE = re.compile(
    r"`value_inputs`[^.]*`(?:planning_inputs\.)?path_correction`[^.]*\bpresent\b"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _flat(text):
    """Collapse every whitespace run to one space, so an anchor survives the
    documents' hard line wrapping."""
    return re.sub(r"\s+", " ", text).strip()


def _paragraphs(text):
    """Blank-line separated blocks, each flattened to one line."""
    return [_flat(block) for block in re.split(r"\n\s*\n", text) if block.strip()]


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
    heading is absent or appears more than once."""
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


# -- matchers ------------------------------------------------------------

# The name pattern is owned by plan-writing SKILL.md and implemented once in
# validate-worker-output.py (NFR3). It appears in its plain form and in the
# form escaped for a Markdown table cell.
_REGEX_ALTERNATION_RE = re.compile(
    r"REPORT\s*\\?\|\s*SUMMARY\s*\\?\|\s*FINDINGS\s*\\?\|\s*ANALYSIS", re.IGNORECASE
)


def contains_name_regex(text):
    return _REGEX_ALTERNATION_RE.search(text) is not None


def citing_paragraphs(text):
    """Paragraphs that cite plan-writing SKILL.md's `## Report Artifact
    Names` section."""
    return [
        p
        for p in _paragraphs(text)
        if "`%s`" % CITED_HEADING in p and CITED_FILE in p
    ]


def names_four_subjects(paragraph):
    """True when the paragraph names tasks' `files`, task bodies, Acceptance
    Criteria and VERIFICATION.md."""
    low = paragraph.lower()
    return (
        "`files`" in paragraph
        and "task bodies" in low
        and "acceptance criteria" in low
        and "VERIFICATION.md" in paragraph
    )


_NEGATED_RUN_RE = re.compile(r"\bnever\s+runs?\b|\b(?:does|do)\s+not\s+run\b", re.I)


def states_no_correction_run(text):
    """True when one paragraph mentions the final-path correction and says the
    worker never runs it."""
    for p in _paragraphs(text):
        if re.search(r"final-path correction", p, re.I) and _NEGATED_RUN_RE.search(p):
            return True
    return False


def states_that(text, *needles):
    """True when `text` (whitespace flattened) holds every needle."""
    flat = _flat(text)
    return all(n in flat for n in needles)


# -- AC-1 ----------------------------------------------------------------


class TestAC1PlannerAgentsCiteTheNamingRule(unittest.TestCase):
    """AC-1 (TS-17, NFR3)."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {
            "implementation-planner.md": _read(PLANNER_AGENT_PATH),
            "rework-planner.md": _read(REWORK_AGENT_PATH),
        }

    def test_each_agent_cites_report_artifact_names_for_the_four_subjects(self):
        for name, text in self.texts.items():
            with self.subTest(document=name):
                cites = citing_paragraphs(text)
                self.assertTrue(cites, "%s does not cite %s" % (name, CITED_HEADING))
                self.assertTrue(
                    any(names_four_subjects(p) for p in cites),
                    "%s citation lacks one of: `files`, task bodies, "
                    "Acceptance Criteria, VERIFICATION.md" % name,
                )

    def test_neither_agent_contains_the_regular_expression(self):
        for name, text in self.texts.items():
            with self.subTest(document=name):
                self.assertFalse(contains_name_regex(text))

    # negative proofs
    def test_regex_matcher_flags_the_plain_and_the_escaped_form(self):
        plain = r"^(REPORT|SUMMARY|FINDINGS|ANALYSIS).*\.md$"
        escaped = r"^(REPORT\|SUMMARY\|FINDINGS\|ANALYSIS).*\.md$"
        wrapped = "REPORT |\nSUMMARY | FINDINGS | ANALYSIS"
        for sample in (plain, escaped, wrapped):
            self.assertTrue(contains_name_regex(sample), sample)

    def test_regex_matcher_accepts_a_citation_and_a_single_prefix(self):
        for sample in (
            "See `## Report Artifact Names`.",
            "A file named REPORT-x.md is a matching name.",
            "The words summary and findings appear in prose.",
        ):
            self.assertFalse(contains_name_regex(sample), sample)

    def test_citation_matcher_rejects_a_missing_heading_or_file(self):
        self.assertEqual(citing_paragraphs("No citation here."), [])
        self.assertEqual(
            citing_paragraphs("See `## Report Artifact Names` somewhere."), [], "file"
        )
        self.assertEqual(
            citing_paragraphs("See `em-workflow/skills/plan-writing/SKILL.md`."),
            [],
            "heading",
        )

    def test_citation_matcher_accepts_a_wrapped_citation(self):
        sample = (
            "See `em-workflow/skills/plan-writing/SKILL.md`, section\n"
            "`## Report Artifact Names`, for every name.\n"
        )
        self.assertEqual(len(citing_paragraphs(sample)), 1)

    def test_subject_matcher_requires_all_four_subjects(self):
        full = (
            "tasks' `files`, task bodies, Acceptance Criteria and VERIFICATION.md"
        )
        self.assertTrue(names_four_subjects(full))
        for missing in (
            full.replace("`files`", "paths"),
            full.replace("task bodies", "notes"),
            full.replace("Acceptance Criteria", "goals"),
            full.replace("VERIFICATION.md", "the plan"),
        ):
            self.assertFalse(names_four_subjects(missing), missing)


# -- AC-2 ----------------------------------------------------------------


class TestAC2ReworkPlannerDocuments(unittest.TestCase):
    """AC-2 (TS-17)."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {
            "rework-planner.md": _read(REWORK_AGENT_PATH),
            "rework-planner-contract.md": _read(REWORK_CONTRACT_PATH),
        }

    def test_each_document_states_the_citation(self):
        for name, text in self.texts.items():
            with self.subTest(document=name):
                self.assertTrue(citing_paragraphs(text), name)

    def test_each_document_states_rework_planner_does_not_run_the_correction(self):
        for name, text in self.texts.items():
            with self.subTest(document=name):
                self.assertTrue(states_no_correction_run(text), name)

    def test_the_contract_does_not_contain_the_regular_expression(self):
        self.assertFalse(contains_name_regex(self.texts["rework-planner-contract.md"]))

    # negative proofs
    def test_no_run_matcher_accepts_both_phrasings(self):
        for sample in (
            "You never run the final-path correction.",
            "rework-planner does not run the Final-path correction\ndispatch.",
        ):
            self.assertTrue(states_no_correction_run(sample), sample)

    def test_no_run_matcher_rejects_other_text(self):
        for sample in (
            "The final-path correction is run by implementation-planner.",
            "You never run the docs-only route.",
            "",
        ):
            self.assertFalse(states_no_correction_run(sample), sample)

    def test_no_run_matcher_needs_both_statements_in_one_paragraph(self):
        sample = "The final-path correction exists.\n\nYou never run anything."
        self.assertFalse(states_no_correction_run(sample))


# -- AC-3 and AC-4 -------------------------------------------------------


class TestAC3AC4FinalPathCorrectionSection(unittest.TestCase):
    """AC-3 and AC-4 (TS-17)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_AGENT_PATH)
        cls.process_lead = _section(cls.text, PROCESS_HEADING, lead_only=True)
        cls.step_2a = _section(cls.text, STEP_2A_HEADING)
        cls.section = _section(cls.text, CORRECTION_HEADING)

    def test_process_routes_the_dispatch_to_the_section(self):
        self.assertTrue(
            states_that(
                self.process_lead,
                "`planning_inputs.path_correction`",
                "non-null",
                "`%s`" % CORRECTION_HEADING,
            )
        )

    def test_the_section_sits_outside_the_2a_section_and_the_route_line(self):
        heads = [line for _i, _lvl, line in _headings(self.text)]
        self.assertGreater(
            heads.index(CORRECTION_HEADING), heads.index("### 8. Save and report")
        )
        self.assertNotIn("path_correction", self.step_2a)
        self.assertNotIn("Final-path correction", self.step_2a)

    def test_the_section_is_second_level_with_no_subheading(self):
        levels = [lvl for _i, lvl, line in _headings(self.text) if line == CORRECTION_HEADING]
        self.assertEqual(levels, [2])
        self.assertEqual(_headings(self.section), [])

    def test_trigger(self):
        self.assertTrue(
            states_that(self.section, "`planning_inputs.path_correction`", "non-null")
        )

    def test_exception_to_the_2a_pass(self):
        self.assertTrue(
            states_that(
                self.section,
                "`### 2a.`",
                "does not run",
                "THREAT-MODEL.md is not written",
            )
        )

    def test_path_choice(self):
        self.assertTrue(
            states_that(
                self.section,
                "does not match",
                "`%s`" % CITED_HEADING,
                "does not exist in the worktree",
                "already name a non-matching replacement",
            )
        )

    def test_path_strings_only_limit(self):
        self.assertTrue(
            states_that(
                self.section,
                "the old path, and the bare old file name",
                "task plan, IMPLEMENTATION.md and VERIFICATION.md",
                "Change nothing else",
            )
        )

    def test_patch_shape(self):
        self.assertTrue(
            states_that(
                self.section,
                "`replace_planning`",
                "`carried_task_ids`",
                "`path_corrections`",
                "`task_id`",
                "`old_path`",
                "`new_path`",
                "`step_patches` empty",
                "`entries`",
                "merged test files",
            )
        )

    def test_unmerged_and_merged_references_in_tests(self):
        self.assertTrue(
            states_that(
                self.section,
                "unmerged reference in a test",
                "implementer",
                "gets no new task",
                "new tasks that correct references in merged test files",
            )
        )

    def test_re_planning_pass(self):
        self.assertTrue(
            states_that(
                self.section,
                "re-planning pass",
                "non-merged task with a violation",
                "through the same field",
            )
        )

    def test_the_section_cites_the_owning_documents_and_has_no_regex(self):
        self.assertFalse(contains_name_regex(self.section))
        self.assertTrue(
            states_that(
                self.section,
                "references/workflow-patch.md",
                "## Final-path correction",
                "references/phases/create-plan-phase.md",
                "## 13. Final-path correction dispatch",
            )
        )

    # negative proofs
    def test_section_matcher_raises_on_a_missing_or_duplicate_heading(self):
        with self.assertRaises(AssertionError):
            _section("## Process\n\nbody\n", CORRECTION_HEADING)
        with self.assertRaises(AssertionError):
            _section(
                "## Final-path correction\n\na\n\n## Final-path correction\n\nb\n",
                CORRECTION_HEADING,
            )

    def test_section_matcher_scopes_to_the_section_and_to_the_lead(self):
        doc = (
            "## Process\n\nlead text\n\n### 1. Step\n\nstep text\n\n"
            "## Final-path correction\n\ncorrection text\n\n## Next\n\nnext text\n"
        )
        self.assertIn("lead text", _section(doc, "## Process", lead_only=True))
        self.assertNotIn("step text", _section(doc, "## Process", lead_only=True))
        self.assertIn("step text", _section(doc, "## Process"))
        self.assertNotIn("correction text", _section(doc, "## Process"))
        self.assertIn("correction text", _section(doc, CORRECTION_HEADING))
        self.assertNotIn("next text", _section(doc, CORRECTION_HEADING))

    def test_heading_scan_sees_a_subheading_and_ignores_a_fenced_one(self):
        body = "text\n\n### Sub\n\nmore\n\n```\n### not a heading\n```\n"
        self.assertEqual([line for _i, _lvl, line in _headings(body)], ["### Sub"])
        self.assertEqual(_headings("plain text only\n"), [])

    def test_phrase_matcher_rejects_a_missing_phrase_and_survives_wrapping(self):
        self.assertTrue(states_that("a very\nlong phrase", "very long phrase"))
        self.assertFalse(states_that("a very long phrase", "short phrase"))


# -- AC-3 of final-path-correction-medium-fixes/task0003 ---------------------

# The bullets of the section before final-path-correction-medium-fixes, kept
# as the sample for the negative proofs.
OLD_PLANNER_SECTION = """\
- **Exception to the `### 2a.` pass.** This dispatch is the one dispatch the
  `### 2a.` pass does not run on: it changes path strings only, and
  THREAT-MODEL.md is not written.
- **Path choice.** For each target, choose a new path that does not match the
  matching-name rule of `## Report Artifact Names` (cited under Inputs above)
  and does not exist in the worktree. When the plan documents already name a
  non-matching replacement, propose that path.
- **Path strings only.** Replace the old path, and the bare old file name, in
  the target's task plan, IMPLEMENTATION.md and VERIFICATION.md. Change
  nothing else.
- **Patch shape.** Return `replace_planning` with every registered id in
  `carried_task_ids`, the corrections in `path_corrections` (each naming
  `task_id`, `old_path` and `new_path`), and `step_patches` empty. `entries`
  holds only new tasks that correct references in merged test files.
- **References in tests.** An unmerged reference in a test is corrected by
  that task's implementer from the corrected plan, so it gets no new task. A
  reference in a merged test file is corrected by a new task under `entries`.
- **Re-planning pass.** A re-planning pass that carries a non-merged task
  with a violation also corrects it, through the same field.
"""

PATH_FORM_NEEDLES = (
    "fully matches `[\\w./-]+`",
    "equals its normalized form",
    "`.`, `./`, `a//b.md`, `a/./b.md` and a trailing `/`",
    "first segment does not start with `-`",
    "a space, a newline, a backtick or a colon",
)
OTHER_PLANS_NEEDLES = (
    "unmerged task that is not a target",
    "only references to the old path or to the bare old file name may be replaced",
    "only when that plan is listed in `write_policy.targets`",
    "otherwise the planner leaves that plan unedited",
    "the old reference may remain there",
    "The plan of a merged task is not edited",
)
SHARED_NAME_NEEDLES = (
    "Several corrections can share one old file name",
    "In a target task's plan a bare occurrence of it is replaced by the new file "
    "name of the correction of the target task that uses the plan",
    "when a plan is used by several target tasks",
    "the task whose file the sentence is about",
    "When no correction of a task using the plan holds that old file name",
    "in IMPLEMENTATION.md, VERIFICATION.md and every other plan",
)
ENTRIES_REQUIREMENTS_NEEDLES = (
    "non-empty list of regular files at the base commit",
    "whose text holds an old path or a bare old file name of the corrections",
    "a new file, a directory or a file without a reference is never listed",
    "`requirements_patch` is null or has no entries",
    "names a requirement already in `workflow.yaml`",
    "sets only `tasks_append`",
    "all ids under `tasks_patch.entries`",
    "no `status`, no `tests_append` and no `tests_replace`",
)
CANONICAL_INTRO_NEEDLES = (
    "The plan of a new task under `entries` is exactly the text below",
    "UTF-8 with LF line ends and a final LF",
    "a plan named TASK.md included",
    "holds nothing else",
)
# D6 of the feature's IMPLEMENTATION.md, line by line: (line number, text the
# list item holds).
CANONICAL_LINES = (
    (1, "# Task Plan: {task_id} - correct path references"),
    (2, "An empty line."),
    (3, "## Scope"),
    (4, "An empty line."),
    (5, "### Files to Modify"),
    (6, "- `{file}` - correct the old references"),
    (7, "An empty line."),
    (8, "## Acceptance Criteria (MANDATORY)"),
    (9, "An empty line."),
    (
        10,
        "- [ ] AC-{n}: `{old_path}` is replaced by `{new_path}`, and the bare "
        "`{old_name}` by `{new_name}`.",
    ),
)
CANONICAL_CONDITIONS = (
    (6, ("For each file of the entry", "in `files` order")),
    (
        10,
        (
            "For each correction with an occurrence in those files at the base commit",
            "in `path_corrections` order",
            "n counting from 1",
            "last path segments",
        ),
    ),
)
REPLANNING_BODY_NEEDLES = (
    "A re-planning pass that carries a non-merged task with a violation also "
    "corrects it, through the same field",
    "On a re-planning pass the body of the documents may change",
    "no old path and no bare old file name may remain in IMPLEMENTATION.md, "
    "VERIFICATION.md or a target task's plan",
)


def _nested_numbered_items(text):
    """{n: flattened item text} for an indented `1.`-style list, with its
    deeper-indented continuation lines joined."""
    items = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"^\s+(\d+)\.\s+(.*)$", line)
        if match:
            current = int(match.group(1))
            items[current] = match.group(2)
        elif current is not None and line.startswith("     ") and line.strip():
            items[current] += " " + line.strip()
        else:
            current = None
    return {n: _flat(t) for n, t in items.items()}


def _canonical_line_defects(items):
    """What is wrong with the numbered lines of the canonical plan. Empty
    when they are the ten lines of D6."""
    if sorted(items) != list(range(1, 11)):
        return ["the list is not numbered 1 to 10: %r" % sorted(items)]
    return [
        "line %d lacks %r" % (number, text)
        for number, text in CANONICAL_LINES
        if text not in items[number]
    ]


class TestAC3MediumFixesPlannerRules(unittest.TestCase):
    """AC-3 of task0003 (FR8, TS-13): the six items of the design, the D8
    condition and the canonical plan lines."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_AGENT_PATH)
        cls.section = _section(cls.text, CORRECTION_HEADING)
        cls.canonical_items = _nested_numbered_items(cls.section)

    def test_the_new_path_form_is_stated(self):
        self.assertTrue(states_that(self.section, *PATH_FORM_NEEDLES))

    def test_only_references_are_replaced_in_an_unmerged_non_target_plan(self):
        self.assertTrue(states_that(self.section, *OTHER_PLANS_NEEDLES))

    def test_the_d8_condition_ties_the_replacement_to_write_policy_targets(self):
        flat = _flat(self.section)
        sentence = next(
            s for s in re.split(r"(?<=[.;])\s+", flat) if "write_policy.targets" in s
        )
        self.assertIn("unmerged task that is not a target", flat)
        self.assertIn("only when that plan is listed in `write_policy.targets`", sentence)
        # The condition and its "otherwise" stand in the same bullet.
        bullet = next(b for b in re.split(r"\n(?=- )", self.section) if "write_policy.targets" in b)
        self.assertTrue(states_that(bullet, "otherwise the planner leaves that plan unedited"))

    def test_a_shared_bare_name_is_replaced_by_the_right_new_name(self):
        self.assertTrue(states_that(self.section, *SHARED_NAME_NEEDLES))

    def test_entries_and_requirements_patch_are_limited(self):
        self.assertTrue(states_that(self.section, *ENTRIES_REQUIREMENTS_NEEDLES))

    def test_the_canonical_plan_is_exact_text(self):
        self.assertTrue(states_that(self.section, *CANONICAL_INTRO_NEEDLES))

    def test_the_canonical_plan_lines_match_d6(self):
        self.assertEqual(_canonical_line_defects(self.canonical_items), [])

    def test_the_canonical_plan_lines_state_their_repetition(self):
        for number, needles in CANONICAL_CONDITIONS:
            self.assertTrue(states_that(self.canonical_items[number], *needles), number)

    def test_the_canonical_plan_is_not_a_subheading_or_a_fenced_heading(self):
        self.assertEqual(_headings(self.section), [])
        for number in (1, 3, 5, 8):
            self.assertFalse(self.canonical_items[number].startswith("#"), number)

    def test_a_re_planning_pass_may_change_the_body_but_leaves_no_old_name(self):
        self.assertTrue(states_that(self.section, *REPLANNING_BODY_NEEDLES))

    # -- negative proofs ----------------------------------------------------

    def test_negative_the_section_before_the_change_fails_every_new_matcher(self):
        for needles in (
            PATH_FORM_NEEDLES,
            OTHER_PLANS_NEEDLES,
            SHARED_NAME_NEEDLES,
            ENTRIES_REQUIREMENTS_NEEDLES,
            CANONICAL_INTRO_NEEDLES,
            REPLANNING_BODY_NEEDLES,
        ):
            self.assertFalse(states_that(OLD_PLANNER_SECTION, *needles), needles[0])
        self.assertEqual(_nested_numbered_items(OLD_PLANNER_SECTION), {})

    def test_negative_the_old_phrases_still_hold_in_the_old_sample(self):
        # Non-vacuity: the sample is the live text minus the new bullets, so
        # the phrases the old tests pin are in both.
        for phrase in (
            "the old path, and the bare old file name",
            "Change nothing else",
            "gets no new task",
            "through the same field",
        ):
            self.assertTrue(states_that(OLD_PLANNER_SECTION, phrase), phrase)
            self.assertTrue(states_that(self.section, phrase), phrase)

    def test_negative_a_d8_condition_dropped_from_the_bullet_is_detected(self):
        forged = _flat(self.section).replace(
            "only when that plan is listed in `write_policy.targets`; ", ""
        )
        self.assertFalse(states_that(forged, *OTHER_PLANS_NEEDLES))

    def test_negative_a_changed_or_missing_canonical_line_is_detected(self):
        forged = dict(self.canonical_items)
        forged[1] = forged[1].replace("correct path references", "fix paths")
        self.assertNotEqual(_canonical_line_defects(forged), [])
        del forged[10]
        self.assertNotEqual(_canonical_line_defects(forged), [])
        self.assertNotEqual(_canonical_line_defects({}), [])

    def test_negative_the_list_parser_sees_nothing_in_a_bullet_only_text(self):
        self.assertEqual(_nested_numbered_items("- a\n  b\n- c\n"), {})
        self.assertEqual(
            _nested_numbered_items("  1. one\n       more\n  2. two\n"),
            {1: "one more", 2: "two"},
        )


# -- AC-5 ----------------------------------------------------------------


class TestAC5PlannerContract(unittest.TestCase):
    """AC-5 (TS-17)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_CONTRACT_PATH)
        cls.subsection = _section(cls.text, PATH_CORRECTION_HEADING)
        cls.digest_inputs = _section(cls.text, DIGEST_INPUTS_HEADING)
        cls.completed = _section(cls.text, COMPLETED_PAYLOAD_HEADING)

    def test_subsection_defines_the_value_shape(self):
        self.assertTrue(
            states_that(
                self.subsection,
                "`planning_inputs.path_correction`",
                "`targets`",
                "`task_id`",
                "`old_path`",
                "null",
            )
        )

    def test_subsection_is_a_third_level_heading_under_planning_inputs(self):
        heads = _headings(self.text)
        names = [line for _i, _lvl, line in heads]
        level = heads[names.index(PATH_CORRECTION_HEADING)][1]
        self.assertEqual(level, 3)
        self.assertLess(
            names.index("## Additional input: `planning_inputs`"),
            names.index(PATH_CORRECTION_HEADING),
        )
        self.assertLess(
            names.index(PATH_CORRECTION_HEADING),
            names.index("## Question packet bundling rule"),
        )

    def test_value_inputs_gains_the_member_when_present(self):
        self.assertRegex(_flat(self.digest_inputs), VALUE_INPUTS_MEMBER_RE)
        self.assertIn("`value_inputs`", self.subsection)

    def test_write_policy_targets_are_replace_own_on_this_dispatch(self):
        self.assertTrue(
            states_that(
                self.subsection,
                "`write_policy.targets`",
                "`replace_own`",
                "IMPLEMENTATION.md, VERIFICATION.md and each target's task plan",
            )
        )

    def test_task_index_lists_only_entries_and_may_be_empty(self):
        self.assertTrue(
            states_that(
                self.subsection,
                "`payload.task_index`",
                "lists only `entries`",
                "may be empty",
            )
        )

    def test_the_contract_cites_the_patch_owner_and_has_no_regex(self):
        self.assertFalse(contains_name_regex(self.text))
        self.assertTrue(
            states_that(
                self.subsection,
                "references/workflow-patch.md",
                "## Final-path correction",
            )
        )

    # negative proofs
    def test_value_inputs_matcher_accepts_and_rejects_samples(self):
        good = "`value_inputs` gains `planning_inputs.path_correction` as a member when it is present."
        also_good = "`value_inputs` gains `path_correction` as a member when present."
        bad_missing = "`value_inputs` has one member, `plugin_versioning`."
        bad_condition = "`value_inputs` gains `planning_inputs.path_correction` as a member."
        bad_other_value = "`value_inputs` gains `answers` as a member when present."
        self.assertRegex(good, VALUE_INPUTS_MEMBER_RE)
        self.assertRegex(also_good, VALUE_INPUTS_MEMBER_RE)
        self.assertNotRegex(bad_missing, VALUE_INPUTS_MEMBER_RE)
        self.assertNotRegex(bad_condition, VALUE_INPUTS_MEMBER_RE)
        self.assertNotRegex(bad_other_value, VALUE_INPUTS_MEMBER_RE)


if __name__ == "__main__":
    unittest.main()
