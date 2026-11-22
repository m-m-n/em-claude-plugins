# Implementation Plan: version-bump-missing-base

## Overview
Change the push-time base determination of `.github/workflows/plugin-version-bump.yml` so that a push whose base commit is unavailable still bumps changed plugins, add a workflow_dispatch path that recovers a lost bump, keep the plugin-dev template byte-identical to the workflow, add a repository-held ruleset definition that forbids non-fast-forward updates of main, and document the post-merge steps (SPEC.md FR1-FR10, NFR1-NFR5).

## Technology Stack
- **GitHub Actions workflow (YAML)** - triggers, ref guard, checkout, environment wiring, the existing pull request create/merge steps.
- **Python 3 standard library + git** - the single heredoc script inside the workflow (NFR1).
- **Python standard library unittest** - regression tests under `tests/`, run by `python3 -m unittest discover -s tests`.
- **GitHub REST API rulesets endpoint through gh** - used only in the documented human procedure; never called by the workflow or the tests.
- **New dependencies**: none. `project.license` is `none`, so there is no license constraint and no dependency license to record.

## Layer Structure
| Layer | Location | Responsibility | May depend on |
|-------|----------|----------------|---------------|
| Workflow wiring | the workflow YAML outside the heredoc | triggers, ref guard, checkout depth, mapping of event values and dispatch inputs to environment variables, pull request create/merge steps | the script layer, only through environment variables in and GITHUB_OUTPUT out |
| Script | the single heredoc in the workflow | base determination, changed-plugin detection, version comparison, dispatch validation, JSON writes, the `bumped` output | git, the repository's JSON files, environment variables |
| Repository data | `<plugin>/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.github/rulesets/main-non-fast-forward.json` | data read and written | nothing |
| Tests | `tests/` | read the workflow, template and ruleset files; run the extracted heredoc in temporary repositories | those files, read-only; never the live repository's git state |
| Documents | `README.md`, `.github/rulesets/README.md`, `plugin-dev/skills/plugin-dev/references/create.md` | describe C1 and the post-merge procedure | C1, C2, C3 (descriptive only) |

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1 version-bump workflow behavior | the observable behavior of `.github/workflows/plugin-version-bump.yml` and its byte-identical template | "C1 contract" below | task0001 (implements), task0003 (describes it in create.md and in the README procedure) |
| C2 ruleset definition file | the repository-held definition of the non-fast-forward ruleset | "C2 contract" below | task0002 (implements), task0003 (refers to it through C3) |
| C3 post-merge procedure split | where each part of the human procedure lives | (a) ruleset creation and confirmation lives in `.github/rulesets/README.md`; (b) workflow_dispatch recovery and (c) cache confirmation live in the maintenance section of the root `README.md`, which points to (a) by that repository-relative path and does not restate it | task0002 (writes (a)), task0003 (writes (b), (c) and the pointer) |
| C4 test conventions | how new test modules are placed and isolated | "C4 contract" below | task0001, task0002 |

### C1 contract
Triggers and guard:
- push to main (the existing trigger), and workflow_dispatch with two required string inputs: `plugin` (a plugin name registered in `.claude-plugin/marketplace.json`) and `min_version` (MAJOR.MINOR.PATCH, each a non-negative integer).
- Under workflow_dispatch the version-update step runs only when the ref is main.

Push outcomes (BEFORE = the push event's before value, AFTER = the pushed commit):
1. BEFORE is 40 hexadecimal characters, not all zeros, and present in the clone: the base is BEFORE.
2. BEFORE has that form but is absent from the clone: one fetch of BEFORE from origin is attempted; on success the base is BEFORE.
3. The fetch fails, or BEFORE is all zeros, or BEFORE is not 40 hexadecimal characters: the base is AFTER's first parent, and a stdout line starting with `::warning::` states the fallback. Processing continues.
4. AFTER has no first parent either: non-zero exit; no file changes.
5. No path ends with exit 0 because the base commit is unavailable.

Changed plugins: for each file in the difference between the base and AFTER, the nearest ancestor directory that contains `.claude-plugin/plugin.json`.

Comparison per changed plugin (versions at the base and at AFTER, compared as integer triples):
- AFTER lower than or equal to the base: the new version is the greater of the two with its patch raised by 1, written to the plugin's plugin.json and to the same-named marketplace entry when that entry carries a version.
- AFTER higher than the base: unchanged.
- No plugin.json at the base (a new plugin), or either version not in MAJOR.MINOR.PATCH form: unchanged.
- A marketplace entry without a version is never rewritten.

workflow_dispatch outcomes:
- `plugin` not registered, or `min_version` not in MAJOR.MINOR.PATCH form: non-zero exit; no file changes.
- Current version lower than or equal to `min_version`, with equal major and minor: `min_version` with its patch raised by 1 is written to plugin.json and to the marketplace entry (when it carries a version).
- Current version lower than or equal to `min_version`, with a different major or minor: non-zero exit; no file changes (A2).
- Current version higher than `min_version`: no file changes; exit 0; `bumped` empty.

Output and merge:
- GITHUB_OUTPUT key `bumped`: the bumped plugins as `name@version`, separated by commas; empty when nothing was bumped.
- The existing pull request create/merge steps run whenever `bumped` is non-empty, for both triggers (A3).
- Every non-zero exit prints a message naming its reason (SPEC.md Error Codes ERR_001-ERR_004).

### C2 contract
- Path: `.github/rulesets/main-non-fast-forward.json`.
- Shape: the GitHub REST API repository ruleset creation payload (A4).
- Content: name `main-non-fast-forward`; target branch; enforcement active; bypass_actors an empty list; the ref-name condition includes exactly `refs/heads/main` and excludes nothing; rules hold exactly one rule, of type non_fast_forward.

### C4 contract
- New test modules live in `tests/` as `test_*.py`, use only the Python standard library, are found by `python3 -m unittest discover -s tests`, and follow the module conventions of the existing tests there. Each task has its own module; no helper module is shared between tasks.
- A test locates the repository root from its own file's location, never from the current working directory or an environment value.
- Isolation (NFR3): every git operation runs inside a per-test temporary directory; remotes are bare repositories inside that directory; the subprocess environment is built explicitly, with HOME and git's global configuration pointing into the temporary directory, git's system configuration disabled, terminal prompts disabled, and no inherited GITHUB_* values; nothing under `~/.claude` is read; no network is used.
- Temporary repositories set their initial branch name and author identity explicitly, so results do not depend on the machine's git configuration.

## Conventions
- **Version handling**: this repository is exempt (`.github/workflows/plugin-version-bump.yml` exists). No task changes a version field in any plugin.json or in `.claude-plugin/marketplace.json` (NFR4). After merge, Actions raises plugin-dev's patch (A8).
- **No concrete version values** in SPEC, plans or acceptance criteria (NFR5). The one concrete value this feature writes is `min_version` in the README procedure (b) (A6).
- **Document language**: every edited document keeps its existing language and style.

## Cross-task Design Decisions

### D1: workflow, template and workflow tests form one task
FR6 requires byte identity between the workflow and the template, and NFR2 puts all logic in one heredoc. Splitting this work across parallel tasks would have two tasks rewrite the same script. Affected: task0001.

### D2: the new ruleset is separate from the existing main ruleset
The new ruleset is named `main-non-fast-forward` (matching the file stem), targets only `refs/heads/main`, and is created as a new ruleset. The existing ruleset named main is never edited (A9). Affected: task0002 (definition and procedure), task0003 (refers to it).

### D3: post-merge procedure split
Follows SPEC.md A5, pinned as C3. Affected: task0002, task0003.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| When a dropped Actions update commit cannot be fetched, the first-parent fallback can produce the same version that commit recorded, so an installed cache holding that version is not refreshed | Medium | Medium | workflow_dispatch recovery (FR4) documented in README procedure (b); the ruleset (FR7) prevents the history replacement that causes it |
| Text-level checks of the workflow YAML in tests are sensitive to formatting | Medium | Low | checks stay narrow (heredoc count, absence of Actions expressions in the heredoc, named inputs, ref guard, step conditions) and their failure messages name the missing element |
| Fetching a commit by id behaves differently on GitHub than on a local bare repository | Low | Medium | tests cover both outcomes (commit served and not served); both lead to a bump |
| The ruleset definition passes the tests but is rejected by the GitHub API | Low | Medium | the definition follows the REST API creation payload; procedure (a) confirms the created ruleset |

## Open Questions
- [ ] workflow_dispatch when the target plugin's current version is not in MAJOR.MINOR.PATCH form: SPEC.md does not state the outcome; task0001 treats it as a non-zero exit with no file change.
- [ ] A changed plugin whose plugin.json is absent at AFTER (a removed plugin): SPEC.md does not state the outcome; task0001 does not bump it, since there is no file to write.
