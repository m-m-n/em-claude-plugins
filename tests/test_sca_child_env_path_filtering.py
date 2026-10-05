"""Tests for sca-absolute-executable-path task0002: the PATH each scanner child
process receives keeps only the caller PATH's absolute entries.

Covers the task's Acceptance Criteria
(feature-docs/sca-absolute-executable-path/tasks/task0002.md):

- AC-1 (FR4): `build_child_env` keeps the absolute entries of the caller's
  PATH as written (duplicates and a trailing directory separator included),
  in their original order, joined with the platform path-list separator;
  relative and empty entries are dropped.
- AC-2 (FR4): the child environment has no PATH key when the caller's PATH
  holds only relative or empty entries, when it is the empty string, and when
  the caller has no PATH.
- AC-3 (FR4, NFR2): every other pass-through key reaches the child with the
  caller's value, and every pin of the ecosystem overrides as before, for
  each ecosystem.
- AC-4 (FR4): through `run_scan`, every recorded npm / cargo-audit /
  pip-audit / govulncheck launch received a PATH equal to the runner's
  absolute entries joined in order.
- AC-5 (NFR1): `build_child_env` is lexical: it returns the same result while
  file opening, filesystem inspection and process launching fail, and its
  parameters stay `ecosystem` and `environ` (the process environment by
  default).
- AC-6 (FR5): the comment above `CHILD_ENV_BASE_KEYS` and the
  `build_child_env` docstring state the PATH rule. The wording is reviewed by
  inspection; the tests only look for the rule's elements and for the
  absence of the old "PATH is carried through unchanged" claim.
- AC-7 (NFR3): this module imports only the standard library. That
  `python3 -m unittest discover -s tests` passes is verified by running it; a
  suite cannot assert its own full-suite outcome.

Design constraint (IMPLEMENTATION.md Conventions, cross-task test
independence): these tests hold whether or not the sibling resolution change
(task0001) is merged. They never assert argv[0], they place no executable
under any relative PATH entry they use, and the run_scan test runs with the
process working directory set to an empty temporary directory.

Harness: this module owns its stubs, following the shape of `ScanHarness` in
`tests/test_sca_scan_unchanged_surfaces.py` without importing it. Each
scanner is an executable stub that appends its tool name, argv, working
directory and launch environment to a record file and prints a well-formed
clean result. The record path is written into the stub itself: the runner
builds each child's environment explicitly, so a variable set by the test
would never reach the child. Every environment variable, module setting and
the process working directory the tests change are restored. The script under
test is loaded by file path (scan-dependencies.py is not a package).
"""

import ast
import contextlib
import importlib.util
import inspect
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_script(name="scan_dependencies_child_env_path_filtering"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

SEP = os.pathsep
ECOSYSTEMS = ("npm", "cargo", "pip", "go")

# The runner keys that reach a child process besides PATH.
OTHER_PASS_THROUGH_KEYS = ("HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "USERPROFILE")


def absolute(*parts):
    """An absolute path built from `parts` below the filesystem root of the
    platform (`/usr/bin` on POSIX)."""
    return os.path.join(os.path.abspath(os.sep), *parts)


def path_list(*entries):
    return SEP.join(entries)


def child_path(environ, ecosystem="npm"):
    """The PATH `build_child_env` hands to a child, or None when it has no
    PATH key."""
    return SCAN.build_child_env({"ecosystem": ecosystem}, environ).get("PATH")


# ---------------------------------------------------------------------------
# AC-1 (FR4): absolute entries survive as written, in order.
# ---------------------------------------------------------------------------


class TestAC1AbsoluteEntriesSurvive(unittest.TestCase):
    def test_ac1_relative_and_empty_entries_are_dropped_and_absolute_ones_joined(self):
        usr_bin = absolute("usr", "bin")
        opt_bin = absolute("opt", "bin")
        caller = path_list("tools", "", usr_bin, "./node_modules/.bin", opt_bin)
        for ecosystem in ECOSYSTEMS:
            with self.subTest(ecosystem=ecosystem):
                self.assertEqual(
                    child_path({"PATH": caller}, ecosystem), path_list(usr_bin, opt_bin)
                )

    def test_ac1_a_duplicated_absolute_entry_keeps_every_original_position(self):
        usr_bin = absolute("usr", "bin")
        opt_bin = absolute("opt", "bin")
        caller = path_list(usr_bin, "tools", opt_bin, "", usr_bin)
        self.assertEqual(
            child_path({"PATH": caller}), path_list(usr_bin, opt_bin, usr_bin)
        )

    def test_ac1_an_absolute_entry_ending_in_a_separator_is_kept_unchanged(self):
        with_separator = absolute("opt", "tools") + os.sep
        usr_bin = absolute("usr", "bin")
        caller = path_list("rel", with_separator, usr_bin)
        self.assertEqual(
            child_path({"PATH": caller}), path_list(with_separator, usr_bin)
        )

    def test_ac1_the_duplicate_and_the_trailing_separator_survive_together(self):
        usr_bin = absolute("usr", "bin")
        with_separator = absolute("opt", "tools") + os.sep
        caller = path_list(
            usr_bin, with_separator, "tools", usr_bin, "", with_separator, "./x"
        )
        self.assertEqual(
            child_path({"PATH": caller}),
            path_list(usr_bin, with_separator, usr_bin, with_separator),
        )

    def test_ac1_the_original_order_is_kept_not_sorted(self):
        entries = [absolute("zeta"), absolute("alpha"), absolute("mid", "dir")]
        caller = path_list(entries[0], "relative", entries[1], "", entries[2])
        self.assertEqual(child_path({"PATH": caller}), path_list(*entries))

    def test_ac1_an_absolute_entry_is_not_normalized(self):
        entries = [
            absolute("usr", "..", "usr", "bin"),
            absolute("usr", "", "bin"),
            absolute("usr", "bin", "."),
        ]
        caller = path_list("rel", *entries)
        self.assertEqual(child_path({"PATH": caller}), path_list(*entries))

    def test_ac1_a_home_shorthand_and_a_variable_reference_are_relative_entries(self):
        usr_bin = absolute("usr", "bin")
        caller = path_list("~/bin", "$HOME/bin", usr_bin)
        self.assertEqual(child_path({"PATH": caller}), usr_bin)

    def test_ac1_an_all_absolute_path_is_unchanged(self):
        caller = path_list(absolute("usr", "bin"), absolute("opt", "bin"))
        self.assertEqual(child_path({"PATH": caller}), caller)

    def test_ac1_a_single_surviving_entry_has_no_separator(self):
        usr_bin = absolute("usr", "bin")
        self.assertEqual(child_path({"PATH": path_list("tools", usr_bin, "")}), usr_bin)


# ---------------------------------------------------------------------------
# AC-2 (FR4): no PATH key when nothing absolute remains.
# ---------------------------------------------------------------------------


class TestAC2NoPathKeyWhenNoEntrySurvives(unittest.TestCase):
    def test_ac2_a_path_of_only_relative_or_empty_entries_is_left_out(self):
        caller = path_list("tools", "./node_modules/.bin", ".", "", "~/bin")
        for ecosystem in ECOSYSTEMS:
            with self.subTest(ecosystem=ecosystem):
                env = SCAN.build_child_env({"ecosystem": ecosystem}, {"PATH": caller})
                self.assertNotIn("PATH", env)

    def test_ac2_a_path_of_only_separators_is_left_out(self):
        env = SCAN.build_child_env({"ecosystem": "go"}, {"PATH": SEP * 3})
        self.assertNotIn("PATH", env)

    def test_ac2_an_empty_path_is_left_out(self):
        for ecosystem in ECOSYSTEMS:
            with self.subTest(ecosystem=ecosystem):
                env = SCAN.build_child_env({"ecosystem": ecosystem}, {"PATH": ""})
                self.assertNotIn("PATH", env)

    def test_ac2_an_environ_without_path_has_no_path_key(self):
        for ecosystem in ECOSYSTEMS:
            with self.subTest(ecosystem=ecosystem):
                env = SCAN.build_child_env({"ecosystem": ecosystem}, {"HOME": "/h"})
                self.assertNotIn("PATH", env)

    def test_ac2_the_other_keys_are_kept_when_path_is_left_out(self):
        environ = {"PATH": path_list("tools", ""), "HOME": "/reviewer/home"}
        env = SCAN.build_child_env({"ecosystem": "cargo"}, environ)
        self.assertEqual(env, {"HOME": "/reviewer/home"})

    def test_ac2_the_pins_still_apply_when_path_is_left_out(self):
        env = SCAN.build_child_env({"ecosystem": "go"}, {"PATH": "tools"})
        self.assertEqual(env, dict(SCAN.ECOSYSTEM_ENV_PINS["go"]))


# ---------------------------------------------------------------------------
# AC-3 (FR4, NFR2): the other pass-through keys and the pins are as before.
# ---------------------------------------------------------------------------


class TestAC3OtherKeysAndPinsAreUnchanged(unittest.TestCase):
    def runner_environ(self):
        environ = {key: f"runner-{key}" for key in OTHER_PASS_THROUGH_KEYS}
        environ["PATH"] = path_list(absolute("usr", "bin"), "tools", absolute("opt", "bin"))
        # Variables that must never reach a child: some of them for the very
        # settings the pins fix, to show that the pin wins.
        environ.update({
            "NPM_TOKEN": "decoy-token",
            "HTTPS_PROXY": "http://decoy.invalid:3128",
            "npm_config_registry": "https://decoy.invalid/",
            "PIP_INDEX_URL": "https://decoy.invalid/simple/",
            "GOFLAGS": "-mod=mod",
            "GOPROXY": "https://decoy.invalid",
        })
        return environ

    def test_ac3_every_ecosystem_is_covered(self):
        self.assertEqual(sorted(SCAN.ECOSYSTEM_ENV_PINS), sorted(ECOSYSTEMS))

    def test_ac3_the_other_pass_through_keys_reach_the_child_with_the_callers_values(self):
        environ = self.runner_environ()
        for ecosystem in ECOSYSTEMS:
            env = SCAN.build_child_env({"ecosystem": ecosystem}, environ)
            for key in OTHER_PASS_THROUGH_KEYS:
                with self.subTest(ecosystem=ecosystem, key=key):
                    self.assertEqual(env[key], environ[key])

    def test_ac3_every_pin_of_the_ecosystem_overrides_the_callers_value(self):
        environ = self.runner_environ()
        for ecosystem in ECOSYSTEMS:
            env = SCAN.build_child_env({"ecosystem": ecosystem}, environ)
            for key, value in SCAN.ECOSYSTEM_ENV_PINS[ecosystem].items():
                with self.subTest(ecosystem=ecosystem, key=key):
                    self.assertEqual(env[key], value)

    def test_ac3_the_child_environment_is_the_other_keys_plus_the_filtered_path_plus_the_pins(self):
        environ = self.runner_environ()
        for ecosystem in ECOSYSTEMS:
            with self.subTest(ecosystem=ecosystem):
                expected = {key: environ[key] for key in OTHER_PASS_THROUGH_KEYS}
                expected["PATH"] = path_list(absolute("usr", "bin"), absolute("opt", "bin"))
                expected.update(SCAN.ECOSYSTEM_ENV_PINS[ecosystem])
                self.assertEqual(
                    SCAN.build_child_env({"ecosystem": ecosystem}, environ), expected
                )

    def test_ac3_no_variable_outside_the_pass_through_keys_and_pins_reaches_the_child(self):
        environ = self.runner_environ()
        allowed = set(OTHER_PASS_THROUGH_KEYS) | {"PATH"}
        for ecosystem in ECOSYSTEMS:
            with self.subTest(ecosystem=ecosystem):
                env = SCAN.build_child_env({"ecosystem": ecosystem}, environ)
                allowed_here = allowed | set(SCAN.ECOSYSTEM_ENV_PINS[ecosystem])
                self.assertEqual(sorted(set(env) - allowed_here), [])

    def test_ac3_the_pass_through_key_list_is_unchanged(self):
        self.assertEqual(
            SCAN.CHILD_ENV_BASE_KEYS,
            ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "USERPROFILE"),
        )


# ---------------------------------------------------------------------------
# Shared run_scan fixture: a project root, a stub directory, a record file, a
# temp parent next to the project, a reviewer HOME and an empty directory to
# stand in as the process working directory -- all inside one temporary tree.
# ---------------------------------------------------------------------------

CLEAN_PAYLOADS = {
    "npm": {"vulnerabilities": {}},
    "cargo-audit": {"vulnerabilities": {"found": False, "list": []}},
    "pip-audit": {"dependencies": []},
    "govulncheck": {"config": {"protocol_version": "v1.0.0", "scanner_name": "govulncheck"}},
}

_STUB_SOURCE = '''#!__PYTHON__
import json
import os
import sys

CONFIG = json.loads(__CONFIG__)


def launch_environment():
    # The environment exactly as the scanner runner handed it over. The
    # interpreter may add variables of its own while starting up (a locale
    # coercion variable), so /proc is read where it exists.
    try:
        with open("/proc/self/environ", "rb") as handle:
            raw = handle.read()
    except OSError:
        return dict(os.environ)
    env = {}
    for item in raw.split(b"\\0"):
        if item:
            key, _, value = item.partition(b"=")
            env[os.fsdecode(key)] = os.fsdecode(value)
    return env


with open(CONFIG["record"], "a", encoding="utf-8") as rec:
    rec.write(json.dumps({
        "tool": CONFIG["tool"],
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "env": launch_environment(),
    }) + "\\n")
sys.stdout.write(CONFIG["payload"])
sys.exit(0)
'''


def write_recording_stub(bin_dir, name, record_path, payload):
    """An executable `name` in `bin_dir`: on every launch it appends its tool
    name, argument vector, working directory and launch environment to
    `record_path`, prints `payload` as JSON and exits 0. The shebang is the
    absolute interpreter because the child PATH holds only the entries the
    test lets through."""
    config = {"tool": name, "record": str(record_path), "payload": json.dumps(payload)}
    source = _STUB_SOURCE.replace("__PYTHON__", sys.executable).replace(
        "__CONFIG__", repr(json.dumps(config))
    )
    path = Path(bin_dir) / name
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


class ScanHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.root = self.base / "project"
        self.bin_dir = self.base / "bin"
        self.extra_dir = self.base / "extra-bin"
        self.records_dir = self.base / "records"
        self.temp_parent = self.base / "tmp"
        self.home = self.base / "reviewer-home"
        self.empty_cwd = self.base / "empty-cwd"
        for directory in (
            self.root, self.bin_dir, self.extra_dir, self.records_dir,
            self.temp_parent, self.home, self.empty_cwd,
        ):
            directory.mkdir()
        self.record_path = self.records_dir / "calls.jsonl"
        # The process working directory is an empty directory, so a relative
        # or empty PATH entry resolves to nothing wherever the tests run. It
        # is restored before the temporary tree is removed.
        previous_cwd = os.getcwd()
        os.chdir(self.empty_cwd)
        self.addCleanup(os.chdir, previous_cwd)

    # -- fixtures ---------------------------------------------------------

    def write(self, rel, data="{}\n"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    def all_four_projects(self):
        self.write("package.json")
        self.write("package-lock.json")
        self.write("Cargo.toml", "[dependencies]\n")
        self.write("Cargo.lock", "# lock\n")
        self.write("go.mod", "module example.invalid/demo\n")
        self.write("requirements.txt", "django==3.2.0\n")

    def install(self, name):
        return write_recording_stub(
            self.bin_dir, name, self.record_path, CLEAN_PAYLOADS[name]
        )

    # -- the runner's environment -----------------------------------------

    def runner_path(self):
        """Relative and empty entries around, and between, the absolute
        recording-stub directory and a second absolute directory (kept with a
        trailing separator). No executable is placed under any relative
        entry."""
        return path_list(
            "tools",
            "",
            str(self.bin_dir),
            "./node_modules/.bin",
            ".",
            str(self.extra_dir) + os.sep,
            "~/bin",
        )

    def expected_child_path(self):
        return path_list(str(self.bin_dir), str(self.extra_dir) + os.sep)

    def runner_environment(self):
        return {
            "PATH": self.runner_path(),
            "HOME": str(self.home),
            "TMPDIR": str(self.temp_parent),
            "TEMP": str(self.temp_parent),
            "TMP": str(self.temp_parent),
            "SYSTEMROOT": "/nonexistent/systemroot",
            "USERPROFILE": str(self.home),
        }

    # -- running ----------------------------------------------------------

    def scan(self, changed_files):
        with mock.patch.dict(os.environ, self.runner_environment(), clear=True), \
                mock.patch.object(tempfile, "tempdir", str(self.temp_parent)):
            return SCAN.run_scan(self.root, changed_files, SCAN.DEFAULT_REGISTRY_PATH)

    def launches(self):
        if not self.record_path.exists():
            return []
        text = self.record_path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# AC-4 (FR4): through run_scan, every scanner launch gets the filtered PATH.
# ---------------------------------------------------------------------------


class TestAC4RunScanChildrenReceiveTheFilteredPath(ScanHarness):
    def test_ac4_every_recorded_launch_received_the_runners_absolute_entries_in_order(self):
        self.all_four_projects()
        for tool in ("npm", "cargo-audit", "pip-audit", "govulncheck"):
            self.install(tool)
        result = self.scan(["package.json", "Cargo.toml", "requirements.txt", "go.mod"])
        self.assertFalse(result["skipped"], result)
        calls = self.launches()
        self.assertEqual(
            sorted(call["tool"] for call in calls),
            ["cargo-audit", "govulncheck", "npm", "pip-audit"],
        )
        for call in calls:
            with self.subTest(tool=call["tool"]):
                self.assertEqual(call["env"]["PATH"], self.expected_child_path())

    def test_ac4_no_launch_received_a_relative_or_empty_path_entry(self):
        self.all_four_projects()
        for tool in ("npm", "cargo-audit", "pip-audit", "govulncheck"):
            self.install(tool)
        self.scan(["package.json", "Cargo.toml", "requirements.txt", "go.mod"])
        calls = self.launches()
        self.assertEqual(len(calls), 4, calls)
        for call in calls:
            entries = call["env"]["PATH"].split(SEP)
            with self.subTest(tool=call["tool"]):
                self.assertTrue(entries)
                for entry in entries:
                    self.assertTrue(
                        entry and os.path.isabs(entry),
                        f"PATH entry {entry!r} is relative or empty",
                    )


# ---------------------------------------------------------------------------
# AC-5 (NFR1): build_child_env is lexical.
# ---------------------------------------------------------------------------


class TestAC5BuildChildEnvIsLexical(unittest.TestCase):
    PATCH_TARGETS = (
        "builtins.open",
        "io.open",
        "os.open",
        "os.stat",
        "os.lstat",
        "os.scandir",
        "os.listdir",
        "os.access",
        "os.getcwd",
        "os.path.exists",
        "os.path.isfile",
        "os.path.isdir",
        "os.path.islink",
        "os.path.realpath",
        "pathlib.Path.stat",
        "pathlib.Path.open",
        "shutil.which",
        "os.system",
        "subprocess.Popen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
    )

    @contextlib.contextmanager
    def forbidden_entry_points(self):
        with contextlib.ExitStack() as stack:
            patched = [
                stack.enter_context(
                    mock.patch(target, side_effect=AssertionError(f"{target} called"))
                )
                for target in self.PATCH_TARGETS
            ]
            yield
            called = [
                target for target, patch in zip(self.PATCH_TARGETS, patched)
                if patch.call_count
            ]
        self.assertEqual(called, [])

    def environ(self):
        return {
            "PATH": path_list(
                "tools", "", absolute("usr", "bin"), "./node_modules/.bin", absolute("opt", "bin")
            ),
            "HOME": "/reviewer/home",
            "TMPDIR": "/reviewer/tmp",
            "NPM_TOKEN": "decoy",
        }

    def test_ac5_the_same_result_while_files_the_filesystem_and_processes_are_off_limits(self):
        for ecosystem in ECOSYSTEMS:
            for environ in (self.environ(), {"PATH": "tools"}, {"PATH": ""}, {}):
                with self.subTest(ecosystem=ecosystem, environ=environ):
                    before = SCAN.build_child_env({"ecosystem": ecosystem}, environ)
                    with self.forbidden_entry_points():
                        during = SCAN.build_child_env({"ecosystem": ecosystem}, environ)
                    self.assertEqual(during, before)

    def test_ac5_the_environ_default_is_the_process_environment(self):
        usr_bin = absolute("usr", "bin")
        process_environ = {"PATH": path_list("tools", usr_bin, ""), "HOME": "/process/home"}
        with mock.patch.dict(os.environ, process_environ, clear=True):
            with self.forbidden_entry_points():
                env = SCAN.build_child_env({"ecosystem": "pip"})
        expected = {"PATH": usr_bin, "HOME": "/process/home"}
        expected.update(SCAN.ECOSYSTEM_ENV_PINS["pip"])
        self.assertEqual(env, expected)

    def test_ac5_the_process_environment_with_no_path_gives_a_child_without_path(self):
        with mock.patch.dict(os.environ, {"HOME": "/process/home"}, clear=True):
            env = SCAN.build_child_env({"ecosystem": "cargo"})
        self.assertEqual(env, {"HOME": "/process/home"})

    def test_ac5_the_parameters_stay_ecosystem_and_environ(self):
        parameters = inspect.signature(SCAN.build_child_env).parameters
        self.assertEqual(list(parameters), ["ecosystem", "environ"])
        self.assertIsNot(parameters["environ"].default, inspect.Parameter.empty)

    def test_ac5_the_callers_environ_is_not_modified(self):
        environ = self.environ()
        snapshot = dict(environ)
        SCAN.build_child_env({"ecosystem": "npm"}, environ)
        self.assertEqual(environ, snapshot)


# ---------------------------------------------------------------------------
# AC-6 (FR5): the comment above CHILD_ENV_BASE_KEYS and the build_child_env
# docstring state the PATH rule.
# ---------------------------------------------------------------------------


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text):
    return [s for s in re.split(r"(?<=[.;])\s+", _normalize(text)) if s]


def _comment_above_child_env_base_keys():
    """The comment block directly above the `CHILD_ENV_BASE_KEYS` assignment,
    without the leading `#` marks, whitespace-normalized."""
    lines = SCRIPT_PATH.read_text(encoding="utf-8").splitlines()
    index = next(
        i for i, line in enumerate(lines) if line.startswith("CHILD_ENV_BASE_KEYS =")
    )
    block = []
    i = index - 1
    while i >= 0 and lines[i].startswith("#"):
        block.append(lines[i].lstrip("#"))
        i -= 1
    return _normalize(" ".join(reversed(block)))


def _states_the_path_rule(text):
    """True when one sentence of `text` says that PATH keeps its absolute
    entries and is left out when none remain."""
    return any(
        "PATH" in sentence
        and "absolute" in sentence
        and re.search(r"left out|dropped|omitted|no PATH", sentence)
        for sentence in _sentences(text)
    )


class TestAC6CommentAndDocstringStateThePathRule(unittest.TestCase):
    def test_ac6_the_comment_above_the_key_list_states_the_path_rule(self):
        comment = _comment_above_child_env_base_keys()
        self.assertTrue(comment, "no comment directly above CHILD_ENV_BASE_KEYS")
        self.assertTrue(
            _states_the_path_rule(comment),
            "the comment above CHILD_ENV_BASE_KEYS does not state that PATH keeps "
            "its absolute entries and is left out when none remain",
        )

    def test_ac6_the_comment_no_longer_says_path_is_carried_through_unchanged(self):
        comment = _comment_above_child_env_base_keys()
        for sentence in _sentences(comment):
            if "PATH" in sentence and re.search(r"carried through|unchanged", sentence):
                # A sentence naming PATH next to "unchanged" is allowed only
                # when it is the PATH rule itself or when it sets PATH apart
                # from the keys that are carried through.
                self.assertTrue(
                    "absolute" in sentence
                    or re.search(r"(but|except|other than|besides) PATH", sentence),
                    f"the comment still carries PATH through unchanged: {sentence!r}",
                )

    def test_ac6_the_docstring_states_the_path_rule(self):
        docstring = SCAN.build_child_env.__doc__
        self.assertTrue(docstring, "build_child_env has no docstring")
        self.assertTrue(
            _states_the_path_rule(docstring),
            "the build_child_env docstring does not state that PATH keeps its "
            "absolute entries and is left out when none remain",
        )


# ---------------------------------------------------------------------------
# AC-7 (NFR3): own module stdlib only.
# ---------------------------------------------------------------------------


class TestAC7OwnModuleStdlibOnly(unittest.TestCase):
    def test_ac7_only_standard_library_imports(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
