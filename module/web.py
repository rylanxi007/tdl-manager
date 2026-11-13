"""web ui for media download"""

import asyncio
import logging
import os
import threading

from flask import Flask, jsonify, render_template, request
from flask_login import LoginManager, UserMixin, login_required, login_user

import utils
from module.app import Application
from module.download_stat import (
    DownloadState,
    get_download_result,
    get_download_state,
    get_total_download_speed,
    set_download_state,
)
from utils.crypto import AesBase64
from utils.format import format_byte

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

_flask_app = Flask(__name__)

_flask_app.secret_key = "tdl"
_login_manager = LoginManager()
_login_manager.login_view = "login"
_login_manager.init_app(_flask_app)
web_login_users: dict = {}
deAesCrypt = AesBase64("1234123412ABCDEF", "ABCDEF1234123412")
_web_client = None
_web_loop: asyncio.AbstractEventLoop | None = None


class User(UserMixin):
    """Web Login User"""

    def __init__(self):
        self.sid = "root"

    @property
    def id(self):
        """ID"""
        return self.sid


@_login_manager.user_loader
def load_user(_):
    """
    Load a user object from the user ID.

    Returns:
        User: The user object.
    """
    return User()


def get_flask_app() -> Flask:
    """get flask app instance"""
    return _flask_app


def run_web_server(app: Application):
    """
    Runs a web server using the Flask framework.
    """

    get_flask_app().run(
        app.web_host, app.web_port, debug=app.debug_web, use_reloader=False
    )


# pylint: disable = W0603
def init_web(app: Application, client=None):
    """
    Set the value of the users variable.

    Args:
        users: The list of users to set.

    Returns:
        None.
    """
    global web_login_users
    global _web_client, _web_loop
    _web_client = client
    _web_loop = app.loop
    if app.web_login_secret:
        web_login_users = {"root": app.web_login_secret}
    else:
        _flask_app.config["LOGIN_DISABLED"] = True
    if app.debug_web:
        threading.Thread(target=run_web_server, args=(app,)).start()
    else:
        threading.Thread(
            target=get_flask_app().run, daemon=True, args=(app.web_host, app.web_port)
        ).start()


@_flask_app.route("/login", methods=["GET", "POST"])
def login():
    """
    Function to handle the login route.

    Parameters:
    - No parameters

    Returns:
    - If the request method is "POST" and the username and
      password match the ones in the web_login_users dictionary,
      it returns a JSON response with a code of "1".
    - Otherwise, it returns a JSON response with a code of "0".
    - If the request method is not "POST", it returns the rendered "login.html" template.
    """
    if request.method == "POST":
        username = "root"
        web_login_form = {}
        for key, value in request.form.items():
            if value:
                value = deAesCrypt.decrypt(value)
            web_login_form[key] = value

        if not web_login_form.get("password"):
            return jsonify({"code": "0"})

        password = web_login_form["password"]
        if username in web_login_users and web_login_users[username] == password:
            user = User()
            login_user(user)
            return jsonify({"code": "1"})

        return jsonify({"code": "0"})

    return render_template("login.html")


@_flask_app.route("/")
@login_required
def index():
    """Index html"""
    return render_template(
        "index.html",
        download_state=(
            "pause" if get_download_state() is DownloadState.Downloading else "continue"
        ),
    )


@_flask_app.route("/get_download_status")
@login_required
def get_download_speed():
    """Get download speed"""
    return (
        '{ "download_speed" : "'
        + format_byte(get_total_download_speed())
        + '/s" , "upload_speed" : "0.00 B/s" } '
    )


@_flask_app.route("/set_download_state", methods=["POST"])
@login_required
def web_set_download_state():
    """Set download state"""
    state = request.args.get("state")

    if state == "continue" and get_download_state() is DownloadState.StopDownload:
        set_download_state(DownloadState.Downloading)
        return "pause"

    if state == "pause" and get_download_state() is DownloadState.Downloading:
        set_download_state(DownloadState.StopDownload)
        return "continue"

    return state


@_flask_app.route("/get_app_version")
def get_app_version():
    """Get telegram_media_downloader version"""
    return utils.__version__


@_flask_app.route("/get_download_list")
@login_required
def get_download_list():
    """get download list"""
    if request.args.get("already_down") is None:
        return "[]"

    already_down = request.args.get("already_down") == "true"

    download_result = get_download_result()
    result = "["
    for chat_id, messages in download_result.items():
        for idx, value in messages.items():
            is_already_down = value["down_byte"] == value["total_size"]

            if already_down and not is_already_down:
                continue

            if result != "[":
                result += ","
            download_speed = format_byte(value["download_speed"]) + "/s"
            result += (
                '{ "chat":"'
                + f"{chat_id}"
                + '", "id":"'
                + f"{idx}"
                + '", "filename":"'
                + os.path.basename(value["file_name"])
                + '", "total_size":"'
                + f'{format_byte(value["total_size"])}'
                + '" ,"download_progress":"'
            )
            result += (
                f'{round(value["down_byte"] / value["total_size"] * 100, 1)}'
                + '" ,"download_speed":"'
                + download_speed
                + '" ,"save_path":"'
                + value["file_name"].replace("\\", "/")
                + '"}'
            )

    result += "]"
    return result


async def _get_dialogs(limit: int = 500) -> list[dict]:
    if _web_client is None:
        return []

    dialogs = []
    raw_peers = []
    async for dialog in _web_client.get_dialogs(limit=limit):
        chat = dialog.chat
        raw_chat = getattr(chat, "raw", None)
        if raw_chat is not None:
            raw_peers.append(raw_chat)
        if getattr(chat, "is_self", False):
            chat_id = "me"
        else:
            chat_id = str(chat.id)

        title = (
            getattr(chat, "title", None)
            or " ".join(
                part
                for part in [
                    getattr(chat, "first_name", None),
                    getattr(chat, "last_name", None),
                ]
                if part
            )
            or getattr(chat, "username", None)
            or chat_id
        )
        chat_type = str(getattr(chat, "type", "")).split(".")[-1] or "chat"
        dialogs.append(
            {
                "id": chat_id,
                "title": title,
                "username": getattr(chat, "username", None),
                "type": chat_type,
            }
        )

    if raw_peers:
        # Dialog results don't persist access hashes by themselves. Store them
        # so a restarted downloader can resolve users and private groups.
        await _web_client.fetch_peers(raw_peers)
        await _web_client.storage.save()

    return sorted(dialogs, key=lambda item: item["title"].casefold())


@_flask_app.route("/api/chats")
@login_required
def get_chat_list():
    """Return dialogs from the connected Telegram account."""
    if _web_client is None or _web_loop is None:
        return jsonify(
            {"ok": False, "message": "Telegram 客户端尚未创建。"}
        ), 503
    if not _web_client.is_connected:
        return jsonify(
            {"ok": False, "message": "请先在下载器控制台完成 Telegram 登录。"}
        ), 503

    try:
        future = asyncio.run_coroutine_threadsafe(_get_dialogs(), _web_loop)
        chats = future.result(timeout=20)
    except Exception as error:
        return jsonify({"ok": False, "message": str(error)}), 503

    return jsonify({"ok": True, "chats": chats})
