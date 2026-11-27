---
title: "wake-task-cleanup-script"
created_date: 2026-11-27
status: draft
---

# wake-task-cleanup-script - 要件定義書

## 1. 概要

### 1.1 背景
implement の wake 手順 4（タスク worktree の削除とタスクブランチの削除）は、オーケストレーターがその場で git コマンドを組み立てて実行している。

### 1.2 目的
- implement の wake 手順 4（タスク worktree の削除とタスクブランチの削除）を em-workflow/scripts/ のスクリプトで実行し、オーケストレーターがその場で git コマンドを組み立てないようにする
- 呼び出し元の作業ディレクトリに関係なく、integration に取り込み済みのタスクブランチを強制しない削除で消せるようにする

### 1.3 スコープ
- em-workflow/scripts/ に置く後片付けスクリプト
- implement-phase.md の手順 4 の書き換え
- 上記のテスト

UI の変更は無い（デザインステップは実施しない）。

## 2. ビジネス要件

### 2.1 ビジネス目標
- implement の wake 手順 4 を em-workflow/scripts/ のスクリプトで実行し、オーケストレーターがその場で git コマンドを組み立てないようにする
- 呼び出し元の作業ディレクトリに関係なく、integration に取り込み済みのタスクブランチを強制しない削除で消せるようにする

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| オーケストレーター | implement フェーズの wake 手順 4 でスクリプトを呼び、結果の JSON を wake フェーズの報告に書く |

### 2.3 期待される効果
- wake 手順 4 で、オーケストレーターが git コマンドをその場で組み立てなくなる
- 呼び出し元の作業ディレクトリ（メインのツリーを含む）に関係なく、integration に取り込み済みのタスクブランチが強制しない削除で消える

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | wake 手順 4 でタスク worktree とタスクブランチを片付ける | オーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: wake 手順 4 でタスク worktree とタスクブランチを片付ける

**アクター**: オーケストレーター

**事前条件**:
- タスクブランチ em-workflow/{feature}/{T} が integration にマージされた直後である

**基本フロー**:
1. オーケストレーターが implement-phase.md の手順 4 に従い、${CLAUDE_PLUGIN_ROOT}/scripts/ で解決したスクリプトを、integration worktree・feature・タスク ID を渡して呼ぶ
2. スクリプトが入力を検証する
3. スクリプトが git worktree remove でタスク worktree を消す
4. スクリプトが integration worktree を基準にした git branch -d で em-workflow/{feature}/{T} を消す
5. スクリプトが結果を標準出力に JSON 1 つで返し、終了コード 0 で終わる
6. オーケストレーターが JSON を読み、残したブランチ名と理由を wake フェーズの報告に書く
7. 手順 3 の status は変わらず、手順 5 に進む

**代替フロー**:
- 入力が不正: git を 1 つも実行せずに 0 以外で終了する
- タスク worktree の削除に失敗: ブランチ削除を試さず、worktree を残したこと・git が返した理由・ブランチ削除を見送ったことと見送った理由を JSON に入れて返す（終了コード 0）
- タスクブランチを消せない: 残したブランチ名と理由を JSON に入れて返す（終了コード 0）
- タスク worktree やタスクブランチが既に無い: 片付け済みとして扱い、対象ごとに「既に無い」を「今回消した」と区別して返す

**事後条件**:
- 消せた対象は消えており、残した対象とその理由が JSON に入っている

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 後片付けスクリプト | wake 手順 4 の後片付けを行うスクリプトを em-workflow/scripts/ に置く | 高 |
| FR2 | 実行するコマンド | git worktree remove と、integration worktree を基準にした git branch -d を実行する。-D、--force、-f は使わない | 高 |
| FR3 | 残したブランチの報告 | 消せなかったブランチの名前と理由を機械で読める形で返す | 高 |
| FR4 | 手順書の書き換え | implement-phase.md の手順 4 をスクリプトの呼び出しに書き換える | 高 |
| FR5 | 入力の検証 | feature・タスク ID・integration worktree のパスの形を確かめる | 高 |
| FR6 | worktree の削除に失敗したとき | ブランチ削除を試さず、両方の理由を返す | 高 |
| FR7 | 対象が既に無いとき | 「既に無い」を「今回消した」と区別して返す | 高 |
| FR8 | 結果の返し方と終了コード | 標準出力の JSON 1 つで返し、終了コードは 0 | 高 |

### 4.2 機能詳細

#### FR1: 後片付けスクリプト

**説明**: wake 手順 4 の後片付けを行うスクリプトを em-workflow/scripts/ に置く。入力は integration worktree、feature、タスク ID など、後片付けに必要な値だけにする。

**入力**:
- integration worktree: パス - feature の integration worktree
- feature: 文字列 - feature 名
- タスク ID: 文字列 - 片付けるタスクの ID

**出力**:
- 結果: JSON（標準出力に 1 つ） - 対象ごとの結果（FR3、FR6、FR7、FR8）
- 終了コード: 整数 - FR8 のとおり

#### FR2: 実行するコマンド

**説明**: スクリプトは git worktree remove でタスク worktree を消し、integration worktree を基準にした git branch -d で em-workflow/{feature}/{T} を消す。-D、--force、-f は使わない。

**ビジネスルール**:
- 強制削除のフラグ（-D、--force、-f）を使わない
- git branch -d は integration worktree を基準にして実行する

#### FR3: 残したブランチの報告

**説明**: ブランチを消せなかったときは、残したブランチ名と理由を機械で読める形で返す。オーケストレーターはその値を wake フェーズの報告に書く。

#### FR4: 手順書の書き換え

**説明**: implement-phase.md の手順 4 は git コマンドを直接書かず、${CLAUDE_PLUGIN_ROOT}/scripts/ で解決したスクリプト（Step I.0 step 4 と同じ方法）を呼ぶ。強制削除に頼らないこと、手順 3 の status が変わらないこと、手順 5 が今までどおり進むことは残す。

**ビジネスルール**:
- 手順 4 の見出し「4. **Clean up** every newly-merged task's worktree and branch:」、失敗時の決まりの文言、手順 5 の後の batch mode 段落の書き出しは変えない
- 手順 4 は、終了コードだけでなく JSON を読み、残したブランチ名と理由を wake フェーズの報告に書くと定める（FR8）

#### FR5: 入力の検証

**説明**: feature とタスク ID を、プラグインが既に feature 名とタスク ID に使っている検証用の正規表現で確かめ、integration worktree のパスの形も確かめる。合わなければ git を 1 つも実行せずに 0 以外で終了する。

**バリデーション**:
| 項目 | ルール | エラーメッセージ |
|------|--------|------------------|
| feature | プラグインが既に feature 名に使っている検証用の正規表現に合う | 規定しない |
| タスク ID | プラグインが既にタスク ID に使っている検証用の正規表現に合う | 規定しない |
| integration worktree | パスの形が合う | 規定しない |

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 入力不正 | feature・タスク ID・integration worktree のパスのいずれかが合わない | git を 1 つも実行せずに 0 以外で終了する |

#### FR6: worktree の削除に失敗したとき

**説明**: タスク worktree の git worktree remove が失敗したときは、そのタスクのブランチ削除を試さない。worktree を残したこと、git が返した理由、ブランチ削除を見送ったことと見送った理由を結果の JSON に入れて返す。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| worktree の削除失敗 | git worktree remove が失敗した（未コミットの変更がある等） | ブランチ削除を試さず、worktree を残したこと・git の理由・ブランチ削除を見送ったことと見送った理由を JSON に入れる。終了コードは 0 |

#### FR7: 対象が既に無いとき

**説明**: タスク worktree やタスクブランチが既に無いときは、片付け済みとして扱い、対象ごとに「既に無い」を「今回消した」と区別して返す。worktree が無いかどうかは git の worktree 登録一覧（git worktree list --porcelain）で、ブランチが無いかどうかは git の ref 解決（refs/heads/em-workflow/{feature}/{T}）で判定し、パスの有無だけでは判定しない。

**ビジネスルール**:
- worktree のディレクトリが無いのに git の登録が残っている場合は「既に無い」とせず、git worktree remove を試し、失敗したら FR6 と同じく worktree を残した扱いで理由を返す
- git worktree prune は実行しない

#### FR8: 結果の返し方と終了コード

**説明**: 結果は標準出力に JSON 1 つで返し、終了コードは 0 にする。worktree やブランチを残したときも 0 にする。0 以外で終了するのは、入力が不正なときと内部エラーのときだけにする。手順 4 は、終了コードだけでなく JSON を読み、残したブランチ名と理由を wake フェーズの報告に書くと定める。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 入力不正 | FR5 の検証に合わない | 0 以外で終了する |
| 内部エラー | スクリプト内部のエラー | 0 以外で終了する |

## 5. 非機能要件

### 5.1 パフォーマンス要件
- 該当なし

### 5.2 セキュリティ要件
- 入力検証: FR5 のとおり

### 5.3 可用性要件
- 該当なし

### 5.4 保守性要件
- NFR1: スクリプトの結果は、呼び出し元の作業ディレクトリ（メインのツリーを含む）に左右されない
- NFR2: 手順書に書く呼び出し行は、destructive-guard.py と interpreter-mismatch-guard.py のどちらでも ask / deny にならない
- NFR3: テストは標準ライブラリの unittest だけで書き、一時ディレクトリに作った使い捨ての git リポジトリを使う

### 5.5 互換性要件
- NFR4: plugin.json と marketplace.json の version は変えない（main への push 時に Actions が patch を上げる）

## 6. UI/UX要件

該当なし（UI の変更は無い）。

## 7. データ要件

該当なし。

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| git | git worktree remove / git worktree list --porcelain / git branch -d / ref 解決 | タスク worktree、タスクブランチ em-workflow/{feature}/{T} |

### 8.2 API仕様要件
該当なし。

## 9. 制約条件

### 9.1 技術的制約
- -D、--force、-f は使わない
- git worktree prune は実行しない
- テストは標準ライブラリの unittest だけで書き、一時ディレクトリに作った使い捨ての git リポジトリを使う

### 9.2 ビジネス上の制約
- plugin.json と marketplace.json の version は変えない
- implement-phase.md の手順 4 の見出し「4. **Clean up** every newly-merged task's worktree and branch:」、失敗時の決まりの文言、手順 5 の後の batch mode 段落の書き出しは変えない

### 9.3 スケジュール制約
- 該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/wake-task-cleanup-script/**`
- `test-docs/wake-task-cleanup-script/**`

`feature-docs/wake-task-cleanup-script/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/wake-task-cleanup-script/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/wake-task-cleanup-script/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| タスク worktree が別のブランチに切り替わっていた場合、消せるはずのタスクブランチも残る | 低 | 許容し、残したことを報告に書く |
| 呼び出し側が終了コードだけを見ると、残したものを見落とす | 中 | 手順 4 に、JSON を読んで残したブランチ名と理由を wake の報告に書くことを明記する |

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: wake 手順 4 の後片付けを行うスクリプトが em-workflow/scripts/ にあり、入力は後片付けに必要な値だけである
- [ ] AC2: スクリプトは git worktree remove と、integration worktree を基準にした git branch -d を実行し、-D、--force、-f を使わない（スクリプトの中身をテストで確かめる）
- [ ] AC3: ブランチを消せなかったとき、残したブランチ名と理由を機械で読める形で返す。手順 4 は、その値を wake の報告に書くと定めている
- [ ] AC4: implement-phase.md の手順 4 に、git コマンドを直接書いた行が無く、スクリプトを呼ぶ形になっている
- [ ] AC5: メインのツリー（タスクブランチを取り込んでいないブランチ）を作業ディレクトリにして呼んでも、integration に取り込み済みのタスクブランチと、その worktree が消えることをテストで確かめる
- [ ] AC6: integration に取り込まれていないタスクブランチは消えずに残り、残した名前と理由が返ることをテストで確かめる
- [ ] AC7: 不正な feature やタスク ID を渡すと、git を実行せずに 0 以外で終了することをテストで確かめる
- [ ] AC8: タスク worktree の削除が失敗したとき（未コミットの変更がある等）、ブランチ削除を試さず、worktree とブランチの両方が残り、それぞれの理由が返ることをテストで確かめる
- [ ] AC9: worktree とブランチの片方または両方が既に無いとき、その対象が「既に無い」として返り、残りの対象は通常どおり片付くことをテストで確かめる。worktree の不在は git の登録一覧で判定している（ディレクトリだけ消えて登録が残っている場合を「既に無い」と返さない）
- [ ] AC10: worktree やブランチを残したときも終了コードは 0 で、結果は標準出力の JSON に入ることをテストで確かめる。手順 4 は JSON を読んで報告に書くと定めている

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系: TS-1（AC5）integration ブランチに取り込み済みのタスクブランチと worktree を作り、取り込んでいないメインのツリーを作業ディレクトリにしてスクリプトを呼ぶ。worktree の登録とブランチが消え、終了コード 0、JSON は両方を「今回消した」と返す
- [ ] 異常系: TS-2（AC6）integration に取り込んでいないタスクブランチで呼ぶ。worktree は消え、ブランチは残り、JSON に残したブランチ名と git の理由が入る。終了コードは 0
- [ ] 異常系: TS-3（AC8）タスク worktree に未コミットの変更を置いて呼ぶ。worktree とブランチの両方が残り、ブランチ削除を試していないことと、それぞれの理由が JSON に入る。終了コードは 0
- [ ] 境界値: TS-4（AC9）ブランチだけが既に無い状態、worktree だけが既に無い状態、両方無い状態でそれぞれ呼ぶ。無い対象は「既に無い」、残りの対象は通常どおりの結果になる
- [ ] 境界値: TS-5（AC9）worktree のディレクトリだけを消し、git の登録を残した状態で呼ぶ。「既に無い」とは返さない
- [ ] セキュリティ: TS-6（AC7）feature やタスク ID に不正な値（パス区切り、'integration'、空文字、先頭がハイフン等）を渡す。git を 1 つも実行せずに 0 以外で終了し、integration ブランチと integration worktree は変わらない
- [ ] 静的検査: TS-7（AC2）スクリプトの本文に -D、--force、-f の削除フラグが無いことを確かめる
- [ ] 静的検査: TS-8（AC4、AC3、AC10）implement-phase.md の手順 4 に git worktree remove / git branch の行が無く、スクリプトの呼び出し行があり、JSON を読んで残したブランチ名と理由を wake の報告に書くと定め、強制削除に頼らない文言・手順 3 の status が変わらない文言・手順 5 が進む文言が残っていることを確かめる
- [ ] 静的検査: TS-9（NFR2）手順 4 の新しい呼び出し行を destructive-guard.py と interpreter-mismatch-guard.py に通し、ask / deny にならないことを確かめる
- [ ] パフォーマンス: 該当なし

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| wake 手順 4 | implement-phase.md の手順 4。新しくマージされたタスクの worktree とブランチを片付ける |
| タスクブランチ | em-workflow/{feature}/{T} |
| 既に無い | 実行前から対象が無かったこと。worktree は git worktree list --porcelain の登録一覧、ブランチは refs/heads/em-workflow/{feature}/{T} の ref 解決で判定する |
| 今回消した | 今回の実行で対象を消したこと |

## 14. 確認事項

### 14.1 確認済み事項
なし。

### 14.2 未確認・保留事項
なし。

### 14.3 前提
- [x] A-worktree-remove-failure: タスク worktree の削除に失敗したときは、ブランチ削除を試さず、両方の理由を返す
- [x] A-worktree-remove-failure-risk: タスク worktree が別のブランチに切り替わっていた場合、消せるはずのタスクブランチも残る。これは許容し、残したことを報告に書く
- [x] A-already-absent: worktree やブランチが既に無いときは片付け済みとして扱い、対象ごとに「既に無い」と区別して返す。不在は、worktree は git の登録一覧、ブランチは git の ref 解決で判定し、パスの有無だけでは判定しない
- [x] A-registered-but-missing-dir: worktree のディレクトリが無いのに git の登録が残っている場合は「既に無い」とせず、git worktree remove を試し、失敗したら FR6 と同じく worktree を残した扱いで理由を返す。git worktree prune は実行しない
- [x] A-exit-status: 結果は標準出力の JSON で返し、残したものがあっても終了コードは 0。入力不正と内部エラーだけ 0 以外
- [x] A-exit-status-risk: 呼び出し側が終了コードだけを見ると残したものを見落とすため、手順 4 には JSON を読んで残したブランチ名と理由を wake の報告に書くことを明記する
- [x] A-version: plugin.json と marketplace.json の version は変えない
- [x] A-step4-wording-pinned: 手順 4 の見出し「4. **Clean up** every newly-merged task's worktree and branch:」、失敗時の決まりの文言、手順 5 の後の batch mode 段落の書き出しは変えない

## 15. 参考資料

- implement-phase.md: implement フェーズの手順書（手順 4 を書き換える）
