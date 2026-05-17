# Alas-Gyre

Alas-Gyre 是一个用于配合 AzurLaneAutoScript WebUI 的轻量桌面极简控制工具。

## 功能

- 查看多个 Alas 配置的运行状态
- 启动 / 停止指定配置
- 悬浮窗状态监控
- 悬浮窗透明度调节和鼠标穿透
- 系统托盘菜单，可快速恢复主界面、打开悬浮窗、打开 Alas 主页
- 首次运行初始化向导，用于配置服务器地址并导出安装用 `fastapi.py`
- 实时日志查看和配置切换
- 导出适配后的 `fastapi.py`，用于替换到 AzurLaneAutoScript 的 `module/webui/fastapi.py`
- 使用 `X-Alas-Gyre-Token` 保护远程 API，避免无认证控制接口暴露

## 运行

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

首次运行且本地没有 `config.json` 时，会自动打开初始化向导。

## 初始化

初始化向导会引导你完成：

- 设置 AzurLaneAutoScript WebUI 的 IP 地址和端口
- 生成或填写 API Token
- 导出 `output/fastapi.py`
- 提示将导出的文件上传并覆盖到 `AzurLaneAutoScript/module/webui/fastapi.py`

覆盖后需要重启 AzurLaneAutoScript 或 WebUI 服务，再回到工具里测试连接。

## Token 与连接

打开设置窗口后可以配置 IP、服务端口和 API Token。

- 点击“生成”可创建一个随机 Token。
- 保存设置后，客户端请求会自动携带 `X-Alas-Gyre-Token`。
- “测试连接”会请求 `/api/health`，可以同时检查服务是否可访问、Token 是否正确。
- 如果导出时 Token 为空，工具会自动生成一个 Token 并保存到本地 `config.json`。

## FastAPI 文件导出

软件内置了适配后的 FastAPI payload，不依赖测试用的 AzurLaneAutoScript 目录。

在主界面底部点击导出按钮，打开导出窗口后点击 `导出 fastapi.py`，会生成：

```text
output/fastapi.py
```

将该文件上传并覆盖到：

```text
AzurLaneAutoScript/module/webui/fastapi.py
```

注意：导出的 `fastapi.py` 内含本机 API Token，不要公开上传。

## 打包

```powershell
pip install -r requirements-dev.txt
pyinstaller Alas-Gyre.spec
```

打包配置会包含：

- `ui/style.qss`
- `ui/assets/alas.ico`
- `resources/fastapi_payload.txt`

## 仓库说明

以下内容不应提交到 GitHub：

- `config.json`
- `output/`
- `build/`
- `dist/`
- `__pycache__/`
- 测试用的完整 `AzurLaneAutoScript/` 目录
