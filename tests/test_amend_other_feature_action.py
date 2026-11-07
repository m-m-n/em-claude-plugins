"""Tests for task0003 of plan-feature-docs-route: `amend_other_feature`, the
seventh `write_policy` action.

Covers task0003 Acceptance Criteria
(feature-docs/plan-feature-docs-route/tasks/task0003.md):

- AC-1 (TM-1): spec-writer-contract.md has the heading "The `write_policy`
  actions"; its row for `amend_other_feature` states the required
  dispatch-time `expect_digest`, the modify-only worker behaviour, the
  implementation-planner create-plan validity and the scope citation; one
  sentence states that `replace_own`, `replace_authorized` and the
  artifact-overwrite policy are not reused; the example comment lists seven
  actions (TestSpecWriterContractRow).
- AC-2: none of the modified Markdown files contains "six actions" or the old
  heading text, and every citation of the action table names the new heading
  (TestCountFreeWording).
- AC-3: worker-envelope.md's self-write table has the `amend_other_feature`
  row (`created` not a member, `modified` member, `deleted` not a member) and
  the document never contains `expect_digest` (TestEnvelopeSelfWriteRow).
- AC-4: `self-write-digest.py` identifies a `modified` path under an
  `amend_other_feature` target as a member and a `created` or `deleted` one as
  not a member; an unknown action is still an input error
  (TestScriptMembership, TestScriptRejectsUnknownActions).
- AC-5: the pins of the three listed test files are refreshed to seven
  actions and the new heading, each with a comment naming this task
  (TestPinsAreRefreshed).
- AC-6: the whole suite passing and `check-plugin-invariants.py` reporting no
  finding are recorded against the suite and
  tests/test_check_plugin_invariants.py (TestRepositoryLevelInvariant); this
  module adds nothing for them.

The document checks read whitespace-normalized, heading-sliced text. Every
matcher has a negative proof: a forged copy of the real text, made by a
replacement whose landing is asserted first, must make the matcher fail.

Standard library only.
"""

import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CONTRACTS = PLUGIN_ROOT / "references" / "contracts"

SPEC_WRITER_CONTRACT = CONTRACTS / "spec-writer-contract.md"
ENVELOPE = CONTRACTS / "worker-envelope.md"
DESIGNER_CONTRACT = CONTRACTS / "designer-contract.md"
REWORK_PLANNER_CONTRACT = CONTRACTS / "rework-planner-contract.md"
SPEC_WRITER_AGENT = PLUGIN_ROOT / "agents" / "spec-writer.md"
ARTIFACT_DIGEST = PLUGIN_ROOT / "references" / "artifact-digest.md"
SCRIPT = PLUGIN_ROOT / "scripts" / "self-write-digest.py"

TESTS_DIR = Path(__file__).resolve().parent
THREAT_MODEL_TEST = TESTS_DIR / "test_threat_model_planner_contract.py"
DOCS_TEST = TESTS_DIR / "test_self_write_digest_docs.py"
DIGEST_TEST = TESTS_DIR / "test_self_write_digest.py"

NEW_HEADING = "### The `write_policy` actions"
NEW_NAME = "The `write_policy` actions"
OLD_NAME = "The six `write_policy` actions"
ACTION = "amend_other_feature"
SEVEN_ACTIONS = (
    "create",
    "replace_own",
    "replace_authorized",
    "preserve",
    "extend_only",
    "regenerate",
    ACTION,
)
TASK_REFERENCE = "plan-feature-docs-route/task0003"

NOT_MEMBER = "not a member"
CALL_TIMEOUT_SECONDS = 30


# --------------------------------------------------------------- helpers ----


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def _heading_section(text, heading):
    """The lines from `heading` up to the next heading of the same or a
    higher level. Raises AssertionError when the heading line is absent."""
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if line == heading:
            break
    else:
        raise AssertionError(f"heading not found: {heading!r}")
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#+) ", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def _table_rows(section):
    """Every table row of `section` as a list of stripped cells, the
    separator row dropped."""
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _forge(test, text, old, new):
    """`text` with `old` replaced by `new`; asserts the replacement landed so
    a negative proof never passes vacuously."""
    test.assertIn(old, text, f"forging precondition: {old!r} is absent")
    forged = text.replace(old, new, 1)
    test.assertNotEqual(forged, text)
    return forged


# ------------------------------------------------- AC-1: the action table ----


def _assert_ac1(test, text):
    lines = text.splitlines()
    test.assertEqual(lines.count(NEW_HEADING), 1)
    test.assertNotIn(OLD_NAME, text)

    section = _heading_section(text, NEW_HEADING)
    rows = {row[0]: row[1:] for row in _table_rows(section)[1:]}
    test.assertEqual(
        [row[0] for row in _table_rows(section)[1:]],
        [f"`{name}`" for name in SEVEN_ACTIONS],
    )
    digest_cell, behaviour_cell = rows[f"`{ACTION}`"]

    digest = _normalize_ws(digest_cell)
    test.assertTrue(digest.startswith("required"), digest)
    test.assertIn("the digest the orchestrator recorded", digest)
    test.assertIn("at dispatch", digest)

    behaviour = _normalize_ws(behaviour_cell)
    test.assertIn("may modify the content of the existing file", behaviour)
    test.assertIn("must not create, delete or change the file kind", behaviour)
    test.assertIn(
        "Valid only on implementation-planner dispatches of create-plan",
        behaviour,
    )
    test.assertRegex(
        behaviour,
        r"scope .{0,60}`references/contracts/planner-contract\.md`, "
        r"`## Other-feature documents`",
    )

    prose = _normalize_ws(
        "\n".join(
            line for line in section.splitlines() if not line.strip().startswith("|")
        )
    )
    test.assertRegex(
        prose,
        r"`amend_other_feature` route reuses neither `replace_own`, "
        r"`replace_authorized` nor the artifact-overwrite batch policy",
    )

    comment = re.search(r"(?m)^\s+action: create\s+# (.*)$", text)
    test.assertIsNotNone(comment, "the target example comment is missing")
    listed = [part.strip() for part in comment.group(1).split("|")]
    test.assertEqual(sorted(listed), sorted(SEVEN_ACTIONS))


class TestSpecWriterContractRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SPEC_WRITER_CONTRACT)

    def test_ac1_heading_row_scope_non_reuse_and_example_comment(self):
        _assert_ac1(self, self.text)

    def test_ac1_who_verifies_section_is_left_as_it_was(self):
        section = _normalize_ws(
            _heading_section(self.text, "### Who verifies `expect_digest`")
        )
        self.assertIn("The orchestrator verifies `expect_digest`, not the worker.", section)
        self.assertIn(
            "The worker does not compute digests and does not re-verify `expect_digest`.",
            section,
        )

    # -- negative proofs ----------------------------------------------------

    def test_ac1_a_table_without_the_row_is_rejected(self):
        row = next(
            line for line in self.text.splitlines() if line.startswith("| `amend_other_feature` |")
        )
        forged = _forge(self, self.text, row + "\n", "")
        with self.assertRaises(AssertionError):
            _assert_ac1(self, forged)

    def test_ac1_each_forged_departure_from_the_row_is_rejected(self):
        departures = (
            ("optional digest", "| required (the digest the orchestrator recorded", "| always `null` (the digest the orchestrator recorded"),
            ("digest not tied to dispatch", "recorded for the path at dispatch", "recorded for the path"),
            ("no modify permission", "may modify the content of the existing file", "may rewrite the file"),
            ("creation allowed", "must not create, delete or change the file kind", "must not delete the file"),
            ("any worker", "Valid only on implementation-planner dispatches of create-plan", "Valid on every dispatch"),
            ("no scope citation", "`## Other-feature documents`", "the planner contract"),
            ("reuse not negated", "route reuses neither", "route reuses"),
            ("artifact-overwrite policy not named", "nor the artifact-overwrite batch policy", "nor anything else"),
            ("example comment lists six", " | regenerate | amend_other_feature", " | regenerate"),
            ("old heading", NEW_HEADING, "### The six `write_policy` actions"),
        )
        for label, old, new in departures:
            with self.subTest(departure=label):
                forged = _forge(self, self.text, old, new)
                with self.assertRaises(AssertionError):
                    _assert_ac1(self, forged)

    def test_ac1_a_forged_eighth_action_row_is_rejected(self):
        row = next(
            line for line in self.text.splitlines() if line.startswith("| `amend_other_feature` |")
        )
        forged = _forge(self, self.text, row, row + "\n| `phantom_action` | required | A forged action. |")
        with self.assertRaises(AssertionError):
            _assert_ac1(self, forged)


# -------------------------------------------- AC-2: count-free wording ----

MODIFIED_MARKDOWN = (
    SPEC_WRITER_CONTRACT,
    ENVELOPE,
    DESIGNER_CONTRACT,
    REWORK_PLANNER_CONTRACT,
    SPEC_WRITER_AGENT,
    ARTIFACT_DIGEST,
)
# A path -> the least number of citations of the action table it must carry.
MINIMUM_CITATIONS = {ARTIFACT_DIGEST: 2, ENVELOPE: 1}

SIX_ACTIONS_RE = re.compile(r"\bsix\s+(?:`write_policy`|actions)", re.IGNORECASE)
CITATION_RE = re.compile(r'"(The [^"]*? actions)"')


def _count_wording_violations(text):
    """Occurrences of the count wording ("six actions", the old heading)."""
    return SIX_ACTIONS_RE.findall(_normalize_ws(text))


def _table_citations(text):
    """The quoted action-table names the text cites."""
    return CITATION_RE.findall(_normalize_ws(text))


class TestCountFreeWording(unittest.TestCase):
    def test_ac2_no_modified_file_names_the_count_or_the_old_heading(self):
        for path in MODIFIED_MARKDOWN:
            with self.subTest(document=path.name):
                text = _read(path)
                self.assertEqual(_count_wording_violations(text), [])
                self.assertNotIn(OLD_NAME, _normalize_ws(text))

    def test_ac2_every_citation_of_the_action_table_names_the_new_heading(self):
        for path in MODIFIED_MARKDOWN:
            with self.subTest(document=path.name):
                citations = _table_citations(_read(path))
                self.assertEqual(set(citations) - {NEW_NAME}, set())
                self.assertGreaterEqual(len(citations), MINIMUM_CITATIONS.get(path, 0))

    def test_ac2_no_plugin_document_cites_the_old_heading(self):
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in sorted(PLUGIN_ROOT.rglob("*.md"))
            if OLD_NAME in _normalize_ws(_read(path))
        ]
        self.assertEqual(offenders, [])

    # -- negative proofs ----------------------------------------------------

    def test_ac2_the_count_matcher_fires_on_each_forged_wording(self):
        for label, forged in (
            ("six actions", "the six actions (`create` / `regenerate`)"),
            ("line-broken six actions", "the six\nactions of the model"),
            ("old heading", 'cites "The six `write_policy` actions"'),
            ("old heading broken across lines", 'cites "The six\n`write_policy` actions"'),
        ):
            with self.subTest(wording=label):
                self.assertNotEqual(_count_wording_violations(forged), [])

    def test_ac2_the_count_matcher_stays_quiet_on_count_free_text(self):
        for clean in (
            "the actions (`create` / `regenerate`)",
            'cites "The `write_policy` actions"',
            "one of the six `status` values",
        ):
            with self.subTest(text=clean):
                self.assertEqual(_count_wording_violations(clean), [])

    def test_ac2_the_citation_matcher_reads_both_headings(self):
        self.assertEqual(
            _table_citations('see ("The `write_policy` actions") and ("The six\n`write_policy` actions")'),
            [NEW_NAME, OLD_NAME],
        )
        self.assertEqual(_table_citations('the "Who verifies `expect_digest`" section'), [])


# ---------------------------- AC-3: worker-envelope.md's self-write row ----

EXPECTED_ENVELOPE_CELLS = [NOT_MEMBER, "member", NOT_MEMBER]


def _envelope_matrix(text):
    start = text.index("| Covering entry |")
    block = []
    for line in text[start:].splitlines():
        if not line.startswith("|"):
            break
        block.append(line)
    return {row[0]: row[1:] for row in _table_rows("\n".join(block))[1:]}


def _assert_ac3_row(test, text):
    rows = _envelope_matrix(text)
    test.assertEqual(rows.get(f"target `{ACTION}`"), EXPECTED_ENVELOPE_CELLS)
    test.assertEqual(text.count(f"| target `{ACTION}` |"), 1)


def _assert_ac3_no_expect_digest(test, text):
    test.assertNotIn("expect_digest", text)


def _assert_ac3(test, text):
    _assert_ac3_row(test, text)
    _assert_ac3_no_expect_digest(test, text)


class TestEnvelopeSelfWriteRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE)

    def test_ac3_the_row_admits_modified_only_and_the_document_has_no_expect_digest(self):
        _assert_ac3(self, self.text)

    def test_ac3_the_existing_rows_keep_their_cells(self):
        rows = _envelope_matrix(self.text)
        self.assertEqual(rows["target `replace_own`"], [NOT_MEMBER, "member", NOT_MEMBER])
        self.assertEqual(rows["target `create`"], ["member", NOT_MEMBER, NOT_MEMBER])
        self.assertEqual(rows["target `preserve`"], [NOT_MEMBER] * 3)

    # -- negative proofs ----------------------------------------------------

    def test_ac3_a_table_without_the_row_is_rejected(self):
        row = next(
            line
            for line in self.text.splitlines()
            if line.startswith(f"| target `{ACTION}` |")
        )
        forged = _forge(self, self.text, row + "\n", "")
        with self.assertRaises(AssertionError):
            _assert_ac3(self, forged)

    def test_ac3_a_row_with_a_wrong_cell_is_rejected(self):
        row = next(
            line
            for line in self.text.splitlines()
            if line.startswith(f"| target `{ACTION}` |")
        )
        for label, cells in (
            ("created admitted", "| member | member | not a member |"),
            ("modified refused", "| not a member | not a member | not a member |"),
            ("deleted admitted", "| not a member | member | member |"),
        ):
            with self.subTest(forged=label):
                forged = _forge(self, self.text, row, f"| target `{ACTION}` {cells}")
                with self.assertRaises(AssertionError):
                    _assert_ac3(self, forged)

    def test_ac3_an_envelope_sample_with_expect_digest_is_rejected(self):
        forged = self.text + "\nThe target carries `expect_digest`.\n"
        with self.assertRaises(AssertionError):
            _assert_ac3_no_expect_digest(self, forged)

    def test_ac3_the_real_envelope_is_free_of_expect_digest(self):
        _assert_ac3_no_expect_digest(self, self.text)


# ----------------------------------------------- AC-4: the script ----------

_SCRIPT_MODULE = None


def script_module():
    """`self-write-digest.py`, loaded by file path on first use."""
    global _SCRIPT_MODULE
    if _SCRIPT_MODULE is None:
        spec = importlib.util.spec_from_file_location(
            "self_write_digest_amend_other_feature", SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SCRIPT_MODULE = module
    return _SCRIPT_MODULE


AMENDED = "feature-docs/other-feature/SPEC.md"
KINDS = ("created", "modified", "deleted")
EXPECTED_MEMBER = {"created": False, "modified": True, "deleted": False}


def _change(path, kind):
    return {"path": path, "kind": kind}


def _target(path, action, source=None):
    entry = {"path": path, "action": action, "expect_digest": None}
    if source is not None:
        entry["source"] = source
    return entry


def _identify(changes, targets, roots=()):
    return script_module().identify_self_writes(
        copy.deepcopy(changes), {"targets": copy.deepcopy(targets)}, list(roots)
    )


def _document(kind, action=ACTION, roots=()):
    dispatch = {
        "worker": "implementation-planner",
        "digest_inputs": {AMENDED: "sha256:" + "a" * 64},
    }
    current = {
        "worker": "implementation-planner",
        "digest_inputs": {AMENDED: "sha256:" + "b" * 64},
    }
    return {
        "operation": "identify_and_substitute",
        "dispatch_digest_source": dispatch,
        "current_digest_source": current,
        "observed_changes": [_change(AMENDED, kind)],
        "write_policy": {"targets": [_target(AMENDED, action)]},
        "allowed_write_roots": list(roots),
    }


def _run_cli(document):
    with tempfile.TemporaryDirectory() as holder:
        tmp = Path(os.path.realpath(holder))
        path = tmp / "input.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(path)],
            cwd=tmp,
            capture_output=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )


class TestScriptMembership(unittest.TestCase):
    def test_ac4_each_change_kind_follows_the_matrix_through_the_module(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                got = _identify([_change(AMENDED, kind)], [_target(AMENDED, ACTION)])
                self.assertEqual(got, [AMENDED] if EXPECTED_MEMBER[kind] else [])

    def test_ac4_each_change_kind_follows_the_matrix_through_the_command_line(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                proc = _run_cli(_document(kind))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                result = json.loads(proc.stdout.decode("utf-8"))
                self.assertEqual(
                    result["self_write_set"], [AMENDED] if EXPECTED_MEMBER[kind] else []
                )

    def test_ac4_a_modified_amended_path_carries_its_dispatch_time_digest(self):
        proc = _run_cli(_document("modified"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        inputs = json.loads(proc.stdout.decode("utf-8"))["digest_source"]["digest_inputs"]
        self.assertEqual(inputs, {AMENDED: "sha256:" + "a" * 64})

    def test_ac4_a_created_amended_path_keeps_its_current_digest(self):
        proc = _run_cli(_document("created"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        inputs = json.loads(proc.stdout.decode("utf-8"))["digest_source"]["digest_inputs"]
        self.assertEqual(inputs, {AMENDED: "sha256:" + "b" * 64})

    def test_ac4_the_target_decides_even_when_the_path_lies_under_a_root(self):
        roots = ["feature-docs/other-feature"]
        created = _identify(
            [_change(AMENDED, "created")], [_target(AMENDED, ACTION)], roots
        )
        modified = _identify(
            [_change(AMENDED, "modified")], [_target(AMENDED, ACTION)], roots
        )
        self.assertEqual(created, [])
        self.assertEqual(modified, [AMENDED])

    def test_ac4_the_target_needs_no_source(self):
        self.assertEqual(
            _identify([], [_target(AMENDED, ACTION)]), []
        )

    def test_ac4_an_unchanged_granted_target_is_not_a_member(self):
        self.assertEqual(
            _identify(
                [_change("feature-docs/x/IMPLEMENTATION.md", "modified")],
                [
                    _target(AMENDED, ACTION),
                    _target("feature-docs/x/IMPLEMENTATION.md", "replace_own"),
                ],
            ),
            ["feature-docs/x/IMPLEMENTATION.md"],
        )

    def test_ac4_regenerate_is_still_decided_after_every_other_path(self):
        regenerated = "design-system/tokens.html"
        targets = [
            _target(regenerated, "regenerate", source=AMENDED),
            _target(AMENDED, ACTION),
        ]
        self.assertEqual(
            _identify(
                [_change(regenerated, "modified"), _change(AMENDED, "modified")],
                targets,
            ),
            sorted([regenerated, AMENDED]),
        )
        self.assertEqual(
            _identify([_change(regenerated, "modified")], targets), []
        )

    def test_ac4_the_module_docstring_lists_the_action(self):
        self.assertIn(ACTION, " ".join((script_module().__doc__ or "").split()))

    # -- the matrix cells are not vacuous -----------------------------------

    def test_ac4_the_membership_probe_distinguishes_member_from_non_member(self):
        member = _identify([_change(AMENDED, "modified")], [_target(AMENDED, ACTION)])
        refused = _identify([_change(AMENDED, "deleted")], [_target(AMENDED, ACTION)])
        self.assertNotEqual(member, refused)


UNKNOWN_ACTIONS = (
    "amend_other_features",
    "amend-other-feature",
    "Amend_Other_Feature",
    "amend_other",
    "overwrite",
)


class TestScriptRejectsUnknownActions(unittest.TestCase):
    def test_ac4_an_unknown_action_is_an_input_error_in_the_module(self):
        module = script_module()
        for action in UNKNOWN_ACTIONS:
            with self.subTest(action=action):
                with self.assertRaises(module.InputError):
                    module.identify_self_writes(
                        [], {"targets": [_target(AMENDED, action)]}, []
                    )

    def test_ac4_an_unknown_action_exits_2_on_the_command_line(self):
        for action in UNKNOWN_ACTIONS:
            with self.subTest(action=action):
                proc = _run_cli(_document("modified", action=action))
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertEqual(proc.stdout, b"")
                self.assertTrue(
                    proc.stderr.startswith(b"self-write-digest: "), proc.stderr
                )
                self.assertNotIn(b"Traceback", proc.stderr)

    def test_ac4_the_known_action_is_not_rejected(self):
        proc = _run_cli(_document("modified"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")

    def test_ac4_a_repeated_amend_target_path_is_still_rejected(self):
        module = script_module()
        with self.assertRaises(module.InputError):
            module.identify_self_writes(
                [],
                {"targets": [_target(AMENDED, ACTION), _target(AMENDED, "preserve")]},
                [],
            )


# ---------------------------------- AC-5: the refreshed pins ---------------


def _load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _task_comment_lines(text):
    return [
        line
        for line in text.splitlines()
        if line.lstrip().startswith("#") and TASK_REFERENCE in line
    ]


class TestPinsAreRefreshed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.threat_model = _load_by_path(
            "pins_threat_model_planner_contract", THREAT_MODEL_TEST
        )
        cls.docs = _load_by_path("pins_self_write_digest_docs", DOCS_TEST)
        cls.digest = _load_by_path("pins_self_write_digest", DIGEST_TEST)

    def test_ac5_the_action_set_pin_holds_the_seven_actions(self):
        self.assertEqual(set(self.threat_model.EXPECTED_ACTIONS), set(SEVEN_ACTIONS))
        self.assertEqual(len(self.threat_model.EXPECTED_ACTIONS), 7)

    def test_ac5_the_matrix_pin_holds_the_new_row(self):
        self.assertEqual(
            self.docs.MATRIX.get(f"target `{ACTION}`"),
            (NOT_MEMBER, "member", NOT_MEMBER),
        )

    def test_ac5_the_matrix_pin_keeps_the_rows_it_had(self):
        for entry in (
            "target `create`",
            "target `replace_own`",
            "target `replace_authorized`",
            "target `extend_only`",
            "target `regenerate`",
            "target `preserve`",
            "not a target, inside an `allowed_write_roots` entry",
            "neither",
        ):
            with self.subTest(entry=entry):
                self.assertIn(entry, self.docs.MATRIX)

    def test_ac5_the_script_test_matrix_covers_the_new_action(self):
        self.assertIn(ACTION, self.digest.ACTIONS)
        self.assertIn(ACTION, {t["action"] for t in self.digest.MATRIX_TARGETS})
        rows = {label: cells for label, _, cells in self.digest.MATRIX_ROWS}
        self.assertEqual(rows["amend_other_feature target"], (False, True, False))

    def test_ac5_no_pin_file_keeps_the_old_heading_literal(self):
        for path in (THREAT_MODEL_TEST, DOCS_TEST, DIGEST_TEST):
            with self.subTest(file=path.name):
                self.assertNotIn(OLD_NAME, _read(path))

    def test_ac5_each_pin_file_carries_a_comment_naming_this_task(self):
        for path in (THREAT_MODEL_TEST, DOCS_TEST, DIGEST_TEST):
            with self.subTest(file=path.name):
                self.assertNotEqual(_task_comment_lines(_read(path)), [])

    # -- negative proofs ----------------------------------------------------

    def test_ac5_the_comment_probe_fires_only_on_a_comment_naming_the_task(self):
        self.assertNotEqual(
            _task_comment_lines(f"# Refreshed by {TASK_REFERENCE}: seven actions"), []
        )
        self.assertEqual(_task_comment_lines("# Refreshed: seven actions"), [])
        self.assertEqual(
            _task_comment_lines(f'assertEqual(x, "{TASK_REFERENCE}")'), []
        )


if __name__ == "__main__":
    unittest.main()
