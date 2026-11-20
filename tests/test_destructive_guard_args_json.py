"""Unit tests of the `--args-json` step of `em-workflow/hooks/destructive-guard.py`
(feature mcp-bridge-args-json-exec-guard, task0001 and task0003; FR3 to FR8,
FR11 to FR13, NFR5, TM-2 to TM-8, A4).

The case runner (em-workflow/hooks/tests/run-destructive-guard.py) pins the
verdicts of the scenario table. This module checks what the table cannot see:

- TM-3: a decoder failure that is not a JSON syntax error, and nesting deeper
  than MAX_ARGS_JSON_DEPTH, set Overrun; a JSON syntax error and a top level
  that is not an object skip the value.
- TM-4 / FR7: the scan charge of the decoded values covers each rebuilt value
  and every JSON value the walk visits; the collaborator adds it to the scanned
  total, or, when it does not fit, leaves the total unchanged, queues nothing
  and holds the scan-budget ask (the deferral).
- FR5 / A4 / D7 / FR12: a decoded top-level `command` string takes no count
  from the payload counter MAX_SHELL_PAYLOAD_EXPANSIONS; a `-c` / `eval` /
  here-string payload left unqueued by a used-up counter holds the scan-budget
  ask.
- FR4 / FR5: what the walk collects, in document order, duplicates and an
  escaped key included.
- FR3 / FR6 / FR2: which statements are inspected (the flag reading of D2).
- FR11 / D5: a static word whose quoting cannot be restored sets Unrestorable
  and holds the `args-json-unrestorable` ask.
- D6: the settled early-stop list; a deny found beside the deferred asks wins.
- NFR5: statements() calls the collaborator once per statement it yields and
  holds no other `--args-json` logic.
- FR8 / FR10: the docstring of the decision lists O1 and O2 as
  IMPLEMENTATION.md states them and none of the forms it says are not out of
  scope.

The hook has no package, so the module is loaded from its file path with
bytecode writing off for the load. statements() is driven in-process; the
decision's results are read through a spy that wraps it. The whole judgment
(main()) is driven through the hook as a subprocess. Standard library only.

A JSON escape for `$` or a backtick is written below as the six characters
backslash, `u`, `0024` (or `0060`), built by ESC_DOLLAR / ESC_BACKTICK, so the
text of a command reaches the hook as the six characters.
"""

import ast
import collections
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "em-workflow", "hooks", "destructive-guard.py")

ESC_DOLLAR = "\\" + "u0024"
ESC_BACKTICK = "\\" + "u0060"

RUN_HEAD = "mcp-bridge run --mcp desktop-commander --tool start_process --args-json "

KIND_NOTHING = "nothing"
KIND_INSPECTED = "inspected"
KIND_OVERRUN = "overrun"


def load_hook():
    """A hook module of its own, loaded with bytecode writing off (no
    `__pycache__` next to the hook); the caller's `sys.dont_write_bytecode` is
    put back on every exit."""
    spec = importlib.util.spec_from_file_location(
        "destructive_guard_args_json_under_test", HOOK
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


GUARD = load_hook()


def run_command(value):
    """An `mcp-bridge run` command whose `--args-json` value is VALUE, written
    in single quotes (VALUE holds no single quote)."""
    return RUN_HEAD + "'" + value + "'"


def kind(result):
    """The kind of a result of the decision: Overrun when the flag is set,
    Inspected when it carries a value, else Nothing (nothing to do)."""
    if result.overrun:
        return KIND_OVERRUN
    return KIND_INSPECTED if result.values else KIND_NOTHING


Flat = collections.namedtuple("Flat", ["charge", "bodies", "commands", "word"])


def sole_value(result):
    """The one decoded value of RESULT, with the result's charge."""
    (value,) = result.values
    return Flat(result.charge, value.bodies, value.commands, value.word)


class Spy:
    """The results of _mcp_bridge_args_json_chunks() over a statements() run
    for the statements whose command word is `mcp-bridge` (the statements a
    queued chunk adds are other commands), the results for every statement,
    and the statements the run yielded."""

    def __init__(self, command, early_stop=None):
        self.results = []
        self.all_results = []
        self.statements = []
        self.early_stop = [] if early_stop is None else early_stop
        original = GUARD._mcp_bridge_args_json_chunks

        def spy(shaped_words, marked):
            result = original(shaped_words, marked)
            self.all_results.append(result)
            if GUARD.head(shaped_words)[0] == "mcp-bridge":
                self.results.append(result)
            return result

        with mock.patch.object(GUARD, "_mcp_bridge_args_json_chunks", spy):
            for statement in GUARD.statements(command, early_stop=self.early_stop):
                self.statements.append(statement[0])

    def inspected(self):
        """The results that carry a decoded value, in statement order."""
        return [r for r in self.results if r.values]

    def kinds(self):
        return [kind(r) for r in self.results]


def nothing_result():
    return GUARD.ArgsJsonResult((), 0, False, False)


class TestDecoderFailure(unittest.TestCase):
    """TM-3: which decoder failures are Overrun and which skip the value."""

    VALUE = '{"command":"ls","shell":"bash"}'

    def test_failure_that_is_not_a_syntax_error_is_overrun(self):
        with mock.patch.object(
            json.JSONDecoder, "decode", side_effect=RuntimeError("decoder failed")
        ):
            spy = Spy(run_command(self.VALUE))
        self.assertEqual([KIND_OVERRUN], spy.kinds())

    def test_overrun_ends_the_scan_with_the_scan_budget_ask(self):
        with mock.patch.object(
            json.JSONDecoder, "decode", side_effect=RuntimeError("decoder failed")
        ):
            spy = Spy(run_command(self.VALUE))
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], spy.early_stop)

    def test_an_integer_the_decoder_refuses_is_overrun(self):
        limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
        if limit <= 0:
            self.skipTest("the interpreter has no integer digit limit")
        value = '{"command":"ls","n":' + "1" * (limit + 1) + "}"
        spy = Spy(run_command(value))
        self.assertEqual([KIND_OVERRUN], spy.kinds())

    def test_a_json_syntax_error_is_not_inspected(self):
        for value in ('{"command":"ls"', '{"command":}', "", "{'command':'ls'}"):
            with self.subTest(value=value):
                spy = Spy(run_command(value))
                self.assertEqual([KIND_NOTHING], spy.kinds())
                self.assertEqual([], spy.early_stop)

    def test_a_top_level_that_is_not_an_object_is_not_inspected(self):
        for value in ('["a"]', '"a"', "1", "null", "true"):
            with self.subTest(value=value):
                spy = Spy(run_command(value))
                self.assertEqual([KIND_NOTHING], spy.kinds())

    def test_nesting_above_the_bound_is_overrun_before_the_decoder_runs(self):
        deep = '{"a":' + "[" * GUARD.MAX_ARGS_JSON_DEPTH + "]" * GUARD.MAX_ARGS_JSON_DEPTH + "}"
        with mock.patch.object(
            json.JSONDecoder, "decode", side_effect=AssertionError("decoder reached")
        ):
            spy = Spy(run_command(deep))
        self.assertEqual([KIND_OVERRUN], spy.kinds())

    def test_nesting_at_the_bound_is_decoded(self):
        edge = '{"a":' + "[" * (GUARD.MAX_ARGS_JSON_DEPTH - 1) + "]" * (GUARD.MAX_ARGS_JSON_DEPTH - 1) + "}"
        spy = Spy(run_command(edge))
        self.assertEqual([KIND_INSPECTED], spy.kinds())

    def test_brackets_inside_strings_do_not_count_as_nesting(self):
        value = '{"a":"' + "[" * 300 + '","b":"\\"' + "{" * 300 + '"}'
        spy = Spy(run_command(value))
        self.assertEqual([KIND_INSPECTED], spy.kinds())

    def test_the_bound_is_one_hundred(self):
        self.assertEqual(100, GUARD.MAX_ARGS_JSON_DEPTH)

    def test_one_value_that_overruns_does_not_hide_a_static_value_before_it(self):
        deep = '{"a":' + "[" * GUARD.MAX_ARGS_JSON_DEPTH + "]" * GUARD.MAX_ARGS_JSON_DEPTH + "}"
        command = RUN_HEAD + "'" + self.VALUE + "' --args-json '" + deep + "'"
        (result,) = Spy(command).results
        self.assertTrue(result.overrun)
        self.assertEqual(1, len(result.values))


class TestCharge(unittest.TestCase):
    """TM-4, FR7: the scan charge of the decoded values, and how the
    collaborator adds it to the scanned total."""

    def count_values(self, node):
        """The number of JSON values in NODE, itself included."""
        if isinstance(node, dict):
            return 1 + sum(self.count_values(v) for v in node.values())
        if isinstance(node, list):
            return 1 + sum(self.count_values(v) for v in node)
        return 1

    def test_the_charge_covers_the_value_and_every_value_visited(self):
        value = '{"a":"x","b":[1,2,{"c":null}],"d":{"e":["f","g"]}}'
        spy = Spy(run_command(value))
        (result,) = spy.inspected()
        floor = len(value) + self.count_values(json.loads(value))
        self.assertGreaterEqual(result.charge, floor)

    def test_the_charge_grows_with_the_strings_searched(self):
        small = Spy(run_command('{"a":"x"}')).inspected()[0].charge
        large = Spy(run_command('{"a":"' + "x" * 500 + '"}')).inspected()[0].charge
        self.assertGreaterEqual(large - small, 500)

    def test_the_charge_of_a_rebuilt_value_counts_its_decoded_length(self):
        # The rebuilt value is the text written here (single quotes keep the
        # JSON escapes): its length is part of the charge.
        value = '{"a":"' + ESC_DOLLAR * 20 + '"}'
        (result,) = Spy(run_command(value)).inspected()
        self.assertGreaterEqual(result.charge, len(value) + 2)

    def test_the_charge_of_two_values_covers_both(self):
        first, second = '{"a":"x"}', '{"b":"yy"}'
        command = RUN_HEAD + "'" + first + "' --args-json '" + second + "'"
        (result,) = Spy(command).inspected()
        self.assertGreaterEqual(result.charge, len(first) + len(second) + 2 + 2)

    def test_the_charge_is_added_to_the_scanned_total(self):
        word_command = run_command('{"command":"ls"}')
        word = None

        def capture(shaped_words, marked):
            nonlocal word
            word = shaped_words[-1]
            return nothing_result()

        with mock.patch.object(GUARD, "_mcp_bridge_args_json_chunks", capture):
            list(GUARD.statements(word_command))
        self.assertIsNotNone(word)

        def inspected(charge):
            def step(shaped_words, marked):
                if GUARD.head(shaped_words)[0] != "mcp-bridge":
                    return nothing_result()
                value = GUARD.ArgsJsonValue(word, ("echo body",), ())
                return GUARD.ArgsJsonResult((value,), charge, False, False)

            return step

        huge = inspected(10 ** 6)
        huge.__name__ = "huge"
        small = inspected(1)
        small.__name__ = "small"

        for step, stop in ((huge, True), (small, False)):
            early_stop = []
            with mock.patch.object(GUARD, "_mcp_bridge_args_json_chunks", step):
                texts = [s[0] for s in GUARD.statements(word_command, early_stop=early_stop)]
            with self.subTest(charge=step.__name__):
                self.assertEqual([GUARD.SCAN_BUDGET_ASK] if stop else [], early_stop)
                self.assertEqual(not stop, "echo body" in texts)


class TestPayloadCounter(unittest.TestCase):
    """AC-6 (FR5, FR12, A4, D7): a decoded top-level `command` string takes no
    count from the payload counter; a `-c` payload that the used-up counter
    leaves unqueued holds the scan-budget ask."""

    VALUE = (
        '{"command":"echo MARK-CMD ' + ESC_DOLLAR + '(echo MARK-BODY)","shell":"bash"}'
    )

    def command_after(self, payloads):
        """A command whose `mcp-bridge run` statement follows PAYLOADS
        `bash -c` payloads."""
        return "; ".join(["bash -c 'true'"] * payloads + [run_command(self.VALUE)])

    def yielded(self, command, early_stop=None):
        return [s[0] for s in GUARD.statements(command, early_stop=early_stop)]

    def test_the_counter_is_twenty_five(self):
        self.assertEqual(25, GUARD.MAX_SHELL_PAYLOAD_EXPANSIONS)

    def test_with_the_counter_used_up_the_command_string_is_still_queued(self):
        texts = self.yielded(self.command_after(GUARD.MAX_SHELL_PAYLOAD_EXPANSIONS))
        self.assertIn("echo MARK-BODY", texts)
        self.assertTrue(any(t.startswith("echo MARK-CMD") for t in texts), texts)

    def test_with_one_count_left_both_are_queued(self):
        texts = self.yielded(self.command_after(GUARD.MAX_SHELL_PAYLOAD_EXPANSIONS - 1))
        self.assertIn("echo MARK-BODY", texts)
        self.assertTrue(any(t.startswith("echo MARK-CMD") for t in texts), texts)

    def test_a_command_string_takes_no_count(self):
        value = '{"command":"echo MARK-ONE","command":"echo MARK-TWO"}'
        # With the counter used up, or nearly, every command string is queued.
        for payloads in (0, 23, 24, 25):
            command = "; ".join(["bash -c 'true'"] * payloads + [run_command(value)])
            texts = self.yielded(command)
            with self.subTest(payloads=payloads):
                self.assertIn("echo MARK-ONE", texts)
                self.assertIn("echo MARK-TWO", texts)

    def test_command_strings_ahead_leave_the_counter_alone(self):
        value = "{" + ",".join('"command":"echo MARK-C%d"' % n for n in range(30)) + "}"
        command = run_command(value) + "; bash -c 'echo MARK-PAYLOAD'"
        early_stop = []
        texts = self.yielded(command, early_stop)
        self.assertIn("echo MARK-PAYLOAD", texts)
        self.assertEqual([], early_stop)
        for n in range(30):
            self.assertIn("echo MARK-C%d" % n, texts)

    def test_a_payload_after_the_counter_is_used_up_is_not_queued_and_holds_the_ask(self):
        command = "; ".join(["bash -c 'true'"] * 25 + ["bash -c 'echo MARK-26'"])
        early_stop = []
        texts = self.yielded(command, early_stop)
        self.assertNotIn("echo MARK-26", texts)
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], early_stop)

    def test_the_twenty_fifth_payload_is_queued_and_holds_no_ask(self):
        command = "; ".join(["bash -c 'true'"] * 24 + ["bash -c 'echo MARK-25'"])
        early_stop = []
        texts = self.yielded(command, early_stop)
        self.assertIn("echo MARK-25", texts)
        self.assertEqual([], early_stop)

    def test_a_blank_payload_after_the_counter_is_used_up_holds_no_ask(self):
        command = "; ".join(["bash -c 'true'"] * 25 + ["bash -c '  '"])
        early_stop = []
        self.yielded(command, early_stop)
        self.assertEqual([], early_stop)

    def test_the_other_payload_forms_are_counted_and_hold_the_ask_too(self):
        for label, last in (
            ("eval", "eval 'echo MARK-LAST'"),
            ("here-string", "bash <<< 'echo MARK-LAST'"),
        ):
            command = "; ".join(["bash -c 'true'"] * 25 + [last])
            early_stop = []
            texts = self.yielded(command, early_stop)
            with self.subTest(label):
                self.assertNotIn("echo MARK-LAST", texts)
                self.assertEqual([GUARD.SCAN_BUDGET_ASK], early_stop)

    def test_a_payload_in_a_substitution_body_holds_the_ask_too(self):
        command = "; ".join(
            ["bash -c 'true'"] * 25 + ['echo "$(bash -c \'echo MARK-SUB\')"']
        )
        early_stop = []
        texts = self.yielded(command, early_stop)
        self.assertNotIn("echo MARK-SUB", texts)
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], early_stop)

    def test_the_settled_ask_is_emitted_when_there_is_no_early_stop_list(self):
        command = "; ".join(["bash -c 'true'"] * 25 + ["bash -c 'echo MARK-26'"])

        class Emitted(Exception):
            pass

        with mock.patch.object(GUARD, "decide", side_effect=Emitted) as decide:
            with self.assertRaises(Emitted):
                list(GUARD.statements(command))
        decide.assert_called_once_with("ask", *GUARD.SCAN_BUDGET_ASK)

    def test_the_component_returns_the_command_string_and_the_body(self):
        # What the collaborator then queues: the body and the command string,
        # neither against the counter.
        (result,) = Spy(run_command(self.VALUE)).inspected()
        value = sole_value(result)
        self.assertEqual(("echo MARK-CMD $(echo MARK-BODY)",), value.commands)
        self.assertEqual(("echo MARK-BODY",), value.bodies)


class TestWalk(unittest.TestCase):
    """FR4, FR5, TM-2: what the walk collects."""

    def result(self, value):
        (result,) = Spy(run_command(value)).inspected()
        return sole_value(result)

    def test_bodies_of_every_string_at_every_depth_in_document_order(self):
        value = (
            '{"a":"' + ESC_DOLLAR + '(echo A)","b":[1,"' + ESC_BACKTICK + 'echo B'
            + ESC_BACKTICK + '",{"c":{"d":"' + ESC_DOLLAR + '(echo D)"}}],"e":"' + ESC_DOLLAR + '(echo E)"}'
        )
        self.assertEqual(
            ("echo A", "echo B", "echo D", "echo E"), self.result(value).bodies
        )

    def test_a_command_below_the_top_level_gets_only_the_candidate_search(self):
        value = '{"a":{"command":"git branch -D example"},"b":[{"command":"x"}]}'
        result = self.result(value)
        self.assertEqual((), result.commands)
        self.assertEqual((), result.bodies)

    def test_every_top_level_command_string_is_collected_duplicates_included(self):
        value = '{"command":"first","x":1,"command":"second","command":"third"}'
        self.assertEqual(("first", "second", "third"), self.result(value).commands)

    def test_a_blank_or_non_string_command_is_not_collected(self):
        value = '{"command":"  ","command":5,"command":["ls"],"command":null,"command":"ls"}'
        self.assertEqual(("ls",), self.result(value).commands)

    def test_a_key_written_with_a_json_escape_is_the_decoded_key(self):
        value = '{"' + "\\" + 'u0063ommand":"git branch -D example"}'
        self.assertEqual(("git branch -D example",), self.result(value).commands)

    def test_object_keys_are_not_searched(self):
        value = '{"' + ESC_DOLLAR + '(echo K)":"v"}'
        self.assertEqual((), self.result(value).bodies)

    def test_a_blank_body_is_not_collected(self):
        value = '{"a":"' + ESC_DOLLAR + '(  )","b":"' + ESC_BACKTICK + ESC_BACKTICK + '"}'
        self.assertEqual((), self.result(value).bodies)

    def test_a_repeated_nested_key_keeps_every_pair(self):
        value = (
            '{"msg":{"text":"' + ESC_DOLLAR + '(echo FIRST)","text":"' + ESC_DOLLAR + '(echo SECOND)"}}'
        )
        self.assertEqual(("echo FIRST", "echo SECOND"), self.result(value).bodies)

    def test_the_walk_survives_a_wide_value(self):
        value = "{" + ",".join('"k%d":["x","y"]' % n for n in range(2000)) + "}"
        result = self.result(value)
        self.assertGreaterEqual(result.charge, len(value) + 3 * 2000)

    def test_the_anchor_word_is_the_value_word(self):
        result = self.result('{"command":"ls"}')
        self.assertEqual('{"command":"ls"}', str(result.word))


def inspected_value_words(spy):
    """The anchor words of every decoded value of the run, in order."""
    return [str(v.word) for r in spy.results for v in r.values]


class TestFlagReading(unittest.TestCase):
    """AC-2, AC-3, AC-4 (FR1, FR2, FR3, FR6, D2): which statements are
    inspected."""

    VALUE = "'{\"command\":\"ls\"}'"

    def kinds(self, command):
        return Spy(command).kinds()

    def test_the_notion_pair_is_not_inspected(self):
        command = (
            "mcp-bridge run --mcp notion --tool notion-create-comment --args-json "
            "'{\"body\":\"x\"}'"
        )
        self.assertEqual([KIND_NOTHING], self.kinds(command))

    def test_the_notion_pair_in_another_flag_order_is_not_inspected(self):
        command = (
            "mcp-bridge run --tool notion-create-comment --dry-run --args-json "
            "'{\"body\":\"x\"}' --mcp notion --format json"
        )
        self.assertEqual([KIND_NOTHING], self.kinds(command))

    def test_an_excluded_statement_sets_no_unrestorable_flag(self):
        command = (
            "mcp-bridge run --mcp notion --tool notion-create-comment --args-json "
            "$'{\"body\":\"x\"}\\0'"
        )
        spy = Spy(command)
        (result,) = spy.results
        self.assertEqual(nothing_result(), result)
        self.assertEqual([], spy.early_stop)

    def test_other_forms_that_read_as_flags_are_inspected(self):
        value = self.VALUE
        for label, command in (
            ("another server", "mcp-bridge run --mcp other --tool notion-create-comment --args-json " + value),
            ("another tool", "mcp-bridge run --mcp notion --tool other --args-json " + value),
            ("no pair", "mcp-bridge run --args-json " + value),
            ("repeated mcp", "mcp-bridge run --mcp notion --mcp other --tool notion-create-comment --args-json " + value),
            ("quoted notion", "mcp-bridge run --mcp 'notion' --tool notion-create-comment --args-json " + value),
            ("quoted tool", "mcp-bridge run --mcp notion --tool 'notion-create-comment' --args-json " + value),
            ("flags first", "mcp-bridge run --dry-run --format json --session s --args-json " + value),
            ("path command", "/usr/local/bin/mcp-bridge run --args-json " + value),
            ("behind env", "env mcp-bridge run --args-json " + value),
        ):
            with self.subTest(label):
                self.assertEqual([KIND_INSPECTED], self.kinds(command))

    def test_the_notion_pair_written_with_a_quoted_flag_name_is_inspected(self):
        value = self.VALUE
        for label, command in (
            ("quoted mcp", "mcp-bridge run '--mcp' notion --tool notion-create-comment --args-json " + value),
            ("quoted tool", "mcp-bridge run --mcp notion '--tool' notion-create-comment --args-json " + value),
            ("quoted args-json", "mcp-bridge run --mcp notion --tool notion-create-comment '--args-json' " + value),
            ("double-quoted mcp", 'mcp-bridge run "--mcp" notion --tool notion-create-comment --args-json ' + value),
            ("backslashed mcp", "mcp-bridge run \\--mcp notion --tool notion-create-comment --args-json " + value),
        ):
            with self.subTest(label):
                self.assertEqual([KIND_INSPECTED], self.kinds(command))

    def test_a_quoted_double_quoted_or_backslashed_flag_name_is_inspected(self):
        value = self.VALUE
        for label, command in (
            ("single-quoted", "mcp-bridge run '--args-json' " + value),
            ("double-quoted", 'mcp-bridge run "--args-json" ' + value),
            ("backslashed", "mcp-bridge run \\--args-json " + value),
            ("partly quoted", "mcp-bridge run --args'-'json " + value),
        ):
            with self.subTest(label):
                spy = Spy(command)
                self.assertEqual([KIND_INSPECTED], spy.kinds())
                self.assertEqual(("ls",), sole_value(spy.results[0]).commands)

    def test_the_equals_form_is_inspected(self):
        for label, command in (
            ("single-quoted value", "mcp-bridge run --args-json='{\"command\":\"ls\"}'"),
            ("double-quoted value", 'mcp-bridge run --args-json="{\\"command\\":\\"ls\\"}"'),
            ("single dash", "mcp-bridge run -args-json='{\"command\":\"ls\"}'"),
        ):
            with self.subTest(label):
                spy = Spy(command)
                self.assertEqual([KIND_INSPECTED], spy.kinds())
                value = sole_value(spy.results[0])
                self.assertEqual(("ls",), value.commands)
                # The anchor is the flag word of the `=` form.
                self.assertTrue(str(value.word).endswith('"command":"ls"}'), str(value.word))
                self.assertIn("args-json=", str(value.word))

    def test_single_dash_flags_are_inspected(self):
        command = "mcp-bridge run -mcp x -tool y -args-json " + self.VALUE
        self.assertEqual([KIND_INSPECTED], self.kinds(command))

    def test_a_value_before_the_terminator_or_a_positional_word_is_inspected(self):
        value = self.VALUE
        for label, command in (
            ("terminator", "mcp-bridge run --args-json " + value + " -- x"),
            ("terminator and a flag", "mcp-bridge run --args-json " + value + " -- --unknown"),
            ("positional", "mcp-bridge run --args-json " + value + " pos"),
            ("positional and a flag", "mcp-bridge run --args-json " + value + " pos --unknown"),
            # A restored text shorter than two characters (a lone `-`, the empty
            # text) is a positional word and ends the flag sequence (D2 step 2).
            ("a lone dash", "mcp-bridge run --args-json " + value + " -"),
            ("a lone dash and a flag", "mcp-bridge run --args-json " + value + " - --unknown"),
            ("an empty single-quoted word", "mcp-bridge run --args-json " + value + " ''"),
            ("a single-quoted lone dash", "mcp-bridge run --args-json " + value + " '-'"),
        ):
            with self.subTest(label):
                self.assertEqual([KIND_INSPECTED], self.kinds(command))

    def test_a_value_after_a_lone_dash_is_not_inspected(self):
        # The lone dash ends the flag sequence: the value before it is
        # inspected, the value after it is not read as a flag value.
        command = (
            "mcp-bridge run --args-json '{\"command\":\"first\"}'"
            " - --args-json '{\"command\":\"second\"}'"
        )
        (result,) = Spy(command).results
        self.assertEqual([("first",)], [v.commands for v in result.values])

    def test_every_value_of_a_repeated_args_json_is_inspected(self):
        command = (
            "mcp-bridge run --args-json '{\"command\":\"first\"}'"
            " --args-json '{\"command\":\"second\"}' --args-json=\"{\\\"command\\\":\\\"third\\\"}\""
        )
        spy = Spy(command)
        (result,) = spy.results
        self.assertEqual(
            [("first",), ("second",), ("third",)], [v.commands for v in result.values]
        )

    def test_a_repeated_args_json_is_judged_value_by_value(self):
        command = (
            "mcp-bridge run --args-json '{\"command\":\"first\"}'"
            " --args-json \"$ARGS\" --args-json '[1]' --args-json '{\"command\":\"last\"}'"
        )
        (result,) = Spy(command).results
        self.assertEqual([("first",), ("last",)], [v.commands for v in result.values])
        self.assertFalse(result.unrestorable)

    def test_a_destination_that_is_not_static_is_inspected(self):
        value = self.VALUE
        for label, command in (
            ("server", 'mcp-bridge run --mcp "$S" --args-json ' + value),
            ("tool", "mcp-bridge run --tool $T --args-json " + value),
            ("both", "mcp-bridge run --mcp $(echo s) --tool `echo t` --args-json " + value),
            ("format and session", "mcp-bridge run --format $F --session $(x) --args-json " + value),
            # The `=` form of a known value-taking name whose value part is not
            # static is a value-taking flag with a non-static inline value (D2
            # step 1, FR3 (c)); it does not stop the inspection (FR3 (g)).
            ("equals form with a destination", 'mcp-bridge run --mcp="$S" --args-json ' + value),
            ("equals form with an unquoted variable as the tool name", "mcp-bridge run --tool=$T --args-json " + value),
            ("equals form with a double-quoted variable as the session name", 'mcp-bridge run --session="$SID" --args-json ' + value),
        ):
            with self.subTest(label):
                self.assertEqual([KIND_INSPECTED], self.kinds(command))

    def test_the_value_beside_an_equals_form_destination_that_is_not_static_is_read(self):
        # The one inspected value of `--mcp="$S" --args-json '{"command":"ls"}'`
        # holds exactly the command string ls, and the Unrestorable flag is not
        # set (FR3 (c), (g)).
        command = 'mcp-bridge run --mcp="$S" --args-json ' + self.VALUE
        spy = Spy(command)
        (result,) = spy.inspected()
        self.assertEqual(("ls",), sole_value(result).commands)
        self.assertFalse(result.unrestorable)

    def test_forms_that_are_not_inspected(self):
        value = self.VALUE
        for label, command in (
            ("unknown flag", "mcp-bridge run --unknown x --args-json " + value),
            ("unknown single dash", "mcp-bridge run -unknown --args-json " + value),
            ("unknown flag after the value", "mcp-bridge run --args-json " + value + " --unknown"),
            ("three dashes", "mcp-bridge run ---args-json " + value),
            ("no value", "mcp-bridge run --args-json"),
            ("no value after a value", "mcp-bridge run --args-json " + value + " --mcp"),
            ("no value of another flag", "mcp-bridge run --args-json " + value + " --tool"),
            ("no args-json", "mcp-bridge run --mcp other --tool t"),
            ("only a dry run", "mcp-bridge run --dry-run"),
            ("not run", "mcp-bridge list --args-json " + value),
            ("no subcommand", "mcp-bridge"),
            ("run only", "mcp-bridge run"),
            ("terminator before the flag", "mcp-bridge run -- --args-json " + value),
            ("positional before the flag", "mcp-bridge run pos --args-json " + value),
            # A lone dash is a positional word: it ends the flag sequence before
            # any `--args-json` is read.
            ("a lone dash before the flag (positional)", "mcp-bridge run - --args-json " + value),
        ):
            with self.subTest(label):
                self.assertEqual([KIND_NOTHING], self.kinds(command))

    def test_a_flag_position_word_that_is_not_static_is_not_inspected(self):
        value = self.VALUE
        for label, command in (
            ("variable", "mcp-bridge run $OPTS --args-json " + value),
            ("quoted variable", 'mcp-bridge run "$OPTS" --args-json ' + value),
            ("substitution", "mcp-bridge run $(echo --dry-run) --args-json " + value),
            ("glob", "mcp-bridge run --args-j* " + value),
            ("after a value", "mcp-bridge run --args-json " + value + " $OPTS"),
            ("after a first flag", "mcp-bridge run --dry-run $OPTS --args-json " + value),
            # An `=`-form word whose name part is not static, or whose name is
            # unknown, leaves the statement not inspected (D2 step 1, FR6 (2),
            # (3)); only a known value-taking name with a non-static value part
            # is read on (see the test of a destination that is not static).
            ("equals form with a name part that is not static", "mcp-bridge run --$N=x --args-json " + value),
            ("equals form of an unknown name with a non-static value part", 'mcp-bridge run --unknown="$S" --args-json ' + value),
        ):
            with self.subTest(label):
                spy = Spy(command)
                self.assertEqual([KIND_NOTHING], spy.kinds())
                self.assertFalse(spy.results[0].unrestorable)

    def test_a_non_static_value_word_is_not_inspected(self):
        for label, command in (
            ("substitution", "mcp-bridge run --args-json \"$(cat args.json)\""),
            ("variable", "mcp-bridge run --args-json \"$ARGS\""),
            ("unquoted variable", "mcp-bridge run --args-json $ARGS"),
            ("backtick", "mcp-bridge run --args-json `cat args.json`"),
            ("unquoted glob", "mcp-bridge run --args-json {*}"),
            ("tilde", "mcp-bridge run --args-json ~/args.json"),
            ("arithmetic", "mcp-bridge run --args-json $((1+2))"),
            ("parameter expansion", "mcp-bridge run --args-json ${ARGS}"),
            ("locale quote with an expansion", 'mcp-bridge run --args-json $"{\\"a\\":$X}"'),
            ("equals form with a substitution", 'mcp-bridge run --args-json="$(cat a.json)"'),
        ):
            with self.subTest(label):
                spy = Spy(command)
                self.assertEqual([KIND_NOTHING], spy.kinds())
                self.assertFalse(spy.results[0].unrestorable)

    def test_the_command_word_that_is_text_of_another_command_is_not_inspected(self):
        command = "echo \"mcp-bridge run --args-json '{\\\"command\\\":\\\"ls\\\"}'\""
        spy = Spy(command)
        self.assertEqual([nothing_result()], spy.all_results)
        self.assertEqual([], spy.results)

    def test_value_forms_are_rebuilt_under_bash_quoting(self):
        escaped_double = '"{\\"command\\":\\"git branch -D example\\"}"'
        ansi_c = "$'{\"command\":\"git branch -D example\"}'"
        joined = "'{\"command\":'\"\"'\"git branch -D example\"}'"
        for label, word in (("double", escaped_double), ("ansi-c", ansi_c), ("joined", joined)):
            with self.subTest(label):
                spy = Spy("mcp-bridge run --args-json " + word)
                (result,) = spy.inspected()
                self.assertEqual(("git branch -D example",), sole_value(result).commands)

    def test_candidate_residue_in_single_quotes_does_not_make_the_word_unreadable(self):
        # The raw `$(` sits in single quotes: Bash passes it on as text.
        command = run_command('{"command":"echo $(echo MARK)"}')
        (result,) = Spy(command).inspected()
        value = sole_value(result)
        self.assertEqual(("echo $(echo MARK)",), value.commands)
        self.assertEqual(("echo MARK",), value.bodies)

    def test_a_real_substitution_in_the_value_word_makes_it_unreadable(self):
        command = "mcp-bridge run --args-json '{\"command\":\"ls\"}'\"$(echo x)\""
        self.assertEqual([KIND_NOTHING], Spy(command).kinds())

    def test_the_anchor_of_a_queued_chunk_is_the_value_word_in_document_order(self):
        value = (
            '{"command":"echo MARK-CMD","a":"' + ESC_DOLLAR + '(echo MARK-BODY)"}'
        )
        origins = {}
        for statement in GUARD.statements(run_command(value), early_stop=[]):
            origins[statement[0]] = statement[5][0]
        # Tokens: mcp-bridge run --mcp x --tool y --args-json VALUE (index 7).
        # Bodies come first (ordinal 1), then the command string (ordinal 2).
        self.assertEqual(((0, 7, 1),), origins["echo MARK-BODY"])
        self.assertEqual(((0, 7, 2),), origins["echo MARK-CMD"])

    def test_the_anchor_of_the_equals_form_is_the_flag_word(self):
        command = "mcp-bridge run --mcp x --tool y --args-json='{\"command\":\"echo MARK-CMD\"}'"
        origins = {}
        for statement in GUARD.statements(command, early_stop=[]):
            origins[statement[0]] = statement[5][0]
        self.assertEqual(((0, 6, 1),), origins["echo MARK-CMD"])


class TestUnrestorable(unittest.TestCase):
    """AC-5 (FR11, D5, TM-7): a static word whose quoting cannot be restored
    sets Unrestorable and holds the `args-json-unrestorable` ask."""

    VALUE = "'{\"command\":\"ls\"}'"

    # The ways to write a word whose quoting cannot be restored, each as the
    # word VALUE_TEXT (the JSON value written inside the quote) at the end.
    VALUE_WORDS = (
        ("ansi-c NUL", "$'{\"command\":\"ls\"}\\0'"),
        ("ansi-c non-ASCII", "$'{\"command\":\"ls\"}\\u00e9'"),
        ("ansi-c hex non-ASCII", "$'{\"command\":\"ls\"}\\xe9'"),
        ("ansi-c unhandled escape", "$'{\"command\":\"ls\"}\\d'"),
        ("locale quote", '$"{\\"command\\":\\"ls\\"}"'),
    )
    FLAG_WORDS = (
        ("ansi-c NUL", "$'--mcp\\0'"),
        ("ansi-c non-ASCII", "$'--mcp\\u00e9'"),
        ("ansi-c unhandled escape", "$'--mcp\\d'"),
        ("locale quote", '$"--mcp"'),
    )

    def test_a_value_word_that_cannot_be_restored_sets_unrestorable(self):
        for label, word in self.VALUE_WORDS:
            with self.subTest(label):
                spy = Spy("mcp-bridge run --args-json " + word)
                (result,) = spy.results
                self.assertTrue(result.unrestorable)
                self.assertEqual((), result.values)
                self.assertFalse(result.overrun)

    def test_the_inline_value_of_the_equals_form_sets_unrestorable(self):
        for label, word in self.VALUE_WORDS:
            with self.subTest(label):
                spy = Spy("mcp-bridge run --args-json=" + word)
                (result,) = spy.results
                self.assertTrue(result.unrestorable)
                self.assertEqual((), result.values)

    def test_a_flag_position_word_that_cannot_be_restored_sets_unrestorable(self):
        for label, word in self.FLAG_WORDS:
            with self.subTest(label):
                spy = Spy("mcp-bridge run " + word + " x --args-json " + self.VALUE)
                (result,) = spy.results
                self.assertTrue(result.unrestorable)

    def test_a_flag_position_word_that_cannot_be_restored_leaves_no_value_inspected(self):
        for label, word in self.FLAG_WORDS:
            for where, command in (
                ("before", "mcp-bridge run " + word + " x --args-json " + self.VALUE),
                ("after", "mcp-bridge run --args-json " + self.VALUE + " " + word + " x"),
            ):
                with self.subTest(label, where=where):
                    (result,) = Spy(command).results
                    self.assertEqual((), result.values)
                    self.assertTrue(result.unrestorable)

    def test_a_word_that_also_holds_a_non_static_element_sets_nothing(self):
        for label, word in (
            ("variable", "$'\\0'$X"),
            ("glob", "$'\\0'*"),
            ("substitution", "$'\\0'\"$(echo x)\""),
            ("locale quote with an expansion", '$"{\\"a\\":$X}"'),
            ("backtick", "$'\\u00e9'`echo x`"),
        ):
            with self.subTest(label, position="value"):
                spy = Spy("mcp-bridge run --args-json " + word)
                (result,) = spy.results
                self.assertFalse(result.unrestorable)
                self.assertEqual((), result.values)
                self.assertEqual([], spy.early_stop)
            with self.subTest(label, position="flag"):
                spy = Spy("mcp-bridge run " + word + " --args-json " + self.VALUE)
                (result,) = spy.results
                self.assertFalse(result.unrestorable)
                self.assertEqual((), result.values)
                self.assertEqual([], spy.early_stop)

    def test_the_notion_pair_sets_nothing(self):
        command = (
            "mcp-bridge run --mcp notion --tool notion-create-comment --args-json "
            "$'{\"body\":\"x\"}\\0'"
        )
        spy = Spy(command)
        (result,) = spy.results
        self.assertFalse(result.unrestorable)
        self.assertEqual([], spy.early_stop)

    def test_a_static_value_beside_an_unrestorable_one_is_still_inspected(self):
        command = (
            "mcp-bridge run --args-json " + self.VALUE + " --args-json $'{\"a\":1}\\0'"
        )
        (result,) = Spy(command).results
        self.assertTrue(result.unrestorable)
        self.assertEqual([("ls",)], [v.commands for v in result.values])

    def test_a_static_word_is_not_unrestorable(self):
        spy = Spy("mcp-bridge run --args-json " + self.VALUE)
        (result,) = spy.results
        self.assertFalse(result.unrestorable)
        self.assertEqual([], spy.early_stop)

    def test_the_ask_constant(self):
        rule, reason = GUARD.ARGS_JSON_UNRESTORABLE_ASK
        self.assertEqual("args-json-unrestorable", rule)
        self.assertTrue(reason.strip())
        self.assertNotEqual(GUARD.SCAN_BUDGET_ASK, GUARD.ARGS_JSON_UNRESTORABLE_ASK)

    def test_the_settled_early_stop_list_is_the_unrestorable_ask_alone(self):
        for label, word in self.VALUE_WORDS:
            with self.subTest(label):
                spy = Spy("mcp-bridge run --args-json " + word)
                self.assertEqual([GUARD.ARGS_JSON_UNRESTORABLE_ASK], spy.early_stop)

    def test_the_settled_early_stop_list_is_the_scan_budget_ask_alone_when_both_are_held(self):
        # A 26th payload the counter leaves unqueued holds the scan-budget ask
        # beside the unrestorable word's ask: the stronger one stands.
        command = "; ".join(
            ["bash -c 'true'"] * 25
            + ["bash -c 'echo MARK-26'", "mcp-bridge run --args-json $'{\"a\":1}\\0'"]
        )
        spy = Spy(command)
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], spy.early_stop)

    def test_the_unrestorable_ask_stands_beside_an_overrun_only_as_the_scan_budget_ask(self):
        deep = '{"a":' + "[" * GUARD.MAX_ARGS_JSON_DEPTH + "]" * GUARD.MAX_ARGS_JSON_DEPTH + "}"
        command = (
            "mcp-bridge run --args-json $'{\"a\":1}\\0'; " + run_command(deep)
        )
        spy = Spy(command)
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], spy.early_stop)

    def test_with_no_early_stop_list_the_ask_is_emitted(self):
        class Emitted(Exception):
            pass

        command = "mcp-bridge run --args-json $'{\"a\":1}\\0'"
        with mock.patch.object(GUARD, "decide", side_effect=Emitted) as decide:
            with self.assertRaises(Emitted):
                list(GUARD.statements(command))
        decide.assert_called_once_with("ask", *GUARD.ARGS_JSON_UNRESTORABLE_ASK)

    def test_the_ask_is_held_until_the_queue_is_drained(self):
        # Every statement of the queued payload is still yielded before the
        # settled ask ends the run.
        command = "bash -c 'echo MARK-PAYLOAD'; mcp-bridge run --args-json $'{\"a\":1}\\0'"
        spy = Spy(command)
        self.assertIn("echo MARK-PAYLOAD", spy.statements)
        self.assertEqual([GUARD.ARGS_JSON_UNRESTORABLE_ASK], spy.early_stop)


class TestDeferral(unittest.TestCase):
    """AC-7 (FR7, D3, D6, TM-3, TM-4): on Overrun and on a charge that does
    not fit, the scanned total is unchanged, nothing of the statement is
    queued, the step does nothing for later statements, and the scan-budget
    ask is held until the queue is drained."""

    DEEP = '{"a":' + "[" * GUARD.MAX_ARGS_JSON_DEPTH + "]" * GUARD.MAX_ARGS_JSON_DEPTH + "}"

    def call(self, result, scanned=0, budget=1000, lexed=True, asks=None):
        """The collaborator over a fixed decision RESULT: (pending, scan,
        asks, how many times the decision was asked)."""
        pending = []
        scan = GUARD._ScanState(budget)
        scan.scanned = scanned
        asks = GUARD._DeferredAsks() if asks is None else asks
        calls = []

        def decision(shaped_words, marked):
            calls.append(1)
            return result

        with mock.patch.object(GUARD, "_mcp_bridge_args_json_chunks", decision):
            GUARD._queue_args_json_chunks(
                ["mcp-bridge", "run"], None, ["w1", "w2"], lexed, ("anchor",), 3,
                GUARD.PY_BODY, pending, scan, asks,
            )
        return pending, scan, asks, len(calls)

    def value(self, word="w2", bodies=("echo B1", "echo B2"), commands=("echo C1",)):
        return GUARD.ArgsJsonValue(word, bodies, commands)

    def inspected(self, charge, *values):
        return GUARD.ArgsJsonResult(values or (self.value(),), charge, False, False)

    def test_a_charge_that_fits_is_added_and_everything_is_queued(self):
        pending, scan, asks, _ = self.call(self.inspected(40), scanned=100)
        self.assertEqual(140, scan.scanned)
        # Bodies first, then the command strings, each anchored at the
        # statement's anchor plus (statement index, word index, ordinal).
        self.assertEqual(
            [
                ("echo B1", ("anchor", (3, 1, 1)), None, GUARD.PY_BODY),
                ("echo B2", ("anchor", (3, 1, 2)), None, GUARD.PY_BODY),
                ("echo C1", ("anchor", (3, 1, 3)), None, GUARD.PY_BODY),
            ],
            [tuple(entry) for entry in pending],
        )
        self.assertIsNone(asks.strongest())

    def test_a_charge_that_reaches_the_budget_exactly_still_fits(self):
        pending, scan, asks, _ = self.call(self.inspected(40), scanned=960, budget=1000)
        self.assertEqual(1000, scan.scanned)
        self.assertEqual(3, len(pending))
        self.assertIsNone(asks.strongest())

    def test_an_entry_carries_the_derived_mark_and_no_substitution_index(self):
        pending, _scan, _asks, _ = self.call(self.inspected(1))
        for entry in pending:
            self.assertIsNone(entry[2])
            self.assertEqual(GUARD.PY_BODY, entry[3])

    def test_the_entries_of_two_values_are_anchored_at_their_own_words(self):
        pending, _scan, _asks, _ = self.call(
            self.inspected(1, self.value("w1", ("echo A",), ()), self.value("w2", (), ("echo B",)))
        )
        self.assertEqual(
            [("echo A", (3, 0, 1)), ("echo B", (3, 1, 1))],
            [(e[0], e[1][-1]) for e in pending],
        )

    def test_a_charge_that_does_not_fit_leaves_the_total_unchanged_and_queues_nothing(self):
        pending, scan, asks, _ = self.call(self.inspected(41), scanned=960, budget=1000)
        self.assertEqual(960, scan.scanned)
        self.assertEqual([], pending)
        self.assertEqual(GUARD.SCAN_BUDGET_ASK, asks.strongest())

    def test_overrun_leaves_the_total_unchanged_and_queues_nothing(self):
        result = GUARD.ArgsJsonResult((self.value(),), 5, True, False)
        pending, scan, asks, _ = self.call(result, scanned=100)
        self.assertEqual(100, scan.scanned)
        self.assertEqual([], pending)
        self.assertEqual(GUARD.SCAN_BUDGET_ASK, asks.strongest())

    def test_after_the_scan_budget_ask_the_step_does_nothing(self):
        asks = GUARD._DeferredAsks()
        self.call(GUARD.ArgsJsonResult((), 0, True, False), asks=asks)
        pending, scan, _asks, asked = self.call(self.inspected(1), scanned=7, asks=asks)
        self.assertEqual(0, asked)
        self.assertEqual([], pending)
        self.assertEqual(7, scan.scanned)

    def test_a_scan_budget_ask_held_by_a_payload_does_not_stop_the_step(self):
        asks = GUARD._DeferredAsks()
        asks.hold_scan_budget()
        pending, scan, _asks, asked = self.call(self.inspected(10), scanned=7, asks=asks)
        self.assertEqual(1, asked)
        self.assertEqual(3, len(pending))
        self.assertEqual(17, scan.scanned)

    def test_a_statement_from_the_parse_failure_fallback_is_left_alone(self):
        pending, scan, asks, asked = self.call(
            GUARD.ArgsJsonResult((), 0, True, True), scanned=7, lexed=False
        )
        self.assertEqual(0, asked)
        self.assertEqual([], pending)
        self.assertEqual(7, scan.scanned)
        self.assertIsNone(asks.strongest())

    def test_unrestorable_holds_its_ask_whatever_the_rest_did(self):
        fits = GUARD.ArgsJsonResult((self.value(),), 3, False, True)
        pending, scan, asks, _ = self.call(fits)
        self.assertEqual(3, len(pending))
        self.assertEqual(3, scan.scanned)
        self.assertEqual(GUARD.ARGS_JSON_UNRESTORABLE_ASK, asks.strongest())

    def test_unrestorable_beside_an_overrun_leaves_the_scan_budget_ask_the_strongest(self):
        both = GUARD.ArgsJsonResult((), 0, True, True)
        pending, scan, asks, _ = self.call(both)
        self.assertEqual([], pending)
        self.assertEqual(0, scan.scanned)
        self.assertEqual(GUARD.SCAN_BUDGET_ASK, asks.strongest())

    def test_a_decision_with_nothing_to_do_changes_nothing(self):
        pending, scan, asks, _ = self.call(nothing_result(), scanned=5)
        self.assertEqual([], pending)
        self.assertEqual(5, scan.scanned)
        self.assertIsNone(asks.strongest())

    def test_overrun_in_a_run_still_yields_a_payload_queued_before_it(self):
        command = (
            "bash -c 'echo MARK-BEFORE'; " + run_command(self.DEEP) + "; "
            + run_command('{"command":"echo MARK-LATER"}')
        )
        spy = Spy(command)
        self.assertIn("echo MARK-BEFORE", spy.statements)
        self.assertNotIn("echo MARK-LATER", spy.statements)
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], spy.early_stop)
        # The step did nothing for the statement after the overrun.
        self.assertEqual([KIND_OVERRUN], spy.kinds())

    def test_a_charge_that_does_not_fit_in_a_run_ends_as_the_scan_budget_ask(self):
        calls = []

        def step(shaped_words, marked):
            if GUARD.head(shaped_words)[0] != "mcp-bridge":
                return nothing_result()
            calls.append(1)
            value = GUARD.ArgsJsonValue(shaped_words[-1], ("echo MARK-BODY",), ("echo MARK-CMD",))
            return GUARD.ArgsJsonResult((value,), 10 ** 6, False, False)

        command = (
            "bash -c 'echo MARK-BEFORE'; " + run_command('{"command":"ls"}') + "; "
            + run_command('{"command":"echo MARK-LATER"}')
        )
        early_stop = []
        with mock.patch.object(GUARD, "_mcp_bridge_args_json_chunks", step):
            texts = [s[0] for s in GUARD.statements(command, early_stop=early_stop)]
        self.assertIn("echo MARK-BEFORE", texts)
        for absent in ("echo MARK-BODY", "echo MARK-CMD", "echo MARK-LATER"):
            self.assertNotIn(absent, texts)
        self.assertEqual(1, len(calls))
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], early_stop)

    def test_the_scan_budget_ask_outranks_the_unrestorable_ask(self):
        asks = GUARD._DeferredAsks()
        asks.hold_unrestorable()
        asks.hold_scan_budget()
        early_stop = []
        asks.settle(early_stop)
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], early_stop)

    def test_an_empty_record_settles_to_nothing(self):
        early_stop = []
        GUARD._DeferredAsks().settle(early_stop)
        self.assertEqual([], early_stop)

    def test_the_record_is_settled_once_with_the_strongest_ask(self):
        for held, expected in (
            (("unrestorable",), GUARD.ARGS_JSON_UNRESTORABLE_ASK),
            (("scan_budget",), GUARD.SCAN_BUDGET_ASK),
            (("unrestorable", "scan_budget"), GUARD.SCAN_BUDGET_ASK),
        ):
            asks = GUARD._DeferredAsks()
            for name in held:
                getattr(asks, "hold_" + name)()
            early_stop = []
            asks.settle(early_stop)
            with self.subTest(held=held):
                self.assertEqual([expected], early_stop)

    def test_an_ordinary_overrun_keeps_its_own_early_return(self):
        # Too much text queued ends the scan at a pop with the scan-budget ask,
        # and the record is not settled (no second entry).
        nested = "echo $(" * 200 + "echo x" + ")" * 200
        early_stop = []
        list(GUARD.statements("mcp-bridge run --args-json $'{\"a\":1}\\0'; " + nested, early_stop=early_stop))
        self.assertEqual([GUARD.SCAN_BUDGET_ASK], early_stop)


GUARD_ENV = {"HOME": "/home/args-json-test-home", "PATH": "", "PYTHONDONTWRITEBYTECODE": "1"}


def judge(command):
    """(decision, reason id) of the hook for COMMAND: the whole judgment, the
    hook run as a subprocess fed one PreToolUse payload (no CLAUDE_BATCH)."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=GUARD_ENV,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return "allow", None
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    reason = out["permissionDecisionReason"]
    rule = None
    if reason.startswith("[destructive-guard/"):
        rule = reason[len("[destructive-guard/"):].split("]", 1)[0]
    return out["permissionDecision"], rule


class TestAnchorLookup(unittest.TestCase):
    """args-json-quoting-bypass TS-16 (FR5, FR9, NFR4): the collaborator finds
    the token index of the anchor word of each value that queues something
    through one walk of the statement's tokens, not one search per value; a
    value that queues nothing costs no token position; a word without a span
    is located by _token_index(). The proof is structural: a token list that
    counts how often it is walked, never elapsed time."""

    MANY = 100
    HEAD = ["mcp-bridge", "run", "--mcp", "desktop-commander", "--tool", "start_process"]

    class WalkCounting(list):
        """A token list that counts how many times it is walked."""

        def __init__(self, items):
            super().__init__(items)
            self.walks = 0

        def __iter__(self):
            self.walks += 1
            return super().__iter__()

    def run_words(self, words):
        """Drive statements() over the command WORDS spell (joined by a blank,
        each written as it is to be lexed): (origins, walks), the anchor of
        each statement it yielded keyed by statement text, and how many times
        the collaborator walked the token list of the statement whose command
        word is `mcp-bridge`."""
        original = GUARD._queue_args_json_chunks
        walked = []

        def spy(shaped_words, marked_chunk, tokens, *rest):
            counting = self.WalkCounting(tokens)
            if tokens and tokens[0] == "mcp-bridge":
                walked.append(counting)
            return original(shaped_words, marked_chunk, counting, *rest)

        origins = {}
        with mock.patch.object(GUARD, "_queue_args_json_chunks", spy):
            for statement in GUARD.statements(" ".join(words), early_stop=[]):
                origins[statement[0]] = statement[5][0]
        (counting,) = walked
        return origins, counting.walks

    def test_many_values_cost_one_walk_and_the_command_string_keeps_its_origin(self):
        words = (
            self.HEAD
            + ["--args-json", "'{}'"] * self.MANY
            + ["--args-json", "'{\"command\":\"echo MARK-CMD\"}'"]
        )
        origins, walks = self.run_words(words)
        # The token index of the value word, read off the words as written; the
        # value has no body, so its command string is the first entry of its word.
        self.assertEqual(((0, len(words) - 1, 1),), origins["echo MARK-CMD"])
        self.assertLessEqual(walks, 1)

    def test_values_that_queue_nothing_cost_no_token_position(self):
        words = self.HEAD + ["--args-json", "'{}'"] * self.MANY
        origins, walks = self.run_words(words)
        self.assertEqual(0, walks)
        self.assertEqual(1, len(origins))

    def test_the_command_strings_of_many_values_share_one_walk_and_keep_their_origins(self):
        words = list(self.HEAD)
        expected = {}
        for i in range(self.MANY):
            words += ["--args-json", "'{}'"]
            if i % 10 == 0:
                words += ["--args-json", "'{\"command\":\"echo MARK-" + str(i) + "\"}'"]
                expected["echo MARK-" + str(i)] = ((0, len(words) - 1, 1),)
        origins, walks = self.run_words(words)
        self.assertEqual(expected, {text: origins[text] for text in expected})
        self.assertLessEqual(walks, 1)

    # The collaborator over a fixed decision result (the decision replaced by a
    # stub, as TestDeferral does), the tokens given as they are.

    def queue(self, tokens, *words):
        """The last origin step (statement index, token index, ordinal) of each
        entry the collaborator queues over TOKENS when the decision names one
        value of a single body at each of WORDS."""
        values = tuple(GUARD.ArgsJsonValue(word, ("echo B",), ()) for word in words)
        result = GUARD.ArgsJsonResult(values, 1, False, False)
        pending = []
        with mock.patch.object(
            GUARD, "_mcp_bridge_args_json_chunks", lambda shaped_words, marked: result
        ):
            GUARD._queue_args_json_chunks(
                ["mcp-bridge", "run"], None, tokens, True, ("anchor",), 3,
                GUARD.PY_BODY, pending, GUARD._ScanState(1000), GUARD._DeferredAsks(),
            )
        return [entry[1][-1] for entry in pending]

    @staticmethod
    def tok(text, span=None):
        token = GUARD.Tok(text)
        token.span = span
        return token

    def test_a_word_without_a_span_is_located_by_identity_first(self):
        first, second = self.tok("dup"), self.tok("dup")
        tokens = [self.tok("a"), first, second]
        # Equal text at 1 and 2: the word itself is at 2.
        self.assertEqual([(3, 2, 1)], self.queue(tokens, second))

    def test_a_word_without_a_span_that_is_not_a_token_is_located_by_text_then_zero(self):
        tokens = [self.tok("a"), self.tok("b")]
        self.assertEqual([(3, 1, 1)], self.queue(tokens, self.tok("b")))
        self.assertEqual([(3, 0, 1)], self.queue(tokens, self.tok("absent")))

    def test_a_word_whose_span_no_token_has_is_located_by_token_index(self):
        tokens = [self.tok("a", (0, 1)), self.tok("b", (2, 3))]
        self.assertEqual([(3, 1, 1)], self.queue(tokens, self.tok("b", (40, 41))))
        self.assertEqual([(3, 0, 1)], self.queue(tokens, self.tok("absent", (40, 41))))

    def test_a_word_with_a_span_gets_the_first_token_with_that_span(self):
        tokens = [self.tok("a", (0, 1)), self.tok("b", (2, 3)), self.tok("b", (2, 3))]
        # The word is the token at 2, but the first token with its span is 1.
        self.assertEqual([(3, 1, 1)], self.queue(tokens, tokens[2]))

    def test_two_values_with_spans_each_get_their_own_index(self):
        tokens = [self.tok("a", (0, 1)), self.tok("b", (2, 3)), self.tok("c", (4, 5))]
        self.assertEqual([(3, 2, 1), (3, 0, 1)], self.queue(tokens, tokens[2], tokens[0]))

    def test_the_step_3_docstring_states_the_lookup_rule(self):
        doc = GUARD._queue_args_json_chunks.__doc__
        for phrase in ("span", "at most once", "_token_index()"):
            with self.subTest(phrase):
                self.assertIn(phrase, doc)


class TestDenyWins(unittest.TestCase):
    """AC-5, AC-6 (FR7, FR11, FR12, D6): the deferred asks are settled after
    the queue is drained, so a deny found beside them wins; alone they are
    asks."""

    UNRESTORABLE = "mcp-bridge run --mcp desktop-commander --tool start_process --args-json $'{\"command\":\"ls\"}\\0'"
    BUDGET_USED_UP = "; ".join(["bash -c 'true'"] * 25 + ["bash -c 'echo LAST'"])
    DESTRUCTIVE = "git branch -D example"

    def test_the_forms_alone_are_asks(self):
        self.assertEqual(("ask", "args-json-unrestorable"), judge(self.UNRESTORABLE))
        self.assertEqual(("ask", "scan-budget-exceeded"), judge(self.BUDGET_USED_UP))

    def test_an_unconditional_destructive_statement_beside_the_unrestorable_form_is_deny(self):
        for label, command in (
            ("before", self.DESTRUCTIVE + "; " + self.UNRESTORABLE),
            ("after", self.UNRESTORABLE + "; " + self.DESTRUCTIVE),
            ("chained", self.UNRESTORABLE + " && " + self.DESTRUCTIVE),
        ):
            with self.subTest(label):
                self.assertEqual("deny", judge(command)[0])

    def test_an_unconditional_destructive_statement_beside_the_used_up_counter_is_deny(self):
        for label, command in (
            ("before", self.DESTRUCTIVE + "; " + self.BUDGET_USED_UP),
            ("after", self.BUDGET_USED_UP + "; " + self.DESTRUCTIVE),
        ):
            with self.subTest(label):
                self.assertEqual("deny", judge(command)[0])

    def test_a_destructive_payload_queued_before_the_used_up_counter_is_deny(self):
        command = "bash -c 'git branch -D example'; " + self.BUDGET_USED_UP
        self.assertEqual("deny", judge(command)[0])

    def test_a_decoded_command_beside_the_unrestorable_form_is_deny(self):
        decoded = "mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{\"command\":\"git branch -D example\"}'"
        self.assertEqual("deny", judge(self.UNRESTORABLE + "; " + decoded)[0])


class _CallSites(ast.NodeVisitor):
    """The names the hook's source references and the function each sits in."""

    def __init__(self):
        self.stack = []
        self.references = []  # (name, enclosing function name or None)

    def visit_FunctionDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Name(self, node):
        self.references.append((node.id, self.stack[-1] if self.stack else None))

    def visit_Attribute(self, node):
        self.references.append((node.attr, self.stack[-1] if self.stack else None))
        self.generic_visit(node)


class TestStructure(unittest.TestCase):
    """AC-8 (NFR5): statements() calls `_queue_args_json_chunks()` once per
    statement it yields and holds no other `--args-json` logic; the decision
    is called only from the collaborator."""

    @classmethod
    def setUpClass(cls):
        with open(HOOK, encoding="utf-8") as handle:
            cls.tree = ast.parse(handle.read())
        cls.sites = _CallSites()
        cls.sites.visit(cls.tree)

    def function(self, name):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        self.fail("no function " + name)

    def test_the_decision_is_referenced_only_from_the_collaborator(self):
        places = {
            where for name, where in self.sites.references
            if name == "_mcp_bridge_args_json_chunks"
        }
        self.assertEqual({"_queue_args_json_chunks"}, places)

    def test_statements_has_one_call_site_and_no_other_args_json_logic(self):
        sites = _CallSites()
        sites.visit(self.function("statements"))
        names = {name for name, _where in sites.references}
        involved = {name for name in names if "args_json" in name.lower()}
        self.assertEqual({"_queue_args_json_chunks"}, involved)
        calls = [
            node for node in ast.walk(self.function("statements"))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_queue_args_json_chunks"
        ]
        self.assertEqual(1, len(calls))

    def test_the_collaborator_is_called_once_per_yielded_statement(self):
        command = (
            "echo a; mcp-bridge run --args-json '{\"command\":\"echo MARK\"}' && bash -c 'echo b'; "
            "echo \"$(echo c)\"; (echo d) | cat; if true; then echo e; fi"
        )
        original = GUARD._queue_args_json_chunks
        calls = []

        def spy(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        with mock.patch.object(GUARD, "_queue_args_json_chunks", spy):
            yielded = list(GUARD.statements(command, early_stop=[]))
        self.assertGreater(len(yielded), 5)
        self.assertEqual(len(yielded), len(calls))

    def test_the_collaborator_is_called_for_a_fallback_statement_too(self):
        command = "echo 'unterminated"
        original = GUARD._queue_args_json_chunks
        calls = []

        def spy(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        with mock.patch.object(GUARD, "_queue_args_json_chunks", spy):
            yielded = list(GUARD.statements(command, early_stop=[]))
        self.assertTrue(any(not statement[2] for statement in yielded), "not a fallback")
        self.assertEqual(len(yielded), len(calls))

    def test_the_record_is_one_per_run(self):
        records = []
        original = GUARD._DeferredAsks

        class Recording(original):
            def __init__(self):
                super().__init__()
                records.append(self)

        with mock.patch.object(GUARD, "_DeferredAsks", Recording):
            list(GUARD.statements("echo a; bash -c 'echo b'", early_stop=[]))
        self.assertEqual(1, len(records))


class TestDocstring(unittest.TestCase):
    """AC-4 (FR8, FR10): the docstring of the decision lists O1 and O2 as
    IMPLEMENTATION.md states them, and none of the forms it says are not out
    of scope."""

    def setUp(self):
        self.doc = " ".join(inspect.getdoc(GUARD._mcp_bridge_args_json_chunks).split())
        self.scope = self.doc[self.doc.index("Out of scope"):]

    def test_o1_and_o2_are_named(self):
        for label in ("O1", "O2"):
            with self.subTest(label):
                self.assertIn(label, self.scope)

    def test_o1_forms(self):
        for phrase in (
            "a command written as plain text, without a substitution, in a key other than the top-level `command`",
            "the `input` of desktop-commander's `interact_with_process`",
            "or in a `command` key below the top level",
            "Only the candidate search applies there",
        ):
            with self.subTest(phrase):
                self.assertIn(phrase, self.scope)

    def test_o2_forms(self):
        for phrase in (
            "the FR6 forms, which keep the raw-string verdict",
            "an `--args-json` value word that is not static, set by a substitution, a variable expansion or the like "
            "(a substitution Bash itself runs is still re-scanned)",
            "a word in flag position that is not static in the same sense",
            "an unknown flag",
            "a value-taking flag with no value word",
            "no `--args-json`",
            "a value that does not decode as JSON",
            "a decoded value whose top level is not an object",
        ):
            with self.subTest(phrase):
                self.assertIn(phrase, self.scope)

    def test_neither_form_is_sent_to_ask(self):
        self.assertIn("Neither form is sent to ask", self.scope)

    def test_no_form_that_is_not_out_of_scope_is_listed(self):
        for phrase in (
            "destination",
            "ANSI-C",
            "quoted flag",
            "`=` form",
            "single-dash",
            "single dash",
            "positional",
            "`--`",
            "repeated",
            "canonical flag sequence",
        ):
            with self.subTest(phrase):
                self.assertNotIn(phrase, self.scope)

    def test_the_flow_states_the_decoded_command_takes_no_payload_count(self):
        self.assertIn("takes no count from MAX_SHELL_PAYLOAD_EXPANSIONS", self.doc)

    def test_the_flow_states_a_word_shorter_than_two_characters_ends_the_flags(self):
        flow = self.doc[: self.doc.index("Out of scope")]
        for phrase in (
            "restored text is shorter than two characters",
            "a lone `-`",
            "positional word",
        ):
            with self.subTest(phrase):
                self.assertIn(phrase, flow)

    def test_the_flow_states_the_three_word_outcomes_and_the_flags(self):
        for phrase in ("Not static", "Unrestorable", "Overrun"):
            with self.subTest(phrase):
                self.assertIn(phrase, self.doc)


if __name__ == "__main__":
    unittest.main()
