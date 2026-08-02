"""Tests for task0001: worker envelope and question-packet/answer contract
documents.

Covers task0001 Acceptance Criteria
(feature-docs/agent-separation/tasks/task0001.md):

- AC-1: `em-workflow/references/contracts/worker-envelope.md` exists and
  documents every input field and every output field listed in
  design-input.md 5.3, with the applicability table from 2.3.
- AC-2: the envelope document defines all six `status` values and, for
  each, the mandatory and forbidden fields.
- AC-3: the envelope document states the `mode_echo` rule, the
  `written_artifacts` digest-reporting rule, and the read-restriction rule.
- AC-4: `em-workflow/references/question-packet-schema.md` exists and
  documents the packet fields, identifier patterns, size limits and the
  complete `category` vocabulary from design-input.md 5.1.
- AC-5: the packet document documents the answer object with its `source`
  vocabulary and all seven consistency rules, marking rules 1-5 as the
  machine-verified subset.
- AC-6: the packet document states that no `on_unanswered` value converts
  an unanswered question into an assumption.
- AC-7: neither document copies a table or rule owned by another SSOT
  listed in design-input.md 10.5; cross-references are path references.

These deliverables are specification documents (task0001.md Test Notes):
verification is by structural assertion rather than behavioural test. The
expected vocabularies (status values, `category` values, envelope field
names, the `source` vocabulary, the consistency-rule count) are derived by
parsing `feature-docs/agent-separation/design-input.md` directly, so the
assertions track the design instead of a hand-copied literal that could
silently drift from it.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN_INPUT_PATH = REPO_ROOT / "feature-docs" / "agent-separation" / "design-input.md"
ENVELOPE_DOC_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "contracts" / "worker-envelope.md"
)
PACKET_DOC_PATH = REPO_ROOT / "em-workflow" / "references" / "question-packet-schema.md"


def _read(path):
    return path.read_text(encoding="utf-8")


def _section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def _yaml_blocks(section_text):
    return re.findall(r"```yaml\n(.*?)```", section_text, re.DOTALL)


def _mapping_keys(yaml_block):
    keys = []
    for line in yaml_block.splitlines():
        match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*):", line)
        if match:
            keys.append(match.group(1))
    return keys


def _backtick_tokens(fragment):
    return re.findall(r"`([a-zA-Z0-9_.\[\]-]+)`", fragment)


def _has_exact_token(text, token):
    """True iff `token` occurs as an exact inline-code span, not merely as a
    substring of a longer identifier or of surrounding prose.

    Edge case (task0001.md Test Notes): a field present in the document but
    spelled differently, or only appearing inside unrelated prose, must NOT
    satisfy this check.
    """
    pattern = r"`" + re.escape(token) + r"`"
    return re.search(pattern, text) is not None


class DesignInputFixtures:
    """Parses design-input.md once and exposes the vocabularies this task's
    two documents must render, so every assertion below tracks the design
    document rather than a copy of it."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(DESIGN_INPUT_PATH)
        return cls._text

    @classmethod
    def section_2_3(cls):
        return _section(cls.text(), "### 2.3 ", "### 2.4 ")

    @classmethod
    def section_5_1(cls):
        return _section(cls.text(), "### 5.1 question packet", "### 5.2 answer")

    @classmethod
    def section_5_2(cls):
        return _section(cls.text(), "### 5.2 answer", "### 5.3 worker")

    @classmethod
    def section_5_3(cls):
        return _section(
            cls.text(), "### 5.3 worker 共通エンベロープ", "### 5.4 各 worker の契約"
        )

    @classmethod
    def section_5_5(cls):
        return _section(cls.text(), "### 5.5 workflow patch", "### 5.6 phase-state")

    @classmethod
    def section_5_6(cls):
        return _section(cls.text(), "### 5.6 phase-state", "#### 5.6.1")

    @classmethod
    def status_values(cls):
        rows = re.findall(r"^\|\s*`([a-z_]+)`\s*\|", cls.section_5_3(), re.MULTILINE)
        seen = []
        for value in rows:
            if value not in seen:
                seen.append(value)
        return seen

    @classmethod
    def category_vocabulary(cls):
        match = re.search(r"`category`\s*の語彙:(.+)", cls.section_5_1())
        assert match, "expected the category vocabulary line in design-input.md 5.1"
        tokens = _backtick_tokens(match.group(1))
        assert tokens, "expected backtick-wrapped category tokens"
        return tokens

    @classmethod
    def envelope_input_fields(cls):
        blocks = _yaml_blocks(cls.section_5_3())
        assert len(blocks) >= 1, "expected an input envelope yaml block in 5.3"
        return set(_mapping_keys(blocks[0]))

    @classmethod
    def envelope_output_fields(cls):
        blocks = _yaml_blocks(cls.section_5_3())
        assert len(blocks) >= 2, "expected an output envelope yaml block in 5.3"
        return set(_mapping_keys(blocks[1]))

    @classmethod
    def applicability_rows(cls):
        table = cls.section_2_3()
        applies, does_not_apply = [], []
        for left, right in re.findall(
            r"^\|([^|\n]*)\|([^|\n]*)\|$", table, re.MULTILINE
        ):
            left, right = left.strip(), right.strip()
            if set(left + right) <= {"-"}:
                continue  # separator row
            if left in ("適用する", "適用しない"):
                continue  # header row
            applies.extend(cls._split_names(left))
            does_not_apply.extend(cls._split_names(right))
        assert applies and does_not_apply, "expected non-empty applicability columns"
        return applies, does_not_apply

    @staticmethod
    def _split_names(cell):
        cell = re.sub(r"[（(].*?[）)]", "", cell).strip()
        if not cell:
            return []
        return [part.strip() for part in cell.split("/") if part.strip()]

    @classmethod
    def source_vocabulary(cls):
        match = re.search(r"^source:\s*\S+\s*#\s*(.+)$", cls.section_5_2(), re.MULTILINE)
        assert match, "expected the answer `source` vocabulary comment in 5.2"
        tokens = [token.strip() for token in match.group(1).split("|")]
        assert tokens, "expected non-empty source vocabulary"
        return tokens

    @classmethod
    def consistency_rule_count(cls):
        rule_lines = re.findall(r"^\d+\. ", cls.section_5_2(), re.MULTILINE)
        assert rule_lines, "expected a numbered consistency-rule list in 5.2"
        return len(rule_lines)

    @classmethod
    def workflow_patch_owned_tokens(cls):
        """Distinctive identifiers owned by workflow-patch.md (task0002),
        confirmed present in design-input.md 5.5 so this list cannot go
        stale relative to the design."""
        candidates = {
            "patch_id",
            "base_input_digest",
            "base_workflow_blob",
            "tasks_patch",
            "requirements_patch",
            "step_patches",
            "expected_next_task_id",
            "replace_planning",
            "append_rework",
        }
        section = cls.section_5_5()
        confirmed = {token for token in candidates if token in section}
        assert confirmed == candidates, (
            "workflow-patch tokens drifted from design-input.md 5.5: "
            f"missing {candidates - confirmed}"
        )
        return confirmed

    @classmethod
    def phase_state_owned_tokens(cls):
        """Distinctive identifiers owned by phase-state.md (task0003),
        confirmed present in design-input.md 5.6."""
        candidates = {
            "active_request_id",
            "worker_runs",
            "progress_fingerprint",
            "stale_redispatch_count",
            "resolved_input_cache",
            "generation_digest",
            "resolved_at_generation",
        }
        section = cls.section_5_6()
        confirmed = {token for token in candidates if token in section}
        assert confirmed == candidates, (
            "phase-state tokens drifted from design-input.md 5.6: "
            f"missing {candidates - confirmed}"
        )
        return confirmed


class TestDesignInputFixturesSelfCheck(unittest.TestCase):
    """Proves the parsing helpers above actually derive non-trivial values
    from design-input.md, rather than vacuously returning empty results."""

    def test_status_values_parses_all_six(self):
        self.assertEqual(
            DesignInputFixtures.status_values(),
            [
                "needs_user_input",
                "completed",
                "blocked",
                "invalid_input",
                "stale_input",
                "failed",
            ],
        )

    def test_category_vocabulary_parses_nineteen_values(self):
        categories = DesignInputFixtures.category_vocabulary()
        self.assertEqual(len(categories), 19)
        self.assertIn("tbd-resolution", categories)
        self.assertIn("other", categories)

    def test_envelope_input_fields_include_known_keys(self):
        fields = DesignInputFixtures.envelope_input_fields()
        self.assertIn("request_id", fields)
        self.assertIn("resolved_input_paths", fields)
        self.assertIn("e2e", fields)

    def test_envelope_output_fields_include_known_keys(self):
        fields = DesignInputFixtures.envelope_output_fields()
        self.assertIn("status", fields)
        self.assertIn("mode_echo", fields)
        self.assertIn("written_artifacts", fields)

    def test_applicability_rows_split_multi_name_cells(self):
        applies, does_not_apply = DesignInputFixtures.applicability_rows()
        self.assertEqual(
            applies,
            [
                "requirements-analyst",
                "spec-writer",
                "rework-planner",
                "implementation-planner",
                "designer",
            ],
        )
        self.assertIn("reviewer", does_not_apply)
        self.assertIn("codex-reviewer", does_not_apply)
        self.assertIn("gitignore-guard", does_not_apply)
        self.assertIn("git-setup-guard", does_not_apply)

    def test_source_vocabulary_parses_four_values(self):
        self.assertEqual(
            DesignInputFixtures.source_vocabulary(),
            [
                "user",
                "batch-decision-table",
                "batch-codex-consultation",
                "batch-safe-default",
            ],
        )

    def test_consistency_rule_count_is_seven(self):
        self.assertEqual(DesignInputFixtures.consistency_rule_count(), 7)


class TestExactTokenHelperSelfCheck(unittest.TestCase):
    """Edge case (task0001.md Test Notes): a field present in the document
    but spelled differently, or only present as a substring of prose, must
    not satisfy the exact-token check."""

    def test_rejects_substring_of_a_longer_identifier(self):
        text = "the `resolved_input_paths_extra` field is unrelated"
        self.assertFalse(_has_exact_token(text, "resolved_input_paths"))

    def test_rejects_prose_without_backticks(self):
        text = "the resolved_input_paths field is mentioned only in prose"
        self.assertFalse(_has_exact_token(text, "resolved_input_paths"))

    def test_accepts_exact_backtick_token(self):
        text = "see `resolved_input_paths` for details"
        self.assertTrue(_has_exact_token(text, "resolved_input_paths"))


class TestWorkerEnvelopeDocExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(
            ENVELOPE_DOC_PATH.is_file(),
            f"expected {ENVELOPE_DOC_PATH} to exist (AC-1)",
        )


class TestWorkerEnvelopeApplicability(unittest.TestCase):
    """AC-1: applicability table from design-input.md 2.3."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)

    def test_documents_every_applicable_worker(self):
        applies, _ = DesignInputFixtures.applicability_rows()
        for worker in applies:
            self.assertTrue(
                _has_exact_token(self.text, worker),
                f"worker-envelope.md must list applicable worker {worker!r}",
            )

    def test_documents_every_non_applicable_worker(self):
        _, does_not_apply = DesignInputFixtures.applicability_rows()
        for worker in does_not_apply:
            self.assertTrue(
                _has_exact_token(self.text, worker),
                f"worker-envelope.md must list non-applicable worker {worker!r}",
            )


class TestWorkerEnvelopeFields(unittest.TestCase):
    """AC-1: every input field and every output field from design-input.md
    5.3 must appear in the document as an exact token."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)

    def test_documents_every_input_field(self):
        for field in sorted(DesignInputFixtures.envelope_input_fields()):
            self.assertTrue(
                _has_exact_token(self.text, field),
                f"worker-envelope.md must document input field {field!r}",
            )

    def test_documents_every_output_field(self):
        for field in sorted(DesignInputFixtures.envelope_output_fields()):
            self.assertTrue(
                _has_exact_token(self.text, field),
                f"worker-envelope.md must document output field {field!r}",
            )


class TestWorkerEnvelopeStatusValues(unittest.TestCase):
    """AC-2: all six `status` values, each with mandatory/forbidden fields."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)

    def test_defines_all_six_status_values(self):
        for status in DesignInputFixtures.status_values():
            self.assertTrue(
                _has_exact_token(self.text, status),
                f"worker-envelope.md must define status value {status!r}",
            )

    def test_documents_mandatory_and_forbidden_columns(self):
        self.assertIn("Mandatory", self.text)
        self.assertIn("Forbidden", self.text)

    def test_needs_user_input_requires_question_packet(self):
        # Sanity that the status/field vocabularies are actually cross-wired,
        # not just independently present anywhere in the document. Anchored
        # on the status table's own row (not the first incidental mention
        # of the word elsewhere in the document).
        idx = self.text.index("| `needs_user_input`")
        window = self.text[idx : idx + 400]
        self.assertIn("question_packet", window)

    def test_completed_requires_payload(self):
        idx = self.text.index("| `completed`")
        window = self.text[idx : idx + 400]
        self.assertIn("payload", window)


class TestWorkerEnvelopeRules(unittest.TestCase):
    """AC-3: mode_echo rule, written_artifacts digest rule, read-restriction
    rule."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)

    def test_states_mode_echo_rule(self):
        self.assertTrue(_has_exact_token(self.text, "mode_echo"))
        self.assertIn("analysis_mode", self.text)
        self.assertIn("null", self.text)

    def test_states_written_artifacts_digest_rule(self):
        self.assertTrue(_has_exact_token(self.text, "written_artifacts"))
        self.assertIn("sha256", self.text)

    def test_states_read_restriction_rule(self):
        self.assertTrue(_has_exact_token(self.text, "resolved_input_paths"))
        lowered = self.text.lower()
        self.assertIn("never", lowered)
        self.assertIn("discovery", lowered)

    def test_states_exclusivity_assumption_and_its_interval(self):
        # design-input.md 5.11.3: the exclusivity assumption for the
        # integration worktree during dispatch, and the interval it applies
        # to (task0001.md Design section). Whitespace is normalized before
        # the phrase check since Markdown hard-wraps prose across lines.
        self.assertIn("5.11.3", self.text)
        normalized = re.sub(r"\s+", " ", self.text.lower())
        self.assertIn("scope snapshot", normalized)
        self.assertIn("verification", normalized)


class TestQuestionPacketDocExists(unittest.TestCase):
    def test_file_exists(self):
        self.assertTrue(
            PACKET_DOC_PATH.is_file(),
            f"expected {PACKET_DOC_PATH} to exist (AC-4)",
        )


class TestQuestionPacketFields(unittest.TestCase):
    """AC-4: packet fields, identifier patterns, size limits, category
    vocabulary."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PACKET_DOC_PATH)

    def test_documents_identifier_patterns(self):
        self.assertIn(r"^[a-z][a-z0-9-]*-q[0-9]{4}$", self.text)
        self.assertIn(r"^[a-z][a-z0-9._-]*$", self.text)

    def test_documents_size_limits(self):
        self.assertIn("2000", self.text)  # summary character limit
        self.assertIn("32", self.text)  # max questions
        self.assertIn("12", self.text)  # header character limit

    def test_documents_every_category_value(self):
        for category in DesignInputFixtures.category_vocabulary():
            self.assertTrue(
                _has_exact_token(self.text, category),
                f"question-packet-schema.md must list category {category!r}",
            )

    def test_documents_per_question_fields(self):
        for field in (
            "gate_id",
            "priority",
            "blocking",
            "answer_mode",
            "options",
            "why_needed",
            "evidence",
            "depends_on",
            "supersedes",
            "on_unanswered",
        ):
            self.assertTrue(
                _has_exact_token(self.text, field),
                f"question-packet-schema.md must document question field {field!r}",
            )

    def test_states_packet_is_question_request_only(self):
        lowered = self.text.lower()
        self.assertIn("status", lowered)
        self.assertIn("does not", lowered)


class TestQuestionPacketAnswerRules(unittest.TestCase):
    """AC-5: answer object, `source` vocabulary, seven consistency rules
    (1-5 machine-verified)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PACKET_DOC_PATH)

    def test_documents_answer_object_fields(self):
        for field in (
            "question_id",
            "packet_id",
            "answered_at",
            "source",
            "answer_mode",
            "selected_option_ids",
            "freeform",
            "normalized_answer",
            "resolution_note",
        ):
            self.assertTrue(
                _has_exact_token(self.text, field),
                f"question-packet-schema.md must document answer field {field!r}",
            )

    def test_documents_source_vocabulary(self):
        for source in DesignInputFixtures.source_vocabulary():
            self.assertTrue(
                _has_exact_token(self.text, source),
                f"question-packet-schema.md must list source value {source!r}",
            )

    def test_documents_all_seven_consistency_rules(self):
        rule_count = DesignInputFixtures.consistency_rule_count()
        found = len(re.findall(r"^\d+\. ", self.text, re.MULTILINE))
        self.assertGreaterEqual(
            found,
            rule_count,
            f"expected at least {rule_count} numbered consistency rules",
        )

    def test_marks_rules_one_through_five_as_machine_verified(self):
        self.assertRegex(self.text, r"[Rr]ules?\s*1\s*[-–]\s*5")
        self.assertIn("machine-verified", self.text.lower())

    def test_options_map_onto_ask_user_question(self):
        self.assertIn("AskUserQuestion", self.text)
        self.assertTrue(_has_exact_token(self.text, "header"))


class TestQuestionPacketOnUnanswered(unittest.TestCase):
    """AC-6: no `on_unanswered` value converts an unanswered question into
    an assumption."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PACKET_DOC_PATH)

    def test_states_no_on_unanswered_value_converts_to_assumption(self):
        self.assertIn(
            "No `on_unanswered` value converts an unanswered question into "
            "an assumption",
            self.text,
        )


class TestNoRestatedSiblingSsotContent(unittest.TestCase):
    """AC-7: neither document restates a table or rule owned by another
    SSOT (design-input.md 10.5); cross-references are path references."""

    @classmethod
    def setUpClass(cls):
        cls.envelope_text = _read(ENVELOPE_DOC_PATH)
        cls.packet_text = _read(PACKET_DOC_PATH)

    def test_neither_doc_restates_workflow_patch_internals(self):
        banned = DesignInputFixtures.workflow_patch_owned_tokens()
        for token in banned:
            self.assertNotIn(
                token,
                self.envelope_text,
                f"worker-envelope.md must not restate workflow-patch token {token!r}",
            )
            self.assertNotIn(
                token,
                self.packet_text,
                f"question-packet-schema.md must not restate workflow-patch token {token!r}",
            )

    def test_neither_doc_restates_phase_state_internals(self):
        banned = DesignInputFixtures.phase_state_owned_tokens()
        for token in banned:
            self.assertNotIn(
                token,
                self.envelope_text,
                f"worker-envelope.md must not restate phase-state token {token!r}",
            )
            self.assertNotIn(
                token,
                self.packet_text,
                f"question-packet-schema.md must not restate phase-state token {token!r}",
            )

    def test_neither_doc_restates_write_policy_internal_actions(self):
        # write_policy's six actions / expect_digest requirement are owned
        # by design-input.md 5.4.2 and the per-worker contracts, not by the
        # common envelope or the packet schema.
        for token in ("expect_digest",):
            self.assertNotIn(token, self.envelope_text)
            self.assertNotIn(token, self.packet_text)

    def test_neither_doc_has_a_workflow_patch_application_rules_heading(self):
        # design-input.md 5.5.5's application-rule list is owned by
        # references/workflow-patch.md (task0002); a heading restating that
        # list's title in either of this task's documents is a defect.
        for text in (self.envelope_text, self.packet_text):
            headings = [
                heading.lower()
                for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)
            ]
            self.assertFalse(
                any("application rule" in heading for heading in headings),
                "must not duplicate workflow-patch.md's application-rule heading",
            )


if __name__ == "__main__":
    unittest.main()
