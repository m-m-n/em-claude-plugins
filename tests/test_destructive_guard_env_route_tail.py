"""Tail rule of the env route of `em-workflow/hooks/destructive-guard.py`
(env-route-unreadable-heredoc-ask task0001; FR1 to FR4, NFR1; TS-9 to TS-12;
TM-1 to TM-5).

The env route (`_args_json_env_payload_values()`) reads the body of a
`bash -c` that `head()` misreads (`/usr/bin/env`, a lone `-`) for the
notion-pair check. When a here-document delimiter word of that body cannot be
read, the lexer treats the rest of the body as an unread tail (a tail source),
and what is in the tail is not read as statements. The tail rule reports the
reading as unrestorable when that tail holds the `mcp-bridge` word (also split
by quotes or a line continuation) or `$'`. What no hook decision shows is
pinned here, in-process:

- TestTailRule (AC-2, TS-9): the predicate
  `_args_json_env_tail_unrestorable(payload, lex_map)` on maps `lex_shell()`
  made for hand-written payloads.
- TestEnvBodyReading (AC-4, TS-10): the env body reading reports Unrestorable
  for the bodies of the decision cases and not for a readable body; the map
  of those bodies has `unreadable` set and a tail start at or before the
  first unreadable `<<` (A4).
- TestBothReadings (AC-5, TS-11): the combination of the two extglob
  readings, the rule answering true under one setting only.
- TestStateRestored (AC-6, TS-12): `_lex_unreadable_met`,
  `_lex_extglob_met` and `_lex_extglob` equal their values at entry after a
  reading in which the rule answered true, for every combination of entry
  values.

The hook has no package, so every test class loads the module from its file
path, with bytecode writing off for the load (no `__pycache__` is written next
to the hook). The module a class loads is its own: the states a test sets are
put back by a cleanup, and every patch is undone when its test ends. Standard
library only; every test is a single static analysis call.
"""

import contextlib
import importlib.util
import itertools
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "em-workflow", "hooks", "destructive-guard.py")

# An env assignment that lifts the notion pair (BASH_FUNC_ imports a function
# named mcp-bridge), so the notion statement of the body is one the route
# reads.
LIFT = "'BASH_FUNC_mcp-bridge%%=() { :; }'"
# The notion-pair call without its command word, the JSON quoted so that it
# fits inside a single-quoted payload.
CALL = (
    " run --mcp notion --tool notion-create-comment"
    ' --args-json "{\\"command\\":\\"git branch -D example\\"}"'
)
# A here-document whose delimiter word `${tag}` cannot be read: the lexer
# reads the rest of the body as its unread tail.
HEREDOC = "cat <<${tag}\nhello\n${tag}\n"
EXT_LINE = "a=(@(x))"

# The TS-1, TS-4 and TS-7 bodies of the decision cases.
BODY_PLAIN = HEREDOC + "mcp-bridge" + CALL
BODY_QUOTE_SPLIT = HEREDOC + '"mcp-"bridge' + CALL
BODY_CONTINUATION_SPLIT = HEREDOC + "mcp-br\\\nidge" + CALL
BODY_ANSI_C = HEREDOC + "$'\\x6dcp-bridge'" + CALL
BODY_WORD_IN_HEREDOC_BODY = "cat <<${tag}\nmcp-bridge\n${tag}\n"
UNREADABLE_BODIES = (
    ("plain word", BODY_PLAIN),
    ("quote-split word", BODY_QUOTE_SPLIT),
    ("continuation-split word", BODY_CONTINUATION_SPLIT),
    ("ANSI-C word", BODY_ANSI_C),
    ("word as here-document body text", BODY_WORD_IN_HEREDOC_BODY),
)

ALL_ENTRY_STATES = list(itertools.product((False, True), repeat=3))


def load_hook():
    """A hook module of its own: empty lexer cache, no judgment behind it.

    The module body runs with bytecode writing off, and the caller's
    `sys.dont_write_bytecode` is put back on every exit, a raising body
    included."""
    spec = importlib.util.spec_from_file_location(
        "destructive_guard_env_route_tail_under_test", HOOK
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
    payload is BODY, single-quoted (BODY holds no single quote, so a `$` in
    it stays text)."""
    assert "'" not in body, body
    return "/usr/bin/env %s bash -c '%s'" % (LIFT, body)


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

    def lex(self, payload, extglob=False):
        """The map `lex_shell()` makes for PAYLOAD in shell mode under the
        setting EXTGLOB, with the states clear before and after."""
        self.reset_states()
        lex_map = self.hook.lex_shell(payload, "shell", True, extglob)
        self.reset_states()
        return lex_map

    def tail_rule(self, payload, extglob=False):
        return self.hook._args_json_env_tail_unrestorable(
            payload, self.lex(payload, extglob)
        )

    def statement(self, body):
        """The one statement of the env command whose payload is BODY, as the
        notion path of the `--args-json` step hands it to the env route: its
        shaped words, the _MarkedText of its chunk and the words after its
        command word. Built under extglob off with the states clear."""
        hook = self.hook
        self.reset_states()
        marked = hook._args_json_payload_chunk(env_command(body), None)
        found = []
        for shaped in hook._args_json_chunk_statements(marked):
            name, args = hook.head(shaped)
            if name is not None:
                found.append((shaped, marked, args))
        self.assertEqual(len(found), 1, found)
        self.reset_states()
        return found[0]

    def marked(self):
        """The _MarkedText of a chunk the statement that runs a payload sits
        in: any statement's will do for the reading of a payload."""
        return self.statement("echo hi")[1]

    def read(self, statement):
        shaped, marked, args = statement
        return self.hook._args_json_env_payload_values(shaped, marked, args)


class TestTailRule(HookTestCase):
    """AC-2 (TS-9): the answers of `_args_json_env_tail_unrestorable()`
    (FR1, FR4; TM-2, TM-3)."""

    def test_the_plain_word_in_the_tail_is_unrestorable(self):
        self.assertTrue(self.tail_rule(BODY_PLAIN))

    def test_the_word_split_by_quotes_is_unrestorable(self):
        self.assertTrue(self.tail_rule(BODY_QUOTE_SPLIT))

    def test_the_word_split_by_single_quotes_and_backslashes_is_unrestorable(self):
        payload = HEREDOC + "m'c'p\\-b\"r\"idge" + CALL
        self.assertTrue(self.tail_rule(payload))

    def test_the_word_split_by_a_line_continuation_is_unrestorable(self):
        self.assertTrue(self.tail_rule(BODY_CONTINUATION_SPLIT))

    def test_an_ansi_c_quote_in_the_tail_is_unrestorable(self):
        self.assertTrue(self.tail_rule(BODY_ANSI_C))

    def test_an_ansi_c_quote_without_the_word_is_unrestorable(self):
        self.assertTrue(self.tail_rule(HEREDOC + "echo $'a'"))

    def test_the_word_as_here_document_body_text_is_unrestorable(self):
        self.assertTrue(self.tail_rule(BODY_WORD_IN_HEREDOC_BODY))

    def test_a_tail_without_the_word_is_not_unrestorable(self):
        self.assertFalse(self.tail_rule(HEREDOC + "echo hi"))

    def test_a_tail_with_only_the_delimiter_word_is_not_unrestorable(self):
        self.assertFalse(self.tail_rule("cat <<${tag}\nhello\n${tag}\n"))

    def test_a_name_that_becomes_the_word_by_a_parameter_expansion_is_not_unrestorable(self):
        # A3: no expansion is evaluated.
        self.assertFalse(self.tail_rule(HEREDOC + "${a}cp-bridge" + CALL))

    def test_a_name_built_by_a_command_substitution_is_not_unrestorable(self):
        # A3: `$(printf ...)` is read as text, never run.
        payload = HEREDOC + "$(printf '%s%s' mcp- bridge)" + CALL
        self.assertFalse(self.tail_rule(payload))

    def test_the_word_only_before_the_tail_start_is_not_unrestorable(self):
        payload = "echo mcp-bridge; " + HEREDOC
        lex_map = self.lex(payload)
        self.assertTrue(lex_map.unreadable)
        self.assertLess(payload.index("mcp-bridge"), lex_map.tail_start)
        self.assertFalse(self.hook._args_json_env_tail_unrestorable(payload, lex_map))

    def test_an_ansi_c_quote_only_before_the_tail_start_is_not_unrestorable(self):
        payload = "echo $'a'; " + HEREDOC + "echo hi"
        lex_map = self.lex(payload)
        self.assertTrue(lex_map.unreadable)
        self.assertLess(payload.index("$'"), lex_map.tail_start)
        self.assertFalse(self.hook._args_json_env_tail_unrestorable(payload, lex_map))

    def test_a_map_whose_unreadable_is_not_set_is_not_unrestorable(self):
        payload = "mcp-bridge" + CALL
        lex_map = self.lex(payload)
        self.assertFalse(lex_map.unreadable)
        self.assertFalse(self.hook._args_json_env_tail_unrestorable(payload, lex_map))

    def test_a_tail_that_is_not_from_an_unreadable_delimiter_is_not_unrestorable(self):
        # An unclosed parameter expansion also starts a tail, but no
        # delimiter word is unreadable: the rule needs `unreadable`.
        for payload in ("echo ${x mcp-bridge", "echo ${x $'a'"):
            with self.subTest(payload=payload):
                lex_map = self.lex(payload)
                self.assertFalse(lex_map.unreadable)
                self.assertIsNotNone(lex_map.tail_start)
                self.assertFalse(
                    self.hook._args_json_env_tail_unrestorable(payload, lex_map)
                )

    def test_an_absent_tail_start_reads_as_the_start_of_the_payload(self):
        # A4: with `unreadable` set the tail start is never absent; if it
        # were, the whole payload would be the tail.
        lex_map = types.SimpleNamespace(unreadable=True, tail_start=None)
        rule = self.hook._args_json_env_tail_unrestorable
        self.assertTrue(rule("echo mcp-bridge", lex_map))
        self.assertTrue(rule("echo $'a'", lex_map))
        self.assertFalse(rule("echo hi", lex_map))

    def test_the_tail_starts_at_the_tail_start_of_the_map(self):
        lex_map = types.SimpleNamespace(unreadable=True, tail_start=5)
        rule = self.hook._args_json_env_tail_unrestorable
        self.assertFalse(rule("mcp-bridge", types.SimpleNamespace(unreadable=True, tail_start=1)))
        self.assertTrue(rule("echo mcp-bridge", lex_map))
        self.assertFalse(rule("mcp-b echo", lex_map))

    def test_line_continuations_are_removed_before_quotes_and_backslashes(self):
        # `mcp-br`, a backslash, a double quote, a newline, `idge`: the
        # backslash and the newline are not adjacent, so no continuation is
        # removed; the backslash and the quote are then removed and the
        # newline stays. The other order would join the word.
        payload = HEREDOC + 'mcp-br\\"\nidge' + CALL
        self.assertFalse(self.tail_rule(payload))

    def test_the_word_with_a_newline_inside_is_not_unrestorable(self):
        self.assertFalse(self.tail_rule(HEREDOC + "mcp-br\nidge" + CALL))

    def test_it_lexes_nothing_and_raises_no_flag(self):
        hook = self.hook
        lex_map = self.lex(BODY_PLAIN)
        for entry in ALL_ENTRY_STATES:
            with self.subTest(entry=entry):
                self.set_states(*entry)
                with mock.patch.object(hook, "lex_shell", side_effect=AssertionError("lexed")):
                    self.assertTrue(hook._args_json_env_tail_unrestorable(BODY_PLAIN, lex_map))
                self.assertEqual(self.states(), entry)


class TestEnvBodyReading(HookTestCase):
    """AC-4 (TS-10): what the env body reading reports (FR1; TM-1)."""

    def reading(self, payload, marked=None):
        if marked is None:
            marked = self.marked()
        self.reset_states()
        result = self.hook._args_json_env_body_reading(payload, marked)
        self.reset_states()
        return result

    def test_the_map_of_each_unreadable_body_has_unreadable_and_an_early_tail_start(self):
        for name, body in UNREADABLE_BODIES:
            with self.subTest(body=name):
                lex_map = self.lex(body)
                self.assertTrue(lex_map.unreadable)
                self.assertIsNotNone(lex_map.tail_start)
                self.assertLessEqual(lex_map.tail_start, body.index("<<"))

    def test_the_reading_reports_unrestorable_for_each_unreadable_body(self):
        for name, body in UNREADABLE_BODIES:
            with self.subTest(body=name):
                self.assertTrue(self.reading(body).unrestorable)

    def test_the_route_reports_unrestorable_without_a_value_for_a_body_it_cannot_read(self):
        for name, body in (
            ("plain word", BODY_PLAIN),
            ("quote-split word", BODY_QUOTE_SPLIT),
            ("continuation-split word", BODY_CONTINUATION_SPLIT),
            ("word as here-document body text", BODY_WORD_IN_HEREDOC_BODY),
        ):
            with self.subTest(body=name):
                result = self.read(self.statement(body))
                self.assertTrue(result.unrestorable)
                self.assertEqual(result.values, ())
                self.assertFalse(result.overrun)

    def test_the_rule_changes_neither_the_entries_nor_the_overrun(self):
        hook = self.hook
        for name, body in UNREADABLE_BODIES:
            with self.subTest(body=name):
                with_rule = self.reading(body)
                with mock.patch.object(
                    hook, "_args_json_env_tail_unrestorable", return_value=False
                ):
                    without_rule = self.reading(body)
                self.assertTrue(with_rule.unrestorable)
                self.assertFalse(without_rule.unrestorable)
                self.assertEqual(with_rule.entries, without_rule.entries)
                self.assertEqual(with_rule.overrun, without_rule.overrun)

    def test_a_readable_body_with_the_word_in_another_statement_is_not_unrestorable(self):
        for body in (
            "echo mcp-bridge",
            "mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{}'",
            "cat <<EOF\nmcp-bridge\nEOF\n",
            "echo mcp-bridge $'a'",
        ):
            with self.subTest(body=body):
                self.assertFalse(self.hook.lex_shell(body, "shell").unreadable)
                self.assertFalse(self.reading(body).unrestorable)

    def test_an_unreadable_body_without_the_word_after_the_tail_start_is_not_unrestorable(self):
        for body in (
            HEREDOC,
            "echo mcp-bridge; " + HEREDOC,
            HEREDOC + "echo hi",
            HEREDOC + "${a}cp-bridge" + CALL,
        ):
            with self.subTest(body=body):
                self.assertTrue(self.lex(body).unreadable)
                self.assertFalse(self.reading(body).unrestorable)

    def test_the_rule_gets_the_map_the_chunk_was_built_from(self):
        hook = self.hook
        seen = []

        def spy(payload, lex_map):
            seen.append((payload, lex_map))
            return False

        with mock.patch.object(hook, "_args_json_env_tail_unrestorable", spy):
            self.reading(BODY_PLAIN)
        self.assertEqual(len(seen), 1)
        payload, lex_map = seen[0]
        self.assertEqual(payload, BODY_PLAIN)
        self.assertIs(lex_map, hook.lex_shell(BODY_PLAIN, "shell"))

    def test_the_rule_is_not_asked_when_the_chunk_cannot_be_built(self):
        hook = self.hook
        marked = self.marked()
        spy = mock.Mock(return_value=True)
        with mock.patch.object(hook, "_args_json_payload_chunk", return_value=None):
            with mock.patch.object(hook, "_args_json_env_tail_unrestorable", spy):
                result = self.reading(BODY_PLAIN, marked)
        self.assertEqual(result, hook._EnvBodyReading((), False, False))
        spy.assert_not_called()

    def test_a_lex_budget_exceeded_of_the_statement_loop_propagates_unchanged(self):
        # The rule runs before the statement loop, so what the loop raises
        # reaches the caller as before.
        hook = self.hook
        raised = hook.LexBudgetExceeded()
        marked = self.marked()
        with mock.patch.object(
            hook, "_args_json_chunk_statements", side_effect=raised
        ):
            with self.assertRaises(hook.LexBudgetExceeded) as caught:
                self.reading(BODY_PLAIN, marked)
        self.assertIs(caught.exception, raised)

    def fake_read_values(self, unrestorable):
        hook = self.hook
        return mock.patch.object(
            hook,
            "_args_json_read_values",
            return_value=hook.ArgsJsonResult((), 0, False, unrestorable),
        )

    def test_the_unrestorable_of_a_lifted_notion_statement_is_still_reported(self):
        # The statements' Unrestorable is ORed into the rule's answer.
        hook = self.hook
        body = "echo hi; mcp-bridge" + CALL
        for rule_answer in (False, True):
            for statement_answer in (False, True):
                with self.subTest(rule=rule_answer, statement=statement_answer):
                    with self.fake_read_values(statement_answer):
                        with mock.patch.object(
                            hook,
                            "_args_json_env_tail_unrestorable",
                            return_value=rule_answer,
                        ):
                            result = self.reading(body)
                    self.assertEqual(result.unrestorable, rule_answer or statement_answer)


class TestBothReadings(HookTestCase):
    """AC-5 (TS-11): a payload read under both extglob settings is
    unrestorable when the rule answers true under only one of them (FR2;
    TM-4)."""

    BODY = EXT_LINE + "; echo hi"

    def rule_under(self, flagged_setting, seen):
        hook = self.hook

        def rule(payload, lex_map):
            seen.append(hook._lex_extglob)
            return hook._lex_extglob == flagged_setting

        return mock.patch.object(hook, "_args_json_env_tail_unrestorable", rule)

    def test_true_under_only_one_setting_makes_the_route_unrestorable(self):
        statement = self.statement(self.BODY)
        for entry_extglob in (False, True):
            for flagged_setting in (False, True):
                with self.subTest(entry_extglob=entry_extglob, flagged_setting=flagged_setting):
                    seen = []
                    self.set_states(False, False, entry_extglob)
                    with self.rule_under(flagged_setting, seen):
                        result = self.read(statement)
                    self.assertEqual(seen, [entry_extglob, not entry_extglob])
                    self.assertTrue(result.unrestorable)
                    self.assertFalse(result.overrun)

    def test_false_under_both_settings_leaves_the_route_restorable(self):
        statement = self.statement(self.BODY)
        for entry_extglob in (False, True):
            with self.subTest(entry_extglob=entry_extglob):
                seen = []
                self.set_states(False, False, entry_extglob)
                with mock.patch.object(
                    self.hook,
                    "_args_json_env_tail_unrestorable",
                    lambda payload, lex_map: seen.append(self.hook._lex_extglob) or False,
                ):
                    result = self.read(statement)
                self.assertEqual(seen, [entry_extglob, not entry_extglob])
                self.assertFalse(result.unrestorable)

    def test_a_delimiter_unreadable_under_extglob_on_only_is_unrestorable(self):
        # The parenthesis and the here-document operator are on one line:
        # extglob off discards that line, so the operator is no unreadable
        # delimiter there; extglob on reads it, and the word is in its tail.
        body = EXT_LINE + "; " + HEREDOC + "mcp-bridge" + CALL
        self.assertFalse(self.lex(body, extglob=False).unreadable)
        self.assertTrue(self.lex(body, extglob=True).unreadable)
        statement = self.statement(body)
        for entry_extglob in (False, True):
            with self.subTest(entry_extglob=entry_extglob):
                self.set_states(False, False, entry_extglob)
                result = self.read(statement)
                self.assertTrue(result.unrestorable)


class TestStateRestored(HookTestCase):
    """AC-6 (TS-12): after a reading in which the rule answered true,
    `_lex_unreadable_met`, `_lex_extglob_met` and `_lex_extglob` equal their
    values at entry, for every combination of entry values (FR3; TM-5)."""

    def assert_restored_for_every_entry(self, body):
        statement = self.statement(body)
        for entry in ALL_ENTRY_STATES:
            with self.subTest(entry=entry):
                self.set_states(*entry)
                result = self.read(statement)
                self.assertTrue(result.unrestorable)
                self.assertEqual(self.states(), entry)

    def test_one_reading(self):
        self.assert_restored_for_every_entry(BODY_PLAIN)

    def test_one_reading_of_a_body_with_only_the_heredoc_text(self):
        self.assert_restored_for_every_entry(BODY_WORD_IN_HEREDOC_BODY)

    def test_two_readings_both_answering_true(self):
        self.assert_restored_for_every_entry(
            EXT_LINE + "\n" + HEREDOC + "mcp-bridge" + CALL
        )

    def test_two_readings_the_rule_true_under_extglob_on_only(self):
        self.assert_restored_for_every_entry(
            EXT_LINE + "; " + HEREDOC + "mcp-bridge" + CALL
        )

    def test_the_rule_adds_no_extglob_unit(self):
        hook = self.hook
        statement = self.statement(EXT_LINE + "; " + HEREDOC + "mcp-bridge" + CALL)
        hook._lex_ext_seen.add(("sentinel", 7))
        before = set(hook._lex_ext_seen)
        result = self.read(statement)
        self.assertTrue(result.unrestorable)
        self.assertEqual(hook._lex_ext_seen, before)


if __name__ == "__main__":
    unittest.main()
