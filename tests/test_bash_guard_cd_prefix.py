"""Contract tests for the `cd "<P>" && <approved command>` allowance in
`em-workflow/hooks/bash_guard.py`.

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

Feature cd-prefix-canonical-path-only, task0001
(feature-docs/cd-prefix-canonical-path-only/tasks/task0001.md): the path check
allows only a canonical absolute path strictly below an area that lies inside
the main worktree, and refuses an over-long path before any file-system
access. It no longer reproduces Bash's path resolution: a path is never
normalized and then accepted, a link is never followed to a destination, and
no location receives special handling.

- AC-1: the allowed directories, from the main worktree and from a git
  worktree (`ALLOW_CASES`, `TestAc1AllowedPrefixForm`).
- AC-2: non-canonical text, links, and other paths are silent through the hook
  and False for a direct `is_below` call (`TestCanonicalPathOnly`).
- AC-3: the length bound is checked first, in the candidate decision and in
  `is_below`, with a run-time bound; boundary lengths; the file-system call
  count grows linearly (`TestLengthBound`).
- AC-4: the area containment rule, with the three link layouts of the fixture
  (`TestAreaContainment`).
- AC-5: undecidable input is not allowed and never raises, and the path check
  starts no child process (`TestFailClosed`); a refusal pattern in the remainder
  still denies (`TestAc4RefusalPatternStillDenies`).
- AC-6: the removed symbols are gone, and the module docstring's path item, the
  `is_below` docstring and the protocol's path item state the new condition and
  none of the old one (`TestRemovedSymbols`, `TestPathConditionWording`).
- AC-7: no test names a removed symbol; this module imports the standard
  library only (`TestRemovedSymbolsAreNotNamed`, `TestAc7StandardLibraryOnly`).

Earlier features, as they apply now. A form whose path the new check refuses is
a silent case.

- implementer-cd-verbatim-conflict, task0001: the allowed form, the syntax
  conditions, the path conditions, the refusal patterns, the commands without a
  prefix, the deny guidance (`TestAc1AllowedPrefixForm` to
  `TestAc6DenyGuidance`, `TestAc7StandardLibraryOnly`).
- is-below-physical-fallback, task0001: a link outside the area, `..`, then a
  name under the target's parent, is silent (`TestFormerFallbackForms`); a
  logical destination outside the area, or a physical path that is not below
  the area, is silent (`TestPhysicalFallbackNotAllowed`); an embedded NUL makes
  the path check return False (`TestNulInPath`).
- cd-prefix-non-directory-dotdot, task0001: a regular file, a missing component
  or a link to either, placed before a `..`, is never allowed
  (`TestNonDirectoryBeforeDotDot`).
- cd-prefix-process-dependent-paths, task0001: a path that is, or passes
  through, a location under /proc or /dev/fd is never allowed, and the hook
  process's own working directory plays no part
  (`TestProcessDependentPathNotAllowed`, `TestProcessDependentPathCheck`,
  `TestLinkBoundAndProbeErrors`, `TestProcessDependentPathContract`).
- cd-prefix-relative-link-target, task0001: a link, whatever its target text,
  is not below the area (`TestRelativeLinkTarget`).
- is-below-stalled-walk-proc-read, task0001: the forms that stall and then
  climb to /proc or /dev/fd are not below the area
  (`TestStalledWalkNeverReachesProc`, `TestStalledLogicalCorner`,
  `TestStalledWalkContract`).

Standard library only.
"""

import ast
import contextlib
import inspect
import io
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

        # Layouts for the area containment rule (feature
        # cd-prefix-canonical-path-only, FR5), one repository each. `resolved`
        # is the canonical path of an existing task directory; `through` is
        # the same directory named through the link.
        #   area-out:   .claude/worktrees/em-workflow -> directory outside the repository
        #   claude-out: .claude -> directory outside the repository
        #   area-in:    .claude/worktrees/em-workflow -> directory inside the repository
        repo = root / "repo-area-out"
        _make_repo(repo)
        target = root / "area-out-target"
        (target / "task0001").mkdir(parents=True)
        (repo / ".claude" / "worktrees").mkdir(parents=True)
        os.symlink(target, repo / ".claude" / "worktrees" / "em-workflow")
        self.layout_area_out = types.SimpleNamespace(
            repo=repo,
            resolved=target / "task0001",
            through=repo / ".claude" / "worktrees" / "em-workflow" / "task0001",
        )
        repo = root / "repo-claude-out"
        _make_repo(repo)
        target = root / "claude-out-target"
        (target / "worktrees" / "em-workflow" / "task0001").mkdir(parents=True)
        os.symlink(target, repo / ".claude")
        self.layout_claude_out = types.SimpleNamespace(
            repo=repo,
            resolved=target / "worktrees" / "em-workflow" / "task0001",
            through=repo / ".claude" / "worktrees" / "em-workflow" / "task0001",
        )
        repo = root / "repo-area-in"
        _make_repo(repo)
        target = repo / "real-area"
        (target / "task0001").mkdir(parents=True)
        (repo / ".claude" / "worktrees").mkdir(parents=True)
        os.symlink(target, repo / ".claude" / "worktrees" / "em-workflow")
        self.layout_area_in = types.SimpleNamespace(
            repo=repo,
            resolved=target / "task0001",
            through=repo / ".claude" / "worktrees" / "em-workflow" / "task0001",
        )

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
        self.store_layouts = root / "approvals-layouts.json"
        for layout in (self.layout_area_out, self.layout_claude_out, self.layout_area_in):
            self.record(self.store_layouts, layout.repo, APPROVED_COMMANDS)
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

# Feature is-below-physical-fallback AC-2, as it stands now: the logical path
# is absent or a file, the physical path is an existing directory strictly below
# the area. Bash lands there through its physical-path fallback; the path check
# does not follow it, so every form is silent (feature
# cd-prefix-canonical-path-only, TS3).
FORMER_FALLBACK_FORMS = (
    ("link outside the area, .., then a directory under the target's parent",
     "@HOP@/../sub"),
    ("same, a deeper directory under the target's parent", "@HOP@/../sub/deeper"),
    ("same, the target's parent itself is the destination", "@HOPTASK@/../task0001"),
    ("logical path is an existing file, physical path is a directory below the area",
     "@HOPDIR@/hop/../sub"),
)

FORMER_FALLBACK_CASES = tuple(
    (SILENT, label, 'cd "' + form + '" && ' + PLAIN_COMMAND)
    for label, form in FORMER_FALLBACK_FORMS
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
) + TM1_CASES + TM2_CASES + NON_DIRECTORY_DOTDOT_CASES + FORMER_FALLBACK_CASES


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


class TestFormerFallbackForms(CdPrefixCase):
    """Feature is-below-physical-fallback AC-2, as it stands now (feature
    cd-prefix-canonical-path-only FR1, FR4; TS3): the logical path is not an
    existing directory and the physical path is an existing directory strictly
    below the area. Bash lands there through its physical-path fallback; the
    path check does not follow it, so each form is silent through the hook and
    False for a direct call. (The `/proc/self/root/..` prefix form that was
    AC-1 there is silent too; see TestProcessDependentPathNotAllowed.)"""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)

    def test_ac2_link_dotdot_name_forms_are_silent_from_the_main_worktree(self):
        self.check_cases(FORMER_FALLBACK_CASES, FIX.repo)

    def test_ac2_link_dotdot_name_forms_are_silent_from_a_git_worktree(self):
        self.check_cases(FORMER_FALLBACK_CASES, FIX.worktree)

    def test_ac2_link_dotdot_name_forms_are_not_below_the_area(self):
        for label, template in FORMER_FALLBACK_FORMS:
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(FIX.expand(template), self.area), False)

    def test_ac2_the_fixture_layout_matches_the_claimed_logical_paths(self):
        # Guards the fixture: the logical path of each form really is absent
        # (or a file), and its physical path a directory below the area.
        absent = os.path.normpath(str(FIX.hop) + "/../sub")
        self.assertFalse(os.path.exists(absent))
        self.assertTrue(os.path.isdir(os.path.realpath(str(FIX.hop) + "/../sub")))
        as_file = os.path.normpath(str(FIX.hopdir) + "/hop/../sub")
        self.assertTrue(os.path.isfile(as_file))
        self.assertTrue(
            os.path.isdir(os.path.realpath(str(FIX.hopdir) + "/hop/../sub"))
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
    """cd-prefix-non-directory-dotdot AC-1 .. AC-4, AC-6, AC-7, as they stand
    now: a regular file, a missing component, or a link to either, placed before
    a `..`, is never allowed, because a `..` component alone refuses the path."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)

    # -- AC-1 -------------------------------------------------------------

    def test_ac1_the_path_check_is_false_for_a_non_directory_before_dotdot(self):
        for label, template in NON_DIRECTORY_FORMS:
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(FIX.expand(template), self.area), False)

    def test_ac1_the_path_check_is_true_only_for_the_canonical_directory_forms(self):
        for label, path, expected in (
            ("existing directory below the area", str(FIX.inside), True),
            ("link, .., then a name under the target's parent",
             FIX.expand("@HOP@/../sub"), False),
        ):
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), expected)

    @unittest.skipUnless(os.path.isdir(PROC_ROOT), "/proc/self/root is not a directory")
    def test_ac1_proc_self_root_dotdot_in_front_is_never_below(self):
        # The non-directory forms stay False with the prefix in front. The
        # plain inside directory, which this test used to expect True, is
        # False too: the prefix is a link component and a `..` component, so
        # the path is not canonical, whatever it resolves to.
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
        procdep/names/link-proc, link-dot-proc, link-dev-fd
                                 links whose relative targets are `proc`,
                                 `./proc` and `dev/fd` (directories of names)
        procdep/names/link-abs-proc, link-abs-dot-proc, link-abs-dev-fd
                                 control links whose absolute targets name the
                                 same locations: <names>/proc, <names>/./proc
                                 and <names>/dev/fd
        procdep/links/...        links inside the area to /proc and /dev/fd
        procdep/links/climb-link a link whose relative target climbs to the
                                 root with `..` components (at least as many
                                 as the path components of links, so the
                                 count follows the depth of the temporary
                                 directory) and then names proc/self/cwd
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
        # Relative targets that name directories of names, and controls whose
        # absolute targets name the same locations.
        self.relative_name_links = (
            ("proc", _link("proc", self.names / "link-proc")),
            ("./proc", _link("./proc", self.names / "link-dot-proc")),
            ("dev/fd", _link("dev/fd", self.names / "link-dev-fd")),
        )
        self.absolute_name_links = (
            (str(self.names / "proc"),
             _link(str(self.names / "proc"), self.names / "link-abs-proc")),
            (str(self.names) + "/./proc",
             _link(str(self.names) + "/./proc", self.names / "link-abs-dot-proc")),
            (str(self.names / "dev" / "fd"),
             _link(str(self.names / "dev" / "fd"), self.names / "link-abs-dev-fd")),
        )
        # A relative target that climbs to the root and then names /proc. The
        # number of `..` follows the depth of the links directory (surplus
        # `..` at the root stay at the root).
        self.climb_target = "/".join([".."] * len(self.links.parts) + ["proc", "self", "cwd"])
        self.climb_link = _link(self.climb_target, self.links / "climb-link")
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
    /dev/fd is judged as if it had no cd prefix, so there is no output. Since
    feature cd-prefix-canonical-path-only that holds because such a path is
    not canonical or holds a link component, not because of the location."""

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

    def test_ac6_a_short_chain_of_links_is_silent(self):
        # A chain of three links ends below the area, but a link is not a
        # canonical path, however short the chain.
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                decision, _ = decide(
                    FIX.run_hook(self.prefixed(str(self.layout.chain(3))), cwd)
                )
                self.assertEqual(decision, SILENT)


class TestProcessDependentPathCheck(unittest.TestCase):
    """AC-2, AC-3, AC-4, AC-5 (module level): the path check applied to the
    area of the fixture. A form under /proc or /dev/fd is False; a directory
    inside the area that is merely named like one is below the area."""

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

    def test_ac4_the_canonical_in_area_forms_are_below(self):
        for label, path in (
            ("existing directory below the area", str(FIX.inside)),
            ("deeper directory below the area", str(FIX.deep)),
        ):
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), True)

    # -- AC-5 -------------------------------------------------------------

    @needs_proc
    def test_ac5_the_proc_self_root_dotdot_prefix_form_is_false(self):
        for target in (FIX.worktree, FIX.inside):
            with self.subTest(target=target.name):
                path = PROC_ROOT + "/.." + str(target)
                self.assertIs(self.guard.is_below(path, self.area), False)


class TestLinkBoundAndProbeErrors(unittest.TestCase):
    """AC-6 (TM-3, TM-4): a link loop, a chain of links of any length, and an
    error while a path component is probed make the path check False."""

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

    def test_ac6_a_chain_of_links_is_false_whatever_its_length(self):
        # Every chain ends in a directory below the area, but a link is never
        # a canonical path.
        for count in (3, 40, 41, 45):
            with self.subTest(links=count):
                self.assertIs(
                    self.guard.is_below(str(self.layout.chain(count)), self.area), False
                )

    def test_ac6_an_error_while_a_path_component_is_probed_makes_the_check_false(self):
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
            *[str(link) for _target, link in self.layout.relative_name_links],
            *[str(link) for _target, link in self.layout.absolute_name_links],
            str(self.layout.climb_link) + "/" + SHARED,
        ]
        with _working_directory(self.layout.work), _no_child_process():
            for path in paths:
                self.guard.is_below(path, self.area)


# ---------------------------------------------------------------------------
# Feature cd-prefix-relative-link-target, task0001, as it stands now (feature
# cd-prefix-canonical-path-only): a link is not below the area whatever its
# target text is, relative or absolute, and whether or not the text reads like
# /proc or /dev/fd.
# ---------------------------------------------------------------------------


class TestRelativeLinkTarget(CdPrefixCase):
    """AC-1 .. AC-3 (FR1, FR2, FR3, NFR2; TM-1, TM-2), as they stand now: a link
    with a relative target and a link with an absolute target are both not
    below the area, at the module level and through the hook."""

    @classmethod
    def setUpClass(cls):
        cls.layout = Layout()
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)

    def prefixed(self, written):
        return 'cd "' + written + '" && ' + PLAIN_COMMAND

    def assert_would_have_been_below(self, written):
        # Guards the fixture: the form names an existing directory strictly
        # below the area, so the path check has no other reason to refuse it.
        self.assertTrue(os.path.isdir(written), written)
        self.assertTrue(
            self.guard.strictly_below(os.path.realpath(written), self.area), written
        )

    # -- AC-1 -------------------------------------------------------------

    def test_ac1_the_fixture_links_have_the_claimed_relative_targets(self):
        for target, link in self.layout.relative_name_links:
            with self.subTest(target=target):
                self.assertEqual(os.readlink(str(link)), target)
                self.assertFalse(os.path.isabs(target))
                self.assert_would_have_been_below(str(link))

    def test_ac1_a_link_with_a_relative_target_naming_an_in_area_directory_is_not_below(self):
        for target, link in self.layout.relative_name_links:
            with self.subTest(target=target):
                self.assertIs(self.guard.is_below(str(link), self.area), False)

    def test_ac1_the_hook_is_silent_for_each_relative_link(self):
        for cwd in (FIX.repo, FIX.worktree):
            for target, link in self.layout.relative_name_links:
                with self.subTest(cwd=cwd.name, target=target):
                    proc = FIX.run_hook(self.prefixed(str(link)), cwd)
                    decision, _ = decide(proc)
                    self.assertEqual(decision, SILENT)

    # -- AC-2 -------------------------------------------------------------

    def test_ac2_a_link_with_an_absolute_target_naming_the_same_location_is_not_below(self):
        for target, link in self.layout.absolute_name_links:
            with self.subTest(target=target):
                self.assertEqual(os.readlink(str(link)), target)
                self.assertTrue(os.path.isabs(target))
                self.assert_would_have_been_below(str(link))
                self.assertIs(self.guard.is_below(str(link), self.area), False)

    def test_ac2_the_hook_is_silent_for_each_absolute_link(self):
        for cwd in (FIX.repo, FIX.worktree):
            for target, link in self.layout.absolute_name_links:
                with self.subTest(cwd=cwd.name, target=target):
                    proc = FIX.run_hook(self.prefixed(str(link)), cwd)
                    decision, _ = decide(proc)
                    self.assertEqual(decision, SILENT)

    # -- AC-3 -------------------------------------------------------------

    def test_ac3_the_climbing_link_has_a_relative_target_with_enough_dotdot(self):
        target = os.readlink(str(self.layout.climb_link))
        self.assertFalse(os.path.isabs(target))
        parts = target.split("/")
        self.assertEqual(parts[-3:], ["proc", "self", "cwd"])
        climbing = parts[:-3]
        self.assertEqual(set(climbing), {".."})
        self.assertGreaterEqual(len(climbing), len(self.layout.links.parts) - 1)

    @needs_proc
    def test_ac3_a_relative_target_climbing_to_the_root_and_naming_proc_is_false(self):
        written = str(self.layout.climb_link) + "/" + SHARED
        with _working_directory(self.layout.work):
            self.assert_would_have_been_below(written)
            self.assertIs(self.guard.is_below(written, self.area), False)

    @needs_proc
    def test_ac3_the_hook_is_silent_for_the_climbing_link(self):
        written = str(self.layout.climb_link) + "/" + SHARED
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                proc = FIX.run_hook(self.prefixed(written), cwd, process_cwd=self.layout.work)
                decision, _ = decide(proc)
                self.assertEqual(decision, SILENT)


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


# ---------------------------------------------------------------------------
# Feature is-below-stalled-walk-proc-read, task0001, as it stands now (feature
# cd-prefix-canonical-path-only): a form that stalls at an absent or
# non-directory component and then climbs to /proc or /dev/fd holds a link or a
# `..` component, so it is not a canonical path and is not below the area.
# ---------------------------------------------------------------------------

PROC_TAIL = ["proc", "self", "cwd"]


def _climb(depth_path, placed):
    """The `..` components that climb to the root from a location `placed`
    components below depth_path. Counted as Layout.climb_target counts, from
    the number of path parts of depth_path; surplus `..` at the root stay at
    the root."""
    return [".."] * (len(depth_path.parts) + placed)


class StalledLayout:
    """A dedicated subdirectory of procdep for the stalled forms, under names
    no other test uses, so the layout seen by the other tests is unchanged.

        stalled/links/inner      an existing directory below the area
        stalled/links/regfile    a regular file
        stalled/links/link-a     relative target proc/missing/, `..` up to the
                                 root, then proc/self/cwd         (form a)
        stalled/links/link-b     the same with x/missing/          (form b)
        stalled/links/link-c     absolute target <inside>/missing/, `..` up to
                                 the root, then proc/self/cwd      (form c)
        stalled/links/link-d     relative target regfile/, `..` up to the
                                 root, then proc/self/cwd          (form d)
        stalled/links/link-e-<n> like form b, ending in dev/fd/<n> (form e)
        stalled/corner/...       the logical-path corner: written as
                                 corner/hop/../name, hop is a link to
                                 corner/hopdest/inner, corner/hopdest/name is
                                 an existing directory, and corner/name is a
                                 stalling link that climbs to
                                 proc/self/cwd/shared
    """

    def __init__(self):
        self.base = Layout()
        self.top = self.base.top / "stalled"
        self.links = self.top / "links"
        self.corner = self.top / "corner"
        self.inner = self.links / "inner"
        hopdest = self.corner / "hopdest"
        for directory in (self.inner, hopdest / "inner", hopdest / "name"):
            directory.mkdir(parents=True, exist_ok=True)
        self.regular_file = self.links / "regfile"
        if not self.regular_file.exists():
            self.regular_file.write_text("not a directory\n", encoding="utf-8")

        def climbing(head, depth_path, placed, tail):
            return head + "/".join(_climb(depth_path, placed) + tail)

        self.form_a = _link(
            climbing("proc/missing/", self.links, 2, PROC_TAIL), self.links / "link-a"
        )
        self.form_b = _link(
            climbing("x/missing/", self.links, 2, PROC_TAIL), self.links / "link-b"
        )
        self.form_c = _link(
            climbing(str(FIX.inside) + "/missing/", FIX.inside, 1, PROC_TAIL),
            self.links / "link-c",
        )
        self.form_d = _link(
            climbing("regfile/", self.links, 1, PROC_TAIL), self.links / "link-d"
        )
        # Only the as-written resolution goes through form b; the logical path
        # collapses past it and names the existing directory.
        self.physical_only = str(self.form_b) + "/../inner"
        # The logical-path corner.
        self.corner_hop = _link(str(hopdest / "inner"), self.corner / "hop")
        self.corner_name = _link(
            climbing("x/missing/", self.corner, 2, PROC_TAIL + [SHARED]),
            self.corner / "name",
        )
        self.corner_written = str(self.corner) + "/hop/../name"

    def dev_fd_link(self, fd):
        """Form e: like form b, ending in dev/fd/<fd>."""
        target = "x/missing/" + "/".join(_climb(self.links, 2) + ["dev", "fd", str(fd)])
        return _link(target, self.links / ("link-e-%d" % fd))

    def proc_forms(self):
        """(label, written path, link that the walk reads) for the forms that
        end in /proc/self/cwd."""
        return [
            ("(a) relative target proc/missing/", str(self.form_a), str(self.form_a)),
            ("(b) relative target x/missing/", str(self.form_b), str(self.form_b)),
            ("(c) absolute target <inside>/missing/", str(self.form_c), str(self.form_c)),
            ("(d) target stalls at a regular file", str(self.form_d), str(self.form_d)),
            ("physical-only variant of (b)", self.physical_only, str(self.form_b)),
        ]


class TestStalledWalkNeverReachesProc(unittest.TestCase):
    """AC-1 (FR1, FR2, FR7, FR8, NFR2), as it stands now: a link form that
    stalls and then climbs to /proc or /dev/fd is not below the area."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.layout = StalledLayout()

    # -- AC-1 -------------------------------------------------------------

    def test_ac1_the_fixture_links_stall_at_an_absent_stage_or_a_regular_file(self):
        # Guards the fixture: each target names, first, a stage that is absent
        # or not a directory, and then climbs to the root before naming /proc.
        for label, link, stall in (
            ("a", self.layout.form_a, self.layout.links / "proc"),
            ("b", self.layout.form_b, self.layout.links / "x"),
            ("c", self.layout.form_c, FIX.inside / "missing"),
            ("d", self.layout.form_d, self.layout.regular_file),
        ):
            with self.subTest(form=label):
                target = os.readlink(str(link))
                self.assertEqual(target.split("/")[-3:], PROC_TAIL)
                self.assertEqual(os.path.isabs(target), label == "c")
                if label == "d":
                    self.assertTrue(stall.is_file())
                else:
                    self.assertFalse(os.path.lexists(str(stall)))
                # Enough `..` to climb from the location after the stall.
                climbing = [part for part in target.split("/") if part == ".."]
                self.assertGreaterEqual(len(climbing), len(stall.parts))

    @needs_proc
    def test_ac1_the_fixture_lenient_realpath_lands_below_the_area(self):
        # Guards the fixture: with the process in work, the lenient realpath of
        # each /proc form lands on an existing directory strictly below the
        # area, so the form would have been below the area but for the link.
        with _working_directory(self.layout.base.work):
            for label, written, _link in self.layout.proc_forms()[:4]:
                with self.subTest(form=label):
                    landed = os.path.realpath(written)
                    self.assertEqual(landed, str(self.layout.base.work))
                    self.assertTrue(os.path.isdir(landed))
                    self.assertTrue(self.guard.strictly_below(landed, self.area))

    @needs_proc
    def test_ac1_a_stalled_form_that_climbs_to_proc_is_false(self):
        with _working_directory(self.layout.base.work):
            for label, written, _link in self.layout.proc_forms():
                with self.subTest(form=label):
                    self.assertIs(self.guard.is_below(written, self.area), False)

    @needs_dev_fd
    def test_ac1_a_stalled_form_that_climbs_to_dev_fd_is_false(self):
        fd = os.open(str(self.layout.base.under_work), os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        link = self.layout.dev_fd_link(fd)
        with _working_directory(self.layout.base.work):
            landed = os.path.realpath(str(link))
            self.assertEqual(landed, str(self.layout.base.under_work))
            self.assertTrue(self.guard.strictly_below(landed, self.area))
            self.assertIs(self.guard.is_below(str(link), self.area), False)


class TestStalledLogicalCorner(CdPrefixCase):
    """AC-2 (FR1, FR2, FR7, NFR1, NFR2): written as <hop>/../<name>, the
    physical resolution lands on an existing directory below the area, while
    the logical collapse lands on a stalling link that climbs to
    proc/self/cwd/shared. The form holds a `..` component, so it is not a
    canonical path."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.layout = StalledLayout()
        cls.written = cls.layout.corner_written

    def prefixed(self, written):
        return 'cd "' + written + '" && ' + PLAIN_COMMAND

    @needs_proc
    def test_ac2_the_fixture_resolves_below_the_area_in_both_ways(self):
        # Guards the fixture, outside any recording. With the process in work,
        # the logical and the physical realpath are existing directories
        # strictly below the area, so the form has no other reason to be
        # refused than its `..` component.
        with _working_directory(self.layout.base.work):
            logical = os.path.realpath(os.path.normpath(self.written))
            physical = os.path.realpath(self.written)
            self.assertEqual(logical, str(self.layout.base.under_work))
            self.assertEqual(physical, str(self.layout.corner / "hopdest" / "name"))
            for resolved in (logical, physical):
                self.assertTrue(os.path.isdir(resolved))
                self.assertTrue(self.guard.strictly_below(resolved, self.area))

    @needs_proc
    def test_ac2_is_below_is_false(self):
        with _working_directory(self.layout.base.work):
            self.assertIs(self.guard.is_below(self.written, self.area), False)

    def test_ac2_non_canonical_text_returns_false_before_any_realpath_call(self):
        with mock.patch.object(
            os.path, "realpath", side_effect=AssertionError("realpath called after a refusal")
        ):
            self.assertIs(self.guard.is_below(self.written, self.area), False)

    @needs_proc
    def test_ac2_the_hook_is_silent_from_the_main_worktree_and_from_a_git_worktree(self):
        for cwd in (FIX.repo, FIX.worktree):
            with self.subTest(cwd=cwd.name):
                proc = FIX.run_hook(
                    self.prefixed(self.written), cwd, process_cwd=self.layout.base.work
                )
                decision, _ = decide(proc)
                self.assertEqual(decision, SILENT)


class TestStalledWalkContract(unittest.TestCase):
    """AC-7 (FR6, NFR3, NFR4): the path check starts no child process, whatever
    the form."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.layout = StalledLayout()

    @needs_proc
    def test_ac7_the_path_check_starts_no_child_process_for_the_added_forms(self):
        fd = os.open(str(self.layout.base.under_work), os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        paths = [written for _label, written, _link in self.layout.proc_forms()]
        paths += [
            str(self.layout.dev_fd_link(fd)),
            self.layout.corner_written,
            str(FIX.dangling) + "/../procdep/chain40/l0",
            str(FIX.inside) + "/does-not-exist/../sub",
        ]
        with _working_directory(self.layout.base.work), _no_child_process():
            for path in paths:
                self.guard.is_below(path, self.area)


# ---------------------------------------------------------------------------
# Feature cd-prefix-canonical-path-only, task0001: the path check allows only a
# canonical absolute path strictly below an area that lies inside the main
# worktree, and refuses an over-long path before any file-system access.
# ---------------------------------------------------------------------------

# The file-system entry points the path check could reach. A recording wraps
# each one and lets the call through.
FILE_SYSTEM_ENTRY_POINTS = (
    (os, ("stat", "lstat", "readlink", "scandir", "listdir", "access")),
    (os.path, ("realpath", "isdir", "isfile", "exists", "lexists", "islink")),
)


@contextlib.contextmanager
def _recorded_file_system():
    """Record the name of every file-system entry point called while active.
    The calls go through. Yields the list of names."""
    calls = []

    def recording(name, real):
        def call(*args, **kwargs):
            calls.append(name)
            return real(*args, **kwargs)

        return call

    with contextlib.ExitStack() as stack:
        for owner, names in FILE_SYSTEM_ENTRY_POINTS:
            for name in names:
                stack.enter_context(
                    mock.patch.object(owner, name, new=recording(name, getattr(owner, name)))
                )
        yield calls


def _run_hook_in_process(guard, command, cwd, store):
    """(exit code, stdout, stderr) of guard.hook_main() for a PreToolUse payload,
    run in this process so that a double can be placed inside the path check."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, FIX.env(store), clear=True):
        with mock.patch.object(sys, "stdin", io.StringIO(payload)):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = guard.hook_main()
    return code, out.getvalue(), err.getvalue()


@contextlib.contextmanager
def _failing_for(owner, name, failing_path, error):
    """owner.<name> raises error when its first argument is failing_path (or,
    for the bound source, on every call); any other call goes through. Yields
    the list of the failures raised."""
    real = getattr(owner, name)
    raised = []

    def call(*args, **kwargs):
        if name == "pathconf" or (args and os.fspath(args[0]) == failing_path):
            raised.append(failing_path)
            raise error
        return real(*args, **kwargs)

    with mock.patch.object(owner, name, new=call):
        yield raised


def _refused_forms():
    """(label, written path) for every form the path check refuses: non-canonical
    text, links, and other paths (feature cd-prefix-canonical-path-only, TS2,
    TS3, TS4)."""
    layout = Layout()
    inside, region = str(FIX.inside), str(FIX.region)
    forms = [
        # Non-canonical text.
        ("trailing slash", inside + "/"),
        ("doubled slash in the middle", region + "//task0001"),
        ("doubled leading slash", "/" + inside),
        ("dot component at the end", inside + "/."),
        ("dot component in the middle", region + "/./task0001"),
        ("dotdot component at the end", inside + "/.."),
        ("dotdot component between names", inside + "/sub/../sub"),
        # Links.
        ("link inside the area to a directory inside the area", str(FIX.hop_in)),
        ("link to a directory outside the area", str(FIX.link_out)),
        ("broken link", str(FIX.dangling)),
        ("link to a file", str(FIX.link_to_file)),
    ]
    forms += [
        ("former fallback form: " + label, FIX.expand(template))
        for label, template in FORMER_FALLBACK_FORMS
    ]
    forms += [
        ("link with the relative target " + target, str(link))
        for target, link in layout.relative_name_links
    ]
    forms += [
        ("link with the absolute target " + target, str(link))
        for target, link in layout.absolute_name_links
    ]
    # Other paths.
    forms += [
        ("root", "/"),
        ("the area itself", region),
        ("sibling sharing the name prefix", str(FIX.sibling)),
        ("another repository's area", str(FIX.other_inside)),
        ("nonexistent path", str(FIX.missing)),
        ("regular file", str(FIX.file)),
    ]
    if os.path.isdir(PROC_ROOT):
        forms += [
            ("proc self root, then the inside directory", PROC_ROOT + inside),
            ("proc self root, .., then the inside directory", PROC_ROOT + "/.." + inside),
        ]
    if os.path.isdir(DEV_FD):
        forms.append(("dev fd", DEV_FD))
    return forms


CANONICAL_FORMS = (
    ("directly below the area", lambda: str(FIX.inside)),
    ("any depth below the area", lambda: str(FIX.deep)),
    ("name with a space", lambda: str(FIX.spaced)),
    ("name with &&", lambda: str(FIX.ampersand)),
    ("git worktree below the area", lambda: str(FIX.worktree)),
)


class TestCanonicalPathOnly(CdPrefixCase):
    """AC-2 (FR1, FR4, FR9; TS2, TS3, TS4; TM-1): every non-canonical, link and
    other form is silent through the hook and False for a direct call, so no
    form is accepted after normalization."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.forms = _refused_forms()

    def test_ac2_the_canonical_directories_are_below_the_area(self):
        for label, make in CANONICAL_FORMS:
            with self.subTest(label=label):
                path = make()
                self.assertIs(self.guard.is_below(path, self.area), True)

    def test_ac2_the_form_list_holds_every_group_of_the_criterion(self):
        labels = [label for label, _path in self.forms]
        for needle in (
            "trailing slash",
            "doubled slash in the middle",
            "doubled leading slash",
            "dot component at the end",
            "dot component in the middle",
            "dotdot component at the end",
            "dotdot component between names",
            "link inside the area to a directory inside the area",
            "link to a directory outside the area",
            "broken link",
            "link to a file",
            "former fallback form: ",
            "link with the relative target ",
            "link with the absolute target ",
            "root",
            "the area itself",
            "sibling sharing the name prefix",
            "another repository's area",
            "nonexistent path",
            "regular file",
        ):
            with self.subTest(needle=needle):
                self.assertTrue(any(label.startswith(needle) for label in labels))

    def test_ac2_is_below_is_false_for_each_refused_form(self):
        for label, path in self.forms:
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac2_each_refused_form_is_silent_through_the_hook_from_both_cwds(self):
        for cwd in (FIX.repo, FIX.worktree):
            for label, path in self.forms:
                with self.subTest(cwd=cwd.name, label=label):
                    command = 'cd "' + path + '" && ' + PLAIN_COMMAND
                    decision, _ = decide(FIX.run_hook(command, cwd))
                    self.assertEqual(decision, SILENT)

    def test_ac2_the_path_is_never_normalized_before_the_check(self):
        # The canonical equivalent of each non-canonical text is judged on its
        # own (below the area, except for the area itself); the text as written
        # is refused.
        inside, region = str(FIX.inside), str(FIX.region)
        for label, written, canonical in (
            ("trailing slash", inside + "/", inside),
            ("doubled slash in the middle", region + "//task0001", inside),
            ("doubled leading slash", "/" + inside, inside),
            ("dot component at the end", inside + "/.", inside),
            ("dot component in the middle", region + "/./task0001", inside),
            ("dotdot component at the end", inside + "/..", region),
            ("dotdot component between names", inside + "/sub/../sub", inside + "/sub"),
        ):
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(canonical, self.area), canonical != region)
                self.assertIs(self.guard.is_below(written, self.area), False)

    def test_ac2_a_link_inside_the_area_to_an_in_area_directory_is_a_real_link(self):
        # Guards the fixture: the link names a directory inside the area, so
        # only the link itself can be the reason for the refusal.
        target = os.path.realpath(str(FIX.hop_in))
        self.assertTrue(os.path.islink(str(FIX.hop_in)))
        self.assertTrue(os.path.isdir(target))
        self.assertTrue(self.guard.strictly_below(target, self.area))


class TestLengthBound(unittest.TestCase):
    """AC-3 (FR2, NFR4; TS5, TS6, TS13; TM-2): the length bound is checked first,
    in the candidate decision and in `is_below`, before `worktree_area()` and any
    file-system access."""

    TAIL = "/x" * 32000

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.common_dir = str(FIX.repo / ".git")

    def command(self, path):
        return 'cd "' + path + '" && ' + PLAIN_COMMAND

    def over_bound_paths(self):
        return (
            ("a path outside the area", "/dev/null" + self.TAIL),
            ("a path below the area", self.area + self.TAIL),
        )

    # -- AC-3, first bullet -------------------------------------------------

    def test_ac3_over_bound_paths_are_false_in_the_candidate_decision(self):
        for label, path in self.over_bound_paths():
            with self.subTest(label=label):
                with mock.patch.object(
                    self.guard, "worktree_area", wraps=self.guard.worktree_area
                ) as area_double, _recorded_file_system() as calls:
                    result = self.guard.is_cd_prefixed_approved(
                        self.command(path), {PLAIN_COMMAND}, self.common_dir
                    )
                self.assertIs(result, False)
                area_double.assert_not_called()
                self.assertEqual(sorted(set(calls)), [])

    def test_ac3_over_bound_paths_are_false_in_is_below(self):
        for label, path in self.over_bound_paths():
            with self.subTest(label=label):
                with _recorded_file_system() as calls:
                    result = self.guard.is_below(path, self.area)
                self.assertIs(result, False)
                self.assertEqual(sorted(set(calls)), [])

    def test_ac3_over_bound_paths_are_silent_through_the_hook(self):
        for cwd in (FIX.repo, FIX.worktree):
            for label, path in self.over_bound_paths():
                with self.subTest(cwd=cwd.name, label=label):
                    decision, _ = decide(FIX.run_hook(self.command(path), cwd))
                    self.assertEqual(decision, SILENT)

    def test_ac3_the_recording_sees_a_call_when_the_length_is_within_the_bound(self):
        # Guards the recording the tests above rely on.
        with mock.patch.object(
            self.guard, "worktree_area", wraps=self.guard.worktree_area
        ) as area_double, _recorded_file_system() as calls:
            result = self.guard.is_cd_prefixed_approved(
                self.command(str(FIX.inside)), {PLAIN_COMMAND}, self.common_dir
            )
        self.assertIs(result, True)
        area_double.assert_called_once()
        self.assertTrue(calls)

    # -- AC-3, second and third bullets --------------------------------------

    def test_ac3_the_bound_is_the_limit_the_system_reports_for_the_root_directory(self):
        with mock.patch.object(os, "pathconf", wraps=os.pathconf) as source:
            self.guard.is_below(str(FIX.inside), self.area)
        source.assert_called_with("/", "PC_PATH_MAX")

    def test_ac3_a_bound_that_cannot_be_obtained_or_is_not_positive_refuses(self):
        path = str(FIX.inside)
        self.assertIs(self.guard.is_below(path, self.area), True)
        for label, double in (
            ("OSError", {"side_effect": OSError("simulated")}),
            ("ValueError", {"side_effect": ValueError("simulated")}),
            ("zero", {"return_value": 0}),
            ("negative", {"return_value": -1}),
        ):
            with self.subTest(label=label):
                with mock.patch.object(os, "pathconf", **double):
                    with _recorded_file_system() as calls:
                        self.assertIs(self.guard.is_below(path, self.area), False)
                    self.assertEqual(sorted(set(calls)), [])
                    self.assertIs(
                        self.guard.is_cd_prefixed_approved(
                            self.command(path), {PLAIN_COMMAND}, self.common_dir
                        ),
                        False,
                    )

    def test_ac3_a_length_equal_to_the_bound_is_refused_before_any_file_system_call(self):
        path = str(FIX.inside)
        size = len(os.fsencode(path))
        with mock.patch.object(os, "pathconf", return_value=size):
            with _recorded_file_system() as calls:
                self.assertIs(self.guard.is_below(path, self.area), False)
            self.assertEqual(sorted(set(calls)), [])

    def test_ac3_a_length_one_byte_shorter_passes_the_length_check(self):
        path = str(FIX.inside)
        size = len(os.fsencode(path))
        with mock.patch.object(os, "pathconf", return_value=size + 1):
            with _recorded_file_system() as calls:
                self.assertIs(self.guard.is_below(path, self.area), True)
            self.assertTrue(calls)
        # Decided by the remaining conditions: a nonexistent path one byte
        # shorter than the bound is False, after the file system was consulted.
        missing = str(FIX.missing)
        size = len(os.fsencode(missing))
        with mock.patch.object(os, "pathconf", return_value=size + 1):
            with _recorded_file_system() as calls:
                self.assertIs(self.guard.is_below(missing, self.area), False)
            self.assertTrue(calls)

    def test_ac3_the_length_is_counted_in_bytes_of_the_file_system_encoding(self):
        path = str(FIX.inside) + "/\u00e9"
        try:
            encoded = os.fsencode(path)
        except ValueError:
            self.skipTest("the file-system encoding cannot encode the test character")
        if len(encoded) <= len(path):
            self.skipTest("the test character is not multi-byte in the file-system encoding")
        with mock.patch.object(os, "pathconf", return_value=len(path) + 1):
            with _recorded_file_system() as calls:
                self.assertIs(self.guard.is_below(path, self.area), False)
            self.assertEqual(sorted(set(calls)), [])

    # -- AC-3, fourth bullet ------------------------------------------------

    def chain(self, depth):
        directory = FIX.region / "lengths" / ("chain%d" % depth)
        for _ in range(depth):
            directory = directory / "n"
        directory.mkdir(parents=True, exist_ok=True)
        return str(directory)

    def counted_calls(self, path):
        with _recorded_file_system() as calls:
            self.assertIs(self.guard.is_below(path, self.area), True)
        return len(calls)

    def test_ac3_the_file_system_call_count_grows_no_faster_than_linearly(self):
        short, long_ = self.chain(8), self.chain(32)
        short_parts, long_parts = len(Path(short).parts), len(Path(long_).parts)
        short_calls, long_calls = self.counted_calls(short), self.counted_calls(long_)
        self.assertGreater(long_calls, short_calls)
        # A count proportional to the number of components keeps this ratio
        # constant; a count that grows with its square does not.
        self.assertLessEqual(long_calls * short_parts, short_calls * long_parts)


class TestAreaContainment(CdPrefixCase):
    """AC-4 (FR5; TS7; TM-4): the resolved area is used only when it lies
    strictly below the realpath of the main worktree."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()

    def prefixed(self, path):
        return 'cd "' + str(path) + '" && ' + PLAIN_COMMAND

    def decide_in(self, layout, path):
        proc = FIX.run_hook(self.prefixed(path), layout.repo, FIX.store_layouts)
        return decide(proc)[0]

    def area_of(self, layout):
        return os.path.realpath(
            os.path.join(str(layout.repo), ".claude", "worktrees", "em-workflow")
        )

    def test_ac4_the_fixture_layouts_have_the_claimed_shape(self):
        for name, layout, inside in (
            ("area-out", FIX.layout_area_out, False),
            ("claude-out", FIX.layout_claude_out, False),
            ("area-in", FIX.layout_area_in, True),
        ):
            with self.subTest(layout=name):
                area = self.area_of(layout)
                self.assertIs(self.guard.strictly_below(area, str(layout.repo)), inside)
                # The canonical task directory is below the resolved area, and
                # the path through the link is not canonical.
                self.assertEqual(os.path.realpath(str(layout.resolved)), str(layout.resolved))
                self.assertTrue(self.guard.strictly_below(str(layout.resolved), area))
                self.assertTrue(os.path.isdir(str(layout.through)))
                self.assertNotEqual(os.path.realpath(str(layout.through)), str(layout.through))

    def test_ac4_worktree_area_is_none_when_the_area_resolves_outside(self):
        for name, layout in (
            ("area-out", FIX.layout_area_out),
            ("claude-out", FIX.layout_claude_out),
        ):
            with self.subTest(layout=name):
                self.assertIsNone(self.guard.worktree_area(str(layout.repo / ".git")))

    def test_ac4_worktree_area_is_the_resolved_area_when_it_resolves_inside(self):
        layout = FIX.layout_area_in
        self.assertEqual(
            self.guard.worktree_area(str(layout.repo / ".git")), self.area_of(layout)
        )

    def test_ac4_an_ordinary_area_is_still_returned(self):
        self.assertEqual(
            self.guard.worktree_area(str(FIX.repo / ".git")), str(FIX.region)
        )

    def test_ac4_nothing_is_allowed_when_the_area_resolves_outside(self):
        for name, layout in (
            ("area-out", FIX.layout_area_out),
            ("claude-out", FIX.layout_claude_out),
        ):
            for label, path in (
                ("canonical directory beyond the link", layout.resolved),
                ("path through the link", layout.through),
            ):
                with self.subTest(layout=name, label=label):
                    self.assertEqual(self.decide_in(layout, path), SILENT)

    def test_ac4_the_candidate_decision_is_false_when_the_area_resolves_outside(self):
        for layout in (FIX.layout_area_out, FIX.layout_claude_out):
            with self.subTest(repo=layout.repo.name):
                self.assertIs(
                    self.guard.is_cd_prefixed_approved(
                        self.prefixed(layout.resolved),
                        {PLAIN_COMMAND},
                        str(layout.repo / ".git"),
                    ),
                    False,
                )

    def test_ac4_the_resolved_canonical_path_is_allowed_when_the_area_resolves_inside(self):
        layout = FIX.layout_area_in
        self.assertEqual(self.decide_in(layout, layout.resolved), ALLOW)

    def test_ac4_the_path_through_the_link_is_silent_when_the_area_resolves_inside(self):
        layout = FIX.layout_area_in
        self.assertEqual(self.decide_in(layout, layout.through), SILENT)


class TestFailClosed(CdPrefixCase):
    """AC-5 (FR3, NFR2, NFR3, NFR5; TS8, TS15; TM-3): input on which the check
    cannot decide is not allowed, never raises, and never reaches the output."""

    UNENCODABLE = "\ud800"

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()
        cls.area = str(FIX.region)
        cls.common_dir = str(FIX.repo / ".git")

    def prefixed(self, path):
        return 'cd "' + path + '" && ' + PLAIN_COMMAND

    def undecidable_paths(self):
        inside = str(FIX.inside)
        return (
            ("NUL after an existing directory", inside + "\x00"),
            ("NUL inside a component", inside + "/su\x00b"),
            ("a character the file-system encoding cannot encode", inside + "/" + self.UNENCODABLE),
            ("an unencodable character right after the root", "/" + self.UNENCODABLE),
        )

    def test_ac5_the_fixture_character_cannot_be_encoded(self):
        with self.assertRaises(ValueError):
            os.fsencode(self.UNENCODABLE)

    def test_ac5_the_path_check_is_false_without_raising(self):
        for label, path in self.undecidable_paths():
            with self.subTest(label=label):
                self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac5_the_candidate_decision_contains_the_encoding_error_itself(self):
        # The length check of the candidate decision runs before is_below's own
        # guard, and before worktree_area().
        for label, path in self.undecidable_paths():
            with self.subTest(label=label):
                with mock.patch.object(
                    self.guard, "worktree_area", wraps=self.guard.worktree_area
                ) as area_double:
                    self.assertIs(
                        self.guard.is_cd_prefixed_approved(
                            self.prefixed(path), {PLAIN_COMMAND}, self.common_dir
                        ),
                        False,
                    )
                if self.UNENCODABLE in path:
                    area_double.assert_not_called()

    def test_ac5_an_injected_resolution_error_makes_the_path_check_false(self):
        path = str(FIX.inside)
        self.assertIs(self.guard.is_below(path, self.area), True)
        for error in (OSError("simulated"), ValueError("simulated")):
            for owner, name in ((os.path, "realpath"), (os, "lstat"), (os.path, "isdir")):
                with self.subTest(error=type(error).__name__, entry_point=name):
                    with mock.patch.object(owner, name, side_effect=error):
                        self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac5_an_error_while_the_bound_is_obtained_makes_the_path_check_false(self):
        path = str(FIX.inside)
        for error in (OSError("simulated"), ValueError("simulated")):
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(os, "pathconf", side_effect=error):
                    self.assertIs(self.guard.is_below(path, self.area), False)

    def test_ac5_a_resolution_error_while_the_area_is_resolved_is_not_allowed(self):
        for error in (OSError("simulated"), ValueError("simulated")):
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(os.path, "realpath", side_effect=error):
                    self.assertIsNone(self.guard.worktree_area(self.common_dir))

    def test_ac5_through_the_hook_an_undecidable_path_exits_zero_silently_without_allow(self):
        for cwd in (FIX.repo, FIX.worktree):
            for label, path in self.undecidable_paths():
                with self.subTest(cwd=cwd.name, label=label):
                    proc = FIX.run_hook(self.prefixed(path), cwd)
                    self.assertEqual(proc.returncode, 0)
                    self.assertEqual(proc.stderr, "")
                    decision, _ = decide(proc)
                    self.assertNotEqual(decision, ALLOW)

    def test_ac5_through_the_hook_an_injected_error_exits_zero_silently_without_allow(self):
        target = str(FIX.inside)
        command = self.prefixed(target)
        code, out, err = _run_hook_in_process(self.guard, command, FIX.repo, FIX.store)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], ALLOW)
        for error in (OSError("simulated"), ValueError("simulated")):
            for owner, name in (
                (os.path, "realpath"),
                (os, "lstat"),
                (os.path, "isdir"),
                (os, "pathconf"),
            ):
                with self.subTest(error=type(error).__name__, entry_point=name):
                    with _failing_for(owner, name, target, error) as raised:
                        code, out, err = _run_hook_in_process(
                            self.guard, command, FIX.repo, FIX.store
                        )
                    self.assertTrue(raised, "the injected error was never reached")
                    self.assertEqual((code, out, err), (0, "", ""))

    def test_ac5_the_path_check_starts_no_child_process_and_passes_no_path_to_one(self):
        paths = [path for _label, path in self.undecidable_paths()]
        paths += [path for _label, path in _refused_forms()]
        paths += [make() for _label, make in CANONICAL_FORMS]
        paths += ["/dev/null" + "/x" * 32000]
        with _no_child_process():
            for path in paths:
                self.guard.is_below(path, self.area)
                self.guard.is_cd_prefixed_approved(
                    self.prefixed(path), {PLAIN_COMMAND}, self.common_dir
                )


# The statements the three places that describe the path condition carry. Each
# is one contiguous phrase after whitespace is flattened and the text lower-cased.
PATH_CONDITION_NEEDLES = (
    "canonical absolute path",
    "no empty, `.` or `..` component other than the root",
    "strictly below the area",
    "equals its own realpath",
    "an existing directory",
    "never normalized and then accepted",
    "path-length limit that the operating system reports for the root directory",
    "greater than or equal to",
    "strictly below the realpath of the main worktree",
    "at any depth",
    "a resolution error counts as not below",
    "never used as the directory or argument of a child process",
)

# Terms of the checks this feature removed. None may appear in the three places.
OLD_CHECK_TERMS = ("logical path", "physical path", "/proc", "/dev/fd", "stage")

REMOVED_SYMBOLS = (
    "_stage_walk_refuses",
    "_under_proc_or_dev_fd",
    "FOLLOWED_LINK_LIMIT",
    "resolves_to_directory",
)


def _missing_path_condition_statements(text):
    """The needles the text does not carry."""
    flat = " ".join(text.split()).lower()
    return [needle for needle in PATH_CONDITION_NEEDLES if needle not in flat]


def _old_check_terms_in(text):
    """The terms of the removed checks the text carries, compared
    case-insensitively with whitespace flattened."""
    flat = " ".join(text.split()).lower()
    return [term for term in OLD_CHECK_TERMS if term in flat]


def _docstring_path_item(docstring):
    """The `path:` item of the `cd prefix:` paragraph, whitespace flattened."""
    match = re.search(r"^  - path:(.*?)^  - approval:", docstring, re.DOTALL | re.MULTILINE)
    return " ".join(match.group(1).split()) if match else None


def _rule_path_item(rule):
    """The path item of the Verbatim execution rule (already flattened)."""
    start = rule.find("the path is a canonical absolute path")
    end = rule.find("everything after the first `&&` matches")
    if start < 0 or end < start:
        return None
    return rule[start:end]


class TestRemovedSymbols(unittest.TestCase):
    """AC-6 (FR4; TS9): the module defines none of the removed symbols."""

    @classmethod
    def setUpClass(cls):
        cls.guard = _load_guard_module()

    def test_ac6_the_module_defines_none_of_the_removed_symbols(self):
        for name in REMOVED_SYMBOLS:
            with self.subTest(name=name):
                self.assertFalse(hasattr(self.guard, name))

    def test_ac6_no_definition_or_name_of_the_removed_symbols_is_in_the_source(self):
        tree = ast.parse(GUARD_PATH.read_text(encoding="utf-8"))
        identifiers = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                identifiers.add(node.name)
            elif isinstance(node, ast.Name):
                identifiers.add(node.id)
            elif isinstance(node, ast.Attribute):
                identifiers.add(node.attr)
        self.assertEqual(identifiers & set(REMOVED_SYMBOLS), set())

    def test_ac6_the_logical_and_physical_checks_are_gone_from_the_code(self):
        # The dual check compared the realpath of the normalized path with the
        # realpath of the path as written; no call to normpath is left on a
        # cd prefix path.
        source = inspect.getsource(self.guard.is_below)
        self.assertNotIn("normpath", source)


class TestPathConditionWording(unittest.TestCase):
    """AC-6 (FR7; TS9): the module docstring's path item, the `is_below`
    docstring and the protocol's path item state the new condition and none of
    the old one."""

    @classmethod
    def setUpClass(cls):
        guard = _load_guard_module()
        cls.rule = _verbatim_execution_rule(PROTOCOL_PATH.read_text(encoding="utf-8"))
        cls.places = {
            "module docstring, path item": _docstring_path_item(guard.__doc__),
            "is_below docstring": guard.is_below.__doc__,
            "protocol, path item": _rule_path_item(cls.rule) if cls.rule else None,
        }

    def test_ac6_all_three_places_are_found(self):
        self.assertIsNotNone(self.rule, "section 'Verbatim execution rule' not found")
        for name, text in self.places.items():
            with self.subTest(place=name):
                self.assertIsNotNone(text, f"{name} not found")
                self.assertTrue(text.strip())

    def test_ac6_each_place_states_the_new_condition(self):
        for name, text in self.places.items():
            with self.subTest(place=name):
                self.assertIsNotNone(text, f"{name} not found")
                self.assertEqual(_missing_path_condition_statements(text), [])

    def test_ac6_the_statement_matcher_fires_on_forged_text(self):
        for name, text in self.places.items():
            self.assertIsNotNone(text, f"{name} not found")
            flat = " ".join(text.split()).lower()
            self.assertEqual(
                _missing_path_condition_statements(flat),
                [],
                f"the {name} does not carry the statement the forgeries start from",
            )
            for needle in PATH_CONDITION_NEEDLES:
                with self.subTest(place=name, needle=needle):
                    forged = flat.replace(needle, "")
                    self.assertNotIn(needle, forged)
                    self.assertIn(needle, _missing_path_condition_statements(forged))

    def test_ac6_the_statement_matcher_does_not_pass_unrelated_text(self):
        self.assertEqual(
            _missing_path_condition_statements(""), list(PATH_CONDITION_NEEDLES)
        )
        self.assertNotEqual(
            _missing_path_condition_statements("the realpath of <path> only"), []
        )

    def test_ac6_no_place_holds_a_term_of_the_removed_checks(self):
        for name, text in self.places.items():
            with self.subTest(place=name):
                self.assertIsNotNone(text, f"{name} not found")
                self.assertEqual(_old_check_terms_in(text), [])

    def test_ac6_the_absence_matcher_fires_on_forged_text(self):
        for name, text in self.places.items():
            self.assertIsNotNone(text, f"{name} not found")
            for term in OLD_CHECK_TERMS:
                with self.subTest(place=name, term=term):
                    # Upper case and a line break inside the term, appended to
                    # the real text, must still be found.
                    broken = term.upper().replace(" ", "\n  ")
                    forged = text + " and then the " + broken + " rule"
                    self.assertIn(term, _old_check_terms_in(forged))

    def test_ac6_the_absence_matcher_stays_silent_on_clean_text(self):
        self.assertEqual(_old_check_terms_in(""), [])
        self.assertEqual(_old_check_terms_in("a canonical absolute path below the area"), [])

    def test_ac6_the_two_path_items_carry_the_same_statements_in_the_same_order(self):
        positions = {}
        for name in ("module docstring, path item", "protocol, path item"):
            flat = " ".join(self.places[name].split()).lower()
            positions[name] = sorted(
                PATH_CONDITION_NEEDLES, key=lambda needle: flat.find(needle)
            )
        self.assertEqual(
            positions["module docstring, path item"], positions["protocol, path item"]
        )


class TestRemovedSymbolsAreNotNamed(unittest.TestCase):
    """AC-7 (FR9; TS11): no test calls, patches or names a removed symbol."""

    @staticmethod
    def named_symbols(source):
        """Removed symbols the source calls, reads, or names as the target of a
        patch or a getattr, found in identifiers and in the string arguments of
        calls. A bare tuple of names, as in this module, is not a use."""
        tree = ast.parse(source)
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in REMOVED_SYMBOLS:
                found.add(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in REMOVED_SYMBOLS:
                found.add(node.attr)
            elif isinstance(node, ast.Call):
                arguments = list(node.args) + [keyword.value for keyword in node.keywords]
                for argument in arguments:
                    if (
                        isinstance(argument, ast.Constant)
                        and isinstance(argument.value, str)
                        and argument.value in REMOVED_SYMBOLS
                    ):
                        found.add(argument.value)
        return found

    def test_ac7_the_detector_fires_on_forged_source(self):
        for name in REMOVED_SYMBOLS:
            with self.subTest(name=name):
                for forged in (
                    "guard." + name + "('x')",
                    "mock.patch.object(guard, '" + name + "', return_value=True)",
                    "getattr(guard, '" + name + "')",
                    name + " = 1",
                ):
                    self.assertEqual(self.named_symbols(forged), {name})
        self.assertEqual(self.named_symbols("guard.is_below('x', 'y')"), set())

    def test_ac7_no_test_module_names_a_removed_symbol(self):
        offenders = {}
        for path in sorted(Path(__file__).resolve().parent.glob("test_*.py")):
            source = path.read_text(encoding="utf-8")
            if not any(symbol in source for symbol in REMOVED_SYMBOLS):
                continue
            found = self.named_symbols(source)
            if found:
                offenders[path.name] = sorted(found)
        self.assertEqual(offenders, {})


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
