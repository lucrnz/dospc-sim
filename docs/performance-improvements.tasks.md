# Performance Improvements

Tasks sorted by descending complexity.

---

## 1. Switch Lark parser from Earley to LALR and cache the parser instance

The Lark parser is instantiated with `parser='earley'` (O(n³) worst-case). LALR is O(n) and Lark supports it natively. The grammar is already LR-compatible (no ambiguous rules). Switching to `parser='lalr'` and keeping the single module-level `_parser` instance will speed up every `parse_command` call, which sits on the critical path of every command and every line of batch execution. Additionally, the transformer can be baked into the LALR parser via `transformer=` kwarg so Lark skips the separate tree-walk pass.

**Files:** `src/dospc_sim/parser.py`
**Estimated impact:** All benchmarks (especially Batch at 163 ops/s), since every operation calls `parse_command`.

Benchmark data: Pre: Batch 165 ops/s, ECHO 2943 ops/s, DIR 2481 ops/s, CALL 1119 ops/s → Post: Batch 1966 ops/s, ECHO 89006 ops/s, DIR 5189 ops/s, CALL 4509 ops/s. Improvement across all benchmarks (Batch +1089%, ECHO +2924%, CALL +303%).

Status: Done

---

## 2. Avoid re-parsing the batch body on every FOR loop iteration

`_execute_for` in `dos_shell.py` calls `self.execute_command(expanded)` for each item in the FOR set, which re-expands variables and re-parses the command string from scratch every iteration. Instead, the raw command template should be reconstructed once via `_ast_to_raw`, and only the variable substitution + parse should happen per iteration — or better, the AST should be cloned with the variable replaced directly, avoiding re-parsing entirely.

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** FOR-heavy batch scripts; reduces per-iteration overhead from full parse to string substitution.

Benchmark data: Pre: Batch 1956 ops/s, CALL 4396 ops/s → Post: Batch 1943 ops/s, CALL 4418 ops/s. Noise (no dedicated FOR benchmark; the optimization reduces per-iteration overhead in FOR loops specifically).

Status: Done

---

## 3. Cache `_find_batch_file` lookups

`_find_batch_file` performs multiple filesystem existence checks (up to 2 extensions × N PATH directories) on every command dispatch when the command is not a built-in. The PATH environment variable rarely changes, so results can be cached in a dict keyed on `(command_name, current_dir, PATH)` and invalidated when `SET PATH=...` or `CD` changes state.

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** CALL benchmark (1094 ops/s), any unknown-command path, batch execution.

Benchmark data: Pre: CALL 4380 ops/s, Batch 1959 ops/s → Post: CALL 5863 ops/s, Batch 1969 ops/s. Improvement (CALL +34%).

Status: Done

---

## 4. Build a command dispatch table instead of `getattr` lookup per call

`_execute_simple` uses `getattr(self, f'cmd_{command.lower()}', None)` on every command invocation. Building a `dict[str, Callable]` once in `__init__` (or as a class-level mapping) eliminates the repeated string formatting and attribute lookup. This also removes the need for the `f'cmd_{...}'` string allocation on every call.

**Files:** `src/dospc_sim/dos_shell.py`, `src/dospc_sim/shell_commands.py`
**Estimated impact:** Every command dispatch; small per-call saving but multiplied across all benchmarks.

Benchmark data: Pre: ECHO 95468 ops/s, CALL 5863 ops/s, Batch 1969 ops/s → Post: ECHO 99819 ops/s, CALL 5957 ops/s, Batch 1999 ops/s. Noise (small constant-factor improvement absorbed by other bottlenecks).

Status: Done

---

## 5. Pre-compile the `_ENV_VAR_RE` replacer and short-circuit when no `%` present

`expand_variables` runs `_ENV_VAR_RE.sub(...)` on every command line and every batch line, even when the text contains no `%` characters. Adding a fast `if '%' not in text: return text` guard skips the regex engine entirely for the common case. The regex is already module-level compiled, but the inner `_replace` closure is recreated on every call — it could be a bound method instead.

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** All benchmarks; largest impact on Batch (many lines expanded).

Benchmark data: Pre: Batch 1998 ops/s, ECHO 94560 ops/s → Post: Batch 1987 ops/s, ECHO 94533 ops/s. Noise (the short-circuit avoids regex overhead on lines without %, which is the common case but not heavily exercised in the benchmark).

Status: Done

---

## 6. Avoid repeated `self.environment['PATH'].split(';')` in `_find_batch_file`

`_find_batch_file` calls `self.environment['PATH'].split(';')` up to twice (once per extension) every time it runs. The split result should be computed once per call (or cached until PATH changes).

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** CALL, batch file lookups, unknown-command fallback.

Benchmark data: Already addressed in Task 3 — _find_batch_file_uncached splits PATH once at the top and reuses the list. No separate benchmark needed.

Status: Done

---

## 7. Reduce `_resolve_path` overhead in `UserFilesystem` — skip double resolve and redundant security checks

`_resolve_path` calls `target.resolve()`, then `_find_case_insensitive`, then `target.resolve(strict=False)` again, and performs the `relative_to` security check twice. When the path already exists (the common case), the case-insensitive walk is a no-op and the second resolve is redundant. Guard the second resolve + security check behind a flag indicating the path was actually modified by `_find_case_insensitive`.

**Files:** `src/dospc_sim/filesystem.py`
**Estimated impact:** Every filesystem operation (DIR, TYPE, COPY, FIND, etc.).

Status: Todo

---

## 8. Use `os.scandir` instead of `Path.iterdir` in `list_directory`

`list_directory` calls `item.stat()`, `item.is_dir()`, and `item.is_file()` separately for each entry, resulting in multiple syscalls per file. `os.scandir` returns `DirEntry` objects that cache `is_dir`/`is_file` results from the initial `readdir` call (on most platforms), cutting syscalls roughly in half.

**Files:** `src/dospc_sim/filesystem.py`
**Estimated impact:** DIR benchmarks (2000-2500 ops/s), TREE, tab completion, wildcard COPY/DEL.

Status: Todo

---

## 9. Avoid full-screen redraw on every keystroke in the editor

`TextEditor._draw_screen` redraws the entire 21-line visible area plus title bar and status bar on every single keypress (character insert, cursor move, backspace). For simple cursor movements, only the cursor position ANSI escape needs to be sent. For single-character inserts, only the current line needs updating. This would reduce SSH traffic and improve editor responsiveness over high-latency connections.

**Files:** `src/dospc_sim/editor.py`
**Estimated impact:** Editor responsiveness (not benchmarked but affects user experience over SSH).

Status: Todo

---

## 10. Pre-split and pre-filter batch lines in `_BatchExecutor.execute` instead of per-line `parse_command`

`_BatchExecutor.execute` already builds a `line_index` list, but it still calls `parse_command` (which includes `line.strip()`, emptiness check, and Lark parse) on every line during execution. Labels and blank lines are already filtered into `None` entries, but comment lines (`::`/`REM`) still go through the full parser. Pre-parsing all non-None lines into AST nodes before the execution loop would allow the PC loop to skip the parse step entirely, at the cost of slightly more memory.

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** Batch benchmark (163 ops/s) — eliminates per-line parse overhead during execution.

Status: Todo

---

## 11. Compile `get_prompt` replacements into a single pass

`get_prompt` performs 14 separate `str.replace` calls in sequence, each scanning the full string. A single `re.sub` with a replacement dict, or a `str.translate`-based approach for the single-character meta-chars, would reduce this to one or two passes.

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** Every prompt display; small per-call saving but called on every command.

Status: Todo

---

## 12. Replace `datetime.now()` calls in `get_prompt` with lazy evaluation

`get_prompt` calls `datetime.now()` and formats it with `strftime` on every invocation, even when the prompt string doesn't contain `$D` or `$T`. Check for the presence of date/time meta-characters first and only call `datetime.now()` when needed.

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** Prompt generation; minor but avoids unnecessary syscall.

Status: Todo

---

## 13. Use `__slots__` on hot-path AST dataclasses

The AST node classes (`CommandLine`, `SimpleCommand`, `Argument`, `Switch`, `CommandName`, etc.) are allocated on every parse. Adding `__slots__=True` to their `@dataclass` decorators reduces per-instance memory and speeds up attribute access.

**Files:** `src/dospc_sim/parser_ast.py`
**Estimated impact:** All benchmarks; reduces allocation overhead on every parse.

Status: Todo

---

## 14. Avoid re-creating the `_replace` closure on every `expand_variables` call

The inner function `_replace` inside `expand_variables` captures `self.environment` but is re-created as a new closure object on every call. Making it a bound method or a cached callable eliminates the closure allocation.

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** Minor; reduces allocation on every command/batch line.

Status: Todo

---

## 15. Short-circuit `_execute_ast` isinstance chain with a dispatch dict

`_execute_ast` uses a chain of 8 `isinstance` checks to dispatch by AST node type. A `dict[type, method]` lookup replaces O(n) isinstance checks with O(1) dict lookup.

**Files:** `src/dospc_sim/dos_shell.py`
**Estimated impact:** Every command execution; small constant-factor improvement.

Status: Todo

---

## 16. Avoid string concatenation in `_output_line` / SSH `output_callback`

The SSH `output_callback` lambda does `text + '\r\n'` on every output line, creating a new string. For commands that produce many lines (DIR, TREE, FIND), buffering output and sending in a single `channel.send` call would reduce the number of SSH sends and string allocations.

**Files:** `src/dospc_sim/ssh_server.py`
**Estimated impact:** DIR, TREE, TYPE, FIND, batch ECHO — reduces SSH round-trips and allocations.

Status: Todo

---

## 17. Cache `SimpleCommand.arguments`, `.switches`, and `.positional_args` properties

These properties on `SimpleCommand` rebuild new lists via list comprehensions on every access. Since AST nodes are not mutated after construction, the results can be cached (e.g., via `functools.cached_property` or computed once in `__post_init__`).

**Files:** `src/dospc_sim/parser_ast.py`
**Estimated impact:** Every command that reads args/switches; small per-call saving.

Status: Todo
