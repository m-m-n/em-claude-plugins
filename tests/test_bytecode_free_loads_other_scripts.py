"""Probe checks for the in-process loads of the remaining em-workflow scripts
(scripts-test-bytecode-suppression task0003; FR1, FR3, TS-2).

Sixteen existing test modules load a script under `em-workflow/scripts/` into
the test process by file path (the loaded script is never `scan-dependencies.py`
and, apart from `tests/test_self_write_digest.py`, never
`validate-worker-output.py`). Each of their loaders must turn bytecode writing
off for the execution of the loaded module's body only and put the caller's
value of `sys.dont_write_bytecode` back on every exit.

The site table below names, for each of the 17 load sites, the test module, its
loader, and what a probe check replaces for one call so the loader runs a probe
module in a test-owned temporary directory instead of the real script:

  - a module-level path constant the loader reads when it runs (plus, for a
    memoizing loader, its module-level cache, set to empty for that call so the
    loader really loads); or
  - for the one loader that takes it, a path argument.

Row 17 (`tests/test_codex_hook_tty_reaper.py`) already has the suppression form
and its module is not edited; it is driven here as a reference-only row.

Each load site is observed for the starting values False and True:

  O1  a probe whose body records the flag sees True;
  O2  after a normal return the flag equals the starting value;
  O3  a probe whose body raises makes the loader raise that same error, the
      error text shows the flag was True inside the body, and afterwards the
      flag equals the starting value;
  O4  the probe's own directory holds no `__pycache__`, `em-workflow/scripts/`
      is unchanged, and a memoizing loader's cache holds, after the probe call,
      the value it held before.

Every test sets the starting value itself right before the call: in a whole run
the inherited value is already True (`tests/test_merge_ci_wait.py` sets it at
module level and never restores it), and a test that inherited it would pass
against a loader that never restored the flag. The value found at test start is
put back on every exit of the test by a cleanup registered before anything
else. Probes live in a directory owned by the test; nothing here aims a loader
at a path under `em-workflow/`.

Nothing is loaded when this module is imported (the record check imports test
modules without running them). The target test modules are loaded once per test
class, by file path, under private names, with the flag forced True while their
bodies run and the previous value put back afterwards (so a target's
module-level load of a real script writes nothing even while that target's
loader is still unsuppressed, and a target that sets the flag at module level
does not leak it).
"""

import collections
import contextlib
import importlib.util
import inspect
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "em-workflow" / "scripts"

EXPECTED_ROW_COUNT = 17

CONSTANT = "path constant"
ARGUMENT = "path argument"

Site = collections.namedtuple(
    "Site", "row module script loader redirect path_attr cache_attr"
)

# The loaded script, the loader, and what a probe check replaces for one call.
# "cache" is the module-level memo a memoizing loader fills on first use.
SITES = (
    Site(1, "test_tier_evaluator_contract.py", "decide-tier.py",
         "load_decide_tier_module", CONSTANT, "DECIDE_TIER_SCRIPT", None),
    Site(2, "test_tier_rules_buckets_codex_facts.py", "decide-tier.py",
         "load_decide_tier_module", CONSTANT, "DECIDE_TIER_SCRIPT", None),
    Site(3, "test_decide_tier_final_score.py", "decide-tier.py",
         "load_decide_tier_module", CONSTANT, "DECIDE_TIER_SCRIPT", None),
    Site(4, "test_tier_rules.py", "decide-tier.py",
         "load_decide_tier_module", CONSTANT, "DECIDE_TIER_SCRIPT", None),
    Site(5, "test_check_plugin_invariants.py", "check-plugin-invariants.py",
         "load_script_module", CONSTANT, "SCRIPT_PATH", None),
    Site(6, "test_self_write_digest_wiring.py", "check-plugin-invariants.py",
         "_load_checker", CONSTANT, "CHECKER_PATH", None),
    Site(7, "test_self_write_digest_docs.py", "check-plugin-invariants.py",
         "_load_checker", CONSTANT, "CHECKER_PATH", None),
    Site(8, "test_worker_digest_results.py", "check-plugin-invariants.py",
         "load_checker_module", CONSTANT, "CHECKER_PATH", None),
    Site(9, "test_recover_orphaned_task.py", "recover-orphaned-task.py",
         "_load_module", CONSTANT, "SCRIPT_PATH", None),
    Site(10, "test_stale_launched_recovery_chain.py", "recover-orphaned-task.py",
         "_load_module", CONSTANT, "SCRIPT_PATH", None),
    Site(11, "test_journal_append_failed.py", "journal-append-failed.py",
         "load_module", CONSTANT, "SCRIPT_PATH", None),
    Site(12, "test_review_shards.py", "review-shards.py",
         "load_script", CONSTANT, "SCRIPT", None),
    Site(13, "test_review_coverage.py", "review-coverage.py",
         "script_module", CONSTANT, "SCRIPT", "_LOADED"),
    Site(14, "test_self_write_digest.py", "self-write-digest.py",
         "script_module", CONSTANT, "SCRIPT", "_LOADED"),
    Site(15, "test_self_write_digest.py", "validate-worker-output.py",
         "validator_module", CONSTANT, "VALIDATOR", "_VALIDATOR_LOADED"),
    Site(16, "test_merge_ci_wait.py", "merge-ci-wait.py",
         "load_module", CONSTANT, "SCRIPT", None),
    Site(17, "test_codex_hook_tty_reaper.py", "codex-hook-tty-reaper.py",
         "load_hook", ARGUMENT, None, None),
)

PROBE_RECORDS_FLAG = "import sys\nFLAG_SEEN_BY_BODY = sys.dont_write_bytecode\n"
PROBE_RAISES = (
    "import sys\n"
    "raise RuntimeError('probe body raised; flag=%r' % sys.dont_write_bytecode)\n"
)
PROBE_RAISES_MESSAGE = "probe body raised; flag=True"
PROBE_BODIES = (("records", PROBE_RECORDS_FLAG), ("raises", PROBE_RAISES))


def listing(root):
    """Every directory and file under ROOT (recursive), relative to ROOT."""
    return sorted(
        os.path.relpath(os.path.join(directory, name), root)
        for directory, dirs, files in os.walk(root)
        for name in dirs + files
    )


def pycache_dirs(root):
    """Every `__pycache__` directory anywhere under ROOT."""
    return sorted(
        os.path.join(directory, name)
        for directory, dirs, _files in os.walk(root)
        for name in dirs
        if name == "__pycache__"
    )


def load_target(module_file):
    """tests/MODULE_FILE as a module of its own: by file path, under a private
    name no discover run uses, with bytecode writing forced off while its body
    runs and the previous value put back afterwards."""
    path = TESTS_DIR / module_file
    spec = importlib.util.spec_from_file_location(
        "_bytecode_free_target_" + path.stem, path
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def missing_attributes(target, site):
    """Names the site table promises that TARGET does not have."""
    missing = []
    loader = getattr(target, site.loader, None)
    if not callable(loader):
        missing.append(site.loader)
    if site.redirect == CONSTANT:
        if not hasattr(target, site.path_attr):
            missing.append(site.path_attr)
    elif callable(loader):
        if "path" not in inspect.signature(loader).parameters:
            missing.append("path (argument of %s)" % site.loader)
    if site.cache_attr is not None and not hasattr(target, site.cache_attr):
        missing.append(site.cache_attr)
    return missing


@contextlib.contextmanager
def redirected(target, site, probe_path):
    """Aim SITE's loader at PROBE_PATH for the duration of the block only.

    Yields the arguments to call the loader with. A path constant is replaced
    by a value of the type it had (a string stays a plain string, a path stays
    a path); a memo cache is set to empty so the loader really loads. Whatever
    was replaced is put back on every exit."""
    if site.redirect == ARGUMENT:
        yield (probe_path,)
        return
    saved = {site.path_attr: getattr(target, site.path_attr)}
    if site.cache_attr is not None:
        saved[site.cache_attr] = getattr(target, site.cache_attr)
    try:
        setattr(target, site.path_attr, type(saved[site.path_attr])(probe_path))
        if site.cache_attr is not None:
            setattr(target, site.cache_attr, None)
        yield ()
    finally:
        for name, value in saved.items():
            setattr(target, name, value)


class _LoadsTargets:
    """Mixin: loads every target test module once for the class and checks that
    `em-workflow/scripts/` is exactly as it was before the targets were loaded
    when the class's tests are done."""

    targets = None
    scripts_listing = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scripts_listing = listing(SCRIPTS_DIR)
        cls.targets = {}
        for site in SITES:
            if site.module not in cls.targets:
                cls.targets[site.module] = load_target(site.module)

    @classmethod
    def tearDownClass(cls):
        try:
            after = listing(SCRIPTS_DIR)
            if after != cls.scripts_listing:
                added = sorted(set(after) - set(cls.scripts_listing))
                removed = sorted(set(cls.scripts_listing) - set(after))
                raise AssertionError(
                    "em-workflow/scripts/ changed while the %s tests ran: "
                    "added %r, removed %r" % (cls.__name__, added, removed)
                )
        finally:
            super().tearDownClass()


class TestLoaderObservations(_LoadsTargets, unittest.TestCase):
    """AC-1 to AC-4 (O1 to O4): each of the 17 load sites, started from False
    and from True."""

    def setUp(self):
        # Registered first, so the value the test found comes back whether the
        # test passes, fails or errors.
        self.addCleanup(setattr, sys, "dont_write_bytecode", sys.dont_write_bytecode)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_root = tmp.name

    def probe(self, source):
        """A fresh directory of the test's own holding a probe module."""
        directory = tempfile.mkdtemp(dir=self.tmp_root)
        path = os.path.join(directory, "probe_script.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        return directory, path

    def aimed(self, site, source):
        """(probe directory, call) where call(starting) sets the flag to
        `starting`, then runs the site's loader against the probe with the
        redirect in place for that one call."""
        directory, path = self.probe(source)
        target = self.targets[site.module]
        loader = getattr(target, site.loader)

        def call(starting):
            with redirected(target, site, path) as args:
                sys.dont_write_bytecode = starting
                return loader(*args)

        return directory, call

    def sub(self, site, starting, **extra):
        """A subtest that names the row, so a failure says which load site."""
        return self.subTest(
            row=site.row, module=site.module, loader=site.loader,
            starting=starting, **extra
        )

    def raising(self, call, starting):
        """Run CALL against a raising probe; return the error it raised."""
        with self.assertRaises(RuntimeError) as caught:
            call(starting)
        return caught.exception

    def run_body(self, call, source, starting):
        """Run CALL against a probe made from SOURCE; a raising probe is
        expected to raise."""
        if source is PROBE_RAISES:
            self.raising(call, starting)
        else:
            call(starting)

    def test_ac1_o1_flag_is_true_while_the_module_body_runs(self):
        for site in SITES:
            for starting in (False, True):
                with self.sub(site, starting):
                    _, call = self.aimed(site, PROBE_RECORDS_FLAG)
                    module = call(starting)
                    self.assertIs(module.FLAG_SEEN_BY_BODY, True)

    def test_ac2_o2_flag_holds_the_starting_value_after_a_normal_return(self):
        for site in SITES:
            for starting in (False, True):
                with self.sub(site, starting):
                    _, call = self.aimed(site, PROBE_RECORDS_FLAG)
                    call(starting)
                    self.assertIs(sys.dont_write_bytecode, starting)

    def test_ac3_o3_a_raising_body_reaches_the_caller_with_the_flag_true(self):
        for site in SITES:
            for starting in (False, True):
                with self.sub(site, starting):
                    _, call = self.aimed(site, PROBE_RAISES)
                    error = self.raising(call, starting)
                    self.assertIs(type(error), RuntimeError)
                    self.assertEqual(str(error), PROBE_RAISES_MESSAGE)

    def test_ac3_o3_flag_holds_the_starting_value_after_the_body_raises(self):
        for site in SITES:
            for starting in (False, True):
                with self.sub(site, starting):
                    _, call = self.aimed(site, PROBE_RAISES)
                    self.raising(call, starting)
                    self.assertIs(sys.dont_write_bytecode, starting)

    def test_ac4_o4_probe_directory_holds_no_pycache(self):
        for site in SITES:
            for starting in (False, True):
                for label, source in PROBE_BODIES:
                    with self.sub(site, starting, body=label):
                        directory, call = self.aimed(site, source)
                        self.run_body(call, source, starting)
                        self.assertEqual(pycache_dirs(directory), [])

    def test_ac4_o4_scripts_directory_is_unchanged_by_the_loader_calls(self):
        before = listing(SCRIPTS_DIR)
        self.assertEqual(before, self.scripts_listing)
        for site in SITES:
            for starting in (False, True):
                for label, source in PROBE_BODIES:
                    with self.sub(site, starting, body=label):
                        _, call = self.aimed(site, source)
                        self.run_body(call, source, starting)
        self.assertEqual(listing(SCRIPTS_DIR), before)

    def test_ac4_o4_memoizing_loader_cache_holds_the_prior_value_after_the_call(self):
        memoizing = [site for site in SITES if site.cache_attr is not None]
        self.assertEqual([site.row for site in memoizing], [13, 14, 15])
        for site in memoizing:
            target = self.targets[site.module]
            self.addCleanup(
                setattr, target, site.cache_attr, getattr(target, site.cache_attr)
            )
            for starting in (False, True):
                with self.sub(site, starting):
                    prior = object()
                    setattr(target, site.cache_attr, prior)
                    _, path = self.probe(PROBE_RECORDS_FLAG)
                    with redirected(target, site, path) as args:
                        sys.dont_write_bytecode = starting
                        module = getattr(target, site.loader)(*args)
                        # The loader really loaded: it filled the emptied cache.
                        self.assertIs(getattr(target, site.cache_attr), module)
                    self.assertIs(getattr(target, site.cache_attr), prior)

    def test_ac4_o4_the_redirect_lasts_one_call_only(self):
        for site in SITES:
            if site.redirect != CONSTANT:
                continue
            target = self.targets[site.module]
            names = [site.path_attr] + ([site.cache_attr] if site.cache_attr else [])
            before = {name: getattr(target, name) for name in names}
            for starting in (False, True):
                for label, source in PROBE_BODIES:
                    with self.sub(site, starting, body=label):
                        _, call = self.aimed(site, source)
                        self.run_body(call, source, starting)
                        for name in names:
                            self.assertIs(getattr(target, name), before[name])

    def test_ac4_o4_a_string_path_constant_is_replaced_by_a_plain_string(self):
        site = next(site for site in SITES if site.row == 16)
        target = self.targets[site.module]
        self.assertIs(type(getattr(target, site.path_attr)), str)
        _, path = self.probe(PROBE_RECORDS_FLAG)
        with redirected(target, site, path):
            self.assertIs(type(getattr(target, site.path_attr)), str)
            self.assertEqual(getattr(target, site.path_attr), path)


class TestSiteTable(_LoadsTargets, unittest.TestCase):
    """AC-4: the site table is not silently short or wrong, and a missing
    loader or redirect attribute makes the probe test fail."""

    def test_ac4_the_table_has_exactly_17_rows(self):
        self.assertEqual(len(SITES), EXPECTED_ROW_COUNT)

    def test_ac4_the_rows_are_numbered_1_to_17_in_order(self):
        self.assertEqual([site.row for site in SITES], list(range(1, 18)))

    def test_ac4_every_loader_and_redirect_attribute_exists_on_its_target(self):
        for site in SITES:
            with self.subTest(row=site.row, module=site.module, loader=site.loader):
                self.assertEqual(missing_attributes(self.targets[site.module], site), [])

    def test_ac4_every_path_constant_names_the_script_the_row_claims(self):
        for site in SITES:
            if site.redirect != CONSTANT:
                continue
            with self.subTest(row=site.row, module=site.module):
                value = getattr(self.targets[site.module], site.path_attr)
                self.assertEqual(os.path.basename(value), site.script)
                self.assertEqual(
                    os.path.realpath(os.path.dirname(value)),
                    os.path.realpath(SCRIPTS_DIR),
                )

    def test_ac4_row_17_loader_default_path_is_the_script_the_row_claims(self):
        site = next(site for site in SITES if site.row == 17)
        loader = getattr(self.targets[site.module], site.loader)
        default = inspect.signature(loader).parameters["path"].default
        self.assertEqual(os.path.basename(default), site.script)

    def test_ac4_the_attribute_check_reports_a_missing_loader(self):
        site = SITES[0]
        stand_in = types.SimpleNamespace(**{site.path_attr: "x.py"})
        self.assertEqual(missing_attributes(stand_in, site), [site.loader])

    def test_ac4_the_attribute_check_reports_a_missing_path_constant(self):
        site = SITES[0]
        stand_in = types.SimpleNamespace(**{site.loader: lambda: None})
        self.assertEqual(missing_attributes(stand_in, site), [site.path_attr])

    def test_ac4_the_attribute_check_reports_a_missing_cache(self):
        site = next(site for site in SITES if site.cache_attr is not None)
        stand_in = types.SimpleNamespace(
            **{site.loader: lambda: None, site.path_attr: "x.py"}
        )
        self.assertEqual(missing_attributes(stand_in, site), [site.cache_attr])

    def test_ac4_the_attribute_check_reports_a_missing_path_argument(self):
        site = next(site for site in SITES if site.redirect == ARGUMENT)
        stand_in = types.SimpleNamespace(**{site.loader: lambda: None})
        self.assertEqual(
            missing_attributes(stand_in, site),
            ["path (argument of %s)" % site.loader],
        )

    def test_ac4_the_attribute_check_accepts_a_complete_stand_in(self):
        for site in SITES:
            with self.subTest(row=site.row):
                names = {site.loader: lambda path=None: None}
                if site.path_attr is not None:
                    names[site.path_attr] = "x.py"
                if site.cache_attr is not None:
                    names[site.cache_attr] = None
                self.assertEqual(
                    missing_attributes(types.SimpleNamespace(**names), site), []
                )


if __name__ == "__main__":
    unittest.main()
