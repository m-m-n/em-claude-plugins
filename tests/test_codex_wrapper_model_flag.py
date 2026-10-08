"""run_codex_exec.sh `-m MODEL` (both plugin copies) and the security
perspective's model pin in reviewers.yaml.

- `-m MODEL` reaches `codex exec` as the adjacent argv elements `-m MODEL`.
- Without `-m`, no `-m` reaches `codex exec`.
- `-m` with no model argument exits 1 without launching.
- em-workflow only: `-m` together with `--litellm` exits 1 without launching.
- The security perspective's codex entry names a model; every other codex
  entry names none.
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


CHAIN_ENTRY = re.compile(r"^\s+- \{harness: (\w+)(?:, model: ([\w.-]+))?\}\s*$")
PERSPECTIVE = re.compile(r"^\s+- perspective: (\w+)\s*$")


def _codex_entries(plugin):
    """Maps perspective -> codex entry model (None when the entry names no
    model) from the plugin's reviewers.yaml."""
    text = (REPO_ROOT / plugin / "references" / "reviewers.yaml").read_text(encoding="utf-8")
    entries = {}
    current = None
    for line in text.splitlines():
        m = PERSPECTIVE.match(line)
        if m:
            current = m.group(1)
            continue
        m = CHAIN_ENTRY.match(line)
        if m and current and m.group(1) == "codex":
            entries[current] = m.group(2)
    return entries


class SecurityModelPinTest(unittest.TestCase):
    def test_only_security_pins_a_codex_model(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                entries = _codex_entries(plugin)
                self.assertIn("security", entries)
                self.assertIsNotNone(entries["security"])
                pinned = {p for p, model in entries.items() if model is not None}
                self.assertEqual(pinned, {"security"})

    def test_both_plugins_pin_the_same_model(self):
        self.assertEqual(
            _codex_entries("em-workflow")["security"],
            _codex_entries("em-review")["security"],
        )


if __name__ == "__main__":
    unittest.main()
