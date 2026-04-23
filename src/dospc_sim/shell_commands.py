"""Shell command implementations and shared command metadata."""

import difflib
import fnmatch
import re
from datetime import datetime

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
    'TIME',
    'TREE',
    'TYPE',
    'VER',
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
    'TIME': 'Displays or sets the system time.',
    'TREE': 'Graphically displays the directory structure.\n\nTREE [path] [/F]',
    'TYPE': 'Displays the contents of a text file.',
    'VER': 'Displays the operating system version.',
}


def get_shell_command_names() -> tuple[str, ...]:
    """Return supported DOS command names."""
    return SHELL_COMMAND_NAMES


def get_shell_command_help(command: str) -> str:
    """Return help text for a DOS command."""
    return SHELL_COMMAND_HELP_TEXTS.get(
        command.upper(), f'Help not available for {command}'
    )


class DOSShellCommandProvider:
    """Command implementations for the DOS shell runtime."""

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
                    f' Volume in drive {self.fs._drive_letter} is DOSPC-SIM'
                )
                self._output_line(f' Directory of {self.fs.get_current_path()}')
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
                        self._output('Are you sure (Y/N)? ')
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
                    entries = self.fs.list_directory()
                    for entry in entries:
                        if (
                            fnmatch.fnmatch(entry.name.upper(), pattern.upper())
                            and not entry.is_dir
                        ):
                            if not quiet:
                                self._output_line(f'Deleting {entry.name}')
                            self.fs.delete_file(entry.name)
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
            target = self.fs._resolve_path(path)
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
