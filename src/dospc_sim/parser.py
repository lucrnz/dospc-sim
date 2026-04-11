"""DOS command parser using Lark with AST node classes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Union

from lark import Lark, Transformer, v_args


# ---------------------------------------------------------------------------
# Grammar - handles regular commands, pipes, and redirections
# ---------------------------------------------------------------------------

_DOS_GRAMMAR = r"""
start: command_line*

command_line: command_chain redirect*
            | command redirect*

command_chain: command (PIPE command)*

command: simple_command

simple_command: command_name argument*
              | command_name

redirect: ">" WORD                            -> write_redirect
        | ">>" WORD                           -> append_redirect
        | "<" WORD                            -> stdin_redirect

argument: switch
        | WORD

switch: "/" SWITCH_CHARS

command_name: WORD

PIPE: "|"

SWITCH_CHARS: /[A-Za-z0-9]+/

WORD: /[^ \t\r\n|<>\/"']+/ | /"[^"]*"/ | /'[^']*'/

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
class GotoCommand:
    label: str


@dataclass
class CallCommand:
    target: SimpleCommand


@dataclass
class PauseCommand:
    pass


@dataclass
class IfExistCondition:
    filename: str


@dataclass
class IfErrorlevelCondition:
    level: int


@dataclass
class IfCompareCondition:
    left: str
    right: str


IfCondition = Union[IfExistCondition, IfErrorlevelCondition, IfCompareCondition]


@dataclass
class IfCommand:
    negated: bool
    condition: IfCondition
    command: "CommandLine"


@dataclass
class ForCommand:
    var: str
    items: List[str]
    command: "CommandLine"


@dataclass
class Label:
    name: str


@dataclass
class CommandLine:
    command: Union[
        SimpleCommand,
        PipeCommand,
        EchoCommand,
        GotoCommand,
        CallCommand,
        PauseCommand,
        IfCommand,
        ForCommand,
        Label,
    ]
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
# Transformer (Lark grammar only)
# ---------------------------------------------------------------------------


def _strip_quotes(val_str: str) -> str:
    if val_str.startswith('"') and val_str.endswith('"'):
        return val_str[1:-1]
    if val_str.startswith("'") and val_str.endswith("'"):
        return val_str[1:-1]
    return val_str


class _DOSTransformer(Transformer):
    @v_args(inline=True)
    def start(self, *lines):
        items = [item for item in lines if item is not None]
        return BatchProgram(lines=items)

    def command_line(self, children):
        return children[0] if children else None

    @v_args(inline=True)
    def command_chain(self, cmd, *rest):
        commands = [cmd]
        for p in rest:
            if isinstance(p, SimpleCommand):
                commands.append(p)
        if len(commands) > 1:
            return CommandLine(command=PipeCommand(commands=commands))
        return CommandLine(command=cmd)

    @v_args(inline=True)
    def command(self, cmd):
        return cmd

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
        return Argument(value=_strip_quotes(str(val)))

    @v_args(inline=True)
    def switch(self, chars):
        return Switch(name=str(chars).upper())

    @v_args(inline=True)
    def write_redirect(self, target):
        return {"type": "stdout", "target": _strip_quotes(str(target))}

    @v_args(inline=True)
    def append_redirect(self, target):
        return {"type": "append", "target": _strip_quotes(str(target))}

    @v_args(inline=True)
    def stdin_redirect(self, target):
        return {"type": "stdin", "target": _strip_quotes(str(target))}

    def PIPE(self, token):
        return token


# ---------------------------------------------------------------------------
# Redirect extraction (pre-parser)
# ---------------------------------------------------------------------------

_APPEND_RE = re.compile(r""">>\s*(\S+)""")
_WRITE_RE = re.compile(r"""(?<!>)>(?!>)\s*(\S+)""")
_INPUT_RE = re.compile(r"""<\s*(\S+)""")


def _parse_redirects(line: str):
    """Extract I/O redirections from a command line.

    Returns (cleaned_line, stdin_redirect, stdout_redirect, append_redirect).
    """
    stdin_redirect = None
    stdout_redirect = None
    append_redirect = None

    remaining = line

    m = _APPEND_RE.search(remaining)
    if m:
        append_redirect = _strip_quotes(m.group(1))
        remaining = remaining[: m.start()].rstrip() + remaining[m.end() :]

    m = _WRITE_RE.search(remaining)
    if m:
        stdout_redirect = _strip_quotes(m.group(1))
        remaining = remaining[: m.start()].rstrip() + remaining[m.end() :]

    m = _INPUT_RE.search(remaining)
    if m:
        stdin_redirect = _strip_quotes(m.group(1))
        remaining = remaining[: m.start()].rstrip() + remaining[m.end() :]

    return remaining.strip(), stdin_redirect, stdout_redirect, append_redirect


# ---------------------------------------------------------------------------
# Echo handling (pre-parser)
# ---------------------------------------------------------------------------

_ECHO_RE = re.compile(r"^ECHO\s*(.*)", re.IGNORECASE)


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
# Batch control flow parsing (pre-parser, produces AST nodes)
# ---------------------------------------------------------------------------

_GOTO_RE = re.compile(r"^GOTO\s+(\S+)$", re.IGNORECASE)
_CALL_RE = re.compile(r"^CALL\s+(.+)$", re.IGNORECASE)
_PAUSE_RE = re.compile(r"^PAUSE\s*$", re.IGNORECASE)

_IF_RE = re.compile(
    r"^IF\s+(NOT\s+)?(EXIST\s+(\S+)|ERRORLEVEL\s+(\d+)|(\S+)\s*==\s*(\S+))\s+(.+)$",
    re.IGNORECASE,
)

_FOR_RE = re.compile(
    r"^FOR\s+%%([A-Za-z])\s+IN\s*\(([^)]+)\)\s+DO\s+(.+)$",
    re.IGNORECASE,
)


def _parse_goto(line: str) -> Optional[CommandLine]:
    m = _GOTO_RE.match(line)
    if m:
        return CommandLine(command=GotoCommand(label=m.group(1).strip().upper()))
    return None


def _parse_call(line: str) -> Optional[CommandLine]:
    m = _CALL_RE.match(line)
    if not m:
        return None
    rest = m.group(1).strip()
    parsed = _parse_simple(rest)
    if parsed:
        return CommandLine(command=CallCommand(target=parsed))
    return None


def _parse_pause(line: str) -> Optional[CommandLine]:
    if _PAUSE_RE.match(line):
        return CommandLine(command=PauseCommand())
    return None


def _parse_if(line: str) -> Optional[CommandLine]:
    m = _IF_RE.match(line)
    if not m:
        return None

    negated = m.group(1) is not None
    rest_cmd = m.group(7).strip()

    condition = None
    if m.group(3):
        condition = IfExistCondition(filename=_strip_quotes(m.group(3)))
    elif m.group(4):
        condition = IfErrorlevelCondition(level=int(m.group(4)))
    elif m.group(5) and m.group(6):
        condition = IfCompareCondition(
            left=_strip_quotes(m.group(5)),
            right=_strip_quotes(m.group(6)),
        )

    if condition is None:
        return None

    cmd_cl = parse_command(rest_cmd)
    if cmd_cl is None:
        cmd_cl = CommandLine(
            command=SimpleCommand(name=CommandName(name=rest_cmd.upper()), args=[])
        )

    return CommandLine(
        command=IfCommand(negated=negated, condition=condition, command=cmd_cl),
    )


def _parse_for(line: str) -> Optional[CommandLine]:
    m = _FOR_RE.match(line)
    if not m:
        return None

    var = m.group(1).upper()
    items = m.group(2).split()
    cmd_text = m.group(3).strip()

    cmd_cl = parse_command(cmd_text)
    if cmd_cl is None:
        cmd_cl = CommandLine(
            command=SimpleCommand(name=CommandName(name=cmd_text.upper()), args=[])
        )

    return CommandLine(
        command=ForCommand(var=var, items=items, command=cmd_cl),
    )


def _parse_simple(line: str) -> Optional[SimpleCommand]:
    """Parse a simple 'CMD arg1 arg2' string into a SimpleCommand."""
    parts = line.split()
    if not parts:
        return None
    name = CommandName(name=parts[0].upper())
    args: List[Argument | Switch] = []
    for p in parts[1:]:
        if p.startswith("/"):
            args.append(Switch(name=p[1:].upper()))
        else:
            args.append(Argument(value=_strip_quotes(p)))
    return SimpleCommand(name=name, args=args)


def _first_word_upper(line: str) -> str:
    return line.upper().split()[0] if line.split() else ""


# ---------------------------------------------------------------------------
# Lark parser instance
# ---------------------------------------------------------------------------

_parser = Lark(
    _DOS_GRAMMAR,
    parser="earley",
    ambiguity="resolve",
    maybe_placeholders=False,
)

_transformer = _DOSTransformer()


def _parse_via_lark(line: str) -> Optional[CommandLine]:
    """Parse using the Lark grammar (regular commands + pipes + redirects)."""
    tree = _parser.parse(line + "\n")
    result = _transformer.transform(tree)
    if isinstance(result, BatchProgram) and result.lines:
        cl = result.lines[0]
        if isinstance(cl, CommandLine):
            return cl
    return None


# ---------------------------------------------------------------------------
# Parser public API
# ---------------------------------------------------------------------------


def parse_command(line: str) -> Optional[CommandLine]:
    if not line or not line.strip():
        return None

    line = line.strip()

    if line.startswith("::") or line.upper().startswith("REM "):
        return None

    # Extract redirects before any parsing
    line, stdin_redirect, stdout_redirect, append_redirect = _parse_redirects(line)
    if not line:
        return None

    # Labels
    if line.startswith(":"):
        label_match = re.match(r"^:([A-Za-z_][A-Za-z0-9_]*)\s*$", line)
        if label_match:
            return CommandLine(
                command=Label(name=label_match.group(1).upper()),
                stdin_redirect=stdin_redirect,
                stdout_redirect=stdout_redirect,
                append_redirect=append_redirect,
            )
        return None

    first = _first_word_upper(line)

    # ECHO (takes rest of line as literal text)
    if first == "ECHO":
        echo = _parse_echo(line)
        if echo is not None:
            return CommandLine(
                command=echo,
                stdin_redirect=stdin_redirect,
                stdout_redirect=stdout_redirect,
                append_redirect=append_redirect,
            )

    # Batch control flow - parsed into AST nodes
    if first == "GOTO":
        result = _parse_goto(line)
        if result:
            return result

    if first == "CALL":
        result = _parse_call(line)
        if result:
            return result

    if first == "PAUSE":
        result = _parse_pause(line)
        if result:
            return result

    if first == "IF":
        result = _parse_if(line)
        if result:
            return result

    if first == "FOR":
        result = _parse_for(line)
        if result:
            return result

    # Regular commands + pipes via Lark grammar
    try:
        cl = _parse_via_lark(line)
        if cl is not None:
            if stdin_redirect:
                cl.stdin_redirect = stdin_redirect
            if stdout_redirect:
                cl.stdout_redirect = stdout_redirect
            if append_redirect:
                cl.append_redirect = append_redirect
            return cl
    except Exception:
        pass

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
