"""Command behavior tests for DOS shell."""

from dospc_sim.shell_commands import get_shell_command_names


class TestDOSShellCommands:
    def test_initial_state(self, shell):
        """Test initial shell state."""
        assert shell.username == 'testuser'
        assert shell.running is False
        assert shell.last_errorlevel == 0
        assert shell.get_prompt() == 'C:\\>'

    def test_cmd_dir_empty(self, shell):
        """Test DIR command on empty directory."""
        shell.cmd_dir([])
        output = '\n'.join(shell._output_capture)

        assert 'Volume in drive C' in output
        assert 'Directory of C:' in output
        assert 'bytes free' in output

    def test_cmd_dir_with_files(self, shell):
        """Test DIR command with files."""
        shell.fs.write_file('test.txt', 'content')
        shell.fs.make_directory('testdir')

        shell._output_capture.clear()
        shell.cmd_dir([])
        output = '\n'.join(shell._output_capture)

        assert 'test.txt' in output
        assert 'testdir' in output
        assert '<DIR>' in output

    def test_cmd_dir_wildcard(self, shell):
        """Test DIR with wildcard pattern filters listing."""
        shell.fs.write_file('file1.txt', 'aaa')
        shell.fs.write_file('file2.txt', 'bbb')
        shell.fs.write_file('file3.log', 'ccc')
        shell._output_capture.clear()
        shell.cmd_dir(['*.txt'])
        output = '\n'.join(shell._output_capture)
        assert 'file1.txt' in output
        assert 'file2.txt' in output
        assert 'file3.log' not in output

    def test_cmd_dir_wildcard_question_mark(self, shell):
        """Test DIR with ? wildcard."""
        shell.fs.write_file('a1.dat', 'x')
        shell.fs.write_file('b2.dat', 'x')
        shell.fs.write_file('cc.dat', 'x')
        shell._output_capture.clear()
        shell.cmd_dir(['??.dat'])
        output = '\n'.join(shell._output_capture)
        assert 'a1.dat' in output
        assert 'b2.dat' in output
        assert 'cc.dat' in output

    def test_cmd_dir_no_wildcard_unchanged(self, shell):
        """Test that DIR without wildcards still works as before."""
        shell.fs.write_file('readme.txt', 'hello')
        shell._output_capture.clear()
        shell.cmd_dir([])
        output = '\n'.join(shell._output_capture)
        assert 'readme.txt' in output

    def test_cmd_dir_wildcard_with_forward_slash_path(self, shell):
        """Test DIR wildcard supports forward slash path separators."""
        shell.fs.make_directory('sub')
        shell.fs.write_file('sub/file1.txt', 'aaa')
        shell.fs.write_file('sub/file2.log', 'bbb')
        shell._output_capture.clear()
        shell.cmd_dir(['sub/*.txt'])
        output = '\n'.join(shell._output_capture)
        assert 'file1.txt' in output
        assert 'file2.log' not in output

    def test_cmd_dir_header_shows_listed_path(self, shell):
        """DIR header must show the listed directory, not cwd (bug 8)."""
        shell.fs.make_directory('subdir')
        shell.fs.write_file('subdir/file.txt', 'data')
        shell._output_capture.clear()
        shell.cmd_dir(['subdir'])
        output = '\n'.join(shell._output_capture)
        assert 'Directory of C:\\subdir' in output

    def test_cmd_cd(self, shell):
        """Test CD command."""
        shell.fs.make_directory('subdir')

        result = shell.cmd_cd(['subdir'])
        assert result == 0
        assert shell.get_prompt() == 'C:\\subdir>'

    def test_cmd_cd_parent(self, shell):
        """Test CD to parent directory."""
        shell.fs.make_directory('subdir')
        shell.fs.change_directory('subdir')

        result = shell.cmd_cd(['..'])
        assert result == 0
        assert shell.get_prompt() == 'C:\\>'

    def test_cmd_cd_not_found(self, shell):
        """Test CD to non-existent directory."""
        result = shell.cmd_cd(['nonexistent'])
        assert result == 1

    def test_cmd_md(self, shell):
        """Test MD command."""
        result = shell.cmd_md(['newdir'])
        assert result == 0
        assert shell.fs.dir_exists('newdir')

    def test_cmd_md_no_args(self, shell):
        """Test MD without arguments."""
        result = shell.cmd_md([])
        assert result == 1

    def test_cmd_rd(self, shell):
        """Test RD command."""
        shell.fs.make_directory('emptydir')

        result = shell.cmd_rd(['emptydir'])
        assert result == 0
        assert not shell.fs.dir_exists('emptydir')

    def test_cmd_rd_not_empty(self, shell):
        """Test RD on non-empty directory."""
        shell.fs.make_directory('parent')
        shell.fs.write_file('parent/file.txt', 'content')

        result = shell.cmd_rd(['parent'])
        assert result == 1

    def test_cmd_rd_recursive(self, shell):
        """Test RD with /S switch."""
        shell.fs.make_directory('parent/child')
        shell.fs.write_file('parent/file.txt', 'content')

        shell._input_callback = lambda: 'Y'
        shell._output_capture.clear()
        result = shell.cmd_rd(['/S', 'parent'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert not shell.fs.dir_exists('parent')
        assert 'Are you sure (Y/N)?' in output

    def test_cmd_rd_recursive_denied(self, shell):
        """Test RD with /S switch denied by user."""
        shell.fs.make_directory('parent/child')
        shell.fs.write_file('parent/file.txt', 'content')

        shell._input_callback = lambda: 'N'
        shell._output_capture.clear()
        result = shell.cmd_rd(['/S', 'parent'])

        assert result == 0
        assert shell.fs.dir_exists('parent')

    def test_cmd_rd_recursive_quiet(self, shell):
        """Test RD with /S /Q suppresses confirmation prompt text."""
        shell.fs.make_directory('parent/child')
        shell.fs.write_file('parent/file.txt', 'content')

        shell._output_capture.clear()
        result = shell.cmd_rd(['/S', '/Q', 'parent'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert not shell.fs.dir_exists('parent')
        assert 'Are you sure (Y/N)?' not in output

    def test_cmd_copy(self, shell):
        """Test COPY command."""
        shell.fs.write_file('source.txt', 'content')

        result = shell.cmd_copy(['source.txt', 'dest.txt'])
        assert result == 0
        assert shell.fs.file_exists('dest.txt')
        assert shell.fs.read_file('dest.txt') == 'content'

    def test_cmd_copy_not_found(self, shell):
        """Test COPY with non-existent source."""
        result = shell.cmd_copy(['nonexistent.txt', 'dest.txt'])
        assert result == 1

    def test_cmd_copy_wildcard(self, shell):
        """Test COPY with wildcard copies multiple files."""
        shell.fs.write_file('doc1.txt', 'one')
        shell.fs.write_file('doc2.txt', 'two')
        shell.fs.write_file('image.png', 'img')
        shell.fs.make_directory('backup')
        shell._output_capture.clear()
        result = shell.cmd_copy(['*.txt', 'backup'])
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert '2 file(s) copied' in output
        assert shell.fs.file_exists('backup/doc1.txt')
        assert shell.fs.file_exists('backup/doc2.txt')
        assert not shell.fs.file_exists('backup/image.png')

    def test_cmd_copy_wildcard_no_match(self, shell):
        """Test COPY with wildcard that matches nothing."""
        shell.fs.write_file('file.log', 'data')
        shell._output_capture.clear()
        result = shell.cmd_copy(['*.xyz', 'somewhere'])
        assert result == 1

    def test_cmd_copy_wildcard_requires_existing_directory_for_multiple_files(
        self, shell
    ):
        """Test COPY wildcard fails when destination is not an existing directory."""
        shell.fs.write_file('doc1.txt', 'one')
        shell.fs.write_file('doc2.txt', 'two')
        shell._output_capture.clear()
        result = shell.cmd_copy(['*.txt', 'backup'])
        output = '\n'.join(shell._output_capture)
        assert result == 1
        assert 'The system cannot find the path specified.' in output
        assert not shell.fs.file_exists('backup')

    def test_cmd_copy_wildcard_surfaces_destination_errors(self, shell):
        """Test COPY wildcard does not swallow destination errors."""
        shell.fs.write_file('doc1.txt', 'one')
        shell._output_capture.clear()
        result = shell.cmd_copy(['*.txt', '..'])
        output = '\n'.join(shell._output_capture)
        assert result == 1
        assert 'The system cannot find the path specified.' in output

    def test_cmd_copy_wildcard_with_forward_slash_path(self, shell):
        """Test COPY wildcard supports forward slash path separators."""
        shell.fs.make_directory('sub')
        shell.fs.write_file('sub/doc1.txt', 'one')
        shell.fs.make_directory('backup')
        shell._output_capture.clear()
        result = shell.cmd_copy(['sub/*.txt', 'backup'])
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert '1 file(s) copied' in output
        assert shell.fs.file_exists('backup/doc1.txt')

    def test_cmd_del(self, shell):
        """Test DEL command."""
        shell.fs.write_file('delete_me.txt', 'content')

        result = shell.cmd_del(['delete_me.txt'])
        assert result == 0
        assert not shell.fs.file_exists('delete_me.txt')

    def test_cmd_del_wildcard(self, shell):
        """Test DEL with wildcard."""
        shell.fs.write_file('file1.txt', 'content')
        shell.fs.write_file('file2.txt', 'content')
        shell.fs.write_file('file3.log', 'content')

        result = shell.cmd_del(['*.txt'])
        assert result == 0
        assert not shell.fs.file_exists('file1.txt')
        assert not shell.fs.file_exists('file2.txt')
        assert shell.fs.file_exists('file3.log')

    def test_cmd_del_wildcard_with_directory(self, shell):
        """DEL with directory prefix must delete from that directory (bug 5)."""
        shell.fs.make_directory('subdir')
        shell.fs.write_file('subdir/a.txt', 'a')
        shell.fs.write_file('subdir/b.txt', 'b')
        shell.fs.write_file('subdir/c.log', 'c')

        result = shell.cmd_del(['subdir\\*.txt'])
        assert result == 0
        assert not shell.fs.file_exists('subdir/a.txt')
        assert not shell.fs.file_exists('subdir/b.txt')
        assert shell.fs.file_exists('subdir/c.log')

    def test_cmd_ren(self, shell):
        """Test REN command."""
        shell.fs.write_file('oldname.txt', 'content')

        result = shell.cmd_ren(['oldname.txt', 'newname.txt'])
        assert result == 0
        assert not shell.fs.file_exists('oldname.txt')
        assert shell.fs.file_exists('newname.txt')

    def test_cmd_move(self, shell):
        """Test MOVE command."""
        shell.fs.make_directory('dest')
        shell.fs.write_file('source.txt', 'content')

        result = shell.cmd_move(['source.txt', 'dest'])
        assert result == 0
        assert not shell.fs.file_exists('source.txt')
        assert shell.fs.file_exists('dest/source.txt')

    def test_cmd_type(self, shell):
        """Test TYPE command."""
        shell.fs.write_file('test.txt', 'Hello, World!')

        shell._output_capture.clear()
        result = shell.cmd_type(['test.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'Hello, World!' in output

    def test_cmd_type_not_found(self, shell):
        """Test TYPE with non-existent file."""
        result = shell.cmd_type(['nonexistent.txt'])
        assert result == 1

    def test_cmd_echo(self, shell):
        """Test ECHO command."""
        shell._output_capture.clear()
        result = shell.cmd_echo(['Hello,', 'World!'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'Hello, World!' in output

    def test_cmd_echo_quoted(self, shell):
        """Test ECHO with quoted text."""
        shell._output_capture.clear()
        result = shell.cmd_echo(['"Hello World"'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'Hello World' in output

    def test_cmd_cls(self, shell):
        """Test CLS command."""
        shell._output_capture.clear()
        result = shell.cmd_cls([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert '\x1b[2J' in output  # ANSI clear screen

    def test_cmd_ver(self, shell):
        """Test VER command."""
        shell._output_capture.clear()
        result = shell.cmd_ver([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'DosPC Sim DOS' in output
        assert 'Version 1.0' in output

    def test_cmd_help(self, shell):
        """Test HELP command."""
        shell._output_capture.clear()
        result = shell.cmd_help([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'DIR' in output
        assert 'COPY' in output
        assert 'HELP' in output

    def test_cmd_help_specific(self, shell):
        """Test HELP for specific command."""
        shell._output_capture.clear()
        result = shell.cmd_help(['DIR'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'directory' in output.lower()

    def test_help_uses_shared_command_names(self, shell):
        """Test HELP command list is sourced from shared command metadata."""
        shell._output_capture.clear()
        result = shell.cmd_help([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        for command in get_shell_command_names():
            assert command in output

    def test_get_available_commands_matches_shared_metadata(self, shell):
        """Test shell command listing helper returns shared command names."""
        assert shell.get_available_commands() == get_shell_command_names()

    def test_cmd_exit(self, shell):
        """Test EXIT command."""
        shell.running = True
        result = shell.cmd_exit([])

        assert result == 0
        assert shell.running is False

    def test_cmd_set(self, shell):
        """Test SET command."""
        result = shell.cmd_set(['TESTVAR=value'])
        assert result == 0
        assert shell.environment['TESTVAR'] == 'value'

    def test_cmd_set_display(self, shell):
        """Test SET command to display all variables."""
        shell._output_capture.clear()
        result = shell.cmd_set([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'PATH=' in output
        assert 'PROMPT=' in output

    def test_cmd_set_undefined_variable(self, shell):
        """SET with undefined variable must print error message (bug 9)."""
        shell._output_capture.clear()
        result = shell.cmd_set(['NONEXISTENT'])
        output = '\n'.join(shell._output_capture)
        assert result == 1
        assert 'not defined' in output

    def test_cmd_path(self, shell):
        """Test PATH command."""
        result = shell.cmd_path(['C:\\;C:\\NEW'])
        assert result == 0
        assert shell.environment['PATH'] == 'C:\\;C:\\NEW'

    def test_cmd_prompt(self, shell):
        """Test PROMPT command."""
        result = shell.cmd_prompt(['$P$G'])
        assert result == 0
        assert shell.environment['PROMPT'] == '$P$G'

    def test_cmd_date(self, shell):
        """Test DATE command."""
        shell._output_capture.clear()
        result = shell.cmd_date([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'Current date:' in output

    def test_cmd_time(self, shell):
        """Test TIME command."""
        shell._output_capture.clear()
        result = shell.cmd_time([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'Current time:' in output

    def test_execute_command_unknown(self, shell):
        """Test executing unknown command."""
        shell._output_capture.clear()
        result = shell.execute_command('UNKNOWN')
        output = '\n'.join(shell._output_capture)

        assert result == 1
        assert 'Bad command or file name' in output

    def test_execute_command_empty(self, shell):
        """Test executing empty command."""
        result = shell.execute_command('')
        assert result == 0

    def test_execute_command_whitespace(self, shell):
        """Test executing whitespace-only command."""
        result = shell.execute_command('   ')
        assert result == 0

    def test_batch_file_execution(self, shell):
        """Test batch file execution."""
        # Create a batch file
        batch_content = """ECHO Line 1
ECHO Line 2
ECHO Line 3"""
        shell.fs.write_file('test.bat', batch_content)

        # Verify file exists
        assert shell.fs.file_exists('test.bat')

        shell._output_capture.clear()
        # Use "TEST" without extension - the shell will find TEST.BAT
        result = shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'Line 1' in output
        assert 'Line 2' in output
        assert 'Line 3' in output

    def test_batch_file_with_params(self, shell):
        """Test batch file with parameters."""
        batch_content = """ECHO %0
ECHO %1
ECHO %2"""
        shell.fs.write_file('test.bat', batch_content)

        # Verify file exists
        assert shell.fs.file_exists('test.bat')

        shell._output_capture.clear()
        # Use "TEST" without extension
        result = shell.execute_command('TEST arg1 arg2')
        output = '\n'.join(shell._output_capture)

        assert result == 0
        # %0 contains the batch file name
        # (may be uppercase due to case-insensitive matching)
        assert 'TEST.BAT' in output.upper()
        assert 'arg1' in output
        assert 'arg2' in output

    def test_batch_file_direct_bat_invocation(self, shell):
        """Test that TEST.BAT can be invoked directly with the extension."""
        batch_content = """ECHO Direct BAT"""
        shell.fs.write_file('test.bat', batch_content)
        shell._output_capture.clear()
        result = shell.execute_command('TEST.BAT')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'Direct BAT' in output

    def test_batch_file_direct_cmd_invocation(self, shell):
        """Test that SCRIPT.CMD can be invoked directly with the extension."""
        batch_content = """ECHO Direct CMD"""
        shell.fs.write_file('script.cmd', batch_content)
        shell._output_capture.clear()
        result = shell.execute_command('SCRIPT.CMD')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'Direct CMD' in output

    def test_batch_file_basename_still_works(self, shell):
        """Test that basename invocation still works after direct extension support."""
        batch_content = """ECHO Basename OK"""
        shell.fs.write_file('mytest.bat', batch_content)
        shell._output_capture.clear()
        result = shell.execute_command('MYTEST')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'Basename OK' in output

    def test_comment_lines(self, shell):
        """Test that comment lines are ignored."""
        result = shell.execute_command(':: This is a comment')
        assert result == 0

        result = shell.execute_command('REM This is also a comment')
        assert result == 0

    # ==================== TREE tests ====================

    def test_cmd_tree_basic(self, shell):
        """Test TREE command with subdirectories."""
        shell.fs.make_directory('DOCS')
        shell.fs.make_directory('GAMES')
        shell.fs.write_file('DOCS/README.TXT', 'hello')
        shell.fs.write_file('ROOT.TXT', 'root file')

        shell._output_capture.clear()
        result = shell.cmd_tree([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'DOCS' in output
        assert 'GAMES' in output
        assert 'ROOT.TXT' not in output

    def test_cmd_tree_with_files(self, shell):
        """Test TREE /F shows files."""
        shell.fs.make_directory('SUB')
        shell.fs.write_file('SUB/FILE.TXT', 'hi')

        shell._output_capture.clear()
        result = shell.cmd_tree(['/F'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'SUB' in output
        assert 'FILE.TXT' in output

    def test_cmd_tree_nested(self, shell):
        """Test TREE with nested directories."""
        shell.fs.make_directory('A')
        shell.fs.make_directory('A/B')
        shell.fs.make_directory('A/C')

        shell._output_capture.clear()
        result = shell.cmd_tree([])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'A' in output
        assert 'B' in output
        assert 'C' in output

    def test_cmd_tree_path_not_found(self, shell):
        """Test TREE with non-existent path."""
        result = shell.cmd_tree(['nonexistent'])
        assert result == 1

    # ==================== FIND tests ====================

    def test_cmd_find_basic(self, shell):
        """Test FIND command searching for a string."""
        shell.fs.write_file('test.txt', 'hello world\nfoo bar\nhello again')

        shell._output_capture.clear()
        result = shell.cmd_find(['hello', 'test.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'hello world' in output
        assert 'hello again' in output
        assert 'foo bar' not in output

    def test_cmd_find_not_found(self, shell):
        """Test FIND with no matches returns 1."""
        shell.fs.write_file('test.txt', 'hello world')

        shell._output_capture.clear()
        result = shell.cmd_find(['xyz', 'test.txt'])
        assert result == 1

    def test_cmd_find_case_insensitive(self, shell):
        """Test FIND /I for case-insensitive search."""
        shell.fs.write_file('test.txt', 'Hello World')

        shell._output_capture.clear()
        result = shell.cmd_find(['hello', '/I', 'test.txt'])
        assert result == 0

    def test_cmd_find_invert(self, shell):
        """Test FIND /V to show non-matching lines."""
        shell.fs.write_file('test.txt', 'hello\nworld\nhello again')

        shell._output_capture.clear()
        result = shell.cmd_find(['hello', '/V', 'test.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'world' in output
        assert 'hello' not in output

    def test_cmd_find_count(self, shell):
        """Test FIND /C to count matching lines."""
        shell.fs.write_file('test.txt', 'hello\nworld\nhello again')

        shell._output_capture.clear()
        result = shell.cmd_find(['hello', '/C', 'test.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert '2' in output

    def test_cmd_find_line_numbers(self, shell):
        """Test FIND /N shows line numbers."""
        shell.fs.write_file('test.txt', 'hello\nworld')

        shell._output_capture.clear()
        result = shell.cmd_find(['hello', '/N', 'test.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert '[1]' in output

    def test_cmd_find_no_args(self, shell):
        """Test FIND with no arguments shows usage."""
        result = shell.cmd_find([])
        assert result == 1

    def test_cmd_find_file_not_found(self, shell):
        """Test FIND with missing file."""
        result = shell.cmd_find(['hello', 'missing.txt'])
        assert result == 1

    # ==================== MORE tests ====================

    def test_cmd_more_basic(self, shell):
        """Test MORE displays file content."""
        shell.fs.write_file('long.txt', 'line1\nline2\nline3')

        shell._output_capture.clear()
        result = shell.cmd_more(['long.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'line1' in output
        assert 'line2' in output
        assert 'line3' in output

    def test_cmd_more_no_args(self, shell):
        """Test MORE with no arguments."""
        result = shell.cmd_more([])
        assert result == 1

    def test_cmd_more_file_not_found(self, shell):
        """Test MORE with missing file."""
        result = shell.cmd_more(['missing.txt'])
        assert result == 1

    # ==================== SORT tests ====================

    def test_cmd_sort_basic(self, shell):
        """Test SORT sorts lines alphabetically."""
        shell.fs.write_file('sortme.txt', 'cherry\napple\nbanana')

        shell._output_capture.clear()
        result = shell.cmd_sort(['sortme.txt'])

        assert result == 0
        lines = [line for line in shell._output_capture if line.strip()]
        assert lines.index('apple') < lines.index('banana')
        assert lines.index('banana') < lines.index('cherry')

    def test_cmd_sort_reverse(self, shell):
        """Test SORT /R reverses order."""
        shell.fs.write_file('sortme.txt', 'apple\ncherry\nbanana')

        shell._output_capture.clear()
        result = shell.cmd_sort(['/R', 'sortme.txt'])
        lines = [line for line in shell._output_capture if line.strip()]

        assert result == 0
        assert lines.index('cherry') < lines.index('banana')
        assert lines.index('banana') < lines.index('apple')

    def test_cmd_sort_output_file(self, shell):
        """Test SORT /O writes to output file."""
        shell.fs.write_file('sortme.txt', 'cherry\napple\nbanana')

        result = shell.cmd_sort(['sortme.txt', '/O', 'sorted.txt'])
        assert result == 0
        assert shell.fs.file_exists('sorted.txt')
        content = shell.fs.read_file('sorted.txt')
        assert content.index('apple') < content.index('banana')
        assert content.index('banana') < content.index('cherry')

    def test_cmd_sort_file_not_found(self, shell):
        """Test SORT with missing file."""
        result = shell.cmd_sort(['missing.txt'])
        assert result == 1

    # ==================== FC tests ====================

    def test_cmd_fc_identical(self, shell):
        """Test FC with identical files."""
        shell.fs.write_file('a.txt', 'hello\nworld')
        shell.fs.write_file('b.txt', 'hello\nworld')

        shell._output_capture.clear()
        result = shell.cmd_fc(['a.txt', 'b.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 0
        assert 'no differences encountered' in output

    def test_cmd_fc_different(self, shell):
        """Test FC with different files."""
        shell.fs.write_file('a.txt', 'hello\nworld')
        shell.fs.write_file('b.txt', 'hello\nearth')

        shell._output_capture.clear()
        result = shell.cmd_fc(['a.txt', 'b.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 1
        assert 'world' in output
        assert 'earth' in output

    def test_cmd_fc_numbers_switch(self, shell):
        """Test FC /N includes line numbers for differences."""
        shell.fs.write_file('a.txt', 'hello\nworld')
        shell.fs.write_file('b.txt', 'hello\nearth')

        shell._output_capture.clear()
        result = shell.cmd_fc(['/N', 'a.txt', 'b.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 1
        assert '2: world' in output
        assert '2: earth' in output

    def test_cmd_fc_without_numbers_switch(self, shell):
        """Test FC without /N keeps original output format."""
        shell.fs.write_file('a.txt', 'hello\nworld')
        shell.fs.write_file('b.txt', 'hello\nearth')

        shell._output_capture.clear()
        result = shell.cmd_fc(['a.txt', 'b.txt'])
        output = '\n'.join(shell._output_capture)

        assert result == 1
        assert 'world' in output
        assert 'earth' in output
        assert '2: world' not in output
        assert '2: earth' not in output

    def test_cmd_fc_no_args(self, shell):
        """Test FC with no arguments."""
        result = shell.cmd_fc([])
        assert result == 1

    def test_cmd_fc_file_not_found(self, shell):
        """Test FC with missing file."""
        shell.fs.write_file('a.txt', 'hello')
        result = shell.cmd_fc(['a.txt', 'missing.txt'])
        assert result == 1

    # ==================== Environment Variable Expansion tests ====================

    def test_expand_known_variable(self, shell):
        shell.environment['MYVAR'] = 'hello'
        assert shell.expand_variables('%MYVAR%') == 'hello'

    def test_expand_case_insensitive(self, shell):
        shell.environment['MYVAR'] = 'hello'
        assert shell.expand_variables('%myvar%') == 'hello'

    def test_expand_unknown_variable_unchanged(self, shell):
        assert shell.expand_variables('%UNKNOWN%') == '%UNKNOWN%'

    def test_expand_multiple_variables(self, shell):
        shell.environment['A'] = '1'
        shell.environment['B'] = '2'
        assert shell.expand_variables('%A% and %B%') == '1 and 2'

    def test_expand_in_echo_command(self, shell):
        shell.environment['GREETING'] = 'Hello'
        shell._output_capture.clear()
        shell.execute_command('ECHO %GREETING% World')
        output = '\n'.join(shell._output_capture)
        assert 'Hello World' in output

    def test_expand_in_type_command(self, shell):
        shell.environment['MYFILE'] = 'test'
        shell.fs.write_file('test.txt', 'content')
        shell._output_capture.clear()
        shell.execute_command('TYPE %MYFILE%.txt')
        output = '\n'.join(shell._output_capture)
        assert 'content' in output

    def test_expand_in_cd_command(self, shell):
        shell.fs.make_directory('MYDIR')
        shell.environment['TARGET'] = 'MYDIR'
        shell._output_capture.clear()
        shell.execute_command('CD %TARGET%')
        assert shell.get_prompt() == 'C:\\MYDIR>'

    def test_expand_path_variable(self, shell):
        shell._output_capture.clear()
        shell.execute_command('ECHO %PATH%')
        output = '\n'.join(shell._output_capture)
        assert 'C:\\' in output


class TestBackgroundJobCommands:
    """Tests for START /B, JOBS, WAIT, KILL, JOBOUT, JOBERR commands."""

    def _wait_for_jobs(self, shell, timeout=2.0):
        """Wait for all background jobs to complete."""
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            shell.jcs.reap()
            if not shell.jcs.get_running_jobs():
                return
            time.sleep(0.05)

    # ==================== START /B tests ====================

    def test_start_b_basic(self, shell):
        """START /B spawns a background job."""
        shell.fs.write_file('test.bat', 'ECHO hello from bg')
        shell._output_capture.clear()
        result = shell.execute_command('START /B TEST')
        assert result == 0
        self._wait_for_jobs(shell)
        jobs = shell.jcs.get_all_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == 'JOB1'

    def test_start_b_with_id(self, shell):
        """START /B /ID:name assigns custom job ID."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell._output_capture.clear()
        result = shell.execute_command('START /B /ID BUILD TEST')
        assert result == 0
        self._wait_for_jobs(shell)
        job = shell.jcs.get_job('BUILD')
        assert job is not None

    def test_start_b_duplicate_id(self, shell):
        """START /B with duplicate ID fails."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B /ID BUILD TEST')
        shell._output_capture.clear()
        result = shell.execute_command('START /B /ID BUILD TEST')
        assert result == 1
        output = '\n'.join(shell._output_capture)
        assert 'ALREADY IN USE' in output

    def test_start_without_b_fails(self, shell):
        """START without /B flag fails."""
        shell._output_capture.clear()
        result = shell.execute_command('START ECHO hello')
        assert result == 1

    def test_start_b_no_command_fails(self, shell):
        """START /B without a command fails."""
        shell._output_capture.clear()
        result = shell.execute_command('START /B')
        assert result == 1

    def test_start_b_captures_stdout(self, shell):
        """Background job captures stdout."""
        shell.fs.write_file('test.bat', '@ECHO OFF\nECHO captured output')
        shell.execute_command('START /B TEST')
        self._wait_for_jobs(shell)
        job = shell.jcs.get_all_jobs()[0]
        assert 'captured output' in job.stdout_buf

    def test_start_b_sets_errorlevel_zero(self, shell):
        """START /B always returns 0 immediately."""
        shell.fs.write_file('fail.bat', 'DIR nonexistent')
        result = shell.execute_command('START /B FAIL')
        assert result == 0

    # ==================== JOBS tests ====================

    def test_jobs_empty(self, shell):
        """JOBS with no jobs ever started returns 1."""
        result = shell.execute_command('JOBS')
        assert result == 1

    def test_jobs_lists_jobs(self, shell):
        """JOBS lists background jobs."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B /ID BUILD TEST')
        self._wait_for_jobs(shell)
        shell._output_capture.clear()
        result = shell.execute_command('JOBS')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'BUILD' in output

    def test_jobs_verbose(self, shell):
        """JOBS /V shows verbose output."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B /ID BUILD TEST')
        self._wait_for_jobs(shell)
        shell._output_capture.clear()
        result = shell.execute_command('JOBS /V')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'BUILD' in output
        assert 'COMMAND' in output

    def test_jobs_purge(self, shell):
        """JOBS /PURGE removes completed jobs."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B TEST')
        self._wait_for_jobs(shell)
        shell.execute_command('JOBS /PURGE')
        shell._output_capture.clear()
        shell.execute_command('JOBS')
        output = '\n'.join(shell._output_capture)
        assert 'JOB1' not in output

    # ==================== WAIT tests ====================

    def test_wait_specific_job(self, shell):
        """WAIT waits for a specific job."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B /ID BUILD TEST')
        shell._output_capture.clear()
        result = shell.execute_command('WAIT BUILD')
        output = '\n'.join(shell._output_capture)
        assert 'BUILD completed' in output
        assert result == 0

    def test_wait_all(self, shell):
        """WAIT /ALL waits for all running jobs."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B /ID A TEST')
        shell.execute_command('START /B /ID B TEST')
        shell._output_capture.clear()
        result = shell.execute_command('WAIT /ALL')
        output = '\n'.join(shell._output_capture)
        assert 'completed' in output
        assert result == 0

    def test_wait_failed_job(self, shell):
        """WAIT returns job's exit code on failure."""
        shell.fs.write_file('fail.bat', '@ECHO OFF\nDIR nonexistent')
        shell.execute_command('START /B /ID FAIL FAIL')
        shell._output_capture.clear()
        result = shell.execute_command('WAIT FAIL')
        output = '\n'.join(shell._output_capture)
        assert 'failed' in output
        assert result != 0

    def test_wait_unknown_job(self, shell):
        """WAIT with unknown job ID returns 1."""
        shell._output_capture.clear()
        result = shell.execute_command('WAIT NOPE')
        output = '\n'.join(shell._output_capture)
        assert result == 1
        assert 'NO SUCH JOB' in output

    def test_wait_timeout(self, shell):
        """WAIT /T:n times out."""
        import threading

        event = threading.Event()

        def execute_fn(stdout_cb, stderr_cb):
            event.wait(timeout=10)
            return 0

        shell.jcs.spawn('SLOW', execute_fn, name='SLOW')
        try:
            shell._output_capture.clear()
            result = shell.execute_command('WAIT SLOW /T:0.3')
            output = '\n'.join(shell._output_capture)
            assert result == 2
            assert 'TIMEOUT' in output
        finally:
            event.set()

    # ==================== KILL tests ====================

    def test_kill_running_job(self, shell):
        """KILL terminates a running job."""
        import threading

        event = threading.Event()

        def execute_fn(stdout_cb, stderr_cb):
            event.wait(timeout=10)
            return 0

        shell.jcs.spawn('LONG', execute_fn, name='LONG')
        try:
            shell._output_capture.clear()
            result = shell.execute_command('KILL LONG /F')
            output = '\n'.join(shell._output_capture)
            assert result == 0
            assert 'terminated' in output
        finally:
            event.set()

    def test_kill_all(self, shell):
        """KILL /ALL terminates all running jobs."""
        import threading

        event = threading.Event()

        def execute_fn(stdout_cb, stderr_cb):
            event.wait(timeout=10)
            return 0

        shell.jcs.spawn('A', execute_fn, name='A')
        shell.jcs.spawn('B', execute_fn, name='B')
        try:
            shell._output_capture.clear()
            result = shell.execute_command('KILL /ALL /F')
            output = '\n'.join(shell._output_capture)
            assert result == 0
            assert 'terminated' in output
        finally:
            event.set()

    def test_kill_unknown_job(self, shell):
        """KILL with unknown job ID returns 1."""
        shell._output_capture.clear()
        result = shell.execute_command('KILL NOPE')
        output = '\n'.join(shell._output_capture)
        assert result == 1
        assert 'NO SUCH JOB' in output

    def test_kill_completed_job(self, shell):
        """KILL on already completed job returns 1."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B /ID DONE TEST')
        self._wait_for_jobs(shell)
        shell._output_capture.clear()
        result = shell.execute_command('KILL DONE')
        output = '\n'.join(shell._output_capture)
        assert result == 1
        assert 'NOT RUNNING' in output

    # ==================== JOBOUT tests ====================

    def test_jobout_shows_stdout(self, shell):
        """JOBOUT displays captured stdout."""
        shell.fs.write_file('test.bat', '@ECHO OFF\nECHO hello world')
        shell.execute_command('START /B /ID OUT TEST')
        self._wait_for_jobs(shell)
        shell._output_capture.clear()
        result = shell.execute_command('JOBOUT OUT')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'hello world' in output

    def test_jobout_n_lines(self, shell):
        """JOBOUT /N:n shows last n lines."""
        shell.fs.write_file('test.bat', '@ECHO OFF\nECHO line1\nECHO line2\nECHO line3')
        shell.execute_command('START /B /ID OUT TEST')
        self._wait_for_jobs(shell)
        shell._output_capture.clear()
        result = shell.execute_command('JOBOUT OUT /N:1')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'line3' in output
        assert 'line1' not in output

    def test_jobout_unknown_job(self, shell):
        """JOBOUT with unknown job returns 1."""
        result = shell.execute_command('JOBOUT NOPE')
        assert result == 1

    # ==================== JOBERR tests ====================

    def test_joberr_shows_stderr(self, shell):
        """JOBERR displays captured stderr."""

        def execute_fn(stdout_cb, stderr_cb):
            stderr_cb('error output')
            return 1

        shell.jcs.spawn('ERR', execute_fn, name='ERR')
        shell.jcs.get_job('ERR').thread.join(timeout=2)
        shell.jcs.reap()
        shell._output_capture.clear()
        result = shell.execute_command('JOBERR ERR')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'error output' in output

    def test_joberr_unknown_job(self, shell):
        """JOBERR with unknown job returns 1."""
        result = shell.execute_command('JOBERR NOPE')
        assert result == 1

    # ==================== HELP tests for new commands ====================

    def test_help_start(self, shell):
        """HELP START shows help text."""
        shell._output_capture.clear()
        shell.execute_command('HELP START')
        output = '\n'.join(shell._output_capture)
        assert 'START' in output

    def test_help_jobs(self, shell):
        """HELP JOBS shows help text."""
        shell._output_capture.clear()
        shell.execute_command('HELP JOBS')
        output = '\n'.join(shell._output_capture)
        assert 'JOBS' in output

    def test_help_wait(self, shell):
        """HELP WAIT shows help text."""
        shell._output_capture.clear()
        shell.execute_command('HELP WAIT')
        output = '\n'.join(shell._output_capture)
        assert 'WAIT' in output

    def test_help_kill(self, shell):
        """HELP KILL shows help text."""
        shell._output_capture.clear()
        shell.execute_command('HELP KILL')
        output = '\n'.join(shell._output_capture)
        assert 'KILL' in output

    # ==================== /TAIL tests ====================

    def test_jobout_tail(self, shell):
        """JOBOUT /TAIL follows output until job ends."""

        def execute_fn(stdout_cb, stderr_cb):
            stdout_cb('line1')
            stdout_cb('line2')
            return 0

        shell.jcs.spawn('CMD', execute_fn, name='TAIL')
        shell.jcs.get_job('TAIL').thread.join(timeout=2)
        shell.jcs.reap()
        shell._output_capture.clear()
        result = shell.execute_command('JOBOUT TAIL /TAIL')
        output = '\n'.join(shell._output_capture)
        assert result == 0
        assert 'line1' in output
        assert 'line2' in output

    # ==================== Ring buffer at shell level ====================

    def test_jobout_ring_buffer_truncation(self, shell):
        """Large output is truncated by the ring buffer."""
        from dospc_sim.jcs import JOB_OUT_BUFSZ

        def execute_fn(stdout_cb, stderr_cb):
            for i in range(2000):
                stdout_cb(f'line {i} ' + 'x' * 40)
            return 0

        shell.jcs.spawn('CMD', execute_fn, name='BIG')
        shell.jcs.get_job('BIG').thread.join(timeout=5)
        shell.jcs.reap()
        job = shell.jcs.get_job('BIG')
        assert len(job.stdout_buf) <= JOB_OUT_BUFSZ

    # ==================== WAIT /ALL mixed results ====================

    def test_wait_all_highest_exit_code(self, shell):
        """WAIT /ALL returns highest non-zero exit code."""

        def ok_fn(stdout_cb, stderr_cb):
            return 0

        def fail_fn(stdout_cb, stderr_cb):
            return 3

        shell.jcs.spawn('CMD1', ok_fn, name='OK')
        shell.jcs.spawn('CMD2', fail_fn, name='FAIL')
        shell.jcs.get_job('OK').thread.join(timeout=2)
        shell.jcs.get_job('FAIL').thread.join(timeout=2)
        shell._output_capture.clear()
        result = shell.execute_command('WAIT /ALL')
        assert result == 3

    # ==================== START /B with inline command ====================

    def test_start_b_inline_echo(self, shell):
        """START /B with inline ECHO command."""
        shell.execute_command('START /B ECHO hello')
        self._wait_for_jobs(shell)
        job = shell.jcs.get_all_jobs()[0]
        assert 'hello' in job.stdout_buf

    # ==================== JOBS after purge ====================

    def test_jobs_after_purge_returns_zero(self, shell):
        """JOBS returns 0 after purge when jobs were started."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B TEST')
        self._wait_for_jobs(shell)
        shell.execute_command('JOBS /PURGE')
        shell._output_capture.clear()
        result = shell.execute_command('JOBS')
        assert result == 0

    # ==================== KILL /ALL with no running jobs ====================

    def test_kill_all_no_running(self, shell):
        """KILL /ALL with no running jobs returns 0."""
        shell.fs.write_file('test.bat', 'ECHO hello')
        shell.execute_command('START /B TEST')
        self._wait_for_jobs(shell)
        shell._output_capture.clear()
        result = shell.execute_command('KILL /ALL')
        assert result == 0

    # ==================== Invalid /ID ====================

    def test_start_b_invalid_id_chars(self, shell):
        """START /B with invalid ID characters fails."""
        shell._output_capture.clear()
        result = shell.execute_command('START /B /ID bad!name ECHO hello')
        assert result == 1
        output = '\n'.join(shell._output_capture)
        assert 'INVALID JOB ID' in output

    # ==================== %ERRORLEVEL% expansion ====================

    def test_errorlevel_variable_expansion(self, shell):
        """ERRORLEVEL expands as a dynamic pseudo-variable."""
        shell.last_errorlevel = 42
        shell._output_capture.clear()
        shell.execute_command('ECHO %ERRORLEVEL%')
        output = '\n'.join(shell._output_capture)
        assert '42' in output

    def test_errorlevel_variable_after_command(self, shell):
        """ERRORLEVEL reflects last command's exit code."""
        shell.execute_command('DIR nonexistent')
        shell._output_capture.clear()
        shell.execute_command('ECHO %ERRORLEVEL%')
        output = '\n'.join(shell._output_capture)
        assert '1' in output
