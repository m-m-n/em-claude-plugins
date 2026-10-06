"""Extglob parse-unit record of `em-workflow/hooks/destructive-guard.py`
(destructive-guard-heredoc-bypass-fixes task0005; FR4, NFR1-NFR4, TM-7).

An extended-glob parenthesis inside an array (`x=(@(a))`) is a pattern group
with `shopt -s extglob` and a syntax error without it, so the hook judges a
command that holds one under both readings, and settles it with an `ask` when
the parentheses sit in more than one parse unit (the option may be switched
in the middle of the command). This module proves that what the lexer finds
reaches its consumers only through the map `lex_shell()` returns, and that
the parse-unit count, the met determination and the verdict of a judgment do
not depend on the lexer cache or on which stage lexed a chunk first.

The hook has no package, so every test loads the module from its file path
(test/README.md) and drives it in-process: lex_shell() for the facts on a
map, run() -- fed a payload on a replaced stdin -- for a judgment. A hook
module loaded afresh has an empty lexer cache and no earlier judgment; a
module is never reset from the outside, only by what a judgment itself resets.
Standard library only.

Layout:

- TestMapFacts (AC-1): the extended-glob line starts and the met fact on the
  map, fresh, cached and after other texts were lexed in between.
- TestRepeatAndPrewarmedJudgments (AC-2): a repeat judgment, a judgment after
  every text of the payload was lexed beforehand, and a judgment after
  unrelated lexings give the verdict, met determination and unit count of a
  first judgment with an empty cache.
- TestCacheDisabled (AC-3): every case-table entry with the lexer cache off.
- TestVerdicts (AC-4): TS5, its differing-prefix variant and T2 AC-4.7.
- TestModuleContract (AC-6): standard library only.
"""

import ast
import collections
import contextlib
import importlib.util
import io
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "em-workflow", "hooks", "destructive-guard.py")
CASES_JSON = os.path.join(
    ROOT, "em-workflow", "hooks", "tests", "destructive-guard-cases.json"
)

with open(CASES_JSON, encoding="utf-8") as _f:
    CASES = json.load(_f)

# TS5: an outer and an inner eval both carrying the prefix `x=(@`, extglob
# switched between them (f34ee27bc8c323b1).
TS5 = "eval 'x=(@(a))\nshopt -s extglob\neval \"x=(@(b))\"'"
# Its variant whose inner eval carries a different prefix, `y=(@`.
TS5_VARIANT = "eval 'x=(@(a))\nshopt -s extglob\neval \"y=(@(b))\"'"
# T2 AC-4.7: one parse unit, allow.
T2_AC_4_7 = 'x=( @(foo|bar) ); cat <<"EOF"\nhello\nEOF'

EXTGLOB_OPENERS = ("@(", "!(", "+(", "*(", "?(")


def load_hook():
    """A hook module of its own: empty lexer cache, no judgment behind it."""
    spec = importlib.util.spec_from_file_location(
        "destructive_guard_extglob_units_under_test", HOOK
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Outcome = collections.namedtuple("Outcome", "verdict met units")


def judge(hook, command):
    """One judgment of COMMAND by the hook's own entry point, run(), fed the
    payload on stdin with the unattended downgrade off. Returns the verdict
    (`allow` / `ask` / `deny`, `(silent)` when the hook gave none), whether
    the judgment met an extended-glob parenthesis (the flag run() decides the
    second reading on) and the parse-unit count of each reading it judged."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    out = io.StringIO()
    with mock.patch.dict(os.environ):
        os.environ.pop("CLAUDE_BATCH", None)
        with mock.patch.object(sys, "stdin", io.StringIO(payload)):
            with contextlib.redirect_stdout(out):
                try:
                    hook.run()
                except SystemExit:
                    pass
                else:
                    raise AssertionError("run() returned without exiting")
    text = out.getvalue().strip()
    verdict = "(silent)"
    if text:
        verdict = json.loads(text)["hookSpecificOutput"]["permissionDecision"]
    return Outcome(verdict, hook._lex_extglob_met, tuple(hook._lex_ext_units))


def facts(lex_map):
    """What one lexing found about extended-glob parentheses, as the map
    carries it."""
    return (tuple(lex_map.ext_lines), lex_map.ext_met)


class NoCache(dict):
    """A lexer cache that keeps nothing: every lex_shell() call lexes afresh."""

    def get(self, key, default=None):
        return default

    def __setitem__(self, key, value):
        pass


def extglob_payloads():
    """TS5, its variant, T2 AC-4.7 and every case-table command that holds an
    extended-glob opener, without repeats."""
    commands = [TS5, TS5_VARIANT, T2_AC_4_7]
    commands += [c for _w, _l, c in CASES if any(o in c for o in EXTGLOB_OPENERS)]
    return list(dict.fromkeys(commands))


# Texts whose extended-glob facts are written out by hand: (text, line starts,
# met). The two readings agree on every one of them. TS5's chunks are the
# outer command, the text of its outer eval and the text of its inner eval.
HAND_WRITTEN_FACTS = [
    (TS5, (), False),
    ("x=(@(a))\nshopt -s extglob\neval \"x=(@(b))\"", (0,), True),
    ("x=(@(b))", (0,), True),
    (TS5_VARIANT, (), False),
    ("x=(@(a))\nshopt -s extglob\neval \"y=(@(b))\"", (0,), True),
    ("y=(@(b))", (0,), True),
    (T2_AC_4_7, (0,), True),
    ("x=(@(a))\ny=(a)\nz=(@(b))", (0, 15), True),
    ("echo hi\nx=(a@(b))", (8,), True),
    ("", (), False),
    ("echo hi", (), False),
    ("x=(a b); cat <<'A'\nbody\nA", (), False),
    ("x=(a (b)); cat <<'A'\nbody\nA", (), False),
    ("echo @(a|b)", (), False),
]

# Commands with no extended-glob parenthesis in an array that are judged after
# a command that has one.
PLAIN_COMMANDS = [
    "echo hi",
    "ls -la /tmp",
    "rm -rf /home/sakura/valuable",
    "x=(a b); cat <<'A'\nbody\nA",
]


class TestMapFacts(unittest.TestCase):
    """AC-1: the line starts and the met fact belong to the map."""

    def test_the_map_of_a_text_carries_the_facts_written_out_by_hand(self):
        hook = load_hook()
        for text, lines, met in HAND_WRITTEN_FACTS:
            for extglob in (False, True):
                with self.subTest(text=text, extglob=extglob):
                    lex_map = hook.lex_shell(text, "shell", True, extglob)
                    self.assertEqual(facts(lex_map), (lines, met))

    def test_a_cached_map_carries_the_facts_of_the_fresh_one(self):
        hook = load_hook()
        for text, lines, met in HAND_WRITTEN_FACTS:
            for extglob in (False, True):
                with self.subTest(text=text, extglob=extglob):
                    fresh = hook.lex_shell(text, "shell", True, extglob)
                    cached = hook.lex_shell(text, "shell", True, extglob)
                    self.assertEqual(facts(fresh), (lines, met))
                    self.assertEqual(facts(cached), facts(fresh))

    def test_other_texts_lexed_in_between_change_no_fact(self):
        # More distinct texts than the cache holds, so the text is lexed
        # afresh the second time, each of them with or without a parenthesis.
        hook = load_hook()
        others = [
            (text, extglob)
            for _w, _l, text in CASES
            for extglob in (False, True)
        ]
        self.assertGreater(len(others), 4 * hook._LEX_CACHE_LIMIT)
        for text, lines, met in HAND_WRITTEN_FACTS:
            for extglob in (False, True):
                with self.subTest(text=text, extglob=extglob):
                    first = hook.lex_shell(text, "shell", True, extglob)
                    for other, other_extglob in others[: 2 * hook._LEX_CACHE_LIMIT]:
                        try:
                            hook.lex_shell(other, "shell", True, other_extglob)
                        except hook.LexBudgetExceeded:
                            pass
                    again = hook.lex_shell(text, "shell", True, extglob)
                    self.assertEqual(facts(first), (lines, met))
                    self.assertEqual(facts(again), (lines, met))

    def test_every_case_table_command_has_the_same_facts_fresh_cached_and_interleaved(self):
        texts = [(c, e) for _w, _l, c in CASES for e in (False, True)]
        # The facts of a lexing that is always fresh (the cache keeps nothing).
        bare = load_hook()
        bare._LEX_CACHE = NoCache()
        wanted = {}
        for text, extglob in texts:
            try:
                wanted[(text, extglob)] = facts(bare.lex_shell(text, "shell", True, extglob))
            except bare.LexBudgetExceeded:
                wanted[(text, extglob)] = None
        self.assertTrue(any(met for _lines, met in filter(None, wanted.values())))
        hook = load_hook()
        mismatches = []
        # Forward (fresh), forward again straight away (cached), then in the
        # reverse order (the text was lexed among many others in between).
        for order in (texts, texts, texts[::-1]):
            for text, extglob in order:
                try:
                    got = facts(hook.lex_shell(text, "shell", True, extglob))
                except hook.LexBudgetExceeded:
                    got = None
                if got != wanted[(text, extglob)]:
                    mismatches.append((text, extglob, got, wanted[(text, extglob)]))
        self.assertEqual(mismatches, [])

    def test_a_text_without_an_extended_glob_parenthesis_has_empty_facts(self):
        hook = load_hook()
        for text, lines, met in HAND_WRITTEN_FACTS:
            if met:
                continue
            for extglob in (False, True):
                with self.subTest(text=text, extglob=extglob):
                    lex_map = hook.lex_shell(text, "shell", True, extglob)
                    self.assertEqual(tuple(lex_map.ext_lines), ())
                    self.assertIs(lex_map.ext_met, False)

    def test_a_cache_hit_raises_the_met_flag_of_the_judgment_that_reads_it(self):
        hook = load_hook()
        text = "x=(a@(b|c))"
        hook.lex_shell(text)
        self.assertTrue(hook._lex_extglob_met)
        hook._lex_extglob_met = False
        # The same key again: a cache hit, and the fact on the map is read.
        hook.lex_shell(text)
        self.assertTrue(hook._lex_extglob_met)


class TestRepeatAndPrewarmedJudgments(unittest.TestCase):
    """AC-2 (TM-7): the verdict, the met determination and the parse-unit
    count do not depend on the lexer cache or on earlier lexings."""

    @staticmethod
    def first_judgment(command):
        """A first judgment with an empty cache, with the lexings it made."""
        hook = load_hook()
        real = hook.lex_shell
        lexings = []

        def recording(text, mode="shell", bodies=True, extglob=None):
            reading = hook._lex_extglob if extglob is None else extglob
            lexings.append((text, mode, bodies, reading))
            return real(text, mode, bodies, extglob)

        hook.lex_shell = recording
        outcome = judge(hook, command)
        return outcome, list(dict.fromkeys(lexings))

    def test_the_payloads_are_there_to_check(self):
        payloads = extglob_payloads()
        self.assertEqual(payloads[:3], [TS5, TS5_VARIANT, T2_AC_4_7])
        self.assertGreaterEqual(len(payloads), 10)

    def test_a_second_judgment_in_one_process_matches_the_first(self):
        for command in extglob_payloads():
            with self.subTest(command=command):
                wanted, _lexings = self.first_judgment(command)
                hook = load_hook()
                self.assertEqual(judge(hook, command), wanted)
                self.assertEqual(judge(hook, command), wanted)
                self.assertEqual(judge(hook, command), wanted)

    def test_a_judgment_after_every_text_of_it_was_lexed_beforehand_matches_the_first(self):
        for command in extglob_payloads():
            with self.subTest(command=command):
                wanted, lexings = self.first_judgment(command)
                hook = load_hook()
                for text, mode, bodies, reading in lexings:
                    hook.lex_shell(text, mode, bodies, reading)
                self.assertEqual(judge(hook, command), wanted)

    def test_a_judgment_after_the_texts_were_lexed_in_the_other_order_matches_the_first(self):
        for command in extglob_payloads():
            with self.subTest(command=command):
                wanted, lexings = self.first_judgment(command)
                hook = load_hook()
                for text, mode, bodies, reading in reversed(lexings):
                    hook.lex_shell(text, mode, bodies, reading)
                self.assertEqual(judge(hook, command), wanted)

    def test_the_met_determination_is_the_judgments_own(self):
        # An earlier judgment and earlier lexings that met a parenthesis do
        # not make a later command, which has none, count as one that did.
        for command in PLAIN_COMMANDS:
            with self.subTest(command=command):
                wanted, _lexings = self.first_judgment(command)
                self.assertFalse(wanted.met)
                self.assertEqual(wanted.units, (0,))
                hook = load_hook()
                judge(hook, TS5)
                hook.lex_shell("x=(a@(b|c))")
                self.assertEqual(judge(hook, command), wanted)

    def test_the_counts_of_the_three_named_inputs(self):
        # TS5 and its variant hold a parenthesis in two parse units, T2 AC-4.7
        # in one: the two readings are judged, and only the two units ask.
        self.assertEqual(self.first_judgment(TS5)[0], Outcome("ask", True, (2, 2)))
        self.assertEqual(self.first_judgment(TS5_VARIANT)[0], Outcome("ask", True, (2, 2)))
        self.assertEqual(self.first_judgment(T2_AC_4_7)[0], Outcome("allow", True, (1, 1)))


class TestCacheDisabled(unittest.TestCase):
    """AC-3 (TM-7): the lexer cache is an optimization, not a part of the
    verdict."""

    def test_every_case_table_entry_yields_its_verdict_with_the_cache_off(self):
        hook = load_hook()
        hook._LEX_CACHE = NoCache()
        mismatches = []
        for want, label, command in CASES:
            got = judge(hook, command).verdict
            if got != want:
                mismatches.append((label, want, got))
        self.assertEqual(mismatches, [])


class TestVerdicts(unittest.TestCase):
    """AC-4 (FR4, NFR1): the verdicts the unit identity of task0003 gives."""

    def test_the_three_named_inputs_are_case_table_entries(self):
        table = {command: want for want, _label, command in CASES}
        self.assertEqual(table[TS5], "ask")
        self.assertEqual(table[TS5_VARIANT], "ask")
        self.assertEqual(table[T2_AC_4_7], "allow")

    def test_ts5_asks(self):
        self.assertEqual(judge(load_hook(), TS5).verdict, "ask")

    def test_ts5_with_a_differing_prefix_asks(self):
        self.assertEqual(judge(load_hook(), TS5_VARIANT).verdict, "ask")

    def test_t2_ac_4_7_allows(self):
        self.assertEqual(judge(load_hook(), T2_AC_4_7).verdict, "allow")


class TestModuleContract(unittest.TestCase):
    """AC-6 (NFR4): the hook and this module import only the standard library."""

    def test_hook_and_test_import_only_the_standard_library(self):
        allowed = set(sys.stdlib_module_names)
        for path in (HOOK, os.path.abspath(__file__)):
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                for name in names:
                    self.assertIn(name, allowed, msg="%s imports %s" % (path, name))


if __name__ == "__main__":
    unittest.main()
