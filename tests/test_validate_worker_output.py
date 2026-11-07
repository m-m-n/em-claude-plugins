"""Tests for task0008: em-workflow/scripts/validate-worker-output.py and its
fixture corpus (em-workflow/references/fixtures/).

Covers task0008 Acceptance Criteria (feature-docs/agent-separation/
tasks/task0008.md):

- AC-1: TestCLIInterface -- five --kind values, mandatory --worker/--input,
  every auxiliary argument from design-input.md 5.11.1; unknown --kind is an
  execution error.
- AC-2: TestExitCodes -- 0 / 1 (JSON on stdout) / 2, and the PyYAML-missing
  message.
- AC-3: TestInputEnvelopeMandatoryForWorkerResult -- omitting
  --input-envelope with --kind worker-result exits 2 for every worker.
- AC-4: TestModeEchoAndAnalystModeExclusivity -- mode_echo missing/mismatch,
  and design_system_detection payload containing full-mode-only keys.
- AC-5: TestDryRunApplyRejections -- stale digest/blob anchor, expected
  mismatch, duplicate patch identifier, replace_all after implementation
  started, append_rework missing the mandatory preserve path.
- AC-6: TestFixtureCoverageValidAndInvalidPerBranch -- every branch group has
  at least one valid and one invalid fixture, including the two analyst
  modes separately.
- AC-7: TestFixtureCorpusDataDriven -- every fixture under
  em-workflow/references/fixtures/ is run and asserted against the exit
  code its directory name (valid-/invalid-) declares.

TestFixtureBranchesDerivedFromDesignInput is the Test Notes' coverage test:
it parses the branch table from design-input.md 5.11.5 (and, for
phase-state, the reconcile table in 5.6.3 that row points at) rather than
hardcoding the expected vocabulary, so a branch added to the design later
has no fixture until one is added (NFR6 applies to tests too; mirrors the
pattern in test_workflow_patch_doc.py).

Edge cases (Test Notes): a task-plan Files bullet with zero/two
backtick-quoted paths (fixtures under worker-result/implementation-planner);
an extend_only target whose YAML contains an alias or merge key
(TestExtendOnlyComparability, direct unit test of the pure helper --
see that function's docstring in the script for why it is not wired to a
--kind path).

task0016 (review round1 rework) added coverage for as5, as6, as8 (validator
half), as15, as16, as17 and as21 -- see feature-docs/agent-separation/
reviews/round1.yaml for the reproductions these classes pin:

- AC-1 / as6: TestWrittenArtifactsContainment, TestPathContainmentHelper --
  segment-wise written_artifacts containment (replaces string-prefix
  matching), malformed entries and a non-list written_artifacts no longer
  crash.
- AC-2 / as5: TestReworkIndexTaskCoverageDirect, TestReworkIndexCoverage --
  rework_index completeness verified against tasks_patch.entries in both
  directions; shared_contract_rationale is a required payload key.
- AC-3 / as15: TestDomainsVocabularyParse -- the domains vocabulary parser
  no longer absorbs the complexity vocabulary comment that follows it.
- AC-4 / as16: TestPlanPathContainment (formerly TestSymlinkedWrittenArtifact
  -- the symlink case now asserts REJECTION instead of successful read,
  per the task's explicit behaviour change) -- absolute paths, `..`
  segments, symlink segments and oversized reads are all rejected before
  the plan file is opened.
- AC-5 / as8 (validator half): TestQuestionCategoryForcesBlockingUnanswered
  -- spec-change/security/license questions must set on_unanswered: block.
- AC-6 / as21: TestStatusPayloadExclusivity -- the five non-completed
  statuses forbid a non-empty payload.
- AC-7 / as21: TestFixtureCoverageDerivedFromCapabilityTable, replacing the
  weak substring check in TestFixtureBranchesDerivedFromDesignInput for
  kind worker-result (see that test's inline comment).

task0003 (feature-docs/create-plan-status-conflict/tasks/task0003.md) adds
TestReplaceAllCreatePlanEntryStatus below, pinning the validator's
`replace_all` dry-run-apply permission check against the create-plan step's
entry status:

- AC-3: a new `invalid-replace-all-create-plan-in-progress` fixture makes
  the check reject the patch with the `replace-all-not-permitted`
  identifier, attributed to the create-plan step's `in_progress` status.
- AC-4: the same patch shape passes (exit 0) for both `pending` (the
  existing `valid-dry-run-apply` fixture, asserted here by name rather than
  only via the combined both-operations sweep) and `needs_update` (new
  `valid-replace-all-create-plan-needs-update` fixture).
- AC-5: the `in_progress` rejection carries exactly one error identifier --
  no staleness, vocabulary, or expected-mismatch entry rides along, so the
  regression cannot pass for the wrong reason.

task0016 (feature-docs/goal-vs-spec-divergence review round1 rework) extends
TestReplaceAllCreatePlanEntryStatus further: the create-plan/task-status
permission check is no longer frozen (feature-docs/create-plan-status-
conflict's D1 freeze is superseded here) because FR4/FR6 require the
re-planning path to permit `merged` tasks, which the check rejected before
this task:

- AC-1: `valid-replace-all-replanning-merged-tasks` -- create-plan `pending`
  re-entered via the SPEC-change transition (a `spec_change` record in
  `--phase-state` plus `workflow.implement.base_commit` already set) permits
  a `merged` task.
- AC-2 / AC-6: `invalid-replace-all-initial-planning-merged-tasks` -- the
  same patch shape without the re-entry signal (no `--phase-state`) is still
  rejected: a narrower invocation never widens what replace_all permits.
- AC-3: `invalid-replace-all-after-implementation-started` (`create-plan:
  needs_update` with an `in_progress` task) still fails on the re-planning
  path too, with exactly one error identifier.

task0017 (feature-docs/goal-vs-spec-divergence review round2 rework) settles
the re-planning permission contract in one place after task0013 (document)
and task0016 (validator) disagreed when changed in separate worktrees:

- AC-1 (FR6): `TestCanonicalReentryInvocation` drives the validator in
  EXACTLY create-plan-phase.md's canonical invocation form -- `--feature-dir`
  plus `--phase-state` pointing at the create-plan phase's own state file,
  never at rework.yaml -- and asserts acceptance. `resolve_rework_phase_
  state()` / `workflow_replace_all_spec_change_reentry()` now read the
  signal from `{feature-dir}/phase-state/rework.yaml`, or from a
  `--phase-state` mapping whose own `phase` is `rework` (an equivalence
  case, proven separately, never substituted for this AC).
- AC-2 (FR4): `TestReplanningReentrySignalHelper` adds direct proofs for
  every new failure direction (missing `phase`, wrong `phase`, feature
  mismatch, a `spec_change` record missing a mandatory field, `consumed:
  true`) -- each falls back to the initial-planning rule, fail-closed.
- AC-3 (FR5) / AC-5: `TestReplanningMandatoryPreserveAndTaskIdAllocation`
  pins the two new re-planning-path-only obligations: `workflow.implement.
  base_commit` mandatory in `preserve`, and `entries` must re-declare every
  task id already registered in `workflow.yaml` (new ids allocated above
  the highest registered one) -- via three new fixtures (`invalid-replace-
  all-replanning-missing-base-commit-preserve`, `invalid-replace-all-
  replanning-consumed-spec-change`, `invalid-replace-all-replanning-drops-
  existing-task`).
- AC-4: the corrected `valid-replace-all-replanning-merged-tasks` fixture
  (preserve gains `workflow.implement.base_commit`, `phase-state.json`
  gains `phase`/`feature`/a complete unconsumed `spec_change` record, and
  its `entries` stop re-issuing `task0009`, the id its own `workflow.json`
  already registers) is asserted by name in both TestReplaceAllCreatePlan
  EntryStatus and the new class above.
- AC-7: every pre-existing fixture in the `replace_planning` group keeps
  its name and its outcome (unchanged in this round) -- already asserted by
  name throughout `TestReplaceAllCreatePlanEntryStatus`, unaffected by this
  round's edits.

task0022 (goal-vs-spec-divergence, review round 3, finding
consumed-flag-split) splits the single `consumed` flag into two independent
flags -- `consumed` (stop-condition-3 suppression) and `replan_authorized`
(the re-planning authorization) -- because the ordering the re-planning path
actually runs through always has `consumed: true` by the time `create-plan`
is reached, so the pre-existing helper always fell back to the
initial-planning rule (FR6 never held):

- AC-3 (FR4, FR6): `workflow_replace_all_spec_change_reentry` now reads
  `replan_authorized` instead of `consumed` -- `TestReplanningReentrySignal
  Helper` below is updated so its "spent authorization" / "malformed
  authorization" cases key on `replan_authorized`, not `consumed`.
- AC-4 (FR6): `TestReentryOrdering` reproduces the transition's real
  sequence (record written -> `create-spec` dispatched, `consumed` becomes
  `true` -> `create-plan` read `pending` with `merged` tasks present) and
  asserts the re-planning `replace_all` is accepted despite `consumed:
  true`, via `valid-replace-all-replanning-after-create-spec-dispatch`.
- AC-6 (FR5, NFR8): the pre-existing `invalid-replace-all-replanning-
  consumed-spec-change` fixture is retired -- the reading it pinned
  (`consumed: true` alone forces rejection) is exactly what this task
  removes -- in favour of the new `invalid-replace-all-replan-authorization-
  spent` fixture, which pins the surviving reading (an already-spent
  `replan_authorized` forces rejection, regardless of `consumed`).
  `valid-replace-all-replanning-merged-tasks` gains `replan_authorized:
  true` alongside its existing `consumed: false`.

task0025 (feature-docs/goal-vs-spec-divergence review round3 rework, AC-2)
adds `TestGateResolvedAnswerSource`: `batch-classification-gate` (the
classification gate's proceed-outcome answer source,
references/question-resolution.md's Classification gate Outcome step) is
present in `ANSWER_SOURCE_VALUES`, and a real answer object using it
validates with `validate_answer()`. The cross-document agreement between
this constant and references/question-packet-schema.md's `source`
vocabulary is asserted in tests/test_gate_outcome_packet_lifecycle.py, not
here (C4: this module owns the validator script, not the schema document).

task0023 (feature-docs/goal-vs-spec-divergence review round 3, D10) revises
task0017's "entries must re-declare every registered id" form: a
re-planning `replace_all` now carries an already-registered id in
`tasks_patch.carried_task_ids` (record copied from `workflow.yaml`
verbatim) rather than re-declaring its body under `tasks_patch.entries`.
Covers task0023 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0023.md):

- AC-3: `TestReplanningCarryOverEnforcement` -- a new
  `invalid-replace-all-replanning-entry-for-registered-id` fixture pins the
  `replace-all-entry-for-registered-id` identifier (an `entries` key naming
  a registered id), reported alone. The other two AC-3 rejections
  (`carried_task_ids` omitting a registered id; a new id at or below the
  high-water mark) are `replace-all-drops-task` (re-grounded, see
  `TestReplanningMandatoryPreserveAndTaskIdAllocation` above) and the
  unchanged `replace-all-task-id-reused`.
- AC-4: field-by-field carry-over (the applied workflow's carried task
  record equals the pre-apply record, including `files`) is proven directly
  against `apply_patch()` in `tests/test_replanning_carry_over.py`, not
  re-tested here (this module stops at the validator's error-identifier
  surface, C4).
- AC-6: `valid-replace-all-replanning-merged-tasks`'s `entries` stop
  re-issuing `task0009` -- it moves to `carried_task_ids` instead (a
  positive demonstration of the rule, not a counter-example pinned as
  valid); `invalid-replace-all-replanning-drops-existing-task` is
  re-grounded on an empty `carried_task_ids` rather than an incomplete
  `entries`. `test_corrected_replanning_merged_tasks_fixture_passes` and
  `test_drops_existing_registered_task_id_rejected` above still assert
  both fixtures by name.

Also touched by task0023 as a necessary follow-on of the merge with
task0022 (D10 meets the consumed-flag-split): `TestCanonicalReentryInvocation.
_patch_obj` (task0022's version still re-declared task0009 under `entries`;
moved to `carried_task_ids`) -- see this module's own git history for the
exact hunk, not restated as a separate docstring paragraph.

rework-contract-drift/task0004 (FR3 validator half, FR4, FR6) adds three
new test classes, covering this task's own AC-6 and AC-7:

- `TestOriginKindVocabulary`: `workflow_replace_all_spec_change_reentry`
  rejects an out-of-vocabulary `spec_change.origin_kind`, accepting only
  `review` and `verify` (mirroring `classification`'s classifier/verdict/
  decision vocabulary enforcement).
- `TestFailedItemCategoryVocabulary`: the new
  `_validate_verify_failed_items_categories` (wired into
  `validate_workflow_patch`, unconditional on `--dry-run-apply`) rejects a
  `workflow.yaml` verify-step `failed_items[]` entry whose `category` is
  missing, empty, or out of the seven-value vocabulary
  (IMPLEMENTATION.md Shared Components), accepting each of the seven.
- `TestOriginIdEvidenceRequirement`: `validate_question` rejects a
  `rework.spec-change` question with no `evidence[]` entry carrying a
  non-empty `origin_id` (the mechanical half of `references/
  question-resolution.md`'s Classification gate origin verification),
  driven directly against the two new fixtures under
  `references/fixtures/question-packet/origin-verification/` (also swept,
  by exit code, through `TestFixtureCorpusDataDriven` above).

rework-contract-drift/task0008 (review round1 rework, FR3, NFR1, NFR2, D11)
narrows `_validate_verify_failed_items_categories`: task0004's version ran
unconditionally over every `failed_items[]` entry regardless of what the
patch touched, rejecting a legacy, category-less entry even when the patch
never went near the verify step -- a defect no worker can repair (a step
patch may set only `status`). The function now takes the patch itself and
is scoped by the new `_verify_step_targeted_by_patch` helper: it errors
only for the entries of a verify step the patch targets via `step_patches`.
`TestFailedItemCategoryVocabulary` below is updated in place (every direct
call now supplies a patch) and gains the two scoping cases (untargeted:
no error even over a non-conforming entry; targeted: retained teeth). The
existing wiring test's patch now targets the verify step, exercising the
new scope instead of the removed unconditional one. Covers this task's
AC-6 and (together with the new fixture case under
`references/fixtures/workflow-patch/append_rework/`) AC-7.

batch-codex-autonomous-decisions/task0004 (FR18-FR21) rewords the rationale
around the `on_unanswered: block` constraint without touching its
behaviour: `BLOCKING_REQUIRED_CATEGORIES` and the `on_unanswered != "block"`
rejection stay exactly as they are (D5).

- AC-1: `TestQuestionPacketSchemaBlockRationale` pins
  `question-packet-schema.md`'s constraint sentence verbatim and asserts
  the new rationale (routes into the minimum-side-effect branch instead of
  the old implicit "batch run aborts" meaning), with a negative proof that
  the superseded wording is gone.
- AC-2: `test_rejection_message_states_the_surviving_rationale` (added to
  `TestQuestionCategoryForcesBlockingUnanswered`) pins a stable fragment of
  the validator's reworded parenthetical rationale, with the same negative
  proof.
- AC-3, AC-4: `TestIrreversibleAssumptionFixtureAccepted` adds
  `references/fixtures/question-packet/category-fail-closed/valid-
  irreversible-assumption-blocking/` and asserts it directly (exit 0), that
  its question's category sits outside `BLOCKING_REQUIRED_CATEGORIES` (so
  it exercises the irreversibility declaration, not the category rule),
  and that its `assumptions[]` entry actually declares `reversible: false`
  against that question. The corpus sweep and the branch-coverage guard
  already discover this fixture by directory-name convention.
- AC-5, AC-6: unchanged, pre-existing `TestQuestionCategoryForcesBlocking
  Unanswered.test_all_three_fail_closed_categories_are_rejected_directly`
  and the gate-registry tests continue to pass untouched, proving the
  freeze (D5, NFR8).
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
FIXTURES_ROOT = REPO_ROOT / "em-workflow" / "references" / "fixtures"
DESIGN_INPUT_PATH = REPO_ROOT / "feature-docs" / "agent-separation" / "design-input.md"
QUESTION_PACKET_SCHEMA_DOC_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "question-packet-schema.md"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()


def run_cli(args, env=None):
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _companion(case_dir, stem):
    for ext in (".json", ".yaml", ".yml"):
        p = case_dir / f"{stem}{ext}"
        if p.is_file():
            return p
    return None


# Fixture directory group -> --worker value, for kinds whose CLI worker
# argument matters (worker-result). Other kinds pass a fixed, arbitrary
# valid worker name since --worker is mandatory but not cross-checked there.
WORKER_FOR_GROUP = {
    "requirements-analyst-full": "requirements-analyst",
    "requirements-analyst-design-system-detection": "requirements-analyst",
    "spec-writer": "spec-writer",
    "implementation-planner": "implementation-planner",
    "rework-planner": "rework-planner",
    "designer": "designer",
}


def build_base_repo(tree, repo_dir):
    """Builds the disposable repository a fixture case's `base-tree.json`
    describes and returns its commit ID. `tree` maps a repository-relative
    path to the file's text. The tree is data because a file whose name
    matches the report-artifact rule cannot be written into this repository
    by an implementer (subagent-report-write-block/task0001). The identity
    is set on every command and no user or system git configuration is read."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"

    def git(*args):
        return subprocess.run(
            [
                "git",
                "-c", "user.name=Fixture",
                "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false",
                "-C", str(repo_dir),
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    repo_dir.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    for rel_path, content in tree.items():
        target = repo_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", "fixture base")
    return git("rev-parse", "HEAD").stdout.strip()


def build_case_args(kind, group, case_dir, scratch_dir=None):
    """Builds the CLI argv for one fixture case directory, wiring every
    companion file/dir present by its fixed role name (see the fixtures
    directory docstring-equivalent in this module: input/envelope/packet/
    answers/workflow/digest-source/phase-state/registries/feature-dir/
    baseline-dir/DRY_RUN_APPLY).

    A case directory holding `base-tree.json` (a mapping from repository-
    relative path to file content) also gets a disposable repository built
    under `scratch_dir`, and `--target-repo` / `--base-commit` pointing at
    it."""
    input_path = _companion(case_dir, "input")
    assert input_path is not None, f"{case_dir} has no input.* file"
    worker = WORKER_FOR_GROUP.get(group, "implementation-planner")
    args = ["--kind", kind, "--worker", worker, "--input", str(input_path)]

    for flag, stem in (
        ("--input-envelope", "envelope"),
        ("--packet", "packet"),
        ("--answers", "answers"),
        ("--workflow", "workflow"),
        ("--digest-source", "digest-source"),
        ("--phase-state", "phase-state"),
    ):
        companion = _companion(case_dir, stem)
        if companion is not None:
            args += [flag, str(companion)]

    for flag, dirname in (
        ("--registries", "registries"),
        ("--feature-dir", "feature-dir"),
        ("--baseline-dir", "baseline-dir"),
    ):
        d = case_dir / dirname
        if d.is_dir():
            args += [flag, str(d)]

    if (case_dir / "DRY_RUN_APPLY").exists():
        args.append("--dry-run-apply")

    base_tree = _companion(case_dir, "base-tree")
    if base_tree is not None:
        assert scratch_dir is not None, (
            f"{case_dir} holds a base tree: pass scratch_dir so its repository can be built"
        )
        repo_dir = Path(scratch_dir) / "base-repo"
        base_commit = build_base_repo(json.loads(base_tree.read_text(encoding="utf-8")), repo_dir)
        args += ["--target-repo", str(repo_dir), "--base-commit", base_commit]

    return args


def discover_fixture_cases():
    """Yields (kind, group, case_dir) for every leaf fixture case directory
    under em-workflow/references/fixtures/. No manifest file is read -- the
    kind/group/outcome are the directory names themselves (Design section:
    "Fixture files carry enough naming structure ... without a separate
    manifest")."""
    if not FIXTURES_ROOT.is_dir():
        return
    for kind_dir in sorted(FIXTURES_ROOT.iterdir()):
        if not kind_dir.is_dir():
            continue
        for group_dir in sorted(kind_dir.iterdir()):
            if not group_dir.is_dir():
                continue
            for case_dir in sorted(group_dir.iterdir()):
                if not case_dir.is_dir():
                    continue
                yield kind_dir.name, group_dir.name, case_dir


def expected_exit_code(case_dir):
    name = case_dir.name
    if name.startswith("valid-"):
        return 0
    if name.startswith("invalid-"):
        return 1
    raise AssertionError(f"fixture case dir {case_dir} must start with valid- or invalid-")


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------

class TestCLIInterface(unittest.TestCase):
    def test_all_five_kind_values_are_declared(self):
        parser = VWO.build_arg_parser()
        kind_action = next(a for a in parser._actions if a.dest == "kind")
        self.assertEqual(set(kind_action.choices), set(VWO.KINDS))
        self.assertEqual(len(VWO.KINDS), 5)

    def test_worker_and_input_are_mandatory(self):
        parser = VWO.build_arg_parser()
        required_dests = {a.dest for a in parser._actions if getattr(a, "required", False)}
        self.assertIn("worker", required_dests)
        self.assertIn("input", required_dests)

    def test_all_auxiliary_arguments_declared(self):
        parser = VWO.build_arg_parser()
        dests = {a.dest for a in parser._actions}
        for expected in (
            "packet",
            "answers",
            "workflow",
            "registries",
            "phase_state",
            "input_envelope",
            "digest_source",
            "feature_dir",
            "baseline_dir",
            "dry_run_apply",
        ):
            self.assertIn(expected, dests, f"missing auxiliary argument {expected!r}")

    def test_unknown_kind_is_an_execution_error(self):
        result = run_cli(["--kind", "not-a-real-kind", "--worker", "designer", "--input", "/nonexistent"])
        self.assertEqual(result.returncode, 2)

    def test_unknown_worker_is_an_execution_error(self):
        result = run_cli(["--kind", "phase-state", "--worker", "not-a-real-worker", "--input", "/nonexistent"])
        self.assertEqual(result.returncode, 2)


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------

class TestExitCodes(unittest.TestCase):
    def test_valid_input_exits_0(self):
        case_dir = FIXTURES_ROOT / "worker-result" / "designer" / "valid-completed"
        result = run_cli(build_case_args("worker-result", "designer", case_dir))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")

    def test_validation_failure_exits_1_with_json_detail_on_stdout(self):
        case_dir = FIXTURES_ROOT / "worker-result" / "spec-writer" / "invalid-missing-payload"
        result = run_cli(build_case_args("worker-result", "spec-writer", case_dir))
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertIn("errors", payload)
        self.assertTrue(payload["errors"])

    def test_pyyaml_missing_exits_2_naming_pyyaml(self):
        with tempfile.TemporaryDirectory() as stub_dir:
            stub_path = Path(stub_dir) / "yaml.py"
            stub_path.write_text("raise ImportError(\"No module named 'yaml'\")\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = stub_dir + os.pathsep + env.get("PYTHONPATH", "")
            result = run_cli(
                ["--kind", "phase-state", "--worker", "designer", "--input", "/nonexistent"], env=env
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("PyYAML", result.stderr)


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------

class TestInputEnvelopeMandatoryForWorkerResult(unittest.TestCase):
    def test_missing_input_envelope_exits_2_for_every_worker(self):
        for worker in VWO.WORKERS:
            with self.subTest(worker=worker):
                result = run_cli(
                    ["--kind", "worker-result", "--worker", worker, "--input", "/nonexistent"]
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("input-envelope", result.stderr)


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------

class TestModeEchoAndAnalystModeExclusivity(unittest.TestCase):
    def _run(self, group, case_name):
        case_dir = FIXTURES_ROOT / "worker-result" / group / case_name
        return run_cli(build_case_args("worker-result", group, case_dir))

    def test_missing_mode_echo_fails_validation(self):
        result = self._run("requirements-analyst-full", "invalid-mode-echo-missing")
        self.assertEqual(result.returncode, 1)
        self.assertIn("mode_echo", result.stdout)

    def test_mismatched_mode_echo_fails_validation(self):
        result = self._run("requirements-analyst-full", "invalid-mode-echo-mismatch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("mode_echo", result.stdout)

    def test_design_system_detection_with_full_mode_payload_keys_fails_validation(self):
        result = self._run("requirements-analyst-design-system-detection", "invalid-full-mode-payload-keys")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("resolved_requirements", messages)

    def test_valid_full_mode_completed_passes(self):
        result = self._run("requirements-analyst-full", "valid-completed")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_valid_design_system_detection_completed_passes(self):
        result = self._run("requirements-analyst-design-system-detection", "valid-completed")
        self.assertEqual(result.returncode, 0, result.stdout)


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------

class TestDryRunApplyRejections(unittest.TestCase):
    """Test Notes: the dry-run application needs a workflow.yaml to apply
    against; each of these fixtures carries a small synthetic workflow.json
    built in em-workflow/references/fixtures/ rather than depending on this
    feature's own workflow.yaml."""

    def _run(self, group, case_name):
        case_dir = FIXTURES_ROOT / "workflow-patch" / group / case_name
        return run_cli(build_case_args("workflow-patch", group, case_dir))

    def test_stale_input_digest_rejected(self):
        result = self._run("replace_planning", "invalid-stale-input-digest")
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stdout.lower())

    def test_stale_workflow_blob_rejected(self):
        result = self._run("replace_planning", "invalid-stale-workflow-blob")
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stdout.lower())

    def test_expected_mismatch_rejected(self):
        result = self._run("append_rework", "invalid-expected-status-mismatch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("expected", result.stdout.lower())

    def test_duplicate_patch_id_with_differing_content_rejected(self):
        result = self._run("replace_planning", "invalid-duplicate-patch-id-differing-content")
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate", result.stdout.lower())

    def test_replace_all_after_implementation_started_rejected(self):
        result = self._run("replace_planning", "invalid-replace-all-after-implementation-started")
        self.assertEqual(result.returncode, 1)
        self.assertIn("replace_all", result.stdout)

    def test_append_rework_missing_mandatory_preserve_path_rejected(self):
        result = self._run("append_rework", "invalid-missing-base-commit-preserve")
        self.assertEqual(result.returncode, 1)
        self.assertIn("workflow.implement.base_commit", result.stdout)

    def test_valid_dry_run_apply_passes_for_both_operations(self):
        for group, case in (
            ("replace_planning", "valid-dry-run-apply"),
            ("append_rework", "valid-dry-run-apply"),
        ):
            with self.subTest(group=group):
                result = self._run(group, case)
                self.assertEqual(result.returncode, 0, result.stdout)


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------

class TestFixtureCoverageValidAndInvalidPerBranch(unittest.TestCase):
    """Every branch-group directory under references/fixtures/<kind>/ must
    contain at least one valid-* and one invalid-* case directory."""

    def test_every_group_has_a_valid_and_an_invalid_case(self):
        groups = {}
        for kind, group, case_dir in discover_fixture_cases():
            groups.setdefault((kind, group), set()).add(
                "valid" if case_dir.name.startswith("valid-") else "invalid"
            )
        self.assertTrue(groups, "expected at least one fixture group to exist")
        for (kind, group), outcomes in sorted(groups.items()):
            with self.subTest(kind=kind, group=group):
                self.assertIn("valid", outcomes, f"{kind}/{group} has no valid-* fixture")
                self.assertIn("invalid", outcomes, f"{kind}/{group} has no invalid-* fixture")

    def test_the_two_analyst_modes_are_covered_separately(self):
        worker_result_groups = {
            group for kind, group, _ in discover_fixture_cases() if kind == "worker-result"
        }
        self.assertIn("requirements-analyst-full", worker_result_groups)
        self.assertIn("requirements-analyst-design-system-detection", worker_result_groups)


# ---------------------------------------------------------------------------
# AC-7 + data-driven fixture corpus runner
# ---------------------------------------------------------------------------

class TestFixtureCorpusDataDriven(unittest.TestCase):
    def test_every_fixture_matches_its_declared_exit_code(self):
        cases = list(discover_fixture_cases())
        self.assertTrue(cases, "expected the fixture corpus to be non-empty")
        for kind, group, case_dir in cases:
            with self.subTest(kind=kind, group=group, case=case_dir.name), \
                    tempfile.TemporaryDirectory() as scratch_dir:
                expected = expected_exit_code(case_dir)
                args = build_case_args(kind, group, case_dir, scratch_dir=scratch_dir)
                result = run_cli(args)
                self.assertEqual(
                    result.returncode,
                    expected,
                    f"{case_dir}: expected exit {expected}, got {result.returncode}\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}",
                )


# ---------------------------------------------------------------------------
# Test Notes: coverage test derived from design-input.md, not hardcoded
# ---------------------------------------------------------------------------

def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def _normalize(token):
    return token.replace("_", "").replace("-", "").lower()


class DesignInputBranchFixture:
    """Derives, per --kind, the set of branch tokens the fixture corpus must
    cover from design-input.md 5.11.5's table (and, for phase-state, the
    5.6.3 reconcile table that row points at instead of enumerating
    inline) -- mirrors test_workflow_patch_doc.py's pattern of parsing the
    design document rather than hardcoding its content a second time."""

    # answer_mode is a field name in the 5.11.5 row, not a branch value by
    # itself; its actual branches are its four enum values (pulled from the
    # script's own constant, not duplicated here).
    TOKEN_EXPANSIONS = {"answer_mode": VWO.ANSWER_MODE_VALUES}

    def __init__(self):
        self.text = _read(DESIGN_INPUT_PATH)
        self.fixture_section = _extract_section(
            self.text, "#### 5.11.5 fixture", "### 5.12 既存 feature の互換性"
        )

    def branch_tokens_for_kind(self, kind):
        if kind == "phase-state":
            return self._phase_state_statuses()
        row_match = re.search(
            r"^\| `%s` \| (.+) \|$" % re.escape(kind), self.fixture_section, re.MULTILINE
        )
        assert row_match, f"expected a 5.11.5 table row for kind {kind!r}"
        raw_tokens = re.findall(r"`([^`]+)`", row_match.group(1))
        assert raw_tokens, f"expected at least one backtick-quoted token in the {kind!r} row"
        tokens = set()
        for t in raw_tokens:
            tokens.update(self.TOKEN_EXPANSIONS.get(t, {t}))
        return tokens

    def _phase_state_statuses(self):
        section = _extract_section(self.text, "#### 5.6.3 再開判定", "#### 5.6.4 サイズ管理")
        statuses = re.findall(r"^\| `([a-z_]+)`", section, re.MULTILINE)
        assert statuses, "expected the 5.6.3 phase-state status table rows"
        return set(statuses)


class TestFixtureBranchesDerivedFromDesignInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputBranchFixture()

    def test_every_parsed_branch_token_has_at_least_one_fixture(self):
        for kind in VWO.KINDS:
            if kind == "worker-result":
                # as21: this substring-anywhere-in-the-kind check is too weak
                # for worker-result -- it is satisfied by ANY worker's
                # fixture mentioning a status token, regardless of which
                # worker actually needs it. Superseded by
                # TestFixtureCoverageDerivedFromCapabilityTable, which reads
                # each fixture's own `status` field and checks it against
                # the worker/mode it actually belongs to.
                continue
            branch_tokens = self.fixture.branch_tokens_for_kind(kind)
            kind_dir = FIXTURES_ROOT / kind
            all_paths_normalized = [
                _normalize(str(case_dir.relative_to(kind_dir)))
                for _, _, case_dir in discover_fixture_cases()
                if case_dir.is_relative_to(kind_dir)
            ]
            for token in sorted(branch_tokens):
                with self.subTest(kind=kind, token=token):
                    needle = _normalize(token)
                    self.assertTrue(
                        any(needle in path for path in all_paths_normalized),
                        f"design-input.md 5.11.5 lists branch {token!r} for kind {kind!r}, "
                        "but no fixture path under references/fixtures/ mentions it -- "
                        "add a fixture (this is the 'fails until a fixture exists' guard)",
                    )


# ---------------------------------------------------------------------------
# Edge case: extend_only YAML with an alias or merge key is uncomparable
# ---------------------------------------------------------------------------

class TestExtendOnlyComparability(unittest.TestCase):
    """design-input.md 5.4.2: an extend_only target whose YAML contains an
    alias or merge key must be reported as uncomparable rather than silently
    accepted. The validator itself has no CLI channel carrying the actual
    current file content for an arbitrary write_policy target (confirmed
    against the exhaustive auxiliary-argument list in the Design section),
    so this rule is exercised directly against the pure helper function --
    see its docstring in validate-worker-output.py."""

    def test_plain_mapping_is_comparable(self):
        self.assertTrue(VWO.yaml_extend_only_comparable("a: 1\nb: 2\n"))

    def test_alias_is_uncomparable(self):
        text = "base: &b\n  x: 1\nderived: *b\n"
        self.assertFalse(VWO.yaml_extend_only_comparable(text))

    def test_merge_key_is_uncomparable(self):
        text = "base: &b\n  x: 1\nderived:\n  <<: *b\n  y: 2\n"
        self.assertFalse(VWO.yaml_extend_only_comparable(text))

    def test_non_mapping_document_is_uncomparable(self):
        self.assertFalse(VWO.yaml_extend_only_comparable("- a\n- b\n"))


# ---------------------------------------------------------------------------
# as16 / AC-4: the `plan` field in a workflow_patch tasks_patch entry is
# untrusted worker output joined to --feature-dir. Absolute paths, `..`
# segments and symlink segments must be rejected before the file is ever
# opened, and an oversized plan file must be rejected before it is read in
# full. Built in temporary directories at test-run time per the Test
# Notes -- the committed fixture corpus never carries a symlink object.
# ---------------------------------------------------------------------------

class TestPlanPathContainment(unittest.TestCase):
    def _make_feature_dir(self, tmp_path):
        feature_dir = tmp_path / "feature-dir"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        return feature_dir, tasks_dir

    @staticmethod
    def _valid_plan_text():
        return (
            "# Task Plan: task0001 -- Something\n\n"
            "## Goal\n\nDeliver something.\n\n"
            "## Requirements\n\nFR1\n\n"
            "## Scope\n\n"
            "### Files to Create\n"
            "- `src/a.go` -- main file\n\n"
            "### Files to Modify\n\n"
            "## Design\n\nNotes.\n\n"
            "## Acceptance Criteria (MANDATORY)\n\n"
            "- [ ] AC-1: something is delivered\n\n"
            "## Test Notes\n\nNotes.\n\n"
            "## Out of Scope\n\nNone.\n"
        )

    def _run(self, feature_dir, plan_rel, tmp_path):
        result_obj = {
            "schema_version": 1,
            "request_id": "run-0001",
            "worker": "implementation-planner",
            "status": "completed",
            "input_revision": {"workflow_blob": "8f17c04", "input_digest": "sha256:" + "a" * 64},
            "question_packet": None,
            "blocking_reason": None,
            "written_artifacts": [
                {"path": "feature-docs/example/tasks/task0001.md", "sha256": "sha256:" + "e" * 64},
            ],
            "workflow_patch": {
                "schema_version": 1,
                "patch_id": "create-plan-p0001",
                "base_input_digest": "sha256:" + "a" * 64,
                "base_workflow_blob": "8f17c04",
                "operation": "replace_planning",
                "tasks_patch": {
                    "mode": "replace_all",
                    "entries": {
                        "task0001": {
                            "title": "Something",
                            "plan": plan_rel,
                            "files": ["src/a.go"],
                            "skills": ["backend-impl"],
                            "domains": ["api-contract"],
                            "complexity": "medium",
                            "requirements": ["FR1"],
                            "initial_status": "pending",
                        }
                    },
                },
                "requirements_patch": None,
                "step_patches": [],
                "preserve": [],
            },
            "mode_echo": None,
            "payload": {"task_index": {"task0001": {"title": "Something"}}},
            "warnings": [],
            "report": "done",
        }
        envelope_obj = {
            "schema_version": 1,
            "request_id": "env-run-0001",
            "phase": "create-plan",
            "mode": "interactive",
            "input_revision": {"workflow_blob": "8f17c04", "input_digest": "sha256:" + "a" * 64},
            "write_policy": {"targets": []},
            "allowed_write_roots": ["feature-docs/example/"],
            "resolved_input_paths": {},
        }
        input_path = tmp_path / "input.json"
        envelope_path = tmp_path / "envelope.json"
        input_path.write_text(json.dumps(result_obj), encoding="utf-8")
        envelope_path.write_text(json.dumps(envelope_obj), encoding="utf-8")

        return run_cli(
            [
                "--kind", "worker-result",
                "--worker", "implementation-planner",
                "--input", str(input_path),
                "--input-envelope", str(envelope_path),
                "--feature-dir", str(feature_dir),
            ]
        )

    def test_plan_reached_through_a_symlink_segment_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            real_plan = tasks_dir / "_real_task0001.md"
            real_plan.write_text(self._valid_plan_text(), encoding="utf-8")
            symlink_plan = tasks_dir / "task0001.md"
            os.symlink(real_plan.name, symlink_plan)
            self.assertTrue(symlink_plan.is_symlink())

            result = self._run(feature_dir, "tasks/task0001.md", tmp_path)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("symlink", result.stdout.lower())

    def test_plan_without_a_symlink_is_still_read_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text(self._valid_plan_text(), encoding="utf-8")

            result = self._run(feature_dir, "tasks/task0001.md", tmp_path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_absolute_plan_path_is_rejected(self):
        # Asserts the SPECIFIC "task-plan-path" rejection code, not merely
        # exit 1 -- the pre-fix code also exits 1 for "/etc/passwd" on a
        # system where that file exists, but only by coincidence: pathlib's
        # `/` operator discards the left operand for an absolute right
        # operand, so it reads the real /etc/passwd and fails on a files-
        # mismatch ("task-plan-files-mismatch"), never recognizing the path
        # itself as unsafe.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text(self._valid_plan_text(), encoding="utf-8")

            result = self._run(feature_dir, "/etc/passwd", tmp_path)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("task-plan-path", result.stdout)

    def test_plan_path_escaping_feature_dir_via_parent_segments_is_rejected(self):
        # Same coincidence risk as the absolute-path case above: the OS
        # resolves `..` when the pre-fix code calls `.is_file()`, so it
        # would also happen to read the outside file and fail on a
        # files-mismatch rather than rejecting the path itself. Assert the
        # specific rejection code to discriminate the real fix.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text(self._valid_plan_text(), encoding="utf-8")
            (tmp_path / "outside.md").write_text("secret", encoding="utf-8")

            result = self._run(feature_dir, "../outside.md", tmp_path)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("task-plan-path", result.stdout)

    def test_oversized_plan_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text("x" * (VWO.MAX_PLAN_READ_BYTES + 1), encoding="utf-8")

            result = self._run(feature_dir, "tasks/task0001.md", tmp_path)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("task-plan-too-large", result.stdout)


class TestPathContainmentHelper(unittest.TestCase):
    """as6: direct unit tests of the pure segment-comparison helper,
    reproducing both measured escapes without going through the CLI."""

    def test_sibling_directory_is_not_contained(self):
        self.assertFalse(VWO.path_is_contained_in_root("feature-docs/example2/evil.md", "feature-docs/example"))

    def test_substring_name_is_not_contained(self):
        self.assertFalse(
            VWO.path_is_contained_in_root(
                "feature-docs/example/design/mockups-evil/x.html",
                "feature-docs/example/design/mockups",
            )
        )

    def test_nested_path_is_contained(self):
        self.assertTrue(VWO.path_is_contained_in_root("feature-docs/example/tasks/task0001.md", "feature-docs/example"))

    def test_traversal_path_is_rejected(self):
        self.assertFalse(VWO.path_is_contained_in_root("feature-docs/example/../../etc/passwd", "feature-docs/example"))

    def test_trailing_slash_root_still_matches(self):
        self.assertTrue(VWO.path_is_contained_in_root("feature-docs/example/IMPLEMENTATION.md", "feature-docs/example/"))


class TestWrittenArtifactsContainment(unittest.TestCase):
    """as6: fixture-driven end-to-end coverage. Segment-wise containment
    replaces the previous string-prefix comparison that admitted a
    sibling-directory escape and a substring-name escape; malformed
    entries and a non-list written_artifacts must produce a
    machine-readable error instead of a traceback / silent per-character
    iteration."""

    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "worker-result" / "designer" / case_name
        return run_cli(build_case_args("worker-result", "designer", case_dir))

    def test_sibling_directory_escape_is_rejected(self):
        result = self._run("invalid-written-artifact-sibling-directory-escape")
        self.assertEqual(result.returncode, 1)
        self.assertIn("write_policy", result.stdout)

    def test_traversal_escape_is_rejected(self):
        result = self._run("invalid-written-artifact-traversal")
        self.assertEqual(result.returncode, 1)

    def test_substring_name_escape_is_rejected(self):
        result = self._run("invalid-written-artifact-substring-name-escape")
        self.assertEqual(result.returncode, 1)
        self.assertIn("write_policy", result.stdout)

    def test_entry_missing_path_is_a_validation_error_not_a_traceback(self):
        result = self._run("invalid-written-artifact-missing-path")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["errors"])

    def test_non_list_written_artifacts_is_a_validation_error_not_a_crash(self):
        # Asserts the SPECIFIC "must be a list" error (exactly one), not
        # merely "some error occurred" -- the pre-fix code also exits 1
        # here, but only by coincidence (it silently iterates the string
        # per character, and each single-character "path" happens to fail
        # containment against every allowed root).
        result = self._run("invalid-written-artifacts-not-a-list")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["errors"]), 1)
        self.assertIn("must be a list", payload["errors"][0]["message"])

    def test_contained_path_in_allowed_root_is_accepted(self):
        result = self._run("valid-written-artifact-in-allowed-root")
        self.assertEqual(result.returncode, 0, result.stdout)


# ---------------------------------------------------------------------------
# as15 / AC-3: the domains vocabulary parser must stop at the domains block
# boundary the same way check-plugin-invariants.py does, so it never
# absorbs the complexity vocabulary comment that follows it.
# ---------------------------------------------------------------------------

class TestDomainsVocabularyParse(unittest.TestCase):
    def test_real_review_rules_yaml_yields_exactly_the_eight_documented_domains(self):
        vocab = VWO.load_domains_vocabulary(REPO_ROOT / "em-workflow" / "references")
        self.assertEqual(
            vocab,
            {
                "auth",
                "input-handling",
                "data-persistence",
                "external-io",
                "concurrency",
                "api-contract",
                "ui",
                "config-infra",
            },
        )

    def test_domain_declaring_a_complexity_value_is_rejected(self):
        case_dir = FIXTURES_ROOT / "workflow-patch" / "replace_planning" / "invalid-domain-is-complexity-value"
        result = run_cli(build_case_args("workflow-patch", "replace_planning", case_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("domains", result.stdout)


# ---------------------------------------------------------------------------
# as8 (validator half) / AC-5: a question whose category is spec-change,
# security or licensing must carry on_unanswered: block, so a worker cannot
# silently choose record_tbd/use_batch_policy and defeat the batch abort.
# ---------------------------------------------------------------------------

class TestQuestionCategoryForcesBlockingUnanswered(unittest.TestCase):
    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "question-packet" / "category-fail-closed" / case_name
        return run_cli(build_case_args("question-packet", "category-fail-closed", case_dir))

    def test_security_question_with_non_blocking_unanswered_is_rejected(self):
        result = self._run("invalid-security-record-tbd")
        self.assertEqual(result.returncode, 1)
        self.assertIn("on_unanswered", result.stdout)

    def test_security_question_with_blocking_unanswered_is_accepted(self):
        result = self._run("valid-security-blocking")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_all_three_fail_closed_categories_are_rejected_directly(self):
        for category in ("spec-change", "security", "license"):
            with self.subTest(category=category):
                q = {
                    "question_id": "q.test",
                    "gate_id": "gate.x",
                    "category": category,
                    "priority": "high",
                    "blocking": True,
                    "prompt": "p",
                    "header": "h",
                    "answer_mode": "freeform",
                    "options": [],
                    "why_needed": "w",
                    "on_unanswered": "record_tbd",
                }
                errors = VWO.validate_question(q, 0)
                messages = " ".join(e["message"] for e in errors)
                self.assertIn("on_unanswered", messages)

    def test_other_categories_do_not_force_blocking(self):
        q = {
            "question_id": "q.test",
            "gate_id": "gate.x",
            "category": "testing",
            "priority": "high",
            "blocking": False,
            "prompt": "p",
            "header": "h",
            "answer_mode": "freeform",
            "options": [],
            "why_needed": "w",
            "on_unanswered": "record_tbd",
        }
        errors = VWO.validate_question(q, 0)
        self.assertEqual(errors, [])

    def test_rejection_message_states_the_surviving_rationale(self):
        # batch-codex-autonomous-decisions/task0004 AC-2 (FR19): the
        # blocking-required category set and the on_unanswered != "block"
        # rejection are frozen (D5); only the message's parenthetical
        # rationale changes -- from justifying the check by the batch
        # abort, to the reason that survives it: a worker cannot choose
        # the non-blocking handling for these categories.
        q = {
            "question_id": "q.test",
            "gate_id": "gate.x",
            "category": "security",
            "priority": "high",
            "blocking": True,
            "prompt": "p",
            "header": "h",
            "answer_mode": "freeform",
            "options": [],
            "why_needed": "w",
            "on_unanswered": "record_tbd",
        }
        errors = VWO.validate_question(q, 0)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("cannot choose the non-blocking handling", messages)
        # Negative proof: the superseded rationale ("the batch abort") is
        # gone, not merely joined by the new wording.
        self.assertNotIn("disable the batch abort", messages)


# ---------------------------------------------------------------------------
# batch-codex-autonomous-decisions/task0004 AC-1 (FR18, FR21): question-
# packet-schema.md's on_unanswered: block constraint sentence stays
# verbatim; only its rationale is reworded -- "block" no longer means the
# batch run aborts, it means the question routes into the minimum-side-
# effect branch instead of letting a worker choose record_tbd or
# use_batch_policy for it. IMPLEMENTATION.md C1: the citation to
# references/question-resolution.md stays, and no condition of that rule
# is restated here.
# ---------------------------------------------------------------------------

class TestQuestionPacketSchemaBlockRationale(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = QUESTION_PACKET_SCHEMA_DOC_PATH.read_text(encoding="utf-8")
        cls.norm = re.sub(r"\s+", " ", cls.text)

    def test_constraint_sentence_is_verbatim(self):
        self.assertIn(
            "A question whose `category` is `spec-change`, `security`, or "
            "`license` must carry `on_unanswered: block` — a question in "
            "one of those categories can never be left to resolve as "
            "`record_tbd` or `use_batch_policy`.",
            self.norm,
        )

    def test_rationale_routes_into_the_minimum_side_effect_branch(self):
        self.assertIn(
            "routes the question into the minimum-side-effect branch",
            self.norm,
        )
        # Negative proof: the old implicit meaning of the constraint (that
        # "block" meant the batch run itself aborts) is gone.
        self.assertNotIn("the batch run will abort", self.norm)
        self.assertNotIn("disable the batch abort", self.norm)

    def test_resolution_time_rule_citation_retained(self):
        self.assertIn("references/question-resolution.md", self.text)
        self.assertIn(
            "states the resolution-time rule this constraint backs",
            self.norm,
        )


# ---------------------------------------------------------------------------
# batch-codex-autonomous-decisions/task0004 AC-3, AC-4 (FR20): a new
# question-packet fixture whose assumptions[] entry declares
# reversible: false is accepted directly by the validator. Its question's
# category is deliberately outside BLOCKING_REQUIRED_CATEGORIES, so the
# fixture exercises the irreversibility declaration rather than the
# category-forces-block rule already covered above. The corpus sweep
# (TestFixtureCorpusDataDriven) and the branch-coverage guard
# (TestFixtureCoverageValidAndInvalidPerBranch) already discover and run
# this fixture by directory-name convention -- no changes needed there.
# ---------------------------------------------------------------------------

class TestIrreversibleAssumptionFixtureAccepted(unittest.TestCase):
    CASE_DIR = (
        FIXTURES_ROOT
        / "question-packet"
        / "category-fail-closed"
        / "valid-irreversible-assumption-blocking"
    )

    def test_fixture_category_is_outside_the_blocking_required_set(self):
        data = json.loads((self.CASE_DIR / "input.json").read_text(encoding="utf-8"))
        categories = {q["category"] for q in data["questions"]}
        self.assertTrue(categories, "fixture must declare at least one question")
        self.assertFalse(
            categories & VWO.BLOCKING_REQUIRED_CATEGORIES,
            "fixture must not rely on a category that already forces block",
        )

    def test_fixture_declares_an_irreversible_assumption(self):
        data = json.loads((self.CASE_DIR / "input.json").read_text(encoding="utf-8"))
        question_ids = {q["question_id"] for q in data["questions"]}
        assumptions = data.get("assumptions") or []
        self.assertTrue(assumptions, "fixture must declare an assumptions[] entry")
        matching = [
            a
            for a in assumptions
            if a.get("reversible") is False
            and question_ids & set(a.get("related_question_ids") or [])
        ]
        self.assertTrue(
            matching,
            "fixture must carry an assumptions[] entry naming a question "
            "in this packet with reversible: false",
        )

    def test_fixture_is_accepted_directly(self):
        result = run_cli(
            build_case_args("question-packet", "category-fail-closed", self.CASE_DIR)
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# as21 / AC-6: worker-envelope.md forbids `payload` on the five non-completed
# statuses; the validator never enforced that.
# ---------------------------------------------------------------------------

class TestStatusPayloadExclusivity(unittest.TestCase):
    def test_blocked_with_nonempty_payload_is_rejected(self):
        case_dir = FIXTURES_ROOT / "worker-result" / "requirements-analyst-full" / "invalid-blocked-with-payload"
        result = run_cli(build_case_args("worker-result", "requirements-analyst-full", case_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("payload", result.stdout)

    def test_every_non_completed_status_forbids_payload_directly(self):
        base = dict(
            schema_version=1,
            worker="designer",
            request_id="run-0001",
            input_revision={"input_digest": "sha256:" + "a" * 64},
            question_packet=None,
            workflow_patch=None,
            mode_echo=None,
            written_artifacts=[],
        )
        for status in ("blocked", "invalid_input", "stale_input", "failed"):
            with self.subTest(status=status):
                data = dict(base, status=status, blocking_reason="x", payload={"design_summary": {}})
                errors = VWO.validate_worker_result(data, "designer")
                messages = " ".join(e["message"] for e in errors)
                self.assertIn("payload", messages)

    def test_completed_still_requires_a_non_empty_payload(self):
        data = dict(
            schema_version=1,
            worker="designer",
            request_id="run-0001",
            input_revision={"input_digest": "sha256:" + "a" * 64},
            question_packet=None,
            workflow_patch=None,
            mode_echo=None,
            written_artifacts=[],
            status="completed",
            blocking_reason=None,
            payload={},
        )
        errors = VWO.validate_worker_result(data, "designer")
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("non-empty payload", messages)


# ---------------------------------------------------------------------------
# as21 / AC-7: fixture coverage generated from WORKER_CAPABILITIES (the
# capability table) instead of checking that a status token merely appears
# SOMEWHERE under fixtures/worker-result/ (see
# TestFixtureBranchesDerivedFromDesignInput, which skips worker-result for
# exactly this reason).
# ---------------------------------------------------------------------------

class TestFixtureCoverageDerivedFromCapabilityTable(unittest.TestCase):
    @staticmethod
    def _group_dir_name(worker, mode_key):
        if worker == "requirements-analyst":
            # Fixture directories use kebab-case even though the mode_key
            # itself (WORKER_CAPABILITIES / mode_echo) is snake_case.
            return f"requirements-analyst-{mode_key.replace('_', '-')}"
        return worker

    @staticmethod
    def _valid_fixture_statuses(group_dir):
        """Maps each valid-* case dir under group_dir to the `status` read
        from its OWN input file -- not from the directory name -- so this
        cannot be satisfied by a differently-named worker's fixture."""
        statuses = set()
        if not group_dir.is_dir():
            return statuses
        for case_dir in sorted(group_dir.iterdir()):
            if not case_dir.is_dir() or not case_dir.name.startswith("valid-"):
                continue
            input_path = _companion(case_dir, "input")
            if input_path is None:
                continue
            data, _ = VWO.parse_yaml_text(input_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                statuses.add(data.get("status"))
        return statuses

    def test_every_worker_and_permitted_status_pair_has_a_valid_fixture(self):
        for worker, modes in VWO.WORKER_CAPABILITIES.items():
            for mode_key, caps in modes.items():
                group = self._group_dir_name(worker, mode_key)
                group_dir = FIXTURES_ROOT / "worker-result" / group
                statuses_present = self._valid_fixture_statuses(group_dir)
                for status in sorted(caps["allowed_statuses"]):
                    with self.subTest(worker=worker, mode=mode_key, status=status):
                        self.assertIn(
                            status,
                            statuses_present,
                            f"no valid-* fixture under {group_dir} declares status {status!r} "
                            f"(worker={worker!r}, mode={mode_key!r})",
                        )


# ---------------------------------------------------------------------------
# Edge case: a task-plan Files bullet with zero or two backtick-quoted paths
# ---------------------------------------------------------------------------

class TestTaskPlanFilesBulletBacktickEdgeCases(unittest.TestCase):
    def test_zero_backtick_tokens_in_a_bullet_is_rejected(self):
        case_dir = (
            FIXTURES_ROOT
            / "worker-result"
            / "implementation-planner"
            / "invalid-task-plan-bullet-zero-backticks"
        )
        result = run_cli(build_case_args("worker-result", "implementation-planner", case_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("backtick", result.stdout)

    def test_two_backtick_tokens_in_a_bullet_is_rejected(self):
        case_dir = (
            FIXTURES_ROOT
            / "worker-result"
            / "implementation-planner"
            / "invalid-task-plan-bullet-two-backticks"
        )
        result = run_cli(build_case_args("worker-result", "implementation-planner", case_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("backtick", result.stdout)


# ---------------------------------------------------------------------------
# rework_index / requirements_patch.tests_append cross-check (5.4.4)
#
# Direct unit test of the internal helper: the fixture corpus's rework-planner
# cases only exercise covered_by_existing (no new_scenarios), so this closes
# the gap for the "new_scenarios must also appear in requirements_patch
# tests_append" rule without adding more committed fixtures for one internal
# helper's branch.
# ---------------------------------------------------------------------------

def _write_verification_md(dir_path, scenario_ids):
    dir_path.mkdir(parents=True, exist_ok=True)
    lines = ["### Test Scenarios from SPEC.md", ""]
    lines.extend(f"- {tid}: something" for tid in scenario_ids)
    (dir_path / "VERIFICATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestReworkIndexNewScenariosRequireTestsAppend(unittest.TestCase):
    # Both cases now declare task0007 in tasks_patch.entries too: as5's
    # coverage fix (TestReworkIndexTaskCoverageDirect below) rejects a
    # rework_index entry naming a task tasks_patch never created, so these
    # workflow_patch fixtures must create the task they index to isolate
    # the tests_append cross-check this class exists to cover.
    def test_new_scenario_missing_from_tests_append_is_rejected(self):
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": ["TS-9"], "rationale": "new case"}}
        workflow_patch = {
            "tasks_patch": {"entries": {"task0007": {}}},
            "requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": []}}}},
        }
        # bs10 (round 2): this case now ALSO carries the "no --baseline-dir"
        # error (feature_dir/baseline_dir are both None), but assertIn only
        # requires "tests_append" to appear SOMEWHERE in the combined
        # messages, so the additional error does not affect this assertion.
        errors = VWO._validate_rework_index(rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("tests_append", messages)

    def test_new_scenario_present_in_tests_append_is_accepted(self):
        # bs10 (round 2): a real feature_dir/baseline_dir pair is now
        # required to isolate the tests_append cross-check this test exists
        # for -- without one, the baseline-requirement rule (see
        # TestReworkIndexRequiresBaselineForNewScenarios below) would itself
        # reject this case, which is not what this test is about.
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": ["TS-9"], "rationale": "new case"}}
        workflow_patch = {
            "tasks_patch": {"entries": {"task0007": {}}},
            "requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": ["TS-9"]}}}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(feature_dir, ["TS-9"])
            _write_verification_md(baseline_dir, [])
            errors = VWO._validate_rework_index(
                rework_index, workflow_patch, envelope=None, feature_dir=feature_dir, baseline_dir=baseline_dir
            )
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# bs10 (round 2, validator half) / AC-5: declaring new_scenarios without a
# --baseline-dir must be an error, not a silent degradation to "the
# identifier exists in the current document" (which the rework-planner
# itself wrote, so it proves nothing).
# ---------------------------------------------------------------------------

class TestReworkIndexRequiresBaselineForNewScenarios(unittest.TestCase):
    def _rework_index_and_patch(self):
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": ["TS-9"], "rationale": "new case"}}
        workflow_patch = {
            "tasks_patch": {"entries": {"task0007": {}}},
            "requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": ["TS-9"]}}}},
        }
        return rework_index, workflow_patch

    def test_new_scenarios_without_baseline_dir_is_rejected_even_with_feature_dir(self):
        rework_index, workflow_patch = self._rework_index_and_patch()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            _write_verification_md(feature_dir, ["TS-9"])
            errors = VWO._validate_rework_index(
                rework_index, workflow_patch, envelope=None, feature_dir=feature_dir, baseline_dir=None
            )
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("baseline", messages.lower())

    def test_new_scenarios_without_baseline_dir_is_rejected_with_no_feature_dir_either(self):
        rework_index, workflow_patch = self._rework_index_and_patch()
        errors = VWO._validate_rework_index(
            rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None
        )
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("baseline", messages.lower())

    def test_new_scenarios_with_baseline_dir_is_not_rejected_for_baseline_reasons(self):
        rework_index, workflow_patch = self._rework_index_and_patch()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(feature_dir, ["TS-9"])
            _write_verification_md(baseline_dir, [])
            errors = VWO._validate_rework_index(
                rework_index, workflow_patch, envelope=None, feature_dir=feature_dir, baseline_dir=baseline_dir
            )
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("baseline", messages.lower())

    def test_covered_by_existing_only_needs_no_baseline_dir(self):
        # A task that only claims covered_by_existing (no new_scenarios) has
        # nothing to verify against a baseline diff, so this rule must not
        # fire for it.
        rework_index = {"task0007": {"covered_by_existing": ["TS-3"], "new_scenarios": [], "rationale": "x"}}
        workflow_patch = {"tasks_patch": {"entries": {"task0007": {}}}}
        envelope = {"verification_index": {"TS-3": ["FR1"]}}
        errors = VWO._validate_rework_index(
            rework_index, workflow_patch, envelope=envelope, feature_dir=None, baseline_dir=None
        )
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# validator-scenario-id-format / task0001: VERIFICATION.md scenario IDs are
# recognized in both the TS-n form and the TSn form, as literal strings (no
# normalization between the forms). AC-1..AC-4 map to the tests below.
# ---------------------------------------------------------------------------

def _scenarios_section(*scenario_ids):
    lines = ["### Test Scenarios from SPEC.md", ""]
    lines.extend(f"| {tid} | something | ok | Unit |" for tid in scenario_ids)
    return "\n".join(lines) + "\n"


class TestScenarioIdExtractionAcceptsBothForms(unittest.TestCase):
    def test_ac1_hyphenless_ids_are_extracted(self):
        # AC-1 (TS-1): TS1, TS2 and TS13 in the section.
        ids = VWO.extract_verification_scenario_ids(_scenarios_section("TS1", "TS2", "TS13"))
        self.assertEqual(ids, {"TS1", "TS2", "TS13"})

    def test_ac1_multi_digit_hyphenless_id_is_not_truncated(self):
        # AC-1 (TS-3): a lone TS13 yields exactly TS13, never a TS1 made of
        # its leading digit.
        ids = VWO.extract_verification_scenario_ids(_scenarios_section("TS13"))
        self.assertEqual(ids, {"TS13"})

    def test_ac2_mixed_forms_keep_their_literal_values(self):
        # AC-2 (TS-2): one hyphenated and one hyphen-less ID, each in its
        # own literal form.
        ids = VWO.extract_verification_scenario_ids(_scenarios_section("TS-1", "TS2"))
        self.assertEqual(ids, {"TS-1", "TS2"})

    def test_hyphenated_ids_are_unchanged(self):
        # Shared Components contract: every ID the hyphenated-only rule
        # finds is still found with the same literal value (multi-digit
        # included, all consecutive digits consumed).
        ids = VWO.extract_verification_scenario_ids(_scenarios_section("TS-1", "TS-2", "TS-13"))
        self.assertEqual(ids, {"TS-1", "TS-2", "TS-13"})

    def test_same_number_in_both_forms_stays_two_distinct_ids(self):
        # AC-4 / D1: TS13 and TS-13 are distinct literal IDs.
        ids = VWO.extract_verification_scenario_ids(_scenarios_section("TS-13", "TS13"))
        self.assertEqual(ids, {"TS-13", "TS13"})

    def test_every_id_the_hyphenated_only_rule_finds_is_still_found(self):
        # Shared Components contract: widening the rule never loses a
        # hyphenated ID, with or without surrounding characters (no
        # word-boundary constraint is introduced).
        texts = [
            "TS-1",
            "see TS-1, TS-22 and TS-333.",
            "TS-1TS-2",
            "XTS-4 and TS-004",
            "TS-12abc",
            "TS--5 TS- TS-7",
            "(TS-8)[TS-9]",
        ]
        for text in texts:
            expected = set(re.findall(r"TS-\d+", text))
            section = "### Test Scenarios from SPEC.md\n\n| " + text + " |\n"
            with self.subTest(text=text):
                ids = VWO.extract_verification_scenario_ids(section)
                self.assertTrue(expected.issubset(ids), (expected, ids))


class TestReworkIndexNoveltyWithBothScenarioIdForms(unittest.TestCase):
    def _check(self, baseline_ids, current_ids, new_scenarios, tests_append):
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": new_scenarios, "rationale": "new case"}}
        workflow_patch = {
            "tasks_patch": {"entries": {"task0007": {}}},
            "requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": tests_append}}}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(feature_dir, current_ids)
            _write_verification_md(baseline_dir, baseline_ids)
            return VWO._validate_rework_index(
                rework_index, workflow_patch, envelope=None, feature_dir=feature_dir, baseline_dir=baseline_dir
            )

    def test_ac3_new_hyphenless_scenario_is_accepted(self):
        # AC-3 (TS-4): baseline TS1..TS12, current TS1..TS13, TS13 declared.
        baseline_ids = [f"TS{n}" for n in range(1, 13)]
        current_ids = [f"TS{n}" for n in range(1, 14)]
        errors = self._check(baseline_ids, current_ids, ["TS13"], ["TS13"])
        self.assertEqual(errors, [])

    def test_ac4_preexisting_hyphenless_scenario_is_rejected(self):
        # AC-4 (TS-5, TM-1): TS12 in both documents is not new.
        baseline_ids = [f"TS{n}" for n in range(1, 13)]
        current_ids = [f"TS{n}" for n in range(1, 13)]
        errors = self._check(baseline_ids, current_ids, ["TS12"], ["TS12"])
        messages = [e["message"] for e in errors]
        self.assertTrue(
            any("new_scenarios 'TS12' is not a new VERIFICATION.md scenario" in m for m in messages),
            messages,
        )

    def test_ac4_hyphenless_id_is_new_when_baseline_holds_only_the_hyphenated_form(self):
        # AC-4 (TS-6): the two forms are not collapsed into one ID.
        errors = self._check(["TS-13"], ["TS13"], ["TS13"], ["TS13"])
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("is not a new VERIFICATION.md scenario", messages)

    def test_preexisting_hyphenated_scenario_is_still_rejected(self):
        # TM-1 for the hyphenated form (unchanged behavior).
        errors = self._check(["TS-12"], ["TS-12"], ["TS-12"], ["TS-12"])
        messages = [e["message"] for e in errors]
        self.assertTrue(
            any("new_scenarios 'TS-12' is not a new VERIFICATION.md scenario" in m for m in messages),
            messages,
        )


# ---------------------------------------------------------------------------
# as5 / AC-2: rework_index completeness against tasks_patch.entries, in both
# directions, plus shared_contract_rationale as a required payload key.
# ---------------------------------------------------------------------------

class TestReworkIndexTaskCoverageDirect(unittest.TestCase):
    """Direct unit tests of the pure coverage-comparison helper: reproduces
    as5's exact measured regression ("replacing the valid-completed
    fixture's rework_index with {} while task0007 remains in tasks_patch
    still exits 0") and its mirror image."""

    def test_task_created_but_absent_from_index_is_rejected(self):
        workflow_patch = {"tasks_patch": {"entries": {"task0007": {}}}}
        errors = VWO._validate_rework_index({}, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("task0007", messages)
        self.assertIn("missing from rework_index", messages)

    def test_index_names_a_task_not_created_is_rejected(self):
        rework_index = {"task0099": {"covered_by_existing": [], "new_scenarios": [], "rationale": "x"}}
        workflow_patch = {"tasks_patch": {"entries": {}}}
        errors = VWO._validate_rework_index(rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("task0099", messages)
        self.assertIn("not created by tasks_patch", messages)

    def test_fully_covered_index_matching_created_tasks_is_accepted(self):
        rework_index = {"task0007": {"covered_by_existing": ["TS-3"], "new_scenarios": [], "rationale": "x"}}
        workflow_patch = {"tasks_patch": {"entries": {"task0007": {}}}}
        envelope = {"verification_index": {"TS-3": ["FR1"]}}
        errors = VWO._validate_rework_index(rework_index, workflow_patch, envelope=envelope, feature_dir=None, baseline_dir=None)
        self.assertEqual(errors, [])


class TestReworkIndexCoverage(unittest.TestCase):
    """Fixture-driven end-to-end coverage for the same rule via the CLI."""

    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "worker-result" / "rework-planner" / case_name
        return run_cli(build_case_args("worker-result", "rework-planner", case_dir))

    def test_created_task_missing_from_rework_index_is_rejected(self):
        result = self._run("invalid-rework-index-missing-task-entry")
        self.assertEqual(result.returncode, 1)
        self.assertIn("task0007", result.stdout)

    def test_rework_index_naming_an_uncreated_task_is_rejected(self):
        result = self._run("invalid-rework-index-unknown-task")
        self.assertEqual(result.returncode, 1)
        self.assertIn("task0007", result.stdout)

    def test_missing_shared_contract_rationale_is_rejected(self):
        result = self._run("invalid-missing-shared-contract-rationale")
        self.assertEqual(result.returncode, 1)
        self.assertIn("shared_contract_rationale", result.stdout)

    def test_valid_completed_with_full_coverage_and_rationale_passes(self):
        result = self._run("valid-completed")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_new_scenarios_without_baseline_dir_is_rejected_via_cli(self):
        result = self._run("invalid-new-scenarios-without-baseline")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("baseline", result.stdout.lower())


# ---------------------------------------------------------------------------
# bs2 (round 2, security/comprehensive) / AC-1, AC-2: gate registry binding.
# gate_id was previously checked for non-emptiness only, so any listed gate
# could be attached to any worker/phase/category/option combination. Both
# measured spoofs from feature-docs/agent-separation/reviews/round2.yaml are
# reproduced here (via fixtures run through the real CLI) and must now be
# rejected; a correctly-bound packet must still pass.
# ---------------------------------------------------------------------------

class TestGateRegistryBinding(unittest.TestCase):
    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "question-packet" / "gate-registry" / case_name
        return run_cli(build_case_args("question-packet", "gate-registry", case_dir))

    def test_worker_phase_and_category_spoof_is_rejected(self):
        # bs2 reproduction 1: "a rework-planner packet with phase rework,
        # category security and gate_id create-spec.design-step" -- measured
        # to exit 0 before this fix.
        result = self._run("invalid-worker-phase-category-spoof")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("registered to worker", messages)
        self.assertIn("registered to phase", messages)
        self.assertIn("requires category", messages)

    def test_category_laundered_through_unrelated_gate_is_rejected(self):
        # bs2 reproduction 2: "category spec-change and gate_id
        # create-plan.tbd-resolution" -- measured to exit 0 before this fix.
        result = self._run("invalid-category-mismatch-tbd-resolution")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("requires category 'tbd-resolution'", messages)

    def test_correctly_bound_gate_passes(self):
        result = self._run("valid-design-step-correct-binding")
        self.assertEqual(result.returncode, 0, result.stdout)


class TestGateRegistryDerivation(unittest.TestCase):
    """Direct unit tests of the derivation helpers, against the plugin's own
    real references/ directory (same precedent as
    TestDomainsVocabularyParse's real-file test above) -- these are the
    plugin's committed reference documents, not test/case-specific fixtures,
    so reading them directly is not a hermeticity violation."""

    REFERENCES_DIR = REPO_ROOT / "em-workflow" / "references"

    def test_category_derived_from_gate_id_suffix(self):
        self.assertEqual(VWO._category_for_gate_id("create-spec.design-step"), "design-step")
        self.assertEqual(VWO._category_for_gate_id("create-plan.tbd-resolution"), "tbd-resolution")
        # "requirement-clarification" is not a CATEGORY_VALUES member, so no
        # category is derived (the analyst contract states this gate covers
        # many categories, not one).
        self.assertIsNone(VWO._category_for_gate_id("create-spec.requirement-clarification"))
        self.assertIsNone(VWO._category_for_gate_id("not-a-gate-id"))

    def test_phase_derived_from_gate_id_prefix(self):
        self.assertEqual(VWO._phase_for_gate_id("create-spec.design-step"), "create-spec")
        self.assertEqual(VWO._phase_for_gate_id("create-plan.tbd-resolution"), "create-plan")
        # "design-system" is not a PHASE_VALUES member.
        self.assertIsNone(VWO._phase_for_gate_id("design-system.reclassify"))

    def test_analyst_contract_gates_are_worker_and_phase_attributed(self):
        registry = VWO.build_gate_registry(self.REFERENCES_DIR)
        entry = registry.get("create-spec.design-step")
        self.assertIsNotNone(entry, "expected create-spec.design-step in the derived registry")
        self.assertEqual(entry["worker"], "requirements-analyst")
        self.assertEqual(entry["phase"], "create-spec")
        self.assertEqual(entry["category"], "design-step")
        self.assertEqual(entry["required_option_id"], "decide_autonomously")

    def test_gate_with_no_contract_table_attribution_is_worker_unconstrained(self):
        # create-plan.tbd-resolution is listed in batch-policies.yaml but no
        # contract attributes it to a specific worker via a "## Gate
        # identifiers" table, so worker/phase/option stay unconstrained --
        # only its suffix-derived category is bound. This is also what
        # keeps the existing fixture corpus (which reuses this gate_id
        # across several different workers as a generic placeholder) green.
        registry = VWO.build_gate_registry(self.REFERENCES_DIR)
        entry = registry.get("create-plan.tbd-resolution")
        self.assertIsNotNone(entry)
        self.assertIsNone(entry["worker"])
        self.assertIsNone(entry["phase"])
        self.assertIsNone(entry["required_option_id"])
        self.assertEqual(entry["category"], "tbd-resolution")

    def test_missing_references_dir_yields_empty_registry(self):
        self.assertEqual(VWO.build_gate_registry(None), {})
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(VWO.build_gate_registry(Path(tmp) / "does-not-exist"), {})

    def test_rework_spec_change_is_registered_via_the_contract_section(self):
        # goal-vs-spec-divergence/task0024 AC-4: rework-planner-contract.md's
        # own "## Gate identifiers" section (tests/test_worker_contract_docs.
        # py pins that document's half) is what makes this entry exist --
        # this test asserts the registry entry itself, per the task's
        # Acceptance Criterion, rather than asserting the contract sentence.
        registry = VWO.build_gate_registry(self.REFERENCES_DIR)
        entry = registry.get("rework.spec-change")
        self.assertIsNotNone(
            entry, "expected rework.spec-change in the derived registry"
        )
        self.assertEqual(entry["worker"], "rework-planner")
        self.assertEqual(entry["category"], "spec-change")

    def test_rework_spec_change_carries_no_required_option_id(self):
        # D1: rework.spec-change stays intentionally unlisted in
        # batch-policies.yaml (no action: select gate), so it has no
        # option_id to require -- unlike create-spec.design-step.
        registry = VWO.build_gate_registry(self.REFERENCES_DIR)
        entry = registry.get("rework.spec-change")
        self.assertIsNotNone(entry)
        self.assertIsNone(entry["required_option_id"])


# ---------------------------------------------------------------------------
# goal-vs-spec-divergence/task0024 (AC-5): the gate registry's category
# binding, previously enforced in one direction only (gate_id -> category,
# TestGateRegistryBinding above), now also rejects the missing direction --
# category: spec-change paired with any gate_id other than
# rework.spec-change. Driven directly through validate_question (not a
# document scan, per Test Notes), against the plugin's own real registry so
# the fixture corpus's actual attribution (rework-planner-contract.md) is
# what proves the binding, not a synthetic stand-in.
# ---------------------------------------------------------------------------

class TestSpecChangeCategoryGateBidirectionalBinding(unittest.TestCase):
    REFERENCES_DIR = REPO_ROOT / "em-workflow" / "references"

    @classmethod
    def setUpClass(cls):
        cls.registry = VWO.build_gate_registry(cls.REFERENCES_DIR)

    @staticmethod
    def _question(gate_id, category):
        return {
            "question_id": "q.spec-change-binding",
            "gate_id": gate_id,
            "category": category,
            "priority": "high",
            "blocking": True,
            "prompt": "p",
            "header": "h",
            "answer_mode": "freeform",
            "options": [],
            "why_needed": "w",
            "on_unanswered": "block",
        }

    def _errors(self, gate_id, category):
        return VWO.validate_question(
            self._question(gate_id, category),
            0,
            gate_registry=self.registry,
            packet_phase="rework",
            packet_worker="rework-planner",
        )

    def test_spec_change_category_with_foreign_gate_id_is_rejected(self):
        # AC-5 direction 1: category: spec-change paired with a gate_id
        # that is not rework.spec-change -- the direction bs2's original
        # fix left open (Design section, Defect 1).
        errors = self._errors("create-spec.requirement-clarification", "spec-change")
        messages = " ".join(e["message"] for e in errors)
        self.assertIn(
            "category 'spec-change' requires gate_id to be one of "
            "['rework.spec-change']",
            messages,
        )

    def test_spec_change_category_with_wholly_unregistered_gate_id_is_rejected(
        self,
    ):
        # The exact reproduction from the Design section: a gate_id that is
        # neither on batch-policies.yaml's gate list nor attributed by any
        # contract -- previously silent (no registry entry to compare
        # against at all).
        errors = self._errors("not-a-registered-gate.foo", "spec-change")
        messages = " ".join(e["message"] for e in errors)
        self.assertIn(
            "category 'spec-change' requires gate_id to be one of "
            "['rework.spec-change']",
            messages,
        )

    def test_rework_spec_change_gate_id_with_foreign_category_is_rejected(self):
        # AC-5 direction 2: gate_id: rework.spec-change paired with a
        # category other than spec-change (the pre-existing forward-
        # direction check, re-asserted here alongside its new counterpart
        # for a single side-by-side proof of both directions).
        errors = self._errors("rework.spec-change", "other")
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("requires category 'spec-change'", messages)

    def test_correctly_paired_spec_change_question_has_no_binding_error(self):
        errors = self._errors("rework.spec-change", "spec-change")
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("requires gate_id", messages)
        self.assertNotIn("requires category", messages)

    def test_unrelated_category_is_unaffected_by_the_new_direction(self):
        # The new category -> gate_id direction must not fire for a
        # category that has no worker-attributed gate_id binding at all
        # (an as-yet-unconstrained category stays unconstrained -- see
        # _gate_ids_for_category's docstring).
        errors = self._errors("gate.unrelated", "other")
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("requires gate_id", messages)


# ---------------------------------------------------------------------------
# bs9 (round 2, comprehensive) / AC-3: every element of the patch entries,
# step patches, preserve list, worker runs, patches, packets, answers and
# resolved_input_cache must produce a machine-readable error for a malformed
# element, never a traceback. The two reproductions the round record names
# are covered end-to-end via fixtures (TestFixtureCorpusDataDriven already
# runs them); the remaining structures this finding also names are covered
# directly here against the pure validation functions.
# ---------------------------------------------------------------------------

class TestMalformedElementsProduceMachineReadableErrors(unittest.TestCase):
    def test_task_patch_entry_as_string_is_rejected_not_a_crash(self):
        # bs9 reproduction 1 (fixture-driven end-to-end coverage also exists
        # at workflow-patch/replace_planning/invalid-task-entry-not-a-mapping).
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "tasks_patch": {"mode": "replace_all", "entries": {"task0001": "not-a-mapping"}},
            "requirements_patch": None,
            "step_patches": [],
            "preserve": [],
        }
        errors = VWO.validate_workflow_patch(patch)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("must be a mapping", messages)

    def test_worker_run_as_string_is_rejected_not_a_crash(self):
        # bs9 reproduction 2 (fixture-driven end-to-end coverage also exists
        # at phase-state/completed/invalid-worker-run-not-a-mapping).
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=["not-a-mapping"], patches=[], packets={}, answers={},
            resolved_input_cache={},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("must be a mapping", messages)

    def test_step_patches_entry_as_string_is_rejected_not_a_crash(self):
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "tasks_patch": {"mode": "replace_all", "entries": {}},
            "requirements_patch": None,
            "step_patches": ["not-a-mapping"],
            "preserve": [],
        }
        errors = VWO.validate_workflow_patch(patch)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("step_patches[0] must be a mapping", messages)

    def test_preserve_entry_as_dict_is_rejected_not_a_crash(self):
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "tasks_patch": {"mode": "replace_all", "entries": {}},
            "requirements_patch": None,
            "step_patches": [],
            "preserve": [{"not": "a string"}],
        }
        errors = VWO.validate_workflow_patch(patch)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("preserve entry", messages)
        self.assertIn("must be a string", messages)

    def test_phase_state_patches_entry_as_string_is_rejected_not_a_crash(self):
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=[], patches=["not-a-mapping"], packets={}, answers={},
            resolved_input_cache={},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("patches[0] must be a mapping", messages)

    def test_phase_state_packet_value_as_string_is_rejected_not_a_crash(self):
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=[], patches=[], packets={"create-plan-q0001": "not-a-mapping"},
            answers={}, resolved_input_cache={},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("packets[create-plan-q0001] must be a mapping", messages)

    def test_phase_state_answer_value_as_string_is_rejected_not_a_crash(self):
        # bs9: "the answers list already has a guard that the equivalent
        # phase-state loop lacks" -- this is the phase-state loop.
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=[], patches=[], packets={},
            answers={"requirement.fr4.tbd-resolution": "not-a-mapping"}, resolved_input_cache={},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("answers[requirement.fr4.tbd-resolution] must be a mapping", messages)

    def test_resolved_input_cache_entry_as_string_is_rejected_not_a_crash(self):
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=[], patches=[], packets={}, answers={},
            resolved_input_cache={"design_system_candidates": "not-a-mapping"},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("resolved_input_cache[design_system_candidates] must be a mapping", messages)


# ---------------------------------------------------------------------------
# bs9 / AC-4: an unexpected exception (one the structural guards above do
# not specifically name) must exit 2 with a message on stderr, never exit 1
# with an empty stdout.
# ---------------------------------------------------------------------------

class TestUnexpectedExceptionExitsTwoWithMessage(unittest.TestCase):
    def test_non_mapping_workflow_during_dry_run_apply_exits_2_not_1_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            patch = {
                "schema_version": 1,
                "patch_id": "create-plan-p0001",
                "base_input_digest": "sha256:" + "a" * 64,
                "base_workflow_blob": "8f17c04",
                "operation": "replace_planning",
                "tasks_patch": {"mode": "replace_all", "entries": {}},
                "requirements_patch": None,
                "step_patches": [],
                "preserve": [],
            }
            input_path = tmp_path / "input.json"
            workflow_path = tmp_path / "workflow.json"
            digest_source_path = tmp_path / "digest-source.json"
            input_path.write_text(json.dumps(patch), encoding="utf-8")
            # A non-mapping workflow.yaml (a bare list) reaches
            # `workflow.get(...)` deep inside the dry-run-apply machinery,
            # which is not one of the structures bs9 explicitly names --
            # this demonstrates the exit-2 safety net catches genuinely
            # unanticipated shapes too, not just the enumerated ones.
            workflow_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            digest_source_path.write_text(json.dumps({"workflow_blob": "8f17c04"}), encoding="utf-8")

            result = run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "implementation-planner",
                    "--input", str(input_path),
                    "--workflow", str(workflow_path),
                    "--digest-source", str(digest_source_path),
                    "--dry-run-apply",
                ]
            )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip(), "expected a message on stderr")


# ---------------------------------------------------------------------------
# bs1 (round 2, comprehensive) / AC-6: the envelope's status table forbids
# `artifacts`, a `patch` and `blocking_reason` on `needs_user_input` -- it
# does NOT forbid `payload`, and the analyst contract requires
# `needs_user_input` to carry `payload.analysis_snapshot`. The payload
# prohibition added last round wrongly extended to this one status; it must
# still hold for the other four non-completed statuses.
# ---------------------------------------------------------------------------

class TestNeedsUserInputPayloadExemption(unittest.TestCase):
    def _base(self, status, payload):
        return dict(
            schema_version=1,
            worker="requirements-analyst",
            request_id="run-0001",
            input_revision={"input_digest": "sha256:" + "a" * 64},
            question_packet={
                "schema_version": 1,
                "packet_id": "create-spec-q0001",
                "phase": "create-spec",
                "worker": "requirements-analyst",
                "iteration": 1,
                "input_revision": {"input_digest": "sha256:" + "a" * 64},
                "questions": [
                    {
                        "question_id": "q.x",
                        "gate_id": "create-spec.requirement-clarification",
                        "category": "other",
                        "priority": "high",
                        "blocking": True,
                        "prompt": "p",
                        "header": "h",
                        "answer_mode": "freeform",
                        "options": [],
                        "why_needed": "w",
                        "on_unanswered": "record_tbd",
                    }
                ],
            },
            workflow_patch=None,
            mode_echo="full",
            written_artifacts=[],
            status=status,
            blocking_reason=None,
            payload=payload,
        )

    def test_needs_user_input_with_non_empty_payload_is_no_longer_rejected_for_payload(self):
        data = self._base("needs_user_input", {"analysis_snapshot": {"feature_name_candidate": "x"}})
        errors = VWO.validate_worker_result(data, "requirements-analyst")
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("forbids a non-empty payload", messages)

    def test_other_non_completed_statuses_still_forbid_payload(self):
        for status in ("blocked", "invalid_input", "stale_input", "failed"):
            with self.subTest(status=status):
                data = self._base(status, {"analysis_snapshot": {}})
                data["question_packet"] = None
                data["blocking_reason"] = "x"
                errors = VWO.validate_worker_result(data, "requirements-analyst")
                messages = " ".join(e["message"] for e in errors)
                self.assertIn("forbids a non-empty payload", messages)

    def test_fixture_analyst_needs_user_input_with_analysis_snapshot_passes(self):
        case_dir = (
            FIXTURES_ROOT / "worker-result" / "requirements-analyst-full"
            / "valid-needs-user-input-with-analysis-snapshot"
        )
        result = run_cli(build_case_args("worker-result", "requirements-analyst-full", case_dir))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# task0003 (feature-docs/create-plan-status-conflict): pins
# validate-worker-output.py's replace_all/create-plan permission check with
# regression fixtures. AC-3/AC-4/AC-5.
#
# task0016 (feature-docs/goal-vs-spec-divergence review round1 rework):
# extends the same class -- workflow-patch.md's `replace_all` permission
# conditions define two permitted paths (initial-planning, re-planning) and
# one rule common to both (no in_progress/failed task); this check now
# implements the path split instead of applying the task-status test
# independently of create-plan's status. AC-1/AC-2/AC-3/AC-4/AC-5/AC-6.
# ---------------------------------------------------------------------------

class TestReplaceAllCreatePlanEntryStatus(unittest.TestCase):
    """The validator's dry-run application (5.5.5 rule 5 /
    _validate_dry_run_apply) rejects replace_all unless the create-plan
    step's entry status is pending or needs_update, and unless the
    task-status rule for whichever of the two permitted paths applies is
    satisfied (workflow-patch.md "replace_all permission conditions"). This
    class pins that behaviour."""

    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "workflow-patch" / "replace_planning" / case_name
        return run_cli(build_case_args("workflow-patch", "replace_planning", case_dir))

    def test_create_plan_in_progress_rejected_with_replace_all_not_permitted(self):
        # AC-3
        result = self._run("invalid-replace-all-create-plan-in-progress")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertIn("replace-all-not-permitted", codes)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("in_progress", messages)

    def test_create_plan_in_progress_rejected_for_exactly_one_reason(self):
        # AC-5: removing the permission check from consideration, every
        # other validation layer is satisfied -- assert on the set of
        # reported error identifiers, not just their count, so the test
        # cannot pass because the fixture happens to be wrong in two ways.
        result = self._run("invalid-replace-all-create-plan-in-progress")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertEqual(codes, {"replace-all-not-permitted"})

    def test_create_plan_needs_update_passes(self):
        # AC-4
        result = self._run("valid-replace-all-create-plan-needs-update")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_create_plan_pending_passes(self):
        # AC-4 (Test Notes): the existing pending case is exercised today
        # only as part of TestDryRunApplyRejections's combined
        # both-operations sweep; this scenario-named assertion means a
        # future change to that combined test cannot silently drop the
        # pending branch.
        result = self._run("valid-dry-run-apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_replanning_reentry_with_merged_task_passes(self):
        # AC-1 (FR4, FR6): create-plan pending, re-entered via the
        # SPEC-change transition (spec_change record in --phase-state +
        # workflow.implement.base_commit already set), permits a merged
        # task -- the re-planning path drops the task-status test for
        # merged, keeping only rule 3 (in_progress/failed).
        result = self._run("valid-replace-all-replanning-merged-tasks")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_initial_planning_with_merged_task_still_rejected(self):
        # AC-2 (FR4): the same patch shape and workflow, but on the
        # initial-planning path (no re-entry signal), is still rejected --
        # a merged task never passes the empty-or-all-pending test.
        result = self._run("invalid-replace-all-initial-planning-merged-tasks")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertEqual(codes, {"replace-all-not-permitted"})

    def test_missing_reentry_signal_defaults_to_initial_planning(self):
        # AC-6: the same fixture as AC-2, from the fail-closed angle -- no
        # --phase-state is passed at all, so the check must never read the
        # merged task's pending create-plan status as a re-planning
        # re-entry. A narrower invocation (missing --phase-state) never
        # widens what replace_all permits.
        case_dir = FIXTURES_ROOT / "workflow-patch" / "replace_planning" / "invalid-replace-all-initial-planning-merged-tasks"
        self.assertFalse(
            (case_dir / "phase-state.json").exists(),
            "this fixture must exercise the missing-signal path -- a "
            "phase-state.json here would prove a different scenario",
        )
        result = self._run("invalid-replace-all-initial-planning-merged-tasks")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertIn("replace-all-not-permitted", codes)

    def test_after_implementation_started_rejected_on_replanning_path_too(self):
        # AC-3 (FR4): a replace_all received while a task is in_progress is
        # a protocol error on BOTH paths, not just initial-planning --
        # create-plan: needs_update (squarely the re-planning path) with an
        # in_progress task still fails, with exactly one error identifier.
        result = self._run("invalid-replace-all-after-implementation-started")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertEqual(codes, {"replace-all-not-permitted"})
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("in_progress", messages)


class TestReplanningMandatoryPreserveAndTaskIdAllocation(unittest.TestCase):
    """task0017 (goal-vs-spec-divergence, review round 2 rework), AC-3 /
    AC-5: on the re-planning path, `workflow.implement.base_commit` is
    mandatory in `preserve`, and new ids are allocated above the highest
    registered one.

    task0023 (review round 3, D10) re-grounds
    `test_drops_existing_registered_task_id_rejected` below on
    `tasks_patch.carried_task_ids` instead of `tasks_patch.entries` -- a
    re-planning `replace_all` no longer re-declares a registered id's body
    under `entries` at all (see `TestReplanningCarryOverEnforcement`
    below); omitting the id from `carried_task_ids` is what the
    `replace-all-drops-task` identifier now names."""

    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "workflow-patch" / "replace_planning" / case_name
        return run_cli(build_case_args("workflow-patch", "replace_planning", case_dir))

    def test_missing_base_commit_preserve_on_replanning_path_rejected(self):
        # AC-3
        result = self._run("invalid-replace-all-replanning-missing-base-commit-preserve")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("workflow.implement.base_commit", result.stdout)

    def test_missing_base_commit_preserve_rejected_for_exactly_one_reason(self):
        result = self._run("invalid-replace-all-replanning-missing-base-commit-preserve")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertEqual(codes, {"preserve"})

    def test_missing_base_commit_preserve_still_accepted_on_initial_planning_path(self):
        # AC-3: the same omission on the initial-planning path is still
        # accepted -- valid-dry-run-apply already pins exactly this (its
        # own preserve is [], and it is on the initial-planning path).
        result = self._run("valid-dry-run-apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_corrected_replanning_merged_tasks_fixture_passes(self):
        # AC-4: the corrected valid- fixture -- base_commit in preserve, a
        # rework-shaped phase-state.json, and task ids that do not re-issue
        # any id its workflow.json already registers.
        result = self._run("valid-replace-all-replanning-merged-tasks")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_drops_existing_registered_task_id_rejected(self):
        # AC-5
        result = self._run("invalid-replace-all-replanning-drops-existing-task")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertEqual(codes, {"replace-all-drops-task"})
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("task0009", messages)

    def test_spent_replan_authorization_record_is_rejected(self):
        # task0022 (review round 3, AC-6): the same corrected patch shape,
        # but the spec_change record's re-planning authorization is already
        # spent (`replan_authorized: false`, `consumed: true`) -- fails
        # closed to the initial-planning path's rule, and the merged task
        # fails that rule's floor. Supersedes the pre-task0022
        # `invalid-replace-all-replanning-consumed-spec-change` fixture,
        # which pinned a reading (`consumed: true` alone forces rejection)
        # this task removes -- see TestReentryOrdering below for the
        # `consumed: true` + unspent-authorization acceptance case.
        result = self._run("invalid-replace-all-replan-authorization-spent")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertEqual(codes, {"replace-all-not-permitted"})


class TestReplanningCarryOverEnforcement(unittest.TestCase):
    """task0023 (goal-vs-spec-divergence, review round 3), AC-3: the
    validator's carry-over declaration checks (workflow-patch.md's
    "Re-planning task-id allocation" section / D10) -- three independently
    reported rejections, exercised each by its own fixture so a case
    proving one never rides along with the other two:

    - `entries` naming an id already registered in `workflow.yaml`
      (`replace-all-entry-for-registered-id`), pinned here.
    - `carried_task_ids` omitting a registered id
      (`replace-all-drops-task`), already pinned by
      `TestReplanningMandatoryPreserveAndTaskIdAllocation.
      test_drops_existing_registered_task_id_rejected` above -- re-grounded
      on `carried_task_ids` rather than `entries` by this task's fixture
      edit, not re-tested a second time here.
    - a new id in `entries` at or below the high-water mark
      (`replace-all-task-id-reused`) -- unchanged behaviour, no dedicated
      fixture in this group; covered structurally by the max-id computation
      carried over unmodified from task0017.
    """

    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "workflow-patch" / "replace_planning" / case_name
        return run_cli(build_case_args("workflow-patch", "replace_planning", case_dir))

    def test_entry_for_registered_id_rejected(self):
        result = self._run("invalid-replace-all-replanning-entry-for-registered-id")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertIn("replace-all-entry-for-registered-id", codes)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("task0009", messages)

    def test_entry_for_registered_id_rejected_for_exactly_one_reason(self):
        # Test Notes: each of AC-3's three rejections must report exactly
        # one error identifier -- a fixture that also trips the drop check
        # or the reused-id check would not isolate the finding this AC
        # names.
        result = self._run("invalid-replace-all-replanning-entry-for-registered-id")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertEqual(codes, {"replace-all-entry-for-registered-id"})

    def test_carried_task_ids_field_present_and_correct_in_the_new_fixture(self):
        # Sanity check on the fixture itself: carried_task_ids DOES list the
        # registered id (so the failure is isolated to the entries-side
        # re-declaration, not to an incidentally-also-missing carry).
        case_dir = FIXTURES_ROOT / "workflow-patch" / "replace_planning" / "invalid-replace-all-replanning-entry-for-registered-id"
        input_data = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
        tasks_patch = input_data["tasks_patch"]
        self.assertEqual(tasks_patch["carried_task_ids"], ["task0009"])
        self.assertIn("task0009", tasks_patch["entries"])


class TestReplanningReentrySignalHelper(unittest.TestCase):
    """Direct unit tests of workflow_replace_all_spec_change_reentry (the
    pure helper backing the re-planning path's second entry form), covering
    each required condition independently -- fixture-driven CLI coverage
    above exercises the combined check, not each condition in isolation.

    task0017 (review round 2 rework): the helper's contract widened -- it no
    longer accepts ANY mapping carrying a `spec_change` record as proof of
    re-entry (that was round 1's own bug: the test harness handed it a
    rework-shaped mapping directly, and that mapping carried no `phase` key
    at all, so nothing in the suite noticed create-plan-phase.md's canonical
    invocation could never actually produce it). A rework-shaped mapping
    must now also declare `phase: rework` and a `feature` matching the
    workflow's own, and its `spec_change` record must carry every
    mandatory phase-state.md field. Every pre-existing test below now
    supplies `phase`/`feature` so it continues to prove the condition it
    names, rather than accidentally exercising the now-mandatory
    phase/feature check instead.

    task0022 (review round 3, consumed-flag-split): the helper's
    re-planning-authorization judgement moved from `consumed` to the
    independent `replan_authorized` flag (`references/phase-state.md`'s
    `spec_change` flag pair) -- `consumed` is never consulted here any
    more. `_rework_phase_state`'s default record now carries
    `replan_authorized: True` (an unspent authorization) so every
    pre-existing test below keeps proving the condition it names rather
    than failing on the newly-mandatory field; the two `consumed`-keyed
    tests this superseded are renamed and re-pointed at
    `replan_authorized` below."""

    FEATURE = "example"

    def _workflow(self, base_commit):
        step = {"id": "implement", "status": "pending"}
        if base_commit is not None:
            step["base_commit"] = base_commit
        return {
            "feature": self.FEATURE,
            "workflow": [{"id": "create-plan", "status": "pending"}, step],
        }

    def _rework_phase_state(self, **overrides):
        base = {
            "phase": "rework",
            "feature": self.FEATURE,
            "spec_change": {
                "reason": "x",
                "origin_kind": "review",
                "origin_id": "abc",
                "recorded_at_commit": "deadbeef",
                "consumed": False,
                "replan_authorized": True,
            },
        }
        base.update(overrides)
        return base

    def test_no_phase_state_is_not_a_reentry(self):
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), None)
        )

    def test_phase_state_without_spec_change_record_is_not_a_reentry(self):
        phase_state = {"phase": "rework", "feature": self.FEATURE}
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    def test_spec_change_record_without_base_commit_is_not_a_reentry(self):
        phase_state = self._rework_phase_state()
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow(None), phase_state)
        )

    def test_spec_change_record_with_base_commit_is_a_reentry(self):
        phase_state = self._rework_phase_state()
        self.assertTrue(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    # --- task0017 (AC-2): the conditions this round's contract adds -------

    def test_missing_phase_key_is_not_a_reentry(self):
        phase_state = self._rework_phase_state()
        del phase_state["phase"]
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    def test_phase_other_than_rework_is_not_a_reentry(self):
        phase_state = self._rework_phase_state(phase="create-plan")
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    def test_feature_mismatch_is_not_a_reentry(self):
        phase_state = self._rework_phase_state(feature="other-feature")
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    def test_spec_change_missing_mandatory_field_is_not_a_reentry(self):
        for missing in ("reason", "origin_kind", "origin_id", "recorded_at_commit"):
            with self.subTest(missing=missing):
                phase_state = self._rework_phase_state()
                del phase_state["spec_change"][missing]
                self.assertFalse(
                    VWO.workflow_replace_all_spec_change_reentry(
                        self._workflow("deadbeef"), phase_state
                    )
                )

    def test_missing_consumed_field_does_not_block_reentry(self):
        # task0022 (review round 3, consumed-flag-split): `consumed` is no
        # longer consulted by this helper at all -- its presence or
        # absence must not affect the outcome. Supersedes the pre-task0022
        # test_spec_change_missing_consumed_field_is_not_a_reentry, which
        # pinned exactly the reading this task removes.
        phase_state = self._rework_phase_state()
        del phase_state["spec_change"]["consumed"]
        self.assertTrue(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    def test_consumed_true_no_longer_blocks_reentry(self):
        # task0022 (review round 3, AC-3/AC-4): this is exactly the
        # ordering the SPEC-change transition -> create-spec dispatch ->
        # create-plan re-entry sequence always produces (create-plan is
        # never reached before the record is marked consumed) -- FR6
        # requires it to still be a re-planning re-entry when the
        # authorization is unspent. Supersedes the pre-task0022
        # test_consumed_true_is_not_a_reentry, which pinned exactly the
        # reading this task removes. See TestReentryOrdering in
        # test_spec_change_replan_authorization.py for the full sequential
        # (not merely state-final) proof.
        phase_state = self._rework_phase_state()
        phase_state["spec_change"]["consumed"] = True
        self.assertTrue(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    def test_replan_authorized_missing_is_not_a_reentry(self):
        phase_state = self._rework_phase_state()
        del phase_state["spec_change"]["replan_authorized"]
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    def test_replan_authorized_false_is_not_a_reentry(self):
        # The spent-authorization direction (AC-3): the mirror of
        # test_spec_change_record_with_base_commit_is_a_reentry above.
        phase_state = self._rework_phase_state()
        phase_state["spec_change"]["replan_authorized"] = False
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow("deadbeef"), phase_state)
        )

    def test_replan_authorized_non_boolean_is_not_a_reentry(self):
        for bad_value in ("true", 1, 0, None, []):
            with self.subTest(bad_value=bad_value):
                phase_state = self._rework_phase_state()
                phase_state["spec_change"]["replan_authorized"] = bad_value
                self.assertFalse(
                    VWO.workflow_replace_all_spec_change_reentry(
                        self._workflow("deadbeef"), phase_state
                    )
                )

    # --- task0017 (AC-1): {feature-dir}/phase-state/rework.yaml is an
    # equivalent source, resolved even when --phase-state carries a
    # DIFFERENT phase's state (create-plan.yaml, exactly the canonical
    # invocation's own form). Full CLI-level coverage of the canonical
    # invocation lives in TestCanonicalReentryInvocation below; these are
    # direct unit tests of the resolution helper itself.

    def test_feature_dir_rework_yaml_is_an_equivalent_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            feature_dir = Path(tmp)
            phase_state_dir = feature_dir / "phase-state"
            phase_state_dir.mkdir()
            (phase_state_dir / "rework.yaml").write_text(
                "phase: rework\n"
                f"feature: {self.FEATURE}\n"
                "spec_change:\n"
                "  reason: x\n"
                "  origin_kind: review\n"
                "  origin_id: abc\n"
                "  recorded_at_commit: deadbeef\n"
                "  consumed: false\n"
                "  replan_authorized: true\n",
                encoding="utf-8",
            )
            # --phase-state carries the CREATE-PLAN phase's own state (the
            # canonical form) -- no spec_change here at all.
            create_plan_phase_state = {"phase": "create-plan", "feature": self.FEATURE}
            self.assertTrue(
                VWO.workflow_replace_all_spec_change_reentry(
                    self._workflow("deadbeef"), create_plan_phase_state, feature_dir=feature_dir
                )
            )

    def test_missing_feature_dir_rework_yaml_falls_back_to_initial_planning(self):
        with tempfile.TemporaryDirectory() as tmp:
            feature_dir = Path(tmp)
            create_plan_phase_state = {"phase": "create-plan", "feature": self.FEATURE}
            self.assertFalse(
                VWO.workflow_replace_all_spec_change_reentry(
                    self._workflow("deadbeef"), create_plan_phase_state, feature_dir=feature_dir
                )
            )


# ---------------------------------------------------------------------------
# task0017 (review round 2 rework) / AC-1 (FR6): the re-entry signal must be
# recognized from the EXACT invocation create-plan-phase.md's canonical form
# documents -- --feature-dir plus --phase-state pointing at the CREATE-PLAN
# phase's own state file (never rework.yaml itself). A test that instead
# passes the rework file directly as --phase-state proves the OLD wiring,
# not the new one -- kept in TestReplanningReentrySignalHelper above as an
# additional equivalence case, never as this AC's own proof. This class
# drives the real CLI, end to end, through --dry-run-apply.
# ---------------------------------------------------------------------------

class TestCanonicalReentryInvocation(unittest.TestCase):
    FEATURE = "example"

    def _workflow_obj(self, base_commit="deadbeef", task_status="merged"):
        return {
            "feature": self.FEATURE,
            "project": {"license": "MIT"},
            "requirements": {"FR1": {"status": "ok", "tasks": [], "tests": [], "title": "x"}},
            "schema_version": 1,
            "tasks": {
                "task0009": {
                    "branch": "em-workflow/example/task0009",
                    "complexity": "low",
                    "domains": [],
                    "files": ["x.go"],
                    "notes": None,
                    "plan": "tasks/task0009.md",
                    "requirements": ["FR1"],
                    "skills": [],
                    "status": task_status,
                    "title": "existing",
                }
            },
            "workflow": [
                {"completed_at_commit": "aaa", "id": "create-spec", "status": "completed"},
                {"id": "design", "skipped_reason": "no UI", "status": "skipped"},
                {"id": "create-plan", "status": "pending"},
                {"base_commit": base_commit, "id": "implement", "status": "pending"},
                {"id": "review", "status": "pending"},
                {"id": "verify", "status": "pending"},
                {"id": "retrospect", "status": "pending"},
            ],
        }

    def _patch_obj(self, base_input_digest):
        # task0023 (goal-vs-spec-divergence, review round 3, D10): a
        # re-planning replace_all carries an already-registered id
        # (task0009) in tasks_patch.carried_task_ids rather than
        # re-declaring its body under tasks_patch.entries -- entries names
        # only the genuinely new task0010.
        return {
            "base_input_digest": base_input_digest,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "patch_id": "create-plan-p0001",
            "preserve": ["workflow.implement.base_commit"],
            "requirements_patch": None,
            "schema_version": 1,
            "step_patches": [],
            "tasks_patch": {
                "carried_task_ids": ["task0009"],
                "entries": {
                    "task0010": {
                        "complexity": "medium",
                        "domains": ["api-contract"],
                        "files": ["src/api/register.go"],
                        "initial_status": "pending",
                        "plan": "tasks/task0010.md",
                        "requirements": ["FR1"],
                        "skills": ["backend-impl"],
                        "title": "User registration API",
                    },
                },
                "mode": "replace_all",
            },
        }

    def _digest_source_obj(self):
        return {
            "answers_digest": "sha256:" + "2" * 64,
            "digest_inputs": {},
            "mode": "interactive",
            "value_inputs": {"task_description": None},
            "worker": "implementation-planner",
            "workflow_blob": "8f17c04",
            "write_policy_digest": "sha256:" + "3" * 64,
        }

    def _write(self, path, obj):
        path.write_text(json.dumps(obj), encoding="utf-8")

    def _run_canonical(self, tmp_path, *, rework_yaml_present):
        # The canonical invocation, verbatim: --feature-dir plus
        # --phase-state pointing at the CREATE-PLAN phase's own state file
        # (create-plan-phase.md never passes rework.yaml as --phase-state).
        feature_dir = tmp_path / "feature-dir"
        (feature_dir / "phase-state").mkdir(parents=True)
        if rework_yaml_present:
            (feature_dir / "phase-state" / "rework.yaml").write_text(
                "phase: rework\n"
                f"feature: {self.FEATURE}\n"
                "spec_change:\n"
                "  reason: x\n"
                "  origin_kind: review\n"
                "  origin_id: abc\n"
                "  recorded_at_commit: deadbeef\n"
                "  consumed: false\n"
                "  replan_authorized: true\n",
                encoding="utf-8",
            )

        create_plan_yaml = tmp_path / "create-plan.yaml"
        create_plan_yaml.write_text(
            f"phase: create-plan\nfeature: {self.FEATURE}\n", encoding="utf-8"
        )

        digest_source = self._digest_source_obj()
        base_input_digest = VWO.normalize_json_sha256(digest_source)

        input_path = tmp_path / "input.json"
        workflow_path = tmp_path / "workflow.json"
        digest_source_path = tmp_path / "digest-source.json"
        self._write(input_path, self._patch_obj(base_input_digest))
        self._write(workflow_path, self._workflow_obj())
        self._write(digest_source_path, digest_source)

        return run_cli(
            [
                "--kind", "workflow-patch",
                "--worker", "implementation-planner",
                "--input", str(input_path),
                "--workflow", str(workflow_path),
                "--digest-source", str(digest_source_path),
                "--feature-dir", str(feature_dir),
                "--phase-state", str(create_plan_yaml),
                "--dry-run-apply",
            ]
        )

    def test_canonical_invocation_form_accepts_merged_task_reentry(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_canonical(Path(tmp), rework_yaml_present=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_feature_dir_rework_yaml_is_rejected_under_the_same_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_canonical(Path(tmp), rework_yaml_present=False)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            codes = {e["code"] for e in payload["errors"]}
            self.assertIn("replace-all-not-permitted", codes)

    def test_rework_file_passed_directly_as_phase_state_is_an_equivalence_case_not_this_ac(self):
        # Test Notes: proves the OLD wiring path still works, as an
        # EQUIVALENT source (a caller that already has the rework file open
        # is not forced to re-supply it) -- kept as an additional case, not
        # as AC-1's own proof (the two tests above are).
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rework_yaml = tmp_path / "rework.yaml"
            rework_yaml.write_text(
                "phase: rework\n"
                f"feature: {self.FEATURE}\n"
                "spec_change:\n"
                "  reason: x\n"
                "  origin_kind: review\n"
                "  origin_id: abc\n"
                "  recorded_at_commit: deadbeef\n"
                "  consumed: false\n"
                "  replan_authorized: true\n",
                encoding="utf-8",
            )
            digest_source = self._digest_source_obj()
            base_input_digest = VWO.normalize_json_sha256(digest_source)

            input_path = tmp_path / "input.json"
            workflow_path = tmp_path / "workflow.json"
            digest_source_path = tmp_path / "digest-source.json"
            self._write(input_path, self._patch_obj(base_input_digest))
            self._write(workflow_path, self._workflow_obj())
            self._write(digest_source_path, digest_source)

            result = run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "implementation-planner",
                    "--input", str(input_path),
                    "--workflow", str(workflow_path),
                    "--digest-source", str(digest_source_path),
                    "--phase-state", str(rework_yaml),
                    "--dry-run-apply",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# task0025 AC-2: the batch-classification-gate answer source.
#
# References/question-resolution.md's Classification gate (Outcome step) and
# references/question-packet-schema.md's `source` vocabulary (the SSOT for
# this value) are covered in tests/test_gate_outcome_packet_lifecycle.py,
# alongside the cross-document agreement check between that vocabulary and
# ANSWER_SOURCE_VALUES below (C4: this module owns the validator, not the
# schema document). This class owns only the validator's own half: the
# constant carries the value, and a real answer object using it validates.
# ---------------------------------------------------------------------------

class TestGateResolvedAnswerSource(unittest.TestCase):
    def test_batch_classification_gate_is_in_answer_source_values(self):
        self.assertIn("batch-classification-gate", VWO.ANSWER_SOURCE_VALUES)

    def test_answer_object_using_batch_classification_gate_validates(self):
        answer = {
            "question_id": "q.spec-change",
            "packet_id": "rework-q0001",
            "answered_at": "2026-08-24T10:00:00+09:00",
            "source": "batch-classification-gate",
            "answer_mode": "freeform",
            "selected_option_ids": [],
            "freeform": "proceed: spec gap confirmed against FR14",
            "normalized_answer": "proceed",
            "resolution_note": (
                "classification gate verdict: spec_gap; see the "
                "rework.yaml classification record"
            ),
        }
        errors = VWO.validate_answer(answer)
        self.assertEqual(errors, [], errors)

    def test_unrecognized_source_value_is_still_rejected(self):
        # Non-vacuity guard: proves the check above is not vacuously
        # passing on a validator that accepts any string as `source`.
        answer = {
            "question_id": "q.spec-change",
            "packet_id": "rework-q0001",
            "answered_at": "2026-08-24T10:00:00+09:00",
            "source": "not-a-real-source",
            "answer_mode": "freeform",
            "selected_option_ids": [],
            "freeform": "x",
            "normalized_answer": "x",
            "resolution_note": None,
        }
        errors = VWO.validate_answer(answer)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("source", messages)


# ---------------------------------------------------------------------------
# rework-contract-drift/task0004 AC-6 (FR6): origin_kind's closed
# vocabulary is enforced by the validator.
# ---------------------------------------------------------------------------

class TestOriginKindVocabulary(unittest.TestCase):
    FEATURE = "example"

    def _workflow(self, base_commit="deadbeef"):
        return {
            "feature": self.FEATURE,
            "workflow": [
                {"id": "create-plan", "status": "pending"},
                {"id": "implement", "status": "pending", "base_commit": base_commit},
            ],
        }

    def _phase_state(self, origin_kind):
        return {
            "phase": "rework",
            "feature": self.FEATURE,
            "spec_change": {
                "reason": "x",
                "origin_kind": origin_kind,
                "origin_id": "abc",
                "recorded_at_commit": "deadbeef",
                "replan_authorized": True,
            },
        }

    def test_review_origin_kind_accepted(self):
        self.assertTrue(
            VWO.workflow_replace_all_spec_change_reentry(
                self._workflow(), self._phase_state("review")
            )
        )

    def test_verify_origin_kind_accepted(self):
        self.assertTrue(
            VWO.workflow_replace_all_spec_change_reentry(
                self._workflow(), self._phase_state("verify")
            )
        )

    def test_out_of_vocabulary_origin_kind_rejected(self):
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(
                self._workflow(), self._phase_state("audit")
            )
        )

    def test_empty_origin_kind_rejected(self):
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(
                self._workflow(), self._phase_state("")
            )
        )


# ---------------------------------------------------------------------------
# rework-contract-drift/task0004 AC-6 (FR3 validator half), scoped by
# rework-contract-drift/task0008 (review round1 rework, FR3, NFR1, NFR2,
# D11): a `workflow.yaml` verify-step `failed_items[]` entry's `category`
# is rejected when missing, empty, or out of the seven-value vocabulary
# (IMPLEMENTATION.md Shared Components), and accepted for each of the
# seven values -- enforced by `_validate_verify_failed_items_categories`,
# wired into `validate_workflow_patch` unconditional on --dry-run-apply,
# but ONLY for the entries of a verify step the patch targets via
# `step_patches` (workflow-schema.md's pre-change compatibility rule): a
# pre-existing entry outside that reach -- one a worker's step patch has no
# way to repair -- contributes no error.
# ---------------------------------------------------------------------------

class TestFailedItemCategoryVocabulary(unittest.TestCase):
    SEVEN_VALUES = (
        "comprehensive",
        "spec",
        "security",
        "performance",
        "architecture",
        "license",
        "unknown",
    )

    def _workflow(self, category):
        failed_item = {"id": "TS-1"}
        if category is not _OMIT:
            failed_item["category"] = category
        return {
            "feature": "example",
            "workflow": [
                {
                    "id": "verify",
                    "status": "pending",
                    "failed_items": [failed_item],
                },
            ],
        }

    def _patch(self, *, targets_verify):
        step_patches = [{"step_id": "verify"}] if targets_verify else []
        return {"step_patches": step_patches}

    def _errors(self, category, *, targets_verify=True):
        return VWO._validate_verify_failed_items_categories(
            self._workflow(category), self._patch(targets_verify=targets_verify)
        )

    def test_each_of_the_seven_values_accepted(self):
        for value in self.SEVEN_VALUES:
            with self.subTest(category=value):
                self.assertEqual(self._errors(value), [])

    def test_missing_category_rejected(self):
        errors = self._errors(_OMIT)
        self.assertTrue(errors)
        self.assertIn("category", errors[0]["message"])

    def test_empty_category_rejected(self):
        errors = self._errors("")
        self.assertTrue(errors)

    def test_out_of_vocabulary_category_rejected(self):
        errors = self._errors("not-a-real-category")
        self.assertTrue(errors)

    def test_no_verify_step_yields_no_errors(self):
        workflow = {"feature": "example", "workflow": []}
        self.assertEqual(
            VWO._validate_verify_failed_items_categories(
                workflow, self._patch(targets_verify=True)
            ),
            [],
        )

    def test_no_failed_items_key_yields_no_errors(self):
        workflow = {
            "feature": "example",
            "workflow": [{"id": "verify", "status": "pending"}],
        }
        self.assertEqual(
            VWO._validate_verify_failed_items_categories(
                workflow, self._patch(targets_verify=True)
            ),
            [],
        )

    def test_untargeted_verify_step_yields_no_category_error(self):
        # task0008 AC-6 (pre-change case): a patch touching no verify step
        # produces no error even over a non-conforming (here: entirely
        # missing) category -- the party that would receive the rejection
        # has no way to repair a pre-existing entry.
        self.assertEqual(
            self._errors(_OMIT, targets_verify=False), []
        )

    def test_targeted_verify_step_retains_the_category_check(self):
        # task0008 AC-6 (retained-teeth case): a patch that DOES target the
        # verify step still rejects a non-conforming entry within it.
        errors = self._errors(_OMIT, targets_verify=True)
        self.assertTrue(errors)
        self.assertIn("category", errors[0]["message"])

    def test_verify_step_target_among_other_step_patches_still_scopes_in(self):
        # A patch touching several steps, one of which is verify, still
        # reaches the verify step's entries.
        patch = {
            "step_patches": [
                {"step_id": "implement"},
                {"step_id": "verify"},
            ]
        }
        errors = VWO._validate_verify_failed_items_categories(
            self._workflow(_OMIT), patch
        )
        self.assertTrue(errors)

    def test_wired_into_validate_workflow_patch_unconditional_on_dry_run(
        self,
    ):
        # AC-6: the check runs on the invocation path that already reads
        # --workflow, not only under --dry-run-apply. task0008: the patch
        # now targets the verify step, exercising the new scope instead of
        # the removed unconditional one.
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "append_rework",
            "tasks_patch": {
                "mode": "append",
                "expected_next_task_id": "task0001",
                "entries": {},
            },
            "step_patches": [{"step_id": "verify"}],
            "preserve": ["workflow.implement.base_commit"],
        }
        errors = VWO.validate_workflow_patch(
            patch,
            workflow=self._workflow("not-a-real-category"),
            dry_run=False,
        )
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("category", messages)

    def test_check_also_runs_under_dry_run_apply(self):
        # AC-6: "driven ... with and without dry-run apply" -- a targeted
        # verify step still errors when --dry-run-apply is also requested.
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "append_rework",
            "tasks_patch": {
                "mode": "append",
                "expected_next_task_id": "task0001",
                "entries": {},
            },
            "step_patches": [{"step_id": "verify"}],
            "preserve": ["workflow.implement.base_commit"],
        }
        errors = VWO.validate_workflow_patch(
            patch,
            workflow=self._workflow("not-a-real-category"),
            dry_run=True,
        )
        codes = {e.get("code") for e in errors}
        self.assertIn("category", codes)

    def test_untargeted_scope_also_holds_under_dry_run_apply(self):
        # AC-6 (pre-change case), driven through the whole entry point with
        # --dry-run-apply also requested: an untargeted patch still
        # produces no category error.
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "append_rework",
            "tasks_patch": {
                "mode": "append",
                "expected_next_task_id": "task0001",
                "entries": {},
            },
            "step_patches": [],
            "preserve": ["workflow.implement.base_commit"],
        }
        errors = VWO.validate_workflow_patch(
            patch,
            workflow=self._workflow(_OMIT),
            dry_run=True,
        )
        codes = {e.get("code") for e in errors}
        self.assertNotIn("category", codes)


_OMIT = object()


# ---------------------------------------------------------------------------
# rework-contract-drift/task0004 AC-7 (FR4): a `rework.spec-change`
# question with no `evidence[]` entry carrying a non-empty `origin_id` is
# rejected -- the mechanical half of `references/question-resolution.md`'s
# Classification gate origin verification -- driven both directly against
# `validate_question` and against the two new fixtures under
# `references/fixtures/question-packet/origin-verification/`.
# ---------------------------------------------------------------------------

class TestOriginIdEvidenceRequirement(unittest.TestCase):
    ORIGIN_VERIFICATION_DIR = (
        FIXTURES_ROOT / "question-packet" / "origin-verification"
    )

    @staticmethod
    def _question(evidence):
        return {
            "question_id": "rework.spec-change.probe",
            "gate_id": "rework.spec-change",
            "category": "spec-change",
            "priority": "high",
            "blocking": True,
            "prompt": "p",
            "header": "h",
            "answer_mode": "freeform",
            "options": [],
            "why_needed": "w",
            "on_unanswered": "block",
            "evidence": evidence,
        }

    def test_evidence_with_origin_id_accepted(self):
        errors = VWO.validate_question(
            self._question([{"path": "x", "origin_id": "TS-9"}]), 0
        )
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("evidence", messages)

    def test_empty_evidence_list_rejected(self):
        errors = VWO.validate_question(self._question([]), 0)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("origin_id", messages)

    def test_evidence_entry_without_origin_id_rejected(self):
        errors = VWO.validate_question(
            self._question([{"path": "x", "line": 1, "detail": "d"}]), 0
        )
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("origin_id", messages)

    def test_empty_string_origin_id_rejected(self):
        errors = VWO.validate_question(
            self._question([{"path": "x", "origin_id": ""}]), 0
        )
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("origin_id", messages)

    def test_non_spec_change_gate_id_unaffected(self):
        # Non-vacuity guard: the check is scoped to gate_id
        # rework.spec-change, never applied to unrelated questions.
        question = self._question([])
        question["gate_id"] = "create-plan.tbd-resolution"
        question["category"] = "tbd-resolution"
        errors = VWO.validate_question(question, 0)
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("origin_id", messages)

    def test_valid_verify_origin_fixture_passes_via_cli(self):
        case_dir = self.ORIGIN_VERIFICATION_DIR / "valid-verify-origin"
        result = run_cli(
            [
                "--kind",
                "question-packet",
                "--worker",
                "rework-planner",
                "--input",
                str(case_dir / "input.json"),
            ]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_missing_origin_id_fixture_rejected_naming_the_reason(
        self,
    ):
        case_dir = self.ORIGIN_VERIFICATION_DIR / "invalid-missing-origin-id"
        result = run_cli(
            [
                "--kind",
                "question-packet",
                "--worker",
                "rework-planner",
                "--input",
                str(case_dir / "input.json"),
            ]
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("origin_id", messages)


# ---------------------------------------------------------------------------
# rework-contract-drift/task0004 AC-2 (FR4, NFR3): owner-scoped absence
# scan. Shared Components "Retired-identifier absence scan": reads live
# files, covers this task's own closed path set (IMPLEMENTATION.md D3's
# task0004 partition), and builds its search term at run time rather than
# carrying it as a contiguous literal in its own source, so the scan never
# matches itself.
#
# Stated exclusions (D3), never scanned here: this feature's own
# feature-docs/rework-contract-drift/REQUIREMENTS.md and SPEC.md (which
# name the retired field in order to require its removal), the completed
# feature-docs/goal-vs-spec-divergence/ and test-docs/ records of the
# previous feature (rewriting a delivered record would falsify history),
# and git history.
# ---------------------------------------------------------------------------

class TestRetiredOriginIdentifierAbsenceScan(unittest.TestCase):
    OWNED_PATHS = [
        REPO_ROOT / "em-workflow" / "references" / "question-packet-schema.md",
        REPO_ROOT / "em-workflow" / "references" / "question-resolution.md",
        REPO_ROOT
        / "em-workflow"
        / "references"
        / "contracts"
        / "rework-planner-contract.md",
        SCRIPT_PATH,
        REPO_ROOT / "tests" / "test_classification_gate.py",
        REPO_ROOT / "tests" / "test_worker_contract_docs.py",
        REPO_ROOT / "tests" / "test_rework_synthesis_contract.py",
        REPO_ROOT / "tests" / "test_question_resolution_doc.py",
        REPO_ROOT / "tests" / "test_validate_worker_output.py",
        REPO_ROOT / "tests" / "test_gate_option_vocabulary.py",
        REPO_ROOT / "tests" / "test_spec_change_origin_binding.py",
        REPO_ROOT / "tests" / "test_spec_change_replan_authorization.py",
        REPO_ROOT / "tests" / "test_replanning_carry_over.py",
    ]

    @classmethod
    def setUpClass(cls):
        # Built at run time -- never a contiguous literal anywhere in this
        # module's own source -- so this scan cannot match itself merely
        # because it TALKS ABOUT the retired field.
        cls.retired_field = "finding" + "_stable_id"

    def _scan(self, paths):
        offenders = []
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if self.retired_field in text:
                offenders.append(str(path))
        return offenders

    def test_retired_field_absent_from_every_owned_file(self):
        for path in self.OWNED_PATHS:
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                self.assertEqual(self._scan([path]), [])

    def test_fixtures_directory_is_scanned_recursively(self):
        fixtures_root = REPO_ROOT / "em-workflow" / "references" / "fixtures"
        offenders = self._scan(p for p in fixtures_root.rglob("*") if p.is_file())
        self.assertEqual(offenders, [])

    def test_scan_does_not_match_itself(self):
        # Non-vacuity guard: the scan's own source file, read live, must
        # not trip the matcher -- proving the search term genuinely never
        # appears as a contiguous literal anywhere in this module.
        this_file = REPO_ROOT / "tests" / "test_validate_worker_output.py"
        self.assertNotIn(
            self.retired_field, this_file.read_text(encoding="utf-8")
        )

    def test_negative_proof_scan_detects_a_planted_occurrence(self):
        # Non-vacuity guard (Test Notes): the scan logic, applied to a
        # synthetic file that DOES carry the retired field, must report
        # it -- proving the absence above cannot pass vacuously.
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "planted.md"
            planted.write_text(
                f"evidence[].{self.retired_field} was here", encoding="utf-8"
            )
            self.assertEqual(self._scan([planted]), [str(planted)])



# ---------------------------------------------------------------------------
# scenario-id-ts-hyphen / task0001: the `scenario-id-form` check. A completed
# implementation-planner result must not newly write a hyphen-less (TSn)
# scenario ID into VERIFICATION.md or a task plan. The read side keeps
# accepting both forms (TestScenarioIdExtractionAcceptsBothForms and
# TestReworkIndexNoveltyWithBothScenarioIdForms above stay unchanged).
# AC-n in the test names are the task plan's acceptance criteria.
#
# Hyphen-less IDs are test data built here; a document written to disk is
# the only place they appear.
# ---------------------------------------------------------------------------

SCENARIO_ID_FORM = "scenario-id-form"


def _scenario_plan_text(file_path="src/a.go", prefix="", extra=""):
    """A task plan body that satisfies the existing Files and Acceptance
    Criteria checks. `prefix` goes before the title, `extra` into Design."""
    return (
        prefix
        + "# Task Plan: task0001 -- Something\n\n"
        "## Goal\n\nDeliver something.\n\n"
        "## Requirements\n\nFR1\n\n"
        "## Scope\n\n"
        "### Files to Create\n"
        f"- `{file_path}` -- main file\n\n"
        "### Files to Modify\n\n"
        f"## Design\n\nNotes. {extra}\n\n"
        "## Acceptance Criteria (MANDATORY)\n\n"
        "- [ ] AC-1: something is delivered\n\n"
        "## Test Notes\n\nNotes.\n\n"
        "## Out of Scope\n\nNone.\n"
    )


def _scenario_verification_text(*lines):
    return "\n".join(
        ["## Test Verification", "", "### Test Scenarios from SPEC.md", "", *lines, ""]
    )


def _planner_result_obj(entries, worker="implementation-planner"):
    """A completed result with a `replace_planning` patch. `entries` maps a
    task id to its `plan` value; each task declares its own file
    `src/<task id>.go`."""
    return {
        "schema_version": 1,
        "request_id": "run-0001",
        "worker": worker,
        "status": "completed",
        "input_revision": {"workflow_blob": "8f17c04", "input_digest": "sha256:" + "a" * 64},
        "question_packet": None,
        "blocking_reason": None,
        "written_artifacts": [],
        "workflow_patch": {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "tasks_patch": {
                "mode": "replace_all",
                "entries": {
                    task_id: {
                        "title": "Something",
                        "plan": plan_rel,
                        "files": [f"src/{task_id}.go"],
                        "skills": ["backend-impl"],
                        "domains": ["api-contract"],
                        "complexity": "medium",
                        "requirements": ["FR1"],
                        "initial_status": "pending",
                    }
                    for task_id, plan_rel in entries.items()
                },
            },
            "requirements_patch": None,
            "step_patches": [],
            "preserve": [],
        },
        "mode_echo": None,
        "payload": {"task_index": {task_id: {"title": "Something"} for task_id in entries}},
        "warnings": [],
        "report": "done",
    }


def _planner_envelope_obj():
    return {
        "schema_version": 1,
        "request_id": "env-run-0001",
        "phase": "create-plan",
        "mode": "interactive",
        "input_revision": {"workflow_blob": "8f17c04", "input_digest": "sha256:" + "a" * 64},
        "write_policy": {"targets": []},
        "allowed_write_roots": ["feature-docs/example/"],
        "resolved_input_paths": {},
    }


class _ScenarioIdFormCheckCase(unittest.TestCase):
    """Shared scaffolding: a temporary feature directory and a way to run the
    worker-result validation function against it."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_path = Path(tmp.name)
        self.feature_dir = self.tmp_path / "feature-dir"
        (self.feature_dir / "tasks").mkdir(parents=True)

    def write_plan(self, rel="tasks/task0001.md", task_id="task0001", **plan_kwargs):
        path = self.feature_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_scenario_plan_text(f"src/{task_id}.go", **plan_kwargs), encoding="utf-8")
        return path

    def write_verification(self, text):
        path = self.feature_dir / "VERIFICATION.md"
        path.write_text(text, encoding="utf-8")
        return path

    def validate(self, entries=None, feature_dir="default"):
        if entries is None:
            entries = {"task0001": "tasks/task0001.md"}
        if feature_dir == "default":
            feature_dir = self.feature_dir
        return VWO.validate_worker_result(
            _planner_result_obj(entries),
            "implementation-planner",
            envelope=_planner_envelope_obj(),
            feature_dir=feature_dir,
        )

    @staticmethod
    def form_errors(errors):
        return [e for e in errors if e["code"] == SCENARIO_ID_FORM]

    def symlink_or_skip(self, link, target):
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"cannot create symlinks on this platform: {exc}")

    def run_cli_on(self, result_obj, with_feature_dir=True):
        input_path = self.tmp_path / "input.json"
        envelope_path = self.tmp_path / "envelope.json"
        input_path.write_text(json.dumps(result_obj), encoding="utf-8")
        envelope_path.write_text(json.dumps(_planner_envelope_obj()), encoding="utf-8")
        args = [
            "--kind", "worker-result",
            "--worker", "implementation-planner",
            "--input", str(input_path),
            "--input-envelope", str(envelope_path),
        ]
        if with_feature_dir:
            args += ["--feature-dir", str(self.feature_dir)]
        return run_cli(args)


class TestHyphenlessScenarioIdFinder(unittest.TestCase):
    """The Hyphen-less ID detection rule, as a pure function of text."""

    def test_finds_a_hyphenless_id(self):
        self.assertEqual(VWO.find_hyphenless_scenario_ids("- TS3: boundary\n"), {"TS3"})

    def test_hyphenated_ids_are_not_reported(self):
        self.assertEqual(VWO.find_hyphenless_scenario_ids("- TS-3 and TS-12\n"), set())

    def test_both_spellings_of_one_number_report_only_the_hyphenless_one(self):
        self.assertEqual(VWO.find_hyphenless_scenario_ids("TS-3 is the same as TS3"), {"TS3"})

    def test_all_digits_are_consumed_and_duplicates_collapse(self):
        self.assertEqual(
            VWO.find_hyphenless_scenario_ids("TS13, TS13 and TS2"), {"TS13", "TS2"}
        )

    def test_fenced_code_block_is_not_scanned(self):
        text = "before\n```\nTS3\n```\nafter\n"
        self.assertEqual(VWO.find_hyphenless_scenario_ids(text), set())

    def test_html_comment_is_not_scanned(self):
        self.assertEqual(VWO.find_hyphenless_scenario_ids("a <!-- TS3 --> b"), set())

    def test_inline_code_span_is_scanned(self):
        self.assertEqual(VWO.find_hyphenless_scenario_ids("see `TS3` here"), {"TS3"})

    def test_match_at_the_very_start_of_the_text_counts(self):
        self.assertEqual(VWO.find_hyphenless_scenario_ids("TS3 first"), {"TS3"})

    def test_match_after_non_ascii_text_counts(self):
        self.assertEqual(
            VWO.find_hyphenless_scenario_ids("検証TS3を確認"), {"TS3"}
        )

    def test_match_after_ascii_punctuation_or_space_counts(self):
        for text in ("(TS3)", "_TS3", "X-TS3", "a TS3", "\nTS3"):
            with self.subTest(text=text):
                self.assertEqual(VWO.find_hyphenless_scenario_ids(text), {"TS3"})

    def test_match_directly_after_an_ascii_letter_or_digit_does_not_count(self):
        for text in ("XTS1", "UTS46", "xTS7", "9TS5", "TS3TS4"):
            with self.subTest(text=text):
                expected = {"TS3"} if text == "TS3TS4" else set()
                self.assertEqual(VWO.find_hyphenless_scenario_ids(text), expected)

    def test_read_grammar_and_extraction_are_unchanged(self):
        # FR4: the read side still returns both forms as literal strings.
        self.assertEqual(VWO._TS_ID_RE.pattern, r"TS-?\d+")
        self.assertEqual(
            VWO.extract_verification_scenario_ids(_scenarios_section("TS-1", "TS2")),
            {"TS-1", "TS2"},
        )


# ---------------------------------------------------------------------------
# scenario-id-fence-scope / task0001: the code range the scenario-ID form check
# leaves out is the line-start fenced blocks (backtick or tilde) and HTML
# comments. Inline triple backticks are not a block, so an ID between them is
# reported. AC-n in the test names are the task plan's acceptance criteria;
# TS-n in the docstrings are the SPEC's test scenarios.
#
# Hyphen-less IDs are test data built here, as in the classes above.
# ---------------------------------------------------------------------------


class TestScenarioIdFenceScopeFinder(unittest.TestCase):
    """AC-1 to AC-4: `find_hyphenless_scenario_ids` as a pure function of text."""

    def ids(self, text):
        return VWO.find_hyphenless_scenario_ids(text)

    # -- AC-1 (TS-1, TS-2, TS-5) ------------------------------------------

    def test_ac1_id_inside_a_backtick_block_is_not_reported(self):
        self.assertEqual(self.ids("```\nTS3\n```\n"), set())

    def test_ac1_id_after_the_fence_characters_of_a_backtick_opening_line_is_not_reported(self):
        for text in ("```TS3 note\nbody\n```\n", "```python TS3\nbody\n```\n"):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), set())

    def test_ac1_id_inside_a_tilde_block_is_not_reported(self):
        self.assertEqual(self.ids("~~~\nTS3\n~~~\n"), set())

    def test_ac1_id_after_the_fence_characters_of_a_tilde_opening_line_is_not_reported(self):
        for text in ("~~~TS3\nbody\n~~~\n", "~~~ TS3 ~~~ for details\nbody\n~~~\n"):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), set())

    def test_ac1_tilde_opening_line_with_text_after_the_run_opens_a_block(self):
        # SPEC A4: the rest of a tilde opening line is unrestricted, so the
        # whole line is an opening line and, unclosed, runs to the end.
        self.assertEqual(self.ids("~~~TS3~~~ for details.\nTS4\n"), set())

    def test_ac1_blocks_whose_lines_start_with_spaces_or_tabs_are_excluded(self):
        for indent in ("  ", "\t", " \t ", " " * 8):
            for fence in ("```", "~~~"):
                text = f"{indent}{fence}\nTS3\n{indent}{fence}\nafter\n"
                with self.subTest(indent=indent, fence=fence):
                    self.assertEqual(self.ids(text), set())

    def test_ac1_an_indented_opening_line_with_text_excludes_the_text_too(self):
        self.assertEqual(self.ids("\t  ~~~ TS3\nbody\n  ~~~\n"), set())

    # -- AC-2 (TS-3, TS-4) ------------------------------------------------

    def test_ac2_id_between_inline_triple_backticks_in_a_sentence_is_reported(self):
        self.assertEqual(self.ids("See ```TS3``` for details.\n"), {"TS3"})

    def test_ac2_id_between_triple_backticks_on_a_line_that_starts_with_them_is_reported(self):
        self.assertEqual(self.ids("```TS3``` for details.\n"), {"TS3"})

    def test_ac2_a_line_of_triple_backticks_with_more_backticks_later_is_not_an_opening_line(self):
        # FR5: nothing after such a line is swallowed.
        self.assertEqual(self.ids("```TS3```\nTS4\n"), {"TS3", "TS4"})
        self.assertEqual(self.ids("```TS3`\nTS4\n"), {"TS3", "TS4"})

    # -- AC-3 (TS-6, TS-7, TS-8) ------------------------------------------

    def test_ac3_id_after_a_longer_closing_run_is_reported(self):
        for text in ("```\nTS1\n````\nTS2\n", "~~~\nTS1\n~~~~~\nTS2\n"):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), {"TS2"})

    def test_ac3_id_after_a_closing_run_followed_by_spaces_and_tabs_is_reported(self):
        for text in ("```\nTS1\n``` \t \nTS2\n", "~~~\nTS1\n~~~\t\nTS2\n"):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), {"TS2"})

    def test_ac3_id_after_a_shorter_run_does_not_close_the_block(self):
        for text in ("````\nTS1\n```\nTS2\n", "~~~~\nTS1\n~~~\nTS2\n"):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), set())

    def test_ac3_id_after_a_run_of_the_other_character_does_not_close_the_block(self):
        for text in ("```\nTS1\n~~~\nTS2\n", "~~~\nTS1\n```\nTS2\n"):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), set())

    def test_ac3_id_after_a_run_followed_by_other_characters_does_not_close_the_block(self):
        for text in ("```\nTS1\n```x\nTS2\n", "~~~\nTS1\n~~~ text\nTS2\n", "```\nTS1\n``` ```\nTS2\n"):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), set())

    def test_ac3_unclosed_opening_line_excludes_everything_from_it_to_the_end(self):
        for text in ("TS1\n```\nTS2\n", "TS1\n~~~\nTS2\n", "TS1\n```TS3\nTS2\n"):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), {"TS1"})

    def test_ac3_a_block_of_one_character_is_not_closed_by_a_line_of_the_other(self):
        # Backtick lines inside a tilde block are block content; the block
        # ends only at the tilde line, and the line after it is checked again.
        self.assertEqual(self.ids("~~~\n```\nTS1\n~~~\nTS2\n"), {"TS2"})

    def test_ac3_lines_are_split_on_the_line_feed_only(self):
        # `str.splitlines` would also split at these characters and so close
        # the block at the third line.
        for separator in ("\u2028", "\u2029", "\x0b", "\x0c", "\x85", "\x1c"):
            text = f"```\nTS1\n```{separator}TS2\nTS3\n"
            with self.subTest(separator=repr(separator)):
                self.assertEqual(self.ids(text), set())

    # -- AC-4 (TS-9, TS-10, TS-11, NFR1) ----------------------------------

    def test_ac4_id_inside_an_html_comment_is_not_reported(self):
        self.assertEqual(self.ids("a <!-- TS3 --> b"), set())
        self.assertEqual(self.ids("<!--\nTS3\n-->\nTS4\n"), {"TS4"})

    def test_ac4_a_comment_opener_inside_a_block_has_no_effect_outside_it(self):
        self.assertEqual(self.ids("```\n<!--\n```\nTS4\n"), {"TS4"})
        self.assertEqual(self.ids("~~~\n<!--\n~~~\nTS4\n-->\n"), {"TS4"})

    def test_ac4_an_opening_shaped_line_inside_a_comment_still_opens_a_block(self):
        # SPEC A5: blocks go first, then comments, as in `_strip_noise`.
        self.assertEqual(self.ids("<!--\n```\n-->\nTS5\n"), set())

    def test_ac4_ids_right_before_and_right_after_a_block_are_reported(self):
        self.assertEqual(self.ids("TS1\n```\nx\n```\nTS2\n"), {"TS1", "TS2"})
        self.assertEqual(self.ids("TS1\n~~~\nx\n~~~\nTS2\n"), {"TS1", "TS2"})

    def test_ac4_id_right_after_a_block_at_the_start_of_the_document_is_reported(self):
        self.assertEqual(self.ids("```\nx\n```\nTS2\n"), {"TS2"})
        self.assertEqual(self.ids("~~~\nx\n~~~\nTS2\n"), {"TS2"})

    def test_ac4_the_line_after_a_block_is_judged_against_a_line_feed(self):
        # SPEC A11: the character before the kept line is a line feed, not
        # the last letter of an earlier kept line, so `abc` does not hide TS2.
        self.assertEqual(self.ids("abc\n```\nx\n```\nTS2\n"), {"TS2"})
        self.assertEqual(self.ids("abc\n```TS1\nx\n```\nTS2\n"), {"TS2"})

    def test_ac4_crlf_document_excludes_the_block_and_reports_the_next_line(self):
        for text in (
            "```\r\nTS1\r\n```\r\nTS2\r\n",
            "~~~\r\nTS1\r\n~~~\r\nTS2\r\n",
            "```TS3\r\nTS1\r\n```\r\nTS2\r\n",
            "  ```\r\nTS1\r\n  ```  \r\nTS2\r\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.ids(text), {"TS2"})

    def test_ac4_degenerate_inputs_return_a_set_without_raising(self):
        for text in ("", "\n", "\r", "\r\n", "```", "~~~", "```TS3", "~~~ TS3", "  ~~~ ", "```\r"):
            with self.subTest(text=text):
                result = self.ids(text)
                self.assertIsInstance(result, set)
                self.assertEqual(result, set())

    # -- beyond the scenarios: SPEC A10 -----------------------------------

    def test_a_fence_after_a_list_marker_is_not_an_opening_line(self):
        # The indented closing-shaped line is itself an opening line, so the
        # ID before it is checked and what follows is excluded.
        self.assertEqual(self.ids("- ```\n  TS3\n  ```\nTS4\n"), {"TS3"})

    def test_a_fence_after_a_quote_marker_is_not_an_opening_line(self):
        self.assertEqual(self.ids("> ```\n> TS3\n> ```\n"), {"TS3"})

    def test_the_preceding_character_test_is_unchanged_outside_blocks(self):
        self.assertEqual(self.ids("```\nx\n```\nXTS1 and (TS2)\n"), {"TS2"})


class TestScenarioIdFenceScopeReadSideUnchanged(unittest.TestCase):
    """AC-5 (TS-12): the read side keeps its range, which differs on purpose
    from the check's (SPEC A7)."""

    TEXT = (
        "### Test Scenarios from SPEC.md\n\n"
        "~~~\n| TS3 | in a tilde block |\n~~~\n\n"
        "See ```TS4``` for details.\n"
    )

    def test_ac5_strip_noise_keeps_a_tilde_block_and_removes_inline_triple_backticks(self):
        self.assertEqual(
            VWO._strip_noise("~~~\nTS3\n~~~\nSee ```TS4``` here.\n"),
            "~~~\nTS3\n~~~\nSee  here.\n",
        )

    def test_ac5_extraction_reads_the_tilde_block_and_not_the_inline_triple_backticks(self):
        self.assertEqual(VWO.extract_verification_scenario_ids(self.TEXT), {"TS3"})

    def test_ac5_the_check_reports_the_opposite_ids(self):
        self.assertEqual(VWO.find_hyphenless_scenario_ids(self.TEXT), {"TS4"})

    def test_ac5_the_fence_and_id_patterns_are_unchanged(self):
        self.assertEqual(VWO._FENCE_RE.pattern, r"```.*?```")
        self.assertEqual(VWO._FENCE_RE.flags & re.DOTALL, re.DOTALL)
        self.assertEqual(VWO._TS_ID_RE.pattern, r"TS-?\d+")


class TestScenarioIdFormCheckFenceScope(_ScenarioIdFormCheckCase):
    """AC-6 (TS-13): the range reaches the check on a completed planner result."""

    def test_ac6_an_id_in_a_tilde_block_yields_no_error_in_either_document(self):
        self.write_plan(extra="\n~~~\nTS7\n~~~\n")
        self.write_verification(_scenario_verification_text("~~~", "| TS3 | a |", "~~~"))
        self.assertEqual(self.validate(), [])

    def test_ac6_an_id_between_inline_triple_backticks_in_verification_md_yields_an_error(self):
        self.write_plan()
        self.write_verification(_scenario_verification_text("See ```TS3``` for details."))
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("VERIFICATION.md", found[0]["message"])
        self.assertIn("TS3", found[0]["message"])

    def test_ac6_an_id_between_inline_triple_backticks_in_a_plan_yields_an_error(self):
        self.write_plan(extra="See ```TS7``` for details.")
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("tasks/task0001.md", found[0]["message"])
        self.assertIn("TS7", found[0]["message"])


class TestScenarioIdFormCheckOnVerification(_ScenarioIdFormCheckCase):
    """AC-1 and the VERIFICATION.md half of AC-3."""

    def test_clean_documents_yield_no_errors(self):
        self.write_plan()
        self.write_verification(_scenario_verification_text("| TS-1 | something | ok | Unit |"))
        self.assertEqual(self.validate(), [])

    def test_ac1_hyphenless_id_yields_exactly_one_error_naming_file_and_id(self):
        self.write_plan()
        self.write_verification(_scenario_verification_text("| TS3 | something | ok | Unit |"))
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("VERIFICATION.md", found[0]["message"])
        self.assertIn("TS3", found[0]["message"])

    def test_ac1_ids_are_listed_deduplicated_and_sorted(self):
        self.write_plan()
        self.write_verification(
            _scenario_verification_text("| TS3 | a |", "| TS12 | b |", "| TS3 | c |", "| TS2 | d |")
        )
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("TS12, TS2, TS3", found[0]["message"])
        self.assertEqual(found[0]["message"].count("TS3"), 1)

    def test_ac1_hyphenated_spelling_of_the_same_number_does_not_hide_the_error(self):
        self.write_plan()
        self.write_verification(
            _scenario_verification_text("| TS-3 | hyphenated |", "| TS3 | hyphen-less |")
        )
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("TS3", found[0]["message"])
        self.assertNotIn("TS-3", found[0]["message"])

    def test_ac1_an_id_outside_the_test_scenarios_section_is_found(self):
        self.write_plan()
        self.write_verification(
            _scenario_verification_text("| TS-1 | ok |") + "\n## Notes\n\nSee TS9 for details.\n"
        )
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("TS9", found[0]["message"])

    def test_ac3_documents_with_only_ignorable_occurrences_yield_no_error(self):
        cases = {
            "fenced code block": "```\nTS3\n```",
            "html comment": "<!-- TS3 -->",
            "letter before TS": "XTS1 and UTS46",
            "digit before TS": "9TS5",
        }
        self.write_plan()
        for label, body in cases.items():
            with self.subTest(label=label):
                self.write_verification(_scenario_verification_text(body))
                self.assertEqual(self.form_errors(self.validate()), [])

    def test_ac3_documents_with_a_countable_occurrence_yield_an_error(self):
        cases = {
            "inline code span": ("see `TS3`", "TS3"),
            "very start of the document": ("TS4 leads the file", "TS4"),
            "after Japanese text": ("検証TS5を確認", "TS5"),
        }
        self.write_plan()
        for label, (body, expected_id) in cases.items():
            with self.subTest(label=label):
                text = _scenario_verification_text(body)
                if label == "very start of the document":
                    text = body + "\n" + text
                self.write_verification(text)
                found = self.form_errors(self.validate())
                self.assertEqual(len(found), 1, found)
                self.assertIn(expected_id, found[0]["message"])


class TestScenarioIdFormCheckOnTaskPlans(_ScenarioIdFormCheckCase):
    """AC-2 and the task-plan half of AC-3."""

    def test_ac2_hyphenless_id_in_a_plan_yields_one_error_naming_task_plan_and_id(self):
        self.write_plan(extra="Covers TS7.")
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        message = found[0]["message"]
        self.assertIn("task0001", message)
        self.assertIn("tasks/task0001.md", message)
        self.assertIn("TS7", message)

    def test_ac2_each_offending_plan_gets_its_own_error(self):
        self.write_plan("tasks/task0001.md", "task0001", extra="Covers TS7.")
        self.write_plan("tasks/task0002.md", "task0002", extra="Covers TS-8.")
        self.write_plan("tasks/task0003.md", "task0003", extra="Covers TS9.")
        found = self.form_errors(
            self.validate(
                {
                    "task0001": "tasks/task0001.md",
                    "task0002": "tasks/task0002.md",
                    "task0003": "tasks/task0003.md",
                }
            )
        )
        self.assertEqual(len(found), 2, found)
        self.assertIn("task0001", found[0]["message"])
        self.assertIn("task0003", found[1]["message"])

    def test_ac2_plan_ids_are_listed_deduplicated_and_sorted(self):
        self.write_plan(extra="TS3 TS12 TS3 TS2")
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("TS12, TS2, TS3", found[0]["message"])

    def test_ac2_both_targets_are_reported_independently(self):
        self.write_plan(extra="Covers TS7.")
        self.write_verification(_scenario_verification_text("| TS3 | a |"))
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 2, found)
        messages = " ".join(e["message"] for e in found)
        self.assertIn("VERIFICATION.md", messages)
        self.assertIn("TS3", messages)
        self.assertIn("tasks/task0001.md", messages)
        self.assertIn("TS7", messages)

    def test_ac2_task_document_plan_is_exempt(self):
        # A plan whose final path segment is TASK.md is not a target, with
        # the very content that is rejected under another name.
        content = "## Change\n\nTouch it for TS7.\n\n## Expected Result\n\nDone.\n"
        task_doc = self.feature_dir / "tasks" / "task0001" / "TASK.md"
        task_doc.parent.mkdir(parents=True)
        task_doc.write_text(content, encoding="utf-8")
        errors = self.validate({"task0001": "tasks/task0001/TASK.md"})
        self.assertEqual(self.form_errors(errors), [])
        self.assertEqual(errors, [])

        other = self.feature_dir / "tasks" / "task0001" / "NOTES.md"
        other.write_text(_scenario_plan_text("src/task0001.go", extra="TS7"), encoding="utf-8")
        found = self.form_errors(self.validate({"task0001": "tasks/task0001/NOTES.md"}))
        self.assertEqual(len(found), 1, found)

    def test_ac3_plans_with_only_ignorable_occurrences_yield_no_error(self):
        cases = {
            "hyphenated form": "Covers TS-7.",
            "fenced code block": "\n```\nTS7\n```\n",
            "html comment": "<!-- TS7 -->",
            "letter before TS": "XTS1 and UTS46",
        }
        for label, extra in cases.items():
            with self.subTest(label=label):
                self.write_plan(extra=extra)
                errors = self.validate()
                self.assertEqual(self.form_errors(errors), [])
                self.assertEqual(errors, [])

    def test_ac3_plans_with_a_countable_occurrence_yield_an_error(self):
        cases = {
            "inline code span": ({"extra": "see `TS7`"}, "TS7"),
            "very start of the document": ({"prefix": "TS8 leads the file\n\n"}, "TS8"),
            "after Japanese text": ({"extra": "検証TS9を確認"}, "TS9"),
        }
        for label, (kwargs, expected_id) in cases.items():
            with self.subTest(label=label):
                self.write_plan(**kwargs)
                found = self.form_errors(self.validate())
                self.assertEqual(len(found), 1, found)
                self.assertIn(expected_id, found[0]["message"])


class TestScenarioIdFormCheckScope(_ScenarioIdFormCheckCase):
    """AC-4: the check runs only for a completed implementation-planner
    result with a feature directory (IMPLEMENTATION.md D1)."""

    def _hyphenless_feature_dir(self):
        self.write_plan(extra="Covers TS7.")
        self.write_verification(_scenario_verification_text("| TS3 | a |"))

    def test_ac4_control_the_same_directory_is_rejected_for_a_completed_planner_result(self):
        self._hyphenless_feature_dir()
        self.assertEqual(len(self.form_errors(self.validate())), 2)

    def test_ac4_rework_planner_result_is_not_checked(self):
        # The rework-planner fixture's own input and envelope, validated
        # against a feature directory that carries hyphen-less documents.
        fixture = FIXTURES_ROOT / "worker-result" / "rework-planner" / "valid-completed"
        result_obj = json.loads((fixture / "input.json").read_text(encoding="utf-8"))
        envelope_obj = json.loads((fixture / "envelope.json").read_text(encoding="utf-8"))
        self._hyphenless_feature_dir()
        self.write_plan("tasks/task0007.md", "task0007", extra="Covers TS7.")
        errors = VWO.validate_worker_result(
            result_obj, "rework-planner", envelope=envelope_obj, feature_dir=self.feature_dir
        )
        self.assertEqual(self.form_errors(errors), [])

    def test_ac4_planner_result_with_another_status_is_not_checked(self):
        self._hyphenless_feature_dir()
        references_dir = REPO_ROOT / "em-workflow" / "references"
        gate_registry = VWO.build_gate_registry(references_dir)
        for name in ("valid-needs-user-input", "valid-blocked", "valid-failed",
                     "valid-invalid-input", "valid-stale-input"):
            fixture = FIXTURES_ROOT / "worker-result" / "implementation-planner" / name
            result_obj = json.loads((fixture / "input.json").read_text(encoding="utf-8"))
            envelope_obj = json.loads((fixture / "envelope.json").read_text(encoding="utf-8"))
            self.assertNotEqual(result_obj["status"], "completed", name)
            with self.subTest(fixture=name):
                errors = VWO.validate_worker_result(
                    result_obj,
                    "implementation-planner",
                    envelope=envelope_obj,
                    feature_dir=self.feature_dir,
                    gate_registry=gate_registry,
                )
                self.assertEqual(errors, [])

    def test_ac4_validation_without_a_feature_directory_is_not_checked(self):
        self._hyphenless_feature_dir()
        self.assertEqual(self.form_errors(self.validate(feature_dir=None)), [])

    def test_ac4_cli_without_feature_dir_exits_zero(self):
        self._hyphenless_feature_dir()
        result = self.run_cli_on(_planner_result_obj({"task0001": "tasks/task0001.md"}), with_feature_dir=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ac4_missing_verification_md_is_not_an_error(self):
        self.write_plan()
        self.assertFalse((self.feature_dir / "VERIFICATION.md").exists())
        self.assertEqual(self.validate(), [])

    def test_ac4_plan_file_no_entry_names_is_not_read(self):
        self.write_plan()
        self.write_plan("tasks/task0002.md", "task0002", extra="Covers TS7.")
        self.assertEqual(self.validate(), [])

    def test_ac4_carried_task_plans_are_not_targets(self):
        # Ids in tasks_patch.carried_task_ids have no entry, so their plans
        # are not read.
        self.write_plan()
        self.write_plan("tasks/task0002.md", "task0002", extra="Covers TS7.")
        result_obj = _planner_result_obj({"task0001": "tasks/task0001.md"})
        result_obj["workflow_patch"]["tasks_patch"]["carried_task_ids"] = ["task0002"]
        found = self.form_errors(
            VWO._validate_scenario_id_form(result_obj["workflow_patch"], self.feature_dir)
        )
        self.assertEqual(found, [])


class TestScenarioIdFormCheckReadSafety(_ScenarioIdFormCheckCase):
    """AC-5 and AC-6 (THREAT-MODEL.md TM-1, TM-2): file state is reported as
    validation errors and never as an exception."""

    def _outside_file(self):
        outside = self.tmp_path / "outside.md"
        outside.write_text(_scenario_plan_text("src/task0001.go", extra="Covers TS7."), encoding="utf-8")
        return outside

    def test_ac5_absolute_plan_path_is_not_read(self):
        outside = self._outside_file()
        errors = self.validate({"task0001": str(outside)})
        self.assertEqual(self.form_errors(errors), [])
        self.assertTrue(any(e["code"] == "task-plan-path" for e in errors), errors)

    def test_ac5_plan_path_with_a_parent_segment_is_not_read(self):
        self._outside_file()
        errors = self.validate({"task0001": "../outside.md"})
        self.assertEqual(self.form_errors(errors), [])
        self.assertTrue(any(e["code"] == "task-plan-path" for e in errors), errors)

    def test_ac5_plan_that_is_a_symlink_is_not_read(self):
        outside = self._outside_file()
        self.symlink_or_skip(self.feature_dir / "tasks" / "task0001.md", outside)
        errors = self.validate()
        self.assertEqual(self.form_errors(errors), [])
        self.assertTrue(any(e["code"] == "task-plan-path" for e in errors), errors)

    def test_ac5_plan_reached_through_a_symlinked_directory_is_not_read(self):
        real_dir = self.tmp_path / "real-tasks"
        real_dir.mkdir()
        (real_dir / "task0001.md").write_text(
            _scenario_plan_text("src/task0001.go", extra="Covers TS7."), encoding="utf-8"
        )
        self.symlink_or_skip(self.feature_dir / "linked", real_dir)
        errors = self.validate({"task0001": "linked/task0001.md"})
        self.assertEqual(self.form_errors(errors), [])
        self.assertTrue(any(e["code"] == "task-plan-path" for e in errors), errors)

    def test_ac5_oversized_or_missing_plan_is_left_to_the_existing_errors(self):
        (self.feature_dir / "tasks" / "task0001.md").write_text(
            "TS7 " + "x" * VWO.MAX_PLAN_READ_BYTES, encoding="utf-8"
        )
        errors = self.validate()
        self.assertEqual(self.form_errors(errors), [])
        self.assertTrue(any(e["code"] == "task-plan-too-large" for e in errors), errors)
        errors = self.validate({"task0001": "tasks/missing.md"})
        self.assertEqual(self.form_errors(errors), [])
        self.assertTrue(any(e["code"] == "task-plan-missing" for e in errors), errors)

    def test_ac5_verification_md_symlink_is_reported_and_not_followed(self):
        self.write_plan()
        target = self.tmp_path / "elsewhere.md"
        target.write_text(_scenario_verification_text("| TS3 | a |"), encoding="utf-8")
        self.symlink_or_skip(self.feature_dir / "VERIFICATION.md", target)
        errors = self.validate()
        found = self.form_errors(errors)
        self.assertEqual(len(found), 1, found)
        self.assertIn("VERIFICATION.md", found[0]["message"])
        self.assertIn("symlink", found[0]["message"])
        for e in errors:
            self.assertNotIn("TS3", e["message"])

    def test_ac5_dangling_verification_md_symlink_is_reported(self):
        self.write_plan()
        self.symlink_or_skip(self.feature_dir / "VERIFICATION.md", self.tmp_path / "does-not-exist.md")
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("symlink", found[0]["message"])

    def test_ac6_oversized_verification_md_is_reported_and_not_scanned(self):
        self.write_plan()
        self.write_verification("TS3 " + "x" * VWO.MAX_PLAN_READ_BYTES)
        self.assertGreater((self.feature_dir / "VERIFICATION.md").stat().st_size, VWO.MAX_PLAN_READ_BYTES)
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("VERIFICATION.md", found[0]["message"])
        self.assertIn("too large", found[0]["message"])
        self.assertNotIn("TS3", found[0]["message"])

    def test_ac6_verification_md_of_exactly_the_limit_is_still_scanned(self):
        self.write_plan()
        self.write_verification("TS3 " + "x" * (VWO.MAX_PLAN_READ_BYTES - 4))
        self.assertEqual((self.feature_dir / "VERIFICATION.md").stat().st_size, VWO.MAX_PLAN_READ_BYTES)
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("TS3", found[0]["message"])

    def test_ac6_verification_md_directory_is_reported(self):
        self.write_plan()
        (self.feature_dir / "VERIFICATION.md").mkdir()
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("VERIFICATION.md", found[0]["message"])
        self.assertIn("not a regular file", found[0]["message"])

    def test_ac6_verification_md_that_is_not_utf8_is_reported_and_not_scanned(self):
        self.write_plan()
        (self.feature_dir / "VERIFICATION.md").write_bytes(b"TS3 \xff\xfe\xfa")
        found = self.form_errors(self.validate())
        self.assertEqual(len(found), 1, found)
        self.assertIn("VERIFICATION.md", found[0]["message"])
        self.assertIn("not UTF-8", found[0]["message"])
        self.assertNotIn("TS3", found[0]["message"])

    def test_ac6_cli_exits_one_not_two_for_each_unreadable_verification_md(self):
        self.write_plan()
        verification = self.feature_dir / "VERIFICATION.md"
        result_obj = _planner_result_obj({"task0001": "tasks/task0001.md"})
        variants = {
            "oversized": lambda: verification.write_text(
                "x" * (VWO.MAX_PLAN_READ_BYTES + 1), encoding="utf-8"
            ),
            "directory": lambda: verification.mkdir(),
            "not UTF-8": lambda: verification.write_bytes(b"\xff\xfe\xfa"),
        }
        for label, make in variants.items():
            with self.subTest(label=label):
                if verification.is_dir():
                    verification.rmdir()
                elif verification.exists():
                    verification.unlink()
                make()
                result = self.run_cli_on(result_obj)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(SCENARIO_ID_FORM, result.stdout)

    def test_check_does_not_raise_on_a_malformed_patch(self):
        self.write_verification(_scenario_verification_text("| TS-1 | a |"))
        malformed = [
            None,
            "text",
            [],
            {},
            {"tasks_patch": None},
            {"tasks_patch": []},
            {"tasks_patch": {"entries": None}},
            {"tasks_patch": {"entries": ["task0001"]}},
            {"tasks_patch": {"entries": {"task0001": None}}},
            {"tasks_patch": {"entries": {"task0001": {"plan": 7}}}},
            {"tasks_patch": {"entries": {"task0001": {"plan": ["tasks/task0001.md"]}}}},
            {"tasks_patch": {"entries": {"task0001": {"plan": "\x00"}}}},
            {"tasks_patch": {"entries": {"task0001": {"plan": ""}}}},
            {"tasks_patch": {"entries": {"task0001": {"plan": "/"}}}},
            {"tasks_patch": {"entries": {"task0001": {"plan": "."}}}},
        ]
        for patch in malformed:
            with self.subTest(patch=repr(patch)):
                self.assertEqual(VWO._validate_scenario_id_form(patch, self.feature_dir), [])


class TestScenarioIdFormCheckCli(_ScenarioIdFormCheckCase):
    """The command line: a hyphen-less VERIFICATION.md exits 1 and the JSON
    detail on stdout carries the `scenario-id-form` code."""

    def test_hyphenless_verification_md_exits_one_with_the_code_in_the_json(self):
        self.write_plan()
        self.write_verification(_scenario_verification_text("| TS3 | a |"))
        result = self.run_cli_on(_planner_result_obj({"task0001": "tasks/task0001.md"}))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        output = json.loads(result.stdout)
        codes = [e["code"] for e in output["errors"]]
        self.assertEqual(codes, [SCENARIO_ID_FORM])

    def test_hyphenated_verification_md_exits_zero(self):
        self.write_plan()
        self.write_verification(_scenario_verification_text("| TS-3 | a |"))
        result = self.run_cli_on(_planner_result_obj({"task0001": "tasks/task0001.md"}))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
