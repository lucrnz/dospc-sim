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
