# Feature: rm-parent-ref-self-config-deny

## 概要

`em-workflow/hooks/destructive-guard.py` の `rm_protected_operand_numbers()` で、rm の対象のうち、親ディレクトリ参照（`..`）を畳むと保護範囲の外に出るものを、自己設定パスとして扱わないようにする。その対象の再帰削除は、self-modification の ask に飲まれず deny / rm-recursive になる。保護範囲の中にとどまる対象の扱いと、HOME が /home の下に無い環境での扱い（前 feature mixed-rm-self-config-deny の FR2・A1）は変えない。

## 目的

- rm の対象のうち、親ディレクトリ参照（`..`）を畳むと保護範囲の外に出るものを、自己設定パスとして扱わない。その対象の再帰削除は、self-modification の ask に飲まれず deny / rm-recursive になる。
- 保護範囲の中にとどまる対象と、HOME が /home の下に無い環境で自己設定パスだけを消す rm は、今と同じく self-modification の ask のままにする（前 feature mixed-rm-self-config-deny の FR2・A1）。

## 受け入れ条件

- [ ] AC1: CLAUDE_BATCH なしの `rm -rf ~/.claude/skills/foo ~/.claude/skills/../../valuable` は deny / rm-recursive になる（攻撃シナリオが成り立たない）。
- [ ] AC2: `rm -rf ~/.claude/skills/../../valuable` 単体は deny / rm-recursive になる。
- [ ] AC3: CLAUDE_BATCH を立てた AC1 の形も deny / rm-recursive になる。
- [ ] AC4: `rm -rf ~/.claude/skills/foo` と、前 feature のケース（mixed-rm-self-config-deny TS-1 から TS-15）の判定と理由 ID は変わらない。
- [ ] AC5: HOME が /home の下に無い環境でも、`rm -rf ~/.claude/skills/foo` は ask / self-modification のまま（A1）で、`rm -rf ~/.claude/skills/../../valuable` は deny / rm-recursive になる。
- [ ] AC6: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` が全件通る。

## 技術要件

### 機能要件

- **FR1: `..` で保護範囲の外に出る対象を保護パスとみなさない**
  `em-workflow/hooks/destructive-guard.py` の `rm_protected_operand_numbers()` で、生のオペランドが SELF_CONFIG に一致しても、そのオペランドの `..` を語彙的に畳んだ形（`~` / `$HOME` は展開しない）が SELF_CONFIG に一致しなければ、生の形の一致は数えない。`normalize_candidate()` の形（HOME を展開して畳んだ形）が SELF_CONFIG に一致する場合は、今と同じく保護パスとみなす。
    - 例: `~/.claude/skills/../../valuable` は、畳んだ形 `~/valuable` も展開した形も一致しないので保護パスではない。
    - 例: `~/.claude/skills/../hooks/x` は畳んだ形 `~/.claude/hooks/x` が一致するので保護パスのまま。
- **FR2: 前 feature の FR2・A1 と両立させる**
  生の形か正規化した形のどちらかで判定する方式（前 feature の FR2）は保ち、正規化後の形だけで判定する方式にはしない。HOME が /home の下に無い環境では、`~/.claude/skills/foo` の `normalize_candidate()` の形が SELF_CONFIG に一致しない。そのため生の形（`..` を畳んでも一致する形）での一致で保護パスとみなし、自己設定パスだけを消す rm は self-modification の ask のままにする（A1）。
- **FR3: 両方の経路に効かせる**
  `rm_protected_operand_numbers()` を呼ぶ 2 か所の両方に同じ判定が効く。
    - 普通の経路: `rm_protected_operand_numbers(args)`（10663 行目）
    - コマンド置換が先頭の経路: `rm_protected_operand_numbers(shaped_words[skip_index:])`（10630 行目）

  除外の条件（その文の `self_modification_asked`）と、除外の単位が対象であることは変えない。
- **FR4: docstring を直す**
  `rm_protected_operand_numbers()` の docstring（10427-10438 行目）の、`check_self_modification()` と同じく生の形か正規化した形で一致を見るという記述を、新しい判定に合わせて書き直す。
- **FR5: 回帰ケースを足す**
  `em-workflow/hooks/tests/destructive-guard-cases.json` の表の最後に、rule 付きで次のケースを足す。
    1. `rm -rf ~/.claude/skills/../../valuable` 単体は deny / rm-recursive。
    2. 保護パスと並べた `rm -rf ~/.claude/skills/foo ~/.claude/skills/../../valuable` は deny / rm-recursive。

  ラベルは `"rm-parent-ref-self-config-deny TS-"` で始め、マシン固有のパスやホームディレクトリのパスは書かない。既存のケースは書き換えない。

### 非機能要件

- **NFR1 - 変わる向き:** 判定は ask（self-modification）から deny（rm-recursive）に変わる向きだけに変わる。今 deny の形は弱めない。既存のケース表で判定や理由 ID が変わるケースは無い（`.claude` と `..` を同じオペランドに含む rm のケースは今の表に無い）。
- **NFR2 - 決定性:** 判定は今までどおりコマンド文字列（と hook 起動時の HOME）だけで決まり、ファイルシステムは見ない（normpath による語彙的な畳み込みだけを使う）。
- **NFR3 - 性能:** 走査は今の scan budget と線形の作業上限の中に収まる。どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない。
- **NFR4 - version:** バグ修正なので plugin.json と marketplace.json の version は変えない（patch は Actions が上げる）。

## 実装方針

### 変更箇所

- `em-workflow/hooks/destructive-guard.py`
    - `rm_protected_operand_numbers()` の保護パス判定（FR1、FR2）
    - 同関数の docstring（FR4）
    - 呼び出し元 2 か所（10630 行目、10663 行目）は同じ関数を通るので、関数側の変更で両方に効く（FR3）
- `em-workflow/hooks/tests/destructive-guard-cases.json` — 表の最後に回帰ケースを足す（FR5）
- `tests/` 配下の unittest — HOME を差し替えたサブプロセスでの判定（TS-6）

### 保護パス判定

オペランドごとに次で判定する。

| 生の形が SELF_CONFIG に一致 | `..` を語彙的に畳んだ形（HOME は展開しない）が一致 | `normalize_candidate()` の形が一致 | 保護パスとみなすか |
|---|---|---|---|
| する | する | 問わない | みなす |
| する | しない | する | みなす |
| する | しない | しない | みなさない |
| しない | — | する | みなす |
| しない | — | しない | みなさない |

### 変えないもの

- `check_self_modification()` の判定（生の形か正規化した形のどちらかで SELF_CONFIG に一致すれば self-modification の ask を出す）。
- 除外の条件（その文の `self_modification_asked`）と、除外の単位が対象であること。
- `.claude/rules/hook-tests.md` の優先順位の箇条。
- 前 feature（mixed-rm-self-config-deny）の SPEC.md。

## 宣言する変更範囲

上に挙げた feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

どの SPEC も、feature 固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/rm-parent-ref-self-config-deny/**`
- `test-docs/rm-parent-ref-self-config-deny/**`

`feature-docs/rm-parent-ref-self-config-deny/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design step の成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・管理し、この節はその規則を再掲しない。

`test-docs/rm-parent-ref-self-config-deny/**` はタスクごとのテスト記録 `test-docs/rm-parent-ref-self-config-deny/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・管理し、この節はその規則を再掲しない。

この 2 つは、SPEC の作成者が明示的に外さない限り宣言に含まれる。

この宣言は上位集合の宣言で、検証時に観測される実際の変更範囲は、宣言した範囲に含まれていればよい（一致は要らない）。宣言したパスが実際には作られなくても違反ではない。

## テストシナリオ

### 結合テスト（ケース表 `em-workflow/hooks/tests/destructive-guard-cases.json`）

- [ ] TS-1: `rm -rf ~/.claude/skills/../../valuable` - [deny, rm-recursive]（ケース表、rule 付き）
- [ ] TS-2: `rm -rf ~/.claude/skills/foo ~/.claude/skills/../../valuable` - [deny, rm-recursive]（ケース表、rule 付き）
- [ ] TS-3: TS-2 の形を batch:true で - [deny, rm-recursive]
- [ ] TS-4: `rm -rf ~/.claude/skills/../hooks/x`（畳んでも保護範囲の中） - [ask, self-modification]
- [ ] TS-5: `rm -rf /home/user/.claude/skills/../../valuable` - [deny, rm-recursive]

### 単体テスト

- [ ] TS-6: HOME を /home の下に無い値に差し替えたサブプロセスで、`rm -rf ~/.claude/skills/foo` が ask / self-modification、`rm -rf ~/.claude/skills/../../valuable` が deny / rm-recursive になる（AC5。ケース表のランナーは HOME を差し替えられないので `tests/` 配下の unittest で確かめる）。
- [ ] TS-7: コマンド置換が先頭の経路 `$(printf rm) -rf ~/.claude/skills/foo ~/.claude/skills/../../valuable` の判定と理由 ID を、実際の出力どおり固定する。

### E2E テスト

**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

### エッジケース

- [ ] TS-8: `rm ~/.claude/skills/../../valuable`（再帰でない）: rm の deny が無いので、`check_self_modification()` が出す self-modification の ask のまま（この feature では変えない）。
- [ ] TS-9: `rm -rf ~/.claude/skills/..`: 畳んだ形 `~/.claude` は SELF_CONFIG に一致しない（今の `rm -rf ~/.claude` と同じ扱い）ので保護パスではなくなり、ask から deny / rm-recursive に変わる。
- [ ] TS-10: `..` で安全な領域に入る対象（例 `~/.claude/skills/../../../../tmp/x`）: `check_rm()` は `safe_delete_target()` で record を出さないので、self-modification の ask のまま。
- [ ] TS-11: `~/.claude/skills/foo/..`: 畳んだ形 `~/.claude/skills` が一致するので保護パスのまま。

## 前提

- **A1:** `check_self_modification()` の判定（生の形か正規化した形のどちらかで SELF_CONFIG に一致すれば self-modification の ask を出す）は変えない。課題の該当箇所は `rm_protected_operand_numbers()` だけで、rm の deny は、残っている self-modification の ask に勝つ（hook-tests.md の優先順位）ので、完了の定義はこの関数を直すだけで満たせる。
- **A2:** 「保護範囲の外に出る」は、生のオペランドの `..` を語彙的に畳んだ形（HOME は展開しない）が SELF_CONFIG に一致しなくなることで判定する。HOME を展開した形だけで判定すると、HOME が /home の下に無い環境で前 feature の A1 が壊れるため。
- **A3:** 前 feature（mixed-rm-self-config-deny）の SPEC.md の Edge Cases の範囲外の記述と Assumption A2 は、当時の記録として書き換えない。
- **A4:** `.claude/rules/hook-tests.md` の優先順位の箇条（保護された自己設定パスだけが候補から外れる）は、この変更の後も正しいので書き換えない。
- **A5:** 新しいケースは表の最後に足す。前 feature の A6 によると、`tests/` 配下でケース表の先頭部分のダイジェストを固定しているテストがあるが、その範囲は表の先頭の一部だけで、最後に足すケースは入らない。
- **A6:** ファイルシステムは見ないので、`..` の手前のシンボリックリンクによる実際の行き先の違いは扱わない（`normalize_candidate()` と同じく語彙的に畳むだけ）。
- **A7:** LICENSE ファイル、パッケージマニフェスト、E2E の仕組み、UI はどれも無い。

## 完了条件

- [ ] FR1 から FR5 が実装され、テストされている
- [ ] TS-1 から TS-11 が通る
- [ ] AC1 から AC6 を満たす
- [ ] NFR1 から NFR4 を満たす

## 未解決の事項

なし（`status: tbd` の要件は無い）。

## 参照

- フックのテストの規則: `.claude/rules/hook-tests.md`
- 前 feature の仕様: `feature-docs/mixed-rm-self-config-deny/SPEC.md`
