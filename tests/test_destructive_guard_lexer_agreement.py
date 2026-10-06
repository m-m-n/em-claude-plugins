"""Agreement test for the unified lexer of `em-workflow/hooks/destructive-guard.py`
(destructive-guard-unified-lexer task0001 and rework task0002, FR10; D6).

The hook decides every quote / comment / expansion / substitution judgment in
one place, `lex_shell(text, mode)`. This module proves that every reader built
on that lexer agrees with it, and -- because layers that all read one lexer map
can share one misread and still agree -- anchors the lexer itself to
hand-written expectations (D6): every edge form below carries expected regions,
expected real heredoc operators where relevant, and an expected hook verdict,
all written out by hand as literals. Nothing here is computed by a shell.

The hook has no package, so the module is loaded from its file path
(test/README.md). Verdict, linearity and determinism checks run the hook
through its stdin JSON / stdout contract. Standard library only.

Layout:

- TestFixedExpectations: regions, real heredoc operators, single-quote
  candidates and the unopened openers of every fixed-expectation form.
- TestFixedVerdicts: the hook's verdict for every fixed form, every benign
  control and every attack form (AC-1, AC-2, AC-7 of the SPEC).
- TestStageAgreement: the stage agreement properties (a)-(f) over every
  cases.json command, every attack form, every benign control and every fixed
  form.
- TestPositionMap: the position-map contract, including a marker longer than
  the substitution it replaces.
- TestSubstitutionPolicies: the three substitution searches stay distinct.
- TestHeredocBodies: nothing written inside a real heredoc body opens
  anything for the command text after its delimiter line.
- TestHeredocDelimiterWords: the delimiter of `<<` / `<<-` is the whole word
  with its quotes removed; an unreadable word takes no body.
- TestUnclosedOpeners: unclosed openers in bulk, determinism, linearity.
- TestReworkLinearity: the two ~60KB inputs of rework round 1 (P10, P11), and
  the linear work of `((` / `$((` openers that close without an adjacent `))`.
- TestNonAdjacentCloseRereading: those openers (review round 2, finding
  29bbf9032dd762a0): the case-table allow cases, map equivalence with the
  whole-text-restart reading, hand-written maps of the nested, double-quoted
  and here-document-pending forms, the ~60KB input and the budget decision.
- TestModuleContract: the replaced readers are gone; standard library only.

Rework round 1 (task0002) adds the forms of IMPLEMENTATION.md P10 (reserved
words after closers and name-taking keywords), P11 (where a heredoc body
begins) and P12 (the word after a process substitution) to the fixed
expectations above: COMMAND_POSITION_FORMS, NON_ARITHMETIC_FORMS,
PROCESS_SUBSTITUTION_FORMS and HEREDOC_BODY_START_FORMS.
"""

import ast
import bisect
import hashlib
import importlib.util
import io
import json
import os
import random
import re
import shlex
import subprocess
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "em-workflow", "hooks", "destructive-guard.py")
CASES_JSON = os.path.join(
    ROOT, "em-workflow", "hooks", "tests", "destructive-guard-cases.json"
)

# Bound for one evaluation of the hook, the same as hooks.json's timeout.
GUARD_TIMEOUT_SECONDS = 10


def _load_hook():
    spec = importlib.util.spec_from_file_location("destructive_guard_under_test", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = _load_hook()

TAIL = "\nrm -rf /home/sakura/valuable\n2"

SUBSTITUTION_KINDS = frozenset(
    {"command-substitution", "backtick-substitution", "process-substitution"}
)
QUOTE_KINDS = frozenset({"single-quote", "double-quote", "ansi-c-quote", "locale-quote"})
OPAQUE_KINDS = QUOTE_KINDS | SUBSTITUTION_KINDS | frozenset(
    {
        "comment",
        "parameter-expansion",
        "arithmetic-expansion",
        "bracket-arithmetic",
        "arithmetic-command",
    }
)
# Kinds whose content shlex would read differently from bash: the masked view
# hides them from the tokenizer.
HIDDEN_KINDS = frozenset(
    {
        "ansi-c-quote",
        "parameter-expansion",
        "arithmetic-expansion",
        "bracket-arithmetic",
        "arithmetic-command",
        "comment",
    }
)


# ---------------------------------------------------------------------------
# Hand-written expectations (D6). A region is written as (kind, literal) or
# (kind, literal, n): the n-th (default first) occurrence of LITERAL in the
# command is the region's text. A heredoc is (delimiter, quoted, body).
# A candidate is (quote literal, candidate literal).
# ---------------------------------------------------------------------------

CONTEXT_FORMS = [
    ('echo "$\'x\'"', [("double-quote", '"$\'x\'"')], [], "allow"),
    ('echo $"a b"', [("locale-quote", '$"a b"')], [], "allow"),
    (
        "echo $$'x' $?'y'",
        [("single-quote", "'x'"), ("single-quote", "'y'")],
        [],
        "allow",
    ),
    (
        "echo $'a\\\\b\\'c'",
        [("ansi-c-quote", "$'a\\\\b\\'c'")],
        [],
        "allow",
    ),
    (
        "echo ${#x} ${x#pat} $#",
        [("parameter-expansion", "${#x}"), ("parameter-expansion", "${x#pat}")],
        [],
        "allow",
    ),
    (
        'echo ${x:-"}"}',
        [("parameter-expansion", '${x:-"}"}'), ("double-quote", '"}"')],
        [],
        "allow",
    ),
    (
        "echo ${x:-${y}}",
        [("parameter-expansion", "${x:-${y}}"), ("parameter-expansion", "${y}")],
        [],
        "allow",
    ),
    (
        "echo $((1+2)) $( (echo a) )",
        [("arithmetic-expansion", "$((1+2))"), ("command-substitution", "$( (echo a) )")],
        [],
        "allow",
    ),
    ("( (echo a) )", [], [], "allow"),
    ("cat a[1] <<EOF\nhi\nEOF", [], [("EOF", False, "hi\n")], "allow"),
    (
        "cat <<<'x'",
        [("here-string-operator", "<<<"), ("single-quote", "'x'")],
        [],
        "allow",
    ),
    (
        "echo $(cat <<EOF\nhi\nEOF\n)",
        [("command-substitution", "$(cat <<EOF\nhi\nEOF\n)")],
        [("EOF", False, "hi\n")],
        "allow",
    ),
    (
        "echo $'a' ${x} $((1<<2)) \"b\" # c",
        [
            ("ansi-c-quote", "$'a'"),
            ("parameter-expansion", "${x}"),
            ("arithmetic-expansion", "$((1<<2))"),
            ("double-quote", '"b"'),
            ("comment", "# c"),
        ],
        [],
        "allow",
    ),
    ('echo "a\nb"; ls', [("double-quote", '"a\nb"')], [], "allow"),
    ("echo ${x:-a\nb}; ls", [("parameter-expansion", "${x:-a\nb}")], [], "allow"),
    ("echo $'a\nb'; ls", [("ansi-c-quote", "$'a\nb'")], [], "allow"),
]

# Round 2 residuals (task0001): the command position after a closer `{` (the
# arithmetic-for header `))` followed by `{`, finding 453963d025537b11) and
# after `time --` / `time -p --` (finding 681fab61e1d9ff2c). Each pair is the
# finding's stable_id and the form; each form is followed by TAIL as a case.
ROUND2_COMMAND_POSITION_CASES = [
    ("453963d025537b11", "for ((i=0;i<1;i++)) { ((1<<2)); }"),
    ("453963d025537b11", "for ((;0;)){ ((1<<2)); }"),
    ("453963d025537b11", "if :; then for ((;0;)) { ((1<<2)); }; fi"),
    ("681fab61e1d9ff2c", "time -- ((1<<2))"),
    ("681fab61e1d9ff2c", "time -p -- ((1<<2))"),
    ("681fab61e1d9ff2c", "time -- ! ((1<<2))"),
]

# Arithmetic commands at every command position P3 lists. Each form is
# followed by TAIL; expected: one arithmetic-command region at the `((`, no
# real heredoc operator, verdict deny.
COMMAND_POSITION_FORMS = [
    "true; ((1<<2))",
    "true && ((1<<2))",
    "false || ((1<<2))",
    "true | ((1<<2))",
    "! ((1<<2))",
    "if true; then ((1<<2)); fi",
    "while false; do ((1<<2)); done",
    "if false; then :; else ((1<<2)); fi",
    "if false; then :; elif ((1<<2)); then :; fi",
    "{ ((1<<2)); }",
    "( ((1<<2)) )",
    "time ((1<<2))",
    "time -p ((1<<2))",
    "case x in x) ((1<<2));; esac",
    "f() ((1<<2))",
    "coproc ((1<<2))",
    # P10 (rework round 1, finding 42180fe3cd060309): a reserved word right
    # after a closer or a name-taking keyword, and the position after
    # `coproc NAME` / `function NAME [()]`.
    "if (true) then ((1<<2)); fi",
    "if ((1)) then ((1<<2)); fi",
    "if { true; } then ((1<<2)); fi",
    "if [[ 1 ]] then ((1<<2)); fi",
    "until (true) do ((1<<2)); done",
    "for x do ((1<<2)); done",
    "function f() ((1<<2))",
    "coproc foo ((1<<2))",
    "select x do ((1<<2)); done",
    "function f ((1<<2))",
    "if :; then if :; then :; fi else ((1<<2)); fi",
    "if :; then while false; do :; done else ((1<<2)); fi",
    "if :; then case x in x) :;; esac else ((1<<2)); fi",
    # Round 2 residuals (task0001): the six forms of
    # ROUND2_COMMAND_POSITION_CASES.
    *[form for _finding, form in ROUND2_COMMAND_POSITION_CASES],
]

# Command-position forms that hold one more arithmetic-command region than the
# `((1<<2))` every form is about: the form -> the extra regions, written out.
COMMAND_POSITION_EXTRA_REGIONS = {
    "if ((1)) then ((1<<2)); fi": [("arithmetic-command", "((1))")],
    "for ((i=0;i<1;i++)) { ((1<<2)); }": [("arithmetic-command", "((i=0;i<1;i++))")],
    "for ((;0;)){ ((1<<2)); }": [("arithmetic-command", "((;0;))")],
    "if :; then for ((;0;)) { ((1<<2)); }; fi": [("arithmetic-command", "((;0;))")],
}

# After `time --` (task0001, FR2) no word is a `time` option any more: a `-p`
# or `--` there is the command word of the timed command, so the `((` after it
# is not at a command position and no arithmetic-command region is read. bash
# rejects both lines as a syntax error, so only the lexical reading is pinned.
TIME_OPTION_END_FORMS = [
    "time -- -p ((1<<2))",
    "time -- -- ((1<<2))",
]

# `((` that is not arithmetic: no arithmetic-command region. The verdict is
# the one the unchanged hook gave when this test was written; this feature
# must not change it.
NON_ARITHMETIC_FORMS = [
    ('echo "((1<<2))"', [("double-quote", '"((1<<2))"')], "allow"),
    ("echo a ((b))", [], "allow"),
    ("cat < ((x))", [], "allow"),
    # P10 negatives: a reserved word at an argument position, `]]` as an
    # argument and a word after a substitution's `)` are none of them a
    # reserved word that opens a command position. The verdicts were
    # recorded from the hook at the base of rework task0002.
    ("echo then ((b))", [], "allow"),
    ("echo ]] then ((b))", [], "allow"),
    ("echo $(true) then ((b))", [("command-substitution", "$(true)")], "allow"),
    ("echo function f ((b))", [], "allow"),
]

PROCESS_SUBSTITUTION_FORMS = [
    (
        "cat <((rm -rf /home/sakura/valuable))",
        [("process-substitution", "<((rm -rf /home/sakura/valuable))")],
        "deny",
    ),
    (
        "cat <(rm -rf /home/sakura/valuable)",
        [("process-substitution", "<(rm -rf /home/sakura/valuable)")],
        "deny",
    ),
    (
        "cat <(((1<<2)))",
        [("process-substitution", "<(((1<<2)))"), ("arithmetic-command", "((1<<2))")],
        "allow",
    ),
    (
        "cat <(((1<<2)))" + TAIL,
        [("process-substitution", "<(((1<<2)))"), ("arithmetic-command", "((1<<2))")],
        "deny",
    ),
    # P12 (rework round 1, finding acf9e8aa8bb287ea): the word goes on after
    # the closing `)`, so a `#` right after it is no comment; a `#` after a
    # blank still is.
    (
        "cat <(true)#; rm -rf /home/sakura/valuable",
        [("process-substitution", "<(true)")],
        "deny",
    ),
    (
        "cat >(true)#; rm -rf /home/sakura/valuable",
        [("process-substitution", ">(true)")],
        "deny",
    ),
    ("echo <(true)#x", [("process-substitution", "<(true)")], "allow"),
    (
        "cat <(true) #; rm -rf /home/sakura/valuable",
        [
            ("process-substitution", "<(true)"),
            ("comment", "#; rm -rf /home/sakura/valuable"),
        ],
        "allow",
    ),
]

# P11 (rework round 1, finding 6ad3de37b64392ec): where a heredoc body begins.
# (command, expected regions, operator literal, delimiter, delimiter quoted,
# body, verdict). Every form has exactly one real heredoc operator, and the
# delimiter line is the last line of the command, holding the delimiter alone.
HEREDOC_BODY_START_FORMS = [
    (
        'cat <<EOF; echo "\n"; rm -rf /home/sakura/valuable\nEOF',
        [("double-quote", '"\n"')],
        "<<EOF",
        "EOF",
        False,
        "",
        "deny",
    ),
    (
        "cat <<EOF; echo '\n'; rm -rf /home/sakura/valuable\nEOF",
        [("single-quote", "'\n'")],
        "<<EOF",
        "EOF",
        False,
        "",
        "deny",
    ),
    (
        "cat <<EOF; echo $(\n); rm -rf /home/sakura/valuable\nEOF",
        [("command-substitution", "$(\n)")],
        "<<EOF",
        "EOF",
        False,
        "",
        "deny",
    ),
    (
        'cat <<EOF; echo "\n"; git reset --hard HEAD\nEOF',
        [("double-quote", '"\n"')],
        "<<EOF",
        "EOF",
        False,
        "",
        "deny",
    ),
    (
        "cat <<EOF \\\n; rm -rf /home/sakura/valuable\nEOF",
        [],
        "<<EOF",
        "EOF",
        False,
        "",
        "deny",
    ),
    (
        'cat <<\'EOF\'; echo "a\nb"\ngit reset --hard HEAD\nEOF',
        [("double-quote", '"a\nb"')],
        "<<'EOF'",
        "EOF",
        True,
        "git reset --hard HEAD\n",
        "allow",
    ),
]

# Small copies of the two ~60KB inputs of TestReworkLinearity: the repeated
# units followed by the destructive statement. They join the stage agreement
# loop at this size (the 60KB originals would blow its runtime budget).
REWORK_REPEATED_FORMS = [
    "if (true) then ((1<<2)); fi\n" * 3 + "rm -rf /home/sakura/valuable",
    'cat <<EOF; echo "\n"; :\nEOF\n' * 3 + "rm -rf /home/sakura/valuable",
]

# Each form is followed by TAIL: an arithmetic-expansion region and no real
# heredoc operator; verdict deny.
EXPANSION_POSITION_FORMS = [
    (
        'echo "$((1<<2))"',
        [("double-quote", '"$((1<<2))"'), ("arithmetic-expansion", "$((1<<2))")],
    ),
    ("cat <$((1<<2))", [("arithmetic-expansion", "$((1<<2))")]),
    (
        "echo ${x:-$((1<<2))}",
        [
            ("parameter-expansion", "${x:-$((1<<2))}"),
            ("arithmetic-expansion", "$((1<<2))"),
        ],
    ),
]

# (command, the opener that is settled as not opened). Expected: no region,
# the re-read tail starting at the opener, no comment and no real heredoc
# operator anywhere; verdict deny.
UNCLOSED_OPENER_FORMS = [
    ("echo ${x\nrm -rf /home/sakura/valuable", "${"),
    ("echo $((1\nrm -rf /home/sakura/valuable", "$(("),
    ("echo $[1\nrm -rf /home/sakura/valuable", "$["),
    ("((x\nrm -rf /home/sakura/valuable", "(("),
    ("echo $'x\nrm -rf /home/sakura/valuable", "$'"),
    ("echo ${x # ; rm -rf /home/sakura/valuable", "${"),
    ("echo $((1 # ; rm -rf /home/sakura/valuable", "$(("),
    ("echo ${x <<EOF\nrm -rf /home/sakura/valuable\nEOF", "${"),
    ("echo $[1 <<EOF\nrm -rf /home/sakura/valuable\nEOF", "$["),
]

# (command, quote literal, candidate literals, enclosing literal or None).
# The verdict is the unchanged hook's (allow).
CANDIDATE_FORMS = [
    ("echo '$(a b)'", "'$(a b)'", ["$(a b)"], None),
    ("echo '$(a (b) c'", "'$(a (b) c'", ["$(a (b)"], None),
    ("echo '$(a b'", "'$(a b'", [], None),
    ("echo '`x`'", "'`x`'", ["`x`"], None),
    ("echo '`x'", "'`x'", [], None),
    ("echo $'$(a)'", "$'$(a)'", ["$(a)"], None),
    ("echo $(echo '$(a)')", "'$(a)'", ["$(a)"], "$(echo '$(a)')"),
]

BENIGN_CONTROLS = [
    "rm -rf /tmp/safe$'\\t'",
    'echo "${x:-a(b}"; cat <<\'EOF\'\ngit reset --hard HEAD\nEOF',
    "echo $((1<<2)); cat <<'EOF'\nrm -rf /tmp/zz\nEOF",
    "for ((i=0; i<3; i++)); do echo $i; done",
    'echo "$\'x\'"',
    "cat <(((1<<2)))",
]

# SPEC AC-1 forms 1-11 and AC-7 forms 1-5 (deny).
ATTACK_FORMS = [
    "cat $'\\'' ; bash -s \\' <<EOF\ngit reset --hard HEAD\nEOF",
    "echo $'\\'' ; rm -rf /home/sakura/valuable \\'",
    "echo $'\\'' ' #' ; rm -rf /home/sakura/valuable\necho \\'",
    "echo ${x/<<EOF/}\nrm -rf /home/sakura/valuable\nEOF",
    "echo ${x:-<<EOF}\nrm -rf /home/sakura/valuable\nEOF",
    "x=${y/<<EOF/}; ls\ngit reset --hard HEAD~3\nEOF",
    "echo $((1<<2))\nrm -rf /home/sakura/valuable\n2",
    "((x=1<<2))\nrm -rf /home/sakura/valuable\n2",
    "echo $[1<<2]\nrm -rf /home/sakura/valuable\n2",
    "if ((1<<2)); then :; fi\nrm -rf /home/sakura/valuable\n2",
    "echo $[a[1]<<2]\nrm -rf /home/sakura/valuable\n2",
    "for ((i=0; i<3; i++)); do rm -rf /home/sakura/valuable; done",
    "echo $(( $(rm -rf /home/sakura/valuable) + 1 ))",
    "echo ${x:-$(rm -rf /home/sakura/valuable)}",
    'echo "$\'" ; rm -rf /home/sakura/valuable',
    "echo ${x\nrm -rf /home/sakura/valuable",
]
ATTACK_ALLOW_FORM = "echo $((1<<2)); cat <<'EOF'\nrm -rf /tmp/zz\nEOF"


def span_of(text, literal, nth=0):
    """(start, end) of the NTH occurrence of LITERAL in TEXT."""
    start = -1
    for _ in range(nth + 1):
        start = text.index(literal, start + 1)
    return start, start + len(literal)


def expected_regions(text, items):
    out = []
    for item in items:
        kind, literal = item[0], item[1]
        nth = item[2] if len(item) > 2 else 0
        start, end = span_of(text, literal, nth)
        out.append((kind, start, end))
    return sorted(out)


def actual_regions(lexmap):
    return sorted((r.kind, r.start, r.end) for r in lexmap.regions)


_verdict_cache = {}


def hook_verdict(command, batch=False):
    """The decision the hook gives COMMAND, run through its stdin JSON /
    stdout contract. Returns (decision, reason)."""
    key = (command, batch)
    if key in _verdict_cache:
        return _verdict_cache[key]
    env = dict(os.environ)
    env.pop("CLAUDE_BATCH", None)
    if batch:
        env["CLAUDE_BATCH"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
            capture_output=True,
            text=True,
            env=env,
            timeout=GUARD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        result = ("(timeout)", "")
    else:
        if proc.returncode != 0:
            result = ("(exit %d)" % proc.returncode, proc.stderr.strip())
        elif not proc.stdout.strip():
            result = ("(silent)", "")
        else:
            out = json.loads(proc.stdout)["hookSpecificOutput"]
            result = (out["permissionDecision"], out["permissionDecisionReason"])
    _verdict_cache[key] = result
    return result


def case_commands():
    with open(CASES_JSON, encoding="utf-8") as f:
        return [(want, label, cmd) for want, label, cmd in json.load(f)]


def heredoc_body(text, op):
    return text[op.body_start : op.body_end] if op.body_start is not None else None


# ---------------------------------------------------------------------------
# Fixed expectations: the lexer's own reading (D6).
# ---------------------------------------------------------------------------


class TestFixedExpectations(unittest.TestCase):
    def check_regions(self, text, items, mode="shell"):
        lexmap = H.lex_shell(text, mode)
        self.assertEqual(
            actual_regions(lexmap), expected_regions(text, items), msg=repr(text)
        )
        return lexmap

    def check_heredocs(self, text, lexmap, expected):
        got = [(op.delimiter, op.quoted, heredoc_body(text, op)) for op in lexmap.heredocs]
        self.assertEqual(got, expected, msg=repr(text))

    def test_context_forms(self):
        for text, regions, heredocs, _verdict in CONTEXT_FORMS:
            with self.subTest(text=text):
                lexmap = self.check_regions(text, regions)
                self.check_heredocs(text, lexmap, heredocs)
                self.assertIsNone(lexmap.tail_start)
                self.assertEqual(list(lexmap.unopened), [])

    def test_command_position_arithmetic(self):
        for form in COMMAND_POSITION_FORMS:
            text = form + TAIL
            with self.subTest(text=text):
                expected = [("arithmetic-command", "((1<<2))")]
                expected += COMMAND_POSITION_EXTRA_REGIONS.get(form, [])
                lexmap = self.check_regions(text, expected)
                self.assertEqual(list(lexmap.heredocs), [])
                self.assertIsNone(lexmap.tail_start)

    def test_no_time_option_follows_a_double_dash(self):
        for text in TIME_OPTION_END_FORMS:
            with self.subTest(text=text):
                lexmap = self.check_regions(text, [])
                self.assertNotIn("arithmetic-command", [r.kind for r in lexmap.regions])
                self.assertIsNone(lexmap.tail_start)

    def test_heredoc_body_start_forms(self):
        # AC-3 (P11): one real heredoc operator, at the `<<`; its body begins
        # after the newline that ends the line on which the region opened
        # after the operator closes; the delimiter line is the last line.
        for text, regions, op_literal, delimiter, quoted, body, _verdict in (
            HEREDOC_BODY_START_FORMS
        ):
            with self.subTest(text=text):
                lexmap = self.check_regions(text, regions)
                self.assertEqual(len(lexmap.heredocs), 1)
                op = lexmap.heredocs[0]
                self.assertEqual((op.start, op.end), span_of(text, op_literal))
                self.assertEqual((op.delimiter, op.quoted), (delimiter, quoted))
                self.assertEqual(heredoc_body(text, op), body)
                delimiter_line = len(text) - len(delimiter)
                self.assertEqual(text[delimiter_line - 1], "\n")
                self.assertEqual(op.body_end, delimiter_line)
                self.assertEqual(op.body_start, delimiter_line - len(body))
                self.assertEqual(op.close_end, len(text))
                self.assertEqual(text[op.body_end : op.close_end], delimiter)
                self.assertIsNone(lexmap.tail_start)

    def test_a_region_enclosing_the_operator_defers_no_body(self):
        # P11: a command or process substitution that holds the operator
        # defers nothing, whether it is still open at the newline after the
        # operator or closed before it: the body is the line after that
        # newline. This is the pre-rework handling of the shape; rework
        # round 1 must not change it.
        for text in (
            "echo $(cat <<EOF\nhi\nEOF\n)",
            "echo $(cat <<EOF); echo x\nhi\nEOF",
            "cat <(cat <<EOF\nhi\nEOF\n)",
            "cat <(cat <<EOF); echo x\nhi\nEOF",
        ):
            with self.subTest(text=text):
                lexmap = H.lex_shell(text)
                self.assertEqual(len(lexmap.heredocs), 1)
                op = lexmap.heredocs[0]
                self.assertEqual(text[op.start : op.end], "<<EOF")
                self.assertEqual(heredoc_body(text, op), "hi\n")

    def test_a_backslash_newline_is_no_body_start(self):
        # P11: the continuation line after `\` + newline still belongs to the
        # operator's command line; the body begins after the line that ends it.
        text = "cat <<EOF \\\nbody-or-command\nEOF\nrm -rf /home/sakura/valuable"
        lexmap = H.lex_shell(text)
        self.assertEqual(len(lexmap.heredocs), 1)
        op = lexmap.heredocs[0]
        self.assertEqual(heredoc_body(text, op), "")
        self.assertEqual(text[op.body_end : op.close_end], "EOF\n")

    def test_arithmetic_for_header(self):
        text = "for ((i=0; i<3; i++)); do echo $i; done"
        self.check_regions(text, [("arithmetic-command", "((i=0; i<3; i++))")])

    def test_double_paren_is_not_arithmetic_elsewhere(self):
        for text, regions, _verdict in NON_ARITHMETIC_FORMS:
            with self.subTest(text=text):
                lexmap = self.check_regions(text, regions)
                self.assertNotIn("arithmetic-command", [r.kind for r in lexmap.regions])

    def test_process_substitution_forms(self):
        for text, regions, _verdict in PROCESS_SUBSTITUTION_FORMS:
            with self.subTest(text=text):
                lexmap = self.check_regions(text, regions)
                self.assertEqual(list(lexmap.heredocs), [])

    def test_expansion_position_forms(self):
        for form, regions in EXPANSION_POSITION_FORMS:
            text = form + TAIL
            with self.subTest(text=text):
                lexmap = self.check_regions(text, regions)
                self.assertEqual(list(lexmap.heredocs), [])

    def test_unclosed_opener_forms(self):
        for text, opener in UNCLOSED_OPENER_FORMS:
            with self.subTest(text=text):
                start = text.index(opener)
                lexmap = H.lex_shell(text)
                self.assertEqual(actual_regions(lexmap), [], msg=repr(text))
                self.assertEqual(list(lexmap.unopened), [start])
                self.assertEqual(lexmap.tail_start, start)
                self.assertEqual(list(lexmap.heredocs), [])
                self.assertNotIn("comment", [r.kind for r in lexmap.regions])

    def test_single_quote_candidates(self):
        for text, quote, candidates, enclosing in CANDIDATE_FORMS:
            with self.subTest(text=text):
                lexmap = H.lex_shell(text)
                q_start, q_end = span_of(text, quote)
                quotes = [
                    i
                    for i, r in enumerate(lexmap.regions)
                    if r.kind in ("single-quote", "ansi-c-quote")
                    and (r.start, r.end) == (q_start, q_end)
                ]
                self.assertEqual(len(quotes), 1, msg=repr(text))
                got = [
                    text[c.start : c.end] for c in lexmap.candidates if c.quote == quotes[0]
                ]
                self.assertEqual(got, candidates)
                for c in lexmap.candidates:
                    self.assertTrue(q_start < c.start and c.end <= q_end)
                    if enclosing is None:
                        self.assertIsNone(c.enclosing)
                    else:
                        outer = lexmap.regions[c.enclosing]
                        self.assertEqual(
                            (outer.kind, text[outer.start : outer.end]),
                            ("command-substitution", enclosing),
                        )

    def test_nesting_is_reported_with_parents(self):
        text = 'echo ${x:-"}"}'
        lexmap = H.lex_shell(text)
        kinds = {(r.kind): r for r in lexmap.regions}
        outer = lexmap.regions.index(kinds["parameter-expansion"])
        self.assertIsNone(kinds["parameter-expansion"].parent)
        self.assertEqual(kinds["double-quote"].parent, outer)

    def test_regions_are_ordered_by_start(self):
        text = "echo ${x:-$(echo \"a $((1+2))\")} $'z' # c"
        lexmap = H.lex_shell(text)
        starts = [r.start for r in lexmap.regions]
        self.assertEqual(starts, sorted(starts))
        for i, r in enumerate(lexmap.regions):
            if r.parent is not None:
                p = lexmap.regions[r.parent]
                self.assertLess(r.parent, i)
                self.assertTrue(p.start <= r.start and r.end <= p.end)

    def test_special_parameters_are_consumed_as_a_unit(self):
        # `$$'` is `$$` followed by an ordinary single quote; the `#` of `$#`,
        # `${#x}` and `${x#pat}` is never a comment.
        for text in ("echo $$'x'", "echo $?'x'", "echo $# $$ $! $- $@ $* $0 $9"):
            with self.subTest(text=text):
                lexmap = H.lex_shell(text)
                self.assertNotIn("ansi-c-quote", [r.kind for r in lexmap.regions])
                self.assertNotIn("comment", [r.kind for r in lexmap.regions])

    def test_backslash_escaped_dollar_opens_nothing(self):
        for text in ("echo \\$'x' ; ls", "echo \\${x ; ls", "echo \\$((1 ; ls"):
            with self.subTest(text=text):
                lexmap = H.lex_shell(text)
                self.assertEqual(actual_regions(lexmap), [] if "'x'" not in text else [("single-quote", text.index("'x'"), text.index("'x'") + 3)])
                self.assertIsNone(lexmap.tail_start)

    def test_arithmetic_read_as_two_parentheses_when_close_is_not_adjacent(self):
        # `((a) | cat)` has a matching close that is not an adjacent `))`: two
        # parentheses, no arithmetic region and no re-read tail.
        for text in ("((echo a) | cat)", "echo $((echo a) | cat)"):
            with self.subTest(text=text):
                lexmap = H.lex_shell(text)
                self.assertNotIn(
                    "arithmetic-command", [r.kind for r in lexmap.regions]
                )
                self.assertNotIn(
                    "arithmetic-expansion", [r.kind for r in lexmap.regions]
                )
                self.assertIsNone(lexmap.tail_start)
        lexmap = H.lex_shell("echo $((echo a) | cat)")
        self.assertEqual(
            [r.kind for r in lexmap.regions], ["command-substitution"]
        )

    def test_case_pattern_close_does_not_end_a_substitution(self):
        text = "echo $(case x in a) echo 1;; b) echo 2;; esac; echo done)"
        lexmap = H.lex_shell(text)
        self.assertEqual(
            actual_regions(lexmap), expected_regions(text, [("command-substitution", text[5:])])
        )

    def test_comment_ends_before_its_newline(self):
        text = "echo a # c $(x)\necho b"
        lexmap = H.lex_shell(text)
        self.assertEqual(
            actual_regions(lexmap), expected_regions(text, [("comment", "# c $(x)")])
        )

    def test_hash_inside_a_word_is_no_comment(self):
        for text in ("echo a#b", "echo $(x)#c", "echo 'a'#b"):
            with self.subTest(text=text):
                self.assertNotIn("comment", [r.kind for r in H.lex_shell(text).regions])

    def test_hash_after_group_close_is_a_comment(self):
        text = "(echo a)#c"
        self.assertIn("comment", [r.kind for r in H.lex_shell(text).regions])

    def test_heredoc_body_mode_literal_top_level(self):
        text = "echo 'a' # $(b) \"c\" $((1<<2)) <(x)"
        lexmap = H.lex_shell(text, "heredoc-body")
        self.assertEqual(
            actual_regions(lexmap),
            expected_regions(
                text,
                [
                    ("command-substitution", "$(b)"),
                    ("arithmetic-expansion", "$((1<<2))"),
                ],
            ),
        )

    def test_real_heredoc_operator_positions_and_bodies(self):
        text = "cat <<EOF <<-'X'\none\nEOF\ntwo\nX\nrm -rf /tmp/zz"
        lexmap = H.lex_shell(text)
        got = [
            (op.delimiter, op.quoted, text[op.start : op.end], heredoc_body(text, op))
            for op in lexmap.heredocs
        ]
        self.assertEqual(
            got,
            [
                ("EOF", False, "<<EOF", "one\n"),
                ("X", True, "<<-'X'", "two\n"),
            ],
        )

    def test_heredoc_whose_delimiter_never_appears_consumes_nothing(self):
        text = "cat <<EOF\nrm -rf /tmp/zz\nno delimiter"
        lexmap = H.lex_shell(text)
        self.assertEqual(len(lexmap.heredocs), 1)
        self.assertIsNone(lexmap.heredocs[0].body_start)
        stripped, records, _omap = H._strip_heredocs_mapped(text)
        self.assertEqual(stripped, text)
        self.assertEqual(records, [])

    def test_here_string_is_never_a_heredoc_operator(self):
        text = "cat <<<EOF\nrm -rf /tmp/zz\nEOF"
        lexmap = H.lex_shell(text)
        self.assertEqual(list(lexmap.heredocs), [])
        self.assertEqual([r.kind for r in lexmap.regions], ["here-string-operator"])

    def test_same_text_gives_the_same_map(self):
        text = "echo ${x # ; $'a' $((1<<2)) <(y)\ncat <<EOF\nhi\nEOF\n$(z"
        first = H.lex_shell(text)
        # A second, independent lexing: the memo the hook keeps must not be
        # what makes the two maps equal.
        H._LEX_CACHE.clear()
        second = H.lex_shell(text)
        self.assertIsNot(first, second)
        self.assertEqual(first.as_tuple(), second.as_tuple())


# ---------------------------------------------------------------------------
# Verdicts (SPEC AC-1, AC-2, AC-7; the benign controls; the fixed forms).
# ---------------------------------------------------------------------------


class TestFixedVerdicts(unittest.TestCase):
    def check(self, command, want):
        got, reason = hook_verdict(command)
        self.assertEqual(got, want, msg="%r -> %s %s" % (command, got, reason))

    def test_context_forms(self):
        for text, _regions, _heredocs, verdict in CONTEXT_FORMS:
            with self.subTest(text=text):
                self.check(text, verdict)

    def test_command_position_forms_are_denied(self):
        for form in COMMAND_POSITION_FORMS:
            with self.subTest(form=form):
                self.check(form + TAIL, "deny")

    def test_round2_command_position_forms_are_denied_in_both_modes(self):
        # task0001 (FR1, FR2): the verdict is deny without and with
        # CLAUDE_BATCH, so an unattended run is never let through either.
        for _finding, form in ROUND2_COMMAND_POSITION_CASES:
            text = form + TAIL
            for batch in (False, True):
                with self.subTest(form=form, batch=batch):
                    got, reason = hook_verdict(text, batch=batch)
                    self.assertEqual(
                        got, "deny", msg="%r batch=%s -> %s %s" % (text, batch, got, reason)
                    )

    def test_non_arithmetic_forms_keep_the_unchanged_verdict(self):
        for text, _regions, verdict in NON_ARITHMETIC_FORMS:
            with self.subTest(text=text):
                self.check(text, verdict)

    def test_process_substitution_forms(self):
        for text, _regions, verdict in PROCESS_SUBSTITUTION_FORMS:
            with self.subTest(text=text):
                self.check(text, verdict)

    def test_expansion_position_forms_are_denied(self):
        for form, _regions in EXPANSION_POSITION_FORMS:
            with self.subTest(form=form):
                self.check(form + TAIL, "deny")

    def test_heredoc_body_start_forms(self):
        for text, *_middle, verdict in HEREDOC_BODY_START_FORMS:
            with self.subTest(text=text):
                self.check(text, verdict)

    def test_repeated_rework_forms_are_denied(self):
        for text in REWORK_REPEATED_FORMS:
            with self.subTest(text=text[:60]):
                self.check(text, "deny")

    def test_unclosed_opener_forms_are_denied(self):
        for text, _opener in UNCLOSED_OPENER_FORMS:
            with self.subTest(text=text):
                self.check(text, "deny")

    def test_candidate_forms_keep_the_unchanged_verdict(self):
        for text, _quote, _candidates, _enclosing in CANDIDATE_FORMS:
            with self.subTest(text=text):
                self.check(text, "allow")

    def test_benign_controls_are_allowed(self):
        for text in BENIGN_CONTROLS:
            with self.subTest(text=text):
                self.check(text, "allow")

    def test_attack_forms_are_denied(self):
        for text in ATTACK_FORMS:
            with self.subTest(text=text):
                self.check(text, "deny")
        self.check(ATTACK_ALLOW_FORM, "allow")

    def test_attack_forms_are_in_the_cases_file(self):
        cases = {cmd: want for want, _label, cmd in case_commands()}
        for text in ATTACK_FORMS:
            self.assertEqual(cases.get(text), "deny", msg=repr(text))
        self.assertEqual(cases.get(ATTACK_ALLOW_FORM), "allow")

    def test_same_command_gives_an_identical_decision(self):
        for text in ATTACK_FORMS[:4] + [ATTACK_ALLOW_FORM]:
            with self.subTest(text=text):
                _verdict_cache.pop((text, False), None)
                first = hook_verdict(text)
                _verdict_cache.pop((text, False), None)
                second = hook_verdict(text)
                self.assertEqual(first, second)


# ---------------------------------------------------------------------------
# Stage agreement properties (a)-(f).
# ---------------------------------------------------------------------------


def _removed_before(segments, pos):
    """Characters removed from the old text before POS, collapsing a position
    inside a replaced segment to that segment's start."""
    shift = 0
    for seg in segments:
        kind, old_start, old_end, new_start, new_end, _ref = seg
        if kind != "replace":
            continue
        if old_end <= pos:
            shift += (old_end - old_start) - (new_end - new_start)
        elif old_start < pos:
            shift += pos - old_start
            break
        else:
            break
    return shift


def to_new_position(posmap, pos):
    """POS of the old text as a position of the new text; a position inside a
    replaced segment collapses to the segment's new start."""
    new = pos - _removed_before(posmap.segments, pos)
    for kind, old_start, old_end, new_start, new_end, _ref in posmap.segments:
        if kind == "replace" and old_start <= pos < old_end:
            return new_start
    return new


class Analysis:
    """One command run through the hook's own per-chunk pipeline, the way
    statements() runs the top-level chunk."""

    def __init__(self, command):
        self.command = command
        self.stripped, self.records, self.omap = H._strip_heredocs_mapped(command)
        self.lex_o = H.lex_shell(command, "shell")
        self.lex_s = H.lex_shell(self.stripped, "shell", False)
        self.scan = H.scan_structure(self.stripped, "shell")
        self.broad = H.scan_structure(self.stripped, "shell", honor_single_quotes=False)
        self.top_spans = H._top_level_spans(self.broad[0], self.broad[1])
        self.marked = H._mark_substitutions(self.stripped, self.top_spans, 0)

    def s_pos(self, o_pos):
        return to_new_position(self.omap, o_pos)

    def region_closed(self, region):
        return region.closed or region.kind not in SUBSTITUTION_KINDS

    def layout_regions(self):
        """The regions the layout layer cannot see into: every region of the
        stripped text except here-string operators and unterminated
        substitutions (their text is read raw). A process substitution
        counts by its body only: marking replaces the body and leaves `<(`
        and `)` in the text as operator tokens (D5)."""
        out = []
        for r in self.lex_s.regions:
            if r.kind == "here-string-operator" or not self.region_closed(r):
                continue
            if r.kind == "process-substitution":
                r = r._replace(start=r.start + 2, end=r.end - 1)
            out.append(r)
        return out

    def quote_ranges(self):
        """Where a quote region or a quote delimiter sits in the stripped
        text: every quote region not nested in a marked substitution, and the
        quote characters of a quoted here-document delimiter."""
        ranges = [
            (r.start, r.end)
            for i, r in enumerate(self.lex_s.regions)
            if r.kind in QUOTE_KINDS and not self.has_closed_substitution_ancestor(i)
        ]
        for op in self.lex_s.heredocs:
            if op.quoted:
                # The whole delimiter word, from after the operator and its
                # blanks: it may hold quote characters anywhere (`E"X"`,
                # `E\X`), and its value is shorter than its text.
                word_start = re.compile(r"<<-?[ \t]*").match(self.stripped, op.start).end()
                ranges.append((word_start, op.end))
        return ranges

    def in_region(self, regions, pos):
        return any(r.start <= pos < r.end for r in regions)

    def has_closed_substitution_ancestor(self, index):
        parent = self.lex_s.regions[index].parent
        while parent is not None:
            r = self.lex_s.regions[parent]
            if r.kind in SUBSTITUTION_KINDS and r.closed:
                return True
            parent = r.parent
        return False


def all_commands():
    commands = []
    seen = set()

    def add(cmd):
        if cmd not in seen:
            seen.add(cmd)
            commands.append(cmd)

    for _want, _label, cmd in case_commands():
        add(cmd)
    for cmd in ATTACK_FORMS + [ATTACK_ALLOW_FORM] + BENIGN_CONTROLS:
        add(cmd)
    for text, *_rest in CONTEXT_FORMS:
        add(text)
    for form in COMMAND_POSITION_FORMS:
        add(form + TAIL)
    for text, *_rest in NON_ARITHMETIC_FORMS:
        add(text)
    for text, *_rest in PROCESS_SUBSTITUTION_FORMS:
        add(text)
    for form, _regions in EXPANSION_POSITION_FORMS:
        add(form + TAIL)
    for text, *_rest in HEREDOC_BODY_START_FORMS:
        add(text)
    for text in REWORK_REPEATED_FORMS:
        add(text)
    for text, _opener in UNCLOSED_OPENER_FORMS:
        add(text)
    for text, *_rest in CANDIDATE_FORMS:
        add(text)
    return commands


class TestStageAgreement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commands = all_commands()

    def each(self, check):
        for command in self.commands:
            with self.subTest(command=command[:80]):
                check(Analysis(command))

    # (a) scan_structure() agrees with the lexer's regions.
    def test_a_scan_structure_follows_the_lexer(self):
        def check(a):
            spans = sorted(
                (a.s_pos(r.start), a.s_pos(r.end))
                for r in a.lex_o.regions
                if r.kind in SUBSTITUTION_KINDS and r.closed
            )
            self.assertEqual(sorted(a.scan[0]), spans)
            opaque = sorted(
                (a.s_pos(r.start), a.s_pos(r.end))
                for r in a.lex_o.regions
                if r.parent is None and r.kind in OPAQUE_KINDS
            )
            self.assertEqual(a.scan[3], opaque)
            candidates = [
                (a.s_pos(c.start), a.s_pos(c.end)) for c in a.lex_o.candidates
            ]
            self.assertEqual(sorted(a.broad[0]), sorted(spans + candidates))

        self.each(check)

    def test_a_unterminated_substitutions_are_reported_unmatched(self):
        def check(a):
            unterminated = sorted(
                a.s_pos(r.start)
                for r in a.lex_o.regions
                if r.kind in SUBSTITUTION_KINDS and not r.closed
            )
            self.assertEqual(sorted(a.scan[2]), unterminated)

        self.each(check)

    def test_a_real_heredoc_operators_become_the_records(self):
        def check(a):
            with_body = [op for op in a.lex_o.heredocs if op.body_start is not None]
            self.assertEqual(len(with_body), len(a.records))
            for op, record in zip(with_body, a.records):
                self.assertEqual(record.op_start, a.s_pos(op.start))
                self.assertEqual(record.op_end, a.s_pos(op.end))
                self.assertEqual(record.quoted, op.quoted)
                self.assertEqual(record.body, a.command[op.body_start : op.body_end])
                self.assertEqual(
                    a.stripped[record.op_start : record.op_end],
                    a.command[op.start : op.end],
                )

        self.each(check)

    # (b) separators.
    def test_b_separators_lie_outside_every_region(self):
        def check(a):
            segments, starts, _operators = H._lex_layout(a.marked, True)
            if starts is None:
                return
            regions = a.layout_regions()
            ranges = []
            for k in range(len(segments) - 1):
                sep = segments[k][2]
                end = starts[k + 1]
                ranges.append((end - len(sep), end))
            for m_start, m_end in ranges:
                for m_pos in range(m_start, m_end):
                    kind, s_pos = a.marked.posmap.to_old(m_pos)[:2]
                    self.assertEqual(kind, "copy")
                    self.assertFalse(
                        a.in_region(regions, s_pos),
                        msg="separator at %d lies inside a region" % s_pos,
                    )
            separator_positions = set()
            for m_start, m_end in ranges:
                for m_pos in range(m_start, m_end):
                    separator_positions.add(a.marked.posmap.to_old(m_pos)[1])
            text = a.stripped
            for pos, ch in enumerate(text):
                if ch != "\n" or a.in_region(regions, pos):
                    continue
                backslashes = 0
                while pos - 1 - backslashes >= 0 and text[pos - 1 - backslashes] == "\\":
                    backslashes += 1
                if backslashes % 2 == 1:
                    continue
                self.assertIn(
                    pos, separator_positions, msg="newline at %d is no separator" % pos
                )

        self.each(check)

    # (c) heredoc operator records.
    def test_c_real_operators_are_recorded_in_their_statement(self):
        def check(a):
            segments, starts, operators = H._lex_layout(a.marked, True)
            if starts is None:
                return
            substitutions = [
                r for r in a.lex_s.regions if r.kind in SUBSTITUTION_KINDS
            ]
            for op in a.lex_o.heredocs:
                s_pos = a.s_pos(op.start)
                if a.in_region(substitutions, s_pos):
                    continue
                m_pos = to_new_position(a.marked.posmap, s_pos)
                k = bisect.bisect_right(starts, m_pos) - 1
                self.assertIn(m_pos, operators.get(k, []), msg="operator at %d" % op.start)

        self.each(check)

    def test_c_no_record_lies_inside_a_region(self):
        def check(a):
            _segments, starts, operators = H._lex_layout(a.marked, True)
            if starts is None:
                return
            regions = a.layout_regions()
            for k, held in operators.items():
                for m_pos in held:
                    kind, s_pos = a.marked.posmap.to_old(m_pos)[:2]
                    self.assertEqual(kind, "copy")
                    if a.in_region(regions, s_pos):
                        self.fail("record at %d lies inside a region" % s_pos)

        self.each(check)

    # (d) Tok provenance.
    def test_d_tok_provenance_matches_the_contract(self):
        def check(a):
            if "\x00" in a.command:
                return
            try:
                raw = H._tokenize_marked(a.marked)
            except ValueError:
                return
            regions = a.layout_regions()
            quote_regions = a.quote_ranges()
            for tok, start, end in raw:
                s_start = a.marked.posmap.to_old(start)
                s_end_kind = a.marked.posmap.to_old(end - 1) if end > start else s_start
                # A span that touches a marker residue maps whole; widen it
                # to the substitution it replaced.
                lo = s_start[1] if s_start[0] == "copy" else s_start[1]
                hi = (
                    s_end_kind[1] + 1
                    if s_end_kind[0] == "copy"
                    else s_end_kind[2]
                )
                text = a.marked.text[start:end]
                expected_operator = bool(text) and all(
                    c in H.PUNCTUATION for c in text
                ) and not any(r.start < hi and lo < r.end for r in regions)
                self.assertEqual(tok.is_operator, expected_operator, msg=repr(text))
                expected_quoted = any(q_s < hi and lo < q_e for q_s, q_e in quote_regions)
                self.assertEqual(tok.quoted, expected_quoted, msg=repr(text))
            # unresolved / substitution_only keep coming from the existing
            # marker mechanism: a token whose value holds marker residue is
            # unresolved (text beside the residue) or substitution_only
            # (nothing but residue); any other token is neither.
            stripped = H._strip_unresolved_marks([t for t, _s, _e in raw])
            for (tok, start, end), done in zip(raw, stripped):
                value = str(tok)
                if H._MARK_RE.search(value):
                    rest = H._MARK_RE.sub("", value)
                    self.assertEqual(done.substitution_only, rest == "", msg=repr(value))
                    self.assertEqual(done.unresolved, rest != "", msg=repr(value))
                elif a.command.count("\x00") == 0:
                    self.assertFalse(done.unresolved, msg=repr(value))
                    self.assertFalse(done.substitution_only, msg=repr(value))

        self.each(check)

    # (e) inspection values.
    def test_e_values_carry_no_mask_character(self):
        def check(a):
            try:
                raw = H._tokenize_marked(a.marked)
            except ValueError:
                return
            mask = a.marked.mask_char
            self.assertNotIn(mask, a.marked.text)
            for tok, _start, _end in raw:
                self.assertNotIn(mask, tok)
            segments = H._lex_layout(a.marked, False)[0]
            for toks, _lexed, sep in segments:
                for tok in toks:
                    self.assertNotIn(mask, tok)

        self.each(check)

    def test_e_unmasked_spans_equal_their_shlex_reading(self):
        def check(a):
            try:
                raw = H._tokenize_marked(a.marked)
            except ValueError:
                return
            masked = set()
            for lo, hi in a.marked.mask_ranges:
                masked.update(range(lo, hi))
            for tok, start, end in raw:
                if tok.is_operator or any(p in masked for p in range(start, end)):
                    continue
                self.assertEqual(
                    shlex.split(a.marked.text[start:end], comments=False),
                    [str(tok)],
                    msg=repr(a.marked.text[start:end]),
                )

        self.each(check)

    def test_e_tokens_keeps_values_clean_and_matches_shlex_without_regions(self):
        def check(a):
            for segment in H.SEGMENT_SPLIT.split(a.command):
                if not segment.strip():
                    continue
                got = H.tokens(segment)
                for word in got:
                    for ch in word:
                        if 0xE000 <= ord(ch) <= 0xF8FF:
                            self.assertIn(ch, a.command)
                lexmap = H.lex_shell(segment)
                if any(r.kind in HIDDEN_KINDS for r in lexmap.regions) or "#" in segment:
                    continue
                try:
                    want = shlex.split(segment, comments=False)
                except ValueError:
                    continue
                self.assertEqual(got, want, msg=repr(segment))

        self.each(check)

    # (f) position map.
    def test_f_position_maps_meet_their_contract(self):
        def check(a):
            self.check_posmap(a.omap, a.command, a.stripped)
            self.check_posmap(a.marked.posmap, a.stripped, a.marked.text)

        self.each(check)

    def check_posmap(self, posmap, old_text, new_text):
        self.assertEqual(posmap.old_len, len(old_text))
        self.assertEqual(posmap.new_len, len(new_text))
        previous_old = previous_new = 0
        for kind, old_start, old_end, new_start, new_end, ref in posmap.segments:
            self.assertEqual(old_start, previous_old)
            self.assertEqual(new_start, previous_new)
            previous_old, previous_new = old_end, new_end
            if kind == "copy":
                self.assertEqual(old_end - old_start, new_end - new_start)
                self.assertEqual(old_text[old_start:old_end], new_text[new_start:new_end])
                # constant shift: round trips return the same position and character
                for probe in {old_start, (old_start + old_end) // 2, old_end - 1}:
                    if not old_start <= probe < old_end:
                        continue
                    mapped = posmap.to_new(probe)
                    self.assertEqual(mapped[0], "copy")
                    back = posmap.to_old(mapped[1])
                    self.assertEqual(back[:2], ("copy", probe))
                    self.assertEqual(old_text[probe], new_text[mapped[1]])
            else:
                self.assertEqual(kind, "replace")
                for probe in {old_start, (old_start + old_end) // 2, old_end - 1}:
                    if not old_start <= probe < old_end:
                        continue
                    mapped = posmap.to_new(probe)
                    self.assertEqual(mapped, ("replace", new_start, new_end, ref))
                for probe in {new_start, (new_start + new_end) // 2, new_end - 1}:
                    if not new_start <= probe < new_end:
                        continue
                    back = posmap.to_old(probe)
                    self.assertEqual(back, ("replace", old_start, old_end, ref))
        self.assertEqual(previous_old, len(old_text))
        self.assertEqual(previous_new, len(new_text))
        # order is kept
        last = -1
        for probe in range(0, len(old_text), max(1, len(old_text) // 200)):
            mapped = posmap.to_new(probe)
            value = mapped[1]
            self.assertGreaterEqual(value, last)
            last = value


# ---------------------------------------------------------------------------
# Position map contract.
# ---------------------------------------------------------------------------


class TestPositionMap(unittest.TestCase):
    def test_removed_heredoc_body_maps_as_a_whole_to_its_record(self):
        text = "cat <<EOF\nrm -rf /tmp/zz\nEOF\necho done"
        stripped, records, omap = H._strip_heredocs_mapped(text)
        self.assertEqual(stripped, "cat <<EOF\necho done")
        self.assertEqual(len(records), 1)
        replaced = [seg for seg in omap.segments if seg[0] == "replace"]
        self.assertEqual(len(replaced), 1)
        _kind, old_start, old_end, new_start, new_end, ref = replaced[0]
        self.assertIs(ref, records[0])
        self.assertEqual(text[old_start:old_end], "rm -rf /tmp/zz\nEOF\n")
        self.assertEqual(new_start, new_end)
        for probe in range(old_start, old_end):
            self.assertEqual(
                omap.to_new(probe), ("replace", new_start, new_end, records[0])
            )

    def test_marker_longer_than_the_substitution_maps_as_a_whole_range(self):
        text = "echo $() $() $()"
        spans, parent_of, _unmatched, _opaque, _containing = H.scan_structure(text)
        top = H._top_level_spans(spans, parent_of)
        self.assertEqual(len(top), 3)
        marked = H._mark_substitutions(text, top, 10)
        # `$()` is three characters; the marker for index 10 is four.
        replaced = [seg for seg in marked.posmap.segments if seg[0] == "replace"]
        self.assertEqual(len(replaced), 3)
        for _kind, s_start, s_end, m_start, m_end, _ref in replaced:
            self.assertEqual(s_end - s_start, 3)
            self.assertGreater(m_end - m_start, s_end - s_start)
            for probe in range(s_start, s_end):
                self.assertEqual(marked.posmap.to_new(probe)[:3], ("replace", m_start, m_end))
            for probe in range(m_start, m_end):
                self.assertEqual(marked.posmap.to_old(probe)[:3], ("replace", s_start, s_end))
        self.assertEqual(
            marked.text,
            "echo %s %s %s"
            % tuple("%s%d%s" % (H.UNRESOLVED_MARK, 10 + i, H._MARK_TERMINATOR) for i in range(3)),
        )

    def test_marker_shorter_than_the_substitution_maps_as_a_whole_range(self):
        text = "echo $(cat /etc/hostname)"
        spans, parent_of, _u, _o, _c = H.scan_structure(text)
        top = H._top_level_spans(spans, parent_of)
        marked = H._mark_substitutions(text, top, 0)
        replaced = [seg for seg in marked.posmap.segments if seg[0] == "replace"]
        self.assertEqual(len(replaced), 1)
        _kind, s_start, s_end, m_start, m_end, _ref = replaced[0]
        self.assertLess(m_end - m_start, s_end - s_start)
        self.assertEqual(marked.posmap.to_new(s_start + 3)[:3], ("replace", m_start, m_end))

    def test_substitution_in_a_removed_heredoc_body_is_not_marked_at_this_level(self):
        text = "cat <<EOF\n$(rm -rf /tmp/zz)\nEOF\necho $(date)"
        stripped, _records, _omap = H._strip_heredocs_mapped(text)
        self.assertEqual(stripped, "cat <<EOF\necho $(date)")


# ---------------------------------------------------------------------------
# The three substitution searches stay distinct (FR9, AC-6).
# ---------------------------------------------------------------------------


class TestSubstitutionPolicies(unittest.TestCase):
    TEXT = "echo '$(a)' # $(b)"

    def texts(self, spans, text):
        return sorted(text[s:e] for s, e in spans)

    def test_shell_mode_honors_single_quotes_and_comments(self):
        spans = H.scan_structure(self.TEXT, mode="shell")[0]
        self.assertEqual(spans, [])

    def test_heredoc_body_mode_treats_top_level_quotes_and_hash_as_literal(self):
        spans = H.scan_structure(self.TEXT, mode="heredoc-body")[0]
        self.assertEqual(self.texts(spans, self.TEXT), ["$(a)", "$(b)"])

    def test_broad_search_also_finds_substitutions_inside_single_quotes(self):
        spans = H.scan_structure(self.TEXT, mode="shell", honor_single_quotes=False)[0]
        self.assertEqual(self.texts(spans, self.TEXT), ["$(a)"])

    def test_broad_spans_are_default_spans_plus_candidates(self):
        text = "echo $(echo '$(a)' `x`) '`y`' \"$(z)\""
        default = H.scan_structure(text, mode="shell")[0]
        broad = H.scan_structure(text, mode="shell", honor_single_quotes=False)[0]
        lexmap = H.lex_shell(text)
        candidates = [(c.start, c.end) for c in lexmap.candidates]
        self.assertEqual(sorted(broad), sorted(default + candidates))
        self.assertTrue(candidates)

    def test_substitution_inside_an_expansion_is_queued_for_scanning(self):
        for command in (
            "echo ${x:-$(rm -rf /home/sakura/valuable)}",
            "echo $(( $(rm -rf /home/sakura/valuable) + 1 ))",
            'echo "${x:-$(rm -rf /home/sakura/valuable)}"',
        ):
            with self.subTest(command=command):
                words = [toks[0] for _t, toks, *_r in H.statements(command) if toks]
                self.assertIn("rm", words)

    def test_process_substitution_body_is_its_own_chunk_and_host_keeps_the_opener(self):
        command = "tee >(bash) <<'EOF'\nrm -rf /home/sakura/valuable\nEOF"
        statements = list(H.statements(command))
        hosts = [toks for _t, toks, *_r in statements if toks and toks[0] == "tee"]
        self.assertEqual(len(hosts), 1)
        self.assertTrue(H._has_process_substitution(hosts[0]))
        words = [toks[0] for _t, toks, *_r in statements if toks]
        self.assertIn("bash", words)
        command = "cat <(rm -rf /home/sakura/valuable)"
        words = [toks[0] for _t, toks, *_r in H.statements(command) if toks]
        self.assertIn("rm", words)
        hosts = [toks for _t, toks, *_r in H.statements(command) if toks and toks[0] == "cat"]
        self.assertTrue(H._has_process_substitution(hosts[0]))

    def test_heredoc_operator_inside_a_process_substitution_is_attributed_there(self):
        command = "cat <(bash <<EOF\nrm -rf /home/sakura/valuable\nEOF\n)"
        self.assertEqual(hook_verdict(command)[0], "deny")
        command = "echo $(bash <<EOF\nrm -rf /home/sakura/valuable\nEOF\n)"
        self.assertEqual(hook_verdict(command)[0], "deny")
        command = "echo $(cat <<'EOF'\nrm -rf /home/sakura/valuable\nEOF\n)"
        self.assertEqual(hook_verdict(command)[0], "allow")


# ---------------------------------------------------------------------------
# Heredoc bodies change no lexer state (FR8, AC-5).
# ---------------------------------------------------------------------------


class TestHeredocBodies(unittest.TestCase):
    BODIES = [
        "it's",
        'say "hi',
        "# not a comment",
        "${x",
        "$((1",
        "$'a",
        "$[1",
        "`x",
        "$(y",
        "it's \"${ $(( $' # `",
    ]

    def test_nothing_in_a_body_opens_anything_for_the_following_text(self):
        for body in self.BODIES:
            command = "cat <<EOF\n%s\nEOF\nrm -rf /home/sakura/valuable" % body
            with self.subTest(body=body):
                lexmap = H.lex_shell(command)
                self.assertEqual(actual_regions(lexmap), [])
                self.assertEqual(len(lexmap.heredocs), 1)
                self.assertEqual(heredoc_body(command, lexmap.heredocs[0]), body + "\n")
                self.assertIsNone(lexmap.tail_start)
                self.assertEqual(hook_verdict(command)[0], "deny")

    def test_a_body_in_a_double_quoted_substitution_is_still_a_body(self):
        command = 'echo "$(cat <<EOF\nit\'s\nEOF\n)"; rm -rf /home/sakura/valuable'
        lexmap = H.lex_shell(command)
        self.assertEqual(len(lexmap.heredocs), 1)
        self.assertEqual(hook_verdict(command)[0], "deny")

    def test_sink_bound_body_in_a_substitution_is_scanned(self):
        for command in (
            "echo $(bash <<EOF\nrm -rf /home/sakura/valuable\nEOF\n)",
            "x=$(sh -s <<EOF\ngit reset --hard HEAD\nEOF\n)",
            "cat <(bash <<EOF\nrm -rf /home/sakura/valuable\nEOF\n)",
        ):
            with self.subTest(command=command):
                self.assertEqual(hook_verdict(command)[0], "deny")

    def test_quote_in_a_body_does_not_hide_the_next_heredoc(self):
        command = "cat <<A\nit's\nA\nbash <<B\nrm -rf /home/sakura/valuable\nB"
        self.assertEqual(hook_verdict(command)[0], "deny")


# ---------------------------------------------------------------------------
# Here-document delimiter words (round 2 residuals, task0003: FR4, NFR1, NFR6;
# review finding 9381769d7116fab2, second half). The delimiter of `<<` / `<<-`
# is the whole following word with its quotes removed, and a word that cannot
# be read takes no body.
# ---------------------------------------------------------------------------


class TestHeredocDelimiterWords(unittest.TestCase):
    DESTRUCTIVE = "rm -rf /home/sakura/valuable"

    # AC-1 / AC-2: (command, operator text, delimiter, quoted, delimiter line).
    # The commands are the three deny cases this task appends to the case
    # table; each one holds a decoy line the old reading closed the body at.
    CASE_FORMS = [
        (
            "cat <<END-X\nbody\nEND-X\nrm -rf /home/sakura/valuable\nEND",
            "<<END-X", "END-X", False, "END-X\n",
        ),
        (
            "cat <<E.X\nbody\nE.X\nrm -rf /home/sakura/valuable\nE",
            "<<E.X", "E.X", False, "E.X\n",
        ),
        (
            "cat <<E\\X\nbody\nEX\nrm -rf /home/sakura/valuable\nE",
            "<<E\\X", "EX", True, "EX\n",
        ),
    ]

    # AC-3: (command, operator text, delimiter, quoted, body).
    VARIANT_FORMS = [
        (
            'cat <<E"X"\nbody\nEX\nrm -rf /home/sakura/valuable',
            '<<E"X"', "EX", True, "body\n",
        ),
        (
            "cat <<'E-X'\nbody\nE-X\nrm -rf /home/sakura/valuable",
            "<<'E-X'", "E-X", True, "body\n",
        ),
        (
            "cat <<\\EOF\nbody\nEOF\nrm -rf /home/sakura/valuable",
            "<<\\EOF", "EOF", True, "body\n",
        ),
        (
            "cat <<E$X\nbody\nE$X\nrm -rf /home/sakura/valuable",
            "<<E$X", "E$X", False, "body\n",
        ),
        (
            "cat <<-EOF\n\tbody\n\tEOF\nrm -rf /home/sakura/valuable",
            "<<-EOF", "EOF", False, "\tbody\n",
        ),
        (
            "cat <<-END-X\n\tbody\n\tEND-X\nrm -rf /home/sakura/valuable",
            "<<-END-X", "END-X", False, "\tbody\n",
        ),
        (
            'cat <<"E\\"X"\nbody\nE"X\nrm -rf /home/sakura/valuable',
            '<<"E\\"X"', 'E"X', True, "body\n",
        ),
        (
            'cat <<"E\\aX"\nbody\nE\\aX\nrm -rf /home/sakura/valuable',
            '<<"E\\aX"', "E\\aX", True, "body\n",
        ),
        (
            'cat <<"E$x"\nbody\nE$x\nrm -rf /home/sakura/valuable',
            '<<"E$x"', "E$x", True, "body\n",
        ),
        (
            "cat <<''\nbody\n\nrm -rf /home/sakura/valuable",
            "<<''", "", True, "body\n",
        ),
    ]

    # AC-4: a delimiter word that cannot be read -- no word before a
    # metacharacter or the end, or a command substitution, a backtick, `${`,
    # `$((`, `$[`, `$'` or `$"` in it. Each holds a destructive line on the
    # line after the operator and a last line the old reading closed at.
    UNREADABLE_FORMS = [
        "cat <<" + TAIL,
        "cat <<-" + TAIL,
        "cat << ;" + TAIL,
        "cat <<E$(x)\nrm -rf /home/sakura/valuable\nE",
        "cat <<E`x`\nrm -rf /home/sakura/valuable\nE",
        "cat <<E${x}\nrm -rf /home/sakura/valuable\nE",
        "cat <<E$((1))\nrm -rf /home/sakura/valuable\nE",
        "cat <<E$[1]\nrm -rf /home/sakura/valuable\nE",
        "cat <<$'E'\nrm -rf /home/sakura/valuable\nE",
        'cat <<$"E"\nrm -rf /home/sakura/valuable\nE',
        'cat <<"E$(x)"\nrm -rf /home/sakura/valuable\nE',
        'cat <<"E`x`"\nrm -rf /home/sakura/valuable\nE',
        "cat <<E\\\nX\nrm -rf /home/sakura/valuable\nE",
    ]

    def operator_of(self, text):
        lexmap = H.lex_shell(text)
        self.assertEqual(len(lexmap.heredocs), 1, msg=repr(text))
        return lexmap, lexmap.heredocs[0]

    def test_whole_word_delimiters_close_at_their_own_line(self):
        # AC-2: one operator, the delimiter the whole word with quotes
        # removed, the body ending before the delimiter line.
        for command, op_text, delimiter, quoted, close_line in self.CASE_FORMS:
            with self.subTest(command=command):
                lexmap, op = self.operator_of(command)
                self.assertEqual(command[op.start : op.end], op_text)
                self.assertEqual((op.delimiter, op.quoted), (delimiter, quoted))
                self.assertEqual(heredoc_body(command, op), "body\n")
                self.assertEqual(command[op.body_end : op.close_end], close_line)
                self.assertIsNone(lexmap.tail_start)

    def test_whole_word_delimiter_forms_are_denied_with_and_without_batch(self):
        # AC-2: the decoy line does not close the body, so the destructive
        # line after the real delimiter line is inspected.
        for command, _op, _delimiter, _quoted, _close in self.CASE_FORMS:
            for batch in (False, True):
                with self.subTest(command=command, batch=batch):
                    decision, reason = hook_verdict(command, batch=batch)
                    self.assertEqual(decision, "deny", msg=reason[:200])

    def test_variant_delimiter_words(self):
        # AC-3: delimiter, quoted flag and body of each variant; the quote
        # characters of the delimiter word are no regions of their own.
        for command, op_text, delimiter, quoted, body in self.VARIANT_FORMS:
            with self.subTest(command=command):
                lexmap, op = self.operator_of(command)
                self.assertEqual(command[op.start : op.end], op_text)
                self.assertEqual((op.delimiter, op.quoted), (delimiter, quoted))
                self.assertEqual(heredoc_body(command, op), body)
                self.assertEqual(actual_regions(lexmap), [])
                self.assertEqual(
                    command[op.close_end :], "rm -rf /home/sakura/valuable"
                )

    def test_variant_delimiter_forms_are_denied(self):
        for command, _op, _delimiter, _quoted, _body in self.VARIANT_FORMS:
            with self.subTest(command=command):
                self.assertEqual(hook_verdict(command)[0], "deny")

    def test_unreadable_delimiter_words_take_no_body(self):
        # AC-4 (NFR6): no operator takes a body, so the line after the
        # operator is read as the command it is.
        for command in self.UNREADABLE_FORMS:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                for op in lexmap.heredocs:
                    self.assertIsNone(op.body_start)
                    self.assertIsNone(op.body_end)
                    self.assertIsNone(op.close_end)
                stripped, records, _omap = H._strip_heredocs_mapped(command)
                self.assertEqual(stripped, command)
                self.assertEqual(records, [])
                for batch in (False, True):
                    decision, reason = hook_verdict(command, batch=batch)
                    self.assertNotEqual(decision, "allow", msg=reason[:200])

    def test_a_later_readable_operator_is_read_after_an_unreadable_one(self):
        command = "cat <<E$(x)\nrm -rf /tmp/zz\nE\ncat <<EOF\nbody\nEOF\n"
        lexmap = H.lex_shell(command)
        bodies = [(op.delimiter, heredoc_body(command, op)) for op in lexmap.heredocs]
        self.assertEqual(bodies, [("EOF", "body\n")])

    def test_a_quote_not_closed_on_the_operators_line_takes_no_body(self):
        # AC-4: no operator, and the text after the `<<` is lexed as the base
        # lexed it for a `<<` that registers no operator (the expected
        # regions were taken from the base before the change): the quote
        # opens a region of its own, running on past the line.
        destructive = "\nrm -rf /home/sakura/valuable\n"
        forms = [
            ("cat <<'EOF" + TAIL, [("single-quote", "'EOF" + TAIL)], False),
            ('cat <<"EOF' + TAIL, [("double-quote", '"EOF' + TAIL)], False),
            (
                "cat <<'EOF" + destructive + "EOF'\n",
                [("single-quote", "'EOF" + destructive + "EOF'")],
                True,
            ),
        ]
        for command, regions, closed in forms:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(list(lexmap.heredocs), [])
                self.assertEqual(actual_regions(lexmap), expected_regions(command, regions))
                self.assertEqual([r.closed for r in lexmap.regions], [closed])
                self.assertIsNone(lexmap.tail_start)

    def test_a_delimiter_holding_a_blank_finds_no_close_line(self):
        # A value the close-line index cannot represent: the operator is read
        # but never finds a close line, so it takes no body.
        for command in (
            "cat <<'E X'\nbody\nE X\nrm -rf /home/sakura/valuable",
            "cat <<E\\ X\nbody\nE X\nrm -rf /home/sakura/valuable",
            'cat <<"E\tX"\nbody\nE\tX\nrm -rf /home/sakura/valuable',
        ):
            with self.subTest(command=command):
                lexmap, op = self.operator_of(command)
                self.assertTrue(any(blank in op.delimiter for blank in " \t"))
                self.assertTrue(op.quoted)
                self.assertIsNone(op.body_start)
                self.assertEqual(hook_verdict(command)[0], "deny")

    def test_close_line_is_the_delimiter_with_optional_blanks_only(self):
        # AC-5: a line holding only the delimiter value, surrounded by
        # spaces and tabs at most, closes the body; one where the value is
        # only a prefix or a suffix does not.
        for delimiter in ("END-X", "E.X", "EOF"):
            command = (
                "cat <<%s\nbody\n%sY\nX%s\n%s-\n \t%s \t\n%s\n" % (
                    (delimiter,) * 6
                )
            )
            with self.subTest(delimiter=delimiter):
                lexmap, op = self.operator_of(command)
                self.assertEqual(op.delimiter, delimiter)
                self.assertEqual(
                    heredoc_body(command, op),
                    "body\n%sY\nX%s\n%s-\n" % ((delimiter,) * 3),
                )
                self.assertEqual(
                    command[op.body_end : op.close_end], " \t%s \t\n" % delimiter
                )

    def test_close_line_index_accepts_non_word_values(self):
        text = "END-X\n  E.X \t\nplain\nE X\n"
        index = H._LexLines(text).word_to_lines()
        self.assertEqual(index["END-X"], [0])
        self.assertEqual(index["E.X"], [1])
        self.assertEqual(index["plain"], [2])
        self.assertNotIn("E X", index)

    def test_word_delimiters_keep_their_reading(self):
        for command, delimiter, quoted in (
            ("cat <<EOF\nbody\nEOF\n", "EOF", False),
            ("cat <<'EOF'\nbody\nEOF\n", "EOF", True),
            ('cat <<"EOF"\nbody\nEOF\n', "EOF", True),
            ("cat <<-EOF\nbody\nEOF\n", "EOF", False),
            ("cat << EOF\nbody\nEOF\n", "EOF", False),
            ("cat <<EOF>out\nbody\nEOF\n", "EOF", False),
            ("(cat <<EOF)\nbody\nEOF\n", "EOF", False),
        ):
            with self.subTest(command=command):
                lexmap, op = self.operator_of(command)
                self.assertEqual((op.delimiter, op.quoted), (delimiter, quoted))
                self.assertEqual(heredoc_body(command, op), "body\n")

    def test_here_string_is_still_no_operator(self):
        command = "cat <<<END-X\nrm -rf /home/sakura/valuable\nEND-X"
        lexmap = H.lex_shell(command)
        self.assertEqual(list(lexmap.heredocs), [])
        self.assertEqual(hook_verdict(command)[0], "deny")

    def test_lexing_work_is_linear_for_non_word_delimiters(self):
        # AC-6 (NFR1).
        unit = "cat <<END-X\nbody\nEND-X\n"
        small = H.lex_shell(unit * 200)
        large = H.lex_shell(unit * 400)
        # Every operator finds its own close line, so the close-line lookup
        # is part of the work measured here.
        self.assertEqual(len(large.heredocs), 400)
        self.assertTrue(all(op.body_start is not None for op in large.heredocs))
        self.assertLessEqual(large.work, 2.5 * small.work + 100)
        self.assertLessEqual(large.work, H.LEX_WORK_FACTOR * len(unit * 400) + 1024)

    def test_lexing_work_is_linear_for_unreadable_words(self):
        for unit in (
            "cat <<'E$(x)\nbody\n",
            'cat <<"E $(x) \n',
            "cat <<E`x`\nbody\nE\n",
        ):
            with self.subTest(unit=unit):
                small = H.lex_shell(unit * 200)
                large = H.lex_shell(unit * 400)
                self.assertLessEqual(large.work, 2.5 * small.work + 100)
                self.assertLessEqual(
                    large.work, H.LEX_WORK_FACTOR * len(unit * 400) + 1024
                )

    def test_new_cases_are_in_the_case_table_after_the_earlier_entries(self):
        # AC-1, AC-7: located by label and command text, never by an absolute
        # index; each sits after the 627 entries present at the feature base.
        cases = case_commands()
        for command, _op, _delimiter, _quoted, _close in self.CASE_FORMS:
            with self.subTest(command=command):
                found = [
                    (index, want, label)
                    for index, (want, label, cmd) in enumerate(cases)
                    if cmd == command
                ]
                self.assertEqual(len(found), 1)
                index, want, label = found[0]
                self.assertGreaterEqual(index, 627)
                self.assertEqual(want, "deny")
                self.assertTrue(label.startswith("9381769d7116fab2 round2-residuals "))


class TestDelimiterWordStageAgreement(TestStageAgreement):
    """The stage agreement properties (a)-(f) of TestStageAgreement, over the
    delimiter word forms of this task: the lexer's quoted delimiter words,
    the masked view and the position maps agree on every one of them."""

    @classmethod
    def setUpClass(cls):
        forms = [form[0] for form in TestHeredocDelimiterWords.CASE_FORMS]
        forms += [form[0] for form in TestHeredocDelimiterWords.VARIANT_FORMS]
        forms += TestHeredocDelimiterWords.UNREADABLE_FORMS
        cls.commands = forms


# ---------------------------------------------------------------------------
# Unclosed openers in bulk (NFR1, NFR3, AC-7).
# ---------------------------------------------------------------------------


class TestUnclosedOpeners(unittest.TestCase):
    OPENERS = ["${", "$((", "$[", "((", "$'"]
    DESTRUCTIVE = "\nrm -rf /home/sakura/valuable\n"

    def bulk(self, opener, size=60000):
        return (opener + " ") * (size // (len(opener) + 1)) + self.DESTRUCTIVE

    def test_bulk_unclosed_openers_get_a_non_allow_decision_in_time(self):
        for opener in self.OPENERS:
            command = self.bulk(opener)
            with self.subTest(opener=opener):
                start = time.monotonic()
                decision, _reason = hook_verdict(command)
                self.assertNotEqual(decision, "allow")
                self.assertNotEqual(decision, "(timeout)")
                self.assertLess(time.monotonic() - start, GUARD_TIMEOUT_SECONDS)

    def test_mixed_bulk_openers_get_a_non_allow_decision_in_time(self):
        unit = "${ $(( $[ (( $' "
        command = unit * (60000 // len(unit)) + self.DESTRUCTIVE
        decision, _reason = hook_verdict(command)
        self.assertNotIn(decision, ("allow", "(timeout)"))

    def test_same_command_gives_an_identical_map_and_decision(self):
        command = self.bulk("${", 6000)
        first = H.lex_shell(command)
        H._LEX_CACHE.clear()
        second = H.lex_shell(command)
        self.assertIsNot(first, second)
        self.assertEqual(first.as_tuple(), second.as_tuple())
        self.assertEqual(hook_verdict(command), hook_verdict(command))

    def test_lexing_work_is_linear_for_unclosed_and_closed_forms(self):
        unit_forms = {
            "closed": "echo ${x} $((1+2)) \"a\" $'b' # c\n",
            "one unclosed per line": "echo ${x\n",
            "unclosed quote chars": "echo $'x\n",
        }
        for name, unit in unit_forms.items():
            with self.subTest(form=name):
                small = H.lex_shell(unit * 200)
                large = H.lex_shell(unit * 400)
                self.assertLessEqual(large.work, 2.5 * small.work + 100)
                self.assertLessEqual(large.work, H.LEX_WORK_FACTOR * len(unit * 400) + 1024)

    def test_many_unclosed_openers_are_settled_without_a_rescan_per_opener(self):
        command = "${ " * 20000
        lexmap = H.lex_shell(command)
        self.assertLessEqual(lexmap.work, H.LEX_WORK_FACTOR * len(command) + 1024)
        self.assertEqual(len(lexmap.unopened), 20000)
        self.assertEqual(lexmap.tail_start, 0)

    def test_budget_exceeded_is_an_ask_never_an_allow(self):
        command = "(( ;" * 15000 + self.DESTRUCTIVE
        decision, _reason = hook_verdict(command)
        self.assertIn(decision, ("ask", "deny"))


# ---------------------------------------------------------------------------
# `((` / `$((` openers that close without an adjacent `))` (review round 2,
# finding 29bbf9032dd762a0): the unit forms, shared by the linearity test of
# TestReworkLinearity and by TestNonAdjacentCloseRereading.
# ---------------------------------------------------------------------------

NON_ADJACENT_STABLE_ID = "29bbf9032dd762a0"


def expansion_lines(count):
    """COUNT lines `x=$((echo N) | wc -c)`, N the line number, joined by a
    newline with no trailing newline."""
    return "\n".join("x=$((echo %d) | wc -c)" % n for n in range(count))


def command_lines(count):
    """COUNT statements `((cd /tmp/aN && ls) || echo no)`, N the statement
    number, joined by a newline with no trailing newline."""
    return "\n".join("((cd /tmp/a%d && ls) || echo no)" % n for n in range(count))


# The three inputs of the review record: L28 and L100 are 633 and 2289
# characters; S40 is forty statements.
NON_ADJACENT_FORMS = {
    "L28": expansion_lines(28),
    "L100": expansion_lines(100),
    "S40": command_lines(40),
}
NON_ADJACENT_UNITS = {
    "arithmetic expansion": expansion_lines,
    "arithmetic command": command_lines,
}


# ---------------------------------------------------------------------------
# Rework round 1: the two ~60KB inputs (task0002 AC-6, NFR3).
# ---------------------------------------------------------------------------


class TestReworkLinearity(unittest.TestCase):
    """Reading a reserved word after a closer (P10) and deferring a heredoc
    body over a multi-line region (P11) must stay linear in the text. Each
    input is run through the hook's stdin JSON / stdout contract and timed."""

    DESTRUCTIVE = "rm -rf /home/sakura/valuable"
    SIZE = 60000

    def inputs(self):
        reserved = "if (true) then ((1<<2)); fi\n"
        deferred = 'cat <<EOF; echo "\n"; :\nEOF\n'
        return {
            "reserved word after a closer": (
                reserved * (self.SIZE // len(reserved)) + self.DESTRUCTIVE
            ),
            "heredoc body deferred over a multi-line quote": (
                deferred * (self.SIZE // len(deferred)) + self.DESTRUCTIVE
            ),
        }

    def test_each_input_gets_deny_within_the_time_limit(self):
        for name, command in self.inputs().items():
            with self.subTest(form=name):
                self.assertGreater(len(command), 50000)
                start = time.monotonic()
                decision, reason = hook_verdict(command)
                self.assertEqual(decision, "deny", msg=reason[:200])
                self.assertLess(time.monotonic() - start, GUARD_TIMEOUT_SECONDS)

    def test_lexing_work_stays_within_the_linear_bound(self):
        for name, command in self.inputs().items():
            with self.subTest(form=name):
                lexmap = H.lex_shell(command)
                self.assertLessEqual(
                    lexmap.work, H.LEX_WORK_FACTOR * len(command) + 1024
                )

    def test_lexing_work_grows_linearly_with_the_input(self):
        units = {
            "reserved word after a closer": "if (true) then ((1<<2)); fi\n",
            "heredoc body deferred over a multi-line quote": 'cat <<EOF; echo "\n"; :\nEOF\n',
        }
        for name, unit in units.items():
            with self.subTest(form=name):
                small = H.lex_shell(unit * 200)
                large = H.lex_shell(unit * 400)
                self.assertLessEqual(large.work, 2.5 * small.work + 100)

    def test_lexing_work_is_linear_for_closes_that_are_not_adjacent(self):
        # AC-3 (FR5, FR7, NFR1): every line holds a `((` / `$((` whose first
        # close is a lone `)`; doubling the lines at most about doubles the
        # work, and the work stays within the work bound.
        for name, build in NON_ADJACENT_UNITS.items():
            with self.subTest(form=name):
                small = H.lex_shell(build(200))
                large_text = build(400)
                large = H.lex_shell(large_text)
                self.assertLessEqual(large.work, 2.5 * small.work + 100)
                self.assertLessEqual(
                    large.work, H.LEX_WORK_FACTOR * len(large_text) + 1024
                )


# ---------------------------------------------------------------------------
# `((` / `$((` read as two parentheses when the close is not adjacent (task0004
# of destructive-guard-lexer-round2-residuals, FR5-FR8, NFR1-NFR5, TM-4).
# ---------------------------------------------------------------------------

# Maps written out by hand (D6): text, regions as (kind, literal[, n]), real
# here-document operators as (delimiter, quoted, body). Each form holds an
# opener that closes without an adjacent `))`, read as two parentheses.
NON_ADJACENT_MAP_FORMS = [
    # An opener nested in another's span: the inner one is read as two
    # parentheses first; the outer one then closes without an adjacent `))`
    # as well, runs to the end of the text and stays unclosed.
    (
        "$(( $((echo a) ) )",
        [
            ("command-substitution", "$(( $((echo a) ) )"),
            ("command-substitution", "$((echo a) )"),
        ],
        [],
    ),
    # The outer opener closes with an adjacent `))` around the inner one.
    (
        "$(( $((echo a) | cat) ))",
        [
            ("arithmetic-expansion", "$(( $((echo a) | cat) ))"),
            ("command-substitution", "$((echo a) | cat)"),
        ],
        [],
    ),
    # Inside double quotes.
    (
        'echo "$((echo a) | wc -c)"',
        [
            ("double-quote", '"$((echo a) | wc -c)"'),
            ("command-substitution", "$((echo a) | wc -c)"),
        ],
        [],
    ),
    # The span crosses a line start while an earlier operator is pending: the
    # open substitution defers the body to the line after its close.
    (
        "cat <<EOF; echo $((echo a\n) | wc -c)\nbody\nEOF\necho done",
        [("command-substitution", "$((echo a\n) | wc -c)")],
        [("EOF", False, "body\n")],
    ),
    # An operator registered inside the span takes its body there: the
    # substitution that encloses it never defers it.
    (
        "echo $((cat <<EOF\nbody\nEOF\n) | wc -c)\necho done",
        [("command-substitution", "$((cat <<EOF\nbody\nEOF\n) | wc -c)")],
        [("EOF", False, "body\n")],
    ),
    # An operator registered inside a nested substitution of the span, with
    # its body in the lines after the span: read once the span is read as two
    # parentheses, never twice.
    (
        "echo $(( $(cat <<EOF\nbody\nEOF\n) ) | wc -c)\necho done",
        [
            ("command-substitution", "$(( $(cat <<EOF\nbody\nEOF\n) ) | wc -c)"),
            ("command-substitution", "$(cat <<EOF\nbody\nEOF\n)"),
        ],
        [("EOF", False, "body\n")],
    ),
    (
        "echo $(( $(cat <<EOF) ) | wc -c)\nbody\nEOF\necho done",
        [
            ("command-substitution", "$(( $(cat <<EOF) ) | wc -c)"),
            ("command-substitution", "$(cat <<EOF)"),
        ],
        [("EOF", False, "body\n")],
    ),
    # An operator pending before the span and another one registered in it.
    (
        "cat <<E1; echo $(( $(cat <<E2) ) | wc -c)\nb1\nE1\nb2\nE2\necho done",
        [
            ("command-substitution", "$(( $(cat <<E2) ) | wc -c)"),
            ("command-substitution", "$(cat <<E2)"),
        ],
        [("E1", False, "b1\n"), ("E2", False, "b2\n")],
    ),
]

# SHA-256 of json.dumps(first 627 case-table entries, ensure_ascii=False).
BASE_ENTRIES_DIGEST = "c6e3b706fb5c0425ca1e89a361aaf812603c4768e509007824fee643a65c3c5b"

# Tokens the generated forms are built from.
NON_ADJACENT_TOKENS = [
    "$((", "((", "(", ")", "))", ")", " ", " ", "a", "echo a", "\n", '"', "'",
    "`", "<<E", "\nE\n", "$(", "${", "}", ";", "|", "&&", "#", "$'", "x=",
    "$[", "]", "cat ", "if ", "then ", "fi", "\\", "$", "<(",
]


def lexical_reading(lexmap):
    """The parts of a lexical map that carry its meaning."""
    return (
        tuple(lexmap.regions),
        tuple(lexmap.heredocs),
        tuple(lexmap.candidates),
        tuple(lexmap.unopened),
        lexmap.tail_start,
    )


def whole_text_restart_reading(text, mode="shell", bodies=True):
    """The reading today's whole-text restart gives, driven over the pass
    function with no work limit: every `((` / `$((` whose first close is not
    an adjacent `))` is added to the openers read as two parentheses and the
    whole text is read again; every unclosed opener is settled the same way.
    Returns what lexical_reading() returns."""
    if bodies and (mode != "shell" or "<<" not in text):
        bodies = False
    lines = H._LexLines(text) if bodies else None
    settled = set()
    reparen = set()
    while True:
        result = H._lex_pass(
            text, mode, settled, reparen, lines, 1 << 60, whole_restart=True
        )
        if result[0] == "done":
            break
        settled.update(result[1])
        reparen.update(result[2])
    _, regions, ops, candidates, encountered, _iterations = result
    return (
        tuple(H.LexRegion(k, s, e, parent, closed) for k, s, e, parent, closed, _a in regions),
        tuple(H.LexHeredoc(*op) for op in ops),
        tuple(sorted(candidates, key=lambda c: (c.start, c.end))),
        tuple(sorted(encountered)),
        min(settled) if settled else None,
    )


def generated_forms(count, seed=29):
    rng = random.Random(seed)
    forms = []
    for _ in range(count):
        size = rng.randint(3, 16)
        forms.append("".join(rng.choice(NON_ADJACENT_TOKENS) for _ in range(size)))
    return forms


def nested_forms(count, seed=29):
    """COUNT forms built from nested openers, quotes, substitutions and
    here-document operators, some of them damaged by one inserted or deleted
    character; deterministic for a SEED."""
    rng = random.Random(seed)
    leaves = [
        "echo a", "x", "a b", "1+2", "", "cat <<E", "echo 'q'", 'echo "q"', "#c",
        "$x", "${y}",
    ]
    closers = ["", ")", " )", ")) "]
    separators = [" ", "\n", ";", " | ", " && ", "\n\n", " # c\n"]

    def build(depth):
        if depth <= 0:
            return rng.choice(leaves)
        kind = rng.randint(0, 17)
        inner = build(depth - 1)
        if kind == 0:
            return "$((" + inner + ")" + rng.choice(closers)
        if kind == 1:
            return "((" + inner + ")" + rng.choice(closers)
        if kind == 2:
            return "(" + inner + ")"
        if kind == 3:
            return "$(" + inner + ")"
        if kind == 4:
            return '"' + inner + '"'
        if kind == 5:
            return "'" + inner + "'"
        if kind == 6:
            return "`" + inner + "`"
        if kind == 7:
            return inner + rng.choice(separators) + build(depth - 1)
        if kind == 8:
            return (
                "cat <<E" + rng.choice(["; ", " ", "\n"]) + inner
                + rng.choice(["\nbody\nE\n", "\nE\n", "\n"])
            )
        if kind == 9:
            return inner + "\nbody\nE\n"
        if kind == 10:
            return "x=" + inner
        if kind == 11:
            return "${" + inner + "}"
        if kind == 12:
            return "$[" + inner + "]"
        if kind == 13:
            return "$'" + inner + "'"
        if kind == 14:
            return "$((" + inner + ")" + build(depth - 1) + ")"
        if kind == 15:
            return "((" + inner + ")" + build(depth - 1) + ")"
        if kind == 16:
            return "<<E\n" + inner
        return inner + " <<-E"

    forms = []
    for _ in range(count):
        text = build(rng.randint(1, 5))
        if text and rng.random() < 0.3:
            pos = rng.randrange(len(text))
            if rng.random() < 0.5:
                text = text[:pos] + text[pos + 1 :]
            else:
                text = text[:pos] + rng.choice(["(", ")", "\n", '"', "'", "$", "`", "\\"]) + text[pos:]
        forms.append(text)
    return forms


class TestNonAdjacentCloseRereading(unittest.TestCase):
    """A `((` / `$((` whose first close is a lone `)` is read as two
    parentheses without reading the whole text again for every such opener:
    the lexical map stays what the whole-text restart gives, the work stays
    linear, and a bound overflow is an ask, never an allow."""

    def check_same_reading(self, text, mode="shell", bodies=True):
        # A fresh lexing: the memo shares the map of a text lexed with its
        # bodies as that of the same text lexed without, which is a different
        # question from the one asked here.
        H._LEX_CACHE.clear()
        got = lexical_reading(H.lex_shell(text, mode, bodies))
        want = whole_text_restart_reading(text, mode, bodies)
        self.assertEqual(got, want, msg=repr(text))

    def test_the_review_inputs_sit_in_the_case_table_after_the_base_entries(self):
        # AC-1, AC-7: located by label and command text, never by a fixed index.
        cases = case_commands()
        for name, form in NON_ADJACENT_FORMS.items():
            with self.subTest(form=name):
                found = [
                    i
                    for i, (_want, label, cmd) in enumerate(cases)
                    if cmd == form and label.startswith(NON_ADJACENT_STABLE_ID)
                ]
                self.assertEqual(len(found), 1)
                self.assertGreaterEqual(found[0], 627)
                self.assertEqual(cases[found[0]][0], "allow")
        # No entry of the first 627 carries this finding's stable_id.
        for _want, label, _cmd in cases[:627]:
            self.assertNotIn(NON_ADJACENT_STABLE_ID, label)

    def test_the_entries_present_at_the_feature_base_are_unchanged(self):
        # AC-7 (FR8): none of the 627 entries of the feature base is removed,
        # edited or reordered; the digest is that of their JSON text.
        cases = case_commands()
        self.assertGreaterEqual(len(cases), 627)
        digest = hashlib.sha256(
            json.dumps(cases[:627], ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        self.assertEqual(digest, BASE_ENTRIES_DIGEST)

    def test_the_review_inputs_get_allow_with_and_without_batch(self):
        # AC-2 (FR5, TM-4)
        for name, form in NON_ADJACENT_FORMS.items():
            for batch in (False, True):
                with self.subTest(form=name, batch=batch):
                    decision, reason = hook_verdict(form, batch=batch)
                    self.assertEqual(decision, "allow", msg=reason[:200])

    def test_every_known_command_reads_as_the_whole_text_restart_reads_it(self):
        # AC-4: the case table and every fixed form of this module, in each
        # mode the hook reads a chunk in.
        for command in all_commands():
            with self.subTest(command=command[:80]):
                self.check_same_reading(command, "shell", True)
                self.check_same_reading(command, "shell", False)
                self.check_same_reading(command, "heredoc-body", False)

    def test_generated_forms_read_as_the_whole_text_restart_reads_them(self):
        for command in generated_forms(4000):
            with self.subTest(command=command):
                self.check_same_reading(command, "shell", True)
                self.check_same_reading(command, "heredoc-body", False)

    def test_nested_generated_forms_read_as_the_whole_text_restart_reads_them(self):
        # Nested openers with here-document operators pending, registered and
        # taking their bodies inside the spans that are read twice.
        for command in nested_forms(3000):
            with self.subTest(command=command):
                self.check_same_reading(command, "shell", True)
                self.check_same_reading(command, "shell", False)
                self.check_same_reading(command, "heredoc-body", False)

    def test_a_candidate_inside_a_span_that_is_read_twice_is_listed_once(self):
        text = "echo $(( $(echo 'a$(b)') ) | cat)"
        lexmap = H.lex_shell(text)
        self.assertEqual([text[c.start : c.end] for c in lexmap.candidates], ["$(b)"])
        self.check_same_reading(text)

    def test_nested_quoted_and_here_document_pending_forms_have_these_maps(self):
        # AC-4: hand-written expectations (D6), and the same map after the
        # lexer cache is cleared.
        for text, regions, heredocs in NON_ADJACENT_MAP_FORMS:
            with self.subTest(text=text):
                first = H.lex_shell(text)
                self.assertEqual(
                    actual_regions(first), expected_regions(text, regions), msg=repr(text)
                )
                got = [(op.delimiter, op.quoted, heredoc_body(text, op)) for op in first.heredocs]
                self.assertEqual(got, heredocs, msg=repr(text))
                self.assertEqual(list(first.unopened), [])
                self.assertIsNone(first.tail_start)
                self.check_same_reading(text)
                H._LEX_CACHE.clear()
                second = H.lex_shell(text)
                self.assertIsNot(first, second)
                self.assertEqual(first.as_tuple(), second.as_tuple())

    def test_a_roughly_60kb_input_gets_allow_within_the_time_limit(self):
        # AC-5 (NFR2)
        lines = []
        size = 0
        while size < 60000:
            line = "x=$((echo %d) | wc -c)" % len(lines)
            lines.append(line)
            size += len(line) + 1
        command = "\n".join(lines)
        self.assertGreater(len(command), 50000)
        start = time.monotonic()
        decision, reason = hook_verdict(command)
        self.assertEqual(decision, "allow", msg=reason[:200])
        self.assertLess(time.monotonic() - start, GUARD_TIMEOUT_SECONDS)

    def run_hook_in_process(self, command, batch):
        """H.run() with the payload on a substituted stdin and the batch
        variable set or cleared; returns (decision, exit code)."""
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        out = io.StringIO()
        with mock.patch.dict(os.environ):
            os.environ.pop("CLAUDE_BATCH", None)
            if batch:
                os.environ["CLAUDE_BATCH"] = "1"
            with mock.patch.object(sys, "stdin", io.StringIO(payload)):
                with mock.patch.object(sys, "stdout", out):
                    with self.assertRaises(SystemExit) as exit_info:
                        H.run()
        decision = json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"]
        return decision, exit_info.exception.code

    def test_exceeding_the_work_bound_is_an_ask_never_an_allow(self):
        # AC-6 (NFR3, TM-4): the same input is within its bound under the
        # real work factor and exceeds it under a lowered one.
        command = expansion_lines(200)
        self.addCleanup(H._LEX_CACHE.clear)
        H._LEX_CACHE.clear()
        normal = H.lex_shell(command)
        self.assertLessEqual(normal.work, H.LEX_WORK_FACTOR * len(command) + 1024)
        self.assertGreater(normal.work, 1024)
        self.assertEqual(self.run_hook_in_process(command, batch=False), ("allow", 0))
        with mock.patch.object(H, "LEX_WORK_FACTOR", 0):
            H._LEX_CACHE.clear()
            with self.assertRaises(H.LexBudgetExceeded):
                H.lex_shell(command)
            H._LEX_CACHE.clear()
            self.assertEqual(self.run_hook_in_process(command, batch=False), ("ask", 0))
            H._LEX_CACHE.clear()
            self.assertEqual(self.run_hook_in_process(command, batch=True), ("deny", 0))


# ---------------------------------------------------------------------------
# Module contract (AC-3, AC-9).
# ---------------------------------------------------------------------------


# The stable_ids of the four round 2 residual findings and the length of the
# case table at the feature base (indexes 0-626).
ROUND2_STABLE_IDS = (
    "453963d025537b11",
    "681fab61e1d9ff2c",
    "9381769d7116fab2",
    "29bbf9032dd762a0",
)
ROUND2_BASE_CASE_COUNT = 627


class TestModuleContract(unittest.TestCase):
    def test_replaced_readers_are_gone(self):
        self.assertFalse(hasattr(H, "_OperatorContext"))
        self.assertFalse(hasattr(H, "_blank_comments"))
        with open(HOOK, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("class _OperatorContext", source)
        self.assertNotIn("def _blank_comments", source)

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

    def test_lexer_reads_no_file_and_evaluates_nothing(self):
        with open(HOOK, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        forbidden = {"open", "eval", "exec", "compile", "__import__"}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and (
                node.name.startswith("lex_")
                or node.name.startswith("_lex")
                or node.name in ("scan_structure", "strip_heredocs", "_strip_heredocs_mapped")
            ):
                for call in ast.walk(node):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                        self.assertNotIn(call.func.id, forbidden, msg=node.name)
                    if isinstance(call, ast.Attribute):
                        self.assertNotIn(call.attr, {"system", "popen", "run", "Popen"}, msg=node.name)

    def test_existing_cases_stay_in_place_and_new_ones_come_after(self):
        cases = case_commands()
        self.assertGreaterEqual(len(cases), 604)
        verdicts = [want for want, _label, _cmd in cases[574:604]]
        self.assertEqual(verdicts.count("allow"), 2)
        self.assertEqual(verdicts[11], "allow")
        self.assertEqual(verdicts[19], "allow")
        self.assertEqual(verdicts.count("deny"), 28)

    def test_rework_cases_are_appended_after_every_earlier_entry(self):
        # task0002 appends 23 cases after the 604 entries that exist at its
        # base: 19, 22 and 23 (indexes 18, 21, 22 of the new block) allow,
        # every other one denies; each label cites its finding's stable_id.
        cases = case_commands()
        self.assertGreaterEqual(len(cases), 627)
        block = cases[604:627]
        verdicts = [want for want, _label, _cmd in block]
        self.assertEqual(
            [i for i, want in enumerate(verdicts) if want == "allow"], [18, 21, 22]
        )
        self.assertEqual(verdicts.count("deny"), 20)
        finding_of = (
            ["42180fe3cd060309"] * 13
            + ["6ad3de37b64392ec"] * 6
            + ["acf9e8aa8bb287ea"] * 4
        )
        for (_want, label, _cmd), finding in zip(block, finding_of):
            self.assertIn(finding, label)
        self.assertEqual(block[0][2], "if (true) then ((1<<2)); fi" + TAIL)
        self.assertEqual(block[22][2], "cat <(true) #; rm -rf /home/sakura/valuable")

    def test_round2_cases_come_only_after_the_base_entries(self):
        # D3: the order of the four round 2 blocks depends on merge order, so
        # this holds whichever of them are present. No label below the base
        # length cites a round 2 finding, and every case of task0001 is found
        # by its label and command text at the base length or later.
        cases = case_commands()
        self.assertGreaterEqual(len(cases), ROUND2_BASE_CASE_COUNT)
        for index, (_want, label, _cmd) in enumerate(cases[:ROUND2_BASE_CASE_COUNT]):
            for stable_id in ROUND2_STABLE_IDS:
                self.assertNotIn(stable_id, label, msg="index %d" % index)
        for finding, form in ROUND2_COMMAND_POSITION_CASES:
            with self.subTest(form=form):
                located = [
                    index
                    for index, (want, label, cmd) in enumerate(cases)
                    if cmd == form + TAIL and want == "deny" and finding in label
                ]
                self.assertEqual(len(located), 1)
                self.assertGreaterEqual(located[0], ROUND2_BASE_CASE_COUNT)


if __name__ == "__main__":
    unittest.main()
