# Implementation Plan: review-perspective-model-effort

## Overview
Each perspective's codex entry in `reviewers.yaml` names a model and an
effort. The effort travels the same path the model already travels
(registry → review-phase R2 → codex-reviewer Step 5 → wrapper), and the
wrapper turns it into the `model_reasoning_effort` override of `codex exec`.

## Technology Stack
- **Language / Framework**: Bash (the two `run_codex_exec.sh` wrappers), YAML
  (the two `reviewers.yaml` registries), Markdown (agent prompts, reference
  documents, READMEs, the repository skill), Python 3 standard library
  `unittest` (tests).
- **New dependencies**: none. No license check applies (`project.license:
  none`, and nothing new is introduced).

## Layer Structure
The layers, from source of truth to execution. Each layer reads only the one
above it.

1. **Registry** — `em-workflow/references/reviewers.yaml`,
   `em-review/references/reviewers.yaml`. Holds model and effort per codex
   entry (task0002).
2. **Orchestration** — both `review-phase.md` (R2 dispatch, round records;
   task0004) and both `review-protocol.md` (the reviewer input contract;
   task0003).
3. **Reviewer agent** — both `agents/codex-reviewer.md` Step 5 (task0003).
4. **Wrapper** — both `scripts/run_codex_exec.sh` (task0001). The only layer
   that validates the effort value.
5. **User documentation** — both READMEs and
   `.claude/skills/security-review-model/SKILL.md` (task0005). They describe
   layers 1–4 and are read by no other layer.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1. Registry codex entry `effort` key | Names the effort of one perspective's codex reviewer | A codex entry is one line in flow form, keys in the order `harness`, `model`, `effort`. `effort` is optional and its value is a lowercase word. A litellm entry never carries `effort`. An entry without `effort` runs at the wrapper's readonly default (xhigh). The `version:` keys (em-workflow 3, em-review 2) stay as they are. | task0002 (writes), task0004 (R2 reads it), task0005 (documents it) |
| C2. Reviewer input field `effort` | Carries the entry's effort from the orchestrator to the codex reviewer | Precondition: the dispatched entry is a codex entry carrying `effort: E`. Postcondition: the input block holds `effort: E`, the value copied verbatim, with no allow-list check. Without `effort` in the entry, the field is absent. The Claude reviewer and the litellm reviewer never receive it. It is entry-specific like `model`, so an R2b hop to a litellm entry does not carry it. | task0004 (sends it, R2), task0003 (documents it in the protocol Inputs and consumes it in Step 5) |
| C3. Wrapper option `--effort LEVEL` | Sets the reasoning effort of one launch | Precondition: the option appears among the options before the prompt, in any order with `-C`, `--output-schema`, `-m` and (em-workflow only) `--litellm`. Postcondition: when LEVEL matches `^[a-z]+$`, the launch argv holds exactly one adjacent pair `-c` / `model_reasoning_effort="LEVEL"`, at the position the readonly xhigh pair takes today, and no xhigh pair; this holds in readonly, in readwrite, and on em-workflow's `--litellm` route. A repeated option uses its last value. A missing value or a non-matching value exits 1, writes one stderr line and launches nothing. Without the option, the argv is unchanged from today: readonly has one xhigh pair, readwrite has none. Both copies behave identically. | task0001 (implements), task0003 (codex-reviewer passes `--effort "<effort>"`), task0005 (documents it) |
| C4. codex-reviewer Step 5 invocation lines | The fenced wrapper lines other tests pin byte for byte | The fenced lines in Step 5 stay byte-identical. The effort is described in prose, the way `model` is: added right before `"$PROMPT"` when supplied. | task0003 |
| C5. Shared test module `tests/test_codex_wrapper_model_flag.py` | Holds both the wrapper-side tests and the registry-side tests | task0001 owns the wrapper half: the stub runner, `ModelFlagTest`, and the new effort test classes. task0002 owns the registry half: the chain-entry pattern, the codex-entry reader and the class that replaces `SecurityModelPinTest`. Each task edits only its own half and the docstring lines about that half. Merge conflicts between the halves are settled by the parent-side-adoption protocol. | task0001, task0002 |

## Conventions
- **Copies stay parallel.** Where em-workflow and em-review hold the same
  passage (wrappers, codex-reviewer Step 5, protocol Inputs, R2 bullets,
  record comments), the new text is the same in both copies. It differs only
  where the surrounding text already differs between the two copies.
- **Pinned tests (NFR6).** A test that pins a hash or a literal of a changed
  file is updated in place: the new value replaces the old one, and a comment
  is added that starts with `Refreshed by
  feature-docs/review-perspective-model-effort/tasks/taskNNNN.md`, names the
  requirement IDs, and says what changed. No pin is removed or loosened, and
  no pinned range is narrowed to avoid the refresh.
- **Tests (NFR4).** Standard library only. No real `codex`: wrapper tests
  put a stub named `codex` on `PATH`, as `tests/test_codex_wrapper_model_flag.py`
  already does. Every new matcher has a negative proof on forged input.
- **Languages.** Agent prompts, reference documents, shell comments and tests
  are written in English. The READMEs and the repository skill keep their
  existing Japanese.
- **Version (NFR5).** Only task0006 changes a version. No other task touches
  `plugin.json` or `.claude-plugin/marketplace.json`.

## Cross-task Design Decisions

### D1. Effort reuses the model's path
The effort is passed exactly where `model` is passed: registry entry →
R2 input block → Step 5 argument → wrapper option. No new mechanism, no new
skip reason, no new Step 6 rule. A Codex rejection of the value falls under
the existing Step 6 non-JSON rule (`harness_unavailable`), so the chain moves
to its next entry. Affects task0002, task0003, task0004.

### D2. The wrapper is the only validator
The orchestrator passes the value verbatim with no allow-list (FR7). The
wrapper alone checks `^[a-z]+$` before embedding the value in TOML (NFR2,
THREAT-MODEL.md TM-1). Affects task0001, task0004.

### D3. Defaults do not move
Without `--effort`, the launch argv is the same as today on every route
(NFR1). Readonly keeps its xhigh pair; readwrite gets no effort pair. Callers
other than codex-reviewer (they pass no `--effort`) see no change. Affects
task0001.

### D4. Untouched ranges
- `em-workflow/references/review-protocol.md`'s harness-description bullets
  (the `PROTOCOL_BULLETS_SHA256` range) are not changed (FR7).
- codex-reviewer Steps 0–4 and Step 6 are not changed; only Step 5 prose is.
- review-phase R2b and R4 text is not changed: their "same input block"
  sentences already cover the new field (SPEC A2).

### D5. Wrapper code keeps one launch
In each wrapper, the text `codex exec` appears in exactly one non-comment
line (the launch), as `tests/test_codex_wrapper_timeout_alignment.py`
requires. New error and usage lines do not contain that text. Affects
task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A hash or literal pin of a changed file is not refreshed | Medium | Full suite fails at verify | Each task plan lists the pins its files feed; every task runs `python3 -m unittest discover -s tests` |
| task0001 and task0002 both edit `tests/test_codex_wrapper_model_flag.py` | High | Merge conflict | C5 splits the module into halves; parent-side adoption settles the rest |
| A slug or effort in the FR2 table is not accepted by Codex (SPEC A7) | Medium | That perspective's codex run skips with `harness_unavailable` and the chain moves on | Accepted by SPEC; not verified in this feature |
| A wrapper change alters the no-`--effort` argv | Low | Other callers' launches change | D3; existing argv tests stay unedited and must pass |

## Open Questions
- [ ] `em-workflow/references/review-evaluation-contract.md` describes
      `perspectives_dispatched` entries as carrying `model` for litellm runs
      only, and does not mention `effort`. SPEC FR8 does not list that file,
      so this plan leaves it unchanged.
- [ ] After task0002, `tests/test_codex_wrapper_model_flag.py` also pins the
      security model. The security-review-model skill's update procedure
      (step 5) lists two test files and not this one. SPEC FR10 does not ask
      for that list to change, so this plan leaves it as it is.
