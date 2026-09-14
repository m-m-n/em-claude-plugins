# Feature: destructive-guard-command-name-substitution

## Overview

`destructive-guard.py` は、コマンド語そのものがコマンド置換で決まる形
（`$(which rm) -rf <path>`）を allow のまま素通りさせる。`head()` が `.substitution_only`
トークンをコマンド語位置で読み飛ばし、コマンド語が `-rf` になるためである。本フィーチャーは、
残りのトークンが既存の破壊的形状に一致するときだけ検査対象に取り込んでこの見逃しを塞ぐ。
あわせて `-c` / `eval` / `<<<` のペイロード引数位置でクォートの有無を区別し、引用付き
`"$(...)"` の繰り上げが生む誤爆を取り除く。

要件の出典は `feature-docs/destructive-guard-command-name-substitution/REQUIREMENTS.md`。

## Objectives

- コマンド語そのものがコマンド置換で決まる形のうち、残りのトークンが既存の破壊的形状に
  一致するものを検査対象に取り込み、`$(which rm) -rf <path>` が allow のまま素通りする
  見逃しを塞ぐ（OBJ-1）。
- `-c` / `eval` / `<<<` のペイロード引数位置でクォートの有無を区別し、引用付き `"$(...)"` を
  「次の語へ繰り上げる」現行挙動が生む誤爆（cases.json:230）を取り除く（OBJ-2）。
- 置換の展開結果そのものがスクリプト本文になる形（cases.json:231）は静的に確定不能である
  ことを設計判断として明文化し、理由文・ラベル・docstring をその範囲と一致させる（OBJ-3）。
- 誤爆を増やさない。`$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` /
  `$(which node) script.js` / `eval "$(ssh-agent -s)"` / `bash -c "$(cat script.sh)"` は
  allow を保つ（OBJ-4）。

## User Stories

### US1: コマンド名が置換で決まる破壊的コマンドを止める

As a destructive-guard フックの判定, I want コマンド語位置が置換のときも残りのトークンを
既存の破壊的形状に照合すること, so that `$(which rm) -rf <path>` が allow のまま素通りしない。

**Acceptance Criteria:**

- [ ] AC-1: `$(which rm) -rf /home/sakura/valuable` が `deny` になり、理由 id が `rm-recursive` である。
- [ ] AC-2: `$(which git) reset --hard HEAD` が `deny`、理由 id が `git-reset-hard` である。

### US2: 無害な形を止めない

As a destructive-guard フックの判定, I want 破壊形状に一致しない残りを現行どおり allow に
保つこと, so that 無人実行の正常系が誤爆で停止しない。

**Acceptance Criteria:**

- [ ] AC-3: `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` / `$(which ls) -la` が `allow` である。
- [ ] AC-4: `$(which rm) -rf dist` と `$(which rm) -rf /tmp/scratch/x` が `allow` である（既存セーフルート例外の継承）。
- [ ] AC-6: `eval "$(ssh-agent -s)"` / `eval "$(direnv export bash)"` / `eval "$(mise activate zsh)"` / `bash -c "$(cat script.sh)"` がいずれも `allow` である。

### US3: ペイロード位置のクォートを実シェル意味論に合わせる

As a destructive-guard フックの判定, I want `-c` / `eval` / `<<<` のペイロード引数位置で
クォートの有無を区別すること, so that 引用付き `"$(...)"` の繰り上げによる誤爆が消え、
未引用置換の deny は保たれる。

**Acceptance Criteria:**

- [ ] AC-5: `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` が `allow` であり、当該ケースが cases.json から削除されずラベル書き換えの上で残っている。
- [ ] AC-7: `bash -c $(printf %s) 'rm -rf /home/sakura/valuable'` / バッククォート形 / `sh -c $(true) 'git reset --hard HEAD'` / `bash <<<$(true) 'rm -rf /home/sakura/valuable'` が `deny` のままである。

### US4: 対象外範囲を明文化する

As a このフックの読み手, I want 静的解析の対象外範囲がラベルと docstring で同一に述べられる
こと, so that 「既知の限界」がどこまでかを 1 つの記述で確認できる。

**Acceptance Criteria:**

- [ ] AC-8: `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` は `allow` であり、そのラベルと `extract_shell_payload()` の docstring が「置換の展開結果がスクリプト本文になる形は対象外」という同一の範囲を述べている。

### US5: 既存の判定とテストを壊さない

As a このプラグインの利用者, I want 既存の判定と理由文が変わらず、テストと version 規約が
満たされること, so that 変更がキャッシュに反映され、検知力が落ちていないことを確認できる。

**Acceptance Criteria:**

- [ ] AC-9: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る。
- [ ] AC-10: `python3 -m unittest discover -s tests` が全件通る。
- [ ] AC-11: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow version が同一値で、変更前より patch が 1 つ以上進んでいる。
- [ ] AC-12: 変更後のフックが、置換を含まないコマンドに対して変更前と同じ判定・同じ理由文を返す。

## Technical Requirements

### Functional Requirements

- **FR1 - コマンド語位置の置換 + rm 破壊形状の検査:** `head()` が `.substitution_only`
  トークンをコマンド語位置で読み飛ばした結果、次のトークンが `-` で始まる（実シェルでは
  コマンド名になり得ない）場合、その文のコマンド名は静的に不明と判定する。このとき残りの
  トークンを既存の rm 破壊形状に照合する: 再帰フラグ（`-r` / `-R` / `--recursive`）と
  強制フラグ（`-f` / `--force`）の両方があり、かつ非フラグのオペランドが 1 つ以上あるときに
  限り、残り引数を既存の `check_rm()` に流す。判定段（deny / ask）と理由 id は `check_rm()`
  が現在返すものをそのまま使い、新しい段は作らない。結果として
  `$(which rm) -rf /home/sakura/valuable` は `rm-recursive` / deny、`$(which rm) -rf dist` や
  `$(which rm) -rf /tmp/x` は既存のセーフルート例外を継承して allow になる。
- **FR2 - コマンド語位置の置換 + git 破壊形状の検査:** 同じくコマンド語位置が
  `.substitution_only` だった文について、残りのトークンを `check_git()` の照合にも掛ける
  （git のサブコマンドは裸の語なので FR1 のフラグ先頭判別では捕まらない）。
  `$(which git) reset --hard HEAD` / `$(which git) clean -fd` が既存の `git-reset-hard` /
  `git-clean` で deny になる。`check_git()` が何も一致させない残り（`echo safe`、`status`）は
  判定を出さない。
- **FR3 - 無害な残りの allow 維持:** `.substitution_only` を読み飛ばした次のトークンが `-` で
  始まらない（=実コマンド語になり得る）場合は現行どおりそれをコマンド語として扱い、FR1 の
  経路に入れない。`$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` /
  `$(which node) script.js` は allow のまま。`$(which ls) -la` のようにフラグ先頭でも rm 形状に
  一致しない残りも allow。
- **FR4 - ペイロード引数位置のクォート判定:** `-c` / `eval` / `<<<` のペイロード引数位置に
  限り、字句解析前のテキストからその位置の置換がクォートで囲まれていたかを判定する。引用付き
  `"$(...)"` は空展開でも語が消えないため `_payload_index()` による次の語への繰り上げを行わず、
  その置換自身をペイロードとして扱う。マーカー構造（`UNRESOLVED_MARK` /
  `SUBSTITUTION_STANDIN` / `Tok` の 3 属性）は変更しない。変更は `extract_shell_payload()` と
  その補助に閉じ、`head()` / `git_subcommand()` / `check_rm()` の読み飛ばしには波及させない。
- **FR5 - 未引用置換の繰り上げ挙動の保存:** 未引用 `$(...)` / バッククォートの繰り上げ挙動は
  現状どおり維持する。cases.json:203-205 と :227 の deny 期待値は不変。
- **FR6 - cases.json:230 の期待値反転とラベル書き換え:**
  `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` のケースは削除せず残し、期待値を
  `deny` から `allow` に変える。ラベルは現行の「fail-closed の代償: …クォートの有無を静的に
  区別できないため…」から、クォート判定により実シェル意味論（第 2 引数は `$0`）に一致させた旨に
  書き換える。`.claude/rules/hook-tests.md` の「既存の deny / ask ケースは消さない」に対しては、
  ケース自体を allow 側の誤爆防止ケースとして保持することで応じる。
- **FR7 - cases.json:231 の対象外宣言の明文化:**
  `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` は allow のままとする。
  ラベルを現行の「既知の限界(基準版と同じ)」から、置換の展開結果（=置換本文の出力）が
  スクリプト本文になる形はこのフックの静的解析の対象外である、という設計判断の記述に書き換える。
  同じ範囲記述を `extract_shell_payload()` の docstring にも置き、理由文・ラベル・docstring の
  3 者を一致させる。
- **FR8 - ケース追加:** `destructive-guard-cases.json` に TS-1〜TS-12 のコマンドを
  `[期待判定, ラベル, コマンド]` の 3 要素で追加する。deny/ask 側と allow 側の両方を入れる。
- **FR9 - ミラー差分注記の更新:** `head()` / `git_subcommand()` の docstring にある
  「Mirrored in failed-run-cleanup-guard.py … That mirror does not know about
  `Tok.substitution_only`; the skip added here for it is local to this file」の注記を、
  FR1 / FR2 で増えた分岐も同じくローカル限定である旨に拡張する。
  `failed-run-cleanup-guard.py` と `muse_guard.py` のコードは変更しない。
- **FR10 - プラグイン version の引き上げ:** `.claude/rules/core-plugin-version-bump.md` に従い、
  同じ変更の中で `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の
  em-workflow エントリの `version` を同じ次の patch 値へ引き上げる。挙動の修正なので patch 単位。

### Non-Functional Requirements

- **NFR1 - 決定性:** 判定は決定的に保つ。ファイルシステム参照（`realpath` / `stat`）、
  サブプロセス起動、置換の実行は一切行わない。判定材料はコマンド文字列のみ。
- **NFR2 - 既存期待値の保存:** 既存の期待値は FR6 の 1 件を除いて不変。特に
  cases.json:194-195 / 197-215 / 217-229 / 233-234 は現行の判定を保つ。
- **NFR3 - 誤爆コスト:** 誤爆コストは見逃しコストと同じ桁（`.claude/rules/hook-tests.md`）。
  一律 `ask` へ倒す実装は採らない。`ask` は無人実行で `deny` に降格するため、正常系を止める
  変更は allow 側ケースで先に固定してから入れる。
- **NFR4 - 降格経路の不変:** `ask` → `deny` の無人実行降格（`decide()` / `unattended()`）は
  変更しない。run-destructive-guard.py 末尾の降格ケースは通り続ける。
- **NFR5 - 変更範囲:** 変更範囲は `em-workflow/hooks/destructive-guard.py` と
  `em-workflow/hooks/tests/destructive-guard-cases.json`、および FR10 の version 2 ファイルに
  限る。他のフックスクリプトには手を入れない。
- **NFR6 - テストの独立性:** テストは外部依存を持たない（`test/README.md`）。追加ケースは
  既存の 3 要素 JSON 形式に従い、新しいランナーや依存を導入しない。

## Implementation Approach

### Architecture

判定は 1 本のコマンド文字列に対する静的解析で、変更は既存の段の内側に閉じる。

```
コマンド文字列
      │
      ▼
  字句解析（Tok / UNRESOLVED_MARK / SUBSTITUTION_STANDIN）  ← 構造は不変 (FR4, AS-5)
      │
      ├─ extract_shell_payload()      ← FR4 / FR5: ペイロード位置のクォート判定
      │
      ▼
  head() / git_subcommand()           ← FR1 / FR2: コマンド語が静的に不明な経路の追加
      │
      ▼
  check_rm() / check_git()            ← 判定段と理由 id は既存のものをそのまま使う (AS-1)
      │
      ▼
  decide() / unattended()             ← 不変 (NFR4)
```

**Component Diagram:**

```
destructive-guard.py
  ├─ extract_shell_payload()  : -c / eval / <<< のペイロード抽出（FR4, FR5, FR7 docstring）
  ├─ _payload_index()         : ペイロード語の位置決定（引用付き置換は繰り上げない）
  ├─ head()                   : 文のコマンド語決定（FR1 の判別、FR9 のミラー注記）
  ├─ git_subcommand()         : git サブコマンド抽出（FR2 経路、FR9 のミラー注記）
  ├─ check_rm()               : rm 破壊形状の判定（呼び出し元が増えるだけ）
  ├─ check_git()              : git 破壊形状の判定（呼び出し元が増えるだけ）
  └─ decide() / unattended()  : 判定段の確定と無人実行降格（不変）
```

### Data Flow

```
Bash コマンド文字列 → 字句解析 → ペイロード抽出 → コマンド語判別 → 形状照合 → 判定 (allow/ask/deny) + 理由 id
```

### API Design

該当なし。PreToolUse フックの入出力形式は変更しない。

### Database Schema

該当なし。永続データを扱わない。

### Dependencies

**Internal Dependencies:**

- `em-workflow/hooks/destructive-guard.py`: 判定ロジック本体。
- `em-workflow/hooks/tests/destructive-guard-cases.json`: `[期待判定, ラベル, コマンド]` の
  3 要素ケース。
- `em-workflow/hooks/tests/run-destructive-guard.py`: ケースランナー。
- `em-workflow/hooks/failed-run-cleanup-guard.py` / `muse_guard.py`: `head()` /
  `git_subcommand()` のミラー先。コードは変更せず、docstring の注記のみ更新する（FR9, AS-6）。

**External Dependencies:**

なし。テストは外部依存を持たない（NFR6）。

### File Structure

```
em-workflow/
├── hooks/
│   ├── destructive-guard.py                 # FR1-FR5, FR7, FR9
│   └── tests/
│       └── destructive-guard-cases.json     # FR6, FR7, FR8
├── .claude-plugin/
│   └── plugin.json                          # FR10 (version)
.claude-plugin/
└── marketplace.json                         # FR10 (version)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-command-name-substitution/**`
- `test-docs/destructive-guard-command-name-substitution/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers
`test-docs/destructive-guard-command-name-substitution/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS-1 (FR1): `$(which rm) -rf /home/sakura/valuable` → `deny`。チケット再現。コマンド名が置換で決まる rm 破壊形状。
- [ ] TS-2 (FR1): `` `which rm` -rf /home/sakura/valuable `` → `deny`。両スペル対称性（バッククォート側）。
- [ ] TS-3 (FR2): `$(which git) reset --hard HEAD` → `deny`。git サブコマンド形状での同等形。
- [ ] TS-4 (FR2): `$(which git) clean -fd` → `deny`。git-clean 形状での同等形。
- [ ] TS-5 (FR3): `$(which node) script.js` → `allow`。誤爆防止。残りが破壊形状に一致しない。
- [ ] TS-6 (FR1, FR3): `$(which ls) -la` → `allow`。誤爆防止。フラグ先頭だが rm 形状（r+f+オペランド）に一致しない。
- [ ] TS-7 (FR1): `$(which grep) -r pattern src` → `allow`。誤爆防止。再帰フラグのみで強制フラグが無い形は対象外。
- [ ] TS-8 (FR1): `$(which rm) -rf dist` → `allow`。誤爆防止。セーフルート（build artifact）例外の継承。
- [ ] TS-9 (FR1): `$(which rm) -rf /tmp/scratch/x` → `allow`。誤爆防止。スクラッチルート配下の例外の継承。
- [ ] TS-10 (FR4, FR6): `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` → `allow`。既存 cases.json:230 の期待値反転。第 2 引数は実シェルでは `$0`。
- [ ] TS-11 (FR4): `eval "$(ssh-agent -s)"` → `allow`。正常系固定。引用付き置換ペイロードを止めない。
- [ ] TS-12 (FR7): `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` → `allow`。対象外であることを明文化した上での allow（既存 cases.json:231）。

### Integration Tests

- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る（AC-9）。
- [ ] `python3 -m unittest discover -s tests` が全件通る（AC-10）。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 未引用置換の繰り上げ形（`bash -c $(printf %s) 'rm -rf /home/sakura/valuable'`、
  バッククォート形、`sh -c $(true) 'git reset --hard HEAD'`、
  `bash <<<$(true) 'rm -rf /home/sakura/valuable'`）は `deny` のまま（AC-7, FR5）。
- [ ] `check_git()` が何も一致させない残り（`echo safe`、`status`）は判定を出さない（FR2）。
- [ ] 置換を含まないコマンドは変更前と同じ判定・同じ理由文を返す（AC-12）。
- [ ] `eval "$(direnv export bash)"` / `eval "$(mise activate zsh)"` /
  `bash -c "$(cat script.sh)"` は `allow`（AC-6）。

### Performance Tests

該当なし。

## Security Considerations

- **Input Validation:** 判定材料はコマンド文字列のみ。ファイルシステム参照（`realpath` /
  `stat`）、サブプロセス起動、置換の実行は行わない（NFR1）。
- **Detection Scope:** コマンド語位置が置換の文は、残りのトークンが既存の rm / git 破壊形状に
  一致するときだけ deny / ask に倒す（FR1, FR2）。
- **Out of Scope:** 置換の展開結果（=置換本文の出力）がスクリプト本文になる形は、このフックの
  静的解析の対象外（FR7）。
- **Unattended Behaviour:** `ask` は無人実行で `deny` に降格する。降格経路は変更しない
  （NFR3, NFR4）。

## Error Handling

### 判定段と理由 id

| 理由 id | 判定 | 発生条件 |
|---------|------|----------|
| `rm-recursive` | deny | コマンド語位置が置換で、残りが再帰フラグ + 強制フラグ + 非フラグオペランドを満たす（FR1, AC-1） |
| `git-reset-hard` | deny | コマンド語位置が置換で、残りが `reset --hard` 形状（FR2, AC-2） |
| `git-clean` | deny | コマンド語位置が置換で、残りが `clean -fd` 形状（FR2） |

判定段（deny / ask）と理由 id は既存の `check_rm()` / `check_git()` が返すものをそのまま使い、
新しい段は作らない（AS-1）。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] AC-1: `$(which rm) -rf /home/sakura/valuable` が `deny` になり、理由 id が `rm-recursive` である。
- [ ] AC-2: `$(which git) reset --hard HEAD` が `deny`、理由 id が `git-reset-hard` である。
- [ ] AC-3: `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` / `$(which ls) -la` が `allow` である。
- [ ] AC-4: `$(which rm) -rf dist` と `$(which rm) -rf /tmp/scratch/x` が `allow` である（既存セーフルート例外の継承）。
- [ ] AC-5: `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` が `allow` であり、当該ケースが cases.json から削除されずラベル書き換えの上で残っている。
- [ ] AC-6: `eval "$(ssh-agent -s)"` / `eval "$(direnv export bash)"` / `eval "$(mise activate zsh)"` / `bash -c "$(cat script.sh)"` がいずれも `allow` である。
- [ ] AC-7: `bash -c $(printf %s) 'rm -rf /home/sakura/valuable'` / バッククォート形 / `sh -c $(true) 'git reset --hard HEAD'` / `bash <<<$(true) 'rm -rf /home/sakura/valuable'` が `deny` のままである。
- [ ] AC-8: `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` は `allow` であり、そのラベルと `extract_shell_payload()` の docstring が「置換の展開結果がスクリプト本文になる形は対象外」という同一の範囲を述べている。
- [ ] AC-9: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る。
- [ ] AC-10: `python3 -m unittest discover -s tests` が全件通る。
- [ ] AC-11: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow version が同一値で、変更前より patch が 1 つ以上進んでいる。
- [ ] AC-12: 変更後のフックが、置換を含まないコマンドに対して変更前と同じ判定・同じ理由文を返す。

## Assumptions

- AS-1: `deny` か `ask` かは新設せず、FR1 / FR2 で既存 `check_rm()` / `check_git()` に残りトークンを
  流した結果の段をそのまま採用する。（reversible）
- AS-2: 「コマンド名が静的に不明」の判別子は「`.substitution_only` を読み飛ばした次のトークンが
  `-` で始まる」ことと、git サブコマンド形状への一致の 2 経路。cases.json:207-215 の既存期待値を
  全て保つ最小の判別子として導出した。（reversible）
- AS-3: `rm` 破壊形状の下限は「再帰フラグ AND 強制フラグ AND 非フラグオペランド 1 つ以上」。
  `grep -r` 等の再帰フラグ単独形を巻き込まないための境界。（reversible）
- AS-4: cases.json の既存 deny/ask ケースは FR6 の 1 件を除いて期待値を変えない。（reversible）
- AS-5: マーカー構造（`UNRESOLVED_MARK` / `SUBSTITUTION_STANDIN` / `Tok` の 3 属性）は
  変更しない。（reversible）
- AS-6: `failed-run-cleanup-guard.py` / `muse_guard.py` はコード変更なし。ミラーの戻り値の形
  （2-tuple）は変わらないため。（reversible）

## Constraints

- プロジェクトに LICENSE、パッケージマニフェスト、ビルドコマンド、フォーマットコマンド、
  E2E 基盤はない。
- テストコマンドは `python3 em-workflow/hooks/tests/run-destructive-guard.py` と
  `python3 -m unittest discover -s tests` の 2 つ。
- `.claude/rules/hook-tests.md`: 既存の deny / ask ケースは消さない。
- `.claude/rules/core-plugin-version-bump.md`: 同じ変更の中で version を 2 箇所同じ値へ上げる。

## Out of Scope

- 置換の展開結果（=置換本文の出力）がスクリプト本文になる形の解析（FR7）。
- `failed-run-cleanup-guard.py` / `muse_guard.py` のコード変更（FR9, AS-6）。
- design ステップ（skipped）。本フィーチャーは UI を持たず、`design_system_candidates` も 0 件。
  字句層コントラクトの設計判断と誤爆許容範囲は create-plan の IMPLEMENTATION.md が担う。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。FR1〜FR10 の status はすべて `resolved`。

## References

- 要件定義書: `feature-docs/destructive-guard-command-name-substitution/REQUIREMENTS.md`
- フック本体: `em-workflow/hooks/destructive-guard.py`
- ケース定義: `em-workflow/hooks/tests/destructive-guard-cases.json`
- ケースランナー: `em-workflow/hooks/tests/run-destructive-guard.py`
- フックのテスト運用ルール: `.claude/rules/hook-tests.md`
- version 引き上げルール: `.claude/rules/core-plugin-version-bump.md`
