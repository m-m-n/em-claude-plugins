"""Unit tests for `scripts/codex-hook-tty-reaper.py`, the Codex Stop hook that
ships as two byte-identical copies: one in `em-workflow/` and one in
`em-review/` (feature-docs/codex-stop-hook-tty-reaper/tasks/task0001.md).

Acceptance Criteria covered:

- AC-1 (FR2, NFR5): both copies exist, are byte-identical and import only the
  standard library; importing a copy performs no action.
- AC-2 (FR3, FR7, TM-4): descendants with a `/dev/pts/*` standard input are
  stopped, whether they have a child or run in their own session; a pipe
  standard input is left alone; a process-name field that imitates the
  following fields cannot shift the parent or the start time.
- AC-3 (FR3, FR4): a parent and its child are both stopped, the child first
  in both the SIGTERM and the SIGKILL phase.
- AC-4 (FR4, NFR2, TM-3): SIGTERM first, SIGKILL no earlier than 0.5 s after
  the last SIGTERM, a SIGTERM-ignoring process is gone within the time bound,
  and a target whose start time changed gets no further signal.
- AC-5 (NFR1, NFR6, TM-2): outsiders and the hook's ancestors are never
  signalled; an anchor argument that is not exactly one ASCII-decimal value
  greater than 1 naming a proper ancestor of the hook stops nothing.
- AC-6 (FR4, FR5, NFR6, TM-1, TM-5): nothing on stdout or stderr and exit 0 on
  every path; invalid or open standard input stops nothing; its fields choose
  no target; failures stop further signals.
- AC-7 (NFR5): a missing process table stops nothing.

PID-reuse hardening (feature-docs/codex-hook-tty-reaper-pid-reuse/tasks/
task0001.md), pinned by the classes `TestLinkRule`, `TestAncestorChainRule`,
`TestPidfdSignalling`, `TestPidfdUnavailable`, `TestPidfdErrors`,
`TestNoPidAddressedSignalling` and `TestModuleDocstring`:

- AC-1 (FR1, TM-1): a descendant link is adopted only when the parent started
  no later than the child; a rejected child and everything below it get no
  signal; equal start times are adopted; an anchor missing from the snapshot
  stops nothing.
- AC-2 (FR6, TM-2): one invalid link on the hook's ancestor chain stops
  nothing; equal start times on the chain do not prevent stopping.
- AC-3 (FR2, TM-3): the pidfd is opened before the identity check and held
  while it runs; a signal goes only through that pidfd and only after the
  check; a PID that changes hands after the check is never reached.
- AC-4 (FR3, TM-4): SIGKILL goes through the pidfd that carried the SIGTERM,
  after the same check; no target gets a second pidfd; every pidfd the run
  opened is closed when `main()` returns, on every path.
- AC-5 (FR4, TM-5): with a pidfd function unavailable nothing is stopped, and
  the PID-addressed signal function is never called.
- AC-6 (FR5): no-such-process at open or send skips that target; any other
  error ends all signalling; exit 0 and no output on every path.
- AC-7 (FR7, FR8, NFR2, NFR3): the defaults of `main()` are the real pidfd
  functions; the fake pidfd binds to the instance holding the PID at open
  time; selection, order, timing and the other pre-existing tests are kept.
- AC-8 (FR9, NFR1): the module docstring states the link rule, the pidfd
  signalling and the pidfd-unavailable behaviour; standard library only.

The test helper `without_attribute`, pinned by the class `TestWithoutAttribute`
(feature-docs/tty-reaper-without-attribute-absent/tasks/task0001.md): an
attribute absent at entry is neither deleted nor assigned and stays absent,
also when the block raises; an attribute present at entry is absent inside the
block and the identical object is back after it, also when the block raises;
nesting it on `os.pidfd_open` and `signal.pidfd_send_signal` restores the
original state.

Anchor identity (feature-docs/codex-hook-tty-reaper-anchor-identity/tasks/
task0001.md), pinned by the class `TestAnchorIdentity` and the docstring test
`test_anchor_identity_the_flow_states_the_anchor_start_time_check`:

- AC-1, AC-2 (FR1, FR4, TM-1): when the snapshot holds the anchor PID with a
  start time that differs from the one the ancestor-chain read saw, by any
  amount (one tick included), nothing is signalled and no pidfd is opened.
- AC-3 (FR1, NFR2): an anchor PID absent from the snapshot stops nothing; the
  mismatch path ends with exit 0 and no output.
- AC-4, AC-5 (FR1, NFR3): a changed parent of the anchor, or an exited process
  between the anchor and the hook, does not prevent stopping.
- AC-6 (FR2, FR3): the Flow describes the check in step 5.

Two kinds of test:

- Real-process tests start a pseudo-Codex tree of their own: a Python process
  that forks descendants, gives the chosen ones a pseudo-terminal as standard
  input and the others a pipe, and runs the hook as a separate process that
  descends from it. Every anchor passed to the hook in these tests is a
  process the test started (NFR4); the test sends no signal itself. Every
  process the tests start ends by itself within `LIFETIME` seconds, and
  normally at once, when the test closes the control pipe.
- In-process tests drive `main()` over a fabricated process table in a
  temporary directory, fake pidfd functions and a fake clock. No real signal
  is sent. A fake pidfd binds, at open time, to the process instance (PID plus
  start time) that holds the PID in the fabricated table; a signal through it
  reaches that instance or raises ProcessLookupError, and never reaches a
  different instance that took over the PID. The PID-addressed `os.kill` is
  replaced by a recorder in every in-process run, and every run asserts that
  it was never called. The hook is loaded from its file path with bytecode
  writing disabled, so no `__pycache__` lands in a distributed plugin
  directory.

Standard library only, per test/README.md.
"""

import ast
import contextlib
import errno
import importlib.util
import inspect
import io
import json
import os
import pty
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_NAME = "codex-hook-tty-reaper.py"
HOOK_PATHS = {
    "em-workflow": REPO_ROOT / "em-workflow" / "scripts" / HOOK_NAME,
    "em-review": REPO_ROOT / "em-review" / "scripts" / HOOK_NAME,
}
HOOK = HOOK_PATHS["em-workflow"]

# A process every real-process test starts ends by itself after this many
# seconds, so a failed test leaves nothing running.
LIFETIME = 20.0
# How long a test waits for a signalled process to disappear, and how long it
# lets a wrongly sent signal land before it calls a process "untouched".
GONE_TIMEOUT = 3.0
SETTLE_SECONDS = 0.2
EVENT_TIMEOUT = 20.0

# Fabricated PIDs start above any PID the kernel hands out (pid_max is at most
# 4194304), so they never collide with the test process or a real process.
FAKE_PID_BASE = 10_000_000


def fake_pid(n):
    return FAKE_PID_BASE + n


def _real_process_skip_reason():
    if not os.path.isdir("/proc") or not os.path.isdir("/proc/self"):
        return "the platform has no /proc"
    try:
        master, slave = pty.openpty()
    except OSError as exc:
        return f"cannot allocate a pseudo-terminal: {exc}"
    os.close(master)
    os.close(slave)
    return None


REAL_PROCESS_SKIP = _real_process_skip_reason()


def load_hook(path=HOOK):
    """The hook as a module of its own, loaded without writing bytecode."""
    spec = importlib.util.spec_from_file_location("codex_hook_tty_reaper_under_test", path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


_NOT_PRESENT = object()


@contextlib.contextmanager
def without_attribute(module, name):
    """MODULE.NAME does not exist inside the block (an interpreter without it).

    An attribute present at entry is removed and the identical object is put
    back on every exit path. An attribute already absent at entry is left
    alone: nothing is deleted on entry and nothing is assigned on exit. An
    exception raised inside the block propagates unchanged."""
    saved = getattr(module, name, _NOT_PRESENT)
    if saved is not _NOT_PRESENT:
        delattr(module, name)
    try:
        yield
    finally:
        if saved is not _NOT_PRESENT:
            setattr(module, name, saved)


def imported_top_level_names(source):
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add("." * node.level + (node.module or "").split(".")[0])
    return names


# --------------------------------------------------------------------------
# Copies (AC-1, TS-2, TS-14)
# --------------------------------------------------------------------------


class TestCopies(unittest.TestCase):
    def test_ac1_both_copies_exist(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                self.assertTrue(path.is_file(), f"{path} is missing")

    def test_ac1_the_two_copies_are_byte_identical(self):
        self.assertEqual(
            HOOK_PATHS["em-workflow"].read_bytes(),
            HOOK_PATHS["em-review"].read_bytes(),
        )

    def test_ac1_each_copy_imports_only_standard_library_modules(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                imported = imported_top_level_names(path.read_text(encoding="utf-8"))
                self.assertTrue(imported, "the hook imports nothing at all")
                self.assertTrue(imported <= set(sys.stdlib_module_names), imported)

    def test_ac1_importing_a_copy_performs_no_action(self):
        # Only definitions at the top level, plus the command-line guard.
        allowed = (
            ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef,
            ast.Assign, ast.AnnAssign,
        )
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            guards = 0
            for index, node in enumerate(tree.body):
                with self.subTest(copy=plugin, statement=index):
                    if (
                        index == 0
                        and isinstance(node, ast.Expr)
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str)
                    ):
                        continue
                    if isinstance(node, ast.If):
                        guards += 1
                        test = ast.unparse(node.test)
                        self.assertIn(test, ('__name__ == "__main__"', "__name__ == '__main__'"))
                        continue
                    self.assertIsInstance(node, allowed, ast.dump(node)[:80])
            with self.subTest(copy=plugin, statement="guard"):
                self.assertEqual(guards, 1)

    def test_ac1_loading_a_copy_leaves_no_bytecode_cache_in_a_plugin_directory(self):
        for plugin, path in HOOK_PATHS.items():
            load_hook(path)
            with self.subTest(copy=plugin):
                self.assertEqual(
                    list(path.parent.glob("__pycache__/codex-hook-tty-reaper*")), []
                )

    def test_nfr6_the_hook_reads_no_environment_variable(self):
        source = HOOK.read_text(encoding="utf-8") if HOOK.is_file() else ""
        self.assertTrue(source, "the hook is missing")
        tree = ast.parse(source)
        attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for forbidden in ("environ", "environb", "getenv", "getenvb", "putenv"):
            self.assertNotIn(forbidden, attributes | names)

    def test_nfr6_the_defaults_of_main_are_the_real_collaborators(self):
        main = load_hook().main
        parameters = inspect.signature(main).parameters
        self.assertEqual(parameters["proc_dir"].default, "/proc")
        # AC-7: the pidfd functions, not the PID-addressed signal function.
        self.assertIs(parameters["pidfd_open"].default, getattr(os, "pidfd_open", None))
        self.assertIs(
            parameters["pidfd_send_signal"].default,
            getattr(signal, "pidfd_send_signal", None),
        )
        self.assertIs(parameters["pidfd_close"].default, os.close)
        self.assertNotIn("send_signal", parameters)
        self.assertNotIn(os.kill, [p.default for p in parameters.values()])
        self.assertIs(parameters["clock"].default, time.monotonic)
        self.assertIs(parameters["sleep"].default, time.sleep)


class TestThisModule(unittest.TestCase):
    def test_ts14_module_imports_are_all_stdlib(self):
        imported = imported_top_level_names(Path(__file__).read_text(encoding="utf-8"))
        self.assertTrue(imported <= set(sys.stdlib_module_names), imported)


# --------------------------------------------------------------------------
# The without_attribute() helper
# (feature-docs/tty-reaper-without-attribute-absent/tasks/task0001.md)
# --------------------------------------------------------------------------

ABSENT = object()


class BlockError(Exception):
    """Raised inside a without_attribute() block; each test raises an instance."""


class RecordingModule(types.ModuleType):
    """A stand-in module that records every attribute deletion and assignment
    as ("del" | "set", attribute name)."""

    def __init__(self, name="recording_stand_in"):
        object.__setattr__(self, "events", [])
        super().__init__(name)

    def __setattr__(self, name, value):
        self.events.append(("set", name))
        super().__setattr__(name, value)

    def __delattr__(self, name):
        self.events.append(("del", name))
        super().__delattr__(name)


class TestWithoutAttribute(unittest.TestCase):
    NAME = "feature"

    def restore_on_cleanup(self, module, name):
        """Put MODULE.NAME back to its present state (object or absence) once the
        test ends, so a failing helper cannot leave a real module altered."""
        original = getattr(module, name, ABSENT)

        def restore():
            if original is ABSENT:
                if hasattr(module, name):
                    delattr(module, name)
            else:
                setattr(module, name, original)

        self.addCleanup(restore)
        return original

    # An attribute absent at entry --------------------------------------

    def test_an_absent_attribute_raises_nothing_and_stays_absent_inside_and_after(self):
        stand_in = types.ModuleType("stand_in")
        with without_attribute(stand_in, self.NAME):
            self.assertFalse(hasattr(stand_in, self.NAME))
        self.assertFalse(hasattr(stand_in, self.NAME))

    def test_an_absent_attribute_is_neither_deleted_nor_assigned(self):
        stand_in = RecordingModule()
        with without_attribute(stand_in, self.NAME):
            pass
        self.assertEqual(stand_in.events, [])
        self.assertFalse(hasattr(stand_in, self.NAME))

    def test_an_exception_over_an_absent_attribute_propagates_and_it_stays_absent(self):
        stand_in = types.ModuleType("stand_in")
        raised = BlockError("raised inside the block")
        with self.assertRaises(BlockError) as caught:
            with without_attribute(stand_in, self.NAME):
                raise raised
        self.assertIs(caught.exception, raised)
        self.assertFalse(hasattr(stand_in, self.NAME))

    # An attribute present at entry -------------------------------------

    def test_a_present_attribute_is_absent_inside_and_the_identical_object_is_back_after(self):
        stand_in = types.ModuleType("stand_in")
        original = object()
        setattr(stand_in, self.NAME, original)
        with without_attribute(stand_in, self.NAME):
            self.assertFalse(hasattr(stand_in, self.NAME))
        self.assertIs(getattr(stand_in, self.NAME), original)

    def test_a_present_attribute_is_restored_and_the_exception_propagates_when_the_block_raises(self):
        stand_in = types.ModuleType("stand_in")
        original = object()
        setattr(stand_in, self.NAME, original)
        raised = BlockError("raised inside the block")
        with self.assertRaises(BlockError) as caught:
            with without_attribute(stand_in, self.NAME):
                self.assertFalse(hasattr(stand_in, self.NAME))
                raise raised
        self.assertIs(caught.exception, raised)
        self.assertIs(getattr(stand_in, self.NAME), original)

    def test_a_present_none_is_an_attribute_that_is_removed_and_put_back(self):
        stand_in = types.ModuleType("stand_in")
        setattr(stand_in, self.NAME, None)
        with without_attribute(stand_in, self.NAME):
            self.assertFalse(hasattr(stand_in, self.NAME))
        self.assertTrue(hasattr(stand_in, self.NAME))
        self.assertIsNone(getattr(stand_in, self.NAME))

    def test_a_present_attribute_is_recorded_as_one_deletion_then_one_assignment(self):
        # The recorder above is what makes "no deletion, no assignment" for an
        # absent attribute a real check: it does see both operations here.
        stand_in = RecordingModule()
        setattr(stand_in, self.NAME, object())
        del stand_in.events[:]
        with without_attribute(stand_in, self.NAME):
            pass
        self.assertEqual(stand_in.events, [("del", self.NAME), ("set", self.NAME)])

    # Nested use on the real modules ------------------------------------

    def assert_nested_use_restores(self, module, name):
        original = self.restore_on_cleanup(module, name)
        with without_attribute(module, name):
            with without_attribute(module, name):
                self.assertFalse(hasattr(module, name))
            self.assertFalse(hasattr(module, name))
        self.assertIs(getattr(module, name, ABSENT), original)

    def test_nested_use_on_os_pidfd_open_restores_the_state_recorded_before_the_outer_block(self):
        self.assert_nested_use_restores(os, "pidfd_open")

    def test_nested_use_on_signal_pidfd_send_signal_restores_the_state_recorded_before_the_outer_block(self):
        self.assert_nested_use_restores(signal, "pidfd_send_signal")

    # The helper's shape ------------------------------------------------

    def test_the_helper_keeps_its_name_and_its_two_parameters(self):
        self.assertEqual(without_attribute.__name__, "without_attribute")
        self.assertEqual(
            list(inspect.signature(without_attribute).parameters), ["module", "name"]
        )


PID_ADDRESSED_SIGNALS ={"kill", "killpg", "pthread_kill", "raise_signal"}


class TestNoPidAddressedSignalling(unittest.TestCase):
    """AC-5: the hook has no PID-addressed signalling path to fall back on."""

    def test_ac5_the_hook_names_no_pid_addressed_signal_function(self):
        for plugin, path in HOOK_PATHS.items():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            referenced = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    referenced.add(node.attr)
                elif isinstance(node, ast.Name):
                    referenced.add(node.id)
                elif isinstance(node, ast.ImportFrom):
                    referenced.update(alias.name for alias in node.names)
            with self.subTest(copy=plugin):
                self.assertEqual(referenced & PID_ADDRESSED_SIGNALS, set())


def docstring_parts(path):
    """(steps, errors): the Flow steps by number and the closing paragraph of
    the module docstring, each as one line of lower-case text."""
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    block, _, errors = doc.split("Flow:\n\n", 1)[1].partition("\n\n")
    steps = {
        int(number): " ".join(text.split()).lower()
        for number, text in re.findall(
            r"^\s*(\d+)\. (.*?)(?=^\s*\d+\. |\Z)", block, re.S | re.M
        )
    }
    return steps, " ".join(errors.split()).lower()


class TestModuleDocstring(unittest.TestCase):
    """AC-8 (FR9): the docstring states the link rule, the pidfd signalling and
    the pidfd-unavailable behaviour."""

    def check(self, text, *phrases):
        for phrase in phrases:
            self.assertIn(phrase, text)

    def test_ac8_the_flow_has_ten_steps_and_a_closing_errors_paragraph(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                steps, errors = docstring_parts(path)
                self.assertEqual(sorted(steps), list(range(1, 11)))
                self.assertTrue(errors)

    def test_ac8_step_4_states_the_start_time_rule_for_the_ancestor_chain(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                steps, _ = docstring_parts(path)
                self.check(steps[4], "ancestor chain", "start-time", "later than", "equal")

    def test_ac8_step_6_states_the_start_time_rule_for_descendants(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                steps, _ = docstring_parts(path)
                self.check(
                    steps[6], "start-time", "snapshot", "started later",
                    "reachable only through", "anchor", "must be in the snapshot",
                )

    def test_ac8_step_8_states_pidfd_opened_before_the_check_and_kept(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                steps, _ = docstring_parts(path)
                self.check(
                    steps[8], "pidfd", "opened", "first", "while the pidfd is held",
                    "through that pidfd", "sigterm",
                )

    def test_ac8_step_10_states_sigkill_through_the_same_pidfd(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                steps, _ = docstring_parts(path)
                self.check(
                    steps[10], "sigkill", "same pidfd", "second pidfd", "closed",
                )

    def test_anchor_identity_the_flow_states_the_anchor_start_time_check(self):
        # The check runs once the snapshot exists, so step 5 describes it; the
        # Flow keeps its ten steps (test_ac8_the_flow_has_ten_steps_...).
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                steps, _ = docstring_parts(path)
                self.check(
                    steps[5], "anchor", "start time", "step 4", "equals", "exactly",
                    "one tick", "stop nothing",
                )

    def test_ac8_the_errors_paragraph_states_the_pidfd_unavailable_behaviour(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                _, errors = docstring_parts(path)
                self.check(
                    errors, "no-such-process", "no further signal", "never sent by pid",
                    "os.pidfd_open", "signal.pidfd_send_signal", "enosys",
                    "nothing is stopped",
                )


# --------------------------------------------------------------------------
# In-process fixtures: a fabricated process table, a fake clock, a recording
# signal sender.
# --------------------------------------------------------------------------


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeTable:
    """A directory shaped like /proc: `<pid>/stat` and `<pid>/fd/0`."""

    def __init__(self, root):
        self.root = Path(root)
        self.entries = {}

    @staticmethod
    def stat_line(pid, ppid, state, start, comm, pgrp, session):
        # 52 fields, as the kernel writes them. `comm` goes in verbatim.
        return (
            f"{pid} ({comm}) {state} {ppid} {pgrp} {session} 0 -1 4194560 "
            + "0 " * 8
            + "20 0 1 0 "
            + f"{start} "
            + " ".join(["0"] * 30)
            + "\n"
        ).encode()

    def add(self, pid, ppid, *, state="S", start=None, stdin=None, comm="proc",
            pgrp=None, session=None):
        if start is None:
            # A child starts after its parent, as on a real machine, so the
            # default tables obey the start-time link rule.
            start = self.entries[ppid]["start"] + 1 if ppid in self.entries else 1001
        self.entries[pid] = {
            "ppid": ppid,
            "state": state,
            "start": start,
            "comm": comm,
            "pgrp": pid if pgrp is None else pgrp,
            "session": pid if session is None else session,
        }
        self._write(pid)
        if stdin is not None:
            link_dir = self.root / str(pid) / "fd"
            link_dir.mkdir(parents=True, exist_ok=True)
            if os.path.lexists(link_dir / "0"):
                os.unlink(link_dir / "0")
            os.symlink(stdin, link_dir / "0")

    def _write(self, pid):
        entry = self.entries[pid]
        directory = self.root / str(pid)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "stat").write_bytes(
            self.stat_line(
                pid, entry["ppid"], entry["state"], entry["start"],
                entry["comm"], entry["pgrp"], entry["session"],
            )
        )

    def change(self, pid, **fields):
        self.entries[pid].update(fields)
        self._write(pid)

    def remove(self, pid):
        shutil.rmtree(self.root / str(pid), ignore_errors=True)

    def holder(self, pid):
        """Start time of the process instance that holds PID now, else None."""
        entry = self.entries.get(pid)
        if entry is None or not (self.root / str(pid)).is_dir():
            return None
        return entry["start"]

    def garble(self, pid, data=b"this is not a stat record\n"):
        (self.root / str(pid) / "stat").write_bytes(data)


class World:
    """A fabricated machine: init, an anchor, a middle process and the hook
    (the test process itself, whose real PID the hook reads).

    It also provides the fake pidfd functions `main()` receives. A pidfd
    binds, when it is opened, to the process instance (PID plus start time)
    that holds the PID in the fabricated table at that moment. A signal sent
    through it is recorded against that instance and that pidfd, or raises
    ProcessLookupError when the instance no longer holds the PID; it never
    reaches a different instance that took the PID over."""

    def __init__(self, case, hook=None):
        self.case = case
        self.dir = Path(case.enterContext(tempfile.TemporaryDirectory()))
        self.table = FakeTable(self.dir)
        self.hook = load_hook() if hook is None else hook
        # The hook reads every stat record through this module-level function;
        # the world watches those reads (and can act right after one).
        self._real_read_stat = self.hook._read_stat
        self.hook._read_stat = self._read_stat
        self.fake_clock = FakeClock()
        # Every signal the fakes delivered: (pid, signum, time). The pid is the
        # PID of the instance the pidfd was bound to.
        self.sent = []
        # The same deliveries with the instance start time and the pidfd used.
        self.deliveries = []
        self.on_send = None
        self.on_sleep = None
        # Called with (pid, signum) inside a pidfd send, before the binding is
        # checked: the instance can change hands "between the check and the
        # signal".
        self.before_send = None
        # Called with (pid, record) right after the hook's stat read of a
        # process returned `record` (None when it could not be read).
        self.on_stat = None
        # Exceptions the fakes raise: {pid: exception} for the open;
        # {pid or (pid, signum): exception} for the send.
        self.open_errors = {}
        self.send_errors = {}
        self.next_pidfd = 900
        self._start_run()
        self.me = os.getpid()
        self.anchor = fake_pid(1)
        self.mid = fake_pid(2)
        self.table.add(1, 0, comm="init")
        self.table.add(self.anchor, 1, stdin="/dev/pts/1", comm="anchor")
        self.table.add(self.mid, self.anchor, stdin="/dev/pts/2", comm="mid")
        self.table.add(self.me, self.mid, stdin="pipe:[1]", comm="hook")
        self.out = ""
        self.err = ""

    # -- the fake pidfd functions -------------------------------------------

    def _no_such_process(self):
        return ProcessLookupError(errno.ESRCH, "No such process")

    def _pidfd_open(self, pid):
        self.open_calls.append(pid)
        self.events.append(("open", pid))
        error = self.open_errors.get(pid)
        if error is not None:
            raise error
        start = self.table.holder(pid)
        if start is None:
            raise self._no_such_process()
        fd = self.next_pidfd
        self.next_pidfd += 1
        self.pidfds[fd] = {"pid": pid, "start": start, "closed": False}
        return fd

    def _pidfd_send_signal(self, fd, signum):
        self.send_calls.append((fd, signum))
        bound = self.pidfds.get(fd)
        if bound is None or bound["closed"]:
            raise OSError(errno.EBADF, "Bad file descriptor")
        pid = bound["pid"]
        self.events.append(("send", pid, signum))
        if self.before_send is not None:
            self.before_send(pid, signum)
        for key in ((pid, signum), pid):
            error = self.send_errors.get(key)
            if error is not None:
                raise error
        if self.table.holder(pid) != bound["start"]:
            raise self._no_such_process()
        self.sent.append((pid, signum, self.fake_clock.now))
        self.deliveries.append(
            {"pid": pid, "start": bound["start"], "fd": fd, "signum": signum}
        )
        if self.on_send is not None:
            self.on_send(pid, signum)

    def _pidfd_close(self, fd):
        self.close_calls.append(fd)
        bound = self.pidfds.get(fd)
        if bound is None or bound["closed"]:
            raise OSError(errno.EBADF, "Bad file descriptor")
        bound["closed"] = True
        self.events.append(("close", bound["pid"]))

    def _sleep(self, seconds):
        self.fake_clock.sleep(seconds)
        if self.on_sleep is not None:
            self.on_sleep()

    def _read_stat(self, proc_dir, pid):
        """The hook's stat read, with a recorder and the `on_stat` callback."""
        record = self._real_read_stat(proc_dir, pid)
        self.stat_reads.append(pid)
        self.events.append(("stat", pid, record))
        if self.on_stat is not None:
            self.on_stat(pid, record)
        return record

    def _start_run(self):
        self.pidfds = {}
        self.open_calls = []
        self.send_calls = []
        self.close_calls = []
        self.kill_calls = []
        self.events = []
        self.stat_reads = []

    # -- running the hook ---------------------------------------------------

    def run(self, argv=None, stdin=b"{}", proc_dir=None, keep_stdin_open=False,
            omit=(), **overrides):
        """Run `main()` once.

        OMIT names seams left out of the call, so the default applies.
        OVERRIDES replace a seam by name (for example `pidfd_open=None`)."""
        argv = [str(self.anchor)] if argv is None else argv
        self._start_run()
        read_end, write_end = os.pipe()

        def feed():
            # A thread: a payload larger than the pipe buffer must not block
            # the test before the hook starts reading.
            try:
                view = memoryview(stdin)
                while view:
                    view = view[os.write(write_end, view):]
            except OSError:
                pass
            finally:
                if not keep_stdin_open:
                    os.close(write_end)

        def pid_addressed_kill(*args):
            self.kill_calls.append(args)

        seams = {
            "pidfd_open": self._pidfd_open,
            "pidfd_send_signal": self._pidfd_send_signal,
            "pidfd_close": self._pidfd_close,
            "clock": self.fake_clock.clock,
            "sleep": self._sleep,
        }
        seams.update(overrides)
        for name in omit:
            del seams[name]
        feeder = threading.Thread(target=feed)
        feeder.start()
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                    mock.patch.object(os, "kill", pid_addressed_kill):
                code = self.hook.main(
                    argv,
                    stdin_fd=read_end,
                    proc_dir=str(self.dir if proc_dir is None else proc_dir),
                    **seams,
                )
        finally:
            os.close(read_end)
            feeder.join()
            if keep_stdin_open:
                os.close(write_end)
        self.out, self.err = out.getvalue(), err.getvalue()
        self.case.assertEqual(code, 0)
        self.case.assertEqual(self.out, "")
        self.case.assertEqual(self.err, "")
        # AC-5: the PID-addressed signal function is never a path.
        self.case.assertEqual(self.kill_calls, [])
        # AC-4: no pidfd the run opened is still open, and none was closed
        # twice or never opened.
        self.case.assertEqual(self.open_pidfds(), [])
        self.case.assertEqual(
            sorted(self.close_calls), sorted(set(self.close_calls)),
            "a pidfd was closed twice",
        )
        # AC-4: no target gets a second pidfd.
        self.case.assertEqual(
            sorted(self.open_calls), sorted(set(self.open_calls)),
            "a target got a second pidfd",
        )
        return code

    # -- what happened ------------------------------------------------------

    def open_pidfds(self):
        return [fd for fd, bound in self.pidfds.items() if not bound["closed"]]

    def terms(self):
        return [pid for pid, signum, _ in self.sent if signum == signal.SIGTERM]

    def kills(self):
        return [pid for pid, signum, _ in self.sent if signum == signal.SIGKILL]

    def signalled(self):
        return {pid for pid, _, _ in self.sent}

    def sequence(self):
        return [(pid, signum) for pid, signum, _ in self.sent]

    def delivered_to(self, pid, start):
        """Signals that reached the instance (PID, START)."""
        return [
            (d["signum"], d["fd"]) for d in self.deliveries
            if d["pid"] == pid and d["start"] == start
        ]

    def pidfds_of(self, pid):
        """The pidfds opened for PID, in the order opened."""
        return [fd for fd, bound in self.pidfds.items() if bound["pid"] == pid]


class InProcessCase(unittest.TestCase):
    def world(self, target=True, hook=None):
        world = World(self, hook=hook)
        self.target = fake_pid(10)
        if target:
            world.table.add(self.target, world.anchor, stdin="/dev/pts/10", comm="target")
        return world


# --------------------------------------------------------------------------
# AC-2, AC-3: which processes are targets, and in what order (in-process)
# --------------------------------------------------------------------------


class TestTargetSelection(InProcessCase):
    def test_ac2_only_descendants_with_a_pts_standard_input_are_signalled(self):
        world = self.world()
        t = self.target
        world.table.add(fake_pid(11), world.anchor, stdin="pipe:[2]")
        world.table.add(fake_pid(12), world.anchor, stdin="/dev/null")
        world.table.add(fake_pid(13), world.anchor)  # standard input unreadable
        world.table.add(fake_pid(14), world.anchor, stdin="/dev/tty")
        world.table.add(fake_pid(15), world.anchor, stdin="/dev/ptsx")
        world.table.add(fake_pid(16), world.anchor, stdin="/tmp/pts/1")
        world.run()
        self.assertEqual(world.terms(), [t])
        self.assertEqual(world.kills(), [t])
        self.assertEqual(world.signalled(), {t})

    def test_ac2_a_descendant_below_a_non_target_is_still_a_target(self):
        world = self.world(target=False)
        world.table.add(fake_pid(20), world.anchor, stdin="pipe:[3]")
        world.table.add(fake_pid(21), fake_pid(20), stdin="/dev/pts/7")
        world.run()
        self.assertEqual(world.terms(), [fake_pid(21)])

    def test_ac2_session_and_process_group_play_no_part(self):
        world = self.world(target=False)
        world.table.add(fake_pid(20), world.anchor, stdin="/dev/pts/7", pgrp=fake_pid(20), session=fake_pid(20))
        world.table.add(fake_pid(21), world.anchor, stdin="/dev/pts/7", pgrp=fake_pid(99), session=fake_pid(98))
        world.run()
        self.assertEqual(sorted(world.terms()), [fake_pid(20), fake_pid(21)])

    def test_ac2_a_descendant_with_children_is_a_target(self):
        world = self.world(target=False)
        world.table.add(fake_pid(20), world.anchor, stdin="/dev/pts/7")
        world.table.add(fake_pid(21), fake_pid(20), stdin="pipe:[4]")
        world.run()
        self.assertEqual(world.terms(), [fake_pid(20)])

    def test_ac2_a_terminal_whose_master_is_gone_still_counts(self):
        world = self.world(target=False)
        world.table.add(fake_pid(20), world.anchor, stdin="/dev/pts/7 (deleted)")
        world.run()
        self.assertEqual(world.terms(), [fake_pid(20)])

    def test_nfr1_a_sibling_of_the_hook_below_the_anchor_is_a_target(self):
        world = self.world(target=False)
        world.table.add(fake_pid(20), world.mid, stdin="/dev/pts/7")
        world.run()
        self.assertEqual(world.terms(), [fake_pid(20)])

    def test_nfr1_outsiders_and_hook_ancestors_with_a_pts_standard_input_are_not_signalled(self):
        world = self.world()
        # A second pseudo-Codex next to the anchor, with descendants.
        parallel = fake_pid(60)
        world.table.add(parallel, 1, stdin="/dev/pts/60")
        world.table.add(fake_pid(61), parallel, stdin="/dev/pts/61")
        world.table.add(fake_pid(62), fake_pid(61), stdin="/dev/pts/62")
        # Further outsiders: a child of init, and one that lost its parent.
        world.table.add(fake_pid(63), 1, stdin="/dev/pts/63")
        world.table.add(fake_pid(64), fake_pid(999), stdin="/dev/pts/64")
        world.run()
        self.assertEqual(world.signalled(), {self.target})
        for pid in (world.anchor, world.mid, world.me, 1, parallel):
            self.assertNotIn(pid, world.signalled())

    def test_ac2_a_zombie_target_receives_no_signal(self):
        world = self.world(target=False)
        world.table.add(fake_pid(20), world.anchor, stdin="/dev/pts/7", state="Z")
        world.table.add(fake_pid(21), world.anchor, stdin="/dev/pts/8")
        world.run()
        self.assertEqual(world.signalled(), {fake_pid(21)})

    def test_nfr6_the_hook_never_signals_itself(self):
        world = self.world()
        world.table.add(world.me, world.mid, stdin="/dev/pts/3")
        world.run()
        self.assertNotIn(world.me, world.signalled())

    def test_ac6_an_unreadable_or_garbled_unrelated_entry_is_left_out(self):
        world = self.world()
        garbled = fake_pid(30)
        world.table.add(garbled, world.anchor, stdin="/dev/pts/30")
        world.table.garble(garbled)
        child_of_garbled = fake_pid(31)
        world.table.add(child_of_garbled, garbled, stdin="/dev/pts/31")
        (world.dir / "self").mkdir()
        (world.dir / "sys").write_text("not a process\n")
        world.run()
        self.assertEqual(world.terms(), [self.target])

    def test_tm4_names_with_spaces_and_parentheses_keep_the_real_parent(self):
        names = ["a b c", "(x)", ") (", "))))", "((", "a\nb", "x) S 1 1 1", ""]
        for name in names:
            with self.subTest(name=name):
                world = self.world(target=False)
                world.table.add(fake_pid(20), world.anchor, stdin="/dev/pts/7", comm=name)
                world.run()
                self.assertEqual(world.terms(), [fake_pid(20)])

    def test_tm4_a_name_imitating_the_anchor_as_parent_does_not_pull_an_outsider_in(self):
        world = self.world()
        forged = f"x) R {world.anchor} 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 5 (y"
        outsider = fake_pid(50)
        world.table.add(outsider, 1, stdin="/dev/pts/9", comm=forged, start=5000)
        world.run()
        self.assertNotIn(outsider, world.signalled())
        self.assertEqual(world.terms(), [self.target])

    def test_tm4_a_name_imitating_an_outside_parent_does_not_hide_a_descendant(self):
        world = self.world(target=False)
        forged = "x) S 1 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 424242 (y"
        descendant = fake_pid(51)
        world.table.add(descendant, world.anchor, stdin="/dev/pts/9", comm=forged, start=5000)
        world.run()
        self.assertEqual(world.terms(), [descendant])
        self.assertEqual(world.kills(), [descendant])

    def test_tm4_a_name_imitating_a_zombie_does_not_hide_a_live_target(self):
        world = self.world(target=False)
        forged = "x) Z 1 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 5 (y"
        descendant = fake_pid(52)
        world.table.add(descendant, world.anchor, stdin="/dev/pts/9", comm=forged, start=5000)
        world.run()
        self.assertEqual(world.terms(), [descendant])


class TestOrder(InProcessCase):
    def build_tree(self, world):
        # depth 1: 30 (target), 40 (target), 41 (not a target)
        # depth 2: 29 (target, child of 30), 31 (not a target, child of 30)
        # depth 3: 28 (target, child of 29), 50 (target, child of 31)
        t = world.table
        t.add(fake_pid(30), world.anchor, stdin="/dev/pts/1")
        t.add(fake_pid(40), world.anchor, stdin="/dev/pts/1")
        t.add(fake_pid(41), world.anchor, stdin="pipe:[5]")
        t.add(fake_pid(29), fake_pid(30), stdin="/dev/pts/1")
        t.add(fake_pid(31), fake_pid(30), stdin="pipe:[6]")
        t.add(fake_pid(28), fake_pid(29), stdin="/dev/pts/1")
        t.add(fake_pid(50), fake_pid(31), stdin="/dev/pts/1")

    def test_ac3_children_are_signalled_before_their_parents_in_both_phases(self):
        world = self.world(target=False)
        self.build_tree(world)
        world.run()
        expected = [fake_pid(n) for n in (28, 50, 29, 30, 40)]
        self.assertEqual(world.terms(), expected)
        self.assertEqual(world.kills(), expected)

    def test_ac3_every_sigterm_precedes_every_sigkill(self):
        world = self.world(target=False)
        self.build_tree(world)
        world.run()
        numbers = [signum for _, signum, _ in world.sent]
        self.assertEqual(numbers, [signal.SIGTERM] * 5 + [signal.SIGKILL] * 5)

    def test_ac3_a_parent_and_child_with_a_pts_standard_input_are_both_stopped(self):
        world = self.world(target=False)
        parent, child = fake_pid(80), fake_pid(70)  # the child has the lower PID
        world.table.add(parent, world.anchor, stdin="/dev/pts/4")
        world.table.add(child, parent, stdin="/dev/pts/4")
        world.run()
        self.assertEqual(world.sequence(), [
            (child, signal.SIGTERM), (parent, signal.SIGTERM),
            (child, signal.SIGKILL), (parent, signal.SIGKILL),
        ])


# --------------------------------------------------------------------------
# AC-4: timing and identity (in-process, fake clock)
# --------------------------------------------------------------------------


class TestTiming(InProcessCase):
    def test_ac4_sigkill_comes_no_earlier_than_half_a_second_after_the_last_sigterm(self):
        world = self.world()
        world.table.add(fake_pid(11), world.anchor, stdin="/dev/pts/1")
        started = world.fake_clock.now
        world.run()
        term_times = [t for _, signum, t in world.sent if signum == signal.SIGTERM]
        kill_times = [t for _, signum, t in world.sent if signum == signal.SIGKILL]
        self.assertEqual(len(term_times), 2)
        self.assertEqual(len(kill_times), 2)
        last_term = max(term_times)
        for kill_time in kill_times:
            self.assertGreaterEqual(kill_time - last_term, 0.5)
        # NFR2: a single bounded wait, not an open-ended one.
        self.assertLess(world.fake_clock.now - started, 0.6)

    def test_ac4_no_sigkill_when_every_target_is_gone_after_sigterm(self):
        world = self.world()
        world.table.add(fake_pid(11), world.anchor, stdin="/dev/pts/1")
        world.on_send = lambda pid, signum: world.table.remove(pid)
        started = world.fake_clock.now
        world.run()
        self.assertEqual(world.kills(), [])
        self.assertLess(world.fake_clock.now - started, 0.5)

    def test_ac4_a_zombie_after_sigterm_counts_as_gone(self):
        world = self.world()
        world.on_send = lambda pid, signum: world.table.change(pid, state="Z")
        world.run()
        self.assertEqual(world.terms(), [self.target])
        self.assertEqual(world.kills(), [])

    def test_ac4_only_the_survivors_of_sigterm_receive_sigkill(self):
        world = self.world()
        stubborn = fake_pid(11)
        world.table.add(stubborn, world.anchor, stdin="/dev/pts/1")
        world.on_send = lambda pid, signum: (
            world.table.remove(pid) if pid == self.target else None
        )
        world.run()
        self.assertEqual(sorted(world.terms()), [self.target, stubborn])
        self.assertEqual(world.kills(), [stubborn])

    def test_ac4_the_wait_ends_as_soon_as_the_last_target_is_gone(self):
        world = self.world()
        started = world.fake_clock.now

        def vanish_after_a_fifth_of_a_second():
            if world.fake_clock.now - started >= 0.2 and self.target in world.table.entries:
                world.table.remove(self.target)
                world.table.entries.pop(self.target)

        world.on_sleep = vanish_after_a_fifth_of_a_second
        world.run()
        self.assertEqual(world.kills(), [])
        self.assertLess(world.fake_clock.now - started, 0.4)

    def test_tm3_a_target_whose_start_time_changed_before_sigterm_gets_no_signal(self):
        world = self.world(target=False)
        first, second = fake_pid(10), fake_pid(11)
        world.table.add(first, world.anchor, stdin="/dev/pts/1")
        world.table.add(second, world.anchor, stdin="/dev/pts/1")
        original = world.table.entries[second]["start"]
        world.on_send = lambda pid, signum: (
            world.table.change(second, start=original + 1)
            if pid == first and signum == signal.SIGTERM else None
        )
        world.run()
        self.assertEqual(world.terms(), [first])
        self.assertEqual(world.kills(), [first])
        self.assertNotIn(second, world.signalled())

    def test_tm3_a_target_whose_start_time_changed_after_sigterm_gets_no_sigkill(self):
        world = self.world(target=False)
        reused, stubborn = fake_pid(10), fake_pid(11)
        world.table.add(reused, world.anchor, stdin="/dev/pts/1")
        world.table.add(stubborn, world.anchor, stdin="/dev/pts/1")
        original = world.table.entries[reused]["start"]
        changed = []

        def reuse_the_pid():
            if not changed:
                world.table.change(reused, start=original + 1)
                changed.append(True)

        world.on_sleep = reuse_the_pid
        world.run()
        self.assertEqual(world.terms(), [reused, stubborn])
        self.assertEqual(world.kills(), [stubborn])

    def test_tm3_a_target_that_vanishes_before_sigterm_gets_no_signal(self):
        world = self.world(target=False)
        first, second = fake_pid(10), fake_pid(11)
        world.table.add(first, world.anchor, stdin="/dev/pts/1")
        world.table.add(second, world.anchor, stdin="/dev/pts/1")
        world.on_send = lambda pid, signum: (
            world.table.remove(second) if pid == first and signum == signal.SIGTERM else None
        )
        world.run()
        self.assertNotIn(second, world.signalled())


# --------------------------------------------------------------------------
# AC-5: the anchor argument (in-process)
# --------------------------------------------------------------------------


class TestAnchorArgument(InProcessCase):
    def arabic_indic(self, number):
        return "".join(chr(0x0660 + int(d)) for d in str(number))

    def fullwidth(self, number):
        return "".join(chr(0xFF10 + int(d)) for d in str(number))

    def test_tm2_the_valid_anchor_stops_the_target(self):
        world = self.world()
        world.run()
        self.assertEqual(world.terms(), [self.target])

    def test_tm2_an_argument_list_or_value_that_is_not_one_valid_anchor_stops_nothing(self):
        world = self.world()
        anchor = str(world.anchor)
        cases = {
            "missing": [],
            "two arguments": [anchor, anchor],
            "two arguments, second empty": [anchor, ""],
            "empty": [""],
            "plus sign": ["+" + anchor],
            "minus sign": ["-" + anchor],
            "leading space": [" " + anchor],
            "trailing space": [anchor + " "],
            "trailing newline": [anchor + "\n"],
            "inner space": [anchor[:3] + " " + anchor[3:]],
            "underscore": [anchor[:3] + "_" + anchor[3:]],
            "hex prefix": [hex(world.anchor)],
            "hex digits": [format(world.anchor, "x")],
            "octal prefix": [oct(world.anchor)],
            "decimal point": [anchor + ".0"],
            "exponent": [anchor + "e0"],
            "arabic-indic digits": [self.arabic_indic(world.anchor)],
            "fullwidth digits": [self.fullwidth(world.anchor)],
            "superscript digits": ["²³"],
            "trailing text": [anchor + "x"],
            "zero": ["0"],
            "one": ["1"],
            "one, padded": ["0001"],
            "one, fullwidth": [self.fullwidth(1)],
            "negative one": ["-1"],
            "the hook itself": [str(world.me)],
            "a process that does not exist": [str(fake_pid(99))],
            "a digit string past the int conversion limit": ["9" * 5000],
        }
        for label, argv in cases.items():
            with self.subTest(case=label):
                fresh = self.world()
                # Something with a terminal below the hook, so that taking the
                # hook itself for the anchor would have a target to stop.
                fresh.table.add(fake_pid(95), fresh.me, stdin="/dev/pts/95")
                fresh.run(argv=argv)
                self.assertEqual(fresh.sent, [])

    def test_tm2_a_process_that_is_not_an_ancestor_of_the_hook_stops_nothing(self):
        world = self.world()
        parallel = fake_pid(60)
        world.table.add(parallel, 1, stdin="/dev/pts/60")
        world.table.add(fake_pid(61), parallel, stdin="/dev/pts/61")
        child_of_hook = fake_pid(62)
        world.table.add(child_of_hook, world.me, stdin="/dev/pts/62")
        for label, anchor in (
            ("a parallel pseudo-Codex", parallel),
            ("a child of the hook", child_of_hook),
            ("a descendant of the anchor off the hook's chain", self.target),
        ):
            with self.subTest(anchor=label):
                world.sent.clear()
                world.run(argv=[str(anchor)])
                self.assertEqual(world.sent, [])

    def test_tm2_the_anchor_itself_and_the_processes_between_it_and_the_hook_are_excluded(self):
        world = self.world()
        world.run()
        for pid in (world.anchor, world.mid, world.me):
            self.assertNotIn(pid, world.signalled())

    def test_tm2_an_anchor_higher_up_the_chain_reaches_the_processes_below_it(self):
        world = self.world(target=False)
        grandparent = fake_pid(3)
        # Re-root the fabricated chain: grandparent -> anchor -> mid -> hook.
        world.table.add(grandparent, 1, stdin="/dev/pts/3")
        world.table.change(world.anchor, ppid=grandparent)
        world.table.add(fake_pid(90), grandparent, stdin="/dev/pts/9")
        world.table.add(fake_pid(91), world.anchor, stdin="/dev/pts/9")
        world.run(argv=[str(grandparent)])
        self.assertEqual(world.signalled(), {fake_pid(90), fake_pid(91)})
        world.sent.clear()
        world.run(argv=[str(world.anchor)])
        self.assertEqual(world.signalled(), {fake_pid(91)})


# --------------------------------------------------------------------------
# AC-6, AC-7: failures, standard input and the process table (in-process)
# --------------------------------------------------------------------------


class TestStandardInput(InProcessCase):
    def test_ac6_standard_input_that_is_not_one_json_object_stops_nothing(self):
        cases = {
            "empty": b"",
            "blank": b"  \n",
            "unterminated object": b"{",
            "not json": b"not json",
            "array": b"[]",
            "array holding an object": b"[{}]",
            "null": b"null",
            "string": b'"{}"',
            "number": b"1",
            "two objects": b"{}{}",
            "trailing garbage": b"{} garbage",
            "not utf-8": b"\xff\xfe{}",
            "not utf-8 inside a value": b'{"a": "\xff"}',
            "nested too deep": b"[" * 100000 + b"]" * 100000,
        }
        for label, payload in cases.items():
            with self.subTest(case=label):
                world = self.world()
                world.run(stdin=payload)
                self.assertEqual(world.sent, [])

    def test_tm5_a_complete_object_on_standard_input_that_is_not_closed_stops_nothing(self):
        world = self.world()
        world.run(stdin=b"{}", keep_stdin_open=True)
        self.assertEqual(world.sent, [])

    def test_ac6_a_json_object_is_enough(self):
        for payload in (b"{}", b'  {"a": 1}\n', b'{"hook_event_name": "Stop"}'):
            with self.subTest(payload=payload):
                world = self.world()
                world.run(stdin=payload)
                self.assertEqual(world.terms(), [self.target])

    def test_tm1_fields_naming_other_processes_or_paths_choose_no_target(self):
        baseline = self.world()
        baseline.run(stdin=b"{}")
        self.assertTrue(baseline.sent)
        outsider = fake_pid(55)
        payloads = [
            {
                "session_id": "s1",
                "transcript_path": "/dev/pts/9",
                "cwd": "/",
                "hook_event_name": "Stop",
                "stop_hook_active": False,
                "last_assistant_message": f"kill {outsider} {fake_pid(1)}",
                "pid": outsider,
                "pids": [outsider, 1, self.target + 1],
                "targets": [outsider],
                "anchor": str(outsider),
                "ppid": outsider,
                "stdin": "/dev/pts/9",
                "proc_dir": "/tmp",
                "signal": 9,
            },
            {"anchor": [str(outsider)], "argv": [str(outsider)], "env": {"PROC": "/tmp"}},
        ]
        for payload in payloads:
            with self.subTest(payload=sorted(payload)):
                world = self.world()
                world.table.add(outsider, 1, stdin="/dev/pts/9")
                world.run(stdin=json.dumps(payload).encode())
                self.assertEqual(world.sequence(), baseline.sequence())


class TestFailures(InProcessCase):
    def test_ac6_a_target_that_ended_after_enumeration_is_not_an_error(self):
        world = self.world(target=False)
        deepest, middle, top = fake_pid(12), fake_pid(11), fake_pid(10)
        world.table.add(top, world.anchor, stdin="/dev/pts/1")
        world.table.add(middle, top, stdin="/dev/pts/1")
        world.table.add(deepest, middle, stdin="/dev/pts/1")

        def first_call_finds_no_process(pid, signum):
            if pid == deepest and signum == signal.SIGTERM:
                raise ProcessLookupError(3, "No such process")

        world.on_send = first_call_finds_no_process
        world.run()
        self.assertEqual(world.terms(), [deepest, middle, top])
        # FR5: the target whose send found no process gets no further signal;
        # the others still do.
        self.assertEqual(world.kills(), [middle, top])

    def test_ac6_no_such_process_while_sending_sigkill_is_not_an_error(self):
        world = self.world(target=False)
        first, second = fake_pid(10), fake_pid(11)
        world.table.add(first, world.anchor, stdin="/dev/pts/1")
        world.table.add(second, world.anchor, stdin="/dev/pts/1")

        def sigkill_finds_no_process(pid, signum):
            if pid == first and signum == signal.SIGKILL:
                raise ProcessLookupError(3, "No such process")

        world.on_send = sigkill_finds_no_process
        world.run()
        self.assertEqual(world.kills(), [first, second])

    def test_ac6_a_signal_error_other_than_no_such_process_stops_further_signals(self):
        for errno_value, exception in ((1, PermissionError), (22, OSError)):
            with self.subTest(exception=exception.__name__):
                world = self.world(target=False)
                for n in (10, 11, 12):
                    world.table.add(fake_pid(n), world.anchor, stdin="/dev/pts/1")

                def fail_on_the_second_call(pid, signum, world=world, e=errno_value, x=exception):
                    if len(world.sent) == 2:
                        raise x(e, "boom")

                world.on_send = fail_on_the_second_call
                world.run()
                self.assertEqual(len(world.sent), 2)

    def test_ac6_a_signal_error_during_the_sigkill_phase_stops_further_signals(self):
        world = self.world(target=False)
        for n in (10, 11, 12):
            world.table.add(fake_pid(n), world.anchor, stdin="/dev/pts/1")

        def fail_on_the_first_sigkill(pid, signum):
            if signum == signal.SIGKILL:
                raise PermissionError(1, "Operation not permitted")

        world.on_send = fail_on_the_first_sigkill
        world.run()
        self.assertEqual(world.terms(), [fake_pid(n) for n in (10, 11, 12)])
        self.assertEqual(len(world.kills()), 1)

    def test_ac6_an_unexpected_error_from_the_clock_stops_further_signals(self):
        world = self.world()
        calls = []

        def broken_sleep(seconds):
            calls.append(seconds)
            raise RuntimeError("boom")

        world._sleep = broken_sleep
        world.run()
        self.assertEqual(world.terms(), [self.target])
        self.assertEqual(world.kills(), [])
        self.assertEqual(len(calls), 1)

    def test_ac6_a_garbled_or_missing_entry_on_the_ancestor_chain_stops_nothing(self):
        def garble_the_middle(world):
            world.table.garble(world.mid)

        def drop_the_middle(world):
            world.table.remove(world.mid)

        def garble_the_hook(world):
            world.table.garble(world.me)

        def garble_init(world):
            world.table.garble(1)

        def drop_init(world):
            world.table.remove(1)

        def garble_the_anchor(world):
            world.table.garble(world.anchor)

        def cut_the_name_field(world):
            world.table.garble(world.mid, f"{world.mid} (mid S {world.anchor}\n".encode())

        def too_few_fields(world):
            world.table.garble(world.mid, f"{world.mid} (mid) S {world.anchor} 1 1\n".encode())

        def non_numeric_parent(world):
            world.table.garble(world.mid, FakeTable.stat_line(
                world.mid, "x", "S", 5, "mid", 1, 1))

        def wrong_pid_in_the_record(world):
            world.table.garble(world.mid, FakeTable.stat_line(
                fake_pid(777), world.anchor, "S", 5, "mid", 1, 1))

        def parent_loop(world):
            world.table.change(world.mid, ppid=world.me)

        cases = {
            "garbled middle": garble_the_middle,
            "missing middle": drop_the_middle,
            "garbled hook entry": garble_the_hook,
            "garbled init": garble_init,
            "missing init": drop_init,
            "garbled anchor": garble_the_anchor,
            "name field not closed": cut_the_name_field,
            "too few fields": too_few_fields,
            "non-numeric parent": non_numeric_parent,
            "record names another PID": wrong_pid_in_the_record,
            "parent loop": parent_loop,
        }
        for label, damage in cases.items():
            with self.subTest(case=label):
                world = self.world()
                damage(world)
                world.run()
                self.assertEqual(world.sent, [])

    def test_ac7_a_missing_process_table_stops_nothing(self):
        world = self.world()
        world.run(proc_dir=world.dir / "no-such-directory")
        self.assertEqual(world.sent, [])

    def test_ac7_a_process_table_without_the_hooks_own_entry_stops_nothing(self):
        world = self.world()
        world.table.remove(world.me)
        world.run()
        self.assertEqual(world.sent, [])

    def test_ac7_an_empty_process_table_stops_nothing(self):
        world = self.world()
        empty = Path(self.enterContext(tempfile.TemporaryDirectory()))
        world.run(proc_dir=empty)
        self.assertEqual(world.sent, [])

    def test_ac7_a_process_table_that_is_a_file_stops_nothing(self):
        world = self.world()
        not_a_directory = world.dir / "plain-file"
        not_a_directory.write_text("x")
        world.run(proc_dir=not_a_directory)
        self.assertEqual(world.sent, [])


# --------------------------------------------------------------------------
# PID reuse: the start-time link rule (AC-1, AC-2)
# --------------------------------------------------------------------------


def start_of(world, pid):
    return world.table.entries[pid]["start"]


class TestLinkRule(InProcessCase):
    """A link from a process to its recorded parent is valid when the parent's
    recorded start time is not later than the process's own (FR1)."""

    def test_ac1_ts1_an_unrelated_process_whose_recorded_parent_was_recreated_later_gets_no_signal(self):
        world = self.world(target=False)
        base = start_of(world, world.anchor)
        parent, unrelated, below = fake_pid(40), fake_pid(41), fake_pid(42)
        # P is a process recreated under the anchor (start base+200). C is an
        # unrelated, older process (start base+100) whose recorded parent is
        # the PID P now holds. D started after C and is C's child.
        world.table.add(parent, world.anchor, stdin="/dev/pts/40", start=base + 200)
        world.table.add(unrelated, parent, stdin="/dev/pts/41", start=base + 100)
        world.table.add(below, unrelated, stdin="/dev/pts/42", start=base + 300)
        world.run()
        self.assertEqual(world.signalled(), {parent})
        self.assertNotIn(unrelated, world.signalled())
        self.assertNotIn(below, world.signalled())

    def test_ac1_ts1_the_same_layout_with_the_child_started_after_its_parent_is_stopped(self):
        # The control: only the start-time order differs from the case above.
        world = self.world(target=False)
        base = start_of(world, world.anchor)
        parent, child, below = fake_pid(40), fake_pid(41), fake_pid(42)
        world.table.add(parent, world.anchor, stdin="/dev/pts/40", start=base + 200)
        world.table.add(child, parent, stdin="/dev/pts/41", start=base + 300)
        world.table.add(below, child, stdin="/dev/pts/42", start=base + 400)
        world.run()
        self.assertEqual(world.signalled(), {parent, child, below})

    def test_ac1_the_boundary_is_one_tick(self):
        for label, offset, stopped in (
            ("parent one tick later", -1, False),
            ("equal start times", 0, True),
            ("parent one tick earlier", 1, True),
        ):
            with self.subTest(case=label):
                world = self.world(target=False)
                base = start_of(world, world.anchor)
                world.table.add(fake_pid(40), world.anchor, stdin="pipe:[8]", start=base + 50)
                world.table.add(fake_pid(41), fake_pid(40), stdin="/dev/pts/41", start=base + 50 + offset)
                world.run()
                self.assertEqual(world.signalled(), {fake_pid(41)} if stopped else set())

    def test_ac1_ts3_a_parent_and_child_with_equal_start_times_under_the_anchor_are_both_stopped(self):
        world = self.world(target=False)
        base = start_of(world, world.anchor)
        parent, child = fake_pid(80), fake_pid(70)
        world.table.add(parent, world.anchor, stdin="/dev/pts/4", start=base + 10)
        world.table.add(child, parent, stdin="/dev/pts/4", start=base + 10)
        world.run()
        self.assertEqual(world.terms(), [child, parent])
        self.assertEqual(world.kills(), [child, parent])

    def test_ac1_ts3_a_child_of_the_anchor_that_started_at_the_same_time_is_stopped(self):
        world = self.world(target=False)
        world.table.add(
            fake_pid(80), world.anchor, stdin="/dev/pts/4", start=start_of(world, world.anchor)
        )
        world.run()
        self.assertEqual(world.terms(), [fake_pid(80)])

    def test_ac1_a_rejected_link_deep_in_the_tree_cuts_only_what_is_below_it(self):
        world = self.world(target=False)
        base = start_of(world, world.anchor)
        top, middle, bottom, below_bottom = (fake_pid(n) for n in (50, 51, 52, 53))
        world.table.add(top, world.anchor, stdin="/dev/pts/5", start=base + 10)
        world.table.add(middle, top, stdin="/dev/pts/5", start=base + 20)
        world.table.add(bottom, middle, stdin="/dev/pts/5", start=base + 15)  # parent later
        world.table.add(below_bottom, bottom, stdin="/dev/pts/5", start=base + 99)
        world.run()
        self.assertEqual(world.terms(), [middle, top])
        self.assertEqual(world.signalled(), {top, middle})

    def test_ac1_a_process_with_a_rejected_link_is_not_a_target_even_when_it_looks_like_one(self):
        world = self.world(target=False)
        base = start_of(world, world.anchor)
        world.table.add(fake_pid(50), world.anchor, stdin="pipe:[9]", start=base + 30)
        world.table.add(fake_pid(51), fake_pid(50), stdin="/dev/pts/9", start=base + 29)
        world.table.add(fake_pid(52), world.anchor, stdin="/dev/pts/9", start=base + 31)
        world.run()
        self.assertEqual(world.signalled(), {fake_pid(52)})

    def test_ac1_an_anchor_missing_from_the_snapshot_stops_nothing(self):
        world = self.world()
        real_snapshot = world.hook._snapshot

        def snapshot_without_the_anchor(proc_dir):
            table = real_snapshot(proc_dir)
            table.pop(world.anchor)
            return table

        world.hook._snapshot = snapshot_without_the_anchor
        world.run()
        self.assertEqual(world.sent, [])
        self.assertEqual(world.open_calls, [])

    def test_ac1_depths_below_adopts_only_valid_links(self):
        hook = load_hook()
        table = {
            1: ("S", 0, 10),
            2: ("S", 1, 20),   # the anchor
            3: ("S", 2, 30),   # parent 20 <= 30: valid, depth 1
            4: ("S", 3, 25),   # parent 30 > 25: rejected
            5: ("S", 4, 99),   # reachable only through the rejected link
            6: ("S", 2, 20),   # equal start times: valid, depth 1
            7: ("S", 6, 21),   # valid, depth 2
            8: ("S", 7, 20),   # parent 21 > 20: rejected, one tick
            9: ("S", 8, 30),   # only through 8
            10: ("S", 1, 5),   # not below the anchor
        }
        self.assertEqual(hook._depths_below(table, 2), {3: 1, 6: 1, 7: 2})

    def test_ac1_depths_below_with_the_anchor_absent_is_empty(self):
        hook = load_hook()
        table = {3: ("S", 2, 30), 4: ("S", 3, 40)}
        self.assertEqual(hook._depths_below(table, 2), {})


def chain_world(case, starts):
    """A world whose chain init -> anchor -> mid -> hook has the start times
    STARTS (a dict by name). The target started after everything else."""
    world = case.world(target=False)
    for name, pid in (
        ("init", 1), ("anchor", world.anchor), ("mid", world.mid), ("hook", world.me),
    ):
        world.table.change(pid, start=starts[name])
    world.table.add(fake_pid(10), world.anchor, stdin="/dev/pts/10", start=9000)
    return world


class TestAncestorChainRule(InProcessCase):
    """The same rule on the hook's ancestor chain; one invalid link stops the
    whole run (FR6)."""

    VALID = {"init": 100, "anchor": 200, "mid": 300, "hook": 400}

    def test_ac2_ts4_the_control_chain_with_ordered_start_times_stops_the_target(self):
        world = chain_world(self, self.VALID)
        world.run()
        self.assertEqual(world.terms(), [fake_pid(10)])

    def test_ac2_ts4_a_chain_with_equal_start_times_stops_the_target(self):
        world = chain_world(self, {"init": 300, "anchor": 300, "mid": 300, "hook": 300})
        world.run()
        self.assertEqual(world.terms(), [fake_pid(10)])
        self.assertEqual(world.kills(), [fake_pid(10)])

    def test_ac2_ts4_one_link_whose_parent_started_later_stops_nothing(self):
        cases = {
            "hook to its parent": {"mid": 500},
            "parent of the hook to the anchor": {"anchor": 500},
            "anchor to init": {"init": 500, "anchor": 200},
            "hook to its parent, one tick": {"mid": 401},
            "anchor to init, one tick": {"init": 201},
        }
        for label, change in cases.items():
            with self.subTest(case=label):
                world = chain_world(self, {**self.VALID, **change})
                world.run()
                self.assertEqual(world.sent, [])
                self.assertEqual(world.open_calls, [])

    def test_ac2_ts4_an_invalid_link_above_the_anchor_stops_nothing(self):
        world = chain_world(self, self.VALID)
        grandparent = fake_pid(3)
        # init -> grandparent -> anchor, with the grandparent started later
        # than the anchor it parents.
        world.table.add(grandparent, 1, stdin="/dev/pts/3", start=250)
        world.table.change(world.anchor, ppid=grandparent)
        world.run()
        self.assertEqual(world.sent, [])

    def test_ac2_ts4_a_valid_link_above_the_anchor_does_not_stop_the_target(self):
        world = chain_world(self, self.VALID)
        grandparent = fake_pid(3)
        world.table.add(grandparent, 1, stdin="/dev/pts/3", start=150)
        world.table.change(world.anchor, ppid=grandparent)
        world.run()
        self.assertEqual(world.terms(), [fake_pid(10)])


# --------------------------------------------------------------------------
# Anchor identity: the anchor of the ancestor-chain read is the anchor of the
# snapshot (feature-docs/codex-hook-tty-reaper-anchor-identity/tasks/
# task0001.md, AC-1 to AC-5)
# --------------------------------------------------------------------------


class TestAnchorIdentity(InProcessCase):
    """The reaper stops anything only when the snapshot holds the anchor PID
    with exactly the start time the ancestor-chain read saw.

    Each test changes the fabricated table after the ancestor-chain read and
    before the snapshot, by wrapping the hook's `_snapshot`: the chain read
    still sees the original anchor."""

    def run_changing_before_the_snapshot(self, world, change):
        """Run the hook; CHANGE runs once, right before the snapshot is taken."""
        calls = []
        real_snapshot = world.hook._snapshot

        def snapshot_after_the_change(proc_dir):
            calls.append(proc_dir)
            change()
            return real_snapshot(proc_dir)

        world.hook._snapshot = snapshot_after_the_change
        code = world.run()
        self.assertEqual(len(calls), 1, "the snapshot was not taken exactly once")
        return code

    def assert_quiet_exit(self, world, code):
        self.assertEqual(code, 0)
        self.assertEqual(world.out, "")
        self.assertEqual(world.err, "")

    def assert_nothing_stopped(self, world):
        self.assertEqual(world.sent, [])
        self.assertEqual(world.open_calls, [])

    def anchor_taken_over(self, world, offset):
        """A callback: the anchor PID is held by a process X that started
        OFFSET ticks after the anchor, and X has a descendant on a terminal
        that started after X. Returns (callback, descendant)."""
        descendant = fake_pid(40)
        x_start = start_of(world, world.anchor) + offset

        def change():
            world.table.change(world.anchor, start=x_start)
            world.table.add(descendant, world.anchor, stdin="/dev/pts/40", start=x_start + 1)

        return change, descendant

    def test_ac1_a_process_that_took_over_the_anchor_pid_stops_nothing(self):
        world = self.world(target=False)
        change, _descendant = self.anchor_taken_over(world, offset=500)
        code = self.run_changing_before_the_snapshot(world, change)
        self.assert_nothing_stopped(world)
        # AC-3: the mismatch path ends quietly with exit code 0.
        self.assert_quiet_exit(world, code)

    def test_ac1_the_same_layout_without_the_takeover_stops_the_descendant(self):
        # The control: the descendant is a real target; only the anchor's
        # start time in the snapshot differs from the test above.
        world = self.world(target=False)
        change, descendant = self.anchor_taken_over(world, offset=0)
        self.run_changing_before_the_snapshot(world, change)
        self.assertEqual(world.terms(), [descendant])
        self.assertEqual(world.kills(), [descendant])

    def test_ac2_a_start_time_that_differs_by_one_tick_stops_nothing(self):
        for label, offset in (("one tick later", 1), ("one tick earlier", -1)):
            with self.subTest(case=label):
                world = self.world(target=False)
                change, _descendant = self.anchor_taken_over(world, offset=offset)
                code = self.run_changing_before_the_snapshot(world, change)
                self.assert_nothing_stopped(world)
                self.assert_quiet_exit(world, code)

    def test_ac3_an_anchor_absent_from_the_snapshot_stops_nothing(self):
        world = self.world()
        descendant = fake_pid(40)

        def change():
            world.table.remove(world.anchor)
            world.table.add(descendant, world.anchor, stdin="/dev/pts/40", start=9000)

        code = self.run_changing_before_the_snapshot(world, change)
        self.assert_nothing_stopped(world)
        self.assert_quiet_exit(world, code)

    def test_ac4_an_anchor_whose_only_change_is_its_parent_is_still_the_anchor(self):
        world = self.world()
        subreaper = fake_pid(3)

        def change():
            world.table.add(subreaper, 1, stdin="pipe:[3]")
            world.table.change(world.anchor, ppid=subreaper)

        self.run_changing_before_the_snapshot(world, change)
        self.assertEqual(world.terms(), [self.target])
        self.assertEqual(world.kills(), [self.target])

    def test_ac5_a_process_between_the_anchor_and_the_hook_that_exited_does_not_matter(self):
        world = self.world()

        def change():
            world.table.remove(world.mid)

        self.run_changing_before_the_snapshot(world, change)
        self.assertEqual(world.terms(), [self.target])
        self.assertEqual(world.kills(), [self.target])


# --------------------------------------------------------------------------
# PID reuse: signalling through a pidfd (AC-3, AC-4)
# --------------------------------------------------------------------------


class TestPidfdSignalling(InProcessCase):
    def test_ac3_the_pidfd_is_opened_just_before_the_check_and_the_signal_follows_the_check(self):
        world = self.world()
        t = self.target
        world.run()
        events = world.events
        sigterm = events.index(("send", t, signal.SIGTERM))
        self.assertEqual(events[sigterm - 2], ("open", t))
        self.assertEqual(events[sigterm - 1][:2], ("stat", t))
        # The pidfd stays open from there on: it closes after the SIGKILL.
        sigkill = events.index(("send", t, signal.SIGKILL))
        self.assertEqual(events[sigkill - 1][:2], ("stat", t))
        self.assertEqual(events.index(("close", t)), len(events) - 1)
        self.assertGreater(events.index(("close", t)), sigkill)

    def test_ac3_signals_go_only_through_the_pidfd_of_the_target(self):
        world = self.world(target=False)
        for n in (10, 11):
            world.table.add(fake_pid(n), world.anchor, stdin="/dev/pts/1")
        world.run()
        self.assertEqual(len(world.deliveries), 4)
        for delivery in world.deliveries:
            self.assertIn(delivery["fd"], world.pidfds_of(delivery["pid"]))

    def test_ac3_ts2_a_pid_that_changes_hands_right_after_the_check_is_never_signalled(self):
        # Reproduction 2: the stat read returns start S for the target, and
        # right after it the PID belongs to a different process (start S+100).
        world = self.world()
        t = self.target
        old = start_of(world, t)
        new = old + 100
        seen = []

        def change_hands_after_the_identity_check(pid, record):
            # Read 1 of the target is the snapshot's; read 2 is the identity
            # check made before the signal.
            if pid == t and world.stat_reads.count(t) == 2:
                seen.append(record)
                world.table.change(t, start=new)

        world.on_stat = change_hands_after_the_identity_check
        world.run()
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][2], old)
        self.assertEqual(world.table.holder(t), new)
        self.assertEqual(world.delivered_to(t, new), [])
        self.assertEqual(world.sent, [])

    def test_ac3_a_pid_that_changes_hands_between_the_sigkill_check_and_the_sigkill_is_not_reached(self):
        world = self.world()
        t = self.target
        old = start_of(world, t)
        new = old + 100

        def change_hands_before_the_sigkill_lands(pid, signum):
            if pid == t and signum == signal.SIGKILL:
                world.table.change(t, start=new)

        world.before_send = change_hands_before_the_sigkill_lands
        world.run()
        self.assertEqual(world.terms(), [t])
        self.assertEqual(world.delivered_to(t, new), [])
        self.assertEqual(world.kills(), [])

    def test_ac3_a_pid_that_changes_hands_between_the_snapshot_and_the_open_gets_no_signal(self):
        world = self.world()
        t = self.target
        new = start_of(world, t) + 100
        world.on_stat = lambda pid, record: (
            world.table.change(t, start=new)
            if pid == t and world.stat_reads.count(t) == 1 else None
        )
        world.run()
        self.assertEqual(world.table.holder(t), new)
        self.assertEqual(world.sent, [])
        # The pidfd was opened (it points at the new holder) and closed again.
        self.assertEqual(len(world.pidfds_of(t)), 1)

    def test_ac3_a_target_that_fails_the_check_gets_no_signal_then_or_later_and_its_pidfd_is_closed(self):
        world = self.world(target=False)
        first, second = fake_pid(10), fake_pid(11)
        world.table.add(first, world.anchor, stdin="/dev/pts/1")
        world.table.add(second, world.anchor, stdin="/dev/pts/1")
        world.on_stat = lambda pid, record: (
            world.table.change(first, state="Z")
            if pid == first and world.stat_reads.count(first) == 1 else None
        )
        world.run()
        self.assertEqual(world.signalled(), {second})
        self.assertEqual(len(world.pidfds_of(first)), 1)
        # Its pidfd was closed before the second target's was even opened.
        self.assertLess(
            world.events.index(("close", first)), world.events.index(("open", second))
        )

    def test_ac3_a_target_that_vanishes_between_the_snapshot_and_the_open_is_skipped(self):
        world = self.world(target=False)
        first, second = fake_pid(10), fake_pid(11)
        world.table.add(first, world.anchor, stdin="/dev/pts/1")
        world.table.add(second, world.anchor, stdin="/dev/pts/1")
        world.on_stat = lambda pid, record: (
            world.table.remove(first)
            if pid == first and world.stat_reads.count(first) == 1 else None
        )
        world.run()
        self.assertEqual(world.signalled(), {second})
        self.assertEqual(world.pidfds_of(first), [])

    def test_ac4_ts7_sigkill_goes_through_the_pidfd_that_carried_the_sigterm(self):
        world = self.world(target=False)
        for n in (10, 11, 12):
            world.table.add(fake_pid(n), world.anchor, stdin="/dev/pts/1")
        world.run()
        for n in (10, 11, 12):
            with self.subTest(target=n):
                pid = fake_pid(n)
                pidfds = world.pidfds_of(pid)
                self.assertEqual(len(pidfds), 1)
                carried = [
                    (d["signum"], d["fd"]) for d in world.deliveries if d["pid"] == pid
                ]
                self.assertEqual(
                    carried,
                    [(signal.SIGTERM, pidfds[0]), (signal.SIGKILL, pidfds[0])],
                )

    def test_ac4_the_sigkill_follows_a_check_made_while_the_pidfd_is_held(self):
        world = self.world(target=False)
        a, b = fake_pid(10), fake_pid(11)
        world.table.add(a, world.anchor, stdin="/dev/pts/1")
        world.table.add(b, world.anchor, stdin="/dev/pts/1")
        world.run()
        events = world.events
        for pid in (a, b):
            with self.subTest(target=pid):
                kill = events.index(("send", pid, signal.SIGKILL))
                self.assertEqual(events[kill - 1][:2], ("stat", pid))
                self.assertLess(events.index(("open", pid)), kill)
                self.assertGreater(events.index(("close", pid)), kill)

    def test_ac4_a_target_that_is_a_zombie_at_the_sigkill_check_gets_no_sigkill(self):
        world = self.world(target=False)
        fading, stubborn = fake_pid(10), fake_pid(11)
        world.table.add(fading, world.anchor, stdin="/dev/pts/1")
        world.table.add(stubborn, world.anchor, stdin="/dev/pts/1")
        world.on_send = lambda pid, signum: (
            world.table.change(fading, state="Z") if pid == fading else None
        )
        world.run()
        self.assertEqual(world.terms(), [fading, stubborn])
        self.assertEqual(world.kills(), [stubborn])

    def test_ac4_all_pidfds_are_closed_when_main_returns_on_the_success_path(self):
        world = self.world(target=False)
        for n in (10, 11, 12):
            world.table.add(fake_pid(n), world.anchor, stdin="/dev/pts/1")
        world.run()
        self.assertEqual(len(world.pidfds), 3)
        self.assertEqual(world.open_pidfds(), [])

    def test_ac4_all_pidfds_are_closed_when_every_target_is_gone_after_the_sigterm(self):
        world = self.world(target=False)
        for n in (10, 11):
            world.table.add(fake_pid(n), world.anchor, stdin="/dev/pts/1")
        world.on_send = lambda pid, signum: world.table.remove(pid)
        world.run()
        self.assertEqual(world.kills(), [])
        self.assertEqual(len(world.pidfds), 2)
        self.assertEqual(world.open_pidfds(), [])

    def test_ac4_all_pidfds_are_closed_when_the_clock_fails_between_the_phases(self):
        world = self.world()

        def broken_sleep(seconds):
            raise RuntimeError("boom")

        world._sleep = broken_sleep
        world.run()
        self.assertEqual(world.kills(), [])
        self.assertEqual(len(world.pidfds), 1)
        self.assertEqual(world.open_pidfds(), [])

    def test_ac4_the_fake_pidfd_binds_to_the_instance_holding_the_pid_at_open_time(self):
        world = self.world()
        t = self.target
        first = start_of(world, t)
        fd_old = world._pidfd_open(t)
        world.table.change(t, start=first + 100)
        fd_new = world._pidfd_open(t)
        with self.assertRaises(ProcessLookupError):
            world._pidfd_send_signal(fd_old, signal.SIGTERM)
        world._pidfd_send_signal(fd_new, signal.SIGTERM)
        self.assertEqual(world.delivered_to(t, first), [])
        self.assertEqual(world.delivered_to(t, first + 100), [(signal.SIGTERM, fd_new)])
        world.table.remove(t)
        with self.assertRaises(ProcessLookupError):
            world._pidfd_open(t)
        with self.assertRaises(ProcessLookupError):
            world._pidfd_send_signal(fd_new, signal.SIGKILL)
        world._pidfd_close(fd_old)
        world._pidfd_close(fd_new)
        self.assertEqual(world.open_pidfds(), [])
        with self.assertRaises(OSError):
            world._pidfd_send_signal(fd_new, signal.SIGKILL)


# --------------------------------------------------------------------------
# PID reuse: pidfd unavailable (AC-5)
# --------------------------------------------------------------------------


class TestPidfdUnavailable(InProcessCase):
    def assert_nothing_stopped(self, world):
        self.assertEqual(world.sent, [])
        self.assertEqual(world.deliveries, [])
        self.assertEqual(world.kill_calls, [])

    def test_ac5_ts5_a_pidfd_open_seam_set_to_none_stops_nothing(self):
        world = self.world()
        world.run(pidfd_open=None)
        self.assert_nothing_stopped(world)
        self.assertEqual(world.open_calls, [])

    def test_ac5_ts5_a_pidfd_send_seam_set_to_none_stops_nothing(self):
        world = self.world()
        world.run(pidfd_send_signal=None)
        self.assert_nothing_stopped(world)
        # Nothing was even opened: no pidfd is left to close, no PID path.
        self.assertEqual(world.open_calls, [])

    def test_ac5_a_pidfd_close_seam_set_to_none_stops_nothing(self):
        world = self.world()
        world.run(pidfd_close=None)
        self.assert_nothing_stopped(world)
        self.assertEqual(world.open_calls, [])

    def test_ac5_ts5_a_pidfd_open_that_raises_enosys_stops_nothing(self):
        world = self.world()
        world.open_errors[self.target] = OSError(errno.ENOSYS, "Function not implemented")
        world.run()
        self.assert_nothing_stopped(world)

    def test_ac5_ts5_a_missing_pidfd_open_function_leaves_a_default_that_stops_nothing(self):
        with without_attribute(os, "pidfd_open"):
            hook = load_hook()
        self.assertIsNone(inspect.signature(hook.main).parameters["pidfd_open"].default)
        world = self.world(hook=hook)
        world.run(omit=("pidfd_open",))
        self.assert_nothing_stopped(world)
        self.assertEqual(world.open_calls, [])

    def test_ac5_ts5_a_missing_pidfd_send_signal_function_leaves_a_default_that_stops_nothing(self):
        with without_attribute(signal, "pidfd_send_signal"):
            hook = load_hook()
        self.assertIsNone(
            inspect.signature(hook.main).parameters["pidfd_send_signal"].default
        )
        world = self.world(hook=hook)
        world.run(omit=("pidfd_send_signal",))
        self.assert_nothing_stopped(world)
        self.assertEqual(world.open_calls, [])

    def test_ac5_the_pid_addressed_signal_function_is_never_a_fallback(self):
        # Every in-process run replaces os.kill with a recorder and asserts it
        # was not called; this case spells that out for the unavailable paths.
        for label, overrides in (
            ("open is None", {"pidfd_open": None}),
            ("send is None", {"pidfd_send_signal": None}),
            ("both are None", {"pidfd_open": None, "pidfd_send_signal": None}),
        ):
            with self.subTest(case=label):
                world = self.world()
                world.run(**overrides)
                self.assertEqual(world.kill_calls, [])
                self.assertEqual(world.sent, [])


# --------------------------------------------------------------------------
# PID reuse: errors while using a pidfd (AC-6)
# --------------------------------------------------------------------------


class TestPidfdErrors(InProcessCase):
    def three(self):
        world = self.world(target=False)
        self.first, self.second, self.third = (fake_pid(n) for n in (10, 11, 12))
        for pid in (self.first, self.second, self.third):
            world.table.add(pid, world.anchor, stdin="/dev/pts/1")
        return world

    def no_such_process(self):
        return ProcessLookupError(errno.ESRCH, "No such process")

    def test_ac6_ts6_no_such_process_at_open_skips_that_target_only(self):
        world = self.three()
        world.open_errors[self.second] = self.no_such_process()
        world.run()
        self.assertEqual(world.terms(), [self.first, self.third])
        self.assertEqual(world.kills(), [self.first, self.third])
        self.assertEqual(world.open_calls, [self.first, self.second, self.third])

    def test_ac6_ts6_no_such_process_at_the_sigterm_send_skips_that_target_only(self):
        world = self.three()
        world.send_errors[(self.second, signal.SIGTERM)] = self.no_such_process()
        world.run()
        self.assertEqual(world.terms(), [self.first, self.third])
        self.assertEqual(world.kills(), [self.first, self.third])
        # Its pidfd was opened and is closed.
        self.assertEqual(len(world.pidfds_of(self.second)), 1)

    def test_ac6_ts6_no_such_process_at_the_sigkill_send_skips_that_target_only(self):
        world = self.three()
        world.send_errors[(self.first, signal.SIGKILL)] = self.no_such_process()
        world.run()
        self.assertEqual(world.terms(), [self.first, self.second, self.third])
        self.assertEqual(world.kills(), [self.second, self.third])

    def test_ac6_ts6_no_such_process_for_every_target_is_not_an_error(self):
        world = self.three()
        for pid in (self.first, self.second, self.third):
            world.open_errors[pid] = self.no_such_process()
        world.run()
        self.assertEqual(world.sent, [])
        self.assertEqual(world.open_calls, [self.first, self.second, self.third])

    def test_ac6_ts6_emfile_at_open_ends_all_signalling_the_sigkill_phase_included(self):
        world = self.three()
        world.open_errors[self.second] = OSError(errno.EMFILE, "Too many open files")
        world.run()
        # The first target got its SIGTERM and then nothing; the third was not
        # even opened.
        self.assertEqual(world.sequence(), [(self.first, signal.SIGTERM)])
        self.assertEqual(world.open_calls, [self.first, self.second])
        self.assertEqual(len(world.pidfds), 1)

    def test_ac6_emfile_at_the_first_open_sends_nothing(self):
        world = self.three()
        world.open_errors[self.first] = OSError(errno.EMFILE, "Too many open files")
        world.run()
        self.assertEqual(world.sent, [])
        self.assertEqual(world.open_calls, [self.first])

    def test_ac6_enosys_at_a_later_open_ends_all_signalling(self):
        world = self.three()
        world.open_errors[self.third] = OSError(errno.ENOSYS, "Function not implemented")
        world.run()
        self.assertEqual(
            world.sequence(),
            [(self.first, signal.SIGTERM), (self.second, signal.SIGTERM)],
        )

    def test_ac6_ts6_permission_error_at_the_sigterm_send_ends_all_signalling(self):
        world = self.three()
        world.send_errors[(self.second, signal.SIGTERM)] = PermissionError(
            errno.EPERM, "Operation not permitted"
        )
        world.run()
        self.assertEqual(world.sequence(), [(self.first, signal.SIGTERM)])
        self.assertEqual(world.open_calls, [self.first, self.second])

    def test_ac6_ts6_permission_error_at_the_sigkill_send_ends_all_signalling(self):
        world = self.three()
        world.send_errors[(self.second, signal.SIGKILL)] = PermissionError(
            errno.EPERM, "Operation not permitted"
        )
        world.run()
        self.assertEqual(world.terms(), [self.first, self.second, self.third])
        self.assertEqual(world.kills(), [self.first])

    def test_ac6_other_errors_at_open_or_send_end_all_signalling(self):
        for label, error in (
            ("EINVAL", OSError(errno.EINVAL, "Invalid argument")),
            ("EBADF", OSError(errno.EBADF, "Bad file descriptor")),
            ("not an OSError", RuntimeError("boom")),
        ):
            with self.subTest(error=label, where="open"):
                world = self.three()
                world.open_errors[self.second] = error
                world.run()
                self.assertEqual(world.sequence(), [(self.first, signal.SIGTERM)])
            with self.subTest(error=label, where="send"):
                world = self.three()
                world.send_errors[(self.second, signal.SIGTERM)] = error
                world.run()
                self.assertEqual(world.sequence(), [(self.first, signal.SIGTERM)])

    def test_ac6_every_error_path_closes_every_pidfd_it_opened(self):
        # World.run asserts it for each run; this case makes sure the paths
        # above really held pidfds when the error hit.
        world = self.three()
        world.send_errors[(self.third, signal.SIGKILL)] = PermissionError(
            errno.EPERM, "Operation not permitted"
        )
        world.run()
        self.assertEqual(len(world.pidfds), 3)
        self.assertEqual(world.open_pidfds(), [])


# --------------------------------------------------------------------------
# Real processes (TS-3 to TS-8, TS-13, TS-15)
# --------------------------------------------------------------------------

# The pseudo-Codex: runs as `python -c`. Its standard input is a
# pseudo-terminal. It forks the descendants the spec names, waits until each
# is set up (so the hook never sees a half-built process), then runs the hook
# as a descendant of the process the spec names, and reports on stdout. Every
# process it starts ends when the control pipe closes or after LIFETIME.
PSEUDO_CODEX_SOURCE = r'''
import json
import os
import select
import signal
import subprocess
import sys
import time

SPEC = json.loads(sys.argv[1])
HOOK = sys.argv[2]
CONTROL = int(sys.argv[3])
LIFETIME = float(sys.argv[4])
START = time.monotonic()
ROOT = os.getpid()
PTY = os.dup(0)
READY_R, READY_W = os.pipe()
GO_R, GO_W = os.pipe()


def emit(event):
    os.write(1, (json.dumps(event) + "\n").encode())


def count(node):
    return 1 + sum(count(child) for child in node.get("children", []))


def find_holder(node):
    if node.get("hook") is not None:
        return node
    for child in node.get("children", []):
        found = find_holder(child)
        if found is not None:
            return found
    return None


def lingering():
    while time.monotonic() - START < LIFETIME:
        readable, _, _ = select.select([CONTROL], [], [], 0.2)
        if readable and not os.read(CONTROL, 1):
            break
    os._exit(0)


def expand(argument):
    arabic = "".join(chr(0x0660 + int(d)) for d in str(ROOT))
    return (
        argument.replace("$ROOT_ARABIC", arabic)
        .replace("$ROOT_HEX", "0x%x" % ROOT)
        .replace("$ROOT", str(ROOT))
    )


def run_hooks(runs):
    results = []
    for run in runs:
        began = time.monotonic()
        proc = subprocess.Popen(
            [sys.executable, HOOK] + [expand(a) for a in run["args"]],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            proc.stdin.write(bytes.fromhex(run["stdin_hex"]))
            proc.stdin.flush()
            if not run.get("stdin_open"):
                proc.stdin.close()
        except OSError:
            pass
        try:
            code = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            code = None
        elapsed = time.monotonic() - began
        out = proc.stdout.read()
        err = proc.stderr.read()
        try:
            proc.stdin.close()
        except OSError:
            pass
        results.append({
            "code": code,
            "stdout": out.decode("latin-1"),
            "stderr": err.decode("latin-1"),
            "elapsed": elapsed,
        })
    emit({"event": "hook", "runs": results})


def run_node(node):
    if node["stdin"] == "pty":
        os.dup2(PTY, 0)
    else:
        read_end, _write_end = os.pipe()  # the write end stays open: no EOF
        os.dup2(read_end, 0)
    if node.get("session"):
        os.setsid()
    if node.get("ignore_term"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.write(READY_W, (json.dumps({"name": node["name"], "pid": os.getpid()}) + "\n").encode())
    for child in node.get("children", []):
        spawn(child)
    if node.get("hook") is not None:
        os.read(GO_R, 1)
        run_hooks(node["hook"])
    lingering()


def spawn(node):
    pid = os.fork()
    if pid == 0:
        try:
            run_node(node)
        finally:
            os._exit(0)
    return pid


pids = {"root": ROOT}
for child in SPEC.get("children", []):
    spawn(child)
total = count(SPEC)
buffer = b""
deadline = time.monotonic() + 15
while len(pids) < total:
    readable, _, _ = select.select([READY_R], [], [], max(0.0, deadline - time.monotonic()))
    if not readable:
        emit({"event": "error", "message": "tree not ready", "pids": pids})
        os._exit(1)
    buffer += os.read(READY_R, 65536)
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        entry = json.loads(line)
        pids[entry["name"]] = entry["pid"]
emit({"event": "tree", "pids": pids})
holder = find_holder(SPEC)
if holder is SPEC:
    run_hooks(SPEC["hook"])
elif holder is not None:
    os.write(GO_W, b"g")
lingering()
'''


def process_state(pid):
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    return data[data.rindex(b")") + 2:data.rindex(b")") + 3].decode()


def is_alive(pid):
    state = process_state(pid)
    return state is not None and state not in ("Z", "X", "x")


def wait_until_gone(pid, timeout=GONE_TIMEOUT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_alive(pid):
            return True
        time.sleep(0.02)
    return not is_alive(pid)


def node(name, stdin="pty", children=(), hook=None, **flags):
    spec = {"name": name, "stdin": stdin, "children": list(children)}
    spec.update(flags)
    if hook is not None:
        spec["hook"] = hook
    return spec


def hook_run(args=("$ROOT",), stdin=b"{}", stdin_open=False):
    return {"args": list(args), "stdin_hex": stdin.hex(), "stdin_open": stdin_open}


def root(children=(), hook=None):
    return node("root", "pty", children, hook=hook)


class PseudoCodex:
    """One pseudo-Codex process the test started, with its descendants."""

    def __init__(self, spec, hook_path=HOOK):
        self.spec = spec
        self.hook_path = hook_path
        self.events = {}
        self.buffer = b""
        self.closed = False
        self.master, slave = pty.openpty()
        control_read, self.control_write = os.pipe()
        self.stderr = tempfile.TemporaryFile()
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-c", PSEUDO_CODEX_SOURCE, json.dumps(spec),
                 str(hook_path), str(control_read), str(LIFETIME)],
                stdin=slave, stdout=subprocess.PIPE, stderr=self.stderr,
                pass_fds=(control_read,),
            )
        finally:
            os.close(slave)
            os.close(control_read)
        self.pid = self.proc.pid

    def wait_for(self, kind, timeout=EVENT_TIMEOUT):
        deadline = time.monotonic() + timeout
        descriptor = self.proc.stdout.fileno()
        while kind not in self.events:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"no {kind!r} event from the pseudo-Codex: {self.diagnostics()}")
            readable, _, _ = select.select([descriptor], [], [], remaining)
            if not readable:
                continue
            chunk = os.read(descriptor, 65536)
            if not chunk:
                raise AssertionError(f"the pseudo-Codex ended early: {self.diagnostics()}")
            self.buffer += chunk
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                event = json.loads(line)
                self.events[event["event"]] = event
                if event["event"] == "error":
                    raise AssertionError(f"pseudo-Codex error: {event}")
        return self.events[kind]

    def pids(self):
        return self.wait_for("tree")["pids"]

    def runs(self):
        return self.wait_for("hook")["runs"]

    def diagnostics(self):
        self.stderr.seek(0)
        return self.stderr.read().decode("utf-8", "replace")

    def close(self):
        if self.closed:
            return
        self.closed = True
        os.close(self.control_write)
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.proc.stdout.close()
        os.close(self.master)
        self.stderr.close()


@unittest.skipIf(REAL_PROCESS_SKIP is not None, REAL_PROCESS_SKIP or "")
class RealProcessCase(unittest.TestCase):
    def start(self, spec, hook_path=HOOK):
        codex = PseudoCodex(spec, hook_path)
        self.addCleanup(codex.close)
        return codex

    def settle(self):
        time.sleep(SETTLE_SECONDS)

    def assert_gone(self, pids, *names):
        for name in names:
            self.assertTrue(
                wait_until_gone(pids[name]),
                f"{name} (pid {pids[name]}) is still alive",
            )

    def assert_alive(self, pids, *names):
        for name in names:
            self.assertTrue(
                is_alive(pids[name]),
                f"{name} (pid {pids[name]}) was stopped, state {process_state(pids[name])}",
            )

    def assert_quiet(self, run, time_bound=3.0):
        self.assertEqual(run["code"], 0, run)
        self.assertEqual(run["stdout"], "", run)
        self.assertEqual(run["stderr"], "", run)
        self.assertLess(run["elapsed"], time_bound, run)


class TestRealTargets(RealProcessCase):
    def test_ac2_terminal_descendants_are_stopped_and_pipe_descendants_remain(self):
        for plugin, path in HOOK_PATHS.items():
            with self.subTest(copy=plugin):
                codex = self.start(root([
                    node("parent", "pty", [node("child", "pty"), node("pipe_child", "pipe")]),
                    node("detached", "pty", session=True),
                    node("pipe_background", "pipe", session=True),
                    node("pipe_plain", "pipe"),
                ], hook=[hook_run()]), hook_path=path)
                pids = codex.pids()
                self.assert_quiet(codex.runs()[0])
                self.assert_gone(pids, "parent", "child", "detached")
                self.settle()
                self.assert_alive(pids, "pipe_child", "pipe_background", "pipe_plain", "root")

    def test_ac3_a_pty_chain_of_three_generations_is_stopped(self):
        codex = self.start(root([
            node("parent", "pty", [node("child", "pty", [node("grandchild", "pty")])]),
        ], hook=[hook_run()]))
        pids = codex.pids()
        self.assert_quiet(codex.runs()[0])
        self.assert_gone(pids, "parent", "child", "grandchild")
        self.assert_alive(pids, "root")

    def test_ac3_a_terminal_process_below_a_pipe_process_is_stopped(self):
        codex = self.start(root([
            node("pipe_parent", "pipe", [node("pty_child", "pty")]),
        ], hook=[hook_run()]))
        pids = codex.pids()
        self.assert_quiet(codex.runs()[0])
        self.assert_gone(pids, "pty_child")
        self.settle()
        self.assert_alive(pids, "pipe_parent")

    def test_ts13_a_detached_background_process_with_a_terminal_is_stopped_like_any_other(self):
        codex = self.start(root([
            node("detached_pty", "pty", session=True),
            node("detached_pipe", "pipe", session=True),
        ], hook=[hook_run()]))
        pids = codex.pids()
        self.assert_quiet(codex.runs()[0])
        self.assert_gone(pids, "detached_pty")
        self.settle()
        self.assert_alive(pids, "detached_pipe")

    def test_ac4_a_process_that_ignores_sigterm_is_gone_when_the_hook_exits(self):
        codex = self.start(root([
            node("stubborn", "pty", ignore_term=True),
            node("polite", "pty"),
        ], hook=[hook_run()]))
        pids = codex.pids()
        run = codex.runs()[0]
        self.assert_quiet(run, time_bound=3.0)
        # The stubborn process survived SIGTERM, so the hook waited the full
        # half second before SIGKILL: it was not sent earlier.
        self.assertGreaterEqual(run["elapsed"], 0.45)
        self.assert_gone(pids, "stubborn", "polite")
        self.assert_alive(pids, "root")

    def test_ac4_with_no_stubborn_target_the_hook_does_not_wait_the_half_second(self):
        codex = self.start(root([node("polite", "pty")], hook=[hook_run()]))
        pids = codex.pids()
        run = codex.runs()[0]
        self.assert_quiet(run)
        self.assert_gone(pids, "polite")


class TestRealBoundaries(RealProcessCase):
    def test_ac5_outsiders_and_the_hooks_ancestors_with_a_terminal_are_not_signalled(self):
        parallel = self.start(root([
            node("p_child", "pty", [node("p_grandchild", "pty")]),
            node("p_detached", "pty", session=True),
            node("p_pipe", "pipe"),
        ]))
        parallel_pids = parallel.pids()
        main = self.start(root([
            node("mid", "pty", [node("mid_child", "pty")], hook=[hook_run()]),
            node("target", "pty"),
        ]))
        pids = main.pids()
        self.assert_quiet(main.runs()[0])
        # The hook was effective: the targets below the anchor are gone.
        self.assert_gone(pids, "target", "mid_child")
        self.settle()
        # The anchor and the process between the anchor and the hook, both
        # with a pseudo-terminal as standard input, were left alone.
        self.assert_alive(pids, "root", "mid")
        self.assert_alive(parallel_pids, "root", "p_child", "p_grandchild", "p_detached", "p_pipe")

    def test_ac5_a_parallel_pseudo_codex_named_as_the_anchor_stops_nothing(self):
        parallel = self.start(root([node("p_child", "pty")]))
        parallel_pids = parallel.pids()
        main = self.start(root(
            [node("target", "pty"), node("pipe_child", "pipe")],
            hook=[hook_run(args=[str(parallel.pid)])],
        ))
        pids = main.pids()
        self.assert_quiet(main.runs()[0])
        self.settle()
        self.assert_alive(pids, "root", "target", "pipe_child")
        self.assert_alive(parallel_pids, "root", "p_child")

    def test_ac5_an_argument_that_is_not_exactly_one_ascii_decimal_anchor_stops_nothing(self):
        runs = [
            hook_run(args=[]),
            hook_run(args=["$ROOT", "$ROOT"]),
            hook_run(args=["+$ROOT"]),
            hook_run(args=[" $ROOT"]),
            hook_run(args=["$ROOT "]),
            hook_run(args=["$ROOT_HEX"]),
            hook_run(args=["$ROOT_ARABIC"]),
            hook_run(args=[""]),
        ]
        codex = self.start(root([node("target", "pty"), node("deep", "pty", [node("deeper", "pty")])],
                                hook=runs))
        pids = codex.pids()
        results = codex.runs()
        self.assertEqual(len(results), len(runs))
        for index, result in enumerate(results):
            with self.subTest(run=index, args=runs[index]["args"]):
                self.assert_quiet(result)
        self.settle()
        self.assert_alive(pids, "root", "target", "deep", "deeper")

    def test_ac6_standard_input_that_is_not_one_json_object_stops_nothing(self):
        runs = [
            hook_run(stdin=b""),
            hook_run(stdin=b"not json"),
            hook_run(stdin=b"[]"),
            hook_run(stdin=b"\xff\xfe{}"),
            hook_run(stdin=b'{"a": '),
        ]
        codex = self.start(root([node("target", "pty")], hook=runs))
        pids = codex.pids()
        results = codex.runs()
        self.assertEqual(len(results), len(runs))
        for index, result in enumerate(results):
            with self.subTest(run=index):
                self.assert_quiet(result)
        self.settle()
        self.assert_alive(pids, "root", "target")

    def test_ac6_standard_input_kept_open_stops_nothing_and_the_hook_exits_in_time(self):
        codex = self.start(root([node("target", "pty")], hook=[hook_run(stdin_open=True)]))
        pids = codex.pids()
        run = codex.runs()[0]
        self.assert_quiet(run, time_bound=3.0)
        self.settle()
        self.assert_alive(pids, "root", "target")

    def test_tm1_a_json_object_naming_other_processes_changes_no_target(self):
        codex_outsider = self.start(root([node("p_child", "pty")]))
        outsider_pids = codex_outsider.pids()
        naming = json.dumps({
            "pid": outsider_pids["p_child"],
            "pids": [codex_outsider.pid, outsider_pids["p_child"]],
            "anchor": str(codex_outsider.pid),
            "cwd": "/dev/pts",
        }).encode()
        codex = self.start(root([node("target", "pty"), node("pipe_child", "pipe")],
                                hook=[hook_run(stdin=naming)]))
        pids = codex.pids()
        self.assert_quiet(codex.runs()[0])
        self.assert_gone(pids, "target")
        self.settle()
        self.assert_alive(pids, "root", "pipe_child")
        self.assert_alive(outsider_pids, "root", "p_child")


class TestCommandLineEntry(unittest.TestCase):
    def run_hook(self, args, stdin):
        return subprocess.run(
            [sys.executable, str(HOOK), *args],
            input=stdin, capture_output=True, timeout=30,
        )

    def test_ac6_without_an_anchor_the_hook_exits_zero_and_writes_nothing(self):
        for stdin in (b"{}", b"", b"\xff", b"[]"):
            with self.subTest(stdin=stdin):
                proc = self.run_hook([], stdin)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, b"")
                self.assertEqual(proc.stderr, b"")

    def test_ac6_a_run_leaves_no_bytecode_cache_in_a_plugin_directory(self):
        for plugin, path in HOOK_PATHS.items():
            self.run_hook([], b"{}")
            with self.subTest(copy=plugin):
                self.assertEqual(
                    list(path.parent.glob("__pycache__/codex-hook-tty-reaper*")), []
                )


if __name__ == "__main__":
    unittest.main()
