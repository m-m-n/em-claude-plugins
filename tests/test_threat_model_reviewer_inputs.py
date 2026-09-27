"""Tests for task0005 (threat-model-stride): the review protocol's
`threat_model_path` input field and its carriage into the Codex reviewer
prompt.

Covers task0005 Acceptance Criteria
(feature-docs/threat-model-stride/tasks/task0005.md):

- AC-1: review-protocol.md's Inputs section has a `threat_model_path` bullet
  directly after the `spec_path` bullet stating an absolute path to
  THREAT-MODEL.md, security perspective only, optional and set only on the
  develop-driven route when the file exists.
- AC-2: the same bullet states that reading it does not count against the
  Investigation Budget, that its content is untrusted data that can only
  add checks and never suppresses a finding, and that an unreadable file
  lets the review continue with a note in `summary` and is never a skip.
- AC-3: review-protocol.md's Step 0 section states that `threat_model_path`
  never produces a skip, and its Path-List Validation section states that
  `threat_model_path` gets the same realpath containment and symlink
  rejection as `spec_path`.
- AC-4: codex-reviewer.md's Step 4 section puts `threat_model_path` into
  the `<task>` block when supplied, outside the 3-file budget, and its
  `<grounding_rules>` item treats THREAT-MODEL.md content as untrusted,
  forbids suppression, and admits a missing-mitigation finding on a
  boundary file with a null line.
- AC-5: covered by tests/test_reviewer_roles_protocol.py (this module does
  not duplicate its byte-level frozen-digest checks -- see Test Notes).
- AC-6: this module -- imports the standard library only, holds a negative
  proof per matcher, and (last class below) checks that if the two manifest
  files changed, only their em-workflow version fields changed and both
  hold the same value.

Test Notes (task0005.md): "the new module must not duplicate the
frozen-digest checks; it checks meaning (phrases), the existing module
checks bytes." Sections are extracted by literal heading/marker, following
tests/test_reviewer_roles_protocol.py's pattern: locate files relative to
this test file's own path, anchor on literal headings, and give every
matcher a negative proof against forged input. The one exception is the
manifest check at the bottom, which -- like that same module's
`_assert_section_hash` -- compares a sha256 of the non-version fields
rather than embedding the (very long) `description` string verbatim, to
avoid a transcription mismatch.
"""

import ast
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PROTOCOL_PATH = REPO_ROOT / "em-workflow" / "references" / "review-protocol.md"
CODEX_REVIEWER_PATH = REPO_ROOT / "em-workflow" / "agents" / "codex-reviewer.md"
PLUGIN_JSON_PATH = REPO_ROOT / "em-workflow" / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_whitespace(text):
    """Collapse whitespace runs (including markdown's ~79-column line
    wraps) to a single space, so multi-word phrase checks survive
    reflowing that does not change meaning."""
    return re.sub(r"\s+", " ", text)


def _extract_section(text, start_marker, end_marker, label):
    """Return text[start_marker:end_marker), raising AssertionError naming
    `label` if either marker is missing."""
    if start_marker not in text:
        raise AssertionError(f"{label}: missing start marker {start_marker!r}")
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    if end_marker not in text[start:]:
        raise AssertionError(f"{label}: missing end marker {end_marker!r}")
    end = text.index(end_marker, start)
    return text[start:end]


def _assert_phrases_present(text, phrases, label):
    """The shared matcher behind every 'this section states X' assertion
    below: every phrase in `phrases` (case-insensitive, whitespace
    normalized) must occur in `text`."""
    normalized = _normalize_whitespace(text).lower()
    missing = [p for p in phrases if p.lower() not in normalized]
    if missing:
        raise AssertionError(f"{label}: missing phrase(s) {missing!r}")


BULLET_START_RE = re.compile(r"^- `([^`]+)`", re.MULTILINE)


def _bullet_order(text):
    """Return the ordered list of top-level bullet names (the backtick-
    quoted token right after '- ') found in `text`, e.g. ['perspective',
    'perspective_skill', ...] for the Inputs section, or ['<task>',
    '<structured_output_contract>', ...] for codex-reviewer.md's Step 4."""
    return [m.group(1) for m in BULLET_START_RE.finditer(text)]


def _assert_bullet_directly_follows(text, earlier_name, later_name, label):
    """`later_name`'s bullet must be the very next top-level bullet after
    `earlier_name`'s -- not merely present somewhere later in `text`."""
    order = _bullet_order(text)
    if earlier_name not in order:
        raise AssertionError(f"{label}: bullet {earlier_name!r} not found")
    if later_name not in order:
        raise AssertionError(f"{label}: bullet {later_name!r} not found")
    idx = order.index(earlier_name)
    if idx + 1 >= len(order) or order[idx + 1] != later_name:
        raise AssertionError(
            f"{label}: bullet {later_name!r} does not directly follow "
            f"{earlier_name!r} (order: {order!r})"
        )


def _bullet_block(text, name, next_markers):
    """Return the text of the bullet starting '- `{name}`' up to whichever
    of `next_markers` appears first after it (or end of `text`)."""
    marker = f"- `{name}`"
    if marker not in text:
        raise AssertionError(f"bullet {name!r} not found")
    start = text.index(marker)
    end = len(text)
    for nm in next_markers:
        if nm in text[start + len(marker) :]:
            candidate = text.index(nm, start + len(marker))
            end = min(end, candidate)
    return text[start:end]


# ---------------------------------------------------------------------------
# AC-1 / AC-2: the Inputs section's `threat_model_path` bullet
# ---------------------------------------------------------------------------

INPUTS_START = "## Inputs (all reviewers)"
STEP0_START = "## Step 0 Fail-Closed Resolution"
REVIEW_TARGET_START = "## Review Target Resolution"
PATH_LIST_START = "## Path-List Validation (orchestrator-owned)"
INVESTIGATION_BUDGET_START = "## Investigation Budget"

IDENTITY_AND_OPTIONALITY_PHRASES = [
    "absolute path",
    "threat-model.md",
    "security perspective only",
    "optional",
    "develop-driven route",
    "when the file exists",
]

BUDGET_AND_UNTRUSTED_PHRASES = [
    "does not count against",
    "investigation budget",
    "untrusted data",
    "only add checks",
    "never suppress a finding",
]

UNREADABLE_NEVER_SKIP_PHRASES = [
    "unreadable file",
    "review continues",
    "cross-check",
    "summary",
    "never a skip",
]


class TestInputsBulletPlacement(unittest.TestCase):
    """AC-1 (placement): `threat_model_path` is the bullet directly after
    `spec_path` in the Inputs section."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PROTOCOL_PATH)
        cls.inputs_section = _extract_section(
            cls.text, INPUTS_START, STEP0_START, "Inputs section"
        )

    def test_threat_model_path_bullet_directly_follows_spec_path(self):
        _assert_bullet_directly_follows(
            self.inputs_section,
            "spec_path",
            "threat_model_path",
            "Inputs section bullet order",
        )

    def test_placement_matcher_rejects_a_non_adjacent_forged_order(self):
        forged = (
            "- `spec_path` — absolute path to SPEC.md\n"
            "- `project_root` — canonicalized project root\n"
            "- `threat_model_path` — absolute path to THREAT-MODEL.md\n"
        )
        with self.assertRaises(AssertionError):
            _assert_bullet_directly_follows(
                forged, "spec_path", "threat_model_path", "forged order"
            )

    def test_placement_matcher_accepts_a_well_formed_adjacent_order(self):
        forged = (
            "- `spec_path` — absolute path to SPEC.md\n"
            "- `threat_model_path` — absolute path to THREAT-MODEL.md\n"
            "- `project_root` — canonicalized project root\n"
        )
        # Does not raise.
        _assert_bullet_directly_follows(
            forged, "spec_path", "threat_model_path", "well-formed order"
        )


class TestInputsBulletIdentityAndOptionality(unittest.TestCase):
    """AC-1 (content): the bullet states an absolute path to THREAT-MODEL.md,
    security perspective only, optional, develop-driven route when the file
    exists."""

    @classmethod
    def setUpClass(cls):
        text = _read(PROTOCOL_PATH)
        inputs_section = _extract_section(
            text, INPUTS_START, STEP0_START, "Inputs section"
        )
        cls.bullet = _bullet_block(
            inputs_section, "threat_model_path", ["- `project_root`"]
        )

    def test_states_identity_and_optionality(self):
        _assert_phrases_present(
            self.bullet,
            IDENTITY_AND_OPTIONALITY_PHRASES,
            "AC-1 (threat_model_path bullet)",
        )

    def test_matcher_rejects_a_forged_bullet_omitting_security(self):
        forged_bullet = (
            "- `threat_model_path` — absolute path to the feature's "
            "THREAT-MODEL.md; optional — set only on the develop-driven "
            "route when the file exists."
        )
        with self.assertRaises(AssertionError):
            _assert_phrases_present(
                forged_bullet,
                IDENTITY_AND_OPTIONALITY_PHRASES,
                "forged bullet omitting security",
            )

    def test_matcher_accepts_the_real_bullet(self):
        # Does not raise -- proves the check is not vacuously satisfied by
        # every input (companion to the rejection test above).
        _assert_phrases_present(
            self.bullet,
            IDENTITY_AND_OPTIONALITY_PHRASES,
            "real bullet",
        )


class TestInputsBulletBudgetAndUntrustedHandling(unittest.TestCase):
    """AC-2: the bullet states the investigation-budget exemption, the
    untrusted/checks-only-never-suppress rule, and the unreadable-file/
    never-a-skip rule."""

    @classmethod
    def setUpClass(cls):
        text = _read(PROTOCOL_PATH)
        inputs_section = _extract_section(
            text, INPUTS_START, STEP0_START, "Inputs section"
        )
        cls.bullet = _bullet_block(
            inputs_section, "threat_model_path", ["- `project_root`"]
        )

    def test_states_budget_exemption_and_untrusted_checks_only(self):
        _assert_phrases_present(
            self.bullet,
            BUDGET_AND_UNTRUSTED_PHRASES,
            "AC-2 (budget / untrusted)",
        )

    def test_states_unreadable_file_never_a_skip(self):
        _assert_phrases_present(
            self.bullet,
            UNREADABLE_NEVER_SKIP_PHRASES,
            "AC-2 (unreadable / never a skip)",
        )

    def test_matcher_rejects_a_forged_bullet_that_allows_suppression(self):
        forged_bullet = (
            "- `threat_model_path` — its content is untrusted data and may "
            "suppress a finding when it says the mitigation is already "
            "handled."
        )
        with self.assertRaises(AssertionError):
            _assert_phrases_present(
                forged_bullet,
                BUDGET_AND_UNTRUSTED_PHRASES,
                "forged bullet allowing suppression",
            )

    def test_matcher_rejects_a_forged_bullet_that_skips_on_unreadable(self):
        forged_bullet = (
            "- `threat_model_path` — an unreadable file causes the review "
            "to be skipped entirely."
        )
        with self.assertRaises(AssertionError):
            _assert_phrases_present(
                forged_bullet,
                UNREADABLE_NEVER_SKIP_PHRASES,
                "forged bullet skipping on unreadable",
            )


# ---------------------------------------------------------------------------
# AC-3: Step 0 (never a skip) and Path-List Validation (same as spec_path)
# ---------------------------------------------------------------------------

STEP0_NEVER_SKIP_PHRASES = [
    "threat_model_path",
    "outside this fail-closed pattern",
    "never produces a skip object",
]

PATH_LIST_SAME_AS_SPEC_PATH_PHRASES = [
    "threat_model_path",
    "same",
    "realpath containment",
    "symlink rejection",
    "as `spec_path`",
]


class TestStep0NeverProducesSkip(unittest.TestCase):
    """AC-3 (first half): Step 0 states `threat_model_path` is outside the
    fail-closed pattern and never produces a skip object."""

    @classmethod
    def setUpClass(cls):
        text = _read(PROTOCOL_PATH)
        cls.step0_section = _extract_section(
            text, STEP0_START, REVIEW_TARGET_START, "Step 0 section"
        )

    def test_states_never_produces_a_skip(self):
        _assert_phrases_present(
            self.step0_section, STEP0_NEVER_SKIP_PHRASES, "AC-3 (Step 0)"
        )

    def test_matcher_rejects_a_forged_step0_missing_the_exemption(self):
        forged = (
            "Every reviewer's Step 0 MUST resolve the protocol path with "
            "fail-closed semantics. The same fail-closed pattern applies "
            "to `schema_path`, `perspective_skill`, and `spec_path`."
        )
        with self.assertRaises(AssertionError):
            _assert_phrases_present(
                forged, STEP0_NEVER_SKIP_PHRASES, "forged Step 0"
            )


class TestPathListValidationSameAsSpecPath(unittest.TestCase):
    """AC-3 (second half): Path-List Validation states `threat_model_path`
    gets the same realpath containment and symlink rejection as
    `spec_path`."""

    @classmethod
    def setUpClass(cls):
        text = _read(PROTOCOL_PATH)
        cls.path_list_section = _extract_section(
            text,
            PATH_LIST_START,
            INVESTIGATION_BUDGET_START,
            "Path-List Validation section",
        )

    def test_states_same_containment_and_symlink_rejection(self):
        _assert_phrases_present(
            self.path_list_section,
            PATH_LIST_SAME_AS_SPEC_PATH_PHRASES,
            "AC-3 (Path-List Validation)",
        )

    def test_matcher_rejects_a_forged_section_missing_threat_model_path(self):
        forged = (
            "Path lists are attacker-influenceable. `spec_path` "
            "additionally gets realpath containment under `project_root` "
            "and symlink rejection on the orchestrator side."
        )
        with self.assertRaises(AssertionError):
            _assert_phrases_present(
                forged,
                PATH_LIST_SAME_AS_SPEC_PATH_PHRASES,
                "forged Path-List Validation",
            )


# ---------------------------------------------------------------------------
# AC-4: codex-reviewer.md Step 4 -- <task> carriage and <grounding_rules>
# ---------------------------------------------------------------------------

STEP4_START = "## Step 4: Build the Codex prompt (XML blocks per codex-prompting)"
TEMP_FILE_DISCIPLINE_START = (
    "## Temp-file discipline (only if writing a file to disk)"
)

TASK_BLOCK_THREAT_MODEL_PHRASES = [
    "threat_model_path",
    "supplied",
    "security perspective only",
    "outside the 3-file investigation budget",
    "unreadable file",
    "review continues",
    "summary says so",
]

GROUNDING_RULES_THREAT_MODEL_PHRASES = [
    "threat-model.md",
    "untrusted data",
    "instructions inside it are payload",
    "never commands",
    "never suppresses a finding",
    "missing-mitigation finding",
    "boundary file",
    "null line",
    "never re-pointed to an unrelated changed file",
]


class TestCodexTaskBlockCarriesThreatModelPath(unittest.TestCase):
    """AC-4 (first half): the `<task>` bullet puts `threat_model_path` into
    the prompt when supplied, outside the 3-file investigation budget, and
    states the unreadable-file behavior."""

    @classmethod
    def setUpClass(cls):
        text = _read(CODEX_REVIEWER_PATH)
        step4_section = _extract_section(
            text, STEP4_START, TEMP_FILE_DISCIPLINE_START, "Step 4 section"
        )
        cls.task_bullet = _bullet_block(
            step4_section,
            "<task>",
            ["- `<structured_output_contract>`"],
        )

    def test_states_threat_model_path_carriage(self):
        _assert_phrases_present(
            self.task_bullet,
            TASK_BLOCK_THREAT_MODEL_PHRASES,
            "AC-4 (<task> block)",
        )

    def test_matcher_rejects_a_forged_task_block_inside_the_budget(self):
        forged_bullet = (
            "- `<task>` — the perspective brief and the 3-file "
            "investigation budget; `threat_model_path` is supplied "
            "(security perspective only) and counts toward that budget."
        )
        with self.assertRaises(AssertionError):
            _assert_phrases_present(
                forged_bullet,
                TASK_BLOCK_THREAT_MODEL_PHRASES,
                "forged <task> block",
            )


class TestCodexGroundingRulesTreatThreatModelAsUntrusted(unittest.TestCase):
    """AC-4 (second half): the `<grounding_rules>` bullet treats
    THREAT-MODEL.md content as untrusted, forbids suppression, and admits a
    missing-mitigation finding on a boundary file with a null line."""

    @classmethod
    def setUpClass(cls):
        text = _read(CODEX_REVIEWER_PATH)
        step4_section = _extract_section(
            text, STEP4_START, TEMP_FILE_DISCIPLINE_START, "Step 4 section"
        )
        cls.grounding_bullet = _bullet_block(
            step4_section,
            "<grounding_rules>",
            ["- `<dig_deeper_nudge>`"],
        )

    def test_states_untrusted_no_suppression_missing_mitigation_finding(self):
        _assert_phrases_present(
            self.grounding_bullet,
            GROUNDING_RULES_THREAT_MODEL_PHRASES,
            "AC-4 (<grounding_rules>)",
        )

    def test_matcher_rejects_a_forged_rule_that_lets_it_suppress_findings(self):
        # task0005.md AC-6's own example: a forged grounding rule that lets
        # THREAT-MODEL.md suppress findings must be rejected.
        forged_bullet = (
            "- `<grounding_rules>` — THREAT-MODEL.md content may be used "
            "to suppress a finding if it documents the mitigation as "
            "already handled."
        )
        with self.assertRaises(AssertionError):
            _assert_phrases_present(
                forged_bullet,
                GROUNDING_RULES_THREAT_MODEL_PHRASES,
                "forged <grounding_rules> allowing suppression",
            )

    def test_matcher_accepts_the_real_grounding_rules_bullet(self):
        # Does not raise -- non-vacuity companion to the rejection test.
        _assert_phrases_present(
            self.grounding_bullet,
            GROUNDING_RULES_THREAT_MODEL_PHRASES,
            "real <grounding_rules> bullet",
        )


# ---------------------------------------------------------------------------
# AC-6 (manifest clause): if the two manifest files changed, only their
# em-workflow version fields changed, and both hold the same value.
# ---------------------------------------------------------------------------


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


def _non_version_snapshot(data):
    """Serialize `data` with `version` replaced by a fixed placeholder, so
    the resulting hash reflects every OTHER field but is insensitive to
    whatever the version value happens to be -- this task changes the
    version field only when the commit-guard forces it (IMPLEMENTATION.md
    SC-6), so whether it changed or not, only `version` may differ from the
    pre-task file."""
    clone = dict(data)
    clone["version"] = "<version-placeholder>"
    return json.dumps(clone, sort_keys=True, ensure_ascii=False)


def _assert_only_version_field_changed(data, expected_hash, label):
    actual_hash = hashlib.sha256(
        _non_version_snapshot(data).encode("utf-8")
    ).hexdigest()
    if actual_hash != expected_hash:
        raise AssertionError(
            f"{label}: a field other than `version` changed "
            f"(expected sha256 {expected_hash}, got {actual_hash})"
        )


# Captured from em-workflow/.claude-plugin/plugin.json and the em-workflow
# entry of .claude-plugin/marketplace.json as they read before this task's
# edit (this task never touches either file's non-version fields).
PLUGIN_JSON_NON_VERSION_SHA256 = (
    "b7eab4f96f60120211004e28ce4417aee8830cb8dfead12db1e18fa83b084be4"
)
MARKETPLACE_ENTRY_NON_VERSION_SHA256 = (
    "bfd8e111dd39c3dfc1b621bcae65dea2419da9d2930ecccd09a785b53a52f4f0"
)


class TestManifestOnlyVersionFieldChanged(unittest.TestCase):
    """AC-6: if the two manifest files changed at all, only their
    em-workflow version fields changed, and both hold the same value.
    Written so that a completely-unchanged pair (the commit-guard did not
    force a bump) also satisfies it trivially."""

    @classmethod
    def setUpClass(cls):
        cls.plugin_data = _load_json(PLUGIN_JSON_PATH)
        cls.marketplace_data = _load_json(MARKETPLACE_PATH)
        cls.marketplace_entry = _marketplace_entry(
            cls.marketplace_data, "em-workflow"
        )

    def test_plugin_json_no_field_other_than_version_changed(self):
        _assert_only_version_field_changed(
            self.plugin_data, PLUGIN_JSON_NON_VERSION_SHA256, "plugin.json"
        )

    def test_marketplace_entry_no_field_other_than_version_changed(self):
        _assert_only_version_field_changed(
            self.marketplace_entry,
            MARKETPLACE_ENTRY_NON_VERSION_SHA256,
            "marketplace.json em-workflow entry",
        )

    def test_both_manifests_hold_the_same_version_value(self):
        self.assertEqual(
            self.plugin_data.get("version"),
            self.marketplace_entry.get("version"),
            "plugin.json and the marketplace em-workflow entry must hold "
            "the same version value",
        )

    def test_matcher_rejects_a_forged_manifest_with_an_unrelated_field_edit(
        self,
    ):
        forged = dict(self.plugin_data)
        forged["description"] = "a silently rewritten description"
        with self.assertRaises(AssertionError):
            _assert_only_version_field_changed(
                forged, PLUGIN_JSON_NON_VERSION_SHA256, "forged plugin.json"
            )

    def test_matcher_accepts_a_forged_manifest_with_only_version_bumped(self):
        forged = dict(self.plugin_data)
        forged["version"] = "99.0.0"
        # Does not raise -- a version-only change is exactly what this
        # check must tolerate.
        _assert_only_version_field_changed(
            forged, PLUGIN_JSON_NON_VERSION_SHA256, "forged plugin.json"
        )


# ---------------------------------------------------------------------------
# AC-6 (module hygiene): standard library only
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-6: this module imports the standard library only."""

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
