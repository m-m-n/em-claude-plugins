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


if __name__ == "__main__":
    unittest.main()
