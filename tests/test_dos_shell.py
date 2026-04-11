"""Tests for DOS shell simulation."""

import pytest
import tempfile
import shutil
from pathlib import Path

from dospc_sim.filesystem import UserFilesystem
from dospc_sim.dos_shell import DOSShell
from dospc_sim.parser import parse_command


class TestDOSShell:
    """Test cases for DOSShell."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path, ignore_errors=True)

    @pytest.fixture
    def shell(self, temp_dir):
        """Create a DOSShell with temp filesystem."""
        user_dir = temp_dir / "testuser"
        user_dir.mkdir()
        fs = UserFilesystem(str(user_dir), "testuser")
        output_capture = []

        def output_callback(text):
            output_capture.append(text)

        shell = DOSShell(fs, "testuser", output_callback)
        shell._output_capture = output_capture
        return shell

    def test_initial_state(self, shell):
        """Test initial shell state."""
        assert shell.username == "testuser"
        assert shell.running is False
        assert shell.last_errorlevel == 0
        assert shell.get_prompt() == "C:\\>"

    def test_cmd_dir_empty(self, shell):
        """Test DIR command on empty directory."""
        shell.cmd_dir([])
        output = "\n".join(shell._output_capture)

        assert "Volume in drive C" in output
        assert "Directory of C:" in output
        assert "bytes free" in output

    def test_cmd_dir_with_files(self, shell):
        """Test DIR command with files."""
        shell.fs.write_file("test.txt", "content")
        shell.fs.make_directory("testdir")

        shell._output_capture.clear()
        shell.cmd_dir([])
        output = "\n".join(shell._output_capture)

        assert "test.txt" in output
        assert "testdir" in output
        assert "<DIR>" in output

    def test_cmd_cd(self, shell):
        """Test CD command."""
        shell.fs.make_directory("subdir")

        result = shell.cmd_cd(["subdir"])
        assert result == 0
        assert shell.get_prompt() == "C:\\subdir>"

    def test_cmd_cd_parent(self, shell):
        """Test CD to parent directory."""
        shell.fs.make_directory("subdir")
        shell.fs.change_directory("subdir")

        result = shell.cmd_cd([".."])
        assert result == 0
        assert shell.get_prompt() == "C:\\>"

    def test_cmd_cd_not_found(self, shell):
        """Test CD to non-existent directory."""
        result = shell.cmd_cd(["nonexistent"])
        assert result == 1

    def test_cmd_md(self, shell):
        """Test MD command."""
        result = shell.cmd_md(["newdir"])
        assert result == 0
        assert shell.fs.dir_exists("newdir")

    def test_cmd_md_no_args(self, shell):
        """Test MD without arguments."""
        result = shell.cmd_md([])
        assert result == 1

    def test_cmd_rd(self, shell):
        """Test RD command."""
        shell.fs.make_directory("emptydir")

        result = shell.cmd_rd(["emptydir"])
        assert result == 0
        assert not shell.fs.dir_exists("emptydir")

    def test_cmd_rd_not_empty(self, shell):
        """Test RD on non-empty directory."""
        shell.fs.make_directory("parent")
        shell.fs.write_file("parent/file.txt", "content")

        result = shell.cmd_rd(["parent"])
        assert result == 1

    def test_cmd_rd_recursive(self, shell):
        """Test RD with /S switch."""
        shell.fs.make_directory("parent/child")
        shell.fs.write_file("parent/file.txt", "content")

        result = shell.cmd_rd(["/S", "parent"])
        assert result == 0
        assert not shell.fs.dir_exists("parent")

    def test_cmd_copy(self, shell):
        """Test COPY command."""
        shell.fs.write_file("source.txt", "content")

        result = shell.cmd_copy(["source.txt", "dest.txt"])
        assert result == 0
        assert shell.fs.file_exists("dest.txt")
        assert shell.fs.read_file("dest.txt") == "content"

    def test_cmd_copy_not_found(self, shell):
        """Test COPY with non-existent source."""
        result = shell.cmd_copy(["nonexistent.txt", "dest.txt"])
        assert result == 1

    def test_cmd_del(self, shell):
        """Test DEL command."""
        shell.fs.write_file("delete_me.txt", "content")

        result = shell.cmd_del(["delete_me.txt"])
        assert result == 0
        assert not shell.fs.file_exists("delete_me.txt")

    def test_cmd_del_wildcard(self, shell):
        """Test DEL with wildcard."""
        shell.fs.write_file("file1.txt", "content")
        shell.fs.write_file("file2.txt", "content")
        shell.fs.write_file("file3.log", "content")

        result = shell.cmd_del(["*.txt"])
        assert result == 0
        assert not shell.fs.file_exists("file1.txt")
        assert not shell.fs.file_exists("file2.txt")
        assert shell.fs.file_exists("file3.log")

    def test_cmd_ren(self, shell):
        """Test REN command."""
        shell.fs.write_file("oldname.txt", "content")

        result = shell.cmd_ren(["oldname.txt", "newname.txt"])
        assert result == 0
        assert not shell.fs.file_exists("oldname.txt")
        assert shell.fs.file_exists("newname.txt")

    def test_cmd_move(self, shell):
        """Test MOVE command."""
        shell.fs.make_directory("dest")
        shell.fs.write_file("source.txt", "content")

        result = shell.cmd_move(["source.txt", "dest"])
        assert result == 0
        assert not shell.fs.file_exists("source.txt")
        assert shell.fs.file_exists("dest/source.txt")

    def test_cmd_type(self, shell):
        """Test TYPE command."""
        shell.fs.write_file("test.txt", "Hello, World!")

        shell._output_capture.clear()
        result = shell.cmd_type(["test.txt"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "Hello, World!" in output

    def test_cmd_type_not_found(self, shell):
        """Test TYPE with non-existent file."""
        result = shell.cmd_type(["nonexistent.txt"])
        assert result == 1

    def test_cmd_echo(self, shell):
        """Test ECHO command."""
        shell._output_capture.clear()
        result = shell.cmd_echo(["Hello,", "World!"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "Hello, World!" in output

    def test_cmd_echo_quoted(self, shell):
        """Test ECHO with quoted text."""
        shell._output_capture.clear()
        result = shell.cmd_echo(['"Hello World"'])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "Hello World" in output

    def test_cmd_cls(self, shell):
        """Test CLS command."""
        shell._output_capture.clear()
        result = shell.cmd_cls([])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "\x1b[2J" in output  # ANSI clear screen

    def test_cmd_ver(self, shell):
        """Test VER command."""
        shell._output_capture.clear()
        result = shell.cmd_ver([])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "DosPC Sim DOS" in output
        assert "Version 1.0" in output

    def test_cmd_help(self, shell):
        """Test HELP command."""
        shell._output_capture.clear()
        result = shell.cmd_help([])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "DIR" in output
        assert "COPY" in output
        assert "HELP" in output

    def test_cmd_help_specific(self, shell):
        """Test HELP for specific command."""
        shell._output_capture.clear()
        result = shell.cmd_help(["DIR"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "directory" in output.lower()

    def test_cmd_exit(self, shell):
        """Test EXIT command."""
        shell.running = True
        result = shell.cmd_exit([])

        assert result == 0
        assert shell.running is False

    def test_cmd_set(self, shell):
        """Test SET command."""
        result = shell.cmd_set(["TESTVAR=value"])
        assert result == 0
        assert shell.environment["TESTVAR"] == "value"

    def test_cmd_set_display(self, shell):
        """Test SET command to display all variables."""
        shell._output_capture.clear()
        result = shell.cmd_set([])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "PATH=" in output
        assert "PROMPT=" in output

    def test_cmd_path(self, shell):
        """Test PATH command."""
        result = shell.cmd_path(["C:\\;C:\\NEW"])
        assert result == 0
        assert shell.environment["PATH"] == "C:\\;C:\\NEW"

    def test_cmd_prompt(self, shell):
        """Test PROMPT command."""
        result = shell.cmd_prompt(["$P$G"])
        assert result == 0
        assert shell.environment["PROMPT"] == "$P$G"

    def test_cmd_date(self, shell):
        """Test DATE command."""
        shell._output_capture.clear()
        result = shell.cmd_date([])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "Current date:" in output

    def test_cmd_time(self, shell):
        """Test TIME command."""
        shell._output_capture.clear()
        result = shell.cmd_time([])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "Current time:" in output

    def test_execute_command_unknown(self, shell):
        """Test executing unknown command."""
        shell._output_capture.clear()
        result = shell.execute_command("UNKNOWN")
        output = "\n".join(shell._output_capture)

        assert result == 1
        assert "Bad command or file name" in output

    def test_execute_command_empty(self, shell):
        """Test executing empty command."""
        result = shell.execute_command("")
        assert result == 0

    def test_execute_command_whitespace(self, shell):
        """Test executing whitespace-only command."""
        result = shell.execute_command("   ")
        assert result == 0

    def test_batch_file_execution(self, shell):
        """Test batch file execution."""
        # Create a batch file
        batch_content = """ECHO Line 1
ECHO Line 2
ECHO Line 3"""
        shell.fs.write_file("test.bat", batch_content)

        # Verify file exists
        assert shell.fs.file_exists("test.bat")

        shell._output_capture.clear()
        # Use "TEST" without extension - the shell will find TEST.BAT
        result = shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "Line 1" in output
        assert "Line 2" in output
        assert "Line 3" in output

    def test_batch_file_with_params(self, shell):
        """Test batch file with parameters."""
        batch_content = """ECHO %0
ECHO %1
ECHO %2"""
        shell.fs.write_file("test.bat", batch_content)

        # Verify file exists
        assert shell.fs.file_exists("test.bat")

        shell._output_capture.clear()
        # Use "TEST" without extension
        result = shell.execute_command("TEST arg1 arg2")
        output = "\n".join(shell._output_capture)

        assert result == 0
        # %0 contains the batch file name (may be uppercase due to case-insensitive matching)
        assert "TEST.BAT" in output.upper()
        assert "arg1" in output
        assert "arg2" in output

    def test_comment_lines(self, shell):
        """Test that comment lines are ignored."""
        result = shell.execute_command(":: This is a comment")
        assert result == 0

        result = shell.execute_command("REM This is also a comment")
        assert result == 0

    # ==================== TREE tests ====================

    def test_cmd_tree_basic(self, shell):
        """Test TREE command with subdirectories."""
        shell.fs.make_directory("DOCS")
        shell.fs.make_directory("GAMES")
        shell.fs.write_file("DOCS/README.TXT", "hello")
        shell.fs.write_file("ROOT.TXT", "root file")

        shell._output_capture.clear()
        result = shell.cmd_tree([])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "DOCS" in output
        assert "GAMES" in output
        assert "ROOT.TXT" not in output

    def test_cmd_tree_with_files(self, shell):
        """Test TREE /F shows files."""
        shell.fs.make_directory("SUB")
        shell.fs.write_file("SUB/FILE.TXT", "hi")

        shell._output_capture.clear()
        result = shell.cmd_tree(["/F"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "SUB" in output
        assert "FILE.TXT" in output

    def test_cmd_tree_nested(self, shell):
        """Test TREE with nested directories."""
        shell.fs.make_directory("A")
        shell.fs.make_directory("A/B")
        shell.fs.make_directory("A/C")

        shell._output_capture.clear()
        result = shell.cmd_tree([])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "A" in output
        assert "B" in output
        assert "C" in output

    def test_cmd_tree_path_not_found(self, shell):
        """Test TREE with non-existent path."""
        result = shell.cmd_tree(["nonexistent"])
        assert result == 1

    # ==================== FIND tests ====================

    def test_cmd_find_basic(self, shell):
        """Test FIND command searching for a string."""
        shell.fs.write_file("test.txt", "hello world\nfoo bar\nhello again")

        shell._output_capture.clear()
        result = shell.cmd_find(["hello", "test.txt"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "hello world" in output
        assert "hello again" in output
        assert "foo bar" not in output

    def test_cmd_find_not_found(self, shell):
        """Test FIND with no matches returns 1."""
        shell.fs.write_file("test.txt", "hello world")

        shell._output_capture.clear()
        result = shell.cmd_find(["xyz", "test.txt"])
        assert result == 1

    def test_cmd_find_case_insensitive(self, shell):
        """Test FIND /I for case-insensitive search."""
        shell.fs.write_file("test.txt", "Hello World")

        shell._output_capture.clear()
        result = shell.cmd_find(["hello", "/I", "test.txt"])
        assert result == 0

    def test_cmd_find_invert(self, shell):
        """Test FIND /V to show non-matching lines."""
        shell.fs.write_file("test.txt", "hello\nworld\nhello again")

        shell._output_capture.clear()
        result = shell.cmd_find(["hello", "/V", "test.txt"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "world" in output
        assert "hello" not in output

    def test_cmd_find_count(self, shell):
        """Test FIND /C to count matching lines."""
        shell.fs.write_file("test.txt", "hello\nworld\nhello again")

        shell._output_capture.clear()
        result = shell.cmd_find(["hello", "/C", "test.txt"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "2" in output

    def test_cmd_find_line_numbers(self, shell):
        """Test FIND /N shows line numbers."""
        shell.fs.write_file("test.txt", "hello\nworld")

        shell._output_capture.clear()
        result = shell.cmd_find(["hello", "/N", "test.txt"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "[1]" in output

    def test_cmd_find_no_args(self, shell):
        """Test FIND with no arguments shows usage."""
        result = shell.cmd_find([])
        assert result == 1

    def test_cmd_find_file_not_found(self, shell):
        """Test FIND with missing file."""
        result = shell.cmd_find(["hello", "missing.txt"])
        assert result == 1

    # ==================== MORE tests ====================

    def test_cmd_more_basic(self, shell):
        """Test MORE displays file content."""
        shell.fs.write_file("long.txt", "line1\nline2\nline3")

        shell._output_capture.clear()
        result = shell.cmd_more(["long.txt"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "line1" in output
        assert "line2" in output
        assert "line3" in output

    def test_cmd_more_no_args(self, shell):
        """Test MORE with no arguments."""
        result = shell.cmd_more([])
        assert result == 1

    def test_cmd_more_file_not_found(self, shell):
        """Test MORE with missing file."""
        result = shell.cmd_more(["missing.txt"])
        assert result == 1

    # ==================== SORT tests ====================

    def test_cmd_sort_basic(self, shell):
        """Test SORT sorts lines alphabetically."""
        shell.fs.write_file("sortme.txt", "cherry\napple\nbanana")

        shell._output_capture.clear()
        result = shell.cmd_sort(["sortme.txt"])

        assert result == 0
        lines = [line for line in shell._output_capture if line.strip()]
        assert lines.index("apple") < lines.index("banana")
        assert lines.index("banana") < lines.index("cherry")

    def test_cmd_sort_reverse(self, shell):
        """Test SORT /R reverses order."""
        shell.fs.write_file("sortme.txt", "apple\ncherry\nbanana")

        shell._output_capture.clear()
        result = shell.cmd_sort(["/R", "sortme.txt"])
        lines = [line for line in shell._output_capture if line.strip()]

        assert result == 0
        assert lines.index("cherry") < lines.index("banana")
        assert lines.index("banana") < lines.index("apple")

    def test_cmd_sort_output_file(self, shell):
        """Test SORT /O writes to output file."""
        shell.fs.write_file("sortme.txt", "cherry\napple\nbanana")

        result = shell.cmd_sort(["sortme.txt", "/O", "sorted.txt"])
        assert result == 0
        assert shell.fs.file_exists("sorted.txt")
        content = shell.fs.read_file("sorted.txt")
        assert content.index("apple") < content.index("banana")
        assert content.index("banana") < content.index("cherry")

    def test_cmd_sort_file_not_found(self, shell):
        """Test SORT with missing file."""
        result = shell.cmd_sort(["missing.txt"])
        assert result == 1

    # ==================== FC tests ====================

    def test_cmd_fc_identical(self, shell):
        """Test FC with identical files."""
        shell.fs.write_file("a.txt", "hello\nworld")
        shell.fs.write_file("b.txt", "hello\nworld")

        shell._output_capture.clear()
        result = shell.cmd_fc(["a.txt", "b.txt"])
        output = "\n".join(shell._output_capture)

        assert result == 0
        assert "no differences encountered" in output

    def test_cmd_fc_different(self, shell):
        """Test FC with different files."""
        shell.fs.write_file("a.txt", "hello\nworld")
        shell.fs.write_file("b.txt", "hello\nearth")

        shell._output_capture.clear()
        result = shell.cmd_fc(["a.txt", "b.txt"])
        output = "\n".join(shell._output_capture)

        assert result == 1
        assert "world" in output
        assert "earth" in output

    def test_cmd_fc_no_args(self, shell):
        """Test FC with no arguments."""
        result = shell.cmd_fc([])
        assert result == 1

    def test_cmd_fc_file_not_found(self, shell):
        """Test FC with missing file."""
        shell.fs.write_file("a.txt", "hello")
        result = shell.cmd_fc(["a.txt", "missing.txt"])
        assert result == 1

    # ==================== Environment Variable Expansion tests ====================

    def test_expand_known_variable(self, shell):
        shell.environment["MYVAR"] = "hello"
        assert shell.expand_variables("%MYVAR%") == "hello"

    def test_expand_case_insensitive(self, shell):
        shell.environment["MYVAR"] = "hello"
        assert shell.expand_variables("%myvar%") == "hello"

    def test_expand_unknown_variable_unchanged(self, shell):
        assert shell.expand_variables("%UNKNOWN%") == "%UNKNOWN%"

    def test_expand_multiple_variables(self, shell):
        shell.environment["A"] = "1"
        shell.environment["B"] = "2"
        assert shell.expand_variables("%A% and %B%") == "1 and 2"

    def test_expand_in_echo_command(self, shell):
        shell.environment["GREETING"] = "Hello"
        shell._output_capture.clear()
        shell.execute_command("ECHO %GREETING% World")
        output = "\n".join(shell._output_capture)
        assert "Hello World" in output

    def test_expand_in_type_command(self, shell):
        shell.environment["MYFILE"] = "test"
        shell.fs.write_file("test.txt", "content")
        shell._output_capture.clear()
        shell.execute_command("TYPE %MYFILE%.txt")
        output = "\n".join(shell._output_capture)
        assert "content" in output

    def test_expand_in_cd_command(self, shell):
        shell.fs.make_directory("MYDIR")
        shell.environment["TARGET"] = "MYDIR"
        shell._output_capture.clear()
        shell.execute_command("CD %TARGET%")
        assert shell.get_prompt() == "C:\\MYDIR>"

    def test_expand_path_variable(self, shell):
        shell._output_capture.clear()
        shell.execute_command("ECHO %PATH%")
        output = "\n".join(shell._output_capture)
        assert "C:\\" in output

    # ==================== Pipe Execution tests ====================

    def test_type_pipe_sort(self, shell):
        shell.fs.write_file("unsorted.txt", "cherry\napple\nbanana")
        shell._output_capture.clear()
        shell.execute_command("TYPE unsorted.txt | SORT")
        output = "\n".join(shell._output_capture)
        apple_idx = output.index("apple")
        banana_idx = output.index("banana")
        cherry_idx = output.index("cherry")
        assert apple_idx < banana_idx < cherry_idx

    def test_type_pipe_find(self, shell):
        shell.fs.write_file("data.txt", "hello world\nfoo bar\nhello again")
        shell._output_capture.clear()
        shell.execute_command("TYPE data.txt | FIND hello")
        output = "\n".join(shell._output_capture)
        assert "hello world" in output
        assert "hello again" in output
        assert "foo bar" not in output

    def test_type_pipe_sort_pipe_find(self, shell):
        shell.fs.write_file("data.txt", "cherry\napple\nbanana")
        shell._output_capture.clear()
        shell.execute_command("TYPE data.txt | SORT | FIND apple")
        output = "\n".join(shell._output_capture)
        assert "apple" in output

    def test_pipe_three_commands(self, shell):
        shell.fs.write_file("data.txt", "zebra\napple\nbanana\navocado")
        shell._output_capture.clear()
        shell.execute_command("TYPE data.txt | SORT | FIND a")
        output = "\n".join(shell._output_capture)
        assert "apple" in output
        assert "avocado" in output

    # ==================== I/O Redirection tests ====================

    def test_echo_redirect_to_file(self, shell):
        shell.execute_command("ECHO Hello World > output.txt")
        assert shell.fs.file_exists("output.txt")
        content = shell.fs.read_file("output.txt")
        assert "Hello World" in content

    def test_dir_redirect_to_file(self, shell):
        shell.fs.write_file("marker.txt", "test")
        shell.execute_command("DIR > listing.txt")
        assert shell.fs.file_exists("listing.txt")

    def test_append_redirect(self, shell):
        shell.execute_command("ECHO Line 1 > log.txt")
        shell.execute_command("ECHO Line 2 >> log.txt")
        content = shell.fs.read_file("log.txt")
        assert "Line 1" in content
        assert "Line 2" in content

    def test_input_redirect_sort(self, shell):
        shell.fs.write_file("data.txt", "cherry\napple\nbanana")
        shell._output_capture.clear()
        shell.execute_command("SORT < data.txt")
        output = "\n".join(shell._output_capture)
        assert "apple" in output
        assert "banana" in output
        assert "cherry" in output

    def test_parser_redirect_write(self):
        r = parse_command("ECHO hello > out.txt")
        assert r is not None
        assert r.stdout_redirect == "out.txt"

    def test_parser_redirect_append(self):
        r = parse_command("ECHO hello >> out.txt")
        assert r is not None
        assert r.append_redirect == "out.txt"

    def test_parser_redirect_input(self):
        r = parse_command("SORT < input.txt")
        assert r is not None
        assert r.stdin_redirect == "input.txt"

    def test_parser_redirect_combined(self):
        r = parse_command("SORT < input.txt > output.txt")
        assert r is not None
        assert r.stdin_redirect == "input.txt"
        assert r.stdout_redirect == "output.txt"

    def test_type_redirect_to_file(self, shell):
        shell.fs.write_file("source.txt", "original content")
        shell.execute_command("TYPE source.txt > copy.txt")
        assert shell.fs.file_exists("copy.txt")
        content = shell.fs.read_file("copy.txt")
        assert "original content" in content

    # ==================== Batch GOTO tests ====================

    def test_goto_forward(self, shell):
        batch = """ECHO Before
GOTO SKIP
ECHO Skipped
:SKIP
ECHO After"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Before" in output
        assert "Skipped" not in output
        assert "After" in output

    def test_goto_backward_loop(self, shell):
        batch = """SET COUNT=0
:LOOP
ECHO Iteration
GOTO END
:END"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Iteration" in output

    def test_goto_nonexistent_label(self, shell):
        batch = """GOTO MISSING
ECHO This runs"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Label not found" in output

    # ==================== Batch IF tests ====================

    def test_if_exist_true(self, shell):
        shell.fs.write_file("exists.txt", "data")
        batch = """IF EXIST exists.txt ECHO Found
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Found" in output
        assert "Done" in output

    def test_if_exist_false(self, shell):
        batch = """IF EXIST missing.txt ECHO Found
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Found" not in output
        assert "Done" in output

    def test_if_not_exist(self, shell):
        batch = """IF NOT EXIST missing.txt ECHO Not Found
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Not Found" in output

    def test_if_errorlevel(self, shell):
        batch = """IF ERRORLEVEL 1 ECHO Failed
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell.last_errorlevel = 1
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Failed" in output

    def test_if_errorlevel_not_met(self, shell):
        batch = """IF ERRORLEVEL 1 ECHO Failed
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell.last_errorlevel = 0
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Failed" not in output
        assert "Done" in output

    def test_if_string_equality(self, shell):
        batch = """IF hello==hello ECHO Match
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Match" in output

    def test_if_string_inequality(self, shell):
        batch = """IF hello==world ECHO Match
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Match" not in output
        assert "Done" in output

    def test_if_goto(self, shell):
        batch = """IF 1==1 GOTO SKIP
ECHO Skipped
:SKIP
ECHO Arrived"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Skipped" not in output
        assert "Arrived" in output

    # ==================== Batch FOR tests ====================

    def test_for_loop_basic(self, shell):
        batch = "FOR %%F IN (a b c) DO ECHO %%F"
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "a" in output
        assert "b" in output
        assert "c" in output

    def test_for_loop_with_file_ops(self, shell):
        shell.fs.write_file("a.txt", "content a")
        shell.fs.write_file("b.txt", "content b")
        batch = "FOR %%F IN (a.txt b.txt) DO TYPE %%F"
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "content a" in output
        assert "content b" in output

    # ==================== Batch CALL tests ====================

    def test_call_batch(self, shell):
        shell.fs.write_file("sub.bat", "ECHO In Subroutine")
        batch = """ECHO Before
CALL SUB
ECHO After"""
        shell.fs.write_file("main.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("MAIN")
        output = "\n".join(shell._output_capture)
        assert "Before" in output
        assert "In Subroutine" in output
        assert "After" in output

    def test_call_with_params(self, shell):
        shell.fs.write_file("greet.bat", "ECHO Hello %1")
        batch = "CALL GREET World"
        shell.fs.write_file("main.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("MAIN")
        output = "\n".join(shell._output_capture)
        assert "Hello World" in output

    # ==================== Batch PAUSE tests ====================

    def test_pause_message(self, shell):
        batch = """ECHO Before
PAUSE
ECHO After"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Before" in output
        assert "Press any key to continue" in output
        assert "After" in output

    # ==================== Batch ECHO ON/OFF tests ====================

    def test_echo_off_does_not_break(self, shell):
        batch = """ECHO OFF
ECHO Still works"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Still works" in output

    # ==================== PROMPT Variable tests ====================

    def test_default_prompt_pg(self, shell):
        prompt = shell.get_prompt()
        assert "C:\\>" in prompt

    def test_prompt_pg(self, shell):
        shell.execute_command("PROMPT $P$G")
        prompt = shell.get_prompt()
        assert "C:\\>" in prompt

    def test_prompt_custom_text(self, shell):
        shell.environment["PROMPT"] = "Hello>"
        prompt = shell.get_prompt()
        assert prompt == "Hello>"

    def test_prompt_dollar_n(self, shell):
        shell.execute_command("PROMPT $N$G")
        prompt = shell.get_prompt()
        assert prompt == "C>"

    def test_prompt_dollar_d(self, shell):
        shell.execute_command("PROMPT $D$G")
        prompt = shell.get_prompt()
        assert ">" in prompt
        assert "/" in prompt

    def test_prompt_dollar_dollar(self, shell):
        shell.execute_command("PROMPT $$test$$")
        prompt = shell.get_prompt()
        assert prompt == "$test$"

    def test_prompt_in_subdirectory(self, shell):
        shell.fs.make_directory("SUB")
        shell.fs.change_directory("SUB")
        shell.execute_command("PROMPT $P$G")
        prompt = shell.get_prompt()
        assert "C:\\SUB>" in prompt

    # ==================== Batch Labels tests ====================

    def test_labels_are_case_insensitive(self, shell):
        batch = """GOTO MyLabel
ECHO Skipped
:MYLABEL
ECHO Found"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Found" in output
        assert "Skipped" not in output

    def test_label_with_underscore(self, shell):
        batch = """GOTO MY_LABEL
ECHO Skipped
:MY_LABEL
ECHO Found"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Found" in output
        assert "Skipped" not in output

    def test_multiple_gotos(self, shell):
        batch = """GOTO SECOND
:FIRST
ECHO First
GOTO END
:SECOND
ECHO Second
GOTO FIRST
:END
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Second" in output
        assert "First" in output
        assert "Done" in output

    # ==================== IF EXIST Directory tests ====================

    def test_if_exist_directory(self, shell):
        shell.fs.make_directory("MYDIR")
        batch = """IF EXIST MYDIR ECHO DirFound
ECHO Done"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "DirFound" in output

    # ==================== Batch Variables in Batch tests ====================

    def test_set_and_use_in_batch(self, shell):
        batch = """SET NAME=World
ECHO Hello %NAME%"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Hello World" in output

    def test_batch_params_with_env_vars(self, shell):
        batch = """ECHO %1
SET FILE=%1
ECHO %FILE%"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST mydata")
        output = "\n".join(shell._output_capture)
        assert "mydata" in output

    # ==================== Combined Batch Features tests ====================

    def test_if_goto_for(self, shell):
        batch = """IF 1==1 GOTO PROCESS
ECHO Skip
:PROCESS
FOR %%I IN (x y z) DO ECHO %%I"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Skip" not in output
        assert "x" in output
        assert "y" in output
        assert "z" in output

    def test_for_with_if(self, shell):
        shell.fs.write_file("a.txt", "content a")
        shell.fs.write_file("b.txt", "content b")
        batch = """FOR %%F IN (a.txt b.txt) DO IF EXIST %%F ECHO Found %%F"""
        shell.fs.write_file("test.bat", batch)
        shell._output_capture.clear()
        shell.execute_command("TEST")
        output = "\n".join(shell._output_capture)
        assert "Found a.txt" in output
        assert "Found b.txt" in output
