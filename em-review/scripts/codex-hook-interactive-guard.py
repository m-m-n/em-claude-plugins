#!/usr/bin/env python3
"""Codex PreToolUse(Bash) guard against launching an interpreter or shell in
interactive mode.

Codex gives a Bash call a pseudo terminal. A `python3 -i` started there keeps
waiting for input after the terminal is gone, and it spins as an orphan
process. The guard reads the command string of one Bash call and denies the
launches that would open a REPL.

Decision flow:

  1. Read stdin, parse it as one JSON object. Any failure -> no output.
  2. Take tool_input.command. Absent or not a string -> no output.
  3. Remove heredoc bodies and split the command into simple commands at
     `;` `&&` `||` `|` `&` and newlines. Quoted text and comments are not
     read as commands. An unbalanced quote or an unterminated heredoc ->
     no output. These make the string undecidable: the commands up to the
     last checkpoint are judged (step 9), and a string with no checkpoint
     gives no output; the same holds for every other `-> no output` of this
     step. The reader takes a command substitution inside double quotes
     (`$( ... )`, `$(( ... ))` or a backtick span) as one chunk up to its
     matching close: quotes, backslashes and substitutions inside it close
     nothing outside, the word holding it is dynamic, and its contents are
     not judged. A chunk that is not closed, or whose close cannot be located
     with certainty -> no output. After the closing quote ordinary reading
     resumes, so a launch outside the quotes is still judged. A backtick span
     outside quotes is one dynamic chunk too: it ends at the first backquote
     that is not part of a backslash pair (a backslash and the character after
     it), and a span with no such backquote left -> no output.
  4. A subshell `( ... )` and a brace group `{ ...; }` are groups. `{` and
     `}` delimit a group only as a standalone word: a `{` opens a group at
     command position, and also right after the head of a zsh anonymous
     function (below); a brace inside a larger word (`{a,b}`) does not. A
     group is connected when it is the right side of `|` or `|&`, or when a
     stdin redirect follows its close (`<` `<<` `<<<` `<&` `0<`). Other
     redirects (`2>` `>`) and a pipe on the right of the group do not connect
     it. A connected group passes the connection to every command inside it,
     nested groups included, so the commands of a group are judged once the
     redirects after its close are known. A group that is not closed -> no
     output. Like every other `-> no output` of this step, it makes the string
     undecidable: the commands up to the last checkpoint are judged (step 9),
     and a string with no checkpoint gives no output. The body of a function
     definition (`name() { ...; }`) is not judged. The guard reads a
     definition by the words before the `(` alone:
     only `name()` and `function name()` start a function definition, where
     `name` is one word that is not dynamic and holds no `=`. A word whose
     content, after quote removal, ends in one of the extglob operator
     characters `?` `*` `+` `@` `!` is no function name, even when it is the
     one reserved word left (`!`): the `()` after it starts no definition and
     the group after its `()` is judged. Only the last character is read,
     whether it is quoted, escaped or followed by a space, and whether extglob
     is enabled is never checked. The
     words before `(` are judged after the leading run of the reserved words
     `!` `do` `elif` `else` `if` `then` `time` `until` `while` is removed, so a
     definition written right after `then` or `do` still starts one; a
     non-dynamic `-p` right after `time` is removed with it, and a reserved
     word later in the words is never removed. When nothing remains, the
     original words are judged. When the one word left after the removal is
     `function` and it holds no quote, no escape and no expansion (a zsh
     anonymous function `function () { ...; }`), it is no function name: the
     `()` after it starts no definition and the group after its `()` is
     judged, with or without a reserved word in front of it. A quoted or
     escaped `function` is still a name, and so is the first `function` of
     `function function ()`. The group that follows the empty `()` of a
     definition is its body, `( ... )` or `{ ...; }`, even when newlines come
     between. Any other words before `()` (an assignment such as `a=()` or
     `export a=()`, a dynamic word, three words or more left after the
     removal) start no definition, so the group after them is judged. `while`
     `for` `until` `if` and `case` are not read as groups.
     A zsh anonymous function has three forms, and the commands inside the
     body of each are judged like those of any other group: `function { ...; }`
     (a standalone `{` in the same simple command right after one `function`
     word that holds no quote, no escape and no expansion, once the leading
     run of reserved words is removed as above), `function () { ...; } arg`
     (the empty `()` right after that `function`) and `() { ...; } arg` (an
     empty `()` read where the simple command holds no word yet; a reserved
     word in front of the `()` keeps the function-name judgment above).
     Newlines may come between the empty `()` and the `{`. Every word after
     the closing `}` of an anonymous body, up to the next `;` `&&` `||` `|`
     `|&` `&` or newline that lies outside a `(`...`)` range (below), or the
     close of an enclosing subshell, is an argument of the anonymous function:
     it is no command and does not make the string undecidable. A stdin
     redirect among or after the arguments connects the body, exactly as when
     it is written right after the `}`; other redirects do not. A `(` among the
     arguments, in the middle of a word (`foo(x)`) or at its start (`(x)`), is
     read together with everything up to its matching `)` as part of one
     argument word: whitespace and `|` inside the range belong to the word and
     end no argument, and the body stays the group the arguments belong to, so
     a stdin redirect after the range still connects it. The matching `)` is
     found by skipping backslash pairs, single-quoted text and double-quoted
     text only; a backquote and a comment get no special reading, so a `)` inside
     one closes the range. When the range from the `(` to that `)` holds an
     unquoted `;`, `&` or newline, the `(` opens a group, exactly as before the
     range was read as a word; so it does when no matching `)` is found. A range
     that holds a backquote, one inside double quotes included, opens a group
     too, unless a backslash escapes the backquote or single quotes enclose it;
     whether the backquotes balance does not matter, and a backquote after the
     range's closing `)` is no trigger. The backquote is only noticed, never
     read: it moves neither the nesting depth nor the `)` that closes the range.
     The group opened for a range that has a matching `)`, holds no unquoted
     `;`, `&` or newline and holds a backquote has the comment exception: while
     it is the innermost open group, an unquoted `#` at word start is a word
     character, not the start of a comment, and the characters after it join the
     word as in any other word, so a `)` after it still closes the group. The
     scan that finds the range still gives a backquote and a comment no special
     reading; the exception belongs to the reading of the group opened after it.
     A group opened while the innermost open group has the comment exception
     starts with it, whatever its own opening condition: the value is copied
     once, when the group opens, and a group that closes takes its value with
     it, so the value of its parent applies again. Reading a direct separator
     ends it: a `;`, a lone `&`, `&&`, `|&` or a newline that the reader itself
     reads while a group with the comment exception is the innermost open group
     clears it for that group for good, and a `#` at word start is a comment
     there as before; `|`, `||`, `&>`, `>&`, a quoted separator and a
     backslash-escaped separator clear nothing, and a separator read inside a
     nested group never changes an outer group. This is the single exception to
     the earlier assumption that group reading adds no new reading: a `#` at
     word start stays a comment outside every group, in a group opened at a `;`,
     `&` or newline, in a group opened because no matching `)` is found and in a
     group whose exception was cleared, a `#` inside `$(` is read as before, and
     a `#` in the middle of a word is a word character as ever.
     The word read as the target of `<<` or `<<-` (the delimiter position) has
     a reading of its own for `${` and for `$'` and `$"`, and only there. An
     unquoted `${` in it starts a range that ends at its close, and the range is
     read, as the close is searched, in one forward scan, into both forms of the
     delimiter word (below) before the delimiter is registered. The close is the
     first `}` that is outside single and double quotes, is not escaped by a
     backslash, does not lie inside a `$( ... )` or a `$(( ... ))` and does not
     close a nested `${ ... }` (the nested ones are counted by depth); a
     backquote there is an ordinary character. The search runs over the whole
     string, not the line, so a quote may span lines. The quote removal is the one described below: the `${`,
     the `}`, a nested `${`, `#`, `:-` and every other character stay as
     written, and the text before and after the range joins the registered
     delimiter unchanged (`foo${v:-"x"}bar` is registered as `foo${v:-x}bar`).
     That is the quote-removal form of the delimiter word. The word has a
     second form, the bash form, and it differs from the quote-removal form only
     when the delimiter word holds at least one `${ ... }` range and no quote
     unit outside its ranges: each range then contributes its original
     characters, with `"`, `'` and the backslash kept as written, minus the
     backslash-newline pairs outside single quotes (the ones inside double
     quotes are dropped too), and all other text of the word is the same as in
     the quote-removal form. When the word holds no range, or holds a quote unit
     outside its ranges, the bash form is the quote-removal form. A quote unit
     outside the ranges is a `'`, `"` or backslash unit that the word reader
     reads for the delimiter word, a quote unit inside a parenthesised argument
     range of the word included; a backslash-newline pair is no unit, and
     neither is a `$( ... )` or backquote span written directly in the word,
     nor the quotes inside it (`$(echo "P")${v:-"x"}` is registered as it stands
     in the bash form, `'P'${v:-"x"}` as `P${v:-x}` in both forms, and `P` with
     a backslash-newline pair before `${v:-"x"}` as `P${v:-"x"}`). Inside a
     range the bash form keeps a single-quoted unit as written, a backslash pair
     as its two characters (a backslash and a newline add nothing), a
     double-quoted unit as written minus its backslash-newline pairs, and a
     substitution as the skip below returns it, the same text as the
     quote-removal form. Both forms come from the one scan that finds the close,
     so the close search and every undecidable case below are the same for
     both, and an unquoted `$'` or `$"` in a range stays undecidable under the
     bash form.
     The delimiter reading is decided by the shell that directly holds the
     string: bash reads the bash form only, zsh and dash read the quote-removal
     form only, sh and ksh read both, and the hook command itself reads the
     quote-removal form only. The holder is matched the way the kind is matched
     (step 7): bash covers the bare name, a digits-and-dots suffix, a path, an
     option-less wrapper and `--posix`, and the suffixed and path forms of the
     other names count too. Only the direct holder decides, so a `zsh -c` string
     inside a `bash -c` string reads the quote-removal form. A string of sh or
     ksh is read under the bash form first and then under the quote-removal
     form (step 9).
     An unquoted `$(` inside a delimiter's `${ ... }` range (`$((` included) is
     skipped by the same case-aware skip that reads a substitution inside
     double quotes: a case statement inside it is read, so its pattern's `)`
     does not end it, and the substitution is kept as written, with its quotes
     (`${v:-$(case x in x) echo "x";; esac)}` is registered as it stands).
     Inside a parenthesised range, and in a `$( ... )` written directly in the
     delimiter word, the reading is unchanged: the `)` that closes the
     parenthesis is found by counting parentheses.
     The string is undecidable when the text ends before that close is found,
     when a quote is still open at the end of the text and when a `$(` has no
     close. The skip of an unquoted `$(` in a delimiter's `${ ... }` range makes
     it undecidable too when it cannot locate the close with certainty (a case
     statement with no closing `esac` before the input ends, for one) or ends
     beyond the end of the text. An unquoted `$'` or `$"` makes it undecidable
     too, inside such a range and outside any `${ ... }` of the delimiter
     alike, at the start of the word or in the middle of it (`foo$'x'`): what
     zsh reads there is not reproduced, so no delimiter is registered. A `$'`
     or `$"` inside double quotes and a backslash-escaped `$` make nothing
     undecidable. An undecidable string follows the checkpoint rule of step 9:
     the commands up to the last checkpoint are judged, so a launch on an
     earlier line is denied and one on the line of the delimiter is not, and a
     string with no checkpoint gives no output. Nothing else changes: a
     `${ ... }` in any other word (it closes at the first `}`, and the written
     characters stay a dynamic word), a `$'` or a `$"` in any other word, the
     target of `<<<` or `<`, a `${ ... }` inside double quotes in the
     delimiter, which the double-quoted unit reader reads, a backquote inside
     a delimiter's `${ ... }` and a `$( ... )` written directly in the
     delimiter word keep their reading.
     A range read as one word that is the delimiter of `<<` or `<<-`, or a part
     of it, has its text quote-removed by the rules the reader applies to any
     word, before the delimiter is registered: outside quotes a backslash is
     dropped and the next character kept (a backslash and a newline are both
     dropped), and `'` and `"` are dropped; single-quoted text is kept as it
     stands; inside double quotes a backslash is dropped only before `$`, a
     backquote, `"`, another backslash or a newline. A `$( ... )` or a
     `$(( ... ))` inside double quotes keeps its original text, the quotes inside
     it included, as zsh registers it; the text of a `$( ... )` outside quotes
     and every other character stay as written. The quote removal is done by the
     same reader that reads a backslash pair, a single-quoted unit and a
     double-quoted unit in any other word, held to the end of the range. A
     substitution skipped inside double quotes whose close lies beyond the end of
     the range, or that cannot be read, makes the whole input undecidable -> no
     output. The part of the word outside the range was quote-removed when it was
     read and is not processed again. A range
     that opens a group, as above, keeps that reading while a delimiter is
     awaited. An unquoted `$'` or `$"` inside such a range makes the whole input
     unknowable -> no output; a `$'` or `$"` inside quotes and a
     backslash-escaped `$` are no trigger.
     A group opened at such a `(` is provisional. A provisional group is
     rescued in three cases: input ends while it is still open (its `)` sits in
     a comment, or there is none), a lone bare `}` is read while it is the
     innermost open group (below), and an unquoted `)` is read while it is the
     innermost open group (below). In every case the first separator read
     directly in it must be a `;` or a lone `&`, and then its `(` is read as an
     argument-word character: the group ends at that separator, what comes
     before it keeps the reading it had, and the commands after that separator
     are judged as following the anonymous function, as commands of the frame
     that encloses the group (the pipe and the stdin redirect of the head reach
     none of them). The first separator read directly is the first one the
     reader meets while the provisional group is the innermost open group; a
     separator inside a group nested in it is not direct. Only the reader's own
     `;` and lone `&` count: a quoted or backslash-escaped `;` or `&`, a `&>` or
     `>&` redirect and the `&&` `||` `|` `|&` operators are no trigger, and an
     operator among them that comes first is the first separator, so the group
     is not rescued. Provisional groups nested in each other are rescued from
     the inside out, and an outer one with no separator of its own takes the
     separator of the inner one as its first. A newline as the first direct
     separator is not rescued -> no output. A group that is genuinely unclosed
     still yields no output: a group that is no provisional group (a `(` at
     command position, a `{` group, a function body) left open, even after a
     rescue, and a provisional group with no separator read directly in it. A
     `)` with no `(` among the arguments is a separator, as anywhere else (it
     closes an enclosing subshell when there is one). The work spent finding
     these ranges is capped at a constant multiple of the length of the string;
     once the cap is spent, every later `(` opens a group, as before.
     A stdin redirect read in the head of an anonymous function also connects
     its body (and so the groups nested in it). The head is the simple command
     up to the body, and the redirect sits before `function`, between `function`
     and the `{` (the parenless form), or before the `(` of the `()`, a newline
     between `()` and `{` included. That connection reaches the body alone: not
     the `(` group of the `()`, not a command after the separator that ends the
     arguments, and not a group that is no anonymous body. A redirect between the
     `()` and the `{` is not read as part of the head, and a redirect other than
     stdin connects nothing.
     When the head of an anonymous function is the right side of `|` or `|&`,
     the pipe connection passes to the body and, through the body, to the groups
     nested in it, and no further: the commands after the arguments are not
     connected, and an explicit `-i` is still denied. The words after the `}` of
     any other brace group, and of a function definition's body, still make the
     string undecidable.
     A standalone bare `}` closes the innermost group when the simple command in
     progress holds no word. With words pending it closes that group in two
     cases only: the group is the body of an anonymous function, or it is a `{`
     group that lies inside the body of an anonymous function, at any depth, a
     `(` group between them and the body of a function definition included. The
     pending words are then finalized first, as a command of that group, exactly
     as a `;` before the `}` finalizes them, and the group is closed. A `{` group
     that lies outside every anonymous function body (a top-level `{ ...; }`, the
     body of a function definition outside one) is not closed by a `}` while
     words are pending: the `}` is an ordinary word and the string stays
     undecidable. A `}` that is quoted, escaped or expanded, that is part of a
     larger word, or that is the target of a redirect closes no group.
     A lone `}` read after a rescued separator closes the enclosing `{` group.
     When the innermost open group is a provisional group, a standalone bare `}`
     rescues the chain of provisional groups there (the run of open provisional
     groups from the innermost outward) and closes the open group just outside
     the chain, provided all of these hold. The chain meets the condition of the
     rescue above, judged on the separators the reader read directly in its
     groups, never on the lookahead that located the ranges: the first direct
     separator of the innermost group is a `;` or a lone `&`, and an outer group
     with none of its own takes the separator of the one nested in it. The
     group just outside the chain is a `{` group (a plain brace group, the body
     of an anonymous function or the body of a function definition), not a `(`
     group and not the top level. And no word is pending, or words are pending
     and that `{` group lies within the body of an anonymous function, as for
     any other `}`; the pending words are then finalized first, as a command of
     that group. The `{` group is closed as a `; }` closes it: the commands read
     in the rescued groups are commands of that group, so a pipe or a stdin
     redirect attached to the group after its close reaches them, the words after
     the `}` of an anonymous body are its arguments, a word after the `}` of any
     other brace group makes the string undecidable, the commands of the body of
     a function definition are not judged, and a `)` after the `}` is a
     separator that closes an enclosing subshell. A `}` that does not meet these
     conditions is an ordinary word and changes no open group, no separator and
     no command; the string then stays undecidable if a group is left open.
     A `)` read while a provisional group is the innermost open group rescues
     the chain of provisional groups there and closes the `(` group just
     outside the chain, provided all of these hold; the word in progress is
     finished first, so a lone `}` finished there keeps its own reading. The
     chain meets the separator condition of the rescues above, judged on the
     separators the reader read directly in its groups: the first direct
     separator of the innermost group is a `;` or a lone `&`, and an outer group
     with none of its own takes the separator of the one nested in it. The group
     just outside the chain is a `(` group, not a `{` group and not the top
     level. The innermost group's case mark and inherited value are both 0
     (below). Words pending before the `)` never block the rescue; they
     become a command of the closed `(` group, exactly as the `)` of an ordinary
     subshell finalizes the words before it. The rescued groups are never
     closed, so the commands read in them are judged as commands of the closed
     `(` group: a pipe into that group and a stdin redirect after its close
     reach them, and they are not judged when that group, or a group around it,
     is the body of a function definition. Text after the `)` is outside the
     closed group, and a later `)` that finds no open `(` group is a separator,
     as anywhere else. A `)` that does not meet these conditions keeps its
     reading: it closes the innermost open group when that is a `(` group, and
     is otherwise a separator. A `)` inside quotes, inside a comment or taken
     into an argument range never reaches this reading.
     The case mark and the inherited value turn the `)` rescue off for a
     chain while either one is 1 or more. The case mark of a provisional group
     is the number of `case`s counted in it that no `esac` has closed yet; it is
     never negative. The reader counts a `case` when it appends one to a simple
     command while that group is the innermost open group, the `case` is at
     command position and it holds no quote, no escape and no expansion (it is
     bare): the mark goes up by 1. Command position is the first word of the
     simple command after the leading run of bare reserved words (`!`, `time`
     and the others, a bare `-p` right after a bare `time` included); a
     reserved word that holds a quote or an escape (a quoted `time`, an
     escaped `!`) is not in the run, the run ends at it, and the `case` after
     it is not at command position. A bare `esac` lowers the count while that
     group is the innermost open group, when it is at command position, or when
     it comes right after the three words `case` (counted as above), any one
     word and a bare `in` of the same simple command: the own case mark goes
     down by 1 when it is 1 or more, otherwise the inherited value goes down by
     1 when that is 1 or more, and nothing changes when both are 0. A quoted,
     escaped or expanded `case` or `esac`, one in any other position (an
     argument of another command), an `esac` on the line after `case x` (the
     newline starts a new simple command) and one in zsh's `case x { ... }` form
     (no bare `in`) change nothing. A
     provisional group opened inside a provisional group also takes the
     inherited value, fixed once when it opens from its parent alone: the
     parent's case mark plus the parent's inherited value at that moment, and 0
     when the parent is not provisional, so the count reaches the whole chain
     below the counting group without any walk over the groups around it. Later
     changes to the parent's values are not followed; the inherited value
     changes only through an `esac` read in the group itself, as above. The
     inherited value is a separate value from the one that blocks the part of a
     chain outside a group. A provisional group whose case mark or inherited
     value is 1 or more is not rescued at a `)`: the `)` is read as the
     terminator of a case pattern, it closes that provisional group itself
     instead of the `(` group outside the chain, and a stdin redirect after it
     reaches only that provisional group. A group whose two values are both 0,
     because it never counted a `case` or because `esac` returned them to 0,
     reads exactly like a group that was never marked, and a chain of such
     groups is rescued at a `)` as before. Neither value is read by the rescue
     at a lone `}` or by the rescue when input ends. The main reader does not
     track the terminators of case patterns in general, so a `)` that
     terminates a case pattern outside a provisional group keeps its reading.
  5. After `|` or `|&` the right side is awaited: a pending pipe survives
     newlines, blank lines, comment-only lines and heredoc bodies, and the
     next non-empty command is the right side. A newline after `&&` or `||`
     never creates a connection.
  6. For each simple command: drop redirections, skip leading variable
     assignments and the option-less wrappers (`env` `nohup` `nice` `exec`
     `command` `time` `sudo` `timeout DURATION`), and match the basename of
     the command word against the interpreter families below. A wrapper
     that carries an option (`env -i`, `nice -n 5`) -> the command is not
     judged.
  7. A shell (bash sh zsh dash ksh) reads `-c` as a flag: `-c` takes no
     value. The rest of its option bundle and the option words after it are
     read as options, letter by letter: an `i` anywhere is a launch with
     `-i`, and each `o` / `O` takes the next word as its value (so do
     `--rcfile` and `--init-file`). `--` or a lone `-` ends the options. With
     `-c`, the literal first operand is judged as a command string and
     inherits the standard input connection of the command that holds it; the
     words after it are positional parameters, never options. The literal
     first operand of a shell `-c` found inside a command string is judged
     too, at every level, with the same rules: the string is split into
     simple commands, and each is read and judged exactly as a command at the
     top level, wrappers and options included. Every such string has a kind,
     bash, zsh or unknown, that decides how its double-quoted command
     substitutions, the nested ones included, read `coproc` and `repeat`. The
     kind comes from the basename of the shell command word that directly holds
     the string, the word left after assignments, option-less wrappers and a
     path, matched the way the interpreter families are matched (the name itself,
     or the name followed only by digits and dots): `bash`, `bash5.2` and
     `/usr/bin/bash` are bash; `zsh`, `zsh5.9` and `/usr/bin/zsh` are zsh; `sh`,
     `dash`, `ksh` and their suffixed forms are unknown. Only the direct holder
     decides, so a `zsh -c` string inside a `bash -c` string is zsh, and the hook
     command itself is of unknown kind. In bash, `coproc` takes a NAME (the word
     after an ordinary word that follows `coproc` is at a command position) and
     `repeat` is an ordinary command name; in zsh, `coproc` takes no NAME (that
     ordinary word is the first word of a simple command and the words after it
     are arguments) and `repeat` is followed by a count and then a command
     position; a string of unknown kind is read with both the bash rule for
     `coproc` and the zsh rule for `repeat` (step 9 for the one re-read).
     Beside the kind, every such string has a delimiter reading, decided by the
     same direct holder and matched the same way (step 4 for the readings and
     their forms): `bash` and its suffixed and path forms read the bash form
     only, `zsh` and `dash` read the quote-removal form only, `sh` and `ksh`
     read both, and the hook command itself reads the quote-removal form only.
     The kind keeps deciding `coproc` and `repeat`, so the two axes differ for
     some shells: `dash` is of unknown kind with the quote-removal form only,
     and `sh` is of unknown kind with both readings.
     The connection passes down
     through every level, so a command inside a nested string is connected
     when the command that holds the string is. A string the reader cannot
     read (an unbalanced quote, an unterminated heredoc, an unclosed group, a
     string for which an unexpected error occurred while it was being read)
     is skipped and passes, and so does a dynamic operand; the walk goes on
     with the command after the one that holds it. That holds for a string
     with no checkpoint and for a string for which an unexpected error
     occurred. A string that stops at `_Undecidable` (an unbalanced quote, an
     unterminated heredoc, an unclosed group) is read as far as its last
     checkpoint (step 9): the commands up to the last checkpoint are judged,
     with the connection inherited from the command that holds the string,
     one level deeper, exactly as the commands of a string read in full; a
     string with no checkpoint gives no output, so nothing is left to judge
     and the walk goes on. Nested strings are walked with an explicit stack (a
     work list), never by recursion, so nesting depth costs no call-stack
     depth. The commands of a nested string are
     judged before the commands after the command that holds it, and the
     first launch to deny decides: no string after it is read. The
     characters re-read from second-level and deeper strings (the operands of
     a shell `-c` inside a first-level string or deeper, as the parser
     receives them after the quote removal of the level that holds them) are
     counted in one running total per hook command, up to 1,000,000
     characters (`NESTED_READ_LIMIT`). First-level strings are not counted
     and are always read; they are the operands of a shell `-c` in the
     command the hook receives. A string that proves undecidable counts at its
     full length, as it is counted before it is read. Once the next
     second-level or deeper string would pass the limit, it and every later
     second-level or deeper string pass unread. Passing the limit is never a reason to deny: the commands
     at the top level and in first-level strings are still judged. `-c`
     without an operand -> no output. Other interpreters keep their reading
     of `-c` `-m` `-e`.
  8. Deny a launch that carries `-i` before the first operand (python, node,
     the shells and lua), and a launch that gives the interpreter no program
     to run: no operand, no code option, standard input neither redirected
     nor connected, and no informational option. The informational short
     options belong to each interpreter: `-V` `-h` for python, lua, ruby,
     deno, irb and ipython, and `-V` `-h` `-v` for node and perl. The shells
     have no information short options, so a shell `-h` or `-V` is an
     ordinary flag. `--version` and `--help` are informational for all, and
     so are the long options an interpreter defines for itself.
  9. Anything undecidable or unexpected -> no output. The one exception is the
     part of an undecidable string that the reader finished before it stopped.
     A checkpoint is a newline that the reader itself reads at the top level,
     at which all of these hold: no group is open, no pipe is pending, no list
     continuation is pending (a trailing `&&` or `||` has not left the list
     open), and the heredoc bodies registered on that line have been read
     through their terminators. A newline inside quotes, a substitution chunk,
     an argument range or a heredoc body is never a checkpoint, nor is a
     backslash-newline pair, and a `;` or `&` is never one, so a launch on the
     line where the reading stops stays silent. When a string is undecidable,
     the commands up to the last checkpoint are judged, with connection and
     skip taken from the groups opened before it exactly as a full read sets
     them; a string with no checkpoint gives no output. The rule applies to
     the hook command and to every nested literal shell `-c` string, and an
     undecidable string counts at its full length toward NESTED_READ_LIMIT. An
     error other than _Undecidable is handled as before: a nested string is
     skipped, and the hook command gives no output. A string of unknown kind
     (the hook command and the `-c` string of a shell other than bash and zsh)
     that stops undecidable is read once more, with neither the bash rule for
     `coproc` nor the zsh rule for `repeat`: `coproc` followed by an ordinary
     word reads that word as the first word of a simple command, and `repeat` is
     an ordinary command name. When that re-read reaches the end of the string,
     its commands are the commands of the string; when it fails, with
     `_Undecidable` or with any other exception, the first read's `_Undecidable`
     and the commands that read settled up to its last checkpoint are used. A
     string of bash or zsh kind is never re-read, and a string is read at most
     twice under one delimiter reading.
     A string whose delimiter reading is both (the `-c` string of `sh` and `ksh`,
     step 4) is read under each reading on its own: reading A is the bash form
     and reading B is the quote-removal form, each applies one rule to the whole
     string (there is no combination per delimiter), and each runs the reading
     above, the re-read and the checkpoint rule included, so the string is read
     at most four times, each read in linear time. Reading B is skipped only when
     every parser built for reading A ended by returning or by raising
     `_Undecidable`, and none of them recorded a delimiter word whose two forms
     differ: B would read the string as A did. The rule of the two readings is
     that the dual reading denies when either reading denies. A reading read to
     its end adds its commands; a
     reading that stopped undecidable adds the commands up to its last
     checkpoint, so a reading that cannot be read does not hide a launch the
     other reading finds; a reading that raised any other exception adds
     nothing, and it does not discard what the other reading added. So no
     outcome of one reading suppresses the commands of the other. The result is
     the commands of reading A and then those of reading B; when either reading
     stopped undecidable it is the checkpoint rule's result for the string, and
     when both raised another exception the exception of reading A leaves,
     exactly as an unexpected error leaves today. A string read under both
     readings counts once, at its length, toward NESTED_READ_LIMIT, as one that
     is re-read does: it is counted before it is read, so the extra reads cost
     no budget. A nested string inside it is another matter: a nested string
     counts each time the walk reaches it in the commands of both readings, so
     one that both readings reach counts twice.

Everything the guard cannot positively identify passes. A misreading costs a
missed detection, never a stalled review. A string the reader cannot read to
its end is the one place where part of it is still read: the commands up to the
last checkpoint are judged, and a launch among them is denied; from there on
nothing is read, and a string with no checkpoint gives no output (step 9).

The guard uses only the standard library and touches no file, network
connection or child process. The decision depends on the command string
alone, never on the working directory or the environment.

Output: one deny object on stdout, or nothing. Exit status 0 either way.
"""

import json
import sys

HOOK_EVENT_NAME = "PreToolUse"

# Wrappers that run the next word as the command. Only option-free use is
# followed; a wrapper carrying an option makes the command undecidable.
WRAPPERS = ("env", "nohup", "nice", "exec", "command", "time", "sudo")

# Reserved words removed in front of the words before a `(`, so a function
# defined right after `then`, `do`, `!` and the like is still read as one.
RESERVED_WORDS = ("!", "do", "elif", "else", "if", "then", "time", "until", "while")

# The reserved words and symbols that leave the next word of a command list in a
# command substitution at a command position, when they are read as standalone
# words at a command position (`_Parser._skip_substitution`): the words that
# open a command (`then`, `do`, `{` and the like) and the closing words `fi`,
# `done` and `}`, which close a compound command.
COMMAND_POSITION_WORDS = (
    "then", "do", "else", "elif", "if", "while", "until", "time", "!", "{", "fi", "done", "}",
)

# The head state a command list keeps (`_Parser._skip_substitution`), one value
# out of this small fixed set: no head; the first word of a simple command was
# read at a command position (a `name()` may follow); `function` was read (the
# next word is the name, or an empty `()` follows); the function name was read
# (an empty `()` may follow); `for` was read (the next word is the name, or a `((` follows); the
# `for` name was read (a zsh word list may follow); `select` or `repeat` was
# read (the next word is an ordinary word; `repeat` starts this state only under
# the zsh repeat rule, `_Parser.zsh_repeat`); `coproc` was read (the next word is
# at a command position and, under the coproc NAME rule, `_Parser.coproc_name`,
# may be a NAME).
HEAD_NONE = 0
HEAD_FIRST = 1
HEAD_FUNCTION = 2
HEAD_FUNCTION_NAME = 3
HEAD_FOR = 4
HEAD_FOR_NAME = 5
HEAD_NAME = 6
HEAD_COPROC = 7

# The head words, standalone and read at a command position, and the head state
# each one starts. `function`, `for`, `select` and `coproc` are head words in
# every reading. `repeat` is a head word only under the zsh repeat rule
# (`_Parser.zsh_repeat`); without the rule it is an ordinary command word. What
# follows `coproc` depends on the coproc NAME rule (`_Parser.coproc_name`): with
# the rule an ordinary word after `coproc` is a NAME and the word after it is at a
# command position, without it that word is the first word of a simple command
# and the words after it are arguments.
HEAD_AFTER_WORD = {
    "function": HEAD_FUNCTION,
    "for": HEAD_FOR,
    "select": HEAD_NAME,
    "coproc": HEAD_COPROC,
    "repeat": HEAD_NAME,
}

# The kind of the shell that holds a string, which decides the two rule switches
# of the parser that reads it (`_Parser`, the module-level `parse`): the shell
# is bash, is zsh, or is not known. The hook command and the strings of every
# other shell (`sh`, `dash`, `ksh`) are of unknown kind. The same holder decides
# a second, separate value, the delimiter reading (below): `dash` is of unknown
# kind with quote removal only, `sh` is of unknown kind with both readings.
KIND_BASH = "bash"
KIND_ZSH = "zsh"
KIND_UNKNOWN = "unknown"

# The two rule switches each kind reads with: (the coproc NAME rule, the zsh
# repeat rule). A string of unknown kind is read first with both rules, and when
# that stops undecidable it is read once more with neither rule.
KIND_SWITCHES = {
    KIND_BASH: (True, False),
    KIND_ZSH: (False, True),
    KIND_UNKNOWN: (True, True),
}

# The delimiter reading of a string: how the `${ ... }` ranges of the word read
# as the target of `<<` or `<<-` are registered. It is a second axis beside the
# kind, decided by the same direct holder (`_delimiter_reading`) and handed to
# the parse driver with the kind: the bash form (each range registered as it is
# written), quote removal (each range registered with its quotes removed, the
# reading before the bash form existed), or both (a string held by `sh` or
# `ksh`, whose rule is not known: it is read under the bash form first and then
# under quote removal, and denied when either reading denies). A parser is built
# for one of the first two (`_Parser.delimiter_rule`); "both" is a driver value
# only. The default everywhere is quote removal, so the hook command itself, a
# string held by `zsh` or `dash`, and every caller that names no reading read
# as they always did.
DELIMITER_BASH_FORM = "bash form"
DELIMITER_QUOTE_REMOVAL = "quote removal"
DELIMITER_BOTH = "both"

# How far the simple command in progress has read the shape `case`, one word,
# `in`, which lets an `esac` right after it lower the case mark
# (`_Parser.case_shape`): nothing of it, a `case` that raised the mark, that
# `case` and the one word after it, and those two and a bare `in`.
CASE_SHAPE_NONE = 0
CASE_SHAPE_CASE = 1
CASE_SHAPE_SUBJECT = 2
CASE_SHAPE_IN = 3

# A word that ends in one of these is no function name: `f?()` and the like are
# extglob patterns, not definitions, so the group after the `()` is judged.
EXTGLOB_OPERATORS = ("?", "*", "+", "@", "!")

# Long informational options that never open a REPL. Every family shares
# these; the short informational options belong to each family (info_letters).
INFO_LONG = ("--version", "--help")

# The characters the traversal re-reads from the literal shell `-c` strings of
# the second level and deeper, per hook command. A string's length is the
# length of its value as handed to the parser, after the holding level's quote
# removal; a string that proves undecidable counts at its full length.
# First-level strings are never counted.
NESTED_READ_LIMIT = 1000000

# The work, per character of the string being parsed, the parser may spend
# locating the `(`...`)` ranges among the arguments of anonymous functions and
# checking them for separators. The first range may span the whole string, so
# the cap never falls below one scan; once it is spent every later `(` opens a
# group, as before ranges were read.
PAREN_SCAN_FACTOR = 4

# The work, per character of the string being parsed, the substitution skip
# (`_Parser._skip_substitution`) may spend reading text a second time: when a
# command-position `((` read as an arithmetic command does not close with `))`,
# the reader goes back to that `((` and reads it as two nested subshells, once
# per `((`. The characters read again, summed over all the skips of one parser,
# may not exceed this many times the length of the string; the skip that would
# exceed it stops undecidable. The total work stays within a constant times the
# length of the string.
ARITHMETIC_REREAD_FACTOR = 8

# The first direct separators that rescue a provisional group: a `;` and a lone
# `&`. Any other first separator (a newline, `&&`, `||`, `|`, `|&`) leaves the
# group unrescued.
RESCUE_SEPARATORS = (";", "&")

# The separators that end the comment exception of a group
# (`_Group.comment_exception`) when the reader itself reads one while that group
# is the innermost open group: a `;`, a lone `&`, `&&`, `|&` and a newline. A `|`
# and `||` are no member, and the redirections `&>` and `>&`, a quoted separator
# and a backslash-escaped one never reach the reader's separator handling.
COMMENT_EXCEPTION_ENDERS = (";", "&", "&&", "|&", "\n")


class _Undecidable(Exception):
    """The string cannot be read to its end. `checkpoint_commands` holds the
    simple commands the reader settled up to its last checkpoint
    (`_Parser.parse`): the reader sets it when the exception leaves its parse
    method, and it stays an empty tuple for a string with no checkpoint. Every
    raise site raises the exception with a reason text only."""

    checkpoint_commands = ()


def _rescue_separator(own, inherited=None):
    """The separator by which a provisional group is rescued, or None when it is
    not. This is the one definition of the separator condition: the rescue when
    input ends (`_rescue_argument_groups`), the rescue at a lone `}`
    (`_Parser._close_after_rescue`, with the values `_Parser._mark_provisional`
    fixes) and the rescue at an unquoted `)`
    (`_Parser._close_paren_after_rescue`, with the same values) all apply it, so
    the three cannot drift apart.

    `own` is the first separator read directly in the group, or None while there
    is none. A group with none of its own takes `inherited`, the separator of
    the group nested in it, which was rescued before it. Only `;` and a lone `&`
    (RESCUE_SEPARATORS) rescue. The innermost group of a chain has nothing to
    inherit, so it needs a separator of its own."""
    first = own if own is not None else inherited
    return first if first in RESCUE_SEPARATORS else None


class _Family:
    """One interpreter family.

    names              known command names (FR8 adds a digits-and-dots suffix)
    deny_i             `-i` opens a REPL, so a launch carrying it is denied
    interactive_long   long options that count as `-i`
    code_letters       short options that pass the program as their value
    code_long          long options that pass the program as their value
    value_letters      short options that take a value (the rest of the
                       bundle, or the next word when last). The shells read
                       a bundle one letter at a time instead: each of these
                       letters takes the next word
    attached_letters   short options whose rest of the bundle is a value, and
                       which never take the next word
    value_long         long options that take the next word as their value
    info_letters       informational short options of this interpreter; they
                       never open a REPL. The shells have none, so a shell
                       `-h` or `-V` is an ordinary flag
    info_long          extra informational long options (`--version` and
                       `--help` are shared by every family)
    """

    def __init__(
        self,
        name,
        names,
        deny_i=False,
        interactive_long=(),
        code_letters="",
        code_long=(),
        value_letters="",
        attached_letters="",
        value_long=(),
        info_letters="",
        info_long=(),
        is_shell=False,
    ):
        self.name = name
        self.names = names
        self.deny_i = deny_i
        self.interactive_long = interactive_long
        self.code_letters = code_letters
        self.code_long = code_long
        self.value_letters = value_letters
        self.attached_letters = attached_letters
        self.value_long = value_long
        self.info_letters = info_letters
        self.info_long = info_long
        self.is_shell = is_shell


FAMILIES = (
    _Family("python", ("python",), deny_i=True, code_letters="cm", value_letters="WX",
            value_long=("--check-hash-based-pycs",), info_letters="Vh"),
    _Family("node", ("node",), deny_i=True, interactive_long=("--interactive",),
            code_letters="ep", code_long=("--eval", "--print"), value_letters="rC",
            value_long=("--require", "--import", "--loader", "--experimental-loader", "--conditions"),
            info_letters="Vhv", info_long=("--test", "--check", "--run")),
    _Family("shell", ("bash", "sh", "zsh", "dash", "ksh"), deny_i=True, code_letters="c",
            value_letters="oO", value_long=("--rcfile", "--init-file"), info_letters="",
            is_shell=True),
    _Family("lua", ("lua",), deny_i=True, code_letters="cme", value_letters="l", info_letters="Vh"),
    _Family("ruby", ("ruby",), code_letters="e", value_letters="Ir", attached_letters="i0xKFW",
            info_letters="Vh"),
    _Family("perl", ("perl",), code_letters="eE", value_letters="IMm", attached_letters="i0xFCdD",
            info_letters="Vhv"),
    _Family("deno", ("deno",), code_letters="cme", info_letters="Vh"),
    _Family("irb", ("irb",), code_letters="cme", info_letters="Vh"),
    _Family("ipython", ("ipython",), code_letters="cme", info_letters="Vh"),
)

DIGITS = "0123456789"

# The largest file descriptor number, as text: a digit-only word of ten digits
# is an fd when it is not greater than this as a string.
MAX_FD = "2147483647"


class _Word:
    __slots__ = ("text", "dynamic", "bare")

    def __init__(self, text, dynamic, bare):
        self.text = text
        # True when the word holds an expansion, so its value is unknown.
        self.dynamic = dynamic
        # True when the word holds no quote, no escape and no expansion.
        self.bare = bare


class _Command:
    __slots__ = ("words", "stdin", "after_pipe", "group")

    def __init__(self, words, stdin, after_pipe, group):
        self.words = words
        # Standard input is redirected with `<`, `<<`, `<<<` or `<&`.
        self.stdin = stdin
        # The command sits on the right side of a pipe.
        self.after_pipe = after_pipe
        # The innermost group that holds the command, or None.
        self.group = group


class _Group:
    """A subshell `( ... )` or a brace group `{ ...; }`.

    kind       "(" or "{"
    parent     the group that holds this one, or None
    pipe       the group is the right side of a pipe
    stdin      a stdin redirect follows the close of the group
    skip       the group is a function body: defined here, run elsewhere
    head       the words right before the `(` are a function name: `name(` or
               `function name(`, where `name` is one word that is not dynamic
               and holds no `=`. A word whose content, after quote removal,
               ends in one of the extglob operator characters `?` `*` `+` `@`
               `!` is no name, so the group after its `()` is judged. The words
               are judged after the leading run of the reserved words `!` `do`
               `elif` `else` `if` `then` `time` `until` `while` is removed, and
               a non-dynamic `-p` right after `time` is removed with it. When
               nothing remains, the original words are judged. The "one word"
               and "`function` and one word" counts are the words left after
               the removal. When the one word left is `function` and it holds
               no quote, no escape and no expansion, it is no name: the group
               after its `()` is judged (a zsh anonymous function). A later
               empty `()` makes the group that follows a function body
    anon       a zsh anonymous function. On a `{` group: the group is an
               anonymous body, so the words after its `}` are arguments, not
               commands and not a reason to call the string undecidable. On a
               `(` group: its empty `()` is the head of an anonymous function
               (one `function` that holds no quote, no escape and no expansion
               once the leading reserved words are removed, or no word at
               all), and the brace group that follows the `()` is the
               anonymous body
    anon_pipe  on a `(` group with `anon`: the head is on the right side of a
               pipe, and the anonymous body takes it as its `pipe`, so the
               pipe connection comes from the head and reaches the body alone;
               the `pipe` of the `(` group itself keeps its own reading. A body
               opened by the parenless `function {` takes the pipe state of
               the simple command that holds the `function`
    anon_stdin on a `(` group with `anon`: a stdin redirect was read in the head
               before the `(`, and the anonymous body takes it as its
               `head_stdin`. The `(` group itself is not connected by it
    head_stdin on an anonymous `{` body: a stdin redirect was read in the head
               before the body, so the body is connected. The head is the
               simple command up to the body: a redirect before `function`,
               between `function` and the `{` of the parenless form, or before
               the `(` of the `()` (it comes from the `(` group's `anon_stdin`,
               however many newlines lie between the `()` and the `{`). A
               redirect between the `()` and the `{` is not part of the head.
               No other group has it; the groups nested in the body are
               connected through the body, by the rule of `connected`
    in_anon    the group lies within an anonymous-function body: it is that body
               itself, or the innermost group open when it opened lies within
               one. The value is fixed once, when the group opens, inherited from
               the innermost group open at that moment (a `(` group, a `{` group
               and the body of a function definition alike, at any depth), and
               never recomputed or derived by walking the enclosing groups, so
               reading it at a `}` takes constant time. A standalone bare `}`
               closes a `{` group that has it while words are pending
    size       (commands, groups) counted when the group opened, itself included
    connected  settled once the whole command is read: the group, or a group
               that holds it, has its standard input connected, by a pipe, by a
               stdin redirect after its close, or (an anonymous body) by a stdin
               redirect in its head. A string that stops at `_Undecidable` has
               it settled the same way for the groups opened before its last
               checkpoint (`_Parser._settle_groups`)
    skipped    settled likewise: the group, or a group that holds it, is a
               function body
    provisional  the group was opened at a `(` among the arguments of an anonymous
               function (`_read_argument_parens`); every other group is genuine.
               A provisional group may be rescued on three occasions: when input
               ends with it still open, when a lone `}` closes the `{` group just
               outside the chain of provisional groups it ends
               (`_Parser._close_after_rescue`), and when an unquoted `)` closes
               the `(` group just outside that chain
               (`_Parser._close_paren_after_rescue`); no other group ever is
    first_sep  on a provisional group: the first separator the reader met while
               the group was the innermost open group, as the text of that
               separator (`;`, `&`, `&&`, `||`, `|`, `|&` or a newline), or None
               while there is none. Later separators do not change it, and a
               separator met inside a group nested in this one is not recorded
               here. A redirection (`&>`, `>&`), a quoted `;` or `&` and a
               backslash-escaped one are no separator
    chain_base on a provisional group: the open group just outside the chain of
               provisional groups this group ends, that is, the nearest open
               ancestor that is not provisional, or None when the chain reaches
               the top level. A `}` rescues the chain only when it is a `{` group,
               and a `)` only when it is a `(` group
    outer_blocked  on a provisional group: the part of that chain outside this
               group cannot be rescued, because an enclosing provisional group has
               a first separator that does not rescue (`_rescue_separator`) or is
               itself blocked. Both chain values are fixed once, when the group
               opens, from the values of its parent alone (`_Parser._mark_provisional`):
               while this group is open its parent reads no direct separator, so
               the parent's part cannot change, and a `}` or a `)` reads them in
               constant time without walking the groups around it
    case_mark  on a provisional group: the case mark, the number of `case`s
               counted in the group that no `esac` has closed yet, never
               negative. The reader adds 1 when it appends a bare `case` to a
               simple command at command position while the group is the
               innermost open group, and takes 1 off when it appends a bare
               `esac` at command position, or right after a counted `case`, any
               one word and a bare `in` of the same simple command
               (`_Parser._append_word`), as long as the mark is 1 or more;
               otherwise an `esac` lowers `case_inherited` instead.
               Command position is the first word after the leading run of bare
               reserved words (`!`, `time` and the others, a bare `-p` right
               after a bare `time` included); a reserved word that holds a quote
               or an escape is not in the run. A quoted, escaped or expanded
               `case` or `esac` and one in any other position change nothing. A
               `)` is not a rescue for a group whose mark is 1 or more: the `)`
               is read as the terminator of a case pattern and closes the
               provisional group itself (`_Parser._closes_paren_after_rescue`).
               A mark of 0 reads like a group that was never marked. The brace
               rescue never reads it
    case_inherited  on a provisional group: the inherited value, a value separate
               from `outer_blocked` and from `case_mark`, fixed when the group
               opens, from the values of its parent alone
               (`_Parser._mark_provisional`): the parent's `case_mark` plus the
               parent's `case_inherited` at that moment when the parent is
               provisional, 0 otherwise. It is a snapshot of the parent's two
               values, so it carries the count down the chain in constant time
               with no walk over the groups around it, and it does not follow
               later changes to the parent's values. It goes down by 1 when an
               `esac` is read in the group itself (at the positions given for
               `case_mark`) while `case_mark` is 0 and it is 1 or more; it is
               never negative. A group whose `case_inherited` is 1 or more is
               treated as one whose `case_mark` is 1 or more at a `)`. The brace
               rescue never reads it
    comment_exception  the group has the comment exception: while it is the
               innermost open group, an unquoted `#` at word start is a word
               character, not the start of a comment, and the characters after
               it join the word as in any other word. It is fixed when the group
               opens: `_read_argument_parens` sets it for a range that has a
               matching `)`, holds no unquoted `;`, `&` or newline and holds a
               backquote, and a group opened while the innermost open group has
               it starts with it, whatever its own opening condition (a `(`
               group, a `{` group or a provisional group alike), the value
               copied once from the parent at that moment. Every other group
               starts without it and reads a `#` at word start as a comment.
               Reading a direct separator ends it: a `;`, a lone `&`, `&&`,
               `|&` or a newline that the reader itself reads while a group with
               the comment exception is the innermost open group clears it for
               that group for good (`_Parser._separator`); `|`, `||`, `&>`, `>&`,
               a quoted separator and a backslash-escaped separator clear
               nothing, and a separator read inside a nested group never changes
               an outer group. When a group closes its value goes with it and
               the value of its parent applies again. This is the single
               exception to the earlier assumption that group reading adds no
               new reading. Only the innermost group is read when a separator or
               a `#` is read, so the check takes constant time
    """

    __slots__ = (
        "kind", "parent", "pipe", "stdin", "skip", "head", "anon", "anon_pipe", "anon_stdin",
        "head_stdin", "in_anon", "size", "connected", "skipped", "provisional", "first_sep",
        "chain_base", "outer_blocked", "case_mark", "case_inherited", "comment_exception",
    )

    def __init__(
        self, kind, parent, pipe, skip, head, size, anon=False, anon_pipe=False, anon_stdin=False,
        head_stdin=False, in_anon=False, comment_exception=False,
    ):
        self.kind = kind
        self.parent = parent
        self.pipe = pipe
        self.stdin = False
        self.skip = skip
        self.head = head
        self.anon = anon
        self.anon_pipe = anon_pipe
        self.anon_stdin = anon_stdin
        self.head_stdin = head_stdin
        self.in_anon = in_anon
        self.size = size
        self.connected = False
        self.skipped = False
        self.provisional = False
        self.first_sep = None
        self.chain_base = None
        self.outer_blocked = False
        self.case_mark = 0
        self.case_inherited = 0
        self.comment_exception = comment_exception


class _Parser:
    """Split a command string into simple commands.

    Quotes, backslashes, comments, redirections and heredocs are read the way
    a shell reads them. Expansions are not evaluated: a word that holds one
    is marked dynamic. Groups (subshells and brace groups) are tracked on a
    stack, never by recursion, so any nesting depth is read in linear time.
    Raises _Undecidable on an unbalanced quote or group, an unclosed command
    substitution inside double quotes, or an unterminated heredoc.

    A string that raises _Undecidable is not lost whole: the reader records
    checkpoints while it reads. A checkpoint is a newline that the reader itself
    reads at the top level, at which all of these hold: no group is open, no pipe
    is pending, no list continuation is pending (a trailing `&&` or `||` has not
    left the list open), and the heredoc bodies registered on that line have been
    read through their terminators. A newline inside quotes, a substitution
    chunk, an argument range or a heredoc body is never a checkpoint, nor is a
    backslash-newline pair, and a `;` or `&` is never one. When a string is
    undecidable, the commands up to the last checkpoint are judged, with
    connection and skip taken from the groups opened before it exactly as a full
    read sets them; a string with no checkpoint gives no output. The rule applies
    to the hook command and to every nested literal shell `-c` string, and an
    undecidable string counts at its full length toward NESTED_READ_LIMIT. An
    error other than _Undecidable is handled as before: a nested string is
    skipped, and the hook command gives no output.

    The reader keeps the last checkpoint as two counts, the simple commands and
    the groups recorded so far, never a copy of a list, so a newline costs
    constant time. The list continuation is a state of its own: it is set when
    `&&` or `||` is read. It is cleared when a simple command with words is
    finished, when a group opens, when a separator other than a newline is
    read, when a separator ends a simple command that held a redirection (a
    line of only redirections included), and when a `)` that closes a `(` group
    ends a simple command that held a redirection. A newline that ends an empty
    command with no redirection (a blank line or a comment-only line) and a
    heredoc body leave it as it was. The pending pipe persists in the same way.
    When _Undecidable leaves `parse`, the method settles `connected` and
    `skipped` of the groups opened before the last checkpoint with the one rule
    a full read applies (`_settle_groups`), each group visited once, attaches
    the first commands, as many as the checkpoint counted, to the exception
    (`_Undecidable.checkpoint_commands`, an empty tuple when there is no
    checkpoint) and raises the same exception again. It neither catches nor
    alters any other exception, and a string read in full returns the commands
    as before.

    Among the arguments of an anonymous function, a `(` is read with its range
    up to the matching `)` as part of one argument word (`_read_argument_parens`),
    unless the range holds an unquoted `;`, `&` or newline, or a backquote (one
    inside double quotes included), or no matching `)` is found: then the `(`
    opens a group, as it did before ranges were read. A backquote that a
    backslash escapes, or that sits in single quotes, does not count. The work
    spent on these ranges is capped at PAREN_SCAN_FACTOR times the length of
    the string, so a string made of ranges that each hold a `;` and nest another
    anonymous function is read in linear time. Once the cap is spent, every later
    `(` opens a group.

    A group opened at such a `(` is provisional (`_Group.provisional`), and the
    first separator the reader meets while it is the innermost open group is kept
    on it (`_Group.first_sep`). A provisional group is rescued if that first
    direct separator is a `;` or a lone `&`: its `(` is read as an argument-word
    character, the group ends at that separator, and the commands after that
    separator are judged as following the anonymous function. The rescue is made
    in three places, and all apply the one separator condition
    (`_rescue_separator`). When input ends, a provisional group that was never
    closed is rescued (`_rescue_argument_groups`). A lone `}` read while a
    provisional group is the innermost open group rescues the chain of
    provisional groups there, from the innermost outward, when the chain meets
    the condition and the open group just outside it is a `{` group
    (`_close_after_rescue`). A lone `}` read after a rescued separator closes the
    enclosing `{` group. A `)` read while a provisional group is the innermost
    open group rescues the chain of provisional groups there and closes the `(`
    group just outside the chain, when the chain meets the condition and that
    group is a `(` group (`_closes_paren_after_rescue`,
    `_close_paren_after_rescue`); words pending before the `)` never block it,
    they become a command of the closed group, and a later `)` that finds no
    open `(` group is a separator. Provisional groups nested in each other are
    rescued from the inside out, and an outer one with no separator of its own
    takes the separator of the inner one as its first. A newline as the first
    direct separator is not rescued. A group that is genuinely unclosed still
    yields no output: a group that is not provisional and is left open, and a
    provisional group that is not rescued, raise _Undecidable, which falls under
    the checkpoint rule above. A `}` that does not qualify is an ordinary word
    and changes no open group, no separator record and no command. Each
    provisional group is removed once, and the check at a `}` or a `)` reads
    values fixed when the group opened (`_Group.chain_base`,
    `_Group.outer_blocked`), so it costs constant time and the whole reading
    stays linear in the length of the string.

    The `)` rescue has one exception, the case mark. The case mark
    (`_Group.case_mark`) of a provisional group is the number of `case`s counted
    in it that no `esac` has closed yet. When the reader appends a bare `case`
    to a simple command while a provisional group is the innermost open group,
    and the `case` is at command position (the first word of the command after
    the leading run of bare reserved words; a reserved word that holds a quote
    or an escape is no part of the run), the mark goes up by 1 (`_append_word`).
    A bare `esac` at command position, or right after a counted `case`, any one
    word and a bare `in` of the same simple command, takes 1 off the own mark
    when it is 1 or more, and otherwise 1 off the inherited value when that is 1
    or more; the state for the run of bare reserved words and for that shape is
    kept apart from the state `_names_function` and `_names_anonymous_function`
    read, and a new simple command begins it over (`_start_words`). A provisional
    group opened inside a provisional group takes the inherited value
    (`_Group.case_inherited`) once, when it opens, from its parent alone: the
    parent's case mark plus the parent's inherited value (`_mark_provisional`),
    so the count runs down the chain without any walk. A group whose case mark
    or inherited value is 1 or more is not rescued at a `)`
    (`_closes_paren_after_rescue`): the `)` ends a case pattern there, so it
    closes that provisional group itself and not the `(` group outside the
    chain, and a stdin redirect after it reaches only that group. A group whose
    two values are both 0 is read exactly like one that was never marked. Both
    values are kept apart from `_Group.outer_blocked`, and the rescue at a lone
    `}` and the rescue when input ends never read them. Counting costs constant
    time per appended word, inheriting constant time per opened group and the
    check constant time per `)`, with no recursion. The main reader does not
    track the terminators of case patterns in general.

    The group opened for a range that has a matching `)`, holds no unquoted `;`,
    `&` or newline and holds a backquote has the comment exception: while it is
    the innermost open group, an unquoted `#` at word start is a word character,
    not the start of a comment, and the characters after it join the word as in
    any other word, so a `)` after it still closes the group. The scan that
    finds the range still gives a backquote and a comment no special reading;
    the exception belongs to the reading of the group opened after it. A group
    opened while the innermost open group has the comment exception starts with
    it, whatever its own opening condition: the value is copied once, when the
    group opens, and a group that closes takes its value with it, so the value
    of its parent applies again. Reading a direct separator ends it: a `;`, a
    lone `&`, `&&`, `|&` or a newline that the reader itself reads while a group
    with the comment exception is the innermost open group clears it for that
    group for good, and a `#` at word start is a comment there as before; `|`,
    `||`, `&>`, `>&`, a quoted separator and a backslash-escaped separator clear
    nothing, and a separator read inside a nested group never changes an outer
    group. This is the single exception to the earlier assumption that group
    reading adds no new reading: a `#` at word start stays a comment outside
    every group, in a group opened at a `;`, `&` or newline, in a group opened
    because no matching `)` is found and in a group whose exception was cleared,
    a `#` inside `$(` is read as before, and a `#` in the middle of a word is a
    word character as ever.

    Two switches, set when the parser is built and fixed for its life, decide how
    `coproc` and `repeat` are read inside a double-quoted command substitution
    (`_skip_substitution`): the coproc NAME rule (`coproc_name`) and the zsh
    repeat rule (`zsh_repeat`). They are parser-wide and never part of a stacked
    entry, so the substitutions nested in the string and the quote removal of a
    delimiter range, which use this same parser, read with the same switches. The
    module-level `parse` builds the parser from the kind of the shell that holds
    the string:

      bash                   NAME rule on   zsh repeat rule off
      zsh                    NAME rule off  zsh repeat rule on
      unknown, first read    NAME rule on   zsh repeat rule on
      unknown, re-read       NAME rule off  zsh repeat rule off

    With the NAME rule on, the ordinary word after `coproc` is a NAME and the word
    after it is at a command position (`coproc c {`); with it off, that word is
    the first word of a simple command and the words after it are arguments
    (`coproc echo case x in x` opens no case statement). With the zsh repeat rule
    on, `repeat` read as a standalone, bare word at a command position is a head
    word (`repeat 1 {`); with it off, `repeat` is an ordinary command word, the
    first word of a simple command, and the words after it are arguments
    (`repeat x case y in y` opens no case statement). `select`, `for` and
    `function` are read the same way in every reading. The module-level `parse`
    reads a string of unknown kind a second time with both rules off when the
    first read stops undecidable.

    A third switch, the delimiter rule (`delimiter_rule`), is set the same way
    and fixed for the parser's life: it decides which form of a heredoc delimiter
    word is registered. A delimiter word has two forms (`_finish_word`). The
    quote-removal form is the text registered before the bash form existed. The
    bash form differs from it only when the word holds at least one `${ ... }`
    range and no quote unit outside its ranges, and then each range contributes
    its original characters (`_remove_range_quotes`). A parser built with the
    bash form registers the bash form; a parser built with quote removal, the
    default, registers the quote-removal form. Either parser records that the
    word "differs" (`differs`) when its two forms are unequal; the module-level
    `parse` reads that record to decide whether a string held by `sh` or `ksh`
    needs its second reading. The delimiter rule never changes how anything
    other than a delimiter word is read, and never changes the kind switches:

      bash form              the `${ ... }` ranges of a delimiter are registered
                             as written, when the word has no quote unit outside
                             its ranges
      quote removal          the ranges are registered with their quotes removed

    The word in progress keeps three things for it besides its text: the same
    word with the bash form of each `${ ... }` range (`bash_buf`), whether it
    holds such a range (`has_range`), and whether a quote unit outside its ranges
    was read (`outside_quote`). A quote unit is a `'`, `"` or backslash unit read
    for the word, one inside a parenthesised argument range included; a
    backslash-newline pair is no unit, and neither is a `$( ... )` or backquote
    span written directly in the word nor the quotes inside it.
    """

    def __init__(
        self,
        command,
        coproc_name=True,
        zsh_repeat=True,
        delimiter_rule=DELIMITER_QUOTE_REMOVAL,
    ):
        self.s = command
        self.n = len(command)
        # The two rule switches, fixed for the life of the parser and read by the
        # substitution skip at the head words `coproc` and `repeat`: the coproc
        # NAME rule and the zsh repeat rule (see the class description).
        self.coproc_name = coproc_name
        self.zsh_repeat = zsh_repeat
        # The third switch, fixed for the life of the parser and read where a
        # heredoc delimiter is registered (`_finish_word`): DELIMITER_BASH_FORM
        # registers the bash form of the delimiter word, DELIMITER_QUOTE_REMOVAL
        # (the default) registers the quote-removal form.
        self.delimiter_rule = delimiter_rule
        # A delimiter word was registered whose bash form and quote-removal form
        # are unequal. The module-level `parse` reads it after the parse.
        self.differs = False
        self.i = 0
        self.commands = []
        self._start_words()
        self.stdin = False
        self.pipe_pending = False
        # The characters the parser may still spend locating `(`...`)` ranges
        # among the arguments of anonymous functions.
        self.paren_budget = PAREN_SCAN_FACTOR * self.n
        # The characters the substitution skip may still read a second time,
        # when a command-position `((` read as an arithmetic command is read
        # again as two nested subshells.
        self.arith_budget = ARITHMETIC_REREAD_FACTOR * self.n
        # Set between a redirection operator and its target word:
        # (is_heredoc, strips_leading_tabs).
        self.redirect = None
        self.heredocs = []
        # A redirection was met in the simple command in progress.
        self.redirected = False
        # Open groups, innermost last, and every group in the order it opened.
        self.frames = []
        self.groups = []
        # A `&&` or `||` was read and nothing has ended it since: the list is
        # still open, so a newline is no checkpoint. A simple command with words,
        # a group opening, a separator other than a newline, a separator that
        # ends a simple command holding a redirection and a `)` that closes a
        # `(` group after such a command end it. An empty command with no
        # redirection (a blank line, a comment-only line) and a heredoc body
        # leave it as it was.
        self.list_pending = False
        # The last checkpoint, as two counts: (simple commands, groups) recorded
        # when the reader read its newline. Only the counts are kept, never a
        # copy of a list, so a newline costs constant time.
        self.checkpoint = (0, 0)
        # The group closed last, while only redirections have followed it (and,
        # for an anonymous body, its arguments, a `(`...`)` range among them
        # included).
        self.after_group = None
        # A `name()` was just read: the next group is the body of a function.
        self.fn_head = False
        # The empty `()` of an anonymous-function head was just read: the `(`
        # group of that `()`. The next brace group is the anonymous body.
        self.anon_head = None
        self._reset_word()

    def _start_words(self):
        """Begin a simple command with no word. The reserved-run state below
        is what `_names_anonymous_function` reads; `_append_word` keeps it.

        The state for the case mark is begun here too, apart from the reserved-run
        state: the run of bare reserved words that precedes command position,
        and the shape `case`, one word, `in` that lets an `esac` lower the case
        mark. A new simple command (after a `;`, a newline, a `)` and the like)
        starts both over, so an `esac` on a line after `case x` is neither at
        command position nor right after `in`."""
        self.words = []
        # Every word so far is removed by the leading reserved-run removal.
        self.run_open = True
        # The last word appended was a `time` that was removed, so a
        # non-dynamic `-p` right after it is removed too.
        self.after_time = False
        # The words so far are the removed run and then exactly one bare
        # `function`.
        self.lone_function = False
        # Every word so far is a bare reserved word, or a bare `-p` right after
        # a bare `time`: the next word that is not one is at command position.
        self.bare_run_open = True
        # The last word appended was a bare `time` of that run.
        self.bare_after_time = False
        # How far the shape `case`, one word, `in` has been read.
        self.case_shape = CASE_SHAPE_NONE

    def _append_word(self, word):
        """Append a word to the simple command and keep the reserved-run state
        in step with it. The state follows the removal `_names_function`
        applies: a word of RESERVED_WORDS that is not dynamic, and a
        non-dynamic `-p` right after a removed `time`, stay in the run; the
        first other word ends it.

        The case mark (`_Group.case_mark`, the number of `case`s that no `esac`
        has closed yet) is kept in step here, from separate state: the run of
        bare reserved words (`bare_run_open`, `bare_after_time`) and the shape
        `case`, one word, `in` (`case_shape`). A word stays in the bare run when
        it is a word of RESERVED_WORDS or a `-p` right after such a `time`
        and holds no quote, no escape and no expansion (`bare`); a quoted or
        escaped `time` or `!` is not counted, and the run ends at it. The first
        word after the run is at command position. The mark changes only while
        the innermost open group is a provisional group, and the change lands on
        that group:

        - A bare `case` at command position raises the mark by 1 and starts the
          shape.
        - A bare `esac` lowers it by 1 when it is at command position, or when
          it comes right after the three words of the shape in the same simple
          command: a counted `case`, any one word and a bare `in`. If the own
          mark is 1 or more it goes down by 1; otherwise the inherited value
          (`_Group.case_inherited`) goes down by 1 when it is 1 or more; if both
          are 0 nothing changes, so neither value is ever negative.
        - Any other word advances the shape or ends it: after a counted `case`
          any word is the one word, after it only a bare `in` goes on, and after
          the `in` any word other than a lowering `esac` ends it.

        A quoted, escaped or expanded `case` or `esac`, one in any other position
        (an argument of another command), an `esac` on the line after `case x`
        (the newline starts a new simple command) and one in zsh's brace form
        `case x { ... }` (no bare `in`) change nothing. A group whose mark and
        inherited value are both 0 reads like one that was never marked. A `)`
        is not a rescue for a group whose mark or inherited value is 1 or more
        (`_closes_paren_after_rescue`). Constant time per word."""
        if self.run_open:
            if self.after_time and not word.dynamic and word.text == "-p":
                self.after_time = False
            elif not word.dynamic and word.text in RESERVED_WORDS:
                self.after_time = word.text == "time"
            else:
                self.run_open = False
                self.after_time = False
                self.lone_function = word.text == "function" and word.bare
        else:
            self.lone_function = False
        at_command_position = False
        if self.bare_run_open:
            if self.bare_after_time and word.bare and word.text == "-p":
                self.bare_after_time = False
            elif word.bare and word.text in RESERVED_WORDS:
                self.bare_after_time = word.text == "time"
            else:
                self.bare_run_open = False
                self.bare_after_time = False
                at_command_position = True
        group = self.frames[-1] if self.frames else None
        if group is not None and group.provisional:
            shape = self.case_shape
            self.case_shape = CASE_SHAPE_NONE
            lowers = False
            if at_command_position:
                if word.bare and word.text == "case":
                    group.case_mark += 1
                    self.case_shape = CASE_SHAPE_CASE
                else:
                    lowers = word.bare and word.text == "esac"
            elif shape == CASE_SHAPE_CASE:
                self.case_shape = CASE_SHAPE_SUBJECT
            elif shape == CASE_SHAPE_SUBJECT:
                if word.bare and word.text == "in":
                    self.case_shape = CASE_SHAPE_IN
            elif shape == CASE_SHAPE_IN:
                lowers = word.bare and word.text == "esac"
            if lowers:
                if group.case_mark >= 1:
                    group.case_mark -= 1
                elif group.case_inherited >= 1:
                    group.case_inherited -= 1
        self.words.append(word)

    def _reset_word(self):
        self.buf = []
        # The same pieces with the bash form of each `${ ... }` range of a
        # delimiter word in place of its quote-removed text; every other piece
        # is the same text. Whether the word holds such a range, and whether a
        # quote unit outside the ranges was read, decide which form the word
        # registers if it is a heredoc delimiter (`_finish_word`).
        self.bash_buf = []
        self.has_range = False
        self.outside_quote = False
        self.started = False
        self.dynamic = False
        # Every character so far is an unquoted digit (a file descriptor).
        self.digits = True
        # No quote, escape or expansion so far: `{` and `}` can be group words.
        self.bare = True

    def _put(self, text, quoted=False, dynamic=False, bash_text=None):
        """Add a piece to the word in progress. `bash_text` is the piece's text in
        the bash form of a delimiter word, when it differs from `text`: a
        `${ ... }` range of a delimiter (`_dollar`)."""
        self.buf.append(text)
        self.bash_buf.append(text if bash_text is None else bash_text)
        self.started = True
        if dynamic:
            self.dynamic = True
        if quoted or dynamic:
            self.bare = False
        if quoted or not all(ch in DIGITS for ch in text):
            self.digits = False

    def _finish_word(self):
        if not self.started:
            return
        text = "".join(self.buf)
        dynamic = self.dynamic
        bare = self.bare
        bash_buf, has_range, outside_quote = self.bash_buf, self.has_range, self.outside_quote
        self._reset_word()
        if self.redirect is not None:
            is_heredoc, strips_tabs = self.redirect
            self.redirect = None
            if is_heredoc:
                # A delimiter word has two forms. The quote-removal form is `text`.
                # The bash form is the word with each `${ ... }` range as written,
                # when the word holds at least one such range and no quote unit
                # outside its ranges; in every other word it is `text`. The parser
                # registers the form of its delimiter rule, and records that the
                # word differs when the two forms are unequal.
                bash_text = "".join(bash_buf) if has_range and not outside_quote else text
                if bash_text != text:
                    self.differs = True
                registered = bash_text if self.delimiter_rule == DELIMITER_BASH_FORM else text
                if not registered:
                    raise _Undecidable("heredoc delimiter")
                self.heredocs.append((registered, strips_tabs))
            return
        # `{` and `}` delimit a brace group only as a standalone word. A `{`
        # opens one at command position, and right after the one `function` of
        # a parenless anonymous function. A `}` that matches no open brace
        # group is an ordinary word, as it was before groups were read. The
        # words after the `}` of an anonymous body are its arguments: none of
        # them opens a group, and a `}` among them still closes an enclosing
        # brace group, as zsh does.
        #
        # A lone bare `}` reads as follows (`bare` and the text `}` leave out a
        # quoted, escaped or expanded one and one joined to other characters; a
        # redirect target returned above). When the innermost open group is a
        # `{` group it closes it, with no word pending, or with words pending
        # when the group lies within an anonymous body (they are finalized as a
        # command of the group first). When the innermost open group is a
        # provisional group, the `}` first rescues the chain of provisional
        # groups it ends, then closes the `{` group just outside the chain, but
        # only when the chain meets the separator condition and that group is a
        # `{` group, with the same word rule (`_closes_after_rescue`). In every
        # other case the `}` is an ordinary word and nothing changes.
        arguments = self._in_arguments()
        if bare and text == "{" and not arguments and (not self.words or self._names_anonymous_function()):
            self._open_group("{")
            return
        if bare and text == "}" and self.frames:
            innermost = self.frames[-1]
            if innermost.kind == "{":
                if not self.words:
                    self._close_group()
                    return
                if innermost.in_anon:
                    # Words are pending and the group lies within an anonymous
                    # body: finalize them as a command of the group, as a `;`
                    # before the `}` would, then close it. Any other brace
                    # group leaves the `}` an ordinary word.
                    self._separator(";")
                    self._close_group()
                    return
            elif self._closes_after_rescue(innermost):
                self._close_after_rescue(innermost)
                return
        if self.after_group is not None and self.after_group.kind == "{":
            if arguments:
                # An argument of the anonymous function: no command, and
                # nothing the guard has to read.
                return
            # Only a redirection, a separator or a comment may follow the `}`.
            raise _Undecidable("word after a brace group")
        self.fn_head = False
        self.anon_head = None
        self.after_group = None
        self._append_word(_Word(text, dynamic, bare))

    def _in_arguments(self):
        """Whether the words now being read follow the closing `}` of an
        anonymous body, so they are its arguments."""
        group = self.after_group
        return group is not None and group.kind == "{" and group.anon

    def _closes_after_rescue(self, group):
        """Whether a lone bare `}` read while `group` is the innermost open group
        (`group` is not a `{` group) rescues the chain of provisional groups that
        ends at `group` and closes the group just outside it. All of these hold:

        1. `group` is provisional, and so is every group of the chain; the
           chain is the run of open provisional groups from `group` outward.
        2. The chain meets the separator condition `_rescue_argument_groups`
           applies when input ends (`_rescue_separator`): the first direct
           separator of `group` is a `;` or a lone `&`, and no enclosing group of
           the chain has one that does not rescue. A group with none of its own
           takes the separator of the one nested in it. The condition is judged
           on the separators the reader read (`_Group.first_sep`), never on the
           lookahead that located the range.
        3. The group just outside the chain (`_Group.chain_base`) is a `{` group:
           a plain brace group, an anonymous body or a function body. A `(` group
           or the top level is not (a `)` rescues the chain over a `(` group,
           `_closes_paren_after_rescue`).
        4. No word is pending, or words are pending and that `{` group lies
           within an anonymous body, as for any other `}`.

        Constant time: it reads `group` and its chain base, and the two values
        `_mark_provisional` fixed when `group` opened. It changes nothing, so a
        `}` that fails it leaves every group, separator record and command as
        they were."""
        if not group.provisional or group.outer_blocked:
            return False
        if _rescue_separator(group.first_sep) is None:
            return False
        base = group.chain_base
        if base is None or base.kind != "{":
            return False
        return not self.words or base.in_anon

    def _close_after_rescue(self, group):
        """Rescue the chain of provisional groups that ends at `group`, from the
        innermost out, and close the `{` group just outside it. `_closes_after_rescue`
        has held. Each group of the chain is removed from the open groups once; its
        `(` is read as an argument-word character and the group ends at its first
        direct separator, exactly as `_rescue_argument_groups` reads it when input
        ends. Nothing is moved: a provisional group carries no connection and no
        skip of its own, so the commands read in the rescued groups take both from
        the groups around them when the string has been read, as the commands of
        the `{` group do. A redirect or pipe attached to that group therefore
        reaches them. Words pending are finalized as a command of that group, as a
        `;` before the `}` would, and the group is then closed as a `; }` closes
        it. The `}` is consumed."""
        base = group.chain_base
        while self.frames[-1] is not base:
            self.frames.pop()
        if self.words:
            self._separator(";")
        self._close_group()

    def _mark_provisional(self, group):
        """Mark the group just opened at an argument `(` as provisional and fix,
        from the values of its parent alone, the two values the check at a `}`
        or a `)` reads (`_Group.chain_base`, `_Group.outer_blocked`).

        When the parent is provisional the parent's group is part of the chain:
        the base is the parent's base, and the part outside this group is
        blocked when the parent's part is, or when the parent's own first direct
        separator does not rescue. That separator is final now and stays so as
        long as this group is open, because the parent reads no direct separator
        meanwhile. The separator it would inherit from this group is one of
        RESCUE_SEPARATORS whenever this group's own separator rescues, so which
        one it is does not matter here. Otherwise the parent (or the top level,
        None) is the base, and nothing outside this group is blocked.

        The same call fixes a third value, `_Group.case_inherited`, from the
        same parent and in the same way: the sum of the parent's case mark
        (`_Group.case_mark`, the number of unfinished `case`s) and the parent's
        inherited value when the parent is provisional, 0 otherwise, whatever
        the parent's separators are. It is a snapshot of the parent's two
        values taken now, read once from the parent alone with no walk over the
        groups around, and it does not follow later changes to the parent's
        values; afterwards it changes only when a bare `esac` is read in this
        group while its own case mark is 0 and the `esac` is at command position
        (the first word after the leading run of bare reserved words) or right
        after a counted `case`, any one word and a bare `in` of the same simple
        command (`_append_word`). It is kept apart from `outer_blocked`: the
        check at a `}` never reads it, and the check at a `)` turns the rescue
        off for a group whose inherited value is 1 or more
        (`_closes_paren_after_rescue`)."""
        group.provisional = True
        parent = group.parent
        if parent is not None and parent.provisional:
            group.chain_base = parent.chain_base
            group.outer_blocked = (
                parent.outer_blocked
                or _rescue_separator(parent.first_sep, RESCUE_SEPARATORS[0]) is None
            )
            group.case_inherited = parent.case_mark + parent.case_inherited
        else:
            group.chain_base = parent
            group.outer_blocked = False
            group.case_inherited = 0

    def _flush(self):
        """End the simple command in progress. Return (made, redirected):
        whether it held words, and whether it held a redirection."""
        self._finish_word()
        self.redirect = None
        made = bool(self.words)
        redirected = self.redirected
        if made:
            group = self.frames[-1] if self.frames else None
            self.commands.append(_Command(self.words, self.stdin, self.pipe_pending, group))
            self.pipe_pending = False
            self.list_pending = False
        self._start_words()
        self.stdin = False
        self.redirected = False
        self.after_group = None
        return made, redirected

    def _separator(self, sep):
        _, redirected = self._flush()
        if self.frames:
            # The first separator read while a provisional group is the
            # innermost open group is its first direct separator; the main
            # reader's own tokens are the only ones that reach here.
            group = self.frames[-1]
            if group.provisional and group.first_sep is None:
                group.first_sep = sep
            # A direct separator ends the comment exception of the innermost
            # group, for good. A separator read inside a nested group reached
            # that group alone and left this one as it was.
            if group.comment_exception and sep in COMMENT_EXCEPTION_ENDERS:
                group.comment_exception = False
        if sep != "\n":
            self.fn_head = False
            self.anon_head = None
        if sep in ("&&", "||"):
            self.list_pending = True
        elif sep != "\n" or redirected:
            # Any other separator ends the list continuation, and so does a
            # newline that ends a command holding a redirection (a line of only
            # `< /dev/null` or `<<EOF`). A newline that ends an empty command
            # with no redirection (a blank line, a comment-only line) leaves it.
            self.list_pending = False
        if sep in ("|", "|&"):
            self.pipe_pending = True
        elif sep != "\n" or redirected:
            # A newline that ends an empty command keeps a pending pipe: the
            # empty lines, comments and heredoc bodies after `|` are not its
            # right side.
            self.pipe_pending = False

    @staticmethod
    def _names_function(words):
        """Whether the words before a `(` are a function name. The leading
        run of reserved words (RESERVED_WORDS) is removed first, together with
        a non-dynamic `-p` right after a removed `time`; a dynamic word never
        matches, and a reserved word later in the words is never removed. When
        nothing remains, the original words are judged. What remains must be
        one word, or `function` and one word, where the name is not dynamic and
        holds no `=` (an assignment such as `a=` or `export a=` is not a name).
        When the one word left is `function` and it holds no quote, no escape
        and no expansion, it is not a function name: the `()` after it starts
        no definition and the group after its `()` is judged (a zsh anonymous
        function). That reading comes before the `function` and one word
        reading, so `function function` is still a definition, and a quoted or
        escaped `function` is still a name.
        A name whose content, after quote removal, ends in one of the extglob
        operator characters `?` `*` `+` `@` `!` is not a function name either,
        even when it is the one reserved word left (`!`): the group after its
        `()` is judged. The rule rejects the word the steps above chose and
        never changes which word that is. Only the last character is read, and
        whether extglob is enabled is never checked. The removal is a view over
        `words` read in one forward pass: the list itself is not changed."""
        end = len(words)
        first = 0
        while first < end and not words[first].dynamic and words[first].text in RESERVED_WORDS:
            was_time = words[first].text == "time"
            first += 1
            if was_time and first < end and not words[first].dynamic and words[first].text == "-p":
                first += 1
        if first == end:
            first = 0
        if end - first == 1 and words[first].text == "function" and words[first].bare:
            return False
        if end - first == 2 and words[first].text == "function":
            first += 1
        if end - first != 1:
            return False
        name = words[first]
        if name.dynamic or "=" in name.text:
            return False
        return not name.text.endswith(EXTGLOB_OPERATORS)

    def _names_anonymous_function(self):
        """Whether the words read so far in the simple command are, after the
        same reserved-run removal that `_names_function` applies, exactly one
        `function` that holds no quote, no escape and no expansion. This is
        the rule of the parenless anonymous function `function { ...; }`: a
        standalone `{` right after such words, in the same simple command,
        opens the body of an anonymous function. `function f {`, a quoted or
        escaped `function`, a dynamic word and a `function` on an earlier line
        do not. The empty `()` of `function () { ...; }` is decided by the same
        rule.
        The decision takes constant time per `{`. It reads `lone_function`,
        which `_append_word` keeps as each word is appended, and never the
        list of words, so a command with many `{` words stays linear in its
        length."""
        return self.lone_function

    def _open_group(self, kind):
        self._finish_word()
        head = kind == "(" and self._names_function(self.words)
        # Whether the group belongs to an anonymous function, and the pipe
        # state of its head, are read before the flush takes the words away and
        # ends a pending pipe. A `{` is the anonymous body after the empty `()`
        # of a head, or right after the one `function` of the parenless form;
        # the body is on the right side of the pipe when its head is. A `(` is
        # an anonymous head after the one `function`, or where the simple
        # command holds no word (not as the body of a function definition, and
        # not among the arguments of an anonymous body). The stdin redirects
        # read in the head simple command are read here too, before the flush
        # drops them: an anonymous `(` keeps them for its body, and a body
        # opened by the parenless `function {` takes them at once. A body that
        # follows the empty `()` takes what the `(` kept, never the redirects
        # read after the `)`.
        anon = False
        anon_pipe = self.pipe_pending
        anon_stdin = False
        head_stdin = False
        if kind == "{":
            if self.anon_head is not None:
                anon = True
                anon_pipe = self.anon_head.anon_pipe
                head_stdin = self.anon_head.anon_stdin
            elif self._names_anonymous_function():
                anon = True
                head_stdin = self.stdin
        elif not head and not self.fn_head and not self._in_arguments():
            anon = self._names_anonymous_function() or not self.words
            anon_stdin = anon and self.stdin
        self._flush()
        self.list_pending = False
        parent = self.frames[-1] if self.frames else None
        # The sizes as they stand once this group is in the list: an empty
        # group is closed with the same sizes.
        size = (len(self.commands), len(self.groups) + 1)
        pipe = anon_pipe if kind == "{" and anon else self.pipe_pending
        # Whether the group lies within an anonymous-function body is fixed
        # here and never read again from the groups around it: an anonymous
        # body is within one, any other group takes the value of the group it
        # opens in, and a group opened at top level that is no anonymous body
        # is not. A `}` reads it in constant time.
        in_anon = (kind == "{" and anon) or (parent is not None and parent.in_anon)
        # The comment exception is fixed here as well, once: a group opened while
        # the innermost open group has it starts with it, whatever its own
        # opening condition; the value is copied and never read from the parent
        # again. `_read_argument_parens` adds the exception its own opening
        # condition gives.
        comment_exception = parent is not None and parent.comment_exception
        group = _Group(
            kind, parent, pipe, self.fn_head, head, size, anon, anon and anon_pipe, anon_stdin,
            head_stdin, in_anon, comment_exception,
        )
        self.pipe_pending = False
        self.fn_head = False
        self.anon_head = None
        self.frames.append(group)
        self.groups.append(group)

    def _close_group(self):
        """Close the innermost group. A stdin redirect read next connects it."""
        group = self.frames.pop()
        self.pipe_pending = False
        self.after_group = group
        if group.kind == "(" and group.size == (len(self.commands), len(self.groups)):
            # `()` with nothing inside: the group that follows is the body of
            # a function (`name()`) or of an anonymous function.
            if group.head:
                self.fn_head = True
            elif group.anon:
                self.anon_head = group

    def _closes_paren_after_rescue(self, group):
        """Whether an unquoted `)` read while `group` is the innermost open group
        rescues the chain of provisional groups that ends at `group` and closes
        the `(` group just outside it. The word in progress has been finished.

        The answer is no, before any reasoning below, when the case mark of
        `group` (`_Group.case_mark`, the number of unfinished `case`s that
        `_append_word` raises at a bare `case` at command position, the first
        word after the leading run of bare reserved words, and lowers at a bare
        `esac` at command position or right after a counted `case`, any one
        word and a bare `in`) or its inherited value (`_Group.case_inherited`,
        fixed once when the group opens as the parent's case mark plus the
        parent's inherited value by `_mark_provisional`, and lowered by that
        `esac` while the own mark is 0) is 1 or more. Whatever its separators
        and its base are, a group where
        either one is 1 or more is not rescued: the `)` is read as the
        terminator of a case pattern. A group where both are 0, never counted
        or returned to 0 by `esac`, goes on to the reasoning below like a group
        that was never marked.
        `_close_paren` then falls through to its ordinary reading and, the
        provisional group being the innermost open group and a `(` group,
        closes that group itself instead of the `(` group outside the chain, so
        a stdin redirect that follows reaches only that group. The check reads
        the two values of `group` alone.

        Otherwise all of these hold:

        1. `group` is provisional and its `outer_blocked` is false: the chain is
           the run of open provisional groups from `group` outward, and no group
           outside `group` in it blocks the rescue.
        2. The separator condition (`_rescue_separator`), the one definition the
           rescue when input ends and the rescue at a `}` apply too, accepts
           `group`'s own first direct separator: a `;` or a lone `&`. `group` is
           the innermost group of its chain, so it has nothing to inherit; the
           separators of the outer groups are already folded into
           `outer_blocked`. Only the separators the reader read count
           (`_Group.first_sep`), never the lookahead that located the range.
        3. The group just outside the chain (`_Group.chain_base`) is a `(` group.
           The top level (None) and a `{` group are not: a `)` there is read as
           it was, and a `{` group is closed by a `}` (`_closes_after_rescue`).
           A chain base is never provisional, by its definition.

        Unlike the rescue at a `}`, no word condition applies: words pending
        before the `)` never block it. Constant time: it reads `group`, its chain
        base and the values `_append_word` and `_mark_provisional` keep on
        `group` (`case_mark`, `case_inherited`, `outer_blocked`, `first_sep`),
        and walks no group. It changes nothing, so a `)` that fails it is read
        exactly as before."""
        if group.case_mark >= 1 or group.case_inherited >= 1:
            return False
        if not group.provisional or group.outer_blocked:
            return False
        if _rescue_separator(group.first_sep) is None:
            return False
        base = group.chain_base
        return base is not None and base.kind == "("

    def _close_paren_after_rescue(self, group):
        """Rescue the chain of provisional groups that ends at `group`, from the
        innermost out, and close the `(` group just outside it.
        `_closes_paren_after_rescue` has held. Each group of the chain is removed
        from the open groups once and is never closed: its `(` is read as an
        argument-word character and the group ends at its first direct
        separator, exactly as `_rescue_argument_groups` reads it when input ends.
        Nothing is moved: a provisional group carries no connection and no skip
        of its own, so the commands read in the rescued groups take both from the
        groups around them when the string has been read, as the commands of the
        closed `(` group do. A pipe into that group and a stdin redirect after
        its close therefore reach them, and they are skipped when that group, or
        a group around it, is the body of a function definition.
        Words pending are finalized as one simple command of the closed group, as
        the `)` of an ordinary subshell finalizes the words before it; no
        separator is recorded on any group, because the chain base is not
        provisional and the `)` is no separator. The group is then closed, so a
        stdin redirect read next connects it, and the `)` is consumed. The list
        continuation is cleared when the simple command that the `)` ends held a
        redirection, and otherwise left as it was. Text after the close is read
        outside the group, and a later `)` with no open `(` group is a
        separator, as anywhere else."""
        base = group.chain_base
        while self.frames[-1] is not base:
            self.frames.pop()
        _, redirected = self._flush()
        if redirected:
            self.list_pending = False
        self._close_group()

    def _close_paren(self):
        """Read an unquoted `)` that the main reader itself meets (a `)` inside
        quotes, a comment, a substitution chunk or an argument range never gets
        here). The word in progress is finished first, so a lone `}` finished
        there keeps its own reading.

        - When the innermost open group is a provisional group that rescues the
          chain it ends and the open group just outside the chain is a `(` group,
          the `)` rescues the chain and closes that group
          (`_closes_paren_after_rescue`, `_close_paren_after_rescue`). A
          provisional group whose case mark or inherited value is 1 or more
          (`_Group.case_mark`, the number of `case`s that no `esac` has closed
          yet, raised by a bare `case` at command position, the first word after
          the leading run of bare reserved words, and lowered by a bare `esac`
          at command position or right after a counted `case`, any one word and
          a bare `in`; and `_Group.case_inherited`, fixed when the group opens
          as the parent's case mark plus the parent's inherited value and
          lowered by that `esac` while the own mark is 0) never rescues: its
          `)` is a case-pattern terminator and takes the next reading. Once
          `esac` has returned both to 0 the group rescues again.
        - Otherwise, when the innermost open group is a `(` group, the `)` closes
          it; the words before the `)` are finalized as a command of that group.
          This is the reading of a `)` read while a provisional group with a
          case mark or inherited value of 1 or more is the innermost open group:
          the provisional group is that `(` group, so the `)` closes it and not
          the subshell outside the chain. In the rescue reading and in this
          one, the list continuation is cleared when the simple command the `)`
          ends held a redirection, and otherwise left as it was.
        - Otherwise no `(` group is the innermost open group (a `case` pattern,
          or a `{` group is the innermost) and the `)` is a separator."""
        self._finish_word()
        if self.frames and self._closes_paren_after_rescue(self.frames[-1]):
            self._close_paren_after_rescue(self.frames[-1])
        elif self.frames and self.frames[-1].kind == "(":
            _, redirected = self._flush()
            if redirected:
                self.list_pending = False
            self._close_group()
        else:
            # No subshell is open (a `case` pattern, for one): a separator.
            self._separator(")")

    def _rescue_argument_groups(self):
        """When input ends, close the provisional groups that were never closed
        and can be rescued, from the innermost out, and stop at the first open
        group that cannot be. A lone `}` rescues the chain of provisional groups
        it ends under the same separator condition before input ends
        (`_close_after_rescue`), and an unquoted `)` does the same when the open
        group just outside the chain is a `(` group (`_close_paren_after_rescue`):
        the condition is `_rescue_separator`, shared by the three rescues, and a
        provisional group a `}` or a `)` rescued is no longer open here.

        A provisional group is rescued when the first separator read directly in
        it is a `;` or a lone `&`: its `(` is then read as an argument-word
        character, the group ends at that separator, and the commands after the
        separator are judged as following the anonymous function. The separator
        of a rescued group is the first direct separator of the group that
        encloses it when that one has none of its own, so groups nested in each
        other are rescued in one pass from the inside out. A group whose first
        direct separator is a newline or another operator, a provisional group
        with no separator, and a group that is not provisional are not rescued:
        the group stays open, and the caller finds it so.

        Nothing is moved. A provisional group opens among the arguments of an
        anonymous function, right after the body is closed, where no pipe is
        pending, and it is never closed, so no redirect reaches it; neither it
        nor the provisional groups around it (all open, since a rescue succeeds
        only when every open group is one) carries a connection, so the
        commands of a rescued group already read as commands that follow the
        anonymous function, and the final pass over the groups settles their
        connection and skip from the groups they sit in as it does for any
        other command. The work is one visit per open group."""
        separator = None
        while self.frames:
            group = self.frames[-1]
            if not group.provisional:
                return
            first = _rescue_separator(group.first_sep, separator)
            if first is None:
                return
            self.frames.pop()
            separator = first

    def _read_heredocs(self):
        s = self.s
        for delim, strips_tabs in self.heredocs:
            while True:
                nl = s.find("\n", self.i)
                end = nl if nl != -1 else self.n
                line = s[self.i:end]
                if (line.lstrip("\t") if strips_tabs else line) == delim:
                    self.i = end + 1 if nl != -1 else self.n
                    break
                if nl == -1:
                    raise _Undecidable("heredoc body")
                self.i = end + 1
        self.heredocs = []

    def _skip_parens(self, start):
        """Return the index just after the `)` that closes the `(` at
        `start`, skipping quoted text. Only backslash pairs, single-quoted text
        and double-quoted text are skipped: a backquote and a comment get no
        special reading. Raises _Undecidable when no `)` closes the `(`."""
        end = self._scan_parens(start)[0]
        if end is None:
            raise _Undecidable("parenthesis")
        return end

    def _scan_parens(self, start, limit=None):
        """Scan from the `(` at `start`, skipping quoted text as `_skip_parens`
        does, and return (end, separated, backquoted, reached). `end` is the
        index just after the `)` that closes the `(`, or None when the scan
        finds none: the `(` is never closed, a quote is not balanced, or `limit`
        characters past `start` have been read without meeting the `)`.
        `separated` is whether an unquoted `;`, `&` or newline lies between the
        `(` and the `)`; a character after a backslash and the text inside
        quotes are never separators. `backquoted` is whether a backquote lies
        between the `(` and the `)`, one inside double quotes included; a
        backquote right after a backslash and one inside single quotes do not
        count, and whether the backquotes balance does not matter. A backquote
        is only noticed, never read: it changes neither the nesting depth, nor
        the quoting, nor where the scan stops. Both flags are false when `end`
        is None. `reached` is the index the scan got to, which is what the work
        it cost is read from. One pass, constant work per character."""
        s = self.s
        n = self.n
        stop = n if limit is None else min(n, start + limit)
        depth = 0
        separated = False
        backquoted = False
        j = start
        while j < stop:
            ch = s[j]
            if ch == "\\":
                j += 2
                continue
            if ch == "'":
                j = s.find("'", j + 1)
                if j == -1:
                    return None, False, False, n
            elif ch == '"':
                j += 1
                while j < n and s[j] != '"':
                    if s[j] == "`":
                        backquoted = True
                    j += 2 if s[j] == "\\" else 1
                if j >= n:
                    return None, False, False, n
            elif ch == "`":
                backquoted = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return j + 1, separated, backquoted, j + 1
            elif ch in ";&\n":
                separated = True
            j += 1
        return None, False, False, min(j, n)

    def _read_argument_parens(self):
        """Read the `(` at `self.i`, met among the arguments of an anonymous
        function (`_in_arguments`), whether it stands in the middle of a word
        (`foo(x)`) or at its start (`(x)`). The `(` and everything up to its
        matching `)` become part of the argument word being read, whitespace and
        `|` included, and `after_group` is left alone: it still points at the
        anonymous body, so a stdin redirect after the range connects the body. A
        separator outside the range ends the arguments as usual. While the
        target of `<<` or `<<-` is being read, the text of the range is
        quote-removed before it joins the word (`_remove_range_quotes`), and a
        quote unit the range held marks the word as holding a quote unit outside
        its `${ ... }` ranges, so the bash form of the word is its quote-removal
        form (`_finish_word`). The text added is the same in both forms.

        The `(` opens a group instead, exactly as before ranges were read, when
        the range holds an unquoted `;`, `&` or newline, or a backquote (one
        inside double quotes included; one a backslash escapes and one inside
        single quotes do not count); when the scan finds no matching `)` (the
        group reading goes on to settle a `(` that is never closed, and it reads
        the comments and backquotes the scan does not); and when the work cap is
        spent. The scan only notices a backquote and never reads it, so a `)`
        inside one closes the range early; the group reading, which does read
        it, settles where it ends. Every scan is charged to `paren_budget`, the
        characters it read: that is what keeps the whole parse linear. A range
        that holds a `;` opens a group, and the arguments of an anonymous
        function nested in it meet the next `(`, so a scan toward the end of the
        string from each of them would be quadratic.

        The group opened here is provisional (`_Group.provisional`). When it is
        never closed and the first separator read directly in it is a `;` or a
        lone `&`, its `(` is read as an argument-word character after all: the
        commands after that separator are judged as following the anonymous
        function (`_rescue_argument_groups`, run when input ends,
        `_close_after_rescue`, run at a lone `}` that closes the `{` group around
        it, or `_close_paren_after_rescue`, run at a `)` that closes the `(`
        group around it). A newline as the first direct separator is not
        rescued.

        The group opened for a range that has a matching `)`, holds no unquoted
        `;`, `&` or newline and holds a backquote has the comment exception:
        while it is the innermost open group, an unquoted `#` at word start is a
        word character, not the start of a comment, and the characters after it
        join the word as in any other word, so a `)` after it still closes the
        group. The scan that finds the range still gives a backquote and a
        comment no special reading; the exception belongs to the reading of the
        group opened after it. A group opened while the innermost open group has
        the comment exception starts with it, whatever its own opening
        condition: the value is copied once, when the group opens, and a group
        that closes takes its value with it, so the value of its parent applies
        again. Reading a direct separator ends it: a `;`, a lone `&`, `&&`, `|&`
        or a newline that the reader itself reads while a group with the comment
        exception is the innermost open group clears it for that group for good,
        and a `#` at word start is a comment there as before; `|`, `||`, `&>`,
        `>&`, a quoted separator and a backslash-escaped separator clear
        nothing, and a separator read inside a nested group never changes an
        outer group. This is the single exception to the earlier assumption that
        group reading adds no new reading: a `#` at word start stays a comment
        outside every group, in a group opened at a `;`, `&` or newline, in a
        group opened because no matching `)` is found and in a group whose
        exception was cleared, a `#` inside `$(` is read as before, and a `#` in
        the middle of a word is a word character as ever."""
        start = self.i
        end, separated, backquoted, reached = self._scan_parens(
            start, self.paren_budget
        )
        self.paren_budget = max(0, self.paren_budget - (reached - start))
        if end is not None and not separated and not backquoted:
            if self._at_delimiter():
                # The range is part of the delimiter of `<<` or `<<-`: register
                # the delimiter zsh uses, not the raw text of the range. A quote
                # unit the range held is a quote unit outside the `${ ... }`
                # ranges of the word, so the bash form of the word is its
                # quote-removal form (`_finish_word`); the text added is the
                # same in both forms.
                text, _, _, quoted = self._remove_range_quotes(start, end)
                self._put(text, quoted=True)
                if quoted:
                    self.outside_quote = True
            else:
                self._put(self.s[start:end], quoted=True)
            self.i = end
            return
        self.i += 1
        self._open_group("(")
        group = self.frames[-1]
        self._mark_provisional(group)
        if end is not None and not separated and backquoted:
            group.comment_exception = True

    def _at_delimiter(self):
        """Whether the word being read is the delimiter of `<<` or `<<-`: the
        operator has been read and its target word is not finished yet. This is
        the delimiter position; the readings that apply only there ask for it."""
        return self.redirect is not None and self.redirect[0]

    def _remove_range_quotes(self, start, end, braced=False):
        """Return (text, next, bash_text, quoted): the text of the range
        `self.s[start:end]` with its quotes removed the way a word's quotes are
        removed where the reader meets them, the index where reading goes on,
        the bash form of the range, and whether the range read a quote unit. The
        range is part of the delimiter of `<<` or `<<-`, so the text a shell
        compares the body lines with is what gets registered: the quote-removal
        form (`text`) or the bash form (`bash_text`), by the delimiter rule of
        the parser (`_finish_word`). Two kinds of range are read by the one
        scan below.

        The bash form of a braced range is its original characters, `"`, `'`
        and backslash included, except that a backslash-newline pair is dropped
        wherever the shared reader drops it: outside quotes, and inside double
        quotes. A single-quoted unit keeps its original characters; a backslash
        and the character after it keep both characters (a backslash and a
        newline add nothing); a double-quoted unit keeps its original characters
        minus the backslash-newline pairs; an unquoted `$(` keeps the text the
        shared reader returns, as the quote-removal form does. Both forms come
        from the same forward scan, which finds the close of the range, so the
        close search and every undecidable case below are the same for both. For
        a parenthesised range the bash form is `text`: its quote units make the
        word's bash form its quote-removal form (`quoted`), so the bash form of
        the range itself is never read. `quoted` is true when the range read a
        quote unit (a `'`, `"` or backslash unit; a backslash-newline pair is
        none); the word reader marks the word with it when the range is a
        parenthesised one.

        A parenthesised range (`braced` false) runs from its `(` through its
        `)`, and `next` is `end`. A braced range (`braced` true) starts at an
        unquoted `${` at `start` and ends at the `}` that closes it, which this
        scan finds: `end` is then only the limit of the text (the end of the
        input), not the end of the range, and `next` is the index just after
        the closing `}`. The close search runs over the text, not the line, so
        a quote may span lines. The close is the first unquoted, unescaped `}`
        at nesting depth zero: an unquoted `${` adds one to the depth and an
        unquoted `}` takes one off; a `}` inside single or double quotes, a
        `}` a backslash escapes and a `}` inside a `$( ... )` count for
        nothing; a backquote is an ordinary character, neither a quote nor a
        substitution. A braced range raises _Undecidable when the text ends
        before the depth is back to zero.

        One pass from left to right, three quote states: outside quotes,
        single-quoted, double-quoted. Outside quotes a backslash is dropped and
        the next character kept (a backslash and a newline are both dropped),
        `'` and `"` open their state and are dropped, and every other character
        is kept: `$` not followed by a quote, `$x`, nested parentheses, the
        `${` and `}` of a braced range with the `#` and `:-` between them, and
        the text of a `$( ... )`, which is kept as written with the quotes
        inside it. A `$` right before a `'` or a `"` outside quotes raises
        _Undecidable: what zsh reads there is not known.
        A backslash pair, a single-quoted unit and a double-quoted unit are
        read by the shared reader `_read_quoted_unit`, held to `end`, and it
        does the quote removal. Single-quoted text is kept as it stands,
        backslashes included, and the closing `'` is dropped. In double quotes
        a backslash before `$`, a backquote, `"`, `\\` or a newline is dropped
        (before a newline together with it) and the next character kept, any
        other backslash stays with the next character, a `$'` or `$"` there is
        no trigger, and the closing `"` is dropped. A `$( ... )` or a
        `$(( ... ))` inside double quotes keeps its original text, the quotes
        inside it included.

        An unquoted `$(` (`$((` included) is read by the kind of range. In a
        braced range, an unquoted `$(` inside a delimiter's `${ ... }` range is
        read by the shared reader `_read_quoted_unit`, held to `end`. That
        reader skips the substitution with the case-aware `_skip_substitution`,
        so a case statement inside it is read through its `esac`, its
        pattern's `)` does not end the substitution, and the original text is
        kept, the quotes inside it included. This method calls the reader only;
        it never calls `_skip_substitution` itself. In a parenthesised range
        (`braced` false) an unquoted `$(` keeps the paren scan (`_skip_parens`),
        which counts parentheses and reads no case statement.

        A quote the range does not close raises _Undecidable, and so does a
        substitution inside double quotes, or an unquoted `$(` of a braced
        range, whose skip ends beyond `end` or cannot be read, and an unquoted
        `$( ... )` of a parenthesised range that has no close. The part of the
        word outside the range is not read here: it was quote-removed when it
        was read and is not processed again. Time is linear in the length of
        the range whatever its nesting depth: each character is read a bounded
        number of times, and a `$( ... )` is skipped once, never rescanned. A
        skip that runs beyond `end` ends the whole reading, so it happens at
        most once."""
        s = self.s
        # The quote-removal text and the bash form, built piece by piece in step.
        out = []
        raw = []
        quoted = False
        j = start
        depth = 0
        while j < end:
            ch = s[j]
            if ch in "\\'\"":
                # The same reader that word reading uses, held to the end of
                # the range. The dynamic indication is of no use here: a
                # registered delimiter is compared as text only. The reader also
                # yields the original characters of the unit, minus the
                # backslash-newline pairs it drops: the bash form of the unit.
                unit = j
                text, j, _, original = self._read_quoted_unit(j, end, original=True)
                out.append(text)
                raw.append(original)
                if ch != "\\" or s[unit + 1] != "\n":
                    quoted = True
            elif ch == "$" and j + 1 < end and s[j + 1] in "'\"":
                raise _Undecidable("dollar quote")
            elif ch == "$" and j + 1 < end and s[j + 1] == "(":
                if braced:
                    # The case-aware skip of the shared reader, held to the end
                    # of the range: a case statement in the substitution is
                    # read, so its pattern's `)` does not end it. The text it
                    # returns is kept in both forms.
                    text, j, _, original = self._read_quoted_unit(j, end, original=True)
                    out.append(text)
                    raw.append(original)
                else:
                    close = self._skip_parens(j + 1)
                    if close > end:
                        raise _Undecidable("parenthesis")
                    out.append(s[j:close])
                    raw.append(s[j:close])
                    j = close
            elif braced and ch == "$" and j + 1 < end and s[j + 1] == "{":
                depth += 1
                out.append("${")
                raw.append("${")
                j += 2
            elif braced and ch == "}":
                out.append(ch)
                raw.append(ch)
                j += 1
                depth -= 1
                if depth == 0:
                    return "".join(out), j, "".join(raw), quoted
            else:
                out.append(ch)
                raw.append(ch)
                j += 1
        if braced:
            raise _Undecidable("brace")
        text = "".join(out)
        return text, j, text, quoted

    def _read_quoted_unit(self, start, limit, original=False):
        """Read the quoted unit that opens at `start` and return (text, next,
        dynamic): the text of the unit with its quotes removed, the index just
        after the unit, and whether the unit holds a substitution or a `$`
        inside double quotes. This is the one reader of a backslash pair, a
        single-quoted unit, a double-quoted unit and the unquoted `$(` of a
        delimiter's `${ ... }` range: word reading calls it with the end of the
        input as `limit` (for a backslash, a single quote or a double quote),
        and the quote removal of a delimiter range (`_remove_range_quotes`)
        calls it with the end of the range (the end of the input, for the range
        of a delimiter's `${`, whose end is found by the same scan).

        With `original` true the reader returns a fourth item, the original
        characters of the unit, quotes included, minus the backslash-newline
        pairs it drops: the bash form of the unit. It is derived here because
        the pairs it drops inside double quotes are told apart from the ones
        inside a substitution only by this reader's own scan. Without `original`
        the three items above are returned, unchanged for every caller. A
        single-quoted unit keeps all its characters; a backslash pair keeps both
        characters, except a backslash and a newline, which give nothing; a
        double-quoted unit keeps every character as written, a substitution
        inside it included, except a backslash and a newline directly inside the
        quotes.

        `limit` is exclusive: the unit must end before it, so `next` never lies
        beyond it. The caller guarantees `start < limit` and that `start` holds
        one of four starts: a backslash, a single quote, a double quote, or an
        unquoted `$` directly followed by `(`. Only the braced reading of
        `_remove_range_quotes` passes a `$(` start; word reading never does,
        because it hands an unquoted `$` to `_dollar`.

        A backslash and the character after it yield that character; a
        backslash and a newline yield nothing. Single-quoted text is kept as it
        stands. Inside double quotes a backslash is dropped only before `$`, a
        backquote, `"`, another backslash or a newline (before a newline
        together with it) and any other backslash stays with the next
        character; a `$` or a backquote marks the unit dynamic. At a backquote,
        a `$(` or a `$((` the substitution is skipped with `_skip_substitution`
        and its original text is kept as written, the quotes inside it
        included: they close nothing here and are not removed.

        An unquoted `$(` inside a delimiter's `${ ... }` range (`$((` included)
        is skipped with `_skip_substitution`, started at the `$`: the same
        case-aware skip as a substitution inside double quotes. The unit is the
        original characters from the `$` through the end of the skip,
        unchanged, the quotes inside them included, and it is dynamic.

        Raises _Undecidable when the unit does not close before `limit` (a
        backslash with no character after it before `limit` included), when the
        skip of a substitution, inside double quotes or from an unquoted `$(`
        start, ends beyond `limit`, and when `_skip_substitution` itself raises
        it. An overrun ends the whole reading, so the skip past `limit` happens
        at most once per string. This reader calls `_skip_substitution` only;
        nothing it calls calls it back."""
        s = self.s
        ch = s[start]
        if ch == "$":
            # An unquoted `$(` of a delimiter's `${ ... }` range: skipped as a
            # substitution inside double quotes is, and kept as written.
            end = self._skip_substitution(start)
            if end > limit:
                raise _Undecidable("substitution")
            if original:
                return s[start:end], end, True, s[start:end]
            return s[start:end], end, True
        if ch == "\\":
            if start + 1 >= limit:
                raise _Undecidable("trailing backslash")
            nxt = s[start + 1]
            if original:
                return ("" if nxt == "\n" else nxt), start + 2, False, ("" if nxt == "\n" else "\\" + nxt)
            return ("" if nxt == "\n" else nxt), start + 2, False
        if ch == "'":
            close = s.find("'", start + 1, limit)
            if close == -1:
                raise _Undecidable("quote")
            if original:
                return s[start + 1:close], close + 1, False, s[start:close + 1]
            return s[start + 1:close], close + 1, False
        j = start + 1
        out = []
        # The original characters of the unit, kept only when asked for.
        raw = [] if original else None
        dynamic = False
        while j < limit:
            ch = s[j]
            if ch == '"':
                if original:
                    return "".join(out), j + 1, dynamic, '"' + "".join(raw) + '"'
                return "".join(out), j + 1, dynamic
            if ch == "\\" and j + 1 < limit:
                nxt = s[j + 1]
                if nxt in '"\\$`':
                    out.append(nxt)
                elif nxt != "\n":
                    out.append("\\" + nxt)
                if original and nxt != "\n":
                    raw.append("\\" + nxt)
                j += 2
                continue
            if ch == "`" or s.startswith("$(", j, limit):
                end = self._skip_substitution(j)
                if end > limit:
                    raise _Undecidable("substitution")
                out.append(s[j:end])
                if original:
                    raw.append(s[j:end])
                dynamic = True
                j = end
                continue
            if ch in "$`":
                dynamic = True
            out.append(ch)
            if original:
                raw.append(ch)
            j += 1
        raise _Undecidable("quote")

    def _skip_substitution(self, start):
        """Return the index just after the command substitution that begins
        at `start` (`$(`, `$((` or a backtick). Only the shared quoted-unit
        reader `_read_quoted_unit` calls it, for two kinds of substitution: one
        inside double quotes, and an unquoted `$(` inside a delimiter's
        `${ ... }` range (a `$(` or a `$((`, never a backtick), which is
        reached from `_read_quoted_unit` by the braced reading of
        `_remove_range_quotes`. The reading below is the same for both.

        Quotes, backslash escapes, `${ ... }` and nested substitutions inside
        the chunk are followed, so a `"` or a `)` that belongs to them closes
        neither the chunk nor the double quote around it. Nesting is kept on
        an explicit stack, so depth costs no recursion, and the contents of
        the chunk are never judged.

        Command position (rule 1). Each command list the reader keeps (the
        body of a `$(`, the body of a nested subshell `(` and every item body
        of a case statement) carries state of constant size: whether the next
        word is at a command position, whether a `[[` read at a command
        position is still open in it, and one head state (rule 7). A list
        opened by `(` also records whether that `(` was read at a command
        position and whether it is a zsh `for` word list. The next word is at
        a command position when the list opens; after `;`, `&` or `|` (`&&`
        and `||` included); after a newline; after a subshell `(`; after a
        standalone `then`, `do`, `else`, `elif`, `if`, `while`, `until`,
        `time`, `!` or `{` that was itself read at a command position; after
        a compound-command closing (rule 5); after a function head and after
        a loop or coproc head (rule 6). It is not at a command position after
        any other word: an ordinary command word, an assignment, a
        redirection target, a `time` option, a word that holds a
        substitution, and a reserved word or `!` read at an argument
        position. The characters of the previous word are never looked at
        backward.

        Opening and closing a case statement (rule 2). A `case` at a command
        position of a command list in the chunk opens a case statement, and a
        case statement inside the chunk is read: its subject, its patterns
        (alternatives, the optional leading `(`, nested parentheses) and its
        item bodies are followed up to the close of the statement, the closing
        `esac` or, in the brace form below, the closing `}`, so its pattern's
        `)` closes neither the chunk nor a group, and the chunk ends at the
        `)` that follows the close. An item body is a command list. The item
        terminators `;;&`, `;;`, `;&` and `;|` end an item and return the
        statement to a pattern position, where `esac` closes it and any other
        word, `case` included, starts a pattern. `case` opens a statement only
        as a standalone word at a command position. In an item body `esac`
        closes a statement only as a standalone word at a command position;
        at a pattern position it closes the statement as a standalone word.
        A `case` or an `esac` at an argument position, one after a reserved
        word or `!` that is itself at an argument position included, is an
        ordinary word and opens or closes nothing, and so is one in a comment.
        A `case` inside backticks, an arithmetic expansion, double quotes or
        `${ ... }` is not read.

        The zsh brace form `case x { ... }` is read for every kind of shell
        that holds the string. A standalone `{` after the subject, decided on
        the characters with the continuation pairs left out and followed by a
        space, a tab, a newline or the end of the input, opens the statement
        in place of `in`, and the statement is at a pattern position; a quoted
        `{`, an escaped `{` and a `{` that is not a standalone word are no
        `in`. A brace-form statement closes in one of three ways: (a) a
        standalone, unquoted, unescaped `}` at a pattern position, decided
        like a pattern-position `esac`; (b) a standalone `esac` at a pattern
        position; (c) a standalone `}` read at a command position of the item
        body list itself while no `{ }` group is open in that body. Each
        brace-form statement keeps the depth of the `{ }` groups open in its
        item body: a standalone `{` read at a command position of the item
        body list itself raises it by one, and so does the standalone `{`
        right after `function` (a zsh anonymous function reads it as its
        name), and a standalone `}` read there lowers it by one while it is 1
        or more and closes the statement otherwise. A quoted or escaped `}` or
        `esac` starts a pattern at a pattern position and is an ordinary word
        in a body, and so is a `}` at an argument position. Braces inside
        quotes, escaped braces and braces inside `${ }`, substitutions,
        arithmetic, word parentheses, subshells and nested case statements are
        never counted: none of them is read at a command position of the body
        list itself, and a nested case statement keeps a form and a depth of
        its own. In the `in` form a `}` at a pattern position starts a pattern
        and a `}` in a body closes no statement.

        Comment after a pattern (rule 3). A `#` directly after the `)` that
        closes an item's pattern (no blank in between) starts a comment that
        runs to the end of the line: an `esac`, a `)` or a quote inside it
        closes nothing, ends no substitution and opens no quote, and after
        the newline the item body starts at a command position. A `#` after
        any other `)` keeps its reading.

        Where a comment starts (the `#` decision). At a site where a comment
        can start, a `#` starts a comment exactly when its effective previous
        character is a space, a tab, a newline, `;`, `&`, `|` or `(`, and that
        character is not escaped. Otherwise the `#` is a word character. The
        effective previous character is the character right before the `#`
        once every continuation pair directly in front of the `#` is left out,
        a run of several pairs included: in `: a`, a pair, `#x` it is the `a`,
        so the `#` is a word character, and in `: `, a pair, `#x` it is the
        space, so the `#` starts a comment. A character is escaped when it is
        the second character of a backslash pair, that is, when the run of
        backslashes directly in front of it has odd length: the `#` after an
        escaped blank, tab, `;`, `&`, `|` or `(` is a word character, and the
        `#` after a blank that follows an even run of backslashes (an escaped
        backslash, say) starts a comment. A `#` whose effective previous
        character is `)`, `<`, `>` or any other character stays a word
        character; the one exception is rule 3: in phase 7 a `)` that closes
        the pattern still lets the `#` start a comment. The sites are the
        start of a word and the comment branch of the command lists p and 8,
        a pattern, the outermost entry of the word list w and the waiting
        phases 1, 3, 4, 5 and 7, and all of them use this one decision. A `#`
        never starts a comment in a nested entry of w, a word parenthesis W,
        double quotes, backticks, `${ ... }` and the arithmetic contexts. The
        decision reads one value kept while reading, the comment-end position:
        the index of the newline that ended the last comment the reader read,
        or none before the first comment. Every branch that reads a comment
        records it in the same step, and a comment that runs to the end of the
        input records nothing. The newline that ends a comment is never part of
        a continuation pair: a backslash inside a comment is comment text, so a
        newline at the comment-end position is an unescaped newline in the
        look, whatever run of backslashes stands in front of it, and a `#` at
        the start of the next line starts a comment. Every other newline is
        classified as above. Apart from that position the decision is computed
        from the characters directly in front of the `#`: the look crosses only
        the continuation pairs directly in front of the `#` and the run of
        backslashes in front of the character it ends on, and every other
        character stops it, so the work summed over the skip stays within a
        constant times the length of the string (recording the position is one
        assignment per comment, and reading it one comparison per newline the
        look crosses). This bounded look is the only place where the characters
        in front of a `#` are looked at.

        Continuation pairs (rule 4). A continuation pair is a backslash
        directly followed by a newline. Where a case statement waits (before
        the subject, after the subject while `in` is awaited, at a pattern
        position, after a pattern's leading `(` and at the start of an item
        body) a pair is skipped without starting a word and the phase is
        kept. `case`, `in` and `esac` are decided on the characters with the
        pairs left out (`_keyword_end`, the pair-stripped keyword decision),
        and so is every other word whose identity changes the reading: the
        reserved words `then`, `do`, `else`, `elif`, `if`, `while`, `until`,
        `time`, `!` and `{`, the closing words `fi`, `done`, `}` and `]]`,
        `[[`, `function` and the head words `for`, `select`, `coproc` and
        `repeat`. Pairs between the characters of such a word and pairs
        directly after it are skipped, before the standalone-word check looks
        at the next character; a sequence that does not spell the keyword
        once the pairs are out is not a keyword; a pair inside a word never
        splits it. A keyword is matched only at the start of a word and looks
        at its own characters and at the runs of pairs between and after
        them; a failed match is not retried from inside the same word, the
        rest of that word is read once as an ordinary word, so the reading
        stays linear.

        Compound-command closings (rule 5). A closing inside a word and a
        compound-command closing are told apart. A closing inside a word goes
        on inside the word: the list is back in the state it had when the
        context opened, and the word after it is read as an argument. These
        are the close of a `$( )` or backquote substitution, the close of a
        quote, the close of `${ ... }`, and the `)` that closes a `(` that was
        not read at a command position (a zsh glob qualifier as in `x(N)`,
        `<(` and `>(`). A compound-command closing gives the next word a
        command position: the `)` that closes a `(` read at a command position
        (a subshell, and the `((` ... `))` arithmetic command); a standalone
        `]]` while a `[[` read as a standalone word at a command position is
        open in the same list, wherever it stands inside the conditional; the
        `esac` that closes a case statement, whether it is read in an item
        body or at a pattern position, which gives the list that holds the
        statement a command position; the `}` that closes a brace-form case
        statement, which gives the list that holds the statement a command
        position as `esac` does; and a standalone, unquoted `fi`, `done` or
        `}` read at a command position. A `]]` with no open `[[`, and a
        `fi`, `done` or `}` at an argument position, are ordinary words. A
        redirection after a closing and its target are read as before: the
        word after the target is not at a command position. The words inside
        `[[ ... ]]` are read as they were; the `[[` is tracked only to
        recognise its `]]`.

        Function heads, loop heads and coproc heads (rule 6). In `name()` the
        first word of a simple command (an ordinary word read at a command
        position) is followed, directly or after blanks, by `(`, only blanks
        and continuation pairs, and `)`: that `)` ends a function head and the
        next word is at a command position (`f() {`, `f () {`, and the same
        with a pair between the parentheses). Whether the parentheses are
        empty is decided by looking at the blanks and the continuation pairs
        between them once more, a bounded number of times; a `(` that does not
        form an empty `()` is read as any other `(`. A standalone, unquoted,
        unescaped `function`
        read at a command position starts a head: the next word is the name,
        an ordinary word that is never read as a keyword or reserved word, the
        word after the name is at a command position, and an empty `()`
        directly after the name or after blanks belongs to the head
        (`function f {`, `function f() {`); a `(` after the name that forms no
        empty `()` is a subshell read at a command position. An empty `()`
        right after `function`, with no name, ends the head of a zsh anonymous
        function as well (`function () {`). Multi-name zsh definitions and
        function-name validity are not considered. A loop or
        coproc head starts only from a standalone word that is unquoted,
        unescaped, read at a command position and spells the head word once
        the pairs are removed; the same word at an argument position, quoted
        or escaped starts no head, and neither does a `function` there. After
        `for` or `select` the next word is the name, an ordinary word that is
        never a keyword (`for case in x` opens no case), and the word after
        the name is at a command position (`for x do`, `select x do`); in
        `for x in a b; do`, `in` and the words after it are ordinary words up
        to the separator. A `((` directly after `for` (blanks allowed) is
        read as opened at a command position, so its `))` gives a command
        position (`for ((i=0;i<1;i++)) do`). In the zsh form `for name
        (words)`, which `for` alone has, a `(` directly after the name
        (blanks allowed) opens a word list: no word inside it is at a command
        position, so nothing in it opens a case statement, acts as a closing
        or starts a head, and its `)` gives the enclosing list a command
        position (`for x (a) {`). After `coproc` the next word is at a command
        position in every reading (`coproc {`, `coproc while`). When that word is
        an ordinary word (a NAME or a command name), the coproc NAME rule of the
        reading decides what follows: with the rule on, the word after it is at
        a command position as well (`coproc c {`); with the rule off, it is the
        first word of a simple command, so a `name()` may follow it, and the
        words after it are arguments (`coproc echo case x in x` opens no case
        statement). After the zsh `repeat` the next word, the count, is an
        ordinary word that is never read as a keyword, and the word after it
        is at a command position (`repeat 1 {`); `repeat` starts a head only
        under the zsh repeat rule of the reading, and without the rule it is an
        ordinary command word, the first word of a simple command, and the words
        after it are arguments (`repeat x case y in y` opens no case statement).
        The kind of the shell that holds the string sets the two rules
        (`parse`).

        Head states (rule 7). The head state of a list is one value out of a
        fixed small set: none; after a first word read at a command position
        (a possible `name()`; the ordinary word after `coproc` is one when the
        coproc NAME rule is off, and `repeat` is one when the zsh repeat rule is
        off); after `function`; after the function name; after `for`; after the
        `for` name; after `select`, or after `repeat` under the zsh repeat rule;
        after `coproc`. A head state lasts only until its head completes or the next
        character rules it out (for `name()`, anything other than blanks
        followed by `(`). A separator (`;`, `&`, `|`, a newline) or the end of
        the list ends any head state still pending, and the position after it
        follows rule 1.

        Heredoc operator (rule 8). Outside a case statement an unquoted `<<`
        that is not `<<<` does not make the chunk undecidable. The command
        list it stands in is marked as having a pending heredoc operator, and
        the word after the operator (the `<<-` form included) is read as an
        ordinary word at an argument position. No heredoc body is read. While
        any open list is marked, an unquoted newline in any context (a word
        parenthesis included, quoted text excluded) makes the chunk
        undecidable, because the body would start there. When the `)` that
        closes a marked list is reached, the mark is dropped and the list
        closes where it would without the operator, so `$(cat <<EOF)` closes at
        its `)`. The mark is one stack index and the newline check one test of
        the character being read, both made in the single forward pass: no `<<`
        looks ahead, so the reading stays linear. The rule is the same for a
        substitution inside double quotes and for the unquoted `$( ... )` of a
        delimiter's `${ ... }` range, which both go through this skip. A `<<`
        inside a case statement (its subject, its patterns, its item bodies and
        every list nested in them) stays undecidable. The brace form
        `case x { ... }` is no exception. `<<<` is a here-string and no
        heredoc, and in an arithmetic context (rule 9) a `<<` is a shift.

        Arithmetic command (rule 9). A `((` read at a command position (a `((`
        directly after `for` included; two parentheses with a blank between
        them are not this form) opens an arithmetic command, the context A. In
        it a `<<` is a left shift and no heredoc, nested parentheses are
        counted (the context a), and quotes and nested expansions are followed
        as everywhere else. A `)` that closes the command must be directly
        followed by a second `)`: the two close it, and the list that holds it
        is at a command position afterwards (the close of a `(` read at a
        command position). When the matching close is not `))`, or when the
        reading inside it stops undecidable, everything read since the `((` is
        dropped and the reader goes back to that `((` and reads it as two
        nested subshells, the reading a `(` at a command position has had. The
        re-read also restores the brace-form state: the form and the depth of
        the statements open at the `((` are what they were there, and the
        values of the statements opened after it go with their stack entries.
        The comment-end position of the `#` decision goes back to its value at
        the `((` as well. A `((` is read again at most once. The characters
        read again are summed over all the skips of one parser, and the sum may
        not exceed `ARITHMETIC_REREAD_FACTOR` (8) times the length of the
        string: the skip that would exceed it is undecidable. The arithmetic
        command, the second reading and the budget use the explicit stack and
        one list of the `((` that are open; nothing recurses, and the total
        work stays within a constant times the length of the string.

        Parenthesis in a word (rule 10). A `(` that is not read at a command
        position, in the middle of a word or at the start of a word at an
        argument position, opens a word parenthesis, the context W. The
        readings that stay: a `(` directly after `<`, `>` or `=` (`<(`, `>(`
        and `=(`), a function head `name()`, and the word list of `for name
        (words)`. The words of W never reach a command position, so a `case`,
        a closing word or a head means nothing in it. A `#` is a word character
        and starts no comment; `;`, `&`, `|` and a newline are word characters,
        neither separators nor undecidable (rule 8 apart); quotes, backslash
        pairs, `$( )`, `$(( ))`, `${ }` and backquotes are followed as in the
        other contexts. A `(` in W opens a nested W and a `)` closes the
        innermost one. When the outermost W closes, the list that holds it goes
        on in the state it had before the `(`, inside the same word.

        Raises _Undecidable when the chunk is not closed, or when its close
        cannot be located with certainty. A chunk with a case statement is
        undecidable for these forms: no `in`, and no standalone `{`, after the
        subject, no closing `esac` before the input ends, a `)` with no
        pattern at a pattern position, a heredoc anywhere in the chunk (item
        bodies included) once a case statement is open, an unmatched `)` in an
        item body, an unquoted `;` or `&` where a pattern must begin, an
        unquoted newline, `;` or `&` in a pattern outside its groups, an item
        terminator read while a `{ }` group is open in a brace-form item body,
        and an `esac` at a command position of a brace-form item body (zsh 5.9
        reports a parse error). Outside a case statement a heredoc operator is
        undecidable only when an unquoted newline follows it before the close
        of its list (rule 8).

        Contexts on the stack: p command list (`$(`, `(`), a arithmetic
        (`$((`) and the parentheses nested in an arithmetic command, A an
        arithmetic command (rule 9), W a parenthesis in a word (rule 10), w the
        word list of a zsh `for`, d double quotes, b backticks, k and K
        `${ ... }` outside and inside double quotes. A
        case statement is one entry above the context that holds its `case`,
        and its phase is the character of the entry: 1 before the subject, 2
        in the subject, 3 after the subject (waiting for `in` or a standalone
        `{`), 4 at a pattern position (right after `in`, right after the `{`
        of the brace form and right after an item terminator), 5
        after the optional leading `(`, 6 in a pattern, 7 at the start of an
        item body, 8 in an item body (a command list). g is a parenthesised
        group inside a subject or a pattern. In the phases 1, 3, 4, 5 and 7 a
        continuation pair is skipped and the first other character decides
        the phase change before it is read; phase 7 hands the first character
        of the body to phase 8, a command list that opens at a command
        position. The word list w opens at the `(` that follows the name of a
        zsh `for`, and it is read in a context of its own, not as the
        arithmetic a. A backslash pair, a quoted unit, a backtick, `$(`, `$((`
        and `${` in it are followed as in every other context. In the word
        list a `#` starts a comment only in the outermost entry: there the
        comment-start decision above applies, as it does in a command list, so
        the effective previous character decides, not the previous character
        alone. In a nested entry every `#` is a word character and starts no
        comment. The comment runs to the next newline, and a quote, a `)` or a
        substitution inside it opens nothing and closes nothing; a comment
        with no newline before the input ends makes the chunk undecidable.
        Every other character, the newline included, is part of a word or
        separates words; no word of the list is at a command position, so
        nothing in it opens a case statement, acts as a closing word or
        starts a head, and a newline gives the next word no command
        position. A `(` read in w opens a nested entry of w (a glob qualifier
        as in `*(N)`): its `)` is a closing inside a word, reading goes on in
        the enclosing list and nothing is given a command position. The one
        exception is a process substitution at the start of a word of the
        outermost entry: an unquoted, unescaped `<(`, `>(` or `=(` there opens
        a command list p instead of a nested entry, so a comment, a quote, a
        substitution or a case statement in it is read as in any command list
        and a `#` after a blank in it starts a comment. The `)` that closes
        that p is a closing inside a word: reading goes back to w and the
        characters after it are the rest of the same word. The start of a word
        is a state kept while reading, moved on before each character is read.
        The only look at the characters behind is the comment-start decision
        above, and it leaves this state as it is. A word starts at the
        position right after the `(` that opens the outermost entry and right
        after an unquoted, unescaped space, tab, newline, `;`, `&` or `|` (the
        newline that ends a comment included). An escaped character (an
        escaped space included) is a word character, and so are a quote, a
        substitution, a nested entry and any other character of a word. A
        continuation pair neither starts a word nor separates words, so it
        keeps the state. A `<(`, `>(` or `=(` in the middle of a word or
        inside a nested entry is read as any other `(` of w (`a=(`, `<->(`,
        `a(<(b))`, one whose `<`, `>` or `=` is escaped or quoted), a nested
        entry in which every `#` is a word character. The `)` that closes the
        outermost entry gives the list that holds the `for` a command position
        (`for x (a) {`). The context a is the arithmetic part of `$((` and the
        parentheses nested in an arithmetic command, and its reading is
        unchanged.
        A second list `saved` runs beside the stack, one entry for
        each stack entry: the state the list under it had when the entry was
        pushed and whether its close gives that list a command position.
        """
        s, n = self.s, self.n
        if s[start] == "`":
            stack = ["b"]
            j = start + 1
        elif s.startswith("$((", start):
            stack = ["p", "a"]
            j = start + 3
        else:
            stack = ["p"]
            j = start + 2
        # The state of the command list on top of the stack (rules 1, 5, 6 and
        # 7): `at_command` is whether the next word is at a command position,
        # `in_word` whether a word is being read, `dbl` whether a `[[` read at
        # a command position is still open in the list and `head` its head
        # state. `saved` holds, for each entry of the stack, the three values
        # `at_command`, `dbl` and `head` the list under it had when the entry
        # was pushed, and whether the close of the entry gives that list a
        # command position. A closing inside a word brings the three values
        # back and the list goes on inside its word; a compound-command
        # closing brings `dbl` back and puts the list at a command position.
        at_command, in_word = True, False
        dbl, head = False, HEAD_NONE
        # The state of the outermost entry of a word list w (the `(` branch and
        # the w branch below): there `in_word` is false at the start of a word,
        # and `procsub` is true while the character just read is an unquoted,
        # unescaped `<`, `>` or `=` that was read at the start of a word, so a
        # `(` right after it opens a process substitution.
        procsub = False
        # The entries of the contexts the chunk opens with stand for a list
        # that is inside a word: the `)` that closes the arithmetic part of a
        # `$((` gives back a list that goes on inside its word.
        saved = [(False, False, HEAD_NONE, False)] * len(stack)
        # The lists with a pending heredoc operator (rule 8), as stack indices,
        # innermost last; the number of case statements open on the stack; the
        # command-position `((` open as an arithmetic command (rule 9), with what
        # is needed to read each again as two subshells, innermost last; and the
        # positions of the `((` that have been read again.
        marks, cases, arith, fallen = [], 0, [], set()
        # The brace-form state of the case statements open on the stack (rule 2):
        # one value for each, innermost last, so the list is as long as `cases`.
        # The value is None for a statement in the `in` form; for a statement in
        # the brace form it is the depth, the number of `{ }` groups open in its
        # item body. A value is made when the statement's entry is pushed and
        # dropped when the entry is popped, so a nested statement has a value of
        # its own. The value that is read and changed is the innermost one, and
        # only while the entry of that statement is on top of the stack.
        braces = []
        # The comment-end position (the `#` decision): the index of the newline
        # that ended the last comment the reader read, -1 before the first. Every
        # branch that reads a comment sets it to the index of the newline that
        # ends that comment, in the same step; a comment that runs to the end of
        # the input leaves it as it is (the chunk is undecidable then). The
        # decision asks it through `_hash_starts_comment`: a newline at this index
        # ends a comment and is never part of a continuation pair. It is an
        # absolute index into the string, it is not part of the per-entry state in
        # `saved`, and the re-read of a `((` (rule 9) restores it.
        comment_end = -1
        while True:
            try:
                while j < n:
                    top = stack[-1]
                    ch = s[j]
                    # The outermost entry of w keeps, while it reads, whether the next
                    # character starts a word and whether it follows an unquoted,
                    # unescaped `<`, `>` or `=` read at the start of a word; the state
                    # is moved on here, before the character is read, and is never
                    # rebuilt by looking at the characters behind. A space, a tab, a
                    # newline (the one that ends a comment included), `;`, `&` and `|`
                    # separate words, and a word starts right after the `(` that opens
                    # the entry. Every other character is in a word: an escaped
                    # character (an escaped space included), the opening of a quote or
                    # of a substitution, a nested entry and a plain word character; so
                    # is the return from a nested context (`in_word` is set when it
                    # closes). A continuation pair, a backslash directly followed by a
                    # newline, neither starts a word nor separates words, so it keeps
                    # the state as it was. A `#` is not decided from this state: the
                    # w branch below asks the comment-start decision
                    # (`_hash_starts_comment`), which looks at the characters directly
                    # in front of the `#` and gives the same answer, since it leaves a
                    # continuation pair out and treats an escaped character as a word
                    # character.
                    opens_process = False
                    if top == "w" and stack[-2] != "w":
                        opens_process = procsub
                        if ch == "\\" and s.startswith("\n", j + 1):
                            pass
                        elif ch in " \t\n;&|":
                            in_word, procsub = False, False
                        else:
                            procsub = ch in "<>=" and not in_word
                            in_word = True
                    if ch == "\n" and marks and top not in "dK":
                        # An unquoted newline while a list has a pending heredoc
                        # operator: the body would start here and is never read.
                        raise _Undecidable("heredoc in a substitution")
                    # The word-start test of the lists p and 8. A `#` that starts a
                    # comment (the comment-start decision, `_hash_starts_comment`)
                    # begins no word: the general comment branch below asks the same
                    # question about the same `#` in the same step, with the same
                    # comment-end position, so the two agree.
                    if (
                        top in "p8"
                        and not in_word
                        and ch not in " \t\n;&|()<>"
                        and not (ch == "\\" and s.startswith("\n", j + 1))
                        and not (ch == "#" and self._hash_starts_comment(j, comment_end))
                    ):
                        # A word begins here. A keyword, a reserved word, a closing
                        # word or a head word is decided once, on the characters that
                        # start the word; any other word is read as an ordinary word,
                        # which is not looked at again.
                        named, head = head, HEAD_NONE
                        if named in (HEAD_FUNCTION, HEAD_FOR, HEAD_NAME):
                            # The name of a function, a loop or a repeat count is an
                            # ordinary word, never a keyword; the word after it is at
                            # a command position.
                            at_command, in_word = True, True
                            if named == HEAD_FUNCTION:
                                head = HEAD_FUNCTION_NAME
                                if (
                                    top == "8"
                                    and braces[-1] is not None
                                    and self._keyword_end(j, "{", " \t\n") != -1
                                ):
                                    # The `{` of zsh's anonymous function
                                    # `function { ... }` stands where the name does
                                    # and is read as the name, but it opens a group
                                    # all the same: its `}` is read at a command
                                    # position and must not close the statement.
                                    braces[-1] += 1
                            elif named == HEAD_FOR:
                                head = HEAD_FOR_NAME
                        else:
                            was_command = at_command
                            kind, end = self._read_command_word(j, at_command, top == "8", dbl)
                            if kind == "case":
                                stack.append("1")
                                saved.append((at_command, dbl, HEAD_NONE, False))
                                cases += 1
                                braces.append(None)
                                j = end
                                continue
                            if kind == "esac":
                                if braces[-1] is not None:
                                    # An `esac` at a command position of a brace-form
                                    # item body closes nothing (zsh 5.9 reports a
                                    # parse error): the close is not certain.
                                    raise _Undecidable("esac in a brace-form case body")
                                stack.pop()
                                dbl = saved.pop()[1]
                                cases -= 1
                                braces.pop()
                                at_command, in_word = True, False
                                j = end
                                continue
                            if kind == "reserved":
                                if top == "8" and braces[-1] is not None:
                                    # A `{` or a `}` read at a command position of the
                                    # item body list itself, in a brace-form statement
                                    # (a list nested in the body is another entry of
                                    # the stack and never gets here): a `{` opens a
                                    # group, a `}` closes the innermost open group and,
                                    # with none open, closes the statement. The words
                                    # are told apart by their first character: `{` and
                                    # `}` are the only reserved words that start with
                                    # one.
                                    if ch == "{":
                                        braces[-1] += 1
                                    elif ch == "}":
                                        if braces[-1] > 0:
                                            braces[-1] -= 1
                                        else:
                                            stack.pop()
                                            dbl = saved.pop()[1]
                                            cases -= 1
                                            braces.pop()
                                            at_command, in_word = True, False
                                j = end
                                continue
                            if kind == "dbl_open":
                                dbl = True
                                at_command, in_word = False, False
                                j = end
                                continue
                            if kind == "dbl_close":
                                dbl = False
                                at_command, in_word = True, False
                                j = end
                                continue
                            if kind is not None:
                                # A head word: `function`, `for`, `select`, `coproc`
                                # or `repeat`.
                                head = HEAD_AFTER_WORD[kind]
                                at_command, in_word = kind == "coproc", False
                                j = end
                                continue
                            at_command, in_word = False, True
                            if was_command:
                                if named == HEAD_COPROC and self.coproc_name:
                                    # The coproc NAME rule: the ordinary word after
                                    # `coproc` is a NAME and the next word is at a
                                    # command position.
                                    at_command = True
                                else:
                                    # The first word of a simple command; after
                                    # `coproc` without the NAME rule that word is the
                                    # command and the words after it are arguments.
                                    head = HEAD_FIRST
                    if top in "13457":
                        # A case statement that waits for a word, for `in` or, after
                        # the subject, for the `{` of zsh's brace form.
                        if ch in " \t\n":
                            j += 1
                        elif ch == "\\" and s.startswith("\n", j + 1):
                            j += 2
                        elif ch == "#" and self._hash_starts_comment(
                            j, comment_end, ")" if top == "7" else ""
                        ):
                            # The comment-start decision of every site. In phase 7 the
                            # `)` that closes the pattern also lets a `#` start a
                            # comment (rule 3), with continuation pairs left out as
                            # everywhere else. The newline that ends the comment is
                            # recorded as the comment-end position in the same step.
                            j = s.find("\n", j)
                            if j == -1:
                                raise _Undecidable("substitution")
                            comment_end = j
                        elif top == "3":
                            end = self._keyword_end(j, "in", " \t\n;&|()<>")
                            if end == -1:
                                # No `in`: a standalone `{` (decided on the
                                # characters with the continuation pairs left out,
                                # followed by a blank or the end of the input) opens
                                # zsh's brace form in its place, with no group open.
                                # A quoted or escaped `{` and a `{` that is not a
                                # standalone word are no `in` either.
                                end = self._keyword_end(j, "{", " \t\n")
                                if end == -1:
                                    raise _Undecidable("case without in")
                                braces[-1] = 0
                            stack[-1] = "4"
                            j = end
                        elif top == "1":
                            if ch in ";&|)":
                                raise _Undecidable("case without a subject")
                            stack[-1] = "2"
                        elif top == "4":
                            end = self._keyword_end(j, "esac", " \t\n;&|)<>")
                            if end == -1 and braces[-1] is not None:
                                # In the brace form a standalone, unquoted `}` at a
                                # pattern position closes the statement as `esac`
                                # does; in the `in` form it starts a pattern.
                                end = self._keyword_end(j, "}", " \t\n;&|)<>")
                            if end != -1:
                                stack.pop()
                                dbl = saved.pop()[1]
                                cases -= 1
                                braces.pop()
                                at_command, in_word, head = True, False, HEAD_NONE
                                j = end
                            elif ch in ");&":
                                raise _Undecidable("case pattern")
                            elif ch == "(":
                                stack[-1] = "5"
                                j += 1
                            else:
                                stack[-1] = "6"
                        elif top == "5":
                            if ch in ");&":
                                raise _Undecidable("case pattern")
                            stack[-1] = "6"
                        else:
                            # Phase 7: the item body starts at a command position.
                            stack[-1] = "8"
                            at_command, in_word, dbl, head = True, False, False, HEAD_NONE
                    elif ch == "\\":
                        j += 2
                    elif top == "b":
                        j += 1
                        if ch == "`":
                            stack.pop()
                            frame = saved.pop()
                            if not stack:
                                return j
                            at_command, dbl, head, _ = frame
                            in_word = True
                    elif ch == "`":
                        stack.append("b")
                        saved.append((at_command, dbl, head, False))
                        j += 1
                    elif ch == '"':
                        if top == "d":
                            stack.pop()
                            at_command, dbl, head, _ = saved.pop()
                            in_word = True
                        else:
                            stack.append("d")
                            saved.append((at_command, dbl, head, False))
                        j += 1
                    elif s.startswith("$((", j):
                        stack.extend(("p", "a"))
                        saved.extend(((at_command, dbl, head, False),) * 2)
                        j += 3
                    elif s.startswith("$(", j):
                        stack.append("p")
                        saved.append((at_command, dbl, head, False))
                        at_command, in_word, dbl, head = True, False, False, HEAD_NONE
                        j += 2
                    elif s.startswith("${", j):
                        stack.append("K" if top in "dK" else "k")
                        saved.append((at_command, dbl, head, False))
                        j += 2
                    elif top == "d":
                        j += 1
                    elif ch == "}" and top in "kK":
                        stack.pop()
                        at_command, dbl, head, _ = saved.pop()
                        in_word = True
                        j += 1
                    elif top == "K":
                        j += 1
                    elif ch == "'":
                        j = s.find("'", j + 1)
                        if j == -1:
                            raise _Undecidable("quote")
                        j += 1
                    elif s.startswith("$'", j):
                        j += 2
                        while j < n and s[j] != "'":
                            j += 2 if s[j] == "\\" else 1
                        j += 1
                    elif top == "k":
                        j += 1
                    elif top in "26g":
                        # The subject of a case statement, a pattern, or a
                        # parenthesised group inside either.
                        if ch == "(":
                            stack.append("g")
                            saved.append((at_command, dbl, head, False))
                            j += 1
                        elif ch == ")":
                            if top == "2":
                                raise _Undecidable("case without in")
                            if top == "6":
                                stack[-1] = "7"
                            else:
                                stack.pop()
                                saved.pop()
                            j += 1
                        elif s.startswith("<<<", j):
                            j += 3
                        elif s.startswith("<<", j):
                            raise _Undecidable("heredoc in a substitution")
                        elif top == "g":
                            j += 1
                        elif top == "2":
                            if ch in "<>" and s.startswith("(", j + 1):
                                stack.append("p")
                                saved.append((at_command, dbl, head, False))
                                at_command, in_word, dbl, head = True, False, False, HEAD_NONE
                                j += 2
                            elif ch in " \t\n":
                                stack[-1] = "3"
                                j += 1
                            elif ch in ";&|":
                                raise _Undecidable("case without in")
                            else:
                                j += 1
                        elif ch in "\n;&":
                            raise _Undecidable("case pattern")
                        elif ch == "#" and self._hash_starts_comment(j, comment_end):
                            # A comment in a pattern starts by the comment-start
                            # decision of every site; a `#` in a group g was read as a
                            # word character above and never gets here. The newline
                            # that ends the comment is recorded as the comment-end
                            # position in the same step.
                            j = s.find("\n", j)
                            if j == -1:
                                raise _Undecidable("substitution")
                            comment_end = j
                        else:
                            j += 1
                    elif ch == "(":
                        kind_char, close_command, width = ("p" if top == "8" else top), False, 1
                        if top == "A":
                            # A parenthesis inside an arithmetic command is counted.
                            kind_char = "a"
                        elif top not in "awW":
                            if head in (HEAD_FIRST, HEAD_FUNCTION, HEAD_FUNCTION_NAME):
                                end = self._empty_parens_end(j)
                                if end != -1:
                                    # A function head, `name()`, `function name()` or
                                    # the anonymous `function ()`: the next word is at
                                    # a command position.
                                    at_command, in_word, head = True, False, HEAD_NONE
                                    j = end
                                    continue
                            # Whether this `(` is read at a command position decides
                            # what its `)` gives; a `((` after `for` counts as read
                            # at one.
                            close_command = at_command or head == HEAD_FOR
                            if head == HEAD_FOR_NAME:
                                # The zsh word list of a `for`: a context of its own
                                # (w). No word of it is at a command position, and its
                                # `)` closes a head. A `(` read inside it opens a
                                # nested entry of the same kind, whose `)` closes
                                # inside a word.
                                kind_char, close_command = "w", True
                            elif close_command:
                                if s.startswith("((", j) and j not in fallen:
                                    # An arithmetic command, until its `))` shows
                                    # otherwise (rule 9): what a second reading from
                                    # this `((` needs is kept.
                                    arith.append(
                                        (
                                            len(stack), j, at_command, in_word, dbl, head,
                                            cases, len(marks), comment_end,
                                        )
                                    )
                                    kind_char, width = "A", 2
                            elif s[j - 1] not in "<>=":
                                # A parenthesis in a word, not a process substitution
                                # or `=(` (rule 10): nothing in it is a command.
                                kind_char = "W"
                        elif opens_process:
                            # An unquoted, unescaped `<(`, `>(` or `=(` read at the
                            # start of a word of the outermost entry of w (`opens_process`
                            # is set only there) is a process substitution: it opens a
                            # command list p, read as in any command list, so a `#`
                            # after a blank in it starts a comment. Its `)` is a closing
                            # inside a word (`close_command` stays False): reading goes
                            # back to w and the characters after it are the rest of the
                            # same word. Any other `(` of w, one in the middle of a
                            # word, in a nested entry or after an escaped or quoted `<`,
                            # `>` or `=` included, opens a nested entry of w above.
                            kind_char = "p"
                        stack.append(kind_char)
                        saved.append((at_command, dbl, HEAD_NONE, close_command))
                        at_command, in_word, dbl, head = True, False, False, HEAD_NONE
                        j += width
                    elif ch == ")":
                        if top == "8":
                            raise _Undecidable("unmatched parenthesis in a case body")
                        if top == "A":
                            # The close of an arithmetic command is `))`; anything
                            # else sends the reader back to its `((`.
                            if not s.startswith("))", j):
                                raise _Undecidable("arithmetic command")
                            arith.pop()
                            j += 1
                        stack.pop()
                        at_command, dbl, head, close_command = saved.pop()
                        if marks and marks[-1] == len(stack):
                            marks.pop()
                        j += 1
                        if not stack:
                            return j
                        if close_command:
                            at_command, in_word, head = True, False, HEAD_NONE
                        else:
                            in_word = True
                    elif top in "aAW":
                        j += 1
                    elif top == "w":
                        # The word list of a zsh `for`: in the outermost entry a `#`
                        # starts a comment by the comment-start decision of a command
                        # list (`_hash_starts_comment`: the effective previous
                        # character, with continuation pairs left out, is a blank, a
                        # tab, a newline, `;`, `&`, `|` or `(` and is not escaped); in
                        # a nested entry (a glob qualifier as in `*(#qN)`, the entry
                        # directly beneath this one is also w) every `#` is a word
                        # character. Every other character is part of a word or
                        # separates words, the newline included. Where a word starts
                        # in the outermost entry is the state `in_word` moved on at
                        # the top of the loop (an escaped space is a word character, a
                        # continuation pair separates no word); a process substitution
                        # at the start of a word is opened in the `(` branch. The
                        # newline that ends a comment is recorded as the comment-end
                        # position in the same step.
                        if (
                            ch == "#"
                            and stack[-2] != "w"
                            and self._hash_starts_comment(j, comment_end)
                        ):
                            j = s.find("\n", j)
                            if j == -1:
                                raise _Undecidable("substitution")
                            comment_end = j
                        else:
                            j += 1
                    elif ch == "#" and self._hash_starts_comment(j, comment_end):
                        # A comment runs to the end of the line. It starts by the
                        # comment-start decision, the one the word-start test above
                        # used for this same `#`: a `#` after a word character, an
                        # escaped blank or a continuation pair that follows a word
                        # character is a word character and gets here as none. The
                        # newline that ends the comment is recorded as the
                        # comment-end position in the same step.
                        j = s.find("\n", j)
                        if j == -1:
                            raise _Undecidable("substitution")
                        comment_end = j
                    elif s.startswith("<<<", j):
                        at_command, in_word, head = False, False, HEAD_NONE
                        j += 3
                    elif s.startswith("<<", j):
                        if cases:
                            raise _Undecidable("heredoc in a substitution")
                        # A heredoc operator outside a case statement (rule 8): its
                        # list is marked, no body is read, and the word after the
                        # operator is an ordinary word.
                        if not marks or marks[-1] != len(stack) - 1:
                            marks.append(len(stack) - 1)
                        at_command, in_word, head = False, False, HEAD_NONE
                        j += 2
                    elif top == "8" and ch == ";" and s.startswith((";;", ";&", ";|"), j):
                        # An item terminator; `;;&` is the longest of them. In the
                        # brace form it ends an item only with no `{ }` group open
                        # in the body: inside a group it is a syntax error, and the
                        # close of the statement is not certain.
                        if braces[-1]:
                            raise _Undecidable("item terminator in a brace group")
                        stack[-1] = "4"
                        j += 3 if s.startswith(";;&", j) else 2
                    elif ch in " \t":
                        in_word = False
                        j += 1
                    elif ch in "\n;&|":
                        at_command, in_word, head = True, False, HEAD_NONE
                        j += 1
                    elif ch in "<>":
                        at_command, in_word, head = False, False, HEAD_NONE
                        j += 1
                    else:
                        j += 1
                raise _Undecidable("substitution")
            except _Undecidable:
                # An arithmetic command that cannot be read to its `))` is read
                # again, once, from its `((` as two nested subshells; with none
                # open the chunk is undecidable.
                if not arith:
                    raise
                (
                    index, opened, at_command, in_word, dbl, head, cases, held, comment_end
                ) = arith.pop()
                # A scan that found no end left `j` at -1: it had read to the end.
                self.arith_budget -= (n if j < opened else min(j, n)) - opened
                if self.arith_budget < 0:
                    raise
                fallen.add(opened)
                del stack[index:], saved[index:], marks[held:]
                # The brace-form state of rule 2 goes back to its value at the `((`:
                # the values of the statements opened after it go with their stack
                # entries (`cases` is the count at the `((`), and the statements
                # open at the `((` lie under the arithmetic command on the stack,
                # where nothing reads or changes their values, so they still hold
                # what they held there.
                del braces[cases:]
                # The comment-end position goes back to its value at the `((` as
                # well (it is kept in the record of the `((`): a comment read after
                # the `((` in the reading that failed may not be one in the second
                # reading.
                j = opened

    def _keyword_end(self, j, word, follow):
        """Return the index where reading goes on after the keyword `word`
        that begins at `j`, or -1 when `word` is not the keyword there. The
        decision is made on the characters with the continuation pairs (a
        backslash directly followed by a newline) left out, the pair-stripped
        rule: the pairs between the keyword's characters and the pairs directly
        after it are skipped, then the next character must be one of `follow`
        or the input must end, so the keyword is a standalone word. A sequence
        that does not spell `word` once the pairs are out (`ca`, a pair, `sex`)
        is not a keyword. The rule is the one for every word whose identity
        changes the reading: `case`, `in` and `esac`, the reserved words, the
        closing words `fi`, `done`, `}` and `]]`, `[[`, `function` and the head
        words `for`, `select`, `coproc` and `repeat`. The caller calls it at the
        start of a word only. It looks at the characters of `word` and at the
        runs of pairs between and after them, nothing else, and never calls
        back into the skip."""
        s, n = self.s, self.n
        k = j
        for letter in word:
            while s.startswith("\\\n", k):
                k += 2
            if k >= n or s[k] != letter:
                return -1
            k += 1
        while s.startswith("\\\n", k):
            k += 2
        if k < n and s[k] not in follow:
            return -1
        return k

    def _hash_starts_comment(self, j, comment_end, closer=""):
        """Return whether the `#` at `j` starts a comment: the one
        comment-start decision of the substitution skip, used at every site
        where a comment can start. The effective previous character is the
        character right before the `#` once every continuation pair directly
        in front of it is left out, a run of several pairs included. The `#`
        starts a comment exactly when that character is a space, a tab, a
        newline, `;`, `&`, `|` or `(` (or one of the characters of `closer`,
        the `)` of a pattern in phase 7) and is not escaped; any other
        effective previous character, `)`, `<` and `>` included, makes the `#`
        a word character. A character is escaped when the run of backslashes
        directly in front of it has odd length. A newline whose run is odd is
        a continuation pair and is left out together with its backslash; a
        newline whose run is even is an ordinary newline. The newline that
        ends a comment is never part of a continuation pair: a backslash
        inside a comment is comment text, so a newline at `comment_end`, the
        comment-end position (the index of the newline that ended the last
        comment the reader read, -1 before the first), is an unescaped
        newline whatever run of backslashes stands in front of it; the look
        stops there and the `#` starts a comment. The look crosses only the
        continuation pairs directly in front of the `#` and the run of
        backslashes in front of the character it ends on, every other
        character stops it, and a `#` further on is such a character, so the
        looks of two `#` never overlap and the work summed over a skip stays
        within a constant times the length of the string; the position costs
        one comparison per newline the look crosses. It reads the position it
        is given, writes nothing, raises nothing and calls no other method."""
        s = self.s
        follow = " \t\n;&|(" + closer
        k = j - 1
        while k >= 0 and s[k] in follow:
            if k == comment_end:
                return True
            b = k - 1
            while b >= 0 and s[b] == "\\":
                b -= 1
            if (k - 1 - b) % 2 == 0:
                return True
            if s[k] != "\n":
                return False
            k -= 2
        return False

    def _empty_parens_end(self, j):
        """Return the index just after the `)` of an empty `()` whose `(` is
        at `j`, or -1 when the parentheses are not empty: only spaces, tabs
        and continuation pairs (a backslash directly followed by a newline)
        lie between them. A pair is skipped together with its newline. The
        parentheses are not empty, and the result is -1, when the input ends
        inside that run (after a pair, or at a backslash with nothing after
        it), when a backslash is followed by any character other than a
        newline, and when any other character stops the run. What the run
        skips is read once here and once more by the caller when it reads the
        `(` as any other `(`, so the check costs constant extra time per
        character. It keeps no state, raises nothing and calls nothing."""
        s, n = self.s, self.n
        k = j + 1
        while k < n:
            if s[k] in " \t":
                k += 1
            elif s[k] == "\\" and k + 1 < n and s[k + 1] == "\n":
                k += 2
            else:
                break
        if k < n and s[k] == ")":
            return k + 1
        return -1

    def _read_command_word(self, j, at_command, in_body, in_dbl):
        """Decide the word that begins at `j` in a command list of the chunk
        and return (kind, end). `at_command` is the command position state
        of the list, `in_body` whether the list is an item body and `in_dbl`
        whether a `[[` read at a command position is open in it. The kind is
        "case" for a `case` that opens a statement (a standalone `case` at a
        command position), "esac" for an `esac` that closes one (a standalone
        `esac` at a command position of an item body), "reserved" for a
        standalone word of `COMMAND_POSITION_WORDS` read at a command
        position (the reserved words, `!`, `{` and the closing words `fi`,
        `done` and `}`), which leaves the next word at a command position,
        "dbl_open" for a standalone `[[` at a command position, "dbl_close"
        for a standalone `]]` while a `[[` is open, the head word itself
        (`function`, `for`, `select`, `coproc` or `repeat`) for a standalone
        head word at a command position, and None for every other word (end
        is `j` then). `repeat` is a head word only under the zsh repeat rule
        (`zsh_repeat`); without the rule it is an ordinary word and the kind is
        None. `select`, `for` and `function` are head words in every
        reading. `end` is where reading goes on. Every word is decided
        by `_keyword_end`, on the characters with the continuation pairs left
        out, so a word at an argument position is never one of them, and
        neither is a quoted or escaped one. The caller calls it once at the
        start of each word."""
        s = self.s
        ch = s[j]
        if in_dbl and ch == "]":
            end = self._keyword_end(j, "]]", " \t\n;&|()<>")
            if end != -1:
                return "dbl_close", end
        if not at_command:
            return None, j
        if ch == "c":
            end = self._keyword_end(j, "case", " \t\n")
            if end != -1:
                return "case", end
        elif ch == "e" and in_body:
            end = self._keyword_end(j, "esac", " \t\n;&|)<>")
            if end != -1:
                return "esac", end
        elif ch == "[":
            end = self._keyword_end(j, "[[", " \t\n")
            if end != -1:
                return "dbl_open", end
        for word in COMMAND_POSITION_WORDS:
            if word[0] == ch:
                end = self._keyword_end(j, word, " \t\n" if word in ("!", "{") else " \t\n;&|()<>")
                if end != -1:
                    return "reserved", end
        for word in HEAD_AFTER_WORD:
            if word == "repeat" and not self.zsh_repeat:
                continue
            if word[0] == ch:
                end = self._keyword_end(j, word, " \t\n;&|()<>")
                if end != -1:
                    return word, end
        return None, j

    def _dollar(self):
        s, i = self.s, self.i
        nxt = s[i + 1] if i + 1 < self.n else ""
        # At the delimiter position the `${` and the `$'` / `$"` get their own
        # reading; everywhere else the readings below stay as they were.
        delimiter = self._at_delimiter()
        if nxt == "(":
            end = self._skip_parens(i + 1)
            self._put(s[i:end], quoted=True, dynamic=True)
            self.i = end
        elif nxt == "{" and delimiter:
            # The range from the `${` to its close is read as it is found, in
            # one scan, into both forms of the delimiter word: the quote-removed
            # text, which adds to the word as it always did, and the bash form,
            # the range's original characters, which adds to the word's bash
            # form (`bash_buf`). `_finish_word` registers one of the two.
            text, self.i, bash_text, _ =self._remove_range_quotes(i, self.n, braced=True)
            self._put(text, quoted=True, dynamic=True, bash_text=bash_text)
            self.has_range = True
        elif nxt in ("'", '"') and delimiter:
            # What zsh reads here is not known, so no delimiter is registered.
            raise _Undecidable("dollar quote")
        elif nxt == "{":
            end = s.find("}", i + 2)
            if end == -1:
                raise _Undecidable("brace")
            self._put(s[i:end + 1], quoted=True, dynamic=True)
            self.i = end + 1
        elif nxt == "'":
            j = i + 2
            while j < self.n and s[j] != "'":
                j += 2 if s[j] == "\\" else 1
            if j >= self.n:
                raise _Undecidable("quote")
            self._put(s[i:j + 1], quoted=True, dynamic=True)
            self.i = j + 1
        elif nxt == '"':
            self.i += 1
        else:
            self._put("$", dynamic=True)
            self.i += 1

    def _redirection(self):
        s, i = self.s, self.i
        ch = s[i]
        if i + 1 < self.n and s[i + 1] == "(":
            # Process substitution: its value is unknown.
            end = self._skip_parens(i + 1)
            self._put(s[i:end], quoted=True, dynamic=True)
            self.i = end
            return
        # The file descriptor named by a digit-only word right before the
        # operator, as its digits without leading zeros ("" is fd 0); None when
        # the operator has no fd word. The word is never converted to a number,
        # so its length costs nothing and raises nothing.
        fd = None
        if self.started and self.digits and self.buf:
            word = "".join(self.buf).lstrip("0")
            if len(word) < 10 or (len(word) == 10 and word <= MAX_FD):
                fd = word
                self._reset_word()
            else:
                # Past the largest fd: an ordinary operand, and the redirect
                # binds to the default fd of its operator.
                self._finish_word()
        else:
            self._finish_word()
        if ch == "<":
            for op in ("<<<", "<<-", "<<", "<&", "<>"):
                if s.startswith(op, i):
                    break
            else:
                op = "<"
        else:
            for op in (">>", ">&", ">|"):
                if s.startswith(op, i):
                    break
            else:
                op = ">"
        self.i = i + len(op)
        self.redirected = True
        if fd == "" or (fd is None and ch == "<"):
            self.stdin = True
            if self.after_group is not None:
                self.after_group.stdin = True
        self.redirect = (op in ("<<", "<<-"), op == "<<-")

    def _closing_backquote(self, start):
        """Return the index of the backquote that closes the span opened by the
        unquoted backquote at `start`. The scan goes forward from the character
        after the opening backquote, and a backslash and the single character
        after it are one pair that never closes the span, whatever that
        character is; this is the pair rule of the backtick context of
        `_skip_substitution`. The first backquote outside a pair closes the
        span, so one after an even run of backslashes (none included) closes it
        and one after an odd run does not. Raises _Undecidable when no such
        backquote is left, a lone backslash at the end of the text included.
        One pass, constant work per character."""
        s, n = self.s, self.n
        j = start + 1
        while j < n:
            ch = s[j]
            if ch == "`":
                return j
            j += 2 if ch == "\\" else 1
        raise _Undecidable("quote")

    def parse(self):
        s = self.s
        try:
            while self.i < self.n:
                i = self.i
                ch = s[i]
                if ch in " \t":
                    self._finish_word()
                    self.i += 1
                elif ch == "\n":
                    self.i += 1
                    self._separator("\n")
                    if self.heredocs:
                        self._read_heredocs()
                    # A checkpoint (FR2): a newline the reader itself reads here, with
                    # no group open, no pipe pending, no list continuation pending and
                    # the heredoc bodies of the line read through their terminators (an
                    # unterminated body raised above). Two counts are all it keeps.
                    if not self.frames and not self.pipe_pending and not self.list_pending:
                        self.checkpoint = (len(self.commands), len(self.groups))
                elif ch == "#" and not self.started and not (
                    self.frames and self.frames[-1].comment_exception
                ):
                    # A comment, unless the innermost open group has the comment
                    # exception: then the `#` falls through to the word characters
                    # below. Only the innermost group is read, so it costs constant
                    # time.
                    end = s.find("\n", i)
                    self.i = self.n if end == -1 else end
                elif ch in "\\'\"":
                    # A backslash pair, a single-quoted unit and a double-quoted
                    # unit are all read by the one quoted-unit reader.
                    text, self.i, dynamic = self._read_quoted_unit(i, self.n)
                    # A backslash and a newline add nothing and start no word; an
                    # empty quote pair adds nothing either, but it starts one.
                    if ch != "\\" or s[i + 1] != "\n":
                        self._put(text, quoted=True, dynamic=dynamic)
                        # A quote unit read for the word, outside any `${ ... }`
                        # range of a delimiter (those are read by `_dollar`).
                        self.outside_quote = True
                elif ch == "$":
                    self._dollar()
                elif ch == "`":
                    end = self._closing_backquote(i)
                    self._put(s[i:end + 1], quoted=True, dynamic=True)
                    self.i = end + 1
                elif ch == ";":
                    self.i += 1
                    self._separator(";")
                elif ch == "&":
                    if s.startswith("&>", i):
                        self._finish_word()
                        self.i += 3 if s.startswith("&>>", i) else 2
                        self.redirected = True
                        self.redirect = (False, False)
                    elif s.startswith("&&", i):
                        self.i += 2
                        self._separator("&&")
                    else:
                        self.i += 1
                        self._separator("&")
                elif ch == "|":
                    if s.startswith("||", i):
                        self.i += 2
                        self._separator("||")
                    elif s.startswith("|&", i):
                        self.i += 2
                        self._separator("|&")
                    else:
                        self.i += 1
                        self._separator("|")
                elif ch == "(":
                    if self._in_arguments():
                        self._read_argument_parens()
                    else:
                        self.i += 1
                        self._open_group("(")
                elif ch == ")":
                    self.i += 1
                    self._close_paren()
                elif ch in "<>":
                    self._redirection()
                else:
                    self._put(ch)
                    self.i += 1
            # The end of the input ends the command in progress; it is no newline
            # the input held, so it is no group's first separator.
            self._flush()
            if self.heredocs:
                raise _Undecidable("heredoc")
            self._rescue_argument_groups()
            if self.frames:
                raise _Undecidable("group")
        except _Undecidable as error:
            # The string cannot be read to its end. The commands up to the last
            # checkpoint are settled and carried on the exception, which is raised
            # on as it is: the groups opened before the checkpoint are all closed
            # (no group was open at it) and every attribute that feeds connection
            # and skip is final, so each carried command takes the connected and
            # skipped values a full read would give it. With no checkpoint the
            # counts are (0, 0) and nothing is carried.
            commands, groups = self.checkpoint
            self._settle_groups(groups)
            error.checkpoint_commands = self.commands[:commands]
            raise
        self._settle_groups(len(self.groups))
        return self.commands

    def _settle_groups(self, count):
        """Settle `connected` and `skipped` of the first `count` groups, which
        are the groups opened first. A group opens after the group that holds it,
        so one pass settles every group, each one visited once. This is the one
        definition of the rule: a full read settles all its groups with it, and a
        string that stops at `_Undecidable` settles the groups opened before its
        last checkpoint, so the two cannot drift apart."""
        groups = self.groups
        for k in range(count):
            group = groups[k]
            parent = group.parent
            group.connected = (
                group.pipe or group.stdin or group.head_stdin
                or (parent is not None and parent.connected)
            )
            group.skipped = group.skip or (parent is not None and parent.skipped)


class _Reading:
    """The outcome of one reading of a string under one delimiter rule
    (`_read_string`).

    commands  the commands the reading adds: the commands of a string read to its
              end, the commands up to the last checkpoint of a string that
              stopped `_Undecidable`, and none for a reading that raised any
              other exception
    error     None for a string read to its end, otherwise the exception the
              reading ends with: the `_Undecidable` it stopped at (the first
              read's, when a re-read of a string of unknown kind failed), or the
              other exception it raised
    differs   some parser of the reading recorded a delimiter word whose bash
              form and quote-removal form are unequal (`_Parser.differs`)
    failed    some parser of the reading ended in an exception other than
              `_Undecidable`, a re-read that failed included
    """

    __slots__ = ("commands", "error", "differs", "failed")

    def __init__(self, commands, error, differs, failed):
        self.commands = commands
        self.error = error
        self.differs = differs
        self.failed = failed


def _read_string(command, kind, delimiter_rule):
    """Read `command` once under one delimiter rule (DELIMITER_BASH_FORM or
    DELIMITER_QUOTE_REMOVAL) and return a `_Reading`. This is the single-reading
    procedure: the string is read with the switches of its kind and, for the
    unknown kind, that first read has both rules on. A string read to its end
    gives its commands. A string of bash or zsh kind that stops `_Undecidable`
    gives the commands up to its last checkpoint. An exception other than
    `_Undecidable` on the first read of any kind ends the reading as a failure
    that adds no commands (the string is not read again). A string of unknown
    kind that stops `_Undecidable` on the first read is read once more by a new
    parser with both rules off; a re-read that reaches the end gives its
    commands, and a re-read that raises anything is discarded and gives the first
    read's checkpoint commands. The parsers are built through the module's
    `_Parser` name, looked up when this runs. It does not call itself: the
    re-read is a second parser object."""
    coproc_name, zsh_repeat = KIND_SWITCHES[kind]
    parser = None
    try:
        parser = _Parser(command, coproc_name, zsh_repeat, delimiter_rule)
        return _Reading(parser.parse(), None, parser.differs, False)
    except _Undecidable as first:
        differs = parser is not None and parser.differs
        if kind != KIND_UNKNOWN:
            return _Reading(first.checkpoint_commands, first, differs, False)
        retry = None
        try:
            retry = _Parser(command, False, False, delimiter_rule)
            commands = retry.parse()
        except Exception as failure:
            # Whatever the re-read raised is discarded: the first read's
            # `_Undecidable` is the outcome, with its checkpoint commands. The
            # re-read is still a parser that ended in an exception, and its
            # record of a differing delimiter word counts.
            if retry is not None and retry.differs:
                differs = True
            return _Reading(
                first.checkpoint_commands, first, differs, not isinstance(failure, _Undecidable)
            )
        return _Reading(commands, None, differs or retry.differs, False)
    except Exception as failure:
        return _Reading((), failure, parser is not None and parser.differs, True)


def parse(command, kind=KIND_UNKNOWN, delimiter=DELIMITER_QUOTE_REMOVAL):
    """Split `command` into simple commands and return them, or raise
    `_Undecidable` carrying the commands settled up to the last checkpoint of the
    string (`_Parser`).

    `kind` is the kind of the shell that holds the string (KIND_BASH, KIND_ZSH or
    KIND_UNKNOWN, the default: the hook command is of unknown kind). `_scan`
    passes the kind `_judge` hands back with a literal shell `-c` string. The
    kind picks the two rule switches the parser is built with (KIND_SWITCHES): the
    coproc NAME rule and the zsh repeat rule. Both are fixed for the life of that
    parser.

    `delimiter` is the delimiter reading of the string (DELIMITER_BASH_FORM,
    DELIMITER_QUOTE_REMOVAL, the default, or DELIMITER_BOTH): how the `${ ... }`
    ranges of a heredoc delimiter are registered. `_judge` hands it back with the
    kind, decided by the same direct holder (`_delimiter_reading`). The default
    reads as the guard read before the delimiter reading existed, so
    `parse(command)` and `parse(command, kind)` are unchanged.

    One reading. For the bash form and for quote removal the string is read once
    under that delimiter rule by the single-reading procedure (`_read_string`),
    which reads a string of unknown kind a second time:

      1. The string is read with the switches of its kind and, for the unknown
         kind, that first read has both rules on. A string read to its end
         returns its commands.
      2. An exception other than `_Undecidable` on the first read leaves this
         function as it is (no re-read), and so does `_Undecidable` on the first
         read of a string of bash or zsh kind: a string whose kind is known is
         never read twice.
      3. `_Undecidable` on the first read of a string of unknown kind is kept
         with its checkpoint commands, and the string is read once more by a
         new parser with both rules off (`coproc` followed by an ordinary word
         reads that word as the first word of a simple command, and `repeat` is
         an ordinary command name).
      4. A re-read that reads to the end returns its commands. A re-read that
         raises anything, `_Undecidable` or any other exception class, is
         discarded, and the kept first `_Undecidable` is raised with the
         commands the first read settled up to its last checkpoint.

    Two readings. A string held by `sh` or `ksh` (DELIMITER_BOTH) is read
    independently under both rules, because the shell behind the name is not
    known. Reading A is the bash form and reading B is quote removal; each runs
    the procedure above on the whole string, with one rule for all of it (there
    are no per-delimiter combinations).

      1. Reading A runs first. Reading B is skipped only when every parser built
         for reading A ended by returning or by raising `_Undecidable`, and none
         of them recorded a differing delimiter word: then B would read the
         string exactly as A did.
      2. What each reading adds: a reading read to its end adds its commands, a
         reading that stopped `_Undecidable` adds its commands up to its last
         checkpoint, and a reading that raised any other exception adds nothing
         and does not discard what the other reading added. So no outcome of one
         reading suppresses the commands of the other.
      3. The result is the commands of reading A and then those of reading B.
         When either reading stopped `_Undecidable` it is raised as an
         `_Undecidable` that carries these commands; otherwise it is returned.
         When both readings raised another exception, the exception of reading A
         leaves this function, exactly as an unexpected error leaves it today.

    A string is read at most twice by each reading, each read in linear time, and
    this function does not call itself: a re-read and a second reading are other
    parser objects. The characters of a string count toward NESTED_READ_LIMIT in
    `_scan`, before this function runs, so a string that is read more than once
    counts once, at its length."""
    if delimiter != DELIMITER_BOTH:
        reading = _read_string(command, kind, delimiter)
        if reading.error is not None:
            raise reading.error
        return reading.commands
    first = _read_string(command, kind, DELIMITER_BASH_FORM)
    if not first.differs and not first.failed:
        # Reading B would read the string exactly as A did.
        if first.error is not None:
            raise first.error
        return first.commands
    second = _read_string(command, kind, DELIMITER_QUOTE_REMOVAL)
    commands = list(first.commands) + list(second.commands)
    if isinstance(first.error, _Undecidable) or isinstance(second.error, _Undecidable):
        stopped = _Undecidable("delimiter readings")
        stopped.checkpoint_commands = commands
        raise stopped
    if first.error is not None and second.error is not None:
        raise first.error
    return commands


def _basename(text):
    return text.rsplit("/", 1)[-1]


def _is_assignment(word):
    name, eq, _ = word.text.partition("=")
    return bool(eq) and name.isidentifier()


def _has_name(name, known):
    """Whether a command word's basename `name` is the known name `known`: the
    name itself, or the name followed only by digits and dots (FR8). This is the
    one match `_family_of` and `_shell_kind` share."""
    if name == known:
        return True
    if name.startswith(known):
        suffix = name[len(known):]
        return all(ch in DIGITS + "." for ch in suffix)
    return False


def _family_of(name):
    """Return the family whose known name matches a command word's basename
    (FR8: the name itself, or the name plus digits and dots), or None."""
    for family in FAMILIES:
        for known in family.names:
            if _has_name(name, known):
                return family
    return None


def _shell_kind(name):
    """Return the kind of the shell whose command word has the basename `name`:
    KIND_BASH or KIND_ZSH when `name` matches `bash` or `zsh` the way
    `_family_of` matches (the name itself, or the name followed only by digits
    and dots: `bash5.2` is bash), and KIND_UNKNOWN for every other shell (`sh`,
    `dash`, `ksh` and their suffixed forms)."""
    if _has_name(name, "bash"):
        return KIND_BASH
    if _has_name(name, "zsh"):
        return KIND_ZSH
    return KIND_UNKNOWN


def _delimiter_reading(name):
    """Return the delimiter reading of the shell whose command word has the
    basename `name`, matched the way `_shell_kind` matches (the name itself, or
    the name followed only by digits and dots): DELIMITER_BASH_FORM for `bash`,
    DELIMITER_BOTH for `sh` and `ksh`, whose rule is not known, and
    DELIMITER_QUOTE_REMOVAL for `zsh` and `dash`. The delimiter reading is a
    second axis beside the kind: `dash` is of unknown kind and reads quote
    removal only, while `sh` is of unknown kind and reads both. Only the direct
    holder decides; the hook command itself is parsed without a reading and so
    reads quote removal."""
    if _has_name(name, "bash"):
        return DELIMITER_BASH_FORM
    if _has_name(name, "sh") or _has_name(name, "ksh"):
        return DELIMITER_BOTH
    return DELIMITER_QUOTE_REMOVAL


def _command_index(words):
    """Return the index of the command word after assignments and wrappers,
    or None when the command is not judged."""
    i = 0
    n = len(words)
    while True:
        while i < n and _is_assignment(words[i]):
            i += 1
        if i >= n or words[i].dynamic:
            return None
        base = _basename(words[i].text)
        if base in WRAPPERS:
            i += 1
            if i < n and words[i].text.startswith("-"):
                return None
            continue
        if base == "timeout":
            i += 1
            if i < n and words[i].text.startswith("-"):
                return None
            i += 1
            continue
        return i


class _Options:
    """What the options of one launch say."""

    def __init__(self):
        self.interactive = False
        self.operand = False
        self.code = False
        self.informational = False
        # The first operand of a shell started with `-c`, when it is a literal.
        self.code_string = None


def _read_shell_options(family, args):
    """Read the options of a shell launch left to right.

    `-c` is a flag that takes no value: it turns on command-string mode and
    reading goes on through the rest of its bundle and the option words after
    it. A bundle is read one letter at a time: `i` makes the launch
    interactive, and each `o` / `O` takes the next word as its value, as do
    `--rcfile` and `--init-file`. `--` ends the options, and so does a lone
    `-` in command-string mode. Reading stops at the first operand: with `-c`
    it is the command string, and the words after it are positional
    parameters, never options. A dynamic word is an operand whose value is
    unknown. The shells have no informational short options.
    """
    result = _Options()
    command_string = False
    operand = None
    k = 0
    n = len(args)
    while k < n:
        word = args[k]
        text = word.text
        if word.dynamic or not text.startswith("-") or (text == "-" and not command_string):
            operand = k
            break
        if text == "--" or text == "-":
            operand = k + 1 if k + 1 < n else None
            break
        if text.startswith("--"):
            name, eq, _ = text.partition("=")
            if name in INFO_LONG or name in family.info_long:
                result.informational = True
            if name in family.value_long and not eq:
                k += 1
            k += 1
            continue
        values = 0
        for letter in text[1:]:
            if letter in family.code_letters:
                command_string = True
                result.code = True
            elif letter == "i":
                result.interactive = True
            elif letter in family.value_letters:
                values += 1
        k += 1 + values
    if operand is not None:
        result.operand = True
        if command_string and not args[operand].dynamic:
            result.code_string = args[operand].text
    return result


def _read_options(family, args):
    """Read options left to right. Reading stops at the first operand and at
    the value of a code-passing option. The shells have a reader of their own."""
    if family.is_shell:
        return _read_shell_options(family, args)
    result = _Options()
    k = 0
    n = len(args)
    while k < n:
        word = args[k]
        text = word.text
        if word.dynamic or text == "-" or not text.startswith("-"):
            result.operand = True
            return result
        if text == "--":
            result.operand = k + 1 < n
            return result
        if text.startswith("--"):
            name, eq, _ = text.partition("=")
            if name in family.interactive_long:
                result.interactive = True
            if name in INFO_LONG or name in family.info_long:
                result.informational = True
            if name in family.code_long:
                result.code = True
                return result
            if name in family.value_long and not eq:
                k += 1
            k += 1
            continue
        letters = text[1:]
        for j, letter in enumerate(letters):
            rest = letters[j + 1:]
            if letter in family.code_letters:
                result.code = True
                return result
            if letter == "i" and family.deny_i:
                result.interactive = True
            elif letter in family.value_letters:
                if not rest:
                    k += 1
                break
            elif letter in family.attached_letters:
                break
            elif letter in family.info_letters:
                result.informational = True
        k += 1
    return result


def _judge(words, connected):
    """Judge one simple command. Return (verdict, inner, inner_kind,
    inner_delimiter): verdict is ("interactive", name), ("noprogram", name) or
    None; inner is a shell `-c` literal to judge, or None; inner_kind is the kind
    of the shell that holds `inner` (KIND_BASH, KIND_ZSH or KIND_UNKNOWN), and
    inner_delimiter is its delimiter reading (DELIMITER_BASH_FORM,
    DELIMITER_QUOTE_REMOVAL or DELIMITER_BOTH); both are None exactly when there
    is no `inner`.

    The kind and the delimiter reading come from the basename of the shell
    command word that directly holds the string: the word left after
    assignments, the option-less wrappers (`env` and the others) and a path,
    matched the way `_family_of` matches (`_shell_kind`, `_delimiter_reading`).
    Only the direct holder decides, so a `zsh -c` string inside a `bash -c`
    string is zsh. The caller is `_scan`, which hands both to `parse`."""
    index = _command_index(words)
    if index is None:
        return None, None, None, None
    name = _basename(words[index].text)
    family = _family_of(name)
    if family is None:
        return None, None, None, None
    options = _read_options(family, words[index + 1:])
    if options.interactive:
        return ("interactive", name), None, None, None
    if options.code or options.operand or options.informational or connected:
        inner = options.code_string
        if inner is None:
            return None, None, None, None
        return None, inner, _shell_kind(name), _delimiter_reading(name)
    return ("noprogram", name), None, None, None


def _scan(commands):
    """Walk the commands of the hook command and of every literal shell `-c`
    string nested in them, and return (kind, name) for the first launch to
    deny, or None.

    Nesting is followed with an explicit work list, never by a call to this
    function or to another that leads back here, so the depth of nested strings
    costs no call stack. Each work-list entry is [commands, position,
    inherited, level]: the simple commands of one string, the index of the
    next command to judge, whether the string inherits a stdin connection from
    its holder, and the nesting level (0 for the hook command, 1 for a
    first-level string, and so on). The entry on top is read first, so the
    commands of a nested string, and of the strings nested in it, are judged
    before the command that follows their holder.

    The strings of the second level and deeper share one running total of
    characters. A string that would carry the total past NESTED_READ_LIMIT is
    not read, and neither is any later one of those levels. First-level strings
    are always read. Reaching the limit is no verdict: the commands still to be
    judged at level 0 and in first-level strings are judged as before.

    Each string is read by its kind and its delimiter reading, those of the shell
    that directly holds it: `_judge` hands both back with the literal `-c`
    string, and this function passes them to `parse` with the string (the hook
    command itself is parsed without either, so it is of unknown kind and reads
    the quote-removal form). A string of unknown kind that stops undecidable is
    read once more inside `parse`, with neither the coproc NAME rule nor the zsh
    repeat rule, and falls back to the first read's checkpoint commands when that
    re-read fails. A string held by `sh` or `ksh` is read under both delimiter
    readings inside `parse`, the bash form first; the dual reading denies when
    either reading denies, because `parse` hands back the commands of both
    readings. This function sees one result either way, and calls `parse` once
    for each string. The characters of a string count toward the limit here,
    before `parse` runs, once at the string's length, so a string that is read
    more than once counts once. A nested string found in the commands of both
    readings is reached, and counted, once for each reading.

    A nested string that cannot be read to its end raises _Undecidable. The
    commands that exception carries (`checkpoint_commands`: the commands up to
    the last checkpoint of that string, none when it has no checkpoint) are the
    commands of that string. They are added to the work list exactly as the
    commands of a string read in full are: with the connection the holder passes
    down, at the level one higher. An empty tuple leaves nothing to judge. A
    checkpoint is a newline that the reader itself reads at the top level, at
    which all of these hold: no group is open, no pipe is pending, no list
    continuation is pending (a trailing `&&` or `||` has not left the list
    open), and the heredoc bodies registered on that line have been read
    through their terminators. When a string is undecidable, the commands up to
    the last checkpoint are judged, with connection and skip taken from the
    groups opened before it exactly as a full read sets them; a string with no
    checkpoint gives no output. The rule applies to the hook command and to
    every nested literal shell `-c` string (`find_deny` takes the commands of
    the hook command the same way), and an undecidable string counts at its full
    length toward NESTED_READ_LIMIT, as its length is counted before it is
    parsed. An error other than _Undecidable is handled as before: that string
    is skipped, and the walk neither returns nor raises.
    """
    pending = [[commands, 0, False, 0]]
    total = 0
    limit_reached = False
    while pending:
        entry = pending[-1]
        entry_commands, position, inherited, level = entry
        if position >= len(entry_commands):
            pending.pop()
            continue
        entry[1] = position + 1
        command = entry_commands[position]
        group = command.group
        if group is not None and group.skipped:
            continue
        connected = inherited or command.stdin or command.after_pipe
        if group is not None and group.connected:
            connected = True
        verdict, inner, inner_kind, inner_delimiter = _judge(command.words, connected)
        if verdict:
            return verdict
        if inner is None:
            continue
        if level >= 1:
            if limit_reached or total + len(inner) > NESTED_READ_LIMIT:
                limit_reached = True
                continue
            total += len(inner)
        try:
            inner_commands = parse(inner, inner_kind, inner_delimiter)
        except _Undecidable as error:
            # The string cannot be read to its end: the commands settled up to
            # its last checkpoint are the commands of this string, judged like
            # those of a string read in full. None are left when it has no
            # checkpoint, and the walk goes on with the command after the holder.
            inner_commands = error.checkpoint_commands
        except Exception:
            # An unexpected error is handled like an unreadable string: this
            # one is skipped and the walk goes on. Never a reason to deny.
            continue
        pending.append([inner_commands, 0, connected, level + 1])
    return None


def find_deny(command):
    """Return (kind, name) for the first launch to deny, or None.

    When the hook command cannot be read to its end (`_Undecidable`), the walk
    runs over the commands settled up to its last checkpoint, and over none when
    it has no checkpoint. Any other exception is not handled here: it reaches
    `main`, which gives no output."""
    try:
        commands = parse(command)
    except _Undecidable as error:
        commands = error.checkpoint_commands
    return _scan(commands)


def deny_reason(kind, name):
    if kind == "interactive":
        lead = f"`{name}` を対話モード（-i）で起動する操作は、ここでは使えない。"
    else:
        lead = f"`{name}` をプログラムを渡さずに起動する操作は、対話モードになるため、ここでは使えない。"
    return (
        "[codex-hook-interactive-guard] "
        + lead
        + "端末が閉じても入力待ちのまま残り続ける孤児プロセスになる。"
        "非対話の実行に切り替えること: `python3 -c '...'` で式を渡す、"
        "スクリプトファイルを作って実行する、"
        "または `python3 - <<EOF` でヒアドキュメントから渡す。"
    )


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read())
        if not isinstance(payload, dict):
            return
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            return
        command = tool_input.get("command")
        if not isinstance(command, str):
            return
        hit = find_deny(command)
        if hit is None:
            return
        text = json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": HOOK_EVENT_NAME,
                    "permissionDecision": "deny",
                    "permissionDecisionReason": deny_reason(*hit),
                }
            },
            ensure_ascii=False,
        )
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except Exception:
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
