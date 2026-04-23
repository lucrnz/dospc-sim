"""Standalone CLI entrypoint for the DOS shell runtime."""

import argparse
import getpass
import sys
from pathlib import Path

from dospc_sim.dos_shell import DOSShell
from dospc_sim.filesystem import UserFilesystem

_STDIN_TOKENS = {'-', 'STDIN'}


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for standalone DOS shell mode."""
    parser = argparse.ArgumentParser(
        prog='dos-shell',
        description='Run the standalone DOS shell interpreter.',
    )
    parser.add_argument(
        'source',
        nargs='?',
        help='Batch source to execute (file path, -, or STDIN)',
    )
    parser.add_argument(
        'script_args',
        nargs='*',
        help='Arguments passed to batch source as %1..%9',
    )
    return parser


def _create_shell() -> DOSShell:
    """Create a DOS shell rooted at the current working directory."""
    username = getpass.getuser() or 'local'
    filesystem = UserFilesystem(str(Path.cwd()), username)
    return DOSShell(filesystem, username)


def _run_interactive(shell: DOSShell) -> int:
    """Run interactive shell session until EXIT or EOF."""
    shell.run()

    while shell.running:
        try:
            command = input(shell.get_prompt())
        except EOFError:
            break
        except KeyboardInterrupt:
            print()
            continue

        shell.execute_command(command)

    return shell.last_errorlevel


def _run_script(shell: DOSShell, script_path: str, script_args: list[str]) -> int:
    """Execute batch file script and exit."""
    batch_file = shell._find_batch_file(script_path)
    if batch_file is None:
        shell._output_line(f'Bad command or file name: {script_path}')
        return 1
    return shell._execute_batch(batch_file, script_args)


def _run_stdin(shell: DOSShell, script_args: list[str]) -> int:
    """Execute batch content from stdin and exit."""
    content = sys.stdin.read()
    if not content:
        return 0
    return shell.execute_batch_content(content, batch_name='STDIN', args=script_args)


def run_dos_shell(argv: list[str] | None = None) -> int:
    """Run standalone DOS shell command and return exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    shell = _create_shell()
    source = args.source

    if source in _STDIN_TOKENS or (source and source.upper() == 'STDIN'):
        return _run_stdin(shell, args.script_args)

    if source:
        return _run_script(shell, source, args.script_args)

    if not sys.stdin.isatty():
        return _run_stdin(shell, [])

    return _run_interactive(shell)


def main() -> None:
    """CLI script entrypoint."""
    raise SystemExit(run_dos_shell())


if __name__ == '__main__':
    main()
