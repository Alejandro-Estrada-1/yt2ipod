"""Tests for the ProcessRunner utility."""

import asyncio
import sys

import pytest

from yt2ipod.core.models.errors import ProcessExecutionError, ProcessTimeoutError
from yt2ipod.utils.runner import ProcessRunner


@pytest.mark.asyncio
async def test_run_success():
    """Test successful command execution."""
    result = await ProcessRunner.run(["echo", "hello world"])
    assert result.exit_code == 0
    assert result.success
    assert result.stdout == "hello world"
    assert result.stderr == ""


@pytest.mark.asyncio
async def test_run_failure():
    """Test failing command execution without check=True."""
    # Using python -c instead of false to ensure cross-platform consistency
    result = await ProcessRunner.run([sys.executable, "-c", "import sys; sys.exit(1)"])
    assert result.exit_code == 1
    assert not result.success


@pytest.mark.asyncio
async def test_run_check_raises():
    """Test check=True raises ProcessExecutionError on failure."""
    with pytest.raises(ProcessExecutionError) as exc_info:
        await ProcessRunner.run(
            [sys.executable, "-c", "import sys; sys.stderr.write('error msg\\n'); sys.exit(2)"],
            check=True
        )

    assert exc_info.value.exit_code == 2
    assert exc_info.value.stderr == "error msg"


@pytest.mark.asyncio
async def test_run_timeout():
    """Test timeout support."""
    with pytest.raises(ProcessTimeoutError):
        # Sleep for 1 second, but timeout after 0.1
        await ProcessRunner.run([sys.executable, "-c", "import time; time.sleep(1)"], timeout=0.1)


@pytest.mark.asyncio
async def test_run_cancellation():
    """Test cancellation cleans up the process."""
    task = asyncio.create_task(
        ProcessRunner.run([sys.executable, "-c", "import time; time.sleep(5)"])
    )

    # Let it start
    await asyncio.sleep(0.1)

    # Cancel it
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_run_stream():
    """Test streaming output line by line."""
    script = (
        "import sys, time\n"
        "sys.stdout.write('line1\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(0.1)\n"
        "sys.stderr.write('err1\\n')\n"
        "sys.stderr.flush()\n"
        "sys.stdout.write('line2\\n')\n"
    )

    items = []
    async for name, line in ProcessRunner.run_stream([sys.executable, "-c", script]):
        items.append((name, line))

    assert ("stdout", "line1") in items
    assert ("stderr", "err1") in items
    assert ("stdout", "line2") in items
    assert len(items) == 3


@pytest.mark.asyncio
async def test_run_stream_timeout():
    """Test timeout during stream."""
    script = (
        "import sys, time\n"
        "sys.stdout.write('first\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(5)\n"
        "sys.stdout.write('second\\n')\n"
    )

    items = []
    with pytest.raises(ProcessTimeoutError):
        async for name, line in ProcessRunner.run_stream([sys.executable, "-c", script], timeout=0.5):
            items.append((name, line))

    assert len(items) == 1
    assert items[0] == ("stdout", "first")


@pytest.mark.asyncio
async def test_run_stream_check_raises():
    """Test run_stream raises on failure if check=True."""
    script = "import sys; sys.exit(42)"

    with pytest.raises(ProcessExecutionError) as exc_info:
        async for _ in ProcessRunner.run_stream([sys.executable, "-c", script], check=True):
            pass

    assert exc_info.value.exit_code == 42


@pytest.mark.asyncio
async def test_shell_injection_prevention():
    """Arguments should be passed exactly, not evaluated by shell."""
    # If run in shell, this would echo "hello" and then exit 0
    # As a list arg, it just echoes the literal string
    result = await ProcessRunner.run(["echo", "hello && exit 1"])
    assert result.exit_code == 0
    assert result.stdout == "hello && exit 1"
