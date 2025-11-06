from asyncio import sleep
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from hygroup.gateway.slack.utils import BurstBuffer


@pytest_asyncio.fixture
async def buffer_and_callback():
    callback = AsyncMock()
    buffer: BurstBuffer[str] = BurstBuffer(callback, min_interval=0.1)
    yield buffer, callback
    buffer.cancel()


@pytest.mark.asyncio
async def test_single_update(buffer_and_callback):
    buffer, callback = buffer_and_callback

    buffer.update("message1")
    await sleep(0.15)

    callback.assert_called_once_with(["message1"])


@pytest.mark.asyncio
async def test_multiple_updates_burst(buffer_and_callback):
    buffer, callback = buffer_and_callback

    buffer.update("message1")
    buffer.update("message2")
    buffer.update("message3")
    await sleep(0.15)

    callback.assert_called_once_with(["message1", "message2", "message3"])


@pytest.mark.asyncio
async def test_batching_with_interval(buffer_and_callback):
    buffer, callback = buffer_and_callback

    buffer.update("batch1_msg1")
    buffer.update("batch1_msg2")
    await sleep(0.15)

    buffer.update("batch2_msg1")
    await sleep(0.15)

    assert callback.call_count == 2
    callback.assert_any_call(["batch1_msg1", "batch1_msg2"])
    callback.assert_any_call(["batch2_msg1"])


@pytest.mark.asyncio
async def test_rapid_updates_during_sleep():
    callback = AsyncMock()
    buffer: BurstBuffer[str] = BurstBuffer(callback, min_interval=0.2)

    buffer.update("msg1")
    await sleep(0.25)

    buffer.update("msg2")
    buffer.update("msg3")
    buffer.update("msg4")
    await sleep(0.25)

    assert callback.call_count == 2
    callback.assert_any_call(["msg1"])
    callback.assert_any_call(["msg2", "msg3", "msg4"])
    buffer.cancel()


@pytest.mark.asyncio
async def test_cancel(buffer_and_callback):
    buffer, callback = buffer_and_callback

    buffer.cancel()
    await sleep(0.05)

    assert buffer._task.done()


@pytest.mark.asyncio
async def test_empty_queue_initially(buffer_and_callback):
    buffer, callback = buffer_and_callback

    await sleep(0.05)
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_order_preservation(buffer_and_callback):
    buffer, callback = buffer_and_callback

    messages = [f"msg{i}" for i in range(10)]
    for msg in messages:
        buffer.update(msg)

    await sleep(0.15)

    callback.assert_called_once_with(messages)


@pytest.mark.asyncio
async def test_custom_min_interval():
    callback = AsyncMock()
    buffer: BurstBuffer[str] = BurstBuffer(callback, min_interval=0.1)

    buffer.update("msg1")
    await sleep(0.15)

    callback.assert_called_once_with(["msg1"])
    buffer.cancel()


@pytest.mark.asyncio
async def test_multiple_batches_sequential(buffer_and_callback):
    buffer, callback = buffer_and_callback

    buffer.update("batch1")
    await sleep(0.15)

    buffer.update("batch2")
    await sleep(0.15)

    buffer.update("batch3")
    await sleep(0.15)

    assert callback.call_count == 3
    assert callback.call_args_list[0][0][0] == ["batch1"]
    assert callback.call_args_list[1][0][0] == ["batch2"]
    assert callback.call_args_list[2][0][0] == ["batch3"]
