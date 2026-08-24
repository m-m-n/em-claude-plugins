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
D2). The exemption registry (`references/gate-option-vocabulary.md`) is
owned by a sibling task (D3); this module only consumes it, degrading to
zero exemptions when the file is absent -- which it is, in this task's own
worktree.

Restricted-subset `gate_policies:` YAML parsing duplicates
tests/test_batch_policies.py's hand-rolled parser rather than importing it
(no test module imports another in this repository; PyYAML is a runtime
dependency of the plugin, not a test dependency -- test/README.md).
"""

import hashlib
import os
import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
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


def load_exempt_gate_ids(registry_path):
    """The exemption registry (IMPLEMENTATION.md D3): a single Markdown
    table in `references/gate-option-vocabulary.md` with a gate-id column
    first. A missing or unreadable registry degrades to zero exemptions --
    never a check-skipping condition (D3's own words: the checker holds no
    hardcoded exemption list, so an absent file must not be mistaken for
    "everything is exempt")."""
    registry_path = Path(registry_path)
    if not registry_path.is_file():
        return set()
    try:
        text = read_text(registry_path)
    except OSError:
        return set()

    table_lines = [
        ln for ln in text.splitlines() if TABLE_ROW_RE.match(ln.strip())
    ]
    if len(table_lines) < 2 or not SEPARATOR_ROW_RE.match(table_lines[1].strip()):
        return set()

    ids = set()
    for raw in table_lines[2:]:
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if not cells:
            continue
        tokens = BACKTICK_RE.findall(cells[0])
        if tokens:
            ids.add(tokens[0])
    return ids


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
    """Hermetic: the absent-exemption-registry degrade (D3, Test Notes)."""

    def test_absent_file_yields_zero_exemptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = Path(tmp) / "gate-option-vocabulary.md"
            self.assertEqual(load_exempt_gate_ids(missing_path), set())

    def test_present_file_parses_listed_gate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "gate-option-vocabulary.md"
            registry_path.write_text(
                "# Exemption registry\n\n"
                "| gate_id | reason | compensating guarantee |\n"
                "|---|---|---|\n"
                "| `some.gate` | cannot be checked mechanically | manual review each release |\n",
                encoding="utf-8",
            )
            self.assertEqual(load_exempt_gate_ids(registry_path), {"some.gate"})

    def test_present_but_zero_row_file_yields_zero_exemptions(self):
        # D3: "at the end of this feature the registry holds zero rows" --
        # a present-but-empty registry must degrade the same as an absent
        # one, not raise or vacuously exempt anything.
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "gate-option-vocabulary.md"
            registry_path.write_text(
                "# Exemption registry\n\n"
                "| gate_id | reason | compensating guarantee |\n"
                "|---|---|---|\n",
                encoding="utf-8",
            )
            self.assertEqual(load_exempt_gate_ids(registry_path), set())

    def test_real_repository_registry_is_absent_in_this_worktree(self):
        # D3 cross-task safety: references/gate-option-vocabulary.md is
        # owned by a sibling task and does not exist here. The correspond-
        # ence sweep below (TestRepositoryCorrespondence) must still cover
        # all eleven select gates unconditionally -- confirmed there, not
        # here, since this task's own checker holds no exemption list of
        # its own to fall back on.
        self.assertEqual(load_exempt_gate_ids(EXEMPTION_REGISTRY_PATH), set())


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
        expected = {
            gid for gid, attrs in self.policy.items() if attrs.get("action") == "select"
        }
        self.assertEqual(set(ISSUING_SITE_MAP.keys()), expected)

    def test_every_select_gate_option_is_declared_at_every_issuing_site(self):
        exempt = load_exempt_gate_ids(EXEMPTION_REGISTRY_PATH)
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
    WORKFLOW_PATCH_SHA256 = (
        "4b3c2ca5cfe65eb484135d7822d411a58a286ffa31d6b0713e00019ca007a85a"
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
    VALIDATE_WORKER_OUTPUT_SHA256 = (
        "74f3229ea4fcdf7a93a23cc5898f643a7c5297ebb92a3387e7135388e8fdb07e"
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
    TEST_VALIDATE_WORKER_OUTPUT_SHA256 = (
        "baf3ba899f058399f5d875236cb53715c393b6dc3e79b29f1f8dbe1f6dc98f62"
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
