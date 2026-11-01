---
title: "approval-unicode-whitespace"
created_date: 2026-11-01
status: draft
---

# approval-unicode-whitespace - 要件定義書

## 1. 概要

### 1.1 背景

Bash が単語の区切りとして扱わない Unicode 空白（U+00A0、U+000B、U+000C など）をコマンドの前後に置くと、そのコマンドが承認済みの別のコマンドとして数えられる。

例: `/usr/bin/true` が承認済みの状態で、test_command を U+00A0 + `/usr/bin/true` とし、作業ツリーに `<U+00A0>/usr/bin/true` という実行ファイルを置く。

### 1.2 目的

2.1 のビジネス目標を達成する。

### 1.3 スコープ

- merge-preflight.py の承認照合（`check_approval`、`collect_commands`）
- bash_guard.py の承認照合（`hook_main`、`is_cd_prefixed_approved`、`cd_remainder_excluded`、`approved_for`、`--list`、`read_stdin_commands`（`--record` / `--remove`）、`declared_commands`）
- 承認照合のトリムに関する記述
    - `em-workflow/references/command-execution-protocol.md`
    - bash_guard.py の docstring
    - merge-preflight.py のモジュール docstring と `check_approval` のコメント
- 上記のテスト（`tests/`）

## 2. ビジネス要件

### 2.1 ビジネス目標

- Bash が単語の区切りとして扱わない Unicode 空白（U+00A0、U+000B、U+000C など）をコマンドの前後に置いても、そのコマンドが承認済みの別のコマンドとして数えられない
- merge-preflight.py と bash_guard.py を同じ変更で直し、両者の承認判定を一致させたままにする

### 2.2 対象ユーザー

該当なし

### 2.3 期待される効果

2.1 のとおり。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | 「照合対象」とトリムの定義 | 承認照合のトリムはスペースとタブだけを両端から除く。除いた後も前後に空白文字が残る値は照合対象外とし、どの経路でも承認しない | resolved |
| FR2 | preflight の承認照合 | `check_approval` は照合対象の値だけを `--list` の集合と照合する | resolved |
| FR3 | preflight の空値判定 | `collect_commands` はスペースとタブを除いて空になる値だけを空として扱う | resolved |
| FR4 | フックの入口 | `hook_main` は受け取ったコマンドの両端からスペースとタブだけを除く | resolved |
| FR5 | cd 前置形の残り部分 | `is_cd_prefixed_approved` と `cd_remainder_excluded` の残り部分のトリムはスペースとタブだけを除く | resolved |
| FR6 | 保存済みエントリ | `approved_for` と `--list` は照合対象外のエントリを承認済みとして扱わない | resolved |
| FR7 | `--record` / `--remove` の入力 | `read_stdin_commands` は行末の LF を 1 つ除いた後にスペースとタブを除いて検証する | resolved |
| FR8 | 宣言済みコマンドの抽出 | `declared_commands` は `COMMAND_KEY_RE` の `\s` を `[ \t]` に変え、値からスペースとタブだけを除く | resolved |
| FR9 | ドキュメント | トリムの記述を「スペースとタブだけを除く。それ以外の空白が前後にある値は承認しない」に改める | resolved |

### 4.2 機能詳細

#### FR1: 「照合対象」とトリムの定義

**説明**: 承認照合のためにトリムするすべての箇所で、両端から除くのはスペース（U+0020）とタブ（U+0009）だけにする。

**ビジネスルール**:
- トリム後の値の先頭または末尾が `str.isspace()` が真になる文字（LF、CR、U+000B、U+000C、U+00A0、U+0085、U+2000〜U+200A、U+3000 など）のとき、その値は照合対象外とし、どの経路でも承認しない。
- 内側の空白は正規化せず、完全一致で比較する。

#### FR2: preflight の承認照合

**説明**: merge-preflight.py の `check_approval` は、照合対象の値だけをスペースとタブを除いた形で `--list` の集合と照合する。

**ビジネスルール**:
- 照合対象外の値は `commands_unapproved` で止める。
- LF / CR を含む値を除外する既存の扱いは維持する。
- `commands` に出力するコマンドは、トリムしていない元の値のままにする。

#### FR3: preflight の空値判定

**説明**: `collect_commands` は、スペースとタブを除いて空になる値だけを空として扱う。

**ビジネスルール**:
- それ以外の空白だけでできた値（例: U+00A0 のみ）は読み飛ばさず、未承認のコマンドとして扱う。

#### FR4: フックの入口

**説明**: bash_guard.py の `hook_main` は、受け取ったコマンドの両端からスペースとタブだけを除く。LF も除かない。

**ビジネスルール**:
- トリム後に照合対象外のコマンドは許可しない。
    - workflow.yaml で宣言されていれば、未承認として拒否する。
    - 宣言されていなければ、判定を返さない。
- トリム後に空になるコマンドは、現在と同じく判定を返さない。

#### FR5: cd 前置形の残り部分

**説明**: `is_cd_prefixed_approved` と `cd_remainder_excluded` での残り部分のトリムは、スペースとタブだけを除く。

**ビジネスルール**:
- 照合対象外の残り部分は、cd 前置形では許可しない。

#### FR6: 保存済みエントリ

**説明**: `approved_for` は保存済みエントリからスペースとタブだけを除き、照合対象外のエントリを承認済みとして数えない。

**ビジネスルール**:
- `--list` は照合対象外のエントリを出力しない。

#### FR7: `--record` / `--remove` の入力

**説明**: `read_stdin_commands` は、stdin の各行から行末の LF をちょうど 1 つ除き、その後スペースとタブを除いて検証する。

**ビジネスルール**:
- CR、U+000B、U+000C、U+00A0 は除かない。
- トリム後に空になる行は、現在と同じく読み飛ばす。
- 1 回の入力に照合対象外の行が 1 つでもあれば、`--record` と `--remove` はどちらも拒否パターンと同じく stderr に報告して終了コード 1 で終わる。その入力からは何も保存せず、何も削除しない。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 照合対象外の行 | stdin に照合対象外の行が 1 行以上ある | stderr に報告し、終了コード 1。ストアは変更しない |

#### FR8: 宣言済みコマンドの抽出

**説明**: `declared_commands` は `COMMAND_KEY_RE` の `\s` を `[ \t]` に変え、値からスペースとタブだけを除く。

**ビジネスルール**:
- 照合対象外の値も宣言済みの集合に含める。フックはそれを未承認として拒否する。

#### FR9: ドキュメント

**説明**: 次のトリムの記述を「スペースとタブだけを除く。それ以外の空白が前後にある値は承認しない」という内容に改める。

- `em-workflow/references/command-execution-protocol.md` の 'Trim surrounding whitespace; skip empty' / 'after trimming' / '(surrounding whitespace aside)'
- bash_guard.py の docstring の 'surrounding blanks removed'
- merge-preflight.py のモジュール docstring（Approval rule の `str.strip()` の記述）
- `check_approval` のコメント

**ビジネスルール**:
- `tests/test_cd_prefix_operator_exclusion_docs.py` が固定している文言は維持する。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし

### 5.2 セキュリティ要件

- 入力検証: 4 章の FR1〜FR8 のとおり。

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- NFR1: bash_guard.py は標準ライブラリのモジュールだけを import する（`TestAc7StandardLibraryOnly`）。
- NFR2: bash_guard.py の実行されるテキストに部分文字列 'status' を含めない（`tests/test_hook_classification_pin.py`）。
- NFR3: テストは Python 3.14 標準ライブラリの unittest だけを使い、`EM_WORKFLOW_APPROVALS` でストアを分離する。
- NFR4: version は変更しない。

### 5.5 互換性要件

- スペースとタブだけが前後にあるコマンドは、これまでどおり承認される（AC10）。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- NFR1〜NFR3 のとおり。

### 9.2 ビジネス上の制約

- NFR4 のとおり。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/approval-unicode-whitespace/**`
- `test-docs/approval-unicode-whitespace/**`

`feature-docs/approval-unicode-whitespace/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/approval-unicode-whitespace/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/approval-unicode-whitespace/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/approval-unicode-whitespace/` ディレクトリを生成しないが、宣言された `test-docs/approval-unicode-whitespace/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1 [FR1, FR2]: `/usr/bin/true` が承認済みのとき、test_command の前・後・両方に U+00A0、U+000B、U+000C のいずれかがあれば、preflight は `commands_unapproved` で止まる
- [ ] AC2 [FR1, FR4, FR8]: `/usr/bin/true` が承認済みのとき、前・後・両方に U+00A0、U+000B、U+000C のいずれかがあるコマンドを bash_guard は許可しない。同じ値が workflow.yaml で宣言されていれば拒否する
- [ ] AC3 [FR5]: cd 前置形で、残り部分の前または後に U+00A0、U+000B、U+000C のいずれかがあれば許可しない
- [ ] AC4 [FR2, FR4]: 攻撃シナリオ（test_command = U+00A0 + `/usr/bin/true`、作業ツリーに `<U+00A0>/usr/bin/true` の実行ファイル）を再現しても、preflight と bash_guard のどちらも承認しない
- [ ] AC5 [FR2, FR4]: `test_fr4_ac3_preflight_agrees_with_bash_guards_own_approval_decision` で、U+000C/U+000B のケースと U+00A0 のケースが「承認されない」になり、両者の一致は保たれる
- [ ] AC6 [FR4, FR5]: 承認済みの文字列に末尾 LF を付けたもの、承認済みの文字列にバックスラッシュ + LF を続けたものは、単独のコマンドとしても cd 前置形でも許可しない。末尾 LF で ALLOW を期待していた既存の 2 テスト（`tests/test_bash_guard_cd_prefix.py:424`、`tests/test_bash_guard_cd_prefix_operators.py:396`）は ALLOW を期待しなくなる
- [ ] AC7 [FR7]: 照合対象外の行（CRLF の行を含む）を含む stdin を与えると、`--record` と `--remove` は終了コード 1 で終わり、同じ入力の他の行が照合対象でもストアは変わらない
- [ ] AC8 [FR6]: ストアに既にある照合対象外のエントリを、`approved_for` と `--list` は承認済みとして扱わない
- [ ] AC9 [FR3]: U+00A0 だけでできた値を preflight は読み飛ばさず、未承認として止まる
- [ ] AC10 [FR1]: 前後にスペースとタブだけがあるコマンドの照合は、これまでどおり承認される（既存のスペース / タブのケースが通る）
- [ ] AC11 [FR9]: ドキュメントに、スペースとタブだけを除くことが書かれている。`python3 -m unittest discover -s tests` が通る

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1 `tests/test_merge_preflight.py`: AC1、AC4、AC9（U+00A0 / U+000B / U+000C × 前 / 後 / 両方。`'  make test'` のようなスペースとの混在を含む）。1198〜1199 行の 2 ケースの期待を「承認されない」に変える（AC5）
- [ ] TS2 bash_guard（既存の `test_bash_guard_cd_prefix*` のファイル、または新規の `tests/test_bash_guard_*.py`）: AC2、AC3、AC4、AC6、AC7、AC8。フックのサブプロセス、`--record` / `--remove` / `--list`、`EM_WORKFLOW_APPROVALS` を通す
- [ ] TS3 `tests/test_bash_guard_cd_prefix.py:424` と `tests/test_bash_guard_cd_prefix_operators.py:396` の期待を ALLOW から ALLOW 以外に変える
- [ ] TS4 その他の `str.isspace()` の代表的な文字（U+0085、U+2000、U+3000、U+001F）も承認されない
- [ ] TS5 内側に U+00A0 がある `make<U+00A0>test` は `make test` と一致しない

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| トリム | 承認照合のために値の両端からスペース（U+0020）とタブ（U+0009）だけを除くこと |
| 照合対象 | トリム後の値の先頭も末尾も `str.isspace()` が真になる文字でない状態 |
| 照合対象外 | トリム後の値の先頭または末尾が `str.isspace()` が真になる文字である状態。どの経路でも承認しない |
| cd 前置形 | cd を前に置いたコマンドの形。`is_cd_prefixed_approved` と `cd_remainder_excluded` が残り部分を扱う |

## 14. 確認事項

### 14.1 確認済み事項

該当なし

### 14.2 未確認・保留事項

なし

### 14.3 前提

- A1（影響度: 中、可逆）: `--remove` は照合対象外の行を `--record` と同じく扱う。終了コード 1 で、ストアは変更しない。ストアに既にある照合対象外のエントリは `approved_for` が返さないため、次に成功した `--record` / `--remove` がそれを除いてストアを書き直す。`--remove` で拒否しても片付けは妨げられない。
- A2（影響度: 低、可逆）: POSIX では `sys.stdin` は改行を変換しない。`--record` / `--remove` の stdin の CRLF の行は、LF を 1 つ除いた後も CR が残り、照合対象外として拒否される。
- A3（影響度: 低、可逆）: `declared_commands` は workflow.yaml を `open()` のユニバーサル改行で読むため、CRLF の行末は LF に正規化される。`[ \t]` への変更で宣言値に CR が入ることはない。
- A4（影響度: 低、可逆）: 既存の挙動を維持する。preflight での LF / CR を含む値の除外、内側の空白を含めた完全一致、`CD_PREFIX_RE` の区切り（`[ \t]`）、拒否パターン。
- A5（影響度: 低、可逆）: version は変更しない。

## 15. 参考資料

- `em-workflow/references/command-execution-protocol.md`
