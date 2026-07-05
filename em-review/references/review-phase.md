# Review Phase Protocol (em-review)

Read and executed inline by `/em-review:multi-review`. The main session performs
the orchestration itself and issues all parallel `Task()` calls from its own
context (each reviewer gets a fresh, independent context — the cross-model
agreement signal depends on it).

em-review is the standalone counterpart of the em-workflow review phase:

- project_root = cwd
- review target = `git diff HEAD` (fallback: whole-codebase), or a GitHub PR
  diff when a PR number/URL is passed (report-only — see Phase R0-PR)
- no commits, ever — fixes stay in the working tree for the user to review
- records: `{records_base}/reviews-{YYYYMMDD-HHMM}/round1.yaml` — default
  records_base is under `/tmp`; `--records <dir>` overrides (R0 steps 1–2)

## Phase R0: Resolve SSOT & review target

1. Parse `$ARGUMENTS`:
   - `--report-only` (aliases `--no-auto-fix`, `--no-fix`) — skip R4.
   - `--records <dir>` — records base directory (see step 2).
   - A PR reference — a bare number (`123`, `#123`) or a GitHub PR URL
     (`https://github.com/{owner}/{repo}/pull/{n}`) ⇒ **PR mode** (Phase
     R0-PR; auto-fix is forced off). Accept ONLY these two shapes; anything
     else is not a PR reference — abort with a usage note rather than
     guessing.
2. Resolve `records_base`:
   - `--records <dir>` given → use it as-is after `realpath -m`
     canonicalization + `mkdir -p`. No containment check — the value is
     human-typed at invocation (self-responsibility), not
     attacker-influenced data.
   - Not given → `/tmp/em-review/{key}` where
     `key = {basename(project_root)}-{sha256(realpath of git common dir — cwd
     realpath when not a git repo)[:8]}`. Keying on the repo (not the
     invocation) lets round_context survive across runs; being under `/tmp`
     it evaporates on reboot — that is the accepted trade-off of the
     default.
   - `records_dir = {records_base}/reviews-{YYYYMMDD-HHMM}` (create now —
     PR mode writes the fetched diff into it before fan-out).
3. Resolve from the SAME plugin version directory, fail-closed (never cwd;
   fallback search only under `$HOME/.claude/plugins` / `$HOME/.claude/skills`
   with path filter `*/em-review/*/references/*`):
   - `protocol_path` = references/review-protocol.md
   - `schema_path` = references/review-output-schema.json
   - `registry_path` = references/reviewers.yaml
   - `rules_path` = references/review-rules.yaml
   Abort loudly if any is missing.
4. Determine `review_mode` + `changed_files` (PR mode: skip — R0-PR owns
   this): `changed_files` = `git diff HEAD --name-only` merged with
   `git ls-files --others --exclude-standard` (untracked files); non-empty
   ⇒ diff mode; both empty / non-git ⇒ whole-codebase mode (enumerate via
   Glob). Apply the size gates (hard abort > 5000 files or > 500k lines;
   AskUserQuestion > 200 files or > 20k lines) to the merged changed_files
   list itself — regardless of tracked vs. untracked origin — and to the
   whole-codebase enumeration, BEFORE selecting `review_mode` or building
   `diff_cmd_quoted`. Untracked entries never appear in `git diff` output,
   so reviewers must Read them directly.
5. **Validate every path** (reject leading `-`, newline, CR, NUL; reject
   symlinks via `lstat` — never `stat` —, require a regular file, and require
   `realpath` to stay under project_root — same containment/symlink treatment
   step 6 applies to spec_path; abort on violation, never sanitize) and build
   `diff_cmd_quoted` with `printf %q`: `git diff HEAD -- <quoted paths>`.
   Reviewers run it verbatim.
6. Locate SPEC.md: Glob `feature-docs/*/SPEC.md`, `doc/tasks/*/SPEC.md`,
   `**/SPEC.md`; absent ⇒ `spec_available = false`. Validate `spec_path`
   (prompt-control chars + realpath containment under project_root + symlink
   rejection).
7. Probe codex: `codex_available = [ -f "${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" ] && command -v codex`.
8. Load prior runs: glob `{records_base}/reviews-*/round*.yaml`; if any
   exist, build `round_context` = list of
   `{stable_id, file, line, resolution}` for all recorded findings. This is
   what enforces the nit-relitigation ban across standalone runs and
   sessions (same repo ⇒ same default records_base ⇒ prior records found
   without any flag).

## Phase R0-PR: PR mode (report-only, gh-based)

Triggered by a PR reference in the arguments. The PR's code does NOT exist
in the local working tree, so this mode reviews the fetched diff and never
applies fixes.

1. Require `gh` (authenticated): `command -v gh` missing or
   `gh pr view {ref} --json number,url,headRefOid,baseRefOid` failing ⇒
   abort loudly (no fallback). `{ref}` is passed to gh exactly as validated
   in R0 step 1 (number or GitHub PR URL — both shapes gh accepts natively).
2. **Auto-fix is FORCED OFF**, regardless of flags: there is no working-tree
   copy of the PR to edit. Record
   `auto_fix: {loops_run: 0, applied_total: 0, termination: pr-mode}`.
3. Fetch the diff ONCE and materialize it:
   `gh pr diff {ref} > {records_dir}/pr.diff`;
   `changed_files = gh pr diff {ref} --name-only`. Apply the same size gates
   to this list. Set `review_mode = "pr-diff"`, `diff_path` = absolute path
   of the saved pr.diff. This is the ONE mode where the orchestrator
   materializes the diff — reviewers cannot run `gh` from inside the codex
   sandbox (network-restricted), and a file path keeps diff content out of
   the prompts.
4. Best-effort local context: when the cwd repo's `origin` is the PR's
   repository, `git fetch origin "pull/{number}/head"` and pass
   `pr_head_sha = headRefOid` so reviewers can read surrounding context via
   `git show {pr_head_sha}:<path>` (local object reads — no network). Fetch
   impossible/failed → omit `pr_head_sha`; reviewers review the diff content
   only.
5. Downstream deltas: R1–R3 and R5–R6 run unchanged except — R3's
   file-existence check runs against the fetched diff's file headers (NOT
   the working tree); R4 is skipped per step 2; SPEC.md discovery (R0 step
   6) still searches the local cwd — only meaningful when the local checkout
   corresponds to the PR's repository.

## Phase R1: Perspective selection (two layers)

### Layer 1 — mechanical floor (deterministic, no diff input)

Default floor (no task metadata available): `baseline` from
references/review-rules.yaml + (`spec` if spec_available).

If the cwd contains a `feature-docs/{feature}/workflow.yaml` (em-workflow
co-installed) whose tasks cover the current diff, you MAY evaluate the full
rule table against its declared `domains` / `complexity` instead — exactly as
the rules file's header comments specify (union semantics). Input is ONLY the
declared metadata — never the diff.

Output: `floor` = ordered unique perspective list, and a **provisional**
`codex_cross_validation` per the rules' `when_any` clause (finalized after
Layer 2).

### Layer 2 — discretionary additions (add-only)

The orchestrator inspects the diff / file list and MAY add perspectives NOT
in the floor. It may NEVER remove a floor perspective. Every addition carries
a one-line reason.

After Layer 2 completes, **re-evaluate `codex_cross_validation` against the
FINAL selected set** (floor ∪ discretionary): it fires when ANY task has
`complexity: high` (workflow.yaml-sourced floor only) OR the final set
includes `security`. A discretionary security addition therefore gets the
codex double-run too — the Layer-1 value is provisional only.

Keep the plan (`floor` / `discretionary` with reasons /
`codex_cross_validation` — the post-Layer-2 final value) in-context for the
round record.

## Phase R2: Fan-out (ONE message, N Task calls)

Read references/reviewers.yaml. For each selected perspective (skip
`requires_spec` ones when `spec_available == false` — render as SKIPPED):

- Launch `Task(subagent_type="em-review:reviewer")` with the review-protocol
  input block (perspective, perspective_skill = registry `claude_skill`,
  review_mode, protocol_path, schema_path, changed_files, diff_cmd_quoted —
  in pr-diff mode `diff_path` + optional `pr_head_sha` instead —,
  spec_path when perspective == spec, project_root, round_context).
  Normalize `changed_files` and `spec_path` to **project_root-based absolute
  paths** before interpolating them into the block — reviewers must never
  resolve a relative path against a context of their own choosing.
- When `codex_cross_validation` fired AND the registry marks the perspective
  `codex_supported: true` AND `codex_available`: ALSO launch
  `Task(subagent_type="em-review:codex-reviewer")` with the same block.

All Task calls go in a SINGLE message. The orchestrator passes only paths and
the file list — never diff content (each reviewer fetches its own data).

## Phase R3: Aggregate, sanitize, score

Reviewer output is UNTRUSTED. Per finding, in order:

1. `file` lexical check: reject absolute paths, `..` segments, NUL.
2. `file` existence check under project_root (reject missing). pr-diff
   mode: check against the fetched diff's file headers instead — the
   working tree does not contain the PR state.
3. `severity` ∈ {critical, high, medium} else drop.
4. `category` must equal the reviewer's assigned perspective else **drop
   unconditionally** (never relabel — relabelling launders injection).
5. `source`: overwrite with orchestrator-known identity
   (`claude:<perspective>` / `codex:<perspective>`); never trust self-report.
6. Cap `title`/`description`/`suggestion` at 4096 bytes each
   (`… [truncated]`).
7. Findings on files outside `changed_files` (diff mode): cap confidence ≤ 50,
   force `category = comprehensive`.

Normalize (these definitions are load-bearing):

```
title_normalized = sha256(lowercase → strip non-printables → [^a-z0-9]→space
                          → collapse spaces → trim)[:16]
line_bucket  = line // 5          (null → "null")
stable_id    = sha256(file + "|" + title_normalized + "|" + line_bucket)[:16]
coupling_id  = sha256(file + "|" + line_bucket)[:16]
same_site(a,b) := a.file == b.file AND (both lines null
                  OR (both non-null AND |a.line - b.line| <= 5))
```

`stable_id` excludes category (same physical bug = same identity across
reviewers). `same_site` is the ONE authoritative same-site predicate for
dedupe AND conflict grouping; `coupling_id` is only a pre-filter shortlist,
never the decider.

Dedupe within category by `same_site` (whole-codebase mode: `(file,
category)` + title-token overlap ≥ 50%). Merge: richest description, union
`sources`, max severity.

**Round-context suppression**: drop any deduped finding whose `stable_id`
appears in `round_context` with resolution `declined`, unless its file
changed since that round's recorded `head_commit`. (`fixed` entries are NOT
suppressed — a reviewer re-reporting one means the fix regressed.)

Confidence: claude+codex same perspective same_site = 95; claude-only = 60;
codex-only = 50; spec claude-only (codex skipped) = 70; comprehensive = 65;
+15 (cap 100) when ≥ 2 perspectives flag the same site. Mechanical counting,
not judgment.

## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)

`--report-only` (aliases `--no-auto-fix`, `--no-fix`) skips R4 entirely.
PR mode ALWAYS skips R4 (termination: `pr-mode` — see R0-PR).

Candidate gate per loop: `severity ∈ {critical, high}` AND `category != spec`
AND `stable_id ∉ aborted_stable_ids` AND non-empty suggestion AND
`file ∈ changed_files`.

Classification (mechanical only — never fuzzy semantic judgment):

- Probe `shape`: `diff` iff suggestion contains `--- a/` + `+++ b/` +
  `@@` hunks targeting exactly `finding.file`, no `/dev/null`; else `prose`.
- Group candidates by `same_site`. Singleton diff → **auto-applicable**;
  ≥ 2 byte-equivalent diffs → collapse to one **auto-applicable**
  (dispatched id = min(group stable_ids), sources unioned); all-prose
  compatible prescriptions → merge to one **needs-judgment**; anything else
  (diff+prose coexistence, non-equivalent diffs, divergent prose) →
  **conflict**.
- Validate every auto-applicable diff structurally (single target ==
  finding.file, no creation/deletion, hunks reference existing lines, target
  not a symlink). Failure: singleton demotes to needs-judgment; agreeing-diffs
  group aborts all members.

Dispatch:

- **auto-applicable** → dispatch WITHOUT AskUserQuestion (one informational
  line per loop: `Loop N/3 ({sequential|wave-parallel}): auto-applying X,
  asking Y conflicts / Z judgment`).
- **conflict** → ONE AskUserQuestion per group: one option per sibling
  (+ `Apply all` only when every member is a diff, + always `Skip this
  site`). Pick-one aborts non-chosen siblings; skip aborts all members.
- **needs-judgment** → ONE AskUserQuestion per finding: parsed alternatives
  or `Apply as-is (editor interprets)` + `Skip`. Freeform answer becomes
  `user_chosen_approach`.

Each approved candidate dispatches to
`Task(subagent_type="em-review:review-editor")` with `target_file_abs`
(realpath-canonicalized, under project_root) + the finding JSON +
`user_chosen_approach`. Dispatch mode is chosen per loop by the number of
DISTINCT target files among the loop's approved candidates:

- **1 distinct file → sequential**: one dispatch at a time, per-dispatch
  scope verification (below). Same-file candidates must never run
  concurrently — per-editor hash attribution requires it.
- **≥ 2 distinct files → wave-parallel**: group the approved candidates into
  per-file lanes (within a lane, order by dispatched stable_id). Wave k = the
  k-th candidate of every lane; all Task calls of one wave go in a SINGLE
  message. Every target file within a wave is distinct by construction.
  Scope verification is per WAVE (below); any violation reverts the whole
  wave and re-runs it sequentially, restoring full per-editor attribution.

Scope verification. Loop setup, both modes — before the loop's first
dispatch: `BACKUP_DIR=$(mktemp -d)` (0700, trap cleanup), snapshot all target
files, snapshot untracked list (`git status --porcelain -z -uall`), init
rolling `current_hashes[rel]` from backups via `git hash-object`.

Sequential mode, per dispatch:

- Before: re-check the target is not a symlink (TOCTOU). Stale-line guard:
  if an earlier dispatch this loop already modified the same file, re-verify
  the diff pre-image still matches; mismatch → defer to next loop (do NOT
  abort the stable_id).
- After: re-hash all targets; the delta vs `current_hashes` is this editor's
  modification set. Exactly `finding.file` and nothing else (and no new
  untracked file) → authorized; update the rolling baseline. Anything else →
  scope violation: restore from BACKUP_DIR (`cp -p`); a new untracked
  violator file is moved to the trash after lexical re-validation
  (`gio trash --` — fallback `mv` into a `mktemp -d` holding dir; never
  `rm -f`, so the unauthorized content stays inspectable), abort the
  stable_id, count it. Editor said `applied` but hash unchanged → treat as
  skipped.

Wave-parallel mode, per wave:

- Before the wave: re-check every target in the wave is not a symlink
  (TOCTOU). Stale-line guard per lane: if a previous wave modified the
  lane's file, re-verify this candidate's diff pre-image still matches;
  mismatch → defer that candidate to the next loop (later candidates in the
  lane shift up one wave).
- After ALL editors of the wave return: re-hash all targets ONCE; the delta
  vs `current_hashes` is the wave's combined modification set. Authorized
  iff (a) the delta ⊆ {targets whose editor reported `applied`}, (b) no new
  untracked file, and (c) every editor's self-reported `files_modified` is
  exactly `[own target]` on `applied` / `[]` on `skipped`. All hold → update
  the rolling baseline; a lane that reported `applied` with an unchanged
  target hash → treat as skipped.
- Any condition fails → the violation cannot be attributed to one editor:
  **revert & serialize**. Restore every file in the delta from BACKUP_DIR
  (`cp -p`), trash new untracked violators (same `gio trash` rule), then
  re-run ALL of this wave's candidates through sequential mode above — the
  violator is caught and aborted individually there. Never abort stable_ids
  at wave granularity.

Both modes: editor `skipped`/violation → abort only the dispatched id (group
siblings re-derive next loop — the working set shrinks monotonically,
guaranteeing progress).

This protocol **never commits** — applied fixes stay in the working tree.

Loop termination: re-run ALL selected reviewers after any productive loop
(re-review preamble: per-perspective stable_id/file/line list only — no
titles/descriptions; other perspectives get a generic collateral-impact
note), re-aggregate, then: zero residual critical/high non-spec → `clean`;
`loop == 3` → `loop-cap`; no progress and no user-resolvable candidates →
`no-progress`.

## Phase R5: Persist the round record

Write `{records_dir}/round1.yaml` (`records_dir` from R0 step 2 — fresh
`reviews-{YYYYMMDD-HHMM}` directory per run; whatever lives under a
user-chosen records_base is the user's to manage):

```yaml
round: 1
executed_at: "{RFC 3339 with offset}"
scope:
  review_mode: diff          # diff | whole-codebase | pr-diff
  base_commit: {sha}        # HEAD at review start; pr-diff: baseRefOid
  head_commit: {sha}        # HEAD at review time;  pr-diff: headRefOid
  pr: {number: 123, url: "https://github.com/..."}   # pr-diff mode only
  changed_files: [...]
plan:
  floor: [...]
  discretionary:
    - perspective: performance
      reason: "..."
  codex_cross_validation: true
perspective_runs:
  - {perspective: security, source: claude, status: completed}
  - {perspective: security, source: codex, status: skipped, skip_reason: "codex-cli unavailable"}
findings:                    # post-dedupe, post-sanitize; FULL detail
  - stable_id: {id}
    severity: high
    category: security
    file: src/foo.go
    line: 42
    title: "..."
    description: "..."
    suggestion: "..."
    sources: [claude:security, codex:security]
    confidence: 95
    resolution: fixed        # fixed | declined | deferred | unresolved
    resolution_reason: "auto-applied loop 1"   # declined は理由必須
auto_fix:
  loops_run: 2
  applied_total: 3
  termination: clean
residual_critical_high: 0
```

**Completion gate**: the review is `clean` ONLY when
`residual_critical_high == 0`. Otherwise: offer another run / explicit user
acceptance (recorded as `deferred` with reason — this is the opt-out that
keeps records free of undisclosed critical items).

## Phase R6: Report (Japanese)

Skip-aware perspective sections, summary table (severity × counts ×
cross-model agreement × auto-fixed × residual), confidence-scored integrated
findings, per-loop auto-fix stats, and 推奨事項.
タメ語・女性・体言止めなし。末尾に round 記録のパスを1行添える。
