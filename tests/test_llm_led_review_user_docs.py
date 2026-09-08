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

- AC-1: both registries carry an em-workflow version strictly past the
  0.1.58 baseline, the two values are equal, and the em-review marketplace
  entry's identity fields (`name`, `description`, `author`, `category`,
  `source`) and key set stay pinned to their pre-task values. `version` is
  excepted from the pin and is instead asserted by shape only (present, a
  dotted-numeric string), because
  `.claude/rules/core-plugin-version-bump.md` requires that field to
  advance whenever the em-review plugin's own contents change -- a rule
  external to this feature's task.
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
# both registries read 0.1.58 before this task's edit. The landed value is
# asserted as strictly past this baseline rather than as an exact literal,
# so unrelated bumps that land alongside this feature do not break the test
# (the pattern of tests/test_plugin_version_parity.py).
BASELINE_VERSION = "0.1.58"

# The em-review marketplace entry's identity fields as they read before
# this task (task0005.md Out of Scope: "The em-review plugin's marketplace
# entry ... must not be modified"). `version` is deliberately not part of
# this literal set -- it is asserted by shape only, via
# `_assert_em_review_entry_matches` below, because
# `.claude/rules/core-plugin-version-bump.md` requires it to advance
# whenever the em-review plugin's own contents change (task0008.md).
EXPECTED_EM_REVIEW_NAME = "em-review"
EXPECTED_EM_REVIEW_DESCRIPTION = (
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
)
EXPECTED_EM_REVIEW_AUTHOR = {"name": "em"}
EXPECTED_EM_REVIEW_CATEGORY = "code-review"
EXPECTED_EM_REVIEW_SOURCE = "./em-review"

# The entry's key set now that it carries `version` (task0008.md Design):
# the five identity keys above, plus `version`. An added or removed key is
# still a detected modification.
EXPECTED_EM_REVIEW_ENTRY_KEYS = {
    "name",
    "description",
    "author",
    "category",
    "source",
    "version",
}

DOTTED_NUMERIC_VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")

# IMPLEMENTATION.md Shared Components, "Primary chains" -- copied here
# verbatim per Test Notes (never read from references/reviewers.yaml,
# which does not carry this feature's edit inside a task worktree).
PINNED_CHAINS = {
    "security": "codex → litellm `muse-spark`",
    "performance": "litellm `muse-spark` → litellm `vertex-glm-5.2` → codex",
    "spec": "litellm `muse-spark` → litellm `vertex-glm-5.2` → codex",
    "architecture": "litellm `vertex-glm-5.2` → litellm `muse-spark` → codex",
    "comprehensive": "codex → litellm `vertex-glm-5.2` → litellm `muse-spark`",
    "license": "codex → litellm `vertex-glm-5.2` → litellm `muse-spark`",
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


def _is_dotted_numeric_version(value):
    """A dotted numeric version string: one or more '.'-separated
    non-negative integers, e.g. "0.5.7". Never compared against a literal
    value -- that is what lets the em-review plugin's own version bumps
    pass this guard without weakening what it detects (task0008.md)."""
    return isinstance(value, str) and DOTTED_NUMERIC_VERSION_RE.match(value) is not None


def _assert_em_review_entry_matches(test, entry):
    """The em-review matcher (task0008.md repair): the key set and every
    identity field (name, description, author, category, source) are
    pinned to their pre-task literal values exactly -- an edit to any of
    them, including the description, is precisely what this guard exists
    to catch. `version` is excepted from the literal pin and is instead
    asserted by shape only (present, dotted numeric), since
    `.claude/rules/core-plugin-version-bump.md` requires it to change over
    time."""
    test.assertEqual(set(entry.keys()), EXPECTED_EM_REVIEW_ENTRY_KEYS)
    test.assertEqual(entry.get("name"), EXPECTED_EM_REVIEW_NAME)
    test.assertEqual(entry.get("description"), EXPECTED_EM_REVIEW_DESCRIPTION)
    test.assertEqual(entry.get("author"), EXPECTED_EM_REVIEW_AUTHOR)
    test.assertEqual(entry.get("category"), EXPECTED_EM_REVIEW_CATEGORY)
    test.assertEqual(entry.get("source"), EXPECTED_EM_REVIEW_SOURCE)
    test.assertTrue(
        _is_dotted_numeric_version(entry.get("version")),
        f"em-review version {entry.get('version')!r} is not a dotted numeric string",
    )


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
    """AC-1: both registries carry a version past the baseline, and agree
    with each other via an actual value comparison (not a duplicated
    literal)."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.marketplace_entry = _marketplace_entry(cls.marketplace, "em-workflow")

    def test_plugin_manifest_version_is_past_baseline(self):
        self.assertGreater(
            _version_tuple(self.manifest.get("version")),
            _version_tuple(BASELINE_VERSION),
        )

    def test_marketplace_entry_version_is_past_baseline(self):
        self.assertGreater(
            _version_tuple(self.marketplace_entry.get("version")),
            _version_tuple(BASELINE_VERSION),
        )

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
    """AC-1, AC-2, AC-4: the em-review marketplace entry's identity fields
    and key set stay pinned to their pre-task values; `version` is asserted
    by shape only (task0008.md repair of the over-specified whole-entry
    snapshot comparison, which broke on the plugin's own required version
    bumps)."""

    def test_em_review_entry_matches_pre_task_identity_and_shape(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        _assert_em_review_entry_matches(self, entry)


class TestEmReviewMatcherDetectionPower(unittest.TestCase):
    """AC-2, AC-3: proofs that the repaired matcher still detects every
    modification it is supposed to, and that its `version` exception is
    genuinely a shape check rather than a literal comparison in disguise.
    All proofs run over synthetic in-memory copies of the entry -- nothing
    here reads or writes `.claude-plugin/marketplace.json` as a fixture."""

    SYNTHETIC_ENTRY = {
        "name": EXPECTED_EM_REVIEW_NAME,
        "description": EXPECTED_EM_REVIEW_DESCRIPTION,
        "author": EXPECTED_EM_REVIEW_AUTHOR,
        "category": EXPECTED_EM_REVIEW_CATEGORY,
        "source": EXPECTED_EM_REVIEW_SOURCE,
        "version": "0.5.7",
    }

    def test_matcher_accepts_the_synthetic_baseline_entry(self):
        # Sanity check: the fixture itself satisfies the matcher, so the
        # negative proofs below are known to fail for the reason each one
        # claims, not because the fixture was already invalid.
        _assert_em_review_entry_matches(self, dict(self.SYNTHETIC_ENTRY))

    def test_matcher_accepts_a_forged_higher_version(self):
        # AC-2: the matcher never compares `version` against a literal, so
        # a synthetic entry differing only by a different, higher version
        # is accepted -- proving the shape assertion is not a literal one
        # in disguise.
        forged = dict(self.SYNTHETIC_ENTRY, version="99.0.0")
        _assert_em_review_entry_matches(self, forged)  # must not raise

    def test_matcher_rejects_an_altered_identity_field(self):
        for field, forged_value in (
            ("name", "em-review-forked"),
            ("description", "a different description"),
            ("author", {"name": "someone-else"}),
            ("category", "other"),
            ("source", "./em-review-forked"),
        ):
            with self.subTest(field=field):
                forged = dict(self.SYNTHETIC_ENTRY, **{field: forged_value})
                with self.assertRaises(AssertionError):
                    _assert_em_review_entry_matches(self, forged)

    def test_matcher_rejects_a_missing_or_non_dotted_numeric_version(self):
        missing = {
            key: value
            for key, value in self.SYNTHETIC_ENTRY.items()
            if key != "version"
        }
        malformed = dict(self.SYNTHETIC_ENTRY, version="not-a-version")
        for label, forged in (("missing", missing), ("malformed", malformed)):
            with self.subTest(label=label):
                with self.assertRaises(AssertionError):
                    _assert_em_review_entry_matches(self, forged)

    def test_matcher_rejects_an_unexpected_extra_key(self):
        forged = dict(self.SYNTHETIC_ENTRY, extra_field="unexpected")
        with self.assertRaises(AssertionError):
            _assert_em_review_entry_matches(self, forged)


class TestEmReviewEntryLookupIsNonVacuous(unittest.TestCase):
    """AC-4: the entry lookup fails loudly when no em-review entry is
    present, rather than returning an empty mapping the matcher would then
    find unobjectionable."""

    def test_lookup_raises_when_no_em_review_entry_present(self):
        document_without_em_review = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(document_without_em_review, "em-review")


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


class TestOwnModuleDocstringStatesRepairedInvariant(unittest.TestCase):
    """AC-5: this module's own docstring no longer claims the em-review
    entry is asserted byte-identical to before, and instead states the
    repaired invariant (identity fields and key set pinned, `version` by
    shape) and why `version` is excepted."""

    @classmethod
    def setUpClass(cls):
        cls.module_doc = sys.modules[__name__].__doc__ or ""

    def test_no_longer_claims_byte_identical_equality(self):
        self.assertNotIn("byte-identical", self.module_doc)

    def test_states_identity_fields_and_key_set_are_pinned(self):
        self.assertIn("identity fields", self.module_doc)
        self.assertIn("key set", self.module_doc)

    def test_states_version_is_excepted_and_why(self):
        self.assertIn("version", self.module_doc)
        self.assertIn("core-plugin-version-bump.md", self.module_doc)


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
