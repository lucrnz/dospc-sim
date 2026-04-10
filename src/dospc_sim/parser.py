"""DOS command parser using Lark with AST node classes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from lark import Lark, Transformer, v_args, Token, Tree


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

_DOS_GRAMMAR = r"""
start: command_line*

command_line: command_chain

command_chain: command (PIPE command)*

command: simple_command

simple_command: command_name argument*
              | command_name

command_name: WORD

argument: switch
        | WORD

switch: "/" SWITCH_CHARS

PIPE: "|"

SWITCH_CHARS: /[A-Za-z0-9]+/

WORD: /[^ \t\r\n|<>\/"']+/
     | /"[^"]*"/
     | /'[^']*'/

%import common.WS
%ignore WS+
"""


# ---------------------------------------------------------------------------
# AST node definitions
# ---------------------------------------------------------------------------

@dataclass
class Argument:
    value: str


@dataclass
class Switch:
    name: str

    @property
    def value(self) -> str:
        return f"/{self.name}"


@dataclass
class CommandName:
    name: str


@dataclass
class SimpleCommand:
    name: CommandName
    args: List[Argument | Switch] = field(default_factory=list)

    @property
    def command(self) -> str:
        return self.name.name

    @property
    def arguments(self) -> List[str]:
        return [a.value for a in self.args]

    @property
    def switches(self) -> List[Switch]:
        return [a for a in self.args if isinstance(a, Switch)]

    @property
    def positional_args(self) -> List[str]:
        return [a.value for a in self.args if isinstance(a, Argument)]


@dataclass
class PipeCommand:
    commands: List[SimpleCommand]


@dataclass
class EchoCommand:
    text: Optional[str] = None
    on: bool = True


@dataclass
class CommandLine:
    command: SimpleCommand | PipeCommand | EchoCommand
    stdin_redirect: Optional[str] = None
    stdout_redirect: Optional[str] = None
    append_redirect: Optional[str] = None


@dataclass
class BatchProgram:
    lines: List[CommandLine]

    @property
    def commands(self) -> List[CommandLine]:
        return self.lines


# ---------------------------------------------------------------------------
# Transformer
# ---------------------------------------------------------------------------

class _DOSTransformer(Transformer):
    @v_args(inline=True)
    def start(self, *lines):
        return BatchProgram(lines=list(lines))

    @v_args(inline=True)
    def command_line(self, chain):
        return chain

    @v_args(inline=True)
    def command_chain(self, *parts):
        commands = [p for p in parts if isinstance(p, (SimpleCommand, PipeCommand))]
        if len(commands) > 1:
            return PipeCommand(commands=commands)
        return commands[0] if commands else parts[0]

    @v_args(inline=True)
    def command(self, simple):
        return simple

    @v_args(inline=True)
    def simple_command(self, *parts):
        name = None
        args: List[Argument | Switch] = []
        for p in parts:
            if isinstance(p, CommandName):
                name = p
            else:
                args.append(p)
        return SimpleCommand(name=name, args=args)

    @v_args(inline=True)
    def command_name(self, word):
        return CommandName(name=str(word).upper())

    @v_args(inline=True)
    def argument(self, val):
        if isinstance(val, (Switch, Argument)):
            return val
        val_str = str(val)
        if val_str.startswith('"') and val_str.endswith('"'):
            val_str = val_str[1:-1]
        elif val_str.startswith("'") and val_str.endswith("'"):
            val_str = val_str[1:-1]
        return Argument(value=val_str)

    @v_args(inline=True)
    def switch(self, chars):
        return Switch(name=str(chars).upper())

    def PIPE(self, token):
        return token


# ---------------------------------------------------------------------------
# Echo handling (pre-parser)
# ---------------------------------------------------------------------------

_ECHO_RE = re.compile(r'^ECHO\s*(.*)', re.IGNORECASE)


def _parse_echo(line: str) -> Optional[EchoCommand]:
    m = _ECHO_RE.match(line)
    if not m:
        return None
    rest = m.group(1).strip()
    if not rest:
        return EchoCommand(text=None, on=True)
    if rest.upper() == "ON":
        return EchoCommand(text=None, on=True)
    if rest.upper() == "OFF":
        return EchoCommand(text=None, on=False)
    if rest.startswith('"') and rest.endswith('"'):
        rest = rest[1:-1]
    elif rest.startswith("'") and rest.endswith("'"):
        rest = rest[1:-1]
    return EchoCommand(text=rest)


# ---------------------------------------------------------------------------
# Parser public API
# ---------------------------------------------------------------------------

_parser = Lark(
    _DOS_GRAMMAR,
    parser="earley",
    ambiguity="resolve",
    maybe_placeholders=False,
)

_transformer = _DOSTransformer()


def parse_command(line: str) -> Optional[CommandLine]:
    if not line or not line.strip():
        return None

    line = line.strip()

    if line.startswith("::") or line.upper().startswith("REM "):
        return None

    # Handle ECHO specially since it takes the rest of the line as text
    upper_stripped = line.upper().split()[0] if line.split() else ""
    if upper_stripped == "ECHO":
        echo = _parse_echo(line)
        if echo is not None:
            return CommandLine(command=echo)

    try:
        tree = _parser.parse(line + "\n")
        result = _transformer.transform(tree)
        if isinstance(result, BatchProgram) and result.lines:
            cmd = result.lines[0]
            if isinstance(cmd, CommandLine):
                return cmd
            return CommandLine(command=cmd)
        return None
    except Exception:
        return None


def parse_batch(content: str) -> BatchProgram:
    lines = content.splitlines()
    commands: List[CommandLine] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("::") or line.upper().startswith("REM "):
            continue
        cmd = parse_command(line)
        if cmd is not None:
            commands.append(cmd)
    return BatchProgram(lines=commands)
