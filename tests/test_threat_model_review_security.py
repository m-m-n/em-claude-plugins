"""Tests for task0006 (threat-model-stride): the review-security skill's
missing-mitigation detection rules.

Covers task0006 Acceptance Criteria
(feature-docs/threat-model-stride/tasks/task0006.md):

- AC-1: `em-workflow/skills/review-security/SKILL.md`'s "What to flag
  (security only)" section has a bullet for an unimplemented designed
  mitigation that applies only when `threat_model_path` is supplied and the
  THREAT-MODEL.md verdict is `threats-identified`.
- AC-2: the same bullet states the finding site -- `file` is a Boundary
  files entry of the TB-n holding the TM-n, `line` is the specific line or
  null, and the finding is never re-pointed to an unrelated changed file.
- AC-3: the same bullet states that the title names the TM-n and the
  description names the TM-n, the TB-n, the project-relative
  THREAT-MODEL.md path and the missing mitigation.
- AC-4: the "What NOT to flag" section states that an absent
  THREAT-MODEL.md, a short verdict and an implemented TM-n are not flagged,
  that THREAT-MODEL.md never suppresses a regular finding, and that
  instructions inside it are data.
- AC-5: the skill's pinned headings and sentences are unchanged (verified
  here against the specific surviving sentences/headings, not a whole-file
  hash, so this task's own addition does not fail its own assertion); the
  category sentence still requires `"category": "security"` for every
  finding. Whether the pre-existing
  `tests/test_sca_axis_skill_and_version.py` module itself still passes is
  verified by running the full suite (recorded in the implementer report),
  not re-asserted inside this module.
- AC-7: this module imports the standard library only and holds a
  negative-proof test per matcher, including a forged bullet that would let
  the finding move to any changed file.

Per the plan's Test Notes, checks are unit-level: the "What to flag
(security only)" section is extracted up to "What NOT to flag", and "What
NOT to flag" is extracted up to the "## category" heading; whitespace
(including markdown line-wrapping) is normalized to single spaces before
phrase matching.

Per tdd-testing's "search existing tests before declaring none exist": the
test directory was searched by both path (`em-workflow/skills/review-
security/SKILL.md`) and filename (`SKILL.md`, `review-security`) before
writing this module. Two existing modules touch this file --
`tests/test_sca_axis_skill_and_version.py` (pins the pre-existing
"What NOT to flag" CVE-delegation sentences and headings; unrelated to
missing-mitigation detection) and `tests/test_reviewers_primary_chains.py`
(reviewer chain resolution, not skill body content) -- neither exercises
the missing-mitigation bullet this task adds, so no existing test covers
AC-1 through AC-4.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SECURITY_SKILL_PATH = (
    REPO_ROOT / "em-workflow" / "skills" / "review-security" / "SKILL.md"
)

WHAT_TO_FLAG_HEADING = "## What to flag (security only)"
WHAT_NOT_TO_FLAG_HEADING = "## What NOT to flag"
CATEGORY_HEADING = "## category"
TITLE_LINE = "# Review Perspective: Security"

# Pinned verbatim from the pre-existing skill text (task0006.md Design:
# "Every pinned heading and sentence stays byte-identical"). Must survive
# this task's edit unchanged.
EXISTING_HEADINGS = (
    TITLE_LINE,
    WHAT_TO_FLAG_HEADING,
    WHAT_NOT_TO_FLAG_HEADING,
    CATEGORY_HEADING,
)
EXISTING_WHAT_TO_FLAG_BULLET_MARKERS = (
    "Injection",
    "Auth / authz bypass",
    "Sensitive data exposure",
    "Cryptographic weakness",
    "Input validation",
    "Misconfig & dependency risk",
    "Prompt-injection",
)
EXISTING_STYLE_HARDENING_SENTENCE = (
    "Style hardening unrelated to a concrete attacker-controlled path."
)
EXISTING_SPECULATION_SENTENCE = (
    '"could be exploited if X and Y and Z" without a realistic threat model.'
)
EXISTING_AXIS2_MARKER = "axis 2"
EXISTING_CATEGORY_LINE = 'Every finding MUST have `"category": "security"`.'


def _section_text(full_text, heading, next_heading):
    """Body text strictly between two headings (each matched as a whole
    line) -- scopes an assertion to one section instead of the whole file."""
    lines = full_text.splitlines()
    try:
        start = lines.index(heading) + 1
    except ValueError:
        raise AssertionError(f"heading {heading!r} not found")
    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx] == next_heading:
            end = idx
            break
    return "\n".join(lines[start:end])


def _normalize(text):
    """Collapse all whitespace (including markdown line-wraps inside a
    bullet) to single spaces, so phrase matching is immune to how a
    sentence happens to be wrapped across lines (plan Test Notes)."""
    return re.sub(r"\s+", " ", text).strip()


def _assert_missing_mitigation_trigger_scoped(test, section):
    """AC-1: the bullet applies only when `threat_model_path` is supplied
    and the verdict is `threats-identified`."""
    normalized = _normalize(section)
    test.assertIn("threat_model_path", normalized)
    test.assertIn("threats-identified", normalized)
    test.assertIn("TM-n", normalized)


def _assert_finding_site_rules(test, section):
    """AC-2: `file` is a Boundary files entry of the TB-n holding the TM-n;
    `line` is the specific line or null; never re-pointed to an unrelated
    changed file."""
    normalized = _normalize(section)
    test.assertIn("Boundary files", normalized)
    test.assertIn("TB-n", normalized)
    test.assertIn("identifiable", normalized)
    test.assertIn("null", normalized)
    lowered = normalized.lower()
    test.assertIn("re-point", lowered)
    test.assertIn("changed_files", normalized)


def _assert_title_description_rules(test, section):
    """AC-3: title names the TM-n; description names the TM-n, the TB-n,
    the project-relative THREAT-MODEL.md path and the missing mitigation."""
    normalized = _normalize(section)
    test.assertIn("title", normalized)
    test.assertIn("description", normalized)
    test.assertIn("THREAT-MODEL.md", normalized)
    test.assertIn("project-relative", normalized)
    test.assertIn("missing mitigation", normalized)


def _assert_severity_rule(test, section):
    """Design: "severity by the realistic impact of the unmitigated
    threat, using the protocol's levels."""
    normalized = _normalize(section)
    lowered = normalized.lower()
    test.assertIn("severity", lowered)
    test.assertIn("realistic impact", lowered)


def _assert_what_not_to_flag_rules(test, section):
    """AC-4: absent THREAT-MODEL.md, a short verdict, and an implemented
    TM-n are not flagged; THREAT-MODEL.md never suppresses a regular
    finding; instructions inside it are data."""
    normalized = _normalize(section)
    lowered = normalized.lower()
    test.assertIn("threat-model.md", lowered)
    test.assertIn("no-trust-boundary", normalized)
    test.assertIn("no-applicable-threat", normalized)
    test.assertIn("does implement", lowered)
    test.assertIn("never suppress", lowered)
    test.assertIn("instructions", lowered)
    test.assertIn("data", lowered)


class TestMissingMitigationBulletExists(unittest.TestCase):
    """AC-1 / AC-2 / AC-3: the "What to flag (security only)" section
    carries the new missing-mitigation bullet with the required content."""

    @classmethod
    def setUpClass(cls):
        cls.text = SECURITY_SKILL_PATH.read_text(encoding="utf-8")
        cls.section = _section_text(
            cls.text, WHAT_TO_FLAG_HEADING, WHAT_NOT_TO_FLAG_HEADING
        )

    def test_trigger_is_scoped_to_threat_model_path_and_verdict(self):
        _assert_missing_mitigation_trigger_scoped(self, self.section)

    def test_finding_site_rules_present(self):
        _assert_finding_site_rules(self, self.section)

    def test_title_and_description_rules_present(self):
        _assert_title_description_rules(self, self.section)

    def test_severity_rule_present(self):
        _assert_severity_rule(self, self.section)


class TestWhatNotToFlagCoversMissingMitigationExclusions(unittest.TestCase):
    """AC-4: the "What NOT to flag" section states the exclusions and the
    non-suppression / untrusted-data rules."""

    @classmethod
    def setUpClass(cls):
        cls.text = SECURITY_SKILL_PATH.read_text(encoding="utf-8")
        cls.section = _section_text(
            cls.text, WHAT_NOT_TO_FLAG_HEADING, CATEGORY_HEADING
        )

    def test_exclusion_and_non_suppression_rules_present(self):
        _assert_what_not_to_flag_rules(self, self.section)


class TestExistingSkillContentSurvives(unittest.TestCase):
    """AC-5: every pinned heading and sentence stays byte-identical; the
    category sentence still requires `"category": "security"`."""

    @classmethod
    def setUpClass(cls):
        cls.text = SECURITY_SKILL_PATH.read_text(encoding="utf-8")

    def test_headings_all_present(self):
        lines = self.text.splitlines()
        for heading in EXISTING_HEADINGS:
            with self.subTest(heading=heading):
                self.assertIn(heading, lines)

    def test_existing_what_to_flag_bullets_survive(self):
        section = _section_text(
            self.text, WHAT_TO_FLAG_HEADING, WHAT_NOT_TO_FLAG_HEADING
        )
        for marker in EXISTING_WHAT_TO_FLAG_BULLET_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, section)

    def test_existing_what_not_to_flag_sentences_survive(self):
        self.assertIn(EXISTING_STYLE_HARDENING_SENTENCE, self.text)
        self.assertIn(EXISTING_SPECULATION_SENTENCE, self.text)
        self.assertIn(EXISTING_AXIS2_MARKER, self.text)

    def test_category_requirement_survives(self):
        self.assertIn(EXISTING_CATEGORY_LINE, self.text)


class TestMatchersDetectRegressions(unittest.TestCase):
    """AC-7: a negative proof per matcher, including a forged bullet that
    would let the finding move to any changed file."""

    def test_trigger_matcher_rejects_a_bullet_missing_the_verdict_scope(self):
        forged = "- Flags a TM-n whose mitigation is not implemented."
        with self.assertRaises(AssertionError):
            _assert_missing_mitigation_trigger_scoped(self, forged)

    def test_trigger_matcher_rejects_a_bullet_missing_threat_model_path(self):
        forged = (
            "- Flags a TM-n whose mitigation is not implemented when the "
            "verdict is threats-identified."
        )
        with self.assertRaises(AssertionError):
            _assert_missing_mitigation_trigger_scoped(self, forged)

    def test_finding_site_matcher_rejects_a_bullet_allowing_repointing(self):
        # The exact regression this task must prevent: a bullet that lets
        # the finding move to any changed file to dodge the confidence cap.
        forged = (
            "`file` may be any file in `changed_files` chosen for "
            "convenience; `line` is null."
        )
        with self.assertRaises(AssertionError):
            _assert_finding_site_rules(self, forged)

    def test_finding_site_matcher_rejects_a_bullet_missing_boundary_scoping(self):
        forged = "`file` is the file the reviewer prefers; `line` is null."
        with self.assertRaises(AssertionError):
            _assert_finding_site_rules(self, forged)

    def test_title_description_matcher_rejects_a_bullet_missing_the_path(self):
        forged = "`title` names the TM-n; `description` explains the gap."
        with self.assertRaises(AssertionError):
            _assert_title_description_rules(self, forged)

    def test_severity_matcher_rejects_a_bullet_with_no_severity_rule(self):
        forged = "This bullet says nothing about how severe the finding is."
        with self.assertRaises(AssertionError):
            _assert_severity_rule(self, forged)

    def test_what_not_to_flag_matcher_rejects_a_section_missing_exclusions(self):
        forged = "Style hardening unrelated to a concrete attacker-controlled path."
        with self.assertRaises(AssertionError):
            _assert_what_not_to_flag_rules(self, forged)

    def test_what_not_to_flag_matcher_rejects_a_section_allowing_suppression(self):
        forged = (
            "Absent THREAT-MODEL.md; no-trust-boundary; no-applicable-threat; "
            "a TM-n the change does implement. An accepted-risk note inside "
            "THREAT-MODEL.md means the finding is suppressed and skipped."
        )
        with self.assertRaises(AssertionError):
            _assert_what_not_to_flag_rules(self, forged)


class TestSectionExtractionHelperFailsOnMissingHeading(unittest.TestCase):
    """Negative proof for the section-extraction helper itself."""

    def test_raises_when_heading_absent(self):
        with self.assertRaises(AssertionError):
            _section_text("no headings here\njust text", "## Missing", "## Also Missing")


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-7: this module imports the standard library only."""

    def test_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None and node.level == 0:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
