"""Tests for the local management panel."""

from unittest import mock

import yaml

import manager


def _write_config(path, value):
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_config_summary_requires_account_and_chat(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        {
            "api_id": "your_api_id",
            "api_hash": "your_api_hash",
            "chat": [{"chat_id": "telegram_chat_id"}],
            "media_types": ["video"],
        },
    )

    summary = manager._config_summary(manager._read_config(config_path))

    assert summary["api_configured"] is False
    assert summary["ready"] is False


def test_config_api_saves_values_and_preserves_chat_state(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        {
            "api_id": 123456,
            "api_hash": "0123456789abcdef0123456789abcdef",
            "chat": [
                {
                    "chat_id": "me",
                    "last_read_message_id": 321,
                }
            ],
            "media_types": ["video"],
            "file_formats": {
                "audio": ["all"],
                "document": ["all"],
                "video": ["all"],
            },
        },
    )
    client = manager.create_app(config_path=config_path, demo_mode=False).test_client()

    response = client.post(
        "/api/config",
        json={
            "api_id": "654321",
            "api_hash": "",
            "chats": ["me", "@example_channel"],
            "media_types": ["photo", "document", "photo"],
            "save_path": str(tmp_path / "downloads"),
            "max_download_task": 7,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["config"]["api_id"] == "654321"
    assert payload["config"]["media_types"] == ["photo", "document"]

    saved = manager._read_config(config_path)
    assert saved["api_hash"] == "0123456789abcdef0123456789abcdef"
    assert saved["chat"][0]["last_read_message_id"] == 321
    assert saved["chat"][1]["chat_id"] == "@example_channel"
    assert saved["web_host"] == "127.0.0.1"


def test_config_rejects_placeholder_api_id(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        {
            "api_id": "your_api_id",
            "api_hash": "your_api_hash",
            "chat": [{"chat_id": "me"}],
            "media_types": ["video"],
        },
    )
    client = manager.create_app(config_path=config_path, demo_mode=False).test_client()

    response = client.post(
        "/api/config",
        json={
            "api_id": "your_api_id",
            "api_hash": "0123456789abcdef0123456789abcdef",
            "chats": ["me"],
            "media_types": ["video"],
        },
    )

    assert response.status_code == 400
    assert "api_id" in response.get_json()["message"]


def test_media_only_update_preserves_chat_ids(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        {
            "api_id": 123456,
            "api_hash": "0123456789abcdef0123456789abcdef",
            "chat": [
                {"chat_id": "me", "last_read_message_id": 42},
                {"chat_id": "@example_channel"},
            ],
            "media_types": ["video"],
        },
    )
    client = manager.create_app(config_path=config_path, demo_mode=False).test_client()

    response = client.post(
        "/api/config",
        json={"media_types": ["photo", "voice"]},
    )

    assert response.status_code == 200
    saved = manager._read_config(config_path)
    assert [item["chat_id"] for item in saved["chat"]] == [
        "me",
        "@example_channel",
    ]
    assert saved["chat"][0]["last_read_message_id"] == 42


def test_dashboard_renders_and_demo_status_has_tasks(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, {"web_port": 59999})
    client = manager.create_app(
        config_path=config_path, demo_mode=True
    ).test_client()

    page = client.get("/")
    status = client.get("/api/status")

    assert page.status_code == 200
    assert "下载总览" in page.get_data(as_text=True)
    assert status.status_code == 200
    payload = status.get_json()
    assert payload["summary"]["active_count"] == 3
    assert payload["summary"]["speed"] == "24.8 MB/s"


def test_dialog_list_is_proxied_from_downloader():
    dialogs = [
        {
            "id": "me",
            "title": "收藏夹",
            "username": None,
            "type": "private",
        },
        {
            "id": "-1001234567890",
            "title": "素材频道",
            "username": "material_channel",
            "type": "channel",
        },
    ]
    with mock.patch.object(
        manager.DownloaderController, "dialogs", return_value=dialogs
    ):
        client = manager.create_app(demo_mode=False).test_client()
        response = client.get("/api/dialogs")

    assert response.status_code == 200
    assert response.get_json()["dialogs"] == dialogs


def test_chat_selection_saves_and_restarts_downloader(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(
        config_path,
        {
            "api_id": 123456,
            "api_hash": "0123456789abcdef0123456789abcdef",
            "chat": [{"chat_id": "me", "last_read_message_id": 12}],
            "media_types": ["video"],
        },
    )
    with mock.patch.object(
        manager.DownloaderController,
        "restart",
        return_value={"ok": True, "state": "running"},
    ) as restart:
        client = manager.create_app(
            config_path=config_path, demo_mode=False
        ).test_client()
        response = client.post(
            "/api/chats/select",
            json={"chats": ["@material_channel", "-1001234567890"]},
        )

    assert response.status_code == 200
    restart.assert_called_once_with(show_console=False)
    saved = manager._read_config(config_path)
    assert [item["chat_id"] for item in saved["chat"]] == [
        "@material_channel",
        "-1001234567890",
    ]
