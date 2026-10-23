# Threat Model: codex-guard-procsub-in-wordlist

## Verdict
threats-identified

## Rationale
SPEC.md と REQUIREMENTS.md を確認した（tier: full、design は skipped）。このフィーチャーが扱う入力は、エージェントが組み立てた Bash コマンド文字列で、PreToolUse(Bash) の JSON としてフックの標準入力に届く。task0001 の domains は input-handling なので、TB-1 を deep で分析した。

フックの役割は、無人実行で入力待ちになる対話的なコマンドを拒否すること。読みのずれは、拒否漏れ（入力待ちで止まる）でも誤拒否（その場で止まる）でも無人実行を止めるので、脅威はすべて Denial of service として記録した。

`tests/test_codex_hook_interactive_guard.py` は開発者の手元で固定の入力を流すだけで、信頼の境界を越えない。外部サービス、永続化、認証は扱わない。

## Trust Boundaries

### TB-1: エージェントが組み立てたコマンド文字列 → codex-hook-interactive-guard の読み
Crossing: エージェント（読んだ外部の文書やツールの出力に影響されうる）が組み立てたコマンド文字列が、PreToolUse(Bash) の JSON としてフックに渡る。フックはそれを字句として読み、deny / silent を決める
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | 語一覧の最も外側の項目の語の先頭にあるプロセス置換の中で、空白の後の `#` コメントに `"` があると、今の読みはそれを引用の開始として読み、入力末尾で判定不能になって後ろの対話的なコマンドを拒否しない（拒否漏れ）。無人実行が入力待ちで止まる（FR1） | TM-1 | 最も外側の項目の語の先頭にある引用・エスケープの無い `<(`・`>(`・`=(` を p として積み、中のコメントをコメントとして読む。2 つのコピーに同じ読みを入れる（FR3） | task0001 AC-1 | VERIFICATION.md Performance / Security Verification の TM-1（TS-1、TS-3、TS-4、TS-5、TS-14） |
| Denial of service | 修正を広く当てすぎ、入れ子の項目の中・語の途中・エスケープや引用符の後・エスケープした空白の後・語の途中の継続行の後の `(` まで p として読むと、`#c` から入力末尾までが改行の無いコメントになり、判定不能で後ろの対話的なコマンドを拒否しない（FR1、FR2） | TM-2 | 語の先頭を読みながら持つ字句状態で決め（エスケープした文字・引用・置換・入れ子の項目は語を始め、継続行は状態を保つ）、それ以外の `(` は入れ子の w のまま読む | task0001 AC-2 | VERIFICATION.md Performance / Security Verification の TM-2（TS-6〜TS-13） |
| Denial of service | 同じプロセス置換の中のコメントの一部にある対話的なコマンドを命令として読み、実行されないコマンドで deny して無人実行を止める（誤拒否）（FR1） | TM-3 | p の中の空白の後の `#` から改行までをコメントとして読み飛ばす | task0001 AC-1 | VERIFICATION.md Performance / Security Verification の TM-3（TS-2） |
| Denial of service | 語の先頭の判定に再帰や読み終えた文字の見返しを足すと、細工した深い入れ子や長い入力で読みが線形でなくなり、フックの判定が止まるか失敗する（NFR1） | TM-4 | 語の先頭を定数サイズの状態で判定し、読みを線形・再帰なしに保つ | task0001 AC-4 | VERIFICATION.md Performance / Security Verification の TM-4（TS-16） |
