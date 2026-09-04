"""Tests for task0005 (llm-led-review): the user-facing description of the
new review composition -- one non-Claude primary reviewer per perspective
(taken from the front of that perspective's `primary_chain`), a Claude
fallback only when a perspective's whole chain is unavailable, one Opus
evaluator subagent that evaluates each round, and the orchestrator deciding
the next action -- across `em-workflow/README.md`,
`em-workflow/skills/review/SKILL.md` and both plugin registries, together
with the accompanying version bump.

Covers task0005 Acceptance Criteria
(feature-docs/llm-led-review/tasks/task0005.md):

- AC-1: both registries carry the pinned version for em-workflow (0.1.59,
  past the 0.1.58 baseline), the two values are equal, and the em-review
  marketplace entry is byte-identical to before.
- AC-2: both em-workflow descriptions state the new composition and no
  longer describe the review step as a Claude reviewer with conditional
  cross-model validation.
- AC-3: README.md's agent table lists `review-evaluator` with its role,
  marks `reviewer` fallback-only and `codex-reviewer` as a primary
  reviewer.
- AC-4: README.md's review section describes the one-reviewer-per-
  perspective dispatch, the Claude fallback, the evaluator step and the
  orchestrator's decision, and its chain table lists all six perspectives
  with exactly the chains pinned in IMPLEMENTATION.md.
- AC-5: README.md's prerequisites state that a missing codex CLI or a
  missing `vertex-review` plugin degrades to the Claude fallback rather
  than losing cross-validation, and no section of the README still
  describes a Claude + cross-model parallel double-run or agreement
  scoring.
- AC-6: skills/review/SKILL.md describes the same composition in its
  description and its bullets, still delegates to `review-phase.md` in
  standalone mode with no reviewer-selection logic of its own, and keeps
  its never-commit, `--report-only`, round-record-path and auto-apply
  statements.
- AC-7: this module (below) asserts AC-1..AC-6. The two full-suite
  commands (`python3 -m unittest discover -s tests` and
  `python3 em-workflow/scripts/check-plugin-invariants.py .`) exiting 0 is
  a CLI-level property that this module cannot assert about itself without
  recursion; it is verified by actually running both commands, recorded in
  the implementer report.

Per the task plan's Test Notes: JSON is parsed with the standard library
and the marketplace entry is selected by `name`, mirroring
`tests/test_plugin_version_parity.py` (not imported from there -- this
module stays independently runnable, per test/README.md). The
version-equality check reads both files' values and compares them
programmatically rather than hard-coding the same literal string in two
places. The chain-table literals are copied from IMPLEMENTATION.md's Shared
Components table, never read from `references/reviewers.yaml` (that file
carries its new chains only after integration). Assertions include the
negative cases -- old wording no longer present -- since those are what
actually prove the replacement happened rather than merely coexisting with
new wording.
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_MANIFEST_PATH = REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
README_PATH = REPO_ROOT / "em-workflow" / "README.md"
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "review" / "SKILL.md"

# Pre-task baseline (IMPLEMENTATION.md Shared Components, "Plugin version"):
# both registries read 0.1.58 before this task's edit; the pinned value
# this task must land is 0.1.59.
BASELINE_VERSION = "0.1.58"
PINNED_VERSION = "0.1.59"

# The em-review marketplace entry as it read before this task -- must stay
# byte-identical (task0005.md Out of Scope: "The em-review plugin's
# marketplace entry ... must not be modified").
EXPECTED_EM_REVIEW_ENTRY = {
    "name": "em-review",
    "description": (
        "Standalone version of the em-workflow review phase. "
        "/em-review:multi-review reviews the current git diff (whole "
        "codebase when no diff) with two-layer dynamic perspective "
        "selection, skill-injected generic reviewers (Claude + "
        "conditional cross-model validation via GPT/Codex and, when the "
        "separately-installed vertex-review plugin is present, Vertex AI "
        "MaaS / Meta Muse through its LiteLLM harness), cross-model "
        "agreement scoring, and bounded auto-fix (≤ 3 loops, skip "
        "with --report-only). Never commits; records default to /tmp "
        "(--records <dir> to override). Also reviews GitHub PRs by "
        "number/URL (report-only)."
    ),
    "author": {"name": "em"},
    "category": "code-review",
    "source": "./em-review",
}

# IMPLEMENTATION.md Shared Components, "Primary chains" -- copied here
# verbatim per Test Notes (never read from references/reviewers.yaml,
# which does not carry this feature's edit inside a task worktree).
PINNED_CHAINS = {
    "security": "codex → litellm `muse-spark`",
    "performance": "litellm `vertex-deepseek-v3.2` → litellm `muse-spark` → codex",
    "spec": "litellm `vertex-deepseek-v3.2` → litellm `muse-spark` → codex",
    "architecture": "litellm `vertex-glm-5` → litellm `muse-spark` → codex",
    "comprehensive": "codex → litellm `vertex-glm-5` → litellm `muse-spark`",
    "license": "codex → litellm `vertex-deepseek-v3.2` → litellm `muse-spark`",
}

# Wording that described the pre-task composition -- a Claude reviewer per
# perspective, conditionally doubled up with a cross-model reviewer, with
# agreement scored -- must not survive anywhere in scope after this task.
FORBIDDEN_README_PHRASES = [
    "クロスモデル二重化",
    "クロスモデル検証は強度の軸として分離",
    "で二重実行される",
    "クロスバリデーション用",
    "クロスバリデーションは全滅してクリーンにスキップされる",
    "全観点がチェーン末尾の Codex エントリに落ちる",
    "cross-model agreement",
    "agreement scoring",
]

FORBIDDEN_SKILL_PHRASES = [
    "条件によりクロスモデル検証",
    "Cross-model validation per review-rules.yaml",
    "cross-model agreement signal",
]

FORBIDDEN_DESCRIPTION_PHRASES = [
    "conditional cross-model validation",
    "cross-model agreement",
    "agreement scoring",
]


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array index, the
    marketplace plugin list's order is not a contract."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _version_tuple(version):
    """Parse a dot-separated version string into a tuple of ints, so
    comparison happens per-component and numerically -- never as a
    whole-string comparison (task0005.md Test Notes: version equality
    "must not be written as a substring match on a hard-coded string in
    two places; read both values and compare them")."""
    parts = (version or "").split(".")
    if not parts or not all(re.fullmatch(r"\d+", p) for p in parts):
        raise AssertionError(f"version {version!r} is not a dotted numeric sequence")
    return tuple(int(p) for p in parts)


def _find_row(text, cell_name):
    """Return the full markdown table row line whose first cell equals
    `cell_name` exactly (e.g. "reviewer", not "codex-reviewer")."""
    prefix = f"| {cell_name} |"
    for line in text.splitlines():
        if line.strip().startswith(prefix):
            return line
    raise AssertionError(f"no table row found for cell {cell_name!r}")


def _find_bullet(text, prefix):
    for line in text.splitlines():
        if line.strip().startswith(prefix):
            return line
    raise AssertionError(f"no bullet line found starting with {prefix!r}")


class TestRegistryVersions(unittest.TestCase):
    """AC-1: both registries carry the pinned version, and agree with each
    other via an actual value comparison (not a duplicated literal)."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.marketplace_entry = _marketplace_entry(cls.marketplace, "em-workflow")

    def test_plugin_manifest_version_is_pinned_value(self):
        self.assertEqual(self.manifest.get("version"), PINNED_VERSION)

    def test_marketplace_entry_version_is_pinned_value(self):
        self.assertEqual(self.marketplace_entry.get("version"), PINNED_VERSION)

    def test_registries_agree_by_reading_both_values(self):
        self.assertEqual(
            self.manifest.get("version"), self.marketplace_entry.get("version")
        )

    def test_version_is_strictly_past_baseline(self):
        self.assertGreater(
            _version_tuple(self.manifest.get("version")),
            _version_tuple(BASELINE_VERSION),
        )


class TestEmReviewEntryUnchanged(unittest.TestCase):
    """AC-1: the em-review marketplace entry is byte-identical to before
    this task (task0005.md Out of Scope forbids touching it)."""

    def test_em_review_entry_matches_pre_task_snapshot(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        self.assertEqual(entry, EXPECTED_EM_REVIEW_ENTRY)


class TestDescriptionsStateNewComposition(unittest.TestCase):
    """AC-2: both em-workflow descriptions state the new composition and
    drop the old "Claude reviewer + conditional cross-model validation"
    framing."""

    @classmethod
    def setUpClass(cls):
        manifest = _load_json(PLUGIN_MANIFEST_PATH)
        marketplace = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(marketplace, "em-workflow")
        cls.plugin_description = manifest.get("description", "")
        cls.marketplace_description = entry.get("description", "")

    def _assert_states_new_composition(self, text, label):
        self.assertIn("non-Claude primary reviewer", text, label)
        self.assertIn("Claude", text, label)
        self.assertTrue(
            "fallback" in text.lower() or "falling back" in text.lower(),
            f"{label}: no fallback wording found",
        )
        self.assertIn("Opus evaluator", text, label)
        self.assertIn("orchestrator decides the next action", text, label)
        for phrase in FORBIDDEN_DESCRIPTION_PHRASES:
            self.assertNotIn(phrase, text, f"{label}: forbidden phrase {phrase!r}")

    def test_plugin_manifest_description(self):
        self._assert_states_new_composition(self.plugin_description, "plugin.json")

    def test_marketplace_description(self):
        self._assert_states_new_composition(
            self.marketplace_description, "marketplace.json"
        )


class TestReadmeAgentTable(unittest.TestCase):
    """AC-3: the agent table gains review-evaluator, marks reviewer as
    fallback-only and codex-reviewer as a primary reviewer."""

    @classmethod
    def setUpClass(cls):
        cls.text = README_PATH.read_text(encoding="utf-8")

    def test_review_evaluator_row_names_opus_and_evaluation_role(self):
        row = _find_row(self.text, "review-evaluator")
        self.assertIn("Opus", row)
        self.assertIn("評価", row)

    def test_reviewer_row_is_fallback_only(self):
        row = _find_row(self.text, "reviewer")
        self.assertIn("フォールバック", row)

    def test_codex_reviewer_row_is_primary_reviewer(self):
        row = _find_row(self.text, "codex-reviewer")
        self.assertIn("primary reviewer", row.lower())
        self.assertNotIn("クロスバリデーション", row)


class TestReadmeReviewSection(unittest.TestCase):
    """AC-4: the review section describes dispatch / fallback / evaluator /
    orchestrator-decision, and the chain table lists all six perspectives
    with exactly the IMPLEMENTATION.md-pinned chains."""

    @classmethod
    def setUpClass(cls):
        cls.text = README_PATH.read_text(encoding="utf-8")

    def test_describes_one_primary_reviewer_dispatch(self):
        self.assertIn("primary_chain", self.text)
        self.assertIn("1 体だけ起動", self.text)

    def test_describes_claude_fallback_on_full_chain_unavailability(self):
        self.assertIn("チェーンの全エントリが利用不可", self.text)
        self.assertIn("Claude 汎用レビュアーにフォールバック", self.text)

    def test_describes_evaluator_step(self):
        self.assertIn("Opus 評価者", self.text)

    def test_describes_orchestrator_decision(self):
        self.assertIn("決定は常にオーケストレーターが行う", self.text)

    def test_chain_table_lists_all_six_perspectives_with_pinned_chains(self):
        start = self.text.index("primary-reviewer")
        end = self.text.index("R2b", start)
        table_block = self.text[start:end]
        for perspective, chain in PINNED_CHAINS.items():
            self.assertIn(
                perspective,
                table_block,
                f"perspective {perspective!r} missing from chain table",
            )
            self.assertIn(
                chain,
                table_block,
                f"chain for {perspective!r} does not match IMPLEMENTATION.md",
            )


class TestReadmePrerequisites(unittest.TestCase):
    """AC-5: prerequisites describe degradation to the Claude fallback
    rather than cross-validation being skipped, and no section of the
    README still describes a parallel double-run or agreement scoring."""

    @classmethod
    def setUpClass(cls):
        cls.text = README_PATH.read_text(encoding="utf-8")

    def test_codex_cli_bullet_describes_fallback_degradation(self):
        line = _find_bullet(self.text, "- Codex CLI")
        self.assertIn("フォールバック", line)

    def test_vertex_review_bullet_describes_fallback_degradation(self):
        line = _find_bullet(self.text, "- `vertex-review`")
        self.assertIn("フォールバック", line)

    def test_no_forbidden_parallel_double_run_or_agreement_wording(self):
        for phrase in FORBIDDEN_README_PHRASES:
            self.assertNotIn(phrase, self.text, f"forbidden phrase survived: {phrase!r}")


class TestSkillDescribesComposition(unittest.TestCase):
    """AC-6: SKILL.md's description and bullets describe the same
    composition as the README, still delegate to review-phase.md in
    standalone mode with no reviewer-selection logic of its own, and keep
    the never-commit / --report-only / round-record-path / auto-apply
    statements."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")
        frontmatter_end = cls.text.index("\n---\n", 4)
        cls.frontmatter = cls.text[:frontmatter_end]
        cls.body = cls.text[frontmatter_end:]
        # Whitespace-normalized body, for substrings that may be
        # word-wrapped across lines in the source Markdown.
        cls.body_flat = re.sub(r"\s+", " ", cls.body)

    def test_frontmatter_fields_unchanged(self):
        self.assertIn("name: review", self.frontmatter)
        self.assertIn('argument-hint: "[--report-only]"', self.frontmatter)
        self.assertIn("disable-model-invocation: true", self.frontmatter)
        self.assertIn("model: opus", self.frontmatter)
        self.assertIn(
            "allowed-tools: Read, Edit, Glob, Grep, Bash, Task, AskUserQuestion",
            self.frontmatter,
        )

    def test_description_states_new_composition(self):
        self.assertIn("primary_chain", self.frontmatter)
        self.assertIn("非 Claude レビュアー", self.frontmatter)
        self.assertIn("フォールバック", self.frontmatter)
        self.assertIn("Opus 評価者", self.frontmatter)

    def test_body_states_one_primary_reviewer_and_fallback_and_evaluator(self):
        self.assertIn("non-Claude primary reviewer", self.body_flat)
        self.assertIn("primary_chain", self.body_flat)
        self.assertIn("falls back to the Claude generic reviewer", self.body_flat)
        self.assertIn("Opus evaluator subagent", self.body_flat)

    def test_still_delegates_to_review_phase_in_standalone_mode(self):
        self.assertIn(
            "Read `${CLAUDE_PLUGIN_ROOT}/references/review-phase.md`", self.body
        )
        self.assertIn("standalone mode", self.body)

    def test_no_reviewer_selection_logic_of_its_own(self):
        # No chain literals duplicated locally -- selection stays owned by
        # review-phase.md / reviewers.yaml, cited by reference only.
        for literal in ("vertex-deepseek-v3.2", "vertex-glm-5", "muse-spark"):
            self.assertNotIn(literal, self.body)

    def test_never_commit_statement_unchanged(self):
        self.assertIn("**Standalone mode never commits**", self.body)

    def test_report_only_behaviour_unchanged(self):
        self.assertIn("--report-only", self.body)
        self.assertIn("--no-auto-fix", self.body)
        self.assertIn("--no-fix", self.body)

    def test_round_record_path_unchanged(self):
        self.assertIn("./reviews-{YYYYMMDD-HHMM}/round1.yaml", self.body)

    def test_auto_apply_caution_unchanged(self):
        self.assertIn("Auto-apply caution", self.body)
        self.assertIn(
            "applied to the working tree **without an\napproval prompt**", self.body
        )

    def test_no_forbidden_cross_model_wording(self):
        for phrase in FORBIDDEN_SKILL_PHRASES:
            self.assertNotIn(phrase, self.text, f"forbidden phrase survived: {phrase!r}")


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-7: this new module imports only the standard library
    (test/README.md's "no external dependencies" rule for test code)."""

    def test_only_standard_library_imports(self):
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
