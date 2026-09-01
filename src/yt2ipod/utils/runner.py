"""Asynchronous process runner for executing external tools.

Provides secure execution (no shell=True), streaming output, timeout,
and cancellation support using asyncio.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional, Tuple

from yt2ipod.core.models.errors import ProcessExecutionError, ProcessTimeoutError
from yt2ipod.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CommandResult:
    """Result of a command execution."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Check if the command exited with 0."""
        return self.exit_code == 0


class ProcessRunner:
    """Secure, async-friendly executor for external commands."""

    @staticmethod
    async def run(
        cmd: list[str],
        timeout: Optional[float] = None,
        check: bool = False,
        cwd: Optional[str] = None,
    ) -> CommandResult:
        """Run a command and capture its output entirely.

        Args:
            cmd: Command and arguments as a list.
            timeout: Maximum execution time in seconds.
            check: If True, raise ProcessExecutionError on non-zero exit.
            cwd: Current working directory for the process.

        Returns:
            CommandResult containing exit code, stdout, and stderr.

        Raises:
            ProcessTimeoutError: If the process exceeds the timeout.
            ProcessExecutionError: If check=True and exit code is non-zero.
        """
        logger.debug(f"Running command: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            if timeout is not None:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            else:
                stdout_bytes, stderr_bytes = await process.communicate()
        except asyncio.TimeoutError as e:
            process.kill()
            await process.wait()
            raise ProcessTimeoutError(f"Command timed out after {timeout}s: {cmd[0]}") from e
        except asyncio.CancelledError:
            logger.debug(f"Process cancelled: {cmd[0]}")
            process.kill()
            await process.wait()
            raise

        stdout = stdout_bytes.decode(errors="replace").strip()
        stderr = stderr_bytes.decode(errors="replace").strip()
        exit_code = process.returncode or 0

        if check and exit_code != 0:
            raise ProcessExecutionError(
                f"Command '{cmd[0]}' failed with exit code {exit_code}",
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
            )

        return CommandResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

    @staticmethod
    async def run_stream(
        cmd: list[str],
        timeout: Optional[float] = None,
        check: bool = False,
        cwd: Optional[str] = None,
    ) -> AsyncIterator[Tuple[str, str]]:
        """Run a command and stream its stdout/stderr line by line.

        This generator yields tuples of ("stdout"|"stderr", line).
        Useful for parsing progress without blocking.

        Args:
            cmd: Command and arguments as a list.
            timeout: Maximum execution time in seconds.
            check: If True, raise ProcessExecutionError on non-zero exit.
            cwd: Current working directory for the process.

        Yields:
            Tuple of (stream_name, line), where stream_name is "stdout" or "stderr".

        Raises:
            ProcessTimeoutError: If the process exceeds the timeout.
            ProcessExecutionError: If check=True and exit code is non-zero.
        """
        logger.debug(f"Streaming command: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        async def read_stream(stream: Optional[asyncio.StreamReader], name: str) -> list[Tuple[str, str]]:
            """Read stream line by line and return a list of tuples."""
            lines = []
            if stream is None:
                return lines
            while True:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode(errors="replace").rstrip('\r\n')
                lines.append((name, line))
            return lines

        # Combine streams as they arrive by creating background tasks
        q: asyncio.Queue[Optional[Tuple[str, str]]] = asyncio.Queue()

        async def _reader(stream: Optional[asyncio.StreamReader], name: str):
            if stream is not None:
                while True:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode(errors="replace").rstrip('\r\n')
                    await q.put((name, line))
            await q.put(None)  # EOF marker

        _t1 = asyncio.create_task(_reader(process.stdout, "stdout"))
        _t2 = asyncio.create_task(_reader(process.stderr, "stderr"))

        active_readers = 2

        async def stream_generator():
            nonlocal active_readers
            while active_readers > 0:
                item = await q.get()
                if item is None:
                    active_readers -= 1
                else:
                    yield item

        try:
            if timeout is not None:
                # Wrap the consumption in a timeout
                async def _consume():
                    async for item in stream_generator():
                        yield item

                # To apply timeout to a generator, we need to wrap the next() calls
                gen = stream_generator()
                while True:
                    try:
                        item = await asyncio.wait_for(gen.__anext__(), timeout=timeout)
                        yield item
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError as e:
                        process.kill()
                        await process.wait()
                        raise ProcessTimeoutError(f"Command timed out: {cmd[0]}") from e
            else:
                async for item in stream_generator():
                    yield item

            # Wait for the process to actually finish
            exit_code = await process.wait()

            if check and exit_code != 0:
                raise ProcessExecutionError(
                    f"Command '{cmd[0]}' failed with exit code {exit_code}",
                    exit_code=exit_code,
                )

        except asyncio.CancelledError:
            logger.debug(f"Stream cancelled: {cmd[0]}")
            process.kill()
            await process.wait()
            raise
