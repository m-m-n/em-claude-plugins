"""Doc-contract tests for task0002 (plan-version-bump-per-commit): the
non-exempt-repository version exception inside the parent-side adoption
protocol of `em-workflow/skills/worktree-task-workflow/SKILL.md`.

In a non-exempt repository, plugin-version-guard validates the plugin
version on every commit. The adoption commit
(`{task_id}: resolve via parent-side adoption`) and the re-implementation
commit (`{task_id}: re-implement on updated parent`) therefore have to carry
a version greater than the relevant earlier values. This module pins that
text in SKILL.md and detects its removal or a permissive restatement.

Scope (IMPLEMENTATION.md "Test scope"): assertions touch only this task's
own document. The cited plan-writing heading is checked by name inside
worktree-task-workflow SKILL.md; plan-writing SKILL.md is never opened.

Covers this task's Acceptance Criteria
(feature-docs/plan-version-bump-per-commit/tasks/task0002.md):

- AC-1 (FR6): adoption commit -- version greater than both the parent-side
  value and the task-side HEAD value from before the adoption.
- AC-2 (FR6): re-implementation commit -- version greater than the HEAD
  value after adoption.
- AC-3 (FR6): the same-named `.claude-plugin/marketplace.json` entry, when it
  carries a version, is set to the same value.
- AC-4 (FR6): an exempt repository performs no additional version step.
- AC-5 (NFR1): the exception cites plan-writing SKILL.md's
  "Plugin Version Handling" section by repository-relative path and heading
  text, and does not restate what that section owns.
- AC-6 (FR7): the negative check. `find_permissive_version_statements`
  returns the sentences of a text that permit keeping the version unchanged
  (or taking the parent-side value as-is) in a non-exempt context. It is
  exercised in both directions: permissive samples are flagged, the
  protocol's own prohibition wording, quoted prohibited examples and
  exempt-repository statements are not, and the real protocol text yields no
  hit.
- AC-7 (NFR2, NFR3, NFR4): no concrete version value and no fenced code
  block in the protocol section, and this module imports only the standard
  library. `python3 -m unittest discover -s tests` passing is the suite
  run itself.

Negative-check rules (kept deliberately small; this is a document
regression guard, not a language parser):

- A sentence is examined only when it mentions a version.
- A sentence that mentions an exempt repository, and does not mention a
  non-exempt one, is exempt-repository context and is never flagged. Write
  exempt-repository statements as their own sentence or bullet.
- "Keep unchanged" expressions: "unchanged", "as-is", "as it is",
  "untouched", "keep / leave / retain ... version", "stays / remains at or
  the same", and "take / adopt / use / keep ... the parent-side value or
  version".
- "No bump needed" expressions: "need not bump", "no need to change",
  "skip the version bump", and similar. These are permissive on their own.
- A "keep unchanged" sentence is flagged unless it carries a prohibition
  ("never", "must not", "do not", "not acceptable", "rejected", ...).

Follows the established convention: standard library only, repository root
computed from this module's own path, whitespace-normalized matching.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "worktree-task-workflow" / "SKILL.md"

PROTOCOL_HEADING = "## Conflict protocol (parent-side adoption)"
ADOPTION_TEMPLATE = "{task_id}: resolve via parent-side adoption"
REIMPLEMENTATION_TEMPLATE = "{task_id}: re-implement on updated parent"

OWNER_PATH = "em-workflow/skills/plan-writing/SKILL.md"
OWNER_HEADING_TEXT = "Plugin Version Handling"
# Literals owned by plan-writing "Plugin Version Handling"; the exception
# cites them and must not restate them.
OWNER_DEFINITION_LITERALS = (
    ".github/workflows/plugin-version-bump.yml",
    "per-component",
    "strictly greater",
)

MARKETPLACE_PATH = ".claude-plugin/marketplace.json"


# ---------------------------------------------------------------------------
# Document access helpers
# ---------------------------------------------------------------------------


def _read_skill():
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse whitespace runs (including line-wrap newlines) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def protocol_section(text):
    """The parent-side adoption protocol: from its heading line up to (not
    including) the next level-2 heading, or end of file."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == PROTOCOL_HEADING:
            start = i
            break
    if start is None:
        raise AssertionError("heading not found in SKILL.md: " + PROTOCOL_HEADING)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


_BULLET_START = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def blocks(text):
    """Split into paragraph / list-item blocks: a blank line or a bullet or
    numbered-list start begins a new block. Each block is whitespace-
    normalized, so wrapped continuation lines join their item."""
    out = []
    current = []

    def flush():
        if current:
            out.append(_normalize_ws(" ".join(current)))
            current.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            continue
        if _BULLET_START.match(line):
            flush()
        current.append(line.strip())
    flush()
    return out


def sentences(text):
    """Blocks further split at sentence terminators."""
    out = []
    for block in blocks(text):
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z`\"(*])", block):
            part = part.strip()
            if part:
                out.append(part)
    return out


def forge(text, old, new):
    """Replace `old` with `new` in `text`, matching whitespace runs in `old`
    against any whitespace (so a phrase wrapped across lines is still found).
    Fails when `old` is absent, so a forged-text test can never pass
    vacuously."""
    pattern = r"\s+".join(re.escape(word) for word in old.split())
    forged, count = re.subn(pattern, lambda _m: new, text)
    if count == 0:
        raise AssertionError("phrase to forge not found in text: " + old)
    return forged


# ---------------------------------------------------------------------------
# Rule predicates (AC-1 .. AC-5); each takes the protocol section text
# ---------------------------------------------------------------------------


def adoption_rule_present(section):
    """AC-1: a block carrying the adoption template states a version greater
    than both the parent-side value and the task-side HEAD value."""
    for block in blocks(section):
        if ADOPTION_TEMPLATE not in block:
            continue
        if (
            re.search(r"\bversion\b", block)
            and "plugin.json" in block
            and "under a plugin" in block
            and re.search(r"\bgreater\b", block)
            and re.search(r"\bboth\b", block)
            and "parent-side value" in block
            and "task-side HEAD value" in block
            and re.search(r"before (?:the )?adoption", block)
        ):
            return True
    return False


def reimplementation_rule_present(section):
    """AC-2: a block carrying the re-implementation template states a version
    greater than the HEAD value after adoption."""
    for block in blocks(section):
        if REIMPLEMENTATION_TEMPLATE not in block:
            continue
        if (
            re.search(r"\bversion\b", block)
            and re.search(r"\bgreater\b", block)
            and re.search(r"HEAD value after (?:the )?adoption", block)
        ):
            return True
    return False


def marketplace_alignment_present(section):
    """AC-3: a block states that the same-named marketplace entry, when it
    carries a version, is set to the same value."""
    for block in blocks(section):
        if (
            MARKETPLACE_PATH in block
            and re.search(r"same-named", block)
            and re.search(r"carries a version", block)
            and re.search(r"same value", block)
        ):
            return True
    return False


def exempt_no_step_present(section):
    """AC-4: a block states that an exempt repository performs no additional
    version step. 'non-exempt' does not count."""
    for block in blocks(section):
        if re.search(r"(?<!non-)\bexempt repository\b", block) and re.search(
            r"no additional version step", block
        ):
            return True
    return False


def citation_present(section):
    """AC-5 (positive half): one block names the owner path and the heading
    text of the owner section, and the exception's scope (non-exempt)."""
    for block in blocks(section):
        if (
            OWNER_PATH in block
            and OWNER_HEADING_TEXT in block
            and "non-exempt" in block
        ):
            return True
    return False


def restated_owner_literals(section):
    """AC-5 (negative half): owner-defined literals that appear in the
    section, i.e. restated instead of cited."""
    return [lit for lit in OWNER_DEFINITION_LITERALS if lit in section]


# ---------------------------------------------------------------------------
# AC-6: negative check
# ---------------------------------------------------------------------------

_VERSION_WORD = re.compile(r"\bversions?\b", re.IGNORECASE)

_KEEP_UNCHANGED = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bunchanged\b",
        r"\bas[- ]is\b",
        r"\bas it is\b",
        r"\buntouched\b",
        r"\b(?:keep|keeps|keeping|leave|leaves|leaving|retain|retains|retaining)"
        r"\s+(?:the\s+|its\s+|that\s+plugin's\s+)?(?:plugin\.json\s+)?versions?\b",
        r"\b(?:stay|stays|staying|remain|remains|remaining)\s+(?:at|the same)\b",
        r"\b(?:take|takes|taking|adopt|adopts|adopting|use|uses|using|accept|accepts"
        r"|accepting|keep|keeps|keeping|reuse|reuses|reusing|copy|copies|copying)\b"
        r"[^.!?]*\bparent(?:-side)?\s+(?:value|version)s?\b",
    )
]

_NO_BUMP = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:need not|needn't|no need to|not required to|not necessary to"
        r"|(?:do|does) not (?:need|have) to|(?:don't|doesn't) (?:need|have) to)"
        r"\s+(?:bump|change|increase|raise|update|set|touch)\b",
        r"\b(?:skip|skips|skipping|omit|omits|omitting|forgo|forgoes|without)"
        r"\s+(?:the\s+|any\s+|a\s+)?(?:version\s+)?(?:bump|change|increase|update)\b",
    )
]

_PROHIBITION = re.compile(
    r"\b(?:never|must not|mustn't|do not|don't|does not|doesn't|may not|cannot|can't"
    r"|not (?:allowed|permitted|acceptable|accepted|sufficient|enough|valid)"
    r"|forbidden|prohibited|rejected|rejects?|insufficient|is not enough)\b",
    re.IGNORECASE,
)

_EXEMPT = re.compile(r"(?<!non-)\bexempt\b", re.IGNORECASE)
_NON_EXEMPT = re.compile(r"\bnon-exempt\b", re.IGNORECASE)


def find_permissive_version_statements(text):
    """Sentences of `text` that permit keeping the version unchanged (or
    taking the parent-side value as-is) outside exempt-repository context."""
    hits = []
    for sentence in sentences(text):
        if not _VERSION_WORD.search(sentence):
            continue
        if _EXEMPT.search(sentence) and not _NON_EXEMPT.search(sentence):
            continue
        if any(p.search(sentence) for p in _NO_BUMP):
            hits.append(sentence)
            continue
        if any(p.search(sentence) for p in _KEEP_UNCHANGED) and not _PROHIBITION.search(
            sentence
        ):
            hits.append(sentence)
    return hits


PERMISSIVE_SAMPLES = (
    "In a non-exempt repository the plugin version may stay unchanged on the adoption commit.",
    "The adoption commit can take the parent-side version as-is.",
    "On the re-implementation commit, keep the version as it is.",
    "A non-exempt repository need not bump the version on the re-implementation commit.",
    "Leave versions untouched when resolving conflicts in a non-exempt repository.",
    "Adopt the parent-side version for plugin.json and commit.",
    "The adoption commit can skip the version bump.",
)

PROHIBITION_SAMPLES = (
    "Never keep the version unchanged and never take the parent-side value as-is.",
    "Keeping the version unchanged is not acceptable on the adoption commit.",
    "Do not leave the plugin version as it is; do not take the parent-side value as-is.",
    'A commit that reuses the parent-side value as-is (for example, "version unchanged") is rejected by the guard.',
    "The version in the commit must not stay unchanged.",
)

EXEMPT_SAMPLES = (
    "In an exempt repository the plugin version stays unchanged and no additional version step is performed.",
    "An exempt repository performs no additional version step, so versions are left untouched.",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProtocolLocation(unittest.TestCase):
    def test_protocol_section_holds_both_commit_templates(self):
        section = protocol_section(_read_skill())
        self.assertIn(ADOPTION_TEMPLATE, section)
        self.assertIn(REIMPLEMENTATION_TEMPLATE, section)


class TestAC1AdoptionCommit(unittest.TestCase):
    """AC-1 (FR6)."""

    def test_adoption_commit_version_greater_than_both_sides(self):
        self.assertTrue(adoption_rule_present(protocol_section(_read_skill())))

    def test_matcher_rejects_forged_text(self):
        section = protocol_section(_read_skill())
        for old, new in (
            ("greater", "equal"),
            ("parent-side value", "parent-side figure"),
            ("task-side HEAD value", "task-side figure"),
        ):
            with self.subTest(replaced=old):
                self.assertNotIn(old, new)
                self.assertFalse(adoption_rule_present(forge(section, old, new)))


class TestAC2ReimplementationCommit(unittest.TestCase):
    """AC-2 (FR6)."""

    def test_reimplementation_commit_version_greater_than_post_adoption_head(self):
        self.assertTrue(reimplementation_rule_present(protocol_section(_read_skill())))

    def test_matcher_rejects_forged_text(self):
        section = protocol_section(_read_skill())
        for old, new in (
            ("greater", "equal"),
            ("HEAD value after", "HEAD value before"),
        ):
            with self.subTest(replaced=old):
                self.assertFalse(
                    reimplementation_rule_present(forge(section, old, new))
                )


class TestAC3MarketplaceAlignment(unittest.TestCase):
    """AC-3 (FR6)."""

    def test_marketplace_entry_set_to_same_value(self):
        self.assertTrue(marketplace_alignment_present(protocol_section(_read_skill())))

    def test_matcher_rejects_forged_text(self):
        section = protocol_section(_read_skill())
        for old, new in (
            (MARKETPLACE_PATH, "other.json"),
            ("same-named", "any"),
            ("carries a version", "exists"),
            ("same value", "different value"),
        ):
            with self.subTest(replaced=old):
                self.assertFalse(
                    marketplace_alignment_present(forge(section, old, new))
                )


class TestAC4ExemptRepository(unittest.TestCase):
    """AC-4 (FR6)."""

    def test_exempt_repository_has_no_additional_version_step(self):
        self.assertTrue(exempt_no_step_present(protocol_section(_read_skill())))

    def test_matcher_rejects_forged_text(self):
        section = protocol_section(_read_skill())
        forged = forge(section, "no additional version step", "an extra version step")
        self.assertFalse(exempt_no_step_present(forged))

    def test_non_exempt_wording_does_not_satisfy_the_matcher(self):
        sample = "A non-exempt repository performs no additional version step."
        self.assertFalse(exempt_no_step_present(sample))


class TestAC5OwnerCitation(unittest.TestCase):
    """AC-5 (NFR1)."""

    def test_exception_cites_owner_path_and_heading_and_scope(self):
        self.assertTrue(citation_present(protocol_section(_read_skill())))

    def test_matcher_rejects_forged_text(self):
        section = protocol_section(_read_skill())
        for old, new in (
            (OWNER_PATH, "em-workflow/skills/other/SKILL.md"),
            (OWNER_HEADING_TEXT, "Version Notes"),
        ):
            with self.subTest(replaced=old):
                self.assertFalse(citation_present(forge(section, old, new)))

    def test_owner_definitions_are_not_restated(self):
        section = protocol_section(_read_skill())
        self.assertTrue(citation_present(section))
        self.assertEqual(restated_owner_literals(section), [])

    def test_restatement_detector_flags_a_restating_sample(self):
        sample = "Exempt means .github/workflows/plugin-version-bump.yml exists."
        self.assertEqual(
            restated_owner_literals(sample),
            [".github/workflows/plugin-version-bump.yml"],
        )


class TestAC6NegativeCheck(unittest.TestCase):
    """AC-6 (FR7): both directions, plus the real protocol text."""

    def test_permissive_samples_are_flagged(self):
        for sample in PERMISSIVE_SAMPLES:
            with self.subTest(sample=sample):
                self.assertEqual(find_permissive_version_statements(sample), [sample])

    def test_prohibition_samples_are_accepted(self):
        for sample in PROHIBITION_SAMPLES:
            with self.subTest(sample=sample):
                self.assertEqual(find_permissive_version_statements(sample), [])

    def test_exempt_repository_samples_are_accepted(self):
        for sample in EXEMPT_SAMPLES:
            with self.subTest(sample=sample):
                self.assertEqual(find_permissive_version_statements(sample), [])

    def test_real_protocol_text_is_accepted(self):
        section = protocol_section(_read_skill())
        self.assertTrue(adoption_rule_present(section))
        self.assertEqual(find_permissive_version_statements(section), [])

    def test_permissive_sentence_added_to_real_protocol_is_flagged(self):
        section = protocol_section(_read_skill())
        for sample in PERMISSIVE_SAMPLES:
            with self.subTest(sample=sample):
                hits = find_permissive_version_statements(section + "\n\n" + sample)
                self.assertEqual(hits, [sample])

    def test_permissive_sentence_wrapped_across_lines_is_flagged(self):
        wrapped = (
            "In a non-exempt repository the adoption commit may keep the\n"
            "version\n"
            "unchanged."
        )
        self.assertEqual(
            find_permissive_version_statements(wrapped),
            ["In a non-exempt repository the adoption commit may keep the version unchanged."],
        )

    def test_general_adopt_parent_side_wording_is_not_a_version_statement(self):
        sample = (
            "For every conflicted file: `git checkout --theirs -- <file>` "
            "(= adopt the PARENT branch's version wholesale; your version of "
            "that file is discarded)."
        )
        self.assertEqual(find_permissive_version_statements(sample), [])


class TestAC7WordingAndMechanics(unittest.TestCase):
    """AC-7 (NFR2, NFR3, NFR4)."""

    def test_protocol_section_has_no_concrete_version_value(self):
        section = protocol_section(_read_skill())
        self.assertEqual(re.findall(r"\bv?\d+\.\d+(?:\.\d+)?\b", section), [])

    def test_version_value_detector_flags_a_concrete_value(self):
        self.assertEqual(
            re.findall(r"\bv?\d+\.\d+(?:\.\d+)?\b", "bump to 0.3.1 or v2.0"),
            ["0.3.1", "v2.0"],
        )

    def test_protocol_section_has_no_fenced_code_block(self):
        self.assertNotIn("```", protocol_section(_read_skill()))

    def test_this_module_imports_only_the_standard_library(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertEqual(sorted(imported - set(sys.stdlib_module_names)), [])


if __name__ == "__main__":
    unittest.main()
