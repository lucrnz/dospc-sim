"""Tests for the DOS command parser (Lark-based AST)."""

from dospc_sim.parser import (
    Argument,
    BatchProgram,
    CallCommand,
    ChainCommand,
    CommandLine,
    CommandName,
    EchoCommand,
    ForCommand,
    GotoCommand,
    IfCommand,
    IfCompareCondition,
    IfDefinedCondition,
    IfErrorlevelCondition,
    IfExistCondition,
    Label,
    PauseCommand,
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

    def test_pipe_with_echo(self):
        """ECHO must be allowed as a pipeable command (bug 4)."""
        r = parse_command('ECHO hello | FIND hello')
        assert r is not None
        assert isinstance(r.command, PipeCommand)
        assert isinstance(r.command.commands[0], EchoCommand)
        assert r.command.commands[0].text == 'hello'
        assert isinstance(r.command.commands[1], SimpleCommand)
        assert r.command.commands[1].command == 'FIND'


class TestBatchControlParsing:
    def test_goto_command(self):
        r = parse_command('GOTO target')
        assert r is not None
        assert isinstance(r.command, GotoCommand)
        assert r.command.label == 'TARGET'

    def test_call_command(self):
        r = parse_command('CALL greet world')
        assert r is not None
        assert isinstance(r.command, CallCommand)
        assert r.command.target.command == 'GREET'
        assert r.command.target.positional_args == ['world']

    def test_pause_command(self):
        r = parse_command('PAUSE')
        assert r is not None
        assert isinstance(r.command, PauseCommand)

    def test_if_exist_command(self):
        r = parse_command('IF EXIST test.txt ECHO found')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert isinstance(r.command.condition, IfExistCondition)
        assert r.command.condition.filename == 'test.txt'
        assert isinstance(r.command.command.command, EchoCommand)
        assert r.command.command.command.text == 'found'

    def test_if_not_errorlevel_command(self):
        r = parse_command('IF NOT ERRORLEVEL 2 GOTO done')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert r.command.negated is True
        assert isinstance(r.command.condition, IfErrorlevelCondition)
        assert r.command.condition.level == 2
        assert isinstance(r.command.command.command, GotoCommand)
        assert r.command.command.command.label == 'DONE'

    def test_if_compare_command(self):
        r = parse_command('IF foo==bar ECHO nope')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert isinstance(r.command.condition, IfCompareCondition)
        assert r.command.condition.left == 'foo'
        assert r.command.condition.right == 'bar'

    def test_for_command(self):
        r = parse_command('FOR %%F IN (a b c) DO TYPE %%F')
        assert r is not None
        assert isinstance(r.command, ForCommand)
        assert r.command.var == 'F'
        assert r.command.items == ['a', 'b', 'c']
        assert isinstance(r.command.command.command, SimpleCommand)
        assert r.command.command.command.command == 'TYPE'
        assert r.command.command.command.positional_args == ['%%F']

    def test_label_command(self):
        r = parse_command(':loop_here')
        assert r is not None
        assert isinstance(r.command, Label)
        assert r.command.name == 'LOOP_HERE'

    def test_if_defined_command(self):
        r = parse_command('IF DEFINED PATH ECHO yes')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert isinstance(r.command.condition, IfDefinedCondition)
        assert r.command.condition.variable == 'PATH'
        assert isinstance(r.command.command.command, EchoCommand)
        assert r.command.command.command.text == 'yes'

    def test_if_not_defined_command(self):
        r = parse_command('IF NOT DEFINED MISSING ECHO no')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert r.command.negated is True
        assert isinstance(r.command.condition, IfDefinedCondition)
        assert r.command.condition.variable == 'MISSING'

    def test_if_defined_case_insensitive(self):
        r = parse_command('if defined myvar echo found')
        assert r is not None
        assert isinstance(r.command.condition, IfDefinedCondition)
        assert r.command.condition.variable == 'MYVAR'

    def test_if_else_command(self):
        r = parse_command('IF EXIST test.txt ECHO yes ELSE ECHO no')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert isinstance(r.command.condition, IfExistCondition)
        assert r.command.command.command.text == 'yes'
        assert r.command.else_command is not None
        assert isinstance(r.command.else_command.command, EchoCommand)
        assert r.command.else_command.command.text == 'no'

    def test_if_else_no_else(self):
        r = parse_command('IF EXIST test.txt ECHO yes')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert r.command.else_command is None

    def test_if_not_else_command(self):
        r = parse_command('IF NOT EXIST test.txt ECHO missing ELSE ECHO found')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert r.command.negated is True
        assert r.command.command.command.text == 'missing'
        assert r.command.else_command is not None
        assert r.command.else_command.command.text == 'found'

    def test_if_compare_else(self):
        r = parse_command('IF a==b ECHO match ELSE ECHO nomatch')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert isinstance(r.command.condition, IfCompareCondition)
        assert r.command.command.command.text == 'match'
        assert r.command.else_command.command.text == 'nomatch'

    def test_if_errorlevel_else(self):
        r = parse_command('IF ERRORLEVEL 1 ECHO fail ELSE ECHO ok')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert r.command.command.command.text == 'fail'
        assert r.command.else_command.command.text == 'ok'

    def test_if_defined_else(self):
        r = parse_command('IF DEFINED VAR ECHO yes ELSE ECHO no')
        assert r is not None
        assert isinstance(r.command, IfCommand)
        assert isinstance(r.command.condition, IfDefinedCondition)
        assert r.command.command.command.text == 'yes'
        assert r.command.else_command.command.text == 'no'

    def test_if_else_with_goto(self):
        r = parse_command('IF 1==1 GOTO WIN ELSE GOTO LOSE')
        assert r is not None
        assert isinstance(r.command.command.command, GotoCommand)
        assert r.command.command.command.label == 'WIN'
        assert isinstance(r.command.else_command.command, GotoCommand)
        assert r.command.else_command.command.label == 'LOSE'

    def test_comment_with_bare_rem(self):
        assert parse_command('REM') is None


class TestChainParsing:
    def test_and_then_two_commands(self):
        r = parse_command('ECHO hello && ECHO world')
        assert r is not None
        assert isinstance(r.command, ChainCommand)
        assert r.command.operator == '&&'
        assert isinstance(r.command.left.command, EchoCommand)
        assert r.command.left.command.text == 'hello'
        assert isinstance(r.command.right.command, EchoCommand)
        assert r.command.right.command.text == 'world'

    def test_or_else_two_commands(self):
        r = parse_command('DIR missing || ECHO fallback')
        assert r is not None
        assert isinstance(r.command, ChainCommand)
        assert r.command.operator == '||'
        assert isinstance(r.command.left.command, SimpleCommand)
        assert r.command.left.command.command == 'DIR'
        assert isinstance(r.command.right.command, EchoCommand)
        assert r.command.right.command.text == 'fallback'

    def test_triple_chain(self):
        r = parse_command('ECHO a && ECHO b && ECHO c')
        assert r is not None
        assert isinstance(r.command, ChainCommand)
        # Left-associative: ((a && b) && c)
        assert r.command.operator == '&&'
        left = r.command.left.command
        assert isinstance(left, ChainCommand)
        assert left.operator == '&&'
        assert isinstance(left.left.command, EchoCommand)
        assert left.left.command.text == 'a'
        assert isinstance(left.right.command, EchoCommand)
        assert left.right.command.text == 'b'
        assert isinstance(r.command.right.command, EchoCommand)
        assert r.command.right.command.text == 'c'

    def test_mixed_and_or_chain(self):
        r = parse_command('ECHO a && ECHO b || ECHO c')
        assert r is not None
        assert isinstance(r.command, ChainCommand)
        assert r.command.operator == '||'
        left = r.command.left.command
        assert isinstance(left, ChainCommand)
        assert left.operator == '&&'

    def test_chain_with_pipe(self):
        r = parse_command('DIR | SORT && ECHO done')
        assert r is not None
        assert isinstance(r.command, ChainCommand)
        assert r.command.operator == '&&'
        assert isinstance(r.command.left.command, PipeCommand)
        assert isinstance(r.command.right.command, EchoCommand)

    def test_chain_with_simple_args(self):
        r = parse_command('COPY a.txt b.txt && ECHO copied')
        assert r is not None
        assert isinstance(r.command, ChainCommand)
        assert r.command.left.command.command == 'COPY'
        assert r.command.left.command.positional_args == ['a.txt', 'b.txt']
        assert r.command.right.command.text == 'copied'

    def test_no_chain_returns_normal(self):
        r = parse_command('ECHO hello')
        assert r is not None
        assert isinstance(r.command, EchoCommand)

    def test_chain_preserves_quotes(self):
        r = parse_command('ECHO "hello world" && ECHO "goodbye"')
        assert r is not None
        assert isinstance(r.command, ChainCommand)
        assert r.command.left.command.text == 'hello world'
        assert r.command.right.command.text == 'goodbye'


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
