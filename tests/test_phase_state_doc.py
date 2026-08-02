"""Tests for task0003: phase-state contract document
(em-workflow/references/phase-state.md).

Covers task0003 Acceptance Criteria
(feature-docs/agent-separation/tasks/task0003.md):

- AC-1: phase-state.md exists and documents every schema field in
  design-input.md 5.6 with its permitted values.
- AC-2: the document defines the permitted worker_runs[].status
  transitions with discarded_stale as terminal, and the active_request_id
  retention exception.
- AC-3: the document defines both exit-4 recovery procedures as distinct
  numbered sequences and states that the discarded_stale record must be
  committed before re-dispatch, with the staging reason.
- AC-4: the document states the consecutive artifact-commit retry limit of
  one with the counter's value at each point.
- AC-5: the document contains the resume decision table covering every
  top-level status, including the dispatching split on a discarded_stale
  active run.
- AC-6: the document contains the legacy-compatibility table, the
  project.design_system backfill procedure with its Step B placement and
  rationale, and the unknown-schema_version abort rule.
- AC-7: the document defines resolved_input_cache including
  generation_digest invalidation, the three re-resolution triggers, the
  reset conditions and the discovery caps with mode-specific handling.

This is a documentation task (Test Notes: "Verified structurally"), so
these are structural/textual checks over the reference markdown -- and, for
AC-1, a parse of design-input.md 5.6's own schema block, so the check stays
tied to the normative source rather than to hand-picked field names.
Follows the pattern established by
tests/test_review_implement_develop_lock_contracts.py (task0007) and
tests/test_planner_designer_worktree_docs.py (task0005).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
DESIGN_INPUT_PATH = REPO_ROOT / "feature-docs" / "agent-separation" / "design-input.md"

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMBERED_STEP_RE = re.compile(r"^(\d+)\.\s+(.*)$")


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def _extract_first_yaml_block(text):
    match = re.search(r"```yaml\n(.*?)\n```", text, re.DOTALL)
    if not match:
        raise AssertionError("expected a ```yaml fenced block in the given text")
    return match.group(1)


def _schema_keys(yaml_block):
    """YAML mapping keys (before ':') that look like identifiers -- i.e.
    schema field names, as opposed to example IDs/paths used as
    illustrative values (`create-plan-q0001:`,
    `requirement.fr4.tbd-resolution:`, `src/design-system/tokens.ts:` are
    excluded by the identifier shape: hyphens/dots/slashes don't match)."""
    keys = set()
    for line in yaml_block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        if ":" not in stripped:
            continue
        key = stripped.split(":", 1)[0].strip()
        if _IDENT_RE.match(key):
            keys.add(key)
    return keys


def _enum_tokens(yaml_block):
    """Pipe-separated identifier tokens found in inline `#` comments -- the
    enum lists such as `# initialized | dispatching | ...`."""
    tokens = set()
    for line in yaml_block.splitlines():
        if "#" not in line:
            continue
        comment = line.split("#", 1)[1]
        if "|" not in comment:
            continue
        for part in comment.split("|"):
            part = part.strip()
            if _IDENT_RE.match(part):
                tokens.add(part)
    return tokens


def _numbered_steps(text):
    """[(step_number:int, step_text:str), ...] for top-level `N. ...`
    markdown list items appearing in `text`, in document order."""
    steps = []
    for line in text.splitlines():
        match = _NUMBERED_STEP_RE.match(line.strip())
        if match:
            steps.append((int(match.group(1)), match.group(2)))
    return steps


class TestPhaseStateDocExistsAndRendersSchemaFaithfully(unittest.TestCase):
    """AC-1: phase-state.md exists and documents every schema field in
    design-input.md 5.6 with its permitted values."""

    @classmethod
    def setUpClass(cls):
        cls.design_text = _read(DESIGN_INPUT_PATH)
        section = _extract_section(cls.design_text, "### 5.6 phase-state", "#### 5.6.1")
        cls.yaml_block = _extract_first_yaml_block(section)

    def test_phase_state_doc_exists(self):
        self.assertTrue(
            PHASE_STATE_PATH.exists(), f"expected {PHASE_STATE_PATH} to exist"
        )

    def test_every_schema_key_from_design_input_5_6_appears(self):
        text = _read(PHASE_STATE_PATH)
        keys = _schema_keys(self.yaml_block)
        self.assertGreater(len(keys), 20, "sanity: parser found a plausible key set")
        missing = sorted(k for k in keys if k not in text)
        self.assertEqual(
            missing, [], f"schema keys from design-input.md 5.6 missing: {missing}"
        )

    def test_every_enum_token_from_design_input_5_6_appears(self):
        text = _read(PHASE_STATE_PATH)
        tokens = _enum_tokens(self.yaml_block)
        self.assertGreater(len(tokens), 10, "sanity: parser found a plausible enum set")
        missing = sorted(t for t in tokens if t not in text)
        self.assertEqual(
            missing, [], f"enum values from design-input.md 5.6 missing: {missing}"
        )


class TestValidationDetectsMissingSchemaCoverage(unittest.TestCase):
    """Proof the checks above fail meaningfully (tdd-testing discipline: a
    test that can never fail is not a test)."""

    def test_schema_key_parser_flags_a_missing_key(self):
        yaml_block = "foo_field: bar\nbaz_field: qux\n"
        keys = _schema_keys(yaml_block)
        self.assertEqual(keys, {"foo_field", "baz_field"})
        missing = sorted(k for k in keys if k not in "only baz_field is present here")
        self.assertEqual(missing, ["foo_field"])

    def test_schema_key_parser_excludes_example_ids_and_paths(self):
        yaml_block = (
            "packets:\n"
            "  create-plan-q0001:\n"
            "    status: answered\n"
            "digests:\n"
            "  src/design-system/tokens.ts: sha256:...\n"
        )
        keys = _schema_keys(yaml_block)
        self.assertNotIn("create-plan-q0001", keys)
        self.assertNotIn("src/design-system/tokens.ts", keys)
        self.assertIn("status", keys)
        self.assertIn("digests", keys)

    def test_enum_token_parser_flags_a_missing_token(self):
        yaml_block = "status: x  # alpha | beta | gamma\n"
        tokens = _enum_tokens(yaml_block)
        self.assertEqual(tokens, {"alpha", "beta", "gamma"})
        missing = sorted(t for t in tokens if t not in "only alpha and beta appear")
        self.assertEqual(missing, ["gamma"])


class TestWorkerRunStatusTransitions(unittest.TestCase):
    """AC-2: permitted worker_runs[].status transitions with
    discarded_stale as terminal, and the active_request_id retention
    exception."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)

    def test_transition_table_lists_worker_return_transitions(self):
        for status in (
            "needs_user_input",
            "completed",
            "blocked",
            "invalid_input",
            "stale_input",
            "failed",
        ):
            self.assertIn(status, self.text)
        self.assertIn("dispatched", self.text)

    def test_discarded_stale_is_stated_as_terminal(self):
        idx = self.text.index("### worker_runs[].status transitions")
        end = self.text.index("### active_request_id lifecycle")
        section = self.text[idx:end]
        self.assertIn("discarded_stale", section)
        self.assertIn("terminal", section.lower())

    def test_active_request_id_retention_exception_present(self):
        self.assertIn("active_request_id", self.text)
        idx = self.text.index("### active_request_id lifecycle")
        section = self.text[idx : idx + 1500]
        self.assertIn("discarded_stale", section)
        self.assertIn("keeps", section.lower())


class TestExit4RecoveryProcedures(unittest.TestCase):
    """AC-3: both exit-4 recovery procedures as distinct numbered
    sequences; the discarded_stale record must be committed before
    re-dispatch, with the staging reason stated."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)

    def test_both_recovery_procedures_present_as_distinct_sections(self):
        self.assertIn("### Phase-state exit-4 recovery", self.text)
        self.assertIn("### Artifact-commit exit-4 recovery", self.text)
        phase_idx = self.text.index("### Phase-state exit-4 recovery")
        artifact_idx = self.text.index("### Artifact-commit exit-4 recovery")
        self.assertLess(phase_idx, artifact_idx)

    def test_phase_state_recovery_is_a_numbered_sequence(self):
        idx = self.text.index("### Phase-state exit-4 recovery")
        end = self.text.index("### Artifact-commit exit-4 recovery")
        steps = _numbered_steps(self.text[idx:end])
        numbers = [n for n, _ in steps]
        self.assertGreaterEqual(len(numbers), 5, "expected a multi-step sequence")
        self.assertEqual(numbers, sorted(numbers))

    def test_artifact_commit_recovery_orders_record_before_redispatch(self):
        idx = self.text.index("### Artifact-commit exit-4 recovery")
        end = self.text.index("### Consecutive retry limit")
        section = self.text[idx:end]
        steps = _numbered_steps(section)
        self.assertGreaterEqual(len(steps), 5, "expected a multi-step sequence")

        record_step = next(
            (n for n, t in steps if "discarded_stale" in t and "stale_redispatch_count" in t),
            None,
        )
        redispatch_step = next(
            (n for n, t in steps if "re-dispatch" in t.lower() and "request_id" in t),
            None,
        )
        self.assertIsNotNone(record_step, "no step records discarded_stale + counter")
        self.assertIsNotNone(redispatch_step, "no step re-dispatches under a new request_id")
        self.assertLess(
            record_step,
            redispatch_step,
            "the discarded_stale record must be committed before re-dispatch",
        )

    def test_staging_reason_for_the_ordering_is_stated(self):
        idx = self.text.index("### Artifact-commit exit-4 recovery")
        end = self.text.index("### Consecutive retry limit")
        section = self.text[idx:end]
        self.assertIn("MUST NOT be reordered", section)
        self.assertIn("stages entire directories", section)


class TestConsecutiveRetryLimit(unittest.TestCase):
    """AC-4: the consecutive artifact-commit retry limit of one, with the
    counter's value at each point."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        idx = cls.text.index("### Consecutive retry limit")
        end = cls.text.index("## Resume decision table")
        cls.section = cls.text[idx:end]

    def test_states_the_cap_is_one_consecutive_occurrence(self):
        self.assertIn("one", self.section.lower())
        self.assertIn("stale_redispatch_count", self.section)

    def test_counter_value_at_each_point_is_stated(self):
        section = self.section
        self.assertIn("Phase start", section)
        self.assertIn("First exit 4", section)
        self.assertIn("Second exit 4", section)
        self.assertIn("After a successful artifact commit", section)
        # values 0 (start), 1 (first exit 4, persisted), failed (second
        # exit 4), 0 (after success) must all be present as table cells.
        self.assertIn("`0`", section)
        self.assertIn("`1`", section)
        self.assertIn("failed", section.lower())


class TestResumeDecisionTable(unittest.TestCase):
    """AC-5: resume decision table covering every top-level status,
    including the dispatching split on a discarded_stale active run."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        idx = cls.text.index("## Resume decision table")
        end = cls.text.index("## Size management")
        cls.section = cls.text[idx:end]

    def test_every_top_level_status_is_covered(self):
        section = self.section
        for status in (
            "initialized",
            "dispatching",
            "awaiting_answers",
            "applying_patch",
            "completed",
        ):
            self.assertIn(f"`{status}`", section, f"status {status!r} not covered")

    def test_dispatching_splits_on_discarded_stale_active_run(self):
        section = self.section
        self.assertIn("discarded_stale", section)
        # two distinct `dispatching` rows: one naming discarded_stale, one not.
        dispatching_lines = [
            line for line in section.splitlines() if line.strip().startswith("| `dispatching`")
        ]
        self.assertGreaterEqual(len(dispatching_lines), 2)
        self.assertTrue(any("discarded_stale" in line for line in dispatching_lines))
        self.assertTrue(any("discarded_stale" not in line for line in dispatching_lines))

    def test_workflow_yaml_wins_when_ahead(self):
        self.assertIn("workflow.yaml", self.section)
        self.assertIn("wins", self.section.lower())


class TestLegacyCompatibility(unittest.TestCase):
    """AC-6: legacy-compatibility table, project.design_system backfill
    procedure with its Step B placement and rationale, and the
    unknown-schema_version abort rule."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        idx = cls.text.index("## Legacy feature compatibility")
        cls.section = cls.text[idx:]

    def test_legacy_compatibility_table_covers_upstream_states(self):
        section = self.section
        self.assertIn("create-spec", section)
        self.assertIn("create-plan", section)
        self.assertIn("completed", section)
        self.assertIn("in_progress", section)
        self.assertIn("pending", section)
        self.assertIn("preserve_and_reuse", section)

    def test_backfill_section_present_with_step_b_placement(self):
        self.assertIn("### project.design_system backfill", self.section)
        idx = self.section.index("### project.design_system backfill")
        backfill_section = self.section[idx:]
        self.assertIn("Step B", backfill_section)
        steps = _numbered_steps(backfill_section)
        numbers = [n for n, _ in steps if n <= 4]
        self.assertGreaterEqual(len(numbers), 4, "expected the 4-step Step B placement sequence")

    def test_backfill_placement_rationale_is_stated(self):
        idx = self.section.index("### project.design_system backfill")
        backfill_section = self.section[idx:]
        self.assertIn("Why not set", backfill_section)
        self.assertIn("in_progress", backfill_section)

    def test_backfill_interrupted_answer_loss_is_stated(self):
        idx = self.section.index("### project.design_system backfill")
        backfill_section = self.section[idx:]
        self.assertIn("Interrupted backfill", backfill_section)
        self.assertIn("lost", backfill_section.lower())

    def test_unknown_schema_version_abort_rule_is_stated(self):
        self.assertIn("schema_version", self.section)
        idx = self.section.index("Unknown `schema_version`")
        surrounding = self.section[idx : idx + 400]
        self.assertIn("abort", surrounding.lower())


class TestResolvedInputCache(unittest.TestCase):
    """AC-7: resolved_input_cache including generation_digest
    invalidation, the three re-resolution triggers, the reset conditions
    and the discovery caps with mode-specific handling."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        idx = cls.text.index("### resolved_input_cache")
        end = cls.text.index("## Update, commit, and exit-4 recovery")
        cls.section = cls.text[idx:end]

    def test_generation_digest_is_the_invalidation_signal_not_head(self):
        section = self.section
        self.assertIn("generation_digest", section)
        self.assertIn("HEAD", section)

    def test_three_re_resolution_triggers_present(self):
        section = self.section
        idx = section.index("Re-resolution triggers")
        triggers_section = section[idx : idx + 1200]
        steps = _numbered_steps(triggers_section)
        self.assertEqual(len(steps), 3, f"expected exactly 3 triggers, got {steps}")

    def test_reset_conditions_present(self):
        section = self.section
        self.assertIn("generation", section)
        self.assertIn("empty map", section.lower())
        self.assertIn("initialized", section)

    def test_discovery_caps_with_mode_specific_handling_present(self):
        section = self.section
        self.assertIn("500", section)
        self.assertIn("5 MB", section)
        self.assertIn("truncated", section)
        self.assertIn("interactive", section)
        self.assertIn("batch", section)
        interactive_idx = section.index("interactive")
        batch_idx = section.index("| batch")
        self.assertLess(interactive_idx, batch_idx)


if __name__ == "__main__":
    unittest.main()
