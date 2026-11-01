"""Hook tests for the space/tab-only approval trim of
`em-workflow/hooks/bash_guard.py` (feature approval-unicode-whitespace,
task0001).

The approval trim removes only spaces (U+0020) and tabs (U+0009) from both
ends of a command. A command that still has another whitespace character
(`str.isspace()`) at either end afterwards is never allowed: it is denied as
unapproved when a working-tree workflow.yaml declares it, and gets no decision
otherwise. The same holds for the remainder of the
`cd "<path>" && <approved command>` form.

Every hook case drives the hook as a subprocess with PreToolUse JSON on
standard input and reads the decision from standard output. The expected
decision is one of three:

- `allow`  -- a JSON `permissionDecision: allow` on standard output.
- `deny`   -- a JSON `permissionDecision: deny` on standard output.
- `silent` -- no output at all (no decision; the normal permission flow
  applies).

Isolation: the approval store is a temporary file selected through
`EM_WORKFLOW_APPROVALS`, `CLAUDE_PROJECT_DIR` is removed from the hook's
environment, and every repository is a temporary git repository. The real
approval store and the real repository's workflow.yaml are never read. Only
matchable commands are recorded in the store. Non-ASCII and control
whitespace is written in this source as escape sequences; the workflow.yaml
fixture receives the raw characters.

Covers task0001 Acceptance Criteria
(feature-docs/approval-unicode-whitespace/tasks/task0001.md), hook halves:

- AC-3: no allow for a padded command; deny when declared, no decision
  otherwise; the attack scenario; a command empty after the trim.
- AC-4: a trailing line feed, or a backslash and a line feed, is not allowed,
  standalone or as the cd prefix remainder; padded cd prefix remainders.
- AC-6: spaces and tabs alone still approve; other whitespace characters and
  inner whitespace do not.
- AC-7: the module docstrings, the standard-library-only imports and the
  absence of the substring `status` in the hook.

Standard library only.
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "bash_guard.py"
PREFLIGHT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "merge-preflight.py"

ALLOW = "allow"
DENY = "deny"
SILENT = "silent"

# Marker fragments of the reasons the hook gives (the strings are the hook's,
# compared here by their stable fragments).
CD_PREFIX_MARKER = "cd 前置形"
UNAPPROVED_MARKER = "未承認"
EXACT_MATCH_MARKER = "完全一致"

APPROVED = "/usr/bin/true"
PLAIN = "make test"

NBSP = " "
VT = "\u000b"
FF = "\u000c"

# The primary set, then the representative other whitespace characters.
PRIMARY_CHARS = (("U+00A0", NBSP), ("U+000B", VT), ("U+000C", FF))
OTHER_CHARS = (
    ("U+0085", "\u0085"),
    ("U+2000", " "),
    ("U+3000", "　"),
    ("U+001F", "\u001f"),
)
ALL_CHARS = PRIMARY_CHARS + OTHER_CHARS


def padded_forms(value, char):
    """(label, text) pairs: `char` before, after and on both sides of `value`,
    alone and mixed with spaces and tabs."""
    return (
        ("before", char + value),
        ("after", value + char),
        ("both", char + value + char),
        ("blanks then char before", " \t" + char + value),
        ("char then blanks before", char + " \t" + value),
        ("char then blanks after", value + char + " \t"),
        ("blanks then char after", value + " \t" + char),
        ("blanks and char on both sides", " " + char + "\t" + value + "\t" + char + " "),
    )


def all_padded(value, chars=ALL_CHARS):
    for name, char in chars:
        for position, text in padded_forms(value, char):
            yield f"{name} {position}", text


def _clean_env():
    return {
        key: value
        for key, value in os.environ.items()
        if key != "CLAUDE_PROJECT_DIR" and not key.startswith("GIT_")
    }


def _git(cwd, *args):
    env = _clean_env()
    env.update(
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
    )
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


def _make_repo(path):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    (path / "README").write_text("fixture\n", encoding="utf-8")
    _git(path, "add", "README")
    _git(path, "commit", "-q", "-m", "init")


# Lines of the working-tree workflow.yaml of the "declared" repository. Every
# padded form of the approved path is declared as a build command, as raw
# characters. The extra lines test the key/value separator and the trailing
# class of the extraction pattern.
def declared_lines():
    lines = []
    for _, text in all_padded(APPROVED):
        lines.append(f"build_command: {text}")
    lines += [
        "test_command:" + NBSP + "make lint",
        "e2e_test_command: make e2e" + NBSP,
        "build_command: \t make lint2 \t",
        "build_command: " + NBSP + "/usr/bin/true",
    ]
    return lines


class Fixture:
    """Two repositories (one declares commands, one does not), a worktree
    area directory in each, and one approval store."""

    def __init__(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="bash-guard-uws-")))
        self.plain = self.root / "plain"
        self.declared = self.root / "declared"
        for repo in (self.plain, self.declared):
            _make_repo(repo)
            (repo / ".claude" / "worktrees" / "em-workflow" / "task0001").mkdir(parents=True)
        self.plain_dir = self.plain / ".claude" / "worktrees" / "em-workflow" / "task0001"
        self.declared_dir = self.declared / ".claude" / "worktrees" / "em-workflow" / "task0001"

        wf_dir = self.declared / "feature-docs" / "demo"
        wf_dir.mkdir(parents=True)
        (wf_dir / "workflow.yaml").write_text(
            "\n".join(declared_lines()) + "\n", encoding="utf-8"
        )

        # The attack scenario: an executable file at the work-tree-relative
        # path U+00A0 + "/usr/bin/true".
        for repo in (self.plain, self.declared):
            attack = repo / NBSP / "usr" / "bin"
            attack.mkdir(parents=True)
            target = attack / "true"
            target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            target.chmod(0o755)

        self.store = self.root / "approvals.json"
        for repo in (self.plain, self.declared):
            self.record(repo, (APPROVED, PLAIN))

    def env(self, extra=None):
        env = _clean_env()
        env["EM_WORKFLOW_APPROVALS"] = str(self.store)
        env["GIT_CEILING_DIRECTORIES"] = str(self.root)
        if extra:
            env.update(extra)
        return env

    def record(self, project_dir, commands):
        proc = subprocess.run(
            [sys.executable, str(GUARD_PATH), "--record", "--project-dir", str(project_dir)],
            input="\n".join(commands) + "\n",
            capture_output=True,
            text=True,
            env=self.env(),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"--record failed: {proc.stderr}")

    def run_hook(self, command, cwd):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
        return subprocess.run(
            [sys.executable, str(GUARD_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env(),
            cwd=str(cwd),
        )

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


FIX = None


def setUpModule():
    global FIX
    FIX = Fixture()


def tearDownModule():
    FIX.cleanup()


def decide(proc):
    """Return (decision, hookSpecificOutput dict or None)."""
    if proc.returncode != 0:
        raise AssertionError(f"hook exited {proc.returncode}: {proc.stderr}")
    if proc.stderr != "":
        raise AssertionError(f"hook wrote to stderr: {proc.stderr}")
    if proc.stdout == "":
        return SILENT, None
    output = json.loads(proc.stdout)["hookSpecificOutput"]
    return output["permissionDecision"], output


def cd_form(remainder, directory=None):
    return 'cd "' + str(directory or FIX.plain_dir) + '" && ' + remainder


class HookCase(unittest.TestCase):
    def assert_silent(self, command, cwd):
        decision, output = decide(FIX.run_hook(command, cwd))
        self.assertEqual((decision, output), (SILENT, None), repr(command))

    def assert_unapproved_deny(self, command, cwd):
        decision, output = decide(FIX.run_hook(command, cwd))
        self.assertEqual(decision, DENY, repr(command))
        self.assertIn(UNAPPROVED_MARKER, output["permissionDecisionReason"], repr(command))

    def assert_exact_allow(self, command, cwd):
        decision, output = decide(FIX.run_hook(command, cwd))
        self.assertEqual(decision, ALLOW, repr(command))
        reason = output["permissionDecisionReason"]
        self.assertIn(EXACT_MATCH_MARKER, reason, repr(command))
        self.assertNotIn(CD_PREFIX_MARKER, reason, repr(command))

    def assert_cd_allow(self, command, cwd):
        decision, output = decide(FIX.run_hook(command, cwd))
        self.assertEqual(decision, ALLOW, repr(command))
        self.assertIn(CD_PREFIX_MARKER, output["permissionDecisionReason"], repr(command))


class TestFixtureControls(HookCase):
    """The fixture approves what the other tests pad."""

    def test_the_approved_value_is_allowed_by_exact_match_in_both_repositories(self):
        for cwd in (FIX.plain, FIX.declared):
            with self.subTest(cwd=cwd.name):
                self.assert_exact_allow(APPROVED, cwd)
                self.assert_exact_allow(PLAIN, cwd)

    def test_the_declared_fixture_denies_a_declared_unapproved_value(self):
        # `make lint2` is declared with surrounding blanks and never approved.
        self.assert_unapproved_deny("make lint2", FIX.declared)
        self.assert_silent("make lint2", FIX.plain)


class TestAc3PaddedCommandIsNeverAllowed(HookCase):
    """AC-3 (FR1, FR4, FR8, TM-3, TM-5)."""

    def test_ac3_a_padded_command_that_is_not_declared_gets_no_decision(self):
        for label, text in all_padded(APPROVED, PRIMARY_CHARS):
            with self.subTest(label=label):
                self.assert_silent(text, FIX.plain)

    def test_ac3_a_padded_command_that_is_declared_is_denied_as_unapproved(self):
        for label, text in all_padded(APPROVED, PRIMARY_CHARS):
            with self.subTest(label=label):
                self.assert_unapproved_deny(text, FIX.declared)

    def test_ac3_the_attack_scenario_gets_no_allow(self):
        command = NBSP + APPROVED
        self.assertTrue((FIX.plain / NBSP / "usr" / "bin" / "true").is_file())
        self.assert_silent(command, FIX.plain)
        self.assert_unapproved_deny(command, FIX.declared)

    def test_ac3_a_command_empty_after_the_trim_gets_no_decision(self):
        for command in ("", " ", "\t", " \t ", "\t\t  \t"):
            for cwd in (FIX.plain, FIX.declared):
                with self.subTest(command=command, cwd=cwd.name):
                    self.assert_silent(command, cwd)

    def test_ac3_a_command_made_only_of_a_padding_character_is_not_allowed(self):
        for name, char in ALL_CHARS:
            with self.subTest(char=name):
                self.assert_silent(char, FIX.plain)
                self.assert_silent(" " + char + "\t", FIX.plain)


class TestAc4LineFeedAndCdPrefixRemainder(HookCase):
    """AC-4 (FR4, FR5, TM-3, TM-4)."""

    def test_ac4_a_trailing_line_feed_is_not_allowed_standalone(self):
        for label, text in (
            ("line feed", PLAIN + "\n"),
            ("backslash and line feed", PLAIN + "\\\n"),
            ("blank and line feed", PLAIN + " \n"),
            ("line feed and blank", PLAIN + "\n "),
            ("two line feeds", PLAIN + "\n\n"),
            ("carriage return and line feed", PLAIN + "\r\n"),
        ):
            with self.subTest(label=label):
                self.assert_silent(text, FIX.plain)

    def test_ac4_a_trailing_line_feed_is_not_allowed_as_the_cd_prefix_remainder(self):
        for label, tail in (
            ("line feed", PLAIN + "\n"),
            ("backslash and line feed", PLAIN + "\\\n"),
            ("blank and line feed", PLAIN + "  \n"),
        ):
            with self.subTest(label=label):
                self.assert_silent(cd_form(tail), FIX.plain)

    def test_ac4_a_padded_remainder_is_not_allowed(self):
        for label, text in all_padded(PLAIN, PRIMARY_CHARS):
            with self.subTest(label=label):
                self.assert_silent(cd_form(text), FIX.plain)

    def test_ac4_a_character_directly_after_the_separator_is_part_of_the_remainder(self):
        for name, char in PRIMARY_CHARS:
            with self.subTest(char=name):
                self.assert_silent('cd "' + str(FIX.plain_dir) + '" &&' + char + PLAIN, FIX.plain)
                self.assert_silent(cd_form(PLAIN + char), FIX.plain)


class TestAc6SpacesAndTabsStillApprove(HookCase):
    """AC-6 (FR1), hook half."""

    def test_ac6_spaces_and_tabs_around_a_command_are_removed_for_the_exact_match(self):
        for label, text in (
            ("trailing blank", PLAIN + " "),
            ("leading blank", " " + PLAIN),
            ("both sides", "  " + PLAIN + "  "),
            ("tabs", "\t" + PLAIN + "\t"),
            ("blanks and tabs mixed", " \t " + PLAIN + "\t \t"),
        ):
            for cwd in (FIX.plain, FIX.declared):
                with self.subTest(label=label, cwd=cwd.name):
                    self.assert_exact_allow(text, cwd)

    def test_ac6_spaces_and_tabs_around_the_remainder_are_removed_for_the_cd_prefix(self):
        for label, remainder in (
            ("blank after", PLAIN + "  "),
            ("tab after", PLAIN + "\t"),
            ("tabs before and after", "\t\t" + PLAIN + "\t "),
            ("no blank", PLAIN),
        ):
            with self.subTest(label=label):
                self.assert_cd_allow(cd_form(remainder), FIX.plain)

    def test_ac6_surrounding_spaces_and_tabs_on_the_whole_cd_form_are_removed(self):
        self.assert_cd_allow("  " + cd_form(PLAIN) + " \t", FIX.plain)

    def test_ac6_other_whitespace_characters_before_or_after_are_not_allowed(self):
        for label, text in all_padded(APPROVED, OTHER_CHARS):
            with self.subTest(label=label):
                self.assert_silent(text, FIX.plain)
                self.assert_unapproved_deny(text, FIX.declared)

    def test_ac6_other_whitespace_characters_around_the_cd_remainder_are_not_allowed(self):
        for label, text in all_padded(PLAIN, OTHER_CHARS):
            with self.subTest(label=label):
                self.assert_silent(cd_form(text), FIX.plain)

    def test_ac6_a_no_break_space_inside_does_not_match_a_blank(self):
        inner = "make" + NBSP + "test"
        self.assert_silent(inner, FIX.plain)
        self.assert_silent(" " + inner + " ", FIX.plain)
        self.assert_silent(cd_form(inner), FIX.plain)


class TestDeclaredCommandExtraction(HookCase):
    """FR8: the key/value separator and the trailing class take spaces and
    tabs only; the value is trimmed by spaces and tabs only."""

    def test_the_value_is_trimmed_by_spaces_and_tabs(self):
        self.assert_unapproved_deny("make lint2", FIX.declared)

    def test_a_no_break_space_after_the_colon_is_part_of_the_value(self):
        self.assert_unapproved_deny(NBSP + "make lint", FIX.declared)
        self.assert_silent("make lint", FIX.declared)

    def test_a_no_break_space_at_the_end_of_the_line_is_part_of_the_value(self):
        self.assert_unapproved_deny("make e2e" + NBSP, FIX.declared)
        self.assert_silent("make e2e", FIX.declared)


def _load_guard_module():
    """The hook's functions, loaded without writing any bytecode file."""
    module = types.ModuleType("bash_guard_under_test")
    source = GUARD_PATH.read_text(encoding="utf-8")
    exec(compile(source, str(GUARD_PATH), "exec"), module.__dict__)
    return module


class TestTrimHelpers(unittest.TestCase):
    """The two module-level helpers of the approval trim rule."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()

    def test_trim_removes_only_spaces_and_tabs_from_both_ends(self):
        trim = self.guard.trim_blanks
        self.assertEqual(trim(" \t make test\t "), "make test")
        self.assertEqual(trim("make  test"), "make  test")
        self.assertEqual(trim(" \t "), "")
        self.assertEqual(trim(""), "")
        for name, char in ALL_CHARS + (("LF", "\n"), ("CR", "\r")):
            with self.subTest(char=name):
                self.assertEqual(trim(" " + char + "x" + char + " "), char + "x" + char)

    def test_matchable_is_true_exactly_for_a_non_empty_value_with_no_whitespace_end(self):
        matchable = self.guard.is_matchable
        self.assertTrue(matchable("make test"))
        self.assertTrue(matchable("a"))
        self.assertTrue(matchable("make" + NBSP + "test"))
        self.assertTrue(matchable("a\nb"))
        self.assertFalse(matchable(""))
        for name, char in ALL_CHARS + (("LF", "\n"), ("CR", "\r")):
            with self.subTest(char=name):
                self.assertFalse(matchable(char + "x"))
                self.assertFalse(matchable("x" + char))
                self.assertFalse(matchable(char))

    def test_the_helpers_are_defined_once(self):
        tree = ast.parse(GUARD_PATH.read_text(encoding="utf-8"))
        names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        self.assertEqual(names.count("trim_blanks"), 1)
        self.assertEqual(names.count("is_matchable"), 1)
        self.assertEqual(
            names[names.index("trim_blanks") - 1], "strip_yaml_quotes"
        )
        self.assertEqual(names[names.index("is_matchable") + 1], "declared_commands")


def _docstring(path):
    return " ".join((ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or "").split())


class TestAc7Documentation(unittest.TestCase):
    """AC-7 (FR9, NFR1, NFR2, NFR3), the hook's module docstring."""

    def test_ac7_the_docstring_states_the_space_and_tab_only_trim(self):
        doc = _docstring(GUARD_PATH)
        self.assertIn("after removing surrounding spaces and tabs only", doc)
        self.assertIn("any other whitespace at either end is never allowed", doc)

    def test_ac7_the_cd_prefix_approval_item_states_the_same_for_the_remainder(self):
        doc = _docstring(GUARD_PATH)
        start = doc.index("approval: the remainder")
        item = doc[start : doc.index("operators:", start)]
        self.assertIn("surrounding spaces and tabs removed", item)
        self.assertIn("any other whitespace at either end is not approved", item)

    def test_ac7_the_docstring_no_longer_describes_the_full_strip(self):
        doc = _docstring(GUARD_PATH)
        self.assertNotIn("surrounding blanks removed", doc)
        self.assertNotIn("with surrounding blanks", doc)

    def test_ac7_the_hook_imports_only_standard_library_modules(self):
        tree = ast.parse(GUARD_PATH.read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
        self.assertTrue(found)
        self.assertEqual(found - set(sys.stdlib_module_names), set())

    def test_ac7_the_hook_source_has_no_status_substring(self):
        self.assertNotIn("status", GUARD_PATH.read_text(encoding="utf-8"))

    def test_ac7_this_module_imports_only_standard_library_modules(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
        self.assertTrue(found)
        self.assertEqual(found - set(sys.stdlib_module_names), set())


class TestAc7PreflightDocumentation(unittest.TestCase):
    """AC-7, merge-preflight.py: the module docstring and the check_approval
    comment."""

    def test_ac7_the_module_docstring_states_the_space_and_tab_only_trim(self):
        doc = _docstring(PREFLIGHT_PATH)
        self.assertIn("only spaces and tabs are removed", doc)
        self.assertIn("any other whitespace at either end is not approved", doc)
        self.assertNotIn("str.strip()", doc)

    def test_ac7_the_check_approval_comment_states_the_same(self):
        source = PREFLIGHT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "check_approval"
        )
        lines = ast.get_source_segment(source, function).splitlines()
        text = " ".join(" ".join(line.strip().lstrip("#").split()) for line in lines)
        self.assertIn("spaces and tabs only", text)
        self.assertIn("any other whitespace at either end is not approved", text)
        self.assertNotIn(".strip()", text)


if __name__ == "__main__":
    unittest.main()
