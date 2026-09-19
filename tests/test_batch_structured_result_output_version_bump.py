"""Tests for task0006 (batch-structured-result-output): the em-workflow
plugin version bump in both registries.

Covers task0006 Acceptance Criteria
(feature-docs/batch-structured-result-output/tasks/task0006.md):

- AC-1: `em-workflow/.claude-plugin/plugin.json` and the marketplace entry
  whose `name` is `em-workflow` carry the same version string.
- AC-2: that version compares strictly greater than `0.1.82` under
  dot-separated numeric comparison, and the module demonstrates that a naive
  whole-string comparison would get a two-digit component wrong, proving the
  comparison used is numeric.
- AC-3: the marketplace entry is located by its `name` field; a forged
  marketplace document missing that entry is rejected.
- AC-4: the `em-review` entry's `name`, `author`, `category`, `source` and
  `version` are unchanged from their pre-change values.
- AC-5: both manifests still parse as JSON, and every other key of each file
  is unchanged.
- AC-6: this module is discovered by `python3 -m unittest discover -s
  tests`, imports the Python standard library only, and carries a negative
  proof for each matcher it introduces (versions disagreeing; version at the
  baseline; version below the baseline; malformed version shape).
- AC-7: nothing is added under `em-workflow/` beyond the version value
  itself (NFR7) -- this module lives under `tests/`, not under
  `em-workflow/`.

Per IMPLEMENTATION.md D9, the bump is a patch bump from the pre-change
baseline `0.1.82`, owned by this task alone (SC8); no other task edits
either manifest. Per the task plan's Design, this module declares its own
baseline and its own comparison helpers -- following the repository's
`test_*_version_bump.py` convention -- rather than editing the generic
`tests/test_plugin_version_parity.py` (D4).

AC-5 ("every other key of each file is unchanged") is checked the same way
as the repository's other version-bump modules: canonicalizing each file
with its `version` field(s) stripped (sorted keys, `ensure_ascii=False`) and
comparing a SHA-256 digest of that canonical form against a baseline digest
computed from the tree immediately before this task's edit -- storing the
digest rather than a copy of the (large) `description` strings.

Matcher -> negative-proof inventory (AC-3, AC-6):

- `_assert_version_past_baseline` (the baseline matcher): negative proofs
  are `test_fails_when_version_equals_baseline` and
  `test_fails_when_version_below_baseline`; malformed-shape proof is
  `test_fails_for_malformed_version_shape`.
- `_assert_versions_agree` (the equality matcher): negative proof is
  `test_fails_when_versions_differ`.
- `_marketplace_entry` (the by-name lookup): negative proof is
  `test_entry_lookup_fails_on_a_missing_entry_name` (AC-3's "forged
  marketplace document missing that entry is rejected").
- the AC-5 digest checks: negative proof is
  `test_digest_check_rejects_a_mutated_nonversion_field`, non-vacuity guard
  is `test_digest_check_ignores_only_the_version_field`.
"""

import ast
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Pre-change baseline (task0006.md, Design / IMPLEMENTATION.md D9): both
# registries read 0.1.82 before this task's edit. The new value must compare
# strictly greater under dot-separated numeric comparison.
BASELINE_VERSION = "0.1.82"

# SHA-256 digests of each file's content with its `version` field(s)
# stripped and canonicalized via `_canonicalize_manifest` /
# `_canonicalize_marketplace` below, computed from the tree as it stood
# immediately before this task's edit (AC-5).
PLUGIN_MANIFEST_NONVERSION_SHA256 = (
    "bf70d7104511c338b6f076c3d9ab08b6a19b757b59d45397324242f11008ebf0"
)
MARKETPLACE_NONVERSION_SHA256 = (
    "91990cece50d28af2864b67d70eb1171e6bbb5ded548e6ca200ecfb5f8a3e363"
)

# The em-review entry's identity fields and version, pinned to their exact
# pre-change values (AC-4) -- this task never touches the em-review plugin.
EM_REVIEW_NAME = "em-review"
EM_REVIEW_AUTHOR = {"name": "em"}
EM_REVIEW_CATEGORY = "code-review"
EM_REVIEW_SOURCE = "./em-review"
EM_REVIEW_VERSION = "0.5.10"

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{path} did not parse as JSON: {exc}") from exc


def _marketplace_entry(data, name):
    """Look the entry up by its `name` field -- never by array position
    (AC-3): the marketplace plugin list's order is not a contract."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _version_tuple(version):
    """Parse a major.minor.patch string into an int 3-tuple, so comparison
    happens per-component and numerically -- never as a whole-string
    comparison, which would sort a two-digit component backwards (e.g.
    "0.1.9" > "0.1.10" lexically; see
    TestVersionComparisonIsDotSeparatedNumeric below)."""
    match = VERSION_RE.match(version or "")
    if match is None:
        raise AssertionError(f"version {version!r} is not of the form X.Y.Z")
    return tuple(int(part) for part in match.groups())


def _assert_versions_agree(test, version_a, version_b):
    test.assertEqual(
        version_a, version_b, f"registries disagree: {version_a!r} != {version_b!r}"
    )


def _assert_version_past_baseline(test, version, baseline=BASELINE_VERSION):
    test.assertGreater(_version_tuple(version), _version_tuple(baseline))


def _canonicalize_manifest(data):
    """Canonical form of a plugin manifest with `version` stripped: sorted
    keys, non-ASCII left unescaped -- so the digest is blind to the version
    bump and sensitive to everything else."""
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


def _assert_em_review_entry_unchanged(test, entry):
    """AC-4: identity fields AND version pinned exactly to their pre-change
    values -- this task must not touch the em-review plugin at all."""
    test.assertEqual(entry.get("name"), EM_REVIEW_NAME)
    test.assertEqual(entry.get("author"), EM_REVIEW_AUTHOR)
    test.assertEqual(entry.get("category"), EM_REVIEW_CATEGORY)
    test.assertEqual(entry.get("source"), EM_REVIEW_SOURCE)
    test.assertEqual(entry.get("version"), EM_REVIEW_VERSION)


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1/AC-2: the plugin manifest's version parses and sits strictly
    past the pre-task baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_manifest_has_a_version_key(self):
        self.assertIn("version", self.data)

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-1/AC-2/AC-3: the em-workflow marketplace entry (found by `name`,
    not position) agrees with the plugin manifest and is past baseline."""

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


class TestEmReviewEntryUnchanged(unittest.TestCase):
    """AC-4: the em-review entry's identity fields and version are unchanged
    from their pre-change values."""

    def test_em_review_entry_unchanged(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        _assert_em_review_entry_unchanged(self, entry)


class TestNoOtherFieldsChanged(unittest.TestCase):
    """AC-5: both manifests still parse as JSON (implicit in `_load_json`
    succeeding), and no field other than `version` changed in either file."""

    def test_plugin_manifest_nonversion_content_unchanged(self):
        data = _load_json(PLUGIN_MANIFEST_PATH)
        self.assertEqual(
            _sha256(_canonicalize_manifest(data)),
            PLUGIN_MANIFEST_NONVERSION_SHA256,
        )

    def test_marketplace_nonversion_content_unchanged(self):
        data = _load_json(MARKETPLACE_PATH)
        self.assertEqual(
            _sha256(_canonicalize_marketplace(data)),
            MARKETPLACE_NONVERSION_SHA256,
        )


class TestVersionComparisonIsDotSeparatedNumeric(unittest.TestCase):
    """AC-2 (hermetic): the comparison helper against synthetic version
    pairs, including a case where whole-string comparison and per-component
    numeric comparison disagree because of a two-digit patch component --
    proves the "past baseline" check is numeric, not a string compare."""

    def test_naive_string_comparison_gets_two_digit_patch_backwards(self):
        # Sanity: demonstrates the failure mode a plain string comparison of
        # full version strings would fall into.
        self.assertGreater("0.1.9", "0.1.10")

    def test_version_tuple_orders_two_digit_patch_correctly(self):
        self.assertGreater(_version_tuple("0.1.10"), _version_tuple("0.1.9"))

    def test_assert_version_past_baseline_is_immune_to_the_string_trap(self):
        # "0.1.10" must be accepted as past a synthetic baseline of "0.1.9",
        # even though "0.1.9" > "0.1.10" as a raw string comparison (proved
        # above) -- this would raise if the helper used naive string
        # comparison instead of the parsed tuple.
        _assert_version_past_baseline(self, "0.1.10", baseline="0.1.9")


class TestValidationDetectsRegressions(unittest.TestCase):
    """AC-2/AC-3/AC-6: a negative proof per matcher, plus a non-vacuity
    guard for the AC-5 digest checks."""

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.1.83", "0.1.84")

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

    FORGED_EM_REVIEW_ENTRY = {
        "name": EM_REVIEW_NAME,
        "author": EM_REVIEW_AUTHOR,
        "category": EM_REVIEW_CATEGORY,
        "source": EM_REVIEW_SOURCE,
        "version": EM_REVIEW_VERSION,
    }

    def test_em_review_matcher_rejects_altered_identity_field(self):
        for field, forged_value in (
            ("name", "em-review-forked"),
            ("author", {"name": "someone-else"}),
            ("category", "other"),
            ("source", "./em-review-forked"),
            ("version", "99.0.0"),
        ):
            with self.subTest(field=field):
                forged = dict(self.FORGED_EM_REVIEW_ENTRY, **{field: forged_value})
                with self.assertRaises(AssertionError):
                    _assert_em_review_entry_unchanged(self, forged)

    def test_digest_check_rejects_a_mutated_nonversion_field(self):
        # Non-vacuity guard for TestNoOtherFieldsChanged: a manifest whose
        # description was altered (version untouched) must NOT match the
        # baseline digest -- proves the digest actually discriminates
        # content, not just presence of the `version` key.
        forged = {
            "name": "em-workflow",
            "description": "a description that was never the baseline one",
            "author": {"name": "em"},
            "version": BASELINE_VERSION,
        }
        self.assertNotEqual(
            _sha256(_canonicalize_manifest(forged)),
            PLUGIN_MANIFEST_NONVERSION_SHA256,
        )

    def test_digest_check_ignores_only_the_version_field(self):
        # Non-vacuity guard: two manifests differing ONLY in `version`
        # canonicalize to the identical digest -- proves the digest is
        # blind to version changes specifically, not to everything.
        base = _load_json(PLUGIN_MANIFEST_PATH)
        forged = dict(base, version="99.0.0")
        self.assertEqual(
            _sha256(_canonicalize_manifest(base)),
            _sha256(_canonicalize_manifest(forged)),
        )


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-6: this new module imports only the standard library (test/
    README.md's "no external dependencies" rule for test code)."""

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
