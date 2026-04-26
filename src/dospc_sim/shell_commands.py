"""Shell command implementations and shared command metadata."""

import difflib
import fnmatch
import re
import time
from datetime import datetime

from dospc_sim.jcs import JobStatus

SHELL_COMMAND_NAMES: tuple[str, ...] = (
    'CALL',
    'CD',
    'CHDIR',
    'CLS',
    'COPY',
    'DATE',
    'DEL',
    'DIR',
    'ECHO',
    'EDIT',
    'ERASE',
    'EXIT',
    'FC',
    'FIND',
    'FOR',
    'GOTO',
    'HELP',
    'IF',
    'JOBERR',
    'JOBOUT',
    'JOBS',
    'KILL',
    'MD',
    'MKDIR',
    'MORE',
    'MOVE',
    'PATH',
    'PAUSE',
    'PROMPT',
    'RD',
    'REN',
    'RENAME',
    'RMDIR',
    'SET',
    'SORT',
    'START',
    'TIME',
    'TREE',
    'TYPE',
    'VER',
    'WAIT',
)

SHELL_COMMAND_HELP_TEXTS: dict[str, str] = {
    'CALL': 'Calls one batch program from another.\n\nCALL batchfile [parameters]',
    'CD': 'Displays the name of or changes the current directory.',
    'CHDIR': 'Displays the name of or changes the current directory.',
    'CLS': 'Clears the screen.',
    'COPY': 'Copies one or more files to another location.',
    'DATE': 'Displays or sets the date.',
    'DEL': 'Deletes one or more files.',
    'DIR': 'Displays a list of files and subdirectories in a directory.',
    'ECHO': 'Displays messages, or turns command-echoing on or off.',
    'EDIT': 'Starts the DosPC Sim text editor.\n\nEDIT [filename]',
    'ERASE': 'Deletes one or more files.',
    'EXIT': 'Quits the command interpreter.',
    'FC': 'Compares two files and displays the differences.\n\nFC [/N] file1 file2',
    'FIND': (
        'Searches for a text string in a file.'
        '\n\nFIND [/V] [/C] [/I] [/N] "string" filename'
    ),
    'FOR': (
        'Runs a specified command for each file in a set.'
        '\n\nFOR %%var IN (set) DO command'
    ),
    'GOTO': 'Directs the command interpreter to a labelled line.\n\nGOTO label',
    'HELP': 'Provides help information for commands.',
    'IF': (
        'Performs conditional processing in batch programs.'
        '\n\nIF [NOT] ERRORLEVEL number command'
        '\nIF [NOT] string1==string2 command'
        '\nIF [NOT] EXIST filename command'
        '\nIF [NOT] DEFINED variable command'
        '\nIF condition command ELSE command'
    ),
    'JOBERR': (
        'Displays captured stderr of a background job.'
        '\n\nJOBERR jobid [/TAIL] [/N:lines]'
    ),
    'JOBOUT': (
        'Displays captured stdout of a background job.'
        '\n\nJOBOUT jobid [/TAIL] [/N:lines]'
    ),
    'JOBS': ('Lists all background jobs in the job table.\n\nJOBS [/V] [/PURGE]'),
    'KILL': (
        'Terminates one or all background jobs.\n\nKILL jobid [/F]\nKILL /ALL [/F]'
    ),
    'MD': 'Creates a directory.',
    'MKDIR': 'Creates a directory.',
    'MORE': 'Displays output one screen at a time.\n\nMORE filename',
    'MOVE': 'Moves one or more files from one directory to another.',
    'PATH': 'Displays or sets a search path for executable files.',
    'PAUSE': 'Suspends processing of a batch file and displays a message.',
    'PROMPT': 'Changes the command prompt.',
    'RD': 'Removes a directory.',
    'REN': 'Renames a file or files.',
    'RENAME': 'Renames a file or files.',
    'RMDIR': 'Removes a directory.',
    'SET': 'Displays, sets, or removes environment variables.',
    'SORT': 'Sorts input lines.\n\nSORT [/R] [filename] [/O outputfile]',
    'START': (
        'Starts a command in a background job.\n\nSTART /B [/ID:name] command [args...]'
    ),
    'TIME': 'Displays or sets the system time.',
    'TREE': 'Graphically displays the directory structure.\n\nTREE [path] [/F]',
    'TYPE': 'Displays the contents of a text file.',
    'VER': 'Displays the operating system version.',
    'WAIT': (
        'Waits for one or all background jobs to complete.'
        '\n\nWAIT jobid [/T:seconds]'
        '\nWAIT /ALL [/T:seconds]'
    ),
}


def get_shell_command_names() -> tuple[str, ...]:
    """Return supported DOS command names."""
    return SHELL_COMMAND_NAMES


def get_shell_command_help(command: str) -> str:
    """Return help text for a DOS command."""
    return SHELL_COMMAND_HELP_TEXTS.get(
        command.upper(), f'Help not available for {command}'
    )


class FileSystemCommandGroup:
    """Filesystem-oriented DOS commands."""

    def cmd_dir(self, args: list[str]) -> int:
        path = '.'
        show_all = False
        wide_format = False
        pattern = None

        for arg in args:
            upper = arg.upper()
            if upper == '/W':
                wide_format = True
            elif upper == '/A':
                show_all = True
            elif not arg.startswith('/'):
                path = arg

        if '*' in path or '?' in path:
            separator_index = max(path.rfind('/'), path.rfind('\\'))
            if separator_index >= 0:
                pattern = path[separator_index + 1 :]
                path = path[:separator_index]
            else:
                pattern = path
                path = '.'

        try:
            entries = self.fs.list_directory(path)
            if pattern:
                entries = [
                    e
                    for e in entries
                    if fnmatch.fnmatch(e.name.upper(), pattern.upper())
                ]
            if not wide_format:
                self._output_line(
                    f' Volume in drive {self.fs.drive_letter} is DOSPC-SIM'
                )
                resolved = self.fs.resolve_path(path)
                try:
                    rel = resolved.relative_to(self.fs.home_dir)
                    if str(rel) == '.':
                        dir_display = f'{self.fs.drive_letter}:\\'
                    else:
                        rel_str = str(rel).replace('/', '\\')
                        dir_display = f'{self.fs.drive_letter}:\\{rel_str}'
                except ValueError:
                    dir_display = self.fs.get_current_path()
                self._output_line(f' Directory of {dir_display}')
                self._output_line()
                total_files = 0
                total_dirs = 0
                total_size = 0
                for entry in entries:
                    if not show_all and entry.name.startswith('.'):
                        continue
                    date_str = entry.modified.strftime('%m/%d/%Y')
                    time_str = entry.modified.strftime('%I:%M %p')
                    if entry.is_dir:
                        self._output_line(
                            f'{date_str}  {time_str}    <DIR>          {entry.name}'
                        )
                        total_dirs += 1
                    else:
                        size_str = f'{entry.size:>14,}'
                        self._output_line(
                            f'{date_str}  {time_str}{size_str} {entry.name}'
                        )
                        total_files += 1
                        total_size += entry.size
                self._output_line()
                self._output_line(
                    f'{"":>14}{total_files} File(s){total_size:>15,} bytes'
                )
                free_space = self.fs.get_free_space()
                self._output_line(
                    f'{"":>14}{total_dirs} Dir(s){free_space:>16,} bytes free'
                )
            else:
                names = [
                    e.name for e in entries if show_all or not e.name.startswith('.')
                ]
                for i in range(0, len(names), 5):
                    row = names[i : i + 5]
                    self._output_line('  '.join(f'{n:<15}' for n in row))
            return 0
        except Exception:
            self._output_line(f'File not found: {path}')
            return 1

    def cmd_cd(self, args: list[str]) -> int:
        if not args:
            self._output_line(self.fs.get_current_path())
            return 0
        try:
            self.fs.change_directory(args[0])
            return 0
        except Exception:
            self._output_line('The system cannot find the path specified.')
            return 1

    cmd_chdir = cmd_cd

    def cmd_md(self, args: list[str]) -> int:
        if not args:
            self._output_line('The syntax of the command is incorrect.')
            return 1
        for dirname in args:
            try:
                self.fs.make_directory(dirname)
            except FileExistsError:
                self._output_line(f'A subdirectory or file {dirname} already exists.')
                return 1
            except Exception as e:
                self._output_line(f'Error creating directory: {e!s}')
                return 1
        return 0

    cmd_mkdir = cmd_md

    def cmd_rd(self, args: list[str]) -> int:
        if not args:
            self._output_line('The syntax of the command is incorrect.')
            return 1
        recursive = False
        quiet = False
        dirs = []
        for arg in args:
            if arg.upper() == '/S':
                recursive = True
            elif arg.upper() == '/Q':
                quiet = True
            elif not arg.startswith('/'):
                dirs.append(arg)
        for dirname in dirs:
            try:
                if recursive:
                    if not quiet:
                        self._output(f'{dirname}, Are you sure (Y/N)? ')
                        response = ''
                        if self._input_callback:
                            response = self._input_callback() or ''
                        if not response.strip().upper().startswith('Y'):
                            continue
                    self.fs.remove_directory_recursive(dirname)
                else:
                    self.fs.remove_directory(dirname)
            except Exception as e:
                self._output_line(f'Error removing directory: {e!s}')
                return 1
        return 0

    cmd_rmdir = cmd_rd

    def cmd_copy(self, args: list[str]) -> int:
        if len(args) < 2:
            self._output_line('The syntax of the command is incorrect.')
            return 1
        source = args[0]
        dest = args[-1]
        if '*' in source or '?' in source:
            normalized_source = source.replace('/', '\\')
            if '\\' in normalized_source:
                src_dir, src_pattern = normalized_source.rsplit('\\', 1)
            else:
                src_dir, src_pattern = '.', normalized_source
            try:
                entries = self.fs.list_directory(src_dir)
            except Exception:
                self._output_line('The system cannot find the file specified.')
                return 1
            matched = [
                e
                for e in entries
                if not e.is_dir and fnmatch.fnmatch(e.name.upper(), src_pattern.upper())
            ]
            if not matched:
                self._output_line('The system cannot find the file specified.')
                return 1

            try:
                dest_is_dir = self.fs.dir_exists(dest)
            except Exception:
                dest_is_dir = False
            if len(matched) > 1 and not dest_is_dir:
                self._output_line('The system cannot find the path specified.')
                return 1

            count = 0
            for entry in matched:
                src_path = entry.name if src_dir == '.' else f'{src_dir}\\{entry.name}'
                try:
                    self.fs.copy_file(src_path, dest)
                except Exception:
                    self._output_line('The system cannot find the path specified.')
                    return 1
                count += 1
            self._output_line(f'        {count} file(s) copied.')
            return 0
        try:
            self.fs.copy_file(source, dest)
            self._output_line('        1 file(s) copied.')
            return 0
        except Exception:
            self._output_line('The system cannot find the file specified.')
            return 1

    def cmd_del(self, args: list[str]) -> int:
        if not args:
            self._output_line('The syntax of the command is incorrect.')
            return 1
        quiet = False
        files = []
        for arg in args:
            if arg.upper() == '/Q':
                quiet = True
            elif not arg.startswith('/'):
                files.append(arg)
        for pattern in files:
            try:
                if '*' in pattern or '?' in pattern:
                    normalized = pattern.replace('/', '\\')
                    if '\\' in normalized:
                        dir_part, file_pattern = normalized.rsplit('\\', 1)
                    else:
                        dir_part, file_pattern = '.', normalized
                    entries = self.fs.list_directory(dir_part)
                    for entry in entries:
                        if (
                            fnmatch.fnmatch(entry.name.upper(), file_pattern.upper())
                            and not entry.is_dir
                        ):
                            if dir_part == '.':
                                full_path = entry.name
                            else:
                                full_path = f'{dir_part}\\{entry.name}'
                            if not quiet:
                                self._output_line(f'Deleting {full_path}')
                            self.fs.delete_file(full_path)
                else:
                    self.fs.delete_file(pattern)
            except Exception:
                self._output_line(f'Could not find {pattern}')
                return 1
        return 0

    cmd_erase = cmd_del

    def cmd_ren(self, args: list[str]) -> int:
        if len(args) < 2:
            self._output_line('The syntax of the command is incorrect.')
            return 1
        try:
            self.fs.rename(args[0], args[1])
            return 0
        except Exception:
            self._output_line('Duplicate file name or file not found')
            return 1

    cmd_rename = cmd_ren

    def cmd_move(self, args: list[str]) -> int:
        if len(args) < 2:
            self._output_line('The syntax of the command is incorrect.')
            return 1
        try:
            self.fs.move_file(args[0], args[-1])
            self._output_line('        1 file(s) moved.')
            return 0
        except Exception:
            self._output_line('The system cannot find the file specified.')
            return 1

    def cmd_type(self, args: list[str]) -> int:
        if not args:
            self._output_line('The syntax of the command is incorrect.')
            return 1
        try:
            self._output_line(self.fs.read_file(args[0]))
            return 0
        except Exception:
            self._output_line('The system cannot find the file specified.')
            return 1

    def cmd_tree(self, args: list[str]) -> int:
        path = '.'
        show_files = False
        for arg in args:
            upper = arg.upper()
            if upper == '/F':
                show_files = True
            elif not arg.startswith('/'):
                path = arg
        try:
            target = self.fs.resolve_path(path)
            if not target.exists():
                self._output_line(f'Path not found: {path}')
                return 1
            if not target.is_dir():
                self._output_line(f'Not a directory: {path}')
                return 1
            rel = self.fs.get_current_path()
            if path != '.':
                rel = path
            self._output_line(f'Folder PATH listing for {rel}')
            self._output_line('Volume serial number is DosPC-Sim')
            self._output_line('.')
            lines = []
            self._build_tree(target, target, '', show_files, lines)
            for line in lines:
                self._output_line(line)
            return 0
        except PermissionError:
            self._output_line('Access denied')
            return 1

    def _build_tree(self, root, current, prefix, show_files, lines):
        entries = sorted(
            current.iterdir(), key=lambda e: (not e.is_dir(), e.name.upper())
        )
        dirs = [e for e in entries if e.is_dir()]
        files = [e for e in entries if e.is_file()]
        all_items = dirs[:]
        if show_files:
            all_items.extend(files)
        for i, item in enumerate(all_items):
            is_last = i == len(all_items) - 1
            connector = '└── ' if is_last else '├── '
            lines.append(f'{prefix}{connector}{item.name}')
            if item.is_dir():
                extension = '    ' if is_last else '│   '
                self._build_tree(root, item, prefix + extension, show_files, lines)


class ShellCoreCommandGroup:
    """Shell state and informational DOS commands."""

    def cmd_cls(self, args: list[str]) -> int:
        self._output('\x1b[2J\x1b[H')
        return 0

    def cmd_echo(self, args: list[str]) -> int:
        if not args:
            self._output_line(f'ECHO is {"on" if self._echo_on else "off"}')
            return 0
        if len(args) == 1 and args[0].upper() == 'ON':
            self._echo_on = True
            return 0
        if len(args) == 1 and args[0].upper() == 'OFF':
            self._echo_on = False
            return 0
        text = ' '.join(args)
        if (text.startswith('"') and text.endswith('"')) or (
            text.startswith("'") and text.endswith("'")
        ):
            text = text[1:-1]
        self._output_line(text)
        return 0

    def cmd_help(self, args: list[str]) -> int:
        if args:
            self._output_line(self._get_command_help(args[0].upper()))
        else:
            self._output_line(
                'For more information on a specific command, type HELP command-name'
            )
            self._output_line()
            commands = list(get_shell_command_names())
            for i in range(0, len(commands), 6):
                row = commands[i : i + 6]
                self._output_line('  '.join(f'{c:<10}' for c in row))
        return 0

    def _get_command_help(self, cmd: str) -> str:
        return get_shell_command_help(cmd)

    def cmd_exit(self, args: list[str]) -> int:
        self.running = False
        return 0

    def cmd_ver(self, args: list[str]) -> int:
        self._output_line()
        self._output_line('DosPC Sim DOS [Version 1.0]')
        self._output_line()
        return 0

    def cmd_set(self, args: list[str]) -> int:
        if not args:
            for key, value in sorted(self.environment.items()):
                self._output_line(f'{key}={value}')
            return 0
        arg = ' '.join(args)
        if '=' in arg:
            parts = arg.split('=', 1)
            var_name = parts[0].strip()
            var_value = parts[1].strip() if len(parts) > 1 else ''
            self.environment[var_name.upper()] = var_value
        else:
            var_name = arg.strip().upper()
            if var_name in self.environment:
                self._output_line(f'{var_name}={self.environment[var_name]}')
            else:
                self._output_line(f'Environment variable {var_name} not defined')
                return 1
        return 0

    def cmd_prompt(self, args: list[str]) -> int:
        if args:
            self.environment['PROMPT'] = ' '.join(args)
        else:
            self._output_line(f'Current prompt: {self.environment["PROMPT"]}')
        return 0

    def cmd_path(self, args: list[str]) -> int:
        if args:
            self.environment['PATH'] = ' '.join(args)
        else:
            self._output_line(f'PATH={self.environment["PATH"]}')
        return 0

    def cmd_date(self, args: list[str]) -> int:
        self._output_line(f'Current date: {datetime.now().strftime("%a %m/%d/%Y")}')
        return 0

    def cmd_time(self, args: list[str]) -> int:
        self._output_line(
            f'Current time: {datetime.now().strftime("%I:%M:%S.%f %p")[:12]}'
        )
        return 0


class TextProcessingCommandGroup:
    """Text-processing and editor DOS commands."""

    def cmd_find(self, args: list[str]) -> int:
        if not args:
            self._output_line('FIND [/V] [/C] [/I] [/N] "string" [filename]')
            self._output_line('  /V  Displays all lines NOT containing the string.')
            self._output_line(
                '  /C  Displays only the count of lines containing the string.'
            )
            self._output_line('  /I  Case-insensitive search.')
            self._output_line('  /N  Displays line numbers with displayed lines.')
            return 1

        invert = False
        count_only = False
        case_insensitive = False
        show_numbers = False
        search_string = None
        filename = None

        i = 0
        while i < len(args):
            upper = args[i].upper()
            if upper == '/V':
                invert = True
            elif upper == '/C':
                count_only = True
            elif upper == '/I':
                case_insensitive = True
            elif upper == '/N':
                show_numbers = True
            elif search_string is None:
                search_string = args[i]
            else:
                filename = args[i]
            i += 1

        if search_string is None:
            self._output_line('FIND: Parameter format not correct')
            return 1

        if filename is not None:
            try:
                content = self.fs.read_file(filename)
            except (FileNotFoundError, IsADirectoryError):
                self._output_line(f'File not found: {filename}')
                return 1
        elif self._piped_input:
            content = self._piped_input
        else:
            self._output_line('FIND: Parameter format not correct')
            return 1

        search_in = search_string.lower() if case_insensitive else search_string
        file_lines = content.splitlines()
        match_lines = []
        match_count = 0

        for idx, line in enumerate(file_lines, 1):
            check_line = line.lower() if case_insensitive else line
            found = search_in in check_line
            if (found and not invert) or (not found and invert):
                match_count += 1
                if not count_only:
                    prefix = f'[{idx}]' if show_numbers else ''
                    match_lines.append(f'{prefix}{line}')

        self._output_line(f'---------- {filename.upper() if filename else "STDIN"}')

        if count_only:
            self._output_line(f'{match_count}')
        else:
            for ml in match_lines:
                self._output_line(ml)

        return 1 if match_count == 0 else 0

    def cmd_more(self, args: list[str]) -> int:
        if not args and not self._piped_input:
            self._output_line('Usage: MORE [filename]')
            return 1
        if args:
            try:
                content = self.fs.read_file(args[0])
            except (FileNotFoundError, IsADirectoryError):
                self._output_line(f'File not found: {args[0]}')
                return 1
        else:
            content = self._piped_input
        lines = content.splitlines()
        page_size = 24
        for i, line in enumerate(lines):
            self._output_line(line)
            if (i + 1) % page_size == 0 and (i + 1) < len(lines):
                self._output('-- More --')
        return 0

    def cmd_sort(self, args: list[str]) -> int:
        reverse = False
        filename = None
        output_file = None
        i = 0
        while i < len(args):
            upper = args[i].upper()
            if upper == '/R':
                reverse = True
            elif upper == '/O' and i + 1 < len(args):
                i += 1
                output_file = args[i]
            elif not args[i].startswith('/'):
                filename = args[i]
            i += 1

        if filename:
            try:
                content = self.fs.read_file(filename)
            except (FileNotFoundError, IsADirectoryError):
                self._output_line(f'File not found: {filename}')
                return 1
            lines = content.splitlines()
        elif self._piped_input:
            lines = self._piped_input.splitlines()
        else:
            lines = []

        sorted_lines = sorted(lines, reverse=reverse)
        if output_file:
            self.fs.write_file(output_file, '\n'.join(sorted_lines) + '\n')
            return 0
        for line in sorted_lines:
            self._output_line(line)
        return 0

    def cmd_fc(self, args: list[str]) -> int:
        if len(args) < 2:
            self._output_line('Usage: FC [/N] file1 file2')
            return 1
        show_numbers = any(arg.upper() == '/N' for arg in args)
        filenames = []
        for arg in args:
            if arg.upper() == '/N':
                continue
            if not arg.startswith('/'):
                filenames.append(arg)
        if len(filenames) < 2:
            self._output_line('Usage: FC [/N] file1 file2')
            return 1

        try:
            content1 = self.fs.read_file(filenames[0])
        except (FileNotFoundError, IsADirectoryError):
            self._output_line(f'File not found: {filenames[0]}')
            return 1
        try:
            content2 = self.fs.read_file(filenames[1])
        except (FileNotFoundError, IsADirectoryError):
            self._output_line(f'File not found: {filenames[1]}')
            return 1

        lines1 = content1.splitlines()
        lines2 = content2.splitlines()

        if lines1 == lines2:
            self._output_line(f'Comparing files {filenames[0]} and {filenames[1]}')
            self._output_line('FC: no differences encountered')
            return 0

        self._output_line(f'Comparing files {filenames[0]} and {filenames[1]}')

        diff = difflib.unified_diff(lines1, lines2, lineterm='', n=0)
        patch_lines = list(diff)[2:]
        in_hunk_1 = False
        in_hunk_2 = False
        old_line = 1
        new_line = 1
        for pl in patch_lines:
            if pl.startswith('@@'):
                in_hunk_1 = False
                in_hunk_2 = False
                match = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@$', pl)
                if match:
                    old_line = int(match.group(1))
                    new_line = int(match.group(2))
                continue
            if pl.startswith('-'):
                if not in_hunk_1:
                    self._output_line(f'***** {filenames[0]}')
                    in_hunk_1 = True
                    in_hunk_2 = False
                line_text = pl[1:]
                if show_numbers:
                    self._output_line(f'{old_line}: {line_text}')
                else:
                    self._output_line(line_text)
                old_line += 1
            elif pl.startswith('+'):
                if not in_hunk_2:
                    self._output_line(f'***** {filenames[1]}')
                    in_hunk_2 = True
                    in_hunk_1 = False
                line_text = pl[1:]
                if show_numbers:
                    self._output_line(f'{new_line}: {line_text}')
                else:
                    self._output_line(line_text)
                new_line += 1
        return 1

    def cmd_edit(self, args: list[str]) -> int:
        filename = args[0] if args else ''
        if hasattr(self, '_editor_input_handler') and self._editor_input_handler:
            return self._editor_input_handler(filename)
        self._output_line('EDIT requires an interactive terminal session.')
        self._output_line('Usage: EDIT [filename]')
        return 1


class JobCommandGroup:
    """Background job management DOS commands."""

    def cmd_start(self, args: list[str]) -> int:
        background = False
        job_name = None
        cmd_args = []
        expect_id_value = False
        i = 0
        while i < len(args):
            upper = args[i].upper()
            if expect_id_value:
                expect_id_value = False
                val = args[i]
                if val.startswith(':'):
                    val = val[1:]
                job_name = val
            elif upper == '/B' and not cmd_args:
                background = True
            elif upper == '/ID' and not cmd_args:
                expect_id_value = True
            elif not cmd_args and upper.startswith('/ID:'):
                job_name = args[i][4:]
            else:
                cmd_args.append(args[i])
            i += 1

        if not background:
            self._output_line('START requires /B flag in this environment.')
            self.last_errorlevel = 1
            return 1

        if not cmd_args:
            self._output_line('ERROR: COULD NOT START: (no command)')
            self.last_errorlevel = 1
            return 1

        command_str = ' '.join(cmd_args)
        parent_cwd = self.fs.get_current_path()
        parent_env = dict(self.environment)
        parent_echo = self._echo_on
        parent_jcs = self.jcs

        def execute_fn(stdout_cb, stderr_cb):
            from dospc_sim.dos_shell import DOSShell
            from dospc_sim.filesystem import UserFilesystem

            bg_fs = UserFilesystem(str(self.fs.home_dir), self.username)
            bg_shell = DOSShell(bg_fs, self.username, stdout_cb)
            bg_shell.environment = dict(parent_env)
            bg_shell._echo_on = parent_echo
            bg_shell.jcs = parent_jcs
            try:
                bg_fs.change_directory(parent_cwd)
            except Exception:
                pass
            try:
                return bg_shell.execute_command(command_str)
            except Exception as exc:
                stderr_cb(f'ERROR: COULD NOT START: {command_str}: {exc}')
                raise

        _entry, error = self.jcs.spawn(command_str, execute_fn, job_name)
        if error:
            self._output_line(error)
            self.last_errorlevel = 1
            return 1

        self.last_errorlevel = 0
        return 0

    def cmd_jobs(self, args: list[str]) -> int:
        self.jcs.reap()
        verbose = any(a.upper() == '/V' for a in args)
        purge = any(a.upper() == '/PURGE' for a in args)

        if purge:
            self.jcs.purge_completed()
            self.jcs.reap()

        jobs = self.jcs.get_all_jobs()
        if not jobs:
            if not self.jcs.has_any_jobs():
                self.last_errorlevel = 1
                return 1
            self.last_errorlevel = 0
            return 0

        if verbose:
            self._output_line(
                f'  {"ID":<10}{"TID":<7}{"STATUS":<10}'
                f'{"EXIT":<6}{"STARTED":<10}{"COMMAND"}'
            )
            self._output_line(
                f'  {"--------":<10}{"-----":<7}{"--------":<10}'
                f'{"----":<6}{"--------":<10}{"-" * 23}'
            )
            for job in jobs:
                tid = ''
                if job.thread and job.thread.ident:
                    tid = str(job.thread.ident)[:5]
                exit_str = str(job.exit_code) if job.status != JobStatus.RUNNING else ''
                time_str = job.start_time.strftime('%H:%M:%S')
                cmd_display = job.command[:23] if len(job.command) > 23 else job.command
                self._output_line(
                    f'  {job.id:<10}{tid:<7}{job.status.name:<10}'
                    f'{exit_str:<6}{time_str:<10}{cmd_display}'
                )
        else:
            self._output_line(f'  {"ID":<10}{"STATUS":<10}{"EXIT":<6}')
            self._output_line(f'  {"--------":<10}{"--------":<10}{"----":<6}')
            for job in jobs:
                exit_str = str(job.exit_code) if job.status != JobStatus.RUNNING else ''
                self._output_line(f'  {job.id:<10}{job.status.name:<10}{exit_str:<6}')

        self.last_errorlevel = 0
        return 0

    def cmd_wait(self, args: list[str]) -> int:
        self.jcs.reap()
        wait_all = False
        job_id = None
        timeout = None

        i = 0
        while i < len(args):
            upper = args[i].upper()
            if upper == '/ALL':
                wait_all = True
            elif upper == '/T' and i + 1 < len(args) and args[i + 1].startswith(':'):
                try:
                    timeout = float(args[i + 1][1:])
                except ValueError:
                    self._output_line('ERROR: INVALID TIMEOUT VALUE')
                    self.last_errorlevel = 1
                    return 1
                i += 1
            elif upper.startswith('/T:'):
                try:
                    timeout = float(upper[3:])
                except ValueError:
                    self._output_line('ERROR: INVALID TIMEOUT VALUE')
                    self.last_errorlevel = 1
                    return 1
            elif not args[i].startswith('/') and not args[i].startswith(':'):
                job_id = args[i]
            i += 1

        if not wait_all and job_id is None:
            self._output_line(
                'Usage: WAIT jobid [/T:seconds] or WAIT /ALL [/T:seconds]'
            )
            self.last_errorlevel = 1
            return 1

        if wait_all:
            running = self.jcs.get_running_jobs()
            if not running:
                all_jobs = self.jcs.get_all_jobs()
                highest_exit = 0
                for job in all_jobs:
                    if job.exit_code == 0:
                        self._output_line(f'{job.id} completed (exit code 0).')
                    else:
                        self._output_line(
                            f'{job.id} failed (exit code {job.exit_code}).'
                        )
                        if job.exit_code > highest_exit:
                            highest_exit = job.exit_code
                self.last_errorlevel = highest_exit
                return highest_exit
            highest_exit = 0
            for job in running:
                completed = self.jcs.wait_job(job, timeout)
                self.jcs.reap()
                if not completed:
                    self._output_line(f'WAIT TIMEOUT: {job.id}')
                    self.last_errorlevel = 2
                    return 2
                if job.exit_code == 0:
                    self._output_line(f'{job.id} completed (exit code 0).')
                else:
                    self._output_line(f'{job.id} failed (exit code {job.exit_code}).')
                    if job.exit_code > highest_exit:
                        highest_exit = job.exit_code
            self.last_errorlevel = highest_exit
            return highest_exit

        job = self.jcs.get_job(job_id)
        if job is None:
            self._output_line(f'ERROR: NO SUCH JOB: {job_id.upper()}')
            self.last_errorlevel = 1
            return 1

        completed = self.jcs.wait_job(job, timeout)
        self.jcs.reap()
        if not completed:
            self._output_line(f'WAIT TIMEOUT: {job.id}')
            self.last_errorlevel = 2
            return 2

        if job.exit_code == 0:
            self._output_line(f'{job.id} completed (exit code 0).')
            self.last_errorlevel = 0
            return 0
        else:
            self._output_line(f'{job.id} failed (exit code {job.exit_code}).')
            self.last_errorlevel = job.exit_code
            return job.exit_code

    def cmd_kill(self, args: list[str]) -> int:
        self.jcs.reap()
        kill_all = False
        force = False
        job_id = None

        for arg in args:
            upper = arg.upper()
            if upper == '/ALL':
                kill_all = True
            elif upper == '/F':
                force = True
            elif not arg.startswith('/'):
                job_id = arg

        if not kill_all and job_id is None:
            self._output_line('Usage: KILL jobid [/F] or KILL /ALL [/F]')
            self.last_errorlevel = 1
            return 1

        if kill_all:
            running = self.jcs.get_running_jobs()
            if not running:
                self.last_errorlevel = 0
                return 0
            for job in running:
                if self.jcs.kill_job(job, force):
                    self._output_line(f'{job.id} terminated.')
                else:
                    self._output_line(f'ERROR: COULD NOT TERMINATE: {job.id}')
                    self.last_errorlevel = 2
                    return 2
            self.last_errorlevel = 0
            return 0

        job = self.jcs.get_job(job_id)
        if job is None:
            self._output_line(f'ERROR: NO SUCH JOB: {job_id.upper()}')
            self.last_errorlevel = 1
            return 1

        if job.status != JobStatus.RUNNING:
            self._output_line(f'ERROR: JOB NOT RUNNING: {job.id}')
            self.last_errorlevel = 1
            return 1

        if self.jcs.kill_job(job, force):
            self._output_line(f'{job.id} terminated.')
            self.last_errorlevel = 0
            return 0
        else:
            self._output_line(f'ERROR: COULD NOT TERMINATE: {job.id}')
            self.last_errorlevel = 2
            return 2

    def cmd_jobout(self, args: list[str]) -> int:
        return self._job_output(args, 'stdout')

    def cmd_joberr(self, args: list[str]) -> int:
        return self._job_output(args, 'stderr')

    def _job_output(self, args: list[str], stream: str) -> int:
        self.jcs.reap()
        job_id = None
        tail = False
        n_lines = None

        i = 0
        while i < len(args):
            upper = args[i].upper()
            if upper == '/TAIL':
                tail = True
            elif upper == '/N' and i + 1 < len(args) and args[i + 1].startswith(':'):
                try:
                    n_lines = int(args[i + 1][1:])
                except ValueError:
                    pass
                i += 1
            elif upper.startswith('/N:'):
                try:
                    n_lines = int(upper[3:])
                except ValueError:
                    pass
            elif not args[i].startswith('/') and not args[i].startswith(':'):
                job_id = args[i]
            i += 1

        if job_id is None:
            cmd_name = 'JOBOUT' if stream == 'stdout' else 'JOBERR'
            self._output_line(f'Usage: {cmd_name} jobid [/TAIL] [/N:lines]')
            self.last_errorlevel = 1
            return 1

        job = self.jcs.get_job(job_id)
        if job is None:
            self._output_line(f'ERROR: NO SUCH JOB: {job_id.upper()}')
            self.last_errorlevel = 1
            return 1

        if tail:
            seen_len = 0
            while True:
                self.jcs.reap()
                with job._lock:
                    buf = job.stdout_buf if stream == 'stdout' else job.stderr_buf
                    new_data = buf[seen_len:]
                    seen_len = len(buf)
                    done = job.status != JobStatus.RUNNING
                if new_data:
                    for line in new_data.splitlines():
                        self._output_line(line)
                if done:
                    with job._lock:
                        buf = job.stdout_buf if stream == 'stdout' else job.stderr_buf
                        final = buf[seen_len:]
                    if final:
                        for line in final.splitlines():
                            self._output_line(line)
                    break
                time.sleep(0.25)
        else:
            with job._lock:
                buf = job.stdout_buf if stream == 'stdout' else job.stderr_buf
            lines = buf.splitlines()
            if n_lines is not None:
                lines = lines[-n_lines:]
            for line in lines:
                self._output_line(line)

        self.last_errorlevel = 0
        return 0


class DOSShellCommandProvider(
    FileSystemCommandGroup,
    ShellCoreCommandGroup,
    TextProcessingCommandGroup,
    JobCommandGroup,
):
    """Command implementations for the DOS shell runtime."""
