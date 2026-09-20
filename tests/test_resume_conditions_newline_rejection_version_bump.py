"""Tests for task0002 (resume-conditions-newline-rejection): the em-workflow
plugin version bump in both distribution registries.

Covers task0002 Acceptance Criteria
(feature-docs/resume-conditions-newline-rejection/tasks/task0002.md):

- AC-1: `em-workflow/.claude-plugin/plugin.json` parses as JSON, its `name`
  still reads `em-workflow`, and its `version` is on the `0.1.x` line with a
  patch component strictly greater than `84`.
- AC-2: `.claude-plugin/marketplace.json` parses as JSON, and the
  `plugins[]` entry found by the name `em-workflow` carries a `version`
  equal, as a string, to the plugin manifest's.
- AC-3: the `plugins[]` entry named `em-review` is unchanged -- its name,
  author, category and source are exactly as before, and its version is
  still a dotted numeric string (asserted by shape, never against a
  literal).
- AC-4: each matcher in this module has a negative proof and a non-vacuity
  guard, including a case proving the version comparison is per-component
  numeric rather than whole-string.
- AC-5: this module is discovered by `python3 -m unittest discover -s
  tests`, imports only the standard library, and the full suite passes with
  no new failures relative to the recorded pre-change baseline -- the
  full-suite outcome is command-level (verified by running the command and
  recorded in the implementer report, per the task plan's Test Notes), but
  the stdlib-only import property is a real assertion here.
- AC-6: `python3 em-workflow/scripts/check-plugin-invariants.py` against the
  repository root exits 0 -- command-level, verified the same way (a suite
  cannot assert its own exit code without recursion).

Per IMPLEMENTATION.md D2, task0002 is the sole writer of both manifests; per
D4, this feature's pre-change baseline (`0.1.84`) is higher than any
existing version-bump module's pinned baseline (the highest is `0.1.82`),
which is why this is a new module rather than an edit to an existing one or
to the generic `tests/test_plugin_version_parity.py`.

Matcher -> proof inventory (task0002.md's Matcher inventory table, AC-4):

- `_assert_version_past_baseline` (version-past-baseline): negative proofs
  are `test_fails_when_version_equals_baseline` and
  `test_fails_when_version_below_baseline`; non-vacuity guard is
  `test_negative_proof_versions_parse_cleanly` (the forged strings parse
  cleanly, so the proof exercises the comparison, not a parse failure).
- `_assert_versions_agree` (versions-agree): negative proof is
  `test_fails_when_versions_differ`; non-vacuity guard is the same
  `test_negative_proof_versions_parse_cleanly` (both forged strings parse
  cleanly).
- `_marketplace_entry` (entry-lookup-by-name): negative proof is
  `test_entry_lookup_fails_on_a_missing_entry_name`; non-vacuity guard is
  `test_entry_lookup_succeeds_and_has_a_version_key` (the lookup against the
  real manifest returns a mapping that has a version key).

The comparison-trap case lives in
`TestVersionComparisonIsPerComponentNumeric` below.
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

# Pre-change baseline (task0002.md Design): both registries read 0.1.84
# before this task's edit. The new value must compare strictly greater
# under dot-separated numeric comparison, on the same 0.1.x line.
BASELINE_VERSION = "0.1.84"

# The em-review entry's identity fields, pinned to their exact pre-change
# values (AC-3) -- this task never touches the em-review plugin.
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
    """Look the entry up by its `name` field -- never by array position
    (AC-2/AC-3): the marketplace plugin list's order is not a contract."""
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name!r}")


def _version_tuple(version):
    """Parse a major.minor.patch string into an int 3-tuple, so comparison
    happens per-component and numerically -- never as a whole-string
    comparison, which would sort a two-digit component backwards (e.g.
    "0.1.9" > "0.1.10" lexically; see
    TestVersionComparisonIsPerComponentNumeric below)."""
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


def _assert_em_review_entry_unchanged(test, entry):
    """AC-3: identity fields pinned exactly; version asserted by shape only
    (a dotted numeric string), never against a literal -- that plugin's
    version changes independently of this feature."""
    test.assertEqual(entry.get("name"), EM_REVIEW_NAME)
    test.assertEqual(entry.get("author"), EM_REVIEW_AUTHOR)
    test.assertEqual(entry.get("category"), EM_REVIEW_CATEGORY)
    test.assertEqual(entry.get("source"), EM_REVIEW_SOURCE)
    _version_tuple(entry.get("version"))  # raises AssertionError if malformed


class TestPluginManifestVersion(unittest.TestCase):
    """AC-1: the plugin manifest parses, its name is unchanged, and its
    version sits strictly past the pre-task baseline on the 0.1.x line."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(PLUGIN_MANIFEST_PATH)

    def test_manifest_name_is_em_workflow(self):
        self.assertEqual(self.data.get("name"), "em-workflow")

    def test_manifest_has_a_version_key(self):
        self.assertIn("version", self.data)

    def test_version_is_on_the_0_1_x_line(self):
        major, minor, _patch = _version_tuple(self.data.get("version"))
        self.assertEqual((major, minor), (0, 1))

    def test_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.data.get("version"))


class TestMarketplaceEntryVersion(unittest.TestCase):
    """AC-2: the em-workflow marketplace entry (found by `name`, not
    position) agrees with the plugin manifest and is past baseline."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_json(MARKETPLACE_PATH)
        cls.manifest = _load_json(PLUGIN_MANIFEST_PATH)
        cls.entry = _marketplace_entry(cls.data, "em-workflow")

    def test_entry_lookup_succeeds_and_has_a_version_key(self):
        # Non-vacuity guard for entry-lookup-by-name's negative proof: the
        # lookup against the real manifest returns a mapping with a version
        # key, so the negative proof below exercises the lookup's failure
        # path, not an accident of an always-raising function.
        self.assertIsInstance(self.entry, dict)
        self.assertIn("version", self.entry)

    def test_em_workflow_entry_version_is_past_baseline(self):
        _assert_version_past_baseline(self, self.entry.get("version"))

    def test_em_workflow_entry_version_matches_plugin_manifest(self):
        _assert_versions_agree(
            self, self.entry.get("version"), self.manifest.get("version")
        )


class TestEmReviewEntryUnchanged(unittest.TestCase):
    """AC-3: the em-review entry's identity fields are unchanged and its
    version is still a dotted numeric string."""

    def test_em_review_entry_unchanged(self):
        data = _load_json(MARKETPLACE_PATH)
        entry = _marketplace_entry(data, "em-review")
        _assert_em_review_entry_unchanged(self, entry)


class TestVersionComparisonIsPerComponentNumeric(unittest.TestCase):
    """AC-4 (comparison-trap case): proves the "past baseline" check is
    per-component numeric, not a whole-string comparison, which would sort a
    two-digit component backwards."""

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
    """AC-4: a negative proof per matcher, each paired with a non-vacuity
    guard proving the forged sample is otherwise well-formed
    (IMPLEMENTATION.md D5)."""

    def test_negative_proof_versions_parse_cleanly(self):
        # Non-vacuity guard for the two negative proofs below: the forged
        # strings used in both parse cleanly as versions, so their rejection
        # below is attributable to the comparison, never to a parse failure.
        for forged in (BASELINE_VERSION, "0.1.5", "0.1.83", "0.1.84"):
            with self.subTest(forged=forged):
                _version_tuple(forged)  # must not raise

    def test_fails_when_version_equals_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, BASELINE_VERSION)

    def test_fails_when_version_below_baseline(self):
        with self.assertRaises(AssertionError):
            _assert_version_past_baseline(self, "0.1.5")

    def test_fails_when_versions_differ(self):
        with self.assertRaises(AssertionError):
            _assert_versions_agree(self, "0.1.83", "0.1.84")

    def test_entry_lookup_fails_on_a_missing_entry_name(self):
        forged = {"plugins": [{"name": "some-other-plugin"}]}
        with self.assertRaises(AssertionError):
            _marketplace_entry(forged, "em-workflow")

    FORGED_EM_REVIEW_ENTRY = {
        "name": EM_REVIEW_NAME,
        "author": EM_REVIEW_AUTHOR,
        "category": EM_REVIEW_CATEGORY,
        "source": EM_REVIEW_SOURCE,
        "version": "0.5.11",
    }

    def test_em_review_matcher_rejects_altered_identity_field(self):
        for field, forged_value in (
            ("name", "em-review-forked"),
            ("author", {"name": "someone-else"}),
            ("category", "other"),
            ("source", "./em-review-forked"),
            ("version", "not-a-version"),
        ):
            with self.subTest(field=field):
                forged = dict(self.FORGED_EM_REVIEW_ENTRY, **{field: forged_value})
                with self.assertRaises(AssertionError):
                    _assert_em_review_entry_unchanged(self, forged)


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-5: this new module imports only the standard library (test/
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
