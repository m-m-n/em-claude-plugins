"""Regression tests for the end-stripped form of declared commands in
`em-workflow/hooks/bash_guard.py` (feature declared-command-yaml-breaks,
task0001).

A workflow.yaml `*_command` declaration can carry U+0085 (next line), U+2028
(line separator) or U+2029 (paragraph separator) at either end of its quoted
value. A YAML reader gives a different string from the raw characters in the
file: inside double quotes a U+0085 at an end becomes one space (U+0020) at
the same end, while U+2028 and U+2029 are kept. The hook trims spaces and tabs
from the command it receives, so the command an agent runs from the parsed
value can differ from every string the declared set held before. The declared
set therefore also holds the value with U+0020, U+0009, U+0085, U+2028 and
U+2029 removed from both ends (form (b)), next to the space/tab-trimmed value
(form (a)). Both forms are denied as unapproved. No allow path changes.

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
with the three characters present as raw characters; this source writes every
non-ASCII character as an escape sequence.

Covers task0001 Acceptance Criteria
(feature-docs/declared-command-yaml-breaks/tasks/task0001.md):

- AC-1: a leading U+0085 in a double-quoted declaration (raw, YAML-parsed and
  end-stripped forms are denied as unapproved).
- AC-2: a trailing U+0085, likewise.
- AC-3: U+2028 and U+2029 at either end, raw and end-stripped forms.
- AC-4: single-quoted and unquoted declarations; a value that is empty after
  end-stripping adds no form (b) entry and keeps its form (a) entry.
- AC-5: other whitespace characters at an end are not removed (direct calls to
  `declared_commands`).
- AC-6: no padded or end-stripped form is allowed; the bare approved command
  keeps its exact-match allow.
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

# Fragments of the reasons the hook gives, written with escape sequences.
UNAPPROVED_MARKER = "\u672a\u627f\u8a8d"
EXACT_MATCH_MARKER = "\u5b8c\u5168\u4e00\u81f4"

APPROVED = "/usr/bin/true"
UNAPPROVED = "./unapproved"

NEL = "\u0085"
LS = "\u2028"
PS = "\u2029"
NBSP = "\u00a0"

BREAK_CHARS = (("U+0085", NEL), ("U+2028", LS), ("U+2029", PS))

# Characters that are whitespace but not in the end-strip set.
NOT_REMOVED_CHARS = (
    (("U+00A0", NBSP), ("U+000B", "\u000b"), ("U+000C", "\u000c"))
    + tuple((f"U+{cp:04X}", chr(cp)) for cp in range(0x2000, 0x200B))
    + (("U+3000", "\u3000"),)
)


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
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="bash-guard-dyb-")))
        self.store = self.root / "approvals.json"
        self._repos = {}
        self._count = 0
        self.plain = self.repo(())

    def env(self):
        env = _clean_env()
        env["EM_WORKFLOW_APPROVALS"] = str(self.store)
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

    def run_hook(self, command, repo):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(repo)}
        return subprocess.run(
            [sys.executable, str(GUARD_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            encoding="utf-8",
            env=self.env(),
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


def declared_set(lines):
    """`declared_commands` on a temporary root whose workflow.yaml has `lines`."""
    with tempfile.TemporaryDirectory(prefix="bash-guard-dyb-direct-") as tmp:
        wf_dir = Path(tmp) / "feature-docs" / "demo"
        wf_dir.mkdir(parents=True)
        (wf_dir / "workflow.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return GUARD.declared_commands([tmp])


class HookCase(unittest.TestCase):
    def decision(self, command, repo):
        return decide(FIX.run_hook(command, repo))

    def assert_silent(self, command, repo):
        decision, output = self.decision(command, repo)
        self.assertEqual((decision, output), (SILENT, None), repr(command))

    def assert_unapproved_deny(self, command, repo):
        decision, output = self.decision(command, repo)
        self.assertEqual(decision, DENY, repr(command))
        self.assertIn(UNAPPROVED_MARKER, output["permissionDecisionReason"], repr(command))

    def assert_exact_allow(self, command, repo):
        decision, output = self.decision(command, repo)
        self.assertEqual(decision, ALLOW, repr(command))
        self.assertIn(EXACT_MATCH_MARKER, output["permissionDecisionReason"], repr(command))


class TestFixtureControls(HookCase):
    """The fixture denies a declared unapproved value and allows the approved one."""

    def test_a_plain_declared_unapproved_value_is_denied_and_undeclared_is_silent(self):
        repo = FIX.repo([declaration(UNAPPROVED)])
        self.assert_unapproved_deny(UNAPPROVED, repo)
        self.assert_silent(UNAPPROVED, FIX.plain)

    def test_the_approved_value_is_allowed_by_exact_match_in_both_kinds_of_repository(self):
        declaring = FIX.repo([declaration(UNAPPROVED)])
        for repo in (FIX.plain, declaring):
            with self.subTest(repo=repo.name):
                self.assert_exact_allow(APPROVED, repo)


class TestAc1LeadingNextLine(HookCase):
    """AC-1 (FR1, FR5, TM-1): U+0085 followed by `./unapproved`, double-quoted."""

    FORMS = (
        ("raw", NEL + UNAPPROVED),
        ("yaml-parsed", " " + UNAPPROVED),
        ("end-stripped", UNAPPROVED),
    )

    def test_ac1_every_form_of_a_leading_u0085_declaration_is_denied_as_unapproved(self):
        repo = FIX.repo([declaration(NEL + UNAPPROVED)])
        for label, command in self.FORMS:
            with self.subTest(form=label):
                self.assert_unapproved_deny(command, repo)

    def test_ac1_the_end_stripped_form_is_denied_for_every_command_key(self):
        for key in ("build_command", "test_command", "format_command", "e2e_test_command"):
            repo = FIX.repo([declaration(NEL + UNAPPROVED, key=key)])
            with self.subTest(key=key):
                self.assert_unapproved_deny(UNAPPROVED, repo)

    def test_ac1_the_forms_get_no_decision_without_a_declaration(self):
        for label, command in self.FORMS:
            with self.subTest(form=label):
                self.assert_silent(command, FIX.plain)


class TestAc2TrailingNextLine(HookCase):
    """AC-2 (FR1, FR5, TM-1): `./unapproved` followed by U+0085, double-quoted."""

    FORMS = (
        ("raw", UNAPPROVED + NEL),
        ("yaml-parsed", UNAPPROVED + " "),
        ("end-stripped", UNAPPROVED),
    )

    def test_ac2_every_form_of_a_trailing_u0085_declaration_is_denied_as_unapproved(self):
        repo = FIX.repo([declaration(UNAPPROVED + NEL)])
        for label, command in self.FORMS:
            with self.subTest(form=label):
                self.assert_unapproved_deny(command, repo)

    def test_ac2_the_forms_get_no_decision_without_a_declaration(self):
        for label, command in self.FORMS:
            with self.subTest(form=label):
                self.assert_silent(command, FIX.plain)


class TestAc3LineAndParagraphSeparators(HookCase):
    """AC-3 (FR1, FR5, TM-1): U+2028 and U+2029 at either end of a double-quoted
    value. The YAML-parsed form equals the raw form."""

    def test_ac3_raw_and_end_stripped_forms_are_denied_as_unapproved(self):
        for name, char in (("U+2028", LS), ("U+2029", PS)):
            for position, value in (("leading", char + UNAPPROVED), ("trailing", UNAPPROVED + char)):
                repo = FIX.repo([declaration(value)])
                for label, command in (("raw (= yaml-parsed)", value), ("end-stripped", UNAPPROVED)):
                    with self.subTest(char=name, position=position, form=label):
                        self.assert_unapproved_deny(command, repo)

    def test_ac3_the_forms_get_no_decision_without_a_declaration(self):
        for name, char in (("U+2028", LS), ("U+2029", PS)):
            for position, value in (("leading", char + UNAPPROVED), ("trailing", UNAPPROVED + char)):
                for label, command in (("raw", value), ("end-stripped", UNAPPROVED)):
                    with self.subTest(char=name, position=position, form=label):
                        self.assert_silent(command, FIX.plain)


class TestAc4OtherQuotingAndEmptyResults(HookCase):
    """AC-4 (FR1, TM-1): single-quoted and unquoted declarations; a value that
    is empty after end-stripping."""

    def test_ac4_single_quoted_and_unquoted_declarations_deny_the_end_stripped_form(self):
        for quote_label, quote in (("single-quoted", "'"), ("unquoted", "")):
            for name, char in BREAK_CHARS:
                for position, value in (
                    ("leading", char + UNAPPROVED),
                    ("trailing", UNAPPROVED + char),
                ):
                    repo = FIX.repo([declaration(value, quote)])
                    with self.subTest(quoting=quote_label, char=name, position=position):
                        self.assert_unapproved_deny(UNAPPROVED, repo)

    def test_ac4_single_quoted_and_unquoted_declarations_put_both_forms_into_the_set(self):
        for quote_label, quote in (("single-quoted", "'"), ("unquoted", "")):
            for name, char in BREAK_CHARS:
                for position, value in (
                    ("leading", char + UNAPPROVED),
                    ("trailing", UNAPPROVED + char),
                ):
                    with self.subTest(quoting=quote_label, char=name, position=position):
                        self.assertEqual(
                            declared_set([declaration(value, quote)]), {value, UNAPPROVED}
                        )

    def test_ac4_a_value_that_is_empty_after_end_stripping_adds_no_form_b_entry(self):
        only_breaks = NEL + LS + PS
        for label, quote, value in (
            ("double-quoted U+0085", '"', NEL),
            ("double-quoted U+2028", '"', LS),
            ("double-quoted U+2029", '"', PS),
            ("double-quoted all three", '"', only_breaks),
            ("single-quoted U+0085", "'", NEL),
            ("unquoted U+0085", "", NEL),
            ("unquoted all three", "", only_breaks),
        ):
            with self.subTest(case=label):
                self.assertEqual(declared_set([declaration(value, quote)]), {value})

    def test_ac4_blanks_around_a_break_only_value_are_trimmed_for_form_a_only(self):
        self.assertEqual(declared_set([declaration(" \t" + NEL + " \t")]), {NEL})

    def test_ac4_a_value_without_removable_ends_contributes_one_entry(self):
        self.assertEqual(declared_set([declaration(UNAPPROVED)]), {UNAPPROVED})
        self.assertEqual(declared_set([declaration("  " + UNAPPROVED + "\t")]), {UNAPPROVED})


class TestAc5OtherWhitespaceIsNotRemoved(unittest.TestCase):
    """AC-5 (FR2): only U+0020, U+0009, U+0085, U+2028 and U+2029 are removed
    from the ends. Direct calls to `declared_commands`."""

    def test_ac5_a_no_break_space_after_the_key_stays_part_of_the_value(self):
        declared = declared_set(["test_command:" + NBSP + "make lint"])
        self.assertIn(NBSP + "make lint", declared)
        self.assertNotIn("make lint", declared)

    def test_ac5_other_whitespace_at_an_end_of_a_quoted_value_is_not_removed(self):
        core = "make lint"
        for name, char in NOT_REMOVED_CHARS:
            for position, value in (
                ("leading", char + core),
                ("trailing", core + char),
                ("both", char + core + char),
            ):
                with self.subTest(char=name, position=position):
                    declared = declared_set([declaration(value)])
                    self.assertEqual(declared, {value})
                    self.assertNotIn(core, declared)

    def test_ac5_removal_stops_at_the_first_character_outside_the_set(self):
        value = " \t" + NEL + NBSP + UNAPPROVED + NBSP + LS + "\t "
        raw_trimmed = NEL + NBSP + UNAPPROVED + NBSP + LS
        self.assertEqual(
            declared_set([declaration(value)]),
            {raw_trimmed, NBSP + UNAPPROVED + NBSP},
        )

    def test_ac5_only_the_five_characters_are_removed_and_only_at_the_ends(self):
        value = NEL + "a" + NEL + "b" + LS + "c" + PS
        self.assertEqual(
            declared_set([declaration(value)]),
            {value, "a" + NEL + "b" + LS + "c"},
        )

    def test_ac5_form_b_gets_no_null_or_tilde_exclusion(self):
        self.assertEqual(
            declared_set([declaration(NEL + "null"), declaration("~" + LS, key="test_command")]),
            {NEL + "null", "null", "~" + LS, "~"},
        )

    def test_ac5_the_existing_exclusion_of_null_and_tilde_is_unchanged(self):
        self.assertEqual(declared_set(["build_command: null", "test_command: ~"]), set())
        self.assertEqual(declared_set([declaration("null"), declaration("~", "'")]), set())


class TestAc6NoAllowPathIsWidened(HookCase):
    """AC-6 (FR3, TM-2): the declared set only moves the boundary between deny
    and no decision."""

    DECLARED_VALUES = (
        NEL + UNAPPROVED,
        UNAPPROVED + NEL,
        LS + UNAPPROVED,
        UNAPPROVED + LS,
        PS + UNAPPROVED,
        UNAPPROVED + PS,
    )
    PADS = (
        ("U+0020", " "),
        ("U+0009", "\t"),
        ("U+0085", NEL),
        ("U+2028", LS),
        ("U+2029", PS),
        ("U+00A0", NBSP),
    )

    @classmethod
    def padded_commands(cls, core):
        yield "bare", core
        for name, char in cls.PADS:
            yield f"{name} leading", char + core
            yield f"{name} trailing", core + char
            yield f"{name} both", char + core + char

    def test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed(self):
        repo = FIX.repo([declaration(value) for value in self.DECLARED_VALUES])
        denied_forms = set(self.DECLARED_VALUES) | {UNAPPROVED}
        for label, command in self.padded_commands(UNAPPROVED):
            with self.subTest(form=label):
                decision, output = self.decision(command, repo)
                self.assertNotEqual(decision, ALLOW, repr(command))
                if command.strip(" \t") in denied_forms:
                    self.assertEqual(decision, DENY, repr(command))
                    self.assertIn(
                        UNAPPROVED_MARKER, output["permissionDecisionReason"], repr(command)
                    )
                else:
                    self.assertEqual(decision, SILENT, repr(command))

    def test_ac6_the_approved_command_padded_with_a_break_char_is_denied_where_declared(self):
        for name, char in BREAK_CHARS:
            for position, padded in (("leading", char + APPROVED), ("trailing", APPROVED + char)):
                repo = FIX.repo([declaration(padded)])
                with self.subTest(char=name, position=position):
                    self.assert_unapproved_deny(padded, repo)

    def test_ac6_the_approved_command_padded_with_a_break_char_gets_no_decision_elsewhere(self):
        for name, char in BREAK_CHARS:
            for position, padded in (("leading", char + APPROVED), ("trailing", APPROVED + char)):
                with self.subTest(char=name, position=position):
                    self.assert_silent(padded, FIX.plain)

    def test_ac6_the_bare_approved_command_keeps_its_exact_match_allow(self):
        full = FIX.repo([declaration(value) for value in self.DECLARED_VALUES])
        self.assert_exact_allow(APPROVED, full)
        for name, char in BREAK_CHARS:
            for position, padded in (("leading", char + APPROVED), ("trailing", APPROVED + char)):
                repo = FIX.repo([declaration(padded)])
                with self.subTest(char=name, position=position):
                    self.assert_exact_allow(APPROVED, repo)


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
    """AC-7 (NFR1, NFR2, NFR3, NFR4, NFR5)."""

    def test_ac7_the_hook_source_has_no_raw_next_line_or_separator_character(self):
        text = GUARD_PATH.read_text(encoding="utf-8")
        for name, char in BREAK_CHARS:
            with self.subTest(char=name):
                self.assertNotIn(char, text)

    def test_ac7_the_hook_helpers_are_defined_once_and_in_order(self):
        tree = ast.parse(GUARD_PATH.read_text(encoding="utf-8"))
        names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
        order = ["strip_yaml_quotes", "trim_blanks", "is_matchable", "declared_commands"]
        for name in order:
            self.assertEqual(names.count(name), 1, name)
        start = names.index("strip_yaml_quotes")
        self.assertEqual(names[start : start + len(order)], order)

    def test_ac7_the_hook_imports_only_standard_library_modules(self):
        found = _imported_modules(GUARD_PATH)
        self.assertTrue(found)
        self.assertEqual(found - set(sys.stdlib_module_names), set())

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
