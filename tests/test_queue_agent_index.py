"""Subprocess-driven contract tests for queue_agent_index.py.

Mirrors the PostToolUse JSON contract Claude Code documents for a completed
`Task(subagent_type="em-workflow:implementer")` / `Agent(...)` launch
(hooks.md "PostToolUse input" / "Agent" tool section): `tool_input` carries
the launch arguments (including the task-assignment prompt), `tool_response`
carries the completed call's result.

The exact `tool_response` shape for the harness's own agent identifier is
unverified in this environment (IMPLEMENTATION.md D3), so both a structured
field (`agentId`) and a text-embedded identifier are exercised (AC-10), with
negative tests bounding the tolerance (Test Notes).
"""

import ast
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "queue_agent_index.py")
HOOKS_JSON_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "hooks.json")

AT_RE_FMT = "%Y-%m-%dT%H:%M:%S%z"


def build_prompt(task_id, worktree_path, include_header=True):
    header = "# Task assignment\n" if include_header else ""
    return (
        f"{header}"
        f"task_id: {task_id}\n"
        f"worktree_path: {worktree_path}\n"
        f"task_plan_path: /main/feature-docs/f/tasks/{task_id}.md\n"
        f"implementation_md_path: /main/feature-docs/f/IMPLEMENTATION.md\n"
        f"parent_branch: em-workflow/f/integration\n"
        f"merge_script: /main/em-workflow/scripts/merge-task.sh\n"
        f"skills_to_load: []\n"
        f"project_commands:\n"
        f"  build: \"\"\n"
        f"  test: \"echo ok\"\n"
        f"  format: \"\"\n"
        f"expected_files: []\n"
    )


def run_hook(stdin_text):
    proc = subprocess.run(
        [sys.executable, HOOK_PATH],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return proc


def run_hook_payload(payload):
    return run_hook(json.dumps(payload))


def post_tool_use_payload(
    task_id,
    worktree_path,
    tool_response,
    subagent_type="em-workflow:implementer",
    include_header=True,
    tool_name="Task",
):
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {
            "subagent_type": subagent_type,
            "description": f"Implement {task_id}",
            "prompt": build_prompt(task_id, worktree_path, include_header=include_header),
        },
        "tool_response": tool_response,
    }


def structured_result(agent_id):
    return {
        "status": "completed",
        "agentId": agent_id,
        "content": [{"type": "text", "text": "Done."}],
    }


def embedded_text_result(agent_id):
    return {
        "status": "completed",
        "content": [
            {"type": "text", "text": f"Implementer finished. agentId: {agent_id}"}
        ],
    }


def content_string_result(agent_id):
    """A `content` field that is a plain string rather than a block list --
    the ordinary shape of a tool result whose type is a bare string
    (task0005 F-2)."""
    return {
        "status": "completed",
        "content": f"Implementer finished. agentId: {agent_id}",
    }


def index_path_for(worktree_path):
    return os.path.join(os.path.dirname(worktree_path), "agents.jsonl")


def read_index_lines(worktree_path):
    path = index_path_for(worktree_path)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def assert_rfc3339_with_offset(value):
    parsed = datetime.strptime(value, AT_RE_FMT)
    assert parsed.utcoffset() is not None


@contextlib.contextmanager
def _tmp_worktree():
    """A fresh temp dir standing in for the feature's worktree root, with a
    'worktree_path' inside it (dirname(worktree_path) is where agents.jsonl
    lives, per the Agent index contract)."""
    with tempfile.TemporaryDirectory() as tmp_root:
        yield os.path.join(tmp_root, "task0001")


class TestFirstLaunchAppendsIndexEntry(unittest.TestCase):
    """AC-1: implementer launch + recoverable agent id -> exactly one entry
    appended, containing agent id, task id, worktree path, RFC3339 `at`.
    Exit status 0."""

    def test_index_entry_appended_with_all_fields(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001", worktree_path, structured_result("agent-xyz-001")
            )
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)

            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            entry = lines[0]
            self.assertEqual(entry["agent_id"], "agent-xyz-001")
            self.assertEqual(entry["agent_ids"], ["agent-xyz-001"])
            self.assertEqual(entry["task"], "task0001")
            self.assertEqual(entry["worktree_path"], worktree_path)
            assert_rfc3339_with_offset(entry["at"])


class TestBothLaunchToolNamesSupported(unittest.TestCase):
    """AC-2: an entry is appended for BOTH launch tool names."""

    def test_agent_tool_name_appends_entry(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001",
                worktree_path,
                structured_result("agent-aaa"),
                tool_name="Agent",
            )
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["agent_id"], "agent-aaa")

    def test_task_tool_name_appends_entry(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001",
                worktree_path,
                structured_result("agent-bbb"),
                tool_name="Task",
            )
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["agent_id"], "agent-bbb")


class TestNonImplementerLaunchIgnored(unittest.TestCase):
    """AC-3: subagent_type names a non-implementer agent -> no entry, exit
    0, even when the prompt carries a well-formed task assignment block."""

    def test_non_implementer_subagent_type_produces_no_entry(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001",
                worktree_path,
                structured_result("agent-xyz-002"),
                subagent_type="Explore",
            )
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(read_index_lines(worktree_path), [])

    def test_non_launch_tool_is_ignored(self):
        proc = run_hook_payload(
            {"tool_name": "Bash", "tool_input": {"command": "echo hi"},
             "tool_response": {"stdout": "hi"}}
        )
        self.assertEqual(proc.returncode, 0)


class TestInvalidIdentityProducesNoEntry(unittest.TestCase):
    """AC-4: invalid task id / relative worktree path / `..` segment -> no
    entry, exit status 0."""

    def test_invalid_task_id_produces_no_entry(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "not-a-task-id", worktree_path, structured_result("agent-1")
            )
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(read_index_lines(worktree_path), [])

    def test_relative_worktree_path_produces_no_entry(self):
        payload = post_tool_use_payload(
            "task0001", "relative/path/task0001", structured_result("agent-1")
        )
        proc = run_hook_payload(payload)
        self.assertEqual(proc.returncode, 0)

    def test_dotdot_worktree_path_produces_no_entry(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            evil = os.path.join(os.path.dirname(worktree_path), "..", "task0001")
            payload = post_tool_use_payload(
                "task0001", evil, structured_result("agent-1")
            )
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(read_index_lines(worktree_path), [])


class TestMissingJournalDirectoryProducesNoEntry(unittest.TestCase):
    """AC-5: derived journal directory absent -> no file, no directory
    created, exit status 0."""

    def test_absent_directory_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            never_created = os.path.join(tmp_root, "does-not-exist")
            worktree_path = os.path.join(never_created, "task0001")
            self.assertFalse(os.path.isdir(never_created))

            payload = post_tool_use_payload(
                "task0001", worktree_path, structured_result("agent-1")
            )
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            self.assertFalse(os.path.isdir(never_created))
            self.assertFalse(os.path.isfile(os.path.join(never_created, "agents.jsonl")))


class TestUnrecoverableAgentIdentifierProducesNoEntry(unittest.TestCase):
    """AC-6 (and D3 negative-space coverage): a tool result carrying no
    recoverable agent identifier produces no entry, exit status 0."""

    def test_result_with_no_identifiable_field_or_text_produces_no_entry(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001",
                worktree_path,
                {"status": "completed", "content": [{"type": "text", "text": "Done."}]},
            )
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(read_index_lines(worktree_path), [])

    def test_result_as_a_list_is_rejected(self):
        """Negative test for a rejected layout: tool_response is neither an
        object nor text -- must not be tolerated."""
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload("task0001", worktree_path, ["completed"])
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(read_index_lines(worktree_path), [])

    def test_non_string_structured_field_is_rejected(self):
        """Negative test: a structured field present but not a string is
        never coerced -- falls through to text (which here has none)."""
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001",
                worktree_path,
                {"agentId": 12345, "content": [{"type": "text", "text": "Done."}]},
            )
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(read_index_lines(worktree_path), [])

    def test_missing_tool_response_produces_no_entry(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = {
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "em-workflow:implementer",
                    "prompt": build_prompt("task0001", worktree_path),
                },
            }
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(read_index_lines(worktree_path), [])


class TestFailOpenOnMalformedInput(unittest.TestCase):
    """AC-7: malformed JSON on stdin -> exit status 0, no output, no writes."""

    def test_malformed_stdin_exits_zero_no_output(self):
        proc = run_hook("not json at all {{{")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_empty_stdin_exits_zero_no_output(self):
        proc = run_hook("")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_non_object_stdin_exits_zero(self):
        proc = run_hook(json.dumps([1, 2, 3]))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")


class TestConcurrentDifferentTasksBothAppend(unittest.TestCase):
    """AC-8: concurrent invocations for different tasks in the same feature
    all append their own entry; every line parses as JSON (no interleaved
    or truncated writes)."""

    def test_concurrent_launches_for_two_tasks_all_append_valid_json(self):
        import threading

        with tempfile.TemporaryDirectory() as tmp_root:
            worktree_a = os.path.join(tmp_root, "task0001")
            worktree_b = os.path.join(tmp_root, "task0002")
            os.makedirs(worktree_a, exist_ok=True)
            os.makedirs(worktree_b, exist_ok=True)

            n_per_task = 4
            stdin_payloads = []
            for i in range(n_per_task):
                stdin_payloads.append(
                    json.dumps(
                        post_tool_use_payload(
                            "task0001", worktree_a, structured_result(f"agent-a-{i}")
                        )
                    )
                )
                stdin_payloads.append(
                    json.dumps(
                        post_tool_use_payload(
                            "task0002", worktree_b, structured_result(f"agent-b-{i}")
                        )
                    )
                )

            n = len(stdin_payloads)
            results = [None] * n
            barrier = threading.Barrier(n)

            def launch(i):
                barrier.wait()
                results[i] = run_hook(stdin_payloads[i])

            threads = [threading.Thread(target=launch, args=(i,)) for i in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            for proc in results:
                self.assertEqual(proc.returncode, 0)

            index_path = os.path.join(tmp_root, "agents.jsonl")
            with open(index_path, encoding="utf-8") as fh:
                raw_lines = [line for line in fh if line.strip()]

            self.assertEqual(len(raw_lines), n, f"expected {n} lines, got: {raw_lines}")

            parsed = [json.loads(line) for line in raw_lines]  # raises if truncated/interleaved
            task_a_entries = [e for e in parsed if e["task"] == "task0001"]
            task_b_entries = [e for e in parsed if e["task"] == "task0002"]
            self.assertEqual(len(task_a_entries), n_per_task)
            self.assertEqual(len(task_b_entries), n_per_task)
            for entry in task_a_entries:
                self.assertEqual(entry["worktree_path"], worktree_a)
            for entry in task_b_entries:
                self.assertEqual(entry["worktree_path"], worktree_b)


class TestHooksJsonRegistersAgentIndexEntry(unittest.TestCase):
    """AC-9: hooks.json stays valid JSON, keeps the three pre-existing
    registrations unchanged, and additionally registers this hook with
    `timeout: 15` and the plugin-root-relative command form. Scoped to this
    hook's own entry only (task0003 owns the whole-file registration
    check)."""

    @classmethod
    def setUpClass(cls):
        cls.raw = Path(HOOKS_JSON_PATH).read_text(encoding="utf-8")
        cls.config = json.loads(cls.raw)

    def test_hooks_json_is_valid_json(self):
        json.loads(self.raw)  # raises on failure

    def _hooks_for(self, event, matcher):
        matches = []
        for group in self.config.get("hooks", {}).get(event, []):
            if matcher is not None and group.get("matcher") != matcher:
                continue
            matches.extend(group.get("hooks", []))
        return matches

    def test_existing_bash_guard_entry_is_unchanged(self):
        hooks = self._hooks_for("PreToolUse", "Bash")
        commands = [h.get("command", "") for h in hooks]
        self.assertTrue(any("bash_guard.py" in c for c in commands))

    def test_existing_launch_guard_entry_is_unchanged(self):
        hooks = self._hooks_for("PreToolUse", "Task|Agent")
        commands = [h.get("command", "") for h in hooks]
        self.assertTrue(any("queue_launch_guard.py" in c for c in commands))

    def test_existing_stop_guard_entry_is_unchanged(self):
        hooks = self._hooks_for("Stop", None)
        commands = [h.get("command", "") for h in hooks]
        self.assertTrue(any("queue_stop_guard.py" in c for c in commands))

    def test_existing_failure_net_entry_is_unchanged(self):
        hooks = self._hooks_for("SubagentStop", None)
        commands = [h.get("command", "") for h in hooks]
        self.assertTrue(any("queue_failure_net.py" in c for c in commands))

    def test_agent_index_writer_is_registered_on_post_tool_use(self):
        matching_hooks = []
        for group in self.config.get("hooks", {}).get("PostToolUse", []):
            matcher = group.get("matcher", "")
            # Must cover both launch tool names.
            if "Task" not in matcher or "Agent" not in matcher:
                continue
            for hook in group.get("hooks", []):
                if "queue_agent_index.py" in hook.get("command", ""):
                    matching_hooks.append(hook)

        self.assertTrue(
            matching_hooks,
            "PostToolUse entry referencing queue_agent_index.py with a "
            "Task/Agent matcher must be registered",
        )
        for hook in matching_hooks:
            self.assertEqual(hook.get("timeout"), 15)
            self.assertIn("${CLAUDE_PLUGIN_ROOT}", hook.get("command", ""))
            self.assertIn("hooks/queue_agent_index.py", hook.get("command", ""))


class TestAgentIdentifierRecoveredFromBothLayouts(unittest.TestCase):
    """AC-10: the agent identifier is recovered both from a structured
    result field and from an identifier embedded in result text.

    Also covers task0005 AC-3: an identifier is recovered from each of the
    three text-bearing shapes -- an object whose content is a block list, an
    object whose content is a plain string, and a plain-string result --
    verified as three separate cases below."""

    def test_structured_field_is_recovered(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001", worktree_path, structured_result("agent-struct-1")
            )
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["agent_id"], "agent-struct-1")

    def test_embedded_text_identifier_is_recovered(self):
        """task0005 AC-3, case: object result, content is a block list."""
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001", worktree_path, embedded_text_result("agent-embedded-2")
            )
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["agent_id"], "agent-embedded-2")

    def test_content_plain_string_identifier_is_recovered(self):
        """task0005 AC-3 / F-2, case: object result, content is a plain
        string (the commonest tool-result shape, and the one that used to
        make the whole recorder a permanent no-op)."""
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001", worktree_path, content_string_result("agent-content-str-4")
            )
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["agent_id"], "agent-content-str-4")

    def test_plain_string_result_with_embedded_identifier_is_recovered(self):
        """task0005 AC-3, case: tool_response itself is a plain string (not
        an object) carrying the embedded identifier."""
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            payload = post_tool_use_payload(
                "task0001", worktree_path, "agentId: agent-plain-3"
            )
            proc = run_hook_payload(payload)
            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["agent_id"], "agent-plain-3")


class TestStructuredFieldSuppressesFreeTextCandidate(unittest.TestCase):
    """task0005 AC-1 (F-1 security regression guard): when the launch result
    carries at least one structured identifier field, no identifier
    harvested from free-text is recorded -- the candidate list contains
    ONLY structured-field values, even when the free-text carries a
    DIFFERENT, attacker-influenceable value."""

    def test_freetext_identifier_absent_when_structured_field_present(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            tool_response = {
                "status": "completed",
                "agentId": "agent-trusted",
                "content": [
                    {"type": "text", "text": "Report: agentId: agent-forged-evil"}
                ],
            }
            payload = post_tool_use_payload("task0001", worktree_path, tool_response)
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            entry = lines[0]
            self.assertEqual(entry["agent_ids"], ["agent-trusted"])
            self.assertEqual(entry["agent_id"], "agent-trusted")
            self.assertNotIn("agent-forged-evil", json.dumps(entry))


class TestRepresentativeMatchesFirstCandidate(unittest.TestCase):
    """task0005 AC-5: the recorded representative identifier (`agent_id`)
    always equals the first element of the recorded candidate list
    (`agent_ids`), asserted in a multi-candidate case."""

    def test_representative_is_first_of_agent_ids_list(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            tool_response = {
                "status": "completed",
                "agentId": "agent-first",
                "taskId": "agent-second",
                "content": [{"type": "text", "text": "Done."}],
            }
            payload = post_tool_use_payload("task0001", worktree_path, tool_response)
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            entry = lines[0]
            self.assertGreater(len(entry["agent_ids"]), 1)
            self.assertEqual(entry["agent_id"], entry["agent_ids"][0])
            self.assertEqual(entry["agent_ids"][0], "agent-first")


class TestMultipleStructuredSpellingsAllRecorded(unittest.TestCase):
    """task0005 AC-6: a launch result carrying two distinct structured
    identifier spellings with DIFFERENT values records both, in discovery
    order, with duplicates removed. Without this test, removing the
    candidate-list feature entirely still leaves the suite green (F-3)."""

    def test_two_distinct_structured_fields_both_recorded_in_order(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            tool_response = {
                "status": "completed",
                "agentId": "agent-alpha",
                "agent_id": "agent-alpha",  # duplicate value -> must collapse
                "taskId": "agent-beta",  # distinct spelling, distinct value
                "content": [{"type": "text", "text": "Done."}],
            }
            payload = post_tool_use_payload("task0001", worktree_path, tool_response)
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            lines = read_index_lines(worktree_path)
            self.assertEqual(len(lines), 1)
            entry = lines[0]
            self.assertEqual(entry["agent_ids"], ["agent-alpha", "agent-beta"])
            self.assertEqual(entry["agent_id"], "agent-alpha")


class TestEmbeddedPatternDoesNotMatchTaskAssignmentLine(unittest.TestCase):
    """task0005 AC-7 (design constraint): the embedded-text identifier
    pattern still does not match a task-assignment-style task id line --
    implementer prompts always contain a literal `task_id: task0001` line,
    which must never be misread as an agent identifier."""

    def test_task_assignment_style_line_is_not_misread_as_agent_id(self):
        with _tmp_worktree() as worktree_path:
            os.makedirs(worktree_path, exist_ok=True)
            tool_response = {
                "status": "completed",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "# Task assignment\n"
                            "task_id: task0001\n"
                            "worktree_path: /some/path/task0001\n"
                        ),
                    }
                ],
            }
            payload = post_tool_use_payload("task0001", worktree_path, tool_response)
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(read_index_lines(worktree_path), [])


class TestSymlinkAtIndexPathIsRefused(unittest.TestCase):
    """task0005 AC-8: with the index path replaced by a symlink to a file
    outside the feature directory, the hook exits 0 and the link target
    stays unwritten (O_NOFOLLOW defense in depth, Agent index contract)."""

    def test_symlink_index_path_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            feature_dir = os.path.join(tmp_root, "feature")
            worktree_path = os.path.join(feature_dir, "task0001")
            os.makedirs(worktree_path, exist_ok=True)

            outside_dir = os.path.join(tmp_root, "outside")
            os.makedirs(outside_dir, exist_ok=True)
            target_path = os.path.join(outside_dir, "target.jsonl")
            original_content = "sentinel\n"
            with open(target_path, "w", encoding="utf-8") as fh:
                fh.write(original_content)

            index_path = os.path.join(feature_dir, "agents.jsonl")
            os.symlink(target_path, index_path)

            payload = post_tool_use_payload(
                "task0001", worktree_path, structured_result("agent-sym-1")
            )
            proc = run_hook_payload(payload)

            self.assertEqual(proc.returncode, 0)
            self.assertTrue(os.path.islink(index_path))
            with open(target_path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), original_content)


class TestStdlibOnly(unittest.TestCase):
    """Technology Stack: standard library only, matching the three existing
    queue hooks (IMPLEMENTATION.md)."""

    def test_imports_are_all_stdlib(self):
        with open(HOOK_PATH, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=HOOK_PATH)

        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported, "expected at least one import in the hook script")
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


if __name__ == "__main__":
    unittest.main()
