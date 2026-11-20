"""Tests for task0003 (review-perspective-model-effort): the codex-reviewer
agents pass an orchestrator-supplied `effort` to the wrapper, and both review
protocols list `effort` among the reviewer inputs.

Covers task0003 Acceptance Criteria
(feature-docs/review-perspective-model-effort/tasks/task0003.md):

- AC-1: in both `codex-reviewer.md` files, Step 5 states that a supplied
  `effort` is added as `--effort "<effort>"` right before `"$PROMPT"`,
  verbatim; that no `--effort` is added without it; that the reviewer never
  chooses an effort; and that a rejected effort falls under the existing
  Step 6 non-JSON rule (`harness_unavailable`). The new paragraph is
  identical in the two files.
- AC-2: the fenced Step 5 wrapper lines are unchanged. The byte pins live in
  `tests/test_codex_reviewer_temp_file_isolation.py`,
  `tests/test_codex_wrapper_timeout_alignment.py` and
  `tests/test_codex_reviewer_interactive_guidance.py` and are not edited by
  this task; this module adds the check that no fenced Step 5 block carries
  `--effort` (the effort is described in prose, like `model`).
- AC-3: in both `review-protocol.md` files, the Inputs section has an
  `effort` item directly after the `model` item: codex reviewer only, only
  when the registry entry names `effort`, passed as `--effort <effort>`
  verbatim, readonly default xhigh when absent, never received by the Claude
  reviewer or the litellm-harness reviewer.
- AC-4: the two pinned-digest modules carry a "Refreshed by" comment naming
  this task (the digests themselves are verified by those modules).
- AC-5: this module asserts AC-1 and AC-3 for both plugins with
  whitespace-normalized phrase checks scoped to Step 5 and to the Inputs
  section, and every matcher has a negative proof on forged text.

Per tdd-testing's "search existing tests before declaring none exist": the
test directory was searched by both path and basename for
`codex-reviewer.md` and `review-protocol.md`. The modules that read them are
`tests/test_reviewer_roles_protocol.py`,
`tests/test_reproduction_reviewer_instructions.py`,
`tests/test_codex_reviewer_temp_file_isolation.py`,
`tests/test_codex_wrapper_timeout_alignment.py` and
`tests/test_codex_reviewer_interactive_guidance.py`. They pin byte ranges and
the wrapper line; none asserts the `effort` statements, so no existing test
covers AC-1, AC-3 or AC-5.

Conventions follow tests/test_reviewer_roles_protocol.py: files are located
relative to this module, sections are extracted by literal headings, and
phrase checks are whitespace-normalized. Standard library only (NFR4).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGINS = ("em-workflow", "em-review")

AGENT_PATHS = {
    plugin: REPO_ROOT / plugin / "agents" / "codex-reviewer.md" for plugin in PLUGINS
}
PROTOCOL_PATHS = {
    plugin: REPO_ROOT / plugin / "references" / "review-protocol.md"
    for plugin in PLUGINS
}

STEP5_HEADING = "## Step 5: Execute Codex"
STEP6_HEADING = "## Step 6: Parse and return"
INPUTS_HEADING = "## Inputs (all reviewers)"
INPUTS_END_HEADING = "## Step 0 Fail-Closed Resolution"

MODEL_ITEM_START = "- `model`"
EFFORT_ITEM_START = "- `effort`"
REVIEW_MODE_ITEM_START = "- `review_mode`"

WRAPPER_INVOCATION_LINE = (
    '"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly -C '
    '"{project_root}" --output-schema "$SCHEMA" "$PROMPT"'
)

# AC-1: what the Step 5 effort paragraph must say, whitespace-normalized.
STEP5_EFFORT_PHRASES = [
    'When the orchestrator supplies `effort`, add `--effort "<effort>"` right '
    'before `"$PROMPT"`, with the value passed verbatim.',
    'When both `model` and `effort` are supplied, `-m "<model>"` and '
    '`--effort "<effort>"` both come before `"$PROMPT"`.',
    "Without `effort`, add no `--effort`: the wrapper then runs its readonly "
    "default.",
    "Never choose an effort yourself.",
    "When Codex rejects the effort, the Step 6 non-JSON rule applies and the "
    "run skips with `harness_unavailable`.",
]

# AC-3: what the Inputs effort item must say, whitespace-normalized.
INPUTS_EFFORT_PHRASES = [
    "codex reviewer only",
    "only when the registry entry names `effort`",
    "Passed to the wrapper as `--effort <effort>`, verbatim.",
    "Absent → readonly runs at xhigh.",
    "The Claude reviewer and the litellm-harness reviewer never receive it.",
]


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapse whitespace runs (markdown's ~79-column wraps included) to a
    single space and strip the ends."""
    return re.sub(r"\s+", " ", text).strip()


def _extract(text, start_marker, end_marker, label):
    """Return text[start_marker:end_marker) (end_marker None = end of text),
    raising AssertionError naming `label` when an anchor is missing."""
    if start_marker not in text:
        raise AssertionError(f"{label}: missing start marker {start_marker!r}")
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    if end_marker not in text[start:]:
        raise AssertionError(f"{label}: missing end marker {end_marker!r}")
    return text[start : text.index(end_marker, start)]


def _assert_phrases_present(normalized_text, phrases, label):
    missing = [p for p in phrases if p not in normalized_text]
    if missing:
        raise AssertionError(f"{label}: missing phrase(s) {missing!r}")


# ---------------------------------------------------------------------------
# Step 5 side (AC-1, AC-2)
# ---------------------------------------------------------------------------


def _step5(text, label):
    return _extract(text, STEP5_HEADING, STEP6_HEADING, f"{label} Step 5 section")


def _split_outside_fences(section):
    """Split a section into (prose_paragraphs, fenced_blocks). A paragraph is
    a run of non-blank lines outside a ``` fence; a fenced block is the text
    between a pair of ``` lines."""
    paragraphs, fences = [], []
    current, fence = [], None
    for line in section.splitlines():
        if line.startswith("```"):
            if fence is None:
                if current:
                    paragraphs.append("\n".join(current))
                    current = []
                fence = []
            else:
                fences.append("\n".join(fence))
                fence = None
            continue
        if fence is not None:
            fence.append(line)
        elif line.strip() == "":
            if current:
                paragraphs.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs, fences


def _effort_paragraph(text, label):
    """The one Step 5 prose paragraph that carries the effort statement,
    required to sit directly after the `model` paragraph."""
    paragraphs, _ = _split_outside_fences(_step5(text, label))
    model_at = [i for i, p in enumerate(paragraphs) if p.startswith("When the orchestrator supplies `model`")]
    if len(model_at) != 1:
        raise AssertionError(
            f"{label}: expected exactly one Step 5 `model` paragraph, "
            f"found {len(model_at)}"
        )
    effort_at = [i for i, p in enumerate(paragraphs) if "--effort" in p]
    if len(effort_at) != 1:
        raise AssertionError(
            f"{label}: expected exactly one Step 5 prose paragraph naming "
            f"`--effort`, found {len(effort_at)}"
        )
    if effort_at[0] != model_at[0] + 1:
        raise AssertionError(
            f"{label}: the effort paragraph does not directly follow the "
            "`model` paragraph"
        )
    return paragraphs[effort_at[0]]


def _assert_step5_effort_statements(text, label):
    _assert_phrases_present(
        _normalize(_effort_paragraph(text, label)), STEP5_EFFORT_PHRASES, label
    )


def _assert_no_effort_in_fenced_step5_blocks(text, label):
    _, fences = _split_outside_fences(_step5(text, label))
    if not fences:
        raise AssertionError(f"{label}: Step 5 has no fenced block")
    for block in fences:
        if "--effort" in block:
            raise AssertionError(
                f"{label}: a fenced Step 5 block carries `--effort`; the "
                "effort is described in prose only"
            )
        if WRAPPER_INVOCATION_LINE not in block:
            raise AssertionError(
                f"{label}: a fenced Step 5 block lost the pinned wrapper line"
            )


# ---------------------------------------------------------------------------
# Inputs side (AC-3)
# ---------------------------------------------------------------------------


def _inputs_section(text, label):
    return _extract(text, INPUTS_HEADING, INPUTS_END_HEADING, f"{label} Inputs")


def _effort_item(text, label):
    """The Inputs `effort` item: from its bullet through the line before the
    next top-level bullet. It must exist once and sit between the `model`
    item and the `review_mode` item."""
    inputs = _inputs_section(text, label)
    if inputs.count(EFFORT_ITEM_START) != 1:
        raise AssertionError(
            f"{label}: expected exactly one Inputs item starting "
            f"{EFFORT_ITEM_START!r}, found {inputs.count(EFFORT_ITEM_START)}"
        )
    model_at = inputs.index(MODEL_ITEM_START)
    effort_at = inputs.index(EFFORT_ITEM_START)
    review_mode_at = inputs.index(REVIEW_MODE_ITEM_START)
    if not model_at < effort_at < review_mode_at:
        raise AssertionError(
            f"{label}: the `effort` item must sit directly after the "
            "`model` item and before `review_mode`"
        )
    return inputs[effort_at:review_mode_at]


def _assert_effort_item_statements(text, label):
    item = _normalize(_effort_item(text, label))
    _assert_phrases_present(item, INPUTS_EFFORT_PHRASES, label)
    # Every sentence that mentions the litellm reviewer must say "never":
    # an item that hands `effort` to the litellm-harness reviewer fails here
    # even when the required phrases above are all present elsewhere.
    for sentence in re.split(r"(?<=[.;])\s+", item):
        if "litellm" in sentence and "never" not in sentence:
            raise AssertionError(
                f"{label}: a sentence mentions the litellm reviewer without "
                f"'never': {sentence!r}"
            )


class TestStep5EffortParagraph(unittest.TestCase):
    """AC-1 and AC-2 on the real codex-reviewer agents."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {plugin: _read(path) for plugin, path in AGENT_PATHS.items()}

    def test_ac1_step5_states_effort_handling(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_step5_effort_statements(text, f"AC-1 {plugin}")

    def test_ac1_effort_paragraph_is_identical_in_both_plugins(self):
        paragraphs = {
            plugin: _normalize(_effort_paragraph(text, f"AC-1 {plugin}"))
            for plugin, text in self.texts.items()
        }
        self.assertEqual(paragraphs["em-workflow"], paragraphs["em-review"])

    def test_ac2_fenced_step5_blocks_carry_no_effort_and_keep_wrapper_line(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_no_effort_in_fenced_step5_blocks(text, f"AC-2 {plugin}")


class TestInputsEffortItem(unittest.TestCase):
    """AC-3 on the real review-protocol documents."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {plugin: _read(path) for plugin, path in PROTOCOL_PATHS.items()}

    def test_ac3_inputs_effort_item_states_scope_value_default_and_exclusions(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                _assert_effort_item_statements(text, f"AC-3 {plugin}")


class TestPinnedDigestModulesCarryRefreshComments(unittest.TestCase):
    """AC-4: the refreshed digests are announced by a "Refreshed by" comment
    naming this task. The digests themselves are verified by the two modules."""

    MARKER = (
        "Refreshed by "
        "feature-docs/review-perspective-model-effort/tasks/task0003.md"
    )

    def test_both_pinned_modules_name_this_task_in_a_refresh_comment(self):
        for name in (
            "test_reviewer_roles_protocol.py",
            "test_reproduction_reviewer_instructions.py",
        ):
            with self.subTest(module=name):
                text = _read(REPO_ROOT / "tests" / name)
                comments = [
                    line for line in text.splitlines() if line.lstrip().startswith("#")
                ]
                joined = _normalize(" ".join(c.lstrip("# ") for c in comments))
                self.assertIn(self.MARKER, joined)


# ---------------------------------------------------------------------------
# Negative proofs (NFR4): each matcher can fail on forged input.
# ---------------------------------------------------------------------------

GOOD_STEP5 = """\
## Step 5: Execute Codex

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly -C "{project_root}" --output-schema "$SCHEMA" "$PROMPT"
```

When the orchestrator supplies `model`, add `-m "<model>"` right before
`"$PROMPT"`, with the value passed verbatim. Without `model`, add no `-m`:
Codex then runs its recommended default model. Never choose a model
yourself.

When the orchestrator supplies `effort`, add `--effort "<effort>"` right
before `"$PROMPT"`, with the value passed verbatim. When both `model` and
`effort` are supplied, `-m "<model>"` and `--effort "<effort>"` both come
before `"$PROMPT"`. Without `effort`, add no `--effort`: the wrapper then
runs its readonly default. Never choose an effort yourself. When Codex
rejects the effort, the Step 6 non-JSON rule applies and the run skips with
`harness_unavailable`.

Assign `$PROMPT` with a quoted heredoc.

```bash
PROMPT=$(cat <<'EOF_1'
...
EOF_1
)
"${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" readonly -C "{project_root}" --output-schema "$SCHEMA" "$PROMPT"
```

## Step 6: Parse and return
"""

GOOD_INPUTS = """\
## Inputs (all reviewers)

- `model` — harness reviewers only; the Claude reviewer never receives it.
  - codex reviewer: present only when the registry entry names a `model`.
- `effort` — codex reviewer only, and only when the registry entry names
  `effort`. Passed to the wrapper as `--effort <effort>`, verbatim. Absent →
  readonly runs at xhigh. The Claude reviewer and the litellm-harness reviewer
  never receive it.
- `review_mode` — `"diff"` or `"whole-codebase"`

## Step 0 Fail-Closed Resolution
"""


class TestMatchersRejectForgedInput(unittest.TestCase):
    """Negative proof: the fixtures above pass, and each forged variant
    fails the matcher it targets."""

    def test_good_step5_fixture_passes(self):
        _assert_step5_effort_statements(GOOD_STEP5, "fixture")
        _assert_no_effort_in_fenced_step5_blocks(GOOD_STEP5, "fixture")

    def test_good_inputs_fixture_passes(self):
        _assert_effort_item_statements(GOOD_INPUTS, "fixture")

    def test_step5_without_the_effort_sentence_fails(self):
        forged = GOOD_STEP5.replace(
            "When the orchestrator supplies `effort`, add `--effort "
            '"<effort>"` right\nbefore `"$PROMPT"`, with the value passed '
            "verbatim. ",
            "",
        )
        self.assertNotEqual(forged, GOOD_STEP5, "the forgery must change the text")
        with self.assertRaises(AssertionError):
            _assert_step5_effort_statements(forged, "forged")

    def test_step5_without_any_effort_paragraph_fails(self):
        start = GOOD_STEP5.index("When the orchestrator supplies `effort`")
        end = GOOD_STEP5.index("Assign `$PROMPT`")
        forged = GOOD_STEP5[:start] + GOOD_STEP5[end:]
        with self.assertRaises(AssertionError):
            _assert_step5_effort_statements(forged, "forged")

    def test_step5_that_lets_the_reviewer_choose_an_effort_fails(self):
        forged = GOOD_STEP5.replace("Never choose an effort yourself.", "")
        self.assertNotEqual(forged, GOOD_STEP5)
        with self.assertRaises(AssertionError):
            _assert_step5_effort_statements(forged, "forged")

    def test_step5_without_the_rejection_rule_fails(self):
        forged = GOOD_STEP5.replace("`harness_unavailable`.", "`rate_limited`.")
        self.assertNotEqual(forged, GOOD_STEP5)
        with self.assertRaises(AssertionError):
            _assert_step5_effort_statements(forged, "forged")

    def test_effort_paragraph_away_from_the_model_paragraph_fails(self):
        start = GOOD_STEP5.index("When the orchestrator supplies `effort`")
        end = GOOD_STEP5.index("Assign `$PROMPT`")
        moved = GOOD_STEP5[:start] + GOOD_STEP5[end:]
        # Re-insert it after the heredoc block, which separates it from `model`.
        moved = moved.replace(
            "## Step 6: Parse and return",
            "Filler paragraph.\n\n"
            + GOOD_STEP5[start:end]
            + "## Step 6: Parse and return",
        )
        with self.assertRaises(AssertionError):
            _effort_paragraph(moved, "forged")

    def test_effort_in_a_fenced_step5_block_fails(self):
        forged = GOOD_STEP5.replace(
            'readonly -C "{project_root}" --output-schema "$SCHEMA" "$PROMPT"\n```\n\n'
            "When the orchestrator supplies `model`",
            'readonly -C "{project_root}" --output-schema "$SCHEMA" '
            '--effort "high" "$PROMPT"\n```\n\n'
            "When the orchestrator supplies `model`",
            1,
        )
        self.assertNotEqual(forged, GOOD_STEP5)
        with self.assertRaises(AssertionError):
            _assert_no_effort_in_fenced_step5_blocks(forged, "forged")

    def test_missing_step5_heading_fails(self):
        with self.assertRaises(AssertionError):
            _effort_paragraph(GOOD_STEP5.replace(STEP5_HEADING, "## Other"), "forged")

    def test_inputs_item_that_hands_effort_to_litellm_fails(self):
        forged = GOOD_INPUTS.replace(
            "The Claude reviewer and the litellm-harness reviewer\n  never receive it.",
            "The Claude reviewer never receives it. The litellm-harness reviewer\n"
            "  receives it as `-m`.",
        )
        self.assertNotEqual(forged, GOOD_INPUTS)
        with self.assertRaises(AssertionError):
            _assert_effort_item_statements(forged, "forged")

    def test_inputs_item_with_extra_litellm_grant_fails_even_with_required_phrases(self):
        forged = GOOD_INPUTS.replace(
            "never receive it.\n",
            "never receive it.\n  litellm-harness reviewer: always present.\n",
        )
        self.assertNotEqual(forged, GOOD_INPUTS)
        with self.assertRaises(AssertionError):
            _assert_effort_item_statements(forged, "forged")

    def test_inputs_item_without_the_xhigh_default_fails(self):
        forged = GOOD_INPUTS.replace("Absent →\n  readonly runs at xhigh. ", "")
        self.assertNotEqual(forged, GOOD_INPUTS)
        with self.assertRaises(AssertionError):
            _assert_effort_item_statements(forged, "forged")

    def test_inputs_without_the_effort_item_fails(self):
        start = GOOD_INPUTS.index("- `effort`")
        end = GOOD_INPUTS.index("- `review_mode`")
        with self.assertRaises(AssertionError):
            _effort_item(GOOD_INPUTS[:start] + GOOD_INPUTS[end:], "forged")

    def test_inputs_effort_item_before_the_model_item_fails(self):
        start = GOOD_INPUTS.index("- `effort`")
        end = GOOD_INPUTS.index("- `review_mode`")
        effort = GOOD_INPUTS[start:end]
        rest = GOOD_INPUTS[:start] + GOOD_INPUTS[end:]
        forged = rest.replace("- `model`", effort + "- `model`", 1)
        with self.assertRaises(AssertionError):
            _effort_item(forged, "forged")


if __name__ == "__main__":
    unittest.main()
