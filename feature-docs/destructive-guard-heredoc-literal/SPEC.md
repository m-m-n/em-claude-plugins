# Feature: destructive-guard-heredoc-literal

## Overview

`em-workflow/hooks/destructive-guard.py` が、Python インタプリタ宛ての heredoc 本文に書かれた
閉じた通常の文字列リテラルの中身を、シェルのコマンドとしても置換としても読まないようにする。
対象は宛先が Python だと確定できる heredoc に限り、それ以外の宛先と、判断できない形の判定は今と変えない。

## Objectives

- destructive-guard.py が、Python インタプリタ宛ての heredoc 本文に書かれた文字列リテラル（引用として書いた破壊的コマンドの語）を実行コマンドと読み違えて deny しないようにする。無人 batch がそこで止まらないようにするため。
- 検知力は落とさない。既存の deny / ask ケースは全件そのまま通る。

## Acceptance Criteria

- [ ] AC-1: `` python3 <<'PY'\ntext = "`git branch -D example`"\nPY `` が allow になる。
- [ ] AC-2: `python3 - <<'PY'` で監査記録を書き込む形（`with open(...) as f: f.write("... rm -rf /home/user/valuable ... git branch -D example ...")`）が allow になる。
- [ ] AC-3: 単一引用符、三重引用符で複数行にまたがるもの（中に `git reset --hard HEAD` の行があるもの）、`r` / `b` の前置子付き、`$( )` を含むリテラル、`python3.12` 宛ての形、コメントに引用符を含む形が、どれも allow になる。
- [ ] AC-4: 既存の deny / ask ケース（`python3.12 <<'EOF'\ngit reset --hard HEAD\nEOF` を含む）が全件そのまま通る。ランナーが全件 ok で終わる。
- [ ] AC-5: 区切り語に引用符が無い `python3 <<PY` で、リテラルの中に `$(git branch -D example)` やバッククォートの `git branch -D example` があるものは deny のまま。
- [ ] AC-6: `python3 <<'PY' | bash`（print で破壊的コマンドを出す）と、`bash -c "$(python3 <<'PY' ... PY\n)"` は deny のまま。
- [ ] AC-7: `bash <<'EOF'` と `perl <<'EOF'` で本文にバッククォートの `git branch -D example` があるものは deny のまま。
- [ ] AC-8: リテラルの後にリテラルの外の行として `git reset --hard HEAD` がある Python 本文は deny のまま。
- [ ] AC-9: 閉じていないリテラルを含む Python 本文と、f-string の中にバッククォートの `git branch -D example` がある Python 本文は、変更前と同じ判定になる。変更前の値を確かめたうえでケースとして固定する。

## Technical Requirements

### Functional Requirements

- **FR1: Python 宛ての heredoc 本文の中の閉じた通常文字列リテラルを読まない** —
  宛先が Python インタプリタだと判定された heredoc では、本文の中の閉じた通常の Python 文字列リテラルの中身を、シェルのコマンドとしても、置換（バッククォート、`$( )`、`${ }`、`<( )`、`>( )`）としても読まない。
  対象にする書き方は `'...'` / `"..."` / `'''...'''` / `"""..."""` と、前置子 `r` `b` `u` およびその組み合わせ（大文字・小文字の両方）。
  字句解析が失敗したときの退避処理による生テキストの照合と、チャンク単位の sink 語の照合も、そのリテラルの中身を見ない。
- **FR2: 宛先が Python だと判定する条件** —
  FR1 を適用するのは次をすべて満たすときだけ。
  - (a) heredoc を持つ文のコマンド語が、`SINK_WORD_RE` の Python 語彙（`python`、`python3`、`python3.12` など）に一致する。`sudo` などのラッパーを外した後の語は、既存の宛先判定の読み方に従う。
  - (b) その文のパイプラインの下流に、sink の段も宛先不明の段も無い。
  - (c) 外側の文（置換を包む文、グループ、パイプライン）のどれにも、sink（シェルでも他のインタプリタでも）が無く、宛先不明のものも無い。

  どれか 1 つでも満たさなければ、判定は今と同じにする。
- **FR3: リテラルの外は今どおり読む** —
  Python 宛ての本文でも、FR1 の対象となる文字列リテラルの外のテキストは今と同じようにシェルとして読む（例: 本文の 1 行がそのまま `git reset --hard HEAD` なら deny のまま）。
  本文全体が有効な Python 構文であることは条件にしない。
  Python のコメント（`#` から行末まで）の中にある引用符で、リテラルを開かない。
- **FR4: f-string / t-string は対象外** —
  前置子 `f` または `t` を含む文字列リテラル（`rf`、`fr`、`Rt` などの組み合わせを含む）は FR1 の対象にしない。その中身は今と同じように読む。
- **FR5: 区切り語に引用符が無い heredoc の置換は今どおり調べる** —
  区切り語に引用符が無い heredoc（`<<PY`）では、外側のシェルが本文を Python に渡す前に `$( )` とバッククォートを展開する。
  そのため、リテラルを除外する前の原文から、Python のリテラルの中に書かれたものも含めて本文中の置換を今と同じに抜き出して調べる（data 宛て heredoc と同じ扱い。バックスラッシュでエスケープした `\$(` は置換と見なさない、という既存の規則も保つ）。
- **FR6: 判断できないときは今と同じ** —
  リテラルの範囲を確定できないとき（閉じていないリテラルがある、など）は、その本文全体にリテラルの中身を読まない扱いをいっさい適用しない。判定は今と同じになる。
- **FR7: 他の宛先は変えない** —
  シェル（`sh`、`bash`、`zsh`、`dash`、`ksh`）、`perl`、`ruby`、`node` 宛ての heredoc、宛先不明の heredoc（`timeout` / `exec` / グループの閉じなど）、data 宛ての heredoc は、判定を今と変えない。
  `cat <<'X' | python3` のようにパイプでつないだ形（現実装でもパイプ下流の sink 宛てと判定される形）も、判定を今と変えない。
- **FR8: テストケース** —
  `em-workflow/hooks/tests/destructive-guard-cases.json` に、再現する形を allow 側のケースとして足す（直す前に足す）。
  境界を固定する deny 側のケースも足す。既存のケースは消さず、書き換えもしない。

### Non-Functional Requirements

- **NFR1 - 静的解析のみ:** 静的解析だけで判定する。本文を評価・実行・import しない。使ってよいのは Python 標準ライブラリだけ。
- **NFR2 - 時間予算:** 1 回の判定は、テストランナーの制限（`GUARD_TIMEOUT_SECONDS` = 10 秒）と既存のスキャン予算の中に収める。リテラルの判定は本文の長さに対して線形にする。
- **NFR3 - 変更範囲:** 変更するのは `em-workflow/hooks/destructive-guard.py` と `em-workflow/hooks/tests/destructive-guard-cases.json` だけ。`plugin.json` と `marketplace.json` の version には触らない。
- **NFR4 - 既存スイートが通る:** `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 ok で終わる。

## Implementation Approach

### 判定の流れ

```
heredoc を持つ文
  → FR2 の (a)(b)(c) をすべて満たすか
      いいえ → 今と同じ判定（FR7）
      はい   → 本文の閉じた通常文字列リテラルの範囲を確定できるか（FR1 / FR3 / FR4）
                 いいえ → 今と同じ判定（FR6）
                 はい   → リテラルの中身を除いて本文を読む（FR1 / FR3）
                          区切り語に引用符が無いときは、除外前の原文から置換も今どおり調べる（FR5）
```

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: 既存の宛先判定（`SINK_WORD_RE`、ラッパーを外す読み方、パイプライン下流と外側の文の判定）、字句解析失敗時の退避処理、チャンク単位の sink 語の照合
- `em-workflow/hooks/tests/run-destructive-guard.py`: テストランナー（`GUARD_TIMEOUT_SECONDS` = 10 秒）

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py
└── tests/
    └── destructive-guard-cases.json
```

## Declared Change Set

この節は手書きの一覧ではなく、create-plan での導出を記す。上記の機能固有のパスは、create-plan で
`workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

機能固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言に含める。

- `feature-docs/destructive-guard-heredoc-literal/**`
- `test-docs/destructive-guard-heredoc-literal/**`

`feature-docs/destructive-guard-heredoc-literal/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、
`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、
design ステップの成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有し、
この節はそれらを引用するだけで規則を再記述しない。

`test-docs/destructive-guard-heredoc-literal/**` はタスクごとのテスト記録
`test-docs/destructive-guard-heredoc-literal/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有し、
この節はそれを引用するだけで規則を再記述しない。

この 2 つの既定エントリは、SPEC の作成者が明示的に外さない限り宣言に含まれる。

この宣言は上位集合の宣言であり、検証時に観測した実際の変更集合が宣言集合に含まれていればよい（一致は求めない）。
宣言したパスが実際に作られなくても違反ではない。

## Test Scenarios

TS-1〜TS-15 は FR8 に従い `em-workflow/hooks/tests/destructive-guard-cases.json` にケースとして足す。
コマンドの中の改行は、ケースの文字列では改行文字になる。

### Unit Tests

allow になる形（直す前に足す）。

- [ ] TS-1: 二重引用符のリテラルの中のバッククォート（AC-1） - allow
  ```
  python3 <<'PY'
  text = "`git branch -D example`"
  PY
  ```
- [ ] TS-2: `python3 -` で監査記録を書き込む形（AC-2） - allow
  ```
  python3 - <<'PY'
  with open("phase-state/batch-audit.yaml", "a") as f:
      f.write("note: `git branch -D example` / rm -rf /home/user/valuable\n")
  PY
  ```
- [ ] TS-3: 単一引用符のリテラルの中の `$( )`（AC-3） - allow
  ```
  python3 <<'PY'
  note = '$(git reset --hard HEAD)'
  PY
  ```
- [ ] TS-4: 三重引用符で複数行にまたがり、中に `git reset --hard HEAD` の行があるリテラル（AC-3） - allow
  ```
  python3 <<'PY'
  doc = """
  git reset --hard HEAD
  """
  PY
  ```
- [ ] TS-5: `python3.12` 宛てで、`r` / `b` の前置子付きリテラル（AC-3） - allow
  ```
  python3.12 <<'PY'
  x = r'`rm -rf /home/user/valuable`'
  y = b"`git branch -D example`"
  PY
  ```
- [ ] TS-6: コメントに引用符を含む形（AC-3） - allow
  ```
  python3 <<'PY'
  # don't
  x = "`git branch -D example`"
  PY
  ```

### Integration Tests

境界を固定する deny 側の形。

- [ ] TS-7: 区切り語に引用符が無い heredoc で、リテラルの中に `$( )`（AC-5） - deny
  ```
  python3 <<PY
  x = "$(git branch -D example)"
  PY
  ```
- [ ] TS-8: 区切り語に引用符が無い heredoc で、リテラルの中にバッククォート（AC-5） - deny
  ```
  python3 <<PY
  x = "`git branch -D example`"
  PY
  ```
- [ ] TS-9: パイプラインの下流が `bash`（AC-6） - deny
  ```
  python3 <<'PY' | bash
  print("git reset --hard HEAD")
  PY
  ```
- [ ] TS-10: 外側の文が `bash -c` の置換（AC-6） - deny
  ```
  bash -c "$(python3 <<'PY'
  print('git reset --hard HEAD')
  PY
  )"
  ```
- [ ] TS-11: `bash` 宛ての heredoc の本文にバッククォート（AC-7） - deny
  ```
  bash <<'EOF'
  echo "`git branch -D example`"
  EOF
  ```
- [ ] TS-12: `perl` 宛ての heredoc の本文にバッククォート（AC-7） - deny
  ```
  perl <<'EOF'
  `git branch -D example`;
  EOF
  ```
- [ ] TS-13: リテラルの後に、リテラルの外の行として `git reset --hard HEAD`（AC-8） - deny
  ```
  python3 <<'PY'
  x = "safe"
  git reset --hard HEAD
  PY
  ```

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

変更前の判定を確かめ、その値を期待値として固定する（変更後も同じ判定になる）。

- [ ] TS-14: 閉じていないリテラルを含む Python 本文（AC-9） - 変更前と同じ判定
  ```
  python3 <<'PY'
  x = "unterminated `git branch -D example`
  PY
  ```
- [ ] TS-15: f-string の中にバッククォート（AC-9） - 変更前と同じ判定
  ```
  python3 <<'PY'
  y = f"{1} `git branch -D example`"
  PY
  ```

### Regression Tests

- [ ] TS-16: 既存スイートの全件（既存の deny / ask ケースを含む）が通る（AC-4） - 次のコマンドが全件 ok で終わる
  ```
  python3 em-workflow/hooks/tests/run-destructive-guard.py
  ```

## Security Considerations

- **Input Validation:** 判定は静的解析だけで行い、本文を評価・実行・import しない（NFR1）。
- **既知の制約:** Python 宛ての heredoc の中で、FR1 の対象リテラルを後からシェルに渡す書き方（`os.system` や `subprocess` の `shell=True` に渡す文字列にバッククォートや `$( )` を含めるもの）は、この変更で allow になりうる（A-3）。

## Error Handling

- リテラルの範囲を確定できないときは、その本文全体にリテラルの中身を読まない扱いを適用せず、判定は今と同じにする（FR6）。
- FR2 の条件を 1 つでも満たさないときは、判定は今と同じにする（FR2）。

## Performance Optimization

### Performance Goals

- 1 回の判定は、テストランナーの制限（`GUARD_TIMEOUT_SECONDS` = 10 秒）と既存のスキャン予算の中に収める（NFR2）。
- リテラルの判定は本文の長さに対して線形にする（NFR2）。

## Assumptions

- **A-1:** 完了の定義（既存の deny / ask を赤にしない）が、期待する挙動の文言（heredoc 本文を一律に解析しない）より優先する。シェル宛ての本文はシェルのコマンドなので、今どおり読む。
- **A-2:** 適用範囲は Python インタプリタ宛ての本文の中の、閉じた通常文字列リテラルに限る。式を評価する f-string / t-string と、perl / ruby / node は変えない。
- **A-3:** Python 宛ての heredoc の中で、FR1 の対象リテラルを後からシェルに渡す書き方（`os.system` や `subprocess` の `shell=True` に渡す文字列にバッククォートや `$( )` を含めるもの）は、この変更で allow になりうる。これは既知の制約として受け入れる。
- **A-4:** 宛先不明の形（`timeout 5 python3 <<'PY'`、`exec python3`、`{ python3; } <<'PY'`）と、パイプでつないだ形（`cat <<'PY' | python3`）は範囲外にして、判定を今と変えない。

## Success Criteria

- [ ] FR1〜FR8 が実装され、テストされている
- [ ] TS-1〜TS-16 がすべて通る
- [ ] NFR1〜NFR4 を満たす

## Open Questions

なし

## References

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/hooks/tests/run-destructive-guard.py`
