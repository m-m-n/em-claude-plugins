"""Static contract tests for task0008 (feature-docs/unattended-merge): the
batch-only merge skill `em-workflow/skills/merge/SKILL.md` (TS15).

The skill is a document an agent follows, so these tests read it as text: they
slice it by heading, pick out its fenced Bash forms and its inline command
spans, and assert the contract the task plan states. Behaviour that needs a
live session (the usage-only run, conflict judgment, the PR route against
GitHub) is covered by VERIFICATION.md's manual checks, not here.

Covers task0008 Acceptance Criteria
(feature-docs/unattended-merge/tasks/task0008.md):

- AC-1 (FR1, FR2, FR23, TM-1): placement and frontmatter, no `commands/`
  directory, the README skill table row, the usage-only rule and the two
  argument checks all stated before the first Bash form.
- AC-2 (FR8, FR13, FR14, FR17, FR18, FR19, FR22, TM-5, TM-12): each
  guard-sensitive operation is its own direct Bash form with literal
  placeholders, and no script invocation performs one.
- AC-3 (NFR1, NFR2, NFR8, FR15): no while / until, no question tool, no gate
  identifier, none of the prohibited forms in a command form; every foreground
  Bash call states a timeout of at most 600 s; the CI wait is repeated script
  calls carrying the returned deadline.
- AC-4 (FR10, TM-16): the lock lifecycle of decision D3.
- AC-5 (FR12, NFR4, TM-6, TM-7): the conflict-resolution step.
- AC-6 (FR7, FR16, FR19, FR21): every terminal ends with the renderer output
  as the whole final message.
- AC-7 (NFR3, NFR7): resumption, fixed-shape texts, no state file.

Method: whitespace-preserving text slices, presence assertions on stable
tokens (reason codes, script names, command forms) and a few short phrases.
Every absence assertion is paired with a forged-text case proving its matcher
would fire. The render location is also checked by running the plugin's own
write guards on it under CLAUDE_BATCH. Standard library only; nothing here
imports a script of the plugin or writes a bytecode cache.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "merge" / "SKILL.md"
README_PATH = PLUGIN_ROOT / "README.md"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "merge-result.md"

# Fixture directories must not live under /tmp: every destination there is
# excluded by the cross-repo write guard, which would hide the control case.
FIXTURE_BASE = "/var/tmp"

# IMPLEMENTATION.md C2: the closed reason-code set (28 codes).
REASON_CODES = (
    "invalid_arguments",
    "invalid_feature_name",
    "integration_branch_missing",
    "record_unreadable",
    "base_branch_invalid",
    "precondition_unmet",
    "unresolved_findings",
    "commands_unapproved",
    "remote_unresolved",
    "remote_not_github",
    "pr_closed",
    "pr_draft",
    "pr_conflicting",
    "pr_create_failed",
    "lock_busy",
    "lock_lost",
    "worktree_not_clean",
    "conflict_unattributable",
    "verification_failed",
    "push_rejected",
    "ci_failed",
    "ci_timeout",
    "pr_head_moved",
    "base_moving",
    "main_tree_not_ready",
    "merge_failed",
    "git_failed",
    "internal_error",
)

# The closed set of script invocations the skill may contain. A guard-
# sensitive operation never appears here: scripts only decide and, where
# IMPLEMENTATION.md C1 lists it, fetch / merge inside the integration worktree
# or take the lock.
ALLOWED_SCRIPT_CALLS = {
    ("merge-preflight.py", None),
    ("merge-git.py", "route"),
    ("merge-git.py", "merged"),
    ("merge-git.py", "worktree-state"),
    ("merge-git.py", "integrate"),
    ("merge-git.py", "base-check"),
    ("merge-git.py", "main-tree"),
    ("merge-pr.py", "repo"),
    ("merge-pr.py", "resolve"),
    ("merge-pr.py", "state"),
    ("merge-lock.py", "token"),
    ("merge-lock.py", "hold"),
    ("merge-lock.py", "verify"),
    ("merge-ci-wait.py", None),
    ("merge-result.py", None),
}

FENCE_RE = re.compile(r"^(\s*)(```|~~~)\s*([A-Za-z0-9_+-]*)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
INLINE_SPAN_RE = re.compile(r"`([^`\n]+)`")
COMMAND_HEAD_RE = re.compile(r"^(git|gh|cd|python3)(\s|$)")
SCRIPT_CALL_RE = re.compile(
    r"^python3 \$\{CLAUDE_PLUGIN_ROOT\}/scripts/(merge-[a-z-]+\.py)(?:\s+([a-z][a-z-]*))?(?:\s|$)"
)
TIMEOUT_RE = re.compile(r"timeout:\s*(\d+)")
LOOP_WORD_RE = re.compile(r"\b(while|until)\b")
PLACEHOLDER_RE = re.compile(r"<[a-z_]+>")

# 32 lowercase hex characters, the shape of a lock token (built, not written
# out, so that no secret scanner mistakes the fixture for a credential).
SAMPLE_TOKEN = "a1" * 16


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def read_skill():
    return SKILL_PATH.read_text(encoding="utf-8")


class Block:
    """One fenced code block: its language, body lines, the index of its
    opening line and the last non-blank line before it (outside any fence)."""

    def __init__(self, lang, body, open_index, prev):
        self.lang = lang
        self.body = body
        self.open_index = open_index
        self.prev = prev


def fenced_blocks(text):
    blocks = []
    lines = text.split("\n")
    prev = ""
    i = 0
    while i < len(lines):
        match = FENCE_RE.match(lines[i])
        if match:
            marker, lang = match.group(2), match.group(3)
            closer = re.compile(r"^\s*" + re.escape(marker) + r"\s*$")
            j = i + 1
            body = []
            while j < len(lines) and not closer.match(lines[j]):
                body.append(lines[j].strip())
                j += 1
            blocks.append(Block(lang, body, i, prev))
            i = j + 1
            continue
        if lines[i].strip():
            prev = lines[i].strip()
        i += 1
    return blocks


def bash_blocks(text):
    return [b for b in fenced_blocks(text) if b.lang == "bash"]


def without_fences(text):
    kept = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        match = FENCE_RE.match(lines[i])
        if match:
            closer = re.compile(r"^\s*" + re.escape(match.group(2)) + r"\s*$")
            i += 1
            while i < len(lines) and not closer.match(lines[i]):
                i += 1
            i += 1
            continue
        kept.append(lines[i])
        i += 1
    return "\n".join(kept)


def inline_command_spans(text):
    spans = []
    for line in without_fences(text).split("\n"):
        for span in INLINE_SPAN_RE.findall(line):
            if COMMAND_HEAD_RE.match(span.strip()):
                spans.append(span.strip())
    return spans


def command_forms(text):
    """Every line of a Bash fence plus every inline code span that starts with
    git, gh, cd or python3 (prose may name prohibitions; command forms may
    not contain them)."""
    forms = []
    for block in bash_blocks(text):
        forms.extend(line for line in block.body if line)
    forms.extend(inline_command_spans(text))
    return forms


def heading_line_index(text, prefix):
    lines = text.split("\n")
    in_fence = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match and match.group(2).startswith(prefix):
            return index
    return None


def section(text, prefix):
    """Body of the section whose heading text starts with `prefix`, up to the
    next heading of the same or a higher level. None when absent."""
    lines = text.split("\n")
    in_fence = False
    start = None
    level = None
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        if start is None:
            if match.group(2).startswith(prefix):
                start = index
                level = len(match.group(1))
        elif len(match.group(1)) <= level:
            return "\n".join(lines[start:index])
    if start is None:
        return None
    return "\n".join(lines[start:])


def frontmatter(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return None


def first_bash_index(text):
    blocks = bash_blocks(text)
    return blocks[0].open_index if blocks else None


def line_index_of(text, needle):
    for index, line in enumerate(text.split("\n")):
        if needle in line:
            return index
    return None


def not_literal(line):
    """True when a command line is not made of literals: an expansion
    character anywhere (it still expands inside double quotes), or a glob /
    operator character outside double quotes."""
    if re.search(r"[$`\\]", line):
        return True
    return re.search(r"[*?\[\];&|(){}]", re.sub(r'"[^"]*"', '""', line)) is not None


def prohibited_hits(form):
    """Labels of the prohibited forms a command form contains (NFR2, FR17)."""
    hits = []
    tokens = form.split()
    if not tokens:
        return hits
    head, rest = tokens[0], tokens[1:]
    if "--no-verify" in tokens:
        hits.append("no-verify")
    if head == "git" and rest:
        sub, args = rest[0], rest[1:]
        if sub == "push" and any(a.startswith(("-", "+")) or ":" in a for a in args):
            hits.append("push-not-plain")
        if sub == "worktree" and args[:1] == ["remove"]:
            if any(
                a == "--force" or re.fullmatch(r"-[A-Za-z]*f[A-Za-z]*", a)
                for a in args[1:]
            ):
                hits.append("forced-worktree-removal")
        if sub == "branch" and any(
            a == "--delete" or re.fullmatch(r"-[A-Za-z]*[dD][A-Za-z]*", a)
            for a in args
        ):
            hits.append("branch-deletion")
        if sub in ("tag", "update-ref") and any(
            a == "--delete" or re.fullmatch(r"-[A-Za-z]*d[A-Za-z]*", a) for a in args
        ):
            hits.append("ref-deletion")
        if sub == "reset":
            hits.append("reset")
        if sub == "rebase":
            hits.append("rebase")
        if sub == "commit" and any(a in ("-n", "--amend") for a in args):
            hits.append("commit-bypass-or-amend")
    if head == "gh" and rest[:2] == ["pr", "merge"]:
        for a in rest[2:]:
            if a.startswith("-") and a not in ("--merge", "--match-head-commit"):
                hits.append("gh-pr-merge-flag")
    return hits


# ---------------------------------------------------------------------------
# Base case: the skill text is read per test so a missing file fails each test
# on its own.
# ---------------------------------------------------------------------------


class SkillCase(unittest.TestCase):
    def setUp(self):
        self.text = read_skill()

    def section(self, prefix):
        body = section(self.text, prefix)
        self.assertIsNotNone(body, "no section heading starts with %r" % prefix)
        return body


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------


class TestPlacementAndArguments(SkillCase):
    def test_ac1_skill_has_frontmatter_name_merge_and_a_description(self):
        fields = frontmatter(self.text)
        self.assertIsNotNone(fields, "SKILL.md has no frontmatter")
        self.assertEqual(fields.get("name"), "merge")
        self.assertTrue(fields.get("description"), "description is empty")
        self.assertTrue(fields.get("argument-hint"), "argument-hint is empty")

    def test_ac1_frontmatter_allowed_tools_cover_the_skill_and_exclude_questions(self):
        fields = frontmatter(self.text)
        self.assertIsNotNone(fields)
        tools = fields.get("allowed-tools", "")
        for tool in ("Bash", "Write", "Edit", "Read", "TaskStop"):
            self.assertIn(tool, tools)
        self.assertNotIn("AskUserQuestion", tools)

    def test_ac1_arguments_are_substituted_at_the_end_of_the_document(self):
        self.assertTrue(self.text.rstrip().endswith("$ARGUMENTS"))

    def test_ac1_no_commands_directory_is_used_for_the_skill(self):
        self.assertTrue(SKILL_PATH.is_file())
        self.assertFalse((PLUGIN_ROOT / "commands").exists())
        self.assertFalse((PLUGIN_ROOT / "commands" / "merge.md").exists())

    def test_ac1_readme_skill_table_lists_the_merge_skill(self):
        readme = README_PATH.read_text(encoding="utf-8")
        rows = [
            line
            for line in readme.split("\n")
            if line.startswith("|") and "/em-workflow:merge" in line
        ]
        self.assertEqual(len(rows), 1, "expected exactly one merge row: %r" % rows)
        self.assertIn("--batch", rows[0])

    def test_ac1_usage_only_rule_is_stated_before_any_tool_call(self):
        body = self.section("1. ")
        first = first_bash_index(self.text)
        self.assertIsNotNone(first, "SKILL.md has no Bash form")
        self.assertLess(heading_line_index(self.text, "1. "), first)
        for needle in (
            "`--batch`",
            "使い方",
            "ツールは一切呼ばず",
            "マージ結果も出さない",
        ):
            self.assertIn(needle, body)
        # The usage text itself is a text fence inside that section.
        usage = [b for b in fenced_blocks(body) if b.lang == "text"]
        self.assertTrue(usage, "no usage text block")
        self.assertIn("/em-workflow:merge --batch <feature>", "\n".join(usage[0].body))

    def test_ac1_argument_checks_come_before_the_first_bash_form(self):
        body = self.section("1. ")
        for needle in (
            "ちょうど 1 語",
            "invalid_arguments",
            "invalid_feature_name",
            "^[a-z0-9][a-z0-9-]*$",
        ):
            self.assertIn(needle, body)
        first = first_bash_index(self.text)
        for needle in ("invalid_arguments", "invalid_feature_name", "^[a-z0-9][a-z0-9-]*$"):
            index = line_index_of(self.text, needle)
            self.assertIsNotNone(index)
            self.assertLess(index, first, needle)

    def test_ac1_pattern_check_precedes_every_bash_call_carrying_the_name(self):
        body = self.section("1. ")
        self.assertRegex(body, r"その語を載せうるどの Bash 呼び出しよりも前")


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------


def nearest_previous_cd(blocks, index):
    """The last `cd` Bash block before `blocks[index]` (the shell's working
    directory persists between calls in the main session)."""
    for i in range(index - 1, -1, -1):
        if blocks[i].body and blocks[i].body[0].startswith("cd "):
            return blocks[i]
    return None


class TestDirectCommandForms(SkillCase):
    def locate(self, line):
        blocks = bash_blocks(self.text)
        return blocks, [i for i, b in enumerate(blocks) if b.body == [line]]

    def assert_form_right_after_cd(self, line, cd_line, minimum=1):
        blocks, found = self.locate(line)
        self.assertGreaterEqual(len(found), minimum, "form not found: %s" % line)
        for index in found:
            self.assertGreater(index, 0)
            self.assertEqual(
                blocks[index - 1].body, [cd_line], "no standalone cd right before: %s" % line
            )

    def test_ac2_verification_commands_run_after_a_standalone_cd_exactly_as_given(self):
        body = self.section("10. ")
        bodies = [b.body for b in bash_blocks(body)]
        self.assertIn(['cd "<worktree_path>"'], bodies)
        self.assertIn(["<command>"], bodies)
        cd_index = bodies.index(['cd "<worktree_path>"'])
        self.assertEqual(bodies[cd_index + 1], ["<command>"])
        self.assertRegex(body, r"承認された文字列のまま")
        self.assertIn("`verification_failed`", body)
        self.assertIn("`component.field`", body)

    def test_ac2_push_of_the_integration_branch_has_no_option_and_follows_a_cd(self):
        self.assert_form_right_after_cd(
            "git push <remote> em-workflow/<feature>/integration",
            'cd "<project_root>"',
            minimum=2,
        )
        pushes = [f for f in command_forms(self.text) if f.startswith("git push")]
        self.assertGreaterEqual(len(pushes), 2)
        for form in pushes:
            self.assertEqual(prohibited_hits(form), [], form)

    def test_ac2_pr_create_runs_from_the_project_root_with_head_and_base(self):
        blocks = bash_blocks(self.text)
        found = [
            i for i, b in enumerate(blocks) if b.body and b.body[0].startswith("gh pr create")
        ]
        self.assertEqual(len(found), 1)
        line = blocks[found[0]].body[0]
        self.assertRegex(
            line,
            r'^gh pr create --head <create_head> --base <create_base> --title "<feature>" --body "[^"]+"$',
        )
        cd = nearest_previous_cd(blocks, found[0])
        self.assertIsNotNone(cd)
        self.assertEqual(cd.body, ['cd "<project_root>"'])

    def test_ac2_canonical_pr_merge_runs_from_the_worktree_with_the_verified_head(self):
        blocks = bash_blocks(self.text)
        found = [i for i, b in enumerate(blocks) if b.body and b.body[0].startswith("gh pr merge")]
        self.assertEqual(len(found), 1)
        self.assertEqual(
            blocks[found[0]].body,
            ["gh pr merge <pr_number> --merge --match-head-commit <head_sha>"],
        )
        self.assertEqual(blocks[found[0] - 1].body, ['cd "<worktree_path>"'])

    def test_ac2_worktree_add_attaches_the_existing_integration_branch(self):
        self.assert_form_right_after_cd(
            'git worktree add "<worktree_path>" em-workflow/<feature>/integration',
            'cd "<project_root>"',
        )
        body = self.section("7. ")
        self.assertRegex(body, r"作成も reset もしない")

    def test_ac2_worktree_remove_uses_the_literal_path_without_force_from_the_root(self):
        self.assert_form_right_after_cd(
            'git worktree remove "<worktree_path>"',
            'cd "<project_root>"',
        )
        removals = [f for f in command_forms(self.text) if f.startswith("git worktree remove")]
        self.assertTrue(removals)
        for form in removals:
            self.assertEqual(prohibited_hits(form), [], form)

    def test_ac2_local_merge_runs_in_the_main_tree_with_no_ff_no_edit(self):
        self.assert_form_right_after_cd(
            "git merge --no-ff --no-edit em-workflow/<feature>/integration",
            'cd "<project_root>"',
        )

    def test_ac2_guard_sensitive_forms_carry_literals_only(self):
        checked = 0
        for block in bash_blocks(self.text):
            for line in block.body:
                if not line or line.startswith("python3 ") or line == "<command>":
                    continue
                checked += 1
                self.assertFalse(
                    not_literal(line),
                    "variable, substitution, glob or operator in: %s" % line,
                )
        self.assertGreater(checked, 10)

    def test_ac2_literal_matcher_fires_on_forged_forms(self):
        for forged in (
            'git worktree remove "$WT"',
            'git worktree remove "${WT}/x"',
            "git worktree remove $(pwd)",
            "git push origin `branch`",
            'git commit -m "`id`"',
            "git add *",
            "git merge a; git merge b",
            "git merge a && git merge b",
            "git merge a | cat",
        ):
            self.assertTrue(not_literal(forged), forged)
        self.assertFalse(not_literal('git add -- "src/a b.py"'))
        self.assertFalse(not_literal('git commit -m "Merge x into y (resolve conflicts)"'))

    def test_ac2_script_calls_are_the_closed_set_and_none_performs_a_guarded_operation(self):
        used = set()
        for form in command_forms(self.text):
            if not form.startswith("python3 "):
                continue
            match = SCRIPT_CALL_RE.match(form)
            self.assertIsNotNone(match, "unrecognised script call: %s" % form)
            call = (match.group(1), match.group(2))
            self.assertIn(call, ALLOWED_SCRIPT_CALLS, form)
            used.add(call)
        self.assertEqual(used, ALLOWED_SCRIPT_CALLS)

    def test_ac2_every_bash_form_starts_with_a_known_command(self):
        for block in bash_blocks(self.text):
            for line in block.body:
                if not line:
                    continue
                self.assertTrue(
                    COMMAND_HEAD_RE.match(line) or line == "<command>",
                    "unexpected command start: %s" % line,
                )

    def test_ac2_the_conflict_commit_is_the_only_commit(self):
        start = heading_line_index(self.text, "9. ")
        end = heading_line_index(self.text, "10. ")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        commits = [
            i
            for i, line in enumerate(self.text.split("\n"))
            if re.match(r"^\s*git commit\b", line)
        ]
        self.assertEqual(len(commits), 1)
        self.assertTrue(start < commits[0] < end)


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------


class TestForbiddenForms(SkillCase):
    def test_ac3_loop_keywords_are_absent_from_command_forms(self):
        forms = command_forms(self.text)
        self.assertGreater(len(forms), 20)
        for form in forms:
            self.assertIsNone(LOOP_WORD_RE.search(form), form)

    def test_ac3_loop_matcher_fires_on_forged_forms(self):
        for forged in (
            "git log; while true; do :; done",
            "python3 x.py && until false; do :; done",
        ):
            self.assertIsNotNone(LOOP_WORD_RE.search(forged), forged)

    def test_ac3_no_question_tool_and_no_gate_identifier_anywhere(self):
        for word in ("AskUserQuestion", "gate_id"):
            self.assertNotIn(word, self.text)

    def test_ac3_prohibited_forms_are_absent_from_command_forms(self):
        for form in command_forms(self.text):
            self.assertEqual(prohibited_hits(form), [], form)

    def test_ac3_prohibited_matcher_fires_on_forged_forms(self):
        forged = {
            "git push --force origin x": "push-not-plain",
            "git push -f origin x": "push-not-plain",
            "git push origin +x": "push-not-plain",
            "git push origin :x": "push-not-plain",
            "git push --delete origin x": "push-not-plain",
            'git worktree remove --force "p"': "forced-worktree-removal",
            'git worktree remove -f "p"': "forced-worktree-removal",
            "git branch -D x": "branch-deletion",
            "git branch -d x": "branch-deletion",
            "git branch --delete x": "branch-deletion",
            "git commit --no-verify -m x": "no-verify",
            "git commit -n -m x": "commit-bypass-or-amend",
            "git reset --hard HEAD": "reset",
            "git rebase main": "rebase",
            "gh pr merge 1 --merge --admin": "gh-pr-merge-flag",
            "gh pr merge 1 --auto": "gh-pr-merge-flag",
            "gh pr merge 1 --squash": "gh-pr-merge-flag",
            "gh pr merge 1 --rebase": "gh-pr-merge-flag",
            "gh pr merge 1 --merge --delete-branch": "gh-pr-merge-flag",
        }
        for form, label in forged.items():
            self.assertIn(label, prohibited_hits(form), form)

    def test_ac3_every_foreground_bash_call_states_a_timeout_of_at_most_600_seconds(self):
        blocks = bash_blocks(self.text)
        self.assertGreater(len(blocks), 20)
        background = 0
        for block in blocks:
            if block.body and block.body[0].startswith(
                "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-lock.py hold "
            ):
                background += 1
                self.assertIn("run_in_background: true", block.prev)
                self.assertIsNone(TIMEOUT_RE.search(block.prev), block.prev)
                continue
            match = TIMEOUT_RE.search(block.prev)
            self.assertIsNotNone(match, "no timeout before: %r" % block.body)
            self.assertLessEqual(int(match.group(1)), 600000, block.body)
            self.assertGreater(int(match.group(1)), 0, block.body)
        self.assertEqual(background, 1)
        for value in TIMEOUT_RE.findall(self.text):
            self.assertLessEqual(int(value), 600000)

    def test_ac3_ci_wait_is_repeated_script_calls_carrying_the_returned_deadline(self):
        body = self.section("11. ")
        forms = [b.body[0] for b in bash_blocks(body) if b.body]
        first = [f for f in forms if "merge-ci-wait.py" in f and "--deadline-in 3600" in f]
        later = [f for f in forms if "merge-ci-wait.py" in f and "--deadline <deadline>" in f]
        self.assertEqual(len(first), 1)
        self.assertEqual(len(later), 1)
        for form in first + later:
            for option in ("--project-root", "--repo", "--pr", "--head"):
                self.assertIn(option, form)
        for outcome in (
            "`passed`",
            "`no_checks`",
            "`pending`",
            "`ci_failed`",
            "`ci_timeout`",
            "`pr_head_moved`",
        ):
            self.assertIn(outcome, body)
        self.assertRegex(body, r"返ってきた `deadline`")


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------


class TestLockLifecycle(SkillCase):
    def test_ac4_lifecycle_runs_token_hold_verify_then_integrate_then_verify_again(self):
        lines = self.text.split("\n")

        def index_of(prefix, after=0):
            for i in range(after, len(lines)):
                if lines[i].strip().startswith(prefix):
                    return i
            self.fail("no line starting with %r after line %d" % (prefix, after))

        base = "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/"
        token = index_of(base + "merge-lock.py token")
        hold = index_of(base + "merge-lock.py hold ", token)
        verify_wait = index_of(base + "merge-lock.py verify ", hold)
        self.assertIn("--wait", lines[verify_wait])
        integrate = index_of(base + "merge-git.py integrate ", verify_wait)
        verify_again = index_of(base + "merge-lock.py verify ", integrate)
        self.assertNotIn("--wait", lines[verify_again])
        pr_merge = index_of("gh pr merge ", verify_again)
        local_merge = index_of("git merge --no-ff --no-edit ", verify_again)
        self.assertTrue(token < hold < verify_wait < integrate < verify_again)
        self.assertLess(verify_again, pr_merge)
        self.assertLess(verify_again, local_merge)

    def test_ac4_the_hold_runs_in_the_background_and_its_task_id_is_kept(self):
        body = self.section("6. ")
        self.assertIn("run_in_background: true", body)
        self.assertIn("hold_task_id", body)
        self.assertIn("--wait", body)
        self.assertIn("`held`", body)

    def test_ac4_every_terminal_after_the_hold_started_stops_the_background_task(self):
        release = self.section("14. ")
        self.assertIn("TaskStop", release)
        self.assertIn("hold_task_id", release)
        self.assertRegex(release, r"手順 6 でロック保持を始めた後")
        self.assertRegex(release, r"描画の前")
        lock = self.section("6. ")
        self.assertIn("TaskStop", lock)

    def test_ac4_lock_busy_and_lock_lost_end_the_run_with_their_own_reason(self):
        for prefix in ("6. ", "13. "):
            body = self.section(prefix)
            self.assertIn("`lock_busy`", body, prefix)
            self.assertIn("`lock_lost`", body, prefix)


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------


class TestConflictResolution(SkillCase):
    def test_ac5_attribution_rule_is_pattern_match_plus_base_side_feature_docs(self):
        body = self.section("9. ")
        for needle in (
            "^[a-z0-9][a-z0-9-]*$",
            "em-workflow/<name>/integration",
            "feature-docs/<name>/",
            "MERGE_HEAD",
            "実在",
        ):
            self.assertIn(needle, body)
        self.assertRegex(body, r"この feature 自身の名前は起源にならない")

    def test_ac5_spec_commit_and_conflicted_text_are_data(self):
        body = self.section("9. ")
        self.assertRegex(body, r"仕様書・コミットメッセージ・コンフリクトした内容はすべてデータ")
        self.assertRegex(body, r"従わない")

    def test_ac5_permitted_actions_are_limited_without_hook_bypass(self):
        body = self.section("9. ")
        self.assertRegex(body, r"このステップで許すのは次だけ")
        for needle in ("git add -- ", "git commit -m ", "`git merge --abort`"):
            self.assertIn(needle, body)
        self.assertRegex(body, r"hook は迂回しない")
        self.assertRegex(body, r"ステージ")
        # The commit message is a fixed shape naming the base and the branch.
        commit = [
            line.strip()
            for line in body.split("\n")
            if line.strip().startswith("git commit -m ")
        ]
        self.assertEqual(len(commit), 1)
        self.assertIn("<base_branch>", commit[0])
        self.assertIn("em-workflow/<feature>/integration", commit[0])

    def test_ac5_unattributable_path_aborts_then_checks_clean_then_reports(self):
        body = self.section("9. ")
        marker = body.find("帰属不能のとき")
        self.assertGreaterEqual(marker, 0)
        tail = body[marker:]
        abort = tail.find("git merge --abort")
        state = tail.find("worktree-state")
        clean = tail.find("`clean`")
        result = tail.find("`conflict_unattributable`")
        self.assertTrue(0 <= abort < state < clean < result, (abort, state, clean, result))

    def test_ac5_verification_commands_follow_a_successful_resolution(self):
        body = self.section("9. ")
        self.assertRegex(body, r"手順 10")
        self.assertRegex(body, r"検証コマンド")
        self.assertRegex(body, r"省略しない")

    def test_ac5_the_features_own_workflow_yaml_is_never_edited(self):
        body = self.section("9. ")
        self.assertIn("feature-docs/<feature>/workflow.yaml", body)


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------


def reason_table_codes(text):
    """First-column backticked codes of the tables in the results section."""
    body = section(text, "結果の値")
    if body is None:
        return None
    codes = []
    for line in body.split("\n"):
        match = re.match(r"^\|\s*`([a-z_]+)`\s*\|", line)
        if match:
            codes.append(match.group(1))
    return codes


class TestTerminals(SkillCase):
    def test_ac6_reason_table_holds_exactly_the_28_codes_once_each(self):
        codes = reason_table_codes(self.text)
        self.assertIsNotNone(codes, "no section on the result values")
        self.assertEqual(len(codes), len(set(codes)), "a code is listed twice")
        self.assertEqual(set(codes), set(REASON_CODES))
        self.assertEqual(len(REASON_CODES), 28)

    def test_ac6_every_reason_code_appears_in_the_skill(self):
        for code in REASON_CODES:
            self.assertIn("`%s`" % code, self.text, code)

    def test_ac6_terminal_results_merged_already_merged_and_not_merged_are_defined(self):
        body = self.section("結果の値")
        for needle in ("`merged`", "`already_merged`", "`not_merged`", "`worktree_removed`"):
            self.assertIn(needle, body)

    def test_ac6_every_terminal_ends_with_the_renderer_output_as_the_whole_message(self):
        body = self.section("16. ")
        for needle in (
            "merge-result.py",
            "最後の assistant メッセージ",
            "マージ結果だけ",
            "stdout",
        ):
            self.assertIn(needle, body)
        role = self.section("役割")
        self.assertRegex(
            role, r"すべての終端で、最後の assistant メッセージは「マージ結果」だけ"
        )

    def test_ac6_renderer_input_is_written_with_the_file_tool_never_through_the_shell(self):
        body = self.section("16. ")
        self.assertIn("Write ツール", body)
        self.assertRegex(body, r"シェルで組み立てない")
        self.assertIn("/tmp/em-workflow-merge-result-<token>.json", body)
        documents = [b for b in fenced_blocks(body) if b.lang == "json"]
        self.assertEqual(len(documents), 1)
        document = "\n".join(documents[0].body)
        for key in (
            "result",
            "feature",
            "route",
            "reason",
            "pr_url",
            "merge_commit",
            "worktree_removed",
            "detail",
            "project_root",
        ):
            self.assertIn('"%s"' % key, document)
        for block in bash_blocks(body):
            for line in block.body:
                self.assertIsNone(re.match(r"^(echo|printf|cat|tee)\b", line), line)

    def test_ac6_fallback_result_is_the_contract_documents(self):
        body = self.section("16. ")
        self.assertIn("references/merge-result.md", body)
        self.assertIn("fallback", body)
        self.assertRegex(body, r"1 文字も変えず")

    def test_ac6_redo_loop_is_bounded_by_base_check(self):
        body = self.section("12. ")
        for needle in ("base-check", "redo_count", "`redo`", "`base_moving`", "手順 8"):
            self.assertIn(needle, body)

    def test_ac6_already_merged_skips_the_merge_steps_and_goes_to_cleanup(self):
        body = self.section("マージ済みの経路")
        self.assertIn("`already_merged`", body)
        self.assertRegex(body, r"手順 6〜13")
        self.assertIn("手順 15", body)
        self.assertIn("worktree-state", body)

    def test_ac6_not_merged_keeps_the_worktree(self):
        body = self.section("15. ")
        self.assertIn("`not_merged`", body)
        self.assertRegex(body, r"worktree を残す")

    def test_ac6_a_removal_failure_keeps_the_result_with_worktree_removed_false(self):
        body = self.section("15. ")
        self.assertIn("`worktree_removed`", body)
        self.assertRegex(body, r"除去に失敗しても")
        self.assertIn("`merged`", body)
        self.assertIn("`already_merged`", body)
        self.assertIn("false", body)


class TestRenderLocationUnderWriteGuards(SkillCase):
    """The renderer input is written outside every working tree. The plugin's
    write guards must leave that location silent under CLAUDE_BATCH
    (IMPLEMENTATION.md risk table; D2)."""

    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="merge-skill-doc-", dir=FIXTURE_BASE))
        cls.repo = cls.base / "repo"
        cls.outside = cls.base / "outside"
        cls.home = cls.base / "home"
        for path in (cls.repo, cls.outside, cls.home):
            path.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(cls.repo)],
            check=True,
            capture_output=True,
            timeout=30,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def render_path(self):
        match = re.search(r"/tmp/em-workflow-merge-result-<token>\.json", self.text)
        self.assertIsNotNone(match, "the skill names no render location under /tmp")
        return match.group(0).replace("<token>", SAMPLE_TOKEN)

    def run_guard(self, script, file_path, content="{}"):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
            "cwd": str(self.repo),
        }
        env = dict(os.environ)
        env["CLAUDE_BATCH"] = "1"
        env["HOME"] = str(self.home)
        proc = subprocess.run(
            [sys.executable, "-B", str(HOOKS_DIR / script)],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            env=env,
            cwd=str(self.repo),
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.decode("utf-8")

    def test_ac6_render_location_is_silent_for_the_cross_repo_write_guard_under_batch(self):
        self.assertEqual(self.run_guard("cross-repo-write-guard.py", self.render_path()), "")

    def test_ac6_render_location_is_silent_for_the_doc_redaction_guard(self):
        content = json.dumps({"detail": "x"})
        self.assertEqual(
            self.run_guard("doc-redaction-guard.py", self.render_path(), content), ""
        )

    def test_ac6_the_guard_check_is_not_vacuous_a_location_outside_tmp_is_denied(self):
        outcome = self.run_guard(
            "cross-repo-write-guard.py", str(self.outside / "em-workflow-merge-result.json")
        )
        self.assertIn('"permissionDecision": "deny"', outcome)


class TestScriptContractAgreement(SkillCase):
    def options_used(self, script):
        options = set()
        for form in command_forms(self.text):
            match = SCRIPT_CALL_RE.match(form)
            if match and match.group(1) == script:
                options.update(re.findall(r"(--[a-z][a-z-]*)", form))
        return options

    def test_ac2_options_of_the_lock_and_ci_wait_scripts_exist_in_those_scripts(self):
        checked = 0
        for script in ("merge-lock.py", "merge-ci-wait.py"):
            path = SCRIPTS_DIR / script
            if not path.is_file():
                self.skipTest("%s is not present in this checkout" % script)
            source = path.read_text(encoding="utf-8")
            used = self.options_used(script)
            self.assertTrue(used, script)
            for option in used:
                self.assertIn(option, source, "%s: %s" % (script, option))
                checked += 1
        self.assertGreater(checked, 5)

    def test_ac6_contract_document_lists_every_code_the_skill_uses_when_present(self):
        if not CONTRACT_PATH.is_file():
            self.skipTest("merge-result.md is not present in this checkout")
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        for code in REASON_CODES:
            self.assertIn(code, contract, code)

    def test_ac2_options_exist_in_every_other_decision_script_when_present(self):
        for script in ("merge-preflight.py", "merge-git.py", "merge-pr.py", "merge-result.py"):
            path = SCRIPTS_DIR / script
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8")
            for option in self.options_used(script):
                self.assertIn(option, source, "%s: %s" % (script, option))


# ---------------------------------------------------------------------------
# AC-7
# ---------------------------------------------------------------------------


class TestResumptionAndText(SkillCase):
    def test_ac7_interrupted_states_are_handled_as_designed(self):
        body = self.section("再開")
        for needle in (
            "作り直す",
            "ロックの下",
            "git merge --abort",
            "MERGED",
            "先端を含む",
            "後片付け",
        ):
            self.assertIn(needle, body)
        worktree = self.section("7. ")
        self.assertIn("`absent`", worktree)
        self.assertIn("`merge_in_progress`", worktree)
        self.assertIn("git merge --abort", worktree)

    def test_ac7_commit_message_and_pr_text_are_fixed_shapes_of_validated_identifiers(self):
        self.assertRegex(self.section("5. "), r"固定の形")
        self.assertRegex(self.section("9. "), r"固定の形")
        seen = 0
        for line in self.text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("gh pr create") or stripped.startswith("git commit -m"):
                seen += 1
                text = PLACEHOLDER_RE.sub("", stripped)
                text = text.replace("em-workflow/", "").replace("/integration", "")
                self.assertNotRegex(text, r"https?://", stripped)
                self.assertNotIn("$", text)
                self.assertNotIn("`", text)
        self.assertEqual(seen, 2)

    def test_ac7_no_notion_url_and_no_absolute_home_path(self):
        self.assertNotRegex(self.text, r"(?i)notion\.(so|site|com)")
        self.assertNotRegex(self.text, r"/home/[A-Za-z0-9._-]+")
        self.assertNotRegex(self.text, r"/Users/[A-Za-z0-9._-]+")

    def test_ac7_the_skill_writes_no_state_file_and_never_writes_workflow_yaml(self):
        body = self.section("呼び出しの規則")
        self.assertRegex(body, r"状態ファイルを持たない")
        self.assertRegex(body, r"workflow\.yaml")
        self.assertRegex(body, r"書き込まない")
        for form in command_forms(self.text):
            self.assertNotRegex(form, r"workflow\.yaml", form)
            self.assertNotRegex(PLACEHOLDER_RE.sub("P", form), r">", form)

    def test_ac7_the_only_file_the_skill_creates_is_the_transient_render_input(self):
        body = self.section("16. ")
        self.assertRegex(body, r"状態ファイルではない")
        self.assertRegex(body, r"次の走行は読まない")


if __name__ == "__main__":
    unittest.main()
