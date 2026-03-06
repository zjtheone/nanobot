import asyncio

import pytest

from nanobot.heartbeat.service import HeartbeatService


class FakeToolCall:
    def __init__(self, args):
        self.arguments = args


class FakeResponse:
    def __init__(self, action="skip", tasks=""):
        self.has_tool_calls = action != "skip"
        self.tool_calls = [FakeToolCall({"action": action, "tasks": tasks})] if self.has_tool_calls else []


class FakeProvider:
    async def chat(self, **kwargs):
        return FakeResponse("skip")


@pytest.mark.asyncio
async def test_start_is_idempotent(tmp_path) -> None:
    service = HeartbeatService(
        workspace=tmp_path,
        provider=FakeProvider(),
        model="test-model",
        interval_s=9999,
        enabled=True,
    )

    await service.start()
    first_task = service._task
    await service.start()

    assert service._task is first_task

    service.stop()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_start_disabled(tmp_path) -> None:
    service = HeartbeatService(
        workspace=tmp_path,
        provider=FakeProvider(),
        model="test-model",
        interval_s=9999,
        enabled=False,
    )

    await service.start()
    assert service._task is None
