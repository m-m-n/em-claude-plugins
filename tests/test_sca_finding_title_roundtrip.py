"""Tests for sca-file-tasks-robustness task0001: every finding title the four
normalizers (pip, npm, cargo, go) produce is recoverable by
`recover_package_advisory`, even when the advisory's short-title source spans
several lines, so every scanned vulnerability reaches `file-tasks` as a task
or a report entry instead of being classified malformed.

Covers the task's Acceptance Criteria
(feature-docs/sca-file-tasks-robustness/tasks/task0001.md):

- AC-1: TestShortTitleWhitespaceCollapse -- LF, CRLF, TAB, U+2028 and U+3000
  (and the other line breaks / no-break spaces) in a short-title source are
  collapsed to single ASCII spaces, no line break survives, and the short
  title neither starts nor ends with whitespace, for each normalizer.
- AC-2: TestRecoveryAfterCollapse -- `recover_package_advisory` returns the
  advisory's original (package, advisory id) pair and
  `group_findings_by_package` reports no malformed entry; the same check is
  applied to every finding produced in the AC-3 and AC-4 tests.
- AC-3: TestPipHeadlineBeforeCvssVector -- a pip description with line
  breaks inside the prose before an embedded CVSS vector yields a one-line
  title without the vector text.
- AC-4: TestWhitespaceOnlyAndOverLongShortTitles -- a whitespace-only short
  title, an over-long one (cap and marker kept), and one that exceeds the cap
  only because of whitespace runs (collapse precedes truncation).
- AC-5: TestFileTasksRoundTrip -- the AC-1 findings of all four normalizers
  reach `file_tasks` as filed tasks (stand-in entry point) or report
  sections (no entry point), with no malformed finding.
- AC-6: TestWhitespaceInPackageOrAdvisoryStaysMalformed -- package names and
  advisory ids are not normalized; one that contains a line break is still
  classified malformed.
- AC-7: TestModuleImportsStandardLibraryOnly -- this module imports only the
  standard library.

Per Test Notes: each normalizer is driven through its own entry function with
a minimal payload in the shape it already reads, against the real registry
(default registry path). Directness: npm and cargo through the per-entry
direct flag, pip through a requirements file in a temporary project root,
go through a go.mod in a temporary project root. The external task system is
never contacted -- `--entry-point` is a recording stand-in executable. The
script under test is loaded by file path (its name contains a hyphen). Only
summary keys that exist before this feature are asserted (IMPLEMENTATION.md
D3), so the AC-5 tests pass whether or not the sibling task that adds a
summary key has merged.
"""

import ast
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("scan_dependencies_title_roundtrip", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCAN = _load_script()

_REGISTRY = SCAN.load_registry(SCAN.DEFAULT_REGISTRY_PATH)
ECOSYSTEMS = {entry["ecosystem"]: entry for entry in _REGISTRY["ecosystems"]}

NORMALIZERS = ("npm", "cargo", "pip", "go")

# One package and one advisory id per normalizer. Both are short and free of
# whitespace so the title cap only ever cuts the short title.
PACKAGES = {
    "npm": "left-pad",
    "cargo": "smallvec",
    "pip": "django",
    "go": "example.org/mod",
}
ADVISORY_IDS = {
    "npm": "GHSA-aaaa-bbbb-cccc",
    "cargo": "RUSTSEC-2024-0001",
    "pip": "PYSEC-2021-9",
    "go": "GO-2024-0001",
}

# CVSS 3.1 base score 7.5 -> band "high" (passes the threshold rule).
CVSS_HIGH = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"

# Every character a title must not contain once a finding is built.
LINE_BREAKS = "\n\r\x0b\x0c\x85\u2028\u2029"

# AC-1 short-title sources: LF, CRLF, TAB, U+2028 and U+3000, with runs and
# with leading / trailing whitespace. The expected collapsed text is below.
MIXED_WHITESPACE_SOURCE = (
    "\n\t Alpha \n\n Beta \r\n\t Gamma\t\tDelta\u2028 \u2028Epsilon\u3000\u3000Zeta \r\n"
)
MIXED_WHITESPACE_COLLAPSED = "Alpha Beta Gamma Delta Epsilon Zeta"
# The remaining line breaks and no-break spaces: VT, FF, NEL, NBSP, U+2029.
OTHER_WHITESPACE_SOURCE = "A\x0bB\x0cC\x85D\xa0E\u2029F"
OTHER_WHITESPACE_COLLAPSED = "A B C D E F"

SOURCES = (
    (MIXED_WHITESPACE_SOURCE, MIXED_WHITESPACE_COLLAPSED),
    (OTHER_WHITESPACE_SOURCE, OTHER_WHITESPACE_COLLAPSED),
)

# Description text carrying a line break; description and suggestion are not
# collapsed, so it must reach the finding's description verbatim.
DESCRIPTION_WITH_BREAK = "first line of detail\nsecond line of detail"


def _title_prefix(package, advisory_id):
    return f"{package}: {advisory_id} — "


class RoundTripCase(unittest.TestCase):
    """A temporary project root plus one `produce` entry per normalizer."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        self.write("requirements.txt", f"{PACKAGES['pip']}==3.2.0\n")
        self.write(
            "Cargo.toml",
            f'[package]\nname = "demo"\nversion = "0.1.0"\n\n[dependencies]\n{PACKAGES["cargo"]} = "1"\n',
        )
        self.write(
            "go.mod",
            f"module example.com/app\n\ngo 1.20\n\nrequire {PACKAGES['go']} v1.0.0\n",
        )

    def write(self, rel_path, text):
        (self.root / rel_path).write_text(text, encoding="utf-8")

    def produce(self, name, source, *, package=None, advisory_id=None):
        """Runs the normalizer `name` over one advisory whose short-title
        source is `source`. Returns `(finding, package, advisory_id)`; the
        normalizer must have produced exactly one finding."""
        package = PACKAGES[name] if package is None else package
        advisory_id = ADVISORY_IDS[name] if advisory_id is None else advisory_id
        ecosystem = ECOSYSTEMS[name]
        if name == "npm":
            data = {
                "vulnerabilities": {
                    package: {
                        "isDirect": True,
                        "severity": "high",
                        "range": "<2.0.0",
                        "fixAvailable": {"name": package, "version": "2.0.0"},
                        "via": [
                            {
                                "title": source,
                                "url": f"https://github.com/advisories/{advisory_id}",
                                "range": "<2.0.0",
                            }
                        ],
                    }
                }
            }
            findings = SCAN.normalize_npm(ecosystem, data, "package.json")
        elif name == "cargo":
            data = {
                "vulnerabilities": {
                    "list": [
                        {
                            "is_direct": True,
                            "severity": "high",
                            "advisory": {
                                "id": advisory_id,
                                "title": source,
                                "description": DESCRIPTION_WITH_BREAK,
                            },
                            "package": {"name": package},
                            "versions": {"patched": [">=2.0.0"]},
                        }
                    ]
                }
            }
            findings, _directness_undetermined = SCAN.normalize_cargo(
                ecosystem, data, "Cargo.toml", self.root
            )
        elif name == "pip":
            data = {
                "dependencies": [
                    {
                        "name": package,
                        "version": "3.2.0",
                        "vulns": [
                            {
                                "id": advisory_id,
                                "fix_versions": ["3.2.1"],
                                "description": f"{source} {CVSS_HIGH}",
                            }
                        ],
                    }
                ]
            }
            findings, _skip_info = SCAN.normalize_pip(ecosystem, data, "requirements.txt", self.root)
        elif name == "go":
            data = [
                {
                    "osv": {
                        "id": advisory_id,
                        "summary": source,
                        "details": DESCRIPTION_WITH_BREAK,
                        "severity": [{"type": "CVSS_V3", "score": CVSS_HIGH}],
                        "affected": [
                            {
                                "package": {"name": package},
                                "ranges": [{"events": [{"fixed": "1.0.1"}]}],
                            }
                        ],
                    }
                },
                {"finding": {"osv": advisory_id, "trace": [{"module": package}]}},
            ]
            findings, _undetermined, reason = SCAN.normalize_go(ecosystem, data, "go.mod", self.root)
            self.assertIsNone(reason)
        else:  # pragma: no cover - guarded by NORMALIZERS
            raise AssertionError(f"unknown normalizer {name!r}")
        self.assertEqual(len(findings), 1, f"{name} must produce exactly one finding")
        return findings[0], package, advisory_id

    def short_title_of(self, finding, package, advisory_id):
        """The short-title part of `finding`'s title: everything after the
        contract's `{package}: {advisory_id} — ` prefix."""
        prefix = _title_prefix(package, advisory_id)
        title = finding["title"]
        self.assertTrue(
            title.startswith(prefix),
            f"title {title!r} does not start with the unchanged package / advisory id prefix {prefix!r}",
        )
        return title[len(prefix):]

    def assertNoLineBreak(self, title):
        offending = [ch for ch in title if ch in LINE_BREAKS]
        self.assertEqual(offending, [], f"title {title!r} still contains line-break characters")

    def assertRoundTrips(self, finding, package, advisory_id):
        """AC-2: recovery returns the original pair and grouping reports no
        malformed entry."""
        self.assertEqual(SCAN.recover_package_advisory(finding), (package, advisory_id))
        groups, malformed = SCAN.group_findings_by_package([finding])
        self.assertEqual(malformed, [])
        self.assertEqual(list(groups), [package])
        self.assertEqual([advisory for advisory, _severity in groups[package]], [advisory_id])


# ---------------------------------------------------------------------------
# AC-1: the short title is whitespace-collapsed, for every normalizer.
# ---------------------------------------------------------------------------

class TestShortTitleWhitespaceCollapse(RoundTripCase):
    def test_ac1_each_whitespace_run_becomes_one_ascii_space(self):
        for name in NORMALIZERS:
            for source, collapsed in SOURCES:
                with self.subTest(normalizer=name, source=source):
                    finding, package, advisory_id = self.produce(name, source)
                    self.assertEqual(self.short_title_of(finding, package, advisory_id), collapsed)

    def test_ac1_no_line_break_character_survives_in_the_title(self):
        for name in NORMALIZERS:
            for source, _collapsed in SOURCES:
                with self.subTest(normalizer=name, source=source):
                    finding, _package, _advisory_id = self.produce(name, source)
                    self.assertNoLineBreak(finding["title"])

    def test_ac1_the_short_title_has_no_whitespace_other_than_single_ascii_spaces(self):
        for name in NORMALIZERS:
            for source, _collapsed in SOURCES:
                with self.subTest(normalizer=name, source=source):
                    finding, package, advisory_id = self.produce(name, source)
                    short = self.short_title_of(finding, package, advisory_id)
                    self.assertEqual([ch for ch in short if ch.isspace() and ch != " "], [])
                    self.assertNotIn("  ", short)

    def test_ac1_the_short_title_neither_starts_nor_ends_with_whitespace(self):
        for name in NORMALIZERS:
            for source, _collapsed in SOURCES:
                with self.subTest(normalizer=name, source=source):
                    finding, package, advisory_id = self.produce(name, source)
                    short = self.short_title_of(finding, package, advisory_id)
                    self.assertTrue(short)
                    self.assertFalse(short[0].isspace())
                    self.assertFalse(short[-1].isspace())

    def test_package_and_advisory_id_are_passed_through_untouched(self):
        for name in NORMALIZERS:
            with self.subTest(normalizer=name):
                finding, package, advisory_id = self.produce(name, MIXED_WHITESPACE_SOURCE)
                self.assertTrue(finding["title"].startswith(_title_prefix(package, advisory_id)))

    def test_description_text_is_not_collapsed(self):
        for name in ("cargo", "go"):
            with self.subTest(normalizer=name):
                finding, _package, _advisory_id = self.produce(name, MIXED_WHITESPACE_SOURCE)
                self.assertIn(DESCRIPTION_WITH_BREAK, finding["description"])


# ---------------------------------------------------------------------------
# AC-2: recovery returns the original pair; grouping reports nothing malformed.
# ---------------------------------------------------------------------------

class TestRecoveryAfterCollapse(RoundTripCase):
    def test_ac2_recovery_returns_the_original_pair_for_every_normalizer(self):
        for name in NORMALIZERS:
            for source, _collapsed in SOURCES:
                with self.subTest(normalizer=name, source=source):
                    finding, package, advisory_id = self.produce(name, source)
                    self.assertEqual(
                        SCAN.recover_package_advisory(finding), (package, advisory_id)
                    )

    def test_ac2_grouping_reports_no_malformed_entry_for_every_normalizer(self):
        for name in NORMALIZERS:
            for source, _collapsed in SOURCES:
                with self.subTest(normalizer=name, source=source):
                    finding, package, advisory_id = self.produce(name, source)
                    self.assertRoundTrips(finding, package, advisory_id)


# ---------------------------------------------------------------------------
# AC-3: pip headline before an embedded CVSS vector.
# ---------------------------------------------------------------------------

class TestPipHeadlineBeforeCvssVector(RoundTripCase):
    PROSE = "Heap overflow in the\nparser allows\r\nremote code\texecution."

    def test_ac3_a_multi_line_headline_yields_a_one_line_title_without_the_vector(self):
        finding, package, advisory_id = self.produce("pip", self.PROSE)
        self.assertNoLineBreak(finding["title"])
        self.assertNotIn("CVSS", finding["title"])
        self.assertNotIn(CVSS_HIGH, finding["title"])
        self.assertEqual(
            finding["title"],
            f"{package}: {advisory_id} — Heap overflow in the parser allows remote code execution.",
        )
        self.assertRoundTrips(finding, package, advisory_id)

    def test_ac3_the_description_keeps_its_line_breaks(self):
        finding, _package, _advisory_id = self.produce("pip", self.PROSE)
        self.assertIn("Heap overflow in the\nparser allows\r\nremote code", finding["description"])


# ---------------------------------------------------------------------------
# AC-4: whitespace-only, over-long, and over-long-only-by-whitespace titles.
# ---------------------------------------------------------------------------

class TestWhitespaceOnlyAndOverLongShortTitles(RoundTripCase):
    WHITESPACE_ONLY = "\n\t \r\n\u2028\u3000"

    def test_ac4_a_whitespace_only_short_title_keeps_the_contract_shape_and_round_trips(self):
        for name in NORMALIZERS:
            with self.subTest(normalizer=name):
                finding, package, advisory_id = self.produce(name, self.WHITESPACE_ONLY)
                self.assertNoLineBreak(finding["title"])
                # pip's own headline fallback (the advisory id) is unchanged;
                # the other normalizers get no new fallback: the short title
                # is empty and the title keeps the contract shape.
                expected_short = advisory_id if name == "pip" else ""
                self.assertEqual(finding["title"], _title_prefix(package, advisory_id) + expected_short)
                self.assertRoundTrips(finding, package, advisory_id)

    def test_ac4_an_over_long_short_title_is_capped_with_the_marker_and_round_trips(self):
        source = "lorem\nipsum " * 1000
        for name in NORMALIZERS:
            with self.subTest(normalizer=name):
                finding, package, advisory_id = self.produce(name, source)
                title = finding["title"]
                self.assertLessEqual(len(title.encode("utf-8")), SCAN.UNTRUSTED_TEXT_MAX_BYTES)
                self.assertTrue(title.endswith(SCAN.TRUNCATION_MARKER))
                self.assertTrue(title.startswith(_title_prefix(package, advisory_id)))
                self.assertNoLineBreak(title)
                self.assertRoundTrips(finding, package, advisory_id)

    def test_ac4_a_short_title_over_the_cap_only_because_of_whitespace_runs_is_not_truncated(self):
        sources = (
            "head" + "\n" * 5000 + "tail",
            "head" + "\u3000" * 2000 + "tail",
            "head" + "\r\n" * 3000 + "tail",
        )
        for name in NORMALIZERS:
            for source in sources:
                with self.subTest(normalizer=name, source_bytes=len(source.encode("utf-8"))):
                    self.assertGreater(len(source.encode("utf-8")), SCAN.UNTRUSTED_TEXT_MAX_BYTES)
                    finding, package, advisory_id = self.produce(name, source)
                    self.assertEqual(finding["title"], _title_prefix(package, advisory_id) + "head tail")
                    self.assertFalse(finding["title"].endswith(SCAN.TRUNCATION_MARKER))
                    self.assertRoundTrips(finding, package, advisory_id)


# ---------------------------------------------------------------------------
# AC-5: scan output -> file-tasks, both branches.
# ---------------------------------------------------------------------------

STANDIN_SCRIPT = '''#!{python}
import json
import sys
from pathlib import Path

CALLS = Path({calls!r})
argv = sys.argv[1:]
noun = argv[0] if len(argv) > 0 else None
verb = argv[1] if len(argv) > 1 else None
rest = argv[2:]
record = {{"noun": noun, "verb": verb}}
if "--title" in rest:
    record["title"] = rest[rest.index("--title") + 1]
if "--references-file" in rest:
    record["references"] = Path(rest[rest.index("--references-file") + 1]).read_text(encoding="utf-8")
calls = json.loads(CALLS.read_text(encoding="utf-8")) if CALLS.exists() else []
calls.append(record)
CALLS.write_text(json.dumps(calls), encoding="utf-8")
if (noun, verb) == ("task", "list"):
    sys.stdout.write("[]")
else:
    sys.stdout.write("{{}}")
sys.exit(0)
'''


class TestFileTasksRoundTrip(RoundTripCase):
    def all_findings(self):
        """The AC-1 findings of all four normalizers, in order, with the
        original (package, advisory id) pair of each."""
        findings = []
        pairs = []
        for name in NORMALIZERS:
            finding, package, advisory_id = self.produce(name, MIXED_WHITESPACE_SOURCE)
            findings.append(finding)
            pairs.append((package, advisory_id))
        return findings, pairs

    def write_standin(self):
        calls_path = Path(self._tmp.name) / "calls.json"
        standin_path = Path(self._tmp.name) / "standin.py"
        standin_path.write_text(
            STANDIN_SCRIPT.format(python=sys.executable, calls=str(calls_path)), encoding="utf-8"
        )
        standin_path.chmod(standin_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return standin_path, calls_path

    def init_git_repo(self):
        env = dict(os.environ)
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(self.root)],
            env=env, capture_output=True, text=True, check=True,
        )

    def test_ac5_every_package_is_filed_as_a_task_through_a_standin_entry_point(self):
        findings, pairs = self.all_findings()
        standin, calls_path = self.write_standin()

        result = SCAN.file_tasks(self.root, "demo-feature", findings, str(standin))

        packages = [package for package, _advisory_id in pairs]
        self.assertEqual(result["malformed_findings"], [])
        self.assertEqual(result["branch"], "ntd")
        self.assertEqual(result["filed_packages"], packages)
        self.assertIsNone(result["failed_package"])
        calls = json.loads(calls_path.read_text(encoding="utf-8"))
        created = [call for call in calls if (call["noun"], call["verb"]) == ("task", "create")]
        self.assertEqual([call["title"] for call in created], packages)
        for call, (_package, advisory_id) in zip(created, pairs):
            with self.subTest(advisory_id=advisory_id):
                self.assertIn(f"{advisory_id} (high)", call["references"])

    def test_ac5_every_package_reaches_the_report_when_there_is_no_entry_point(self):
        findings, pairs = self.all_findings()
        self.init_git_repo()

        result = SCAN.file_tasks(self.root, "demo-feature", findings, None)

        self.assertEqual(result["malformed_findings"], [])
        self.assertEqual(result["branch"], "report")
        report = Path(result["report_path"]).read_text(encoding="utf-8")
        for package, advisory_id in pairs:
            with self.subTest(package=package):
                self.assertIn(f"## {package}\n- {advisory_id} (high)\n", report)
        self.assertNotIn("Malformed findings", report)


# ---------------------------------------------------------------------------
# AC-6: package names and advisory ids are not normalized.
# ---------------------------------------------------------------------------

class TestWhitespaceInPackageOrAdvisoryStaysMalformed(RoundTripCase):
    def assertMalformed(self, finding):
        with self.assertRaises(SCAN.FindingTitleError):
            SCAN.recover_package_advisory(finding)
        groups, malformed = SCAN.group_findings_by_package([finding])
        self.assertEqual(groups, {})
        self.assertEqual(malformed, [{"position": 0, "reason": SCAN.MALFORMED_FINDING_REASON}])

    def test_ac6_a_package_name_with_a_line_break_is_still_malformed(self):
        for name in ("npm", "cargo"):
            with self.subTest(normalizer=name):
                package = "left\npad"
                finding, _package, advisory_id = self.produce(name, "plain title", package=package)
                self.assertTrue(finding["title"].startswith(_title_prefix(package, advisory_id)))
                self.assertMalformed(finding)

    def test_ac6_an_advisory_id_with_whitespace_is_still_malformed(self):
        for name in ("npm", "cargo"):
            for advisory_id in ("GHSA aaaa", "GHSA\naaaa"):
                with self.subTest(normalizer=name, advisory_id=advisory_id):
                    finding, package, _advisory_id = self.produce(
                        name, "plain title", advisory_id=advisory_id
                    )
                    self.assertTrue(finding["title"].startswith(_title_prefix(package, advisory_id)))
                    self.assertMalformed(finding)

    def test_ac6_a_malformed_finding_does_not_hide_a_well_formed_one(self):
        bad, _package, _advisory_id = self.produce("npm", "plain title", package="left\npad")
        good, package, advisory_id = self.produce("npm", MIXED_WHITESPACE_SOURCE)
        groups, malformed = SCAN.group_findings_by_package([bad, good])
        self.assertEqual(list(groups), [package])
        self.assertEqual([advisory for advisory, _severity in groups[package]], [advisory_id])
        self.assertEqual([entry["position"] for entry in malformed], [0])


# ---------------------------------------------------------------------------
# AC-7: standard library only.
# ---------------------------------------------------------------------------

def _imported_top_level_modules(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


class TestModuleImportsStandardLibraryOnly(unittest.TestCase):
    def test_ac7_this_module_imports_only_the_standard_library(self):
        imported = _imported_top_level_modules(Path(__file__))
        self.assertIn("unittest", imported)
        self.assertEqual({m for m in imported if m not in sys.stdlib_module_names}, set())


if __name__ == "__main__":
    unittest.main()
