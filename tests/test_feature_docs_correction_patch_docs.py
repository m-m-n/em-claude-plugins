"""Document contract tests for task0007 (plan-feature-docs-route): the
workflow-patch contract for the feature-docs correction.

Covers task0007 Acceptance Criteria
(feature-docs/plan-feature-docs-route/tasks/task0007.md):

- AC-1: `TestTasksPatchFieldParagraph` -- the `## tasks_patch` lead defines
  `tasks_patch.feature_docs_removals` (the list of `task_id` and `path`,
  `carried_task_ids` membership, absence from other patches, never together
  with `path_corrections`) and points to `## Feature-docs correction`.
- AC-2: `TestPermissionSentences` -- the permission intro and the
  correction-entry sentence keep their pinned phrases and name
  `## Feature-docs correction` and `tasks_patch.feature_docs_removals`; the
  protocol-error sentence is byte-identical to before.
- AC-3: `TestVerbatimPointer` -- the verbatim-copy pointer names both
  corrections and holds "exception" and "verbatim".
- AC-4 (TM-4): `TestSectionPlacement`, `TestSectionPermissionTable`,
  `TestSectionCodes`, `TestSectionInputsApplicationAndOwnership` -- the new
  H2 sits between the recovery section and `## Final-path correction` and
  states the permission table, every code with its condition, the
  `--dry-run-apply` inputs, the application, the plan agreement, the
  ownership and the two citations.
- AC-5: `TestRulesAndPins` -- the numbered application rules are still 1 to
  18 with "All eighteen rules apply", `## Final-path correction` is still
  directly before `## Ownership boundary`, and `WORKFLOW_PATCH_SHA256`
  carries a refresh comment naming this task.
- AC-6: the full suite passes. That is verified by running
  `python3 -m unittest discover -s tests`, not re-asserted here.

The deliverable is a Markdown document, so verification is textual: the
sections are located by heading outside fenced blocks, and phrases are
matched after collapsing whitespace. Every matcher is a function that returns
the list of defects it finds (empty when the text is right) and has a
negative proof: a synthetic text that lacks one phrase, or a live copy that
is forged by one move, must be reported.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PATCH_DOC = REPO_ROOT / "em-workflow" / "references" / "workflow-patch.md"
GATE_VOCABULARY_TEST = REPO_ROOT / "tests" / "test_gate_option_vocabulary.py"

SECTION_HEADING = "## Feature-docs correction"
FINAL_PATH_HEADING = "## Final-path correction"
RECOVERY_HEADING = "## Interrupted authorization-spend recovery"
OWNERSHIP_HEADING = "## Ownership boundary"
RULES_HEADING = "## Application rules (in order)"
TASKS_PATCH_HEADING = "## `tasks_patch`"
PERMISSION_HEADING = "### `replace_all` permission conditions"
ALLOCATION_HEADING = "### Re-planning task-id allocation"
APPEND_HEADING = "### `append` requirements"
FENCE = "`" * 3

FIELD = "`tasks_patch.feature_docs_removals`"
SECTION_REF = "`## Feature-docs correction`"
FINAL_PATH_REF = "`## Final-path correction`"

# The protocol-error sentence, as it was before this task, with its line
# breaks: it must stay byte-identical.
PROTOCOL_ERROR_RAW = (
    "A `replace_all` received while any task is `in_progress` or `failed` is a\n"
    "protocol error on BOTH paths above. Neither this protocol-error rule nor\n"
    "the Initial-planning path's floor condition above changes as a result of\n"
    "the Re-planning path's widening."
)
OLD_VERBATIM_END = (
    "a `merged` task keeps its `status`, its `branch` and its `files` across "
    "the patch without either field entering the `preserve` vocabulary."
)
ALL_EIGHTEEN = "All eighteen rules apply, in order, to every patch:"

CODE_PREFIX = "feature-docs-removal-"
CODE_SUFFIXES = (
    "not-permitted",
    "in-flight",
    "merged",
    "path",
    "empty-files",
    "incomplete",
    "limits",
)
SHAPE_CODE = "feature-docs-removal-shape"
ALL_CODES = (SHAPE_CODE,) + tuple(CODE_PREFIX + s for s in CODE_SUFFIXES)

# code -> phrases the unit (table row, bullet or paragraph) that states the
# code must hold, so the code is stated together with its condition.
CODE_CONDITIONS = {
    SHAPE_CODE: (
        "malformed",
        "`carried_task_ids`",
        "duplicate",
        "`path_corrections`",
        "`append_rework`",
    ),
    CODE_PREFIX + "in-flight": ("`in_progress`", "`launched`", "journal"),
    CODE_PREFIX + "merged": ("`merged`", "journal event"),
    CODE_PREFIX + "path": ("feature-docs path", "`files`"),
    CODE_PREFIX + "empty-files": ("`files`", "not empty"),
    CODE_PREFIX + "incomplete": ("not `merged`", "feature-docs path"),
    CODE_PREFIX + "limits": (
        "`step_patches`",
        "`tasks_patch.entries`",
        "`requirements_patch`",
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


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


def _paragraphs(text):
    return [_norm(p) for p in re.split(r"\n\s*\n", text) if p.strip()]


def _sentence_with(text, *tokens):
    """The first sentence of the normalized text that holds every token."""
    flat = _norm(text)
    for sent in re.split(r"(?<=[.:;])\s+", flat):
        if all(t in sent for t in tokens):
            return sent
    raise AssertionError("no sentence holds %r" % (tokens,))


def _units(text):
    """The statements of a section: each table row, each top-level bullet
    (continuation lines joined) and each other paragraph, normalized."""
    units = []
    for chunk in re.split(r"\n\s*\n", text):
        lines = [l for l in chunk.split("\n") if l.strip()]
        if lines and all(l.startswith("|") for l in lines):
            units.extend(_norm(l) for l in lines)
        elif any(l.startswith("- ") for l in lines):
            units.extend(
                _norm(piece) for piece in re.split(r"\n(?=- )", chunk) if piece.strip()
            )
        elif lines:
            units.append(_norm(chunk))
    return units


def _units_with(text, token):
    return [u for u in _units(text) if token in u]


def _missing(flat, needles):
    return [n for n in needles if _norm(n) not in flat]


def _patch_text():
    return _read(PATCH_DOC)


def _section():
    return _h2_section(_patch_text(), SECTION_HEADING)


def _tasks_patch_lead(text):
    """The `## tasks_patch` section up to its first `### ` subsection."""
    body = _h2_section(text, TASKS_PATCH_HEADING)
    return body.split("\n### ", 1)[0]


def _permission_text(text):
    return _between(text, PERMISSION_HEADING, ALLOCATION_HEADING)


def _allocation_text(text):
    return _between(text, ALLOCATION_HEADING, APPEND_HEADING)


# ---------------------------------------------------------------------------
# Matchers: each returns the list of defects (empty when the text is right)
# ---------------------------------------------------------------------------

FIELD_PARAGRAPH_NEEDLES = (
    FIELD,
    "`replace_planning`",
    "non-empty list of mappings with exactly `task_id` and `path`",
    "`carried_task_ids`",
    "absent from every other patch",
    "`path_corrections`",
    SECTION_REF,
)


def _field_paragraph_defects(lead):
    """AC-1: the paragraph of the `tasks_patch` lead that defines the field,
    placed after the `path_corrections` paragraph."""
    paragraphs = _paragraphs(lead)
    holders = [i for i, p in enumerate(paragraphs) if FIELD in p]
    if not holders:
        return ["no paragraph of the tasks_patch lead defines %s" % FIELD]
    index = holders[0]
    defects = [
        "field paragraph lacks %r" % n
        for n in _missing(paragraphs[index], FIELD_PARAGRAPH_NEEDLES)
    ]
    # "never together with": the exclusion with path_corrections is stated.
    if "together with `path_corrections`" not in paragraphs[index]:
        defects.append("field paragraph does not say it is never together with path_corrections")
    corrections = [i for i, p in enumerate(paragraphs) if "`tasks_patch.path_corrections`" in p]
    if not corrections or corrections[0] >= index:
        defects.append("the field paragraph is not after the path_corrections paragraph")
    return defects


def _permission_intro_defects(permission_text):
    for para in _paragraphs(permission_text):
        if "exactly two paths" in para:
            intro = para
            break
    else:
        return ["the 'exactly two paths' sentence is missing"]
    return [
        "intro lacks %r" % n
        for n in (
            "exactly two paths",
            FINAL_PATH_REF,
            "`tasks_patch.path_corrections`",
            SECTION_REF,
            FIELD,
            "a patch matching none of these is rejected",
        )
        if n not in intro
    ]


def _protocol_error_defects(permission_text):
    """The protocol-error sentence is byte-identical, and the sentence after
    it that names `## Final-path correction` keeps its pinned phrases and
    also names `## Feature-docs correction`."""
    if PROTOCOL_ERROR_RAW not in permission_text:
        return ["the protocol-error sentence is missing or changed"]
    after = _norm(permission_text.split(PROTOCOL_ERROR_RAW, 1)[1])
    try:
        sentence = _sentence_with(after, FINAL_PATH_REF)
    except AssertionError:
        return ["no sentence after it names the final-path section"]
    return [
        "sentence lacks %r" % n
        for n in (
            "correction entry",
            "`failed` task is not a protocol error",
            "`in_progress`",
            SECTION_REF,
        )
        if n not in sentence
    ]


def _verbatim_pointer_defects(allocation_text):
    flat = _norm(allocation_text)
    if _norm(OLD_VERBATIM_END) not in flat:
        return ["the carried-verbatim text is missing or changed"]
    after = flat.split(_norm(OLD_VERBATIM_END), 1)[1]
    try:
        sentence = _sentence_with(after, FINAL_PATH_REF)
    except AssertionError:
        return ["no sentence after the verbatim text names the final-path section"]
    return [
        "sentence lacks %r" % n
        for n in ("exception", "verbatim", SECTION_REF)
        if n not in sentence
    ]


def _placement_defects(text):
    heads = _h2_headings(text)
    if heads.count(SECTION_HEADING) != 1:
        return ["%r appears %d times" % (SECTION_HEADING, heads.count(SECTION_HEADING))]
    defects = []
    for heading in (RECOVERY_HEADING, FINAL_PATH_HEADING, OWNERSHIP_HEADING):
        if heads.count(heading) != 1:
            return ["%r appears %d times" % (heading, heads.count(heading))]
    here = heads.index(SECTION_HEADING)
    if heads.index(RECOVERY_HEADING) != here - 1:
        defects.append("the section does not directly follow %r" % RECOVERY_HEADING)
    if heads.index(FINAL_PATH_HEADING) != here + 1:
        defects.append("the section is not directly before %r" % FINAL_PATH_HEADING)
    return defects


def _rule_count_defects(text):
    rules = _between(text, RULES_HEADING, RECOVERY_HEADING)
    defects = []
    numbers = [int(n) for n in re.findall(r"^(\d+)\. ", rules, re.MULTILINE)]
    if numbers != list(range(1, 19)):
        defects.append("the numbered rules are %r, not 1 to 18" % (numbers,))
    if rules.count(ALL_EIGHTEEN) != 1:
        defects.append("'All eighteen rules apply' is not stated exactly once")
    return defects


def _final_path_adjacency_defects(text):
    heads = _h2_headings(text)
    if heads.count(FINAL_PATH_HEADING) != 1 or heads.count(OWNERSHIP_HEADING) != 1:
        return ["a heading is missing or repeated"]
    if heads.index(OWNERSHIP_HEADING) - heads.index(FINAL_PATH_HEADING) != 1:
        return ["%r is not directly before %r" % (FINAL_PATH_HEADING, OWNERSHIP_HEADING)]
    return []


def _code_defects(section):
    """AC-4: every code is stated, each with its condition."""
    defects = []
    for code in ALL_CODES:
        token = "`%s`" % code
        units = _units_with(section, token)
        if not units:
            defects.append("code %s is not stated" % token)
            continue
        if code == CODE_PREFIX + "not-permitted":
            continue  # the permission table checks its rows
        needles = CODE_CONDITIONS[code]
        if not any(not _missing(u, needles) for u in units):
            defects.append("no statement of %s holds %r" % (token, needles))
    return defects


def _permission_table_defects(section):
    rows = [l for l in section.splitlines() if l.startswith("|")]
    defects = []
    entry = [r for r in rows if "(the correction entry)" in r]
    if len(entry) != 1:
        defects.append("the correction-entry row is missing or repeated")
    else:
        row = _norm(entry[0])
        for needle in (
            "`create-plan` is `completed`",
            "`implement` is `failed`",
            "Admitted",
            "carry-over and `preserve` obligations of the Re-planning path apply",
            "A `failed` task is permitted",
            "an `in_progress` task stays rejected as `replace-all-not-permitted`",
        ):
            if needle not in row:
                defects.append("correction-entry row lacks %r" % needle)
    not_permitted = "`%snot-permitted`" % CODE_PREFIX
    for label in ("| The Re-planning path", "| The Initial-planning path", "| Any other state"):
        found = [r for r in rows if r.startswith(label)]
        if len(found) != 1:
            defects.append("the %r row is missing or repeated" % label)
        elif "Rejected" not in found[0] or not_permitted not in found[0]:
            defects.append("the %r row is not rejected as %s" % (label, not_permitted))
    return defects


def _inputs_defects(section):
    units = _units_with(section, "**Inputs.**")
    if len(units) != 1:
        return ["the Inputs paragraph is missing or repeated"]
    return [
        "Inputs lacks %r" % n
        for n in (
            "`--dry-run-apply`",
            "`--workflow`",
            "`--journal`",
            "`--feature-dir`",
            "A missing input is an execution error (exit 2)",
        )
        if n not in units[0]
    ]


def _application_defects(section):
    units = _units_with(section, "**Application.**")
    if len(units) != 1:
        return ["the Application paragraph is missing or repeated"]
    return [
        "Application lacks %r" % n
        for n in (
            "every occurrence of `path` is removed from the target task's `files`",
            "`notes` is set to null",
            "Every other field",
            "every other record is copied verbatim",
        )
        if n not in units[0]
    ]


def _plan_agreement_and_ownership_defects(section):
    defects = []
    agreement = _units_with(section, "**Plan agreement.**")
    if len(agreement) != 1:
        defects.append("the Plan agreement paragraph is missing or repeated")
    elif "`task-plan-files-mismatch`" not in agreement[0]:
        defects.append("Plan agreement does not name `task-plan-files-mismatch`")
    ownership = _units_with(section, "**Ownership.**")
    if len(ownership) != 1:
        defects.append("the Ownership paragraph is missing or repeated")
    else:
        for needle in (
            "`implementation-planner` corrects the plan documents and proposes the removals",
            "the orchestrator applies the patch",
            "The implementer and `rework-planner` do not",
        ):
            if needle not in ownership[0]:
                defects.append("Ownership lacks %r" % needle)
    return defects


def _citation_defects(section):
    flat = _norm(section)
    return [
        "section lacks the citation %r" % n
        for n in (
            "`skills/plan-writing/SKILL.md`, section `## Feature-docs Files`",
            "`skills/develop/SKILL.md`'s `## Step A.6: failed からの入口`",
        )
        if n not in flat
    ]


def _predicate_restated(section):
    """True when the section restates the feature-docs path predicate that
    plan-writing owns."""
    flat = _norm(section)
    return any(w in flat for w in ("first segment", "path_segments", "normalization"))


def _without_behaviour_defects(section):
    sentence = "A `replace_all` without `feature_docs_removals` behaves as before in every state."
    return [] if sentence in _norm(section) else ["the 'behaves as before' sentence is missing"]


def _move_section_after(text, heading, anchor):
    """A copy of `text` with the H2 section `heading` moved to just after the
    H2 section `anchor`."""
    body = _h2_section(text, heading)
    without = text.replace(body, "", 1)
    heads = [
        (offset, line.rstrip("\n"))
        for offset, line in _lines_outside_fences(without)
        if line.startswith("## ")
    ]
    for i, (offset, line) in enumerate(heads):
        if line == anchor:
            return without[: heads[i + 1][0]] + body + without[heads[i + 1][0] :]
    raise AssertionError("anchor not found: %r" % anchor)


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------


class TestTasksPatchFieldParagraph(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        cls.text = _patch_text()
        cls.lead = _tasks_patch_lead(cls.text)

    def test_the_lead_defines_the_field(self):
        self.assertEqual(_field_paragraph_defects(self.lead), [])

    def test_negative_pre_change_lead_is_rejected(self):
        pre_change = "\n\n".join(
            p
            for p in re.split(r"\n\s*\n", self.lead)
            if FIELD not in p
        )
        self.assertNotEqual(_field_paragraph_defects(pre_change), [])

    def test_negative_each_dropped_phrase_is_rejected(self):
        paragraph = next(
            p for p in re.split(r"\n\s*\n", self.lead) if FIELD in p
        )
        for needle in FIELD_PARAGRAPH_NEEDLES[1:] + ("together with `path_corrections`",):
            with self.subTest(dropped=needle):
                forged = self.lead.replace(paragraph, _norm(paragraph).replace(needle, "x"), 1)
                self.assertNotEqual(forged, self.lead)
                self.assertNotEqual(_field_paragraph_defects(forged), [])

    def test_negative_a_paragraph_before_path_corrections_is_rejected(self):
        paragraphs = re.split(r"\n\s*\n", self.lead)
        field = next(p for p in paragraphs if FIELD in p)
        rest = [p for p in paragraphs if p is not field]
        first = next(i for i, p in enumerate(rest) if "`tasks_patch.path_corrections`" in p)
        forged = "\n\n".join(rest[:first] + [field] + rest[first:])
        self.assertNotEqual(_field_paragraph_defects(forged), [])


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------


class TestPermissionSentences(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.text = _patch_text()
        cls.permission = _permission_text(cls.text)

    def test_the_intro_keeps_its_phrases_and_names_the_new_section(self):
        self.assertEqual(_permission_intro_defects(self.permission), [])

    def test_both_existing_path_bullets_are_still_present(self):
        self.assertIn("- **Initial-planning path**", self.permission)
        self.assertIn("- **Re-planning path**", self.permission)

    def test_the_protocol_error_sentence_is_byte_identical(self):
        self.assertEqual(self.permission.count(PROTOCOL_ERROR_RAW), 1)

    def test_the_correction_entry_sentence_names_both_sections(self):
        self.assertEqual(_protocol_error_defects(self.permission), [])

    def test_negative_pre_change_intro_is_rejected(self):
        pre_change = (
            "`replace_all` is permitted through exactly two paths, and through "
            "the one further state that `## Final-path correction` (below) "
            "admits for a patch carrying `tasks_patch.path_corrections`; a "
            "patch matching none of these is rejected:"
        )
        self.assertNotEqual(_permission_intro_defects(pre_change), [])

    def test_negative_each_dropped_intro_phrase_is_rejected(self):
        intro = next(
            p for p in re.split(r"\n\s*\n", self.permission) if "exactly two paths" in p
        )
        for needle in (SECTION_REF, FIELD, "a patch matching none of these is rejected"):
            with self.subTest(dropped=needle):
                forged = self.permission.replace(intro, _norm(intro).replace(needle, "x"), 1)
                self.assertNotEqual(forged, self.permission)
                self.assertNotEqual(_permission_intro_defects(forged), [])

    def test_negative_pre_change_correction_entry_sentence_is_rejected(self):
        pre_change = (
            PROTOCOL_ERROR_RAW
            + " The correction entry of `## Final-path correction` (below) is "
            "the one state in which a `failed` task is not a protocol error, "
            "and an `in_progress` task stays one there."
        )
        self.assertNotEqual(_protocol_error_defects(pre_change), [])

    def test_negative_a_changed_protocol_error_sentence_is_rejected(self):
        forged = self.permission.replace("BOTH paths", "either path", 1)
        self.assertNotEqual(forged, self.permission)
        self.assertNotEqual(_protocol_error_defects(forged), [])
        self.assertEqual(forged.count(PROTOCOL_ERROR_RAW), 0)


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------


class TestVerbatimPointer(unittest.TestCase):
    """AC-3."""

    @classmethod
    def setUpClass(cls):
        cls.allocation = _allocation_text(_patch_text())

    def test_the_pointer_names_both_corrections(self):
        self.assertEqual(_verbatim_pointer_defects(self.allocation), [])

    def test_negative_pre_change_pointer_is_rejected(self):
        pre_change = (
            OLD_VERBATIM_END
            + "\n\nThe one exception to this verbatim copy is the final-path "
            "correction (`## Final-path correction`, below)."
        )
        self.assertNotEqual(_verbatim_pointer_defects(pre_change), [])

    def test_negative_a_pointer_without_the_word_exception_is_rejected(self):
        forged = _norm(self.allocation).replace("exception", "case")
        self.assertNotEqual(_verbatim_pointer_defects(forged), [])


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------


class TestSectionPlacement(unittest.TestCase):
    """AC-4: one H2, directly between the recovery section and the
    final-path section."""

    @classmethod
    def setUpClass(cls):
        cls.text = _patch_text()

    def test_one_h2_between_recovery_and_final_path_correction(self):
        self.assertEqual(_placement_defects(self.text), [])

    def test_negative_the_section_moved_after_final_path_correction_is_rejected(self):
        forged = _move_section_after(self.text, SECTION_HEADING, FINAL_PATH_HEADING)
        self.assertNotEqual(forged, self.text)
        self.assertNotEqual(_placement_defects(forged), [])

    def test_negative_a_second_copy_of_the_heading_is_rejected(self):
        forged = self.text + "\n" + SECTION_HEADING + "\n\nA second copy.\n"
        self.assertNotEqual(_placement_defects(forged), [])

    def test_the_section_has_no_subheading_and_no_numbered_rule(self):
        section = _section()
        self.assertNotRegex(section, r"(?m)^### ")
        self.assertNotRegex(section, r"(?m)^\d+\. ")


class TestSectionPermissionTable(unittest.TestCase):
    """AC-4: the permission-states table."""

    @classmethod
    def setUpClass(cls):
        cls.section = _section()

    def test_the_table_states_the_entry_and_the_rejected_states(self):
        self.assertEqual(_permission_table_defects(self.section), [])

    def test_negative_a_table_without_the_not_permitted_code_is_rejected(self):
        forged = self.section.replace("`%snot-permitted`" % CODE_PREFIX, "x")
        self.assertNotEqual(_permission_table_defects(forged), [])

    def test_negative_a_table_without_the_admitted_entry_row_is_rejected(self):
        forged = self.section.replace("(the correction entry)", "(some state)")
        self.assertNotEqual(_permission_table_defects(forged), [])

    def test_negative_an_entry_row_that_admits_in_progress_is_rejected(self):
        forged = self.section.replace(
            "an `in_progress` task stays rejected as `replace-all-not-permitted`",
            "an `in_progress` task is permitted",
        )
        self.assertNotEqual(_permission_table_defects(forged), [])


class TestSectionCodes(unittest.TestCase):
    """AC-4: every code with its condition."""

    @classmethod
    def setUpClass(cls):
        cls.section = _section()

    def test_the_eight_codes_are_each_stated_with_their_condition(self):
        self.assertEqual(len(ALL_CODES), 8)
        self.assertEqual(_code_defects(self.section), [])

    def test_only_the_eight_codes_of_the_prefix_appear(self):
        found = set(re.findall(r"`(feature-docs-removal-[a-z-]+)`", self.section))
        self.assertEqual(found, set(ALL_CODES))

    def test_negative_a_section_missing_one_code_is_rejected(self):
        for code in ALL_CODES:
            with self.subTest(code=code):
                forged = self.section.replace("`%s`" % code, "`x`")
                self.assertNotEqual(forged, self.section)
                self.assertNotEqual(_code_defects(forged), [])

    def test_negative_a_code_stated_without_its_condition_is_rejected(self):
        for code, needles in CODE_CONDITIONS.items():
            for needle in needles:
                with self.subTest(code=code, dropped=needle):
                    forged_units = [
                        u.replace(needle, "x") if "`%s`" % code in u else u
                        for u in _units(self.section)
                    ]
                    forged = "\n\n".join(forged_units)
                    self.assertNotEqual(_code_defects(forged), [])


class TestSectionInputsApplicationAndOwnership(unittest.TestCase):
    """AC-4: the inputs, the application, the plan agreement, the ownership
    and the two citations."""

    @classmethod
    def setUpClass(cls):
        cls.section = _section()

    def test_the_inputs_name_the_three_flags_and_the_execution_error(self):
        self.assertEqual(_inputs_defects(self.section), [])

    def test_the_application_removes_only_the_path_and_clears_notes(self):
        self.assertEqual(_application_defects(self.section), [])

    def test_the_plan_agreement_and_the_ownership_are_stated(self):
        self.assertEqual(_plan_agreement_and_ownership_defects(self.section), [])

    def test_the_two_citations_are_present(self):
        self.assertEqual(_citation_defects(self.section), [])

    def test_the_predicate_is_cited_not_restated(self):
        self.assertFalse(_predicate_restated(self.section))

    def test_a_replace_all_without_the_field_behaves_as_before(self):
        self.assertEqual(_without_behaviour_defects(self.section), [])

    def test_negative_each_dropped_input_is_rejected(self):
        for flag in ("`--dry-run-apply`", "`--workflow`", "`--journal`", "`--feature-dir`"):
            with self.subTest(flag=flag):
                forged = self.section.replace(flag, "x")
                self.assertNotEqual(_inputs_defects(forged), [])

    def test_negative_an_application_that_keeps_notes_is_rejected(self):
        forged = self.section.replace("`notes` is set to null", "`notes` is kept")
        self.assertNotEqual(_application_defects(forged), [])

    def test_negative_a_missing_plan_agreement_code_is_rejected(self):
        forged = self.section.replace("`task-plan-files-mismatch`", "x")
        self.assertNotEqual(_plan_agreement_and_ownership_defects(forged), [])

    def test_negative_an_ownership_that_names_the_implementer_is_rejected(self):
        forged = self.section.replace("The implementer and `rework-planner` do not", "x")
        self.assertNotEqual(_plan_agreement_and_ownership_defects(forged), [])

    def test_negative_a_missing_citation_is_rejected(self):
        for citation in (
            "`skills/plan-writing/SKILL.md`, section `## Feature-docs Files`",
            "`skills/develop/SKILL.md`'s `## Step A.6: failed からの入口`",
        ):
            with self.subTest(citation=citation):
                forged = _norm(self.section).replace(citation, "x")
                self.assertNotEqual(_citation_defects(forged), [])

    def test_negative_a_restated_predicate_is_rejected(self):
        forged = self.section + "\nA path whose first segment is exactly `feature-docs`.\n"
        self.assertTrue(_predicate_restated(forged))

    def test_negative_a_missing_behaves_as_before_sentence_is_rejected(self):
        forged = self.section.replace("behaves as before", "x")
        self.assertNotEqual(_without_behaviour_defects(forged), [])


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------


def _pin_comment_defects(test_text):
    """The comment paragraph directly above `WORKFLOW_PATCH_SHA256 = (` (the
    comment lines after the last bare `#` separator) names this task."""
    marker = "    WORKFLOW_PATCH_SHA256 = ("
    if test_text.count(marker) != 1:
        return ["WORKFLOW_PATCH_SHA256 is not assigned exactly once"]
    block = []
    for line in reversed(test_text.split(marker, 1)[0].splitlines()):
        stripped = line.strip()
        if not stripped.startswith("#") or stripped == "#":
            break
        block.append(stripped)
    comment = _norm(" ".join(reversed(block)))
    if not comment.startswith("# Refreshed again by plan-feature-docs-route/task0007"):
        return [
            "the comment above the pin does not start with "
            "'Refreshed again by plan-feature-docs-route/task0007'"
        ]
    return []


class TestRulesAndPins(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        cls.text = _patch_text()
        cls.pin_test = _read(GATE_VOCABULARY_TEST)

    def test_the_numbered_rules_are_one_to_eighteen_with_the_statement(self):
        self.assertEqual(_rule_count_defects(self.text), [])

    def test_final_path_correction_is_directly_before_ownership_boundary(self):
        self.assertEqual(_final_path_adjacency_defects(self.text), [])

    def test_the_recovery_section_is_before_the_final_path_section(self):
        heads = _h2_headings(self.text)
        self.assertLess(heads.index(RECOVERY_HEADING), heads.index(FINAL_PATH_HEADING))

    def test_the_pin_comment_names_this_task(self):
        self.assertEqual(_pin_comment_defects(self.pin_test), [])

    def test_negative_a_nineteenth_rule_is_rejected(self):
        forged = self.text.replace(
            "\n\n" + RECOVERY_HEADING,
            "\n19. A nineteenth rule.\n\n" + RECOVERY_HEADING,
            1,
        )
        self.assertNotEqual(forged, self.text)
        self.assertNotEqual(_rule_count_defects(forged), [])

    def test_negative_a_missing_statement_is_rejected(self):
        forged = self.text.replace("All eighteen rules apply", "Some rules apply", 1)
        self.assertNotEqual(_rule_count_defects(forged), [])

    def test_negative_the_section_between_final_path_and_ownership_is_rejected(self):
        forged = _move_section_after(self.text, SECTION_HEADING, FINAL_PATH_HEADING)
        self.assertNotEqual(_final_path_adjacency_defects(forged), [])

    def test_negative_a_pin_without_the_task_comment_is_rejected(self):
        forged = self.pin_test.replace("plan-feature-docs-route/task0007", "x")
        self.assertNotEqual(forged, self.pin_test)
        self.assertNotEqual(_pin_comment_defects(forged), [])


if __name__ == "__main__":
    unittest.main()
