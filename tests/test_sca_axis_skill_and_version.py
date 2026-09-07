"""Tests for task0006 (review-sca-axis): the security-skill delegation note
and the em-workflow plugin version bump.

Covers task0006 Acceptance Criteria
(feature-docs/review-sca-axis/tasks/task0006.md):

- AC-1: `em-workflow/skills/review-security/SKILL.md`'s "What NOT to flag"
  section states that known-CVE judgement for dependency packages is
  performed mechanically by axis 2.
- AC-2: the rest of that skill is unchanged -- its heading structure, its
  pre-existing "What NOT to flag" sentences and its `category` requirement
  all survive.
- AC-3: `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry
  of `.claude-plugin/marketplace.json` carry the SAME version, strictly
  greater than 0.1.65 by semantic-version (tuple) comparison.
- AC-4: every `tests/test_sca_*.py` module present in the tree imports only
  standard-library modules in its own import statements -- a static scan,
  so it holds in this isolated worktree and covers every such module once
  the other review-sca-axis tasks are integrated. A module that loads a
  script by file path (as task0001's and task0005's do) is not a
  third-party import and must not be flagged.
- AC-5: `python3 -m unittest discover -s tests` and
  `python3 em-workflow/scripts/check-plugin-invariants.py <repo-root>` both
  exit 0 in this task's own worktree. Not unit-testable from inside this
  module for the same reason test_plugin_version_parity.py's AC-3 is not
  (a suite cannot assert its own full-suite outcome without recursion, and
  the invariants checker's exit code is already covered by
  test_check_plugin_invariants.py); verified by actually running both
  commands, recorded in the implementer report.

Per Test Notes, AC-3's comparison uses a dot-separated numeric tuple, not a
whole-string comparison (the repository's existing version-bump test
modules already establish this pattern -- see
test_plugin_version_parity.py). AC-2's "unchanged" is asserted against the
specific surviving sentences and headings rather than a whole-file hash, so
this task's own addition does not fail its own assertion.
"""

import ast
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SECURITY_SKILL_PATH = PLUGIN_ROOT / "skills" / "review-security" / "SKILL.md"

# Pre-task baseline (task0006.md, Design): both registries read 0.1.65
# before this task's edit. The new version must compare strictly greater.
BASELINE_VERSION = "0.1.65"

# Sentences pinned verbatim from the pre-existing skill text (task0006.md
# AC-2): these must survive this task's edit byte-for-byte.
EXISTING_WHAT_NOT_TO_FLAG_SENTENCES = (
    'Style hardening unrelated to a concrete attacker-controlled path.',
    '"could be exploited if X and Y and Z" without a realistic threat model.',
)
EXISTING_CATEGORY_LINE = 'Every finding MUST have `"category": "security"`.'
EXISTING_HEADINGS = (
    "# Review Perspective: Security",
    "## What to flag (security only)",
    "## What NOT to flag",
    "## category",
)


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _version_tuple(version):
    """Parse a dot-separated version string into a tuple of ints for
    per-component numeric comparison -- never a whole-string comparison,
    which would sort a two-digit component backwards (e.g. "0.1.9" >
    "0.1.65" lexically)."""
    parts = (version or "").split(".")
    if not parts or not all(re.fullmatch(r"\d+", p) for p in parts):
        raise AssertionError(f"version {version!r} is not a dotted numeric sequence")
    return tuple(int(p) for p in parts)


def _assert_version_past_baseline(test, version, baseline=BASELINE_VERSION):
    test.assertGreater(_version_tuple(version), _version_tuple(baseline))


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


def _section_text(full_text, heading, next_heading):
    """The body text strictly between two headings (each matched as a whole
    line), used to scope an assertion to one section of the document
    instead of the whole file."""
    lines = full_text.splitlines()
    try:
        start = lines.index(heading) + 1
    except ValueError:
        raise AssertionError(f"heading {heading!r} not found")
    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx] == next_heading:
            end = idx
            break
    return "\n".join(lines[start:end])


def _top_level_import_names(source):
    """The set of top-level module names named by real `import` /
    `from ... import` statements in `source` -- never names appearing only
    as string arguments to a call (e.g. `importlib.util.spec_from_file_
    location("scan_dependencies", path)`), so loading a script by file path
    is never mistaken for a third-party import (task0006.md Test Notes)."""
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and node.level == 0:
                names.add(node.module.split(".")[0])
            # node.module is None (`from . import x`) or node.level > 0
            # (relative imports) never name a third-party top-level module.
    return names


def _non_stdlib_imports(source):
    stdlib = sys.stdlib_module_names
    return sorted(name for name in _top_level_import_names(source) if name not in stdlib)


class TestSecuritySkillDelegationNote(unittest.TestCase):
    """AC-1: the "What NOT to flag" section states that known-CVE judgement
    for dependency packages is made mechanically by axis 2."""

    @classmethod
    def setUpClass(cls):
        cls.text = SECURITY_SKILL_PATH.read_text(encoding="utf-8")
        cls.section = _section_text(cls.text, "## What NOT to flag", "## category")

    def test_section_mentions_axis_2(self):
        self.assertIn("axis 2", self.section)

    def test_section_states_the_judgement_is_mechanical(self):
        self.assertIn("mechanically", self.section)

    def test_section_scopes_the_delegation_to_known_cve_dependency_judgement(self):
        lowered = self.section.lower()
        self.assertIn("cve", lowered)
        self.assertIn("dependency", lowered)


class TestSecuritySkillUnchangedElsewhere(unittest.TestCase):
    """AC-2: heading structure, the two pre-existing "What NOT to flag"
    sentences, and the `category` requirement all survive this task's
    edit."""

    @classmethod
    def setUpClass(cls):
        cls.text = SECURITY_SKILL_PATH.read_text(encoding="utf-8")

    def test_headings_all_present(self):
        for heading in EXISTING_HEADINGS:
            with self.subTest(heading=heading):
                self.assertIn(heading, self.text.splitlines())

    def test_existing_what_not_to_flag_sentences_survive(self):
        for sentence in EXISTING_WHAT_NOT_TO_FLAG_SENTENCES:
            with self.subTest(sentence=sentence):
                self.assertIn(sentence, self.text)

    def test_category_requirement_survives(self):
        self.assertIn(EXISTING_CATEGORY_LINE, self.text)

    def test_what_to_flag_section_untouched(self):
        section = _section_text(
            self.text, "## What to flag (security only)", "## What NOT to flag"
        )
        self.assertIn("Injection", section)
        self.assertIn("Cryptographic weakness", section)
        self.assertIn("Prompt-injection", section)


class TestPluginManifestVersion(unittest.TestCase):
    """AC-3: the plugin manifest's version is past the pre-task baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_manifest_has_a_version_key(self):
        self.assertIn("version", self.data)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))

    def test_name_field_unchanged(self):
        self.assertEqual(self.data.get("name"), "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-3: the em-workflow marketplace entry's version (found by name)
    agrees with the plugin manifest and is past baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_em_workflow_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )

    def test_em_review_entry_untouched(self):
        # Out of scope (task0006.md): "any other plugin's version in
        # marketplace.json" must not move.
        em_review = _marketplace_entry(self.data, "em-review")
        self.assertEqual(em_review.get("source"), "./em-review")


class TestVersionComparisonIsDotSeparatedNumeric(unittest.TestCase):
    """Test Notes: the comparison helper against a synthetic pair where
    whole-string comparison and per-component numeric comparison disagree
    because of a two-digit patch component."""

    def test_naive_string_comparison_gets_two_digit_patch_backwards(self):
        self.assertGreater("0.1.9", "0.1.65")

    def test_version_tuple_orders_two_digit_patch_correctly(self):
        self.assertGreater(_version_tuple("0.1.66"), _version_tuple("0.1.9"))

    def test_assert_version_past_baseline_is_immune_to_the_string_trap(self):
        _assert_version_past_baseline(self, "0.1.10", baseline="0.1.9")


class TestVersionValidationDetectsRegressions(unittest.TestCase):
    """Negative-proof: the version checks above fail meaningfully when
    versions differ or a version is at/below baseline."""

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.1.66", "0.1.67")

    def test_fails_when_version_equals_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, BASELINE_VERSION)

    def test_fails_when_version_below_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1.5")

    def test_fails_for_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "abc")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")


class TestScaTestModulesImportOnlyStdlib(unittest.TestCase):
    """AC-4: every `tests/test_sca_*.py` module present in the tree imports
    only standard-library modules in its own import statements. A static
    scan over whatever such modules exist -- holds in this isolated
    worktree (only this module) and covers all of them after integration
    (task0001's and task0005's modules join the glob)."""

    @classmethod
    def setUpClass(cls):
        cls.modules = sorted(TESTS_DIR.glob("test_sca_*.py"))

    def test_scan_is_non_vacuous(self):
        # Guard against silently passing over an empty glob: this module
        # itself must always match its own naming convention.
        names = [p.name for p in self.modules]
        self.assertIn("test_sca_axis_skill_and_version.py", names)

    def test_every_sca_module_imports_only_stdlib(self):
        for path in self.modules:
            with self.subTest(module=path.name):
                source = path.read_text(encoding="utf-8")
                offenders = _non_stdlib_imports(source)
                self.assertEqual(
                    offenders,
                    [],
                    f"{path.name} imports non-stdlib module(s): {offenders}",
                )


class TestFilePathScriptLoadingIsNotFlaggedAsImport(unittest.TestCase):
    """Test Notes: a module that loads a script by file path (the pattern
    task0001's and task0005's own test modules use to exercise
    scan-dependencies.py, which is not a package) is not a third-party
    import and must not be flagged -- an explicit case so the check is not
    accidentally over-strict."""

    FILE_PATH_LOADING_SOURCE = (
        "import importlib.util\n"
        "import unittest\n"
        "from pathlib import Path\n"
        "\n"
        "SCRIPT_PATH = (\n"
        "    Path(__file__).resolve().parent.parent\n"
        "    / 'em-workflow' / 'scripts' / 'scan-dependencies.py'\n"
        ")\n"
        "\n"
        "\n"
        "def _load_script():\n"
        "    spec = importlib.util.spec_from_file_location(\n"
        "        'scan_dependencies', SCRIPT_PATH\n"
        "    )\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    return module\n"
    )

    def test_file_path_loading_source_is_not_flagged(self):
        offenders = _non_stdlib_imports(self.FILE_PATH_LOADING_SOURCE)
        self.assertEqual(offenders, [])

    def test_the_loaded_module_name_never_appears_as_a_flagged_import(self):
        # The dynamically-loaded module name ("scan_dependencies") is not a
        # standard-library module, so if the checker mistakenly captured
        # string-literal arguments as imports, it would show up here.
        offenders = _non_stdlib_imports(self.FILE_PATH_LOADING_SOURCE)
        self.assertNotIn("scan_dependencies", offenders)

    def test_relative_import_from_package_is_ignored_not_flagged(self):
        # `from . import x` has node.module is None; must not raise and
        # must not be treated as a third-party import.
        offenders = _non_stdlib_imports("from . import something\n")
        self.assertEqual(offenders, [])


class TestScaImportScanDetectsRegressions(unittest.TestCase):
    """Negative-proof: the stdlib-only scan actually flags a genuine
    third-party import, in both `import` and `from ... import` form."""

    def test_flags_a_plain_third_party_import(self):
        offenders = _non_stdlib_imports("import yaml\n")
        self.assertEqual(offenders, ["yaml"])

    def test_flags_a_from_import_of_a_third_party_package(self):
        offenders = _non_stdlib_imports("from requests import get\n")
        self.assertEqual(offenders, ["requests"])

    def test_stdlib_imports_are_never_flagged(self):
        offenders = _non_stdlib_imports(
            "import json\nimport re\nfrom pathlib import Path\n"
        )
        self.assertEqual(offenders, [])


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-4 (self-check): this module's own imports are standard-library
    only, following test/README.md's "no external dependencies" rule for
    test code."""

    def test_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        offenders = _non_stdlib_imports(source)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
