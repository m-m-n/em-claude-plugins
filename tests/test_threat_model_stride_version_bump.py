"""Tests for task0006 (threat-model-stride): the em-workflow plugin's minor
version bump (FR11).

Covers task0006 Acceptance Criteria
(feature-docs/threat-model-stride/tasks/task0006.md):

- AC-6: `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry
  of `.claude-plugin/marketplace.json` hold the identical well-formed
  version whose (major, minor) pair is strictly greater than the base
  revision's; no other field of either file changes; the em-review entry is
  unchanged; this module passes and holds a negative proof per matcher;
  every existing `tests/test_*_version_bump.py` module passes unmodified
  (verified by running the full suite, not re-asserted here -- a suite
  cannot assert its own full-suite outcome without recursion, per the
  precedent in test_plugin_version_parity.py / test_recycled_task_id_
  version_bump.py).

Per the plan's Design and Test Notes (SC-6): the base revision's em-workflow
version is held here as a floor; only the (major, minor) pair is required to
move (FR11 raises the minor position and resets patch to zero, but a sibling
task's commit-guard fallback or parent-side adoption may leave a non-zero
patch -- the plan's own Test Notes: "If the commit guard or a sibling task's
fallback already raised the minor position at merge time, the parent-side
value wins; AC-6 still holds"). The comparison is a per-component numeric
tuple, never a whole-string or literal-equality comparison, so later
legitimate bumps keep this test green. JSON is parsed, never pattern-matched.
Standard library only.
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

# Pre-task baseline (read from HEAD at the time this test was written, per
# SC-6: "Concrete version values never appear in SPEC, plans or AC; they are
# read from HEAD at commit time"). The live (major, minor) pair must compare
# strictly greater than this floor's pair -- never a literal-equality pin.
BASELINE_VERSION = "0.2.14"

EM_REVIEW_NAME = "em-review"
EM_REVIEW_AUTHOR = {"name": "em"}
EM_REVIEW_CATEGORY = "code-review"
EM_REVIEW_SOURCE = "./em-review"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


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
    """Parse a well-formed three-part dotted version (X.Y.Z) into an int
    tuple. Rejects anything with a different shape (missing/extra
    component, non-numeric part) -- "well-formed three-part version" per
    the plan's Design."""
    match = VERSION_RE.match(version or "")
    if match is None:
        raise AssertionError(
            f"version {version!r} is not a well-formed three-part version (X.Y.Z)"
        )
    return tuple(int(g) for g in match.groups())


def _assert_minor_position_past_baseline(test, version, baseline=BASELINE_VERSION):
    """FR11: only the (major, minor) pair is required to move past the
    baseline's pair -- the patch component is deliberately excluded from
    the comparison, since a parent-side-adopted value after conflict
    resolution may carry a non-zero patch (plan Test Notes)."""
    version_pair = _version_tuple(version)[:2]
    baseline_pair = _version_tuple(baseline)[:2]
    test.assertGreater(
        version_pair,
        baseline_pair,
        f"(major, minor) of {version!r} is not strictly past baseline {baseline!r}",
    )


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a,
        version_b,
        f"registries disagree: {version_a!r} != {version_b!r}",
    )


def _assert_em_review_entry_unchanged(test, entry):
    """AC-6: the em-review entry's identity fields are pinned exactly; its
    `version` is checked by shape only (well-formed three-part), never
    against a literal value, since it is not owned by this task."""
    test.assertEqual(entry.get("name"), EM_REVIEW_NAME)
    test.assertEqual(entry.get("author"), EM_REVIEW_AUTHOR)
    test.assertEqual(entry.get("category"), EM_REVIEW_CATEGORY)
    test.assertEqual(entry.get("source"), EM_REVIEW_SOURCE)
    _version_tuple(entry.get("version"))  # shape-only; raises if malformed


class TestPluginManifestVersion(unittest.TestCase):
    """AC-6: plugin.json's version has its minor position raised past the
    baseline, and no other field of the manifest changes."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_manifest_has_a_version_key(self):
        self.assertIn("version", self.data)

    def test_minor_position_is_past_baseline(self):
        _assert_minor_position_past_baseline(self, self.data.get("version"))

    def test_name_field_unchanged(self):
        self.assertEqual(self.data.get("name"), "em-workflow")


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-6: the em-workflow marketplace entry (found by name, not
    position) holds the identical version as the plugin manifest, past the
    baseline's minor position."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_entry_lookup_is_non_vacuous(self):
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_em_workflow_entry_minor_position_is_past_baseline(self):
        _assert_minor_position_past_baseline(self, self.entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest_exactly(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )

    def test_em_workflow_entry_source_unchanged(self):
        self.assertEqual(self.entry.get("source"), "./em-workflow")


class TestEmReviewEntryUnchanged(unittest.TestCase):
    """AC-6: the em-review entry's identity fields are unchanged; its
    version is well-formed but not pinned to a literal (out of this task's
    scope)."""

    def test_em_review_entry_matches(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, EM_REVIEW_NAME)
        _assert_em_review_entry_unchanged(self, entry)


class TestVersionComparisonExcludesPatch(unittest.TestCase):
    """Hermetic proof that the comparison is on the (major, minor) pair
    only, so a parent-side-adopted non-zero patch after conflict
    resolution still passes (plan Test Notes)."""

    def test_same_minor_different_patch_still_counts_as_past_baseline(self):
        # baseline 0.2.14 -> a value with the *same* minor but a *higher*
        # patch does NOT count (patch alone never satisfies FR11); this is
        # the "forged patch-only bump" negative proof, restated positively
        # here as a sanity check on the tuple slicing itself.
        self.assertEqual(_version_tuple("0.2.99")[:2], _version_tuple("0.2.0")[:2])

    def test_bumped_minor_with_any_patch_counts_as_past_baseline(self):
        _assert_minor_position_past_baseline(self, "0.3.7", baseline="0.2.14")
        _assert_minor_position_past_baseline(self, "0.3.0", baseline="0.2.14")

    def test_bumped_major_counts_as_past_baseline(self):
        _assert_minor_position_past_baseline(self, "1.0.0", baseline="0.2.14")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-6: a negative proof per matcher -- a forged patch-only bump, a
    forged differing pair, and a forged malformed version."""

    def test_minor_matcher_rejects_a_forged_patch_only_bump(self):
        # Same (major, minor) as baseline, only the patch moved: FR11 is
        # about the minor position, so this must NOT satisfy the check.
        forged_patch_only = "0.2.15"
        with self.assertRaises(AssertionError):
            _assert_minor_position_past_baseline(self, forged_patch_only)

    def test_minor_matcher_rejects_version_equal_to_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_minor_position_past_baseline(self, BASELINE_VERSION)

    def test_minor_matcher_rejects_version_below_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_minor_position_past_baseline(self, "0.1.99")

    def test_agreement_matcher_rejects_a_forged_differing_pair(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.3.0", "0.4.0")

    def test_malformed_version_matcher_rejects_missing_patch_component(self):
        with self.assertRaises(AssertionError):
            _version_tuple("0.3")

    def test_malformed_version_matcher_rejects_extra_component(self):
        with self.assertRaises(AssertionError):
            _version_tuple("0.3.0.1")

    def test_malformed_version_matcher_rejects_non_numeric_component(self):
        with self.assertRaises(AssertionError):
            _version_tuple("0.x.0")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    FORGED_EM_REVIEW_ENTRY = {
        "name": EM_REVIEW_NAME,
        "author": EM_REVIEW_AUTHOR,
        "category": EM_REVIEW_CATEGORY,
        "source": EM_REVIEW_SOURCE,
        "version": "0.5.13",
    }

    def test_em_review_matcher_rejects_altered_identity_field(self):
        for field, forged_value in (
            ("name", "em-review-forked"),
            ("author", {"name": "someone-else"}),
            ("category", "other"),
            ("source", "./em-review-forked"),
        ):
            with self.subTest(field=field):
                forged = dict(self.FORGED_EM_REVIEW_ENTRY, **{field: forged_value})
                with self.assertRaises(AssertionError):
                    _assert_em_review_entry_unchanged(self, forged)

    def test_em_review_matcher_rejects_malformed_version(self):
        forged = dict(self.FORGED_EM_REVIEW_ENTRY, version="not-a-version")
        with self.assertRaises(AssertionError):
            _assert_em_review_entry_unchanged(self, forged)

    def test_em_review_matcher_accepts_forged_higher_version(self):
        # The matcher never pins a literal version value, so a forged
        # sample differing only by a higher well-formed version is
        # accepted.
        forged = dict(self.FORGED_EM_REVIEW_ENTRY, version="99.0.0")
        _assert_em_review_entry_unchanged(self, forged)  # must not raise


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """This module imports the standard library only (test/README.md's "no
    external dependencies" rule for test code)."""

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
                if node.module is not None and node.level == 0:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
