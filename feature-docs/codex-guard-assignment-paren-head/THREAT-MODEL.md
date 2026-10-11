# Threat Model: codex-guard-assignment-paren-head

## Verdict
threats-identified

## Rationale
調べたもの: SPEC.md の FR1〜FR6 / NFR1〜NFR2、tier（reduced。REQUIREMENTS.md と design は省略）、修正対象の hook の 2 つのコピーとそのテスト表。

この機能の入力は、Codex の Bash 呼び出しのコマンド文字列だけ。hook はそれを PreToolUse の標準入力 JSON として受け取り、静的に読んで deny を 1 つ出すか、何も出さないかを決める。コマンド文字列は Codex（LLM）が生成し、レビュー対象のリポジトリの内容に影響されうるため、信頼できない入力として扱う。境界は TB-1 の 1 つ。

task0001 は `input-handling` を宣言しているため、TB-1 の深さは deep。6 つの STRIDE カテゴリーをすべて検討し、当てはまるのは Denial of service だけだった。hook は判定結果を出すだけで、利用者の識別・記録・秘密情報・権限を扱わず、入力で自身の状態を書き換えられることもないため、他の 5 つは当てはまらない。

hook の既存の性質（判定できない入力は何も出力しない、標準ライブラリだけを使う、ファイル・ネットワーク・子プロセスに触れない、深い入れ子でも線形時間で答える）はこの変更で変えないため、新しい脅威として記録しない（NFR1。既存のテストで固定されている）。

## Trust Boundaries

### TB-1: Codex の Bash コマンド文字列 → codex-hook-interactive-guard の判定
Crossing: Codex（LLM）が生成した Bash コマンド文字列が、PreToolUse の標準入力 JSON として hook の構文の読み取りに渡る。文字列はレビュー対象のリポジトリの内容に影響されうる。
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | `(` の直前の単純コマンドが代入語（`a=` / `a+=` / `export a=`）でも関数名とみなされ、その `()` の後に改行・空行・コメント行を挟んで続く `( ... )` / `{ ...; }` が関数本体として判定から外れる。その中の対話起動（`python3 -i` など）が deny されず、端末が閉じた後も入力待ちの孤児プロセスとして残る（FR1, FR2）。 | TM-1 | 関数名ありとみなす条件を FR1 の 2 つの形（`=` を含まない動的でない語 1 つ、または `function` とその語）に限り、それ以外の `()` の後に続くグループは判定する。関数定義の本体を判定しない範囲（FR3）と `;` 区切りの判定（FR4）は保ち、両コピーに同じ修正を入れてバイト単位で同一に保つ（FR5）。 | task0001 AC-1 | VERIFICATION.md Performance / Security Verification の TM-1 |
