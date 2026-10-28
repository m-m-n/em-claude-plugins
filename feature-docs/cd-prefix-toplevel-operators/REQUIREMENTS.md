---
title: "cd-prefix-toplevel-operators"
created_date: 2026-10-28
status: draft
---

# cd-prefix-toplevel-operators - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/hooks/bash_guard.py` は、承認文字列に `cd "{worktree_path}" && ` を前置した形（cd 前置形）を allow する。承認文字列のトップレベルに単独の `&`、`;`、`||`、改行があると、承認文字列の一部が cd 先の worktree ではなく元の cwd（メイン作業ツリー）で動きうる。

### 1.2 目的

- bash_guard.py が allow する cd 前置形では、承認文字列の全部が cd 先の worktree で動く。元の cwd（メイン作業ツリー）で動く部分を残さない。
- hook・文書・試験を同じ変更で揃え、再発を試験で検出する。

### 1.3 スコープ

- `em-workflow/hooks/bash_guard.py` の cd 前置形の allow 条件と module docstring（FR1〜FR5、FR9）
- `em-workflow/references/command-execution-protocol.md` の Verbatim execution rule（FR6）
- `em-workflow/agents/implementer.md` の Step 3、`em-workflow/skills/worktree-task-workflow/SKILL.md` の Command execution gate 節（FR7）
- `em-workflow/README.md` の実行時強制の項、`em-workflow/references/workflow-schema.md` の Command approval store 節（FR8）
- `tests/` の hook 試験と文書試験（FR10）

`cd "{worktree_path}" && <承認文字列>` という実行形は変えない。

## 2. ビジネス要件

### 2.1 ビジネス目標

- bash_guard.py が allow する cd 前置形では、承認文字列の全部が cd 先の worktree で動く。元の cwd（メイン作業ツリー）で動く部分を残さない。
- hook・文書・試験を同じ変更で揃え、再発を試験で検出する。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| implementer | 承認文字列を cd 前置形で実行する em-workflow のエージェント |

### 2.3 期待される効果

- cd 前置形で allow されたコマンドは、すべて cd 先の worktree で動く。
- 再発を試験で検出できる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 承認文字列を cd 前置形で実行する | implementer | 高 |

### 3.2 ユースケース詳細

#### UC01: 承認文字列を cd 前置形で実行する

**アクター**: implementer

**事前条件**:
- 承認文字列が承認ストアにある。

**基本フロー**:
1. implementer が `cd "{worktree_path}" && <承認文字列>` を実行しようとする。
2. bash_guard.py が禁止パターンをコマンド全体に当てる（FR5）。
3. bash_guard.py が `<残り>` を FR2・FR3 の規則で走査し、対象外の条件に当たらないことを確かめる（FR1）。
4. 承認済みの cd 前置形として allow する。

**代替フロー**:
- 禁止パターンに一致した場合: 承認の有無に関係なく deny する（FR5）。
- `<残り>` が FR1〜FR3 の対象外の条件に当たる場合: 文字列全体を今の判定表で判定する。承認済みと完全一致なら allow、workflow.yaml にあって未承認なら deny、それ以外は判定なし（FR4）。
- 対象外になる承認文字列は、implementer が実行せず notes で報告する（FR6、FR7）。

**事後条件**:
- allow された cd 前置形では、承認文字列の全部が cd 先の worktree で動く。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | トップレベル演算子を含む承認文字列を cd 前置形の対象外にする | cd 前置形の allow 条件に、トップレベル演算子が無いことと FR3 の除外条件に当たらないことを加える | 高 |
| FR2 | 演算子の検出規則（引用と転送を区別する） | `<残り>` を左から走査し、引用・エスケープ・転送を区別して単独の演算子を数える | 高 |
| FR3 | 安全側の追加除外条件 | 入れ子を解析せず、解析が難しい構文を対象外にする | 高 |
| FR4 | 対象外にした形は今の判定表で判定する | 対象外の cd 前置形は文字列全体を今の判定表で判定し、新しい deny は足さない | 高 |
| FR5 | 禁止パターンの判定を先に当てる順序を保つ | 禁止パターンを FR1 より先にコマンド全体へ当てる | 高 |
| FR6 | command-execution-protocol.md に対象外の条件を書く | Verbatim execution rule に FR1〜FR3 の条件と implementer の扱いを書く | 中 |
| FR7 | implementer の手順書に、該当する承認文字列の扱いを書く | implementer.md と worktree-task-workflow SKILL.md に、実行せず notes で報告することを書く | 中 |
| FR8 | README.md と workflow-schema.md の説明に対象外の条件を書き足す | cd 前置形の allow 条件の説明に、対象外になる承認文字列を書き足す | 中 |
| FR9 | bash_guard.py の docstring を合わせる | module docstring の cd prefix の条件に FR1〜FR3 を書き足す | 中 |
| FR10 | 再発を検出する試験 | FR1〜FR4 の hook 試験と FR6〜FR8 の文書試験を足す | 高 |

### 4.2 機能詳細

#### FR1: トップレベル演算子を含む承認文字列を cd 前置形の対象外にする

**説明**: `em-workflow/hooks/bash_guard.py` の cd 前置形の allow 条件に、次の条件を加える。`<残り>`（最初の `&&` より後ろをトリムした文字列）に、FR2 の規則で数えた単独の `&`、`;`、`||`、改行が無い。さらに FR3 の除外条件にも当たらない。`cd "{worktree_path}" && <承認文字列>` という実行形は変えない。

#### FR2: 演算子の検出規則（引用と転送を区別する）

**説明**: `<残り>` を左から走査する。

**ビジネスルール**:
- 単一引用・二重引用・バックスラッシュエスケープの中の文字は数えない。
- 単一引用の中のバックスラッシュは通常の文字として扱う。
- 二重引用の中のエスケープは Bash の規則に従う。
- 引用の外では、`&&`、`|&`、`>&`、`<&`、`&>`、`&>>`、`||` を最長一致で 1 つのまとまりとして認識する。
- `&&`、`|&`、`>&`、`<&`、`&>`、`&>>` に含まれる `&` は数えない。
- それ以外の単独の `&`、`;`、`||`、改行があれば対象外にする。

#### FR3: 安全側の追加除外条件

**説明**: `<残り>` が次のどれかに当たる場合も対象外にする。入れ子は解析しない。

**ビジネスルール**:
- 閉じていない引用、末尾のバックスラッシュ、文字列の内部の改行
- `$'` または `$"`
- `#`（位置を問わない。引用の中も含む）
- 引用の外にある `(` `)` `{` `}`
- `$(...)`、`${...}`、バッククォート
- 二重引用の中の置換構文（`$(`、`${`、バッククォート）

#### FR4: 対象外にした形は今の判定表で判定する

**説明**: FR1〜FR3 で対象外になった cd 前置形は、文字列全体を今の判定表で判定する。

**ビジネスルール**:
- 承認済みと完全一致なら allow する。
- workflow.yaml にあって未承認なら deny する。
- それ以外は判定なし。
- 新しい deny は足さない。
- cd を前置しないコマンド（承認済みの `A & B` との完全一致を含む）の判定も変えない。

#### FR5: 禁止パターンの判定を先に当てる順序を保つ

**説明**: 禁止パターンは今までどおり、cd 前置部分を含むコマンド全体に FR1 より先に当てる。一致したら、承認の有無に関係なく deny する。

#### FR6: command-execution-protocol.md に対象外の条件を書く

**説明**: `em-workflow/references/command-execution-protocol.md` の Verbatim execution rule にある、hook が cd 前置形を allow する条件の箇条書きに、FR1〜FR3 の条件を書き足す。トップレベルに単独の `&`、`;`、`||`、改行を含む承認文字列などは対象外になる。あわせて、該当する承認文字列は implementer が実行せず notes で報告することを書く。

#### FR7: implementer の手順書に、該当する承認文字列の扱いを書く

**説明**: `em-workflow/agents/implementer.md` の Step 3 と、`em-workflow/skills/worktree-task-workflow/SKILL.md` の Command execution gate 節に、cd 前置形の対象外になる承認文字列は実行せず notes で報告することを書く。

#### FR8: README.md と workflow-schema.md の説明に対象外の条件を書き足す

**説明**: `em-workflow/README.md` の実行時強制の項と、`em-workflow/references/workflow-schema.md` の Command approval store 節にある cd 前置形の allow 条件の説明に、トップレベルに `&` / `;` / `||` を含む承認文字列は対象外になることを書き足す。詳細は `references/command-execution-protocol.md` に任せる。

#### FR9: bash_guard.py の docstring を合わせる

**説明**: bash_guard.py の module docstring にある cd prefix の条件の箇条書きに、FR1〜FR3 の条件を書き足す。

#### FR10: 再発を検出する試験

**説明**: `tests/` の hook 試験に、FR1〜FR4 を確かめるケースを足す。方式は `tests/test_bash_guard_cd_prefix.py` と同じ（hook を subprocess で起動して JSON を渡す、`EM_WORKFLOW_APPROVALS` で承認ストアを分ける、一時的な git リポジトリを使う）。FR6〜FR8 の文書の記述を確かめる文書試験も足す。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし

### 5.2 セキュリティ要件

- 入力検証: 判定は LLM を使わず、コードで決定的に行う。bash_guard.py は Python 標準ライブラリだけを使う（NFR1）。

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- hook 分類試験の前提を守る: bash_guard.py の実行コード（コメントと docstring を除く）に部分文字列 `"status"` を足さない（`tests/test_hook_classification_pin.py`、`tests/test_bash_guard_cd_prefix.py` の AC-7）（NFR2）。
- hash 固定ファイルと hook 登録を変えない: `em-workflow/hooks/queue_launch_guard.py` と `em-workflow/scripts/merge-task.sh` はバイト単位で変えない。`em-workflow/hooks/hooks.json` の登録内容と順序は変えない（NFR3）。
- version を変えない: プラグインの version は変えない（NFR4）。
- SKILL の gate 節の文言の制約: `worktree-task-workflow/SKILL.md` の Command execution gate 節では、`(byte-for-byte)` をちょうど 1 回だけにし、ほかに `byte`、`identical to`、`equal to the line` を書かない。implementer.md と SKILL.md には、`separate` と `cd` を同じ文に含む文、`chain` と `&&` と禁止語を同じ文に含む文、`may reset` / `may have reset` を含む文を書かない（`tests/test_implementer_cd_chain_docs.py` の AC-3、AC-5）（NFR5）。
- 既存の文書試験の固定を保つ: `tests/test_cd_prefix_exception_docs.py` と `tests/test_implementer_cd_chain_docs.py` が固定している文言（`cd "{worktree_path}" &&`、everything after the first `&&` … approved string、判定表の行の順序、only one `cd` と主張しないこと など）を保つ（NFR6）。
- 試験の実行方法: 試験は標準ライブラリの unittest だけを使い、`python3 -m unittest discover -s tests` がすべて通る（NFR7）。

### 5.5 互換性要件

- 既存の allow ケースと、cd を前置しないコマンドの判定は変えない（FR4、前提 A4）。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- bash_guard.py は Python 標準ライブラリだけを使う（NFR1）。
- 試験は標準ライブラリの unittest だけを使う（NFR7）。
- `em-workflow/hooks/queue_launch_guard.py` と `em-workflow/scripts/merge-task.sh` はバイト単位で変えない。`em-workflow/hooks/hooks.json` の登録内容と順序は変えない（NFR3）。

### 9.2 ビジネス上の制約

- プラグインの version は変えない（NFR4）。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/cd-prefix-toplevel-operators/**`
- `test-docs/cd-prefix-toplevel-operators/**`

`feature-docs/cd-prefix-toplevel-operators/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/cd-prefix-toplevel-operators/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/cd-prefix-toplevel-operators/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/cd-prefix-toplevel-operators/` ディレクトリを生成しないが、宣言された `test-docs/cd-prefix-toplevel-operators/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

該当なし

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `A & B` を承認済みにしたとき、`cd "<worktree 領域の下>" && A & B` に hook は allow を返さず、判定なしになる。（FR1、FR2、FR4）
- [ ] AC2: `A ; B`、`A || B`、および内部に改行を含む承認文字列でも、cd 前置形は判定なしになる。（FR1、FR2、FR3、FR4）
- [ ] AC3: 既存の allow ケース（`make test`、環境変数の代入で始まる文字列、`a && b`、パス条件の各 allow ケース）と、`make test 2>&1`、`a |& b`、`a | b`、`a &> log`、`a &>> log`、`a <&0`、引用の中の `;` や `&`（例: `echo "a;b"`、`echo 'a&b'`）、エスケープした `\;` を承認したときの cd 前置形は allow のまま。（FR1、FR2）
- [ ] AC4: FR3 の各条件に当たる承認文字列の cd 前置形は判定なしになる。対象は、閉じていない引用、末尾のバックスラッシュ、`$'…'`、`$"…"`、`#`、引用の外の `(` `)` `{` `}`、`$(...)`、`${...}`、バッククォート、二重引用の中の `$(` / `${` / バッククォート。（FR3、FR4）
- [ ] AC5: cd を前置しない `A & B` の完全一致は allow のまま。workflow.yaml にあって未承認の文字列は deny のまま。（FR4）
- [ ] AC6: 禁止パターンを含む承認文字列の cd 前置形は、トップレベル演算子の有無に関係なく deny され、理由に禁止パターンが示される。（FR5）
- [ ] AC7: command-execution-protocol.md の Verbatim execution rule、implementer.md の Step 3、worktree-task-workflow SKILL.md の Command execution gate 節、README.md の実行時強制の項、workflow-schema.md の Command approval store 節、bash_guard.py の docstring が、対象外の条件と implementer の扱いを、それぞれ FR6〜FR9 の範囲で書いている。文書試験がそれを確かめる。（FR6、FR7、FR8、FR9、FR10）
- [ ] AC8: `python3 -m unittest discover -s tests` がすべて通る。NFR2〜NFR6 の制約を満たす。（NFR1、NFR2、NFR3、NFR5、NFR6、NFR7）

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: `make test 2>&1`、`a |& b`、`a | b`、`a &> log`、`a &>> log`、`a <&0`、`a && b`、`echo "a;b"`、`echo 'a&b'`、`echo a\;b` を承認し、cd 前置形が allow のままであることを確かめる（AC3）。
- [ ] 正常系: `tests/test_bash_guard_cd_prefix.py` の既存ケースがすべて通ることを確かめる（AC3、AC8）。
- [ ] 正常系: cd を前置しない `A & B` の完全一致が allow、宣言済みで未承認の文字列が deny のままであることを確かめる（AC5）。
- [ ] 異常系: `A & B`、`A ; B`、`A || B`、`A &`、`A;` を承認し、cd 前置形が判定なしになることを確かめる（AC1、AC2）。
- [ ] 異常系: FR3 の各条件（閉じていない引用、末尾のバックスラッシュ、`$'x'`、`$"x"`、`#` の位置違い（引用の中を含む）、引用の外の `(` `)` `{` `}`、`$(true)`、`${HOME}`、バッククォート、二重引用の中の `$(` / `${` / バッククォート）を承認し、cd 前置形が判定なしになることを確かめる（AC4）。
- [ ] セキュリティ: 禁止パターンを含み `&` も含む承認文字列（承認ストアに直接書く）の cd 前置形が deny になることを確かめる（AC6）。
- [ ] 文書: 見出しで節を切り出し、空白を正規化して、FR6〜FR9 の記述（対象外の条件、implementer が実行せず notes で報告すること）が各文書にあることを確かめる。不在を確かめる assertion には、照合器が反応することを示す偽の文のケースを組にする（AC7）。
- [ ] 境界値:
    - `&&&` のように `&&` の直後に `&` が続く場合: `&&` を認識した後の単独の `&` を数えて対象外にする。
    - `||` と `|&` の区別: 引用の外で最長一致で認識する。
    - 単一引用の中のバックスラッシュ（`'a\'`）: 通常の文字として扱い、引用はそこで閉じる。
    - 二重引用の中のエスケープした引用符（`"a\"b"`）: 引用は閉じない。
    - 二重引用の中の素の `$VAR`: FR3 の除外対象ではない。
    - `<残り>` の前後の空白・末尾の改行: トリムしたあとに判定する（hook は入力全体も先に strip している）。
    - path 部分に `&&` や空白を含む場合: 走査するのは `<残り>` だけで、path は対象外（既存ケース `x && y` ディレクトリ）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| cd 前置形 | `cd "{worktree_path}" && <承認文字列>` という実行形 |
| `<残り>` | cd 前置形の最初の `&&` より後ろをトリムした文字列 |
| 判定なし | hook が allow も deny も返さないこと |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 修正方針（requirement.fix-approach）: exclude_toplevel_operators とする。`cd "{worktree_path}" && <承認文字列>` という実行形は変えない。（A1）
- [x] 検出の精度（requirement.operator-detection-precision）: quote_and_redirect_aware とする。FR2 の走査規則と FR3 の安全側の追加除外条件は、回答で示された詳細化（単一引用の中のバックスラッシュ、二重引用の中のエスケープ、最長一致での認識、`$'` / `$"` / `#`、括弧・波括弧、置換構文）に従う。（A2）
- [x] 設計ステップ（design-step.decision）: 省略する。（A5）

### 14.2 未確認・保留事項

なし

### 14.3 前提

- A3: 対象外になった cd 前置形は判定なしに落ちる。新しい deny は足さない。
- A4: 既存の allow ケースと、cd を前置しないコマンドの判定は変えない。
- A6: bash_guard.py の未承認 deny の additionalContext（`UNAPPROVED_GUIDANCE`）は変えない。対象外になった形は判定なしに落ち、deny にならないため、この案内は出ない。

## 15. 参考資料

- 該当なし
