"""Regression tests for the six-character end-strip declared match in
`em-workflow/hooks/bash_guard.py` (feature declared-command-edge-fold,
task0001).

A workflow.yaml `*_command` declaration can carry U+0085 (next line), U+2028
(line separator) or U+2029 (paragraph separator), mixed or repeated, at the
ends of its quoted value. A YAML reader turns a U+0085 inside double quotes
into one space or one line feed, depending on where it sits, and keeps U+2028
and U+2029. The string a YAML reader gives for such a declaration can differ
from every string in the declared set that `declared_commands` builds with its
five-character end strip.

The hook therefore also compares the end-stripped form of the received command
with the declared set. The six characters are U+0020, U+0009, LF (U+000A),
U+0085, U+2028 and U+2029; the end-stripped form is the command with every
leading and trailing occurrence of them removed, in any number and any mix. The
form is used only for the declared check, so it moves the boundary between deny
and no decision and never adds an allow.

Every hook case drives the hook as a subprocess with PreToolUse JSON on
standard input and reads the decision from standard output. The expected
decision is one of three:

- `allow`  -- a JSON `permissionDecision: allow` on standard output.
- `deny`   -- a JSON `permissionDecision: deny` on standard output.
- `silent` -- no output at all (no decision; the normal permission flow
  applies).

The YAML-parsed forms are written here as literals; no YAML library is used.

Isolation: the approval store is a temporary file selected through
`EM_WORKFLOW_APPROVALS` and holds only `/usr/bin/true`, `CLAUDE_PROJECT_DIR` is
removed from the hook's environment, and every repository is a temporary git
repository. The real approval store and the real repository's workflow.yaml
are never read. Each case that needs a declaration gets a repository whose
workflow.yaml declares only that case's value, so a deny cannot be credited to
another case's declaration. The workflow.yaml fixtures are written as UTF-8
with the characters present as raw characters; this source writes every
non-ASCII character as an escape sequence.

Covers task0001 Acceptance Criteria
(feature-docs/declared-command-edge-fold/tasks/task0001.md):

- AC-1: rows one to four of the table (U+0085 next to U+2028 or U+2029 at
  opposite ends), double-quoted.
- AC-2: rows five to ten (repeated or mixed characters at one end),
  double-quoted.
- AC-3: the same declarations single-quoted, and the early-return path with an
  approval store file that does not exist.
- AC-4: no decision without a declaration, no allow anywhere, the approved
  command keeps its allow, U+00A0 padding and an all-newline declaration get
  no decision, and the cd-prefixed form keeps its verdict.
- AC-5: the approved command padded with LF, U+0085, U+2028 or U+2029 is denied
  where it is declared.
- AC-6: `declared_commands` is unchanged for a declaration of AC-1.
- AC-7: source constraints of the hook and of this module.

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

ALLOW = "allow"
DENY = "deny"
SILENT = "silent"

# Fragment of the unapproved-deny reason, written with escape sequences.
UNAPPROVED_MARKER = "\u672a\u627f\u8a8d"

APPROVED = "/usr/bin/true"
UNAPPROVED = "./unapproved"

NEL = "\u0085"
LS = "\u2028"
PS = "\u2029"
NBSP = "\u00a0"
LF = "\n"

# The six characters of the end-stripped form.
SIX_CHARS = " \t" + LF + NEL + LS + PS

# The verdict of the hook, before this task changed it, for the cd-prefixed
# approved command with a trailing U+2028 (AC-4). Recorded by running the
# unchanged hook before the hook was edited.
CD_PREFIXED_VERDICT_BEFORE_CHANGE = SILENT

# (label, declaration inside the quotes, YAML-parsed form).
AC1_ROWS = (
    ("row 1", NEL + UNAPPROVED + LS, " " + UNAPPROVED + LS),
    ("row 2", NEL + UNAPPROVED + PS, " " + UNAPPROVED + PS),
    ("row 3", LS + UNAPPROVED + NEL, LS + UNAPPROVED + " "),
    ("row 4", PS + UNAPPROVED + NEL, PS + UNAPPROVED + " "),
)
AC2_ROWS = (
    ("row 5", NEL + NEL + UNAPPROVED, LF + UNAPPROVED),
    ("row 6", UNAPPROVED + NEL + NEL, UNAPPROVED + LF),
    ("row 7", NEL + LS + UNAPPROVED, LS + UNAPPROVED),
    ("row 8", UNAPPROVED + NEL + LS, UNAPPROVED + LS),
    ("row 9", LS + NEL + UNAPPROVED, LS + LF + UNAPPROVED),
    ("row 10", UNAPPROVED + LS + NEL, UNAPPROVED + LS + LF),
)
LAST_ROW = ("row 11", NEL + LS + PS, LS + PS)

DENIED_ROWS = AC1_ROWS + AC2_ROWS


def declaration(value, quote='"', key="build_command"):
    """One workflow.yaml line: `key: <quote>value<quote>`."""
    return f"{key}: {quote}{value}{quote}"


def _clean_env():
    return {
        key: value
        for key, value in os.environ.items()
        if key != "CLAUDE_PROJECT_DIR" and not key.startswith("GIT_")
    }


def _git_init(path):
    env = _clean_env()
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    proc = subprocess.run(
        ["git", "-C", str(path), "init", "-q"],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git init failed: {proc.stderr}")


class Fixture:
    """Temporary git repositories and one approval store that holds only
    `/usr/bin/true` for each of them. `plain` has no workflow.yaml."""

    def __init__(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="bash-guard-aef-")))
        self.store = self.root / "approvals.json"
        # A path that never exists: the approval store file is absent.
        self.absent_store = self.root / "absent-store" / "approvals.json"
        self._repos = {}
        self._count = 0
        self.plain = self.repo(())

    def env(self, store=None):
        env = _clean_env()
        env["EM_WORKFLOW_APPROVALS"] = str(store or self.store)
        env["GIT_CEILING_DIRECTORIES"] = str(self.root)
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def repo(self, lines):
        """A repository whose workflow.yaml has exactly `lines` (no
        workflow.yaml for an empty tuple). Repeated calls with the same lines
        return the same repository."""
        key = tuple(lines)
        if key in self._repos:
            return self._repos[key]
        self._count += 1
        path = self.root / f"repo{self._count:03d}"
        path.mkdir()
        _git_init(path)
        if key:
            wf_dir = path / "feature-docs" / "demo"
            wf_dir.mkdir(parents=True)
            (wf_dir / "workflow.yaml").write_text("\n".join(key) + "\n", encoding="utf-8")
        self._record(path, (APPROVED,))
        self._repos[key] = path
        return path

    def _record(self, project_dir, commands):
        proc = subprocess.run(
            [sys.executable, str(GUARD_PATH), "--record", "--project-dir", str(project_dir)],
            input="\n".join(commands) + "\n",
            capture_output=True,
            encoding="utf-8",
            env=self.env(),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"--record failed: {proc.stderr}")

    def run_hook(self, command, repo, store=None):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(repo)}
        return subprocess.run(
            [sys.executable, str(GUARD_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            encoding="utf-8",
            env=self.env(store),
            cwd=str(repo),
        )

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def _load_guard_module():
    """The hook's functions, loaded without writing any bytecode file."""
    module = types.ModuleType("bash_guard_under_test")
    source = GUARD_PATH.read_text(encoding="utf-8")
    exec(compile(source, str(GUARD_PATH), "exec"), module.__dict__)
    return module


FIX = None
GUARD = None


def setUpModule():
    global FIX, GUARD
    GUARD = _load_guard_module()
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


class HookCase(unittest.TestCase):
    def decision(self, command, repo, store=None):
        return decide(FIX.run_hook(command, repo, store))

    def assert_silent(self, command, repo, store=None):
        decision, output = self.decision(command, repo, store)
        self.assertEqual((decision, output), (SILENT, None), repr(command))

    def assert_unapproved_deny(self, command, repo, store=None):
        decision, output = self.decision(command, repo, store)
        self.assertEqual(decision, DENY, repr(command))
        self.assertIn(UNAPPROVED_MARKER, output["permissionDecisionReason"], repr(command))

    def assert_not_allowed(self, command, repo, store=None):
        decision, _ = self.decision(command, repo, store)
        self.assertNotEqual(decision, ALLOW, repr(command))

    def assert_exact_allow(self, command, repo):
        decision, _ = self.decision(command, repo)
        self.assertEqual(decision, ALLOW, repr(command))


class TestFixtureControls(HookCase):
    """The fixture denies a declared unapproved value and allows the approved one."""

    def test_a_plain_declared_unapproved_value_is_denied_and_undeclared_is_silent(self):
        repo = FIX.repo([declaration(UNAPPROVED)])
        self.assert_unapproved_deny(UNAPPROVED, repo)
        self.assert_silent(UNAPPROVED, FIX.plain)


class TestAc1OppositeEnds(HookCase):
    """AC-1 (FR1, FR4, TM-1): rows one to four, double-quoted."""

    def test_ac1_the_yaml_parsed_form_is_denied_as_unapproved(self):
        for label, value, parsed in AC1_ROWS:
            repo = FIX.repo([declaration(value)])
            with self.subTest(row=label):
                self.assert_unapproved_deny(parsed, repo)

    def test_ac1_the_raw_form_and_the_bare_command_stay_denied_as_unapproved(self):
        for label, value, _parsed in AC1_ROWS:
            repo = FIX.repo([declaration(value)])
            for form_label, command in (("raw", value), ("bare", UNAPPROVED)):
                with self.subTest(row=label, form=form_label):
                    self.assert_unapproved_deny(command, repo)


class TestAc2RepeatedAndMixedEnds(HookCase):
    """AC-2 (FR1, FR4, TM-1): rows five to ten, double-quoted."""

    def test_ac2_the_yaml_parsed_form_is_denied_as_unapproved(self):
        for label, value, parsed in AC2_ROWS:
            repo = FIX.repo([declaration(value)])
            with self.subTest(row=label):
                self.assert_unapproved_deny(parsed, repo)

    def test_ac2_the_denial_holds_for_every_command_key(self):
        label, value, parsed = AC2_ROWS[0]
        for key in ("build_command", "test_command", "format_command", "e2e_test_command"):
            repo = FIX.repo([declaration(value, key=key)])
            with self.subTest(row=label, key=key):
                self.assert_unapproved_deny(parsed, repo)


class TestAc3SingleQuotesAndMissingStore(HookCase):
    """AC-3 (FR1, FR4, TM-1): single quotes, and the early-return path."""

    def test_ac3_single_quoted_declarations_deny_the_yaml_parsed_form(self):
        for label, value, parsed in DENIED_ROWS:
            repo = FIX.repo([declaration(value, "'")])
            with self.subTest(row=label):
                self.assert_unapproved_deny(parsed, repo)

    def test_ac3_a_missing_approval_store_still_denies_the_yaml_parsed_form(self):
        label, value, parsed = AC1_ROWS[0]
        repo = FIX.repo([declaration(value)])
        self.assertFalse(FIX.absent_store.exists())
        with self.subTest(row=label):
            self.assert_unapproved_deny(parsed, repo, store=FIX.absent_store)

    def test_ac3_a_missing_approval_store_gets_no_decision_without_a_declaration(self):
        label, _value, parsed = AC1_ROWS[0]
        self.assertFalse(FIX.absent_store.exists())
        with self.subTest(row=label):
            self.assert_silent(parsed, FIX.plain, store=FIX.absent_store)


class TestAc4NoWidenedAllow(HookCase):
    """AC-4 (FR1, FR2, FR4, TM-2): the match moves deny and no decision only."""

    def yaml_parsed_forms(self):
        for label, _value, parsed in DENIED_ROWS:
            yield label, parsed

    def every_form(self):
        for label, value, parsed in DENIED_ROWS:
            yield f"{label} parsed", parsed
            yield f"{label} raw", value
        yield "bare", UNAPPROVED

    def test_ac4_without_a_declaration_every_yaml_parsed_form_gets_no_decision(self):
        for label, parsed in self.yaml_parsed_forms():
            with self.subTest(row=label):
                self.assert_silent(parsed, FIX.plain)

    def test_ac4_no_form_is_allowed_with_or_without_the_declaration(self):
        for row_label, value, _parsed in DENIED_ROWS:
            repo = FIX.repo([declaration(value)])
            for label, command in self.every_form():
                with self.subTest(row=row_label, form=label, repo="declaring"):
                    self.assert_not_allowed(command, repo)
        for label, command in self.every_form():
            with self.subTest(form=label, repo="plain"):
                self.assert_not_allowed(command, FIX.plain)

    def test_ac4_the_approved_command_is_allowed_in_both_kinds_of_repository(self):
        declaring = FIX.repo([declaration(AC1_ROWS[0][1])])
        for repo in (FIX.plain, declaring):
            with self.subTest(repo=repo.name):
                self.assert_exact_allow(APPROVED, repo)

    def test_ac4_no_break_space_padding_gets_no_decision_in_a_declaring_repository(self):
        repo = FIX.repo([declaration(AC1_ROWS[0][1])])
        self.assert_silent(NBSP + UNAPPROVED + NBSP, repo)

    def test_ac4_a_declaration_of_newline_characters_only_gets_no_decision(self):
        label, value, parsed = LAST_ROW
        repo = FIX.repo([declaration(value)])
        with self.subTest(row=label):
            self.assert_silent(parsed, repo)

    def test_ac4_the_cd_prefixed_approved_command_with_a_trailing_u2028_keeps_its_verdict(self):
        repo = FIX.repo([declaration(APPROVED, quote="")])
        command = f'cd "{repo}" && {APPROVED}{LS}'
        decision, _output = self.decision(command, repo)
        self.assertNotEqual(decision, ALLOW)
        self.assertEqual(decision, CD_PREFIXED_VERDICT_BEFORE_CHANGE)


class TestAc5ApprovedCommandPaddedAtAnEnd(HookCase):
    """AC-5 (FR3): where the approved command is declared, a padded form is
    denied as unapproved; elsewhere it gets no decision."""

    PADDED = (
        ("trailing LF", APPROVED + LF),
        ("leading U+0085", NEL + APPROVED),
        ("trailing U+2028", APPROVED + LS),
        ("trailing U+2029", APPROVED + PS),
    )

    def test_ac5_the_padded_forms_are_denied_where_the_command_is_declared(self):
        repo = FIX.repo([declaration(APPROVED, quote="")])
        for label, command in self.PADDED:
            with self.subTest(form=label):
                self.assert_unapproved_deny(command, repo)

    def test_ac5_the_padded_forms_get_no_decision_without_a_declaration(self):
        for label, command in self.PADDED:
            with self.subTest(form=label):
                self.assert_silent(command, FIX.plain)


class TestAc6DeclaredCommandsIsUnchanged(unittest.TestCase):
    """AC-6 (FR2): the declared set that `declared_commands` returns."""

    def test_ac6_a_declaration_of_row_one_adds_exactly_the_raw_value_and_the_bare_command(self):
        _label, value, _parsed = AC1_ROWS[0]
        repo = FIX.repo([declaration(value)])
        self.assertEqual(GUARD.declared_commands([str(repo)]), {value, UNAPPROVED})


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


class TestAc7SourceConstraints(unittest.TestCase):
    """AC-7 (FR5, NFR1 to NFR7): shape of the hook source and of this module."""

    HELPERS_IN_ORDER = ["strip_yaml_quotes", "trim_blanks", "is_matchable", "declared_commands"]

    def setUp(self):
        self.text = GUARD_PATH.read_text(encoding="utf-8")
        self.tree = ast.parse(self.text)

    def six_char_constants(self):
        """(index in the module body, name) of every module-level string
        constant whose characters are exactly the six characters."""
        found = []
        for index, node in enumerate(self.tree.body):
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
                continue
            if set(value.value) != set(SIX_CHARS):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.append((index, target.id))
        return found

    def single_six_char_constant(self):
        found = self.six_char_constants()
        self.assertEqual(len(found), 1, found)
        return found[0]

    def test_ac7_exactly_one_module_level_constant_holds_the_six_characters(self):
        _index, name = self.single_six_char_constant()
        self.assertNotEqual(name, "DECLARED_END_STRIP")
        self.assertNotIn("status", name.lower())

    def test_ac7_the_five_character_declared_end_strip_is_unchanged(self):
        self.assertEqual(GUARD.DECLARED_END_STRIP, " \t" + NEL + LS + PS)

    def test_ac7_the_constant_is_not_placed_between_the_declared_helper_definitions(self):
        names = [node.name if isinstance(node, ast.FunctionDef) else None for node in self.tree.body]
        first = names.index(self.HELPERS_IN_ORDER[0])
        last = names.index(self.HELPERS_IN_ORDER[-1])
        index, _name = self.single_six_char_constant()
        self.assertFalse(first <= index <= last, (first, index, last))

    def test_ac7_the_helpers_are_defined_once_and_in_order(self):
        names = [node.name for node in self.tree.body if isinstance(node, ast.FunctionDef)]
        for name in self.HELPERS_IN_ORDER:
            self.assertEqual(names.count(name), 1, name)
        start = names.index(self.HELPERS_IN_ORDER[0])
        self.assertEqual(names[start : start + 4], self.HELPERS_IN_ORDER)

    def test_ac7_only_hook_main_uses_the_constant(self):
        _index, name = self.single_six_char_constant()
        users = []
        for node in self.tree.body:
            uses = [n for n in ast.walk(node) if isinstance(n, ast.Name) and n.id == name]
            if isinstance(node, ast.Assign):
                uses = [n for n in uses if not isinstance(n.ctx, ast.Store)]
            if uses:
                users.append(getattr(node, "name", None))
        self.assertEqual(users, ["hook_main"])

    def test_ac7_the_hook_source_has_no_raw_next_line_or_separator_character(self):
        for name, char in (("U+0085", NEL), ("U+2028", LS), ("U+2029", PS)):
            with self.subTest(char=name):
                self.assertNotIn(char, self.text)

    def test_ac7_the_hook_imports_only_standard_library_modules(self):
        found = _imported_modules(GUARD_PATH)
        self.assertTrue(found)
        self.assertEqual(found - set(sys.stdlib_module_names), set())

    def test_ac7_the_module_docstring_names_the_characters_and_keeps_its_pinned_phrases(self):
        docstring = " ".join(ast.get_docstring(self.tree).split())
        for phrase in (
            "U+0085",
            "U+2028",
            "U+2029",
            "end-stripped",
            "after removing surrounding spaces and tabs only",
            "any other whitespace at either end is never allowed",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, docstring)

    def test_ac7_this_module_imports_only_standard_library_modules(self):
        found = _imported_modules(Path(__file__))
        self.assertTrue(found)
        self.assertEqual(found - set(sys.stdlib_module_names), set())
        self.assertNotIn("yaml", found)

    def test_ac7_this_module_source_has_only_ascii_characters(self):
        data = Path(__file__).read_bytes()
        self.assertEqual([b for b in data if b > 0x7F], [])


if __name__ == "__main__":
    unittest.main()
