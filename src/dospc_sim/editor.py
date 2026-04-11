"""DOS-style text editor for DosPC Sim SSH sessions.

A simple text editor similar to DOS edit.com that works over SSH connections.
Supports basic file opening, editing, and saving functionality.
"""

from dospc_sim.filesystem import UserFilesystem


class TextEditor:
    """Simple DOS-style text editor for SSH sessions."""

    def __init__(self, filesystem: UserFilesystem, output_callback, input_callback):
        self.fs = filesystem
        self.output = output_callback
        self.get_input = input_callback
        self.lines: list[str] = []
        self.filename: str | None = None
        self.modified = False
        self.cursor_row = 0
        self.cursor_col = 0
        self.running = False
        self.status_message = ""
        self._alternate_screen = False

    def _out(self, text: str) -> None:
        """Output text with proper CRLF line endings for terminal compatibility."""
        # Convert lone \n to \r\n for proper terminal rendering
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        self.output(text)

    def _init_terminal(self) -> None:
        """Initialize terminal for full-screen editing."""
        # Switch to alternate screen buffer
        self._out("\x1b[?1049h")
        self._alternate_screen = True
        # Clear screen and hide cursor
        self._out("\x1b[2J\x1b[H")
        self._out("\x1b[?25l")  # Hide cursor during redraw

    def _reset_terminal(self) -> None:
        """Reset terminal to normal state."""
        # Show cursor
        self._out("\x1b[?25h")
        # Switch back to main screen buffer
        if self._alternate_screen:
            self._out("\x1b[?1049l")
            self._alternate_screen = False
        # Ensure we start on a fresh line
        self._out("\r\n")

    def run(self, filename: str | None = None) -> int:
        """Run the editor, optionally opening a file."""
        self.running = True

        # Initialize terminal
        self._init_terminal()

        try:
            if filename:
                self.open_file(filename)
            else:
                self.lines = [""]
                self.filename = None
                self.modified = False

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
                self.lines = content.split("\n")
                # Remove trailing empty line if file ends with newline
                if self.lines and self.lines[-1] == "":
                    self.lines = self.lines[:-1]
                self.filename = filename
                self.modified = False
                self.cursor_row = 0
                self.cursor_col = 0
                self.status_message = f"Opened {filename}"
                return True
            else:
                # New file
                self.lines = [""]
                self.filename = filename
                self.modified = False
                self.cursor_row = 0
                self.cursor_col = 0
                self.status_message = f"New file: {filename}"
                return True
        except Exception as e:
            self.status_message = f"Error: {e!s}"
            self.lines = [""]
            self.filename = filename
            return False

    def save_file(self, filename: str | None = None) -> bool:
        """Save the current file."""
        if filename:
            self.filename = filename

        if not self.filename:
            self.status_message = "No filename specified"
            return False

        try:
            content = "\n".join(self.lines)
            self.fs.write_file(self.filename, content)
            self.modified = False
            self.status_message = f"Saved {self.filename}"
            return True
        except Exception as e:
            self.status_message = f"Error saving: {e!s}"
            return False

    def _handle_key(self, key: str) -> None:
        """Handle a single keypress."""
        if len(key) == 1:
            # Regular character
            if ord(key) >= 32 and ord(key) < 127:
                self._insert_char(key)
            elif key == "\r" or key == "\n":
                self._insert_newline()
            elif ord(key) == 27:  # Escape
                self._show_help()
            elif ord(key) == 8 or ord(key) == 127:  # Backspace
                self._backspace()
            elif ord(key) == 9:  # Tab
                self._insert_char("    ")
        elif key.startswith("\x1b["):
            # ANSI escape sequence (arrow keys, etc.)
            self._handle_escape_sequence(key)
        elif key == "\x11" or key == "\x03":  # Ctrl+Q
            self._quit()
        elif key == "\x13":  # Ctrl+S
            self.save_file()
            self._draw_screen()
        elif key == "\x0f":  # Ctrl+O (Open)
            self._prompt_open()
        elif key == "\x01":  # Ctrl+A (Save As)
            self._prompt_save_as()
        elif key == "\x08":  # Ctrl+H (Help)
            self._show_help()
        elif key == "\x7f":  # Delete
            self._delete_char()

    def _handle_escape_sequence(self, seq: str) -> None:
        """Handle ANSI escape sequences."""
        if seq == "\x1b[A":  # Up arrow
            self._move_cursor_up()
        elif seq == "\x1b[B":  # Down arrow
            self._move_cursor_down()
        elif seq == "\x1b[C":  # Right arrow
            self._move_cursor_right()
        elif seq == "\x1b[D":  # Left arrow
            self._move_cursor_left()
        elif seq == "\x1b[H":  # Home
            self.cursor_col = 0
            self._draw_screen()
        elif seq == "\x1b[F":  # End
            if self.cursor_row < len(self.lines):
                self.cursor_col = len(self.lines[self.cursor_row])
            self._draw_screen()
        elif seq == "\x1b[3~":  # Delete key
            self._delete_char()
        elif seq == "\x1b[5~":  # Page Up
            self._page_up()
        elif seq == "\x1b[6~":  # Page Down
            self._page_down()

    def _insert_char(self, char: str) -> None:
        """Insert a character at cursor position."""
        if self.cursor_row >= len(self.lines):
            self.lines.append("")

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
            self.lines.append("")
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
                "Unsaved changes! Press Ctrl+Q again to quit without saving"
            )
            self._draw_screen()
            # Simple debounce - just quit on next request
            self.running = False
        else:
            self.running = False

    def _prompt_open(self) -> None:
        """Prompt for filename to open."""
        self._draw_prompt("Open file: ")
        filename = self.get_input()
        if filename:
            self.open_file(filename.strip())
        self._draw_screen()

    def _prompt_save_as(self) -> None:
        """Prompt for filename to save as."""
        self._draw_prompt("Save as: ")
        filename = self.get_input()
        if filename:
            self.save_file(filename.strip())
        self._draw_screen()

    def _draw_prompt(self, prompt: str) -> None:
        """Draw a prompt at the bottom of screen."""
        self._out(f"\x1b[{24};1H\x1b[K{prompt}")

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
        # Build screen buffer for atomic output
        screen_lines = []

        # Move to home position (no clear - we're in alternate buffer)
        screen_lines.append("\x1b[H")

        # Draw title bar with inverse video
        title = "DOSPC SIM EDIT"
        filename_display = self.filename if self.filename else "Untitled"
        modified_flag = " *" if self.modified else ""
        title_bar = f" {title} - {filename_display}{modified_flag}"
        title_bar = title_bar.ljust(79)[:79]
        screen_lines.append(f"\x1b[7m{title_bar}\x1b[0m")

        # Draw text area (lines 2-22, 21 lines total)
        visible_lines = 21
        start_row = max(0, self.cursor_row - 10)

        for i in range(visible_lines):
            row = start_row + i
            if row < len(self.lines):
                line = self.lines[row]
                # Show line number and content
                line_num = f"{row + 1:4d} "
                display_line = line[:73]
                screen_lines.append(f"{line_num}{display_line}")
            else:
                screen_lines.append("~")

        # Draw status bar with inverse video
        status = f" {self.status_message}"
        status = status.ljust(79)[:79]
        screen_lines.append(f"\x1b[7m{status}\x1b[0m")

        # Join all lines and output atomically
        screen_content = "\n".join(screen_lines)
        self._out(screen_content)

        # Position cursor (separate to ensure it's after screen content)
        cursor_screen_row = (
            self.cursor_row - start_row + 2
        )  # +2 for title bar (1-indexed)
        cursor_screen_col = self.cursor_col + 6  # +6 for line number (1-indexed)
        self._out(f"\x1b[{cursor_screen_row};{cursor_screen_col}H")


def run_editor(
    filesystem: UserFilesystem, filename: str | None, output_callback, input_callback
) -> int:
    """Run the editor as a command."""
    editor = TextEditor(filesystem, output_callback, input_callback)
    return editor.run(filename)
