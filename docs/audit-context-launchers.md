# 启动器与 Runtime 更新上下文

此文件保留优化前的阅读快照及当时的未确认点；修复结果、当前测试和待验证项见 [workflow-review.md](workflow-review.md)。

日期：2026-09-26。静态上下文记录，不是漏洞判定或运行验收。范围为当前启动脚本模板、生成器、Runtime 更新客户端；未启动 ALAS、未发送远端请求、未构建。行号对应本次阅读快照，后续修改可能移动。

## 调用图与外部约定

- 初始化界面调用 `generate_portable_overlay_launchers`（`ui/init_window.py:492`），生成 Runtime 五个文件：两个 Overlay 文件、两个平台启动器和更新服务（`alas_gyre/api/overlay_launcher.py:13-20,193-210`）。源文件由 `core/paths.py:12-22,34-36` 从源码或冻结包资源中定位。
- 旧式 `generate_overlay_launchers` 在 ALAS 根目录生成脚本，使用外置 Overlay 和桌面配置文件，直接前台运行；便携生成器则在 `gyre_runtime` 下生成菜单/后台/更新服务完整模板。这是不同生命周期合同（`overlay_launcher.py:81-140,175-210`）。
- POSIX 菜单 1 调用 `start_with_logs → start_background → launch_detached → sh script __gyre_service_run → run_alas_foreground`（`resources/start_gyre_alas.sh.template:930-1004,1514,1545-1547`）。子启动器再次解析根目录、检查端口、启动 updater，再 `exec` 宿主入口。
- Windows 菜单前台路径为 `start_foreground → run_alas_core`；后台路径先生成 `.gyre_run_alas.cmd`，由隐藏 `cmd.exe` 启动，PID 保存该 cmd 的 PID（`resources/start_gyre_alas.bat.template:632-641,756-833`）。
- 设置界面的线程调用 `update_remote_runtime`，按返回的 `restart_required` 展示提示，没有自动重启 ALAS（`ui/settings_window.py:655-682`）。客户端 GET `/runtime/info`，生成本地五文件并比较 SHA-256，只 POST 不同文件的 Base64 数据（`alas_gyre/api/runtime_update.py:68-142`）。

## 必须维持的规则

- ALAS 根目录最小判据是存在 `gui.py` 和 `module/webui/app.py`（生成器 `23-31`；SH `145-147`）。此规则不保证宿主依赖、Python 版本或运行兼容性。
- POSIX 服务应拥有独立会话且标准输入脱离终端。已有实现优先 `setsid`，否则 Python `Popen(start_new_session=True)`，标准输出/错误写日志（SH `696-724`）。菜单 Ctrl+C trap 仅退出启动器；真实终端信号行为仍需运行验证。
- PID 文件包含正整数这一最小规则由 SH `get_pid`/`get_updater_pid` 检查；进程存活用 `kill -0`（SH `539-596`）。保存 PID 的身份、启动时间和当前 Runtime 归属：nothing found。BAT 判活使用 `tasklist`（BAT `247-260`）。
- 远端更新文件白名单与本地 `RUNTIME_UPDATE_FILES` 应保持一致（生成器 `14-20`；`resources/gyre_runtime_updater.py:34-38`）。服务端先检查所有输入的路径、编码、大小和摘要，再逐个备份并替换（updater `115-134,276-325`）。多文件一起成功或回滚的保证：nothing found。
- Runtime 更新传输沿用 `X-Alas-Gyre-Token`；请求通过 `api_request` 使用 `requests.Session(trust_env=False)`，连接不继承代理配置（`alas_gyre/api/client.py:1,23-31`）。本记录不改变既有认证和监听约定。

## 启停与重启假设

- SH 普通停止只 TERM/KILL 保存的单个 PID；检查退出最多等待 10 秒，强杀后删除 PID 文件（SH `1006-1029`）。`restart_background` 无条件继续启动（`1032-1034`）。宿主 `run_alas.sh`/pixi 分支是否最终 `exec` 到服务、子进程如何清理：未建立。
- 随附宿主 `AlasApp_0.4.10_fullcn/AzurLaneAutoScript/gui.py:88-109` 在 `EnableReload` 模式创建 multiprocessing 子进程，父进程只显式捕获 KeyboardInterrupt。启动器 TERM 单个 PID 能否终止 WebUI 子进程：nothing found；需独立假宿主进程树测试及实际宿主验证。
- SH updater 停止同样只针对单 PID（SH `768-786`）；BAT 停止调用 `taskkill /T /F`，随后直接删除 PID 文件并报告停止（BAT `690-705,835-851`）。Windows taskkill 失败后的状态保证：nothing found。
- 端口占用处理将 PID 文件匹配、命令行或工作目录包含 ALAS root 视为归属证据；updater 判断依赖命令行包含脚本名（SH `629-657,859-874`；BAT `271-290,727-732`）。同名脚本/嵌套目录/多 Runtime 情况的唯一归属保证：nothing found。
- 新启动成功由延迟后的 PID 存活确认，并非 HTTP 就绪确认（SH `759-765,982-993`；BAT `678-688,821-833`）。日志应区分存活与 API 可用。

## 自动启动约定

- systemd 用 `Type=simple`、前台 `__gyre_service_run`、`KillMode=control-group`；停止入口会同时停止 ALAS/updater（SH `1102-1126,1549-1552`）。后台 updater 即使 setsid 仍可能留在同一 systemd cgroup；这与手动菜单停止仅停止 ALAS 的行为不同。
- OpenRC 用 supervise-daemon、前台入口、共享 PID 文件、`stop_post` 调用统一停止（SH `1129-1166`）。配置路径被直接插入 shell 源码和 command_args；含空格、引号、美元符号路径的正确性尚未验证。
- systemd/OpenRC 服务名固定（SH `14-15`），多实例安装的隔离行为未建立。systemd 路径转义函数只处理反斜杠/双引号（SH `1098-1099`），其他 unit specifier 字符尚未验证。

## 配置与生成假设

- SH 文件级默认赋值（`22-25`）发生在 `load_config` 保存“环境值”（`151-156`）之前。读取配置（`169-172`）后又将保存值覆写回来（`183-187`）。真实环境、默认值、配置文件三者优先级是否符合用户设置，需要隔离 fixture 验证。
- SH 多数函数的 `pid`、`py`、`port`、`root`、`i` 为全局 shell 变量；命令替换会隔离其中部分写入，普通嵌套调用不会。当前未证明全局变量互不影响；后续修改必须沿调用栈检查，不能直接假设函数局部。
- Windows 开启 delayed expansion（BAT `2`）；token 仅由 `_bat_value` 转义百分号并删除双引号（生成器 `77-78,143-148`）。特殊 token 字符保真范围未建立。
- BAT 两个临时 runner 使用 ASCII 编码写入路径和命令（`668,811`），而入口模板设置 UTF-8 codepage（`3`）。中文/非 ASCII Runtime 路径在两次解析之间保持原样的保证：nothing found。
- 生成器 `write_text` 直接覆盖文件（`166-172`）；多个文件生成的原子性和失败回滚：nothing found。本地文件缺失时更新打包会跳过（runtime_update `43-46`）；完整清单保证依赖前面的生成器成功。

## 更新客户端边界待核对

- `runtime_update_port` 仅检查 `str.isdigit()`，未检查范围；IP 直接拼接 URL（runtime_update `16-23`）。IPv6、零端口、大端口与 Unicode 数字处理合同未建立。
- GET 响应确认 JSON dict/files dict（`83-90`）；POST 响应捕获 JSON 解析异常后直接 `.get()`（`125-133`）。合法 JSON 非对象的合同没有检查。
- 本地生成错误没有在 `update_remote_runtime` 内转为结构化结果（`92`）；上层 UI 包含兜底异常处理（settings `680-681`）。客户端调用者能否依赖函数始终返回 dict，应明确。
- 服务端 updater 自身替换不设置 ALAS restart_required（updater `36`），其旧进程继续执行到手动重启；ALAS 与 updater 的更新生效时点必须分别解释。

## 验证边界

本记录只检查源码和随附宿主启动结构。未验证 Linux/macOS/Windows 真终端信号、systemd/OpenRC、特殊路径、并发启动、PID 复用或远端实际更新。上述 open questions 留给后续限定范围复现与修复阶段，不应作为已确认生产缺陷或已修复项目报告。
