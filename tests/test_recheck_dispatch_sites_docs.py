"""Document tests for self-write-exclusivity-window task0004.

The three dispatch sites (the design step branch of `skills/develop/SKILL.md`,
create-plan section 8 and rework section 10) show the return-time recheck
between their comparison (or the `validate-worker-output.py` validation) and
their recording write, as a citation of Rule R1
(`references/contracts/worker-envelope.md`, "Recomputation and comparison
timing"). They cite the rule and the term; they never restate what the
recheck compares, the membership matrix or the substitution.

Covers task0004's Acceptance Criteria
(feature-docs/self-write-exclusivity-window/tasks/task0004.md):

- AC-1 (FR7, TM-1): the design step branch, step 5.
- AC-2 (FR7, TM-1): create-plan section 8's return-time paragraph.
- AC-3 (FR7, TM-1): rework section 10's "Return-time digest" paragraph.
- AC-4 (FR7): no site restates the recheck's comparison, the membership
  matrix or the substitution.
- AC-5 (FR7, NFR3): each site keeps its pre-change wording and the order
  `scope verification` -> `scripts/self-write-digest.py` -> `Layer 5 recording`
  (rework: -> `step 3 validates`). The existing wiring tests are run
  unchanged by the suite and are not repeated here.
- AC-6 (FR8, NFR1, NFR2): this file (standard library only; heading, list
  item and paragraph slices; whitespace-insensitive token positions; every
  probe paired with a forged-text control).

Method: slice by heading, then by the list item or paragraph that carries
`scripts/self-write-digest.py`; compare the first positions of named tokens
on whitespace-removed text, so a line wrap never matters (Japanese text wraps
without spaces). Never full-document equality and never a line-break
position. Every probe is paired with forged text on which it fires; the
forged pre-change texts below are the sites' wording as it stood before this
task. The tests assert the sites' citation text only; they never assert that
`worker-envelope.md` already contains the recheck (that text lands in another
worktree).

Document tests for rework-recheck-before-patch-write task0001
(feature-docs/rework-recheck-before-patch-write/tasks/task0001.md). In rework
section 10's "Return-time digest" paragraph the return-time recheck sits after
step 3's validation and before step 3's application of the rework patch:

- the order probe (`_application_order_defects`): the recheck follows the
  "step 3 validates" token and the rule-1 compare/stale sentence, and every
  application token (`APPLICATION_TOKENS`) follows the recheck. Its forged
  controls are `BASE_REVISION_RW_RETURN_TIME`, the paragraph as it stood at the
  feature's base (the recheck follows "Step 3 validates and applies"), and the
  real paragraph with the application sentence moved before the recheck;
- the application-sentence probe (`_application_statement_defects`): one
  sentence after the recheck sentence says the patch is applied only after a
  passing recheck and names the workflow.yaml write and the commit;
- the step-numbering probe (`_step_numbering_defects`): section 10's
  review-sourced steps 1-4 keep their numbers and meaning, and the two
  citations of those numbers still exist.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

DEVELOP_SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
CREATE_PLAN_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
REWORK_SYNTHESIS_PATH = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"

SCRIPT_TOKEN = "scripts/self-write-digest.py"
RECHECK_TOKEN = "return-time recheck"
LAYER_5_RECORDING = "Layer 5 recording"
SELF_WRITE_SET = "self_write_set"
ENVELOPE_PATH_TOKEN = "references/contracts/worker-envelope.md"
R1_TOKENS = (ENVELOPE_PATH_TOKEN, "Rule R1", "Recomputation and comparison timing")

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


# ---------------------------------------------------------------------------
# Helpers (document slicing and matchers)
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Whitespace-normalize: any run of whitespace becomes one space."""
    return " ".join(text.split())


def _squash(text):
    """Remove all whitespace, lowercase. Makes token comparison immune to
    where a document wraps a line (Japanese text wraps with no space)."""
    return "".join(text.split()).lower()


def _has(text, token):
    return _squash(token) in _squash(text)


def _pos(text, token):
    """First position of `token` in the squashed text, or -1."""
    return _squash(text).find(_squash(token))


def _headings(text):
    found = []
    in_fence = False
    for idx, line in enumerate(text.splitlines()):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((idx, len(match.group(1)), match.group(2)))
    return found


def _section(text, title, level):
    """The body of the one level-`level` heading titled `title`, up to the
    next heading of the same or a higher level."""
    lines = text.splitlines()
    heads = _headings(text)
    hits = [(i, h) for i, h in enumerate(heads) if h[2] == title and h[1] == level]
    if len(hits) != 1:
        raise AssertionError(
            f"expected exactly one level-{level} heading {title!r}, found {len(hits)}"
        )
    pos, (start, lvl, _title) = hits[0]
    end = len(lines)
    for nxt_line, nxt_lvl, _nxt in heads[pos + 1:]:
        if nxt_lvl <= lvl:
            end = nxt_line
            break
    return "\n".join(lines[start + 1:end])


def _numbered_item(text, number):
    """The list item that starts with `<number>. ` at column 0, up to the next
    unindented non-blank line."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^{number}\.\s", line):
            start = i
            break
    if start is None:
        raise AssertionError(f"no list item numbered {number}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.strip() and not line[0].isspace():
            end = j
            break
    return "\n".join(lines[start:end])


def _paragraphs(text):
    return [b for b in re.split(r"\n\s*\n", text) if b.strip()]


def _paragraph_with(text, token):
    """The blank-line-delimited block that contains `token`."""
    for block in _paragraphs(text):
        if _has(block, token):
            return block
    raise AssertionError(f"no paragraph contains {token!r}")


def _sentences(text):
    """Sentences of the whitespace-normalized text (split on the Japanese
    full stop or on a period followed by a space)."""
    return [s for s in re.split(r"。|(?<=[.!?])\s+", _norm(text)) if s.strip()]


def _sentence_with(text, *tokens):
    """The first sentence that contains every one of `tokens`."""
    for sentence in _sentences(text):
        if all(_has(sentence, t) for t in tokens):
            return sentence
    raise AssertionError(f"no sentence contains all of {tokens!r}")


def _sentence_end(text, *tokens):
    """Position, in the squashed text, just after the first sentence that
    contains every one of `tokens`; -1 when there is no such sentence."""
    flat = _squash(text)
    for sentence in _sentences(text):
        if all(_has(sentence, t) for t in tokens):
            start = flat.find(_squash(sentence))
            return start + len(_squash(sentence)) if start >= 0 else -1
    return -1


# ---------------------------------------------------------------------------
# The sites and the recheck probe
# ---------------------------------------------------------------------------


class _Site:
    """What one dispatch site must show, in tokens.

    `earlier` are the tokens that precede the recheck, in this order;
    `stale_tokens` identify the site's compare/stale sentence, which ends
    before the recheck; `later` are the tokens each of which follows the
    recheck; `mismatch`, `cannot_run` and `actor` are the wording the
    recheck sentence uses at this site (the develop skill is Japanese).
    """

    def __init__(self, label, text, pre_change, earlier, stale_tokens, later,
                 mismatch, cannot_run, actor):
        self.label = label
        self.text = text
        self.pre_change = pre_change
        self.earlier = earlier
        self.stale_tokens = stale_tokens
        self.later = later
        self.mismatch = mismatch
        self.cannot_run = cannot_run
        self.actor = actor


def _recheck_defects(text, site):
    """Everything wrong with the recheck reference in `text`, as a list of
    strings starting with a code: missing / order / citation / stale / actor.
    An empty list means the reference is as the task plan requires."""
    sentences = [s for s in _sentences(text) if _has(s, RECHECK_TOKEN)]
    if not sentences:
        return [f"missing: no sentence names {RECHECK_TOKEN!r}"]
    sentence = sentences[0]
    defects = []
    recheck_pos = _pos(text, RECHECK_TOKEN)

    previous = -1
    for token in site.earlier:
        pos = _pos(text, token)
        if pos < 0:
            defects.append(f"order: {token!r} not found")
        elif pos <= previous:
            defects.append(f"order: {token!r} is out of order")
        elif pos >= recheck_pos:
            defects.append(f"order: {token!r} does not precede the recheck")
        if pos >= 0:
            previous = max(previous, pos)

    stale_end = _sentence_end(text, *site.stale_tokens)
    if stale_end < 0:
        defects.append(f"order: compare/stale sentence {site.stale_tokens!r} not found")
    elif recheck_pos < stale_end:
        defects.append("order: the recheck is inside or before the compare/stale sentence")

    for token in site.later:
        pos = _pos(text, token)
        if pos < 0:
            defects.append(f"order: {token!r} not found")
        elif recheck_pos >= pos:
            defects.append(f"order: the recheck does not precede {token!r}")

    for token in R1_TOKENS:
        if not _has(sentence, token):
            defects.append(f"citation: the recheck sentence lacks {token!r}")

    for token in ("stale", site.mismatch, site.cannot_run):
        if not _has(sentence, token):
            defects.append(f"stale: the recheck sentence lacks {token!r}")

    if not _has(sentence, site.actor):
        defects.append(f"actor: the recheck sentence lacks {site.actor!r}")
    return defects


def _defect_codes(defects):
    return sorted({d.split(":", 1)[0] for d in defects})


def _recheck_sentence(text):
    return _sentence_with(text, RECHECK_TOKEN)


def _without_recheck_sentence(text):
    """`text`, normalized, with the recheck sentence taken out."""
    sentence = _recheck_sentence(text)
    flat = _norm(text)
    if sentence not in flat:
        raise AssertionError("recheck sentence is not a substring of the normalized text")
    return flat.replace(sentence, "", 1)


def _with_recheck_sentence_moved_to_the_end(text):
    sentence = _recheck_sentence(text)
    return _without_recheck_sentence(text) + " " + sentence + "。"


def _with_recheck_sentence_edited(text, old, new):
    sentence = _recheck_sentence(text)
    if old not in sentence:
        raise AssertionError(f"{old!r} is not in the recheck sentence: {sentence!r}")
    return _norm(text).replace(sentence, sentence.replace(old, new), 1)


# Negative probes for "no restatement" (FR7, NFR6). The comparison's values
# (blob id, mode, kind) and `git hash-object` belong to Rule R1; so do the
# membership matrix and the substitution.
COMPARISON_PROBES = (
    re.compile(r"\bblob\b|ブロブ", re.I),
    re.compile(r"\bgit hash-object\b", re.I),
    re.compile(r"\bsymlink\b|シンボリックリンク", re.I),
    re.compile(r"(?:\bmode\b|モード)[^.。]{0,60}(?:\bkind\b|種別)", re.I),
    re.compile(r"(?:\bkind\b|種別)[^.。]{0,60}(?:\bmode\b|モード)", re.I),
)
MATRIX_PROBES = (
    re.compile(r"\bnot a member\b", re.I),
    re.compile(r"\bmember only when\b", re.I),
    re.compile(
        r"`(?:create|replace_own|replace_authorized|extend_only|regenerate|preserve)`"
        r"[^.]{0,80}\b(?:created|modified|deleted)\b",
        re.I,
    ),
)
SUBSTITUTION_PROBES = (
    re.compile(r"\babsent key\b", re.I),
    re.compile(r"\bis absent from\b", re.I),
    re.compile(r"\bholds the dispatch-time (?:value|digest)\b", re.I),
    re.compile(r"dispatch\s*時点?の値に置き換え"),
)
# D2: Layer 5's Calculation runs before the recheck; no site may say it runs
# after it.
_AFTER_THE_RECHECK = re.compile(
    r"\b(?:after|following)\s+the\s+`?return-time recheck\b|再確認の?(?:後|あと)|再確認後",
    re.I,
)


def _restatement_hits(text):
    flat = _norm(text)
    probes = COMPARISON_PROBES + MATRIX_PROBES + SUBSTITUTION_PROBES
    return [p.pattern for p in probes if p.search(flat)]


def _comparison_hits(text):
    flat = _norm(text)
    return [p.pattern for p in COMPARISON_PROBES if p.search(flat)]


def _calculation_after_recheck_hits(text):
    return [
        s for s in _sentences(text)
        if _has(s, "Calculation") and _AFTER_THE_RECHECK.search(s)
    ]


# ---------------------------------------------------------------------------
# Documents, slices and pre-change controls (read once)
# ---------------------------------------------------------------------------

_DEVELOP = _read(DEVELOP_SKILL_PATH)
_CREATE_PLAN = _read(CREATE_PLAN_PATH)
_REWORK = _read(REWORK_SYNTHESIS_PATH)
_REVIEW_PHASE = _read(REVIEW_PHASE_PATH)

DESIGN_BRANCH = _section(_DEVELOP, "design ステップ分岐", 3)
DESIGN_STEP_5 = _numbered_item(DESIGN_BRANCH, 5)

CP_SECTION_3 = _section(_CREATE_PLAN, "3. Reconcile on entry", 2)
CP_SECTION_4 = _section(_CREATE_PLAN, "4. Planner dispatch", 2)
CP_SECTION_8 = _section(_CREATE_PLAN, "8. Validation", 2)
CP_SECTION_9 = _section(
    _CREATE_PLAN,
    "9. Planning invariants — the validator-implemented subset, and human review for the rest",
    2,
)
CP_RETURN_TIME = _paragraph_with(CP_SECTION_8, SCRIPT_TOKEN)

RW_SECTION_10 = _section(_REWORK, "10. Workflow state transition", 2)
RW_RETURN_TIME = _paragraph_with(RW_SECTION_10, SCRIPT_TOKEN)

SITE_SLICES = (
    ("design step branch", DESIGN_BRANCH),
    ("create-plan section 3", CP_SECTION_3),
    ("create-plan section 4", CP_SECTION_4),
    ("create-plan section 8", CP_SECTION_8),
    ("create-plan section 9", CP_SECTION_9),
    ("rework section 10", RW_SECTION_10),
)

# The sites' wording as it stood before this task: forged controls on which
# the recheck probe must fire, and the sentences the task keeps. The rework
# site's text is the paragraph without the recheck sentence and without the
# sentence that says when the patch is applied; its validation sentence follows
# the rewording of rework-recheck-before-patch-write task0001.
PRE_CHANGE_DESIGN_STEP_5 = """5. 完了後、scope verification（layer 4。
   `references/phases/create-spec-phase.md` の「Scope verification」）を行う。
   通ったら、オーケストレーターが現在の digest_source を dispatch 時と同じ
   手順で再計算し、`scripts/self-write-digest.py`（operation
   `identify_and_substitute`）を実行する。実行方法・比較の規則・順序は
   `references/contracts/worker-envelope.md` の Rule R1
   「Recomputation and comparison timing」に従い、ここでは繰り返さない。
   スクリプトが返した digest_source から計算した digest を dispatch 時の
   `input_digest` と比較し、不一致、またはスクリプトの終了コードが `0` 以外なら
   stale として扱う（stale の扱いは、scope verification が定める stale
   handling（`references/phases/create-spec-phase.md`）に従う）。一致したら
   `references/artifact-digest.md` の `Layer 5 recording` に従って、
   `written_artifacts` の各 path の digest を `phase-state/design.yaml`
   （`phase: design`。スキーマは `references/phase-state.md`）の
   `artifacts` に記録する。`tokens.yaml` と `tokens.html` は、
   両方とも書かれたら両方を記録する。`artifacts` の記録と、スクリプトが返した
   `self_write_set` の記録は、同一の phase-state 書き込みで行う
   （`written_artifacts` が空の run では、返却された status を記録する書き込みで
   行う）。そのうえで成果物（DESIGN.md /
   更新された `design-system/` 配下 / mockup）を検証し、design step の
   `status` と `completed_at_commit`（規則 R2）を設定して commit-docs.sh で
   コミットする
   （`payload.design_summary`: decisions_count / open_items / tokens /
   mockups をレポートに反映。batch:
   `${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md` の出力抑制規律により、
   進捗のナラティブと `payload.design_summary` の結果サマリ本文はランニング
   出力に出さない。workflow.yaml への書き込み・commit-docs.sh でのコミット・
   ゲート解決・design step の status 遷移は対話時と変わらない）
"""

PRE_CHANGE_CP_RETURN_TIME = """The return-time order on the planner's result is this one. The orchestrator
completes the scope verification (layer 4), recomputes the current
digest_source from current state exactly as at dispatch, and runs
`scripts/self-write-digest.py` (operation `identify_and_substitute`), as
`references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
comparison timing" states. Then the orchestrator runs
`scripts/validate-worker-output.py` with the substituted digest_source the
script returned as `--digest-source`, so that application rule 1 compares the
substituted digest_source with the dispatch-time `input_digest`. A mismatch,
or a script exit other than `0`, makes the result stale. When the result is
not stale, the orchestrator records layer 5 (`Layer 5 recording`) together
with `self_write_set`, in the same phase-state write.
"""

PRE_CHANGE_RW_RETURN_TIME = """**Return-time digest (steps 2 and 3, all four routes)**: the rework-planner
run's entry in `phase-state/rework.yaml` carries `dispatch_digest_inputs`, the
per-path `digest_inputs` map of the dispatch's digest_source
(`references/phase-state.md` defines the field and when it is written). After
the scope verification (layer 4) of rework-planner's result passes, the
orchestrator recomputes the current digest_source and runs
`scripts/self-write-digest.py` (operation `identify_and_substitute`), as
`references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
comparison timing" states. Step 3 validates the patch against the
digest_source the script returned, by application rules 1-14 of
`references/workflow-patch.md`: rule 1 compares that substituted digest_source
with the dispatch-time `input_digest`, and a mismatch, or a script exit other
than `0`, makes the result stale. The orchestrator records `self_write_set` in
the same phase-state write as the `Layer 5 recording` of `written_artifacts`
into `phase-state/rework.yaml`."""

DESIGN_SITE = _Site(
    label="design step 5",
    text=DESIGN_STEP_5,
    pre_change=PRE_CHANGE_DESIGN_STEP_5,
    earlier=("Scope verification", SCRIPT_TOKEN),
    stale_tokens=("不一致", "終了コード", "stale"),
    later=(LAYER_5_RECORDING, SELF_WRITE_SET),
    mismatch="不一致",
    cannot_run="実行できない",
    actor="オーケストレーター",
)
CREATE_PLAN_SITE = _Site(
    label="create-plan section 8",
    text=CP_RETURN_TIME,
    pre_change=PRE_CHANGE_CP_RETURN_TIME,
    earlier=("scope verification", SCRIPT_TOKEN, "validate-worker-output.py"),
    stale_tokens=("script exit", "stale"),
    later=(LAYER_5_RECORDING, SELF_WRITE_SET),
    mismatch="mismatch",
    cannot_run="cannot run",
    actor="orchestrator",
)
REWORK_SITE = _Site(
    label="rework section 10",
    text=RW_RETURN_TIME,
    pre_change=PRE_CHANGE_RW_RETURN_TIME,
    earlier=("scope verification", SCRIPT_TOKEN, "step 3 validates"),
    stale_tokens=("script exit", "stale"),
    later=(SELF_WRITE_SET, LAYER_5_RECORDING),
    mismatch="mismatch",
    cannot_run="cannot run",
    actor="orchestrator",
)


# ---------------------------------------------------------------------------
# AC-1, AC-2, AC-3 and the site half of AC-5: one set of checks per site
# ---------------------------------------------------------------------------


class _RecheckSiteChecks:
    """The checks every dispatch site shares. Not collected on its own; each
    concrete class below binds `SITE`."""

    SITE = None

    def test_site_names_the_recheck_in_one_sentence(self):
        self.assertTrue(
            [s for s in _sentences(self.SITE.text) if _has(s, RECHECK_TOKEN)],
            f"{self.SITE.label}: no sentence names {RECHECK_TOKEN!r}",
        )

    def test_site_recheck_reference_has_no_defect(self):
        self.assertEqual(_recheck_defects(self.SITE.text, self.SITE), [])

    def test_recheck_follows_the_comparison_and_precedes_the_recording_write(self):
        text = self.SITE.text
        recheck_pos = _pos(text, RECHECK_TOKEN)
        self.assertGreaterEqual(recheck_pos, 0)
        for token in self.SITE.earlier:
            self.assertGreaterEqual(_pos(text, token), 0, f"{token!r} not found")
            self.assertLess(_pos(text, token), recheck_pos, f"{token!r} must precede")
        self.assertGreaterEqual(
            recheck_pos, _sentence_end(text, *self.SITE.stale_tokens),
            "the recheck must come after the compare/stale sentence",
        )
        for token in self.SITE.later:
            self.assertGreaterEqual(_pos(text, token), 0, f"{token!r} not found")
            self.assertLess(recheck_pos, _pos(text, token), f"{token!r} must follow")

    def test_recheck_sentence_cites_rule_r1_with_the_timing_paragraph(self):
        sentence = _recheck_sentence(self.SITE.text)
        for token in R1_TOKENS:
            self.assertTrue(_has(sentence, token), f"R1 citation lacks {token!r}")

    def test_recheck_sentence_makes_a_mismatch_or_a_failed_recheck_stale(self):
        sentence = _recheck_sentence(self.SITE.text)
        for token in ("stale", self.SITE.mismatch, self.SITE.cannot_run):
            self.assertTrue(_has(sentence, token), f"{token!r} missing: {sentence}")

    def test_recheck_sentence_names_the_orchestrator_as_the_actor(self):
        self.assertTrue(_has(_recheck_sentence(self.SITE.text), self.SITE.actor))

    def test_site_keeps_every_pre_change_sentence(self):
        flat = _squash(self.SITE.text)
        for sentence in _sentences(self.SITE.pre_change):
            with self.subTest(sentence=sentence[:60]):
                self.assertIn(_squash(sentence), flat)

    def test_site_never_says_calculation_runs_after_the_recheck(self):
        self.assertEqual(_calculation_after_recheck_hits(self.SITE.text), [])

    # -- forged-text controls: each defect kind makes the probe fire -------

    def test_pre_change_text_makes_the_probe_fire_as_missing(self):
        defects = _recheck_defects(self.SITE.pre_change, self.SITE)
        self.assertEqual(_defect_codes(defects), ["missing"], defects)

    def test_text_without_the_recheck_sentence_makes_the_probe_fire(self):
        forged = _without_recheck_sentence(self.SITE.text)
        self.assertEqual(_defect_codes(_recheck_defects(forged, self.SITE)), ["missing"])

    def test_recheck_moved_after_the_recording_write_makes_the_probe_fire(self):
        forged = _with_recheck_sentence_moved_to_the_end(self.SITE.text)
        defects = _recheck_defects(forged, self.SITE)
        self.assertIn("order", _defect_codes(defects), defects)

    def test_recheck_placed_before_the_script_makes_the_probe_fire(self):
        sentence = _recheck_sentence(self.SITE.text)
        forged = sentence + "。 " + _without_recheck_sentence(self.SITE.text)
        defects = _recheck_defects(forged, self.SITE)
        self.assertIn("order", _defect_codes(defects), defects)

    def test_recheck_sentence_without_the_citation_makes_the_probe_fire(self):
        forged = _with_recheck_sentence_edited(
            self.SITE.text, "worker-envelope.md", "other.md"
        )
        defects = _recheck_defects(forged, self.SITE)
        self.assertIn("citation", _defect_codes(defects), defects)

    def test_recheck_sentence_without_the_stale_statement_makes_the_probe_fire(self):
        for old, new in (
            ("stale", "fresh"),
            (self.SITE.mismatch, "difference"),
            (self.SITE.cannot_run, "is skipped"),
        ):
            with self.subTest(removed=old):
                forged = _with_recheck_sentence_edited(self.SITE.text, old, new)
                defects = _recheck_defects(forged, self.SITE)
                self.assertIn("stale", _defect_codes(defects), defects)

    def test_recheck_sentence_without_the_orchestrator_makes_the_probe_fire(self):
        forged = _with_recheck_sentence_edited(self.SITE.text, self.SITE.actor, "someone")
        defects = _recheck_defects(forged, self.SITE)
        self.assertIn("actor", _defect_codes(defects), defects)

    def test_calculation_after_the_recheck_makes_the_probe_fire(self):
        forged = (
            "The orchestrator runs Layer 5 `Calculation` after the return-time recheck."
        )
        self.assertNotEqual(_calculation_after_recheck_hits(forged), [])
        forged_ja = "Layer 5 の `Calculation` は再確認の後に行う。"
        self.assertNotEqual(_calculation_after_recheck_hits(forged_ja), [])

    def test_calculation_before_the_recheck_keeps_the_probe_quiet(self):
        allowed = (
            "Layer 5 `Calculation` runs before the return-time recheck, "
            "and the recording write follows the recheck."
        )
        self.assertEqual(_calculation_after_recheck_hits(allowed), [])


class TestDesignStep5RecheckReference(_RecheckSiteChecks, unittest.TestCase):
    """AC-1 (FR7, TM-1): develop SKILL.md, design step branch, step 5."""

    SITE = DESIGN_SITE


class TestCreatePlanSection8RecheckReference(_RecheckSiteChecks, unittest.TestCase):
    """AC-2 (FR7, TM-1): create-plan section 8, the return-time paragraph."""

    SITE = CREATE_PLAN_SITE

    def test_order_is_script_then_validator_then_recheck_then_recording(self):
        tokens = (
            SCRIPT_TOKEN, "validate-worker-output.py", RECHECK_TOKEN,
            LAYER_5_RECORDING, SELF_WRITE_SET,
        )
        positions = [_pos(CP_RETURN_TIME, t) for t in tokens]
        self.assertNotIn(-1, positions, positions)
        self.assertEqual(positions, sorted(set(positions)), positions)


class TestReworkSection10RecheckReference(_RecheckSiteChecks, unittest.TestCase):
    """AC-3 (FR7, TM-1): rework section 10, the "Return-time digest" paragraph."""

    SITE = REWORK_SITE

    def test_order_is_script_then_step_3_then_recheck_then_recording(self):
        tokens = (SCRIPT_TOKEN, "step 3 validates", RECHECK_TOKEN)
        positions = [_pos(RW_RETURN_TIME, t) for t in tokens]
        self.assertNotIn(-1, positions, positions)
        self.assertEqual(positions, sorted(set(positions)), positions)
        recheck_pos = positions[-1]
        recording_sentence = _sentence_with(RW_RETURN_TIME, SELF_WRITE_SET, LAYER_5_RECORDING)
        self.assertLess(recheck_pos, _pos(RW_RETURN_TIME, recording_sentence))


# ---------------------------------------------------------------------------
# AC-4: no restatement
# ---------------------------------------------------------------------------


class TestSitesDoNotRestateTheRecheck(unittest.TestCase):
    """AC-4 (FR7): the sites cite the recheck; Rule R1 owns what it compares,
    the membership matrix and the substitution."""

    def test_no_site_slice_restates_the_comparison_matrix_or_substitution(self):
        for label, body in SITE_SLICES:
            with self.subTest(site=label):
                self.assertEqual(_restatement_hits(body), [])

    def test_no_site_slice_names_git_hash_object(self):
        for label, body in SITE_SLICES:
            with self.subTest(site=label):
                self.assertNotIn("git hash-object", _norm(body))

    def test_each_recheck_sentence_stays_clear_of_the_comparison_values(self):
        for site in (DESIGN_SITE, CREATE_PLAN_SITE, REWORK_SITE):
            with self.subTest(site=site.label):
                self.assertEqual(_comparison_hits(_recheck_sentence(site.text)), [])

    def test_pre_change_sites_are_quiet(self):
        for site in (DESIGN_SITE, CREATE_PLAN_SITE, REWORK_SITE):
            with self.subTest(site=site.label):
                self.assertEqual(_restatement_hits(site.pre_change), [])

    def test_enumerating_blob_id_mode_and_kind_makes_the_probe_fire(self):
        forged = (
            "The return-time recheck compares the git blob id, the mode and the "
            "kind of each path with the scope verification's values."
        )
        self.assertNotEqual(_comparison_hits(forged), [])
        forged_ja = "再確認では blob id・mode・種別を scope verification の観測値と比べる。"
        self.assertNotEqual(_comparison_hits(forged_ja), [])

    def test_naming_git_hash_object_makes_the_probe_fire(self):
        forged = "The return-time recheck runs `git hash-object` on each path."
        self.assertNotEqual(_comparison_hits(forged), [])

    def test_forged_site_text_that_restates_the_comparison_makes_the_probe_fire(self):
        restated = (
            " The orchestrator reads the git blob id, mode and kind of each "
            "path again."
        )
        for site in (DESIGN_SITE, CREATE_PLAN_SITE, REWORK_SITE):
            with self.subTest(site=site.label):
                self.assertNotEqual(_restatement_hits(site.text + restated), [])

    def test_forged_matrix_wording_makes_the_probe_fire(self):
        forged = (
            "A path is not a member of the set when its action is `create` and "
            "its change is modified."
        )
        self.assertNotEqual(_restatement_hits(forged), [])
        forged_action_by_kind = "`replace_own` admits a path that was modified."
        self.assertNotEqual(_restatement_hits(forged_action_by_kind), [])

    def test_forged_substitution_wording_makes_the_probe_fire(self):
        forged = "When the path is an absent key of the map it is absent from the digest."
        self.assertNotEqual(_restatement_hits(forged), [])
        forged_ja = "dispatch 時の値に置き換える。"
        self.assertNotEqual(_restatement_hits(forged_ja), [])

    def test_a_citing_sentence_keeps_the_probes_quiet(self):
        citing = (
            "The orchestrator runs the return-time recheck before the recording "
            "phase-state write, as `references/contracts/worker-envelope.md`, "
            'Rule R1, "Recomputation and comparison timing" states.'
        )
        self.assertEqual(_restatement_hits(citing), [])


# ---------------------------------------------------------------------------
# Rework section 10: the recheck sits between step 3's validation and step 3's
# application of the patch (rework-recheck-before-patch-write task0001)
# ---------------------------------------------------------------------------

VALIDATION_TOKEN = "step 3 validates"
# The first mention of the patch application, as one named set: the verb
# wording with which the base revision says step 3 applies the patch, rule 15's
# write to workflow.yaml and rule 16's commits. None of them may match the
# validation wording ("application rule 1", "application rules 1-14"); on the
# squashed text "rules1-14" holds neither "rule15" nor "rule16".
APPLICATION_TOKENS = ("validates and applies", "rule 15", "rule 16")
# The sentence after the recheck that says when the patch is applied.
APPLIED_ONLY_AFTER_TOKENS = (
    "applied only after a passing recheck",
    "stale",
    "workflow.yaml",
    "commit",
)

# The "Return-time digest" paragraph exactly as it stood at this feature's base
# (copied verbatim before the document was edited): the recheck follows "Step 3
# validates and applies". Forged control for the order probe.
BASE_REVISION_RW_RETURN_TIME = """**Return-time digest (steps 2 and 3, all four routes)**: the rework-planner
run's entry in `phase-state/rework.yaml` carries `dispatch_digest_inputs`, the
per-path `digest_inputs` map of the dispatch's digest_source
(`references/phase-state.md` defines the field and when it is written). After
the scope verification (layer 4) of rework-planner's result passes, the
orchestrator recomputes the current digest_source and runs
`scripts/self-write-digest.py` (operation `identify_and_substitute`), as
`references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
comparison timing" states. Step 3 validates and applies the patch against the
digest_source the script returned: application rule 1 of
`references/workflow-patch.md` compares that substituted digest_source with the
dispatch-time `input_digest`, and a mismatch, or a script exit other than `0`,
makes the result stale. The orchestrator then runs the return-time recheck
before the recording phase-state write, as
`references/contracts/worker-envelope.md`, Rule R1, "Recomputation and
comparison timing" states; a recheck mismatch, or a recheck that cannot run,
makes the result stale. The orchestrator records `self_write_set` in the same
phase-state write as the `Layer 5 recording` of `written_artifacts` into
`phase-state/rework.yaml`."""


def _application_order_defects(text):
    """Everything wrong with the order of validation, recheck and application
    in `text`, as a list of strings starting with a code: missing / order /
    application-missing / application-order. An empty list means the recheck
    follows the step 3 validation and the rule-1 compare/stale sentence, and
    every application token follows the recheck."""
    recheck_pos = _pos(text, RECHECK_TOKEN)
    if recheck_pos < 0:
        return [f"missing: no text names {RECHECK_TOKEN!r}"]
    defects = []

    validation_pos = _pos(text, VALIDATION_TOKEN)
    if validation_pos < 0:
        defects.append(f"order: {VALIDATION_TOKEN!r} not found")
    elif recheck_pos <= validation_pos:
        defects.append(f"order: the recheck does not come after {VALIDATION_TOKEN!r}")

    stale_tokens = REWORK_SITE.stale_tokens
    stale_end = _sentence_end(text, *stale_tokens)
    if stale_end < 0:
        defects.append(f"order: compare/stale sentence {stale_tokens!r} not found")
    elif recheck_pos < stale_end:
        defects.append("order: the recheck is inside or before the compare/stale sentence")

    positions = {token: _pos(text, token) for token in APPLICATION_TOKENS}
    present = {token: pos for token, pos in positions.items() if pos >= 0}
    if not present:
        defects.append(f"application-missing: none of {APPLICATION_TOKENS!r} is present")
    for token, pos in present.items():
        if pos < recheck_pos:
            defects.append(f"application-order: {token!r} comes before the recheck")
    return defects


def _application_statement_defects(text):
    """What is wrong with the sentence that says the patch is applied only
    after a passing recheck, as a list of strings starting with a code:
    missing / statement / order. The sentence names the workflow.yaml write
    and the commit, and comes after the recheck sentence."""
    if not [s for s in _sentences(text) if _has(s, RECHECK_TOKEN)]:
        return [f"missing: no sentence names {RECHECK_TOKEN!r}"]
    recheck_end = _sentence_end(text, RECHECK_TOKEN)
    matches = [
        s for s in _sentences(text)
        if all(_has(s, t) for t in APPLIED_ONLY_AFTER_TOKENS)
    ]
    if not matches:
        return [f"statement: no sentence contains all of {APPLIED_ONLY_AFTER_TOKENS!r}"]
    if not [s for s in matches if _pos(text, s) >= recheck_end]:
        return ["order: the application sentence does not come after the recheck sentence"]
    return []


def _application_sentence(text):
    return _sentence_with(text, *APPLIED_ONLY_AFTER_TOKENS)


def _without_sentence(text, *tokens):
    """`text`, normalized, with the first sentence that holds `tokens` removed."""
    flat = _norm(text)
    return flat.replace(_sentence_with(flat, *tokens), "", 1)


def _with_sentence_moved_before(text, moved_tokens, anchor_tokens):
    """`text`, normalized, with the sentence holding `moved_tokens` placed
    directly before the sentence holding `anchor_tokens`."""
    flat = _norm(text)
    moved = _sentence_with(flat, *moved_tokens)
    anchor = _sentence_with(flat, *anchor_tokens)
    rest = flat.replace(moved, "", 1)
    if anchor not in rest:
        raise AssertionError("anchor sentence is not a substring of the remaining text")
    return rest.replace(anchor, moved + " " + anchor, 1)


# Section 10's review-sourced steps and the passages that cite their numbers.
REVIEW_SOURCED_STEPS = (
    (1, "review.needs_rework"),
    (2, "dispatches rework-planner"),
    (3, "validates and applies rework-planner's patch"),
    (4, "`implement` returning to `pending`"),
)
VERIFY_SOURCED_MARKER = "**Verify-sourced rework**"
REVIEW_PHASE_STEP_CITATION = (
    "after step 1 of `references/rework-task-synthesis.md` Section 10"
)
DEVELOP_STEP_CITATION = "step 1 は行わず step 2 から"


def _step_numbering_defects(section, review_phase, develop):
    """What is wrong with section 10's numbered steps, as a list of strings
    starting with a code: list / meaning / citation. An empty list means items
    1-4 of the review-sourced list exist in order before the "Verify-sourced
    rework" sentence, each with its meaning token, and the review-phase and
    develop citations of those numbers still exist."""
    cut = section.find(VERIFY_SOURCED_MARKER)
    if cut < 0:
        return [f"list: {VERIFY_SOURCED_MARKER!r} not found in the section"]
    head = section[:cut]
    defects = []
    numbers = [int(m.group(1)) for m in re.finditer(r"^(\d+)\.\s", head, re.M)]
    expected = [number for number, _token in REVIEW_SOURCED_STEPS]
    if numbers != expected:
        defects.append(f"list: items are numbered {numbers}, expected {expected}")
    for number, token in REVIEW_SOURCED_STEPS:
        try:
            item = _numbered_item(head, number)
        except AssertionError:
            defects.append(f"list: no item numbered {number}")
            continue
        if not _has(item, token):
            defects.append(f"meaning: item {number} lacks {token!r}")
    if not _has(review_phase, REVIEW_PHASE_STEP_CITATION):
        defects.append(f"citation: review-phase.md lacks {REVIEW_PHASE_STEP_CITATION!r}")
    if not _has(develop, DEVELOP_STEP_CITATION):
        defects.append(f"citation: develop SKILL.md lacks {DEVELOP_STEP_CITATION!r}")
    return defects


class TestReworkSection10ApplicationOrder(unittest.TestCase):
    """AC-1 (FR1, TM-1): the recheck follows step 3's validation and precedes
    every mention of the patch application."""

    def test_real_paragraph_has_no_order_defect(self):
        self.assertEqual(_application_order_defects(RW_RETURN_TIME), [])

    def test_recheck_follows_the_step_3_validation_token(self):
        validation_pos = _pos(RW_RETURN_TIME, VALIDATION_TOKEN)
        self.assertGreaterEqual(validation_pos, 0)
        self.assertLess(validation_pos, _pos(RW_RETURN_TIME, RECHECK_TOKEN))

    def test_recheck_follows_the_end_of_the_rule_1_compare_and_stale_sentence(self):
        stale_end = _sentence_end(RW_RETURN_TIME, *REWORK_SITE.stale_tokens)
        self.assertGreater(stale_end, 0)
        self.assertGreaterEqual(_pos(RW_RETURN_TIME, RECHECK_TOKEN), stale_end)

    def test_at_least_one_application_token_is_present(self):
        present = [t for t in APPLICATION_TOKENS if _has(RW_RETURN_TIME, t)]
        self.assertNotEqual(present, [])

    def test_every_application_token_present_follows_the_recheck(self):
        recheck_pos = _pos(RW_RETURN_TIME, RECHECK_TOKEN)
        for token in APPLICATION_TOKENS:
            if _has(RW_RETURN_TIME, token):
                with self.subTest(token=token):
                    self.assertGreater(_pos(RW_RETURN_TIME, token), recheck_pos)

    def test_validation_sentence_names_rules_1_to_14_and_the_rule_1_comparison(self):
        sentence = _sentence_with(RW_RETURN_TIME, VALIDATION_TOKEN)
        for token in (
            "application rules 1-14",
            "references/workflow-patch.md",
            "rule 1",
            "substituted digest_source",
            "dispatch-time `input_digest`",
            "script exit",
            "stale",
        ):
            with self.subTest(token=token):
                self.assertTrue(_has(sentence, token), sentence)

    def test_validation_sentence_no_longer_says_that_step_3_applies_the_patch(self):
        sentence = _sentence_with(RW_RETURN_TIME, VALIDATION_TOKEN)
        self.assertFalse(_has(sentence, "applies"), sentence)

    def test_application_tokens_never_match_the_validation_wording(self):
        validation_wording = (
            "Step 3 validates the patch by application rules 1-14 of "
            "`references/workflow-patch.md`.",
            "Application rule 1 of `references/workflow-patch.md` compares the digest.",
        )
        for wording in validation_wording:
            for token in APPLICATION_TOKENS:
                with self.subTest(token=token):
                    self.assertFalse(_has(wording, token), wording)

    def test_paragraph_adds_no_numbered_step(self):
        self.assertIsNone(re.search(r"^\d+\.\s", RW_RETURN_TIME, re.M))

    # -- AC-2: the sentence that says when the patch is applied ------------

    def test_application_sentence_follows_the_recheck_sentence(self):
        self.assertEqual(_application_statement_defects(RW_RETURN_TIME), [])

    def test_application_sentence_names_the_workflow_yaml_write_and_the_commit(self):
        sentence = _application_sentence(RW_RETURN_TIME)
        for token in ("rule 15", "rule 16", "workflow.yaml", "commit", "stale"):
            with self.subTest(token=token):
                self.assertTrue(_has(sentence, token), sentence)

    def test_application_sentence_without_it_makes_the_statement_probe_fire(self):
        forged = _without_sentence(RW_RETURN_TIME, *APPLIED_ONLY_AFTER_TOKENS)
        defects = _application_statement_defects(forged)
        self.assertEqual(_defect_codes(defects), ["statement"], defects)

    def test_application_sentence_before_the_recheck_makes_the_statement_probe_fire(self):
        forged = _with_sentence_moved_before(
            RW_RETURN_TIME, APPLIED_ONLY_AFTER_TOKENS, (RECHECK_TOKEN,)
        )
        defects = _application_statement_defects(forged)
        self.assertEqual(_defect_codes(defects), ["order"], defects)

    def test_application_sentence_without_the_commit_makes_the_statement_probe_fire(self):
        sentence = _application_sentence(RW_RETURN_TIME)
        forged = _norm(RW_RETURN_TIME).replace(sentence, sentence.replace("commit", "step"))
        defects = _application_statement_defects(forged)
        self.assertEqual(_defect_codes(defects), ["statement"], defects)

    def test_statement_probe_on_text_without_the_recheck_fires_as_missing(self):
        defects = _application_statement_defects(PRE_CHANGE_RW_RETURN_TIME)
        self.assertEqual(_defect_codes(defects), ["missing"], defects)

    # -- AC-3: forged controls make the order probe fire -------------------

    def test_base_revision_paragraph_makes_the_order_probe_fire(self):
        defects = _application_order_defects(BASE_REVISION_RW_RETURN_TIME)
        self.assertEqual(_defect_codes(defects), ["application-order"], defects)

    def test_base_revision_paragraph_holds_the_recheck_after_validates_and_applies(self):
        self.assertGreaterEqual(_pos(BASE_REVISION_RW_RETURN_TIME, "Step 3 validates and applies"), 0)
        self.assertLess(
            _pos(BASE_REVISION_RW_RETURN_TIME, "Step 3 validates and applies"),
            _pos(BASE_REVISION_RW_RETURN_TIME, RECHECK_TOKEN),
        )

    def test_base_revision_paragraph_passes_the_other_site_checks(self):
        self.assertEqual(_recheck_defects(BASE_REVISION_RW_RETURN_TIME, REWORK_SITE), [])

    def test_application_sentence_moved_before_the_recheck_makes_the_order_probe_fire(self):
        forged = _with_sentence_moved_before(
            RW_RETURN_TIME, APPLIED_ONLY_AFTER_TOKENS, (RECHECK_TOKEN,)
        )
        defects = _application_order_defects(forged)
        self.assertEqual(_defect_codes(defects), ["application-order"], defects)

    def test_application_sentence_removed_makes_the_order_probe_fire(self):
        forged = _without_sentence(RW_RETURN_TIME, *APPLIED_ONLY_AFTER_TOKENS)
        defects = _application_order_defects(forged)
        self.assertEqual(_defect_codes(defects), ["application-missing"], defects)

    def test_recheck_moved_before_the_validation_makes_the_order_probe_fire(self):
        forged = _with_sentence_moved_before(
            RW_RETURN_TIME, (RECHECK_TOKEN,), (VALIDATION_TOKEN,)
        )
        defects = _application_order_defects(forged)
        self.assertIn("order", _defect_codes(defects), defects)

    def test_text_without_the_recheck_makes_the_order_probe_fire_as_missing(self):
        defects = _application_order_defects(PRE_CHANGE_RW_RETURN_TIME)
        self.assertEqual(_defect_codes(defects), ["missing"], defects)


class TestReworkSection10StepNumbering(unittest.TestCase):
    """AC-5 (FR3): section 10's review-sourced steps 1-4 keep their numbers and
    meaning; the citations of those numbers still resolve."""

    def test_real_section_has_no_step_numbering_defect(self):
        self.assertEqual(_step_numbering_defects(RW_SECTION_10, _REVIEW_PHASE, _DEVELOP), [])

    def test_steps_1_to_4_come_in_order_before_the_verify_sourced_sentence(self):
        head = RW_SECTION_10[: RW_SECTION_10.index(VERIFY_SOURCED_MARKER)]
        found = [int(m.group(1)) for m in re.finditer(r"^(\d+)\.\s", head, re.M)]
        self.assertEqual(found, [1, 2, 3, 4])

    def test_each_step_keeps_its_meaning_token(self):
        head = RW_SECTION_10[: RW_SECTION_10.index(VERIFY_SOURCED_MARKER)]
        for number, token in REVIEW_SOURCED_STEPS:
            with self.subTest(step=number):
                self.assertTrue(_has(_numbered_item(head, number), token))

    def test_review_phase_cites_step_1_of_section_10(self):
        self.assertTrue(_has(_REVIEW_PHASE, REVIEW_PHASE_STEP_CITATION))

    def test_develop_skill_cites_starting_from_step_2(self):
        self.assertTrue(_has(_DEVELOP, DEVELOP_STEP_CITATION))

    def test_step_inserted_between_steps_3_and_4_makes_the_probe_fire(self):
        forged = RW_SECTION_10.replace(
            "\n4. ", "\n4. The orchestrator runs the return-time recheck.\n5. ", 1
        )
        self.assertNotEqual(forged, RW_SECTION_10)
        defects = _step_numbering_defects(forged, _REVIEW_PHASE, _DEVELOP)
        self.assertEqual(_defect_codes(defects), ["list", "meaning"], defects)

    def test_missing_step_makes_the_probe_fire(self):
        forged = RW_SECTION_10.replace("\n3. ", "\n- ", 1)
        self.assertNotEqual(forged, RW_SECTION_10)
        defects = _step_numbering_defects(forged, _REVIEW_PHASE, _DEVELOP)
        self.assertIn("list", _defect_codes(defects), defects)

    def test_section_without_the_verify_sourced_sentence_makes_the_probe_fire(self):
        forged = RW_SECTION_10.replace(VERIFY_SOURCED_MARKER, "**Other**", 1)
        defects = _step_numbering_defects(forged, _REVIEW_PHASE, _DEVELOP)
        self.assertEqual(_defect_codes(defects), ["list"], defects)

    def test_changed_citations_make_the_probe_fire(self):
        review_phase = _REVIEW_PHASE.replace("after step 1 of", "after step 2 of", 1)
        develop = _DEVELOP.replace("step 1 は行わず", "step 2 は行わず", 1)
        self.assertNotEqual(review_phase, _REVIEW_PHASE)
        self.assertNotEqual(develop, _DEVELOP)
        defects = _step_numbering_defects(RW_SECTION_10, review_phase, _DEVELOP)
        self.assertEqual(_defect_codes(defects), ["citation"], defects)
        defects = _step_numbering_defects(RW_SECTION_10, _REVIEW_PHASE, develop)
        self.assertEqual(_defect_codes(defects), ["citation"], defects)


class TestApplicationOrderHelpers(unittest.TestCase):
    def test_sentence_moved_before_puts_the_sentence_directly_before_the_anchor(self):
        text = "alpha one. beta two. gamma three."
        moved = _with_sentence_moved_before(text, ("gamma",), ("beta",))
        self.assertEqual([s.split()[0] for s in _sentences(moved)], ["alpha", "gamma", "beta"])

    def test_without_sentence_removes_only_the_first_matching_sentence(self):
        text = "alpha one. beta two. gamma three."
        self.assertEqual(_sentences(_without_sentence(text, "beta")), ["alpha one.", "gamma three."])


# ---------------------------------------------------------------------------
# The slicing helpers the assertions above rely on
# ---------------------------------------------------------------------------


class TestSliceHelpers(unittest.TestCase):
    def test_numbered_item_stops_at_the_next_unindented_line(self):
        text = "1. a\n   cont\n2. b\n   more\n\ntrailing\n"
        self.assertEqual(_norm(_numbered_item(text, 1)), "1. a cont")
        self.assertEqual(_norm(_numbered_item(text, 2)), "2. b more")

    def test_section_requires_exactly_one_heading(self):
        with self.assertRaises(AssertionError):
            _section("# a\n\n## x\n\n## x\n", "x", 2)

    def test_sentence_with_requires_every_token_in_one_sentence(self):
        with self.assertRaises(AssertionError):
            _sentence_with("alpha is here. beta is there.", "alpha", "beta")

    def test_pos_ignores_line_wraps_and_case(self):
        self.assertEqual(_pos("return-time\n  Recheck", RECHECK_TOKEN), 0)
        self.assertEqual(_pos("none here", RECHECK_TOKEN), -1)

    def test_sentence_end_marks_the_end_of_the_first_matching_sentence(self):
        text = "one two. three four. five"
        self.assertEqual(_sentence_end(text, "three"), len(_squash("one two. three four.")))
        self.assertEqual(_sentence_end(text, "absent"), -1)


if __name__ == "__main__":
    unittest.main()
