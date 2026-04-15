# DOS Command Compatibility

This document details the DOS command compatibility status for the SSH DOS Environment.

## Command Implementation Status

### File and Directory Commands

| Command | Status | Description | Notes |
|---------|--------|-------------|-------|
| `DIR` | ✅ Fully Implemented | List directory contents | Supports `/W` (wide format) and `/A` (show all) switches |
| `CD` / `CHDIR` | ✅ Fully Implemented | Change directory | Shows current directory when called without arguments |
| `MD` / `MKDIR` | ✅ Fully Implemented | Create directory | Creates directories recursively |
| `RD` / `RMDIR` | ✅ Fully Implemented | Remove directory | Supports `/S` (recursive) and `/Q` (quiet) switches |
| `COPY` | ✅ Fully Implemented | Copy files | Single file copy supported |
| `DEL` / `ERASE` | ✅ Fully Implemented | Delete files | Supports wildcards (`*`, `?`) and `/Q` switch |
| `REN` / `RENAME` | ✅ Fully Implemented | Rename files | Single file/directory rename |
| `MOVE` | ✅ Fully Implemented | Move files | Moves files between directories |
| `TYPE` | ✅ Fully Implemented | Display file contents | Text file display with UTF-8 support |
| `TREE` | ✅ Fully Implemented | Display directory structure | Supports `/F` (show files) switch |
| `FIND` | ✅ Fully Implemented | Search for text in a file | Supports `/V` (invert), `/C` (count), `/I` (case-insensitive), `/N` (line numbers), and piped input |
| `MORE` | ✅ Fully Implemented | Display output one page at a time | Paginated file display; supports piped input |
| `SORT` | ✅ Fully Implemented | Sort lines alphabetically | Supports `/R` (reverse), `/O file` (output to file), and piped input |
| `FC` | ✅ Fully Implemented | Compare two files | Supports `/N` (line numbers) switch |
| `EDIT` | ✅ Fully Implemented | Full-screen text editor | Supports cursor navigation, file open/save, Ctrl key shortcuts |

### System and Environment Commands

| Command | Status | Description | Notes |
|---------|--------|-------------|-------|
| `CLS` | ✅ Fully Implemented | Clear screen | Uses ANSI escape sequences |
| `ECHO` | ✅ Fully Implemented | Display messages | Supports `ECHO ON/OFF` and text output |
| `HELP` | ✅ Fully Implemented | Display help | Lists all commands or specific command help |
| `EXIT` | ✅ Fully Implemented | Exit shell | Closes SSH session |
| `VER` | ✅ Fully Implemented | Display version | Shows "DosPC Sim DOS [Version 1.0]" |
| `SET` | ✅ Fully Implemented | Environment variables | Display/set environment variables |
| `PROMPT` | ✅ Fully Implemented | Change prompt | Supports `$P`, `$G`, `$L`, `$D`, `$T`, `$N`, `$$` meta-characters |
| `PATH` | ✅ Fully Implemented | Display/set path | View or modify search path |
| `DATE` | ⚠️ Partially Implemented | Display date | Shows current date (setting not implemented) |
| `TIME` | ⚠️ Partially Implemented | Display time | Shows current time (setting not implemented) |

### I/O Redirection and Pipes

| Feature | Status | Description | Notes |
|---------|--------|-------------|-------|
| Pipes (`\|`) | ✅ Fully Implemented | Pipe output between commands | Multi-stage pipes supported |
| Output Redirect (`>`) | ✅ Fully Implemented | Redirect output to file | Overwrites target file |
| Append Redirect (`>>`) | ✅ Fully Implemented | Append output to file | Appends to existing content |
| Input Redirect (`<`) | ✅ Fully Implemented | Redirect input from file | Reads file as stdin |

### Batch File Support

| Feature | Status | Description | Notes |
|---------|--------|-------------|-------|
| `.BAT` Execution | ✅ Fully Implemented | Execute batch files | |
| `.CMD` Execution | ✅ Fully Implemented | Execute command scripts | |
| `%0-%9` Parameters | ✅ Fully Implemented | Command line parameter substitution | |
| `%VAR%` Expansion | ✅ Fully Implemented | Environment variable expansion | Expanded at execution time |
| `REM` Comments | ✅ Fully Implemented | Remark/comment lines | |
| `::` Comments | ✅ Fully Implemented | Alternative comment style | |
| Labels (`:LABEL`) | ✅ Fully Implemented | Label lines for GOTO targets | |
| `GOTO` | ✅ Fully Implemented | Jump to label | Supports forward and backward jumps |
| `CALL` | ✅ Fully Implemented | Call another batch file | Supports passing arguments |
| `IF` | ✅ Fully Implemented | Conditional execution | Supports `EXIST`, `ERRORLEVEL`, string comparison (`==`), and `NOT` |
| `FOR` | ✅ Fully Implemented | Loop construct | Supports `%%var IN (set) DO command` |
| `PAUSE` | ✅ Fully Implemented | Pause execution | Displays "Press any key to continue . . . " |
| `ECHO OFF` | ⚠️ Partially Implemented | Command echo suppression | Toggle works; batch commands are not echoed regardless of state |
| `@` Prefix | ❌ Not Implemented | Suppress echo for single line | |
| `IF DEFINED` | ❌ Not Implemented | Check if variable is defined | |
| `IF` / `ELSE` | ❌ Not Implemented | Else clause for conditionals | |

## Command Details

### DIR Command

**Syntax:** `DIR [path] [/W] [/A]`

**Switches:**
- `/W` - Wide format (5 columns)
- `/A` - Show all files including hidden

**Output Format:**
```
 Volume in drive C is DOSPC-SIM
 Directory of C:\

01/15/2026  10:30 AM    <DIR>          DOCS
01/15/2026  10:30 AM    <DIR>          GAMES
01/15/2026  10:30 AM               256 README.TXT
               1 File(s)            256 bytes
               2 Dir(s)    52,428,800 bytes free
```

### COPY Command

**Syntax:** `COPY source destination`

**Notes:**
- Single file copy only
- Supports relative and absolute paths
- Automatically handles directory destinations

### DEL/ERASE Command

**Syntax:** `DEL filespec [/Q]`

**Features:**
- Wildcard support: `*` (any chars) and `?` (single char)
- `/Q` - Quiet mode (no confirmation)

**Examples:**
- `DEL *.TXT` - Delete all .txt files
- `DEL FILE?.DAT` - Delete FILE1.DAT, FILE2.DAT, etc.

### CD/CHDIR Command

**Syntax:** `CD [path]`

**Features:**
- `CD` alone shows current directory
- Supports `..` (parent directory)
- Supports absolute paths from C:\

### EDIT Command

**Syntax:** `EDIT [filename]`

**Features:**
- Full-screen text editor using alternate screen buffer
- Arrow keys, Home/End, PgUp/PgDn navigation
- Ctrl+S to save, Ctrl+Q to quit, Ctrl+O to open, Ctrl+A to save as
- Line numbers displayed in editor
- Unsaved changes warning on quit

### PROMPT Command

**Syntax:** `PROMPT [string]`

**Meta-characters:**
- `$P` - Current path
- `$G` - `>` character
- `$L` - `<` character
- `$D` - Current date
- `$T` - Current time
- `$N` - Drive letter
- `$$` - Literal `$`

### IF Command (Batch)

**Syntax:**
- `IF [NOT] EXIST filename command`
- `IF [NOT] ERRORLEVEL number command`
- `IF [NOT] string1==string2 command`

### FOR Command (Batch)

**Syntax:** `FOR %%var IN (set) DO command`

**Example:**
```
FOR %%F IN (file1.txt file2.txt file3.txt) DO TYPE %%F
```

## Security Features

### User Isolation

1. **Home Directory Restriction**: Users cannot access files outside their home directory
2. **Path Validation**: All paths are resolved and validated against home directory
3. **Permission Errors**: Attempts to escape home directory result in "Access denied" errors
4. **Case-Insensitive File Access**: File lookups use case-insensitive matching for DOS compatibility

### C: Drive Mapping

Each user's home directory is mapped to C:\
- `C:\` = User's home directory
- Relative paths are relative to current directory
- `..` moves up within home directory only

## Environment Variables

The following environment variables are available:

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `PROMPT` | `$P$G` | Command prompt string (evaluates to `C:\>` at root) |
| `PATH` | `C:\;C:\DOS;C:\WINDOWS` | Search path for executables |
| `COMSPEC` | `C:\COMMAND.COM` | Command interpreter path |
| `TEMP` | `C:\TEMP` | Temporary directory |
| `TMP` | `C:\TEMP` | Temporary directory |

## Limitations and Known Issues

### Not Implemented

1. **Command chaining (`&&`, `||`)**: Multiple command execution is not supported
2. **Background execution (`&`)**: Not applicable in this environment
3. **`@` prefix**: Suppressing echo for a single batch line is not supported
4. **`IF DEFINED`**: Checking if a variable is defined is not supported
5. **`IF` / `ELSE`**: Else clause for conditionals is not supported

### Partial Implementations

1. **Batch ECHO**: `ECHO ON/OFF` toggle works, but batch commands are never echoed during execution regardless of ECHO state
2. **Wildcards**: Only DEL supports wildcards; COPY and DIR have limited support

## Future Enhancements

Planned features for future releases:

- [ ] Batch `@` prefix for single-line echo suppression
- [ ] `IF DEFINED` and `IF` / `ELSE` support
- [ ] Command history and line editing
- [ ] Tab completion for filenames
- [ ] Additional commands: ATTRIB, XCOPY, DOSKEY
- [ ] Network drive simulation (NET USE)
