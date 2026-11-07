"""Document contract tests for plan-feature-docs-route/task0002: the planner
contract owns the other-feature document route and the
`planning_inputs.feature_docs_correction` value.

Covers task0002 Acceptance Criteria
(feature-docs/plan-feature-docs-route/tasks/task0002.md):

- AC-1 (`TestAC1TwoStageRoute`): `## Other-feature documents` states the
  stage-1 request result and its admission, the orchestrator's grant and
  re-dispatch, the stage-2 fix declaration with its equality to the written
  grants, and that validation, the `workflow.yaml` update and the commit stay
  with the orchestrator before `create-plan` completes.
- AC-2 (`TestAC2ScopeRule`): the same section states the four conditions of
  the scope rule, the out-of-scope paths, the `blocked` outcome and the three
  validator codes.
- AC-3 (`TestAC3UntrustedAndRedaction`): the same section cites the worker
  envelope's Untrusted-Input Handling and Doc Redaction sections.
- AC-4 (`TestAC4CorrectionSubsection`): the `### feature_docs_correction
  (dispatch-resolved value)` subsection.
- AC-5 (`TestAC5DigestInputs`): `## digest_inputs` lists each
  `amend_other_feature` target, gains the `value_inputs` member and keeps the
  overlap paragraph's four path-like spans.
- AC-6 (`TestAC6WritePolicyPayloadAndPins`): no "six actions" wording, the
  `completed` payload section, and the refreshed heading pins of
  `tests/test_scenario_id_planner_docs.py`.
- AC-7 is the whole suite (`python3 -m unittest discover -s tests`); it has no
  test of its own.

Convention: standard library `unittest` only, no other test module imported.
Every assertion reads the section it concerns on whitespace-flattened text,
and every custom matcher has a negative proof against an in-test sample (a
sample missing one required element). The checker script is loaded by path
for the digest-sentence and gate-id rules; this module never writes under
`em-workflow/`.
"""

import ast
import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "planner-contract.md"
CHECKER_PATH = PLUGIN_ROOT / "scripts" / "check-plugin-invariants.py"
SCENARIO_PIN_TEST_PATH = REPO_ROOT / "tests" / "test_scenario_id_planner_docs.py"

OTHER_FEATURE_HEADING = "## Other-feature documents"
CORRECTION_HEADING = "### feature_docs_correction (dispatch-resolved value)"
PATH_CORRECTION_HEADING = "### path_correction (dispatch-resolved value)"
PLANNING_INPUTS_HEADING = "## Additional input: `planning_inputs`"
TASK_MD_APPEND_HEADING = "### Minimal-tier `TASK.md` append (SC-3)"
BUNDLING_HEADING = "## Question packet bundling rule"
DIGEST_INPUTS_HEADING = "## digest_inputs"
COMPLETED_HEADING = "## `completed` payload"
SCOPE_HEADING = "## Scope & concurrency assumption"
SCENARIO_HEADING = "## Scenario ID form"
GATE_VOCAB_HEADING = "## Gate option vocabulary"

THREE_CODES = (
    "other-feature-doc-scope",
    "other-feature-doc-request",
    "other-feature-doc-fix",
)
OUT_OF_SCOPE_TOKENS = (
    "`feature-docs/LESSONS.md`",
    "`workflow.yaml`",
    "`phase-state/`",
    "`tasks/`",
    "`design/mockups/`",
)
OVERLAP_PATH_LIKE_SPANS = {
    "IMPLEMENTATION.md",
    "VERIFICATION.md",
    "THREAT-MODEL.md",
    "tasks/",
}
ENVELOPE_CITATION = "references/contracts/worker-envelope.md"


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _flat(text):
    """Collapse every whitespace run to one space, so an anchor survives the
    documents' hard line wrapping."""
    return re.sub(r"\s+", " ", text).strip()


_HEADING_RE = re.compile(r"^(#{1,6}) \S")


def _headings(text):
    """(line_index, level, line) for every Markdown heading outside a fenced
    code block."""
    in_fence = False
    found = []
    for index, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((index, len(match.group(1)), line))
    return found


def _heading_lines(text, level):
    return [line for _i, lvl, line in _headings(text) if lvl == level]


def _section(text, heading):
    """Body of the section opened by `heading` (heading line excluded), up to
    the next heading of the same or a shallower level. Raises AssertionError
    when the heading is absent or appears more than once."""
    lines = text.split("\n")
    heads = _headings(text)
    starts = [i for i, _lvl, line in heads if line == heading]
    if len(starts) != 1:
        raise AssertionError(
            "expected exactly one heading line %r, found %d" % (heading, len(starts))
        )
    start = starts[0]
    level = next(lvl for i, lvl, _line in heads if i == start)
    end = len(lines)
    for i, lvl, _line in heads:
        if i > start and lvl <= level:
            end = i
            break
    return "\n".join(lines[start + 1 : end])


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", _flat(text)) if s]


def _paragraphs(text):
    return [_flat(block) for block in re.split(r"\n\s*\n", text) if block.strip()]


_BULLET_START = re.compile(r"^- ")
_NUMBERED_START = re.compile(r"^\d+\. ")


def _items(block, start_re):
    """Flattened list items of `block` whose first line matches `start_re`.
    An item ends at a blank line or at the next item."""
    items = []
    current = None
    for line in block.split("\n"):
        if start_re.match(line):
            if current is not None:
                items.append(current)
            current = [start_re.sub("", line, count=1)]
        elif not line.strip():
            if current is not None:
                items.append(current)
                current = None
        elif current is not None:
            current.append(line)
    if current is not None:
        items.append(current)
    return [_flat(" ".join(parts)) for parts in items]


def _bullets(block):
    return _items(block, _BULLET_START)


def _numbered(block):
    return _items(block, _NUMBERED_START)


def _forge(sample, needle, replacement=""):
    """`sample` with the first occurrence of `needle` replaced, matching the
    needle's words across any line wrapping. Fails when the needle is absent,
    so a proof cannot pass because its edit missed."""
    words = needle.split()
    pattern = r"\s+".join(re.escape(word) for word in words)
    forged, count = re.subn(pattern, lambda _m: replacement, sample, count=1)
    if count != 1:
        raise AssertionError("proof edit missed: %r" % needle)
    return forged


def _only(candidates, what):
    _require(len(candidates) == 1, "expected exactly one %s, found %d" % (what, len(candidates)))
    return candidates[0]


def _holds_all(text, needles, what):
    flat = _flat(text)
    for needle in needles:
        _require(needle in flat, "%s lacks %r" % (what, needle))
    return flat


def _sentence_with(text, *needles):
    """The sentences of `text` holding every needle."""
    return [s for s in _sentences(text) if all(n in s for n in needles)]


def _fenced_blocks(text):
    return re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL)


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "_check_plugin_invariants_for_other_feature_docs", CHECKER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cpi = _load_checker()


# ---------------------------------------------------------------------------
# AC-1 matchers: the two-stage route.
# ---------------------------------------------------------------------------

_ADMITTED_WITHOUT_GRANTS_RE = re.compile(
    r"admitted only [^.]*\b(?:without|no)\b[^.]*`amend_other_feature` targets?"
)
_ADMITTED_WITH_GRANTS_RE = re.compile(
    r"admitted only [^.]*\bcarries\b[^.]*`amend_other_feature` targets?"
)


def check_request_result(section):
    """The stage-1 request result: shape and admission."""
    item = _only(
        [b for b in _bullets(section) if "`other_feature_doc_requests`" in b],
        "bullet naming `other_feature_doc_requests`",
    )
    _holds_all(
        item,
        (
            "`status: completed`",
            "empty `written_artifacts`",
            "null `workflow_patch`",
            "only `other_feature_doc_requests`",
            "exactly `path` and `reason`",
        ),
        "the request-result bullet",
    )
    _require(
        _ADMITTED_WITHOUT_GRANTS_RE.search(item) is not None,
        "the request-result bullet does not say it is admitted only without "
        "`amend_other_feature` targets",
    )
    return item


def check_grant(section):
    """The orchestrator's grant and the re-dispatch."""
    item = _only(
        [b for b in _bullets(section) if "re-dispatches" in b],
        "bullet naming the re-dispatch",
    )
    _holds_all(
        item,
        (
            "orchestrator",
            "one `amend_other_feature` target per",
            "`expect_digest`",
            "a new `request_id`",
            "`references/phases/create-plan-phase.md`",
            "`## 4. Planner dispatch`",
        ),
        "the grant bullet",
    )
    return item


def check_fix_declaration(section):
    """The stage-2 fix declaration and its equality with the written grants."""
    item = _only(
        [b for b in _bullets(section) if "`payload.other_feature_doc_fixes`" in b],
        "bullet naming `payload.other_feature_doc_fixes`",
    )
    _holds_all(
        item,
        (
            "exactly `path`, `change` and `reason`",
            "`written_artifacts`",
            "equal",
            "granted paths",
        ),
        "the fix-declaration bullet",
    )
    _require(
        _ADMITTED_WITH_GRANTS_RE.search(item) is not None,
        "the fix-declaration bullet does not say it is admitted only when the "
        "dispatch carries `amend_other_feature` targets",
    )
    return item


def check_orchestrator_keeps(section):
    """Validation, the workflow.yaml update and the commit stay with the
    orchestrator, before create-plan completes."""
    hits = _sentence_with(section, "before `create-plan` completes")
    sentence = _only(hits, "sentence ending with 'before `create-plan` completes'")
    _holds_all(
        sentence,
        ("orchestrator", "Validation", "the `workflow.yaml` update", "the commit"),
        "the orchestrator-owned-steps sentence",
    )
    return sentence


# ---------------------------------------------------------------------------
# AC-2 matchers: the scope rule, the out-of-scope paths, the codes.
# ---------------------------------------------------------------------------


def check_scope_rule(section):
    """Exactly four numbered conditions, each holding its required elements."""
    items = _numbered(section)
    _require(len(items) == 4, "expected four scope-rule conditions, found %d" % len(items))
    one, two, three, four = items
    for needle in ("non-empty", "not absolute", "NUL", "`..`"):
        _require(needle in one, "condition 1 lacks %r" % needle)
    for needle in ("three segments", "exactly `feature-docs`", "is not the feature being planned"):
        _require(needle in two, "condition 2 lacks %r" % needle)
    for needle in ("`.md`", "case-sensitive"):
        _require(needle in three, "condition 3 lacks %r" % needle)
    for needle in ("`phase-state/`", "`tasks/`", "`design/mockups/`", "by segments"):
        _require(needle in four, "condition 4 lacks %r" % needle)
    return items


def check_out_of_scope(section):
    hits = _sentence_with(section, "Out of scope")
    sentence = _only(hits, "sentence opening the out-of-scope list")
    for token in OUT_OF_SCOPE_TOKENS:
        _require(token in sentence, "the out-of-scope sentence lacks %s" % token)
    return sentence


def check_blocked_outcomes(section):
    never = _only(
        _sentence_with(section, "out-of-scope path", "never granted"),
        "sentence saying an out-of-scope path is never granted",
    )
    _require("never written" in never, "the sentence lacks 'never written'")
    planner = _sentence_with(section, "out-of-scope path", "`blocked`", "naming the path")
    _require(len(planner) == 1, "expected one sentence with `blocked` naming the path")
    stage2 = _sentence_with(section, "not granted", "`blocked`", "naming the path")
    _require(len(stage2) == 1, "expected one stage-2 sentence with `blocked` naming the path")
    return never


def check_codes(section):
    """Each of the three codes is named in a bullet of its own."""
    bullets = _bullets(section)
    for code in THREE_CODES:
        hits = [b for b in bullets if b.startswith("`%s`" % code)]
        _require(len(hits) == 1, "expected one bullet opening with `%s`" % code)
    return THREE_CODES


# ---------------------------------------------------------------------------
# AC-3 matchers: untrusted content and redaction.
# ---------------------------------------------------------------------------


def check_untrusted_and_redaction(section):
    untrusted = _only(
        _sentence_with(section, "untrusted", "Untrusted-Input Handling"),
        "sentence classifying the content as untrusted",
    )
    _require(ENVELOPE_CITATION in untrusted, "the untrusted sentence does not cite the envelope")
    redaction = _only(
        _sentence_with(section, "Doc Redaction"),
        "sentence citing Doc Redaction",
    )
    _require(ENVELOPE_CITATION in redaction, "the redaction sentence does not cite the envelope")
    return untrusted, redaction


# ---------------------------------------------------------------------------
# Negative-proof samples.
# ---------------------------------------------------------------------------

GOOD_ROUTE = """\
- **Stage 1: the request result.** When the plan needs another feature's
  document changed and the dispatch carries no `amend_other_feature` target,
  the planner writes nothing and returns `status: completed` with empty
  `written_artifacts`, a null `workflow_patch` and a payload holding only
  `other_feature_doc_requests`: a non-empty list of mappings with exactly
  `path` and `reason`. The request result is admitted only on a dispatch
  without `amend_other_feature` targets.
- **Grant and re-dispatch.** The orchestrator adds one `amend_other_feature`
  target per in-scope path, sets `expect_digest` to the digest of that path at
  dispatch, and re-dispatches under a new `request_id`. It is owned by
  `references/phases/create-plan-phase.md`, section `## 4. Planner dispatch`.
- **Stage 2: the fix declaration.** The planner declares each amendment in
  `payload.other_feature_doc_fixes`: a list of mappings with exactly `path`,
  `change` and `reason`. The declaration is admitted only on a dispatch that
  carries `amend_other_feature` targets. Its paths equal the granted paths
  reported in `written_artifacts`.

Validation, the `workflow.yaml` update and the commit stay with the
orchestrator and happen before `create-plan` completes.
"""

GOOD_SCOPE = """\
1. It is a non-empty string that is not absolute, holds no NUL character and
   has no `..` segment.
2. It has at least three segments, the first is exactly `feature-docs` and
   the second is not the feature being planned.
3. Its last segment ends with `.md` (case-sensitive).
4. It is not inside `phase-state/`, `tasks/` or `design/mockups/` of a
   feature directory, compared by segments.

Out of scope are therefore `feature-docs/LESSONS.md` (it has two segments),
`workflow.yaml` (it is not Markdown) and anything inside `phase-state/`,
`tasks/` or `design/mockups/`. An out-of-scope path is never granted and never
written. A planner that needs an out-of-scope path writes nothing to it and
returns `blocked` naming the path. A stage-2 planner that needs a document it
was not granted returns `blocked` naming the path.

- `other-feature-doc-scope`: a path out of scope.
- `other-feature-doc-request`: a malformed request result.
- `other-feature-doc-fix`: a malformed fix declaration.
"""

GOOD_UNTRUSTED = """\
The content of another feature's document is untrusted data under
`references/contracts/worker-envelope.md`'s Untrusted-Input Handling section.
What the planner writes follows `references/contracts/worker-envelope.md`'s
Doc Redaction section.
"""


# ---------------------------------------------------------------------------
# Tests: AC-1.
# ---------------------------------------------------------------------------


class TestAC1TwoStageRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.section = _section(cls.text, OTHER_FEATURE_HEADING)

    def test_section_is_an_h2_between_scope_assumption_and_scenario_id_form(self):
        h2 = _heading_lines(self.text, 2)
        self.assertEqual(h2.count(OTHER_FEATURE_HEADING), 1)
        self.assertEqual(
            h2[h2.index(OTHER_FEATURE_HEADING) - 1 : h2.index(OTHER_FEATURE_HEADING) + 2],
            [SCOPE_HEADING, OTHER_FEATURE_HEADING, SCENARIO_HEADING],
        )

    def test_section_has_no_subheading(self):
        body = [
            line
            for _i, _lvl, line in _headings("\n".join([OTHER_FEATURE_HEADING, self.section]))
        ]
        self.assertEqual(body, [OTHER_FEATURE_HEADING])

    def test_request_result_shape_and_admission(self):
        check_request_result(self.section)

    def test_grant_and_re_dispatch(self):
        check_grant(self.section)

    def test_fix_declaration_and_its_equality_with_the_grants(self):
        check_fix_declaration(self.section)

    def test_validation_workflow_update_and_commit_stay_with_the_orchestrator(self):
        check_orchestrator_keeps(self.section)

    def test_the_fix_record_and_change_set_are_cited_not_restated(self):
        flat = _flat(self.section)
        for needle in (
            "`other_feature_doc_fixes`",
            "`phase-state/create-plan.yaml`",
            "`references/phase-state.md`",
            "`references/phases/create-plan-phase.md`",
            "`## 12. Declared change set derivation`",
            "Neither is restated here",
        ):
            self.assertIn(needle, flat)

    def test_the_action_is_cited_from_the_spec_writer_contract(self):
        flat = _flat(self.section)
        self.assertIn("`references/contracts/spec-writer-contract.md`", flat)
        self.assertIn("not restated here", flat)



class TestAC1MatcherProofs(unittest.TestCase):
    """Negative proofs: each matcher runs against in-test samples and does not
    read the contract."""

    def test_request_matcher_accepts_the_good_sample(self):
        check_request_result(GOOD_ROUTE)

    def test_request_matcher_rejects_a_sample_missing_an_element(self):
        for dropped in (
            "`status: completed` ",
            "empty `written_artifacts`, ",
            "a null `workflow_patch` and ",
            "exactly\n  `path` and `reason`",
        ):
            with self.subTest(dropped=dropped):
                forged = _forge(GOOD_ROUTE, dropped, "")
                self.assertNotEqual(forged, GOOD_ROUTE)
                with self.assertRaises(AssertionError):
                    check_request_result(forged)

    def test_request_matcher_rejects_a_sample_without_the_admission(self):
        forged = _forge(
            GOOD_ROUTE,
            "The request result is admitted only on a dispatch without `amend_other_feature` targets.",
            "The request result is admitted on any dispatch.",
        )
        self.assertNotEqual(forged, GOOD_ROUTE)
        with self.assertRaises(AssertionError):
            check_request_result(forged)

    def test_grant_matcher_accepts_the_good_sample_and_rejects_a_missing_element(self):
        check_grant(GOOD_ROUTE)
        for dropped in (
            "one `amend_other_feature`\n  target per",
            "`expect_digest`",
            "a new `request_id`",
            "`## 4. Planner dispatch`",
        ):
            with self.subTest(dropped=dropped):
                forged = _forge(GOOD_ROUTE, dropped, "x")
                self.assertNotEqual(forged, GOOD_ROUTE)
                with self.assertRaises(AssertionError):
                    check_grant(forged)

    def test_fix_matcher_accepts_the_good_sample_and_rejects_a_missing_element(self):
        check_fix_declaration(GOOD_ROUTE)
        for dropped in (
            "exactly `path`, `change` and `reason`",
            "reported in `written_artifacts`",
            "Its paths equal the granted paths",
            "carries `amend_other_feature` targets",
        ):
            with self.subTest(dropped=dropped):
                forged = _forge(GOOD_ROUTE, dropped, "x")
                self.assertNotEqual(forged, GOOD_ROUTE)
                with self.assertRaises(AssertionError):
                    check_fix_declaration(forged)

    def test_orchestrator_matcher_accepts_the_good_sample_and_rejects_a_missing_element(self):
        check_orchestrator_keeps(GOOD_ROUTE)
        for dropped in (
            "Validation, ",
            "the `workflow.yaml` update and ",
            "orchestrator and happen before",
            "before `create-plan` completes",
        ):
            with self.subTest(dropped=dropped):
                forged = _forge(GOOD_ROUTE, dropped, "x ")
                self.assertNotEqual(forged, GOOD_ROUTE)
                with self.assertRaises(AssertionError):
                    check_orchestrator_keeps(forged)


# ---------------------------------------------------------------------------
# Tests: AC-2.
# ---------------------------------------------------------------------------


class TestAC2ScopeRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.section = _section(cls.text, OTHER_FEATURE_HEADING)

    def test_four_conditions(self):
        check_scope_rule(self.section)

    def test_out_of_scope_paths_are_named(self):
        check_out_of_scope(self.section)

    def test_out_of_scope_path_is_never_granted_or_written_and_blocked_names_it(self):
        check_blocked_outcomes(self.section)

    def test_the_three_codes_are_named(self):
        check_codes(self.section)



class TestAC2MatcherProofs(unittest.TestCase):
    """Negative proofs: each matcher runs against in-test samples and does not
    read the contract."""

    def test_scope_matcher_accepts_the_good_sample(self):
        check_scope_rule(GOOD_SCOPE)

    def test_scope_matcher_rejects_a_sample_missing_a_condition(self):
        forged = GOOD_SCOPE.replace(
            "3. Its last segment ends with `.md` (case-sensitive).\n", ""
        )
        self.assertNotEqual(forged, GOOD_SCOPE)
        with self.assertRaises(AssertionError):
            check_scope_rule(forged)

    def test_scope_matcher_rejects_a_sample_with_a_condition_missing_its_element(self):
        for dropped in (
            "not absolute, ",
            "holds no NUL character and\n   has no `..` segment",
            "is not the feature being planned",
            "(case-sensitive)",
            "`design/mockups/` of a\n   feature directory, compared by segments",
        ):
            with self.subTest(dropped=dropped):
                forged = _forge(GOOD_SCOPE, dropped, "x")
                self.assertNotEqual(forged, GOOD_SCOPE)
                with self.assertRaises(AssertionError):
                    check_scope_rule(forged)

    def test_scope_matcher_rejects_a_fifth_condition(self):
        forged = GOOD_SCOPE.replace(
            "\nOut of scope", "5. It exists.\n\nOut of scope", 1
        )
        with self.assertRaises(AssertionError):
            check_scope_rule(forged)

    def test_out_of_scope_matcher_accepts_the_good_sample_and_rejects_a_missing_path(self):
        check_out_of_scope(GOOD_SCOPE)
        for token in OUT_OF_SCOPE_TOKENS:
            with self.subTest(token=token):
                forged = GOOD_SCOPE.replace(token, "`x`")
                with self.assertRaises(AssertionError):
                    check_out_of_scope(forged)

    def test_blocked_matcher_accepts_the_good_sample_and_rejects_a_missing_element(self):
        check_blocked_outcomes(GOOD_SCOPE)
        for needle, replacement in (
            ("never granted and never written", "never granted"),
            (
                "returns `blocked` naming the path. A stage-2 planner",
                "stops. A stage-2 planner",
            ),
            ("was not granted returns `blocked` naming the path", "was not granted stops"),
        ):
            with self.subTest(needle=needle):
                forged = _forge(GOOD_SCOPE, needle, replacement)
                self.assertNotEqual(forged, GOOD_SCOPE)
                with self.assertRaises(AssertionError):
                    check_blocked_outcomes(forged)

    def test_codes_matcher_accepts_the_good_sample_and_rejects_a_missing_code(self):
        check_codes(GOOD_SCOPE)
        for code in THREE_CODES:
            with self.subTest(code=code):
                forged = GOOD_SCOPE.replace("`%s`:" % code, "`other`:")
                with self.assertRaises(AssertionError):
                    check_codes(forged)


# ---------------------------------------------------------------------------
# Tests: AC-3.
# ---------------------------------------------------------------------------


class TestAC3UntrustedAndRedaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.section = _section(cls.text, OTHER_FEATURE_HEADING)

    def test_untrusted_content_and_redaction_are_cited(self):
        check_untrusted_and_redaction(self.section)

    def test_section_does_not_restate_redaction(self):
        flat = _flat(self.section)
        self.assertNotIn("Notion", flat)
        self.assertNotIn("home directory", flat)



class TestAC3MatcherProofs(unittest.TestCase):
    """Negative proofs: the matcher runs against in-test samples and does not
    read the contract."""

    def test_matcher_accepts_the_good_sample(self):
        check_untrusted_and_redaction(GOOD_UNTRUSTED)

    def test_matcher_rejects_a_sample_missing_an_element(self):
        for dropped in (
            "is untrusted data under",
            "Untrusted-Input Handling",
            "Doc Redaction",
        ):
            with self.subTest(dropped=dropped):
                forged = _forge(GOOD_UNTRUSTED, dropped, "x")
                self.assertNotEqual(forged, GOOD_UNTRUSTED)
                with self.assertRaises(AssertionError):
                    check_untrusted_and_redaction(forged)

    def test_matcher_rejects_a_sample_that_does_not_cite_the_envelope(self):
        forged = GOOD_UNTRUSTED.replace(ENVELOPE_CITATION, "references/x.md")
        with self.assertRaises(AssertionError):
            check_untrusted_and_redaction(forged)


# ---------------------------------------------------------------------------
# AC-4 matchers: the correction subsection.
# ---------------------------------------------------------------------------


def _bullet_with(section, token):
    return _only([b for b in _bullets(section) if token in b], "bullet holding %s" % token)


def check_correction_subsection(section):
    flat = _holds_all(
        section,
        (
            "`planning_inputs.feature_docs_correction`",
            "`targets`",
            "`task_id`",
            "`path`",
        ),
        "the shape statement",
    )
    prose = re.sub(r"```.*?```", "", section, flags=re.DOTALL)
    _holds_all(prose, ("and null on every other dispatch",), "the prose")
    _require("exactly `task_id` and `path`" in flat, "the shape lacks 'exactly `task_id` and `path`'")
    exclusive = _bullet_with(section, "`path_correction`")
    _require("never non-null" in exclusive, "the exclusivity bullet lacks 'never non-null'")
    digest = _bullet_with(section, "`value_inputs`")
    _require("member" in digest, "the digest bullet lacks 'member'")
    policy = _bullet_with(section, "`write_policy.targets`")
    _holds_all(
        policy,
        (
            "`replace_own`",
            "IMPLEMENTATION.md, VERIFICATION.md and each target's task plan",
            "`amend_other_feature`",
            "`allowed_write_roots` is empty",
        ),
        "the write_policy bullet",
    )
    output = _bullet_with(section, "`tasks_patch.feature_docs_removals`")
    _holds_all(
        output,
        (
            "`replace_planning`",
            "`references/workflow-patch.md`",
            "`## Feature-docs correction`",
            "`payload.task_index` is empty",
        ),
        "the output bullet",
    )
    process = _bullet_with(section, "`agents/implementation-planner.md`")
    _require(
        "`## Feature-docs correction`" in process,
        "the process bullet does not cite `## Feature-docs correction`",
    )
    return flat


GOOD_CORRECTION = """\
`planning_inputs.feature_docs_correction` is present on the correction
dispatch and null on every other dispatch.

```yaml
feature_docs_correction:           # null on every other dispatch
  targets:
    - task_id: task0004
      path: <repository-relative path>
```

- **Shape**: `targets` is a list of mappings with exactly `task_id` and `path`.
- **Exclusive**: the value is never non-null together with `path_correction`.
- **Digest**: the orchestrator includes it, when present, as a
  `value_inputs` member of this worker's `input_digest`.
- **write_policy**: `write_policy.targets` has action `replace_own` for
  IMPLEMENTATION.md, VERIFICATION.md and each target's task plan, plus the
  `amend_other_feature` targets after a request. `allowed_write_roots` is empty.
- **Output**: `replace_planning` carrying `tasks_patch.feature_docs_removals`,
  owned by `references/workflow-patch.md`, section
  `## Feature-docs correction`. `payload.task_index` is empty.
- **Process**: owned by `agents/implementation-planner.md`, section
  `## Feature-docs correction`.
"""


class TestAC4CorrectionSubsection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.subsection = _section(cls.text, CORRECTION_HEADING)

    def test_heading_is_an_h3_between_path_correction_and_bundling_rule(self):
        heads = [(lvl, line) for _i, lvl, line in _headings(self.text)]
        names = [line for _lvl, line in heads]
        self.assertEqual(names.count(CORRECTION_HEADING), 1)
        index = names.index(CORRECTION_HEADING)
        self.assertEqual(heads[index][0], 3)
        self.assertEqual(names[index - 1], PATH_CORRECTION_HEADING)
        self.assertEqual(names[index + 1], BUNDLING_HEADING)

    def test_subsection_states_every_element(self):
        check_correction_subsection(self.subsection)

    def test_planning_inputs_yaml_block_gains_one_commented_line(self):
        planning_inputs = _section(self.text, PLANNING_INPUTS_HEADING)
        block = _fenced_blocks(planning_inputs)[0]
        lines = [
            line for line in block.split("\n") if "feature_docs_correction" in line
        ]
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], r"^\s+feature_docs_correction:.*#")

    def test_path_correction_subsection_keeps_its_bullets(self):
        section = _section(self.text, PATH_CORRECTION_HEADING)
        for label in ("**Shape**", "**Untrusted**", "**Digest**", "**write_policy**", "**Output**", "**Process**"):
            self.assertIn(label, section)



class TestAC4MatcherProofs(unittest.TestCase):
    """Negative proofs: the matcher runs against in-test samples and does not
    read the contract."""

    def test_matcher_accepts_the_good_sample(self):
        check_correction_subsection(GOOD_CORRECTION)

    def test_matcher_rejects_a_sample_missing_an_element(self):
        for dropped in (
            "and null on every other dispatch.",
            "exactly `task_id` and `path`",
            "never non-null together with `path_correction`",
            "as a `value_inputs` member",
            "`replace_own` for\n  IMPLEMENTATION.md, VERIFICATION.md and each target's task plan",
            "plus the\n  `amend_other_feature` targets after a request",
            "`allowed_write_roots` is empty",
            "`tasks_patch.feature_docs_removals`",
            "`references/workflow-patch.md`",
            "`payload.task_index` is empty",
            "`agents/implementation-planner.md`",
        ):
            with self.subTest(dropped=dropped):
                forged = _forge(GOOD_CORRECTION, dropped, "x")
                self.assertNotEqual(forged, GOOD_CORRECTION)
                with self.assertRaises(AssertionError):
                    check_correction_subsection(forged)


# ---------------------------------------------------------------------------
# AC-5 matchers: digest_inputs.
# ---------------------------------------------------------------------------

_VALUE_INPUTS_FEATURE_DOCS_RE = re.compile(
    r"`value_inputs`[^.]*`(?:planning_inputs\.)?feature_docs_correction`[^.]*\bpresent\b"
)
_ACTION_NAMES_RE = re.compile(
    r"\b(?:replace_own|replace_authorized|extend_only|regenerate|preserve)\b|`create`"
)
_CHANGE_KINDS_RE = re.compile(r"\b(?:created|modified|deleted)\b")
_SUBSTITUTION_RE = re.compile(
    r"\babsent\b|dispatch-time value|\bsubstitut\w*|\bmember\b|self-write set",
    re.IGNORECASE,
)


def _path_like_spans(paragraph):
    spans = re.findall(r"`([^`]+)`", paragraph)
    return {span for span in spans if "/" in span or "." in span}


def overlap_paragraph(section):
    return _only(
        [
            p
            for p in _paragraphs(section)
            if ENVELOPE_CITATION in p
            and "Rule R1" in p
            and "Recomputation and comparison timing" in p
        ],
        "overlap paragraph citing Rule R1",
    )


def check_overlap_paragraph(paragraph):
    _require(paragraph.startswith("The orchestrator"), "the paragraph does not open with 'The orchestrator'")
    _require("`amend_other_feature`" in paragraph, "the paragraph does not name `amend_other_feature`")
    named = _path_like_spans(paragraph) - {ENVELOPE_CITATION}
    _require(
        named == OVERLAP_PATH_LIKE_SPANS,
        "the path-like spans are %r, expected %r" % (sorted(named), sorted(OVERLAP_PATH_LIKE_SPANS)),
    )
    _require(
        _ACTION_NAMES_RE.search(paragraph) is None,
        "the paragraph names a write_policy action other than `amend_other_feature`",
    )
    _require(_CHANGE_KINDS_RE.search(paragraph) is None, "the paragraph names a change kind")
    _require(_SUBSTITUTION_RE.search(paragraph) is None, "the paragraph words out the substitution")
    return named


def check_value_inputs_sentence(section):
    _require(
        _VALUE_INPUTS_FEATURE_DOCS_RE.search(_flat(section)) is not None,
        "no sentence says `value_inputs` gains `feature_docs_correction` when present",
    )


def check_target_member_bullet(section):
    hits = [b for b in _bullets(section) if "each `amend_other_feature` target" in b]
    return _only(hits, "bullet listing each `amend_other_feature` target")


GOOD_OVERLAP = (
    "The orchestrator applies the self-write rule of "
    "`references/contracts/worker-envelope.md`, Rule R1, \"Recomputation and "
    "comparison timing\", when it recomputes `input_digest` on this worker's "
    "return. The overlap between this worker's `digest_inputs` and the paths "
    "its `write_policy` lets it write is `IMPLEMENTATION.md`, "
    "`VERIFICATION.md`, `THREAT-MODEL.md` and `tasks/`, together with the "
    "document of each `amend_other_feature` target of the dispatch."
)


class TestAC5DigestInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.section = _section(cls.text, DIGEST_INPUTS_HEADING)

    def test_each_amend_other_feature_target_is_a_listed_member(self):
        check_target_member_bullet(self.section)

    def test_value_inputs_gains_the_correction_value_when_present(self):
        check_value_inputs_sentence(self.section)

    def test_overlap_paragraph_names_the_targets_and_keeps_its_four_spans(self):
        check_overlap_paragraph(overlap_paragraph(self.section))

    def test_digest_sentences_of_the_new_text_name_the_orchestrator_or_are_negated(self):
        new_text = "\n\n".join(
            [
                _section(self.text, OTHER_FEATURE_HEADING),
                _section(self.text, CORRECTION_HEADING),
                self.section,
            ]
        )
        violations = [
            sentence
            for sentence in cpi._sentences(new_text)
            if cpi.DIGEST_TERM_RE.search(sentence)
            and not cpi.ORCHESTRATOR_RE.search(sentence)
            and not cpi.NEGATION_RE.search(sentence)
        ]
        self.assertEqual(violations, [])
        self.assertEqual(cpi.find_worker_directed_digest_instructions(new_text, ()), [])

    # -- negative proofs ------------------------------------------------

    def test_overlap_matcher_accepts_the_good_sample(self):
        self.assertEqual(check_overlap_paragraph(GOOD_OVERLAP), OVERLAP_PATH_LIKE_SPANS)

    def test_overlap_matcher_rejects_an_extra_path_like_span(self):
        forged = GOOD_OVERLAP.replace(
            "of the dispatch.", "of the dispatch and `feature-docs/x/OTHER.md`."
        )
        with self.assertRaises(AssertionError):
            check_overlap_paragraph(forged)

    def test_overlap_matcher_rejects_a_missing_span(self):
        forged = GOOD_OVERLAP.replace("`VERIFICATION.md`, ", "")
        with self.assertRaises(AssertionError):
            check_overlap_paragraph(forged)

    def test_overlap_matcher_rejects_a_sample_that_does_not_name_the_targets(self):
        forged = GOOD_OVERLAP.replace(
            ", together with the document of each `amend_other_feature` target of the dispatch", ""
        )
        with self.assertRaises(AssertionError):
            check_overlap_paragraph(forged)

    def test_overlap_matcher_rejects_a_changed_first_word(self):
        forged = GOOD_OVERLAP.replace("The orchestrator applies", "This contract applies", 1)
        with self.assertRaises(AssertionError):
            check_overlap_paragraph(forged)

    def test_overlap_matcher_rejects_another_action_or_a_change_kind(self):
        for extra in (" A `replace_own` target is included.", " The file may be modified."):
            with self.subTest(extra=extra):
                with self.assertRaises(AssertionError):
                    check_overlap_paragraph(GOOD_OVERLAP + extra)

    def test_overlap_paragraph_finder_rejects_a_text_without_the_citation(self):
        with self.assertRaises(AssertionError):
            overlap_paragraph("The orchestrator applies a rule.\n")

    def test_value_inputs_matcher_accepts_and_rejects_samples(self):
        good = (
            "`value_inputs` gains `planning_inputs.feature_docs_correction` as a "
            "member when it is present."
        )
        check_value_inputs_sentence(good)
        for bad in (
            "`value_inputs` has one member, `plugin_versioning`.",
            "`value_inputs` gains `planning_inputs.feature_docs_correction` as a member.",
            "`value_inputs` gains `planning_inputs.path_correction` as a member when it is present.",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(AssertionError):
                    check_value_inputs_sentence(bad)

    def test_member_bullet_matcher_accepts_and_rejects_samples(self):
        good = "- `IMPLEMENTATION.md`\n- each `amend_other_feature` target of the dispatch\n"
        self.assertIn("each `amend_other_feature` target", check_target_member_bullet(good))
        with self.assertRaises(AssertionError):
            check_target_member_bullet("- `IMPLEMENTATION.md`\n- `workflow.yaml`\n")


# ---------------------------------------------------------------------------
# AC-6 matchers and tests: wording, payload and the refreshed pins.
# ---------------------------------------------------------------------------

_SIX_ACTIONS_RE = re.compile(r"\bsix\s+(?:`[^`]*`\s+)?actions?\b", re.IGNORECASE)


def count_free_violations(text):
    return _SIX_ACTIONS_RE.findall(_flat(text))


def write_policy_paragraph(planning_inputs_lead):
    return _only(
        [p for p in _paragraphs(planning_inputs_lead) if p.startswith("`write_policy` is also part of the input")],
        "write_policy paragraph",
    )


def check_write_policy_sentence(paragraph):
    hits = _sentence_with(paragraph, "`amend_other_feature`", "only after")
    sentence = _only(hits, "sentence saying `amend_other_feature` targets appear only after a request")
    _require("`## Other-feature documents`" in sentence, "the sentence does not cite `## Other-feature documents`")
    return sentence


def check_completed_payload(section):
    flat = _flat(section)
    _require(
        "`payload.other_feature_doc_fixes`" in flat,
        "the section does not name `payload.other_feature_doc_fixes`",
    )
    block = _only(_fenced_blocks(section), "yaml block")
    commented = [
        line
        for line in block.split("\n")
        if line.lstrip().startswith("#") and "other_feature_doc_fixes" in line
    ]
    _require(commented, "the yaml block has no commented line for `other_feature_doc_fixes`")
    request = _sentence_with(section, "request result", "stage-1", "`completed`")
    _require(len(request) >= 1, "the section does not name the request result as the stage-1 `completed` shape")
    correction = _sentence_with(
        section, "`payload.task_index`", "feature-docs correction", CORRECTION_HEADING
    )
    _require(len(correction) >= 1, "the section does not cite the correction dispatch's task_index rule")
    return flat


GOOD_PAYLOAD = """\
```yaml
written_artifacts: [...]
payload:
  task_index:
    task0001: { title: ... }
  # other_feature_doc_fixes:         # stage 2 only
  #   - { path: ..., change: ..., reason: ... }
```

The request result is the stage-1 `completed` shape that
`## Other-feature documents` defines. It carries `other_feature_doc_requests`.
On the feature-docs correction dispatch, `payload.task_index` follows the rule
of "### feature_docs_correction (dispatch-resolved value)" above. A stage-2
result adds `payload.other_feature_doc_fixes`.
"""


def literal_list(source, name):
    """The list literal assigned to module-level `name` in `source`."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("no module-level assignment of %s" % name)


def check_heading_pins(source):
    """The scenario-id test's pin lists hold the two new headings, in document
    order, and a comment names this task."""
    h2 = literal_list(source, "CONTRACT_H2_BASE")
    h3 = literal_list(source, "CONTRACT_H3_BASE")
    _require(OTHER_FEATURE_HEADING in h2, "CONTRACT_H2_BASE lacks %r" % OTHER_FEATURE_HEADING)
    _require(
        h2.index(SCOPE_HEADING) + 1 == h2.index(OTHER_FEATURE_HEADING)
        and h2.index(OTHER_FEATURE_HEADING) + 1 == h2.index(GATE_VOCAB_HEADING),
        "CONTRACT_H2_BASE does not hold %r between its neighbours" % OTHER_FEATURE_HEADING,
    )
    _require(CORRECTION_HEADING in h3, "CONTRACT_H3_BASE lacks %r" % CORRECTION_HEADING)
    _require(
        h3.index(PATH_CORRECTION_HEADING) + 1 == h3.index(CORRECTION_HEADING),
        "CONTRACT_H3_BASE does not hold %r after the path_correction heading" % CORRECTION_HEADING,
    )
    _require(
        re.search(r"^\s*#.*plan-feature-docs-route/task0002", source, re.MULTILINE) is not None,
        "no comment names plan-feature-docs-route/task0002",
    )
    return h2, h3


GOOD_PIN_SOURCE = '''\
# Refreshed by plan-feature-docs-route/task0002: the two new headings.
CONTRACT_H2_BASE = [
    "## Scope & concurrency assumption",
    "## Other-feature documents",
    "## Gate option vocabulary",
]
CONTRACT_H3_BASE = [
    "### path_correction (dispatch-resolved value)",
    "### feature_docs_correction (dispatch-resolved value)",
]
'''


class TestAC6WritePolicyPayloadAndPins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)

    def test_no_six_actions_wording_anywhere_in_the_contract(self):
        self.assertEqual(count_free_violations(self.text), [])

    def test_the_envelope_status_count_is_not_an_actions_count(self):
        self.assertIn("the six `status` values", _flat(self.text))

    def test_write_policy_paragraph_says_the_targets_appear_only_after_a_request(self):
        lead = _section(self.text, PLANNING_INPUTS_HEADING).split(TASK_MD_APPEND_HEADING)[0]
        check_write_policy_sentence(write_policy_paragraph(lead))

    def test_completed_payload_names_the_request_result_and_the_fix_declaration(self):
        check_completed_payload(_section(self.text, COMPLETED_HEADING))

    def test_scenario_id_test_pins_are_refreshed_with_a_comment_naming_this_task(self):
        check_heading_pins(_read(SCENARIO_PIN_TEST_PATH))

    def test_the_refreshed_pins_follow_the_live_contract_headings(self):
        h2, h3 = check_heading_pins(_read(SCENARIO_PIN_TEST_PATH))
        live_h2 = [line for line in _heading_lines(self.text, 2) if line != SCENARIO_HEADING]
        self.assertEqual(h2, live_h2)
        self.assertEqual(h3, _heading_lines(self.text, 3))

    # -- negative proofs ------------------------------------------------

    def test_six_actions_matcher_flags_the_old_wordings_and_spares_the_status_count(self):
        for old in (
            "the six actions, the split",
            "The six `write_policy` actions",
            "six action",
        ):
            with self.subTest(old=old):
                self.assertNotEqual(count_free_violations(old), [])
        for clean in (
            "the six `status` values and their constraints",
            "the actions, the `targets` split",
        ):
            with self.subTest(clean=clean):
                self.assertEqual(count_free_violations(clean), [])

    def test_write_policy_matchers_accept_and_reject_samples(self):
        good = (
            "`write_policy` is also part of the input, in the common form. "
            "`amend_other_feature` targets appear only after a request, as "
            "`## Other-feature documents` states."
        )
        check_write_policy_sentence(write_policy_paragraph(good))
        for bad in (
            "`write_policy` is also part of the input. `amend_other_feature` targets appear always.",
            "`write_policy` is also part of the input. `amend_other_feature` targets appear only after a request.",
            "`write_policy` is also part of the input. Targets appear only after a request, per `## Other-feature documents`.",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(AssertionError):
                    check_write_policy_sentence(write_policy_paragraph(bad))

    def test_payload_matcher_accepts_the_good_sample_and_rejects_a_missing_element(self):
        check_completed_payload(GOOD_PAYLOAD)
        for dropped in (
            "  # other_feature_doc_fixes:         # stage 2 only\n",
            "stage-1 ",
            "On the feature-docs correction dispatch, `payload.task_index` follows the rule\nof "
            "\"### feature_docs_correction (dispatch-resolved value)\" above.",
        ):
            with self.subTest(dropped=dropped):
                forged = _forge(GOOD_PAYLOAD, dropped, "")
                self.assertNotEqual(forged, GOOD_PAYLOAD)
                with self.assertRaises(AssertionError):
                    check_completed_payload(forged)

    def test_pin_matcher_accepts_the_good_sample_and_rejects_a_stale_pin(self):
        check_heading_pins(GOOD_PIN_SOURCE)
        stale = GOOD_PIN_SOURCE.replace('    "## Other-feature documents",\n', "")
        with self.assertRaises(AssertionError):
            check_heading_pins(stale)
        misplaced = GOOD_PIN_SOURCE.replace(
            '    "## Scope & concurrency assumption",\n    "## Other-feature documents",\n',
            '    "## Other-feature documents",\n    "## Scope & concurrency assumption",\n',
        )
        with self.assertRaises(AssertionError):
            check_heading_pins(misplaced)
        uncommented = GOOD_PIN_SOURCE.replace(
            "# Refreshed by plan-feature-docs-route/task0002: the two new headings.\n", ""
        )
        with self.assertRaises(AssertionError):
            check_heading_pins(uncommented)


# ---------------------------------------------------------------------------
# Hygiene: the gate-id backtick rule, redaction, module imports.
# ---------------------------------------------------------------------------

_PHASE_YAML_NAME_RE = re.compile(r"^[a-z]+(?:-[a-z]+)*\.yaml$")


def bare_phase_yaml_spans(text):
    """Backtick spans that are a bare phase-state YAML file name (the
    Conventions' backtick token rule writes them with their directory)."""
    spans = re.findall(r"`([^`]+)`", text)
    return [s for s in spans if _PHASE_YAML_NAME_RE.match(s) and s != "workflow.yaml"]


class TestHygiene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.new_text = "\n\n".join(
            [_section(cls.text, OTHER_FEATURE_HEADING), _section(cls.text, CORRECTION_HEADING)]
        )

    def test_new_text_holds_no_gate_id_span_and_no_bare_phase_yaml_name(self):
        self.assertEqual(cpi.extract_gate_ids_from_text(self.new_text), set())
        self.assertEqual(bare_phase_yaml_spans(self.new_text), [])

    def test_the_contract_gate_ids_stay_within_the_three_of_its_vocabulary(self):
        self.assertLessEqual(
            cpi.extract_gate_ids_from_text(self.text),
            {
                "create-plan.tbd-resolution",
                "create-plan.license-conflict",
                "create-plan.existing-files",
            },
        )

    def test_new_text_adds_no_gate_and_no_question(self):
        flat = _flat(self.new_text)
        for word in ("gate_id", "gate ID", "AskUserQuestion", "question_packet"):
            self.assertNotIn(word, flat)

    def test_new_text_carries_no_notion_url_or_home_directory_path(self):
        for needle in ("notion.so", "notion.site", "/home/", "/Users/"):
            self.assertNotIn(needle, self.new_text)



class TestHygieneProofs(unittest.TestCase):
    def test_gate_id_matcher_proof(self):
        self.assertEqual(
            cpi.extract_gate_ids_from_text("the gate ID `create-plan.sample` is named"),
            {"create-plan.sample"},
        )
        self.assertEqual(bare_phase_yaml_spans("see `create-plan.yaml` here"), ["create-plan.yaml"])
        self.assertEqual(bare_phase_yaml_spans("see `phase-state/create-plan.yaml` and `workflow.yaml`"), [])

    def test_module_imports_the_standard_library_only(self):
        import sys

        tree = ast.parse(_read(Path(__file__).resolve()))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "relative import")
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())


if __name__ == "__main__":
    unittest.main()
