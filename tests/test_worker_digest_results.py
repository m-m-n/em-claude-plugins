"""worker-digest-ownership task0004 (AC-6, TS5): path-only `written_artifacts`.

A Bash-less writing envelope worker never computes a digest, so its
`completed` result lists each written path with `sha256` set to null or left
out. `validate-worker-output.py --kind worker-result` must accept both forms
for every worker that stance check derives, and must still reject an entry
that has no `path`.

Which workers those are is never listed here: they come from
`derive_digest_stance_workers` in `check-plugin-invariants.py`, i.e. from
worker-envelope.md's Applicability table and the agents' frontmatter tools.
For each derived worker the test copies the shipped
`references/fixtures/worker-result/{worker}/valid-completed` directory into a
temporary directory, rewrites only `written_artifacts` (and, when the shipped
fixture reports none, the envelope's write coverage for one probe path) and
runs the validator as a child process with the same auxiliary files the
fixture-corpus runner passes for a fixture directory.

Standard library only.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = REPO_ROOT / "em-workflow" / "scripts" / "check-plugin-invariants.py"
VALIDATOR_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
WORKER_RESULT_FIXTURES = REPO_ROOT / "em-workflow" / "references" / "fixtures" / "worker-result"
THIS_FILE = Path(__file__).resolve()

PLACEHOLDER_SHA256 = "sha256:" + "0" * 64
PROBE_ALLOWED_ROOT = "feature-docs/digest-ownership-probe/"
PROBE_PATH = PROBE_ALLOWED_ROOT + "probe.md"


def load_checker_module():
    spec = importlib.util.spec_from_file_location(
        "_check_plugin_invariants_for_worker_digest_results", CHECKER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker_module()


def companion(case_dir, stem):
    for ext in (".json", ".yaml", ".yml"):
        candidate = case_dir / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


def validator_args(worker, case_dir):
    """The validator argv for one fixture case directory: every auxiliary file
    or directory present is wired by its role name, as the fixture-corpus
    runner in test_validate_worker_output.py does."""
    input_path = companion(case_dir, "input")
    assert input_path is not None, f"{case_dir} has no input.* file"
    args = [
        sys.executable,
        str(VALIDATOR_PATH),
        "--kind",
        "worker-result",
        "--worker",
        worker,
        "--input",
        str(input_path),
    ]
    for flag, stem in (
        ("--input-envelope", "envelope"),
        ("--packet", "packet"),
        ("--answers", "answers"),
        ("--workflow", "workflow"),
        ("--digest-source", "digest-source"),
        ("--phase-state", "phase-state"),
    ):
        path = companion(case_dir, stem)
        if path is not None:
            args += [flag, str(path)]
    for flag, dirname in (
        ("--registries", "registries"),
        ("--feature-dir", "feature-dir"),
        ("--baseline-dir", "baseline-dir"),
    ):
        directory = case_dir / dirname
        if directory.is_dir():
            args += [flag, str(directory)]
    if (case_dir / "DRY_RUN_APPLY").exists():
        args.append("--dry-run-apply")
    return args


def covered_probe_path(envelope):
    """A path the envelope's write coverage admits. An existing writable
    target or allowed root is used as is; when the shipped fixture covers
    nothing, the envelope copy gains one allowed root for the probe path."""
    for target in (envelope.get("write_policy") or {}).get("targets") or []:
        if target.get("path") and target.get("action") in ("create", "replace_own"):
            return target["path"]
    roots = envelope.get("allowed_write_roots") or []
    if roots:
        return roots[0].rstrip("/") + "/probe.md"
    envelope["allowed_write_roots"] = [PROBE_ALLOWED_ROOT]
    return PROBE_PATH


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class WorkerFixtureCase:
    """A temporary copy of one worker's shipped `valid-completed` fixture."""

    def __init__(self, tmp_dir, worker):
        self.worker = worker
        source = WORKER_RESULT_FIXTURES / worker / "valid-completed"
        self.case_dir = Path(tmp_dir) / worker / "valid-completed"
        shutil.copytree(source, self.case_dir)
        self.result = json.loads(companion(self.case_dir, "input").read_text(encoding="utf-8"))
        envelope_path = companion(self.case_dir, "envelope")
        self.envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        self.entries = list(self.result.get("written_artifacts") or [])
        if not self.entries:
            self.entries = [{"path": covered_probe_path(self.envelope), "sha256": PLACEHOLDER_SHA256}]
            write_json(envelope_path, self.envelope)

    def run(self, entries):
        assert entries, f"{self.worker}: a run needs at least one written_artifacts entry"
        result = dict(self.result)
        result["written_artifacts"] = entries
        write_json(companion(self.case_dir, "input"), result)
        return subprocess.run(
            validator_args(self.worker, self.case_dir), capture_output=True, text=True
        )

    def with_null_sha256(self):
        return [dict(entry, sha256=None) for entry in self.entries]

    def with_sha256_omitted(self):
        return [{key: value for key, value in entry.items() if key != "sha256"} for entry in self.entries]

    def without_path(self):
        first, rest = dict(self.entries[0]), self.entries[1:]
        first.pop("path", None)
        return [first] + rest


class TestDerivedWorkersAcceptPathOnlyWrittenArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workers = CHECKER.derive_digest_stance_workers(str(REPO_ROOT))

    def for_each_derived_worker(self, check):
        """Runs `check(case)` once per derived worker on a fresh temporary copy
        of that worker's fixture; the derived set itself must be non-empty, so
        a loop over nothing can never pass."""
        self.assertTrue(self.workers, "no worker derived from the real repository")
        with tempfile.TemporaryDirectory() as tmp:
            for worker in self.workers:
                with self.subTest(worker=worker):
                    check(WorkerFixtureCase(tmp, worker))

    def test_derived_worker_set_is_not_empty(self):
        self.assertTrue(self.workers, "no worker derived from the real repository")

    def test_every_derived_worker_has_a_valid_completed_fixture(self):
        self.assertTrue(self.workers)
        for worker in self.workers:
            with self.subTest(worker=worker):
                case_dir = WORKER_RESULT_FIXTURES / worker / "valid-completed"
                self.assertTrue(case_dir.is_dir(), f"missing fixture directory {case_dir}")
                self.assertIsNotNone(companion(case_dir, "input"))
                self.assertIsNotNone(companion(case_dir, "envelope"))

    def test_sha256_null_is_accepted(self):
        def check(case):
            entries = case.with_null_sha256()
            self.assertTrue(entries)
            self.assertTrue(all(entry["sha256"] is None for entry in entries))
            proc = case.run(entries)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        self.for_each_derived_worker(check)

    def test_sha256_omitted_is_accepted(self):
        def check(case):
            entries = case.with_sha256_omitted()
            self.assertTrue(entries)
            self.assertTrue(all("sha256" not in entry for entry in entries))
            proc = case.run(entries)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        self.for_each_derived_worker(check)

    def test_an_entry_that_still_carries_a_digest_is_accepted_too(self):
        # The validator checks structure and write coverage only; a digest the
        # worker did put in an entry is never what decides.
        def check(case):
            proc = case.run(case.entries)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        self.for_each_derived_worker(check)

    def test_entry_without_a_path_is_rejected(self):
        def check(case):
            entries = case.without_path()
            self.assertNotIn("path", entries[0])
            proc = case.run(entries)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["errors"])
            self.assertTrue(
                any("written_artifacts" in json.dumps(error) for error in payload["errors"]),
                payload["errors"],
            )

        self.for_each_derived_worker(check)


class TestThisFileKeepsToTheStandardLibraryAndNoDispatchReference(unittest.TestCase):
    def test_no_dispatch_reference_literal(self):
        # Built from parts so this assertion's own source never forms the
        # string the agent/dispatch parity scan looks for.
        needle = "subagent_type" + "=" + '"' + "em-workflow:"
        source = THIS_FILE.read_text(encoding="utf-8")
        self.assertNotIn(needle, source)
        self.assertNotIn("subagent_type" + "=" + "'" + "em-workflow:", source)

    def test_imports_are_standard_library_only(self):
        imported = set()
        for line in THIS_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                imported.add(stripped.split()[1].split(".")[0])
            elif stripped.startswith("from ") and " import " in stripped:
                imported.add(stripped.split()[1].split(".")[0])
        self.assertTrue(imported)
        self.assertTrue(
            imported <= set(sys.stdlib_module_names),
            sorted(imported - set(sys.stdlib_module_names)),
        )


if __name__ == "__main__":
    unittest.main()
