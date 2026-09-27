"""Tests for task0003 (threat-model-stride): the planner contract, the
create-plan phase protocol's dispatch/scope-check wiring for THREAT-MODEL.md,
and the minimal-tier TASK.md append permission.

Covers task0003 Acceptance Criteria
(feature-docs/threat-model-stride/tasks/task0003.md):

- AC-1: planner-contract.md's `planning_inputs` section documents
  `threat_model_template`, states THREAT-MODEL.md is a write_policy target
  with the same action rule as IMPLEMENTATION.md, and its `digest_inputs`
  / `completed` payload sections list THREAT-MODEL.md.
- AC-2: planner-contract.md has a `###` subsection inside the
  `planning_inputs` section owning the minimal-tier TASK.md append rule in
  full (SC-3).
- AC-3: create-plan-phase.md's section 4 (dispatch), section 7 (completion
  output) and section 1 (purpose) all mention THREAT-MODEL.md / the
  template / the TASK.md target as designed.
- AC-4: create-plan-phase.md states the TASK.md scope-check delta citing
  both planner-contract.md and create-spec-phase.md, and section 9's
  human-review list includes the TM-n reflection invariant.
- AC-5: spec-writer-contract.md's `extend_only` key-comparison rule points
  to planner-contract.md for the minimal-tier TASK.md Markdown append, and
  the six `write_policy` actions remain exactly six.
- AC-6: none of the three documents introduces a new gate_id -- the set of
  backtick-quoted, namespace-prefixed dotted gate_id tokens in each is
  unchanged from the base revision.
- AC-7: this module imports the standard library only, holds a negative
  proof per matcher, and the two plugin manifests (if touched by the commit
  guard fallback) change only their `version` field, identically.

These deliverables are specification documents (Markdown), so verification
is structural/textual against the rendered documents, anchored on their
existing headings -- the same technique
tests/test_worker_contracts_planning.py and tests/test_phase_protocols.py
already use for sibling contracts and phase protocols.
"""

import ast
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "em-workflow" / "references" / "contracts"
PHASES_DIR = REPO_ROOT / "em-workflow" / "references" / "phases"

PLANNER_PATH = CONTRACTS_DIR / "planner-contract.md"
SPEC_WRITER_PATH = CONTRACTS_DIR / "spec-writer-contract.md"
CREATE_PLAN_PATH = PHASES_DIR / "create-plan-phase.md"

PLUGIN_JSON_PATH = REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


# ---------------------------------------------------------------------------
# Files exist
# ---------------------------------------------------------------------------


class TestFilesExist(unittest.TestCase):
    def test_all_three_documents_exist(self):
        for path in (PLANNER_PATH, SPEC_WRITER_PATH, CREATE_PLAN_PATH):
            self.assertTrue(path.is_file(), f"{path} must exist")


# ---------------------------------------------------------------------------
# AC-1: planning_inputs field, write_policy target, digest_inputs,
# completed payload.
# ---------------------------------------------------------------------------


def _assert_ac1(test, text):
    test.assertIn("threat_model_template", text)

    wp_section = _extract_section(
        text,
        "## Additional input: `planning_inputs`",
        "### Minimal-tier `TASK.md` append",
    )
    test.assertIn("THREAT-MODEL.md", wp_section)
    test.assertIn("same terms", wp_section)
    test.assertIn("`create`", wp_section)
    test.assertIn("`replace_own`", wp_section)

    digest_section = _extract_section(text, "## digest_inputs", "## `completed` payload")
    test.assertIn("THREAT-MODEL.md", digest_section)
    test.assertIn("references/templates/threat-model.md", digest_section)

    payload_section = _extract_section(text, "## `completed` payload", "## Prohibited fields")
    test.assertIn("THREAT-MODEL.md", payload_section)
    test.assertIn("written_artifacts", payload_section)


class TestPlannerContractAC1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)

    def test_ac1_documented(self):
        _assert_ac1(self, self.text)

    # -- negative proof + non-vacuity guard -----------------------------

    FORGED_NO_THREAT_MODEL = (
        "## Additional input: `planning_inputs`\n\n"
        "```yaml\nplanning_inputs:\n  requirements_path: x\n```\n\n"
        "The planner's write_policy.targets cover IMPLEMENTATION.md and "
        "VERIFICATION.md (action `create` on a first pass, `replace_own` "
        "on a same-phase rewrite).\n\n"
        "### Minimal-tier `TASK.md` append\n\ncontent\n\n"
        "## Question packet bundling rule\n\ncontent\n\n"
        "## digest_inputs\n\n- REQUIREMENTS.md\n\n"
        "## `completed` payload\n\nwritten_artifacts: [...]\n\n"
        "## Prohibited fields\n"
    )

    def test_forged_text_without_threat_model_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_ac1(self, self.FORGED_NO_THREAT_MODEL)

    def test_forged_text_otherwise_well_formed(self):
        self.assertIn("planning_inputs", self.FORGED_NO_THREAT_MODEL)
        self.assertIn("write_policy.targets", self.FORGED_NO_THREAT_MODEL)


# ---------------------------------------------------------------------------
# AC-2: the minimal-tier TASK.md append subsection (SC-3), owned in full.
# ---------------------------------------------------------------------------


def _assert_ac2(test, text):
    sub = _extract_section(
        text,
        "### Minimal-tier `TASK.md` append",
        "## Question packet bundling rule",
    )
    lowered = sub.lower()
    test.assertIn("minimal", lowered)
    test.assertIn("threats-identified", sub)
    test.assertIn("extend_only", sub)
    test.assertIn("expect_digest", sub)
    test.assertIn("dispatch time", sub)
    test.assertIn("exact prefix", lowered)
    test.assertIn("no heading line", lowered)
    test.assertIn("## Expected Result", sub)
    test.assertIn("final", lowered)
    test.assertIn("`blocked`", sub)
    test.assertIn("writes nothing", lowered)
    test.assertIn("written_artifacts", sub)
    test.assertIn("only when", lowered)


class TestPlannerContractAC2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)

    def test_ac2_subsection_documented(self):
        _assert_ac2(self, self.text)

    def test_subsection_sits_inside_the_planning_inputs_section_span(self):
        start = self.text.index("## Additional input: `planning_inputs`")
        sub = self.text.index("### Minimal-tier `TASK.md` append")
        question_heading = self.text.index("## Question packet bundling rule")
        self.assertLess(start, sub)
        self.assertLess(sub, question_heading)

    def test_subsection_heading_is_a_level_3_heading(self):
        # Non-vacuity guard for the span test above: confirms the heading
        # really is `### ...`, not merely a same-titled `## ...` heading
        # that would also satisfy an index-ordering check.
        idx = self.text.index("Minimal-tier `TASK.md` append")
        line_start = self.text.rfind("\n", 0, idx) + 1
        self.assertTrue(self.text[line_start:idx].startswith("### "))

    # -- negative proof + non-vacuity guard -----------------------------
    # A forged append rule that omits the final-section precondition.

    FORGED_NO_FINAL_SECTION_PRECONDITION = (
        "### Minimal-tier `TASK.md` append\n\n"
        "Applies only when the tier is `minimal` and the threat-model "
        "verdict is `threats-identified`.\n\n"
        "- write_policy target: `feature-docs/{feature}/TASK.md`, action "
        "`extend_only`, `expect_digest` = its digest at dispatch time.\n"
        "- Exact-prefix rule: the pre-existing content of TASK.md must be "
        "an exact prefix of the new content.\n"
        "- No-heading rule: the appended text contains no heading line.\n"
        "- written_artifacts: TASK.md appears in written_artifacts only "
        "when it was actually appended.\n\n"
        "## Question packet bundling rule\n"
    )

    def test_forged_append_rule_omitting_final_section_precondition_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_ac2(self, self.FORGED_NO_FINAL_SECTION_PRECONDITION)

    def test_forged_text_otherwise_well_formed(self):
        # The forgery still carries every OTHER fact the matcher checks,
        # isolating the failure to the missing final-section precondition.
        forged = self.FORGED_NO_FINAL_SECTION_PRECONDITION
        self.assertIn("extend_only", forged)
        self.assertIn("expect_digest", forged)
        self.assertIn("exact prefix", forged.lower())
        self.assertIn("no heading line", forged.lower())
        self.assertIn("written_artifacts", forged)


# ---------------------------------------------------------------------------
# AC-3: create-plan-phase.md section 4 / section 7 / section 1.
# ---------------------------------------------------------------------------


def _assert_ac3(test, text):
    sec1 = _extract_section(text, "## 1. Purpose and ownership", "## 2. Preconditions")
    test.assertIn("THREAT-MODEL.md", sec1)

    sec4 = _extract_section(text, "## 4. Planner dispatch", "## 5. Question loop")
    test.assertIn("references/templates/threat-model.md", sec4)
    test.assertIn("planning_inputs.threat_model_template", sec4)
    test.assertIn("THREAT-MODEL.md", sec4)
    test.assertIn("TASK.md", sec4)
    test.assertIn("extend_only", sec4)

    sec7 = _extract_section(text, "## 7. Planner completion output", "## 8. Validation")
    test.assertIn("THREAT-MODEL.md", sec7)


class TestCreatePlanPhaseAC3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)

    def test_ac3_dispatch_and_completion_documented(self):
        _assert_ac3(self, self.text)

    # -- negative proof + non-vacuity guard -----------------------------

    FORGED_PRE_THREAT_MODEL = (
        "## 1. Purpose and ownership\n\n"
        "- implementation-planner produces IMPLEMENTATION.md, "
        "VERIFICATION.md, per-task plans.\n\n"
        "## 2. Preconditions\n\ncontent\n\n"
        "## 4. Planner dispatch\n\n"
        "- The registry paths it must consult: "
        "references/templates/task-plan.md.\n\n"
        "## 5. Question loop\n\ncontent\n\n"
        "## 7. Planner completion output\n\n"
        "written artifacts: IMPLEMENTATION.md, VERIFICATION.md.\n\n"
        "## 8. Validation\n\ncontent\n"
    )

    def test_forged_pre_threat_model_text_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_ac3(self, self.FORGED_PRE_THREAT_MODEL)

    def test_forged_text_otherwise_well_formed(self):
        self.assertIn("implementation-planner produces", self.FORGED_PRE_THREAT_MODEL)
        self.assertIn("registry paths", self.FORGED_PRE_THREAT_MODEL)


# ---------------------------------------------------------------------------
# AC-4: the TASK.md scope-check delta, and section 9's TM-n invariant.
# ---------------------------------------------------------------------------


def _assert_ac4(test, text):
    delta_section = _extract_section(
        text,
        "The clean-worktree precondition and the post-dispatch scope comparison",
        "## 1. Purpose and ownership",
    )
    test.assertIn("references/phases/create-spec-phase.md", delta_section)
    test.assertIn("references/contracts/planner-contract.md", delta_section)
    test.assertIn("pre-dispatch snapshot keeps", delta_section)
    test.assertIn("TASK.md", delta_section)
    test.assertIn("full content", delta_section)
    test.assertIn("post-dispatch check applies", delta_section)

    sec9 = _extract_section(text, "## 9. Planning invariants", "## 10. Atomic patch application")
    test.assertIn("remain human review only", sec9)
    test.assertIn("TM-n", sec9)
    test.assertIn("threats-identified", sec9)
    test.assertIn("plan-writing reflection rules", sec9)


class TestCreatePlanPhaseAC4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_PLAN_PATH)

    def test_ac4_scope_check_delta_and_human_review_documented(self):
        _assert_ac4(self, self.text)

    # -- negative proof + non-vacuity guard -----------------------------

    FORGED_NO_DELTA_NO_TM_N = (
        "The clean-worktree precondition and the post-dispatch scope "
        "comparison: references/phases/create-spec-phase.md (\"Scope "
        "verification\") -- identical here, so it is not repeated in this "
        "document.\n\n"
        "## 1. Purpose and ownership\n\ncontent\n\n"
        "## 9. Planning invariants -- x\n\n"
        "The following remain human review only:\n\n"
        "- No `excluded` or `tbd` requirement has a task assigned to it.\n\n"
        "## 10. Atomic patch application\n\ncontent\n"
    )

    def test_forged_text_missing_delta_and_tm_n_invariant_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_ac4(self, self.FORGED_NO_DELTA_NO_TM_N)

    def test_forged_text_otherwise_well_formed(self):
        self.assertIn("create-spec-phase.md", self.FORGED_NO_DELTA_NO_TM_N)
        self.assertIn("remain human review only", self.FORGED_NO_DELTA_NO_TM_N)


# ---------------------------------------------------------------------------
# AC-5: spec-writer-contract.md's extend_only pointer, and the six actions.
# ---------------------------------------------------------------------------


def _assert_ac5_pointer(test, text):
    section = _extract_section(
        text,
        "### `extend_only` key-comparison rule",
        "## How the orchestrator chooses each target's action before dispatch",
    )
    test.assertIn("references/contracts/planner-contract.md", section)
    test.assertIn("minimal-tier", section.lower())
    test.assertIn("TASK.md", section)
    test.assertIn("Markdown", section)


ACTION_ROW_RE = re.compile(r"^\| `([a-z_]+)` \|", re.MULTILINE)
EXPECTED_ACTIONS = {
    "create",
    "replace_own",
    "replace_authorized",
    "preserve",
    "extend_only",
    "regenerate",
}


def _assert_ac5_six_actions(test, text):
    table_section = _extract_section(
        text,
        "### The six `write_policy` actions",
        "**`regenerate` requires",
    )
    rows = ACTION_ROW_RE.findall(table_section)
    test.assertEqual(set(rows), EXPECTED_ACTIONS)
    test.assertEqual(len(rows), 6)


class TestSpecWriterContractAC5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SPEC_WRITER_PATH)

    def test_ac5_pointer_documented(self):
        _assert_ac5_pointer(self, self.text)

    def test_ac5_six_actions_unchanged(self):
        _assert_ac5_six_actions(self, self.text)

    # -- negative proofs + non-vacuity guards ----------------------------

    FORGED_NO_POINTER = (
        "### `extend_only` key-comparison rule\n\n"
        "`extend_only` applies to `design-system/tokens.yaml`. The worker "
        "parses the target as a YAML map.\n\n"
        "## How the orchestrator chooses each target's action before dispatch\n"
    )

    def test_forged_text_without_pointer_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_ac5_pointer(self, self.FORGED_NO_POINTER)

    def test_forged_pointer_text_otherwise_well_formed(self):
        self.assertIn("extend_only", self.FORGED_NO_POINTER)
        self.assertIn("design-system/tokens.yaml", self.FORGED_NO_POINTER)

    def test_forged_seventh_action_is_rejected(self):
        mutated = self.text.replace(
            "### The six `write_policy` actions\n\n"
            "| action | `expect_digest` | worker behaviour |\n"
            "|---|---|---|\n",
            "### The six `write_policy` actions\n\n"
            "| action | `expect_digest` | worker behaviour |\n"
            "|---|---|---|\n"
            "| `phantom_action` | required | A forged seventh action. |\n",
        )
        # Non-vacuity precondition: the replacement actually landed.
        self.assertIn("phantom_action", mutated)
        with self.assertRaises(AssertionError):
            _assert_ac5_six_actions(self, mutated)


# ---------------------------------------------------------------------------
# AC-6: no new gate_id introduced -- the set of backtick-quoted,
# namespace-prefixed dotted gate_id tokens is unchanged per document.
# ---------------------------------------------------------------------------

GATE_ID_RE = re.compile(r"`([a-z][a-z0-9-]*)\.([a-z][a-z0-9-]*)`")
# The fixed set of workflow-step namespaces a real gate_id's first segment
# is drawn from (em-workflow/references/batch-policies.yaml's gate_policies
# keys, plus the other workflow-step ids for completeness). Filtering on
# this set excludes non-gate dotted backtick tokens that share the same
# `word.word` shape (e.g. `project.license`, `tokens.yaml`).
GATE_NAMESPACES = {
    "create-spec",
    "create-plan",
    "design-system",
    "design",
    "review",
    "verify",
    "rework",
    "retrospect",
    "implement",
}


def _gate_ids_in(text):
    return frozenset(
        f"{a}.{b}" for a, b in GATE_ID_RE.findall(text) if a in GATE_NAMESPACES
    )


# The base-revision gate_id set for each document (recorded before this
# task's edits landed) -- also cross-checked against
# tests/test_gate_option_vocabulary.py's ISSUING_SITE_MAP, which lists the
# identical gate -> document associations for these three files.
BASE_GATE_IDS = {
    PLANNER_PATH: frozenset(
        {
            "create-plan.tbd-resolution",
            "create-plan.license-conflict",
            "create-plan.existing-files",
        }
    ),
    CREATE_PLAN_PATH: frozenset({"design-system.reclassify"}),
    SPEC_WRITER_PATH: frozenset(
        {
            "create-spec.artifact-overwrite",
            "design.artifact-overwrite",
            "create-plan.artifact-overwrite",
        }
    ),
}


class TestAC6NoNewGateIdIntroduced(unittest.TestCase):
    def test_planner_contract_gate_id_set_unchanged(self):
        self.assertEqual(_gate_ids_in(_read(PLANNER_PATH)), BASE_GATE_IDS[PLANNER_PATH])

    def test_create_plan_phase_gate_id_set_unchanged(self):
        self.assertEqual(
            _gate_ids_in(_read(CREATE_PLAN_PATH)), BASE_GATE_IDS[CREATE_PLAN_PATH]
        )

    def test_spec_writer_contract_gate_id_set_unchanged(self):
        self.assertEqual(
            _gate_ids_in(_read(SPEC_WRITER_PATH)), BASE_GATE_IDS[SPEC_WRITER_PATH]
        )

    def test_detector_matches_a_known_real_gate_id(self):
        # Non-vacuity guard: the detector actually recognizes a real gate_id
        # shape, so the three equality checks above are not vacuously true
        # against a detector that matches nothing.
        self.assertEqual(
            _gate_ids_in("See `create-plan.tbd-resolution` for details."),
            frozenset({"create-plan.tbd-resolution"}),
        )

    # -- negative proof ---------------------------------------------------

    def test_forged_addition_of_a_new_gate_id_is_detected(self):
        mutated = _read(PLANNER_PATH) + "\n\nSee `create-plan.new-gate` for details.\n"
        self.assertNotEqual(_gate_ids_in(mutated), BASE_GATE_IDS[PLANNER_PATH])

    def test_non_gate_dotted_tokens_are_not_mistaken_for_gate_ids(self):
        # `project.license` and `tokens.yaml` share the `word.word` backtick
        # shape but are not gate_ids -- the namespace filter must exclude
        # them.
        self.assertEqual(
            _gate_ids_in("`project.license` and `tokens.yaml` are not gates."),
            frozenset(),
        )


# ---------------------------------------------------------------------------
# AC-7: this module's own hygiene, and the manifest version-only-change
# invariant.
# ---------------------------------------------------------------------------


class TestModuleImportsStandardLibraryOnly(unittest.TestCase):
    def test_only_stdlib_top_level_imports(self):
        stdlib_names = set(sys.stdlib_module_names)
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        self.assertEqual(imported - stdlib_names, set())


# Base revision (git log a69ffefb, before this task's edits): both
# registries read 0.2.14; every field other than `version` is pinned by a
# sha256 digest of its canonical (sorted-key) JSON form, following this
# repository's existing hash-pin convention
# (tests/test_gate_option_vocabulary.py's `TestFrozenMachineReadSurface`:
# "refreshed, don't remove" on a legitimate future edit). `version` itself
# is checked as a floor, never a literal-equality pin
# (IMPLEMENTATION.md SC-6) -- the commit-guard fallback may have bumped it
# in the same commit as this task's document edits.
BASE_PLUGIN_JSON_VERSION = "0.2.14"
BASE_PLUGIN_JSON_NON_VERSION_SHA256 = (
    "9685ad84dff340269c26b03a0357a9ef26dabe290b607c2ac93940a127727f44"
)
BASE_MARKETPLACE_NON_VERSION_SHA256 = (
    "95992d59d4019b210d7730324f6d1b2922893fbef8817383f5709bf5adf1d381"
)


def _version_tuple(v):
    return tuple(int(part) for part in v.split("."))


def _non_version_digest(entry):
    """sha256 of the canonical (sorted-key) JSON form of `entry` with the
    `version` key removed -- so any change to any OTHER field is detected,
    without embedding the (large, frequently-legitimately-edited)
    `description` text as a literal in this test module."""
    non_version = {k: v for k, v in entry.items() if k != "version"}
    canonical = json.dumps(non_version, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TestManifestVersionOnlyChange(unittest.TestCase):
    """AC-7: if the commit-guard fallback touched the two manifests, only
    their `version` fields changed, and both hold the same value."""

    @classmethod
    def setUpClass(cls):
        cls.plugin_json = json.loads(_read(PLUGIN_JSON_PATH))
        marketplace = json.loads(_read(MARKETPLACE_JSON_PATH))
        cls.em_workflow_entry = next(
            p for p in marketplace["plugins"] if p.get("name") == "em-workflow"
        )

    def test_plugin_json_version_is_never_lower_than_the_base(self):
        self.assertGreaterEqual(
            _version_tuple(self.plugin_json["version"]),
            _version_tuple(BASE_PLUGIN_JSON_VERSION),
        )

    def test_plugin_json_and_marketplace_versions_are_identical(self):
        self.assertEqual(self.plugin_json["version"], self.em_workflow_entry["version"])

    def test_plugin_json_non_version_fields_unchanged(self):
        self.assertEqual(
            _non_version_digest(self.plugin_json), BASE_PLUGIN_JSON_NON_VERSION_SHA256
        )

    def test_marketplace_em_workflow_non_version_fields_unchanged(self):
        self.assertEqual(
            _non_version_digest(self.em_workflow_entry),
            BASE_MARKETPLACE_NON_VERSION_SHA256,
        )

    # -- negative proof + non-vacuity guard -----------------------------

    def test_forged_non_version_mutation_is_detected(self):
        mutated = dict(self.plugin_json)
        mutated["description"] = mutated.get("description", "") + " mutated"
        self.assertNotEqual(
            _non_version_digest(mutated), BASE_PLUGIN_JSON_NON_VERSION_SHA256
        )

    def test_digest_helper_is_insensitive_to_the_version_field_itself(self):
        # Non-vacuity guard on the helper: changing ONLY `version` must not
        # change the digest, since that is precisely the field the
        # commit-guard fallback is permitted to touch.
        bumped = dict(self.plugin_json)
        bumped["version"] = "999.999.999"
        self.assertEqual(_non_version_digest(bumped), _non_version_digest(self.plugin_json))


if __name__ == "__main__":
    unittest.main()
