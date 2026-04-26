"""Unit tests for the Job Control Subsystem."""

import threading
import time

import pytest

from dospc_sim.jcs import (
    JOB_ID_MAX_LEN,
    JOB_OUT_BUFSZ,
    JOB_TABLE_MAX,
    JobControlSubsystem,
    JobEntry,
    JobStatus,
)


@pytest.fixture
def jcs():
    j = JobControlSubsystem()
    yield j
    j.shutdown()


def _quick_job(exit_code=0, duration=0.0):
    """Returns an execute_fn that completes with given exit code."""

    def execute_fn(stdout_cb, stderr_cb):
        if duration > 0:
            time.sleep(duration)
        stdout_cb('output line')
        return exit_code

    return execute_fn


def _blocking_job():
    """Returns an execute_fn that blocks until cancelled."""
    event = threading.Event()

    def execute_fn(stdout_cb, stderr_cb):
        event.wait(timeout=10)
        return 0

    return execute_fn, event


class TestJobEntry:
    def test_append_stdout(self):
        entry = JobEntry(slot=1, id='TEST', thread=None)
        entry.append_stdout('hello')
        assert 'hello' in entry.stdout_buf

    def test_append_stderr(self):
        entry = JobEntry(slot=1, id='TEST', thread=None)
        entry.append_stderr('error msg')
        assert 'error msg' in entry.stderr_buf

    def test_stdout_ring_buffer(self):
        entry = JobEntry(slot=1, id='TEST', thread=None)
        big_data = 'x' * (JOB_OUT_BUFSZ + 100)
        entry.append_stdout(big_data)
        assert len(entry.stdout_buf) <= JOB_OUT_BUFSZ + 1  # +1 for newline

    def test_stderr_ring_buffer(self):
        entry = JobEntry(slot=1, id='TEST', thread=None)
        big_data = 'x' * (JOB_OUT_BUFSZ + 100)
        entry.append_stderr(big_data)
        assert len(entry.stderr_buf) <= JOB_OUT_BUFSZ + 1


class TestJobControlSubsystem:
    def test_spawn_auto_id(self, jcs):
        entry, error = jcs.spawn('ECHO hello', _quick_job())
        assert error is None
        assert entry is not None
        assert entry.id == 'JOB1'

    def test_spawn_sequential_ids(self, jcs):
        e1, _ = jcs.spawn('CMD1', _quick_job())
        e2, _ = jcs.spawn('CMD2', _quick_job())
        assert e1.id == 'JOB1'
        assert e2.id == 'JOB2'

    def test_spawn_named_job(self, jcs):
        entry, error = jcs.spawn('ECHO hello', _quick_job(), name='BUILD')
        assert error is None
        assert entry.id == 'BUILD'

    def test_spawn_duplicate_name_rejected(self, jcs):
        jcs.spawn('CMD1', _quick_job(), name='BUILD')
        entry, error = jcs.spawn('CMD2', _quick_job(), name='BUILD')
        assert entry is None
        assert 'ALREADY IN USE' in error

    def test_spawn_invalid_name_rejected(self, jcs):
        entry, error = jcs.spawn('CMD', _quick_job(), name='bad name!')
        assert entry is None
        assert 'INVALID JOB ID' in error

    def test_spawn_name_too_long(self, jcs):
        long_name = 'A' * (JOB_ID_MAX_LEN + 1)
        entry, error = jcs.spawn('CMD', _quick_job(), name=long_name)
        assert entry is None
        assert 'INVALID JOB ID' in error

    def test_spawn_table_full(self, jcs):
        fn, event = _blocking_job()
        try:
            for i in range(JOB_TABLE_MAX):
                _e, err = jcs.spawn(f'CMD{i}', fn)
                assert err is None
            entry, error = jcs.spawn('EXTRA', fn)
            assert entry is None
            assert 'TABLE FULL' in error
        finally:
            event.set()

    def test_reap_completed_job(self, jcs):
        entry, _ = jcs.spawn('ECHO hello', _quick_job())
        entry.thread.join(timeout=2)
        jcs.reap()
        assert entry.status in (JobStatus.DONE, JobStatus.FAILED)

    def test_reap_failed_job(self, jcs):
        entry, _ = jcs.spawn('FAIL', _quick_job(exit_code=1))
        entry.thread.join(timeout=2)
        jcs.reap()
        assert entry.status == JobStatus.FAILED
        assert entry.exit_code == 1

    def test_get_job_by_id(self, jcs):
        jcs.spawn('CMD', _quick_job(), name='MYJOB')
        job = jcs.get_job('MYJOB')
        assert job is not None
        assert job.id == 'MYJOB'

    def test_get_job_case_insensitive(self, jcs):
        jcs.spawn('CMD', _quick_job(), name='MYJOB')
        assert jcs.get_job('myjob') is not None

    def test_get_job_not_found(self, jcs):
        assert jcs.get_job('NOPE') is None

    def test_get_all_jobs(self, jcs):
        jcs.spawn('CMD1', _quick_job())
        jcs.spawn('CMD2', _quick_job())
        assert len(jcs.get_all_jobs()) == 2

    def test_get_running_jobs(self, jcs):
        fn, event = _blocking_job()
        try:
            jcs.spawn('CMD', fn)
            assert len(jcs.get_running_jobs()) == 1
        finally:
            event.set()

    def test_kill_job(self, jcs):
        fn, event = _blocking_job()
        entry, _ = jcs.spawn('CMD', fn)
        try:
            killed = jcs.kill_job(entry, force=True)
            assert killed
            assert entry.status == JobStatus.KILLED
        finally:
            event.set()

    def test_kill_completed_job_fails(self, jcs):
        entry, _ = jcs.spawn('CMD', _quick_job())
        entry.thread.join(timeout=2)
        jcs.reap()
        result = jcs.kill_job(entry)
        assert result is False

    def test_wait_job_completes(self, jcs):
        entry, _ = jcs.spawn('CMD', _quick_job())
        completed = jcs.wait_job(entry)
        assert completed
        assert entry.status == JobStatus.DONE

    def test_wait_job_timeout(self, jcs):
        fn, event = _blocking_job()
        entry, _ = jcs.spawn('CMD', fn)
        try:
            completed = jcs.wait_job(entry, timeout=0.3)
            assert not completed
            assert entry.status == JobStatus.RUNNING
        finally:
            event.set()

    def test_purge_completed(self, jcs):
        entry, _ = jcs.spawn('CMD', _quick_job())
        entry.thread.join(timeout=2)
        jcs.reap()
        purged = jcs.purge_completed()
        assert purged == 1
        assert len(jcs.get_all_jobs()) == 0

    def test_has_any_jobs(self, jcs):
        assert not jcs.has_any_jobs()
        jcs.spawn('CMD', _quick_job())
        assert jcs.has_any_jobs()

    def test_shutdown(self, jcs):
        fn, event = _blocking_job()
        try:
            jcs.spawn('CMD', fn)
            jcs.shutdown()
            assert len(jcs.get_all_jobs()) == 0
        finally:
            event.set()

    def test_job_captures_stdout(self, jcs):
        def execute_fn(stdout_cb, stderr_cb):
            stdout_cb('hello world')
            return 0

        entry, _ = jcs.spawn('CMD', execute_fn)
        entry.thread.join(timeout=2)
        assert 'hello world' in entry.stdout_buf

    def test_job_captures_stderr(self, jcs):
        def execute_fn(stdout_cb, stderr_cb):
            stderr_cb('error occurred')
            return 1

        entry, _ = jcs.spawn('CMD', execute_fn)
        entry.thread.join(timeout=2)
        assert 'error occurred' in entry.stderr_buf

    def test_exception_in_job_sets_failed(self, jcs):
        def execute_fn(stdout_cb, stderr_cb):
            raise RuntimeError('boom')

        entry, _ = jcs.spawn('CMD', execute_fn)
        entry.thread.join(timeout=2)
        jcs.reap()
        assert entry.status == JobStatus.FAILED
        assert entry.exit_code == 1
