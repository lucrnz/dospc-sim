"""Tests for the DOS command parser (Lark-based AST)."""

from dospc_sim.parser import (
    Argument,
    BatchProgram,
    CommandLine,
    CommandName,
    EchoCommand,
    PipeCommand,
    SimpleCommand,
    Switch,
    parse_batch,
    parse_command,
)


class TestParseSimpleCommand:
    def test_basic_command(self):
        r = parse_command('DIR')
        assert r is not None
        assert isinstance(r, CommandLine)
        assert isinstance(r.command, SimpleCommand)
        assert r.command.command == 'DIR'
        assert r.command.arguments == []

    def test_command_with_args(self):
        r = parse_command('COPY source.txt dest.txt')
        assert r is not None
        cmd = r.command
        assert cmd.command == 'COPY'
        assert cmd.arguments == ['source.txt', 'dest.txt']

    def test_command_with_switch(self):
        r = parse_command('DIR /W')
        assert r is not None
        cmd = r.command
        assert cmd.command == 'DIR'
        assert cmd.arguments == ['/W']
        assert len(cmd.switches) == 1
        assert cmd.switches[0].name == 'W'
        assert cmd.positional_args == []

    def test_command_with_multiple_switches(self):
        r = parse_command('DIR /W /A')
        assert r is not None
        cmd = r.command
        assert cmd.arguments == ['/W', '/A']
        assert len(cmd.switches) == 2

    def test_command_mixed_args_and_switches(self):
        r = parse_command('RD /S /Q dirname')
        assert r is not None
        cmd = r.command
        assert cmd.arguments == ['/S', '/Q', 'dirname']
        assert cmd.positional_args == ['dirname']
        assert len(cmd.switches) == 2

    def test_case_insensitive_command(self):
        r = parse_command('dir /w')
        assert r is not None
        assert r.command.command == 'DIR'

    def test_set_command(self):
        r = parse_command('SET VAR=value')
        assert r is not None
        assert r.command.command == 'SET'
        assert r.command.arguments == ['VAR=value']

    def test_cd_command(self):
        r = parse_command('CD subdir')
        assert r is not None
        assert r.command.command == 'CD'
        assert r.command.arguments == ['subdir']

    def test_empty_command(self):
        assert parse_command('') is None

    def test_whitespace_only(self):
        assert parse_command('   ') is None

    def test_none_like(self):
        assert parse_command('  \t ') is None

    def test_comment_double_colon(self):
        assert parse_command(':: this is a comment') is None

    def test_rem_comment(self):
        assert parse_command('REM this is a remark') is None

    def test_fc_command(self):
        r = parse_command('FC /N file1.txt file2.txt')
        assert r is not None
        cmd = r.command
        assert cmd.command == 'FC'
        assert cmd.positional_args == ['file1.txt', 'file2.txt']

    def test_find_command_with_string(self):
        r = parse_command('FIND /I "hello" test.txt')
        assert r is not None
        cmd = r.command
        assert cmd.command == 'FIND'
        assert 'hello' in cmd.positional_args
        assert 'test.txt' in cmd.positional_args

    def test_sort_command(self):
        r = parse_command('SORT /R input.txt /O output.txt')
        assert r is not None
        cmd = r.command
        assert cmd.command == 'SORT'
        assert '/R' in cmd.arguments
        assert '/O' in cmd.arguments

    def test_no_args_command(self):
        r = parse_command('CLS')
        assert r is not None
        assert r.command.command == 'CLS'
        assert r.command.arguments == []


class TestEchoParsing:
    def test_echo_with_text(self):
        r = parse_command('ECHO Hello World')
        assert r is not None
        assert isinstance(r.command, EchoCommand)
        assert r.command.text == 'Hello World'

    def test_echo_empty(self):
        r = parse_command('ECHO')
        assert r is not None
        assert isinstance(r.command, EchoCommand)
        assert r.command.text is None
        assert r.command.on is None

    def test_echo_on(self):
        r = parse_command('ECHO ON')
        assert r is not None
        assert isinstance(r.command, EchoCommand)
        assert r.command.on is True

    def test_echo_off(self):
        r = parse_command('ECHO OFF')
        assert r is not None
        assert isinstance(r.command, EchoCommand)
        assert r.command.on is False

    def test_echo_quoted(self):
        r = parse_command('ECHO "Hello World"')
        assert r is not None
        assert isinstance(r.command, EchoCommand)
        assert r.command.text == 'Hello World'

    def test_echo_case_insensitive(self):
        r = parse_command('echo hello')
        assert r is not None
        assert isinstance(r.command, EchoCommand)
        assert r.command.text == 'hello'


class TestPipeParsing:
    def test_pipe_two_commands(self):
        r = parse_command('DIR | SORT')
        assert r is not None
        assert isinstance(r.command, PipeCommand)
        assert len(r.command.commands) == 2
        assert r.command.commands[0].command == 'DIR'
        assert r.command.commands[1].command == 'SORT'

    def test_pipe_with_args(self):
        r = parse_command('TYPE file.txt | FIND /I hello')
        assert r is not None
        assert isinstance(r.command, PipeCommand)
        assert r.command.commands[0].command == 'TYPE'
        assert r.command.commands[1].command == 'FIND'


class TestBatchParsing:
    def test_simple_batch(self):
        content = 'ECHO Line 1\nDIR\nCOPY a.txt b.txt'
        prog = parse_batch(content)
        assert isinstance(prog, BatchProgram)
        assert len(prog.commands) == 3

    def test_batch_skips_comments(self):
        content = ':: comment\nECHO Hello\nREM remark\nDIR'
        prog = parse_batch(content)
        assert len(prog.commands) == 2

    def test_batch_skips_blank_lines(self):
        content = 'ECHO Hello\n\n\nDIR'
        prog = parse_batch(content)
        assert len(prog.commands) == 2

    def test_empty_batch(self):
        prog = parse_batch('')
        assert len(prog.commands) == 0

    def test_comment_only_batch(self):
        prog = parse_batch(':: only comments\nREM nothing else')
        assert len(prog.commands) == 0

    def test_batch_commands_property(self):
        content = 'DIR\nCLS'
        prog = parse_batch(content)
        assert len(prog.commands) == 2
        assert prog.commands == prog.lines


class TestASTNodeProperties:
    def test_switch_value(self):
        s = Switch(name='W')
        assert s.value == '/W'

    def test_simple_command_properties(self):
        cmd = SimpleCommand(
            name=CommandName(name='DIR'),
            args=[Switch(name='W'), Argument(value='path'), Switch(name='A')],
        )
        assert cmd.command == 'DIR'
        assert cmd.arguments == ['/W', 'path', '/A']
        assert cmd.positional_args == ['path']
        assert len(cmd.switches) == 2
        assert cmd.switches[0].name == 'W'
        assert cmd.switches[1].name == 'A'

    def test_command_line_defaults(self):
        cl = CommandLine(command=SimpleCommand(name=CommandName(name='CLS'), args=[]))
        assert cl.stdin_redirect is None
        assert cl.stdout_redirect is None
        assert cl.append_redirect is None
