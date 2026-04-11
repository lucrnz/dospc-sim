"""DosPC Sim - A retro-styled terminal UI application with SSH server."""

import logging
import queue
import threading
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Grid
from textual.widgets import (
    Header,
    Footer,
    Static,
    Label,
    Button,
    Input,
    DataTable,
    Log,
    TabbedContent,
    TabPane,
    Checkbox,
)
from textual.reactive import reactive
from textual.color import Color

from dospc_sim.ssh_server import SSHServer
from dospc_sim.users import UserManager
from dospc_sim.cli import run_cli


# Setup logging - use a queue to avoid TUI conflicts
log_queue = queue.Queue()
logger = logging.getLogger("dospc_sim")


class QueueLogHandler(logging.Handler):
    """Log handler that puts messages in a queue for thread-safe TUI updates."""

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            pass


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
            yield Label("╔══════════════════════════════════════╗", id="border-top")
            yield Label("║                                      ║", id="border-mid1")
            yield Label("║     🖥️  DOSPC SIM  v1.0              ║", id="title")
            yield Label("║                                      ║", id="border-mid2")
            yield Label("║     🚧 COMING SOON 🚧                ║", id="subtitle")
            yield Label("║                                      ║", id="border-mid3")
            yield Label("║     A retro computing experience     ║", id="description")
            yield Label("║                                      ║", id="border-mid4")
            yield Label("╚══════════════════════════════════════╝", id="border-bottom")


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
            # Control section
            with Vertical(id="control-section"):
                yield Label("🔐 SSH Server Control", id="panel-title")
                yield Label(
                    "Status: Stopped", id="server-status", classes="status-stopped"
                )
                with Horizontal(classes="btn-container"):
                    yield Button("▶ Start", id="btn-start", variant="success")
                    yield Button(
                        "⏹ Stop", id="btn-stop", variant="error", disabled=True
                    )
                yield Label("Host: 0.0.0.0:2222", id="server-host")
                yield Label("Active Connections: 0", id="active-connections")

            # Log section
            with Vertical(id="log-section"):
                yield Label("📜 SSH Server Logs", id="log-title")
                yield Log(id="ssh-log")


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
        yield Label("👥 User Management", id="panel-title")
        with Vertical(id="user-form"):
            yield Label("Create New User:")
            yield Input(placeholder="Username", id="input-username")
            yield Input(placeholder="Password", password=True, id="input-password")
            with Horizontal():
                yield Button("Create User", id="btn-create-user", variant="primary")
                yield Button("Refresh List", id="btn-refresh-users")
        yield Label("")
        yield Label("Existing Users:")
        yield DataTable(id="users-table")


class DosPCSimApp(App):
    """Main DosPC Sim application with SSH server and retro styling."""

    CSS = """
    Screen {
        background: $surface-darken-1;
    }
    Header {
        display: none;
    }
    Footer {
        background: $surface;
        color: $text;
    }
    TabbedContent {
        padding: 0 1;
        height: 100%;
    }
    TabPane {
        padding: 1;
        height: 100%;
    }
    ContentSwitcher {
        height: 100%;
    }
    #panel-title {
        text-style: bold;
        text-align: center;
        padding: 1;
    }
    #home-screen {
        text-align: center;
        content-align: center middle;
        height: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "toggle_theme", "Toggle Theme"),
        ("f1", "help", "Help"),
    ]

    dark_mode = reactive(True)

    def __init__(self) -> None:
        super().__init__()
        self.ssh_server: SSHServer | None = None
        self.user_manager = UserManager()
        self.log_handler = None
        self.log_widget: Log | None = None

    def compose(self) -> ComposeResult:
        # No menubar - using tabs instead

        with TabbedContent():
            with TabPane("🏠 Home", id="tab-home"):
                yield self._create_home_screen()
            with TabPane("🔐 SSH Server", id="tab-ssh"):
                yield SSHControlPanel()
            with TabPane("👥 Users", id="tab-users"):
                yield UserManagementPanel()

        yield Footer()

    def _create_home_screen(self) -> Static:
        """Create the home/welcome screen."""
        return Static(
            """
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║                    🖥️  DOSPC SIM  v1.0                          ║
║                                                                ║
║              SSH DOS Environment Server                        ║
║                                                                ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  Features:                                                     ║
║  • SSH server with DOS environment simulation                  ║
║  • User isolation with dedicated home directories              ║
║  • Full DOS command support (DIR, CD, MD, COPY, etc.)          ║
║  • Batch file execution                                        ║
║                                                                ║
║  Use the tabs above to:                                        ║
║  • 🔐 SSH Server - Start/stop server and view logs             ║
║  • 👥 Users - Create and manage user accounts                  ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
        """,
            id="home-screen",
        )

    def on_mount(self) -> None:
        self.title = "DosPC Sim"
        self.sub_title = "SSH DOS Environment Server"

        # Initialize SSH server (not started yet)
        self.ssh_server = SSHServer()

        # Setup logging after widgets are mounted
        self._setup_log_handler()
        self._refresh_users_table()

        # Apply initial theme
        self.update_theme()

        # Start log polling
        self.set_interval(0.1, self._poll_log_queue)

    def _setup_log_handler(self) -> None:
        """Setup log handler to capture SSH logs."""
        try:
            # Store reference to log widget
            self.log_widget = self.query_one("#ssh-log", Log)

            # Create queue-based handler
            self.log_handler = QueueLogHandler(log_queue)
            self.log_handler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            self.log_handler.setFormatter(formatter)

            # Add to loggers
            logging.getLogger("dospc_sim").addHandler(self.log_handler)
            logging.getLogger("dospc_sim.ssh").addHandler(self.log_handler)

            # Log startup message
            logger.info("DosPC Sim UI started - SSH Server ready")
        except Exception as e:
            print(f"Failed to setup log handler: {e}")

    def _poll_log_queue(self) -> None:
        """Poll the log queue and write to the Log widget."""
        if self.log_widget is None:
            return

        try:
            # Process up to 10 messages per poll
            for _ in range(10):
                try:
                    msg = log_queue.get_nowait()
                    self.log_widget.write_line(msg)
                except queue.Empty:
                    break
        except Exception:
            pass

    def _refresh_users_table(self) -> None:
        """Refresh the users table."""
        try:
            table = self.query_one("#users-table", DataTable)
            table.clear(columns=True)
            table.add_columns("Username", "Created", "Last Login", "Home Directory")

            for user in self.user_manager.list_users():
                last_login = user.last_login or "Never"
                table.add_row(
                    user.username,
                    user.created_at[:10],
                    last_login[:10] if last_login != "Never" else last_login,
                    str(user.home_dir),
                )
        except Exception as e:
            logger.error(f"Failed to refresh users table: {e}")

    def watch_dark_mode(self, dark_mode: bool) -> None:
        """Watch for dark mode changes and update theme."""
        self.update_theme()

    def update_theme(self) -> None:
        """Update the application theme based on dark_mode state."""
        # Apply theme to app
        self.dark = self.dark_mode

        # Update CSS variables by refreshing the screen
        self.refresh_css()

        # Log theme change
        theme_name = "dark" if self.dark_mode else "light"
        logger.info(f"Theme changed to {theme_name}")

    def action_toggle_theme(self) -> None:
        """Toggle between light and dark themes."""
        self.dark_mode = not self.dark_mode
        self.notify(f"Theme: {'Dark' if self.dark_mode else 'Light'}")

    def action_help(self) -> None:
        """Show help information."""
        self.notify("Help: Use tabs to navigate. 't' toggles theme, 'q' to quit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id

        if btn_id == "btn-start":
            self._start_ssh_server()
        elif btn_id == "btn-stop":
            self._stop_ssh_server()
        elif btn_id == "btn-create-user":
            self._create_user()
        elif btn_id == "btn-refresh-users":
            self._refresh_users_table()

    def _start_ssh_server(self) -> None:
        """Start the SSH server."""
        if self.ssh_server and not self.ssh_server.is_running():
            if self.ssh_server.start():
                self.query_one("#server-status", Label).update("Status: Running")
                self.query_one("#server-status", Label).remove_class("status-stopped")
                self.query_one("#server-status", Label).add_class("status-running")
                self.query_one("#btn-start", Button).disabled = True
                self.query_one("#btn-stop", Button).disabled = False
                logger.info("SSH server started on port 2222")
                self._update_server_status()
            else:
                logger.error("Failed to start SSH server")
                self.notify("Failed to start SSH server", severity="error")

    def _stop_ssh_server(self) -> None:
        """Stop the SSH server."""
        if self.ssh_server and self.ssh_server.is_running():
            self.ssh_server.stop()
            self.query_one("#server-status", Label).update("Status: Stopped")
            self.query_one("#server-status", Label).remove_class("status-running")
            self.query_one("#server-status", Label).add_class("status-stopped")
            self.query_one("#btn-start", Button).disabled = False
            self.query_one("#btn-stop", Button).disabled = True
            logger.info("SSH server stopped")

    def _update_server_status(self) -> None:
        """Update server status display."""
        if self.ssh_server and self.ssh_server.is_running():
            status = self.ssh_server.get_status()
            try:
                self.query_one("#active-connections", Label).update(
                    f"Active Connections: {status['active_connections']}"
                )
            except Exception:
                pass
            # Schedule next update
            self.set_timer(1, self._update_server_status)

    def _create_user(self) -> None:
        """Create a new user."""
        username_input = self.query_one("#input-username", Input)
        password_input = self.query_one("#input-password", Input)

        username = username_input.value.strip()
        password = password_input.value

        if not username or not password:
            self.notify("Username and password are required", severity="error")
            return

        try:
            self.user_manager.create_user(username, password)
            logger.info(f"User '{username}' created successfully")
            self.notify(f"User '{username}' created successfully")
            username_input.value = ""
            password_input.value = ""
            self._refresh_users_table()
        except ValueError as e:
            self.notify(str(e), severity="error")
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            self.notify(f"Failed to create user: {e}", severity="error")

    def on_unmount(self) -> None:
        """Cleanup when app closes."""
        if self.ssh_server and self.ssh_server.is_running():
            self.ssh_server.stop()


def main() -> None:
    """Entry point for the DosPC Sim application."""
    if run_cli():
        return
    app = DosPCSimApp()
    app.run()


if __name__ == "__main__":
    main()
