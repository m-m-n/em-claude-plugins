"""Tests for worker-digest-ownership/task0003: the `design` phase value and
the digest alignment of the three contract documents.

Covers task0003 Acceptance Criteria
(feature-docs/worker-digest-ownership/tasks/task0003.md):

- AC-1 (FR5, TS4): `validate-worker-output.py --kind phase-state` accepts
  an otherwise valid phase-state with `phase: design`, rejects unknown
  values (`designs`, `deploy`) with a failure detail that names the `phase`
  field, and still accepts `create-spec`, `create-plan` and `rework`.
- AC-2 (FR5): phase-state.md's "File layout" lists `design.yaml` (created
  only when the design step dispatches the designer), the `phase` field row
  includes `design`, and the Resume decision table section states that
  `design.yaml`'s `status` never becomes `applying_patch`.
- AC-3 (FR5): worker-envelope.md's input `phase` row includes `design`, the
  document still contains no `expect_digest` token, and the Applicability
  table is unchanged.
- AC-4 (FR2, FR8, NFR2, TS11): phase-state.md's `artifacts` entry and
  worker-envelope.md's "`written_artifacts` reporting" cite the owner
  document `references/artifact-digest.md` by section name; neither restates
  the digest format.
- AC-5 (FR3): spec-writer-contract.md's "Who verifies `expect_digest`" names
  every dispatch site through the owner document, "How the orchestrator
  chooses each target's action before dispatch" cites the owner's
  "Calculation" and "Legacy records", and no sentence directs the worker to
  compute or verify a digest. The heading and the two pinned sentences are
  pinned by tests/test_worker_contracts_create_spec.py
  (TestSpecWriterContract.test_orchestrator_owns_expect_digest_verification);
  the Resume table rows, the Legacy feature compatibility section and the
  `expect_digest` token absence from worker-envelope.md are already pinned
  by tests/test_phase_state_doc.py and tests/test_worker_contract_docs.py.
- AC-6 (NFR1): the validator byte pin in tests/test_gate_option_vocabulary.py
  carries a "Refreshed again by worker-digest-ownership/task0003" comment
  naming the `design` phase value.

The document assertions are section-sliced and whitespace-normalized (no
full-document equality, no dependence on line-break positions); each absence
assertion has a forged-text companion that shows its matcher fires. The
owner document `references/artifact-digest.md` is produced by another task:
these tests read the citing documents only and never the owner.

Standard library only (NFR3).
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
REFERENCES = PLUGIN_ROOT / "references"
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-worker-output.py"
PHASE_STATE_PATH = REFERENCES / "phase-state.md"
ENVELOPE_PATH = REFERENCES / "contracts" / "worker-envelope.md"
SPEC_WRITER_PATH = REFERENCES / "contracts" / "spec-writer-contract.md"
GATE_VOCAB_TEST_PATH = REPO_ROOT / "tests" / "test_gate_option_vocabulary.py"

OWNER_PATH_TOKEN = "references/artifact-digest.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def _heading_level(line):
    match = re.match(r"^(#{1,6}) ", line)
    return len(match.group(1)) if match else 0


def _section(text, heading):
    """Text from the line equal to `heading` up to (not including) the next
    heading of the same or a higher level. Headings inside fenced code
    blocks are ignored. Raises AssertionError when the heading is absent."""
    level = len(heading) - len(heading.lstrip("#"))
    collected = []
    in_section = False
    in_fence = False
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        if stripped.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence:
            current = _heading_level(stripped)
            if in_section and current and current <= level:
                break
            if not in_section and stripped.rstrip() == heading:
                in_section = True
        if in_section:
            collected.append(line)
    if not in_section:
        raise AssertionError(f"heading {heading!r} not found")
    return "".join(collected)


def _table_row(section_text, first_cell):
    """The markdown table row whose first cell is the backticked
    `first_cell`; AssertionError when absent."""
    prefix = f"| `{first_cell}` |"
    for line in section_text.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"table row {prefix!r} not found")


def _sentences(text):
    flat = _normalize_ws(text)
    return [s for s in re.split(r"(?<=[.!?])\s+", flat) if s]


def _cites_section(text, section_name):
    """True when the (already whitespace-normalized) text names the owner
    path token and the quoted section name in the same paragraph-sized
    window."""
    pattern = re.compile(
        re.escape(OWNER_PATH_TOKEN) + r"[^|]{0,400}?[\"“]" + re.escape(section_name) + r"[\"”]"
    )
    return bool(pattern.search(text))


_DIGEST_FORMAT_RESTATEMENT = re.compile(
    r"(raw bytes|hexadecimal|lowercase hex|64 (lower|hex)|hash-object|blob id of)",
    re.IGNORECASE,
)


def _restates_digest_format(text):
    return bool(_DIGEST_FORMAT_RESTATEMENT.search(text))


def _restates_verification_procedure(text):
    """True when the text spells out the orchestrator's calculate-and-compare
    steps (owned by the digest owner document's "Calculation" and
    "Pre-dispatch verification") instead of citing them."""
    return bool(
        re.search(r"computes the sha256|compares it with|compute the sha256", text, re.IGNORECASE)
    )


_WORKER_DIRECTED_DIGEST_ACTION = re.compile(
    r"(?:\b(?:the|a|every|each)\s+)?\b(?:worker|spec-writer)\b\s+"
    r"(?:(?:must|should|shall|will|can|may)\s+)?"
    r"(?:re-?)?(?:compute|computes|hash|hashes|verify|verifies|compare|compares|recompute|recomputes)\b",
    re.IGNORECASE,
)
_SENTENCE_START_IMPERATIVE = re.compile(
    r"^(?:Compute|Hash|Verify|Compare|Recompute)\b[^.]*\b(?:digest|sha256|expect_digest)\b"
)


def _worker_directed_digest_sentences(text):
    """Sentences that tell the worker to compute, hash, verify or compare a
    digest: a worker subject (optionally with a modal) directly followed by
    one of those verbs, or an imperative sentence about a digest. Negated
    forms ("does not compute", "never ...") do not match because the
    negation sits between the subject and the verb."""
    flagged = []
    for sentence in _sentences(text):
        if _WORKER_DIRECTED_DIGEST_ACTION.search(sentence) and re.search(
            r"digest|sha256|expect_digest", sentence, re.IGNORECASE
        ):
            flagged.append(sentence)
        elif _SENTENCE_START_IMPERATIVE.search(sentence):
            flagged.append(sentence)
    return flagged


def _has_expect_digest_token(text):
    return re.search(r"\bexpect_digest\b", text) is not None


def _run_validator(args):
    return subprocess.run(
        [sys.executable, str(VALIDATOR)] + list(args),
        capture_output=True,
        text=True,
    )


def _load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output_under_test", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# AC-1: the validator's phase vocabulary
# ---------------------------------------------------------------------------


class TestPhaseStateValidatorDesignPhase(unittest.TestCase):
    """AC-1 (FR5, TS4)."""

    @staticmethod
    def _phase_state(phase):
        return {
            "schema_version": 1,
            "feature": "example-feature",
            "phase": phase,
            "status": "initialized",
            "generation": 1,
        }

    def _validate(self, phase_state):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "phase-state.json"
            path.write_text(json.dumps(phase_state), encoding="utf-8")
            return _run_validator(
                ["--kind", "phase-state", "--worker", "designer", "--input", str(path)]
            )

    def test_ac1_design_phase_state_is_accepted(self):
        result = self._validate(self._phase_state("design"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ac1_existing_phase_values_are_still_accepted(self):
        for phase in ("create-spec", "create-plan", "rework"):
            with self.subTest(phase=phase):
                result = self._validate(self._phase_state(phase))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ac1_unknown_phase_values_are_rejected_naming_the_phase_field(self):
        for phase in ("designs", "deploy"):
            with self.subTest(phase=phase):
                result = self._validate(self._phase_state(phase))
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                errors = json.loads(result.stdout)["errors"]
                phase_errors = [e for e in errors if e.get("code") == "phase"]
                self.assertTrue(phase_errors, f"no error naming the phase field: {errors}")
                self.assertIn("phase", phase_errors[0]["message"])

    def test_ac1_acceptance_of_design_is_not_vacuous_the_only_difference_is_phase(self):
        accepted = self._phase_state("design")
        rejected = self._phase_state("designs")
        self.assertEqual(
            {k: v for k, v in accepted.items() if k != "phase"},
            {k: v for k, v in rejected.items() if k != "phase"},
        )
        self.assertEqual(self._validate(accepted).returncode, 0)
        self.assertEqual(self._validate(rejected).returncode, 1)

    def test_ac1_gate_registry_attributes_no_gate_to_the_design_phase(self):
        """The shared phase vocabulary also feeds the gate-ID phase prefix
        helper; no worker contract's "Gate identifiers" section names a
        `design.` gate, so the registry is unchanged."""
        module = _load_validator_module()
        registry = module.build_gate_registry(REFERENCES)
        self.assertTrue(registry, "gate registry unexpectedly empty")
        self.assertIsNone(registry["design-system.reclassify"]["phase"])
        design_phase_gates = sorted(
            gate_id for gate_id, entry in registry.items() if entry.get("phase") == "design"
        )
        self.assertEqual(design_phase_gates, [])


# ---------------------------------------------------------------------------
# AC-2 / AC-4: phase-state.md
# ---------------------------------------------------------------------------


class TestPhaseStateDocDesign(unittest.TestCase):
    """AC-2 (FR5) and the phase-state half of AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.layout = _section(cls.text, "## File layout")
        cls.schema = _section(cls.text, "## Schema")
        cls.resume = _section(cls.text, "## Resume decision table")

    @staticmethod
    def _strip_tree_decoration(block):
        return _normalize_ws(re.sub(r"[│├└─#]", " ", block))

    def test_ac2_file_layout_lists_design_yaml(self):
        self.assertIn("design.yaml", self.layout)

    def test_ac2_file_layout_states_design_yaml_exists_only_when_the_designer_is_dispatched(self):
        flat = self._strip_tree_decoration(self.layout)
        self.assertRegex(
            flat,
            r"design\.yaml\s.*?only when the design step dispatches the designer",
        )

    def test_ac2_file_layout_states_no_file_when_the_step_is_skipped(self):
        flat = self._strip_tree_decoration(self.layout)
        self.assertRegex(flat, r"design\.yaml\s.*?no file when the step is `skipped`")

    def test_ac2_phase_field_row_includes_design_and_keeps_the_file_name_rule(self):
        row = _normalize_ws(_table_row(self.schema, "phase"))
        for value in ("create-spec", "create-plan", "rework", "design"):
            self.assertIn(f"`{value}`", row)
        self.assertIn("matches the file name", row)

    def test_ac2_resume_section_states_design_yaml_never_applies_a_patch(self):
        flat = _normalize_ws(self.resume)
        last_row = flat.index("| `completed` |")
        statement = flat[last_row:]
        self.assertIn("`design.yaml`", statement)
        self.assertRegex(statement, r"never becomes `applying_patch`")
        self.assertRegex(statement, r"`applying_patch` rows? .*?do(es)? not apply")

    def test_ac2_resume_table_keeps_every_row_the_statement_does_not_apply_to(self):
        first_cells = [
            line.split("|")[1].strip()
            for line in self.resume.splitlines()
            if line.startswith("| ") and not line.startswith("| phase-state") and "---" not in line
        ]
        self.assertEqual(
            first_cells,
            [
                "`initialized`",
                "`dispatching` (no artifact; `active_request_id`'s run is `discarded_stale`)",
                "`dispatching` (no artifact; otherwise)",
                "`dispatching` (artifact present, no patch proposed)",
                "`awaiting_answers`",
                "`applying_patch` (not yet applied)",
                "`applying_patch` (applied; step not yet `completed`)",
                "`completed`",
            ],
        )

    def test_ac2_resume_section_names_the_reason_the_designer_returns_no_patch(self):
        flat = _normalize_ws(self.resume)
        self.assertRegex(flat, r"designer returns no workflow patch")

    def test_ac4_artifacts_row_cites_the_owner_digest_definition_and_legacy_records(self):
        row = _normalize_ws(_table_row(self.schema, "artifacts"))
        self.assertTrue(_cites_section(row, "Digest definition"), row)
        self.assertIn('"Legacy records"', row)
        self.assertRegex(row, r"not a git blob id")

    def test_ac4_artifacts_row_does_not_restate_the_digest_format(self):
        row = _normalize_ws(_table_row(self.schema, "artifacts"))
        self.assertFalse(_restates_digest_format(row), row)

    def test_ac4_restatement_matcher_fires_on_forged_text(self):
        forged = (
            "`sha256` is the sha256 over the file's raw bytes, rendered as 64 "
            "lowercase hexadecimal digits"
        )
        self.assertTrue(_restates_digest_format(forged))
        self.assertTrue(_restates_digest_format("computed with git hash-object"))

    def test_ac4_citation_matcher_fires_only_with_path_and_section_together(self):
        self.assertTrue(
            _cites_section(
                'see `references/artifact-digest.md` "Digest definition" for it', "Digest definition"
            )
        )
        self.assertFalse(_cites_section('see "Digest definition" for it', "Digest definition"))
        self.assertFalse(
            _cites_section("see `references/artifact-digest.md` for it", "Digest definition")
        )


# ---------------------------------------------------------------------------
# AC-3 / AC-4: worker-envelope.md
# ---------------------------------------------------------------------------


class TestWorkerEnvelopeDocDesign(unittest.TestCase):
    """AC-3 (FR5) and the envelope half of AC-4."""

    # The Applicability table as it stood before this task (AC-3: the table
    # is not edited). Whitespace-normalized.
    APPLICABILITY_TABLE = _normalize_ws(
        """
        | Applies | Does not apply |
        |---|---|
        | `requirements-analyst` (new) | `implementer` |
        | `spec-writer` (new) | `reviewer` / `codex-reviewer` |
        | `rework-planner` (new) | `review-editor` |
        | `implementation-planner` (revised) | `gitignore-guard` / `git-setup-guard` |
        | `designer` (revised) | |
        """
    )

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_PATH)
        cls.inputs = _section(cls.text, "## Input fields")
        cls.reporting = _section(cls.text, "## `written_artifacts` reporting")
        cls.applicability = _section(cls.text, "## Applicability (design-input.md 2.3)")

    def test_ac3_input_phase_row_includes_design_and_the_existing_values(self):
        row = _normalize_ws(_table_row(self.inputs, "phase"))
        for value in ("create-spec", "create-plan", "review", "verify", "rework", "design"):
            self.assertIn(f"`{value}`", row)

    def test_ac3_document_contains_no_expect_digest_token(self):
        self.assertFalse(_has_expect_digest_token(self.text))

    def test_ac3_token_matcher_fires_on_forged_text(self):
        self.assertTrue(_has_expect_digest_token(self.text + "\nsee `expect_digest` here\n"))

    def test_ac3_applicability_table_is_unchanged(self):
        table_lines = [
            line for line in self.applicability.splitlines() if line.startswith("|")
        ]
        self.assertEqual(_normalize_ws("\n".join(table_lines)), self.APPLICABILITY_TABLE)

    def test_ac3_applicability_matcher_fires_on_a_forged_extra_worker(self):
        table_lines = [
            line for line in self.applicability.splitlines() if line.startswith("|")
        ]
        forged = _normalize_ws("\n".join(table_lines + ["| `extra-worker` | |"]))
        self.assertNotEqual(forged, self.APPLICABILITY_TABLE)

    def test_ac4_reporting_section_cites_the_owner_layer5_recording(self):
        self.assertTrue(_cites_section(_normalize_ws(self.reporting), "Layer 5 recording"))

    def test_ac4_reporting_section_keeps_the_worker_stance_sentence(self):
        self.assertIn(
            "The worker does not compute digests", _normalize_ws(self.reporting)
        )

    def test_ac4_reporting_section_does_not_restate_the_digest_format(self):
        self.assertFalse(_restates_digest_format(self.reporting), self.reporting)

    def test_ac4_reporting_section_directs_the_worker_to_no_digest_action(self):
        self.assertEqual(_worker_directed_digest_sentences(self.reporting), [])


# ---------------------------------------------------------------------------
# AC-5: spec-writer-contract.md
# ---------------------------------------------------------------------------


class TestSpecWriterContractDigestOwnership(unittest.TestCase):
    """AC-5 (FR3)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SPEC_WRITER_PATH)
        cls.who_verifies = _section(cls.text, "### Who verifies `expect_digest`")
        cls.action_choice = _section(
            cls.text, "## How the orchestrator chooses each target's action before dispatch"
        )

    def test_ac5_who_verifies_cites_the_owner_dispatch_sites_and_verification(self):
        flat = _normalize_ws(self.who_verifies)
        self.assertTrue(_cites_section(flat, "Dispatch sites"), flat)
        self.assertTrue(_cites_section(flat, "Pre-dispatch verification"), flat)

    def test_ac5_who_verifies_names_all_four_dispatch_sites(self):
        flat = _normalize_ws(self.who_verifies)
        for site in ("create-spec", "design step", "create-plan", "rework"):
            self.assertIn(site, flat, f"dispatch site {site!r} not named")

    def test_ac5_who_verifies_cites_the_procedure_instead_of_restating_it(self):
        flat = _normalize_ws(self.who_verifies)
        self.assertFalse(_restates_verification_procedure(flat), flat)

    def test_ac5_procedure_matcher_fires_on_forged_text(self):
        forged = (
            "Immediately before dispatch the orchestrator computes the sha256 of "
            "every `targets` path and compares it with that `expect_digest`."
        )
        self.assertTrue(_restates_verification_procedure(forged))

    def test_ac5_action_choice_cites_the_owner_calculation_and_legacy_records(self):
        flat = _normalize_ws(self.action_choice)
        self.assertTrue(_cites_section(flat, "Calculation"), flat)
        self.assertTrue(_cites_section(flat, "Legacy records"), flat)

    def test_ac5_contract_directs_the_worker_to_no_digest_action(self):
        self.assertEqual(_worker_directed_digest_sentences(self.text), [])

    def test_ac5_worker_directed_matcher_fires_on_forged_text(self):
        for forged in (
            "The worker computes the sha256 of every target.",
            "The worker must verify `expect_digest` before writing.",
            "A worker should re-verify the digest of each target.",
            "Compute the sha256 of each target before writing.",
            "The spec-writer compares the digest with `expect_digest`.",
        ):
            with self.subTest(forged=forged):
                self.assertTrue(_worker_directed_digest_sentences(forged), forged)

    def test_ac5_worker_directed_matcher_passes_the_negated_and_orchestrator_forms(self):
        for sentence in (
            "The worker does not compute digests and does not re-verify `expect_digest`.",
            "A worker never returns `blocked` because it cannot compute a digest.",
            "The orchestrator verifies `expect_digest`, not the worker.",
            "The orchestrator computes the sha256 of every target.",
        ):
            with self.subTest(sentence=sentence):
                self.assertEqual(_worker_directed_digest_sentences(sentence), [])


# ---------------------------------------------------------------------------
# AC-6: the validator byte pin refresh
# ---------------------------------------------------------------------------


class TestValidatorPinRefreshComment(unittest.TestCase):
    """AC-6 (NFR1): the pin is refreshed in place with its comment, never
    removed."""

    MARKER = "Refreshed again by worker-digest-ownership/task0003"

    @classmethod
    def setUpClass(cls):
        cls.text = _read(GATE_VOCAB_TEST_PATH)

    def test_ac6_pin_carries_the_refresh_comment_naming_the_design_phase_value(self):
        self.assertIn(self.MARKER, self.text)
        start = self.text.index(self.MARKER)
        end = self.text.index("VALIDATE_WORKER_OUTPUT_SHA256 = (", start)
        comment = _normalize_ws(re.sub(r"^\s*#", " ", self.text[start:end], flags=re.MULTILINE))
        self.assertIn("design", comment)
        self.assertIn("phase", comment)

    def test_ac6_the_pin_assignment_still_exists(self):
        self.assertRegex(self.text, r"VALIDATE_WORKER_OUTPUT_SHA256 = \(\s*\"[0-9a-f]{64}\"\s*\)")


if __name__ == "__main__":
    unittest.main()
