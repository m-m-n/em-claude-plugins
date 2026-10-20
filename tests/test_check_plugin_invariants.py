"""Tests for em-workflow/scripts/check-plugin-invariants.py (task0014;
enforcement fixed by task0021).

Renders design-input.md 9.1 (automated verification table) and
IMPLEMENTATION.md D4: the checks assert properties of the fully integrated
repository, which no single task worktree exhibits. Every test below
therefore builds a synthetic directory tree in a temporary directory and
exercises the check functions against it -- never the real repository
(AC-6). The authoritative run against the real repository used to be only a
verify-phase step recorded in VERIFICATION.md; task0021 adds a case here too
(TestRepositoryLevelInvariant), because that was the actual defect (reviews/
round1.yaml finding as2): the suite could pass while the checker itself
failed on the real tree.

The script's filename intentionally uses a hyphen (CLI-script convention,
not an importable package), so it is loaded via `importlib.util` from its
actual path -- the identical technique test_hooks_registration.py already
uses for hook scripts.

task0014 acceptance criteria covered (unchanged by task0021):
- AC-1: the CLI accepts a repository root argument and exits 0 / 1 / 2.
- AC-2: all seven checks exist as independently callable functions.
- AC-3: every check reports specific offenders on failure, not a bare bool.
- AC-4: agent/dispatch parity fails both for an undispatched definition and
  for a dispatch of a missing definition.
- AC-5: gate coverage fails in both directions and excludes the documented
  intentional exception (`rework.spec-change`, design-input.md 5.4.4/5.9)
  from both directions.
- AC-6: every check's passing and failing branch is exercised here.
- AC-7: digest reproducibility computes twice over a self-built input and
  compares.

task0021 acceptance criteria added here (feature-docs/agent-separation/
tasks/task0021.md -- numbered independently of the list above, which is
task0014's own):
- AC-1: TestRepositoryLevelInvariant -- the checker exits 0 against the real
  repository root.
- AC-2: covered in tests/test_reference_sweep.py, not here.
- AC-3: TestStaleReferences' new "allows_*" cases (other features'
  feature-docs, test-docs, and tests/ literals), alongside the pre-existing
  "fails_on_*" cases which still prove an occurrence under the plugin
  directory (em-workflow/) is never excused.
- AC-4: TestSinglePassTraversal.
- AC-5: every pre-existing synthetic case above still passes unmodified.
- AC-6: TestGateIdCoverage's new "referenced_without_nearby_gate_id_phrase"
  and "mention_inside_the_policy_file_itself" cases.
- AC-7: verified by this task's implementer report, not a test (it depends
  on sibling merges already having landed at this worktree's branch point).
"""

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "check-plugin-invariants.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location(
        "_check_plugin_invariants_under_test", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cpi = load_script_module()


def write(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestAllSevenChecksExist(unittest.TestCase):
    """AC-2: each of the seven checks is an independently callable function."""

    def test_seven_check_functions_are_independently_callable(self):
        names = [
            "check_agent_dispatch_parity",
            "check_stale_references",
            "check_gate_id_coverage",
            "check_domains_vocabulary_parity",
            "check_forbidden_task_assignment_heading",
            "check_fixture_branch_coverage",
            "check_digest_reproducibility",
        ]
        for n in names:
            self.assertTrue(callable(getattr(cpi, n, None)), f"{n} missing or not callable")


class TestAgentDispatchParity(unittest.TestCase):
    def test_passes_when_every_definition_is_dispatched_and_vice_versa(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "em-workflow" / "agents" / "implementer.md", "# implementer\n")
            write(root / "em-workflow" / "agents" / "reviewer.md", "# reviewer\n")
            write(
                root / "em-workflow" / "references" / "implement-phase.md",
                'Launch `Task(subagent_type="em-workflow:implementer")`.\n',
            )
            write(
                root / "em-workflow" / "references" / "review-phase.md",
                'Launch `Task(subagent_type="em-workflow:reviewer")`.\n',
            )
            result = cpi.check_agent_dispatch_parity(str(root))
            self.assertTrue(result.passed, result.offenders)
            self.assertEqual(result.offenders, [])

    def test_fails_on_an_undispatched_definition(self):
        # AC-4, direction 1: a definition nobody dispatches.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "em-workflow" / "agents" / "implementer.md", "# implementer\n")
            write(root / "em-workflow" / "agents" / "orphan.md", "# orphan\n")
            write(
                root / "em-workflow" / "references" / "implement-phase.md",
                'Launch `Task(subagent_type="em-workflow:implementer")`.\n',
            )
            result = cpi.check_agent_dispatch_parity(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(any("orphan" in o for o in result.offenders), result.offenders)

    def test_fails_on_a_dispatch_of_a_missing_definition(self):
        # AC-4, direction 2: a dispatch referencing a name with no definition.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "em-workflow" / "agents" / "implementer.md", "# implementer\n")
            write(
                root / "em-workflow" / "references" / "implement-phase.md",
                'Launch `Task(subagent_type="em-workflow:implementer")` then '
                '`Task(subagent_type="em-workflow:ghost")`.\n',
            )
            result = cpi.check_agent_dispatch_parity(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(any("ghost" in o for o in result.offenders), result.offenders)

    def test_non_markdown_file_in_agents_dir_is_not_a_definition(self):
        # Edge case (Test Notes): a non-Markdown file under agents/ must not
        # be treated as an agent definition.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "em-workflow" / "agents" / "implementer.md", "# implementer\n")
            write(root / "em-workflow" / "agents" / "notes.txt", "not an agent\n")
            write(
                root / "em-workflow" / "references" / "implement-phase.md",
                'Launch `Task(subagent_type="em-workflow:implementer")`.\n',
            )
            result = cpi.check_agent_dispatch_parity(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_reference_inside_a_fenced_code_block_still_counts(self):
        # Edge case (Test Notes): a subagent-type reference inside a fenced
        # code block must still count as a reference.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "em-workflow" / "agents" / "implementer.md", "# implementer\n")
            write(
                root / "em-workflow" / "references" / "implement-phase.md",
                "Example call:\n\n```\nTask(subagent_type=\"em-workflow:implementer\")\n```\n",
            )
            result = cpi.check_agent_dispatch_parity(str(root))
            self.assertTrue(result.passed, result.offenders)


class TestStaleReferences(unittest.TestCase):
    def test_passes_when_no_stale_reference_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "em-workflow" / "agents" / "implementer.md", "# implementer\n")
            result = cpi.check_stale_references(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_fails_on_the_removed_agent_name_outside_the_feature_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "em-workflow" / "skills" / "develop" / "SKILL.md",
                "Read requirements-spec-creator.md and follow it.\n",
            )
            result = cpi.check_stale_references(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(
                any("skills/develop/SKILL.md" in o for o in result.offenders), result.offenders
            )

    def test_fails_on_the_inline_execution_phrase_outside_the_feature_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "em-workflow" / "skills" / "develop" / "SKILL.md",
                "agents/designer.md を Read してインラインで従う\n",
            )
            result = cpi.check_stale_references(str(root))
            self.assertFalse(result.passed)

    def test_allows_historical_quotation_inside_this_features_own_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "feature-docs" / "agent-separation" / "design-input.md",
                "The old requirements-spec-creator agent used to be Read "
                "してインラインで従う.\n",
            )
            result = cpi.check_stale_references(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_allows_historical_quotation_in_a_different_features_feature_docs(self):
        # task0021 AC-3 (reviews/round1.yaml finding as2): "other features'
        # historical records" -- not just this feature's own feature-docs/
        # agent-separation, any completed feature's feature-docs directory
        # (e.g. feature-docs/integration-worktree-orchestration/**, which
        # is what the previous single-feature prefix actually missed).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "feature-docs" / "some-other-feature" / "REQUIREMENTS.md",
                f"Historically depended on {cpi.STALE_AGENT_NAME}.\n",
            )
            result = cpi.check_stale_references(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_allows_an_absence_asserting_test_literal_in_test_docs(self):
        # task0021 AC-3: a recorded test-run outcome that quotes the
        # deleted name (e.g. a red_reason string) is not a stale reference.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "test-docs" / "agent-separation" / "task0099.tests.yaml",
                f'red_reason: "{cpi.STALE_AGENT_NAME!r} unexpectedly found"\n',
            )
            result = cpi.check_stale_references(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_allows_an_absence_asserting_test_literal_in_the_tests_directory(self):
        # task0021 AC-3: "a test that asserts a string's absence must
        # contain that string" -- a literal constant used by an assertNotIn
        # style check must not itself be reported as a stale reference.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "tests" / "test_something_else.py",
                f'OLD_NAME = "{cpi.STALE_AGENT_NAME}"\n'
                "def test_absent(self):\n"
                "    self.assertNotIn(OLD_NAME, some_text)\n",
            )
            result = cpi.check_stale_references(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_still_fails_under_the_plugin_directory_even_though_other_roots_are_allowed(self):
        # task0021 AC-3: widening the allowed roots must never excuse a
        # real occurrence under em-workflow/ -- the one directory the
        # allowed-roots set deliberately omits.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "em-workflow" / "references" / "batch-mode.md",
                f"See agents/{cpi.STALE_AGENT_NAME}.md for the old flow.\n",
            )
            result = cpi.check_stale_references(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(
                any("batch-mode.md" in o for o in result.offenders), result.offenders
            )


class TestGateIdCoverage(unittest.TestCase):
    def _write_policy(self, root, gate_ids):
        body = "gate_policies:\n"
        for gid in gate_ids:
            body += f"  {gid}:\n    action: select\n    option_id: x\n"
        write(root / "em-workflow" / "references" / "batch-policies.yaml", body)

    def test_passes_when_referenced_and_policy_sets_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, ["create-spec.feature-identity"])
            write(
                root / "em-workflow" / "references" / "phases" / "create-spec-phase.md",
                "Ask via gate ID `create-spec.feature-identity`.\n",
            )
            result = cpi.check_gate_id_coverage(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_fails_when_a_referenced_gate_is_missing_from_policy(self):
        # AC-5, direction 1.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, [])
            write(
                root / "em-workflow" / "references" / "phases" / "create-spec-phase.md",
                "Ask via gate ID `create-spec.feature-identity`.\n",
            )
            result = cpi.check_gate_id_coverage(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(
                any("create-spec.feature-identity" in o for o in result.offenders),
                result.offenders,
            )

    def test_fails_when_policy_has_an_entry_never_referenced(self):
        # AC-5, direction 2.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, ["create-spec.feature-identity"])
            write(
                root / "em-workflow" / "skills" / "develop" / "SKILL.md",
                "no gate mentions here\n",
            )
            result = cpi.check_gate_id_coverage(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(
                any("create-spec.feature-identity" in o for o in result.offenders),
                result.offenders,
            )

    def test_documented_intentional_exception_excluded_both_directions(self):
        # AC-5: `rework.spec-change` (design-input.md 5.4.4/5.9) is
        # deliberately absent from the policy file; it must not be reported
        # in either direction.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, ["create-spec.feature-identity"])
            write(
                root / "em-workflow" / "references" / "phases" / "create-spec-phase.md",
                "Ask via gate ID `create-spec.feature-identity`.\n",
            )
            write(
                root / "em-workflow" / "skills" / "develop" / "SKILL.md",
                "Rework asks `gate_id: rework.spec-change` before resuming.\n",
            )
            result = cpi.check_gate_id_coverage(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_gate_id_differing_only_by_case_is_not_treated_as_a_match(self):
        # Edge case (Test Notes): case must not be normalized away.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, ["create-spec.feature-identity"])
            write(
                root / "em-workflow" / "references" / "phases" / "create-spec-phase.md",
                "Ask via gate ID `Create-Spec.Feature-Identity`.\n",
            )
            result = cpi.check_gate_id_coverage(str(root))
            self.assertFalse(result.passed)
            self.assertEqual(len(result.offenders), 2, result.offenders)

    def test_unrelated_dotted_backtick_token_is_not_mistaken_for_a_gate_id(self):
        # A package-manifest name or a workflow.yaml field path can share the
        # same `namespace.name` backtick shape as a real gate ID (e.g.
        # `go.mod`, `project.components`) without being anywhere near a
        # "gate ID" / "gate_id" mention. It must not be reported as a
        # dangling reference, and the policy's real entry must still be
        # reported unused (nothing in this document actually references it).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, ["create-spec.feature-identity"])
            write(
                root / "em-workflow" / "references" / "phases" / "create-spec-phase.md",
                "Detected manifests: `go.mod`, `project.components`.\n",
            )
            result = cpi.check_gate_id_coverage(str(root))
            self.assertFalse(result.passed)
            self.assertFalse(any("go.mod" in o for o in result.offenders), result.offenders)
            self.assertFalse(
                any("project.components" in o for o in result.offenders), result.offenders
            )
            self.assertTrue(
                any("create-spec.feature-identity" in o for o in result.offenders),
                result.offenders,
            )

    def test_identifier_referenced_without_a_nearby_gate_id_phrase_is_not_unreferenced(self):
        # task0021 AC-6 (reviews/round1.yaml finding as2): replaces the
        # proximity heuristic for known policy vocabulary. A table row that
        # names the gate id with no "gate ID" / "gate_id" phrase anywhere
        # nearby, in a file outside find_gate_scan_files()'s narrow scope
        # (an agent prompt, not a phase protocol) -- the exact shape of the
        # real six-identifier false report this fixes (analyst contract and
        # prompt, batch-mode table, planner prompt).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, ["create-plan.license-conflict"])
            write(
                root / "em-workflow" / "agents" / "implementation-planner.md",
                "| license conflict (step 3) | `create-plan.license-conflict` |\n",
            )
            result = cpi.check_gate_id_coverage(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_mention_inside_the_policy_file_itself_does_not_count_as_a_reference(self):
        # task0021 AC-6: a gate id being a key inside batch-policies.yaml is
        # not, by itself, a reference to that id -- with no other file
        # mentioning it, it must still be reported as unused.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, ["create-plan.license-conflict"])
            result = cpi.check_gate_id_coverage(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(
                any("create-plan.license-conflict" in o for o in result.offenders),
                result.offenders,
            )

    def test_mention_inside_the_checkers_own_file_does_not_count_as_a_reference(self):
        # task0027 AC-1/AC-2 (reviews/round2.yaml finding bs11): the
        # reference direction excludes only the policy file, not the
        # checker itself, so a gate id named solely inside the checker's own
        # comments would be reported as referenced forever -- surviving
        # even if every real document dropped it. Build a synthetic tree
        # where the checker's own (copied) source is the ONLY place the
        # gate id occurs; it must still be reported unreferenced.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_policy(root, ["test-ns.self-only-gate"])
            write(
                root / "em-workflow" / "scripts" / "check-plugin-invariants.py",
                "# This comment names test-ns.self-only-gate as an example.\n",
            )
            result = cpi.check_gate_id_coverage(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(
                any("test-ns.self-only-gate" in o for o in result.offenders),
                result.offenders,
            )

    def test_real_repository_gate_ids_named_in_the_checkers_comments_are_still_referenced(self):
        # task0027 AC-3: `create-spec.design-system` and
        # `design-system.reclassify` are the two policy keys the checker's
        # own comments happen to name as literal substrings (Test Notes).
        # After excluding the checker's own file from the reference scan,
        # both must still be reported as referenced against the real
        # repository, because other documents genuinely reference them --
        # distinguishing a genuine reference from the self-match this task
        # removes.
        result = cpi.check_gate_id_coverage(str(REPO_ROOT))
        unreferenced = [o for o in result.offenders if "never referenced" in o]
        self.assertFalse(
            any("create-spec.design-system" in o for o in unreferenced), unreferenced
        )
        self.assertFalse(
            any("design-system.reclassify" in o for o in unreferenced), unreferenced
        )


class TestDomainsVocabularyParity(unittest.TestCase):
    def test_passes_when_sets_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "em-workflow" / "references" / "review-rules.yaml",
                "# domains vocabulary (fixed, 2 values):\n"
                "#   auth / input-handling\n"
                "# complexity vocabulary: low / medium / high\n",
            )
            write(
                root / "em-workflow" / "skills" / "plan-writing" / "SKILL.md",
                "## domains criteria (assign every value that materially applies)\n\n"
                "- `auth` — auth stuff.\n"
                "- `input-handling` — parsing stuff.\n\n"
                "## Next Section\n",
            )
            result = cpi.check_domains_vocabulary_parity(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_fails_when_review_rules_has_an_extra_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "em-workflow" / "references" / "review-rules.yaml",
                "# domains vocabulary (fixed, 2 values):\n"
                "#   auth / input-handling\n"
                "# complexity vocabulary: low / medium / high\n",
            )
            write(
                root / "em-workflow" / "skills" / "plan-writing" / "SKILL.md",
                "## domains criteria (assign every value that materially applies)\n\n"
                "- `auth` — auth stuff.\n\n"
                "## Next Section\n",
            )
            result = cpi.check_domains_vocabulary_parity(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(any("input-handling" in o for o in result.offenders), result.offenders)

    def test_fails_when_plan_writing_has_an_extra_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "em-workflow" / "references" / "review-rules.yaml",
                "# domains vocabulary (fixed, 1 values):\n"
                "#   auth\n"
                "# complexity vocabulary: low / medium / high\n",
            )
            write(
                root / "em-workflow" / "skills" / "plan-writing" / "SKILL.md",
                "## domains criteria (assign every value that materially applies)\n\n"
                "- `auth` — auth stuff.\n"
                "- `ui` — ui stuff.\n\n"
                "## Next Section\n",
            )
            result = cpi.check_domains_vocabulary_parity(str(root))
            self.assertFalse(result.passed)
            self.assertTrue(any("ui" in o for o in result.offenders), result.offenders)


class TestForbiddenTaskAssignmentHeading(unittest.TestCase):
    def test_passes_when_no_agent_has_the_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "em-workflow" / "agents" / "implementer.md",
                "# Implementer Agent\n\nBody.\n",
            )
            result = cpi.check_forbidden_task_assignment_heading(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_fails_when_an_agent_has_the_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "em-workflow" / "agents" / "implementer.md",
                "# Implementer Agent\n\n# Task assignment\ntask_id: task0001\n",
            )
            result = cpi.check_forbidden_task_assignment_heading(str(root))
            self.assertFalse(result.passed)
            self.assertIn("implementer.md", result.offenders)


class TestFixtureBranchCoverage(unittest.TestCase):
    DESIGN_TABLE = (
        "#### 5.11.5 fixture\n\n"
        "| kind | 網羅すべき分岐 |\n"
        "|---|---|\n"
        "| `worker-result` | worker ごとの status |\n"
        "| `question-packet` | answer_mode の境界 |\n"
    )

    def test_passes_when_every_kind_has_a_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "feature-docs" / "agent-separation" / "design-input.md",
                self.DESIGN_TABLE,
            )
            write(
                root
                / "em-workflow"
                / "references"
                / "fixtures"
                / "worker-result"
                / "analyst.full.valid.yaml",
                "ok\n",
            )
            write(
                root
                / "em-workflow"
                / "references"
                / "fixtures"
                / "question-packet.single-select.valid.yaml",
                "ok\n",
            )
            result = cpi.check_fixture_branch_coverage(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_fails_when_a_kind_has_no_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "feature-docs" / "agent-separation" / "design-input.md",
                self.DESIGN_TABLE,
            )
            write(
                root
                / "em-workflow"
                / "references"
                / "fixtures"
                / "worker-result"
                / "analyst.full.valid.yaml",
                "ok\n",
            )
            result = cpi.check_fixture_branch_coverage(str(root))
            self.assertFalse(result.passed)
            self.assertIn("question-packet", result.offenders)

    def test_fixture_with_non_conventional_name_does_not_count(self):
        # Edge case (Test Notes): a fixtures-directory file whose name
        # carries no kind marker must not silently satisfy any kind.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root / "feature-docs" / "agent-separation" / "design-input.md",
                self.DESIGN_TABLE,
            )
            write(
                root
                / "em-workflow"
                / "references"
                / "fixtures"
                / "worker-result"
                / "analyst.full.valid.yaml",
                "ok\n",
            )
            write(root / "em-workflow" / "references" / "fixtures" / "README.md", "notes\n")
            result = cpi.check_fixture_branch_coverage(str(root))
            self.assertFalse(result.passed)
            self.assertIn("question-packet", result.offenders)


class TestDigestReproducibility(unittest.TestCase):
    def test_check_passes(self):
        result = cpi.check_digest_reproducibility()
        self.assertTrue(result.passed, result.offenders)
        self.assertEqual(result.offenders, [])

    def test_compute_input_digest_is_stable_across_key_order(self):
        a = {"worker": "implementation-planner", "digest_inputs": {"a": "1", "b": "2"}}
        b = {"digest_inputs": {"b": "2", "a": "1"}, "worker": "implementation-planner"}
        self.assertEqual(cpi.compute_input_digest(a), cpi.compute_input_digest(b))

    def test_compute_input_digest_changes_with_real_content_change(self):
        # Proves the digest genuinely discriminates content -- not a stub
        # that always returns the same value.
        a = {"worker": "implementation-planner", "digest_inputs": {"a": "1"}}
        b = {"worker": "implementation-planner", "digest_inputs": {"a": "2"}}
        self.assertNotEqual(cpi.compute_input_digest(a), cpi.compute_input_digest(b))


# ---------------------------------------------------------------------------
# worker-digest-ownership task0004: synthetic tree for worker_digest_stance.
#
# Fictional names only (`stance-worker`, `stance-reader`, `stance-contract`)
# so this helper never writes a path another task's helper writes
# (IMPLEMENTATION.md "Checker extension protocol").
# ---------------------------------------------------------------------------

STANCE_ENVELOPE_PATH = ("em-workflow", "references", "contracts", "worker-envelope.md")
STANCE_SPEC_WRITER_CONTRACT_PATH = (
    "em-workflow",
    "references",
    "contracts",
    "spec-writer-contract.md",
)
STANCE_CONTRACT_PATH = ("em-workflow", "references", "contracts", "stance-contract.md")
STANCE_WORKER_PATH = ("em-workflow", "agents", "stance-worker.md")
STANCE_READER_PATH = ("em-workflow", "agents", "stance-reader.md")

# Owner stance sentences the check requires inside their owner sections.
ENVELOPE_OWNER_SENTENCE = "The worker does not compute digests"
SPEC_WRITER_OWNER_SENTENCE = (
    "A worker never returns `blocked` because it\ncannot compute a digest."
)

STANCE_CITATION_I = (
    'The "`written_artifacts` reporting" section of\n'
    "`references/contracts/worker-envelope.md` states that this worker lists\n"
    "paths only and that the orchestrator computes every digest.\n"
)
STANCE_CITATION_II = (
    'The "Who verifies `expect_digest`" section of\n'
    "`references/contracts/spec-writer-contract.md` states that this worker\n"
    "never computes or re-verifies a digest and never returns `blocked`\n"
    "because it cannot compute one.\n"
)


def stance_envelope_doc(applies_rows=("`stance-worker` (new)", "`stance-reader` (revised)")):
    """A synthetic worker-envelope.md: an Applicability table whose `Applies`
    column carries `applies_rows` (annotations included), plus the owner
    section for the path-only `written_artifacts` stance."""
    rows = "".join(f"| {cell} | `implementer` |\n" for cell in applies_rows)
    return (
        "# Worker Envelope Contract (synthetic)\n\n"
        "## Applicability\n\n"
        "The envelope applies to the workers in the left column.\n\n"
        "| Applies | Does not apply |\n"
        "|---|---|\n"
        f"{rows}\n"
        "## `written_artifacts` reporting\n\n"
        "Whenever a worker writes any file, it lists every written path in\n"
        "`written_artifacts`. "
        f"{ENVELOPE_OWNER_SENTENCE}: an entry's\n"
        "`sha256` is `null` or absent.\n\n"
        "## Exclusivity assumption during dispatch\n\n"
        "Only the orchestrator and the dispatched worker touch the worktree.\n"
    )


def stance_agent_doc(name, tools, body=""):
    return (
        "---\n"
        f"name: {name}\n"
        "description: Synthetic worker used by the invariant checker tests.\n"
        f"tools: {tools}\n"
        "---\n\n"
        f"# {name}\n\n"
        f"{body}"
    )


def stance_worker_body(
    citation_i=STANCE_CITATION_I,
    citation_ii=STANCE_CITATION_II,
    contract_line="Follow `references/contracts/stance-contract.md`.\n",
):
    parts = [part for part in (contract_line, citation_i, citation_ii) if part]
    return "\n".join(parts)


def add_stance_worker_files(root):
    """worker_digest_stance's passing synthetic files: an envelope document
    listing `stance-worker` (annotated) and the read-only `stance-reader`; both
    agent files; a fictional contract that cites the envelope; the spec-writer
    owner section; and one dispatch line per fictional agent so the
    agent/dispatch parity check passes."""
    write(root.joinpath(*STANCE_ENVELOPE_PATH), stance_envelope_doc())
    write(
        root.joinpath(*STANCE_SPEC_WRITER_CONTRACT_PATH),
        "# spec-writer Worker Contract (synthetic)\n\n"
        "This contract extends `references/contracts/worker-envelope.md`.\n\n"
        "## `write_policy`\n\n"
        "### Who verifies `expect_digest`\n\n"
        "The orchestrator verifies `expect_digest`, not the worker. The worker\n"
        "does not compute digests. "
        f"{SPEC_WRITER_OWNER_SENTENCE}\n\n"
        "### Another subsection\n\n"
        "Unrelated text.\n",
    )
    write(
        root.joinpath(*STANCE_CONTRACT_PATH),
        "# stance-worker Contract (synthetic)\n\n"
        "This contract extends `references/contracts/worker-envelope.md`.\n",
    )
    write(
        root.joinpath(*STANCE_WORKER_PATH),
        stance_agent_doc("stance-worker", "Read, Write", stance_worker_body()),
    )
    write(
        root.joinpath(*STANCE_READER_PATH),
        stance_agent_doc("stance-reader", "Read, Glob, Grep", "Reads only.\n"),
    )
    write(
        root / "em-workflow" / "references" / "stance-dispatch.md",
        'Dispatch `Task(subagent_type="em-workflow:stance-worker")` and\n'
        '`Task(subagent_type="em-workflow:stance-reader")`.\n',
    )


def build_passing_repo(root):
    """A synthetic tree satisfying every one of the seven checks at once,
    for the CLI-level exit-code tests (AC-1)."""
    write(root / "em-workflow" / "agents" / "implementer.md", "# Implementer\n")
    write(
        root / "em-workflow" / "references" / "phases" / "create-spec-phase.md",
        "Ask via gate ID `create-spec.feature-identity`.\n"
        'Dispatch `Task(subagent_type="em-workflow:implementer")`.\n',
    )
    write(
        root / "em-workflow" / "references" / "batch-policies.yaml",
        "gate_policies:\n  create-spec.feature-identity:\n    action: select\n"
        "    option_id: x\n",
    )
    write(
        root / "em-workflow" / "references" / "review-rules.yaml",
        "# domains vocabulary (fixed, 1 values):\n#   auth\n"
        "# complexity vocabulary: low / medium / high\n",
    )
    write(
        root / "em-workflow" / "skills" / "plan-writing" / "SKILL.md",
        "## domains criteria (assign every value that materially applies)\n\n"
        "- `auth` — auth stuff.\n\n## Next\n",
    )
    add_stance_worker_files(root)
    write(
        root / "feature-docs" / "agent-separation" / "design-input.md",
        "#### 5.11.5 fixture\n\n| kind | 網羅すべき分岐 |\n|---|---|\n"
        "| `worker-result` | x |\n",
    )
    write(
        root / "em-workflow" / "references" / "fixtures" / "worker-result" / "a.valid.yaml",
        "ok\n",
    )


class TestCli(unittest.TestCase):
    """AC-1: the CLI accepts a repository root and exits 0 / 1 / 2."""

    def test_exit_0_when_all_checks_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_exit_1_when_a_check_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            # Break agent/dispatch parity: an orphan definition.
            write(root / "em-workflow" / "agents" / "orphan.md", "# orphan\n")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("orphan", proc.stdout)

    def test_exit_2_when_repository_root_does_not_exist(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "/nonexistent/path/does/not/exist"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_exit_2_when_no_argument_given(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)


class TestRepositoryLevelInvariant(unittest.TestCase):
    """task0021 AC-1 / AC-7 (reviews/round1.yaml finding as2): every prior
    case above runs the checker against a synthetic tree, and REPO_ROOT
    (defined at module scope) was never once used as a target -- which is
    why the suite could pass while `check-plugin-invariants.py .` failed on
    the very same tree. This is the case that makes the checks invariants
    rather than only exercised.

    This is dispatched last, after every sibling rework task has merged
    (task0021.md Design/Test Notes): the assertion below is only honestly
    satisfiable once agent_dispatch_parity's dispatch-trio fix, the batch
    gate jurisdiction fix and the stale-agent-reference fix are all present
    at this worktree's branch point."""

    def test_checker_exits_cleanly_against_the_repository_root(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(REPO_ROOT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class TestSinglePassTraversal(unittest.TestCase):
    """task0021 AC-4 (reviews/round1.yaml finding as22): agent_dispatch_
    parity and stale_references used to each call iter_repo_files(root) and
    read_text() on every file independently, walking and reading the whole
    tree twice. Assert the traversal count rather than timing (task0021.md
    Test Notes), by counting invocations of iter_repo_files -- the shared
    traversal helper -- while running both checks together via
    run_all_checks()."""

    def test_iter_repo_files_invoked_once_when_both_checks_run_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            with patch.object(cpi, "iter_repo_files", wraps=cpi.iter_repo_files) as mock_iter:
                results = cpi.run_all_checks(str(root))
            self.assertEqual(mock_iter.call_count, 1, "expected a single shared traversal")
            names = {r.name for r in results}
            self.assertIn("agent_dispatch_parity", names)
            self.assertIn("stale_references", names)
            for result in results:
                if result.name in ("agent_dispatch_parity", "stale_references"):
                    self.assertTrue(result.passed, result.offenders)

    def test_each_check_remains_independently_callable_with_its_own_traversal(self):
        # AC-2 (task0014) must still hold: calling one check alone still
        # works correctly (its own single traversal), independent of the
        # other -- run_all_checks() is what shares the walk, not the public
        # functions losing their standalone meaning.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            with patch.object(cpi, "iter_repo_files", wraps=cpi.iter_repo_files) as mock_iter:
                agent_result = cpi.check_agent_dispatch_parity(str(root))
            self.assertEqual(mock_iter.call_count, 1)
            self.assertTrue(agent_result.passed, agent_result.offenders)

            with patch.object(cpi, "iter_repo_files", wraps=cpi.iter_repo_files) as mock_iter:
                stale_result = cpi.check_stale_references(str(root))
            self.assertEqual(mock_iter.call_count, 1)
            self.assertTrue(stale_result.passed, stale_result.offenders)


# ---------------------------------------------------------------------------
# worker-digest-ownership task0004: target-worker derivation and the
# worker_digest_stance check.
# ---------------------------------------------------------------------------


def edit_file(path, old, new):
    """Replace `old` with `new` in a synthetic file, asserting `old` is
    really there so a mutation can never silently become a no-op."""
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def worker_digest_stance_offenders(root):
    result = cpi.check_worker_digest_stance(str(root))
    return result, "\n".join(result.offenders)


class TestDigestStanceTargetDerivation(unittest.TestCase):
    """AC-2: the helper derives target workers from worker-envelope.md's
    Applicability table and the agents' frontmatter tools; nothing is
    hard-coded."""

    def derive(self, root):
        return cpi.derive_digest_stance_workers(str(root))

    def make_tree(self, root, applies_rows, agents):
        write(root.joinpath(*STANCE_ENVELOPE_PATH), stance_envelope_doc(applies_rows))
        for name, tools in agents.items():
            write(root / "em-workflow" / "agents" / f"{name}.md", stance_agent_doc(name, tools))

    def test_real_repository_set_is_non_empty_and_matches_an_independent_reading(self):
        envelope = (REPO_ROOT.joinpath(*STANCE_ENVELOPE_PATH)).read_text(encoding="utf-8")
        section = envelope.split("## Applicability", 1)[1].split("\n## ", 1)[0]
        applies = re.findall(r"^\|\s*`([^`]+)`", section, re.MULTILINE)
        expected = set()
        for name in applies:
            agent_text = (REPO_ROOT / "em-workflow" / "agents" / f"{name}.md").read_text(
                encoding="utf-8"
            )
            tools_line = re.search(r"^tools:\s*(.*)$", agent_text, re.MULTILINE).group(1)
            tools = [t.strip() for t in tools_line.split(",")]
            if any(t in ("Write", "Edit", "MultiEdit", "NotebookEdit") for t in tools) and not any(
                t.startswith("Bash") for t in tools
            ):
                expected.add(name)
        derived = cpi.derive_digest_stance_workers(str(REPO_ROOT))
        self.assertTrue(derived, "derived set must not be empty")
        self.assertEqual(set(derived), expected)
        self.assertEqual(derived, sorted(derived))

    def test_real_repository_set_excludes_the_read_only_analyst(self):
        self.assertNotIn(
            "requirements-analyst", cpi.derive_digest_stance_workers(str(REPO_ROOT))
        )

    def test_synthetic_tree_strips_annotations_and_derives_fictional_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            # `stance-worker` carries the annotation (new) in the table; the
            # read-only `stance-reader` is dropped.
            self.assertEqual(self.derive(root), ["stance-worker"])

    def test_each_file_writing_tool_qualifies(self):
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.make_tree(root, ["`alpha-worker`"], {"alpha-worker": f"Read, {tool}"})
                self.assertEqual(self.derive(root), ["alpha-worker"])

    def test_bash_holding_worker_is_dropped_in_every_form(self):
        for tools in ("Read, Write, Bash", "Bash, Write", "Read, Write, Bash(git status:*)"):
            with self.subTest(tools=tools), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.make_tree(root, ["`alpha-worker`"], {"alpha-worker": tools})
                self.assertEqual(self.derive(root), [])

    def test_worker_without_a_writing_tool_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_tree(root, ["`alpha-worker`"], {"alpha-worker": "Read, Glob, Grep"})
            self.assertEqual(self.derive(root), [])

    def test_missing_agent_file_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_tree(
                root,
                ["`alpha-worker`", "`ghost-worker` (new)"],
                {"alpha-worker": "Read, Write"},
            )
            self.assertEqual(self.derive(root), ["alpha-worker"])

    def test_tools_written_as_a_yaml_block_list_are_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root.joinpath(*STANCE_ENVELOPE_PATH), stance_envelope_doc(["`alpha-worker`"]))
            write(
                root / "em-workflow" / "agents" / "alpha-worker.md",
                "---\nname: alpha-worker\ntools:\n  - Read\n  - Write\n---\n\n# alpha\n",
            )
            self.assertEqual(self.derive(root), ["alpha-worker"])

    def test_result_is_sorted_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_tree(
                root,
                ["`zeta-worker`", "`alpha-worker` (new)", "`zeta-worker` (revised)"],
                {"zeta-worker": "Read, Write", "alpha-worker": "Read, Edit"},
            )
            self.assertEqual(self.derive(root), ["alpha-worker", "zeta-worker"])

    def test_only_the_applies_column_is_read(self):
        # `implementer` sits in the "Does not apply" column of every synthetic
        # row and has a writing tool; it must never be derived.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_tree(
                root,
                ["`alpha-worker`"],
                {"alpha-worker": "Read, Write", "implementer": "Read, Write"},
            )
            self.assertEqual(self.derive(root), ["alpha-worker"])

    def test_no_envelope_document_gives_an_empty_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.derive(Path(tmp)), [])

    def test_worker_name_that_is_not_a_plain_name_is_never_joined_into_a_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_tree(root, ["`../agents/alpha-worker`"], {"alpha-worker": "Read, Write"})
            self.assertEqual(self.derive(root), [])


class TestWorkerDigestStanceCheck(unittest.TestCase):
    """AC-3: worker_digest_stance passes on the real repository and fails on
    synthetic trees, naming the offending worker or document."""

    def test_passes_on_the_real_repository(self):
        result = cpi.check_worker_digest_stance(str(REPO_ROOT))
        self.assertEqual(result.name, "worker_digest_stance")
        self.assertTrue(result.passed, result.offenders)
        self.assertEqual(result.offenders, [])

    def test_passes_on_the_synthetic_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            result = cpi.check_worker_digest_stance(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_is_the_last_result_of_run_all_checks_and_the_first_seven_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            names = [r.name for r in cpi.run_all_checks(str(root))]
        self.assertEqual(
            names[:7],
            [
                "agent_dispatch_parity",
                "stale_references",
                "gate_id_coverage",
                "domains_vocabulary_parity",
                "forbidden_task_assignment_heading",
                "fixture_branch_coverage",
                "digest_reproducibility",
            ],
        )
        self.assertEqual(names[-1], "worker_digest_stance")

    def test_reads_fixed_paths_and_never_walks_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            with patch.object(cpi, "iter_repo_files", wraps=cpi.iter_repo_files) as mock_iter:
                cpi.check_worker_digest_stance(str(root))
            self.assertEqual(mock_iter.call_count, 0)

    def test_fails_when_a_target_prompt_lacks_citation_i(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            edit_file(root.joinpath(*STANCE_WORKER_PATH), STANCE_CITATION_I, "")
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("stance-worker", text)
            self.assertIn("worker-envelope.md", text)

    def test_fails_when_a_target_prompt_lacks_citation_ii(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            edit_file(root.joinpath(*STANCE_WORKER_PATH), STANCE_CITATION_II, "")
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("stance-worker", text)
            self.assertIn("Who verifies", text)

    def test_citation_path_and_section_name_in_different_paragraphs_do_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            edit_file(
                root.joinpath(*STANCE_WORKER_PATH),
                'The "`written_artifacts` reporting" section of\n'
                "`references/contracts/worker-envelope.md`",
                'The "`written_artifacts` reporting" section of\n\n'
                "`references/contracts/worker-envelope.md`",
            )
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("stance-worker", text)

    def test_citations_may_share_one_paragraph_and_break_lines_anywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            body = stance_worker_body(
                citation_i="",
                citation_ii=(
                    'The "`written_artifacts`\nreporting" section of\n'
                    "`references/contracts/worker-envelope.md`\n"
                    "and the \"Who verifies\n`expect_digest`\" section of\n"
                    "`references/contracts/spec-writer-contract.md`\n"
                    "state that this worker lists paths only, and that it never computes a\n"
                    "digest.\n"
                ),
            )
            write(
                root.joinpath(*STANCE_WORKER_PATH),
                stance_agent_doc("stance-worker", "Read, Write", body),
            )
            result = cpi.check_worker_digest_stance(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_fails_when_a_target_prompt_cites_no_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_WORKER_PATH),
                stance_agent_doc("stance-worker", "Read, Write", "Writes files.\n"),
            )
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("stance-worker", text)
            self.assertIn("cites no", text)

    def test_fails_when_a_cited_contract_does_not_cite_the_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_CONTRACT_PATH),
                "# stance-worker Contract (synthetic)\n\nIt extends nothing.\n",
            )
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("stance-contract.md", text)

    def test_fails_when_a_cited_contract_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            root.joinpath(*STANCE_CONTRACT_PATH).unlink()
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("stance-contract.md", text)

    def test_fails_when_the_envelope_owner_sentence_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            edit_file(
                root.joinpath(*STANCE_ENVELOPE_PATH),
                ENVELOPE_OWNER_SENTENCE,
                "Digests are somebody else's concern",
            )
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("worker-envelope.md", text)

    def test_fails_when_the_spec_writer_contract_owner_sentence_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            edit_file(
                root.joinpath(*STANCE_SPEC_WRITER_CONTRACT_PATH),
                SPEC_WRITER_OWNER_SENTENCE,
                "Nothing is promised here.",
            )
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("spec-writer-contract.md", text)

    def test_an_owner_sentence_outside_its_section_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            envelope = root.joinpath(*STANCE_ENVELOPE_PATH)
            edit_file(envelope, ENVELOPE_OWNER_SENTENCE, "Digests are not discussed")
            # The sentence now lives in the next section instead.
            edit_file(
                envelope,
                "Only the orchestrator and the dispatched worker touch the worktree.",
                f"{ENVELOPE_OWNER_SENTENCE}.",
            )
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("worker-envelope.md", text)

    def test_an_owner_sentence_broken_across_lines_still_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            edit_file(
                root.joinpath(*STANCE_SPEC_WRITER_CONTRACT_PATH),
                "A worker never returns `blocked` because it\ncannot compute a digest.",
                "A  worker never returns `blocked`\nbecause it cannot\ncompute a digest.",
            )
            result = cpi.check_worker_digest_stance(str(root))
            self.assertTrue(result.passed, result.offenders)

    def test_fails_when_a_listed_worker_has_no_agent_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            edit_file(
                root.joinpath(*STANCE_ENVELOPE_PATH),
                "| `stance-reader` (revised) |",
                "| `ghost-worker` (new) |",
            )
            result, text = worker_digest_stance_offenders(root)
            self.assertFalse(result.passed)
            self.assertIn("ghost-worker", text)


class TestWorkerDirectedDigestInstruction(unittest.TestCase):
    """AC-4: a worker-directed digest instruction in a target prompt or a
    cited contract fails the check; negated, orchestrator-attributed and
    passive sentences do not."""

    WORKER_NAMES = ["stance-worker"]

    FLAGGED = {
        "imperative_with_leading_clause": (
            "Before writing, compute the sha256 of each target and compare it with "
            "`expect_digest`."
        ),
        "worker_subject": "The worker computes the digest of every written path.",
        "second_person_subject": "You verify every `expect_digest` before writing.",
        "this_agent_subject": "This agent hashes each written file.",
        "own_name_subject": "stance-worker compares the hash with expect_digest before it writes.",
        "modal_worker_subject": "The worker must compute the sha256 of every written path.",
        "imperative_after_adverb": "Always re-verify the digest of each target.",
        "imperative_second_clause": "Write the file, then compute its sha256.",
        "imperative_recompute": "Recompute the sha256 of every target after writing.",
        "line_break_inside_the_sentence": "The worker computes\nthe digest of\nevery written path.",
        "table_cell": "| compute the sha256 of every target | before dispatch |",
        "list_item": "- Compute the digest of each file.\n- Return the report.",
        "negated_neighbour_does_not_shield": (
            "Compute the sha256 of each target. The worker never returns `blocked`."
        ),
        "japanese_worker_subject": "worker は書き込み前に expect_digest を照合する。",
        "japanese_imperative": "書き込み後に written_artifacts の sha256 を計算すること。",
        "calculate_the_hash": "Calculate the hash of every file the worker wrote.",
    }

    NOT_FLAGGED = {
        "negated_worker_subject": "The worker does not compute digests.",
        "negated_never": "A worker never returns `blocked` because it cannot compute a digest.",
        "negated_imperative": "Do not compute or re-verify digests.",
        "negated_contraction": "The worker doesn't verify the sha256.",
        "orchestrator_attributed": (
            "The orchestrator computes the sha256 of every `targets` path and compares it "
            "with `expect_digest`."
        ),
        "japanese_orchestrator": "digest の照合はオーケストレーターが行う。",
        "japanese_negated": "worker は digest を計算しない。",
        "passive_with_no_actor": "Every digest is computed before dispatch.",
        "passive_with_orchestrator": "The sha256 is verified by the orchestrator.",
        "paths_only_with_null": "The worker lists each written path with `sha256: null`.",
        "compound_input_digest": "Compute the input_digest from the digest_inputs map.",
        "compound_answers_digest": "The worker copies `answers_digest` verbatim and recomputes nothing.",
        "compound_base_input_digest": "Compare it with the base_input_digest value.",
        "verb_without_a_digest_term": "Compare the two lists and verify the paths exist.",
        "digest_term_without_a_verb": "Each entry carries a sha256 field.",
        "subject_is_another_party": "The reviewer computes the sha256 of nothing.",
        "orchestrator_owns_it": "Verifying `expect_digest` is the orchestrator's job.",
        "unrelated_prose": "Write REQUIREMENTS.md and SPEC.md from the analysis.",
    }

    def find(self, text):
        return cpi.find_worker_directed_digest_instructions(text, self.WORKER_NAMES)

    def test_each_flagged_example_is_reported(self):
        for label, text in self.FLAGGED.items():
            with self.subTest(label=label):
                self.assertTrue(self.find(text), f"not flagged: {text!r}")

    def test_each_unflagged_example_is_left_alone(self):
        for label, text in self.NOT_FLAGGED.items():
            with self.subTest(label=label):
                self.assertEqual(self.find(text), [], f"wrongly flagged: {text!r}")

    def test_line_break_positions_never_change_the_verdict(self):
        for label, text in {**self.FLAGGED, **self.NOT_FLAGGED}.items():
            if "\n" in text or text.startswith(("-", "|")):
                continue
            words = text.split(" ")
            rewrapped = "\n".join(" ".join(words[i : i + 3]) for i in range(0, len(words), 3))
            with self.subTest(label=label):
                self.assertEqual(bool(self.find(text)), bool(self.find(rewrapped)), rewrapped)

    def test_a_flagged_sentence_in_a_target_prompt_fails_the_check(self):
        for label in ("imperative_with_leading_clause", "worker_subject"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                build_passing_repo(root)
                prompt = root.joinpath(*STANCE_WORKER_PATH)
                prompt.write_text(
                    prompt.read_text(encoding="utf-8") + "\n" + self.FLAGGED[label] + "\n",
                    encoding="utf-8",
                )
                result, text = worker_digest_stance_offenders(root)
                self.assertFalse(result.passed)
                self.assertIn("stance-worker", text)

    def test_the_two_acceptance_examples_inside_a_cited_contract_fail_the_check(self):
        for label in ("imperative_with_leading_clause", "worker_subject"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                build_passing_repo(root)
                contract = root.joinpath(*STANCE_CONTRACT_PATH)
                contract.write_text(
                    contract.read_text(encoding="utf-8") + "\n" + self.FLAGGED[label] + "\n",
                    encoding="utf-8",
                )
                result, text = worker_digest_stance_offenders(root)
                self.assertFalse(result.passed)
                self.assertIn("stance-contract.md", text)

    def test_negated_orchestrator_attributed_and_passive_sentences_pass_the_check(self):
        sentences = [
            "The worker does not compute digests.",
            "The orchestrator computes the sha256 of every written path.",
            "Every digest is computed before dispatch.",
        ]
        for target in (STANCE_WORKER_PATH, STANCE_CONTRACT_PATH):
            for sentence in sentences:
                with self.subTest(target=target[-1], sentence=sentence), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    build_passing_repo(root)
                    path = root.joinpath(*target)
                    path.write_text(
                        path.read_text(encoding="utf-8") + "\n" + sentence + "\n",
                        encoding="utf-8",
                    )
                    result = cpi.check_worker_digest_stance(str(root))
                    self.assertTrue(result.passed, result.offenders)

    def test_a_flagged_sentence_in_a_non_target_document_is_not_this_checks_business(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            reader = root.joinpath(*STANCE_READER_PATH)
            reader.write_text(
                reader.read_text(encoding="utf-8") + "\n" + self.FLAGGED["worker_subject"] + "\n",
                encoding="utf-8",
            )
            result = cpi.check_worker_digest_stance(str(root))
            self.assertTrue(result.passed, result.offenders)


class TestEmptyTargetSetFails(unittest.TestCase):
    """AC-5 (TS8): an empty derived set is never a pass."""

    def assert_fails_naming_the_empty_set(self, root):
        result = cpi.check_worker_digest_stance(str(root))
        self.assertFalse(result.passed, "an empty target set must not pass")
        self.assertTrue(
            any("no target worker" in o for o in result.offenders), result.offenders
        )

    def test_no_envelope_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            root.joinpath(*STANCE_ENVELOPE_PATH).unlink()
            self.assert_fails_naming_the_empty_set(root)

    def test_a_tree_with_no_files_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_fails_naming_the_empty_set(Path(tmp))

    def test_no_applicability_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_ENVELOPE_PATH),
                "# Worker Envelope Contract (synthetic)\n\n"
                "## `written_artifacts` reporting\n\n"
                f"{ENVELOPE_OWNER_SENTENCE}.\n",
            )
            self.assert_fails_naming_the_empty_set(root)

    def test_applicability_section_without_a_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_ENVELOPE_PATH),
                "# Worker Envelope Contract (synthetic)\n\n"
                "## Applicability\n\nEvery worker applies.\n\n"
                "## `written_artifacts` reporting\n\n"
                f"{ENVELOPE_OWNER_SENTENCE}.\n",
            )
            self.assert_fails_naming_the_empty_set(root)

    def test_table_without_applies_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_ENVELOPE_PATH),
                "# Worker Envelope Contract (synthetic)\n\n"
                "## Applicability\n\n"
                "| Applies | Does not apply |\n|---|---|\n| | `implementer` |\n\n"
                "## `written_artifacts` reporting\n\n"
                f"{ENVELOPE_OWNER_SENTENCE}.\n",
            )
            self.assert_fails_naming_the_empty_set(root)

    def test_table_without_an_applies_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_ENVELOPE_PATH),
                "# Worker Envelope Contract (synthetic)\n\n"
                "## Applicability\n\n"
                "| Worker | Notes |\n|---|---|\n| `stance-worker` | x |\n\n"
                "## `written_artifacts` reporting\n\n"
                f"{ENVELOPE_OWNER_SENTENCE}.\n",
            )
            self.assert_fails_naming_the_empty_set(root)

    def test_only_bash_holding_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_WORKER_PATH),
                stance_agent_doc("stance-worker", "Read, Write, Bash", stance_worker_body()),
            )
            self.assert_fails_naming_the_empty_set(root)

    def test_only_write_less_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_WORKER_PATH),
                stance_agent_doc("stance-worker", "Read, Glob, Grep", stance_worker_body()),
            )
            self.assert_fails_naming_the_empty_set(root)

    def test_cli_exits_1_on_an_empty_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_passing_repo(root)
            write(
                root.joinpath(*STANCE_WORKER_PATH),
                stance_agent_doc("stance-worker", "Read", stance_worker_body()),
            )
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(root)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("worker_digest_stance", proc.stdout)


class TestRealPromptCitationPlacement(unittest.TestCase):
    """AC-1: where the stance citations sit in the real agent prompts. The
    worker_digest_stance check proves every derived worker carries both
    citations; these cases pin the two placements that other tests fix
    byte-for-byte or section-wise."""

    @staticmethod
    def paragraph_containing(text, needle):
        for block in re.split(r"\n[ \t]*\n", text):
            normalized = " ".join(block.split())
            if needle in normalized:
                return normalized
        raise AssertionError(f"no paragraph contains {needle!r}")

    def test_the_spec_writer_digest_bullet_keeps_its_phrases_and_carries_both_citations(self):
        text = (REPO_ROOT / "em-workflow" / "agents" / "spec-writer.md").read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for phrase in (
            "Do not compute or re-verify digests.",
            "Never return `blocked` because you cannot compute a digest.",
            "`sha256: null`",
        ):
            self.assertIn(phrase, normalized)
        paragraph = self.paragraph_containing(text, "Do not compute or re-verify digests.")
        for token in (
            "references/contracts/worker-envelope.md",
            "`written_artifacts` reporting",
            "references/contracts/spec-writer-contract.md",
            "Who verifies `expect_digest`",
        ):
            self.assertIn(token, paragraph)

    def test_the_planner_citations_sit_outside_step_4_and_before_the_gate_vocabulary(self):
        text = (REPO_ROOT / "em-workflow" / "agents" / "implementation-planner.md").read_text(
            encoding="utf-8"
        )
        step4_start = text.index("### 4. ")
        step4_end = text.index("### 5. ", step4_start)
        vocabulary_start = text.index("## Gate option vocabulary")
        self.assertNotIn("expect_digest", text[step4_start:step4_end])
        for name_pattern in (
            r'"`written_artifacts`\s+reporting"',
            r'"Who\s+verifies\s+`expect_digest`"',
        ):
            positions = [m.start() for m in re.finditer(name_pattern, text)]
            self.assertTrue(positions, f"{name_pattern} not cited")
            self.assertTrue(
                any(step4_end <= pos < vocabulary_start for pos in positions),
                f"{name_pattern} is not cited between step 4 and the gate vocabulary",
            )


if __name__ == "__main__":
    unittest.main()
