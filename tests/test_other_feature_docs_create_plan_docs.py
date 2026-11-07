"""Document contract tests for plan-feature-docs-route/task0009: how
create-plan grants other-feature documents, checks and records the declared
fixes, and reads them into the declared change set.

Covers task0009 Acceptance Criteria
(feature-docs/plan-feature-docs-route/tasks/task0009.md):

- AC-1 (`TestAC1GrantRule`): section 4 of
  `em-workflow/references/phases/create-plan-phase.md` states the grant rule.
- AC-2 (`TestAC2CompletionOutput`): section 7 names the stage-1 request result
  and `payload.other_feature_doc_fixes` and cites the planner contract.
- AC-3 (`TestAC3ScopeVerificationAndRecording`): section 8 states the layer 4
  coverage and the recording write; the return-time order paragraph is
  byte-identical.
- AC-4 (`TestAC4ValidatorImplementedList`): section 9's implemented list gains
  the three bullets; the not-implemented block and the canonical invocation
  block keep their pinned digests.
- AC-5 (`TestAC5ChangeSetDerivation`): section 12 reads the fix record as a
  fourth input, states its retention and its timing trigger, and no forbidden
  word appears from the section 12 heading to the end of the document.
- AC-6 (`TestAC6PhaseStateRecord`): `em-workflow/references/phase-state.md`
  defines `other_feature_doc_fixes` in its schema example and field table.
- AC-7 is the whole suite (`python3 -m unittest discover -s tests`); it has no
  test of its own.

Convention: standard library `unittest` only. Every assertion reads the
section it concerns on whitespace-flattened text. Every matcher has a negative
proof against an in-test sample that lacks one required element, so a proof
never depends on the live documents. The checker script and the pin constants
of `tests/test_scenario_id_planner_docs.py` are loaded by path (the module is
never imported by name); this module never writes under `em-workflow/`.
"""

import ast
import hashlib
import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PHASE_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
CHECKER_PATH = PLUGIN_ROOT / "scripts" / "check-plugin-invariants.py"
SECTION_9_PIN_TEST_PATH = REPO_ROOT / "tests" / "test_scenario_id_planner_docs.py"

SECTION_12_HEADING = "## 12. Declared change set derivation"
CONTRACT_CITATION = "`references/contracts/planner-contract.md`"
OTHER_FEATURE_SECTION = "`## Other-feature documents`"

# sha256 of the return-time order paragraph of section 8, computed from the
# base revision of this task. The paragraph stays byte-identical.
RETURN_TIME_ORDER_SHA256 = (
    "d31997483b681800feeaf6359a51d70c75839a2285be697f8e2d35ad47990f49"
)
RETURN_TIME_ORDER_START = "The return-time order on the planner's result is this one."

SECTION_9_INTRO = "mechanically implements only the"
SECTION_9_NOT_IMPLEMENTED_MARKER = (
    "The following are named as planning invariants but are **not implemented"
)
SECTION_9_CANONICAL_MARKER = "**Canonical validator invocation**"
SECTION_9_DIGEST_SOURCE_MARKER = "The `--digest-source` file holds"

# Words that never appear from the section 12 heading to the end of the
# document (pinned by tests/test_change_set_derivation.py and
# tests/test_scenario_id_planner_docs.py; this module restates the list).
LOWERCASE_FORBIDDEN = ("exclud", "subtract", "ignor", "除外")
CASE_SENSITIVE_FORBIDDEN = (
    "SUPERSET",
    "CONTAINED IN",
    "Initial-planning path",
    "protocol error on BOTH paths",
)

# Wording that belongs to the digest owner's definition or procedure; a site
# section that carries any of it restates the owner instead of citing it.
DIGEST_OWNER_WORDING = (
    "raw bytes",
    "raw-byte",
    "lowercase hex",
    "hexadecimal",
    "artifact-digest.py",
    "not_a_regular_file",
    "single-quoted",
    "single quote",
    "git hash-object",
)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _flat(text):
    """Collapse every whitespace run to one space, so an anchor survives the
    documents' hard line wrapping."""
    return re.sub(r"\s+", " ", text).strip()


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _only(candidates, what):
    _require(
        len(candidates) == 1,
        "expected exactly one %s, found %d" % (what, len(candidates)),
    )
    return candidates[0]


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
        match = re.match(r"^(#{1,6}) \S", line)
        if match:
            found.append((index, len(match.group(1)), line))
    return found


def _numbered_h2(text, number):
    """Body of the one `## {number}. ` section (heading line excluded), up to
    the next H2. Raises AssertionError unless exactly one such heading exists
    outside a fenced block."""
    lines = text.split("\n")
    h2 = [(i, line) for i, level, line in _headings(text) if level == 2]
    starts = [i for i, line in h2 if line.startswith("## %s. " % number)]
    _require(len(starts) == 1, "expected exactly one '## %s. ' heading" % number)
    start = starts[0]
    end = next((i for i, _line in h2 if i > start), len(lines))
    return "\n".join(lines[start + 1 : end])


def _paragraphs(text):
    """Raw paragraphs (blank-line separated, surrounding line breaks
    removed), fenced blocks kept whole."""
    return [
        block.strip("\n")
        for block in re.split(r"\n\s*\n", text)
        if block.strip()
    ]


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
    return _items(block, re.compile(r"^- "))


def _holds_all(text, needles, what):
    flat = _flat(text)
    for needle in needles:
        _require(_flat(needle) in flat, "%s lacks %r" % (what, needle))
    return flat


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


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cpi = _load_module("_check_plugin_invariants_for_task0009", CHECKER_PATH)


def _phase_section(number):
    return _numbered_h2(_read(PHASE_PATH), number)


def _section_12_to_end():
    text = _read(PHASE_PATH)
    _require(text.count(SECTION_12_HEADING) == 1, "section 12 heading not unique")
    return text[text.index(SECTION_12_HEADING) :]


def _label_paragraph(section, label):
    """The one raw paragraph of `section` that starts with `label`."""
    return _only(
        [p for p in _paragraphs(section) if p.lstrip().startswith(label)],
        "paragraph starting with %r" % label,
    )


def _assert_rejects_each_needle(testcase, check, sample, needles):
    """Negative proof: `check` accepts `sample` and rejects it once any one
    required needle is removed."""
    check(sample)
    for needle in needles:
        forged = _forge(sample, needle)
        with testcase.assertRaises(AssertionError, msg="accepted without %r" % needle):
            check(forged)


# ---------------------------------------------------------------------------
# AC-1: section 4, the grant rule.
# ---------------------------------------------------------------------------

GRANT_LABEL = "**Other-feature document grant.**"
GRANT_NEEDLES = (
    # The scope rule citation and the regular-file check.
    CONTRACT_CITATION,
    OTHER_FEATURE_SECTION,
    "the scope rule of that section",
    "exists as a regular file in the integration worktree",
    "A path that fails either check is not granted.",
    # One target per path, the digest, the pre-dispatch verification.
    "the orchestrator adds one `amend_other_feature` target to the `write_policy`",
    "`expect_digest` set to the digest the orchestrator computes for the path now",
    "The orchestrator verifies that target before the dispatch per "
    "`references/artifact-digest.md` (`Pre-dispatch verification`)",
    # One re-dispatch under a new request_id.
    "re-dispatches the planner once, under a new `request_id`, with the same "
    "planning inputs",
    # The granted paths in digest_inputs and dispatch_digest_inputs.
    "`digest_inputs` include each granted path",
    "`dispatch_digest_inputs` records them",
    # No grant for a request result that fails validation.
    "A request result that fails validation, or none of whose paths passes "
    "both checks, is handled like any failed planner result, and nothing is "
    "granted.",
    # Grants are not persisted; stage 1 is re-run on resume.
    "A grant lives only in the `write_policy` of the dispatch it was added to "
    "and is not persisted",
    "an interrupted stage 2 resumes by running stage 1 again",
    # No question and no new gate.
    "The grant asks no question and adds no gate.",
)
GOOD_GRANT = """\
**Other-feature document grant.** When the planner returns the stage-1
request result that `references/contracts/planner-contract.md`
(`## Other-feature documents`) defines and the result validates, the
orchestrator checks each requested path against the scope rule of that
section and confirms that the path exists as a regular file in the
integration worktree. A path that fails either check is not granted. For each
path that passes, the orchestrator adds one `amend_other_feature` target to
the `write_policy`, with `expect_digest` set to the digest the orchestrator
computes for the path now. The orchestrator verifies that target before the
dispatch per `references/artifact-digest.md` (`Pre-dispatch verification`).
It then re-dispatches the planner once, under a new `request_id`, with the
same planning inputs. That dispatch's `digest_inputs` include each granted
path, and the `worker_runs` entry's `dispatch_digest_inputs` records them. A
request result that fails validation, or none of whose paths passes both
checks, is handled like any failed planner result, and nothing is granted. A
grant lives only in the `write_policy` of the dispatch it was added to and is
not persisted, so an interrupted stage 2 resumes by running stage 1 again.
The grant asks no question and adds no gate.
"""


def check_grant_paragraph(paragraph):
    _holds_all(paragraph, GRANT_NEEDLES, "the grant paragraph")


def grant_paragraph(section):
    return _label_paragraph(section, GRANT_LABEL)


class TestAC1GrantRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _phase_section(4)

    def test_section_4_states_the_grant_rule(self):
        check_grant_paragraph(grant_paragraph(self.section))

    def test_the_grant_paragraph_follows_the_dispatch_inputs(self):
        flat = _flat(self.section)
        self.assertIn(GRANT_LABEL, flat)
        self.assertLess(
            flat.index("The planner run's `worker_runs` entry"),
            flat.index(GRANT_LABEL),
        )
        self.assertLess(
            flat.index("- The `plugin_versioning` value"),
            flat.index(GRANT_LABEL),
        )

    def test_existing_dispatch_paragraphs_are_kept(self):
        flat = _flat(self.section)
        for needle in (
            "Before the `Task` dispatch, the orchestrator verifies the planner's "
            "`write_policy.targets` per `references/artifact-digest.md` "
            "(`Pre-dispatch verification`).",
            "carries `dispatch_digest_inputs`, the per-path `digest_inputs` map of "
            "the dispatch's digest_source",
        ):
            self.assertIn(_flat(needle), flat)

    def test_the_grant_paragraph_restates_no_digest_owner_wording(self):
        flat = _flat(grant_paragraph(self.section)).lower()
        for wording in DIGEST_OWNER_WORDING:
            self.assertNotIn(wording.lower(), flat)

    # -- negative proofs ------------------------------------------------

    def test_matcher_accepts_the_good_sample_and_rejects_each_missing_element(self):
        _assert_rejects_each_needle(self, check_grant_paragraph, GOOD_GRANT, GRANT_NEEDLES)

    def test_paragraph_finder_rejects_a_section_without_the_paragraph(self):
        with self.assertRaises(AssertionError):
            grant_paragraph("Some other paragraph.\n\nAnd another one.\n")

    def test_paragraph_finder_rejects_a_duplicated_paragraph(self):
        with self.assertRaises(AssertionError):
            grant_paragraph(GOOD_GRANT + "\n" + GOOD_GRANT)


# ---------------------------------------------------------------------------
# AC-2: section 7, the completion output.
# ---------------------------------------------------------------------------

COMPLETION_LABEL = "The planner's completed output also covers"
COMPLETION_NEEDLES = (
    "the other-feature route of " + CONTRACT_CITATION,
    OTHER_FEATURE_SECTION,
    "the stage-1 request result, whose payload holds `other_feature_doc_requests`",
    "the stage-2 `payload.other_feature_doc_fixes`",
    "That section owns both shapes, and this document does not restate them.",
)
GOOD_COMPLETION = """\
The planner's completed output also covers the other-feature route of
`references/contracts/planner-contract.md` (`## Other-feature documents`):
the stage-1 request result, whose payload holds `other_feature_doc_requests`,
and the stage-2 `payload.other_feature_doc_fixes`. That section owns both
shapes, and this document does not restate them.
"""


def check_completion_paragraph(paragraph):
    _holds_all(paragraph, COMPLETION_NEEDLES, "the completion paragraph")


def completion_paragraph(section):
    return _label_paragraph(section, COMPLETION_LABEL)


class TestAC2CompletionOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _phase_section(7)

    def test_section_7_names_the_request_result_and_the_fix_declaration(self):
        check_completion_paragraph(completion_paragraph(self.section))

    def test_existing_completion_output_sentence_is_kept(self):
        self.assertIn(
            _flat(
                "On `status: completed`, the planner's payload carries: the "
                "written artifacts (IMPLEMENTATION.md, VERIFICATION.md, "
                "THREAT-MODEL.md, `tasks/*.md`, and TASK.md at the `minimal` "
                "tier when appended), the task index, and the proposed "
                "workflow patch"
            ),
            _flat(self.section),
        )

    # -- negative proofs ------------------------------------------------

    def test_matcher_accepts_the_good_sample_and_rejects_each_missing_element(self):
        _assert_rejects_each_needle(
            self, check_completion_paragraph, GOOD_COMPLETION, COMPLETION_NEEDLES
        )

    def test_paragraph_finder_rejects_a_section_without_the_paragraph(self):
        with self.assertRaises(AssertionError):
            completion_paragraph("On `status: completed`, the payload carries things.\n")


# ---------------------------------------------------------------------------
# AC-3: section 8, scope verification and the recording write.
# ---------------------------------------------------------------------------

FIXES_LABEL = "**Other-feature document fixes.**"
COVERAGE_SENTENCE = (
    "In scope verification (layer 4), every observed `modified` path that is "
    "an `amend_other_feature` target of the dispatch must be listed in "
    "`written_artifacts` and declared in `other_feature_doc_fixes`; otherwise "
    "the result fails scope verification."
)
RECORDING_NEEDLES = (
    "The recording phase-state write appends one `other_feature_doc_fixes` "
    "entry per declared fix",
    "(`path`, `change`, `reason`, and `produced_by` set to the run's `request_id`)",
    "the same write that records layer 5 and `self_write_set`",
)
FIXES_NEEDLES = (COVERAGE_SENTENCE,) + RECORDING_NEEDLES
GOOD_FIXES = """\
**Other-feature document fixes.** In scope verification (layer 4), every
observed `modified` path that is an `amend_other_feature` target of the
dispatch must be listed in `written_artifacts` and declared in
`other_feature_doc_fixes`; otherwise the result fails scope verification. The
recording phase-state write appends one `other_feature_doc_fixes` entry per
declared fix (`path`, `change`, `reason`, and `produced_by` set to the run's
`request_id`). That is the same write that records layer 5 and
`self_write_set`; `references/phase-state.md` defines the record.
"""


def check_fixes_paragraph(paragraph):
    _holds_all(paragraph, FIXES_NEEDLES, "the fixes paragraph")
    _holds_all(
        paragraph,
        ("`references/phase-state.md` defines the record",),
        "the fixes paragraph",
    )


def fixes_paragraph(section):
    return _label_paragraph(section, FIXES_LABEL)


class TestAC3ScopeVerificationAndRecording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _phase_section(8)

    def test_section_8_states_the_coverage_and_the_recording_write(self):
        check_fixes_paragraph(fixes_paragraph(self.section))

    def test_the_return_time_order_paragraph_is_byte_identical(self):
        paragraph = _only(
            [
                p
                for p in _paragraphs(self.section)
                if p.startswith(RETURN_TIME_ORDER_START)
            ],
            "return-time order paragraph",
        )
        self.assertEqual(
            hashlib.sha256(paragraph.encode("utf-8")).hexdigest(),
            RETURN_TIME_ORDER_SHA256,
        )

    def test_the_new_paragraph_follows_the_return_time_order_paragraph(self):
        flat = _flat(self.section)
        self.assertIn(FIXES_LABEL, flat)
        self.assertLess(flat.index(RETURN_TIME_ORDER_START), flat.index(FIXES_LABEL))

    def test_layer_5_recording_sentence_is_kept(self):
        self.assertIn(
            _flat(
                "Once layer 4 has passed, the orchestrator's layer 5 records the "
                "digests of the written artifacts per `references/artifact-digest.md` "
                "(`Layer 5 recording`), into `phase-state/create-plan.yaml`."
            ),
            _flat(self.section),
        )

    def test_the_new_paragraph_restates_no_digest_owner_wording(self):
        flat = _flat(fixes_paragraph(self.section)).lower()
        for wording in DIGEST_OWNER_WORDING:
            self.assertNotIn(wording.lower(), flat)

    # -- negative proofs ------------------------------------------------

    def test_matcher_accepts_the_good_sample_and_rejects_each_missing_element(self):
        _assert_rejects_each_needle(
            self,
            check_fixes_paragraph,
            GOOD_FIXES,
            FIXES_NEEDLES + ("`references/phase-state.md` defines the record",),
        )

    def test_a_section_8_copy_without_the_coverage_sentence_fails(self):
        copy = _forge(GOOD_FIXES, COVERAGE_SENTENCE)
        self.assertIn("The recording phase-state write", _flat(copy))
        with self.assertRaises(AssertionError):
            check_fixes_paragraph(copy)

    def test_a_section_8_copy_without_the_recording_sentence_fails(self):
        copy = _forge(
            GOOD_FIXES,
            "The recording phase-state write appends one `other_feature_doc_fixes` "
            "entry per declared fix",
        )
        with self.assertRaises(AssertionError):
            check_fixes_paragraph(copy)

    def test_pin_detects_a_changed_return_time_order_paragraph(self):
        paragraph = _only(
            [
                p
                for p in _paragraphs(_phase_section(8))
                if p.startswith(RETURN_TIME_ORDER_START)
            ],
            "return-time order paragraph",
        )
        for changed in (paragraph + " ", paragraph.replace("this one", "that one", 1)):
            self.assertNotEqual(
                hashlib.sha256(changed.encode("utf-8")).hexdigest(),
                RETURN_TIME_ORDER_SHA256,
            )


# ---------------------------------------------------------------------------
# AC-4: section 9, the validator-implemented list.
# ---------------------------------------------------------------------------

FEATURE_DOCS_BULLET_NEEDLES = (
    "`plan-task-feature-docs`",
    "`files` of a `tasks_patch.entries` item of a `replace_planning` patch",
    "`skills/plan-writing/SKILL.md`",
    "`## Feature-docs Files`",
)
OTHER_FEATURE_BULLET_NEEDLES = (
    CONTRACT_CITATION,
    OTHER_FEATURE_SECTION,
    "`other-feature-doc-scope`",
    "`other-feature-doc-request`",
    "`other-feature-doc-fix`",
)
REMOVALS_BULLET_NEEDLES = (
    "`tasks_patch.feature_docs_removals`",
    "`references/workflow-patch.md`",
    "`## Feature-docs correction`",
    "`--dry-run-apply`",
    "`--journal`",
)
GOOD_SECTION_9_BULLETS = """\
- No feature-docs path in the `files` of a `tasks_patch.entries` item of a
  `replace_planning` patch: each one is reported with the error code
  `plan-task-feature-docs`. The rule is owned by `skills/plan-writing/SKILL.md`
  (`## Feature-docs Files`) and is not restated here.
- The other-feature document route: a violation of
  `references/contracts/planner-contract.md`'s `## Other-feature documents` is
  reported with `other-feature-doc-scope`, `other-feature-doc-request` or
  `other-feature-doc-fix`, the codes that section assigns.
- A patch carrying `tasks_patch.feature_docs_removals` meets the conditions of
  `references/workflow-patch.md`'s `## Feature-docs correction`, checked under
  `--dry-run-apply` with `--journal` (the feature's `journal.jsonl`) added to
  the invocation below.
"""


def _bullet_with(bullets, token):
    return _only([b for b in bullets if token in b], "bullet naming %s" % token)


def check_section_9_bullets(bullets):
    _holds_all(
        _bullet_with(bullets, "`plan-task-feature-docs`"),
        FEATURE_DOCS_BULLET_NEEDLES,
        "the plan-task-feature-docs bullet",
    )
    _holds_all(
        _bullet_with(bullets, "`other-feature-doc-scope`"),
        OTHER_FEATURE_BULLET_NEEDLES,
        "the other-feature bullet",
    )
    _holds_all(
        _bullet_with(bullets, "`tasks_patch.feature_docs_removals`"),
        REMOVALS_BULLET_NEEDLES,
        "the feature_docs_removals bullet",
    )


def _implemented_list(section):
    start = section.index(SECTION_9_INTRO)
    return section[start : section.index(SECTION_9_NOT_IMPLEMENTED_MARKER, start)]


def _between(text, start_marker, end_marker):
    start = text.index(start_marker)
    return text[start : text.index(end_marker, start + len(start_marker))]


def _pins():
    """The section 9 digest pins and the invocation lines added after them,
    read from the module that owns them."""
    module = _load_module("_section_9_pins_for_task0009", SECTION_9_PIN_TEST_PATH)
    return module


class TestAC4ValidatorImplementedList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _phase_section(9)
        cls.implemented = _implemented_list(cls.section)
        cls.bullets = _bullets(cls.implemented)

    def test_the_implemented_list_gains_the_three_bullets(self):
        check_section_9_bullets(self.bullets)

    def test_the_new_bullets_replace_no_existing_bullet(self):
        flat = _flat(self.implemented)
        for needle in (
            "Every task plan has a non-empty Acceptance Criteria section.",
            "A task's `files` and its task plan's Files section agree as a union.",
            "No new report-artifact name in the `files` of `tasks_patch.entries`",
            "A patch carrying `tasks_patch.path_corrections` meets the conditions of",
        ):
            self.assertIn(needle, flat)

    def test_each_new_bullet_sits_inside_the_implemented_list(self):
        self.assertEqual(
            len([b for b in self.bullets if "`plan-task-feature-docs`" in b]), 1
        )
        self.assertLess(
            self.section.index("`plan-task-feature-docs`"),
            self.section.index(SECTION_9_NOT_IMPLEMENTED_MARKER),
        )
        self.assertLess(
            self.section.index("`tasks_patch.feature_docs_removals`"),
            self.section.index(SECTION_9_NOT_IMPLEMENTED_MARKER),
        )

    def test_the_not_implemented_block_matches_its_pinned_digest(self):
        pins = _pins()
        block = _between(
            self.section, SECTION_9_NOT_IMPLEMENTED_MARKER, SECTION_9_CANONICAL_MARKER
        )
        self.assertEqual(
            hashlib.sha256(block.encode("utf-8")).hexdigest(),
            pins.PHASE_NOT_IMPLEMENTED_SHA256,
        )

    def test_the_canonical_invocation_block_matches_its_pinned_digest(self):
        pins = _pins()
        block = _between(
            self.section, SECTION_9_CANONICAL_MARKER, SECTION_9_DIGEST_SOURCE_MARKER
        )
        for added in pins.PHASE_CANONICAL_INVOCATION_ADDED_LINES:
            self.assertEqual(block.count(added), 1, added)
            block = block.replace(added, "")
        self.assertEqual(
            hashlib.sha256(block.encode("utf-8")).hexdigest(),
            pins.PHASE_CANONICAL_INVOCATION_SHA256,
        )

    # -- negative proofs ------------------------------------------------

    def test_bullet_matcher_accepts_the_good_sample(self):
        check_section_9_bullets(_bullets(GOOD_SECTION_9_BULLETS))

    def test_bullet_matcher_rejects_each_missing_element(self):
        for needle in (
            FEATURE_DOCS_BULLET_NEEDLES
            + OTHER_FEATURE_BULLET_NEEDLES
            + REMOVALS_BULLET_NEEDLES
        ):
            forged = _bullets(_forge(GOOD_SECTION_9_BULLETS, needle))
            with self.assertRaises(AssertionError, msg="accepted without %r" % needle):
                check_section_9_bullets(forged)

    def test_bullet_matcher_rejects_a_list_without_one_of_the_bullets(self):
        for token in (
            "`plan-task-feature-docs`",
            "`other-feature-doc-scope`",
            "`tasks_patch.feature_docs_removals`",
        ):
            kept = [b for b in _bullets(GOOD_SECTION_9_BULLETS) if token not in b]
            self.assertEqual(len(kept), 2)
            with self.assertRaises(AssertionError):
                check_section_9_bullets(kept)

    def test_pins_detect_a_changed_block(self):
        pins = _pins()
        block = _between(
            self.section, SECTION_9_NOT_IMPLEMENTED_MARKER, SECTION_9_CANONICAL_MARKER
        )
        self.assertNotEqual(
            hashlib.sha256((block + "- extra bullet.\n").encode("utf-8")).hexdigest(),
            pins.PHASE_NOT_IMPLEMENTED_SHA256,
        )


# ---------------------------------------------------------------------------
# AC-5: section 12, the declared change set derivation.
# ---------------------------------------------------------------------------

INPUTS_NEEDLES = (
    "the union of four sources",
    "Every `tasks.*.files` entry registered in `workflow.yaml` by planning",
    "the default entries",
    "the implement-derived additions",
    "`references/implement-phase.md`",
    "and every `path` of the `other_feature_doc_fixes` record in "
    "`phase-state/create-plan.yaml`",
    "`references/phase-state.md` defines",
)
RETENTION_NEEDLES = (
    "The `other_feature_doc_fixes` record is append-only and survives phase "
    "restarts and re-planning, so a fix stays in the derived set.",
)
TIMING_NEEDLES = (
    "re-derived whenever the task set changes",
    "re-planning",
    "a rework append",
    "an implement wake that admitted a deviation",
    "or a fix is recorded",
)
GOOD_SECTION_12 = """\
- **Inputs**: the union of four sources. Every `tasks.*.files` entry
  registered in `workflow.yaml` by planning; the default entries, whose
  enumeration and membership semantics live in
  `references/templates/spec-document.md` and
  `references/templates/requirements-document.md` (this document cites
  them and never restates them); the implement-derived additions
  admitted by the deviation auto-addition rule in
  `references/implement-phase.md` — cited here by path, its evidence
  condition not restated in this document; and every `path` of the
  `other_feature_doc_fixes` record in `phase-state/create-plan.yaml`, which
  `references/phase-state.md` defines.
- **Retention**: an admitted addition is retained in exactly one
  location — the `files` list of the task whose deviation was admitted, in
  `workflow.yaml`, the same list the union above is read from. The
  `other_feature_doc_fixes` record is append-only and survives phase
  restarts and re-planning, so a fix stays in the derived set.
- **Timing**: the derivation is available once planning's proposed patch
  has registered the task set (section 10 above), and it is re-derived
  whenever the task set changes — re-planning, a rework append, or an
  implement wake that admitted a deviation — or a fix is recorded, rather
  than being frozen at the first successful planning pass.
"""
# The Inputs, Retention and Timing bullets as the base revision wrote them:
# three inputs, no fix record, three triggers.
PRE_CHANGE_SECTION_12 = """\
- **Inputs**: the union of three sources. Every `tasks.*.files` entry
  registered in `workflow.yaml` by planning; the default entries, whose
  enumeration and membership semantics live in
  `references/templates/spec-document.md` and
  `references/templates/requirements-document.md` (this document cites
  them and never restates them); and the implement-derived additions
  admitted by the deviation auto-addition rule in
  `references/implement-phase.md` — cited here by path, its evidence
  condition not restated in this document.
- **Retention**: an admitted addition is retained in exactly one
  location — the `files` list of the task whose deviation was admitted, in
  `workflow.yaml`, the same list the union above is read from.
- **Timing**: the derivation is available once planning's proposed patch
  has registered the task set (section 10 above), and it is re-derived
  whenever the task set changes — re-planning, a rework append, or an
  implement wake that admitted a deviation — rather than being frozen at
  the first successful planning pass.
"""


def _section_12_bullet(bullets, label):
    return _only(
        [b for b in bullets if b.startswith("**%s**" % label)],
        "%s bullet" % label,
    )


def check_section_12(body):
    bullets = _bullets(body)
    _holds_all(_section_12_bullet(bullets, "Inputs"), INPUTS_NEEDLES, "the Inputs bullet")
    _holds_all(
        _section_12_bullet(bullets, "Retention"), RETENTION_NEEDLES, "the Retention bullet"
    )
    _holds_all(_section_12_bullet(bullets, "Timing"), TIMING_NEEDLES, "the Timing bullet")


def check_no_forbidden_words(text):
    lowered = text.lower()
    for word in LOWERCASE_FORBIDDEN:
        _require(word not in lowered, "forbidden word %r present" % word)
    for word in CASE_SENSITIVE_FORBIDDEN:
        _require(word not in text, "forbidden phrase %r present" % word)


class TestAC5ChangeSetDerivation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = _phase_section(12)
        cls.to_end = _section_12_to_end()

    def test_section_12_reads_the_fix_record_as_a_fourth_input(self):
        check_section_12(self.body)

    def test_the_three_existing_inputs_and_pinned_triggers_stay(self):
        flat = _flat(self.body)
        for needle in (
            "derived — not authored",
            "a guard, not a statement of the goal",
            "the templates cited above state the superset/containment semantics",
            "the `files` list of the task whose deviation was admitted",
            "Re-derivation reads that location",
            "survive every later re-derivation",
            "a re-planning `replace_all` carries every already-registered task id "
            "verbatim rather than re-declaring it",
            "references/workflow-patch.md",
        ):
            self.assertIn(_flat(needle), flat)

    def test_no_forbidden_word_from_the_heading_to_the_end_of_the_document(self):
        check_no_forbidden_words(self.to_end)

    def test_the_two_workflow_artifact_root_globs_never_co_occur(self):
        self.assertFalse(
            "feature-docs/{feature}/**" in self.to_end
            and "test-docs/{feature}/**" in self.to_end
        )

    # -- negative proofs ------------------------------------------------

    def test_matcher_accepts_the_good_sample_and_rejects_each_missing_element(self):
        needles = INPUTS_NEEDLES + RETENTION_NEEDLES + TIMING_NEEDLES
        check_section_12(GOOD_SECTION_12)
        for needle in needles:
            # `re-planning` and the like also occur elsewhere in the sample;
            # remove every occurrence so the proof removes the element.
            words = needle.split()
            pattern = r"\s+".join(re.escape(word) for word in words)
            forged = re.sub(pattern, "", GOOD_SECTION_12)
            self.assertNotEqual(forged, GOOD_SECTION_12, needle)
            with self.assertRaises(AssertionError, msg="accepted without %r" % needle):
                check_section_12(forged)

    def test_a_section_12_copy_with_three_inputs_fails_the_fourth_input_check(self):
        with self.assertRaises(AssertionError):
            check_section_12(PRE_CHANGE_SECTION_12)

    def test_a_copy_that_names_four_sources_but_no_record_fails(self):
        copy = _forge(
            GOOD_SECTION_12,
            "and every `path` of the `other_feature_doc_fixes` record in "
            "`phase-state/create-plan.yaml`, which `references/phase-state.md` "
            "defines",
            "and a fourth thing",
        )
        with self.assertRaises(AssertionError):
            check_section_12(copy)

    def test_a_copy_without_the_retention_sentence_fails(self):
        copy = _forge(GOOD_SECTION_12, RETENTION_NEEDLES[0])
        with self.assertRaises(AssertionError):
            check_section_12(copy)

    def test_a_copy_with_the_old_timing_fails(self):
        copy = _forge(GOOD_SECTION_12, "or a fix is recorded,")
        with self.assertRaises(AssertionError):
            check_section_12(copy)

    def test_forbidden_word_matcher_flags_each_word(self):
        check_no_forbidden_words("Out of scope, removes, and not granted.")
        for word in LOWERCASE_FORBIDDEN + CASE_SENSITIVE_FORBIDDEN:
            with self.assertRaises(AssertionError, msg=word):
                check_no_forbidden_words("A sentence with %s inside." % word)
        with self.assertRaises(AssertionError):
            check_no_forbidden_words("Both are IGNORED here.")

    def test_forbidden_word_scan_reaches_the_end_of_the_document(self):
        self.assertTrue(
            self.to_end.rstrip().endswith(_read(PHASE_PATH).rstrip()[-40:])
        )
        self.assertIn("## 13. ", self.to_end)


# ---------------------------------------------------------------------------
# AC-6: phase-state.md, the schema example and the field table.
# ---------------------------------------------------------------------------

RECORD_FIELD = "other_feature_doc_fixes"
ROW_NEEDLES = (
    "`phase: create-plan` only",
    "append-only",
    "`path`, `change`, `reason` and `produced_by`",
    "The orchestrator appends one entry per declared fix",
    "the run's recording phase-state write",
    "layer-5 `artifacts` entries and `self_write_set`",
    "never rewritten or cleared",
    "a phase restart (`generation` increases) included",
    "`references/phases/create-plan-phase.md`, section 12",
    "reads every `path` into the declared change set",
    "stays valid",
)
GOOD_ROW = (
    "| `other_feature_doc_fixes` | `phase: create-plan` only. An append-only "
    "list of the other-feature document fixes that planner runs declared. "
    "Each entry: `path`, `change`, `reason` and `produced_by` (the "
    "`request_id` of the run that declared the fix). The orchestrator appends "
    "one entry per declared fix in the run's recording phase-state write, the "
    "same write that records the run's layer-5 `artifacts` entries and "
    "`self_write_set` (`references/phases/create-plan-phase.md`, section 8). "
    "The list is never rewritten or cleared, a phase restart (`generation` "
    "increases) included. `references/phases/create-plan-phase.md`, section "
    "12, reads every `path` into the declared change set. A file written "
    "before the field existed lacks it and stays valid. |"
)
EXAMPLE_KEYS = ("path", "change", "reason", "produced_by")
GOOD_EXAMPLE = """\
other_feature_doc_fixes:       # `phase: create-plan` only; append-only
  - path: feature-docs/other-feature/SPEC.md
    change: "..."
    reason: "..."
    produced_by: create-plan-run-0002
"""
# Row text variants that must not match the "append-only" wording needles.
ROW_NEEDLE_REPAIRS = {
    "append-only": "append only",
    "never rewritten or cleared": "rewritten when needed",
    "a phase restart (`generation` increases) included": "",
    "stays valid": "is invalid",
}


def schema_example_block(text):
    """The first fenced yaml block after the `## Schema` heading."""
    start = text.index("\n## Schema\n")
    match = re.search(r"```yaml\n(.*?)\n```", text[start:], re.DOTALL)
    _require(match is not None, "no yaml block under ## Schema")
    return match.group(1)


def check_schema_example(block):
    lines = block.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith(RECORD_FIELD + ":")]
    _require(len(starts) == 1, "expected one top-level %s: line" % RECORD_FIELD)
    entry_lines = []
    for line in lines[starts[0] + 1 :]:
        if line and not line.startswith(" "):
            break
        entry_lines.append(line)
    entries = [line for line in entry_lines if line.startswith("  - ")]
    _require(len(entries) == 1, "the example holds %d entries, expected 1" % len(entries))
    body = "\n".join(entry_lines)
    for key in EXAMPLE_KEYS:
        _require(
            re.search(r"^(?:  - |    )%s: \S" % re.escape(key), body, re.MULTILINE),
            "the example entry lacks %r" % key,
        )
    return entries


def field_table_row(text):
    return _only(
        [
            line
            for line in text.split("\n")
            if line.startswith("| `%s` |" % RECORD_FIELD)
        ],
        "field table row for %s" % RECORD_FIELD,
    )


def check_field_row(row):
    _holds_all(row, ROW_NEEDLES, "the %s row" % RECORD_FIELD)


class TestAC6PhaseStateRecord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)

    def test_the_schema_example_defines_the_record_with_one_entry(self):
        check_schema_example(schema_example_block(self.text))

    def test_the_field_table_defines_the_record(self):
        check_field_row(field_table_row(self.text))

    def test_the_row_sits_inside_the_top_level_field_table(self):
        marker = "Every top-level field:"
        self.assertEqual(self.text.count(marker), 1)
        table = self.text[self.text.index(marker) :]
        self.assertIn("| `%s` |" % RECORD_FIELD, table)
        self.assertLess(table.index("| `schema_version` |"), table.index("| `%s` |" % RECORD_FIELD))
        self.assertLess(table.index("| `%s` |" % RECORD_FIELD), table.index("| `last_error` |"))

    def test_existing_example_lines_and_rows_are_kept(self):
        block = schema_example_block(self.text)
        for line in ("schema_version: 1", "worker_runs:", "artifacts:", "patches:", "classification:"):
            self.assertIn(line, block)
        for field in ("artifacts", "patches", "worker_runs", "classification"):
            self.assertIn("| `%s` |" % field, self.text)

    # -- negative proofs ------------------------------------------------

    def test_row_matcher_accepts_the_good_sample_and_rejects_each_missing_element(self):
        _assert_rejects_each_needle(self, check_field_row, GOOD_ROW, ROW_NEEDLES)

    def test_row_matcher_rejects_a_changed_wording(self):
        check_field_row(GOOD_ROW)
        for needle, repair in ROW_NEEDLE_REPAIRS.items():
            forged = _forge(GOOD_ROW, needle, repair)
            with self.assertRaises(AssertionError, msg=needle):
                check_field_row(forged)

    def test_row_finder_rejects_a_missing_or_duplicated_row(self):
        with self.assertRaises(AssertionError):
            field_table_row("| `artifacts` | text |\n")
        with self.assertRaises(AssertionError):
            field_table_row(GOOD_ROW + "\n" + GOOD_ROW + "\n")

    def test_example_matcher_accepts_the_good_sample(self):
        self.assertEqual(len(check_schema_example(GOOD_EXAMPLE)), 1)

    def test_example_matcher_rejects_a_missing_key(self):
        for key in EXAMPLE_KEYS:
            forged = re.sub(r"^(  - |    )%s: .*\n" % key, "", GOOD_EXAMPLE, flags=re.MULTILINE)
            self.assertNotEqual(forged, GOOD_EXAMPLE, key)
            with self.assertRaises(AssertionError, msg=key):
                check_schema_example(forged)

    def test_example_matcher_rejects_no_entry_and_two_entries(self):
        with self.assertRaises(AssertionError):
            check_schema_example("other_feature_doc_fixes: []\nlast_error: null\n")
        with self.assertRaises(AssertionError):
            check_schema_example(GOOD_EXAMPLE + GOOD_EXAMPLE.split("\n", 1)[1])
        with self.assertRaises(AssertionError):
            check_schema_example("last_error: null\n")

    def test_example_block_finder_rejects_a_document_without_a_block(self):
        with self.assertRaises(AssertionError):
            schema_example_block("\n## Schema\n\nNo block here.\n")


# ---------------------------------------------------------------------------
# Hygiene: digest sentences, gate-id spans, redaction, no question or gate,
# standard-library imports.
# ---------------------------------------------------------------------------

_PHASE_YAML_NAME_RE = re.compile(r"^[a-z]+(?:-[a-z]+)*\.yaml$")


def bare_phase_yaml_spans(text):
    """Backtick spans that are a bare phase-state YAML file name (the
    Conventions' backtick token rule writes them with their directory)."""
    spans = re.findall(r"`([^`]+)`", text)
    return [s for s in spans if _PHASE_YAML_NAME_RE.match(s) and s != "workflow.yaml"]


def digest_sentence_violations(text):
    """Sentences that carry a digest term, name no orchestrator and hold no
    negation (the checker's own predicates)."""
    return [
        sentence
        for sentence in cpi._sentences(text)
        if cpi.DIGEST_TERM_RE.search(sentence)
        and not cpi.ORCHESTRATOR_RE.search(sentence)
        and not cpi.NEGATION_RE.search(sentence)
    ]


def _new_text():
    """The text this task adds or changes, taken from the live documents."""
    section_12 = _bullets(_phase_section(12))
    return "\n\n".join(
        [
            grant_paragraph(_phase_section(4)),
            completion_paragraph(_phase_section(7)),
            fixes_paragraph(_phase_section(8)),
            "\n".join(
                "- " + b
                for b in _bullets(_implemented_list(_phase_section(9)))
                if "`plan-task-feature-docs`" in b
                or "`other-feature-doc-scope`" in b
                or "`tasks_patch.feature_docs_removals`" in b
            ),
            "\n".join(
                "- " + b
                for b in section_12
                if b.startswith(("**Inputs**", "**Retention**", "**Timing**"))
            ),
            field_table_row(_read(PHASE_STATE_PATH)),
        ]
    )


class TestHygiene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new_text = _new_text()

    def test_digest_sentences_name_the_orchestrator_or_are_negated(self):
        self.assertEqual(digest_sentence_violations(self.new_text), [])
        self.assertEqual(cpi.find_worker_directed_digest_instructions(self.new_text, ()), [])

    def test_new_text_holds_no_gate_id_span_and_no_bare_phase_yaml_name(self):
        self.assertEqual(cpi.extract_gate_ids_from_text(self.new_text), set())
        self.assertEqual(bare_phase_yaml_spans(self.new_text), [])

    def test_new_text_adds_no_gate_and_no_question(self):
        flat = _flat(self.new_text)
        for word in ("gate_id", "gate ID", "AskUserQuestion", "question_packet"):
            self.assertNotIn(word, flat)

    def test_new_text_carries_no_notion_url_or_home_directory_path(self):
        for needle in ("notion.so", "notion.site", "/home/", "/Users/"):
            self.assertNotIn(needle, self.new_text)

    def test_create_plan_phase_never_names_git_hash_object(self):
        self.assertNotIn("git hash-object", _read(PHASE_PATH))

    # -- negative proofs ------------------------------------------------

    def test_digest_matcher_flags_a_worker_directed_sentence(self):
        self.assertTrue(
            digest_sentence_violations("The planner sets the digest of the path.")
        )
        self.assertEqual(
            digest_sentence_violations("The orchestrator computes the digest of the path."),
            [],
        )
        self.assertEqual(
            digest_sentence_violations("The planner never computes a digest."), []
        )

    def test_gate_id_matcher_proof(self):
        self.assertEqual(
            cpi.extract_gate_ids_from_text("the gate ID `create-plan.sample` is named"),
            {"create-plan.sample"},
        )
        self.assertEqual(bare_phase_yaml_spans("see `create-plan.yaml` here"), ["create-plan.yaml"])
        self.assertEqual(
            bare_phase_yaml_spans("see `phase-state/create-plan.yaml` and `workflow.yaml`"), []
        )

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
