"""Tests for task0003 (review-sca-axis): axis 2's placement in
review-phase.md Phases R0-R3b.

Covers task0003 Acceptance Criteria
(feature-docs/review-sca-axis/tasks/task0003.md):

- AC-1: R0 carries a notion-task-dispatch availability probe step stating
  that the marketplace name is not hard-coded and that the newest version is
  chosen among several, and distinguishing itself from R0 step 1's
  fail-closed SSOT resolution. (TS-8)
- AC-2: R1's Mandatory Layer-2 check states that the dependency
  manifest / lockfile trigger adds `vulnerability` in addition to `license`,
  with the `license` behaviour unchanged. (TS-8)
- AC-3: R2 states that `vulnerability` runs as an orchestrator-executed
  script step (no Task dispatch, no model), names the scan invocation, and
  states that the reachability judgement belongs to the R3a evaluator.
  `reviewers.yaml` still holds exactly six perspectives and does not contain
  `vulnerability`. (TS-11, TS-8)
- AC-4: R2 / R2b state that a `source: tool` run is excluded from the
  registry chain walk, from the fallback determination and from the
  `unreviewed_perspectives` accounting. (TS-8)
- AC-5: the axis-2 run's `perspective_runs` row is documented with the run
  id, perspective, role, source and status values IMPLEMENTATION.md pins,
  and the path by which it reaches R3a's input, R3b step 3's category
  cross-check and the accountability floor is followable in the document.
  (TS-15)
- AC-6: `review-protocol.md` is byte-identical to its pre-change content in
  its Read-only Constraint section, and `batch-policies.yaml` plus
  `batch-mode.md`'s Non-packet gates table carry no new gate identifier.
  (TS-16, TS-17)
- AC-7: in this task's worktree, `python3 -m unittest discover -s tests`
  exits 0 and `python3 em-workflow/scripts/check-plugin-invariants.py
  <repo-root>` exits 0 -- verified by actually running both commands
  (recorded in the implementer report); a suite cannot assert its own
  full-suite outcome, following test_review_phase_llm_led.py's AC-7
  precedent.

This is a documentation task (task0003.md Test Notes): every criterion is a
document assertion. Sections are sliced on literal headings and phrases are
asserted within the sliced section (whitespace-normalized first, to survive
the document's ~79-column reflowing) so a statement landing in the wrong
phase fails. AC-6's invariance side additionally carries a negative case (a
forged sample) proving the comparison/extraction can actually fail, per
task0003.md Test Notes and the established pattern in
test_review_phase_llm_led.py's TestValidationDetectsRegressions.

`reviewers.yaml` is read with a hand-rolled restricted-subset parser local
to this module (repository convention: tests/test_batch_policies.py,
tests/test_reviewers_primary_chains.py). PyYAML is a runtime dependency of
the em-workflow plugin, never a test dependency (IMPLEMENTATION.md
Technology Stack) -- this module imports the standard library only.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ROOT = os.path.join(REPO_ROOT, "em-workflow")
REVIEW_PHASE_PATH = os.path.join(PLUGIN_ROOT, "references", "review-phase.md")
REVIEW_PROTOCOL_PATH = os.path.join(PLUGIN_ROOT, "references", "review-protocol.md")
REVIEWERS_PATH = os.path.join(PLUGIN_ROOT, "references", "reviewers.yaml")
BATCH_POLICIES_PATH = os.path.join(PLUGIN_ROOT, "references", "batch-policies.yaml")
BATCH_MODE_PATH = os.path.join(PLUGIN_ROOT, "references", "batch-mode.md")

R0_HEADING = "## Phase R0: Resolve SSOT & review target"
R1_HEADING = "## Phase R1: Perspective selection (two layers)"
R2_HEADING = "## Phase R2: Fan-out (ONE message, N Task calls)"
R2B_HEADING = "## Phase R2b: Cross-model fallback (chain walk)"
R3A_HEADING = "## Phase R3a: Evaluation (single Opus evaluator)"
R3B_HEADING = "## Phase R3b: Mechanical gates on the evaluation"
R4_HEADING = "## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)"

READ_ONLY_CONSTRAINT_HEADING = "## Read-only Constraint"
UNTRUSTED_INPUT_HEADING = "## Untrusted-Input Handling"

# Pinned verbatim from review-protocol.md's Read-only Constraint section, as
# it read BEFORE this task's change (this task never edits review-protocol.md
# -- NFR1 -- so this is also its expected content AFTER). Captured by direct
# inspection of the file at task start.
PINNED_READ_ONLY_CONSTRAINT = """## Read-only Constraint

- No `git commit`, `git checkout`, `git stash`, `git reset`, branch switches.
- No formatter / linter runs that modify files.
- No `Write` / `Edit` of project files.
- No network calls except the cross-model harness invocation (codex wrapper /
  `codex exec -p litellm`, each in its own reviewer only).
- Allowed read-only git: `git diff`, `git diff HEAD`, `git rev-parse`,
  `git status --porcelain`, `git log`."""

# Pinned gate-identifier sets, as of task start (this task never edits either
# file -- NFR5). batch-policies.yaml: every 2-space-indented `gate_id: ...`
# key directly under `gate_policies:`.
PINNED_BATCH_POLICIES_GATE_IDS = frozenset(
    {
        "create-spec.feature-identity",
        "create-spec.requirement-clarification",
        "create-spec.design-step",
        "create-spec.design-system",
        "design-system.reclassify",
        "create-spec.artifact-overwrite",
        "design.artifact-overwrite",
        "create-plan.artifact-overwrite",
        "create-spec.command-approval",
        "create-spec.stalled",
        "create-plan.tbd-resolution",
        "create-plan.license-conflict",
        "create-plan.existing-files",
    }
)

# batch-mode.md's Non-packet gates table: every row-leading backtick-quoted
# identifier.
PINNED_BATCH_MODE_NON_PACKET_GATE_IDS = frozenset(
    {
        "implement.failed-task",
        "review.auto-fix-conflict",
        "review.auto-fix-judgment",
        "review.residual-critical-high",
        "verify.failed",
        "develop.completion",
    }
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _slice(text, start_heading, end_heading=None):
    start = text.index(start_heading)
    if end_heading is None:
        return text[start:]
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _has_exact_token(text, token):
    """True iff `token` occurs as an exact inline-code span (backtick
    delimited) -- test_review_phase_llm_led.py precedent."""
    pattern = r"`" + re.escape(token) + r"`"
    return re.search(pattern, text) is not None


# ---------------------------------------------------------------------------
# reviewers.yaml: hand-rolled restricted-subset parser (perspective names
# only -- this module needs no chain detail).
# ---------------------------------------------------------------------------


def parse_reviewers_yaml_perspective_names(text):
    """Returns the ordered list of `perspective:` values directly under the
    top-level `perspectives:` block (2-space-indented `- perspective: NAME`
    list items). Raises ValueError if no such block is found."""
    lines = text.splitlines()
    names = []
    in_block = False
    saw_block = False
    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not in_block:
            if line == "perspectives:":
                in_block = True
                saw_block = True
            continue
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0:
            break
        if indent == 2:
            if not stripped.startswith("- perspective:"):
                raise ValueError(f"expected a perspective list item, got: {raw!r}")
            names.append(stripped[len("- perspective:"):].strip())
    if not saw_block:
        raise ValueError("no top-level `perspectives:` key found")
    return names


# ---------------------------------------------------------------------------
# batch-policies.yaml / batch-mode.md: gate-identifier extraction.
# ---------------------------------------------------------------------------

POLICY_KEY_RE = re.compile(r"^  ([a-z][a-zA-Z0-9.\-]*):\s*$", re.MULTILINE)
TABLE_ROW_GATE_RE = re.compile(r"^\|\s*`([a-z][a-zA-Z0-9.\-]*)`", re.MULTILINE)


def extract_batch_policies_gate_ids(text):
    return frozenset(POLICY_KEY_RE.findall(text))


def extract_batch_mode_non_packet_gate_ids(text):
    table = _slice(text, "## Non-packet gates")
    return frozenset(TABLE_ROW_GATE_RE.findall(table))


class DocumentFixture:
    """Reads review-phase.md once and slices out the sections this module
    needs (task0003 owns R0/R1/R2/R2b/R3a/R3b only)."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(REVIEW_PHASE_PATH)
        return cls._text

    @classmethod
    def r0(cls):
        return _slice(cls.text(), R0_HEADING, R1_HEADING)

    @classmethod
    def r1(cls):
        return _slice(cls.text(), R1_HEADING, R2_HEADING)

    @classmethod
    def r2(cls):
        return _slice(cls.text(), R2_HEADING, R2B_HEADING)

    @classmethod
    def r2b(cls):
        return _slice(cls.text(), R2B_HEADING, R3A_HEADING)

    @classmethod
    def r3a(cls):
        return _slice(cls.text(), R3A_HEADING, R3B_HEADING)

    @classmethod
    def r3b(cls):
        return _slice(cls.text(), R3B_HEADING, R4_HEADING)


# ---------------------------------------------------------------------------
# AC-1: R0 notion-task-dispatch probe.
# ---------------------------------------------------------------------------


class TestAC1R0NotionTaskDispatchProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r0 = DocumentFixture.r0()

    def test_probe_names_notion_task_dispatch(self):
        self.assertIn("notion-task-dispatch", self.r0)

    def test_probe_glob_path_present(self):
        self.assertIn(
            "$HOME/.claude/plugins/cache/*/notion-task-dispatch/*/scripts/ntd.sh",
            self.r0,
        )

    def test_marketplace_segment_not_hard_coded(self):
        norm = _norm(self.r0)
        self.assertIn("marketplace segment is never hard-coded", norm)

    def test_newest_version_picked_among_several(self):
        norm = _norm(self.r0)
        self.assertIn("newest", norm)
        self.assertIn("several plugin", norm)
        self.assertIn("versions are installed", norm)

    def test_distinguished_from_step_1_fail_closed_ssot_resolution(self):
        norm = _norm(self.r0)
        self.assertIn("Unlike step 1's fail-closed SSOT resolution", norm)

    def test_negative_result_is_ordinary_supported_state_not_abort(self):
        norm = _norm(self.r0)
        self.assertIn(
            "this is an availability probe: an unset `ntd_path` here is an "
            "ordinary, supported state, not an abort",
            norm,
        )

    def test_probe_result_is_input_to_filing_path_only(self):
        norm = _norm(self.r0)
        self.assertIn(
            "nothing here decides the filing branch by itself", norm
        )

    def test_probe_placed_after_probe_litellm_before_load_prior_rounds(self):
        idx_litellm = self.r0.index("Probe litellm")
        idx_ntd = self.r0.index("Probe notion-task-dispatch")
        idx_prior = self.r0.index("Load prior rounds")
        self.assertLess(idx_litellm, idx_ntd)
        self.assertLess(idx_ntd, idx_prior)


# ---------------------------------------------------------------------------
# AC-2: R1 Mandatory Layer-2 check rides `vulnerability` along `license`.
# ---------------------------------------------------------------------------


class TestAC2R1MandatoryLayerTwoAddsVulnerability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r1 = DocumentFixture.r1()

    def test_license_trigger_paragraph_still_present_unchanged(self):
        # Purely additive edit (IMPLEMENTATION.md Conventions): the
        # pre-existing license-trigger sentence must survive verbatim.
        self.assertIn(
            "ADD the `license` perspective. It is never in the floor\n"
            "(review-rules.yaml has no manifest signal), so this is the "
            "only path that\nselects it.",
            self.r1,
        )

    def test_same_trigger_adds_vulnerability(self):
        norm = _norm(self.r1)
        self.assertIn(
            "additionally ADDs the `vulnerability` perspective to the "
            "selected set",
            norm,
        )

    def test_vendored_source_clause_stays_license_only(self):
        norm = _norm(self.r1)
        self.assertIn(
            "not the vendored-third-party-source clause, which stays "
            "`license`-only",
            norm,
        )

    def test_license_behaviour_stated_unchanged(self):
        norm = _norm(self.r1)
        self.assertIn("The `license` behaviour above is\nunchanged".replace("\n", " "), norm)

    def test_vulnerability_never_in_mechanical_floor(self):
        norm = _norm(self.r1)
        self.assertIn(
            "`vulnerability` is never in the mechanical floor", norm
        )


# ---------------------------------------------------------------------------
# AC-3: R2 axis 2 as orchestrator-executed script step; reviewers.yaml pin.
# ---------------------------------------------------------------------------


class TestAC3R2Axis2ScriptStep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = DocumentFixture.r2()

    def test_axis_2_served_by_vulnerability_not_task_dispatch(self):
        norm = _norm(self.r2)
        self.assertIn(
            "`vulnerability`\nis served by axis 2, never by a "
            "Task-dispatched reviewer".replace("\n", " "),
            norm,
        )

    def test_orchestrator_itself_executes_scan_subcommand(self):
        self.assertIn("the orchestrator", self.r2)
        norm = _norm(self.r2)
        self.assertIn(
            "the orchestrator\nitself executes the `scan` subcommand of\n"
            "`em-workflow/scripts/scan-dependencies.py`".replace("\n", " "),
            norm,
        )

    def test_no_model_anywhere_on_its_path(self):
        norm = _norm(self.r2)
        self.assertIn("no model anywhere on its path", norm)

    def test_reachability_judgement_belongs_to_r3a_evaluator(self):
        norm = _norm(self.r2)
        self.assertIn(
            "belongs to\nthe R3a\nevaluator, not to axis 2".replace("\n", " "),
            norm,
        )

    def test_states_vulnerability_absent_from_reviewers_registry(self):
        norm = _norm(self.r2)
        self.assertIn(
            "`vulnerability` never appears among "
            "`references/reviewers.yaml`'s\nsix perspectives".replace("\n", " "),
            norm,
        )

    def test_threshold_lives_in_vuln_scanners_registry_not_restated(self):
        norm = _norm(self.r2)
        self.assertIn("`references/vuln-scanners.yaml`", norm)
        self.assertIn("not restated here as a protocol rule", norm)

    def test_reviewers_yaml_has_exactly_six_perspectives_and_no_vulnerability(self):
        text = _read(REVIEWERS_PATH)
        names = parse_reviewers_yaml_perspective_names(text)
        self.assertEqual(len(names), 6)
        self.assertNotIn("vulnerability", names)


# ---------------------------------------------------------------------------
# AC-4: R2 / R2b exclude `source: tool` from registry lookup, chain walk,
# fallback determination and `unreviewed_perspectives` accounting.
# ---------------------------------------------------------------------------


class TestAC4SourceToolExcludedFromChainWalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = DocumentFixture.r2()
        cls.r2b = DocumentFixture.r2b()

    def test_r2_states_source_tool_never_looked_up_in_registry(self):
        norm = _norm(self.r2)
        self.assertIn(
            "A `source: tool` run is never looked up in the registry",
            norm,
        )
        self.assertIn("never walks a `primary_chain`", norm)

    def test_r2b_states_no_fallback_hop_consumed(self):
        norm = _norm(self.r2b)
        self.assertIn(
            "never consumes one of this section's\nfallback hops".replace(
                "\n", " "
            ),
            norm,
        )

    def test_r2b_states_no_claude_fallback_dispatch_triggered(self):
        norm = _norm(self.r2b)
        self.assertIn("never triggers the Claude fallback dispatch", norm)

    def test_r2b_states_never_in_unreviewed_perspectives(self):
        norm = _norm(self.r2b)
        self.assertIn(
            "never appears in Phase R5's\n`unreviewed_perspectives` "
            "list".replace("\n", " "),
            norm,
        )

    def test_r2b_states_skip_not_a_retryable_chain_walk_candidate(self):
        norm = _norm(self.r2b)
        self.assertIn(
            "not a candidate for this section's\nretryable-`skip_reason` "
            "table".replace("\n", " "),
            norm,
        )


# ---------------------------------------------------------------------------
# AC-5: the axis-2 `perspective_runs` row, and its path to R3a / R3b.
# ---------------------------------------------------------------------------


class TestAC5Axis2RunIdentityAndDownstreamPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = DocumentFixture.r2()
        cls.r3a = DocumentFixture.r3a()
        cls.r3b = DocumentFixture.r3b()

    def test_run_identity_row_values_present_in_r2(self):
        for token in [
            'run_id: "vulnerability#tool"',
            "perspective: vulnerability",
            "role: tool",
            "source: tool",
        ]:
            self.assertIn(token, self.r2)

    def test_status_enumeration_present(self):
        norm = _norm(self.r2)
        self.assertIn("`status` one of `completed` / `skipped`", norm)
        self.assertIn("`skip_reason`", norm)
        self.assertIn("`failed`", norm)

    def test_skipped_axis_2_run_is_ordinary_recorded_skip(self):
        norm = _norm(self.r2)
        self.assertIn(
            "recorded exactly as this\nordinary skip".replace("\n", " "),
            norm,
        )
        self.assertIn(
            "never as a retryable chain-walk `skip_reason`", norm
        )

    def test_r3a_carries_axis_2_run_like_any_other(self):
        norm = _norm(self.r3a)
        self.assertIn(
            "Axis 2's run enters this input exactly like a "
            "Task-dispatched perspective's\nrun".replace("\n", " "),
            norm,
        )
        self.assertIn("`perspectives_dispatched`", norm)
        self.assertIn("`reviewer_outputs`", norm)

    def test_r3b_states_no_special_case_for_source_tool(self):
        norm = _norm(self.r3b)
        self.assertIn("Axis 2 interoperates unchanged", norm)
        self.assertIn(
            "Step 3's category cross-check\nresolves a `vulnerability` "
            "finding against axis 2's".replace("\n", " "),
            norm,
        )
        self.assertIn(
            "cannot be\nsilently suppressed by the evaluator".replace(
                "\n", " "
            ),
            norm,
        )
        self.assertIn(
            "No property, step or exception in\nthis phase treats "
            "`source: tool` differently".replace("\n", " "),
            norm,
        )


# ---------------------------------------------------------------------------
# AC-6: invariance -- review-protocol.md, batch-policies.yaml, batch-mode.md.
# ---------------------------------------------------------------------------


class TestAC6ReviewProtocolReadOnlyConstraintUnchanged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_PROTOCOL_PATH)
        cls.section = _slice(
            cls.text, READ_ONLY_CONSTRAINT_HEADING, UNTRUSTED_INPUT_HEADING
        ).rstrip()

    def test_section_matches_pinned_bytes_exactly(self):
        self.assertEqual(self.section, PINNED_READ_ONLY_CONSTRAINT)

    def test_negative_case_forged_section_does_not_match(self):
        forged = PINNED_READ_ONLY_CONSTRAINT + "\n- No exception for axis 2."
        self.assertNotEqual(forged, PINNED_READ_ONLY_CONSTRAINT)
        self.assertNotEqual(forged, self.section)


class TestAC6NoNewGateIdentifierIntroduced(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policies_text = _read(BATCH_POLICIES_PATH)
        cls.batch_mode_text = _read(BATCH_MODE_PATH)

    def test_batch_policies_gate_id_set_unchanged(self):
        self.assertEqual(
            extract_batch_policies_gate_ids(self.policies_text),
            PINNED_BATCH_POLICIES_GATE_IDS,
        )

    def test_batch_mode_non_packet_gate_id_set_unchanged(self):
        self.assertEqual(
            extract_batch_mode_non_packet_gate_ids(self.batch_mode_text),
            PINNED_BATCH_MODE_NON_PACKET_GATE_IDS,
        )

    def test_negative_case_extractor_flags_a_forged_extra_gate_id(self):
        forged = self.policies_text + "\n  review.vulnerability-axis:\n"
        forged_ids = extract_batch_policies_gate_ids(forged)
        self.assertNotEqual(forged_ids, PINNED_BATCH_POLICIES_GATE_IDS)
        self.assertIn("review.vulnerability-axis", forged_ids)

    def test_negative_case_table_extractor_flags_a_forged_extra_row(self):
        forged = self.batch_mode_text.replace(
            "## Non-packet gates",
            "## Non-packet gates\n\n| `review.vulnerability-axis` | x | y |",
            1,
        )
        forged_ids = extract_batch_mode_non_packet_gate_ids(forged)
        self.assertIn("review.vulnerability-axis", forged_ids)
        self.assertNotEqual(forged_ids, PINNED_BATCH_MODE_NON_PACKET_GATE_IDS)

    def test_no_gate_id_declaration_in_new_r0_through_r3b_text(self):
        # NFR5: no new gate identifier is introduced anywhere in this
        # task's own edits.
        new_path = "\n".join(
            [
                DocumentFixture.r0(),
                DocumentFixture.r1(),
                DocumentFixture.r2(),
                DocumentFixture.r2b(),
                DocumentFixture.r3a(),
                DocumentFixture.r3b(),
            ]
        )
        self.assertNotIn("gate_id:", new_path)
        self.assertNotIn("AskUserQuestion(", new_path)


# ---------------------------------------------------------------------------
# Own-module convention: standard-library-only imports (test/README.md,
# IMPLEMENTATION.md Technology Stack "Test dependency").
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import ast
        import sys
        from pathlib import Path

        source = Path(__file__).read_text(encoding="utf-8")
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
