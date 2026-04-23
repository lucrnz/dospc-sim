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
        # Create filesystem
        fs = UserFilesystem(user.home_dir, user.username)

        def output_callback(text: str):
            """Send output to the client."""
            try:
                channel.send(text + '\r\n')
            except Exception:
                pass

        # Create DOS shell
        self.shell = DOSShell(fs, user.username, output_callback)

        input_line_buffer = []

        def input_callback():
            try:
                data = channel.recv(1024)
                if data:
                    input_line_buffer.append(
                        data.decode('utf-8', errors='ignore').strip()
                    )
            except Exception:
                pass

        self.shell._input_callback = input_callback

        # Set up the editor handler
        self.shell.set_editor_handler(
            lambda filename: self._run_editor(channel, fs, filename)
        )

        self.shell.run()

        # Line editor state
        command_buffer = ''
        cursor_pos = 0
        history: list[str] = []
        history_index = len(history)

        def refresh_line():
            nonlocal command_buffer, cursor_pos
            prompt = self.shell.get_prompt()
            # Move to start of prompt, clear to end, redraw
            channel.send(f'\r\x1b[K{prompt}{command_buffer}')
            if cursor_pos < len(command_buffer):
                channel.send(f'\x1b[{len(command_buffer) - cursor_pos}D')

        prompt = self.shell.get_prompt()
        channel.send(prompt)

        while self.shell.running and not channel.closed:
            try:
                data = channel.recv(1024)
                if not data:
                    break

                i = 0
                raw = data
                while i < len(raw):
                    b = raw[i]

                    if b == 0x1B:  # ESC sequence
                        seq = bytes([b])
                        i += 1
                        while i < len(raw) and len(seq) < 8:
                            seq += bytes([raw[i]])
                            i += 1
                            # Check if this is a complete ANSI sequence
                            if len(seq) == 2 and seq[1] in (0x4F, 0x5B):
                                continue
                            if (len(seq) >= 3 and chr(seq[-1]).isalpha()) or seq[
                                -1
                            ] == ord('~'):
                                break
                        else:
                            # Need more data - wait briefly
                            try:
                                ready, _, _ = select.select([channel], [], [], 0.05)
                                if ready:
                                    more = channel.recv(16)
                                    raw = raw[:i] + more + raw[i:]
                                    continue
                            except Exception:
                                pass

                        # Parse the escape sequence
                        seq_str = seq.decode('utf-8', errors='ignore')

                        if seq_str == '\x1b[A':  # Up arrow
                            if history and history_index > 0:
                                history_index -= 1
                                command_buffer = history[history_index]
                                cursor_pos = len(command_buffer)
                                refresh_line()
                        elif seq_str == '\x1b[B':  # Down arrow
                            if history_index < len(history) - 1:
                                history_index += 1
                                command_buffer = history[history_index]
                            else:
                                history_index = len(history)
                                command_buffer = ''
                            cursor_pos = len(command_buffer)
                            refresh_line()
                        elif seq_str == '\x1b[C':  # Right arrow
                            if cursor_pos < len(command_buffer):
                                cursor_pos += 1
                                channel.send('\x1b[C')
                        elif seq_str == '\x1b[D':  # Left arrow
                            if cursor_pos > 0:
                                cursor_pos -= 1
                                channel.send('\x1b[D')
                        elif seq_str in ('\x1b[H', '\x1b[1~', '\x1bOH'):  # Home
                            if cursor_pos > 0:
                                channel.send(f'\x1b[{cursor_pos}D')
                                cursor_pos = 0
                        elif seq_str in ('\x1b[F', '\x1b[4~', '\x1bOF'):  # End
                            if cursor_pos < len(command_buffer):
                                channel.send(
                                    f'\x1b[{len(command_buffer) - cursor_pos}C'
                                )
                                cursor_pos = len(command_buffer)
                        elif seq_str in ('\x1b[3~',) and cursor_pos < len(
                            command_buffer
                        ):
                            command_buffer = (
                                command_buffer[:cursor_pos]
                                + command_buffer[cursor_pos + 1 :]
                            )
                            channel.send(command_buffer[cursor_pos:] + ' ')
                            channel.send(
                                f'\x1b[{len(command_buffer) - cursor_pos + 1}D'
                            )
                        continue

                    if b == 0x0D or b == 0x0A:  # Enter
                        i += 1
                        # Skip LF after CR
                        if i < len(raw) and raw[i] == 0x0A:
                            i += 1
                        channel.send('\r\n')
                        if command_buffer.strip():
                            cmd = command_buffer.strip()
                            logger.info(f'User {user.username} executed: {cmd}')
                            self.shell.execute_command(command_buffer.strip())
                            history.append(command_buffer.strip())
                            history_index = len(history)
                        command_buffer = ''
                        cursor_pos = 0
                        if self.shell.running:
                            prompt = self.shell.get_prompt()
                            channel.send(prompt)
                        continue

                    if b == 0x7F or b == 0x08:  # Backspace
                        i += 1
                        if cursor_pos > 0:
                            command_buffer = (
                                command_buffer[: cursor_pos - 1]
                                + command_buffer[cursor_pos:]
                            )
                            cursor_pos -= 1
                            channel.send('\b' + command_buffer[cursor_pos:] + ' ')
                            move_back = len(command_buffer) - cursor_pos + 1
                            channel.send(f'\x1b[{move_back}D')
                        continue

                    if b == 0x03:  # Ctrl+C
                        i += 1
                        channel.send('^C\r\n')
                        command_buffer = ''
                        cursor_pos = 0
                        history_index = len(history)
                        if self.shell.running:
                            prompt = self.shell.get_prompt()
                            channel.send(prompt)
                        continue

                    if b == 0x04:  # Ctrl+D
                        self.shell.running = False
                        break

                    if b == 0x09:  # Tab - autocomplete
                        i += 1
                        completions = self._tab_complete(
                            fs, self.shell, command_buffer, cursor_pos
                        )
                        if len(completions) == 1:
                            # Replace the last word with the completion
                            prefix = command_buffer[:cursor_pos]
                            last_space = prefix.rfind(' ')
                            before = prefix[: last_space + 1] if last_space >= 0 else ''
                            new_word = completions[0]
                            after = command_buffer[cursor_pos:]
                            command_buffer = before + new_word + after
                            cursor_pos = len(before) + len(new_word)
                            refresh_line()
                        elif len(completions) > 1:
                            channel.send('\r\n')
                            # Display completions in columns
                            max_len = max(len(c) for c in completions) + 2
                            cols = max(1, 80 // max_len)
                            for j in range(0, len(completions), cols):
                                row = completions[j : j + cols]
                                channel.send(
                                    '  '.join(f'{c:<{max_len}}' for c in row) + '\r\n'
                                )
                            refresh_line()
                        continue

                    if b >= 0x20 and b < 0x7F:  # Printable char
                        ch = chr(b)
                        i += 1
                        command_buffer = (
                            command_buffer[:cursor_pos]
                            + ch
                            + command_buffer[cursor_pos:]
                        )
                        cursor_pos += 1
                        # Echo the char and redraw after cursor
                        channel.send(ch + command_buffer[cursor_pos:])
                        if len(command_buffer) - cursor_pos > 0:
                            channel.send(f'\x1b[{len(command_buffer) - cursor_pos}D')
                        continue

                    i += 1  # skip unknown bytes

            except Exception as e:
                logger.error(f'Error in shell for {user.username}: {e}')
                break

        logger.info(f'Session ended for user {user.username} from {self.address[0]}')
        channel.send('\r\nGoodbye!\r\n')

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
