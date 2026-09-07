"""Tests for task0001 (review-sca-axis): the SCA registry document, and
`scan-dependencies.py`'s `scan` subcommand (ecosystem selection, command
assembly, per-tool normalization, threshold, truncation, determinism and
read-only discipline).

Covers task0001 Acceptance Criteria
(feature-docs/review-sca-axis/tasks/task0001.md):

- AC-1: em-workflow/references/vuln-scanners.yaml exists, carries a
  `version` key and a responsibility-split header comment, and holds for
  each of npm / cargo / pip / go: the selecting manifest filenames, the
  executable, the machine-readable argument form, the severity mapping,
  and the two threshold facts (direct-only, high-and-above).
- AC-2: ecosystem selection and command assembly from a changed-file list
  containing package.json / Cargo.toml / pyproject.toml / requirements.txt
  / go.mod, taking both the tool name and the arguments from the registry.
- AC-3: a representative machine-readable output sample from each of the
  four tools normalizes into a review-output-schema.json-conformant object
  (`source: "tool"`, every finding `category: "vulnerability"`, no property
  outside the schema).
- AC-4: transitive-dependency advisories and below-high-severity advisories
  are absent from `findings` for a sample containing both, dropped at
  normalization time (the objects never exist).
- AC-5: with the ecosystem's executable not resolvable on PATH, the result
  is `skipped: true` with a machine-stable `skip_reason`, `findings` empty,
  no fallback of any kind.
- AC-6: an advisory-sourced field over 4096 bytes truncates with a visible
  marker; no `suggestion` ever carries diff hunk markers.
- AC-7: running `scan` twice over the same inputs yields byte-identical
  output, and a scan leaves the project root's tracked/untracked file
  state unchanged.
- AC-10: scan-dependencies.py registers both `scan` and `file-tasks`;
  `file-tasks` is the marked placeholder.

Per Test Notes / IMPLEMENTATION.md Conventions: this module's own imports
stay standard-library only (NFR7) -- the script under test is loaded by
file path (its name contains a hyphen), following
tests/test_validate_worker_output.py's pattern; the script's own PyYAML
import is transitive and does not breach NFR7. `vuln-scanners.yaml` is
independently parsed here with a hand-rolled, restricted-subset parser
(never PyYAML in this module's own imports), matching
tests/test_reviewers_primary_chains.py's convention -- this is a document
check independent of the script's own (real) PyYAML-based parsing
exercised by the scan-flow tests below. Schema conformance is checked by a
structural assertion written directly against the schema document, not a
third-party validator. The execution boundary (tool resolution + subprocess
invocation) is exercised by pointing PATH at a temporary directory: empty
for AC-5, holding a stand-in executable that prints a fixture for AC-3/
AC-4/AC-6/AC-7.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "em-workflow" / "references" / "vuln-scanners.yaml"
SCHEMA_PATH = REPO_ROOT / "em-workflow" / "references" / "review-output-schema.json"
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("scan_dependencies", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_module()


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# AC-1: vuln-scanners.yaml structural check -- a hand-rolled, restricted-
# subset parser local to this test module (never PyYAML in this module's
# own imports), matching tests/test_reviewers_primary_chains.py.
# ---------------------------------------------------------------------------

def _parse_flow_list(value):
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"expected a flow list, got: {value!r}")
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [item.strip() for item in inner.split(",")]


def _parse_flow_mapping(value):
    if not (value.startswith("{") and value.endswith("}")):
        raise ValueError(f"expected a flow mapping, got: {value!r}")
    inner = value[1:-1].strip()
    result = {}
    if not inner:
        return result
    for part in inner.split(","):
        k, _, v = part.partition(":")
        result[k.strip()] = v.strip()
    return result


def parse_vuln_scanners_yaml(text):
    """Restricted-subset parser for vuln-scanners.yaml's `ecosystems:` list.
    Returns a list of per-ecosystem dicts. Raises ValueError if no
    top-level `ecosystems:` key is found or a line inside the block
    violates the expected nesting."""
    lines = text.splitlines()
    ecosystems = []
    in_block = False
    saw_block = False
    current = None

    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not in_block:
            if line == "ecosystems:":
                in_block = True
                saw_block = True
            continue
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            break  # dedent back to column 0: the ecosystems block ended

        if indent == 2:
            if not stripped.startswith("- ecosystem:"):
                raise ValueError(f"expected an ecosystem list item, got: {raw!r}")
            current = {"ecosystem": stripped[len("- ecosystem:"):].strip()}
            ecosystems.append(current)
            continue

        if current is None:
            raise ValueError(f"attribute line before any ecosystem: {raw!r}")

        if indent != 4:
            raise ValueError(f"unexpected indentation: {raw!r}")

        key, sep, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not sep:
            raise ValueError(f"malformed line: {raw!r}")
        if value.startswith("["):
            current[key] = _parse_flow_list(value)
        elif value.startswith("{"):
            current[key] = _parse_flow_mapping(value)
        else:
            current[key] = value

    if not saw_block:
        raise ValueError("no top-level `ecosystems:` key found")
    return ecosystems


EXPECTED_MANIFESTS = {
    "npm": ["package.json"],
    "cargo": ["Cargo.toml"],
    "pip": ["pyproject.toml", "requirements.txt"],
    "go": ["go.mod"],
}
EXPECTED_EXECUTABLES = {
    "npm": "npm",
    "cargo": "cargo",
    "pip": "pip-audit",
    "go": "govulncheck",
}


class TestVulnScannersRegistryStructure(unittest.TestCase):
    """AC-1: the registry document's own content, independent of the
    script's (real) PyYAML-based parsing."""

    @classmethod
    def setUpClass(cls):
        cls.text = REGISTRY_PATH.read_text(encoding="utf-8")
        cls.ecosystems = parse_vuln_scanners_yaml(cls.text)
        cls.by_name = {e["ecosystem"]: e for e in cls.ecosystems}

    def test_registry_file_exists(self):
        self.assertTrue(REGISTRY_PATH.is_file())

    def test_version_key_present(self):
        self.assertRegex(self.text, r"(?m)^version:\s*\d+\s*$")

    def test_header_states_responsibility_split(self):
        header = self.text.split("\nversion:", 1)[0]
        normalized = re.sub(r"\s+", " ", header.replace("#", "")).lower()
        self.assertIn("this registry owns which tool serves each manifest", normalized)
        self.assertIn("scan-dependencies.py owns how to run", normalized)
        self.assertIn("how to normalize", normalized)

    def test_parses_without_error(self):
        self.assertIsInstance(self.ecosystems, list)
        self.assertGreater(len(self.ecosystems), 0)

    def test_exactly_four_expected_ecosystems(self):
        self.assertEqual(set(self.by_name), set(EXPECTED_MANIFESTS))

    def test_manifests_per_ecosystem(self):
        for name, manifests in EXPECTED_MANIFESTS.items():
            with self.subTest(ecosystem=name):
                self.assertEqual(self.by_name[name]["manifests"], manifests)

    def test_executable_per_ecosystem(self):
        for name, exe in EXPECTED_EXECUTABLES.items():
            with self.subTest(ecosystem=name):
                self.assertEqual(self.by_name[name]["executable"], exe)

    def test_args_is_non_empty_list_per_ecosystem(self):
        for name, entry in self.by_name.items():
            with self.subTest(ecosystem=name):
                self.assertIsInstance(entry["args"], list)
                self.assertTrue(entry["args"])

    def test_severity_map_maps_critical_and_high(self):
        for name, entry in self.by_name.items():
            with self.subTest(ecosystem=name):
                self.assertEqual(entry["severity_map"].get("critical"), "critical")
                self.assertEqual(entry["severity_map"].get("high"), "high")

    def test_threshold_direct_only_and_high_floor(self):
        for name, entry in self.by_name.items():
            with self.subTest(ecosystem=name):
                self.assertEqual(entry["threshold"].get("direct_only"), "true")
                self.assertEqual(entry["threshold"].get("min_severity"), "high")


class TestVulnScannersParserDetectsMalformedInput(unittest.TestCase):
    """Regression proof (tdd-testing discipline): the parser above must be
    able to fail, not just succeed on well-formed input."""

    def test_missing_ecosystems_key_raises(self):
        with self.assertRaises(ValueError):
            parse_vuln_scanners_yaml("version: 1\n")

    def test_malformed_list_item_raises(self):
        with self.assertRaises(ValueError):
            parse_vuln_scanners_yaml("ecosystems:\n  - not_ecosystem: npm\n")


# ---------------------------------------------------------------------------
# AC-2 (TS-1): ecosystem selection + command assembly from the real
# registry, via the script's own (real) load_registry/select_ecosystems/
# build_command.
# ---------------------------------------------------------------------------

class TestEcosystemSelectionAndCommandAssembly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)

    def test_selects_all_four_ecosystems_from_changed_files(self):
        changed = [
            "package.json",
            "Cargo.toml",
            "pyproject.toml",
            "requirements.txt",
            "go.mod",
        ]
        selected = SCAN.select_ecosystems(self.registry, changed)
        self.assertEqual({e["ecosystem"] for e in selected}, {"npm", "cargo", "pip", "go"})

    def test_command_assembled_from_registry_tool_and_args(self):
        changed = [
            "package.json",
            "Cargo.toml",
            "pyproject.toml",
            "requirements.txt",
            "go.mod",
        ]
        selected = {e["ecosystem"]: e for e in SCAN.select_ecosystems(self.registry, changed)}
        expected_commands = {
            "npm": ["npm", "audit", "--json"],
            "cargo": ["cargo", "audit", "--json"],
            "pip": ["pip-audit", "--format", "json"],
            "go": ["govulncheck", "-json", "./..."],
        }
        for name, expected_cmd in expected_commands.items():
            with self.subTest(ecosystem=name):
                self.assertEqual(SCAN.build_command(selected[name]), expected_cmd)

    def test_no_manifest_in_change_selects_nothing(self):
        selected = SCAN.select_ecosystems(self.registry, ["README.md", "src/app.py"])
        self.assertEqual(selected, [])

    def test_pip_selected_by_either_pyproject_or_requirements(self):
        for changed in (["pyproject.toml"], ["requirements.txt"]):
            with self.subTest(changed=changed):
                selected = SCAN.select_ecosystems(self.registry, changed)
                self.assertEqual({e["ecosystem"] for e in selected}, {"pip"})

    def test_no_manifest_in_change_yields_empty_non_skipped_result(self):
        result = SCAN.run_scan(Path("."), ["README.md"], SCAN.DEFAULT_REGISTRY_PATH)
        self.assertEqual(result["findings"], [])
        self.assertFalse(result["skipped"])
        self.assertIsNone(result["skip_reason"])
        self.assertEqual(result["source"], "tool")


# ---------------------------------------------------------------------------
# Representative machine-readable output fixtures (AC-3/AC-4). Each sample
# contains one advisory that clears the threshold (kept) and at least one
# that does not (dropped: transitive, or below high severity), per Test
# Notes' "a sample that contains both".
# ---------------------------------------------------------------------------

NPM_FIXTURE = {
    "vulnerabilities": {
        "lodash": {
            "name": "lodash",
            "severity": "critical",
            "isDirect": True,
            "range": "<4.17.21",
            "fixAvailable": {"name": "lodash", "version": "4.17.21"},
            "via": [
                {
                    "source": 1096742,
                    "name": "lodash",
                    "title": "Prototype Pollution in lodash",
                    "url": "https://github.com/advisories/GHSA-p6mc-m468-83gw",
                    "severity": "critical",
                    "range": "<4.17.21",
                }
            ],
        },
        "minimist": {
            "name": "minimist",
            "severity": "critical",
            "isDirect": False,
            "range": "<1.2.6",
            "fixAvailable": True,
            "via": [
                {
                    "source": 1097682,
                    "name": "minimist",
                    "title": "Prototype Pollution in minimist",
                    "url": "https://github.com/advisories/GHSA-xvch-5gv4-984h",
                    "severity": "critical",
                    "range": "<1.2.6",
                }
            ],
        },
        "qs": {
            "name": "qs",
            "severity": "moderate",
            "isDirect": True,
            "range": "<6.10.3",
            "fixAvailable": {"name": "qs", "version": "6.10.3"},
            "via": [
                {
                    "source": 1000001,
                    "name": "qs",
                    "title": "Denial of Service in qs",
                    "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc",
                    "severity": "moderate",
                    "range": "<6.10.3",
                }
            ],
        },
    }
}

CARGO_FIXTURE = {
    "vulnerabilities": {
        "found": True,
        "list": [
            {
                "advisory": {
                    "id": "RUSTSEC-2023-0001",
                    "title": "Integer overflow in foo",
                    "description": "A crafted input can cause an integer overflow leading to a panic.",
                    "url": "https://rustsec.org/advisories/RUSTSEC-2023-0001",
                },
                "package": {"name": "foo", "version": "1.0.0"},
                "versions": {"patched": [">=1.0.1"]},
                "severity": "high",
                "is_direct": True,
            },
            {
                "advisory": {
                    "id": "RUSTSEC-2023-0002",
                    "title": "Use-after-free in bar",
                    "description": "A transitive dependency has a use-after-free.",
                    "url": "https://rustsec.org/advisories/RUSTSEC-2023-0002",
                },
                "package": {"name": "bar", "version": "2.1.0"},
                "versions": {"patched": [">=2.2.0"]},
                "severity": "critical",
                "is_direct": False,
            },
            {
                "advisory": {
                    "id": "RUSTSEC-2023-0003",
                    "title": "Denial of service in baz",
                    "description": "A direct dependency has a medium-severity DoS.",
                    "url": "https://rustsec.org/advisories/RUSTSEC-2023-0003",
                },
                "package": {"name": "baz", "version": "0.5.0"},
                "versions": {"patched": [">=0.5.1"]},
                "severity": "medium",
                "is_direct": True,
            },
        ],
    }
}

PIP_FIXTURE = {
    "dependencies": [
        {
            "name": "django",
            "version": "3.2.0",
            "direct": True,
            "vulns": [
                {
                    "id": "PYSEC-2021-9",
                    "fix_versions": ["3.2.1"],
                    "description": "SQL injection in QuerySet.",
                    "severity": "critical",
                }
            ],
        },
        {
            "name": "urllib3",
            "version": "1.26.0",
            "direct": False,
            "vulns": [
                {
                    "id": "PYSEC-2021-10",
                    "fix_versions": ["1.26.5"],
                    "description": "A transitive dependency has a high-severity issue.",
                    "severity": "high",
                }
            ],
        },
        {
            "name": "requests",
            "version": "2.25.0",
            "direct": True,
            "vulns": [
                {
                    "id": "PYSEC-2021-11",
                    "fix_versions": ["2.25.1"],
                    "description": "A direct dependency has a low-severity issue.",
                    "severity": "low",
                }
            ],
        },
    ]
}

GO_FIXTURE = {
    "vulns": [
        {
            "osv": {
                "id": "GO-2023-1234",
                "summary": "Improper validation in golang.org/x/net",
                "details": "A crafted header can bypass validation.",
                "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "0.10.0"}]}]}],
            },
            "package": "golang.org/x/net",
            "severity": "high",
            "is_direct": True,
        },
        {
            "osv": {
                "id": "GO-2023-5678",
                "summary": "Panic in golang.org/x/text",
                "details": "A transitive dependency can panic on malformed input.",
                "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "0.5.0"}]}]}],
            },
            "package": "golang.org/x/text",
            "severity": "critical",
            "is_direct": False,
        },
        {
            "osv": {
                "id": "GO-2023-9012",
                "summary": "Minor info leak in golang.org/x/sys",
                "details": "A direct dependency leaks minor info at medium severity.",
                "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "0.3.0"}]}]}],
            },
            "package": "golang.org/x/sys",
            "severity": "medium",
            "is_direct": True,
        },
    ]
}


def _write_stub(bin_dir, name, fixture):
    """Writes an executable named `name` into `bin_dir` that always prints
    `fixture` (already JSON-encoded once here, in this module's own stdlib
    `json` import) verbatim to stdout, ignoring argv -- a stand-in for the
    real SCA tool (Test Notes: "a stand-in executable that prints a
    fixture")."""
    # The shebang uses sys.executable's absolute path rather than
    # `/usr/bin/env python3` -- these tests deliberately restrict PATH to
    # `bin_dir` alone (so only the stub resolves as the ecosystem's tool),
    # and `env` would otherwise fail to find `python3` under that
    # restricted PATH when the OS invokes the shebang interpreter.
    payload = json.dumps(fixture)
    script = bin_dir / name
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f"sys.stdout.write({payload!r})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def assert_conforms_to_schema(testcase, obj, schema):
    """Structural assertion against review-output-schema.json -- not a
    third-party validator (Test Notes)."""
    root_props = schema["properties"]
    for key in schema["required"]:
        testcase.assertIn(key, obj, f"missing required root key {key!r}")
    if schema.get("additionalProperties") is False:
        extra = set(obj) - set(root_props)
        testcase.assertFalse(extra, f"unexpected root keys: {extra}")
    testcase.assertIn(obj["source"], root_props["source"]["enum"])
    testcase.assertIsInstance(obj["findings"], list)
    testcase.assertIsInstance(obj["summary"], str)
    testcase.assertIsInstance(obj["skipped"], bool)
    if obj["skipped"]:
        testcase.assertIsInstance(obj["skip_reason"], str)
    else:
        testcase.assertIsNone(obj["skip_reason"])

    finding_schema = root_props["findings"]["items"]
    finding_props = finding_schema["properties"]
    for finding in obj["findings"]:
        for key in finding_schema["required"]:
            testcase.assertIn(key, finding, f"finding missing required key {key!r}")
        if finding_schema.get("additionalProperties") is False:
            extra = set(finding) - set(finding_props)
            testcase.assertFalse(extra, f"unexpected finding keys: {extra}")
        testcase.assertIn(finding["category"], finding_props["category"]["enum"])
        testcase.assertIn(finding["severity"], finding_props["severity"]["enum"])
        testcase.assertIsInstance(finding["title"], str)
        testcase.assertIsInstance(finding["description"], str)
        testcase.assertIsInstance(finding["suggestion"], str)
        testcase.assertIsInstance(finding["file"], str)
        testcase.assertTrue(finding["line"] is None or isinstance(finding["line"], int))
        testcase.assertTrue(finding["line_end"] is None or isinstance(finding["line_end"], int))


def _run_scan_with_stub(tool_name, fixture, changed_files):
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp) / "project"
        project_root.mkdir()
        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir()
        _write_stub(bin_dir, tool_name, fixture)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
            return SCAN.run_scan(project_root, changed_files, SCAN.DEFAULT_REGISTRY_PATH)


class TestNormalizationProducesSchemaConformantResult(unittest.TestCase):
    """AC-3 (TS-2): each of the four tools' representative fixture
    normalizes into a schema-conformant object. AC-4 (TS-3): the
    transitive-dependency / below-high-severity advisory in each fixture
    never appears in `findings`."""

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()

    def test_npm_sample_normalizes_and_conforms(self):
        result = _run_scan_with_stub("npm", NPM_FIXTURE, ["package.json"])
        assert_conforms_to_schema(self, result, self.schema)
        self.assertEqual(result["source"], "tool")
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["category"], "vulnerability")
        self.assertEqual(finding["severity"], "critical")
        self.assertTrue(finding["title"].startswith("lodash: GHSA-p6mc-m468-83gw"))
        self.assertEqual(finding["file"], "package.json")

    def test_npm_transitive_and_below_threshold_dropped(self):
        result = _run_scan_with_stub("npm", NPM_FIXTURE, ["package.json"])
        titles = " ".join(f["title"] for f in result["findings"])
        self.assertNotIn("minimist", titles)
        self.assertNotIn("qs:", titles)

    def test_cargo_sample_normalizes_and_conforms(self):
        result = _run_scan_with_stub("cargo", CARGO_FIXTURE, ["Cargo.toml"])
        assert_conforms_to_schema(self, result, self.schema)
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["severity"], "high")
        self.assertTrue(finding["title"].startswith("foo: RUSTSEC-2023-0001"))
        self.assertEqual(finding["file"], "Cargo.toml")

    def test_cargo_transitive_and_below_threshold_dropped(self):
        result = _run_scan_with_stub("cargo", CARGO_FIXTURE, ["Cargo.toml"])
        titles = " ".join(f["title"] for f in result["findings"])
        self.assertNotIn("bar:", titles)
        self.assertNotIn("baz:", titles)

    def test_pip_sample_normalizes_and_conforms(self):
        result = _run_scan_with_stub("pip-audit", PIP_FIXTURE, ["pyproject.toml"])
        assert_conforms_to_schema(self, result, self.schema)
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["severity"], "critical")
        self.assertTrue(finding["title"].startswith("django: PYSEC-2021-9"))
        self.assertEqual(finding["file"], "pyproject.toml")

    def test_pip_transitive_and_below_threshold_dropped(self):
        result = _run_scan_with_stub("pip-audit", PIP_FIXTURE, ["pyproject.toml"])
        titles = " ".join(f["title"] for f in result["findings"])
        self.assertNotIn("urllib3", titles)
        self.assertNotIn("requests", titles)

    def test_go_sample_normalizes_and_conforms(self):
        result = _run_scan_with_stub("govulncheck", GO_FIXTURE, ["go.mod"])
        assert_conforms_to_schema(self, result, self.schema)
        self.assertEqual(len(result["findings"]), 1)
        finding = result["findings"][0]
        self.assertEqual(finding["severity"], "high")
        self.assertTrue(finding["title"].startswith("golang.org/x/net: GO-2023-1234"))
        self.assertEqual(finding["file"], "go.mod")

    def test_go_transitive_and_below_threshold_dropped(self):
        result = _run_scan_with_stub("govulncheck", GO_FIXTURE, ["go.mod"])
        titles = " ".join(f["title"] for f in result["findings"])
        self.assertNotIn("x/text", titles)
        self.assertNotIn("x/sys", titles)


# ---------------------------------------------------------------------------
# AC-5 (TS-4): the ecosystem's tool is not resolvable on PATH.
# ---------------------------------------------------------------------------

class TestToolNotResolvableIsSkip(unittest.TestCase):
    def test_missing_npm_executable_yields_skip_with_empty_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            empty_bin = Path(tmp) / "empty-bin"
            empty_bin.mkdir()
            with mock.patch.dict(os.environ, {"PATH": str(empty_bin)}, clear=False):
                result = SCAN.run_scan(
                    project_root, ["package.json"], SCAN.DEFAULT_REGISTRY_PATH
                )
        self.assertTrue(result["skipped"])
        self.assertIsInstance(result["skip_reason"], str)
        self.assertIn("npm", result["skip_reason"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["source"], "tool")

    def test_skip_reason_is_machine_stable_identifier(self):
        # Called twice with the same (missing-tool) inputs -> identical
        # skip_reason, proving it is a stable identifier, not e.g. a
        # timestamp or a randomly-ordered string.
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            empty_bin = Path(tmp) / "empty-bin"
            empty_bin.mkdir()
            with mock.patch.dict(os.environ, {"PATH": str(empty_bin)}, clear=False):
                r1 = SCAN.run_scan(project_root, ["package.json"], SCAN.DEFAULT_REGISTRY_PATH)
                r2 = SCAN.run_scan(project_root, ["package.json"], SCAN.DEFAULT_REGISTRY_PATH)
        self.assertEqual(r1["skip_reason"], r2["skip_reason"])


# ---------------------------------------------------------------------------
# AC-6 (TS-20): untrusted-text truncation.
# ---------------------------------------------------------------------------

class TestUntrustedTextTruncation(unittest.TestCase):
    def test_long_advisory_title_is_truncated_with_marker(self):
        long_title = "A" * 5000
        fixture = {
            "vulnerabilities": {
                "evilpkg": {
                    "name": "evilpkg",
                    "severity": "critical",
                    "isDirect": True,
                    "range": "*",
                    "fixAvailable": {"name": "evilpkg", "version": "9.9.9"},
                    "via": [
                        {
                            "source": 1,
                            "name": "evilpkg",
                            "title": long_title,
                            "url": "https://github.com/advisories/GHSA-zzzz-zzzz-zzzz",
                            "severity": "critical",
                            "range": "*",
                        }
                    ],
                }
            }
        }
        result = _run_scan_with_stub("npm", fixture, ["package.json"])
        self.assertEqual(len(result["findings"]), 1)
        title = result["findings"][0]["title"]
        self.assertLessEqual(len(title.encode("utf-8")), SCAN.UNTRUSTED_TEXT_MAX_BYTES)
        self.assertIn(SCAN.TRUNCATION_MARKER, title)
        self.assertLess(len(title), len(long_title))

    def test_suggestion_is_prose_never_diff_shaped(self):
        result = _run_scan_with_stub("npm", NPM_FIXTURE, ["package.json"])
        self.assertTrue(result["findings"])
        for finding in result["findings"]:
            for marker in ("--- ", "+++ ", "@@ ", "diff --git"):
                self.assertNotIn(marker, finding["suggestion"])

    def test_truncate_helper_never_exceeds_limit_and_marks_visibly(self):
        # `truncate_untrusted` is the shared helper both `scan` (this task)
        # and `file-tasks` (task0005) use -- IMPLEMENTATION.md's single-
        # helper contract, adopted verbatim from task0005's file rather
        # than duplicated.
        truncated = SCAN.truncate_untrusted("B" * 10000)
        self.assertLessEqual(len(truncated.encode("utf-8")), SCAN.UNTRUSTED_TEXT_MAX_BYTES)
        self.assertIn(SCAN.TRUNCATION_MARKER, truncated)

    def test_truncate_helper_leaves_short_text_untouched(self):
        self.assertEqual(SCAN.truncate_untrusted("short text"), "short text")


# ---------------------------------------------------------------------------
# AC-7 (TS-19): determinism and read-only discipline.
# ---------------------------------------------------------------------------

class TestDeterminismAndReadOnlyDiscipline(unittest.TestCase):
    def test_repeated_scan_yields_byte_identical_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", NPM_FIXTURE)
            with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
                r1 = SCAN.run_scan(project_root, ["package.json"], SCAN.DEFAULT_REGISTRY_PATH)
                r2 = SCAN.run_scan(project_root, ["package.json"], SCAN.DEFAULT_REGISTRY_PATH)
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))

    def test_scan_leaves_project_root_file_state_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=project_root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "t@example.com"], cwd=project_root, check=True
            )
            subprocess.run(["git", "config", "user.name", "t"], cwd=project_root, check=True)
            (project_root / "package.json").write_text("{}\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=project_root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=project_root, check=True)

            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", NPM_FIXTURE)

            before = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
                SCAN.run_scan(project_root, ["package.json"], SCAN.DEFAULT_REGISTRY_PATH)

            after = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# AC-10: co-ownership skeleton -- both subcommands registered. task0005's
# real `file-tasks` implementation was already on the integration branch
# when this task merged; the parent-side-adoption protocol
# (worktree-task-workflow) adopted that file wholesale and re-applied only
# this task's `scan` half on top, so neither subcommand is a placeholder in
# the merged file (task0005's own tests/test_sca_task_filing.py -- not
# duplicated here -- is what proves `file-tasks` itself still passes).
# ---------------------------------------------------------------------------

class TestCoOwnershipSkeleton(unittest.TestCase):
    def test_both_subcommands_registered(self):
        parser = SCAN.build_parser()
        subparsers_actions = [
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ]
        self.assertTrue(subparsers_actions)
        choices = subparsers_actions[0].choices
        self.assertIn("scan", choices)
        self.assertIn("file-tasks", choices)

    def test_scan_is_a_real_implementation_not_a_placeholder(self):
        # Directly proves `scan_command` does real normalization work
        # rather than raising the "implemented by the other task"
        # placeholder ExecutionError a not-yet-merged half would.
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            changed_files_path = Path(tmp) / "changed.json"
            changed_files_path.write_text(json.dumps(["README.md"]), encoding="utf-8")
            args = argparse.Namespace(
                project_root=str(project_root),
                changed_files=str(changed_files_path),
                registry=None,
            )
            result = SCAN.scan_command(args)
        self.assertEqual(result["source"], "tool")
        self.assertFalse(result["skipped"])

    def test_file_tasks_still_dispatches_to_its_own_real_command(self):
        # AC-10's merge-keeps-the-other-real-half guarantee, checked at the
        # dispatch-wiring level (not re-testing file_tasks's own behavior,
        # which is tests/test_sca_task_filing.py's job): the `file-tasks`
        # subparser's registered callback is task0005's real
        # `file_tasks_command`, not this task's placeholder mechanism.
        parser = SCAN.build_parser()
        args = parser.parse_args(
            ["file-tasks", "--project-root", "x", "--feature", "y", "--findings", "z"]
        )
        self.assertIs(args.func, SCAN.file_tasks_command)


# ---------------------------------------------------------------------------
# CLI-level check: `scan` produces exactly one JSON object on stdout, exit 0.
# ---------------------------------------------------------------------------

class TestScanCliProducesOneObjectExitZero(unittest.TestCase):
    def test_scan_subcommand_end_to_end_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir()
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            _write_stub(bin_dir, "npm", NPM_FIXTURE)
            changed_files_path = Path(tmp) / "changed.json"
            changed_files_path.write_text(json.dumps(["package.json"]), encoding="utf-8")

            proc_env = dict(os.environ)
            proc_env["PATH"] = str(bin_dir)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "scan",
                    "--project-root",
                    str(project_root),
                    "--changed-files",
                    str(changed_files_path),
                ],
                capture_output=True,
                text=True,
                env=proc_env,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["source"], "tool")
        self.assertEqual(len(result["findings"]), 1)


if __name__ == "__main__":
    unittest.main()
