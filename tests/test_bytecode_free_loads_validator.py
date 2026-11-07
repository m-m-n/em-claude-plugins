"""Probe checks: every in-process load of `validate-worker-output.py` from a
test module is bytecode-free and puts the caller's flag back.

Feature scripts-test-bytecode-suppression, task0002
(feature-docs/scripts-test-bytecode-suppression/tasks/task0002.md). The sixteen
test modules listed in `SITES` each carry a loader that loads
`em-workflow/scripts/validate-worker-output.py` into the test process by file
path. A loader must turn `sys.dont_write_bytecode` on for the whole execution
of the loaded module's body and put the caller's value back on every exit
(IMPLEMENTATION.md C1).

For every row of the site table, for each starting value (False, True), this
module drives the row's loader against a probe module that lives in a
directory owned by the test, and makes the observations of IMPLEMENTATION.md
C3:

- O1 (AC-1): a probe body that records the flag sees True.
- O2 (AC-2): after a normal return, the flag equals the starting value.
- O3 (AC-3): a probe body that raises makes the loader raise that same error,
  the error text shows the flag was True inside the body, and afterwards the
  flag equals the starting value.
- O4 (AC-4): after the loads, the probe's own directory holds no
  `__pycache__`; the recursive listing of `em-workflow/scripts/` equals the
  listing taken before the target modules were loaded; the table has exactly
  sixteen rows; every named loader and redirect attribute exists on its loaded
  target.

How a loader is aimed at a probe: for one call, the row's redirect on the
loaded target module is replaced -- a module-level path constant the loader
reads when it runs, or (row 16, whose loader builds the path itself from the
repository root) the root constant, with the probe placed at
`em-workflow/scripts/validate-worker-output.py` under a test-owned temporary
root. No probe is placed under, and no loader is aimed at, any path under the
repository's `em-workflow/` directory.

Every test sets the starting value of `sys.dont_write_bytecode` itself: in a
whole run the inherited value is already True (another test module sets it at
module level and never restores it), and a test that inherited it would pass
against a loader that never restored the flag. The value found at test start
is put back on every exit of the test.

Target test modules are loaded lazily (when the tests of a class run, once per
class), by file path, under a private module name, with the flag forced True
while their bodies run and the previous value restored afterwards. Loading
does not run their tests, and importing this module loads nothing.

Standard library only; the process-wide `os.environ` is never touched.
"""

import collections
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "em-workflow" / "scripts"

PRIVATE_NAME_PREFIX = "bytecode_free_loads_validator_target_"
VALIDATOR_RELATIVE = ("em-workflow", "scripts", "validate-worker-output.py")

PATH_REDIRECT = "path"
ROOT_REDIRECT = "root"

Site = collections.namedtuple("Site", "row module loader kind attribute")

# The 16-row site table of the task plan: test module file name, loader name,
# redirect kind and the attribute the redirect replaces for one call.
SITES = (
    Site(1, "test_digest_contract_alignment.py", "_load_validator_module", PATH_REDIRECT, "VALIDATOR"),
    Site(2, "test_requirements_tests_replace.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(3, "test_replanning_producer_alignment.py", "_load_validator_module", PATH_REDIRECT, "VALIDATOR_SCRIPT_PATH"),
    Site(4, "test_final_path_correction.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(5, "test_routeback_record_schema_patch.py", "_load_validator", PATH_REDIRECT, "VALIDATOR_PATH"),
    Site(6, "test_report_name_validation.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(7, "test_validate_worker_output.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(8, "test_spec_change_gate_binding.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(9, "test_tier_rework_path.py", "_load_validator_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(10, "test_replanning_carry_over.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(11, "test_spec_change_replan_authorization.py", "_load_validator_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(12, "test_classification_audit_retention.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(13, "test_tier_task_document_plan.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(14, "test_tier_phase_preconditions.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(15, "test_rework_docs_only_validator_rules.py", "_load_module", PATH_REDIRECT, "SCRIPT_PATH"),
    Site(16, "test_gate_outcome_packet_lifecycle.py", "_load_validator_module", ROOT_REDIRECT, "REPO_ROOT"),
)
EXPECTED_ROW_COUNT = 16

STARTING_VALUES = (False, True)

# Probe bodies. The first records the flag it sees; the second raises with the
# flag value in its message.
RECORD_PROBE = (
    "import sys\n"
    "FLAG_SEEN_IN_BODY = sys.dont_write_bytecode\n"
)
RAISE_PROBE = (
    "import sys\n"
    "raise RuntimeError('probe body ran with dont_write_bytecode=%r'"
    " % (sys.dont_write_bytecode,))\n"
)
RAISE_MESSAGE_FLAG_TRUE = "probe body ran with dont_write_bytecode=True"


def _load_test_module(file_name):
    """Load one test module by file path under a private name.

    The flag is forced True while the module body runs and the previous value
    is put back afterwards, so a module-level load of a real script writes
    nothing even while that module's loader is still broken, and a module that
    sets the flag at module level does not leak it. The module is not put into
    the interpreter's module registry."""
    path = TESTS_DIR / file_name
    spec = importlib.util.spec_from_file_location(
        PRIVATE_NAME_PREFIX + path.stem, path
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _listing(directory):
    """Recursive listing of a directory, as sorted relative path strings."""
    return sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))


def _pycache_dirs(directory):
    """Every `__pycache__` directory under `directory`, relative to it."""
    return sorted(
        str(p.relative_to(directory)) for p in directory.rglob("__pycache__")
    )


Observation = collections.namedtuple(
    "Observation", "result error flag_after pycache_dirs"
)


class TestBytecodeFreeLoadsOfValidator(unittest.TestCase):
    """The sixteen loaders of validate-worker-output.py, driven against probes
    (AC-1, AC-2, AC-3, AC-4 of task0002)."""

    @classmethod
    def setUpClass(cls):
        # The listing is taken before any target is loaded.
        cls.scripts_listing_before = _listing(SCRIPTS_DIR)
        cls.targets = {site.row: _load_test_module(site.module) for site in SITES}

    @classmethod
    def tearDownClass(cls):
        cls._assert_scripts_listing_unchanged()

    @classmethod
    def _assert_scripts_listing_unchanged(cls):
        after = _listing(SCRIPTS_DIR)
        if after != cls.scripts_listing_before:
            added = sorted(set(after) - set(cls.scripts_listing_before))
            removed = sorted(set(cls.scripts_listing_before) - set(after))
            raise AssertionError(
                "the recursive listing of em-workflow/scripts/ changed since "
                "before the targets were loaded: added=%r removed=%r"
                % (added, removed)
            )

    def setUp(self):
        # Registered before anything else: the flag found at test start is put
        # back on every exit of the test (pass, fail or error).
        self.addCleanup(setattr, sys, "dont_write_bytecode", sys.dont_write_bytecode)

    def _drive(self, site, start, probe_source):
        """Aim `site`'s loader at a fresh probe and call it once.

        The probe lives in a fresh directory owned by this test. The starting
        value is set here, immediately before the call; the redirect is
        replaced for this one call only."""
        target = self.targets[site.row]
        loader = getattr(target, site.loader)
        original = getattr(target, site.attribute)
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            if site.kind == ROOT_REDIRECT:
                probe_path = root.joinpath(*VALIDATOR_RELATIVE)
                probe_path.parent.mkdir(parents=True)
                redirect_value = root
            else:
                probe_path = root / "probe_module.py"
                redirect_value = probe_path
            probe_path.write_text(probe_source, encoding="utf-8")

            result = None
            error = None
            setattr(target, site.attribute, redirect_value)
            try:
                sys.dont_write_bytecode = start
                try:
                    result = loader()
                except Exception as exc:  # observed, not handled
                    error = exc
                flag_after = sys.dont_write_bytecode
            finally:
                setattr(target, site.attribute, original)
            return Observation(result, error, flag_after, _pycache_dirs(root))

    @staticmethod
    def _cases():
        """Every (site, starting value) pair, each reported on its own."""
        for site in SITES:
            for start in STARTING_VALUES:
                yield site, start

    # -- the table ----------------------------------------------------------

    def test_ac4_site_table_has_exactly_sixteen_distinct_rows(self):
        self.assertEqual(len(SITES), EXPECTED_ROW_COUNT)
        self.assertEqual([site.row for site in SITES], list(range(1, 17)))
        self.assertEqual(len({site.module for site in SITES}), EXPECTED_ROW_COUNT)

    def test_ac4_every_loader_and_redirect_attribute_exists_on_loaded_target(self):
        for site in SITES:
            with self.subTest(row=site.row, module=site.module):
                target = self.targets[site.row]
                self.assertTrue(
                    callable(getattr(target, site.loader, None)),
                    "loader %s is missing from %s" % (site.loader, site.module),
                )
                self.assertTrue(
                    hasattr(target, site.attribute),
                    "redirect attribute %s is missing from %s"
                    % (site.attribute, site.module),
                )

    # -- O1 / AC-1 ----------------------------------------------------------

    def test_ac1_recording_probe_sees_flag_true(self):
        for site, start in self._cases():
            with self.subTest(row=site.row, module=site.module, start=start):
                observed = self._drive(site, start, RECORD_PROBE)
                self.assertIsNone(observed.error)
                self.assertIs(observed.result.FLAG_SEEN_IN_BODY, True)

    # -- O2 / AC-2 ----------------------------------------------------------

    def test_ac2_flag_equals_starting_value_after_normal_return(self):
        for site, start in self._cases():
            with self.subTest(row=site.row, module=site.module, start=start):
                observed = self._drive(site, start, RECORD_PROBE)
                self.assertIsNone(observed.error)
                self.assertIs(observed.flag_after, start)

    # -- O3 / AC-3 ----------------------------------------------------------

    def test_ac3_raising_probe_error_reaches_caller_with_flag_true_in_body(self):
        for site, start in self._cases():
            with self.subTest(row=site.row, module=site.module, start=start):
                observed = self._drive(site, start, RAISE_PROBE)
                self.assertIsInstance(observed.error, RuntimeError)
                self.assertEqual(str(observed.error), RAISE_MESSAGE_FLAG_TRUE)

    def test_ac3_flag_equals_starting_value_after_raising_probe(self):
        for site, start in self._cases():
            with self.subTest(row=site.row, module=site.module, start=start):
                observed = self._drive(site, start, RAISE_PROBE)
                self.assertIsInstance(observed.error, RuntimeError)
                self.assertIs(observed.flag_after, start)

    # -- O4 / AC-4 ----------------------------------------------------------

    def test_ac4_normal_return_leaves_no_pycache_in_probe_directory(self):
        for site, start in self._cases():
            with self.subTest(row=site.row, module=site.module, start=start):
                observed = self._drive(site, start, RECORD_PROBE)
                self.assertIsNone(observed.error)
                self.assertEqual(observed.pycache_dirs, [])

    def test_ac4_raising_probe_leaves_no_pycache_in_probe_directory(self):
        for site, start in self._cases():
            with self.subTest(row=site.row, module=site.module, start=start):
                observed = self._drive(site, start, RAISE_PROBE)
                self.assertIsInstance(observed.error, RuntimeError)
                self.assertEqual(observed.pycache_dirs, [])

    def test_ac4_scripts_directory_listing_unchanged_after_every_probe_run(self):
        for site, start in self._cases():
            for source in (RECORD_PROBE, RAISE_PROBE):
                self._drive(site, start, source)
        self._assert_scripts_listing_unchanged()


if __name__ == "__main__":
    unittest.main()
