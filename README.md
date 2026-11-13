<h1 align="center">TDL Manager</h1>

<p align="center">
  Telegram 媒体下载器可视化管理面板
</p>

<p align="center">
  <a href="./README.md">中文</a> ·
  <a href="./README_EN.md">English</a> ·
  <a href="https://github.com/rylanxi007/tdl-manager/issues">问题反馈</a>
</p>

> 本项目基于
> [tangyoha/telegram_media_downloader](https://github.com/tangyoha/telegram_media_downloader)
> 扩展，新增独立 Web 管理面板、真实 Telegram 会话选择、任务可视化和安全配置流程。

## 管理入口

正常使用时访问：

```text
http://127.0.0.1:5080
```

端口说明：

| 端口 | 用途 | 是否需要手动访问 |
| --- | --- | --- |
| `5080` | TDL Manager 管理面板 | 是，日常操作入口 |
| `5000` | 原下载器内部 Web/状态服务 | 否，由管理面板自动访问 |

## 这个改版解决了什么

原下载器功能完整，但配置、会话选择和任务观察主要依赖手动编辑配置文件或简表页面。TDL Manager 在此基础上增加了完整的可视化管理流程：

- **管理面板先启动**：即使尚未填写 Telegram API，也可以先打开面板再配置，不再因为占位配置立即退出。
- **表单化配置**：在页面中填写 `api_id`、`api_hash`、聊天 ID、保存目录和并行任务数。
- **真实会话选择**：登录 Telegram 后读取账号中的群组、频道、超级群组和私聊，支持搜索与多选。
- **重启后仍可解析会话**：持久化 Telegram peer access hash，修复私聊或私有群组重启后出现 `PEER_ID_INVALID` 的问题。
- **实时任务视图**：显示总下载速度、单任务速度、进度、文件大小、来源和保存路径。
- **任务控制**：支持暂停、继续、停止下载器。
- **媒体类型选择**：通过弹窗选择视频、图片、文件、音频、语音、圆形视频或动图。
- **应用会话后自动重启**：选择新的群组或对话后保存配置，并自动重启下载任务。
- **本地访问**：管理面板默认只监听 `127.0.0.1`，不暴露到局域网。
- **凭据隔离**：真实配置、session、日志和下载内容均被 `.gitignore` 排除。

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
```

Windows：

```bat
.venv\Scripts\python.exe -m pip install -r requirements-manager.txt
```

Linux / macOS：

```bash
.venv/bin/python -m pip install -r requirements-manager.txt
```

### 2. 启动管理面板

Windows 可双击：

```text
start_manager.bat
```

也可以直接运行：

```bash
python manager.py --open
```

管理面板地址：

```text
http://127.0.0.1:5080
```

### 3. 配置 Telegram

1. 打开 <https://my.telegram.org/apps>。
2. 创建应用并取得 `api_id` 和 `api_hash`。
3. 在“连接设置”中填写并保存。
4. 点击“启动下载”。
5. 首次运行会打开下载器控制台，按提示输入 Telegram 手机号、验证码和两步验证密码。
6. 登录完成后，点击“从 Telegram 选择”。
7. 搜索并勾选要下载的群组、频道或私聊。
8. 点击“应用并开始下载”。

收藏夹可手动填写 `me`，公开频道可使用 `@channel_name`。

## 功能界面

管理面板包含：

- 下载总览
- 实时速度
- 活动任务
- 已完成文件
- 保存目录
- 任务搜索
- 连接状态
- 下载范围
- Telegram 会话选择
- 连接设置
- 首次登录控制台提示

## 项目结构

```text
manager.py                 管理面板与下载器进程控制
manager_web/               管理面板前端
media_downloader.py        原下载器入口
module/                    下载、Web、Telegram 扩展模块
config.yaml.example        脱敏配置示例
data.yaml.example          脱敏运行数据示例
MANAGER_README_CN.md       管理面板补充说明
```

## 配置文件与隐私

管理面板会把真实配置写入项目根目录的 `config.yaml`。

以下内容已在 `.gitignore` 中排除：

- `config.yaml`
- `data.yaml`
- `.venv/`
- `sessions/`
- `*.session`
- `log/`
- `downloads/`
- `temp/`

请勿提交真实的 API 凭据、Telegram session、日志或下载文件。

## 原项目与说明

- 上游项目：
  [tangyoha/telegram_media_downloader](https://github.com/tangyoha/telegram_media_downloader)
- 英文说明：[README_EN.md](./README_EN.md)
- 上游中文说明：[README_CN.md](./README_CN.md)
- 管理面板补充说明：[MANAGER_README_CN.md](./MANAGER_README_CN.md)
- License: MIT
