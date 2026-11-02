"""Document-content tests for task0002 (scenario-id-ts-hyphen): the
spec-writer prompt, the SPEC.md template and the spec-writer contract number
every SPEC.md test scenario, and every
`payload.spec_index.test_scenarios[].id`, in the TS-n form (`TS-1`, `TS-2`,
...).

Covers the task0002 Acceptance Criteria:

- AC-1 (FR1): the `## Rendering REQUIREMENTS.md and SPEC.md` section of
  `em-workflow/agents/spec-writer.md` carries a scenario numbering rule that
  names `TS-1` and `TS-2`, gives the pattern `^TS-[1-9][0-9]*$` and requires
  literal agreement with `payload.spec_index.test_scenarios[].id` ->
  TestSpecWriterRenderingRule.
- AC-2 (FR1): the `## Output` section's `test_scenarios[]` bullet states that
  `id` is in the TS-n form -> TestSpecWriterOutputBullet.
- AC-3 (FR1): every placeholder item of the template's `## Test Scenarios`
  section (the regression line aside) begins with a TS-n ID, numbered from
  `TS-1` in document order with no gap and no repeat ->
  TestTemplateScenarioIds.
- AC-4 (FR1): the template's heading lines are identical in text and order to
  the base revision, and the E2E detection-result lines and the regression
  line are unchanged -> TestTemplateStructureUnchanged.
- AC-5 (FR1): the contract's `test_scenarios[]` entry states the TS-n form
  for `id` with `TS-1` as an example; the contract's gate_id set is unchanged
  -> TestContractScenarioEntry.
- AC-6 (FR1): none of the three documents holds a hyphen-less scenario ID, as
  found by the Hyphen-less ID detection rule (IMPLEMENTATION.md Shared
  Components) -> TestNoHyphenlessScenarioIds. The rule is implemented here
  and does not import the validator script, so this module stays independent
  of task0001.
- AC-7 (NFR3): this module asserts AC-1 to AC-6 and carries a negative proof
  per matcher (TestMatchersFailOnPreChangeExcerpts), each guarded for
  non-vacuity (TestPreChangeExcerptGuards).

Every literal-phrase matcher keeps the phrase in one module-level constant
shared by its positive test and its negative-proof test. Content assertions
read whitespace-normalized text so a line wrap never breaks an assertion.

Retention checks exempt from a negative proof against a pre-change excerpt
(they assert content that already existed before this task, so no red state
occurs; their matchers are proven on mutated copies instead):
- the AC-4 heading list and the E2E lines, the AC-5 gate_id set, and the
  FR/NFR numbering sentence retained in the SPEC.md bullet.

The hyphen-less detection of AC-6 is applied to the whole file as the plan
states and, additionally, to each section this task edits. The template
holds its whole body inside one outer fenced block next to nested fenced
blocks, so the fence-removal step pairs those fences in a way that leaves
part of the template prose out of the whole-file scan; the per-section scan
(sections contain no fence line) closes that gap.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_WRITER_PATH = REPO_ROOT / "em-workflow" / "agents" / "spec-writer.md"
SPEC_TEMPLATE_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "templates" / "spec-document.md"
)
SPEC_WRITER_CONTRACT_PATH = (
    REPO_ROOT
    / "em-workflow"
    / "references"
    / "contracts"
    / "spec-writer-contract.md"
)

# Section anchors (literal headings; line-anchored lookups).
RENDERING_HEADING = "## Rendering REQUIREMENTS.md and SPEC.md"
OUTPUT_HEADING = "## Output"
REPORT_HEADING = "## Report"
TEST_SCENARIOS_HEADING = "## Test Scenarios"
SECURITY_HEADING = "## Security Considerations"
CONTRACT_PAYLOAD_HEADING = "## `completed` payload"
CONTRACT_POSTCONDITIONS_HEADING = "## Post-conditions"
CONTRACT_GATE_VOCABULARY_HEADING = "## Gate option vocabulary"

SPEC_MD_BULLET_START = "- SPEC.md (English):"
OUTPUT_SCENARIOS_BULLET_START = "- `payload.spec_index.test_scenarios[]`"

# AC-1: the numbering rule's literals.
SCENARIO_ID_FIELD = "payload.spec_index.test_scenarios[].id"
RULE_NAMES_TS_1 = "`TS-1`"
RULE_NAMES_TS_2 = "`TS-2`"
RULE_PATTERN = "`^TS-[1-9][0-9]*$`"
RULE_SEQUENCE = "as one sequence starting at `TS-1`"
RULE_LITERAL_AGREEMENT = (
    "agree exactly, as literal strings, with `" + SCENARIO_ID_FIELD + "`"
)
FR_NFR_RULE_RETAINED = "`^(FR|NFR)[1-9][0-9]*$`"

# AC-2: the Output bullet states the ID form.
OUTPUT_ID_FORM_RE = re.compile(r"`id` is the TS-n string .*used in SPEC\.md")

# AC-3: the template item grammar.
SCENARIO_ID_RE = re.compile(r"^TS-[1-9][0-9]*$")
TS_ITEM_RE = re.compile(r"^- \[ \] (TS-[1-9][0-9]*)(?=[:\s])")
E2E_REGRESSION_LINE = "- [ ] Existing E2E tests pass without regression"
E2E_DETECTION_LINES = (
    '**Existing E2E tests**: {Phase 0.3 detection result or "None"}',
    '**Run command**: {Detected command or "Not detected"}',
)
EXPECTED_SUBSECTIONS = (
    "### Unit Tests",
    "### Integration Tests",
    "### E2E Tests",
    "### Edge Cases",
    "### Performance Tests",
)

# AC-4: the heading lines of the template at the base revision, in order.
BASE_TEMPLATE_HEADINGS = (
    "# SPEC.md テンプレート",
    "# Feature: {Feature Name}",
    "## Overview",
    "## Objectives",
    "## User Stories",
    "### US1: {User Story Title}",
    "### US2: {User Story Title}",
    "## Technical Requirements",
    "### Functional Requirements",
    "### Non-Functional Requirements",
    "## Implementation Approach",
    "### Architecture",
    "### Data Flow",
    "### API Design",
    "#### Endpoint 1: {Endpoint Name}",
    "### Database Schema",
    "#### Table 1: {table_name}",
    "#### Entity Relationship Diagram",
    "### Dependencies",
    "### File Structure",
    "## Declared Change Set",
    "## Test Scenarios",
    "### Unit Tests",
    "### Integration Tests",
    "### E2E Tests",
    "### Edge Cases",
    "### Performance Tests",
    "## Security Considerations",
    "## Error Handling",
    "### Error Codes",
    "### Error Flow",
    "## Performance Optimization",
    "### Performance Goals",
    "### Optimization Strategies",
    "### Caching Strategy",
    "## Success Criteria",
    "## Open Questions",
    "## Implementation Phases (if applicable)",
    "### Phase 1: {Phase Name}",
    "### Phase 2: {Phase Name}",
    "## References",
)
HEADING_LINE_RE = re.compile(r"^#{1,6} ")

# AC-5: the contract entry and the gate_id set at the base revision.
CONTRACT_FORM_PHRASE = "`id` uses the TS-n form"
CONTRACT_EXAMPLE_PHRASE = "`TS-1`"
CONTRACT_AGREEMENT_PHRASE = "agrees exactly with the IDs in SPEC.md"
BASE_GATE_IDS = frozenset(
    {
        "create-spec.artifact-overwrite",
        "design.artifact-overwrite",
        "create-plan.artifact-overwrite",
    }
)

# AC-6: the Hyphen-less ID detection rule. The first two patterns are the
# validator's noise-stripping step (fenced code blocks, HTML comments); the
# third is the read grammar. A match counts when it holds no hyphen and its
# immediately preceding character is not an ASCII letter or digit.
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
READ_GRAMMAR_RE = re.compile(r"TS-?\d+")
ASCII_ALNUM_RE = re.compile(r"[A-Za-z0-9]")

# Verbatim pre-change excerpts of the three documents at this task's base
# revision. Each is exactly the region the matcher below reads, captured
# before the edit; the negative proofs run the live matchers against them.
PRE_CHANGE_RENDERING_SECTION = (
    "## Rendering REQUIREMENTS.md and SPEC.md\n"
    "\n"
    "- REQUIREMENTS.md (Japanese): fill the template from `requirements_analysis`\n"
    "  — business objectives, functional and non-functional requirements,\n"
    "  acceptance criteria, edge cases, confirmed facts. No Change History\n"
    "  section.\n"
    "- SPEC.md (English): implementation-focused rendering of the same\n"
    "  requirements, referencing the requirements document. Number every\n"
    "  functional requirement `FR1`, `FR2`, … and non-functional requirement\n"
    "  `NFR1`, `NFR2`, … (hyphen-less, matching\n"
    "  `^(FR|NFR)[1-9][0-9]*$`) — these IDs must agree exactly, as literal\n"
    "  strings, with `payload.spec_index.requirements` and with the IDs\n"
    "  `workflow.yaml`'s requirements mapping already carries. No Last-Updated\n"
    "  / Change History sections.\n"
    "- Every requirement with `status: tbd` in `requirements_analysis` carries a\n"
    "  non-empty `tbd_reason` in both documents.\n"
    "\n"
)

PRE_CHANGE_OUTPUT_SECTION = (
    "## Output\n"
    "\n"
    "`completed` payload:\n"
    "\n"
    "- `payload.spec_index.requirements[]` — `id`, `title`, `status`,\n"
    "  `tbd_reason`; these IDs must agree exactly with the IDs appearing in\n"
    "  SPEC.md.\n"
    "- `payload.spec_index.test_scenarios[]` — `id`, `requirement_ids`.\n"
    "- `payload.assumptions_written[]` — every assumption you rendered into\n"
    "  either document, traced back to `requirements_analysis`.\n"
    "\n"
)

PRE_CHANGE_TEMPLATE_TEST_SCENARIOS = (
    "## Test Scenarios\n"
    "\n"
    "### Unit Tests\n"
    "- [ ] Test 1: {Description} - {Expected behavior}\n"
    "- [ ] Test 2: {Description} - {Expected behavior}\n"
    "\n"
    "### Integration Tests\n"
    "- [ ] Test 1: {Description} - {Expected behavior}\n"
    "- [ ] Test 2: {Description} - {Expected behavior}\n"
    "\n"
    "### E2E Tests\n"
    "**Existing E2E tests**: {Phase 0.3 detection result or \"None\"}\n"
    "**Run command**: {Detected command or \"Not detected\"}\n"
    "- [ ] Existing E2E tests pass without regression\n"
    "- [ ] Scenario 1: {User flow description}\n"
    "- [ ] Scenario 2: {User flow description}\n"
    "\n"
    "### Edge Cases\n"
    "- [ ] Edge case 1: {Description and expected handling}\n"
    "- [ ] Edge case 2: {Description and expected handling}\n"
    "\n"
    "### Performance Tests\n"
    "- [ ] Load test: {Scenario and acceptance criteria}\n"
    "- [ ] Stress test: {Scenario and acceptance criteria}\n"
    "\n"
)

PRE_CHANGE_CONTRACT_PAYLOAD_SECTION = (
    "## `completed` payload\n"
    "\n"
    "- `spec_index`:\n"
    "  - `requirements[]` — `id`, `title`, `status`, `tbd_reason`\n"
    "  - `test_scenarios[]` — `id`, `requirement_ids`\n"
    "- `assumptions_written[]`\n"
    "\n"
)


# --- helpers ---------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse whitespace runs (line wraps included) to one space."""
    return re.sub(r"\s+", " ", text)


def _heading_offset(text, heading):
    """Offset of the single line equal to `heading`; the anchor must exist
    exactly once so a slice can never silently move."""
    offsets = [
        m.start()
        for m in re.finditer(
            "^" + re.escape(heading) + "$", text, re.MULTILINE
        )
    ]
    if len(offsets) != 1:
        raise AssertionError(
            f"heading {heading!r} found {len(offsets)} times, expected 1"
        )
    return offsets[0]


def _section(text, heading, next_heading):
    """From `heading` up to (not including) the line `next_heading`."""
    start = _heading_offset(text, heading)
    after = start + len(heading)
    end = after + _heading_offset(text[after:], next_heading)
    return text[start:end]


def _top_level_bullet(section, start_marker):
    """The `- ` bullet beginning with `start_marker`, up to the next
    top-level `- ` line (or the end of the section)."""
    start = section.index(start_marker)
    after = start + len(start_marker)
    nxt = re.search(r"^- ", section[after:], re.MULTILINE)
    end = after + nxt.start() if nxt else len(section)
    return section[start:end]


def rendering_section(text):
    return _section(text, RENDERING_HEADING, OUTPUT_HEADING)


def output_section(text):
    return _section(text, OUTPUT_HEADING, REPORT_HEADING)


def template_scenarios_section(text):
    return _section(text, TEST_SCENARIOS_HEADING, SECURITY_HEADING)


def contract_payload_section(text):
    return _section(text, CONTRACT_PAYLOAD_HEADING, CONTRACT_POSTCONDITIONS_HEADING)


def contract_scenarios_entry(payload_section):
    """The nested `test_scenarios[]` list entry of the `spec_index` list,
    continuation lines included."""
    m = re.search(
        r"^  - `test_scenarios\[\]`.*?(?=^\s*- |^## |\Z)",
        payload_section,
        re.MULTILINE | re.DOTALL,
    )
    if m is None:
        raise AssertionError("test_scenarios[] entry not found")
    return m.group(0)


def _contains(text, phrase):
    return phrase in _normalize_ws(text)


# --- matchers ----------------------------------------------------------------


def template_scenario_items(section):
    """[(subsection heading, item line)] for every checkbox item that must
    carry a TS-n ID: all checkbox items of the section except the E2E
    regression line, which stays unchanged."""
    items = []
    current = None
    for line in section.split("\n"):
        if line.startswith("### "):
            current = line.strip()
        elif line.startswith("- [ ] ") and line != E2E_REGRESSION_LINE:
            items.append((current, line))
    return items


def template_id_problems(section):
    """Problems with the template's scenario items; [] when every item
    begins with a TS-n ID, the IDs run TS-1.. in document order with no gap
    and no repeat, and every expected subsection holds at least one item."""
    items = template_scenario_items(section)
    problems = []
    subsections = {sub for sub, _ in items}
    for sub in EXPECTED_SUBSECTIONS:
        if sub not in subsections:
            problems.append(f"{sub}: no scenario item")
    ids = []
    for sub, line in items:
        m = TS_ITEM_RE.match(line)
        if m is None:
            problems.append(f"{sub}: item does not begin with a TS-n ID: {line!r}")
        else:
            ids.append(m.group(1))
    expected = [f"TS-{n}" for n in range(1, len(ids) + 1)]
    if ids != expected:
        problems.append(f"IDs {ids} are not the sequence {expected}")
    return problems


def heading_lines(text):
    return [line for line in text.split("\n") if HEADING_LINE_RE.match(line)]


def headings_match_base(text):
    return heading_lines(text) == list(BASE_TEMPLATE_HEADINGS)


def e2e_lines_unchanged(text):
    block = "\n".join(E2E_DETECTION_LINES + (E2E_REGRESSION_LINE,)) + "\n"
    return block in text


def gate_ids(text):
    start = _heading_offset(text, CONTRACT_GATE_VOCABULARY_HEADING)
    return set(re.findall(r"^\| `([^`]+)` \|", text[start:], re.MULTILINE))


def hyphenless_ids(text):
    """Hyphen-less ID detection rule: strip fenced code blocks and HTML
    comments (inline code spans stay), then keep the read-grammar matches
    that hold no hyphen and whose preceding character is not an ASCII letter
    or digit. A match at the very start counts; a non-ASCII preceding
    character does not stop a match from counting."""
    text = FENCE_RE.sub("", text)
    text = HTML_COMMENT_RE.sub("", text)
    found = set()
    for m in READ_GRAMMAR_RE.finditer(text):
        if "-" in m.group(0):
            continue
        if m.start() > 0 and ASCII_ALNUM_RE.match(text[m.start() - 1]):
            continue
        found.add(m.group(0))
    return sorted(found)


# --- test data built inside this module -------------------------------------


def _number_items(excerpt, ids):
    """Give the excerpt's scenario items (regression line excepted) the
    given IDs in document order."""
    ids = list(ids)
    out = []
    for line in excerpt.split("\n"):
        if line.startswith("- [ ] ") and line != E2E_REGRESSION_LINE:
            line = "- [ ] " + ids.pop(0) + ": " + line[len("- [ ] "):]
        out.append(line)
    if ids:
        raise AssertionError(f"unused IDs: {ids}")
    return "\n".join(out)


ITEM_COUNT = 10  # placeholder items in the pre-change Test Scenarios excerpt
GOOD_IDS = [f"TS-{n}" for n in range(1, ITEM_COUNT + 1)]


# --- AC-1 --------------------------------------------------------------------


class TestSpecWriterRenderingRule(unittest.TestCase):
    """AC-1: the scenario numbering rule sits in the SPEC.md bullet of the
    `## Rendering REQUIREMENTS.md and SPEC.md` section, next to the FR/NFR
    numbering sentence."""

    @classmethod
    def setUpClass(cls):
        cls.bullet = _top_level_bullet(
            rendering_section(_read(SPEC_WRITER_PATH)), SPEC_MD_BULLET_START
        )

    def test_ac1_names_ts_1(self):
        self.assertTrue(_contains(self.bullet, RULE_NAMES_TS_1), self.bullet)

    def test_ac1_names_ts_2(self):
        self.assertTrue(_contains(self.bullet, RULE_NAMES_TS_2), self.bullet)

    def test_ac1_gives_the_scenario_id_pattern(self):
        self.assertTrue(_contains(self.bullet, RULE_PATTERN), self.bullet)

    def test_ac1_states_one_sequence_starting_at_ts_1(self):
        self.assertTrue(_contains(self.bullet, RULE_SEQUENCE), self.bullet)

    def test_ac1_requires_literal_agreement_with_spec_index_ids(self):
        self.assertTrue(
            _contains(self.bullet, RULE_LITERAL_AGREEMENT), self.bullet
        )

    def test_ac1_fr_nfr_numbering_sentence_is_retained(self):
        self.assertTrue(_contains(self.bullet, FR_NFR_RULE_RETAINED))


# --- AC-2 --------------------------------------------------------------------


class TestSpecWriterOutputBullet(unittest.TestCase):
    """AC-2: the `## Output` section's `test_scenarios[]` bullet states that
    `id` is the TS-n string used in SPEC.md."""

    @classmethod
    def setUpClass(cls):
        cls.bullet = _top_level_bullet(
            output_section(_read(SPEC_WRITER_PATH)),
            OUTPUT_SCENARIOS_BULLET_START,
        )

    def test_ac2_bullet_states_id_is_the_ts_n_string_used_in_spec_md(self):
        self.assertIsNotNone(
            OUTPUT_ID_FORM_RE.search(_normalize_ws(self.bullet)), self.bullet
        )


# --- AC-3 --------------------------------------------------------------------


class TestTemplateScenarioIds(unittest.TestCase):
    """AC-3: every placeholder item of the template's Test Scenarios section
    begins with a TS-n ID, numbered from TS-1 in document order with no gap
    and no repeat."""

    @classmethod
    def setUpClass(cls):
        cls.section = template_scenarios_section(_read(SPEC_TEMPLATE_PATH))

    def test_ac3_every_item_has_an_id_and_the_ids_run_from_ts_1(self):
        self.assertEqual(template_id_problems(self.section), [])

    def test_ac3_every_id_matches_the_scenario_id_pattern(self):
        items = template_scenario_items(self.section)
        self.assertGreaterEqual(len(items), len(EXPECTED_SUBSECTIONS))
        for _sub, line in items:
            m = TS_ITEM_RE.match(line)
            self.assertIsNotNone(m, line)
            self.assertRegex(m.group(1), SCENARIO_ID_RE)


# --- AC-4 --------------------------------------------------------------------


class TestTemplateStructureUnchanged(unittest.TestCase):
    """AC-4: heading lines identical to the base revision; the E2E
    detection-result lines and the regression line unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SPEC_TEMPLATE_PATH)

    def test_ac4_heading_lines_are_identical_to_the_base_revision(self):
        self.assertEqual(heading_lines(self.text), list(BASE_TEMPLATE_HEADINGS))

    def test_ac4_e2e_detection_and_regression_lines_are_unchanged(self):
        self.assertTrue(e2e_lines_unchanged(self.text))


# --- AC-5 --------------------------------------------------------------------


class TestContractScenarioEntry(unittest.TestCase):
    """AC-5: the contract's `test_scenarios[]` entry states the TS-n form for
    `id` with `TS-1` as an example and agreement with SPEC.md; the gate_id
    set is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SPEC_WRITER_CONTRACT_PATH)
        cls.entry = contract_scenarios_entry(contract_payload_section(cls.text))

    def test_ac5_entry_states_the_ts_n_form_for_id(self):
        self.assertTrue(_contains(self.entry, CONTRACT_FORM_PHRASE), self.entry)

    def test_ac5_entry_gives_ts_1_as_an_example(self):
        self.assertTrue(
            _contains(self.entry, CONTRACT_EXAMPLE_PHRASE), self.entry
        )

    def test_ac5_entry_states_exact_agreement_with_spec_md_ids(self):
        self.assertTrue(
            _contains(self.entry, CONTRACT_AGREEMENT_PHRASE), self.entry
        )

    def test_ac5_gate_id_set_is_unchanged(self):
        self.assertEqual(gate_ids(self.text), set(BASE_GATE_IDS))


# --- AC-6 --------------------------------------------------------------------


class TestNoHyphenlessScenarioIds(unittest.TestCase):
    """AC-6: none of the three documents holds a hyphen-less scenario ID."""

    @classmethod
    def setUpClass(cls):
        cls.spec_writer = _read(SPEC_WRITER_PATH)
        cls.template = _read(SPEC_TEMPLATE_PATH)
        cls.contract = _read(SPEC_WRITER_CONTRACT_PATH)

    def test_ac6_spec_writer_whole_file_has_no_hyphenless_id(self):
        self.assertEqual(hyphenless_ids(self.spec_writer), [])

    def test_ac6_template_whole_file_has_no_hyphenless_id(self):
        self.assertEqual(hyphenless_ids(self.template), [])

    def test_ac6_contract_whole_file_has_no_hyphenless_id(self):
        self.assertEqual(hyphenless_ids(self.contract), [])

    def test_ac6_edited_sections_have_no_hyphenless_id(self):
        for name, section in (
            ("spec-writer rendering", rendering_section(self.spec_writer)),
            ("spec-writer output", output_section(self.spec_writer)),
            ("template test scenarios", template_scenarios_section(self.template)),
            ("contract payload", contract_payload_section(self.contract)),
        ):
            with self.subTest(section=name):
                self.assertEqual(hyphenless_ids(section), [])

    def test_ac6_each_document_names_a_ts_n_id(self):
        # Non-vacuity: a scan of text that no longer carries any scenario ID
        # would pass trivially.
        for name, text in (
            ("spec-writer.md", self.spec_writer),
            ("spec-document.md", self.template),
            ("spec-writer-contract.md", self.contract),
        ):
            with self.subTest(document=name):
                self.assertRegex(text, r"TS-[1-9][0-9]*")


# --- AC-7: negative proofs ---------------------------------------------------

# Detection cases built here as test data: (label, text, expected result).
HYPHENLESS_FLAGGED_CASES = (
    ("match at the very start of the text", "TS1 is a scenario", ["TS1"]),
    ("preceded by a space", "see TS12 here", ["TS12"]),
    ("preceded by non-ASCII text", "説明TS3を参照", ["TS3"]),
    ("inside an inline code span", "see `TS4` here", ["TS4"]),
    ("preceded by a hyphen", "-TS5", ["TS5"]),
    ("all consecutive digits are consumed", "TS130", ["TS130"]),
    ("mixed with the TS-n form", "TS-13 and TS13", ["TS13"]),
)
HYPHENLESS_IGNORED_CASES = (
    ("preceded by an ASCII letter", "XTS1", []),
    ("preceded by a lowercase ASCII letter", "see aTS2", []),
    ("preceded by an ASCII digit", "9TS1", []),
    ("a longer alphanumeric run", "UTS46", []),
    ("TS-n form only", "TS-1 and TS-22", []),
    ("inside a fenced code block", "```\nTS1\n```", []),
    ("inside an HTML comment", "<!-- TS2 -->", []),
)


class TestMatchersFailOnPreChangeExcerpts(unittest.TestCase):
    """AC-7: every matcher above is shown failing against a pre-change
    excerpt (or, for the retention matchers and the hyphen-less detector,
    against a mutated or derived copy)."""

    @classmethod
    def setUpClass(cls):
        cls.pre_rendering_bullet = _top_level_bullet(
            PRE_CHANGE_RENDERING_SECTION, SPEC_MD_BULLET_START
        )
        cls.pre_output_bullet = _top_level_bullet(
            PRE_CHANGE_OUTPUT_SECTION, OUTPUT_SCENARIOS_BULLET_START
        )
        cls.pre_contract_entry = contract_scenarios_entry(
            PRE_CHANGE_CONTRACT_PAYLOAD_SECTION
        )

    # AC-1 matchers.
    def test_rule_names_ts_1_is_absent_before_the_change(self):
        self.assertFalse(_contains(self.pre_rendering_bullet, RULE_NAMES_TS_1))

    def test_rule_names_ts_2_is_absent_before_the_change(self):
        self.assertFalse(_contains(self.pre_rendering_bullet, RULE_NAMES_TS_2))

    def test_rule_pattern_is_absent_before_the_change(self):
        self.assertFalse(_contains(self.pre_rendering_bullet, RULE_PATTERN))

    def test_rule_sequence_is_absent_before_the_change(self):
        self.assertFalse(_contains(self.pre_rendering_bullet, RULE_SEQUENCE))

    def test_rule_literal_agreement_is_absent_before_the_change(self):
        self.assertFalse(
            _contains(self.pre_rendering_bullet, RULE_LITERAL_AGREEMENT)
        )

    # AC-2 matcher.
    def test_output_id_form_statement_is_absent_before_the_change(self):
        self.assertIsNone(
            OUTPUT_ID_FORM_RE.search(_normalize_ws(self.pre_output_bullet))
        )

    # AC-3 matcher.
    def test_template_id_matcher_flags_every_pre_change_item(self):
        problems = template_id_problems(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS)
        flagged = [p for p in problems if "does not begin with a TS-n ID" in p]
        self.assertEqual(len(flagged), ITEM_COUNT, problems)

    def test_template_id_matcher_accepts_a_correctly_numbered_section(self):
        # Positive control: the matcher is not failing for every input.
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, GOOD_IDS)
        self.assertEqual(template_id_problems(numbered), [])

    def test_template_id_matcher_flags_a_gap(self):
        ids = GOOD_IDS[:4] + GOOD_IDS[5:] + ["TS-11"]
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, ids)
        self.assertNotEqual(template_id_problems(numbered), [])

    def test_template_id_matcher_flags_a_repeat(self):
        ids = GOOD_IDS[:5] + GOOD_IDS[4:-1]
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, ids)
        self.assertNotEqual(template_id_problems(numbered), [])

    def test_template_id_matcher_flags_a_sequence_not_starting_at_ts_1(self):
        ids = [f"TS-{n}" for n in range(2, ITEM_COUNT + 2)]
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, ids)
        self.assertNotEqual(template_id_problems(numbered), [])

    def test_template_id_matcher_flags_a_document_order_violation(self):
        ids = [GOOD_IDS[1], GOOD_IDS[0]] + GOOD_IDS[2:]
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, ids)
        self.assertNotEqual(template_id_problems(numbered), [])

    def test_template_id_matcher_flags_hyphenless_ids(self):
        ids = [i.replace("TS-", "TS") for i in GOOD_IDS]
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, ids)
        self.assertNotEqual(template_id_problems(numbered), [])

    def test_template_id_matcher_flags_a_zero_id(self):
        ids = ["TS-0"] + GOOD_IDS[1:]
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, ids)
        self.assertNotEqual(template_id_problems(numbered), [])

    def test_template_id_matcher_flags_an_emptied_subsection(self):
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, GOOD_IDS)
        emptied = numbered.replace(
            "- [ ] TS-9: Load test: {Scenario and acceptance criteria}\n", ""
        ).replace(
            "- [ ] TS-10: Stress test: {Scenario and acceptance criteria}\n", ""
        )
        self.assertNotEqual(emptied, numbered)
        self.assertTrue(
            any(
                "### Performance Tests: no scenario item" in p
                for p in template_id_problems(emptied)
            )
        )

    # AC-4 matchers (retention): shown failing on mutated copies.
    def test_heading_matcher_accepts_the_base_list(self):
        self.assertTrue(
            headings_match_base("\n".join(BASE_TEMPLATE_HEADINGS) + "\n")
        )

    def test_heading_matcher_flags_a_renamed_heading(self):
        headings = list(BASE_TEMPLATE_HEADINGS)
        headings[headings.index("### Edge Cases")] = "### Edge Cases and Limits"
        self.assertFalse(headings_match_base("\n".join(headings) + "\n"))

    def test_heading_matcher_flags_a_removed_heading(self):
        headings = list(BASE_TEMPLATE_HEADINGS)
        headings.remove("### Unit Tests")
        self.assertFalse(headings_match_base("\n".join(headings) + "\n"))

    def test_heading_matcher_flags_an_added_heading(self):
        headings = list(BASE_TEMPLATE_HEADINGS)
        headings.insert(headings.index("### Performance Tests") + 1, "### Notes")
        self.assertFalse(headings_match_base("\n".join(headings) + "\n"))

    def test_heading_matcher_flags_a_reordered_heading(self):
        headings = list(BASE_TEMPLATE_HEADINGS)
        i = headings.index("### Integration Tests")
        headings[i], headings[i + 1] = headings[i + 1], headings[i]
        self.assertFalse(headings_match_base("\n".join(headings) + "\n"))

    def test_e2e_matcher_accepts_the_pre_change_lines(self):
        self.assertTrue(e2e_lines_unchanged(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS))

    def test_e2e_matcher_flags_an_id_on_the_regression_line(self):
        mutated = PRE_CHANGE_TEMPLATE_TEST_SCENARIOS.replace(
            E2E_REGRESSION_LINE,
            "- [ ] TS-5: Existing E2E tests pass without regression",
        )
        self.assertNotEqual(mutated, PRE_CHANGE_TEMPLATE_TEST_SCENARIOS)
        self.assertFalse(e2e_lines_unchanged(mutated))

    def test_e2e_matcher_flags_an_altered_detection_line(self):
        mutated = PRE_CHANGE_TEMPLATE_TEST_SCENARIOS.replace(
            "**Run command**:", "**Run command (E2E)**:"
        )
        self.assertNotEqual(mutated, PRE_CHANGE_TEMPLATE_TEST_SCENARIOS)
        self.assertFalse(e2e_lines_unchanged(mutated))

    # AC-5 matchers.
    def test_contract_form_statement_is_absent_before_the_change(self):
        self.assertFalse(_contains(self.pre_contract_entry, CONTRACT_FORM_PHRASE))

    def test_contract_ts_1_example_is_absent_before_the_change(self):
        self.assertFalse(
            _contains(self.pre_contract_entry, CONTRACT_EXAMPLE_PHRASE)
        )

    def test_contract_agreement_statement_is_absent_before_the_change(self):
        self.assertFalse(
            _contains(self.pre_contract_entry, CONTRACT_AGREEMENT_PHRASE)
        )

    def test_gate_id_matcher_accepts_the_base_set_and_flags_changes(self):
        rows = [
            f"| `{g}` | `overwrite` | meaning |" for g in sorted(BASE_GATE_IDS)
        ]
        head = (
            CONTRACT_GATE_VOCABULARY_HEADING
            + "\n\n| gate_id | option_id | meaning |\n|---|---|---|\n"
        )
        base = set(BASE_GATE_IDS)
        self.assertEqual(gate_ids(head + "\n".join(rows) + "\n"), base)
        added = rows + ["| `extra.gate` | `overwrite` | meaning |"]
        self.assertNotEqual(gate_ids(head + "\n".join(added) + "\n"), base)
        self.assertNotEqual(gate_ids(head + "\n".join(rows[1:]) + "\n"), base)

    # AC-6 detector.
    def test_detector_flags_the_cases_it_must_flag(self):
        for label, text, expected in HYPHENLESS_FLAGGED_CASES:
            with self.subTest(case=label):
                self.assertEqual(hyphenless_ids(text), expected)

    def test_detector_ignores_the_cases_it_must_ignore(self):
        for label, text, expected in HYPHENLESS_IGNORED_CASES:
            with self.subTest(case=label):
                self.assertEqual(hyphenless_ids(text), expected)

    def test_detector_flags_a_hyphenless_pre_change_template_excerpt(self):
        mutated = PRE_CHANGE_TEMPLATE_TEST_SCENARIOS.replace(
            "- [ ] Test 1:", "- [ ] TS1:"
        )
        self.assertNotEqual(mutated, PRE_CHANGE_TEMPLATE_TEST_SCENARIOS)
        self.assertEqual(hyphenless_ids(mutated), ["TS1"])

    def test_detector_flags_a_hyphenless_copy_of_a_numbered_section(self):
        numbered = _number_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS, GOOD_IDS)
        self.assertEqual(hyphenless_ids(numbered), [])
        hyphenless = numbered.replace("TS-", "TS")
        self.assertEqual(
            hyphenless_ids(hyphenless),
            sorted(f"TS{n}" for n in range(1, ITEM_COUNT + 1)),
        )

    def test_detector_flags_a_hyphenless_id_in_a_pre_change_rule_bullet(self):
        mutated = self.pre_rendering_bullet + "  Scenarios are numbered `TS1`.\n"
        self.assertEqual(hyphenless_ids(mutated), ["TS1"])


class TestPreChangeExcerptGuards(unittest.TestCase):
    """Non-vacuity guards: each pre-change excerpt still carries the anchors
    the negative proofs depend on, so a negative proof can never pass
    because its excerpt was emptied or truncated."""

    def test_rendering_excerpt_carries_the_spec_md_bullet_and_fr_nfr_rule(self):
        self.assertIn(SPEC_MD_BULLET_START, PRE_CHANGE_RENDERING_SECTION)
        self.assertTrue(
            _contains(PRE_CHANGE_RENDERING_SECTION, FR_NFR_RULE_RETAINED)
        )
        self.assertTrue(
            _contains(
                PRE_CHANGE_RENDERING_SECTION,
                "agree exactly, as literal strings, with "
                "`payload.spec_index.requirements`",
            )
        )

    def test_output_excerpt_carries_the_test_scenarios_bullet(self):
        self.assertIn(OUTPUT_SCENARIOS_BULLET_START, PRE_CHANGE_OUTPUT_SECTION)
        self.assertTrue(
            _contains(
                _top_level_bullet(
                    PRE_CHANGE_OUTPUT_SECTION, OUTPUT_SCENARIOS_BULLET_START
                ),
                "`id`, `requirement_ids`",
            )
        )

    def test_template_excerpt_carries_every_subsection_and_the_e2e_lines(self):
        self.assertTrue(
            PRE_CHANGE_TEMPLATE_TEST_SCENARIOS.startswith(TEST_SCENARIOS_HEADING)
        )
        for sub in EXPECTED_SUBSECTIONS:
            self.assertIn(sub + "\n", PRE_CHANGE_TEMPLATE_TEST_SCENARIOS)
        self.assertTrue(e2e_lines_unchanged(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS))
        self.assertEqual(
            len(template_scenario_items(PRE_CHANGE_TEMPLATE_TEST_SCENARIOS)),
            ITEM_COUNT,
        )

    def test_contract_excerpt_carries_the_test_scenarios_entry(self):
        entry = contract_scenarios_entry(PRE_CHANGE_CONTRACT_PAYLOAD_SECTION)
        self.assertTrue(_contains(entry, "`id`, `requirement_ids`"))


if __name__ == "__main__":
    unittest.main()
