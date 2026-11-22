"""Regression tests for `.github/workflows/plugin-version-bump.yml`
(feature version-bump-missing-base, task0001).

Two kinds of tests live here.

Text tests read the workflow YAML and the plugin-dev template as text: the
single heredoc, the byte identity of the two files, the workflow_dispatch
wiring, the environment wiring of the heredoc (no Actions expression inside
it), and the imports of the heredoc.

Integration tests extract the single heredoc from the workflow and run it
with the interpreter running the tests, inside temporary repositories:

- push cases use a bare repository inside the temporary directory, a seed
  history, and a clone made with `git clone --no-local`;
- workflow_dispatch cases use a plain temporary repository.

Isolation (IMPLEMENTATION.md C4): the repository root is located from this
file; every git operation runs inside a per-test temporary directory; the
subprocess environment is built explicitly (HOME and git's global
configuration inside the temporary directory, git's system configuration
disabled, terminal prompts disabled, no inherited GITHUB_* value); nothing
under `~/.claude` is read; no network is used. Initial branch name and
author identity are set explicitly.

"No file changed" means the bytes of every plugin.json and marketplace.json
read before the run equal those read after it.

Fixture versions are test data, not plan text.

Protocol version 0 is forced in the temporary git configuration. Protocol
version 2 lets a server serve any object that exists in its object database,
which would make `uploadpack.allowAnySHA1InWant` irrelevant; under version 0
the bare repository serves a commit that is in no ref only when that option
is enabled, which is how a hosting service behaves in the cases below.
"""

import ast
import collections
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "plugin-version-bump.yml"
TEMPLATE_PATH = (
    REPO_ROOT / "plugin-dev" / "skills" / "plugin-dev" / "templates" / "plugin-version-bump.yml"
)

# A 40-hex value that exists in no repository.
NONEXISTENT_SHA = "deadbeef" * 5
ALL_ZEROS = "0" * 40

GITCONFIG = (
    "[user]\n"
    "\tname = Version Bump Test\n"
    "\temail = version-bump-test@example.invalid\n"
    "[init]\n"
    "\tdefaultBranch = main\n"
    "[commit]\n"
    "\tgpgsign = false\n"
    "[protocol]\n"
    "\tversion = 0\n"
)

# How each value the heredoc needs is expected to reach the step's env block.
ROLE_EXPRESSIONS = {
    "event": ("github.event_name",),
    "before": ("github.event.before",),
    "after": ("github.sha",),
    "plugin": ("github.event.inputs.plugin", "inputs.plugin"),
    "min_version": ("github.event.inputs.min_version", "inputs.min_version"),
}


# ---------------------------------------------------------------------------
# Workflow text helpers
# ---------------------------------------------------------------------------

Node = collections.namedtuple("Node", "value children")
KEY_LINE = re.compile(r"^\s*([A-Za-z_][\w.-]*):(?:\s+(.*))?\s*$")
HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _skippable(line):
    return not line.strip() or line.lstrip().startswith("#")


def parse_mapping(lines):
    """Read one indentation-based block mapping.

    Returns {key: Node(inline value, child lines)}. Only the narrow YAML
    shape the workflow uses is understood.
    """
    entries = {}
    base = None
    current = None
    for line in lines:
        if _skippable(line):
            if current is not None:
                entries[current][1].append(line)
            continue
        indent = _indent(line)
        if base is None:
            base = indent
        match = KEY_LINE.match(line) if indent == base else None
        if match:
            current = match.group(1)
            entries[current] = (match.group(2) or "", [])
        elif current is not None and indent > base:
            entries[current][1].append(line)
    return {key: Node(value, children) for key, (value, children) in entries.items()}


def workflow_steps(text):
    """Return the steps of job `bump` as a list of parsed mappings."""
    top = parse_mapping(text.splitlines())
    jobs = parse_mapping(top["jobs"].children)
    job = parse_mapping(jobs["bump"].children)
    items = []
    current = None
    item_indent = None
    for line in job["steps"].children:
        if _skippable(line):
            if current is not None:
                current.append(line)
            continue
        indent = _indent(line)
        if item_indent is None:
            item_indent = indent
        if indent == item_indent and line.lstrip().startswith("- "):
            current = [" " * (indent + 2) + line.lstrip()[2:]]
            items.append(current)
        elif current is not None:
            current.append(line)
    return [parse_mapping(item) for item in items]


def bump_step(text):
    steps = [s for s in workflow_steps(text) if s.get("id") and s["id"].value == "bump"]
    if len(steps) != 1:
        raise AssertionError(f"expected exactly one step with id 'bump', found {len(steps)}")
    return steps[0]


def step_env(step):
    env = {}
    if "env" in step:
        for name, node in parse_mapping(step["env"].children).items():
            env[name] = node.value
    return env


def env_roles(env):
    """Map each role of ROLE_EXPRESSIONS to the env variable carrying it."""
    roles = {}
    for name, value in env.items():
        match = re.fullmatch(r"\$\{\{\s*(.+?)\s*\}\}", value.strip())
        if not match:
            continue
        for role, expressions in ROLE_EXPRESSIONS.items():
            if match.group(1) in expressions:
                roles.setdefault(role, name)
    return roles


def find_heredocs(text):
    """Find every heredoc opening in `text` (outside heredoc bodies)."""
    lines = text.splitlines()
    found = []
    i = 0
    while i < len(lines):
        match = HEREDOC_OPEN.search(lines[i])
        if not match:
            i += 1
            continue
        delimiter = match.group(2)
        body = []
        j = i + 1
        while j < len(lines) and lines[j].strip() != delimiter:
            body.append(lines[j])
            j += 1
        found.append(
            {
                "line": i + 1,
                "delimiter": delimiter,
                "quoted": bool(match.group(1)),
                "terminated": j < len(lines),
                "indent": _indent(lines[i]),
                "body": body,
            }
        )
        i = j + 1
    return found


def heredoc_source(text):
    """Return the single heredoc body with the YAML block indentation removed."""
    found = find_heredocs(text)
    if len(found) != 1:
        raise AssertionError(f"expected exactly one heredoc, found {len(found)}")
    heredoc = found[0]
    prefix = " " * heredoc["indent"]
    out = []
    for line in heredoc["body"]:
        if not line.strip():
            out.append("")
        elif line.startswith(prefix):
            out.append(line[len(prefix):])
        else:
            raise AssertionError(f"heredoc body line is indented less than its opening: {line!r}")
    return "\n".join(out) + "\n"


def _is_os_environ(node):
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def environment_reads(source):
    """Return (names read from os.environ / os.getenv, count of other os.environ uses)."""
    tree = ast.parse(source)
    names = set()
    recognised = 0
    total = sum(1 for node in ast.walk(tree) if _is_os_environ(node))
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _is_os_environ(node.value):
            recognised += 1
            if isinstance(node.slice, ast.Constant):
                names.add(node.slice.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func = node.func
            if _is_os_environ(func.value) and func.attr in ("get", "pop", "setdefault"):
                recognised += 1
                if node.args and isinstance(node.args[0], ast.Constant):
                    names.add(node.args[0].value)
            elif (
                func.attr == "getenv"
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    names.add(node.args[0].value)
    return names, total - recognised


def imported_top_level_modules(source):
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module.split(".")[0] if node.module and node.level == 0 else "")
    return modules


def exit_zero_calls(source):
    """Return the line numbers of calls that end the process with status 0."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in ("exit", "_exit"):
                arg = node.args[0] if node.args else None
                if arg is None or (isinstance(arg, ast.Constant) and arg.value in (0, None)):
                    lines.append(node.lineno)
        elif isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc
            if isinstance(exc, ast.Name) and exc.id == "SystemExit":
                lines.append(node.lineno)
            elif isinstance(exc, ast.Call) and getattr(exc.func, "id", "") == "SystemExit":
                arg = exc.args[0] if exc.args else None
                if arg is None or (isinstance(arg, ast.Constant) and arg.value in (0, None)):
                    lines.append(node.lineno)
    return lines


# ---------------------------------------------------------------------------
# Text tests
# ---------------------------------------------------------------------------


class WorkflowTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.template = TEMPLATE_PATH.read_text(encoding="utf-8")

    # TS-1 (AC-8)
    def test_ac8_workflow_has_exactly_one_heredoc(self):
        found = find_heredocs(self.workflow)
        self.assertEqual(len(found), 1, f"heredoc openings found at lines {[h['line'] for h in found]}")
        self.assertTrue(found[0]["terminated"], "the heredoc has no terminator line")
        self.assertTrue(heredoc_source(self.workflow).strip(), "the heredoc body is empty")

    def test_ac8_heredoc_delimiter_is_quoted_so_the_shell_expands_nothing(self):
        self.assertTrue(find_heredocs(self.workflow)[0]["quoted"])

    def test_ac8_heredoc_is_valid_python(self):
        ast.parse(heredoc_source(self.workflow))

    # TS-2 (AC-8)
    def test_ac8_workflow_and_template_are_byte_identical(self):
        self.assertEqual(WORKFLOW_PATH.read_bytes(), TEMPLATE_PATH.read_bytes())

    # TS-18 (AC-8): the import half; the "only git" half is checked by review.
    def test_ac8_heredoc_imports_only_standard_library_modules(self):
        names = getattr(sys, "stdlib_module_names", None)
        if names is None:
            self.skipTest("sys.stdlib_module_names needs Python 3.10 or newer")
        imported = imported_top_level_modules(heredoc_source(self.workflow))
        self.assertTrue(imported, "the heredoc imports nothing; the check would be vacuous")
        self.assertEqual(sorted(imported - set(names)), [])

    # AC-3, second half
    def test_ac3_no_branch_ends_with_exit_zero_when_the_base_commit_is_unavailable(self):
        for label, text in (("workflow", self.workflow), ("template", self.template)):
            with self.subTest(file=label):
                source = heredoc_source(text)
                self.assertEqual(exit_zero_calls(source), [], "the script exits 0 explicitly")
                self.assertNotRegex(source, r"skip:\s*base commit")
                self.assertNotRegex(text, r"(?m)^\s*exit 0\s*$")

    # TS-15 (AC-7)
    def test_ac7_push_trigger_stays_limited_to_main(self):
        top = parse_mapping(self.workflow.splitlines())
        triggers = parse_mapping(top["on"].children)
        self.assertIn("push", triggers)
        branches = parse_mapping(triggers["push"].children)["branches"].value
        self.assertEqual(branches.replace(" ", ""), "[main]")

    def test_ac7_workflow_dispatch_declares_required_string_inputs(self):
        top = parse_mapping(self.workflow.splitlines())
        triggers = parse_mapping(top["on"].children)
        self.assertIn("workflow_dispatch", triggers, "workflow_dispatch is not declared")
        dispatch = parse_mapping(triggers["workflow_dispatch"].children)
        self.assertIn("inputs", dispatch, "workflow_dispatch declares no inputs")
        inputs = parse_mapping(dispatch["inputs"].children)
        for name in ("plugin", "min_version"):
            with self.subTest(input=name):
                self.assertIn(name, inputs)
                declared = parse_mapping(inputs[name].children)
                self.assertIn("required", declared)
                self.assertEqual(declared["required"].value, "true")
                self.assertEqual(declared["type"].value if "type" in declared else "", "string")

    def test_ac7_version_update_step_runs_under_dispatch_only_on_main(self):
        step = bump_step(self.workflow)
        self.assertIn("if", step, "the version-update step has no condition")
        condition = step["if"].value
        self.assertIn("workflow_dispatch", condition)
        self.assertIn("github.ref == 'refs/heads/main'", condition)

    # TS-16 (AC-7)
    def test_ac7_pull_request_steps_depend_only_on_bumped_being_non_empty(self):
        pr_steps = [
            step
            for step in workflow_steps(self.workflow)
            if "run" in step and re.search(r"\bgh pr (create|merge)\b", "\n".join(step["run"].children))
        ]
        self.assertTrue(pr_steps, "no step creates or merges the pull request")
        for step in pr_steps:
            self.assertIn("if", step, "a pull request step has no condition")
            condition = re.sub(r"\s+", " ", step["if"].value.strip())
            self.assertEqual(condition, "steps.bump.outputs.bumped != ''")

    # TS-17 (AC-7, TM-1)
    def test_ac7_step_env_defines_every_value_the_heredoc_reads(self):
        step = bump_step(self.workflow)
        env = step_env(step)
        roles = env_roles(env)
        missing = sorted(set(ROLE_EXPRESSIONS) - set(roles))
        self.assertEqual(missing, [], f"the step env does not carry: {missing}")
        names, other_uses = environment_reads(heredoc_source(self.workflow))
        self.assertEqual(other_uses, 0, "the heredoc uses os.environ in a way this check cannot follow")
        runner_provided = {"GITHUB_OUTPUT"}
        self.assertEqual(sorted(names - set(env) - runner_provided), [])
        for role, name in roles.items():
            with self.subTest(role=role):
                self.assertIn(name, names, f"the heredoc never reads {name}")

    def test_ac7_heredoc_body_contains_no_actions_expression(self):
        self.assertNotIn("${{", heredoc_source(self.workflow))

    def test_ac7_version_update_step_script_contains_no_actions_expression(self):
        step = bump_step(self.workflow)
        self.assertNotIn("${{", "\n".join(step["run"].children))


# ---------------------------------------------------------------------------
# Fixtures for the integration tests
# ---------------------------------------------------------------------------


def dump(obj):
    """Serialise the way the workflow script writes JSON files."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def plugin_files(directory, name, version, extra_dir_files=None):
    manifest = {"name": name, "description": f"{name} test plugin"}
    if version is not None:
        manifest["version"] = version
    files = {
        f"{directory}/.claude-plugin/plugin.json": dump(manifest),
        f"{directory}/README.md": f"{name} readme\n",
    }
    files.update(extra_dir_files or {})
    return files


def market_files(entries):
    """entries: list of (name, directory, version or None)."""
    plugins = []
    for name, directory, version in entries:
        entry = {"name": name, "description": f"{name} entry", "source": f"./{directory}"}
        if version is not None:
            entry["version"] = version
        plugins.append(entry)
    return {".claude-plugin/marketplace.json": dump({"name": "test-market", "plugins": plugins})}


def standard_tree(alpha="1.2.3", beta="2.0.0", market_alpha=True, market_beta=True):
    files = {"README.md": "root readme\n"}
    files.update(plugin_files("alpha", "alpha", alpha))
    files.update(plugin_files("beta", "beta", beta))
    files.update(
        market_files(
            [
                ("alpha", "alpha", alpha if market_alpha else None),
                ("beta", "beta", beta if market_beta else None),
            ]
        )
    )
    return files


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def plugin_version(repo, directory):
    return read_json(Path(repo) / directory / ".claude-plugin" / "plugin.json").get("version")


def market_entry(repo, name):
    for entry in read_json(Path(repo) / ".claude-plugin" / "marketplace.json")["plugins"]:
        if entry["name"] == name:
            return entry
    raise AssertionError(f"no marketplace entry named {name}")


def snapshot(root):
    """Bytes of every plugin.json and marketplace.json below `root`."""
    found = {}
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for filename in files:
            if filename in ("plugin.json", "marketplace.json"):
                path = Path(current) / filename
                found[str(path.relative_to(root))] = path.read_bytes()
    return found


def version_tuple(text):
    return tuple(int(part) for part in text.split("."))


class Result:
    def __init__(self, completed, output_path, trace_path):
        self.returncode = completed.returncode
        self.stdout = completed.stdout
        self.stderr = completed.stderr
        self.outputs = {}
        if Path(output_path).exists():
            for line in Path(output_path).read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator:
                    self.outputs[key] = value
        self.fetch_attempts = 0
        if Path(trace_path).exists():
            self.fetch_attempts = sum(
                1
                for line in Path(trace_path).read_text(encoding="utf-8", errors="replace").splitlines()
                if "built-in: git fetch" in line
            )

    def warnings(self):
        return [line for line in self.stdout.splitlines() if line.startswith("::warning::")]

    def bumped_items(self):
        return [item.strip() for item in self.outputs["bumped"].split(",") if item.strip()]

    def diagnostic(self):
        return (
            f"exit={self.returncode} outputs={self.outputs!r} "
            f"stdout={self.stdout!r} stderr={self.stderr!r}"
        )


class Sandbox:
    """One temporary world: git environment, bare repository, seed, clone."""

    def __init__(self, root, heredoc, roles):
        self.root = Path(root)
        self.root.mkdir(parents=True)
        self.heredoc = heredoc
        self.roles = roles
        home = self.root / "home"
        home.mkdir()
        gitconfig = home / "gitconfig"
        gitconfig.write_text(GITCONFIG, encoding="utf-8")
        self.env = {
            "PATH": os.environ.get("PATH", os.defpath),
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
        self.bare = self.root / "bare.git"
        self.seed = self.root / "seed"
        self.clone = self.root / "clone"
        self.repo = self.root / "repo"
        self.output = self.root / "github_output"
        self.trace = self.root / "git_trace.log"

    def git(self, *args, cwd=None):
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.seed),
            env=self.env,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {completed.stderr}")
        return completed.stdout.strip()

    def has_commit(self, repo, sha):
        completed = subprocess.run(
            ["git", "cat-file", "-e", sha + "^{commit}"],
            cwd=str(repo),
            env=self.env,
            capture_output=True,
        )
        return completed.returncode == 0

    def init_bare(self, serve_any_sha=False):
        self.git("init", "-q", "--bare", "-b", "main", str(self.bare), cwd=self.root)
        self.git("config", "gc.auto", "0", cwd=self.bare)
        self.git("config", "receive.autogc", "false", cwd=self.bare)
        if serve_any_sha:
            self.git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=self.bare)

    def init_seed(self):
        self.git("init", "-q", "-b", "main", str(self.seed), cwd=self.root)
        self.git("remote", "add", "origin", str(self.bare))

    def write(self, files, cwd=None):
        base = Path(cwd or self.seed)
        for relative, text in files.items():
            path = base / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit(self, message, files=None, cwd=None):
        self.write(files or {}, cwd)
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-q", "-m", message, cwd=cwd)
        return self.git("rev-parse", "HEAD", cwd=cwd)

    def push(self, refspec):
        self.git("push", "-q", "origin", refspec)

    def make_clone(self):
        self.git("clone", "-q", "--no-local", str(self.bare), str(self.clone), cwd=self.root)
        return self.clone

    def make_repo(self, files):
        self.git("init", "-q", "-b", "main", str(self.repo), cwd=self.root)
        self.commit("fixture", files, cwd=self.repo)
        return self.repo

    def run_script(self, cwd, event, before="", after="", plugin="", min_version=""):
        env = dict(self.env)
        values = {
            "event": event,
            "before": before,
            "after": after,
            "plugin": plugin,
            "min_version": min_version,
        }
        for role, name in self.roles.items():
            env[name] = values[role]
        env["GITHUB_OUTPUT"] = str(self.output)
        env["GIT_TRACE"] = str(self.trace)
        for leftover in (self.output, self.trace):
            if leftover.exists():
                leftover.unlink()
        completed = subprocess.run(
            [sys.executable, "-I", "-"],
            input=self.heredoc,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return Result(completed, self.output, self.trace)


class ScriptTestCase(unittest.TestCase):
    """Base class: a temporary directory per test and the extracted heredoc."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.sandboxes = 0
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.heredoc = heredoc_source(text)
        try:
            self.roles = env_roles(step_env(bump_step(text)))
        except (AssertionError, KeyError):
            self.roles = {}

    def sandbox(self):
        self.sandboxes += 1
        return Sandbox(self.tmp / f"sandbox{self.sandboxes}", self.heredoc, self.roles)

    def push_scenario(self, base_files, change_files, serve_any_sha=False):
        """A bare repository with a base commit and a change commit, and a fresh clone."""
        sandbox = self.sandbox()
        sandbox.init_bare(serve_any_sha)
        sandbox.init_seed()
        base = sandbox.commit("base", base_files)
        sandbox.push("main")
        change = sandbox.commit("change", change_files)
        sandbox.push("main")
        clone = sandbox.make_clone()
        return sandbox, clone, base, change

    def root_commit_scenario(self):
        sandbox = self.sandbox()
        sandbox.init_bare()
        sandbox.init_seed()
        root = sandbox.commit("root", standard_tree())
        sandbox.push("main")
        clone = sandbox.make_clone()
        return sandbox, clone, root

    def dropped_update_scenario(self, serve_any_sha):
        """An update commit is added on main, then main is replaced by a merge
        commit that does not contain it; the next push is for that merge.

        Returns (sandbox, clone, update commit, first parent of the merge, merge).
        """
        sandbox = self.sandbox()
        sandbox.init_bare(serve_any_sha)
        sandbox.init_seed()
        base = sandbox.commit("base", standard_tree())
        sandbox.push("main")
        update = sandbox.commit("actions update", standard_tree(alpha="1.2.4"))
        sandbox.push("main")
        sandbox.git("checkout", "-q", "-b", "side", base)
        sandbox.commit("side change", {"alpha/side.md": "side\n"})
        sandbox.git("checkout", "-q", "-b", "dev", base)
        first_parent = sandbox.commit("dev change", {"alpha/dev.md": "dev\n"})
        sandbox.git("merge", "-q", "--no-ff", "-m", "merge side", "side")
        merge = sandbox.git("rev-parse", "HEAD")
        sandbox.push("dev")
        # Move main in the bare repository away from the update commit; no gc runs,
        # so the commit stays stored there without being in any ref.
        sandbox.git("update-ref", "refs/heads/main", merge, cwd=sandbox.bare)
        sandbox.git("update-ref", "-d", "refs/heads/dev", cwd=sandbox.bare)
        clone = sandbox.make_clone()
        self.assertTrue(sandbox.has_commit(sandbox.bare, update), "fixture: the bare repository lost the update commit")
        self.assertFalse(sandbox.has_commit(clone, update), "fixture: the clone already holds the update commit")
        return sandbox, clone, update, first_parent, merge

    def assert_no_files_changed(self, before, repo):
        self.assertEqual(snapshot(repo), before)


# ---------------------------------------------------------------------------
# AC-1, AC-2, AC-3: base determination
# ---------------------------------------------------------------------------


def alpha_readme_change(**versions):
    files = standard_tree(**versions)
    files["alpha/README.md"] = "alpha readme, changed\n"
    return files


class BaseDeterminationTests(ScriptTestCase):
    # TS-4 (AC-1)
    def test_ac1_before_present_in_clone_is_the_base(self):
        sandbox, clone, base, change = self.push_scenario(standard_tree(), alpha_readme_change())
        result = sandbox.run_script(clone, "push", before=base, after=change)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(result.warnings(), [])
        self.assertEqual(result.fetch_attempts, 0)
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
        self.assertEqual(market_entry(clone, "alpha")["version"], "1.2.4")
        self.assertEqual(plugin_version(clone, "beta"), "2.0.0")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")
        self.assertEqual(set(result.outputs), {"bumped"}, "GITHUB_OUTPUT carries more than the bumped key")

    # TS-5 (AC-1)
    def test_ac1_before_absent_from_clone_but_served_is_fetched_once_and_is_the_base(self):
        sandbox, clone, update, first_parent, merge = self.dropped_update_scenario(serve_any_sha=True)
        result = sandbox.run_script(clone, "push", before=update, after=merge)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(result.warnings(), [])
        self.assertEqual(result.fetch_attempts, 1)
        # The update commit's version is the higher one, so it must have been the base.
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.5")
        self.assertEqual(market_entry(clone, "alpha")["version"], "1.2.5")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.5")

    # TS-6 (AC-2)
    def test_ac2_before_absent_from_the_bare_repository_too_falls_back_to_the_first_parent(self):
        sandbox, clone, base, change = self.push_scenario(standard_tree(), alpha_readme_change())
        result = sandbox.run_script(clone, "push", before=NONEXISTENT_SHA, after=change)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(result.fetch_attempts, 1, "exactly one failed fetch attempt is expected")
        warnings = result.warnings()
        self.assertTrue(warnings, f"no ::warning:: line on stdout: {result.stdout!r}")
        self.assertTrue(any(base in line for line in warnings), "the warning does not name the commit used")
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
        self.assertEqual(market_entry(clone, "alpha")["version"], "1.2.4")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")

    # TS-7 (AC-2)
    def test_ac2_all_zero_before_falls_back_to_the_first_parent_without_fetching(self):
        sandbox, clone, base, change = self.push_scenario(standard_tree(), alpha_readme_change())
        result = sandbox.run_script(clone, "push", before=ALL_ZEROS, after=change)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(result.fetch_attempts, 0)
        self.assertTrue(any(base in line for line in result.warnings()), result.stdout)
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")

    # AC-2, A1
    def test_ac2_before_that_is_not_40_hex_characters_falls_back_without_fetching(self):
        malformed = [
            "",
            "not-a-sha",
            "abc123",
            "g" * 40,
            "a" * 39,
            "a" * 41,
            "a" * 40 + "\n",
            "a" * 20 + "\n" + "a" * 19,
        ]
        for value in malformed:
            with self.subTest(before=value):
                sandbox, clone, base, change = self.push_scenario(standard_tree(), alpha_readme_change())
                result = sandbox.run_script(clone, "push", before=value, after=change)
                self.assertEqual(result.returncode, 0, result.diagnostic())
                self.assertEqual(result.fetch_attempts, 0)
                warnings = result.warnings()
                self.assertTrue(warnings, result.stdout)
                self.assertTrue(any(base in line for line in warnings), result.stdout)
                self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
                self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")

    # TS-8 (AC-3)
    def test_ac3_root_commit_with_unavailable_base_fails_and_changes_no_file(self):
        for label, value in (
            ("unknown commit", NONEXISTENT_SHA),
            ("all zeros", ALL_ZEROS),
            ("malformed", "not-a-sha"),
        ):
            with self.subTest(before=label):
                sandbox, clone, root = self.root_commit_scenario()
                before = snapshot(clone)
                result = sandbox.run_script(clone, "push", before=value, after=root)
                self.assertNotEqual(result.returncode, 0, result.diagnostic())
                self.assert_no_files_changed(before, clone)
                self.assertNotIn("bumped", result.outputs)
                self.assertIn("ERR_001", result.stdout + result.stderr)
                if label == "unknown commit":
                    self.assertEqual(result.fetch_attempts, 1)


# ---------------------------------------------------------------------------
# AC-4: version comparison rules, changed-plugin detection, bumped output
# ---------------------------------------------------------------------------


class VersionRuleTests(ScriptTestCase):
    def push(self, base_files, change_files):
        sandbox, clone, base, change = self.push_scenario(base_files, change_files)
        before = snapshot(clone)
        result = sandbox.run_script(clone, "push", before=base, after=change)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(result.warnings(), [])
        return clone, before, result

    # TS-10 (AC-4)
    def test_ac4_after_lower_than_base_writes_the_greater_version_with_patch_raised(self):
        clone, _, result = self.push(standard_tree(alpha="1.2.4"), alpha_readme_change(alpha="1.2.3"))
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.5")
        self.assertEqual(market_entry(clone, "alpha")["version"], "1.2.5")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.5")

    def test_ac4_after_lower_in_minor_than_base_writes_the_base_line_with_patch_raised(self):
        clone, _, result = self.push(standard_tree(alpha="1.3.0"), alpha_readme_change(alpha="1.2.9"))
        self.assertEqual(plugin_version(clone, "alpha"), "1.3.1")
        self.assertEqual(market_entry(clone, "alpha")["version"], "1.3.1")

    def test_ac4_after_equal_to_base_raises_the_patch(self):
        clone, _, result = self.push(standard_tree(), alpha_readme_change())
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
        self.assertEqual(market_entry(clone, "alpha")["version"], "1.2.4")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")

    def test_ac4_after_higher_than_base_leaves_versions_and_bumped_empty(self):
        sandbox, clone, base, change = self.push_scenario(
            standard_tree(), alpha_readme_change(alpha="1.3.0")
        )
        before = snapshot(clone)
        result = sandbox.run_script(clone, "push", before=base, after=change)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assert_no_files_changed(before, clone)
        self.assertEqual(plugin_version(clone, "alpha"), "1.3.0")
        self.assertEqual(market_entry(clone, "alpha")["version"], "1.3.0")
        self.assertEqual(result.outputs["bumped"], "")

    def test_ac4_versions_are_compared_as_integers_not_as_text(self):
        # "1.2.10" is higher than "1.2.9" although it sorts lower as text.
        sandbox, clone, base, change = self.push_scenario(
            standard_tree(alpha="1.2.9"), alpha_readme_change(alpha="1.2.10")
        )
        before = snapshot(clone)
        result = sandbox.run_script(clone, "push", before=base, after=change)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assert_no_files_changed(before, clone)
        self.assertEqual(result.outputs["bumped"], "")
        # And the other direction: "1.2.9" is lower than "1.2.10".
        clone2, _, result2 = self.push(
            standard_tree(alpha="1.2.10"), alpha_readme_change(alpha="1.2.9")
        )
        self.assertEqual(plugin_version(clone2, "alpha"), "1.2.11")
        self.assertEqual(result2.outputs["bumped"], "alpha@1.2.11")

    # TS-11 (AC-4)
    def test_ac4_a_new_plugin_is_not_bumped_while_a_changed_one_is(self):
        base_files = {"README.md": "root\n"}
        base_files.update(plugin_files("alpha", "alpha", "1.2.3"))
        base_files.update(market_files([("alpha", "alpha", "1.2.3")]))
        change_files = dict(base_files)
        change_files["alpha/README.md"] = "alpha, changed\n"
        change_files.update(plugin_files("newplugin", "newplugin", "0.1.0"))
        change_files.update(market_files([("alpha", "alpha", "1.2.3"), ("newplugin", "newplugin", "0.1.0")]))
        clone, _, result = self.push(base_files, change_files)
        self.assertEqual(plugin_version(clone, "newplugin"), "0.1.0")
        self.assertEqual(market_entry(clone, "newplugin")["version"], "0.1.0")
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")

    def test_ac4_a_push_that_only_adds_a_plugin_bumps_nothing(self):
        change_files = standard_tree()
        change_files.update(plugin_files("newplugin", "newplugin", "0.1.0"))
        change_files.update(
            market_files(
                [("alpha", "alpha", "1.2.3"), ("beta", "beta", "2.0.0"), ("newplugin", "newplugin", "0.1.0")]
            )
        )
        clone, before, result = self.push(standard_tree(), change_files)
        self.assertEqual(result.outputs["bumped"], "")
        self.assertEqual(plugin_version(clone, "newplugin"), "0.1.0")
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.3")

    def test_ac4_versions_not_in_major_minor_patch_form_are_not_bumped(self):
        cases = [
            ("1.2", "1.2"),
            ("1.2.3-beta", "1.2.3-beta"),
            ("v1.2.3", "v1.2.3"),
            ("1.2.3.4", "1.2.3.4"),
            ("1.2.3", "1.2"),
            ("1.2", "1.2.3"),
            ("1.2.3", None),
            ("1.2.3", 5),
        ]
        for base_version, after_version in cases:
            with self.subTest(base=base_version, after=after_version):
                base_files = {"README.md": "root\n"}
                base_files.update(plugin_files("weird", "weird", base_version))
                base_files.update(market_files([("weird", "weird", base_version)]))
                change_files = dict(base_files)
                change_files.update(plugin_files("weird", "weird", after_version))
                change_files["weird/README.md"] = "changed\n"
                sandbox, clone, base, change = self.push_scenario(base_files, change_files)
                before = snapshot(clone)
                result = sandbox.run_script(clone, "push", before=base, after=change)
                self.assertEqual(result.returncode, 0, result.diagnostic())
                self.assert_no_files_changed(before, clone)
                self.assertEqual(result.outputs["bumped"], "")

    # TS-12 (AC-4)
    def test_ac4_a_marketplace_entry_without_a_version_is_not_rewritten(self):
        base_files = standard_tree(market_alpha=False)
        change_files = standard_tree(market_alpha=False)
        change_files["alpha/README.md"] = "changed\n"
        change_files["beta/README.md"] = "changed\n"
        clone, _, result = self.push(base_files, change_files)
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
        self.assertNotIn("version", market_entry(clone, "alpha"))
        self.assertEqual(plugin_version(clone, "beta"), "2.0.1")
        self.assertEqual(market_entry(clone, "beta")["version"], "2.0.1")

    def test_ac4_when_no_marketplace_entry_carries_a_version_the_file_is_untouched(self):
        base_files = standard_tree(market_alpha=False, market_beta=False)
        change_files = dict(base_files)
        change_files["alpha/README.md"] = "changed\n"
        clone, before, result = self.push(base_files, change_files)
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
        key = ".claude-plugin/marketplace.json"
        self.assertEqual(snapshot(clone)[key], before[key])

    def test_ac4_only_version_values_differ_after_a_bump(self):
        clone, before, _ = self.push(standard_tree(), alpha_readme_change())
        after = snapshot(clone)
        for key in before:
            if before[key] != after[key]:
                self.assertEqual(
                    before[key].decode("utf-8").replace("1.2.3", "1.2.4"),
                    after[key].decode("utf-8"),
                    f"{key} differs in more than the version value",
                )

    # AC-4: changed-plugin detection
    def test_ac4_a_change_outside_every_plugin_bumps_nothing(self):
        change_files = standard_tree()
        change_files["README.md"] = "root, changed\n"
        change_files["docs/guide.md"] = "guide\n"
        _, before, result = self.push(standard_tree(), change_files)
        self.assertEqual(result.outputs["bumped"], "")

    def test_ac4_a_change_in_a_nested_directory_is_attributed_to_its_plugin(self):
        change_files = standard_tree()
        change_files["alpha/skills/one/deep/file.md"] = "deep\n"
        clone, _, result = self.push(standard_tree(), change_files)
        self.assertEqual(plugin_version(clone, "alpha"), "1.2.4")
        self.assertEqual(plugin_version(clone, "beta"), "2.0.0")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")

    def test_ac4_a_change_inside_a_nested_plugin_is_attributed_to_the_nearest_plugin(self):
        def tree(outer_version, inner_version):
            files = {"README.md": "root\n"}
            files.update(plugin_files("outer", "outer", outer_version))
            files.update(plugin_files("outer/inner", "inner", inner_version))
            files.update(
                market_files(
                    [("outer", "outer", outer_version), ("inner", "outer/inner", inner_version)]
                )
            )
            return files

        change_files = tree("3.0.0", "4.0.0")
        change_files["outer/inner/skills/file.md"] = "inner change\n"
        clone, _, result = self.push(tree("3.0.0", "4.0.0"), change_files)
        self.assertEqual(plugin_version(clone, "outer/inner"), "4.0.1")
        self.assertEqual(plugin_version(clone, "outer"), "3.0.0")
        self.assertEqual(market_entry(clone, "inner")["version"], "4.0.1")
        self.assertEqual(market_entry(clone, "outer")["version"], "3.0.0")
        self.assertEqual(result.outputs["bumped"], "inner@4.0.1")

    def test_ac4_a_plugin_removed_in_the_push_is_not_bumped(self):
        sandbox = self.sandbox()
        sandbox.init_bare()
        sandbox.init_seed()
        base = sandbox.commit("base", standard_tree())
        sandbox.push("main")
        sandbox.git("rm", "-r", "-q", "beta")
        change = sandbox.commit("remove beta, touch alpha", {"alpha/README.md": "changed\n"})
        sandbox.push("main")
        clone = sandbox.make_clone()
        result = sandbox.run_script(clone, "push", before=base, after=change)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")
        self.assertFalse((clone / "beta").exists())

    # TS-14 (AC-4)
    def test_ac4_bumped_lists_every_bumped_plugin_as_name_at_version(self):
        change_files = standard_tree()
        change_files["alpha/README.md"] = "changed\n"
        change_files["beta/README.md"] = "changed\n"
        _, _, result = self.push(standard_tree(), change_files)
        items = result.bumped_items()
        self.assertEqual(len(items), 2, result.outputs)
        self.assertEqual(set(items), {"alpha@1.2.4", "beta@2.0.1"})
        self.assertTrue(all(re.fullmatch(r"[^@,\s]+@\d+\.\d+\.\d+", item) for item in items), items)

    def test_ac4_bumped_is_written_and_empty_when_nothing_is_bumped(self):
        change_files = standard_tree()
        change_files["README.md"] = "root, changed\n"
        _, _, result = self.push(standard_tree(), change_files)
        self.assertIn("bumped", result.outputs)
        self.assertEqual(result.outputs["bumped"], "")


# ---------------------------------------------------------------------------
# AC-5: reproduction of the reported scenario
# ---------------------------------------------------------------------------


class DroppedUpdateReproductionTests(ScriptTestCase):
    def reproduce(self, serve_any_sha):
        sandbox, clone, update, first_parent, merge = self.dropped_update_scenario(serve_any_sha)
        base = update if serve_any_sha else first_parent
        base_version = json.loads(
            sandbox.git("show", f"{base}:alpha/.claude-plugin/plugin.json", cwd=sandbox.bare)
        )["version"]
        result = sandbox.run_script(clone, "push", before=update, after=merge)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        written = plugin_version(clone, "alpha")
        self.assertEqual(market_entry(clone, "alpha")["version"], written)
        self.assertGreater(version_tuple(written), version_tuple(base_version))
        return result, written

    # TS-9 (AC-5), the bare repository serves the dropped commit
    def test_ac5_reproduction_when_the_bare_repository_serves_the_dropped_commit(self):
        result, written = self.reproduce(serve_any_sha=True)
        self.assertEqual(written, "1.2.5")
        self.assertEqual(result.fetch_attempts, 1)
        self.assertEqual(result.warnings(), [])

    # TS-9 (AC-5), the bare repository does not serve it
    def test_ac5_reproduction_when_the_bare_repository_does_not_serve_the_dropped_commit(self):
        result, written = self.reproduce(serve_any_sha=False)
        self.assertEqual(written, "1.2.4")
        self.assertEqual(result.fetch_attempts, 1)
        self.assertTrue(result.warnings(), result.stdout)


# ---------------------------------------------------------------------------
# AC-6: workflow_dispatch
# ---------------------------------------------------------------------------


class DispatchTests(ScriptTestCase):
    def dispatch(self, plugin, min_version, files=None):
        sandbox = self.sandbox()
        repo = sandbox.make_repo(files or standard_tree())
        before = snapshot(repo)
        result = sandbox.run_script(repo, "workflow_dispatch", plugin=plugin, min_version=min_version)
        return sandbox, repo, before, result

    def assert_rejected(self, sandbox, repo, before, result):
        self.assertNotEqual(result.returncode, 0, result.diagnostic())
        self.assert_no_files_changed(before, repo)
        self.assertNotIn("bumped", result.outputs)

    # TS-13 (AC-6)
    def test_ac6_current_lower_than_min_version_with_equal_major_and_minor_writes_min_version_plus_one(self):
        _, repo, _, result = self.dispatch("alpha", "1.2.9")
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(plugin_version(repo, "alpha"), "1.2.10")
        self.assertEqual(market_entry(repo, "alpha")["version"], "1.2.10")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.10")
        self.assertEqual(set(result.outputs), {"bumped"}, "GITHUB_OUTPUT carries more than the bumped key")
        self.assertEqual(plugin_version(repo, "beta"), "2.0.0")

    def test_ac6_current_equal_to_min_version_writes_min_version_plus_one(self):
        _, repo, _, result = self.dispatch("alpha", "1.2.3")
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(plugin_version(repo, "alpha"), "1.2.4")
        self.assertEqual(market_entry(repo, "alpha")["version"], "1.2.4")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")

    def test_ac6_current_higher_than_min_version_changes_no_file_and_bumped_is_empty(self):
        _, repo, before, result = self.dispatch("alpha", "1.2.2")
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assert_no_files_changed(before, repo)
        self.assertIn("bumped", result.outputs)
        self.assertEqual(result.outputs["bumped"], "")

    def test_ac6_versions_are_compared_as_integers_not_as_text(self):
        files = standard_tree(alpha="1.10.0")
        _, repo, before, result = self.dispatch("alpha", "1.9.9", files)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assert_no_files_changed(before, repo)
        self.assertEqual(result.outputs["bumped"], "")

    def test_ac6_current_lower_than_min_version_with_a_different_minor_exits_non_zero(self):
        sandbox, repo, before, result = self.dispatch("alpha", "1.3.0")
        self.assert_rejected(sandbox, repo, before, result)
        self.assertIn("ERR_004", result.stdout + result.stderr)

    def test_ac6_current_lower_than_min_version_with_a_different_major_exits_non_zero(self):
        sandbox, repo, before, result = self.dispatch("alpha", "2.2.3")
        self.assert_rejected(sandbox, repo, before, result)
        self.assertIn("ERR_004", result.stdout + result.stderr)

    def test_ac6_an_unregistered_plugin_exits_non_zero(self):
        files = standard_tree()
        files.update(plugin_files("unregistered", "unregistered", "1.2.3"))
        sandbox, repo, before, result = self.dispatch("unregistered", "1.2.3", files)
        self.assert_rejected(sandbox, repo, before, result)
        self.assertIn("ERR_002", result.stdout + result.stderr)

    # TM-2
    def test_ac6_a_plugin_shaped_like_a_relative_path_exits_non_zero_without_touching_files(self):
        for value in ("./alpha", "alpha/", "alpha/../beta", "../outside", "./../outside", "/etc", "", " alpha", "ALPHA"):
            with self.subTest(plugin=value):
                sandbox = self.sandbox()
                files = standard_tree()
                repo = sandbox.make_repo(files)
                outside = sandbox.root / "outside" / ".claude-plugin"
                outside.mkdir(parents=True)
                (outside / "plugin.json").write_text(dump({"name": "outside", "version": "1.2.3"}), encoding="utf-8")
                outside_before = (outside / "plugin.json").read_bytes()
                before = snapshot(repo)
                result = sandbox.run_script(repo, "workflow_dispatch", plugin=value, min_version="1.2.3")
                self.assert_rejected(sandbox, repo, before, result)
                self.assertEqual((outside / "plugin.json").read_bytes(), outside_before)

    # TM-3
    def test_ac6_a_malformed_min_version_exits_non_zero_and_writes_no_bumped_value(self):
        malformed = [
            "",
            "1.2",
            "1.2.3.4",
            "1.2.3 ",
            " 1.2.3",
            "v1.2.3",
            "1.2.x",
            "-1.2.3",
            "1.2.3-beta",
            "1.2.3abc",
            "1.2.3\n",
            "1.2.3\nbumped=injected",
            "1.2.3\r\n",
            "１.２.３",
            "1.2.3; echo",
        ]
        for value in malformed:
            with self.subTest(min_version=value):
                sandbox, repo, before, result = self.dispatch("alpha", value)
                self.assert_rejected(sandbox, repo, before, result)
                self.assertIn("ERR_003", result.stdout + result.stderr)

    def test_ac6_a_current_version_not_in_major_minor_patch_form_exits_non_zero(self):
        files = standard_tree(alpha="1.2")
        sandbox, repo, before, result = self.dispatch("alpha", "1.2.3", files)
        self.assert_rejected(sandbox, repo, before, result)

    # TM-2: the plugin.json is located from the registered entry, not from the raw input.
    def test_ac6_the_plugin_json_is_located_from_the_registered_entry(self):
        files = {"README.md": "root\n"}
        files.update(plugin_files("pkg/alpha-impl", "alpha", "1.2.3"))
        files.update(plugin_files("alpha", "decoy", "1.2.3"))
        files.update(market_files([("alpha", "pkg/alpha-impl", "1.2.3")]))
        _, repo, _, result = self.dispatch("alpha", "1.2.3", files)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(plugin_version(repo, "pkg/alpha-impl"), "1.2.4")
        self.assertEqual(market_entry(repo, "alpha")["version"], "1.2.4")
        self.assertEqual(plugin_version(repo, "alpha"), "1.2.3", "the decoy directory named like the input was written")
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")

    def test_ac6_a_marketplace_entry_without_a_version_is_not_rewritten(self):
        files = standard_tree(market_alpha=False)
        _, repo, _, result = self.dispatch("alpha", "1.2.3", files)
        self.assertEqual(result.returncode, 0, result.diagnostic())
        self.assertEqual(plugin_version(repo, "alpha"), "1.2.4")
        self.assertNotIn("version", market_entry(repo, "alpha"))
        self.assertEqual(result.outputs["bumped"], "alpha@1.2.4")


if __name__ == "__main__":
    unittest.main()
