# Alas-Gyre

<div align="center">

**Elegant, secure, and ultra-lightweight desktop controller for AzurLaneAutoScript (ALAS) WebUI.**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide-6-green.svg?style=flat-square&logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d7.svg?style=flat-square&logo=windows&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange.svg?style=flat-square)](#)

[🌐 English](#alas-gyre) | [🇨🇳 简体中文](#alas-gyre---简体中文)

</div>

---

# Alas-Gyre

**Alas-Gyre** is a sleek, premium, and secure desktop companion designed exclusively for [AzurLaneAutoScript (ALAS)](https://github.com/LmeSzinc/AzurLaneAutoScript). Built with **PySide6**, it offers multi-instance status monitoring and absolute background control in a beautiful Windows 11 Fluent-inspired aesthetic, fully supporting custom dark and light themes.

<div align="center">
  <img src="ui_preview.png?v=3" alt="Alas-Gyre UI Preview" width="314"/>
  <p><em>Main Control Dashboard (Dark Mode)</em></p>
</div>

## ✨ Key Features

- **Multi-Instance Dashboard**: Monitor and control multiple ALAS configuration instances (`alas`, `alas2`, etc.) simultaneously in real-time.
- **Micro-floating Widget**: A high-performance, click-through, and translucent status widget displaying elided status strings and offering instant stop/start actions.
- **Fluent UI / UX Design**: Fully custom vector close and minimize controls, custom HSL color-tailored stylesheets, micro-animations, and complete custom dark/light modes.
- **First-Run Interactive Setup**: A beautiful initial wizard guiding you through connection validation and automated backend payload generation.
- **Real-Time Log Streamer**: Instant connection to configuration logs with full trace scroll locks and dynamic log-level colored highlight bars.
- **Token Security Guard**: Uses `X-Alas-Gyre-Token` headers for all remote requests, securely encapsulating ALAS endpoints from unauthorized local or remote access.
- **Zero-Dependency FastAPI Export**: Export pre-compiled FastAPI payloads containing your custom secret token, ready to cover `module/webui/fastapi.py`.

---

## 🚀 Getting Started

### Prerequisites
- Windows 10 / 11
- Python 3.9 or higher

### Installation

1. Clone or download the repository:
   ```powershell
   git clone https://github.com/Ange-Katrina/Alas-Gyre.git
   cd Alas-Gyre
   ```

2. Create a virtual environment and install the required packages:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Run the application:
   ```powershell
   python main.py
   ```

*Note: On your first run, the **Interactive Initialization Wizard** will automatically launch to guide you through configuration.*

---

## 🛠️ Remote Host Integration & Security

Alas-Gyre communicates with the ALAS instance over HTTP using a secure customized API token.

<div align="center">
  <img src="settings_preview.png?v=3" alt="Alas-Gyre Settings Preview" width="420"/>
  <p><em>Secure Connection Settings & Client Customization</em></p>
</div>

### 1. The Security Header
All requests sent by Alas-Gyre are validated using the header:
```http
X-Alas-Gyre-Token: <YOUR_GENERATED_API_TOKEN>
```

### 2. Deploying the FastAPI Payload
To support status calls and token validation on the ALAS server side:
1. Click the **Export (⇪)** button on the Alas-Gyre bottom dock.
2. Click **Export fastapi.py**. This generates a fully rendered `output/fastapi.py` injected with your unique API token.
3. Upload and replace the existing file on your ALAS machine:
   ```text
   AzurLaneAutoScript/module/webui/fastapi.py
   ```
4. Restart the ALAS WebUI service to apply changes.

---

## 📦 Packaging & Distribution

To compile the project into a standalone, single-executable Windows binary:

```powershell
# Install development dependencies
pip install -r requirements-dev.txt

# Run compiler using PyInstaller
pyinstaller Alas-Gyre.spec
```

The compiled binary will be located inside the `dist/` directory.

---

# Alas-Gyre - 简体中文

**Alas-Gyre** 是一款专为 [AzurLaneAutoScript (ALAS)](https://github.com/LmeSzinc/AzurLaneAutoScript) 设计的高颜值、轻量且高度安全的极简桌面控制面板。项目基于 **PySide6** 开发，采用现代 Windows 11 Fluent 风格设计，并完美原生适配深色/浅色视觉模式。

## ✨ 核心特性

- **多配置主面板**：实时查看并一键启动/停止多个 ALAS 配置实例（如 `alas`、`alas2` 等）。
- **极简状态悬浮窗**：支持鼠标穿透、透明度微调与精细文本滚动的桌面微型监控器。
- **高质感 Fluent 设计**：精致的抗锯齿矢量绘制按钮、顺滑的微交互动画，并完美支持深色/浅色双模式。
- **首航交互向导**：首次打开自动进入图形化向导，轻松录入连接配置并快速验证。
- **实时日志查看器**：动态抓取配置输出，包含滚动锁定机制以及专属高亮色彩的日志等级侧边条。
- **Token 安全屏障**：全面使用 `X-Alas-Gyre-Token` 安全头进行双向握手，彻底避免局域网内未授权的 API 操纵。
- **零依赖 FastAPI 导出**：自动嵌入您本机的密钥 Token，一键生成用于覆盖 ALAS 侧的 `fastapi.py` 控制脚本。

---

## 🚀 快速开始

### 环境准备
- 操作系统：Windows 10 / 11
- Python 版本：3.9 及以上

### 简易安装

1. 克隆或下载本项目到本地：
   ```powershell
   git clone https://github.com/Ange-Katrina/Alas-Gyre.git
   cd Alas-Gyre
   ```

2. 创建虚拟环境并安装所需依赖：
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. 启动运行：
   ```powershell
   python main.py
   ```

*注意：若本地没有检测到 `config.json`，软件会自动打开 **初始化向导** 引导您完成配置。*

---

## 🛠️ 服务端对接与安全验证

Alas-Gyre 通过内置的安全加密握手协议与 ALAS 服务端交互。

### 1. 认证安全头
客户端发出的所有请求都会强制附带如下 HTTP 请求头：
```http
X-Alas-Gyre-Token: <您的秘钥Token>
```

### 2. 部署 `fastapi.py` 载荷文件
为了让 ALAS 服务端能够校验上述安全头并响应控制指令：
1. 在主界面底栏点击 **导出 (⇪)** 图标。
2. 在弹出窗口中点击 **导出 fastapi.py**，将在本地生成内置您独立 Token 的 `output/fastapi.py` 文件。
3. 将此文件上传并覆盖到 ALAS 服务端所在目录：
   ```text
   AzurLaneAutoScript/module/webui/fastapi.py
   ```
4. 重启 ALAS 服务端或 WebUI 进程以应用该安全通道。

---

## 📦 独立程序打包

如果您需要打包生成无需 Python 环境的单文件可执行程序 (`.exe`)：

```powershell
# 安装开发打包依赖
pip install -r requirements-dev.txt

# 使用 spec 配置文件执行打包
pyinstaller Alas-Gyre.spec
```

打包完成后，您可以在 `dist/` 文件夹下找到编译好的 `Alas-Gyre.exe`！

---

## 📄 License
This project is open-source and released under the [GNU General Public License v3.0 (GPL-3.0)](LICENSE) terms.
