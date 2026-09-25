"""Tests for task0001: the gate-option-vocabulary correspondence check.

Covers task0001 Acceptance Criteria
(feature-docs/batch-policy-option-id-consistency/tasks/task0001.md):

- AC-1: every `action: select` entry of `em-workflow/references/batch-
  policies.yaml` has at least one declaring document, and each declaring
  document's `## Gate option vocabulary` block offers that entry's
  `option_id`. The check covers all eleven select gates (the issuing-site
  map's key set), not a subset, and reports the offending gate and document
  path when it fails.
- AC-2: the design-step gate's policy `option_id` is unchanged
  (`decide_autonomously`) and is declared by both analyst-contract.md and
  requirements-analyst.md; the design-system gate's policy `option_id` is
  unchanged (`top_candidate_or_none`) and create-spec-phase.md's section 11a
  declares it alongside the three `kind` values it already documents.
- AC-3: every option_id that existed only in batch-policies.yaml before this
  change (feature-identity, design-system, license-conflict, existing-files,
  TBD-resolution, stalled) is unchanged and now has a declared row at its
  gate's issuing site.
- AC-4: a mutated policy option_id, a vocabulary block missing the named
  option, and an option_id present only in an unrelated field elsewhere in
  the same document (e.g. `on_unanswered: record_tbd`, a real question-
  packet field whose value collides with the `create-spec.stalled` policy
  option_id) each make the check fail -- proven against synthetic document
  trees, never merely asserted about the real repository.
- AC-5: covered by tests/test_batch_policies.py's policy-structure half
  (this module owns correspondence facts only -- IMPLEMENTATION.md D5).
- AC-6: `em-workflow/references/workflow-patch.md`,
  `em-workflow/scripts/validate-worker-output.py`,
  `tests/test_validate_worker_output.py`, and the
  `valid-design-step-correct-binding` fixture are byte-identical to their
  pre-task0001 state; a digest mismatch on any of them fails a test here.
- AC-7: this module imports no third-party package (test/README.md, no
  external test dependencies).

The `## Gate option vocabulary` block format and the issuing-site map are
this module's own pinned data (IMPLEMENTATION.md Shared Components: "Gate
option vocabulary block", "Issuing-site map" -- both owned by this module,
D2). The exemption registry (`references/gate-option-vocabulary.md`) now
exists with zero data rows: the section extractor, the row parser, the
row validator and the exemption loader all live in the shared helper
`tests/_gate_vocabulary.py` (exemption-registry-section-scope/task0001);
this module only consumes the loader, passing it the `action: select`
gate-id set it has already parsed from batch-policies.yaml, and degrades
to zero exemptions when the registry file is absent, unreadable, or has
no `## Exemption registry` section.

Restricted-subset `gate_policies:` YAML parsing duplicates
tests/test_batch_policies.py's hand-rolled parser rather than importing it
(no test module imports another in this repository; PyYAML is a runtime
dependency of the plugin, not a test dependency -- test/README.md).
"""

import ast
import hashlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

import _gate_vocabulary

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
HELPER_PATH = TESTS_DIR / "_gate_vocabulary.py"
POLICY_PATH = REPO_ROOT / "em-workflow" / "references" / "batch-policies.yaml"
EXEMPTION_REGISTRY_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "gate-option-vocabulary.md"
)

GATE_OPTION_VOCAB_HEADING = "## Gate option vocabulary"
TABLE_ROW_RE = re.compile(r"^\|(.*)\|\s*$")
SEPARATOR_ROW_RE = re.compile(r"^\|[\s\-:|]+\|\s*$")
BACKTICK_RE = re.compile(r"`([^`]+)`")

# The pinned issuing-site map (IMPLEMENTATION.md D2): gate_id -> the
# repository-relative document paths that must declare that gate's
# vocabulary. Its key set is asserted equal to batch-policies.yaml's
# `action: select` gate set below (TestRepositoryCorrespondence).
ISSUING_SITE_MAP = {
    "create-spec.feature-identity": (
        "em-workflow/references/phases/create-spec-phase.md",
    ),
    "create-spec.design-step": (
        "em-workflow/references/contracts/analyst-contract.md",
        "em-workflow/agents/requirements-analyst.md",
    ),
    "create-spec.design-system": (
        "em-workflow/references/phases/create-spec-phase.md",
    ),
    "design-system.reclassify": (
        "em-workflow/references/contracts/designer-contract.md",
    ),
    "create-spec.artifact-overwrite": (
        "em-workflow/references/contracts/spec-writer-contract.md",
    ),
    "design.artifact-overwrite": (
        "em-workflow/references/contracts/spec-writer-contract.md",
    ),
    "create-plan.artifact-overwrite": (
        "em-workflow/references/contracts/spec-writer-contract.md",
    ),
    "create-spec.stalled": (
        "em-workflow/references/phases/create-spec-phase.md",
    ),
    "create-plan.tbd-resolution": (
        "em-workflow/references/contracts/planner-contract.md",
        "em-workflow/agents/implementation-planner.md",
    ),
    "create-plan.license-conflict": (
        "em-workflow/references/contracts/planner-contract.md",
        "em-workflow/agents/implementation-planner.md",
    ),
    "create-plan.existing-files": (
        "em-workflow/references/contracts/planner-contract.md",
        "em-workflow/agents/implementation-planner.md",
    ),
}

# D1 pairs: documents that declare the same gate must offer the same
# option_id SET, not merely overlap.
D1_PAIRED_GATES = {
    "create-spec.design-step": (
        "em-workflow/references/contracts/analyst-contract.md",
        "em-workflow/agents/requirements-analyst.md",
    ),
    "create-plan.tbd-resolution": (
        "em-workflow/references/contracts/planner-contract.md",
        "em-workflow/agents/implementation-planner.md",
    ),
    "create-plan.license-conflict": (
        "em-workflow/references/contracts/planner-contract.md",
        "em-workflow/agents/implementation-planner.md",
    ),
    "create-plan.existing-files": (
        "em-workflow/references/contracts/planner-contract.md",
        "em-workflow/agents/implementation-planner.md",
    ),
}


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_gate_policies(text):
    """Parse the `gate_policies:` block out of a restricted-subset YAML
    text (batch-policies.yaml's own dialect -- see
    tests/test_batch_policies.py's module docstring). Returns
    {gate_id: {key: value_str}}. Raises ValueError on a structural
    violation, matching test_batch_policies.py's parser."""
    lines = text.splitlines()
    gate_policies = {}
    in_block = False
    current_gate = None
    saw_block = False

    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not in_block:
            if line == "gate_policies:":
                in_block = True
                saw_block = True
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            break
        if indent == 2:
            if not stripped.endswith(":"):
                raise ValueError(f"expected a gate-ID key, got: {raw!r}")
            current_gate = stripped[:-1]
            gate_policies[current_gate] = {}
        elif indent == 4:
            if current_gate is None or ":" not in stripped:
                raise ValueError(f"unexpected line in gate block: {raw!r}")
            key, _, value = stripped.partition(":")
            gate_policies[current_gate][key.strip()] = value.strip()
        else:
            raise ValueError(f"unexpected indentation: {raw!r}")

    if not saw_block:
        raise ValueError("no top-level `gate_policies:` key found")
    return gate_policies


def extract_vocabulary_section(text):
    """Returns the body text following the `## Gate option vocabulary`
    heading, up to (not including) the next level-2 `## ` heading or EOF.
    Returns None when the document has no such heading at all (the
    "absent section" parser case)."""
    idx = text.find(GATE_OPTION_VOCAB_HEADING)
    if idx == -1:
        return None
    rest = text[idx + len(GATE_OPTION_VOCAB_HEADING) :]
    m = re.search(r"^## ", rest, re.MULTILINE)
    if m:
        return rest[: m.start()]
    return rest


def parse_vocabulary_rows(text, doc_label="<document>"):
    """Parses the `## Gate option vocabulary` block of `text`. Returns a
    list of (gate_id, option_id, meaning) tuples -- empty when the section
    is absent, or present but carries no table at all (the "section present
    but empty" case). Raises ValueError, naming `doc_label` and the
    offending row, when a row inside an actually-present table is malformed
    (the block's postcondition is enforced loudly -- IMPLEMENTATION.md
    "Error-handling policy for the verification layer": a malformed block
    must never silently degrade to an empty option set, since that would
    make a missing declaration look like a passing check)."""
    section = extract_vocabulary_section(text)
    if section is None:
        return []

    table_lines = [
        ln for ln in section.splitlines() if TABLE_ROW_RE.match(ln.strip())
    ]
    if not table_lines:
        return []

    if len(table_lines) < 2 or not SEPARATOR_ROW_RE.match(table_lines[1].strip()):
        raise ValueError(
            f"{doc_label}: `{GATE_OPTION_VOCAB_HEADING}` table has no valid "
            f"header separator row (first table line: {table_lines[0]!r})"
        )

    rows = []
    for raw in table_lines[2:]:
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) != 3:
            raise ValueError(
                f"{doc_label}: malformed `{GATE_OPTION_VOCAB_HEADING}` row "
                f"(expected 3 cells, got {len(cells)}): {raw!r}"
            )
        gate_cell, option_cell, meaning = cells
        gate_tokens = BACKTICK_RE.findall(gate_cell)
        option_tokens = BACKTICK_RE.findall(option_cell)
        if len(gate_tokens) != 1:
            raise ValueError(
                f"{doc_label}: malformed `{GATE_OPTION_VOCAB_HEADING}` row "
                f"(gate_id cell must carry exactly one backtick-quoted "
                f"token): {raw!r}"
            )
        if len(option_tokens) != 1:
            raise ValueError(
                f"{doc_label}: malformed `{GATE_OPTION_VOCAB_HEADING}` row "
                f"(option_id cell must carry exactly one backtick-quoted "
                f"token): {raw!r}"
            )
        if not meaning.strip():
            raise ValueError(
                f"{doc_label}: malformed `{GATE_OPTION_VOCAB_HEADING}` row "
                f"(empty meaning): {raw!r}"
            )
        rows.append((gate_tokens[0], option_tokens[0], meaning.strip()))
    return rows


def options_for_gate(rows, gate_id):
    return {option_id for (gid, option_id, _meaning) in rows if gid == gate_id}


def gate_offers_option(text, gate_id, option_id, doc_label="<document>"):
    """True iff `text`'s vocabulary block declares `option_id` for
    `gate_id`. Never raises for a well-formed-but-non-matching block; still
    raises ValueError on a genuinely malformed row (parse_vocabulary_rows'
    loud-failure rule)."""
    rows = parse_vocabulary_rows(text, doc_label)
    return option_id in options_for_gate(rows, gate_id)


# A well-formed synthetic document reused across several hermetic tests.
WELL_FORMED_DOC = """# Some Contract

Intro prose that is not part of the block.

## Gate option vocabulary

| gate_id | option_id | meaning |
|---|---|---|
| `example.gate` | `preserve_and_reuse` | Treat the existing artifact as authoritative. |
| `example.gate` | `overwrite` | Replace the existing artifact. |

## Some Other Section

Unrelated prose after the block.
"""


class TestVocabularyBlockParser(unittest.TestCase):
    """Hermetic: the parser and its failure modes (Test Notes: "well-formed,
    malformed row, absent section, section present but empty")."""

    def test_well_formed_block_parses_every_row(self):
        rows = parse_vocabulary_rows(WELL_FORMED_DOC, "doc.md")
        self.assertEqual(
            set(rows),
            {
                ("example.gate", "preserve_and_reuse", "Treat the existing artifact as authoritative."),
                ("example.gate", "overwrite", "Replace the existing artifact."),
            },
        )

    def test_absent_section_returns_no_rows(self):
        self.assertEqual(
            parse_vocabulary_rows("# No such section in this document.\n", "doc.md"),
            [],
        )

    def test_section_present_but_empty_returns_no_rows(self):
        doc = "## Gate option vocabulary\n\nNothing here yet.\n\n## Next Section\ncontent\n"
        self.assertEqual(parse_vocabulary_rows(doc, "doc.md"), [])

    def test_malformed_row_wrong_cell_count_raises(self):
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| `example.gate` | `overwrite` |\n"
        )
        with self.assertRaises(ValueError):
            parse_vocabulary_rows(doc, "doc.md")

    def test_malformed_row_missing_backticks_on_gate_id_raises(self):
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| example.gate | `overwrite` | Replace the existing artifact. |\n"
        )
        with self.assertRaises(ValueError):
            parse_vocabulary_rows(doc, "doc.md")

    def test_malformed_row_missing_backticks_on_option_id_raises(self):
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| `example.gate` | overwrite | Replace the existing artifact. |\n"
        )
        with self.assertRaises(ValueError):
            parse_vocabulary_rows(doc, "doc.md")

    def test_malformed_row_double_backtick_span_raises(self):
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| `example.gate` `other.gate` | `overwrite` | Replace the existing artifact. |\n"
        )
        with self.assertRaises(ValueError):
            parse_vocabulary_rows(doc, "doc.md")

    def test_malformed_row_empty_meaning_raises(self):
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| `example.gate` | `overwrite` |  |\n"
        )
        with self.assertRaises(ValueError):
            parse_vocabulary_rows(doc, "doc.md")

    def test_error_message_names_document_and_row(self):
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| example.gate | `overwrite` | Replace the existing artifact. |\n"
        )
        with self.assertRaises(ValueError) as ctx:
            parse_vocabulary_rows(doc, "my-doc.md")
        self.assertIn("my-doc.md", str(ctx.exception))


class TestCorrespondenceDecisionHermetic(unittest.TestCase):
    """Hermetic: the membership decision (AC-4), including the two
    non-vacuity-critical negative cases: a vocabulary block that omits the
    named option, and a mutated/renamed policy value that the document was
    never updated to match."""

    def test_member_option_is_offered(self):
        self.assertTrue(
            gate_offers_option(WELL_FORMED_DOC, "example.gate", "preserve_and_reuse")
        )

    def test_non_member_option_is_not_offered(self):
        self.assertFalse(gate_offers_option(WELL_FORMED_DOC, "example.gate", "abort"))

    def test_option_declared_for_a_different_gate_does_not_count(self):
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| `other.gate` | `preserve_and_reuse` | Wrong gate entirely. |\n"
        )
        self.assertFalse(gate_offers_option(doc, "example.gate", "preserve_and_reuse"))

    def test_mutated_policy_option_id_is_detected_as_missing(self):
        # Simulates a document that was never updated after the policy's
        # option_id changed (e.g. a rename from preserve_and_reuse to
        # preserve_and_reuse_v2): the old value no longer appears, so the
        # check must fail rather than match on a stale row.
        mutated = WELL_FORMED_DOC.replace("preserve_and_reuse", "preserve_and_reuse_v2")
        self.assertFalse(gate_offers_option(mutated, "example.gate", "preserve_and_reuse"))

    def test_vocabulary_block_missing_the_named_option_fails(self):
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| `example.gate` | `overwrite` | Replace the existing artifact. |\n"
        )
        self.assertFalse(gate_offers_option(doc, "example.gate", "preserve_and_reuse"))

    def test_on_unanswered_field_value_elsewhere_does_not_count(self):
        # A real, repository-observed ambiguity: `on_unanswered` is a
        # question-packet field whose own enum includes `record_tbd`
        # (question-packet-schema.md), the very same string used as
        # `create-spec.stalled`'s policy option_id. A document that
        # mentions `on_unanswered: record_tbd` in prose, without a
        # corresponding `## Gate option vocabulary` table row, must not be
        # read as declaring that option.
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            "| `create-spec.stalled` | `abort_create_spec` | Abort create-spec. |\n"
            "\n"
            "## Batch answer handling\n\n"
            "A question in this category might carry `on_unanswered: record_tbd`\n"
            "as its default -- a question-packet field value, not a declared row.\n"
        )
        self.assertFalse(gate_offers_option(doc, "create-spec.stalled", "record_tbd"))


class TestSyntheticDocumentTree(unittest.TestCase):
    """Exercises the full read-from-disk path (not just in-memory strings)
    against synthetic document trees built in a temporary directory (Test
    Notes: "synthetic document trees built in temporary directories")."""

    def test_correspondence_passes_against_a_synthetic_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc_path = Path(tmp) / "contract.md"
            doc_path.write_text(WELL_FORMED_DOC, encoding="utf-8")
            rows = parse_vocabulary_rows(read_text(doc_path), doc_label=str(doc_path))
            self.assertIn("preserve_and_reuse", options_for_gate(rows, "example.gate"))

    def test_correspondence_fails_against_a_synthetic_tree_with_mutated_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc_path = Path(tmp) / "contract.md"
            mutated = WELL_FORMED_DOC.replace("preserve_and_reuse", "preserve_and_reuse_v2")
            doc_path.write_text(mutated, encoding="utf-8")
            rows = parse_vocabulary_rows(read_text(doc_path), doc_label=str(doc_path))
            self.assertNotIn("preserve_and_reuse", options_for_gate(rows, "example.gate"))

    def test_malformed_row_raises_when_read_from_a_real_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc_path = Path(tmp) / "contract.md"
            doc_path.write_text(
                "## Gate option vocabulary\n\n"
                "| gate_id | option_id | meaning |\n"
                "|---|---|---|\n"
                "| example.gate | `overwrite` | Replace the existing artifact. |\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                parse_vocabulary_rows(read_text(doc_path), doc_label=str(doc_path))
            self.assertIn(str(doc_path), str(ctx.exception))


class TestExemptionRegistryDegrade(unittest.TestCase):
    """Hermetic: the absent/present-but-empty exemption-registry degrade,
    through the shared loader `_gate_vocabulary.load_exempt_gate_ids`
    (D3, Test Notes, exemption-registry-section-scope/task0001)."""

    def test_absent_file_yields_zero_exemptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = Path(tmp) / "gate-option-vocabulary.md"
            self.assertEqual(
                _gate_vocabulary.load_exempt_gate_ids(
                    missing_path, {"create-spec.feature-identity"}
                ),
                set(),
            )

    def test_present_file_parses_listed_gate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "gate-option-vocabulary.md"
            registry_path.write_text(
                "## Exemption registry\n\n"
                "| gate_id | reason | compensating guarantee |\n"
                "|---|---|---|\n"
                "| `create-spec.feature-identity` | cannot be checked mechanically | manual review each release |\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _gate_vocabulary.load_exempt_gate_ids(
                    registry_path, {"create-spec.feature-identity"}
                ),
                {"create-spec.feature-identity"},
            )

    def test_present_but_zero_row_file_yields_zero_exemptions(self):
        # D3: "at the end of this feature the registry holds zero rows" --
        # a present-but-empty registry must degrade the same as an absent
        # one, not raise or vacuously exempt anything.
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "gate-option-vocabulary.md"
            registry_path.write_text(
                "## Exemption registry\n\n"
                "| gate_id | reason | compensating guarantee |\n"
                "|---|---|---|\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _gate_vocabulary.load_exempt_gate_ids(
                    registry_path, {"create-spec.feature-identity"}
                ),
                set(),
            )

    def test_real_repository_registry_is_present_with_zero_rows(self):
        # FR8, SPEC A-5: references/gate-option-vocabulary.md has merged in
        # from exemption-registry-section-scope/task0001's sibling doc task
        # and now exists, with its `## Exemption registry` table holding
        # zero data rows. The correspondence sweep below
        # (TestRepositoryCorrespondence) still covers all eleven select
        # gates unconditionally -- confirmed there, not here.
        self.assertTrue(EXEMPTION_REGISTRY_PATH.is_file())
        policy = _parse_gate_policies(read_text(POLICY_PATH))
        select_ids = {
            gid for gid, attrs in policy.items() if attrs.get("action") == "select"
        }
        self.assertEqual(
            _gate_vocabulary.load_exempt_gate_ids(EXEMPTION_REGISTRY_PATH, select_ids),
            set(),
        )


def _write_doc_and_load(doc_text, select_ids, filename="gate-option-vocabulary.md"):
    """Test helper: writes `doc_text` to a temp file and calls the shared
    loader against it with `select_ids`. Returns the loader's result, or
    lets the loader's ValueError propagate."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        path.write_text(doc_text, encoding="utf-8")
        return _gate_vocabulary.load_exempt_gate_ids(path, select_ids)


class TestExemptionRegistrySectionExtractorHermetic(unittest.TestCase):
    """AC-2 (FR1): the shared extractor's section boundaries, asserted
    directly against `_gate_vocabulary.extract_exemption_registry_section`."""

    def test_section_starts_after_the_heading_and_ends_before_next_level2_heading(self):
        doc = (
            "# Doc\n"
            "## Exemption registry\n"
            "body line 1\n"
            "body line 2\n"
            "## Scope\n"
            "unrelated\n"
        )
        section = _gate_vocabulary.extract_exemption_registry_section(doc)
        self.assertEqual(section, "body line 1\nbody line 2\n")

    def test_section_runs_to_end_of_text_when_no_next_heading(self):
        doc = "## Exemption registry\nonly body\n"
        section = _gate_vocabulary.extract_exemption_registry_section(doc)
        self.assertEqual(section, "only body\n")

    def test_document_without_the_heading_gives_the_no_section_result(self):
        self.assertIsNone(
            _gate_vocabulary.extract_exemption_registry_section(
                "# Doc\nno heading here\n"
            )
        )


class TestExemptionRowParserHermetic(unittest.TestCase):
    """AC-3 (FR2): the shared row parser, asserted directly against
    `_gate_vocabulary.parse_exemption_table_rows`."""

    def test_skips_header_and_separator_and_returns_one_tuple_per_data_row(self):
        section = (
            "\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            "| `gate.a` | reason a | guarantee a |\n"
            "| `gate.b` | reason b | guarantee b |\n"
        )
        rows = _gate_vocabulary.parse_exemption_table_rows(section)
        self.assertEqual(
            rows,
            [
                ("`gate.a`", "reason a", "guarantee a"),
                ("`gate.b`", "reason b", "guarantee b"),
            ],
        )

    def test_data_row_with_wrong_cell_count_raises(self):
        section = (
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            "| `gate.a` | reason a |\n"
        )
        with self.assertRaises(ValueError):
            _gate_vocabulary.parse_exemption_table_rows(section)

    def test_section_with_no_pipe_table_line_raises(self):
        with self.assertRaises(ValueError):
            _gate_vocabulary.parse_exemption_table_rows("\nJust prose, no table here.\n")


class TestExemptionLoaderHermeticRegression(unittest.TestCase):
    """AC-5 (FR5, FR6): `_gate_vocabulary.load_exempt_gate_ids` against
    synthetic documents built in a temporary directory, with an explicit
    select set (Test Notes; exemption-registry-section-scope/task0001,
    the ticket's own reproduction case is (a))."""

    def test_a_unrelated_vocabulary_table_before_zero_row_registry_gives_empty_set(self):
        unrelated_gate = "create-spec.feature-identity"
        doc = (
            "## Gate option vocabulary\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            f"| `{unrelated_gate}` | `derive_from_task_description` | derive the feature name. |\n"
            "\n"
            "## Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
        )
        # Non-vacuity precondition: the fixture really does hold a
        # pipe-table line naming the unrelated gate, and that line sits
        # outside the extractor's returned section.
        pipe_line = next(
            line
            for line in doc.splitlines()
            if unrelated_gate in line and line.strip().startswith("|")
        )
        section = _gate_vocabulary.extract_exemption_registry_section(doc)
        self.assertIsNotNone(section)
        self.assertNotIn(pipe_line, section)

        self.assertEqual(
            _write_doc_and_load(doc, {unrelated_gate}), set()
        )

    def test_b_table_in_scope_section_after_registry_is_not_counted(self):
        exempt_gate = "create-plan.existing-files"
        unrelated_gate = "create-spec.feature-identity"
        doc = (
            "## Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{exempt_gate}` | cannot be checked mechanically | manual review each release |\n"
            "\n"
            "## Scope\n\n"
            "| gate_id | option_id | meaning |\n"
            "|---|---|---|\n"
            f"| `{unrelated_gate}` | `derive_from_task_description` | derive the feature name. |\n"
        )
        # Non-vacuity precondition, same shape as case (a) above.
        pipe_line = next(
            line
            for line in doc.splitlines()
            if unrelated_gate in line and line.strip().startswith("|")
        )
        section = _gate_vocabulary.extract_exemption_registry_section(doc)
        self.assertIsNotNone(section)
        self.assertNotIn(pipe_line, section)

        self.assertEqual(
            _write_doc_and_load(doc, {exempt_gate, unrelated_gate}), {exempt_gate}
        )

    def test_c1_row_missing_reason_raises_with_violation_substring(self):
        gate = "create-spec.feature-identity"
        doc = (
            "## Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{gate}` |  | manual review each release |\n"
        )
        with self.assertRaises(ValueError) as ctx:
            _write_doc_and_load(doc, {gate})
        self.assertIn("missing a reason", str(ctx.exception))

    def test_c2_row_missing_guarantee_raises_with_violation_substring(self):
        gate = "create-spec.feature-identity"
        doc = (
            "## Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{gate}` | some reason |  |\n"
        )
        with self.assertRaises(ValueError) as ctx:
            _write_doc_and_load(doc, {gate})
        self.assertIn("missing a compensating guarantee", str(ctx.exception))

    def test_c3_row_naming_a_gate_outside_the_select_set_raises_with_violation_substring(self):
        gate = "create-spec.feature-identity"
        doc = (
            "## Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{gate}` | some reason | some guarantee |\n"
        )
        with self.assertRaises(ValueError) as ctx:
            _write_doc_and_load(doc, set())  # empty select set: gate is "outside" it
        self.assertIn("not an `action: select` entry", str(ctx.exception))

    def test_c4_row_with_wrong_cell_count_raises(self):
        doc = (
            "## Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            "| `create-spec.feature-identity` | only one more cell |\n"
        )
        with self.assertRaises(ValueError):
            _write_doc_and_load(doc, {"create-spec.feature-identity"})

    def test_d_valid_row_gives_exactly_its_gate_id(self):
        gate = "create-plan.existing-files"
        doc = (
            "## Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{gate}` | cannot be checked mechanically | manual review each release |\n"
        )
        self.assertEqual(_write_doc_and_load(doc, {gate}), {gate})

    def test_level3_subheading_inside_registry_section_does_not_end_it(self):
        gate = "create-spec.feature-identity"
        doc = (
            "## Exemption registry\n\n"
            "### Notes\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{gate}` | cannot be checked mechanically | manual review each release |\n"
        )
        self.assertEqual(_write_doc_and_load(doc, {gate}), {gate})

    def test_level3_exemption_registry_heading_is_not_a_section_start(self):
        gate = "create-spec.feature-identity"
        doc = (
            "### Exemption registry\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{gate}` | cannot be checked mechanically | manual review each release |\n"
        )
        self.assertEqual(_write_doc_and_load(doc, {gate}), set())

    def test_midline_mention_of_the_heading_is_not_a_section_start(self):
        gate = "create-spec.feature-identity"
        doc = (
            "Prose that talks about the ## Exemption registry heading "
            "without starting one.\n\n"
            "| gate_id | reason | compensating guarantee |\n"
            "|---|---|---|\n"
            f"| `{gate}` | cannot be checked mechanically | manual review each release |\n"
        )
        self.assertEqual(_write_doc_and_load(doc, {gate}), set())

    def test_present_section_with_prose_but_no_table_raises(self):
        doc = (
            "## Exemption registry\n\n"
            "This section has prose but never gets to a table.\n"
        )
        with self.assertRaises(ValueError):
            _write_doc_and_load(doc, set())


def _module_level_function_names(source):
    """Returns the set of names bound by a module-level `def`/`async def`
    in `source` (top-level only -- a `def` nested inside a class or
    another function does not count)."""
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _modules_defining_any_of(tests_dir, names):
    """Returns {file_name: overlap_names} for every `test_*.py` file
    directly under `tests_dir` whose module-level function definitions
    overlap `names`."""
    offenders = {}
    for path in sorted(Path(tests_dir).glob("test_*.py")):
        overlap = _module_level_function_names(path.read_text(encoding="utf-8")) & names
        if overlap:
            offenders[path.name] = overlap
    return offenders


def _top_level_import_names(source):
    """Returns the set of top-level module names `source` imports, from
    both `import x[.y]` and `from x[.y] import ...` statements."""
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


class TestSharedHelperStaticCheckDetectorsHermetic(unittest.TestCase):
    """Non-vacuity companions for TestSharedHelperContract below: prove the
    two AST-based detector functions actually flag a synthetic violation
    before trusting them against the real tests/ directory."""

    def test_function_definition_detector_flags_a_synthetic_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "test_fake_one.py").write_text(
                "def load_exempt_gate_ids(x):\n    return x\n", encoding="utf-8"
            )
            (tmp_path / "test_fake_two.py").write_text(
                "def something_else():\n    pass\n", encoding="utf-8"
            )
            offenders = _modules_defining_any_of(tmp_path, {"load_exempt_gate_ids"})
            self.assertEqual(set(offenders), {"test_fake_one.py"})

    def test_function_definition_detector_is_silent_with_no_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "test_fake_one.py").write_text(
                "def something_else():\n    pass\n", encoding="utf-8"
            )
            offenders = _modules_defining_any_of(tmp_path, {"load_exempt_gate_ids"})
            self.assertEqual(offenders, {})

    def test_import_name_detector_flags_a_synthetic_cross_module_import(self):
        self.assertIn(
            "test_gate_option_vocabulary_doc",
            _top_level_import_names("import test_gate_option_vocabulary_doc\n"),
        )

    def test_import_name_detector_flags_a_synthetic_from_import(self):
        self.assertIn(
            "_gate_vocabulary",
            _top_level_import_names(
                "from _gate_vocabulary import load_exempt_gate_ids\n"
            ),
        )


class TestSharedHelperContract(unittest.TestCase):
    """AC-1 (FR4, NFR1, NFR5): the shared helper's structural contract."""

    SHARED_NAMES = {
        "extract_exemption_registry_section",
        "parse_exemption_table_rows",
        "validate_exemption_rows",
        "load_exempt_gate_ids",
    }

    def test_helper_file_exists_with_a_name_unittest_discover_will_not_collect(self):
        self.assertTrue(HELPER_PATH.is_file())
        self.assertFalse(HELPER_PATH.name.startswith("test"))

    def test_helper_defines_no_testcase_subclass(self):
        tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
        class_names = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
        self.assertEqual(class_names, [])

    def test_helper_imports_only_standard_library_modules(self):
        stdlib_names = set(sys.stdlib_module_names)
        imported = _top_level_import_names(HELPER_PATH.read_text(encoding="utf-8"))
        self.assertEqual(imported - stdlib_names, set())

    def test_helper_is_the_sole_definer_of_the_shared_names_among_test_modules(self):
        offenders = _modules_defining_any_of(TESTS_DIR, self.SHARED_NAMES)
        self.assertEqual(offenders, {})

    def test_both_consumer_modules_import_the_helper_and_not_each_other(self):
        doc_side = _top_level_import_names(
            (TESTS_DIR / "test_gate_option_vocabulary_doc.py").read_text(encoding="utf-8")
        )
        consumer_side = _top_level_import_names(
            (TESTS_DIR / "test_gate_option_vocabulary.py").read_text(encoding="utf-8")
        )
        self.assertIn("_gate_vocabulary", doc_side)
        self.assertIn("_gate_vocabulary", consumer_side)
        self.assertNotIn("test_gate_option_vocabulary", doc_side)
        self.assertNotIn("test_gate_option_vocabulary_doc", consumer_side)


class TestDigestPinMechanismHermetic(unittest.TestCase):
    """Non-vacuity companion for the frozen-file digest pins below: proves
    the sha256-comparison matcher itself reports a mismatch when the
    underlying fact is untrue."""

    def test_mismatched_content_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "frozen.txt"
            p.write_text("original content", encoding="utf-8")
            original_digest = hashlib.sha256(p.read_bytes()).hexdigest()
            p.write_text("mutated content", encoding="utf-8")
            self.assertNotEqual(
                hashlib.sha256(p.read_bytes()).hexdigest(), original_digest
            )


class TestRepositoryCorrespondence(unittest.TestCase):
    """Integration: the real repository. Reads layers 1 (batch-
    policies.yaml) and 2 (the seven issuing documents) once and applies the
    same decision the hermetic half already proved correct (AC-1, AC-2,
    AC-3, D1)."""

    @classmethod
    def setUpClass(cls):
        cls.policy_text = read_text(POLICY_PATH)
        cls.policy = _parse_gate_policies(cls.policy_text)
        cls.select_ids = {
            gid for gid, attrs in cls.policy.items() if attrs.get("action") == "select"
        }
        cls._doc_cache = {}

    def _rows_for(self, rel_path):
        if rel_path not in self._doc_cache:
            path = REPO_ROOT / rel_path
            self._doc_cache[rel_path] = parse_vocabulary_rows(
                read_text(path), doc_label=rel_path
            )
        return self._doc_cache[rel_path]

    # -- AC-1 -----------------------------------------------------------

    def test_issuing_site_map_matches_policy_select_gate_set(self):
        self.assertEqual(set(ISSUING_SITE_MAP.keys()), self.select_ids)

    def test_every_select_gate_option_is_declared_at_every_issuing_site(self):
        exempt = _gate_vocabulary.load_exempt_gate_ids(
            EXEMPTION_REGISTRY_PATH, self.select_ids
        )
        offenders = []
        for gate_id, doc_paths in ISSUING_SITE_MAP.items():
            if gate_id in exempt:
                continue
            option_id = self.policy[gate_id].get("option_id")
            for rel_path in doc_paths:
                rows = self._rows_for(rel_path)
                if option_id not in options_for_gate(rows, gate_id):
                    offenders.append(
                        f"{gate_id} @ {rel_path}: missing option_id {option_id!r}"
                    )
        self.assertEqual(offenders, [], "\n".join(offenders))

    # -- AC-2 -------------------------------------------------------------

    def test_design_step_option_id_unchanged(self):
        self.assertEqual(
            self.policy["create-spec.design-step"]["option_id"], "decide_autonomously"
        )

    def test_design_system_option_id_unchanged(self):
        self.assertEqual(
            self.policy["create-spec.design-system"]["option_id"],
            "top_candidate_or_none",
        )

    def test_design_step_declared_by_both_contract_and_prompt(self):
        for rel_path in ISSUING_SITE_MAP["create-spec.design-step"]:
            rows = self._rows_for(rel_path)
            self.assertIn(
                "decide_autonomously", options_for_gate(rows, "create-spec.design-step")
            )

    def test_design_system_declares_three_kind_values_alongside_policy_value(self):
        rows = self._rows_for("em-workflow/references/phases/create-spec-phase.md")
        options = options_for_gate(rows, "create-spec.design-system")
        self.assertEqual(
            options, {"top_candidate_or_none", "project_native", "em_workflow", "none"}
        )

    # -- AC-3 ---------------------------------------------------------------

    def test_previously_policy_only_option_ids_unchanged(self):
        expected = {
            "create-spec.feature-identity": "derive_from_task_description",
            "create-spec.design-system": "top_candidate_or_none",
            "create-plan.license-conflict": "compatible_alternative",
            "create-plan.existing-files": "merge",
            "create-plan.tbd-resolution": "assume",
            "create-spec.stalled": "record_tbd",
        }
        for gate_id, option_id in expected.items():
            with self.subTest(gate_id=gate_id):
                self.assertEqual(self.policy[gate_id]["option_id"], option_id)

    # -- D1 -------------------------------------------------------------

    def test_d1_paired_documents_offer_identical_option_sets(self):
        for gate_id, (doc_a, doc_b) in D1_PAIRED_GATES.items():
            with self.subTest(gate_id=gate_id):
                self.assertEqual(
                    options_for_gate(self._rows_for(doc_a), gate_id),
                    options_for_gate(self._rows_for(doc_b), gate_id),
                )


class TestFrozenMachineReadSurface(unittest.TestCase):
    """AC-6: byte-identity pins for the two frozen files and the design-step
    fixture (IMPLEMENTATION.md "Frozen machine-read surface"), plus the one
    pinned line of the existing validator test module whose expectation
    depends on the policy's design-step option_id staying
    `decide_autonomously`."""

    WORKFLOW_PATCH_PATH = REPO_ROOT / "em-workflow" / "references" / "workflow-patch.md"
    VALIDATE_WORKER_OUTPUT_PATH = (
        REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
    )
    TEST_VALIDATE_WORKER_OUTPUT_PATH = REPO_ROOT / "tests" / "test_validate_worker_output.py"
    FIXTURE_PATH = (
        REPO_ROOT
        / "em-workflow"
        / "references"
        / "fixtures"
        / "question-packet"
        / "gate-registry"
        / "valid-design-step-correct-binding"
        / "input.json"
    )

    # Updated by goal-vs-spec-divergence/task0002, which owned
    # em-workflow/references/workflow-patch.md and intentionally edited it
    # (the freeze this pin enforces was scoped to the
    # batch-policy-option-id-consistency implementation window, which had
    # completed; the pin was refreshed there, not removed, to keep guarding
    # against future incidental edits).
    #
    # Refreshed again by goal-vs-spec-divergence/task0013 (review round 1
    # rework), which also intentionally edits workflow-patch.md (the
    # re-planning permission conditions and task-id allocation rule) --
    # same rationale: refresh, don't remove, so the guard keeps catching
    # future incidental edits.
    #
    # Refreshed again by goal-vs-spec-divergence/task0017 (review round 2
    # rework), which settles the re-planning permission contract in one
    # place: the second Re-planning path case now reads an UNCONSUMED
    # `spec_change` record (with its reading position named), the
    # Re-planning task-id allocation section gains the "must re-declare
    # every registered id" rule, and the Application rules list gains rule
    # 17 for it. Same rationale as the two refreshes above: refresh, don't
    # remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0022 (review round 3
    # rework, finding consumed-flag-split): the Re-planning path's second
    # case now reads a `spec_change` record carrying an UNSPENT
    # RE-PLANNING AUTHORIZATION (`replan_authorized`) instead of an
    # unconsumed record -- `consumed`'s value is explicitly excluded from
    # the decision (references/phase-state.md's `spec_change` flag pair).
    # Same rationale: refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0023 (review round 3,
    # D10, merged after task0022): the `tasks_patch` block gains
    # `carried_task_ids`, the Re-planning task-id allocation section is
    # rewritten around the carried_task_ids/entries disjoint-set split,
    # application rule 12 narrows to `entries` only, rule 17 is restated in
    # terms of `carried_task_ids`, and the `preserve` section gains the
    # carried-id remark. Same rationale: refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0029: the document
    # gains a new Application rule 18 -- once a re-planning `replace_all`
    # has been applied, the orchestrator sets that record's
    # `spec_change.replan_authorized` to `false`, in the same phase-state
    # write that records the application (the one consumption procedure
    # AC-1 requires) -- and the "All seventeen rules" count statement
    # becomes "All eighteen rules" in the same edit (D12). Same rationale:
    # refresh, don't remove.
    #
    # Refreshed again by rework-contract-drift/task0002 (D2: task0002 is
    # this file's sole owner for this specific pin): the unspent
    # re-planning authorization condition now names the origin pair
    # (`origin_kind` / `origin_id`) instead of the retired single-field
    # name it used to require, the document gains a new Application rule
    # 19 (recovery and idempotency for an interruption between rule 15's
    # patch write and rule 18's authorization-spending write) -- the "All
    # eighteen rules" count statement becomes "All nineteen rules" in the
    # same edit -- and the Ownership boundary section gains a paragraph
    # naming rule 18's crossing into phase-state. Same rationale: refresh,
    # don't remove.
    #
    # Refreshed again by rework-contract-drift/task0008 (review round1
    # rework, D9: task0008 is the sole owner of this pin for the round):
    # rule 19 relocates entirely OUT of the numbered Application rules
    # list into its own titled section ("## Interrupted authorization-
    # spend recovery"), whose recognition condition now defers to
    # `references/phase-state.md`'s own already-applied determination
    # (keyed by the patch's own `patch_id`) instead of a bare
    # `base_workflow_blob` mismatch -- the "All nineteen rules" count
    # statement reverts to "All eighteen rules" in the same edit. Same
    # rationale: refresh, don't remove.
    #
    # Refreshed again by task-tier-reduction/task0011 (review round 1
    # rework): the Re-planning path's own bullet now names the
    # tier-upgrade procedure (`skills/develop/SKILL.md`) as a second
    # source of an explicit re-plan, alongside the SPEC-change transition
    # -- the record it writes before setting `create-plan` to
    # `needs_update` is an authorized `spec_change` record on the same
    # terms as the SPEC-change transition's own. Same rationale: refresh,
    # don't remove.
    WORKFLOW_PATCH_SHA256 = (
        "4a4f075844b960655fe882c49e8b0a78f6b91e8c5370743e1280d0b6f39c0a7e"
    )
    # Updated by goal-vs-spec-divergence/task0016 (review round1 rework),
    # which the user's SPEC.md/REQUIREMENTS.md Declared Change Set extension
    # brought em-workflow/scripts/** into (phase-state/rework.yaml
    # deviation_from_transition) so the replace_all permission check could
    # be made to agree with workflow-patch.md's two permitted paths. As with
    # WORKFLOW_PATCH_SHA256 above, the pin is refreshed, not removed, to
    # keep guarding against future incidental edits of these two files.
    #
    # Refreshed again by goal-vs-spec-divergence/task0017 (review round 2
    # rework): the re-entry recognition helper now resolves its signal from
    # `{feature-dir}/phase-state/rework.yaml` or a `--phase-state` mapping
    # whose own `phase` is `rework` (never any mapping carrying a
    # `spec_change` record, which is what task0016 had left in place and
    # which task0013's canonical invocation could never actually satisfy),
    # `REQUIRED_PRESERVE_BY_OPERATION` stays operation-flat while the
    # path-dependent mandatory-preserve and task-id-allocation checks move
    # into `_validate_dry_run_apply`'s `replace_all` branch. Same rationale:
    # refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0024 (review round 3,
    # AC-4/AC-5): the gate registry's category binding gains the reverse
    # direction -- `_gate_ids_for_category` plus the category -> gate_id
    # check inside `validate_question`, closing the direction where
    # `category: spec-change` paired with an unregistered or
    # worker-unattributed `gate_id` previously passed with no error. Same
    # rationale: refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0022 (review round 3
    # rework, finding consumed-flag-split):
    # `workflow_replace_all_spec_change_reentry` now checks
    # `spec_change.replan_authorized` (present, boolean, `True`) for the
    # re-planning-authorization judgement and no longer consults
    # `consumed` at all. Same rationale: refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0025 (review round 3
    # rework): `ANSWER_SOURCE_VALUES` gains `batch-classification-gate` (the
    # batch-only classification gate's proceed-outcome answer source,
    # references/question-resolution.md's Classification gate Outcome
    # step). Same rationale: refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0023 (review round 3,
    # D10, merged after task0022 and task0025): `validate_workflow_patch`
    # gains a structural `tasks_patch.carried_task_ids` shape check, the
    # `elif is_replanning:` branch of `_validate_dry_run_apply` is rewritten
    # around `carried_task_ids` (three independently reported rejection
    # codes instead of the old drop/reuse pair), and `apply_patch`'s
    # `replace_planning` arm now copies a carried id's record from the
    # pre-apply workflow verbatim. Same rationale: refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0029: `classifier`
    # verdict / decision value constants are added, `validate_phase_state`
    # gains the `classification` list-shape and field checks (an
    # append-type list, never a wholesale-replaced mapping), and
    # `SPEC_CHANGE_MANDATORY_FIELDS` moves from the retired single-field
    # origin identifier to the `origin_kind` / `origin_id` pair
    # (references/rework-task-synthesis.md -- a `verify`-sourced record is
    # accepted on the same terms as a `review`-sourced one, D13). Same
    # rationale: refresh, don't remove.
    #
    # Refreshed again by rework-contract-drift/task0004 (FR3, FR4, FR6):
    # `ORIGIN_KIND_VALUES` and `FAILED_ITEM_CATEGORY_VALUES` are added;
    # `workflow_replace_all_spec_change_reentry` enforces `origin_kind`'s
    # closed vocabulary; `validate_workflow_patch` enforces
    # `workflow.yaml`'s verify-step `failed_items[].category` closed
    # vocabulary via the new `_validate_verify_failed_items_categories`;
    # `validate_question` rejects a `rework.spec-change` question with no
    # `evidence[]` entry carrying a non-empty `origin_id`; the packet
    # schema's evidence field's retired single-field name is renamed to
    # `origin_id` in `SPEC_CHANGE_MANDATORY_FIELDS`'s neighboring comment,
    # and the retired name is removed from every comment in this script.
    # Same rationale: refresh, don't remove.
    #
    # Refreshed again by rework-contract-drift/task0008 (review round1
    # rework, D9: task0008 is the sole owner of this pin for the round):
    # `_validate_verify_failed_items_categories` gains a mandatory `patch`
    # parameter and a new `_verify_step_targeted_by_patch` helper -- the
    # category check now errors only for the entries of a verify step the
    # patch targets via `step_patches`, never for a pre-existing entry a
    # patch neither supplies nor targets (a defect no worker can repair).
    # The call site inside `validate_workflow_patch` passes `data` (the
    # patch) through. Same rationale: refresh, don't remove.
    #
    # Refreshed again by batch-codex-autonomous-decisions/task0004 (FR19):
    # the on_unanswered != "block" rejection message's parenthetical
    # rationale is reworded (from justifying the check by "the batch
    # abort" to the reason that survives it -- a worker cannot choose the
    # non-blocking handling for spec-change / security / license
    # questions). No accept/reject behaviour changes (D5).
    # PINNED_VALIDATOR_TEST_LINE below is unaffected and still asserted.
    # Same rationale: refresh, don't remove.
    #
    # Refreshed again by task-tier-reduction/task0008 (FR24, NFR4):
    # `_validate_rework_index` gains a `verification_doc_absent` fail-closed
    # branch -- when a task declares `new_scenarios` but the feature
    # directory has no VERIFICATION.md to diff (the most-reducing tier
    # never produces one until the tier is upgraded), the check now reports
    # a distinct error naming that case instead of silently passing.
    # PINNED_VALIDATOR_TEST_LINE below is unaffected and still asserted.
    # Same rationale: refresh, don't remove.
    #
    # Refreshed again by task-tier-reduction/task0010 (AC-1 through AC-4):
    # `_validate_task_plans_against_patch` gains the task-document
    # exemption -- a task entry whose `plan` value's final path segment
    # equals the task document's file name (`TASK.md`) skips only the
    # Files-section reconciliation and Acceptance Criteria presence
    # checks; every other check (path safety, symlink rejection,
    # containment, existence, size) still applies unconditionally.
    # PINNED_VALIDATOR_TEST_LINE below is unaffected and still asserted.
    # Same rationale: refresh, don't remove.
    #
    # Refreshed again by task-id-allocation-ssot/task0002: the re-planning
    # allocation comment above the replace_all carry-over checks is
    # reworded to describe what the code enforces (registered ids are
    # carried via tasks_patch.carried_task_ids and are not re-declared
    # under tasks_patch.entries) instead of the stale "entries must
    # re-declare every registered id" premise; it now cites
    # workflow-patch.md "Re-planning task-id allocation" (IMPLEMENTATION.md
    # C1). No executable-code line changes. PINNED_VALIDATOR_TEST_LINE
    # below is unaffected and still asserted. Same rationale: refresh,
    # don't remove.
    VALIDATE_WORKER_OUTPUT_SHA256 = (
        "c92a6529b6d0f71a7b2e76ff988a6b7f17b212985b547aa3c6d72d829dd4c92a"
    )
    # Refreshed again by goal-vs-spec-divergence/task0017 (review round 2
    # rework): TestReplanningReentrySignalHelper gains the tightened-
    # contract cases (phase/feature match, unconsumed record, the
    # feature-dir equivalent source) and TestCanonicalReentryInvocation /
    # TestReplanningMandatoryPreserveAndTaskIdAllocation are new. Same
    # rationale as the two refreshes above: refresh, don't remove --
    # PINNED_VALIDATOR_TEST_LINE below is unaffected and still asserted.
    #
    # Refreshed again by goal-vs-spec-divergence/task0024 (review round 3,
    # AC-4/AC-5): TestGateRegistryDerivation gains the rework.spec-change
    # registration pins, and TestSpecChangeCategoryGateBidirectionalBinding
    # is new, proving the category -> gate_id direction the validator gains
    # above. PINNED_VALIDATOR_TEST_LINE below is unaffected and still
    # asserted. Same rationale: refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0022 (review round 3
    # rework, finding consumed-flag-split): TestReplanningReentrySignal
    # Helper's `consumed`-keyed cases are renamed/re-pointed at
    # `replan_authorized` (`consumed: true` no longer blocks re-entry), new
    # `replan_authorized` direction cases are added, and
    # `test_consumed_spec_change_record_is_rejected` is renamed/re-pointed
    # at the new `invalid-replace-all-replan-authorization-spent` fixture.
    # PINNED_VALIDATOR_TEST_LINE below is unaffected and still asserted.
    #
    # Refreshed again by goal-vs-spec-divergence/task0025 (review round 3
    # rework): adds TestGateResolvedAnswerSource, pinning
    # `batch-classification-gate` in `ANSWER_SOURCE_VALUES` and that a real
    # answer object using it validates. Same rationale: refresh, don't
    # remove -- PINNED_VALIDATOR_TEST_LINE below is unaffected and still
    # asserted.
    #
    # Refreshed again by goal-vs-spec-divergence/task0023 (review round 3,
    # D10, merged after task0022 and task0025): `TestCanonicalReentryInvocation.
    # _patch_obj` and `TestReplanningMandatoryPreserveAndTaskIdAllocation`
    # move to the carried_task_ids/entries carry-over form, and
    # `TestReplanningCarryOverEnforcement` is new (the
    # `replace-all-entry-for-registered-id` rejection). PINNED_VALIDATOR_
    # TEST_LINE below is unaffected and still asserted. Same rationale:
    # refresh, don't remove.
    #
    # Refreshed again by goal-vs-spec-divergence/task0029: every
    # retired-single-field-keyed fixture literal moves to the `origin_kind`
    # / `origin_id` pair (`_rework_phase_state`, the `--dry-run-apply`
    # canonical-invocation YAML builders), matching the validator's renamed
    # `SPEC_CHANGE_MANDATORY_FIELDS`. PINNED_VALIDATOR_TEST_LINE below is
    # unaffected and still asserted. Same rationale: refresh, don't remove.
    #
    # Refreshed again by rework-contract-drift/task0004: origin_kind's
    # closed vocabulary is enforced in
    # workflow_replace_all_spec_change_reentry (FR6); a
    # rework.spec-change question's evidence[] origin-naming obligation is
    # enforced in validate_question (FR4); the packet schema's evidence
    # field's retired single-field name is renamed to origin_id, and the
    # retired name is removed from every comment. New
    # TestOriginIdEvidenceRequirement /
    # TestFailedItemCategoryVocabulary / TestOriginKindVocabulary classes
    # cover the new enforcement. PINNED_VALIDATOR_TEST_LINE below is
    # unaffected and still asserted. Same rationale: refresh, don't remove.
    #
    # Refreshed again by rework-contract-drift/task0008 (review round1
    # rework, D9: task0008 is the sole owner of this pin for the round):
    # `TestFailedItemCategoryVocabulary` is updated in place -- every
    # direct call to `_validate_verify_failed_items_categories` now
    # supplies a patch, and the class gains the untargeted/targeted
    # scoping cases (including under `--dry-run-apply`) -- and the wiring
    # test's patch now targets the verify step via `step_patches`.
    # PINNED_VALIDATOR_TEST_LINE below is unaffected and still asserted.
    # Same rationale: refresh, don't remove.
    #
    # Refreshed again by batch-codex-autonomous-decisions/task0004 (FR18,
    # FR20, FR21): TestQuestionPacketSchemaBlockRationale is new (pins
    # question-packet-schema.md's on_unanswered: block constraint sentence
    # verbatim and its reworded rationale), TestIrreversibleAssumption
    # FixtureAccepted is new (direct-run assertion for the new
    # `valid-irreversible-assumption-blocking` fixture), and
    # TestQuestionCategoryForcesBlockingUnanswered gains
    # test_rejection_message_states_the_surviving_rationale (the
    # message-rationale pin). PINNED_VALIDATOR_TEST_LINE below is
    # unaffected and still asserted. Same rationale: refresh, don't remove.
    TEST_VALIDATE_WORKER_OUTPUT_SHA256 = (
        "295f1843403079f58fe1506de63b574ed81e3d01bb764ddf087970d5fe2f2760"
    )
    FIXTURE_SHA256 = (
        "c8414e673876bb05dc9d35c571b35e255a53c185586d7bc876edf5aadd1f05f5"
    )

    PINNED_VALIDATOR_TEST_LINE = (
        '        self.assertEqual(entry["required_option_id"], "decide_autonomously")'
    )

    @staticmethod
    def _sha256(path):
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def test_workflow_patch_md_byte_identical(self):
        self.assertEqual(self._sha256(self.WORKFLOW_PATCH_PATH), self.WORKFLOW_PATCH_SHA256)

    def test_validate_worker_output_py_byte_identical(self):
        self.assertEqual(
            self._sha256(self.VALIDATE_WORKER_OUTPUT_PATH),
            self.VALIDATE_WORKER_OUTPUT_SHA256,
        )

    def test_test_validate_worker_output_py_byte_identical(self):
        self.assertEqual(
            self._sha256(self.TEST_VALIDATE_WORKER_OUTPUT_PATH),
            self.TEST_VALIDATE_WORKER_OUTPUT_SHA256,
        )

    def test_design_step_fixture_byte_identical(self):
        self.assertEqual(self._sha256(self.FIXTURE_PATH), self.FIXTURE_SHA256)

    def test_pinned_validator_test_line_unchanged(self):
        text = read_text(self.TEST_VALIDATE_WORKER_OUTPUT_PATH)
        self.assertIn(self.PINNED_VALIDATOR_TEST_LINE, text)


if __name__ == "__main__":
    unittest.main()
