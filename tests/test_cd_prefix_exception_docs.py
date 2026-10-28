"""Document tests for implementer-cd-verbatim-conflict task0003.

The hook allows one `cd` prefix form for the implementer:
`cd "{worktree_path}" && <approved string>` in a single Bash call
(feature-docs/implementer-cd-verbatim-conflict/IMPLEMENTATION.md, C1 and C2).
Three documents describe the hook; this module checks that they state the
implementer exception and that the orchestrator rules are still there.

Covers task0003's Acceptance Criteria
(feature-docs/implementer-cd-verbatim-conflict/tasks/task0003.md):

- AC-1 (FR6): `references/command-execution-protocol.md`, section
  "Verbatim execution rule": the implementer exception and the conditions
  under which the hook allows the form.
- AC-2 (FR6): the same section: the orchestrator rules, the ban on
  environment-assignment prefixes and the ban on splitting, joining and
  quote-wrapping are still there.
- AC-3 (FR6): section "Runtime enforcement": the decision table row for the
  `cd` prefix form sits after the refusal-pattern row and before the
  exact-match row; the refusal row still denies even when approved.
- AC-4 (FR8): `README.md`, the numbered item for the runtime enforcement.
- AC-5 (FR8): `references/workflow-schema.md`, section "Command approval
  store".
- AC-6 (NFR8): this module imports the standard library only.

Method (the task plan's Test Notes): slice by heading, whitespace-normalize,
assert presence or absence of stable phrases. Never a line number. Every
absence assertion is paired with a forged-text case proving its matcher
would fire. Standard library only.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

PROTOCOL_PATH = PLUGIN_ROOT / "references" / "command-execution-protocol.md"
README_PATH = PLUGIN_ROOT / "README.md"
SCHEMA_PATH = PLUGIN_ROOT / "references" / "workflow-schema.md"

CD_FORM = 'cd "{worktree_path}" &&'
PROTOCOL_CITATION = "references/command-execution-protocol.md"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _normalize(text):
    """Collapse every whitespace run (line wraps included) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def _section(text, heading):
    """Body of the section whose heading text starts with `heading`.

    The section runs from the heading line to the next heading of the same
    or a higher level (fenced code is not scanned for headings). Returns
    None when no such heading exists.
    """
    lines = text.splitlines()
    start = None
    level = None
    in_fence = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        if start is None:
            if match.group(2).startswith(heading):
                start = index
                level = len(match.group(1))
            continue
        if len(match.group(1)) <= level:
            return "\n".join(lines[start + 1:index])
    if start is None:
        return None
    return "\n".join(lines[start + 1:])


def _numbered_item(text, marker):
    """The numbered-list item (`1. ...`) whose first line contains `marker`.

    The item runs to the next numbered item or the next blank line.
    """
    lines = text.splitlines()
    item_re = re.compile(r"^\d+\.\s")
    for index, line in enumerate(lines):
        if item_re.match(line) and marker in line:
            collected = [line]
            for follower in lines[index + 1:]:
                if not follower.strip() or item_re.match(follower):
                    break
                collected.append(follower)
            return "\n".join(collected)
    return None


def _table_rows(section_text):
    """Data rows of the first markdown table: list of (condition, decision)."""
    rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append((cells[0], cells[1]))
    # The first row is the header (Condition | Decision).
    return rows[1:]


def _row_index(rows, predicate):
    matches = [i for i, (cond, _) in enumerate(rows) if predicate(cond)]
    return matches


# D3: a document must never claim the whole command holds one `cd`.
ONE_CD_PATTERNS = (
    re.compile(r"(only|exactly|at most)\s+one\s+`?cd`?", re.IGNORECASE),
    re.compile(r"コマンド全体で\s*`?cd`?\s*は\s*1\s*つ"),
)


def _claims_one_cd_in_whole_command(text):
    normalized = _normalize(text)
    return any(pattern.search(normalized) for pattern in ONE_CD_PATTERNS)


class TestVerbatimSection(unittest.TestCase):
    """AC-1 and AC-2: the Verbatim execution rule section."""

    @classmethod
    def setUpClass(cls):
        raw = _section(_read(PROTOCOL_PATH), "Verbatim execution rule")
        cls.raw = raw
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "section 'Verbatim execution rule' not found"
        )

    # --- AC-1: the implementer exception -------------------------------

    def test_ac1_names_the_implementer_exception(self):
        self.assertIn("Implementer", self.text)
        self.assertIn("exception", self.text.lower())

    def test_ac1_rules_are_split_by_role(self):
        self.assertIn("**Orchestrator", self.raw)
        self.assertIn("**Implementer", self.raw)

    def test_ac1_subagent_cwd_does_not_persist_between_bash_calls(self):
        self.assertIn("subagent", self.text)
        self.assertIn("does not persist between Bash calls", self.text)

    def test_ac1_states_the_cd_prefix_form_in_one_bash_call(self):
        self.assertIn(CD_FORM + " <approved string>", self.text)
        self.assertIn("single Bash call", self.text)

    def test_ac1_part_after_the_ampersands_is_the_approved_string(self):
        self.assertRegex(
            self.text,
            r"after `&&`[^.]*approved string[^.]*exactly",
        )

    def test_ac1_states_hook_conditions_quoted_absolute_path(self):
        self.assertIn("double-quoted absolute path", self.text)

    def test_ac1_states_hook_conditions_realpath_under_worktrees_dir(self):
        self.assertIn("realpath", self.text)
        self.assertIn(".claude/worktrees/em-workflow/", self.text)
        self.assertRegex(self.text, r"(deeper|below|under)[^.]*\.claude/worktrees/em-workflow/")

    def test_ac1_states_hook_conditions_rest_equals_approved_string(self):
        self.assertRegex(
            self.text,
            r"everything after the first `&&`[^.]*approved string",
        )

    # --- AC-2: the retained rules ---------------------------------------

    def test_ac2_orchestrator_keeps_the_separate_cd_rule(self):
        self.assertIn("separate `cd` call first", self.text)
        self.assertIn("shell cwd persists between Bash calls", self.text)

    def test_ac2_orchestrator_returns_to_project_root(self):
        self.assertIn(
            "returns to the project root with a separate `cd` call",
            self.text,
        )
        self.assertIn(
            "while the cwd is still inside a worktree",
            self.text,
        )

    def test_ac2_orchestrator_does_not_prefix_cd_and_ampersands(self):
        self.assertIn("prefix `cd {dir} && …`", self.text)

    def test_ac2_environment_assignment_prefix_stays_forbidden(self):
        self.assertIn("environment assignments", self.text)
        self.assertRegex(
            self.text, r"(never|Never|not)[^.]*prefix[^.]*environment assignments"
        )

    def test_ac2_split_join_quote_wrap_stays_forbidden(self):
        self.assertIn(
            'Never split, join, quote-wrap, or "improve" the string',
            self.text,
        )

    def test_ac2_mutated_string_no_longer_matches_its_approval(self):
        self.assertIn("A mutated string no longer matches its approval", self.text)
        self.assertIn("normal permission prompt", self.text)

    def test_section_does_not_claim_one_cd_in_the_whole_command(self):
        self.assertFalse(_claims_one_cd_in_whole_command(self.text))

    def test_one_cd_matcher_fires_on_forged_text(self):
        self.assertTrue(
            _claims_one_cd_in_whole_command("The command holds only one `cd`.")
        )
        self.assertTrue(
            _claims_one_cd_in_whole_command("コマンド全体で cd は 1 つ")
        )
        self.assertFalse(
            _claims_one_cd_in_whole_command("The prefix holds one `cd`.")
        )


class TestRuntimeEnforcementSection(unittest.TestCase):
    """AC-3: the Runtime enforcement decision table."""

    @classmethod
    def setUpClass(cls):
        raw = _section(_read(PROTOCOL_PATH), "Runtime enforcement")
        cls.raw = raw
        cls.text = _normalize(raw) if raw is not None else None
        cls.rows = _table_rows(raw) if raw is not None else []

    def setUp(self):
        self.assertIsNotNone(
            self.text, "section 'Runtime enforcement' not found"
        )

    def _positions(self):
        refusal = _row_index(self.rows, lambda c: "refusal pattern" in c)
        cd_form = _row_index(self.rows, lambda c: CD_FORM in _normalize(c))
        exact = _row_index(
            self.rows, lambda c: "exactly matches an approved string" in c
        )
        return refusal, cd_form, exact

    def test_ac3_has_exactly_one_cd_prefix_row(self):
        _, cd_form, _ = self._positions()
        self.assertEqual(len(cd_form), 1, self.rows)

    def test_ac3_cd_prefix_row_decides_allow(self):
        _, cd_form, _ = self._positions()
        self.assertEqual(len(cd_form), 1, self.rows)
        decision = self.rows[cd_form[0]][1]
        self.assertTrue(decision.startswith("`allow`"), decision)

    def test_ac3_cd_prefix_row_sits_after_refusal_and_before_exact_match(self):
        refusal, cd_form, exact = self._positions()
        self.assertEqual(len(refusal), 1, self.rows)
        self.assertEqual(len(cd_form), 1, self.rows)
        self.assertEqual(len(exact), 1, self.rows)
        self.assertLess(refusal[0], cd_form[0])
        self.assertLess(cd_form[0], exact[0])

    def test_ac3_refusal_row_still_denies_even_when_approved(self):
        refusal, _, _ = self._positions()
        self.assertEqual(len(refusal), 1, self.rows)
        condition, decision = self.rows[refusal[0]]
        self.assertTrue(decision.startswith("`deny`"), decision)
        self.assertIn("even if approved", decision)

    def test_ac3_refusal_row_covers_the_whole_command_including_cd_prefix(self):
        refusal, _, _ = self._positions()
        self.assertEqual(len(refusal), 1, self.rows)
        condition = _normalize(self.rows[refusal[0]][0])
        self.assertIn("whole command", condition)
        self.assertIn("`cd` prefix", condition)

    def test_ac3_unmet_cd_prefix_form_is_judged_as_a_whole_string(self):
        self.assertRegex(
            self.text,
            r"`cd` prefix form that does not meet the conditions[^.]*"
            r"(whole string|as a whole)[^.]*remaining rows",
        )

    def test_ac3_deny_handling_keeps_its_two_bullets(self):
        start = self.raw.index("On a `deny` for an unapproved command")
        tail = self.raw[start:]
        bullets = [
            line for line in tail.splitlines() if line.startswith("- ")
        ]
        self.assertEqual(len(bullets), 2, bullets)
        self.assertTrue(bullets[0].startswith("- **Orchestrator**"))
        self.assertTrue(bullets[1].startswith("- **Implementer / other subagents**"))

    def test_ac3_row_order_matcher_fires_on_forged_table(self):
        forged = (
            "| Condition | Decision |\n"
            "|---|---|\n"
            '| Implementer form `cd "{worktree_path}" && x` | `allow` |\n'
            "| Command matches a refusal pattern | `deny` — even if approved |\n"
            "| Command exactly matches an approved string for this repo | `allow` |\n"
        )
        rows = _table_rows(forged)
        refusal = _row_index(rows, lambda c: "refusal pattern" in c)
        cd_form = _row_index(rows, lambda c: CD_FORM in _normalize(c))
        self.assertEqual(refusal, [1])
        self.assertEqual(cd_form, [0])
        self.assertGreater(refusal[0], cd_form[0])


class TestReadmeRuntimeEnforcement(unittest.TestCase):
    """AC-4: the README item for the runtime enforcement."""

    @classmethod
    def setUpClass(cls):
        raw = _numbered_item(_read(README_PATH), "実行時強制")
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "numbered item containing '実行時強制' not found"
        )

    def test_ac4_states_the_implementer_cd_prefix_exception(self):
        self.assertIn("implementer", self.text)
        self.assertIn(CD_FORM, self.text)
        self.assertIn("1 回の Bash 呼び出し", self.text)

    def test_ac4_defers_the_details_to_the_protocol(self):
        self.assertIn(PROTOCOL_CITATION, self.text)

    def test_ac4_keeps_the_existing_decisions(self):
        self.assertIn("承認済み文字列と完全一致 → allow", self.text)
        self.assertIn("workflow.yaml 記載かつ未承認 → deny", self.text)
        self.assertIn("禁止パターン", self.text)
        self.assertIn("承認済みでも deny", self.text)

    def test_ac4_does_not_claim_one_cd_in_the_whole_command(self):
        self.assertFalse(_claims_one_cd_in_whole_command(self.text))


class TestSchemaCommandApprovalStore(unittest.TestCase):
    """AC-5: workflow-schema.md, section Command approval store."""

    @classmethod
    def setUpClass(cls):
        raw = _section(_read(SCHEMA_PATH), "Command approval store")
        cls.text = _normalize(raw) if raw is not None else None

    def setUp(self):
        self.assertIsNotNone(
            self.text, "section 'Command approval store' not found"
        )

    def test_ac5_states_the_implementer_cd_prefix_exception(self):
        self.assertIn("implementer", self.text)
        self.assertIn(CD_FORM, self.text)
        self.assertIn("single Bash call", self.text)

    def test_ac5_keeps_the_existing_hook_description(self):
        self.assertIn("approved exact string → allow", self.text)
        self.assertIn("declared-but-unapproved → deny", self.text)

    def test_ac5_keeps_the_reference_to_the_protocol(self):
        self.assertIn("Details: `" + PROTOCOL_CITATION + "`", self.text)

    def test_ac5_does_not_claim_one_cd_in_the_whole_command(self):
        self.assertFalse(_claims_one_cd_in_whole_command(self.text))


class TestStandardLibraryOnly(unittest.TestCase):
    """AC-6: this module imports the standard library only."""

    def test_ac6_imports_are_standard_library(self):
        tree = ast.parse(_read(__file__))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertFalse(
            imported - set(sys.stdlib_module_names),
            sorted(imported - set(sys.stdlib_module_names)),
        )


if __name__ == "__main__":
    unittest.main()
