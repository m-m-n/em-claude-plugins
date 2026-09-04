# Review Phase Protocol (em-workflow)

Read and executed inline by `/em-workflow:develop` (review step) and by
`/em-workflow:review` (standalone). The main session performs the
orchestration itself and issues all parallel `Task()` calls from its own
context.

Two execution contexts, one protocol:

| | develop-駆動 | standalone (/em-workflow:review) |
|---|---|---|
| project_root | integration worktree | cwd |
| review target | `git diff {base_commit} HEAD` (integrated diff) | `git diff HEAD` (fallback: whole-codebase) |
| perspective selection | Layer 1 (workflow.yaml tasks) + Layer 2 | fallback floor + Layer 2 |
| auto-fix commits | orchestrator commits fixes to the integration branch per loop | no commits (working tree only) |
| records | feature-docs/{feature}/reviews/roundN.yaml + workflow.yaml summary | ./reviews-{YYYYMMDD-HHMM}/round1.yaml だけ書く (git 管理はユーザー任せ) |

## Phase R0: Resolve SSOT & review target

1. Resolve from the SAME plugin version directory, fail-closed (never cwd;
   fallback search only under `$HOME/.claude/plugins` / `$HOME/.claude/skills`
   with path filter `*/em-workflow/*/references/*`):
   - `protocol_path` = references/review-protocol.md
   - `schema_path` = references/review-output-schema.json
   - `registry_path` = references/reviewers.yaml
   - `rules_path` = references/review-rules.yaml
   - `evaluation_contract_path` = references/review-evaluation-contract.md
   Abort loudly if any is missing.
2. Determine `review_mode` + `changed_files`:
   - develop-駆動: `changed_files = git -C {project_root} diff --name-only
     {base_commit} HEAD`; `review_mode = "diff"`. Exclude
     `feature-docs/{feature}/**` (docs are not review targets).
   - standalone: `changed_files` = `git diff HEAD --name-only` merged with
     `git ls-files --others --exclude-standard` (untracked files); non-empty
     ⇒ diff mode; both empty / non-git ⇒ whole-codebase mode (enumerate via
     Glob; apply the size gates: hard abort > 5000 files or > 500k
     lines; AskUserQuestion > 200 files or > 20k lines). Before selecting
     `review_mode` or building `diff_cmd_quoted`, apply the SAME size gates
     (hard abort > 5000 files or > 500k lines; AskUserQuestion > 200 files or
     > 20k lines) to this merged changed_files list itself, regardless of
     tracked vs. untracked origin. Untracked entries never appear in `git
     diff` output, so reviewers must Read them directly.
3. **Validate every path** (reject leading `-`, newline, CR, NUL; reject
   symlinks via `lstat` — never `stat` —, require a regular file, and require
   `realpath` to stay under project_root — same containment/symlink treatment
   step 4 applies to spec_path; abort on violation, never sanitize) and build
   `diff_cmd_quoted` with `printf %q`:
   develop-駆動 `git -C {project_root} diff {base_commit} -- <quoted paths>`
   (project_root = integration worktree, so the command resolves against it
   even though reviewers inherit the main session's cwd), standalone
   `git diff HEAD -- <quoted paths>`. Reviewers run it verbatim.
4. Locate SPEC.md: develop-駆動 → `{project_root}/feature-docs/{feature}/SPEC.md`
   — the committed copy inside the integration worktree is the canonical
   review input (must exist; SDD guarantees it). Do NOT resolve the spec from
   the main tree: the containment check below is project_root-based and the
   integration copy is what the reviewed code was built against. Standalone →
   Glob `feature-docs/*/SPEC.md`, `doc/tasks/*/SPEC.md`, `**/SPEC.md`;
   absent ⇒ `spec_available = false`. Validate `spec_path` (prompt-control
   chars + realpath containment under project_root + symlink rejection).
5. Probe codex: `codex_available = [ -f "${CLAUDE_PLUGIN_ROOT}/scripts/run_codex_exec.sh" ] && command -v codex`.
6. Probe litellm: `litellm_available` = the optional `vertex-review` plugin
   is installed AND its harness (`codex exec -p litellm`) is configured.
   ALL of these must hold — any one missing → `false`:
   ```bash
   find "$HOME/.claude/plugins" -maxdepth 6 -type f \
     -path '*/vertex-review/*/agents/vertex-reviewer.md' 2>/dev/null | grep -q .
   command -v codex                       # the harness IS the Codex CLI
   [ -n "${LITELLM_API_KEY:-}" ]          # proxy auth (virtual key)
   [ -f "$HOME/.codex/litellm.config.toml" ]   # the `-p litellm` profile
   ```
   Do NOT probe the proxy itself (liveliness endpoint, container state, or
   the remaining budget): the port and the deployment shape are the
   vertex-review plugin's knowledge, not this phase's. A proxy that is down
   or out of budget surfaces as a reviewer skip and is handled by the R2b
   chain walk. An environment without the plugin behaves exactly as before
   litellm support existed — every chain falls through to its codex entry.
7. Load prior rounds (develop-駆動 only): read existing
   `reviews/round*.yaml`; build `round_context` = list of
   `{stable_id, file, line, resolution}` for all recorded findings. This is
   what enforces the nit-relitigation ban across rounds and sessions.

## Phase R1: Perspective selection (two layers)

### Layer 1 — mechanical floor (deterministic, no diff input)

Input: ONLY the declared task metadata. develop-駆動: the `domains` /
`complexity` of the tasks in THIS feature's workflow.yaml. Standalone with no
workflow.yaml: the floor is `baseline` + (`spec` if spec_available) only.

Evaluate references/review-rules.yaml exactly as its header comments specify
(union semantics). Output: `floor` = ordered unique perspective list, and a
**provisional** `cross_validation` per the rules' `when_any` clause
(finalized after Layer 2).

### Layer 2 — discretionary additions (add-only)

The orchestrator inspects the integrated diff (develop-駆動) or the diff /
file list (standalone) and MAY add perspectives NOT in the floor. It may
NEVER remove a floor perspective. Every addition carries a one-line reason.

Mandatory Layer-2 check — `license`: when the diff touches dependency
manifests or lockfiles (`package.json`, `go.mod`, `Cargo.toml`,
`pyproject.toml` / `requirements.txt`, `composer.json`, `Gemfile`,
`build.gradle` / `pom.xml`, and their lockfiles) or adds vendored
third-party source, ADD the `license` perspective. It is never in the floor
(review-rules.yaml has no manifest signal), so this is the only path that
selects it.

After Layer 2 completes, **re-evaluate `cross_validation` against the
FINAL selected set** (floor ∪ discretionary): it fires when ANY task has
`complexity: high` OR the final set includes `security`. Firing no longer
adds a second dispatch (IMPLEMENTATION.md D2): every selected perspective
already runs exactly one primary reviewer (Phase R2). Instead it marks the
round as high-intensity for the evaluator (Phase R3a's `cross_validation`
input field) — the Layer-1 value is provisional only.

Record the plan before fan-out — develop-駆動: into workflow.yaml
`review.plan` (`floor` / `discretionary` / `cross_validation` — the
post-Layer-2 final value); standalone: keep it in-context for the round
record.

## Phase R2: Fan-out (ONE message, N Task calls)

Read references/reviewers.yaml. For each selected perspective (skip
`requires_spec` ones when `spec_available == false` — render as SKIPPED):

Walk that perspective's registry `primary_chain` (an ordered list of
`{harness, model?}` entries — the registry's per-perspective chain key,
IMPLEMENTATION.md Shared Components "Registry chain key") from the front and
take the FIRST entry whose harness is available (`codex_available` for
`codex`, `litellm_available` for `litellm`). Dispatch exactly ONE primary
reviewer for this perspective:

- `{harness: codex}` → `Task(subagent_type="em-workflow:codex-reviewer")`
- `{harness: litellm, model: M}` →
  `Task(subagent_type="vertex-review:vertex-reviewer")` with `model: M`
  added to the input block (a separately-installed plugin; the block is
  otherwise identical — that reviewer fetches diff/file data itself exactly
  like the codex reviewer). `M` is passed through verbatim from the
  registry; never substitute a model of your own choosing, and never
  dispatch this reviewer without a `model`.

**No entry of the chain available** → dispatch
`Task(subagent_type="em-workflow:reviewer")` instead. The two branches are
mutually exclusive: the Claude reviewer is never launched alongside a
harness reviewer for the same perspective. Exactly one primary reviewer runs
per selected perspective.

Every dispatch — primary harness reviewer or Claude fallback — carries the
same review-protocol input block (perspective, perspective_skill = registry
`claude_skill`, review_mode, protocol_path, schema_path, changed_files,
diff_cmd_quoted, spec_path when perspective == spec, project_license when
perspective == license (develop-駆動: workflow.yaml `project.license`;
standalone: detect from `{project_root}/LICENSE*`, `none` when absent),
project_root, round_context, lessons).
`lessons`: when `feature-docs/LESSONS.md` exists (develop-駆動: in the MAIN
working tree — the orchestrator reads it itself, it is not a reviewer-side
path; standalone: under cwd) and it has a `## reviewer:{perspective}`
section, inline that section's items verbatim; omit the field otherwise.
Normalize `changed_files` and `spec_path` to **project_root-based absolute
paths** before interpolating them into the block — reviewers inherit the
main session's cwd, and in develop-駆動 mode the reviewed code exists ONLY
in the integration worktree at project_root, so relative paths (or Reads
resolved against the reviewer's own cwd) would hit the wrong tree.

Record per perspective: the chain INDEX picked, the run `role`
(`primary` / `fallback`), and the orchestrator-known source identity
(IMPLEMENTATION.md Shared Components "Source identity vocabulary":
`codex:<perspective>`, `litellm:<model>:<perspective>` for a primary
dispatch, `claude:<perspective>` for the fallback) — R2b resumes the walk
from the entry after the recorded chain index.

All Task calls go in a SINGLE message. The orchestrator passes only paths and
the file list — never diff content (each reviewer fetches its own data).

## Phase R2b: Cross-model fallback (chain walk)

Applies to every perspective whose R2 primary-reviewer dispatch returned
`skipped: true` with a **retryable** `skip_reason`. Retryable reasons, and
how far the walk advances:

| `skip_reason` | What it means | Advance to |
|---|---|---|
| `rate_limited` | upstream congestion (Codex rate limit, Vertex 429) | the next entry in the chain |
| `budget_exhausted` | the harness's own budget is spent (LiteLLM's monthly virtual-key cap) | the next entry of a **different** harness |
| `harness_unavailable` | the harness could not be reached at all (proxy down, profile broken, wrapper missing) | the next entry of a **different** harness |

Budget and reachability are properties of the HARNESS, not the model: all
`litellm` entries share one virtual key and one proxy, so retrying another
model on it repeats the failure. Congestion is not — Vertex 429 says nothing
about Muse, so `rate_limited` may advance within the same harness.

Every other `skip_reason` (`protocol_unresolved`, `schema_unresolved`,
`skill_unresolved`, `no_spec`, …) is **not** retryable: it reports a config
or input problem that every entry would hit identically. Keep the skip.

**Malformed non-retryable results.** A dispatched reviewer's result that is
neither a valid `skipped: true` object (with one of the `skip_reason`s above)
nor schema-valid per the Phase R0-resolved `schema_path`
(`references/review-output-schema.json`) — it fails schema
validation, or the Task output is truncated/unparseable as JSON — is not a
skip and is not routed through this table. Record that run in
`perspective_runs` with `status: failed` (not `skipped`, not `completed`);
do not invent a `skip_reason` for it. A perspective whose only run this round
is `status: failed` has no `perspective_runs` entry with `status: completed`,
so Phase R5's Unreviewed-perspective disclosure lists it in
`unreviewed_perspectives` — that disclosure is record-keeping, not a
completion blocker, so it does NOT by itself hold the step open. Run
`references/workflow-failure-recovery.md`'s workflow-doctor when the
harness-level cause needs diagnosing, and report it in Phase R6; do not
dispatch an additional reviewer from R2b.

A result that IS schema-valid — including a well-formed empty `findings: []`
with `skipped: false`, `skip_reason: null` — is a substantive completed
result and is used as-is for Phase R3a's `reviewer_outputs`. Schema validity
is the only test; do not additionally judge whether the reviewer "really"
inspected the diff.

Walk rules:

- Resume after the chain index R2 recorded; skip entries whose harness is
  unavailable (that costs no hop) and entries excluded by the table above.
- **At most 2 fallback dispatches per perspective**, which walks a 3-entry
  chain to its end. Exhausted chain, or no eligible entry → the perspective
  keeps its last skip result — a skip contribution, not a Claude re-run: the
  Claude fallback branch is decided in R2 from availability, never from a
  skip.
- The LAST dispatched result is this perspective's primary-reviewer result
  for Phase R3a, in place of the skips that preceded it.
- Each hop depends on the previous result, so hops are sequential — but
  perspectives are independent: all perspectives falling back at the same hop
  go in ONE message.
- The evaluator (Phase R3a) is dispatched only after every selected
  perspective's chain walk has finished. This chain-walk mechanism (R2b as a
  whole) applies identically to Phase R4's in-loop re-reviews; only the
  evaluator dispatch at the end of the walk is skipped there (Phase R3a,
  Phase R4 Loop termination).

This is the only cross-validation step that runs after seeing another
reviewer's result — every dispatch in R2 is availability-based and decided
before any Task call.

A reviewer that fails at the **harness** level never reaches this table: the
Task call itself comes back `is_error`, a permission denial lands in its
output, or the Codex wrapper script never executed, so there is no
`skip_reason` to route on. That is not a chain-walk case — diagnose it per
`references/workflow-failure-recovery.md` (dispatch `workflow-doctor` over
the failed agents' JSONL logs) and include the diagnosis in the R6 report
rather than silently recording the perspective as missing.

## Phase R3a: Evaluation (single Opus evaluator)

One dispatch of `Task(subagent_type="em-workflow:review-evaluator")` per
round — never more than one, and never skipped — carrying the evaluator
input block. This cap covers the round as a whole, including any Phase R4
in-loop re-review: re-review findings from a productive auto-fix loop are
NOT run through a second evaluator dispatch; Phase R4's Loop termination
routes them through the R3b mechanical gates directly (the same path as
R3b's evaluator-failure degradation).

- `evaluation_contract_path` — resolved in Phase R0 alongside the other SSOT
  paths, under the same fail-closed rule.
- `project_root`, `review_mode`, `changed_files`, `round`.
- `cross_validation` — Phase R1's final post-Layer-2 value; it marks the
  round high-intensity for the evaluator and no longer adds a dispatch of
  its own.
- `round_context`.
- `spec_path` — only when the spec perspective ran this round.
- `lessons` — optional, same resolution rule as Phase R2.
- `perspectives_dispatched` — one entry per perspective run this round,
  carrying `run_id`, `perspective`, `role`, `status`, `skip_reason`, and
  `model` for litellm runs.
- `reviewer_outputs` — one entry per run, carrying `run_id` plus that run's
  verbatim reviewer output.
- `unreviewed_perspectives` — perspectives with no completed reviewer run
  this round; present and empty when there are none (produced once the
  round's chain walks and fallbacks have concluded — see Phase R2b / R5).
  The evaluator's Independent Inspection Duty
  (`references/review-evaluation-contract.md`) does not apply to a
  perspective listed here: there is no reviewer output to corroborate.

`changed_files` and `spec_path` are normalized to project_root-based
absolute paths exactly as for reviewers (Phase R2). Every run's verbatim
output is tagged with the `run_id` the orchestrator itself assigned when
dispatching it. The evaluator returns one object; Phase R3b defines how the
orchestrator processes it.

## Phase R3b: Mechanical gates on the evaluation

The evaluator's output is UNTRUSTED, same as every reviewer's. The
orchestrator recomputes identity itself and never trusts the evaluation's
`stable_id`, `sources` or `category` (IMPLEMENTATION.md D3/D8). Per finding,
in this order:

1. `file` lexical check: reject absolute paths, `..` segments, NUL. Then the
   existence check under project_root (reject missing).
2. `severity` ∈ {critical, high, medium} else drop.
3. `category` must equal the dispatched perspective of the finding's source
   run(s) — the evaluator-supplied `sources` ids looked up against
   `perspectives_dispatched`; a finding left with no valid run (attributed
   to `claude:evaluator`) must instead carry a category that was dispatched
   this round — on mismatch, **drop unconditionally** (never relabel —
   relabelling launders injection). A finding on a file outside
   `changed_files` (diff mode) keeps its category — the old forced relabel
   to `comprehensive` is removed — and takes only the confidence cap below.
4. Cap `title`/`description`/`suggestion` at 4096 bytes each
   (`… [truncated]`).
5. `stable_id` recomputed from the unchanged normalization formula (these
   definitions are load-bearing and stay verbatim):

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
   dedupe, conflict grouping AND the accountability floor below;
   `coupling_id` is only a pre-filter shortlist, never the decider. Any
   evaluator-supplied `stable_id` is discarded.
6. `sources` rebuilt by mapping the evaluator-supplied `sources` ids onto
   the run identities the orchestrator itself assigned in Phase R2 / R2b;
   unknown ids are dropped, and a finding left with none is attributed to
   `claude:evaluator`.
7. Confidence = the evaluator's value, then the two mechanical corrections,
   in that order: `+15` (cap 100) when ≥ 2 perspectives flag the same site;
   hard cap `50` for a finding outside `changed_files`. These are the ONLY
   confidence arithmetic the orchestrator performs.

Dedupe within category by `same_site` (whole-codebase mode: `(file,
category)` + title-token overlap ≥ 50%). Merge: richest description, union
`sources`, max severity.

**Round-context suppression**: drop any deduped finding whose `stable_id`
appears in `round_context` with resolution `declined`, unless its file
changed since that round's recorded `head_commit`. (`fixed` entries are NOT
suppressed — a reviewer re-reporting one means the fix regressed.)

**Evaluator accountability floor** (IMPLEMENTATION.md D8, mechanical, no
judgment call — replaces the old whole-evaluation coverage gate): for every
critical/high site a reviewer run reported this round, that site must
appear — by `same_site`, the same predicate step 5 defines, never a
bucketed site reduction — in either the evaluation's `findings` or
its `dismissed_sites` (`references/review-evaluation-contract.md`). A site
matched by neither is lifted into `findings` on its own: the reviewer run's
own text, that run's orchestrator-assigned source identity, the dispatching
perspective as `category`, and confidence `60` — nothing else about the
evaluation is discarded, and no relabelling occurs. A round where every
reviewer critical/high site is legitimately dismissed lifts nothing and the
evaluation is kept as-is: dismissing everything through `dismissed_sites`
is an ordinary triage outcome, not an omission signal. This floor checks a
completeness property the evaluator's own contract declares
(`dismissed_sites`); it never re-judges the evaluation's content, and it
never discards the evaluation itself.

**Evaluator-failure degradation** (IMPLEMENTATION.md D4/D8): the
orchestrator does NOT abort or skip the round when either of exactly two
structural triggers fires — the evaluator's Task failed, or the returned
object is missing a required root field. Coverage is never a trigger: the
accountability floor above only ever lifts individual sites into the kept
evaluation, it never degrades the whole object. On either trigger, the
orchestrator takes each primary/fallback reviewer's own findings through
the same gates above instead: self-reported `category` is checked against
the dispatching perspective per step 3's discipline — mismatch drops the
finding unconditionally (never relabel); a match is stamped with the
dispatching perspective, discarding the self-report. `sources` is set to
that run's own identity and confidence to `60`; the orchestrator records
the evaluator run with `status: failed` in `perspective_runs`; and proceeds
to Phase R4 with its own decision procedure. When the evaluator's Task
SUCCEEDED but the accountability floor had to lift one or more sites, the
evaluator run is instead recorded with `status: completed` and `degraded:
true` in `perspective_runs` — never `status: failed`, which would misreport
a successful Task.

**`recommended_action` is advice, never a decision** (IMPLEMENTATION.md D5):
it never overrides the completion gate (`residual_critical_high == 0`,
defined once in Phase R5's Completion gate — not restated here), the
`--report-only` flag, the auto-fix loop cap, the batch rework cap, or the
fixed rework ordering of `references/rework-task-synthesis.md` Section 10.
Writes, commits and AskUserQuestion stay orchestrator-exclusive; this new
path introduces no new AskUserQuestion and no new gate identifier.

## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)

`--report-only` (aliases `--no-auto-fix`, `--no-fix`) skips R4 entirely.

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

Batch mode (develop-駆動 only; the orchestrator propagates `--batch`): no
AskUserQuestion. **conflict** → skip the site (abort all members;
conflicting prescriptions are not mechanically resolvable —
`references/batch-mode.md`'s Non-packet gates table, gate
`review.auto-fix-conflict`). **needs-judgment** → auto-select `Apply as-is
(editor interprets)` (`references/batch-mode.md`'s Non-packet gates table,
gate `review.auto-fix-judgment`).

Each approved candidate dispatches to
`Task(subagent_type="em-workflow:review-editor")` with `target_file_abs`
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

Scope verification (condensed). Loop setup, both modes —
before the loop's first dispatch: `BACKUP_DIR=$(mktemp -d)` (0700, trap
cleanup), snapshot all target files, snapshot untracked list
(`git status --porcelain -z -uall`), init rolling `current_hashes[rel]`
from backups via `git hash-object`.

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

develop-駆動 only: after each loop with `applied > 0`, commit the fixes in
the integration worktree under the SAME shared lock `commit-docs.sh` and
`merge-task.sh` use — `commit-docs.sh` itself cannot be reused here (it
stages only its fixed `ARTIFACT_PATHS` allowlist, while a fix commit must
stage arbitrary authorized source files named by the loop's findings), so
acquire the lock, stage, and commit inside one critical section:

```bash
PROJECT_ROOT={printf-%q-rendered project_root}
authorized_files=( {authorized files, one shell-quoted argv element per file} )
GIT_COMMON_DIR=$(git -C "$PROJECT_ROOT" rev-parse --path-format=absolute --git-common-dir) || exit 1
exec 9>"$GIT_COMMON_DIR/em-workflow-merge.lock" || exit 1
flock 9 || exit 1
git -C "$PROJECT_ROOT" add -A -- "${authorized_files[@]}" || exit 1
git -C "$PROJECT_ROOT" commit -m "fix({feature}): review round {round} loop {N}" || exit 1
# fd 9 closes (releasing the lock) when this shell/subshell exits
```

Every step above is fail-fast (`||  exit 1`): a failure to resolve
`GIT_COMMON_DIR`, open fd 9, acquire the lock, or stage files aborts
the section before any commit runs, so the integration ref can never
advance without the shared lock. `PROJECT_ROOT` is rendered by the
orchestrator via `printf %q` (never raw textual substitution) into a
single shell word, captured once into a variable, and referenced as
`"$PROJECT_ROOT"`; authorized
files are expanded from a bash array (`"${authorized_files[@]}"`),
never via textual placeholder substitution, so filenames containing
shell metacharacters cannot be interpreted as shell syntax.

(`--path-format=absolute`, git ≥ 2.31, sidesteps the cwd-relative output
`rev-parse --git-common-dir` can otherwise return under `-C`.)

No bare `git add`/`git commit` against the integration worktree runs outside
this locked section anywhere in this document. Standalone mode commits
nothing, ever.

Loop termination: re-run ALL selected reviewers after any productive loop
(re-review preamble: per-perspective stable_id/file/line list only — no
titles/descriptions; other perspectives get a generic collateral-impact
note). Re-aggregation of this in-loop re-review output does NOT re-dispatch
the evaluator — Phase R3a's "never more than one [dispatch], and never
skipped" per round is not relaxed here. Instead, run each re-reviewed
perspective's own findings straight through the Phase R3b mechanical gates,
the same path Phase R3b's evaluator-failure degradation already uses:
self-reported `category` checked against the dispatching perspective per
step 3's discipline (mismatch drops unconditionally, never relabel; a
match is stamped with the dispatching perspective, discarding the
self-report), `sources` set to that run's own identity, confidence `60`
(the two mechanical corrections in R3b step 7 still apply on top). Record each in-loop re-review run in `perspective_runs`
exactly like a normal round run (`role: primary`/`fallback`, `status`). Then:
zero residual critical/high non-spec → `clean`; `loop == 3` → `loop-cap`; no
progress and no user-resolvable candidates → `no-progress`.

## Phase R5: Persist the round record

Write `reviews/round{N}.yaml` (develop-駆動: at
`{project_root}/feature-docs/{feature}/reviews/round{N}.yaml` —
project_root is the integration worktree per the mode table above, a
committed worktree-resident path like every other feature-docs artifact;
standalone: `./reviews-{timestamp}/round1.yaml`), N = prior rounds + 1:

```yaml
round: {N}
executed_at: "{RFC 3339 with offset}"
scope:
  review_mode: diff
  base_commit: {sha}        # diff base (develop: implement base_commit)
  head_commit: {sha}        # HEAD at review time
  changed_files: [...]
plan:
  floor: [...]
  discretionary:
    - perspective: performance
      reason: "..."
  cross_validation: true
perspective_runs:
  - {perspective: security, role: primary, source: codex, status: skipped, skip_reason: "rate_limited"}
  - {perspective: security, role: primary, source: litellm, model: muse-spark, status: completed}
  - {perspective: performance, role: fallback, source: claude, status: completed}
  - {role: evaluator, source: claude, status: completed}
  # `model` は litellm ハーネスのときだけ付ける。R2b の chain walk は
  # 1 観点につき primary の複数行になり得る — 最後の行がその観点の
  # primary reviewer 結果。role: fallback は primary_chain に利用可能な
  # エントリが無かったときの Claude 単独実行を表す。role: evaluator の
  # 行だけ `perspective` を持たない。
findings:                    # post-dedupe, post-sanitize; FULL detail
  - stable_id: {id}
    severity: high
    category: security
    file: src/foo.go
    line: 42
    title: "..."
    description: "..."
    suggestion: "..."
    sources: [claude:security, litellm:muse-spark:security]
    confidence: 95
    resolution: fixed        # fixed | declined | deferred | unresolved
    resolution_reason: "auto-applied loop 1"   # declined は理由必須
auto_fix:
  loops_run: 2
  applied_total: 3
  termination: clean
residual_critical_high: 0
rework_required: false       # true → implement へ差し戻し
```

`perspective_runs` entries gain a `role` field: `primary` (a `primary_chain`
entry ran for that perspective), `fallback` (no chain entry was available;
the entry's `source` is `claude`), or `evaluator` (the round's single
evaluator run — the only entry with no `perspective` field). `source:
claude` on a perspective entry now means the fallback run (IMPLEMENTATION.md
D1); it is never a second, parallel run alongside a harness reviewer for the
same perspective. The `evaluator` entry additionally carries `degraded:
true` whenever its Task succeeded but Phase R3b's accountability floor had
to lift one or more sites into `findings`; its `status` stays `completed`
in that case (IMPLEMENTATION.md D8) — `status: failed` is reserved for the
two structural degradation triggers of Phase R3b.

develop-駆動: update workflow.yaml `review` block (rounds_completed,
perspectives, residual_critical_high, needs_rework, status), then commit
both the round record and the workflow.yaml update in the same step —
`commit-docs.sh {integration_worktree} "docs({feature}): review round {N}"`
("レビュー記録はデフォルトでコミット" policy). There is no deferred
end-of-run sync: each round's records and resolution updates land on the
integration branch immediately, including the batch-mode rework/defer
updates below.

**Completion gate**: the review step may be marked `completed` ONLY when
`residual_critical_high == 0`. Otherwise: offer another round / rework /
explicit user acceptance (recorded as `deferred` with reason — this is the
opt-out that keeps committed records free of undisclosed critical items).
Batch mode: same rule, recorded as `deferred` per `references/batch-mode.md`'s
Non-packet gates table (gate `review.residual-critical-high`) rather than
offered interactively.

**Unreviewed-perspective disclosure** (record-keeping only — never a
completion blocker): among perspectives actually dispatched this round in
Phase R2 (excluding any `requires_spec` perspective skipped there because
`spec_available == false` — no dispatch, no `perspective_runs` entry, nothing
to disclose), any perspective whose entries this round are all `status:
skipped` or `status: failed` — no `status: completed` entry at all (the R2b
chain-exhausted case, or an R2b malformed-result case) — has not actually
been reviewed this round regardless of its finding count. List such
perspectives under a round-record-root `unreviewed_perspectives` field
(present and empty when there are none). This is disclosure, not a gate: the
step still completes whenever `residual_critical_high == 0` above holds, and
no new gate identifier or batch non-packet gates table entry is introduced
for it. Interactive mode surfaces the same list in the Phase R6 report so a
human is not silently left unaware that a perspective went unreviewed.

Rework path (interactive): when the user selects rework, follow the fixed
ordering `references/rework-task-synthesis.md` Section 10 states for
review-sourced rework — the orchestrator writes `review.needs_rework = true`
and `review.status = pending` directly to workflow.yaml FIRST (this write is
the orchestrator's own; it is NEVER carried inside a worker patch), THEN
dispatches rework-planner, THEN validates and applies rework-planner's patch
(`tasks_patch` + `step_patches` + `preserve`). `implement` returning to
`pending` is carried inside that patch's `step_patches` in the last step —
it is never a separate write, and it never happens before the patch has
registered at least one pending rework task
(`references/rework-task-synthesis.md` Invariant 1). Task synthesis itself —
grouping, task ID allocation, metadata derivation, verification coverage,
and the rest of the invariants — is defined once in
`references/rework-task-synthesis.md`; this document does not restate it.

Batch mode (develop-駆動 only): no offer — auto-rework with cap 1. When
`batch.review_rework_count == 0` in workflow.yaml: follow the SAME ordering
as the interactive path above (`references/rework-task-synthesis.md`
Section 10) — write `review.needs_rework = true` and `review.status =
pending` directly, dispatch rework-planner to synthesize rework tasks from
the residual critical/high findings per `references/rework-task-synthesis.md`,
then validate and apply its patch (`implement` returning to `pending` is
carried inside that patch, exactly as in the interactive path — never a
separate write here either), and increment the counter. When the counter is
already ≥ 1: mark each residual finding `resolution: deferred` with
`resolution_reason: "batch mode: rework cap reached"` and complete the step
— the round record keeps them visible for the human evaluator.

This batch auto-rework / defer-at-cap behaviour above, its counter and its
round-record writes are unchanged by `references/batch-mode.md`'s
output-suppression discipline; any abort reached during this phase is a
stop under that document's stop/abort exception and keeps its full
output.

## Phase R6: Report (Japanese)

Rendering rules: skip-aware perspective sections, summary
table (severity × counts × confidence × auto-fixed × residual),
confidence-scored integrated findings, per-loop auto-fix stats, and 推奨事項.
タメ語・女性・体言止めなし。develop-駆動では末尾に round 記録のパスと
workflow.yaml の review サマリ更新結果を1行ずつ添える。

In a `--batch` run, this report's body above is not emitted into the main
context (`references/batch-mode.md` defines the withholding), while the
round record `reviews/round{N}.yaml` Phase R5 writes above — its content,
fields and write timing — are unchanged; this is what keeps this phase's
findings, including any deferred at Phase R5's cap, auditable from the run
report.
