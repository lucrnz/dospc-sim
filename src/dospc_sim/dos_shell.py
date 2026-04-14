"""DOS shell simulation for SSH clients."""

import re
from collections.abc import Callable
from datetime import datetime

from dospc_sim.filesystem import UserFilesystem
from dospc_sim.parser import (
    CallCommand,
    CommandLine,
    EchoCommand,
    ForCommand,
    GotoCommand,
    IfCommand,
    IfCompareCondition,
    IfErrorlevelCondition,
    IfExistCondition,
    Label,
    PauseCommand,
    PipeCommand,
    SimpleCommand,
    Switch,
    parse_command,
)

_ENV_VAR_RE = re.compile(r'%([^%]+)%')


class _GotoSignal(Exception):
    """Signal raised by GOTO to jump to a label in batch execution."""

    def __init__(self, label: str):
        self.label = label


class DOSShell:
    """Simulates a DOS environment for SSH clients."""

    def __init__(
        self,
        filesystem: UserFilesystem,
        username: str,
        output_callback: Callable[[str], None] | None = None,
    ):
        self.fs = filesystem
        self.username = username
        self.output_callback = output_callback or print
        self.running = False
        self.last_errorlevel = 0
        self.aliases: dict[str, str] = {}
        self.environment = {
            'PROMPT': '$P$G',
            'PATH': 'C:\\;C:\\DOS;C:\\WINDOWS',
            'COMSPEC': 'C:\\COMMAND.COM',
            'TEMP': 'C:\\TEMP',
            'TMP': 'C:\\TEMP',
        }
        self._piped_input: str | None = None
        self._input_callback: Callable[[], str] | None = None
        self._echo_on = True

    def _output(self, text: str = '') -> None:
        self.output_callback(text)

    def _output_line(self, text: str = '') -> None:
        self._output(text)

    def expand_variables(self, text: str) -> str:
        """Expand %VAR% environment variable references in text."""

        def _replace(match):
            var_name = match.group(1).upper()
            if var_name in self.environment:
                return self.environment[var_name]
            return match.group(0)

        return _ENV_VAR_RE.sub(_replace, text)

    def get_prompt(self) -> str:
        """Get the current DOS prompt."""
        prompt_str = self.environment.get('PROMPT', '$P$G')
        path = self.fs.get_current_path()
        now = datetime.now()
        prompt_str = prompt_str.replace('$$', '\x00')
        prompt_str = prompt_str.replace('$P', path).replace('$p', path)
        prompt_str = prompt_str.replace('$G', '>').replace('$g', '>')
        prompt_str = prompt_str.replace('$L', '<').replace('$l', '<')
        prompt_str = prompt_str.replace('$D', now.strftime('%m/%d/%Y')).replace(
            '$d', now.strftime('%m/%d/%Y')
        )
        prompt_str = prompt_str.replace('$T', now.strftime('%H:%M:%S')).replace(
            '$t', now.strftime('%H:%M:%S')
        )
        prompt_str = prompt_str.replace('$N', self.fs._drive_letter).replace(
            '$n', self.fs._drive_letter
        )
        prompt_str = prompt_str.replace('\x00', '$')
        return prompt_str

    def run(self) -> None:
        self.running = True
        self._output_line(f'Welcome, {self.username}!')
        self._output_line('Type HELP for available commands.')
        self._output_line()

    def execute_command(self, command_line: str) -> int:
        """Execute a single command string and return errorlevel."""
        command_line = command_line.strip()
        if not command_line:
            return 0

        command_line = self.expand_variables(command_line)
        parsed = parse_command(command_line)
        if parsed is None:
            return 0

        return self._execute_parsed(parsed)

    def _execute_parsed(self, parsed: CommandLine) -> int:
        """Execute a parsed CommandLine AST node."""
        ast = parsed.command

        if isinstance(ast, Label):
            return 0

        # Handle I/O redirection: capture output
        redirecting = parsed.stdout_redirect or parsed.append_redirect
        if redirecting:
            captured = []
            original_callback = self.output_callback
            self.output_callback = lambda text, buf=captured: buf.append(text)

        if parsed.stdin_redirect:
            try:
                self._piped_input = self.fs.read_file(parsed.stdin_redirect)
            except (FileNotFoundError, IsADirectoryError):
                self._output_line('The system cannot find the file specified.')
                if redirecting:
                    self.output_callback = original_callback
                self.last_errorlevel = 1
                self._piped_input = None
                return 1

        self.last_errorlevel = self._execute_ast(ast)

        if redirecting:
            self.output_callback = original_callback
            output_text = '\n'.join(captured)
            if parsed.append_redirect:
                try:
                    existing = self.fs.read_file(parsed.append_redirect)
                    output_text = existing + '\n' + output_text
                except (FileNotFoundError, IsADirectoryError):
                    pass
                self.fs.write_file(parsed.append_redirect, output_text)
            elif parsed.stdout_redirect:
                self.fs.write_file(parsed.stdout_redirect, output_text)

        self._piped_input = None
        return self.last_errorlevel

    def _execute_ast(self, ast) -> int:
        """Dispatch execution based on AST node type."""
        if isinstance(ast, EchoCommand):
            return self._execute_echo(ast)
        if isinstance(ast, SimpleCommand):
            return self._execute_simple(ast)
        if isinstance(ast, PipeCommand):
            return self._execute_pipe(ast)
        if isinstance(ast, GotoCommand):
            raise _GotoSignal(ast.label)
        if isinstance(ast, CallCommand):
            return self._execute_call(ast)
        if isinstance(ast, PauseCommand):
            return self._execute_pause()
        if isinstance(ast, IfCommand):
            return self._execute_if(ast)
        if isinstance(ast, ForCommand):
            return self._execute_for(ast)
        if isinstance(ast, Label):
            return 0
        return 0

    def _execute_echo(self, echo: EchoCommand) -> int:
        if echo.text is None:
            if echo.on is None:
                self._output_line(f'ECHO is {"on" if self._echo_on else "off"}')
            else:
                self._echo_on = echo.on
        else:
            self._output_line(echo.text)
        return 0

    def _execute_simple(self, cmd: SimpleCommand) -> int:
        command = cmd.command
        args = cmd.arguments
        positional = cmd.positional_args

        if command in self.aliases:
            alias_cmd = self.aliases[command]
            for i, arg in enumerate(positional, 1):
                alias_cmd = alias_cmd.replace(f'${i}', arg)
            alias_cmd = alias_cmd.replace('$*', ' '.join(positional))
            return self.execute_command(alias_cmd)

        try:
            handler = getattr(self, f'cmd_{command.lower()}', None)
            if handler:
                return handler(args)
            batch_file = self._find_batch_file(command)
            if batch_file:
                return self._execute_batch(batch_file, positional)
            self._output_line(f'Bad command or file name: {command}')
            return 1
        except Exception as e:
            self._output_line(f'Error: {e!s}')
            return 1

    def _execute_pipe(self, pipe: PipeCommand) -> int:
        if len(pipe.commands) < 2:
            if pipe.commands:
                return self._execute_simple(pipe.commands[0])
            return 1

        prev_output = None
        result = 0
        for i, cmd in enumerate(pipe.commands):
            is_last = i == len(pipe.commands) - 1
            self._piped_input = prev_output
            if is_last:
                result = self._execute_simple(cmd)
            else:
                captured = []
                original_callback = self.output_callback
                self.output_callback = lambda text, buf=captured: buf.append(text)
                self._execute_simple(cmd)
                self.output_callback = original_callback
                prev_output = '\n'.join(captured)
        self._piped_input = None
        self.last_errorlevel = result
        return result

    def _execute_call(self, call: CallCommand) -> int:
        target = call.target
        batch_file = self._find_batch_file(target.command)
        if batch_file:
            return self._execute_batch(batch_file, target.positional_args)
        self._output_line(f'Bad command or file name: {target.command}')
        return 1

    def _execute_pause(self) -> int:
        self._output('Press any key to continue . . . ')
        if self._input_callback:
            self._input_callback()
        return 0

    def _execute_if(self, if_cmd: IfCommand) -> int:
        cond = if_cmd.condition
        condition_met = False

        if isinstance(cond, IfExistCondition):
            condition_met = self.fs.file_exists(cond.filename) or self.fs.dir_exists(
                cond.filename
            )
        elif isinstance(cond, IfErrorlevelCondition):
            condition_met = self.last_errorlevel >= cond.level
        elif isinstance(cond, IfCompareCondition):
            condition_met = cond.left.upper() == cond.right.upper()

        if if_cmd.negated:
            condition_met = not condition_met

        if condition_met:
            return self._execute_parsed(if_cmd.command)
        return 0

    def _execute_for(self, for_cmd: ForCommand) -> int:
        result = 0
        inner = for_cmd.command
        raw_body = self._ast_to_raw(inner) if inner else ''
        for item in for_cmd.items:
            expanded = raw_body.replace(f'%%{for_cmd.var}', item)
            result = self.execute_command(expanded)
        return result

    def _ast_to_raw(self, cl: CommandLine) -> str:
        """Reconstruct a raw command string from a CommandLine AST node."""
        ast = cl.command
        if isinstance(ast, EchoCommand):
            if ast.text is None:
                return 'ECHO'
            return f'ECHO {ast.text}'
        if isinstance(ast, SimpleCommand):
            parts = [ast.command]
            for a in ast.args:
                if isinstance(a, Switch):
                    parts.append(f'/{a.name}')
                else:
                    parts.append(a.value)
            return ' '.join(parts)
        if isinstance(ast, GotoCommand):
            return f'GOTO {ast.label}'
        if isinstance(ast, IfCommand):
            parts = ['IF']
            if ast.negated:
                parts.append('NOT')
            cond = ast.condition
            if isinstance(cond, IfExistCondition):
                parts.append(f'EXIST {cond.filename}')
            elif isinstance(cond, IfErrorlevelCondition):
                parts.append(f'ERRORLEVEL {cond.level}')
            elif isinstance(cond, IfCompareCondition):
                parts.append(f'{cond.left}=={cond.right}')
            if ast.command:
                parts.append(self._ast_to_raw(ast.command))
            return ' '.join(parts)
        if isinstance(ast, PauseCommand):
            return 'PAUSE'
        if isinstance(ast, CallCommand):
            return f'CALL {self._ast_to_raw(CommandLine(command=ast.target))}'
        return ''

    def _find_batch_file(self, name: str) -> str | None:
        for ext in ['.BAT', '.CMD']:
            test_path = f'{name}{ext}'
            if self.fs.file_exists(test_path):
                return test_path
            for path_dir in self.environment['PATH'].split(';'):
                try:
                    path_dir = path_dir.strip()
                    if path_dir:
                        test_path = f'{path_dir}\\{name}{ext}'
                        if self.fs.file_exists(test_path):
                            return test_path
                except Exception:
                    continue
        return None

    def _execute_batch(self, batch_file: str, args: list[str]) -> int:
        """Execute a batch file via the Lark AST."""
        try:
            content = self.fs.read_file(batch_file)

            params = {0: batch_file}
            for i, arg in enumerate(args[:9], 1):
                params[i] = arg
            for i in range(10):
                placeholder = f'%{i}'
                if placeholder in content and i in params:
                    content = content.replace(placeholder, params[i])

            raw_lines = content.splitlines()

            # Build label index from raw content
            labels: dict[str, int] = {}
            line_index: list[str | None] = []
            for raw in raw_lines:
                stripped = raw.strip()
                if (
                    not stripped
                    or stripped.startswith('::')
                    or stripped.upper().startswith('REM ')
                ):
                    line_index.append(None)
                else:
                    line_index.append(stripped)
                    label_match = re.match(r'^:([A-Za-z_][A-Za-z0-9_]*)\s*$', stripped)
                    if label_match:
                        labels[label_match.group(1).upper()] = len(line_index) - 1

            pc = 0
            saved_echo = self._echo_on
            self._echo_on = True

            while pc < len(line_index):
                raw_line = line_index[pc]
                pc += 1

                if raw_line is None:
                    continue

                # Expand environment variables at execution time
                expanded = self.expand_variables(raw_line)
                parsed = parse_command(expanded)
                if parsed is None:
                    continue

                try:
                    self._execute_parsed(parsed)
                except _GotoSignal as g:
                    target = g.label.upper()
                    if target in labels:
                        pc = labels[target] + 1
                    else:
                        self._output_line(f'Label not found: {target}')

            self._echo_on = saved_echo
            return self.last_errorlevel
        except _GotoSignal:
            return self.last_errorlevel
        except Exception as e:
            self._output_line(f'Batch error: {e!s}')
            return 1

    # ==================== DOS Commands ====================

    def cmd_dir(self, args: list[str]) -> int:
        path = '.'
        show_all = False
        wide_format = False

        for arg in args:
            upper = arg.upper()
            if upper == '/W':
                wide_format = True
            elif upper == '/A':
                show_all = True
            elif not arg.startswith('/'):
                path = arg

        try:
            entries = self.fs.list_directory(path)
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
        dirs = []
        for arg in args:
            if arg.upper() == '/S':
                recursive = True
            elif arg.upper() == '/Q':
                pass
            elif not arg.startswith('/'):
                dirs.append(arg)
        for dirname in dirs:
            try:
                if recursive:
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
                    import fnmatch

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
            commands = [
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
            ]
            for i in range(0, len(commands), 6):
                row = commands[i : i + 6]
                self._output_line('  '.join(f'{c:<10}' for c in row))
        return 0

    def _get_command_help(self, cmd: str) -> str:
        help_texts = {
            'CALL': (
                'Calls one batch program from another.\n\nCALL batchfile [parameters]'
            ),
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
            'FC': (
                'Compares two files and displays the differences.'
                '\n\nFC [/N] file1 file2'
            ),
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
        return help_texts.get(cmd, f'Help not available for {cmd}')

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
        filenames = []
        for arg in args:
            if arg.upper() == '/N':
                pass
            elif not arg.startswith('/'):
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
        import difflib

        diff = difflib.unified_diff(lines1, lines2, lineterm='', n=0)
        patch_lines = list(diff)[2:]
        in_hunk_1 = False
        in_hunk_2 = False
        for pl in patch_lines:
            if pl.startswith('-'):
                if not in_hunk_1:
                    self._output_line(f'***** {filenames[0]}')
                    in_hunk_1 = True
                    in_hunk_2 = False
                self._output_line(pl[1:])
            elif pl.startswith('+'):
                if not in_hunk_2:
                    self._output_line(f'***** {filenames[1]}')
                    in_hunk_2 = True
                    in_hunk_1 = False
                self._output_line(pl[1:])
        return 1

    def cmd_edit(self, args: list[str]) -> int:
        filename = args[0] if args else ''
        if hasattr(self, '_editor_input_handler') and self._editor_input_handler:
            return self._editor_input_handler(filename)
        self._output_line('EDIT requires an interactive terminal session.')
        self._output_line('Usage: EDIT [filename]')
        return 1

    def set_editor_handler(self, handler) -> None:
        self._editor_input_handler = handler
