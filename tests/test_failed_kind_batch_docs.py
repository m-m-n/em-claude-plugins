"""Tests for task0004 (implement-failed-kind): batch-mode.md and
batch-terminal-line.md follow the `failed_kind` branch without adding a
stop reason code and without restating the field's definition.

Covers task0004 Acceptance Criteria
(feature-docs/implement-failed-kind/tasks/task0004.md):

- AC-1 (FR10): the `implement.failed-task` row states that the second
  failure's abort write also carries the decision-required `failed_kind`
  value, and keeps its existing pointer to `references/implement-phase.md`
  Step I.2.c as the rule's owner.
- AC-2 (FR10): the failure-stops bullet no longer asserts unconditionally
  that every failure stops the run; it names the bounded, counted
  auto-resume as the exception and cites `skills/develop/SKILL.md` for the
  branch and the cap.
- AC-3 (FR10): the `step_needs_intervention` Meaning cell states that an
  `implement` `failed` counts only when `failed_kind` reads the
  decision-required value, and cites `references/workflow-schema.md` for
  the missing-value case rather than restating the rule.
- AC-4 (FR10): the precedence paragraph's restriction sentence covers both
  restrictions on `stop-condition-3`'s meaning -- the existing
  phase-specific-row one and the new `failed_kind` one.
- AC-5 (regression): the stop reason code table still contains exactly
  eleven codes, with the same names and the same `state` column values;
  the coverage table still maps `stop-condition-3` to
  `step_needs_intervention` with the develop skill as its source; and the
  precedence rule still names the same three phase-specific stop points.
  A negative proof shows each matcher fires against a synthetic copy with
  a code added, a code removed, or a mapping changed.
- AC-6 (NFR1): neither document enumerates the `failed_kind` values as a
  permitted set, glosses their meanings, or restates the missing-value
  read rule; both cite the owning document by repository-relative path
  where the field is used. A negative proof shows the detector fires
  against a synthetic restating copy.
- AC-7 (NFR4): `python3 -m unittest discover -s tests` passes with the new
  module present, and the new module imports only the standard library.

Neither this task nor its test module restates the `failed_kind`
vocabulary's meanings or the missing-value read rule -- both live in
`em-workflow/references/workflow-schema.md` (task0001), cited here by path
only.
"""

import ast
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BATCH_MODE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "batch-mode.md"
)
TERMINAL_LINE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "batch-terminal-line.md"
)

SCHEMA_CITATION = "references/workflow-schema.md"

# The closed two-value vocabulary this feature adds (task0001 owns its
# definition). Used here only to detect whether a consumer document names
# BOTH values together (the forbidden "permitted set" shape) -- never to
# assert what either value means.
VOCAB_VALUES = ["infra", "decision"]

# Phrases that would only appear if a consumer restated the vocabulary's
# meanings instead of citing them (D7 "forbidden": glossing the values).
GLOSS_PHRASES = [
    "infrastructure-caused failure",
    "decision-caused failure",
    "external-cause value",
    "implementation-failure value",
]

# Phrases that would only appear if a consumer restated the missing-value
# read rule instead of citing it (D7 "forbidden").
MISSING_VALUE_RESTATEMENT_RE = re.compile(
    r"(absent|missing|unset)[^.]{0,80}reads as `decision`"
    r"|reads as `decision`[^.]{0,80}(absent|missing|unset)",
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _table_row(text, anchor):
    """Locate a table row by its anchor (leading cell text) rather than by
    row index -- row order is not a contract for a single-row lookup."""
    idx = text.index(anchor)
    end = text.index("\n", idx)
    return text[idx:end]


def _parse_pipe_rows(section_text):
    rows = []
    for line in section_text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        inner = line[1:-1]
        cells = [c.strip() for c in inner.split("|")]
        if all(set(c) <= {"-"} for c in cells if c):
            continue  # header separator row
        rows.append(cells)
    return rows


def _reason_code_state_pairs(text):
    section = _section(text, "## Stop reason codes", "## Stop point coverage")
    rows = _parse_pipe_rows(section)
    data_rows = [r for r in rows if re.match(r"^`[a-z_]+`$", r[0])]
    return [(r[0].strip("`"), r[-1].strip("`")) for r in data_rows]


def backtick_quoted_vocab_terms_present(text):
    """Return the subset of VOCAB_VALUES that occur backtick-quoted (e.g.
    `` `infra` ``) in `text` -- the shape a restated vocabulary bullet list
    or "permitted set" enumeration would use, as distinct from the single,
    legitimate branch-condition/write-statement mention AC-1 and AC-3
    require."""
    return [v for v in VOCAB_VALUES if f"`{v}`" in text]


def gloss_phrases_present(text):
    return [p for p in GLOSS_PHRASES if p in text]


def missing_value_restatement_present(text):
    return bool(MISSING_VALUE_RESTATEMENT_RE.search(text))


# Reconstructed pre-task text, used only for AC-2's non-vacuity guard: the
# unconditional phrasing this task must remove, as it read before the
# edit.
ORIGINAL_FAILURE_STOPS_BULLET = (
    "- Failure stops are UNCHANGED: batch mode removes confirmations on the "
    "success path, it never hides failures. Stuck steps, YAML errors, and "
    "post-cap failures still stop the run with a report — the external "
    "service reads that report and cuts a follow-up task."
)

UNCONDITIONAL_GONE_MARKER = "it never hides failures"

EXPECTED_REASON_CODE_STATE_PAIRS = [
    ("step_stuck", "stopped"),
    ("step_needs_intervention", "stopped"),
    ("workflow_yaml_unparseable", "stopped"),
    ("git_setup_aborted", "stopped"),
    ("gate_fail_closed", "stopped"),
    ("gate_option_unavailable", "stopped"),
    ("implement_task_failed", "stopped"),
    ("verify_rework_cap_reached", "stopped"),
    ("completion_aborted", "stopped"),
    ("feature_resolution_aborted", "stopped"),
    ("docs_commit_conflict_aborted", "stopped"),
]

EXPECTED_COVERAGE_ROW = (
    "| `stop-condition-3` | `step_needs_intervention` | `skills/develop/SKILL.md` |"
)


class BatchModeDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)


class TerminalLineDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(TERMINAL_LINE_PATH)


# --- AC-1: implement.failed-task row carries failed_kind ------------------


class TestImplementFailedTaskRowCarriesFailedKind(BatchModeDocTestCase):
    def _row(self):
        return _table_row(self.text, "| `implement.failed-task`")

    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(BATCH_MODE_PATH))

    def test_row_states_the_same_write_also_sets_failed_kind(self):
        row = self._row()
        self.assertIn("`failed_kind`", row)
        self.assertIn("also sets `failed_kind`", row)

    def test_row_names_the_decision_value(self):
        row = self._row()
        self.assertIn("to `decision`", row)

    def test_row_cites_the_schema_document(self):
        row = self._row()
        self.assertIn(SCHEMA_CITATION, row)

    def test_row_keeps_existing_full_detail_pointer(self):
        row = self._row()
        self.assertIn(
            "Full detail: `references/implement-phase.md` Step I.2.c", row
        )

    def test_row_does_not_name_the_infra_value(self):
        # The row is a summary of one write path (D2: batch second-failure
        # is unconditionally `decision`) -- it must not restate the other
        # write paths' classification, which would require naming `infra`.
        row = self._row()
        self.assertNotIn("`infra`", row)


# --- AC-2: failure-stops bullet narrowed, auto-resume named as exception --


class TestFailureStopsBulletNarrowed(BatchModeDocTestCase):
    def _bullet(self):
        return _section(self.text, "- Failure stops are", "\n\n## Non-packet gates")

    def test_names_the_bounded_counted_exception(self):
        bullet = _norm(self._bullet())
        self.assertIn("infra auto-resume", bullet)
        self.assertIn("bounded", bullet)
        self.assertIn("counted", bullet)

    def test_cites_develop_skill_for_branch_and_cap(self):
        bullet = self._bullet()
        self.assertIn("skills/develop/SKILL.md", bullet)

    def test_unconditional_phrasing_is_gone(self):
        bullet = self._bullet()
        self.assertNotIn(UNCONDITIONAL_GONE_MARKER, bullet)

    def test_non_vacuity_gone_matcher_fires_on_original_bullet(self):
        # Proves the assertion above is not vacuous: the "gone" marker DOES
        # match the pre-task bullet text.
        self.assertIn(UNCONDITIONAL_GONE_MARKER, ORIGINAL_FAILURE_STOPS_BULLET)

    def test_still_names_stuck_steps_yaml_errors_and_post_cap_failures(self):
        # Regression: the still-true part of the original claim survives.
        bullet = _norm(self._bullet())
        self.assertIn("Stuck steps, YAML errors, and post-cap failures", bullet)
        self.assertIn("still stop the run with a report", bullet)


# --- AC-3: step_needs_intervention Meaning cell narrowed -------------------


class TestStepNeedsInterventionMeaningNarrowed(TerminalLineDocTestCase):
    def _row(self):
        return _table_row(self.text, "| `step_needs_intervention` |")

    def test_doc_exists(self):
        self.assertTrue(os.path.isfile(TERMINAL_LINE_PATH))

    def test_row_restricts_implement_failed_to_decision(self):
        row = self._row()
        self.assertIn("for the `implement` step", row)
        self.assertIn("`failed_kind` reads `decision`", row)

    def test_row_cites_schema_for_missing_value_case_without_restating(self):
        row = self._row()
        self.assertIn("missing-value case", row)
        self.assertIn(SCHEMA_CITATION, row)
        # Forbidden: stating the outcome of the missing-value rule itself
        # rather than pointing at its owning document.
        self.assertNotRegex(row, MISSING_VALUE_RESTATEMENT_RE)

    def test_row_code_and_state_columns_unchanged(self):
        row = self._row()
        self.assertTrue(row.startswith("| `step_needs_intervention` |"))
        self.assertTrue(row.rstrip().endswith("| `stopped` |"))

    def test_row_does_not_name_the_infra_value(self):
        row = self._row()
        self.assertNotIn("`infra`", row)


# --- AC-4: precedence paragraph states both restrictions coherently -------


class TestPrecedenceParagraphStatesBothRestrictions(TerminalLineDocTestCase):
    def _paragraph(self):
        return _section(
            self.text, "Precedence rule:", "\n\n## No line on a wait turn"
        )

    def test_states_the_phase_specific_row_restriction(self):
        paragraph = _norm(self._paragraph())
        self.assertIn(
            "restricted to `failed` / `needs_update` states that no "
            "phase-specific row covers",
            paragraph,
        )

    def test_states_the_failed_kind_restriction_for_implement(self):
        paragraph = _norm(self._paragraph())
        self.assertIn("`implement` step's", paragraph)
        self.assertIn("`failed_kind` reads `decision`", paragraph)

    def test_both_restrictions_are_one_coherent_statement(self):
        # Both restrictions live in the same sentence/paragraph rather than
        # being scattered -- checked by requiring the failed_kind
        # restriction to appear after, and joined to, the phase-specific
        # one within the same paragraph text.
        paragraph = _norm(self._paragraph())
        phase_specific_idx = paragraph.index(
            "restricted to `failed` / `needs_update` states that no "
            "phase-specific row covers"
        )
        failed_kind_idx = paragraph.index("`failed_kind` reads `decision`")
        self.assertLess(phase_specific_idx, failed_kind_idx)

    def test_three_phase_specific_stop_points_unchanged(self):
        paragraph = self._paragraph()
        for point in (
            "`implement-second-failure`",
            "`verify-rework-cap`",
            "`docs-commit-conflict`",
        ):
            self.assertIn(point, paragraph)


# --- AC-5: regression backbone ---------------------------------------------


class TestStopReasonCodeTableUnchangedExceptMeaning(TerminalLineDocTestCase):
    def test_exactly_eleven_codes_same_names_and_states_in_order(self):
        self.assertEqual(
            _reason_code_state_pairs(self.text), EXPECTED_REASON_CODE_STATE_PAIRS
        )

    def test_negative_proof_added_code_is_detected(self):
        section = _section(self.text, "## Stop reason codes", "## Stop point coverage")
        synthetic = self.text.replace(
            section, section + "| `extra_code` | Something new | `stopped` |\n"
        )
        self.assertNotEqual(
            _reason_code_state_pairs(synthetic), EXPECTED_REASON_CODE_STATE_PAIRS
        )

    def test_negative_proof_removed_code_is_detected(self):
        removed_row = (
            "| `docs_commit_conflict_aborted` | A phase aborted after a "
            "second consecutive `commit-docs.sh` exit 4 | `stopped` |\n"
        )
        self.assertIn(removed_row, self.text)
        synthetic = self.text.replace(removed_row, "")
        self.assertNotEqual(
            _reason_code_state_pairs(synthetic), EXPECTED_REASON_CODE_STATE_PAIRS
        )


class TestCoverageTableMappingUnchanged(TerminalLineDocTestCase):
    def test_stop_condition_3_maps_to_step_needs_intervention_via_develop_skill(
        self,
    ):
        section = _section(self.text, "## Stop point coverage", "Precedence rule:")
        row = _table_row(section, "| `stop-condition-3` |")
        self.assertEqual(row, EXPECTED_COVERAGE_ROW)

    def test_negative_proof_changed_mapping_is_detected(self):
        altered_row = (
            "| `stop-condition-3` | `step_stuck` | `skills/develop/SKILL.md` |"
        )
        self.assertIn(EXPECTED_COVERAGE_ROW, self.text)
        synthetic = self.text.replace(EXPECTED_COVERAGE_ROW, altered_row)
        section = _section(
            synthetic, "## Stop point coverage", "Precedence rule:"
        )
        row = _table_row(section, "| `stop-condition-3` |")
        self.assertNotEqual(row, EXPECTED_COVERAGE_ROW)


# --- AC-6: no restated vocabulary, gloss, or missing-value rule -----------


class TestNoRestatedVocabularyOrGloss(unittest.TestCase):
    def test_batch_mode_never_names_both_values_together(self):
        text = _read(BATCH_MODE_PATH)
        found = backtick_quoted_vocab_terms_present(text)
        self.assertNotIn("infra", found)

    def test_terminal_line_never_names_both_values_together(self):
        text = _read(TERMINAL_LINE_PATH)
        found = backtick_quoted_vocab_terms_present(text)
        self.assertNotIn("infra", found)

    def test_batch_mode_has_no_gloss_phrases(self):
        text = _read(BATCH_MODE_PATH)
        self.assertEqual(gloss_phrases_present(text), [])

    def test_terminal_line_has_no_gloss_phrases(self):
        text = _read(TERMINAL_LINE_PATH)
        self.assertEqual(gloss_phrases_present(text), [])

    def test_batch_mode_does_not_restate_missing_value_rule(self):
        text = _read(BATCH_MODE_PATH)
        self.assertFalse(missing_value_restatement_present(text))

    def test_terminal_line_does_not_restate_missing_value_rule(self):
        text = _read(TERMINAL_LINE_PATH)
        self.assertFalse(missing_value_restatement_present(text))

    def test_batch_mode_cites_the_owning_document(self):
        text = _read(BATCH_MODE_PATH)
        self.assertIn(SCHEMA_CITATION, text)

    def test_terminal_line_cites_the_owning_document(self):
        text = _read(TERMINAL_LINE_PATH)
        self.assertIn(SCHEMA_CITATION, text)

    def test_negative_proof_both_values_together_is_detected(self):
        synthetic = "The field is one of `infra` or `decision`.\n"
        self.assertEqual(
            backtick_quoted_vocab_terms_present(synthetic), ["infra", "decision"]
        )

    def test_negative_proof_gloss_phrase_is_detected(self):
        synthetic = (
            "`infra` means an infrastructure-caused failure and `decision` "
            "means a decision-caused failure.\n"
        )
        self.assertEqual(
            sorted(gloss_phrases_present(synthetic)),
            sorted(["infrastructure-caused failure", "decision-caused failure"]),
        )

    def test_negative_proof_missing_value_restatement_is_detected(self):
        synthetic = "An absent value reads as `decision` in every case.\n"
        self.assertTrue(missing_value_restatement_present(synthetic))

    def test_negative_proof_tolerates_single_value_mentions(self):
        # Non-vacuity companion: a lone, legitimate branch-condition/write
        # mention (as AC-1 and AC-3 require) must NOT be flagged.
        synthetic = "This path writes `decision` unconditionally.\n"
        found = backtick_quoted_vocab_terms_present(synthetic)
        self.assertNotIn("infra", found)
        self.assertEqual(gloss_phrases_present(synthetic), [])
        self.assertFalse(missing_value_restatement_present(synthetic))


# --- Out-of-scope guard: closed set size and out-of-scope files untouched -


class TestOutOfScopeUntouched(unittest.TestCase):
    def test_batch_policies_file_has_no_failed_kind_mention(self):
        path = os.path.join(
            REPO_ROOT, "em-workflow", "references", "batch-policies.yaml"
        )
        text = _read(path)
        self.assertNotIn("failed_kind", text)


# --- task0007 (round-1 rework, D11): the `batch.infra_resume` record's ----
# key set, materialising writer and cap ownership --------------------------
#
# Covers task0007 Acceptance Criteria
# (feature-docs/implement-failed-kind/tasks/task0007.md):
#
# - AC-1 (FR7): the batch-mode `batch` block snippet's key set equals the
#   schema's `batch` block snippet's key set -- derived from both
#   documents by parsing each snippet, never from a literal list held in
#   this test.
# - AC-2 (FR7): the sentence describing what the `batch` block persists
#   covers the auto-resume record as well as the rework counters, and its
#   "never activates the mode" clause is unchanged.
# - AC-3 (FR7, NFR1): the cap citation names the schema document for the
#   key, the member names and the unset-read defaults, and the develop
#   skill for the consuming judgment; no sentence attributes the cap's
#   definition wholly to the develop skill.

SCHEMA_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "workflow-schema.md"
)


def _strip_yaml_comment(line):
    idx = line.find("#")
    return line if idx == -1 else line[:idx]


def _yaml_mapping_keys(block_text):
    """Return the set of mapping keys appearing anywhere in `block_text`,
    ignoring comments and indentation -- a structural parse of the fenced
    snippet, not a hard-coded expectation."""
    keys = set()
    for raw_line in block_text.splitlines():
        line = _strip_yaml_comment(raw_line).strip()
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", line)
        if match:
            keys.add(match.group(1))
    return keys


def _batch_mode_snippet():
    text = _read(BATCH_MODE_PATH)
    fence_start = text.index("```yaml\nbatch:")
    fence_end = text.index("```", fence_start + len("```yaml"))
    return text[fence_start:fence_end]


def _schema_batch_snippet():
    # Mirrors test_failed_kind_schema.py's _full_structure_block() /
    # _batch_mapping(): `batch:` is the last top-level mapping in the
    # schema's "## Full structure" yaml fence, so its own text runs to the
    # fence's end.
    text = _read(SCHEMA_PATH)
    fence_start = text.index("```yaml", text.index("## Full structure"))
    fence_end = text.index("```", fence_start + len("```yaml"))
    full_structure = text[fence_start:fence_end]
    start = full_structure.index("\nbatch:")
    return full_structure[start:]


class TestBatchBlockSnippetKeySetEquivalence(unittest.TestCase):
    def test_batch_mode_snippet_key_set_equals_schema_snippet_key_set(self):
        batch_mode_keys = _yaml_mapping_keys(_batch_mode_snippet())
        schema_keys = _yaml_mapping_keys(_schema_batch_snippet())
        self.assertEqual(batch_mode_keys, schema_keys)

    def test_batch_mode_snippet_contains_infra_resume_record(self):
        keys = _yaml_mapping_keys(_batch_mode_snippet())
        self.assertIn("infra_resume", keys)
        self.assertIn("rounds", keys)
        self.assertIn("cap", keys)

    def test_non_vacuity_the_two_snippets_are_not_trivially_empty(self):
        # Guards the equality check above against passing vacuously
        # because both sides parsed to an empty set.
        self.assertTrue(_yaml_mapping_keys(_batch_mode_snippet()))
        self.assertTrue(_yaml_mapping_keys(_schema_batch_snippet()))

    def test_negative_proof_a_dropped_member_key_is_detected(self):
        schema_keys = _yaml_mapping_keys(_schema_batch_snippet())
        reduced = schema_keys - {"cap"}
        batch_mode_keys = _yaml_mapping_keys(_batch_mode_snippet())
        self.assertNotEqual(batch_mode_keys, reduced)


class TestBatchBlockPersistsSentenceCoversAutoResume(unittest.TestCase):
    def _bullet(self):
        text = _read(BATCH_MODE_PATH)
        return _section(text, "- Active ONLY when", "\n- In batch mode")

    def test_states_the_block_persists_the_auto_resume_record_too(self):
        bullet = _norm(self._bullet())
        self.assertIn("infra auto-resume record", bullet)
        self.assertIn("rework counters", bullet)

    def test_never_activates_the_mode_clause_is_unchanged(self):
        bullet = _norm(self._bullet())
        self.assertIn("it never activates the mode", bullet)

    def test_no_longer_claims_rework_counters_only(self):
        bullet = _norm(self._bullet())
        self.assertNotIn("rework counters ONLY", bullet)

    def test_negative_proof_only_marker_would_have_matched_pre_task_text(self):
        # Found-input guard for the assertNotIn above: proves the marker
        # actually matches the pre-task wording, so its absence now is
        # meaningful rather than the matcher being unable to fire at all.
        original = (
            "The `batch` block in workflow.yaml persists rework counters "
            "ONLY — it never activates the mode."
        )
        self.assertIn("rework counters ONLY", original)


class TestCapOwnershipCitationNamesEachOwner(unittest.TestCase):
    def _cap_sentence(self):
        text = _read(BATCH_MODE_PATH)
        return _section(
            text,
            "The one exception is the `implement` step's",
            "\n\n## Non-packet gates",
        )

    def test_cites_develop_skill_for_the_branch_and_consuming_judgment(self):
        sentence = _norm(self._cap_sentence())
        self.assertIn(
            "The branch and the cap's consuming judgment are "
            "`skills/develop/SKILL.md`'s to define",
            sentence,
        )

    def test_cites_schema_for_the_key_member_names_and_defaults(self):
        sentence = _norm(self._cap_sentence())
        self.assertIn(
            "the cap's key, its member names and its unset-read defaults "
            "are",
            sentence,
        )
        self.assertIn(SCHEMA_CITATION, sentence)

    def test_no_sentence_in_the_document_attributes_cap_wholly_to_develop_skill(
        self,
    ):
        text = _norm(_read(BATCH_MODE_PATH))
        self.assertNotIn(
            "the cap are `skills/develop/SKILL.md`'s to define", text
        )

    def test_negative_proof_pre_task_wording_would_have_matched_the_forbidden_pattern(
        self,
    ):
        # Found-input guard: the pre-task sentence attributed the cap
        # wholly to the develop skill in exactly this shape.
        original = (
            "The branch and the cap are `skills/develop/SKILL.md`'s to "
            "define, not this document's to restate."
        )
        self.assertIn(
            "the cap are `skills/develop/SKILL.md`'s to define", original
        )


# --- AC-7: this module imports only the standard library -------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        source = _read(os.path.abspath(__file__))
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
