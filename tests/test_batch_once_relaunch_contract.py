"""Tests for task0001 (batch-once-refire-dedup): the `--once` re-launch
contract wording in `em-workflow/references/batch-mode.md` and
`em-workflow/references/batch-terminal-line.md`, plus regression pins for
the existing Step A rules (batch-mode.md) and the `develop/SKILL.md`
「パス引数なし」 item.

Covers task0001 Acceptance Criteria
(feature-docs/batch-once-refire-dedup/tasks/task0001.md):

- AC-1/AC-4 (C1): the `## Non-packet gates` Step A feature resolution row
  contains anchors A1, A2 and the `references/batch-terminal-line.md`
  pointer.
- AC-3/AC-4 (C2): the `## Field values` `state` bullet contains
  "re-launches the same feature" plus anchors A1 and A2.
- AC-2/AC-4 (C3): the Step A row still contains the four existing rule
  phrases verbatim.
- AC-4 (C4): `develop/SKILL.md`'s 「パス引数なし」 item still contains its
  two existing phrases.
- AC-5: a negative proof per required phrase of C1-C4, an extraction
  failure proof per scope (row / bullet / item missing, or the row
  matching more than once), and a scope proof that anchors placed outside
  the extracted scope do not satisfy C1 or C2.
- Standard-library-only self-check (NFR2).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"
TERMINAL_LINE_PATH = PLUGIN_ROOT / "references" / "batch-terminal-line.md"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

# IMPLEMENTATION.md Shared Components: the re-launch contract anchors.
ANCHOR_A1 = "`feature` value as the path argument"
ANCHOR_A2 = "does not pass the task description again"

TERMINAL_LINE_POINTER = "references/batch-terminal-line.md"
RELAUNCH_PHRASE = "re-launches the same feature"

# IMPLEMENTATION.md Shared Components: existing Step A rule phrases that
# must survive the edit verbatim.
EXISTING_RULE_PHRASES = [
    "Explicit feature-name/path argument wins",
    "No path argument → always a new feature",
    "Existing branches are never enumerated, and a feature is never "
    "guessed from them",
    "resuming requires the explicit feature name",
]

SKILL_NO_PATH_ARG_PHRASES = [
    "常に新規 feature として Step A の "
    "create-spec ルートへ",
    "既存ブランチの列挙・推測"
    "はしない",
]


# ---------------------------------------------------------------------------
# I/O + normalization helpers
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses whitespace runs (including line wraps) to a single space,
    so a phrase check does not depend on where the source happens to wrap
    a line. Never used for structural extraction, which depends on
    newlines as delimiters."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Scope extractors (pure functions over document text)
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def _extract_section(text, heading):
    """Extracts the body of the level-2 `heading` section (without the
    leading `## `), up to the next level-2 heading or end of text. Raises
    AssertionError if the heading is absent."""
    matches = list(_HEADING_RE.finditer(text))
    for i, match in enumerate(matches):
        if match.group(1).strip() == heading:
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return text[start:end]
    raise AssertionError(f"section {heading!r} not found")


def _table_rows(section_text):
    """Yields each data row of a Markdown table in `section_text` as
    (raw_line, cells), skipping the header row and the `---` separator."""
    rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(c and set(c) <= {"-", " ", ":"} for c in cells):
            continue  # separator row, e.g. |---|---|
        rows.append((line, cells))
    return rows


def extract_step_a_row(batch_mode_text):
    """Extractor: the single `## Non-packet gates` table row whose first
    cell begins with "Step A feature resolution". Raises AssertionError
    if the section or row is absent, or if more than one row matches."""
    section = _extract_section(batch_mode_text, "Non-packet gates")
    matches = [
        line
        for line, cells in _table_rows(section)
        if cells and cells[0].startswith("Step A feature resolution")
    ]
    if len(matches) != 1:
        raise AssertionError(
            "expected exactly one 'Step A feature resolution' row, "
            f"found {len(matches)}"
        )
    return matches[0]


_TOP_LEVEL_BULLET_RE = re.compile(r"^- `([a-zA-Z_]+)`", re.MULTILINE)


def extract_state_bullet(terminal_line_text):
    """Extractor: the top-level `## Field values` bullet that opens with
    the backticked `state` key, up to the next top-level bullet (or
    section end). Raises AssertionError if the section or bullet is
    absent."""
    section = _extract_section(terminal_line_text, "Field values")
    bullets = list(_TOP_LEVEL_BULLET_RE.finditer(section))
    for i, match in enumerate(bullets):
        if match.group(1) == "state":
            start = match.start()
            end = bullets[i + 1].start() if i + 1 < len(bullets) else len(section)
            return section[start:end]
    raise AssertionError("`state` bullet not found in `## Field values`")


def extract_no_path_arg_item(skill_text):
    """Extractor: the list item opening with 「パス引数なし」 inside the
    argument-processing part of SKILL.md (before `## Step 0`), including
    its indented continuation line. Raises AssertionError if the `## Step
    0` heading, or the item itself, is absent."""
    step0_match = re.search(r"^## Step 0", skill_text, re.MULTILINE)
    if step0_match is None:
        raise AssertionError("`## Step 0` heading not found")
    scope = skill_text[: step0_match.start()]
    lines = scope.splitlines(keepends=True)

    start_idx = None
    for i, line in enumerate(lines):
        if line.startswith("- パス引数なし"):
            start_idx = i
            break
    if start_idx is None:
        raise AssertionError(
            "「パス引数なし」 item not found "
            "before `## Step 0`"
        )

    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if lines[j].startswith("- "):
            end_idx = j
            break
    return "".join(lines[start_idx:end_idx])


# ---------------------------------------------------------------------------
# Matchers (C1-C4): whitespace-normalized substring checks over a scope
# ---------------------------------------------------------------------------


def check_c1(row_text):
    """C1: the Step A row states the re-launch contract."""
    normalized = _normalize(row_text)
    if ANCHOR_A1 not in normalized:
        raise AssertionError(f"missing anchor A1: {ANCHOR_A1!r}")
    if ANCHOR_A2 not in normalized:
        raise AssertionError(f"missing anchor A2: {ANCHOR_A2!r}")
    if TERMINAL_LINE_POINTER not in normalized:
        raise AssertionError(f"missing pointer: {TERMINAL_LINE_POINTER!r}")


def check_c2(bullet_text):
    """C2: the `state` bullet states the consumer side of the contract."""
    normalized = _normalize(bullet_text)
    if RELAUNCH_PHRASE not in normalized:
        raise AssertionError(f"missing phrase: {RELAUNCH_PHRASE!r}")
    if ANCHOR_A1 not in normalized:
        raise AssertionError(f"missing anchor A1: {ANCHOR_A1!r}")
    if ANCHOR_A2 not in normalized:
        raise AssertionError(f"missing anchor A2: {ANCHOR_A2!r}")


def check_c3(row_text):
    """C3: the Step A row still carries the existing rule phrases."""
    normalized = _normalize(row_text)
    for phrase in EXISTING_RULE_PHRASES:
        if phrase not in normalized:
            raise AssertionError(f"missing existing rule phrase: {phrase!r}")


def check_c4(item_text):
    """C4: the 「パス引数なし」 item still carries its two phrases."""
    normalized = _normalize(item_text)
    for phrase in SKILL_NO_PATH_ARG_PHRASES:
        if phrase not in normalized:
            raise AssertionError(f"missing phrase: {phrase!r}")


# ---------------------------------------------------------------------------
# Synthetic forged documents (negative proofs; no file I/O)
# ---------------------------------------------------------------------------

_FORGED_STEP_A_ROW_TEXT = (
    "| Step A feature resolution (interactive path takes the task "
    "description from the conversation) | Explicit feature-name/path "
    "argument wins. No path argument → always a new feature. "
    "Existing branches are never enumerated, and a feature is never "
    "guessed from them -- resuming requires the explicit feature name. "
    f"A re-launch passes the structured result's {ANCHOR_A1} "
    f"(value owned by {TERMINAL_LINE_POINTER}) and {ANCHOR_A2} |"
)

FORGED_BATCH_MODE_WELL_FORMED = (
    "## Non-packet gates\n\n"
    "| Gate (interactive behavior) | Batch behavior |\n"
    "|---|---|\n"
    "| Step 0 git-setup (gitleaks missing) | UNCHANGED |\n"
    f"{_FORGED_STEP_A_ROW_TEXT}\n"
)

FORGED_BATCH_MODE_MISSING_SECTION = (
    "# Batch Mode Protocol\n\n## Some Other Section\n\nnothing here.\n"
)

FORGED_BATCH_MODE_MISSING_ROW = (
    "## Non-packet gates\n\n"
    "| Gate (interactive behavior) | Batch behavior |\n"
    "|---|---|\n"
    "| Step 0 git-setup (gitleaks missing) | UNCHANGED |\n"
)

FORGED_BATCH_MODE_TWO_MATCHING_ROWS = (
    "## Non-packet gates\n\n"
    "| Gate (interactive behavior) | Batch behavior |\n"
    "|---|---|\n"
    "| Step A feature resolution (first copy) | a |\n"
    "| Step A feature resolution (second copy) | b |\n"
)

FORGED_BATCH_MODE_ANCHORS_IN_WRONG_ROW = (
    "## Non-packet gates\n\n"
    "| Gate (interactive behavior) | Batch behavior |\n"
    "|---|---|\n"
    "| Step A feature resolution (interactive path takes the task "
    "description from the conversation) | Explicit feature-name/path "
    "argument wins. No path argument → always a new feature. "
    "Existing branches are never enumerated, and a feature is never "
    "guessed from them -- resuming requires the explicit feature name |\n"
    f"| Some other gate | {ANCHOR_A1} {ANCHOR_A2} "
    f"{TERMINAL_LINE_POINTER} |\n"
)

FORGED_TERMINAL_LINE_WELL_FORMED = (
    "## Field values\n\n"
    "- `state` — the run's terminal outcome. A consumer that sees "
    "`state` as `phase_done` re-launches the same feature to continue "
    f"it, passing the result's {ANCHOR_A1} and {ANCHOR_A2}.\n"
    "- `step` — unrelated bullet.\n"
)

FORGED_TERMINAL_LINE_MISSING_SECTION = (
    "# doc\n\n## Something Else\n\nno Field values section here.\n"
)

FORGED_TERMINAL_LINE_MISSING_BULLET = (
    "## Field values\n\n"
    "- `step` — description here.\n"
    "- `reason` — description here.\n"
)

FORGED_TERMINAL_LINE_ANCHORS_IN_FEATURE_BULLET = (
    "## Field values\n\n"
    "- `state` — the run's terminal outcome. A consumer that sees "
    "`state` as `phase_done` re-launches the same feature to continue "
    "it.\n"
    f"- `feature` — the feature slug. {ANCHOR_A1} {ANCHOR_A2}\n"
)

FORGED_SKILL_WELL_FORMED = (
    "- パス引数（存在するディ"
    "レクトリ）: 使う\n"
    "- パス引数なし: 常に新規 "
    "feature として Step A の create-spec ルー"
    "トへ\n  （既存ブランチの"
    "列挙・推測はしない）\n\n"
    "## Step 0: git-setup ゲート\n"
)

FORGED_SKILL_MISSING_STEP0 = (
    "- パス引数（存在するディ"
    "レクトリ）: 使う\n"
    "- パス引数なし: 常に新規 "
    "feature として Step A の create-spec ルー"
    "トへ\n"
)

FORGED_SKILL_MISSING_ITEM = (
    "- パス引数（存在するディ"
    "レクトリ）: 使う\n\n"
    "## Step 0: git-setup ゲート\n"
)


# ---------------------------------------------------------------------------
# Extraction proofs (AC-5): missing scope fails extraction, never yields an
# empty scope silently.
# ---------------------------------------------------------------------------


class TestStepARowExtractor(unittest.TestCase):
    def test_finds_the_real_row(self):
        row = extract_step_a_row(_read(BATCH_MODE_PATH))
        self.assertTrue(row.strip().startswith("| Step A feature resolution"))

    def test_finds_the_row_in_a_well_formed_forgery(self):
        row = extract_step_a_row(FORGED_BATCH_MODE_WELL_FORMED)
        self.assertTrue(row.strip().startswith("| Step A feature resolution"))

    def test_fails_when_section_absent(self):
        with self.assertRaises(AssertionError):
            extract_step_a_row(FORGED_BATCH_MODE_MISSING_SECTION)

    def test_fails_when_row_absent(self):
        with self.assertRaises(AssertionError):
            extract_step_a_row(FORGED_BATCH_MODE_MISSING_ROW)

    def test_fails_when_row_matches_more_than_once(self):
        with self.assertRaises(AssertionError):
            extract_step_a_row(FORGED_BATCH_MODE_TWO_MATCHING_ROWS)


class TestStateBulletExtractor(unittest.TestCase):
    def test_finds_the_real_bullet(self):
        bullet = extract_state_bullet(_read(TERMINAL_LINE_PATH))
        self.assertTrue(bullet.startswith("- `state`"))

    def test_finds_the_bullet_in_a_well_formed_forgery(self):
        bullet = extract_state_bullet(FORGED_TERMINAL_LINE_WELL_FORMED)
        self.assertTrue(bullet.startswith("- `state`"))

    def test_excludes_the_next_top_level_bullet(self):
        bullet = extract_state_bullet(FORGED_TERMINAL_LINE_WELL_FORMED)
        self.assertNotIn("unrelated bullet", bullet)

    def test_fails_when_section_absent(self):
        with self.assertRaises(AssertionError):
            extract_state_bullet(FORGED_TERMINAL_LINE_MISSING_SECTION)

    def test_fails_when_bullet_absent(self):
        with self.assertRaises(AssertionError):
            extract_state_bullet(FORGED_TERMINAL_LINE_MISSING_BULLET)


class TestNoPathArgItemExtractor(unittest.TestCase):
    def test_finds_the_real_item(self):
        item = extract_no_path_arg_item(_read(SKILL_PATH))
        self.assertTrue(
            item.startswith("- パス引数なし")
        )

    def test_finds_the_item_in_a_well_formed_forgery(self):
        item = extract_no_path_arg_item(FORGED_SKILL_WELL_FORMED)
        self.assertTrue(
            item.startswith("- パス引数なし")
        )

    def test_fails_when_step0_heading_absent(self):
        with self.assertRaises(AssertionError):
            extract_no_path_arg_item(FORGED_SKILL_MISSING_STEP0)

    def test_fails_when_item_absent(self):
        with self.assertRaises(AssertionError):
            extract_no_path_arg_item(FORGED_SKILL_MISSING_ITEM)


# ---------------------------------------------------------------------------
# C1 - re-launch contract in batch-mode.md
# ---------------------------------------------------------------------------


class TestC1ReLaunchContractInBatchMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.row = extract_step_a_row(_read(BATCH_MODE_PATH))
        # Edge case (Test Notes): the source may wrap a phrase across a
        # line break, so phrase-removal negative proofs operate on the
        # whitespace-normalized scope -- the same normalization `check_c1`
        # applies internally.
        cls.normalized_row = _normalize(cls.row)

    def test_passes_on_the_real_document(self):
        check_c1(self.row)

    def test_fails_when_anchor_a1_removed(self):
        forged = self.normalized_row.replace(ANCHOR_A1, "")
        with self.assertRaises(AssertionError):
            check_c1(forged)

    def test_fails_when_anchor_a2_removed(self):
        forged = self.normalized_row.replace(ANCHOR_A2, "")
        with self.assertRaises(AssertionError):
            check_c1(forged)

    def test_fails_when_pointer_removed(self):
        forged = self.normalized_row.replace(TERMINAL_LINE_POINTER, "")
        with self.assertRaises(AssertionError):
            check_c1(forged)

    def test_fails_when_anchors_appear_only_in_a_different_row(self):
        """Scope proof: anchors placed outside the Step A row do not
        satisfy C1, even though they are present elsewhere in the
        document."""
        row = extract_step_a_row(FORGED_BATCH_MODE_ANCHORS_IN_WRONG_ROW)
        self.assertNotIn(ANCHOR_A1, row)
        with self.assertRaises(AssertionError):
            check_c1(row)


# ---------------------------------------------------------------------------
# C2 - re-launch contract in batch-terminal-line.md
# ---------------------------------------------------------------------------


class TestC2ReLaunchContractInTerminalLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bullet = extract_state_bullet(_read(TERMINAL_LINE_PATH))
        # Edge case (Test Notes): the source may wrap a phrase across a
        # line break, so phrase-removal negative proofs operate on the
        # whitespace-normalized scope -- the same normalization `check_c2`
        # applies internally.
        cls.normalized_bullet = _normalize(cls.bullet)

    def test_passes_on_the_real_document(self):
        check_c2(self.bullet)

    def test_fails_when_relaunch_phrase_removed(self):
        forged = self.normalized_bullet.replace(RELAUNCH_PHRASE, "")
        with self.assertRaises(AssertionError):
            check_c2(forged)

    def test_fails_when_anchor_a1_removed(self):
        forged = self.normalized_bullet.replace(ANCHOR_A1, "")
        with self.assertRaises(AssertionError):
            check_c2(forged)

    def test_fails_when_anchor_a2_removed(self):
        forged = self.normalized_bullet.replace(ANCHOR_A2, "")
        with self.assertRaises(AssertionError):
            check_c2(forged)

    def test_fails_when_anchors_appear_only_in_the_feature_bullet(self):
        """Scope proof: anchors placed in the `feature` bullet do not
        satisfy C2 -- the extractor must not leak the next bullet's
        content into the `state` scope."""
        bullet = extract_state_bullet(
            FORGED_TERMINAL_LINE_ANCHORS_IN_FEATURE_BULLET
        )
        self.assertNotIn(ANCHOR_A1, bullet)
        with self.assertRaises(AssertionError):
            check_c2(bullet)


# ---------------------------------------------------------------------------
# C3 - existing Step A rules survive verbatim
# ---------------------------------------------------------------------------


class TestC3ExistingStepARules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.row = extract_step_a_row(_read(BATCH_MODE_PATH))
        cls.normalized_row = _normalize(cls.row)

    def test_passes_on_the_real_document(self):
        check_c3(self.row)

    def test_fails_when_each_phrase_removed(self):
        for phrase in EXISTING_RULE_PHRASES:
            with self.subTest(phrase=phrase):
                forged = self.normalized_row.replace(phrase, "")
                with self.assertRaises(AssertionError):
                    check_c3(forged)


# ---------------------------------------------------------------------------
# C4 - SKILL.md 「パス引数なし」 item (permanent regression pin)
# ---------------------------------------------------------------------------


class TestC4SkillNoPathArgItem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.item = extract_no_path_arg_item(_read(SKILL_PATH))
        # Edge case (Test Notes): C4 matches Japanese phrases that the
        # source wraps across a line break; match each phrase separately
        # after whitespace normalization.
        cls.normalized_item = _normalize(cls.item)

    def test_passes_on_the_real_document(self):
        check_c4(self.item)

    def test_fails_when_each_phrase_removed(self):
        for phrase in SKILL_NO_PATH_ARG_PHRASES:
            with self.subTest(phrase=phrase):
                forged = self.normalized_item.replace(phrase, "")
                with self.assertRaises(AssertionError):
                    check_c4(forged)


# ---------------------------------------------------------------------------
# Standard-library-only self-check (NFR2)
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """This module imports the Python standard library only."""

    def test_own_imports_are_all_stdlib(self):
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=__file__)

        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported, "expected at least one import in this module")
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


if __name__ == "__main__":
    unittest.main()
