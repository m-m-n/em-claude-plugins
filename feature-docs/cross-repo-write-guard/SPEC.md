# Feature: cross-repo-write-guard

## Overview

カレントの git リポジトリ（`git rev-parse --show-toplevel`）の外へのファイル書き込みを、em-workflow 同梱の PreToolUse フック `cross-repo-write-guard.py` が確認（ask）に回す。無人実行（claude-batch）では ask を deny に降格する。判定できない書き込み先には何も出力しない。要件は `feature-docs/cross-repo-write-guard/REQUIREMENTS.md` を参照。

## Objectives

- BO-1: カレントの git リポジトリ（`git rev-parse --show-toplevel`）の外へのファイル書き込みを、em-workflow 同梱の PreToolUse フックが機械的に確認（ask）に回す。
- BO-2: 無人実行（claude-batch）では ask を deny に降格し、理由をツール結果として返す。
- BO-3: 判定できない書き込み先には何も出力せず、誤爆で実行を止めない。

## Acceptance Criteria

- [ ] AC-1（FR1, FR14）: hooks.json の PreToolUse `Bash` グループで cross-repo-write-guard.py が loop-command-guard.py の直後・destructive-guard.py の直前にあり、`Write|Edit|MultiEdit` グループにも同じスクリプトが登録されている。tests/test_hooks_registration.py と tests/test_guardrail_hooks_migration.py が通る。
- [ ] AC-2（FR2, FR5, FR6）: Write / Edit / MultiEdit の file_path が toplevel 外なら ask、toplevel 内・/tmp 配下・~/.claude 配下なら何も出力しない。
- [ ] AC-3（FR2, FR3, FR11）: cwd が git リポジトリ外、または payload が不正な場合は何も出力せず終了コード 0。
- [ ] AC-4（FR3）: worktree を cwd とし、メイン作業ツリーへ書き込むと ask になる。
- [ ] AC-5（FR4）: toplevel 内のシンボリックリンクを経由して外を指す書き込み先（未作成ファイルを含む）は ask。`/repo` を toplevel とするとき `/repo-other` 配下は ask。
- [ ] AC-6（FR5）: `2>/dev/null` など列挙した /dev 配下は何も出力せず、列挙外の /dev 配下は通常どおり判定される。
- [ ] AC-7（FR7）: toplevel 外を指すリダイレクト・tee・sed -i・cp / mv の書き込み先は ask、toplevel 内なら何も出力しない。
- [ ] AC-8（FR8）: サブシェル・波括弧・ラッパーの内側の外向き書き込みは ask。`bash -c` 文字列と `$( )` 本体の中だけにある書き込み、ヒアドキュメント本文、クォート内の文字列、コメントは何も出力しない。それらを含む文の外側のリダイレクトは判定される。
- [ ] AC-9（FR4, FR9）: 変数展開・コマンド置換・glob・`$HOME` を含む書き込み先は判定されず、引用されていない `~/` は HOME に展開されて判定される。
- [ ] AC-10（FR10）: `cd` の後の相対パスは判定されず、絶対パスは判定される。サブシェル内の `cd` の後でも、サブシェルの外の相対パスは判定される。
- [ ] AC-11（FR6）: CLAUDE_BATCH が有効なとき ask は deny に降格し、理由に降格した旨が含まれる。どの経路でも allow は出力されない。
- [ ] AC-12（FR12, FR13）: `.claude/rules/hook-tests.md` に cross-repo-write-guard 節があり、`python3 -m unittest tests.test_cross_repo_write_guard` が通る。
- [ ] AC-13（FR15, FR16）: README のフック表に cross-repo-write-guard.py があり、Bash フックの本数・順序の記述と表が食い違わない。destructive-guard.py に差分が無い。

## Technical Requirements

### Functional Requirements
- **FR1:** フックスクリプトと登録 — `em-workflow/hooks/cross-repo-write-guard.py` を追加し、1 本のスクリプトを `hooks.json` の PreToolUse の 2 つの matcher に登録する。(a) `Bash` グループでは `loop-command-guard.py` の直後・`destructive-guard.py` の直前に置く。(b) `Write|Edit|MultiEdit` グループでは `gitleaks-write-guard.sh` の後に置く。コマンド形は `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/cross-repo-write-guard.py`、timeout は 15、statusMessage を付ける。
- **FR2:** 入力の読み取り — 標準入力の JSON を読む。`tool_name` が `Write` / `Edit` / `MultiEdit` なら `tool_input.file_path` を、`Bash` なら `tool_input.command` を判定対象にする。JSON として読めない・型が合わない・値が空・それ以外の tool_name・payload の `cwd` が文字列でない場合は何も出力しない。
- **FR3:** 比較の基準となるリポジトリ — payload の `cwd` で `git rev-parse --show-toplevel` を実行し、その出力だけを基準にする。cwd が git リポジトリ内でない・git が無い・git が失敗する・時間切れの場合は何も出力しない。worktree（`.claude/worktrees/` 配下を含む）からメイン作業ツリーへの書き込みも外側として扱う。
- **FR4:** パスの解決と正規化 — 相対パスは payload の `cwd` を起点に絶対パスにする。引用されていない先頭の `~` と `~/` だけを HOME に展開し、`$HOME` / `${HOME}` は変数展開として判定しない。`.` / `..` を正規化し、存在する最長の親までシンボリックリンクを解決して（os.path.realpath 相当）比較する。toplevel と除外根も同じ方法で解決し、パス要素の境界で比較する（`/repo` は `/repo-other` を含まない）。
- **FR5:** 判定しない書き込み先 — `/tmp` 配下と `~/.claude/` 配下は判定しない（FR4 と同じ解決をしたうえで境界比較）。`/dev/null`、`/dev/stdout`、`/dev/stderr`、`/dev/tty`、`/dev/fd/` 配下は、シンボリックリンク解決より前に字面（`.` / `..` の字面正規化後の絶対パス）で照合して判定から除く。それ以外の `/dev` 配下は通常どおり判定する。
- **FR6:** 判定の出力 — 判定対象の書き込み先が 1 つでも toplevel の外なら、`permissionDecision: "ask"` を 1 件出力する。理由には `[cross-repo-write-guard]` を前置し、外側と判定した書き込み先の絶対パスと toplevel を含める。環境変数 `CLAUDE_BATCH` が空・`0`・`false`・`no` 以外のときは `deny` に降格し、降格した旨を理由に追記する。`allow` は出力しない。外側の書き込み先が無ければ何も出力しない。終了コードは常に 0。
- **FR7:** Bash で判定する書き込みの形 — 静的に書き込み先を確定できる次の形を判定する。(a) 出力リダイレクト `>`、`>>`、`>|`、`&>`、`&>>` と、fd 番号付きの `N>`、`N>>`、`N>|`（`>&N` / `N>&M` / `>&-` の fd 複製は書き込み先にしない）。(b) `tee` のファイルオペランドすべて。(c) `sed -i` / `--in-place`（GNU sed の解釈）の対象ファイル。スクリプトは `-e` / `-f` が無ければ最初の非オプション語。(d) `cp` / `mv` の書き込み先（`-t DIR` / `--target-directory` があればそれ、無ければオペランドが 2 つ以上あるときの最後のオペランド）。`mv` の移動元、その他のコマンド（touch / mkdir / rm / dd / install / ln / rsync など）は判定しない。
- **FR8:** Bash の構文の解析範囲 — 最上位の単純コマンド、サブシェル `( )` と波括弧 `{ }` の内部、ラッパー（sudo / env / nohup / time / command / nice）と先頭の変数代入の後ろのコマンドを判定する。`bash -c` 等の文字列、`$( )`・バッククォート・プロセス置換の本体は判定しない。それらを含む文の外側のリダイレクトは判定する。ヒアドキュメント本文・クォート内の文字列・コメントはコマンドとして読まない。
- **FR9:** 解決できない書き込み先 — 変数展開・コマンド置換・glob（`*` `?` `[`）・解析器が扱わない引用を含む書き込み先は判定しない（同じコマンド内の他の書き込み先は判定を続ける）。閉じないクォートやヒアドキュメントなどでコマンド全体を解析できない場合は何も出力しない。
- **FR10:** 作業ディレクトリ変更の後の相対パス — 同じコマンド内で `cd` / `pushd` / `popd` が現れた後の相対パスの書き込み先は判定しない。絶対パスは判定する。サブシェル内の `cd` は外側へ持ち出さない（波括弧内の `cd` は以降に効く）。`env -C` / `sudo --chdir` などの作業ディレクトリ変更付きラッパーを使った文の相対パスの書き込み先も判定しない。
- **FR11:** 失敗時の扱い — 処理中の予期しない例外はすべて何も出力せず終了コード 0 で終える。
- **FR12:** フックのテスト — `tests/test_cross_repo_write_guard.py` を追加する。Bash の判定ケースは `CASES` に `(期待する判定, ラベル, コマンド)` で並べ、期待する判定は `ask` か `silent`。Write / Edit / MultiEdit、CLAUDE_BATCH による降格、不正な入力はそれぞれ別のテストで確かめる。フックはサブプロセスとして JSON を標準入力に渡して起動する。
- **FR13:** hook-tests.md への追記 — `.claude/rules/hook-tests.md` に `## cross-repo-write-guard` 節を追加する。変更時に `python3 -m unittest tests.test_cross_repo_write_guard` を走らせること、ケースの置き場所と形（`CASES` に `(期待する判定, ラベル, コマンド)`、期待する判定は `ask` か `silent`）を書く。
- **FR14:** 登録テストの更新 — `tests/test_hooks_registration.py` の重複検査のキーを `(event, matcher, script)` に変え、同じ matcher 内の重複検出は維持する。PreToolUse(Bash) 配列の固定検査を 10 件に更新し、cross-repo-write-guard.py の位置を固定する。`tests/test_guardrail_hooks_migration.py` の `EXPECTED_BASH_GUARD_ORDER` に loop-command-guard.py と destructive-guard.py の間として追加する。テストのクラス名・メソッド名を変える場合、それを参照する `test-docs/**/*.tests.yaml` の ID も同じ変更で直す。
- **FR15:** README の更新 — `em-workflow/README.md` のガードレール hook 表に cross-repo-write-guard.py の行（イベント: PreToolUse(Bash) と PreToolUse(Write|Edit|MultiEdit)）を追加し、PreToolUse(Bash) の本数と配列順の記述を 10 本に更新する。冒頭の「4 本同梱」の古い本数は、表と食い違わない形に直す。
- **FR16:** destructive-guard.py は変更しない — `em-workflow/hooks/destructive-guard.py` は変更しない。判定の優先順位（deny > defer > ask > allow）により、その allow は新フックの ask / deny を上書きしない。

### Non-Functional Requirements
- **NFR1 - 依存:** フックとテストは Python 標準ライブラリのみを使う。
- **NFR2 - 副作用:** フックはファイルを書かない。外部プロセスは `git rev-parse --show-toplevel` の 1 回だけで、除外・解決不能を除いた判定対象の書き込み先が 1 つ以上あるときだけ起動する。
- **NFR3 - 時間:** git の呼び出しにはフックの timeout（15 秒）より短い時間制限を付け、超えたら何も出力しない。
- **NFR4 - テストの隔離:** テストは実際の `~/.claude` に触れない。HOME を一時ディレクトリに差し替え、フィクスチャの git リポジトリは一時ディレクトリに作る。

## Implementation Approach

### Architecture

**フックの登録位置（FR1）:**
```
hooks.json PreToolUse
├── matcher: Bash
│   ├── ...
│   ├── loop-command-guard.py
│   ├── cross-repo-write-guard.py   # 追加
│   └── destructive-guard.py
└── matcher: Write|Edit|MultiEdit
    ├── ...
    ├── gitleaks-write-guard.sh
    └── cross-repo-write-guard.py   # 追加（gitleaks-write-guard.sh の後）
```

コマンド形は `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/cross-repo-write-guard.py`、timeout は 15、statusMessage を付ける。

### Data Flow

```
標準入力 JSON
  → tool_name で分岐（FR2）
      Write / Edit / MultiEdit: tool_input.file_path
      Bash: tool_input.command を解析（FR7〜FR10）
  → 書き込み先ごとに解決（FR4）・除外（FR5）・解決不能の除去（FR9）
  → 判定対象が 1 つ以上あるときだけ cwd で git rev-parse --show-toplevel（FR3, NFR2, NFR3）
  → toplevel の外の書き込み先があれば ask、CLAUDE_BATCH が有効なら deny（FR6）
  → それ以外・失敗時は何も出力しない（FR2, FR3, FR9, FR11）。終了コードは常に 0
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/hooks.json`: PreToolUse の `Bash` と `Write|Edit|MultiEdit` の 2 matcher に登録する（FR1）。
- `em-workflow/hooks/destructive-guard.py`: 変更しない（FR16）。

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）。
- git: `git rev-parse --show-toplevel` の 1 回だけ（NFR2）。

### File Structure

```
em-workflow/
├── hooks/
│   ├── cross-repo-write-guard.py      # 追加（FR1〜FR11）
│   ├── hooks.json                     # 登録を追加（FR1）
│   └── destructive-guard.py           # 変更しない（FR16）
└── README.md                          # hook 表と本数・配列順の記述を更新（FR15）
tests/
├── test_cross_repo_write_guard.py     # 追加（FR12）
├── test_hooks_registration.py         # 重複検査キーと Bash 配列の固定検査を更新（FR14）
└── test_guardrail_hooks_migration.py  # EXPECTED_BASH_GUARD_ORDER を更新（FR14）
.claude/rules/
└── hook-tests.md                      # cross-repo-write-guard 節を追加（FR13）
```

テストのクラス名・メソッド名を変える場合は、それを参照する `test-docs/**/*.tests.yaml` の ID も同じ変更で直す（FR14）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/cross-repo-write-guard/**`
- `test-docs/cross-repo-write-guard/**`

`feature-docs/cross-repo-write-guard/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/cross-repo-write-guard/**` covers `test-docs/cross-repo-write-guard/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/cross-repo-write-guard/` directory at all; the declared
`test-docs/cross-repo-write-guard/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: Write / Edit / MultiEdit の内外判定（AC-2: FR2, FR5, FR6） - フィクスチャ repo 内・外・/tmp 配下・HOME 差し替え後の ~/.claude 配下・相対 file_path。
- [ ] TS-2: リポジトリ外の cwd と不正入力（AC-3: FR2, FR3, FR11） - git 管理外の cwd、壊れた JSON、tool_name 違い、空 command、cwd 欠落。
- [ ] TS-3: worktree からメイン作業ツリーへ（AC-4: FR3） - `git worktree add` で作った worktree を cwd にする。
- [ ] TS-4: シンボリックリンクと境界（AC-5: FR4） - repo 内リンク経由の外向き書き込み（未作成ファイル）、`repo` と `repo-other`。
- [ ] TS-5: /dev の除外リスト（AC-6: FR5） - `> /dev/null`、`2>/dev/null`、`&>/dev/null`、`/dev/fd/1`、列挙外の /dev パス。
- [ ] TS-6: 書き込みの形ごとの判定（AC-7: FR7） - `>`、`>>`、`>|`、`&>`、`2>`、`>&2`（判定しない）、`tee -a`、`sed -i`、`sed -i.bak -e`、`cp a b`、`cp -t DIR a`、`mv a b`、オペランド 1 つの cp。
- [ ] TS-7: 入れ子と非コマンド文字列（AC-8: FR8） - `( )`、`{ ; }`、`sudo` / `env` / `nohup` / `time` / `command` / `nice`、`bash -c '...'`、`x=$(...)`、外側リダイレクト付きの `bash -c`、ヒアドキュメント本文、クォート、コメント。
- [ ] TS-8: 解決できない書き込み先と ~（AC-9: FR4, FR9） - `$VAR`、`${HOME}`、`$(pwd)/x`、glob、引用された `'~/x'`、引用されていない `~/x`。
- [ ] TS-9: cd の後（AC-10: FR10） - `cd /x && echo > a`（silent）、`cd /x && echo > /outside/a`（ask）、`(cd /x && echo > a); echo > ../outside`（ask）、`pushd`、`env -C`。
- [ ] TS-10: 無人実行の降格（AC-11: FR6） - CLAUDE_BATCH=1 で deny、`0` / `false` / `no` / 未設定で ask。理由の文言。
- [ ] TS-11: 登録とドキュメント（AC-1, AC-12, AC-13: FR1, FR12, FR13, FR14, FR15, FR16） - 既存の登録テスト 2 本と新テストの実行。

### Integration Tests
該当なし。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- TS-4・TS-5・TS-8・TS-9 に含まれる。

### Performance Tests
該当なし。

## Security Considerations

- **Input Validation:** FR2 のとおり、JSON として読めない・型が合わない・値が空・対象外の tool_name・`cwd` が文字列でない入力には何も出力しない。
- その他の項目（Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF）は該当なし。

## Error Handling

### Error Codes

| 条件 | 動作 | 要件 |
|------|------|------|
| 入力が不正（JSON として読めない・型が合わない・値が空・対象外の tool_name・`cwd` が文字列でない） | 何も出力しない | FR2 |
| cwd が git リポジトリ内でない・git が無い・git が失敗する・時間切れ | 何も出力しない | FR3, NFR3 |
| コマンド全体を解析できない（閉じないクォート・ヒアドキュメントなど） | 何も出力しない | FR9 |
| 予期しない例外 | 何も出力しない | FR11 |

どの場合も終了コードは 0（FR6, FR11）。

### Error Flow

```
例外・判定不能 → 何も出力しない → 終了コード 0
```

## Performance Optimization

### Performance Goals
- git の呼び出しにはフックの timeout（15 秒）より短い時間制限を付ける（NFR3）。

### Optimization Strategies
- 外部プロセスは `git rev-parse --show-toplevel` の 1 回だけで、除外・解決不能を除いた判定対象の書き込み先が 1 つ以上あるときだけ起動する（NFR2）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] AC-1〜AC-13 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（`status: tbd` の要件は無い）。

## Assumptions

- A-1: 比較は cwd の `--show-toplevel` とだけ行い、worktree からメイン作業ツリーへの書き込みも外側として ask（batch では deny）にする。
- A-2: destructive-guard.py は変更しない。docstring の古い記述の訂正も対象外。
- A-3: cwd が git リポジトリ内でないときは何も出力しない。
- A-4: /dev/null、/dev/stdout、/dev/stderr、/dev/tty、/dev/fd/ 配下だけをシンボリックリンク解決前に字面で除外する。
- A-5: cd / pushd / popd / env -C / sudo --chdir の後の相対パスは判定しない。サブシェル内の cd は外へ持ち出さない。
- A-6: 解析範囲は最上位・サブシェル・波括弧・ラッパーの後まで。bash -c 文字列と $( ) 本体は判定せず、外側のリダイレクトは判定する。
- A-7: realpath 相当で正規化し、toplevel と除外根も同様に解決してパス要素の境界で比較する。
- A-8: 引用されていない先頭の ~ と ~/ だけを HOME に展開し、$HOME / ${HOME} は判定しない。
- A-9: 1 本のスクリプトを Bash と Write|Edit|MultiEdit の 2 matcher に登録し、test_hooks_registration.py の重複検査キーを (event, matcher, script) にする。
- A-10: Bash グループでは loop-command-guard.py の直後・destructive-guard.py の直前に置く。
- A-11: timeout は標準の 15（NONSTANDARD_HOOK_TIMEOUTS への追加なし）。Write|Edit|MultiEdit グループでは gitleaks-write-guard.sh の後に置く。
- A-12: 判定する出力リダイレクトは `>`、`>>`、`>|`、`&>`、`&>>`、`N>`、`N>>`、`N>|`。fd 複製は書き込み先にしない。sed は GNU sed として解釈する。
- A-13: テストのフィクスチャ repo は /tmp の外の一時ディレクトリ（例: tempfile の dir に /var/tmp）に作り、HOME は一時ディレクトリに差し替える。
- A-14: README 冒頭の「4 本同梱」は本数を書かない文に直す。表に無い muse_guard.py / heredoc-stdin-guard.py の行は追加しない。
- A-15: version は手で変えない（Actions による patch 上げに任せる）。
- A-16: ユーザーが名指ししたパスの見分けは対象外。

## References

- 要件定義書: `feature-docs/cross-repo-write-guard/REQUIREMENTS.md`
