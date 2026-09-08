# Design: muse-spark-contributor-consent

## Surfaces

This feature has **no rendered graphical UI**. SPEC.md 6.1 names exactly two
user-facing surfaces, and the CLI adds a third:

| # | Surface | Consumer | Governed by |
|---|---------|----------|-------------|
| S1 | `contributor-consent` skill: fact block + one `AskUserQuestion` round | human, interactive session | FR13 |
| S2 | Hook deny payload: `permissionDecisionReason` + `additionalContext` | permission UI (human) and the dispatching agent | FR4 |
| S3 | `muse_guard.py` CLI stdout/stderr (`--record` / `--remove` / `--list`) | human, and the skill parsing `--list` | FR7 |
| S4 | Written pre-dispatch criteria in `reviewers.yaml` / `review-phase.md` | reviewing LLM | FR9 |

Nothing in this feature is rendered by a browser, a component framework, or a
styling system. There is no existing design asset in this repository to follow
("follows existing" applies to nothing here — `project.design_system.kind` is
`none`, and `resolved_input_paths` supplied zero design-system files, zero
sibling `DESIGN.md` files, and zero visual inputs).

## Decisions

### D1 — No design tokens, no token sheet, no mockups

`design-system/tokens.yaml`, `design-system/tokens.html`, and
`feature-docs/muse-spark-contributor-consent/design/mockups/*.html` are **not
created** by this design step. `project.design_system.kind` stays `none`.
DESIGN.md is the sole artifact of this step.

### D2 — Shared conventions for all text surfaces (S1–S3)

- Japanese prose; identifiers stay verbatim ASCII (`muse-spark-contributor`,
  `muse_guard.py`, `--record`, `~/.claude/em-workflow/muse-consent.json`).
- Plain form (常体) throughout — see O1 for the one condition that overrides this.
- No emoji, no ANSI color, no box drawing, no leading symbols/bullets glyphs
  beyond a plain `-`.
- One statement per line. Every string inside the hook's JSON payload (S2) is a
  **single-line string containing no `\n`**, so the permission UI and the
  agent's context both render it as one unit.
- No text surface ever quotes back any part of `tool_input.command` — see D5.

### D3 — Deny payload: exact field set (S2)

The hook prints one JSON object to stdout and nothing else:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "<D4>",
    "additionalContext": "<D6>"
  }
}
```

Exactly these four inner keys — no `suppressOutput`, no extra diagnostics keys.
On every non-deny path the process writes **zero bytes** to stdout (not `{}`,
not a newline) and exits 0.

### D4 — `permissionDecisionReason`: exact text

```
muse-spark-contributor（contributor ティア）は、このリポジトリの同意が記録されていないため使用できない。
```

One sentence. It names the model, names the condition (consent absent), and
scopes it to "this repository". It carries no path, no project key, no store
location and no remediation step — remediation lives in D6.

### D5 — Deny text is a compile-time constant, never interpolated

`permissionDecisionReason` and `additionalContext` are module-level string
constants. Nothing from the hook's input is interpolated into them: not
`tool_input.command`, not the cwd, not the derived project key, not the store
path, not any store content. Only D7's `PLUGIN_SLUG` substitution occurs, and
that value is a literal in the source file, not input-derived.

### D6 — `additionalContext`: exact text

```
回避策を探さず、reviewers.yaml の chain にある非 contributor の muse-spark エントリ、または他の chain エントリでレビューを続行する。同意はユーザーが対話セッションで /em-workflow:contributor-consent スキルを実行したときにだけ記録される。エージェント自身が muse_guard.py --record を実行して同意を代行してはならない。
```

Three clauses, in this order and no other: (1) what to do instead, (2) who may
grant consent and how, (3) the explicit prohibition on the agent self-granting
consent through the CLI.

### D7 — `PLUGIN_SLUG` is the single permitted divergence between the two copies

FR1 requires the two `muse_guard.py` copies to be byte-identical "except where
they must name their own plugin". That exception is **exactly one module-level
constant**:

```python
PLUGIN_SLUG = "em-workflow"   # em-review copy: "em-review"
```

It is used in exactly one place: the `/{PLUGIN_SLUG}:contributor-consent`
skill reference inside `additionalContext` (D6). Every other byte of the two
files — including `permissionDecisionReason` (D4), which contains no plugin
name for this reason — is identical. Both copies denying the same invocation
(NFR9) therefore differ only in that one slug, and a deny twice is still a
deny.

### D8 — Skill: subject line, then exactly three facts (S1)

The skill prints, before asking anything:

```
対象リポジトリ: /absolute/path/to/repo

リモートの可視性: public
ライセンス: MIT
コントリビューター: あなたのみ
```

- The subject line is the **subject of consent, not a fourth fact**. It is
  separated from the fact block by a blank line, and SKILL.md documents the
  three facts as their own explicitly labeled group (see O3).
- The three facts appear in this fixed order with these fixed labels.
- Value vocabulary:
  - 可視性: `public` / `private` / `internal` / `取得できず`
  - ライセンス: the license name as reported (e.g. `MIT`), or `なし`
    (repository genuinely has no license), or `取得できず`
  - コントリビューター: `あなたのみ` / `あなたを含む N 名` / `取得できず`
- A fact that cannot be collected is rendered as `取得できず` — never omitted,
  never guessed, never replaced by a conversational follow-up question. The
  question in D9 is still asked; the facts inform the decision, they do not
  gate it.
- Unpushed-commit state is not shown (FR13).

### D9 — Skill: one `AskUserQuestion` round, two options, state-dependent

Exactly one question object, `multiSelect: false`, `header: 同意`, two options.
The skill runs `--list` first (D12) and selects one of two wordings:

**Not yet consented:**

- question: `このリポジトリの差分を muse-spark contributor ティアへ送ることに同意する?`
- option 1 — label `同意する` / description
  `以後このリポジトリのレビューで contributor ティアの使用を許可する。同意ストアにこのリポジトリのキーを記録する。`
- option 2 — label `同意しない` / description
  `何も記録しない。contributor ティアは引き続き deny される。`

**Already consented:**

- question: `このリポジトリの contributor ティア同意は記録済み。どうする?`
- option 1 — label `維持する` / description `記録を変更しない。`
- option 2 — label `撤回する` / description
  `同意ストアからこのリポジトリのキーを削除する。以後 contributor ティアは deny される。`

Two options in each state, because a presence-only store has exactly two
states. Revocation (UC04) reaches the store through the second wording, so the
skill still asks exactly one round in both directions.

### D10 — Skill: dismissal is the no-write option

If the user dismisses the question or answers nothing, the skill takes the
non-mutating branch (`同意しない` / `維持する`), prints one line
(`同意ストアは変更していない。`), and exits 0 without invoking the CLI.

### D11 — Skill: the "not installed" exit (S1)

When the `litellm_available` probe is false, the skill prints exactly:

```
vertex-review の LiteLLM ハーネスが見つからない。contributor ティアはこの環境では使えないため、同意の記録は不要。
```

then exits — no fact collection, no question, no store read, no store write.

### D12 — CLI output shape (S3)

- Results go to stdout; errors go to stderr. Exit 0 on success, 1 on runtime
  failure (store write failed, store malformed), 2 on argument misuse
  (argparse default).
- Exactly one of `--record` / `--remove` / `--list` is required and they are
  mutually exclusive; `--project-dir DIR` is required for all three.
- `--list`: prints **the project key alone on one line** when consent exists;
  prints nothing when it does not. Exit 0 in both cases. This is the only
  machine-parsed output in the feature — the skill branches on empty vs
  non-empty stdout (D9), so it carries no label, no prefix and no timestamp.
- `--record`: `同意を記録した: <project key>` — idempotent; a second
  `--record` refreshes `updated_at` and prints the same line (no "already
  recorded" variant).
- `--remove`, key present: `同意を削除した: <project key>`
- `--remove`, key absent: `同意は記録されていない: <project key>`, exit 0,
  store untouched (and not created).
- The store path appears in output only inside an error message on stderr.

### D13 — Store file shape written by the CLI

```json
{
  "version": "1",
  "projects": {
    "<project key>": {
      "updated_at": "2026-09-08T12:34:56+09:00"
    }
  }
}
```

- `version` is the string `"1"`.
- `updated_at` is RFC 3339 with an explicit UTC offset —
  `datetime.now().astimezone().isoformat(timespec="seconds")`. Never a naked
  local time, never a bare epoch.
- Serialized with `indent=2`, `sort_keys=True`, `ensure_ascii=False`, and a
  trailing newline, so successive `--record` runs produce reviewable diffs.
- No field other than `updated_at` is ever written under a project key (NFR7).

### D14 — Malformed store: the CLI refuses to repair, matching the hook

- Hook path and `--list`: a missing / unreadable / invalid-JSON /
  wrong-shaped store means "no consent for any project". No write, no repair
  (FR6).
- `--record` / `--remove` on a malformed store: **exit 1** with
  `同意ストアの形式が不正: <path>` on stderr, writing nothing. The CLI does not
  overwrite it with a fresh store, because doing so would silently discard
  other repositories' consent entries. Repair is the user's explicit act.
- A missing store is not malformed: `--record` creates parent directories and
  the file (FR7).

### D15 — Written criteria: one-vs-three presented as two separately headed lists (S4)

AC-7 / TS-14 require the single per-dispatch "do not use" item and the three
"outside the scope of consent" conditions to be **textually distinguishable**.
They are rendered as two lists under two distinct headings, never merged and
never interleaved:

- `Per-dispatch: do not use` — exactly one bullet.
- `Outside the scope of consent` — exactly three bullets.

The third out-of-scope bullet is phrased as a present-state test at dispatch
time ("if the repository is currently private, or its license is no longer the
one the consent was reasonable under, do not use the contributor tier") and
never as a comparison against a value recorded at consent time — the store
holds no such value (NFR7, a10).

## Rationale

- **D1**: This project ships Claude Code plugins. Every surface is terminal
  text, a JSON payload consumed by the permission system, or Markdown/YAML read
  by an LLM. There is no color, no spacing scale, no typography and no layout to
  decide, so a token file would consist entirely of values nothing consumes, and
  a self-contained HTML mockup would depict a screen that does not exist. The
  designer contract's `action: create` permits creating those files, it does not
  require it. Creating them would also flip the project into a state where
  `kind: none` plus an existing token file triggers the contract's abort +
  reclassification gate on every later phase — a real cost for zero benefit.
  The decisions this feature genuinely needs are wording and output-shape
  decisions, and they are recorded above.
- **D2**: The guard family's messages are terse machine notices, not prose; a
  single register keeps two hook copies plus a CLI plus a skill from drifting
  into three different voices. Single-line hook strings matter because the
  string is injected into an agent's context — a multi-line reason invites the
  agent to treat later lines as separate instructions.
- **D4/D6 split**: `permissionDecisionReason` is what a human sees in the
  permission UI; `additionalContext` is what steers the agent. Keeping
  remediation out of the reason keeps the human-facing line to one readable
  sentence, and keeps the agent-facing instruction in the field designed for it.
- **D5**: The deny text is fed straight back into the agent's context. If any
  part of the denied command were echoed into it, a crafted command string
  would become agent-visible instruction text — the exact prompt-injection
  channel this feature's code-not-prose gate (BO2, FR1) exists to close.
- **D6 clause 3**: `muse_guard.py --record` is reachable by any agent that can
  run Bash, and nothing in the SPEC gates the CLI itself (a10 deliberately keeps
  the store presence-only and the hook read-only). The deny text is therefore
  the only place where "do not grant your own consent" can be stated at the
  moment it would be tempting. This is an instruction, not an enforcement, and
  it is recorded as such — it does not weaken FR4's code-level deny, which still
  fires on the next invocation if the store was never written.
- **D7**: FR1 demands byte-identical copies but the deny text must point the
  user at a skill whose slash-command namespace is the plugin's own. Reducing
  the divergence to one named constant makes FR1's "except where they must name
  their own plugin" carve-out mechanically checkable — a diff of the two files
  should show exactly one changed line.
- **D8 subject line**: consent is per repository and the key derivation folds
  every worktree of a repository into one entry (FR3). A user running the skill
  from `.claude/worktrees/.../integration` cannot otherwise tell what they are
  consenting for. Showing the unavailable facts as `取得できず` rather than
  hiding them is the same judgment: consent given without knowing that
  visibility could not be determined is not informed consent.
- **D9**: FR13 fixes the round count at one, and UC04 routes revocation through
  the same skill. Making the wording state-dependent is what lets both flows fit
  in one round without a mode argument or a second question.
- **D10**: The store is the record of an affirmative human decision. Silence is
  not that decision, so silence writes nothing — in either direction.
- **D12 `--list`**: it is the only output another program reads (the skill's
  D9 branch). Bare-key output makes "consented?" a non-empty-stdout test, and
  TS-11 already fixes this shape ("`--list` shows the project key when
  consented, nothing when not"). The mutating commands print a human sentence
  instead, because only humans read them.
- **D13 `updated_at`**: an offset-bearing RFC 3339 timestamp is required by the
  repository's timezone rule — a naked local time in a file that outlives the
  session is unreadable later. It is also the only field permitted under NFR7.
- **D14**: FR6 forbids the hook from repairing the store. Letting the CLI
  silently rewrite a malformed store would make the same file self-healing on
  one path and inert on the other, and would destroy other repositories'
  consents as a side effect of one `--record`. Failing loudly on a path the
  human is already watching is the cheaper failure.
- **D15**: AC-7 and TS-14 verify a *textual* distinction, so the distinction is
  made structurally (two headings, fixed bullet counts) rather than
  rhetorically. A verifier can then count bullets under each heading.

## Open items

- **O1 — Register (常体 vs 敬体) of the guard messages.** D2 fixes plain form
  (常体) for D4/D6/D11/D12. The existing guard family (`bash_guard.py`,
  `destructive-guard.py`) was not among this dispatch's resolved input paths, so
  its message register could not be inspected. **Resolution**: at implementation,
  read the deny/ask messages those two hooks already emit; if they use 敬体,
  match them and adjust D4/D6 accordingly. Consistency with the existing guard
  family outranks D2's choice — only the register changes, the clause structure
  and content of D4/D6 stay exactly as decided.
- **O2 — Exact invocation of the `litellm_available` probe.** D11 fixes the
  message the probe's false branch prints, but the probe itself is already
  defined in each plugin's `review-phase.md`, which was not a resolved input
  here. **Resolution**: at implementation, invoke the probe exactly as that
  document defines it (per plugin) rather than reimplementing it in SKILL.md;
  only D11's message text is this design's to fix.
- **O3 — "Exactly three facts" as TS-18 will count it.** D8 adds a subject line
  above the three facts. TS-18 checks that SKILL.md describes exactly three
  presented facts, so a naive count of labeled lines could read four.
  **Resolution**: SKILL.md must present the three facts as one explicitly
  labeled group (e.g. a numbered list introduced as 提示する 3 つの事実) with the
  subject line described separately as the consent target. If review or verify
  still reads it as a fourth fact, drop the subject line — the three facts are
  requirement-fixed, the subject line is this design's addition.
