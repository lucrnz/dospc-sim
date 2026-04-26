"""Tests for the text editor module."""

import shutil
import tempfile
from unittest.mock import Mock

import pytest

from dospc_sim.editor import TextEditor, run_editor
from dospc_sim.filesystem import UserFilesystem


class TestTextEditor:
    """Tests for the TextEditor class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def filesystem(self, temp_dir):
        """Create a UserFilesystem for testing."""
        return UserFilesystem(temp_dir, 'testuser')

    @pytest.fixture
    def mock_output(self):
        """Create a mock output callback."""
        return Mock()

    @pytest.fixture
    def mock_input_sequence(self):
        """Create a mock input function that returns a sequence of keys."""

        def make_input(keys):
            key_iter = iter(keys)

            def mock_input():
                try:
                    return next(key_iter)
                except StopIteration as exc:
                    raise EOFError() from exc

            return mock_input

        return make_input

    def test_editor_initialization(self, filesystem, mock_output, mock_input_sequence):
        """Test that the editor initializes correctly."""
        input_fn = mock_input_sequence(['\x03'])  # Ctrl+C to quit
        editor = TextEditor(filesystem, mock_output, input_fn)

        assert editor.fs == filesystem
        assert editor.lines == []
        assert editor.filename is None
        assert editor.modified is False
        assert editor.cursor_row == 0
        assert editor.cursor_col == 0

    def test_open_new_file(self, filesystem, mock_output, mock_input_sequence):
        """Test opening a new file."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        result = editor.open_file('newfile.txt')

        assert result is True
        assert editor.filename == 'newfile.txt'
        assert editor.lines == ['']
        assert editor.modified is False
        assert 'New file' in editor.status_message

    def test_open_existing_file(self, filesystem, mock_output, mock_input_sequence):
        """Test opening an existing file."""
        # Create a file first
        filesystem.write_file('test.txt', 'Line 1\nLine 2\nLine 3')

        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        result = editor.open_file('test.txt')

        assert result is True
        assert editor.filename == 'test.txt'
        assert editor.lines == ['Line 1', 'Line 2', 'Line 3']
        assert editor.modified is False
        assert 'Opened' in editor.status_message

    def test_save_file(self, filesystem, mock_output, mock_input_sequence):
        """Test saving a file."""
        editor = TextEditor(filesystem, mock_output, lambda: '\x03')

        editor.open_file('test.txt')
        editor.lines = ['hello']
        editor.modified = True
        result = editor.save_file()

        # Verify file was saved
        assert result is True
        assert editor.modified is False
        content = filesystem.read_file('test.txt')
        assert 'hello' in content

    def test_insert_character(self, filesystem, mock_output, mock_input_sequence):
        """Test inserting a character."""
        input_fn = mock_input_sequence(['a', '\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('test.txt')
        editor._insert_char('a')

        assert editor.lines == ['a']
        assert editor.modified is True
        assert editor.cursor_col == 1

    def test_insert_newline(self, filesystem, mock_output, mock_input_sequence):
        """Test inserting a newline."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('test.txt')
        editor.lines = ['hello world']
        editor.cursor_col = 5
        editor._insert_newline()

        assert editor.lines == ['hello', ' world']
        assert editor.cursor_row == 1
        assert editor.cursor_col == 0
        assert editor.modified is True

    def test_backspace(self, filesystem, mock_output, mock_input_sequence):
        """Test backspace functionality."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('test.txt')
        editor.lines = ['hello']
        editor.cursor_col = 5
        editor._backspace()

        assert editor.lines == ['hell']
        assert editor.cursor_col == 4
        assert editor.modified is True

    def test_backspace_join_lines(self, filesystem, mock_output, mock_input_sequence):
        """Test backspace at start of line joins with previous line."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('test.txt')
        editor.lines = ['hello', 'world']
        editor.cursor_row = 1
        editor.cursor_col = 0
        editor._backspace()

        assert editor.lines == ['helloworld']
        assert editor.cursor_row == 0
        assert editor.cursor_col == 5

    def test_delete_char(self, filesystem, mock_output, mock_input_sequence):
        """Test delete character functionality."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('test.txt')
        editor.lines = ['hello']
        editor.cursor_col = 0
        editor._delete_char()

        assert editor.lines == ['ello']
        assert editor.modified is True

    def test_cursor_movement(self, filesystem, mock_output, mock_input_sequence):
        """Test cursor movement."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('test.txt')
        editor.lines = ['hello', 'world']
        editor.cursor_row = 0
        editor.cursor_col = 0

        # Move right
        editor._move_cursor_right()
        assert editor.cursor_col == 1

        # Move down
        editor._move_cursor_down()
        assert editor.cursor_row == 1
        assert editor.cursor_col == 1  # Clamped to line length

        # Move left
        editor._move_cursor_left()
        assert editor.cursor_col == 0

        # Move up
        editor._move_cursor_up()
        assert editor.cursor_row == 0

    def test_page_up_down(self, filesystem, mock_output, mock_input_sequence):
        """Test page up and page down."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('test.txt')
        editor.lines = [f'line {i}' for i in range(50)]
        editor.cursor_row = 25

        editor._page_up()
        assert editor.cursor_row == 5  # 25 - 20

        editor._page_down()
        assert editor.cursor_row == 25  # 5 + 20

    def test_save_new_file(self, filesystem, mock_output, mock_input_sequence):
        """Test saving a new file."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('newfile.txt')
        editor.lines = ['test content', 'second line']
        result = editor.save_file()

        assert result is True
        assert editor.modified is False
        assert 'Saved' in editor.status_message

        # Verify content
        content = filesystem.read_file('newfile.txt')
        assert content == 'test content\nsecond line'

    def test_save_as_different_name(self, filesystem, mock_output, mock_input_sequence):
        """Test save as with a different filename."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)

        editor.open_file('original.txt')
        editor.lines = ['content']
        result = editor.save_file('newname.txt')

        assert result is True
        assert editor.filename == 'newname.txt'
        assert filesystem.file_exists('newname.txt')

    def test_quit_unsaved_warns_first(
        self, filesystem, mock_output, mock_input_sequence
    ):
        """Test first quit with unsaved changes warns but does not exit."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)
        editor.running = True

        editor.open_file('test.txt')
        editor.lines = ['modified']
        editor.modified = True

        editor._quit()
        assert editor.running is True
        assert 'Unsaved changes' in editor.status_message

    def test_quit_unsaved_exits_on_second(
        self, filesystem, mock_output, mock_input_sequence
    ):
        """Test second quit with unsaved changes exits."""
        input_fn = mock_input_sequence(['\x03'])
        editor = TextEditor(filesystem, mock_output, input_fn)
        editor.running = True

        editor.open_file('test.txt')
        editor.lines = ['modified']
        editor.modified = True

        editor._quit()
        assert editor.running is True
        editor._quit()
        assert editor.running is False


class TestEditorIntegration:
    """Integration tests for the editor."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    def test_run_editor_function(self, temp_dir):
        """Test the run_editor convenience function."""
        filesystem = UserFilesystem(temp_dir, 'testuser')
        outputs = []
        inputs = ['\x03']  # Quit immediately
        input_iter = iter(inputs)

        def output_cb(text):
            outputs.append(text)

        def input_cb():
            try:
                return next(input_iter)
            except StopIteration as exc:
                raise EOFError() from exc

        result = run_editor(filesystem, 'test.txt', output_cb, input_cb)

        assert result == 0  # No modifications
        assert len(outputs) > 0  # Should have drawn screen


class TestEscapeSequences:
    """Tests for ANSI escape sequence handling."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def editor(self, temp_dir):
        """Create an editor instance."""
        filesystem = UserFilesystem(temp_dir, 'testuser')
        mock_output = Mock()

        def mock_input():
            return '\x03'  # Ctrl+C

        return TextEditor(filesystem, mock_output, mock_input)

    def test_arrow_up(self, editor):
        """Test up arrow escape sequence."""
        editor.lines = ['line1', 'line2']
        editor.cursor_row = 1
        editor.cursor_col = 0

        editor._handle_escape_sequence('\x1b[A')

        assert editor.cursor_row == 0

    def test_arrow_down(self, editor):
        """Test down arrow escape sequence."""
        editor.lines = ['line1', 'line2']
        editor.cursor_row = 0
        editor.cursor_col = 0

        editor._handle_escape_sequence('\x1b[B')

        assert editor.cursor_row == 1

    def test_arrow_right(self, editor):
        """Test right arrow escape sequence."""
        editor.lines = ['test']
        editor.cursor_col = 0

        editor._handle_escape_sequence('\x1b[C')

        assert editor.cursor_col == 1

    def test_arrow_left(self, editor):
        """Test left arrow escape sequence."""
        editor.lines = ['test']
        editor.cursor_col = 2

        editor._handle_escape_sequence('\x1b[D')

        assert editor.cursor_col == 1

    def test_home_key(self, editor):
        """Test home key escape sequence."""
        editor.lines = ['test']
        editor.cursor_col = 3

        editor._handle_escape_sequence('\x1b[H')

        assert editor.cursor_col == 0

    def test_home_key_vt_style(self, editor):
        """Test home key VT-style escape sequence (VSCode terminal)."""
        editor.lines = ['test']
        editor.cursor_col = 3

        editor._handle_escape_sequence('\x1b[1~')

        assert editor.cursor_col == 0

    def test_home_key_application(self, editor):
        """Test home key application mode escape sequence (VSCode terminal)."""
        editor.lines = ['test']
        editor.cursor_col = 3

        editor._handle_escape_sequence('\x1bOH')

        assert editor.cursor_col == 0

    def test_end_key(self, editor):
        """Test end key escape sequence."""
        editor.lines = ['test']
        editor.cursor_col = 0

        editor._handle_escape_sequence('\x1b[F')

        assert editor.cursor_col == 4

    def test_end_key_vt_style(self, editor):
        """Test end key VT-style escape sequence (VSCode terminal)."""
        editor.lines = ['test']
        editor.cursor_col = 0

        editor._handle_escape_sequence('\x1b[4~')

        assert editor.cursor_col == 4

    def test_end_key_application(self, editor):
        """Test end key application mode escape sequence (VSCode terminal)."""
        editor.lines = ['test']
        editor.cursor_col = 0

        editor._handle_escape_sequence('\x1bOF')

        assert editor.cursor_col == 4

    def test_delete_key(self, editor):
        """Test delete key escape sequence."""
        editor.lines = ['test']
        editor.cursor_col = 0

        editor._handle_escape_sequence('\x1b[3~')

        assert editor.lines == ['est']

    def test_page_up(self, editor):
        """Test page up escape sequence."""
        editor.lines = [f'line{i}' for i in range(30)]
        editor.cursor_row = 25

        editor._handle_escape_sequence('\x1b[5~')

        assert editor.cursor_row == 5

    def test_page_down(self, editor):
        """Test page down escape sequence."""
        editor.lines = [f'line{i}' for i in range(30)]
        editor.cursor_row = 5

        editor._handle_escape_sequence('\x1b[6~')

        assert editor.cursor_row == 25


class TestKeyBindings:
    """Tests for Ctrl key bindings."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def editor(self, temp_dir):
        """Create an editor instance."""
        filesystem = UserFilesystem(temp_dir, 'testuser')
        mock_output = Mock()

        def mock_input():
            return '\x03'  # Ctrl+C

        return TextEditor(filesystem, mock_output, mock_input)

    def test_ctrl_q_quits(self, editor):
        """Test Ctrl+Q quits the editor."""
        editor.running = True
        editor._handle_key('\x11')  # Ctrl+Q
        assert editor.running is False

    def test_ctrl_c_quits(self, editor):
        """Test Ctrl+C quits the editor."""
        editor.running = True
        editor._handle_key('\x03')  # Ctrl+C
        assert editor.running is False

    def test_ctrl_s_saves(self, editor):
        """Test Ctrl+S saves the file."""
        editor.open_file('test.txt')
        editor.lines = ['test content']
        editor.modified = True

        editor._handle_key('\x13')  # Ctrl+S

        assert editor.modified is False
        assert 'Saved' in editor.status_message

    def test_backspace_code_8(self, editor):
        """Test backspace with code 8."""
        editor.lines = ['hello']
        editor.cursor_col = 5

        editor._handle_key('\x08')  # Backspace

        assert editor.lines == ['hell']
        assert editor.cursor_col == 4

    def test_backspace_code_127(self, editor):
        """Test backspace with code 127 (DEL)."""
        editor.lines = ['hello']
        editor.cursor_col = 5

        editor._handle_key('\x7f')  # DEL (127)

        assert editor.lines == ['hell']
        assert editor.cursor_col == 4

    def test_tab_inserts_spaces(self, editor):
        """Test Tab inserts 4 spaces."""
        editor.lines = ['']
        editor.cursor_col = 0

        editor._handle_key('\t')  # Tab

        assert editor.lines == ['    ']
        assert editor.cursor_col == 4

    def test_enter_creates_newline(self, editor):
        """Test Enter creates a new line."""
        editor.lines = ['hello world']
        editor.cursor_col = 5

        editor._handle_key('\r')  # Enter

        assert editor.lines == ['hello', ' world']
        assert editor.cursor_row == 1
        assert editor.cursor_col == 0

    def test_escape_shows_help(self, editor):
        """Test Escape shows help."""
        # This is hard to test directly since it calls get_input()
        # Just verify the handler doesn't crash
        editor._handle_key('\x1b')  # Escape - will wait for input
        # The test passes if no exception is raised
