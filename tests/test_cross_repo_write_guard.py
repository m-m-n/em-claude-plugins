"""Contract tests for `em-workflow/hooks/cross-repo-write-guard.py`.

Every run drives the hook as a subprocess with one PreToolUse payload as JSON
on standard input and asserts on standard output, in the same shape as
`tests/test_loop_command_guard.py`. `ask` cases guard the point of the hook:
a statically resolvable write whose destination lies outside the toplevel of
the payload `cwd`'s git repository must be sent to confirmation. `silent`
cases guard the cost: the hook must say nothing whenever the destination is
inside the toplevel, excluded, unresolvable or the input cannot be judged, so
a false `ask` (which becomes `deny` in unattended runs) never stops a run.

Isolation (NFR4): every hook run gets an explicitly built environment with
`HOME` set to a temporary directory (never the real `~/.claude`),
`CLAUDE_BATCH` removed unless the test sets it, and the inherited git
location variables removed. Fixture repositories live under a temporary root
below `/var/tmp`, outside `/tmp`: under `/tmp` every destination would be
excluded and no `ask` could ever be produced.

Bash judgment cases are the rows of the module-level table `CASES`,
`(expected, label, command)` with expected `ask` or `silent`, run with the
fixture repository as `cwd`. The label prefix (`AC5`, `AC6`, `AC7`) names the
acceptance criterion of cross-repo-write-guard task0001 the row belongs to.
Symbolic links, worktrees and the `repo` / `repo-other` boundary need real
fixtures and have dedicated tests.

Standard library only, per test/README.md.
"""

import ast
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "em-workflow" / "hooks" / "cross-repo-write-guard.py"

TAG = "[cross-repo-write-guard]"

# Fixtures must not live under /tmp (every destination there is excluded).
FIXTURE_BASE = "/var/tmp"

# Absolute destination outside every fixture directory, outside /tmp and
# outside the substituted HOME. Nothing is ever created there: the hook only
# reads the command text and resolves paths.
OUT = "/var/cwg-outside"

# The hook's own limit for the git lookup is shorter than its 15-second
# registration timeout; the whole run must stay below that timeout.
HOOK_TIMEOUT_SECONDS = 15.0


def _clean_git_env(home):
    """Environment for fixture-building git calls: no inherited git location
    variables, no global or system configuration, explicit author identity."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": home,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    return env


class Fixture:
    """Directory tree shared by every test of the module.

    ROOT/
      home/.claude/        substituted HOME
      probe/               process working directory of every hook run
      repo/                the fixture repository (toplevel)
        sub/
        link_out -> ../outside
        link_in  -> sub
        dangling -> ../outside/not-yet.txt
        .claude/worktrees/wt1/   linked worktree inside the main tree
      repo-other/          sibling sharing the toplevel's string prefix
      outside/
      nogit/               not inside any repository
      wt2/                 linked worktree outside the main tree
      cwdlink -> repo
      tmplink -> /tmp
      weird name.../       repository whose directory name has shell metacharacters
    """

    def build(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="cwg-", dir=FIXTURE_BASE))
        r = self.root
        self.home = os.path.join(r, "home")
        self.probe = os.path.join(r, "probe")
        self.repo = os.path.join(r, "repo")
        self.repo_other = os.path.join(r, "repo-other")
        self.outside = os.path.join(r, "outside")
        self.nogit = os.path.join(r, "nogit")
        self.wt_inner = os.path.join(self.repo, ".claude", "worktrees", "wt1")
        self.wt_outer = os.path.join(r, "wt2")
        self.cwdlink = os.path.join(r, "cwdlink")
        self.tmplink = os.path.join(r, "tmplink")
        self.weird = os.path.join(
            r, "weird $(touch pwned1) ;touch pwned2; `touch pwned3` 'q' \"d\""
        )
        for d in (
            os.path.join(self.home, ".claude"),
            self.probe,
            os.path.join(self.repo, "sub"),
            self.repo_other,
            self.outside,
            self.nogit,
            self.weird,
        ):
            os.makedirs(d)
        self._git_init(self.repo)
        self._git(self.repo, "worktree", "add", "-q", "-b", "wt1", self.wt_inner)
        self._git(self.repo, "worktree", "add", "-q", "-b", "wt2", self.wt_outer)
        self._git_init(self.weird)
        os.symlink(self.outside, os.path.join(self.repo, "link_out"))
        os.symlink("sub", os.path.join(self.repo, "link_in"))
        os.symlink(
            os.path.join(self.outside, "not-yet.txt"),
            os.path.join(self.repo, "dangling"),
        )
        os.symlink(self.repo, self.cwdlink)
        os.symlink("/tmp", self.tmplink)

    def destroy(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _git(self, cwd, *args):
        subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=_clean_git_env(self.home),
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def _git_init(self, path):
        self._git(path, "-c", "init.defaultBranch=main", "init", "-q")
        self._git(
            path,
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "fixture",
        )

    def listing(self, top):
        """Every path below `top` (relative), directories and files, sorted."""
        found = []
        for dirpath, dirnames, filenames in os.walk(top):
            for name in dirnames + filenames:
                found.append(os.path.relpath(os.path.join(dirpath, name), top))
        return sorted(found)


FIX = Fixture()


def setUpModule():
    if not os.path.isdir(FIXTURE_BASE):
        raise unittest.SkipTest(f"{FIXTURE_BASE} is not available for fixtures")
    FIX.build()


def tearDownModule():
    FIX.destroy()


class Result:
    def __init__(self, code, out, err):
        self.code = code
        self.out = out
        self.err = err
        self.decision = None
        self.reason = None
        if out:
            parsed = json.loads(out)
            body = parsed["hookSpecificOutput"]
            self.decision = body["permissionDecision"]
            self.reason = body["permissionDecisionReason"]
            self.body = body


def hook_env(batch=None, path_prefix=None):
    """The complete environment of one hook run, built explicitly: HOME is the
    substituted directory, CLAUDE_BATCH exists only when `batch` is given and
    no inherited git location variable survives."""
    path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    if path_prefix:
        path = path_prefix + os.pathsep + path
    env = {
        "PATH": path,
        "HOME": FIX.home,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": FIX.root,
    }
    if batch is not None:
        env["CLAUDE_BATCH"] = batch
    return env


def run_hook(payload, *, raw=None, batch=None, path_prefix=None):
    """Run the hook as a subprocess and return a Result.

    Universal checks on every run (AC-8, AC-10): exit code 0, empty stderr,
    stdout either empty or exactly one decision document whose reason begins
    with the tag, and never an `allow`."""
    data = raw if raw is not None else json.dumps(payload).encode("utf-8")
    if isinstance(data, str):
        data = data.encode("utf-8")
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=data,
        capture_output=True,
        env=hook_env(batch=batch, path_prefix=path_prefix),
        cwd=FIX.probe,
        timeout=HOOK_TIMEOUT_SECONDS * 2,
    )
    elapsed = time.monotonic() - started
    out = proc.stdout.decode("utf-8")
    err = proc.stderr.decode("utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"exit code {proc.returncode}; stderr={err!r}")
    if err != "":
        raise AssertionError(f"stderr is not empty: {err!r}")
    if elapsed >= HOOK_TIMEOUT_SECONDS:
        raise AssertionError(f"run took {elapsed:.1f}s, not under the 15s timeout")
    result = Result(proc.returncode, out, err)
    if out:
        if set(result.body) != {
            "hookEventName",
            "permissionDecision",
            "permissionDecisionReason",
        }:
            raise AssertionError(f"unexpected output keys: {sorted(result.body)}")
        if result.body["hookEventName"] != "PreToolUse":
            raise AssertionError(result.body["hookEventName"])
        if result.decision == "allow" or result.decision not in ("ask", "deny"):
            raise AssertionError(f"decision {result.decision!r} is not ask or deny")
        if not result.reason.startswith(TAG):
            raise AssertionError(f"reason does not begin with the tag: {result.reason!r}")
    return result


# Hook runs are independent processes over read-only fixtures, so the long
# tables run a few at a time; results are still judged one by one, in order.
PARALLEL_RUNS = max(2, min(8, os.cpu_count() or 2))


def run_hooks(payloads, **kwargs):
    """Run `run_hook` for every payload concurrently. Return one callable per
    payload, in order, that yields the Result (or raises what the run raised)
    when called -- so a failing run is reported where its row is judged."""
    pool = ThreadPoolExecutor(max_workers=PARALLEL_RUNS)
    try:
        futures = [pool.submit(run_hook, payload, **kwargs) for payload in payloads]
    finally:
        pool.shutdown(wait=True)
    return [future.result for future in futures]


def bash_payload(command, cwd=None):
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": FIX.repo if cwd is None else cwd,
    }


def file_payload(tool, path, cwd=None):
    if tool == "Write":
        tool_input = {"file_path": path, "content": "x"}
    elif tool == "Edit":
        tool_input = {"file_path": path, "old_string": "a", "new_string": "b"}
    else:
        tool_input = {
            "file_path": path,
            "edits": [{"old_string": "a", "new_string": "b"}],
        }
    return {
        "tool_name": tool,
        "tool_input": tool_input,
        "cwd": FIX.repo if cwd is None else cwd,
    }


# (expected, label, command) -- expected is "ask" or "silent". Commands are
# static strings run with the fixture repository as cwd: inside destinations
# are relative paths, outside destinations are absolute paths under OUT (or
# `~/...` / `../...`, which leave the repository too).
CASES = [
    # ------------------------------------------------------------------
    # AC-5 (FR5, FR7; TM-1, TM-2): the write forms, descriptor duplication,
    # other commands, and the /dev sinks.
    # ------------------------------------------------------------------
    ("ask", "AC5 > redirect", f"echo hi > {OUT}/a"),
    ("ask", "AC5 >> redirect", f"echo hi >> {OUT}/a"),
    ("ask", "AC5 >| redirect", f"echo hi >| {OUT}/a"),
    ("ask", "AC5 &> redirect", f"echo hi &> {OUT}/a"),
    ("ask", "AC5 &>> redirect", f"echo hi &>> {OUT}/a"),
    ("ask", "AC5 2> redirect", f"echo hi 2> {OUT}/a"),
    ("ask", "AC5 1>> redirect", f"echo hi 1>> {OUT}/a"),
    ("ask", "AC5 2>| redirect", f"echo hi 2>| {OUT}/a"),
    ("ask", "AC5 attached >word", f"echo hi >{OUT}/a"),
    ("ask", "AC5 attached 2>word", f"echo hi 2>{OUT}/a"),
    ("ask", "AC5 attached >>word", f"echo hi >>{OUT}/a"),
    ("ask", "AC5 redirect then 2>&1", f"echo hi > {OUT}/a 2>&1"),
    ("ask", "AC5 redirect before the command", f"> {OUT}/a echo hi"),
    ("ask", "AC5 redirect only", f"> {OUT}/a"),
    ("ask", "AC5 tee", f"echo hi | tee {OUT}/a"),
    ("ask", "AC5 tee -a", f"echo hi | tee -a {OUT}/a"),
    ("ask", "AC5 tee second operand", f"echo hi | tee a {OUT}/b"),
    ("ask", "AC5 tee after --", f"echo hi | tee -- {OUT}/a"),
    ("ask", "AC5 tee long option", f"echo hi | tee --append {OUT}/a"),
    ("ask", "AC5 sed -i", f"sed -i s/a/b/ {OUT}/f"),
    ("ask", "AC5 sed -i.bak -e", f"sed -i.bak -e s/a/b/ {OUT}/f"),
    ("ask", "AC5 sed --in-place", f"sed --in-place s/a/b/ {OUT}/f"),
    ("ask", "AC5 sed --in-place=SUFFIX", f"sed --in-place=.bak s/a/b/ {OUT}/f"),
    ("ask", "AC5 sed cluster -ni", f"sed -ni s/a/b/p {OUT}/f"),
    ("ask", "AC5 sed -E -i", f"sed -E -i s/a/b/ {OUT}/f"),
    ("ask", "AC5 sed -i -e with the file first", f"sed -i -e p {OUT}/f"),
    ("ask", "AC5 sed -i every file", f"sed -i s/a/b/ a {OUT}/f"),
    ("ask", "AC5 sed -i -f script file", f"sed -i -f script.sed {OUT}/f"),
    ("ask", "AC5 sed -i --expression", f"sed -i --expression=p {OUT}/f"),
    ("ask", "AC5 cp last operand", f"cp a {OUT}/b"),
    ("ask", "AC5 cp -r last operand", f"cp -r a {OUT}/"),
    ("ask", "AC5 cp several sources", f"cp a b {OUT}/dir/"),
    ("ask", "AC5 cp -t DIR", f"cp -t {OUT} a"),
    ("ask", "AC5 cp -tDIR", f"cp -t{OUT} a"),
    ("ask", "AC5 cp cluster -rt DIR", f"cp -rt {OUT} a"),
    ("ask", "AC5 cp --target-directory=DIR", f"cp --target-directory={OUT} a"),
    ("ask", "AC5 cp --target-directory DIR", f"cp --target-directory {OUT} a"),
    ("ask", "AC5 mv last operand", f"mv a {OUT}/b"),
    ("ask", "AC5 mv -t DIR", f"mv -t {OUT} a b"),
    ("ask", "AC5 other /dev path", "echo hi > /dev/zero"),
    ("ask", "AC5 other /dev path below a directory", "echo hi > /dev/shm/cwg-x"),
    ("silent", "AC5 > inside", "echo hi > a"),
    ("silent", "AC5 >> inside subdirectory", "echo hi >> sub/a"),
    ("silent", "AC5 &> inside", "echo hi &> a"),
    ("silent", "AC5 2> inside", "echo hi 2> a"),
    ("silent", "AC5 tee inside", "echo hi | tee a"),
    ("silent", "AC5 tee -a inside", "echo hi | tee -a sub/a"),
    ("silent", "AC5 sed -i inside", "sed -i s/a/b/ a"),
    ("silent", "AC5 sed -i.bak -e inside", "sed -i.bak -e s/a/b/ sub/a"),
    ("silent", "AC5 cp inside", "cp a b"),
    ("silent", "AC5 cp -t inside", "cp -t sub a"),
    ("silent", "AC5 mv inside", "mv a sub/b"),
    ("silent", "AC5 >&2", "echo hi >&2"),
    ("silent", "AC5 1>&2", "echo hi 1>&2"),
    ("silent", "AC5 2>&1", "echo hi 2>&1"),
    ("silent", "AC5 >&-", "echo hi >&-"),
    ("silent", "AC5 2>&-", "echo hi 2>&-"),
    ("silent", "AC5 inside redirect with 2>&1", "echo hi > a 2>&1"),
    ("silent", "AC5 mv outside source", f"mv {OUT}/a b"),
    ("silent", "AC5 mv outside source into a directory", f"mv {OUT}/a sub/"),
    ("silent", "AC5 cp outside source", f"cp {OUT}/a b"),
    ("silent", "AC5 cp single operand", f"cp {OUT}/a"),
    ("silent", "AC5 touch", f"touch {OUT}/a"),
    ("silent", "AC5 rm", f"rm {OUT}/a"),
    ("silent", "AC5 mkdir", f"mkdir {OUT}/d"),
    ("silent", "AC5 cat", f"cat {OUT}/a"),
    ("silent", "AC5 ln", f"ln -s a {OUT}/l"),
    ("silent", "AC5 rsync", f"rsync a {OUT}/"),
    ("silent", "AC5 dd of=", f"dd if=a of={OUT}/b"),
    ("silent", "AC5 install", f"install a {OUT}/"),
    ("silent", "AC5 sed without -i", f"sed s/a/b/ {OUT}/f"),
    ("silent", "AC5 sed -n without -i", f"sed -n p {OUT}/f"),
    ("silent", "AC5 sed -e without -i", f"sed -e s/a/b/ {OUT}/f"),
    ("silent", "AC5 sed -i without a file", "sed -i s/a/b/"),
    ("silent", "AC5 sed -i script is not a destination", f"sed -i {OUT}/script a"),
    ("silent", "AC5 tee -- option-like name inside", "echo hi | tee -- -x"),
    ("silent", "AC5 input redirect", f"cat < {OUT}/a"),
    ("silent", "AC5 input redirect with inside output", f"cat < {OUT}/a > b"),
    ("silent", "AC5 herestring", "cat <<< hi"),
    ("silent", "AC5 /dev/null", "echo hi > /dev/null"),
    ("silent", "AC5 2>/dev/null", "echo hi 2>/dev/null"),
    ("silent", "AC5 &>/dev/null", "echo hi &>/dev/null"),
    ("silent", "AC5 >/dev/null 2>&1", "echo hi >/dev/null 2>&1"),
    ("silent", "AC5 /dev/stdout", "echo hi > /dev/stdout"),
    ("silent", "AC5 /dev/stderr", "echo hi > /dev/stderr"),
    ("silent", "AC5 /dev/tty", "echo hi > /dev/tty"),
    ("silent", "AC5 /dev/fd/1", "echo hi > /dev/fd/1"),
    ("silent", "AC5 2>/dev/fd/2", "echo hi 2>/dev/fd/2"),
    ("silent", "AC5 /dev/fd/ normalized literally", "echo hi > /dev/fd/../fd/1"),
    ("silent", "AC5 tee /dev/null", "echo hi | tee /dev/null"),
    ("silent", "AC5 cp to /dev/null", "cp a /dev/null"),
    # ------------------------------------------------------------------
    # AC-6 (FR8; TM-1, TM-2): scopes that are judged and text that is not a
    # command.
    # ------------------------------------------------------------------
    ("ask", "AC6 subshell", f"(echo hi > {OUT}/a)"),
    ("ask", "AC6 subshell with spaces", f"( echo hi > {OUT}/a )"),
    ("ask", "AC6 brace group", f"{{ echo hi > {OUT}/a; }}"),
    ("ask", "AC6 brace group tee", f"{{ echo hi; tee {OUT}/a; }}"),
    ("ask", "AC6 nested groups", f"( {{ echo hi > {OUT}/a; }} )"),
    ("ask", "AC6 sudo", f"sudo tee {OUT}/a"),
    ("ask", "AC6 sudo -u USER", f"sudo -u root tee {OUT}/a"),
    ("ask", "AC6 sudo -n", f"sudo -n tee {OUT}/a"),
    ("ask", "AC6 sudo cp", f"sudo cp a {OUT}/b"),
    ("ask", "AC6 sudo sed -i", f"sudo sed -i s/a/b/ {OUT}/f"),
    ("ask", "AC6 env", f"env tee {OUT}/a"),
    ("ask", "AC6 env assignment", f"env FOO=1 tee {OUT}/a"),
    ("ask", "AC6 env -i", f"env -i tee {OUT}/a"),
    ("ask", "AC6 env -u NAME", f"env -u FOO tee {OUT}/a"),
    ("ask", "AC6 nohup", f"nohup tee {OUT}/a"),
    ("ask", "AC6 time", f"time tee {OUT}/a"),
    ("ask", "AC6 time -p", f"time -p cp a {OUT}/b"),
    ("ask", "AC6 command", f"command tee {OUT}/a"),
    ("ask", "AC6 nice", f"nice tee {OUT}/a"),
    ("ask", "AC6 nice -n N", f"nice -n 5 tee {OUT}/a"),
    ("ask", "AC6 nice -N", f"nice -10 tee {OUT}/a"),
    ("ask", "AC6 stacked wrappers", f"nohup sudo env nice cp a {OUT}/b"),
    ("ask", "AC6 leading assignment", f"FOO=1 tee {OUT}/a"),
    ("ask", "AC6 two leading assignments", f"FOO=1 BAR=2 cp a {OUT}/b"),
    ("ask", "AC6 assignment with substitution", f"FOO=$(date) tee {OUT}/a"),
    ("ask", "AC6 assignment then redirect", f"FOO=1 echo hi > {OUT}/a"),
    ("ask", "AC6 after &&", f"echo a && echo b > {OUT}/a"),
    ("ask", "AC6 after ||", f"false || tee {OUT}/a"),
    ("ask", "AC6 after ;", f"echo a; echo b > {OUT}/a"),
    ("ask", "AC6 after |", f"echo a | tee {OUT}/a"),
    ("ask", "AC6 after |&", f"echo a |& tee {OUT}/a"),
    ("ask", "AC6 after &", f"echo a & echo b > {OUT}/a"),
    ("ask", "AC6 after newline", f"echo a\necho b > {OUT}/a"),
    ("ask", "AC6 after backslash-newline continuation", f"echo a \\\n> {OUT}/a"),
    ("ask", "AC6 bash -c with an outside redirect", f"bash -c 'echo hi' > {OUT}/a"),
    ("ask", "AC6 bash -c with an outside appended redirect", f'bash -c "echo hi" >> {OUT}/a'),
    ("ask", "AC6 command substitution with an outside redirect", f"echo $(date) > {OUT}/a"),
    ("ask", "AC6 quoted substitution with an outside redirect", f'echo "$(date)" > {OUT}/a'),
    ("ask", "AC6 backquote with an outside redirect", f"echo `date` > {OUT}/a"),
    ("ask", "AC6 process substitution with an outside redirect", f"diff <(ls) <(ls) > {OUT}/a"),
    ("ask", "AC6 group redirect after brace group", f"{{ bash -c 'echo hi'; }} > {OUT}/a"),
    ("ask", "AC6 group redirect after subshell", f"( echo hi ) > {OUT}/a"),
    ("ask", "AC6 group redirect 2>", f"{{ echo hi; }} 2> {OUT}/a"),
    ("ask", "AC6 group redirect then pipe", f"( echo hi ) 2>&1 | tee {OUT}/a"),
    ("ask", "AC6 heredoc then redirect on the same line", f"cat > {OUT}/a <<EOF\nbody\nEOF"),
    ("ask", "AC6 redirect before heredoc operator", f"cat <<EOF > {OUT}/a\nbody\nEOF"),
    ("ask", "AC6 heredoc piped to tee", f"cat <<'EOF' | tee {OUT}/a\nbody\nEOF"),
    ("ask", "AC6 heredoc with tab stripping", f"cat <<-EOF > {OUT}/a\n\tbody\n\tEOF"),
    ("ask", "AC6 statement after a heredoc", f"cat <<EOF\nbody\nEOF\necho hi > {OUT}/a"),
    (
        "ask",
        "AC6 heredoc inside a substitution does not break the parse",
        f"git commit -m \"$(cat <<'EOF'\nfix: don't touch it (really\nEOF\n)\" && echo hi > {OUT}/a",
    ),
    (
        "silent",
        "AC6 heredoc body inside a substitution is not read",
        f"git commit -m \"$(cat <<'EOF'\necho hi > {OUT}/a\nEOF\n)\"",
    ),
    (
        "ask",
        "AC6 tab-stripped heredoc inside a substitution",
        f"echo $(cat <<-EOF\n\tbody (\n\tEOF\n) > {OUT}/a",
    ),
    ("ask", "AC6 hash inside a word is not a comment", f"echo a#b > {OUT}/a"),
    ("ask", "AC6 comment ends at the newline", f"# note\necho hi > {OUT}/a"),
    ("ask", "AC6 if body redirect", f"if true; then echo hi > {OUT}/a; fi"),
    ("silent", "AC6 bash -c string", f"bash -c 'echo hi > {OUT}/a'"),
    ("silent", "AC6 sh -c string with tee", f'sh -c "tee {OUT}/a"'),
    ("silent", "AC6 bash -lc string with cp", f"bash -lc 'cp a {OUT}/b'"),
    ("silent", "AC6 eval string", f'eval "echo hi > {OUT}/a"'),
    ("silent", "AC6 command substitution body", f"echo $(echo hi > {OUT}/a)"),
    ("silent", "AC6 quoted substitution body", f'echo "$(tee {OUT}/a)"'),
    ("silent", "AC6 backquote body", f"echo `echo hi > {OUT}/a`"),
    ("silent", "AC6 process substitution body", f"tee >(cat > {OUT}/a)"),
    ("silent", "AC6 input process substitution body", f"cat <(echo hi > {OUT}/a)"),
    ("silent", "AC6 assignment substitution body", f"x=$(echo > {OUT}/a)"),
    ("silent", "AC6 arithmetic body", f"echo $((1 + 2)) > a"),
    ("silent", "AC6 heredoc body", f"cat <<EOF\necho hi > {OUT}/a\nEOF"),
    ("silent", "AC6 quoted heredoc body", f"cat <<'EOF'\ntee {OUT}/a\nEOF"),
    ("silent", "AC6 tab-stripped heredoc body", f"cat <<-EOF\n\techo > {OUT}/a\n\tEOF"),
    ("silent", "AC6 heredoc body then inside statement", f"cat <<EOF\nbody > {OUT}/a\nEOF\necho ok > a"),
    ("silent", "AC6 two heredocs on one line", f"cat <<A <<B\n> {OUT}/a\nA\n> {OUT}/b\nB"),
    ("silent", "AC6 herestring text", f'cat <<< "echo > {OUT}/a"'),
    ("silent", "AC6 double-quoted text", f'echo "hi > {OUT}/a"'),
    ("silent", "AC6 single-quoted text", f"echo 'tee {OUT}/a'"),
    ("silent", "AC6 quoted operator", f"echo '>' {OUT}/a"),
    ("silent", "AC6 escaped operator", f"echo \\> {OUT}/a"),
    ("silent", "AC6 quoted fd redirect text", f'echo "2>{OUT}/a"'),
    ("silent", "AC6 trailing comment", f"echo hi # > {OUT}/a"),
    ("silent", "AC6 whole-line comment", f"# tee {OUT}/a"),
    ("silent", "AC6 comment after an inside write", f"echo hi > a # > {OUT}/a"),
    ("silent", "AC6 comment after cp", f"echo hi # cp a {OUT}/b"),
    # ------------------------------------------------------------------
    # AC-7 (FR4, FR9, FR10; TM-2): unresolvable destinations, tilde,
    # unparseable text, working-directory changes.
    # ------------------------------------------------------------------
    ("silent", "AC7 $VAR", f"echo hi > $OUT/x"),
    ("silent", "AC7 $HOME", "echo hi > $HOME/x"),
    ("silent", "AC7 ${HOME}", "echo hi > ${HOME}/x"),
    ("silent", "AC7 quoted $HOME", 'echo hi > "$HOME/x"'),
    ("silent", "AC7 ${var:-default}", f"echo hi > ${{x:-{OUT}/a}}"),
    ("silent", "AC7 positional parameter", "echo hi > $1"),
    ("silent", "AC7 command substitution path", "echo hi > $(pwd)/x"),
    ("silent", "AC7 quoted command substitution path", 'echo hi > "$(pwd)/x"'),
    ("silent", "AC7 backquote path", "echo hi > `pwd`/x"),
    ("silent", "AC7 star glob", f"echo hi > {OUT}/*"),
    ("silent", "AC7 question glob", f"echo hi > {OUT}/?"),
    ("silent", "AC7 bracket glob", f"echo hi > {OUT}/[ab]"),
    ("silent", "AC7 tee glob", f"echo hi | tee {OUT}/*.log"),
    ("silent", "AC7 ANSI-C quoting", f"echo hi > $'{OUT}/a'"),
    ("silent", "AC7 locale quoting", f'echo hi > $"{OUT}/a"'),
    ("silent", "AC7 cp variable destination", "cp a $DEST"),
    ("silent", "AC7 cp glob destination", f"cp a {OUT}/*"),
    ("silent", "AC7 variable then inside", "echo hi > $HOME/x > a"),
    ("silent", "AC7 process substitution destination", "echo hi > >(cat)"),
    ("ask", "AC7 other operand of the same tee still judged", f"echo hi | tee $X {OUT}/a"),
    ("ask", "AC7 glob next to a literal tee operand", f"echo hi | tee {OUT}/*.log {OUT}/b"),
    ("ask", "AC7 variable redirect next to a literal one", f"echo hi > $HOME/x 2> {OUT}/a"),
    ("ask", "AC7 cp variable source with a literal destination", f"cp $A $B {OUT}/dir"),
    ("ask", "AC7 quoted star is a literal name", f'echo hi > "{OUT}/*"'),
    ("ask", "AC7 escaped star is a literal name", f"echo hi > {OUT}/\\*"),
    ("ask", "AC7 quoted dollar is a literal name", f"echo hi > '{OUT}/$x'"),
    ("ask", "AC7 single-quoted outside path", f"echo hi > '{OUT}/a b'"),
    ("ask", "AC7 double-quoted outside path", f'echo hi > "{OUT}/a b"'),
    ("ask", "AC7 relative path leaving the repository", "echo hi > ../x"),
    ("ask", "AC7 relative path through sub/..", "echo hi > sub/../../x"),
    ("silent", "AC7 relative path staying inside", "echo hi > sub/../a"),
    ("silent", "AC7 unterminated double quote", f'echo hi > {OUT}/a "unterminated'),
    ("silent", "AC7 unterminated single quote", f"echo hi > {OUT}/a 'unterminated"),
    ("silent", "AC7 unterminated substitution", f"echo hi > {OUT}/a $(unterminated"),
    ("silent", "AC7 unterminated backquote", f"echo hi > {OUT}/a `unterminated"),
    ("silent", "AC7 unterminated braced expansion", f"echo hi > {OUT}/a ${{unterminated"),
    ("silent", "AC7 later unterminated quote voids the outside write", f'echo hi > {OUT}/a; echo "x'),
    ("silent", "AC7 heredoc without delimiter line", f"cat <<EOF > {OUT}/a\nbody"),
    ("silent", "AC7 heredoc without any body", f"cat > {OUT}/a <<EOF"),
    ("silent", "AC7 unterminated subshell", f"( echo hi > {OUT}/a"),
    ("silent", "AC7 unterminated brace group", f"{{ echo hi > {OUT}/a"),
    ("silent", "AC7 stray )", f"echo hi > {OUT}/a )"),
    ("silent", "AC7 stray }", f"echo hi > {OUT}/a; }}"),
    ("silent", "AC7 redirection without a target", "echo hi >"),
    ("ask", "AC7 unquoted ~/ expands to HOME", "echo hi > ~/x"),
    ("ask", "AC7 attached ~/", "echo hi >~/x"),
    ("ask", "AC7 ~ alone is HOME", "echo hi > ~"),
    ("ask", "AC7 tee ~/", "echo hi | tee ~/x"),
    ("ask", "AC7 cp to ~/", "cp a ~/x"),
    ("ask", "AC7 ~/ with .. leaving the .claude exclusion", "echo hi > ~/.claude/../x"),
    ("silent", "AC7 ~/.claude is excluded", "echo hi > ~/.claude/x"),
    ("silent", "AC7 ~/.claude after normalization", "echo hi > ~/x/../.claude/y"),
    ("silent", "AC7 single-quoted tilde is a relative name", "echo hi > '~/x'"),
    ("silent", "AC7 double-quoted tilde is a relative name", 'echo hi > "~/x"'),
    ("silent", "AC7 escaped tilde is a relative name", "echo hi > \\~/x"),
    ("silent", "AC7 tilde inside a word is a relative name", "echo hi > a~/x"),
    ("silent", "AC7 /tmp is excluded", "echo hi > /tmp/x"),
    ("silent", "AC7 /tmp itself is excluded", "echo hi > /tmp"),
    ("ask", "AC7 /tmp-other is not /tmp", "echo hi > /tmp-cwg-other/x"),
    ("silent", "AC7 cd then relative", "cd sub && echo hi > a"),
    ("silent", "AC7 cd then relative leaving the repository", "cd sub && echo hi > ../../x"),
    ("ask", "AC7 cd then absolute outside", f"cd sub && echo hi > {OUT}/a"),
    ("ask", "AC7 cd with ; then absolute outside", f"cd sub; echo hi > {OUT}/a"),
    ("silent", "AC7 cd with ; then relative", "cd sub; echo hi > ../../x"),
    ("silent", "AC7 cd with newline then relative", "cd sub\necho hi > ../../x"),
    ("silent", "AC7 cd with || then relative", "cd sub || echo hi > ../../x"),
    ("silent", "AC7 pushd then relative", "pushd sub >/dev/null && echo hi > ../../x"),
    ("silent", "AC7 popd then relative", "popd; echo hi > ../../x"),
    ("ask", "AC7 pushd then absolute", f"pushd sub >/dev/null && tee {OUT}/a"),
    ("silent", "AC7 cd then relative cp", "cd sub && cp a ../../x"),
    ("silent", "AC7 cd then nested relative", "cd sub; (echo hi > ../../x)"),
    ("silent", "AC7 cd then nested brace relative", "cd sub; { echo hi > ../../x; }"),
    ("ask", "AC7 relative before cd", "echo hi > ../x; cd sub"),
    ("ask", "AC7 cd word as an argument is not a cd", "echo cd sub; echo hi > ../x"),
    ("silent", "AC7 env -C", "env -C sub tee ../../x"),
    ("silent", "AC7 env --chdir=DIR", "env --chdir=sub tee ../../x"),
    ("silent", "AC7 env --chdir DIR", "env --chdir sub tee ../../x"),
    ("silent", "AC7 env -C redirect", "env -C sub echo hi > ../../x"),
    ("silent", "AC7 sudo -D", "sudo -D sub tee ../../x"),
    ("silent", "AC7 sudo --chdir=DIR", "sudo --chdir=sub tee ../../x"),
    ("silent", "AC7 sudo --chdir DIR", "sudo --chdir sub cp a ../../x"),
    ("ask", "AC7 env -C absolute", f"env -C sub tee {OUT}/a"),
    ("ask", "AC7 sudo --chdir absolute", f"sudo --chdir=sub tee {OUT}/a"),
    ("ask", "AC7 env -u is not a chdir", "env -u FOO tee ../../x"),
    ("ask", "AC7 env without -C", "env tee ../../x"),
    ("ask", "AC7 env -C only suppresses its own statement", "env -C sub true; echo hi > ../x"),
    ("ask", "AC7 subshell cd does not suppress after the subshell", "(cd sub && echo ok); echo hi > ../x"),
    ("ask", "AC7 subshell cd does not suppress later cp", "(cd sub); cp a ../x"),
    ("silent", "AC7 subshell cd suppresses inside the subshell", "(cd sub; echo hi > ../../x)"),
    ("silent", "AC7 brace group cd suppresses after the group", "{ cd sub; }; echo hi > ../x"),
    ("silent", "AC7 brace group cd suppresses with &&", "{ cd sub; echo ok; } && echo hi > ../x"),
    ("ask", "AC7 brace group cd then absolute", f"{{ cd sub; }}; tee {OUT}/a"),
    ("ask", "AC7 nested subshell cd stays confined", "{ (cd sub); echo hi > ../x; }"),
    ("silent", "AC7 cd inside a nested group suppresses that group", "( cd sub; { echo hi > ../../x; } )"),
]

ASK_ROW_PREFIXES = ("AC5 ", "AC6 ", "AC7 ")


def _run_cases(case, prefix):
    rows = [row for row in CASES if row[1].startswith(prefix)]
    case.assertTrue(rows, f"no rows for {prefix!r}")
    results = run_hooks([bash_payload(command) for _, _, command in rows])
    for (expected, label, command), get_result in zip(rows, results):
        with case.subTest(label=label, command=command):
            result = get_result()
            if expected == "ask":
                case.assertEqual(result.decision, "ask", result.out)
                case.assertIn(FIX.repo, result.reason)
            else:
                case.assertEqual(result.out, "")


class TestBashCases(unittest.TestCase):
    """AC-5, AC-6 and AC-7 through the module-level CASES table."""

    def test_every_row_is_well_formed(self):
        labels = [row[1] for row in CASES]
        self.assertEqual(len(labels), len(set(labels)), "labels must be unique")
        for row in CASES:
            with self.subTest(row=row[1]):
                self.assertEqual(len(row), 3)
                self.assertIn(row[0], ("ask", "silent"))
                self.assertIsInstance(row[2], str)
                self.assertTrue(row[1].startswith(ASK_ROW_PREFIXES), row[1])

    def test_cases_ac5_write_forms_and_dev_sinks(self):
        _run_cases(self, "AC5 ")

    def test_cases_ac6_scopes_and_non_command_text(self):
        _run_cases(self, "AC6 ")

    def test_cases_ac7_unresolvable_tilde_and_directory_changes(self):
        _run_cases(self, "AC7 ")


class TestFileWriteTools(unittest.TestCase):
    """AC-2 (FR2, FR4, FR5, FR6): Write, Edit and MultiEdit judge file_path."""

    TOOLS = ("Write", "Edit", "MultiEdit")

    def _paths(self):
        return {
            "ask": [
                OUT + "/x",
                FIX.outside + "/x",
                FIX.repo_other + "/x",
                FIX.home + "/x",
                "~/x",
                "~",
                "../x",
                FIX.home + "/.claude-other/x",
                "/tmp-cwg-other/x",
                FIX.root + "/x",
            ],
            "silent": [
                "a.txt",
                "sub/a.txt",
                "./sub/../a.txt",
                FIX.repo + "/a.txt",
                FIX.repo + "/sub/a.txt",
                FIX.repo,
                "/tmp/x",
                "/tmp",
                "/tmp/deep/er/x",
                FIX.home + "/.claude/x",
                FIX.home + "/.claude",
                "~/.claude/x",
                "~/.claude",
            ],
        }

    def _run(self, kind):
        pairs = [(tool, path) for tool in self.TOOLS for path in self._paths()[kind]]
        results = run_hooks([file_payload(tool, path) for tool, path in pairs])
        return [(tool, path, get) for (tool, path), get in zip(pairs, results)]

    def test_outside_file_path_asks(self):
        for tool, path, get_result in self._run("ask"):
            with self.subTest(tool=tool, path=path):
                result = get_result()
                self.assertEqual(result.decision, "ask", result.out)

    def test_inside_and_excluded_file_path_is_silent(self):
        for tool, path, get_result in self._run("silent"):
            with self.subTest(tool=tool, path=path):
                self.assertEqual(get_result().out, "")

    def test_relative_file_path_is_made_absolute_against_the_cwd(self):
        sub = os.path.join(FIX.repo, "sub")
        inside = run_hook(file_payload("Write", "a.txt", cwd=sub))
        self.assertEqual(inside.out, "")
        outside = run_hook(file_payload("Write", "../../x", cwd=sub))
        self.assertEqual(outside.decision, "ask")
        self.assertIn(os.path.join(FIX.root, "x"), outside.reason)

    def test_other_tool_names_are_not_judged(self):
        for tool in ("Read", "Grep", "NotebookEdit", "bash", "write", ""):
            with self.subTest(tool=tool):
                payload = file_payload("Write", OUT + "/x")
                payload["tool_name"] = tool
                self.assertEqual(run_hook(payload).out, "")


class TestInvalidInputFailsOpen(unittest.TestCase):
    """AC-3 (FR2, FR3, FR11): anything that cannot be judged is silent."""

    def _write(self):
        return file_payload("Write", OUT + "/x")

    def _bash(self):
        return bash_payload(f"echo hi > {OUT}/x")

    def test_baseline_payloads_do_ask(self):
        # Non-vacuity: the mutated payloads below differ from these only in
        # the mutated part, so their silence is caused by the mutation.
        self.assertEqual(run_hook(self._write()).decision, "ask")
        self.assertEqual(run_hook(self._bash()).decision, "ask")

    def test_stdin_that_is_not_a_json_object(self):
        raws = [
            b"",
            b"   ",
            b"not json",
            b"{",
            b'{"tool_name": "Write"',
            b"[]",
            b'["Write"]',
            b'"Write"',
            b"123",
            b"null",
            b"true",
            b"\xff\xfe\x00bad",
            json.dumps(self._write()).encode("utf-8") + b" trailing",
        ]
        for raw in raws:
            with self.subTest(raw=raw):
                self.assertEqual(run_hook(None, raw=raw).out, "")

    def test_tool_name_other_than_the_four(self):
        for name in ("Read", "Glob", "NotebookEdit", "Task", "write", "BASH", "", None, 7, ["Bash"]):
            with self.subTest(tool_name=name):
                payload = self._bash()
                payload["tool_name"] = name
                self.assertEqual(run_hook(payload).out, "")
        payload = self._bash()
        del payload["tool_name"]
        self.assertEqual(run_hook(payload).out, "")

    def test_tool_input_that_is_not_an_object(self):
        for value in ("echo hi", ["command"], 5, None, True):
            for base in (self._write(), self._bash()):
                with self.subTest(tool_input=value, tool=base["tool_name"]):
                    base["tool_input"] = value
                    self.assertEqual(run_hook(base).out, "")
        for base in (self._write(), self._bash()):
            del base["tool_input"]
            self.assertEqual(run_hook(base).out, "")

    def test_file_path_missing_non_string_or_empty(self):
        for value in (None, "", 5, ["/x"], {"p": "/x"}, True):
            with self.subTest(file_path=value):
                payload = self._write()
                payload["tool_input"]["file_path"] = value
                self.assertEqual(run_hook(payload).out, "")
        payload = self._write()
        del payload["tool_input"]["file_path"]
        self.assertEqual(run_hook(payload).out, "")

    def test_command_missing_non_string_or_empty(self):
        for value in (None, "", 5, ["echo"], {"c": "echo"}, True):
            with self.subTest(command=value):
                payload = self._bash()
                payload["tool_input"]["command"] = value
                self.assertEqual(run_hook(payload).out, "")
        payload = self._bash()
        del payload["tool_input"]["command"]
        self.assertEqual(run_hook(payload).out, "")

    def test_cwd_missing_non_string_or_empty(self):
        for value in (None, "", 5, ["/x"], {"p": "/x"}, True):
            for base in (self._write(), self._bash()):
                with self.subTest(cwd=value, tool=base["tool_name"]):
                    base["cwd"] = value
                    self.assertEqual(run_hook(base).out, "")
        for base in (self._write(), self._bash()):
            del base["cwd"]
            self.assertEqual(run_hook(base).out, "")

    def test_cwd_outside_every_git_repository(self):
        for base in (self._write(), self._bash()):
            with self.subTest(tool=base["tool_name"]):
                base["cwd"] = FIX.nogit
                self.assertEqual(run_hook(base).out, "")

    def test_cwd_that_does_not_exist_on_disk(self):
        for base in (self._write(), self._bash()):
            with self.subTest(tool=base["tool_name"]):
                base["cwd"] = os.path.join(FIX.root, "does-not-exist")
                self.assertEqual(run_hook(base).out, "")

    def test_cwd_that_is_a_file(self):
        marker = os.path.join(FIX.repo, "a-file")
        with open(marker, "w") as handle:
            handle.write("x")
        try:
            for base in (self._write(), self._bash()):
                with self.subTest(tool=base["tool_name"]):
                    base["cwd"] = marker
                    self.assertEqual(run_hook(base).out, "")
        finally:
            os.unlink(marker)

    def test_nul_byte_in_the_destination_is_silent(self):
        payload = file_payload("Write", OUT + "/x\x00y")
        self.assertEqual(run_hook(payload).out, "")


class TestPathResolution(unittest.TestCase):
    """AC-4 (FR3, FR4; TM-3): the toplevel is the only comparison base and
    destinations are compared after real-path resolution at path-component
    boundaries."""

    def test_linked_worktree_inside_the_main_tree_writing_into_the_main_tree(self):
        for tool_payload in (
            file_payload("Write", os.path.join(FIX.repo, "x"), cwd=FIX.wt_inner),
            bash_payload(f"echo hi > {FIX.repo}/x", cwd=FIX.wt_inner),
            bash_payload("echo hi > ../../../x", cwd=FIX.wt_inner),
        ):
            with self.subTest(payload=tool_payload["tool_input"]):
                result = run_hook(tool_payload)
                self.assertEqual(result.decision, "ask", result.out)
                self.assertIn(FIX.wt_inner, result.reason)

    def test_linked_worktree_outside_the_main_tree_writing_into_the_main_tree(self):
        for tool_payload in (
            file_payload("Edit", os.path.join(FIX.repo, "x"), cwd=FIX.wt_outer),
            bash_payload(f"cp a {FIX.repo}/b", cwd=FIX.wt_outer),
        ):
            with self.subTest(payload=tool_payload["tool_input"]):
                result = run_hook(tool_payload)
                self.assertEqual(result.decision, "ask", result.out)
                self.assertIn(FIX.wt_outer, result.reason)

    def test_linked_worktree_writing_into_itself_is_silent(self):
        for cwd in (FIX.wt_inner, FIX.wt_outer):
            for tool_payload in (
                file_payload("Write", os.path.join(cwd, "x"), cwd=cwd),
                file_payload("Write", "sub/x", cwd=cwd),
                bash_payload("echo hi > x", cwd=cwd),
                bash_payload(f"echo hi > {cwd}/x", cwd=cwd),
            ):
                with self.subTest(cwd=cwd, payload=tool_payload["tool_input"]):
                    self.assertEqual(run_hook(tool_payload).out, "")

    def test_main_tree_writing_into_a_nested_worktree_is_inside(self):
        result = run_hook(file_payload("Write", os.path.join(FIX.wt_inner, "x")))
        self.assertEqual(result.out, "")

    def test_not_yet_existing_file_through_a_symlink_pointing_outside(self):
        target = os.path.join(FIX.outside, "new.txt")
        self.assertFalse(os.path.exists(target))
        for tool_payload in (
            file_payload("Write", os.path.join(FIX.repo, "link_out", "new.txt")),
            file_payload("Write", "link_out/new.txt"),
            bash_payload("echo hi > link_out/new.txt"),
            bash_payload("echo hi | tee link_out/new.txt"),
            bash_payload("cp a link_out/new.txt"),
        ):
            with self.subTest(payload=tool_payload["tool_input"]):
                result = run_hook(tool_payload)
                self.assertEqual(result.decision, "ask", result.out)
                self.assertIn(target, result.reason)
        self.assertFalse(os.path.exists(target))

    def test_not_yet_existing_nested_path_through_a_symlink_pointing_outside(self):
        target = os.path.join(FIX.outside, "no", "such", "dir", "new.txt")
        result = run_hook(file_payload("Write", "link_out/no/such/dir/new.txt"))
        self.assertEqual(result.decision, "ask", result.out)
        self.assertIn(target, result.reason)

    def test_dangling_symlink_pointing_outside(self):
        result = run_hook(bash_payload("echo hi > dangling"))
        self.assertEqual(result.decision, "ask", result.out)
        self.assertIn(os.path.join(FIX.outside, "not-yet.txt"), result.reason)

    def test_symlink_as_the_final_component_is_followed(self):
        result = run_hook(bash_payload("echo hi > link_out"))
        self.assertEqual(result.decision, "ask", result.out)
        self.assertIn(FIX.outside, result.reason)
        self.assertEqual(run_hook(bash_payload("echo hi > link_in")).out, "")

    def test_many_distinct_destinations_are_judged_well_within_the_time_limit(self):
        # run_hook fails any run that takes the 15-second hook timeout or
        # longer, so a destination list handled in quadratic time is caught.
        operands = " ".join(f"sub/f{i}" for i in range(20000))
        result = run_hook(bash_payload(f"tee {operands} {OUT}/zz"))
        self.assertEqual(result.decision, "ask", result.out[:200])
        self.assertEqual(result.reason.count("\n  - "), 1)

    def test_symlink_pointing_inside_is_silent(self):
        for tool_payload in (
            file_payload("Write", "link_in/new.txt"),
            bash_payload("echo hi > link_in/new.txt"),
        ):
            with self.subTest(payload=tool_payload["tool_input"]):
                self.assertEqual(run_hook(tool_payload).out, "")

    def test_symlink_to_the_excluded_tmp_root_is_resolved_before_excluding(self):
        result = run_hook(file_payload("Write", os.path.join(FIX.tmplink, "x")))
        self.assertEqual(result.out, "")

    def test_destination_under_a_sibling_sharing_the_toplevel_prefix(self):
        self.assertTrue(FIX.repo_other.startswith(FIX.repo))
        for tool_payload in (
            file_payload("Write", os.path.join(FIX.repo_other, "x")),
            bash_payload(f"echo hi > {FIX.repo_other}/x"),
            bash_payload("echo hi > ../repo-other/x"),
            bash_payload(f"echo hi > {FIX.repo}-other"),
        ):
            with self.subTest(payload=tool_payload["tool_input"]):
                result = run_hook(tool_payload)
                self.assertEqual(result.decision, "ask", result.out)

    def test_destination_under_the_toplevel_is_silent(self):
        for tool_payload in (
            file_payload("Write", os.path.join(FIX.repo, "x")),
            file_payload("Write", os.path.join(FIX.repo, "sub", "deep", "x")),
            bash_payload(f"echo hi > {FIX.repo}/x"),
            bash_payload(f"echo hi > {FIX.repo}/sub/../x"),
            bash_payload(f"echo hi > {FIX.repo}"),
            bash_payload(f"echo hi > {FIX.repo}/"),
            bash_payload("echo hi > ../repo/x"),
        ):
            with self.subTest(payload=tool_payload["tool_input"]):
                self.assertEqual(run_hook(tool_payload).out, "")

    def test_cwd_in_a_subdirectory_compares_against_the_toplevel(self):
        sub = os.path.join(FIX.repo, "sub")
        self.assertEqual(run_hook(bash_payload("echo hi > ../a", cwd=sub)).out, "")
        self.assertEqual(
            run_hook(bash_payload(f"echo hi > {FIX.repo}/a", cwd=sub)).out, ""
        )
        result = run_hook(bash_payload("echo hi > ../../a", cwd=sub))
        self.assertEqual(result.decision, "ask", result.out)

    def test_cwd_reached_through_a_symlink(self):
        self.assertEqual(
            run_hook(bash_payload("echo hi > x", cwd=FIX.cwdlink)).out, ""
        )
        result = run_hook(bash_payload("echo hi > ../x", cwd=FIX.cwdlink))
        self.assertEqual(result.decision, "ask", result.out)

    def test_excluded_root_boundary_is_a_path_component_boundary(self):
        result = run_hook(file_payload("Write", FIX.home + "/.claudeX/x"))
        self.assertEqual(result.decision, "ask", result.out)


class TestDecisionOutput(unittest.TestCase):
    """AC-8 (FR6; TM-6, TM-7): one decision, tag prefix, paths in the
    reason, the CLAUDE_BATCH downgrade, never an allow."""

    def _multi(self):
        return bash_payload(
            f"echo hi > {OUT}/one 2> {FIX.outside}/two && tee {OUT}/one a"
        )

    def test_reason_names_every_outside_destination_once_and_the_toplevel(self):
        result = run_hook(self._multi())
        self.assertEqual(result.decision, "ask")
        self.assertTrue(result.reason.startswith(TAG))
        self.assertEqual(result.reason.count(os.path.realpath(OUT) + "/one"), 1)
        self.assertEqual(result.reason.count(FIX.outside + "/two"), 1)
        self.assertIn(FIX.repo, result.reason)
        self.assertNotIn(os.path.join(FIX.repo, "a"), result.reason)

    def test_exactly_one_decision_document(self):
        result = run_hook(self._multi())
        decoder = json.JSONDecoder()
        document, end = decoder.raw_decode(result.out)
        self.assertEqual(result.out[end:].strip(), "")
        self.assertEqual(list(document), ["hookSpecificOutput"])

    def test_reason_for_a_write_tool_names_the_resolved_path(self):
        result = run_hook(file_payload("Write", "link_out/new.txt"))
        self.assertIn(os.path.join(FIX.outside, "new.txt"), result.reason)
        self.assertIn(FIX.repo, result.reason)

    def test_batch_values_other_than_empty_0_false_no_deny(self):
        for value in ("1", "true", "yes", "on", "claude-batch", "2", "x"):
            with self.subTest(CLAUDE_BATCH=value):
                result = run_hook(self._multi(), batch=value)
                self.assertEqual(result.decision, "deny", result.out)
                self.assertTrue(result.reason.startswith(TAG))
                self.assertIn(FIX.repo, result.reason)
                self.assertIn(FIX.outside + "/two", result.reason)

    def test_downgrade_notice_is_in_the_deny_reason_only(self):
        denied = run_hook(self._multi(), batch="1")
        asked = run_hook(self._multi())
        self.assertIn("claude-batch", denied.reason)
        self.assertIn("降格", denied.reason)
        self.assertNotIn("claude-batch", asked.reason)
        self.assertNotIn("降格", asked.reason)

    def test_batch_unset_empty_0_false_no_ask(self):
        self.assertEqual(run_hook(self._multi()).decision, "ask")
        for value in ("", "0", "false", "no"):
            with self.subTest(CLAUDE_BATCH=value):
                self.assertEqual(run_hook(self._multi(), batch=value).decision, "ask")

    def test_batch_downgrade_applies_to_the_write_tools_too(self):
        for tool in ("Write", "Edit", "MultiEdit"):
            with self.subTest(tool=tool):
                result = run_hook(file_payload(tool, OUT + "/x"), batch="1")
                self.assertEqual(result.decision, "deny")

    def test_batch_does_not_make_silent_cases_loud(self):
        for payload in (
            bash_payload("echo hi > a"),
            bash_payload("echo hi > /dev/null"),
            file_payload("Write", "/tmp/x"),
        ):
            with self.subTest(payload=payload["tool_input"]):
                self.assertEqual(run_hook(payload, batch="1").out, "")

    def test_every_ask_row_of_the_write_forms_is_a_deny_under_batch(self):
        # run_hook raises on any `allow` in any run of this module, so the
        # absence of an allow is checked by every other test as well.
        rows = [
            (label, command)
            for expected, label, command in CASES
            if label.startswith("AC5 ") and expected == "ask"
        ]
        results = run_hooks([bash_payload(command) for _, command in rows], batch="1")
        for (label, _), get_result in zip(rows, results):
            with self.subTest(label=label):
                self.assertEqual(get_result().decision, "deny")


def _write_stub(directory, body):
    path = os.path.join(directory, "git")
    with open(path, "w") as handle:
        handle.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class TestGitInvocation(unittest.TestCase):
    """AC-9 (NFR2, NFR3; TM-4, TM-5): git is started at most once, only when
    a destination remains, as an argument vector, under a time limit."""

    @classmethod
    def setUpClass(cls):
        cls.stub_dir = tempfile.mkdtemp(prefix="stub-", dir=FIXTURE_BASE)
        cls.log = os.path.join(cls.stub_dir, "calls.log")
        _write_stub(
            cls.stub_dir,
            "#!/bin/sh\n"
            'dir=$(dirname "$0")\n'
            'printf \'%s|%s\\n\' "$(pwd -P)" "$*" >> "$dir/calls.log"\n'
            'cat "$dir/toplevel"\n',
        )
        with open(os.path.join(cls.stub_dir, "toplevel"), "w") as handle:
            handle.write(FIX.repo + "\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.stub_dir, ignore_errors=True)

    def setUp(self):
        if os.path.exists(self.log):
            os.unlink(self.log)

    def _calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as handle:
            return handle.read().splitlines()

    def _run(self, payload, **kwargs):
        return run_hook(payload, path_prefix=self.stub_dir, **kwargs)

    def test_git_is_never_started_when_every_destination_is_excluded(self):
        payloads = [
            file_payload("Write", "/tmp/x"),
            file_payload("Write", "~/.claude/x"),
            bash_payload("echo hi > /dev/null"),
            bash_payload("echo hi 2>&1 >/dev/stderr"),
            bash_payload("echo hi > /tmp/a | tee /tmp/b"),
            bash_payload("echo hi > ~/.claude/x"),
        ]
        for payload in payloads:
            with self.subTest(payload=payload["tool_input"]):
                self.assertEqual(self._run(payload).out, "")
                self.assertEqual(self._calls(), [])

    def test_git_is_never_started_when_every_destination_is_unresolvable(self):
        payloads = [
            bash_payload("echo hi > $HOME/x"),
            bash_payload('echo hi > "$(pwd)/x"'),
            bash_payload(f"echo hi > {OUT}/*"),
            bash_payload("echo hi | tee $A $B"),
            bash_payload(f"bash -c 'echo hi > {OUT}/a'"),
            bash_payload("cd sub && echo hi > ../../x"),
            bash_payload(f'echo hi > {OUT}/a "unterminated'),
            bash_payload("echo hi"),
            bash_payload("touch a b c"),
        ]
        for payload in payloads:
            with self.subTest(payload=payload["tool_input"]):
                self.assertEqual(self._run(payload).out, "")
                self.assertEqual(self._calls(), [])

    def test_git_is_never_started_for_invalid_input(self):
        for raw in (b"", b"not json", b"[]"):
            self.assertEqual(run_hook(None, raw=raw, path_prefix=self.stub_dir).out, "")
        payload = bash_payload(f"echo hi > {OUT}/x")
        payload["tool_name"] = "Read"
        self.assertEqual(self._run(payload).out, "")
        self.assertEqual(self._calls(), [])

    def test_git_is_started_exactly_once_for_one_destination(self):
        for payload in (
            bash_payload(f"echo hi > {OUT}/x"),
            file_payload("Write", OUT + "/x"),
            bash_payload("echo hi > a"),
        ):
            with self.subTest(payload=payload["tool_input"]):
                self.setUp()
                self._run(payload)
                self.assertEqual(len(self._calls()), 1, self._calls())

    def test_git_is_started_exactly_once_for_several_destinations(self):
        payload = bash_payload(
            f"echo hi > {OUT}/a 2> {OUT}/b; tee {OUT}/c a sub/b; cp x {OUT}/d"
        )
        result = self._run(payload)
        self.assertEqual(result.decision, "ask")
        self.assertEqual(len(self._calls()), 1, self._calls())

    def test_git_is_asked_for_the_toplevel_in_the_payload_cwd(self):
        self._run(bash_payload(f"echo hi > {OUT}/x", cwd=FIX.cwdlink))
        calls = self._calls()
        self.assertEqual(len(calls), 1)
        directory, _, arguments = calls[0].partition("|")
        self.assertEqual(directory, FIX.repo)
        self.assertEqual(arguments, "rev-parse --show-toplevel")

    def test_decision_is_made_from_the_stubbed_toplevel(self):
        other = os.path.join(FIX.root, "outside")
        with open(os.path.join(self.stub_dir, "toplevel"), "w") as handle:
            handle.write(other + "\n")
        try:
            inside = self._run(bash_payload(f"echo hi > {other}/x"))
            self.assertEqual(inside.out, "")
            outside = self._run(bash_payload(f"echo hi > {FIX.repo}/x"))
            self.assertEqual(outside.decision, "ask")
            self.assertIn(other, outside.reason)
        finally:
            with open(os.path.join(self.stub_dir, "toplevel"), "w") as handle:
                handle.write(FIX.repo + "\n")

    def test_empty_or_failing_git_output_is_silent(self):
        scratch = tempfile.mkdtemp(prefix="stub-", dir=FIXTURE_BASE)
        try:
            for body in (
                "#!/bin/sh\nexit 0\n",
                "#!/bin/sh\necho fatal >&2\nexit 128\n",
                "#!/bin/sh\necho /somewhere\nexit 1\n",
            ):
                with self.subTest(body=body):
                    _write_stub(scratch, body)
                    result = run_hook(
                        bash_payload(f"echo hi > {OUT}/x"), path_prefix=scratch
                    )
                    self.assertEqual(result.out, "")
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_missing_git_is_silent(self):
        empty = tempfile.mkdtemp(prefix="nogit-path-", dir=FIXTURE_BASE)
        try:
            env = hook_env()
            env["PATH"] = empty
            proc = subprocess.run(
                [sys.executable, str(HOOK_PATH)],
                input=json.dumps(bash_payload(f"echo hi > {OUT}/x")).encode(),
                capture_output=True,
                env=env,
                cwd=FIX.probe,
                timeout=HOOK_TIMEOUT_SECONDS,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, b"")
            self.assertEqual(proc.stderr, b"")
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def test_git_that_does_not_answer_in_time_leads_to_no_output(self):
        scratch = tempfile.mkdtemp(prefix="stub-", dir=FIXTURE_BASE)
        try:
            # The stub replaces itself with the waiting program, so killing
            # the process it started on expiry leaves nothing behind.
            _write_stub(scratch, "#!/bin/sh\nexec sleep 120\n")
            started = time.monotonic()
            result = run_hook(
                bash_payload(f"echo hi > {OUT}/x"), path_prefix=scratch
            )
            elapsed = time.monotonic() - started
            self.assertEqual(result.out, "")
            self.assertLess(elapsed, HOOK_TIMEOUT_SECONDS)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_cwd_with_shell_metacharacters_is_decided_correctly_and_runs_nothing(self):
        before = {
            "probe": FIX.listing(FIX.probe),
            "root": FIX.listing(FIX.root),
            "weird": FIX.listing(FIX.weird),
        }
        for payload in (
            bash_payload(f"echo hi > {OUT}/x", cwd=FIX.weird),
            file_payload("Write", OUT + "/x", cwd=FIX.weird),
        ):
            with self.subTest(payload=payload["tool_input"]):
                result = run_hook(payload)
                self.assertEqual(result.decision, "ask", result.out)
                self.assertIn(FIX.weird, result.reason)
        inside = run_hook(bash_payload("echo hi > x", cwd=FIX.weird))
        self.assertEqual(inside.out, "")
        after = {
            "probe": FIX.listing(FIX.probe),
            "root": FIX.listing(FIX.root),
            "weird": FIX.listing(FIX.weird),
        }
        self.assertEqual(before, after)
        for name in ("pwned1", "pwned2", "pwned3"):
            for directory in (FIX.probe, FIX.root, FIX.weird, FIX.repo):
                self.assertFalse(os.path.exists(os.path.join(directory, name)))

    def test_hook_runs_leave_the_fixture_repository_and_home_untouched(self):
        before = (FIX.listing(FIX.repo), FIX.listing(FIX.home), FIX.listing(FIX.outside))
        payloads = [
            bash_payload(f"echo hi > {OUT}/x"),
            bash_payload("echo hi > a; tee b; cp a sub/c; sed -i s/a/b/ d"),
            bash_payload("echo hi > ~/x"),
            file_payload("Write", "link_out/new.txt"),
            file_payload("Edit", "~/.claude/settings.json"),
            file_payload("MultiEdit", "sub/a.txt"),
        ]
        for payload in payloads:
            run_hook(payload)
            run_hook(payload, batch="1")
        after = (FIX.listing(FIX.repo), FIX.listing(FIX.home), FIX.listing(FIX.outside))
        self.assertEqual(before, after)


class TestHookSourceAndIsolation(unittest.TestCase):
    """AC-10 (FR12, NFR1, NFR4): standard library only, run as a subprocess,
    isolated HOME and fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.source = HOOK_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _imported_modules(self):
        names = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names.extend((alias.name, 0) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append((node.module or "", node.level))
        return names

    def test_every_imported_module_belongs_to_the_standard_library(self):
        imported = self._imported_modules()
        self.assertTrue(imported)
        for name, level in imported:
            with self.subTest(module=name):
                self.assertEqual(level, 0, "relative import")
                self.assertIn(name.split(".")[0], sys.stdlib_module_names)

    def test_hook_does_not_import_dynamically(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, ("__import__", "importlib"))

    def test_hook_does_not_start_a_shell(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.keyword) and node.arg == "shell":
                self.assertIsInstance(node.value, ast.Constant)
                self.assertFalse(node.value.value)
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, ("system", "popen", "getoutput", "getstatusoutput"))

    def test_hook_script_exists_next_to_hooks_json(self):
        self.assertTrue(HOOK_PATH.is_file())
        self.assertTrue((HOOK_PATH.parent / "hooks.json").is_file())

    def test_hook_runs_with_the_current_interpreter_as_a_subprocess(self):
        result = run_hook(bash_payload(f"echo hi > {OUT}/x"))
        self.assertEqual(result.decision, "ask")

    def test_every_hook_run_environment_is_isolated(self):
        env = hook_env()
        self.assertEqual(env["HOME"], FIX.home)
        self.assertNotIn("CLAUDE_BATCH", env)
        self.assertFalse([k for k in env if k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")])
        self.assertEqual(hook_env(batch="1")["CLAUDE_BATCH"], "1")

    def test_fixture_root_and_home_are_outside_tmp(self):
        tmp = os.path.realpath("/tmp")
        for path in (FIX.root, FIX.home, FIX.repo):
            with self.subTest(path=path):
                self.assertNotEqual(path, tmp)
                self.assertFalse(path.startswith(tmp + "/"))
        self.assertFalse(FIX.home.startswith(FIX.repo + "/"))
        real_claude = os.path.realpath(os.path.expanduser("~/.claude"))
        self.assertFalse((FIX.home + "/").startswith(real_claude + "/"))

    def test_the_real_home_is_never_judged(self):
        # The substituted HOME decides what `~` and `~/.claude` mean: a path
        # under the real home is outside, a path under the substituted
        # `.claude` is excluded.
        real_claude = os.path.realpath(os.path.expanduser("~/.claude"))
        if real_claude != os.path.realpath(os.path.join(FIX.home, ".claude")):
            result = run_hook(file_payload("Write", real_claude + "/x"))
            self.assertEqual(result.decision, "ask", result.out)
        self.assertEqual(
            run_hook(file_payload("Write", FIX.home + "/.claude/x")).out, ""
        )


if __name__ == "__main__":
    unittest.main()
