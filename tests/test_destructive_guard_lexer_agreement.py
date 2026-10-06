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
- TestTimeOptions: `time -p` takes no second `-p` as an option; the word is
  the command word (review round 1, finding 48e1f462b0dd164f).
- TestStageAgreement: the stage agreement properties (a)-(f) over every
  cases.json command, every attack form, every benign control and every fixed
  form.
- TestPositionMap: the position-map contract, including a marker longer than
  the substitution it replaces.
- TestSubstitutionPolicies: the three substitution searches stay distinct.
- TestArraySubscripts: the array subscript of an assignment word is one
  region and registers no here-document operator; an unclosed one is settled
  (round 2 residuals, task0002).
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
- TestResumeSnapshot: the state a non-adjacent-close resume saves and restores
  is one named snapshot type over one pass-state record, every field of the
  record is classified, and the pass returns the openers it newly reads as two
  parentheses instead of changing the set it was given (rework round 1,
  task0007, finding 956849b341a5150b).
- TestModuleContract: the replaced readers are gone; standard library only.
- TestArraySubscriptAndExtglobReadings, TestStageAgreementUnderExtglobOn
  (destructive-guard-heredoc-syntax-error task0002, P14): array subscripts,
  eval / let / alias arrays, and the two readings of an extended-glob
  parenthesis inside an array, read by the lexer and by its consumers.

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

BRACE_KIND = "brace-command-substitution"
SUBSTITUTION_KINDS = frozenset(
    {
        "command-substitution",
        "backtick-substitution",
        "process-substitution",
        BRACE_KIND,
    }
)
QUOTE_KINDS = frozenset({"single-quote", "double-quote", "ansi-c-quote", "locale-quote"})
OPAQUE_KINDS = QUOTE_KINDS | SUBSTITUTION_KINDS | frozenset(
    {
        "comment",
        "parameter-expansion",
        "arithmetic-expansion",
        "bracket-arithmetic",
        "arithmetic-command",
        "array-subscript",
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
        "array-subscript",
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

# `time` options as bash 5.3 reads them (review round 1, task0006, finding
# 48e1f462b0dd164f). Directly after `time`, `-p` and `--` are options;
# directly after `time -p`, only `--` is. A second `-p` is therefore the
# command word: it ends the command position, so the `a[1<<2]=x` after it is
# an argument and its `<<` a real here-document operator (bash reports `-p` as
# not found and closes the body at the line `2]=x`).
TIME_P_REPEATED_FORM = "time -p -p a[1<<2]=x"
# The same form followed by a body line `'`, its close line and a destructive
# line: the command text of this task's case-table entry.
TIME_P_REPEATED_CASE = TIME_P_REPEATED_FORM + "\n'\n2]=x\nrm -rf /home/sakura/valuable\n'"
# Where the command word is not at a command position, so the `((` after it
# opens no arithmetic command (bash rejects the line; only the lexical reading
# is pinned, as for TIME_OPTION_END_FORMS).
TIME_P_REPEATED_ARITHMETIC_FORM = "time -p -p ((1<<2))"
# One `-p`, or `--`, before the assignment word: it is still at a command
# position, `a[1<<2]` is a subscript and no operator is registered.
TIME_OPTION_SUBSCRIPT_FORMS = [
    "time -p a[1<<2]=x",
    "time -- a[1<<2]=x",
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
# `time` options (review round 1, task0006, finding 48e1f462b0dd164f).
# ---------------------------------------------------------------------------

# Every case this task appends to the case table begins its label with this.
TIME_OPTION_LABEL = "48e1f462b0dd164f round2-residuals "
TIME_OPTION_CASE_FLOOR = 627


def array_subscript_regions(lexmap):
    return sorted((r.start, r.end) for r in lexmap.regions if r.kind == "array-subscript")


class TestTimeOptions(unittest.TestCase):
    def test_a_second_p_after_time_p_is_the_command_word_and_the_operator_is_real(self):
        # AC-2, AC-3: `-p` after `time -p` is no option, so `a[1<<2]=x` is an
        # argument: no subscript region, one here-document operator at its
        # `<<` that takes the body `'` and closes at `2]=x`.
        text = TIME_P_REPEATED_CASE
        lexmap = H.lex_shell(text)
        self.assertEqual(array_subscript_regions(lexmap), [])
        self.assertEqual(len(lexmap.heredocs), 1)
        op = lexmap.heredocs[0]
        self.assertEqual(op.start, text.index("<<"))
        self.assertEqual((op.delimiter, op.quoted), ("2]=x", False))
        self.assertEqual(heredoc_body(text, op), "'\n")
        self.assertEqual(text[op.body_end : op.close_end], "2]=x\n")

    def test_the_same_form_with_the_shared_tail_registers_the_operator_too(self):
        text = TIME_P_REPEATED_FORM + TAIL
        lexmap = H.lex_shell(text)
        self.assertEqual(array_subscript_regions(lexmap), [])
        self.assertEqual([(op.delimiter, op.quoted) for op in lexmap.heredocs], [("2]=x", False)])

    def test_a_second_p_after_time_p_ends_the_command_position(self):
        # AC-3: the `((` after the command word `-p` is not at a command
        # position, so it is no arithmetic command.
        text = TIME_P_REPEATED_ARITHMETIC_FORM + TAIL
        lexmap = H.lex_shell(text)
        self.assertNotIn("arithmetic-command", [r.kind for r in lexmap.regions])
        self.assertEqual(actual_regions(lexmap), [])

    def test_one_p_or_a_double_dash_keeps_the_subscript_and_registers_no_operator(self):
        # AC-3: the assignment word is still at a command position.
        for form in TIME_OPTION_SUBSCRIPT_FORMS:
            with self.subTest(form=form):
                text = form + TAIL
                lexmap = H.lex_shell(text)
                self.assertEqual(lexmap.heredocs, [])
                self.assertEqual(array_subscript_regions(lexmap), [span_of(text, "[1<<2]")])
                self.assertIsNone(lexmap.tail_start)

    def test_the_repeated_p_case_is_denied_in_both_modes(self):
        # AC-2: without and with CLAUDE_BATCH, an unattended run is not let
        # through either.
        for batch in (False, True):
            with self.subTest(batch=batch):
                got, reason = hook_verdict(TIME_P_REPEATED_CASE, batch=batch)
                self.assertEqual(
                    got,
                    "deny",
                    msg="%r batch=%s -> %s %s" % (TIME_P_REPEATED_CASE, batch, got, reason),
                )

    def test_the_subscript_forms_still_deny_the_destructive_tail_in_both_modes(self):
        for form in TIME_OPTION_SUBSCRIPT_FORMS:
            for batch in (False, True):
                with self.subTest(form=form, batch=batch):
                    got, reason = hook_verdict(form + TAIL, batch=batch)
                    self.assertEqual(got, "deny", msg="%r -> %s %s" % (form, got, reason))

    def test_the_case_is_in_the_case_table_after_the_base_entries(self):
        # AC-1, AC-6: found by label and command text, never by a fixed
        # index; it comes after the 627 entries that exist at the feature
        # base, and only one entry carries it.
        located = [
            (index, want)
            for index, (want, label, cmd) in enumerate(case_commands())
            if cmd == TIME_P_REPEATED_CASE and label.startswith(TIME_OPTION_LABEL)
        ]
        self.assertEqual(len(located), 1)
        self.assertGreaterEqual(located[0][0], TIME_OPTION_CASE_FLOOR)
        self.assertEqual(located[0][1], "deny")


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
        quote characters of a quoted here-document delimiter that is not
        inside a marked substitution either (the marker residue that stands
        for the substitution holds neither: they belong to its own chunk)."""
        ranges = [
            (r.start, r.end)
            for i, r in enumerate(self.lex_s.regions)
            if r.kind in QUOTE_KINDS and not self.has_closed_substitution_ancestor(i)
        ]
        closed_substitutions = [
            r
            for r in self.lex_s.regions
            if r.kind in SUBSTITUTION_KINDS and r.closed
        ]
        for op in self.lex_s.heredocs:
            if op.quoted and not self.in_region(closed_substitutions, op.start):
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
    for form in (
        TIME_P_REPEATED_FORM,
        TIME_P_REPEATED_ARITHMETIC_FORM,
        *TIME_OPTION_SUBSCRIPT_FORMS,
    ):
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
    # A command beyond the lexer's work bound is not read by any stage (the
    # hook answers it with the scan-budget ask, which the case table pins), so
    # there is no map to compare the stages against.
    return [command for command in commands if _lexer_reads(command)]


def _lexer_reads(command):
    try:
        H.lex_shell(command, "shell")
    except H.LexBudgetExceeded:
        return False
    return True


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
                try:
                    got = H.tokens(segment)
                except H.LexBudgetExceeded:
                    # A split that cuts a subscript read across lines leaves
                    # a fragment with an unmatched `[`: the lexer cannot
                    # settle it (P14), and the hook answers such a text with
                    # an `ask`, never with tokens.
                    continue
                for word in got:
                    for ch in word:
                        if 0xE000 <= ord(ch) <= 0xF8FF:
                            self.assertIn(ch, a.command)
                lexmap = H.lex_shell(segment)
                if any(r.kind in HIDDEN_KINDS for r in lexmap.regions) or "#" in segment:
                    continue
                if any(segment[pos] in "'\"" for pos in lexmap.unopened):
                    # A tail source left a quote character literal (task0005):
                    # the masked view hides it from shlex, which would open a
                    # quote there; shlex.split() on the bare text would not
                    # read the word the lexer reads.
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
# Array subscript of an assignment word (round 2 residuals, task0002, FR3).
# ---------------------------------------------------------------------------

# Every case this task appends to the case table begins its label with this.
SUBSCRIPT_LABEL = "9381769d7116fab2 round2-residuals FR3."
SUBSCRIPT_CASE_FLOOR = 627

# (command, the subscript literal): bash 5.3 reads `name[` through its
# matching `]` at each of these positions, so the lexer reports the literal
# as one array-subscript region and registers no here-document operator.
SUBSCRIPT_FORMS = [
    ("a[1<<2]=x", "[1<<2]"),
    ("x=1 a[1<<2]=y", "[1<<2]"),
    ("x=1 y=2 a[1<<2]=y", "[1<<2]"),
    ("x=$(echo 1) a[1<<2]=y", "[1<<2]"),
    ('x="1" a[1<<2]=y', "[1<<2]"),
    ("a[1<<2]+=x", "[1<<2]"),
    ("a[1<<2]", "[1<<2]"),
    ("a[1<<2]x=y", "[1<<2]"),
    ("a[ 1 << 2 ]=x", "[ 1 << 2 ]"),
    ("a[b[1]<<2]=x", "[b[1]<<2]"),
    ("a[b[1<<2]]=x", "[b[1<<2]]"),
    ('a["1"<<2]=x', '["1"<<2]'),
    ("a['k]'<<2]=x", "['k]'<<2]"),
    ('a["]"<<2]=x', '["]"<<2]'),
    ("a[$(echo 1)<<2]=x", "[$(echo 1)<<2]"),
    ("a[$(echo ])<<2]=x", "[$(echo ])<<2]"),
    ("a[`echo 1`<<2]=x", "[`echo 1`<<2]"),
    ("a[${x:-1}<<2]=x", "[${x:-1}<<2]"),
    ("a[$((1))<<2]=x", "[$((1))<<2]"),
    ("a[(1<<2)]=x", "[(1<<2)]"),
    ("a[\\]<<2]=x", "[\\]<<2]"),
    ("x=$(a[1<<2]=x)", "[1<<2]"),
    ("echo $(a[1<<2]=x)", "[1<<2]"),
    ("`a[1<<2]=x`", "[1<<2]"),
    ("cat <(a[1<<2]=x)", "[1<<2]"),
    ("{ a[1<<2]=y; }", "[1<<2]"),
    ("(a[1<<2]=y)", "[1<<2]"),
    ("echo hi; a[1<<2]=y", "[1<<2]"),
    ("echo hi | a[1<<2]=y", "[1<<2]"),
    ("echo hi && a[1<<2]=y", "[1<<2]"),
    ("echo hi & a[1<<2]=y", "[1<<2]"),
    ("echo hi\na[1<<2]=y", "[1<<2]"),
    ("if a[1<<2]=y; then :; fi", "[1<<2]"),
    ("if :; then a[1<<2]=y; fi", "[1<<2]"),
    ("while ! a[1<<2]=y; do :; done", "[1<<2]"),
    ("for i in 1; do a[1<<2]=y; done", "[1<<2]"),
    ("case x in x) a[1<<2]=y;; esac", "[1<<2]"),
    ("f() { a[1<<2]=y; }", "[1<<2]"),
    ("time a[1<<2]=y", "[1<<2]"),
    ("time -p a[1<<2]=y", "[1<<2]"),
    ("! a[1<<2]=y", "[1<<2]"),
    ("coproc a[1<<2]=y", "[1<<2]"),
    ("a[1]=1 b[1<<2]=y", "[1<<2]"),
    ("a[1]+=1 b[1<<2]=y", "[1<<2]"),
    (">/dev/null a[1<<2]=y", "[1<<2]"),
    ("</dev/null a[1<<2]=y", "[1<<2]"),
    ("2>/dev/null a[1<<2]=y", "[1<<2]"),
    ("12>/dev/null a[1<<2]=y", "[1<<2]"),
    ("{fd}>/dev/null a[1<<2]=y", "[1<<2]"),
    ("> /dev/null a[1<<2]=y", "[1<<2]"),
    (">&2 a[1<<2]=y", "[1<<2]"),
    ("2>&1 a[1<<2]=y", "[1<<2]"),
    ("&>/dev/null a[1<<2]=y", "[1<<2]"),
    ("<<<x a[1<<2]=y", "[1<<2]"),
    (">/dev/null 2>/dev/null a[1<<2]=y", "[1<<2]"),
    (">/dev/null x=1 a[1<<2]=y", "[1<<2]"),
    ("time >/dev/null a[1<<2]=y", "[1<<2]"),
    ("! >/dev/null a[1<<2]=y", "[1<<2]"),
    ("echo hi; >/dev/null a[1<<2]=y", "[1<<2]"),
]

# bash 5.3 registers the `<<` of each of these as a here-document operator:
# the word is an argument, or the assignment position was lost, or the word is
# not an identifier followed by `[`. The lexer keeps its reading: one operator
# and no array-subscript region.
SUBSCRIPT_ARGUMENT_FORMS = [
    "echo a[1<<2]",
    "echo a[1<<2]=x",
    "echo hi; echo a[1<<2]",
    "x=1 echo a[1<<2]",
    "x=1 echo a[1<<2]=y",
    "declare a[1<<2]=x",
    "declare -a a[1<<2]=x",
    "local a[1<<2]=x",
    "export a[1<<2]=x",
    "readonly a[1<<2]=x",
    "typeset a[1<<2]=x",
    "x=1 declare a[1<<2]=y",
    "a b[1<<2]=y",
    "1a[1<<2]=y",
    "a-b[1<<2]=y",
    "a.b[1<<2]=y",
    "x=a[1<<2]",
    ">/dev/null echo a[1<<2]=y",
    "echo hi >/dev/null a[1<<2]=y",
    "x=1 >/dev/null a[1<<2]=y",
    "x=1 2>&1 a[1<<2]=y",
    ">/dev/null x=1 >/dev/null a[1<<2]=y",
    ">/dev/null time a[1<<2]=y",
    "echo $(( 1 )) a[1<<2]=y",
]

# (command, the subscript literal). bash 5.3 reads a subscript across lines to
# its matching `]` (P14 of destructive-guard-heredoc-syntax-error): one
# array-subscript region over the lines, no operator and no comment in it.
SUBSCRIPT_MULTILINE_FORMS = [
    ("a[1<<2\n]=x" + TAIL, "[1<<2\n]"),
    ("a[1<<2 # ; rm -rf /home/sakura/valuable\n]=x", "[1<<2 # ; rm -rf /home/sakura/valuable\n]"),
    ("a[$(echo 1\n)<<2]=x" + TAIL, "[$(echo 1\n)<<2]"),
    ('a["1\n"<<2]=x' + TAIL, '["1\n"<<2]'),
]

# A subscript whose `]` never comes: bash keeps reading for it to the end of
# the text and runs none of the lines it took in. The lexer raises
# LexUnmatchedSubscript, which the hook answers with an `ask` (a `deny` in a
# batch run), never an `allow`.
SUBSCRIPT_UNCLOSED_FORMS = [
    "a[1<<2\nrm -rf /home/sakura/valuable\n2",
    "a[1<<2",
    "a[1 # ; rm -rf /home/sakura/valuable",
    "x=1 a[1<<2\nrm -rf /home/sakura/valuable\n2",
    "echo $(a[1<<2\nrm -rf /home/sakura/valuable\n2\n)",
    "a[1<<2]=x\nb[3<<4\nrm -rf /home/sakura/valuable\n4",
]


def subscript_regions(lexmap):
    return sorted((r.start, r.end) for r in lexmap.regions if r.kind == "array-subscript")


def subscript_cases():
    """The cases this task appended, with their index, found by label."""
    return [
        (index, want, label, cmd)
        for index, (want, label, cmd) in enumerate(case_commands())
        if label.startswith(SUBSCRIPT_LABEL)
    ]


class TestArraySubscripts(unittest.TestCase):
    def test_subscript_of_an_assignment_word_is_one_region_and_no_operator(self):
        command = "a[1<<2]=x" + TAIL
        lexmap = H.lex_shell(command)
        self.assertEqual(lexmap.heredocs, [])
        self.assertEqual(actual_regions(lexmap), [("array-subscript", 1, 7)])
        self.assertEqual(command[1:7], "[1<<2]")
        self.assertEqual(lexmap.unopened, [])
        self.assertIsNone(lexmap.tail_start)
        self.assertEqual(hook_verdict(command)[0], "deny")
        self.assertEqual(hook_verdict(command, batch=True)[0], "deny")

    def test_each_subscript_form_is_one_region_with_no_operator(self):
        for command, literal in SUBSCRIPT_FORMS:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command + TAIL)
                self.assertEqual(lexmap.heredocs, [])
                found = subscript_regions(lexmap)
                for n in range(command.count(literal)):
                    self.assertIn(span_of(command, literal, n), found)
                self.assertIsNone(lexmap.tail_start)
                self.assertEqual(lexmap.unopened, [])

    def test_each_subscript_form_denies_the_destructive_tail_in_both_modes(self):
        for command, _literal in SUBSCRIPT_FORMS:
            with self.subTest(command=command):
                self.assertEqual(hook_verdict(command + TAIL)[0], "deny")
                self.assertEqual(hook_verdict(command + TAIL, batch=True)[0], "deny")

    def test_a_subscript_nests_only_what_it_holds(self):
        command = "a[b[1]<<2]=x" + TAIL
        lexmap = H.lex_shell(command)
        self.assertEqual(subscript_regions(lexmap), [span_of(command, "[b[1]<<2]")])
        command = 'a["1"<<2]=x' + TAIL
        lexmap = H.lex_shell(command)
        self.assertEqual(
            actual_regions(lexmap),
            expected_regions(
                command, [("array-subscript", '["1"<<2]'), ("double-quote", '"1"')]
            ),
        )
        command = "a[$(echo 1)<<2]=x" + TAIL
        lexmap = H.lex_shell(command)
        self.assertEqual(
            actual_regions(lexmap),
            expected_regions(
                command,
                [("array-subscript", "[$(echo 1)<<2]"), ("command-substitution", "$(echo 1)")],
            ),
        )

    def test_a_closer_inside_a_quote_or_substitution_does_not_close_the_subscript(self):
        for command, literal in (
            ("a['k]'<<2]=x", "['k]'<<2]"),
            ('a["]"<<2]=x', '["]"<<2]'),
            ("a[$(echo ])<<2]=x", "[$(echo ])<<2]"),
            ("a[`echo ]`<<2]=x", "[`echo ]`<<2]"),
            ("a[${x:-]}<<2]=x", "[${x:-]}<<2]"),
            ("a[\\]<<2]=x", "[\\]<<2]"),
        ):
            with self.subTest(command=command):
                lexmap = H.lex_shell(command + TAIL)
                self.assertEqual(subscript_regions(lexmap), [span_of(command, literal)])
                self.assertEqual(lexmap.heredocs, [])

    def test_a_here_document_operator_after_the_closing_bracket_is_real(self):
        command = "a[1] <<EOF\nhi\nEOF"
        lexmap = H.lex_shell(command)
        self.assertEqual(subscript_regions(lexmap), [span_of(command, "[1]")])
        self.assertEqual(len(lexmap.heredocs), 1)
        self.assertEqual(lexmap.heredocs[0].delimiter, "EOF")
        self.assertEqual(heredoc_body(command, lexmap.heredocs[0]), "hi\n")
        command = "a[1]<<EOF\nhi\nEOF"
        lexmap = H.lex_shell(command)
        self.assertEqual(subscript_regions(lexmap), [span_of(command, "[1]")])
        self.assertEqual(len(lexmap.heredocs), 1)
        self.assertEqual(lexmap.heredocs[0].delimiter, "EOF")
        command = "a[$(echo 1)]<<EOF\nhi\nEOF"
        lexmap = H.lex_shell(command)
        self.assertEqual(len(lexmap.heredocs), 1)

    def test_the_masked_view_hides_the_subscript_from_the_word_splitter(self):
        for command in ("a[1<<2]=x", "a[1<<2]+=x", "x=1 a[1<<2]=y", "a[b[1]<<2]=x"):
            with self.subTest(command=command):
                toks = H._tokenize_marked(H._MarkedText.plain(command))
                self.assertEqual([str(t) for t, _s, _e in toks], command.split())
                self.assertFalse(any(t.is_operator for t, _s, _e in toks))

    def test_separators_and_blanks_inside_a_subscript_stay_in_one_word(self):
        # bash reads the whole matched pair as part of the word: nothing in it
        # splits the word or starts a statement.
        for command in ("a[ 1 << 2 ]=x", "a[1;2]=x", "a[1|2]=x", "a[(1)]=x", "a[1 && 2]=x"):
            with self.subTest(command=command):
                toks = H._tokenize_marked(H._MarkedText.plain(command))
                self.assertEqual([str(t) for t, _s, _e in toks], [command])
                self.assertFalse(any(t.is_operator for t, _s, _e in toks))
                self.assertEqual(len(H.lex_segments(command)), 1)

    def test_a_substitution_inside_a_subscript_is_still_inspected(self):
        for command in (
            "a[$(rm -rf /home/sakura/valuable)]=x",
            "x=1 a[`rm -rf /home/sakura/valuable`]=x",
            "a[$(rm -rf /home/sakura/valuable)<<2]=x",
        ):
            with self.subTest(command=command):
                self.assertEqual(hook_verdict(command)[0], "deny")
                self.assertEqual(hook_verdict(command, batch=True)[0], "deny")

    def test_the_heredoc_body_top_level_reads_no_subscript(self):
        lexmap = H.lex_shell("a[1<<2]=x", "heredoc-body")
        self.assertEqual(subscript_regions(lexmap), [])

    # AC-4: argument-position reading is unchanged.
    def test_argument_position_reading_keeps_its_operator(self):
        for command in SUBSCRIPT_ARGUMENT_FORMS:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command + TAIL)
                self.assertEqual(subscript_regions(lexmap), [])
                self.assertEqual(len(lexmap.heredocs), 1)
                self.assertIsNone(lexmap.tail_start)

    def test_a_subscript_word_that_is_no_assignment_ends_the_assignment_position(self):
        command = "a[1] b[1<<2]=y" + TAIL
        lexmap = H.lex_shell(command)
        self.assertEqual(subscript_regions(lexmap), [span_of(command, "[1]")])
        self.assertEqual(len(lexmap.heredocs), 1)
        self.assertEqual(lexmap.heredocs[0].start, command.index("<<"))

    def test_the_existing_context_form_cat_a1_heredoc_is_unchanged(self):
        command = "cat a[1] <<EOF\nhi\nEOF"
        lexmap = H.lex_shell(command)
        self.assertEqual(actual_regions(lexmap), [])
        self.assertEqual(len(lexmap.heredocs), 1)
        op = lexmap.heredocs[0]
        self.assertEqual((op.delimiter, op.quoted), ("EOF", False))
        self.assertEqual(heredoc_body(command, op), "hi\n")
        self.assertEqual(hook_verdict(command)[0], "allow")

    def test_echo_a_subscript_still_registers_the_operator(self):
        command = "echo a[1<<2]"
        lexmap = H.lex_shell(command)
        self.assertEqual(len(lexmap.heredocs), 1)
        self.assertEqual(lexmap.heredocs[0].start, command.index("<<"))
        self.assertEqual(subscript_regions(lexmap), [])

    def test_declaration_builtin_arguments_keep_the_operator(self):
        # bash 5.3 registers the `<<` of `declare a[1<<2]=x` and of the other
        # declaration builtins as a here-document operator.
        for word in ("declare", "local", "export", "readonly", "typeset"):
            command = "%s a[1<<2]=x" % word + TAIL
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(len(lexmap.heredocs), 1)
                self.assertEqual(subscript_regions(lexmap), [])

    # AC-5: a subscript that closes on a later line is read across the lines;
    # one that never closes is no reading the hook allows.
    def test_a_subscript_closing_on_a_later_line_is_one_region(self):
        for command, literal in SUBSCRIPT_MULTILINE_FORMS:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(subscript_regions(lexmap), [span_of(command, literal)])
                self.assertEqual(lexmap.heredocs, [])
                self.assertIsNone(lexmap.tail_start)
                self.assertFalse(any(r.kind == "comment" for r in lexmap.regions))

    def test_a_destructive_line_after_a_multiline_subscript_is_denied(self):
        for command, _literal in SUBSCRIPT_MULTILINE_FORMS:
            if not command.endswith(TAIL):
                continue
            with self.subTest(command=command):
                self.assertEqual(hook_verdict(command)[0], "deny")
                self.assertEqual(hook_verdict(command, batch=True)[0], "deny")

    def test_an_unclosed_subscript_is_never_allowed(self):
        for command in SUBSCRIPT_UNCLOSED_FORMS:
            with self.subTest(command=command):
                H._LEX_CACHE.clear()
                with self.assertRaises(H.LexUnmatchedSubscript):
                    H.lex_shell(command)
                self.assertEqual(hook_verdict(command)[0], "ask")
                self.assertEqual(hook_verdict(command, batch=True)[0], "deny")

    def test_no_subscript_is_read_after_the_tail_start(self):
        command = "echo ${x\na[1<<2]=y\nrm -rf /home/sakura/valuable\n2"
        lexmap = H.lex_shell(command)
        self.assertEqual(subscript_regions(lexmap), [])
        self.assertEqual(lexmap.heredocs, [])
        self.assertEqual(lexmap.tail_start, command.index("${"))
        self.assertEqual(hook_verdict(command)[0], "deny")

    def test_the_same_command_gives_an_identical_map(self):
        for command in ("a[1<<2]=x" + TAIL, "a[1<<2\n]=x" + TAIL):
            with self.subTest(command=command):
                first = H.lex_shell(command)
                H._LEX_CACHE.clear()
                second = H.lex_shell(command)
                self.assertIsNot(first, second)
                self.assertEqual(first.as_tuple(), second.as_tuple())

    # AC-6: linear work for closed subscripts, on one line or across lines.
    def test_lexing_work_is_linear_for_closed_and_multiline_subscripts(self):
        for unit in ("a[1<<2]=x\n", "a[\n]=x\n"):
            with self.subTest(unit=unit):
                small = H.lex_shell(unit * 200)
                large = H.lex_shell(unit * 400)
                self.assertLessEqual(large.work, 2.5 * small.work + 100)
                self.assertLessEqual(large.work, H.LEX_WORK_FACTOR * len(unit * 400) + 1024)

    def test_many_unclosed_subscripts_end_in_one_reading(self):
        # The first `[` takes in the rest of the text: one pass reaches its
        # end and raises, however many there are.
        for count in (200, 400):
            with self.subTest(count=count):
                H._LEX_CACHE.clear()
                with self.assertRaises(H.LexUnmatchedSubscript):
                    H.lex_shell("a[\n" * count)

    def test_nested_subscripts_that_span_lines_cost_no_pass_per_level(self):
        command = "a[$(" * 300 + "x\n" + ")]=1" * 300
        lexmap = H.lex_shell(command)
        self.assertLessEqual(lexmap.rounds, 3)
        self.assertLessEqual(lexmap.work, H.LEX_WORK_FACTOR * len(command) + 1024)

    # AC-1, AC-3, AC-7: this task's block of the case table.
    def test_the_cases_are_appended_after_the_earlier_entries_and_all_deny(self):
        cases = subscript_cases()
        self.assertGreaterEqual(len(cases), 20)
        for index, want, label, _cmd in cases:
            with self.subTest(label=label):
                self.assertGreaterEqual(index, SUBSCRIPT_CASE_FLOOR)
                self.assertEqual(want, "deny")
        commands = [cmd for _i, _w, _l, cmd in cases]
        self.assertIn("a[1<<2]=x" + TAIL, commands)

    def test_each_appended_case_is_read_without_an_operator_and_denied_in_both_modes(self):
        for _index, _want, label, command in subscript_cases():
            with self.subTest(label=label):
                self.assertEqual(H.lex_shell(command).heredocs, [])
                self.assertEqual(hook_verdict(command)[0], "deny")
                self.assertEqual(hook_verdict(command, batch=True)[0], "deny")


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

    def test_a_later_operator_is_no_operator_after_an_unreadable_one(self):
        # Rework round 1 (task0005): the unreadable `<<` is a tail source, so
        # no operator is opened after it and the lines of a later `<<EOF`
        # stay inspected as the commands they might be.
        command = "cat <<E$(x)\nrm -rf /tmp/zz\nE\ncat <<EOF\nbody\nEOF\n"
        lexmap = H.lex_shell(command)
        self.assertEqual(list(lexmap.heredocs), [])
        self.assertEqual(lexmap.tail_start, command.index("<<"))

    def test_a_quote_not_closed_on_the_operators_line_takes_no_body(self):
        # Rework round 1 (task0005, AC-3): no operator, and the `<<` is a
        # tail source -- no quote region (nor comment) starts at or after it,
        # so the lines the old reading let the quote swallow stay inspected.
        destructive = "\nrm -rf /home/sakura/valuable\n"
        forms = [
            "cat <<'EOF" + TAIL,
            'cat <<"EOF' + TAIL,
            "cat <<'EOF" + destructive + "EOF'\n",
        ]
        for command in forms:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(list(lexmap.heredocs), [])
                self.assertEqual(actual_regions(lexmap), [])
                self.assertEqual(lexmap.tail_start, command.index("<<"))
                for batch in (False, True):
                    self.assertEqual(hook_verdict(command, batch=batch)[0], "deny")

    def test_a_delimiter_holding_a_blank_finds_its_close_line(self):
        # Rework round 1 (task0005, AC-5): the close-line index looks up a
        # value that holds a space or a tab, so the operator takes its body.
        for command in (
            "cat <<'E X'\nbody\nE X\nrm -rf /home/sakura/valuable",
            "cat <<E\\ X\nbody\nE X\nrm -rf /home/sakura/valuable",
            'cat <<"E\tX"\nbody\nE\tX\nrm -rf /home/sakura/valuable',
        ):
            with self.subTest(command=command):
                lexmap, op = self.operator_of(command)
                self.assertTrue(any(blank in op.delimiter for blank in " \t"))
                self.assertTrue(op.quoted)
                self.assertEqual(heredoc_body(command, op), "body\n")
                self.assertEqual(command[op.close_end :], "rm -rf /home/sakura/valuable")
                self.assertEqual(hook_verdict(command)[0], "deny")

    def test_close_line_under_double_less_is_the_exact_delimiter(self):
        # Rework round 1 (task0005, AC-5): under `<<` a line closes the body
        # only when it equals the delimiter value once its line end is
        # removed; a leading or trailing space or tab, a prefix and a suffix
        # all keep the body going.
        near_misses = [
            " %s", "\t%s", "%s ", "%s\t", " \t%s \t", "%sY", "X%s", "%s-",
        ]
        for delimiter in ("END-X", "E.X", "EOF"):
            lines = [form % delimiter for form in near_misses]
            command = "cat <<%s\nbody\n%s\n%s\n" % (delimiter, "\n".join(lines), delimiter)
            with self.subTest(delimiter=delimiter):
                lexmap, op = self.operator_of(command)
                self.assertEqual(op.delimiter, delimiter)
                self.assertEqual(
                    heredoc_body(command, op), "body\n" + "\n".join(lines) + "\n"
                )
                self.assertEqual(command[op.body_end : op.close_end], delimiter + "\n")

    def test_close_line_under_dash_removes_leading_tabs_only(self):
        # Rework round 1 (task0005, AC-5): under `<<-` the leading tabs of a
        # line are removed first and the remainder must equal the delimiter;
        # a leading space, a tab after a space and any trailing blank do not
        # close.
        for delimiter in ("END-X", "EOF"):
            for closer in ("%s", "\t%s", "\t\t%s"):
                near_misses = [" %s", " \t%s", "\t %s", "%s ", "\t%s\t", "\t%s "]
                lines = [form % delimiter for form in near_misses]
                command = "cat <<-%s\nbody\n%s\n%s\nrest\n" % (
                    delimiter, "\n".join(lines), closer % delimiter,
                )
                with self.subTest(delimiter=delimiter, closer=closer):
                    lexmap, op = self.operator_of(command)
                    self.assertEqual(op.delimiter, delimiter)
                    self.assertEqual(
                        heredoc_body(command, op), "body\n" + "\n".join(lines) + "\n"
                    )
                    self.assertEqual(
                        command[op.body_end : op.close_end], (closer % delimiter) + "\n"
                    )

    def test_a_tab_indented_close_line_does_not_close_a_plain_operator(self):
        command = "cat <<EOF\nbody\n\tEOF\nrest\n"
        self.assertIsNone(self.operator_of(command)[1].body_start)

    def test_close_line_index_looks_up_values_holding_blanks(self):
        # Rework round 1 (task0005, AC-5): one index per operator flavour.
        # Under `<<` a line is its own key (line end removed); under `<<-`
        # its leading tabs are dropped from the key.
        text = "END-X\n  E.X \t\nplain\nE X\n\t\tE Y\n\n\t\n"
        lines = H._LexLines(text)
        exact = lines.close_lines(False)
        self.assertEqual(exact["END-X"], [0])
        self.assertEqual(exact["  E.X \t"], [1])
        self.assertEqual(exact["plain"], [2])
        self.assertEqual(exact["E X"], [3])
        self.assertEqual(exact["\t\tE Y"], [4])
        self.assertEqual(exact[""], [5])
        self.assertEqual(exact["\t"], [6])
        for missing in ("E.X", "E Y", "E"):
            self.assertNotIn(missing, exact)
        dashed = lines.close_lines(True)
        self.assertEqual(dashed["E X"], [3])
        self.assertEqual(dashed["E Y"], [4])
        self.assertEqual(dashed[""], [5, 6])
        self.assertEqual(dashed["  E.X \t"], [1])
        self.assertNotIn("E.X", dashed)

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


# ---------------------------------------------------------------------------
# Rework round 1 (task0005: FR4, FR6, FR8, NFR5, NFR6; review findings
# 1baa909f9b288847 and 19edf404b5cbeb2b). A `<<` whose delimiter word cannot be
# read registers no operator and is a tail source: from it on no comment, no
# quote region and no further here-document operator is opened, so every
# following line stays inspected. A close line ends a body only where bash 5.3
# ends it: under `<<` the line equals the delimiter value, under `<<-` it does
# once its leading tabs are removed.
# ---------------------------------------------------------------------------


class TestHeredocFallbackAndCloseLines(unittest.TestCase):
    # AC-2 / AC-1: the two 1baa909f9b288847 commands.
    FALLBACK_FORMS = [
        "cat <<E${x}\n# $(rm -rf /home/sakura/valuable)\nE\nE${x}",
        "cat <<E`x`\n'\nE`x`\nrm -rf /home/sakura/valuable\n'",
    ]
    # AC-4 / AC-1: the two 19edf404b5cbeb2b commands.
    CLOSE_LINE_FORMS = [
        "cat <<END-X\n END-X\n# $(rm -rf /home/sakura/valuable)\nEND\nEND-X",
        "cat <<END\n END\n# $(rm -rf /home/sakura/valuable)\nEND",
    ]
    # AC-5: the allow case.
    BLANK_DELIMITER_FORM = "cat <<E' X'\nhello\nE X"
    # AC-3: unreadable words with no operator, each with a destructive line
    # after the operator's line.
    UNREADABLE_FORMS = [
        "cat <<" + TAIL,
        "cat <<-" + TAIL,
        "cat << ;" + TAIL,
        "cat <<'EOF" + TAIL,
        'cat <<"EOF' + TAIL,
        "cat <<E$(x)\n'\nrm -rf /home/sakura/valuable\n'",
        "cat <<E$((1))\n#\nrm -rf /home/sakura/valuable",
        "cat <<E$[1]\n\"\nrm -rf /home/sakura/valuable\n\"",
        "cat <<$'E'\n# x\nrm -rf /home/sakura/valuable",
        "cat <<E\\\n'\nrm -rf /home/sakura/valuable\n'",
    ]
    STOPPED_KINDS = QUOTE_KINDS | {"comment"}

    def check_tail_reading(self, command):
        """No operator for the `<<`, no comment or quote region from it on,
        and the map's tail start at or before it."""
        lexmap = H.lex_shell(command)
        pos = command.index("<<")
        self.assertEqual(list(lexmap.heredocs), [], msg=repr(command))
        self.assertEqual(
            [r for r in lexmap.regions if r.start >= pos and r.kind in self.STOPPED_KINDS],
            [],
            msg=repr(command),
        )
        self.assertIsNotNone(lexmap.tail_start, msg=repr(command))
        self.assertLessEqual(lexmap.tail_start, pos, msg=repr(command))
        return lexmap

    def test_unreadable_word_is_a_tail_source_and_denied(self):
        # AC-2 (NFR6, TM-3): the lines after the `<<` are read as the commands
        # they are, in both modes.
        for command in self.FALLBACK_FORMS:
            with self.subTest(command=command):
                self.check_tail_reading(command)
                for batch in (False, True):
                    decision, reason = hook_verdict(command, batch=batch)
                    self.assertEqual(decision, "deny", msg=reason[:200])

    def test_the_destructive_line_is_inside_a_substitution_region_of_the_tail(self):
        command = self.FALLBACK_FORMS[0]
        lexmap = H.lex_shell(command)
        kinds = [(r.kind, command[r.start : r.end]) for r in lexmap.regions]
        self.assertIn(
            ("command-substitution", "$(rm -rf /home/sakura/valuable)"), kinds
        )
        command = self.FALLBACK_FORMS[1]
        kinds = [(r.kind, command[r.start : r.end]) for r in H.lex_shell(command).regions]
        self.assertEqual(
            [k for k in kinds if k[0] == "backtick-substitution"],
            [("backtick-substitution", "`x`"), ("backtick-substitution", "`x`")],
        )

    def test_empty_and_unclosed_quote_words_take_the_same_tail_reading(self):
        # AC-3: no word before the newline, a quote that does not close on
        # the operator's line, and the other unreadable words.
        for command in self.UNREADABLE_FORMS:
            with self.subTest(command=command):
                lexmap = self.check_tail_reading(command)
                self.assertEqual(lexmap.tail_start, command.index("<<"))
                for batch in (False, True):
                    decision, reason = hook_verdict(command, batch=batch)
                    self.assertEqual(decision, "deny", msg=reason[:200])

    def test_quote_characters_of_the_tail_are_listed_and_hidden_from_shlex(self):
        # No quote region opens, so each `'` / `"` of the tail is literal: the
        # map lists it in UNOPENED and the masked view hides it from shlex,
        # which would otherwise pair two of them across the lines between.
        command = self.FALLBACK_FORMS[1]
        quotes = [i for i, ch in enumerate(command) if ch == "'"]
        self.assertEqual(len(quotes), 2)
        lexmap = H.lex_shell(command)
        self.assertEqual(list(lexmap.unopened), quotes)
        view = H._MarkedText.plain(command)
        self.assertEqual([lo for lo, _hi in view.mask_ranges], quotes)
        self.assertNotIn("'", view.view)
        # An unreadable `<<` followed by double quotes and `$'` / `$"` the same way.
        command = "cat <<E${x}\n\"a\n$'b\n$\"c\nrm -rf /home/sakura/valuable\n\""
        lexmap = H.lex_shell(command)
        self.assertEqual([r.kind for r in lexmap.regions], ["parameter-expansion"])
        self.assertEqual(
            list(lexmap.unopened),
            [i for i, ch in enumerate(command) if ch in "'\""],
        )
        self.assertEqual(hook_verdict(command)[0], "deny")

    def test_lexing_work_is_linear_in_a_tail_full_of_quote_characters(self):
        unit = "' \" \\\n# c $'a $\"b\n"
        small = H.lex_shell("cat <<E${x}\n" + unit * 200)
        large = H.lex_shell("cat <<E${x}\n" + unit * 400)
        self.assertLessEqual(large.work, 2.5 * small.work + 100)
        self.assertLessEqual(
            large.work, H.LEX_WORK_FACTOR * len("cat <<E${x}\n" + unit * 400) + 1024
        )

    def test_no_operator_is_opened_after_an_unreadable_word(self):
        command = "cat <<E${x}\ncat <<EOF\nrm -rf /home/sakura/valuable\nEOF\n"
        lexmap = self.check_tail_reading(command)
        self.assertEqual(list(lexmap.unopened), [])
        self.assertEqual(hook_verdict(command)[0], "deny")

    def test_an_earlier_operator_keeps_its_body(self):
        command = "cat <<A <<B${x}\nbody\nA\nrm -rf /home/sakura/valuable\n"
        lexmap = H.lex_shell(command)
        self.assertEqual(
            [(op.delimiter, heredoc_body(command, op)) for op in lexmap.heredocs],
            [("A", "body\n")],
        )
        self.assertEqual(lexmap.tail_start, command.index("<<B"))
        self.assertEqual(hook_verdict(command)[0], "deny")

    def test_tail_start_is_the_earliest_of_the_unreadable_word_and_the_settle_channel(self):
        before = "cat <<E${x}\necho ${y\n"
        self.assertEqual(H.lex_shell(before).tail_start, before.index("<<"))
        after = "echo ${y\ncat <<E${x}\n"
        lexmap = H.lex_shell(after)
        self.assertEqual(lexmap.tail_start, after.index("${y"))
        self.assertEqual(list(lexmap.unopened), [after.index("${y")])

    def test_a_readable_word_is_no_tail_source(self):
        for command in (
            "cat <<EOF\nbody\nEOF\necho 'a' # c\n",
            "cat <<'EOF'\nbody\nEOF\necho 'a' # c\n",
            "cat <<E X\nbody\nE\necho 'a' # c\n",
        ):
            with self.subTest(command=command):
                self.assertIsNone(H.lex_shell(command).tail_start)

    def test_a_tail_source_in_a_resumed_span_is_taken_back_with_the_pass_state(self):
        # A `$((` whose first close is a lone `)` is read again as a command
        # substitution holding a group. The tail source found while its span
        # was read as arithmetic is part of the state the resume takes back:
        # the quote before the `<<` is a region on the second reading, and
        # the whole map equals the one a whole-text restart gives.
        for command in (
            "echo $(( 'a ) ' $(cat <<E${x}) ) | cat) 'q' # c\n",
            "echo $(( $(cat <<E${x}) ) | cat) 'q' # c\n",
            "echo $(( 'a ) ' $(cat <<E${x}) ) | cat) $(( $(cat <<E${y}) ) | cat) 'q'\n",
        ):
            with self.subTest(command=command):
                H._LEX_CACHE.clear()
                lexmap = H.lex_shell(command)
                self.assertEqual(lexical_reading(lexmap), whole_text_restart_reading(command))
                self.assertEqual(lexmap.tail_start, command.index("<<"))
                self.assertEqual(list(lexmap.heredocs), [])
                quotes = [command[r.start : r.end] for r in lexmap.regions if r.kind in QUOTE_KINDS]
                self.assertEqual(quotes, ["'a ) '"] if "'a ) '" in command else [])
                self.assertNotIn("comment", [r.kind for r in lexmap.regions])

    def test_close_line_forms_keep_the_blank_indented_line_in_the_body(self):
        # AC-4 (NFR6, TM-3): one operator whose body runs to the last line.
        for command in self.CLOSE_LINE_FORMS:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(len(lexmap.heredocs), 1)
                op = lexmap.heredocs[0]
                last_line = command.rindex("\n") + 1
                self.assertEqual(op.body_end, last_line)
                self.assertEqual(op.close_end, len(command))
                self.assertEqual(command[op.body_end : op.close_end], op.delimiter)
                self.assertTrue(heredoc_body(command, op).startswith(" END"))
                self.assertIsNone(lexmap.tail_start)
                for batch in (False, True):
                    decision, reason = hook_verdict(command, batch=batch)
                    self.assertEqual(decision, "deny", msg=reason[:200])

    def test_a_quoted_delimiter_holding_a_blank_registers_one_operator(self):
        # AC-5: the value is `E X`, quoted, and the body closes at `E X`.
        command = self.BLANK_DELIMITER_FORM
        lexmap = H.lex_shell(command)
        self.assertEqual(len(lexmap.heredocs), 1)
        op = lexmap.heredocs[0]
        self.assertEqual((op.delimiter, op.quoted), ("E X", True))
        self.assertEqual(heredoc_body(command, op), "hello\n")
        self.assertEqual(command[op.body_end : op.close_end], "E X")
        for batch in (False, True):
            decision, reason = hook_verdict(command, batch=batch)
            self.assertEqual(decision, "allow", msg=reason[:200])

    def test_close_line_decides_which_statement_follows(self):
        # Under `<<` a space-indented delimiter line is body text and the
        # exact line ends it; under `<<-` a tab-indented one ends it.
        destructive = "rm -rf /home/sakura/valuable"
        for command, closes in (
            ("cat <<E\n E\n" + destructive + "\nE\n", False),
            ("cat <<E\nE \n" + destructive + "\nE\n", False),
            ("cat <<E\n\tE\n" + destructive + "\nE\n", False),
            ("cat <<E\nE\n" + destructive + "\n", True),
            ("cat <<-E\n\tE\n" + destructive + "\n", True),
            ("cat <<-E\n E\n" + destructive + "\nE\n", False),
            ("cat <<-E\n\tE \n" + destructive + "\nE\n", False),
        ):
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(len(lexmap.heredocs), 1)
                op = lexmap.heredocs[0]
                self.assertEqual(
                    destructive in command[op.close_end :], closes, msg=repr(command)
                )

    def test_new_cases_are_in_the_case_table_after_the_earlier_entries(self):
        # AC-1, AC-5, AC-7: located by label and command text, never by an
        # absolute index; each sits after the 627 entries present at the base.
        cases = case_commands()
        expected = [(form, "deny", "1baa909f9b288847 round2-residuals ")
                    for form in self.FALLBACK_FORMS]
        expected += [(form, "deny", "19edf404b5cbeb2b round2-residuals ")
                     for form in self.CLOSE_LINE_FORMS]
        expected.append(
            (self.BLANK_DELIMITER_FORM, "allow", "19edf404b5cbeb2b round2-residuals ")
        )
        previous = -1
        for command, verdict, prefix in expected:
            with self.subTest(command=command):
                found = [
                    (index, want, label)
                    for index, (want, label, cmd) in enumerate(cases)
                    if cmd == command
                ]
                self.assertEqual(len(found), 1)
                index, want, label = found[0]
                self.assertGreaterEqual(index, 627)
                self.assertGreater(index, previous)
                previous = index
                self.assertEqual(want, verdict)
                self.assertTrue(label.startswith(prefix), msg=label)


class TestFallbackStageAgreement(TestStageAgreement):
    """The stage agreement properties (a)-(f) of TestStageAgreement, over the
    forms of the here-document fallback and close-line rules."""

    @classmethod
    def setUpClass(cls):
        forms = list(TestHeredocFallbackAndCloseLines.FALLBACK_FORMS)
        forms += TestHeredocFallbackAndCloseLines.CLOSE_LINE_FORMS
        forms += TestHeredocFallbackAndCloseLines.UNREADABLE_FORMS
        forms.append(TestHeredocFallbackAndCloseLines.BLANK_DELIMITER_FORM)
        cls.commands = forms


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
    # `${` followed by a blank is the bash 5.3 command form (nested command
    # forms, never settled); `${x` is the parameter form, settled when it never
    # closes: the bulk test covers both readings (1fcae1f76f2a20f0, SPEC A8).
    OPENERS = ["${", "${x", "$((", "$[", "((", "$'"]
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
        command = "${x " * 20000
        lexmap = H.lex_shell(command)
        self.assertLessEqual(lexmap.work, H.LEX_WORK_FACTOR * len(command) + 1024)
        self.assertEqual(len(lexmap.unopened), 20000)
        self.assertEqual(lexmap.tail_start, 0)

    def test_many_unclosed_command_forms_are_read_in_linear_work_and_never_settled(self):
        command = "${ " * 20000
        lexmap = H.lex_shell(command)
        self.assertLessEqual(lexmap.work, H.LEX_WORK_FACTOR * len(command) + 1024)
        self.assertEqual(list(lexmap.unopened), [])
        self.assertIsNone(lexmap.tail_start)
        self.assertEqual(lexmap.rounds, 1)

    def test_budget_exceeded_is_an_ask_never_an_allow(self):
        command = "(( ;" * 15000 + self.DESTRUCTIVE
        decision, _reason = hook_verdict(command)
        self.assertIn(decision, ("ask", "deny"))


# ---------------------------------------------------------------------------
# The bash 5.3 command form of `${` (destructive-guard-lexer-round2-deferred,
# task0005: FR7, FR9-FR11, NFR1-NFR7; review finding 1fcae1f76f2a20f0).
# `${` directly followed by a space, a tab, a newline or `|` is a command
# substitution (`${ cmd; }` / `${|cmd; }`) whose content is read as commands;
# every other `${` is the parameter form. Expectations are written out by hand
# (D6); the forms marked "bash 5.3.9" were run there with `rm` replaced by
# `echo`.
# ---------------------------------------------------------------------------

BRACE_LABEL_ID = "1fcae1f76f2a20f0 round2-deferred"
# The first index a block appended by a task of this feature can sit at.
BRACE_BLOCK_FLOOR = 769
RM_VALUABLE = "rm -rf /home/sakura/valuable"

# The seven cases of the task plan and the four it adds beyond SPEC.md (the
# first three confirmed on bash 5.3.9, the last one a deny that keeps a
# conservative verdict): tag -> (expected verdict, command).
BRACE_CASES = {
    "FR7.1": ("deny", "echo ${ " + RM_VALUABLE + "; }"),
    "FR7.2": ("deny", "echo ${|" + RM_VALUABLE + "; }"),
    "FR7.3": ("deny", "echo ${\n" + RM_VALUABLE + "\n}"),
    "FR7.4": ("deny", "cat <<E\n${ " + RM_VALUABLE + "; }\nE"),
    "FR7.5": ("deny", "echo ${ " + RM_VALUABLE),
    "FR7.6": ("allow", "echo ${x} ${x:-y} ${#x}"),
    "FR7.7": ("allow", "cat <<'E'\n${ " + RM_VALUABLE + "; }\nE"),
    "FR7.8": ("deny", 'echo "${ ' + RM_VALUABLE + '; }"'),
    "FR7.9": ("deny", "echo ${x:-${ " + RM_VALUABLE + "; }}"),
    "FR7.10": ("deny", "echo ${ { " + RM_VALUABLE + "; }; }"),
    "FR7.11": ("deny", "git reset --hard`${ x`"),
}
BRACE_REQUIRED_TAGS = ["FR7.%d" % n for n in range(1, 8)]

# (command, the literal of the one region, its inner text): cases 1 to 3. The
# inner text is exactly what lies between the opener (`${`, or `${|`) and the
# final `}`.
BRACE_CLOSED_FORMS = [
    (
        BRACE_CASES["FR7.1"][1],
        "${ " + RM_VALUABLE + "; }",
        " " + RM_VALUABLE + "; ",
    ),
    (
        BRACE_CASES["FR7.2"][1],
        "${|" + RM_VALUABLE + "; }",
        RM_VALUABLE + "; ",
    ),
    (
        BRACE_CASES["FR7.3"][1],
        "${\n" + RM_VALUABLE + "\n}",
        "\n" + RM_VALUABLE + "\n",
    ),
]

# Where the close lands (SPEC A7; bash 5.3.9): (command, the command form's
# literal, or None when it never closes). A `}` closes at a reserved-word
# position (the start of the content, after `;`, `&`, a newline, after a
# closer), as a token of its own: what follows it is not part of it.
BRACE_CLOSE_FORMS = [
    ("echo ${ echo hi;}", "${ echo hi;}"),
    ("echo ${ echo hi; }}", "${ echo hi; }"),
    ("echo ${ echo hi; }x", "${ echo hi; }"),
    ("echo ${ echo hi &}", "${ echo hi &}"),
    ("echo ${ }", "${ }"),
    ("echo ${|}", "${|}"),
    ("echo ${ echo hi\n}", "${ echo hi\n}"),
    ("echo ${ echo hi; } }", "${ echo hi; }"),
    ("echo ${ { echo hi; } }", "${ { echo hi; } }"),
    ("echo ${ { echo hi; }; }", "${ { echo hi; }; }"),
    ("echo ${ { { echo hi; }; }; }", "${ { { echo hi; }; }; }"),
    ("echo ${ ( echo hi ) }", "${ ( echo hi ) }"),
    ("echo ${ if true; then echo hi; fi }", "${ if true; then echo hi; fi }"),
    ("echo ${ case x in x) echo hi;; esac }", "${ case x in x) echo hi;; esac }"),
    # A `}` that is an argument, part of a word or quoted closes nothing.
    ("echo ${ echo }", None),
    ("echo ${ echo hi}", None),
    ("echo ${ echo \\}", None),
    ("echo ${ echo a}b; }", "${ echo a}b; }"),
    ("echo ${ echo \\}; }", "${ echo \\}; }"),
    ("echo ${ echo $x}; }", "${ echo $x}; }"),
    ("echo ${ >f }", None),
    ("echo ${ { echo hi; }", None),
    ("echo ${ case x in }) echo hi;; esac; }", "${ case x in }) echo hi;; esac; }"),
]

# (command, [(kind, literal[, n]), ...], the child region's parent literal):
# the command form read inside another region (AC-3).
BRACE_NESTED_FORMS = [
    (
        BRACE_CASES["FR7.8"][1],
        [("double-quote", '"${ ' + RM_VALUABLE + '; }"'), (BRACE_KIND, "${ " + RM_VALUABLE + "; }")],
        "double-quote",
    ),
    (
        BRACE_CASES["FR7.9"][1],
        [
            ("parameter-expansion", "${x:-${ " + RM_VALUABLE + "; }}"),
            (BRACE_KIND, "${ " + RM_VALUABLE + "; }"),
        ],
        "parameter-expansion",
    ),
    (
        BRACE_CASES["FR7.10"][1],
        [(BRACE_KIND, "${ { " + RM_VALUABLE + "; }; }")],
        None,
    ),
]

# The two forms of AC-4 that are not cases: a `}` that closes nothing, and a
# command form after a `<<` whose delimiter word cannot be read (D4).
BRACE_ARGUMENT_FORM = "echo ${ echo }"
BRACE_TAIL_FORM = "cat <<E${x}\necho ${ " + RM_VALUABLE + "; }"

# Existing cases whose discarded line holds a command form (AC-5): label
# fragment -> the text the form is cut at (the newline that ends the line).
BRACE_DISCARDED_LABELS = [
    "heredoc-syntax-error E-12 ",
    "heredoc-syntax-error T2 AC-5.5 ",
    "heredoc-syntax-error T2 AC-5.7 ",
]


def brace_cases():
    """{tag: (verdict, command, index)} of the cases this task appended,
    found by label (never by an absolute index)."""
    found = {}
    for index, (want, label, cmd) in enumerate(case_commands()):
        if label.startswith(BRACE_LABEL_ID + " FR7."):
            tag = label.split(" ")[2]
            assert tag not in found, tag
            found[tag] = (want, cmd, index)
    return found


def brace_regions(lexmap):
    return [r for r in lexmap.regions if r.kind == BRACE_KIND]


class TestBraceCommandSubstitution(unittest.TestCase):
    def verdicts(self, command):
        return hook_verdict(command)[0], hook_verdict(command, batch=True)[0]

    def assert_both_modes(self, command, want):
        self.assertEqual(self.verdicts(command), (want, want), msg=repr(command))

    # AC-1, AC-7: the cases are in the table, after the feature base.
    def test_the_cases_are_in_the_case_table_after_the_base(self):
        found = brace_cases()
        for tag in BRACE_REQUIRED_TAGS:
            self.assertIn(tag, found)
        for tag, (want, cmd, index) in found.items():
            with self.subTest(tag=tag):
                self.assertEqual((want, cmd), BRACE_CASES[tag])
                self.assertGreaterEqual(index, BRACE_BLOCK_FLOOR)
        indexes = sorted(index for _w, _c, index in found.values())
        self.assertEqual(indexes, list(range(indexes[0], indexes[0] + len(indexes))))

    def test_the_cases_label_and_text_match_the_plan(self):
        found = brace_cases()
        labels = {
            index: label for index, (_w, label, _c) in enumerate(case_commands())
        }
        for tag, (_want, _cmd, index) in found.items():
            self.assertTrue(
                labels[index].startswith("%s %s " % (BRACE_LABEL_ID, tag)), msg=labels[index]
            )

    # AC-2: cases 1 to 3.
    def test_a_closed_command_form_is_one_region_and_one_span(self):
        for command, literal, inner in BRACE_CLOSED_FORMS:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(
                    actual_regions(lexmap),
                    expected_regions(command, [(BRACE_KIND, literal)]),
                )
                (region,) = lexmap.regions
                self.assertTrue(region.closed)
                self.assertIsNone(region.parent)
                self.assertEqual(list(lexmap.unopened), [])
                self.assertIsNone(lexmap.tail_start)
                self.assertEqual(list(lexmap.heredocs), [])
                spans, parent_of, unmatched, opaque, _containing = H.scan_structure(command)
                self.assertEqual(spans, [(region.start, region.end)])
                self.assertEqual(parent_of, {(region.start, region.end): None})
                self.assertEqual(unmatched, [])
                self.assertEqual(opaque, [(region.start, region.end)])
                got_inner, inner_start = H._span_inner(command, spans[0])
                self.assertEqual(got_inner, inner)
                self.assertEqual(command[inner_start : inner_start + len(inner)], inner)

    def test_the_map_is_the_same_after_clearing_the_lexer_cache(self):
        closed = [form[0] for form in BRACE_CLOSED_FORMS]
        for command in closed + [cmd for _tag, (_want, cmd) in BRACE_CASES.items()]:
            with self.subTest(command=command):
                first = H.lex_shell(command)
                H._LEX_CACHE.clear()
                second = H.lex_shell(command)
                self.assertIsNot(first, second)
                self.assertEqual(first.as_tuple(), second.as_tuple())
                if command in closed:
                    # The map being compared is the one with the command
                    # form in it.
                    self.assertEqual(len(brace_regions(first)), 1)
                    self.assertEqual(len(brace_regions(second)), 1)

    def test_the_closed_command_forms_are_deny_in_both_modes(self):
        for command, _literal, _inner in BRACE_CLOSED_FORMS:
            with self.subTest(command=command):
                self.assert_both_modes(command, "deny")

    def test_a_command_form_in_a_heredoc_body_is_one_substitution(self):
        # Case 4: the here-document body extraction reports the form, its
        # inner text exactly what lies between `${` and `}` (`${|` from after
        # the `|`).
        for opener, inner in (
            ("${ ", " " + RM_VALUABLE + "; "),
            ("${|", RM_VALUABLE + "; "),
            ("${\n", "\n" + RM_VALUABLE + "; "),
        ):
            command = "cat <<E\n" + opener + RM_VALUABLE + "; }\nE"
            with self.subTest(opener=opener):
                lexmap = H.lex_shell(command)
                self.assertEqual(len(lexmap.heredocs), 1)
                body = heredoc_body(command, lexmap.heredocs[0])
                self.assertEqual(body, opener + RM_VALUABLE + "; }\n")
                bodies, needs_whole_body = H._extract_heredoc_body_substitutions(body)
                self.assertEqual(bodies, [(inner, 0)])
                self.assertFalse(needs_whole_body)
                body_map = H.lex_shell(body, "heredoc-body")
                self.assertEqual(
                    actual_regions(body_map),
                    expected_regions(body, [(BRACE_KIND, opener + RM_VALUABLE + "; }")]),
                )
                self.assert_both_modes(command, "deny")

    def test_case_4_is_deny_in_both_modes(self):
        self.assert_both_modes(BRACE_CASES["FR7.4"][1], "deny")

    def test_an_unclosed_command_form_in_a_heredoc_body_is_inspected(self):
        # The body is read as the here-document reads it: a quote or `#`
        # before an unclosed form opens nothing there, so the form's content
        # is inspected whatever precedes it.
        for prefix in ("", "it's\n", "# note\n", '"\n', "'\n", "a'b\n"):
            for opener in ("${ ", "${|", "${\n"):
                command = "cat <<E\n" + prefix + opener + RM_VALUABLE + "\nE"
                with self.subTest(command=command):
                    self.assert_both_modes(command, "deny")

    def test_a_benign_unclosed_command_form_in_a_heredoc_body_is_allowed(self):
        for command in (
            "cat <<E\nit's\n${ echo hi\nE",
            "cat <<E\nit's\n${|echo hi\nE",
            "cat <<'E'\nit's\n${ " + RM_VALUABLE + "\nE",
        ):
            with self.subTest(command=command):
                self.assert_both_modes(command, "allow")

    # AC-3: the form inside other regions.
    def test_a_command_form_inside_another_region(self):
        for command, items, outer in BRACE_NESTED_FORMS:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(
                    actual_regions(lexmap), expected_regions(command, items)
                )
                (region,) = brace_regions(lexmap)
                self.assertTrue(region.closed)
                if outer is None:
                    self.assertIsNone(region.parent)
                else:
                    self.assertEqual(lexmap.regions[region.parent].kind, outer)
                self.assertEqual(list(lexmap.unopened), [])
                self.assertIsNone(lexmap.tail_start)
                self.assert_both_modes(command, "deny")

    def test_the_command_form_in_double_quotes_is_a_span_of_the_quote(self):
        command = BRACE_CASES["FR7.8"][1]
        spans, parent_of, unmatched, opaque, _containing = H.scan_structure(command)
        form = span_of(command, "${ " + RM_VALUABLE + "; }")
        quote = span_of(command, '"${ ' + RM_VALUABLE + '; }"')
        self.assertEqual(spans, [form])
        self.assertEqual(unmatched, [])
        self.assertEqual(opaque, [quote])

    def test_an_inner_brace_group_does_not_close_the_form(self):
        command = BRACE_CASES["FR7.10"][1]
        lexmap = H.lex_shell(command)
        (region,) = brace_regions(lexmap)
        self.assertEqual((region.start, region.end), (command.index("${"), len(command)))

    # SPEC A7: where the close lands.
    def test_where_the_close_lands(self):
        for command, literal in BRACE_CLOSE_FORMS:
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                regions = brace_regions(lexmap)
                self.assertEqual(len(regions), 1)
                region = regions[0]
                self.assertEqual(region.start, command.index("${"))
                if literal is None:
                    self.assertFalse(region.closed)
                    self.assertEqual(region.end, len(command))
                else:
                    self.assertTrue(region.closed)
                    self.assertEqual(
                        command[region.start : region.end], literal
                    )
                self.assertEqual(list(lexmap.unopened), [])
                self.assertIsNone(lexmap.tail_start)

    def test_a_brace_group_count_is_per_form(self):
        # The `}` of a group opened in the outer form does not close the form
        # inside it, and the form's own `}` is not taken for the group's.
        command = "{ echo ${ echo hi; }; }; " + RM_VALUABLE
        lexmap = H.lex_shell(command)
        (region,) = brace_regions(lexmap)
        self.assertTrue(region.closed)
        self.assertEqual(command[region.start : region.end], "${ echo hi; }")
        self.assert_both_modes(command, "deny")

    def test_the_text_after_a_closed_form_is_read_at_the_outer_level(self):
        for command in (
            "echo ${ echo hi; }; " + RM_VALUABLE,
            "echo ${ echo hi; }\n" + RM_VALUABLE,
            "echo ${ echo hi; }}; " + RM_VALUABLE,
            "echo ${ echo hi;}x; " + RM_VALUABLE,
        ):
            with self.subTest(command=command):
                self.assert_both_modes(command, "deny")

    # AC-4: an unclosed form, the parameter form, a tail source.
    def test_an_unclosed_command_form_runs_to_the_end_and_is_inspected(self):
        command = BRACE_CASES["FR7.5"][1]
        lexmap = H.lex_shell(command)
        self.assertEqual(
            actual_regions(lexmap),
            [(BRACE_KIND, command.index("${"), len(command))],
        )
        (region,) = lexmap.regions
        self.assertFalse(region.closed)
        self.assertEqual(list(lexmap.unopened), [])
        self.assertIsNone(lexmap.tail_start)
        spans, _parent_of, unmatched, _opaque, _containing = H.scan_structure(command)
        self.assertEqual(spans, [])
        self.assertEqual(unmatched, [region.start])
        self.assertEqual(
            H._unclosed_command_forms(command), [(" " + RM_VALUABLE, region.start)]
        )
        self.assert_both_modes(command, "deny")

    def test_only_the_outermost_unclosed_form_is_queued(self):
        command = "echo ${ echo ${ echo ${|" + RM_VALUABLE
        outer = command.index("${")
        self.assertEqual(
            H._unclosed_command_forms(command),
            [(" echo ${ echo ${|" + RM_VALUABLE, outer)],
        )
        self.assert_both_modes(command, "deny")

    def test_a_closed_form_is_not_in_the_unclosed_list(self):
        self.assertEqual(H._unclosed_command_forms("echo ${ echo hi; }"), [])
        self.assertEqual(H._unclosed_command_forms("echo ${x"), [])

    def test_a_close_that_never_comes_closes_nothing(self):
        lexmap = H.lex_shell(BRACE_ARGUMENT_FORM)
        (region,) = brace_regions(lexmap)
        self.assertFalse(region.closed)
        self.assertEqual(region.end, len(BRACE_ARGUMENT_FORM))
        self.assertEqual(
            H._unclosed_command_forms(BRACE_ARGUMENT_FORM), [(" echo }", region.start)]
        )

    def test_the_parameter_form_stays_a_parameter_expansion(self):
        command = BRACE_CASES["FR7.6"][1]
        lexmap = H.lex_shell(command)
        self.assertEqual(
            actual_regions(lexmap),
            expected_regions(
                command,
                [
                    ("parameter-expansion", "${x}"),
                    ("parameter-expansion", "${x:-y}"),
                    ("parameter-expansion", "${#x}"),
                ],
            ),
        )
        self.assertEqual(brace_regions(lexmap), [])
        self.assertEqual(list(lexmap.unopened), [])
        self.assertIsNone(lexmap.tail_start)
        self.assert_both_modes(command, "allow")

    def test_a_backtick_ends_a_command_form_opened_inside_it(self):
        # A backtick substitution ends at the next unescaped backtick whatever
        # it holds (bash 5.3.9 runs the command before it here, the
        # substitution being a syntax error of its own): the form opened inside
        # it ends unclosed there, and the substitution stays a closed span, so
        # the word before it is still read as it was.
        for command, forms in (
            ("git reset --hard`${ x`", ["${ x"]),
            ("git reset --hard`${ ${|x`", ["${ ${|x", "${|x"]),
            ("git reset --hard`echo ${ x`", ["${ x"]),
        ):
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                (backtick,) = [
                    r for r in lexmap.regions if r.kind == "backtick-substitution"
                ]
                self.assertTrue(backtick.closed)
                self.assertEqual(command[backtick.start : backtick.end][-1], "`")
                self.assertEqual(backtick.end, len(command))
                got = [command[r.start : r.end] for r in brace_regions(lexmap)]
                self.assertEqual(got, forms)
                for region in brace_regions(lexmap):
                    self.assertFalse(region.closed)
                    self.assertEqual(region.end, backtick.end - 1)
                spans, _parent_of, unmatched, _opaque, _c = H.scan_structure(command)
                self.assertEqual(spans, [(backtick.start, backtick.end)])
                self.assertEqual(len(unmatched), len(forms))
                self.assert_both_modes(command, "deny")

    def test_a_command_form_closed_inside_a_backtick_substitution_is_closed(self):
        command = "echo `echo ${ echo hi; }` ; " + RM_VALUABLE
        lexmap = H.lex_shell(command)
        (region,) = brace_regions(lexmap)
        self.assertTrue(region.closed)
        self.assertEqual(command[region.start : region.end], "${ echo hi; }")
        self.assert_both_modes(command, "deny")

    def test_a_blank_other_than_space_tab_newline_does_not_open_the_form(self):
        for command in ("echo ${\rx}", "echo ${\x0cx}", "echo ${\x0bx}"):
            with self.subTest(command=command):
                lexmap = H.lex_shell(command)
                self.assertEqual(brace_regions(lexmap), [])

    def test_a_tab_opens_the_form(self):
        command = "echo ${\t" + RM_VALUABLE + "; }"
        lexmap = H.lex_shell(command)
        (region,) = brace_regions(lexmap)
        self.assertTrue(region.closed)
        self.assert_both_modes(command, "deny")

    def test_a_quoted_delimiter_body_keeps_the_form_as_text(self):
        command = BRACE_CASES["FR7.7"][1]
        lexmap = H.lex_shell(command)
        self.assertEqual(lexmap.regions, [])
        self.assertEqual(len(lexmap.heredocs), 1)
        self.assertTrue(lexmap.heredocs[0].quoted)
        self.assert_both_modes(command, "allow")

    def test_the_form_opens_after_a_delimiter_word_that_cannot_be_read(self):
        # D4: a tail source refuses the parameter form, never the command form.
        lexmap = H.lex_shell(BRACE_TAIL_FORM)
        regions = brace_regions(lexmap)
        self.assertEqual(len(regions), 1)
        self.assertGreater(regions[0].start, BRACE_TAIL_FORM.index("<<"))
        self.assertEqual(regions[0].start, BRACE_TAIL_FORM.index("${ "))
        self.assertTrue(regions[0].closed)
        self.assertNotIn(regions[0].start, list(lexmap.unopened))
        self.assert_both_modes(BRACE_TAIL_FORM, "deny")

    # AC-5: the form on a discarded line.
    def test_a_form_on_a_discarded_line_closes_at_the_newline(self):
        cases = case_commands()
        for fragment in BRACE_DISCARDED_LABELS:
            matching = [
                (want, label, cmd) for want, label, cmd in cases if fragment in label
            ]
            self.assertEqual(len(matching), 1, msg=fragment)
            want, _label, command = matching[0]
            with self.subTest(label=fragment):
                self.assertEqual(want, "deny")
                lexmap = H.lex_shell(command)
                regions = brace_regions(lexmap)
                self.assertEqual(len(regions), 1)
                region = regions[0]
                self.assertFalse(region.closed)
                newline = command.index("\n", region.start)
                self.assertEqual(region.end, newline)
                self.assertEqual(list(lexmap.unopened), [])
                self.assert_both_modes(command, "deny")

    # AC-6: work.
    def test_lexing_work_is_linear_for_every_case_repeated(self):
        found = brace_cases()
        for tag in BRACE_REQUIRED_TAGS:
            _want, command, _index = found[tag]
            with self.subTest(tag=tag):
                small = H.lex_shell("\n".join([command] * 200))
                large_text = "\n".join([command] * 400)
                large = H.lex_shell(large_text)
                self.assertLessEqual(large.work, 2.5 * small.work + 100)
                self.assertLessEqual(
                    large.work, H.LEX_WORK_FACTOR * len(large_text) + 1024
                )

    def test_repeated_unclosed_forms_get_a_non_allow_decision_in_time(self):
        for tag in ("FR7.1", "FR7.5"):
            command = ("\n".join([BRACE_CASES[tag][1]] * 1000))[:60000]
            with self.subTest(tag=tag):
                start = time.monotonic()
                decision, _reason = hook_verdict(command)
                self.assertNotIn(decision, ("allow", "(timeout)"))
                self.assertLess(time.monotonic() - start, GUARD_TIMEOUT_SECONDS)

    def test_nested_unclosed_forms_followed_by_a_destructive_line_are_never_allow(self):
        command = "${ " * 20000 + "\n" + RM_VALUABLE + "\n"
        start = time.monotonic()
        decision, _reason = hook_verdict(command)
        self.assertIn(decision, ("ask", "deny"))
        self.assertEqual(hook_verdict(command, batch=True)[0], "deny")
        self.assertLess(time.monotonic() - start, 2 * GUARD_TIMEOUT_SECONDS)


class TestBraceCommandStageAgreement(TestStageAgreement):
    """The stage agreement properties (a)-(f) of TestStageAgreement, over the
    command form of `${`: cases 1 to 7 (and the three beyond the SPEC), the
    nested, close and unclosed forms, so the lexer's regions, the structure
    scan, marking, the layout layer and the position maps agree on the new
    region kind."""

    @classmethod
    def setUpClass(cls):
        forms = [cmd for _want, cmd in BRACE_CASES.values()]
        forms += [form[0] for form in BRACE_CLOSED_FORMS]
        forms += [form[0] for form in BRACE_CLOSE_FORMS]
        forms += [form[0] for form in BRACE_NESTED_FORMS]
        forms += [BRACE_ARGUMENT_FORM, BRACE_TAIL_FORM]
        forms += [
            "cat <<E\n${|" + RM_VALUABLE + "; }\nE",
            "echo ${ cat <<E\n" + RM_VALUABLE + "\nE\n}",
            "echo ${ echo hi; } ${|echo ho; } $(echo ${ echo hu; })",
        ]
        seen = []
        for form in forms:
            if form not in seen:
                seen.append(form)
        cls.commands = [form for form in seen if _lexer_reads(form)]

    def test_the_command_forms_are_there_to_check(self):
        # The properties run over these forms; each is read as a command
        # form, so they meet the new region kind and do not pass over a form
        # the lexer reads another way. (A form in a here-document body is
        # read by the body mode, not by the shell-mode map of the command.)
        forms = [cmd for want, cmd in BRACE_CASES.values() if want == "deny"]
        forms += [form[0] for form in BRACE_CLOSED_FORMS]
        forms += [form[0] for form in BRACE_NESTED_FORMS]
        for form in forms:
            with self.subTest(command=form):
                self.assertIn(form, self.commands)
                if "<<" not in form:
                    self.assertTrue(brace_regions(H.lex_shell(form)))


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
        if result.status == "done":
            break
        settled.update(result.settle)
        reparen.update(result.reparen)
    # The re-read tail starts at the earliest settled opener or at the `<<`
    # whose delimiter word could not be read.
    tails = [
        pos for pos in (min(settled) if settled else None, result.tail_source)
        if pos is not None
    ]
    return (
        tuple(
            H.LexRegion(k, s, e, parent, closed)
            for k, s, e, parent, closed, _a in result.regions
        ),
        tuple(H.LexHeredoc(*op) for op in result.ops),
        tuple(sorted(result.candidates, key=lambda c: (c.start, c.end))),
        tuple(sorted(result.encountered)),
        min(tails) if tails else None,
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
# Resume snapshot and the pass result (rework round 1, task0007; review finding
# 956849b341a5150b).
# ---------------------------------------------------------------------------


def classification_gaps(state_cls):
    """(fields of STATE_CLS in no list, fields in more than one list) over the
    pass-state record's enumerable fields and the snapshot type's lists."""
    snapshot = H._LexResumeSnapshot
    fields = set()
    for cls in state_cls.__mro__:
        fields.update(getattr(cls, "__slots__", ()))
    listed = (
        list(snapshot.COLLECTIONS) + list(snapshot.SCALARS) + list(snapshot.NOT_RESTORED)
    )
    unclassified = fields - set(listed)
    repeated = {name for name in listed if listed.count(name) > 1}
    return unclassified, repeated


class TestResumeSnapshot(unittest.TestCase):
    """One named snapshot type captures and restores what the non-adjacent
    close resume takes back; every field of the pass state is either restored
    through it or named in its not-restored list; a pass returns the openers it
    newly reads as two parentheses and leaves the set it was given alone."""

    SNAPSHOT = property(lambda self: H._LexResumeSnapshot)

    def make_state(self):
        return H._LexPassState(H._LexFrame("top", 0, None, None, True), 50)

    def run_pass(self, text, reparen, settled=None, whole_restart=False, bodies=True):
        lines = H._LexLines(text) if bodies and "<<" in text else None
        return H._lex_pass(
            text, "shell", set() if settled is None else settled, reparen, lines,
            1 << 60, whole_restart=whole_restart,
        )

    # AC-1
    def test_restore_returns_every_declared_field_to_its_captured_value(self):
        state = self.make_state()
        for name in self.SNAPSHOT.SCALARS:
            setattr(state, name, ("captured", name))
        for name in self.SNAPSHOT.COLLECTIONS:
            getattr(state, name).extend([("kept", name, k) for k in range(3)])
        want = {name: list(getattr(state, name)) for name in self.SNAPSHOT.COLLECTIONS}
        want.update({name: getattr(state, name) for name in self.SNAPSHOT.SCALARS})
        snapshot = self.SNAPSHOT.capture(state)
        for name in self.SNAPSHOT.COLLECTIONS:
            getattr(state, name).append(("added", name))
            getattr(state, name).append(("added again", name))
        for name in self.SNAPSHOT.SCALARS:
            setattr(state, name, ("changed", name))
        snapshot.restore(state)
        for name in self.SNAPSHOT.COLLECTIONS + self.SNAPSHOT.SCALARS:
            with self.subTest(field=name):
                self.assertEqual(getattr(state, name), want[name])

    def test_the_snapshot_declares_at_least_the_state_a_resume_takes_back(self):
        # AC-1: the iteration above is only as good as the declared fields.
        restored = set(self.SNAPSHOT.COLLECTIONS) | set(self.SNAPSHOT.SCALARS)
        self.assertLessEqual(
            {"regions", "candidates", "encountered", "ops", "hd_pending", "hd_seqs",
             "hd_trigger", "limit", "cont_at", "seq"},
            restored,
        )

    def test_restore_cuts_the_collections_in_place(self):
        # The pass holds the collections under their own names: a restore that
        # rebinds one would leave the pass writing to a list the state no
        # longer holds.
        state = self.make_state()
        held = {name: getattr(state, name) for name in self.SNAPSHOT.COLLECTIONS}
        snapshot = self.SNAPSHOT.capture(state)
        for name in self.SNAPSHOT.COLLECTIONS:
            getattr(state, name).append(object())
        snapshot.restore(state)
        for name in self.SNAPSHOT.COLLECTIONS:
            with self.subTest(field=name):
                self.assertIs(getattr(state, name), held[name])

    def test_the_fields_a_resume_does_not_restore_are_left_as_they_are(self):
        state = self.make_state()
        snapshot = self.SNAPSHOT.capture(state)
        state.iterations += 7
        state.reparen_found.add(11)
        snapshot.restore(state)
        self.assertEqual(state.iterations, 7)
        self.assertEqual(state.reparen_found, {11})

    # AC-2
    def test_every_pass_state_field_is_in_exactly_one_list(self):
        unclassified, repeated = classification_gaps(H._LexPassState)
        self.assertEqual(unclassified, set())
        self.assertEqual(repeated, set())
        fields = set(H._LexPassState.__slots__)
        restored = set(self.SNAPSHOT.COLLECTIONS) | set(self.SNAPSHOT.SCALARS)
        not_restored = set(self.SNAPSHOT.NOT_RESTORED)
        self.assertEqual(fields, restored | not_restored)
        self.assertEqual(restored & not_restored, set())

    def test_a_pass_state_field_added_without_classification_is_found(self):
        class WithNewField(H._LexPassState):
            __slots__ = ("added_later",)

        unclassified, repeated = classification_gaps(WithNewField)
        self.assertEqual(unclassified, {"added_later"})
        self.assertEqual(repeated, set())

    # AC-3
    def test_pending_entries_and_sequence_records_are_restored_independently(self):
        for pending_count, seq_count in ((3, 2), (1, 4), (0, 2), (2, 0)):
            with self.subTest(pending=pending_count, seqs=seq_count):
                state = self.make_state()
                state.hd_pending.extend(["op%d" % k for k in range(pending_count)])
                state.hd_seqs.extend([10 + k for k in range(seq_count)])
                want_pending = list(state.hd_pending)
                want_seqs = list(state.hd_seqs)
                snapshot = self.SNAPSHOT.capture(state)
                state.hd_pending.extend(["late-op-a", "late-op-b"])
                state.hd_seqs.extend([90, 91, 92])
                snapshot.restore(state)
                self.assertEqual(state.hd_pending, want_pending)
                self.assertEqual(state.hd_seqs, want_seqs)

    # AC-4
    def test_the_pass_names_its_new_opener_and_leaves_the_given_set_alone(self):
        text = "x=$((echo a) | wc -c)"
        opener = text.index("$((")
        given = set()
        result = self.run_pass(text, given)
        self.assertEqual(result.status, "done")
        self.assertEqual(given, set())
        self.assertEqual(set(result.reparen), {opener})

    def test_openers_already_given_are_read_as_two_parentheses_and_not_named_again(self):
        text = "x=$((echo a) | wc -c); y=$((echo b) | wc -c)"
        first = text.index("$((")
        second = text.index("$((", first + 1)
        given = {first}
        result = self.run_pass(text, given)
        self.assertEqual(given, {first})
        self.assertEqual(set(result.reparen), {second})

    def test_the_given_set_is_not_changed_by_a_pass_that_names_several_openers(self):
        text = "echo $(( $((echo a) | cat) | wc -c) $((echo b) | wc -c)"
        given = {10_000}
        result = self.run_pass(text, given)
        self.assertEqual(given, {10_000})
        self.assertEqual(
            sorted(result.reparen),
            [m.start() for m in re.finditer(re.escape("$(("), text)],
        )

    def test_an_ending_pass_returns_the_openers_it_found_before_it_ended(self):
        # The pass that ends to settle an unclosed opener also found one that
        # closes without an adjacent `))`; the caller gets both.
        text = "x=$((echo a) | wc -c); echo ${y"
        given = set()
        result = self.run_pass(text, given)
        self.assertEqual(result.status, "restart")
        self.assertEqual(given, set())
        self.assertEqual(list(result.settle), [text.index("${")])
        self.assertEqual(set(result.reparen), {text.index("$((")})

    def test_the_whole_text_restart_reading_returns_its_opener_the_same_way(self):
        text = "x=$((echo a) | wc -c)"
        given = set()
        result = self.run_pass(text, given, whole_restart=True)
        self.assertEqual(result.status, "restart")
        self.assertEqual(given, set())
        self.assertEqual(list(result.settle), [])
        self.assertEqual(set(result.reparen), {text.index("$((")})

    def test_the_final_map_is_the_one_the_combined_set_gives(self):
        # lex_shell() combines what each pass returns: the map of a text with
        # the opener in the given set equals the map without it, the pass
        # having found the opener itself.
        text = "x=$((echo a) | wc -c)\necho done"
        H._LEX_CACHE.clear()
        self.addCleanup(H._LEX_CACHE.clear)
        from_lexer = lexical_reading(H.lex_shell(text))
        given = {text.index("$((")}
        result = self.run_pass(text, given)
        self.assertEqual(result.status, "done")
        self.assertEqual(set(result.reparen), set())
        self.assertEqual(
            tuple(
                H.LexRegion(k, s, e, parent, closed)
                for k, s, e, parent, closed, _a in result.regions
            ),
            from_lexer[0],
        )


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


# ---------------------------------------------------------------------------
# destructive-guard-heredoc-syntax-error task0002 (P14): array subscripts,
# eval / let / alias, and extended-glob parentheses inside an array. The case
# table pins the verdicts; these pin what the lexer itself reads.
# ---------------------------------------------------------------------------

# Where a `<<EOF` right after the array would be a heredoc operator in bash.
SUBSCRIPT_ARRAY_FORMS = [
    "eval x=( <<EOF\nbody\nEOF",
    "let x=( <<EOF\nbody\nEOF",
    "alias x=( <<EOF\nbody\nEOF",
    'x["0"]=( <<EOF\nbody\nEOF',
    "x[$i]=( <<EOF\nbody\nEOF",
    "x['k']=( <<EOF\nbody\nEOF",
    "x[a b]=( <<EOF\nbody\nEOF",
    "x[0]+=( <<EOF\nbody\nEOF",
    "x[$(echo ])]=( <<EOF\nbody\nEOF",
    "eval x[a b]=( <<EOF\nbody\nEOF",
    "x=( [a b]=c <<EOF\nbody\nEOF",
    "x=([1<<2]=foo <<EOF\nbody\nEOF",
]

# Forms whose `<<` the lexer must read as part of a subscript, so the one real
# operator is the one that follows.
SUBSCRIPT_OPERATOR_FORMS = [
    "x=([1<<2]=foo); cat <<'EOF'\nbody\nEOF",
    "x=([1 <<2]=foo [3]=bar); cat <<'EOF'\nbody\nEOF",
    "x[1<<2]=5; cat <<'EOF'\nbody\nEOF",
    'x["k"]=v; cat <<\'EOF\'\nbody\nEOF',
    "let x=1; cat <<'EOF'\nbody\nEOF",
    "alias ll='ls -l'; cat <<'EOF'\nbody\nEOF",
]

EXTGLOB_ARRAY_FORM = re.compile(r"=\([^\n]*[?*+@!]\(")


class TestArraySubscriptAndExtglobReadings(unittest.TestCase):
    def test_a_subscript_or_assignment_builtin_array_is_an_array_context(self):
        # The `<<EOF` directly in the array is no operator, so the lexer
        # registers no heredoc at all and the line after it is a command line.
        for text in SUBSCRIPT_ARRAY_FORMS:
            with self.subTest(text=text):
                self.assertEqual(list(H.lex_shell(text).heredocs), [])

    def test_a_shift_in_a_subscript_is_no_heredoc_operator(self):
        for text in SUBSCRIPT_OPERATOR_FORMS:
            with self.subTest(text=text):
                heredocs = H.lex_shell(text).heredocs
                self.assertEqual(len(heredocs), 1)
                op = heredocs[0]
                self.assertEqual((op.delimiter, heredoc_body(text, op)), ("EOF", "body\n"))
                self.assertGreater(op.start, text.index(";"))

    def test_an_unmatched_subscript_cannot_be_settled(self):
        for text in (
            "x[0=( <<EOF\necho hi\nEOF",
            "x=([foo <<EOF\necho hi\nEOF",
            "x[${",
        ):
            with self.subTest(text=text):
                with self.assertRaises(H.LexUnmatchedSubscript):
                    H.lex_shell(text)
                # It is an unsettled text for every caller that already
                # handles the work bound.
                with self.assertRaises(H.LexBudgetExceeded):
                    H.lex_shell(text)

    def test_the_extended_glob_reading_decides_whether_the_line_is_discarded(self):
        text = "x=(@(foo)); cat <<'A'\nbody\nA"
        off = H.lex_shell(text, "shell", True, False)
        on = H.lex_shell(text, "shell", True, True)
        self.assertEqual(list(off.heredocs), [])
        self.assertEqual(len(on.heredocs), 1)
        self.assertEqual(heredoc_body(text, on.heredocs[0]), "body\n")

    def test_a_bare_parenthesis_in_an_array_discards_the_line_under_both_readings(self):
        text = "x=(a (b)); cat <<'A'\nbody\nA"
        for extglob in (False, True):
            with self.subTest(extglob=extglob):
                self.assertEqual(
                    list(H.lex_shell(text, "shell", True, extglob).heredocs), []
                )

    def test_a_lexing_that_met_an_extended_glob_parenthesis_says_so(self):
        H._lex_extglob_met = False
        H.lex_shell("x=(a b); cat <<'A'\nbody\nA")
        H.lex_shell("x=(a (b)); cat <<'A'\nbody\nA")
        H.lex_shell("echo @(a|b)")
        self.assertFalse(H._lex_extglob_met)
        H.lex_shell("x=(a@(b|c))")
        self.assertTrue(H._lex_extglob_met)
        H._lex_extglob_met = False

    def test_the_reading_in_force_is_the_default_and_part_of_the_cache_key(self):
        text = "x=(@(foo)); cat <<'A'\nbody\nA"
        try:
            H._lex_extglob = True
            self.assertEqual(len(H.lex_shell(text).heredocs), 1)
            H._lex_extglob = False
            self.assertEqual(list(H.lex_shell(text).heredocs), [])
        finally:
            H._lex_extglob = False
            H._lex_extglob_met = False

    def test_the_two_readings_leave_a_command_without_such_a_parenthesis_alone(self):
        for text in SUBSCRIPT_OPERATOR_FORMS + SUBSCRIPT_ARRAY_FORMS:
            with self.subTest(text=text):
                try:
                    off = H.lex_shell(text, "shell", True, False).as_tuple()
                    on = H.lex_shell(text, "shell", True, True).as_tuple()
                except H.LexBudgetExceeded:
                    continue
                self.assertEqual(off, on)


class TestStageAgreementUnderExtglobOn(TestStageAgreement):
    """The stage-agreement checks over every case-table command that holds an
    extended-glob parenthesis in an array, with the lexer reading it as the
    pattern group `shopt -s extglob` makes it (P14): the second reading the
    hook judges such a command under must agree with its consumers as well."""

    @classmethod
    def setUpClass(cls):
        cls.commands = [c for c in all_commands() if EXTGLOB_ARRAY_FORM.search(c)]
        H._lex_extglob = True

    @classmethod
    def tearDownClass(cls):
        H._lex_extglob = False
        H._lex_extglob_met = False

    def test_the_forms_are_there_to_check(self):
        self.assertGreaterEqual(len(self.commands), 7)


if __name__ == "__main__":
    unittest.main()
