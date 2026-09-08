# Implementation Plan: muse-spark-contributor-consent

## Overview

Ship a code-enforced, per-repository consent gate for the `muse-spark-contributor`
tier: a PreToolUse(Bash) guard denies contributor-tier invocations in repositories
whose consent was never recorded, an out-of-band CLI plus an interactive skill are
the only ways consent is granted or revoked, and the judgment that cannot be
mechanized is written into both plugins' review registry / protocol documents as
pre-dispatch criteria.

## Technology Stack

- **Language**: Python 3, standard library only — the guard script (hook path and
  CLI path) and every test module.
- **Documents**: Markdown and YAML inside both plugin trees (`skills/`,
  `references/`, `.claude-plugin/`).
- **New third-party dependencies**: none. No package is added by this feature, so
  no dependency license has to be reconciled. `project.license` is `none`
  (no constraint) and is not changed by any task.

## Layer Structure

Five layers. Each depends only on the contract named in Shared Components, never
on another layer's internals.

1. **Enforcement** — the guard's hook path. Input: the PreToolUse payload and the
   consent store on disk. Output: a deny decision or no decision. Read-only with
   respect to the store; performs no network access and no LLM call.
2. **Grant** — the guard's CLI path. The *only* writer of the consent store.
   Never invoked by the hook path and never invoked by the workflow itself.
3. **Interaction** — the `contributor-consent` skill. Depends on the CLI contract
   only; it never reads or writes the store file directly.
4. **Registration** — each plugin's `hooks/hooks.json`. Depends on the script's
   in-plugin path and on the verbatim command form.
5. **Written criteria** — each plugin's `references/reviewers.yaml` and
   `references/review-phase.md`. Depends on nothing executable; read by a
   dispatching LLM before it dispatches a reviewer.

Prohibited directions: Enforcement never depends on Interaction or on Written
criteria; Interaction never bypasses Grant to touch the store; **no shared Python
module is extracted across the two plugins** — the two script copies are
duplicated deliberately (FR1).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Consent store file | Records, as presence only, which repositories consented | Path `~/.claude/em-workflow/muse-consent.json`, overridable by the `EM_WORKFLOW_MUSE_CONSENT` environment variable (test use). Shape: a mapping with a `version` field whose value is the string `1` and a `projects` mapping; each project key maps to an object whose **only** field is `updated_at`, an RFC 3339 timestamp with an explicit UTC offset at seconds precision. Presence of a project key *is* the consent. **Reader precondition**: none — missing, unreadable, invalid-JSON, or wrong-shaped (not a mapping, or `projects` not a mapping) all mean "no consent for any project", with no repair and no write. **Writer postcondition**: the file is replaced atomically (write a temporary file in the same directory, then replace), parent directories are created when absent, serialization is 2-space indented with sorted keys, non-ASCII left unescaped, and a trailing newline; no field other than `updated_at` is ever written under a project key. | task0001 (implements both sides), task0002 (documents it; never touches it directly) |
| Project key derivation | Maps a directory to the repository-level consent key | Identical in rule to the existing `bash_guard` project-key routine: the git common directory of the caller's directory in absolute form; when git is unavailable or the directory is not inside a repository, the fully symlink-resolved absolute path of the directory. Consequence, and part of the contract: every worktree of one repository resolves to one key, and a non-repository directory referenced through a symlink resolves to the same key as its real path. | task0001 (implements), task0002 (shows the resolved subject of consent to the user) |
| Guard CLI | The out-of-band grant / revoke / inspect interface | Exactly one of `--record`, `--remove`, `--list` is required and they are mutually exclusive; `--project-dir DIR` is required for all three. `--list`: prints the project key **alone on one line** when consent exists and prints nothing when it does not; exit 0 either way — this is the only machine-parsed output in the feature, so it carries no label, prefix or timestamp. `--record`: idempotent; refreshes `updated_at`, prints one line naming the recorded key, and has no "already recorded" variant. `--remove`: removes the key entirely (never leaves an empty object) and prints one line; when the key was absent it says so and exits 0 with the store untouched and not created. Results go to stdout, errors to stderr. Exit 0 on success, 1 on runtime failure (store malformed on a mutating command, write failure), 2 on argument misuse. On a malformed store a mutating command writes nothing and fails loudly rather than rewriting the file. | task0001 (implements), task0002 (invokes and documents it) |
| Deny payload | What the enforcement layer returns when consent is absent | One JSON object on stdout carrying exactly four inner fields under `hookSpecificOutput`: the event name, the decision `deny`, a human-facing reason, and an agent-facing additional context. No further diagnostic fields. Every one of those strings is a **single-line** string containing no newline. On every non-deny path stdout receives **zero bytes** (not an empty object, not a newline) and the process exits 0. The two strings are module-level constants; nothing from the input — the command, the working directory, the derived project key, the store path or any store content — is interpolated into them. | task0001 |
| Hook registration form | How the script is wired into each plugin | Registered under the `PreToolUse` event with matcher `Bash`; the command entry is exactly `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/muse_guard.py` with `timeout` 15; positioned **before** the destructive-guard entry so that guard's blanket allow cannot terminate the decision first. Identical verbatim form and timeout in both plugins. | task0001 |
| Plugin slug constant | The single permitted divergence between the two script copies | One module-level constant naming the owning plugin, used in exactly one place: the skill reference inside the agent-facing deny text. A diff of the two copies shows exactly that one changed line and nothing else. | task0001 |
| Interactive-question budget | Guarantees the unattended path gains no new gate | No develop-phase or review-phase document in either plugin gains an occurrence of the interactive-question tool name relative to the base revision. The new `contributor-consent` skill document is outside this pinned set and is referenced by no develop-phase document. | task0002 and task0003 must not increase it; task0005 pins and verifies it |
| Review chain immutability | Guarantees the registry keeps choosing the non-contributor tier | Every perspective's primary chain in both plugins' `reviewers.yaml` stays byte-identical to the base revision; no chain entry names the contributor tier; the em-workflow registry still contains no `cross_validation` literal. New prose goes only where the registry's restricted parser tolerates it (the header comment block, or outside the perspectives block). | task0003 |
| Version identity | Keeps installed caches from serving stale plugin files | For each plugin, the version in `<plugin>/.claude-plugin/plugin.json` equals the version in that plugin's entry in the repository-root `.claude-plugin/marketplace.json`, and both are greater than the base revision's value. | task0004 only — no other task edits a version field |

## Conventions

- **Message language and register**: Japanese prose; identifiers stay verbatim
  ASCII (`muse-spark-contributor`, `muse_guard.py`, `--record`, the store path).
  Plain form (常体) unless the existing guard family's messages use 敬体, in which
  case the existing family's register wins (see Open Questions, O1). Register is
  the only thing that may change — clause structure and content stay as specified
  in the task plans.
- **No decoration**: no emoji, no ANSI color, no box drawing, no bullet glyphs
  beyond a plain hyphen. One statement per line.
- **No input echo**: no user-facing string produced by the guard ever quotes back
  any part of the inspected command. A crafted command string must not become
  agent-visible instruction text.
- **Error-handling policy (enforcement layer)**: fail open. Anything the guard
  cannot classify with confidence yields no decision, exit 0, empty stdout. The
  guard never emits `ask` and never emits `allow` — `ask` is downgraded to `deny`
  in unattended runs and would stall them.
- **Error-handling policy (grant layer)**: fail loud. A malformed store aborts a
  mutating command with a stderr message and a non-zero exit rather than being
  repaired, because repairing it would silently discard other repositories'
  consent entries.
- **Tests**: every test module in this feature lives in the repository-root
  `tests/` directory and is picked up by `python3 -m unittest discover -s tests`.
  Standard library only. No test reads or writes the real `~/.claude` state — the
  store path override is set to a path under a temporary directory in every case.
  **No file is added under either plugin's `hooks/tests/`** for this feature; the
  case-runner style used by the destructive guard is deliberately not replicated.
- **Fixed new test module names** (so parallel tasks cannot collide):
  `tests/test_muse_guard.py`, `tests/test_muse_guard_registration.py`,
  `tests/test_contributor_consent_skill.py`,
  `tests/test_contributor_tier_criteria.py`,
  `tests/test_muse_consent_version_bump.py`,
  `tests/test_muse_consent_no_new_questions.py`.
- **Shared-file etiquette**: `em-review/.claude-plugin/plugin.json` may be touched
  by two tasks. Each task edits only its own field — task0004 edits the version,
  task0001 touches it only if hook discovery requires the manifest to declare the
  hooks file. Neither reformats the file.

## Cross-task Design Decisions

### D-A: Two verbatim copies, one named divergence

Both plugins carry their own `muse_guard.py`; no shared module is extracted. The
only byte-level divergence is the plugin-slug constant. Rationale: a plugin cache
is materialized per plugin, so a shared module would have no location either
plugin could import from; making the carve-out one named constant makes the
"identical except where it names its own plugin" rule mechanically checkable.
Affected: task0001.

### D-B: Read-only enforcement, sole-writer grant

The hook path never creates, repairs or writes the store; the CLI path is the only
writer and refuses to repair a malformed store. Rationale: one file must not be
self-healing on one path and inert on the other, and one repository's `--record`
must never delete another repository's consent. Affected: task0001, and task0002
which must not work around a `--record` failure.

### D-C: Registration ships with the script, in one task

The two `hooks.json` edits, the ordered-guard constant update, and the registration
invariants live in the same task as the script itself. Rationale: repository-wide
hook invariants assert that every registered script exists and is executable, so a
worktree that registers a script it does not contain cannot pass its own test run.
This is the reason task0001 is larger than the other tasks. Affected: task0001.

### D-D: One-versus-three rendered as two headed lists

The single per-dispatch "do not use" item and the three "outside the scope of
consent" conditions appear under two distinct headings with fixed bullet counts,
never merged and never interleaved, so a verifier can count bullets per heading.
The third out-of-scope condition is phrased as a present-state test applied at
dispatch time, never as a comparison against a value recorded when consent was
given — the store holds no such value. Affected: task0003.

### D-E: No design tokens, no token sheet, no mockups

The design step deliberately produced no token file and no mockup: every surface
in this feature is terminal text, a JSON payload consumed by the permission
system, or a document read by an LLM. The design decisions that do exist are
wording and output-shape decisions, and they are carried into the task plans as
literal message content. Nothing in this feature is compared against a mockup.
Affected: all tasks (nobody creates `design-system/` files).

### D-F: The interactive-question baseline is a literal, and the assertion is "not increased"

The verifying test carries a literal table of per-file occurrence counts taken from
the base revision, and asserts that no file's current count exceeds its pinned
value, plus that no file outside the table contains any occurrence. The new
`contributor-consent` skill document is the single documented exclusion.
Rationale: recomputing the baseline from the same tree at test time would be
tautological, and a "not increased" comparison stays green when unrelated text is
removed. Affected: task0005 (owns it), task0002 and task0003 (must not increase it).

### D-G: Version bump is owned by exactly one task

Only task0004 edits a version field, in both plugins and in the marketplace entry,
in one coherent change. Rationale: two tasks bumping independently would produce
conflicting values for the same plugin. Affected: task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The command matcher misreads a mere mention (quoted string, search pattern argument, here-document body) as an invocation and denies a legitimate command | Medium | High — a misfire stalls an unattended run outright | Boundary-aware matching in both directions plus a dedicated non-invocation test group; the fail-open default means an unclassifiable command yields no decision |
| The command matcher misses an invocation spelling the harness actually uses | Medium | High — the gate silently does not hold | Every spelling the harness emits is enumerated as its own test case (bare and equals forms, each with and without quoting) |
| A registered-but-absent script breaks repository-wide hook invariants mid-integration | Low | Medium | D-C keeps registration and script in one task |
| An added sentence in a review-phase document mentions the interactive-question tool and trips the budget test | Medium | Low | Stated as a convention and verified by task0005; the assertion is per file and directional |
| The two script copies drift apart over the two files' authoring | Medium | Medium | D-A reduces the permitted divergence to one constant and a test compares the copies |
| The registry's restricted parser rejects newly added prose | Medium | Medium | Prose is confined to the tolerated locations, and the chain-pinning test runs against both plugins |
| The existing ordered-guard constant and other hook invariant tests encode assumptions this feature breaks | Medium | Medium | task0001 owns updating that constant and re-running the existing hook invariant tests |

## Open Questions

- [ ] **O1 — Register of the guard's messages.** The existing guard family's deny
      and ask messages were not available as an input to planning. Resolved at
      implementation by task0001: read the messages the existing bash guard and
      destructive guard already emit; if they use 敬体, match them and adjust the
      guard's two message strings accordingly. Consistency with the existing family
      outranks the plain-form default; only the register changes.
- [ ] **O2 — Exact invocation of the LiteLLM availability probe.** The probe is
      already defined in each plugin's review-phase document, which was not an
      input to planning. Resolved at implementation by task0002: invoke the probe
      exactly as that document defines it, per plugin, rather than reimplementing
      it inside the skill.
- [ ] **O3 — How "exactly three facts" is counted.** The skill shows a subject line
      above the three facts, and a naive count of labeled lines could read four.
      Resolved at implementation by task0002: present the three facts as one
      explicitly labeled group with the subject line described separately as the
      target of consent; if review or verify still reads it as a fourth fact, drop
      the subject line — the three facts are requirement-fixed, the subject line is
      not.
