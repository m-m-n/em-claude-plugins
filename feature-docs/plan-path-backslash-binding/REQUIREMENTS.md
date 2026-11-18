---
title: "plan-path-backslash-binding"
created_date: 2026-11-19
status: draft
---

# plan-path-backslash-binding - 要件定義書

## 1. 概要

### 1.1 背景
implement-phase.md の Step I.2.a のペイロードは、task_plan_path を「joined with the stored tasks.{T}.plan value」として組んでいる。create-plan-phase.md 2a 節も「joined with that value」と述べている。一方、検証器（scripts/validate-worker-output.py）は保存値を path_segments で正規化してから計画書を読む。保存値が `tasks/\task0003.md` や `tasks\task0003.md` のようなバックスラッシュ綴りのとき、検証器が読む計画書と、実装担当に渡すパスが指す計画書が別のファイルになりうる。

### 1.2 目的
- 実装担当に渡す計画書を、検証器が検証した計画書と同じファイルにする。tasks.{T}.plan の綴りを変えても、検証済みでない計画書を実装担当に渡せないようにする。
- 悪意が無い場合でも、バックスラッシュ綴りの plan 値から存在しないパスが実装担当に渡らないようにする。

### 1.3 スコープ
- implement-phase.md の Step I.2.a（task_plan_path の行）と Plan-path check の規則 2・3
- create-plan-phase.md 2a 節の、保存値を絶対パスに解決する文
- tests/test_final_path_correction_docs.py の該当する文言の固定
- scripts/validate-worker-output.py の挙動は変えない（FR4）

## 2. ビジネス要件

### 2.1 ビジネス目標
- 実装担当に渡す計画書を、検証器が検証した計画書と同じファイルにする。tasks.{T}.plan の綴りを変えても、検証済みでない計画書を実装担当に渡せないようにする。
- 悪意が無い場合でも、バックスラッシュ綴りの plan 値から存在しないパスが実装担当に渡らないようにする。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | implement フェーズで実装担当に計画書を渡す流れを使う |

### 2.3 期待される効果
- task_plan_path と検証器の読む計画書が、plan 値の綴りによらず同じファイルを指す
- バックスラッシュ綴りの plan 値から、存在しないパスや囮のファイルを指すパスが実装担当に渡らない

## 3. ユースケース

該当なし（変更対象はフェーズ文書とテストで、利用者の操作手順は変わらない）。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | task_plan_path を正規化後のセグメントから組む | Step I.2.a の task_plan_path を、path_segments で正規化したセグメントの結合で示す |
| FR2 | Plan-path check の規則 2・3 を同じ解決結果に適用する | 規則 2・3 の判定対象を FR1 と同じパスにする |
| FR3 | create-plan-phase.md 2a 節の記述を合わせる | 2a 節の解決文を FR1 と同じ内容に揃える |
| FR4 | 検証器側の解決は変えない | validate-worker-output.py の解決処理と綴りの結び付きを残す |
| FR5 | 文書テストを新しい記述に合わせる | test_final_path_correction_docs.py の固定文言を更新し、修正前の記述を検出する |

### 4.2 機能詳細

#### FR1: task_plan_path を正規化後のセグメントから組む

**説明**: implement-phase.md の Step I.2.a のペイロードの task_plan_path は、統合 worktree の feature-docs/{feature}/ に、保存値 tasks.{T}.plan を scripts/validate-worker-output.py の path_segments で正規化したセグメントを結合した絶対パスとする。保存値の文字列をそのまま結合しない。path_segments はその処理を引用する形で示し、本文で中身を書き直さない。

**ビジネスルール**:
- task_plan_path の行の位置は変えない。worktree_path の直後、implementation_md_path の直前、`## Untrusted data` の行より前とする。

#### FR2: Plan-path check の規則 2・3 を同じ解決結果に適用する

**説明**: Plan-path check の規則 2（symlink の検査）と規則 3（realpath による内側判定）は、FR1 で task_plan_path として渡すパスと同じパス、つまり正規化後のセグメントを feature-docs/{feature} に結合したパスに対して判定する。

**ビジネスルール**:
- 規則 1（is_safe_relative_path と、セグメントが 1 つ以上あること）と規則 4（制御文字）の内容は変えない。
- 規則は 4 つのままで、各規則は 1 文の箇条 1 つとする。
- 段落は NFR1 の言い回しの制約を満たす。

#### FR3: create-plan-phase.md 2a 節の記述を合わせる

**説明**: create-plan-phase.md の 2a 節で、implement フェーズが保存値をどう絶対パスに解決するかを述べた文を、FR1 と同じく「path_segments で正規化したセグメントを結合する」内容に揃える。

**ビジネスルール**:
- Plan-path check は引用のままとし、書き直さない。
- 保存値を述べる文と、解決後の絶対パスを述べる文は別の文のままにする。

#### FR4: 検証器側の解決は変えない

**説明**: scripts/validate-worker-output.py の _resolve_contained_relative_path、_plan_is_bound_to_task_md、path_segments、is_safe_relative_path の挙動は変えない。

**ビジネスルール**:
- `./tasks/{T}.md`、`tasks//{T}.md`、`tasks/./{T}.md`、`tasks\{T}.md` が `tasks/{T}.md` に結び付く挙動は残す。

#### FR5: 文書テストを新しい記述に合わせる

**説明**: tests/test_final_path_correction_docs.py のうち、task_plan_path の行、Plan-path check の規則 2・3、2a 節の解決文を固定している文言を、FR1 から FR3 の記述に合わせて更新する。

**ビジネスルール**:
- 修正前の「保存値をそのまま結合する」記述は、否定側の見本として検出される状態にする。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- 入力検証: 実装担当に渡す計画書のパスは、検証器が検証した計画書と同じファイルを指す（FR1、FR2、AC-4）。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- ドキュメント（NFR1）: Plan-path check の段落は、tests/test_final_path_correction_docs.py が固定している言い回しの制約を満たす。条件は次のとおり。
    - PP_FORBIDDEN_PHRASES の語句を含まない。
    - 1 文に含む条件語（PP_CONDITION_MARKERS: strictly below / existing directory / realpath / `..` / empty component / link component / symbolic link）は 2 つまで。
    - 大文字の EVERY・ALL を使わない。
    - Control-character check の段落の直後で、承認ゲートの段落の直前に置く。
- テスト（NFR2）: テストは Python 標準ライブラリの unittest だけで書き、`python3 -m unittest discover -s tests` が全件通る。

### 5.5 互換性要件
- NFR3: em-workflow の version は変更しない。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- path_segments は引用で示し、正規化の手順を本文で書き直さない。
- テストは Python 標準ライブラリの unittest だけで書く。

### 9.2 ビジネス上の制約
- em-workflow の version は変更しない。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 保存値が正規形と一致しないときに拒否する規則を足すと、検証器が受け入れる `./tasks/{T}.md` などの綴りで implement フェーズが止まり、両者の判断が食い違う | 中 | 拒否規則は足さず、正規化後のセグメントから絶対パスを組む対応だけとする（前提 A1） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: implement-phase.md Step I.2.a のペイロードの task_plan_path の行は、path_segments で正規化したセグメントを feature-docs/{feature}/ に結合した絶対パスを示す。保存値の文字列をそのまま結合する形を示さない。行の位置は変えず、worktree_path の直後、implementation_md_path の直前、`## Untrusted data` の行より前とする。
- [ ] AC-2: Plan-path check の規則 2・3 は、task_plan_path と同じ正規化後の結合パスを判定対象とする。規則は 4 つ、各 1 文で、NFR1 の言い回しの制約を満たす。
- [ ] AC-3: create-plan-phase.md 2a 節の解決文は、正規化後のセグメントを結合することを述べ、Plan-path check を引用する。保存値の文と解決後の絶対パスの文は別の文である。
- [ ] AC-4: 攻撃シナリオが成立しない。`tasks/task0003.md` に canonical_correction_plan の出力を置き、`tasks/` 配下の文字どおりの名前 `\task0003.md` に別の本文を置き、plan を `tasks/\task0003.md`（または `tasks\task0003.md`）にする。このとき、文書が定める task_plan_path の導出結果は、検証器の _resolve_contained_relative_path が読む `tasks/task0003.md` と同じファイルを指し、`\task0003.md` を指さない。
- [ ] AC-5: 検証器の既存挙動が変わらない。tests/test_final_path_correction.py の TestPlanBindingAdmits.test_every_spelling_of_tasks_t_md_is_bound を含む既存テストがそのまま通る。
- [ ] AC-6: 修正前の記述（implement-phase.md:546 の「joined with the stored tasks.{T}.plan value」、create-plan-phase.md 2a 節の「joined with that value」）を見本として与えると、更新後の文書テストが問題として検出する。
- [ ] AC-7: `python3 -m unittest discover -s tests` が全件通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系（TS-1）: 現行の task_plan_path の行が、正規化後のセグメント結合を示す文言を含み、行の位置の条件を満たす。修正前の行（保存値の文字列をそのまま結合）の見本は問題として検出される。
- [ ] 正常系（TS-2）: Plan-path check の規則 2・3 の箇条が正規化後の結合パスを判定対象とする文言を含む。4 箇条・各 1 文・言い回しの制約（禁止語句、条件語 2 つまで、大文字の量化詞なし）を満たす。規則を 1 つ削った見本や文言を抜いた見本は検出される。
- [ ] 正常系（TS-3）: create-plan-phase.md 2a 節の解決文が新しい文言と Plan-path check の引用を含み、保存値の文と別の文である。修正前の 2a 節の見本は検出される。
- [ ] セキュリティ（TS-4）: 一時ディレクトリの `feature-docs/{feature}/tasks/` に正規形の `task0003.md` と、文字どおりの名前 `\task0003.md` の囮を置く。plan が `tasks/\task0003.md` の場合と `tasks\task0003.md` の場合のどちらでも、文書が定める導出（path_segments で正規化したセグメントの結合）が、検証器の _resolve_contained_relative_path の返すパスと一致し、囮を指さない。
- [ ] 回帰（TS-5）: 既存の tests/test_final_path_correction.py（綴りの結び付き AC-5 を含む）と tests/test_final_path_correction_docs.py の残りのテストが通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 保存値 | workflow.yaml の tasks.{T}.plan に保存された文字列 |
| task_plan_path | implement-phase.md の Step I.2.a で実装担当に渡すペイロードの、計画書の絶対パス |
| path_segments | scripts/validate-worker-output.py の、パスをセグメントに正規化する処理 |
| Plan-path check | implement-phase.md の、plan のパスを検査する 4 つの規則 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: 対応は根本対応（正規化後のセグメントから絶対パスを組み、検証と起動で同じ解決結果を使う）だけとする。保存値が正規形と一致しないときに拒否する規則（暫定緩和策）は Plan-path check に足さない。
- [x] A2: 検証器が `tasks/{T}.md` の別綴り（`./`、`//`、`/./`、バックスラッシュ）を結び付きありと判定する挙動は残す。
- [x] A3: implement-phase.md は path_segments を引用で示し、正規化の手順を本文で書き直さない。
- [x] A4: version の minor / major は上げない。patch は main への push 時に Actions が上げる。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- implement-phase.md: Step I.2.a、Plan-path check
- create-plan-phase.md: 2a 節
- scripts/validate-worker-output.py: path_segments、is_safe_relative_path、_resolve_contained_relative_path、_plan_is_bound_to_task_md
- tests/test_final_path_correction.py、tests/test_final_path_correction_docs.py
