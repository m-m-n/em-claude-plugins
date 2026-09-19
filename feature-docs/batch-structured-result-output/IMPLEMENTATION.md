# Implementation Plan: batch-structured-result-output

## Overview

Replace em-workflow's prefixed four-field batch terminal line with a bare
eight-key YAML structured result owned by one SSOT document, restate the three
pointer documents that cite it, and update every test module that pins the old
shape — in one change, with no compatibility period.

## Technology Stack

- **Primary artifact kind**: Markdown contract documents under
  `em-workflow/references/` and `em-workflow/skills/`. There is no runtime
  component — the structured result is text the model writes into its final
  assistant message (NFR2).
- **Test language**: Python 3 `unittest`, discovered by
  `python3 -m unittest discover -s tests` (workflow.yaml
  `project.components.main.test_command`).
- **New dependency**: PyYAML — test-time only, used as the real parser for the
  conformance cases (NFR3). License: MIT (permissive). `project.license` is
  `none`, so there is no project license to violate; the dependency is
  dev/test-only and is NOT added under `em-workflow/` (NFR7), so it never
  reaches a user's plugin cache. See D6 below.

## Layer Structure

Three layers, with a one-way citation direction that must not be reversed:

| Layer | Members | Responsibility |
|---|---|---|
| SSOT | `em-workflow/references/batch-terminal-line.md` | Owns the structured result's format in full: key set, key order, quoting, escaping, value domains, the closed stop reason-code set, the stop-point → reason-code mapping, the consumer constraints, and the confidentiality boundary (FR1) |
| Pointers | `em-workflow/references/batch-mode.md`, `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/implement-phase.md` | Name the SSOT and state only WHEN a result is emitted / what else a turn may print. Restate no literal the SSOT owns (FR20, NFR1) |
| Guards | `tests/**` | Assert the SSOT's structure positively and the pointers' literal-absence negatively |

Allowed dependency direction: Pointers → SSOT (by path citation only).
Guards → both. Never SSOT → Pointers.

## Shared Components

Every row below is a contract two or more tasks implement against
independently. Tasks run fully in parallel; nothing here may be renegotiated
inside a single task.

**Worktree-independence rule for the guards.** A task's own tests must pass in
that task's own worktree, where every OTHER task's edits are still absent. A
test module therefore asserts against a real repository file ONLY when the task
owning that file is the same task. Every cross-task expectation is expressed
against the canonical values written in this document instead, and the task
that owns a file also owns the single "binding" assertion that the real file
carries those canonical values (D5).

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| SC1 — Key set and key order | The structured result's eight keys | Exactly `state`, `step`, `reason`, `detail`, `feature`, `branch`, `pr_url`, `resume_conditions`, in that order, each written once, each at line start, each value a double-quoted scalar (the empty value written as an empty pair of double quotes), the whole document exactly eight physical lines | task0001 (states in the SSOT and binds), task0004, task0005 (apply as canonical) |
| SC2 — SSOT section layout | The level-2 heading sequence of `batch-terminal-line.md` | Exactly, in order: `Purpose`, `Result format`, `Escaping`, `Field values`, `Stop reason codes`, `Stop point coverage`, `Consumer constraints`, `No result on a wait turn`, `Responsibility boundary`. `Stop reason codes` must be immediately followed by `Stop point coverage` — an existing guard (`tests/test_failed_kind_batch_docs.py`) slices the document between exactly those two headings, so no heading may be inserted between them | task0001 (writes and binds), task0002 / task0003 (may cite section names in prose only) |
| SC3 — Escaping rule | The canonical character-by-character escaping rule | The canonical mapping is the "Canonical escaping rule" table below. `## Escaping` states it as one Markdown table whose first column names the source character and whose second column gives the emitted escape, followed by prose stating (a) the residual code-point ranges that become a four-digit `\uXXXX` escape and (b) that the rule is applied character by character to the source value and never re-processes a generated escape | task0001 (writes and binds), task0004 (applies as canonical) |
| SC4 — Derivation bullets | Where each derived value's rule is stated | `## Field values` carries one bullet per key of SC1, in SC1's order, each opening with the backticked key name. The `feature`, `branch`, `pr_url` and `resume_conditions` bullets each state their derivation rule and their empty-string case (FR9-FR12), per the "Canonical derivation outcomes" table below | task0001 (writes and binds), task0005 (applies the outcomes as canonical) |
| SC5 — Forbidden-literal set | What a pointer document may never restate | The union of: the field-name token set of SC1 (each key as a bare token in a `key:`-shaped or `key=`-shaped citation), every `state` value, every `step` value including the `no-step` sentinel, every `reason` code including `context_budget_reached` and `none`, and the removed prefix literal of SC6. A pointer document names the SSOT path instead | task0001 (pins the set in `tests/test_batch_stop_contract.py` for `batch-mode.md`), task0002, task0003 (comply, and retarget their own modules' guards to the same set) |
| SC6 — Removed prefix literal | The legacy marker-line prefix | The exact string `EM_WORKFLOW_TERMINAL:` must not occur in ANY file under `em-workflow/` after this change. It survives only as a test-side constant under `tests/`, which the sweep does not walk | task0001 (owns the inverted sweep), task0002, task0003 (must not reintroduce it) |
| SC7 — Audit-item assignment | Which value carries which "## Reporting" item | `detail` carries, in full: every auto-approved command string; every assumption recorded during create-spec/planning; auto-rework rounds consumed (review / verify); every deferred finding with its `stable_id`; every unlisted-gate fallback resolution; every autonomous fail-closed-route resolution; the kept integration branch name together with the take-over guidance. `resume_conditions` carries, in full, the stop-recovery guidance, and only when `state` is `stopped`. A count alone or a pointer alone satisfies neither | task0002 (writes the assignment into `batch-mode.md`'s "## Reporting" and binds it), task0003 (SKILL.md's report instruction cites it), task0005 (applies the item list as canonical) |
| SC8 — Version value | The single bumped em-workflow version | One value, written identically to `em-workflow/.claude-plugin/plugin.json` and to the `name: em-workflow` entry of `.claude-plugin/marketplace.json`. Both currently read `0.1.82`; the new value compares strictly greater under dot-separated numeric comparison. The `em-review` entry is not touched | task0006 only — no other task lists either manifest in its files |
| SC9 — Test-module ownership | Which task edits which test module | Each test module is edited by exactly one task (each task plan's Scope is the register). A task that finds it needs a guard inside another task's module reports the need instead of editing the module | all tasks |

### Canonical escaping rule (SC3)

Applied character by character to the source value, left to right, never
re-processing a character the rule has just generated.

| Source character | Emitted |
|---|---|
| backslash | two backslashes |
| double quote | backslash followed by a double quote |
| CR (U+000D) | backslash followed by `r` |
| LF (U+000A) | backslash followed by `n` |
| TAB (U+0009) | backslash followed by `t` |

Any character NOT covered above that falls in U+0000-U+001F, U+007F-U+009F,
U+2028, U+2029, U+FFFE or U+FFFF becomes a backslash, `u`, and exactly four
lower-case-hex digits. Every other valid Unicode character, including non-BMP
characters, is emitted unchanged.

Because every value is double-quoted, a colon, a leading hyphen or a hash
inside a value needs no special handling, and no physical newline can appear
inside a value (SC1's eight-physical-line invariant).

### Canonical derivation outcomes (SC4)

The ten sites TS4 enumerates, and the value each key takes at that site. "slug"
means the confirmed feature slug; "integration branch" means the integration
branch name built from that slug.

| Site | `feature` | `branch` | `pr_url` | `resume_conditions` |
|---|---|---|---|---|
| Step 0 git-setup abort, no name supplied | empty | empty | empty | non-empty |
| Step 0 git-setup abort, supplied name matches the slug pattern | supplied name | empty | empty | non-empty |
| Step 0 git-setup abort, supplied name fails the slug pattern | empty | empty | empty | non-empty |
| Step A feature-resolution abort | empty | empty | empty | non-empty |
| Integration branch created by this run | slug | integration branch | empty | per `state` |
| Integration branch confirmed existing by this run | slug | integration branch | empty | per `state` |
| Step C keep-branch after worktree removal | slug | integration branch | per outcome | per `state` |
| Step C `--pr` success | slug | integration branch | the created PR's bare URL | empty |
| Step C `--pr` success then a later stop | slug | integration branch | the created PR's bare URL | non-empty |
| Verify cap-reached run | slug | integration branch | per outcome | non-empty |

"per `state`" means FR12's rule: non-empty only when `state` is `stopped`.
The slug pattern is the one FR9 states; a supplied name that does not match it
is never used, and no value is ever guessed from a task description or from an
existing branch.

## Conventions

**Documentation language.** The SSOT and the two `references/` pointer
documents are written in English, matching their current text.
`em-workflow/skills/develop/SKILL.md` stays Japanese, matching its current
text.

**Citation discipline (NFR1).** A pointer document cites the SSOT by its
repository-relative path and states only WHEN the result is emitted and what
else the turn may print. It restates nothing from SC5. Existing guards assert
those absences over the WHOLE file, so a literal reintroduced anywhere in a
pointer document fails the suite — including inside an example or a comment.

**Naming.** The artifact is called "the structured result" (Japanese:
構造化結果) throughout. The words "terminal line" / 終端行 are retired from
every document this change touches, because they name the removed shape. A
section heading that currently says "line" is renamed accordingly (A2).

**Test authoring (NFR4).** Repository convention, unchanged:

- Prefer a durable invariant over a fixed literal wherever the literal would go
  stale; a pure regression guard over deliberately-retained wording is exempt.
- Every NEW matcher carries a negative proof (a forged sample the matcher
  rejects) AND a non-vacuity guard (the same forged sample is otherwise
  well-formed on every point the matcher does not test).
- Assertions read raw file text, so a literal hidden inside a fenced block is
  still seen.
- Modules are discovered by `python3 -m unittest discover -s tests` and, apart
  from the single exception in D6, import the Python standard library only.
  Each new module keeps the repository's stdlib-only self-check.

**Error handling policy.** The only error surface this change touches is the
consumer's rejection of a malformed result (FR14). The SSOT states the rejected
combinations as constraints the emitter must satisfy BEFORE emitting; no retry,
fallback or second shape exists. Absence of a result remains the
abnormal-outcome signal (NFR6) and must never be replaced by an error message a
consumer could mistake for a result.

## Cross-task Design Decisions

### D1 — One SSOT rewrite, three pointer rewrites, disjoint file sets

`batch-terminal-line.md` is rewritten by task0001 alone. `batch-mode.md` by
task0002 alone. `develop/SKILL.md` and `implement-phase.md` by task0003 alone.
The two version manifests by task0006 alone. No two tasks write the same
non-test file, and no two tasks write the same test module (SC9).

*Rationale*: the documents cite each other only by path, so each can be
rewritten against SC1-SC8 without reading the others' new text.
*Affected tasks*: all.

### D2 — Structural guards over the SSOT live in one module

`tests/test_batch_stop_contract.py` remains the single module that asserts
`batch-terminal-line.md`'s own structure (headings, reason-code table, coverage
table, value domains, escaping table, derivation bullets) and `batch-mode.md`'s
literal absence. task0001 owns it end to end, including retargeting its
`CONTRACT_HEADINGS` to SC2 and inverting its prefix sweep to SC6.

*Rationale*: the module's extractors and its forged negative-proof samples are
one interlocking system; splitting it across tasks would duplicate the
extractors. *Affected tasks*: task0001 (owner); task0002 and task0003 comply
with SC5/SC6 and retarget only their own modules.

### D3 — The pointer guards stay where they already live

Each pointer document's retargeted absence guard stays in the module that
already carries it, rather than migrating into one new module:
`batch-mode.md`'s in `tests/test_batch_quiet_output_discipline.py`,
`tests/test_batch_quiet_output_phase_wiring.py` and
`tests/test_batch_quiet_output_audit_persistence.py`; `develop/SKILL.md`'s and
`implement-phase.md`'s in `tests/test_batch_stop_contract_skill_wiring.py`,
`tests/test_batch_quiet_output_skill_wiring.py`,
`tests/test_verify_cap_run_continuation.py`,
`tests/test_failed_kind_stop_condition.py` and
`tests/test_develop_once_option.py`.

*Rationale*: these modules carry per-document pins whose non-vacuity grounding
already references the document they guard; moving them would rewrite passing
guards for no gain. *Affected tasks*: task0002, task0003.

### D4 — New behaviour gets new modules, existing modules are only retargeted

The conformance, derivation and audit-containment scenarios (TS1-TS5, TS9) are
NEW test modules. No existing module grows a conformance responsibility. The
version-bump check (TS10) is a new per-feature module following the
repository's `test_*_version_bump.py` convention, leaving the generic
`tests/test_plugin_version_parity.py` untouched.

*Rationale*: the repository's own history shows per-feature modules keep the
baseline pin honest; folding a new baseline into the generic parity module
would erase the previous feature's baseline. *Affected tasks*: task0004,
task0005, task0006.

### D5 — Canonical values here, one binding assertion per owned file

A conformance test that reads the SSOT directly cannot be green inside its own
worktree, because the SSOT's rewrite lands in a different task's worktree. The
rule for this change:

- SC1, SC3, SC4 and SC7 hold their canonical values in THIS document.
- A guard module owned by the same task as the file it reads asserts the real
  file against those canonical values — that is the "binding" assertion.
  task0001 binds the SSOT (SC1-SC4). task0002 binds `batch-mode.md`'s
  "## Reporting" assignment (SC7).
- A guard module NOT owned by the file's task declares the canonical values
  independently and exercises behaviour against them, never against the file.

Drift is therefore caught at exactly one place per contract, and no task's
suite depends on another task's unmerged edit.

*Rationale*: the failure this feature exists to fix is precisely two documented
shapes drifting with no guard firing; the binding assertion is what keeps a
single guard responsible for each shape. *Affected tasks*: task0001, task0002,
task0004, task0005.

### D6 — Conformance parser: PyYAML, as the single named exception to NFR4

NFR3 requires verification against a real parser and names PyYAML; NFR4 says
test modules import the standard library only. NFR3 is the more specific
requirement for the conformance module, and the more specific requirement wins
there and nowhere else:

- Exactly the conformance modules of task0004 import the YAML parser. Every
  other module, new or edited, stays standard-library-only.
- The import is guarded so an environment without the parser produces a clearly
  labelled skip naming the missing package, never an import error that aborts
  discovery for the whole suite.
- Because a skip would make NFR3 vacuous, VERIFICATION.md records "the
  conformance module ran, with zero skipped tests" as an explicit verification
  item. A skipped conformance run is a FAILED verification item, not a pass.

*Rationale*: the alternative — hand-rolling a YAML reader inside the test —
would verify the change against em-workflow's own reading of YAML, which is
exactly what must not be trusted here. *Affected tasks*: task0004.

### D7 — Size budget versus "in full" (FR14 vs FR17)

FR17 requires every "## Reporting" audit item to appear in full inside a value;
FR14 caps the whole document at 64 KiB UTF-8. The SSOT states the cap as a hard
emitter-side constraint AND states that nothing may be dropped, summarized,
replaced by a count, or replaced by a pointer in order to satisfy it. The audit
items are bounded in practice (short command strings, assumption lines, two
small counters, finding ids, one branch name). If a run ever cannot satisfy
both, that is a reportable condition for the run, never a licence to truncate;
the SSOT says so explicitly so the emitter has no silent third option.

*Rationale*: leaving the interaction unstated would let an emitter invent
truncation, breaking the consumer's audit surface with no signal.
*Affected tasks*: task0001 (states it), task0002 (must not weaken
"## Reporting" into a pointer list), task0005 (asserts a pointer/count sample
is rejected).

### D8 — `context_budget_reached` is documented, never emitted

The `reason` value domain documents twelve values; the Stop point coverage
table keeps eleven rows binding eleven codes. The twelfth,
`context_budget_reached`, is reserved by the consumer and never emitted by
em-workflow. The SSOT states this as a single, named, explicitly-scoped
exception to the "every code has exactly one stop point" symmetry — scoped to
exactly this one code — so a future reader does not read the asymmetry as an
omission and "fix" it by inventing a stop point.

*Rationale*: the coverage table's bidirectional guard would otherwise have to
be weakened, losing its ability to detect a genuinely uncovered stop point.
*Affected tasks*: task0001.

### D9 — The version bump is a patch bump, owned by one task

`0.1.82` → the next patch version, written to both manifests by task0006 only.
Removing the legacy line changes what an external consumer must parse, which
argues for a larger bump; the repository rule requires only that the two
manifests agree, and the repository's convention is patch-by-default (A6).
Patch is chosen so the bump matches every other document-level change in this
repository's history; the reasoning is recorded here rather than relitigated
inside the task.

*Rationale*: a single owning task avoids two tasks conflicting on the same two
JSON files. *Affected tasks*: task0006 (owner); all others must not edit either
manifest.

### D10 — Other features' `feature-docs/**` are historical records

Occurrences of the removed prefix and of the four-field shape inside OTHER
features' `feature-docs/**` and `test-docs/**` artifacts are per-feature
history, not live contract, and are not rewritten (A3). The sweep of SC6 walks
`em-workflow/` only, so those occurrences neither fail it nor need an
allowlist.

*Rationale*: rewriting historical feature records would falsify the audit trail
of past runs. *Affected tasks*: task0001 (sweep scope); all others leave other
features' documents alone.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A conformance module silently skips because the YAML parser is absent, making NFR3 vacuous | medium | high | D6: the skip is labelled, and VERIFICATION.md treats a skipped conformance run as a failed item, not a pass |
| A pointer document reintroduces a forbidden literal while being rewritten | medium | medium | SC5 plus whole-file absence guards in three separate modules; failures surface in the same suite run |
| A conformance module's canonical copy of the escaping rule drifts from the SSOT's table | medium | high | D5: task0001's binding assertion compares the SSOT's extracted table against the same canonical set, so drift fails at exactly one place |
| `detail` assembled "in full" exceeds the 64 KiB document bound | low | medium | D7: the SSOT states the interaction explicitly and forbids silent truncation |
| Two tasks edit the same JSON manifest and conflict | low | medium | D9 plus SC8: task0006 is the only task whose files contain either manifest |
| A heading inserted between `Stop reason codes` and `Stop point coverage` breaks an existing, unrelated guard | low | medium | SC2 states the adjacency constraint as part of the heading contract |
| Renaming "terminal line" / 終端行 wording breaks a Japanese-language pin in a module this change does not open | medium | medium | task0003's scope lists every module carrying such a pin; the whole-suite run (TS11) is the backstop |

## Open Questions

- [ ] Is PyYAML present in the environment where the verify phase runs the
      suite? If not, NFR3's conformance cannot be demonstrated and D6's
      verification item fails rather than passing by skip.
- [ ] FR14's 64 KiB bound and FR17's "in full" rule can in principle conflict
      for a run with an unusually large audit set. D7 fixes the precedence
      (never truncate) but does not define what the run should do instead;
      this is deliberately left to a follow-up if it is ever observed.
- [ ] FR15 requires the `reason` domain to document twelve values while the
      coverage table binds eleven. The twelfth value's spelling is taken from
      the consumer's documented domain (`context_budget_reached`); nothing in
      this repository can verify that spelling against the consumer.
