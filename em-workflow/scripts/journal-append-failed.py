#!/usr/bin/env python3
"""journal-append-failed.py -- the sole new journal writer authorized to
record a terminal `failed` event with reason `orphaned`, `stale-launched`,
or `merge-unverified` (SC2', feature-docs/stale-launched-retry-recovery/
IMPLEMENTATION.md; formerly SC2, feature-docs/orphaned-implementer-recovery/
IMPLEMENTATION.md; SC-1, feature-docs/routeback-deferred-findings/
IMPLEMENTATION.md).

This is a narrow write authority, not a general-purpose journal tool: the
`--reason` value is checked against a closed set -- `orphaned`,
`stale-launched` and `merge-unverified` (D5, widened; SC-1, widened again)
-- before the journal is even opened. Widening the set is a deliberate,
reviewable change to that constant, never a side effect of adding a generic
writer.

`merge-unverified` has a DIFFERENT precondition from the other two reasons:
it appends only over a task whose OWN final journal event is `merged` --
never over `launched` -- and it never accepts a launch identity
(`--launch-at` supplied together with it is a usage error, D4). Its sole
caller is the orchestrator's I.2.b step 1 ancestor-check branch in
`em-workflow/references/implement-phase.md` (IMPLEMENTATION.md SC-4 label,
feature-docs/routeback-deferred-findings/IMPLEMENTATION.md); this module
neither restates nor depends on that document's prose.

Usage:
  journal-append-failed.py --journal PATH --task TASKID --reason orphaned
  journal-append-failed.py --journal PATH --task TASKID --reason stale-launched \\
      --launch-at RAW_AT_VALUE
  journal-append-failed.py --journal PATH --task TASKID --reason merge-unverified

Preconditions (never relaxed, never silently repaired):
  - The journal file must already exist. This helper never creates it and
    never creates its parent directory -- an absent file or an absent
    parent directory is reported as an error.
  - The journal path must not be a symbolic link. Opened with O_NOFOLLOW in
    addition to the upfront check, so a symlink planted between the check
    and the open is still refused rather than followed.

Critical section: one exclusive advisory lock (flock) is held on the
journal file itself across BOTH the replay that determines the task's
current final event and the append -- so a concurrent writer (this helper,
or one of the existing `failed`/`launched` writers) can never interleave
with this one (NFR2).

Decision (re-checked independently of the caller, never trusted blindly),
made INSIDE the same lock as the replay:
  For `orphaned` and `stale-launched`:
  - the task's OWN final event is `launched` and no `--launch-at` was
    supplied -> append (today's behaviour, unchanged);
  - the task's OWN final event is `launched`, `--launch-at` was supplied,
    and that event's `at` equals the supplied value (exact string compare,
    never parsed/normalised) -> append;
  - the task's OWN final event is `launched`, `--launch-at` was supplied,
    and that event's `at` differs, is absent, or is not a string -> no
    append; the caller's launch identity no longer matches the journal's;
  - anything else (`merged`, `failed`, no event at all for this task, any
    other event name) -> no append.
  For `merge-unverified` (never accepts `--launch-at`; rejected earlier,
  before the journal is opened -- see below):
  - the task's OWN final event is `merged` -> append exactly one `failed`
    line through the same line builder the other reasons use (only the
    `reason` value differs);
  - anything else (`launched`, `failed`, no event at all for this task, any
    other event name) -> no append; never over `launched`.
This is the fail-safe direction (NFR1): doubt about the task's real state,
or about which launch is being terminated, never produces a write.

`--launch-at` supplied together with `--reason merge-unverified` is a usage
error, decided BEFORE the journal is opened (D4): the new reason has no
launch-identity semantics.

Outcome: one line of JSON on stdout with keys `outcome`
(`appended` | `noop_terminal` | `launch_changed`), `task`, `reason`. Exit 0
for all three decided outcomes. Exit non-zero (and no write) for a usage
error (argparse, the reason check, or the merge-unverified/--launch-at
combination) or an internal error (this module's own diagnostics);
diagnostics go to stderr, never stdout, in either case.
"""

import argparse
import errno
import fcntl
import json
import os
import sys
from datetime import datetime

# D5 / SC-1: the closed set of `--reason` values this helper accepts.
# Widening this is a deliberate, reviewable change (IMPLEMENTATION.md D5;
# feature-docs/routeback-deferred-findings/IMPLEMENTATION.md SC-1) -- never a
# consequence of the helper being made more generic.
VALID_REASONS = {"orphaned", "stale-launched", "merge-unverified"}


class JournalAccessError(Exception):
    """A precondition failure on the journal path itself (SC2 Pre: the file
    must already exist, and must not be a symbolic link). Raised BEFORE any
    write is attempted; the journal is guaranteed untouched when this is
    raised."""


def valid_reason(reason):
    return isinstance(reason, str) and reason in VALID_REASONS


def now_rfc3339():
    """Same format as the existing `failed` writers (queue_failure_net.py,
    queue_taskstop_net.py): local time, seconds precision, explicit UTC
    offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def open_journal_for_append(path):
    """Opens `path` read/write, positioned to append, WITHOUT creating it
    and WITHOUT following a symbolic link (SC2 Pre). Raises
    JournalAccessError with a human-readable message on any precondition
    failure; never creates the file or its parent directory on any path
    through this function."""
    parent = os.path.dirname(path) or "."
    if not os.path.isdir(parent):
        raise JournalAccessError(f"journal directory does not exist: {parent}")
    if os.path.islink(path):
        raise JournalAccessError(f"journal path is a symbolic link, refusing to open: {path}")
    if not os.path.exists(path):
        raise JournalAccessError(f"journal file does not exist: {path}")

    flags = os.O_RDWR | os.O_APPEND
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise JournalAccessError(f"journal path is a symbolic link, refusing to open: {path}")
        raise JournalAccessError(f"cannot open journal file {path}: {exc}")
    return fd


def read_all_fd(fd):
    """Reads the full current content of an already-open fd, from offset 0,
    without disturbing its O_APPEND write behavior."""
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def last_event_for_task(content, task_id):
    """Replays `content` (journal file text) for the LAST event recorded
    for `task_id`, by file order. None means no event recorded for this
    task. Malformed lines are skipped, never raised -- matching the
    replay discipline of the existing journal writers/readers. Thin
    wrapper over `last_entry_for_task`, kept for callers that only need
    the event name."""
    entry = last_entry_for_task(content, task_id)
    return entry.get("event") if entry is not None else None


def last_entry_for_task(content, task_id):
    """Replays `content` (journal file text) for the LAST full JSON entry
    recorded for `task_id`, by file order -- same replay discipline as
    `last_event_for_task` (malformed lines skipped, never raised), but
    returns the whole entry dict rather than just the event name, so a
    caller can inspect additional fields (e.g. `at`) of that last event.
    None means no event recorded for this task."""
    last_entry = None
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("task") != task_id:
            continue
        event = entry.get("event")
        if isinstance(event, str):
            last_entry = entry
    return last_entry


def build_failed_line(task_id, reason):
    """SC4: field names and ORDER are taken from the existing `failed`
    writers (queue_failure_net.py, queue_taskstop_net.py), not invented.
    The change is additive: new values (`orphaned`, `stale-launched`) of
    the existing `reason` field."""
    entry = {
        "event": "failed",
        "task": task_id,
        "at": now_rfc3339(),
        "reason": reason,
    }
    return json.dumps(entry, ensure_ascii=False)


def append_failed_fd(fd, task_id, reason):
    line = build_failed_line(task_id, reason)
    os.write(fd, (line + "\n").encode("utf-8"))
    os.fsync(fd)


def decide_and_append(journal_path, task_id, reason, launch_at=None):
    """The full critical section (NFR2): open (no create, no symlink
    follow), take an exclusive lock, replay the task's OWN final event
    under that lock, and decide whether to append the `failed` line.

    For `orphaned` and `stale-launched`: append ONLY when that final event
    is `launched` AND (no `launch_at` was supplied, OR that event's own
    `at` equals `launch_at` as an exact string). `launch_at` is never
    parsed or normalised (D-C) -- an absent, differing, or non-string `at`
    on the last `launched` event yields `launch_changed` instead of an
    append. Every other observed state -- `merged`, `failed`, or no event
    at all -- is a no-op (NFR1 fail-safe direction: doubt never produces a
    write).

    For `merge-unverified` (SC-1, feature-docs/routeback-deferred-findings/
    IMPLEMENTATION.md): append ONLY when that final event is `merged`;
    every other observed state -- `launched`, `failed`, or no event at all
    -- is a no-op. `launch_at` is never supplied with this reason (rejected
    earlier, in `main`, before the journal is opened -- D4).

    Returns the outcome string (`appended` | `noop_terminal` |
    `launch_changed`). Raises JournalAccessError for a precondition
    failure on the journal path itself -- the journal is left untouched in
    that case."""
    fd = open_journal_for_append(journal_path)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            content = read_all_fd(fd)
            entry = last_entry_for_task(content, task_id)
            last_event = entry.get("event") if entry is not None else None

            if reason == "merge-unverified":
                if last_event != "merged":
                    return "noop_terminal"
                append_failed_fd(fd, task_id, reason)
                return "appended"

            if last_event != "launched":
                return "noop_terminal"
            if launch_at is None:
                append_failed_fd(fd, task_id, reason)
                return "appended"
            current_at = entry.get("at")
            if isinstance(current_at, str) and current_at == launch_at:
                append_failed_fd(fd, task_id, reason)
                return "appended"
            return "launch_changed"
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="journal-append-failed.py",
        description=(
            "Append one terminal `failed` journal event for an orphaned, "
            "stale-launched, or ancestor-check-failed (merge-unverified) "
            "implementer task (SC2'; SC-1, "
            "feature-docs/routeback-deferred-findings/IMPLEMENTATION.md)."
        ),
    )
    parser.add_argument("--journal", required=True, metavar="PATH", help="path to the feature's journal.jsonl")
    parser.add_argument("--task", required=True, metavar="TASKID", help="task id, e.g. task0007")
    parser.add_argument(
        "--reason",
        required=True,
        metavar="NAME",
        help=f"closed set: {sorted(VALID_REASONS)}",
    )
    parser.add_argument(
        "--launch-at",
        required=False,
        default=None,
        metavar="VALUE",
        help=(
            "raw `at` value of the `launched` event this decision was made "
            "against; compared as an exact string against the task's last "
            "event inside the lock, never parsed or normalised (D-C); not "
            "accepted together with --reason merge-unverified"
        ),
    )
    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)  # argparse itself exits non-zero, stderr-only, on a usage error

    if not valid_reason(args.reason):
        print(
            f"journal-append-failed: --reason must be one of {sorted(VALID_REASONS)}, got {args.reason!r}",
            file=sys.stderr,
        )
        return 2

    if args.reason == "merge-unverified" and args.launch_at is not None:
        # D4: decided BEFORE the journal is opened -- the new reason has no
        # launch-identity semantics. Distinct diagnostic from the
        # unknown-reason rejection above.
        print(
            "journal-append-failed: --launch-at is not accepted together with --reason merge-unverified",
            file=sys.stderr,
        )
        return 2

    try:
        outcome = decide_and_append(args.journal, args.task, args.reason, launch_at=args.launch_at)
    except JournalAccessError as exc:
        print(f"journal-append-failed: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"journal-append-failed: unexpected OS error: {exc}", file=sys.stderr)
        return 2

    result = {"outcome": outcome, "task": args.task, "reason": args.reason}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
