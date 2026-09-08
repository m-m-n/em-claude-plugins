"""Tests for task0004 (muse-spark-contributor-consent): the em-workflow and
em-review plugin version bumps, applied to both plugin manifests and to
`.claude-plugin/marketplace.json`.

Covers task0004 Acceptance Criteria
(feature-docs/muse-spark-contributor-consent/tasks/task0004.md):

- AC-1: `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry
  in `.claude-plugin/marketplace.json` carry the same version string, it
  parses as a semantic version, and it is strictly greater than 0.1.69.
- AC-2: `em-review/.claude-plugin/plugin.json` and the em-review entry in
  `.claude-plugin/marketplace.json` carry the same version string, it
  parses as a semantic version, and it is strictly greater than 0.5.7.
- AC-3: no field other than the version changed in the three edited files,
  and no other marketplace entry changed.
- AC-4: this module asserts AC-1 through AC-3 using version-ordered
  comparison rather than string comparison, imports no third-party
  package, and passes under `python3 -m unittest discover -s tests`. The
  pre-existing plugin-version parity test (tests/test_plugin_version_parity.py)
  still passes -- verified by running the full suite, not asserted here (a
  suite cannot assert its own sibling module's outcome without recursion).

Per the task plan's Test Notes, version comparison happens component-wise
as integers, never as a whole-string comparison -- a string comparison
would call "0.1.7" greater than "0.1.69". The floor values (0.1.69, 0.5.7)
are kept as literals: they are this feature's base revision, and a test
that recomputed them from the working tree would assert nothing.

AC-3 ("no field other than the version changed") is checked by
canonicalizing each edited file's content with its `version` field(s)
stripped (sorted keys, `ensure_ascii=False`) and comparing a SHA-256 digest
of that canonical form against a baseline digest computed from the tree
immediately before this task's edit. Storing digests rather than the raw
pre-bump content keeps this module from having to carry a copy of the
(large) plugin.json `description` strings; the canonicalization function
below is exactly what produced the baseline digests.
"""

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EM_WORKFLOW_MANIFEST_PATH = (
    REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"
)
EM_REVIEW_MANIFEST_PATH = REPO_ROOT / "em-review" / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Pre-task baseline (task0004.md, Design): both plugins' versions on the
# tree before this task's edit.
EM_WORKFLOW_BASELINE_VERSION = "0.1.69"
EM_REVIEW_BASELINE_VERSION = "0.5.7"

# SHA-256 digests of each file's content with its `version` field(s)
# stripped and canonicalized via `_canonicalize_manifest` /
# `_canonicalize_marketplace` below, computed from the tree as it stood
# immediately before this task's edit (AC-3).
EM_WORKFLOW_MANIFEST_NONVERSION_SHA256 = (
    "c4f8b9a97b62b34f648b99b32e53b14c76d3ddbbd533d29dac10bbe34b5286b4"
)
EM_REVIEW_MANIFEST_NONVERSION_SHA256 = (
    "6f6b717184be5c2a250c80e39f0a526e103f9d752d039fa47f6343e9bd0dc3b3"
)
MARKETPLACE_NONVERSION_SHA256 = (
    "91990cece50d28af2864b67d70eb1171e6bbb5ded548e6ca200ecfb5f8a3e363"
)

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


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
    """Parse a major.minor.patch string into an int 3-tuple, so comparison
    happens per-component and numerically -- never as a whole-string
    comparison, which would sort a two-digit component backwards (e.g.
    "0.1.7" > "0.1.69" lexically)."""
    match = VERSION_RE.match(version or "")
    if match is None:
        raise AssertionError(f"version {version!r} is not of the form X.Y.Z")
    return tuple(int(part) for part in match.groups())


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a, version_b, f"registries disagree: {version_a!r} != {version_b!r}"
    )


def _assert_version_past_baseline(test, version, baseline):
    test.assertGreater(_version_tuple(version), _version_tuple(baseline))


def _canonicalize_manifest(data):
    """Canonical form of a plugin manifest with `version` stripped: sorted
    keys, non-ASCII left unescaped -- matches the serialization convention
    documented for the consent store, applied here to the pre-existing
    plugin.json files for a stable digest."""
    stripped = dict(data)
    stripped.pop("version", None)
    return json.dumps(stripped, sort_keys=True, ensure_ascii=False)


def _canonicalize_marketplace(data):
    """Canonical form of marketplace.json with every entry's `version`
    stripped, entry order preserved (a reorder counts as a change)."""
    return json.dumps(
        {
            "$schema": data.get("$schema"),
            "name": data.get("name"),
            "description": data.get("description"),
            "owner": data.get("owner"),
            "plugins": [
                {k: v for k, v in entry.items() if k != "version"}
                for entry in data.get("plugins", [])
            ],
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TestEmWorkflowVersion(unittest.TestCase):
    """AC-1: em-workflow's manifest and marketplace entry agree, parse as
    X.Y.Z, and sit strictly past the pre-task baseline (0.1.69)."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = _load_json(EM_WORKFLOW_MANIFEST_PATH)
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.entry = _marketplace_entry(cls.marketplace, "em-workflow")

    def test_manifest_version_parses_as_semver(self):
        _version_tuple(self.manifest.get("version"))  # must not raise

    def test_manifest_version_is_past_baseline(self):
        _assert_version_past_baseline(
            self, self.manifest.get("version"), EM_WORKFLOW_BASELINE_VERSION
        )

    def test_marketplace_entry_lookup_is_non_vacuous(self):
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_marketplace_entry_version_matches_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )

    def test_marketplace_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(
            self, self.entry.get("version"), EM_WORKFLOW_BASELINE_VERSION
        )


class TestEmReviewVersion(unittest.TestCase):
    """AC-2: em-review's manifest and marketplace entry agree, parse as
    X.Y.Z, and sit strictly past the pre-task baseline (0.5.7)."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = _load_json(EM_REVIEW_MANIFEST_PATH)
        cls.marketplace = _load_json(MARKETPLACE_PATH)
        cls.entry = _marketplace_entry(cls.marketplace, "em-review")

    def test_manifest_version_parses_as_semver(self):
        _version_tuple(self.manifest.get("version"))  # must not raise

    def test_manifest_version_is_past_baseline(self):
        _assert_version_past_baseline(
            self, self.manifest.get("version"), EM_REVIEW_BASELINE_VERSION
        )

    def test_marketplace_entry_lookup_is_non_vacuous(self):
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_marketplace_entry_version_matches_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )

    def test_marketplace_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(
            self, self.entry.get("version"), EM_REVIEW_BASELINE_VERSION
        )


class TestNoOtherFieldsChanged(unittest.TestCase):
    """AC-3: only the `version` field(s) moved in the three edited files."""

    def test_em_workflow_manifest_nonversion_content_unchanged(self):
        data = _load_json(EM_WORKFLOW_MANIFEST_PATH)
        self.assertEqual(
            _sha256(_canonicalize_manifest(data)),
            EM_WORKFLOW_MANIFEST_NONVERSION_SHA256,
        )

    def test_em_review_manifest_nonversion_content_unchanged(self):
        data = _load_json(EM_REVIEW_MANIFEST_PATH)
        self.assertEqual(
            _sha256(_canonicalize_manifest(data)),
            EM_REVIEW_MANIFEST_NONVERSION_SHA256,
        )

    def test_marketplace_nonversion_content_unchanged(self):
        data = _load_json(MARKETPLACE_PATH)
        self.assertEqual(
            _sha256(_canonicalize_marketplace(data)),
            MARKETPLACE_NONVERSION_SHA256,
        )


class TestVersionComparisonIsDotSeparatedNumeric(unittest.TestCase):
    """Test Notes (hermetic): the comparison helper against synthetic
    version pairs, including a case where whole-string comparison and
    per-component numeric comparison disagree -- proves the "past baseline"
    check survives future bumps rather than being pinned to one literal."""

    def test_naive_string_comparison_gets_two_digit_minor_backwards(self):
        # Sanity: demonstrates the failure mode a plain string comparison
        # of full version strings would fall into.
        self.assertGreater("0.1.7", "0.1.69")

    def test_version_tuple_orders_two_digit_minor_correctly(self):
        self.assertGreater(_version_tuple("0.1.69"), _version_tuple("0.1.7"))

    def test_assert_version_past_baseline_is_immune_to_the_string_trap(self):
        # "0.1.69" must be accepted as past a synthetic baseline of "0.1.7",
        # even though "0.1.7" > "0.1.69" as a raw string comparison (proved
        # above) -- this would raise if the helper used naive string
        # comparison instead of the parsed tuple.
        _assert_version_past_baseline(self, "0.1.69", "0.1.7")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-4: proof that the checks above fail meaningfully -- when the two
    registries disagree, when a version sits at or below its baseline, for
    a malformed version shape, when a marketplace entry is missing, and
    when the non-version content of a file has actually changed."""

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.1.70", "0.1.71")

    def test_fails_when_em_workflow_version_equals_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(
                self, EM_WORKFLOW_BASELINE_VERSION, EM_WORKFLOW_BASELINE_VERSION
            )

    def test_fails_when_em_review_version_below_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.5.6", EM_REVIEW_BASELINE_VERSION)

    def test_fails_for_malformed_version_shape(self):
        with self.assertRaises(AssertionError):
            _version_tuple("not-a-version")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    def test_digest_check_rejects_a_mutated_nonversion_field(self):
        # Non-vacuity guard for TestNoOtherFieldsChanged: a manifest whose
        # description was altered (version untouched) must NOT match the
        # baseline digest -- proves the digest actually discriminates
        # content, not just presence of the `version` key.
        forged = {
            "name": "em-workflow",
            "description": "a description that was never the baseline one",
            "author": {"name": "em"},
            "version": EM_WORKFLOW_BASELINE_VERSION,
        }
        self.assertNotEqual(
            _sha256(_canonicalize_manifest(forged)),
            EM_WORKFLOW_MANIFEST_NONVERSION_SHA256,
        )

    def test_digest_check_ignores_only_the_version_field(self):
        # Non-vacuity guard: two manifests differing ONLY in `version`
        # canonicalize to the identical digest -- proves the digest is
        # blind to version changes specifically, not to everything.
        base = _load_json(EM_WORKFLOW_MANIFEST_PATH)
        forged = dict(base, version="99.0.0")
        self.assertEqual(
            _sha256(_canonicalize_manifest(base)),
            _sha256(_canonicalize_manifest(forged)),
        )


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-4: this new module imports only the standard library (test/
    README.md's "no external dependencies" rule for test code)."""

    def test_only_standard_library_imports(self):
        import ast

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
