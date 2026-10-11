"""Tests for sca-directness-resolution task0001: the cargo scan unit decides
directness from a tomllib-parsed Cargo.toml by canonical-name matching, counts
the advisories it cannot classify into the cargo undetermined note, and skips
explicitly when tomllib is unavailable.

Covers the task's Acceptance Criteria
(feature-docs/sca-directness-resolution/tasks/task0001.md):

- AC-1 (FR1): a declared `Foo_Bar` matches a reported `foo-bar`; a payload
  entry that carries `is_direct` keeps precedence and is never undetermined.
- AC-2 (FR2): `[dependencies]`, `[dev-dependencies]`, `[build-dependencies]`,
  the sub-table form and `target.<cfg>` tables declare direct crates.
- AC-3 (FR2): `package = '<name>'` renames and `workspace = true` entries
  renamed in `[workspace.dependencies]`.
- AC-4 (FR5, TM-5): a `[workspace]` with members leaves the set incomplete:
  an undeclared advisory is no finding, `skipped` stays false and the summary
  ends with the cargo undetermined note; a complete manifest stays transitive.
- AC-5 (FR5, NFR3, TM-4): invalid TOML, an unreadable manifest and unexpected
  shapes return normally with the advisory counted as undetermined.
- AC-6 (FR5, NFR4, TM-6): the counting edges, the plural text and the position
  and wording of the note.
- AC-7 (FR6, NFR4, TM-6): tomllib unavailable -> `cargo_toml_parser_unavailable`
  and cargo-audit is never launched.
- AC-8 (NFR1, NFR5): the standard-library-only import list; the full suite is
  run by the implementer, not from in here.

Per the task's Test Notes: no real scanner runs. Each tool is a recording
stand-in executable on a PATH restricted to its own directory, and every
fixture project lives in a temporary directory created by the test. This
module imports the standard library only.
"""

import ast
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_script(name="scan_dependencies_cargo_directness"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

CARGO_NOTE_ONE = " 1 cargo advisory with undetermined directness (cargo_directness_undetermined)."
CARGO_NOTE_TWO = " 2 cargo advisories with undetermined directness (cargo_directness_undetermined)."
CRITICAL_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
MEDIUM_VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"

_STUB_SOURCE = '''#!__PYTHON__
import json
import sys

CONFIG = json.loads(__CONFIG__)
with open(CONFIG["record"], "a", encoding="utf-8") as rec:
    rec.write(json.dumps({"tool": CONFIG["tool"], "argv": sys.argv[1:]}) + "\\n")
sys.stdout.write(CONFIG["stdout"])
sys.exit(CONFIG["exit_code"])
'''


def cargo_entry(package, advisory_id, severity="high", cvss=None, **extra):
    """One cargo-audit vulnerability entry. `severity` / `cvss` follow the way
    the existing normalizer reads them; both None leaves the severity
    undeterminable. No `is_direct` unless passed through `extra`."""
    advisory = {"id": advisory_id, "title": f"title of {advisory_id}", "description": "d"}
    if cvss is not None:
        advisory["cvss"] = cvss
    entry = {
        "advisory": advisory,
        "package": {"name": package, "version": "1.0.0"},
        "versions": {"patched": [">=1.0.1"]},
    }
    if severity is not None:
        entry["severity"] = severity
    entry.update(extra)
    return entry


def cargo_payload(*entries):
    return {"vulnerabilities": {"found": bool(entries), "list": list(entries)}}


class CargoScanCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.root = self.base / "project"
        self.bin_dir = self.base / "bin"
        self.records_dir = self.base / "records"
        for directory in (self.root, self.bin_dir, self.records_dir):
            directory.mkdir()
        self.record_path = self.records_dir / "calls.jsonl"

    # -- fixtures ---------------------------------------------------------

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def cargo_project(self, manifest, rel_dir=""):
        """Cargo.toml (text or bytes) plus the Cargo.lock the binding needs."""
        prefix = f"{rel_dir}/" if rel_dir else ""
        manifest_path = self.write(f"{prefix}Cargo.toml", manifest)
        self.write(f"{prefix}Cargo.lock", "# lock\n")
        return manifest_path

    def install(self, tool, stdout, exit_code=0):
        config = {
            "tool": tool,
            "record": str(self.record_path),
            "stdout": stdout if isinstance(stdout, str) else json.dumps(stdout),
            "exit_code": exit_code,
        }
        source = _STUB_SOURCE.replace("__PYTHON__", sys.executable).replace(
            "__CONFIG__", repr(json.dumps(config))
        )
        path = self.bin_dir / tool
        path.write_text(source, encoding="utf-8")
        path.chmod(0o755)

    def install_cargo(self, *entries):
        self.install("cargo-audit", cargo_payload(*entries), exit_code=1 if entries else 0)

    # -- running ----------------------------------------------------------

    def scan(self, changed_files=("Cargo.toml",)):
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir)}):
            return SCAN.run_scan(self.root, list(changed_files), SCAN.DEFAULT_REGISTRY_PATH)

    def launches(self):
        if not self.record_path.exists():
            return []
        text = self.record_path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def scan_cargo(self, manifest, *entries):
        """A cargo-only scan of `manifest` reporting `entries`."""
        self.cargo_project(manifest)
        self.install_cargo(*entries)
        return self.scan()

    # -- assertions -------------------------------------------------------

    @staticmethod
    def titles(result):
        return [finding["title"] for finding in result["findings"]]

    def assertFindingFor(self, result, package, advisory_id):
        prefix = f"{package}: {advisory_id}"
        self.assertTrue(
            any(title.startswith(prefix) for title in self.titles(result)),
            f"no finding {prefix!r} in {self.titles(result)!r}",
        )

    def assertNoFinding(self, result):
        self.assertEqual(result["findings"], [])

    def assertCompletedWithNote(self, result, note):
        self.assertFalse(result["skipped"])
        self.assertIsNone(result["skip_reason"])
        self.assertTrue(result["summary"].endswith(note), result["summary"])

    def assertCompletedWithoutDirectnessNote(self, result):
        self.assertFalse(result["skipped"])
        self.assertIsNone(result["skip_reason"])
        self.assertNotIn("undetermined directness", result["summary"])


# ---------------------------------------------------------------------------
# AC-1 (FR1): canonical matching and is_direct precedence
# ---------------------------------------------------------------------------

class TestAc1CanonicalMatching(CargoScanCase):
    def test_ac1_declared_foo_underscore_bar_matches_reported_foo_hyphen_bar(self):
        result = self.scan_cargo(
            '[package]\nname = "demo"\n\n[dependencies]\nFoo_Bar = "1"\n',
            cargo_entry("foo-bar", "RUSTSEC-2024-0001"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "foo-bar", "RUSTSEC-2024-0001")
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac1_case_and_separator_variants_match_in_both_directions(self):
        cases = [
            ("Foo_Bar", "foo-bar"),
            ("foo-bar", "FOO_BAR"),
            ("foo.bar", "foo_bar"),
            ("foo_bar", "Foo.Bar"),
            ("foo--bar", "foo-bar"),
            ("FOO", "foo"),
        ]
        for index, (declared, reported) in enumerate(cases):
            with self.subTest(declared=declared, reported=reported):
                rel_dir = f"variant{index}"
                self.cargo_project(f'[dependencies]\n"{declared}" = "1"\n', rel_dir=rel_dir)
                self.install_cargo(cargo_entry(reported, "RUSTSEC-2024-0002"))
                result = self.scan([f"{rel_dir}/Cargo.toml"])
                self.assertEqual(len(result["findings"]), 1)

    def test_ac1_a_different_name_is_not_matched_by_canonicalization(self):
        result = self.scan_cargo(
            '[dependencies]\nFoo_Bar = "1"\n',
            cargo_entry("foobar", "RUSTSEC-2024-0003"),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac1_is_direct_true_wins_over_the_manifest_with_an_incomplete_set(self):
        result = self.scan_cargo(
            '[workspace]\nmembers = ["crates/a"]\n',
            cargo_entry("undeclared", "RUSTSEC-2024-0004", is_direct=True),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "undeclared", "RUSTSEC-2024-0004")
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac1_is_direct_false_wins_over_a_declaring_manifest(self):
        result = self.scan_cargo(
            '[dependencies]\nserde = "1"\n',
            cargo_entry("serde", "RUSTSEC-2024-0005", is_direct=False),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac1_is_direct_false_is_never_undetermined_under_an_incomplete_set(self):
        result = self.scan_cargo(
            "this is [not valid toml",
            cargo_entry("serde", "RUSTSEC-2024-0006", is_direct=False),
            cargo_entry("tokio", "RUSTSEC-2024-0007", severity=None, is_direct=False),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)


# ---------------------------------------------------------------------------
# AC-2 (FR2): the tables that declare direct crates
# ---------------------------------------------------------------------------

class TestAc2DependencyTables(CargoScanCase):
    def test_ac2_dependencies_dev_dependencies_and_build_dependencies_are_direct(self):
        manifest = (
            '[package]\nname = "demo"\n\n'
            '[dependencies]\nserde = "1"\n\n'
            '[dev-dependencies]\nmockall = "0.11"\n\n'
            '[build-dependencies]\ncc = "1"\n'
        )
        result = self.scan_cargo(
            manifest,
            cargo_entry("serde", "RUSTSEC-2024-0010"),
            cargo_entry("mockall", "RUSTSEC-2024-0011"),
            cargo_entry("cc", "RUSTSEC-2024-0012"),
            cargo_entry("transitive-only", "RUSTSEC-2024-0013"),
        )
        self.assertEqual(len(result["findings"]), 3)
        for package, advisory_id in (
            ("serde", "RUSTSEC-2024-0010"),
            ("mockall", "RUSTSEC-2024-0011"),
            ("cc", "RUSTSEC-2024-0012"),
        ):
            self.assertFindingFor(result, package, advisory_id)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac2_the_sub_table_form_declares_a_direct_crate(self):
        result = self.scan_cargo(
            "[dependencies.serde]\nversion = '1'\nfeatures = ['derive']\n",
            cargo_entry("serde", "RUSTSEC-2024-0014"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "serde", "RUSTSEC-2024-0014")
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac2_the_sub_table_form_works_in_the_other_dependency_tables_too(self):
        manifest = (
            "[dev-dependencies.mockall]\nversion = '0.11'\n\n"
            "[build-dependencies.cc]\nversion = '1'\n"
        )
        result = self.scan_cargo(
            manifest,
            cargo_entry("mockall", "RUSTSEC-2024-0015"),
            cargo_entry("cc", "RUSTSEC-2024-0016"),
        )
        self.assertEqual(len(result["findings"]), 2)

    def test_ac2_target_specific_tables_declare_direct_crates(self):
        manifest = (
            "[target.'cfg(unix)'.dependencies]\nfoo = '1'\n\n"
            "[target.'cfg(windows)'.dev-dependencies]\nwinfoo = '1'\n\n"
            "[target.x86_64-unknown-linux-gnu.build-dependencies]\nlinuxfoo = '1'\n"
        )
        result = self.scan_cargo(
            manifest,
            cargo_entry("foo", "RUSTSEC-2024-0017"),
            cargo_entry("winfoo", "RUSTSEC-2024-0018"),
            cargo_entry("linuxfoo", "RUSTSEC-2024-0019"),
        )
        self.assertEqual(len(result["findings"]), 3)
        self.assertFindingFor(result, "foo", "RUSTSEC-2024-0017")
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac2_a_target_specific_sub_table_form_declares_a_direct_crate(self):
        result = self.scan_cargo(
            "[target.'cfg(unix)'.dependencies.foo]\nversion = '1'\n",
            cargo_entry("foo", "RUSTSEC-2024-0020"),
        )
        self.assertEqual(len(result["findings"]), 1)

    def test_ac2_a_complete_manifest_keeps_an_undeclared_crate_transitive(self):
        result = self.scan_cargo(
            '[dependencies]\nserde = "1"\n',
            cargo_entry("not-declared", "RUSTSEC-2024-0021"),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)


# ---------------------------------------------------------------------------
# AC-3 (FR2): package renames and workspace inheritance
# ---------------------------------------------------------------------------

class TestAc3RenamesAndWorkspaceInheritance(CargoScanCase):
    def test_ac3_a_package_rename_makes_the_real_name_direct_and_not_the_alias(self):
        manifest = "[dependencies]\nalias = { package = 'real-name', version = '1' }\n"
        result = self.scan_cargo(
            manifest,
            cargo_entry("real-name", "RUSTSEC-2024-0030"),
            cargo_entry("alias", "RUSTSEC-2024-0031"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "real-name", "RUSTSEC-2024-0030")
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac3_a_rename_in_the_sub_table_form_is_read_too(self):
        manifest = "[dependencies.alias]\npackage = 'real-name'\nversion = '1'\n"
        result = self.scan_cargo(
            manifest,
            cargo_entry("real-name", "RUSTSEC-2024-0032"),
            cargo_entry("alias", "RUSTSEC-2024-0033"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "real-name", "RUSTSEC-2024-0032")

    def test_ac3_a_workspace_entry_renamed_in_workspace_dependencies_is_direct_under_the_new_name(self):
        manifest = (
            "[workspace.dependencies]\nx = { version = '1', package = 'y' }\n\n"
            "[dependencies]\nx = { workspace = true }\n"
        )
        result = self.scan_cargo(
            manifest,
            cargo_entry("y", "RUSTSEC-2024-0034"),
            cargo_entry("x", "RUSTSEC-2024-0035"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "y", "RUSTSEC-2024-0034")
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac3_a_workspace_entry_without_a_rename_is_direct_under_its_key(self):
        manifest = (
            "[workspace.dependencies]\nx = '1'\n\n"
            "[dependencies]\nx = { workspace = true }\n"
        )
        result = self.scan_cargo(manifest, cargo_entry("x", "RUSTSEC-2024-0036"))
        self.assertEqual(len(result["findings"]), 1)

    def test_ac3_a_workspace_entry_missing_from_workspace_dependencies_is_direct_under_its_key(self):
        manifest = "[dependencies]\nx = { workspace = true }\n"
        result = self.scan_cargo(manifest, cargo_entry("x", "RUSTSEC-2024-0037"))
        self.assertEqual(len(result["findings"]), 1)

    def test_ac3_workspace_dependencies_entries_are_not_direct_by_themselves(self):
        manifest = "[workspace.dependencies]\nz = '1'\n\n[dependencies]\nserde = '1'\n"
        result = self.scan_cargo(manifest, cargo_entry("z", "RUSTSEC-2024-0038"))
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)


# ---------------------------------------------------------------------------
# AC-4 (FR5, TM-5): workspace members leave the set incomplete
# ---------------------------------------------------------------------------

class TestAc4WorkspaceMembers(CargoScanCase):
    WORKSPACE_MANIFEST = (
        '[workspace]\nmembers = ["crates/a", "crates/b"]\n\n'
        '[dependencies]\nserde = "1"\n'
    )

    def test_ac4_an_undeclared_advisory_under_workspace_members_is_counted_not_a_finding(self):
        result = self.scan_cargo(
            self.WORKSPACE_MANIFEST,
            cargo_entry("member-only-crate", "RUSTSEC-2024-0040"),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    def test_ac4_crates_declared_in_the_roots_own_tables_remain_direct(self):
        result = self.scan_cargo(
            self.WORKSPACE_MANIFEST,
            cargo_entry("serde", "RUSTSEC-2024-0041"),
            cargo_entry("member-only-crate", "RUSTSEC-2024-0042"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "serde", "RUSTSEC-2024-0041")
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    def test_ac4_a_declared_advisory_is_never_counted_as_undetermined(self):
        result = self.scan_cargo(
            self.WORKSPACE_MANIFEST,
            cargo_entry("serde", "RUSTSEC-2024-0043"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac4_a_workspace_without_members_is_complete(self):
        manifest = '[workspace]\nresolver = "2"\n\n[dependencies]\nserde = "1"\n'
        result = self.scan_cargo(manifest, cargo_entry("undeclared", "RUSTSEC-2024-0044"))
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac4_a_workspace_with_an_empty_members_list_is_complete(self):
        manifest = "[workspace]\nmembers = []\n\n[dependencies]\nserde = '1'\n"
        result = self.scan_cargo(manifest, cargo_entry("undeclared", "RUSTSEC-2024-0045"))
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac4_a_complete_manifest_keeps_an_undeclared_advisory_transitive_without_a_note(self):
        result = self.scan_cargo(
            '[package]\nname = "demo"\n\n[dependencies]\nserde = "1"\n',
            cargo_entry("undeclared", "RUSTSEC-2024-0046"),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac4_member_manifests_are_not_read(self):
        # crates/a declares `member-dep`; the root's set stays incomplete and
        # the member's declaration does not turn the advisory into a finding.
        self.write("crates/a/Cargo.toml", "[dependencies]\nmember-dep = '1'\n")
        result = self.scan_cargo(
            self.WORKSPACE_MANIFEST,
            cargo_entry("member-dep", "RUSTSEC-2024-0047"),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)


# ---------------------------------------------------------------------------
# AC-5 (FR5, NFR3, TM-4): nothing a manifest contains can raise out of the scan
# ---------------------------------------------------------------------------

class TestAc5UnresolvableManifests(CargoScanCase):
    UNDECLARED = ("undeclared", "RUSTSEC-2024-0050")

    def assertCountedAsUndetermined(self, manifest):
        result = self.scan_cargo(manifest, cargo_entry(*self.UNDECLARED))
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    def test_ac5_invalid_toml_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined("[dependencies\nserde = ")

    def test_ac5_a_manifest_that_is_not_utf8_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined(b"\xff\xfe[dependencies]\nserde = '1'\n")

    def test_ac5_a_manifest_that_cannot_be_read_is_counted_as_undetermined(self):
        path = self.cargo_project('[dependencies]\nserde = "1"\n')
        self.install_cargo(cargo_entry(*self.UNDECLARED))
        path.chmod(0o000)
        self.addCleanup(path.chmod, 0o644)
        if os.access(path, os.R_OK):
            self.skipTest("file permissions are not enforced for this user")
        result = self.scan()
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    def test_ac5_a_dependencies_table_given_as_a_string_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined('dependencies = "serde"\n')

    def test_ac5_a_dev_dependencies_table_given_as_a_list_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined("dev-dependencies = ['serde']\n")

    def test_ac5_a_package_given_as_a_number_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined("[dependencies]\nalias = { package = 5, version = '1' }\n")

    def test_ac5_a_target_given_as_a_string_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined('target = "x"\n')

    def test_ac5_a_target_entry_that_is_not_a_table_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined("[target]\n'cfg(unix)' = 'x'\n")

    def test_ac5_a_target_dependencies_table_that_is_not_a_table_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined("[target.'cfg(unix)']\ndependencies = 5\n")

    def test_ac5_workspace_members_given_as_a_string_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined('[workspace]\nmembers = "crates/*"\n')

    def test_ac5_a_workspace_given_as_a_string_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined('workspace = "x"\n')

    def test_ac5_workspace_dependencies_given_as_a_string_is_counted_as_undetermined(self):
        self.assertCountedAsUndetermined('[workspace]\ndependencies = "x"\n')

    def test_ac5_a_workspace_rename_with_a_non_string_package_is_counted_as_undetermined(self):
        manifest = (
            "[workspace.dependencies]\nx = { version = '1', package = 7 }\n\n"
            "[dependencies]\nx = { workspace = true }\n"
        )
        self.assertCountedAsUndetermined(manifest)

    def test_ac5_the_declared_names_of_an_unexpected_shape_still_match(self):
        # An incomplete set keeps the names it did resolve.
        result = self.scan_cargo(
            "[dependencies]\nserde = '1'\nalias = { package = 5 }\n",
            cargo_entry("serde", "RUSTSEC-2024-0051"),
            cargo_entry(*self.UNDECLARED),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "serde", "RUSTSEC-2024-0051")
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    def test_ac5_the_resolver_never_raises_and_reports_incomplete_for_a_missing_file(self):
        missing = self.root / "does-not-exist" / "Cargo.toml"
        names = SCAN._cargo_direct_dependency_names(str(missing))
        self.assertFalse(names.complete)
        self.assertEqual(len(names), 0)

    def test_ac5_the_resolver_never_raises_for_a_directory_or_a_none_path(self):
        for bad in (str(self.root), None):
            with self.subTest(path=bad):
                names = SCAN._cargo_direct_dependency_names(bad)
                self.assertFalse(names.complete)

    def test_ac5_deeply_nested_toml_does_not_escape_the_scan(self):
        self.assertCountedAsUndetermined("a = " + "[" * 5000 + "]" * 5000 + "\n")


# ---------------------------------------------------------------------------
# AC-6 (FR5, NFR4, TM-6): counting edges, wording and position of the note
# ---------------------------------------------------------------------------

class TestAc6CountingAndNote(CargoScanCase):
    INCOMPLETE = '[workspace]\nmembers = ["crates/a"]\n'

    def test_ac6_a_known_severity_below_threshold_is_dropped_without_being_counted(self):
        result = self.scan_cargo(
            self.INCOMPLETE,
            cargo_entry("low-crate", "RUSTSEC-2024-0060", severity="low"),
            cargo_entry("medium-crate", "RUSTSEC-2024-0061", severity="medium"),
            cargo_entry("vector-crate", "RUSTSEC-2024-0062", severity=None, cvss=MEDIUM_VECTOR),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac6_an_unknown_severity_is_counted_exactly_once(self):
        result = self.scan_cargo(
            self.INCOMPLETE,
            cargo_entry("unknown-crate", "RUSTSEC-2024-0063", severity=None),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    def test_ac6_a_severity_at_or_above_threshold_is_counted(self):
        result = self.scan_cargo(
            self.INCOMPLETE,
            cargo_entry("high-crate", "RUSTSEC-2024-0064", severity="high"),
            cargo_entry("critical-crate", "RUSTSEC-2024-0065", severity=None, cvss=CRITICAL_VECTOR),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_TWO)

    def test_ac6_known_below_threshold_and_unknown_mix_counts_only_the_unknown(self):
        result = self.scan_cargo(
            self.INCOMPLETE,
            cargo_entry("low-crate", "RUSTSEC-2024-0066", severity="low"),
            cargo_entry("unknown-crate", "RUSTSEC-2024-0067", severity=None),
        )
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    def test_ac6_two_undetermined_advisories_use_the_plural_text(self):
        result = self.scan_cargo(
            self.INCOMPLETE,
            cargo_entry("a-crate", "RUSTSEC-2024-0068"),
            cargo_entry("b-crate", "RUSTSEC-2024-0069"),
        )
        self.assertCompletedWithNote(result, CARGO_NOTE_TWO)
        self.assertNotIn("advisory with", result["summary"])

    def test_ac6_two_advisories_for_one_crate_are_counted_twice(self):
        result = self.scan_cargo(
            self.INCOMPLETE,
            cargo_entry("a-crate", "RUSTSEC-2024-0070"),
            cargo_entry("a-crate", "RUSTSEC-2024-0071"),
        )
        self.assertCompletedWithNote(result, CARGO_NOTE_TWO)

    def test_ac6_the_note_carries_no_crate_name_manifest_path_or_advisory_text(self):
        result = self.scan_cargo(
            self.INCOMPLETE,
            cargo_entry("secret-crate-name", "RUSTSEC-2024-0072"),
        )
        summary = result["summary"]
        for fragment in ("secret-crate-name", "RUSTSEC-2024-0072", "title of", "Cargo.toml", str(self.root)):
            self.assertNotIn(fragment, summary)

    def test_ac6_the_note_is_counted_across_cargo_units(self):
        self.cargo_project(self.INCOMPLETE, rel_dir="svc-a")
        self.cargo_project(self.INCOMPLETE, rel_dir="svc-b")
        self.install_cargo(cargo_entry("undeclared", "RUSTSEC-2024-0073"))
        result = self.scan(["svc-a/Cargo.toml", "svc-b/Cargo.toml"])
        self.assertEqual(len(self.launches()), 2)
        self.assertCompletedWithNote(result, CARGO_NOTE_TWO)

    def test_ac6_the_cargo_note_follows_every_pre_existing_note(self):
        self.cargo_project(self.INCOMPLETE)
        self.install_cargo(cargo_entry("undeclared", "RUSTSEC-2024-0074"))
        # pip: a direct package whose advisory has no severity (pip note).
        self.write("requirements.txt", "django==3.2.0\n")
        self.install(
            "pip-audit",
            {
                "dependencies": [
                    {
                        "name": "django",
                        "version": "3.2.0",
                        "vulns": [
                            {"id": "PYSEC-2024-1", "fix_versions": [], "aliases": [], "description": "no vector"}
                        ],
                    }
                ]
            },
            exit_code=1,
        )
        # go: a direct module whose advisory has no severity (go note).
        self.write("go.mod", "module example.invalid/demo\n\nrequire example.invalid/dep v1.0.0\n")
        go_stream = "\n".join(
            json.dumps(obj)
            for obj in (
                {"config": {"protocol_version": "v1.0.0"}},
                {"osv": {"id": "GO-2024-0001"}},
                {"finding": {"osv": "GO-2024-0001", "trace": [{"module": "example.invalid/dep"}]}},
            )
        )
        self.install("govulncheck", go_stream, exit_code=0)
        result = self.scan(["Cargo.toml", "requirements.txt", "go.mod"])
        summary = result["summary"]
        pip_note = " 1 pip advisory with undetermined severity (pip_severity_undetermined)."
        go_note = " 1 go advisory with undetermined severity (go_severity_undetermined)."
        self.assertIn(pip_note, summary)
        self.assertIn(go_note, summary)
        self.assertTrue(summary.endswith(CARGO_NOTE_ONE), summary)
        self.assertLess(summary.index(pip_note), summary.index(CARGO_NOTE_ONE))
        self.assertLess(summary.index(go_note), summary.index(CARGO_NOTE_ONE))

    def test_ac6_the_note_composer_orders_pip_before_cargo_and_omits_zero_counts(self):
        compose = SCAN._undetermined_directness_notes
        pip_note = " 2 pip advisories with undetermined directness (pip_directness_undetermined)."
        cargo_note = " 1 cargo advisory with undetermined directness (cargo_directness_undetermined)."
        self.assertEqual(compose(0, 0), "")
        self.assertEqual(compose(2, 0), pip_note)
        self.assertEqual(compose(0, 1), cargo_note)
        self.assertEqual(compose(2, 1), pip_note + cargo_note)
        self.assertEqual(
            compose(1, 3),
            " 1 pip advisory with undetermined directness (pip_directness_undetermined)."
            " 3 cargo advisories with undetermined directness (cargo_directness_undetermined).",
        )


# ---------------------------------------------------------------------------
# AC-7 (FR6, NFR4, TM-6): tomllib unavailable
# ---------------------------------------------------------------------------

class TestAc7TomlParserUnavailable(CargoScanCase):
    def test_ac7_without_tomllib_the_cargo_unit_reports_the_fixed_skip_reason(self):
        self.cargo_project('[dependencies]\nserde = "1"\n')
        self.install_cargo(cargo_entry("serde", "RUSTSEC-2024-0080"))
        with mock.patch.object(SCAN, "tomllib", None):
            result = self.scan()
        self.assertTrue(result["skipped"])
        self.assertEqual(result["skip_reason"], "cargo_toml_parser_unavailable")
        self.assertEqual(result["findings"], [])

    def test_ac7_without_tomllib_the_cargo_audit_stand_in_is_never_invoked(self):
        self.cargo_project('[dependencies]\nserde = "1"\n')
        self.install_cargo(cargo_entry("serde", "RUSTSEC-2024-0081"))
        with mock.patch.object(SCAN, "tomllib", None):
            self.scan()
        self.assertEqual(self.launches(), [])

    def test_ac7_the_skip_text_carries_only_the_fixed_token(self):
        self.cargo_project('[dependencies]\nserde = "1"\n')
        self.install_cargo(cargo_entry("serde", "RUSTSEC-2024-0082"))
        with mock.patch.object(SCAN, "tomllib", None):
            result = self.scan()
        self.assertIn("cargo_toml_parser_unavailable", result["summary"])
        for fragment in ("serde", "RUSTSEC", "Cargo.toml", str(self.root)):
            self.assertNotIn(fragment, result["summary"])
        self.assertNotIn("undetermined directness", result["summary"])

    def test_ac7_the_check_is_made_at_call_time_each_time(self):
        self.cargo_project('[dependencies]\nserde = "1"\n')
        self.install_cargo(cargo_entry("serde", "RUSTSEC-2024-0083"))
        with mock.patch.object(SCAN, "tomllib", None):
            self.assertTrue(self.scan()["skipped"])
        self.assertEqual(self.launches(), [])
        result = self.scan()
        self.assertFalse(result["skipped"])
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(len(self.launches()), 1)

    def test_ac7_a_cargo_skip_does_not_stop_other_ecosystems(self):
        self.cargo_project('[dependencies]\nserde = "1"\n')
        self.install_cargo(cargo_entry("serde", "RUSTSEC-2024-0084"))
        self.write("go.mod", "module example.invalid/demo\n")
        go_stream = json.dumps({"config": {"protocol_version": "v1.0.0"}})
        self.install("govulncheck", go_stream, exit_code=0)
        with mock.patch.object(SCAN, "tomllib", None):
            result = self.scan(["Cargo.toml", "go.mod"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["skip_reason"], "cargo_toml_parser_unavailable")
        self.assertEqual([call["tool"] for call in self.launches()], ["govulncheck"])


# ---------------------------------------------------------------------------
# DirectNames contract (IMPLEMENTATION.md "Shared Components")
# ---------------------------------------------------------------------------

class TestDirectNamesContract(unittest.TestCase):
    def test_it_reads_like_an_immutable_set_of_the_names(self):
        names = SCAN.DirectNames({"serde", "Foo_Bar"}, complete=False)
        self.assertIn("serde", names)
        self.assertNotIn("tokio", names)
        self.assertEqual(len(names), 2)
        self.assertEqual(sorted(names), ["Foo_Bar", "serde"])
        self.assertEqual(names, {"serde", "Foo_Bar"})
        self.assertFalse(hasattr(names, "add"))

    def test_it_exposes_a_read_only_complete_flag(self):
        self.assertTrue(SCAN.DirectNames({"a"}, complete=True).complete)
        self.assertFalse(SCAN.DirectNames({"a"}, complete=False).complete)
        with self.assertRaises(AttributeError):
            SCAN.DirectNames({"a"}).complete = False

    def test_names_are_kept_as_written(self):
        self.assertEqual(set(SCAN.DirectNames({"Foo_Bar"})), {"Foo_Bar"})

    def test_a_legacy_plain_set_from_a_resolver_is_treated_as_complete(self):
        # The legacy-value rule: a stand-in resolver that still returns a plain
        # set classifies exactly as a complete set does.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "Cargo.toml").write_text("[dependencies]\nserde = '1'\n", encoding="utf-8")
            payload = cargo_payload(
                cargo_entry("serde", "RUSTSEC-2024-0090"),
                cargo_entry("undeclared", "RUSTSEC-2024-0091"),
            )
            ecosystem = {"ecosystem": "cargo", "severity_map": {"critical": "critical", "high": "high"}, "threshold": {"direct_only": True}}
            with mock.patch.object(SCAN, "_cargo_direct_dependency_names", lambda path: {"serde"}):
                findings, undetermined = SCAN.normalize_cargo(ecosystem, payload, "Cargo.toml", root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(undetermined, 0)


# ---------------------------------------------------------------------------
# AC-8 (NFR1): standard library only
# ---------------------------------------------------------------------------

class TestAc8StandardLibraryOnly(unittest.TestCase):
    @staticmethod
    def top_level_imports(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
        return modules

    def test_ac8_the_script_imports_only_the_standard_library_and_guarded_yaml(self):
        modules = self.top_level_imports(SCRIPT_PATH)
        # `yaml` is the script's pre-existing guarded optional import.
        outside = {m for m in modules if m not in sys.stdlib_module_names and m != "yaml"}
        self.assertEqual(outside, set())

    def test_ac8_tomllib_is_reached_only_through_the_guarded_import(self):
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        imports_of_tomllib = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Import) and any(a.name == "tomllib" for a in node.names)
        ]
        self.assertEqual(len(imports_of_tomllib), 1)
        guarded = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Try) and any(imp in ast.walk(node) for imp in imports_of_tomllib)
        ]
        self.assertEqual(len(guarded), 1)

    def test_ac8_this_module_imports_only_the_standard_library(self):
        modules = self.top_level_imports(Path(__file__))
        self.assertEqual({m for m in modules if m not in sys.stdlib_module_names}, set())


# ---------------------------------------------------------------------------
# sca-cargo-implicit-workspace-members task0001: a `[workspace]` root manifest
# with a path-bearing root dependency entry leaves the direct set incomplete
# (feature-docs/sca-cargo-implicit-workspace-members/tasks/task0001.md)
#
# - AC-1 (FR1, FR4, FR5, TM-1, TM-2): a `[workspace]` without `members` (or
#   with `members = []`) and a root path dependency counts an undeclared
#   advisory in the cargo note; the member manifest is not read.
# - AC-2 (FR1, FR5, TM-1): the path entry in dev-dependencies,
#   build-dependencies, a target table and the sub-table form.
# - AC-3 (FR2, FR5, TM-1): a path inherited through `workspace = true`, also
#   with a `package` rename.
# - AC-4 (FR4): declared crates stay findings, determined-below-threshold
#   advisories are dropped uncounted.
# - AC-5 (FR3, NFR5): workspaces without a path-bearing root entry, `[patch]`
#   and `[replace]` paths, and manifests without `[workspace]` stay complete.
# - AC-6 (NFR2, NFR3, NFR4, TM-2, TM-3, TM-4): the path value is never
#   followed, non-string `path` values raise nothing, and no manifest-derived
#   text reaches the result.
# - AC-7 (NFR1, NFR5, NFR6) is the full suite plus the plugin-invariants
#   check, run by the implementer, not from in here.
# ---------------------------------------------------------------------------

class TestCargoImplicitWorkspaceMembers(CargoScanCase):
    UNDECLARED = ("undeclared-member-dep", "RUSTSEC-2025-0100")

    # -- helpers ----------------------------------------------------------

    def assertUndeterminedOnce(self, manifest):
        """An undeclared high-severity advisory is no finding and is counted
        once in the cargo undetermined note."""
        result = self.scan_cargo(manifest, cargo_entry(*self.UNDECLARED))
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)
        return result

    def assertStaysTransitive(self, manifest):
        """An undeclared high-severity advisory stays transitive: no finding
        and no cargo undetermined note."""
        result = self.scan_cargo(manifest, cargo_entry(*self.UNDECLARED))
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)
        return result

    def write_member(self, declared="undeclared-member-dep"):
        """member/Cargo.toml declares `declared`; it must never be read."""
        self.write("member/Cargo.toml", f"[dependencies]\n{declared} = '1'\n")

    # -- AC-1 (FR1, FR4, FR5, TM-1, TM-2) ---------------------------------

    def test_ac1_a_workspace_without_members_and_a_root_path_dependency_is_counted_not_a_finding(self):
        self.write_member()
        self.assertUndeterminedOnce(
            '[workspace]\nresolver = "2"\n\n[dependencies]\nmember = { path = "member" }\n'
        )

    def test_ac1_a_workspace_with_an_empty_members_list_and_a_root_path_dependency_is_counted(self):
        self.write_member()
        self.assertUndeterminedOnce(
            '[workspace]\nmembers = []\n\n[dependencies]\nmember = { path = "member" }\n'
        )

    def test_ac1_an_empty_workspace_table_and_a_root_path_dependency_is_counted(self):
        self.write_member()
        self.assertUndeterminedOnce('[workspace]\n\n[dependencies]\nmember = { path = "member" }\n')

    def test_ac1_the_member_manifest_declaration_does_not_turn_the_advisory_into_a_finding(self):
        # member/Cargo.toml declares the advisory's crate; the root's set stays
        # incomplete and the member manifest is not read.
        self.write_member()
        result = self.scan_cargo(
            '[workspace]\n\n[dependencies]\nmember = { path = "member" }\n',
            cargo_entry(*self.UNDECLARED),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)
        self.assertFalse(result["skipped"])
        self.assertIsNone(result["skip_reason"])

    # -- AC-2 (FR1, FR5, TM-1) --------------------------------------------

    def test_ac2_a_path_entry_in_dev_dependencies_is_counted(self):
        self.assertUndeterminedOnce(
            '[workspace]\n\n[dev-dependencies]\nmember = { path = "member" }\n'
        )

    def test_ac2_a_path_entry_in_build_dependencies_is_counted(self):
        self.assertUndeterminedOnce(
            '[workspace]\n\n[build-dependencies]\nmember = { path = "member" }\n'
        )

    def test_ac2_a_path_entry_in_a_target_dependencies_table_is_counted(self):
        self.assertUndeterminedOnce(
            "[workspace]\n\n[target.'cfg(unix)'.dependencies]\nmember = { path = 'member' }\n"
        )

    def test_ac2_a_path_entry_in_a_target_dev_dependencies_table_is_counted(self):
        self.assertUndeterminedOnce(
            "[workspace]\n\n[target.'cfg(unix)'.dev-dependencies]\nmember = { path = 'member' }\n"
        )

    def test_ac2_a_path_entry_in_a_target_build_dependencies_table_is_counted(self):
        self.assertUndeterminedOnce(
            "[workspace]\n\n[target.'cfg(windows)'.build-dependencies]\nmember = { path = 'member' }\n"
        )

    def test_ac2_a_path_entry_in_the_sub_table_form_is_counted(self):
        self.assertUndeterminedOnce('[workspace]\n\n[dependencies.member]\npath = "member"\n')

    def test_ac2_a_path_entry_in_the_dev_dependencies_sub_table_form_is_counted(self):
        self.assertUndeterminedOnce('[workspace]\n\n[dev-dependencies.member]\npath = "member"\n')

    def test_ac2_a_path_entry_in_the_target_sub_table_form_is_counted(self):
        self.assertUndeterminedOnce(
            "[workspace]\n\n[target.'cfg(unix)'.dependencies.member]\npath = 'member'\n"
        )

    def test_ac2_a_path_entry_next_to_a_plain_version_entry_is_counted(self):
        self.assertUndeterminedOnce(
            '[workspace]\n\n[dependencies]\nserde = "1"\nmember = { path = "member", version = "0.1" }\n'
        )

    # -- AC-3 (FR2, FR5, TM-1) --------------------------------------------

    def test_ac3_a_path_inherited_through_workspace_true_is_counted(self):
        self.assertUndeterminedOnce(
            '[workspace.dependencies]\nmember = { path = "member" }\n\n'
            "[dependencies]\nmember = { workspace = true }\n"
        )

    def test_ac3_a_path_inherited_in_the_sub_table_form_is_counted(self):
        self.assertUndeterminedOnce(
            '[workspace.dependencies]\nmember = { path = "member" }\n\n'
            "[dependencies.member]\nworkspace = true\n"
        )

    def test_ac3_a_path_inherited_in_a_target_table_is_counted(self):
        self.assertUndeterminedOnce(
            '[workspace.dependencies]\nmember = { path = "member" }\n\n'
            "[target.'cfg(unix)'.dependencies]\nmember = { workspace = true }\n"
        )

    def test_ac3_an_inherited_path_with_a_package_rename_counts_the_undeclared_advisory_once(self):
        self.assertUndeterminedOnce(
            '[workspace.dependencies]\nmember = { path = "member", package = "real-member" }\n\n'
            "[dependencies]\nmember = { workspace = true }\n"
        )

    def test_ac3_an_advisory_for_the_renamed_package_of_an_inherited_path_is_a_finding(self):
        result = self.scan_cargo(
            '[workspace.dependencies]\nmember = { path = "member", package = "real-member" }\n\n'
            "[dependencies]\nmember = { workspace = true }\n",
            cargo_entry("real-member", "RUSTSEC-2025-0101"),
            cargo_entry(*self.UNDECLARED),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "real-member", "RUSTSEC-2025-0101")
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    # -- AC-4 (FR4) -------------------------------------------------------

    def test_ac4_a_crate_declared_in_the_root_stays_a_finding_without_a_note_under_fr1(self):
        result = self.scan_cargo(
            '[workspace]\n\n[dependencies]\nserde = "1"\nmember = { path = "member" }\n',
            cargo_entry("serde", "RUSTSEC-2025-0102"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "serde", "RUSTSEC-2025-0102")
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac4_a_crate_declared_in_the_root_stays_a_finding_without_a_note_under_fr2(self):
        result = self.scan_cargo(
            '[workspace.dependencies]\nmember = { path = "member" }\n\n'
            '[dependencies]\nserde = "1"\nmember = { workspace = true }\n',
            cargo_entry("serde", "RUSTSEC-2025-0103"),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "serde", "RUSTSEC-2025-0103")
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac4_a_declared_finding_and_an_undeclared_advisory_give_one_finding_and_the_note(self):
        result = self.scan_cargo(
            '[workspace]\n\n[dependencies]\nserde = "1"\nmember = { path = "member" }\n',
            cargo_entry("serde", "RUSTSEC-2025-0104"),
            cargo_entry(*self.UNDECLARED),
        )
        self.assertEqual(len(result["findings"]), 1)
        self.assertFindingFor(result, "serde", "RUSTSEC-2025-0104")
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    def test_ac4_an_undeclared_advisory_below_the_threshold_is_dropped_uncounted_under_fr1(self):
        result = self.scan_cargo(
            '[workspace]\n\n[dependencies]\nmember = { path = "member" }\n',
            cargo_entry("undeclared-low", "RUSTSEC-2025-0105", severity="low"),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac4_an_undeclared_advisory_below_the_threshold_is_dropped_uncounted_under_fr2(self):
        result = self.scan_cargo(
            '[workspace.dependencies]\nmember = { path = "member" }\n\n'
            "[dependencies]\nmember = { workspace = true }\n",
            cargo_entry("undeclared-low", "RUSTSEC-2025-0106", severity="low"),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithoutDirectnessNote(result)

    def test_ac4_a_below_threshold_advisory_next_to_an_undetermined_one_is_not_counted(self):
        result = self.scan_cargo(
            '[workspace]\n\n[dependencies]\nmember = { path = "member" }\n',
            cargo_entry("undeclared-low", "RUSTSEC-2025-0107", severity="low"),
            cargo_entry(*self.UNDECLARED),
        )
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)

    # -- AC-5 (FR3, NFR5) -------------------------------------------------

    def test_ac5_a_workspace_without_members_and_without_a_path_entry_stays_transitive(self):
        self.assertStaysTransitive('[workspace]\n\n[dependencies]\nserde = "1"\n')

    def test_ac5_a_workspace_with_an_empty_members_list_and_without_a_path_entry_stays_transitive(self):
        self.assertStaysTransitive('[workspace]\nmembers = []\n\n[dependencies]\nserde = "1"\n')

    def test_ac5_an_unreferenced_workspace_dependencies_path_entry_stays_transitive(self):
        self.assertStaysTransitive(
            '[workspace.dependencies]\nmember = { path = "member" }\n\n[dependencies]\nserde = "1"\n'
        )

    def test_ac5_a_workspace_dependencies_path_entry_referenced_under_another_key_stays_transitive(self):
        self.assertStaysTransitive(
            '[workspace.dependencies]\nmember = { path = "member" }\nserde = "1"\n\n'
            "[dependencies]\nserde = { workspace = true }\n"
        )

    def test_ac5_an_inherited_entry_without_a_path_in_workspace_dependencies_stays_transitive(self):
        self.assertStaysTransitive(
            '[workspace.dependencies]\nserde = "1"\nlog = { version = "0.4" }\n\n'
            "[dependencies]\nserde = { workspace = true }\nlog = { workspace = true }\n"
        )

    def test_ac5_a_package_manifest_without_a_workspace_and_with_a_path_dependency_stays_transitive(self):
        self.assertStaysTransitive(
            '[package]\nname = "demo"\n\n[dependencies]\nmember = { path = "member" }\n'
        )

    def test_ac5_a_path_dependency_in_a_target_table_without_a_workspace_stays_transitive(self):
        self.assertStaysTransitive(
            "[target.'cfg(unix)'.dependencies]\nmember = { path = 'member' }\n"
        )

    def test_ac5_a_patch_path_entry_does_not_make_a_workspace_incomplete(self):
        self.assertStaysTransitive(
            '[workspace]\n\n[dependencies]\nserde = "1"\n\n'
            '[patch.crates-io]\nserde = { path = "vendor/serde" }\n'
        )

    def test_ac5_a_replace_path_entry_does_not_make_a_workspace_incomplete(self):
        self.assertStaysTransitive(
            '[workspace]\n\n[dependencies]\nserde = "1"\n\n'
            '[replace]\n"serde:1.0.0" = { path = "vendor/serde" }\n'
        )

    # -- AC-6 (NFR2, NFR3, NFR4, TM-2, TM-3, TM-4) ------------------------

    DISTINCTIVE_DEP = "zz-distinctive-dependency-q7"
    OUTSIDE_CRATE = "outside-declared-crate"

    def assertCountedWithoutLeaking(self, manifest, leaks=()):
        """The scan of `manifest` returns normally; the resolver called
        directly flags the set incomplete without raising and reads the root
        manifest only; the undeclared advisory is counted once, no finding;
        neither summary nor skip_reason carries manifest-derived text."""
        manifest_path = self.cargo_project(manifest)
        self.install_cargo(cargo_entry(self.OUTSIDE_CRATE, "RUSTSEC-2025-0108"))
        result = self.scan()
        self.assertNoFinding(result)
        self.assertCompletedWithNote(result, CARGO_NOTE_ONE)
        for fragment in (*leaks, "Cargo.toml", str(manifest_path), str(self.root)):
            self.assertNotIn(fragment, result["summary"])
        reads = []
        original = SCAN._read_resolved_text

        def recording(path):
            reads.append(str(path))
            return original(path)

        with mock.patch.object(SCAN, "_read_resolved_text", recording):
            names = SCAN._cargo_direct_dependency_names(str(manifest_path))
        self.assertFalse(names.complete)
        self.assertEqual(reads, [str(manifest_path)])

    def test_ac6_a_path_value_pointing_outside_the_project_is_never_followed(self):
        outside = self.base / "outside-the-project-q7"
        outside.mkdir()
        (outside / "Cargo.toml").write_text(
            f"[dependencies]\n{self.OUTSIDE_CRATE} = '1'\n", encoding="utf-8"
        )
        manifest = f"[workspace]\n\n[dependencies]\n{self.DISTINCTIVE_DEP} = {{ path = '{outside}' }}\n"
        self.assertCountedWithoutLeaking(manifest, leaks=(self.DISTINCTIVE_DEP, str(outside), "outside-the-project-q7"))

    def test_ac6_an_integer_path_value_on_a_root_entry_is_handled(self):
        manifest = f"[workspace]\n\n[dependencies]\n{self.DISTINCTIVE_DEP} = {{ path = 5 }}\n"
        self.assertCountedWithoutLeaking(manifest, leaks=(self.DISTINCTIVE_DEP,))

    def test_ac6_a_table_path_value_on_a_root_entry_is_handled(self):
        manifest = f"[workspace]\n\n[dependencies]\n{self.DISTINCTIVE_DEP} = {{ path = {{ nested = 1 }} }}\n"
        self.assertCountedWithoutLeaking(manifest, leaks=(self.DISTINCTIVE_DEP,))

    def test_ac6_an_integer_path_value_on_an_inherited_workspace_entry_is_handled(self):
        manifest = (
            f"[workspace.dependencies]\n{self.DISTINCTIVE_DEP} = {{ path = 5 }}\n\n"
            f"[dependencies]\n{self.DISTINCTIVE_DEP} = {{ workspace = true }}\n"
        )
        self.assertCountedWithoutLeaking(manifest, leaks=(self.DISTINCTIVE_DEP,))

    def test_ac6_a_table_path_value_on_an_inherited_workspace_entry_is_handled(self):
        manifest = (
            f"[workspace.dependencies]\n{self.DISTINCTIVE_DEP} = {{ path = {{ nested = 1 }} }}\n\n"
            f"[dependencies]\n{self.DISTINCTIVE_DEP} = {{ workspace = true }}\n"
        )
        self.assertCountedWithoutLeaking(manifest, leaks=(self.DISTINCTIVE_DEP,))

    def test_ac6_a_path_bearing_entry_still_contributes_its_name_as_before(self):
        manifest_path = self.cargo_project(
            "[workspace.dependencies]\n"
            'inherited = { path = "inherited", package = "real-inherited" }\n\n'
            "[dependencies]\n"
            'member = { path = "member" }\n'
            'alias = { path = "alias", package = "real-alias" }\n'
            "inherited = { workspace = true }\n"
        )
        names = SCAN._cargo_direct_dependency_names(str(manifest_path))
        self.assertEqual(set(names), {"member", "real-alias", "real-inherited"})
        self.assertFalse(names.complete)

    def test_ac6_the_incompleteness_comes_from_the_flag_alone_not_from_a_new_reason_text(self):
        result = self.scan_cargo(
            '[workspace]\n\n[dependencies]\nmember = { path = "member" }\n',
            cargo_entry(*self.UNDECLARED),
        )
        self.assertIsNone(result["skip_reason"])
        self.assertEqual(result["summary"].count("undetermined directness"), 1)
        self.assertIn("cargo_directness_undetermined", result["summary"])


if __name__ == "__main__":
    unittest.main()
