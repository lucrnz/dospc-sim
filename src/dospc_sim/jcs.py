"""Job Control Subsystem for background job management."""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

JOB_ID_MAX_LEN = 32
JOB_OUT_BUFSZ = 65536  # 64 KB ring buffer per stream
JOB_TABLE_MAX = 64

_JOB_ID_RE = re.compile(r'^[A-Za-z0-9_]+$')


class JobStatus(Enum):
    RUNNING = 0
    DONE = 1
    KILLED = 2
    FAILED = 3


@dataclass
class JobEntry:
    slot: int
    id: str
    thread: threading.Thread | None
    status: JobStatus = JobStatus.RUNNING
    exit_code: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    command: str = ''
    stdout_buf: str = ''
    stderr_buf: str = ''
    _cancelled: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def append_stdout(self, text: str) -> None:
        with self._lock:
            self.stdout_buf += text + '\n'
            if len(self.stdout_buf) > JOB_OUT_BUFSZ:
                self.stdout_buf = self.stdout_buf[-JOB_OUT_BUFSZ:]

    def append_stderr(self, text: str) -> None:
        with self._lock:
            self.stderr_buf += text + '\n'
            if len(self.stderr_buf) > JOB_OUT_BUFSZ:
                self.stderr_buf = self.stderr_buf[-JOB_OUT_BUFSZ:]

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled


class JobControlSubsystem:
    """Manages background jobs for a DOSShell instance."""

    def __init__(self) -> None:
        self._jobs: list[JobEntry] = []
        self._counter: int = 0
        self._lock = threading.Lock()

    def _next_id(self) -> str:
        self._counter += 1
        return f'JOB{self._counter}'

    def spawn(
        self,
        command_str: str,
        execute_fn: Callable[[Callable[[str], None], Callable[[str], None]], int],
        name: str | None = None,
    ) -> tuple[JobEntry | None, str | None]:
        """Spawn a background job.

        Args:
            command_str: The original command string for display.
            execute_fn: A callable that takes (stdout_callback, stderr_callback)
                        and returns an exit code.
            name: Optional user-specified job ID.

        Returns:
            (JobEntry, None) on success, or (None, error_message) on failure.
        """
        with self._lock:
            if len(self._jobs) >= JOB_TABLE_MAX:
                return None, f'ERROR: JOB TABLE FULL (MAX {JOB_TABLE_MAX})'

            if name is not None:
                name_upper = name.upper()
                if not _JOB_ID_RE.match(name) or len(name) > JOB_ID_MAX_LEN:
                    return None, f'ERROR: INVALID JOB ID: {name}'
                for job in self._jobs:
                    if job.id.upper() == name_upper:
                        return None, f'ERROR: JOB ID ALREADY IN USE: {name_upper}'
                job_id = name_upper
            else:
                job_id = self._next_id()

            slot = len(self._jobs) + 1
            entry = JobEntry(
                slot=slot,
                id=job_id,
                thread=None,
                command=command_str,
            )
            self._jobs.append(entry)

        def _worker() -> None:
            try:
                exit_code = execute_fn(entry.append_stdout, entry.append_stderr)
            except Exception:
                exit_code = 1
            with entry._lock:
                entry.exit_code = exit_code
                if entry._cancelled:
                    entry.status = JobStatus.KILLED
                elif exit_code == 0:
                    entry.status = JobStatus.DONE
                else:
                    entry.status = JobStatus.FAILED

        thread = threading.Thread(target=_worker, daemon=True)
        entry.thread = thread
        thread.start()
        return entry, None

    def reap(self) -> None:
        """Update status of completed jobs whose threads have exited."""
        with self._lock:
            snapshot = list(self._jobs)
        for job in snapshot:
            if (
                job.status == JobStatus.RUNNING
                and job.thread is not None
                and not job.thread.is_alive()
            ):
                with job._lock:
                    if job.status == JobStatus.RUNNING:
                        if job.exit_code == 0:
                            job.status = JobStatus.DONE
                        else:
                            job.status = JobStatus.FAILED

    def get_job(self, job_id: str) -> JobEntry | None:
        """Find a job by ID (case-insensitive)."""
        upper = job_id.upper()
        with self._lock:
            for job in self._jobs:
                if job.id.upper() == upper:
                    return job
        return None

    def get_all_jobs(self) -> list[JobEntry]:
        with self._lock:
            return list(self._jobs)

    def get_running_jobs(self) -> list[JobEntry]:
        with self._lock:
            return [j for j in self._jobs if j.status == JobStatus.RUNNING]

    def kill_job(self, job: JobEntry, force: bool = False) -> bool:
        """Request cancellation of a job.

        Sets the cancellation flag. Without force, waits up to 3 seconds
        for the thread to finish. With force, marks killed immediately.
        """
        if job.status != JobStatus.RUNNING:
            return False
        job.cancel()
        if force:
            with job._lock:
                job.status = JobStatus.KILLED
            return True
        if job.thread is not None:
            job.thread.join(timeout=3.0)
        with job._lock:
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.KILLED
        return True

    def wait_job(self, job: JobEntry, timeout: float | None = None) -> bool:
        """Wait for a job to complete.

        Returns True if the job completed, False on timeout.
        """
        if job.status != JobStatus.RUNNING:
            return True
        if job.thread is None:
            return True
        if timeout is not None:
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                job.thread.join(timeout=min(remaining, 0.25))
                if not job.thread.is_alive():
                    self.reap()
                    return True
        else:
            while job.thread.is_alive():
                job.thread.join(timeout=0.25)
            self.reap()
            return True

    def purge_completed(self) -> int:
        """Remove completed/killed/failed jobs from the table."""
        with self._lock:
            before = len(self._jobs)
            self._jobs = [j for j in self._jobs if j.status == JobStatus.RUNNING]
            return before - len(self._jobs)

    def has_any_jobs(self) -> bool:
        return self._counter > 0

    def shutdown(self) -> None:
        """Kill all running jobs and clear the table."""
        with self._lock:
            jobs = list(self._jobs)
        for job in jobs:
            if job.status == JobStatus.RUNNING:
                self.kill_job(job, force=True)
        with self._lock:
            self._jobs.clear()
