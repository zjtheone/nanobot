"""Test message tool tracking and send callback."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.tools.message import MessageTool
from nanobot.bus.events import OutboundMessage


class TestMessageToolTurnTracking:

    def test_sent_in_turn_tracks_state(self) -> None:
        tool = MessageTool()
        tool.set_context("feishu", "chat1")
        assert not tool._sent_in_turn
        tool._sent_in_turn = True
        assert tool._sent_in_turn

    def test_start_turn_resets(self) -> None:
        tool = MessageTool()
        tool._sent_in_turn = True
        tool.start_turn()
        assert not tool._sent_in_turn

    def test_set_context(self) -> None:
        tool = MessageTool()
        tool.set_context("telegram", "user123", "msg456")
        assert tool._default_channel == "telegram"
        assert tool._default_chat_id == "user123"
        assert tool._default_message_id == "msg456"

    def test_set_send_callback(self) -> None:
        tool = MessageTool()
        callback = AsyncMock()
        tool.set_send_callback(callback)
        assert tool._send_callback is callback

    @pytest.mark.asyncio
    async def test_execute_sends_message(self) -> None:
        sent: list[OutboundMessage] = []

        async def capture(msg: OutboundMessage) -> None:
            sent.append(msg)

        tool = MessageTool(send_callback=capture, default_channel="feishu", default_chat_id="chat1")

        result = await tool.execute(content="Hello!", channel="feishu", chat_id="chat1")

        assert len(sent) == 1
        assert sent[0].content == "Hello!"
        assert sent[0].channel == "feishu"
        assert sent[0].chat_id == "chat1"
        assert tool._sent_in_turn
