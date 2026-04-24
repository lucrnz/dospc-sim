"""AST node definitions for DOS parser output."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Argument:
    value: str


@dataclass
class Switch:
    name: str

    @property
    def value(self) -> str:
        return f'/{self.name}'


@dataclass
class CommandName:
    name: str


@dataclass
class SimpleCommand:
    name: CommandName
    args: list[Argument | Switch] = field(default_factory=list)

    @property
    def command(self) -> str:
        return self.name.name

    @property
    def arguments(self) -> list[str]:
        return [a.value for a in self.args]

    @property
    def switches(self) -> list[Switch]:
        return [a for a in self.args if isinstance(a, Switch)]

    @property
    def positional_args(self) -> list[str]:
        return [a.value for a in self.args if isinstance(a, Argument)]


@dataclass
class PipeCommand:
    commands: list[SimpleCommand]


@dataclass
class EchoCommand:
    text: str | None = None
    on: bool | None = None


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


IfCondition = IfExistCondition | IfErrorlevelCondition | IfCompareCondition


@dataclass
class IfCommand:
    negated: bool
    condition: IfCondition
    command: CommandLine


@dataclass
class ForCommand:
    var: str
    items: list[str]
    command: CommandLine


@dataclass
class Label:
    name: str


@dataclass
class CommandLine:
    command: (
        SimpleCommand
        | PipeCommand
        | EchoCommand
        | GotoCommand
        | CallCommand
        | PauseCommand
        | IfCommand
        | ForCommand
        | Label
    )
    stdin_redirect: str | None = None
    stdout_redirect: str | None = None
    append_redirect: str | None = None


@dataclass
class BatchProgram:
    lines: list[CommandLine]

    @property
    def commands(self) -> list[CommandLine]:
        return self.lines
