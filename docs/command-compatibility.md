# DosPC Sim DOS Command Compatibility

This document details the DOS command compatibility status for the DosPC Sim SSH DOS Environment.

## Overview

DosPC Sim provides a simulated DOS environment accessible via SSH. Each user has an isolated home directory mounted as the C: drive. All commands are restricted to the user's own home directory, preventing cross-user file access.

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

### System and Environment Commands

| Command | Status | Description | Notes |
|---------|--------|-------------|-------|
| `CLS` | ✅ Fully Implemented | Clear screen | Uses ANSI escape sequences |
| `ECHO` | ✅ Fully Implemented | Display messages | Supports `ECHO ON/OFF` and text output |
| `HELP` | ✅ Fully Implemented | Display help | Lists all commands or specific command help |
| `EXIT` | ✅ Fully Implemented | Exit shell | Closes SSH session |
| `VER` | ✅ Fully Implemented | Display version | Shows "DosPC Sim DOS [Version 1.0]" |
| `SET` | ✅ Fully Implemented | Environment variables | Display/set environment variables |
| `PROMPT` | ✅ Fully Implemented | Change prompt | Modify command prompt string |
| `PATH` | ✅ Fully Implemented | Display/set path | View or modify search path |
| `DATE` | ✅ Partially Implemented | Display date | Shows current date (setting not implemented) |
| `TIME` | ✅ Partially Implemented | Display time | Shows current time (setting not implemented) |

### Batch File Support

| Feature | Status | Description |
|---------|--------|-------------|
| `.BAT` Execution | ✅ Fully Implemented | Execute batch files |
| `.CMD` Execution | ✅ Fully Implemented | Execute command scripts |
| `%0-%9` Parameters | ✅ Fully Implemented | Command line parameter substitution |
| `REM` Comments | ✅ Fully Implemented | Remark/comment lines |
| `::` Comments | ✅ Fully Implemented | Alternative comment style |
| `ECHO OFF` | ⚠️ Stub | Command echo suppression (stub) |
| `PAUSE` | ❌ Not Implemented | Pause execution |
| `IF` | ❌ Not Implemented | Conditional execution |
| `FOR` | ❌ Not Implemented | Loop construct |
| `GOTO` | ❌ Not Implemented | Jump to label |
| `CALL` | ❌ Not Implemented | Call another batch file |

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

01/15/2024  10:30 AM    <DIR>          DOCS
01/15/2024  10:30 AM    <DIR>          GAMES
01/15/2024  10:30 AM               256 README.TXT
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

## Security Features

### User Isolation

1. **Home Directory Restriction**: Users cannot access files outside their home directory
2. **Path Validation**: All paths are resolved and validated against home directory
3. **Permission Errors**: Attempts to escape home directory result in "Access denied" errors

### C: Drive Mapping

Each user's home directory is mapped to C:\
- `C:\` = User's home directory
- Relative paths are relative to current directory
- `..` moves up within home directory only

## Environment Variables

The following environment variables are available:

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `PROMPT` | `C:\>` | Command prompt string |
| `PATH` | `C:\;C:\DOS;C:\WINDOWS` | Search path for executables |
| `COMSPEC` | `C:\COMMAND.COM` | Command interpreter path |
| `TEMP` | `C:\TEMP` | Temporary directory |
| `TMP` | `C:\TEMP` | Temporary directory |

## Limitations and Known Issues

### Not Implemented

1. **Pipes (`|`)**: Command piping is not supported
2. **Redirection (`>`, `<`, `>>`)**: I/O redirection is not supported
3. **Command chaining (`&&`, `||`)**: Multiple command execution is not supported
4. **Background execution (`&`)**: Not applicable in this environment

### Partial Implementations

1. **Batch Files**: Basic execution works, but advanced features (loops, conditionals) are not implemented
2. **Wildcards**: Only DEL supports wildcards; COPY and DIR have limited support

## Future Enhancements

Planned features for future releases:

- [ ] Full batch file control structures (IF, FOR, GOTO)
- [ ] I/O redirection support
- [ ] Command history and line editing
- [ ] Tab completion for filenames
- [ ] Additional commands: ATTRIB, FIND, MORE, SORT
- [ ] Network drive simulation (NET USE)

## Version History

### Version 1.0 (Current)

- Initial release with core DOS commands
- SSH server with password authentication
- User isolation and home directory mapping
- Basic batch file support

---

*Last Updated: 2024*
*DosPC Sim DOS Environment Version 1.0*
