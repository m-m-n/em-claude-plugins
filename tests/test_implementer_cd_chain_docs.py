"""Doc-contract tests for task0002 (implementer-cd-verbatim-conflict): the
chained `cd` form in `em-workflow/agents/implementer.md` and
`em-workflow/skills/worktree-task-workflow/SKILL.md`.

The implementer runs in a subagent whose Bash cwd does not persist between
calls. A stand-alone `cd` therefore never reaches the next call. Both documents
have to tell the implementer to run the tests, builds, formats and
`merge_script` as `cd "{worktree_path}" && <command>` in a single Bash call,
to say that the cwd does not persist between Bash calls, and to keep the
approved string itself unmodified (no environment assignment in front of it).
The earlier instructions (a separate `cd` call, a ban on joining `cd` with
`&&`, "the cwd may have reset") must be gone.

Scope: assertions touch only these two documents. Each assertion is scoped to
one section: the text between the section heading and the next heading of the
same or a higher level. Text is located by section headings and stable
phrases, never by line numbers, and is whitespace-normalized so that line
wrapping does not matter.

Covers this task's Acceptance Criteria
(feature-docs/implementer-cd-verbatim-conflict/tasks/task0002.md):

- AC-1 (FR4): implementer.md Step 3 states that the cwd does not persist
  between Bash calls, tells the implementer to run the tests, builds, formats
  and `merge_script` as `cd "{worktree_path}" && <command>` in a single Bash
  call, keeps `git -C "{worktree_path}"` for git, and says no environment
  assignment goes in front of the command string.
- AC-2 (FR4): implementer.md Step 6 shows the merge_script call as one Bash
  call, `cd "{worktree_path}" && "{merge_script}" "{parent_branch}"
  "{task_id}"`, and keeps the exit-code branches.
  `tests/test_implementer_tests_yaml_record_contract.py` pins the rest of
  Step 6 and passes with the suite.
- AC-3 (FR4, FR5): neither document keeps a sentence that asks for a separate
  `cd` call, a sentence that forbids joining `cd` with `&&`, or a sentence
  that says the cwd may reset. The three negative checks are exercised in both
  directions: the earlier wording is flagged and the real documents yield no
  hit.
- AC-4 (FR5): SKILL.md "merge-task.sh contract" shows the merge_script call as
  one Bash call that starts with `cd "{worktree_path}" &&`, and says the cwd
  does not persist between Bash calls.
- AC-5 (FR5, NFR6): SKILL.md "Command execution gate" keeps the existing
  verbatim sentence with `(byte-for-byte)` and "A mutated string no longer
  matches its approval.", says the only allowed prefix is
  `cd "{worktree_path}" &&` in the same Bash call, says no environment
  assignment is prefixed, and carries `(byte-for-byte)` exactly once with no
  other byte-equality wording.
- AC-6 (FR5): the fixed sentence in
  `tests/test_worktree_skill_instruction_source.py` follows the rewritten
  gate sentence; that module passes with the suite.
- AC-7 (NFR4, NFR8): this module imports only the standard library;
  `python3 -m unittest discover -s tests` passing is the suite run itself.

Follows the established convention: standard library only, repository root
computed from this module's own path, whitespace-normalized matching.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENTER_PATH = REPO_ROOT / "em-workflow" / "agents" / "implementer.md"
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "worktree-task-workflow" / "SKILL.md"

STEP_3_NAME = "Step 3: Verify the worktree"
STEP_6_NAME = "Step 6: Merge"
CONTRACT_NAME = "merge-task.sh contract"
GATE_NAME = "Command execution gate"

CD_PREFIX = 'cd "{worktree_path}" &&'
MERGE_CALL = 'cd "{worktree_path}" && "{merge_script}" "{parent_branch}" "{task_id}"'
GIT_C = 'git -C "{worktree_path}"'
NO_PERSIST = "does not persist between Bash calls"

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BULLET_START = re.compile(r"^\s*(?:[-*]|\d+\.)\s")
_PROHIBITION = re.compile(r"\b(?:never|not|don't)\b", re.IGNORECASE)


def _normalize_ws(text):
    """Collapse whitespace runs (including line-wrap newlines) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def section_text(text, name, source="document"):
    """The section whose heading text is `name` (optionally followed by more
    words): from the line after its heading up to (not including) the next
    heading of the same or a higher level, or end of file. Headings inside
    fenced code blocks are ignored. Raises AssertionError when the heading is
    absent, so a renamed heading fails loudly instead of letting a negative
    check pass over an empty string."""
    lines = text.splitlines()
    in_fence = False
    start = None
    level = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING.match(line)
        if not match:
            continue
        depth = len(match.group(1))
        heading = match.group(2)
        if start is None:
            if heading == name or heading.startswith(name + " "):
                start = i + 1
                level = depth
            continue
        if depth <= level:
            return "\n".join(lines[start:i])
    if start is None:
        raise AssertionError(f"heading not found in {source}: {name}")
    return "\n".join(lines[start:])


def fenced_blocks(text):
    """The bodies of the fenced code blocks of `text`, each stripped."""
    out = []
    current = None
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if current is None:
                current = []
            else:
                out.append("\n".join(current).strip())
                current = None
            continue
        if current is not None:
            current.append(line)
    return out


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
        current.append(line)
    flush()
    return out


def sentences(text):
    """Sentences of every block of `text`, whitespace-normalized."""
    out = []
    for block in blocks(text):
        out.extend(s for s in re.split(r"(?<=\.)\s+", block) if s)
    return out


def sentences_with(text, *terms):
    """The sentences of `text` that contain every term (case-sensitive)."""
    return [s for s in sentences(text) if all(t in s for t in terms)]


# --- AC-3 negative checks ---------------------------------------------------


def find_separate_cd_sentences(text):
    """Sentences that ask for a separate `cd` call: `separate` and `cd` in the
    same sentence."""
    return [
        s
        for s in sentences(text)
        if re.search(r"\bseparate\b", s) and re.search(r"\bcd\b", s)
    ]


def find_chain_prohibition_sentences(text):
    """Sentences that forbid joining `cd` with `&&`: `chain` and `&&` in the
    same sentence together with a prohibition word."""
    return [
        s
        for s in sentences(text)
        if "chain" in s and "&&" in s and _PROHIBITION.search(s)
    ]


def find_cwd_may_reset_sentences(text):
    """Sentences that say the cwd may reset."""
    return [s for s in sentences(text) if "may reset" in s or "may have reset" in s]


# --- documents --------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def implementer_text():
    return _read(IMPLEMENTER_PATH)


def skill_text():
    return _read(SKILL_PATH)


def step3_section():
    return section_text(implementer_text(), STEP_3_NAME, "implementer.md")


def step6_section():
    return section_text(implementer_text(), STEP_6_NAME, "implementer.md")


def contract_section():
    return section_text(skill_text(), CONTRACT_NAME, "SKILL.md")


def gate_section():
    return section_text(skill_text(), GATE_NAME, "SKILL.md")


# The earlier wording of each document, kept as forged text so that the
# negative checks are shown to detect it.
OLD_IMPLEMENTER_STEP_3 = (
    "Do NOT rely on a `cd` persisting between Bash calls — your cwd may reset on "
    "every call, and a bare `git commit` / merge run from the main tree would "
    "mutate `base_branch`. Target the worktree explicitly in EVERY command: use "
    '`git -C "{worktree_path}" ...` for git, and for everything else (tests, '
    'builds, `merge_script`) run a separate `cd "{worktree_path}"` call '
    "immediately before the command. Never chain the `cd` with `&&`."
)
OLD_IMPLEMENTER_STEP_6 = (
    'Run a separate `cd "{worktree_path}"` call, then '
    '`"{merge_script}" "{parent_branch}" "{task_id}"` (the `cd` immediately '
    "before, never chained with `&&` — never assume an earlier cwd carried over) "
    "and branch on its exit code exactly as `worktree-task-workflow` specifies:"
)
OLD_SKILL_CONTRACT = (
    'Invocation (clean tree; run a separate `cd "{worktree_path}"` call '
    "immediately before, and never chain it with `&&` — the cwd may have reset "
    "since an earlier call, and running this from the main tree would merge the "
    "wrong HEAD):"
)
OLD_SKILL_GATE = (
    "Run each `project_commands` string **verbatim** (byte-for-byte). Never "
    "prefix `cd …` or environment assignments — change directory with a "
    'separate `cd "{worktree_path}"` call immediately before each command (the '
    "cwd may have reset since an earlier call). A mutated string no longer "
    "matches its approval."
)

NEW_WORDING = (
    "The cwd does not persist between Bash calls. Run the tests, builds, formats "
    'and `merge_script` as `cd "{worktree_path}" && <command>` in a single Bash '
    "call. Never prefix environment assignments."
)


class TestSectionScoping(unittest.TestCase):
    """The sections are located and scoped by heading."""

    def test_section_text_ends_at_next_heading_of_same_or_higher_level(self):
        text = (
            "# Top\n\n"
            "## A\n\nbody a\n\n### A sub\n\nsub body\n\n"
            "## B\n\nbody b\n\n"
            "# Top 2\n\nbody top 2\n"
        )
        a = section_text(text, "A")
        self.assertIn("body a", a)
        self.assertIn("sub body", a)
        self.assertNotIn("body b", a)
        self.assertEqual(_normalize_ws(section_text(text, "B")), "body b")

    def test_section_text_ignores_headings_inside_fenced_code(self):
        text = "## A\n\nbefore\n\n```\n## not a heading\n```\n\nafter\n\n## B\n\nb\n"
        a = section_text(text, "A")
        self.assertIn("before", a)
        self.assertIn("after", a)

    def test_section_text_raises_for_missing_heading(self):
        with self.assertRaises(AssertionError):
            section_text("## A\n\nx\n", "Missing")

    def test_every_section_is_found_and_nonempty(self):
        for name, getter in (
            (STEP_3_NAME, step3_section),
            (STEP_6_NAME, step6_section),
            (CONTRACT_NAME, contract_section),
            (GATE_NAME, gate_section),
        ):
            with self.subTest(section=name):
                self.assertTrue(getter().strip())

    def test_neighbouring_sections_are_not_swallowed(self):
        self.assertNotIn("Step 4", step3_section())
        self.assertNotIn("Step 7", step6_section())
        self.assertNotIn("Conflict protocol", contract_section())
        self.assertNotIn("Untrusted input", gate_section())


class TestAC1ImplementerStep3(unittest.TestCase):
    """AC-1 (FR4): implementer.md Step 3."""

    def test_ac1_states_that_the_cwd_does_not_persist_between_bash_calls(self):
        hits = sentences_with(step3_section(), "cwd", NO_PERSIST)
        self.assertEqual(len(hits), 1, sentences(step3_section()))

    def test_ac1_runs_tests_builds_formats_and_merge_script_as_one_chained_call(self):
        hits = sentences_with(
            step3_section(),
            'cd "{worktree_path}" && <command>',
            "single Bash call",
            "tests",
            "builds",
            "formats",
            "`merge_script`",
        )
        self.assertEqual(len(hits), 1, sentences(step3_section()))

    def test_ac1_git_operations_keep_git_dash_c(self):
        hits = sentences_with(step3_section(), GIT_C, "for git")
        self.assertEqual(len(hits), 1, sentences(step3_section()))

    def test_ac1_command_string_gets_no_environment_assignment_in_front(self):
        hits = sentences_with(
            step3_section(), "`<command>`", "approved string", "environment assignment"
        )
        self.assertEqual(len(hits), 1, sentences(step3_section()))

    def test_ac1_read_and_write_boundary_rule_is_unchanged(self):
        self.assertIn(
            "You MUST NOT read from or write to any path outside `worktree_path` "
            "except: reading `task_plan_path` / `implementation_md_path` / "
            "`lessons_path`, and executing `merge_script`.",
            _normalize_ws(step3_section()),
        )

    def test_ac1_main_tree_reason_is_kept(self):
        hits = sentences_with(step3_section(), "main tree", "`base_branch`")
        self.assertEqual(len(hits), 1, sentences(step3_section()))


class TestAC2ImplementerStep6(unittest.TestCase):
    """AC-2 (FR4): implementer.md Step 6."""

    def test_ac2_shows_the_merge_script_call_as_one_bash_call(self):
        hits = sentences_with(step6_section(), MERGE_CALL, "single Bash call")
        self.assertEqual(len(hits), 1, sentences(step6_section()))

    def test_ac2_exit_code_branches_are_kept(self):
        section = _normalize_ws(step6_section())
        for expected in (
            "`0` → merged. Done.",
            "`1` → conflict. Execute the parent-side-adoption protocol from the skill",
            "after **3** failed conflict cycles, stop and report `failed`",
            "`2` → error. Diagnose",
            "exactly as `worktree-task-workflow` specifies:",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, section)


class TestAC3NoOldWording(unittest.TestCase):
    """AC-3 (FR4, FR5): the earlier instructions are gone from both documents,
    and each negative check is shown to detect them."""

    def test_ac3_no_separate_cd_call_sentence_remains(self):
        self.assertEqual(find_separate_cd_sentences(implementer_text()), [])
        self.assertEqual(find_separate_cd_sentences(skill_text()), [])

    def test_ac3_no_ban_on_joining_cd_with_and_and_remains(self):
        self.assertEqual(find_chain_prohibition_sentences(implementer_text()), [])
        self.assertEqual(find_chain_prohibition_sentences(skill_text()), [])

    def test_ac3_no_cwd_may_reset_sentence_remains(self):
        self.assertEqual(find_cwd_may_reset_sentences(implementer_text()), [])
        self.assertEqual(find_cwd_may_reset_sentences(skill_text()), [])

    def test_ac3_separate_cd_check_flags_the_earlier_wording(self):
        for forged in (
            OLD_IMPLEMENTER_STEP_3,
            OLD_IMPLEMENTER_STEP_6,
            OLD_SKILL_CONTRACT,
            OLD_SKILL_GATE,
        ):
            with self.subTest(forged=forged[:40]):
                self.assertNotEqual(find_separate_cd_sentences(forged), [])

    def test_ac3_chain_prohibition_check_flags_the_earlier_wording(self):
        for forged in (OLD_IMPLEMENTER_STEP_3, OLD_IMPLEMENTER_STEP_6, OLD_SKILL_CONTRACT):
            with self.subTest(forged=forged[:40]):
                self.assertNotEqual(find_chain_prohibition_sentences(forged), [])

    def test_ac3_cwd_may_reset_check_flags_the_earlier_wording(self):
        for forged in (OLD_IMPLEMENTER_STEP_3, OLD_SKILL_CONTRACT, OLD_SKILL_GATE):
            with self.subTest(forged=forged[:40]):
                self.assertNotEqual(find_cwd_may_reset_sentences(forged), [])

    def test_ac3_checks_accept_the_new_wording(self):
        self.assertEqual(find_separate_cd_sentences(NEW_WORDING), [])
        self.assertEqual(find_chain_prohibition_sentences(NEW_WORDING), [])
        self.assertEqual(find_cwd_may_reset_sentences(NEW_WORDING), [])


class TestAC4SkillMergeContract(unittest.TestCase):
    """AC-4 (FR5): SKILL.md merge-task.sh contract."""

    def test_ac4_invocation_is_one_bash_call_that_starts_with_the_cd_prefix(self):
        hits = sentences_with(
            contract_section(), CD_PREFIX, "single Bash call", "clean tree"
        )
        self.assertEqual(len(hits), 1, sentences(contract_section()))

    def test_ac4_code_block_shows_the_chained_call(self):
        self.assertIn(MERGE_CALL, fenced_blocks(contract_section()))

    def test_ac4_states_that_the_cwd_does_not_persist_between_bash_calls(self):
        hits = sentences_with(contract_section(), "cwd", NO_PERSIST)
        self.assertEqual(len(hits), 1, sentences(contract_section()))

    def test_ac4_reason_names_the_wrong_head_of_the_main_tree(self):
        hits = sentences_with(contract_section(), "main tree", "wrong HEAD")
        self.assertEqual(len(hits), 1, sentences(contract_section()))

    def test_ac4_exit_codes_and_flock_description_are_unchanged(self):
        section = _normalize_ws(contract_section())
        for expected in (
            "**0 — merged.** Your task is complete.",
            "**1 — conflict.** Conflicted files are listed on stderr.",
            "Max **3** conflict cycles; then report `failed`.",
            "**2 — error.** Read the `ERROR:` message.",
            "The script serializes concurrent mergers with flock — a wait is normal, never kill it.",
            "It never touches your working tree; it only advances the parent ref.",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, section)


class TestAC5SkillCommandExecutionGate(unittest.TestCase):
    """AC-5 (FR5, NFR6): SKILL.md Command execution gate."""

    def test_ac5_existing_verbatim_and_mutation_sentences_remain(self):
        section = _normalize_ws(gate_section())
        for expected in (
            "Run each `project_commands` string **verbatim** (byte-for-byte).",
            "A mutated string no longer matches its approval.",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, section)

    def test_ac5_only_prefix_allowed_is_the_cd_prefix_in_the_same_bash_call(self):
        hits = sentences_with(
            gate_section(), "The only prefix allowed is", CD_PREFIX, "same Bash call"
        )
        self.assertEqual(len(hits), 1, sentences(gate_section()))

    def test_ac5_states_that_the_cwd_does_not_persist_between_bash_calls(self):
        hits = sentences_with(gate_section(), "cwd", NO_PERSIST)
        self.assertEqual(len(hits), 1, sentences(gate_section()))

    def test_ac5_environment_assignments_are_not_prefixed(self):
        hits = sentences_with(
            gate_section(), "Never prefix", "environment assignments"
        )
        self.assertEqual(len(hits), 1, sentences(gate_section()))

    def test_ac5_earlier_never_prefix_cd_sentence_is_gone(self):
        self.assertNotIn("Never prefix `cd …`", _normalize_ws(gate_section()))

    def test_ac5_deny_rule_and_hard_refuse_are_unchanged(self):
        section = _normalize_ws(gate_section())
        for expected in (
            "If the hook denies a command: do NOT retry, rephrase, or restructure",
            "Run nothing, set `tests: \"fail\"`, and explain in `notes`",
            "Hard-refuse network exfiltration, `sudo`, `rm -rf` outside the worktree,",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, section)

    def test_ac5_byte_for_byte_appears_exactly_once_and_no_other_byte_claim(self):
        section = _normalize_ws(gate_section())
        self.assertEqual(section.count("(byte-for-byte)"), 1)
        self.assertNotIn("byte", section.replace("(byte-for-byte)", ""))
        for phrase in ("identical to", "equal to the line"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, section)


class TestAC7Mechanics(unittest.TestCase):
    """AC-7 (NFR4, NFR8)."""

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
