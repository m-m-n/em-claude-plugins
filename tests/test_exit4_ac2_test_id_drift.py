"""Tests for exit4-ac2-test-id-drift task0001: every acceptance test ID
recorded in `test-docs/exit4-tip-argument/task0002.tests.yaml` resolves under
the standard unittest runner, and the AC-2 record plus the module docstring of
`tests/test_exit4_tip_argument_version_bump.py` describe the assertions that
actually exist.

Covers task0001 Acceptance Criteria
(feature-docs/exit4-ac2-test-id-drift/tasks/task0001.md):

- AC-1 (FR1): AC-2's `tests` holds exactly four IDs, the fourth is the
  replacement ID, and the stale ID appears nowhere in the record
  (TestTargetRecordIds).
- AC-2 (FR2): AC-2's red_reason wording (TestAc2RedReasonWording).
- AC-3 (FR3, FR4): the version_bump module docstring wording
  (TestVersionBumpDocstringWording).
- AC-4 (FR5, FR6): the explicit target list and the resolution of every
  extracted ID (TestTargetEnumeration, TestRecordedIdsResolve).
- AC-5 (FR5): the aggregate check lists every unresolved ID
  (TestAggregateCheck).
- AC-6 (FR7): the negative proof and the non-vacuity guards
  (TestResolutionJudge, TestTargetRecordIds).
- AC-7 (NFR1): this module imports only the standard library
  (TestModuleImports).

Resolving an ID imports its module but never runs a test and never calls a
resolved object. A `tests.`-prefixed ID is resolvable only while the
repository root is on `sys.path`, so every resolution runs inside
`repo_root_importable()`.
"""

import ast
import contextlib
import importlib
import inspect
import re
import sys
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_BUMP_MODULE_PATH = REPO_ROOT / "tests" / "test_exit4_tip_argument_version_bump.py"

TARGET_RECORD = REPO_ROOT / "test-docs" / "exit4-tip-argument" / "task0002.tests.yaml"
# FR6: an explicit enumeration. Never a glob or directory scan of test-docs/.
TARGET_RECORDS = (TARGET_RECORD,)

MODULE_ID = "tests.test_exit4_tip_argument_version_bump"
CLASS_ID = MODULE_ID + ".TestMarketplaceEntryVersion"
STALE_ID = CLASS_ID + ".test_em_review_entry_has_no_version_key"
REPLACEMENT_ID = CLASS_ID + ".test_em_review_entry_version_not_bumped_with_em_workflow"

AC2_PAST_BASELINE_TEST = "test_em_workflow_entry_version_is_past_baseline"
AC2_EQUALITY_TEST = "test_em_workflow_entry_version_matches_plugin_manifest"
AC2_EM_REVIEW_SOURCE_TEST = "test_em_review_entry_source_unchanged"
AC2_EM_REVIEW_VERSION_TEST = "test_em_review_entry_version_not_bumped_with_em_workflow"
AC2_TEST_METHODS = (
    AC2_PAST_BASELINE_TEST,
    AC2_EQUALITY_TEST,
    AC2_EM_REVIEW_SOURCE_TEST,
    AC2_EM_REVIEW_VERSION_TEST,
)

EXPECTED_ID_COUNTS = {"AC-1": 2, "AC-2": 4, "AC-3": 1, "AC-4": 4, "AC-5": 0}

OBSERVED_RED_CLAUSE = (
    "AssertionError: (0, 1, 68) not greater than (0, 1, 68) "
    "(marketplace.json em-workflow entry still 0.1.68, the pre-bump value at the "
    "feature's diff base, before the bump; baseline patch 68)"
)
OLD_RED_REASON_PHRASE = "that entry is untouched"
STALE_METHOD_NAME = "has_no_version_key"
OLD_DOCSTRING_STRINGS = ("no `version` key", "no-version-key")

Resolution = namedtuple("Resolution", ["resolved", "reason"])


# --- import-path setup -----------------------------------------------------


@contextlib.contextmanager
def repo_root_importable():
    """Put the repository root on `sys.path` for the duration of the block and
    take it off again afterwards -- unless it was already there, in which case
    the existing entry is left alone."""
    root = str(REPO_ROOT)
    if root in sys.path:
        yield
        return
    sys.path.insert(0, root)
    importlib.invalidate_caches()
    try:
        yield
    finally:
        sys.path.remove(root)


# --- ID extractor ------------------------------------------------------------

_AC_KEY_RE = re.compile(r"^  ([^\s:#][^:]*):\s*$")
_TESTS_KEY_RE = re.compile(r"^    tests:(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s+- (.+)$")
_ID_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _is_blank_or_comment(line):
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def _strip_trailing_comment(text):
    return re.sub(r"\s+#.*$", "", text).strip()


def read_ac_blocks(path):
    """Return `[(ac_key, body_lines)]` for the `acceptance_tests` block of the
    tests.yaml at `path`, in file order. Fails (AssertionError) when the block
    or its AC keys cannot be found."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for number, line in enumerate(lines):
        if re.match(r"^acceptance_tests:\s*$", line):
            start = number
            break
    if start is None:
        raise AssertionError(f"{path}: no top-level `acceptance_tests:` block")
    blocks = []
    for line in lines[start + 1 :]:
        if _is_blank_or_comment(line):
            continue
        if _indent(line) == 0:
            break
        if _indent(line) == 2:
            match = _AC_KEY_RE.match(line)
            if match is None:
                raise AssertionError(f"{path}: unrecognised acceptance_tests entry {line!r}")
            if any(key == match.group(1) for key, _ in blocks):
                raise AssertionError(f"{path}: duplicate AC key {match.group(1)!r}")
            blocks.append((match.group(1), []))
            continue
        if not blocks:
            raise AssertionError(f"{path}: content before the first AC key: {line!r}")
        blocks[-1][1].append(line)
    if not blocks:
        raise AssertionError(f"{path}: `acceptance_tests:` holds no AC keys")
    return blocks


def _ids_of_block(path, ac_key, body):
    tests_lines = [number for number, line in enumerate(body) if _TESTS_KEY_RE.match(line)]
    if len(tests_lines) != 1:
        raise AssertionError(
            f"{path}: {ac_key} must carry exactly one `tests` key, found {len(tests_lines)}"
        )
    first = tests_lines[0]
    inline = _strip_trailing_comment(_TESTS_KEY_RE.match(body[first]).group(1))
    if inline == "[]":
        return []
    if inline:
        raise AssertionError(
            f"{path}: {ac_key} `tests` has the unsupported form {inline!r}; "
            "expected `[]` or a block list of IDs"
        )
    ids = []
    for line in body[first + 1 :]:
        if _is_blank_or_comment(line):
            continue
        item = _LIST_ITEM_RE.match(line)
        if item is not None and _indent(line) >= 4:
            value = _strip_trailing_comment(item.group(1))
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if _ID_RE.match(value) is None:
                raise AssertionError(
                    f"{path}: {ac_key} `tests` entry {value!r} is not a dotted test ID"
                )
            ids.append(value)
            continue
        if _indent(line) > 4:
            raise AssertionError(
                f"{path}: {ac_key} `tests` holds content that is not a list of IDs: {line!r}"
            )
        break
    if not ids:
        raise AssertionError(f"{path}: {ac_key} `tests` is a block list with no IDs")
    return ids


def extract_acceptance_test_ids(path):
    """Return `{ac_key: [test IDs]}` for the tests.yaml at `path`, in file
    order. An AC whose `tests` is `[]` yields an empty list. Any other shape of
    `tests` fails (AssertionError) with a message naming the file and the AC,
    so a malformed record can never silently yield zero IDs."""
    return {
        ac_key: _ids_of_block(path, ac_key, body) for ac_key, body in read_ac_blocks(path)
    }


def flatten_ids(ids_by_ac):
    return [test_id for ids in ids_by_ac.values() for test_id in ids]


# --- resolution judge --------------------------------------------------------

_MISSING = object()


def _resolve_structurally(dotted):
    """Resolve without running or calling anything: the longest importable
    dotted prefix must be a module, and what remains must be nothing, a
    test-case class, or a test-case class plus a method defined on it."""
    if _ID_RE.match(dotted) is None:
        return Resolution(False, "not a dotted identifier")
    parts = dotted.split(".")
    module = None
    rest = []
    for cut in range(len(parts), 0, -1):
        name = ".".join(parts[:cut])
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        except Exception as exc:  # the module's own body failed
            return Resolution(False, f"importing {name} raised {type(exc).__name__}: {exc}")
        rest = parts[cut:]
        break
    if module is None:
        return Resolution(False, "no importable module prefix")
    if not rest:
        return Resolution(True, f"module {module.__name__}")
    owner = getattr(module, rest[0], _MISSING)
    if owner is _MISSING:
        return Resolution(False, f"module {module.__name__} has no attribute {rest[0]!r}")
    if not (isinstance(owner, type) and issubclass(owner, unittest.TestCase)):
        return Resolution(False, f"{module.__name__}.{rest[0]} is not a test-case class")
    if len(rest) == 1:
        return Resolution(True, f"test-case class {owner.__qualname__}")
    if len(rest) > 2:
        return Resolution(False, f"{owner.__qualname__} has no nested path {'.'.join(rest[1:])!r}")
    for klass in owner.__mro__:
        if klass in unittest.TestCase.__mro__:
            break
        if inspect.isfunction(vars(klass).get(rest[1])):
            return Resolution(True, f"method {owner.__qualname__}.{rest[1]}")
    return Resolution(False, f"{owner.__qualname__} defines no method {rest[1]!r}")


def _flatten_suite(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten_suite(item)
        else:
            yield item


def _loader_failure(dotted):
    """Ask the standard loader to resolve `dotted` and report why it failed,
    or None when it did not. The loader may signal a missing attribute without
    raising: it records the error in `loader.errors` and returns a failure
    placeholder instead. Loading builds test instances; it runs none."""
    loader = unittest.TestLoader()
    try:
        suite = loader.loadTestsFromName(dotted)
    except Exception as exc:
        return f"standard loader raised {type(exc).__name__}: {exc}"
    if loader.errors:
        lines = loader.errors[0].strip().splitlines()
        return "standard loader recorded an error: " + (lines[-1] if lines else "(empty)")
    for case in _flatten_suite(suite):
        if type(case).__name__ == "_FailedTest":
            return f"standard loader returned a failure placeholder: {case.id()}"
    return None


def resolve_id(dotted):
    """Judge whether one dotted acceptance test ID resolves. Never runs a test
    and never calls a resolved object."""
    with repo_root_importable():
        result = _resolve_structurally(dotted)
        if not result.resolved:
            return result
        failure = _loader_failure(dotted)
        if failure is not None:
            return Resolution(False, failure)
        return result


def assert_ids_resolve(ids):
    """Pass exactly when every ID resolves; otherwise fail with a message that
    lists every unresolved ID (and no resolved one)."""
    with repo_root_importable():
        unresolved = []
        for test_id in ids:
            result = resolve_id(test_id)
            if not result.resolved:
                unresolved.append(f"  {test_id}  ({result.reason})")
    if unresolved:
        raise AssertionError(
            f"{len(unresolved)} acceptance test ID(s) do not resolve:\n" + "\n".join(unresolved)
        )


# --- wording checks ----------------------------------------------------------


def read_module_docstring(path):
    """The module docstring of the file at `path`, read from its source with
    the module neither imported nor executed."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return ast.get_docstring(tree, clean=False) or ""


def assert_docstring_wording(docstring):
    """FR3 / FR4: neither stale string is present. Whitespace is collapsed
    first so a line break inside a phrase cannot hide it."""
    text = " ".join(docstring.split())
    if not text:
        raise AssertionError("the module docstring read is empty")
    for marker in ("AC-2", "AC-4"):
        if marker not in text:
            raise AssertionError(f"the module docstring read does not mention {marker}")
    for stale in OLD_DOCSTRING_STRINGS:
        if stale in text:
            raise AssertionError(f"the module docstring still contains {stale!r}")


_RED_REASON_RE = re.compile(r"^    red_reason:\s*(.*)$")
_DOUBLE_QUOTED_RE = re.compile(r'^"([^"\\]*)"$')


def read_ac_red_reason(path, ac_key):
    """The value of `ac_key`'s red_reason in the tests.yaml at `path`. The AC
    block must carry exactly one red_reason line, in the single-line
    double-quoted form; anything else fails (AssertionError) naming the file."""
    bodies = dict(read_ac_blocks(path))
    if ac_key not in bodies:
        raise AssertionError(f"{path}: no {ac_key} block")
    matches = [m for m in map(_RED_REASON_RE.match, bodies[ac_key]) if m is not None]
    if len(matches) != 1:
        raise AssertionError(
            f"{path}: {ac_key} must carry exactly one red_reason line, found {len(matches)}"
        )
    quoted = _DOUBLE_QUOTED_RE.match(matches[0].group(1).strip())
    if quoted is None:
        raise AssertionError(
            f"{path}: {ac_key} red_reason is not a single-line double-quoted scalar"
        )
    return quoted.group(1)


def assert_ac2_red_reason(path):
    """FR2: AC-2's red_reason in the tests.yaml at `path` describes the real
    assertions, and AC-2 keeps `red_confirmed: true`."""
    value = read_ac_red_reason(path, "AC-2")
    if not value.strip():
        raise AssertionError(f"{path}: AC-2 red_reason is empty")
    if not value.startswith(OBSERVED_RED_CLAUSE):
        raise AssertionError(f"{path}: AC-2 red_reason does not begin with the observed-red clause")
    if value.count("AssertionError") != 1:
        raise AssertionError(
            f"{path}: AC-2 red_reason must contain 'AssertionError' exactly once, "
            f"found {value.count('AssertionError')}"
        )
    missing = [name for name in AC2_TEST_METHODS if name not in value]
    if missing:
        raise AssertionError(f"{path}: AC-2 red_reason does not name {missing}")
    for forbidden in (OLD_RED_REASON_PHRASE, STALE_METHOD_NAME):
        if forbidden in value:
            raise AssertionError(f"{path}: AC-2 red_reason still contains {forbidden!r}")
    body = dict(read_ac_blocks(path))["AC-2"]
    if not any(line.rstrip() == "    red_confirmed: true" for line in body):
        raise AssertionError(f"{path}: AC-2 no longer carries `red_confirmed: true`")


# --- tests -------------------------------------------------------------------


def _write(directory, text):
    path = Path(directory) / "record.tests.yaml"
    path.write_text(text, encoding="utf-8")
    return path


class TestTargetEnumeration(unittest.TestCase):
    """AC-4 (FR6): the target list is an explicit enumeration of one file."""

    def test_target_list_holds_only_the_task0002_record(self):
        self.assertEqual(TARGET_RECORDS, (TARGET_RECORD,))
        self.assertEqual(
            TARGET_RECORD.relative_to(REPO_ROOT).as_posix(),
            "test-docs/exit4-tip-argument/task0002.tests.yaml",
        )

    def test_target_record_exists(self):
        self.assertTrue(TARGET_RECORD.is_file(), f"{TARGET_RECORD} is missing")


class TestIdExtraction(unittest.TestCase):
    """The extractor reads block lists, and refuses shapes it cannot read
    instead of yielding zero IDs."""

    def test_block_list_and_inline_empty_list_are_read_in_file_order(self):
        text = (
            "task_id: t\n"
            "acceptance_tests:\n"
            "  AC-1:\n"
            "    tests:\n"
            "      - pkg.mod.TestA.test_one\n"
            "      - pkg.mod.TestA.test_two\n"
            "    red_confirmed: true\n"
            "  AC-2:\n"
            "    tests: []\n"
            "    red_reason: \"none\"\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            ids = extract_acceptance_test_ids(_write(directory, text))
        self.assertEqual(
            ids, {"AC-1": ["pkg.mod.TestA.test_one", "pkg.mod.TestA.test_two"], "AC-2": []}
        )

    def test_flow_list_with_entries_fails_naming_file_and_ac(self):
        text = "acceptance_tests:\n  AC-7:\n    tests: [pkg.mod.TestA.test_one, pkg.mod.TestA.test_two]\n"
        self._assert_rejected(text, "AC-7")

    def test_nested_mapping_fails_naming_file_and_ac(self):
        text = "acceptance_tests:\n  AC-8:\n    tests:\n      first: pkg.mod.TestA.test_one\n"
        self._assert_rejected(text, "AC-8")

    def test_missing_tests_key_fails_naming_file_and_ac(self):
        text = "acceptance_tests:\n  AC-9:\n    red_confirmed: true\n"
        self._assert_rejected(text, "AC-9")

    def test_empty_block_list_fails_naming_file_and_ac(self):
        text = "acceptance_tests:\n  AC-10:\n    tests:\n    red_confirmed: true\n"
        self._assert_rejected(text, "AC-10")

    def _assert_rejected(self, text, ac_key):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, text)
            with self.assertRaises(AssertionError) as caught:
                extract_acceptance_test_ids(path)
        self.assertIn(str(path), str(caught.exception))
        self.assertIn(ac_key, str(caught.exception))


class TestTargetRecordIds(unittest.TestCase):
    """AC-1 (FR1) and AC-6 (FR7): what the target record lists, plus the
    non-vacuity guards on the extracted list."""

    @classmethod
    def setUpClass(cls):
        cls.by_ac = extract_acceptance_test_ids(TARGET_RECORD)
        cls.ids = flatten_ids(cls.by_ac)

    def test_extracted_ids_are_not_empty(self):
        self.assertTrue(self.ids)

    def test_extracted_ids_contain_the_replacement_id(self):
        self.assertIn(REPLACEMENT_ID, self.ids)

    def test_per_ac_counts_match_the_record(self):
        counts = {ac_key: len(ids) for ac_key, ids in self.by_ac.items()}
        self.assertEqual(counts, EXPECTED_ID_COUNTS)
        self.assertEqual(len(self.ids), 11)

    def test_ac2_holds_four_ids_and_the_fourth_is_the_replacement(self):
        ac2 = self.by_ac["AC-2"]
        self.assertEqual(len(ac2), 4)
        self.assertEqual(ac2[3], REPLACEMENT_ID)

    def test_stale_id_appears_nowhere_in_the_record(self):
        text = TARGET_RECORD.read_text(encoding="utf-8")
        self.assertNotIn(STALE_ID, text)
        self.assertNotIn(STALE_METHOD_NAME, text)


class TestRepoRootImportable(unittest.TestCase):
    def test_root_is_importable_inside_and_path_is_restored_afterwards(self):
        before = list(sys.path)
        with repo_root_importable():
            self.assertIn(str(REPO_ROOT), sys.path)
        self.assertEqual(sys.path, before)

    def test_path_is_restored_when_the_block_raises(self):
        before = list(sys.path)
        with self.assertRaises(RuntimeError):
            with repo_root_importable():
                raise RuntimeError("boom")
        self.assertEqual(sys.path, before)


class TestResolutionJudge(unittest.TestCase):
    """AC-6 (FR7): the judge accepts module, class and method IDs, and rejects
    the stale ID -- with a guard showing the rejection is not an import
    failure."""

    def test_module_id_resolves(self):
        self.assertTrue(resolve_id(MODULE_ID).resolved)

    def test_class_id_resolves(self):
        self.assertTrue(resolve_id(CLASS_ID).resolved)

    def test_method_id_resolves(self):
        self.assertTrue(resolve_id(REPLACEMENT_ID).resolved)

    def test_stale_id_is_reported_unresolved(self):
        """Negative proof."""
        result = resolve_id(STALE_ID)
        self.assertFalse(result.resolved)
        self.assertIn("test_em_review_entry_has_no_version_key", result.reason)

    def test_stale_ids_module_part_and_class_part_both_resolve(self):
        """Guard on the negative proof: the stale ID fails on the missing
        method, not on a broken import."""
        class_part = STALE_ID.rsplit(".", 1)[0]
        module_part = class_part.rsplit(".", 1)[0]
        self.assertEqual(class_part, CLASS_ID)
        self.assertEqual(module_part, MODULE_ID)
        self.assertTrue(resolve_id(module_part).resolved)
        self.assertTrue(resolve_id(class_part).resolved)

    def test_loader_gate_rejects_the_stale_id_that_the_loader_does_not_raise_for(self):
        """The loader reports a missing attribute through `loader.errors` and a
        failure placeholder rather than an exception; the gate must still
        reject it."""
        with repo_root_importable():
            self.assertIsNotNone(_loader_failure(STALE_ID))
            self.assertIsNone(_loader_failure(REPLACEMENT_ID))

    def test_unresolvable_shapes_are_rejected(self):
        cases = {
            "missing module": "tests.no_such_module_for_resolution.TestX.test_y",
            "missing class": MODULE_ID + ".TestNoSuchClass.test_y",
            "attribute that is not a test-case class": MODULE_ID + ".Path",
            "function that is not a test-case class": MODULE_ID + "._load_json",
            "method only inherited from TestCase": CLASS_ID + ".assertEqual",
            "path below a method": REPLACEMENT_ID + ".extra",
            "empty ID": "",
            "malformed ID": "tests..broken",
        }
        for label, dotted in cases.items():
            with self.subTest(label):
                self.assertFalse(resolve_id(dotted).resolved)


class TestAggregateCheck(unittest.TestCase):
    """AC-5 (FR5): the failure message lists every unresolved ID."""

    def test_message_lists_both_unresolvable_ids_and_not_the_resolvable_one(self):
        unresolvable_a = CLASS_ID + ".test_no_such_method_alpha"
        unresolvable_b = CLASS_ID + ".test_no_such_method_beta"
        resolvable = CLASS_ID + ".test_em_review_entry_source_unchanged"
        with self.assertRaises(AssertionError) as caught:
            assert_ids_resolve([unresolvable_a, resolvable, unresolvable_b])
        message = str(caught.exception)
        self.assertIn(unresolvable_a, message)
        self.assertIn(unresolvable_b, message)
        self.assertNotIn(resolvable, message)

    def test_passes_when_every_id_resolves(self):
        assert_ids_resolve([MODULE_ID, CLASS_ID, REPLACEMENT_ID])


class TestRecordedIdsResolve(unittest.TestCase):
    """AC-4 (FR5, FR6): every ID recorded in each target record resolves."""

    def test_every_id_in_every_target_record_resolves(self):
        for record in TARGET_RECORDS:
            with self.subTest(record=record.name):
                ids = flatten_ids(extract_acceptance_test_ids(record))
                self.assertTrue(ids, f"{record} yielded no IDs")
                assert_ids_resolve(ids)


class TestVersionBumpDocstringWording(unittest.TestCase):
    """AC-3 (FR3, FR4): the module docstring no longer carries the stale
    wording."""

    def test_docstring_carries_neither_stale_string(self):
        assert_docstring_wording(read_module_docstring(VERSION_BUMP_MODULE_PATH))

    def test_check_rejects_each_stale_string(self):
        for stale in OLD_DOCSTRING_STRINGS:
            with self.subTest(stale=stale):
                with self.assertRaises(AssertionError):
                    assert_docstring_wording(f"AC-2 and AC-4 ... {stale} ...")

    def test_check_sees_a_stale_string_split_across_lines(self):
        with self.assertRaises(AssertionError):
            assert_docstring_wording("AC-2 AC-4 carries no\n`version` key")

    def test_check_rejects_an_empty_docstring(self):
        with self.assertRaises(AssertionError):
            assert_docstring_wording("")

    def test_check_rejects_a_docstring_that_does_not_mention_ac2_and_ac4(self):
        for text in ("mentions AC-2 only", "mentions AC-4 only"):
            with self.subTest(text=text):
                with self.assertRaises(AssertionError):
                    assert_docstring_wording(text)

    def test_check_accepts_clean_wording(self):
        assert_docstring_wording("AC-2 and AC-4 describe the real assertions")


class TestAc2RedReasonWording(unittest.TestCase):
    """AC-2 (FR2): AC-2's red_reason describes the assertions that exist."""

    VALID_VALUE = (
        OBSERVED_RED_CLAUSE
        + f"; {AC2_EQUALITY_TEST} was green at the baseline, so {AC2_PAST_BASELINE_TEST} "
        + f"carried the observed red; {AC2_EM_REVIEW_SOURCE_TEST} and "
        + f"{AC2_EM_REVIEW_VERSION_TEST} are retention guards"
    )

    def test_target_record_ac2_red_reason_matches_the_real_assertions(self):
        assert_ac2_red_reason(TARGET_RECORD)

    def test_check_accepts_a_well_formed_value(self):
        self._assert_accepted(self.VALID_VALUE)

    def test_check_rejects_a_missing_red_reason(self):
        self._assert_rejected(None)

    def test_check_rejects_an_empty_red_reason(self):
        self._assert_rejected("")

    def test_check_rejects_the_pre_fix_value(self):
        old = (
            OBSERVED_RED_CLAUSE
            + "; the em-review retention checks were already green pre-bump since "
            + OLD_RED_REASON_PHRASE
        )
        self._assert_rejected(old)

    def test_check_rejects_a_second_assertion_error(self):
        self._assert_rejected(self.VALID_VALUE + "; AssertionError: forged")

    def test_check_rejects_a_value_that_does_not_begin_with_the_observed_clause(self):
        self._assert_rejected("preamble " + self.VALID_VALUE)

    def test_check_rejects_a_value_missing_an_ac2_method_name(self):
        self._assert_rejected(self.VALID_VALUE.replace(AC2_EQUALITY_TEST, "the equality test"))

    def test_check_rejects_the_stale_method_name(self):
        self._assert_rejected(self.VALID_VALUE + "; test_em_review_entry_" + STALE_METHOD_NAME)

    def test_check_rejects_a_dropped_red_confirmed(self):
        self._assert_rejected(self.VALID_VALUE, red_confirmed="false")

    def test_check_rejects_two_red_reason_lines(self):
        text = self._record(self.VALID_VALUE) + '    red_reason: "second"\n'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(AssertionError):
                assert_ac2_red_reason(_write(directory, text))

    def test_check_rejects_a_value_that_is_not_double_quoted(self):
        text = self._record(self.VALID_VALUE).replace('"' + self.VALID_VALUE + '"', self.VALID_VALUE)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(AssertionError):
                assert_ac2_red_reason(_write(directory, text))

    def _record(self, value, red_confirmed="true"):
        lines = [
            "task_id: t",
            "acceptance_tests:",
            "  AC-2:",
            "    tests:",
            f"      - {REPLACEMENT_ID}",
            f"    red_confirmed: {red_confirmed}",
        ]
        if value is not None:
            lines.append(f'    red_reason: "{value}"')
        return "\n".join(lines) + "\n"

    def _assert_accepted(self, value):
        with tempfile.TemporaryDirectory() as directory:
            assert_ac2_red_reason(_write(directory, self._record(value)))

    def _assert_rejected(self, value, red_confirmed="true"):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, self._record(value, red_confirmed))
            with self.assertRaises(AssertionError) as caught:
                assert_ac2_red_reason(path)
        self.assertIn(str(path), str(caught.exception))


class TestModuleImports(unittest.TestCase):
    """AC-7 (NFR1): this module imports only the standard library; no YAML
    library, no other test module."""

    def test_every_import_is_a_standard_library_module(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                imported.add(node.module.split(".")[0])
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())


if __name__ == "__main__":
    unittest.main()
