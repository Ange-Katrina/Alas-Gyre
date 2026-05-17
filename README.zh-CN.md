# Alas-Gyre - 简体中文

<div align="center">

**专为 AzurLaneAutoScript (ALAS) WebUI 设计的高颜值、轻量级、安全的桌面极简控制面板。**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide-6-green.svg?style=flat-square&logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d7.svg?style=flat-square&logo=windows&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange.svg?style=flat-square)](#)

[🌐 English](README.md)

</div>

---

**Alas-Gyre** 是一款专为 [AzurLaneAutoScript (ALAS)](https://github.com/LmeSzinc/AzurLaneAutoScript) 设计的高颜值、轻量且高度安全的极简桌面控制面板。项目基于 **PySide6** 开发，采用现代 Windows 11 Fluent 风格设计，并完美原生适配深色/浅色双重视觉模式。

### 📸 软件界面效果展示

| 单实例主界面 | 多配置实例并行运行 |
| :---: | :---: |
| <img src="ui_preview.png?v=4" alt="单实例主界面" width="314"/> | <img src="multi_preview.png?v=4" alt="多配置实例主界面" width="314"/> |
| *极简单配置卡片面板* | *多配置实例并行并发控制与心跳* |

| 安全连接与个性化设置 | 实时日志高亮流式查看器 | 桌面上层透明呼吸悬浮窗 |
| :---: | :---: | :---: |
| <img src="settings_preview.png?v=4" alt="设置界面" width="350"/> | <img src="log_preview.png?v=4" alt="日志查看器" width="350"/> | <img src="float_preview.png?v=4" alt="悬浮窗" width="220"/> |
| *安全认证连接设置* | *动态日志等级染色高亮面板* | *鼠标穿透与半透明桌面监控* |

## ✨ 核心特性

- **多配置主面板**：实时查看并一键启动/停止多个 ALAS 配置实例（如 `alas`、`alas2` 等）。
- **极简状态悬浮窗**：支持鼠标穿透、透明度微调与精细文本滚动的桌面微型监控器。
- **高质感 Fluent 设计**：精致的抗锯齿矢量绘制按钮、顺滑的微交互动画，并完美支持深色/浅色双模式。
- **首航交互向导**：首次打开自动进入图形化向导，轻松录入连接配置并快速验证。
- **实时日志查看器**：动态抓取配置输出，包含滚动锁定机制以及专属高亮色彩的日志等级侧边条。
- **Token 安全屏障**：全面使用 `X-Alas-Gyre-Token` 安全头进行双向安全握手，彻底避免未授权的 API 操纵。
- **零依赖 FastAPI 导出**：自动嵌入您本机的独立密钥 Token，一键生成用于覆盖 ALAS 侧的 `fastapi.py` 控制脚本。

---

## 🚀 快速开始

### 📦 下载与运行（推荐方式）
这是使用 Alas-Gyre 最为简单快捷的方式。您**无需安装 Python** 环境，也无需克隆项目！

1. 前往本仓库的 [Releases](https://github.com/Ange-Katrina/Alas-Gyre/releases) 发布页面。
2. 下载最新编译打包好的单文件执行程序：**`Alas-Gyre.exe`**。
3. 将下载好的 `Alas-Gyre.exe` 移动到您电脑的任意文件夹中，**直接双击运行**即可！
   *(首次打开时，软件会自动弹出 **交互式初始化向导** 引导您完成所有连接设置。)*

---

### 💻 源码运行与开发（开发者指南）
如果您想直接通过原始 Python 运行程序或进行二次开发：

#### 环境要求
- 操作系统：Windows 10 / 11
- Python 版本：3.9 及以上

#### 操作步骤
1. 克隆本项目到本地：
   ```powershell
   git clone https://github.com/Ange-Katrina/Alas-Gyre.git
   cd Alas-Gyre
   ```
2. 创建虚拟环境并安装运行依赖：
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. 启动运行：
   ```powershell
   python main.py
   ```

---

## 🛠️ 服务端对接与安全验证

Alas-Gyre 通过内置的安全加密握手协议与 ALAS 服务端交互。

<div align="center">
  <img src="settings_preview.png?v=4" alt="Alas-Gyre 设置界面预览" width="420"/>
  <p><em>安全连接配置与客户端个性化设置</em></p>
</div>

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

## 📄 开源协议
本项目完全开源，遵循 [GNU General Public License v3.0 (GPL-3.0)](LICENSE) 许可协议。
