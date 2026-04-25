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
from dospc_sim.shell_commands import DOSShellCommandProvider, get_shell_command_names

_ENV_VAR_RE = re.compile(r'%([^%]+)%')


class _GotoSignal(Exception):
    """Signal raised by GOTO to jump to a label in batch execution."""

    def __init__(self, label: str):
        self.label = label


class _RedirectionExecutor:
    """Handle command execution with DOS-style redirection semantics."""

    def __init__(self, shell: 'DOSShell'):
        self.shell = shell

    def execute(self, parsed: CommandLine) -> int:
        ast = parsed.command
        if isinstance(ast, Label):
            return 0

        redirecting = parsed.stdout_redirect or parsed.append_redirect
        captured: list[str] = []
        original_callback = self.shell.output_callback
        if redirecting:
            self.shell.output_callback = lambda text, buf=captured: buf.append(text)

        if parsed.stdin_redirect:
            try:
                self.shell._piped_input = self.shell.fs.read_file(parsed.stdin_redirect)
            except (FileNotFoundError, IsADirectoryError):
                self.shell._output_line('The system cannot find the file specified.')
                if redirecting:
                    self.shell.output_callback = original_callback
                self.shell.last_errorlevel = 1
                self.shell._piped_input = None
                return 1

        self.shell.last_errorlevel = self.shell._execute_ast(ast)

        if redirecting:
            self.shell.output_callback = original_callback
            output_text = '\n'.join(captured)
            if parsed.append_redirect:
                try:
                    existing = self.shell.fs.read_file(parsed.append_redirect)
                    output_text = existing + '\n' + output_text
                except (FileNotFoundError, IsADirectoryError):
                    pass
                self.shell.fs.write_file(parsed.append_redirect, output_text)
            elif parsed.stdout_redirect:
                self.shell.fs.write_file(parsed.stdout_redirect, output_text)

        self.shell._piped_input = None
        return self.shell.last_errorlevel


class _BatchExecutor:
    """Execute batch scripts using parsed AST commands and goto labels."""

    def __init__(self, shell: 'DOSShell'):
        self.shell = shell

    def execute(self, content: str, batch_name: str, args: list[str] | None) -> int:
        try:
            params = {0: batch_name}
            for i, arg in enumerate((args or [])[:9], 1):
                params[i] = arg
            for i in range(10):
                placeholder = f'%{i}'
                if placeholder in content and i in params:
                    content = content.replace(placeholder, params[i])

            raw_lines = content.splitlines()
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
            while pc < len(line_index):
                raw_line = line_index[pc]
                pc += 1

                if raw_line is None:
                    continue

                expanded = self.shell.expand_variables(raw_line)
                parsed = parse_command(expanded)
                if parsed is None:
                    continue

                if self.shell._echo_on and not isinstance(parsed.command, Label):
                    self.shell._output_line(f'{self.shell.get_prompt()}{expanded}')

                try:
                    self.shell._execute_parsed(parsed)
                except _GotoSignal as g:
                    target = g.label.upper()
                    if target in labels:
                        pc = labels[target] + 1
                    else:
                        self.shell._output_line(f'Label not found: {target}')

            return self.shell.last_errorlevel
        except _GotoSignal:
            return self.shell.last_errorlevel
        except Exception as e:
            self.shell._output_line(f'Batch error: {e!s}')
            return 1


class DOSShell(DOSShellCommandProvider):
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
        self._redirection_executor = _RedirectionExecutor(self)
        self._batch_executor = _BatchExecutor(self)
        self._batch_file_cache: dict[tuple[str, str, str], str | None] = {}
        self._batch_cache_path: str = self.environment['PATH']
        self._batch_cache_cwd: str = ''
        self._cmd_dispatch: dict[str, Callable[[list[str]], int]] = {}
        for attr in dir(self):
            if attr.startswith('cmd_'):
                self._cmd_dispatch[attr[4:].upper()] = getattr(self, attr)

    def _output(self, text: str = '') -> None:
        self.output_callback(text)

    def _output_line(self, text: str = '') -> None:
        self._output(text)

    def _env_var_replace(self, match: re.Match) -> str:
        var_name = match.group(1).upper()
        env = self.environment
        if var_name in env:
            return env[var_name]
        return match.group(0)

    def expand_variables(self, text: str) -> str:
        """Expand %VAR% environment variable references in text."""
        if '%' not in text:
            return text
        return _ENV_VAR_RE.sub(self._env_var_replace, text)

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
        prompt_str = prompt_str.replace('$N', self.fs.drive_letter).replace(
            '$n', self.fs.drive_letter
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
        return self._redirection_executor.execute(parsed)

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
            handler = self._cmd_dispatch.get(command)
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
        pattern = re.compile(rf'%%{re.escape(for_cmd.var)}', re.IGNORECASE)
        for item in for_cmd.items:
            substituted = pattern.sub(item, raw_body)
            expanded = self.expand_variables(substituted)
            parsed = parse_command(expanded)
            if parsed is not None:
                result = self._execute_parsed(parsed)
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
        cur_path = self.environment['PATH']
        cur_cwd = self.fs.get_current_path()
        if cur_path != self._batch_cache_path or cur_cwd != self._batch_cache_cwd:
            self._batch_file_cache.clear()
            self._batch_cache_path = cur_path
            self._batch_cache_cwd = cur_cwd

        upper = name.upper()
        cache_key = (upper, cur_cwd, cur_path)
        if cache_key in self._batch_file_cache:
            return self._batch_file_cache[cache_key]

        result = self._find_batch_file_uncached(name, upper, cur_path)
        self._batch_file_cache[cache_key] = result
        return result

    def _find_batch_file_uncached(
        self, name: str, upper: str, path_env: str
    ) -> str | None:
        path_dirs = [d.strip() for d in path_env.split(';') if d.strip()]
        if upper.endswith('.BAT') or upper.endswith('.CMD'):
            if self.fs.file_exists(name):
                return name
            for path_dir in path_dirs:
                test_path = f'{path_dir}\\{name}'
                if self.fs.file_exists(test_path):
                    return test_path
            return None
        for ext in ('.BAT', '.CMD'):
            test_path = f'{name}{ext}'
            if self.fs.file_exists(test_path):
                return test_path
            for path_dir in path_dirs:
                test_path = f'{path_dir}\\{name}{ext}'
                if self.fs.file_exists(test_path):
                    return test_path
        return None

    def _execute_batch(self, batch_file: str, args: list[str]) -> int:
        """Execute a batch file via the Lark AST."""
        try:
            content = self.fs.read_file(batch_file)
        except Exception as e:
            self._output_line(f'Batch error: {e!s}')
            return 1
        return self._execute_batch_content(content, batch_file, args)

    def execute_batch_content(
        self, content: str, batch_name: str = 'STDIN', args: list[str] | None = None
    ) -> int:
        """Execute batch source text using parser + AST semantics."""
        return self._execute_batch_content(content, batch_name, args)

    def _execute_batch_content(
        self, content: str, batch_name: str, args: list[str] | None
    ) -> int:
        """Execute batch content with optional positional arguments."""
        return self._batch_executor.execute(content, batch_name, args)

    @staticmethod
    def get_available_commands() -> tuple[str, ...]:
        """Return available shell commands."""
        return get_shell_command_names()

    def set_editor_handler(self, handler) -> None:
        self._editor_input_handler = handler
