# SmartParcel Gateway Qt 本地维护面板

## 定位

这个面板是 `smartparcel-gateway` 的 Linux 本地配置/维护工具，面向开发调试、初期部署和现场维护。它不是业务前端，不替代微信小程序、gateway local API 或 MQTT 主流程。

面板只作为独立工具运行，通过读取/修改 `.env`、调用现有 CLI、访问本机 local API 和只读查看 SQLite 完成维护工作。

## 安装依赖

```bash
cd smartparcel-gateway
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-qt.txt
```

也可以使用脚本：

```bash
bash scripts/install_qt_panel_deps.sh
```

## 启动方式

```bash
cd smartparcel-gateway
python tools/gateway_qt_panel/main.py
```

或：

```bash
bash scripts/run_qt_panel.sh
```

`run_qt_panel.sh` 会自动进入 `smartparcel-gateway` 目录，并优先使用 `.venv/bin/python`。

如果希望一键进入 `.venv`、启动 gateway Local API 并打开 Qt 面板：

```bash
bash scripts/quick_start_gateway_qt_panel.sh
```

默认会后台启动：

```bash
python -m gateway.main local-api --host 127.0.0.1 --port 19000
```

面板关闭后脚本会自动停止该 gateway 进程。日志写入 `logs/quick-start-local-api.log`。

如需启动完整 gateway 循环，可使用：

```bash
bash scripts/quick_start_gateway_qt_panel.sh run
```

## Linux 网关机运行方式

网关机需要具备可用的桌面环境、屏幕和输入设备。面板默认访问：

```text
http://127.0.0.1:19000
```

如果需要 BLE 标签操作，请先启动 local API：

```bash
python -m gateway.main local-api --host 127.0.0.1 --port 19000
```

## 页面功能

- 总览：查看 `.env`、SQLite、Local API、Server Health、MQTT 基础配置。
- 初期部署：从 `.env.example` 创建 `.env`，保存初始配置，执行 `init-db`、`health`、`bootstrap-activate`。
- 底层配置：通过白名单表单编辑配置，保存前自动备份。
- Server / MQTT：查看 server/MQTT 配置，测试 health，复制 topic 模板。
- BLE 设置：切换 `BLE_BACKEND`，通过 local API 扫描、查看、连接、唤醒、停止标签。
- 本地数据库：只读查看白名单 SQLite 表，每次最多 200 行。
- Local API：检查 `/local/health` 和 `/local/tags`。
- 系统服务：生成 systemd service 模板，查看服务状态，不自动安装。
- 自动启动：通过开关创建用户级 systemd 服务，并在 Linux 桌面登录后自动打开 Qt 面板。
- 日志：查看面板操作日志和命令输出。
- 危险操作：备份 `.env`、备份 SQLite、导出脱敏调试报告。

## 安全注意事项

- 保存 `.env` 前会自动生成 `.env.bak.YYYYMMDD_HHMMSS`。
- 面板不长期明文展示 `GATEWAY_SECRET`、registration token 或 MQTT password。
- 不要提交 `.env`、数据库文件、日志文件或本机 systemd 配置。
- 当前版本不提供删除数据库、清空业务数据、重建数据库、修改网络或蓝牙系统权限。

## Gateway 与 Qt 自动启动

该功能适用于带 systemd 和桌面环境的 Linux 网关机。Gateway 由用户级 systemd 服务启动；Qt 面板通过 XDG Autostart 在用户进入桌面后打开。无桌面会话时 Gateway 仍可运行，但无法显示 Qt 窗口。

可在面板“系统服务”页勾选“桌面登录后自动启动 Gateway 服务并打开 Qt 面板”，然后点击“应用自动启动开关”。也可直接使用：

```bash
bash scripts/gateway_qt_autostart.sh enable
bash scripts/gateway_qt_autostart.sh status
bash scripts/gateway_qt_autostart.sh disable
```

启用后生成用户本地文件：

```text
~/.config/systemd/user/smartparcel-gateway.service
~/.config/autostart/smartparcel-gateway-qt.desktop
```

这些运行时文件不写入仓库，也不包含 `.env` secret。启用前需安装 `.venv`、Gateway 依赖和 PySide6，并确保用户登录时存在图形桌面会话。

## 常见问题

### PySide6 安装失败

确认使用的是带桌面环境的 Linux，并升级 pip：

```bash
python -m pip install --upgrade pip
pip install -r requirements-qt.txt
```

### Local API 显示离线

先启动：

```bash
python -m gateway.main local-api --host 127.0.0.1 --port 19000
```

### BLE real 模式不可用

检查蓝牙适配器、系统权限、`BLE_BACKEND=real`，并重启 local API。

### Server health 失败

确认 `SERVER_BASE_URL` 指向 server 根地址，例如：

```text
http://127.0.0.1:18000
```
