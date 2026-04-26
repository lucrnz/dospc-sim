"""SSH Server implementation for DosPC Sim."""

import logging
import os
import select
import socket
import threading
from pathlib import Path

from paramiko import RSAKey, ServerInterface, Transport
from paramiko.common import (
    AUTH_FAILED,
    AUTH_SUCCESSFUL,
    OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED,
    OPEN_SUCCEEDED,
)

from dospc_sim.dos_shell import DOSShell
from dospc_sim.filesystem import UserFilesystem
from dospc_sim.users import User, UserManager

# Setup logging
logger = logging.getLogger('dospc_sim.ssh')


DATA_DIR = Path('data')
SSH_KEYS_DIR = DATA_DIR / 'ssh_keys'
HOST_KEY_FILE = SSH_KEYS_DIR / 'host_rsa_key'


class SSHServerInterface(ServerInterface):
    """Paramiko server interface implementation."""

    def __init__(self, user_manager: UserManager, client_address: tuple):
        self.user_manager = user_manager
        self.client_address = client_address
        self.user: User | None = None
        self.authenticated = False
        self.event = threading.Event()
        logger.info(f'New connection from {client_address[0]}:{client_address[1]}')

    def check_channel_request(self, kind: str, chanid: int):
        """Check if a channel request is allowed."""
        if kind == 'session':
            return OPEN_SUCCEEDED
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username: str, password: str):
        """Authenticate using password."""
        logger.info(f'Password auth attempt for user: {username}')
        user = self.user_manager.authenticate(username, password)
        if user:
            self.user = user
            self.authenticated = True
            addr = self.client_address[0]
            logger.info(f'User {username} authenticated from {addr}')
            return AUTH_SUCCESSFUL
        logger.warning(
            f'Failed password auth for user: {username} from {self.client_address[0]}'
        )
        return AUTH_FAILED

    def check_auth_publickey(self, username: str, key):
        """Authenticate using public key (not implemented)."""
        return AUTH_FAILED

    def get_allowed_auths(self, username: str):
        """Return allowed authentication methods."""
        return 'password'

    def check_channel_shell_request(self, channel):
        """Accept shell request."""
        self.event.set()
        return True

    def check_channel_pty_request(
        self,
        channel,
        term: str,
        width: int,
        height: int,
        pixelwidth: int,
        pixelheight: int,
        modes: bytes,
    ):
        """Accept PTY request."""
        return True

    def check_channel_exec_request(self, channel, command: bytes):
        """Accept exec request."""
        return False  # Disable exec for now, use shell only


class SSHInteractiveSession:
    """Interactive SSH shell session with line editing state."""

    def __init__(self, channel, shell: DOSShell, username: str, tab_complete):
        self.channel = channel
        self.shell = shell
        self.username = username
        self._tab_complete = tab_complete
        self.command_buffer = ''
        self.cursor_pos = 0
        self.history: list[str] = []
        self.history_index = 0

    def _refresh_line(self) -> None:
        prompt = self.shell.get_prompt()
        self.channel.send(f'\r\x1b[K{prompt}{self.command_buffer}')
        if self.cursor_pos < len(self.command_buffer):
            self.channel.send(f'\x1b[{len(self.command_buffer) - self.cursor_pos}D')

    def _show_prompt(self) -> None:
        self.channel.send(self.shell.get_prompt())

    def _parse_escape_sequence(self, raw: bytes, index: int) -> tuple[str, int, bytes]:
        seq = bytes([raw[index]])
        index += 1
        while index < len(raw) and len(seq) < 8:
            seq += bytes([raw[index]])
            index += 1
            if len(seq) == 2 and seq[1] in (0x4F, 0x5B):
                continue
            if (len(seq) >= 3 and chr(seq[-1]).isalpha()) or seq[-1] == ord('~'):
                break
        else:
            try:
                ready, _, _ = select.select([self.channel], [], [], 0.05)
                if ready:
                    more = self.channel.recv(16)
                    raw = raw[:index] + more + raw[index:]
                    while index < len(raw) and len(seq) < 8:
                        seq += bytes([raw[index]])
                        index += 1
                        if len(seq) == 2 and seq[1] in (0x4F, 0x5B):
                            continue
                        if (len(seq) >= 3 and chr(seq[-1]).isalpha()) or seq[-1] == ord('~'):
                            break
            except Exception:
                pass
        return seq.decode('utf-8', errors='ignore'), index, raw

    def _handle_escape(self, seq_str: str) -> None:
        if seq_str == '\x1b[A':
            if self.history and self.history_index > 0:
                self.history_index -= 1
                self.command_buffer = self.history[self.history_index]
                self.cursor_pos = len(self.command_buffer)
                self._refresh_line()
            return
        if seq_str == '\x1b[B':
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.command_buffer = self.history[self.history_index]
            else:
                self.history_index = len(self.history)
                self.command_buffer = ''
            self.cursor_pos = len(self.command_buffer)
            self._refresh_line()
            return
        if seq_str == '\x1b[C':
            if self.cursor_pos < len(self.command_buffer):
                self.cursor_pos += 1
                self.channel.send('\x1b[C')
            return
        if seq_str == '\x1b[D':
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                self.channel.send('\x1b[D')
            return
        if seq_str in ('\x1b[H', '\x1b[1~', '\x1bOH'):
            if self.cursor_pos > 0:
                self.channel.send(f'\x1b[{self.cursor_pos}D')
                self.cursor_pos = 0
            return
        if seq_str in ('\x1b[F', '\x1b[4~', '\x1bOF'):
            if self.cursor_pos < len(self.command_buffer):
                self.channel.send(f'\x1b[{len(self.command_buffer) - self.cursor_pos}C')
                self.cursor_pos = len(self.command_buffer)
            return
        if seq_str == '\x1b[3~' and self.cursor_pos < len(self.command_buffer):
            self.command_buffer = (
                self.command_buffer[: self.cursor_pos]
                + self.command_buffer[self.cursor_pos + 1 :]
            )
            self.channel.send(self.command_buffer[self.cursor_pos:] + ' ')
            self.channel.send(f'\x1b[{len(self.command_buffer) - self.cursor_pos + 1}D')

    def _handle_enter(self, raw: bytes, index: int) -> int:
        index += 1
        if index < len(raw) and raw[index] == 0x0A:
            index += 1
        self.channel.send('\r\n')
        if self.command_buffer.strip():
            command = self.command_buffer.strip()
            logger.info(f'User {self.username} executed: {command}')
            self.shell.execute_command(command)
            self.history.append(command)
            self.history_index = len(self.history)
        self.command_buffer = ''
        self.cursor_pos = 0
        if self.shell.running:
            self._show_prompt()
        return index

    def _handle_backspace(self) -> None:
        if self.cursor_pos > 0:
            self.command_buffer = (
                self.command_buffer[: self.cursor_pos - 1]
                + self.command_buffer[self.cursor_pos :]
            )
            self.cursor_pos -= 1
            self.channel.send('\b' + self.command_buffer[self.cursor_pos:] + ' ')
            move_back = len(self.command_buffer) - self.cursor_pos + 1
            self.channel.send(f'\x1b[{move_back}D')

    def _handle_interrupt(self) -> None:
        self.channel.send('^C\r\n')
        self.command_buffer = ''
        self.cursor_pos = 0
        self.history_index = len(self.history)
        if self.shell.running:
            self._show_prompt()

    def _handle_tab(self) -> None:
        completions = self._tab_complete(self.command_buffer, self.cursor_pos)
        if len(completions) == 1:
            prefix = self.command_buffer[: self.cursor_pos]
            last_space = prefix.rfind(' ')
            before = prefix[: last_space + 1] if last_space >= 0 else ''
            new_word = completions[0]
            after = self.command_buffer[self.cursor_pos :]
            self.command_buffer = before + new_word + after
            self.cursor_pos = len(before) + len(new_word)
            self._refresh_line()
            return
        if len(completions) > 1:
            self.channel.send('\r\n')
            max_len = max(len(c) for c in completions) + 2
            cols = max(1, 80 // max_len)
            for idx in range(0, len(completions), cols):
                row = completions[idx : idx + cols]
                self.channel.send('  '.join(f'{c:<{max_len}}' for c in row) + '\r\n')
            self._refresh_line()

    def _insert_printable(self, ch: str) -> None:
        self.command_buffer = (
            self.command_buffer[: self.cursor_pos]
            + ch
            + self.command_buffer[self.cursor_pos :]
        )
        self.cursor_pos += 1
        self.channel.send(ch + self.command_buffer[self.cursor_pos:])
        if len(self.command_buffer) - self.cursor_pos > 0:
            self.channel.send(f'\x1b[{len(self.command_buffer) - self.cursor_pos}D')

    def run(self) -> None:
        self.history_index = len(self.history)
        self._show_prompt()
        while self.shell.running and not self.channel.closed:
            data = self.channel.recv(1024)
            if not data:
                break
            index = 0
            while index < len(data):
                byte = data[index]
                if byte == 0x1B:
                    seq, index, data = self._parse_escape_sequence(data, index)
                    self._handle_escape(seq)
                    continue
                if byte in (0x0D, 0x0A):
                    index = self._handle_enter(data, index)
                    continue
                if byte in (0x7F, 0x08):
                    index += 1
                    self._handle_backspace()
                    continue
                if byte == 0x03:
                    index += 1
                    self._handle_interrupt()
                    continue
                if byte == 0x04:
                    self.shell.running = False
                    break
                if byte == 0x09:
                    index += 1
                    self._handle_tab()
                    continue
                if 0x20 <= byte < 0x7F:
                    index += 1
                    self._insert_printable(chr(byte))
                    continue
                index += 1


class SSHClientHandler(threading.Thread):
    """Handle a single SSH client connection."""

    def __init__(
        self,
        client_socket: socket.socket,
        address: tuple,
        host_key: RSAKey,
        user_manager: UserManager,
    ):
        super().__init__(daemon=True)
        self.client_socket = client_socket
        self.address = address
        self.host_key = host_key
        self.user_manager = user_manager
        self.transport: Transport | None = None
        self.channel = None
        self.shell: DOSShell | None = None

    def run(self):
        """Handle the client connection."""
        try:
            self.transport = Transport(self.client_socket)
            self.transport.add_server_key(self.host_key)

            server = SSHServerInterface(self.user_manager, self.address)
            self.transport.start_server(server=server)

            # Wait for authentication
            chan = self.transport.accept(30)
            if chan is None:
                logger.warning(f'No channel established for {self.address[0]}')
                return

            if not server.authenticated or server.user is None:
                logger.warning(f'Client not authenticated: {self.address[0]}')
                chan.close()
                return

            # Setup DOS environment
            self._setup_shell(chan, server.user)

        except Exception as e:
            logger.error(f'Error handling client {self.address[0]}: {e}')
        finally:
            self._cleanup()

    def _setup_shell(self, channel, user: User):
        """Setup DOS shell for the user."""
        fs = UserFilesystem(user.home_dir, user.username)

        _crlf = b'\r\n'

        def output_callback(text: str):
            """Send output to the client."""
            try:
                channel.sendall(text.encode('utf-8') + _crlf)
            except Exception:
                pass

        self.shell = DOSShell(fs, user.username, output_callback)

        def input_callback():
            try:
                data = channel.recv(1024)
                return data.decode('utf-8', errors='ignore') if data else ''
            except Exception:
                return ''

        self.shell._input_callback = input_callback
        self.shell.set_editor_handler(
            lambda filename: self._run_editor(channel, fs, filename)
        )
        self.shell.run()

        session = SSHInteractiveSession(
            channel=channel,
            shell=self.shell,
            username=user.username,
            tab_complete=lambda buffer, cursor: self._tab_complete(
                fs, self.shell, buffer, cursor
            ),
        )

        try:
            session.run()
        except Exception as e:
            logger.error(f'Error in shell for {user.username}: {e}')

        logger.info(f'Session ended for user {user.username} from {self.address[0]}')
        try:
            channel.send('\r\nGoodbye!\r\n')
        except Exception:
            pass

    @staticmethod
    def _tab_complete(
        fs: UserFilesystem, shell: DOSShell, buffer: str, cursor_pos: int
    ) -> list[str]:
        """Generate tab completions for the current buffer."""
        prefix = buffer[:cursor_pos]
        last_space = prefix.rfind(' ')

        if last_space < 0:
            # Completing a command name
            partial = prefix.upper()
            commands = list(shell.get_available_commands())
            matches = [c for c in commands if c.startswith(partial)]
            # Also check batch files
            try:
                entries = fs.list_directory('.')
                for e in entries:
                    upper_name = e.name.upper()
                    if upper_name.endswith(('.BAT', '.CMD')):
                        base = upper_name.rsplit('.', 1)[0]
                        if base.startswith(partial):
                            matches.append(base)
            except Exception:
                pass
            return matches
        else:
            # Completing a filename/path
            partial = prefix[last_space + 1 :]
            try:
                # Handle path with directory component
                if '\\' in partial or '/' in partial:
                    sep_idx = max(partial.rfind('\\'), partial.rfind('/'))
                    dir_part = partial[: sep_idx + 1]
                    file_prefix = partial[sep_idx + 1 :].upper()
                else:
                    dir_part = ''
                    file_prefix = partial.upper()

                entries = fs.list_directory(dir_part if dir_part else '.')
                matches = []
                for e in entries:
                    if e.name.upper().startswith(file_prefix):
                        if dir_part:
                            matches.append(dir_part + e.name)
                        else:
                            matches.append(e.name + ('\\' if e.is_dir else ''))
                return matches
            except Exception:
                return []

    def _run_editor(self, channel, fs, filename: str) -> int:
        """Run the text editor over the SSH channel."""
        from dospc_sim.editor import TextEditor

        def editor_output(text: str):
            """Send output to the channel."""
            try:
                channel.send(text.encode('utf-8'))
            except Exception:
                pass

        def editor_input() -> str:
            """Read a key from the channel."""
            # Read raw bytes for escape sequences
            buf = b''
            while True:
                try:
                    # Use select for timeout-based reading
                    ready, _, _ = select.select([channel], [], [], 0.1)
                    if not ready:
                        if buf:
                            # Return what we have if buffer not empty
                            return buf.decode('utf-8', errors='ignore')
                        continue

                    data = channel.recv(1)
                    if not data:
                        raise EOFError()
                    buf += data

                    # Check for complete escape sequences
                    if buf.startswith(b'\x1b'):
                        # Escape sequence - read more
                        if len(buf) == 1:
                            # Could be ESC key or start of sequence
                            # Wait for more data (increased timeout for VSCode terminal)
                            ready, _, _ = select.select([channel], [], [], 0.1)
                            if not ready:
                                # No more data, it's just ESC
                                return buf.decode('utf-8', errors='ignore')
                            continue
                        elif len(buf) == 2 and buf[1:2] in b'[O':
                            # CSI or OSC sequence, need more
                            continue
                        elif len(buf) >= 3:
                            # Check for complete sequence
                            # Arrow keys: \x1b[A, \x1b[B, etc.
                            # Home/End: \x1b[H, \x1b[F, \x1bOH, \x1bOF
                            # VT-style: \x1b[1~, \x1b[4~ (Home/End in some terminals)
                            # Page keys: \x1b[5~, \x1b[6~
                            # Delete: \x1b[3~
                            if buf[2:3] in b'ABCDEFHOPQRS':
                                return buf.decode('utf-8', errors='ignore')
                            elif buf[2:3] in b'123456789':
                                # Could be \x1b[1~ etc.
                                if len(buf) >= 4 and buf[3:4] == b'~':
                                    return buf.decode('utf-8', errors='ignore')
                                continue
                            else:
                                return buf.decode('utf-8', errors='ignore')
                    else:
                        # Regular character
                        return buf.decode('utf-8', errors='ignore')

                except Exception as exc:
                    raise EOFError() from exc

        # Create and run the editor
        editor = TextEditor(fs, editor_output, editor_input)
        return editor.run(filename)

    def _cleanup(self):
        """Clean up resources."""
        try:
            if self.transport:
                self.transport.close()
        except Exception:
            pass
        try:
            self.client_socket.close()
        except Exception:
            pass


class SSHServer:
    """SSH Server for DosPC Sim."""

    def __init__(
        self, host: str = '0.0.0.0', port: int = 2222, data_dir: Path = DATA_DIR
    ):
        self.host = host
        self.port = port
        self.data_dir = data_dir
        self.ssh_keys_dir = data_dir / 'ssh_keys'
        self.host_key_file = self.ssh_keys_dir / 'host_rsa_key'
        self.user_manager = UserManager(data_dir)
        self.host_key: RSAKey | None = None
        self.server_socket: socket.socket | None = None
        self.running = False
        self._threads: list = []
        self._lock = threading.Lock()

        self._ensure_directories()
        self._load_or_generate_host_key()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ssh_keys_dir.mkdir(parents=True, exist_ok=True)
        # Secure the SSH keys directory
        os.chmod(self.ssh_keys_dir, 0o700)

    def _load_or_generate_host_key(self) -> None:
        """Load or generate the SSH host key."""
        if self.host_key_file.exists():
            try:
                self.host_key = RSAKey(filename=str(self.host_key_file))
                logger.info(f'Loaded host key from {self.host_key_file}')
            except Exception as e:
                logger.error(f'Failed to load host key: {e}')
                self._generate_host_key()
        else:
            self._generate_host_key()

    def _generate_host_key(self) -> None:
        """Generate a new SSH host key."""
        logger.info('Generating new RSA host key...')
        self.host_key = RSAKey.generate(2048)
        self.host_key.write_private_key_file(str(self.host_key_file))
        os.chmod(self.host_key_file, 0o600)
        logger.info(f'Host key saved to {self.host_key_file}')

    def start(self) -> bool:
        """Start the SSH server."""
        if self.running:
            logger.warning('SSH server is already running')
            return False

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Allow checking for shutdown

            self.running = True
            logger.info(f'SSH server started on {self.host}:{self.port}')

            # Start accept thread
            self._accept_thread = threading.Thread(
                target=self._accept_loop, daemon=True
            )
            self._accept_thread.start()

            return True
        except Exception as e:
            logger.error(f'Failed to start SSH server: {e}')
            return False

    def _accept_loop(self):
        """Accept incoming connections."""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                logger.info(f'New connection from {address[0]}:{address[1]}')

                handler = SSHClientHandler(
                    client_socket, address, self.host_key, self.user_manager
                )
                handler.start()

                with self._lock:
                    self._threads.append(handler)
                    # Clean up finished threads
                    self._threads = [t for t in self._threads if t.is_alive()]

            except TimeoutError:
                continue
            except OSError:
                break
            except Exception as e:
                if self.running:
                    logger.error(f'Error accepting connection: {e}')

    def stop(self):
        """Stop the SSH server."""
        if not self.running:
            return

        logger.info('Stopping SSH server...')
        self.running = False

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        # Wait for threads to finish
        with self._lock:
            for thread in self._threads:
                try:
                    thread.join(timeout=2)
                except Exception:
                    pass

        logger.info('SSH server stopped')

    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.running

    def get_status(self) -> dict:
        """Get server status information."""
        with self._lock:
            active_connections = sum(1 for t in self._threads if t.is_alive())

        return {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'active_connections': active_connections,
            'host_key_fingerprint': self.host_key.get_fingerprint().hex()
            if self.host_key
            else None,
        }

    def create_user(self, username: str, password: str) -> User:
        """Create a new user."""
        return self.user_manager.create_user(username, password)

    def delete_user(self, username: str) -> bool:
        """Delete a user."""
        return self.user_manager.delete_user(username)

    def list_users(self):
        """List all users."""
        return self.user_manager.list_users()
