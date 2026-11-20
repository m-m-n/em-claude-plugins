"""run_codex_exec.sh `-m MODEL` (both plugin copies) and the per-perspective
codex model and effort pins in reviewers.yaml.

- `-m MODEL` reaches `codex exec` as the adjacent argv elements `-m MODEL`.
- Without `-m`, no `-m` reaches `codex exec`.
- `-m` with no model argument exits 1 without launching.
- em-workflow only: `-m` together with `--litellm` exits 1 without launching.
- `--effort LEVEL` (both plugin copies, feature-docs/review-perspective-model-effort,
  task0001): a LEVEL matching `^[a-z]+$` reaches `codex exec` as the one
  adjacent argv pair `-c` / `model_reasoning_effort="LEVEL"`, directly after
  the sandbox pair, and replaces the mode's own choice (the xhigh pair in
  readonly, nothing in readwrite), on em-workflow's `--litellm` route too.
  Without `--effort` the argv keeps the mode's choice. A missing or
  non-matching value exits 1 with one stderr line and no launch. The last of
  several `--effort` options wins.
- Every codex entry in both reviewers.yaml files names the model and the
  effort of the per-perspective table pinned below, and the two plugins give
  the same model and effort for every perspective they share.
"""

import ast
import itertools
import json
import os
import re
import subprocess
import sys
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


# --- `--effort LEVEL` (task0001) ---------------------------------------------

EFFORT_KEY = "model_reasoning_effort"
SANDBOX = {"readonly": "read-only", "readwrite": "workspace-write"}
REQUIRES_VALUE_LINE = "ERROR: --effort requires an effort argument"
BAD_VALUE_LINE = "ERROR: --effort value must match ^[a-z]+$"
LITELLM_MODEL = "muse-spark"


def _effort_pair(level):
    return ["-c", f'{EFFORT_KEY}="{level}"']


def _effort_indexes(argv):
    """Indexes of the argv elements that carry an effort override. The last
    element is the prompt, never an override, so it is left out."""
    return [i for i, element in enumerate(argv[:-1]) if EFFORT_KEY in element]


def _holds_single_effort_pair(argv, level):
    """True when exactly one argv element carries the effort key and that
    element is `model_reasoning_effort="LEVEL"` directly preceded by `-c`."""
    indexes = _effort_indexes(argv)
    if len(indexes) != 1:
        return False
    i = indexes[0]
    return i > 0 and argv[i - 1] == "-c" and argv[i] == f'{EFFORT_KEY}="{level}"'


def _holds_no_effort_element(argv):
    return _effort_indexes(argv) == []


def _holds_effort_pair_after_sandbox(argv, mode, level):
    return _has_adjacent(argv, ["-s", SANDBOX[mode], *_effort_pair(level)])


def _non_comment_text(script_text):
    return "\n".join(
        line for line in script_text.splitlines() if not line.strip().startswith("#")
    )


def _imported_top_level_modules(source):
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


class EffortOptionLaunchTest(unittest.TestCase):
    """AC-1 and AC-3: a valid `--effort LEVEL` becomes the one effort pair of
    the launch, in either mode and on the em-workflow `--litellm` route."""

    def _launch(self, plugin, wrapper_args):
        proc, launches = _run_wrapper(plugin, wrapper_args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(launches), 1)
        return launches[0]

    def test_readonly_effort_replaces_the_xhigh_pair(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                argv = self._launch(plugin, ["readonly", "--effort", "high", "prompt"])
                self.assertTrue(_holds_single_effort_pair(argv, "high"), argv)
                self.assertNotIn(f'{EFFORT_KEY}="xhigh"', argv)
                self.assertTrue(_holds_effort_pair_after_sandbox(argv, "readonly", "high"), argv)

    def test_readwrite_effort_adds_one_pair(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                argv = self._launch(plugin, ["readwrite", "--effort", "low", "prompt"])
                self.assertTrue(_holds_single_effort_pair(argv, "low"), argv)
                self.assertTrue(_holds_effort_pair_after_sandbox(argv, "readwrite", "low"), argv)

    def test_litellm_route_effort_replaces_the_xhigh_pair(self):
        argv = self._launch(
            "em-workflow",
            ["readonly", "--litellm", LITELLM_MODEL, "--effort", "low", "prompt"],
        )
        self.assertTrue(_holds_single_effort_pair(argv, "low"), argv)
        self.assertNotIn(f'{EFFORT_KEY}="xhigh"', argv)
        self.assertTrue(_has_adjacent(argv, ["-p", "litellm", "-m", LITELLM_MODEL]), argv)
        self.assertTrue(_holds_effort_pair_after_sandbox(argv, "readonly", "low"), argv)

    def test_litellm_route_accepts_effort_before_litellm(self):
        argv = self._launch(
            "em-workflow",
            ["readwrite", "--effort", "medium", "--litellm", LITELLM_MODEL, "prompt"],
        )
        self.assertTrue(_holds_single_effort_pair(argv, "medium"), argv)
        self.assertTrue(_has_adjacent(argv, ["-p", "litellm", "-m", LITELLM_MODEL]), argv)

    def test_model_with_litellm_still_exits_1_when_effort_is_given(self):
        proc, launches = _run_wrapper(
            "em-workflow",
            ["readonly", "-m", "gpt-6-astra", "--litellm", LITELLM_MODEL,
             "--effort", "low", "prompt"],
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("-m and --litellm cannot be combined", proc.stderr)
        self.assertEqual(launches, [])


class EffortDefaultUnchangedTest(unittest.TestCase):
    """AC-2: without `--effort` the argv keeps the mode's own choice."""

    def test_readonly_without_effort_keeps_one_xhigh_pair_after_the_sandbox_pair(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                proc, launches = _run_wrapper(plugin, ["readonly", "prompt"])
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(launches), 1)
                argv = launches[0]
                self.assertTrue(_holds_single_effort_pair(argv, "xhigh"), argv)
                self.assertTrue(_holds_effort_pair_after_sandbox(argv, "readonly", "xhigh"), argv)

    def test_readwrite_without_effort_has_no_effort_element(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                proc, launches = _run_wrapper(plugin, ["readwrite", "prompt"])
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(launches), 1)
                self.assertTrue(_holds_no_effort_element(launches[0]), launches[0])

    def test_litellm_route_without_effort_keeps_the_mode_default(self):
        proc, launches = _run_wrapper(
            "em-workflow", ["readonly", "--litellm", LITELLM_MODEL, "prompt"]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(launches), 1)
        self.assertTrue(_holds_single_effort_pair(launches[0], "xhigh"), launches[0])
        self.assertTrue(
            _holds_effort_pair_after_sandbox(launches[0], "readonly", "xhigh"), launches[0]
        )

        proc, launches = _run_wrapper(
            "em-workflow", ["readwrite", "--litellm", LITELLM_MODEL, "prompt"]
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(launches), 1)
        self.assertTrue(_holds_no_effort_element(launches[0]), launches[0])


class EffortValueRejectionTest(unittest.TestCase):
    """AC-4 (TM-1): a missing or non-matching value exits 1 with one fixed
    stderr line and launches nothing; both copies say the same bytes."""

    INVALID_VALUES = (
        ("double quote", 'hi"gh'),
        ("uppercase letter", "High"),
        ("space", "hi gh"),
        ("backslash", "hi\\gh"),
        ("empty string", ""),
        ("trailing newline", "high\n"),
        ("embedded newline", "high\nx"),
        ("hyphen", "x-high"),
        ("digit", "high2"),
        ("non-ascii letter", "hïgh"),
        ("leading dash", "-high"),
        ("toml injection", 'high"\nsandbox_mode="danger-full-access'),
    )

    def _stderr_per_plugin(self, wrapper_args_for):
        seen = {}
        for plugin in PLUGINS:
            proc, launches = _run_wrapper(plugin, wrapper_args_for(plugin))
            self.assertEqual(proc.returncode, 1, (plugin, proc.stderr))
            self.assertEqual(proc.stdout, "", plugin)
            self.assertEqual(launches, [], plugin)
            seen[plugin] = proc.stderr
        return seen

    def test_non_matching_value_is_rejected_with_one_fixed_line(self):
        for mode in ("readonly", "readwrite"):
            for label, value in self.INVALID_VALUES:
                with self.subTest(mode=mode, value=label):
                    seen = self._stderr_per_plugin(
                        lambda plugin: [mode, "--effort", value, "prompt"]
                    )
                    for plugin, stderr in seen.items():
                        self.assertEqual(stderr, BAD_VALUE_LINE + "\n", plugin)
                    self.assertEqual(seen["em-workflow"], seen["em-review"])

    def test_the_rejected_value_is_never_echoed(self):
        for label, value in self.INVALID_VALUES:
            if not value:
                continue
            with self.subTest(value=label):
                seen = self._stderr_per_plugin(
                    lambda plugin: ["readonly", "--effort", value, "prompt"]
                )
                for plugin, stderr in seen.items():
                    self.assertNotIn(value, stderr, plugin)
                    self.assertEqual(len(stderr.splitlines()), 1, plugin)

    def test_litellm_route_rejects_a_non_matching_value(self):
        proc, launches = _run_wrapper(
            "em-workflow",
            ["readonly", "--litellm", LITELLM_MODEL, "--effort", "High", "prompt"],
        )
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stderr, BAD_VALUE_LINE + "\n")
        self.assertEqual(launches, [])

    def test_missing_value_is_rejected_with_one_fixed_line(self):
        with tempfile.TemporaryDirectory() as workdir:
            cases = (
                ("no value, no prompt", ["readonly", "--effort"]),
                ("prompt swallowed as the value", ["readonly", "--effort", "prompt"]),
                ("value but no prompt", ["readonly", "--effort", "low"]),
                ("after another option", ["readwrite", "-C", workdir, "--effort"]),
            )
            for label, wrapper_args in cases:
                with self.subTest(case=label):
                    seen = self._stderr_per_plugin(lambda plugin: wrapper_args)
                    for plugin, stderr in seen.items():
                        self.assertEqual(stderr, REQUIRES_VALUE_LINE + "\n", plugin)
                    self.assertEqual(seen["em-workflow"], seen["em-review"])


class EffortCombinationTest(unittest.TestCase):
    """AC-5: `--effort` combines with the other options in any order; every
    flag pair stays adjacent, the prompt stays last, the last value wins."""

    def _check_orders(self, plugin, groups, expected_pairs):
        """Runs every order of the option groups. `expected_pairs` holds the
        argv pair each non-effort group must leave on the launch."""
        for order in itertools.permutations(groups):
            with self.subTest(plugin=plugin, order=order):
                wrapper_args = ["readonly"]
                for name in order:
                    wrapper_args += groups[name]
                wrapper_args.append("prompt")
                proc, launches = _run_wrapper(plugin, wrapper_args)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(launches), 1)
                argv = launches[0]
                self.assertTrue(_holds_single_effort_pair(argv, "high"), argv)
                self.assertTrue(_holds_effort_pair_after_sandbox(argv, "readonly", "high"), argv)
                for name, pair in expected_pairs.items():
                    self.assertTrue(_has_adjacent(argv, pair), (name, argv))
                self.assertEqual(argv[-1].splitlines()[-1], "prompt")

    def test_effort_with_model_workdir_and_schema_in_any_order(self):
        with tempfile.TemporaryDirectory() as workdir:
            groups = {
                "effort": ["--effort", "high"],
                "model": ["-m", "gpt-6-astra"],
                "workdir": ["-C", workdir],
                "schema": ["--output-schema", "s.json"],
            }
            expected_pairs = {
                "model": ["-m", "gpt-6-astra"],
                "workdir": ["-C", workdir],
                "schema": ["--output-schema", "s.json"],
            }
            for plugin in PLUGINS:
                self._check_orders(plugin, groups, expected_pairs)

    def test_effort_with_litellm_workdir_and_schema_in_any_order(self):
        with tempfile.TemporaryDirectory() as workdir:
            groups = {
                "effort": ["--effort", "high"],
                "litellm": ["--litellm", LITELLM_MODEL],
                "workdir": ["-C", workdir],
                "schema": ["--output-schema", "s.json"],
            }
            expected_pairs = {
                "litellm": ["-p", "litellm", "-m", LITELLM_MODEL],
                "workdir": ["-C", workdir],
                "schema": ["--output-schema", "s.json"],
            }
            self._check_orders("em-workflow", groups, expected_pairs)

    def test_the_last_effort_wins(self):
        for plugin in PLUGINS:
            for mode in ("readonly", "readwrite"):
                with self.subTest(plugin=plugin, mode=mode):
                    proc, launches = _run_wrapper(
                        plugin, [mode, "--effort", "low", "--effort", "high", "prompt"]
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(len(launches), 1)
                    argv = launches[0]
                    self.assertTrue(_holds_single_effort_pair(argv, "high"), argv)
                    self.assertNotIn(f'{EFFORT_KEY}="low"', argv)

    def test_the_last_effort_wins_on_the_litellm_route(self):
        proc, launches = _run_wrapper(
            "em-workflow",
            ["readonly", "--effort", "low", "--litellm", LITELLM_MODEL,
             "--effort", "high", "prompt"],
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(launches), 1)
        self.assertTrue(_holds_single_effort_pair(launches[0], "high"), launches[0])
        self.assertNotIn(f'{EFFORT_KEY}="low"', launches[0])


class EffortWrapperTextTest(unittest.TestCase):
    """AC-6 (D5): the wrapper code keeps one launch; the new error lines do
    not mention it."""

    def test_each_wrapper_has_codex_exec_once_in_non_comment_lines(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                text = (REPO_ROOT / plugin / "scripts" / "run_codex_exec.sh").read_text(
                    encoding="utf-8"
                )
                self.assertEqual(_non_comment_text(text).count("codex exec"), 1)

    def test_each_wrapper_documents_the_effort_option_in_its_header(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin):
                text = (REPO_ROOT / plugin / "scripts" / "run_codex_exec.sh").read_text(
                    encoding="utf-8"
                )
                header = text.split("set -euo pipefail", 1)[0]
                self.assertIn("--effort LEVEL", header)
                self.assertIn("^[a-z]+$", header)


class EffortTestModuleIsStdlibOnlyTest(unittest.TestCase):
    """AC-7 (NFR4): this module imports the standard library only."""

    def test_this_module_imports_only_the_standard_library(self):
        source = Path(__file__).read_text(encoding="utf-8")
        imported = _imported_top_level_modules(source)
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_the_import_reader_flags_a_third_party_import(self):
        forged = "import json\nimport yaml\nfrom requests import get\n"
        imported = _imported_top_level_modules(forged)
        self.assertEqual(imported - set(sys.stdlib_module_names), {"yaml", "requests"})


class EffortMatcherNegativeProofTest(unittest.TestCase):
    """Every matcher above fails meaningfully on forged argv."""

    BASE = ["--color", "never", "-s", "read-only"]
    TAIL = ["-C", "/w", "prompt"]

    def _argv(self, *effort_elements):
        return [*self.BASE, *effort_elements, *self.TAIL]

    def test_single_pair_matcher_accepts_a_well_formed_argv(self):
        argv = self._argv(*_effort_pair("high"))
        self.assertTrue(_holds_single_effort_pair(argv, "high"))

    def test_single_pair_matcher_rejects_two_pairs(self):
        argv = self._argv(*_effort_pair("high"), *_effort_pair("high"))
        self.assertFalse(_holds_single_effort_pair(argv, "high"))

    def test_single_pair_matcher_rejects_an_xhigh_pair_left_beside_the_new_one(self):
        argv = self._argv(*_effort_pair("xhigh"), *_effort_pair("high"))
        self.assertFalse(_holds_single_effort_pair(argv, "high"))

    def test_single_pair_matcher_rejects_a_split_pair(self):
        argv = [*self.BASE, "-c", "-C", "/w", f'{EFFORT_KEY}="high"', "prompt"]
        self.assertFalse(_holds_single_effort_pair(argv, "high"))

    def test_single_pair_matcher_rejects_an_element_without_dash_c(self):
        argv = self._argv(f'{EFFORT_KEY}="high"')
        self.assertFalse(_holds_single_effort_pair(argv, "high"))

    def test_single_pair_matcher_rejects_a_different_level(self):
        argv = self._argv(*_effort_pair("low"))
        self.assertFalse(_holds_single_effort_pair(argv, "high"))

    def test_single_pair_matcher_rejects_an_argv_without_the_pair(self):
        self.assertFalse(_holds_single_effort_pair(self._argv(), "high"))

    def test_single_pair_matcher_ignores_the_prompt_element(self):
        argv = [*self.BASE, *_effort_pair("high"), f'text with {EFFORT_KEY} inside']
        self.assertTrue(_holds_single_effort_pair(argv, "high"))

    def test_no_effort_matcher_accepts_an_argv_without_an_effort_element(self):
        self.assertTrue(_holds_no_effort_element(self._argv()))

    def test_no_effort_matcher_rejects_any_effort_element(self):
        self.assertFalse(_holds_no_effort_element(self._argv(*_effort_pair("xhigh"))))
        self.assertFalse(_holds_no_effort_element(self._argv(f'{EFFORT_KEY}="low"')))

    def test_position_matcher_accepts_the_pair_directly_after_the_sandbox_pair(self):
        argv = self._argv(*_effort_pair("high"))
        self.assertTrue(_holds_effort_pair_after_sandbox(argv, "readonly", "high"))

    def test_position_matcher_rejects_a_pair_placed_elsewhere(self):
        argv = [*self.BASE, "-C", "/w", *_effort_pair("high"), "prompt"]
        self.assertFalse(_holds_effort_pair_after_sandbox(argv, "readonly", "high"))

    def test_position_matcher_rejects_the_other_modes_sandbox(self):
        argv = self._argv(*_effort_pair("high"))
        self.assertFalse(_holds_effort_pair_after_sandbox(argv, "readwrite", "high"))

    def test_launch_count_matcher_flags_a_second_launch_in_code(self):
        forged = '# codex exec is mentioned here\ntimeout 1 codex exec a\necho "codex exec b"\n'
        self.assertEqual(_non_comment_text(forged).count("codex exec"), 2)
        genuine = "# codex exec is mentioned here\ntimeout 1 codex exec a\n"
        self.assertEqual(_non_comment_text(genuine).count("codex exec"), 1)


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
