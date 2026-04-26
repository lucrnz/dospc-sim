"""Batch execution behavior tests for DOS shell."""


class TestDOSShellBatch:
    # ==================== Batch GOTO tests ====================

    def test_goto_forward(self, shell):
        batch = """ECHO Before
GOTO SKIP
ECHO Skipped
:SKIP
ECHO After"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Before' in output
        assert 'Skipped' not in output
        assert 'After' in output

    def test_goto_backward_loop(self, shell):
        batch = """SET COUNT=0
:LOOP
ECHO Iteration
GOTO END
:END"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Iteration' in output

    def test_goto_nonexistent_label(self, shell):
        batch = """GOTO MISSING
ECHO This runs"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Label not found' in output

    # ==================== Batch IF tests ====================

    def test_if_exist_true(self, shell):
        shell.fs.write_file('exists.txt', 'data')
        batch = """IF EXIST exists.txt ECHO Found
ECHO Done"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Found' in output
        assert 'Done' in output

    def test_if_exist_false(self, shell):
        batch = """ECHO OFF
IF EXIST missing.txt ECHO Found
ECHO Done"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Found' not in output
        assert 'Done' in output

    def test_if_not_exist(self, shell):
        batch = """IF NOT EXIST missing.txt ECHO Not Found
ECHO Done"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Not Found' in output

    def test_if_errorlevel(self, shell):
        batch = """IF ERRORLEVEL 1 ECHO Failed
ECHO Done"""
        shell.fs.write_file('test.bat', batch)
        shell.last_errorlevel = 1
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Failed' in output

    def test_if_errorlevel_not_met(self, shell):
        batch = """ECHO OFF
IF ERRORLEVEL 1 ECHO Failed
ECHO Done"""
        shell.fs.write_file('test.bat', batch)
        shell.last_errorlevel = 0
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Failed' not in output
        assert 'Done' in output

    def test_if_string_equality(self, shell):
        batch = """IF hello==hello ECHO Match
ECHO Done"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Match' in output

    def test_if_string_inequality(self, shell):
        batch = """ECHO OFF
IF hello==world ECHO Match
ECHO Done"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Match' not in output
        assert 'Done' in output

    def test_if_goto(self, shell):
        batch = """IF 1==1 GOTO SKIP
ECHO Skipped
:SKIP
ECHO Arrived"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Skipped' not in output
        assert 'Arrived' in output

    # ==================== Batch FOR tests ====================

    def test_for_loop_basic(self, shell):
        batch = 'FOR %%F IN (a b c) DO ECHO %%F'
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'a' in output
        assert 'b' in output
        assert 'c' in output

    def test_for_loop_with_file_ops(self, shell):
        shell.fs.write_file('a.txt', 'content a')
        shell.fs.write_file('b.txt', 'content b')
        batch = 'FOR %%F IN (a.txt b.txt) DO TYPE %%F'
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'content a' in output
        assert 'content b' in output

    def test_for_loop_lowercase_reference(self, shell):
        batch = 'FOR %%F IN (a b c) DO ECHO %%f'
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'a' in output
        assert 'b' in output
        assert 'c' in output

    def test_for_loop_mixed_case_references(self, shell):
        batch = """FOR %%F IN (a b) DO ECHO %%F %%f"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'a a' in output
        assert 'b b' in output

    def test_for_loop_preserves_backslashes_in_item_values(self, shell):
        batch = r'FOR %%F IN (C:\temp) DO ECHO %%f'
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'C:\\temp' in output

    # ==================== Batch CALL tests ====================

    def test_call_batch(self, shell):
        shell.fs.write_file('sub.bat', 'ECHO In Subroutine')
        batch = """ECHO Before
CALL SUB
ECHO After"""
        shell.fs.write_file('main.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('MAIN')
        output = '\n'.join(shell._output_capture)
        assert 'Before' in output
        assert 'In Subroutine' in output
        assert 'After' in output

    def test_call_with_params(self, shell):
        shell.fs.write_file('greet.bat', 'ECHO Hello %1')
        batch = 'CALL GREET World'
        shell.fs.write_file('main.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('MAIN')
        output = '\n'.join(shell._output_capture)
        assert 'Hello World' in output

    # ==================== Batch PAUSE tests ====================

    def test_pause_message(self, shell):
        batch = """ECHO Before
PAUSE
ECHO After"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Before' in output
        assert 'Press any key to continue' in output
        assert 'After' in output

    # ==================== Batch ECHO ON/OFF tests ====================

    def test_echo_off_does_not_break(self, shell):
        batch = """ECHO OFF
ECHO Still works"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Still works' in output

    def test_batch_echo_on_echoes_commands(self, shell):
        """With ECHO ON (default), batch commands are echoed before execution."""
        batch = """ECHO Hello"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        # The echoed command line should include the prompt and the command
        assert 'C:\\>ECHO Hello' in output
        # The command output itself should also appear
        assert 'Hello' in output

    def test_batch_echo_off_suppresses_echo(self, shell):
        """ECHO OFF suppresses command echoing for subsequent lines."""
        batch = """ECHO OFF
ECHO Line1
ECHO Line2"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        # After ECHO OFF, commands should NOT be echoed
        assert 'C:\\>ECHO Line1' not in output
        assert 'C:\\>ECHO Line2' not in output
        # But their output should still appear
        assert 'Line1' in output
        assert 'Line2' in output

    def test_batch_echo_on_off_toggle(self, shell):
        """ECHO can be toggled on and off within a batch file."""
        batch = """ECHO OFF
ECHO Silent
ECHO ON
ECHO Visible"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        # After ECHO OFF, the ECHO Silent command should not be echoed
        assert 'C:\\>ECHO Silent' not in output
        assert 'Silent' in output
        # After ECHO ON, the ECHO Visible command should be echoed
        assert 'C:\\>ECHO Visible' in output
        assert 'Visible' in output

    def test_call_batch_inherits_echo_off_state(self, shell):
        """Nested batch calls should inherit current ECHO state."""
        shell.fs.write_file('sub.bat', 'ECHO In Subroutine')
        batch = """ECHO OFF
CALL SUB
ECHO After"""
        shell.fs.write_file('main.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('MAIN')
        output = '\n'.join(shell._output_capture)
        assert 'C:\\>ECHO In Subroutine' not in output
        assert 'In Subroutine' in output
        assert 'After' in output

    # ==================== PROMPT Variable tests ====================

    def test_default_prompt_pg(self, shell):
        prompt = shell.get_prompt()
        assert 'C:\\>' in prompt

    def test_prompt_pg(self, shell):
        shell.execute_command('PROMPT $P$G')
        prompt = shell.get_prompt()
        assert 'C:\\>' in prompt

    def test_prompt_custom_text(self, shell):
        shell.environment['PROMPT'] = 'Hello>'
        prompt = shell.get_prompt()
        assert prompt == 'Hello>'

    def test_prompt_dollar_n(self, shell):
        shell.execute_command('PROMPT $N$G')
        prompt = shell.get_prompt()
        assert prompt == 'C>'

    def test_prompt_dollar_d(self, shell):
        shell.execute_command('PROMPT $D$G')
        prompt = shell.get_prompt()
        assert '>' in prompt
        assert '/' in prompt

    def test_prompt_dollar_dollar(self, shell):
        shell.execute_command('PROMPT $$test$$')
        prompt = shell.get_prompt()
        assert prompt == '$test$'

    def test_prompt_in_subdirectory(self, shell):
        shell.fs.make_directory('SUB')
        shell.fs.change_directory('SUB')
        shell.execute_command('PROMPT $P$G')
        prompt = shell.get_prompt()
        assert 'C:\\SUB>' in prompt

    # ==================== Batch Labels tests ====================

    def test_labels_are_case_insensitive(self, shell):
        batch = """GOTO MyLabel
ECHO Skipped
:MYLABEL
ECHO Found"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Found' in output
        assert 'Skipped' not in output

    def test_label_with_underscore(self, shell):
        batch = """GOTO MY_LABEL
ECHO Skipped
:MY_LABEL
ECHO Found"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Found' in output
        assert 'Skipped' not in output

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
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Second' in output
        assert 'First' in output
        assert 'Done' in output

    # ==================== IF EXIST Directory tests ====================

    def test_if_exist_directory(self, shell):
        shell.fs.make_directory('MYDIR')
        batch = """IF EXIST MYDIR ECHO DirFound
ECHO Done"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'DirFound' in output

    # ==================== Batch Variables in Batch tests ====================

    def test_set_and_use_in_batch(self, shell):
        batch = """SET NAME=World
ECHO Hello %NAME%"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Hello World' in output

    def test_batch_params_with_env_vars(self, shell):
        batch = """ECHO %1
SET FILE=%1
ECHO %FILE%"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST mydata')
        output = '\n'.join(shell._output_capture)
        assert 'mydata' in output

    # ==================== Combined Batch Features tests ====================

    def test_if_goto_for(self, shell):
        batch = """IF 1==1 GOTO PROCESS
ECHO Skip
:PROCESS
FOR %%I IN (x y z) DO ECHO %%I"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Skip' not in output
        assert 'x' in output
        assert 'y' in output
        assert 'z' in output

    def test_for_with_if(self, shell):
        shell.fs.write_file('a.txt', 'content a')
        shell.fs.write_file('b.txt', 'content b')
        batch = """FOR %%F IN (a.txt b.txt) DO IF EXIST %%F ECHO Found %%F"""
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'Found a.txt' in output
        assert 'Found b.txt' in output

    # ==================== FOR body with pipes regression (bug 3) =========

    def test_for_loop_body_with_pipe(self, shell):
        """FOR loop body containing a pipe must execute, not produce empty string."""
        shell.fs.write_file('a.txt', 'hello\nworld')
        shell.fs.write_file('b.txt', 'foo\nbar')
        batch = 'FOR %%F IN (a.txt b.txt) DO TYPE %%F | FIND hello'
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'hello' in output

    def test_for_loop_body_with_nested_for(self, shell):
        """FOR loop body containing another FOR must execute."""
        batch = 'FOR %%X IN (a b) DO FOR %%Y IN (1 2) DO ECHO %%X %%Y'
        shell.fs.write_file('test.bat', batch)
        shell._output_capture.clear()
        shell.execute_command('TEST')
        output = '\n'.join(shell._output_capture)
        assert 'a' in output
