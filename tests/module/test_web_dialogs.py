"""Tests for the dialog picker data endpoint."""

import asyncio
from types import SimpleNamespace
from unittest import mock

from module import web


class FakeClient:
    def __init__(self):
        self.peer_batches = []
        self.storage = SimpleNamespace(save=self._save)

    async def _save(self):
        self.saved = True

    async def get_dialogs(self, limit=500):
        del limit
        yield SimpleNamespace(
            chat=SimpleNamespace(
                id=777,
                title=None,
                first_name="Saved",
                last_name="Messages",
                username=None,
                type="private",
                is_self=True,
                raw=object(),
            )
        )
        yield SimpleNamespace(
            chat=SimpleNamespace(
                id=-100123,
                title="素材频道",
                first_name=None,
                last_name=None,
                username="material_channel",
                type="channel",
                is_self=False,
                raw=object(),
            )
        )

    async def fetch_peers(self, peers):
        self.peer_batches.append(peers)


def test_get_dialogs_returns_searchable_chat_metadata():
    client = FakeClient()
    with mock.patch.object(web, "_web_client", client):
        dialogs = asyncio.run(web._get_dialogs())

    assert dialogs == [
        {
            "id": "me",
            "title": "Saved Messages",
            "username": None,
            "type": "private",
        },
        {
            "id": "-100123",
            "title": "素材频道",
            "username": "material_channel",
            "type": "channel",
        },
    ]
    assert len(client.peer_batches) == 1
    assert len(client.peer_batches[0]) == 2
    assert client.saved is True
