# Implementation Plan: large-diff-review-coverage

## Overview

The review phase stops counting a perspective as clean when its reviewer timed
out, returned non-JSON output, returned a fixed litellm empty result, or skipped
on oversized input. em-workflow measures the review input, splits it into
file-level shards above 200,000 characters, caps dispatches per pass, and records
unreviewed and partially reviewed perspectives; em-review takes only the
codex-reviewer skip handling.

## Technology Stack

- **Language**: Python 3, standard library only, for two new scripts under
  `em-workflow/scripts/`.
- **Tests**: standard library `unittest`, discovered from `tests/`.
- **Documents**: Markdown protocol, reference and agent files of em-workflow and
  em-review.
- **Dependencies**: none new, so no license record applies.

## Layer Structure

| Layer | Files | Responsibility | Depends on |
|---|---|---|---|
| Orchestrator protocol | `em-workflow/references/review-phase.md`, `em-workflow/references/batch-mode.md` | When to measure, split, dispatch, classify, compute coverage, record and report | The two scripts through their contracts below; reviewers through the unchanged input block |
| Scripts | `em-workflow/scripts/review-shards.py`, `em-workflow/scripts/review-coverage.py` | Deterministic measurement, splitting and cap; result classification and coverage | `git`, read-only, for review-shards only |
| Reviewers | `codex-reviewer.md` and `review-protocol.md` of both plugins | One result or skip object per run | Nothing above |
| Evaluator | `em-workflow/references/review-evaluation-contract.md`, `em-workflow/agents/review-evaluator.md` | Uses both coverage fields for its inspection duty | The values the orchestrator passes in its input block |

Dependencies point from the protocol to the scripts, the reviewers and the
evaluator only. A script reads nothing but its input document and, for
review-shards, the reviewed tree.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| review-shards.py | Measure per-file review input, split into shards, apply the cap | Pre: one argument, the path of a UTF-8 JSON input document with exactly the keys `project_root` (absolute path of the reviewed tree), `review_mode` (`diff` or `whole-codebase`), `diff_base` (`HEAD` or a 40-hex commit id in diff mode; null in whole-codebase mode), `changed_files` (project-relative paths, no duplicates), `perspective_count` (integer 1 to 24, D4). Post, exit 0: a JSON object on stdout with exactly the keys `limit`, `total_chars`, `split`, `files`, `shards`, `shard_cap`, `dispatched_shards`, `excess_shards` (D2). Post, exit 2: a message on stderr and nothing on stdout | task0002 (builds), task0004 (Phase R2 use), task0005 (Phase R4 use) |
| review-coverage.py `classify_results` | Decide completed or failed for schema-valid, non-skipped results | Pre: `operation` is `classify_results`; `results` is a list of objects with `run_id`, `origin` (`codex`, `litellm` or `claude`, the harness the orchestrator recorded at dispatch), `finding_count` (integer, 0 or more) and `summary` (string). Post, exit 0: `results`, a list of objects with `run_id` and `status` in input order; `status` is `failed` exactly under D6, else `completed`. Post, exit 2: invalid input | task0003 (builds), task0004 (Phase R2b use) |
| review-coverage.py `coverage` | Compute both coverage fields | Pre: `operation` is `coverage`; `perspectives` (the Task-dispatched perspectives of the round, in dispatch order); `passes` (D3); `perspective_runs` (rows with `run_id`, `perspective`, `role`, `status`, `source`, as recorded). Post, exit 0: exactly `unreviewed_perspectives` and `partially_reviewed_perspectives` (D5). Post, exit 2: invalid input, a malformed or duplicate run_id, or a run that does not fit its pass manifest | task0003 (builds), task0005 (Phase R4 passes, Phase R5 record), task0006 (Phase R3a input) |
| run_id | Name every Task-dispatched run uniquely within a round | D1 | task0003 (parses), task0004 (Phase R2 / R2b), task0005 (Phase R4, Phase R5 example) |
| Coverage fields of the round record | Disclose unreviewed and partially reviewed perspectives | Root `unreviewed_perspectives`: perspective names. Root `partially_reviewed_perspectives`: entries with `perspective`, `unreviewed_files` and `reason`. Both present and empty when there are none. Values are copied from the `coverage` output, never derived by hand | task0003 (produces), task0005 (persists), task0006 (Phase R3a, Phase R6, batch reporting) |
| Retryable skip_reason sets | Say which skips advance the chain walk | D7 | task0001 (review protocols), task0004 (Phase R2b table, README) |
| Spec rescue run | Shard-level spec runs after the full-diff path failed | D8 | task0003 (`spec_rescue`), task0004 (dispatch), task0005 (findings rule) |
| Section and test-pin ownership | Keep parallel edits of shared files apart | D10 | all tasks |

## Conventions

- **Script interface**: the same shape as `em-workflow/scripts/self-write-digest.py`.
  One argument, the input document path. The input is a JSON object. Output is a
  JSON object on stdout, UTF-8, non-ASCII characters unescaped, stable key order.
  Exit 0 on success. Exit 2 on a usage error, invalid input or failure, with the
  message on stderr and nothing on stdout. Standard library only.
- **Paths**: every path in a script input, a script output or a coverage field is
  project-relative and `/`-separated. A script rejects an absolute path, a `..`
  segment, NUL, CR, LF or a leading `-` in any path with exit 2.
- **Invocation**: the orchestrator writes the input document with its
  file-writing tool into the session scratchpad directory, outside
  `project_root`. It never assembles the document through shell interpolation,
  and no path taken from the document appears on the command line. It runs the
  script with `python3` from the plugin's `scripts/` directory and reads only the
  JSON output. It never reads diff text to measure size (NFR3).
- **Fixed values**: the 200,000-character limit and the 24-dispatch cap are
  constants of review-shards.py. review-phase.md states them as the values the
  script applies.
- **Failure handling**: D9.
- **Tests**: standard library `unittest` only. A script is loaded by file path,
  the way existing tests load scripts. Shell-related behavior runs in a
  disposable git repository in a temporary directory. No network. No test
  creates load for its own sake: large inputs are a few files of a few hundred
  thousand characters. A new text-inspection test pins phrases over
  whitespace-normalized text, includes a negative proof (a forged text the
  matcher rejects), and adds no whole-section digest over `review-phase.md`.
- **Redaction**: documents, records and tests hold no absolute path under a home
  directory and no Notion URL (`em-workflow/references/doc-redaction.md`).

## Cross-task Design Decisions

### D1: run_id grammar

The format is `{perspective}[@s{k}]#[loop{N}.]{chain_index|fallback}`.

- `@s{k}` is present only for a run in a split pass; `k` is the shard index from
  review-shards, starting at 1. A spec run carries it only as a rescue run (D8).
- `loop{N}.` is present only for Phase R4 loop N, N starting at 1.
- The last segment is the chain index (integer, 0 or more) of the dispatched
  chain entry, or `fallback` for the Claude fallback.
- `vulnerability#tool` and `evaluator` are unchanged. An unsplit Phase R2 run
  keeps `{perspective}#{chain_index}` or `{perspective}#fallback` (NFR1). The old
  Phase R4 form `{perspective}#loop{N}` is replaced.
- Examples: `security#0`, `performance@s2#1`, `spec@s1#fallback`,
  `architecture@s3#loop1.0`, `comprehensive#loop2.fallback`.

Affected tasks: task0003, task0004, task0005.

### D2: Measurement, shards and cap

- **Measurement, diff mode**: per file, the character count of that file's diff
  text against `diff_base`. Pathspecs are literal, and external diff, text
  conversion and color are off. When that diff text is empty (an untracked file,
  or no textual change), the file content is counted instead. In a repository
  with no commit yet and `diff_base` `HEAD`, every file is counted by content.
- **Measurement, whole-codebase mode**: content only; `git` is not run.
- Characters are counted after decoding as UTF-8 with invalid bytes replaced.
- Every path is first checked with the Phase R0 step 3 rules: a regular file,
  not a symlink, inside `project_root`. A violation exits 2 before any read.
- **Split**: when the total exceeds 200,000, files are ordered by path code
  point and filled next-fit into shards of at most 200,000 characters. A file
  over 200,000 forms its own shard. Shard indexes start at 1. When the total is
  200,000 or less, `split` is false and one shard (index 1) holds every path.
- **Cap**: `shard_cap` is floor(24 / `perspective_count`). `dispatched_shards`
  are the existing indexes 1 to `shard_cap`, and `excess_shards` are the rest,
  which are the shards at the end of the path order (A11).
- `files` lists `path` and `chars` in path order; `shards` lists `index`,
  `paths` and `chars`; `limit` is 200,000.

Affected tasks: task0002, task0004, task0005.

### D3: Coverage passes

A pass is one fan-out of reviewers over one manifest. Loop 0 is Phase R2 with
its Phase R2b walks; loop N is the re-review of Phase R4 loop N. Each entry of
`passes` carries `loop`, `fixed_files` (files the fix of that loop changed;
empty for loop 0) and `manifest` (the review-shards output of that pass,
verbatim). A run belongs to the pass named by its run_id's loop part. The
coverage universe is the file list of the last pass.

Affected tasks: task0003, task0004, task0005.

### D4: Selected perspective count

`perspective_count` is the number of perspectives Phase R2 dispatches through
Task this round. spec counts when it is dispatched. A `requires_spec`
perspective skipped for lack of a SPEC and axis 2 `vulnerability` do not count
(A10). Per pass, each non-spec perspective has at most `shard_cap` primary
dispatches and spec has one (the full diff), so the total stays at or below 24.
Chain-walk retries, Claude fallbacks and spec rescue runs are not primary
dispatches (FR7, D8).

Affected tasks: task0002, task0004, task0005.

### D5: Coverage determination

- Rows with `role: evaluator` or `source: tool` are ignored.
- Rows are grouped by perspective, shard and loop. The last row of a group, in
  `perspective_runs` order, decides the group (FR9).
- A run without `@s` covers every file of its pass manifest. A run with `@s{k}`
  covers shard k of its pass.
- A file's last change loop is the highest loop whose `fixed_files` holds it, or
  0. A perspective-file pair is reviewed when a group ending `completed` covers
  the file in a pass whose loop is at or above the file's last change loop
  (FR14).
- `unreviewed_perspectives`: each listed perspective with no group ending
  `completed`, or with a non-empty universe and no reviewed file (FR4).
- `partially_reviewed_perspectives`: each other perspective with at least one
  unreviewed file or with a spec rescue run (D8). An entry holds `perspective`,
  `unreviewed_files` (sorted) and `reason`.
- `reason` joins the tokens that apply with `,` and no space, in this order:
  `changed_after_review` (the file was covered only before its last change),
  `shard_cap_exceeded` (the file is in an excess shard of a pass at or after its
  last change), `run_not_completed` (the file is in a dispatched unit whose group
  did not end `completed`), `spec_rescue` (spec ran rescue runs this round).
- Both lists follow the order of `perspectives`.

Affected tasks: task0003, task0005, task0006.

### D6: litellm empty-result rule

A result is `failed` exactly when its origin is `litellm`, its findings count is
0, and its summary is byte-identical to `litellm model output truncated` or
`litellm returned non-JSON output`. The origin is the harness the orchestrator
recorded at dispatch, never the result's own `source`. A failed result gets no
`skip_reason` (A9) and takes the existing malformed-result path: `status:
failed` and one Claude fallback.

Affected tasks: task0003, task0004.

### D7: Retryable skip_reason sets per plugin

- em-workflow: `rate_limited`, `budget_exhausted`, `harness_unavailable` and
  `review_data_too_large`. `review_data_too_large` advances to the next entry of
  a different harness; an exhausted chain gets the existing Claude fallback.
  `scratchpad_unavailable` and every other value stay non-retryable.
- em-review: the three values are unchanged, and `review_data_too_large` stays
  non-retryable (FR17).
- In both plugins a Codex timeout (wrapper exit 124) and Codex non-JSON output
  are `harness_unavailable` skips.

Affected tasks: task0001, task0004.

### D8: Spec order and rescue runs

spec is never split. It runs its normal chain on the full diff: the front
entry, the Phase R2b walk, then the Claude fallback. Only when that whole path
ends with no completed run and the pass is split does spec get rescue runs: one
per dispatched shard, at most `shard_cap`, with run_id `spec@s{k}#...`, each with
the per-shard walk and Claude fallback. Rescue runs are spec retries, not
primary dispatches. An unsplit pass never has rescue runs (NFR1). Once spec has
a rescue run in a round, it is disclosed as partial with `spec_rescue` for that
round, even when every rescue shard completes and even when a later pass's
full-diff run completes.

A missing-implementation finding (A8) of a rescue run is recorded with
`resolution: unresolved` and a `resolution_reason` beginning `unverified`. It is
excluded from auto-fix candidates and from the residual critical/high count. The
same handling applies on the evaluator path, the evaluator-failure degradation
and Phase R4 re-review (FR12).

Affected tasks: task0003, task0004, task0005.

### D9: Script failure handling

- review-shards exits non-zero: the review phase aborts loudly before any
  dispatch of that pass, as the Phase R0 fail-closed aborts do. No round record
  is written.
- `classify_results` exits non-zero: every result of that call counts as failed
  and takes the malformed-result path.
- `coverage` exits non-zero: the review phase aborts before the round record is
  written. A round record without both coverage fields is never written.
- None of these adds a question or a gate identifier.

Affected tasks: task0003, task0004, task0005, task0006.

### D10: Section and test-pin ownership

- `em-workflow/references/review-phase.md`: task0004 edits Phase R2 and Phase
  R2b; task0005 edits Phase R3b, Phase R4 and Phase R5; task0006 edits Phase R3a
  and Phase R6. An edit outside the owned sections is a reported deviation.
- `tests/test_reviewer_roles_protocol.py` and
  `tests/test_reproduction_reviewer_instructions.py`: task0001.
- `tests/test_review_phase_llm_led.py`: task0004 updates the Phase R2b
  routing-table test; task0005 updates the Phase R5 disclosure test.
- batch-mode tests: task0006.
- New test modules, one per task: `tests/test_codex_reviewer_skip_handling.py`
  (task0001), `tests/test_review_shards.py` (task0002),
  `tests/test_review_coverage.py` (task0003),
  `tests/test_review_phase_shard_dispatch.py` (task0004),
  `tests/test_review_phase_coverage_record.py` (task0005),
  `tests/test_review_coverage_disclosure.py` (task0006).
- A pin is updated only when its pinned text is the text this feature changes.

Affected tasks: all.

### D11: Where the coverage fields surface

The Phase R3a input carries both fields, computed over the loop-0 pass right
after Phase R2b. Phase R5 records the final values, computed after the last
Phase R4 pass. Phase R6 and the batch final result render them from the round
record. Only `unreviewed_perspectives` is exempt from the evaluator's
Independent Inspection Duty (FR16). The completion gate stays
`residual_critical_high == 0`, and no gate is added (FR15).

Affected tasks: task0005, task0006.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Three tasks edit `review-phase.md` in parallel and conflict | High | Medium | D10 section ownership; the parent-side adoption protocol resolves merge conflicts |
| A single file over 200,000 characters still exceeds the litellm model | Medium | Medium | `review_data_too_large` walks to Codex; a shard that never completes is disclosed |
| Codex still times out on a 200,000-character shard (A12) | Medium | Medium | The timeout is a `harness_unavailable` skip and walks the chain; disclosure if nothing completes |
| A design issue spanning shards is missed (A13) | Medium | Low | Known constraint; the investigation budget stays at 3 files |
| A pin update weakens an existing check | Low | Medium | D10; new tests carry negative proofs |

## Open Questions

- [ ] None blocking. The planning assumptions are listed in the completion
  report.
