# Alas-Gyre

**面向 AzurLaneAutoScript 的轻量桌面控制端。**

Alas-Gyre 为 ALAS 用户提供更清晰的日常操作方式：生成外置 `gyre_runtime`，通过 Gyre 启动器启动 ALAS，然后在桌面客户端集中管理配置、状态、日志、截图和 Runtime 更新。Alas-Gyre 不修改 ALAS 官方源码。

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-Qt-41CD52?style=flat-square&logo=qt&logoColor=white)](https://pypi.org/project/PySide6/)
[![Client](https://img.shields.io/badge/Client-Windows%20%7C%20macOS%20%7C%20Linux-64748B?style=flat-square)](#客户端使用)
[![Host](https://img.shields.io/badge/ALAS%20Host-Windows%20%7C%20Linux-0F766E?style=flat-square)](#alas-运行端设置)
[![License](https://img.shields.io/badge/License-GPL--3.0-F97316?style=flat-square)](LICENSE)

[English](README.md)

---

## 界面预览

### 初始化向导

<img src="docs/images/init_preview.png" alt="Overlay Runtime 初始化向导" width="680"/>

### 主控制台

<img src="docs/images/ui_preview.png" alt="Alas-Gyre 主控制台" width="294"/>

### 多配置控制

<img src="docs/images/multi_preview.png" alt="多配置控制" width="294"/>

### 设置

<img src="docs/images/settings_preview.png" alt="系统设置" width="720"/>

### 日志

<img src="docs/images/log_preview.png" alt="日志查看器" width="680"/>

### 悬浮监控

<img src="docs/images/float_preview.png" alt="悬浮监控窗口" width="260"/>

## Alas-Gyre 是什么？

Alas-Gyre 是给 ALAS 用户使用的桌面客户端。它不会替换 ALAS 官方文件，而是生成一个可移动的 `gyre_runtime` 目录，并通过启动器在 ALAS 启动时加载 Overlay Runtime。

这样可以在不影响 ALAS 更新的前提下增加日常控制能力：启动/停止配置、查看状态、打开日志、查看错误截图、更新 Runtime，以及使用悬浮监控窗口。

## 功能特性

- **Overlay Runtime**：启动时接入 ALAS，不修改 ALAS 官方源码。
- **远程控制**：从桌面客户端控制 Windows 或 Linux 设备上的 ALAS。
- **多配置面板**：集中显示多个 ALAS 配置，并可分别启动、停止和查看状态。
- **任务名称显示**：可选显示当前任务名，支持任务名翻译和长文本滚动。
- **日志与截图**：在客户端查看运行日志和错误截图。
- **悬浮监控**：提供置顶小窗，支持透明度和点击穿透。
- **Runtime 更新**：首次部署后，可通过更新服务维护启动器、Overlay 和 Updater。
- **Runtime 维护**：支持日志轮转和低内存温和清理，适合长期运行。
- **稳定桌面体验**：托盘菜单、设置入口、深色/浅色主题和初始化向导。

## 平台支持

| 组件 | Windows | macOS | Linux |
| --- | --- | --- | --- |
| Alas-Gyre 桌面客户端 | Release exe 或源码运行 | 源码运行 | 源码运行 |
| ALAS 运行端启动器 | `start_gyre_alas.bat` | 暂不作为目标平台 | `start_gyre_alas.sh` |
| Runtime 更新服务 | 支持 | 暂不作为目标平台 | 支持 |
| 开机自启动 | 通过启动器/系统方式 | 暂不作为目标平台 | systemd / OpenRC |

macOS/Linux 桌面客户端目前以 Python + PySide6 源码运行方式使用。正式打包发布主要面向 Windows。

## 快速开始

### 1. 生成 `gyre_runtime`

打开 Alas-Gyre，按照初始化向导生成 `gyre_runtime`。连接测试是可选项，可以等 ALAS 通过启动器启动后再测试。

### 2. 将 Runtime 放在 ALAS 目录外

把 `gyre_runtime` 复制到运行 ALAS 的设备上。建议放在 ALAS 官方目录外，避免 ALAS 更新时被覆盖或删除。

### 3. 通过 Gyre 启动器启动 ALAS

Windows 运行端：

```bat
start_gyre_alas.bat
```

Linux 运行端：

```bash
chmod +x start_gyre_alas.sh
./start_gyre_alas.sh
```

在启动器菜单中选择 ALAS 根目录，然后以前台或后台模式启动 ALAS。

### 4. 回到桌面客户端连接

回到 Alas-Gyre，根据需要在设置中填写主机信息，并执行可选连接测试。

## 客户端使用

### Windows 客户端

推荐直接下载 Windows Release exe 运行。

也可以从源码运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

### macOS 客户端

从源码运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

需要 Python 3.10+。

### Linux 桌面客户端

从源码运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

如果 Qt 因 XCB platform plugin 无法启动，请为当前发行版安装缺失的 Qt/XCB 运行库。

## ALAS 运行端设置

### Windows 运行端

1. 将 `gyre_runtime` 放到 ALAS 目录外的稳定位置。
2. 运行 `start_gyre_alas.bat`。
3. 在菜单中选择 ALAS 根目录。
4. 以前台或后台模式启动 ALAS。
5. 之后继续通过 Gyre 启动器启动 ALAS。

### Linux 运行端

1. 将 `gyre_runtime` 上传到 ALAS 目录外的稳定位置。
2. 执行：

```bash
chmod +x start_gyre_alas.sh
./start_gyre_alas.sh
```

3. 在终端菜单中选择 ALAS 根目录。
4. 以前台或后台模式启动 ALAS。
5. 通过启动器菜单查看状态、停止/重启 ALAS、管理 Runtime 更新服务和安装开机自启动。

Linux 自启动支持 Debian/Ubuntu 等 systemd 环境，以及 Alpine 等 OpenRC 环境。安装自启动前，启动器会自动安装/检查常用 Linux 依赖。

## Runtime 更新

首次部署完成后，可以在设置页更新远端 Overlay Runtime。

- 默认更新服务监听地址：`0.0.0.0:22268`，支持局域网访问。
- 可通过启动器菜单管理：查看状态、启动、停止、重启。
- 使用初始化向导生成的同一个 Gyre Token。
- 只传输发生变化的 Runtime 文件。
- 更新后需要通过启动器重启 ALAS 才会生效。
- 不建议把更新服务端口暴露到公网。

## 升级说明

从旧版本升级时建议按以下流程执行。

### 1. 升级桌面客户端

Windows 用户下载新版 Release exe 后替换旧版即可。源码用户执行：

```bash
git pull
python -m pip install -r requirements.txt
python main.py
```

### 2. 升级 `gyre_runtime`

推荐使用客户端设置页更新：

1. 打开 **设置**。
2. 确认主机 IP、更新端口和 API Token。
3. 点击 **更新 Runtime**。
4. 等待更新结果。
5. 通过 Gyre 启动器重启 ALAS，使新的 Overlay 生效。

如果更新服务不可用，使用手动方式：

1. 打开初始化向导，重新生成 `gyre_runtime`。
2. 将新的 `gyre_runtime` 上传或复制到 ALAS 运行端，仍然放在 ALAS 官方目录外。
3. 保持 API Token 一致，或同步修改客户端设置中的 Token。
4. 运行启动器并重启 ALAS。

### 3. Web-Scrcpy 网关接口升级

本版本新增给 Web-Scrcpy 后端使用的网关接口：

```text
GET  /api/gyre/config?config=<name>
PUT  /api/gyre/config?config=<source>&target=<target>
POST /api/gyre/restart?config=<name>
```

升级 `gyre_runtime` 并重启 ALAS 后，Web-Scrcpy 后端可以携带 Gyre Token 调用这些接口。不要把 Gyre Token 暴露给浏览器，也不要让浏览器直接调用 Gyre Runtime。Web-Scrcpy 仍然需要自己维护用户与 ALAS 配置的绑定关系，并且只把用户绑定的配置名传给 Gyre Runtime。

Web-Scrcpy 验证清单：

- 普通用户不能调用 `/api/gyre/configs`；
- 普通用户只能使用自己绑定的配置名；
- 保存配置时请求体使用 `{"data": {...}}`；
- 错误恢复优先调用 `/api/gyre/restart`，不要再依赖手动 stop/start 组合。

### 4. 启动器变更后重新安装 Linux 自启动

如果新版修改了 `start_gyre_alas.sh`，需要重新安装服务：

```bash
cd /path/to/gyre_runtime
chmod +x start_gyre_alas.sh
./start_gyre_alas.sh
```

然后选择：

```text
8) 卸载开机自启动
7) 安装开机自启动
```

检查 systemd：

```bash
systemctl status alas-gyre-overlay --no-pager
journalctl -u alas-gyre-overlay -n 100 --no-pager
```

检查 OpenRC：

```bash
rc-update show default | grep alas
rc-service alas-gyre-overlay status
tail -n 100 /path/to/gyre_runtime/.gyre_alas.log
```

如果 Alpine 运行在 Docker、WSL 或 chroot 中，且 OpenRC 不是 PID 1，`rc-update` 可能能安装服务，但容器启动时不会自动运行服务。此时需要由宿主机、面板或容器 supervisor 拉起脚本。

### 5. 升级后验证

- 桌面客户端可以连接 `/api/gyre/health`。
- health 响应中包含 `memory_watchdog`。
- `.gyre_alas.log` 达到配置大小后会轮转。
- 托盘右键菜单包含 **系统设置**。
- 多配置较多时，主界面底部工具栏仍保持可见。

## 常见问题

### Overlay API 不可用

请通过 `start_gyre_alas.bat` 或 `start_gyre_alas.sh` 启动 ALAS，然后重新测试连接。

### Token 不一致

重新生成 `gyre_runtime`，或在设置中更新远端 Runtime，然后通过启动器重启 ALAS，确保桌面客户端和 Runtime 使用同一个 Token。

### Runtime 更新服务不可达

在 ALAS 所在设备上打开启动器菜单，启动或重启更新服务。确认局域网防火墙允许更新端口，并确认端口和 Token 与设置页一致。

### Linux 自启动无效

确认主机实际使用 systemd 或 OpenRC 作为 init 系统。Docker、WSL、chroot 环境即使可以安装 service 文件，也通常不会自动运行开机服务。

### Linux GUI 无法启动

安装当前发行版缺失的 Qt/XCB 运行库。这通常表示 Python 依赖已经安装，但桌面环境缺少 Qt 平台库。

### 任务名称显示过多

在设置中关闭 **显示任务名称**。主界面和悬浮窗仍会自动滚动过长的配置名。

## 开发

从源码运行：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

构建 Windows 包：

```powershell
pip install -r requirements-dev.txt
python -m PyInstaller Alas-Gyre.spec --noconfirm
```

## 许可证

Alas-Gyre 基于 [GNU General Public License v3.0](LICENSE) 发布。
