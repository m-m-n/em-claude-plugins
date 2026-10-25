---
title: "codex-stop-hook-tty-reaper"
created_date: 2026-10-25
status: draft
---

# codex-stop-hook-tty-reaper - 要件定義書

## 1. 概要

### 1.1 背景
run_codex_exec.sh で起動した Codex の終了後に、端末の入力待ちのまま残った対話起動のプロセス（python3 -i、bash -i など）が孤児化し、CPU を使い続ける。

### 1.2 目的
- run_codex_exec.sh で起動した Codex の終了後に、端末の入力待ちのまま残った対話起動のプロセス（python3 -i、bash -i など）が孤児化して CPU を使い続けないようにする。
- コマンド文字列の静的解析に頼らず、ターン終了時に実際に残っているプロセスを見て止める。

### 1.3 スコープ
- em-workflow と em-review の run_codex_exec.sh への Stop フックの登録（すべての起動経路）
- 各プラグインの scripts/ に置く Stop フックのスクリプト（2 つのコピーはバイト単位で同一）
- フックを起動した Codex の子孫のうち、標準入力が /dev/pts/* のプロセスの停止
- tests/ に置く unittest
- 本物の Codex を使う手動の実機確認と、その記録

対象外:
- codex-hook-interactive-guard.py の PreToolUse 登録の変更（そのまま残す）
- 意図して残したバックグラウンドのプロセスを判定から除外する処理
- em-workflow と em-review の version の変更

## 2. ビジネス要件

### 2.1 ビジネス目標
- run_codex_exec.sh で起動した Codex の終了後に、端末の入力待ちのまま残った対話起動のプロセスが孤児化して CPU を使い続けないようにする。
- コマンド文字列の静的解析に頼らず、ターン終了時に実際に残っているプロセスを見て止める。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow / em-review の利用者 | run_codex_exec.sh 経由で Codex を起動する |

### 2.3 期待される効果
- Codex の終了後に、端末の入力待ちのプロセスが残らない。
- 読み取り専用のコマンドだけの実行では、フックが何も止めない。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター |
|----|----------------|----------|
| UC01 | Codex のターン終了時に端末の入力待ちのプロセスを止める | run_codex_exec.sh / Codex |

### 3.2 ユースケース詳細

#### UC01: Codex のターン終了時に端末の入力待ちのプロセスを止める

**アクター**: run_codex_exec.sh / Codex

**事前条件**:
- run_codex_exec.sh が、起動時の引数 `-c hooks.Stop=...` で Stop フックを登録して Codex を起動している。

**基本フロー**:
1. Codex のターンが終わり、Stop フックが起動する。
2. フックは、フックを起動した Codex の子孫のうち、標準入力が /dev/pts/* のプロセスを対象として列挙する（子を持つプロセスも含む。フック自身とその祖先は含まない）。
3. フックは対象を子から順に（深いものから）止める。各対象に SIGTERM を送り、0.5 秒後も生きていれば、同じプロセスであることを確かめてから SIGKILL を送る。
4. フックは block / continue の判定を返さずに終了する。

**代替フロー**:
- 途中で終わったプロセス（ESRCH）はエラーにしない。
- フックの中で失敗したら、何も止めずに終了する。
- /proc が使えない環境では何もしない。

**事後条件**:
- Codex の子孫で、標準入力が端末のまま残っているプロセスが無い。
- Codex の停止と Codex の終了コードは変わらない。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | Stop フックの登録 | resolved |
| FR2 | フックスクリプトの配置 | assumed（A2） |
| FR3 | 停止対象の判定 | resolved |
| FR4 | 停止の手順 | assumed（A4） |
| FR5 | Codex の停止を妨げない | assumed（A6） |
| FR6 | 既存の PreToolUse フックの維持 | assumed（A1） |
| FR7 | バックグラウンドのプロセスの扱い | resolved |
| FR8 | 実機での確認と記録 | assumed（A5） |

### 4.2 機能詳細

#### FR1: Stop フックの登録

**説明**: em-workflow と em-review の run_codex_exec.sh は、すべての起動経路（readonly / readwrite、em-workflow の既定経路と --litellm 経路）で、起動時の引数 `-c hooks.Stop=...` により Stop フックを登録する。

#### FR2: フックスクリプトの配置

**説明**: Stop フックのスクリプトは各プラグインの scripts/ に置き、ラッパー自身の位置（SCRIPT_DIR）から導いた絶対パスで登録する。2 つのコピーはバイト単位で同一に保つ。

**前提**: A2

#### FR3: 停止対象の判定

**説明**: フックを起動した Codex の子孫のうち、標準入力が /dev/pts/* のプロセスをすべて対象にする。子を持つプロセスも対象に含め、末端には絞らない。フック自身とその祖先は対象にしない。フックを起動した Codex の特定方法（フックの祖先をたどる、またはラッパーの PID を渡す）は SPEC で決める。

**ビジネスルール**:
- 対象の条件は、フックを起動した Codex の子孫であることと、標準入力が /dev/pts/* であること。
- フック自身とその祖先は対象外。

#### FR4: 停止の手順

**説明**: 対象を子から順に（深いものから）止める。各対象に SIGTERM を送り、0.5 秒後も生きていれば SIGKILL を送る。SIGKILL の前に、同じプロセスであること（PID の再利用でないこと）を確かめる。途中で終わったプロセス（ESRCH）はエラーにしない。

**前提**: A4

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| ESRCH | 列挙後にプロセスが終わった | エラーにしない |
| PID の再利用 | SIGKILL の前に同じプロセスでないと分かった | SIGKILL を送らない |

#### FR5: Codex の停止を妨げない

**説明**: フックは block / continue の判定を返さず、Codex の停止も Codex の終了コードも変えない。フックの中で失敗したら、何も止めずに終了する。

**前提**: A6

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| フック内の失敗 | 不正な標準入力などでフックの処理が失敗した | 何も止めずに終了する |

#### FR6: 既存の PreToolUse フックの維持

**説明**: codex-hook-interactive-guard.py の PreToolUse 登録はそのまま残す。

**前提**: A1

#### FR7: バックグラウンドのプロセスの扱い

**説明**: 意図して残したバックグラウンドのプロセスを判定から除外する処理は入れない。FR3 の判定（子孫関係と標準入力）を変えず、巻き込むかどうかを確かめて記録するだけにする。確認と記録は readonly と readwrite の両方の経路で行う。

#### FR8: 実機での確認と記録

**説明**: 本物の Codex で次を確認し、結果を記録する。
- tty:true で残した python3 -i と bash -i が終了後に残らないこと。
- 読み取り専用のコマンドだけの実行ではフックが何も止めないこと。
- readwrite と --litellm 経由の起動でも同じ判定で対象が見つかること。
- 意図して残したバックグラウンドのプロセスを巻き込むかどうか（readonly と readwrite の両方）。

**前提**: A5

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR2 所要時間の上限: 1 回のフック実行は、SIGTERM 後の 0.5 秒の待ちを含め、短い一定の時間で終わる。

### 5.2 セキュリティ要件
- NFR1 シグナルの到達範囲: フックを起動した Codex の子孫以外のプロセスにはシグナルを送らない。並列に動く別の Codex、その子孫、呼び出し元の Claude Code やそれ以前の祖先も対象外。
- NFR6 信頼しない入力への耐性: フックは Codex のサンドボックスの外で --dangerously-bypass-hook-trust の下で動く。レビュー対象のリポジトリの内容やフックの標準入力の内容によって、止める対象が Codex の子孫以外に広がらない。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR4 テストの依存と隔離: テストは tests/ に置く標準ライブラリだけの unittest で書き、本物の Codex に到達せず、自分で起こしたプロセス以外にシグナルを送らない。

### 5.5 互換性要件
- NFR3 ラッパーの既存契約の維持: 使い方の表示、受け付けるフラグ、codex exec を 1 回だけ起動すること、--dangerously-bypass-hook-trust が 1 回であること、2>&1 の扱い、プロンプトが最後の引数であることを変えない（A3）。
- NFR5 実行環境: フックは python3 の標準ライブラリだけで動く。/proc が使えない環境では何もしない（A7）。

## 6. UI/UX要件

該当なし（UI の無い、シェルのラッパーとプロセス制御のフックの変更。デザインステップは skipped）

## 7. データ要件

該当なし

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| Codex（codex exec） | 起動時の引数 `-c hooks.Stop=...` による Stop フックの登録 | フックの標準入力 |

### 8.2 API仕様要件
該当なし

## 9. 制約条件

### 9.1 技術的制約
- フックは python3 の標準ライブラリだけで動く（NFR5）。
- 子孫と標準入力の判定に /proc を使う。/proc が使えない環境では何もしない（A7）。
- テストは標準ライブラリだけの unittest で書く（NFR4）。

### 9.2 ビジネス上の制約
- em-workflow と em-review の version は変更しない（A8）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-stop-hook-tty-reaper/**`
- `test-docs/codex-stop-hook-tty-reaper/**`

`feature-docs/codex-stop-hook-tty-reaper/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-stop-hook-tty-reaper/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-stop-hook-tty-reaper/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-stop-hook-tty-reaper/` ディレクトリを生成しないが、宣言された `test-docs/codex-stop-hook-tty-reaper/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 意図して残したバックグラウンドのプロセスを巻き込むかどうか | - | 判定は変えず、readonly と readwrite の両方で確かめて記録する（FR7、FR8） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: run_codex_exec.sh（em-workflow / em-review）が、すべての起動経路で Stop フックを登録する
- [ ] AC-2: Stop フックが、Codex の子孫で標準入力が端末のまま残っているプロセスを、子を持つものも含めて止める
- [ ] AC-3: python3 -i と bash -i を tty:true で残した Codex の実行で、終了後にそのプロセスが残らない
- [ ] AC-4: 読み取り専用のコマンドだけを実行した Codex の実行で、フックが何も止めない
- [ ] AC-5: readwrite と --litellm 経由の起動でも、同じ判定で対象が見つかることを確かめる
- [ ] AC-6: 意図して残したバックグラウンドのプロセスを巻き込むかどうかを readonly と readwrite の両方の経路で確かめ、結果を記録する

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1（unit、AC-1 / FR1 / FR2 / FR6 / NFR3）: tests/test_codex_hook_wrapper_args.py を拡張し、stub の codex で em-workflow（readonly / readwrite / --litellm）と em-review（readonly / readwrite）の各経路を起動して、`-c hooks.Stop=...` が 1 つあり、各プラグインの scripts/ にある Stop フックの絶対パスを指すこと、PreToolUse の登録とラッパーの既存契約が変わらないことを確かめる。
- [ ] TS-2（unit、FR2）: em-workflow と em-review の Stop フックのスクリプトがバイト単位で同一であることを確かめる。
- [ ] TS-3（unit、AC-2 / FR3）: テスト自身が擬似 Codex のプロセス木を起こし、標準入力を pty にした子孫と、標準入力がパイプの子孫を置く。フックを擬似 Codex の子孫として起動し、pty の子孫だけが止まり、パイプの子孫は残ることを確かめる。
- [ ] TS-4（unit、FR3 / FR4）: 子を持つ端末のプロセス（pty の親とその子）が両方止まり、子から順に止まることを確かめる。
- [ ] TS-5（unit、FR4 / NFR2）: SIGTERM を無視するプロセスが 0.5 秒後の SIGKILL で止まり、フックの実行が上限時間内に終わることを確かめる。
- [ ] TS-6（unit、NFR1）: 擬似 Codex の外にある、標準入力が pty のプロセス（並列の別の擬似 Codex の子孫を含む）と、標準入力が pty のフックの祖先は止まらないことを確かめる。
- [ ] TS-7（unit、FR4 / FR5）: 列挙後に終わったプロセス（ESRCH）でエラーにならないこと、フックが判定の JSON を出さず終了コード 0 で終わること、不正な標準入力でも何も止めずに終わることを確かめる。
- [ ] TS-8（unit、NFR5）: /proc が使えない状況を模して、フックが何もせず終わることを確かめる。
- [ ] MV-1（manual、AC-3 / FR8）: 本物の Codex で python3 -i と bash -i を tty:true で残し、終了後にそのプロセスが残らないことを確かめて記録する。
- [ ] MV-2（manual、AC-4 / FR8）: 読み取り専用のコマンドだけを実行させ、フックが何も止めないことを確かめて記録する。
- [ ] MV-3（manual、AC-5 / FR8）: readwrite と --litellm 経由で起動し、同じ判定で対象が見つかることを確かめて記録する。
- [ ] MV-4（manual、AC-6 / FR7 / FR8）: readonly と readwrite の両方で、意図して残したバックグラウンドのプロセスを巻き込むかどうかを確かめて記録する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| Stop フック | Codex のターン終了時に起動するフック。run_codex_exec.sh が起動時の引数 `-c hooks.Stop=...` で登録する |
| 停止対象 | フックを起動した Codex の子孫のうち、標準入力が /dev/pts/* のプロセス（フック自身とその祖先を除く） |
| 起動経路 | readonly / readwrite、em-workflow の既定経路と --litellm 経路 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] version の扱い（requirement.version-bump）: patch_by_actions。em-workflow と em-review の version は変更しない（A8）
- [x] デザインステップ: skipped（UI の無い、シェルのラッパーとプロセス制御のフックの変更）

前提:

| ID | 内容 | 影響度 | 可逆 |
|----|------|--------|------|
| A1 | codex-hook-interactive-guard.py の PreToolUse 登録は変更せず残す。 | low | 可 |
| A2 | Stop フックのスクリプトは各プラグインの scripts/ に置き、ラッパーの位置から導いた絶対パスで登録する。2 つのコピーはバイト単位で同一に保つ。 | low | 可 |
| A3 | ラッパーの既存契約（使い方、フラグ、codex exec の 1 回起動、--dangerously-bypass-hook-trust が 1 回、2>&1、プロンプトが最後の引数）を変えない。 | medium | 可 |
| A4 | 停止は SIGTERM のあと 0.5 秒待ち、生きていれば SIGKILL を送る。 | low | 可 |
| A5 | 本物の Codex を使う確認はテストスイートに入れず、手動の実機確認として記録する。 | low | 可 |
| A6 | フックは block / continue の判定を返さず、失敗しても何も止めずに終わる。 | medium | 可 |
| A7 | /proc が使えない環境ではフックは何もしない。 | low | 可 |
| A8 | em-workflow と em-review の version は変更しない。 | low | 可 |

### 14.2 未確認・保留事項
- [ ] フックを起動した Codex の特定方法（フックの祖先をたどる、またはラッパーの PID を渡す）（FR3）

## 15. 参考資料

- tests/test_codex_hook_wrapper_args.py: ラッパーの既存契約を固定しているテスト
