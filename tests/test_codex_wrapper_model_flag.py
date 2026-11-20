"""run_codex_exec.sh `-m MODEL` (both plugin copies) and the per-perspective
codex model and effort pins in reviewers.yaml.

- `-m MODEL` reaches `codex exec` as the adjacent argv elements `-m MODEL`.
- Without `-m`, no `-m` reaches `codex exec`.
- `-m` with no model argument exits 1 without launching.
- em-workflow only: `-m` together with `--litellm` exits 1 without launching.
- Every codex entry in both reviewers.yaml files names the model and the
  effort of the per-perspective table pinned below, and the two plugins give
  the same model and effort for every perspective they share.
"""

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ("em-workflow", "em-review")

STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import sys

with open(os.environ["CODEX_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:]}) + "\\n")
print("STUB_ANSWER: ok")
"""


def _run_wrapper(plugin, wrapper_args):
    with tempfile.TemporaryDirectory() as stub_dir_s:
        stub_dir = Path(stub_dir_s)
        log_path = stub_dir / "stub.log"
        stub_path = stub_dir / "codex"
        stub_path.write_text(STUB_SOURCE, encoding="utf-8")
        stub_path.chmod(0o755)
        fake_home = stub_dir / "home"
        fake_home.mkdir()

        env = dict(os.environ)
        env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
        env["CODEX_STUB_LOG"] = str(log_path)
        env["HOME"] = str(fake_home)
        env.pop("CODEX_HOME", None)

        script = REPO_ROOT / plugin / "scripts" / "run_codex_exec.sh"
        proc = subprocess.run(
            ["bash", str(script), *wrapper_args],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        launches = []
        if log_path.is_file():
            for line in log_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    launches.append(json.loads(line)["argv"])
        return proc, launches


def _has_adjacent(argv, expected):
    width = len(expected)
    return any(argv[i:i + width] == expected for i in range(len(argv) - width + 1))


class ModelFlagTest(unittest.TestCase):
    def test_model_flag_is_passed_through(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                proc, launches = _run_wrapper(plugin, ["readonly", "-m", "gpt-6-astra", "prompt"])
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(launches), 1)
                self.assertTrue(_has_adjacent(launches[0], ["-m", "gpt-6-astra"]), launches[0])
                self.assertEqual(launches[0].count("-m"), 1, launches[0])

    def test_no_model_flag_without_m(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                proc, launches = _run_wrapper(plugin, ["readonly", "prompt"])
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(launches), 1)
                self.assertNotIn("-m", launches[0])

    def test_model_flag_combines_with_other_flags(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                with tempfile.TemporaryDirectory() as workdir:
                    proc, launches = _run_wrapper(
                        plugin,
                        ["readonly", "-C", workdir, "--output-schema", "s.json",
                         "-m", "gpt-6-astra", "prompt"],
                    )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(launches), 1)
                argv = launches[0]
                self.assertTrue(_has_adjacent(argv, ["-m", "gpt-6-astra"]), argv)
                self.assertTrue(_has_adjacent(argv, ["--output-schema", "s.json"]), argv)
                self.assertEqual(argv[-1].splitlines()[-1], "prompt")

    def test_model_flag_without_argument_does_not_launch(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                proc, launches = _run_wrapper(plugin, ["readonly", "-m", "prompt"])
                self.assertEqual(proc.returncode, 1)
                self.assertIn("-m requires a model argument", proc.stderr)
                self.assertEqual(launches, [])

    def test_model_flag_with_litellm_does_not_launch(self):
        proc, launches = _run_wrapper(
            "em-workflow", ["readonly", "-m", "gpt-6-astra", "--litellm", "muse-spark", "prompt"]
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("-m and --litellm cannot be combined", proc.stderr)
        self.assertEqual(launches, [])


# One-line flow form with the keys in the registry's order: `harness`, then
# the optional `model`, then the optional `effort`.
CHAIN_ENTRY = re.compile(
    r"^\s+- \{harness: (\w+)(?:, model: ([\w.-]+))?(?:, effort: ([a-z]+))?\}\s*$"
)
PERSPECTIVE = re.compile(r"^\s+- perspective: (\w+)\s*$")


def parse_codex_entries(text):
    """Maps perspective -> (model, effort) for the codex entry of each
    perspective in a reviewers.yaml text. A key the entry omits reads as
    None. A codex line that does not follow the one-line flow form in the
    registry's key order is not read at all, so its perspective is missing
    from the result."""
    entries = {}
    current = None
    for line in text.splitlines():
        m = PERSPECTIVE.match(line)
        if m:
            current = m.group(1)
            continue
        m = CHAIN_ENTRY.match(line)
        if m and current and m.group(1) == "codex":
            entries[current] = (m.group(2), m.group(3))
    return entries


def _codex_entries(plugin):
    """Maps perspective -> (model, effort) from the plugin's reviewers.yaml."""
    text = (REPO_ROOT / plugin / "references" / "reviewers.yaml").read_text(encoding="utf-8")
    return parse_codex_entries(text)


def codex_entries_match(text, expected):
    """Matcher: True iff the codex entries read from the registry `text`
    equal `expected` exactly -- the same perspectives, each with the same
    model and effort."""
    return parse_codex_entries(text) == expected


def shared_perspectives_agree(entries_a, entries_b):
    """Matcher: True iff every perspective present in both `entries_a` and
    `entries_b` has the same (model, effort) in both."""
    return all(entries_a[p] == entries_b[p] for p in entries_a.keys() & entries_b.keys())


# Refreshed by feature-docs/review-perspective-model-effort/tasks/task0002.md
# (FR1, FR2): replaces the old "only security names a codex model" pin. Every
# codex entry now names a model and an effort. The values are the FR2 table
# as literals, written out per plugin and not read back from the registries.
# em-review has no license perspective, and its comprehensive chain is empty.
EXPECTED_CODEX_ENTRIES = {
    "em-workflow": {
        "security": ("gpt-6.2-astra", "xhigh"),
        "performance": ("gpt-6.2-sol", "xhigh"),
        "architecture": ("gpt-6.2-astra", "high"),
        "spec": ("gpt-6.2-sol", "xhigh"),
        "comprehensive": ("gpt-6.2-astra", "high"),
        "license": ("gpt-6.2-sol", "low"),
    },
    "em-review": {
        "security": ("gpt-6.2-astra", "xhigh"),
        "performance": ("gpt-6.2-sol", "xhigh"),
        "architecture": ("gpt-6.2-astra", "high"),
        "spec": ("gpt-6.2-sol", "xhigh"),
    },
}

SHARED_PERSPECTIVES = {"security", "performance", "architecture", "spec"}


class CodexEntryModelEffortPinTest(unittest.TestCase):
    """AC-5 (TS-7): the live registries pin the FR2 model and effort."""

    def test_each_plugin_pins_the_fr2_model_and_effort_per_perspective(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                self.assertEqual(_codex_entries(plugin), EXPECTED_CODEX_ENTRIES[plugin])

    def test_both_plugins_give_the_same_model_and_effort_per_shared_perspective(self):
        workflow = _codex_entries("em-workflow")
        review = _codex_entries("em-review")
        # Guards against a vacuous pass: the overlap is exactly the four
        # perspectives both plugins carry.
        self.assertEqual(workflow.keys() & review.keys(), SHARED_PERSPECTIVES)
        self.assertTrue(shared_perspectives_agree(workflow, review))


def _render_registry(entries):
    """Builds registry-shaped text (one-line flow entries, the registry's key
    order) from a perspective -> (model, effort) mapping. A None model or
    effort leaves that key out of the line."""
    lines = ["version: 0", "", "perspectives:"]
    for perspective, (model, effort) in entries.items():
        parts = ["harness: codex"]
        if model is not None:
            parts.append(f"model: {model}")
        if effort is not None:
            parts.append(f"effort: {effort}")
        lines += [
            f"  - perspective: {perspective}",
            "    primary_chain:",
            "      - {" + ", ".join(parts) + "}",
            "      - {harness: litellm, model: muse-spark}",
        ]
    return "\n".join(lines) + "\n"


class CodexEntryMatchersRejectForgedRegistryTest(unittest.TestCase):
    """AC-5 negative proofs: every case builds a forged registry text in
    memory, so nothing is read from or written to disk."""

    def setUp(self):
        self.expected = EXPECTED_CODEX_ENTRIES["em-workflow"]

    def test_pin_matcher_accepts_the_unaltered_registry(self):
        # Positive control: without it, the rejections below could pass
        # because the renderer and the reader disagree about the shape.
        self.assertTrue(codex_entries_match(_render_registry(self.expected), self.expected))

    def test_pin_matcher_rejects_a_registry_where_one_effort_differs(self):
        forged = dict(self.expected, security=("gpt-6.2-astra", "high"))
        self.assertFalse(codex_entries_match(_render_registry(forged), self.expected))

    def test_pin_matcher_rejects_a_registry_where_one_model_differs(self):
        forged = dict(self.expected, spec=("gpt-6.2-astra", "xhigh"))
        self.assertFalse(codex_entries_match(_render_registry(forged), self.expected))

    def test_pin_matcher_rejects_a_codex_entry_without_effort(self):
        forged = dict(self.expected, license=("gpt-6.2-sol", None))
        self.assertFalse(codex_entries_match(_render_registry(forged), self.expected))

    def test_pin_matcher_rejects_a_codex_entry_without_model(self):
        forged = dict(self.expected, comprehensive=(None, "high"))
        self.assertFalse(codex_entries_match(_render_registry(forged), self.expected))

    def test_pin_matcher_rejects_a_registry_missing_a_perspective(self):
        forged = {p: v for p, v in self.expected.items() if p != "license"}
        self.assertFalse(codex_entries_match(_render_registry(forged), self.expected))

    def test_pin_matcher_rejects_effort_written_before_model(self):
        text = _render_registry(self.expected).replace(
            "{harness: codex, model: gpt-6.2-sol, effort: low}",
            "{harness: codex, effort: low, model: gpt-6.2-sol}",
        )
        self.assertNotEqual(text, _render_registry(self.expected))
        self.assertFalse(codex_entries_match(text, self.expected))

    def test_agreement_matcher_accepts_identical_shared_entries(self):
        workflow = parse_codex_entries(_render_registry(EXPECTED_CODEX_ENTRIES["em-workflow"]))
        review = parse_codex_entries(_render_registry(EXPECTED_CODEX_ENTRIES["em-review"]))
        self.assertTrue(shared_perspectives_agree(workflow, review))

    def test_agreement_matcher_rejects_a_shared_perspective_whose_effort_differs(self):
        workflow = parse_codex_entries(_render_registry(EXPECTED_CODEX_ENTRIES["em-workflow"]))
        review = parse_codex_entries(
            _render_registry(dict(EXPECTED_CODEX_ENTRIES["em-review"], spec=("gpt-6.2-sol", "high")))
        )
        self.assertFalse(shared_perspectives_agree(workflow, review))

    def test_agreement_matcher_ignores_a_perspective_only_one_plugin_has(self):
        workflow = parse_codex_entries(_render_registry(EXPECTED_CODEX_ENTRIES["em-workflow"]))
        review = parse_codex_entries(_render_registry(EXPECTED_CODEX_ENTRIES["em-review"]))
        self.assertNotIn("license", review)
        self.assertIn("license", workflow)
        self.assertTrue(shared_perspectives_agree(workflow, review))


if __name__ == "__main__":
    unittest.main()
