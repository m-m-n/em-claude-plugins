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
import re
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

    # args-json-quoting-bypass TS-17 (FR1, FR9; finding 3f7145c6c8c0b26a): the
    # notion pair excludes a statement only when the `--format`, `--session`
    # and `--args-json` value words are single-word-certain.

    NOTION = "mcp-bridge run --mcp notion --tool notion-create-comment "
    COMMAND_VALUE = "'{\"command\":\"ls\"}'"

    def notion_pair(self, command):
        """(the answers of _args_json_notion_pair() over a statements() run of
        COMMAND, in call order; the Spy of the run)."""
        answers = []
        original = GUARD._args_json_notion_pair

        def wrapper(marked, words):
            answer = original(marked, words)
            answers.append(answer)
            return answer

        with mock.patch.object(GUARD, "_args_json_notion_pair", wrapper):
            run = Spy(command)
        return answers, run

    # Value words that Bash may turn into a word count other than one.
    SPLITTING_WORDS = (
        ("unquoted parameter expansion with a default", "${REVIEW_UNSET:-json --mcp desktop-commander --tool start_process}"),
        ("unquoted variable", "$FORMAT"),
        ("unquoted command substitution", "$(echo json)"),
        ("unquoted arithmetic expansion", "$((1 + 2))"),
        ("unquoted brace list", "{json,--mcp=desktop-commander}"),
        ("unquoted brace range", "{1..3}"),
        ("unquoted glob", "*"),
        ("unquoted bracket glob", "[jt]son"),
        ("leading tilde", "~root"),
        ("quoted at-sign parameter", '"$@"'),
        ("quoted at-sign array", '"${A[@]}"'),
        ("quoted at-sign array with a modifier", '"${A[@]#x}"'),
        ("quoted prefix names", '"${!PREFIX@}"'),
        ("quoted braced at-sign parameter", '"${@}"'),
        ("quoted at-sign array between other text", 'x"${A[@]}"y'),
    )

    def test_a_format_or_session_value_that_may_split_is_not_excluded(self):
        for flag in ("--format", "--session"):
            for label, word in self.SPLITTING_WORDS:
                with self.subTest(flag + " " + label):
                    command = self.NOTION + flag + " " + word + " --args-json " + self.COMMAND_VALUE
                    answers, run = self.notion_pair(command)
                    self.assertEqual([False], answers)
                    self.assertEqual([KIND_INSPECTED], run.kinds())

    def test_a_decoded_command_after_a_split_format_value_is_inspected(self):
        command = (
            self.NOTION + "--format ${REVIEW_UNSET:-json --mcp desktop-commander --tool start_process} "
            "--args-json '{\"command\":\"git branch -D example\"}'"
        )
        (result,) = Spy(command).inspected()
        self.assertEqual(("git branch -D example",), sole_value(result).commands)

    def test_an_args_json_value_that_may_split_leaves_the_pair_undetermined(self):
        for label, word in self.SPLITTING_WORDS:
            with self.subTest(label):
                answers, run = self.notion_pair(self.NOTION + "--args-json " + word)
                self.assertEqual([False], answers)
                # A value word that is not static is skipped by the flag
                # reading (O2 (1)), so the kind alone does not show the
                # exclusion; the answer above does.
                self.assertEqual([KIND_NOTHING], run.kinds())

    def test_the_pair_is_not_excluded_for_any_one_of_several_value_words(self):
        command = (
            self.NOTION + "--format json --session $SID --args-json " + self.COMMAND_VALUE
        )
        answers, run = self.notion_pair(command)
        self.assertEqual([False], answers)
        self.assertEqual([KIND_INSPECTED], run.kinds())
        command = (
            self.NOTION + "--format json --format \"${A[@]}\" --args-json " + self.COMMAND_VALUE
        )
        answers, run = self.notion_pair(command)
        self.assertEqual([False], answers)
        self.assertEqual([KIND_INSPECTED], run.kinds())

    # Value words that Bash always passes as exactly one argument.
    ONE_WORD_FORMS = (
        ("plain word", "json"),
        ("single-quoted", "'json'"),
        ("double-quoted", '"json"'),
        ("double-quoted variable", '"$SID"'),
        ("double-quoted braced variable", '"${SID}"'),
        ("double-quoted command substitution", '"$(cat comment.json)"'),
        ("double-quoted star array", '"${A[*]}"'),
        ("double-quoted star parameter", '"$*"'),
        ("double-quoted escaped dollar", '"\\$@"'),
        ("single-quoted at-sign", "'$@'"),
        ("single-quoted glob", "'*'"),
        ("single-quoted braces", "'{a,b}'"),
        ("backslashed glob", "\\*"),
        ("backslashed braces", "\\{a,b\\}"),
        ("double-quoted tilde", '"~"'),
        ("double-quoted text with a space", '"a b"'),
        ("ANSI-C quote", "$'json'"),
        ("ANSI-C quote that does not decode", "$'a\\0b'"),
        ("locale quote", '$"json"'),
        ("mixed quotes", "a'b'\"c\"\\d"),
    )

    def test_a_value_that_is_always_one_word_keeps_the_pair_excluded(self):
        for flag in ("--format", "--session", "--args-json"):
            for label, word in self.ONE_WORD_FORMS:
                with self.subTest(flag + " " + label):
                    command = self.NOTION + flag + " " + word
                    if flag != "--args-json":
                        command += " --args-json " + self.COMMAND_VALUE
                    answers, run = self.notion_pair(command)
                    self.assertEqual([True], answers)
                    self.assertEqual([nothing_result()], run.results)
                    self.assertEqual([], run.early_stop)

    def test_the_session_variable_and_the_comment_substitution_stay_excluded(self):
        for label, command in (
            (
                "session variable",
                self.NOTION + "--session \"$SID\" --args-json "
                "'{\"body\":\"$(git branch -D example) と記載する\"}'",
            ),
            (
                "args-json command substitution",
                self.NOTION + "--args-json \"$(cat comment.json)\"",
            ),
            (
                "args-json ANSI-C value",
                self.NOTION + "--args-json $'{\"body\":\"x\"}\\0'",
            ),
        ):
            with self.subTest(label):
                answers, run = self.notion_pair(command)
                self.assertEqual([True], answers)
                self.assertEqual([KIND_NOTHING], run.kinds())
                (result,) = run.results
                self.assertFalse(result.unrestorable)
                self.assertEqual([], run.early_stop)

    def test_the_single_word_judgment_is_one_helper_called_only_by_the_notion_pair(self):
        """AC-4 (NFR6): the judgment has one home, and the notion-pair
        predicate is its only caller."""
        with open(HOOK, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        helpers = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and "single_word" in node.name
        ]
        self.assertEqual(1, len(helpers), helpers)
        sites = _CallSites()
        sites.visit(tree)
        places = {where for name, where in sites.references if name == helpers[0]}
        self.assertEqual({"_args_json_notion_pair"}, places)

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

    def test_an_unquoted_backslash_escaped_equals_ends_the_name_part(self):
        """args-json-quoting-bypass TS-18 (FR2, FR9): outside quotes a
        backslash-escaped `=` ends the name part of a non-static flag word the
        way an unquoted `=` does, so the static `--args-json` value after it is
        inspected; inside double quotes `\\=` keeps its backslash, the name is
        not a known one, and the statement stays nothing to do."""
        for label, command in (
            ("server", 'mcp-bridge run --mcp\\="$S" --args-json ' + self.VALUE),
            ("session", 'mcp-bridge run --session\\="$SID" --args-json ' + self.VALUE),
        ):
            with self.subTest(label):
                spy = Spy(command)
                self.assertEqual([KIND_INSPECTED], spy.kinds())
                self.assertEqual(("ls",), sole_value(spy.results[0]).commands)
        with self.subTest("escaped equals inside double quotes"):
            command = 'mcp-bridge run "--mcp\\=$S" --args-json ' + self.VALUE
            self.assertEqual([KIND_NOTHING], self.kinds(command))

    def test_the_name_reading_docstring_states_the_escaped_equals(self):
        """args-json-quoting-bypass TS-18 (FR10): the docstring of
        _flag_equals_prefix_name() says that an unquoted `=` or an unquoted
        backslash-escaped `=` ends the name part and that a `\\=` inside double
        quotes keeps its backslash."""
        doc = " ".join(inspect.getdoc(GUARD._flag_equals_prefix_name).split())
        for phrase in (
            "an unquoted `=` or an unquoted backslash-escaped `=`",
            "either one ends the name part",
            "A `\\=` inside double quotes",
            "keeps its backslash",
        ):
            with self.subTest(phrase):
                self.assertIn(phrase, doc)

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


class TestDollarReading(unittest.TestCase):
    """args-json-quoting-bypass TS-13 to TS-15 (FR3, FR4, FR7, FR9, FR10, TM-4,
    TM-5): how the word readers read a `$`. A `$`, one or more line
    continuations (a backslash and a newline) and a character that starts an
    expansion make the word Unrestorable; a `$` before a character that starts
    no expansion, a non-ASCII character included, is a literal `$`."""

    NL = "\n"
    FR3_FORM = (
        "a `$`, one or more line continuations (a backslash and a newline), "
        "and a character that starts an expansion"
    )

    def lex(self, written):
        """The marked text and the value word of the `mcp-bridge run`
        statement whose `--args-json` value is WRITTEN, as the decision
        receives them (a spy on the decision records its arguments). The
        statement is checked to end with WRITTEN as written, line continuations
        included, and the word to span it (unless it starts with a
        substitution's residue)."""
        seen = []
        original = GUARD._mcp_bridge_args_json_chunks

        def spy(shaped_words, marked):
            seen.append((shaped_words, marked))
            return original(shaped_words, marked)

        with mock.patch.object(GUARD, "_mcp_bridge_args_json_chunks", spy):
            list(GUARD.statements("mcp-bridge run --args-json " + written, early_stop=[]))
        ((shaped_words, marked),) = [
            s for s in seen if GUARD.head(s[0])[0] == "mcp-bridge"
        ]
        word = shaped_words[-1]
        self.assertTrue(marked.source.endswith(written))
        bounds = GUARD._word_source_bounds(marked, *word.span)
        if bounds is not None:  # None: the word starts with a substitution's residue
            self.assertEqual(written, marked.source[bounds[0]:bounds[1]])
        return marked, word

    def static(self, written):
        """_read_static_word() over the value word WRITTEN."""
        return GUARD._read_static_word(*self.lex(written))

    def as_written(self, written):
        """_read_word_as_written() over the value word WRITTEN."""
        return GUARD._read_word_as_written(*self.lex(written))

    def cont(self, count=1):
        """COUNT line continuations: a backslash and a newline, each."""
        return ("\\" + self.NL) * count

    def test_a_double_quoted_dollar_continuation_expansion_start_is_unrestorable(self):
        """TS-13 (AC-2, FR3): `"$`, a line continuation and a character that
        starts an expansion`"` is Unrestorable."""
        c = self.cont
        for label, written in (
            ("name", '"$' + c() + 'DEST"'),
            ("two continuations", '"$' + c(2) + 'DEST"'),
            ("three continuations", '"$' + c(3) + 'DEST"'),
            ("brace", '"$' + c() + '{DEST}"'),
            ("bracket", '"$' + c() + '[DEST]"'),
            ("digit", '"$' + c() + '1"'),
            ("underscore", '"$' + c() + '_"'),
            ("special parameter", '"$' + c() + '@"'),
            ("text around", '"a $' + c() + 'DEST b"'),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_UNRESTORABLE, None), self.static(written))

    def test_a_dollar_continuation_paren_is_a_substitution_and_not_static(self):
        """TS-13 (AC-2, FR3): a `$`, a line continuation and a `(` is a
        substitution Bash runs (the marking reads it as one), not a quoting
        that cannot be restored: the word stays Not static, in double quotes
        and outside. A `{` after an unquoted `$` and a continuation is a
        parameter expansion region, also Not static."""
        c = self.cont
        for label, written in (
            ("double quote, paren", '"$' + c() + '(DEST)"'),
            ("unquoted, paren", "$" + c() + "(DEST)"),
            ("unquoted, brace", "$" + c() + "{DEST}"),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_NOT_STATIC, None), self.static(written))

    def test_an_unquoted_dollar_continuation_name_is_unrestorable(self):
        """TS-13 (AC-2, FR3): an unquoted `$`, a line continuation and a name
        character is Unrestorable."""
        c = self.cont
        for label, written in (
            ("name", "$" + c() + "X"),
            ("two continuations", "$" + c(2) + "X"),
            ("digit", "$" + c() + "1"),
            ("text around", "a$" + c() + "Xb"),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_UNRESTORABLE, None), self.static(written))

    def test_an_unquoted_dollar_continuation_quote_is_unrestorable(self):
        """TS-13 (AC-2, FR3): an unquoted `$`, a line continuation and a quoted
        part (the opener of an ANSI-C or locale quote split by the
        continuation) is Unrestorable."""
        c = self.cont
        for label, written in (
            ("single quote", "$" + c() + "'abc'"),
            ("double quote", "$" + c() + '"abc"'),
            ("two continuations", "$" + c(2) + "'abc'"),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_UNRESTORABLE, None), self.static(written))

    def test_a_word_that_also_holds_an_expansion_is_not_static(self):
        """TS-13 (AC-2, FR3): an expansion anywhere in the word wins over the
        FR3 form, whichever comes first."""
        c = self.cont
        for label, written in (
            ("double quote, expansion after", '"$' + c() + 'DEST $Y"'),
            ("double quote, expansion before", '"$Y $' + c() + 'DEST"'),
            ("double quote, backtick after", '"$' + c() + 'DEST `x`"'),
            ("double quote, expansion in a second region", '"$' + c() + 'DEST"$Y'),
            ("unquoted, expansion after", "$" + c() + "X$Y"),
            ("unquoted, expansion before", "$Y$" + c() + "X"),
            ("unquoted, substitution after", "$" + c() + "X$(echo x)"),
            ("unquoted, glob after", "$" + c() + "X*"),
            ("locale quote, expansion after", '$"$' + c() + "X $Y" + '"'),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_NOT_STATIC, None), self.static(written))

    def test_a_dollar_continuation_before_no_expansion_is_a_literal_dollar(self):
        """TS-13 (AC-2, FR3): a `$` whose next character after the line
        continuations starts no expansion (a space, the closing quote, another
        symbol, the end) is a literal `$`; the continuations vanish."""
        c = self.cont
        for label, written, text in (
            ("space", '"a $' + c() + ' b"', "a $ b"),
            ("closing quote", '"a $' + c() + '"', "a $"),
            ("two continuations then a space", '"a $' + c(2) + ' b"', "a $ b"),
            ("two continuations then the closing quote", '"a $' + c(2) + '"', "a $"),
            ("only the dollar and a continuation", '"$' + c() + '"', "$"),
            ("percent sign", '"$' + c() + '%"', "$%"),
            ("a backslash escape", '"$' + c() + '\\"x"', '$"x'),
            ("unquoted, percent sign", "a$" + c() + "%b", "a$%b"),
            ("unquoted, a backslash escape", "$" + c() + "\\x", "$x"),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_STATIC, text), self.static(written))

    def test_a_continuation_without_a_dollar_vanishes_as_before(self):
        """TS-13 (AC-7): a line continuation that does not follow a `$` is
        read as before."""
        c = self.cont
        for label, written, text in (
            ("double quote", '"a' + c() + 'b"', "ab"),
            ("unquoted", "a" + c() + "b", "ab"),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_STATIC, text), self.static(written))

    def test_a_dollar_without_a_continuation_is_read_as_before(self):
        """TS-13 (AC-7): both sides of the continuation rule: with no
        continuation, a `$` before an expansion-start character is not static
        and a `$` before any other ASCII character is a literal `$`."""
        for label, written, expected in (
            ("double quote, name", '"$DEST"', (GUARD.WORD_NOT_STATIC, None)),
            ("double quote, brace", '"${DEST}"', (GUARD.WORD_NOT_STATIC, None)),
            ("double quote, special parameter", '"$@"', (GUARD.WORD_NOT_STATIC, None)),
            ("double quote, space", '"a $ b"', (GUARD.WORD_STATIC, "a $ b")),
            ("double quote, percent sign", '"$%"', (GUARD.WORD_STATIC, "$%")),
            ("double quote, end", '"a $"', (GUARD.WORD_STATIC, "a $")),
            ("unquoted, name", "$X", (GUARD.WORD_NOT_STATIC, None)),
            ("unquoted, special parameter", "$@", (GUARD.WORD_NOT_STATIC, None)),
            ("unquoted, end", "a$", (GUARD.WORD_STATIC, "a$")),
            ("unquoted, percent sign", "a$%b", (GUARD.WORD_STATIC, "a$%b")),
        ):
            with self.subTest(label):
                self.assertEqual(expected, self.static(written))

    def test_the_masking_stop_reading_does_not_determine_the_fr3_form(self):
        """TS-14 (AC-3, FR3): `_read_word_as_written()` gives None for a
        double-quoted word holding a `$`, a line continuation and a character
        that starts an expansion."""
        c = self.cont
        for label, written in (
            ("name", '"$' + c() + 'DEST"'),
            ("two continuations", '"$' + c(2) + 'DEST"'),
            ("brace", '"$' + c() + '{DEST}"'),
            ("special parameter", '"$' + c() + '@"'),
            ("text around", '"a $' + c() + 'DEST b"'),
        ):
            with self.subTest(label):
                self.assertIsNone(self.as_written(written))

    def test_the_masking_stop_reading_of_a_word_without_the_fr3_form_is_as_before(self):
        """TS-14 (AC-3, AC-7): a word without the FR3 form is read as before."""
        c = self.cont
        for label, written, expected in (
            ("plain", "plain", "plain"),
            ("double quote, space", '"a $ b"', "a $ b"),
            ("double quote, end", '"a $"', "a $"),
            ("double quote, dollar continuation space", '"a $' + c() + ' b"', "a $ b"),
            ("double quote, dollar continuation end", '"a $' + c() + '"', "a $"),
            ("double quote, continuation only", '"a' + c() + 'b"', "ab"),
            ("double quote, name", '"$DEST"', None),
            ("double quote, brace", '"${DEST}"', None),
            ("unquoted, dollar", "$X", None),
            ("unquoted, dollar continuation", "$" + c() + "X", None),
        ):
            with self.subTest(label):
                self.assertEqual(expected, self.as_written(written))

    def test_a_dollar_before_a_non_ascii_character_is_literal(self):
        """TS-15 (AC-5, FR4): the double-quoted value `"5 $€"` is read as
        static text `5 $€`, and the same value written with `\\$€` is read as
        the same text."""
        for label, written in (
            ("bare", '"5 $€"'),
            ("escaped", '"5 \\$€"'),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_STATIC, "5 $€"), self.static(written))

    def test_a_dollar_before_a_non_ascii_character_is_literal_in_every_position(self):
        """TS-15 (FR4): a `$` before a non-ASCII character is literal in a
        double-quoted body and outside quotes, a non-ASCII letter included."""
        for label, written, text in (
            ("double quote, symbol", '"$€"', "$€"),
            ("double quote, letter", '"$é"', "$é"),
            ("double quote, letter, text around", '"a $é b"', "a $é b"),
            ("unquoted, symbol", "a$€b", "a$€b"),
            ("unquoted, letter", "$é", "$é"),
            ("single-quoted parts around an unquoted one", "'{\"a\":\"'$€'\"}'", '{"a":"$€"}'),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_STATIC, text), self.static(written))

    def test_a_non_ascii_character_after_a_continuation_is_literal(self):
        """TS-15 (FR3, FR4): a `$`, a line continuation and a non-ASCII
        character is a literal `$` and the character; the continuation
        vanishes."""
        c = self.cont
        for label, written, text in (
            ("double quote", '"5 $' + c() + '€"', "5 $€"),
            ("double quote, two continuations", '"5 $' + c(2) + '€"', "5 $€"),
            ("unquoted", "a$" + c() + "€b", "a$€b"),
        ):
            with self.subTest(label):
                self.assertEqual((GUARD.WORD_STATIC, text), self.static(written))

    def test_a_locale_quote_is_unrestorable_unless_it_holds_an_expansion(self):
        """TS-13, TS-15 (FR3, FR4): a locale quote whose body holds the FR3
        form or a `$` before a non-ASCII character holds no expansion, so it is
        Unrestorable (as any locale quote without one); with an expansion it is
        not static."""
        c = self.cont
        for label, written, expected in (
            ("plain", '$"abc"', (GUARD.WORD_UNRESTORABLE, None)),
            ("the FR3 form", '$"$' + c() + 'X"', (GUARD.WORD_UNRESTORABLE, None)),
            ("a dollar before a non-ASCII character", '$"5 $€"', (GUARD.WORD_UNRESTORABLE, None)),
            ("an expansion", '$"$X"', (GUARD.WORD_NOT_STATIC, None)),
        ):
            with self.subTest(label):
                self.assertEqual(expected, self.static(written))

    def test_the_docstrings_and_the_comment_name_the_fr3_form(self):
        """AC-6 (FR7, FR10): the docstrings of the readers, step 4 of the
        decision's docstring and the comment above the Unrestorable ask write
        the FR3 form the same way."""
        decision = " ".join(GUARD._mcp_bridge_args_json_chunks.__doc__.split())
        step4 = decision[decision.index("4. Word outcomes"):decision.index("5. Values")]
        with open(HOOK, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        at = lines.index("ARGS_JSON_UNRESTORABLE_ASK = (")
        comment = []
        for line in reversed(lines[:at]):
            if not line.startswith("#"):
                break
            comment.insert(0, line[1:].strip())
        texts = {
            "_read_static_word": GUARD._read_static_word.__doc__,
            "_read_double_quoted": GUARD._read_double_quoted.__doc__,
            "_read_word_as_written": GUARD._read_word_as_written.__doc__,
            "decision step 4": step4,
            "comment above the ask": " ".join(comment),
        }
        for label, text in texts.items():
            with self.subTest(label):
                self.assertIn(self.FR3_FORM, " ".join(text.split()))

    def test_the_docstrings_state_that_a_dollar_before_a_non_ascii_character_is_literal(self):
        """AC-6 (FR4, FR10): the docstrings of `_read_static_word()` and
        `_read_double_quoted()` say that a `$` before a non-ASCII character is
        a literal `$`."""
        for name in ("_read_static_word", "_read_double_quoted"):
            with self.subTest(name):
                doc = " ".join(getattr(GUARD, name).__doc__.split())
                self.assertIn("non-ASCII", doc)


class TestNamerefDeclarations(unittest.TestCase):
    """args-json-quoting-bypass TS-32 (FR1, FR9, NFR6; findings
    1d971862e2458376, 6083a3b46956a2f0, 4d1573a9f53b167f, 7bb299da67faace7): the
    nameref declarations the single-word-certain judgment consults are the ones
    Bash has in effect for the statement. A declaration command is recognised
    with Bash's word and redirection boundaries and through `command --`, so a
    glued form reads like its spaced form, and a derived chunk sees the
    declarations of every chunk around it. The notion call of each command
    below gives KIND_INSPECTED: its `--format "$r"` may expand to several
    arguments, so the notion pair is not excluded."""

    ARRAY = "A=(json --mcp desktop-commander --tool start_process); "
    NOTION = (
        "mcp-bridge run --mcp notion --tool notion-create-comment "
        "--format \"$r\" --args-json '{\"command\":\"git branch -D example\"}'"
    )
    DECLARE = "declare -n r='A[@]'"

    def kinds(self, command):
        """The kinds of the `mcp-bridge` statements of a statements() run of
        COMMAND (the entry point the TS-17 tests use)."""
        return Spy(command).kinds()

    def glued_and_spaced(self):
        """(label, the glued form, the spaced form) of every form TS-27 to
        TS-29 name; the spaced form is the one the scan always read."""
        notion = "; " + self.NOTION
        return (
            (
                "TS-27 input redirection touching declare",
                self.ARRAY + "declare</dev/null -n r='A[@]'" + notion,
                self.ARRAY + "declare </dev/null -n r='A[@]'" + notion,
            ),
            (
                "TS-27 output redirection touching declare",
                self.ARRAY + "declare>/dev/null -n r='A[@]'" + notion,
                self.ARRAY + "declare >/dev/null -n r='A[@]'" + notion,
            ),
            (
                "TS-29 source with &> touching it",
                "source&>/dev/null ./env.sh" + notion,
                "source &>/dev/null ./env.sh" + notion,
            ),
            (
                "TS-29 dot with &> touching it",
                ".&>/dev/null ./env.sh" + notion,
                ". &>/dev/null ./env.sh" + notion,
            ),
        )

    def every_command(self):
        """(label, command) of every command TS-27, TS-28, TS-29 and TS-30
        name, written out in full."""
        notion = "; " + self.NOTION
        commands = []
        for label, glued, spaced in self.glued_and_spaced():
            commands.append((label + " (glued)", glued))
            commands.append((label + " (spaced)", spaced))
        commands.extend(
            (
                (
                    "TS-28 redirection before the command name",
                    self.ARRAY + "</dev/null " + self.DECLARE + notion,
                ),
                (
                    "TS-30 command --",
                    self.ARRAY + "command -- " + self.DECLARE + notion,
                ),
                (
                    "TS-30 command -p --",
                    self.ARRAY + "command -p -- " + self.DECLARE + notion,
                ),
            )
        )
        return commands

    def test_the_notion_call_of_every_ts_27_to_30_command_is_inspected(self):
        """args-json-quoting-bypass TS-32: the `mcp-bridge` statement of every
        TS-27, TS-28, TS-29 and TS-30 command gives KIND_INSPECTED."""
        for label, command in self.every_command():
            with self.subTest(label):
                self.assertEqual([KIND_INSPECTED], self.kinds(command))

    def test_a_glued_form_gives_the_same_kind_as_its_spaced_form(self):
        """args-json-quoting-bypass TS-32: a redirection operator that touches
        the command name gives the kind the same command with a space gives."""
        for label, glued, spaced in self.glued_and_spaced():
            with self.subTest(label):
                self.assertEqual(self.kinds(spaced), self.kinds(glued))

    def test_a_redirection_in_any_place_is_left_out_of_the_command_name(self):
        """args-json-quoting-bypass TS-32 (6083a3b46956a2f0): a redirection
        before the name, touching it, or after it, with a file descriptor
        number, a `{name}` variable or a `>&` target, does not hide the
        declaration."""
        notion = "; " + self.NOTION
        for label, prefix in (
            ("descriptor number", "declare 2>/dev/null -n r='A[@]'"),
            ("descriptor variable", "declare {fd}>/dev/null -n r='A[@]'"),
            ("duplication target", "declare >&2 -n r='A[@]'"),
            ("before the name, touching", "</dev/null declare -n r='A[@]'"),
            ("after the options", "declare -n r='A[@]' </dev/null"),
            ("in a group", "{ declare</dev/null -n r='A[@]'; }"),
        ):
            with self.subTest(label):
                self.assertEqual(
                    [KIND_INSPECTED], self.kinds(self.ARRAY + prefix + notion)
                )

    def test_a_prefix_word_before_the_declaration_is_skipped(self):
        """args-json-quoting-bypass TS-32 (7bb299da67faace7): the words that
        stand before a command name (`command`, `builtin` and `time` with their
        own options and `--`, an assignment, a reserved word) do not hide a
        `declare -n` after them."""
        notion = "; " + self.NOTION
        for label, head in (
            ("command", "command " + self.DECLARE),
            ("builtin --", "builtin -- " + self.DECLARE),
            ("time -p --", "time -p -- " + self.DECLARE),
            ("assignment with +=", "x+=1 " + self.DECLARE),
            ("elif", "if false; then :; elif " + self.DECLARE + "; then :; fi"),
            ("command -p command --", "command -p command -- " + self.DECLARE),
        ):
            with self.subTest(label):
                self.assertEqual(
                    [KIND_INSPECTED], self.kinds(self.ARRAY + head + notion)
                )

    def test_a_declaration_with_no_nameref_option_does_not_make_the_call_uncertain(self):
        """args-json-quoting-bypass TS-32 (FR1): a glued redirection on a
        `declare` without `-n` (or on `echo`) and a comment that names a
        declaration do not mark the shell state, so the notion call keeps its
        exclusion and is not inspected."""
        call = self.NOTION.replace('"$r"', '"$SID"')
        for label, command in (
            ("declare without -n", self.ARRAY + "declare</dev/null -a r; " + call),
            ("echo with a glued redirection", self.ARRAY + "echo>/dev/null hello; " + call),
            ("command -- before echo", self.ARRAY + "command -- echo hello; " + call),
            ("comment that names a declaration", "echo a\n# " + self.DECLARE + "\n" + call),
        ):
            with self.subTest(label):
                self.assertEqual([KIND_NOTHING], self.kinds(command))

    def test_a_declaration_in_an_enclosing_chunk_counts_at_any_depth(self):
        """args-json-quoting-bypass TS-32 (1d971862e2458376): the notion call
        one, two and three command substitutions below a chunk that declares
        the nameref is inspected, wherever that chunk stands in the chain."""
        for label, command in (
            (
                "declaration one level above the call's chunk",
                self.ARRAY + "echo $(" + self.DECLARE + "; echo $(" + self.NOTION + "))",
            ),
            (
                "declaration two levels above the call's chunk",
                self.ARRAY + "echo $(" + self.DECLARE + "; echo $(echo $(" + self.NOTION + ")))",
            ),
            (
                "declaration in the command itself, call three levels down",
                self.ARRAY + self.DECLARE + "; echo $(echo $(echo $(" + self.NOTION + ")))",
            ),
        ):
            with self.subTest(label):
                self.assertEqual([KIND_INSPECTED], self.kinds(command))

    def test_no_declaration_anywhere_keeps_the_nested_call_excluded(self):
        """args-json-quoting-bypass TS-32 (TS-31): with no declaration in any
        chunk of the chain, a notion call with `--session "$SID"` below one or
        two command substitutions is not inspected."""
        call = self.NOTION.replace('"$r"', '"$SID"')
        for label, command in (
            ("one level", "echo $(" + call + ")"),
            ("two levels", "echo $(echo $(" + call + "))"),
        ):
            with self.subTest(label):
                self.assertEqual([KIND_NOTHING], self.kinds(command))

    def test_the_chain_is_walked_without_recursion(self):
        """args-json-quoting-bypass TS-32 (1d971862e2458376): a declaration at
        the top of a chain far deeper than the interpreter's recursion limit
        still reaches the innermost chunk."""
        top = GUARD._MarkedText.plain(self.DECLARE)
        node = top
        for _ in range(3 * sys.getrecursionlimit()):
            inner = GUARD._MarkedText.plain("echo x")
            inner._is_derived = True
            inner._outer_marked = node
            node = inner
        self.assertTrue(GUARD._args_json_nameref_declared(node))
        quiet = GUARD._MarkedText.plain("echo x")
        node = quiet
        for _ in range(3 * sys.getrecursionlimit()):
            inner = GUARD._MarkedText.plain("echo x")
            inner._is_derived = True
            inner._outer_marked = node
            node = inner
        self.assertFalse(GUARD._args_json_nameref_declared(node))

    def test_a_derived_chunk_without_a_link_reads_as_declared(self):
        """args-json-quoting-bypass TS-32: a derived chunk that carries no
        link to the chunk it came from reads as "may declare" (fail safe)."""
        orphan = GUARD._MarkedText.plain("echo x")
        orphan._is_derived = True
        self.assertTrue(GUARD._args_json_nameref_declared(orphan))


class TestCommandNameAllowlist(unittest.TestCase):
    """args-json-deferred-eval-bypass TS-2 to TS-6, TS-8 and TS-14 (FR1 to FR3,
    FR6, FR7, NFR1): the command-level reading of a chunk classifies every
    simple command's name by an allowlist, reads the arithmetic command as
    uncertain and reads the command-level evaluation triggers as uncertain.
    A chunk read as uncertain drops the notion-pair exclusion, so the notion
    call after it gives KIND_INSPECTED; a chunk that holds only allowlisted
    names and no trigger keeps the exclusion and gives KIND_NOTHING with
    `--session "$SID"`."""

    ARRAY = "A=(json --mcp desktop-commander --tool start_process); "
    NOTION = (
        "mcp-bridge run --mcp notion --tool notion-create-comment "
        "--format \"$r\" --args-json '{\"command\":\"git branch -D example\"}'"
    )

    def kinds(self, command):
        """The kinds of the `mcp-bridge` statements of a statements() run of
        COMMAND."""
        return Spy(command).kinds()

    def call_sid(self):
        """The notion call whose `--session "$SID"` is one word for certain."""
        return self.NOTION.replace('--format "$r"', '--session "$SID"')

    def uncertain(self, text):
        """Whether the chunk TEXT, followed by the notion call with
        `--session "$SID"`, reads as uncertain: the call is inspected only
        when the chunk may declare a nameref or leave the shell state
        uncertain, so this is the per-chunk answer as the whole judgment
        reaches it (substitutions already replaced by markers)."""
        return self.kinds(text + "; " + self.call_sid()) == [KIND_INSPECTED]

    def attack_forms(self):
        """(label, form) of every form TS-2 to TS-6 name that stands before
        the notion call, written out in full."""
        forms = [
            ("TS-2 `$''{`-split value evaluated by (( a ))",
             "a='z[$''{ declare -gn r=A[@]; }0]'; (( a ))"),
            ("TS-2 ANSI-C value evaluated by (( a ))",
             "a=$'z[$\\x7b declare -gn r=A[@]; }0]'; (( a ))"),
            ("TS-3 value read from a quoted-delimiter heredoc",
             "read -r a <<'EOF'\nz[0]\nEOF\n(( a ))"),
            ("TS-3 value read from a file", "read -r a < value.txt; (( a ))"),
            ("TS-4 arithmetic command", "((x=1))"),
            ("TS-4 arithmetic command as an if condition",
             "if ((a)); then :; fi"),
            ("TS-4 for ((...))", "for ((i=0; i<1; i++)); do :; done"),
            ("TS-4 let", "let a"),
            ("TS-4 [[ -v", "[[ -v a ]]"),
            ("TS-4 declare -i", "declare -i x"),
            ("TS-4 local -i", "local -i x"),
            ("TS-4 local -i in a function body", "f() { local -i x=1; }"),
            ("TS-4 typeset -gi", "typeset -gi x"),
            ("TS-4 prefix assignment to OPTIND", "OPTIND=1 :"),
            ("TS-4 prefix assignment to PS4", "PS4=x :"),
            ("TS-4 declare OPTIND=...", "declare OPTIND=1"),
            ("TS-4 set -x", "set -x"),
            ("TS-4 set -o xtrace", "set -o xtrace"),
            ("TS-4 declare with a variable subscript", "declare 'a[$i]=1'"),
            ("TS-4 let in a group", "{ let a; }"),
            ("TS-4 let in an if body", "if true; then let a; fi"),
            ("TS-4 let in a while body", "while false; do let a; done"),
            ("TS-6 printf -v", "printf -v x y"),
            ("TS-6 printf with %n", "printf '%n' x"),
            ("TS-6 read", "read x"),
            ("TS-6 getopts", "getopts o x"),
            ("TS-6 wait -p", "wait -p x"),
            ("TS-6 unset", "unset x"),
            ("TS-6 test -v", "test -v x"),
            ("TS-6 [ -v", "[ -v x ]"),
            ("TS-6 a function defined and called in the chunk", "f() { :; }; f"),
            ("TS-6 an unclassified name", "frobnicate x"),
        ]
        for op in ("-eq", "-ne", "-lt", "-le", "-gt", "-ge"):
            forms.append(("TS-4 [[ " + op, "[[ a " + op + " b ]]"))
        for name in ("fc", "history", "enable", "compgen", "complete", "bind"):
            forms.append(("TS-5 " + name, name))
            forms.append(("TS-5 builtin " + name, "builtin " + name))
            forms.append(("TS-5 command " + name, "command " + name))
        return forms

    def certain_forms(self):
        """(label, form) of every form the plan keeps certain."""
        return (
            ("echo with a quoted substitution", 'echo "$(cat x)"'),
            ("printf with a plain format", "printf '%s\\n' x"),
            ("test -n", "test -n x"),
            ("[ a = b ]", "[ a = b ]"),
            ("[[ a == b ]]", "[[ a == b ]]"),
            ("true", "true"),
            ("colon", ":"),
            ("if true", "if true; then echo a; fi"),
            ("while false", "while false; do echo a; done"),
            ("command -- echo", "command -- echo hello"),
            ("declare -a", "declare -a r"),
        )

    def test_the_notion_call_after_each_uncertain_form_is_inspected(self):
        """TS-2 to TS-6: the `mcp-bridge` statement after each form, with
        `--format "$r"`, gives KIND_INSPECTED."""
        for label, form in self.attack_forms():
            with self.subTest(label):
                self.assertEqual(
                    [KIND_INSPECTED],
                    self.kinds(self.ARRAY + form + "; " + self.NOTION),
                )

    def test_each_uncertain_form_reads_as_an_uncertain_chunk(self):
        """TS-2 to TS-6: the per-chunk answer for each form on its own is
        True."""
        for label, form in self.attack_forms():
            with self.subTest(label):
                self.assertTrue(self.uncertain(form))

    def test_each_certain_form_keeps_the_exclusion(self):
        """TS-8 (FR6): a chunk of allowlisted names and no trigger reads as
        certain, and the notion call with `--session "$SID"` after it gives
        KIND_NOTHING."""
        for label, form in self.certain_forms():
            with self.subTest(label):
                self.assertEqual(
                    [KIND_NOTHING],
                    self.kinds(form + "; " + self.call_sid()),
                )

    def test_an_arithmetic_command_without_blanks_makes_the_call_uncertain(self):
        """FR7 (moved from the TestNamerefDeclarations subtest): the notion
        call after `((x=1));` is inspected."""
        self.assertEqual([KIND_INSPECTED], self.kinds("((x=1)); " + self.call_sid()))

    def test_an_arithmetic_command_reads_as_uncertain_wherever_a_command_stands(self):
        """FR2: `((...))` is uncertain on its own, with blanks, without
        blanks, as an `if` and a `while` condition, inside a group, a loop
        body, a function body under an allowlisted name and `for ((...))`."""
        for label, text in (
            ("on its own", "(( a ))"),
            ("without blanks", "((x=1))"),
            ("as an if condition", "if ((a)); then :; fi"),
            ("as a while condition", "while ((a)); do :; done"),
            ("inside a group", "{ ((a)); }"),
            ("inside a loop body", "while true; do ((a)); done"),
            ("inside a function body", "echo() { ((a)); }"),
            ("for ((...))", "for ((i=0; i<1; i++)); do :; done"),
            ("after an operator", "true && ((a))"),
        ):
            with self.subTest(label):
                self.assertTrue(self.uncertain(text))

    def test_the_moved_subtest_leaves_no_arithmetic_command_in_its_docstring(self):
        """FR7: the docstring of the TestNamerefDeclarations test the
        `'arithmetic command without blanks'` subtest left no longer names an
        arithmetic command."""
        doc = " ".join(
            inspect.getdoc(
                TestNamerefDeclarations
                .test_a_declaration_with_no_nameref_option_does_not_make_the_call_uncertain
            ).split()
        )
        self.assertNotIn("arithmetic command", doc)

    def test_every_deny_entry_of_the_feature_pins_the_existing_reason_id(self):
        """FR5, FR8, NFR3 (TS-10, TS-15): each case-table entry whose label
        starts with `args-json-deferred-eval-bypass` and that expects deny
        carries `{"rule": "git-branch-force-delete"}`, and the entries cover
        TS-2 to TS-6."""
        cases = os.path.join(ROOT, "em-workflow", "hooks", "tests", "destructive-guard-cases.json")
        with open(cases, encoding="utf-8") as handle:
            entries = [
                case for case in json.load(handle)
                if case[1].startswith("args-json-deferred-eval-bypass")
            ]
        covered = set()
        for case in entries:
            covered.add(case[1].split()[1].rstrip(":"))
            if case[0] == "deny":
                with self.subTest(case[1][:60]):
                    self.assertEqual({"rule": "git-branch-force-delete"}, case[3])
        self.assertLessEqual({"TS-2", "TS-3", "TS-4", "TS-5", "TS-6"}, covered)

    def test_a_word_holding_an_arithmetic_command_is_not_restorable(self):
        """FR2: `_args_json_declaration_word()` no longer keeps an arithmetic
        command as restorable text."""
        marked = GUARD._MarkedText.plain("((x=1))")
        ((words, _lexed, _sep),) = list(GUARD.lex_segments(marked))
        (word,) = words
        self.assertFalse(GUARD._args_json_declaration_word(marked, word)[1])

    def test_a_name_the_old_denylist_held_stays_uncertain(self):
        """FR3: the names of the former denylist are now "any other name"."""
        for text in (
            "eval x", "source f", ". f", "trap : DEBUG", "alias a=b",
            "mapfile x", "readarray x",
        ):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text))

    def test_the_name_after_a_prefix_is_classified_the_same_way(self):
        """FR3: the name after `builtin`, `command`, `exec`, `time` and `!`
        (with their own options and `--`) is classified like a bare name."""
        for text in (
            "builtin fc", "command -- read x", "command -p -- fc", "exec unset x",
            "time let a", "time -p -- let a", "! test -v x", "builtin -- history",
        ):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text))
        for text in (
            "builtin echo a", "command -- echo a", "exec true", "time :",
            "! false", "command -p printf '%s' a",
        ):
            with self.subTest(text):
                self.assertFalse(self.uncertain(text))

    def test_the_integer_attribute_set_holds_optind_and_each_member_is_uncertain(self):
        """FR1: a prefix assignment, a bare assignment and a `declare`
        argument whose target is in the integer-attribute set or is `PS4`
        reads as uncertain; any other target does not."""
        names = GUARD._ARGS_JSON_INTEGER_VARIABLES
        self.assertIn("OPTIND", names)
        for name in sorted(names) + ["PS4"]:
            for label, text in (
                ("prefix assignment", name + "=1 :"),
                ("bare assignment", name + "=1"),
                ("append assignment", name + "+=1 :"),
                ("declare argument", "declare " + name + "=1"),
                ("local argument", "local " + name + "=1"),
            ):
                with self.subTest(name + " " + label):
                    self.assertTrue(self.uncertain(text))
        for text in ("x=1 :", "x=1", "declare x=1", "local y=2", "PS1=x :"):
            with self.subTest(text):
                self.assertFalse(self.uncertain(text))

    def test_printf_is_uncertain_only_for_an_option_or_a_percent_n_conversion(self):
        """FR3: `printf` with a leading option word, a format holding a `%n`
        conversion (flags, width, precision and length modifiers allowed
        between), or an option or format word that cannot be restored."""
        for text in (
            "printf -v x y", "printf -vx y", "printf -x y", "printf - x",
            "printf '%n' x", "printf '%5n' x", "printf '%-10.3ln' x",
            "printf '%s%n' a b", "printf \"%n\" x",
            "printf $o x", "printf \"$f\" x", "printf -- $f", "printf $f",
        ):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text), text)
        for text in (
            "printf '%s\\n' x", "printf -- '%s' x", "printf '%%n' x",
            "printf '%s' -v", "printf", "printf '%d%%' 5", "printf %s \"$x\"",
            "printf --", "printf -- -v x",
        ):
            with self.subTest(text):
                self.assertFalse(self.uncertain(text), text)

    def test_test_and_bracket_are_uncertain_for_v_or_an_unrestorable_word(self):
        """FR3 and NFR1: `test` / `[` with a word whose restored text is
        `-v`, or a word that cannot be restored (it may expand to `-v`)."""
        for text in (
            "test -v x", "[ -v x ]", "test \"-v\" x", "[ a -v ]",
            "test \"$x\"", "test $x", "[ $x = a ]", "[ \"$x\" = a ]",
            "test -n $(echo x)",
        ):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text), text)
        for text in ("test -n x", "[ a = b ]", "test", "[ ]", "[ -z '' ]"):
            with self.subTest(text):
                self.assertFalse(self.uncertain(text), text)

    def test_double_bracket_is_uncertain_only_for_an_arithmetic_operator_or_v(self):
        """FR1 and FR3: `[[` reads its operator words as written (they are
        never expanded), so an unrestorable operand does not matter."""
        for text in (
            "[[ a -eq b ]]", "[[ a -ne b ]]", "[[ a -lt b ]]", "[[ a -le b ]]",
            "[[ a -gt b ]]", "[[ a -ge b ]]", "[[ -v a ]]", "[[ $x -eq 1 ]]",
        ):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text), text)
        for text in (
            "[[ a == b ]]", "[[ $x == a ]]", "[[ \"$x\" = b ]]", "[[ -n a ]]",
            "[[ a == b* ]]",
        ):
            with self.subTest(text):
                self.assertFalse(self.uncertain(text), text)

    def test_a_declaration_builtin_is_uncertain_for_i_n_a_target_or_a_subscript(self):
        """FR1 and FR3: `declare`, `local` and `typeset` are uncertain for an
        option word holding `n` or `i`, a word that cannot be restored, an
        assignment to an integer-attribute target or `PS4`, and a `[...]`
        subscript that is not digits only, `@` or `*`."""
        for text in (
            "declare -n r", "local -n r", "typeset -n r", "declare -gn r",
            "declare -i x", "local -i x", "typeset -gi x", "declare -ir x",
            "declare \"$x\"", "declare -a $x", "declare 'a[$i]=1'",
            "declare 'a[i]=1'", "declare 'a=([$i]=1)'", "declare 'a[]=1'",
            "declare OPTIND=1", "typeset PS4=x",
        ):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text), text)
        for text in (
            "declare -a r", "declare -A m", "declare -p", "local x=1",
            "typeset -r y", "declare -g x=1", "declare 'a[0]=1'",
            "declare 'a[12]=1'", "declare 'r=A[@]'", "declare 'r=A[*]'",
            "declare -a r=(x y)",
        ):
            with self.subTest(text):
                self.assertFalse(self.uncertain(text), text)

    def test_a_command_name_that_cannot_be_restored_makes_the_chunk_uncertain(self):
        """NFR1: a name that holds an expansion, a substitution or a
        backtick cannot be settled and reads as uncertain."""
        for text in (
            "$cmd x", "\"$cmd\" x", "${cmd} x", "$(echo echo) x", "`echo echo` x",
            "e$x x", "\"$@\"", "ec*o x",
        ):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text), text)

    def test_the_words_of_a_compound_assignment_are_no_command(self):
        """The elements inside the parentheses of `NAME=(...)` are data, not a
        command name, so a name outside the allowlist there does not make the
        chunk uncertain; the same words after the closing parenthesis, or
        after a `;`, do."""
        for text in (
            "A=(x y z)", "A+=(b)", "declare -a A=(x y)", "A=()", "A=( x )",
            "A=(json --mcp desktop-commander --tool start_process)",
            "A=(eval x)", "A=($x)", "A=([0]=1)", "A=([@]=1 [12]=2)",
        ):
            with self.subTest(text):
                self.assertFalse(self.uncertain(text), text)
        for text in ("A=(x) eval y", "A=(x); frobnicate", "A=(x) let a"):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text), text)

    def test_a_subscript_element_of_a_compound_assignment_is_uncertain(self):
        """FR1: an element `[sub]=value` whose subscript is not digits only,
        `@` or `*` (Bash evaluates it as an arithmetic expression for an
        indexed array) reads as uncertain, wherever the element stands in the
        list."""
        for text in (
            "A=([i]=1)", "A=([$i]=1)", "A=(x [i]=1)", "A+=([i]+=1)",
            "declare -A m=([k]=v)", "declare -a m=([$i]=v)",
        ):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text), text)

    def test_a_function_definition_is_classified_by_its_name(self):
        """FR3: the name word of a definition is a simple command of its own,
        so a definition under a name outside the allowlist makes the chunk
        uncertain, and so does the `function` keyword; a definition under an
        allowlisted name keeps its body read as statements."""
        for text in ("f() { :; }", "function f { :; }", "f() { :; }; f", "echo() { let a; }"):
            with self.subTest(text):
                self.assertTrue(self.uncertain(text), text)

    def test_a_name_outside_the_allowlist_is_uncertain_whatever_its_words(self):
        """FR3: the list is closed; each of these is a name outside it."""
        for name in (
            "let", "read", "getopts", "wait", "unset", "set", "shopt", "fc",
            "history", "enable", "compgen", "complete", "bind", "eval",
            "source", ".", "trap", "alias", "mapfile", "readarray", "export",
            "readonly", "for", "select", "function", "coproc", "cat", "git",
            "ls", "frobnicate",
        ):
            with self.subTest(name):
                self.assertTrue(self.uncertain(name + " x"), name)
        with self.subTest("case"):
            self.assertTrue(self.uncertain("case x in a) :;; esac"))

    def test_the_allowlisted_names_are_certain_whatever_their_words(self):
        """FR3 and FR6: `mcp-bridge`, `echo`, `:`, `true`, `false`, `fi` and
        `done` are certain whatever their words hold."""
        for text in (
            "echo $x \"$(cat y)\" `z` \"$w\"", "mcp-bridge run --args-json '{}'",
            ": \"$x\" $(cat y)", "true $x", "false \"$y\"",
        ):
            with self.subTest(text):
                self.assertFalse(self.uncertain(text), text)


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

    def test_step_2_and_the_notion_pair_name_the_single_word_certain_condition(self):
        """args-json-quoting-bypass FR10 (TS-1 to TS-5): step 2 of the
        decision, the docstring of the notion-pair predicate and the comment
        above _MCP_RUN_VALUE_FLAGS state that the pair is determined only for
        single-word-certain value words."""
        flow = self.doc[: self.doc.index("Out of scope")]
        step_2 = flow[flow.index("2. Notion pair"): flow.index("3. Flag reading")]
        pair_doc = " ".join(inspect.getdoc(GUARD._args_json_notion_pair).split())
        for label, text in (("step 2", step_2), ("predicate", pair_doc)):
            for phrase in (
                "single-word-certain",
                "`--format`, `--session` and `--args-json` value words",
            ):
                with self.subTest(label + ": " + phrase):
                    self.assertIn(phrase, text)
        with open(HOOK, encoding="utf-8") as handle:
            source = handle.read()
        comment = source[: source.index("_MCP_RUN_VALUE_FLAGS = frozenset(")]
        comment = " ".join(comment[comment.rindex("# The flags of `mcp-bridge run`"):].split())
        with self.subTest("comment above _MCP_RUN_VALUE_FLAGS"):
            self.assertIn("single-word-certain", comment)

    def test_o2_item_8_states_the_word_count_shift_in_both_docstrings(self):
        """args-json-quoting-bypass FR6 (TS-12): O2 item 8 stands directly
        after item 2 and before item 3, with the scope of the SPEC's O2 (8),
        in the decision's docstring ("Out of scope" part) and in the
        out-of-scope declaration of extract_shell_payload_anchored()."""
        anchored = " ".join(inspect.getdoc(GUARD.extract_shell_payload_anchored).split())
        for label, text in (("decision", self.scope), ("anchored", anchored)):
            for phrase in (
                "2. a word in flag position that is not static in the same sense; 8. a value word of the mcp, tool, format or session flag",
                "or the value part after the `=` of a flag word",
                "that Bash expansion turns into a word count other than one",
                "shifting where mcp-bridge reads flags and values so that a later args-json value is hidden",
                "the flag reading reads words as written",
                "keeps its current verdict without the decoded-value inspection and is not sent to ask); 3. an unknown flag",
            ):
                with self.subTest(label + ": " + phrase):
                    self.assertIn(phrase, text)
        cases = os.path.join(ROOT, "em-workflow", "hooks", "tests", "destructive-guard-cases.json")
        with open(cases, encoding="utf-8") as handle:
            labels = [case[1] for case in json.load(handle)]
        with self.subTest("the TS-12 runner label names O2 (8)"):
            (label,) = [l for l in labels if l.startswith("args-json-quoting-bypass TS-12:")]
            self.assertIn("O2 (8)", label)



CASES_PATH = os.path.join(ROOT, "em-workflow", "hooks", "tests", "destructive-guard-cases.json")


class TestExpansionLevelDeferredEvaluation(unittest.TestCase):
    """args-json-deferred-eval-bypass task0001 (FR1, FR4, FR5, FR6, FR8, NFR1,
    NFR2; TS-1, TS-4, TS-9, TS-11, TS-12, TS-13, TS-14): a chunk that holds an
    expansion re-evaluating a value as code in the current shell, wherever the
    lexer reads it as syntax and in the body of an unquoted-delimiter heredoc,
    leaves the shell state uncertain, so the notion call of the chunk is
    inspected (KIND_INSPECTED). A construct that only stands in a data
    position (single quotes, a quoted-delimiter heredoc body), in a subshell
    body or as a harmless subscript or offset keeps the exclusion
    (KIND_NOTHING)."""

    ARRAY = "A=(json --mcp desktop-commander --tool start_process); "
    NOTION = (
        "mcp-bridge run --mcp notion --tool notion-create-comment "
        "--format \"$r\" --args-json '{\"command\":\"git branch -D example\"}'"
    )
    NOTION_SID = NOTION.replace('--format "$r"', '--session "$SID"')

    # (label, a form that carries the construct, with echo or `:` as the
    # command): the constructs of the table in the task plan, the enumerated
    # FR1 rows first.
    COUNTED = (
        ("arithmetic expansion", "echo $((a))"),
        ("bracket arithmetic", "echo $[a]"),
        ("assignment-word subscript with a $ expansion", "a[$i]=1"),
        ("assignment-word subscript with a name", "a[i]=1"),
        ("compound-assignment element with a $ expansion", "b=([$i]=v)"),
        ("compound-assignment element with a name", "b=([i]=v)"),
        ("compound assignment with a digit and a name element", "b=([2]=v [i]=w)"),
        ("parameter-expansion subscript with a $ expansion", 'echo "${a[$i]}"'),
        ("parameter-expansion subscript with a name", 'echo "${a[i]}"'),
        ("length of a subscripted name", 'echo "${#a[i]}"'),
        ("subscript followed by an operator", 'echo "${a[i]:-x}"'),
        ("subscript with a space around a digit", 'echo "${a[ 0 ]}"'),
        ("subscript with a sign", 'echo "${a[-1]}"'),
        ("subscript in the operand of another expansion", 'echo "${x:-${a[i]}}"'),
        ("@P transformation", 'echo "${x@P}"'),
        ("@P transformation of a subscripted name", 'echo "${a[0]@P}"'),
        ("@P transformation of a positional parameter", 'echo "${1@P}"'),
        ("@P transformation of a special parameter", 'echo "${@@P}"'),
        ("indirect expansion", 'echo "${!x}"'),
        ("indirect expansion with a subscript", 'echo "${!a[0]}"'),
        ("key list", 'echo "${!a[@]}"'),
        ("prefix list", "echo ${!pre*}"),
        ("assigning expansion with =", 'echo "${x=y}"'),
        ("assigning expansion with :=", 'echo "${x:=y}"'),
        ("assigning expansion of a subscripted name", 'echo "${a[0]:=y}"'),
        ("assigning expansion of PS4", 'echo "${PS4:=y}"'),
        ("substring with a name offset", 'echo "${s:p}"'),
        ("substring with a name length", 'echo "${s:0:n}"'),
        ("substring with an arithmetic offset", 'echo "${s:0-1}"'),
        ("substring of an array with a name offset", 'echo "${a[@]:n}"'),
        ("substring with a $ expansion length", 'echo "${s:1:$n}"'),
        ("arithmetic expansion in an operand", 'echo "${x:-$((a))}"'),
        ("@P in an operand", 'echo "${y:-${z@P}}"'),
        ("arithmetic expansion in a here-string", ': <<< "$((a))"'),
        ("expansion inside a brace command substitution", 'echo "${ echo $((a)); }"'),
    )

    # The positions the task plan names; {c} is the construct. The heredoc
    # position is checked apart (the body leaves the chunk text).
    POSITIONS = (
        ("function body", "f() { echo {c}; }"),
        ("{ } group", "{ echo {c}; }"),
        ("if body", "if true; then echo {c}; fi"),
        ("while body", "while false; do echo {c}; done"),
        ("for body", "for x in a; do echo {c}; done"),
        ("case item", "case x in a) echo {c};; esac"),
        ("conditional", "[[ x == {c} ]]"),
        ("double quotes", 'echo "{c}"'),
        ("here-string word", ': <<< "{c}"'),
        ("here-string word without quotes", ": <<< {c}"),
        ("subshell group", "( echo {c} )"),
    )
    CONSTRUCTS = (("arithmetic expansion", "$((a))"), ("@P transformation", "${x@P}"))

    def plain(self, text):
        return GUARD._MarkedText.plain(text)

    def defers(self, text):
        """The expansion-level reading of the chunk TEXT (no heredoc)."""
        return GUARD._args_json_has_deferred_evaluation(self.plain(text))

    def stripped(self, command):
        stripped, _records, _omap = GUARD._strip_heredocs_mapped(command)
        return stripped

    def marks(self, command):
        """Whether the heredoc removal of COMMAND carries the mark."""
        return isinstance(self.stripped(command), GUARD._StrippedWithShellSubstitution)

    def scans(self, command):
        """([(chunk source, result), ...] of the per-chunk scans a
        statements() run of COMMAND asked for, the kinds of its `mcp-bridge`
        statements). The first scan is the one of the chunk that holds the
        notion call."""
        original = GUARD._args_json_nameref_scan
        calls = []

        def spy(marked):
            result = original(marked)
            calls.append((str(marked.source), result))
            return result

        with mock.patch.object(GUARD, "_args_json_nameref_scan", spy):
            kinds = Spy(command).kinds()
        return calls, kinds

    def assert_uncertain(self, form):
        """The notion call after FORM is inspected; the chunk's scan, the
        first one asked for, reads true."""
        calls, kinds = self.scans(self.ARRAY + form + "; " + self.NOTION)
        self.assertEqual([KIND_INSPECTED], kinds)
        self.assertTrue(calls and calls[0][1], calls)

    def assert_certain(self, form):
        """The notion call (with `--session "$SID"`) after FORM keeps the
        exclusion; the chunk's scan, the first one asked for, reads false."""
        calls, kinds = self.scans(self.ARRAY + form + "; " + self.NOTION_SID)
        self.assertEqual([KIND_NOTHING], kinds)
        self.assertTrue(calls and not calls[0][1], calls)

    # --- AC-1: every counted construct ---------------------------------

    def test_the_ts_1_attack_form_reads_the_chunk_as_uncertain(self):
        """AC-1 (TS-1): a value that hides the opener with an ANSI-C quote is
        evaluated by `${p@P}` in double quotes."""
        form = "p=$'$\\x7b declare -gn r=A[@]; }'; : \"${p@P}\""
        with self.subTest("expansion level"):
            self.assertTrue(self.defers(form))
        with self.subTest("notion call"):
            self.assert_uncertain(form)

    def test_every_counted_construct_reads_the_chunk_as_uncertain(self):
        """AC-1 (TS-4): the expansion level reads each construct of the table
        as uncertain, and the notion call after it is inspected."""
        for label, form in self.COUNTED:
            with self.subTest(label + ": expansion level"):
                self.assertTrue(self.defers(form))
            with self.subTest(label + ": notion call"):
                self.assert_uncertain(form)

    # --- AC-2: positions ------------------------------------------------

    def test_an_arithmetic_expansion_and_at_p_are_read_at_every_position(self):
        """AC-2 (TS-4): a function body, a group, a conditional, a loop, double
        quotes and a here-string word."""
        for name, construct in self.CONSTRUCTS:
            for place, template in self.POSITIONS:
                form = template.replace("{c}", construct)
                with self.subTest(name + " in " + place + ": expansion level"):
                    self.assertTrue(self.defers(form))
                with self.subTest(name + " in " + place + ": notion call"):
                    self.assert_uncertain(form)

    def test_the_body_of_an_unquoted_delimiter_heredoc_is_read(self):
        """AC-2 (TS-4): an arithmetic expansion and a `${x@P}` in the body of a
        heredoc whose delimiter is not quoted mark the removed body, and the
        notion call after the heredoc is inspected."""
        for name, construct in self.CONSTRUCTS:
            command = ": <<EOF\n" + construct + "\nEOF\n"
            with self.subTest(name + ": mark"):
                self.assertTrue(self.marks(command))
            with self.subTest(name + ": notion call"):
                calls, kinds = self.scans(self.ARRAY + command + self.NOTION)
                self.assertEqual([KIND_INSPECTED], kinds)

    def test_every_counted_construct_marks_an_unquoted_heredoc_body(self):
        """AC-2: the constructs of the table that the shell expands in a
        heredoc body, read the way the shell expands it (a quote character
        there is literal)."""
        in_a_body = (
            "$((a))", "$[a]", "${p@P}", "${a[$i]}", "${a[i]}", "${#a[i]}", "${!x}",
            "${!a[@]}", "${x=y}", "${x:=y}", "${s:p}", "${s:0:n}", "${y:-$((a))}",
            "${y:-${z@P}}", "'${p@P}'", '"$((a))"', "text $((a)) text",
        )
        for body in in_a_body:
            with self.subTest(body):
                self.assertTrue(self.marks(": <<EOF\n" + body + "\nEOF\n"))

    def test_a_continuation_inside_the_opener_of_a_body_is_read(self):
        """AC-2 / AC-5: a backslash-newline between `$` and `((` in an unquoted
        body is removed by the shell before it expands the body."""
        self.assertTrue(self.marks(": <<EOF\n$\\\n((a))\nEOF\n"))
        self.assertTrue(self.marks(": <<EOF\n${p@\\\nP}\nEOF\n"))

    def test_an_escaped_backslash_before_a_newline_does_not_hide_a_construct(self):
        """AC-5: two backslashes and a newline are not a continuation; the
        construct on the next line still counts, however the removal of
        continuations reads the text."""
        self.assertTrue(self.marks(": <<EOF\n\\\\\n$((a))\nEOF\n"))

    # --- AC-3: what is not counted --------------------------------------

    def test_a_construct_in_a_subshell_body_keeps_the_exclusion(self):
        """AC-3 (TS-9): an arithmetic command, an arithmetic expansion and
        `${p@P}` that stand only inside a command substitution, a backtick
        substitution or a process substitution change the subshell, not the
        caller."""
        body = '(( a )); echo $((a)); echo "${p@P}"'
        for label, form in (
            ("command substitution", "echo $( " + body + " )"),
            ("backtick substitution", "echo `" + body + "`"),
            ("process substitution", "echo <( " + body + " )"),
        ):
            with self.subTest(label + ": expansion level"):
                self.assertFalse(self.defers(form))
            with self.subTest(label + ": notion call"):
                self.assert_certain(form)

    def test_a_construct_nested_in_substitutions_keeps_the_exclusion(self):
        """AC-3 (D2): the substitution need not be the nearest region."""
        for form in (
            "echo $(echo $(echo $((a))))",
            'echo "$(echo ${p@P})"',
            "echo ${x:-$(echo $((a)))}",
            "echo ${x:-`echo ${y@P}`}",
            "cat <(echo ${z:=1})",
        ):
            with self.subTest(form):
                self.assertFalse(self.defers(form))

    def test_a_data_position_keeps_the_exclusion(self):
        """AC-3 (TS-11, A3): single quotes, ANSI-C quotes and comments hold
        data."""
        for label, form in (
            ("single quotes", "echo '(( a )) $((a)) ${p@P} ${!x}'"),
            ("ANSI-C quotes", "echo $'$((a)) ${p@P} ${!x}'"),
            ("a comment", "echo hello # $((a)) ${p@P} ${!x}\n:"),
        ):
            with self.subTest(label + ": expansion level"):
                self.assertFalse(self.defers(form))
            with self.subTest(label + ": notion call"):
                self.assert_certain(form)

    def test_the_body_of_a_quoted_delimiter_heredoc_keeps_the_exclusion(self):
        """AC-3 (TS-11, A3): a quoted delimiter makes the body inert."""
        body = "$(( a ))\n${p@P}\n${!x}\n"
        for delimiter in ("'EOF'", '"EOF"', "\\EOF"):
            command = "echo <<" + delimiter + "\n" + body + "EOF\n"
            with self.subTest(delimiter + ": mark"):
                self.assertFalse(self.marks(command))
            with self.subTest(delimiter + ": notion call"):
                calls, kinds = self.scans(self.ARRAY + command + self.NOTION_SID)
                self.assertEqual([KIND_NOTHING], kinds)
                self.assertTrue(calls and not calls[0][1], calls)

    def test_a_body_with_nothing_to_evaluate_keeps_the_exclusion(self):
        """AC-3 (TS-11): an unquoted body whose expansions evaluate nothing, a
        bare `((` (literal in a body), and a body with no `$` do not mark."""
        for body in (
            "hello",
            "((a))",
            "${A[0]} ${A[@]} ${A[*]}",
            "${s:1:2} ${x:-y} ${x#p}",
            "$(echo $((a)))",
            "`echo $((a))`",
            "\\$((a)) \\${p@P}",
            "$HOME $1 $@",
        ):
            with self.subTest(body):
                self.assertFalse(self.marks(": <<EOF\n" + body + "\nEOF\n"))
        for command in ("cat <<EOF\nhello\nEOF\n", "cat <<EOF\n$HOME\nEOF\n"):
            with self.subTest(command):
                self.assertIs(str, type(self.stripped(command)))

    def test_a_harmless_subscript_keeps_the_exclusion(self):
        """AC-3 (TS-11, A4): digit-only, `@` and `*` subscripts and compound
        assignments without subscripts evaluate nothing."""
        for form in (
            'echo "${A[0]}" "${A[@]}" "${A[*]}"',
            'echo "${#A[@]}" "${#A[0]}"',
            'echo "${A[@]:1:2}" "${A[0]:-x}" "${A[12]}"',
            "B=(x y z)",
            "B+=(x y)",
            "c[2]=1",
            "d=([2]=v [10]=w)",
        ):
            with self.subTest(form + ": expansion level"):
                self.assertFalse(self.defers(form))
        with self.subTest("notion call"):
            self.assert_certain('echo "${A[0]}" "${A[@]}" "${A[*]}"')
        with self.subTest("notion call, compound assignment"):
            self.assert_certain("B=(x y z)")

    def test_a_parameter_expansion_that_evaluates_nothing_keeps_the_exclusion(self):
        """AC-3: the other forms of a parameter expansion are not counted: a
        default or alternative word, a pattern removal or replacement, a
        case change, the other transformations and the length."""
        for form in (
            'echo "${x}"', 'echo "${x:-y}"', 'echo "${x-y}"', 'echo "${x:+y}"',
            'echo "${x+y}"', 'echo "${x:?y}"', 'echo "${x?y}"', 'echo "${x#p}"',
            'echo "${x##p}"', 'echo "${x%p}"', 'echo "${x%%p}"', 'echo "${x/a/b}"',
            'echo "${x//a/b}"', 'echo "${x^^}"', 'echo "${x,,}"', 'echo "${x@Q}"',
            'echo "${x@U}"', 'echo "${x@a}"', 'echo "${#x}"', 'echo "${#}"',
            'echo "${@}"', 'echo "${*}"', 'echo "${x:-@P}"', 'echo "${x:-=}"',
            'echo "${x:-:=}"', 'echo "${a[0]@Q}"', 'echo "${@:2}"', 'echo "${*:1:2}"',
            'echo "${x/=/y}"', 'echo "${x%:=}"',
        ):
            with self.subTest(form):
                self.assertFalse(self.defers(form))

    # --- AC-3 (TS-12): substrings --------------------------------------

    def test_a_substring_whose_offset_or_length_is_not_digits_is_uncertain(self):
        """AC-3 (TS-12): the notion call after `${s:p}` and `${s:0:n}` is
        inspected."""
        for form in ('echo "${s:p}"', 'echo "${s:0:n}"'):
            with self.subTest(form):
                self.assert_uncertain(form)

    def test_a_substring_made_of_digits_keeps_the_exclusion(self):
        """AC-3 (TS-12): digit offsets and lengths, with an optional sign and
        blanks, evaluate nothing; `:-`, `:+` and `:?` are not substrings."""
        for form in (
            'echo "${s:1:2}"', 'echo "${s:1}"', 'echo "${s: -1}"', 'echo "${s: 1 : 2 }"',
            'echo "${s:+1}"', 'echo "${s::2}"', 'echo "${s:-1}"', 'echo "${s:+p}"',
            'echo "${s:?p}"', 'echo "${@:1:2}"',
        ):
            with self.subTest(form + ": expansion level"):
                self.assertFalse(self.defers(form))
        with self.subTest("notion call"):
            self.assert_certain('echo "${s:1:2}"')

    # --- AC-4 -------------------------------------------------------------

    def test_the_literal_check_is_still_consulted_by_the_scan(self):
        """AC-4 (FR4): a chunk whose other sources are quiet reads as
        uncertain when `_args_json_has_brace_substitution()` holds."""
        chunk = self.plain("echo hello")
        self.assertFalse(GUARD._args_json_nameref_scan(chunk))
        with mock.patch.object(GUARD, "_args_json_has_brace_substitution", return_value=True):
            self.assertTrue(GUARD._args_json_nameref_scan(chunk))

    def test_the_literal_check_still_reads_a_quoted_opener(self):
        """AC-4 (FR4): a quoted `${ ` is still read by the literal check, not
        by the expansion level, which sees nothing in single quotes."""
        chunk = self.plain("p='${ declare -gn r=A[@]; }'")
        self.assertFalse(GUARD._args_json_has_deferred_evaluation(chunk))
        self.assertTrue(GUARD._args_json_has_brace_substitution(chunk))
        self.assertTrue(GUARD._args_json_nameref_scan(chunk))

    # --- AC-5: failures, once per chunk, no recursion --------------------

    def test_a_chunk_the_lexer_cannot_settle_reads_as_uncertain(self):
        """AC-5 (NFR1, TM-4; TS-13): the expansion level reads true, and
        nothing is raised, when the lexer fails for the chunk's text with its
        work bound or with any other exception."""
        for exc in (
            GUARD.LexBudgetExceeded("work bound"),
            GUARD.LexUnmatchedSubscript("subscript"),
            RuntimeError("anything"),
            RecursionError("deep"),
        ):
            chunk = self.plain("echo hello")

            def failing(*_args, **_kwargs):
                raise exc

            with self.subTest(type(exc).__name__):
                with mock.patch.object(GUARD, "lex_shell", failing):
                    self.assertTrue(GUARD._args_json_has_deferred_evaluation(chunk))
                    self.assertTrue(GUARD._args_json_nameref_scan(chunk))

    def test_a_heredoc_body_the_lexer_cannot_settle_marks_the_removal(self):
        """AC-5 (NFR1, TM-4; TS-14): the removal step returns a marked text and
        raises nothing when the lexer fails for an unquoted body, and does not
        read a quoted body at all."""
        original = GUARD.lex_shell
        modes = []

        def failing_for_bodies(text, mode="shell", *args, **kwargs):
            modes.append(mode)
            if mode == "heredoc-body":
                raise exc
            return original(text, mode, *args, **kwargs)

        for exc in (GUARD.LexBudgetExceeded("work bound"), RuntimeError("anything")):
            with self.subTest(type(exc).__name__ + ", unquoted"):
                del modes[:]
                with mock.patch.object(GUARD, "lex_shell", failing_for_bodies):
                    stripped, records, _omap = GUARD._strip_heredocs_mapped(
                        ": <<EOF\nhello $HOME\nEOF\n"
                    )
                self.assertIsInstance(stripped, GUARD._StrippedWithShellSubstitution)
                self.assertEqual(1, len(records))
                self.assertIn("heredoc-body", modes)
            with self.subTest(type(exc).__name__ + ", quoted"):
                with mock.patch.object(GUARD, "lex_shell", failing_for_bodies):
                    stripped, _records, _omap = GUARD._strip_heredocs_mapped(
                        ": <<'EOF'\nhello $HOME\nEOF\n"
                    )
                self.assertIs(str, type(stripped))

    def test_a_body_with_no_dollar_is_not_lexed(self):
        """AC-5 (NFR2): no construct of the expansion level lacks a `$` in a
        body, so such a body costs no lexing."""
        original = GUARD.lex_shell
        modes = []

        def counting(text, mode="shell", *args, **kwargs):
            modes.append(mode)
            return original(text, mode, *args, **kwargs)

        with mock.patch.object(GUARD, "lex_shell", counting):
            GUARD._strip_heredocs_mapped(": <<EOF\nhello\nEOF\n")
        self.assertNotIn("heredoc-body", modes)

    def test_the_expansion_level_reading_runs_once_per_chunk(self):
        """AC-5 (NFR2): the per-chunk answer of the same chunk, asked for
        twice, runs the expansion-level reading once."""
        chunk = self.plain("echo hello")
        original = GUARD._args_json_has_deferred_evaluation
        calls = []

        def spy(marked):
            calls.append(marked)
            return original(marked)

        with mock.patch.object(GUARD, "_args_json_has_deferred_evaluation", spy):
            first = GUARD._args_json_nameref_declared(chunk)
            second = GUARD._args_json_nameref_declared(chunk)
        self.assertEqual((False, False), (first, second))
        self.assertEqual(1, len(calls))

    def test_a_derived_chunk_reads_its_own_text_and_the_ones_around_it(self):
        """AC-5 (NFR2): a chunk with an expansion of its own is uncertain, and
        so is a chunk derived from it."""
        quiet = self.plain("echo hello")
        loud = self.plain("echo $((a))")
        loud._is_derived = True
        loud._outer_marked = quiet
        self.assertTrue(GUARD._args_json_nameref_declared(loud))
        inner = self.plain("echo x")
        inner._is_derived = True
        inner._outer_marked = loud
        self.assertTrue(GUARD._args_json_nameref_declared(inner))

    def test_the_expansion_level_reading_is_called_only_from_the_scan(self):
        """AC-5 (NFR2): its result is cached with the per-chunk answer because
        nothing else calls it."""
        with open(HOOK, encoding="utf-8") as handle:
            sites = _CallSites()
            sites.visit(ast.parse(handle.read()))
        places = {
            where for name, where in sites.references
            if name == "_args_json_has_deferred_evaluation"
        }
        self.assertEqual({"_args_json_nameref_scan"}, places)

    def test_a_long_parameter_expansion_is_read_by_its_head(self):
        """AC-5: a long text costs a constant per region. A substring too long
        for the head reads as evaluating; other long expansions read by their
        head."""
        self.assertTrue(self.defers("echo ${s:1:2" + " " * 400 + "+n}"))
        self.assertFalse(self.defers("echo ${a[0]:-" + "x" * 400 + "}"))
        self.assertTrue(self.defers("echo ${a[i]:-" + "x" * 400 + "}"))

    def test_a_deep_nest_of_expansions_is_read(self):
        """AC-5: depth is read without recursion in the reading itself."""
        depth = 300
        text = "echo " + "${a:-" * depth + "x" + "}" * depth
        self.assertFalse(self.defers(text))
        text = "echo " + "${a:-" * depth + "${p@P}" + "}" * depth
        self.assertTrue(self.defers(text))

    # --- AC-6 -------------------------------------------------------------

    def test_the_docstring_of_the_scan_names_its_sources_and_no_command(self):
        """AC-6 / Conventions: the docstring of `_args_json_nameref_scan()`
        states its sources and refers to `_args_json_declares_nameref()` for
        the command-name rules; it names no command."""
        doc = " ".join(inspect.getdoc(GUARD._args_json_nameref_scan).split())
        for phrase in (
            "_args_json_has_brace_substitution()",
            "_args_json_has_deferred_evaluation()",
            "_args_json_declares_nameref()",
            "lex_segments()",
        ):
            with self.subTest(phrase):
                self.assertIn(phrase, doc)
        for command in (
            "declare", "local", "typeset", "eval", "source", "trap", "alias",
            "mapfile", "readarray", "echo", "mcp-bridge", "printf",
        ):
            with self.subTest("no " + command):
                self.assertIsNone(re.search(r"\b" + re.escape(command) + r"\b", doc))

    def test_the_marker_and_its_predicate_state_the_widened_meaning(self):
        """Conventions: the docstrings of the stripped-text marker type, its
        predicate, the removal step and `_ChunkLinks.register()` say that a
        removed body marks the chunk for an expansion that re-evaluates a
        value, not only for a current-shell substitution."""
        for obj in (
            GUARD._StrippedWithShellSubstitution,
            GUARD._bodies_hold_current_shell_substitution,
            GUARD._strip_heredocs_mapped,
            GUARD._ChunkLinks.register,
        ):
            doc = " ".join(inspect.getdoc(obj).split())
            with self.subTest(getattr(obj, "__qualname__", obj)):
                self.assertIn("re-evaluate", doc)

    def test_every_added_case_follows_the_label_and_rule_conventions(self):
        """AC-6 (FR5, FR8; TS-10): each case of this feature starts its label
        with `args-json-deferred-eval-bypass`; each deny case carries the
        existing reason ID of the decoded command."""
        with open(CASES_PATH, encoding="utf-8") as handle:
            cases = [
                case for case in json.load(handle)
                if case[1].startswith("args-json-deferred-eval-bypass")
            ]
        self.assertGreater(len(cases), 20)
        for case in cases:
            with self.subTest(case[1][:80]):
                if case[0] == "deny":
                    self.assertEqual(
                        {"rule": "git-branch-force-delete"},
                        case[3] if len(case) == 4 else None,
                    )
                else:
                    self.assertEqual("allow", case[0])


if __name__ == "__main__":
    unittest.main()
