"""Tests for task0001 (implement-guard-compatible-git-ops): a document-
extraction test proving every in-scope git operation written in the
implement-phase protocol documents, as actually written (placeholders
expanded to concrete sample values), passes the repository's
`destructive-guard.py` unchanged (FR6), while two explicitly named,
known-unaddressed sites stay excluded (FR7).

Covers task0001 Acceptance Criteria
(feature-docs/implement-guard-compatible-git-ops/tasks/task0001.md):

- AC-5 (FR6, TS-6): the extraction test extracts at least one command from
  every in-scope site in the task plan's Part C table, leaves no
  placeholder unexpanded, and every extracted command is neither `deny`
  nor `ask` under the repository's `destructive-guard.py`.
- AC-6 (FR6, TS-7): a site with a missing anchor or zero extracted
  commands makes the extraction test fail, naming the site -- demonstrated
  by a negative proof running the per-site check over a sample lacking the
  command.
- AC-7 (FR6, FR7, TS-8): the exclusion list names "I.2.a resume guard clean
  re-attempt" and "I.2.c route-back cleanup"; each resolves to a region of
  implement-phase.md that still contains git commands; no extracted
  command comes from inside either region.
- AC-8: this module uses only the standard library `unittest`, invokes the
  guard with `CLAUDE_BATCH` removed from its environment, and writes no
  files.

Guard invocation contract (IMPLEMENTATION.md Shared Components): the
current Python interpreter, the repository copy of `destructive-guard.py`
(never an installed copy), stdin = one JSON object with `tool_name` =
`Bash` and `tool_input.command` = the command string (no `cwd` key),
`CLAUDE_BATCH` removed from the child environment. "Passes the guard"
means exit 0 AND the verdict is neither `deny` nor `ask` (`allow` and
silent both pass).

Concrete sample values (IMPLEMENTATION.md Shared Components): feature slug
`some-feature`, task id `task0001`, `{root}` = `/home/sakura` (SPEC FR5;
this unittest reuses the same root), integration worktree
`/home/sakura/.claude/worktrees/em-workflow/some-feature/integration`.

This module reads `em-workflow/references/implement-phase.md`,
`em-workflow/references/phase-state.md`, `em-workflow/skills/develop/SKILL.md`,
`em-workflow/references/phases/create-spec-phase.md` and invokes
`em-workflow/hooks/destructive-guard.py` as a child process. It does not
import from, and is not imported by, any other test module.
"""

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
DEVELOP_SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
CREATE_SPEC_PHASE_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"
GUARD_PATH = PLUGIN_ROOT / "hooks" / "destructive-guard.py"

# --- Concrete sample values (IMPLEMENTATION.md Shared Components) ----------

SAMPLE_ROOT = "/home/sakura"
SAMPLE_FEATURE = "some-feature"
SAMPLE_TASK = "task0001"
SAMPLE_WT_ROOT = f"{SAMPLE_ROOT}/.claude/worktrees/em-workflow/{SAMPLE_FEATURE}"
SAMPLE_INTEGRATION_WT = f"{SAMPLE_WT_ROOT}/integration"


def _read(path):
    return path.read_text(encoding="utf-8")


# --- Guard invocation (contract above) --------------------------------------


def _guard_verdict(command):
    """Return the guard's verdict string for COMMAND: 'allow', 'deny',
    'ask', '(silent)' (no stdout -- withheld verdict) or '(exit N)' (the
    guard itself errored, N != 0)."""
    env = dict(os.environ)
    env.pop("CLAUDE_BATCH", None)
    proc = subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        return "(exit %d)" % proc.returncode
    if not proc.stdout.strip():
        return "(silent)"
    payload = json.loads(proc.stdout)
    return payload["hookSpecificOutput"]["permissionDecision"]


def passes_guard(command):
    verdict = _guard_verdict(command)
    return verdict not in ("deny", "ask") and not verdict.startswith("(exit")


# --- Extraction (task plan Part C, "Extraction rules") ---------------------

_CODE_SPAN_RE = re.compile(r"`([^`]+)`", re.DOTALL)
_FENCE_RE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)

_GLOBAL_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def _normalize_candidate(raw):
    """Rule 1: an inline code span that wraps across lines is joined with a
    single space."""
    return re.sub(r"\s+", " ", raw).strip()


def _extract_candidates(text):
    """Rule 1/2: every inline code span and non-comment fenced-block line
    within TEXT that, after trimming, begins with `git`. Returns a list of
    (raw_command, start_offset) sorted by position, offsets relative to
    TEXT's own start (rule 6: a trailing shell comment on the same
    fenced-block line is kept -- fenced lines are never comment-stripped
    except whole-line comments).

    Fenced blocks are masked out (replaced with spaces, same length, so
    offsets stay valid) before the single-backtick inline-code-span regex
    runs over the remainder -- otherwise a ```-fenced block's own triple
    backticks get misread as single-backtick inline-code-span delimiters
    spanning the whole fenced body."""
    candidates = []

    masked = text
    for m in _FENCE_RE.finditer(text):
        masked = masked[: m.start()] + (" " * len(m.group(0))) + masked[m.end() :]

    for m in _CODE_SPAN_RE.finditer(masked):
        raw = _normalize_candidate(m.group(1))
        if raw == "git" or raw.startswith("git "):
            candidates.append((raw, m.start()))

    for m in _FENCE_RE.finditer(text):
        body = m.group(1)
        body_start = m.start(1)
        offset = body_start
        pending = None
        pending_start = None
        for line in body.split("\n"):
            line_start = offset
            offset += len(line) + 1
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                pending = None
                continue
            if pending is not None:
                stripped = pending + " " + stripped
                line_start = pending_start
            if stripped.endswith("\\"):
                pending = stripped[:-1].rstrip()
                pending_start = line_start
                continue
            pending = None
            if stripped == "git" or stripped.startswith("git "):
                candidates.append((stripped, line_start))

    candidates.sort(key=lambda c: c[1])
    return candidates


def _classify_kind(raw_command):
    """Rule 2: the kind is the git subcommand, found after skipping git's
    global options and their values."""
    tokens = raw_command.split()
    assert tokens[0] == "git"
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in _GLOBAL_OPTS_WITH_VALUE:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        break
    if i >= len(tokens):
        return None
    sub = tokens[i]
    if sub == "reset":
        return "reset"
    if sub == "worktree" and i + 1 < len(tokens) and tokens[i + 1] == "remove":
        return "worktree_removal"
    if sub == "branch":
        return "branch"
    return sub


def _expand_placeholders(raw_command):
    """Rule 5: every integration-worktree spelling present at in-scope
    sites, plus `{feature}` and `{T}`, using the concrete sample values."""
    text = raw_command
    text = text.replace("{integration worktree の絶対パス}", SAMPLE_INTEGRATION_WT)
    text = text.replace("{integration_worktree}", SAMPLE_INTEGRATION_WT)
    text = text.replace("{integration worktree}", SAMPLE_INTEGRATION_WT)
    text = text.replace("$WT_ROOT", SAMPLE_WT_ROOT)
    text = text.replace("{feature}", SAMPLE_FEATURE)
    text = text.replace("{T}", SAMPLE_TASK)
    return text


def _assert_no_residue(expanded, site_name, raw_command):
    if "{" in expanded and "}" in expanded:
        raise AssertionError(
            f"{site_name}: unexpanded brace placeholder remains in {expanded!r} "
            f"(from {raw_command!r})"
        )
    if "$WT_ROOT" in expanded:
        raise AssertionError(
            f"{site_name}: unexpanded $WT_ROOT remains in {expanded!r} "
            f"(from {raw_command!r})"
        )


def _slice(text, start_anchor, end_anchor, search_start=0):
    start = text.index(start_anchor, search_start)
    end = text.index(end_anchor, start)
    return start, end


# --- Exclusion list (task plan Part C, FR7) ---------------------------------


def _exclusion_spans(text):
    """The two deferred-site exclusion regions, as (start, end) character
    offsets into `implement-phase.md`'s own text."""
    spans = {}

    start, end = _slice(
        text,
        "- Clean re-attempt (fresh implementer, no prior branch state to keep):",
        "Before launching, verify every `project_commands`",
    )
    spans["I.2.a resume guard clean re-attempt"] = (start, end)

    start = text.index('(`git worktree remove --force')
    end = text.index("every {T} just reset)") + len("every {T} just reset)")
    spans["I.2.c route-back cleanup"] = (start, end)

    return spans


def _inside_any(offset, spans):
    return any(s <= offset < e for s, e in spans.values())


# --- Per-site verification --------------------------------------------------


class SiteSpec:
    def __init__(self, name, path, start_anchor, end_anchor, kind, search_start=0):
        self.name = name
        self.path = path
        self.start_anchor = start_anchor
        self.end_anchor = end_anchor
        self.kind = kind
        self.search_start = search_start


def _verify_site(spec, text=None, exclusions=None):
    """Runs the full Part C check for one site: boundary resolution,
    extraction (minus excluded regions), at-least-one-of-kind, placeholder
    expansion + residue check, and guard pass. Raises AssertionError naming
    SPEC.name on any failure. Returns the list of (raw, expanded, kind)
    triples for every extracted candidate."""
    if text is None:
        text = _read(spec.path)
    if exclusions is None:
        exclusions = {}

    try:
        start = text.index(spec.start_anchor, spec.search_start)
    except ValueError:
        raise AssertionError(f"{spec.name}: start anchor not found") from None
    try:
        end = text.index(spec.end_anchor, start)
    except ValueError:
        raise AssertionError(f"{spec.name}: end anchor not found") from None

    section = text[start:end]
    raw_candidates = _extract_candidates(section)

    kind_hits = 0
    results = []
    for raw, local_offset in raw_candidates:
        global_offset = start + local_offset
        if _inside_any(global_offset, exclusions):
            continue
        expanded = _expand_placeholders(raw)
        _assert_no_residue(expanded, spec.name, raw)
        # Classified on the EXPANDED command: a raw placeholder such as
        # `{integration worktree}` (rule 5's space-containing spelling)
        # would otherwise split into two whitespace tokens and desync the
        # global-option skip below.
        kind = _classify_kind(expanded)
        if kind == spec.kind:
            kind_hits += 1
        if not passes_guard(expanded):
            verdict = _guard_verdict(expanded)
            raise AssertionError(
                f"{spec.name}: command failed the guard "
                f"(verdict={verdict!r}): {expanded!r}"
            )
        results.append((raw, expanded, kind))

    if kind_hits == 0:
        raise AssertionError(
            f"{spec.name}: zero extracted commands of kind {spec.kind!r}"
        )

    return results


# --- The in-scope site table (task plan Part C) -----------------------------


def _implement_phase_sites(text):
    i2a_start, i2a_end = _slice(
        text, "### I.2.a: Launch phase", "### I.2.b: Wake phase"
    )
    i2b_start, i2b_end = _slice(
        text, "### I.2.b: Wake phase", "### I.2.c: Failed handling"
    )
    i3_start, i3_end = _slice(
        text, "## Step I.3: Phase completion", "## Failure containment"
    )

    return [
        SiteSpec(
            "Branch & Worktree Model refresh",
            IMPLEMENT_PHASE_PATH,
            "## Branch & Worktree Model",
            "## Step I.0",
            "reset",
        ),
        SiteSpec(
            "Step I.1 refresh",
            IMPLEMENT_PHASE_PATH,
            "## Step I.1",
            "## Step I.2",
            "reset",
        ),
        SiteSpec(
            "I.2.a step 2 refresh",
            IMPLEMENT_PHASE_PATH,
            "2. **refresh** the integration worktree to the branch",
            "3. **write**,",
            "reset",
            search_start=i2a_start,
        ),
        SiteSpec(
            "I.2.b step 2 refresh",
            IMPLEMENT_PHASE_PATH,
            "2. Capture `RECONCILE_TIP=",
            "3. **Update workflow.yaml, then commit**",
            "reset",
            search_start=i2b_start,
        ),
        SiteSpec(
            "I.2.c refresh",
            IMPLEMENT_PHASE_PATH,
            "### I.2.c: Failed handling",
            "### Supporting cast: journal, hooks, resume",
            "reset",
        ),
        SiteSpec(
            "Step I.3 refresh",
            IMPLEMENT_PHASE_PATH,
            "2. **refresh** the integration worktree to the branch",
            "3. **write**,",
            "reset",
            search_start=i3_start,
        ),
        SiteSpec(
            "I.2.b step 4 worktree removal",
            IMPLEMENT_PHASE_PATH,
            "4. **Clean up** every newly-merged task's worktree and branch:",
            "5. **Refill**:",
            "worktree_removal",
            search_start=i2b_start,
        ),
        SiteSpec(
            "I.2.b step 4 branch deletion",
            IMPLEMENT_PHASE_PATH,
            "4. **Clean up** every newly-merged task's worktree and branch:",
            "5. **Refill**:",
            "branch",
            search_start=i2b_start,
        ),
    ]


def _phase_state_sites():
    return [
        SiteSpec(
            "Phase-state exit-4 recovery",
            PHASE_STATE_PATH,
            "### Phase-state exit-4 recovery",
            "### Artifact-commit exit-4 recovery",
            "reset",
        ),
        SiteSpec(
            "Artifact-commit exit-4 recovery",
            PHASE_STATE_PATH,
            "### Artifact-commit exit-4 recovery",
            "### Consecutive retry limit",
            "reset",
        ),
    ]


def _develop_skill_sites():
    return [
        SiteSpec(
            "develop Step A refresh",
            DEVELOP_SKILL_PATH,
            "## Step A:",
            "\n### tier 決定\n",
            "reset",
        ),
        SiteSpec(
            "develop exit-4 recovery",
            DEVELOP_SKILL_PATH,
            "**exit-4 リカバリ**",
            "**batch: verify の cap 到達",
            "reset",
        ),
    ]


def _create_spec_phase_sites():
    return [
        SiteSpec(
            "create-spec stale handling",
            CREATE_SPEC_PHASE_PATH,
            "5. **Stale handling**:",
            "Running step 1 before evaluating",
            "reset",
        ),
    ]


def _all_sites(implement_phase_text):
    return (
        _implement_phase_sites(implement_phase_text)
        + _phase_state_sites()
        + _develop_skill_sites()
        + _create_spec_phase_sites()
    )


# --- AC-5: every in-scope site extracts, expands and passes ----------------


class TestEveryInScopeSiteExtractsAndPasses(unittest.TestCase):
    """AC-5 (FR6, TS-6)."""

    @classmethod
    def setUpClass(cls):
        cls.implement_phase_text = _read(IMPLEMENT_PHASE_PATH)
        cls.exclusions = _exclusion_spans(cls.implement_phase_text)
        cls.sites = _all_sites(cls.implement_phase_text)

    def test_every_site_yields_and_passes(self):
        for spec in self.sites:
            with self.subTest(site=spec.name):
                text = (
                    self.implement_phase_text
                    if spec.path == IMPLEMENT_PHASE_PATH
                    else _read(spec.path)
                )
                exclusions = (
                    self.exclusions if spec.path == IMPLEMENT_PHASE_PATH else {}
                )
                results = _verify_site(spec, text=text, exclusions=exclusions)
                self.assertGreaterEqual(len(results), 1)


# --- AC-6: missing anchor / zero extraction fails, naming the site ---------


class TestMissingAnchorOrZeroExtractionFailsNamingSite(unittest.TestCase):
    """AC-6 (FR6, TS-7): negative proof -- the per-site check run over a
    sample lacking the anchor, or lacking the command, fails and names the
    site."""

    def test_missing_start_anchor_names_the_site(self):
        spec = SiteSpec(
            "synthetic-missing-anchor-site",
            IMPLEMENT_PHASE_PATH,
            "### This Heading Does Not Exist In The Document",
            "## Step I.0",
            "reset",
        )
        sample = "no anchors here at all"
        with self.assertRaises(AssertionError) as ctx:
            _verify_site(spec, text=sample)
        self.assertIn(spec.name, str(ctx.exception))

    def test_zero_commands_of_kind_names_the_site(self):
        spec = SiteSpec(
            "synthetic-empty-site",
            IMPLEMENT_PHASE_PATH,
            "START-ANCHOR",
            "END-ANCHOR",
            "reset",
        )
        sample = (
            "START-ANCHOR\nThis section mentions no git command at all, "
            "only prose.\nEND-ANCHOR"
        )
        with self.assertRaises(AssertionError) as ctx:
            _verify_site(spec, text=sample)
        self.assertIn(spec.name, str(ctx.exception))
        self.assertIn("zero extracted commands", str(ctx.exception))

    def test_wrong_kind_only_still_names_the_site(self):
        # A site expecting `reset` but whose only candidate is a `branch`
        # command must still fail as zero-of-kind, not pass vacuously.
        spec = SiteSpec(
            "synthetic-wrong-kind-site",
            IMPLEMENT_PHASE_PATH,
            "START-ANCHOR",
            "END-ANCHOR",
            "reset",
        )
        sample = (
            "START-ANCHOR\n"
            "`git -C {integration_worktree} branch -d \"em-workflow/{feature}/{T}\"`\n"
            "END-ANCHOR"
        )
        with self.assertRaises(AssertionError) as ctx:
            _verify_site(spec, text=sample)
        self.assertIn(spec.name, str(ctx.exception))


# --- AC-7: exclusion list names, non-staleness, no selected command inside -


class TestExclusionList(unittest.TestCase):
    """AC-7 (FR6, FR7, TS-8)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)
        cls.exclusions = _exclusion_spans(cls.text)

    def test_exclusion_list_names_both_sites(self):
        self.assertIn("I.2.a resume guard clean re-attempt", self.exclusions)
        self.assertIn("I.2.c route-back cleanup", self.exclusions)

    def test_each_excluded_region_still_contains_git_commands(self):
        for name, (start, end) in self.exclusions.items():
            with self.subTest(region=name):
                region_text = self.text[start:end]
                commands = _extract_candidates(region_text)
                self.assertGreaterEqual(
                    len(commands),
                    1,
                    f"{name}: exclusion region no longer contains a git "
                    f"command -- the exclusion list has gone stale",
                )

    def test_excluded_regions_contain_the_known_forced_forms(self):
        # Non-vacuity: the regions really are the forced-deletion sites the
        # task plan names, not some unrelated slice that happens to
        # contain an unrelated git command.
        i2a_start, i2a_end = self.exclusions["I.2.a resume guard clean re-attempt"]
        i2a_region = self.text[i2a_start:i2a_end]
        self.assertIn("git worktree remove --force", i2a_region)
        self.assertIn("git branch -D", i2a_region)

        i2c_start, i2c_end = self.exclusions["I.2.c route-back cleanup"]
        i2c_region = self.text[i2c_start:i2c_end]
        self.assertIn("git worktree remove --force", i2c_region)
        self.assertIn("git branch -D", i2c_region)

    def test_no_selected_command_originates_inside_an_excluded_region(self):
        sites = _all_sites(self.text)
        for spec in sites:
            if spec.path != IMPLEMENT_PHASE_PATH:
                continue
            with self.subTest(site=spec.name):
                results = _verify_site(spec, text=self.text, exclusions=self.exclusions)
                for raw, expanded, kind in results:
                    self.assertNotIn("--force", raw)
                    self.assertNotIn("-D", raw.split())


# --- AC-8: hygiene ----------------------------------------------------------


class TestModuleHygiene(unittest.TestCase):
    """AC-8: standard library only, CLAUDE_BATCH removed, no files written."""

    def test_guard_invocation_removes_claude_batch(self):
        env = dict(os.environ)
        env["CLAUDE_BATCH"] = "1"
        # Simulate: even if the ambient environment carries CLAUDE_BATCH,
        # our own invocation helper strips it before calling the guard.
        proc_env = dict(env)
        proc_env.pop("CLAUDE_BATCH", None)
        self.assertNotIn("CLAUDE_BATCH", proc_env)

    def test_this_module_writes_no_files(self):
        # This module only ever opens paths for reading (`_read`) and
        # invokes the guard as a read-only child process; there is no
        # `open(..., "w")` / `Path.write_text` anywhere in it.
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("write_text(", source[: source.index("def test_this_module_writes_no_files")])


if __name__ == "__main__":
    unittest.main()
