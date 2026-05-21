# Alas-Gyre

<div align="center">

**一个轻量、安全的 AzurLaneAutoScript（ALAS）桌面控制器。**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-green.svg?style=flat-square&logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Release](https://img.shields.io/badge/Release-Windows%20binary-0078d7.svg?style=flat-square&logo=windows&logoColor=white)](https://github.com/Ange-Katrina/Alas-Gyre/releases)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange.svg?style=flat-square)](LICENSE)

[English README](README.md)

</div>

---

Alas-Gyre 是一个基于 PySide6 的 ALAS 桌面控制工具。它通过导出定制版 `fastapi.py`，在 ALAS WebUI 侧增加 Token 校验和控制接口，然后在桌面端提供状态监控、启动/停止、日志查看、错误截图查看和版本维护等功能。

当前官方发布包主要面向 **Windows**。核心程序使用 Python/PySide6 编写，因此 macOS 和 Linux 用户也可以从源码运行或自行打包；Windows 专属能力会在下方单独说明。

## 界面预览

| 主窗口 | 多配置控制 |
| :---: | :---: |
| <img src="docs/images/ui_preview.png?v=6" alt="主窗口" width="314"/> | <img src="docs/images/multi_preview.png?v=6" alt="多配置控制" width="314"/> |
| 单个配置状态与启动/停止控制 | 多个 ALAS 配置独立显示状态和操作按钮 |

| 设置 | 日志与错误截图 | 悬浮窗 |
| :---: | :---: | :---: |
| <img src="docs/images/settings_preview.png?v=6" alt="设置窗口" width="350"/> | <img src="docs/images/log_preview.png?v=6" alt="日志窗口" width="350"/> | <img src="docs/images/float_preview.png?v=6" alt="悬浮窗" width="220"/> |
| 连接、Token、主题和更新设置 | 实时日志，并合并错误截图页 | 桌面悬浮状态看板 |

## 功能介绍

### ALAS 控制

- 通过 Token 保护的接口读取 ALAS WebUI 状态。
- 在桌面端启动或停止指定 ALAS 配置。
- 自动识别 `alas`、`alas2`、`alas3` 等配置，并以独立行显示。
- 删除配置时带安全限制：不能删除最后一个配置，运行中的配置需要先停止，日志文件不会被删除。
- 支持空闲、运行中、出错、更新中、未连接等状态轮询。

### 安全 `fastapi.py` 载荷

- 导出适配 Alas-Gyre 的定制 `fastapi.py`。
- 将本地 API Token 写入导出的脚本，并通过 `X-Alas-Gyre-Token` 校验请求。
- 为 Alas-Gyre 提供配置列表、状态、启动/停止、日志、错误截图、载荷更新等接口。
- 支持手动导出到任意目录。
- 已安装新版载荷的 ALAS，可在软件内直接更新 `fastapi.py` 并重启 ALAS。

### 初始化向导

- 配置 ALAS 的 IP、端口和 API Token。
- 生成本地 Token。
- 导出定制 `fastapi.py`。
- 进入主界面前测试连接。
- Windows 下可以搜索本机正在运行的 ALAS，自动替换 `module/webui/fastapi.py` 并重启 ALAS。

### 日志与错误截图

- 按当前配置打开日志窗口。
- 优先读取 ALAS 实时日志，无法读取时回退到最新日志文件。
- 错误截图功能已合并到日志窗口的“错误截图”页。
- 截图来自 ALAS 错误记录目录 `log/error/<timestamp>`。
- 需要在 ALAS 中开启官方“保存错误截图/保存错误”相关选项，出错后才会生成截图。

### 悬浮窗与界面偏好

- 小型桌面悬浮状态看板。
- 可调整透明度，并支持悬浮窗穿透。
- 深色/浅色主题。
- 中文/英文界面。
- 主窗口置顶。
- 支持系统托盘菜单的平台会显示托盘入口。

### 版本更新

- 在设置窗口检查 GitHub Releases。
- 打包版本可下载并替换自身。
- 同时支持 PyInstaller 和 Nuitka 两种构建产物：PyInstaller 版本只更新 PyInstaller 包，Nuitka 版本只更新 Nuitka 包。
- 可在设置中更新已经部署到 ALAS 的 `fastapi.py`。

## 工作原理

```text
Alas-Gyre Desktop
   |
   |  HTTP + X-Alas-Gyre-Token
   v
ALAS WebUI service with generated fastapi.py
   |
   |  status / start / stop / config / log / error screenshots
   v
AzurLaneAutoScript
```

关键文件：

| 文件 | 作用 |
| --- | --- |
| `config.json` | 本地运行配置，包含 IP、端口、Token、主题等。已被 Git 忽略。 |
| `fastapi.py` | 导出给 ALAS 使用的载荷，包含 Token。已被 Git 忽略。 |
| `resources/fastapi_payload.txt` | 生成 ALAS 侧 `fastapi.py` 的模板。 |

不要公开上传 `config.json` 或生成后的 `fastapi.py`。

## 下载与使用

### Windows 发布版

1. 打开 [Releases](https://github.com/Ange-Katrina/Alas-Gyre/releases)。
2. 下载 Windows `.exe`。
3. 运行 `Alas-Gyre.exe`。
4. 首次启动会打开初始化向导。
5. 输入 ALAS WebUI 的 IP、端口和 Token。
6. 部署 `fastapi.py`。
7. 点击“测试连接”，成功后进入主界面。

默认端口通常为：

```text
22267
```

如果你的 ALAS WebUI 使用了其他端口，请以实际配置为准。

### 部署 `fastapi.py`

#### 方法 A：Windows 本地 ALAS 自动搜索

适用于 Alas-Gyre 和 ALAS 在同一台 Windows 机器上运行。

1. 打开初始化向导。
2. 填写 IP、端口和 Token。
3. 点击“搜索本地 ALAS”。
4. Alas-Gyre 会查找正在运行的 ALAS 进程，替换 `module/webui/fastapi.py`，然后重启 ALAS。
5. 回到向导点击“测试连接”。

#### 方法 B：手动导出

适用于远程 ALAS、非 Windows 环境或自动搜索失败的情况。

1. 在向导或主窗口中点击“导出 fastapi.py”。
2. 将生成的文件复制到 ALAS 目录：

   ```text
   AzurLaneAutoScript/module/webui/fastapi.py
   ```

3. 重启 ALAS 或 WebUI 服务。
4. 回到 Alas-Gyre 点击“测试连接”。

## 从源码运行

### Windows

```powershell
git clone https://github.com/Ange-Katrina/Alas-Gyre.git
cd Alas-Gyre
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
python main.py
```

### macOS / Linux

```bash
git clone https://github.com/Ange-Katrina/Alas-Gyre.git
cd Alas-Gyre
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
python main.py
```

说明：

- 主界面、Token 连接、手动导出 `fastapi.py`、日志查看和远程 ALAS 控制属于 Python/PySide6 功能。
- “搜索本地 ALAS 并自动替换/重启”依赖 Windows 进程查询，在 macOS/Linux 上应使用手动导出。
- 系统托盘、透明窗口和置顶行为在不同桌面环境下可能表现不同。

## 从源码编译

### 编译要求

- Python 3.10 或更高版本。
- `pip install -r requirements.txt`。
- Windows 发布版推荐使用 Python 3.12。
- macOS 只能在 macOS 上编译，Linux 只能在 Linux 上编译；不要指望 PyInstaller/Nuitka 跨系统生成原生可执行文件。
- 如果使用 Nuitka，系统需要可用的 C/C++ 编译工具链。

### Windows PyInstaller

```powershell
python -m pip install -U pip
pip install -r requirements.txt
pip install pyinstaller

@'
BUILD_FLAVOR = "pyinstaller"
'@ | Set-Content -Encoding UTF8 build_info.py

pyinstaller --noconfirm --clean --onefile --windowed `
  --name Alas-Gyre `
  --icon ui/assets/alas.ico `
  --add-data "ui;ui" `
  --add-data "resources;resources" `
  main.py
```

输出文件：

```text
dist/Alas-Gyre.exe
```

### Windows Nuitka

```powershell
python -m pip install -U pip
pip install -r requirements.txt
pip install nuitka ordered-set zstandard

@'
BUILD_FLAVOR = "nuitka"
'@ | Set-Content -Encoding UTF8 build_info.py

python -m nuitka main.py `
  --onefile `
  --windows-console-mode=disable `
  --windows-icon-from-ico=ui/assets/alas.ico `
  --enable-plugin=pyside6 `
  --include-data-dir=ui=ui `
  --include-data-files=resources/fastapi_payload.txt=resources/fastapi_payload.txt `
  --output-filename=Alas-Gyre-Nuitka.exe
```

### macOS / Linux PyInstaller

```bash
python -m pip install -U pip
pip install -r requirements.txt
pip install pyinstaller

cat > build_info.py <<'PY'
BUILD_FLAVOR = "pyinstaller"
PY

pyinstaller --noconfirm --clean --onefile --windowed \
  --name Alas-Gyre \
  --add-data "ui:ui" \
  --add-data "resources:resources" \
  main.py
```

macOS 如需应用图标，请使用 `.icns` 并添加：

```bash
--icon path/to/icon.icns
```

### macOS / Linux Nuitka

```bash
python -m pip install -U pip
pip install -r requirements.txt
pip install nuitka ordered-set zstandard

cat > build_info.py <<'PY'
BUILD_FLAVOR = "nuitka"
PY

python -m nuitka main.py \
  --onefile \
  --enable-plugin=pyside6 \
  --include-data-dir=ui=ui \
  --include-data-files=resources/fastapi_payload.txt=resources/fastapi_payload.txt \
  --output-filename=Alas-Gyre
```

编译完成后，确认输出目录旁至少包含：

```text
ui/
resources/fastapi_payload.txt
```

如果打包工具没有正确内嵌资源，导出 `fastapi.py`、图标或主题会不可用。

## GitHub Actions 发布编译

仓库内置工作流会在创建 tag 时构建 Windows 发布包：

```bash
git tag v1.1.5
git push origin v1.1.5
```

工作流会生成 PyInstaller 和 Nuitka 两种 Windows 可执行文件，并写入对应的 `BUILD_FLAVOR`，用于自动更新时区分版本。

## 故障排查

### 显示未连接

- 确认 ALAS WebUI 已启动。
- 确认 IP 和端口正确。
- 确认防火墙允许访问该端口。
- 确认 `fastapi.py` 已覆盖到 `AzurLaneAutoScript/module/webui/fastapi.py`。
- 覆盖 `fastapi.py` 后需要重启 ALAS。

### Token 无效

`config.json` 和生成后的 `fastapi.py` 必须使用同一个 Token。

处理方式：

1. 在设置或向导中重新生成 Token。
2. 重新导出 `fastapi.py`。
3. 覆盖到 ALAS。
4. 重启 ALAS。

### 错误截图为空

- 在 ALAS 中开启官方保存错误截图/保存错误相关选项。
- 让 ALAS 实际产生一次错误。
- 确认 ALAS 目录存在 `log/error/<timestamp>`。
- 打开日志窗口，切换到“错误截图”页并刷新。

## 仓库清理规则

不要提交以下本地文件：

```text
config.json
fastapi.py
build_info.py
build/
dist/
*.build/
*.dist/
*.onefile-build/
*.nuitka-cache/
__pycache__/
.ruff_cache/
```

这些文件已经加入 `.gitignore`。

## 许可证

本项目基于 [GPL-3.0](LICENSE) 发布。
