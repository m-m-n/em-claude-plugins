"""Subprocess-driven argument tests for task0002: both `run_codex_exec.sh`
wrappers register the interactive-guard PreToolUse hook on every
`codex exec` launch
(feature-docs/codex-interactive-guard-hook/tasks/task0002.md).

Covers task0002 Acceptance Criteria:

- AC-1 (FR1, FR4): em-workflow's default path, readonly and readwrite: the
  stub-recorded argv carries `--dangerously-bypass-hook-trust` and one `-c`
  value starting with `hooks.PreToolUse=`. That value parses as TOML into a
  one-element array (matcher `Bash`, one command hook), and the command,
  executed the way Codex 0.160.0 executes it (through a POSIX shell), runs
  `python3` on the absolute path of
  em-workflow/scripts/codex-hook-interactive-guard.py in the tree under test.
- AC-2 (FR2, FR4): the same for `--litellm MODEL`, plus `-p litellm -m MODEL`
  as four adjacent argv elements and no `--ignore-user-config`.
- AC-3 (FR3, FR4): the same for em-review's wrapper, with the command naming
  em-review/scripts/codex-hook-interactive-guard.py.
- AC-4 (TM-3): a copy of a plugin's scripts directory under a path with a
  space and a single quote (and a path with every shell/TOML metacharacter)
  still yields a `-c` value that parses as TOML and a command that resolves
  to exactly the copied directory's hook path. Both wrappers.
- AC-5 (TM-4, NFR5): the bypass flag only ever appears alongside the
  config-isolation flags each launch carries today; the reasoning-effort and
  otel `-c` overrides are still present.
- AC-6 (NFR3): one stub invocation per wrapper run, no `2>&1` in the
  em-workflow wrapper, usage text and accepted flags unchanged, em-review's
  wrapper has `codex exec` exactly once across non-comment lines.
- AC-7 (NFR4, FR14): every wrapper run goes through one harness that puts a
  stub `codex` first on PATH and points HOME at a temporary directory; real
  Codex is never reached.

Test Notes this module follows:

- The module never asserts that the hook file exists or how it behaves: it
  is task0001's deliverable and absent from this task's worktree
  (IMPLEMENTATION.md D2). Only the path the `-c` value names is pinned.
- The wrapper reads `../references/codex-cli.yaml` relative to its own
  location, so the AC-4 copies carry that one file next to the copied
  `scripts/` directory; nothing else outside the copy is needed.
- Nothing under em-workflow/ or em-review/ is imported: the wrappers are
  run as separate processes, so no bytecode cache lands in a plugin
  directory (IMPLEMENTATION.md Conventions).

Non-vacuity: the hook-registration checker and the adjacency matcher each
carry negative proofs against forged argv, in the style of the neighbouring
wrapper test modules.
"""

import ast
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / "em-workflow" / "scripts"
REVIEW_SCRIPTS_DIR = REPO_ROOT / "em-review" / "scripts"
WRAPPER_NAME = "run_codex_exec.sh"
HOOK_NAME = "codex-hook-interactive-guard.py"
CONFIG_RELATIVE = Path("references") / "codex-cli.yaml"

BYPASS_FLAG = "--dangerously-bypass-hook-trust"
HOOK_KEY_PREFIX = "hooks.PreToolUse="
MODEL = "test-model-xyz"
MODES = ("readonly", "readwrite")

WORKFLOW_USAGE = (
    'Usage: run_codex_exec.sh <readonly|readwrite> [-C DIR] '
    '[--output-schema F] [--litellm MODEL] "prompt"'
)
REVIEW_USAGE = (
    'Usage: run_codex_exec.sh <readonly|readwrite> [-C DIR] '
    '[--output-schema F] "prompt"'
)

# Launch paths: (label, plugin scripts dir, wrapper-specific args placed
# between the mode and the prompt, whether the launch carries
# --ignore-user-config today).
DEFAULT_PATH = ("workflow-default", WORKFLOW_SCRIPTS_DIR, [], True)
LITELLM_PATH = ("workflow-litellm", WORKFLOW_SCRIPTS_DIR, ["--litellm", MODEL], False)
REVIEW_PATH = ("review", REVIEW_SCRIPTS_DIR, [], True)
ALL_PATHS = (DEFAULT_PATH, LITELLM_PATH, REVIEW_PATH)

# The stub codex records its argv as one JSON line and exits successfully.
CODEX_STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import sys

with open(os.environ["CODEX_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:], "home": os.environ.get("HOME")}) + "\\n")
print("STUB_ANSWER: ok")
sys.exit(0)
"""

# Stands in for `python3` when a recorded hook command is executed through
# a shell: it records the arguments it receives. The interpreter named in
# the shebang is the running one, so the stub never resolves back to itself.
PYTHON_RECORDER_SOURCE = """#!{interpreter}
import json
import os
import sys

with open(os.environ["HOOK_RECORD"], "w", encoding="utf-8") as fh:
    json.dump(sys.argv[1:], fh)
"""

# Directory names for AC-4. The first is the plan's case (a space and a
# single quote); the others carry every character that matters to the TOML
# basic-string layer or to a POSIX shell.
SPACE_AND_QUOTE_NAME = "sp ace's dir"
HOSTILE_NAMES = (
    'we ird\'q"d\\b$HOME`id`;x&y|z<w>v*u?t(s)#r!q~p',
    "tab\there",
    "new\nline",
    "日本語 ディレクトリ",
)


def _write_executable(path, source):
    path.write_text(source, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _read_log(log_path):
    records = []
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def _run_wrapper(wrapper_path, wrapper_args, extra_env=None, cwd=None, timeout=30):
    """Runs a wrapper as a subprocess with a stub `codex` first on PATH and
    an isolated HOME (AC-7). Returns (CompletedProcess, list of recorded
    launches). The caller's working directory is a fresh temporary
    directory unless `cwd` is given, so a path derived from the working
    directory could not be mistaken for one derived from the wrapper."""
    with tempfile.TemporaryDirectory() as work_s:
        work = Path(work_s)
        stub_dir = work / "stub-bin"
        stub_dir.mkdir()
        _write_executable(stub_dir / "codex", CODEX_STUB_SOURCE)
        log_path = work / "stub.log"
        fake_home = work / "home"
        fake_home.mkdir()
        caller_cwd = work / "caller-cwd"
        caller_cwd.mkdir()

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        env["HOME"] = str(fake_home)
        env["CODEX_STUB_LOG"] = str(log_path)
        env.pop("CODEX_OTLP_ENDPOINT", None)
        env.pop("CODEX_HOME", None)
        if extra_env:
            env.update(extra_env)

        # AC-7: the `codex` the wrapper will find is the stub, never a real
        # one, and HOME is a directory this run owns.
        resolved = shutil.which("codex", path=env["PATH"])
        assert resolved == str(stub_dir / "codex"), resolved
        assert Path(env["HOME"]).parent == work

        proc = subprocess.run(
            ["bash", str(wrapper_path), *wrapper_args],
            env=env,
            cwd=str(cwd if cwd is not None else caller_cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc, _read_log(log_path)


def _launch_argv(wrapper_path, mode, path_args, extra_env=None, prompt="do the thing"):
    """Runs one launch and returns the single recorded argv (the wrapper run
    must have exited 0 and invoked the stub exactly once)."""
    proc, launches = _run_wrapper(
        wrapper_path, [mode, *path_args, prompt], extra_env=extra_env
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"wrapper exited {proc.returncode}: stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    if len(launches) != 1:
        raise AssertionError(f"expected exactly one stub invocation, got {launches}")
    return launches[0]["argv"]


def _find_adjacent(argv, expected):
    """True exactly when `expected` occurs in `argv` as adjacent elements,
    in order. An empty `expected` is refused (it would match vacuously)."""
    expected = list(expected)
    if not expected:
        raise ValueError("expected sequence must not be empty")
    width = len(expected)
    return any(
        list(argv[start:start + width]) == expected
        for start in range(len(argv) - width + 1)
    )


def _hook_c_values(argv):
    """Every value passed as `-c <value>` that starts with the hook key."""
    return [
        argv[i + 1]
        for i in range(len(argv) - 1)
        if argv[i] == "-c" and argv[i + 1].startswith(HOOK_KEY_PREFIX)
    ]


def _run_command_through_shell(command, shell, tmp_root):
    """Executes a recorded hook command the way Codex 0.160.0 does (through
    a POSIX shell), with a recorder in place of `python3`. Returns the
    arguments the interpreter received."""
    bin_dir = Path(tmp_root) / f"python-bin-{shell}"
    bin_dir.mkdir(exist_ok=True)
    _write_executable(
        bin_dir / "python3",
        PYTHON_RECORDER_SOURCE.format(interpreter=sys.executable),
    )
    record = Path(tmp_root) / f"record-{shell}.json"
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["HOOK_RECORD"] = str(record)
    proc = subprocess.run(
        [shell, "-c", command], env=env, capture_output=True, text=True, timeout=30
    )
    if proc.returncode != 0 or not record.is_file():
        raise AssertionError(
            f"{shell} -c {command!r} did not run the interpreter: "
            f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    return json.loads(record.read_text(encoding="utf-8"))


def _available_shells():
    shells = ["sh", "bash"]
    if shutil.which("zsh"):
        shells.append("zsh")
    return shells


def _assert_hook_registered(argv, expected_hook_path):
    """The hook-registration checker (AC-1 / AC-2 / AC-3 / AC-4). Raises
    with a descriptive message rather than returning a bool."""
    if argv.count(BYPASS_FLAG) != 1:
        raise AssertionError(f"{BYPASS_FLAG} must appear exactly once in {argv!r}")
    values = _hook_c_values(argv)
    if len(values) != 1:
        raise AssertionError(
            f"expected exactly one `-c {HOOK_KEY_PREFIX}...` pair, found {len(values)} in {argv!r}"
        )
    parsed = tomllib.loads(values[0])
    groups = parsed["hooks"]["PreToolUse"]
    if not isinstance(groups, list) or len(groups) != 1:
        raise AssertionError(f"PreToolUse must be a one-element array: {groups!r}")
    group = groups[0]
    if group.get("matcher") != "Bash":
        raise AssertionError(f"matcher must be 'Bash': {group!r}")
    hooks = group.get("hooks")
    if not isinstance(hooks, list) or len(hooks) != 1:
        raise AssertionError(f"matcher group must hold exactly one hook: {group!r}")
    hook = hooks[0]
    if hook.get("type") != "command" or not isinstance(hook.get("command"), str):
        raise AssertionError(f"hook must be a command-type hook: {hook!r}")
    if not os.path.isabs(expected_hook_path):
        raise AssertionError(f"expected hook path is not absolute: {expected_hook_path!r}")
    with tempfile.TemporaryDirectory() as tmp_root:
        for shell in _available_shells():
            received = _run_command_through_shell(hook["command"], shell, tmp_root)
            if received != [expected_hook_path]:
                raise AssertionError(
                    f"under {shell}, the command {hook['command']!r} passed "
                    f"{received!r} to python3, expected exactly "
                    f"{[expected_hook_path]!r}"
                )
    return hook["command"]


class TestHookRegistrationOnEveryLaunch(unittest.TestCase):
    """AC-1 / AC-2 / AC-3: the hook registration and the bypass flag reach
    every launch path in both modes."""

    def _check(self, launch_path, mode):
        label, scripts_dir, path_args, _ = launch_path
        wrapper = scripts_dir / WRAPPER_NAME
        argv = _launch_argv(wrapper, mode, path_args)
        command = _assert_hook_registered(argv, str(scripts_dir / HOOK_NAME))
        # The interpreter is Python 3 (the first word of the command).
        self.assertEqual(shlex.split(command)[0], "python3", f"{label}/{mode}")
        return argv

    def test_ac1_workflow_default_path_readonly(self):
        self._check(DEFAULT_PATH, "readonly")

    def test_ac1_workflow_default_path_readwrite(self):
        self._check(DEFAULT_PATH, "readwrite")

    def test_ac2_workflow_litellm_path_readonly(self):
        argv = self._check(LITELLM_PATH, "readonly")
        self.assertTrue(_find_adjacent(argv, ["-p", "litellm", "-m", MODEL]))
        self.assertNotIn("--ignore-user-config", argv)

    def test_ac2_workflow_litellm_path_readwrite(self):
        argv = self._check(LITELLM_PATH, "readwrite")
        self.assertTrue(_find_adjacent(argv, ["-p", "litellm", "-m", MODEL]))
        self.assertNotIn("--ignore-user-config", argv)

    def test_ac3_review_readonly(self):
        self._check(REVIEW_PATH, "readonly")

    def test_ac3_review_readwrite(self):
        self._check(REVIEW_PATH, "readwrite")

    def test_hook_path_does_not_depend_on_the_callers_working_directory(self):
        # _run_wrapper starts every wrapper in a fresh temporary directory;
        # here the caller instead stands inside another plugin's directory.
        for launch_path in ALL_PATHS:
            label, scripts_dir, path_args, _ = launch_path
            with self.subTest(path=label):
                other = REVIEW_SCRIPTS_DIR if scripts_dir == WORKFLOW_SCRIPTS_DIR else WORKFLOW_SCRIPTS_DIR
                proc, launches = _run_wrapper(
                    scripts_dir / WRAPPER_NAME,
                    ["readonly", *path_args, "prompt"],
                    cwd=other,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(launches), 1)
                _assert_hook_registered(
                    launches[0]["argv"], str(scripts_dir / HOOK_NAME)
                )

    def test_each_plugin_references_only_its_own_hook_copy(self):
        for launch_path in ALL_PATHS:
            label, scripts_dir, path_args, _ = launch_path
            with self.subTest(path=label):
                argv = _launch_argv(scripts_dir / WRAPPER_NAME, "readonly", path_args)
                other = REVIEW_SCRIPTS_DIR if scripts_dir == WORKFLOW_SCRIPTS_DIR else WORKFLOW_SCRIPTS_DIR
                values = _hook_c_values(argv)
                self.assertEqual(len(values), 1, argv)
                self.assertNotIn(str(other), values[0])


class TestHookPathSurvivesHostilePlugins(unittest.TestCase):
    """AC-4 (TM-3): a copy of the plugin's scripts directory under an
    awkward path still resolves back to exactly the copied hook path."""

    def _copy_plugin(self, scripts_dir, root, dir_name):
        plugin_copy = Path(root) / dir_name
        shutil.copytree(
            scripts_dir,
            plugin_copy / "scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (plugin_copy / "references").mkdir()
        shutil.copy(
            scripts_dir.parent / CONFIG_RELATIVE, plugin_copy / CONFIG_RELATIVE
        )
        return plugin_copy / "scripts"

    def _check_copy(self, launch_path, dir_name):
        label, scripts_dir, path_args, _ = launch_path
        with tempfile.TemporaryDirectory() as root_s:
            # realpath: the wrapper reports the directory it was started
            # from, and the comparison below is about the name, not about
            # symlinks in the temporary root.
            root = os.path.realpath(root_s)
            copied_scripts = self._copy_plugin(scripts_dir, root, dir_name)
            proc, launches = _run_wrapper(
                copied_scripts / WRAPPER_NAME, ["readonly", *path_args, "prompt"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(len(launches), 1, f"{label} in {dir_name!r}")
            expected = str(copied_scripts / HOOK_NAME)
            self.assertIn(dir_name, expected)
            _assert_hook_registered(launches[0]["argv"], expected)

    def test_space_and_single_quote_in_path_for_every_launch_path(self):
        for launch_path in ALL_PATHS:
            with self.subTest(path=launch_path[0]):
                self._check_copy(launch_path, SPACE_AND_QUOTE_NAME)

    def test_every_shell_and_toml_metacharacter_in_path(self):
        for launch_path in (DEFAULT_PATH, REVIEW_PATH):
            for name in HOSTILE_NAMES:
                with self.subTest(path=launch_path[0], name=name):
                    self._check_copy(launch_path, name)


class TestConfigIsolationIsPreserved(unittest.TestCase):
    """AC-5 (TM-4, NFR5): the bypass flag never travels without the
    config-isolation flags the launch carries today, and the existing -c
    overrides are intact."""

    def test_bypass_flag_only_alongside_the_launchs_isolation_flags(self):
        for label, scripts_dir, path_args, has_ignore_user_config in ALL_PATHS:
            for mode in MODES:
                with self.subTest(path=label, mode=mode):
                    argv = _launch_argv(scripts_dir / WRAPPER_NAME, mode, path_args)
                    self.assertIn(BYPASS_FLAG, argv)
                    self.assertIn("--ignore-rules", argv)
                    if has_ignore_user_config:
                        self.assertIn("--ignore-user-config", argv)
                    else:
                        self.assertNotIn("--ignore-user-config", argv)

    def test_reasoning_effort_override_is_still_present_in_readonly(self):
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            with self.subTest(path=label):
                argv = _launch_argv(scripts_dir / WRAPPER_NAME, "readonly", path_args)
                self.assertTrue(
                    _find_adjacent(argv, ["-c", 'model_reasoning_effort="xhigh"']), argv
                )

    def test_otel_overrides_are_still_present_next_to_the_hook(self):
        endpoint = "http://127.0.0.1:4318/v1/logs"
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            for mode in MODES:
                with self.subTest(path=label, mode=mode):
                    argv = _launch_argv(
                        scripts_dir / WRAPPER_NAME,
                        mode,
                        path_args,
                        extra_env={"CODEX_OTLP_ENDPOINT": endpoint},
                    )
                    self.assertTrue(_find_adjacent(argv, ["-c", 'otel.environment="local"']))
                    self.assertTrue(
                        _find_adjacent(
                            argv,
                            [
                                "-c",
                                'otel.exporter={otlp-http={endpoint="'
                                + endpoint
                                + '",protocol="binary"}}',
                            ],
                        )
                    )
                    _assert_hook_registered(argv, str(scripts_dir / HOOK_NAME))

    def test_litellm_profile_words_stay_adjacent_with_every_extra_flag(self):
        # The hook arguments must never land between `-p litellm -m MODEL`,
        # whatever other optional flags and overrides are in play.
        for mode in MODES:
            with self.subTest(mode=mode):
                argv = _launch_argv(
                    WORKFLOW_SCRIPTS_DIR / WRAPPER_NAME,
                    mode,
                    ["-C", "/tmp/somewhere", "--output-schema", "schema.json",
                     "--litellm", MODEL],
                    extra_env={"CODEX_OTLP_ENDPOINT": "http://127.0.0.1:4318/v1/logs"},
                )
                self.assertTrue(_find_adjacent(argv, ["-p", "litellm", "-m", MODEL]), argv)
                self.assertNotIn("--ignore-user-config", argv)
                self.assertIn(BYPASS_FLAG, argv)

    def test_the_prompt_is_still_the_last_argument(self):
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            with self.subTest(path=label):
                argv = _launch_argv(
                    scripts_dir / WRAPPER_NAME, "readwrite", path_args, prompt="PROMPT-TEXT"
                )
                self.assertEqual(argv[-1], "PROMPT-TEXT")


class TestWrapperContractIsUnchanged(unittest.TestCase):
    """AC-6 (NFR3): the launch count, the usage surface and the text-level
    pins hold on their own in this module."""

    def test_every_wrapper_run_invokes_the_stub_exactly_once(self):
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            for mode in MODES:
                with self.subTest(path=label, mode=mode):
                    proc, launches = _run_wrapper(
                        scripts_dir / WRAPPER_NAME, [mode, *path_args, "prompt"]
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(len(launches), 1, launches)

    def test_em_workflow_wrapper_text_has_no_combined_stream_redirect(self):
        text = (WORKFLOW_SCRIPTS_DIR / WRAPPER_NAME).read_text(encoding="utf-8")
        self.assertNotIn("2>&1", text)

    def test_em_review_wrapper_keeps_its_one_existing_combined_redirect(self):
        # AC-6 words the `2>&1` pin as "neither wrapper", but em-review's
        # launch has always been `... </dev/null 2>&1 || exit_code=$?`, and
        # no existing test or requirement (NFR3 names the em-workflow
        # wrapper only) asks for it to change. This pins that the hook
        # registration neither added a second redirect nor altered that one.
        text = (REVIEW_SCRIPTS_DIR / WRAPPER_NAME).read_text(encoding="utf-8")
        self.assertEqual(text.count("2>&1"), 1)

    def test_usage_text_is_unchanged(self):
        for wrapper, usage in (
            (WORKFLOW_SCRIPTS_DIR / WRAPPER_NAME, WORKFLOW_USAGE),
            (REVIEW_SCRIPTS_DIR / WRAPPER_NAME, REVIEW_USAGE),
        ):
            with self.subTest(wrapper=str(wrapper)):
                proc, launches = _run_wrapper(wrapper, [])
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(proc.stderr.strip(), usage)
                self.assertEqual(launches, [])

    def test_unknown_flag_and_invalid_mode_messages_are_unchanged(self):
        for wrapper in (
            WORKFLOW_SCRIPTS_DIR / WRAPPER_NAME,
            REVIEW_SCRIPTS_DIR / WRAPPER_NAME,
        ):
            with self.subTest(wrapper=str(wrapper)):
                proc, launches = _run_wrapper(wrapper, ["readonly", "--bogus", "prompt"])
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(proc.stderr.strip(), "ERROR: Unknown flag '--bogus'")
                proc, launches = _run_wrapper(wrapper, ["sideways", "prompt"])
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(
                    proc.stderr.strip(),
                    "ERROR: Invalid mode 'sideways'. Use 'readonly' or 'readwrite'.",
                )
                self.assertEqual(launches, [])

    def test_litellm_is_still_not_accepted_by_the_em_review_wrapper(self):
        proc, launches = _run_wrapper(
            REVIEW_SCRIPTS_DIR / WRAPPER_NAME, ["readonly", "--litellm", MODEL, "prompt"]
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stderr.strip(), "ERROR: Unknown flag '--litellm'")
        self.assertEqual(launches, [])

    def test_accepted_flags_still_reach_the_launch(self):
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            with self.subTest(path=label):
                argv = _launch_argv(
                    scripts_dir / WRAPPER_NAME,
                    "readonly",
                    ["-C", "/tmp/work-here", "--output-schema", "schema.json", *path_args],
                )
                self.assertTrue(_find_adjacent(argv, ["-C", "/tmp/work-here"]))
                self.assertTrue(_find_adjacent(argv, ["--output-schema", "schema.json"]))
                for flag in ("--color", "--skip-git-repo-check", "--ignore-rules"):
                    self.assertIn(flag, argv)

    def test_em_review_wrapper_has_codex_exec_once_in_non_comment_lines(self):
        text = (REVIEW_SCRIPTS_DIR / WRAPPER_NAME).read_text(encoding="utf-8")
        code = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("#")
        )
        self.assertEqual(code.count("codex exec"), 1)


class TestHarnessNeverReachesRealCodex(unittest.TestCase):
    """AC-7 (NFR4, FR14): the harness shape that keeps this module off real
    Codex, and the module's own dependencies."""

    def test_the_stub_is_what_the_wrapper_runs(self):
        # A wrapper run that did not reach the stub would leave no record.
        proc, launches = _run_wrapper(
            WORKFLOW_SCRIPTS_DIR / WRAPPER_NAME, ["readonly", "prompt"]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("STUB_ANSWER: ok", proc.stdout)
        self.assertEqual(len(launches), 1)

    def test_the_launch_sees_an_isolated_home(self):
        real_home = os.environ.get("HOME", "")
        proc, launches = _run_wrapper(
            REVIEW_SCRIPTS_DIR / WRAPPER_NAME, ["readonly", "prompt"]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        seen_home = launches[0]["home"]
        self.assertNotEqual(seen_home, real_home)
        self.assertTrue(seen_home.startswith(tempfile.gettempdir()), seen_home)

    def test_module_imports_are_all_stdlib(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported <= set(sys.stdlib_module_names), imported)


class TestCheckerDetectsRegressions(unittest.TestCase):
    """Non-vacuity: the registration checker and the adjacency matcher fail
    against forged input, so a green run above means something."""

    HOOK_PATH = "/plugins/x/scripts/" + HOOK_NAME

    def _good_value(self, command=None, matcher="Bash", extra_group=False):
        command = command or f"python3 '{self.HOOK_PATH}'"
        group = '{matcher="%s", hooks=[{type="command", command="%s"}]}' % (matcher, command)
        groups = group + (", " + group if extra_group else "")
        return f"{HOOK_KEY_PREFIX}[{groups}]"

    def _good_argv(self, **kwargs):
        return ["exec", "-c", self._good_value(**kwargs), BYPASS_FLAG, "prompt"]

    def test_accepts_a_well_formed_argv(self):
        _assert_hook_registered(self._good_argv(), self.HOOK_PATH)

    def test_rejects_argv_without_the_bypass_flag(self):
        argv = [a for a in self._good_argv() if a != BYPASS_FLAG]
        with self.assertRaises(AssertionError):
            _assert_hook_registered(argv, self.HOOK_PATH)

    def test_rejects_argv_without_the_hook_value(self):
        with self.assertRaises(AssertionError):
            _assert_hook_registered(["exec", BYPASS_FLAG, "prompt"], self.HOOK_PATH)

    def test_rejects_a_hook_value_not_preceded_by_dash_c(self):
        argv = ["exec", self._good_value(), BYPASS_FLAG, "prompt"]
        with self.assertRaises(AssertionError):
            _assert_hook_registered(argv, self.HOOK_PATH)

    def test_rejects_the_wrong_matcher(self):
        with self.assertRaises(AssertionError):
            _assert_hook_registered(self._good_argv(matcher="Read"), self.HOOK_PATH)

    def test_rejects_a_two_element_array(self):
        with self.assertRaises(AssertionError):
            _assert_hook_registered(self._good_argv(extra_group=True), self.HOOK_PATH)

    def test_rejects_another_plugins_hook_path(self):
        with self.assertRaises(AssertionError):
            _assert_hook_registered(self._good_argv(), "/plugins/y/scripts/" + HOOK_NAME)

    def test_rejects_a_path_that_is_not_quoted_for_the_shell(self):
        bad = self._good_argv(command=f"python3 /plugins/with space/{HOOK_NAME}")
        with self.assertRaises(AssertionError):
            _assert_hook_registered(bad, f"/plugins/with space/{HOOK_NAME}")

    def test_rejects_a_value_that_is_not_valid_toml(self):
        argv = ["exec", "-c", HOOK_KEY_PREFIX + "[{matcher=Bash}]", BYPASS_FLAG, "prompt"]
        with self.assertRaises(tomllib.TOMLDecodeError):
            _assert_hook_registered(argv, self.HOOK_PATH)

    def test_rejects_a_relative_expected_path(self):
        with self.assertRaises(AssertionError):
            _assert_hook_registered(self._good_argv(), "scripts/" + HOOK_NAME)

    def test_adjacency_matcher_accepts_adjacent_and_rejects_scattered(self):
        words = ["-p", "litellm", "-m", MODEL]
        self.assertTrue(_find_adjacent(["a", *words, "b"], words))
        self.assertFalse(_find_adjacent(["-p", "litellm", "-c", "x", "-m", MODEL], words))
        self.assertFalse(_find_adjacent(["-m", MODEL, "-p", "litellm"], words))

    def test_adjacency_matcher_refuses_an_empty_sequence(self):
        with self.assertRaises(ValueError):
            _find_adjacent(["a"], [])


if __name__ == "__main__":
    unittest.main()
