#!/usr/bin/env python3
"""Codex Stop hook that stops the terminal-bound descendants of a launch.

Codex gives a command a pseudo terminal when asked for `tty: true`. A
`python3 -i` or `bash -i` started there keeps waiting for input after the
turn is over and can spin as an orphan. At the end of a turn this hook stops
every descendant of the launch whose standard input is `/dev/pts/*`.

Invocation: `python3 codex-hook-tty-reaper.py ANCHOR`, with the Stop payload
Codex writes on standard input. ANCHOR is the PID of the `run_codex_exec.sh`
process that started the launch. It is the only thing that selects targets.

On every path the hook exits with status 0 and writes nothing to standard
output or standard error: it returns no block / continue decision and does
not change how Codex stops. Any doubt ends in stopping nothing.

Flow:

  1. Read standard input to end-of-input, for at most 1 second. Anything but
     one UTF-8 JSON object -> stop nothing. No field of the object is used.
  2. The argument list must be exactly one argument made of ASCII digits
     only, with a value greater than 1. Otherwise stop nothing.
  3. Read the process table (`/proc`). If it is missing or the hook's own
     entry cannot be read -> stop nothing.
  4. Walk the hook's own ancestor chain to PID 1. If a link cannot be read,
     or ANCHOR is not a proper ancestor on the chain -> stop nothing. Every
     link must obey the start-time rule: the parent's start time is not later
     than its child's (equal is fine). One link that breaks it -> stop
     nothing.
  5. Take one snapshot of the process table. Parent, state and start time are
     read from after the last closing parenthesis of the process-name field,
     so a name that holds spaces or parentheses cannot shift them. An entry
     that vanishes or cannot be read is left out. Then ANCHOR must still be
     the process step 4 saw: the snapshot must hold an entry for its PID
     whose start time equals, exactly, the start time of ANCHOR read in the
     step 4 walk. A start time that differs by any amount (one tick
     included), or no entry for the PID -> stop nothing. The parent is not
     compared.
  6. Targets: descendants of ANCHOR whose standard-input link (fd 0) names a
     path under `/dev/pts/` (a terminal whose master is gone reads as
     `/dev/pts/N (deleted)` and counts), minus the hook and every process on
     its ancestor chain. Session, process group and having children play no
     part. The descendants are found from the snapshot through links that
     obey the same start-time rule, using the start times the snapshot
     recorded: a process whose parent started later than it did is not a
     descendant, and neither is anything reachable only through it. ANCHOR
     itself must be in the snapshot, or there are no targets.
  7. Order: deepest first, ties by ascending PID, so every target comes after
     all of its target descendants.
  8. SIGTERM each target, in that order. For each, a pidfd is opened for its
     PID first. While the pidfd is held, the target must still be the same
     process: entry present, same start time as recorded, not a zombie. Only
     then SIGTERM is sent, through that pidfd, and the pidfd is kept. A target
     that fails the check gets no signal now or later and its pidfd is
     closed.
  9. Wait until every signalled target is gone or 0.5 seconds have passed
     since the last SIGTERM.
 10. SIGKILL, in the same order, each target that is still there: the same
     check, then SIGKILL through the same pidfd that carried its SIGTERM. A
     target never gets a second pidfd. Every pidfd the hook opened is closed
     before it exits, on every path.

A no-such-process result from opening a pidfd or from sending through it is
not an error: that target gets no further signal and the others go on. Any
other error ends the run: no further signal is sent (the SIGKILL phase
included) and the open pidfds are closed. Signals are never sent by PID. When
`os.pidfd_open` or `signal.pidfd_send_signal` does not exist, or the kernel
has no pidfd (ENOSYS), nothing is stopped.
"""

import json
import os
import select
import signal
import sys
import time

PROC_DIR = "/proc"
STDIN_LIMIT_SECONDS = 1.0
GRACE_SECONDS = 0.5
POLL_SECONDS = 0.01
READ_CHUNK = 65536
STAT_LIMIT = 65536
PTY_PREFIX = "/dev/pts/"
DEAD_STATES = frozenset("ZXx")
# Fields after the process name in /proc/PID/stat, counted from the state
# (field 3): ppid is field 4, starttime is field 22.
STAT_PPID_INDEX = 1
STAT_START_INDEX = 19
STAT_MIN_FIELDS = 20
# The real pidfd functions. A missing one is None, which `_stop` reads as
# "pidfd unavailable": the hook stops nothing and never signals by PID.
PIDFD_OPEN = getattr(os, "pidfd_open", None)
PIDFD_SEND_SIGNAL = getattr(signal, "pidfd_send_signal", None)


def _stdin_is_one_json_object(fd, clock):
    """True when FD delivers one UTF-8 JSON object before the time limit."""
    deadline = clock() + STDIN_LIMIT_SECONDS
    poller = select.poll()
    poller.register(fd, select.POLLIN)
    chunks = []
    while True:
        remaining = deadline - clock()
        if remaining <= 0 or not poller.poll(remaining * 1000.0):
            return False
        chunk = os.read(fd, READ_CHUNK)
        if not chunk:
            break
        chunks.append(chunk)
    try:
        value = json.loads(b"".join(chunks).decode("utf-8"))
    except ValueError:  # includes UnicodeDecodeError
        return False
    return isinstance(value, dict)


def _parse_anchor(argv):
    """The anchor PID, or None unless ARGV is exactly one valid argument."""
    if len(argv) != 1:
        return None
    text = argv[0]
    if not (text.isascii() and text.isdigit()):
        return None
    value = int(text)
    return value if value > 1 else None


def _read_stat(proc_dir, pid):
    """(state, ppid, start) of PID, or None when it cannot be read as such.

    The three values come from after the last closing parenthesis: the
    process name may hold any byte, including spaces and parentheses."""
    try:
        with open(os.path.join(proc_dir, str(pid), "stat"), "rb") as handle:
            data = handle.read(STAT_LIMIT)
    except OSError:
        return None
    head = b"%d (" % pid
    if not data.startswith(head):
        return None
    close = data.rfind(b")")
    if close < len(head):
        return None
    rest = data[close + 1:]
    if not rest.startswith(b" "):
        return None
    fields = rest.split()
    if len(fields) < STAT_MIN_FIELDS:
        return None
    state, ppid, start = fields[0], fields[STAT_PPID_INDEX], fields[STAT_START_INDEX]
    if len(state) != 1 or not state.isalpha() or not state.isascii():
        return None
    if not (ppid.isdigit() and start.isdigit()):
        return None
    return state.decode("ascii"), int(ppid), int(start)


def _ancestor_chain(proc_dir, pid, starts=None):
    """[PID, parent, ..., top] up to PID 1, or None when a link is unreadable,
    the chain loops, or a link breaks the start-time rule (a parent that
    started later than its child).

    When STARTS is a dict, it receives {pid: start time} for every link of the
    chain, taken from the same reads that built the chain."""
    chain = [pid]
    seen = {pid}
    record = _read_stat(proc_dir, pid)
    while True:
        if record is None:
            return None
        if starts is not None:
            starts[chain[-1]] = record[2]
        ppid = record[1]
        if chain[-1] == 1 or ppid == 0:
            return chain
        if ppid in seen:
            return None
        parent = _read_stat(proc_dir, ppid)
        if parent is None or parent[2] > record[2]:
            return None
        seen.add(ppid)
        chain.append(ppid)
        record = parent


def _snapshot(proc_dir):
    """{pid: (state, ppid, start)} for every readable entry of the table."""
    table = {}
    for name in os.listdir(proc_dir):
        if not (name.isascii() and name.isdigit()):
            continue
        pid = int(name)
        if pid < 1 or str(pid) != name:
            continue
        record = _read_stat(proc_dir, pid)
        if record is not None:
            table[pid] = record
    return table


def _anchor_is_unchanged(table, anchor, start):
    """True when TABLE holds ANCHOR with exactly START as its start time.

    Identity is the PID plus the start time; the parent plays no part."""
    entry = table.get(anchor)
    return entry is not None and entry[2] == start


def _depths_below(table, anchor):
    """{pid: depth below ANCHOR} for every descendant of ANCHOR.

    A link from a process to its recorded parent is adopted only when the
    parent's recorded start time is not later than the process's own. A
    process whose link is rejected, and everything reachable only through it,
    is not a descendant. ANCHOR must be in TABLE; otherwise nothing is."""
    if anchor not in table:
        return {}
    children = {}
    for pid, (_state, ppid, _start) in table.items():
        children.setdefault(ppid, []).append(pid)
    depths = {}
    seen = {anchor}
    frontier = [anchor]
    depth = 0
    while frontier:
        depth += 1
        following = []
        for parent in frontier:
            parent_start = table[parent][2]
            for child in children.get(parent, ()):
                if child in seen or table[child][2] < parent_start:
                    continue
                seen.add(child)
                depths[child] = depth
                following.append(child)
        frontier = following
    return depths


def _has_terminal_stdin(proc_dir, pid):
    try:
        link = os.readlink(os.path.join(proc_dir, str(pid), "fd", "0"))
    except OSError:
        return False
    return link.startswith(PTY_PREFIX) and len(link) > len(PTY_PREFIX)


def _targets(proc_dir, table, anchor, excluded):
    """[(pid, start)] of the targets, deepest first, ties by ascending PID."""
    found = []
    for pid, depth in _depths_below(table, anchor).items():
        if pid in excluded or not _has_terminal_stdin(proc_dir, pid):
            continue
        found.append((-depth, pid, table[pid][2]))
    found.sort()
    return [(pid, start) for _depth, pid, start in found]


def _same_process(proc_dir, pid, start):
    """True while PID is still the process recorded with START, and alive."""
    record = _read_stat(proc_dir, pid)
    return record is not None and record[2] == start and record[0] not in DEAD_STATES


def _release(held, pidfd, pidfd_close):
    """Close PIDFD now; it leaves HELD first, so it is never closed twice."""
    held.remove(pidfd)
    pidfd_close(pidfd)


def _stop(proc_dir, targets, pidfd_open, pidfd_send_signal, pidfd_close, clock, sleep):
    if not (callable(pidfd_open) and callable(pidfd_send_signal) and callable(pidfd_close)):
        return
    held = []  # every pidfd opened and not yet closed
    try:
        signalled = []
        for pid, start in targets:
            try:
                pidfd = pidfd_open(pid)
            except ProcessLookupError:
                continue
            held.append(pidfd)
            if not _same_process(proc_dir, pid, start):
                _release(held, pidfd, pidfd_close)
                continue
            try:
                pidfd_send_signal(pidfd, signal.SIGTERM)
            except ProcessLookupError:
                _release(held, pidfd, pidfd_close)
                continue
            signalled.append((pid, start, pidfd))
        if not signalled:
            return
        deadline = clock() + GRACE_SECONDS
        while any(_same_process(proc_dir, pid, start) for pid, start, _pidfd in signalled):
            remaining = deadline - clock()
            if remaining <= 0:
                break
            sleep(min(POLL_SECONDS, remaining))
        else:
            return
        for pid, start, pidfd in signalled:
            if _same_process(proc_dir, pid, start):
                try:
                    pidfd_send_signal(pidfd, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    finally:
        while held:
            try:
                pidfd_close(held.pop())
            except Exception:
                pass


def _reap(argv, stdin_fd, proc_dir, pidfd_open, pidfd_send_signal, pidfd_close,
          clock, sleep):
    if not _stdin_is_one_json_object(stdin_fd, clock):
        return
    anchor = _parse_anchor(argv)
    if anchor is None:
        return
    own = os.getpid()
    starts = {}
    chain = _ancestor_chain(proc_dir, own, starts)
    if chain is None or anchor not in chain[1:]:
        return
    table = _snapshot(proc_dir)
    if not _anchor_is_unchanged(table, anchor, starts[anchor]):
        return
    targets = _targets(proc_dir, table, anchor, set(chain))
    _stop(proc_dir, targets, pidfd_open, pidfd_send_signal, pidfd_close, clock, sleep)


def main(argv, stdin_fd=0, proc_dir=PROC_DIR, pidfd_open=PIDFD_OPEN,
         pidfd_send_signal=PIDFD_SEND_SIGNAL, pidfd_close=os.close,
         clock=time.monotonic, sleep=time.sleep):
    """Run the hook once. Always returns 0; never writes to stdout/stderr.

    The collaborators are the seams of the unit tests. The command-line entry
    below always uses the real ones. A pidfd function that is None means
    "unavailable": nothing is stopped."""
    try:
        _reap(argv, stdin_fd, proc_dir, pidfd_open, pidfd_send_signal, pidfd_close,
              clock, sleep)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except BaseException:
        pass
    sys.exit(0)
