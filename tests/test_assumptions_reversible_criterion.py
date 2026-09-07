"""Tests for task0001 (assumptions-reversible-criteria): pins the
`assumptions[].reversible` judgement criterion at its single normative
definition site and its binding citation in the six worker-facing
documents of the three packet-capable workers (requirements-analyst,
implementation-planner, rework-planner, and their three worker contracts).

Covers task0001 Acceptance Criteria
(feature-docs/assumptions-reversible-criteria/tasks/task0001.md):

- AC-1: the definition site (`references/question-packet-schema.md`)
  states both halves of the criterion.
- AC-2 / AC-3: each of the six citing documents (three agent prompts,
  three worker contracts) carries the criterion in condensed form plus
  the pointer to the owning schema document, asserted per file so a
  single omission fails alone and names the file that lost it.
- AC-4: `references/question-resolution.md` is unmodified by this task;
  its four abort arms, the Precedence reservation, the surviving-abort
  enumeration, the batch relaxation, the Classification gate's
  direction-2 irreversibility check, and the worker-declared-basis
  paragraph are all still present.
- AC-5: the module's matcher fails when the criterion is stripped
  (forged) from any one of the seven documents, and passes against the
  real tree, per document.
- AC-6: every matcher/extractor this module introduces has a
  non-vacuity companion -- forged text constructed in-memory (never
  written to a file) that the matcher accepts, proving no assertion can
  pass by matching nothing.
- AC-7: no `gate_id` new to this feature appears in any of the seven
  documents, none of them cites a `task00NN` identifier or a
  `feature-docs/` path as attribution to this feature, and every test
  module under `tests/` imports only standard-library names.

C1 (the criterion token set) and C2 (the definition-site / citing-site
role split) are IMPLEMENTATION.md's shared contracts for this feature
(task0001, task0002).

A note on AC-7's attribution check (NFR3): task0001.md's Design section
reads this as attribution *to this feature* specifically ("as
attribution"), not a blanket ban on the substrings `task00NN` /
`feature-docs/` anywhere in the seven documents -- several of them
already carry unrelated, pre-existing `task00NN` numbering-format
examples (e.g. "starting at `task0001` (task0001, task0002, ...)") and
generic `feature-docs/{feature}/...` template placeholders that this
task neither introduces nor is asked to remove. `_has_feature_attribution`
below checks the two concrete fingerprints an attribution to *this*
feature would actually leave: the feature's own name (as it would appear
in a `feature-docs/assumptions-reversible-criteria/...` path) and one of
this feature's own task-plan filenames (`task00NN.md`).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EM_WORKFLOW = REPO_ROOT / "em-workflow"
TESTS_DIR = REPO_ROOT / "tests"

DEFINITION_DOC = EM_WORKFLOW / "references" / "question-packet-schema.md"
CONSUMPTION_DOC = EM_WORKFLOW / "references" / "question-resolution.md"

CITING_DOCS = {
    "agents/requirements-analyst.md": EM_WORKFLOW / "agents" / "requirements-analyst.md",
    "agents/implementation-planner.md": EM_WORKFLOW / "agents" / "implementation-planner.md",
    "agents/rework-planner.md": EM_WORKFLOW / "agents" / "rework-planner.md",
    "references/contracts/analyst-contract.md": EM_WORKFLOW
    / "references"
    / "contracts"
    / "analyst-contract.md",
    "references/contracts/planner-contract.md": EM_WORKFLOW
    / "references"
    / "contracts"
    / "planner-contract.md",
    "references/contracts/rework-planner-contract.md": EM_WORKFLOW
    / "references"
    / "contracts"
    / "rework-planner-contract.md",
}

ALL_SEVEN_DOCS = dict(CITING_DOCS)
ALL_SEVEN_DOCS["references/question-packet-schema.md"] = DEFINITION_DOC


def _read(path):
    return path.read_text(encoding="utf-8")


# --- C1: the criterion token set --------------------------------------
#
# A document carries the criterion iff it contains the field token, the
# irreversible-half phrase, and all three preserved-half phrases; a
# *citing* site additionally contains the pointer token
# (IMPLEMENTATION.md C1).

FIELD_TOKEN = "assumptions[].reversible"
IRREVERSIBLE_HALF = "cannot be undone once applied"
PRESERVED_HALF_TOKENS = ("preserved constraint", "invariant", "pinned by an existing test")
POINTER_TOKEN = "references/question-packet-schema.md"


def _carries_criterion(text):
    """C1: true iff `text` contains the field token, the irreversible-half
    phrase, and all three preserved-half phrases."""
    if FIELD_TOKEN not in text:
        return False
    if IRREVERSIBLE_HALF not in text:
        return False
    return all(token in text for token in PRESERVED_HALF_TOKENS)


def _cites_criterion(text):
    """C1 for a citing site: carries the criterion AND the pointer to the
    owning schema document. A pointer alone -- with the criterion itself
    missing or incomplete -- does not satisfy this (task0001.md Test
    Notes edge case: "a pointer alone is not carrying the criterion")."""
    return _carries_criterion(text) and POINTER_TOKEN in text


def _strip_criterion(text):
    """Forges a copy of `text` with every C1 token removed. Used by AC-5's
    per-file negative proof: the real document must carry the criterion,
    the forged (stripped) copy must not."""
    forged = text
    for token in (FIELD_TOKEN, IRREVERSIBLE_HALF) + PRESERVED_HALF_TOKENS:
        forged = forged.replace(token, "")
    return forged


# Synthetic forged text (constructed here; no file is read or written)
# carrying every C1 token, including the pointer.
FORGED_TEXT_WITH_CRITERION = (
    "`assumptions[].reversible` is `false` only for an assumption about "
    "an operation that cannot be undone once applied; it is `true` for a "
    "preserved constraint, an invariant, or a fact pinned by an existing "
    "test (`references/question-packet-schema.md`)."
)

# Same, but with the pointer stripped -- both halves present, no pointer.
FORGED_TEXT_WITHOUT_POINTER = (
    "`assumptions[].reversible` is `false` only for an assumption about "
    "an operation that cannot be undone once applied; it is `true` for a "
    "preserved constraint, an invariant, or a fact pinned by an existing "
    "test."
)

# A pointer with no criterion at all.
FORGED_TEXT_POINTER_ONLY = "See `references/question-packet-schema.md` for the field list."

# The field name present, but neither half of the criterion.
FORGED_TEXT_FIELD_TOKEN_ONLY = "`assumptions[].reversible` | Boolean |"

# Unrelated prose containing none of the tokens.
FORGED_TEXT_UNRELATED = "This paragraph discusses something else entirely."


# --- AC-7 / NFR2: gate_id absence extractor -----------------------------

_GATE_ID_PREFIXES = (
    "design-system",
    "create-spec",
    "create-plan",
    "implement",
    "develop",
    "design",
    "verify",
    "rework",
    "review",
)
_GATE_ID_RE = re.compile(
    r"\b(" + "|".join(re.escape(prefix) for prefix in _GATE_ID_PREFIXES) + r")\.([a-z][a-z-]*)\b"
)
_GATE_ID_NON_SUFFIXES = {"md", "yaml", "yml", "py", "sh", "json"}


def _gate_ids_in(text):
    """Extracts gate_id-shaped tokens (`<phase-prefix>.<kebab-word>`) from
    `text`, filtering out filename-shaped false positives (e.g.
    `rework.md`, `design.yaml`) by their trailing segment."""
    found = set()
    for match in _GATE_ID_RE.finditer(text):
        if match.group(2) in _GATE_ID_NON_SUFFIXES:
            continue
        found.add(match.group(0))
    return found


# The gate_id set already present in each of the seven documents before
# this feature (computed by reading the pre-edit tree; hardcoded here so
# the absence check does not need to inspect git history -- an absence
# assertion must hold standalone, per IMPLEMENTATION.md C4).
GATE_ID_BASELINE = {
    "references/question-packet-schema.md": frozenset({"rework.spec-change"}),
    "agents/requirements-analyst.md": frozenset(
        {"create-spec.design-step", "create-spec.requirement-clarification"}
    ),
    "agents/implementation-planner.md": frozenset(
        {
            "create-plan.existing-files",
            "create-plan.license-conflict",
            "create-plan.tbd-resolution",
        }
    ),
    "agents/rework-planner.md": frozenset({"rework.spec-change"}),
    "references/contracts/analyst-contract.md": frozenset(
        {"create-spec.design-step", "create-spec.requirement-clarification"}
    ),
    "references/contracts/planner-contract.md": frozenset(
        {
            "create-plan.existing-files",
            "create-plan.license-conflict",
            "create-plan.tbd-resolution",
        }
    ),
    "references/contracts/rework-planner-contract.md": frozenset({"rework.spec-change"}),
}


# --- AC-7 / NFR3: feature-attribution absence checker -------------------

FEATURE_NAME = "assumptions-reversible-criteria"
_TASK_PLAN_FILENAME_RE = re.compile(r"task\d{4}\.md")


def _has_feature_attribution(text):
    """True iff `text` carries a fingerprint of attribution to *this*
    feature: its own name (as it would appear in a
    `feature-docs/assumptions-reversible-criteria/...` path) or one of
    its own task-plan filenames (`task00NN.md`). Deliberately narrower
    than a blanket `task00NN` / `feature-docs/` substring ban -- see the
    module docstring."""
    if FEATURE_NAME in text:
        return True
    return _TASK_PLAN_FILENAME_RE.search(text) is not None


# --- AC-7 / NFR4: standard-library-only import checker -------------------

_STDLIB_MODULES = set(sys.stdlib_module_names) | set(sys.builtin_module_names)


def _imported_top_level_modules(source, filename="<forged>"):
    tree = ast.parse(source, filename=filename)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
    return modules


def _non_stdlib_imports(source, filename="<forged>"):
    return _imported_top_level_modules(source, filename=filename) - _STDLIB_MODULES


# --- AC-4: consumption-site retention -------------------------------------


def _normalize(text):
    """Collapses whitespace runs to a single space, so a pinned substring
    survives incidental markdown line-wrap changes."""
    return re.sub(r"\s+", " ", text)


CONSUMPTION_RETENTION_SUBSTRINGS = (
    # The four fail-closed abort arms.
    "the question's `category` (`references/question-packet-schema.md`) is "
    "`security` or `license`;",
    "the `gate_id` appears on the explicit fail-closed gate list",
    "the question's `category` (`references/question-packet-schema.md`) is "
    "`spec-change`, unless its `gate_id` is exactly `rework.spec-change`",
    "an `assumptions[]` entry whose `related_question_ids` names this question "
    "carries `reversible: false` — an irreversible operation.",
    # The worker-declared-basis paragraph.
    "The irreversibility abort's basis is the packet's own declaration.",
    # The batch relaxation.
    "The batch relaxation.",
    "Conditioned on the `--batch` invocation flag alone",
    # The surviving-abort enumeration.
    "The surviving aborts.",
    "enumerated here, once",
    # The Precedence reservation.
    "Precedence reservation.",
    "The routed arm applies only when none of the three immediate-abort "
    "conditions above holds",
    # The Classification gate's direction-2 irreversibility check.
    "or when an `assumptions[]` entry naming the question carries "
    "`reversible: false` — the one worker-supplied field this direction "
    "reads, its basis worker-declared rather than a second, independent "
    "defence",
)


class TestDefinitionSiteCriterion(unittest.TestCase):
    """AC-1: the schema document's `assumptions[].reversible` row states
    both halves of the criterion."""

    def test_schema_document_states_both_halves(self):
        self.assertTrue(_carries_criterion(_read(DEFINITION_DOC)))


class TestCitingSitesCarryCriterion(unittest.TestCase):
    """AC-2 / AC-3: each of the six citing documents carries the condensed
    criterion plus the pointer, asserted per file so a single omission
    fails alone and names the file that lost it."""

    def test_requirements_analyst_agent_cites_criterion(self):
        self.assertTrue(
            _cites_criterion(_read(CITING_DOCS["agents/requirements-analyst.md"]))
        )

    def test_implementation_planner_agent_cites_criterion(self):
        self.assertTrue(
            _cites_criterion(_read(CITING_DOCS["agents/implementation-planner.md"]))
        )

    def test_rework_planner_agent_cites_criterion(self):
        self.assertTrue(_cites_criterion(_read(CITING_DOCS["agents/rework-planner.md"])))

    def test_analyst_contract_cites_criterion(self):
        self.assertTrue(
            _cites_criterion(
                _read(CITING_DOCS["references/contracts/analyst-contract.md"])
            )
        )

    def test_planner_contract_cites_criterion(self):
        self.assertTrue(
            _cites_criterion(
                _read(CITING_DOCS["references/contracts/planner-contract.md"])
            )
        )

    def test_rework_planner_contract_cites_criterion(self):
        self.assertTrue(
            _cites_criterion(
                _read(CITING_DOCS["references/contracts/rework-planner-contract.md"])
            )
        )


class TestFailsWhenCriterionStrippedPerFile(unittest.TestCase):
    """AC-5: the matcher passes against the real tree and fails against a
    forged, criterion-stripped copy, proved per document (all seven)."""

    def test_definition_site_real_vs_stripped(self):
        real = _read(DEFINITION_DOC)
        self.assertTrue(_carries_criterion(real))
        self.assertFalse(_carries_criterion(_strip_criterion(real)))

    def test_requirements_analyst_agent_real_vs_stripped(self):
        real = _read(CITING_DOCS["agents/requirements-analyst.md"])
        self.assertTrue(_cites_criterion(real))
        self.assertFalse(_cites_criterion(_strip_criterion(real)))

    def test_implementation_planner_agent_real_vs_stripped(self):
        real = _read(CITING_DOCS["agents/implementation-planner.md"])
        self.assertTrue(_cites_criterion(real))
        self.assertFalse(_cites_criterion(_strip_criterion(real)))

    def test_rework_planner_agent_real_vs_stripped(self):
        real = _read(CITING_DOCS["agents/rework-planner.md"])
        self.assertTrue(_cites_criterion(real))
        self.assertFalse(_cites_criterion(_strip_criterion(real)))

    def test_analyst_contract_real_vs_stripped(self):
        real = _read(CITING_DOCS["references/contracts/analyst-contract.md"])
        self.assertTrue(_cites_criterion(real))
        self.assertFalse(_cites_criterion(_strip_criterion(real)))

    def test_planner_contract_real_vs_stripped(self):
        real = _read(CITING_DOCS["references/contracts/planner-contract.md"])
        self.assertTrue(_cites_criterion(real))
        self.assertFalse(_cites_criterion(_strip_criterion(real)))

    def test_rework_planner_contract_real_vs_stripped(self):
        real = _read(CITING_DOCS["references/contracts/rework-planner-contract.md"])
        self.assertTrue(_cites_criterion(real))
        self.assertFalse(_cites_criterion(_strip_criterion(real)))

    def test_citing_site_with_pointer_but_missing_preserved_half_fails(self):
        # Edge case (Test Notes): a document that contains the pointer but
        # has lost one half of the criterion must fail.
        real = _read(CITING_DOCS["agents/requirements-analyst.md"])
        forged = real
        for token in PRESERVED_HALF_TOKENS:
            forged = forged.replace(token, "")
        self.assertIn(POINTER_TOKEN, forged)
        self.assertFalse(_cites_criterion(forged))

    def test_citing_site_with_pointer_but_missing_irreversible_half_fails(self):
        real = _read(CITING_DOCS["agents/requirements-analyst.md"])
        forged = real.replace(IRREVERSIBLE_HALF, "")
        self.assertIn(POINTER_TOKEN, forged)
        self.assertFalse(_cites_criterion(forged))


class TestNonVacuity(unittest.TestCase):
    """AC-6: every matcher/extractor this module introduces is proved
    non-vacuous -- it rejects forged text missing what it looks for, and
    accepts/detects forged text (constructed here, never read from a
    file) containing it."""

    # _carries_criterion / _cites_criterion --------------------------------

    def test_carries_criterion_accepts_forged_text_with_criterion(self):
        self.assertTrue(_carries_criterion(FORGED_TEXT_WITH_CRITERION))

    def test_carries_criterion_rejects_unrelated_forged_text(self):
        self.assertFalse(_carries_criterion(FORGED_TEXT_UNRELATED))

    def test_carries_criterion_rejects_field_token_alone(self):
        # Edge case (Test Notes): the definition site must not be accepted
        # merely because it contains the field name.
        self.assertFalse(_carries_criterion(FORGED_TEXT_FIELD_TOKEN_ONLY))

    def test_carries_criterion_requires_every_preserved_half_token(self):
        for missing in PRESERVED_HALF_TOKENS:
            with self.subTest(missing=missing):
                kept = [token for token in PRESERVED_HALF_TOKENS if token != missing]
                text = (
                    f"`{FIELD_TOKEN}` is `false` only for an operation that "
                    f"{IRREVERSIBLE_HALF}; it is `true` for " + ", ".join(kept) + "."
                )
                self.assertFalse(_carries_criterion(text))

    def test_cites_criterion_accepts_forged_text_with_pointer(self):
        self.assertTrue(_cites_criterion(FORGED_TEXT_WITH_CRITERION))

    def test_cites_criterion_rejects_forged_text_missing_pointer(self):
        self.assertTrue(_carries_criterion(FORGED_TEXT_WITHOUT_POINTER))
        self.assertFalse(_cites_criterion(FORGED_TEXT_WITHOUT_POINTER))

    def test_cites_criterion_rejects_pointer_only_forged_text(self):
        # Edge case (Test Notes): a pointer alone is not "carrying the
        # criterion".
        self.assertFalse(_carries_criterion(FORGED_TEXT_POINTER_ONLY))
        self.assertFalse(_cites_criterion(FORGED_TEXT_POINTER_ONLY))

    # _gate_ids_in -----------------------------------------------------

    def test_gate_id_extractor_finds_nothing_in_unrelated_forged_text(self):
        self.assertEqual(_gate_ids_in(FORGED_TEXT_UNRELATED), set())

    def test_gate_id_extractor_detects_forged_new_gate_id(self):
        forged = "This decision point's `gate_id` is `create-spec.totally-new-gate`."
        self.assertIn("create-spec.totally-new-gate", _gate_ids_in(forged))

    def test_gate_id_extractor_ignores_file_extension_shaped_tokens(self):
        forged = "See `rework.md` for details, and `design.yaml` too."
        self.assertEqual(_gate_ids_in(forged), set())

    # _has_feature_attribution ------------------------------------------

    def test_feature_attribution_checker_rejects_unrelated_forged_text(self):
        self.assertFalse(_has_feature_attribution(FORGED_TEXT_UNRELATED))

    def test_feature_attribution_checker_detects_forged_feature_path(self):
        forged = (
            "See feature-docs/assumptions-reversible-criteria/tasks/task0001.md "
            "for rationale."
        )
        self.assertTrue(_has_feature_attribution(forged))

    def test_feature_attribution_checker_detects_forged_task_plan_filename(self):
        forged = "Introduced by task0002.md."
        self.assertTrue(_has_feature_attribution(forged))

    def test_feature_attribution_checker_ignores_bare_task_id_example(self):
        # The pre-existing numbering-format examples in these documents
        # (e.g. "starting at `task0001` (task0001, task0002, ...)") are
        # not attribution and must not be flagged.
        forged = "Number every task taskNNNN in order, starting at task0001."
        self.assertFalse(_has_feature_attribution(forged))

    # _non_stdlib_imports --------------------------------------------------

    def test_stdlib_checker_accepts_forged_stdlib_only_source(self):
        forged_source = "import re\nimport unittest\nfrom pathlib import Path\n"
        self.assertEqual(_non_stdlib_imports(forged_source), set())

    def test_stdlib_checker_detects_forged_non_stdlib_import(self):
        forged_source = "import numpy\n"
        self.assertEqual(_non_stdlib_imports(forged_source), {"numpy"})

    # consumption-site retention non-vacuity -------------------------------

    def test_consumption_retention_substrings_absent_from_forged_stripped_copy(self):
        real = _normalize(_read(CONSUMPTION_DOC))
        forged = real
        for substring in CONSUMPTION_RETENTION_SUBSTRINGS:
            forged = forged.replace(substring, "")
        for substring in CONSUMPTION_RETENTION_SUBSTRINGS:
            with self.subTest(substring=substring[:60]):
                self.assertNotIn(substring, forged)


class TestConsumptionSiteUnmodified(unittest.TestCase):
    """AC-4: `question-resolution.md` is unmodified by this task; its four
    abort arms, the Precedence reservation, the surviving-abort
    enumeration, the batch relaxation, the Classification gate's
    direction-2 irreversibility check, and the worker-declared-basis
    paragraph are all still present."""

    @classmethod
    def setUpClass(cls):
        cls.text = _normalize(_read(CONSUMPTION_DOC))

    def test_retains_every_pinned_substring(self):
        for substring in CONSUMPTION_RETENTION_SUBSTRINGS:
            with self.subTest(substring=substring[:60]):
                self.assertIn(substring, self.text)


class TestNoNewGateId(unittest.TestCase):
    """AC-7 / NFR2: no `gate_id` identifier new to this feature appears in
    any of the seven documents. Enumerates the gate identifiers already
    present (pre-feature baseline, hardcoded above) and asserts the
    extracted set does not grow -- an absence property, so it also holds
    in a worktree where a sibling task's edits are absent
    (IMPLEMENTATION.md C4)."""

    def test_no_document_gains_a_new_gate_id(self):
        for relative, path in ALL_SEVEN_DOCS.items():
            with self.subTest(document=relative):
                baseline = GATE_ID_BASELINE[relative]
                found = _gate_ids_in(_read(path))
                self.assertTrue(
                    found <= baseline,
                    f"{relative} gained gate_id(s) not in the pre-feature "
                    f"baseline: {sorted(found - baseline)}",
                )


class TestNoFeatureAttribution(unittest.TestCase):
    """AC-7 / NFR3: none of the seven documents cites a `task00NN`
    identifier or a `feature-docs/` path as attribution to this feature
    (see the module docstring for the exact fingerprint checked)."""

    def test_no_document_carries_feature_attribution(self):
        for relative, path in ALL_SEVEN_DOCS.items():
            with self.subTest(document=relative):
                self.assertFalse(_has_feature_attribution(_read(path)))


class TestStandardLibraryOnlyImports(unittest.TestCase):
    """AC-7 / NFR4: every test module under `tests/` imports only
    standard-library names."""

    def test_every_test_module_imports_only_stdlib(self):
        violations = {}
        for path in sorted(TESTS_DIR.glob("*.py")):
            non_std = _non_stdlib_imports(_read(path), filename=str(path))
            if non_std:
                violations[path.name] = non_std
        self.assertEqual(violations, {}, f"non-stdlib imports found: {violations}")


if __name__ == "__main__":
    unittest.main()
