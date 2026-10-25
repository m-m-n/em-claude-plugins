"""Subprocess-driven tests for task0003 of codex-stop-hook-tty-reaper: on its
`--litellm` route, em-workflow's `run_codex_exec.sh` creates the
launch-dedicated Codex home in a per-user cache directory instead of the
temporary directory
(feature-docs/codex-stop-hook-tty-reaper/tasks/task0003.md).

Covers task0003 Acceptance Criteria:

- AC-1 (FR8): on the `--litellm` route, readonly and readwrite, the
  `CODEX_HOME` the stub codex sees is a directory directly under the
  `em-workflow` directory of `XDG_CACHE_HOME` (when it is set to an absolute
  path) or of `HOME`'s `.cache` (when it is unset or relative); never under
  the `TMPDIR` given to the wrapper and never under the user's Codex home.
  The parent `em-workflow` directory is covered both missing and present.
- AC-2: during the launch the launch home exists, is accessible to its
  owner only, and holds exactly `config.toml` plus a byte-identical
  `litellm.config.toml` when the user's Codex home has one; `config.toml`
  parses as TOML and every project entry is `untrusted`, the working
  directory included.
- AC-3: after the wrapper exits (stub exit 0 and non-zero) the launch home
  of the run is gone, nothing is left under `TMPDIR`, a pre-existing parent
  directory is left as it was, and the user's Codex home is unchanged.
- AC-4: with `HOME` empty (or unset) and no absolute `XDG_CACHE_HOME`, the
  `--litellm` route writes one diagnostic line to standard error, exits
  non-zero and never invokes the stub codex.
- AC-5: on the default route the stub sees no `CODEX_HOME` and nothing is
  created under the cache base.
- AC-6 (NFR3): every `--litellm` run in this module that is expected to
  launch invokes the stub codex exactly once (asserted by the harness); the
  existing `tests.test_codex_hook_wrapper_args` module is not edited.
- AC-7 (NFR4): this module imports only standard-library modules, and every
  wrapper run uses a stub `codex` first on PATH and its own HOME,
  XDG_CACHE_HOME (or none) and TMPDIR inside a temporary directory the test
  owns.

Test Notes this module follows:

- The stub codex records, while the launch is in progress, the `CODEX_HOME`
  it sees and that directory's permission bits, listing and file contents,
  because the launch home is removed when the wrapper exits.
- `XDG_CACHE_HOME` and `CODEX_HOME` are removed from the inherited
  environment, and `TMPDIR` is a directory separate from the test's `HOME`
  and `XDG_CACHE_HOME`, so "not under TMPDIR" is a meaningful check even
  though every directory of the test is itself temporary.
- Nothing under em-workflow/ is imported: the wrapper is run as a separate
  process, so no bytecode cache lands in a plugin directory.

Non-vacuity: the location checker and the import checker each carry negative
proofs against forged input, in the style of the neighbouring wrapper test
modules.
"""

import ast
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPER = REPO_ROOT / "em-workflow" / "scripts" / "run_codex_exec.sh"

MODES = ("readonly", "readwrite")
MODEL = "test-model"
LITELLM_ARGS = ["--litellm", MODEL]

# No trailing newline and a non-ASCII byte: a copy that re-encodes or
# normalises the user's profile is not byte-identical.
PROFILE_BYTES = (
    b"# user litellm profile \xc3\xa9\n"
    b'[model_providers.litellm]\nname = "LiteLLM proxy"\nenv_key = "LITELLM_API_KEY"'
)
AUTH_TEXT = '{"token": "user-secret-that-must-not-be-copied"}\n'

# The stub codex records what it can see at launch time: a few environment
# variables, and the permission bits, listing and file contents of the
# CODEX_HOME it was handed.
CODEX_STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import stat
import sys

def read_hex(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().hex()
    except OSError:
        return None

home = os.environ.get("CODEX_HOME")
is_dir = bool(home) and os.path.isdir(home)
entries = sorted(os.listdir(home)) if is_dir else None
record = {
    "argv": sys.argv[1:],
    "env": {
        name: os.environ.get(name)
        for name in ("HOME", "XDG_CACHE_HOME", "TMPDIR", "CODEX_HOME", "PATH")
    },
    "launch_home_is_dir": is_dir,
    "mode": stat.S_IMODE(os.stat(home).st_mode) if is_dir else None,
    "entries": entries,
    "files": {n: read_hex(os.path.join(home, n)) for n in entries} if is_dir else None,
}
with open(os.environ["CODEX_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\\n")
sys.exit(int(os.environ.get("CODEX_STUB_EXIT", "0")))
"""


def _write_executable(path, source):
    path.write_text(source, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _snapshot(directory):
    return {
        str(p.relative_to(directory)): p.read_bytes() if p.is_file() else None
        for p in sorted(Path(directory).rglob("*"))
    }


class Run:
    """Everything one wrapper run through the stub produced. All paths are
    kept as `Path` objects of directories that no longer exist; the facts
    that needed the directories were collected before they were removed."""

    def __init__(self, **fields):
        self.__dict__.update(fields)

    def launch(self):
        """The single recorded stub invocation. The run must have invoked the
        stub codex exactly once (AC-6) and exited with the stub's status."""
        assert len(self.records) == 1, (
            f"expected exactly one stub invocation, got {len(self.records)}; "
            f"exit={self.proc.returncode} stderr={self.proc.stderr!r}"
        )
        return self.records[0]


def run_wrapper(
    *,
    mode,
    route,
    xdg="unset",
    preexisting="nothing",
    home="set",
    user_home_via_env=True,
    user_profile=PROFILE_BYTES,
    stub_exit=0,
    pass_workdir=True,
):
    """Runs the em-workflow wrapper once with a stub `codex` first on PATH.

    route: "litellm" or "default".
    xdg: "unset", "absolute" (a directory with missing ancestors) or
        "relative" (a relative path).
    preexisting: "nothing", "cache_base" (only the cache base exists) or
        "parent" (the `em-workflow` directory exists and holds a sentinel).
    home: "set" (the test's own HOME), "empty" (HOME="") or "unset".
    user_home_via_env: the user's Codex home is given by CODEX_HOME (True)
        or is the default `HOME/.codex` (False).
    The route "default" never sets CODEX_HOME (AC-5)."""
    with tempfile.TemporaryDirectory() as work_s:
        work = Path(work_s).resolve()
        stub_dir = work / "stub-bin"
        stub_dir.mkdir()
        _write_executable(stub_dir / "codex", CODEX_STUB_SOURCE)
        log_path = work / "stub.log"
        home_dir = work / "home"
        home_dir.mkdir()
        tmp = work / "tmp"
        tmp.mkdir()
        workdir = work / "repo"
        workdir.mkdir()
        caller_cwd = work / "caller-cwd"
        caller_cwd.mkdir()

        via_env = user_home_via_env and route == "litellm"
        user_home = work / "user-codex-home" if via_env else home_dir / ".codex"
        user_home.mkdir()
        (user_home / "auth.json").write_text(AUTH_TEXT, encoding="utf-8")
        (user_home / "config.toml").write_text(
            f'[projects."{workdir}"]\ntrust_level = "trusted"\n', encoding="utf-8"
        )
        if user_profile is not None:
            (user_home / "litellm.config.toml").write_bytes(user_profile)
        user_home_before = _snapshot(user_home)

        env = dict(os.environ)
        for name in ("XDG_CACHE_HOME", "CODEX_HOME", "CODEX_OTLP_ENDPOINT", "HOME"):
            env.pop(name, None)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        if home == "set":
            env["HOME"] = str(home_dir)
        elif home == "empty":
            env["HOME"] = ""
        env["TMPDIR"] = str(tmp)
        if via_env:
            env["CODEX_HOME"] = str(user_home)
        env["CODEX_STUB_LOG"] = str(log_path)
        env["CODEX_STUB_EXIT"] = str(stub_exit)

        # AC-7: the `codex` the wrapper will find is the stub, never a real
        # one, and every directory it is given is one this run owns.
        resolved = shutil.which("codex", path=env["PATH"])
        assert resolved == str(stub_dir / "codex"), resolved

        xdg_base = work / "xdg" / "nested" / "cache"
        if xdg == "absolute":
            env["XDG_CACHE_HOME"] = str(xdg_base)
            cache_base = xdg_base
        elif xdg == "relative":
            env["XDG_CACHE_HOME"] = "relative-cache"
            cache_base = home_dir / ".cache" if home == "set" else None
        else:
            cache_base = home_dir / ".cache" if home == "set" else None
        parent = cache_base / "em-workflow" if cache_base is not None else None

        if preexisting == "cache_base" and cache_base is not None:
            cache_base.mkdir(parents=True)
        elif preexisting == "parent" and parent is not None:
            parent.mkdir(parents=True)
            (parent / "sentinel").write_text("keep", encoding="utf-8")

        args = [mode, *(LITELLM_ARGS if route == "litellm" else [])]
        if pass_workdir:
            args += ["-C", str(workdir)]
        args += ["do the thing"]
        proc = subprocess.run(
            ["bash", str(WRAPPER), *args],
            env=env,
            cwd=str(caller_cwd),
            capture_output=True,
            text=True,
            timeout=60,
        )

        records = []
        if log_path.is_file():
            records = [
                json.loads(line)
                for line in log_path.read_text("utf-8").splitlines()
                if line.strip()
            ]
        codex_homes = [r["env"]["CODEX_HOME"] for r in records if r["env"]["CODEX_HOME"]]
        return Run(
            proc=proc,
            records=records,
            work=work,
            home_dir=home_dir,
            tmp=tmp,
            workdir=workdir,
            caller_cwd=caller_cwd,
            user_home=user_home,
            cache_base=cache_base,
            parent=parent,
            stub_dir=stub_dir,
            tmp_after=sorted(p.name for p in tmp.iterdir()),
            parent_after=(
                sorted(p.name for p in parent.iterdir())
                if parent is not None and parent.is_dir()
                else None
            ),
            cache_base_exists_after=(
                cache_base.exists() if cache_base is not None else None
            ),
            relative_base_exists_after=(caller_cwd / "relative-cache").exists(),
            launch_homes_exist_after=[Path(h).exists() for h in codex_homes],
            user_home_unchanged=_snapshot(user_home) == user_home_before,
        )


def location_problems(record, parent, tmp, user_home):
    """Problems with where a recorded launch's CODEX_HOME is (empty list: it
    is a directory directly under `parent`, outside `tmp` and outside the
    user's Codex home)."""
    codex_home = record["env"]["CODEX_HOME"]
    if not codex_home:
        return ["CODEX_HOME is not set for codex"]
    problems = []
    launch_home = Path(codex_home)
    if parent is None or launch_home.parent.resolve() != Path(parent).resolve():
        problems.append(f"CODEX_HOME is not directly under {parent}")
    resolved = launch_home.resolve()
    if resolved.is_relative_to(Path(tmp).resolve()):
        problems.append("CODEX_HOME is under TMPDIR")
    if resolved.is_relative_to(Path(user_home).resolve()):
        problems.append("CODEX_HOME is under the user's Codex home")
    return problems


def third_party_imports(source):
    """Top-level module names imported by `source` that are not part of the
    standard library."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return sorted(found - set(sys.stdlib_module_names))


class LaunchHomeTestCase(unittest.TestCase):
    def assert_launched_under_parent(self, run, label=""):
        record = run.launch()
        problems = location_problems(record, run.parent, run.tmp, run.user_home)
        self.assertEqual(problems, [], f"{label}: {problems} (CODEX_HOME={record['env']['CODEX_HOME']})")
        return record


class TestLaunchHomeLocation(LaunchHomeTestCase):
    """AC-1: where the launch home is created."""

    def test_absolute_xdg_cache_home_holds_the_launch_home_under_em_workflow(self):
        for mode in MODES:
            for preexisting in ("nothing", "cache_base", "parent"):
                with self.subTest(mode=mode, preexisting=preexisting):
                    run = run_wrapper(
                        mode=mode, route="litellm", xdg="absolute", preexisting=preexisting
                    )
                    self.assertEqual(run.proc.returncode, 0, run.proc.stderr)
                    self.assertEqual(run.parent, run.work / "xdg" / "nested" / "cache" / "em-workflow")
                    self.assert_launched_under_parent(run)

    def test_unset_xdg_cache_home_holds_the_launch_home_under_home_cache_em_workflow(self):
        for mode in MODES:
            for preexisting in ("nothing", "cache_base", "parent"):
                for via_env in (True, False):
                    with self.subTest(mode=mode, preexisting=preexisting, user_home_via_env=via_env):
                        run = run_wrapper(
                            mode=mode,
                            route="litellm",
                            xdg="unset",
                            preexisting=preexisting,
                            user_home_via_env=via_env,
                        )
                        self.assertEqual(run.proc.returncode, 0, run.proc.stderr)
                        self.assertEqual(run.parent, run.home_dir / ".cache" / "em-workflow")
                        self.assert_launched_under_parent(run)

    def test_relative_xdg_cache_home_is_ignored_in_favour_of_home_cache(self):
        for mode in MODES:
            for preexisting in ("nothing", "parent"):
                with self.subTest(mode=mode, preexisting=preexisting):
                    run = run_wrapper(
                        mode=mode, route="litellm", xdg="relative", preexisting=preexisting
                    )
                    self.assertEqual(run.proc.returncode, 0, run.proc.stderr)
                    self.assertEqual(run.parent, run.home_dir / ".cache" / "em-workflow")
                    self.assert_launched_under_parent(run)
                    self.assertFalse(
                        run.relative_base_exists_after,
                        "the relative XDG_CACHE_HOME was created under the working directory",
                    )

    def test_location_checker_flags_forged_records(self):
        parent = Path("/c/em-workflow")
        tmp = Path("/t")
        user_home = Path("/u/.codex")

        def forged(codex_home):
            return {"env": {"CODEX_HOME": codex_home}}

        self.assertEqual(location_problems(forged("/c/em-workflow/h.abc"), parent, tmp, user_home), [])
        self.assertTrue(location_problems(forged(None), parent, tmp, user_home))
        self.assertTrue(location_problems(forged("/t/codex-launch-home.abc"), parent, tmp, user_home))
        self.assertTrue(location_problems(forged("/u/.codex/h.abc"), parent, tmp, user_home))
        self.assertTrue(location_problems(forged("/c/em-workflow/x/h.abc"), parent, tmp, user_home))
        self.assertTrue(location_problems(forged("/c/other/h.abc"), parent, tmp, user_home))
        self.assertTrue(location_problems(forged("/c/em-workflow/h.abc"), None, tmp, user_home))
        self.assertTrue(location_problems(forged("/c/em-workflow/h.abc"), parent, Path("/c"), user_home))
        self.assertTrue(
            location_problems(forged("/c/em-workflow/h.abc"), parent, tmp, Path("/c/em-workflow"))
        )


class TestLaunchHomeContent(LaunchHomeTestCase):
    """AC-2: the relocated launch home holds what it held before."""

    def test_launch_home_is_owner_only_and_holds_exactly_the_wrapper_files(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                run = run_wrapper(mode=mode, route="litellm", xdg="absolute")
                record = self.assert_launched_under_parent(run)
                self.assertTrue(record["launch_home_is_dir"], "the launch home does not exist during the launch")
                self.assertEqual(record["mode"] & 0o077, 0, oct(record["mode"]))
                self.assertEqual(record["mode"] & 0o700, 0o700, oct(record["mode"]))
                self.assertEqual(record["entries"], ["config.toml", "litellm.config.toml"])
                self.assertEqual(
                    bytes.fromhex(record["files"]["litellm.config.toml"]), PROFILE_BYTES
                )

    def test_launch_home_without_a_user_profile_holds_only_config_toml(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                run = run_wrapper(mode=mode, route="litellm", xdg="absolute", user_profile=None)
                record = self.assert_launched_under_parent(run)
                self.assertEqual(record["entries"], ["config.toml"])

    def test_config_toml_marks_every_project_untrusted_including_the_working_directory(self):
        for mode in MODES:
            for pass_workdir in (True, False):
                with self.subTest(mode=mode, pass_workdir=pass_workdir):
                    run = run_wrapper(
                        mode=mode, route="litellm", xdg="absolute", pass_workdir=pass_workdir
                    )
                    record = self.assert_launched_under_parent(run)
                    config = tomllib.loads(bytes.fromhex(record["files"]["config.toml"]).decode("utf-8"))
                    projects = config.get("projects", {})
                    self.assertTrue(projects, "config.toml has no project entry")
                    levels = {key: value.get("trust_level") for key, value in projects.items()}
                    self.assertEqual(
                        {key: level for key, level in levels.items() if level != "untrusted"}, {}
                    )
                    working_directory = run.workdir if pass_workdir else run.caller_cwd
                    self.assertEqual(levels.get(str(working_directory)), "untrusted")


class TestLaunchHomeRemoval(LaunchHomeTestCase):
    """AC-3: the relocated launch home does not outlive the wrapper."""

    def _check_removed(self, run, stub_exit, preexisting):
        self.assertEqual(run.proc.returncode, stub_exit, run.proc.stderr)
        self.assert_launched_under_parent(run)
        self.assertEqual(run.launch_homes_exist_after, [False], "the launch home outlived the wrapper")
        self.assertEqual(run.tmp_after, [], "the run left something under TMPDIR")
        self.assertEqual(
            run.parent_after, ["sentinel"] if preexisting == "parent" else [],
            "the parent directory does not hold exactly what it held before the run",
        )
        self.assertTrue(run.user_home_unchanged, "the user's Codex home changed")

    def test_launch_home_is_removed_when_codex_exits_zero_and_non_zero(self):
        for mode in MODES:
            for stub_exit in (0, 3):
                for preexisting in ("nothing", "parent"):
                    with self.subTest(mode=mode, stub_exit=stub_exit, preexisting=preexisting):
                        run = run_wrapper(
                            mode=mode,
                            route="litellm",
                            xdg="absolute",
                            preexisting=preexisting,
                            stub_exit=stub_exit,
                        )
                        self._check_removed(run, stub_exit, preexisting)

    def test_launch_home_is_removed_under_the_home_cache_fallback(self):
        for stub_exit in (0, 3):
            with self.subTest(stub_exit=stub_exit):
                run = run_wrapper(
                    mode="readwrite", route="litellm", xdg="unset", stub_exit=stub_exit
                )
                self._check_removed(run, stub_exit, "nothing")


class TestCacheBaseCannotBeDetermined(unittest.TestCase):
    """AC-4: without HOME and without an absolute XDG_CACHE_HOME the
    --litellm route stops before launching codex."""

    def _check_refused(self, run):
        self.assertNotEqual(run.proc.returncode, 0, "the wrapper exited 0")
        lines = [line for line in run.proc.stderr.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"expected one diagnostic line, got {run.proc.stderr!r}")
        self.assertEqual(run.records, [], "the stub codex was invoked")
        self.assertEqual(run.tmp_after, [], "the run left something under TMPDIR")
        self.assertFalse(run.relative_base_exists_after)

    def test_empty_home_and_unset_xdg_cache_home_is_refused(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self._check_refused(
                    run_wrapper(mode=mode, route="litellm", xdg="unset", home="empty")
                )

    def test_unset_home_and_unset_xdg_cache_home_is_refused(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self._check_refused(
                    run_wrapper(mode=mode, route="litellm", xdg="unset", home="unset")
                )

    def test_empty_home_and_relative_xdg_cache_home_is_refused(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self._check_refused(
                    run_wrapper(mode=mode, route="litellm", xdg="relative", home="empty")
                )

    def test_empty_home_with_an_absolute_xdg_cache_home_still_launches(self):
        run = run_wrapper(mode="readonly", route="litellm", xdg="absolute", home="empty")
        self.assertEqual(run.proc.returncode, 0, run.proc.stderr)
        record = run.launch()
        launch_home = Path(record["env"]["CODEX_HOME"])
        self.assertEqual(launch_home.parent, run.work / "xdg" / "nested" / "cache" / "em-workflow")


class TestDefaultRouteUnchanged(unittest.TestCase):
    """AC-5: the default route neither sets CODEX_HOME nor creates anything
    under the cache base."""

    def test_default_route_sets_no_codex_home_and_creates_nothing_under_the_cache_base(self):
        for mode in MODES:
            for xdg in ("unset", "absolute"):
                with self.subTest(mode=mode, xdg=xdg):
                    run = run_wrapper(mode=mode, route="default", xdg=xdg)
                    self.assertEqual(run.proc.returncode, 0, run.proc.stderr)
                    record = run.launch()
                    self.assertIsNone(record["env"]["CODEX_HOME"])
                    self.assertFalse(
                        run.cache_base_exists_after, f"{run.cache_base} was created"
                    )
                    self.assertEqual(run.tmp_after, [])


class TestHarnessIsolation(unittest.TestCase):
    """AC-7: the module is standard-library only and its runs are confined."""

    def test_module_imports_only_standard_library_modules(self):
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertEqual(third_party_imports(source), [])

    def test_import_checker_flags_a_third_party_import(self):
        self.assertEqual(third_party_imports("import os\nimport yaml\nfrom pytest import x\n"), ["pytest", "yaml"])
        self.assertEqual(third_party_imports("import os.path\nfrom pathlib import Path\n"), [])

    def test_every_run_uses_a_stub_codex_and_directories_the_test_owns(self):
        run = run_wrapper(mode="readonly", route="litellm", xdg="absolute")
        self.assertEqual(run.proc.returncode, 0, run.proc.stderr)
        env = run.launch()["env"]
        self.assertEqual(env["PATH"].split(os.pathsep)[0], str(run.stub_dir))
        for name in ("HOME", "XDG_CACHE_HOME", "TMPDIR"):
            self.assertTrue(
                Path(env[name]).resolve().is_relative_to(run.work), f"{name}={env[name]}"
            )
        self.assertNotEqual(Path(env["TMPDIR"]).resolve(), Path(env["HOME"]).resolve())
        self.assertFalse(Path(env["TMPDIR"]).resolve().is_relative_to(Path(env["HOME"]).resolve()))
        self.assertFalse(
            Path(env["TMPDIR"]).resolve().is_relative_to(Path(env["XDG_CACHE_HOME"]).resolve())
        )


if __name__ == "__main__":
    unittest.main()
