"""Local management panel for Telegram Media Downloader."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml
from Crypto.Cipher import AES
from flask import Flask, jsonify, render_template, request


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"
DATA_PATH = ROOT / "data.yaml"
SESSION_PATH = ROOT / "sessions" / "media_downloader.session"
MANAGER_HOST = os.getenv("TDL_MANAGER_HOST", "127.0.0.1")
MANAGER_PORT = int(os.getenv("TDL_MANAGER_PORT", "5080"))
DOWNLOADER_LOG = ROOT / "log" / "manager-downloader.log"
STATUS_TIMEOUT = 1.0
DIALOG_TIMEOUT = 25.0

MEDIA_OPTIONS = [
    {
        "id": "video",
        "label": "视频",
        "description": "普通视频、短视频和视频消息",
    },
    {
        "id": "photo",
        "label": "图片",
        "description": "频道照片与相册图片",
    },
    {
        "id": "document",
        "label": "文件",
        "description": "PDF、压缩包及其他附件",
    },
    {
        "id": "audio",
        "label": "音频",
        "description": "音乐文件与歌曲",
    },
    {
        "id": "voice",
        "label": "语音",
        "description": "语音消息",
    },
    {
        "id": "video_note",
        "label": "圆形视频",
        "description": "Telegram 视频留言",
    },
    {
        "id": "animation",
        "label": "动图",
        "description": "GIF 与无声动画",
    },
]
MEDIA_IDS = {item["id"] for item in MEDIA_OPTIONS}
PLACEHOLDER_API_ID = "your_api_id"
PLACEHOLDER_API_HASH = "your_api_hash"
PLACEHOLDER_CHAT_ID = "telegram_chat_id"


class ConfigError(ValueError):
    """Raised when a submitted configuration is invalid."""


def _read_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as config_file:
        value = yaml.safe_load(config_file)
    return value if isinstance(value, dict) else {}


def _write_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as config_file:
        yaml.safe_dump(
            config,
            config_file,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    os.replace(temporary_path, path)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _valid_api_id(value: Any) -> str:
    api_id = _clean_text(value)
    if api_id == PLACEHOLDER_API_ID or not api_id.isdigit() or int(api_id) <= 0:
        raise ConfigError("请填写有效的 Telegram api_id（只能包含数字）。")
    return api_id


def _valid_api_hash(value: Any) -> str:
    api_hash = _clean_text(value)
    if api_hash == PLACEHOLDER_API_HASH or len(api_hash) < 16:
        raise ConfigError("请填写有效的 Telegram api_hash。")
    return api_hash


def _parse_chats(value: Any) -> list[str]:
    if isinstance(value, str):
        rows = value.replace(",", "\n").splitlines()
    elif isinstance(value, list):
        rows = value
    else:
        rows = []

    chats: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            chat_id = _clean_text(row.get("chat_id"))
        else:
            chat_id = _clean_text(row)
        if not chat_id or chat_id == PLACEHOLDER_CHAT_ID:
            continue
        if chat_id not in chats:
            chats.append(chat_id)

    return chats


def _parse_media_types(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ConfigError("请选择至少一种要下载的媒体类型。")
    media_types = [item for item in value if item in MEDIA_IDS]
    media_types = list(dict.fromkeys(media_types))
    if not media_types:
        raise ConfigError("请选择至少一种要下载的媒体类型。")
    return media_types


def _parse_positive_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, minimum), maximum)


def _chat_configs(
    chats: list[str], existing_chat_configs: Any
) -> list[dict[str, Any]]:
    existing: dict[str, dict[str, Any]] = {}
    if isinstance(existing_chat_configs, list):
        for item in existing_chat_configs:
            if not isinstance(item, dict) or "chat_id" not in item:
                continue
            existing[str(item["chat_id"])] = dict(item)

    result = []
    for chat_id in chats:
        item = existing.get(chat_id, {})
        item["chat_id"] = chat_id
        item.setdefault("last_read_message_id", 0)
        result.append(item)
    return result


def _config_summary(config: dict[str, Any]) -> dict[str, Any]:
    api_id = _clean_text(config.get("api_id"))
    api_hash = _clean_text(config.get("api_hash"))
    chats = []
    for item in config.get("chat") or []:
        if isinstance(item, dict):
            chat_id = _clean_text(item.get("chat_id"))
            if chat_id and chat_id != PLACEHOLDER_CHAT_ID:
                chats.append(chat_id)

    api_configured = (
        api_id.isdigit() and int(api_id) > 0 and len(api_hash) >= 16
    )
    return {
        "api_id": "" if api_id == PLACEHOLDER_API_ID else api_id,
        "api_hash_configured": api_configured,
        "chats": chats,
        "media_types": [
            item for item in config.get("media_types") or [] if item in MEDIA_IDS
        ],
        "save_path": _clean_text(config.get("save_path")),
        "max_download_task": _parse_positive_int(
            config.get("max_download_task"), 5, 1, 32
        ),
        "web_port": _parse_positive_int(config.get("web_port"), 5000, 1024, 65535),
        "api_configured": api_configured,
        "has_chats": bool(chats),
        "ready": api_configured,
    }


def _save_config(payload: dict[str, Any], path: Path = CONFIG_PATH) -> dict[str, Any]:
    current = _read_config(path)

    api_id = _valid_api_id(payload.get("api_id", current.get("api_id")))
    incoming_api_hash = _clean_text(payload.get("api_hash"))
    api_hash = (
        _valid_api_hash(incoming_api_hash)
        if incoming_api_hash
        else _valid_api_hash(current.get("api_hash"))
    )
    chats = _parse_chats(payload.get("chats", current.get("chat")))
    media_types = _parse_media_types(
        payload.get("media_types", current.get("media_types"))
    )

    save_path = _clean_text(payload.get("save_path", current.get("save_path")))
    if not save_path:
        save_path = str(ROOT / "downloads")

    file_formats = current.get("file_formats")
    if not isinstance(file_formats, dict):
        file_formats = {}
    for media_type in ("audio", "document", "video"):
        file_formats.setdefault(media_type, ["all"])

    current.update(
        {
            "api_id": int(api_id),
            "api_hash": api_hash,
            "chat": _chat_configs(chats, current.get("chat")),
            "media_types": media_types,
            "file_formats": file_formats,
            "save_path": save_path,
            "max_download_task": _parse_positive_int(
                payload.get("max_download_task", current.get("max_download_task")),
                5,
                1,
                32,
            ),
            "web_host": "127.0.0.1",
            "web_port": _parse_positive_int(
                payload.get("web_port", current.get("web_port")), 5000, 1024, 65535
            ),
            "keep_running": True,
        }
    )
    current.setdefault("language", "ZH")
    current.setdefault("file_path_prefix", ["chat_title", "media_datetime"])
    _write_config(current, path)
    return current


def _encrypt_web_password(password: str) -> str:
    key = b"1234123412ABCDEF"
    iv = b"ABCDEF1234123412"
    raw = password.encode("utf-8")
    padding_size = 16 - len(raw) % 16
    padded = raw + bytes([padding_size]) * padding_size
    encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(padded)
    return base64.b64encode(encrypted).decode("ascii")


class DownloaderController:
    """Start and inspect the Telegram downloader process."""

    def __init__(self, root: Path, config_path: Path):
        self.root = root
        self.config_path = config_path
        self.process: subprocess.Popen | None = None
        self.log_file = None
        self.started_at: float | None = None
        self.desired_state = "running"
        self.lock = threading.RLock()
        self.session = requests.Session()
        self.auth_signature: tuple[str, str, str] | None = None

    def _config(self) -> dict[str, Any]:
        return _read_config(self.config_path)

    def _port(self) -> int:
        return _parse_positive_int(self._config().get("web_port"), 5000, 1024, 65535)

    def _base_url(self) -> str:
        return f"http://127.0.0.1:{self._port()}"

    def _login(
        self, force: bool = False, timeout: float = STATUS_TIMEOUT
    ) -> None:
        config = self._config()
        secret = _clean_text(config.get("web_login_secret"))
        signature = (self._base_url(), secret, config.get("web_host", ""))
        if not secret:
            self.session.cookies.clear()
            self.auth_signature = signature
            return
        if not force and self.auth_signature == signature:
            return

        response = self.session.post(
            f"{self._base_url()}/login",
            data={"password": _encrypt_web_password(secret)},
            timeout=timeout,
        )
        response.raise_for_status()
        if response.json().get("code") != "1":
            raise requests.RequestException("下载器 Web 登录失败")
        self.auth_signature = signature

    def _json(self, path: str, timeout: float = STATUS_TIMEOUT) -> Any:
        self._login(timeout=timeout)
        response = self.session.get(
            f"{self._base_url()}{path}", timeout=timeout
        )
        if "text/html" in response.headers.get("content-type", ""):
            self._login(force=True, timeout=timeout)
            response = self.session.get(
                f"{self._base_url()}{path}", timeout=timeout
            )
        if response.status_code >= 400:
            try:
                message = _clean_text(response.json().get("message"))
            except (ValueError, AttributeError):
                message = ""
            raise requests.RequestException(
                message or f"下载器接口返回 HTTP {response.status_code}。"
            )
        response.raise_for_status()
        return response.json()

    def is_process_running(self) -> bool:
        with self.lock:
            return self.process is not None and self.process.poll() is None

    def _is_web_online(self) -> bool:
        try:
            self._json("/get_download_status")
            return True
        except (requests.RequestException, ValueError):
            return False

    def start(self, show_console: bool = True) -> dict[str, Any]:
        with self.lock:
            if self.is_process_running():
                return {
                    "ok": True,
                    "message": "下载器已经在运行。",
                    "state": self.desired_state,
                }

            summary = _config_summary(self._config())
            if not summary["ready"]:
                raise ConfigError("请先填写 API 信息和至少一个聊天 ID。")
            if not (self.root / "media_downloader.py").exists():
                raise ConfigError("找不到 media_downloader.py。")

            DOWNLOADER_LOG.parent.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            force_hidden = os.getenv("TDL_MANAGER_HEADLESS") == "1"
            visible_console = (
                sys.platform == "win32" and show_console and not force_hidden
            )

            command = [sys.executable, str(self.root / "media_downloader.py")]
            popen_options: dict[str, Any] = {
                "cwd": str(self.root),
                "env": env,
            }
            if visible_console:
                popen_options["creationflags"] = subprocess.CREATE_NEW_CONSOLE
            else:
                self.log_file = DOWNLOADER_LOG.open("a", encoding="utf-8")
                popen_options.update(
                    {
                        "stdin": subprocess.DEVNULL,
                        "stdout": self.log_file,
                        "stderr": subprocess.STDOUT,
                    }
                )
                if sys.platform == "win32":
                    popen_options["creationflags"] = (
                        subprocess.CREATE_NEW_PROCESS_GROUP
                    )

            self.process = subprocess.Popen(command, **popen_options)
            self.started_at = time.time()
            self.desired_state = "running"
            time.sleep(1)
            exit_code = self.process.poll()
            if exit_code is not None:
                message = self._log_tail() or f"下载器启动后立即退出，退出码 {exit_code}。"
                self.process = None
                raise ConfigError(message)

            message = (
                "已启动，并打开下载器控制台。首次登录时请按提示输入手机号和验证码。"
                if visible_console
                else "下载器已启动。"
            )
            return {"ok": True, "message": message, "state": "running"}

    def restart(self, show_console: bool = False) -> dict[str, Any]:
        with self.lock:
            was_running = self.is_process_running()
            if not was_running:
                return {
                    "ok": True,
                    "message": "聊天来源已保存。",
                    "state": "offline",
                }
            self.stop()
            result = self.start(show_console=show_console)
            result["message"] = "已应用新的聊天来源，下载任务已重新启动。"
            return result

    def stop(self) -> dict[str, Any]:
        with self.lock:
            if not self.is_process_running():
                return {"ok": True, "message": "下载器当前没有运行。"}
            assert self.process is not None
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            self.process = None
            self.started_at = None
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            return {"ok": True, "message": "下载器已停止。"}

    def _log_tail(self, line_count: int = 8) -> str:
        if not DOWNLOADER_LOG.exists():
            return ""
        try:
            lines = DOWNLOADER_LOG.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return "\n".join(lines.splitlines()[-line_count:])

    def pause_or_resume(self, state: str) -> dict[str, Any]:
        if state not in {"pause", "continue"}:
            raise ConfigError("无效的下载状态。")
        self._login()
        response = self.session.post(
            f"{self._base_url()}/set_download_state",
            params={"state": state},
            timeout=2,
        )
        response.raise_for_status()
        self.desired_state = "paused" if response.text == "continue" else "running"
        return {
            "ok": True,
            "state": self.desired_state,
            "message": "下载已暂停。" if self.desired_state == "paused" else "下载已继续。",
        }

    def dialogs(self) -> list[dict[str, Any]]:
        if os.getenv("TDL_MANAGER_DEMO") == "1" and not self._is_web_online():
            return self._demo_dialogs()
        value = self._json("/api/chats", timeout=DIALOG_TIMEOUT)
        if isinstance(value, dict) and not value.get("ok", True):
            raise requests.RequestException(
                _clean_text(value.get("message")) or "读取 Telegram 对话框失败。"
            )
        chats = value.get("chats", []) if isinstance(value, dict) else []
        return [item for item in chats if isinstance(item, dict)]

    def status(self, demo_mode: bool = False) -> dict[str, Any]:
        config = self._config()
        summary = _config_summary(config)
        process_running = self.is_process_running()
        tasks: list[dict[str, Any]] = []
        completed: list[dict[str, Any]] = []
        speed = "0 B/s"
        web_online = False
        state = "offline"
        state_label = "未启动"

        try:
            speed_value = self._json("/get_download_status")
            speed = speed_value.get("download_speed", "0 B/s")
            active_value = self._json("/get_download_list?already_down=false")
            completed_value = self._json("/get_download_list?already_down=true")
            web_online = True
            tasks = [
                self._normalise_task(item)
                for item in active_value
                if float(item.get("download_progress") or 0) < 100
            ]
            completed = [self._normalise_task(item) for item in completed_value]
            state = "paused" if self.desired_state == "paused" else "running"
            state_label = "已暂停" if state == "paused" else "下载中"
            if process_running and not SESSION_PATH.exists():
                state = "login"
                state_label = "等待 Telegram 登录"
        except (requests.RequestException, ValueError, TypeError):
            speed = "0 B/s"

        if demo_mode and not web_online and not process_running:
            tasks = self._demo_tasks()
            completed = self._demo_completed()
            speed = "24.8 MB/s"
            state = "running"
            state_label = "下载中"
            web_online = True
            session_ready = True
        else:
            session_ready = SESSION_PATH.exists()

        active_remaining = sum(
            max(
                0,
                (100 - float(item.get("progress") or 0))
                / 100
                * float(item.get("total_bytes") or 0),
            )
            for item in tasks
        )
        return {
            "downloader": {
                "online": web_online,
                "managed": process_running,
                "state": state,
                "state_label": state_label,
                "port": self._port(),
                "pid": self.process.pid if process_running and self.process else None,
                "session_ready": session_ready,
            },
            "config": summary,
            "summary": {
                "speed": speed,
                "active_count": len(tasks),
                "completed_count": len(completed),
                "remaining_bytes": active_remaining,
            },
            "tasks": tasks,
            "completed": completed[:100],
            "media_options": MEDIA_OPTIONS,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }

    @staticmethod
    def _normalise_task(item: dict[str, Any]) -> dict[str, Any]:
        total_size = _clean_text(item.get("total_size"))
        return {
            "key": f"{item.get('chat', '')}-{item.get('id', '')}",
            "chat": _clean_text(item.get("chat")),
            "message_id": _clean_text(item.get("id")),
            "filename": _clean_text(item.get("filename")),
            "total_size": total_size,
            "progress": round(float(item.get("download_progress") or 0), 1),
            "speed": _clean_text(item.get("download_speed")) or "0 B/s",
            "save_path": _clean_text(item.get("save_path")),
        }

    @staticmethod
    def _demo_tasks() -> list[dict[str, Any]]:
        return [
            {
                "key": "-1001988-48217",
                "chat": "设计素材频道",
                "message_id": "48217",
                "filename": "product_motion_reference.mp4",
                "total_size": "286.4 MB",
                "progress": 68.4,
                "speed": "16.2 MB/s",
                "save_path": "",
            },
            {
                "key": "me-3912",
                "chat": "收藏夹",
                "message_id": "3912",
                "filename": "brand_guidelines_2026.pdf",
                "total_size": "42.8 MB",
                "progress": 31.9,
                "speed": "8.6 MB/s",
                "save_path": "",
            },
            {
                "key": "-1007712-8841",
                "chat": "视频素材库",
                "message_id": "8841",
                "filename": "intro_sequence_final.mov",
                "total_size": "624.1 MB",
                "progress": 8.7,
                "speed": "5.1 MB/s",
                "save_path": "",
            },
        ]

    @staticmethod
    def _demo_completed() -> list[dict[str, Any]]:
        return [
            {
                "key": "-1001988-48201",
                "chat": "设计素材频道",
                "message_id": "48201",
                "filename": "campaign-stills.zip",
                "total_size": "118.7 MB",
                "progress": 100,
                "speed": "0 B/s",
                "save_path": "downloads/design/campaign-stills.zip",
            },
            {
                "key": "me-3888",
                "chat": "收藏夹",
                "message_id": "3888",
                "filename": "moodboard_reference.png",
                "total_size": "8.4 MB",
                "progress": 100,
                "speed": "0 B/s",
                "save_path": "downloads/saved/moodboard_reference.png",
            },
        ]

    @staticmethod
    def _demo_dialogs() -> list[dict[str, Any]]:
        return [
            {
                "id": "me",
                "title": "收藏夹",
                "username": None,
                "type": "private",
            },
            {
                "id": "-1001988123456",
                "title": "设计素材频道",
                "username": "design_assets",
                "type": "channel",
            },
            {
                "id": "-1007712889900",
                "title": "视频素材库",
                "username": None,
                "type": "supergroup",
            },
            {
                "id": "30219488",
                "title": "示例联系人",
                "username": "sample_contact",
                "type": "private",
            },
            {
                "id": "-1005531200456",
                "title": "产品与增长讨论组",
                "username": None,
                "type": "group",
            },
        ]


def create_app(
    config_path: Path = CONFIG_PATH,
    demo_mode: bool | None = None,
) -> Flask:
    """Create the local management panel application."""
    app = Flask(
        __name__,
        template_folder="manager_web/templates",
        static_folder="manager_web/static",
    )
    app.json.ensure_ascii = False
    controller = DownloaderController(ROOT, config_path)
    demo_enabled = (
        os.getenv("TDL_MANAGER_DEMO") == "1" if demo_mode is None else demo_mode
    )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        return jsonify(controller.status(demo_mode=demo_enabled))

    @app.get("/api/config")
    def config():
        return jsonify(_config_summary(_read_config(config_path)))

    @app.post("/api/config")
    def save_config():
        payload = request.get_json(silent=True) or request.form.to_dict()
        try:
            saved = _save_config(payload, config_path)
        except ConfigError as error:
            return jsonify({"ok": False, "message": str(error)}), 400
        return jsonify(
            {
                "ok": True,
                "message": "配置已保存。",
                "config": _config_summary(saved),
            }
        )

    @app.post("/api/downloader/start")
    def start_downloader():
        try:
            return jsonify(controller.start())
        except ConfigError as error:
            return jsonify({"ok": False, "message": str(error)}), 400
        except OSError as error:
            return (
                jsonify({"ok": False, "message": f"启动下载器失败：{error}"}),
                500,
            )

    @app.post("/api/downloader/stop")
    def stop_downloader():
        try:
            return jsonify(controller.stop())
        except OSError as error:
            return (
                jsonify({"ok": False, "message": f"停止下载器失败：{error}"}),
                500,
            )

    @app.post("/api/downloads/state")
    def set_download_state():
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify(controller.pause_or_resume(_clean_text(payload.get("state"))))
        except ConfigError as error:
            return jsonify({"ok": False, "message": str(error)}), 400
        except requests.RequestException:
            return (
                jsonify({"ok": False, "message": "下载器未连接，无法切换下载状态。"}),
                409,
            )

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "version": "1.0.0"})

    @app.get("/api/dialogs")
    def dialogs():
        try:
            return jsonify({"ok": True, "dialogs": controller.dialogs()})
        except requests.RequestException as error:
            error_text = _clean_text(error).lower()
            if "timed out" in error_text or "timeout" in error_text:
                message = "读取会话列表超时。请确认 Telegram 已登录，然后重试。"
            elif "connection" in error_text or "failed to establish" in error_text:
                message = "下载器尚未就绪，请等待几秒后重试。"
            else:
                message = _clean_text(error) or "请启动下载器并完成 Telegram 登录。"
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": message,
                    }
                ),
                409,
            )

    @app.post("/api/chats/select")
    def select_chats():
        payload = request.get_json(silent=True) or {}
        try:
            # Refresh dialog peers before restarting so private users and
            # access-hash-only groups remain resolvable in the new process.
            try:
                controller.dialogs()
            except requests.RequestException:
                pass
            saved = _save_config({"chats": payload.get("chats", [])}, config_path)
            result = controller.restart(show_console=False)
            result["config"] = _config_summary(saved)
            result["message"] = (
                "聊天来源已保存，下载任务已重新启动。"
                if result.get("state") == "running"
                else "聊天来源已保存。"
            )
            return jsonify(result)
        except ConfigError as error:
            return jsonify({"ok": False, "message": str(error)}), 400
        except OSError as error:
            return (
                jsonify({"ok": False, "message": f"重新启动下载器失败：{error}"}),
                500,
            )

    return app


app = create_app()


if __name__ == "__main__":
    if "--open" in sys.argv:
        threading.Timer(
            0.8,
            lambda: webbrowser.open(f"http://{MANAGER_HOST}:{MANAGER_PORT}"),
        ).start()
    app.run(MANAGER_HOST, MANAGER_PORT, debug=False, use_reloader=False)
