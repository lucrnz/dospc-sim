"""Pipe and redirection tests for DOS shell."""

from dospc_sim.parser import parse_command


class TestDOSShellRedirection:
    # ==================== Pipe Execution tests ====================

    def test_type_pipe_sort(self, shell):
        shell.fs.write_file('unsorted.txt', 'cherry\napple\nbanana')
        shell._output_capture.clear()
        shell.execute_command('TYPE unsorted.txt | SORT')
        output = '\n'.join(shell._output_capture)
        apple_idx = output.index('apple')
        banana_idx = output.index('banana')
        cherry_idx = output.index('cherry')
        assert apple_idx < banana_idx < cherry_idx

    def test_type_pipe_find(self, shell):
        shell.fs.write_file('data.txt', 'hello world\nfoo bar\nhello again')
        shell._output_capture.clear()
        shell.execute_command('TYPE data.txt | FIND hello')
        output = '\n'.join(shell._output_capture)
        assert 'hello world' in output
        assert 'hello again' in output
        assert 'foo bar' not in output

    def test_type_pipe_sort_pipe_find(self, shell):
        shell.fs.write_file('data.txt', 'cherry\napple\nbanana')
        shell._output_capture.clear()
        shell.execute_command('TYPE data.txt | SORT | FIND apple')
        output = '\n'.join(shell._output_capture)
        assert 'apple' in output

    def test_pipe_three_commands(self, shell):
        shell.fs.write_file('data.txt', 'zebra\napple\nbanana\navocado')
        shell._output_capture.clear()
        shell.execute_command('TYPE data.txt | SORT | FIND a')
        output = '\n'.join(shell._output_capture)
        assert 'apple' in output
        assert 'avocado' in output

    # ==================== I/O Redirection tests ====================

    def test_echo_redirect_to_file(self, shell):
        shell.execute_command('ECHO Hello World > output.txt')
        assert shell.fs.file_exists('output.txt')
        content = shell.fs.read_file('output.txt')
        assert 'Hello World' in content

    def test_dir_redirect_to_file(self, shell):
        shell.fs.write_file('marker.txt', 'test')
        shell.execute_command('DIR > listing.txt')
        assert shell.fs.file_exists('listing.txt')

    def test_append_redirect(self, shell):
        shell.execute_command('ECHO Line 1 > log.txt')
        shell.execute_command('ECHO Line 2 >> log.txt')
        content = shell.fs.read_file('log.txt')
        assert 'Line 1' in content
        assert 'Line 2' in content

    def test_input_redirect_sort(self, shell):
        shell.fs.write_file('data.txt', 'cherry\napple\nbanana')
        shell._output_capture.clear()
        shell.execute_command('SORT < data.txt')
        output = '\n'.join(shell._output_capture)
        assert 'apple' in output
        assert 'banana' in output
        assert 'cherry' in output

    def test_parser_redirect_write(self):
        r = parse_command('ECHO hello > out.txt')
        assert r is not None
        assert r.stdout_redirect == 'out.txt'

    def test_parser_redirect_append(self):
        r = parse_command('ECHO hello >> out.txt')
        assert r is not None
        assert r.append_redirect == 'out.txt'

    def test_parser_redirect_input(self):
        r = parse_command('SORT < input.txt')
        assert r is not None
        assert r.stdin_redirect == 'input.txt'

    def test_parser_redirect_combined(self):
        r = parse_command('SORT < input.txt > output.txt')
        assert r is not None
        assert r.stdin_redirect == 'input.txt'
        assert r.stdout_redirect == 'output.txt'

    def test_type_redirect_to_file(self, shell):
        shell.fs.write_file('source.txt', 'original content')
        shell.execute_command('TYPE source.txt > copy.txt')
        assert shell.fs.file_exists('copy.txt')
        content = shell.fs.read_file('copy.txt')
        assert 'original content' in content
