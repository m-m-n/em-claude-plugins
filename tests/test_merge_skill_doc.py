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

Covers task0010 Acceptance Criterion AC-6
(feature-docs/unattended-merge/tasks/task0010.md; TestPrDecisionBindings): every
`merge-pr.py state` form passes `--base <base_branch>`, the `merge-pr.py
resolve` forms of steps 5.2 and 5.3 pass `--integration-tip <integration_tip>`
and the post-merge form of step 13.2 passes `--integration-tip <head_sha>`.

Covers unattended-merge-medium-fixes task0001 Acceptance Criteria
(feature-docs/unattended-merge-medium-fixes/tasks/task0001.md; the classes
TestLocalMergeBoundToHeadSha, TestStep10HeadCheckRunsInTheWorktree,
TestPostLockMergedRedecision and TestHostQualifiedRepository, plus the two
assertions adjusted in TestDirectCommandForms and TestPrDecisionBindings):

- AC-1, AC-2 (FR1, TM-5): the local merge only lands the verified head_sha
  (integration-tip read before the merge), and a second parent that differs
  from it or cannot be read keeps the result `merged` with a one-line detail.
- AC-3 (FR2): the step-10 HEAD check is preceded by its own worktree cd.
- AC-4, AC-5 (FR3, TM-6): the merged decision is repeated once the lock is
  held, and the already-merged path accepts that entry.
- AC-6 (FR5): `repo` is the host-qualified `HOST/OWNER/NAME` and every later
  `--repo` receives it as is.

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
        # unattended-merge-medium-fixes task0001 AC-1: the integration-tip read
        # now sits between the project-root cd and the merge, so the guarantee
        # about the merge's working directory is the nearest previous cd.
        blocks, found = self.locate("git merge --no-ff --no-edit em-workflow/<feature>/integration")
        self.assertEqual(len(found), 1, "expected exactly one local merge form")
        cd = nearest_previous_cd(blocks, found[0])
        self.assertIsNotNone(cd, "no cd before the local merge")
        self.assertEqual(cd.body, ['cd "<project_root>"'])
        self.assertGreater(found[0], 0)
        before = blocks[found[0] - 1].body
        self.assertEqual(len(before), 1)
        self.assertRegex(
            before[0],
            r"^git rev-parse\b.* refs/heads/em-workflow/<feature>/integration$",
            "the block right before the merge is not the integration-tip read",
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
        self.assertFalse(not_literal('git --literal-pathspecs add -- "src/a b.py"'))
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
        for needle in (
            "git --literal-pathspecs add -- ",
            "git --literal-pathspecs rm -- ",
            "git commit -m ",
            "`git merge --abort`",
        ):
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


# ---------------------------------------------------------------------------
# task0010 AC-6 (feature-docs/unattended-merge, FR7, FR8, FR9): the PR
# decisions are bound to the current base and the current integration tip
# ---------------------------------------------------------------------------

MERGE_PR_FORM_RE = re.compile(
    r"^python3 \$\{CLAUDE_PLUGIN_ROOT\}/scripts/merge-pr\.py (repo|resolve|state)(?:\s|$)"
)


def merge_pr_forms(text, subcommand):
    """Every command form of `text` that calls `merge-pr.py <subcommand>`."""
    found = []
    for form in command_forms(text):
        match = MERGE_PR_FORM_RE.match(form)
        if match and match.group(1) == subcommand:
            found.append(form)
    return found


def has_option(form, option, value):
    """True when `form` carries `option` immediately followed by `value`."""
    tokens = form.split()
    return any(
        tokens[i] == option and tokens[i + 1] == value for i in range(len(tokens) - 1)
    )


class TestPrDecisionBindings(SkillCase):
    def test_ac6_every_state_form_passes_the_base_branch(self):
        forms = merge_pr_forms(self.text, "state")
        self.assertTrue(forms, "no merge-pr.py state form")
        for form in forms:
            self.assertTrue(has_option(form, "--base", "<base_branch>"), form)

    def test_ac6_step_5_2_resolve_passes_the_integration_tip_from_preflight(self):
        body = self.section("5. ")
        forms = merge_pr_forms(body, "resolve")
        self.assertEqual(len(forms), 1, forms)
        self.assertTrue(has_option(forms[0], "--integration-tip", "<integration_tip>"), forms[0])

    def test_ac6_step_5_3_re_resolve_passes_the_integration_tip_from_preflight(self):
        body = self.section("5. ")
        marker = "3. `none` のときの PR 作成"
        start = body.find(marker)
        self.assertGreaterEqual(start, 0, "step 5.3 not found")
        step_5_3 = body[start:]
        self.assertIn("`resolve`", step_5_3)
        self.assertIn("--integration-tip <integration_tip>", step_5_3)

    def test_ac6_step_13_2_post_merge_re_resolve_passes_the_merged_head(self):
        body = self.section("13. ")
        forms = merge_pr_forms(body, "resolve")
        self.assertEqual(len(forms), 1, forms)
        self.assertTrue(has_option(forms[0], "--integration-tip", "<head_sha>"), forms[0])
        for option, value in (
            ("--repo", "<repo>"),
            ("--feature", "<feature>"),
            ("--base", "<base_branch>"),
        ):
            self.assertTrue(has_option(forms[0], option, value), forms[0])
        merge = line_index_of(body, "gh pr merge <pr_number>")
        resolve = line_index_of(body, forms[0])
        self.assertIsNotNone(merge)
        self.assertIsNotNone(resolve)
        self.assertLess(merge, resolve, "the re-resolve must come after gh pr merge")

    def test_ac6_step_13_2_no_longer_calls_the_re_resolve_the_same_as_step_5_2(self):
        body = self.section("13. ")
        self.assertNotIn("手順 5.2 と同じ呼び出し", body)

    def test_ac6_every_resolve_form_in_the_skill_passes_an_integration_tip(self):
        # Three forms since unattended-merge-medium-fixes task0001 AC-4: step
        # 5.2, the re-decision after the lock (step 6) and step 13.2. Since
        # merge-tip-binding task0002 AC-2 the step 6 form passes the tip read
        # after the lock (<locked_tip>), not the preflight tip.
        forms = merge_pr_forms(self.text, "resolve")
        self.assertEqual(len(forms), 3, forms)
        tips = []
        for form in forms:
            match = re.search(
                r"--integration-tip <(integration_tip|locked_tip|head_sha)>(\s|$)", form
            )
            self.assertIsNotNone(match, form)
            tips.append(match.group(1))
        self.assertEqual(tips, ["integration_tip", "locked_tip", "head_sha"], forms)

    def test_ac6_the_new_option_values_stay_literal_identifiers(self):
        for subcommand in ("resolve", "state"):
            for form in merge_pr_forms(self.text, subcommand):
                tail = form.split("merge-pr.py", 1)[1]
                self.assertFalse(re.search(r"[$`\\;&|(){}*?\[\]]", tail), form)

    def test_ac6_the_matchers_fire_on_forged_forms(self):
        good_state = (
            'python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-pr.py state --project-root "<project_root>" '
            "--repo <repo> --pr <pr_number> --head <head_sha> --base <base_branch>"
        )
        forged_state = good_state.replace(" --base <base_branch>", "")
        self.assertTrue(has_option(good_state, "--base", "<base_branch>"))
        self.assertFalse(has_option(forged_state, "--base", "<base_branch>"))
        wrong_value = good_state.replace("--base <base_branch>", "--base main")
        self.assertFalse(has_option(wrong_value, "--base", "<base_branch>"))
        text = "```bash\n%s\n```\n" % forged_state
        self.assertEqual(merge_pr_forms(text, "state"), [forged_state])
        self.assertEqual(merge_pr_forms(text, "resolve"), [])
        resolve_without_tip = (
            'python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-pr.py resolve --project-root "<project_root>" '
            "--repo <repo> --feature <feature> --base <base_branch>"
        )
        self.assertFalse(has_option(resolve_without_tip, "--integration-tip", "<integration_tip>"))


# ---------------------------------------------------------------------------
# task0001 (feature-docs/unattended-merge-medium-fixes): the local merge is
# bound to head_sha (FR1), the step-10 HEAD check runs in the worktree (FR2),
# the merged decision is repeated after the lock (FR3) and the host-qualified
# repository identifier reaches every later `--repo` (FR5)
# ---------------------------------------------------------------------------

MERGE_FORM = "git merge --no-ff --no-edit em-workflow/<feature>/integration"
TIP_REF = "refs/heads/em-workflow/<feature>/integration"
TIP_READ_RE = re.compile(r"^git rev-parse\b.*\s" + re.escape(TIP_REF) + r"$")
PARENTS_READ_RE = re.compile(r"^git log -n 1 --format=%P HEAD$")
STATUS_FORM = "git status --porcelain --untracked-files=no"
GH_PR_CREATE_FORM = (
    'gh pr create --head <create_head> --base <create_base> --title "<feature>" '
    '--body "Unattended merge of feature <feature>: '
    'em-workflow/<feature>/integration into <base_branch>."'
)
GH_PR_MERGE_FORM = "gh pr merge <pr_number> --merge --match-head-commit <head_sha>"
REPO_OPTION_RE = re.compile(r"(^|\s)--repo <repo>(\s|$)")


def shell_unsafe(line):
    """True when a command line carries a character that is not a plain
    literal for every common interactive shell: anything `not_literal` rejects
    plus the `^` and `~` revision suffixes, which some configurations glob."""
    return not_literal(line) or re.search(r"[\^~]", line) is not None


def block_lines(blocks, predicate):
    """Indices of the single-line blocks whose line satisfies `predicate`."""
    return [i for i, b in enumerate(blocks) if len(b.body) == 1 and predicate(b.body[0])]


def local_route_text(text):
    """Step 13.3 (the local route) up to the end of step 13. None when absent."""
    body = section(text, "13. ")
    if body is None:
        return None
    start = body.find("3. ローカルルート")
    return body[start:] if start >= 0 else None


def head_check_follows_worktree_cd(text):
    """True when, in step 10, the Bash block right before the
    `git status --porcelain` block is exactly the standalone worktree cd."""
    body = section(text, "10. ")
    if body is None:
        return False
    blocks = bash_blocks(body)
    found = block_lines(blocks, lambda line: line == STATUS_FORM)
    if len(found) != 1 or found[0] == 0:
        return False
    return blocks[found[0] - 1].body == ['cd "<worktree_path>"']


def redecision_text(text):
    """Item 4 of step 6 (the merged decision repeated after the lock): from its
    numbered line up to the paragraph that follows the list. None when absent."""
    body = section(text, "6. ")
    if body is None:
        return None
    lines = body.split("\n")
    start = next((i for i, line in enumerate(lines) if re.match(r"^4\. ", line)), None)
    if start is None:
        return None
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("ここから先")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def outcome_lines(text):
    """Map each backticked outcome that opens a bullet line to the whole line."""
    found = {}
    for line in text.split("\n"):
        match = re.match(r"^\s*-\s+`([a-z_]+)`", line)
        if match:
            found[match.group(1)] = line.strip()
    return found


def table_cells(text, code):
    """Cells of the result-value table row whose first cell is `code`."""
    body = section(text, "結果の値")
    if body is None:
        return None
    for line in body.split("\n"):
        if re.match(r"^\|\s*`%s`\s*\|" % re.escape(code), line):
            return [cell.strip() for cell in line.strip().strip("|").split("|")]
    return None


class TestLocalMergeBoundToHeadSha(SkillCase):
    """AC-1 and AC-2 of task0001 (FR1, TM-5, TS1)."""

    def local(self):
        local = local_route_text(self.text)
        self.assertIsNotNone(local, "step 13.3 not found")
        return local

    def test_ac1_integration_tip_is_read_after_the_main_tree_check_and_before_the_merge(self):
        local = self.local()
        blocks = bash_blocks(local)
        tip = block_lines(blocks, TIP_READ_RE.match)
        merge = block_lines(blocks, lambda line: line == MERGE_FORM)
        self.assertEqual(len(tip), 1, "no single read of %s" % TIP_REF)
        self.assertEqual(len(merge), 1)
        main_tree = line_index_of(local, "`main-tree`")
        self.assertIsNotNone(main_tree)
        self.assertLess(main_tree, blocks[tip[0]].open_index)
        self.assertLess(tip[0], merge[0])

    def test_ac1_a_tip_other_than_head_sha_ends_verification_failed_without_merging(self):
        local = self.local()
        blocks = bash_blocks(local)
        tip = block_lines(blocks, TIP_READ_RE.match)
        merge = block_lines(blocks, lambda line: line == MERGE_FORM)
        self.assertEqual(len(tip), 1)
        self.assertEqual(len(merge), 1)
        lines = local.split("\n")
        between = "\n".join(lines[blocks[tip[0]].open_index : blocks[merge[0]].open_index])
        for needle in ("`head_sha`", "`verification_failed`", "マージせず", "`git_failed`"):
            self.assertIn(needle, between)
        self.assertIn("integration branch moved after verification", between)

    def test_ac1_the_merge_runs_right_after_the_tip_read_with_the_project_root_cd_before_both(self):
        blocks = bash_blocks(self.local())
        merge = block_lines(blocks, lambda line: line == MERGE_FORM)
        self.assertEqual(len(merge), 1)
        cd = nearest_previous_cd(blocks, merge[0])
        self.assertIsNotNone(cd)
        self.assertEqual(cd.body, ['cd "<project_root>"'])
        between = [b.body for b in blocks[blocks.index(cd) + 1 : merge[0]]]
        self.assertEqual(len(between), 1, between)
        self.assertRegex(between[0][0], TIP_READ_RE)

    def test_ac1_the_tip_read_is_a_shell_safe_read_only_form(self):
        blocks = bash_blocks(self.local())
        tip = block_lines(blocks, TIP_READ_RE.match)
        self.assertEqual(len(tip), 1)
        line = blocks[tip[0]].body[0]
        self.assertTrue(line.startswith("git rev-parse "), line)
        self.assertFalse(shell_unsafe(line), line)

    def test_ac1_a_failing_merge_still_aborts_before_merge_failed(self):
        local = self.local()
        blocks = bash_blocks(local)
        merge = block_lines(blocks, lambda line: line == MERGE_FORM)
        abort = block_lines(blocks, lambda line: line == "git merge --abort")
        self.assertEqual(len(merge), 1)
        self.assertEqual(len(abort), 1)
        self.assertLess(merge[0], abort[0])
        before_abort = "\n".join(
            local.split("\n")[blocks[merge[0]].open_index : blocks[abort[0]].open_index]
        )
        self.assertIn("`merge_failed`", before_abort)

    def test_ac2_the_second_parent_is_read_after_the_merge_success_branch(self):
        blocks = bash_blocks(self.local())
        merge = block_lines(blocks, lambda line: line == MERGE_FORM)
        abort = block_lines(blocks, lambda line: line == "git merge --abort")
        head = block_lines(blocks, lambda line: line == "git rev-parse HEAD")
        parents = block_lines(blocks, PARENTS_READ_RE.match)
        for found in (merge, abort, head, parents):
            self.assertEqual(len(found), 1, found)
        self.assertTrue(merge[0] < abort[0] < head[0] < parents[0], (merge, abort, head, parents))
        line = blocks[parents[0]].body[0]
        self.assertFalse(shell_unsafe(line), line)

    def test_ac2_a_mismatch_or_an_unreadable_parent_keeps_merged_with_a_one_line_detail(self):
        local = self.local()
        blocks = bash_blocks(local)
        parents = block_lines(blocks, PARENTS_READ_RE.match)
        self.assertEqual(len(parents), 1)
        after = "\n".join(local.split("\n")[blocks[parents[0]].open_index :])
        for needle in (
            "第 2 親",
            "`merged` のまま",
            "`head_sha`",
            "1 行",
            "固定文",
            "40 桁の小文字 16 進",
            "second parent could not be read",
            "differs from verified head_sha",
        ):
            self.assertIn(needle, after)
        for forbidden in ("`verification_failed`", "`merge_failed`"):
            self.assertNotIn(forbidden, after)

    def test_ac2_cleanup_runs_after_the_second_parent_check_as_for_any_merged_result(self):
        local = self.local()
        blocks = bash_blocks(local)
        parents = block_lines(blocks, PARENTS_READ_RE.match)
        self.assertEqual(len(parents), 1)
        after = "\n".join(local.split("\n")[blocks[parents[0]].open_index :])
        self.assertIn("手順 14", after)
        self.assertIn("手順 15", after)

    def test_ac2_the_detail_fixed_text_rule_names_this_case_as_its_only_exception(self):
        body = self.section("結果の値")
        rule = [line for line in body.split("\n") if line.startswith("`detail` の固定文")]
        self.assertEqual(len(rule), 1)
        self.assertRegex(rule[0], r"例外は.*手順 13\.3.*第 2 親")

    def test_ac2_the_verification_failed_row_lists_step_13_and_the_moved_branch_detail(self):
        cells = table_cells(self.text, "verification_failed")
        self.assertIsNotNone(cells, "no verification_failed row")
        steps = {step.strip() for step in cells[2].split(",")}
        self.assertEqual(steps, {"10", "13"})
        self.assertIn("integration branch moved after verification", cells[3])

    def test_ac1_the_shell_safe_matcher_fires_on_forged_forms(self):
        for forged in (
            "git rev-parse --verify HEAD^2",
            "git rev-parse --verify HEAD~1",
            "git rev-parse --verify HEAD^{commit}",
            "git rev-parse --verify $(echo HEAD)",
            "git log -n 1 --format=%P HEAD; git merge x",
        ):
            self.assertTrue(shell_unsafe(forged), forged)
        for good in (
            "git rev-parse --verify refs/heads/em-workflow/<feature>/integration",
            "git log -n 1 --format=%P HEAD",
            "git rev-parse HEAD",
        ):
            self.assertFalse(shell_unsafe(good), good)

    def test_ac1_no_command_form_in_the_skill_carries_a_revision_suffix(self):
        for form in command_forms(self.text):
            self.assertIsNone(re.search(r"[\^~]", form), form)

    def test_ac1_the_ordering_matchers_fire_on_forged_text(self):
        forged = (
            "### 13. マージ\n\n"
            "3. ローカルルート。\n\n"
            "   ```bash\n   cd \"<project_root>\"\n   ```\n\n"
            "   ```bash\n   %s\n   ```\n" % MERGE_FORM
        )
        blocks = bash_blocks(local_route_text(forged))
        self.assertEqual(block_lines(blocks, TIP_READ_RE.match), [])
        self.assertEqual(len(block_lines(blocks, lambda line: line == MERGE_FORM)), 1)
        self.assertIsNone(TIP_READ_RE.match("git rev-parse --verify HEAD"))
        self.assertIsNone(PARENTS_READ_RE.match("git log -n 1 --format=%P HEAD^"))


class TestStep10HeadCheckRunsInTheWorktree(SkillCase):
    """AC-3 of task0001 (FR2, TS2)."""

    def test_ac3_the_block_right_before_git_status_is_a_standalone_worktree_cd(self):
        self.assertTrue(head_check_follows_worktree_cd(self.text))

    def test_ac3_the_head_check_pair_follows_that_cd_after_the_command_block(self):
        blocks = bash_blocks(self.section("10. "))
        status = block_lines(blocks, lambda line: line == STATUS_FORM)
        command = block_lines(blocks, lambda line: line == "<command>")
        self.assertEqual(len(status), 1)
        self.assertEqual(len(command), 1)
        self.assertLess(command[0], status[0] - 1)
        self.assertEqual(blocks[status[0] + 1].body, ["git rev-parse HEAD"])

    def test_ac3_the_first_worktree_cd_is_still_followed_by_the_command(self):
        blocks = bash_blocks(self.section("10. "))
        cds = [i for i, b in enumerate(blocks) if b.body == ['cd "<worktree_path>"']]
        self.assertEqual(len(cds), 2, "one cd for the commands, one for the HEAD check")
        self.assertEqual(blocks[cds[0] + 1].body, ["<command>"])

    def test_ac3_the_check_also_runs_when_commands_is_empty(self):
        body = self.section("10. ")
        lines = [line for line in body.split("\n") if "`commands` が空" in line]
        self.assertTrue(lines, "no statement about an empty commands list")
        joined = "\n".join(lines)
        self.assertIn("実行しない", joined)
        self.assertRegex(joined, r"`commands` が空でも必ず行う")
        self.assertNotIn("何も実行しない", body)

    def test_ac3_the_matcher_fires_on_a_forged_step_without_the_cd(self):
        forged = (
            "### 10. 検証コマンド\n\n"
            "```bash\ncd \"<worktree_path>\"\n```\n\n"
            "```bash\n<command>\n```\n\n"
            "```bash\n%s\n```\n\n"
            "```bash\ngit rev-parse HEAD\n```\n" % STATUS_FORM
        )
        self.assertFalse(head_check_follows_worktree_cd(forged))
        fixed = forged.replace(
            "```bash\n%s\n```" % STATUS_FORM,
            "```bash\ncd \"<worktree_path>\"\n```\n\n```bash\n%s\n```" % STATUS_FORM,
        )
        self.assertTrue(head_check_follows_worktree_cd(fixed))


class TestPostLockMergedRedecision(SkillCase):
    """AC-4 and AC-5 of task0001 (FR3, TM-6, TS3)."""

    def step6_forms(self):
        """Bash blocks of step 6 in document order, with whole-document indices."""
        start = heading_line_index(self.text, "6. ")
        end = heading_line_index(self.text, "7. ")
        self.assertTrue(start is not None and end is not None and start < end)
        return [b for b in bash_blocks(self.text) if start < b.open_index < end]

    def test_ac4_held_leads_to_the_redecision_not_straight_to_step_7(self):
        body = self.section("6. ")
        held = [line for line in body.split("\n") if line.strip().startswith("- `held`")]
        self.assertEqual(len(held), 1)
        self.assertNotIn("手順 7", held[0])
        self.assertIsNotNone(redecision_text(self.text), "no re-decision item in step 6")

    def test_ac4_the_redecision_forms_follow_the_wait_and_precede_step_7(self):
        blocks = self.step6_forms()
        wait = [
            i
            for i, b in enumerate(blocks)
            if b.body and "merge-lock.py verify " in b.body[0] and "--wait" in b.body[0]
        ]
        merged = [i for i, b in enumerate(blocks) if b.body and "merge-git.py merged " in b.body[0]]
        resolve = [i for i, b in enumerate(blocks) if b.body and "merge-pr.py resolve " in b.body[0]]
        self.assertEqual((len(wait), len(merged), len(resolve)), (1, 1, 1))
        self.assertTrue(wait[0] < merged[0] < resolve[0], (wait, merged, resolve))
        step7 = heading_line_index(self.text, "7. ")
        for index in (merged[0], resolve[0]):
            self.assertLess(blocks[index].open_index, step7)

    def redecision_forms(self):
        """(merged block, resolve block) of step 6; fails when either is absent."""
        blocks = self.step6_forms()
        merged = [b for b in blocks if b.body and "merge-git.py merged " in b.body[0]]
        resolve = [b for b in blocks if b.body and "merge-pr.py resolve " in b.body[0]]
        self.assertEqual(len(merged), 1, "no merge-git.py merged form in step 6")
        self.assertEqual(len(resolve), 1, "no merge-pr.py resolve form in step 6")
        return merged[0], resolve[0]

    def test_ac4_each_redecision_form_has_its_own_timeout_line(self):
        merged, resolve = self.redecision_forms()
        for block in (merged, resolve):
            match = TIMEOUT_RE.search(block.prev)
            self.assertIsNotNone(match, block.body)
            self.assertTrue(0 < int(match.group(1)) <= 600000, block.body)
        lines = self.text.split("\n")
        between = "\n".join(lines[merged.open_index + 3 : resolve.open_index])
        self.assertIn("timeout:", between, "the two forms share one timeout line")

    def test_ac4_the_redecision_forms_pass_the_options_of_steps_4_and_5_2(self):
        merged, resolve = self.redecision_forms()
        step4 = [f for f in command_forms(self.section("4. ")) if "merge-git.py merged " in f]
        self.assertEqual(len(step4), 1)
        self.assertEqual(merged.body[0], step4[0])
        # merge-tip-binding task0002 AC-2: the PR-route form is the step 5.2
        # form token for token, except that the tip value is <locked_tip>.
        step5 = merge_pr_forms(self.section("5. "), "resolve")
        self.assertEqual(len(step5), 1)
        expected = ["<locked_tip>" if t == "<integration_tip>" else t for t in step5[0].split()]
        self.assertNotEqual(expected, step5[0].split(), "the step 5.2 form carries no <integration_tip>")
        self.assertEqual(resolve.body[0].split(), expected)
        for option, value in (
            ("--repo", "<repo>"),
            ("--feature", "<feature>"),
            ("--base", "<base_branch>"),
            ("--integration-tip", "<locked_tip>"),
        ):
            self.assertTrue(has_option(resolve.body[0], option, value), resolve.body[0])
        self.assertNotIn("<integration_tip>", resolve.body[0])

    def test_ac4_each_outcome_is_handled_as_the_decision_table_says(self):
        text = redecision_text(self.text)
        self.assertIsNotNone(text, "no re-decision item in step 6")
        outcomes = outcome_lines(text)
        self.assertEqual(
            set(outcomes), {"merged", "not_merged", "open", "stop", "none"}, sorted(outcomes)
        )
        for needle in ("マージ済みの経路", "`already_merged`", "`pr_url`", "`merge_commit`"):
            self.assertIn(needle, outcomes["merged"])
        self.assertIn("手順 7", outcomes["not_merged"])
        for needle in ("`pr_number`", "`pr_url`", "手順 7"):
            self.assertIn(needle, outcomes["open"])
        for needle in ("`reason`", "`detail`"):
            self.assertIn(needle, outcomes["stop"])
        self.assertIn("`internal_error`", outcomes["none"])

    def test_ac4_the_hold_task_is_stopped_before_every_terminal_the_redecision_reaches(self):
        text = redecision_text(self.text)
        self.assertIsNotNone(text, "no re-decision item in step 6")
        outcomes = outcome_lines(text)
        for outcome in ("merged", "stop", "none"):
            self.assertIn("手順 14", outcomes.get(outcome, ""), outcome)
        failure = [line for line in text.split("\n") if "スクリプトの失敗" in line]
        self.assertEqual(len(failure), 1, failure)
        self.assertIn("手順 14", failure[0])
        self.assertIn("`internal_error`", failure[0])

    def test_ac5_the_already_merged_entry_list_names_the_step_6_redecision(self):
        body = self.section("マージ済みの経路")
        entry = body.split("\n\n", 2)[1].split("。")[0]
        for needle in ("手順 4", "手順 5.2", "手順 13.2", "手順 6", "再判定"):
            self.assertIn(needle, entry)

    def test_ac5_item_1_stops_the_hold_task_first_for_the_step_6_entry(self):
        body = self.section("マージ済みの経路")
        item = [line for line in body.split("\n") if re.match(r"^1\. ", line)]
        self.assertEqual(len(item), 1)
        for needle in ("手順 6", "手順 13.2", "手順 14"):
            self.assertIn(needle, item[0])

    def test_ac5_the_skipped_steps_and_the_cleanup_are_still_named(self):
        body = self.section("マージ済みの経路")
        for needle in ("`already_merged`", "手順 6〜13", "手順 7〜13", "手順 15"):
            self.assertIn(needle, body)

    def test_ac4_the_outcome_matcher_fires_on_forged_text(self):
        forged = (
            "4. 判定し直す。\n\n"
            "   - `merged`（ローカル / PR）: 「マージ済みの経路」へ進む。\n"
            "   - `stop`（ローカル / PR）: その `reason` で終端する。\n"
            "ここから先は続く。\n"
        )
        forged_section = "### 6. ロック\n\n" + forged
        text = redecision_text(forged_section)
        self.assertIsNotNone(text)
        outcomes = outcome_lines(text)
        self.assertEqual(set(outcomes), {"merged", "stop"})
        self.assertNotIn("手順 14", outcomes["merged"])
        self.assertNotIn("手順 14", outcomes["stop"])
        self.assertIsNone(redecision_text("### 6. ロック\n\n3. 確かめる。\n"))


# ---------------------------------------------------------------------------
# merge-tip-binding task0002 (feature-docs/merge-tip-binding): the PR route
# re-decides after the lock at the integration tip read after the lock
# ---------------------------------------------------------------------------

PROJECT_ROOT_CD = 'cd "<project_root>"'
TIP_READ_FORM = "git rev-parse --verify " + TIP_REF
LOCKED_TIP = "<locked_tip>"
HEX40_PHRASE = "40 桁の小文字 16 進"
OLD_TIP_PHRASES = (
    "手順 4 / 5.2 と同じ `integration_tip`",
    "`--integration-tip` には `integration_tip` を渡す",
)
ROUTE_TIP_STATEMENTS = (
    r"`merge-git\.py merged` は、呼んだ時点の integration ブランチの先端で判定する",
    r"PR ルートは.*`locked_tip` で判定する",
)
RULE_NEEDLES = ("末尾の改行", "`locked_tip`", "git が失敗", "手順 14", "`internal_error`")


def step6_blocks(text):
    """Bash blocks of step 6 in document order, with whole-document indices.
    Empty when the step 6 or step 7 heading is absent."""
    start = heading_line_index(text, "6. ")
    end = heading_line_index(text, "7. ")
    if start is None or end is None or start >= end:
        return []
    return [b for b in bash_blocks(text) if start < b.open_index < end]


def first_block(blocks, predicate, after):
    """Index of the first block after position `after` that satisfies
    `predicate`, or None."""
    for i in range(after + 1, len(blocks)):
        if blocks[i].body and predicate(blocks[i]):
            return i
    return None


def is_wait_verify(block):
    return "merge-lock.py verify " in block.body[0] and "--wait" in block.body[0]


def is_merged_form(block):
    return "merge-git.py merged " in block.body[0]


def is_project_root_cd(block):
    return block.body == [PROJECT_ROOT_CD]


def is_tip_read(block):
    return len(block.body) == 1 and TIP_READ_RE.match(block.body[0]) is not None


def is_pr_resolve(block):
    return "merge-pr.py resolve " in block.body[0]


POST_LOCK_CHAIN = (
    ("wait", is_wait_verify),
    ("merged", is_merged_form),
    ("cd", is_project_root_cd),
    ("read", is_tip_read),
    ("resolve", is_pr_resolve),
)


def post_lock_chain(text):
    """(blocks, positions): the Bash blocks of step 6 and, per name of
    POST_LOCK_CHAIN, the index of the first block after the previous name's
    block; None where the chain breaks, and for every later name."""
    blocks = step6_blocks(text)
    positions = {}
    at = -1
    for name, predicate in POST_LOCK_CHAIN:
        found = first_block(blocks, predicate, at) if at is not None else None
        positions[name] = found
        at = found
    return blocks, positions


def directly_preceding_line(lines, block):
    """Index of the last non-blank line right before the block's opening fence."""
    i = block.open_index - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    return i if i >= 0 else None


def chain_problems(text):
    """AC-1: order, own timeout lines and shell safety of the PR route's
    post-lock blocks. An empty list means none."""
    blocks, at = post_lock_chain(text)
    missing = [name for name, index in at.items() if index is None]
    if missing:
        return [
            "step 6 has no %s block in the order wait, merged, cd, read, resolve" % name
            for name in missing
        ]
    problems = []
    lines = text.split("\n")
    for name in ("cd", "read", "resolve"):
        line_index = directly_preceding_line(lines, blocks[at[name]])
        match = TIMEOUT_RE.search(lines[line_index]) if line_index is not None else None
        if match is None or not 0 < int(match.group(1)) <= 600000:
            problems.append("the %s block has no own timeout line of at most 600000" % name)
    read_line = blocks[at["read"]].body[0]
    if read_line != TIP_READ_FORM:
        problems.append("the read line is not exactly %s" % TIP_READ_FORM)
    if shell_unsafe(read_line):
        problems.append("the read line is not shell-safe")
    return problems


def resolve_problems(text):
    """AC-2: the step 6 resolve form is the step 5.2 form with only the tip
    value replaced by <locked_tip>, and no other command form carries it."""
    forms = [b.body[0] for b in step6_blocks(text) if b.body and is_pr_resolve(b)]
    if len(forms) != 1:
        return ["step 6 does not hold exactly one merge-pr.py resolve form"]
    form = forms[0]
    problems = []
    if not has_option(form, "--integration-tip", LOCKED_TIP):
        problems.append("the step 6 resolve form does not pass --integration-tip %s" % LOCKED_TIP)
    if "<integration_tip>" in form:
        problems.append("the step 6 resolve form still carries <integration_tip>")
    step5 = merge_pr_forms(section(text, "5. ") or "", "resolve")
    if len(step5) != 1:
        problems.append("step 5 does not hold exactly one resolve form")
    else:
        expected = [LOCKED_TIP if t == "<integration_tip>" else t for t in step5[0].split()]
        if form.split() != expected:
            problems.append("the step 6 resolve form is not the step 5.2 form with only the tip replaced")
    users = [f for f in command_forms(text) if LOCKED_TIP in f]
    if users != [form]:
        problems.append("%s is used in a command form other than the step 6 resolve form" % LOCKED_TIP)
    return problems


def step6_line_index(text, line):
    """Index of the first line equal to `line` inside the step 6 range."""
    lines = text.split("\n")
    start = heading_line_index(text, "6. ")
    end = heading_line_index(text, "7. ")
    if start is None or end is None:
        return None
    for i in range(start, end):
        if lines[i] == line:
            return i
    return None


def read_rule_problems(text):
    """AC-3: item 4 states, as prose between the read and the resolve, that the
    output becomes `locked_tip` only when it is exactly 40 lowercase hex
    characters, that anything else ends in 手順 14 and `internal_error`, and
    that `integration_tip` is not overwritten."""
    item = redecision_text(text)
    if item is None:
        return ["no item 4 in step 6"]
    prose = without_fences(item)
    problems = []
    if "`integration_tip` は上書きしない" not in prose:
        problems.append("item 4 does not say that `integration_tip` is not overwritten")
    rules = [line for line in prose.split("\n") if HEX40_PHRASE in line]
    if len(rules) != 1:
        return problems + ["item 4 does not hold exactly one line stating the 40-digit rule"]
    rule = rules[0]
    for needle in RULE_NEEDLES:
        if needle not in rule:
            problems.append("the read-value rule does not contain %s" % needle)
    if "スクリプトの失敗" in rule:
        problems.append("the read-value rule reuses the phrase スクリプトの失敗")
    if re.match(r"^\s*-\s", rule):
        problems.append("the read-value rule is written as a bullet")
    blocks, at = post_lock_chain(text)
    rule_index = step6_line_index(text, rule)
    if at["read"] is not None and at["resolve"] is not None and rule_index is not None:
        if not blocks[at["read"]].open_index < rule_index < blocks[at["resolve"]].open_index:
            problems.append("the read-value rule is not between the read and the resolve")
    return problems


def route_tip_problems(text):
    """AC-4: item 4 no longer reuses the preflight tip as the tip of both
    routes; it says what each route judges."""
    item = redecision_text(text)
    if item is None:
        return ["no item 4 in step 6"]
    prose = without_fences(item)
    problems = []
    for phrase in OLD_TIP_PHRASES:
        if phrase in item:
            problems.append("item 4 still contains %s" % phrase)
    for pattern in ROUTE_TIP_STATEMENTS:
        if not re.search(pattern, prose):
            problems.append("item 4 does not state %s" % pattern)
    return problems


def held_value_description(text, name):
    """The full-width-parenthesised description after `name` in 「保持する値」."""
    body = section(text, "保持する値")
    if body is None:
        return None
    match = re.search(r"`%s`（([^）]*)）" % re.escape(name), body)
    return match.group(1) if match else None


def held_values_problems(text):
    """AC-5: `integration_tip` is also step 8's value and never overwritten;
    `locked_tip` is the tip read after the lock, passed only to step 6.4."""
    problems = []
    tip = held_value_description(text, "integration_tip")
    if tip is None:
        problems.append("the held values have no `integration_tip` description")
    else:
        for needle in ("手順 5", "手順 8", "上書きしない"):
            if needle not in tip:
                problems.append("the `integration_tip` description does not contain %s" % needle)
    locked = held_value_description(text, "locked_tip")
    if locked is None:
        problems.append("the held values have no `locked_tip` description")
    else:
        for needle in ("手順 6.4", "ロックを取った後", "integration ブランチの先端", "`resolve` にだけ渡す"):
            if needle not in locked:
                problems.append("the `locked_tip` description does not contain %s" % needle)
    return problems


# A document in the shape the matchers read, for the forged-text cases. The
# default arguments make the control document that every matcher accepts; each
# forged case changes one thing.
FORGED_MERGED = (
    "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-git.py merged "
    '--project-root "<project_root>" --feature <feature> --base <base_branch>'
)
FORGED_WAIT = (
    "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-lock.py verify "
    '--project-root "<project_root>" --token <lock_token> --wait 30'
)
FORGED_RESOLVE = (
    "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-pr.py resolve "
    '--project-root "<project_root>" --repo <repo> --feature <feature> '
    "--base <base_branch> --integration-tip %s"
)
FORGED_BLOCKS = {
    "wait": (120000, FORGED_WAIT),
    "merged": (120000, FORGED_MERGED),
    "cd": (60000, PROJECT_ROOT_CD),
    "read": (60000, TIP_READ_FORM),
    "resolve": (600000, FORGED_RESOLVE % LOCKED_TIP),
}
GOOD_OPENING = (
    "`held` を得たら、手順 7 の前に、マージ済みかを判定し直す。"
    "ローカルルートの `merge-git.py merged` は、呼んだ時点の integration ブランチの先端で判定する。"
    "PR ルートは、ロックを取った後に読み直した `locked_tip` で判定する。"
)
GOOD_RULE = (
    "読んだ出力の末尾の改行を除いた値が、40 桁の小文字 16 進のちょうどであるときだけ "
    "`locked_tip` として保持する。git が失敗したとき、またはそれ以外の値のときは、"
    "手順 14 で保持タスクを止めてから、`internal_error` で終端へ進む。"
    "`integration_tip` は上書きしない。"
)
GOOD_HELD = (
    "`integration_tip`（事前判定が読んだ先端。手順 5 の `resolve` に渡す。"
    "手順 8 の取り込みで期待する HEAD としても使う。上書きしない）、"
    "`locked_tip`（手順 6.4 の PR ルートが、ロックを取った後に読んだ integration ブランチの先端。"
    "手順 6.4 の `resolve` にだけ渡す）。"
)


def forged_skill(
    pre=("wait",),
    post=("merged", "cd", "read", "resolve"),
    opening=GOOD_OPENING,
    rule=GOOD_RULE,
    rule_after="read",
    held=GOOD_HELD,
    **overrides
):
    """`pre` are the step 6 blocks before item 4, `post` the blocks inside it;
    `overrides` replace a block's (timeout, command) pair, a timeout of None
    omits its timeout line."""
    specs = dict(FORGED_BLOCKS)
    specs.update(overrides)

    def emit(names):
        parts = []
        for name in names:
            timeout, command = specs[name]
            if timeout is not None:
                parts.append("   Bash 呼び出し（timeout: %d）:\n" % timeout)
            parts.append("   ```bash\n   %s\n   ```\n" % command)
            if rule and name == rule_after:
                parts.append("   %s\n" % rule)
        return "\n".join(parts)

    return (
        "## 保持する値\n\n%s\n\n"
        "## 手順\n\n"
        "### 4. ローカルルートの確認\n\n"
        "```bash\n%s\n```\n\n"
        "### 5. PR ルートの確認と PR の確保\n\n"
        "2. PR の解決。\n\n"
        "   ```bash\n   %s\n   ```\n\n"
        "### 6. ロック\n\n"
        "3. 取得できたことを確かめる。\n\n%s\n"
        "4. %s\n\n%s\n"
        "   - `merged`（ローカル / PR）: 「マージ済みの経路」へ進む。\n"
        "ここから先のどの終端でも、描画の前に手順 14 の停止を行う。\n\n"
        "### 7. integration worktree\n"
    ) % (
        held,
        FORGED_MERGED,
        FORGED_RESOLVE % "<integration_tip>",
        emit(pre),
        opening,
        emit(post),
    )


ALL_TIP_CHECKS = (
    chain_problems,
    resolve_problems,
    read_rule_problems,
    route_tip_problems,
    held_values_problems,
)


class TestPostLockTipBinding(SkillCase):
    """AC-1 to AC-6 of merge-tip-binding task0002 (FR1, FR5, FR6).

    Coverage: AC-1 the order, timeout lines and shell safety of the PR route's
    cd / read / resolve blocks in step 6; AC-2 the step 6 resolve form carries
    `<locked_tip>` and is otherwise the step 5.2 form; AC-3 the read-value
    rule of item 4 (40 lowercase hex, fail-closed to 手順 14 and
    `internal_error`, `integration_tip` not overwritten); AC-4 item 4 says
    what each route judges; AC-5 the held values describe `integration_tip`
    and `locked_tip`; AC-6 every matcher fires on a forged document. AC-7
    (`merge-pr.py` unchanged) is covered by the existing task0010 AC-4 tests
    of tests/test_merge_pr.py and the full suite.
    """

    def test_ac1_the_pr_route_reads_the_tip_between_the_wait_verify_and_the_resolve(self):
        self.assertEqual(chain_problems(self.text), [])

    def test_ac1_the_local_route_block_is_unchanged_and_precedes_the_pr_route_blocks(self):
        blocks, at = post_lock_chain(self.text)
        self.assertIsNotNone(at["merged"], "no merged block after the wait verify")
        self.assertIsNotNone(at["cd"], "no cd block after the merged block")
        self.assertLess(at["merged"], at["cd"])
        step4 = [f for f in command_forms(self.section("4. ")) if "merge-git.py merged " in f]
        self.assertEqual(len(step4), 1)
        self.assertEqual(blocks[at["merged"]].body, step4)

    def test_ac2_the_step_6_resolve_form_passes_the_locked_tip_and_is_otherwise_the_step_5_2_form(self):
        self.assertEqual(resolve_problems(self.text), [])

    def test_ac3_item_4_states_the_read_value_rule_between_the_read_and_the_resolve(self):
        self.assertEqual(read_rule_problems(self.text), [])

    def test_ac3_the_rule_adds_no_outcome_bullet_and_no_second_script_failure_line(self):
        item = redecision_text(self.text)
        self.assertIsNotNone(item, "no item 4 in step 6")
        self.assertEqual(
            set(outcome_lines(item)), {"merged", "not_merged", "open", "stop", "none"}
        )
        failure = [line for line in item.split("\n") if "スクリプトの失敗" in line]
        self.assertEqual(len(failure), 1, failure)

    def test_ac4_item_4_says_what_each_route_judges_and_drops_the_shared_tip_phrase(self):
        self.assertEqual(route_tip_problems(self.text), [])

    def test_ac5_the_held_values_describe_integration_tip_and_locked_tip(self):
        self.assertEqual(held_values_problems(self.text), [])

    def test_ac5_the_held_values_list_names_each_tip_once(self):
        body = self.section("保持する値")
        self.assertEqual(body.count("`integration_tip`（"), 1)
        self.assertEqual(body.count("`locked_tip`（"), 1)

    def test_ac6_the_control_document_passes_every_matcher(self):
        text = forged_skill()
        for check in ALL_TIP_CHECKS:
            self.assertEqual(check(text), [], check.__name__)

    def test_ac6_the_order_matcher_fires_when_the_read_block_is_missing(self):
        problems = chain_problems(forged_skill(post=("merged", "cd", "resolve")))
        self.assertTrue(any("no read block" in p for p in problems), problems)

    def test_ac6_the_order_matcher_fires_when_the_cd_block_is_missing(self):
        problems = chain_problems(forged_skill(post=("merged", "read", "resolve")))
        self.assertTrue(any("no cd block" in p for p in problems), problems)

    def test_ac6_the_order_matcher_fires_when_the_read_comes_before_the_wait_verify(self):
        text = forged_skill(pre=("read", "wait"), post=("merged", "cd", "resolve"))
        problems = chain_problems(text)
        self.assertTrue(any("no read block" in p for p in problems), problems)

    def test_ac6_the_order_matcher_fires_when_the_read_comes_before_the_cd(self):
        problems = chain_problems(forged_skill(post=("merged", "read", "cd", "resolve")))
        self.assertTrue(any("no read block" in p for p in problems), problems)

    def test_ac6_the_order_matcher_fires_when_the_read_comes_after_the_resolve(self):
        problems = chain_problems(forged_skill(post=("merged", "cd", "resolve", "read")))
        self.assertTrue(any("no resolve block" in p for p in problems), problems)

    def test_ac6_the_order_matcher_fires_when_the_merged_block_follows_the_pr_route_blocks(self):
        problems = chain_problems(forged_skill(post=("cd", "read", "resolve", "merged")))
        self.assertTrue(any("no cd block" in p for p in problems), problems)

    def test_ac6_the_timeout_matcher_fires_when_a_block_shares_the_previous_timeout_line(self):
        problems = chain_problems(forged_skill(read=(None, TIP_READ_FORM)))
        self.assertEqual(problems, ["the read block has no own timeout line of at most 600000"])

    def test_ac6_the_timeout_matcher_fires_on_a_timeout_above_600000(self):
        problems = chain_problems(forged_skill(resolve=(600001, FORGED_RESOLVE % LOCKED_TIP)))
        self.assertIn("the resolve block has no own timeout line of at most 600000", problems)

    def test_ac6_the_read_form_matcher_fires_on_an_expansion_in_the_read_line(self):
        unsafe = "git rev-parse --verify $(echo x) " + TIP_REF
        problems = chain_problems(forged_skill(read=(60000, unsafe)))
        self.assertIn("the read line is not shell-safe", problems)
        self.assertIn("the read line is not exactly %s" % TIP_READ_FORM, problems)

    def test_ac6_the_resolve_matcher_fires_when_the_form_still_carries_the_preflight_tip(self):
        text = forged_skill(resolve=(600000, FORGED_RESOLVE % "<integration_tip>"))
        problems = resolve_problems(text)
        self.assertIn("the step 6 resolve form still carries <integration_tip>", problems)
        self.assertTrue(any("does not pass --integration-tip" in p for p in problems), problems)

    def test_ac6_the_resolve_matcher_fires_when_another_option_differs_from_step_5_2(self):
        other = (FORGED_RESOLVE % LOCKED_TIP).replace("--base <base_branch>", "--base main")
        problems = resolve_problems(forged_skill(resolve=(600000, other)))
        self.assertTrue(any("only the tip replaced" in p for p in problems), problems)

    def test_ac6_the_resolve_matcher_fires_when_locked_tip_reaches_another_command_form(self):
        text = forged_skill() + "\n```bash\ngit log -n 1 <locked_tip>\n```\n"
        problems = resolve_problems(text)
        self.assertTrue(any("other than the step 6 resolve form" in p for p in problems), problems)

    def test_ac6_the_rule_matcher_fires_when_the_rule_is_missing(self):
        problems = read_rule_problems(forged_skill(rule=""))
        self.assertTrue(any("exactly one line stating the 40-digit rule" in p for p in problems), problems)

    def test_ac6_the_rule_matcher_fires_when_the_failure_path_is_not_stated(self):
        rule = GOOD_RULE.replace("手順 14 で保持タスクを止めてから、`internal_error` で終端へ進む。", "")
        problems = read_rule_problems(forged_skill(rule=rule))
        self.assertIn("the read-value rule does not contain 手順 14", problems)
        self.assertIn("the read-value rule does not contain `internal_error`", problems)

    def test_ac6_the_rule_matcher_fires_when_integration_tip_is_not_said_to_stay(self):
        problems = read_rule_problems(forged_skill(rule=GOOD_RULE.replace("`integration_tip` は上書きしない。", "")))
        self.assertIn("item 4 does not say that `integration_tip` is not overwritten", problems)

    def test_ac6_the_rule_matcher_fires_when_the_rule_reuses_the_script_failure_phrase(self):
        problems = read_rule_problems(forged_skill(rule=GOOD_RULE + "スクリプトの失敗と同じ。"))
        self.assertIn("the read-value rule reuses the phrase スクリプトの失敗", problems)

    def test_ac6_the_rule_matcher_fires_when_the_rule_is_an_outcome_bullet(self):
        problems = read_rule_problems(forged_skill(rule="- " + GOOD_RULE))
        self.assertIn("the read-value rule is written as a bullet", problems)

    def test_ac6_the_rule_matcher_fires_when_the_rule_follows_the_resolve(self):
        problems = read_rule_problems(forged_skill(rule_after="resolve"))
        self.assertIn("the read-value rule is not between the read and the resolve", problems)

    def test_ac6_the_route_matcher_fires_when_item_4_keeps_the_old_phrase(self):
        opening = "`held` を得たら、手順 7 の前に、マージ済みかを判定し直す。先端は手順 4 / 5.2 と同じ `integration_tip`。"
        problems = route_tip_problems(forged_skill(opening=opening))
        self.assertIn("item 4 still contains 手順 4 / 5.2 と同じ `integration_tip`", problems)
        self.assertEqual(len(problems), 3, problems)

    def test_ac6_the_route_matcher_fires_when_only_one_route_is_described(self):
        opening = GOOD_OPENING.replace("PR ルートは、ロックを取った後に読み直した `locked_tip` で判定する。", "")
        problems = route_tip_problems(forged_skill(opening=opening))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("locked_tip", problems[0])

    def test_ac6_the_held_values_matcher_fires_without_locked_tip(self):
        held = GOOD_HELD.split("、`locked_tip`")[0] + "。"
        problems = held_values_problems(forged_skill(held=held))
        self.assertEqual(problems, ["the held values have no `locked_tip` description"])

    def test_ac6_the_held_values_matcher_fires_when_integration_tip_is_not_tied_to_step_8(self):
        held = GOOD_HELD.replace("手順 8 の取り込みで期待する HEAD としても使う。", "").replace("上書きしない", "")
        problems = held_values_problems(forged_skill(held=held))
        self.assertIn("the `integration_tip` description does not contain 手順 8", problems)
        self.assertIn("the `integration_tip` description does not contain 上書きしない", problems)

    def test_ac6_the_held_values_matcher_fires_when_locked_tip_may_reach_another_step(self):
        held = GOOD_HELD.replace("`resolve` にだけ渡す", "`resolve` に渡す")
        problems = held_values_problems(forged_skill(held=held))
        self.assertIn("the `locked_tip` description does not contain `resolve` にだけ渡す", problems)


class TestHostQualifiedRepository(SkillCase):
    """AC-6 of task0001 (FR5, D1)."""

    def step_5_1(self):
        body = self.section("5. ")
        start = body.find("1. GitHub リポジトリの解決")
        end = body.find("2. PR の解決")
        self.assertTrue(0 <= start < end)
        return body[start:end]

    def test_ac6_step_5_1_states_repo_is_host_owner_name_passed_verbatim(self):
        text = self.step_5_1()
        self.assertIn("`HOST/OWNER/NAME`", text)
        self.assertRegex(text, r"`--repo <repo>` には、この値をそのまま渡す")

    def test_ac6_repo_is_no_longer_described_as_owner_name(self):
        self.assertNotIn("（owner/name）", self.text)
        self.assertNotIn("owner/name", self.step_5_1())

    def test_ac6_the_held_values_list_describes_repo_the_same_way(self):
        body = self.section("保持する値")
        self.assertIn("`HOST/OWNER/NAME`", body)
        self.assertNotIn("owner/name", body)

    def test_ac6_every_repo_option_in_a_command_form_is_the_repo_value(self):
        forms = [f for f in command_forms(self.text) if "--repo" in f]
        self.assertGreaterEqual(len(forms), 5, forms)
        for form in forms:
            self.assertRegex(form, REPO_OPTION_RE)
            self.assertEqual(form.count("--repo"), 1, form)

    def test_ac6_gh_pr_create_and_merge_forms_are_unchanged_and_carry_no_repo(self):
        blocks = bash_blocks(self.text)
        create = block_lines(blocks, lambda line: line.startswith("gh pr create"))
        merge = block_lines(blocks, lambda line: line.startswith("gh pr merge"))
        self.assertEqual(len(create), 1)
        self.assertEqual(len(merge), 1)
        self.assertEqual(blocks[create[0]].body, [GH_PR_CREATE_FORM])
        self.assertEqual(blocks[merge[0]].body, [GH_PR_MERGE_FORM])
        for form in (GH_PR_CREATE_FORM, GH_PR_MERGE_FORM):
            self.assertNotIn("--repo", form)

    def test_ac6_the_repo_matcher_fires_on_forged_forms(self):
        good = "python3 x.py resolve --repo <repo> --feature <feature>"
        self.assertRegex(good, REPO_OPTION_RE)
        for forged in (
            "python3 x.py resolve --repo owner/name --feature <feature>",
            "python3 x.py resolve --repo <repo>/x --feature <feature>",
            "python3 x.py resolve --repo-name <repo>",
        ):
            self.assertIsNone(REPO_OPTION_RE.search(forged), forged)


if __name__ == "__main__":
    unittest.main()
