# Feature: batch-structured-result-output

Requirements document: `feature-docs/batch-structured-result-output/REQUIREMENTS.md`.
This specification is the implementation-facing rendering of that document;
both derive from the same resolved requirements.

## Overview

em-workflow's batch terminal output and its external consumer have silently
diverged: the consumer parses a batch run's captured stdout as YAML and
requires a top-level mapping of eight keys, while em-workflow still emits an
`EM_WORKFLOW_TERMINAL:`-prefixed four-field `key=value` line, and the
consumer has already deleted its marker-line parser. This change replaces
the terminal line with the structured eight-key YAML result, makes that
result em-workflow's sole terminal output shape, and restates every SSOT
paragraph and test assertion that depended on the old shape.

## Objectives

- Make a batch run's terminal state machine-readable by the consumer again.
- Make the structured result em-workflow's sole terminal output shape, with
  no dual emission and no compatibility period.
- Make the next divergence from the consumer's documented domain visible in
  this repository rather than silent.

## User Stories

### US1: Terminal batch turn emits a structured result

As em-workflow running in batch mode, I want to emit the terminal state as a
bare eight-key YAML mapping, so that the run's outcome is machine-readable
by the consumer.

**Acceptance Criteria:**

- [ ] AC-1: A terminal batch turn's final assistant message parses under a
      strict YAML load as exactly one mapping, with exactly the eight keys of
      FR3, in that order, each appearing once, and every value a string.
- [ ] AC-2: The emitted document is exactly eight physical lines for every
      input, including values whose sources contain CR, LF, CRLF and TAB.
- [ ] AC-3: All 14 adversarial cases of NFR3 round-trip through PyYAML to a
      single mapping of eight string values.
- [ ] AC-4: `detail`'s normalization (FR7) is applied before escaping, and is
      NOT applied to `resume_conditions` (FR8) — demonstrated by a `detail`
      source containing newlines yielding no `\n` escape, and a
      `resume_conditions` source containing newlines yielding `\n` escapes.
- [ ] AC-5: `feature`, `branch`, `pr_url` and `resume_conditions` follow
      FR9-FR12 at each named site, including the Step 0 git-setup abort, the
      Step A feature-resolution abort, the post-worktree-removal keep-branch
      case, the PR-created-then-stopped case and the verify cap-reached run.

### US2: Consumer parses the captured stdout

As the external consumer, I want the run's captured stdout to satisfy my
documented constraints, so that I can accept the result without a marker-line
parser.

**Acceptance Criteria:**

- [ ] AC-6: The consumer's constraints (FR14) hold: no `stopped`+`none`;
      `phase_done` implies `reason: "none"` and `resume_conditions: ""`;
      `branch` and `pr_url` carry no line terminators and no terminal-control
      code points; the document is at most 64 KiB UTF-8.
- [ ] AC-10: Every audit item "## Reporting" requires appears in full inside
      `detail` or `resume_conditions` (FR17); no pointer-only or count-only
      presentation of any item; the change writes no new aggregated report
      artifact.

### US3: The repository keeps the contract single-sited

As an em-workflow maintainer, I want the structured result defined in exactly
one place and cited everywhere else, so that a future divergence surfaces in
this repository.

**Acceptance Criteria:**

- [ ] AC-7: The literal `EM_WORKFLOW_TERMINAL:` occurs nowhere under
      `em-workflow/` — the existing AC-7 sweep in
      `tests/test_batch_stop_contract.py` is inverted from "only inside
      `batch-terminal-line.md`'s fenced blocks" to "absent everywhere".
- [ ] AC-8: The SSOT documents twelve `reason` values, marks
      `context_budget_reached` as never emitted by em-workflow, keeps the Stop
      point coverage table at eleven rows binding the same eleven codes, and
      states the named exception explicitly (FR15).
- [ ] AC-9: `batch-mode.md`'s restated "## Batch quiet output" paragraph
      (FR18) names `EM_WORKFLOW_PROGRESS:`, establishes non-confusability
      against the structured result's shape without naming any terminal
      prefix, and preserves NFR6's absence signal.
- [ ] AC-11: `batch-mode.md`, `skills/develop/SKILL.md` and
      `implement-phase.md` name the SSOT and restate no literal from it (FR20,
      NFR1) — the retargeted absence guards pass.
- [ ] AC-12: `em-workflow/.claude-plugin/plugin.json` and the em-workflow
      entry of `.claude-plugin/marketplace.json` carry the same, bumped
      version (FR21).
- [ ] AC-13: `python3 -m unittest discover -s tests` passes with no new
      failures, and every new matcher carries a negative proof plus a
      non-vacuity guard (NFR4).

## Technical Requirements

### Functional Requirements

- **FR1 — SSOT ownership of the structured result:**
  `em-workflow/references/batch-terminal-line.md` becomes the sole owner of
  the structured result's format — its key set, key order, quoting and
  escaping rules, the `state` / `step` / `reason` value domains, the closed
  stop reason-code set, and the mapping from every terminating stop point to
  a reason code — replacing its current ownership of a prefixed four-field
  line.
- **FR2 — Bare eight-key mapping as the whole final message:** The final
  assistant message of a terminal batch turn is one YAML mapping emitted
  bare: no code fence, no surrounding prose, no document separator, no
  comments, no extra keys, and nothing before or after it.
- **FR3 — Fixed key set and key order:** Exactly these eight keys, each
  written once, at line start, in this order: `state`, `step`, `reason`,
  `detail`, `feature`, `branch`, `pr_url`, `resume_conditions`.
- **FR4 — Every value a double-quoted scalar:** Every value is emitted as a
  double-quoted YAML scalar, including the empty string, which is written
  `""`.
- **FR5 — Escaping rule:** Applied character by character to the source
  value, never re-processing a generated escape: `\` to `\\`; `"` to `\"`;
  CR to `\r`; LF to `\n`; TAB to `\t`. Any remaining character in
  U+0000-U+001F, U+007F-U+009F, U+2028, U+2029, U+FFFE, U+FFFF becomes a
  four-digit `\uXXXX`. Every other valid Unicode character is kept as-is.
- **FR6 — Eight-physical-line invariant:** Because every value is
  double-quoted, a `:`, a leading `-` or a `#` inside a value needs no
  special handling. No physical newline ever appears inside a value, so the
  document is always exactly eight physical lines.
- **FR7 — `detail` normalization retained, then escaped:** `detail` keeps its
  existing normalization exactly as the current SSOT states it: CR/LF/TAB to
  a single space, runs of spaces collapsed, the result trimmed, and a fixed
  non-empty placeholder substituted when the normalized value is empty.
  Normalization and YAML escaping are two separate steps applied in that
  order.
- **FR8 — `resume_conditions` is not detail-normalized:** The `detail`
  normalization is NOT applied to `resume_conditions`, which is Markdown and
  preserves its own newlines, indentation and trailing spaces — surviving as
  `\n` escapes inside the quoted scalar.
- **FR9 — `feature` derivation:** `feature` is the confirmed feature slug, or
  `""` when the slug was never confirmed. It is never guessed from a task
  description and never guessed from existing branches. An explicitly
  supplied name is usable even at a Step 0 abort, but only if it matches
  `^[a-z0-9][a-z0-9-]*$`.
- **FR10 — `branch` derivation:** `branch` is
  `em-workflow/{feature}/integration` only when this run confirmed that
  branch exists or created it; `""` otherwise, including the Step 0 git-setup
  abort and the Step A feature-resolution abort. Being able to construct the
  name is not the same as the branch existing. The value is retained after
  Step C removes the worktree when the branch is kept.
- **FR11 — `pr_url` derivation:** `pr_url` is the bare URL of a PR this run's
  Step C created successfully with `gh pr create`, and `""` otherwise. It is
  retained even when the run subsequently stops — e.g. a cleanup failure
  after the PR was created, or a verify cap-reached run.
- **FR12 — `resume_conditions` presence rule:** `resume_conditions` is
  non-whitespace Markdown only when `state` is `stopped`, and `""` when
  `state` is `completed` or `phase_done`.
- **FR13 — `state` and `step` domains unchanged:** The `state` domain
  (`completed` / `stopped` / `phase_done`), the `step` domain (the seven
  `workflow.yaml` step ids plus the `no-step` sentinel) and all of `step`'s
  existing precedence rules — the general executed-step rule, the `no-step`
  sentinel rule, the `state=completed` to `retrospect` rule, and the Step C
  outcome asymmetry — are unchanged.
- **FR14 — Constraints carried over from the consumer:** `state: "stopped"`
  with `reason: "none"` is rejected; `state: "phase_done"` requires
  `reason: "none"` and `resume_conditions: ""`; `branch` and `pr_url` must
  contain no line terminators and no terminal-control code points (escaping
  does not help — the consumer rejects the value after parsing); the whole
  document must be at most 64 KiB encoded UTF-8.
- **FR15 — `context_budget_reached` documented as never emitted:**
  `context_budget_reached` is listed in the SSOT's documented `reason` value
  domain and explicitly marked as a code em-workflow NEVER emits (reserved by
  the consumer). The Stop point coverage table keeps its eleven rows and
  eleven bound codes; the departure from the "every code has exactly one stop
  point" symmetry is stated as an intentional, named exception covering
  exactly this one code.
- **FR16 — Legacy marker line removed entirely:** The
  `EM_WORKFLOW_TERMINAL:`-prefixed four-field line is removed entirely. The
  structured YAML result is em-workflow's sole terminal output shape; no dual
  emission, no compatibility period.
- **FR17 — "## Reporting" audit items carried in full inside the values:**
  Every audit item `references/batch-mode.md`'s "## Reporting" requires is
  carried IN FULL inside the string values — the audit items and the take-over
  guidance in `detail`, the stop-recovery guidance in `resume_conditions`.
  Presence by reference (a count, or a pointer alone) does NOT satisfy
  "## Reporting". No new aggregated report artifact is written:
  batch-mode.md's Audit-item source map already binds every required item to
  an already-persisted location.
- **FR18 — Prefix-disjointness paragraph restated:**
  `references/batch-mode.md`'s "## Batch quiet output" paragraph justifying
  prefix disjointness must be restated: with the terminal prefix gone there is
  no longer a terminal prefix to compare the `EM_WORKFLOW_PROGRESS:` prefix
  against. The restated paragraph must still establish that a consumer never
  confuses a non-terminal marker line with a terminal structured result, and
  must still preserve the terminal contract's "no result = abnormal outcome"
  signal.
- **FR19 — Progress marker line unchanged:** The non-terminal
  `EM_WORKFLOW_PROGRESS:` marker line keeps its current two-field (`phase`,
  `point`) shape and is out of scope, EXCEPT for the restatement required by
  FR18.
- **FR20 — Pointer documents updated without restating literals:**
  `references/batch-mode.md`'s "## Terminal line" section,
  `skills/develop/SKILL.md`'s 「## バッチ終端行」 section and its four other
  終端行 citations, and `references/implement-phase.md`'s one citation are
  updated to the structured result. They keep naming the SSOT and continue to
  restate none of its literals — no `state=` value literal, no reason code, no
  `no-step` sentinel, no field-name token set — because the existing D2 guards
  assert exactly those absences.
- **FR21 — Plugin version bump:** Per
  `.claude/rules/core-plugin-version-bump.md`, the same change bumps the
  em-workflow version in both `em-workflow/.claude-plugin/plugin.json` and the
  em-workflow entry of `.claude-plugin/marketplace.json`, to the same value.
  Both currently read `0.1.82`. The em-review entry (`0.5.10`) is not touched.
- **FR22 — Test-side contract updated in the same change:** Every test module
  that pins the old shape is updated within this same change rather than left
  to go stale, following the repository's established convention.

### Non-Functional Requirements

- **NFR1 - SSOT discipline preserved:** `batch-terminal-line.md` remains the
  single definition site. `batch-mode.md`, `skills/develop/SKILL.md` and
  `implement-phase.md` cite it and restate no literal from it. The existing
  whole-file absence guards (`tests/test_batch_quiet_output_discipline.py`,
  `tests/test_batch_quiet_output_phase_wiring.py`,
  `tests/test_batch_stop_contract_skill_wiring.py`) must stay green after
  being retargeted to the new literals.
- **NFR2 - No external tool, LLM-writable:** Emitting the result requires no
  external tool: it is text the model writes into its final assistant message.
  The escaping rule must therefore be applicable character by character,
  without a YAML serializer library, and must be stated in the SSOT in a form
  an LLM can follow deterministically.
- **NFR3 - Conformance verified against a real parser:** The quoting rule is
  verified against PyYAML over 14 adversarial cases (empty string, `null`,
  `true`, `0`, `: value`, `- item`, `# title`, `x: y # z`, embedded LF / CRLF
  / TAB, embedded quotes and backslashes, non-BMP emoji, and a string of
  C0/C1/line-separator/noncharacter code points); each must round-trip to a
  single mapping of eight string values.
- **NFR4 - Test authoring convention:** Follow the repository's existing
  convention: durable invariants over fixed literals wherever a literal would
  go stale; a negative proof plus a non-vacuity guard per new matcher; pure
  regression guards over retained wording exempted. Test modules import the
  Python standard library only (`os`, `re`, `unittest`, `pathlib`) and are
  discovered by `python3 -m unittest discover -s tests`.
- **NFR5 - Confidentiality boundary extended to the new fields:** The
  "## Responsibility boundary" rule — the result carries no confidential
  information beyond paths, because its content is relayed outside
  em-workflow's process boundary — now governs `detail`, `resume_conditions`,
  `branch` and `pr_url`, not `detail` alone.
- **NFR6 - Absence remains the abnormal-outcome signal:** A crash or truncated
  turn produces no structured result; a consumer that sees no result at the
  end of a run reads that absence as an abnormal outcome rather than as
  success. This property must survive FR16 and FR18.
- **NFR7 - Bundled-file awareness:** Per
  `.claude/rules/core-plugin-structure.md`, everything under `em-workflow/` is
  copied into the user's plugin cache. Nothing in this change adds a runtime
  dependency or a generated artifact under that root.

## Implementation Approach

### Architecture

**Emission path:**

```
terminal stop point
  → state / step / reason        (FR13, FR15 domains — unchanged)
  → detail            normalize (FR7) → escape (FR5)
  → feature / branch / pr_url    derive (FR9, FR10, FR11) → escape (FR5)
  → resume_conditions            derive (FR12) → escape only (FR8, FR5)
  → eight quoted lines in fixed order (FR2, FR3, FR4, FR6)
  → final assistant message (whole message, nothing else)
```

There is no runtime component: the emission is text the model writes (NFR2).
The only executable artifacts this change touches are the Python test
modules.

**Component Diagram:**

```
batch-terminal-line.md   (SSOT — owns the format, FR1)
        ▲ cited by, literals never restated (FR20, NFR1)
        ├── batch-mode.md            ## Terminal line / ## Batch quiet output
        │                            / ## Reporting / ## Responsibility boundary
        ├── skills/develop/SKILL.md  ## バッチ終端行 + 4 citations
        └── implement-phase.md       1 citation

tests/  (asserts the SSOT's structure and the pointers' literal-absence)
```

### Data Flow

```
run reaches a terminal stop point
  → derivation per FR7-FR13
  → escaping per FR5
  → bare eight-line YAML mapping on stdout (final assistant message)
  → consumer parses stdout as YAML, applies FR14's constraints
```

Absence of a result at the end of a run is itself the abnormal-outcome
signal (NFR6).

### Result Document Shape

| Key | Order | Value |
|---|---|---|
| `state` | 1 | `completed` / `stopped` / `phase_done` (FR13) |
| `step` | 2 | one of the seven `workflow.yaml` step ids, or the `no-step` sentinel (FR13) |
| `reason` | 3 | one of the twelve documented values; `context_budget_reached` is never emitted (FR15) |
| `detail` | 4 | normalized (FR7) then escaped (FR5); carries the "## Reporting" audit items and take-over guidance in full (FR17) |
| `feature` | 5 | confirmed slug, else `""` (FR9) |
| `branch` | 6 | `em-workflow/{feature}/integration` when confirmed or created by this run, else `""` (FR10) |
| `pr_url` | 7 | bare URL of a PR created by this run's Step C, else `""` (FR11) |
| `resume_conditions` | 8 | non-whitespace Markdown only when `state` is `stopped`, else `""` (FR12); carries the stop-recovery guidance in full (FR17) |

Every value is a double-quoted scalar (FR4); the empty value is `""`. The
document is always exactly eight physical lines (FR6).

### API Design

Not applicable: no endpoint is added or changed. The interface with the
external consumer is the result document shape above, constrained by FR14.

### Database Schema

Not applicable: no persisted data store is involved. No new aggregated report
artifact is written (FR17).

### Dependencies

**Internal Dependencies:**

- `em-workflow/references/batch-terminal-line.md`: the SSOT this change
  re-owns (FR1).
- `em-workflow/references/batch-mode.md`: "## Terminal line",
  "## Batch quiet output", "## Reporting" with its Audit-item source map, and
  "## Responsibility boundary" (FR17, FR18, FR20, NFR5).
- `em-workflow/skills/develop/SKILL.md`: 「## バッチ終端行」 plus four other
  終端行 citations (FR20).
- `em-workflow/references/implement-phase.md`: one citation (FR20).
- `.claude/rules/core-plugin-version-bump.md` (FR21),
  `.claude/rules/core-plugin-structure.md` (NFR7),
  `.claude/rules/hook-tests.md` (TS11).

**External Dependencies:**

- PyYAML: used by the conformance tests as the real parser (NFR3). No runtime
  dependency is added under `em-workflow/` (NFR7).

### File Structure

```
em-workflow/
├── references/
│   ├── batch-terminal-line.md      # SSOT of the structured result (FR1)
│   ├── batch-mode.md               # FR17, FR18, FR20, NFR5
│   └── implement-phase.md          # FR20
├── skills/develop/SKILL.md         # FR20
└── .claude-plugin/plugin.json      # FR21
.claude-plugin/marketplace.json     # FR21
tests/
├── test_batch_stop_contract.py                 # CONTRACT_HEADINGS (A2), AC-7 sweep
├── test_batch_quiet_output_discipline.py       # absence guard (NFR1)
├── test_batch_quiet_output_phase_wiring.py     # absence guard (NFR1)
└── test_batch_stop_contract_skill_wiring.py    # absence guard (NFR1)
```

The change is documentation-and-test-only: three reference SSOT markdown
documents, one skill markdown document, ten Python test modules and two JSON
version manifests.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1 (AC-1, AC-2): Parse a representative terminal result for each
      `state` value under a strict YAML load; assert one mapping, eight keys in
      fixed order, all string values, and exactly eight physical lines.
- [ ] TS2 (AC-3): Feed each of the 14 adversarial source values through the
      documented escaping rule and PyYAML; assert the round-tripped value
      equals the source value byte for byte.
- [ ] TS3 (AC-4): A `detail` source containing CR/LF/TAB and space runs; a
      `resume_conditions` source containing newlines, indentation and trailing
      spaces. Assert normalization-then-escaping on the former and
      escaping-only on the latter.
- [ ] TS4 (AC-5): Table-driven over the derivation sites: Step 0 abort without
      a supplied name, Step 0 abort with a slug-conforming supplied name, Step 0
      abort with a non-conforming supplied name, Step A abort, branch created,
      branch confirmed existing, Step C keep-branch after worktree removal,
      `--pr` success, `--pr` success followed by a cleanup stop, verify
      cap-reached run.
- [ ] TS7 (AC-8): Extract the `reason` value domain and the coverage table
      structurally; assert twelve documented values, eleven coverage rows,
      eleven bound codes, `context_budget_reached` absent from the coverage
      table and present in the domain marked never-emitted, and the
      named-exception sentence present. Negative proof: a forged domain that
      adds the twelfth code as a coverage row is rejected.
- [ ] TS10 (AC-12): Read both manifests; assert the em-workflow versions are
      equal and strictly greater than `0.1.82`, and that the em-review version
      is unchanged.

### Integration Tests

- [ ] TS6 (AC-7): `os.walk` over `em-workflow/` asserting the prefix literal
      is absent from every file (no hand-maintained allowlist), with the
      existing non-vacuity guard retained.
- [ ] TS8 (AC-9, AC-11): Retargeted absence guards over `batch-mode.md`,
      `skills/develop/SKILL.md` and `implement-phase.md`, plus a positive
      matcher over the restated disjointness paragraph with its own negative
      proof and non-vacuity guard.
- [ ] TS9 (AC-10): Each "## Reporting" audit item is asserted present in full
      within the value it is assigned to; a forged sample carrying a pointer or
      a count in place of an item is rejected. Assert no new aggregated report
      path enters the write set.
- [ ] TS11 (AC-13): Whole-suite `python3 -m unittest discover -s tests`, plus
      `python3 em-workflow/hooks/tests/run-destructive-guard.py` (unaffected,
      run as a no-regression check per `.claude/rules/hook-tests.md`).

### E2E Tests

**Existing E2E tests**: None — no E2E infrastructure exists in this project
(A7).
**Run command**: Not detected.

- [ ] TS12 (AC-1, AC-6): Manual — launch a real `--batch` run and a
      `--batch --once` run; capture stdout; confirm the consumer's parser
      accepts the result. No automated E2E harness exists in this project.

### Edge Cases

- [ ] TS5 (AC-6): Reject-path assertions for `stopped`+`none` and for
      `phase_done` with a non-empty `resume_conditions`; control-character and
      line-terminator rejection for `branch` / `pr_url` after parsing; a 64 KiB
      boundary case.
- [ ] NFR3's adversarial inputs (covered by TS2): empty string, `null`,
      `true`, `0`, `: value`, `- item`, `# title`, `x: y # z`, embedded LF /
      CRLF / TAB, embedded quotes and backslashes, non-BMP emoji, and a string
      of C0/C1/line-separator/noncharacter code points.
- [ ] `detail`'s fixed non-empty placeholder when the normalized value is
      empty (FR7).

### Performance Tests

Not applicable. The only size constraint is FR14's 64 KiB UTF-8 document
bound, covered by TS5.

## Security Considerations

- **Data Protection:** NFR5 — the confidentiality boundary ("no confidential
  information beyond paths", because the content is relayed outside
  em-workflow's process boundary) governs `detail`, `resume_conditions`,
  `branch` and `pr_url`.
- **Input Validation:** FR14 — `branch` and `pr_url` must carry no line
  terminators and no terminal-control code points; escaping does not help,
  since the consumer rejects the value after parsing. Control and
  noncharacter code points elsewhere are escaped as `\uXXXX` per FR5.
- **Authentication / Authorization / XSS / SQL injection / CSRF:** Not
  applicable — no endpoint, no data store and no rendered surface is involved.

## Error Handling

### Rejected Combinations (FR14)

| Condition | Consumer behaviour |
|---|---|
| `state: "stopped"` with `reason: "none"` | Rejected |
| `state: "phase_done"` without `reason: "none"` | Rejected |
| `state: "phase_done"` with non-empty `resume_conditions` | Rejected |
| `branch` or `pr_url` containing a line terminator or a terminal-control code point | Rejected after parsing |
| Document larger than 64 KiB encoded UTF-8 | Rejected |

### Absence of a Result

A crash or truncated turn produces no structured result. A consumer that
sees no result at the end of a run reads that absence as an abnormal
outcome rather than as success (NFR6); this property must survive FR16 and
FR18.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements (FR1-FR22) are implemented.
- [ ] All acceptance criteria AC-1 through AC-13 hold.
- [ ] All test scenarios TS1-TS12 pass, with TS12 performed manually.
- [ ] `python3 -m unittest discover -s tests` passes with no new failures
      (AC-13).
- [ ] The two manifests carry the same bumped em-workflow version, with the
      em-review version untouched (AC-12).
- [ ] The literal `EM_WORKFLOW_TERMINAL:` occurs nowhere under `em-workflow/`
      (AC-7).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every functional and non-functional requirement is resolved.

## Assumptions

- **A1** (reversible): The SSOT document keeps its existing path
  `em-workflow/references/batch-terminal-line.md`; no file rename accompanies
  the shape change.
- **A2** (reversible): The document's seven fixed level-2 headings may be
  renamed or extended as the new shape requires (notably "Line format"), and
  `CONTRACT_HEADINGS` in `tests/test_batch_stop_contract.py` is updated in the
  same change rather than left to go stale.
- **A3** (reversible): Occurrences of `EM_WORKFLOW_TERMINAL:` and of the
  four-field shape inside OTHER features' `feature-docs/**` artifacts are
  historical per-feature records, not live contract, and are not rewritten.
- **A4** (reversible): The eleven existing stop reason codes and their eleven
  stop-point bindings are unchanged; `context_budget_reached` is documented
  outside the coverage table.
- **A5** (reversible): The `state` and `step` domains and every `step`
  precedence rule are unchanged; their existing regression guards stay green
  unmodified.
- **A6** (reversible): The version bump is a patch bump from `0.1.82` in both
  manifests. If the plan judges the removal of the legacy line a compatibility
  break, a minor or major bump is equally admissible — the rule only requires
  the two manifests to agree.
- **A7** (reversible): No E2E infrastructure exists in this project.
  Verification is the Python `unittest` suite plus manual observation of a
  `--batch` run.
- **A8** (reversible): The project has no LICENSE file at its root, so
  `project.license` is recorded as unknown rather than guessed.

## Design Step

Skipped. Documentation-and-test-only change: three reference SSOT markdown
documents, one skill markdown document, ten Python test modules and two JSON
version manifests. No user-facing UI, no rendered surface, no visual input,
and no design-system candidate paths were resolved.

## References

- Requirements document: `feature-docs/batch-structured-result-output/REQUIREMENTS.md`
- Structured result SSOT: `em-workflow/references/batch-terminal-line.md`
- Batch mode contract: `em-workflow/references/batch-mode.md`
- Develop skill: `em-workflow/skills/develop/SKILL.md`
- Implement phase: `em-workflow/references/implement-phase.md`
- Contract heading and prefix-sweep tests: `tests/test_batch_stop_contract.py`
- Absence guards: `tests/test_batch_quiet_output_discipline.py`,
  `tests/test_batch_quiet_output_phase_wiring.py`,
  `tests/test_batch_stop_contract_skill_wiring.py`
- Version manifests: `em-workflow/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`
- Repository rules: `.claude/rules/core-plugin-version-bump.md`,
  `.claude/rules/core-plugin-structure.md`, `.claude/rules/hook-tests.md`
