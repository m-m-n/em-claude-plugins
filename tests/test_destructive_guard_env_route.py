"""Env-route body reading of `em-workflow/hooks/destructive-guard.py`
(env-route-lex-flag-isolation task0001; FR1-FR4, NFR2; TS-8, TS-9, TS-10;
TM-1, TM-3, TM-4).

The env route (`_args_json_env_payload_values()`) reads the body of a
`bash -c` that `head()` misreads (`/usr/bin/env`, a lone `-`) for the
notion-pair check. Its lexer calls used to leave the module-level flags
`_lex_unreadable_met` and `_lex_extglob_met` raised for the rest of the
decision, and a body with an extended-pattern parenthesis is read under both
extglob settings by the route itself. What no hook decision shows is pinned
here, in-process:

- TestStateRestored (AC-4, TS-8): after the reading exits -- by a normal
  return, by an early return, by an exception -- the three states equal their
  values at entry, for every combination of entry values; the exception
  propagates unchanged; the second reading runs under the opposite setting.
- TestBothReadings (AC-5, TS-9): a value both readings return is returned once
  and charged once; the union of the readings is returned; an overrun or an
  unrestorable raised by only one reading is reported.
- TestExtglobUnitRecord (AC-6, TS-10): the route records no extglob unit.

The hook has no package, so every test class loads the module from its file
path, with bytecode writing off for the load (no `__pycache__` is written next
to the hook). The module a class loads is its own: the states a test sets are
put back by a cleanup, and every patch is undone when its test ends. Standard
library only.
"""

import collections
import contextlib
import importlib.util
import io
import itertools
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "em-workflow", "hooks", "destructive-guard.py")

# An env assignment that lifts the notion pair (BASH_FUNC_ imports a function
# named mcp-bridge), so the notion statement of the body is one the route
# reads.
LIFT = "'BASH_FUNC_mcp-bridge%%=() { :; }'"
NOTION = (
    "mcp-bridge run --mcp notion --tool notion-create-comment "
    "--args-json '{\"command\":\"git branch -D example\"}'"
)
# The same call whose JSON value spans two lines: the extglob-off reading
# discards the line an extended-pattern parenthesis sits on, so a quote opened
# on that line is no region, and only the extglob-on reading sees the call.
NOTION_TWO_LINES = (
    "mcp-bridge run --mcp notion --tool notion-create-comment "
    "--args-json '{\n\"command\":\"git branch -D example\"}'"
)
EXT_LINE = "a=(@(x))"
COMMAND_FOUND = "git branch -D example"

ALL_ENTRY_STATES = list(itertools.product((False, True), repeat=3))


def load_hook():
    """A hook module of its own: empty lexer cache, no judgment behind it.

    The module body runs with bytecode writing off, and the caller's
    `sys.dont_write_bytecode` is put back on every exit, a raising body
    included."""
    spec = importlib.util.spec_from_file_location(
        "destructive_guard_env_route_under_test", HOOK
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def env_command(body):
    """`/usr/bin/env` with the lifting assignment and a `bash -c` whose
    payload is BODY: single-quoted when BODY holds no single quote (so a `$`
    in it stays text), else double-quoted with its `\\` and `"` escaped."""
    if "'" not in body:
        return "/usr/bin/env %s bash -c '%s'" % (LIFT, body)
    escaped = body.replace("\\", "\\\\").replace('"', '\\"')
    return '/usr/bin/env %s bash -c "%s"' % (LIFT, escaped)


Statement = collections.namedtuple("Statement", "shaped marked args")


def env_statement(hook, command):
    """The one statement of COMMAND the env route is asked about: its shaped
    words, the _MarkedText of its chunk and the words after its command word,
    as the notion path of the `--args-json` step hands them over."""
    marked = hook._args_json_payload_chunk(command, None)
    found = []
    for shaped in hook._args_json_chunk_statements(marked):
        name, args = hook.head(shaped)
        if name is not None:
            found.append(Statement(shaped, marked, args))
    assert len(found) == 1, found
    return found[0]


class HookTestCase(unittest.TestCase):
    """A hook module of its own per class, and a way to read and set the three
    states the env route must leave as it found them."""

    @classmethod
    def setUpClass(cls):
        cls.hook = load_hook()

    def setUp(self):
        self.addCleanup(self.reset_states)
        self.reset_states()

    def reset_states(self):
        self.hook._lex_unreadable_met = False
        self.hook._lex_extglob_met = False
        self.hook._lex_extglob = False
        self.hook._lex_ext_seen.clear()

    def states(self):
        return (
            self.hook._lex_unreadable_met,
            self.hook._lex_extglob_met,
            self.hook._lex_extglob,
        )

    def set_states(self, unreadable, extglob_met, extglob):
        self.hook._lex_unreadable_met = unreadable
        self.hook._lex_extglob_met = extglob_met
        self.hook._lex_extglob = extglob

    def statement(self, body):
        """The env-route statement of BODY, built under extglob off with the
        states clear, so building it leaves nothing behind."""
        self.reset_states()
        statement = env_statement(self.hook, env_command(body))
        self.reset_states()
        return statement

    def read(self, statement):
        return self.hook._args_json_env_payload_values(
            statement.shaped, statement.marked, statement.args
        )


class TestStateRestored(HookTestCase):
    """AC-4 (TS-8): `_lex_unreadable_met`, `_lex_extglob_met` and
    `_lex_extglob` equal their values at entry on every exit (TM-1, TM-3)."""

    def assert_restored_for_every_entry(self, body, patches=()):
        statement = self.statement(body)
        for entry in ALL_ENTRY_STATES:
            with self.subTest(entry=entry):
                self.set_states(*entry)
                with contextlib.ExitStack() as stack:
                    for patch in patches:
                        stack.enter_context(patch())
                    self.read(statement)
                self.assertEqual(self.states(), entry)

    def test_normal_return_one_reading(self):
        self.assert_restored_for_every_entry("echo hi; " + NOTION)

    def test_normal_return_two_readings(self):
        self.assert_restored_for_every_entry(EXT_LINE + "; " + NOTION)

    def test_normal_return_without_a_lifted_notion_statement(self):
        self.assert_restored_for_every_entry("echo hi")

    def test_flags_the_body_raises_do_not_stay_raised(self):
        # FR1: a body whose heredoc delimiter cannot be read raises
        # `_lex_unreadable_met` while it is read; it is not left raised.
        statement = self.statement("cat <<${tag}\nhello\n${tag}\n")
        self.set_states(False, False, False)
        self.read(statement)
        self.assertEqual(self.states(), (False, False, False))

    def test_extglob_flag_the_body_raises_does_not_stay_raised(self):
        statement = self.statement(EXT_LINE)
        self.set_states(False, False, False)
        self.read(statement)
        self.assertEqual(self.states(), (False, False, False))

    def test_flags_raised_before_the_reading_stay_raised(self):
        # TM-1: the value restored is the entry value, never a fixed false.
        statement = self.statement("echo hi")
        self.set_states(True, True, False)
        self.read(statement)
        self.assertEqual(self.states(), (True, True, False))

    def test_early_return_when_the_payload_chunk_cannot_be_built(self):
        hook = self.hook
        real_lex_shell = hook.lex_shell
        payload = "echo hi"

        def lex_shell(text, *args, **kwargs):
            if text == payload:
                hook._lex_unreadable_met = True
                hook._lex_extglob_met = True
                raise hook.LexBudgetExceeded()
            return real_lex_shell(text, *args, **kwargs)

        statement = self.statement(payload)
        for entry in ALL_ENTRY_STATES:
            with self.subTest(entry=entry):
                self.set_states(*entry)
                with mock.patch.object(hook, "lex_shell", lex_shell):
                    result = self.read(statement)
                self.assertEqual(result, hook._ARGS_JSON_NOTHING)
                self.assertEqual(self.states(), entry)

    def test_early_return_with_a_chunk_that_cannot_be_lexed_in_the_second_reading(self):
        # The first reading builds a chunk; the second finds none. Both
        # states the readings touched are put back.
        hook = self.hook
        real_chunk = hook._args_json_payload_chunk
        statement = self.statement(EXT_LINE + "; " + NOTION)

        def chunk(payload, outer_marked):
            built = real_chunk(payload, outer_marked)
            if hook._lex_extglob:
                hook._lex_unreadable_met = True
                return None
            return built

        for entry in ((False, False, False), (True, True, False)):
            with self.subTest(entry=entry):
                self.set_states(*entry)
                with mock.patch.object(hook, "_args_json_payload_chunk", chunk):
                    self.read(statement)
                self.assertEqual(self.states(), entry)

    def test_exception_in_the_first_reading_propagates_unchanged_and_restores(self):
        hook = self.hook
        raised = hook.LexBudgetExceeded()

        def chunk_statements(marked):
            hook._lex_unreadable_met = True
            hook._lex_extglob_met = True
            raise raised

        statement = self.statement(EXT_LINE + "; " + NOTION)
        for entry in ALL_ENTRY_STATES:
            with self.subTest(entry=entry):
                self.set_states(*entry)
                with mock.patch.object(
                    hook, "_args_json_chunk_statements", chunk_statements
                ):
                    with self.assertRaises(hook.LexBudgetExceeded) as caught:
                        self.read(statement)
                self.assertIs(caught.exception, raised)
                self.assertEqual(self.states(), entry)

    def test_exception_in_the_second_reading_restores_the_extglob_setting(self):
        # TM-3: the setting switched for the second reading is back when the
        # second reading raises.
        hook = self.hook
        raised = hook.LexBudgetExceeded()
        real_statements = hook._args_json_chunk_statements
        statement = self.statement(EXT_LINE + "; " + NOTION)
        for entry in ALL_ENTRY_STATES:
            with self.subTest(entry=entry):
                entry_extglob = entry[2]

                def chunk_statements(marked, entry_extglob=entry_extglob):
                    if hook._lex_extglob != entry_extglob:
                        hook._lex_unreadable_met = True
                        raise raised
                    return real_statements(marked)

                self.set_states(*entry)
                with mock.patch.object(
                    hook, "_args_json_chunk_statements", chunk_statements
                ):
                    with self.assertRaises(hook.LexBudgetExceeded) as caught:
                        self.read(statement)
                self.assertIs(caught.exception, raised)
                self.assertEqual(self.states(), entry)

    def test_second_reading_runs_under_the_opposite_setting_only_when_a_paren_was_met(self):
        hook = self.hook
        real_statements = hook._args_json_chunk_statements
        for body, expected_count in (
            (EXT_LINE + "; " + NOTION, 2),
            ("echo hi; " + NOTION, 1),
        ):
            statement = self.statement(body)
            for entry_extglob in (False, True):
                with self.subTest(body=body, entry_extglob=entry_extglob):
                    seen = []

                    def chunk_statements(marked):
                        seen.append(hook._lex_extglob)
                        return real_statements(marked)

                    self.set_states(False, False, entry_extglob)
                    with mock.patch.object(
                        hook, "_args_json_chunk_statements", chunk_statements
                    ):
                        self.read(statement)
                    self.assertEqual(len(seen), expected_count)
                    self.assertEqual(seen[0], entry_extglob)
                    if expected_count == 2:
                        self.assertEqual(seen[1], not entry_extglob)


class TestBothReadings(HookTestCase):
    """AC-5 (TS-9): the result of the two readings (FR3, FR4; TM-4)."""

    def commands_of(self, result):
        return [c for value in result.values for c in value.commands]

    def bodies_of(self, result):
        return [b for value in result.values for b in value.bodies]

    def test_a_value_both_readings_return_is_returned_once_and_charged_once(self):
        single = self.read(self.statement("echo hi; " + NOTION))
        self.assertEqual(self.commands_of(single), [COMMAND_FOUND])
        for entry_extglob in (False, True):
            with self.subTest(entry_extglob=entry_extglob):
                statement = self.statement(EXT_LINE + "; " + NOTION)
                self.set_states(False, False, entry_extglob)
                both = self.read(statement)
                self.assertEqual(self.commands_of(both), [COMMAND_FOUND])
                self.assertEqual(len(both.values), 1)
                self.assertEqual(both.charge, single.charge)

    def lifted_notion_values(self, statement, payload, extglob):
        """The decoded `command` strings one reading of PAYLOAD under the
        extglob setting EXTGLOB finds: the lexer calls of the body reading
        (FR1), made by hand under that setting."""
        hook = self.hook
        self.set_states(False, False, extglob)
        found = []
        chunk = hook._args_json_payload_chunk(payload, statement.marked)
        for inner in hook._args_json_chunk_statements(chunk):
            name, args = hook.head(inner)
            if name is None:
                continue
            words = hook._args_json_lifted_notion_words(inner, chunk, name, args)
            if words is None:
                continue
            for value in hook._args_json_read_values(chunk, words).values:
                found.extend(value.commands)
        return found

    def test_the_two_line_notion_pair_is_visible_only_under_extglob_on(self):
        # TS-6 / AC-3: the fact the decision case rests on, read from the
        # lexer: the extglob-off reading discards the line the parenthesis is
        # on, and the call that follows it on that line is not seen.
        body = EXT_LINE + "; " + NOTION_TWO_LINES
        statement = self.statement(body)
        self.assertEqual(self.lifted_notion_values(statement, body, False), [])
        self.assertEqual(
            self.lifted_notion_values(statement, body, True), [COMMAND_FOUND]
        )

    def test_the_one_line_notion_pair_is_visible_under_both_settings(self):
        body = EXT_LINE + "; " + NOTION
        statement = self.statement(body)
        for extglob in (False, True):
            with self.subTest(extglob=extglob):
                self.assertEqual(
                    self.lifted_notion_values(statement, body, extglob), [COMMAND_FOUND]
                )

    def test_the_value_only_one_reading_shows_is_returned(self):
        # FR3 / TM-2: the call is visible under the extglob-on reading only.
        statement = self.statement(EXT_LINE + "; " + NOTION_TWO_LINES)
        for entry_extglob in (False, True):
            with self.subTest(entry_extglob=entry_extglob):
                self.set_states(False, False, entry_extglob)
                result = self.read(statement)
                self.assertEqual(self.commands_of(result), [COMMAND_FOUND])
                self.assertGreater(result.charge, 0)

    def test_the_value_is_not_returned_when_neither_reading_shows_it(self):
        statement = self.statement(EXT_LINE + "; echo hi")
        result = self.read(statement)
        self.assertEqual(result, self.hook._ARGS_JSON_NOTHING)

    def fake_read_values(self, by_setting):
        """A `_args_json_read_values()` that answers BY_SETTING[reading in
        force]: an ArgsJsonResult built from (charge, bodies, commands,
        overrun, unrestorable)."""
        hook = self.hook

        def read_values(marked, words):
            charge, bodies, commands, overrun, unrestorable = by_setting[hook._lex_extglob]
            values = ()
            if bodies or commands:
                values = (hook.ArgsJsonValue("word", tuple(bodies), tuple(commands)),)
            return hook.ArgsJsonResult(values, charge, overrun, unrestorable)

        return mock.patch.object(self.hook, "_args_json_read_values", read_values)

    def test_identical_results_of_the_two_readings_count_once(self):
        statement = self.statement(EXT_LINE + "; " + NOTION)
        same = (10, ("b1",), ("c1",), False, False)
        with self.fake_read_values({False: same, True: same}):
            result = self.read(statement)
        self.assertEqual(self.bodies_of(result), ["b1"])
        self.assertEqual(self.commands_of(result), ["c1"])
        self.assertEqual(result.charge, 10)

    def test_overlapping_results_return_each_string_once(self):
        statement = self.statement(EXT_LINE + "; " + NOTION)
        for entry_extglob in (False, True):
            with self.subTest(entry_extglob=entry_extglob):
                first = (10, ("b1",), ("c1", "c2"), False, False)
                second = (12, ("b1", "b2"), ("c1",), False, False)
                by_setting = {entry_extglob: first, not entry_extglob: second}
                self.set_states(False, False, entry_extglob)
                with self.fake_read_values(by_setting):
                    result = self.read(statement)
                self.assertEqual(self.bodies_of(result), ["b1", "b2"])
                self.assertEqual(self.commands_of(result), ["c1", "c2"])
                self.assertEqual(result.charge, 22)

    def test_a_result_whose_strings_the_first_reading_already_returned_is_not_charged(self):
        statement = self.statement(EXT_LINE + "; " + NOTION)
        first = (10, ("b1",), ("c1", "c2"), False, False)
        second = (7, ("b1",), ("c1",), False, False)
        with self.fake_read_values({False: first, True: second}):
            result = self.read(statement)
        self.assertEqual(self.bodies_of(result), ["b1"])
        self.assertEqual(self.commands_of(result), ["c1", "c2"])
        self.assertEqual(result.charge, 10)

    def test_duplicates_inside_one_reading_are_kept(self):
        statement = self.statement(EXT_LINE + "; " + NOTION)
        first = (10, (), ("c1", "c1"), False, False)
        second = (10, (), ("c1", "c1"), False, False)
        with self.fake_read_values({False: first, True: second}):
            result = self.read(statement)
        self.assertEqual(self.commands_of(result), ["c1", "c1"])
        self.assertEqual(result.charge, 10)

    def test_overrun_raised_by_only_one_reading_is_reported(self):
        statement = self.statement(EXT_LINE + "; " + NOTION)
        clean = (10, (), ("c1",), False, False)
        flagged = (10, (), ("c1",), True, False)
        for entry_extglob in (False, True):
            for flagged_setting in (False, True):
                with self.subTest(entry_extglob=entry_extglob, flagged_setting=flagged_setting):
                    by_setting = {flagged_setting: flagged, not flagged_setting: clean}
                    self.set_states(False, False, entry_extglob)
                    with self.fake_read_values(by_setting):
                        result = self.read(statement)
                    self.assertTrue(result.overrun)
                    self.assertFalse(result.unrestorable)
                    self.assertEqual(self.commands_of(result), ["c1"])
                    self.assertEqual(result.charge, 10)

    def test_unrestorable_raised_by_only_one_reading_is_reported(self):
        statement = self.statement(EXT_LINE + "; " + NOTION)
        clean = (10, (), ("c1",), False, False)
        flagged = (10, (), ("c1",), False, True)
        for entry_extglob in (False, True):
            for flagged_setting in (False, True):
                with self.subTest(entry_extglob=entry_extglob, flagged_setting=flagged_setting):
                    by_setting = {flagged_setting: flagged, not flagged_setting: clean}
                    self.set_states(False, False, entry_extglob)
                    with self.fake_read_values(by_setting):
                        result = self.read(statement)
                    self.assertTrue(result.unrestorable)
                    self.assertFalse(result.overrun)
                    self.assertEqual(self.commands_of(result), ["c1"])
                    self.assertEqual(result.charge, 10)

    def test_neither_flag_is_set_when_neither_reading_raises_it(self):
        statement = self.statement(EXT_LINE + "; " + NOTION)
        clean = (10, (), ("c1",), False, False)
        with self.fake_read_values({False: clean, True: clean}):
            result = self.read(statement)
        self.assertFalse(result.overrun)
        self.assertFalse(result.unrestorable)

    def test_flags_of_a_statement_that_has_no_value_are_reported(self):
        # An overrun with no decoded value still reaches the result.
        statement = self.statement(EXT_LINE + "; " + NOTION)
        only_one = (0, (), (), True, False)
        clean = (0, (), (), False, False)
        with self.fake_read_values({False: clean, True: only_one}):
            result = self.read(statement)
        self.assertTrue(result.overrun)
        self.assertEqual(result.values, ())


class TestExtglobUnitRecord(HookTestCase):
    """AC-6 (TS-10, NFR2): the route records no extglob unit."""

    def test_reading_a_body_with_an_extended_pattern_paren_records_no_unit(self):
        hook = self.hook
        statement = self.statement(EXT_LINE + "; " + NOTION)
        hook._lex_ext_seen.add(("sentinel", 7))
        before = set(hook._lex_ext_seen)
        count_before = hook._count_extglob_units()
        seen = []
        real_statements = hook._args_json_chunk_statements

        def chunk_statements(marked):
            seen.append(hook._lex_extglob)
            return real_statements(marked)

        with mock.patch.object(hook, "_args_json_chunk_statements", chunk_statements):
            self.read(statement)
        self.assertEqual(len(seen), 2, "both readings ran")
        self.assertEqual(hook._lex_ext_seen, before)
        self.assertEqual(hook._count_extglob_units(), count_before)

    def test_reading_with_an_empty_record_leaves_it_empty(self):
        hook = self.hook
        self.read(self.statement(EXT_LINE + "; " + NOTION_TWO_LINES))
        self.assertEqual(hook._count_extglob_units(), 0)


class TestJudgmentThroughRun(HookTestCase):
    """The route's effect on the judgment of a whole command (FR1, NFR1): the
    flags run() decides on are those of the lexing outside the route."""

    def judge(self, command, batch=False):
        hook = self.hook
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        out = io.StringIO()
        with mock.patch.dict(os.environ):
            os.environ.pop("CLAUDE_BATCH", None)
            if batch:
                os.environ["CLAUDE_BATCH"] = "1"
            with mock.patch.object(sys, "stdin", io.StringIO(payload)):
                with contextlib.redirect_stdout(out):
                    try:
                        hook.run()
                    except SystemExit:
                        pass
                    else:
                        raise AssertionError("run() returned without exiting")
        text = out.getvalue().strip()
        if not text:
            return "(silent)"
        return json.loads(text)["hookSpecificOutput"]["permissionDecision"]

    def test_a_body_with_only_a_paren_does_not_start_the_second_whole_command_reading(self):
        hook = self.hook
        self.assertEqual(self.judge(env_command(EXT_LINE)), "allow")
        self.assertFalse(hook._lex_extglob_met)
        self.assertEqual(list(hook._lex_ext_units), [0])

    def test_a_body_with_only_an_unreadable_delimiter_leaves_the_flag_down(self):
        hook = self.hook
        command = "/usr/bin/env bash -c 'cat <<${tag}\nhello\n${tag}\n'"
        self.assertEqual(self.judge(command, batch=True), "allow")
        self.assertFalse(hook._lex_unreadable_met)


if __name__ == "__main__":
    unittest.main()
