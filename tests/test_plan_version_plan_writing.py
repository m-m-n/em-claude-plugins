"""Tests for task0001 (plan-version-bump-per-commit): the plan-writing skill
gains a `## Plugin Version Handling` section so every plan (create-plan and
rework) is consistent with plugin-version-guard's per-commit check in
non-exempt repositories and carries no version instruction in exempt ones.

Covers task0001 Acceptance Criteria
(feature-docs/plan-version-bump-per-commit/tasks/task0001.md):

- AC-1: the heading `## Plugin Version Handling` exists exactly once and its
  non-exempt subsection states the four elements (patch bump of
  `plugin.json` in the same commit, marketplace alignment, advance on each
  commit, strictly greater than the value at the immediately preceding HEAD
  by per-component numeric comparison).
- AC-2: newly added plugins and marketplace entries without a version are
  neither bumped nor aligned.
- AC-3: keep-unchanged instructions are prohibited (both quoted examples
  named), the files rule names `plugin.json` and `marketplace.json`, and each
  plugin-changing task plan carries the per-commit instruction itself.
- AC-4: exempt / non-exempt are defined by the workflow file at the
  repository root; the exempt subsection instructs no version change and
  names only where to bump for a minor or major bump, with no concrete value.
- AC-5: exemption state and plugin locations come from the dispatch's
  `plugin_versioning` value; the section covers both planners; conflict-time
  commits are cited (path plus protocol name), not restated.
- AC-6: the Pre-Save Self-Verification Checklist gains the three items.
- AC-7: the negative check (a statement permitting an unchanged version on a
  plugin-changing commit in a non-exempt repository) rejects an in-test
  permissive sample and accepts the section's own prohibited-example
  quotations and exempt subsection; the section has no fenced code block and
  no concrete version value. The whole suite passing is verified by running
  `python3 -m unittest discover -s tests`, not re-asserted here.

Per IMPLEMENTATION.md Conventions: standard library only, the repository
root derived from this file's location, nothing read from `~/.claude`,
assertions only on this task's own document (plan-writing/SKILL.md), anchors
on pinned headings and key terms rather than whole sentences, and a negative
proof for every custom matcher. Per test/README.md no test module imports
another, so the small extraction helpers are local to this module.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "plan-writing" / "SKILL.md"

SECTION_HEADING = "## Plugin Version Handling"
DEFINITIONS_HEADING = "### Definitions"
INPUT_HEADING = "### Input"
NON_EXEMPT_HEADING = "### Non-exempt repositories"
EXEMPT_HEADING = "### Exempt repositories"
CHECKLIST_HEADING = "## Pre-Save Self-Verification Checklist (MANDATORY)"

PROHIBITED_EXAMPLES = (
    "only the first task bumps the version",
    "subsequent tasks / rework tasks do not bump the version",
)

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
LIST_START_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?")
DOTTED_VERSION_RE = re.compile(r"\b\d+\.\d+(?:\.\d+)*\b")


# ---------------------------------------------------------------------------
# Extraction helpers (fence-aware, so template headings inside fenced blocks
# of SKILL.md are never mistaken for real headings)
# ---------------------------------------------------------------------------


def read_skill():
    return SKILL_PATH.read_text(encoding="utf-8")


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


def extract_section(text, heading):
    """The heading line plus everything up to the next heading of the same or
    a shallower level, outside fenced blocks. Raises AssertionError when the
    heading line is absent or appears more than once."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    fenced = _fence_flags(lines)
    starts = [
        i for i, line in enumerate(lines)
        if not fenced[i] and line.rstrip() == heading
    ]
    if len(starts) != 1:
        raise AssertionError(
            f"expected exactly one heading line {heading!r}, found {len(starts)}"
        )
    end = len(lines)
    for j in range(starts[0] + 1, len(lines)):
        if not fenced[j] and 0 < _heading_level(lines[j]) <= level:
            end = j
            break
    return "\n".join(lines[starts[0]:end]) + "\n"


def split_blocks(text):
    """Group lines into blocks (one paragraph or one list item each) and
    return (h2_heading, h3_heading, block_text) triples. Heading lines are not
    blocks. Headings inside fenced blocks are ignored."""
    lines = text.splitlines()
    fenced = _fence_flags(lines)
    out = []
    h2 = h3 = ""
    current = []

    def flush():
        if current:
            out.append((h2, h3, " ".join(current)))
            current.clear()

    for i, line in enumerate(lines):
        level = 0 if fenced[i] else _heading_level(line)
        if level:
            flush()
            if level <= 2:
                h2, h3 = line.rstrip(), ""
            elif level == 3:
                h3 = line.rstrip()
            continue
        if not line.strip():
            flush()
            continue
        if LIST_START_RE.match(line):
            flush()
            current.append(LIST_START_RE.sub("", line, count=1).strip())
        else:
            current.append(line.strip())
    flush()
    return out


def sentences(block):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", block) if s.strip()]


# ---------------------------------------------------------------------------
# Negative check (FR7): a statement permitting an unchanged version on a
# plugin-changing commit in a non-exempt repository.
#
# The prohibition itself quotes the forbidden phrases and the exempt
# subsection legitimately says plans change no version, so a plain phrase
# search would misfire. Scope: everything except the Exempt repositories
# subsection and exempt-scoped checklist items; sentences that carry the
# prohibition (a negated speech act such as "must not state", or the word
# "prohibited") are excluded.
# ---------------------------------------------------------------------------

_LATER = r"(?:subsequent|later|other|rework|following|remaining)\s+(?:tasks?|commits?)"
PERMISSIVE_PATTERNS = (
    # "only the first task bumps the version"
    re.compile(
        r"\bonly\s+(?:the\s+)?(?:first|initial)\s+(?:task|commit)\b.*"
        r"\b(?:bumps?|changes?|raises?|updates?)\b",
        re.I,
    ),
    # "subsequent tasks / rework tasks do not bump the version"
    re.compile(
        rf"\b{_LATER}(?:\s*/\s*{_LATER})*\s+"
        r"(?:do(?:es)?\s+not|don't|doesn't|need\s+not|must\s+not|should\s+not|"
        r"never|skip|leave|keep|retain)\b",
        re.I,
    ),
    # "keeps the version unchanged", "leaves it unchanged", "left as is"
    re.compile(r"\b(?:unchanged|as[- ]is)\b", re.I),
    # "do not bump the version", "need not change it", "never touch"
    re.compile(
        r"\b(?:do(?:es)?\s+not|don't|doesn't|need\s+not|needn't|must\s+not|"
        r"should\s+not|may\s+not|never|no\s+need\s+to)\s+(?:\w+\s+){0,2}?"
        r"(?:bump|change|raise|touch|update|modify|increase|advance)\w*",
        re.I,
    ),
    # "skip the version bump", "no version bump", "bump is optional"
    re.compile(
        r"\b(?:skip|skips|skipping|omit|omits|omitting|forgo|forgoes|without)\s+"
        r"(?:\w+\s+){0,2}?(?:bump|version\s+(?:bump|change|increase))",
        re.I,
    ),
    re.compile(r"\bno\s+(?:version\s+)?(?:bump|change|increase)\b", re.I),
    re.compile(
        r"\bbump\w*\s+(?:is|are)\s+(?:optional|unnecessary|not\s+required|"
        r"not\s+needed)\b",
        re.I,
    ),
    re.compile(r"\bmay\s+(?:leave|keep|skip|omit)\b", re.I),
)
_VERSION_WORD_RE = re.compile(r"\bversion|bump", re.I)
PROHIBITION_MARKER_RE = re.compile(
    r"\b(?:prohibit\w*|forbid\w*|"
    r"(?:no|never|must\s+not|do\s+not|does\s+not|may\s+not)\s+(?:\w+\s+){0,3}?"
    r"(?:say|says|state|states|contain|contains|carry|carries|include|includes|"
    r"instruct|instructs|write|writes|give|gives|permit|permits|allow|allows|"
    r"tell|tells|imply|implies)\b)",
    re.I,
)
EXEMPT_SCOPED_RE = re.compile(r"(?<![\w-])exempt\s+repositor", re.I)


def carries_prohibition(sentence):
    return bool(PROHIBITION_MARKER_RE.search(sentence))


def is_permissive_sentence(sentence):
    if carries_prohibition(sentence):
        return False
    if not _VERSION_WORD_RE.search(sentence):
        return False
    return any(pattern.search(sentence) for pattern in PERMISSIVE_PATTERNS)


def find_permissive_statements(text):
    found = []
    for h2, h3, block in split_blocks(text):
        if h2 == SECTION_HEADING and h3 == EXEMPT_HEADING:
            continue
        if h2 == CHECKLIST_HEADING and EXEMPT_SCOPED_RE.search(block):
            continue
        for sentence in sentences(block):
            if is_permissive_sentence(sentence):
                found.append(sentence)
    return found


def has_fenced_block(section_text):
    return any(FENCE_RE.match(line) for line in section_text.splitlines())


def concrete_versions(section_text):
    return DOTTED_VERSION_RE.findall(section_text)


CONFLICT_TIME_RESTATEMENT_TERMS = (
    "resolve via parent-side adoption",
    "re-implement on updated parent",
    "--theirs",
)


def restated_conflict_terms(section_text):
    folded = flat(section_text)
    return [t for t in CONFLICT_TIME_RESTATEMENT_TERMS if t in folded]


# ---------------------------------------------------------------------------
# Shared fixtures and assertions
# ---------------------------------------------------------------------------


class SkillTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read_skill()

    def section(self):
        return extract_section(self.text, SECTION_HEADING)

    def subsection(self, heading):
        return extract_section(self.section(), heading)

    def assert_terms(self, text, terms):
        folded = flat(text)
        missing = [t for t in terms if t.casefold() not in folded]
        self.assertEqual(missing, [], f"terms missing: {missing}")


# ---------------------------------------------------------------------------
# Helper negative proofs
# ---------------------------------------------------------------------------


class TestExtractionHelpers(unittest.TestCase):
    DOC = (
        "# Title\n\n## A\n\ntext a\n\n### A1\n\nsub a1\n\n## B\n\ntext b\n\n"
        "```markdown\n## A\n```\n"
    )

    def test_extract_section_stops_at_next_same_level_heading(self):
        section = extract_section(self.DOC, "## A")
        self.assertIn("sub a1", section)
        self.assertNotIn("text b", section)

    def test_extract_subsection_stops_at_shallower_heading(self):
        section = extract_section(self.DOC, "### A1")
        self.assertIn("sub a1", section)
        self.assertNotIn("text b", section)

    def test_extract_section_raises_when_heading_absent(self):
        with self.assertRaises(AssertionError):
            extract_section(self.DOC, "## Missing")

    def test_extract_section_ignores_heading_inside_fenced_block(self):
        # "## A" appears once as a real heading and once inside a fence.
        self.assertIn("text a", extract_section(self.DOC, "## A"))

    def test_extract_section_raises_when_heading_duplicated(self):
        with self.assertRaises(AssertionError):
            extract_section("## A\n\nx\n\n## A\n\ny\n", "## A")

    def test_split_blocks_separates_list_items_and_tracks_headings(self):
        blocks = split_blocks("## H2\n\n### H3\n\n- one\n  more\n- two\n")
        self.assertEqual(
            blocks, [("## H2", "### H3", "one more"), ("## H2", "### H3", "two")]
        )

    def test_has_fenced_block_detects_fence(self):
        self.assertTrue(has_fenced_block("a\n```\ncode\n```\n"))
        self.assertFalse(has_fenced_block("a\nplain\n"))

    def test_concrete_versions_detects_dotted_literal_only(self):
        self.assertEqual(concrete_versions("bump to 0.2.12 now"), ["0.2.12"])
        self.assertEqual(concrete_versions("plugin.json and marketplace.json"), [])

    def test_restated_conflict_terms_detects_restatement(self):
        forged = "Commit with message: Resolve via parent-side adoption."
        self.assertEqual(
            restated_conflict_terms(forged), ["resolve via parent-side adoption"]
        )
        self.assertEqual(restated_conflict_terms("cites the protocol only"), [])


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------


class TestAc1PerCommitBumpRule(SkillTestCase):
    def test_ac1_heading_is_pinned_level_two_exact_text(self):
        self.assertIn(SECTION_HEADING, self.text.splitlines())
        self.section()  # raises unless exactly one such heading

    def test_ac1_section_has_distinct_non_exempt_and_exempt_subsections(self):
        non_exempt = self.subsection(NON_EXEMPT_HEADING)
        exempt = self.subsection(EXEMPT_HEADING)
        self.assertNotEqual(non_exempt, exempt)

    def test_ac1_non_exempt_states_patch_bump_in_same_commit(self):
        self.assert_terms(
            self.subsection(NON_EXEMPT_HEADING),
            ["patch", "plugin.json", "same commit"],
        )

    def test_ac1_non_exempt_states_marketplace_alignment(self):
        self.assert_terms(
            self.subsection(NON_EXEMPT_HEADING),
            [
                ".claude-plugin/marketplace.json",
                "same name",
                "carries a version",
                "same value",
            ],
        )

    def test_ac1_non_exempt_states_advance_on_each_commit(self):
        self.assertRegex(
            flat(self.subsection(NON_EXEMPT_HEADING)),
            r"advances? on each (?:such )?commit",
        )

    def test_ac1_non_exempt_states_strictly_greater_than_preceding_head(self):
        self.assert_terms(
            self.subsection(NON_EXEMPT_HEADING),
            [
                "strictly greater",
                "per-component numeric comparison",
                "immediately preceding HEAD",
            ],
        )


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------


class TestAc2OutsideTheRule(SkillTestCase):
    def test_ac2_new_plugins_and_unversioned_entries_are_not_bumped(self):
        self.assert_terms(
            self.subsection(NON_EXEMPT_HEADING),
            [
                "newly added",
                "no `plugin.json` at base",
                "marketplace entry without a version",
                "neither bumped nor aligned",
            ],
        )


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------


class TestAc3ProhibitionFilesAndCarriage(SkillTestCase):
    def test_ac3_prohibits_keep_unchanged_with_both_quoted_examples(self):
        non_exempt = self.subsection(NON_EXEMPT_HEADING)
        self.assert_terms(
            non_exempt, ["must not", "unchanged", "plugin-changing commit"]
        )
        for example in PROHIBITED_EXAMPLES:
            self.assertIn(f'"{example}"', flat(non_exempt))

    def test_ac3_files_rule_names_plugin_json_and_marketplace_json(self):
        self.assert_terms(
            self.subsection(NON_EXEMPT_HEADING),
            [
                "files",
                "`plugin.json`",
                "`.claude-plugin/marketplace.json`",
                "marketplace_versioned",
            ],
        )

    def test_ac3_each_task_plan_carries_the_per_commit_instruction_itself(self):
        non_exempt = self.subsection(NON_EXEMPT_HEADING)
        self.assert_terms(
            non_exempt,
            [
                "every task plan",
                "per-commit instruction",
                "itself",
                "rework task plan",
            ],
        )


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------


class TestAc4DefinitionsAndExempt(SkillTestCase):
    def test_ac4_defines_exempt_and_non_exempt_by_workflow_file_at_root(self):
        self.assert_terms(
            self.subsection(DEFINITIONS_HEADING),
            [
                "exempt repository",
                "non-exempt repository",
                ".github/workflows/plugin-version-bump.yml",
                "repository root",
            ],
        )

    def test_ac4_defines_under_a_plugin_and_comparison_rule(self):
        self.assert_terms(
            self.subsection(DEFINITIONS_HEADING),
            [
                "under a plugin",
                ".claude-plugin/plugin.json",
                "strictly greater",
                "per-component numeric comparison",
            ],
        )

    def test_ac4_exempt_subsection_instructs_no_version_change(self):
        self.assert_terms(
            self.subsection(EXEMPT_HEADING), ["instruct no version change"]
        )

    def test_ac4_exempt_subsection_names_only_where_for_minor_or_major(self):
        self.assert_terms(
            self.subsection(EXEMPT_HEADING),
            ["minor", "major", "where", "concrete value"],
        )


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------


class TestAc5InputAndCitations(SkillTestCase):
    def test_ac5_input_comes_from_plugin_versioning_not_own_discovery(self):
        self.assert_terms(
            self.subsection(INPUT_HEADING),
            [
                "`plugin_versioning`",
                "dispatch",
                "never discovers",
                "em-workflow/references/contracts/planner-contract.md",
                "plugin_versioning (dispatch-resolved value)",
            ],
        )

    def test_ac5_applies_to_both_planners(self):
        self.assert_terms(self.section(), ["implementation-planner", "rework-planner"])

    def test_ac5_cites_parent_side_adoption_protocol_by_path_and_name(self):
        self.assert_terms(
            self.section(),
            [
                "em-workflow/skills/worktree-task-workflow/SKILL.md",
                "parent-side adoption protocol",
            ],
        )

    def test_ac5_does_not_restate_the_conflict_time_rule(self):
        self.assertEqual(restated_conflict_terms(self.section()), [])


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------


def checklist_bullets(text):
    return [
        flat(block)
        for h2, _h3, block in split_blocks(text)
        if h2 == CHECKLIST_HEADING
    ]


def has_files_and_per_commit_item(bullets):
    return any(
        all(t in b for t in ("plugin.json", "marketplace_versioned", "per-commit", "files"))
        for b in bullets
    )


def has_no_keep_unchanged_item(bullets):
    return any(
        all(t in b for t in ("unchanged", "plugin-changing commit")) for b in bullets
    )


def has_exempt_no_instruction_item(bullets):
    return any(
        EXEMPT_SCOPED_RE.search(b)
        and "version change" in b
        and "concrete version value" in b
        for b in bullets
    )


class TestAc6ChecklistItems(SkillTestCase):
    def test_ac6_checklist_has_files_and_per_commit_instruction_item(self):
        self.assertTrue(has_files_and_per_commit_item(checklist_bullets(self.text)))

    def test_ac6_checklist_has_no_keep_unchanged_instruction_item(self):
        self.assertTrue(has_no_keep_unchanged_item(checklist_bullets(self.text)))

    def test_ac6_checklist_has_exempt_no_instruction_item(self):
        self.assertTrue(has_exempt_no_instruction_item(checklist_bullets(self.text)))

    def test_ac6_negative_proof_matchers_reject_unrelated_checklist(self):
        unrelated = ["no language-specific code blocks anywhere."]
        self.assertFalse(has_files_and_per_commit_item(unrelated))
        self.assertFalse(has_no_keep_unchanged_item(unrelated))
        self.assertFalse(has_exempt_no_instruction_item(unrelated))

    def test_ac6_existing_checklist_items_are_kept(self):
        bullets = checklist_bullets(self.text)
        self.assertTrue(
            any("threat-model.md is written with exactly one verdict" in b for b in bullets)
        )
        self.assertTrue(
            any("no mitigation exists without a recorded threat" in b for b in bullets)
        )


# ---------------------------------------------------------------------------
# AC-7
# ---------------------------------------------------------------------------

PERMISSIVE_SAMPLES = (
    "Only the first task bumps the version; subsequent tasks leave it unchanged.",
    "Rework tasks do not bump the version.",
    "Subsequent tasks / rework tasks do not bump the version.",
    "The plugin version may stay unchanged when a later commit changes the same plugin.",
    'The plan instructs "only the first task bumps the version".',
    "A task plan can skip the version bump for files under a plugin.",
    "A bump is optional for documentation-only commits.",
    "Plans need not bump the version for documentation-only commits.",
)

ACCEPTED_SAMPLES = (
    'Plans must not state or imply that the version stays unchanged, for example '
    '"only the first task bumps the version".',
    'Prohibited instructions include "subsequent tasks / rework tasks do not bump '
    'the version".',
    "No plan text contains an instruction that keeps the version unchanged on a "
    "plugin-changing commit.",
    "Every commit that changes a file under a plugin bumps the patch component "
    "of that plugin's version in the same commit.",
    "The version advances on each such commit.",
)

DOCTORED_TEMPLATE = (
    "## Plugin Version Handling\n\n"
    "### Non-exempt repositories\n\n"
    "- Every plugin-changing commit bumps the patch component.\n"
    "{non_exempt}"
    "\n### Exempt repositories\n\n"
    "- Plans instruct no version change for any task.\n"
    "{exempt}"
    "\n## Pre-Save Self-Verification Checklist (MANDATORY)\n\n"
    "- [ ] Exempt repository: no task plan instructs a version change.\n"
    "{checklist}"
)


def doctor(non_exempt="", exempt="", checklist=""):
    return DOCTORED_TEMPLATE.format(
        non_exempt=non_exempt, exempt=exempt, checklist=checklist
    )


class TestAc7NegativeCheck(SkillTestCase):
    def test_ac7_negative_check_rejects_each_permissive_sample(self):
        for sample in PERMISSIVE_SAMPLES:
            with self.subTest(sample=sample):
                self.assertTrue(is_permissive_sentence(sample))
                self.assertEqual(
                    find_permissive_statements(doctor(non_exempt=f"- {sample}\n")),
                    [sample],
                )

    def test_ac7_negative_check_accepts_prohibition_and_rule_wording(self):
        for sample in ACCEPTED_SAMPLES:
            with self.subTest(sample=sample):
                self.assertFalse(is_permissive_sentence(sample))
                self.assertEqual(
                    find_permissive_statements(doctor(non_exempt=f"- {sample}\n")),
                    [],
                )

    def test_ac7_negative_check_ignores_permissive_text_in_exempt_subsection(self):
        sample = "Later tasks do not bump the version."
        self.assertEqual(find_permissive_statements(doctor(exempt=f"- {sample}\n")), [])
        self.assertEqual(
            find_permissive_statements(doctor(non_exempt=f"- {sample}\n")), [sample]
        )

    def test_ac7_negative_check_ignores_exempt_scoped_checklist_item(self):
        sample = "Exempt repository: later tasks do not bump the version."
        self.assertEqual(find_permissive_statements(doctor(checklist=f"- [ ] {sample}\n")), [])
        non_exempt_item = "Non-exempt repository: later tasks do not bump the version."
        self.assertEqual(
            find_permissive_statements(doctor(checklist=f"- [ ] {non_exempt_item}\n")),
            [non_exempt_item],
        )

    def test_ac7_negative_check_rejects_permissive_text_outside_the_section(self):
        # Permission written in another part of SKILL.md (here: a task
        # decomposition style numbered rule) is caught too.
        text = (
            "## Task decomposition rules\n\n"
            "1. Only the first task bumps the version of a plugin.\n"
        )
        self.assertEqual(
            find_permissive_statements(text),
            ["Only the first task bumps the version of a plugin."],
        )

    def test_ac7_real_skill_md_has_no_permissive_statement(self):
        self.section()  # the section must exist before the check means anything
        self.assertEqual(find_permissive_statements(self.text), [])

    def test_ac7_real_prohibited_example_sentences_are_accepted(self):
        non_exempt = self.subsection(NON_EXEMPT_HEADING)
        quoting = [
            s
            for _h2, _h3, block in split_blocks(non_exempt)
            for s in sentences(block)
            if any(example in flat(s) for example in PROHIBITED_EXAMPLES)
        ]
        self.assertTrue(quoting, "no sentence quotes the prohibited examples")
        for sentence in quoting:
            with self.subTest(sentence=sentence):
                self.assertTrue(carries_prohibition(sentence))
                self.assertFalse(is_permissive_sentence(sentence))

    def test_ac7_real_exempt_subsection_is_accepted(self):
        exempt = self.subsection(EXEMPT_HEADING)
        doctored = doctor(exempt=exempt)
        self.assertEqual(find_permissive_statements(doctored), [])

    def test_ac7_negative_proof_prohibition_marker_needs_negated_speech_act(self):
        self.assertTrue(carries_prohibition("Plans must not state that it stays."))
        self.assertTrue(carries_prohibition("Prohibited instructions include these."))
        self.assertFalse(carries_prohibition("Plans must not bump the version."))
        self.assertFalse(carries_prohibition("Rework tasks do not bump the version."))


class TestAc7SectionShape(SkillTestCase):
    def test_ac7_section_has_no_fenced_code_block(self):
        self.assertFalse(has_fenced_block(self.section()))

    def test_ac7_section_has_no_concrete_version_value(self):
        self.assertEqual(concrete_versions(self.section()), [])

    def test_ac7_negative_proof_shape_matchers_fire_on_forged_section(self):
        forged = "## Plugin Version Handling\n\n```\nbump to 0.2.12\n```\n"
        self.assertTrue(has_fenced_block(extract_section(forged, SECTION_HEADING)))
        self.assertEqual(
            concrete_versions(extract_section(forged, SECTION_HEADING)), ["0.2.12"]
        )


if __name__ == "__main__":
    unittest.main()
