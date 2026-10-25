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

The module also covers the Stop hook registration of
feature-docs/codex-stop-hook-tty-reaper/tasks/task0002.md. Both wrappers
register scripts/codex-hook-tty-reaper.py (the copy next to the wrapper) as a
Codex Stop hook on every launch path, with the wrapper's own process ID as
the single argument (the TM-2 anchor). Stop-hook tests are named `*_stop_*`
and map to that task's Acceptance Criteria:

- Stop AC-1 (FR1, FR2, TM-2): on em-workflow default, em-workflow --litellm
  and em-review, readonly and readwrite, the recorded argv holds exactly one
  `-c` value starting with `hooks.Stop=`. It parses as TOML into one group
  with no matcher and exactly one command hook, and the command, executed
  through sh, bash (and zsh when present), runs `python3` with exactly two
  arguments: the absolute path of the same plugin's
  scripts/codex-hook-tty-reaper.py and the decimal process ID of the wrapper
  process itself, which the harness reads from the process it started.
- Stop AC-2 (FR2): the path comes from the wrapper's own location, not from
  the caller's working directory; neither plugin names the other's
  directory; a copy of scripts/ without the hook file still launches the
  stub exactly once.
- Stop AC-3 (TM-6): the Stop value survives copies under awkward directory
  names (a space and a single quote; every shell/TOML metacharacter).
- Stop AC-4 (FR6): the PreToolUse registration checks still hold on every
  launch path, next to the Stop registration.
- Stop AC-5 (NFR3): one bypass flag, the prompt last, `-p litellm -m MODEL`
  adjacent, isolation flags and overrides intact (the rest of the wrapper
  contract is pinned by the classes above).
- Stop AC-6 (NFR4): the same harness (stub `codex` first on PATH, isolated
  HOME), standard-library imports only. The Stop hook is never executed and
  its file is never required (IMPLEMENTATION.md D3): `python3` is replaced by
  a recorder when a recorded command is run.
"""

import ast
import json
import os
import re
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
STOP_HOOK_NAME = "codex-hook-tty-reaper.py"
CONFIG_RELATIVE = Path("references") / "codex-cli.yaml"

BYPASS_FLAG = "--dangerously-bypass-hook-trust"
HOOK_KEY_PREFIX = "hooks.PreToolUse="
STOP_KEY_PREFIX = "hooks.Stop="
MODEL = "test-model-xyz"
MODES = ("readonly", "readwrite")

WORKFLOW_USAGE = (
    'Usage: run_codex_exec.sh <readonly|readwrite> [-C DIR] '
    '[--output-schema F] [-m MODEL] [--litellm MODEL] "prompt"'
)
REVIEW_USAGE = (
    'Usage: run_codex_exec.sh <readonly|readwrite> [-C DIR] '
    '[--output-schema F] [-m MODEL] "prompt"'
)

# Launch paths: (label, plugin scripts dir, wrapper-specific args placed
# between the mode and the prompt, whether the launch carries
# --ignore-user-config today).
DEFAULT_PATH = ("workflow-default", WORKFLOW_SCRIPTS_DIR, [], True)
LITELLM_PATH = ("workflow-litellm", WORKFLOW_SCRIPTS_DIR, ["--litellm", MODEL], False)
REVIEW_PATH = ("review", REVIEW_SCRIPTS_DIR, [], True)
ALL_PATHS = (DEFAULT_PATH, LITELLM_PATH, REVIEW_PATH)

# The stub codex records its argv, its HOME and its ancestor process IDs
# (nearest first, read from /proc where it exists) as one JSON line and
# exits successfully.
CODEX_STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import sys


def ancestors():
    chain = []
    pid = os.getppid()
    while pid > 1 and len(chain) < 64:
        chain.append(pid)
        try:
            with open("/proc/%d/stat" % pid, "rb") as fh:
                data = fh.read().decode("utf-8", "replace")
            pid = int(data.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return chain


with open(os.environ["CODEX_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({
        "argv": sys.argv[1:],
        "home": os.environ.get("HOME"),
        "ancestors": ancestors(),
    }) + "\\n")
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


def _run_wrapper_pid(wrapper_path, wrapper_args, extra_env=None, cwd=None, timeout=30):
    """Runs a wrapper as a subprocess with a stub `codex` first on PATH and
    an isolated HOME (AC-7). Returns (CompletedProcess, list of recorded
    launches, process ID of the wrapper). The wrapper is started directly
    as `bash <script>`, so the process ID the harness reads is that of the
    shell process that runs the wrapper script and later waits on the launch.
    The caller's working directory is a fresh temporary
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

        with subprocess.Popen(
            ["bash", str(wrapper_path), *wrapper_args],
            env=env,
            cwd=str(cwd if cwd is not None else caller_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as popen:
            try:
                stdout, stderr = popen.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                popen.kill()
                popen.communicate()
                raise
            proc = subprocess.CompletedProcess(
                popen.args, popen.returncode, stdout, stderr
            )
            return proc, _read_log(log_path), popen.pid


def _run_wrapper(wrapper_path, wrapper_args, extra_env=None, cwd=None, timeout=30):
    """Same as `_run_wrapper_pid`, without the wrapper's process ID.
    Returns (CompletedProcess, list of recorded launches)."""
    proc, launches, _ = _run_wrapper_pid(
        wrapper_path, wrapper_args, extra_env=extra_env, cwd=cwd, timeout=timeout
    )
    return proc, launches


def _launch_record(wrapper_path, mode, path_args, extra_env=None, prompt="do the thing"):
    """Runs one launch and returns (the single recorded launch, the wrapper's
    process ID). The wrapper run must have exited 0 and invoked the stub
    exactly once."""
    proc, launches, pid = _run_wrapper_pid(
        wrapper_path, [mode, *path_args, prompt], extra_env=extra_env
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"wrapper exited {proc.returncode}: stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    if len(launches) != 1:
        raise AssertionError(f"expected exactly one stub invocation, got {launches}")
    return launches[0], pid


def _launch_argv(wrapper_path, mode, path_args, extra_env=None, prompt="do the thing"):
    """Runs one launch and returns the single recorded argv (the wrapper run
    must have exited 0 and invoked the stub exactly once)."""
    record, _ = _launch_record(
        wrapper_path, mode, path_args, extra_env=extra_env, prompt=prompt
    )
    return record["argv"]


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


def _stop_c_values(argv):
    """Every value passed as `-c <value>` that starts with the Stop hook key."""
    return [
        argv[i + 1]
        for i in range(len(argv) - 1)
        if argv[i] == "-c" and argv[i + 1].startswith(STOP_KEY_PREFIX)
    ]


def _assert_stop_registered(argv, expected_hook_path, expected_anchor):
    """The Stop-registration checker (Stop AC-1 / AC-2 / AC-3). Raises with a
    descriptive message rather than returning a bool. `expected_anchor` is the
    process ID of the wrapper process that was launched. The recorded command
    is run through every available shell with a recorder in place of
    `python3`; the hook file itself is never executed or required."""
    values = _stop_c_values(argv)
    if len(values) != 1:
        raise AssertionError(
            f"expected exactly one `-c {STOP_KEY_PREFIX}...` pair, found {len(values)} in {argv!r}"
        )
    parsed = tomllib.loads(values[0])
    groups = parsed["hooks"]["Stop"]
    if not isinstance(groups, list) or len(groups) != 1:
        raise AssertionError(f"Stop must be a one-group array: {groups!r}")
    group = groups[0]
    if not isinstance(group, dict) or "matcher" in group:
        raise AssertionError(f"the Stop group must have no matcher: {group!r}")
    hooks = group.get("hooks")
    if not isinstance(hooks, list) or len(hooks) != 1:
        raise AssertionError(f"the Stop group must hold exactly one hook: {group!r}")
    hook = hooks[0]
    if hook.get("type") != "command" or not isinstance(hook.get("command"), str):
        raise AssertionError(f"the Stop hook must be a command-type hook: {hook!r}")
    if not os.path.isabs(expected_hook_path):
        raise AssertionError(f"expected hook path is not absolute: {expected_hook_path!r}")
    if not isinstance(expected_anchor, int) or expected_anchor <= 1:
        raise AssertionError(f"expected anchor is not a process ID: {expected_anchor!r}")
    expected = [expected_hook_path, str(expected_anchor)]
    with tempfile.TemporaryDirectory() as tmp_root:
        for shell in _available_shells():
            received = _run_command_through_shell(hook["command"], shell, tmp_root)
            if len(received) != 2:
                raise AssertionError(
                    f"under {shell}, the command {hook['command']!r} passed "
                    f"{len(received)} arguments {received!r} to python3, expected "
                    f"exactly two: {expected!r}"
                )
            if re.fullmatch(r"[0-9]+", received[1]) is None:
                raise AssertionError(
                    f"under {shell}, the anchor {received[1]!r} of "
                    f"{hook['command']!r} is not ASCII decimal digits"
                )
            if received != expected:
                raise AssertionError(
                    f"under {shell}, the command {hook['command']!r} passed "
                    f"{received!r} to python3, expected {expected!r}"
                )
    return hook["command"]


def _copy_plugin_scripts(scripts_dir, root, dir_name):
    """Copies a plugin's scripts directory, with references/codex-cli.yaml
    beside it, under `root/dir_name`. Returns the copied scripts directory."""
    plugin_copy = Path(root) / dir_name
    shutil.copytree(
        scripts_dir,
        plugin_copy / "scripts",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (plugin_copy / "references").mkdir()
    shutil.copy(scripts_dir.parent / CONFIG_RELATIVE, plugin_copy / CONFIG_RELATIVE)
    return plugin_copy / "scripts"


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
        return _copy_plugin_scripts(scripts_dir, root, dir_name)

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


class TestStopHookRegistrationOnEveryLaunch(unittest.TestCase):
    """Stop AC-1 (FR1, FR2, TM-2): the Stop registration, with the wrapper's
    own process ID as its anchor, reaches every launch path in both modes."""

    def _check(self, launch_path, mode):
        label, scripts_dir, path_args, _ = launch_path
        record, pid = _launch_record(scripts_dir / WRAPPER_NAME, mode, path_args)
        command = _assert_stop_registered(
            record["argv"], str(scripts_dir / STOP_HOOK_NAME), pid
        )
        # The interpreter is Python 3 (the first word of the command).
        self.assertEqual(shlex.split(command)[0], "python3", f"{label}/{mode}")
        return record, pid

    def test_stop_ac1_workflow_default_path_readonly(self):
        self._check(DEFAULT_PATH, "readonly")

    def test_stop_ac1_workflow_default_path_readwrite(self):
        self._check(DEFAULT_PATH, "readwrite")

    def test_stop_ac1_workflow_litellm_path_readonly(self):
        self._check(LITELLM_PATH, "readonly")

    def test_stop_ac1_workflow_litellm_path_readwrite(self):
        self._check(LITELLM_PATH, "readwrite")

    def test_stop_ac1_review_readonly(self):
        self._check(REVIEW_PATH, "readonly")

    def test_stop_ac1_review_readwrite(self):
        self._check(REVIEW_PATH, "readwrite")

    @unittest.skipUnless(os.path.isdir("/proc/self"), "needs /proc to read ancestors")
    def test_stop_ac1_anchor_stays_an_ancestor_of_the_launch(self):
        # S1 precondition: the anchor is alive and an ancestor of whatever
        # the launch starts (the stub stands where Codex, and so the hook's
        # ancestry, would be). A subshell's process ID would not be.
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            for mode in MODES:
                with self.subTest(path=label, mode=mode):
                    record, pid = _launch_record(
                        scripts_dir / WRAPPER_NAME, mode, path_args
                    )
                    _assert_stop_registered(
                        record["argv"], str(scripts_dir / STOP_HOOK_NAME), pid
                    )
                    self.assertIn(pid, record["ancestors"])

    def test_stop_ac1_each_run_carries_its_own_anchor(self):
        anchors = set()
        for _ in range(2):
            record, pid = _launch_record(
                WORKFLOW_SCRIPTS_DIR / WRAPPER_NAME, "readonly", []
            )
            _assert_stop_registered(
                record["argv"], str(WORKFLOW_SCRIPTS_DIR / STOP_HOOK_NAME), pid
            )
            anchors.add(pid)
        self.assertEqual(len(anchors), 2)


class TestStopHookPathFollowsTheWrapper(unittest.TestCase):
    """Stop AC-2 (FR2): the path comes from the wrapper's own location."""

    @staticmethod
    def _other(scripts_dir):
        return REVIEW_SCRIPTS_DIR if scripts_dir == WORKFLOW_SCRIPTS_DIR else WORKFLOW_SCRIPTS_DIR

    def test_stop_ac2_path_does_not_depend_on_the_callers_working_directory(self):
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            with self.subTest(path=label):
                proc, launches, pid = _run_wrapper_pid(
                    scripts_dir / WRAPPER_NAME,
                    ["readonly", *path_args, "prompt"],
                    cwd=self._other(scripts_dir),
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(launches), 1)
                _assert_stop_registered(
                    launches[0]["argv"], str(scripts_dir / STOP_HOOK_NAME), pid
                )

    def test_stop_ac2_each_plugin_names_only_its_own_directory(self):
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            with self.subTest(path=label):
                argv = _launch_argv(scripts_dir / WRAPPER_NAME, "readonly", path_args)
                values = _stop_c_values(argv)
                self.assertEqual(len(values), 1, argv)
                self.assertIn(str(scripts_dir), values[0])
                self.assertNotIn(str(self._other(scripts_dir)), values[0])

    def test_stop_ac2_a_scripts_copy_without_the_hook_file_still_launches_once(self):
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            with self.subTest(path=label):
                with tempfile.TemporaryDirectory() as root_s:
                    root = os.path.realpath(root_s)
                    copied = _copy_plugin_scripts(scripts_dir, root, "plugin-copy")
                    hook_file = copied / STOP_HOOK_NAME
                    if hook_file.exists():
                        hook_file.unlink()
                    self.assertFalse(hook_file.exists())
                    proc, launches, pid = _run_wrapper_pid(
                        copied / WRAPPER_NAME, ["readonly", *path_args, "prompt"]
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(len(launches), 1, launches)
                    _assert_stop_registered(launches[0]["argv"], str(hook_file), pid)
                    self.assertEqual(proc.stderr, "")


class TestStopHookPathSurvivesHostilePlugins(unittest.TestCase):
    """Stop AC-3 (TM-6): a copy of the plugin's scripts directory under an
    awkward path still yields a Stop value that parses as TOML and a command
    that passes exactly the copied hook path and the wrapper's process ID."""

    def _check_copy(self, launch_path, dir_name):
        label, scripts_dir, path_args, _ = launch_path
        with tempfile.TemporaryDirectory() as root_s:
            root = os.path.realpath(root_s)
            copied_scripts = _copy_plugin_scripts(scripts_dir, root, dir_name)
            proc, launches, pid = _run_wrapper_pid(
                copied_scripts / WRAPPER_NAME, ["readonly", *path_args, "prompt"]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(len(launches), 1, f"{label} in {dir_name!r}")
            expected = str(copied_scripts / STOP_HOOK_NAME)
            self.assertIn(dir_name, expected)
            _assert_stop_registered(launches[0]["argv"], expected, pid)

    def test_stop_ac3_space_and_single_quote_in_path_for_every_launch_path(self):
        for launch_path in ALL_PATHS:
            with self.subTest(path=launch_path[0]):
                self._check_copy(launch_path, SPACE_AND_QUOTE_NAME)

    def test_stop_ac3_every_shell_and_toml_metacharacter_in_path(self):
        for launch_path in (DEFAULT_PATH, REVIEW_PATH):
            for name in HOSTILE_NAMES:
                with self.subTest(path=launch_path[0], name=name):
                    self._check_copy(launch_path, name)


class TestStopRegistrationLeavesTheLaunchContractAlone(unittest.TestCase):
    """Stop AC-4 (FR6) and Stop AC-5 (NFR3): the Stop value joins the
    existing hook flag group without disturbing the PreToolUse registration
    or the launch's other arguments."""

    def test_stop_ac4_both_registrations_and_one_bypass_flag_on_every_launch(self):
        for label, scripts_dir, path_args, _ in ALL_PATHS:
            for mode in MODES:
                with self.subTest(path=label, mode=mode):
                    record, pid = _launch_record(scripts_dir / WRAPPER_NAME, mode, path_args)
                    argv = record["argv"]
                    # The existing PreToolUse checks, unchanged: one value,
                    # matcher Bash, the same plugin's interactive guard, and
                    # exactly one bypass flag.
                    _assert_hook_registered(argv, str(scripts_dir / HOOK_NAME))
                    self.assertEqual(len(_hook_c_values(argv)), 1)
                    _assert_stop_registered(argv, str(scripts_dir / STOP_HOOK_NAME), pid)
                    self.assertEqual(argv.count(BYPASS_FLAG), 1)

    def test_stop_ac5_stop_value_stays_out_of_the_profile_words_and_before_the_prompt(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                record, _ = _launch_record(
                    WORKFLOW_SCRIPTS_DIR / WRAPPER_NAME,
                    mode,
                    ["-C", "/tmp/somewhere", "--output-schema", "schema.json",
                     "--litellm", MODEL],
                    extra_env={"CODEX_OTLP_ENDPOINT": "http://127.0.0.1:4318/v1/logs"},
                    prompt="PROMPT-TEXT",
                )
                argv = record["argv"]
                self.assertTrue(_find_adjacent(argv, ["-p", "litellm", "-m", MODEL]), argv)
                self.assertNotIn("--ignore-user-config", argv)
                self.assertTrue(argv[-1].endswith("PROMPT-TEXT"), argv[-1])
                stop_values = _stop_c_values(argv)
                self.assertEqual(len(stop_values), 1, argv)
                self.assertLess(argv.index(stop_values[0]), len(argv) - 1)

    def test_stop_ac5_isolation_flags_and_overrides_survive_next_to_the_stop_value(self):
        endpoint = "http://127.0.0.1:4318/v1/logs"
        for label, scripts_dir, path_args, has_ignore_user_config in ALL_PATHS:
            for mode in MODES:
                with self.subTest(path=label, mode=mode):
                    record, pid = _launch_record(
                        scripts_dir / WRAPPER_NAME,
                        mode,
                        path_args,
                        extra_env={"CODEX_OTLP_ENDPOINT": endpoint},
                        prompt="PROMPT-TEXT",
                    )
                    argv = record["argv"]
                    _assert_stop_registered(argv, str(scripts_dir / STOP_HOOK_NAME), pid)
                    self.assertIn("--ignore-rules", argv)
                    self.assertEqual("--ignore-user-config" in argv, has_ignore_user_config)
                    self.assertTrue(_find_adjacent(argv, ["-c", 'otel.environment="local"']))
                    if mode == "readonly":
                        self.assertTrue(
                            _find_adjacent(argv, ["-c", 'model_reasoning_effort="xhigh"'])
                        )
                    self.assertTrue(argv[-1].endswith("PROMPT-TEXT"))


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


class TestStopCheckerDetectsRegressions(unittest.TestCase):
    """Non-vacuity for the Stop checker: it fails against forged argv, so a
    green run above means something. The forged hook path does not exist; the
    checker never needs the hook file."""

    HOOK_PATH = "/plugins/x/scripts/" + STOP_HOOK_NAME
    ANCHOR = 4242

    def _hook(self, command, hook_type="command"):
        return '{type="%s", command="%s"}' % (hook_type, command)

    def _good_command(self, path=None, anchor=None):
        path = path or self.HOOK_PATH
        anchor = self.ANCHOR if anchor is None else anchor
        return f"python3 '{path}' {anchor}"

    def _value(self, command=None, group_fields="", hooks=None, groups=1):
        command = command or self._good_command()
        hook_list = hooks if hooks is not None else [self._hook(command)]
        group = "{%shooks=[%s]}" % (group_fields, ", ".join(hook_list))
        return f"{STOP_KEY_PREFIX}[{', '.join([group] * groups)}]"

    def _argv(self, *values):
        argv = ["exec"]
        for value in values:
            argv += ["-c", value]
        return argv + [BYPASS_FLAG, "prompt"]

    def _good_argv(self):
        return self._argv(self._value())

    def _reject(self, argv, path=None, anchor=None):
        with self.assertRaises(AssertionError):
            _assert_stop_registered(
                argv, path or self.HOOK_PATH, self.ANCHOR if anchor is None else anchor
            )

    def test_accepts_a_well_formed_argv(self):
        _assert_stop_registered(self._good_argv(), self.HOOK_PATH, self.ANCHOR)

    def test_rejects_argv_without_the_stop_value(self):
        self._reject(["exec", BYPASS_FLAG, "prompt"])

    def test_rejects_two_stop_values(self):
        self._reject(self._argv(self._value(), self._value()))

    def test_rejects_a_stop_value_not_preceded_by_dash_c(self):
        self._reject(["exec", self._value(), BYPASS_FLAG, "prompt"])

    def test_rejects_a_pretooluse_value_in_place_of_the_stop_value(self):
        value = self._value().replace(STOP_KEY_PREFIX, HOOK_KEY_PREFIX, 1)
        self._reject(self._argv(value))

    def test_rejects_a_group_with_a_matcher(self):
        self._reject(self._argv(self._value(group_fields='matcher="Bash", ')))

    def test_rejects_an_empty_matcher(self):
        self._reject(self._argv(self._value(group_fields='matcher="", ')))

    def test_rejects_two_groups(self):
        self._reject(self._argv(self._value(groups=2)))

    def test_rejects_two_hooks_in_the_group(self):
        hooks = [self._hook(self._good_command()), self._hook(self._good_command())]
        self._reject(self._argv(self._value(hooks=hooks)))

    def test_rejects_a_group_without_hooks(self):
        self._reject(self._argv(self._value(hooks=[])))

    def test_rejects_a_non_command_hook_type(self):
        hooks = [self._hook(self._good_command(), hook_type="prompt")]
        self._reject(self._argv(self._value(hooks=hooks)))

    def test_rejects_another_plugins_hook_path(self):
        self._reject(self._good_argv(), path="/plugins/y/scripts/" + STOP_HOOK_NAME)

    def test_rejects_the_other_hooks_file_name(self):
        other = "/plugins/x/scripts/" + HOOK_NAME
        self._reject(self._argv(self._value(self._good_command(path=other))))

    def test_rejects_a_path_that_is_not_quoted_for_the_shell(self):
        path = f"/plugins/with space/{STOP_HOOK_NAME}"
        command = f"python3 {path} {self.ANCHOR}"
        self._reject(self._argv(self._value(command)), path=path)

    def test_rejects_a_missing_anchor(self):
        command = f"python3 '{self.HOOK_PATH}'"
        self._reject(self._argv(self._value(command)))

    def test_rejects_an_extra_argument_after_the_anchor(self):
        command = self._good_command() + " extra"
        self._reject(self._argv(self._value(command)))

    def test_rejects_two_anchors(self):
        command = self._good_command() + f" {self.ANCHOR}"
        self._reject(self._argv(self._value(command)))

    def test_rejects_a_non_decimal_anchor(self):
        for bad in ("abc", "0x10a2", "42.5", "-4242", "4242a", "४२४२"):
            with self.subTest(anchor=bad):
                command = f"python3 '{self.HOOK_PATH}' {bad}"
                self._reject(self._argv(self._value(command)))

    def test_rejects_an_anchor_left_for_the_shell_to_expand(self):
        # `$$` expands to the executing shell's own process ID, which is
        # decimal but is not the wrapper's.
        command = f"python3 '{self.HOOK_PATH}' $$"
        self._reject(self._argv(self._value(command)))

    def test_rejects_a_zero_padded_anchor(self):
        command = f"python3 '{self.HOOK_PATH}' 0{self.ANCHOR}"
        self._reject(self._argv(self._value(command)))

    def test_rejects_an_anchor_that_is_another_process(self):
        # The anchor must be the wrapper's: any other process ID is refused.
        command = self._good_command(anchor=self.ANCHOR + 1)
        self._reject(self._argv(self._value(command)))

    def test_rejects_a_value_that_is_not_valid_toml(self):
        argv = ["exec", "-c", STOP_KEY_PREFIX + "[{hooks=Bash}]", BYPASS_FLAG, "prompt"]
        with self.assertRaises(tomllib.TOMLDecodeError):
            _assert_stop_registered(argv, self.HOOK_PATH, self.ANCHOR)

    def test_rejects_a_relative_expected_path(self):
        with self.assertRaises(AssertionError):
            _assert_stop_registered(
                self._good_argv(), "scripts/" + STOP_HOOK_NAME, self.ANCHOR
            )

    def test_rejects_an_expected_anchor_that_is_not_a_process_id(self):
        for bad in (None, "4242", 0, 1, -5):
            with self.subTest(anchor=bad):
                with self.assertRaises(AssertionError):
                    _assert_stop_registered(self._good_argv(), self.HOOK_PATH, bad)


if __name__ == "__main__":
    unittest.main()
