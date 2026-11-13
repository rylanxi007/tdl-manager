# TDL 管理面板

## 启动

首次运行先安装依赖：

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-manager.txt
```

双击 `start_manager.bat`，浏览器会打开：

```text
http://127.0.0.1:5080
```

管理服务只监听本机地址，不会暴露到局域网。

## 首次配置

1. 打开 <https://my.telegram.org/apps>，使用 Telegram 账号登录。
2. 创建应用，取得 `api_id` 和 `api_hash`。
3. 在管理面板的“连接设置”中填写两个值并保存。
4. 点击“启动下载”。首次运行会打开控制台，按提示完成 Telegram 登录。
5. 再次进入“连接设置”，点击“从 Telegram 选择”。
6. 搜索并勾选群组、频道或私聊，点击“应用并开始下载”，下载器会自动重启并开始处理所选会话。

也可以手动填写聊天 ID。收藏夹填写 `me`，公开频道可填写 `@channel_name`。

## 功能

- 实时显示总下载速度与每个任务的进度。
- 暂停、继续、停止下载器。
- 从 Telegram 账号的实际会话列表中选择群组、频道或私聊。
- 通过弹窗选择视频、图片、文件、音频、语音、圆形视频或动图。
- 在面板中维护 API 凭据、聊天 ID、保存目录和并行任务数。

配置直接写入项目根目录的 `config.yaml`。下载任务仍由原项目的 `media_downloader.py` 执行。

## 隐私

以下内容已被 `.gitignore` 排除，不应提交到公开仓库：

- `config.yaml`
- `data.yaml`
- `.venv/`
- `sessions/`
- `*.session`
- `log/`
- `downloads/`
- `temp/`

仓库只保留脱敏示例 `config.yaml.example` 和 `data.yaml.example`。
