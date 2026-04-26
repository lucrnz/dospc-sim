"""Standalone CLI entrypoint for the DOS shell runtime."""

import argparse
import getpass
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dospc_sim.dos_shell import DOSShell
from dospc_sim.filesystem import UserFilesystem

_STDIN_TOKENS = {'-', 'STDIN'}


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    iterations: int
    seconds: float

    @property
    def ops_per_sec(self) -> float:
        if self.seconds == 0:
            return float('inf')
        return self.iterations / self.seconds


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    setup: Callable[[], None]
    run: Callable[[], None]
    per_iteration_reset: Callable[[], None]
    teardown: Callable[[], None]


def _benchmark_time(
    fn: Callable[[], None],
    iterations: int,
    reset: Callable[[], None] | None = None,
) -> float:
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
        if reset:
            reset()
    return time.perf_counter() - start


def _output_lines(shell: DOSShell) -> list[str]:
    output = getattr(shell, '_output_capture', [])
    return output


def _reset_output(shell: DOSShell) -> None:
    output = getattr(shell, '_output_capture', None)
    if output is not None:
        output.clear()


def _write_fixture_files(shell: DOSShell) -> None:
    shell.fs.write_file('alpha.txt', 'alpha\nline2\nline3\n')
    shell.fs.write_file('beta.txt', 'beta\nline2\nline3\n')
    shell.fs.write_file('gamma.log', 'gamma\nline2\nline3\n')
    shell.fs.make_directory('docs')
    shell.fs.write_file('docs/readme.txt', 'readme\ninfo\n')
    shell.fs.make_directory('data')
    shell.fs.write_file('data/data1.txt', 'one\n')
    shell.fs.write_file('data/data2.txt', 'two\n')
    shell.fs.write_file('docs/alpha.txt', 'alpha copy\n')
    shell.fs.write_file('docs/beta.txt', 'beta copy\n')


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for standalone DOS shell mode."""
    parser = argparse.ArgumentParser(
        prog='dos-shell',
        description='Run the standalone DOS shell interpreter.',
    )
    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Run benchmark suite and exit.',
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=100,
        help='Iterations per benchmark (default: 100).',
    )
    parser.add_argument(
        'source',
        nargs='?',
        help='Batch source to execute (file path, -, or STDIN)',
    )
    parser.add_argument(
        'script_args',
        nargs='*',
        help='Arguments passed to batch source as %1..%9',
    )
    return parser


def _create_shell() -> DOSShell:
    """Create a DOS shell rooted at the current working directory."""
    username = getpass.getuser() or 'local'
    filesystem = UserFilesystem(str(Path.cwd()), username)
    return DOSShell(filesystem, username)


def _run_interactive(shell: DOSShell) -> int:
    """Run interactive shell session until EXIT or EOF."""
    shell.run()

    try:
        while shell.running:
            shell.jcs.reap()
            try:
                command = input(shell.get_prompt())
            except EOFError:
                break
            except KeyboardInterrupt:
                print()
                continue

            shell.execute_command(command)
    finally:
        shell.jcs.shutdown()

    return shell.last_errorlevel


def _run_script(shell: DOSShell, script_path: str, script_args: list[str]) -> int:
    """Execute batch file script and exit."""
    batch_file = shell._find_batch_file(script_path)
    if batch_file is None:
        shell._output_line(f'Bad command or file name: {script_path}')
        return 1
    return shell._execute_batch(batch_file, script_args)


def _run_stdin(shell: DOSShell, script_args: list[str]) -> int:
    """Execute batch content from stdin and exit."""
    content = sys.stdin.read()
    if not content:
        return 0
    return shell.execute_batch_content(content, batch_name='STDIN', args=script_args)


def _noop() -> None:
    return None


def _wait_bg(shell: DOSShell) -> None:
    """Wait for all background jobs to complete."""
    for job in shell.jcs.get_running_jobs():
        if job.thread is not None:
            job.thread.join(timeout=2)
    shell.jcs.reap()


def _build_benchmark_cases(shell: DOSShell) -> list[BenchmarkCase]:
    def run(cmd: str) -> Callable[[], None]:
        def _runner() -> None:
            shell.execute_command(cmd)

        return _runner

    def remove_benchdir() -> None:
        shell.execute_command('RD benchdir')

    def ensure_benchdir() -> None:
        shell.execute_command('RD benchdir')
        shell.execute_command('MD benchdir')

    def remove_outfile() -> None:
        shell.execute_command('DEL out.txt')

    def ensure_copy_file() -> None:
        shell.fs.write_file('copy.txt', 'alpha\n')

    def ensure_alpha() -> None:
        shell.fs.write_file('alpha.txt', 'alpha\n')

    def ensure_alpha1() -> None:
        shell.fs.write_file('alpha1.txt', 'alpha\n')

    pipe_cmd = 'TYPE beta.txt | FIND line | SORT'
    batch_script = '\n'.join(
        [
            ':: Benchmark batch',
            '@ECHO OFF',
            'SET COUNT=0',
            ':loop',
            'SET COUNT=1',
            'IF EXIST beta.txt ECHO found',
            'IF NOT ERRORLEVEL 2 ECHO ok',
            'IF alpha==alpha ECHO match',
            'IF DEFINED COUNT ECHO defined',
            'IF 1==2 ECHO no ELSE ECHO yes',
            'FOR %%F IN (alpha.txt beta.txt) DO TYPE %%F',
            'GOTO done',
            ':done',
        ]
    )
    shell.fs.write_file('batch.bat', 'ECHO batch')

    return [
        BenchmarkCase('DIR', _noop, run('DIR'), _noop, _noop),
        BenchmarkCase('DIR /W', _noop, run('DIR /W'), _noop, _noop),
        BenchmarkCase('DIR /A', _noop, run('DIR /A'), _noop, _noop),
        BenchmarkCase('DIR wildcard', _noop, run('DIR *.txt'), _noop, _noop),
        BenchmarkCase('CD', _noop, run('CD \\'), _noop, _noop),
        BenchmarkCase(
            'MD', remove_benchdir, run('MD benchdir'), remove_benchdir, _noop
        ),
        BenchmarkCase(
            'RD', ensure_benchdir, run('RD benchdir'), run('MD benchdir'), _noop
        ),
        BenchmarkCase(
            'COPY',
            ensure_alpha,
            run('COPY alpha.txt copy.txt'),
            run('DEL copy.txt'),
            _noop,
        ),
        BenchmarkCase(
            'DEL', ensure_copy_file, run('DEL copy.txt'), ensure_copy_file, _noop
        ),
        BenchmarkCase(
            'REN',
            ensure_alpha,
            run('REN alpha.txt alpha1.txt'),
            run('REN alpha1.txt alpha.txt'),
            _noop,
        ),
        BenchmarkCase(
            'MOVE',
            ensure_alpha1,
            run('MOVE alpha1.txt docs'),
            run('MOVE docs\\alpha1.txt alpha1.txt'),
            _noop,
        ),
        BenchmarkCase('COPY wildcard', _noop, run('COPY *.txt docs'), _noop, _noop),
        BenchmarkCase('TYPE', _noop, run('TYPE beta.txt'), _noop, _noop),
        BenchmarkCase('TREE', _noop, run('TREE /F'), _noop, _noop),
        BenchmarkCase('FIND', _noop, run('FIND /I line beta.txt'), _noop, _noop),
        BenchmarkCase('MORE', _noop, run('MORE beta.txt'), _noop, _noop),
        BenchmarkCase('SORT', _noop, run('SORT beta.txt'), _noop, _noop),
        BenchmarkCase('FC', _noop, run('FC beta.txt gamma.log'), _noop, _noop),
        BenchmarkCase('SET', _noop, run('SET BENCH=1'), _noop, run('SET BENCH=')),
        BenchmarkCase('PROMPT', _noop, run('PROMPT $P$G'), _noop, _noop),
        BenchmarkCase('PATH', _noop, run('PATH C:\\'), _noop, _noop),
        BenchmarkCase('DATE', _noop, run('DATE'), _noop, _noop),
        BenchmarkCase('TIME', _noop, run('TIME'), _noop, _noop),
        BenchmarkCase('VER', _noop, run('VER'), _noop, _noop),
        BenchmarkCase('ECHO', _noop, run('ECHO hello'), _noop, _noop),
        BenchmarkCase('CLS', _noop, run('CLS'), _noop, _noop),
        BenchmarkCase('Pipes', _noop, run(pipe_cmd), _noop, _noop),
        BenchmarkCase('Echo pipe', _noop, run('ECHO hello | FIND hello'), _noop, _noop),
        BenchmarkCase(
            'Redirect >',
            remove_outfile,
            run('ECHO hi > out.txt'),
            remove_outfile,
            _noop,
        ),
        BenchmarkCase(
            'Redirect >>',
            remove_outfile,
            run('ECHO hi >> out.txt'),
            remove_outfile,
            _noop,
        ),
        BenchmarkCase('Redirect <', _noop, run('FIND line < beta.txt'), _noop, _noop),
        BenchmarkCase('CALL', _noop, run('CALL batch.bat'), _noop, _noop),
        BenchmarkCase(
            'IF DEFINED',
            _noop,
            run('IF DEFINED PATH ECHO yes'),
            _noop,
            _noop,
        ),
        BenchmarkCase(
            'IF ELSE',
            _noop,
            run('IF 1==2 ECHO no ELSE ECHO yes'),
            _noop,
            _noop,
        ),
        BenchmarkCase(
            'Chain &&',
            _noop,
            run('ECHO hello && ECHO world'),
            _noop,
            _noop,
        ),
        BenchmarkCase(
            'Chain ||',
            _noop,
            run('DIR missing || ECHO fallback'),
            _noop,
            _noop,
        ),
        BenchmarkCase(
            '@ prefix',
            _noop,
            lambda: shell.execute_batch_content('@ECHO hello\n@ECHO world'),
            run('ECHO ON'),
            _noop,
        ),
        BenchmarkCase(
            'Batch',
            _noop,
            lambda: shell.execute_batch_content(batch_script),
            run('ECHO ON'),
            _noop,
        ),
        BenchmarkCase(
            'START /B',
            _noop,
            lambda: (
                shell.execute_command('START /B ECHO hello'),
                _wait_bg(shell),
                shell.jcs.purge_completed(),
            ),
            _noop,
            _noop,
        ),
        BenchmarkCase(
            'JOBS',
            lambda: (
                shell.execute_command('START /B ECHO hello'),
                _wait_bg(shell),
            ),
            run('JOBS'),
            _noop,
            lambda: shell.jcs.purge_completed(),
        ),
        BenchmarkCase(
            'WAIT',
            _noop,
            lambda: (
                shell.execute_command('START /B ECHO hello'),
                shell.execute_command('WAIT /ALL'),
                shell.jcs.purge_completed(),
            ),
            _noop,
            _noop,
        ),
    ]


def _execute_benchmark_cases(
    shell: DOSShell, cases: list[BenchmarkCase], iterations: int
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []

    for case in cases:
        case.setup()
        _reset_output(shell)

        def reset(current_case: BenchmarkCase = case) -> None:
            current_case.per_iteration_reset()
            _reset_output(shell)

        duration = _benchmark_time(case.run, iterations, reset=reset)
        results.append(
            BenchmarkResult(name=case.name, iterations=iterations, seconds=duration)
        )
        case.teardown()
        _reset_output(shell)

    return results


def _print_benchmark_results(shell: DOSShell, results: list[BenchmarkResult]) -> None:
    _reset_output(shell)
    header = f'{"Benchmark":<22} {"Iterations":>10} {"Seconds":>12} {"Ops/Sec":>12}'
    shell._output_line(header)
    shell._output_line('-' * len(header))
    for result in results:
        shell._output_line(
            f'{result.name:<22} {result.iterations:>10} '
            f'{result.seconds:>12.4f} {result.ops_per_sec:>12.2f}'
        )

    for line in _output_lines(shell):
        print(line)


def _run_benchmark(iterations: int) -> int:
    username = getpass.getuser() or 'local'
    with tempfile.TemporaryDirectory() as temp_dir:
        fs = UserFilesystem(temp_dir, username)
        output_capture: list[str] = []

        def output_callback(text: str) -> None:
            output_capture.append(text)

        shell = DOSShell(fs, username, output_callback)
        shell._output_capture = output_capture
        _write_fixture_files(shell)

        cases = _build_benchmark_cases(shell)
        results = _execute_benchmark_cases(shell, cases, iterations)
        _print_benchmark_results(shell, results)

    return 0


def run_dos_shell(argv: list[str] | None = None) -> int:
    """Run standalone DOS shell command and return exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.benchmark:
        return _run_benchmark(max(1, args.iterations))

    shell = _create_shell()
    source = args.source

    if source in _STDIN_TOKENS or (source and source.upper() == 'STDIN'):
        return _run_stdin(shell, args.script_args)

    if source:
        return _run_script(shell, source, args.script_args)

    if not sys.stdin.isatty():
        return _run_stdin(shell, [])

    return _run_interactive(shell)


def main() -> None:
    """CLI script entrypoint."""
    raise SystemExit(run_dos_shell())


if __name__ == '__main__':
    main()
