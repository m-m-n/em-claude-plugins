# Implementation Plan: destructive-guard SAFE_DELETE traversal fix

## Overview

The delete guard's safe-path exception is moved from an un-normalized regex
prefix match to a component-wise containment judgement on the lexically
normalized target, and the expectation table is realigned with the corrected
decisions. The plugin version is raised in the same feature because files
under `em-workflow/` change.

## Technology Stack

- **Language**: Python 3, standard library only — the guard runs synchronously
  on every Bash invocation and must stay import-cheap and dependency-free.
- **Key libraries**: none. No new dependency is introduced by this feature.
- **License**: `project.license` is `none`, so no compatibility constraint
  applies; with zero new dependencies there is no new license to record.
- **Test mechanism**: the project's own expectation suite (case table + runner
  under `em-workflow/hooks/tests/`). No test framework is added.

## Layer Structure

Evaluation pipeline of the guard, and the only permitted dependency
directions:

1. **Input decode** — the hook payload is read and the command string is
   extracted.
2. **Lexing / segmentation** — the command string is split into segments and
   words; quoting, here-documents and command substitution are resolved here.
   Everything downstream sees words, never raw command text. A word this layer
   altered by removing a command substitution carries that fact downstream,
   together with whether the removal covered the whole word (D7).
3. **Shared lexical helpers** — pure, filesystem-free transformations over a
   single token (home-form expansion, lexical path folding). Helpers never
   call a check.
4. **Per-command checks** — one check per command word family (the recursive
   delete check is one of them). Checks depend on layer 3, never the reverse.
5. **Decision emission** — a single decision (`allow` / `ask` / `deny`) with a
   stable reason id. A check emits at most one decision for the whole command,
   but it selects that decision only after evaluating every target of every
   segment: the strongest decision found wins, and emission happens once at the
   end (D6).

The expectation suite depends on the guard; the guard never depends on the
suite. The case table is a description of the guard's actual behaviour, never
a source the guard consults.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Lexical normalization helper (`normalize_candidate`) | Turn one raw target token into a comparable path form | **Pre**: a single word-level token. **Post**: home forms (`~`, `$HOME`, `${HOME}`) replaced by the home value known at hook start; `.` / `..` / duplicate separators folded lexically; a leading double separator collapsed to one; the filesystem is never consulted (no real-path resolution, no file-status inspection, no subprocess). Existing callers keep their current results — the helper's behaviour is reused, not altered. | task0001 |
| Safe-root vocabulary (`SAFE_DELETE`) | Name the roots the recursive-delete check may wave through, in two classes | **Pre**: none. **Post**: exposes (a) build-artifact names — `node_modules`, `dist`, `build`, `target`, `.next`, `coverage` — safe on exact match and below, relative targets only; (b) scratch roots — `/tmp`, `/var/tmp`, `tmp`, `.cache` — safe only for proper descendants, the root itself never safe. Its comment states this rule. | task0001 |
| Recursive-delete check (`check_rm`) | Decide allow / ask / deny for one recursive delete | **Pre**: the command's word list. **Post**: exactly one of `allow` (fall-through, no output), `ask` with reason id `rm-unresolvable`, `deny` with reason id `rm-root` or `rm-recursive`. That one decision is the strongest decision any target of any segment warrants (D6), and the reason text names every target that contributed to it. No new reason id is introduced; the existing `rm-root` check keeps reading the raw token so its reason id survives. | task0001, task0003 |
| Unresolved-evidence signal (lexing → check boundary) | Tell the check that a word's text was altered by substitution removal, and whether the removal covered the whole word | **Pre**: a word the lexing layer produced. **Post**: the check can distinguish three states — (a) the word contained no substitution; (b) a substitution covered the WHOLE word, so the word contributes no target and the existing zero-target early return applies unchanged; (c) a substitution was adjacent to other text in the same word, so the word is a target whose value is unresolvable and which never reaches the safe exception. The signal is filesystem-free and carries no resolved value. State (b) keeps the decisions the SPEC pins to `allow` (US3); collapsing (b) into (c) is a specification violation (D7). | task0003 |
| Expectation case table (`destructive-guard-cases.json`) | Pin every decision the guard is expected to make | **Pre**: a JSON array of 3-element entries `[expected decision, label, command]`. **Post**: every entry states the corrected decision; no pre-existing `deny` or `ask` entry is removed. Owned exclusively by task0001 — no other task edits it. | task0001 |
| Plugin version pair | Declare the shipped plugin version | **Pre**: both manifests read `0.1.72` for `em-workflow`. **Post**: both read the identical raised value; no other plugin's version moves. Owned exclusively by task0002 — no other task edits a version field. | task0002 |

## Conventions

- **Case-table entries**: three elements, `[expected decision, label, command]`.
  The label states the reason for the expectation in Japanese. The wording
  "既知の穴(未修正)" marks a hole that is knowingly left open — it must not
  survive on an entry whose hole this feature closes.
- **Case-table growth**: entries are added, never deleted. An existing `deny`
  or `ask` entry stays; the half of the suite that proves a fix did not cost
  detection power depends on it.
- **Reason ids** stay as they are: `rm-root`, `rm-recursive`,
  `rm-unresolvable`. A behaviour change reuses an existing id rather than
  introducing a new one.
- **Determinism**: no decision path touches the filesystem. Path judgement is
  string processing only.
- **Version bump**: semver patch for a behaviour fix; the same literal value in
  both manifests.

## Cross-task Design Decisions

### D1: The decision logic and the case table are one task

The suite is the only arbiter of the guard's behaviour, and it runs both
halves together. A task that flipped the expectations without the logic (or the
reverse) would be red in its own worktree and could not state a passing
acceptance criterion. They therefore live in task0001 as one unit.

Affected tasks: task0001.

### D2: The version bump is a separate task with a pinned value

The bump touches only the two manifests, shares no file with task0001, and has
no test of its own. Isolating it keeps task0001's "tests pass = task done"
semantics intact. The value is pinned feature-wide at **0.1.73** (patch
increment from 0.1.72) so the two tasks cannot disagree, and `em-review`'s
version is not touched.

Affected tasks: task0001 (must not edit a version field), task0002 (owns it).

### D3: A safe-root match is never demoted to ask

Demoting the safe-root path to `ask` would stop unattended runs in place, since
`ask` becomes `deny` under batch execution. Normalization plus component-wise
containment already removes the dangerous false allows, so the demotion would
buy nothing and cost a stalled run per occurrence.

Affected tasks: task0001.

### D4: Unresolved expansions are judged before the safe exception; pure globs are not

A target carrying a variable expansion or command substitution can resolve
anywhere, so lexical folding of a parent reference inside it proves nothing —
it is judged unresolvable before the safe exception is considered. A pure glob
cannot produce a parent reference, so it still reaches the safe exception,
except for a dot-leading glob component, which could match a parent reference.

Affected tasks: task0001.

### D5: Symlink escape stays out of scope and is documented in place

Excluding it would require resolving real paths, which breaks both determinism
and the pinned allow for deletions under the scratch root. The residual
constraint is stated in the code rather than silently accepted.

Affected tasks: task0001.

### D6: The strongest decision wins over the first decision reached

A check that emits the first decision it reaches lets an `ask` on an early
target end the scan, so a later target — or a later segment — that warrants
`deny` is approved together with the `ask`, and the reason text names only the
target that triggered the `ask`. Decision selection is therefore separated from
decision emission: every target of every segment is evaluated, the strongest
decision is kept (`deny` > `ask` > `allow`), and emission happens once at the
end. This changes no reason id and adds no new one; it changes only which of
the existing decisions is the one emitted.

Affected tasks: task0003 (owns it); task0001's decision order per target is
unchanged and stays the input to this selection.

### D7: Substitution removal is signalled, and whole-word removal stays distinct

Removing a command substitution from a word erases the evidence that the word
cannot be resolved, and lexical folding then cancels a parent reference against
the residue — a delete whose real destination is outside every safe root reaches
the safe exception. The lexing layer therefore signals the removal downstream
(Shared Components, "Unresolved-evidence signal").

The signal keeps two shapes apart, and the distinction is decidable statically
from whether the removed span covered the whole word:

- A word that consisted SOLELY of a substitution contributes no target. The
  zero-target early return applies unchanged, and the `allow` the SPEC pins for
  it (US3's acceptance criterion for substitution-only targets) is preserved.
- A word where the substitution was adjacent to other text is a target whose
  value is unresolvable. It never reaches the safe exception.

Treating both shapes as unresolvable is what an earlier attempt at this fix did:
it moved the SPEC-pinned `allow` entries to `ask` and violated the
specification rather than lagging behind it. The SPEC is not re-pinned to
accommodate the wider treatment.

Affected tasks: task0003 (owns it); the helper's own behaviour (Shared
Components, lexical normalization) is not altered.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Relaxing the prefix match regresses pinned deny cases (an earlier attempt dropped the suite from 150/150 to 130/150) | Medium | High | Keep the two-class asymmetry; the scratch class never makes its own root safe; full suite is an acceptance criterion |
| A new false positive on the allow side stops an unattended run | Medium | High | Every allow behaviour named in the spec is pinned as a case-table entry and as an acceptance criterion |
| Reordering against the unresolved-expansion check silently turns existing `ask` entries into `allow` | Medium | High | Judge expansions/substitutions before the safe exception; the affected entries are named in task0001's criteria |
| Normalizing too early changes which reason id an existing deny reports | Low | Medium | Normalization is confined to the safe-exception judgement; the root/home check keeps reading the raw token |
| The two manifests drift to different versions | Low | Medium | Single pinned value (D2) and an equality criterion in task0002 |
| Signalling substitution removal too widely moves the SPEC-pinned allow for substitution-only targets to ask (this already happened once) | Medium | High | D7's two shapes are kept distinct on a statically decidable condition; the preserved allow is a named acceptance criterion of task0003, verified by a full suite run rather than by the new entries alone |
| Deferring the ask to collect a later deny changes which decision an existing ask-pinned entry reports | Low | High | D6 keeps every reason id and every per-target rule as it is; a command whose unresolvable target is its only target is a named acceptance criterion on the ask side |

## Open Questions

- [ ] None. Every requirement is resolved in workflow.yaml; no `tbd` entry
      remains.
