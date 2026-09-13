"""Tests for task0005 (codex-wrapper-fallback-removal, verify rework round
1): the two integrated checks VERIFICATION.md's "Integrated checks that
belong only to this phase" states in prose become machine-checked.

Covers task0005 Acceptance Criteria
(feature-docs/codex-wrapper-fallback-removal/tasks/task0005.md):

- AC-1 (IC1, FR7/NFR4): neither removed phrase occurs in any UTF-8-decodable
  file under `em-workflow/` or `em-review/` (Tier A).
- AC-2 (IC1): every git-tracked file containing either phrase has a path
  whose first segment is `feature-docs`, `test-docs` or `tests` (Tier B).
- AC-3 (IC1, non-vacuity): both the Tier A and the Tier B matcher carry a
  negative proof (forged input containing the defect is rejected) and a
  non-vacuity guard (forged input without the defect is accepted).
- AC-4 (IC2, NFR6): `tests/test_reviewer_roles_protocol.py` declares
  `DIGEST_SOURCE_DOCUMENTS`, built from that module's own `*_PATH`
  constants (naming `em-workflow/agents/codex-reviewer.md` among them),
  plus the rule sentence that a task declaring one of those documents must
  also declare this module.
- AC-5 (IC2, NFR6): this module reads `tests/test_reviewer_roles_protocol.py`
  as text -- never imports it -- and asserts AC-4's declaration is present
  and names the agent document; a forged module text missing the
  declaration is rejected.
- AC-6 (IC2, no weakening): this module asserts
  `tests/test_reviewer_roles_protocol.py` still declares every baseline
  test class name and at least as many 64-hex-digit digest constants as it
  did before this task, in the not-below direction (never equality, per
  IMPLEMENTATION.md's Version-assertion baseline rule); no digest VALUE is
  duplicated into this module. A forged text with one class or one digest
  removed is rejected.
- AC-7 (IC2, preservation): not independently automatable beyond AC-6's
  regression guard (which mechanically rejects removal of any baseline
  class or digest) and the whole-suite run staying green; the diff-purity
  claim (no existing assertion/helper/class changed) is confirmed by
  inspection at commit time, not by a test here.
- AC-8 (NFR5): this module imports the Python standard library only,
  reaches no network and no real provider (it touches only local files and
  `git ls-files`), and both project test commands exit 0.

Test authoring follows `tests/test_wrapper_fallback_doc_realignment.py`'s
form: standard library only, no import from another test module, every
constant re-declared locally, and every new matcher carries a negative
proof plus a non-vacuity guard over forged input.

Tier A enumeration follows `tests/test_reference_sweep.py`'s
`_iter_plugin_directory_files` (`os.walk` over the plugin trees, skipping
any file whose bytes do not decode as UTF-8). Tier B enumeration follows
`tests/test_commit_docs.py`'s existing use of `subprocess` for git
plumbing, via `git ls-files -z` from the repository root -- not `os.walk`,
because an untracked sibling worktree under `.claude/worktrees/` (gitignored
at the main repo root, per `.gitignore`) can otherwise carry a whole copy of
`feature-docs/...` at a path whose first segment is not one of the three
allowed areas.

TDD-awkward (Test Notes): AC-1 and AC-2 pass the moment they are written --
the four documents this feature edited are already clean and every current
tracked occurrence already lies inside the three allowed areas. Their value
is as regression guards, so the confirmed red is on the matchers behind
AC-3 and AC-6 instead: each of `_assert_removed_phrases_absent`,
`_assert_occurrences_contained` and `_assert_no_class_or_digest_removed` was
first run as a no-op that never raises, which made its own "rejects forged
bad input" test fail with "AssertionError not raised" (the reject test, not
the accept test -- the accept/well-formed tests pass regardless of the
no-op), then corrected to the raising form shown below. AC-4/AC-5 are the
one place this module's own tests were red against real files before any
implementation existed: before `tests/test_reviewer_roles_protocol.py`
gained the declaration, reading it as text and asserting the declaration is
present failed for the right reason (`DIGEST_SOURCE_DOCUMENTS declaration
not found`).
"""

import ast
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_TREES = (REPO_ROOT / "em-workflow", REPO_ROOT / "em-review")
PROTOCOL_TEST_MODULE_PATH = REPO_ROOT / "tests" / "test_reviewer_roles_protocol.py"

REMOVED_PHRASES = (
    "whether a fallback provider answered",
    "The wrapper's reply may come from a fallback provider",
)

ALLOWED_CONTAINMENT_TOP_SEGMENTS = frozenset({"feature-docs", "test-docs", "tests"})

# task0005 Design ("Integrated check 2's durable half (TS14)"): the
# module-level constant `tests/test_reviewer_roles_protocol.py` must declare,
# and the four source documents it must name -- one per that module's own
# `*_PATH` constant, so this list is a plain restatement, never a second
# source of truth for the paths themselves (those live only in that module).
DIGEST_DECLARATION_CONSTANT_NAME = "DIGEST_SOURCE_DOCUMENTS"
REQUIRED_SOURCE_DOCUMENT_NAMES = (
    "em-workflow/references/review-protocol.md",
    "em-workflow/references/review-output-schema.json",
    "em-workflow/agents/reviewer.md",
    "em-workflow/agents/codex-reviewer.md",
)
RULE_SENTENCE_PHRASES = (
    "must also declare this module",
    "forces this module's digest to be recomputed",
)

# Baseline captured from `tests/test_reviewer_roles_protocol.py` as it stood
# immediately before this task (task0004 + task0007's rework, pre-task0005).
BASELINE_TEST_CLASS_NAMES = (
    "TestSingleReviewerDispatchStatement",
    "TestNoSecondOpinionFramingSurvives",
    "TestFrozenInputFieldNames",
    "TestFrozenSkipReasonStrings",
    "TestFrozenSeverityLevels",
    "TestFrozenSectionsUnchanged",
    "TestReviewOutputSchemaCategoryWidened",
    "TestReviewerAgentFallbackRoleStatement",
    "TestCodexReviewerAgentPrimaryRoleStatement",
    "TestValidationDetectsRegressions",
    "TestProtocolTriggerFramingCoversBothRoutes",
    "TestReviewerAgentTriggerFramingCoversBothRoutes",
)
BASELINE_DIGEST_CONSTANT_COUNT = 9

CLASS_DECLARATION_PATTERN = re.compile(r"^class (\w+)", re.MULTILINE)
DIGEST_HEX_PATTERN = re.compile(r'"([0-9a-fA-F]{64})"')


def _iter_plugin_directory_files(plugin_root):
    """Mirrors `tests/test_reference_sweep.py`'s helper of the same name."""
    for dirpath, _dirnames, filenames in os.walk(plugin_root):
        for filename in filenames:
            yield Path(dirpath) / filename


def _try_read_utf8_strict(path):
    """Returns the file's text if it decodes as UTF-8, else None -- a
    `__pycache__` artefact or any other non-UTF-8 byte content is skipped
    rather than aborting the sweep (task0005 Design, Tier A)."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _git_tracked_files(repo_root):
    """The only subprocess in this module (Test Notes): `git ls-files -z`
    from the repository root. Uses `check=True` so a missing/broken git
    fails this test loudly via `CalledProcessError` rather than silently
    returning an empty list that would make AC-2 vacuously true."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(repo_root),
        capture_output=True,
        check=True,
    )
    raw = result.stdout.decode("utf-8")
    return [entry for entry in raw.split("\0") if entry]


# ---------------------------------------------------------------------------
# Tier A matcher (AC-1, AC-3): neither removed phrase in any file's content
# ---------------------------------------------------------------------------


def _assert_removed_phrases_absent(file_contents, phrases):
    """`file_contents`: iterable of (label, text) pairs. Raises naming the
    offending label and phrase if any phrase occurs in any text."""
    for label, text in file_contents:
        for phrase in phrases:
            if phrase in text:
                raise AssertionError(
                    f"removed phrase {phrase!r} still occurs in {label!r}"
                )


FORGED_FILE_CONTENTS_CLEAN = (
    ("fake/doc.md", "The wrapper launches codex exec exactly once."),
)
FORGED_FILE_CONTENTS_WITH_PHRASE = (
    (
        "fake/doc.md",
        "The wrapper's reply may come from a fallback provider, so record it.",
    ),
)


class TestTierAMatcherNegativeProof(unittest.TestCase):
    """AC-3 (Tier A): negative proof + non-vacuity guard for
    `_assert_removed_phrases_absent` against forged file content."""

    def test_forged_dirty_content_is_well_formed(self):
        label, text = FORGED_FILE_CONTENTS_WITH_PHRASE[0]
        self.assertIn(REMOVED_PHRASES[1], text)

    def test_forged_content_with_phrase_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_removed_phrases_absent(
                FORGED_FILE_CONTENTS_WITH_PHRASE, REMOVED_PHRASES
            )

    def test_forged_clean_content_is_accepted(self):
        # Does not raise.
        _assert_removed_phrases_absent(FORGED_FILE_CONTENTS_CLEAN, REMOVED_PHRASES)


# ---------------------------------------------------------------------------
# AC-1: Tier A real sweep over em-workflow/ and em-review/
# ---------------------------------------------------------------------------


class TestTierARemovedPhraseSweep(unittest.TestCase):
    """AC-1: neither removed phrase occurs in any UTF-8-decodable file under
    `em-workflow/` or `em-review/`."""

    def test_no_removed_phrase_under_plugin_trees(self):
        file_contents = []
        for plugin_root in PLUGIN_TREES:
            for path in _iter_plugin_directory_files(plugin_root):
                text = _try_read_utf8_strict(path)
                if text is None:
                    continue
                file_contents.append((str(path.relative_to(REPO_ROOT)), text))
        self.assertTrue(
            file_contents,
            "sanity check: expected at least one UTF-8-decodable file under "
            "the plugin trees -- an empty walk would make this vacuously "
            "true",
        )
        _assert_removed_phrases_absent(file_contents, REMOVED_PHRASES)


# ---------------------------------------------------------------------------
# Tier B matcher (AC-2, AC-3): every tracked occurrence's path is contained
# ---------------------------------------------------------------------------


def _assert_occurrences_contained(occurrence_paths, allowed_top_segments):
    for rel_path in occurrence_paths:
        top_segment = PurePosixPath(rel_path).parts[0]
        if top_segment not in allowed_top_segments:
            raise AssertionError(
                f"occurrence at {rel_path!r} lies outside the allowed areas "
                f"{sorted(allowed_top_segments)!r}"
            )


FORGED_OCCURRENCE_PATHS_WITH_OUTSIDE_OCCURRENCE = (
    "feature-docs/codex-wrapper-fallback-removal/SPEC.md",
    "README.md",  # repository-root path: outside the three allowed areas
)
FORGED_OCCURRENCE_PATHS_ALL_INSIDE = (
    "feature-docs/codex-wrapper-fallback-removal/SPEC.md",
    "test-docs/codex-wrapper-fallback-removal/task0002.tests.yaml",
    "tests/test_question_resolution_doc.py",
)


class TestTierBMatcherNegativeProof(unittest.TestCase):
    """AC-3 (Tier B): negative proof + non-vacuity guard for
    `_assert_occurrences_contained` against forged occurrence-path lists."""

    def test_forged_outside_occurrence_is_well_formed(self):
        self.assertEqual(
            PurePosixPath(
                FORGED_OCCURRENCE_PATHS_WITH_OUTSIDE_OCCURRENCE[1]
            ).parts[0],
            "README.md",
        )

    def test_forged_list_with_outside_occurrence_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_occurrences_contained(
                FORGED_OCCURRENCE_PATHS_WITH_OUTSIDE_OCCURRENCE,
                ALLOWED_CONTAINMENT_TOP_SEGMENTS,
            )

    def test_forged_list_all_inside_is_accepted(self):
        # Does not raise.
        _assert_occurrences_contained(
            FORGED_OCCURRENCE_PATHS_ALL_INSIDE, ALLOWED_CONTAINMENT_TOP_SEGMENTS
        )


# ---------------------------------------------------------------------------
# AC-2: Tier B real sweep over git-tracked files
# ---------------------------------------------------------------------------


class TestTierBChangeSetContainmentSweep(unittest.TestCase):
    """AC-2: every git-tracked file containing either removed phrase has a
    path whose first segment is `feature-docs`, `test-docs` or `tests`."""

    def test_tracked_occurrences_are_contained_in_allowed_areas(self):
        tracked_files = _git_tracked_files(REPO_ROOT)
        self.assertGreater(
            len(tracked_files),
            500,
            "sanity check: `git ls-files` must enumerate the repository's "
            "real tracked-file set, not an empty/truncated list -- an empty "
            "enumeration would make this check vacuously true",
        )
        occurrence_paths = []
        for rel_path in tracked_files:
            data = (REPO_ROOT / rel_path).read_bytes()
            text = data.decode("utf-8", errors="ignore")
            if any(phrase in text for phrase in REMOVED_PHRASES):
                occurrence_paths.append(rel_path)
        self.assertTrue(
            occurrence_paths,
            "sanity check: expected at least one tracked occurrence of a "
            "removed phrase (the feature-docs/test-docs/tests history that "
            "deliberately quotes it)",
        )
        _assert_occurrences_contained(occurrence_paths, ALLOWED_CONTAINMENT_TOP_SEGMENTS)


# ---------------------------------------------------------------------------
# TS14 matcher (AC-4, AC-5): the digest-source declaration is present
# ---------------------------------------------------------------------------


def _assert_digest_source_declaration_present(module_text):
    if DIGEST_DECLARATION_CONSTANT_NAME not in module_text:
        raise AssertionError(
            f"{DIGEST_DECLARATION_CONSTANT_NAME} declaration not found"
        )
    for name in REQUIRED_SOURCE_DOCUMENT_NAMES:
        if name not in module_text:
            raise AssertionError(f"source document {name!r} not named")
    for phrase in RULE_SENTENCE_PHRASES:
        if phrase not in module_text:
            raise AssertionError(f"rule sentence phrase {phrase!r} missing")


FORGED_MODULE_TEXT_WITHOUT_DECLARATION = (
    "PROTOCOL_PATH = REPO_ROOT / 'em-workflow' / 'references' / "
    "'review-protocol.md'\n"
    "CODEX_REVIEWER_AGENT_PATH = REPO_ROOT / 'em-workflow' / 'agents' / "
    "'codex-reviewer.md'\n"
    "class TestSomething(unittest.TestCase):\n    pass\n"
)


class TestDigestSourceDeclarationMatcherNegativeProof(unittest.TestCase):
    """AC-5: negative proof for `_assert_digest_source_declaration_present`
    against a forged module text that never declares
    `DIGEST_SOURCE_DOCUMENTS`."""

    def test_forged_text_without_declaration_is_well_formed_otherwise(self):
        self.assertNotIn(
            DIGEST_DECLARATION_CONSTANT_NAME, FORGED_MODULE_TEXT_WITHOUT_DECLARATION
        )
        self.assertIn(
            "codex-reviewer.md", FORGED_MODULE_TEXT_WITHOUT_DECLARATION
        )

    def test_forged_text_without_declaration_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_digest_source_declaration_present(
                FORGED_MODULE_TEXT_WITHOUT_DECLARATION
            )


# ---------------------------------------------------------------------------
# AC-4, AC-5: the real declaration in tests/test_reviewer_roles_protocol.py
# ---------------------------------------------------------------------------


class TestDigestSourceDeclarationPresentInProtocolModule(unittest.TestCase):
    """AC-4, AC-5: `tests/test_reviewer_roles_protocol.py` declares
    `DIGEST_SOURCE_DOCUMENTS` (naming all four of its own `*_PATH`
    constants, including `em-workflow/agents/codex-reviewer.md`) plus the
    rule sentence -- read here as text; this module never imports the
    other."""

    def test_declaration_and_rule_sentence_present(self):
        module_text = PROTOCOL_TEST_MODULE_PATH.read_text(encoding="utf-8")
        _assert_digest_source_declaration_present(module_text)


# ---------------------------------------------------------------------------
# No-weakening matcher (AC-6): baseline classes/digests survive, not-below
# ---------------------------------------------------------------------------


def _assert_no_class_or_digest_removed(
    module_text, baseline_class_names, baseline_digest_count
):
    declared_classes = set(CLASS_DECLARATION_PATTERN.findall(module_text))
    missing_classes = [c for c in baseline_class_names if c not in declared_classes]
    if missing_classes:
        raise AssertionError(f"test class(es) removed: {missing_classes}")
    digest_count = len(DIGEST_HEX_PATTERN.findall(module_text))
    if digest_count < baseline_digest_count:
        raise AssertionError(
            "digest constant count dropped below baseline "
            f"({digest_count} < {baseline_digest_count})"
        )


# Synthetic fixtures (not a mutation of the real, large file) so the
# negative proof is deterministic and independent of that file's actual
# content.
_SYNTHETIC_BASELINE_CLASSES = ("TestAlpha", "TestBeta")
_SYNTHETIC_BASELINE_DIGEST_COUNT = 2
_SYNTHETIC_HASH_ONE = "a" * 64
_SYNTHETIC_HASH_TWO = "b" * 64

SYNTHETIC_MODULE_TEXT_COMPLETE = (
    "class TestAlpha(unittest.TestCase):\n    pass\n\n"
    "class TestBeta(unittest.TestCase):\n    pass\n\n"
    f'HASH_ONE = "{_SYNTHETIC_HASH_ONE}"\n'
    f'HASH_TWO = "{_SYNTHETIC_HASH_TWO}"\n'
)
SYNTHETIC_MODULE_TEXT_MISSING_CLASS = (
    "class TestAlpha(unittest.TestCase):\n    pass\n\n"
    f'HASH_ONE = "{_SYNTHETIC_HASH_ONE}"\n'
    f'HASH_TWO = "{_SYNTHETIC_HASH_TWO}"\n'
)
SYNTHETIC_MODULE_TEXT_MISSING_DIGEST = (
    "class TestAlpha(unittest.TestCase):\n    pass\n\n"
    "class TestBeta(unittest.TestCase):\n    pass\n\n"
    f'HASH_ONE = "{_SYNTHETIC_HASH_ONE}"\n'
)


class TestNoWeakeningMatcherNegativeProof(unittest.TestCase):
    """AC-6: negative proof + non-vacuity guard for
    `_assert_no_class_or_digest_removed`, over synthetic fixtures rather
    than a mutation of the real (large) protocol test module."""

    def test_synthetic_missing_class_fixture_is_well_formed(self):
        self.assertNotIn("class TestBeta", SYNTHETIC_MODULE_TEXT_MISSING_CLASS)
        self.assertIn("class TestAlpha", SYNTHETIC_MODULE_TEXT_MISSING_CLASS)

    def test_synthetic_missing_digest_fixture_is_well_formed(self):
        self.assertEqual(
            len(DIGEST_HEX_PATTERN.findall(SYNTHETIC_MODULE_TEXT_MISSING_DIGEST)), 1
        )

    def test_synthetic_text_missing_a_class_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_no_class_or_digest_removed(
                SYNTHETIC_MODULE_TEXT_MISSING_CLASS,
                _SYNTHETIC_BASELINE_CLASSES,
                _SYNTHETIC_BASELINE_DIGEST_COUNT,
            )

    def test_synthetic_text_missing_a_digest_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_no_class_or_digest_removed(
                SYNTHETIC_MODULE_TEXT_MISSING_DIGEST,
                _SYNTHETIC_BASELINE_CLASSES,
                _SYNTHETIC_BASELINE_DIGEST_COUNT,
            )

    def test_synthetic_complete_text_is_accepted(self):
        # Does not raise.
        _assert_no_class_or_digest_removed(
            SYNTHETIC_MODULE_TEXT_COMPLETE,
            _SYNTHETIC_BASELINE_CLASSES,
            _SYNTHETIC_BASELINE_DIGEST_COUNT,
        )


# ---------------------------------------------------------------------------
# AC-6: the real baseline-preservation check against the protocol module
# ---------------------------------------------------------------------------


class TestBaselineClassesAndDigestsPreservedInProtocolModule(unittest.TestCase):
    """AC-6: `tests/test_reviewer_roles_protocol.py` still declares every
    baseline test class and at least as many 64-hex-digit digest constants
    as it did before this task -- not-below, never equality (IMPLEMENTATION
    .md's Version-assertion baseline rule). No digest VALUE from that module
    is duplicated here; only the count is compared."""

    def test_no_baseline_class_or_digest_removed(self):
        module_text = PROTOCOL_TEST_MODULE_PATH.read_text(encoding="utf-8")
        _assert_no_class_or_digest_removed(
            module_text, BASELINE_TEST_CLASS_NAMES, BASELINE_DIGEST_CONSTANT_COUNT
        )


# ---------------------------------------------------------------------------
# AC-8: this module's own imports are standard-library only
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-8: this module imports the Python standard library only."""

    def test_own_imports_are_all_stdlib(self):
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=__file__)

        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported, "expected at least one import in this module")
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


# ---------------------------------------------------------------------------
# Files exist
# ---------------------------------------------------------------------------


class TestFilesExist(unittest.TestCase):
    def test_all_referenced_paths_exist(self):
        for path in (*PLUGIN_TREES, PROTOCOL_TEST_MODULE_PATH):
            self.assertTrue(path.exists(), f"expected {path} to exist")


if __name__ == "__main__":
    unittest.main()
