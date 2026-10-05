"""Tests for codex-repo-hook-trust task0001: on every wrapper launch route
where Codex 0.160.0 was observed executing repository hooks, the wrapper
hands Codex a protective specification
(feature-docs/codex-repo-hook-trust/HOOK-TRUST-FINDINGS.md,
feature-docs/codex-repo-hook-trust/tasks/task0001.md).

The findings record names one executing route: the em-workflow wrapper's
`--litellm MODEL` route. It reads the user-level Codex configuration (the
`-p litellm` profile layers on top of it), and that configuration carries
the project trust that makes Codex load the working directory's `.codex/`
configuration layers, including their hook definitions. The protective
specification is a launch-dedicated Codex home: the wrapper gives codex a
fresh CODEX_HOME that holds the litellm profile and nothing else but a
config.toml marking the working directory and every directory above it as
`untrusted`. No trust entry from the user's real Codex home reaches the
launch.

Covers task0001 Acceptance Criteria:

- AC-5 (FR5, NFR1, NFR2, NFR5), TS1 (always runs, stub codex): for the
  changed route (em-workflow --litellm) x {readonly, readwrite} the stub
  sees the protective specification, the wrapper's own guard registration
  in argv, and HOME and CODEX_HOME pointing at temporary directories. The
  predicate that decides this is shown to reject forged records that lack
  the specification (non-vacuity). The credential variable carries a
  sentinel value that must be absent from the wrapper's captured output
  and from the files of the launch home; failure diagnostics name
  variables, never their values.
- AC-4 (FR3, NFR3), pinned together with the four existing wrapper test
  modules: the changed route keeps `-p litellm -m MODEL`, `--ignore-rules`,
  the bypass flag and the guard registration, gains no `--ignore-user-config`
  and no 2>&1; routes that were not observed executing (em-workflow default,
  em-review default) are launched exactly as before (same CODEX_HOME).
- AC-6 (FR5, NFR1, NFR2), TS2 (real Codex, may skip): with temporary HOME
  and CODEX_HOME, when codex reports 0.160.0 and a control launch with the
  pre-change composition creates the marker, the launch through the wrapper
  leaves no marker. The case skips -- never passes -- when codex is absent,
  does not report 0.160.0, git is missing, or the control creates no marker.
  Every real launch is bounded in wall-clock time and its process tree is
  ended when the bound is hit. The skip rule itself is pinned by running the
  TS2 class in a child interpreter whose PATH lacks codex or carries a fake
  one (other version, or a control that creates no marker).

Nothing under em-workflow/ or em-review/ is imported: the wrappers run as
separate processes. Standard library only (NFR2).
"""

import http.server
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / "em-workflow" / "scripts"
REVIEW_SCRIPTS_DIR = REPO_ROOT / "em-review" / "scripts"
WRAPPER_NAME = "run_codex_exec.sh"
HOOK_NAME = "codex-hook-interactive-guard.py"

BYPASS_FLAG = "--dangerously-bypass-hook-trust"
HOOK_KEY_PREFIX = "hooks.PreToolUse="
MODEL = "test-model-xyz"
MODES = ("readonly", "readwrite")
SUPPORTED_CODEX_VERSION = "0.160.0"

CREDENTIAL_VAR = "LITELLM_API_KEY"
# A recognisable placeholder, not a credential. It stands where the
# credential value stands and must never reach captured output or files.
CREDENTIAL_SENTINEL = "SENTINEL-credential-value-9f3a1c7e5b"

PROFILE_TEXT = (
    'model = "test-profile-model"\n'
    'model_provider = "litellm"\n'
    "\n"
    "[model_providers.litellm]\n"
    'name = "LiteLLM proxy"\n'
    'base_url = "http://127.0.0.1:9/v1"\n'
    'env_key = "LITELLM_API_KEY"\n'
    'wire_api = "responses"\n'
    "request_max_retries = 0\n"
    "stream_max_retries = 0\n"
)

# The stub codex records what it can see at launch time: argv, the few
# environment variables that matter, and the files of the CODEX_HOME it was
# handed (the wrapper removes a launch-dedicated home right after codex
# returns, so this is the only moment it can be read). The credential value
# is never recorded -- only whether the variable is set.
CODEX_STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import sys

def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None

home = os.environ.get("CODEX_HOME")
record = {
    "argv": sys.argv[1:],
    "env": {
        "HOME": os.environ.get("HOME"),
        "CODEX_HOME": home,
        "TMPDIR": os.environ.get("TMPDIR"),
        "credential_set": bool(os.environ.get("LITELLM_API_KEY")),
    },
    "cwd": os.getcwd(),
    "home_entries": sorted(os.listdir(home)) if home and os.path.isdir(home) else None,
    "config_toml": read(os.path.join(home, "config.toml")) if home else None,
    "profile_toml": read(os.path.join(home, "litellm.config.toml")) if home else None,
}
with open(os.environ["CODEX_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\\n")
print("STUB_ANSWER: ok")
sys.exit(int(os.environ.get("CODEX_STUB_EXIT", "0")))
"""


def _write_executable(path, source):
    path.write_text(source, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _toml_key(path):
    """The path as a TOML basic-string key, the way a config file spells it."""
    out = []
    for ch in str(path):
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("\\u%04X" % ord(ch))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _ancestors_inclusive(path):
    """`path` and every directory above it, nearest first."""
    path = Path(path)
    return [path, *path.parents]


class Launch:
    """Everything one wrapper run through the stub produced."""

    def __init__(self, proc, record, work, user_home, home, tmp, workdir, passed):
        self.proc = proc
        self.record = record
        self.work = work
        self.user_home = user_home
        self.home = home
        self.tmp = tmp
        self.workdir = workdir
        self.passed = passed


def run_stub_launch(
    wrapper,
    wrapper_args,
    *,
    mode,
    user_config=None,
    user_profile=PROFILE_TEXT,
    workdir_name="repo",
    use_link=False,
    pass_workdir=True,
    stub_exit=0,
):
    """Runs a wrapper once with a stub `codex` first on PATH. HOME, CODEX_HOME
    (the user's Codex home) and TMPDIR are fresh temporary directories; the
    credential variable carries the sentinel. `user_config` is a callable
    taking the working directory and returning the user's config.toml text
    (None: no config.toml)."""
    with tempfile.TemporaryDirectory() as work_s:
        work = Path(work_s).resolve()
        stub_dir = work / "stub-bin"
        stub_dir.mkdir()
        _write_executable(stub_dir / "codex", CODEX_STUB_SOURCE)
        log_path = work / "stub.log"
        home = work / "home"
        home.mkdir()
        user_home = work / "user-codex-home"
        user_home.mkdir()
        tmp = work / "tmp"
        tmp.mkdir()
        workdir = work / workdir_name
        workdir.mkdir()
        passed = workdir
        if use_link:
            passed = work / "link-to-workdir"
            passed.symlink_to(workdir, target_is_directory=True)
        if user_config is not None:
            (user_home / "config.toml").write_text(user_config(workdir), encoding="utf-8")
        if user_profile is not None:
            (user_home / "litellm.config.toml").write_text(user_profile, encoding="utf-8")
        before = _snapshot(user_home)

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        env["HOME"] = str(home)
        env["CODEX_HOME"] = str(user_home)
        env["TMPDIR"] = str(tmp)
        env[CREDENTIAL_VAR] = CREDENTIAL_SENTINEL
        env["CODEX_STUB_LOG"] = str(log_path)
        env["CODEX_STUB_EXIT"] = str(stub_exit)
        env.pop("CODEX_OTLP_ENDPOINT", None)

        resolved = shutil.which("codex", path=env["PATH"])
        assert resolved == str(stub_dir / "codex"), "the stub codex is not first on PATH"

        args = [mode, *wrapper_args]
        if pass_workdir:
            args += ["-C", str(passed)]
        args += ["do the thing"]
        proc = subprocess.run(
            ["bash", str(wrapper), *args],
            env=env,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        records = []
        if log_path.is_file():
            records = [json.loads(line) for line in log_path.read_text("utf-8").splitlines() if line.strip()]
        assert len(records) == 1, f"expected exactly one stub invocation, got {len(records)}"
        record = records[0]
        record["leftover_tmp"] = sorted(p.name for p in tmp.iterdir())
        record["user_home_unchanged"] = _snapshot(user_home) == before
        return Launch(proc, record, work, user_home, home, tmp, workdir, passed)


def _snapshot(directory):
    return {
        str(p.relative_to(directory)): p.read_bytes() if p.is_file() else None
        for p in sorted(Path(directory).rglob("*"))
    }


def guard_registration_problems(argv, hook_path):
    """Problems with the wrapper's own interactive-guard registration in an
    argv (empty list: it is registered)."""
    problems = []
    if argv.count(BYPASS_FLAG) != 1:
        problems.append(f"{BYPASS_FLAG} does not appear exactly once")
    values = [
        argv[i + 1]
        for i in range(len(argv) - 1)
        if argv[i] == "-c" and argv[i + 1].startswith(HOOK_KEY_PREFIX)
    ]
    if len(values) != 1:
        problems.append(f"expected one `-c {HOOK_KEY_PREFIX}...` pair, found {len(values)}")
        return problems
    try:
        groups = tomllib.loads(values[0])["hooks"]["PreToolUse"]
        hook = groups[0]["hooks"][0]
        words = shlex.split(hook["command"])
    except (tomllib.TOMLDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        problems.append(f"the PreToolUse registration does not parse ({type(exc).__name__})")
        return problems
    if groups[0].get("matcher") != "Bash" or len(groups) != 1:
        problems.append("the PreToolUse registration is not a single Bash matcher group")
    if words != ["python3", str(hook_path)]:
        problems.append("the registered hook command does not run the wrapper's own guard script")
    return problems


def protective_specification_problems(record, ctx):
    """Problems with a recorded launch of the em-workflow --litellm route:
    what the stub saw must show the protective specification. An empty list
    means the specification is present. Messages name variables and files,
    never credential values."""
    problems = []
    env = record.get("env", {})
    codex_home = env.get("CODEX_HOME")
    home = env.get("HOME")
    work = ctx["work"]
    if not home or not Path(home).resolve().is_relative_to(work):
        problems.append("HOME is not a temporary directory of the test")
    if not codex_home:
        problems.append("CODEX_HOME is not set for codex")
        return problems
    launch_home = Path(codex_home).resolve()
    if launch_home == Path(ctx["user_home"]).resolve():
        problems.append("CODEX_HOME is the user's Codex home, not a launch-dedicated home")
    if not launch_home.is_relative_to(work):
        problems.append("CODEX_HOME is not inside a temporary directory of the test")
    config_text = record.get("config_toml")
    if config_text is None:
        problems.append("the launch home has no config.toml")
    else:
        try:
            projects = tomllib.loads(config_text).get("projects", {})
        except tomllib.TOMLDecodeError:
            problems.append("the launch home config.toml is not valid TOML")
            projects = {}
        trusted = sorted(k for k, v in projects.items() if v.get("trust_level") != "untrusted")
        if trusted:
            problems.append(f"{len(trusted)} project entr(ies) of the launch home are not marked untrusted")
        for directory in ctx["untrusted_directories"]:
            if projects.get(str(directory), {}).get("trust_level") != "untrusted":
                problems.append(f"directory {directory} is not marked untrusted in the launch home")
    if record.get("profile_toml") != ctx["profile_text"]:
        problems.append("the launch home does not carry the user's litellm profile unchanged")
    for field in ("config_toml", "profile_toml"):
        if CREDENTIAL_SENTINEL in (record.get(field) or ""):
            problems.append(f"the credential value of {CREDENTIAL_VAR} reached the launch home file {field}")
    return problems


def credential_leak_problems(*texts):
    """Names of the captured streams that carry the sentinel (indexes only;
    the value itself is never put into a message)."""
    return [
        f"captured stream #{index} carries the value of {CREDENTIAL_VAR}"
        for index, text in enumerate(texts)
        if CREDENTIAL_SENTINEL in text
    ]


def _context(launch, profile_text=PROFILE_TEXT):
    """What the predicate compares a record against: the directories that
    must be marked untrusted are the working directory and every directory
    above it, spelled both physically and the way it was passed."""
    directories = set(_ancestors_inclusive(launch.workdir))
    directories |= set(_ancestors_inclusive(launch.passed))
    return {
        "work": launch.work,
        "user_home": launch.user_home,
        "profile_text": profile_text,
        "untrusted_directories": sorted(directories, key=str),
    }


def _trusting_config(workdir):
    """A user config that trusts the working directory and every directory
    above it, plus an unrelated setting."""
    entries = "".join(
        f"[projects.{_toml_key(d)}]\ntrust_level = \"trusted\"\n\n"
        for d in _ancestors_inclusive(workdir)
    )
    return 'model = "user-pinned-model"\n\n' + entries


def _implicit_config(workdir):
    return 'model = "user-pinned-model"\n'


def _trusting_only_the_repository(workdir):
    return f'[projects.{_toml_key(workdir)}]\ntrust_level = "trusted"\n'


WORKFLOW_WRAPPER = WORKFLOW_SCRIPTS_DIR / WRAPPER_NAME
REVIEW_WRAPPER = REVIEW_SCRIPTS_DIR / WRAPPER_NAME
LITELLM_ARGS = ["--litellm", MODEL]


class TestProtectiveSpecificationOnLitellmRoute(unittest.TestCase):
    """AC-5 / TS1: the changed route (em-workflow --litellm) in both modes."""

    def _check(self, mode, user_config, **kwargs):
        launch = run_stub_launch(
            WORKFLOW_WRAPPER, LITELLM_ARGS, mode=mode, user_config=user_config, **kwargs
        )
        self.assertEqual(launch.proc.returncode, 0, launch.proc.stderr)
        problems = protective_specification_problems(launch.record, _context(launch))
        self.assertEqual(problems, [], f"{mode}: {problems}")
        problems = guard_registration_problems(
            launch.record["argv"], WORKFLOW_SCRIPTS_DIR / HOOK_NAME
        )
        self.assertEqual(problems, [], f"{mode}: {problems}")
        return launch

    def test_ts1_user_config_trusts_the_working_directory_readonly(self):
        self._check("readonly", _trusting_config)

    def test_ts1_user_config_trusts_the_working_directory_readwrite(self):
        self._check("readwrite", _trusting_config)

    def test_ts1_user_config_without_trust_readonly(self):
        self._check("readonly", _implicit_config)

    def test_ts1_user_config_without_trust_readwrite(self):
        # Codex 0.160.0 marks an untrusted working directory trusted on its
        # own when the sandbox is writable; the launch home must already
        # carry an explicit untrusted entry (findings record, P3 readwrite).
        self._check("readwrite", _implicit_config)

    def test_ts1_user_has_no_config_toml_at_all(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self._check(mode, None)

    def test_ts1_working_directory_passed_through_a_symlink(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                launch = self._check(mode, _trusting_config, use_link=True)
                projects = tomllib.loads(launch.record["config_toml"])["projects"]
                self.assertIn(str(launch.passed), projects, "the spelling that was passed")
                self.assertIn(str(launch.workdir), projects, "the physical spelling")

    def test_ts1_no_C_flag_uses_the_callers_working_directory(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self._check(mode, _trusting_config, pass_workdir=False)

    def test_ts1_working_directory_name_with_toml_and_shell_metacharacters(self):
        name = 'we ird\'q"d\\b$HOME`id`;x&y|z<w>v*u?t(s)#r!q~p'
        for mode in MODES:
            with self.subTest(mode=mode):
                launch = self._check(mode, _trusting_config, workdir_name=name)
                projects = tomllib.loads(launch.record["config_toml"])["projects"]
                self.assertIn(str(launch.workdir), projects)

    def test_ts1_launch_home_is_removed_and_users_home_is_untouched(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                launch = self._check(mode, _trusting_config)
                self.assertEqual(launch.record["leftover_tmp"], [])
                self.assertTrue(launch.record["user_home_unchanged"])

    def test_ts1_codex_exit_code_still_surfaces_and_the_home_is_still_removed(self):
        launch = run_stub_launch(
            WORKFLOW_WRAPPER, LITELLM_ARGS, mode="readonly",
            user_config=_trusting_config, stub_exit=3,
        )
        self.assertEqual(launch.proc.returncode, 3)
        self.assertEqual(launch.record["leftover_tmp"], [])

    def test_ts1_launch_composition_other_than_the_home_is_kept(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                launch = self._check(mode, _trusting_config)
                argv = launch.record["argv"]
                width = 4
                self.assertTrue(
                    any(argv[i:i + width] == ["-p", "litellm", "-m", MODEL] for i in range(len(argv))),
                    f"-p litellm -m MODEL missing in {argv!r}",
                )
                self.assertIn("--ignore-rules", argv)
                self.assertNotIn("--ignore-user-config", argv)
                self.assertEqual(argv[0], "exec")
                self.assertEqual(argv[-1].splitlines()[-1], "do the thing")
                self.assertEqual(argv.count("exec"), 1)


class TestRoutesNotObservedExecutingKeepTheirLaunch(unittest.TestCase):
    """AC-3 / AC-4: the em-workflow default route and the em-review default
    route were not observed executing repository hooks; their launch
    composition -- including the Codex home they hand over -- is unchanged."""

    ROUTES = (
        ("workflow-default", WORKFLOW_WRAPPER, []),
        ("review-default", REVIEW_WRAPPER, []),
    )

    def test_codex_home_and_isolation_flags_are_exactly_as_before(self):
        for label, wrapper, route_args in self.ROUTES:
            for mode in MODES:
                with self.subTest(route=label, mode=mode):
                    launch = run_stub_launch(
                        wrapper, route_args, mode=mode, user_config=_trusting_config
                    )
                    self.assertEqual(launch.proc.returncode, 0, launch.proc.stderr)
                    env = launch.record["env"]
                    self.assertEqual(Path(env["CODEX_HOME"]), launch.user_home)
                    self.assertIn("--ignore-user-config", launch.record["argv"])
                    self.assertIn("--ignore-rules", launch.record["argv"])
                    self.assertNotIn("-p", launch.record["argv"])
                    self.assertTrue(launch.record["user_home_unchanged"])


class TestSpecificationCheckIsNotVacuous(unittest.TestCase):
    """Non-vacuity: the predicate that TS1 relies on rejects records that
    differ from a good one only by lacking the specification."""

    @classmethod
    def setUpClass(cls):
        cls.launch = run_stub_launch(
            WORKFLOW_WRAPPER, LITELLM_ARGS, mode="readwrite", user_config=_trusting_config
        )
        cls.ctx = _context(cls.launch)
        cls.good = cls.launch.record

    def test_the_genuine_record_passes(self):
        self.assertEqual(protective_specification_problems(self.good, self.ctx), [])

    def test_a_record_handed_the_users_own_home_is_rejected(self):
        forged = json.loads(json.dumps(self.good))
        forged["env"]["CODEX_HOME"] = str(self.ctx["user_home"])
        self.assertTrue(protective_specification_problems(forged, self.ctx))

    def test_a_record_whose_config_trusts_the_working_directory_is_rejected(self):
        forged = json.loads(json.dumps(self.good))
        forged["config_toml"] = _trusting_config(self.launch.workdir)
        self.assertTrue(protective_specification_problems(forged, self.ctx))

    def test_a_record_whose_config_lacks_the_untrusted_marker_is_rejected(self):
        forged = json.loads(json.dumps(self.good))
        forged["config_toml"] = ""
        self.assertTrue(protective_specification_problems(forged, self.ctx))
        forged["config_toml"] = None
        self.assertTrue(protective_specification_problems(forged, self.ctx))

    def test_a_record_without_the_profile_is_rejected(self):
        forged = json.loads(json.dumps(self.good))
        forged["profile_toml"] = None
        self.assertTrue(protective_specification_problems(forged, self.ctx))

    def test_a_record_with_codex_home_outside_the_temporary_directories_is_rejected(self):
        forged = json.loads(json.dumps(self.good))
        forged["env"]["CODEX_HOME"] = "/nonexistent-elsewhere/.codex"
        self.assertTrue(protective_specification_problems(forged, self.ctx))
        forged = json.loads(json.dumps(self.good))
        forged["env"]["HOME"] = "/nonexistent-elsewhere"
        self.assertTrue(protective_specification_problems(forged, self.ctx))

    def test_a_record_without_the_guard_registration_is_rejected(self):
        argv = list(self.good["argv"])
        self.assertEqual(
            guard_registration_problems(argv, WORKFLOW_SCRIPTS_DIR / HOOK_NAME), []
        )
        without_bypass = [a for a in argv if a != BYPASS_FLAG]
        self.assertTrue(guard_registration_problems(without_bypass, WORKFLOW_SCRIPTS_DIR / HOOK_NAME))
        stripped = []
        i = 0
        while i < len(argv):
            if argv[i] == "-c" and argv[i + 1].startswith(HOOK_KEY_PREFIX):
                i += 2
                continue
            stripped.append(argv[i])
            i += 1
        self.assertTrue(guard_registration_problems(stripped, WORKFLOW_SCRIPTS_DIR / HOOK_NAME))

    def test_the_stub_saw_the_temporary_home_and_codex_home(self):
        env = self.good["env"]
        self.assertTrue(Path(env["HOME"]).resolve().is_relative_to(self.launch.work))
        self.assertTrue(Path(env["CODEX_HOME"]).resolve().is_relative_to(self.launch.work))
        self.assertNotEqual(Path(env["CODEX_HOME"]).resolve(), self.launch.user_home.resolve())


class TestCredentialValueStaysOutOfOutput(unittest.TestCase):
    """NFR5: the credential variable carries a sentinel; it must not appear
    in the wrapper's captured streams or in the launch home's files, and a
    failure message must not carry the value."""

    def test_sentinel_is_absent_from_every_route_in_both_modes(self):
        routes = (
            ("workflow-litellm", WORKFLOW_WRAPPER, LITELLM_ARGS),
            ("workflow-default", WORKFLOW_WRAPPER, []),
            ("review-default", REVIEW_WRAPPER, []),
        )
        for label, wrapper, route_args in routes:
            for mode in MODES:
                with self.subTest(route=label, mode=mode):
                    launch = run_stub_launch(
                        wrapper, route_args, mode=mode, user_config=_trusting_config
                    )
                    self.assertTrue(launch.record["env"]["credential_set"])
                    problems = credential_leak_problems(launch.proc.stdout, launch.proc.stderr)
                    self.assertEqual(problems, [])
                    for field in ("config_toml", "profile_toml"):
                        self.assertNotIn(CREDENTIAL_SENTINEL, launch.record[field] or "")

    def test_leak_checker_rejects_forged_output_and_names_no_value(self):
        problems = credential_leak_problems("ok", f"banner {CREDENTIAL_SENTINEL} banner")
        self.assertEqual(len(problems), 1)
        for message in problems:
            self.assertNotIn(CREDENTIAL_SENTINEL, message)
            self.assertIn(CREDENTIAL_VAR, message)
        forged = {"env": {"HOME": "/x", "CODEX_HOME": "/x/h"}, "config_toml": CREDENTIAL_SENTINEL,
                  "profile_toml": PROFILE_TEXT}
        ctx = {"work": Path("/x"), "user_home": Path("/x/u"), "profile_text": PROFILE_TEXT,
               "untrusted_directories": []}
        messages = protective_specification_problems(forged, ctx)
        self.assertTrue(any(CREDENTIAL_VAR in m for m in messages))
        for message in messages:
            self.assertNotIn(CREDENTIAL_SENTINEL, message)


# --------------------------------------------------------------------------
# TS2: real Codex.
# --------------------------------------------------------------------------

class FakeBackend:
    """A local HTTP server standing in for the model backend: it answers
    every request at once with an HTTP 400 error body. Codex then ends the
    turn immediately, after the session-level hooks have run, and no
    credential or external service is involved. (A closed port would make
    Codex wait for the network indefinitely.)"""

    def __enter__(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(handler):
                length = int(handler.headers.get("Content-Length") or 0)
                handler.rfile.read(length)
                body = json.dumps({"error": {"message": "fake backend", "type": "invalid_request_error"}}).encode()
                handler.send_response(400)
                handler.send_header("Content-Type", "application/json")
                handler.send_header("Content-Length", str(len(body)))
                handler.end_headers()
                handler.wfile.write(body)

            do_GET = do_POST

            def log_message(handler, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)


def _codex_version():
    codex = shutil.which("codex")
    if not codex:
        return None, "codex is not on PATH"
    try:
        with tempfile.TemporaryDirectory() as scratch:
            out = subprocess.run(
                [codex, "--version"], capture_output=True, text=True, timeout=30,
                env={**os.environ, "HOME": scratch, "CODEX_HOME": scratch},
            ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"codex --version failed ({type(exc).__name__})"
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", out)
    return (match.group(1) if match else None), (out.strip() or "no version reported")


def _descendants(root_pid):
    """Every descendant of `root_pid`, read from the process table."""
    table = subprocess.run(
        ["ps", "-e", "-o", "pid=,ppid="], capture_output=True, text=True, timeout=30
    ).stdout
    children = {}
    for line in table.splitlines():
        parts = line.split()
        if len(parts) == 2:
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    found, queue = [], [root_pid]
    while queue:
        for child in children.get(queue.pop(), []):
            found.append(child)
            queue.append(child)
    return found


def _end_tree(root_pid):
    """Ends `root_pid` and everything below it (the wrapper's `timeout`
    puts codex in a process group of its own, so a group signal alone would
    leave it behind)."""
    victims = _descendants(root_pid) + [root_pid]
    for pid in victims:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _run_bounded(cmd, *, env, cwd, bound_seconds):
    """Runs a command bounded in wall-clock time; on the bound the whole
    process tree is ended. Returns (exit code or None, stdout, stderr,
    whether the bound was hit)."""
    proc = subprocess.Popen(
        cmd, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=bound_seconds)
        return proc.returncode, out, err, False
    except subprocess.TimeoutExpired:
        _end_tree(proc.pid)
        out, err = proc.communicate()
        return None, out or "", err or "", True


class TestRepositoryHooksDoNotRunThroughTheWrapper(unittest.TestCase):
    """AC-6 / TS2: real Codex. A repository whose `.codex/` carries hooks
    that write marker files (SessionStart from config.toml, UserPromptSubmit
    from hooks.json); the control launch (pre-change composition, no
    protective specification) must create a marker, the launch through the
    wrapper must not."""

    BOUND_SECONDS = 60

    @classmethod
    def setUpClass(cls):
        version, detail = _codex_version()
        if version != SUPPORTED_CODEX_VERSION:
            raise unittest.SkipTest(
                f"codex {SUPPORTED_CODEX_VERSION} is required; found: {version or detail}"
            )
        if not shutil.which("git"):
            raise unittest.SkipTest("git is required to build the temporary repository")

    def _environment(self, work, user_config, marker_dir, base_url):
        home = work / "home"
        user_home = work / "codex-home"
        tmp = work / "tmp"
        repo = work / "repo"
        for d in (home, user_home, tmp, repo, marker_dir):
            d.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
        (repo / ".codex").mkdir()
        session_marker = marker_dir / "SessionStart"
        prompt_marker = marker_dir / "UserPromptSubmit"
        (repo / ".codex" / "config.toml").write_text(
            "[[hooks.SessionStart]]\n[[hooks.SessionStart.hooks]]\n"
            'type = "command"\n'
            f'command = "printf x > {shlex.quote(str(session_marker))}"\n',
            encoding="utf-8",
        )
        (repo / ".codex" / "hooks.json").write_text(
            json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{
                "type": "command",
                "command": f"printf x > {shlex.quote(str(prompt_marker))}",
            }]}]}}),
            encoding="utf-8",
        )
        (user_home / "litellm.config.toml").write_text(
            PROFILE_TEXT.replace("http://127.0.0.1:9/v1", base_url), encoding="utf-8"
        )
        if user_config is not None:
            (user_home / "config.toml").write_text(user_config(repo.resolve()), encoding="utf-8")
        env = dict(os.environ)
        env.update(HOME=str(home), CODEX_HOME=str(user_home), TMPDIR=str(tmp))
        env[CREDENTIAL_VAR] = CREDENTIAL_SENTINEL
        env.pop("CODEX_OTLP_ENDPOINT", None)
        return repo, env

    def _case(self, mode, user_config):
        sandbox = {"readonly": "read-only", "readwrite": "workspace-write"}[mode]
        with FakeBackend() as backend, \
                tempfile.TemporaryDirectory() as control_s, \
                tempfile.TemporaryDirectory() as wrapper_s:
            control_work = Path(control_s).resolve()
            wrapper_work = Path(wrapper_s).resolve()
            control_markers = control_work / "markers"
            wrapper_markers = wrapper_work / "markers"

            repo, env = self._environment(control_work, user_config, control_markers, backend.base_url)
            # The pre-change composition of the route: no protective
            # specification, the user's own Codex home.
            control_cmd = [
                "codex", "exec", "--color", "never", "--skip-git-repo-check", "--ignore-rules",
                "-s", sandbox, "-C", str(repo), "-p", "litellm", "-m", MODEL,
                BYPASS_FLAG, "reply with the word ok",
            ]
            rc, out, err, timed_out = _run_bounded(
                control_cmd, env=env, cwd=str(repo), bound_seconds=self.BOUND_SECONDS
            )
            self.assertEqual(credential_leak_problems(out, err), [])
            created = sorted(p.name for p in control_markers.iterdir())
            if not created:
                self.skipTest(
                    "the control launch (no protective specification) created no marker "
                    f"(exit {rc}, bound hit: {timed_out}); the real-Codex check cannot decide"
                )

            repo, env = self._environment(wrapper_work, user_config, wrapper_markers, backend.base_url)
            rc, out, err, timed_out = _run_bounded(
                ["bash", str(WORKFLOW_WRAPPER), mode, *LITELLM_ARGS, "-C", str(repo),
                 "reply with the word ok"],
                env=env, cwd=str(repo), bound_seconds=self.BOUND_SECONDS,
            )
            self.assertFalse(timed_out, "the wrapper launch outlived the test's time bound")
            self.assertEqual(credential_leak_problems(out, err), [])
            self.assertIn(
                "session id:", out + err,
                "the wrapper launch never started a Codex session, so a missing marker proves nothing",
            )
            leaked = sorted(p.name for p in wrapper_markers.iterdir())
            self.assertEqual(
                leaked, [],
                f"repository hooks ran through the wrapper (the control created: {created})",
            )

    def test_ts2_readonly_user_config_trusts_the_repository(self):
        self._case("readonly", _trusting_only_the_repository)

    def test_ts2_readwrite_user_config_trusts_the_repository(self):
        self._case("readwrite", _trusting_only_the_repository)

    def test_ts2_readwrite_repository_not_trusted_by_the_user_config(self):
        # Codex 0.160.0 trusts the working directory on its own when the
        # sandbox is writable (findings record, P3 readwrite).
        self._case("readwrite", _implicit_config)


class TestRealCodexCheckSkipsInsteadOfPassing(unittest.TestCase):
    """AC-6: the real-Codex cases skip -- never pass -- when codex is absent,
    does not report 0.160.0, or the control launch creates no marker. The
    TS2 class is run in a child interpreter whose PATH carries (or lacks) a
    fake `codex`; the child's report must say skipped, with no pass."""

    FAKE_CODEX = "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo \"codex-cli {version}\"; exit 0; fi\nexit 0\n"

    def _run_ts2_with_path(self, path_entries):
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(path_entries)
        for name in ("CODEX_HOME", "CODEX_OTLP_ENDPOINT"):
            env.pop(name, None)
        target = f"{Path(__file__).stem}.{TestRepositoryHooksDoNotRunThroughTheWrapper.__name__}"
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", target],
            cwd=str(Path(__file__).resolve().parent), env=env,
            capture_output=True, text=True, timeout=120,
        )
        return proc.returncode, proc.stdout + proc.stderr

    def _assert_only_skips(self, rc, report):
        self.assertEqual(rc, 0, report)
        self.assertIn("skipped", report)
        self.assertNotIn("FAILED", report)
        self.assertNotRegex(report, r"(?m)\.\.\. ok$", "a real-Codex case passed instead of skipping")

    def test_codex_absent_skips(self):
        without_codex = [
            d for d in os.environ.get("PATH", "").split(os.pathsep)
            if d and not (Path(d) / "codex").exists()
        ]
        rc, report = self._run_ts2_with_path(without_codex)
        self._assert_only_skips(rc, report)
        self.assertIn("not on PATH", report)

    def test_other_codex_version_skips(self):
        with tempfile.TemporaryDirectory() as fake_s:
            fake = Path(fake_s)
            (fake / "codex").write_text(self.FAKE_CODEX.format(version="0.159.0"), encoding="utf-8")
            (fake / "codex").chmod(0o755)
            rc, report = self._run_ts2_with_path([fake_s, *os.environ.get("PATH", "").split(os.pathsep)])
        self._assert_only_skips(rc, report)
        self.assertIn("found: 0.159.0", report)

    def test_control_without_marker_skips(self):
        with tempfile.TemporaryDirectory() as fake_s:
            fake = Path(fake_s)
            (fake / "codex").write_text(
                self.FAKE_CODEX.format(version=SUPPORTED_CODEX_VERSION), encoding="utf-8"
            )
            (fake / "codex").chmod(0o755)
            rc, report = self._run_ts2_with_path([fake_s, *os.environ.get("PATH", "").split(os.pathsep)])
        self._assert_only_skips(rc, report)
        self.assertIn("created no marker", report)
        self.assertIn("skipped=3", report, "all three real-Codex cases must skip")


if __name__ == "__main__":
    unittest.main()
