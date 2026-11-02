"""Tests for task0003 (scenario-id-ts-hyphen): the plan-writing skill's
scenario ID rule requires the TS-n form in every new VERIFICATION.md and task
plan, and accepts the hyphen-less (TSn) form only when an existing document is
read.

Covers task0003 Acceptance Criteria
(feature-docs/scenario-id-ts-hyphen/tasks/task0003.md):

- AC-1: the scenario ID rule block states that new VERIFICATION.md files and
  new task plans use only the TS-n form.
- AC-2: the block states that the TSn form is a valid scenario ID only when an
  existing document is read; no sentence in SKILL.md says the TSn form may be
  written into a new VERIFICATION.md or task plan.
- AC-3: the block keeps both existing statements (only two scenario ID forms;
  IDs compared as literal strings, `TS13` and `TS-13` distinct).
- AC-4: when SPEC.md uses the hyphen-less form, the new VERIFICATION.md uses
  the same numbers in the TS-n form and SPEC.md is not rewritten.
- AC-5: a hyphen-less ID anywhere in a new VERIFICATION.md or task plan,
  outside fenced code blocks and HTML comments, makes the validator reject the
  implementation-planner result.
- AC-6: the Pre-Save Self-Verification Checklist gains an item requiring
  TS-n-only scenario IDs; every checklist item of the base revision is still
  present unchanged.
- AC-7: this module asserts AC-1 to AC-6 with a negative proof per matcher
  against the pre-change rule block embedded below. The block is located
  between the end of the VERIFICATION.md template block and the
  `## Pre-Save Self-Verification Checklist (MANDATORY)` heading. The whole
  suite passing is verified by running `python3 -m unittest discover -s tests`,
  not re-asserted here.

Per IMPLEMENTATION.md Conventions ("Document-content tests"): standard
library only, files located relative to this module's path, anchors on literal
headings, whitespace-normalized comparison so a line wrap does not break an
assertion, and at least one negative proof per matcher. Per test/README.md no
test module imports another, so every helper is local to this module.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "plan-writing" / "SKILL.md"

TEMPLATE_HEADING = "## VERIFICATION.md Template (feature-wide)"
CHECKLIST_HEADING = "## Pre-Save Self-Verification Checklist (MANDATORY)"

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
LIST_START_RE = re.compile(r"^\s*[-*+]\s+(?:\[[ xX]\]\s+)?")


# ---------------------------------------------------------------------------
# Pre-change excerpts (the base revision of SKILL.md), embedded so that every
# matcher can be shown failing on the text it is meant to reject.
# ---------------------------------------------------------------------------

TEMPLATE_STUB = (
    "# Plan Writing\n"
    "\n"
    "## VERIFICATION.md Template (feature-wide)\n"
    "\n"
    "```markdown\n"
    "# Verification Document: {Feature Name}\n"
    "\n"
    "## Overview\n"
    "\n"
    "### Test Scenarios from SPEC.md\n"
    "| ID | Scenario | Expected Result | Test Type |\n"
    "|----|----------|-----------------|-----------|\n"
    "| TS-N | {scenario} | {outcome} | Unit/Integration |\n"
    "```\n"
)

PRE_CHANGE_RULE_BLOCK = """\

Scenario IDs in the template's scenario table follow one rule, which stays
outside the template block:

- New VERIFICATION.md files use the TS-n form: `TS`, a hyphen, one or more
  digits.
- The TSn form — `TS` immediately followed by one or more digits, no hyphen —
  is also a valid scenario ID, and `em-workflow/scripts/validate-worker-output.py`
  recognizes it.
- These two are the only scenario ID forms.
- Scenario IDs are compared as literal strings, so `TS13` and `TS-13` are
  distinct IDs.

"""

PRE_CHANGE_CHECKLIST = """\
## Pre-Save Self-Verification Checklist (MANDATORY)

- [ ] No language-specific code blocks, library API calls, or snippets
      anywhere (IMPLEMENTATION.md AND every task plan).
- [ ] IMPLEMENTATION.md contains only cross-task content.
- [ ] Every task: files / skills / domains / complexity /
      requirements all present in workflow.yaml.
- [ ] Every cross-task component use has its contract pinned in
      IMPLEMENTATION.md Shared Components.
- [ ] Every task plan has non-empty, verifiable Acceptance Criteria.
- [ ] Every FR/NFR maps to ≥ 1 task and ≥ 1 test (or is flagged as a gap).
- [ ] skills values exist in impl-skills.yaml; domains values in the 8-value
      vocabulary; complexity in {low, medium, high}.
- [ ] THREAT-MODEL.md is written with exactly one verdict.
- [ ] Every `TM-n` appears in at least one task AC and in VERIFICATION.md
      (full / reduced) or in TASK.md's Expected Result (minimal).
- [ ] No mitigation exists without a recorded threat.
- [ ] Non-exempt repository: every task whose files fall under a plugin lists
      that plugin's `plugin.json` (and `.claude-plugin/marketplace.json` when
      `marketplace_versioned` is true) among its files and carries the
      per-commit version instruction itself (Plugin Version Handling).
- [ ] No plan text contains an instruction that keeps the version unchanged on
      a plugin-changing commit, rework task plans included.
- [ ] Exempt repository: no plan text instructs a version change and none
      contains a concrete version value; a minor or major bump names only
      where to bump.
"""

PRE_CHANGE_DOC = TEMPLATE_STUB + PRE_CHANGE_RULE_BLOCK + PRE_CHANGE_CHECKLIST


# ---------------------------------------------------------------------------
# Extraction helpers (fence-aware)
# ---------------------------------------------------------------------------


def flat(text):
    """Collapse whitespace and casefold, so wrapped lines do not hide terms."""
    return re.sub(r"\s+", " ", text).casefold()


def _fence_flags(lines):
    flags = []
    inside = False
    for line in lines:
        if FENCE_RE.match(line):
            flags.append(True)
            inside = not inside
        else:
            flags.append(inside)
    return flags


def _heading_level(line):
    match = HEADING_RE.match(line)
    return len(match.group(1)) if match else 0


def _single_heading_index(lines, fenced, heading):
    starts = [
        i for i, line in enumerate(lines)
        if not fenced[i] and line.rstrip() == heading
    ]
    if len(starts) != 1:
        raise AssertionError(
            f"expected exactly one heading line {heading!r}, found {len(starts)}"
        )
    return starts[0]


def extract_rule_block(text):
    """The text between the end of the VERIFICATION.md template's fenced block
    and the Pre-Save Self-Verification Checklist heading. Raises
    AssertionError when an anchor is absent, duplicated or out of order."""
    lines = text.splitlines()
    fenced = _fence_flags(lines)
    template_at = _single_heading_index(lines, fenced, TEMPLATE_HEADING)
    checklist_at = _single_heading_index(lines, fenced, CHECKLIST_HEADING)
    fences = [
        i for i in range(template_at + 1, len(lines)) if FENCE_RE.match(lines[i])
    ]
    if len(fences) < 2:
        raise AssertionError("the template's fenced block was not found")
    template_end = fences[1]
    if not template_end < checklist_at:
        raise AssertionError("the checklist heading does not follow the template block")
    return "\n".join(lines[template_end + 1:checklist_at]) + "\n"


def rule_items(block):
    """Whitespace-normalized text of each top-level list item in a block."""
    items = []
    current = None
    for line in block.splitlines():
        if LIST_START_RE.match(line):
            if current is not None:
                items.append(current)
            current = [LIST_START_RE.sub("", line, count=1).strip()]
        elif line.strip() and current is not None and line.startswith((" ", "\t")):
            current.append(line.strip())
        else:
            if current is not None:
                items.append(current)
                current = None
    if current is not None:
        items.append(current)
    return [flat(" ".join(item)) for item in items]


def checklist_bullets(text):
    """Whitespace-normalized checklist bullets of the Pre-Save Self-Verification
    Checklist section (up to the next heading of the same or a shallower
    level, or the end of the file)."""
    lines = text.splitlines()
    fenced = _fence_flags(lines)
    start = _single_heading_index(lines, fenced, CHECKLIST_HEADING)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if not fenced[j] and 0 < _heading_level(lines[j]) <= 2:
            end = j
            break
    return rule_items("\n".join(lines[start + 1:end]))


def paragraphs(text):
    """One entry per paragraph or list item (blank lines and list starts split
    entries); headings are dropped."""
    out = []
    current = []

    def flush():
        if current:
            out.append(" ".join(current))
            current.clear()

    for line in text.splitlines():
        if _heading_level(line) or not line.strip():
            flush()
        elif LIST_START_RE.match(line):
            flush()
            current.append(LIST_START_RE.sub("", line, count=1).strip())
        else:
            current.append(line.strip())
    flush()
    return out


def sentences(paragraph):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()]


# ---------------------------------------------------------------------------
# AC-1 .. AC-5 matchers over the rule block's list items (normalized)
# ---------------------------------------------------------------------------


def states_ts_n_only(items):
    """AC-1: new VERIFICATION.md files and new task plans use only TS-n."""
    return any(
        re.search(
            r"\bnew verification\.md files and new task plans\b.*"
            r"\buse the ts-n form only\b",
            item,
        )
        for item in items
    )


TSN_QUALIFIER = "only when an existing document is read"


def states_tsn_only_when_reading(items):
    """AC-2 (positive half): the TSn form is a valid scenario ID only when an
    existing document is read."""
    return any(
        re.search(
            r"\btsn form\b.*\bis a valid scenario id only when an existing "
            r"document is read\b",
            item,
        )
        for item in items
    )


TSN_MENTION_RE = re.compile(
    r"\btsn\b|hyphen-less|immediately followed by (?:one or more )?digits"
    r"|(?<![A-Za-z0-9-])TS\d+\b",
    re.I,
)
TSN_PERMISSION_RE = re.compile(
    r"\b(?:is|are)\s+(?:also\s+)?(?:a\s+)?valid\b"
    r"|\b(?:may|can)\s+(?:also\s+)?be\s+(?:written|used)\b"
    r"|\b(?:allowed|permitted|accepted|acceptable)\b",
    re.I,
)


def unqualified_tsn_permissions(text):
    """AC-2 (negative half): sentences that grant the TSn form without the
    'only when an existing document is read' qualifier."""
    found = []
    for paragraph in paragraphs(text):
        for sentence in sentences(paragraph):
            if (
                TSN_MENTION_RE.search(sentence)
                and TSN_PERMISSION_RE.search(sentence)
                and TSN_QUALIFIER not in flat(sentence)
            ):
                found.append(sentence)
    return found


def keeps_only_two_forms(items):
    """AC-3: there are only two scenario ID forms."""
    return any(
        re.search(r"\bthese two are the only scenario id forms\b", item)
        for item in items
    )


def keeps_literal_comparison(items):
    """AC-3: literal-string comparison with TS13 / TS-13 named as distinct."""
    return any(
        "compared as literal strings" in item
        and "`ts13`" in item
        and "`ts-13`" in item
        and "distinct" in item
        for item in items
    )


def states_legacy_spec_mapping(items):
    """AC-4: hyphen-less SPEC.md -> same numbers in TS-n form, SPEC.md not
    rewritten."""
    return any(
        re.search(r"\bwhen spec\.md uses the hyphen-less form\b", item)
        and "the same numbers in the ts-n form" in item
        and re.search(r"\bspec\.md is not rewritten\b", item)
        for item in items
    )


def states_validator_rejects_hyphen_less(items):
    """AC-5: a hyphen-less ID anywhere in a new VERIFICATION.md or task plan,
    outside fenced code blocks and HTML comments, gets the planner result
    rejected by the scenario-ID form check."""
    needed = (
        "contains no hyphen-less id anywhere",
        "outside fenced code blocks and html comments",
        "not only in the scenario table",
        "implementation-planner result",
        "rejected",
        "scenario-id form check",
        "validate-worker-output.py",
    )
    return any(
        "new verification.md or task plan" in item
        and all(term in item for term in needed)
        for item in items
    )


# ---------------------------------------------------------------------------
# AC-6 matchers over checklist bullets (normalized)
# ---------------------------------------------------------------------------


def has_ts_n_only_item(bullets):
    """AC-6: a checklist item requiring TS-n-only scenario IDs in new
    VERIFICATION.md files and task plans."""
    return any(
        all(
            term in bullet
            for term in (
                "verification.md",
                "task plan",
                "only ts-n scenario ids",
                "no hyphen-less id",
                "fenced code blocks and html comments",
            )
        )
        for bullet in bullets
    )


def missing_base_bullets(base, current):
    """AC-6: base-revision checklist bullets that are no longer present
    unchanged (subset check)."""
    present = set(current)
    return [bullet for bullet in base if bullet not in present]


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class SkillTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")
        cls.block = extract_rule_block(cls.text)
        cls.items = rule_items(cls.block)
        cls.pre_block = extract_rule_block(PRE_CHANGE_DOC)
        cls.pre_items = rule_items(cls.pre_block)


class TestAc7BlockLocation(SkillTestCase):
    def test_ac7_block_sits_between_template_end_and_checklist_heading(self):
        self.assertIn("scenario ids", flat(self.block))
        self.assertNotIn("Build Verification", self.block)
        self.assertNotIn(CHECKLIST_HEADING, self.block)
        self.assertNotIn("```", self.block)

    def test_ac7_pre_change_block_is_located_from_the_embedded_document(self):
        self.assertEqual(self.pre_block.strip(), PRE_CHANGE_RULE_BLOCK.strip())

    def test_ac7_negative_proof_locator_rejects_missing_or_duplicated_anchors(self):
        without_checklist = TEMPLATE_STUB + PRE_CHANGE_RULE_BLOCK
        with self.assertRaises(AssertionError):
            extract_rule_block(without_checklist)
        without_template = PRE_CHANGE_RULE_BLOCK + PRE_CHANGE_CHECKLIST
        with self.assertRaises(AssertionError):
            extract_rule_block(without_template)
        duplicated = PRE_CHANGE_DOC + "\n" + PRE_CHANGE_CHECKLIST
        with self.assertRaises(AssertionError):
            extract_rule_block(duplicated)

    def test_ac7_negative_proof_template_headings_in_the_fence_are_not_anchors(self):
        # The template's own `## Overview` line sits inside the fenced block and
        # must not end the template or start the block.
        self.assertNotIn("Overview", self.pre_block)
        self.assertNotIn("Test Scenarios", self.pre_block)


class TestAc1TsNOnly(SkillTestCase):
    def test_ac1_new_verification_and_task_plans_use_only_ts_n(self):
        self.assertTrue(states_ts_n_only(self.items))

    def test_ac1_negative_proof_pre_change_block_is_rejected(self):
        self.assertFalse(states_ts_n_only(self.pre_items))

    def test_ac1_negative_proof_task_plans_are_required(self):
        verification_only = rule_items(
            "- New VERIFICATION.md files use the TS-n form only: `TS`, a hyphen,\n"
            "  one or more digits.\n"
        )
        self.assertFalse(states_ts_n_only(verification_only))


class TestAc2TsnOnlyWhenReading(SkillTestCase):
    def test_ac2_tsn_form_is_valid_only_when_an_existing_document_is_read(self):
        self.assertTrue(states_tsn_only_when_reading(self.items))

    def test_ac2_no_sentence_grants_the_tsn_form_without_the_qualifier(self):
        self.assertEqual(unqualified_tsn_permissions(self.text), [])

    def test_ac2_the_unqualified_sentence_is_gone(self):
        self.assertNotIn("is also a valid scenario id", flat(self.text))

    def test_ac2_negative_proof_pre_change_block_is_rejected(self):
        self.assertFalse(states_tsn_only_when_reading(self.pre_items))

    def test_ac2_negative_proof_pre_change_text_is_found_by_the_grant_matcher(self):
        found = unqualified_tsn_permissions(PRE_CHANGE_DOC)
        self.assertEqual(len(found), 1)
        self.assertIn("is also a valid scenario ID", found[0])
        self.assertIn("is also a valid scenario id", flat(PRE_CHANGE_DOC))

    def test_ac2_negative_proof_grant_matcher_finds_other_wordings(self):
        samples = (
            "The TSn form may be written into a new task plan.",
            "The hyphen-less form is accepted in a new VERIFICATION.md.",
            "A new VERIFICATION.md is allowed to use TS13.",
            "The TSn form is valid in task plans.",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(unqualified_tsn_permissions(sample), [sample])

    def test_ac2_negative_proof_grant_matcher_accepts_qualified_and_unrelated(self):
        qualified = (
            "The TSn form is a valid scenario ID only when an existing document "
            "is read."
        )
        self.assertEqual(unqualified_tsn_permissions(qualified), [])
        unrelated = "Requirement IDs are hyphen-less (`FR1`, `NFR2`) and string-matched."
        self.assertEqual(unqualified_tsn_permissions(unrelated), [])

    def test_ac2_negative_proof_positive_matcher_needs_the_qualifier(self):
        unqualified = rule_items(
            "- The TSn form is a valid scenario ID, and the validator recognizes it.\n"
        )
        self.assertFalse(states_tsn_only_when_reading(unqualified))


class TestAc3ExistingStatementsKept(SkillTestCase):
    def test_ac3_only_two_scenario_id_forms_is_kept(self):
        self.assertTrue(keeps_only_two_forms(self.items))

    def test_ac3_literal_comparison_with_distinct_13_examples_is_kept(self):
        self.assertTrue(keeps_literal_comparison(self.items))

    def test_ac3_negative_proof_matchers_reject_a_block_without_the_statements(self):
        stripped = rule_items(
            "- New VERIFICATION.md files and new task plans use the TS-n form only.\n"
            "- A hyphen-less ID is rejected by the validator.\n"
        )
        self.assertFalse(keeps_only_two_forms(stripped))
        self.assertFalse(keeps_literal_comparison(stripped))

    def test_ac3_negative_proof_literal_comparison_needs_both_spellings(self):
        one_spelling = rule_items(
            "- Scenario IDs are compared as literal strings, so `TS13` is a\n"
            "  distinct ID.\n"
        )
        self.assertFalse(keeps_literal_comparison(one_spelling))
        no_distinct = rule_items(
            "- Scenario IDs are compared as literal strings: `TS13`, `TS-13`.\n"
        )
        self.assertFalse(keeps_literal_comparison(no_distinct))

    def test_ac3_both_statements_pre_existed_in_the_pre_change_block(self):
        # Retention criterion: the base revision already carried both
        # statements, so no red state exists for AC-3.
        self.assertTrue(keeps_only_two_forms(self.pre_items))
        self.assertTrue(keeps_literal_comparison(self.pre_items))


class TestAc4LegacySpecMapping(SkillTestCase):
    def test_ac4_hyphen_less_spec_maps_to_same_numbers_in_ts_n_form(self):
        self.assertTrue(states_legacy_spec_mapping(self.items))

    def test_ac4_negative_proof_pre_change_block_is_rejected(self):
        self.assertFalse(states_legacy_spec_mapping(self.pre_items))

    def test_ac4_negative_proof_both_halves_are_required(self):
        no_rewrite_clause = rule_items(
            "- When SPEC.md uses the hyphen-less form, the new VERIFICATION.md\n"
            "  uses the same numbers in the TS-n form.\n"
        )
        self.assertFalse(states_legacy_spec_mapping(no_rewrite_clause))
        no_mapping_clause = rule_items(
            "- When SPEC.md uses the hyphen-less form, SPEC.md is not rewritten.\n"
        )
        self.assertFalse(states_legacy_spec_mapping(no_mapping_clause))


class TestAc5ValidatorRejection(SkillTestCase):
    def test_ac5_hyphen_less_id_anywhere_gets_the_planner_result_rejected(self):
        self.assertTrue(states_validator_rejects_hyphen_less(self.items))

    def test_ac5_negative_proof_pre_change_block_is_rejected(self):
        self.assertFalse(states_validator_rejects_hyphen_less(self.pre_items))

    def test_ac5_negative_proof_every_element_is_required(self):
        complete = (
            "- A new VERIFICATION.md or task plan contains no hyphen-less ID anywhere\n"
            "  outside fenced code blocks and HTML comments, not only in the scenario\n"
            "  table. An implementation-planner result that breaks this is rejected by\n"
            "  the scenario-ID form check of\n"
            "  `em-workflow/scripts/validate-worker-output.py`.\n"
        )
        self.assertTrue(states_validator_rejects_hyphen_less(rule_items(complete)))
        for dropped in (
            "outside fenced code blocks and HTML comments, ",
            ", not only in the scenario\n  table",
            "implementation-planner ",
            "is rejected by",
            "the scenario-ID form check of",
            "validate-worker-output.py",
        ):
            with self.subTest(dropped=dropped):
                doctored = complete.replace(dropped, "")
                self.assertNotEqual(doctored, complete)
                self.assertFalse(
                    states_validator_rejects_hyphen_less(rule_items(doctored))
                )


class TestAc6Checklist(SkillTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bullets = checklist_bullets(cls.text)
        cls.base_bullets = checklist_bullets(PRE_CHANGE_DOC)

    def test_ac6_checklist_requires_ts_n_only_scenario_ids(self):
        self.assertTrue(has_ts_n_only_item(self.bullets))

    def test_ac6_every_base_revision_checklist_item_is_still_present_unchanged(self):
        self.assertEqual(len(self.base_bullets), 13)
        self.assertEqual(missing_base_bullets(self.base_bullets, self.bullets), [])

    def test_ac6_negative_proof_base_checklist_has_no_such_item(self):
        self.assertFalse(has_ts_n_only_item(self.base_bullets))
        self.assertFalse(has_ts_n_only_item(["no language-specific code blocks anywhere."]))

    def test_ac6_negative_proof_item_matcher_needs_every_element(self):
        complete = (
            "- [ ] New VERIFICATION.md and every task plan use only TS-n scenario\n"
            "      IDs, with no hyphen-less ID outside fenced code blocks and HTML\n"
            "      comments.\n"
        )
        self.assertTrue(has_ts_n_only_item(rule_items(complete)))
        for dropped in (
            "New VERIFICATION.md and every ",
            "task plan ",
            "use only TS-n scenario\n      IDs",
            "with no hyphen-less ID ",
            "outside fenced code blocks and HTML\n      comments",
        ):
            with self.subTest(dropped=dropped):
                doctored = complete.replace(dropped, "", 1)
                self.assertNotEqual(doctored, complete)
                self.assertFalse(has_ts_n_only_item(rule_items(doctored)))

    def test_ac6_negative_proof_subset_check_detects_a_removed_item(self):
        current = list(self.bullets)
        removed = current.pop(3)
        self.assertEqual(missing_base_bullets(self.base_bullets, current), [removed])

    def test_ac6_negative_proof_subset_check_detects_a_changed_item(self):
        current = list(self.bullets)
        index = current.index(self.base_bullets[1])
        current[index] = current[index].replace("cross-task", "any")
        self.assertEqual(
            missing_base_bullets(self.base_bullets, current), [self.base_bullets[1]]
        )

    def test_ac6_negative_proof_subset_check_accepts_the_pre_change_checklist(self):
        self.assertEqual(missing_base_bullets(self.base_bullets, self.base_bullets), [])


if __name__ == "__main__":
    unittest.main()
