"""Tests for the batch second-opinion consultation's harness chain.

The Codex consultation in em-workflow/references/question-resolution.md used
to run on one harness: the Codex CLI, with the Opus escalation standing in
whenever the wrapper was unavailable. It now walks a two-entry chain --
`codex` first, then `litellm` with the model `muse-spark` -- and only falls
to the escalation once no entry of that chain is left.

- AC-1: run_codex_exec.sh accepts `--litellm MODEL` and expands it to
  `-p litellm -m MODEL`, passing MODEL through verbatim.
- AC-2: the `--litellm` path does NOT pass `--ignore-user-config`, which
  suppresses the profile layering `-p litellm` depends on; the default path
  still does pass it, and names no model.
- AC-3: `--litellm` with no model argument is a usage error, and the flag is
  advertised in the usage message.
- AC-4: the wrapper still launches `codex exec` exactly once per invocation
  on the `--litellm` path -- the chain lives in the consultation procedure,
  never inside the wrapper.
- AC-5: question-resolution.md's availability probe describes both entries in
  order, states the litellm entry's own prerequisites, states that the
  vertex-review plugin is not among them, and delegates the contributor-tier
  read-mapping to references/reviewers.yaml instead of restating it.
- AC-6: the wrapper-invocation step carries `--litellm muse-spark`, and the
  chain advances on the wrapper's exit code alone -- never by classifying the
  reply, which is what the wrapper's own no-response-shape-recognition
  contract requires.
- AC-7: the end-of-consultation reasons and the Opus escalation's entry
  condition both cover an exhausted chain, and step 10 records which entry
  answered.
- AC-8: neither registry assigns a model other than `muse-spark` on the
  litellm harness.
- AC-9: the contributor-consent guard classifies a contributor-tier
  selection made through the wrapper's `--litellm`, in both plugin copies.
  Before `--litellm` existed the wrapper could not name a model at all, so
  the guard only had to recognize a bare `codex` invocation; the flag makes
  the tier reachable without the word `codex` appearing anywhere in the
  command.

Per Test Notes: standard library only. The wrapper is exercised through a
stubbed `codex` first on PATH that appends its argv to a JSON-lines log --
the subprocess-harness pattern tests/test_codex_wrapper_single_invocation.py
already uses -- so the assertions are about the real launch, not about the
script's text.

Contributor-tier gating of the litellm entry (feature
consult-litellm-contributor-tier, task0001). The consultation procedure used
to carry one fixed example, `--litellm muse-spark`, and the orchestrator
copied it literally instead of following the contributor-tier reading the
procedure cites. The procedure now determines `contributor_consented` once
per consultation (step 1) and picks the litellm invocation from it (step 2).
The cases in TestConsultationProcedureChain that carry a "contributor-tier
AC-n" comment pin that behavior on the document text:

- AC-1: step 1 names `contributor_consented`, runs the consent-check command
  pinned by tests/test_contributor_tier_criteria.py, runs it only when the
  litellm entry is available and before the first turn, and states the
  true / false rule.
- AC-2: step 2 names `contributor_consented` and carries both invocations;
  the standard form is matched as a standalone flag value, because it is a
  prefix of the contributor form.
- AC-3: the value is fixed for the whole consultation, including turns after
  a mid-consultation move from codex to litellm.
- AC-6: a failed check yields false even when the failed run printed a line.
"""

import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "run_codex_exec.sh"
QUESTION_RESOLUTION_DOC = (
    REPO_ROOT / "em-workflow" / "references" / "question-resolution.md"
)
EM_WORKFLOW_REVIEWERS = REPO_ROOT / "em-workflow" / "references" / "reviewers.yaml"
EM_REVIEW_REVIEWERS = REPO_ROOT / "em-review" / "references" / "reviewers.yaml"
GUARD_PATHS = {
    "em-workflow": REPO_ROOT / "em-workflow" / "hooks" / "muse_guard.py",
    "em-review": REPO_ROOT / "em-review" / "hooks" / "muse_guard.py",
}

STUB_SOURCE = """#!/usr/bin/env python3
import json
import os
import sys

with open(os.environ["CODEX_STUB_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:]}) + "\\n")

print("STUB_ANSWER: ok")
sys.exit(0)
"""


def _norm(text):
    return re.sub(r"\s+", " ", text)


CONTRIBUTOR_TIER_CRITERIA_TESTS = (
    REPO_ROOT / "tests" / "test_contributor_tier_criteria.py"
)


def _pinned_consent_check_command():
    """CONSENT_CHECK_COMMAND exactly as tests/test_contributor_tier_criteria.py
    pins it for review-phase.md Phase R0 and the registries. Loaded from that
    file by path (so it works under both `discover -s tests` and
    `-m unittest tests.<module>`) rather than re-typed here, so the
    consultation procedure and the review phase cannot drift apart."""
    spec = importlib.util.spec_from_file_location(
        "_contributor_tier_criteria_pins", CONTRIBUTOR_TIER_CRITERIA_TESTS
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CONSENT_CHECK_COMMAND


def _between(text, start, end):
    """The slice of `text` from `start` up to (not including) `end`."""
    head = text.index(start)
    return text[head : text.index(end, head + len(start))]


# The standard-tier flag value is a prefix of the contributor-tier one, so a
# plain substring check for it is satisfied by the contributor form alone. A
# standalone occurrence is one not continued by another name character.
STANDARD_INVOCATION = re.compile(r"--litellm muse-spark(?![\w\-])")
CONTRIBUTOR_INVOCATION = "--litellm muse-spark-contributor"


def _run_wrapper(*args):
    """Run the wrapper with a stubbed `codex` first on PATH. Returns
    (CompletedProcess, [launch argv, ...])."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        bindir = tmpdir / "bin"
        bindir.mkdir()
        stub = bindir / "codex"
        stub.write_text(STUB_SOURCE, encoding="utf-8")
        stub.chmod(0o755)
        log_path = tmpdir / "launches.jsonl"

        env = dict(os.environ)
        env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
        env["CODEX_STUB_LOG"] = str(log_path)
        env["HOME"] = str(tmpdir)

        proc = subprocess.run(
            [str(SCRIPT_PATH), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmpdir),
        )
        launches = [
            json.loads(line)["argv"]
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ] if log_path.is_file() else []
        return proc, launches


def _flag_value(argv, flag):
    """The argument following `flag`, or None when the flag is absent."""
    for i, token in enumerate(argv):
        if token == flag and i + 1 < len(argv):
            return argv[i + 1]
    return None


class TestWrapperLitellmFlag(unittest.TestCase):
    """AC-1 through AC-4: the wrapper's own launch."""

    def test_litellm_expands_to_profile_and_model(self):
        proc, launches = _run_wrapper("readonly", "--litellm", "muse-spark", "hi")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(launches), 1)
        argv = launches[0]
        self.assertEqual(_flag_value(argv, "-p"), "litellm")
        self.assertEqual(_flag_value(argv, "-m"), "muse-spark")

    def test_model_value_passes_through_verbatim(self):
        # AC-1: the wrapper never defaults, rewrites or tier-maps the name.
        proc, launches = _run_wrapper(
            "readonly", "--litellm", "some-other-model", "hi"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(_flag_value(launches[0], "-m"), "some-other-model")

    def test_litellm_path_drops_ignore_user_config(self):
        # AC-2: --ignore-user-config suppresses the `-p litellm` profile
        # layering, so it must not reach the launch on this path.
        _proc, launches = _run_wrapper("readonly", "--litellm", "muse-spark", "hi")
        self.assertNotIn("--ignore-user-config", launches[0])

    def test_default_path_keeps_ignore_user_config_and_names_no_model(self):
        # AC-2, the other half: the pre-existing path is untouched.
        _proc, launches = _run_wrapper("readonly", "hi")
        argv = launches[0]
        self.assertIn("--ignore-user-config", argv)
        self.assertNotIn("-p", argv)
        self.assertNotIn("-m", argv)

    def test_litellm_composes_with_workdir_flag(self):
        _proc, launches = _run_wrapper(
            "readonly", "--litellm", "muse-spark", "-C", "/tmp", "hi"
        )
        argv = launches[0]
        self.assertEqual(_flag_value(argv, "-C"), "/tmp")
        self.assertEqual(_flag_value(argv, "-m"), "muse-spark")

    def test_litellm_without_model_is_a_usage_error(self):
        # AC-3
        proc, launches = _run_wrapper("readonly", "--litellm")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--litellm requires a model argument", proc.stderr)
        self.assertEqual(launches, [])

    def test_usage_message_advertises_the_flag(self):
        # AC-3: a flag the script accepts is named where it tells the caller
        # what it accepts.
        proc, _launches = _run_wrapper("readonly")
        self.assertIn("--litellm", proc.stderr)

    def test_exactly_one_launch_on_the_litellm_path(self):
        # AC-4: no chain inside the wrapper.
        _proc, launches = _run_wrapper("readonly", "--litellm", "muse-spark", "hi")
        self.assertEqual(len(launches), 1)


class TestConsultationProcedureChain(unittest.TestCase):
    """AC-5 through AC-7: question-resolution.md's consultation procedure."""

    @classmethod
    def setUpClass(cls):
        cls.text = QUESTION_RESOLUTION_DOC.read_text(encoding="utf-8")
        marker = "### Codex consultation procedure"
        assert marker in cls.text
        cls.section = cls.text.split(marker, 1)[1]
        cls.norm_section = _norm(cls.section)
        # Step ranges, cut from the whitespace-normalized section so line
        # wrapping never matters. Step 1 runs up to the step 2 heading, step 2
        # up to the step 3 heading, and the combined range up to step 3.
        step_1 = "1. **Availability probe.**"
        step_2 = "2. **Wrapper invocation.**"
        step_3 = "3. **One turn per call.**"
        cls.step_1 = _between(cls.norm_section, step_1, step_2)
        cls.step_2 = _between(cls.norm_section, step_2, step_3)
        cls.step_1_to_2 = _between(cls.norm_section, step_1, step_3)

    def test_probe_states_two_entries_in_order(self):
        # AC-5
        self.assertIn(
            "two harness entries, tried in this order — `codex`, then "
            "`litellm` with the model `muse-spark`",
            self.norm_section,
        )

    def test_probe_states_one_consultation_runs_on_one_entry(self):
        # AC-5: the chain reaches a reachable harness; it is not a second
        # opinion placed beside an answer already given.
        self.assertIn(
            "one consultation runs entirely on the first of them that "
            "probes available",
            self.norm_section,
        )
        self.assertIn(
            "never to place a second model beside an answer an entry "
            "already gave",
            self.norm_section,
        )

    def test_litellm_probe_names_its_own_prerequisites(self):
        # AC-5
        self.assertIn('[ -n "${LITELLM_API_KEY:-}" ]', self.section)
        self.assertIn(
            '[ -f "${CODEX_HOME:-$HOME/.codex}/litellm.config.toml" ]',
            self.section,
        )

    def test_litellm_probe_excludes_the_vertex_review_plugin(self):
        # AC-5: narrower than review-phase.md Phase R0's probe, and the
        # reason is stated rather than left implicit.
        self.assertIn(
            "`vertex-review` plugin is deliberately NOT part of this probe",
            self.norm_section,
        )
        self.assertIn("no reviewer agent is dispatched", self.norm_section)
        self.assertIn("references/review-phase.md", self.section)

    def test_contributor_read_mapping_is_cited_not_restated(self):
        # AC-5: one rule, owned by the registry.
        self.assertIn(
            "`references/reviewers.yaml`'s contributor-tier pre-dispatch "
            "criteria (cited, not restated)",
            self.norm_section,
        )
        self.assertIn(
            "the model name written here is never edited to reach that tier",
            self.norm_section,
        )
        # The registry's own criteria text must not be duplicated here.
        self.assertNotIn("Outside the scope of consent", self.section)

    def test_exhausted_chain_reaches_the_escalation(self):
        # AC-5: the pre-existing escalation wording still governs, now
        # keyed on the whole chain rather than on one wrapper.
        self.assertIn(
            "No entry available → skip straight to the Opus escalation "
            "below, which runs in Codex's place",
            self.norm_section,
        )

    def test_wrapper_invocation_carries_the_litellm_flag(self):
        # AC-6
        self.assertIn("`--litellm muse-spark`", self.norm_section)
        self.assertIn("`-p litellm -m muse-spark`", self.norm_section)

    def test_advance_is_decided_on_the_exit_code_alone(self):
        # AC-6: no response-shape recognition, matching the wrapper's
        # contract. The absence of rate-limit prose is pinned separately in
        # tests/test_question_resolution_doc.py; this is the positive half.
        self.assertIn(
            "A turn whose wrapper call exits non-zero", self.norm_section
        )
        self.assertIn("decided on the exit code alone", self.norm_section)
        self.assertIn(
            "the reply is never inspected to classify why the launch failed",
            self.norm_section,
        )

    def test_turns_already_spent_still_count_against_the_ceiling(self):
        # AC-6: advancing does not buy a fresh five-turn budget.
        self.assertIn(
            "Turns already spent still count against the ceiling below",
            self.norm_section,
        )

    def test_last_entry_failure_ends_the_consultation(self):
        # AC-7
        self.assertIn(
            "A non-zero exit on the last available entry ends the "
            "consultation",
            self.norm_section,
        )

    def test_end_of_consultation_reasons_cover_the_exhausted_chain(self):
        # AC-7, fallback-sequence step 6.
        norm_text = _norm(self.text)
        self.assertIn(
            "a non-zero wrapper exit hit the last available entry of the "
            "consultation's harness chain, or the availability probe found "
            "no entry of that chain available",
            norm_text,
        )

    def test_escalation_entry_condition_covers_the_exhausted_chain(self):
        # AC-7
        escalation = _norm(self.text.split("### Opus escalation", 1)[1])
        self.assertIn(
            "by a non-zero wrapper exit on the last available entry of its "
            "harness chain",
            escalation,
        )
        self.assertIn(
            "the availability probe found no entry of that chain available "
            "and no consultation turn ran at all",
            escalation,
        )

    def test_step_10_records_which_entry_answered(self):
        # AC-7
        self.assertIn(
            "when a consultation turn ran, which entry of the "
            "consultation's harness chain answered",
            _norm(self.text),
        )

    # -- Contributor-tier gating of the litellm entry ----------------------

    def test_step_1_determines_contributor_consent_with_the_pinned_command(self):
        # contributor-tier AC-1: the field name and the consent-check command
        # that review-phase.md Phase R0 runs, identical to the pinned string.
        self.assertIn("contributor_consented", self.step_1)
        self.assertIn(_pinned_consent_check_command(), self.step_1)

    def test_step_1_runs_the_check_only_for_an_available_entry_before_turn_one(
        self,
    ):
        # contributor-tier AC-1: when the determination runs.
        self.assertIn("this entry is judged available", self.step_1)
        self.assertIn("before the consultation's first turn", self.step_1)

    def test_step_1_states_the_true_and_false_rule(self):
        # contributor-tier AC-1: one printed line is consent; nothing printed
        # or a failure is not.
        self.assertIn(
            "true when the command succeeds and prints one line", self.step_1
        )
        self.assertIn("false when it prints nothing or fails", self.step_1)

    def test_step_2_names_both_invocations_and_the_consent_value(self):
        # contributor-tier AC-2: the field name, the contributor form for the
        # true case and the standard form for the false case. The standard
        # form is matched as a standalone value, not as a prefix.
        self.assertIn("contributor_consented", self.step_2)
        self.assertIn(CONTRIBUTOR_INVOCATION, self.step_2)
        self.assertRegex(self.step_2, STANDARD_INVOCATION)

    def test_step_2_ties_each_invocation_to_its_consent_value(self):
        # contributor-tier AC-2: true selects the contributor model and false
        # the standard one -- never the other way round.
        self.assertIn(
            "`--litellm muse-spark-contributor` when it is true", self.step_2
        )
        self.assertIn("`--litellm muse-spark` when it is false", self.step_2)

    def test_step_2_standard_form_check_is_not_satisfied_by_the_contributor_form(
        self,
    ):
        # contributor-tier AC-2, the prefix trap: the standard form is a
        # prefix of the contributor form. Strip every standalone standard
        # occurrence from the real step 2; what is left carries the
        # contributor form alone, and the standard-form check must reject it.
        contributor_only = STANDARD_INVOCATION.sub(
            "--litellm <removed>", self.step_2
        )
        self.assertIn(CONTRIBUTOR_INVOCATION, contributor_only)
        self.assertNotRegex(contributor_only, STANDARD_INVOCATION)
        # The check itself: it rejects the contributor form alone and still
        # accepts the standard form beside it.
        self.assertIsNone(STANDARD_INVOCATION.search(CONTRIBUTOR_INVOCATION))
        self.assertIsNotNone(
            STANDARD_INVOCATION.search(
                f"{CONTRIBUTOR_INVOCATION} then --litellm muse-spark."
            )
        )

    def test_consent_value_is_fixed_for_the_whole_consultation(self):
        # contributor-tier AC-3: one determination, reused by every litellm
        # turn -- including turns after a mid-consultation move from codex to
        # litellm -- and never re-determined per turn.
        self.assertIn(
            "every `litellm` turn of that consultation uses it",
            self.step_1_to_2,
        )
        self.assertIn(
            "including the turns after a mid-consultation move from `codex` "
            "to `litellm`",
            self.step_1_to_2,
        )
        self.assertIn("never re-determined per turn", self.step_1_to_2)

    def test_a_failed_consent_check_yields_false_even_when_it_printed_a_line(
        self,
    ):
        # contributor-tier AC-6 (THREAT-MODEL.md TM-1): failure takes
        # precedence over the one-line rule, so a single-line error message
        # is never read as consent.
        self.assertIn(
            "A failure takes precedence over the one-line rule", self.step_1
        )
        self.assertIn(
            "a failed run that printed one line (for example a single-line "
            "error message) still yields false",
            self.step_1,
        )


class TestRegistriesAssignOnlyMuseSpark(unittest.TestCase):
    """AC-8: the litellm half of every chain is `muse-spark`."""

    def test_no_other_litellm_model_is_assigned(self):
        pattern = re.compile(r"\{harness:\s*litellm,\s*model:\s*([\w.\-]+)\}")
        for path in (EM_WORKFLOW_REVIEWERS, EM_REVIEW_REVIEWERS):
            text = path.read_text(encoding="utf-8")
            models = set(pattern.findall(text))
            with self.subTest(registry=path.name, plugin=path.parent.parent.name):
                self.assertEqual(models, {"muse-spark"})

    def test_no_retired_vertex_model_name_survives_anywhere_in_either_registry(
        self,
    ):
        for path in (EM_WORKFLOW_REVIEWERS, EM_REVIEW_REVIEWERS):
            text = path.read_text(encoding="utf-8").lower()
            for stale in ("vertex-glm", "vertex-deepseek", "deepseek"):
                with self.subTest(plugin=path.parent.parent.name, name=stale):
                    self.assertNotIn(stale, text)


def _load_guard(path):
    spec = importlib.util.spec_from_file_location(
        f"muse_guard_{path.parent.parent.name.replace('-', '_')}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Each row is (expected classification, label, command). The deny rows are
# what AC-9 adds; the allow rows are the no-misfire floor the flag must not
# erode -- a wrapper call on the Standard tier, and the pre-existing
# commit-message / search-pattern shapes the guard has always let through.
GUARD_CASES = [
    (
        True,
        "wrapper, flag and value as separate tokens",
        '"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly '
        '--litellm muse-spark-contributor -C /x "p"',
    ),
    (
        True,
        "wrapper, --litellm=value in one token",
        '/a/b/run_codex_exec.sh readonly --litellm=muse-spark-contributor "p"',
    ),
    (
        True,
        "wrapper behind a recognized wrapper word",
        'timeout 600 /a/run_codex_exec.sh readonly '
        '--litellm muse-spark-contributor "p"',
    ),
    (
        True,
        "wrapper inside a shell command string",
        "bash -c '/a/run_codex_exec.sh readonly "
        "--litellm muse-spark-contributor \"p\"'",
    ),
    (
        True,
        "bare codex on the contributor tier still classifies",
        'codex exec -p litellm -m muse-spark-contributor "p"',
    ),
    (
        False,
        "wrapper on the Standard tier",
        '"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly '
        '--litellm muse-spark -C /x "p"',
    ),
    (
        False,
        "wrapper with no model selection at all",
        '/a/run_codex_exec.sh readonly -C /x "p"',
    ),
    (
        False,
        "commit message that happens to be the tier name",
        "git commit -m muse-spark-contributor",
    ),
    (
        False,
        "search pattern that happens to be the tier name",
        "grep -m muse-spark-contributor file",
    ),
    (
        False,
        "the tier name as a plain argument to an unrelated command",
        "echo --litellm muse-spark-contributor",
    ),
    (
        False,
        "-m is not the wrapper's own flag",
        'run_codex_exec.sh readonly -m muse-spark-contributor "p"',
    ),
    (
        False,
        "--litellm is not codex's own flag",
        'codex exec --litellm muse-spark-contributor "p"',
    ),
]


class TestConsentGuardCoversTheWrapperFlag(unittest.TestCase):
    """AC-9: `--litellm` is a model selection the consent guard sees."""

    @classmethod
    def setUpClass(cls):
        cls.guards = {name: _load_guard(path) for name, path in GUARD_PATHS.items()}

    def test_classification(self):
        for expected, label, command in GUARD_CASES:
            for plugin, guard in self.guards.items():
                with self.subTest(plugin=plugin, case=label):
                    self.assertEqual(
                        guard.is_contributor_invocation(command),
                        expected,
                        f"{label}: {command}",
                    )

    def test_case_table_is_non_vacuous(self):
        # Both verdicts are actually exercised, so a classifier stuck on one
        # answer cannot pass the table above.
        verdicts = {expected for expected, _label, _cmd in GUARD_CASES}
        self.assertEqual(verdicts, {True, False})

    def test_both_copies_carry_the_flag_name(self):
        for name, path in GUARD_PATHS.items():
            with self.subTest(plugin=name):
                self.assertIn(
                    '_LITELLM_FLAG_NAME = "--litellm"',
                    path.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
