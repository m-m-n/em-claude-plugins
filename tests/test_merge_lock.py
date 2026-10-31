"""Tests for task0005 (feature-docs/unattended-merge): the repository-wide
merge lock script `em-workflow/scripts/merge-lock.py` (subcommands token,
hold, verify; IMPLEMENTATION.md C1, C2, C7 and decision D3).

Every behavioural test runs the script with the test interpreter as a child
process against a throwaway git repository (plus a linked worktree) built in a
temporary directory. A holder is a long-running `hold` child that the test
starts and ends through its own process API (`terminate()` / `kill()`); no
shell kill is involved. Every wait is bounded, so a failing case becomes a
failure instead of a stuck suite. Nothing here touches the network or the real
home directory.

Covers task0005 Acceptance Criteria
(feature-docs/unattended-merge/tasks/task0005.md):

- AC-1: `token` prints a 32-lowercase-hex token; two calls differ.
- AC-2 (FR10): `hold`, started from a linked worktree, locks
  `em-workflow-feature-merge.lock` in the common git directory and writes a
  holder record (feature, token, process id, offset-qualified time); it never
  creates or locks `em-workflow-merge.lock`.
- AC-3 (FR10, TS8, TM-16): while a holder for feature `a` lives, `hold` for
  `b` stops `lock_busy` at once with `holder_feature` `a` and leaves the
  record alone; `verify` with `b`'s token stops `lock_busy`.
- AC-4 (TS23, TM-17): `verify` with the live holder's token is `held`; after
  the holder ends it is `lock_lost`; a record left by a dead process is
  `lock_lost` for any token and a new `hold` then succeeds.
- AC-5 (TS23, TM-17): a second run of the same feature, with its own token,
  gets `lock_busy` from `hold`, and `verify` with the second token is
  `lock_busy`, never `held`.
- AC-6 (TS20): `verify --wait` returns `held` once a later-starting holder
  carries the token and `lock_lost` within the wait bound when none does; a
  holder stays idle; the script runs no git command other than locating the
  common git directory and no push, PR or worktree operation.
"""

import fcntl
import json
import os
import re
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "merge-lock.py"

# Upper bound for one short child process and for one wait on a holder.
CALL_TIMEOUT_SECONDS = 20

LOCK_NAME = "em-workflow-feature-merge.lock"
RECORD_NAME = "em-workflow-feature-merge.holder"
MERGE_TASK_LOCK_NAME = "em-workflow-merge.lock"

TOKEN_FORMAT = re.compile(r"\A[0-9a-f]{32}\Z")

HAS_PROCFS = os.path.exists("/proc/self/stat")

# Git variables that would redirect the throwaway repositories.
GIT_REDIRECT_VARIABLES = (
    "GIT_DIR",
    "GIT_COMMON_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
)

TOKEN_A = "a" * 32
TOKEN_B = "b" * 32
TOKEN_C = "c" * 32


def base_env(home, **overrides):
    """An environment that isolates git from the real user configuration."""
    env = {k: v for k, v in os.environ.items() if k not in GIT_REDIRECT_VARIABLES}
    env.update(
        HOME=str(home),
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.invalid",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.invalid",
    )
    env.update(overrides)
    return env


def git(args, cwd, env):
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        timeout=CALL_TIMEOUT_SECONDS,
    )


def read_line(proc, timeout=CALL_TIMEOUT_SECONDS):
    """One stdout line of a child started with bufsize=0, or a failure."""
    deadline = time.monotonic() + timeout
    buf = b""
    fd = proc.stdout.fileno()
    while b"\n" not in buf:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"no complete stdout line within {timeout}s: {buf!r}")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            raise AssertionError(f"child closed stdout early: {buf!r}")
        buf += chunk
    return buf.split(b"\n", 1)[0].decode("utf-8")


def proc_cpu_ticks(pid):
    """utime + stime of a process, in clock ticks, from /proc/<pid>/stat."""
    raw = Path(f"/proc/{pid}/stat").read_bytes()
    fields = raw[raw.rindex(b")") + 2 :].split()
    return int(fields[11]) + int(fields[12])


def proc_start_time(pid):
    raw = Path(f"/proc/{pid}/stat").read_bytes()
    fields = raw[raw.rindex(b")") + 2 :].split()
    return int(fields[19])


class MergeLockCase(unittest.TestCase):
    """A temporary repository with a linked worktree, and script runners."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = base_env(self.home)
        self.main = self.tmp / "repo"
        self.main.mkdir()
        git(["init", "-q", "-b", "main"], self.main, self.env)
        git(["commit", "-q", "--allow-empty", "-m", "initial"], self.main, self.env)
        self.linked = self.tmp / "linked"
        git(["worktree", "add", "-q", "-b", "linked", str(self.linked)], self.main, self.env)
        self.common = (self.main / ".git").resolve()
        self.lock_path = self.common / LOCK_NAME
        self.record_path = self.common / RECORD_NAME

    # -- runners -----------------------------------------------------------

    def run_script(self, *argv, cwd=None, env=None):
        try:
            return subprocess.run(
                [sys.executable, "-B", str(SCRIPT), *argv],
                cwd=cwd if cwd is not None else self.tmp,
                env=env if env is not None else self.env,
                capture_output=True,
                timeout=CALL_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise AssertionError(
                f"child did not return within {CALL_TIMEOUT_SECONDS}s: {argv!r}"
            ) from None

    def result(self, proc):
        """Decode the one JSON object the contract promises on stdout."""
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        text = proc.stdout.decode("utf-8")
        self.assertEqual(text.count("\n"), 1, repr(text))
        self.assertTrue(text.endswith("\n"), repr(text))
        value = json.loads(text)
        self.assertIsInstance(value, dict)
        for key in ("outcome", "reason", "detail"):
            self.assertIn(key, value)
        return value

    def start_holder(self, feature, token, project_root=None, cwd=None, env=None):
        """Start `hold` as a child; return (popen, first-line result)."""
        errlog = tempfile.TemporaryFile()
        self.addCleanup(errlog.close)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "hold",
                "--project-root",
                str(project_root if project_root is not None else self.main),
                "--feature",
                feature,
                "--token",
                token,
            ],
            cwd=cwd if cwd is not None else self.tmp,
            env=env if env is not None else self.env,
            stdout=subprocess.PIPE,
            stderr=errlog,
            bufsize=0,
        )
        self.addCleanup(self.stop, proc)
        line = read_line(proc)
        return proc, json.loads(line)

    def stop(self, proc):
        """End a child through the process API and reap it."""
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=CALL_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=CALL_TIMEOUT_SECONDS)
        if proc.stdout is not None:
            proc.stdout.close()

    def acquired_holder(self, feature, token, **kw):
        proc, first = self.start_holder(feature, token, **kw)
        self.assertEqual(first["outcome"], "acquired", first)
        return proc

    def verify(self, token, *extra, project_root=None):
        return self.result(
            self.run_script(
                "verify",
                "--project-root",
                str(project_root if project_root is not None else self.main),
                "--token",
                token,
                *extra,
            )
        )

    def hold_attempt(self, feature, token, project_root=None):
        """A `hold` that is expected to return at once (lock busy)."""
        return self.result(
            self.run_script(
                "hold",
                "--project-root",
                str(project_root if project_root is not None else self.main),
                "--feature",
                feature,
                "--token",
                token,
            )
        )

    def read_record(self):
        return json.loads(self.record_path.read_text(encoding="utf-8"))

    def write_record(self, **fields):
        record = {
            "feature": "stale-feature",
            "token": TOKEN_C,
            "pid": 1,
            "acquired_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        record.update(fields)
        self.record_path.write_text(json.dumps(record), encoding="utf-8")

    def dead_pid(self):
        """The pid of a child that has already exited and been reaped."""
        child = subprocess.Popen([sys.executable, "-B", "-c", "pass"])
        child.wait(timeout=CALL_TIMEOUT_SECONDS)
        return child.pid


class TestToken(MergeLockCase):
    """AC-1."""

    def test_ac1_token_is_32_lowercase_hex(self):
        out = self.result(self.run_script("token"))
        self.assertEqual(out["outcome"], "token")
        self.assertIsNone(out["reason"])
        self.assertRegex(out["token"], TOKEN_FORMAT)

    def test_ac1_two_calls_return_different_tokens(self):
        first = self.result(self.run_script("token"))["token"]
        second = self.result(self.run_script("token"))["token"]
        self.assertRegex(first, TOKEN_FORMAT)
        self.assertRegex(second, TOKEN_FORMAT)
        self.assertNotEqual(first, second)

    def test_ac1_token_needs_no_repository(self):
        proc = self.run_script("token", cwd=self.home)
        self.assertEqual(self.result(proc)["outcome"], "token")


class TestHoldAcquire(MergeLockCase):
    """AC-2."""

    def test_ac2_hold_from_linked_worktree_writes_the_record(self):
        before = datetime.now().astimezone()
        proc, first = self.start_holder(
            "alpha", TOKEN_A, project_root=self.linked, cwd=self.linked
        )
        after = datetime.now().astimezone()
        self.assertEqual(first["outcome"], "acquired", first)
        self.assertIsNone(first["reason"])
        self.assertTrue(self.lock_path.is_file(), "lock target missing in common dir")
        record = self.read_record()
        self.assertEqual(record["feature"], "alpha")
        self.assertEqual(record["token"], TOKEN_A)
        self.assertEqual(record["pid"], proc.pid)
        stamp = datetime.fromisoformat(record["acquired_at"])
        self.assertIsNotNone(stamp.utcoffset(), "time carries no UTC offset")
        self.assertGreaterEqual(stamp, before - timedelta(seconds=2))
        self.assertLessEqual(stamp, after + timedelta(seconds=2))

    def test_ac2_lock_and_record_live_in_the_common_dir_not_the_worktree(self):
        self.acquired_holder("alpha", TOKEN_A, project_root=self.linked, cwd=self.linked)
        self.assertTrue(self.record_path.is_file())
        linked_git_dir = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.linked,
                env=self.env,
                capture_output=True,
                check=True,
                timeout=CALL_TIMEOUT_SECONDS,
            )
            .stdout.decode()
            .strip()
        )
        self.assertNotEqual(linked_git_dir.resolve(), self.common)
        self.assertFalse((linked_git_dir / LOCK_NAME).exists())
        self.assertFalse((self.linked / LOCK_NAME).exists())

    def test_ac2_main_tree_and_linked_worktree_share_one_lock(self):
        self.acquired_holder("alpha", TOKEN_A, project_root=self.linked, cwd=self.linked)
        out = self.hold_attempt("beta", TOKEN_B, project_root=self.main)
        self.assertEqual(out["outcome"], "stop")
        self.assertEqual(out["reason"], "lock_busy")
        self.assertEqual(out["holder_feature"], "alpha")

    def test_ac2_merge_task_lock_is_never_created(self):
        self.acquired_holder("alpha", TOKEN_A)
        self.assertFalse((self.common / MERGE_TASK_LOCK_NAME).exists())

    def test_ac2_merge_task_lock_is_never_locked(self):
        other = self.common / MERGE_TASK_LOCK_NAME
        fd = os.open(other, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # merge-task.sh's lock is held by this test; hold must not care.
        self.acquired_holder("alpha", TOKEN_A)
        self.assertEqual(other.read_bytes(), b"")

    def test_ac2_hold_does_not_truncate_the_lock_file(self):
        self.lock_path.write_bytes(b"keep")
        self.acquired_holder("alpha", TOKEN_A)
        self.assertEqual(self.lock_path.read_bytes(), b"keep")

    def test_ac2_hold_leaves_no_temporary_file_behind(self):
        self.acquired_holder("alpha", TOKEN_A)
        names = sorted(p.name for p in self.common.glob("em-workflow-feature-merge*"))
        self.assertEqual(names, sorted([LOCK_NAME, RECORD_NAME]))

    def test_ac2_hold_prints_exactly_one_line_while_holding(self):
        proc = self.acquired_holder("alpha", TOKEN_A)
        ready, _, _ = select.select([proc.stdout.fileno()], [], [], 0.3)
        self.assertEqual(ready, [], "holder wrote more than the acquired line")
        self.assertIsNone(proc.poll(), "holder exited on its own")

    def test_ac2_hold_uses_project_root_not_the_working_directory(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        self.acquired_holder("alpha", TOKEN_A, project_root=self.main, cwd=outside)
        self.assertEqual(self.read_record()["feature"], "alpha")


class TestBusyLock(MergeLockCase):
    """AC-3 and AC-5."""

    def test_ac3_other_feature_hold_is_busy_and_record_is_unchanged(self):
        self.acquired_holder("a", TOKEN_A)
        before = self.record_path.read_bytes()
        before_stat = self.record_path.stat()
        started = time.monotonic()
        out = self.hold_attempt("b", TOKEN_B)
        self.assertLess(time.monotonic() - started, CALL_TIMEOUT_SECONDS)
        self.assertEqual(out["outcome"], "stop")
        self.assertEqual(out["reason"], "lock_busy")
        self.assertEqual(out["holder_feature"], "a")
        self.assertEqual(self.record_path.read_bytes(), before)
        self.assertEqual(self.record_path.stat().st_ino, before_stat.st_ino)
        self.assertEqual(self.record_path.stat().st_mtime_ns, before_stat.st_mtime_ns)

    def test_ac3_other_feature_verify_is_busy(self):
        self.acquired_holder("a", TOKEN_A)
        out = self.verify(TOKEN_B)
        self.assertEqual(out["outcome"], "stop")
        self.assertEqual(out["reason"], "lock_busy")
        self.assertEqual(out["holder_feature"], "a")

    def test_ac3_busy_hold_with_unreadable_record_reports_empty_feature(self):
        self.acquired_holder("a", TOKEN_A)
        self.record_path.write_bytes(b"{not json")
        out = self.hold_attempt("b", TOKEN_B)
        self.assertEqual(out["reason"], "lock_busy")
        self.assertEqual(out["holder_feature"], "")
        self.assertEqual(self.record_path.read_bytes(), b"{not json")

    def test_ac3_busy_hold_with_no_record_reports_empty_feature(self):
        self.acquired_holder("a", TOKEN_A)
        self.record_path.unlink()
        out = self.hold_attempt("b", TOKEN_B)
        self.assertEqual(out["reason"], "lock_busy")
        self.assertEqual(out["holder_feature"], "")
        self.assertFalse(self.record_path.exists())

    def test_ac5_second_run_of_same_feature_gets_lock_busy_from_hold(self):
        self.acquired_holder("same", TOKEN_A)
        out = self.hold_attempt("same", TOKEN_B)
        self.assertEqual(out["outcome"], "stop")
        self.assertEqual(out["reason"], "lock_busy")
        self.assertEqual(out["holder_feature"], "same")
        self.assertEqual(self.read_record()["token"], TOKEN_A)

    def test_ac5_second_token_verify_is_busy_never_held(self):
        self.acquired_holder("same", TOKEN_A)
        self.hold_attempt("same", TOKEN_B)
        out = self.verify(TOKEN_B)
        self.assertNotEqual(out["outcome"], "held")
        self.assertEqual(out["outcome"], "stop")
        self.assertEqual(out["reason"], "lock_busy")

    def test_ac5_first_run_still_verifies_held_after_the_rejected_attempt(self):
        self.acquired_holder("same", TOKEN_A)
        self.hold_attempt("same", TOKEN_B)
        self.assertEqual(self.verify(TOKEN_A)["outcome"], "held")


class TestHolderLiveness(MergeLockCase):
    """AC-4."""

    def test_ac4_live_holder_token_is_held(self):
        self.acquired_holder("alpha", TOKEN_A)
        out = self.verify(TOKEN_A)
        self.assertEqual(out["outcome"], "held")
        self.assertIsNone(out["reason"])

    def test_ac4_terminated_holder_is_lock_lost(self):
        proc = self.acquired_holder("alpha", TOKEN_A)
        self.assertEqual(self.verify(TOKEN_A)["outcome"], "held")
        proc.terminate()
        proc.wait(timeout=CALL_TIMEOUT_SECONDS)
        out = self.verify(TOKEN_A)
        self.assertEqual(out["outcome"], "stop")
        self.assertEqual(out["reason"], "lock_lost")

    def test_ac4_record_left_by_dead_holder_is_lost_for_any_token(self):
        proc = self.acquired_holder("alpha", TOKEN_A)
        proc.terminate()
        proc.wait(timeout=CALL_TIMEOUT_SECONDS)
        self.assertTrue(self.record_path.is_file(), "the dead holder's record is gone")
        for token in (TOKEN_A, TOKEN_B):
            out = self.verify(token)
            self.assertEqual(out["outcome"], "stop", token)
            self.assertEqual(out["reason"], "lock_lost", token)

    def test_ac4_new_hold_succeeds_after_a_stale_record(self):
        proc = self.acquired_holder("alpha", TOKEN_A)
        proc.terminate()
        proc.wait(timeout=CALL_TIMEOUT_SECONDS)
        self.acquired_holder("beta", TOKEN_B)
        record = self.read_record()
        self.assertEqual(record["feature"], "beta")
        self.assertEqual(record["token"], TOKEN_B)
        self.assertEqual(self.verify(TOKEN_B)["outcome"], "held")
        self.assertEqual(self.verify(TOKEN_A)["reason"], "lock_busy")

    def test_ac4_killed_holder_releases_the_lock_too(self):
        proc = self.acquired_holder("alpha", TOKEN_A)
        proc.kill()
        proc.wait(timeout=CALL_TIMEOUT_SECONDS)
        self.assertEqual(self.verify(TOKEN_A)["reason"], "lock_lost")
        self.acquired_holder("beta", TOKEN_B)

    def test_ac4_forged_record_of_a_dead_pid_is_lost(self):
        self.write_record(feature="ghost", token=TOKEN_A, pid=self.dead_pid())
        for token in (TOKEN_A, TOKEN_B):
            out = self.verify(token)
            self.assertEqual(out["reason"], "lock_lost", token)
        self.acquired_holder("alpha", TOKEN_B)

    def test_ac4_busy_hold_ignores_the_feature_of_a_dead_record(self):
        holder = self.acquired_holder("alpha", TOKEN_A)
        # A record naming a dead process cannot name the live lock owner.
        self.write_record(feature="ghost", token=TOKEN_C, pid=self.dead_pid())
        out = self.hold_attempt("beta", TOKEN_B)
        self.assertEqual(out["reason"], "lock_busy")
        self.assertEqual(out["holder_feature"], "")
        self.assertIsNone(holder.poll())

    def test_ac4_forged_record_of_a_live_pid_is_held_for_its_token_only(self):
        self.write_record(feature="forged", token=TOKEN_A, pid=os.getpid())
        self.assertEqual(self.verify(TOKEN_A)["outcome"], "held")
        other = self.verify(TOKEN_B)
        self.assertEqual(other["reason"], "lock_busy")
        self.assertEqual(other["holder_feature"], "forged")

    @unittest.skipUnless(
        HAS_PROCFS and hasattr(os, "waitid") and hasattr(os, "WNOWAIT"),
        "needs /proc and waitid(WNOWAIT)",
    )
    def test_ac4_unreaped_holder_is_lost(self):
        proc = self.acquired_holder("alpha", TOKEN_A)
        self.assertEqual(self.verify(TOKEN_A)["outcome"], "held")
        proc.terminate()
        # Wait for the exit without reaping: the holder stays a zombie, whose
        # pid still answers a signal-free liveness probe, yet its lock is gone.
        os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOWAIT)
        self.assertEqual(self.verify(TOKEN_A)["reason"], "lock_lost")
        self.acquired_holder("beta", TOKEN_B)

    @unittest.skipUnless(HAS_PROCFS, "needs /proc")
    def test_ac4_recorded_start_time_must_match_the_process(self):
        start = proc_start_time(os.getpid())
        self.write_record(token=TOKEN_A, pid=os.getpid(), process_start=start)
        self.assertEqual(self.verify(TOKEN_A)["outcome"], "held")
        self.write_record(token=TOKEN_A, pid=os.getpid(), process_start=start + 1)
        self.assertEqual(self.verify(TOKEN_A)["reason"], "lock_lost")

    @unittest.skipUnless(HAS_PROCFS, "needs /proc")
    def test_ac4_hold_records_its_own_start_time(self):
        proc = self.acquired_holder("alpha", TOKEN_A)
        self.assertEqual(self.read_record()["process_start"], proc_start_time(proc.pid))

    def test_ac4_verify_never_creates_or_blocks_on_the_lock(self):
        self.assertFalse(self.lock_path.exists())
        self.assertEqual(self.verify(TOKEN_A)["reason"], "lock_lost")
        self.assertFalse(self.lock_path.exists(), "verify created the lock file")
        # Even with the lock file held by someone else, verify returns.
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual(self.verify(TOKEN_A)["reason"], "lock_lost")

    def test_ac4_record_with_invalid_fields_is_not_a_holder(self):
        bad_records = {
            "bad token": {"token": "XYZ"},
            "bad feature": {"feature": "Not Valid"},
            "pid zero": {"pid": 0},
            "pid negative": {"pid": -1},
            "pid bool": {"pid": True},
            "pid text": {"pid": "123"},
            "start text": {"process_start": "1"},
        }
        for label, override in bad_records.items():
            with self.subTest(label):
                fields = {"feature": "ghost", "token": TOKEN_A, "pid": os.getpid()}
                fields.update(override)
                self.write_record(**fields)
                out = self.verify(TOKEN_A)
                self.assertEqual(out["reason"], "lock_lost")


class TestVerifyWait(MergeLockCase):
    """AC-6, the wait part."""

    def start_verify(self, token, wait):
        return subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "verify",
                "--project-root",
                str(self.main),
                "--token",
                token,
                "--wait",
                str(wait),
            ],
            cwd=self.tmp,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_ac6_wait_returns_held_when_the_holder_starts_slightly_later(self):
        waiter = self.start_verify(TOKEN_A, 15)
        self.addCleanup(self.stop, waiter)
        started = time.monotonic()
        time.sleep(0.5)
        self.assertIsNone(waiter.poll(), "verify gave up before the holder started")
        self.acquired_holder("alpha", TOKEN_A)
        stdout, stderr = waiter.communicate(timeout=CALL_TIMEOUT_SECONDS)
        elapsed = time.monotonic() - started
        self.assertEqual(waiter.returncode, 0, stderr)
        out = json.loads(stdout)
        self.assertEqual(out["outcome"], "held")
        self.assertLess(elapsed, 15, "verify waited out the whole bound")

    def test_ac6_wait_without_a_holder_is_lock_lost_within_the_bound(self):
        started = time.monotonic()
        out = self.verify(TOKEN_A, "--wait", "1")
        elapsed = time.monotonic() - started
        self.assertEqual(out["outcome"], "stop")
        self.assertEqual(out["reason"], "lock_lost")
        self.assertGreaterEqual(elapsed, 0.9, "verify did not wait")
        self.assertLess(elapsed, 1 + 8, "verify overran the wait bound")

    def test_ac6_default_wait_is_zero(self):
        started = time.monotonic()
        out = self.verify(TOKEN_A)
        self.assertEqual(out["reason"], "lock_lost")
        self.assertLess(time.monotonic() - started, 5)

    def test_ac6_busy_does_not_wait(self):
        self.acquired_holder("a", TOKEN_A)
        started = time.monotonic()
        out = self.verify(TOKEN_B, "--wait", "10")
        self.assertEqual(out["reason"], "lock_busy")
        self.assertLess(time.monotonic() - started, 5)

    def test_ac6_unreadable_record_counts_as_not_yet_while_waiting(self):
        self.record_path.write_bytes(b'{"feature": "al')
        waiter = self.start_verify(TOKEN_A, 15)
        self.addCleanup(self.stop, waiter)
        time.sleep(0.4)
        self.assertIsNone(waiter.poll(), "verify gave up on an unreadable record")
        self.acquired_holder("alpha", TOKEN_A)
        stdout, stderr = waiter.communicate(timeout=CALL_TIMEOUT_SECONDS)
        self.assertEqual(json.loads(stdout)["outcome"], "held", stderr)

    def test_ac6_unreadable_record_without_wait_is_lock_lost(self):
        self.record_path.write_bytes(b'{"feature": "al')
        self.assertEqual(self.verify(TOKEN_A)["reason"], "lock_lost")

    def test_ac6_dead_record_stays_lost_for_the_whole_wait(self):
        self.write_record(token=TOKEN_A, pid=self.dead_pid())
        started = time.monotonic()
        out = self.verify(TOKEN_A, "--wait", "1")
        self.assertEqual(out["reason"], "lock_lost")
        self.assertGreaterEqual(time.monotonic() - started, 0.9)


class TestHolderIdle(MergeLockCase):
    """AC-6, the idle part."""

    @unittest.skipUnless(HAS_PROCFS, "needs /proc for CPU time sampling")
    def test_ac6_holder_does_not_spin(self):
        proc = self.acquired_holder("alpha", TOKEN_A)
        time.sleep(0.3)  # let start-up settle
        before = proc_cpu_ticks(proc.pid)
        time.sleep(1.0)
        after = proc_cpu_ticks(proc.pid)
        ticks_per_second = os.sysconf("SC_CLK_TCK")
        # A spinning process would use about one second of CPU here.
        self.assertLessEqual(after - before, max(1, ticks_per_second // 20))
        self.assertIsNone(proc.poll())


class TestOperationBoundary(MergeLockCase):
    """AC-6, the boundary part (FR22, TS20): git is only asked where the
    common directory is; gh is never run."""

    def setUp(self):
        super().setUp()
        self.shim_dir = self.tmp / "shim"
        self.shim_dir.mkdir()
        self.git_log = self.tmp / "git.log"
        self.gh_log = self.tmp / "gh.log"
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        git_shim = self.shim_dir / "git"
        git_shim.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$*" >> "$MERGE_LOCK_TEST_GIT_LOG"\n'
            'exec "$MERGE_LOCK_TEST_REAL_GIT" "$@"\n'
        )
        gh_stub = self.shim_dir / "gh"
        gh_stub.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$*" >> "$MERGE_LOCK_TEST_GH_LOG"\n'
            "exit 1\n"
        )
        for path in (git_shim, gh_stub):
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        self.shim_env = base_env(
            self.home,
            PATH=f"{self.shim_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            MERGE_LOCK_TEST_GIT_LOG=str(self.git_log),
            MERGE_LOCK_TEST_GH_LOG=str(self.gh_log),
            MERGE_LOCK_TEST_REAL_GIT=real_git,
        )

    def git_calls(self):
        if not self.git_log.exists():
            return []
        return self.git_log.read_text().splitlines()

    def test_ac6_all_subcommands_only_locate_the_common_git_directory(self):
        self.result(self.run_script("token", env=self.shim_env))
        self.assertEqual(self.git_calls(), [], "token must not run git at all")
        proc, first = self.start_holder("alpha", TOKEN_A, env=self.shim_env)
        self.assertEqual(first["outcome"], "acquired")
        self.result(
            self.run_script(
                "hold",
                "--project-root",
                str(self.main),
                "--feature",
                "beta",
                "--token",
                TOKEN_B,
                env=self.shim_env,
            )
        )
        for token, extra in ((TOKEN_A, []), (TOKEN_B, []), (TOKEN_C, ["--wait", "0.3"])):
            self.result(
                self.run_script(
                    "verify",
                    "--project-root",
                    str(self.linked),
                    "--token",
                    token,
                    *extra,
                    env=self.shim_env,
                )
            )
        calls = self.git_calls()
        self.assertGreaterEqual(len(calls), 5, "the shim was not exercised")
        for call in calls:
            self.assertEqual(call, "rev-parse --git-common-dir", calls)
        self.assertFalse(self.gh_log.exists(), "gh was run")

    def test_ac6_repository_state_is_untouched(self):
        def snapshot():
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.main,
                env=self.env,
                capture_output=True,
                check=True,
                timeout=CALL_TIMEOUT_SECONDS,
            ).stdout
            refs = subprocess.run(
                ["git", "for-each-ref"],
                cwd=self.main,
                env=self.env,
                capture_output=True,
                check=True,
                timeout=CALL_TIMEOUT_SECONDS,
            ).stdout
            worktrees = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.main,
                env=self.env,
                capture_output=True,
                check=True,
                timeout=CALL_TIMEOUT_SECONDS,
            ).stdout
            return status, refs, worktrees

        before = snapshot()
        self.acquired_holder("alpha", TOKEN_A)
        self.verify(TOKEN_A)
        self.assertEqual(snapshot(), before)


class TestArguments(MergeLockCase):
    """C1: exit 2 for missing or malformed arguments; no stdout then."""

    def assert_usage_error(self, *argv):
        proc = self.run_script(*argv)
        self.assertEqual(proc.returncode, 2, (argv, proc.stderr))
        self.assertEqual(proc.stdout, b"", argv)
        self.assertIn(b"usage:", proc.stderr, argv)

    def test_no_subcommand_is_a_usage_error(self):
        self.assert_usage_error()

    def test_unknown_subcommand_is_a_usage_error(self):
        self.assert_usage_error("release")

    def test_hold_with_missing_arguments_is_a_usage_error(self):
        root = str(self.main)
        self.assert_usage_error("hold")
        self.assert_usage_error("hold", "--project-root", root, "--feature", "a")
        self.assert_usage_error("hold", "--project-root", root, "--token", TOKEN_A)
        self.assert_usage_error("hold", "--feature", "a", "--token", TOKEN_A)

    def test_verify_with_missing_arguments_is_a_usage_error(self):
        self.assert_usage_error("verify")
        self.assert_usage_error("verify", "--project-root", str(self.main))
        self.assert_usage_error("verify", "--token", TOKEN_A)

    def test_malformed_feature_is_a_usage_error(self):
        for feature in ("", "-a", "A", "a_b", "a b", "a/b", "a\n"):
            with self.subTest(feature=feature):
                self.assert_usage_error(
                    "hold",
                    "--project-root",
                    str(self.main),
                    "--feature",
                    feature,
                    "--token",
                    TOKEN_A,
                )

    def test_malformed_token_is_a_usage_error(self):
        for token in ("", "A" * 32, "a" * 31, "a" * 33, "g" * 32, "a" * 32 + "\n"):
            with self.subTest(token=token):
                self.assert_usage_error(
                    "verify", "--project-root", str(self.main), "--token", token
                )
                self.assert_usage_error(
                    "hold",
                    "--project-root",
                    str(self.main),
                    "--feature",
                    "a",
                    "--token",
                    token,
                )

    def test_malformed_wait_is_a_usage_error(self):
        for wait in ("-1", "nan", "inf", "abc", "", "601", "1e9"):
            with self.subTest(wait=wait):
                self.assert_usage_error(
                    "verify",
                    "--project-root",
                    str(self.main),
                    "--token",
                    TOKEN_A,
                    "--wait",
                    wait,
                )

    def test_project_root_that_is_not_a_directory_is_a_usage_error(self):
        self.assert_usage_error(
            "verify",
            "--project-root",
            str(self.tmp / "missing"),
            "--token",
            TOKEN_A,
        )

    def test_project_root_outside_a_repository_is_an_internal_failure(self):
        outside = self.tmp / "plain"
        outside.mkdir()
        env = dict(self.env, GIT_CEILING_DIRECTORIES=str(self.tmp))
        for argv in (
            ["verify", "--project-root", str(outside), "--token", TOKEN_A],
            ["hold", "--project-root", str(outside), "--feature", "a", "--token", TOKEN_A],
        ):
            with self.subTest(argv=argv[0]):
                proc = self.run_script(*argv, env=env)
                self.assertNotIn(proc.returncode, (0, 2), proc.stderr)
                self.assertEqual(proc.stdout, b"")


if __name__ == "__main__":
    unittest.main()
