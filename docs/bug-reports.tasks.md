# Bug Reports

Tasks sorted by descending priority.

---

## 1. `RD /S` without `/Q` deletes without waiting for user confirmation

`cmd_rd` in `shell_commands.py` prints the "Are you sure (Y/N)?" prompt when `/S` is used without `/Q`, but it never reads the user's response — it immediately proceeds to call `remove_directory_recursive`. The `_input_callback` (used by PAUSE) is never consulted, and there is no mechanism to read a Y/N answer. This means `RD /S dirname` always deletes recursively without actual confirmation.

**Files:** `src/dospc_sim/shell_commands.py`
**Impact:** Data loss — recursive directory deletion happens unconditionally despite a confirmation prompt.

Benchmark data: Pre: RD 3576 ops/s | Post: RD 3484 ops/s | Delta: noise

Status: Done

---

## 2. Editor quit warning is misleading; unsaved changes exit immediately

`TextEditor._quit` in `editor.py` sets `self.running = False` on the first quit attempt even when there are unsaved changes. The status message warns about unsaved changes and says "Press Ctrl+Q again to quit without saving", but since `running` is already `False`, the editor exits immediately without giving the user a chance to see the warning or press Ctrl+Q again.

**Files:** `src/dospc_sim/editor.py`
**Impact:** UX/Data loss — users don't get a chance to cancel after the warning.

Benchmark data: Pre: N/A (editor not benchmarked) | Post: N/A | Delta: noise

Status: Done

---

## 3. FOR loop bodies with pipes or nested FOR commands execute as empty strings

`_ast_to_raw` in `dos_shell.py` returns an empty string for `PipeCommand` and `ForCommand` nodes. When a `FOR` loop body contains a pipe or another `FOR` command, the reconstructed command string is blank and nothing is executed.

**Files:** `src/dospc_sim/dos_shell.py`
**Impact:** Functional — FOR loops with piped or nested commands do nothing.

Benchmark data: Pre: Batch 2489 ops/s, Pipes 10140 ops/s | Post: Batch 2409 ops/s, Pipes 9905 ops/s | Delta: noise

Status: Done

---

## 4. Pipes cannot include built-in commands like `ECHO`

The grammar limits `command_chain` to `simple_command`, while `ECHO` is parsed as `EchoCommand`. As a result, `ECHO hello | FIND hello` cannot be parsed as a pipe chain and does not behave like DOS/CMD.

**Files:** `src/dospc_sim/parser.py`, `src/dospc_sim/dos_shell.py`
**Impact:** Compatibility — common pipe usage with `ECHO` and other built-ins fails.

Benchmark data: Pre: Pipes 10140 ops/s | Post: Pipes 9905 ops/s, Echo pipe 44097 ops/s | Delta: noise

Status: Done

---

## 5. `DEL` wildcard ignores directory components

`cmd_del` always calls `self.fs.list_directory()` without honoring path components in wildcard patterns. `DEL subdir\*.txt` matches against the current directory rather than `subdir`.

**Files:** `src/dospc_sim/shell_commands.py`
**Impact:** Functional — wildcard deletes with a directory prefix silently fail or target the wrong directory.

Status: Todo

---

## 6. Escape sequence parsing can drop bytes read mid-sequence

`_parse_escape_sequence` reads additional bytes from the channel and appends them to a local `raw` buffer, but the caller in `run()` continues iterating over the original `data` buffer. Any extra bytes read are lost, which can corrupt input for multi-byte escape sequences.

**Files:** `src/dospc_sim/ssh_server.py`
**Impact:** Input handling — some escape sequences or rapid keypresses can be dropped or misparsed.

Status: Todo

---

## 7. SSH session always sends "Goodbye" even after client disconnect

After `session.run()` ends, `_setup_shell` unconditionally calls `channel.send(...)`. If the client already disconnected, this raises and is logged as an error despite being a normal disconnect.

**Files:** `src/dospc_sim/ssh_server.py`
**Impact:** Noise — spurious error logs on normal disconnects.

Status: Todo

---

## 8. `DIR` header always shows the current directory, not the listed directory

`cmd_dir` prints `Directory of {self.fs.get_current_path()}` even when a different path argument is provided. `DIR subdir` still shows the current directory in the header.

**Files:** `src/dospc_sim/shell_commands.py`
**Impact:** Cosmetic/Functional — misleading output for non-current directory listings.

Status: Todo

---

## 9. `SET VARNAME` with no `=` prints nothing for undefined variables

When a variable doesn't exist, `cmd_set` returns with no output. In Windows CMD, the command prints `Environment variable VARNAME not defined`.

**Files:** `src/dospc_sim/shell_commands.py`
**Impact:** Compatibility — missing feedback for undefined variables.

Status: Todo

---

## 10. `get_free_space` uses `os.statvfs`, which is unavailable on Windows hosts

`get_free_space` calls `os.statvfs`, which raises `AttributeError` on Windows. If the server runs on Windows, `DIR` will crash when it tries to display free space.

**Files:** `src/dospc_sim/filesystem.py`
**Impact:** Portability — `DIR` fails on Windows hosts.

Status: Todo

---

## 11. `_parse_escape_sequence` can lose bytes read mid-sequence

`_parse_escape_sequence` mutates a local copy of the raw input when it reads extra bytes from the channel, but the caller keeps iterating the original buffer. Any extra bytes read mid-sequence are discarded before the main loop sees them.

**Files:** `src/dospc_sim/ssh_server.py`
**Impact:** Input handling — escape sequences that require extra reads may be partially consumed, causing garbled input or missed keystrokes.

Status: Todo

---

## 12. `channel.send` after session end can raise on closed channels

After `session.run()` returns, `_setup_shell` calls `channel.send("\r\nGoodbye!\r\n")` without checking channel state. If the client already closed the channel, this raises and is logged as an error.

**Files:** `src/dospc_sim/ssh_server.py`
**Impact:** Noise — spurious error logs on normal disconnects.

Status: Todo

---

## 13. `DIR` output path header does not reflect the argument path

The `DIR` header always uses `self.fs.get_current_path()`, so the header is wrong when listing a path other than the current directory.

**Files:** `src/dospc_sim/shell_commands.py`
**Impact:** Cosmetic — confusing output for `DIR` on other directories.

Status: Todo

---

## 14. `SET` with no `=` omits an error for undefined variables

When a variable doesn't exist, `cmd_set` returns without output. Windows CMD prints `Environment variable VARNAME not defined` in this case.

**Files:** `src/dospc_sim/shell_commands.py`
**Impact:** Compatibility — undefined variables fail silently.

Status: Todo

---

## 15. `get_free_space` crashes on Windows hosts

`os.statvfs` is unavailable on Windows. If the server runs there, `DIR` will crash when it tries to display free space.

**Files:** `src/dospc_sim/filesystem.py`
**Impact:** Portability — Windows hosts will error in `DIR`.

Status: Todo

---

## 16. Pipes cannot include built-in commands parsed as `EchoCommand`

`command_chain` only accepts `simple_command`, so `ECHO hello | FIND hello` is not parsed as a pipe chain. This diverges from DOS/CMD behavior.

**Files:** `src/dospc_sim/parser.py`, `src/dospc_sim/dos_shell.py`
**Impact:** Compatibility — built-in commands cannot participate in pipes.

Duplicate of bug 4, fixed there.

Status: Done

---

## 17. `DEL` wildcard with directory prefix ignores the directory component

`cmd_del` lists the current directory even when the wildcard pattern includes a path component. `DEL subdir\*.txt` fails to delete files in `subdir`.

**Files:** `src/dospc_sim/shell_commands.py`
**Impact:** Functional — wildcard deletes with path prefixes fail.

Status: Todo