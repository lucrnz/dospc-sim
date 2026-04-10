"""Tests for DOS shell simulation."""

import os
import pytest
import tempfile
import shutil
from pathlib import Path

from dospc_sim.filesystem import UserFilesystem
from dospc_sim.dos_shell import DOSShell


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
