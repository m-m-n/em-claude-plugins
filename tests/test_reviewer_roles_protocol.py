"""Tests for task0004: reviewer-side role framing (llm-led-review).

Covers task0004 Acceptance Criteria
(feature-docs/llm-led-review/tasks/task0004.md):

- AC-1: em-workflow/references/review-protocol.md states that exactly one
  reviewer runs per selected perspective -- a harness reviewer (codex /
  litellm) as the main review, the Claude reviewer only as the
  no-available-entry fallback -- and contains no surviving text framing a
  harness reviewer as a second opinion, a cross-validation partner or an
  agreement source.
- AC-2: review-protocol.md still contains every input field name it
  documents today, every skip_reason string byte-identical, the retryable-set
  statement, the three severity levels, the investigation budget, the
  output-schema rules, the read-only constraint and the untrusted-input
  section -- all frozen, verified by section hash where the section is
  wholly unchanged.
- AC-3: review-output-schema.json parses as JSON, its finding `category`
  enum contains all six registry perspectives including `license`, and its
  `required` lists, `additionalProperties` flags, `severity` enum and root
  `source` enum are unchanged.
- AC-4: em-workflow/agents/reviewer.md states the fallback-only dispatch
  condition in both its description and its body, keeps its frontmatter
  fields unchanged, and keeps its protocol-following steps intact.
- AC-5: em-workflow/agents/codex-reviewer.md states the primary-review role
  in both its description and its body, keeps its frontmatter fields
  unchanged, and keeps its scratchpad temp-file discipline section verbatim.
- AC-6: this file asserts AC-1 through AC-5, including the negative
  assertions of AC-1 (this docstring plus the test classes below constitute
  that coverage).

Following the pattern of tests/test_codex_reviewer_temp_file_isolation.py:
locate files relative to this test file's own path, anchor section
extraction on literal headings/markers, and freeze wholly-unchanged sections
by sha256 of their exact bytes (computed once from the pre-edit file) rather
than embedding large text blocks that risk a transcription mismatch. Small,
single-line/short-phrase invariants (skip_reason strings, field names) are
checked as plain substrings, matching this repository's existing convention.
"""

import hashlib
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PROTOCOL_PATH = REPO_ROOT / "em-workflow" / "references" / "review-protocol.md"
SCHEMA_PATH = REPO_ROOT / "em-workflow" / "references" / "review-output-schema.json"
REVIEWER_AGENT_PATH = REPO_ROOT / "em-workflow" / "agents" / "reviewer.md"
CODEX_REVIEWER_AGENT_PATH = REPO_ROOT / "em-workflow" / "agents" / "codex-reviewer.md"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_whitespace(text):
    """Collapse whitespace runs (including markdown's ~79-column line wraps)
    to a single space, so multi-word phrase checks survive reflowing that
    does not change meaning."""
    return re.sub(r"\s+", " ", text)


def _extract_section(text, start_marker, end_marker, label):
    """Return text[start_marker:end_marker), raising AssertionError naming
    `label` if either marker is missing -- so a renamed/removed anchor fails
    loudly instead of silently matching nothing."""
    if start_marker not in text:
        raise AssertionError(f"{label}: missing start marker {start_marker!r}")
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    if end_marker not in text[start:]:
        raise AssertionError(f"{label}: missing end marker {end_marker!r}")
    end = text.index(end_marker, start)
    return text[start:end]


def _assert_section_hash(text, start_marker, end_marker, expected_sha256, label):
    """The real check behind every 'this section is frozen' assertion below,
    extracted into a helper so TestValidationDetectsRegressions can run it
    against forged/mutated input inside assertRaises."""
    section = _extract_section(text, start_marker, end_marker, label)
    actual = hashlib.sha256(section.encode("utf-8")).hexdigest()
    if actual != expected_sha256:
        raise AssertionError(
            f"{label}: section byte content changed "
            f"(expected sha256 {expected_sha256}, got {actual})"
        )


# ---------------------------------------------------------------------------
# AC-1: review-protocol.md dispatch-rule statement + no second-opinion framing
# ---------------------------------------------------------------------------

# The three harness-description bullets (em-workflow:reviewer /
# em-workflow:codex-reviewer / vertex-review:vertex-reviewer) must stay
# verbatim per the task plan's Design section ("keeps all three entries and
# their harness descriptions"). Hash computed from the pre-edit file.
PROTOCOL_BULLETS_START = (
    "- `em-workflow:reviewer` (Claude) — loads the perspective skill named in its"
)
PROTOCOL_BULLETS_END = "For a selected perspective, the review phase dispatches"
PROTOCOL_BULLETS_SHA256 = (
    "102ddfba4736854ad0d2eb04bac8a8a7e1dad22d3566dca6e6da82da4eaffbf3"
)

# Phrases that would frame a harness reviewer as a second opinion / a
# cross-validation partner / an agreement source (AC-1 negative assertions),
# plus the exact old phrasing ("Any cross-model reviewer") this task rewords
# in the Skip Semantics section.
FORBIDDEN_FRAMING_PHRASES = [
    "second opinion",
    "cross-model check",
    "agreement partner",
    "cross-validation partner",
    "agreement source",
    "cross-model reviewer",
]

DISPATCH_RULE_PHRASES = [
    "exactly one",
    "main review",
    "fallback",
    "no available harness entry",
    "never dispatched together",
]


class TestSingleReviewerDispatchStatement(unittest.TestCase):
    """AC-1 (positive): the opening section states that exactly one reviewer
    runs per selected perspective -- a harness reviewer as the main review,
    the Claude reviewer only as the no-available-entry fallback."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PROTOCOL_PATH)
        cls.normalized = _normalize_whitespace(cls.text.lower())

    def test_states_exactly_one_reviewer_dispatched_per_perspective(self):
        self.assertIn(
            "exactly one",
            self.normalized,
            "AC-1: must state that exactly one reviewer is dispatched per "
            "selected perspective",
        )

    def test_states_harness_reviewer_as_main_review(self):
        self.assertIn(
            "main review",
            self.normalized,
            "AC-1: must frame the harness reviewer (codex/litellm) as the "
            "MAIN review for the perspective",
        )

    def test_states_claude_reviewer_as_fallback_only_when_no_harness_entry(self):
        self.assertIn(
            "fallback",
            self.normalized,
            "AC-1: must state the Claude reviewer runs only as fallback",
        )
        self.assertIn(
            "no available harness entry",
            self.normalized,
            "AC-1: fallback condition must be 'no available harness entry' "
            "in the perspective's registry chain",
        )

    def test_states_the_two_are_mutually_exclusive(self):
        self.assertIn(
            "never dispatched together",
            self.normalized,
            "AC-1: must state a harness reviewer and the Claude reviewer "
            "are never dispatched together for the same perspective",
        )

    def test_three_harness_description_bullets_stay_verbatim(self):
        _assert_section_hash(
            self.text,
            PROTOCOL_BULLETS_START,
            PROTOCOL_BULLETS_END,
            PROTOCOL_BULLETS_SHA256,
            "AC-1 (harness description bullets)",
        )


class TestNoSecondOpinionFramingSurvives(unittest.TestCase):
    """AC-1 (negative): no surviving text frames a harness reviewer as a
    second opinion, a cross-validation partner, or an agreement source."""

    @classmethod
    def setUpClass(cls):
        cls.lowered = _read(PROTOCOL_PATH).lower()

    def test_no_forbidden_framing_phrase_present(self):
        for phrase in FORBIDDEN_FRAMING_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(
                    phrase,
                    self.lowered,
                    f"AC-1: forbidden framing phrase {phrase!r} must not "
                    "survive in review-protocol.md",
                )


# ---------------------------------------------------------------------------
# AC-2: review-protocol.md frozen invariants (inputs, skip_reason strings,
# retryable set, severity, investigation budget, output schema, read-only,
# untrusted-input)
# ---------------------------------------------------------------------------

INPUT_FIELD_NAMES = [
    "perspective",
    "perspective_skill",
    "model",
    "review_mode",
    "protocol_path",
    "schema_path",
    "changed_files",
    "diff_cmd_quoted",
    "spec_path",
    "project_root",
    "round_context",
    "lessons",
]

# All skip_reason string values documented in review-protocol.md today.
SKIP_REASON_STRINGS = [
    "protocol_unresolved",
    "no_spec",
    "harness_unavailable",
    "rate_limited",
    "budget_exhausted",
    "skill_unresolved",
    "schema_unresolved",
    "scratchpad_unavailable",
    "review_data_too_large",
]

RETRYABLE_SKIP_REASONS = ["rate_limited", "budget_exhausted", "harness_unavailable"]

SEVERITY_LEVELS = ["critical", "high", "medium"]

FROZEN_SECTIONS = [
    (
        "Inputs",
        "## Inputs (all reviewers)",
        "## Step 0 Fail-Closed Resolution",
        "2866d813218cc7b7d445e506d93cb0a468094b1c8713855d036475bd1b942400",
    ),
    (
        "Investigation Budget",
        "## Investigation Budget",
        "## Severity",
        "37b1cba2d815315bb68494b933381d9d102486f0e7ead73111643533961330d7",
    ),
    (
        "Severity",
        "## Severity",
        "## Output Schema",
        "70cec02e098416fb3a2b800b017e141eb17f24f121bec5abd45cde6969e6ecf4",
    ),
    (
        "Output Schema",
        "## Output Schema",
        "## Round Continuity",
        "8a40ceb994ad00288c6c9dcf412c13fcba2be1e2faafd02e7fde856f19f1344e",
    ),
    (
        "Read-only Constraint",
        "## Read-only Constraint",
        "## Untrusted-Input Handling",
        "cd8b63caac1b267bd7abd8aac87ad8fc41770104bb82973c52687f40d04e2513",
    ),
    (
        "Untrusted-Input Handling",
        "## Untrusted-Input Handling",
        None,
        "54535adf0677b89e1e2f9ab64be8ad24f2a73f33a1f4dd3d09bf9a3be548e5c6",
    ),
]


class TestFrozenInputFieldNames(unittest.TestCase):
    """AC-2: every input field name documented today is still documented,
    scoped to the Inputs section so a stray use of a common word (e.g.
    'model' in prose elsewhere) cannot false-positive this check."""

    @classmethod
    def setUpClass(cls):
        text = _read(PROTOCOL_PATH)
        cls.inputs_section = _extract_section(
            text,
            "## Inputs (all reviewers)",
            "## Step 0 Fail-Closed Resolution",
            "AC-2 (Inputs section)",
        )

    def test_every_documented_input_field_name_present(self):
        for field in INPUT_FIELD_NAMES:
            with self.subTest(field=field):
                self.assertIn(
                    f"`{field}`",
                    self.inputs_section,
                    f"AC-2: input field name `{field}` must still be "
                    "documented in the Inputs section",
                )


class TestFrozenSkipReasonStrings(unittest.TestCase):
    """AC-2: every skip_reason string is byte-identical to today's set."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PROTOCOL_PATH)

    def test_every_skip_reason_string_present_verbatim(self):
        for reason in SKIP_REASON_STRINGS:
            with self.subTest(reason=reason):
                self.assertIn(
                    f'"{reason}"',
                    self.text,
                    f"AC-2: skip_reason value {reason!r} must still appear "
                    "verbatim",
                )

    def test_retryable_set_statement_present(self):
        normalized = _normalize_whitespace(self.text)
        self.assertIn(
            "the **retryable** set",
            normalized,
            "AC-2: the doc must still state the retryable-set concept",
        )
        self.assertIn(
            "walks the perspective's fallback chain on exactly these",
            normalized,
            "AC-2: the doc must still state Phase R2b walks the chain on "
            "exactly these strings",
        )

    def test_exactly_three_retryable_reasons_named(self):
        for reason in RETRYABLE_SKIP_REASONS:
            with self.subTest(reason=reason):
                self.assertIn(f'"{reason}"', self.text)
        self.assertEqual(
            3,
            len(RETRYABLE_SKIP_REASONS),
            "AC-2: exactly three reasons are retryable",
        )

    def test_non_retryable_skip_reasons_statement_present(self):
        normalized = _normalize_whitespace(self.text)
        self.assertIn(
            "These last two are NOT retryable, like every value outside "
            "the three above",
            normalized,
            "AC-2: the doc must still mark the last two skip reasons "
            "non-retryable",
        )


class TestFrozenSeverityLevels(unittest.TestCase):
    """AC-2: the three severity levels stay exactly critical/high/medium."""

    def test_three_severity_levels_defined_verbatim(self):
        text = _read(PROTOCOL_PATH)
        section = _extract_section(
            text, "## Severity", "## Output Schema", "AC-2 (Severity section)"
        )
        for level in SEVERITY_LEVELS:
            with self.subTest(level=level):
                self.assertIn(f"`{level}`", section)


class TestFrozenSectionsUnchanged(unittest.TestCase):
    """AC-2: sections that carry no task0004 edit stay byte-identical to
    the pre-edit file, verified by sha256 rather than a giant embedded
    literal (avoids transcription risk while still proving verbatim)."""

    def test_frozen_sections_hash_unchanged(self):
        text = _read(PROTOCOL_PATH)
        for label, start, end, expected in FROZEN_SECTIONS:
            with self.subTest(section=label):
                _assert_section_hash(text, start, end, expected, f"AC-2 ({label})")


# ---------------------------------------------------------------------------
# AC-3: review-output-schema.json category enum widened to six perspectives
# ---------------------------------------------------------------------------

REGISTRY_PERSPECTIVES = [
    "security",
    "performance",
    "architecture",
    "spec",
    "comprehensive",
    "license",
]

FROZEN_SCHEMA_ROOT = {
    "required": ["findings", "summary", "skipped", "skip_reason", "source"],
    "additionalProperties": False,
}

FROZEN_FINDING_REQUIRED = [
    "file",
    "line",
    "line_end",
    "severity",
    "category",
    "title",
    "description",
    "suggestion",
]

FROZEN_SEVERITY_ENUM = ["critical", "high", "medium"]
FROZEN_SOURCE_ENUM = ["claude", "codex", "litellm"]


class TestReviewOutputSchemaCategoryWidened(unittest.TestCase):
    """AC-3: schema parses; category enum contains all six registry
    perspectives including license; required/additionalProperties/severity
    enum/source enum are unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _read(SCHEMA_PATH)
        cls.data = json.loads(cls.raw)

    def test_schema_parses_as_json(self):
        # setUpClass already parsed it; re-parse here so THIS test fails
        # (not errors at class level) on malformed JSON.
        json.loads(self.raw)

    def test_category_enum_contains_all_six_registry_perspectives(self):
        category_enum = self.data["properties"]["findings"]["items"]["properties"][
            "category"
        ]["enum"]
        for perspective in REGISTRY_PERSPECTIVES:
            with self.subTest(perspective=perspective):
                self.assertIn(
                    perspective,
                    category_enum,
                    f"AC-3: category enum must include registry perspective "
                    f"{perspective!r}",
                )
        self.assertEqual(
            6,
            len(REGISTRY_PERSPECTIVES),
            "AC-3: exactly six registry perspectives are expected",
        )

    def test_root_required_and_additional_properties_unchanged(self):
        self.assertEqual(
            FROZEN_SCHEMA_ROOT["required"],
            self.data["required"],
            "AC-3: root required list must be unchanged",
        )
        self.assertEqual(
            FROZEN_SCHEMA_ROOT["additionalProperties"],
            self.data["additionalProperties"],
            "AC-3: root additionalProperties must be unchanged",
        )

    def test_finding_required_and_additional_properties_unchanged(self):
        finding_schema = self.data["properties"]["findings"]["items"]
        self.assertEqual(
            FROZEN_FINDING_REQUIRED,
            finding_schema["required"],
            "AC-3: finding required list must be unchanged",
        )
        self.assertFalse(
            finding_schema["additionalProperties"],
            "AC-3: finding additionalProperties must stay false",
        )

    def test_severity_enum_unchanged(self):
        severity_enum = self.data["properties"]["findings"]["items"]["properties"][
            "severity"
        ]["enum"]
        self.assertEqual(FROZEN_SEVERITY_ENUM, severity_enum)

    def test_root_source_enum_unchanged(self):
        source_enum = self.data["properties"]["source"]["enum"]
        self.assertEqual(FROZEN_SOURCE_ENUM, source_enum)


# ---------------------------------------------------------------------------
# AC-4: agents/reviewer.md fallback-only role statement
# ---------------------------------------------------------------------------

REVIEWER_FROZEN_FRONTMATTER_LINES = [
    "name: reviewer",
    "model: opus",
    "effort: xhigh",
    "tools: Read, Glob, Grep, Bash, Skill",
]

# Everything from the original opening body sentence through EOF (i.e. the
# Step 0/1/2/3 protocol-following steps) must stay byte-identical; this
# task only inserts a new sentence BEFORE this anchor.
REVIEWER_STEPS_START = (
    "You review the current code change from **exactly one perspective**"
)
REVIEWER_STEPS_SHA256 = (
    "31bd8390460eb3145cead4d99279226e2100f034eafafd4d0127a3699d8625c1"
)

FALLBACK_ROLE_PHRASES = ["fallback", "no available harness entry"]


class TestReviewerAgentFallbackRoleStatement(unittest.TestCase):
    """AC-4: description and body state the fallback-only dispatch
    condition; frontmatter fields and protocol-following steps unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEWER_AGENT_PATH)
        frontmatter_end = cls.text.index("---", 3)
        cls.frontmatter = cls.text[:frontmatter_end]
        cls.body = cls.text[frontmatter_end:]

    def test_description_states_fallback_only_dispatch_condition(self):
        description_match = re.search(
            r"^description:\s*(.*)$", self.frontmatter, re.MULTILINE
        )
        self.assertIsNotNone(
            description_match, "AC-4: frontmatter must have a description field"
        )
        description = description_match.group(1)
        for phrase in FALLBACK_ROLE_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(
                    phrase,
                    description,
                    f"AC-4: description must state {phrase!r}",
                )

    def test_body_states_fallback_only_dispatch_condition(self):
        # Only the portion before the unchanged original opening sentence
        # is new task0004 prose.
        new_prose_end = self.body.index(REVIEWER_STEPS_START)
        new_prose = _normalize_whitespace(self.body[:new_prose_end].lower())
        for phrase in FALLBACK_ROLE_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(
                    phrase,
                    new_prose,
                    f"AC-4: body role statement must state {phrase!r}",
                )
        self.assertIn(
            "never run alongside a harness reviewer",
            new_prose,
            "AC-4: body must state mutual exclusivity with a harness "
            "reviewer for the same perspective",
        )

    def test_frontmatter_fields_unchanged(self):
        for line in REVIEWER_FROZEN_FRONTMATTER_LINES:
            with self.subTest(line=line):
                self.assertIn(line, self.frontmatter)

    def test_protocol_following_steps_intact(self):
        _assert_section_hash(
            self.body,
            REVIEWER_STEPS_START,
            None,
            REVIEWER_STEPS_SHA256,
            "AC-4 (Steps 0-3)",
        )


# ---------------------------------------------------------------------------
# AC-5: agents/codex-reviewer.md primary-review role statement
# ---------------------------------------------------------------------------

CODEX_REVIEWER_FROZEN_FRONTMATTER_LINES = [
    "name: codex-reviewer",
    "model: sonnet",
    "effort: medium",
    "tools: Bash, Read, Skill",
    "skills:",
    "  - codex-prompting",
]

# Everything from "## Step 0" through EOF -- including the availability
# probe, the wrapper-script delegation, the skip objects, and critically the
# scratchpad temp-file discipline section -- must stay byte-identical; this
# task only edits the description and the opening body sentence before this
# anchor.
CODEX_REVIEWER_STEPS_START = (
    "## Step 0: Read the protocol (strict fail-closed resolution)"
)
CODEX_REVIEWER_STEPS_SHA256 = (
    "3a90a4d3197b507caa036ea70cc7211f0f4115bd133077c41a696567bbec0dee"
)

PRIMARY_ROLE_PHRASE = "main review"


class TestCodexReviewerAgentPrimaryRoleStatement(unittest.TestCase):
    """AC-5: description and body state the primary-review role through
    Codex CLI; frontmatter fields unchanged; scratchpad temp-file discipline
    section (and every other Step) verbatim."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CODEX_REVIEWER_AGENT_PATH)
        frontmatter_end = cls.text.index("---", 3)
        cls.frontmatter = cls.text[:frontmatter_end]
        cls.body = cls.text[frontmatter_end:]

    def test_description_states_primary_review_role(self):
        description_match = re.search(
            r"^description:\s*(.*)$", self.frontmatter, re.MULTILINE
        )
        self.assertIsNotNone(
            description_match, "AC-5: frontmatter must have a description field"
        )
        description = description_match.group(1).lower()
        self.assertIn(
            "main",
            description,
            "AC-5: description must state the MAIN-review role",
        )
        self.assertNotIn(
            "クロスバリデーション",
            description_match.group(1),
            "AC-5: description must not still frame this as a "
            "cross-validation run",
        )

    def test_body_opening_sentence_states_primary_review_role(self):
        new_prose_end = self.body.index(CODEX_REVIEWER_STEPS_START)
        opening_prose = _normalize_whitespace(self.body[:new_prose_end].lower())
        self.assertIn(
            PRIMARY_ROLE_PHRASE,
            opening_prose,
            "AC-5: body opening sentence must state the main-review role",
        )
        self.assertNotIn(
            "independent second-model review",
            opening_prose,
            "AC-5: body must not still frame this as an independent "
            "second-model review for cross-validation",
        )

    def test_frontmatter_fields_unchanged(self):
        for line in CODEX_REVIEWER_FROZEN_FRONTMATTER_LINES:
            with self.subTest(line=line):
                self.assertIn(line, self.frontmatter)

    def test_steps_including_scratchpad_discipline_section_verbatim(self):
        _assert_section_hash(
            self.body,
            CODEX_REVIEWER_STEPS_START,
            None,
            CODEX_REVIEWER_STEPS_SHA256,
            "AC-5 (Steps 0-6, incl. scratchpad discipline)",
        )


# ---------------------------------------------------------------------------
# Regression proof: the helpers above must be able to fail, not just pass.
# ---------------------------------------------------------------------------


class TestValidationDetectsRegressions(unittest.TestCase):
    """Per tdd-testing discipline (a test that can never fail is not a
    test): run the real helper functions above against forged input inside
    assertRaises, proving each detects the defect it claims to guard."""

    def test_missing_section_marker_is_detected(self):
        with self.assertRaises(AssertionError):
            _extract_section(
                "no markers here at all",
                "## Does Not Exist",
                "## Also Missing",
                "fake-section",
            )

    def test_missing_end_marker_is_detected(self):
        with self.assertRaises(AssertionError):
            _extract_section(
                "## Start\nsome content, no end heading",
                "## Start",
                "## Missing End",
                "fake-section",
            )

    def test_section_hash_mismatch_is_detected(self):
        with self.assertRaises(AssertionError):
            _assert_section_hash(
                "## Start\nmutated content\n## End",
                "## Start",
                "## End",
                "0" * 64,
                "fake-section",
            )

    def test_section_hash_match_passes(self):
        text = "## Start\nstable content\n## End"
        expected = hashlib.sha256(
            text[text.index("## Start") : text.index("## End")].encode("utf-8")
        ).hexdigest()
        # Does not raise.
        _assert_section_hash(text, "## Start", "## End", expected, "fake-section")

    def test_forbidden_framing_phrase_detection_is_meaningful(self):
        forged = "this reviewer exists to provide a second opinion on the diff"
        self.assertTrue(
            any(phrase in forged for phrase in FORBIDDEN_FRAMING_PHRASES),
            "the forbidden-phrase list must actually match a forged "
            "second-opinion sentence",
        )

    def test_missing_input_field_is_detected_by_membership_check(self):
        section_without_model = "\n".join(
            f"- `{f}`" for f in INPUT_FIELD_NAMES if f != "model"
        )
        self.assertNotIn(
            "`model`",
            section_without_model,
            "sanity check: the forged section genuinely omits `model`",
        )


# ---------------------------------------------------------------------------
# task0007 (rework round 1): the Claude reviewer's trigger framing widens to
# cover both the fan-out-time and the chain-exhaustion-time route.
#
# Covers task0007 AC-3 (feature-docs/llm-led-review/tasks/task0007.md):
# review-protocol.md and agents/reviewer.md state the Claude reviewer's
# trigger as "no chain entry is available at the moment of the decision --
# at fan-out, or after the chain walk has exhausted every entry", and keep
# the constraint that a Claude reviewer and a harness reviewer are never
# dispatched simultaneously for the same perspective. Both halves are
# asserted in both files below.
# ---------------------------------------------------------------------------

MOMENT_OF_DECISION_PHRASES = [
    "no chain entry is available at the moment of the decision",
    "at fan-out",
    "chain walk has exhausted every entry",
]


class TestProtocolTriggerFramingCoversBothRoutes(unittest.TestCase):
    """AC-3 (review-protocol.md): the fallback trigger is framed as 'no
    chain entry available at the moment of the decision', covering both the
    R2 fan-out route and the R2b chain-exhaustion route, and the
    mutual-exclusivity constraint (never dispatched together / never a
    second opinion alongside a completed harness run) survives."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PROTOCOL_PATH)
        cls.normalized = _normalize_whitespace(cls.text)

    def test_states_trigger_as_moment_of_decision(self):
        for phrase in MOMENT_OF_DECISION_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_still_states_never_dispatched_together(self):
        self.assertIn("never dispatched together", self.normalized.lower())

    def test_still_states_no_second_opinion_alongside_completed_run(self):
        self.assertIn(
            "never runs as a second, parallel opinion", self.normalized
        )

    def test_old_no_available_harness_entry_phrase_still_present(self):
        # task0004's AC-1 pinned this phrase; task0007 widens the framing
        # but must not delete it.
        self.assertIn("no available harness entry", self.normalized.lower())


class TestReviewerAgentTriggerFramingCoversBothRoutes(unittest.TestCase):
    """AC-3 (agents/reviewer.md): same trigger framing, same
    mutual-exclusivity constraint, stated in the agent's own body -- while
    the frontmatter and the protocol-following steps (task0004's frozen
    hash boundary) stay untouched."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEWER_AGENT_PATH)
        cls.normalized = _normalize_whitespace(cls.text)

    def test_states_trigger_as_moment_of_decision(self):
        for phrase in MOMENT_OF_DECISION_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.normalized)

    def test_still_states_never_run_alongside_a_harness_reviewer(self):
        self.assertIn(
            "you never run alongside a harness reviewer", self.normalized
        )

    def test_still_states_no_second_opinion_alongside_completed_run(self):
        self.assertIn(
            "never as a second opinion alongside one that already "
            "completed",
            self.normalized,
        )

    def test_frontmatter_fields_unchanged_by_this_task(self):
        for line in REVIEWER_FROZEN_FRONTMATTER_LINES:
            with self.subTest(line=line):
                self.assertIn(line, self.text)

    def test_protocol_following_steps_still_intact(self):
        frontmatter_end = self.text.index("---", 3)
        body = self.text[frontmatter_end:]
        _assert_section_hash(
            body,
            REVIEWER_STEPS_START,
            None,
            REVIEWER_STEPS_SHA256,
            "task0007 (Steps 0-3 unchanged)",
        )


if __name__ == "__main__":
    unittest.main()
