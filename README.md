# Alas-Gyre

<div align="center">

**Elegant, secure, and ultra-lightweight desktop controller for AzurLaneAutoScript (ALAS) WebUI.**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide-6-green.svg?style=flat-square&logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d7.svg?style=flat-square&logo=windows&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange.svg?style=flat-square)](#)

[🇨🇳 简体中文](README.zh-CN.md)

</div>

---

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

## 📄 License
This project is open-source and released under the [GNU General Public License v3.0 (GPL-3.0)](LICENSE) terms.
