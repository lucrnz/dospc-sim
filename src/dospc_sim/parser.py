"""DOS command parser using Lark with AST node classes."""

from __future__ import annotations

import re

from lark import Lark, Token, Transformer, v_args

from dospc_sim.parser_ast import (
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
)

# ---------------------------------------------------------------------------
# Grammar - handles regular commands, pipes, and redirections
# ---------------------------------------------------------------------------

_DOS_GRAMMAR = r"""
start: command_line

command_line: command redirect*

?command: comment
        | if_command
        | for_command
        | echo_command
        | goto_command
        | call_command
        | pause_command
        | label
        | command_chain
        | simple_command

command_chain: pipeable_command ("|" pipeable_command)+

pipeable_command: simple_command
               | echo_command

simple_command: command_name argument*

echo_command: "ECHO"i echo_argument*
goto_command: "GOTO"i WORD
call_command: "CALL"i simple_command
pause_command: "PAUSE"i
if_command: "IF"i not_modifier? if_condition command_line
for_command: "FOR"i FOR_VAR "IN"i "(" for_items ")" "DO"i command_line
label: LABEL_TOKEN
comment: COMMENT

if_condition: "EXIST"i WORD        -> if_exist_condition
            | "ERRORLEVEL"i NUMBER -> if_errorlevel_condition
            | "DEFINED"i WORD      -> if_defined_condition
            | COMPARE_EXPR          -> if_compare_condition

for_items: WORD+

redirect: ">" WORD                  -> write_redirect
        | ">>" WORD                 -> append_redirect
        | "<" WORD                  -> stdin_redirect

echo_argument: switch
             | WORD

argument: switch
        | WORD

not_modifier: "NOT"i

switch: "/" SWITCH_CHARS

command_name: WORD

FOR_VAR.2: /%%[A-Za-z]/
LABEL_TOKEN.3: /:[A-Za-z_][A-Za-z0-9_]*/
COMMENT.3: /::[^\r\n]*/ | /(?i:REM)(?=$|\s).*/
SWITCH_CHARS: /[A-Za-z0-9]+/
NUMBER: /\d+/
COMPARE_EXPR: /[^\s|<>]+(?:\s*==\s*[^\s|<>]+)+/

WORD: /[^ \t\r\n|<>\/()"']+/ | /"[^"]*"/ | /'[^']*'/

%import common.WS_INLINE
%ignore WS_INLINE
"""


# ---------------------------------------------------------------------------
# Transformer (Lark grammar only)
# ---------------------------------------------------------------------------


def _strip_quotes(val_str: str) -> str:
    if val_str.startswith('"') and val_str.endswith('"'):
        return val_str[1:-1]
    if val_str.startswith("'") and val_str.endswith("'"):
        return val_str[1:-1]
    return val_str


def _argument_value(value: Argument | Switch | str) -> str:
    if isinstance(value, (Argument, Switch)):
        return value.value
    return value


def _split_compare_expr(expr: str) -> tuple[str, str]:
    left, right = expr.split('==', 1)
    return _strip_quotes(left.strip()), _strip_quotes(right.strip())


class _DOSTransformer(Transformer):
    @v_args(inline=True)
    def start(self, line):
        if line is None:
            return BatchProgram(lines=[])
        return BatchProgram(lines=[line])

    def command_line(self, children):
        if not children:
            return None

        command = children[0]
        if command is None:
            return None

        parsed = (
            command
            if isinstance(command, CommandLine)
            else CommandLine(command=command)
        )
        for redirect in children[1:]:
            if redirect['type'] == 'stdin':
                parsed.stdin_redirect = redirect['target']
            elif redirect['type'] == 'stdout':
                parsed.stdout_redirect = redirect['target']
            elif redirect['type'] == 'append':
                parsed.append_redirect = redirect['target']
        return parsed

    def comment(self, _children):
        return None

    def command_chain(self, children):
        commands = [child for child in children if not isinstance(child, Token)]
        return PipeCommand(commands=commands)

    @v_args(inline=True)
    def pipeable_command(self, cmd):
        return cmd

    def simple_command(self, children):
        return SimpleCommand(name=children[0], args=children[1:])

    @v_args(inline=True)
    def command_name(self, word):
        return CommandName(name=str(word).upper())

    @v_args(inline=True)
    def echo_command(self, *parts):
        values = [_argument_value(part) for part in parts]
        if not values:
            return EchoCommand(text=None, on=None)
        if len(values) == 1 and values[0].upper() == 'ON':
            return EchoCommand(text=None, on=True)
        if len(values) == 1 and values[0].upper() == 'OFF':
            return EchoCommand(text=None, on=False)
        return EchoCommand(text=' '.join(values))

    @v_args(inline=True)
    def goto_command(self, label):
        return GotoCommand(label=str(label).upper())

    @v_args(inline=True)
    def call_command(self, target):
        return CallCommand(target=target)

    def pause_command(self, _children):
        return PauseCommand()

    @v_args(inline=True)
    def if_command(self, *parts):
        if len(parts) == 3:
            negated = True
            condition, command = parts[1], parts[2]
        else:
            negated = False
            condition, command = parts
        return IfCommand(negated=negated, condition=condition, command=command)

    @v_args(inline=True)
    def for_command(self, var, items, command):
        return ForCommand(var=str(var)[2:].upper(), items=items, command=command)

    @v_args(inline=True)
    def label(self, token):
        return Label(name=str(token)[1:].upper())

    def for_items(self, children):
        return [str(item) for item in children]

    @v_args(inline=True)
    def argument(self, val):
        if isinstance(val, Switch):
            return val
        return Argument(value=str(val))

    @v_args(inline=True)
    def echo_argument(self, val):
        if isinstance(val, Switch):
            return val
        return str(val)

    def not_modifier(self, _children):
        return True

    @v_args(inline=True)
    def switch(self, chars):
        return Switch(name=str(chars).upper())

    @v_args(inline=True)
    def if_exist_condition(self, filename):
        return IfExistCondition(filename=str(filename))

    @v_args(inline=True)
    def if_errorlevel_condition(self, level):
        return IfErrorlevelCondition(level=int(level))

    @v_args(inline=True)
    def if_defined_condition(self, varname):
        return IfDefinedCondition(variable=str(varname).upper())

    @v_args(inline=True)
    def if_compare_condition(self, expr):
        left, right = _split_compare_expr(str(expr))
        return IfCompareCondition(left=left, right=right)

    @v_args(inline=True)
    def write_redirect(self, target):
        return {'type': 'stdout', 'target': str(target)}

    @v_args(inline=True)
    def append_redirect(self, target):
        return {'type': 'append', 'target': str(target)}

    @v_args(inline=True)
    def stdin_redirect(self, target):
        return {'type': 'stdin', 'target': str(target)}

    def WORD(self, token):
        return _strip_quotes(str(token))

    def NUMBER(self, token):
        return int(str(token))


# ---------------------------------------------------------------------------
# Lark parser instance
# ---------------------------------------------------------------------------

_parser = Lark(
    _DOS_GRAMMAR,
    parser='lalr',
    maybe_placeholders=False,
    transformer=_DOSTransformer(),
)


def _parse_via_lark(line: str) -> CommandLine | None:
    """Parse using the Lark grammar."""
    result = _parser.parse(line)
    if isinstance(result, BatchProgram) and result.lines:
        cl = result.lines[0]
        if isinstance(cl, CommandLine):
            return cl
    return None


# ---------------------------------------------------------------------------
# Parser public API
# ---------------------------------------------------------------------------


_CHAIN_RE = re.compile(r'&&|\|\|')
_ELSE_RE = re.compile(r'\bELSE\b', re.IGNORECASE)


def _split_if_else(line: str) -> tuple[str, str | None]:
    """Split an IF...ELSE line into the IF part and the ELSE command.

    Only splits when the line starts with IF (possibly preceded by NOT).
    Finds the ELSE keyword that separates the then-command from the
    else-command.
    """
    upper = line.lstrip().upper()
    if not upper.startswith('IF '):
        return line, None

    for m in _ELSE_RE.finditer(line):
        pos = m.start()
        if_part = line[:pos].rstrip()
        else_part = line[pos + 4 :].lstrip()
        # Validate: the IF part must parse as a valid IfCommand
        try:
            result = _parse_via_lark(if_part)
        except Exception:
            continue
        if result is not None and isinstance(result.command, IfCommand):
            return if_part, else_part if else_part else None
    return line, None


def _split_chain(line: str) -> list[tuple[str, str]]:
    """Split a line on && and || operators, respecting quoted strings.

    Returns a list of (segment, operator) tuples.  The last segment has
    an empty-string operator.
    """
    segments: list[tuple[str, str]] = []
    in_single = False
    in_double = False
    i = 0
    start = 0
    while i < len(line):
        ch = line[i]
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif not in_single and not in_double:
            if line[i : i + 2] == '&&':
                segments.append((line[start:i].rstrip(), '&&'))
                i += 2
                start = i
                while i < len(line) and line[i] in ' \t':
                    i += 1
                start = i
                continue
            if line[i : i + 2] == '||':
                segments.append((line[start:i].rstrip(), '||'))
                i += 2
                start = i
                while i < len(line) and line[i] in ' \t':
                    i += 1
                start = i
                continue
        i += 1
    segments.append((line[start:].rstrip(), ''))
    return segments


def _parse_single(line: str) -> CommandLine | None:
    """Parse a single command (no chain operators), handling IF...ELSE."""
    if_part, else_part = _split_if_else(line)

    result = _parse_via_lark(if_part)
    if result is None:
        return None

    if else_part and isinstance(result.command, IfCommand):
        else_parsed = _parse_single(else_part)
        if else_parsed is not None:
            result.command.else_command = else_parsed

    return result


def parse_command(line: str) -> CommandLine | None:
    if not line or not line.strip():
        return None

    try:
        stripped = line.strip()
        segments = _split_chain(stripped)

        if len(segments) == 1:
            return _parse_single(segments[0][0])

        # Build a left-associative chain tree
        left = _parse_single(segments[0][0])
        if left is None:
            return None

        for i in range(1, len(segments)):
            op = segments[i - 1][1]
            right = _parse_single(segments[i][0])
            if right is None:
                return None
            chain = ChainCommand(left=left, operator=op, right=right)
            left = CommandLine(command=chain)

        return left
    except Exception:
        return None


def parse_batch(content: str) -> BatchProgram:
    commands: list[CommandLine] = []
    for line in content.splitlines():
        cmd = parse_command(line)
        if cmd is not None:
            commands.append(cmd)
    return BatchProgram(lines=commands)
