"""Tests for task0001 (large-diff-review-coverage): Codex reviewer timeout and
non-JSON skip handling in em-workflow and em-review.

Covers the task0001 Acceptance Criteria
(feature-docs/large-diff-review-coverage/tasks/task0001.md):

- AC-1 (FR1): in both codex-reviewer agents, the first rule of Step 6 checks
  wrapper exit code 124 before any JSON parse, returns exactly the timeout
  skip object, decides on the exit code only, and discards partial findings.
- AC-2 (FR2): in both agents, output that fails to parse and matches neither
  the rate-limit nor the unsupported-model rule returns exactly the non-JSON
  skip object; the old non-JSON object with `skipped` false appears nowhere.
- AC-3: the rate-limit and unsupported-model rules keep their objects
  byte-identical and sit after the exit-124 rule and the parse rule.
- AC-4 (FR10): em-workflow's review-protocol.md names the timeout and
  non-JSON cases under `harness_unavailable`, lists four retryable values
  including `review_data_too_large`, and keeps `scratchpad_unavailable`
  non-retryable.
- AC-5 (FR17): em-review's review-protocol.md names the timeout and non-JSON
  cases under `harness_unavailable`, keeps exactly three retryable values with
  `review_data_too_large` non-retryable, and no em-review file mentions shards
  or a dispatch cap.
- AC-7: this module checks AC-1 to AC-5 on the real files, including the
  order inside Step 6, and its matchers reject forged texts (parse-first
  order, the old non-JSON object, a three-value em-workflow retryable set).

All checks are text inspection over whitespace-normalized text. Order checks
compare positions inside the Step 6 section, which runs from the Step 6
heading to the end of the file.
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

STEP6_HEADING = "## Step 6: Parse and return"
SKIP_SEMANTICS_HEADING = "## Skip Semantics"

# The skip objects of Step 6, exactly as returned.
TIMEOUT_OBJECT = (
    '{"findings": [], "summary": "skipped: codex timed out", "skipped": true, '
    '"skip_reason": "harness_unavailable", "source": "codex"}'
)
NON_JSON_OBJECT = (
    '{"findings": [], "summary": "skipped: codex returned non-JSON output", '
    '"skipped": true, "skip_reason": "harness_unavailable", "source": "codex"}'
)
RATE_LIMIT_OBJECT = (
    '{"findings": [], "summary": "skipped: codex rate limited", "skipped": true, '
    '"skip_reason": "rate_limited", "source": "codex"}'
)
MODEL_UNSUPPORTED_OBJECT = (
    '{"findings": [], "summary": "skipped: codex model unsupported", '
    '"skipped": true, "skip_reason": "harness_unavailable", "source": "codex"}'
)
# The object the non-JSON rule returned before this task: a clean-looking
# result with `skipped` false.
OLD_NON_JSON_OBJECT = (
    '{"findings": [], "summary": "codex returned non-JSON output", '
    '"skipped": false, "skip_reason": null, "source": "codex"}'
)

# Anchor of the parse rule, the second rule of Step 6.
PARSE_ANCHOR = "parse Codex's JSON"

# Key terms the first rule of Step 6 must carry (AC-1).
FIRST_RULE_PHRASES = (
    "exit code 124",
    "before any JSON parse",
    "never from the output text",
    "discard",
    "partial findings",
    "valid JSON",
)

RETRYABLE_STATEMENT_RE = re.compile(
    r"These (\w+) `skip_reason` values are the \*\*retryable\*\* set"
)
SKIP_REASON_RE = re.compile(r'skip_reason"?:\s*"([a-z_]+)"')

EM_WORKFLOW_RETRYABLE = {
    "harness_unavailable",
    "rate_limited",
    "budget_exhausted",
    "review_data_too_large",
}
EM_REVIEW_RETRYABLE = {"harness_unavailable", "rate_limited", "budget_exhausted"}


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def _step6_section(text):
    """The Step 6 section: from its heading to the end of the file."""
    if STEP6_HEADING not in text:
        raise AssertionError(f"missing heading {STEP6_HEADING!r}")
    return text[text.index(STEP6_HEADING) :]


def _skip_semantics_section(text):
    """The Skip Semantics section: from its heading to the next `## `
    heading or the end of the file."""
    if SKIP_SEMANTICS_HEADING not in text:
        raise AssertionError(f"missing heading {SKIP_SEMANTICS_HEADING!r}")
    start = text.index(SKIP_SEMANTICS_HEADING)
    following = re.search(r"^## ", text[start + len(SKIP_SEMANTICS_HEADING) :], re.M)
    if following is None:
        return text[start:]
    return text[start : start + len(SKIP_SEMANTICS_HEADING) + following.start()]


def _top_level_bullets(section):
    """Whitespace-normalized top-level bullets; indented and blank lines after
    a bullet belong to it."""
    bullets = []
    for line in section.splitlines():
        if line.startswith("- "):
            bullets.append([line])
        elif bullets:
            bullets[-1].append(line)
    return [_normalize("\n".join(lines)) for lines in bullets]


# ---------------------------------------------------------------------------
# Step 6 matchers (AC-1, AC-2, AC-3)
# ---------------------------------------------------------------------------


def _position(step6_normalized, needle, label):
    if step6_normalized.count(needle) != 1:
        raise AssertionError(
            f"{label}: expected exactly one occurrence in Step 6, found "
            f"{step6_normalized.count(needle)}"
        )
    return step6_normalized.index(needle)


def assert_exit_124_rule_first(text, label):
    """AC-1: the first rule of Step 6 checks wrapper exit code 124 before any
    JSON parse and returns exactly the timeout skip object."""
    first = _top_level_bullets(_step6_section(text))[0]
    if TIMEOUT_OBJECT not in first:
        raise AssertionError(
            f"{label}: the first rule of Step 6 does not return exactly the "
            "timeout skip object"
        )
    for phrase in FIRST_RULE_PHRASES:
        if phrase not in first:
            raise AssertionError(
                f"{label}: the first rule of Step 6 does not state {phrase!r}"
            )


def assert_exit_124_precedes_parse(text, label):
    """AC-1: within Step 6 the timeout object comes before the parse rule."""
    step6 = _normalize(_step6_section(text))
    timeout_at = _position(step6, TIMEOUT_OBJECT, f"{label} timeout object")
    parse_at = _position(step6, PARSE_ANCHOR, f"{label} parse rule")
    if timeout_at > parse_at:
        raise AssertionError(
            f"{label}: the parse rule comes before the exit-124 rule in Step 6"
        )


def assert_non_json_rule(text, label):
    """AC-2: the non-JSON rule returns exactly the non-JSON skip object, only
    after a failed parse that matched neither the rate-limit nor the
    unsupported-model rule; the old object appears nowhere."""
    normalized = _normalize(text)
    if OLD_NON_JSON_OBJECT in normalized:
        raise AssertionError(f"{label}: the old non-JSON object is still present")
    if re.search(r'\{[^{}]*non-JSON[^{}]*"skipped": false[^{}]*\}', normalized):
        raise AssertionError(
            f"{label}: an object with non-JSON output and `skipped` false remains"
        )
    step6 = _normalize(_step6_section(text))
    non_json_at = _position(step6, NON_JSON_OBJECT, f"{label} non-JSON object")
    rate_at = _position(step6, RATE_LIMIT_OBJECT, f"{label} rate-limit object")
    model_at = _position(
        step6, MODEL_UNSUPPORTED_OBJECT, f"{label} unsupported-model object"
    )
    if non_json_at < rate_at or non_json_at < model_at:
        raise AssertionError(
            f"{label}: the non-JSON rule comes before the rate-limit or "
            "unsupported-model rule"
        )
    bullet = next(
        b for b in _top_level_bullets(_step6_section(text)) if NON_JSON_OBJECT in b
    )
    for phrase in ("parse fails", "neither"):
        if phrase not in bullet:
            raise AssertionError(
                f"{label}: the non-JSON rule does not state {phrase!r}"
            )


def assert_rate_limit_and_model_rules_after_parse(text, label):
    """AC-3: both rules keep their objects and apply only after the exit-124
    rule and a failed parse."""
    step6 = _normalize(_step6_section(text))
    timeout_at = _position(step6, TIMEOUT_OBJECT, f"{label} timeout object")
    parse_at = _position(step6, PARSE_ANCHOR, f"{label} parse rule")
    rate_at = _position(step6, RATE_LIMIT_OBJECT, f"{label} rate-limit object")
    model_at = _position(
        step6, MODEL_UNSUPPORTED_OBJECT, f"{label} unsupported-model object"
    )
    if not (timeout_at < parse_at < rate_at and parse_at < model_at):
        raise AssertionError(
            f"{label}: the rate-limit and unsupported-model rules do not both "
            "follow the exit-124 rule and the parse rule"
        )
    bullets = _top_level_bullets(_step6_section(text))
    rate_bullet = next(b for b in bullets if RATE_LIMIT_OBJECT in b)
    model_bullet = next(b for b in bullets if MODEL_UNSUPPORTED_OBJECT in b)
    if not rate_bullet.startswith("- Only when the parse fails:"):
        raise AssertionError(
            f"{label}: the rate-limit rule is not limited to a failed parse"
        )
    if not model_bullet.startswith("- Only when the parse fails, `model` was supplied"):
        raise AssertionError(
            f"{label}: the unsupported-model rule is not limited to a failed parse"
        )
    if "other than 124" not in model_bullet:
        raise AssertionError(
            f"{label}: the unsupported-model rule does not exclude exit code 124"
        )


# ---------------------------------------------------------------------------
# Skip Semantics matchers (AC-4, AC-5)
# ---------------------------------------------------------------------------


def _harness_unavailable_bullet(bullets):
    return next(
        (b for b in bullets if '"skip_reason": "harness_unavailable"' in b), None
    )


def assert_harness_unavailable_names_timeout_and_non_json(text, label):
    """AC-4 / AC-5: the `harness_unavailable` bullet names the Codex timeout
    (wrapper exit code 124) and Codex output that is not parseable JSON."""
    bullets = _top_level_bullets(_skip_semantics_section(text))
    bullet = _harness_unavailable_bullet(bullets)
    if bullet is None:
        raise AssertionError(f"{label}: no `harness_unavailable` bullet")
    for phrase in ("timeout", "exit code 124", "not parseable JSON"):
        if phrase not in bullet:
            raise AssertionError(
                f"{label}: the `harness_unavailable` bullet does not name {phrase!r}"
            )


def _retryable_group(bullets):
    """(statement count word, set of skip_reason values from the
    `harness_unavailable` bullet through the bullet holding the retryable-set
    statement, index of that bullet)."""
    start = next(
        (i for i, b in enumerate(bullets) if '"skip_reason": "harness_unavailable"' in b),
        None,
    )
    end = next((i for i, b in enumerate(bullets) if RETRYABLE_STATEMENT_RE.search(b)), None)
    if start is None or end is None or end < start:
        raise AssertionError("retryable-set statement not found after the first harness bullet")
    word = RETRYABLE_STATEMENT_RE.search(bullets[end]).group(1)
    values = set()
    for bullet in bullets[start : end + 1]:
        values.update(SKIP_REASON_RE.findall(bullet))
    return word, values, end


def _assert_retryable_set(text, label, expected, count_word):
    bullets = _top_level_bullets(_skip_semantics_section(text))
    word, values, end = _retryable_group(bullets)
    if word != count_word:
        raise AssertionError(
            f"{label}: the retryable-set statement says {word!r} values, "
            f"expected {count_word!r}"
        )
    if values != expected:
        raise AssertionError(
            f"{label}: the retryable values are {sorted(values)}, "
            f"expected {sorted(expected)}"
        )
    statement_bullet = bullets[end]
    if "walks the perspective's fallback chain on exactly these strings" not in (
        statement_bullet
    ):
        raise AssertionError(
            f"{label}: the retryable-set statement lost the chain-walk sentence"
        )
    return bullets, end


def assert_em_workflow_retryable_set(text, label):
    """AC-4: four retryable values including `review_data_too_large`;
    `scratchpad_unavailable` stays non-retryable."""
    bullets, end = _assert_retryable_set(
        text, label, EM_WORKFLOW_RETRYABLE, "four"
    )
    after = " ".join(bullets[end + 1 :])
    if "`scratchpad_unavailable`, like every value outside the four above, is NOT retryable" not in after:
        raise AssertionError(
            f"{label}: `scratchpad_unavailable` is not stated non-retryable "
            "against the four-value set"
        )
    if "review_data_too_large" in after:
        raise AssertionError(
            f"{label}: `review_data_too_large` appears after the retryable-set "
            "statement"
        )


def assert_em_review_retryable_set(text, label):
    """AC-5: exactly three retryable values; `scratchpad_unavailable` and
    `review_data_too_large` stay non-retryable."""
    bullets, end = _assert_retryable_set(text, label, EM_REVIEW_RETRYABLE, "three")
    after = " ".join(bullets[end + 1 :])
    if "These last two are NOT retryable, like every value outside the three above" not in after:
        raise AssertionError(
            f"{label}: the non-retryable statement for the last two values is missing"
        )
    for value in ("scratchpad_unavailable", "review_data_too_large"):
        if f'skip_reason: "{value}"' not in after:
            raise AssertionError(
                f"{label}: {value} is not listed after the retryable-set statement"
            )


SHARD_TERMS_RE = re.compile(r"shard|dispatch[\s-]+cap", re.I)


def find_shard_terms(text):
    """Mentions of shards or a dispatch cap in `text`."""
    return SHARD_TERMS_RE.findall(text)


def _em_review_text_files():
    root = REPO_ROOT / "em-review"
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


# ---------------------------------------------------------------------------
# Real files
# ---------------------------------------------------------------------------


class TestStep6ExitCode124Rule(unittest.TestCase):
    """AC-1 on both codex-reviewer agents."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {plugin: _read(path) for plugin, path in AGENT_PATHS.items()}

    def test_ac1_first_rule_returns_timeout_object_on_exit_124(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                assert_exit_124_rule_first(text, f"AC-1 {plugin}")

    def test_ac1_exit_124_rule_precedes_the_parse_rule(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                assert_exit_124_precedes_parse(text, f"AC-1 {plugin}")


class TestStep6NonJsonRule(unittest.TestCase):
    """AC-2 on both codex-reviewer agents."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {plugin: _read(path) for plugin, path in AGENT_PATHS.items()}

    def test_ac2_non_json_returns_skip_object_and_old_object_is_gone(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                assert_non_json_rule(text, f"AC-2 {plugin}")


class TestStep6RateLimitAndModelRules(unittest.TestCase):
    """AC-3 on both codex-reviewer agents."""

    @classmethod
    def setUpClass(cls):
        cls.texts = {plugin: _read(path) for plugin, path in AGENT_PATHS.items()}

    def test_ac3_rules_keep_objects_and_follow_exit_124_and_parse(self):
        for plugin, text in self.texts.items():
            with self.subTest(plugin=plugin):
                assert_rate_limit_and_model_rules_after_parse(text, f"AC-3 {plugin}")

    def test_step6_text_is_identical_in_both_agents(self):
        step6 = {
            plugin: _normalize(_step6_section(text))
            for plugin, text in self.texts.items()
        }
        self.assertEqual(step6["em-workflow"], step6["em-review"])


class TestEmWorkflowProtocolSkipSemantics(unittest.TestCase):
    """AC-4 on em-workflow's review-protocol.md."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PROTOCOL_PATHS["em-workflow"])

    def test_ac4_harness_unavailable_names_timeout_and_non_json(self):
        assert_harness_unavailable_names_timeout_and_non_json(
            self.text, "AC-4 em-workflow"
        )

    def test_ac4_four_retryable_values_with_scratchpad_non_retryable(self):
        assert_em_workflow_retryable_set(self.text, "AC-4 em-workflow")


class TestEmReviewProtocolSkipSemantics(unittest.TestCase):
    """AC-5 on em-review's review-protocol.md and the em-review file set."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PROTOCOL_PATHS["em-review"])

    def test_ac5_harness_unavailable_names_timeout_and_non_json(self):
        assert_harness_unavailable_names_timeout_and_non_json(
            self.text, "AC-5 em-review"
        )

    def test_ac5_three_retryable_values_with_review_data_too_large_non_retryable(self):
        assert_em_review_retryable_set(self.text, "AC-5 em-review")

    def test_ac5_no_em_review_file_mentions_shards_or_a_dispatch_cap(self):
        files = _em_review_text_files()
        self.assertTrue(files, "no em-review files found")
        for path in files:
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                text = path.read_text(encoding="utf-8", errors="replace")
                self.assertEqual([], find_shard_terms(text))


# ---------------------------------------------------------------------------
# Negative proofs: each matcher rejects the forged text it claims to guard
# against (AC-7).
# ---------------------------------------------------------------------------


def _assert_rejects(matcher, real, forged, label):
    """Negative proof: `matcher` accepts the real text, `forged` differs from
    it, and `matcher` rejects `forged`. Accepting the real text first keeps
    the proof from passing for an unrelated reason."""
    matcher(real, f"{label}: real text")
    if forged == real:
        raise AssertionError(f"{label}: the forgery did not change the text")
    try:
        matcher(forged, label)
    except AssertionError:
        return
    raise AssertionError(f"{label}: the matcher accepted the forged text")


def _replace_flexible(text, phrase, replacement):
    """Replace `phrase` wherever it appears, whatever line wrapping splits it."""
    pattern = r"\s+".join(re.escape(word) for word in phrase.split())
    return re.sub(pattern, lambda _match: replacement, text)


def _step6_bullet_line_ranges(text):
    """(head, lines of Step 6, [start index of each top-level bullet])."""
    start = text.index(STEP6_HEADING)
    lines = text[start:].splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith("- ")]
    return text[:start], lines, starts


def _swap_first_two_step6_bullets(text):
    """A forged agent text whose Step 6 puts the parse rule before the
    exit-124 rule."""
    head, lines, starts = _step6_bullet_line_ranges(text)
    first, second, third = starts[0], starts[1], starts[2]
    swapped = lines[:first] + lines[second:third] + lines[first:second] + lines[third:]
    return head + "".join(swapped)


def _move_timeout_rule_last(text):
    """A forged agent text whose exit-124 rule is the last rule of Step 6."""
    head, lines, starts = _step6_bullet_line_ranges(text)
    first, second = starts[0], starts[1]
    return head + "".join(lines[:first] + lines[second:] + lines[first:second])


class TestMatchersRejectForgedTexts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agents = {plugin: _read(path) for plugin, path in AGENT_PATHS.items()}
        cls.protocols = {
            plugin: _read(path) for plugin, path in PROTOCOL_PATHS.items()
        }

    def test_parse_first_order_is_rejected(self):
        for plugin, text in self.agents.items():
            with self.subTest(plugin=plugin):
                forged = _swap_first_two_step6_bullets(text)
                for matcher in (
                    assert_exit_124_rule_first,
                    assert_exit_124_precedes_parse,
                    assert_rate_limit_and_model_rules_after_parse,
                ):
                    _assert_rejects(matcher, text, forged, "forged parse-first")

    def test_exit_124_rule_placed_last_is_rejected(self):
        for plugin, text in self.agents.items():
            with self.subTest(plugin=plugin):
                forged = _move_timeout_rule_last(text)
                for matcher in (
                    assert_exit_124_rule_first,
                    assert_exit_124_precedes_parse,
                    assert_rate_limit_and_model_rules_after_parse,
                ):
                    _assert_rejects(matcher, text, forged, "forged timeout-last")

    def test_exit_124_rule_that_reads_output_text_is_rejected(self):
        for plugin, text in self.agents.items():
            with self.subTest(plugin=plugin):
                forged = _replace_flexible(
                    text, "never from the output text", "from any text"
                )
                _assert_rejects(
                    assert_exit_124_rule_first, text, forged, "forged output-text"
                )

    def test_exit_124_rule_that_keeps_partial_findings_is_rejected(self):
        for plugin, text in self.agents.items():
            with self.subTest(plugin=plugin):
                forged = _replace_flexible(text, "partial findings", "findings")
                _assert_rejects(
                    assert_exit_124_rule_first, text, forged, "forged partial findings"
                )

    def test_timeout_object_that_is_not_a_skip_is_rejected(self):
        for plugin, text in self.agents.items():
            with self.subTest(plugin=plugin):
                forged = text.replace(
                    TIMEOUT_OBJECT,
                    TIMEOUT_OBJECT.replace('"skipped": true', '"skipped": false'),
                )
                _assert_rejects(
                    assert_exit_124_rule_first, text, forged, "forged timeout object"
                )

    def test_old_non_json_object_is_rejected(self):
        for plugin, text in self.agents.items():
            with self.subTest(plugin=plugin):
                replaced = text.replace(NON_JSON_OBJECT, OLD_NON_JSON_OBJECT)
                _assert_rejects(
                    assert_non_json_rule, text, replaced, "forged old object replaces new"
                )
                both = text.replace(
                    NON_JSON_OBJECT, NON_JSON_OBJECT + "\n  " + OLD_NON_JSON_OBJECT
                )
                _assert_rejects(
                    assert_non_json_rule, text, both, "forged old object alongside new"
                )

    def test_rate_limit_rule_not_limited_to_a_failed_parse_is_rejected(self):
        for plugin, text in self.agents.items():
            with self.subTest(plugin=plugin):
                forged = _replace_flexible(
                    text, "- Only when the parse fails: check", "- Check"
                )
                _assert_rejects(
                    assert_rate_limit_and_model_rules_after_parse,
                    text,
                    forged,
                    "forged rate-limit rule",
                )

    def test_three_value_em_workflow_retryable_set_is_rejected(self):
        real = self.protocols["em-workflow"]
        # The em-review protocol is a real three-value text.
        _assert_rejects(
            assert_em_workflow_retryable_set,
            real,
            self.protocols["em-review"],
            "forged three-value set (em-review text)",
        )
        forged_count = _replace_flexible(
            real,
            "These four `skip_reason` values",
            "These three `skip_reason` values",
        )
        _assert_rejects(
            assert_em_workflow_retryable_set, real, forged_count, "forged count word"
        )
        forged_values = _replace_flexible(
            real,
            '`skip_reason: "review_data_too_large"`',
            '`skip_reason: "other_reason"`',
        )
        _assert_rejects(
            assert_em_workflow_retryable_set,
            real,
            forged_values,
            "forged value set without review_data_too_large",
        )

    def test_four_value_em_review_retryable_set_is_rejected(self):
        _assert_rejects(
            assert_em_review_retryable_set,
            self.protocols["em-review"],
            self.protocols["em-workflow"],
            "forged four-value set (em-workflow text)",
        )

    def test_protocol_without_timeout_and_non_json_cases_is_rejected(self):
        for plugin, text in self.protocols.items():
            with self.subTest(plugin=plugin):
                forged = _replace_flexible(text, "not parseable JSON", "unusable")
                _assert_rejects(
                    assert_harness_unavailable_names_timeout_and_non_json,
                    text,
                    forged,
                    "forged missing non-JSON case",
                )

    def test_shard_and_dispatch_cap_mentions_are_found(self):
        self.assertTrue(find_shard_terms("the diff is split into shards"))
        self.assertTrue(find_shard_terms("a Dispatch cap of 24"))
        self.assertTrue(find_shard_terms("a dispatch-cap per pass"))
        self.assertEqual([], find_shard_terms("no such mention here"))


if __name__ == "__main__":
    unittest.main()
