"""Contract tests for the `cd "<P>" && <approved command>` allowance in
`em-workflow/hooks/bash_guard.py` (feature implementer-cd-verbatim-conflict,
task0001).

Every case drives the hook as a subprocess with PreToolUse JSON on standard
input and reads the decision from standard output, in the same shape as
`tests/test_loop_command_guard.py`. The expected decision is one of three:

- `allow`  -- a JSON `permissionDecision: allow` on standard output.
- `deny`   -- a JSON `permissionDecision: deny` on standard output.
- `silent` -- no output at all (no decision; the normal permission flow
  applies).

Isolation: the approval store is a temporary file selected through
`EM_WORKFLOW_APPROVALS`, `CLAUDE_PROJECT_DIR` is removed from the hook's
environment, and every repository is a temporary git repository. The real
approval store and the real repository's workflow.yaml are never read.
Paths used for comparison are realpaths, so a temporary directory reached
through a symbolic link does not skew the cases.

Covers task0001 Acceptance Criteria
(feature-docs/implementer-cd-verbatim-conflict/tasks/task0001.md):

- AC-1: allow for `cd "P" && X` (syntax and path conditions met, X approved).
- AC-2: silent for every form that breaks a syntax condition.
- AC-3: silent for every form that breaks a path condition.
- AC-4: a refusal pattern in X still denies, with the refusal reason.
- AC-5: commands without a `cd` prefix are judged as before; no new deny.
- AC-6: the guidance of the unapproved deny names the three audiences.
- AC-7: standard-library-only imports; no `status` substring in the
  executable text of the hook.

Feature is-below-physical-fallback, task0001
(feature-docs/is-below-physical-fallback/tasks/task0001.md): the path check
also accepts a path that Bash reaches through its physical-path fallback
(the logical path is not an existing directory, the physical path is an
existing directory strictly below the area).

- AC-1: `/proc/self/root/..` followed by an absolute worktree path was
  allowed; it is no longer allowed (feature cd-prefix-process-dependent-paths:
  a path under /proc or /dev/fd fails the path check).
- AC-2: a link outside the area, `..`, then a name under the target's parent
  is allowed (logical path absent, or an existing file).
- AC-3 (TM-1): a logical destination that exists outside the area is never
  allowed, whatever the physical path is.
- AC-4 (TM-2): when the logical path is not a directory, a physical path that
  is not an existing directory strictly below the area is not allowed.
- AC-5 (TM-4): an embedded NUL makes the path check return False.
- AC-7: the hook docstring and the protocol's Verbatim execution rule state
  the new path condition.

Feature cd-prefix-non-directory-dotdot, task0001
(feature-docs/cd-prefix-non-directory-dotdot/tasks/task0001.md): the physical
path counts as an existing directory only when the operating system resolves
the path exactly as written to a directory, so a regular file, a missing
component, or a link to either, placed before a `..`, is never allowed.

- AC-1: the path check is False for `<area>/afile/../task0001` and
  `<area>/task0001/does-not-exist/..`, with or without `/proc/self/root/..`
  in front, and still True for `<area>/task0001` and `<root>/hop/../sub`.
- AC-2, AC-3: the same forms are silent through the hook.
- AC-4: the fixture layout shows the forms were allowed before, and the
  decision does not depend on strict-mode realpath.
- AC-5: every existing case above is left as it was.
- AC-6: the path check starts no child process.
- AC-7: a resolution error or a NUL in an added form makes the check False.

Feature cd-prefix-process-dependent-paths, task0001
(feature-docs/cd-prefix-process-dependent-paths/tasks/task0001.md): the path
check is False for a path that is, or passes through, a location under /proc
or /dev/fd, because the operating system resolves such a path against the
process that asks. The hook process and the Bash process can differ, so the
form must never be allowed. This is judged on the path as written, on each
stage reached while resolving the logical path and the physical path component
by component, and on the target of each link followed.

- AC-1: the hook subprocess runs in a working directory of its own
  (`Fixture.run_hook(..., process_cwd=...)`); `/proc/self/cwd/<name>` and
  `/proc/self/cwd/../<name>` are not allowed.
- AC-2: the path check is False for the /proc and /dev/fd forms and their
  lexical variants.
- AC-3: the path check is False for a link inside the area that points at one.
- AC-4: directories named `proc`, `procfoo` and `dev/fd` inside the area, and
  the existing in-area forms, are still below the area.
- AC-5: the `/proc/self/root/..` prefix form is silent; no new deny.
- AC-6: a link loop, a chain beyond the followed-link bound and a probe or
  link-reading error make the check False; the hook exits 0 and writes nothing
  to stderr.
- AC-7: the signature and the caller of the path check are unchanged; the path
  check starts no child process for the added forms.

Standard library only.
"""

import ast
import contextlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "bash_guard.py"
PROTOCOL_PATH = REPO_ROOT / "em-workflow" / "references" / "command-execution-protocol.md"

ALLOW = "allow"
DENY = "deny"
SILENT = "silent"

ENV_PREFIXED = (
    "CARGO_TARGET_DIR=src-tauri/target cargo test "
    "--manifest-path src-tauri/Cargo.toml --lib"
)
AMPERSAND_COMMAND = "a && b"
PLAIN_COMMAND = "make test"
SUDO_COMMAND = "sudo make test"
DECLARED_COMMAND = "make lint"
UNRELATED_COMMAND = "make build"

APPROVED_COMMANDS = (PLAIN_COMMAND, ENV_PREFIXED, AMPERSAND_COMMAND)


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


class Fixture:
    """Temporary repositories, approval stores and a git call logger."""

    def __init__(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="bash-guard-cd-")))
        root = self.root

        # Repository 1: the repository the hook runs in.
        self.repo = root / "repo1"
        _make_repo(self.repo)
        self.region = self.repo / ".claude" / "worktrees" / "em-workflow"
        self.inside = self.region / "task0001"
        self.deep = self.inside / "sub" / "deeper"
        self.deep.mkdir(parents=True)
        for name in (
            "dollar$dir",
            "back`tick",
            "back\\slash",
            "new\nline",
            "x && y",
            "with space",
        ):
            (self.region / name).mkdir()
        self.dollar = self.region / "dollar$dir"
        self.backtick = self.region / "back`tick"
        self.backslash = self.region / "back\\slash"
        self.newline = self.region / "new\nline"
        self.ampersand = self.region / "x && y"
        self.spaced = self.region / "with space"
        self.file = self.region / "afile"
        self.file.write_text("not a directory\n", encoding="utf-8")
        self.missing = self.region / "does-not-exist"
        #   area/link-to-file -> area/afile; area/dangling -> area/gone (absent)
        self.link_to_file = self.region / "link-to-file"
        os.symlink(self.file, self.link_to_file)
        self.dangling = self.region / "dangling"
        os.symlink(self.region / "gone", self.dangling)
        self.sibling = self.repo / ".claude" / "worktrees" / "em-workflow-x" / "task0001"
        self.sibling.mkdir(parents=True)

        # Layout for the physical-path fallback: forms whose logical path is
        # not an existing directory while the physical path is. Everything
        # lives under the temporary root.
        self.elsewhere = self.repo / ".claude" / "worktrees" / "elsewhere"
        self.elsewhere.mkdir()
        #   root/hop -> area/task0001/sub          (link outside the area)
        self.hop = root / "hop"
        os.symlink(self.inside / "sub", self.hop)
        #   root/hopdir/hop -> area/task0001/sub, root/hopdir/sub is a file
        self.hopdir = root / "hopdir"
        self.hopdir.mkdir()
        os.symlink(self.inside / "sub", self.hopdir / "hop")
        (self.hopdir / "sub").write_text("not a directory\n", encoding="utf-8")
        #   root/hop-task -> area/task0001; root/hop-sibling -> worktrees/em-workflow-x
        self.hop_task = root / "hop-task"
        os.symlink(self.inside, self.hop_task)
        self.hop_sibling = root / "hop-sibling"
        os.symlink(self.sibling.parent, self.hop_sibling)
        #   area/hop-in -> area/task0001/sub/deeper (link inside the area)
        self.hop_in = self.region / "hop-in"
        os.symlink(self.inside / "sub" / "deeper", self.hop_in)
        #   a directory inside the area that mirrors the sibling's layout
        self.twin = self.inside / "em-workflow-x" / "task0001"
        self.twin.mkdir(parents=True)

        # A directory outside every worktree area, and a link to it placed
        # inside the area.
        self.outside = root / "outside"
        self.outside.mkdir()
        self.link_out = self.region / "link-out"
        os.symlink(self.outside, self.link_out)
        self.dotdot = Path(
            os.path.join(str(self.inside), *([".."] * 5), "outside")
        )

        # A real git worktree below the area, used as the hook's cwd.
        self.worktree = self.region / "wtree"
        _git(self.repo, "worktree", "add", "-q", str(self.worktree), "-b", "wtree")

        # Repository 2: same layout, different repository.
        self.repo2 = root / "repo2"
        _make_repo(self.repo2)
        self.other_inside = self.repo2 / ".claude" / "worktrees" / "em-workflow" / "task0001"
        self.other_inside.mkdir(parents=True)

        # A directory that is not a git repository.
        self.nongit = root / "plain"
        self.nongit.mkdir()

        # A declared (workflow.yaml) but never approved command.
        wf_dir = self.repo / "feature-docs" / "demo"
        wf_dir.mkdir(parents=True)
        (wf_dir / "workflow.yaml").write_text(
            f"test_command: {DECLARED_COMMAND}\n", encoding="utf-8"
        )

        # git call logger: lets a test see which cwd / arguments git ran with.
        self.git_log = root / "git-calls.log"
        shim_dir = root / "shim"
        shim_dir.mkdir()
        real_git = shutil.which("git")
        shim = shim_dir / "git"
        shim.write_text(
            "#!/bin/sh\n"
            'printf \'%s\\t%s\\n\' "$PWD" "$*" >> "$GIT_SHIM_LOG"\n'
            f'exec "{real_git}" "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
        self.shim_dir = shim_dir

        # Approval stores.
        self.store = root / "approvals-main.json"
        self.store_sudo = root / "approvals-sudo.json"
        self.store_nongit = root / "approvals-nongit.json"
        self.record(self.store, self.repo, APPROVED_COMMANDS)
        self.record(self.store_nongit, self.nongit, APPROVED_COMMANDS)
        key = _git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        # `--record` refuses refusal patterns, so this store is written directly.
        self.store_sudo.write_text(
            json.dumps(
                {"version": 1, "projects": {key: {"approved_commands": [SUDO_COMMAND]}}}
            ),
            encoding="utf-8",
        )

    def tokens(self):
        return {
            "@IN@": str(self.inside),
            "@DEEP@": str(self.deep),
            "@REGION@": str(self.region),
            "@SIBLING@": str(self.sibling),
            "@OUT@": str(self.outside),
            "@OTHER@": str(self.other_inside),
            "@DOTDOT@": str(self.dotdot),
            "@LINK@": str(self.link_out),
            "@FILE@": str(self.file),
            "@MISSING@": str(self.missing),
            "@DOLLAR@": str(self.dollar),
            "@BACKTICK@": str(self.backtick),
            "@BACKSLASH@": str(self.backslash),
            "@NEWLINE@": str(self.newline),
            "@AMP@": str(self.ampersand),
            "@SPACED@": str(self.spaced),
            "@WT@": str(self.worktree),
            "@HOP@": str(self.hop),
            "@HOPDIR@": str(self.hopdir),
            "@HOPTASK@": str(self.hop_task),
            "@HOPSIB@": str(self.hop_sibling),
            "@HOPIN@": str(self.hop_in),
            "@LINKFILE@": str(self.link_to_file),
            "@DANGLING@": str(self.dangling),
        }

    def expand(self, template):
        for token, value in self.tokens().items():
            template = template.replace(token, value)
        return template

    def env(self, store, extra=None):
        env = _clean_env()
        env["EM_WORKFLOW_APPROVALS"] = str(store)
        env["GIT_CEILING_DIRECTORIES"] = str(self.root)
        if extra:
            env.update(extra)
        return env

    def record(self, store, project_dir, commands):
        proc = subprocess.run(
            [sys.executable, str(GUARD_PATH), "--record", "--project-dir", str(project_dir)],
            input="\n".join(commands) + "\n",
            capture_output=True,
            text=True,
            env=self.env(store),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"--record failed: {proc.stderr}")

    def run_hook(self, command, cwd, store=None, extra_env=None, process_cwd=None):
        """Run the hook as a subprocess. The JSON payload's `cwd` is always
        `cwd`; the subprocess's own working directory is `cwd` too unless
        `process_cwd` names another one."""
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
        proc = subprocess.run(
            [sys.executable, str(GUARD_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env(store or self.store, extra_env),
            cwd=str(cwd if process_cwd is None else process_cwd),
        )
        return proc

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


# (expected decision, label, command template)
ALLOW_CASES = (
    (ALLOW, "plain approved command", 'cd "@IN@" && ' + PLAIN_COMMAND),
    (ALLOW, "approved command that starts with an env assignment", 'cd "@IN@" && ' + ENV_PREFIXED),
    (ALLOW, "approved command that itself contains &&", 'cd "@IN@" && ' + AMPERSAND_COMMAND),
    (ALLOW, "deeper directory below the area", 'cd "@DEEP@" && ' + PLAIN_COMMAND),
    (ALLOW, "no space before &&", 'cd "@IN@"&& ' + PLAIN_COMMAND),
    (ALLOW, "no space after &&", 'cd "@IN@" &&' + PLAIN_COMMAND),
    (ALLOW, "tabs around the path and &&", 'cd\t"@IN@"\t&&\t' + PLAIN_COMMAND),
    (ALLOW, "several spaces everywhere", 'cd   "@IN@"   &&   ' + PLAIN_COMMAND),
    (ALLOW, "surrounding whitespace on the command", '  cd "@IN@" && ' + PLAIN_COMMAND + "  \n"),
    (ALLOW, "path containing && is not used for splitting", 'cd "@AMP@" && ' + PLAIN_COMMAND),
    (ALLOW, "path containing a space", 'cd "@SPACED@" && ' + PLAIN_COMMAND),
    (ALLOW, "a git worktree below the area", 'cd "@WT@" && ' + PLAIN_COMMAND),
)

SYNTAX_CASES = (
    (SILENT, "unquoted path", 'cd @IN@ && ' + PLAIN_COMMAND),
    (SILENT, "single-quoted path", "cd '@IN@' && " + PLAIN_COMMAND),
    (SILENT, "relative path, bare name", 'cd "task0001" && ' + PLAIN_COMMAND),
    (SILENT, "relative path that resolves into the area from cwd",
     'cd "./.claude/worktrees/em-workflow/task0001" && ' + PLAIN_COMMAND),
    (SILENT, "path with a dollar sign (directory exists)", 'cd "@DOLLAR@" && ' + PLAIN_COMMAND),
    (SILENT, "path with a variable reference", 'cd "@IN@/$HOME" && ' + PLAIN_COMMAND),
    (SILENT, "path with a backtick (directory exists)", 'cd "@BACKTICK@" && ' + PLAIN_COMMAND),
    (SILENT, "path with a command substitution", 'cd "@IN@/$(true)" && ' + PLAIN_COMMAND),
    (SILENT, "path with a backslash (directory exists)", 'cd "@BACKSLASH@" && ' + PLAIN_COMMAND),
    (SILENT, "path with a newline (directory exists)", 'cd "@NEWLINE@" && ' + PLAIN_COMMAND),
    (SILENT, "cd with -P", 'cd -P "@IN@" && ' + PLAIN_COMMAND),
    (SILENT, "cd with --", 'cd -- "@IN@" && ' + PLAIN_COMMAND),
    (SILENT, "two path arguments", 'cd "@IN@" "@IN@" && ' + PLAIN_COMMAND),
    (SILENT, "semicolon between the closing quote and &&",
     'cd "@IN@" ; true && ' + PLAIN_COMMAND),
    (SILENT, "pipe between the closing quote and &&",
     'cd "@IN@" | true && ' + PLAIN_COMMAND),
    (SILENT, "newline between the closing quote and &&",
     'cd "@IN@"\n&& ' + PLAIN_COMMAND),
    (SILENT, "second cd in the prefix, remainder not approved",
     'cd "@IN@" && cd "@IN@" && ' + PLAIN_COMMAND),
    (SILENT, "command added before the approved string",
     'cd "@IN@" && echo x && ' + PLAIN_COMMAND),
    (SILENT, "command added after with semicolon",
     'cd "@IN@" && ' + PLAIN_COMMAND + " ; echo x"),
    (SILENT, "command added after with &&",
     'cd "@IN@" && ' + PLAIN_COMMAND + " && echo x"),
    (SILENT, "command added after with a pipe",
     'cd "@IN@" && ' + PLAIN_COMMAND + " | tee out"),
    (SILENT, "remainder is a prefix of an approved string", 'cd "@IN@" && make'),
    (SILENT, "remainder is only the first half of an approved && string", 'cd "@IN@" && a'),
    (SILENT, "remainder is only the second half of an approved && string", 'cd "@IN@" && b'),
    (SILENT, "empty remainder", 'cd "@IN@" &&'),
    (SILENT, "blank remainder", 'cd "@IN@" &&    '),
    (SILENT, "no && at all", 'cd "@IN@"'),
    (SILENT, "no space between cd and the path", 'cd"@IN@" && ' + PLAIN_COMMAND),
    (SILENT, "something in front of cd", 'echo x; cd "@IN@" && ' + PLAIN_COMMAND),
    (SILENT, "pushd instead of cd", 'pushd "@IN@" && ' + PLAIN_COMMAND),
    (SILENT, "empty path", 'cd "" && ' + PLAIN_COMMAND),
)

# AC-3 (TM-1): the logical destination exists outside the area, or is the
# area itself, or is below the area while the physical one is not.
TM1_CASES = (
    (SILENT, "link inside the area followed by .. : logical is the worktrees directory outside the area",
     'cd "@HOPIN@/../.." && ' + PLAIN_COMMAND),
    (SILENT, "link inside the area followed by .. : logical is under the prefix-sharing sibling",
     'cd "@HOPIN@/../../em-workflow-x/task0001" && ' + PLAIN_COMMAND),
    (SILENT, "link inside the area followed by .. : logical is the area itself",
     'cd "@HOPIN@/.." && ' + PLAIN_COMMAND),
    (SILENT, "logical path below the area, physical path absent",
     'cd "@HOPIN@/../task0001" && ' + PLAIN_COMMAND),
)

# AC-4 (TM-2): the logical path is not an existing directory, and the physical
# path is not an existing directory strictly below the area.
TM2_CASES = (
    (SILENT, "physical path is an existing directory outside the area",
     'cd "@HOPSIB@/../elsewhere" && ' + PLAIN_COMMAND),
    (SILENT, "physical path is the area itself",
     'cd "@HOPSIB@/../em-workflow" && ' + PLAIN_COMMAND),
    (SILENT, "physical path is below a sibling sharing the name prefix",
     'cd "@HOPSIB@/../em-workflow-x/task0001" && ' + PLAIN_COMMAND),
    (SILENT, "physical path does not exist",
     'cd "@HOPTASK@/../does-not-exist" && ' + PLAIN_COMMAND),
    (SILENT, "physical path is an existing file",
     'cd "@HOPTASK@/../afile" && ' + PLAIN_COMMAND),
)

# Feature cd-prefix-non-directory-dotdot AC-2: a regular file, a missing
# component, or a link to either, followed by `..`. The logical path is the
# existing <area>/task0001 (or its name collapsed), and the lenient realpath
# lands below the area, but the operating system cannot resolve the path as
# written, so the physical path is not an existing directory.
NON_DIRECTORY_DOTDOT_CASES = (
    (SILENT, "regular file followed by .., then an existing directory",
     'cd "@FILE@/../task0001" && ' + PLAIN_COMMAND),
    (SILENT, "missing component followed by ..",
     'cd "@IN@/does-not-exist/.." && ' + PLAIN_COMMAND),
    (SILENT, "link to a regular file followed by .., then an existing directory",
     'cd "@LINKFILE@/../task0001" && ' + PLAIN_COMMAND),
    (SILENT, "link to a missing target followed by .., then an existing directory",
     'cd "@DANGLING@/../task0001" && ' + PLAIN_COMMAND),
)

PATH_CASES = (
    (SILENT, "existing directory outside the area", 'cd "@OUT@" && ' + PLAIN_COMMAND),
    (SILENT, "area of another repository", 'cd "@OTHER@" && ' + PLAIN_COMMAND),
    (SILENT, ".. that leaves the area", 'cd "@DOTDOT@" && ' + PLAIN_COMMAND),
    (SILENT, "symbolic link inside the area pointing outside", 'cd "@LINK@" && ' + PLAIN_COMMAND),
    (SILENT, "the area itself", 'cd "@REGION@" && ' + PLAIN_COMMAND),
    (SILENT, "sibling directory sharing the name prefix", 'cd "@SIBLING@" && ' + PLAIN_COMMAND),
    (SILENT, "path that does not exist", 'cd "@MISSING@" && ' + PLAIN_COMMAND),
    (SILENT, "path that is a file", 'cd "@FILE@" && ' + PLAIN_COMMAND),
    (SILENT, "root directory", 'cd "/" && ' + PLAIN_COMMAND),
) + TM1_CASES + TM2_CASES + NON_DIRECTORY_DOTDOT_CASES

# AC-2: the logical path is absent or a file, the physical path is an existing
# directory strictly below the area.
FALLBACK_ALLOW_CASES = (
    (ALLOW, "link outside the area, .., then a directory under the target's parent",
     'cd "@HOP@/../sub" && ' + PLAIN_COMMAND),
    (ALLOW, "same, a deeper directory under the target's parent",
     'cd "@HOP@/../sub/deeper" && ' + PLAIN_COMMAND),
    (ALLOW, "same, the target's parent itself is the destination",
     'cd "@HOPTASK@/../task0001" && ' + PLAIN_COMMAND),
    (ALLOW, "logical path is an existing file, physical path is a directory below the area",
     'cd "@HOPDIR@/hop/../sub" && ' + PLAIN_COMMAND),
)


class CdPrefixCase(unittest.TestCase):
    def check_cases(self, cases, cwd, store=None):
        for expected, label, template in cases:
            with self.subTest(label=label, cwd=cwd.name):
                proc = FIX.run_hook(FIX.expand(template), cwd, store)
                decision, _output = decide(proc)
                self.assertEqual(decision, expected)


class TestAc1AllowedPrefixForm(CdPrefixCase):
    """AC-1 (FR1, FR9)."""

    def test_ac1_allow_when_cwd_is_main_worktree(self):
        self.check_cases(ALLOW_CASES, FIX.repo)

    def test_ac1_allow_when_cwd_is_a_git_worktree(self):
        self.check_cases(ALLOW_CASES, FIX.worktree)

    def test_ac1_allow_reason_differs_from_the_exact_match_reason(self):
        _, exact = decide(FIX.run_hook(PLAIN_COMMAND, FIX.repo))
        decision, prefixed = decide(
            FIX.run_hook(FIX.expand('cd "@IN@" && ' + PLAIN_COMMAND), FIX.repo)
        )
        self.assertEqual(decision, ALLOW)
        self.assertNotEqual(
            prefixed["permissionDecisionReason"], exact["permissionDecisionReason"]
        )

    def test_ac1_no_child_process_uses_the_prefixed_path(self):
        log = FIX.git_log
        if log.exists():
            log.unlink()
        extra = {
            "PATH": str(FIX.shim_dir) + os.pathsep + os.environ.get("PATH", ""),
            "GIT_SHIM_LOG": str(log),
        }
        command = FIX.expand('cd "@IN@" && ' + PLAIN_COMMAND)
        decision, _ = decide(FIX.run_hook(command, FIX.repo, extra_env=extra))
        self.assertEqual(decision, ALLOW)
        lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        self.assertTrue(lines, "git was never run through the logger")
        for line in lines:
            self.assertNotIn(str(FIX.inside), line)


class TestAc2SyntaxConditions(CdPrefixCase):
    """AC-2 (FR1, FR3, FR9, TM-1): a form that breaks a syntax condition is
    left to the pre-change judgement, which is no output."""

    def test_ac2_forms_breaking_a_syntax_condition_are_silent(self):
        self.check_cases(SYNTAX_CASES, FIX.repo)


class TestAc3PathConditions(CdPrefixCase):
    """AC-3 (FR1, FR3, FR9, TM-2): a form that breaks a path condition is
    left to the pre-change judgement, which is no output."""

    def test_ac3_forms_breaking_a_path_condition_are_silent(self):
        self.check_cases(PATH_CASES, FIX.repo)

    def test_ac3_cwd_outside_any_git_repository_is_silent(self):
        # The remainder is approved for this cwd's project, so only the
        # unobtainable git common dir can keep the answer silent.
        command = FIX.expand('cd "@IN@" && ' + PLAIN_COMMAND)
        decision, _ = decide(FIX.run_hook(command, FIX.nongit, FIX.store_nongit))
        self.assertEqual(decision, SILENT)

    def test_ac3_nongit_cwd_still_allows_the_exact_approved_string(self):
        decision, _ = decide(FIX.run_hook(PLAIN_COMMAND, FIX.nongit, FIX.store_nongit))
        self.assertEqual(decision, ALLOW)


class TestAc4RefusalPatternStillDenies(CdPrefixCase):
    """AC-4 (FR2, FR9, TM-3)."""

    def test_ac4_refusal_pattern_in_the_remainder_denies(self):
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                command = FIX.expand('cd "@IN@" && ' + SUDO_COMMAND)
                decision, output = decide(FIX.run_hook(command, cwd, FIX.store_sudo))
                self.assertEqual(decision, DENY)
                reason = output["permissionDecisionReason"]
                self.assertIn("禁止パターン", reason)
                self.assertIn("sudo", reason)

    def test_ac4_the_store_holds_the_refused_string_verbatim(self):
        # Guards the fixture: the exact string alone also denies, proving the
        # store entry is what is being matched.
        decision, output = decide(FIX.run_hook(SUDO_COMMAND, FIX.repo, FIX.store_sudo))
        self.assertEqual(decision, DENY)
        self.assertIn("禁止パターン", output["permissionDecisionReason"])


class TestAc5CommandsWithoutPrefixUnchanged(CdPrefixCase):
    """AC-5 (FR3, FR9, NFR2)."""

    def test_ac5_approved_command_allows(self):
        decision, output = decide(FIX.run_hook(PLAIN_COMMAND, FIX.repo))
        self.assertEqual(decision, ALLOW)
        self.assertIn("承認済み", output["permissionDecisionReason"])

    def test_ac5_declared_unapproved_command_denies(self):
        decision, output = decide(FIX.run_hook(DECLARED_COMMAND, FIX.repo))
        self.assertEqual(decision, DENY)
        self.assertIn("未承認", output["permissionDecisionReason"])

    def test_ac5_neither_declared_nor_approved_is_silent(self):
        decision, _ = decide(FIX.run_hook(UNRELATED_COMMAND, FIX.repo))
        self.assertEqual(decision, SILENT)

    def test_ac5_prefixed_declared_unapproved_command_is_silent(self):
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                command = FIX.expand('cd "@IN@" && ' + DECLARED_COMMAND)
                decision, _ = decide(FIX.run_hook(command, cwd))
                self.assertEqual(decision, SILENT)

    def test_ac5_prefixed_unrelated_command_is_silent(self):
        command = FIX.expand('cd "@IN@" && ' + UNRELATED_COMMAND)
        decision, _ = decide(FIX.run_hook(command, FIX.repo))
        self.assertEqual(decision, SILENT)

    def test_ac5_non_bash_and_blank_input_stay_silent(self):
        proc = subprocess.run(
            [sys.executable, str(GUARD_PATH)],
            input=json.dumps({"tool_name": "Read", "tool_input": {"command": PLAIN_COMMAND}}),
            capture_output=True,
            text=True,
            env=FIX.env(FIX.store),
        )
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        decision, _ = decide(FIX.run_hook("   ", FIX.repo))
        self.assertEqual(decision, SILENT)


class TestAc6DenyGuidance(CdPrefixCase):
    """AC-6 (FR7): the unapproved deny carries separate guidance for the
    orchestrator, for the implementer and for a subagent that cannot ask."""

    @classmethod
    def setUpClass(cls):
        decision, output = decide(FIX.run_hook(DECLARED_COMMAND, FIX.repo))
        assert decision == DENY
        cls.context = output["additionalContext"]
        cls.sentences = [s for s in cls.context.split("。") if s.strip()]

    def sentence_index(self, marker):
        found = [i for i, s in enumerate(self.sentences) if marker in s]
        self.assertTrue(found, f"{marker!r} not in additionalContext: {self.context!r}")
        return found[0]

    def test_ac6_orchestrator_guidance_names_a_standalone_cd(self):
        index = self.sentence_index("単独の cd")
        self.assertIn("オーケストレーター", self.sentences[index])

    def test_ac6_implementer_guidance_names_the_chained_form(self):
        index = self.sentence_index('cd "{worktree_path}" && ')
        self.assertIn("implementer", self.sentences[index])
        self.assertIn("1 回の Bash 呼び出し", self.sentences[index])

    def test_ac6_subagent_guidance_says_do_not_retry_and_report_in_notes(self):
        index = self.sentence_index("再試行")
        sentence = self.sentences[index]
        self.assertIn("AskUserQuestion", sentence)
        self.assertIn("notes", sentence)

    def test_ac6_the_three_guidance_items_are_separate_sentences(self):
        indexes = {
            self.sentence_index("単独の cd"),
            self.sentence_index('cd "{worktree_path}" && '),
            self.sentence_index("再試行"),
        }
        self.assertEqual(len(indexes), 3)

    def test_ac6_transforming_the_approved_string_is_discouraged(self):
        self.assertIn("環境変数", self.context)

    def test_ac6_refusal_pattern_deny_guidance_is_unchanged(self):
        decision, output = decide(FIX.run_hook(SUDO_COMMAND, FIX.repo, FIX.store_sudo))
        self.assertEqual(decision, DENY)
        self.assertIn("ユーザーに定義の修正を報告すること", output["additionalContext"])
        self.assertNotIn('cd "{worktree_path}"', output["additionalContext"])


def _load_guard_module():
    """The hook's functions, loaded without writing any bytecode file."""
    module = types.ModuleType("bash_guard_under_test")
    source = GUARD_PATH.read_text(encoding="utf-8")
    exec(compile(source, str(GUARD_PATH), "exec"), module.__dict__)
    return module


PROC_ROOT = "/proc/self/root"


class TestPhysicalFallbackAllowed(CdPrefixCase):
    """AC-2 (FR1, FR3, FR8): the logical path is not an existing directory and
    the physical path is an existing directory strictly below the area. (The
    `/proc/self/root/..` prefix form that was AC-1 here is no longer allowed;
    see TestProcessDependentPathNotAllowed.)"""

    def test_ac2_link_dotdot_name_forms_are_allowed_from_the_main_worktree(self):
        self.check_cases(FALLBACK_ALLOW_CASES, FIX.repo)

    def test_ac2_link_dotdot_name_forms_are_allowed_from_a_git_worktree(self):
        self.check_cases(FALLBACK_ALLOW_CASES, FIX.worktree)

    def test_ac2_the_fixture_layout_matches_the_claimed_logical_paths(self):
        # Guards the fixture: the logical path of each allowed form really is
        # absent (or a file), and its physical path a directory below the area.
        absent = os.path.normpath(str(FIX.hop) + "/../sub")
        self.assertFalse(os.path.exists(absent))
        self.assertTrue(os.path.isdir(os.path.realpath(str(FIX.hop) + "/../sub")))
        as_file = os.path.normpath(str(FIX.hopdir) + "/hop/../sub")
        self.assertTrue(os.path.isfile(as_file))
        self.assertTrue(
            os.path.isdir(os.path.realpath(str(FIX.hopdir) + "/hop/../sub"))
        )

    def test_ac2_the_allow_reason_is_the_cd_prefix_reason(self):
        _, exact = decide(FIX.run_hook(PLAIN_COMMAND, FIX.repo))
        decision, prefixed = decide(
            FIX.run_hook(FIX.expand('cd "@HOP@/../sub" && ' + PLAIN_COMMAND), FIX.repo)
        )
        self.assertEqual(decision, ALLOW)
        self.assertNotEqual(
            prefixed["permissionDecisionReason"], exact["permissionDecisionReason"]
        )


class TestPhysicalFallbackNotAllowed(CdPrefixCase):
    """AC-3, AC-4 (FR2, FR4, FR5, FR8, TM-1, TM-2): no output."""

    def test_ac3_logical_destination_that_exists_outside_the_area_is_silent(self):
        for cwd in (FIX.repo, FIX.worktree):
            self.check_cases(TM1_CASES, cwd)

    def test_ac3_the_fixture_layout_matches_the_claimed_destinations(self):
        # Guards the fixture: the physical path is an existing directory
        # inside the area, the logical one an existing directory outside it.
        written = str(FIX.hop_in) + "/../.."
        logical = os.path.realpath(os.path.normpath(written))
        physical = os.path.realpath(written)
        self.assertTrue(os.path.isdir(logical))
        self.assertEqual(logical, str(FIX.region.parent))
        self.assertTrue(os.path.isdir(physical))
        self.assertEqual(physical, str(FIX.inside))

    def test_ac4_physical_path_that_is_not_below_the_area_is_silent(self):
        for cwd in (FIX.repo, FIX.worktree):
            self.check_cases(TM2_CASES, cwd)

    def test_ac4_the_fixture_layout_matches_the_claimed_destinations(self):
        # Guards the fixture: every logical path is not a directory, and each
        # physical path is what its label says.
        expected = {
            "@HOPSIB@/../elsewhere": FIX.elsewhere,
            "@HOPSIB@/../em-workflow": FIX.region,
            "@HOPSIB@/../em-workflow-x/task0001": FIX.sibling,
            "@HOPTASK@/../afile": FIX.file,
        }
        for template, physical in expected.items():
            with self.subTest(template=template):
                written = FIX.expand(template)
                self.assertFalse(os.path.isdir(os.path.normpath(written)))
                self.assertEqual(os.path.realpath(written), str(physical))
        for template in ("@HOPTASK@/../does-not-exist",):
            written = FIX.expand(template)
            self.assertFalse(os.path.isdir(os.path.normpath(written)))
            self.assertFalse(os.path.exists(os.path.realpath(written)))


class TestNulInPath(CdPrefixCase):
    """AC-5 (NFR4, TM-4): an embedded NUL character never raises."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)

    def test_ac5_the_path_check_returns_false_for_a_path_with_a_nul(self):
        for label, path in (
            ("nul after an existing directory", str(FIX.inside) + "\x00"),
            ("nul inside a component", str(FIX.inside) + "/su\x00b"),
            ("nul after a fallback form", FIX.expand("@HOP@/../sub") + "\x00"),
            ("nul before a dotdot", str(FIX.inside) + "\x00/.."),
        ):
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac5_a_resolution_error_makes_the_path_check_false(self):
        path = str(FIX.inside)
        self.assertIs(self.guard.is_below(path, self.area), True)
        for error in (OSError("simulated"), ValueError("simulated")):
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(os.path, "realpath", side_effect=error):
                    self.assertIs(self.guard.is_below(path, self.area), False)
                with mock.patch.object(os.path, "isdir", side_effect=error):
                    self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac5_through_the_hook_a_nul_path_exits_zero_silently_without_allow(self):
        for cwd in (FIX.repo, FIX.worktree):
            for template in (
                'cd "@IN@\x00" && ' + PLAIN_COMMAND,
                'cd "@HOP@/../sub\x00" && ' + PLAIN_COMMAND,
            ):
                with self.subTest(cwd=cwd.name, template=template):
                    proc = FIX.run_hook(FIX.expand(template), cwd)
                    self.assertEqual(proc.returncode, 0)
                    self.assertEqual(proc.stderr, "")
                    decision, _ = decide(proc)
                    self.assertNotEqual(decision, ALLOW)


# Feature cd-prefix-non-directory-dotdot: the forms whose `..` follows a
# component that is not a directory. The first two are the forms the criteria
# name; the last two are the link variants.
REQUIRED_NON_DIRECTORY_FORMS = (
    ("regular file then ..", "@FILE@/../task0001"),
    ("missing component then ..", "@IN@/does-not-exist/.."),
)
NON_DIRECTORY_FORMS = REQUIRED_NON_DIRECTORY_FORMS + (
    ("link to a regular file then ..", "@LINKFILE@/../task0001"),
    ("link to a missing target then ..", "@DANGLING@/../task0001"),
)


class TestNonDirectoryBeforeDotDot(CdPrefixCase):
    """cd-prefix-non-directory-dotdot AC-1 .. AC-4, AC-6, AC-7: the physical
    path is an existing directory only when the operating system resolves the
    path exactly as written to a directory."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)

    # -- AC-1 -------------------------------------------------------------

    def test_ac1_the_path_check_is_false_for_a_non_directory_before_dotdot(self):
        for label, template in NON_DIRECTORY_FORMS:
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(FIX.expand(template), self.area), False)

    def test_ac1_the_path_check_is_still_true_for_existing_directory_forms(self):
        for label, path in (
            ("existing directory below the area", str(FIX.inside)),
            ("link, .., then a name under the target's parent", FIX.expand("@HOP@/../sub")),
        ):
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), True)

    @unittest.skipUnless(os.path.isdir(PROC_ROOT), "/proc/self/root is not a directory")
    def test_ac1_proc_self_root_dotdot_in_front_is_never_below(self):
        # The non-directory forms stay False with the prefix in front. The
        # plain inside directory, which this test used to expect True, is
        # False too: a path under /proc fails the path check, whatever it
        # resolves to (feature cd-prefix-process-dependent-paths, D2).
        for label, template in NON_DIRECTORY_FORMS:
            with self.subTest(label=label):
                path = PROC_ROOT + "/.." + FIX.expand(template)
                self.assertIs(self.guard.is_below(path, self.area), False)
        path = PROC_ROOT + "/.." + str(FIX.inside)
        self.assertIs(self.guard.is_below(path, self.area), False)

    # -- AC-2, AC-3 -------------------------------------------------------

    def test_ac2_the_required_forms_are_in_the_path_cases_as_silent(self):
        cases = {template: expected for expected, _label, template in PATH_CASES}
        for _label, form in REQUIRED_NON_DIRECTORY_FORMS:
            with self.subTest(form=form):
                template = 'cd "' + form + '" && ' + PLAIN_COMMAND
                self.assertEqual(cases.get(template), SILENT)

    def test_ac2_the_added_forms_are_silent_from_a_git_worktree(self):
        self.check_cases(NON_DIRECTORY_DOTDOT_CASES, FIX.worktree)

    @unittest.skipUnless(os.path.isdir(PROC_ROOT), "/proc/self/root is not a directory")
    def test_ac3_proc_self_root_dotdot_in_front_of_the_added_forms_is_silent(self):
        for cwd in (FIX.repo, FIX.worktree):
            for label, template in NON_DIRECTORY_FORMS:
                with self.subTest(cwd=cwd.name, label=label):
                    command = (
                        'cd "' + PROC_ROOT + "/.." + FIX.expand(template) + '" && ' + PLAIN_COMMAND
                    )
                    decision, _ = decide(FIX.run_hook(command, cwd))
                    self.assertEqual(decision, SILENT)

    # -- AC-4 -------------------------------------------------------------

    def written_forms(self):
        forms = [(label, FIX.expand(template)) for label, template in NON_DIRECTORY_FORMS]
        if os.path.isdir(PROC_ROOT):
            forms += [
                ("proc root, " + label, PROC_ROOT + "/.." + written)
                for label, written in list(forms)
            ]
        return forms

    def test_ac4_the_fixture_layout_matches_the_claimed_resolution(self):
        # Guards the fixture: the operating system cannot resolve each form as
        # written, while the lenient realpath lands on an existing directory
        # strictly below the area. Together: the form was allowed before.
        for label, written in self.written_forms():
            with self.subTest(label=label):
                with self.assertRaises((NotADirectoryError, FileNotFoundError)):
                    os.stat(written)
                self.assertFalse(os.path.isdir(written))
                lenient = os.path.realpath(written, strict=False)
                self.assertTrue(os.path.isdir(lenient))
                self.assertTrue(self.guard.strictly_below(lenient, self.area))

    def test_ac4_the_decision_does_not_depend_on_strict_mode_realpath(self):
        real_realpath = os.path.realpath

        def always_lenient(path, **_ignored_strict_request):
            return real_realpath(path)

        with mock.patch.object(os.path, "realpath", new=always_lenient):
            for label, written in self.written_forms():
                with self.subTest(label=label):
                    self.assertIs(self.guard.is_below(written, self.area), False)
            self.assertIs(self.guard.is_below(str(FIX.inside), self.area), True)

    # -- AC-6 -------------------------------------------------------------

    def test_ac6_the_path_check_starts_no_child_process(self):
        entry_points = (
            (subprocess, ("Popen", "run", "call", "check_call", "check_output",
                          "getoutput", "getstatusoutput")),
            (os, ("system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp",
                  "execv", "execve", "execvp", "execvpe",
                  "spawnv", "spawnve", "spawnvp", "spawnvpe")),
        )
        paths = [written for _label, written in self.written_forms()]
        paths.append(str(FIX.inside))
        with contextlib.ExitStack() as stack:
            for owner, names in entry_points:
                for name in names:
                    if hasattr(owner, name):
                        stack.enter_context(
                            mock.patch.object(
                                owner,
                                name,
                                side_effect=AssertionError(
                                    f"{owner.__name__}.{name} called by the path check"
                                ),
                            )
                        )
            for path in paths:
                self.guard.is_below(path, self.area)

    # -- AC-7 -------------------------------------------------------------

    def test_ac7_a_resolution_error_in_the_as_written_step_makes_the_check_false(self):
        paths = [str(FIX.inside)] + [FIX.expand(t) for _label, t in NON_DIRECTORY_FORMS]
        for error in (OSError("simulated"), ValueError("simulated")):
            for path in paths:
                with self.subTest(error=type(error).__name__, path=path):
                    with mock.patch.object(
                        self.guard, "resolves_to_directory", side_effect=error
                    ):
                        self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac7_the_as_written_step_alone_can_refuse_an_ordinary_directory(self):
        with mock.patch.object(self.guard, "resolves_to_directory", return_value=False):
            self.assertIs(self.guard.is_below(str(FIX.inside), self.area), False)

    def test_ac7_a_nul_inserted_into_an_added_form_makes_the_check_false(self):
        for label, path in (
            ("nul after the file", str(FIX.file) + "\x00/../task0001"),
            ("nul after the missing component", str(FIX.inside) + "/does-not-exist\x00/.."),
            ("nul at the end of the file form", str(FIX.file) + "/../task0001\x00"),
        ):
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), False)


# ---------------------------------------------------------------------------
# Feature cd-prefix-process-dependent-paths, task0001: a path under /proc or
# /dev/fd fails the path check. The operating system resolves such a path
# against the process that asks, and the hook process is not the Bash process.
# ---------------------------------------------------------------------------

PROC_SELF = "/proc/self"
DEV_FD = "/dev/fd"
SHARED = "shared"

needs_proc = unittest.skipUnless(os.path.isdir(PROC_SELF), "/proc/self is not a directory")
needs_dev_fd = unittest.skipUnless(
    os.path.isdir(PROC_SELF) and os.path.isdir(DEV_FD),
    "/proc/self or /dev/fd is not a directory",
)


@contextlib.contextmanager
def _working_directory(path):
    """Move this process into path; the previous directory is restored."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _link(target, link):
    """Create the symbolic link once; an existing one is left alone."""
    if not os.path.lexists(str(link)):
        os.symlink(str(target), str(link))
    return link


def _link_chain(directory, count, final):
    """directory/l0 -> l1 -> ... -> l<count-1> -> final. Following l0 follows
    exactly `count` links. Returns the path of l0."""
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        target = "l%d" % (index + 1) if index < count - 1 else final
        _link(target, directory / ("l%d" % index))
    return directory / "l0"


class Layout:
    """A dedicated subdirectory of the area for the process dependent cases,
    so the layout seen by the other tests of this module is unchanged.

        procdep/work/shared      the hook process's working directory is work,
        procdep/shared           so /proc/self/cwd/shared and
                                 /proc/self/cwd/../shared both land below the
                                 area
        procdep/names/...        directories named like the excluded locations
        procdep/links/...        links inside the area to /proc and /dev/fd
        procdep/loops/...        link loops
        procdep/chain<N>/l0      a chain that follows N links, then shared
    """

    def __init__(self):
        self.top = FIX.region / "procdep"
        self.work = self.top / "work"
        self.under_work = self.work / SHARED
        self.beside_work = self.top / SHARED
        self.names = self.top / "names"
        self.links = self.top / "links"
        self.loops = self.top / "loops"
        for directory in (
            self.under_work,
            self.beside_work,
            self.names / "proc",
            self.names / "procfoo",
            self.names / "dev" / "fd",
            self.links,
            self.loops,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self.cwd_link = _link("/proc/self/cwd", self.links / "cwd-link")
        self.self_link = _link("/proc/self", self.links / "self-link")
        self.ping = _link("pong", self.loops / "ping")
        _link("ping", self.loops / "pong")
        self.selfish = _link("selfish", self.loops / "selfish")

    def chain(self, count):
        return _link_chain(self.top / ("chain%d" % count), count, self.beside_work)

    def cwd_forms(self):
        """(label, written path) for the forms that name the process's own
        working directory. With the process in work, each lands on an
        existing directory strictly below the area."""
        return [
            ("cwd then a name", PROC_SELF + "/cwd/" + SHARED),
            ("cwd, .., then a name", PROC_SELF + "/cwd/../" + SHARED),
        ]


def _first_component_directory():
    """An existing directory directly below the root, as /<name>."""
    return "/" + FIX.inside.parts[1]


@contextlib.contextmanager
def _no_child_process():
    """The standard library's child-process entry points raise while active."""
    entry_points = (
        (subprocess, ("Popen", "run", "call", "check_call", "check_output",
                      "getoutput", "getstatusoutput")),
        (os, ("system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp",
              "execv", "execve", "execvp", "execvpe",
              "spawnv", "spawnve", "spawnvp", "spawnvpe")),
    )
    with contextlib.ExitStack() as stack:
        for owner, names in entry_points:
            for name in names:
                if hasattr(owner, name):
                    stack.enter_context(
                        mock.patch.object(
                            owner,
                            name,
                            side_effect=AssertionError(
                                f"{owner.__name__}.{name} called by the path check"
                            ),
                        )
                    )
        yield


class TestProcessDependentPathNotAllowed(CdPrefixCase):
    """AC-1, AC-3 (hook level), AC-5, AC-6 (hook level), TM-1 .. TM-4: a cd
    prefix form whose path is, or passes through, a location under /proc or
    /dev/fd is judged as if it had no cd prefix, so there is no output."""

    @classmethod
    def setUpClass(cls):
        cls.layout = Layout()
        cls.guard = _load_guard_module()

    def prefixed(self, written):
        return 'cd "' + written + '" && ' + PLAIN_COMMAND

    # -- AC-1 -------------------------------------------------------------

    @needs_proc
    def test_ac1_the_fixture_lands_the_hook_process_below_the_area_and_bash_elsewhere(self):
        # Guards the fixture: with the hook subprocess in work, the same path
        # text names an existing directory strictly below the area, so the
        # hook would have allowed the form before the exclusion. Bash runs in
        # the input cwd, where the text names something else.
        area = str(FIX.region)
        for label, written in self.layout.cwd_forms():
            with self.subTest(label=label):
                hook_side = written.replace(PROC_SELF + "/cwd", str(self.layout.work), 1)
                self.assertTrue(os.path.isdir(hook_side))
                self.assertTrue(self.guard.strictly_below(os.path.realpath(hook_side), area))
                for cwd in (FIX.repo, FIX.worktree):
                    bash_side = written.replace(PROC_SELF + "/cwd", str(cwd), 1)
                    landed = os.path.realpath(bash_side)
                    self.assertFalse(
                        os.path.isdir(bash_side) and self.guard.strictly_below(landed, area)
                    )

    @needs_proc
    def test_ac1_cwd_forms_are_silent_when_the_hook_process_runs_elsewhere(self):
        for cwd in (FIX.repo, FIX.worktree):
            for label, written in self.layout.cwd_forms():
                with self.subTest(cwd=cwd.name, label=label):
                    proc = FIX.run_hook(
                        self.prefixed(written), cwd, process_cwd=self.layout.work
                    )
                    decision, _ = decide(proc)
                    self.assertEqual(decision, SILENT)

    def test_ac1_an_ordinary_path_is_still_allowed_with_a_separate_process_cwd(self):
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                proc = FIX.run_hook(
                    self.prefixed(str(self.layout.under_work)),
                    cwd,
                    process_cwd=self.layout.work,
                )
                decision, _ = decide(proc)
                self.assertEqual(decision, ALLOW)

    def test_ac1_run_hook_without_the_parameter_runs_in_the_input_cwd(self):
        with mock.patch.object(subprocess, "run", wraps=subprocess.run) as spy:
            FIX.run_hook(PLAIN_COMMAND, FIX.repo)
            FIX.run_hook(PLAIN_COMMAND, FIX.repo, process_cwd=self.layout.work)
        omitted, given = spy.call_args_list
        self.assertEqual(omitted.kwargs["cwd"], str(FIX.repo))
        self.assertEqual(given.kwargs["cwd"], str(self.layout.work))
        for call in (omitted, given):
            self.assertEqual(json.loads(call.kwargs["input"])["cwd"], str(FIX.repo))

    # -- AC-3 (hook level) --------------------------------------------------

    @needs_proc
    def test_ac3_a_link_to_the_process_cwd_inside_the_area_is_silent(self):
        for cwd in (FIX.repo, FIX.worktree):
            for label, written in (
                ("link to cwd", str(self.layout.cwd_link) + "/" + SHARED),
                ("link to cwd, .., then a name", str(self.layout.cwd_link) + "/../" + SHARED),
                ("link to /proc/self, then cwd", str(self.layout.self_link) + "/cwd/" + SHARED),
            ):
                with self.subTest(cwd=cwd.name, label=label):
                    proc = FIX.run_hook(
                        self.prefixed(written), cwd, process_cwd=self.layout.work
                    )
                    decision, _ = decide(proc)
                    self.assertEqual(decision, SILENT)

    # -- AC-5 -------------------------------------------------------------

    @unittest.skipUnless(os.path.isdir(PROC_ROOT), "/proc/self/root is not a directory")
    def test_ac5_proc_self_root_dotdot_before_an_absolute_worktree_path_is_silent(self):
        for cwd in (FIX.repo, FIX.worktree):
            for target in (FIX.worktree, FIX.inside):
                with self.subTest(cwd=cwd.name, target=target.name):
                    command = 'cd "' + PROC_ROOT + "/.." + str(target) + '" && ' + PLAIN_COMMAND
                    decision, _ = decide(FIX.run_hook(command, cwd))
                    self.assertEqual(decision, SILENT)

    def test_ac5_the_approved_string_run_alone_is_still_allowed(self):
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                decision, _ = decide(FIX.run_hook(PLAIN_COMMAND, cwd))
                self.assertEqual(decision, ALLOW)

    @unittest.skipUnless(os.path.isdir(PROC_ROOT), "/proc/self/root is not a directory")
    def test_ac5_a_refused_form_with_a_declared_but_unapproved_remainder_is_silent(self):
        # No new deny: the declared command is judged exactly as if the cd
        # prefix were absent from the form, and the form is not the declared
        # string, so there is no decision.
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                command = 'cd "' + PROC_ROOT + "/.." + str(FIX.inside) + '" && ' + DECLARED_COMMAND
                decision, _ = decide(FIX.run_hook(command, cwd))
                self.assertEqual(decision, SILENT)

    # -- AC-6 (hook level) --------------------------------------------------

    def test_ac6_a_loop_or_an_over_bound_chain_exits_zero_silently_and_is_not_allowed(self):
        forms = (
            ("link loop", str(self.layout.ping)),
            ("below a link loop", str(self.layout.ping) + "/" + SHARED),
            ("link to itself", str(self.layout.selfish)),
            ("chain beyond the bound", str(self.layout.chain(45))),
        )
        for cwd in (FIX.repo, FIX.worktree):
            for label, written in forms:
                with self.subTest(cwd=cwd.name, label=label):
                    proc = FIX.run_hook(self.prefixed(written), cwd)
                    self.assertEqual(proc.returncode, 0)
                    self.assertEqual(proc.stderr, "")
                    decision, _ = decide(proc)
                    self.assertNotEqual(decision, ALLOW)
                    self.assertEqual(decision, SILENT)

    def test_ac6_a_short_chain_of_links_is_still_allowed(self):
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                decision, _ = decide(
                    FIX.run_hook(self.prefixed(str(self.layout.chain(3))), cwd)
                )
                self.assertEqual(decision, ALLOW)


class TestProcessDependentPathCheck(unittest.TestCase):
    """AC-2, AC-3, AC-4, AC-5 (module level): the path check applied to the
    area of the fixture."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.layout = Layout()

    def assert_would_have_been_below(self, written):
        # Guards the fixture: the form names an existing directory strictly
        # below the area, so the path check had no other reason to refuse it.
        self.assertTrue(os.path.isdir(written), written)
        self.assertTrue(
            self.guard.strictly_below(os.path.realpath(written), self.area), written
        )

    def assert_false_below_the_area(self, forms):
        for label, written in forms:
            with self.subTest(label=label):
                self.assert_would_have_been_below(written)
                self.assertIs(self.guard.is_below(written, self.area), False)

    # -- AC-2 -------------------------------------------------------------

    @needs_proc
    def test_ac2_forms_that_name_the_process_cwd_are_false(self):
        forms = [
            ("cwd then a name", PROC_SELF + "/cwd/" + SHARED),
            ("cwd, .., then a name", PROC_SELF + "/cwd/../" + SHARED),
            ("own pid, cwd, then a name", "/proc/%d/cwd/%s" % (os.getpid(), SHARED)),
            ("trailing slash", PROC_SELF + "/cwd/" + SHARED + "/"),
            ("doubled leading slash", "//proc/self/cwd/" + SHARED),
            ("dot component after the root", "/./proc/self/cwd/" + SHARED),
            (
                "existing directory, .., then proc",
                _first_component_directory() + "/../proc/self/cwd/" + SHARED,
            ),
        ]
        if os.path.isdir("/proc/thread-self"):
            forms.append(("thread-self, cwd, then a name", "/proc/thread-self/cwd/" + SHARED))
        with _working_directory(self.layout.work):
            self.assert_false_below_the_area(forms)

    @needs_proc
    def test_ac2_the_root_of_the_process_is_false_with_and_without_dotdot(self):
        forms = [
            ("root then the inside directory", PROC_ROOT + str(FIX.inside)),
            ("root, .., then the inside directory", PROC_ROOT + "/.." + str(FIX.inside)),
            ("root then the worktree", PROC_ROOT + str(FIX.worktree)),
        ]
        self.assert_false_below_the_area(forms)

    @needs_proc
    def test_ac2_proc_self_fd_forms_are_false(self):
        fd = os.open(str(self.layout.under_work), os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        self.assert_false_below_the_area(
            [
                ("proc self fd", "%s/fd/%d" % (PROC_SELF, fd)),
                ("proc self fd, trailing slash", "%s/fd/%d/" % (PROC_SELF, fd)),
            ]
        )

    @needs_dev_fd
    def test_ac2_dev_fd_forms_are_false(self):
        fd = os.open(str(self.layout.under_work), os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        self.assert_false_below_the_area(
            [
                ("dev fd", "%s/%d" % (DEV_FD, fd)),
                ("dev fd, dot component", "/dev/./fd/%d" % fd),
                ("dev fd, doubled slash", "/dev//fd/%d" % fd),
            ]
        )

    @needs_proc
    def test_ac2_the_logical_walk_refuses_a_form_only_the_collapsed_path_reaches(self):
        # `..` collapsed against the missing first component leaves a path
        # under /proc. The as-written resolution cannot get there, so the
        # existing rule's as-written query is replaced by one that agrees;
        # the logical resolution is then the only thing that can refuse.
        form = "/does-not-exist-for-the-walk/../proc/self/cwd/" + SHARED
        with _working_directory(self.layout.work):
            self.assertTrue(os.path.isdir(os.path.normpath(form)))
            with mock.patch.object(self.guard, "resolves_to_directory", return_value=True):
                self.assertIs(self.guard.is_below(form, self.area), False)

    # -- AC-3 -------------------------------------------------------------

    @needs_proc
    def test_ac3_a_link_to_the_process_cwd_is_false(self):
        forms = [
            ("link to cwd then a name", str(self.layout.cwd_link) + "/" + SHARED),
            ("link to cwd, .., then a name", str(self.layout.cwd_link) + "/../" + SHARED),
            ("link to cwd itself", str(self.layout.cwd_link)),
        ]
        with _working_directory(self.layout.work):
            self.assert_false_below_the_area(forms)

    @needs_proc
    def test_ac3_a_link_to_proc_self_followed_by_cwd_is_false(self):
        forms = [
            ("link to /proc/self, cwd, then a name",
             str(self.layout.self_link) + "/cwd/" + SHARED),
        ]
        with _working_directory(self.layout.work):
            self.assert_false_below_the_area(forms)

    @needs_dev_fd
    def test_ac3_a_link_to_a_dev_fd_entry_is_false(self):
        fd = os.open(str(self.layout.under_work), os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        link = self.layout.links / ("fd-link-%d" % fd)
        os.symlink("%s/%d" % (DEV_FD, fd), str(link))
        self.addCleanup(os.unlink, str(link))
        self.assert_false_below_the_area(
            [("link to a /dev/fd entry", str(link)), ("trailing slash", str(link) + "/")]
        )

    # -- AC-4 -------------------------------------------------------------

    def test_ac4_directories_named_like_the_excluded_ones_are_below(self):
        for name in ("proc", "procfoo", "dev/fd"):
            with self.subTest(name=name):
                path = str(self.layout.names / name)
                self.assertTrue(os.path.isdir(path))
                self.assertIs(self.guard.is_below(path, self.area), True)

    def test_ac4_the_existing_in_area_forms_are_below(self):
        for label, path in (
            ("existing directory below the area", str(FIX.inside)),
            ("deeper directory below the area", str(FIX.deep)),
            ("link, .., then a name under the target's parent", FIX.expand("@HOP@/../sub")),
        ):
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), True)

    def test_ac4_the_lexical_predicate_is_true_for_the_excluded_locations(self):
        for text in (
            "/proc",
            "/dev/fd",
            "//proc/x",
            "/./proc/x",
            "/proc/x/",
            "/proc/self/cwd",
            "/dev/fd/3",
            "/dev/./fd",
            "/dev//fd/3",
            "//dev/fd",
        ):
            with self.subTest(text=text):
                self.assertIs(self.guard._under_proc_or_dev_fd(text), True)

    def test_ac4_the_lexical_predicate_is_false_for_everything_else(self):
        for text in (
            "/procfoo",
            "/dev",
            "/dev/null",
            "/dev/fdx",
            "/dev/x/fd",
            "/",
            "",
            "/x/proc",
            "/x/dev/fd",
            self.area + "/proc",
            self.area + "/dev/fd",
        ):
            with self.subTest(text=text):
                self.assertIs(self.guard._under_proc_or_dev_fd(text), False)

    def test_ac4_the_lexical_predicate_does_not_touch_the_file_system(self):
        with mock.patch.object(os, "lstat", side_effect=AssertionError("file system touched")):
            with mock.patch.object(os, "stat", side_effect=AssertionError("file system touched")):
                self.assertIs(self.guard._under_proc_or_dev_fd("/proc/self/cwd"), True)
                self.assertIs(self.guard._under_proc_or_dev_fd("/procfoo"), False)

    # -- AC-5 -------------------------------------------------------------

    @needs_proc
    def test_ac5_the_proc_self_root_dotdot_prefix_form_is_false(self):
        for target in (FIX.worktree, FIX.inside):
            with self.subTest(target=target.name):
                path = PROC_ROOT + "/.." + str(target)
                self.assertIs(self.guard.is_below(path, self.area), False)


class TestLinkBoundAndProbeErrors(unittest.TestCase):
    """AC-6 (TM-3, TM-4): a link loop, a chain beyond the followed-link bound,
    and an error while a stage is probed or a link target is read make the
    path check False."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.layout = Layout()

    def test_ac6_a_link_loop_is_false(self):
        for label, path in (
            ("two links pointing at each other", str(self.layout.ping)),
            ("below the loop", str(self.layout.ping) + "/" + SHARED),
            ("a link pointing at itself", str(self.layout.selfish)),
        ):
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac6_a_chain_beyond_the_bound_is_false_and_a_short_chain_is_true(self):
        self.assertIs(self.guard.is_below(str(self.layout.chain(3)), self.area), True)
        self.assertIs(self.guard.is_below(str(self.layout.chain(45)), self.area), False)

    def test_ac6_the_walk_alone_decides_the_followed_link_bound(self):
        # The as-written query of the existing rule is replaced by one that
        # agrees, so only the walk can refuse. The bound is the Linux kernel's
        # own limit for one resolution: 40 links are followed, the 41st is not.
        with mock.patch.object(self.guard, "resolves_to_directory", return_value=True):
            for count, expected in ((3, True), (40, True), (41, False), (45, False)):
                with self.subTest(links=count):
                    self.assertIs(
                        self.guard.is_below(str(self.layout.chain(count)), self.area),
                        expected,
                    )

    def test_ac6_the_walk_alone_refuses_a_loop(self):
        with mock.patch.object(self.guard, "resolves_to_directory", return_value=True):
            for path in (str(self.layout.ping), str(self.layout.selfish)):
                with self.subTest(path=path):
                    self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac6_an_error_while_a_stage_is_probed_makes_the_check_false(self):
        target = str(self.layout.under_work)
        self.assertIs(self.guard.is_below(target, self.area), True)
        real_lstat = os.lstat
        for error in (OSError("simulated"), ValueError("simulated")):

            def probe(path, *args, **kwargs):
                if os.fspath(path) == target:
                    raise error
                return real_lstat(path, *args, **kwargs)

            with self.subTest(error=type(error).__name__):
                with mock.patch.object(os, "lstat", new=probe):
                    self.assertIs(self.guard.is_below(target, self.area), False)

    def test_ac6_an_error_while_a_link_target_is_read_makes_the_check_false(self):
        path = str(self.layout.chain(3))
        self.assertIs(self.guard.is_below(path, self.area), True)
        for error in (OSError("simulated"), ValueError("simulated")):
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(os, "readlink", side_effect=error):
                    self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac6_a_missing_stage_or_a_non_directory_stage_is_not_an_error(self):
        # The two endings that are not failures: the existing rule decides.
        with mock.patch.object(self.guard, "resolves_to_directory", return_value=True):
            for label, path in (
                ("missing stage then ..", str(FIX.inside) + "/does-not-exist/../sub"),
                ("regular file then ..", str(FIX.file) + "/../task0001"),
            ):
                with self.subTest(label=label):
                    self.assertIs(self.guard.is_below(path, self.area), True)


class TestProcessDependentPathContract(unittest.TestCase):
    """AC-7: what the change leaves as it was."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.layout = Layout()

    def test_ac7_is_below_keeps_its_parameters(self):
        self.assertEqual(list(inspect.signature(self.guard.is_below).parameters), ["path", "area"])

    def test_ac7_the_caller_still_passes_the_path_and_the_area_unchanged(self):
        command = 'cd "' + str(FIX.inside) + '" && ' + PLAIN_COMMAND
        with mock.patch.object(self.guard, "is_below", return_value=True) as spy:
            result = self.guard.is_cd_prefixed_approved(
                command, {PLAIN_COMMAND}, str(FIX.repo / ".git")
            )
        self.assertIs(result, True)
        spy.assert_called_once_with(str(FIX.inside), self.area)

    @needs_proc
    def test_ac7_the_path_check_starts_no_child_process_for_the_added_forms(self):
        fd = os.open(str(self.layout.under_work), os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        paths = [
            PROC_SELF + "/cwd/" + SHARED,
            PROC_SELF + "/cwd/../" + SHARED,
            "/proc/thread-self/cwd/" + SHARED,
            "/proc/%d/cwd/%s" % (os.getpid(), SHARED),
            "%s/fd/%d" % (PROC_SELF, fd),
            "%s/%d" % (DEV_FD, fd),
            PROC_ROOT + str(FIX.inside),
            PROC_ROOT + "/.." + str(FIX.inside),
            "//proc/self/cwd/" + SHARED,
            "/./proc/self/cwd/" + SHARED,
            _first_component_directory() + "/../proc/self/cwd/" + SHARED,
            str(self.layout.cwd_link) + "/" + SHARED,
            str(self.layout.self_link) + "/cwd/" + SHARED,
            str(self.layout.ping),
            str(self.layout.chain(45)),
            str(self.layout.chain(3)),
            str(self.layout.names / "proc"),
            str(FIX.inside),
        ]
        with _working_directory(self.layout.work), _no_child_process():
            for path in paths:
                self.guard.is_below(path, self.area)


def _verbatim_execution_rule(text):
    """Body of the protocol's "Verbatim execution rule" section."""
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("## Verbatim execution rule")),
        None,
    )
    if start is None:
        return None
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return " ".join(" ".join(lines[start:end]).split())


def _states_single_realpath_condition(text):
    """True when the text states that the realpath alone must be an existing
    directory below the area (the condition this change replaces)."""
    flat = " ".join(text.split())
    return bool(
        re.search(r"realpath of <path> is an existing directory", flat)
        or re.search(r"path's realpath is an existing directory", flat)
    )


def _states_new_path_condition(text):
    """True when the text carries the two-sided rule: the logical path, the
    physical path, both strictly below the area when the logical path is an
    existing directory, otherwise the physical path alone."""
    flat = " ".join(text.split()).lower()
    return all(
        needle in flat
        for needle in (
            "logical path",
            "physical path",
            "strictly below",
            "existing directory",
            "otherwise",
            "both",
        )
    )


class TestPathConditionWording(unittest.TestCase):
    """AC-7 (FR7): the hook docstring and the protocol's Verbatim execution
    rule state the same two-sided path condition."""

    @classmethod
    def setUpClass(cls):
        cls.docstring = _load_guard_module().__doc__
        cls.rule = _verbatim_execution_rule(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_ac7_matchers_fire_on_forged_text(self):
        self.assertTrue(
            _states_single_realpath_condition(
                "the realpath of <path> is an existing directory strictly below X"
            )
        )
        self.assertTrue(
            _states_single_realpath_condition(
                "the path's realpath is an existing directory deeper than X"
            )
        )
        self.assertFalse(_states_new_path_condition("the realpath of <path> only"))

    def test_ac7_the_hook_docstring_states_the_new_condition(self):
        self.assertTrue(_states_new_path_condition(self.docstring))

    def test_ac7_the_hook_docstring_no_longer_states_the_single_realpath_condition(self):
        self.assertFalse(_states_single_realpath_condition(self.docstring))

    def test_ac7_the_protocol_rule_states_the_new_condition(self):
        self.assertIsNotNone(self.rule, "section 'Verbatim execution rule' not found")
        self.assertTrue(_states_new_path_condition(self.rule))

    def test_ac7_the_protocol_rule_no_longer_states_the_single_realpath_condition(self):
        self.assertIsNotNone(self.rule, "section 'Verbatim execution rule' not found")
        self.assertFalse(_states_single_realpath_condition(self.rule))

    def test_ac7_both_places_define_the_two_terms(self):
        self.assertIsNotNone(self.rule, "section 'Verbatim execution rule' not found")
        for name, text in (("docstring", self.docstring), ("protocol", self.rule)):
            flat = " ".join(text.split())
            with self.subTest(place=name):
                self.assertRegex(flat, r"logical path \([^)]*\.\.[^)]*\)")
                self.assertRegex(flat, r"physical path \([^)]*as written[^)]*\)")


# Needles that carry the statement about /proc and /dev/fd. `/proc` keeps its
# slash: the docstring already says "child process", so a bare `proc` would
# match before the statement exists.
PROCESS_DEPENDENT_PATH_NEEDLES = (
    "/proc",
    "/dev/fd",
    "fails the path check",
    "first component is `proc`",
    "`dev` and `fd`",
    "judged on the path as written",
    "each stage reached while resolving the logical path and the physical path",
    "the target of each link followed",
    "final realpath alone",
)


def _states_process_dependent_path_rule(text):
    """True when the text states that a path under /proc or /dev/fd fails the
    path check, judged on the path as written, on each stage of the resolution
    of both the logical path and the physical path, and on the target of each
    link followed."""
    flat = " ".join(text.split()).lower()
    return all(needle in flat for needle in PROCESS_DEPENDENT_PATH_NEEDLES)


def _docstring_path_item(docstring):
    """The `path:` item of the `cd prefix:` paragraph, whitespace flattened."""
    match = re.search(r"^  - path:(.*?)^  - approval:", docstring, re.DOTALL | re.MULTILINE)
    return " ".join(match.group(1).split()) if match else None


def _rule_path_item(rule):
    """The path item of the Verbatim execution rule (already flattened)."""
    start = rule.find("the path reaches an existing directory")
    end = rule.find("everything after the first `&&` matches")
    if start < 0 or end < start:
        return None
    return rule[start:end]


class TestProcessDependentPathWording(unittest.TestCase):
    """AC-1 to AC-4 (FR5, NFR6): the hook docstring and the protocol's Verbatim
    execution rule both state that a path under /proc or /dev/fd fails the
    path check, and how that is judged."""

    @classmethod
    def setUpClass(cls):
        cls.docstring = _load_guard_module().__doc__
        cls.rule = _verbatim_execution_rule(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_ac4_the_matcher_fires_on_forged_text_with_one_needle_removed(self):
        self.assertIsNotNone(self.rule, "section 'Verbatim execution rule' not found")
        for name, text in (("docstring", self.docstring), ("protocol", self.rule)):
            flat = " ".join(text.split()).lower()
            self.assertTrue(
                _states_process_dependent_path_rule(flat),
                f"the {name} does not carry the statement the forgeries start from",
            )
            for needle in PROCESS_DEPENDENT_PATH_NEEDLES:
                with self.subTest(place=name, needle=needle):
                    forged = flat.replace(needle, "")
                    self.assertNotIn(needle, forged)
                    self.assertFalse(_states_process_dependent_path_rule(forged))

    def test_ac4_the_matcher_does_not_fire_on_unrelated_text(self):
        self.assertFalse(_states_process_dependent_path_rule(""))
        self.assertFalse(_states_process_dependent_path_rule("the realpath of <path> only"))
        self.assertFalse(_states_process_dependent_path_rule("never used as a child process"))

    def test_ac1_the_hook_docstring_states_the_rule(self):
        self.assertTrue(_states_process_dependent_path_rule(self.docstring))

    def test_ac1_the_statement_sits_in_the_path_item_of_the_docstring(self):
        item = _docstring_path_item(self.docstring)
        self.assertIsNotNone(item, "path item of the 'cd prefix:' paragraph not found")
        self.assertTrue(_states_process_dependent_path_rule(item))

    def test_ac2_the_protocol_rule_states_the_rule(self):
        self.assertIsNotNone(self.rule, "section 'Verbatim execution rule' not found")
        self.assertTrue(_states_process_dependent_path_rule(self.rule))

    def test_ac2_the_statement_sits_in_the_path_item_of_the_protocol_rule(self):
        self.assertIsNotNone(self.rule, "section 'Verbatim execution rule' not found")
        item = _rule_path_item(self.rule)
        self.assertIsNotNone(item, "path item of the Verbatim execution rule not found")
        self.assertTrue(_states_process_dependent_path_rule(item))

    def test_ac3_neither_place_describes_the_proc_self_root_prefix_as_allowed(self):
        self.assertIsNotNone(self.rule, "section 'Verbatim execution rule' not found")
        for name, text in (("docstring", self.docstring), ("protocol", self.rule)):
            with self.subTest(place=name):
                self.assertNotIn("/proc/self/root", " ".join(text.split()))


def _imported_top_level_modules(source):
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def _executable_text_fragments(source):
    """Identifiers and string literals of the module, docstrings excluded."""
    tree = ast.parse(source)
    docstring_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_nodes.add(id(body[0].value))
    fragments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstring_nodes:
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


class TestAc7StandardLibraryOnly(unittest.TestCase):
    """AC-7 (NFR1, NFR3, NFR8)."""

    def test_ac7_hook_imports_only_standard_library_modules(self):
        source = GUARD_PATH.read_text(encoding="utf-8")
        imported = _imported_top_level_modules(source)
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_ac7_this_test_module_imports_only_standard_library_modules(self):
        source = Path(__file__).read_text(encoding="utf-8")
        imported = _imported_top_level_modules(source)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_ac7_hook_executable_text_has_no_status_substring(self):
        # tests/test_hook_classification_pin.py counts "status" next to
        # "workflow.yaml" in executable text as a per-task status read.
        source = GUARD_PATH.read_text(encoding="utf-8")
        offenders = [f for f in _executable_text_fragments(source) if "status" in f]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
