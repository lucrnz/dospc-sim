"""Textual UI panel widgets for DosPC Sim."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Log, Static


class ComingSoonScreen(Static):
    """A 'Coming Soon' screen with retro styling. (Kept for backwards compatibility)"""

    DEFAULT_CSS = """
    ComingSoonScreen {
        width: 100%;
        height: 100%;
        content-align: center middle;
        background: $surface-darken-1;
    }
    ComingSoonScreen > Vertical {
        width: auto;
        height: auto;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label('╔══════════════════════════════════════╗', id='border-top')
            yield Label('║                                      ║', id='border-mid1')
            yield Label('║     🖥️  DOSPC SIM  v1.0              ║', id='title')
            yield Label('║                                      ║', id='border-mid2')
            yield Label('║     🚧 COMING SOON 🚧                ║', id='subtitle')
            yield Label('║                                      ║', id='border-mid3')
            yield Label('║     A retro computing experience     ║', id='description')
            yield Label('║                                      ║', id='border-mid4')
            yield Label('╚══════════════════════════════════════╝', id='border-bottom')


class SSHControlPanel(Static):
    """Control panel for SSH server with integrated logs."""

    DEFAULT_CSS = """
    SSHControlPanel {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    SSHControlPanel #control-section {
        height: auto;
        padding: 1;
        border: solid $primary;
        margin-bottom: 1;
    }
    SSHControlPanel #server-status {
        text-align: center;
        padding: 1;
    }
    SSHControlPanel .status-running {
        color: $success;
        text-style: bold;
    }
    SSHControlPanel .status-stopped {
        color: $error;
        text-style: bold;
    }
    SSHControlPanel .btn-container {
        align: center middle;
        height: auto;
        margin: 1 0;
    }
    SSHControlPanel #log-section {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    SSHControlPanel #ssh-log {
        height: 100%;
        border: solid $surface-darken-2;
        background: $surface-darken-1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id='control-section'):
                yield Label('🔐 SSH Server Control', id='panel-title')
                yield Label(
                    'Status: Stopped', id='server-status', classes='status-stopped'
                )
                with Horizontal(classes='btn-container'):
                    yield Button('▶ Start', id='btn-start', variant='success')
                    yield Button(
                        '⏹ Stop', id='btn-stop', variant='error', disabled=True
                    )
                yield Label('Host: 0.0.0.0:2222', id='server-host')
                yield Label('Active Connections: 0', id='active-connections')

            with Vertical(id='log-section'):
                yield Label('📜 SSH Server Logs', id='log-title')
                yield Log(id='ssh-log')


class UserManagementPanel(Static):
    """Panel for managing users."""

    DEFAULT_CSS = """
    UserManagementPanel {
        padding: 1;
        border: solid $primary;
        height: 100%;
    }
    UserManagementPanel #user-form {
        padding: 1;
        height: auto;
    }
    UserManagementPanel Input {
        margin: 1 0;
    }
    UserManagementPanel #users-table {
        height: 1fr;
        border: solid $surface-darken-2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label('👥 User Management', id='panel-title')
        with Vertical(id='user-form'):
            yield Label('Create New User:')
            yield Input(placeholder='Username', id='input-username')
            yield Input(placeholder='Password', password=True, id='input-password')
            with Horizontal():
                yield Button('Create User', id='btn-create-user', variant='primary')
                yield Button('Refresh List', id='btn-refresh-users')
        yield Label('')
        yield Label('Existing Users:')
        yield DataTable(id='users-table')
