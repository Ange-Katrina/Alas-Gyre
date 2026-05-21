# Alas-Gyre

<div align="center">

**A compact, secure desktop controller for AzurLaneAutoScript (ALAS) WebUI.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-green.svg?style=flat-square&logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Release](https://img.shields.io/badge/Release-Windows%20binary-0078d7.svg?style=flat-square&logo=windows&logoColor=white)](https://github.com/Ange-Katrina/Alas-Gyre/releases)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange.svg?style=flat-square)](LICENSE)

[Chinese README](README.zh-CN.md)

</div>

---

Alas-Gyre is a PySide6 desktop app for controlling [AzurLaneAutoScript (ALAS)](https://github.com/LmeSzinc/AzurLaneAutoScript) through its WebUI service. It exports a customized token-protected `fastapi.py` for ALAS, then provides a clean desktop UI for status monitoring, start/stop control, logs, error screenshots and update maintenance.

The official release currently targets **Windows**. The core app is Python/PySide6 based, so macOS and Linux users can run or package it manually. Windows-only helper features are noted below.

## Screenshots

| Main Window | Multi-Config Control |
| :---: | :---: |
| <img src="docs/images/ui_preview_en.png?v=6" alt="Main window" width="314"/> | <img src="docs/images/multi_preview_en.png?v=6" alt="Multi-config control" width="314"/> |
| Single ALAS config status and control | Multiple ALAS configs with independent status/action rows |

| Settings | Logs & Error Screenshots | Floating Monitor |
| :---: | :---: | :---: |
| <img src="docs/images/settings_preview_en.png?v=6" alt="Settings" width="350"/> | <img src="docs/images/log_preview_en.png?v=6" alt="Log viewer" width="350"/> | <img src="docs/images/float_preview_en.png?v=6" alt="Floating widget" width="220"/> |
| Connection, token, theme and update options | Live logs plus ALAS error screenshot tab | Compact desktop status widget |

## Features

### ALAS control

- Read ALAS WebUI status through a token-protected API.
- Start or stop selected ALAS configs from the desktop UI.
- Detect ALAS config files such as `alas`, `alas2`, `alas3` and show them as independent rows.
- Delete ALAS config files with safety checks: the last config cannot be deleted, running configs must be stopped first, and logs are kept.
- Status polling for idle, running, error, updating and disconnected states.

### Secure `fastapi.py` payload

- Exports a customized ALAS-side `fastapi.py`.
- Embeds your local API token and validates requests with `X-Alas-Gyre-Token`.
- Adds endpoints required by Alas-Gyre: configs, status, start/stop, logs, error screenshots and payload update.
- Supports manual export to any folder.
- Supports in-app `fastapi.py` update when ALAS already uses a compatible new payload.

### First-run setup wizard

- Configures ALAS IP, port and API token.
- Generates a local token.
- Exports the customized `fastapi.py`.
- Tests the connection before entering the main UI.
- On Windows, can search for a running local ALAS process, replace `module/webui/fastapi.py`, and restart ALAS automatically.

### Logs and error screenshots

- Opens logs for the selected config.
- Reads live ALAS console output when available; otherwise falls back to the latest log file.
- Error screenshots are shown inside the log window.
- Screenshots are loaded from ALAS error records under `log/error/<timestamp>`.
- ALAS' own error-saving option must be enabled to produce screenshots.

### Floating monitor and UI preferences

- Compact floating status monitor.
- Adjustable opacity and optional click-through mode.
- Dark/light theme.
- Chinese/English UI language.
- Main window always-on-top option.
- System tray menu where the platform supports it.

### Updates

- Checks GitHub Releases from the settings window.
- Packaged builds can download and replace themselves.
- PyInstaller and Nuitka builds are distinguished, so each build updates to the matching asset.
- Auto-update is currently designed around Windows release assets. Self-built macOS/Linux users should update manually unless they also adapt release assets and updater logic.

## How it works

```text
Alas-Gyre desktop app
        |
        | HTTP + X-Alas-Gyre-Token
        v
ALAS WebUI service with generated fastapi.py
        |
        v
ALAS config/status/log/error-screenshot data
```

Important files:

| File | Purpose |
| --- | --- |
| `config.json` | Local Alas-Gyre settings. Contains your token. Ignored by Git. |
| `fastapi.py` | Generated payload for ALAS. Contains your token. Ignored by Git. |
| `resources/fastapi_payload.txt` | Template used to generate the ALAS-side `fastapi.py`. |

Do not publish `config.json` or generated `fastapi.py`.

## Download and setup

### Windows release

1. Open [Releases](https://github.com/Ange-Katrina/Alas-Gyre/releases).
2. Download the latest Windows executable.
   - `Alas-Gyre.exe`: PyInstaller build.
   - `Alas-Gyre-Nuitka.exe`: Nuitka build, when provided.
3. Put the executable in a writable folder.
4. Double-click to run.
5. Follow the first-run setup wizard.

Default ALAS WebUI address:

```text
IP:   127.0.0.1
Port: 22267
```

For remote ALAS, use the server IP and make sure the WebUI port is reachable.

### Deploy `fastapi.py`

#### Method A: Windows local ALAS auto-search

1. Start ALAS on the same Windows machine.
2. Open the setup wizard.
3. Click **Find Local ALAS**.
4. Alas-Gyre searches the running ALAS process, replaces `module/webui/fastapi.py`, and restarts ALAS.
5. Click **Test Connection**.

#### Method B: Manual export

1. Click **Export fastapi.py** in the wizard or main window.
2. Copy the generated file to:

   ```text
   AzurLaneAutoScript/module/webui/fastapi.py
   ```

3. Restart ALAS WebUI.
4. Click **Test Connection** in Alas-Gyre.

## Run from source

### Windows

```powershell
git clone https://github.com/Ange-Katrina/Alas-Gyre.git
cd Alas-Gyre
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

### macOS / Linux

```bash
git clone https://github.com/Ange-Katrina/Alas-Gyre.git
cd Alas-Gyre
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Platform notes:

- Core UI, token connection, manual `fastapi.py` export, log viewing and remote ALAS control are Python/PySide6 features.
- Windows local ALAS process search/restart is Windows-only.
- Packaged auto-update is release-asset dependent and currently Windows-focused.
- Linux tray behavior depends on the desktop environment.

## Build from source

### Build requirements

- Python 3.10+ recommended. CI uses Python 3.12.
- `pip install -r requirements.txt`.
- PyInstaller: `pip install pyinstaller` or `pip install -r requirements-dev.txt`.
- Nuitka requires a C/C++ compiler.
  - Windows: Microsoft Visual C++ Build Tools or compatible compiler.
  - macOS: Xcode Command Line Tools.
  - Linux: `gcc`/`g++`; standalone packaging commonly needs `patchelf`.

### Windows PyInstaller

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
'BUILD_FLAVOR = "pyinstaller"' | Set-Content -Encoding utf8 build_info.py
pyinstaller Alas-Gyre.spec --noconfirm
```

Output:

```text
dist/Alas-Gyre.exe
```

### Windows Nuitka

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install nuitka ordered-set zstandard
'BUILD_FLAVOR = "nuitka"' | Set-Content -Encoding utf8 build_info.py
python -m nuitka `
  --onefile `
  --enable-plugin=pyside6 `
  --assume-yes-for-downloads `
  --remove-output `
  --windows-console-mode=disable `
  --windows-icon-from-ico=ui/assets/alas.ico `
  --include-data-files=ui/style.qss=ui/style.qss `
  --include-data-files=ui/light.qss=ui/light.qss `
  --include-data-dir=ui/assets=ui/assets `
  --include-data-files=resources/fastapi_payload.txt=resources/fastapi_payload.txt `
  --output-filename=Alas-Gyre-Nuitka.exe `
  main.py
```

### macOS / Linux PyInstaller

Do not use `Alas-Gyre.spec` directly for macOS/Linux. It is optimized for Windows Qt binaries.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
printf 'BUILD_FLAVOR = "pyinstaller"\n' > build_info.py
pyinstaller --noconfirm --onefile --windowed --name Alas-Gyre \
  --add-data "ui/style.qss:ui" \
  --add-data "ui/light.qss:ui" \
  --add-data "ui/assets:ui/assets" \
  --add-data "resources/fastapi_payload.txt:resources" \
  main.py
```

### macOS / Linux Nuitka

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install nuitka ordered-set zstandard
printf 'BUILD_FLAVOR = "nuitka"\n' > build_info.py
python -m nuitka \
  --onefile \
  --enable-plugin=pyside6 \
  --assume-yes-for-downloads \
  --remove-output \
  --include-data-files=ui/style.qss=ui/style.qss \
  --include-data-files=ui/light.qss=ui/light.qss \
  --include-data-dir=ui/assets=ui/assets \
  --include-data-files=resources/fastapi_payload.txt=resources/fastapi_payload.txt \
  --output-filename=Alas-Gyre \
  main.py
```

Required runtime data files:

```text
ui/style.qss
ui/light.qss
ui/assets/**
resources/fastapi_payload.txt
```

## GitHub Actions release build

The included workflow builds Windows PyInstaller and Nuitka release assets when you push a version tag:

```bash
git tag v1.1.4
git push origin v1.1.4
```

## Troubleshooting

### Disconnected

- Confirm ALAS WebUI is running.
- Confirm IP and port are correct.
- Confirm `fastapi.py` was replaced under `AzurLaneAutoScript/module/webui/fastapi.py`.
- Restart ALAS after replacing `fastapi.py`.
- Re-export `fastapi.py` if the token changed.

### Token invalid

`config.json` and generated `fastapi.py` must contain the same token.

### Error screenshots are empty

- Enable ALAS error saving.
- Confirm ALAS has produced an error record.
- Check whether `log/error/<timestamp>` exists in the ALAS directory.

## License

Alas-Gyre is released under the [GNU General Public License v3.0](LICENSE).
