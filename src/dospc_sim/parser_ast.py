"""AST node definitions for DOS parser output."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Argument:
    value: str


@dataclass(slots=True)
class Switch:
    name: str

    @property
    def value(self) -> str:
        return f'/{self.name}'


@dataclass(slots=True)
class CommandName:
    name: str


@dataclass(slots=True)
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


@dataclass(slots=True)
class PipeCommand:
    commands: list[SimpleCommand | EchoCommand]


@dataclass(slots=True)
class EchoCommand:
    text: str | None = None
    on: bool | None = None


@dataclass(slots=True)
class GotoCommand:
    label: str


@dataclass(slots=True)
class CallCommand:
    target: SimpleCommand


@dataclass(slots=True)
class PauseCommand:
    pass


@dataclass(slots=True)
class IfExistCondition:
    filename: str


@dataclass(slots=True)
class IfErrorlevelCondition:
    level: int


@dataclass(slots=True)
class IfCompareCondition:
    left: str
    right: str


@dataclass(slots=True)
class IfDefinedCondition:
    variable: str


IfCondition = (
    IfExistCondition | IfErrorlevelCondition | IfCompareCondition | IfDefinedCondition
)


@dataclass(slots=True)
class IfCommand:
    negated: bool
    condition: IfCondition
    command: CommandLine
    else_command: CommandLine | None = None


@dataclass(slots=True)
class ForCommand:
    var: str
    items: list[str]
    command: CommandLine


@dataclass(slots=True)
class ChainCommand:
    """Represents command chaining with && (and_then) or || (or_else)."""

    left: CommandLine
    operator: str  # '&&' or '||'
    right: CommandLine


@dataclass(slots=True)
class Label:
    name: str


@dataclass(slots=True)
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
        | ChainCommand
        | Label
    )
    stdin_redirect: str | None = None
    stdout_redirect: str | None = None
    append_redirect: str | None = None


@dataclass(slots=True)
class BatchProgram:
    lines: list[CommandLine]

    @property
    def commands(self) -> list[CommandLine]:
        return self.lines
