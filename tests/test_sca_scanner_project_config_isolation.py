"""Tests for sca-scanner-project-config-isolation task0001: the axis-2 npm and
cargo scans run from a per-group isolation directory created outside the
reviewed tree, so the reviewed project's own `.npmrc` / `.cargo/audit.toml`
are no longer on the scanners' discovery path.

Covers the task's Acceptance Criteria
(feature-docs/sca-scanner-project-config-isolation/tasks/task0001.md):

- AC-1 (TM-1): npm runs from an isolation directory holding byte-identical
  copies of `package.json` and the selected anchor, with no `.npmrc` on the
  cwd or any ancestor path; argv is unchanged.
- AC-2 (TM-2): cargo-audit runs from an isolation directory with
  `--file <copy>` right after `audit`, no `--url` / `--db`; the target flag
  is declared by the registry and read by job assembly; directness is judged
  from the original Cargo.toml.
- AC-3 (TM-3, TM-7): several groups with different inputs each get their own
  directory and their own copies; order and labels are unchanged; an allowed
  same-directory symlink is copied as a regular file.
- AC-4 (TM-4): a temp parent redirected into the reviewed tree makes the unit
  `<ecosystem>_isolation_failed`; nothing is launched or changed.
- AC-5 (TM-5, TM-6, TM-9): a failed copy skips only its own group, with a
  path-free reason.
- AC-6 (TM-7, TM-8): no isolation directory remains after success, tool
  failure, timeout or a copy failure; the directory is owner-only.
- AC-7: `build_scan_job` with prepared inputs opens no file and launches no
  process.
- AC-8: child environments, `ECOSYSTEM_ENV_PINS` and the docstrings /
  comments (the full suite is run by the implementer, not from in here).

Per the task's Test Notes: no real scanner runs. Each tool is a recording
stub on a PATH restricted to its own directory. A stub reads its behavior
from a JSON file beside it -- the child environment is built explicitly by
the script under test, so a test-set environment variable could never reach
it. On every launch it records, BEFORE the isolation directory is removed,
its working directory, argv, environment, the permission bits of the working
directory, its listing and the content of every copied input, and whether a
`.npmrc` / `.cargo/audit.toml` exists in the working directory and in each
ancestor. The temp parent is a dedicated, empty directory that is a sibling
of the project tree; "no isolation directory remains" is that directory being
empty after the run. The process-wide temp-directory cache is reset before
and restored after every run. This module owns its own harness and imports
the standard library only.
"""

import ast
import base64
import contextlib
import errno
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"
REGISTRY_PATH = REPO_ROOT / "em-workflow" / "references" / "vuln-scanners.yaml"


def _load_script(name="scan_dependencies_config_isolation"):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

ENV_TEMP_KEYS = ("TMPDIR", "TEMP", "TMP")

NPM_CLEAN = {"vulnerabilities": {}}
CARGO_CLEAN = {"vulnerabilities": {"found": False, "list": []}}
NPM_VULN = {
    "vulnerabilities": {
        "lodash": {
            "name": "lodash",
            "severity": "critical",
            "isDirect": True,
            "range": "<4.17.21",
            "fixAvailable": {"name": "lodash", "version": "4.17.21"},
            "via": [
                {
                    "source": 1,
                    "name": "lodash",
                    "title": "Prototype Pollution in lodash",
                    "url": "https://github.com/advisories/GHSA-p6mc-m468-83gw",
                    "severity": "critical",
                    "range": "<4.17.21",
                }
            ],
        }
    }
}


def _cargo_entry(package, advisory_id):
    return {
        "advisory": {"id": advisory_id, "title": "t", "description": "d"},
        "package": {"name": package, "version": "1.0.0"},
        "versions": {"patched": [">=1.0.1"]},
        "severity": "high",
    }


# `foo` is a direct dependency of the fixture Cargo.toml, `bar` is not.
CARGO_VULN = {
    "vulnerabilities": {
        "found": True,
        "list": [_cargo_entry("foo", "RUSTSEC-2023-0001"), _cargo_entry("bar", "RUSTSEC-2023-0002")],
    }
}
CARGO_TOML = '[package]\nname = "demo"\n\n[dependencies]\nfoo = "1"\n'

ADVERSARIAL_NPMRC = (
    "https-proxy=http://evil.example.invalid:3128\n"
    "strict-ssl=false\n"
    "registry=http://evil.example.invalid/\n"
    "cafile=/evil/ca.pem\n"
)
ADVERSARIAL_AUDIT_TOML = (
    "[advisories]\n"
    'ignore = ["RUSTSEC-2023-0001"]\n'
    "[database]\n"
    'url = "https://evil.example.invalid/advisory-db.git"\n'
    'path = "/evil/advisory-db"\n'
)

_STUB_SOURCE = '''#!__PYTHON__
import base64
import json
import os
import stat
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.basename(__file__)
with open(os.path.join(HERE, TOOL + ".config.json"), encoding="utf-8") as fh:
    CONFIG = json.load(fh)


def b64(path):
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


cwd = os.path.realpath(os.getcwd())
entries = {}
for name in sorted(os.listdir(cwd)):
    path = os.path.join(cwd, name)
    st = os.lstat(path)
    entry = {
        "regular": stat.S_ISREG(st.st_mode),
        "symlink": stat.S_ISLNK(st.st_mode),
        "mode": stat.S_IMODE(st.st_mode),
    }
    if entry["regular"]:
        entry["content"] = b64(path)
    entries[name] = entry

ancestors = []
current = cwd
while True:
    ancestors.append({
        "dir": current,
        "npmrc": os.path.lexists(os.path.join(current, ".npmrc")),
        "audit_toml": os.path.lexists(os.path.join(current, ".cargo", "audit.toml")),
    })
    parent = os.path.dirname(current)
    if parent == current:
        break
    current = parent

argv_files = {}
for arg in sys.argv[1:]:
    if os.path.isfile(arg):
        argv_files[arg] = b64(arg)

record = {
    "tool": TOOL,
    "argv": sys.argv,
    "cwd": cwd,
    "cwd_mode": stat.S_IMODE(os.stat(cwd).st_mode),
    "home": os.environ.get("HOME"),
    "env": dict(os.environ),
    "entries": entries,
    "ancestors": ancestors,
    "argv_files": argv_files,
}
with open(CONFIG["record"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record) + "\\n")

if CONFIG.get("litter"):
    cache = os.path.join(cwd, "scanner-cache")
    os.makedirs(os.path.join(cache, "nested"))
    with open(os.path.join(cache, "nested", "entry.txt"), "w", encoding="utf-8") as fh:
        fh.write("left behind by the scanner")
    os.chmod(os.path.join(cache, "nested"), 0o500)
    os.chmod(cache, 0o500)
    with open(CONFIG["record"] + ".litter", "a", encoding="utf-8") as fh:
        fh.write("littered\\n")

mode = CONFIG["mode"]
if mode == "sleep":
    time.sleep(120)
if mode == "fail":
    sys.exit(2)
if mode == "garbage":
    sys.stdout.write("this is not json")
    sys.exit(0)
sys.stdout.write(json.dumps(CONFIG["payload"]))
sys.exit(CONFIG["exit_code"])
'''


def prepared_inputs(name):
    """A prepared-input value whose paths do not exist: `build_scan_job` only
    composes values from it."""
    if name == "npm":
        return SCAN.PreparedInputs(
            directory="/iso/npm",
            files={"manifest": "/iso/npm/package.json", "anchor": "/iso/npm/package-lock.json"},
        )
    return SCAN.PreparedInputs(directory="/iso/cargo", files={"lockfile": "/iso/cargo/Cargo.lock"})


def inside(root, path):
    """True when `path` equals `root` or lies under it, by path components."""
    return Path(os.path.realpath(path)).is_relative_to(os.path.realpath(root))


def snapshot(root):
    """Paths plus contents of a tree, without following symlinks."""
    result = {}
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = os.path.join(current, name)
            rel = os.path.relpath(path, root)
            if os.path.islink(path):
                result[rel] = ("link", os.readlink(path))
            elif os.path.isdir(path):
                result[rel] = ("dir", None)
            else:
                with open(path, "rb") as fh:
                    result[rel] = ("file", fh.read())
    return result


class IsolationCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.root = self.base / "project"
        self.bin_dir = self.base / "bin"
        self.iso_tmp = self.base / "iso-tmp"
        self.records_dir = self.base / "records"
        self.home = self.base / "home"
        for directory in (self.root, self.bin_dir, self.iso_tmp, self.records_dir, self.home):
            directory.mkdir()
        self.record_path = self.records_dir / "calls.jsonl"
        self.run_environ = None
        self.configure("npm", "normal", NPM_CLEAN)
        self.configure("cargo-audit", "normal", CARGO_CLEAN)
        for tool in ("npm", "cargo-audit"):
            stub = self.bin_dir / tool
            stub.write_text(_STUB_SOURCE.replace("__PYTHON__", sys.executable), encoding="utf-8")
            stub.chmod(0o755)

    # -- fixtures ---------------------------------------------------------

    def configure(self, tool, mode, payload=None, exit_code=0, litter=False):
        config = {
            "record": str(self.record_path),
            "mode": mode,
            "payload": payload,
            "exit_code": exit_code,
            "litter": litter,
        }
        (self.bin_dir / f"{tool}.config.json").write_text(json.dumps(config), encoding="utf-8")

    def use_vulnerable_stubs(self):
        self.configure("npm", "normal", NPM_VULN, exit_code=1)
        self.configure("cargo-audit", "normal", CARGO_VULN, exit_code=1)

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def npm_project(self, rel_dir="", tag=None):
        """package.json and package-lock.json whose bytes are unique to the
        directory (non-UTF-8 bytes and CRLF included) -- returns both."""
        tag = tag if tag is not None else (rel_dir or "root")
        prefix = f"{rel_dir}/" if rel_dir else ""
        manifest = f'{{"name": "{tag}"}}\r\n'.encode() + b"\xff\x00manifest"
        lock = f'{{"lock": "{tag}"}}\r\n'.encode() + b"\xfe\x00lock"
        self.write(f"{prefix}package.json", manifest)
        self.write(f"{prefix}package-lock.json", lock)
        return manifest, lock

    def cargo_project(self, rel_dir="", tag=None):
        tag = tag if tag is not None else (rel_dir or "root")
        prefix = f"{rel_dir}/" if rel_dir else ""
        lock = f"# Cargo.lock of {tag}\r\n".encode() + b"\xfd\x00lock"
        self.write(f"{prefix}Cargo.toml", CARGO_TOML)
        self.write(f"{prefix}Cargo.lock", lock)
        return lock

    # -- running ----------------------------------------------------------

    @contextlib.contextmanager
    def runner_environment(self, temp_via="TMPDIR", temp_dir=None):
        """PATH is the stub directory only and HOME a test value. Of the temp
        sources exactly `temp_via` is set (`override` is the process-wide
        `tempfile.tempdir`), pointing at `temp_dir` (default: the dedicated
        empty temp parent). The cached selection is reset before and restored
        after."""
        temp_dir = self.iso_tmp if temp_dir is None else temp_dir
        saved_cache = tempfile.tempdir
        with mock.patch.dict(os.environ):
            for key in ENV_TEMP_KEYS:
                os.environ.pop(key, None)
            os.environ["PATH"] = str(self.bin_dir)
            os.environ["HOME"] = str(self.home)
            if temp_via in ENV_TEMP_KEYS:
                os.environ[temp_via] = str(temp_dir)
                tempfile.tempdir = None
            else:
                tempfile.tempdir = str(temp_dir)
            self.run_environ = dict(os.environ)
            try:
                yield
            finally:
                tempfile.tempdir = saved_cache

    def scan(self, changed_files, **environment):
        with self.runner_environment(**environment):
            return SCAN.run_scan(self.root, changed_files, SCAN.DEFAULT_REGISTRY_PATH)

    def launches(self, tool=None):
        if not self.record_path.exists():
            return []
        text = self.record_path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
        return [r for r in records if tool is None or r["tool"] == tool]

    @staticmethod
    def content(record, name):
        return base64.b64decode(record["entries"][name]["content"])

    def assertNoIsolationDirectoryRemains(self):
        self.assertEqual(sorted(p.name for p in self.iso_tmp.iterdir()), [])

    def assertEveryLaunchRanFromTheTempParentAndLeftNothing(self, expected_launches):
        records = self.launches()
        self.assertEqual(len(records), expected_launches)
        for record in records:
            self.assertRanFromTheTempParent(record)
            self.assertFalse(os.path.exists(record["cwd"]), "the isolation directory remains")
        self.assertNoIsolationDirectoryRemains()

    def assertRanFromTheTempParent(self, record, parent=None):
        """The scanner's cwd is a directory under the temp parent (so the
        isolation directory existed while it ran) and not inside the tree."""
        parent = self.iso_tmp if parent is None else parent
        self.assertTrue(inside(parent, record["cwd"]), "the cwd is not under the temp parent")
        self.assertNotEqual(Path(record["cwd"]).resolve(), Path(parent).resolve())
        self.assertFalse(inside(self.root, record["cwd"]), "the cwd is inside the reviewed tree")

    def assertConfigurationNotDiscoverable(self, record):
        self.assertFalse(inside(self.root, record["cwd"]), "the cwd is inside the reviewed tree")
        for ancestor in record["ancestors"]:
            self.assertFalse(ancestor["npmrc"], f"a .npmrc exists in {ancestor['dir']}")
            self.assertFalse(ancestor["audit_toml"], f"a .cargo/audit.toml exists in {ancestor['dir']}")


# ---------------------------------------------------------------------------
# AC-1 (FR1, FR5, FR9, FR12; TM-1)
# ---------------------------------------------------------------------------

class TestNpmRunsFromAnIsolationDirectory(IsolationCase):
    def test_ac1_cwd_is_outside_the_project_and_free_of_project_configuration(self):
        self.write(".npmrc", ADVERSARIAL_NPMRC)
        manifest, lock = self.npm_project("")
        self.use_vulnerable_stubs()
        result = self.scan(["package.json"])
        (record,) = self.launches("npm")
        self.assertConfigurationNotDiscoverable(record)
        self.assertTrue(inside(self.iso_tmp, record["cwd"]))
        self.assertEqual(
            record["argv"],
            [str(self.bin_dir / "npm"), "audit", "--json", "--workspaces=false"],
        )
        self.assertEqual(self.content(record, "package.json"), manifest)
        self.assertEqual(self.content(record, "package-lock.json"), lock)
        self.assertEqual(sorted(record["entries"]), ["package-lock.json", "package.json"])
        self.assertFalse(result["skipped"], result)
        self.assertEqual([f["file"] for f in result["findings"]], ["package.json"])

    def test_ac1_the_copies_are_regular_files_not_links(self):
        self.npm_project("")
        self.scan(["package.json"])
        (record,) = self.launches("npm")
        self.assertRanFromTheTempParent(record)
        for name in ("package.json", "package-lock.json"):
            self.assertTrue(record["entries"][name]["regular"], name)
            self.assertFalse(record["entries"][name]["symlink"], name)

    def test_ac1_a_nested_project_runs_from_an_isolation_directory_with_its_own_label(self):
        self.write("services/api/.npmrc", ADVERSARIAL_NPMRC)
        manifest, _lock = self.npm_project("services/api")
        self.use_vulnerable_stubs()
        result = self.scan(["services/api/package.json"])
        (record,) = self.launches("npm")
        self.assertConfigurationNotDiscoverable(record)
        self.assertEqual(self.content(record, "package.json"), manifest)
        self.assertEqual([f["file"] for f in result["findings"]], ["services/api/package.json"])

    def test_ac1_shrinkwrap_is_the_only_anchor_copied_when_both_anchors_exist(self):
        manifest, lock = self.npm_project("")
        shrinkwrap = b'{"shrinkwrap": true}\r\n\xfc\x00'
        self.write("npm-shrinkwrap.json", shrinkwrap)
        self.scan(["package.json"])
        (record,) = self.launches("npm")
        self.assertEqual(sorted(record["entries"]), ["npm-shrinkwrap.json", "package.json"])
        self.assertEqual(self.content(record, "npm-shrinkwrap.json"), shrinkwrap)
        self.assertEqual(self.content(record, "package.json"), manifest)
        self.assertNotIn(lock, [self.content(record, n) for n in record["entries"]])

    def test_ac1_a_lockfile_only_change_is_labelled_with_that_lockfile(self):
        self.npm_project("a")
        self.use_vulnerable_stubs()
        result = self.scan(["a/package-lock.json"])
        (record,) = self.launches("npm")
        self.assertRanFromTheTempParent(record)
        self.assertEqual([f["file"] for f in result["findings"]], ["a/package-lock.json"])

    def test_ac1_the_project_tree_is_left_untouched(self):
        self.write(".npmrc", ADVERSARIAL_NPMRC)
        self.npm_project("")
        before = snapshot(self.root)
        self.scan(["package.json"])
        self.assertRanFromTheTempParent(self.launches("npm")[0])
        self.assertEqual(snapshot(self.root), before)


# ---------------------------------------------------------------------------
# AC-2 (FR2, FR3, FR5, FR9, FR12; TM-2)
# ---------------------------------------------------------------------------

class TestCargoRunsFromAnIsolationDirectoryWithTheCopiedLockfile(IsolationCase):
    def test_ac2_cwd_argv_and_copy_of_a_project_with_an_adversarial_audit_config(self):
        self.write(".cargo/audit.toml", ADVERSARIAL_AUDIT_TOML)
        lock = self.cargo_project("")
        self.use_vulnerable_stubs()
        result = self.scan(["Cargo.toml"])
        (record,) = self.launches("cargo-audit")
        self.assertConfigurationNotDiscoverable(record)
        self.assertTrue(inside(self.iso_tmp, record["cwd"]))
        executable, *rest = record["argv"]
        self.assertEqual(executable, str(self.bin_dir / "cargo-audit"))
        self.assertEqual(rest[:2], ["audit", "--file"])
        copy = rest[2]
        self.assertEqual(rest[3:], ["--json"])
        self.assertNotIn("--url", record["argv"])
        self.assertNotIn("--db", record["argv"])
        self.assertTrue(inside(record["cwd"], copy), "the copy lies outside the recorded cwd")
        self.assertEqual(base64.b64decode(record["argv_files"][copy]), lock)
        self.assertEqual(sorted(record["entries"]), ["Cargo.lock"])
        self.assertFalse(result["skipped"], result)

    def test_ac2_a_vulnerability_in_a_crate_direct_in_the_original_cargo_toml_is_judged_direct(self):
        self.cargo_project("crates/a")
        self.use_vulnerable_stubs()
        result = self.scan(["crates/a/Cargo.toml"])
        (record,) = self.launches("cargo-audit")
        self.assertRanFromTheTempParent(record)
        self.assertEqual(record["argv"][2], "--file")
        self.assertEqual([f["file"] for f in result["findings"]], ["crates/a/Cargo.toml"])
        self.assertEqual([f["title"].split(":")[0] for f in result["findings"]], ["foo"])

    def test_ac2_the_registry_cargo_entry_declares_the_lockfile_target_flag(self):
        registry = SCAN.load_registry(REGISTRY_PATH)
        cargo = {e["ecosystem"]: e for e in registry["ecosystems"]}["cargo"]
        self.assertEqual(cargo["target_flag"], "--file")
        self.assertEqual(cargo["args"], ["audit", "--json"])

    def test_ac2_job_assembly_places_the_declared_flag_right_after_audit(self):
        cargo = self._cargo_entry()
        job = SCAN.build_scan_job(
            cargo, "Cargo.toml", "/proj", "/x/cargo-audit", prepared_inputs=prepared_inputs("cargo")
        )
        self.assertEqual(
            job["argv"], ["/x/cargo-audit", "audit", "--file", "/iso/cargo/Cargo.lock", "--json"]
        )

    def test_ac2_job_assembly_reads_the_declaration_it_does_not_hard_code_the_flag(self):
        cargo = dict(self._cargo_entry(), target_flag="--declared-elsewhere")
        job = SCAN.build_scan_job(
            cargo, "Cargo.toml", "/proj", "/x/cargo-audit", prepared_inputs=prepared_inputs("cargo")
        )
        self.assertEqual(job["argv"][:4], ["/x/cargo-audit", "audit", "--declared-elsewhere", "/iso/cargo/Cargo.lock"])
        self.assertNotIn("--file", job["argv"])

    def test_ac2_a_cargo_entry_without_the_declaration_yields_no_job(self):
        cargo = {k: v for k, v in self._cargo_entry().items() if k != "target_flag"}
        with self.assertRaises(SCAN.JobConstructionError):
            SCAN.build_scan_job(
                cargo, "Cargo.toml", "/proj", "/x/cargo-audit", prepared_inputs=prepared_inputs("cargo")
            )

    def test_ac2_the_project_tree_is_left_untouched(self):
        self.write(".cargo/audit.toml", ADVERSARIAL_AUDIT_TOML)
        self.cargo_project("")
        before = snapshot(self.root)
        self.scan(["Cargo.toml"])
        self.assertRanFromTheTempParent(self.launches("cargo-audit")[0])
        self.assertEqual(snapshot(self.root), before)

    @staticmethod
    def _cargo_entry():
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        return {e["ecosystem"]: e for e in registry["ecosystems"]}["cargo"]

    @staticmethod
    def _prepared(name):
        return prepared_inputs(name)


# ---------------------------------------------------------------------------
# AC-3 (FR5, FR8, FR9; TM-3, TM-7)
# ---------------------------------------------------------------------------

class TestEachGroupGetsItsOwnDirectoryAndItsOwnCopies(IsolationCase):
    def test_ac3_inputs_directories_order_and_labels_of_several_groups(self):
        npm_inputs = {d: self.npm_project(d) for d in ("c", "a", "b")}
        cargo_inputs = {d: self.cargo_project(d) for d in ("y", "x")}
        self.use_vulnerable_stubs()
        changed = [
            "c/package.json", "y/Cargo.toml", "a/package.json",
            "x/Cargo.toml", "b/package.json",
        ]
        result = self.scan(changed)

        npm_records = self.launches("npm")
        cargo_records = self.launches("cargo-audit")
        self.assertEqual(
            [self.content(r, "package.json") for r in npm_records],
            [npm_inputs[d][0] for d in ("a", "b", "c")],
        )
        self.assertEqual(
            [self.content(r, "package-lock.json") for r in npm_records],
            [npm_inputs[d][1] for d in ("a", "b", "c")],
        )
        self.assertEqual(
            [base64.b64decode(r["argv_files"][r["argv"][3]]) for r in cargo_records],
            [cargo_inputs[d] for d in ("x", "y")],
        )
        directories = [r["cwd"] for r in npm_records + cargo_records]
        self.assertEqual(len(set(directories)), 5, "isolation directories are not distinct")
        self.assertEqual(
            [r["tool"] for r in self.launches()], ["npm"] * 3 + ["cargo-audit"] * 2
        )
        self.assertEqual(
            [f["file"] for f in result["findings"]],
            ["a/package.json", "b/package.json", "c/package.json", "x/Cargo.toml", "y/Cargo.toml"],
        )
        self.assertFalse(result["skipped"], result)

    def test_ac3_an_allowed_same_directory_symlink_is_copied_as_a_regular_file(self):
        self.write("svc/package.json", b'{"name": "svc"}\n')
        target = b'{"lock": "the link target"}\n\xfb'
        self.write("svc/real-lock.json", target)
        os.symlink("real-lock.json", self.root / "svc" / "package-lock.json")
        result = self.scan(["svc/package.json"])
        (record,) = self.launches("npm")
        entry = record["entries"]["package-lock.json"]
        self.assertTrue(entry["regular"])
        self.assertFalse(entry["symlink"])
        self.assertEqual(self.content(record, "package-lock.json"), target)
        self.assertNotIn("real-lock.json", record["entries"])
        self.assertFalse(result["skipped"], result)

    def test_ac3_a_symlinked_cargo_lock_in_the_same_directory_is_copied_as_a_regular_file(self):
        self.write("Cargo.toml", CARGO_TOML)
        target = b"# the real lock\n\xfa"
        self.write("lock.real", target)
        os.symlink("lock.real", self.root / "Cargo.lock")
        result = self.scan(["Cargo.toml"])
        (record,) = self.launches("cargo-audit")
        self.assertTrue(record["entries"]["Cargo.lock"]["regular"])
        self.assertEqual(self.content(record, "Cargo.lock"), target)
        self.assertFalse(result["skipped"], result)

    def test_ac3_groups_are_launched_in_the_order_they_were_before_the_change(self):
        for directory in ("b", "a-b", "a/b", "a"):
            self.npm_project(directory)
        self.scan(["b/package.json", "a/b/package.json", "a-b/package.json", "a/package.json"])
        for record in self.launches("npm"):
            self.assertRanFromTheTempParent(record)
        # plain string order of the directory: "a" < "a-b" < "a/b" < "b"
        self.assertEqual(
            [json.loads(self.content(r, "package.json").split(b"\r\n")[0])["name"]
             for r in self.launches("npm")],
            ["a", "a-b", "a/b", "b"],
        )


# ---------------------------------------------------------------------------
# AC-4 (FR6, FR7, NFR2; TM-4)
# ---------------------------------------------------------------------------

class TestATempParentInsideTheReviewedTreeIsAnIsolationFailure(IsolationCase):
    def setUp(self):
        super().setUp()
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.alias = self.base / "alias"
        os.symlink(self.scratch, self.alias)
        self.npm_project("")
        self.cargo_project("c")

    def assertIsolationFailsAndTheTreeIsUntouched(self, **environment):
        before = snapshot(self.root)
        result = self.scan(["package.json", "c/Cargo.toml"], **environment)
        self.assertTrue(result["skipped"], result)
        self.assertEqual(result["skip_reason"], "cargo_isolation_failed+npm_isolation_failed")
        self.assertEqual(result["findings"], [])
        self.assertEqual(self.launches(), [], "a scanner was launched")
        self.assertEqual(snapshot(self.root), before)
        self.assertNoIsolationDirectoryRemains()

    def test_ac4_tmpdir_pointing_into_the_tree(self):
        self.assertIsolationFailsAndTheTreeIsUntouched(temp_via="TMPDIR", temp_dir=self.scratch)

    def test_ac4_temp_pointing_into_the_tree(self):
        self.assertIsolationFailsAndTheTreeIsUntouched(temp_via="TEMP", temp_dir=self.scratch)

    def test_ac4_tmp_pointing_into_the_tree(self):
        self.assertIsolationFailsAndTheTreeIsUntouched(temp_via="TMP", temp_dir=self.scratch)

    def test_ac4_the_process_wide_override_pointing_into_the_tree(self):
        self.assertIsolationFailsAndTheTreeIsUntouched(temp_via="override", temp_dir=self.scratch)

    def test_ac4_a_temp_parent_that_resolves_through_a_symlink_into_the_tree(self):
        self.assertIsolationFailsAndTheTreeIsUntouched(temp_via="TMPDIR", temp_dir=self.alias)
        self.assertIsolationFailsAndTheTreeIsUntouched(temp_via="override", temp_dir=self.alias)

    def test_ac4_the_project_root_itself_as_the_temp_parent(self):
        self.assertIsolationFailsAndTheTreeIsUntouched(temp_via="TMPDIR", temp_dir=self.root)

    def test_ac4_a_sibling_whose_name_merely_starts_with_the_root_name_is_not_inside_it(self):
        sibling = self.base / "project-tmp"
        sibling.mkdir()
        result = self.scan(["package.json"], temp_dir=sibling)
        self.assertFalse(result["skipped"], result)
        (record,) = self.launches("npm")
        self.assertRanFromTheTempParent(record, parent=sibling)
        self.assertEqual(list(sibling.iterdir()), [])

    def test_ac4_an_in_tree_environment_variable_is_ignored_while_the_override_names_a_valid_parent(self):
        # the cached selection wins over the environment: the standard
        # selection would use the override, so that is what is checked.
        saved = tempfile.tempdir
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_dir), "TMPDIR": str(self.scratch)}):
            tempfile.tempdir = str(self.iso_tmp)
            try:
                result = SCAN.run_scan(self.root, ["package.json"], SCAN.DEFAULT_REGISTRY_PATH)
            finally:
                tempfile.tempdir = saved
        self.assertFalse(result["skipped"], result)
        (record,) = self.launches("npm")
        self.assertRanFromTheTempParent(record)
        self.assertEqual(list(self.scratch.iterdir()), [])


# ---------------------------------------------------------------------------
# AC-5 (FR7, NFR3; TM-5, TM-6, TM-9)
# ---------------------------------------------------------------------------

class TestACopyFailureAffectsOnlyItsOwnGroup(IsolationCase):
    SECRET = "boom-secret-text"

    def failing_copy(self, directory):
        """A `_copy_input` that fails for the lockfile of `directory` -- the
        SECOND copy of an npm group, after the manifest was already written."""
        real = SCAN._copy_input

        def flaky(source, destination):
            if Path(source).parent.name == directory and Path(source).name in (
                "package-lock.json", "Cargo.lock"
            ):
                raise OSError(errno.EIO, f"{self.SECRET} {source} -> {destination}")
            return real(source, destination)

        return mock.patch.object(SCAN, "_copy_input", side_effect=flaky)

    def assertPathFree(self, result):
        texts = [result["skip_reason"], result["summary"]]
        forbidden = [str(self.root), str(self.iso_tmp), str(self.base), self.SECRET, "iso-tmp"]
        forbidden += [r["cwd"] for r in self.launches()]
        for text in texts:
            for needle in forbidden:
                self.assertNotIn(needle, text)
            self.assertNotIn("/", text)

    def test_ac5_a_failed_npm_copy_launches_nothing_for_that_group_and_scans_the_others(self):
        self.npm_project("a")
        manifest_b, _ = self.npm_project("b")
        self.use_vulnerable_stubs()
        with self.failing_copy("a"):
            result = self.scan(["a/package.json", "b/package.json"])
        records = self.launches("npm")
        self.assertEqual([self.content(r, "package.json") for r in records], [manifest_b])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["skip_reason"], "npm_isolation_failed")
        self.assertEqual([f["file"] for f in result["findings"]], ["b/package.json"])
        self.assertEqual(
            result["summary"],
            "Scanned npm; 1 finding(s) at or above threshold. Not completed: npm_isolation_failed.",
        )
        self.assertPathFree(result)
        self.assertNoIsolationDirectoryRemains()

    def test_ac5_a_failed_cargo_copy_launches_nothing_for_that_group_and_scans_the_others(self):
        self.cargo_project("x")
        lock_y = self.cargo_project("y")
        self.use_vulnerable_stubs()
        with self.failing_copy("x"):
            result = self.scan(["x/Cargo.toml", "y/Cargo.toml"])
        records = self.launches("cargo-audit")
        self.assertEqual(
            [base64.b64decode(r["argv_files"][r["argv"][3]]) for r in records], [lock_y]
        )
        self.assertEqual(result["skip_reason"], "cargo_isolation_failed")
        self.assertEqual([f["file"] for f in result["findings"]], ["y/Cargo.toml"])
        self.assertPathFree(result)
        self.assertNoIsolationDirectoryRemains()

    def test_ac5_nothing_is_launched_when_every_group_fails(self):
        self.npm_project("a")
        with self.failing_copy("a"):
            result = self.scan(["a/package.json"])
        self.assertEqual(self.launches(), [])
        self.assertEqual(result["skip_reason"], "npm_isolation_failed")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["summary"], "Scan skipped: npm_isolation_failed")
        self.assertPathFree(result)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "permission bits do not bind root")
    def test_ac5_an_unreadable_input_is_an_isolation_failure_after_the_first_copy_succeeded(self):
        self.npm_project("a")
        manifest_b, _ = self.npm_project("b")
        self.use_vulnerable_stubs()
        (self.root / "a" / "package-lock.json").chmod(0)
        try:
            result = self.scan(["a/package.json", "b/package.json"])
        finally:
            (self.root / "a" / "package-lock.json").chmod(0o644)
        self.assertEqual([self.content(r, "package.json") for r in self.launches("npm")], [manifest_b])
        self.assertEqual(result["skip_reason"], "npm_isolation_failed")
        self.assertEqual([f["file"] for f in result["findings"]], ["b/package.json"])
        self.assertPathFree(result)
        self.assertNoIsolationDirectoryRemains()

    def test_ac5_a_source_that_no_longer_passes_the_binding_rule_at_copy_time_is_not_copied(self):
        # the binding check is forced to pass; the copy step re-validates
        # with the same rule and refuses an anchor that links elsewhere.
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "package-lock.json").write_bytes(b"{}\n")
        self.write("a/package.json", b"{}\n")
        os.symlink(outside / "package-lock.json", self.root / "a" / "package-lock.json")
        with mock.patch.object(SCAN, "_binding_check", return_value=True):
            result = self.scan(["a/package.json"])
        self.assertEqual(self.launches(), [])
        self.assertEqual(result["skip_reason"], "npm_isolation_failed")
        self.assertNoIsolationDirectoryRemains()

    def test_ac5_the_reason_never_falls_back_to_an_unbindable_or_execution_reason(self):
        self.npm_project("a")
        with self.failing_copy("a"):
            result = self.scan(["a/package.json"])
        self.assertNotIn("unbindable", result["skip_reason"])
        self.assertNotIn("execution_failed", result["skip_reason"])


# ---------------------------------------------------------------------------
# AC-6 (FR8, NFR2; TM-7, TM-8)
# ---------------------------------------------------------------------------

class TestTheIsolationDirectoryIsOwnerOnlyAndAlwaysRemoved(IsolationCase):
    def setUp(self):
        super().setUp()
        self.npm_project("a")
        self.cargo_project("c")
        self.changed = ["a/package.json", "c/Cargo.toml"]

    def test_ac6_nothing_remains_after_success(self):
        result = self.scan(self.changed)
        self.assertFalse(result["skipped"], result)
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(2)

    def test_ac6_nothing_remains_after_a_tool_failure_without_output(self):
        self.configure("npm", "fail")
        self.configure("cargo-audit", "fail")
        result = self.scan(self.changed)
        self.assertEqual(result["skip_reason"], "cargo_empty_output+npm_empty_output")
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(2)

    def test_ac6_nothing_remains_after_malformed_output(self):
        self.configure("npm", "garbage")
        self.configure("cargo-audit", "garbage")
        result = self.scan(self.changed)
        self.assertEqual(result["skip_reason"], "cargo_unparseable_output+npm_unparseable_output")
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(2)

    def test_ac6_nothing_remains_after_an_undocumented_exit_status(self):
        self.configure("npm", "normal", NPM_CLEAN, exit_code=7)
        self.configure("cargo-audit", "normal", CARGO_CLEAN, exit_code=7)
        result = self.scan(self.changed)
        self.assertEqual(
            result["skip_reason"], "cargo_undocumented_exit_status+npm_undocumented_exit_status"
        )
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(2)

    def test_ac6_nothing_remains_after_a_timeout(self):
        self.configure("npm", "sleep")
        self.configure("cargo-audit", "sleep")
        with mock.patch.object(SCAN, "SCAN_TIMEOUT_SECONDS", 3):
            result = self.scan(self.changed)
        self.assertEqual(result["skip_reason"], "cargo_execution_failed+npm_execution_failed")
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(2)

    def test_ac6_nothing_remains_after_a_failure_in_the_middle_of_copying(self):
        real = SCAN._copy_input
        calls = []

        def fail_on_the_second_copy(source, destination):
            calls.append(destination)
            if len(calls) == 2:
                raise OSError(errno.ENOSPC, "no space left")
            return real(source, destination)

        with mock.patch.object(SCAN, "_copy_input", side_effect=fail_on_the_second_copy):
            result = self.scan(["a/package.json"])
        self.assertEqual(len(calls), 2)
        for destination in calls:
            self.assertTrue(inside(self.iso_tmp, destination), "a copy was not written under the temp parent")
        self.assertEqual(result["skip_reason"], "npm_isolation_failed")
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(0)

    def test_ac6_files_the_scanner_itself_left_behind_are_removed_too(self):
        self.configure("npm", "normal", NPM_CLEAN, litter=True)
        self.configure("cargo-audit", "normal", CARGO_CLEAN, litter=True)
        result = self.scan(self.changed)
        self.assertFalse(result["skipped"], result)
        littered = Path(str(self.record_path) + ".litter").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(littered), 2, "each scanner leaves a read-only tree behind")
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(2)

    def test_ac6_the_cwd_grants_nothing_to_group_or_other(self):
        self.scan(self.changed)
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(2)
        for record in self.launches():
            self.assertEqual(record["cwd_mode"] & 0o077, 0, oct(record["cwd_mode"]))
            for name, entry in record["entries"].items():
                self.assertEqual(entry["mode"] & 0o077, 0, f"{name} {oct(entry['mode'])}")

    def test_ac6_the_directory_is_owner_only_from_its_creation_not_by_the_umask(self):
        saved = os.umask(0)
        try:
            self.scan(self.changed)
        finally:
            os.umask(saved)
        records = self.launches()
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(record["cwd_mode"], 0o700)
            for name, entry in record["entries"].items():
                self.assertEqual(entry["mode"] & 0o077, 0, f"{name} {oct(entry['mode'])}")

    def test_ac6_no_group_after_the_first_sees_a_directory_left_by_an_earlier_one(self):
        self.npm_project("b")
        self.scan(["a/package.json", "b/package.json"])
        self.assertEveryLaunchRanFromTheTempParentAndLeftNothing(2)
        for record in self.launches("npm"):
            self.assertEqual(sorted(record["entries"]), ["package-lock.json", "package.json"])


class TestTheIsolationWorkspaceItself(IsolationCase):
    def setUp(self):
        super().setUp()
        self.npm_project("")
        self.real_root = os.path.realpath(self.root)

    def test_it_yields_a_directory_holding_exactly_the_inputs_and_removes_it_on_exit(self):
        with self.runner_environment():
            with SCAN.isolation_workspace("npm", self.real_root, self.real_root) as prepared:
                directory = Path(prepared.directory)
                self.assertTrue(directory.is_dir())
                self.assertFalse(inside(self.root, directory))
                self.assertEqual(sorted(p.name for p in directory.iterdir()), ["package-lock.json", "package.json"])
                self.assertEqual(
                    {role: Path(path).name for role, path in prepared.files.items()},
                    {"manifest": "package.json", "anchor": "package-lock.json"},
                )
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        self.assertFalse(directory.exists())

    def test_it_removes_the_directory_when_the_body_raises(self):
        with self.runner_environment():
            with self.assertRaises(RuntimeError):
                with SCAN.isolation_workspace("npm", self.real_root, self.real_root) as prepared:
                    directory = Path(prepared.directory)
                    raise RuntimeError("scanner blew up")
        self.assertFalse(directory.exists())
        self.assertNoIsolationDirectoryRemains()

    def test_a_failure_signal_carries_no_path(self):
        (self.root / "package-lock.json").unlink()
        with self.runner_environment():
            with self.assertRaises(SCAN.IsolationError) as caught:
                with SCAN.isolation_workspace("npm", self.real_root, self.real_root):
                    self.fail("the workspace must not be entered")
        self.assertEqual(caught.exception.args, ())
        self.assertNoIsolationDirectoryRemains()


# ---------------------------------------------------------------------------
# AC-7 (FR4, NFR1)
# ---------------------------------------------------------------------------

class TestBuildScanJobIsPureWithPreparedInputs(unittest.TestCase):
    PATCH_TARGETS = (
        "builtins.open",
        "io.open",
        "os.open",
        "os.system",
        "subprocess.Popen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_output",
    )

    @classmethod
    def setUpClass(cls):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        cls.entries = {e["ecosystem"]: e for e in registry["ecosystems"]}

    @contextlib.contextmanager
    def forbidden_entry_points(self):
        with contextlib.ExitStack() as stack:
            patched = [
                stack.enter_context(mock.patch(t, side_effect=AssertionError(f"{t} called")))
                for t in self.PATCH_TARGETS
            ]
            yield
            for target, patch in zip(self.PATCH_TARGETS, patched):
                self.assertEqual(patch.call_count, 0, f"{target} was called")

    def test_ac7_npm_and_cargo_jobs_are_built_without_opening_a_file_or_starting_a_process(self):
        with self.forbidden_entry_points():
            npm = SCAN.build_scan_job(
                self.entries["npm"], "services/api/package.json", "/not/there", "/x/npm",
                prepared_inputs=prepared_inputs("npm"),
            )
            cargo = SCAN.build_scan_job(
                self.entries["cargo"], "crates/a/Cargo.toml", "/not/there", "/x/cargo-audit",
                prepared_inputs=prepared_inputs("cargo"),
            )
        self.assertEqual(npm["cwd"], "/iso/npm")
        self.assertEqual(npm["argv"], ["/x/npm", "audit", "--json", "--workspaces=false"])
        self.assertEqual(npm["manifest"], "services/api/package.json")
        self.assertEqual(cargo["cwd"], "/iso/cargo")
        self.assertEqual(
            cargo["argv"], ["/x/cargo-audit", "audit", "--file", "/iso/cargo/Cargo.lock", "--json"]
        )
        self.assertEqual(cargo["manifest"], "crates/a/Cargo.toml")

    def test_ac7_the_paths_of_the_prepared_inputs_need_not_exist(self):
        self.assertFalse(os.path.exists("/iso"))
        job = SCAN.build_scan_job(
            self.entries["cargo"], "Cargo.toml", "/p", "/x/cargo-audit", prepared_inputs=prepared_inputs("cargo")
        )
        self.assertEqual(job["cwd"], "/iso/cargo")

    def test_ac7_an_npm_or_cargo_job_never_has_the_project_root_as_its_cwd(self):
        for name, manifest in (("npm", "package.json"), ("cargo", "Cargo.toml")):
            with self.subTest(ecosystem=name, prepared="absent"):
                with self.assertRaises(SCAN.JobConstructionError):
                    SCAN.build_scan_job(self.entries[name], manifest, "/proj", f"/x/{name}")
            with self.subTest(ecosystem=name, prepared="none"):
                with self.assertRaises(SCAN.JobConstructionError):
                    SCAN.build_scan_job(
                        self.entries[name], manifest, "/proj", f"/x/{name}", prepared_inputs=None
                    )

    def test_ac7_a_prepared_value_for_the_wrong_shape_is_rejected(self):
        with self.assertRaises(SCAN.JobConstructionError):
            SCAN.build_scan_job(
                self.entries["cargo"], "Cargo.toml", "/p", "/x/cargo-audit",
                prepared_inputs=SCAN.PreparedInputs(directory="/iso/cargo", files={}),
            )

    def test_ac7_the_target_is_still_validated_as_a_plain_project_relative_path(self):
        for target in ("/abs/package.json", "../package.json", "a\x00b/package.json"):
            with self.subTest(target=target):
                with self.assertRaises(SCAN.JobConstructionError):
                    SCAN.build_scan_job(
                        self.entries["npm"], target, "/proj", "/x/npm", prepared_inputs=prepared_inputs("npm")
                    )

    def test_ac7_pip_and_go_jobs_ignore_prepared_inputs(self):
        for name, manifest in (("pip", "requirements.txt"), ("go", "svc/go.mod")):
            with self.subTest(ecosystem=name):
                plain = SCAN.build_scan_job(self.entries[name], manifest, "/proj", f"/x/{name}")
                given = SCAN.build_scan_job(
                    self.entries[name], manifest, "/proj", f"/x/{name}", prepared_inputs=prepared_inputs("npm")
                )
                self.assertEqual(plain, given)
        self.assertEqual(
            SCAN.build_scan_job(self.entries["go"], "svc/go.mod", "/proj", "/x/go")["cwd"], "/proj/svc"
        )
        self.assertEqual(
            SCAN.build_scan_job(self.entries["pip"], "requirements.txt", "/proj", "/x/pip")["cwd"], "/proj"
        )


# ---------------------------------------------------------------------------
# AC-8 (FR10, FR11, FR13, NFR4)
# ---------------------------------------------------------------------------

class TestEnvironmentsAndPinsAreUnchanged(IsolationCase):
    def test_ac8_child_environments_carry_no_added_or_overridden_variable_and_home_is_unchanged(self):
        self.npm_project("a")
        self.cargo_project("c")
        self.scan(["a/package.json", "c/Cargo.toml"])
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        entries = {e["ecosystem"]: e for e in registry["ecosystems"]}
        for tool, name in (("npm", "npm"), ("cargo-audit", "cargo")):
            (record,) = self.launches(tool)
            expected = SCAN.build_child_env(entries[name], environ=self.run_environ)
            recorded = dict(record["env"])
            if "LC_CTYPE" not in expected:
                recorded.pop("LC_CTYPE", None)  # added by the interpreter's own C-locale coercion
            with self.subTest(ecosystem=name):
                self.assertEqual(recorded, expected)
                self.assertEqual(record["home"], str(self.home))

    def test_ac8_the_pin_table_holds_its_previous_values(self):
        self.assertEqual(
            SCAN.ECOSYSTEM_ENV_PINS,
            {
                "npm": {
                    "npm_config_registry": "https://registry.npmjs.org/",
                    "npm_config_userconfig": os.devnull,
                },
                "cargo": {},
                "pip": {"PIP_CONFIG_FILE": os.devnull, "PIP_INDEX_URL": "https://pypi.org/simple/"},
                "go": {
                    "GOENV": "off",
                    "GOWORK": "off",
                    "GOFLAGS": "-mod=readonly",
                    "GOPROXY": "https://proxy.golang.org,direct",
                },
            },
        )

    def test_ac8_jobs_carry_the_runners_home_as_is(self):
        registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
        entries = {e["ecosystem"]: e for e in registry["ecosystems"]}
        environ = {"PATH": "/usr/bin", "HOME": "/home/reviewer", "TMPDIR": "/t"}
        for name, manifest in (("npm", "package.json"), ("cargo", "Cargo.toml")):
            job = SCAN.build_scan_job(
                entries[name], manifest, "/proj", f"/x/{name}", environ=environ,
                prepared_inputs=prepared_inputs(name),
            )
            self.assertEqual(job["env"]["HOME"], "/home/reviewer")
            self.assertEqual(
                set(job["env"]), {"PATH", "HOME", "TMPDIR"} | set(SCAN.ECOSYSTEM_ENV_PINS[name])
            )


def _function_docstring(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_docstring(node) or ""
    raise AssertionError(f"no function {name}")


def _comment_block_above(lines, marker_regex):
    """The consecutive `#` comment lines immediately above the first line
    matching `marker_regex`."""
    index = next(i for i, line in enumerate(lines) if re.match(marker_regex, line))
    block = []
    i = index - 1
    while i >= 0 and lines[i].lstrip().startswith("#"):
        block.append(lines[i])
        i -= 1
    return "\n".join(reversed(block))


# (npm | cargo) ... run / launched ... in / inside ... the project root / directory
STALE_CWD_DESCRIPTION = re.compile(
    r"\b(npm|cargo)\b[^.]{0,80}?\b(run|runs|launched|started)\b[^.]{0,40}?\b(in|inside)\b"
    r"[^.]{0,30}?\bproject (root|directory)\b",
    re.IGNORECASE | re.DOTALL,
)


class TestTheNewExecutionLocationIsDocumented(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        cls.lines = source.splitlines()
        tree = ast.parse(source)
        cls.docs = {
            name: _function_docstring(tree, name)
            for name in ("build_scan_job", "run_ecosystem_command", "_scan_bound_group", "run_scan")
        }
        cls.pins_comment = _comment_block_above(cls.lines, r"^ECOSYSTEM_ENV_PINS = ")
        cls.bound_comment = _comment_block_above(cls.lines, r"^PROJECT_BOUND_ECOSYSTEMS = ")
        yaml_lines = REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
        cls.yaml_lines = yaml_lines
        start = next(i for i, line in enumerate(yaml_lines) if line.strip() == "- ecosystem: cargo")
        end = next(i for i in range(start + 1, len(yaml_lines)) if yaml_lines[i].strip().startswith("- ecosystem:"))
        cls.cargo_yaml = "\n".join(yaml_lines[start:end])

    def test_ac8_build_scan_job_describes_the_prepared_input_and_its_purity(self):
        doc = self.docs["build_scan_job"]
        self.assertIn("isolation directory", doc)
        self.assertIn("prepared_inputs", doc)
        self.assertRegex(doc, r"(?i)\bpure\b|reads and writes no file|opens no file")

    def test_ac8_run_ecosystem_command_describes_the_isolation_directory_cwd(self):
        self.assertIn("isolation directory", self.docs["run_ecosystem_command"])

    def test_ac8_scan_bound_group_describes_preparation_removal_and_failure_mapping(self):
        doc = self.docs["_scan_bound_group"]
        self.assertIn("isolation directory", doc)
        self.assertRegex(doc, r"(?i)\bremov")
        self.assertIn("_isolation_failed", doc)

    def test_ac8_run_scan_names_both_isolation_reason_tokens(self):
        doc = self.docs["run_scan"]
        self.assertIn("npm_isolation_failed", doc)
        self.assertIn("cargo_isolation_failed", doc)
        self.assertIn("isolation directory", doc)

    def test_ac8_the_pin_comment_states_the_isolation_directory_and_the_trusted_scope(self):
        comment = self.pins_comment
        self.assertIn("isolation directory", comment)
        for term in ("HOME", "globalconfig", "audit.toml", "advisory"):
            self.assertIn(term, comment)

    def test_ac8_the_cargo_registry_comment_describes_isolation_directory_execution(self):
        self.assertIn("isolation directory", self.cargo_yaml)
        self.assertIn("--file", self.cargo_yaml)

    def test_ac8_none_of_them_still_describes_the_project_root_as_the_npm_or_cargo_cwd(self):
        texts = dict(self.docs)
        texts["ECOSYSTEM_ENV_PINS comment"] = self.pins_comment
        texts["PROJECT_BOUND_ECOSYSTEMS comment"] = self.bound_comment
        texts["vuln-scanners.yaml cargo entry"] = self.cargo_yaml
        for where, text in texts.items():
            with self.subTest(where=where):
                self.assertIsNone(STALE_CWD_DESCRIPTION.search(text), STALE_CWD_DESCRIPTION.search(text))


# ---------------------------------------------------------------------------
# build_scan_jobs keeps its grouping contract (it never prepares anything).
# ---------------------------------------------------------------------------

class TestBuildScanJobsNeedsThePreparedInputsOfNpmAndCargoGroups(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        bin_dir = Path(self._tmp.name) / "bin"
        bin_dir.mkdir()
        for name in ("npm", "cargo-audit", "govulncheck"):
            stub = bin_dir / name
            stub.write_text(f"#!{sys.executable}\n", encoding="utf-8")
            stub.chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"PATH": str(bin_dir)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)

    def test_jobs_of_npm_and_cargo_groups_run_in_the_prepared_directories(self):
        prepared = {
            "a/package.json": prepared_inputs("npm"),
            "Cargo.toml": prepared_inputs("cargo"),
        }
        jobs, reasons = SCAN.build_scan_jobs(
            self.registry, ["a/package.json", "Cargo.toml"], "/proj", prepared_inputs=prepared
        )
        self.assertEqual(reasons, [])
        self.assertEqual([(j["ecosystem"], j["cwd"]) for j in jobs], [("npm", "/iso/npm"), ("cargo", "/iso/cargo")])
        self.assertEqual([j["manifest"] for j in jobs], ["a/package.json", "Cargo.toml"])

    def test_a_group_without_prepared_inputs_yields_no_job_with_the_project_root_as_cwd(self):
        with self.assertRaises(SCAN.JobConstructionError):
            SCAN.build_scan_jobs(self.registry, ["package.json"], "/proj")

    def test_go_jobs_need_no_prepared_inputs(self):
        jobs, reasons = SCAN.build_scan_jobs(self.registry, ["svc/go.mod"], "/proj")
        self.assertEqual(reasons, [])
        self.assertEqual([j["cwd"] for j in jobs], ["/proj/svc"])


# ---------------------------------------------------------------------------
# NFR4: imports of this module.
# ---------------------------------------------------------------------------

class TestThisModuleUsesOnlyTheStandardLibrary(unittest.TestCase):
    def test_imports_are_standard_library_only(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
        self.assertEqual({m for m in modules if m not in sys.stdlib_module_names}, set())
        self.assertFalse({m for m in modules if m.startswith("test_")})


if __name__ == "__main__":
    unittest.main()
