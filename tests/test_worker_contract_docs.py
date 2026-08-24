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
REWORK_PLANNER_CONTRACT_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "contracts" / "rework-planner-contract.md"
)


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

    @classmethod
    def section_r1(cls):
        return _section(cls.text(), "#### 規則 R1", "#### 規則 R2")

    @classmethod
    def section_validation_layers(cls):
        return _section(cls.text(), "#### 5.11.2", "#### 5.11.3")

    @classmethod
    def digest_source_structural_keys(cls):
        """The `digest_source` object's structural field names
        (design-input.md 5.0 R1), confirmed present in the design text so
        this list cannot drift from it. Excludes `value_inputs`'s
        worker-specific example keys (`task_description` /
        `resolved_requirements` / `rework_source`), which are illustrative
        content, not structure owned by the common envelope."""
        candidates = {
            "digest_source",
            "worker",
            "mode",
            "workflow_blob",
            "digest_inputs",
            "value_inputs",
            "answers_digest",
            "write_policy_digest",
        }
        section = cls.section_r1()
        confirmed = {token for token in candidates if token in section}
        assert confirmed == candidates, (
            "digest_source structural keys drifted from design-input.md "
            f"5.0 R1: missing {candidates - confirmed}"
        )
        return confirmed

    @classmethod
    def digest_normalization_separator_literal(cls):
        match = re.search(r"区切りを\s*`([^`]+)`", cls.section_r1())
        assert match, (
            "expected the normalization separator literal in design-input.md "
            "5.0 R1"
        )
        return match.group(1)

    @classmethod
    def validation_layer_owner_kind(cls):
        """{layer_number: 'script'|'orchestrator'}, derived from
        design-input.md 5.11.2's table so worker-envelope.md's rendering
        cannot silently drift from the design."""
        section = cls.section_validation_layers()
        rows = re.findall(r"^\|\s*(\d+)\s*\|(.+?)\|(.+?)\|\s*$", section, re.MULTILINE)
        assert len(rows) == 7, f"expected seven validation layer rows, got {len(rows)}"
        result = {}
        for num, _name, owner in rows:
            owner = owner.strip()
            if "スクリプト" in owner:
                result[int(num)] = "script"
            elif "オーケストレーター" in owner:
                result[int(num)] = "orchestrator"
            else:
                raise AssertionError(f"unrecognized owner cell: {owner!r}")
        return result

    # Closed vocabulary translating design-input.md 5.3's Japanese-listed
    # forbidden-field terms into the English field tokens the shipped
    # documents use.
    _FORBIDDEN_JP_TERM_MAP = {
        "成果物": "written_artifacts",
        "patch": "workflow_patch",
        "blocking_reason": "blocking_reason",
        "question_packet": "question_packet",
    }

    @classmethod
    def status_forbidden_terms(cls):
        """{status: frozenset(english forbidden tokens)}, derived from
        design-input.md 5.3's own `status` の値と制約 table by translating
        each row's explicit "X・Y・Z は禁止" clause through
        `_FORBIDDEN_JP_TERM_MAP`. A row that never uses 禁止 (invalid_input,
        stale_input, failed) yields an empty set -- design is silent there,
        it does not assert an empty prohibition."""
        text = cls.text()
        header_idx = text.index("| status | 意味 | 制約 |")
        table_text = text[header_idx:]
        lines = table_text.splitlines()
        result = {}
        for line in lines[1:]:
            if not line.startswith("|"):
                break
            if "---" in line:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            status = cells[0].strip("`")
            constraint = cells[2] if len(cells) > 2 else ""
            match = re.search(r"([^。]+)は禁止", constraint)
            if not match:
                result[status] = frozenset()
                continue
            terms = [t.strip().strip("`") for t in match.group(1).split("・")]
            result[status] = frozenset(
                cls._FORBIDDEN_JP_TERM_MAP[t]
                for t in terms
                if t in cls._FORBIDDEN_JP_TERM_MAP
            )
        return result


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

    def test_digest_source_structural_keys_parses_eight_keys(self):
        keys = DesignInputFixtures.digest_source_structural_keys()
        self.assertEqual(
            keys,
            {
                "digest_source",
                "worker",
                "mode",
                "workflow_blob",
                "digest_inputs",
                "value_inputs",
                "answers_digest",
                "write_policy_digest",
            },
        )

    def test_digest_normalization_separator_literal_parses(self):
        self.assertEqual(
            DesignInputFixtures.digest_normalization_separator_literal(),
            '(",", ":")',
        )

    def test_validation_layer_owner_kind_parses_seven_layers(self):
        owners = DesignInputFixtures.validation_layer_owner_kind()
        self.assertEqual(len(owners), 7)
        self.assertEqual(owners[1], "script")
        self.assertEqual(owners[4], "orchestrator")
        self.assertEqual(owners[7], "orchestrator")
        self.assertEqual(
            {v for v in owners.values()}, {"script", "orchestrator"}
        )

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

    def test_status_forbidden_terms_parses_needs_user_input_row(self):
        # task0024 AC-1/AC-2: design-input.md 5.3's needs_user_input row
        # explicitly forbids written_artifacts/workflow_patch/blocking_reason
        # and says nothing about payload -- this is the design fact the
        # payload-prohibition correction rests on.
        terms = DesignInputFixtures.status_forbidden_terms()
        self.assertEqual(
            terms["needs_user_input"],
            {"written_artifacts", "workflow_patch", "blocking_reason"},
        )
        self.assertNotIn("payload", terms["needs_user_input"])
        self.assertEqual(terms["completed"], {"question_packet"})
        self.assertEqual(terms["blocked"], {"question_packet"})
        # design's wording for these three rows never uses 禁止 at all --
        # its silence is not evidence of an empty prohibition, only that
        # design does not encode one explicitly here.
        self.assertEqual(terms["invalid_input"], frozenset())
        self.assertEqual(terms["stale_input"], frozenset())
        self.assertEqual(terms["failed"], frozenset())


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


def _rendered_status_forbidden_terms(text):
    r"""{status: frozenset(backtick tokens)}, parsed from worker-envelope.md's
    own rendered `## \`status\` values and field constraints` table."""
    section = _section(
        text,
        "## `status` values and field constraints",
        "Re-dispatch behavior",
    )
    rows = re.findall(
        r"^\|\s*`([a-z_]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$",
        section,
        re.MULTILINE,
    )
    assert rows, "expected to find the rendered status table rows"
    return {status: frozenset(_backtick_tokens(forbidden)) for status, _meaning, _mandatory, forbidden in rows}


class TestWorkerEnvelopeStatusTablePayloadCorrection(unittest.TestCase):
    """task0024 AC-1/AC-2 (bs1/bs3 half): the status table no longer
    forbids a payload on `needs_user_input`, while every other non-completed
    status keeps forbidding it."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)
        cls.rendered = _rendered_status_forbidden_terms(cls.text)

    # AC-1
    def test_needs_user_input_forbidden_set_matches_design_exactly(self):
        # design-input.md 5.3 fully and explicitly enumerates this row's
        # forbidden set (成果物・patch・blocking_reason は禁止) and says
        # nothing about payload -- an exact match is the correct assertion,
        # not a subset check.
        design_expected = DesignInputFixtures.status_forbidden_terms()[
            "needs_user_input"
        ]
        self.assertEqual(self.rendered["needs_user_input"], design_expected)

    def test_needs_user_input_no_longer_forbids_payload(self):
        self.assertNotIn("payload", self.rendered["needs_user_input"])

    def test_needs_user_input_still_forbids_artifacts_patch_and_blocking_reason(self):
        for token in ("written_artifacts", "workflow_patch", "blocking_reason"):
            self.assertIn(token, self.rendered["needs_user_input"])

    # AC-2
    def test_other_non_completed_statuses_still_forbid_payload(self):
        other_statuses = [
            status
            for status in DesignInputFixtures.status_values()
            if status not in ("needs_user_input", "completed")
        ]
        # sanity: this must be the known three-status set, not vacuous
        self.assertEqual(
            set(other_statuses), {"blocked", "invalid_input", "stale_input", "failed"}
        )
        for status in other_statuses:
            self.assertIn(
                "payload",
                self.rendered[status],
                f"{status!r} must still forbid payload (AC-2)",
            )

    def test_completed_status_unchanged(self):
        self.assertEqual(self.rendered["completed"], {"question_packet"})


class TestWorkerEnvelopePriorAnalysisField(unittest.TestCase):
    """task0024 AC-3/AC-4 (bs5): the envelope defines `prior_analysis` with
    `content` and `input_digest`, and states its size bound; the analyst's
    contract states the reuse rule on top of it."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)

    def test_documents_prior_analysis_with_both_members(self):
        self.assertTrue(_has_exact_token(self.text, "prior_analysis"))
        idx = self.text.index("### `prior_analysis`")
        section = self.text[idx : idx + 2000]
        self.assertIn("content", section)
        self.assertIn("input_digest", section)

    def test_states_a_numeric_size_bound(self):
        idx = self.text.index("### `prior_analysis`")
        section = self.text[idx : idx + 2000]
        lowered = section.lower()
        self.assertIn("size bound", lowered)
        self.assertRegex(section, r"\d+\s*KB")

    def test_states_requirements_analyst_only(self):
        idx = self.text.index("### `prior_analysis`")
        section = self.text[idx : idx + 2000]
        self.assertIn("requirements-analyst", section)
        self.assertIn("only", section)

    def test_analyst_contract_states_reuse_on_matching_digest(self):
        analyst_text = _read(
            REPO_ROOT
            / "em-workflow"
            / "references"
            / "contracts"
            / "analyst-contract.md"
        )
        self.assertIn("prior_analysis", analyst_text)
        lowered = analyst_text.lower()
        self.assertIn("continue from", lowered)
        self.assertIn("re-investigate", lowered)
        self.assertIn("input_digest", analyst_text)


class TestWorkerEnvelopeUntrustedInputSection(unittest.TestCase):
    """task0024 AC-5/AC-6 (bs12): the envelope has an untrusted-input
    section covering the data-not-instructions rule, the refusal to take
    role/shape/gate/category direction from content, and the reporting
    duty; every worker prompt references it and none restates it."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)
        idx = cls.text.index("## Untrusted-Input Handling")
        cls.section = cls.text[idx:]

    def test_has_the_section(self):
        self.assertIn("## Untrusted-Input Handling", self.text)

    def test_states_data_not_instructions_rule(self):
        lowered = self.section.lower()
        self.assertIn("untrusted", lowered)
        self.assertIn("data to analyse", lowered)
        self.assertIn("never commands to follow", lowered)

    def test_states_refusal_of_role_shape_gate_and_category_direction(self):
        self.assertIn("role", self.section.lower())
        self.assertIn("output shape", self.section)
        self.assertIn("gate_id", self.section)
        self.assertIn("category", self.section)
        self.assertIn("never obeyed", self.section)

    def test_states_reporting_duty(self):
        self.assertIn("injection", self.section.lower())
        self.assertIn("`report`", self.section)

    AGENT_PATHS = (
        REPO_ROOT / "em-workflow" / "agents" / "requirements-analyst.md",
        REPO_ROOT / "em-workflow" / "agents" / "spec-writer.md",
        REPO_ROOT / "em-workflow" / "agents" / "rework-planner.md",
        REPO_ROOT / "em-workflow" / "agents" / "designer.md",
        REPO_ROOT / "em-workflow" / "agents" / "implementation-planner.md",
    )

    # Sentences distinctive to the envelope's own rendering of the rule;
    # a worker prompt containing any of these would be restating the
    # section rather than referencing it (NFR6).
    DISTINCTIVE_ENVELOPE_SENTENCES = (
        "untrusted attacker-influenceable data",
        "ignore previous instructions",
        "reports that as a fact in its result",
    )

    def test_every_worker_prompt_references_the_section(self):
        for path in self.AGENT_PATHS:
            text = _read(path)
            normalized = re.sub(r"\s+", " ", text)
            self.assertIn(
                "Untrusted-Input Handling",
                normalized,
                f"{path.name} must reference the Untrusted-Input Handling section",
            )
            self.assertIn(
                "references/contracts/worker-envelope.md",
                text,
                f"{path.name} must reference worker-envelope.md by path",
            )

    def test_no_worker_prompt_restates_the_section(self):
        for path in self.AGENT_PATHS:
            text = _read(path)
            normalized = re.sub(r"\s+", " ", text)
            for sentence in self.DISTINCTIVE_ENVELOPE_SENTENCES:
                self.assertNotIn(
                    sentence,
                    normalized,
                    f"{path.name} must not restate the envelope's untrusted-input "
                    f"wording ({sentence!r})",
                )


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


class TestWorkerEnvelopeDigestRuleIsShipped(unittest.TestCase):
    """task0019 AC-1: the envelope contract states rule R1's normalization
    procedure and the `digest_source` structure in full, without requiring
    the reader to open design-input.md."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)

    def test_states_every_digest_source_structural_key(self):
        for key in sorted(DesignInputFixtures.digest_source_structural_keys()):
            self.assertTrue(
                _has_exact_token(self.text, key),
                f"worker-envelope.md must state digest_source key {key!r}",
            )

    def test_states_the_normalization_separator_literal(self):
        literal = DesignInputFixtures.digest_normalization_separator_literal()
        self.assertIn(
            literal,
            self.text,
            "worker-envelope.md must state the exact JSON separator literal "
            "from design-input.md 5.0 R1",
        )

    def test_states_sort_ascending_non_ascii_and_sha256(self):
        lowered = self.text.lower()
        self.assertIn("ascending", lowered)
        self.assertIn("sha256", lowered)
        self.assertIn("non-ascii", lowered)

    def test_states_recomputation_and_comparison_timing(self):
        # The staleness guarantee depends on dispatch-time and return-time
        # computation using the identical procedure; this must be stated,
        # not left implicit.
        normalized = re.sub(r"\s+", " ", self.text.lower())
        self.assertIn("before dispatch", normalized)
        self.assertIn("recomputes", normalized)
        self.assertIn("stale", normalized)

    def test_input_digest_field_row_points_inside_this_document(self):
        # task0019 AC-3: the input_revision.input_digest row must resolve
        # within this document (a self-contained "below"), not only to
        # design-input.md.
        idx = self.text.index("`input_revision`.`input_digest`")
        window = self.text[idx : idx + 200]
        self.assertIn("below", window)
        self.assertIn("## Rule R1", self.text)


class TestWorkerEnvelopeValidationLayers(unittest.TestCase):
    """task0019 AC-2: the envelope contract states which validation layers
    belong to the script and which to the orchestrator."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_DOC_PATH)

    def test_has_a_validation_layers_section(self):
        self.assertIn("## Validation layers", self.text)

    def test_layer_owner_split_matches_design(self):
        expected = DesignInputFixtures.validation_layer_owner_kind()
        section = _section(self.text, "## Validation layers", "## Output fields")
        rows = re.findall(
            r"^\|\s*(\d+)\s*\|(.+?)\|(.+?)\|\s*$", section, re.MULTILINE
        )
        self.assertEqual(len(rows), 7, "expected seven rendered validation layer rows")
        actual = {}
        for num, _name, owner in rows:
            owner = owner.strip()
            if "Script" in owner:
                actual[int(num)] = "script"
            elif "Orchestrator" in owner:
                actual[int(num)] = "orchestrator"
            else:
                self.fail(f"unrecognized owner cell in worker-envelope.md: {owner!r}")
        self.assertEqual(expected, actual)


class TestNoDesignDocRequiredForNormativeContent(unittest.TestCase):
    """task0019 AC-3 (scoped to this task's shipped files): no in-scope
    contract document instructs the reader to open design-input.md to
    resolve a rule; design-document mentions are citations alongside
    content stated in the shipped file itself, never the sole destination."""

    IN_SCOPE_FILES = (
        ENVELOPE_DOC_PATH,
        PACKET_DOC_PATH,
        REPO_ROOT / "em-workflow" / "references" / "contracts" / "analyst-contract.md",
        REPO_ROOT / "em-workflow" / "references" / "contracts" / "designer-contract.md",
    )

    BANNED_PATTERNS = (
        re.compile(r"see design-input\.md.*for (the|its) (rule|procedure)", re.IGNORECASE),
        re.compile(r"read design-input\.md", re.IGNORECASE),
        re.compile(r"consult design-input\.md", re.IGNORECASE),
    )

    def test_no_file_instructs_reading_design_doc_to_resolve_a_rule(self):
        for path in self.IN_SCOPE_FILES:
            text = _read(path)
            for pattern in self.BANNED_PATTERNS:
                self.assertIsNone(
                    pattern.search(text),
                    f"{path.name} must not instruct the reader to open "
                    "design-input.md to resolve a rule",
                )


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


class TestQuestionPacketEvidenceFindingStableIdField(unittest.TestCase):
    """task0019 AC-7 (round2 findings 87ae09bcfe6410c0, 61c73dc71f323f45,
    cbb5659c4025c46e): `questions[].evidence[]` gains `finding_stable_id` in
    the packet schema's field table -- the structured field the
    Classification gate's origin verification requires
    (tests/test_classification_gate.py)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PACKET_DOC_PATH)

    def _evidence_row(self, field):
        marker = f"`questions[].evidence[]`.`{field}`"
        self.assertIn(marker, self.text, f"expected the {field!r} field row")
        idx = self.text.index(marker)
        row_end = self.text.index("\n", idx)
        return self.text[idx:row_end]

    def test_field_table_has_existing_evidence_rows(self):
        # Non-vacuity guard (Test Notes): the table itself must be found
        # before the new row's presence means anything.
        self._evidence_row("path")
        self._evidence_row("line")
        self._evidence_row("detail")

    def test_finding_stable_id_field_present(self):
        row = self._evidence_row("finding_stable_id")
        self.assertIn("stable_id", row.lower())

    def test_finding_stable_id_negative_proof_missing_field_is_detected(self):
        fake_text = (
            "| `questions[].evidence[]`.`path` | Evidence file path |\n"
            "| `questions[].evidence[]`.`line` | Evidence line number |\n"
            "| `questions[].evidence[]`.`detail` | Evidence detail text |\n"
        )
        self.assertNotIn(
            "`questions[].evidence[]`.`finding_stable_id`", fake_text
        )


class TestQuestionPacketGateIdOwnership(unittest.TestCase):
    """task0019 AC-5: the `gate_id` ownership statement names files that
    actually hold gate identifiers. `references/question-resolution.md`
    holds none (it is the resolution procedure, not an identifier
    registry) and must not be named as an owner of the ID set."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PACKET_DOC_PATH)

    def _gate_id_row(self):
        idx = self.text.index("`questions[]`.`gate_id`")
        row_end = self.text.index("\n", idx)
        return self.text[idx:row_end]

    def test_does_not_name_question_resolution_as_an_id_owner(self):
        self.assertNotIn("question-resolution.md", self._gate_id_row())

    def test_names_batch_policies_as_the_batch_handling_owner(self):
        self.assertIn("batch-policies.yaml", self._gate_id_row())

    def test_names_worker_contracts_as_where_identifiers_originate(self):
        row = self._gate_id_row()
        self.assertIn("contract", row.lower())


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


class TestReworkPlannerContractSpecChangeCitation(unittest.TestCase):
    """task0012 AC-5 (NFR1): rework-planner-contract.md states batch
    resolution of `rework.spec-change` only by citing question-resolution.md's
    classification gate -- the superseded fail-closed-abort claim is absent
    -- and states the packet's origin-naming obligation that the gate's
    origin verification (tests/test_classification_gate.py) depends on."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REWORK_PLANNER_CONTRACT_PATH)

    def _transition_section(self):
        return _section(
            self.text,
            "## Specification-change transition",
            "## Other conditions under which a question packet may be returned",
        )

    def test_batch_mode_cites_classification_gate_not_unlisted_fallback(self):
        section = re.sub(r"\s+", " ", self._transition_section())
        self.assertIn(
            "In batch mode, `rework.spec-change` is resolved through the "
            "classification gate defined in "
            "`references/question-resolution.md`",
            section,
        )
        self.assertIn("this document does not restate", section)

    def test_interactive_mode_stated_unchanged(self):
        section = re.sub(r"\s+", " ", self._transition_section())
        self.assertIn(
            "Interactive mode is unchanged: the user is asked directly",
            section,
        )

    def test_superseded_fail_closed_abort_claim_is_absent(self):
        # C5: the absence half. Non-vacuity: `_transition_section` above
        # already proved the section exists (it would have raised
        # otherwise); this checks it is also non-empty.
        section = self._transition_section()
        self.assertTrue(section.strip())
        self.assertNotIn("falls to the unlisted-gate fallback", section)
        self.assertNotIn("aborts rather than proceeding", section)

    def test_superseded_claim_negative_proof_would_be_caught(self):
        # Non-vacuity guard (Test Notes): the matcher above must actually
        # flag the pre-task0012 wording it supersedes, not merely pass by
        # vacuity against text that never contained it.
        fake_section = (
            "In batch mode, `rework.spec-change` has no defined policy in "
            "`batch-policies.yaml`, so it falls to the unlisted-gate "
            "fallback (5.9), which — because a specification change is "
            "one of the fail-closed categories — aborts rather than "
            "proceeding."
        )
        self.assertIn("falls to the unlisted-gate fallback", fake_section)
        self.assertIn("aborts rather than proceeding", fake_section)

    def test_states_packet_names_stable_id_via_finding_stable_id_field(self):
        # task0019 AC-8 (round2 findings 87ae09bcfe6410c0, 61c73dc71f323f45):
        # the packet names stable_ids through the structured
        # `evidence[].finding_stable_id` field, never the record path.
        section = re.sub(r"\s+", " ", self._transition_section())
        self.assertIn(
            "The question packet returned for `gate_id: rework.spec-change` "
            "names each originating review finding's `stable_id` in the "
            "question's `evidence[].finding_stable_id` entries",
            section,
        )
        self.assertIn(
            "the gate's origin verification "
            "(`references/question-resolution.md`) locates that record "
            "itself",
            section,
        )

    def test_states_packet_does_not_name_the_record_path(self):
        section = re.sub(r"\s+", " ", self._transition_section())
        self.assertIn(
            "does not name the review round record path", section
        )

    def test_old_packet_names_record_path_wording_is_gone(self):
        # Negative proof: the pre-task0019 wording let the packet name the
        # record path -- the worker-controlled channel the origin-
        # verification bypass used. It must not survive.
        section = self._transition_section()
        self.assertNotIn(
            "names each originating review finding's `stable_id` and the "
            "review round record path",
            section,
        )

    def test_old_wording_negative_proof_would_be_caught(self):
        fake_section = (
            "The question packet returned for `gate_id: rework.spec-change` "
            "names each originating review finding's `stable_id` and the "
            "review round record path in the question's `evidence[]` "
            "entries -- the gate's origin verification "
            "(`references/question-resolution.md`) reads them from there."
        )
        self.assertIn(
            "names each originating review finding's `stable_id` and the "
            "review round record path",
            fake_section,
        )

    def test_does_not_restate_the_r5_position_or_path_formula(self):
        # NFR1: the round-record location formula is owned by
        # references/review-phase.md's R5 section and cited from
        # question-resolution.md; this contract must not restate it.
        self.assertNotIn("Phase R5", self.text)
        self.assertNotIn("reviews/round", self.text)

    def test_packet_obligation_negative_proof_missing_obligation_fails_matcher(self):
        fake_section = (
            "In batch mode, `rework.spec-change` is resolved through the "
            "classification gate defined in "
            "`references/question-resolution.md`, which this document does "
            "not restate."
        )
        self.assertNotIn(
            "names each originating review finding's `stable_id`",
            fake_section,
        )

    def test_five_step_sequence_unaffected_by_the_citation_rewrite(self):
        # Retention: the five numbered orchestrator-follow-up steps this
        # task did not touch must still be exactly five, in order -- the
        # citation rewrite only replaces the trailing prose paragraph.
        section = self._transition_section()
        numbered = re.findall(r"^(\d+)\. ", section, re.MULTILINE)
        self.assertEqual(numbered, ["1", "2", "3", "4", "5"])


class TestReworkPlannerContractGateIdentifiers(unittest.TestCase):
    """task0024 AC-4 (FR11): rework-planner-contract.md carries a
    "## Gate identifiers" section naming `rework.spec-change` -- this is
    what attributes the gate to the `rework-planner` worker and puts it
    into the validator's gate registry (see
    tests/test_validate_worker_output.py's TestGateRegistryDerivation and
    tests/test_spec_change_gate_binding.py, which assert the registry
    entry the section produces, rather than asserting this sentence)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(REWORK_PLANNER_CONTRACT_PATH)

    def _gate_identifiers_section(self):
        return _section(
            self.text,
            "## Gate identifiers",
            "## Other conditions under which a question packet may be returned",
        )

    def test_section_exists_and_names_the_gate_id(self):
        section = self._gate_identifiers_section()
        self.assertIn("`rework.spec-change`", section)

    def test_section_states_no_batch_policies_entry(self):
        section = re.sub(r"\s+", " ", self._gate_identifiers_section())
        self.assertIn(
            "carries no entry in `references/batch-policies.yaml`", section
        )

    def test_section_cites_classification_gate_not_restated(self):
        section = re.sub(r"\s+", " ", self._gate_identifiers_section())
        self.assertIn(
            "the classification gate defined in "
            "`references/question-resolution.md`",
            section,
        )
        self.assertIn("cited, not restated", section)

    def test_section_states_the_registry_consequence(self):
        section = re.sub(r"\s+", " ", self._gate_identifiers_section())
        self.assertIn(
            "puts it into the validator's gate registry "
            "(`em-workflow/scripts/validate-worker-output.py`)",
            section,
        )
        self.assertIn("binding it to the `spec-change` category", section)

    def test_negative_twin_no_gate_identifiers_heading_fails(self):
        # Non-vacuity guard: text that names the gate_id in prose without
        # the "## Gate identifiers" heading (the pre-task0024 state -- the
        # heading and its parser attribution did not exist at all) must not
        # satisfy the section locator above.
        fake_text = (
            "## Specification-change transition\n\n"
            "The rework-planner raises `rework.spec-change` via the "
            "transition above.\n\n"
            "## Other conditions under which a question packet may be "
            "returned\n"
        )
        with self.assertRaises(ValueError):
            _section(
                fake_text,
                "## Gate identifiers",
                "## Other conditions under which a question packet may be returned",
            )


if __name__ == "__main__":
    unittest.main()
