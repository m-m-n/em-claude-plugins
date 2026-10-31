#!/usr/bin/env python3
"""Repository-wide merge lock (em-workflow plugin, task0005 of
feature-docs/unattended-merge; FR10 / FR22 / NFR5; IMPLEMENTATION.md C1, C2,
C7 and decision D3).

Serializes the unattended merge runs of one repository. A background holder
process keeps an exclusive flock on a file in the repository's common git
directory from base integration through the merge; every run proves with its
own token that it is the current holder.

Subcommands (long options only, one JSON object on one stdout line):

  token
      {"outcome": "token", "reason": null, "detail": "", "token": "<32 hex>"}

  hold --project-root P --feature F --token T
      Takes an exclusive, non-blocking flock on `em-workflow-feature-merge.lock`
      in the common git directory (the file is opened without truncating it),
      replaces the sibling holder record `em-workflow-feature-merge.holder`
      atomically with {feature, token, pid, acquired_at (with UTC offset),
      process_start (Linux only)}, prints outcome `acquired`, then waits
      without using CPU until it is terminated. The operating system releases
      the lock when the process ends, whether through TaskStop, a signal or
      the end of the session. When the lock is busy it prints stop `lock_busy`
      with `holder_feature` (empty when no live holder is named by a readable
      record) and exits 0 at once, without touching the record.

  verify --project-root P --token T [--wait SECONDS]
      Never takes the lock. Reads the holder record and probes the recorded
      process without sending a signal:
        - the record carries T and its process is alive -> outcome `held`
        - a live process carries another token -> stop `lock_busy`
        - otherwise, polls until SECONDS (default 0) elapse, then stop
          `lock_lost`; a missing, unreadable or partly written record, a dead
          holder and a holder that has not started yet are all "not yet".

Liveness: `kill(pid, 0)` answers for a zombie and for a reused pid as well,
so on Linux the probe also reads /proc/<pid>/stat. A zombie is dead (its lock
is already released), and when the record carries `process_start` the
process's start time must match it, so a recycled pid is not taken for the
holder.

The only external command is `git rev-parse --git-common-dir`, which locates
the common git directory; the lock of merge-task.sh (`em-workflow-merge.lock`)
is never opened. Exit codes: 0 when a decision was produced (stop outcomes
included), 2 for missing or malformed arguments, 1 for an internal failure
(diagnostic on stderr, nothing on stdout).
"""

import argparse
import fcntl
import json
import math
import os
import re
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime

LOCK_NAME = "em-workflow-feature-merge.lock"
RECORD_NAME = "em-workflow-feature-merge.holder"

FEATURE_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")
TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}")

GIT_TIMEOUT_SECONDS = 30
# One invocation finishes within 600 s (C1); the bound leaves room for start-up.
MAX_WAIT_SECONDS = 590.0
POLL_INTERVAL_SECONDS = 0.05
MAX_RECORD_BYTES = 4096
MAX_PID = 2**31 - 1

# Variables that would point git at another repository than --project-root.
GIT_REDIRECT_VARIABLES = (
    "GIT_DIR",
    "GIT_COMMON_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
)


class InternalFailure(Exception):
    """A failure that is no decision: reported on stderr, exit 1."""


def is_feature(value):
    return isinstance(value, str) and FEATURE_PATTERN.fullmatch(value) is not None


def is_token(value):
    return isinstance(value, str) and TOKEN_PATTERN.fullmatch(value) is not None


def emit(outcome, reason=None, detail="", **extra):
    payload = {"outcome": outcome, "reason": reason, "detail": detail}
    payload.update(extra)
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()


# -- argument validation ---------------------------------------------------


def arg_feature(value):
    if not is_feature(value):
        raise argparse.ArgumentTypeError("not a valid feature name")
    return value


def arg_token(value):
    if not is_token(value):
        raise argparse.ArgumentTypeError("not a 32-character lowercase hex token")
    return value


def arg_directory(value):
    if not value or "\0" in value or not os.path.isdir(value):
        raise argparse.ArgumentTypeError("not an existing directory")
    return value


def arg_wait(value):
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("not a number") from None
    if not math.isfinite(seconds) or seconds < 0 or seconds > MAX_WAIT_SECONDS:
        raise argparse.ArgumentTypeError(
            f"must be between 0 and {MAX_WAIT_SECONDS:g} seconds"
        )
    return seconds


def build_parser():
    parser = argparse.ArgumentParser(
        prog="merge-lock.py",
        description="Repository-wide merge lock (token / hold / verify).",
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("token", allow_abbrev=False, help="print a fresh token")

    hold = commands.add_parser(
        "hold", allow_abbrev=False, help="take the lock and keep it until terminated"
    )
    hold.add_argument("--project-root", required=True, type=arg_directory)
    hold.add_argument("--feature", required=True, type=arg_feature)
    hold.add_argument("--token", required=True, type=arg_token)

    verify = commands.add_parser(
        "verify", allow_abbrev=False, help="check that this token is the live holder"
    )
    verify.add_argument("--project-root", required=True, type=arg_directory)
    verify.add_argument("--token", required=True, type=arg_token)
    verify.add_argument("--wait", type=arg_wait, default=0.0)
    return parser


# -- repository ------------------------------------------------------------


def locate_common_dir(project_root):
    """The absolute common git directory shared by every worktree."""
    env = {k: v for k, v in os.environ.items() if k not in GIT_REDIRECT_VARIABLES}
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=project_root,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InternalFailure(f"cannot run git: {type(exc).__name__}") from None
    if proc.returncode != 0:
        raise InternalFailure("git could not locate the common git directory")
    text = os.fsdecode(proc.stdout)
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        raise InternalFailure("git printed no common git directory")
    common = os.path.realpath(os.path.join(project_root, text))
    if not os.path.isdir(common):
        raise InternalFailure("the common git directory does not exist")
    return common


# -- holder record and liveness --------------------------------------------


def parse_proc_stat(raw):
    """The stat fields after the command name: [state, ppid, ...]."""
    close = raw.rindex(b")")
    return raw[close + 2 :].split()


def own_start_time():
    """The start time of this process in clock ticks since boot, or None."""
    try:
        with open("/proc/self/stat", "rb") as handle:
            return int(parse_proc_stat(handle.read(4096))[19])
    except (OSError, ValueError, IndexError):
        return None


def read_record(common_dir):
    """The validated holder record, or None when absent or unusable."""
    path = os.path.join(common_dir, RECORD_NAME)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RECORD_BYTES:
            return None
        data = os.read(fd, MAX_RECORD_BYTES + 1)
    except OSError:
        return None
    finally:
        os.close(fd)
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(document, dict):
        return None
    pid = document.get("pid")
    start = document.get("process_start")
    if not is_feature(document.get("feature")) or not is_token(document.get("token")):
        return None
    if type(pid) is not int or not 0 < pid <= MAX_PID:
        return None
    if start is not None and (type(start) is not int or start < 0):
        return None
    return {
        "feature": document["feature"],
        "token": document["token"],
        "pid": pid,
        "process_start": start,
    }


def holder_alive(record):
    """Whether the process the record names is a live holder (no signal sent)."""
    pid = record["pid"]
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # exists, owned by someone else
    except OSError:
        return False
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            raw = handle.read(4096)
    except FileNotFoundError:
        # With a usable /proc, no entry means the process is gone.
        return not os.path.exists("/proc/self/stat")
    except OSError:
        return True  # /proc cannot be read; the signal-free probe stands
    try:
        fields = parse_proc_stat(raw)
        state = fields[0]
        started = int(fields[19])
    except (ValueError, IndexError):
        return False  # cannot confirm the process; fail closed
    if state in (b"Z", b"X"):
        return False  # exited; its lock is already released
    if record["process_start"] is not None and record["process_start"] != started:
        return False  # the pid now belongs to another process
    return True


def classify(common_dir, token):
    """('held' | 'busy' | 'none', record) for this token."""
    record = read_record(common_dir)
    if record is None or not holder_alive(record):
        return "none", None
    return ("held" if record["token"] == token else "busy"), record


# -- subcommands -----------------------------------------------------------


def command_token(_args):
    token = secrets.token_hex(16)
    if not is_token(token):
        raise InternalFailure("generated token is malformed")
    emit("token", token=token)
    return 0


def write_record(common_dir, feature, token):
    record = {
        "feature": feature,
        "token": token,
        "pid": os.getpid(),
        "acquired_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    start = own_start_time()
    if start is not None:
        record["process_start"] = start
    payload = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temp_path = tempfile.mkstemp(
        prefix=RECORD_NAME + ".", suffix=".tmp", dir=common_dir
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, os.path.join(common_dir, RECORD_NAME))
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def command_hold(args):
    common_dir = locate_common_dir(args.project_root)
    lock_path = os.path.join(common_dir, LOCK_NAME)
    try:
        lock_fd = os.open(
            lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600
        )
    except OSError as exc:
        raise InternalFailure(f"cannot open the lock file: {exc.strerror}") from None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        record = read_record(common_dir)
        holder_feature = ""
        if record is not None and holder_alive(record):
            holder_feature = record["feature"]
        emit(
            "stop",
            "lock_busy",
            "another run holds the merge lock",
            holder_feature=holder_feature,
        )
        return 0
    except OSError as exc:
        os.close(lock_fd)
        raise InternalFailure(f"cannot lock the lock file: {exc.strerror}") from None

    write_record(common_dir, args.feature, args.token)
    emit("acquired")
    # lock_fd stays open for the life of the process; the operating system
    # releases the lock when the process ends. signal.pause() sleeps in the
    # kernel, so the holder uses no CPU while it waits.
    while True:
        signal.pause()


def command_verify(args):
    common_dir = locate_common_dir(args.project_root)
    deadline = time.monotonic() + args.wait
    while True:
        state, record = classify(common_dir, args.token)
        if state == "held":
            emit("held")
            return 0
        if state == "busy":
            emit(
                "stop",
                "lock_busy",
                "a live holder carries another token",
                holder_feature=record["feature"],
            )
            return 0
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(POLL_INTERVAL_SECONDS, remaining))
    emit("stop", "lock_lost", "no live holder carries this token")
    return 0


COMMANDS = {"token": command_token, "hold": command_hold, "verify": command_verify}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except InternalFailure as exc:
        sys.stderr.write(f"merge-lock.py: {exc}\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"merge-lock.py: {type(exc).__name__}: {exc.strerror}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
