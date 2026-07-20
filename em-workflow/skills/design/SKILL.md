---
name: design
description: "デザイン詰めの手動対話コマンド（em-workflow）。実機確認後のフィードバックや実機スクリーンショットをもとに、design-system/tokens.yaml・feature-docs/{feature}/DESIGN.md・HTML モックを合意ループで更新します。コードには触れません — 実装への反映は /em-workflow:develop に委ねます。引数で feature を指定、引数なしは対象を確認します（デフォルト: システム全体）"
argument-hint: "[feature-name]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
---

# em-workflow Design (interactive refinement)

原則: **develop の design ステップは自律で「まず動くもの」を作る。ここは
実機を見たあとにデザインを詰める場所**。デザイン成果物（トークン・モック・
DESIGN.md）だけを更新し、コードには一切触れない — 実装への反映は
/em-workflow:develop の仕事。

成果物の場所と規律は `${CLAUDE_PLUGIN_ROOT}/agents/designer.md` の
**Design Artifact Rules** に従う（最初に Read する。tokens.yaml の書式は
`${CLAUDE_PLUGIN_ROOT}/references/templates/design-tokens.yaml`）。

## Step 1: スコープ決定

- 引数で feature 名が指定されていればその feature
  （`feature-docs/{feature}/` の存在を確認。無ければ既存 feature 一覧を
  提示して終了）
- 引数なし: Glob `feature-docs/*/DESIGN.md` で feature を列挙し、
  AskUserQuestion で対象を確認する。**先頭の選択肢（デフォルト）は
  「システム全体」**（design-system/tokens.yaml と横断的な見た目の方針）、
  以降に各 feature を並べる

## Step 2: コンテキスト読み込み

tokens.yaml（無ければ project-native システムの該当設定）、対象 feature の
DESIGN.md / mockups を読む。システム全体スコープでは全 feature の DESIGN.md
を概観して、トークン変更が波及する範囲を掴んでおく。

## Step 3: フィードバック聴取

- 最初に「実機のスクリーンショットはある?」と確認する。あればパスを
  受け取って Read（画像）し、モック / トークンとの乖離を具体的に列挙する。
  スクショを手元に残す場合はプロジェクトルートの `tmp/` 配下に置く
  （`tmp/` は git 管理外であること — バイナリは git 管理しない。配下の
  パスは固定せず、セッション内のコンテキストで扱う）。変更根拠は Step 5
  で DESIGN.md に言語化して残す
- 言葉のフィードバックは、対象の成果物（どのトークン / どのモックのどの
  部分）へ翻訳してから認識合わせする

## Step 4: 合意ループ

修正候補ごとに: 成果物を更新 → ユーザーに確認（モックはブラウザで開いて
もらう）→ フィードバック → 再修正。**ユーザーの明示承認で確定**。対話
コマンドなのでループ上限は設けない。

- tokens.yaml の変更は feature 横断に波及する — 変更するトークンの使用箇所
  （既存モック・実装コード）を Grep で列挙し、影響範囲を添えて確認する。
  変更を適用したら `design-system/tokens.html`（ビジュアルトークンシート）
  を必ず再生成し、パレットの確認はこれをブラウザで開いてもらう
- モックの更新でも designer.md のモック規律（self-contained / token CSS
  変数 / SPEC 状態網羅）を維持する

## Step 5: DESIGN.md / meta 更新

- feature スコープ: 変更した決定を DESIGN.md の Decisions / Rationale に
  反映する（変更履歴は書かない — 変遷は git が持つ）
- システム全体スコープ: tokens.yaml の `meta`（tone / naming）と各
  `description` を最新の判断に揃える

## Step 6: 締め

日本語で報告する: 更新した成果物の一覧、更新後の成果物と現在の実装との
乖離（あれば 1-3 行）。乖離があれば「反映するには /em-workflow:develop で
デザイン反映の feature を回してね」と案内する（このコマンドからは起動
しない）。プロジェクトが git 管理下なら、更新した成果物のコミットを促す。

## 境界

- コード・スタイルファイル・workflow.yaml・SPEC.md・REQUIREMENTS.md に
  触れない
- 書き込み先は `feature-docs/*/DESIGN.md`・`feature-docs/*/design/` 配下・
  `design-system/` 配下・プロジェクトルート `tmp/` 配下（スクショの一時
  保管のみ）に限る

$ARGUMENTS
