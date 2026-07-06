# Alas-Gyre

**A lightweight desktop control plane for AzurLaneAutoScript.**

Alas-Gyre helps ALAS users operate daily automation from a compact desktop client. It generates an external `gyre_runtime`, starts ALAS through the Gyre launcher, and provides remote control, multi-config status, logs, screenshots, runtime updates, and a floating monitor without modifying official ALAS source files.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-Qt-41CD52?style=flat-square&logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Client](https://img.shields.io/badge/Client-Windows%20%7C%20macOS%20%7C%20Linux-64748B?style=flat-square)](#client-setup)
[![Host](https://img.shields.io/badge/ALAS%20Host-Windows%20%7C%20Linux-0F766E?style=flat-square)](#alas-host-setup)
[![License](https://img.shields.io/badge/License-GPL--3.0-F97316?style=flat-square)](LICENSE)

[简体中文](README.zh-cn.md)

---

## Preview

### Setup Wizard

<img src="docs/images/init_preview_en.png" alt="Overlay Runtime setup wizard" width="680"/>

### Console

<img src="docs/images/ui_preview_en.png" alt="Alas-Gyre console" width="294"/>

### Multi-config Control

<img src="docs/images/multi_preview_en.png" alt="Multi-config control" width="294"/>

### Settings

<img src="docs/images/settings_preview_en.png" alt="Settings" width="720"/>

### Logs

<img src="docs/images/log_preview_en.png" alt="Log viewer" width="680"/>

### Floating Monitor

<img src="docs/images/float_preview_en.png" alt="Floating monitor" width="260"/>

## What is Alas-Gyre?

Alas-Gyre is a desktop companion for users who already run ALAS. It does not replace official ALAS files. Instead, it creates a portable `gyre_runtime` directory and loads an Overlay Runtime when ALAS starts through the Gyre launcher.

This keeps ALAS updates safe while adding day-to-day controls: start or stop configs, watch status, open logs, inspect error screenshots, update the runtime, and use a compact floating monitor.

## Features

- **Overlay Runtime** - integrates at launch time without modifying official ALAS source files.
- **Remote control** - operate ALAS running on another Windows or Linux host.
- **Multi-config dashboard** - monitor and control multiple ALAS configs independently.
- **Task visibility** - optional task-name display with translated task names and marquee labels.
- **Logs and screenshots** - view recent logs and error screenshots from the client.
- **Floating monitor** - compact always-on-top view with opacity and click-through options.
- **Runtime updater** - update launcher, overlay, and updater files after the first deployment.
- **Runtime maintenance** - bounded log rotation and low-memory cleanup for long-running hosts.
- **Stable desktop UI** - tray menu, settings entry, dark/light themes, and setup wizard.

## Platform Support

| Component | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Alas-Gyre desktop client | Release executable or source | Source run | Source run |
| ALAS host launcher | `start_gyre_alas.bat` | Not targeted | `start_gyre_alas.sh` |
| Runtime updater service | Supported | Not targeted | Supported |
| Host autostart | Manual/launcher based | Not targeted | systemd / OpenRC |

macOS/Linux desktop usage means running the client from source with Python and PySide6. Packaged desktop releases are currently focused on Windows.

## Quick Start

### 1. Generate `gyre_runtime`

Open Alas-Gyre and follow the setup wizard. The wizard generates `gyre_runtime`; the connection test is optional and can be done after ALAS is started with the launcher.

### 2. Place Runtime outside ALAS

Copy `gyre_runtime` to the machine that runs ALAS. Keep it outside the official ALAS directory so ALAS updates do not remove it.

### 3. Start ALAS through the Gyre launcher

Windows host:

```bat
start_gyre_alas.bat
```

Linux host:

```bash
chmod +x start_gyre_alas.sh
./start_gyre_alas.sh
```

Use the launcher menu to select the ALAS root, then start ALAS in foreground or background mode.

### 4. Connect from the desktop client

Return to Alas-Gyre, configure the host in Settings if needed, and run the optional connection test.

## Client Setup

### Windows client

Recommended: download the Windows release executable and run it directly.

Source run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

### macOS client

Run from source:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Use Python 3.10+.

### Linux desktop client

Run from source:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If Qt fails to start because the XCB platform plugin cannot load, install the missing Qt/XCB runtime libraries for your distribution and rerun the client.

## ALAS Host Setup

### Windows ALAS host

1. Copy `gyre_runtime` to a stable location outside the ALAS directory.
2. Run `start_gyre_alas.bat`.
3. Use the menu to select the ALAS root.
4. Start ALAS in foreground or background mode.
5. Keep using the Gyre launcher for future ALAS starts.

### Linux ALAS host

1. Upload `gyre_runtime` to a stable location outside the ALAS directory.
2. Run:

```bash
chmod +x start_gyre_alas.sh
./start_gyre_alas.sh
```

3. Use the terminal menu to select the ALAS root.
4. Start ALAS in foreground or background mode.
5. Use the launcher menu to view status, stop/restart ALAS, manage the runtime updater, and install autostart.

Linux autostart supports systemd on Debian/Ubuntu-style hosts and OpenRC on Alpine-style hosts. The launcher installs/checks common Linux dependencies before installing autostart.

## Runtime Updates

After the first deployment, Alas-Gyre can update the remote Overlay Runtime from Settings.

- Default updater listen address: `0.0.0.0:22268` for LAN access
- Managed by the launcher menu: status, start, stop, restart
- Uses the same Gyre token generated by the setup wizard
- Sends only changed runtime files
- Takes effect after ALAS is restarted through the launcher
- Do not expose the updater port to the public Internet

## Upgrade Guide

Use this process when upgrading from an older Alas-Gyre release.

### 1. Upgrade the desktop client

Windows users should download the new release executable and replace the old one. Source users should pull the latest code and reinstall dependencies if needed:

```bash
git pull
python -m pip install -r requirements.txt
python main.py
```

### 2. Upgrade `gyre_runtime`

Preferred path from the desktop client:

1. Open **Settings**.
2. Confirm the host IP, update port, and API Token.
3. Click **Update Runtime**.
4. Wait for the update result.
5. Restart ALAS from the Gyre launcher so the new overlay takes effect.

Manual path when the updater is unavailable:

1. Open the setup wizard and generate a new `gyre_runtime`.
2. Upload or copy it to the ALAS host outside the official ALAS directory.
3. Keep the same API Token, or update the client settings to match the new token.
4. Run the launcher and restart ALAS.

### 3. Reinstall Linux autostart after launcher changes

When the release changes `start_gyre_alas.sh`, reinstall the service:

```bash
cd /path/to/gyre_runtime
chmod +x start_gyre_alas.sh
./start_gyre_alas.sh
```

Then select:

```text
8) Uninstall autostart
7) Install autostart
```

Check the service:

systemd:

```bash
systemctl status alas-gyre-overlay --no-pager
journalctl -u alas-gyre-overlay -n 100 --no-pager
```

OpenRC:

```bash
rc-update show default | grep alas
rc-service alas-gyre-overlay status
tail -n 100 /path/to/gyre_runtime/.gyre_alas.log
```

If Alpine is running inside Docker, WSL, or a chroot where OpenRC is not PID 1, `rc-update` can install the service but it will not automatically start at container boot. Start it from the real init system, host panel, or container supervisor.

### 4. Verify after upgrade

- The desktop client can reach `/api/gyre/health`.
- `memory_watchdog` appears in the health response.
- `.gyre_alas.log` rotates when it reaches the configured size.
- The tray right-click menu contains **System Settings**.
- The main console keeps the bottom toolbar visible with many configs.

## Troubleshooting

### Overlay API is unavailable

Start ALAS through `start_gyre_alas.bat` or `start_gyre_alas.sh`, then run the connection test again.

### Token mismatch

Regenerate `gyre_runtime` or update the remote Runtime from Settings, then restart ALAS through the launcher so the desktop client and runtime use the same token.

### Runtime updater is unreachable

Open the launcher menu on the ALAS host and start or restart the updater service. Confirm that the LAN firewall allows the update port and that the token matches Settings.

### Autostart does not work on Linux

Check whether the host actually runs systemd or OpenRC as the init system. Docker, WSL, and chroot environments often do not run boot services even if service files can be installed.

### Linux GUI does not start

Install missing Qt/XCB runtime libraries for your distribution. This usually means Python dependencies installed correctly, but the desktop environment lacks required Qt platform libraries.

### Task text is too noisy

Disable **Show Task Name** in Settings. Long config names still scroll automatically in the main and floating windows.

## Development

Run from source:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Build the Windows package:

```powershell
pip install -r requirements-dev.txt
python -m PyInstaller Alas-Gyre.spec --noconfirm
```

## License

Alas-Gyre is released under the [GNU General Public License v3.0](LICENSE).
