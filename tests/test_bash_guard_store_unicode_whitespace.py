"""Store-side tests for the approval trim rule in
`em-workflow/hooks/bash_guard.py`.

Feature approval-unicode-whitespace, task0002: the approved set
(`approved_for`, `--list`) and the `--record` / `--remove` stdin lines trim
spaces and tabs only. A value that still has any other whitespace character
(by `str.isspace()`) at either end after that trim is non-matchable: a stored
entry of that kind is never approved and never listed, and one such stdin line
refuses the whole `--record` / `--remove` input without touching the store.

Every case runs bash_guard.py as a child process, the way the approval gate
and Claude Code run it:

- the CLI with `--project-dir` pointing at a temporary git repository and the
  input given as bytes;
- the hook with a PreToolUse JSON payload on standard input.

Isolation: the approval store is a temporary file selected through
`EM_WORKFLOW_APPROVALS`, `CLAUDE_PROJECT_DIR` and `GIT_*` are removed from the
child environment, and the repository is a temporary git repository. The real
approval store is never read or written. Non-ASCII and control whitespace is
written as escape sequences, never as raw invisible characters.

Hook assertions use matchable commands only (`/usr/bin/true`, `make test`,
`make<U+00A0>test`); how the hook treats a command that is itself padded with
other whitespace is another task's contract.

- AC-1: a stored entry padded with U+00A0, U+000B, U+000C, CR or LF is neither
  listed nor approved (`TestAc1StoredEntryWithOtherWhitespace`).
- AC-2: one non-matchable stdin line refuses the whole `--record` / `--remove`
  input and leaves the store untouched (`TestAc2NonMatchableLineRefusesInput`).
- AC-3: space/tab-only padding behaves as before (`TestAc3SpaceAndTabBehaviour`).
- AC-4: a non-matchable stored entry disappears from the stored list on the
  next successful run (`TestAc4NonMatchableEntryDropsOnNextWrite`).
- AC-5: the other whitespace characters and the inner-whitespace case
  (`TestAc5OtherWhitespaceAndInnerWhitespace`).
- AC-6: standard library only, no `status` substring, the C2 helpers
  (`TestAc6ModuleContract`).

Standard library only.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "bash_guard.py"

NBSP = " "
VT = "\u000b"
FF = "\u000c"
CR = "\r"
LF = "\n"
NEL = "\u0085"
EN_QUAD = " "
IDEOGRAPHIC_SPACE = "　"
UNIT_SEPARATOR = "\u001f"

# The primary character set of the feature (each before, after and on both
# sides of a value) and the representative other whitespace characters.
PRIMARY_CHARS = (("U+00A0", NBSP), ("U+000B", VT), ("U+000C", FF))
OTHER_CHARS = (
    ("U+0085", NEL),
    ("U+2000", EN_QUAD),
    ("U+3000", IDEOGRAPHIC_SPACE),
    ("U+001F", UNIT_SEPARATOR),
)
# Characters that can pad a stored entry (the store is JSON, so LF is possible
# there although a stdin line cannot hold one).
STORED_CHARS = PRIMARY_CHARS + (("CR", CR), ("LF", LF))

ALLOW = "allow"
SILENT = "silent"

TRUE_COMMAND = "/usr/bin/true"
TEST_COMMAND = "make test"
LINT_COMMAND = "make lint"
BUILD_COMMAND = "make build"
INNER_NBSP_COMMAND = "make" + NBSP + "test"

REPORT_PREFIX = "bash_guard: REFUSED ("


def _paddings(char, command):
    return (
        ("before", char + command),
        ("after", command + char),
        ("both", char + command + char),
    )


def _lines(text):
    """Split on LF only; `str.splitlines` also splits on U+000B, U+000C, U+001F."""
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def _base_env():
    return {
        key: value
        for key, value in os.environ.items()
        if key not in ("CLAUDE_PROJECT_DIR", "EM_WORKFLOW_APPROVALS")
        and not key.startswith("GIT_")
    }


def _git(directory, *args):
    env = _base_env()
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    proc = subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


_module_dir = None
REPO = None
PROJECT_KEY = None


def setUpModule():
    global _module_dir, REPO, PROJECT_KEY
    _module_dir = tempfile.TemporaryDirectory(prefix="bash-guard-store-ws-repo-")
    REPO = Path(os.path.realpath(_module_dir.name)) / "repo"
    REPO.mkdir()
    _git(REPO, "init", "-q")
    # The key bash_guard.py files a project under: the absolute git common dir.
    PROJECT_KEY = _git(
        REPO, "rev-parse", "--path-format=absolute", "--git-common-dir"
    )


def tearDownModule():
    _module_dir.cleanup()


class StoreTestCase(unittest.TestCase):
    """A fresh store location per test; helpers to run the CLI and the hook."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="bash-guard-store-ws-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(os.path.realpath(tmp.name))
        # The store lives in a directory of its own, so a leftover temporary
        # file beside it shows up in a directory listing.
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.store = self.state / "approvals.json"
        self.env = _base_env()
        self.env["EM_WORKFLOW_APPROVALS"] = str(self.store)
        self.env["PYTHONIOENCODING"] = "utf-8"

    # -- store access -----------------------------------------------------

    def plant(self, entries, key=None):
        """Write the store file directly, as a user (or an older version) could."""
        data = {
            "version": 1,
            "projects": {
                key or PROJECT_KEY: {
                    "approved_commands": entries,
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        }
        self.store.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def stored_commands(self):
        """The project's stored list, or None when the project has no entry."""
        data = json.loads(self.store.read_text(encoding="utf-8"))
        entry = data["projects"].get(PROJECT_KEY)
        return None if entry is None else entry["approved_commands"]

    def snapshot(self):
        """The store file's bytes (None when absent) and the store directory listing."""
        content = self.store.read_bytes() if self.store.exists() else None
        return content, sorted(path.name for path in self.state.iterdir())

    # -- child processes --------------------------------------------------

    def run_cli(self, mode, stdin=""):
        data = stdin.encode("utf-8") if isinstance(stdin, str) else stdin
        proc = subprocess.run(
            [sys.executable, str(GUARD_PATH), mode, "--project-dir", str(REPO)],
            input=data,
            capture_output=True,
            env=self.env,
            cwd=str(self.tmp),
            timeout=60,
        )
        return types.SimpleNamespace(
            returncode=proc.returncode,
            stdout=proc.stdout.decode("utf-8"),
            stderr=proc.stderr.decode("utf-8"),
        )

    def run_hook(self, command):
        """The hook's decision for `command`: allow, deny or silent."""
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(REPO)}
        )
        proc = subprocess.run(
            [sys.executable, str(GUARD_PATH)],
            input=payload.encode("utf-8"),
            capture_output=True,
            env=self.env,
            cwd=str(self.tmp),
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8"))
        out = proc.stdout.decode("utf-8")
        if not out.strip():
            return SILENT
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"]

    # -- shared assertions ------------------------------------------------

    def assert_list(self, expected):
        result = self.run_cli("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(_lines(result.stdout), expected)

    def assert_input_refused(self, mode, stdin, bad_lines):
        """The run refuses the input: exit 1, one report per bad line, nothing
        approved on stdout, and the store file and its directory unchanged."""
        before = self.snapshot()
        result = self.run_cli(mode, stdin)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        reports = [
            line for line in _lines(result.stderr) if line.startswith(REPORT_PREFIX)
        ]
        self.assertEqual(len(reports), len(bad_lines), result.stderr)
        for line in bad_lines:
            suffix = "): " + ascii(line.strip(" \t"))
            self.assertTrue(
                any(report.endswith(suffix) for report in reports),
                f"no report for {ascii(line)} in {result.stderr!r}",
            )
        self.assertEqual(self.snapshot(), before)


class TestAc1StoredEntryWithOtherWhitespace(StoreTestCase):
    """AC-1 (FR1, FR6, TM-7)."""

    def test_ac1_list_omits_an_entry_padded_with_other_whitespace(self):
        for name, char in STORED_CHARS:
            for where, entry in _paddings(char, TRUE_COMMAND):
                with self.subTest(char=name, where=where):
                    self.plant([entry])
                    self.assert_list([])

    def test_ac1_hook_does_not_allow_the_stripped_form_of_such_an_entry(self):
        for name, char in STORED_CHARS:
            for where, entry in _paddings(char, TRUE_COMMAND):
                with self.subTest(char=name, where=where):
                    self.plant([entry])
                    self.assertEqual(self.run_hook(TRUE_COMMAND), SILENT)

    def test_ac1_entry_mixed_with_spaces_and_tabs_is_still_not_approved(self):
        entries = [
            " \t" + NBSP + TEST_COMMAND,
            LINT_COMMAND + VT + " \t ",
            "  " + FF + BUILD_COMMAND + CR + "\t",
        ]
        self.plant(entries)
        self.assert_list([])
        for command in (TEST_COMMAND, LINT_COMMAND, BUILD_COMMAND):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(command), SILENT)

    def test_ac1_entry_of_only_other_whitespace_is_not_listed(self):
        self.plant([NBSP, VT + FF, CR + LF, " " + NBSP + "\t"])
        self.assert_list([])

    def test_ac1_stripped_form_stored_as_its_own_entry_is_still_approved(self):
        self.plant([NBSP + TRUE_COMMAND, TRUE_COMMAND])
        self.assert_list([TRUE_COMMAND])
        self.assertEqual(self.run_hook(TRUE_COMMAND), ALLOW)

    def test_ac1_matchable_entry_is_listed_and_approved(self):
        self.plant([TRUE_COMMAND])
        self.assert_list([TRUE_COMMAND])
        self.assertEqual(self.run_hook(TRUE_COMMAND), ALLOW)


class TestAc2NonMatchableLineRefusesInput(StoreTestCase):
    """AC-2 (FR7, TM-6)."""

    MODES = ("--record", "--remove")

    def bad_lines(self):
        lines = []
        for _, char in PRIMARY_CHARS + (("CR", CR),):
            lines.extend(line for _, line in _paddings(char, TEST_COMMAND))
        return lines

    def check_each_bad_line(self, planted):
        for mode in self.MODES:
            for bad in self.bad_lines():
                with self.subTest(mode=mode, line=ascii(bad), planted=planted):
                    if planted:
                        self.plant([LINT_COMMAND])
                    elif self.store.exists():
                        self.store.unlink()
                    # The other lines of the same input are matchable.
                    stdin = BUILD_COMMAND + "\n" + bad + "\n" + LINT_COMMAND + "\n"
                    self.assert_input_refused(mode, stdin, [bad])

    def test_ac2_refused_with_an_existing_store(self):
        self.check_each_bad_line(planted=True)

    def test_ac2_refused_with_no_store(self):
        self.check_each_bad_line(planted=False)
        self.assertFalse(self.store.exists())

    def test_ac2_crlf_terminated_line_is_refused(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                self.plant([LINT_COMMAND])
                self.assert_input_refused(
                    mode, TEST_COMMAND + "\r\n" + BUILD_COMMAND + "\n", [TEST_COMMAND + CR]
                )

    def test_ac2_line_of_only_other_whitespace_is_refused_not_skipped(self):
        for bad in (NBSP, VT, FF, "\r", " " + NBSP + "\t"):
            for mode in self.MODES:
                with self.subTest(mode=mode, line=ascii(bad)):
                    self.plant([LINT_COMMAND])
                    self.assert_input_refused(mode, bad + "\n" + BUILD_COMMAND + "\n", [bad])

    def test_ac2_every_non_matchable_line_is_reported_and_matchable_ones_are_not(self):
        bad = [NBSP + TEST_COMMAND, LINT_COMMAND + VT, FF + BUILD_COMMAND + FF]
        stdin = "\n".join([bad[0], TRUE_COMMAND, bad[1], "", bad[2]]) + "\n"
        for mode in self.MODES:
            with self.subTest(mode=mode):
                self.plant([LINT_COMMAND])
                self.assert_input_refused(mode, stdin, bad)

    def test_ac2_final_line_without_a_line_feed_is_judged_as_it_is(self):
        # Nothing is removed from a final line that has no LF, so a trailing CR
        # or U+00A0 stays and the line is refused.
        for tail in (TEST_COMMAND + CR, TEST_COMMAND + NBSP, NBSP + TEST_COMMAND):
            for mode in self.MODES:
                with self.subTest(mode=mode, tail=ascii(tail)):
                    self.plant([LINT_COMMAND])
                    self.assert_input_refused(mode, BUILD_COMMAND + "\n" + tail, [tail])

    def test_ac2_refused_run_approves_nothing_for_the_hook(self):
        self.assert_input_refused("--record", NBSP + TEST_COMMAND + "\n" + BUILD_COMMAND + "\n", [NBSP + TEST_COMMAND])
        self.assertEqual(self.run_hook(BUILD_COMMAND), SILENT)
        self.assertEqual(self.run_hook(TEST_COMMAND), SILENT)

    def test_ac2_non_matchable_line_with_a_refusal_pattern_is_still_refused(self):
        bad = NBSP + "sudo " + TEST_COMMAND
        before = self.snapshot()
        result = self.run_cli("--record", bad + "\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.snapshot(), before)


class TestAc3SpaceAndTabBehaviour(StoreTestCase):
    """AC-3 (FR1, FR7)."""

    def test_ac3_record_stores_the_space_and_tab_trimmed_form(self):
        stdin = "  \t" + TEST_COMMAND + " \t \n\n \t \n" + LINT_COMMAND + "\n"
        result = self.run_cli("--record", stdin)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            _lines(result.stdout)[1:],
            ["approved: " + LINT_COMMAND, "approved: " + TEST_COMMAND],
        )
        self.assertEqual(self.stored_commands(), [LINT_COMMAND, TEST_COMMAND])
        self.assert_list([LINT_COMMAND, TEST_COMMAND])
        self.assertEqual(self.run_hook(TEST_COMMAND), ALLOW)
        self.assertEqual(self.run_hook(LINT_COMMAND), ALLOW)

    def test_ac3_remove_matches_the_space_and_tab_trimmed_form(self):
        self.plant([LINT_COMMAND, TEST_COMMAND])
        result = self.run_cli("--remove", "\t " + TEST_COMMAND + "  \n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stored_commands(), [LINT_COMMAND])
        self.assertEqual(self.run_hook(TEST_COMMAND), SILENT)
        self.assertEqual(self.run_hook(LINT_COMMAND), ALLOW)

    def test_ac3_exactly_one_trailing_line_feed_is_removed(self):
        for stdin in (TEST_COMMAND + "\n", TEST_COMMAND):
            with self.subTest(stdin=ascii(stdin)):
                if self.store.exists():
                    self.store.unlink()
                result = self.run_cli("--record", stdin)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.stored_commands(), [TEST_COMMAND])

    def test_ac3_stored_entry_with_spaces_and_tabs_is_listed_and_approved_trimmed(self):
        self.plant(["  " + TEST_COMMAND + "\t"])
        self.assert_list([TEST_COMMAND])
        self.assertEqual(self.run_hook(TEST_COMMAND), ALLOW)

    def test_ac3_non_string_and_empty_stored_entries_are_not_members(self):
        self.plant([None, 5, "", " \t ", ["x"], {"a": 1}, TEST_COMMAND])
        self.assert_list([TEST_COMMAND])

    def test_ac3_input_with_no_command_left_exits_1_with_the_existing_message(self):
        for stdin in ("", "\n", "  \t\n\n \t \n", " \t"):
            for mode in ("--record", "--remove"):
                with self.subTest(mode=mode, stdin=ascii(stdin)):
                    self.plant([LINT_COMMAND])
                    before = self.snapshot()
                    result = self.run_cli(mode, stdin)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(
                        _lines(result.stderr), ["bash_guard: no commands on stdin"]
                    )
                    self.assertEqual(self.snapshot(), before)

    def test_ac3_refusal_pattern_still_refuses_record(self):
        before = self.snapshot()
        result = self.run_cli("--record", "sudo " + TEST_COMMAND + "\n" + BUILD_COMMAND + "\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn(
            "bash_guard: REFUSED (privilege escalation (sudo/doas)): sudo " + TEST_COMMAND,
            _lines(result.stderr),
        )
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.store.exists())


class TestAc4NonMatchableEntryDropsOnNextWrite(StoreTestCase):
    """AC-4 (FR6, FR7): the merge base for both modes is the approved set."""

    PLANTED = [NBSP + TRUE_COMMAND, LINT_COMMAND, TEST_COMMAND + VT, "  " + BUILD_COMMAND + "\t"]

    def test_ac4_successful_record_drops_non_matchable_entries(self):
        self.plant(self.PLANTED)
        result = self.run_cli("--record", "make clean\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stored_commands(), [BUILD_COMMAND, "make clean", LINT_COMMAND])
        self.assertEqual(
            _lines(result.stdout)[1:],
            ["approved: " + BUILD_COMMAND, "approved: make clean", "approved: " + LINT_COMMAND],
        )

    def test_ac4_successful_remove_drops_non_matchable_entries(self):
        self.plant(self.PLANTED)
        result = self.run_cli("--remove", LINT_COMMAND + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stored_commands(), [BUILD_COMMAND])

    def test_ac4_remove_of_an_absent_command_still_drops_them(self):
        self.plant(self.PLANTED)
        result = self.run_cli("--remove", "make clean\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stored_commands(), [BUILD_COMMAND, LINT_COMMAND])

    def test_ac4_remove_leaves_no_project_entry_when_nothing_matchable_remains(self):
        self.plant([NBSP + TRUE_COMMAND, FF + TEST_COMMAND])
        result = self.run_cli("--remove", LINT_COMMAND + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.stored_commands())

    def test_ac4_dropped_entry_is_not_resurrected_by_its_stripped_form(self):
        self.plant([NBSP + TRUE_COMMAND])
        self.assertEqual(self.run_cli("--record", LINT_COMMAND + "\n").returncode, 0)
        self.assertEqual(self.stored_commands(), [LINT_COMMAND])
        self.assertEqual(self.run_hook(TRUE_COMMAND), SILENT)

    def test_ac4_refused_run_does_not_drop_them(self):
        self.plant(self.PLANTED)
        self.assert_input_refused("--record", NBSP + "make clean\n", [NBSP + "make clean"])
        self.assertEqual(self.stored_commands(), self.PLANTED)


class TestAc5OtherWhitespaceAndInnerWhitespace(StoreTestCase):
    """AC-5 (FR1): the representative other whitespace characters and an inner one."""

    def test_ac5_stdin_line_with_other_whitespace_at_an_end_refuses_the_input(self):
        for name, char in OTHER_CHARS:
            for where, line in _paddings(char, TEST_COMMAND):
                for mode in ("--record", "--remove"):
                    with self.subTest(char=name, where=where, mode=mode):
                        self.plant([LINT_COMMAND])
                        stdin = BUILD_COMMAND + "\n" + line + "\n"
                        self.assert_input_refused(mode, stdin, [line])

    def test_ac5_stored_entry_with_other_whitespace_is_neither_listed_nor_approved(self):
        for name, char in OTHER_CHARS:
            for where, entry in _paddings(char, TRUE_COMMAND):
                with self.subTest(char=name, where=where):
                    self.plant([entry])
                    self.assert_list([])
                    self.assertEqual(self.run_hook(TRUE_COMMAND), SILENT)

    def test_ac5_other_whitespace_inside_a_value_is_kept(self):
        for name, char in OTHER_CHARS + PRIMARY_CHARS:
            command = "make" + char + "test"
            with self.subTest(char=name):
                if self.store.exists():
                    self.store.unlink()
                result = self.run_cli("--record", command + "\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.stored_commands(), [command])
                self.assert_list([command])
                self.assertEqual(self.run_hook(TEST_COMMAND), SILENT)

    def test_ac5_inner_u00a0_is_recorded_and_listed_as_it_is_and_does_not_approve_make_test(self):
        result = self.run_cli("--record", INNER_NBSP_COMMAND + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(_lines(result.stdout)[1:], ["approved: " + INNER_NBSP_COMMAND])
        self.assertEqual(self.stored_commands(), [INNER_NBSP_COMMAND])
        self.assert_list([INNER_NBSP_COMMAND])
        self.assertEqual(self.run_hook(TEST_COMMAND), SILENT)
        self.assertEqual(self.run_hook(INNER_NBSP_COMMAND), ALLOW)

    def test_ac5_remove_of_make_test_does_not_remove_the_inner_u00a0_entry(self):
        self.plant([INNER_NBSP_COMMAND, TEST_COMMAND])
        self.assertEqual(self.run_cli("--remove", TEST_COMMAND + "\n").returncode, 0)
        self.assertEqual(self.stored_commands(), [INNER_NBSP_COMMAND])


def _imported_top_level_modules(source):
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def _executable_text_fragments(source):
    """Identifiers and string literals of the module, docstrings excluded."""
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    fragments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                fragments.append(node.value)
        elif isinstance(node, ast.Name):
            fragments.append(node.id)
        elif isinstance(node, ast.Attribute):
            fragments.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            fragments.append(node.name)
        elif isinstance(node, ast.arg):
            fragments.append(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            fragments.append(node.arg)
        elif isinstance(node, ast.alias):
            fragments.append(node.name)
    return fragments


def _load_guard_namespace():
    """The module's top-level names, executed from source (writes no bytecode)."""
    source = GUARD_PATH.read_text(encoding="utf-8")
    namespace = {"__name__": "bash_guard_under_test", "__file__": str(GUARD_PATH)}
    exec(compile(source, str(GUARD_PATH), "exec"), namespace)
    return namespace


def _all_whitespace_characters():
    return [chr(i) for i in range(sys.maxunicode + 1) if chr(i).isspace()]


class TestAc6ModuleContract(unittest.TestCase):
    """AC-6 (NFR1, NFR2, NFR3) and the C2 helper contract."""

    @classmethod
    def setUpClass(cls):
        cls.source = GUARD_PATH.read_text(encoding="utf-8")
        cls.namespace = _load_guard_namespace()
        cls.tree = ast.parse(cls.source)

    def test_ac6_guard_imports_only_standard_library_modules(self):
        imported = _imported_top_level_modules(self.source)
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_ac6_this_module_imports_only_standard_library_modules(self):
        imported = _imported_top_level_modules(Path(__file__).read_text(encoding="utf-8"))
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_ac6_guard_executable_text_has_no_status_substring(self):
        offenders = [f for f in _executable_text_fragments(self.source) if "status" in f]
        self.assertEqual(offenders, [])

    def test_ac6_trim_helpers_are_defined_once_between_strip_yaml_quotes_and_declared_commands(self):
        names = [
            node.name for node in self.tree.body if isinstance(node, ast.FunctionDef)
        ]
        for name in ("trim_blanks", "is_matchable"):
            self.assertEqual(names.count(name), 1, name)
        start = names.index("strip_yaml_quotes")
        self.assertEqual(
            names[start : start + 4],
            ["strip_yaml_quotes", "trim_blanks", "is_matchable", "declared_commands"],
        )

    def test_ac6_trim_helper_names_and_docstrings_have_no_status_substring(self):
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in ("trim_blanks", "is_matchable"):
                text = node.name + "\n" + (ast.get_docstring(node) or "")
                self.assertNotIn("status", text.lower(), node.name)

    def test_ac6_trim_blanks_removes_spaces_and_tabs_only(self):
        trim = self.namespace["trim_blanks"]
        self.assertEqual(trim(" \t make test \t "), "make test")
        self.assertEqual(trim(" \t \t"), "")
        self.assertEqual(trim(""), "")
        self.assertEqual(trim("make  test"), "make  test")
        for char in _all_whitespace_characters():
            if char in " \t":
                continue
            value = char + "x" + char
            self.assertEqual(trim(value), value, ascii(char))
            self.assertEqual(trim(" \t" + value + "\t "), value, ascii(char))

    def test_ac6_is_matchable_follows_the_string_whitespace_test_at_both_ends(self):
        matchable = self.namespace["is_matchable"]
        self.assertFalse(matchable(""))
        self.assertTrue(matchable("x"))
        self.assertTrue(matchable("make test"))
        self.assertTrue(matchable(INNER_NBSP_COMMAND))
        for char in _all_whitespace_characters():
            if char in " \t":
                continue
            for value in (char, char + "x", "x" + char, char + "x" + char):
                self.assertFalse(matchable(value), ascii(value))
            self.assertTrue(matchable("x" + char + "x"), ascii(char))

    def test_ac6_approved_for_keeps_only_matchable_trimmed_string_entries(self):
        approved_for = self.namespace["approved_for"]
        store = {
            "projects": {
                "k": {
                    "approved_commands": [
                        " \t" + TEST_COMMAND + "\t",
                        NBSP + LINT_COMMAND,
                        BUILD_COMMAND + CR,
                        INNER_NBSP_COMMAND,
                        "",
                        " \t",
                        NBSP,
                        None,
                        7,
                    ]
                }
            }
        }
        self.assertEqual(approved_for(store, "k"), {TEST_COMMAND, INNER_NBSP_COMMAND})
        self.assertEqual(approved_for(store, "other"), set())
        self.assertEqual(approved_for({"projects": {"k": {}}}, "k"), set())


if __name__ == "__main__":
    unittest.main()
