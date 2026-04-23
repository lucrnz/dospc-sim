"""Tests for standalone dos-shell CLI entrypoint."""

import io

from dospc_sim import dos_shell_cli


class _FakeStdin(io.StringIO):
    def __init__(self, value: str, *, is_tty: bool):
        super().__init__(value)
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


def test_run_interactive_mode_uses_current_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dos_shell_cli.sys, 'stdin', _FakeStdin('', is_tty=True))
    monkeypatch.setattr(dos_shell_cli.getpass, 'getuser', lambda: 'testuser')

    captured = {}

    def fake_run_interactive(shell):
        captured['home_dir'] = shell.fs.home_dir
        return 42

    monkeypatch.setattr(dos_shell_cli, '_run_interactive', fake_run_interactive)

    result = dos_shell_cli.run_dos_shell([])

    assert result == 42
    assert captured['home_dir'] == tmp_path.resolve()


def test_run_script_file_with_args(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dos_shell_cli.getpass, 'getuser', lambda: 'testuser')
    (tmp_path / 'greet.bat').write_text('ECHO %1', encoding='utf-8')

    result = dos_shell_cli.run_dos_shell(['greet.bat', 'World'])

    output = capsys.readouterr().out
    assert result == 0
    assert 'World' in output


def test_run_piped_stdin_without_source_executes_and_exits(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dos_shell_cli.getpass, 'getuser', lambda: 'testuser')
    monkeypatch.setattr(
        dos_shell_cli.sys, 'stdin', _FakeStdin('ECHO Pipe', is_tty=False)
    )
    monkeypatch.setattr(
        dos_shell_cli,
        '_run_interactive',
        lambda shell: (_ for _ in ()).throw(AssertionError('interactive mode called')),
    )

    result = dos_shell_cli.run_dos_shell([])

    output = capsys.readouterr().out
    assert result == 0
    assert 'Pipe' in output


def test_run_explicit_dash_stdin_token(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dos_shell_cli.getpass, 'getuser', lambda: 'testuser')
    monkeypatch.setattr(
        dos_shell_cli.sys, 'stdin', _FakeStdin('ECHO DashToken', is_tty=True)
    )

    result = dos_shell_cli.run_dos_shell(['-'])

    output = capsys.readouterr().out
    assert result == 0
    assert 'DashToken' in output


def test_run_explicit_stdin_token_with_args(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dos_shell_cli.getpass, 'getuser', lambda: 'testuser')
    monkeypatch.setattr(dos_shell_cli.sys, 'stdin', _FakeStdin('ECHO %1', is_tty=True))

    result = dos_shell_cli.run_dos_shell(['STDIN', 'ArgumentValue'])

    output = capsys.readouterr().out
    assert result == 0
    assert 'ArgumentValue' in output


def test_run_script_missing_file_returns_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dos_shell_cli.getpass, 'getuser', lambda: 'testuser')

    result = dos_shell_cli.run_dos_shell(['missing.bat'])

    output = capsys.readouterr().out
    assert result == 1
    assert 'Bad command or file name' in output
