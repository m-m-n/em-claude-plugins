# Implementation Plan: muse-spark-contributor-consent

## Overview

Ship a code-enforced, per-repository consent gate for the `muse-spark-contributor`
tier. The gate has **two enforcement surfaces**: a PreToolUse(Bash) guard that denies
contributor-tier invocations in repositories whose consent was never recorded, and a
consent-write CLI that refuses to touch the store unless its standard input is an
interactive terminal. Consent is granted or revoked only out of band — an interactive
skill presents the command and the user runs it in their own terminal. The judgment
that cannot be mechanized is written into both plugins' review registry / protocol
documents as pre-dispatch criteria.

This is the second planning pass. Tasks task0001–task0006 are merged; task0007–task0009
carry the work the amended SPEC added (the consent-write provenance boundary, FR7 / FR13)
and the work verify found still open (quote-unaware command splitting, FR4 / FR5).

## Technology Stack

- **Language**: Python 3, standard library only — the guard script (hook path and
  CLI path) and every test module. The shell-lexing, terminal-detection and
  pseudo-terminal facilities the new tasks need are all standard library.
- **Documents**: Markdown and YAML inside both plugin trees (`skills/`,
  `references/`, `.claude-plugin/`).
- **New third-party dependencies**: none. No package is added by this feature, so
  no dependency license has to be reconciled. `project.license` is `none`
  (no constraint) and is not changed by any task.

## Layer Structure

Five layers. Each depends only on the contract named in Shared Components, never
on another layer's internals.

1. **Enforcement (hook)** — the guard's hook path. Input: the PreToolUse payload and
   the consent store on disk. Output: a deny decision or no decision. Read-only with
   respect to the store; performs no network access and no LLM call.
2. **Enforcement (grant)** — the guard's CLI path. The *only* writer of the consent
   store, and itself gated on an interactive standard input. Never invoked by the hook
   path, never invoked by the workflow, and never invoked by the skill for its two
   mutating commands.
3. **Interaction** — the `contributor-consent` skill. Reads state through the CLI's
   read-only command and hands the user the mutating command to run themselves; it
   never reads or writes the store file directly and never runs a mutating command.
4. **Registration** — each plugin's `hooks/hooks.json`. Depends on the script's
   in-plugin path and on the verbatim command form.
5. **Written criteria** — each plugin's `references/reviewers.yaml` and
   `references/review-phase.md`. Depends on nothing executable; read by a
   dispatching LLM before it dispatches a reviewer.

Prohibited directions: Enforcement never depends on Interaction or on Written
criteria; Interaction never bypasses Grant to touch the store, and never performs a
Grant-layer mutation on the user's behalf; **no shared Python module is extracted
across the two plugins** — the two script copies are duplicated deliberately (FR1).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Consent store file | Records, as presence only, which repositories consented | Path `~/.claude/em-workflow/muse-consent.json`, overridable by the `EM_WORKFLOW_MUSE_CONSENT` environment variable (test use). Shape: a mapping with a `version` field whose value is the string `1` and a `projects` mapping; each project key maps to an object whose **only** field is `updated_at`, an RFC 3339 timestamp with an explicit UTC offset at seconds precision. Presence of a project key *is* the consent. **Reader precondition**: none — missing, unreadable, invalid-JSON, or wrong-shaped (not a mapping, or `projects` not a mapping) all mean "no consent for any project", with no repair and no write. **Writer postcondition**: the file is replaced atomically (write a temporary file in the same directory, then replace), parent directories are created when absent, serialization is 2-space indented with sorted keys, non-ASCII left unescaped, and a trailing newline; no field other than `updated_at` is ever written under a project key. | task0001 (implements both sides), task0008 (adds the write-path precondition below, changes nothing else), task0002 / task0009 (document it; never touch it directly) |
| Project key derivation | Maps a directory to the repository-level consent key | Identical in rule to the existing `bash_guard` project-key routine: the git common directory of the caller's directory in absolute form; when git is unavailable or the directory is not inside a repository, the fully symlink-resolved absolute path of the directory. Consequence, and part of the contract: every worktree of one repository resolves to one key, and a non-repository directory referenced through a symlink resolves to the same key as its real path. | task0001 (implements), task0002 / task0009 (show the resolved subject of consent to the user) |
| Guard CLI | The out-of-band grant / revoke / inspect interface | Exactly one of `--record`, `--remove`, `--list` is required and they are mutually exclusive; `--project-dir DIR` is required for all three. `--list`: prints the project key **alone on one line** when consent exists and prints nothing when it does not; exit 0 either way — this is the only machine-parsed output in the feature, so it carries no label, prefix or timestamp. `--record`: idempotent; refreshes `updated_at`, prints one line naming the recorded key, and has no "already recorded" variant. `--remove`: removes the key entirely (never leaves an empty object) and prints one line; when the key was absent it says so and exits 0 with the store untouched and not created. Results go to stdout, errors to stderr. Exit 0 on success, 1 on runtime failure (store malformed on a mutating command, write failure), 2 on argument misuse. On a malformed store a mutating command writes nothing and fails loudly rather than rewriting the file. | task0001 (implements), task0008 (adds the provenance precondition below), task0002 / task0009 (invoke the read-only command and document all three) |
| **Consent-write provenance boundary** | Restricts which invocations of the CLI may change the store | Precondition on `--record` and `--remove` only: the process's **standard input is an interactive terminal**. When it is not, the command changes nothing and exits non-zero, printing to stderr one Japanese line stating that it must be run from an interactive terminal. The refusal is evaluated **before** project-key derivation and before any store access, so the refusing run creates no store file, repairs none, and leaves an existing store byte-identical. `--list` is explicitly **outside** this precondition: it works regardless of the standard-input kind and remains callable by an agent. The interactive-terminal test is a provenance proxy, not proof of human operation (SPEC a12) — the boundary it establishes is "an agent's ordinary Bash call path cannot record consent", not unbypassability. | task0008 (implements and tests both sides), task0009 (relies on it: the skill presents the mutating command instead of running it) |
| **Command recognition** | Decides whether a Bash command string invokes the contributor tier | Input: the raw command string. Output: exactly one of "invokes the contributor tier" or "does not / cannot be classified". **Splitting into commands must happen only after shell quoting has been honoured**: a separator character (statement separator, pipe, background, boolean operators, newline) inside a single- or double-quoted region is ordinary text, never a boundary. A quoted region is a single argument token, and is re-examined as command text **only** in the two roles where a shell would execute it: the argument that follows a nested shell's command-string flag, and the body of a command substitution. Recognition of a model-selection argument compares its value to the tier name by exact equality after quote removal, in both directions (the plain tier never matches the contributor tier and vice versa). Anything the recognizer cannot classify with confidence produces "does not", never an exception and never a decision. The whole contract is a pure function of the command string: no subprocess, no file access, no network. | task0007 (owns it), task0008 (must not change it) |
| Deny payload | What the enforcement layer returns when consent is absent | One JSON object on stdout carrying exactly four inner fields under `hookSpecificOutput`: the event name, the decision `deny`, a human-facing reason, and an agent-facing additional context. No further diagnostic fields. Every one of those strings is a **single-line** string containing no newline. On every non-deny path stdout receives **zero bytes** (not an empty object, not a newline) and the process exits 0. The two strings are module-level constants; nothing from the input — the command, the working directory, the derived project key, the store path or any store content — is interpolated into them. | task0001 (owns the text); task0007 / task0008 must leave it unchanged |
| Hook registration form | How the script is wired into each plugin | Registered under the `PreToolUse` event with matcher `Bash`; the command entry is exactly `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/muse_guard.py` with `timeout` 15; positioned **before** the destructive-guard entry so that guard's blanket allow cannot terminate the decision first. Identical verbatim form and timeout in both plugins. | task0001 |
| Plugin slug constant | The single permitted divergence between the two script copies | One module-level constant naming the owning plugin, used in exactly one place: the skill reference inside the agent-facing deny text. A diff of the two copies shows exactly that one changed line and nothing else. Every task that edits either copy re-establishes this on both. | task0001, task0007, task0008 |
| Interactive-question budget | Guarantees the unattended path gains no new gate | No develop-phase or review-phase document in either plugin gains an occurrence of the interactive-question tool name relative to the base revision. The two `contributor-consent` skill documents are outside this pinned set and are referenced by no develop-phase document. | task0002, task0003 and task0009 must not increase it; task0005 pins and verifies it |
| Review chain immutability | Guarantees the registry keeps choosing the non-contributor tier | Every perspective's primary chain in both plugins' `reviewers.yaml` stays byte-identical to the base revision; no chain entry names the contributor tier; the em-workflow registry still contains no `cross_validation` literal. New prose goes only where the registry's restricted parser tolerates it (the header comment block, or outside the perspectives block). | task0003 |
| Version identity | Keeps installed caches from serving stale plugin files | For each plugin, the version in `<plugin>/.claude-plugin/plugin.json` equals the version in that plugin's entry in the repository-root `.claude-plugin/marketplace.json`, and both are greater than the base revision's value. Already satisfied within this feature's change set. | task0004 only — no other task edits a version field |

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
- **Error-handling policy (hook layer)**: fail open. Anything the guard
  cannot classify with confidence yields no decision, exit 0, empty stdout. The
  guard never emits `ask` and never emits `allow` — `ask` is downgraded to `deny`
  in unattended runs and would stall them. Widening recognition never converts a
  mention into a deny: every widening is paired with the mention that must stay
  undecided.
- **Error-handling policy (grant layer)**: fail loud. A malformed store aborts a
  mutating command with a stderr message and a non-zero exit rather than being
  repaired, because repairing it would silently discard other repositories'
  consent entries. The provenance refusal (non-interactive standard input) is the
  one refusal that precedes even reading the store.
- **Tests**: every test module in this feature lives in the repository-root
  `tests/` directory and is picked up by `python3 -m unittest discover -s tests`.
  Standard library only. No test reads or writes the real `~/.claude` state — the
  store path override is set to a path under a temporary directory in every case.
  **No file is added under either plugin's `hooks/tests/`** for this feature; the
  case-runner style used by the destructive guard is deliberately not replicated.
- **Interactive-terminal tests**: any test that must exercise a successful
  `--record` / `--remove` allocates a pseudo-terminal for the child's standard
  input with the standard library facility for that purpose; any test that must
  exercise the refusal gives the child an ordinary pipe. Both shapes are standard
  library only (NFR6).
- **Fixed new test module names** (so parallel tasks cannot collide):
  `tests/test_muse_guard.py`, `tests/test_muse_guard_registration.py`,
  `tests/test_contributor_consent_skill.py`,
  `tests/test_contributor_tier_criteria.py`,
  `tests/test_muse_consent_version_bump.py`,
  `tests/test_muse_consent_no_new_questions.py`.
  The second planning pass introduces **no new test module** — its scenarios land
  in the two modules already listed above.
- **Shared-file etiquette**: `em-review/.claude-plugin/plugin.json` may be touched
  by two tasks. Each task edits only its own field — task0004 edits the version,
  task0001 touches it only if hook discovery requires the manifest to declare the
  hooks file. Neither reformats the file. The guard script and its test module are
  governed by the stricter rule in D-J below.

## Cross-task Design Decisions

### D-A: Two verbatim copies, one named divergence

Both plugins carry their own `muse_guard.py`; no shared module is extracted. The
only byte-level divergence is the plugin-slug constant. Rationale: a plugin cache
is materialized per plugin, so a shared module would have no location either
plugin could import from; making the carve-out one named constant makes the
"identical except where it names its own plugin" rule mechanically checkable.
Affected: task0001, task0007, task0008.

### D-B: Read-only enforcement, sole-writer grant

The hook path never creates, repairs or writes the store; the CLI path is the only
writer and refuses to repair a malformed store. Rationale: one file must not be
self-healing on one path and inert on the other, and one repository's `--record`
must never delete another repository's consent. Affected: task0001, and
task0002 / task0009 which must not work around a `--record` failure.

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
value, plus that no file outside the table contains any occurrence. The two
`contributor-consent` skill documents are the single documented exclusion.
Rationale: recomputing the baseline from the same tree at test time would be
tautological, and a "not increased" comparison stays green when unrelated text is
removed. Affected: task0005 (owns it), task0002 / task0003 / task0009 (must not
increase it).

### D-G: Version bump is owned by exactly one task, and is not repeated

Only task0004 edits a version field, in both plugins and in the marketplace entry,
in one coherent change; it is already applied inside this feature's change set and
still exceeds the base revision. The second planning pass therefore adds **no**
version task and **no** task may edit a version field: the feature has not shipped
between the two passes, so one bump covers the whole change set. Rationale: two
tasks bumping independently would produce conflicting values for the same plugin.
Affected: task0004 owns it; task0007, task0008, task0009 are forbidden from it.

### D-H: Recognition is rebuilt on real lexing, not on more enumerated spellings

The verify phase found four scenarios failing for one reason: the recognizer split
the command string into segments **before** shell quoting was honoured, so a
quoted separator both broke a real invocation apart and carved a mere mention into
a standalone one. The remedy is a change of mechanism, not a longer table of
spellings — the rework gate explicitly rejected adding another string classifier.
Recognition is rebuilt so that a single quote-aware tokenization is the *first*
step and every later step consumes tokens, never the raw string. Python's
standard-library POSIX shell tokenizer is the expected basis; a hand-rolled regular
expression over the raw string is rejected for this role. Quoted text is inert by
default and becomes command text only in the two roles a shell would execute it in
(a nested shell's command-string argument, a command-substitution body), which is
exactly what keeps the widening from turning mentions into denies. Wrapper
resolution must step over a wrapper option that takes its value in a separate
token, and shell nesting must be recognized when the command-string flag is bundled
with other short options. Affected: task0007 owns it; task0008 must not touch it.

### D-I: Consent-write provenance is a CLI precondition, and the skill only presents the command

The second enforcement surface lives entirely on the CLI's two mutating commands:
they refuse to change the store unless standard input is an interactive terminal,
and the refusal precedes every store access. The skill is therefore rewritten to
**present** the command line for the user to run in their own terminal rather than
running it — an agent-run invocation would be refused anyway, and presenting it
keeps the skill honest about who performs the write. The read-only command stays
outside the precondition so the skill can still report the current state. The hook
classification surface (FR4 / FR5) is untouched by this decision. The
interactive-terminal test is a provenance proxy, not proof of human operation
(SPEC a12); the residual is accepted and stated in the SPEC. Affected: task0008
(CLI side) and task0009 (skill side); they meet only at the CLI contract above and
share no file.

### D-J: Merge boundary inside the two files task0007 and task0008 share

Both tasks edit `em-workflow/hooks/muse_guard.py`, `em-review/hooks/muse_guard.py`
and `tests/test_muse_guard.py`, and they run in parallel worktrees. The overlap is
made safe by disjoint regions rather than by ordering:

- task0007 edits only the command-recognition region of the script and adds test
  cases only to the recognition test groups.
- task0008 edits only the CLI region of the script (plus the existing test cases
  that call a mutating command, which its own change breaks) and adds its new cases
  as their own test group.
- Neither task renames, reorders or reformats anything outside its region, and
  neither changes the deny payload, the store contract, the project-key derivation
  or the plugin-slug constant's value.

Rationale: the two changes are in different layers with no shared contract, so a
single combined task would be oversized while an ordering dependency does not
exist in this workflow. Conflicts that still arise are resolved by the
implementer's parent-side-adoption protocol. Affected: task0007, task0008.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The rebuilt recognizer widens what counts as an invocation and denies a mention, stalling an unattended run | Medium | High | Every widening in task0007 is paired with the mention that must stay undecided; quoted text is inert unless it occupies one of two executable roles; the fail-open default covers anything unclassifiable |
| The rebuilt recognizer still misses an invocation shape the harness emits | Medium | High | The four verify reproductions are acceptance criteria verbatim, and the recognition contract fixes the *mechanism* rather than an enumeration, so a new spelling is covered by tokenization rather than by a new row |
| task0007 and task0008 collide in the two files they share | Medium | Medium | D-J's region split plus distinct test group names; conflicts fall back to the parent-side-adoption protocol |
| The provenance refusal breaks the existing tests that record consent | High | Medium | task0008 owns updating every existing case that calls a mutating command to use a pseudo-terminal standard input; that update is one of its acceptance criteria |
| The provenance refusal is read as a claim of unbypassability | Medium | Medium | SPEC a12 states the residual; the refusal message and the task plans state the boundary as "an agent's ordinary Bash call path", never as "impossible" |
| The skill's presented command is copied into an agent-run Bash call and silently fails | Medium | Low | The presented text states that the user runs it in their own terminal, and the CLI's refusal message repeats the reason on stderr |
| The two script copies drift apart across three tasks that edit them | Medium | Medium | D-A keeps the permitted divergence to one constant and the copy-comparison test runs in every task that edits either copy |
| An added sentence in a skill document trips the interactive-question budget test | Medium | Low | The skill documents are the pinned set's documented exclusion; task0009 adds no occurrence to any develop-phase or review-phase document |

## Open Questions

- [ ] **O1 — Register of the guard's messages.** The existing guard family's deny
      and ask messages were not available as an input to planning. Resolved at
      implementation: read the messages the existing bash guard and destructive
      guard already emit; if they use 敬体, match them and adjust this feature's
      user-facing strings accordingly. Consistency with the existing family
      outranks the plain-form default; only the register changes. Applies to the
      guard messages (task0001), the provenance refusal line (task0008) and the
      skill's lines (task0009).
- [ ] **O2 — Exact invocation of the LiteLLM availability probe.** The probe is
      already defined in each plugin's review-phase document, which was not an
      input to planning. Resolved at implementation by task0009: invoke the probe
      exactly as that document defines it, per plugin, rather than reimplementing
      it inside the skill.
- [ ] **O3 — How "exactly three facts" is counted.** The skill shows a subject line
      above the three facts, and a naive count of labeled lines could read four.
      Resolved at implementation by task0009: present the three facts as one
      explicitly labeled group with the subject line described separately as the
      target of consent; if review or verify still reads it as a fourth fact, drop
      the subject line — the three facts are requirement-fixed, the subject line is
      not.
- [ ] **O4 — Design decisions predating the FR13 amendment.** DESIGN.md's skill
      decisions describe the consenting option as recording the key and the
      revoking option as deleting it, which was written before FR13 was narrowed to
      "present the command". Resolved at implementation by task0009: keep the
      question count, the option count, the state-dependent wording split and the
      no-write-on-dismissal behavior exactly as designed, and re-word only the part
      of each option's description that names who performs the write. No other
      design decision changes.
- [ ] **O5 — Residual review findings from round 2.** Seven critical/high findings
      were deferred at the batch rework cap and are not covered by any task here;
      the amended SPEC's SC-8 no longer requires that count to be zero. Their
      content was not an input to this planning pass. Resolved at review: any of
      them whose root cause is the pre-quote splitting is subsumed by task0007;
      anything else re-surfaces as a fresh finding against the current tree.
