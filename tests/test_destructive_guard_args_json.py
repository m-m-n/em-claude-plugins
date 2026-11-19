"""Unit tests of the `--args-json` step of `em-workflow/hooks/destructive-guard.py`
(feature mcp-bridge-args-json-exec-guard, task0001; FR4 to FR8, TM-2 to TM-4, A4).

The case runner (em-workflow/hooks/tests/run-destructive-guard.py) pins the
verdicts of the scenario table. This module checks what the table cannot see:

- TM-3 (AC-5): a decoder failure that is not a JSON syntax error, and nesting
  deeper than MAX_ARGS_JSON_DEPTH, give the Overrun result; a JSON syntax error
  and a top level that is not an object give Not inspected.
- TM-4 / FR7 (AC-6): the scan charge of an Inspected value covers the rebuilt
  value and every JSON value the walk visits, and statements() adds it to the
  running scanned total and takes the scan-budget early stop when it passes.
- FR5 / A4 (AC-6): each queued top-level `command` string takes one from the
  payload counter MAX_SHELL_PAYLOAD_EXPANSIONS sets; none is queued at zero,
  while the candidate bodies still are.
- FR4 / FR5 (AC-2, AC-5): what the walk collects, in document order, duplicates
  and an escaped key included.
- FR8 (AC-4): the docstring of the component lists every out-of-scope form.

The hook has no package, so the module is loaded from its file path with
bytecode writing off for the load. statements() is driven in-process; the
component's results are read through a spy that wraps it. Standard library
only.

A JSON escape for `$` or a backtick is written below as the six characters
backslash, `u`, `0024` (or `0060`), built by ESC_DOLLAR / ESC_BACKTICK, so the
text of a command reaches the hook as the six characters.
"""

import importlib.util
import inspect
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "em-workflow", "hooks", "destructive-guard.py")

ESC_DOLLAR = "\\" + "u0024"
ESC_BACKTICK = "\\" + "u0060"

RUN_HEAD = "mcp-bridge run --mcp desktop-commander --tool start_process --args-json "


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


class Spy:
    """The results of _mcp_bridge_args_json_chunks() over a statements() run
    for the statements whose command word is `mcp-bridge` (the statements a
    queued chunk adds are other commands), and the statements the run
    yielded."""

    def __init__(self, command, early_stop=None):
        self.results = []
        self.all_kinds = []
        self.statements = []
        self.early_stop = [] if early_stop is None else early_stop
        original = GUARD._mcp_bridge_args_json_chunks

        def spy(shaped_words, marked):
            result = original(shaped_words, marked)
            self.all_kinds.append(result.kind)
            if GUARD.head(shaped_words)[0] == "mcp-bridge":
                self.results.append(result)
            return result

        with mock.patch.object(GUARD, "_mcp_bridge_args_json_chunks", spy):
            for statement in GUARD.statements(command, early_stop=self.early_stop):
                self.statements.append(statement[0])

    def inspected(self):
        """The results of the Inspected kind, in statement order."""
        return [r for r in self.results if r.kind == GUARD.ARGS_JSON_INSPECTED]

    def kinds(self):
        return [r.kind for r in self.results]


class TestDecoderFailure(unittest.TestCase):
    """AC-5 (TM-3): which decoder failures are Overrun and which are Not
    inspected."""

    VALUE = '{"command":"ls","shell":"bash"}'

    def test_failure_that_is_not_a_syntax_error_is_overrun(self):
        with mock.patch.object(
            json.JSONDecoder, "decode", side_effect=RuntimeError("decoder failed")
        ):
            spy = Spy(run_command(self.VALUE))
        self.assertEqual([GUARD.ARGS_JSON_OVERRUN], spy.kinds())

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
        self.assertEqual([GUARD.ARGS_JSON_OVERRUN], spy.kinds())

    def test_a_json_syntax_error_is_not_inspected(self):
        for value in ('{"command":"ls"', '{"command":}', "", "{'command':'ls'}"):
            with self.subTest(value=value):
                spy = Spy(run_command(value))
                self.assertEqual([GUARD.ARGS_JSON_NOT_INSPECTED], spy.kinds())
                self.assertEqual([], spy.early_stop)

    def test_a_top_level_that_is_not_an_object_is_not_inspected(self):
        for value in ('["a"]', '"a"', "1", "null", "true"):
            with self.subTest(value=value):
                spy = Spy(run_command(value))
                self.assertEqual([GUARD.ARGS_JSON_NOT_INSPECTED], spy.kinds())

    def test_nesting_above_the_bound_is_overrun_before_the_decoder_runs(self):
        deep = '{"a":' + "[" * GUARD.MAX_ARGS_JSON_DEPTH + "]" * GUARD.MAX_ARGS_JSON_DEPTH + "}"
        with mock.patch.object(
            json.JSONDecoder, "decode", side_effect=AssertionError("decoder reached")
        ):
            spy = Spy(run_command(deep))
        self.assertEqual([GUARD.ARGS_JSON_OVERRUN], spy.kinds())

    def test_nesting_at_the_bound_is_decoded(self):
        edge = '{"a":' + "[" * (GUARD.MAX_ARGS_JSON_DEPTH - 1) + "]" * (GUARD.MAX_ARGS_JSON_DEPTH - 1) + "}"
        spy = Spy(run_command(edge))
        self.assertEqual([GUARD.ARGS_JSON_INSPECTED], spy.kinds())

    def test_brackets_inside_strings_do_not_count_as_nesting(self):
        value = '{"a":"' + "[" * 300 + '","b":"\\"' + "{" * 300 + '"}'
        spy = Spy(run_command(value))
        self.assertEqual([GUARD.ARGS_JSON_INSPECTED], spy.kinds())

    def test_the_bound_is_one_hundred(self):
        self.assertEqual(100, GUARD.MAX_ARGS_JSON_DEPTH)


class TestCharge(unittest.TestCase):
    """AC-6 (TM-4, FR7): the scan charge of an Inspected value."""

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

    def test_the_charge_is_added_to_the_scanned_total(self):
        word_command = run_command('{"command":"ls"}')
        word = None

        def capture(shaped_words, marked):
            nonlocal word
            word = shaped_words[-1]
            return GUARD.ArgsJsonResult(GUARD.ARGS_JSON_NOT_INSPECTED, 0, (), (), None)

        with mock.patch.object(GUARD, "_mcp_bridge_args_json_chunks", capture):
            list(GUARD.statements(word_command))
        self.assertIsNotNone(word)

        def inspected(charge):
            def step(shaped_words, marked):
                if GUARD.head(shaped_words)[0] != "mcp-bridge":
                    return GUARD.ArgsJsonResult(
                        GUARD.ARGS_JSON_NOT_INSPECTED, 0, (), (), None
                    )
                return GUARD.ArgsJsonResult(
                    GUARD.ARGS_JSON_INSPECTED, charge, ("echo body",), (), word
                )

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
    """AC-6 (FR5, A4): a queued top-level `command` string takes one from the
    payload counter; none is queued at zero, bodies are."""

    VALUE = (
        '{"command":"echo MARK-CMD ' + ESC_DOLLAR + '(echo MARK-BODY)","shell":"bash"}'
    )

    def command_after(self, payloads):
        """A command whose `mcp-bridge run` statement follows PAYLOADS
        `bash -c` payloads."""
        return "; ".join(["bash -c 'true'"] * payloads + [run_command(self.VALUE)])

    def yielded(self, command):
        return [s[0] for s in GUARD.statements(command)]

    def test_the_counter_is_twenty_five(self):
        self.assertEqual(25, GUARD.MAX_SHELL_PAYLOAD_EXPANSIONS)

    def test_with_the_counter_used_up_the_command_string_is_not_queued(self):
        texts = self.yielded(self.command_after(GUARD.MAX_SHELL_PAYLOAD_EXPANSIONS))
        self.assertIn("echo MARK-BODY", texts)
        self.assertFalse(any(t.startswith("echo MARK-CMD") for t in texts), texts)

    def test_with_one_count_left_both_are_queued(self):
        texts = self.yielded(self.command_after(GUARD.MAX_SHELL_PAYLOAD_EXPANSIONS - 1))
        self.assertIn("echo MARK-BODY", texts)
        self.assertTrue(any(t.startswith("echo MARK-CMD") for t in texts), texts)

    def test_each_command_string_takes_one_count(self):
        value = '{"command":"echo MARK-ONE","command":"echo MARK-TWO"}'
        # Two counts left: both command strings; one left: only the first.
        for payloads, wanted in ((23, {"MARK-ONE", "MARK-TWO"}), (24, {"MARK-ONE"}), (25, set())):
            command = "; ".join(["bash -c 'true'"] * payloads + [run_command(value)])
            texts = self.yielded(command)
            found = {
                m for m in ("MARK-ONE", "MARK-TWO") if ("echo " + m) in texts
            }
            with self.subTest(payloads=payloads):
                self.assertEqual(wanted, found)

    def test_the_component_returns_the_command_string_and_the_body(self):
        # What statements() then queues: the body unconditionally, the command
        # string against the counter.
        (result,) = Spy(run_command(self.VALUE)).inspected()
        self.assertEqual(("echo MARK-CMD $(echo MARK-BODY)",), result.commands)
        self.assertEqual(("echo MARK-BODY",), result.bodies)


class TestWalk(unittest.TestCase):
    """AC-2, AC-5 (FR4, FR5, TM-2): what the walk collects."""

    def result(self, value):
        (result,) = Spy(run_command(value)).inspected()
        return result

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


class TestFlagReading(unittest.TestCase):
    """AC-3, AC-4 (FR1, FR2, FR6, D2): which statements are inspected."""

    def kinds(self, command):
        return Spy(command).kinds()

    def test_the_notion_pair_is_not_inspected(self):
        command = (
            "mcp-bridge run --mcp notion --tool notion-create-comment --args-json "
            "'{\"body\":\"x\"}'"
        )
        self.assertEqual([GUARD.ARGS_JSON_NOT_INSPECTED], self.kinds(command))

    def test_the_notion_pair_in_another_flag_order_is_not_inspected(self):
        command = (
            "mcp-bridge run --tool notion-create-comment --dry-run --args-json "
            "'{\"body\":\"x\"}' --mcp notion --format json"
        )
        self.assertEqual([GUARD.ARGS_JSON_NOT_INSPECTED], self.kinds(command))

    def test_other_forms_that_read_as_flags_are_inspected(self):
        value = "'{\"command\":\"ls\"}'"
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
                self.assertEqual([GUARD.ARGS_JSON_INSPECTED], self.kinds(command))

    def test_forms_outside_the_canonical_flag_sequence_are_not_inspected(self):
        value = "'{\"command\":\"ls\"}'"
        for label, command in (
            ("equals form", "mcp-bridge run --args-json=" + value),
            ("single dash", "mcp-bridge run -args-json " + value),
            ("quoted flag", "mcp-bridge run '--args-json' " + value),
            ("terminator", "mcp-bridge run --args-json " + value + " -- x"),
            ("positional", "mcp-bridge run --args-json " + value + " pos"),
            ("unknown flag", "mcp-bridge run --unknown x --args-json " + value),
            ("no value", "mcp-bridge run --args-json"),
            ("repeated args-json", "mcp-bridge run --args-json " + value + " --args-json " + value),
            ("no args-json", "mcp-bridge run --mcp other --tool t"),
            ("not run", "mcp-bridge list --args-json " + value),
            ("no subcommand", "mcp-bridge"),
        ):
            with self.subTest(label):
                self.assertEqual([GUARD.ARGS_JSON_NOT_INSPECTED], self.kinds(command))

    def test_a_non_static_value_word_is_not_inspected(self):
        for label, command in (
            ("substitution", "mcp-bridge run --args-json \"$(cat args.json)\""),
            ("variable", "mcp-bridge run --args-json \"$ARGS\""),
            ("unquoted glob", "mcp-bridge run --args-json {*}"),
            ("static value but dynamic server", "mcp-bridge run --mcp \"$S\" --args-json '{\"command\":\"ls\"}'"),
            ("static value but dynamic tool", "mcp-bridge run --tool $T --args-json '{\"command\":\"ls\"}'"),
        ):
            with self.subTest(label):
                self.assertEqual([GUARD.ARGS_JSON_NOT_INSPECTED], self.kinds(command))

    def test_the_command_word_that_is_text_of_another_command_is_not_inspected(self):
        command = "echo \"mcp-bridge run --args-json '{\\\"command\\\":\\\"ls\\\"}'\""
        spy = Spy(command)
        self.assertEqual([GUARD.ARGS_JSON_NOT_INSPECTED], spy.all_kinds)
        self.assertEqual([], spy.results)

    def test_value_forms_are_rebuilt_under_bash_quoting(self):
        escaped_double = '"{\\"command\\":\\"git branch -D example\\"}"'
        ansi_c = "$'{\"command\":\"git branch -D example\"}'"
        joined = "'{\"command\":'\"\"'\"git branch -D example\"}'"
        for label, word in (("double", escaped_double), ("ansi-c", ansi_c), ("joined", joined)):
            with self.subTest(label):
                spy = Spy("mcp-bridge run --args-json " + word)
                (result,) = spy.inspected()
                self.assertEqual(("git branch -D example",), result.commands)

    def test_candidate_residue_in_single_quotes_does_not_make_the_word_unreadable(self):
        # The raw `$(` sits in single quotes: Bash passes it on as text.
        command = run_command('{"command":"echo $(echo MARK)"}')
        (result,) = Spy(command).inspected()
        self.assertEqual(("echo $(echo MARK)",), result.commands)
        self.assertEqual(("echo MARK",), result.bodies)

    def test_a_real_substitution_in_the_value_word_makes_it_unreadable(self):
        command = "mcp-bridge run --args-json '{\"command\":\"ls\"}'\"$(echo x)\""
        self.assertEqual([GUARD.ARGS_JSON_NOT_INSPECTED], Spy(command).kinds())


class TestDocstring(unittest.TestCase):
    """AC-4 (FR8): the docstring of the component lists every out-of-scope
    form of IMPLEMENTATION.md O1 and O2 with the scope it gives them."""

    def setUp(self):
        self.doc = " ".join(inspect.getdoc(GUARD._mcp_bridge_args_json_chunks).split())

    def test_o1_and_o2_are_named(self):
        for label in ("O1", "O2"):
            with self.subTest(label):
                self.assertIn(label, self.doc)

    def test_o1_forms(self):
        for phrase in (
            "plain text, without a substitution",
            "other than the top-level `command`",
            "`input`",
            "`interact_with_process`",
            "`command` key below the top level",
            "Only the candidate search applies",
        ):
            with self.subTest(phrase):
                self.assertIn(phrase, self.doc)

    def test_o2_forms(self):
        for phrase in (
            "set by a substitution or a variable expansion",
            "a substitution Bash itself runs is still re-scanned",
            "`--mcp` or `--tool` value word is not static",
            "does not decode as JSON",
            "`--args-json` missing, repeated, or written in the `=` form",
            "do not read as the canonical flag sequence",
            "top level is not an object",
        ):
            with self.subTest(phrase):
                self.assertIn(phrase, self.doc)


if __name__ == "__main__":
    unittest.main()
