"""Contract tests for the `~/.config/gitleaks/*.toml` loop in the two
gitleaks guard hooks (`gitleaks-write-guard.sh`, `gitleaks-precommit.sh`).

Each hook scans once without `--config`, then once per user toml in name
order, and blocks when any scan reports a leak. A user toml whose scan ends
in a gitleaks error is skipped with a warning. Driven with a fake gitleaks
in the sandbox of `tests/test_guardrail_hooks_migration.py`.

Standard library only, per test/README.md.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_guardrail_hooks_migration import (
    COMMIT_PAYLOAD,
    WRITE_PAYLOAD,
    GitleaksHookSandbox,
)

# A fake gitleaks that appends its `--config` value ("-" when absent) to
# $HOME/calls, then exits 9 for a config named leak.toml, 1 for one named
# broken.toml, and 0 otherwise.
FAKE_GITLEAKS = """#!/usr/bin/env bash
cfg=-
while [ $# -gt 0 ]; do
    [ "$1" = --config ] && cfg=$2
    shift
done
printf '%s\\n' "$cfg" >> "$HOME/calls"
case $cfg in
    */leak.toml) exit 9 ;;
    */broken.toml) exit 1 ;;
esac
exit 0
"""


class UserConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.sandbox = GitleaksHookSandbox()
        self.addCleanup(self.sandbox.close)
        self.sandbox.install_path_gitleaks(FAKE_GITLEAKS)
        self.config_dir = self.sandbox.home / ".config" / "gitleaks"

    def add_configs(self, *names):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            (self.config_dir / name).write_text("")

    def calls(self):
        path = self.sandbox.home / "calls"
        return path.read_text().splitlines() if path.exists() else []

    def config_path(self, name):
        return str(self.config_dir / name)


class TestWriteGuardUserConfigs(UserConfigTestCase):
    def run_guard(self):
        return self.sandbox.run_hook("gitleaks-write-guard.sh", WRITE_PAYLOAD)

    def test_without_config_dir_scans_once_without_config(self):
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["-"])

    def test_scans_default_first_then_each_toml_in_name_order(self):
        self.add_configs("b.toml", "a.toml", "notes.txt")
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.calls(), ["-", self.config_path("a.toml"), self.config_path("b.toml")]
        )

    def test_blocks_when_a_user_toml_reports_a_leak(self):
        self.add_configs("leak.toml")
        result = self.run_guard()
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_skips_a_broken_toml_with_a_warning(self):
        self.add_configs("broken.toml", "c.toml")
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.config_path("c.toml"), self.calls())
        message = json.loads(result.stdout)["systemMessage"]
        self.assertIn(self.config_path("broken.toml"), message)

    def test_warns_when_gitleaks_cannot_be_resolved(self):
        (self.sandbox.bin / "gitleaks").unlink()
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gitleaks", json.loads(result.stdout)["systemMessage"])


class TestPrecommitUserConfigs(UserConfigTestCase):
    def setUp(self):
        super().setUp()
        self.repo = self.sandbox.root / "repo"
        subprocess.run(
            ["git", "init", "-q", str(self.repo)],
            check=True,
            env=self.sandbox.env(),
        )

    def run_guard(self):
        payload = dict(COMMIT_PAYLOAD, cwd=str(self.repo))
        return self.sandbox.run_hook("gitleaks-precommit.sh", payload)

    def test_scans_default_first_then_each_toml(self):
        self.add_configs("a.toml")
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        # staged and unstaged diff per config; no untracked files
        self.assertEqual(
            self.calls(),
            ["-", "-", self.config_path("a.toml"), self.config_path("a.toml")],
        )

    def test_repo_gitleaks_toml_is_used_for_the_first_scan(self):
        (self.repo / ".gitleaks.toml").write_text("")
        subprocess.run(
            ["git", "-C", str(self.repo), "add", ".gitleaks.toml"],
            check=True,
            env=self.sandbox.env(),
        )
        self.run_guard()
        self.assertEqual(self.calls()[:2], [".gitleaks.toml", ".gitleaks.toml"])

    def test_blocks_when_a_user_toml_reports_a_leak(self):
        self.add_configs("leak.toml")
        result = self.run_guard()
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_skips_a_broken_toml_with_a_warning(self):
        self.add_configs("broken.toml")
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        message = json.loads(result.stdout)["systemMessage"]
        self.assertIn(self.config_path("broken.toml"), message)

    def test_warns_when_gitleaks_cannot_be_resolved(self):
        (self.sandbox.bin / "gitleaks").unlink()
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gitleaks", json.loads(result.stdout)["systemMessage"])


if __name__ == "__main__":
    unittest.main()
