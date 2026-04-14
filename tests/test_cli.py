"""Tests for the CLI interface."""

from unittest.mock import patch

import pytest

from dospc_sim.cli import build_parser, run_cli
from dospc_sim.users import UserManager


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / 'data'
    d.mkdir()
    return d


@pytest.fixture
def user_manager(data_dir):
    return UserManager(data_dir)


@pytest.fixture(autouse=True)
def isolate_data(tmp_path, monkeypatch):
    monkeypatch.setattr('dospc_sim.users.DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr('dospc_sim.users.USERS_FILE', tmp_path / 'data' / 'users.json')
    monkeypatch.setattr('dospc_sim.users.USERS_DIR', tmp_path / 'data' / 'users')
    monkeypatch.setattr(
        'dospc_sim.cli.UserManager', lambda: UserManager(tmp_path / 'data')
    )


class TestBuildParser:
    def test_parser_creates_without_error(self):
        parser = build_parser()
        assert parser is not None

    def test_parse_user_add(self):
        parser = build_parser()
        args = parser.parse_args(['user', 'add', 'alice'])
        assert args.command == 'user'
        assert args.user_command == 'add'
        assert args.username == 'alice'

    def test_parse_user_list(self):
        parser = build_parser()
        args = parser.parse_args(['user', 'list'])
        assert args.command == 'user'
        assert args.user_command == 'list'

    def test_parse_user_remove(self):
        parser = build_parser()
        args = parser.parse_args(['user', 'remove', 'bob'])
        assert args.command == 'user'
        assert args.user_command == 'remove'
        assert args.username == 'bob'

    def test_parse_server_listen(self):
        parser = build_parser()
        args = parser.parse_args(['server', 'listen'])
        assert args.command == 'server'
        assert args.server_command == 'listen'
        assert args.host == '0.0.0.0'
        assert args.port == 2222

    def test_parse_server_listen_custom(self):
        parser = build_parser()
        args = parser.parse_args(
            ['server', 'listen', '--host', '127.0.0.1', '--port', '8022']
        )
        assert args.host == '127.0.0.1'
        assert args.port == 8022

    def test_parse_no_command(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None


class TestRunCli:
    def test_no_command_returns_false(self):
        result = run_cli([])
        assert result is False

    def test_user_add(self, tmp_path):
        with patch('dospc_sim.cli.getpass.getpass', side_effect=['secret', 'secret']):
            result = run_cli(['user', 'add', 'testuser'])

        assert result is True
        um = UserManager(tmp_path / 'data')
        assert um.user_exists('testuser')

    def test_user_add_password_mismatch(self, tmp_path):
        with (
            patch('dospc_sim.cli.getpass.getpass', side_effect=['secret', 'other']),
            pytest.raises(SystemExit),
        ):
            run_cli(['user', 'add', 'mismatchuser'])

    def test_user_add_empty_password(self, tmp_path):
        with (
            patch('dospc_sim.cli.getpass.getpass', return_value=''),
            pytest.raises(SystemExit),
        ):
            run_cli(['user', 'add', 'emptyuser'])

    def test_user_list_empty(self, capsys):
        result = run_cli(['user', 'list'])
        assert result is True
        captured = capsys.readouterr()
        assert 'No users found' in captured.out

    def test_user_list_with_users(self, tmp_path, capsys):
        um = UserManager(tmp_path / 'data')
        um.create_user('alice', 'password123')

        result = run_cli(['user', 'list'])
        assert result is True
        captured = capsys.readouterr()
        assert 'alice' in captured.out

    def test_user_remove(self, tmp_path):
        um = UserManager(tmp_path / 'data')
        um.create_user('bob', 'password123')

        with patch('builtins.input', side_effect=['y', 'y']):
            result = run_cli(['user', 'remove', 'bob'])

        assert result is True
        um2 = UserManager(tmp_path / 'data')
        assert not um2.user_exists('bob')

    def test_user_remove_cancelled(self, tmp_path):
        um = UserManager(tmp_path / 'data')
        um.create_user('charlie', 'password123')

        with patch('builtins.input', return_value='n'):
            result = run_cli(['user', 'remove', 'charlie'])

        assert result is True
        assert um.user_exists('charlie')

    def test_user_remove_not_found(self, tmp_path):
        with pytest.raises(SystemExit):
            run_cli(['user', 'remove', 'nonexistent'])

    def test_user_subcommand_missing_exits(self):
        with pytest.raises(SystemExit):
            run_cli(['user'])

    def test_server_subcommand_missing_exits(self):
        with pytest.raises(SystemExit):
            run_cli(['server'])
