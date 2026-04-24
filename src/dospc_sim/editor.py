"""DOS-style text editor for DosPC Sim SSH sessions.

A simple text editor similar to DOS edit.com that works over SSH connections.
Supports basic file opening, editing, and saving functionality.
"""

from dospc_sim.filesystem import UserFilesystem


class EditorBuffer:
    """Text buffer and cursor state for editor operations."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.filename: str | None = None
        self.modified = False
        self.cursor_row = 0
        self.cursor_col = 0
        self.status_message = ''

    def initialize_new(self, filename: str | None = None, status: str = '') -> None:
        self.lines = ['']
        self.filename = filename
        self.modified = False
        self.cursor_row = 0
        self.cursor_col = 0
        self.status_message = status


class EditorRenderer:
    """Terminal rendering concerns for the text editor."""

    def __init__(self, output_callback) -> None:
        self.output = output_callback
        self._alternate_screen = False

    def _out(self, text: str) -> None:
        text = text.replace('\r\n', '\n').replace('\n', '\r\n')
        self.output(text)

    def init_terminal(self) -> None:
        self._out('\x1b[?1049h')
        self._alternate_screen = True
        self._out('\x1b[2J\x1b[H')

    def reset_terminal(self) -> None:
        self._out('\x1b[?25h')
        if self._alternate_screen:
            self._out('\x1b[?1049l')
            self._alternate_screen = False
        self._out('\r\n')

    def draw_prompt(self, prompt: str) -> None:
        self._out(f'\x1b[{24};1H\x1b[K{prompt}')

    def draw_screen(self, buffer: EditorBuffer) -> None:
        screen_lines = []
        screen_lines.append('\x1b[2J\x1b[H')
        title = 'DOSPC SIM EDIT'
        filename_display = buffer.filename if buffer.filename else 'Untitled'
        modified_flag = ' *' if buffer.modified else ''
        title_bar = f' {title} - {filename_display}{modified_flag}'
        title_bar = title_bar.ljust(79)[:79]
        screen_lines.append(f'\x1b[7m{title_bar}\x1b[0m')

        visible_lines = 21
        start_row = max(0, buffer.cursor_row - 10)
        for i in range(visible_lines):
            row = start_row + i
            if row < len(buffer.lines):
                line = buffer.lines[row]
                line_num = f'{row + 1:4d} '
                display_line = line[:73]
                screen_lines.append(f'{line_num}{display_line}')
            else:
                screen_lines.append('~')

        status = f' {buffer.status_message}'
        status = status.ljust(79)[:79]
        screen_lines.append(f'\x1b[7m{status}\x1b[0m')

        self._out('\n'.join(screen_lines))
        cursor_screen_row = buffer.cursor_row - start_row + 3
        cursor_screen_col = buffer.cursor_col + 6
        self._out(f'\x1b[{cursor_screen_row};{cursor_screen_col}H')
        self._out('\x1b[?25h')


class TextEditor:
    """Simple DOS-style text editor for SSH sessions."""

    def __init__(self, filesystem: UserFilesystem, output_callback, input_callback):
        self.fs = filesystem
        self.output = output_callback
        self.get_input = input_callback
        self.buffer = EditorBuffer()
        self.renderer = EditorRenderer(output_callback)
        self.running = False

    @property
    def lines(self) -> list[str]:
        return self.buffer.lines

    @lines.setter
    def lines(self, value: list[str]) -> None:
        self.buffer.lines = value

    @property
    def filename(self) -> str | None:
        return self.buffer.filename

    @filename.setter
    def filename(self, value: str | None) -> None:
        self.buffer.filename = value

    @property
    def modified(self) -> bool:
        return self.buffer.modified

    @modified.setter
    def modified(self, value: bool) -> None:
        self.buffer.modified = value

    @property
    def cursor_row(self) -> int:
        return self.buffer.cursor_row

    @cursor_row.setter
    def cursor_row(self, value: int) -> None:
        self.buffer.cursor_row = value

    @property
    def cursor_col(self) -> int:
        return self.buffer.cursor_col

    @cursor_col.setter
    def cursor_col(self, value: int) -> None:
        self.buffer.cursor_col = value

    @property
    def status_message(self) -> str:
        return self.buffer.status_message

    @status_message.setter
    def status_message(self, value: str) -> None:
        self.buffer.status_message = value

    def _out(self, text: str) -> None:
        """Output text with proper CRLF line endings for terminal compatibility."""
        self.renderer._out(text)

    def _init_terminal(self) -> None:
        """Initialize terminal for full-screen editing."""
        self.renderer.init_terminal()

    def _reset_terminal(self) -> None:
        """Reset terminal to normal state."""
        self.renderer.reset_terminal()

    def run(self, filename: str | None = None) -> int:
        """Run the editor, optionally opening a file."""
        self.running = True

        # Initialize terminal
        self._init_terminal()

        try:
            if filename:
                self.open_file(filename)
            else:
                self.buffer.initialize_new()

            self._draw_screen()

            while self.running:
                try:
                    key = self.get_input()
                    if key:
                        self._handle_key(key)
                except EOFError:
                    break
                except KeyboardInterrupt:
                    break
        finally:
            # Always reset terminal on exit
            self._reset_terminal()

        return 0 if not self.modified else 1

    def open_file(self, filename: str) -> bool:
        """Open a file for editing."""
        try:
            if self.fs.file_exists(filename):
                content = self.fs.read_file(filename)
                self.lines = content.split('\n')
                # Remove trailing empty line if file ends with newline
                if self.lines and self.lines[-1] == '':
                    self.lines = self.lines[:-1]
                self.filename = filename
                self.modified = False
                self.cursor_row = 0
                self.cursor_col = 0
                self.status_message = f'Opened {filename}'
                return True
            else:
                # New file
                self.buffer.initialize_new(filename, f'New file: {filename}')
                return True
        except Exception as e:
            self.status_message = f'Error: {e!s}'
            self.buffer.initialize_new(filename, self.status_message)
            return False

    def save_file(self, filename: str | None = None) -> bool:
        """Save the current file."""
        if filename:
            self.filename = filename

        if not self.filename:
            self.status_message = 'No filename specified'
            return False

        try:
            content = '\n'.join(self.lines)
            self.fs.write_file(self.filename, content)
            self.modified = False
            self.status_message = f'Saved {self.filename}'
            return True
        except Exception as e:
            self.status_message = f'Error saving: {e!s}'
            return False

    def _handle_key(self, key: str) -> None:
        """Handle a single keypress."""
        if key.startswith('\x1b['):
            # ANSI escape sequence (arrow keys, etc.)
            self._handle_escape_sequence(key)
            return

        if len(key) == 1:
            code = ord(key)

            # Ctrl key combinations (codes 0-31)
            if code == 0x03 or code == 0x11:  # Ctrl+C / Ctrl+Q - quit
                self._quit()
            elif code == 0x13:  # Ctrl+S - save
                self.save_file()
                self._draw_screen()
            elif code == 0x0F:  # Ctrl+O - open file
                self._prompt_open()
            elif code == 0x01:  # Ctrl+A - save as
                self._prompt_save_as()
            elif code == 0x08:  # Backspace (also Ctrl+H)
                self._backspace()
            # Regular printable characters
            elif code >= 32 and code < 127:
                self._insert_char(key)
            # Special keys
            elif code == 0x0D or code == 0x0A:  # Enter (\r or \n)
                self._insert_newline()
            elif code == 0x1B:  # Escape
                self._show_help()
            elif code == 0x7F:  # DEL (127) - backspace on some terminals
                self._backspace()
            elif code == 0x09:  # Tab
                self._insert_char('    ')

    def _handle_escape_sequence(self, seq: str) -> None:
        """Handle ANSI escape sequences."""
        # Arrow keys
        if seq == '\x1b[A':  # Up arrow
            self._move_cursor_up()
        elif seq == '\x1b[B':  # Down arrow
            self._move_cursor_down()
        elif seq == '\x1b[C':  # Right arrow
            self._move_cursor_right()
        elif seq == '\x1b[D':  # Left arrow
            self._move_cursor_left()
        # Home key - multiple variants for different terminals
        elif seq in ('\x1b[H', '\x1b[1~', '\x1bOH'):
            self.cursor_col = 0
            self._draw_screen()
        # End key - multiple variants for different terminals
        elif seq in ('\x1b[F', '\x1b[4~', '\x1bOF'):
            if self.cursor_row < len(self.lines):
                self.cursor_col = len(self.lines[self.cursor_row])
            self._draw_screen()
        # Insert key
        elif seq == '\x1b[2~':
            pass  # Insert mode not implemented
        # Delete key
        elif seq == '\x1b[3~':
            self._delete_char()
        # Page Up
        elif seq == '\x1b[5~':
            self._page_up()
        # Page Down
        elif seq == '\x1b[6~':
            self._page_down()

    def _insert_char(self, char: str) -> None:
        """Insert a character at cursor position."""
        if self.cursor_row >= len(self.lines):
            self.lines.append('')

        line = self.lines[self.cursor_row]
        self.lines[self.cursor_row] = (
            line[: self.cursor_col] + char + line[self.cursor_col :]
        )
        self.cursor_col += len(char)
        self.modified = True
        self._draw_screen()

    def _insert_newline(self) -> None:
        """Insert a new line at cursor position."""
        if self.cursor_row >= len(self.lines):
            self.lines.append('')
        else:
            line = self.lines[self.cursor_row]
            self.lines[self.cursor_row] = line[: self.cursor_col]
            self.lines.insert(self.cursor_row + 1, line[self.cursor_col :])

        self.cursor_row += 1
        self.cursor_col = 0
        self.modified = True
        self._draw_screen()

    def _backspace(self) -> None:
        """Handle backspace key."""
        if self.cursor_col > 0:
            line = self.lines[self.cursor_row]
            self.lines[self.cursor_row] = (
                line[: self.cursor_col - 1] + line[self.cursor_col :]
            )
            self.cursor_col -= 1
            self.modified = True
        elif self.cursor_row > 0:
            # Join with previous line
            self.cursor_col = len(self.lines[self.cursor_row - 1])
            self.lines[self.cursor_row - 1] += self.lines[self.cursor_row]
            self.lines.pop(self.cursor_row)
            self.cursor_row -= 1
            self.modified = True
        self._draw_screen()

    def _delete_char(self) -> None:
        """Delete character at cursor position."""
        if self.cursor_row < len(self.lines):
            line = self.lines[self.cursor_row]
            if self.cursor_col < len(line):
                self.lines[self.cursor_row] = (
                    line[: self.cursor_col] + line[self.cursor_col + 1 :]
                )
                self.modified = True
            elif self.cursor_row < len(self.lines) - 1:
                # Join with next line
                self.lines[self.cursor_row] += self.lines[self.cursor_row + 1]
                self.lines.pop(self.cursor_row + 1)
                self.modified = True
        self._draw_screen()

    def _move_cursor_up(self) -> None:
        """Move cursor up one line."""
        if self.cursor_row > 0:
            self.cursor_row -= 1
            if self.cursor_row < len(self.lines):
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))
            else:
                self.cursor_col = 0
        self._draw_screen()

    def _move_cursor_down(self) -> None:
        """Move cursor down one line."""
        if self.cursor_row < len(self.lines) - 1:
            self.cursor_row += 1
            if self.cursor_row < len(self.lines):
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))
            else:
                self.cursor_col = 0
        self._draw_screen()

    def _move_cursor_left(self) -> None:
        """Move cursor left one character."""
        if self.cursor_col > 0:
            self.cursor_col -= 1
        elif self.cursor_row > 0:
            self.cursor_row -= 1
            self.cursor_col = (
                len(self.lines[self.cursor_row])
                if self.cursor_row < len(self.lines)
                else 0
            )
        self._draw_screen()

    def _move_cursor_right(self) -> None:
        """Move cursor right one character."""
        if self.cursor_row < len(self.lines):
            if self.cursor_col < len(self.lines[self.cursor_row]):
                self.cursor_col += 1
            elif self.cursor_row < len(self.lines) - 1:
                self.cursor_row += 1
                self.cursor_col = 0
        self._draw_screen()

    def _page_up(self) -> None:
        """Move up one page."""
        self.cursor_row = max(0, self.cursor_row - 20)
        if self.cursor_row < len(self.lines):
            self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))
        self._draw_screen()

    def _page_down(self) -> None:
        """Move down one page."""
        self.cursor_row = min(len(self.lines) - 1, self.cursor_row + 20)
        if self.cursor_row < len(self.lines):
            self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_row]))
        self._draw_screen()

    def _quit(self) -> None:
        """Quit the editor."""
        if self.modified:
            self.status_message = (
                'Unsaved changes! Press Ctrl+Q again to quit without saving'
            )
            self._draw_screen()
            # Simple debounce - just quit on next request
            self.running = False
        else:
            self.running = False

    def _prompt_open(self) -> None:
        """Prompt for filename to open."""
        self._draw_prompt('Open file: ')
        filename = self.get_input()
        if filename:
            self.open_file(filename.strip())
        self._draw_screen()

    def _prompt_save_as(self) -> None:
        """Prompt for filename to save as."""
        self._draw_prompt('Save as: ')
        filename = self.get_input()
        if filename:
            self.save_file(filename.strip())
        self._draw_screen()

    def _draw_prompt(self, prompt: str) -> None:
        """Draw a prompt at the bottom of screen."""
        self.renderer.draw_prompt(prompt)

    def _show_help(self) -> None:
        """Show help screen."""
        # Use ASCII art for maximum compatibility
        help_text = """
+----------------------------------------------------------------+
|                         EDIT HELP                              |
+----------------------------------------------------------------+
|  Navigation:                                                   |
|    Arrow Keys    - Move cursor                                 |
|    Home/End      - Beginning/End of line                       |
|    PgUp/PgDn     - Page up/down                                |
|                                                                |
|  Editing:                                                      |
|    Typing        - Insert characters                           |
|    Enter         - New line                                    |
|    Backspace     - Delete character before cursor              |
|    Delete        - Delete character at cursor                  |
|    Tab           - Insert 4 spaces                             |
|                                                                |
|  File Operations:                                              |
|    Ctrl+S        - Save file                                   |
|    Ctrl+O        - Open file                                   |
|    Ctrl+A        - Save As (new filename)                      |
|    Ctrl+Q        - Quit editor                                 |
|                                                                |
|  Press any key to continue...                                  |
+----------------------------------------------------------------+
"""
        self._out(help_text)
        # Wait for any key
        self.get_input()
        self._draw_screen()

    def _draw_screen(self) -> None:
        """Redraw the entire screen."""
        self.renderer.draw_screen(self.buffer)


def run_editor(
    filesystem: UserFilesystem, filename: str | None, output_callback, input_callback
) -> int:
    """Run the editor as a command."""
    editor = TextEditor(filesystem, output_callback, input_callback)
    return editor.run(filename)
