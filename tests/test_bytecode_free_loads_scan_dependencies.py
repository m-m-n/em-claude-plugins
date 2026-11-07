"""Probe checks for the bytecode-free in-process loads of scan-dependencies.py
(scripts-test-bytecode-suppression task0001; FR1, FR3, NFR1, NFR2, NFR3).

Twenty-one test modules in `tests/` load `em-workflow/scripts/scan-dependencies.py`
into the test process by file path. Each of their loaders must turn bytecode
writing off for the whole execution of the loaded module's body and put the
caller's `sys.dont_write_bytecode` back on every exit, a raising body included
(IMPLEMENTATION.md C1). This module drives each of those loaders against a
probe module in a test-owned temporary directory (the loader's path constant
is replaced for one call only), so a broken loader can never write under
`em-workflow/`.

Every probe check makes the same observations per site, each for the starting
values False and True (IMPLEMENTATION.md C3):

- O1 (AC-1): a probe whose body records the flag sees True.
- O2 (AC-2): after a normal return the flag equals the starting value.
- O3 (AC-3): a probe whose body raises makes the loader raise that same error,
  the error text shows the flag was True inside the body, and afterwards the
  flag equals the starting value.
- O4 (AC-4): the probe's own directory holds no `__pycache__` afterwards, the
  recursive listing of `em-workflow/scripts/` equals the one taken before the
  targets were loaded, the site table has exactly 21 rows, and a missing
  loader or path constant is reported.

The target test modules are loaded lazily, once per test class, by file path
under private names, with the flag forced True while a target's body runs and
the previous value restored afterwards (IMPLEMENTATION.md C4). Importing this
module loads nothing. Every test sets the starting value of the flag itself:
in a whole run the inherited value is already True, and a test that relied on
it would pass against a loader that never restores the flag.

This module imports the standard library only and no other test module by name.
"""

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
SCRIPTS_DIR = REPO_ROOT / "em-workflow" / "scripts"

# (test module file name, loader name, path constant name). Every loader reads
# its path constant when it runs and is called with no arguments.
SITES = (
    ("test_sca_file_tasks_unexpected_exceptions.py", "load_script_module", "SCRIPT_PATH"),
    ("test_sca_listing_undecodable_output.py", "load_script_module", "SCRIPT_PATH"),
    ("test_sca_pip_lockfile_audit.py", "_load_script", "SCRIPT_PATH"),
    ("test_scan_dependencies_cargo_directness.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_absolute_executable_resolution.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_file_tasks_oserror.py", "load_script_module", "SCRIPT_PATH"),
    ("test_scan_dependencies_pyproject_directness.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_child_env_path_filtering.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_go_govulncheck_real_output.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_scanner_project_config_isolation.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_scan_job_grouping.py", "_load_module", "SCRIPT_PATH"),
    ("test_sca_task_filing.py", "load_script_module", "SCRIPT_PATH"),
    ("test_sca_run_scan_plan_units.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_scan_unchanged_surfaces.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_per_project_scan_binding.py", "_load_script", "SCRIPT_PATH"),
    ("test_reproduction_output_contract.py", "_load_scanner", "SCAN_SCRIPT_PATH"),
    ("test_sca_scan_execution.py", "_load_module", "SCRIPT_PATH"),
    ("test_scan_dependencies_pip_directness.py", "_load_module", "SCRIPT_PATH"),
    ("test_sca_scan_invocation.py", "_load_module", "SCRIPT_PATH"),
    ("test_sca_finding_title_roundtrip.py", "_load_script", "SCRIPT_PATH"),
    ("test_sca_scan_normalization.py", "_load_module", "SCRIPT_PATH"),
)

EXPECTED_SITE_COUNT = 21

PROBE_RECORDS_FLAG = "import sys\nFLAG_SEEN_BY_BODY = sys.dont_write_bytecode\n"
PROBE_RAISES = (
    "import sys\n"
    "raise RuntimeError('probe body raised; flag=%r' % sys.dont_write_bytecode)\n"
)
PROBE_RAISED_MESSAGE = "probe body raised; flag=True"

STARTING_VALUES = (False, True)


def scripts_listing():
    """Recursive, sorted listing (directories and files) of
    `em-workflow/scripts/`."""
    return sorted(
        os.path.join(directory, name)
        for directory, dirs, files in os.walk(SCRIPTS_DIR)
        for name in dirs + files
    )


def load_target(index, file_name):
    """One existing test module, loaded by file path under a private name that
    no discover run and no `tests.`-prefixed run uses. The flag is forced True
    while the target's body runs (so its module-level load of the real script
    writes nothing even while that target's loader is still unsuppressed, and a
    target that sets the flag at module level does not leak it) and the
    previous value is put back on every exit."""
    private_name = "_bytecode_free_loads_scan_dependencies_target_%02d" % index
    spec = importlib.util.spec_from_file_location(private_name, TESTS_DIR / file_name)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def missing_attributes(sites, targets):
    """`"<file>: <name>"` for every loader or path constant that is absent from
    its loaded target, or a loader that is not callable."""
    missing = []
    for (file_name, loader_name, path_name), target in zip(sites, targets):
        if not callable(getattr(target, loader_name, None)):
            missing.append("%s: loader %s" % (file_name, loader_name))
        if not hasattr(target, path_name):
            missing.append("%s: path constant %s" % (file_name, path_name))
    return missing


class TestScanDependenciesLoadersWriteNoBytecode(unittest.TestCase):
    """AC-1 to AC-4: each of the 21 loaders turns bytecode writing on only for
    the load and puts the caller's value back, and the load leaves no bytecode
    next to the probe."""

    @classmethod
    def setUpClass(cls):
        cls.listing_before = scripts_listing()
        cls.targets = [
            load_target(index, file_name)
            for index, (file_name, _, _) in enumerate(SITES)
        ]

    @classmethod
    def tearDownClass(cls):
        after = scripts_listing()
        if after != cls.listing_before:
            raise AssertionError(
                "em-workflow/scripts/ changed while the probe class ran: %s"
                % sorted(set(after) ^ set(cls.listing_before))
            )

    def setUp(self):
        # Registered first, so the value the test found comes back whether the
        # test passes, fails or errors.
        self.addCleanup(setattr, sys, "dont_write_bytecode", sys.dont_write_bytecode)

    def drive(self, index, source, starting):
        """Call the loader of row `index` once, with its path constant aimed at
        a fresh probe in a fresh test-owned directory and
        `sys.dont_write_bytecode` set to `starting` just before the call.

        Returns `(module, error, flag_after, probe_dir)`; `module` is None when
        the loader raised, `error` is None when it returned."""
        _, loader_name, path_name = SITES[index]
        target = self.targets[index]
        loader = getattr(target, loader_name)
        getattr(target, path_name)  # an absent constant fails here, naming itself
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        probe_path = Path(tmp.name) / "probe_scan_dependencies.py"
        probe_path.write_text(source, encoding="utf-8")
        module = error = None
        sys.dont_write_bytecode = starting
        with mock.patch.object(target, path_name, probe_path):
            try:
                module = loader()
            except Exception as exc:  # the caller of drive() judges it
                error = exc
        flag_after = sys.dont_write_bytecode
        return module, error, flag_after, tmp.name

    @staticmethod
    def rows_and_starts():
        """`(index, row name, starting value)` for every row and both starting
        values; each test judges one of them per subtest, so a failure names
        the row."""
        for index, (file_name, _, _) in enumerate(SITES):
            for starting in STARTING_VALUES:
                yield index, file_name, starting

    def test_o1_ac1_flag_is_true_while_the_module_body_runs(self):
        for index, row, starting in self.rows_and_starts():
            with self.subTest(row=row, starting=starting):
                module, error, _, _ = self.drive(index, PROBE_RECORDS_FLAG, starting)
                self.assertIsNone(error)
                self.assertIs(module.FLAG_SEEN_BY_BODY, True)

    def test_o2_ac2_flag_holds_the_starting_value_after_a_normal_return(self):
        for index, row, starting in self.rows_and_starts():
            with self.subTest(row=row, starting=starting):
                _, error, flag_after, _ = self.drive(index, PROBE_RECORDS_FLAG, starting)
                self.assertIsNone(error)
                self.assertIs(flag_after, starting)

    def test_o3_ac3_a_raising_body_reaches_the_caller_with_the_flag_true(self):
        for index, row, starting in self.rows_and_starts():
            with self.subTest(row=row, starting=starting):
                module, error, _, _ = self.drive(index, PROBE_RAISES, starting)
                self.assertIsNone(module)
                self.assertIs(type(error), RuntimeError)
                self.assertEqual(str(error), PROBE_RAISED_MESSAGE)

    def test_o3_ac3_flag_holds_the_starting_value_after_the_body_raises(self):
        for index, row, starting in self.rows_and_starts():
            with self.subTest(row=row, starting=starting):
                _, error, flag_after, _ = self.drive(index, PROBE_RAISES, starting)
                self.assertIsNotNone(error)
                self.assertIs(flag_after, starting)

    def test_o4_ac4_the_probe_directory_holds_no_pycache_after_either_probe(self):
        for index, row, starting in self.rows_and_starts():
            for label, source in (("records", PROBE_RECORDS_FLAG), ("raises", PROBE_RAISES)):
                with self.subTest(row=row, starting=starting, probe=label):
                    _, _, _, probe_dir = self.drive(index, source, starting)
                    self.assertNotIn("__pycache__", os.listdir(probe_dir))

    def test_o4_ac4_the_scripts_listing_is_unchanged_since_before_the_loads(self):
        self.assertEqual(scripts_listing(), self.listing_before)

    def test_o4_ac4_the_site_table_has_exactly_the_planned_rows(self):
        self.assertEqual(len(SITES), EXPECTED_SITE_COUNT)
        self.assertEqual(len({file_name for file_name, _, _ in SITES}), EXPECTED_SITE_COUNT)
        for file_name, loader_name, path_name in SITES:
            with self.subTest(row=file_name):
                self.assertTrue((TESTS_DIR / file_name).is_file())
                self.assertTrue(loader_name)
                self.assertTrue(path_name)

    def test_o4_ac4_every_loader_and_path_constant_exists_on_its_loaded_target(self):
        self.assertEqual(len(self.targets), len(SITES))
        self.assertEqual(missing_attributes(SITES, self.targets), [])


class TestMissingAttributesAreReported(unittest.TestCase):
    """AC-4: a loader or a path constant that is absent from a loaded target
    makes the probe check fail (it is named, not skipped)."""

    SITE = ("test_demo.py", "_load_script", "SCRIPT_PATH")

    def test_a_complete_target_reports_nothing(self):
        target = types.SimpleNamespace(_load_script=lambda: None, SCRIPT_PATH="x")
        self.assertEqual(missing_attributes([self.SITE], [target]), [])

    def test_a_missing_loader_is_named(self):
        target = types.SimpleNamespace(SCRIPT_PATH="x")
        self.assertEqual(
            missing_attributes([self.SITE], [target]),
            ["test_demo.py: loader _load_script"],
        )

    def test_a_loader_that_is_not_callable_is_named(self):
        target = types.SimpleNamespace(_load_script="not callable", SCRIPT_PATH="x")
        self.assertEqual(
            missing_attributes([self.SITE], [target]),
            ["test_demo.py: loader _load_script"],
        )

    def test_a_missing_path_constant_is_named(self):
        target = types.SimpleNamespace(_load_script=lambda: None)
        self.assertEqual(
            missing_attributes([self.SITE], [target]),
            ["test_demo.py: path constant SCRIPT_PATH"],
        )


if __name__ == "__main__":
    unittest.main()
