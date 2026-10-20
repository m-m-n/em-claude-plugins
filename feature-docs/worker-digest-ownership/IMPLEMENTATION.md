# Implementation Plan: worker-digest-ownership

## Overview

The orchestrator, never a Bash-less writing worker, computes, verifies and
records every artifact digest, through one standard-library script and one
owner document that every `write_policy` dispatch site cites. Two new
invariant checks, validator tests and script tests detect a regression.

## Technology Stack

- **Language**: Python 3, standard library only (new script, checker
  extension, validator change, every new test); Markdown for protocol
  documents.
- **Test framework**: `unittest`, run as `python3 -m unittest discover -s tests`.
- **New dependencies**: none. `project.license` is `none`; no license line
  is recorded because nothing new is introduced.

## Layer Structure

| Layer | Members | Responsibility |
|---|---|---|
| Owner document | `em-workflow/references/artifact-digest.md` | Sole owner of the digest definition, the calculation means, the pre-dispatch verification procedure, layer-5 recording, the legacy-record rule, and the list of dispatch sites |
| Citing protocol documents | `references/phases/create-spec-phase.md`, `references/phases/create-plan-phase.md`, `references/rework-task-synthesis.md`, `skills/develop/SKILL.md`, `references/contracts/spec-writer-contract.md`, `references/contracts/worker-envelope.md`, `references/phase-state.md`, the four worker agent prompts | Cite the owner document (path + section name); never restate its content |
| Tooling scripts | `scripts/artifact-digest.py`, `scripts/validate-worker-output.py`, `scripts/check-plugin-invariants.py` | Calculation; structural validation; repository invariants |
| Tests | `tests/` | Run scripts as child processes or load them as modules; read documents |

Allowed directions: citing documents → owner document → script (by its
invocation). The script reads no document. The checker reads documents and
agent files only. Tests depend on scripts and documents, never the reverse.
All paths in this document are repository-relative unless written relative
to `em-workflow/`.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Owner document `em-workflow/references/artifact-digest.md` | Protocol-side SSOT for digests | Exists at this path after task0002. Carries exactly these section headings (level 2), which other documents cite by name: `Digest definition`, `Calculation`, `Pre-dispatch verification`, `Layer 5 recording`, `Legacy records`, `Dispatch sites`. A citation is the path token `references/artifact-digest.md` plus the quoted section name in the same paragraph. | built by task0002; cited by task0003 |
| Digest script `em-workflow/scripts/artifact-digest.py` | The single calculation of the artifact digest | "Digest script CLI contract" below | built by task0001; its invocation is documented by task0002 |
| Design phase-state record | Where design-step digests are recorded | Path `feature-docs/{feature}/phase-state/design.yaml`; `phase` value `design`; the existing phase-state schema unchanged; its `status` never takes `applying_patch`; created only when the design step dispatches the designer (none when the step is `skipped`). `validate-worker-output.py --kind phase-state` accepts `phase: design`. | defined by task0003; written by the procedure task0002 documents |
| Owner stance sections (existing) | Owner text of the worker-side digest stance | `references/contracts/worker-envelope.md` keeps heading "`written_artifacts` reporting" and, inside it, the sentence beginning "The worker does not compute digests". `references/contracts/spec-writer-contract.md` keeps heading "Who verifies `expect_digest`" and, inside it, "The orchestrator verifies `expect_digest`, not the worker." and "A worker never returns `blocked` because it cannot compute a digest." (the existing line break after "cannot" is preserved, NFR1). Matching is whitespace-normalized. | edited (preserving) by task0003; read by task0004's check |
| Invariant-checker extension protocol | Lets two tasks extend `check-plugin-invariants.py` in parallel | See "Checker extension protocol" below | task0002, task0004 |

### Digest script CLI contract

- **Invocation**: `python3`, then the double-quoted script path, then one or
  more target paths. The script defines no options: every argument is a
  target path taken verbatim, including arguments beginning with `-`
  (`-`, `--`, `--help` are file names). Relative paths resolve against the
  current directory. An empty argument is reported as `missing`.
- **Digest**: sha256 over the file's raw bytes, rendered `sha256:` followed by
  64 lowercase hexadecimal digits. Read in bounded chunks (memory use does
  not grow with file size).
- **Entry kinds**: only a regular file is hashed. The entry is never resolved
  through a symlink, and nothing waits on a FIFO or device; the regular-file
  determination holds for the handle actually read, so an entry swapped
  between inspection and reading cannot redirect or block the read.
- **Output**: stdout carries one JSON array, UTF-8 encoded whatever the
  locale, non-ASCII characters unescaped, followed by a newline. Exactly one
  element per argument, in argument order, duplicates kept. A success element
  has `path` (the argument as given) and `sha256` (the digest). A failure
  element has `path`, `sha256: null` and `error`, one of `missing` (no
  filesystem entry), `not_a_regular_file` (directory, symlink, FIFO, device,
  socket), `unreadable` (a regular file whose reading failed).
- **Exit codes**: `0` = every element has a digest; `1` = at least one
  element has an `error` (every other element is still hashed); `2` = no
  argument (usage text on stderr) or an unexpected internal failure; stdout
  carries no array on exit `2`.
- **Isolation**: standard library only; starts no child process and calls no
  external command (NFR3).

### Checker extension protocol

- task0002 adds `check_dispatch_digest_wiring(root)` (result name
  `dispatch_digest_wiring`); task0004 adds `check_worker_digest_stance(root)`
  (result name `worker_digest_stance`). Each returns the existing
  `CheckResult` shape, is a pure function of `root`, and reads fixed paths
  only — neither walks the repository nor calls `iter_repo_files` (the
  single-traversal test must keep counting one call).
- `run_all_checks` appends them after the existing seven, in the order
  `dispatch_digest_wiring`, `worker_digest_stance`.
- `tests/test_check_plugin_invariants.py`'s `build_passing_repo` gains one
  call per task, each to that task's own helper that adds the synthetic files
  its check needs. Fictional agent names differ per helper
  (`wiring-worker` for task0002, `stance-worker` for task0004) so the two
  helpers never write the same path.
- The module docstring's check enumeration is updated by task0002 only, and
  names both new checks.
- On a merge conflict in these two files, keep both sides' additions.

## Conventions

- **Citation, not restatement (NFR2)**: a citing document names the owner
  path and section; it never re-words the definition, the procedure, or the
  script's output and exit contract.
- **`git hash-object`**: never named as the means for `expect_digest`,
  phase-state `artifacts[].sha256`, or layer-5 digests. It stays only in
  create-spec-phase.md's post-dispatch scope comparison and in the owner
  document's `Legacy records` section. `create-plan-phase.md` never contains
  it; `worker-envelope.md` never contains the token `expect_digest` (NFR1).
- **No worker-directed digest instruction**: no worker agent prompt or worker
  contract gains a sentence telling the worker to compute, hash, verify or
  compare a digest. Sentences about digests attribute the action to the
  orchestrator or negate it. task0004's check enforces this; its exact rule
  is in that task's plan.
- **Pinned wording (NFR1)**: existing headings are never renamed; the
  sentences listed in SPEC.md NFR1 stay as they are; the full suite is run
  before completion. When an existing byte pin covers a file this feature
  must change, the pin is refreshed in place with a "Refreshed again by
  worker-digest-ownership/{task}" comment, following that test file's
  "refresh, don't remove" convention; a pin is never removed or weakened.
- **Tests**: `unittest` and the standard library only (NFR3); synthetic trees
  in temporary directories; whitespace-normalized, section-sliced document
  assertions (no full-document equality, no dependence on line-break
  positions, no fixed list of worker names). A new test file never contains
  the text `subagent_type=` followed by a quote and `em-workflow:` (only
  `tests/test_check_plugin_invariants.py` is excluded from the real-repository
  dispatch-parity scan).
- **Gate-ID scan hygiene**: new prose never puts a dotted backtick span within
  120 characters after a "gate id" / "gate_id" mention unless it is a real
  gate ID listed in `batch-policies.yaml` (the gate-ID coverage check reads
  every plugin file).
- **Language**: protocol documents in English; `skills/develop/SKILL.md` in
  Japanese, citing the owner's English section names verbatim.

## Cross-task Design Decisions

### D1: A new owner document

The digest rules span four dispatch sites, three phase-state files and the
legacy migration, so they get one neutral owner,
`references/artifact-digest.md`. `worker-envelope.md` cannot hold them (it
must not carry the token `expect_digest`), and `spec-writer-contract.md` is
one worker's contract; it keeps owning *who* verifies, while the owner
document owns *how* and *where*. Affects task0002, task0003.

### D2: Script interface (resolves SPEC.md's open question, A7)

File name `artifact-digest.py`, JSON array output, three error tokens, exit
codes 0/1/2, no options, regular files only — as pinned above. JSON keeps
paths with spaces, Japanese characters or line breaks unambiguous;
positional elements make the input/output correspondence exact even for
duplicates. Affects task0001, task0002.

### D3: Quoting rule for target paths (TM-1)

The orchestrator passes each target path as its own single-quoted shell word,
and the script path double-quoted (it contains `${CLAUDE_PLUGIN_ROOT}`). A
path containing a single quote, a line break or NUL is never put into a
command: before dispatch it counts as a mismatch, at layer 5 as an
artifact-validation failure. Owned by the owner document's `Calculation`
section (task0002).

### D4: Legacy records by equality only (FR8, TM-3)

A recorded value that differs from the new digest is compared, after
dropping an optional `sha256:` prefix, with the current file's git blob id
(the legacy method). Equal → treated as a match and superseded by the new
digest at that dispatch's layer-5 recording; otherwise → the existing
digest-mismatch branch. Length or format never decides. Applies where an
action decision compares a recorded digest (create-spec, design,
create-plan); rework's action choice is unchanged. Owned by task0002.

### D5: Each check lands with the content it validates

Tasks run fully in parallel and every worktree runs the repository-level
checker test, so a check and everything it validates sit in the same task:
the wiring check with the owner document and the site wiring (task0002), the
stance check with the agent-prompt citations (task0004). The wiring check is
driven by the owner document's `Dispatch sites` registry and does not derive
target workers; the derivation from the Applicability table and agent
frontmatter lives only in task0004. The cross-check "registry workers ⊇
derived target workers" needs both and is a verify-phase manual item (see
Open Questions).

### D6: Where the positive stance must appear

The positive stance (no `blocked` for an uncomputable digest; path-only
`written_artifacts`) is required in each target agent prompt, as citations of
the two owner stance sections. Each contract the prompt cites must cite
`references/contracts/worker-envelope.md` and must carry no worker-directed
digest instruction. This is how TS1's "agent prompt と contract … （本文または
参照で）" is checked. Affects task0004 (and task0003, which edits a cited
contract).

### D7: Scenario ID form

VERIFICATION.md uses the `TSn` form (`TS1` …) so that IDs string-match SPEC.md
and the `requirements[].tests` already recorded in workflow.yaml.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Merge conflicts in `check-plugin-invariants.py` / its test between task0002 and task0004 | High | Low | Checker extension protocol (fixed append order, separate helpers, docstring owned by one task) |
| The stance check's negative rule flags a legitimate sentence in the real repository | Medium | Medium | Rule limited to worker-addressed sentences; real-repository pass is an Acceptance Criterion |
| A doc edit breaks an existing wording/byte pin | Medium | Medium | Pinned-wording convention; full suite before completion; validator pin refresh is planned |
| Registry workers drift from the derived target workers (no automated cross-check yet) | Low | Medium | Manual verify item; follow-up noted in Open Questions |
| The orchestrator interpolates a hostile path despite the quoting rule | Low | High | TM-1 in the owner document; layer 4 runs before layer 5 |

## Open Questions

- [ ] An automated cross-check between the `Dispatch sites` registry's
      workers and the derived target workers needs both new checks merged;
      it is a manual verify item for now and a candidate follow-up task.
- [ ] "再現手順で現象が起きない" (a real create-spec re-entry with
      `replace_own`) is not executable from unit tests (A5); it is a manual
      verification item.
