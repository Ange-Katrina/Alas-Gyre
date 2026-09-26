# 项目流程检查与 API / 脚本优化记录

状态：本地隔离验证通过；真实运行端 **NEEDS_REVALIDATION**。

本记录基于当前工作区。开始前已有的 Overlay 修改、随附 ALAS、旧审计报告和探测脚本均保留；没有提交、推送、构建 EXE、更新远端或启动真实 ALAS。

## 检查范围与流程

| 流程 | 入口及依赖 | 本轮结果 |
| --- | --- | --- |
| 桌面初始化 | `main.py` → `alas_gyre/app.py` → 初始化向导、设置、托盘 | 核对配置与 Runtime 生成关系，保留界面布局 |
| 桌面监控与控制 | 主窗口/悬浮窗 → `alas_gyre/api/client.py` → Overlay | 修复断线残留状态、缺失配置状态、控制超时及 HTTP 重定向 |
| 宿主加载 | Linux/Windows 启动器 → `sitecustomize.py` → Uvicorn ASGI 包装 | 保留外置注入方式；不修改官方宿主源码 |
| 配置与进程 API | `/api/gyre/*` → 宿主 ProcessManager / 配置文件 | 统一修改操作互斥，隔离同步等待，核对宿主事件与子模块配置名 |
| 日志与截图 | Overlay → 内存日志、磁盘日志、错误图片 | 日志读取加字节上限；日志渲染、截图列表等同步工作移出请求事件循环 |
| ALAS 本体更新 | Overlay → `module.webui.updater.updater` | 保留现有 API；阻止更新与新启动/重启冲突，取消只在宿主等待阶段接受 |
| Runtime 更新 | 设置页 → 清单/增量上传 → 独立 HTTP 服务 | 慢连接隔离、并发上限、写入互斥、失败回滚及回传哈希确认 |
| 桌面程序更新 | GitHub Release 检查 → SHA-256 → 更新 helper | 保留已有哈希校验；修复 helper 启动失败仍先报成功、无限重试与路径编码问题 |
| 服务管理 | 后台运行、PID、systemd/OpenRC、Windows runner | 修复配置优先级、PID 归属、停止确认、独立进程组、中文路径 |
| 发布 | GitHub Actions / PyInstaller / Nuitka | 阅读现有发布链路；未触发构建或发布 |

宿主兼容性对照来自 `AlasApp_0.4.10_fullcn/AzurLaneAutoScript/module/webui/process_manager.py`、`updater.py`、`app.py`、`module/submodule/utils.py` 和 `gui.py`。没有把宿主本体的游戏任务逻辑纳入修改范围。

## 已处理的问题

| 编号 | 原流程问题 | 处理与证据 |
| --- | --- | --- |
| FLOW-01 | 配置保存/重启持 `threading.Lock` 等待 ASGI send；停止、重启同步等待阻塞请求循环 | 修改工作在 executor 中执行，响应发送前释放锁；同配置冲突返回 409；测试覆盖 yielding send、慢停止期间 health 可响应 |
| FLOW-02 | 启动未向宿主传入 updater.event，子模块名与宿主逻辑名不一致 | 传入宿主共享事件；启动前刷新宿主子模块索引；`demo.maa.json` 对应逻辑名 `demo`；同名多个文件拒绝含糊选择 |
| FLOW-03 | 删除时状态查询失败按 idle 处理；并发删除可能移除最后两个配置 | 查询失败拒绝删除；配置目录修改锁保证最后一个配置保留；保存/删除仅接受已停止的 idle/error 状态 |
| FLOW-04 | 启动/重启与更新可以交叉；执行文件更新阶段的 cancel 无法真正撤销 | 更新预约与启动/重启互斥且预约不阻塞事件循环；更新期间重启在停止实例前拒绝；只有宿主 wait 阶段接受 cancel |
| FLOW-05 | 长日志单行不受 lines 限制；配置正文可以无限等待；异常 Token 可能抛出异常 | 文件/内存日志上限 512 KiB；配置正文总等待上限 15 秒，大小上限继续为 2 MiB；Token 字节比较及重复头拒绝 |
| FLOW-06 | Runtime HTTPServer 被慢连接串行阻塞 | 最多 16 个并发连接、5 秒 socket 空闲超时；文件更新另行互斥；真实回环 HTTP 慢头测试通过 |
| FLOW-07 | 固定临时文件名及多文件更新中途失败造成部分新旧混合 | 唯一临时文件、校验、原子替换；失败尝试还原已写入文件；逐文件 `.bak` 保留；测试模拟第二文件失败并验证恢复 |
| FLOW-08 | Runtime 客户端接受非对象 JSON 后崩溃、未核对最终文件清单 | 校验协议/对象结构/最终全部文件哈希；真实客户端与回环服务验证增量上传及再次检查 latest |
| FLOW-09 | 请求重定向可能携带自定义 Token，IPv6/端口处理不完整 | 默认拒绝重定向、不自动重试写操作；支持 IPv6 方括号及 1–65535 端口检查 |
| FLOW-10 | 服务断线时部分配置行保留 running/旧任务名，启停请求 3 秒超时短于后端停止确认 | 失败或缺失配置更新为 disconnected，清空旧任务；主窗口/悬浮窗控制读取超时为 20 秒 |
| FLOW-11 | Linux 前台启动被 Ctrl+C 带停；后台服务未完全隔离终端 | 菜单 1 改为后台启动+日志查看；独立会话、关闭终端 stdin；服务管理器内部入口仍以前台方式供 supervisor 托管 |
| FLOW-12 | 配置默认值反过来覆盖 `.gyre_runtime.conf`；显式 ALAS_ROOT 可能丢失 | 保存原始环境快照，环境 > 文件 > 默认；兼容 CRLF；重复载入与显式 root 覆盖测试通过 |
| FLOW-13 | 仅凭 kill -0/PID 判断归属；单 PID 停止遗留 reload 子进程；停止失败仍清 PID | 检查当前 Runtime/宿主归属；物理路径比较支持符号链接 root；Linux 私有进程组整体停止并排除 zombie；Windows 强杀后重新确认，失败保留 PID |
| FLOW-14 | Windows ASCII runner 损坏中文路径 | UTF-8 无 BOM runner，首先切换代码页；用含中文和空格的临时路径实际执行两个 dummy runner 验证 |
| FLOW-15 | 更新服务自身被覆盖后界面没有重启提示 | 更新响应增加 `updater_restart_required`，设置页提示在启动器中重启更新服务 |
| FLOW-16 | 桌面更新 helper 无限等待/重试，创建失败之前已经报成功 | 有限等待/替换重试，helper 创建后才报告成功；Windows UTF-8 与路径百分号转义，POSIX 同目录原子 mv；失败用例确认不退出应用、不替换旧文件 |

## 本地验证

运行：

```powershell
python -B -m unittest discover -s tools -p 'test_*.py' -v
python -m ruff check --select F,E9 alas_gyre ui overlay resources/gyre_runtime_updater.py tools/test_api_workflows.py tools/test_linux_launcher.py tools/test_windows_launcher.py
```

本机结果：27 项测试，26 项通过，1 项跳过。另通过 `sh -n`、`dash -n`、Python AST 语法检查及 `git diff --check`。

- `tools/test_api_workflows.py`：API 并发、鉴权、宿主事件适配、配置写入、日志/正文上限、更新回滚、HTTP 慢连接、真实回环更新、桌面轮询及更新失败分支。
- `tools/test_linux_launcher.py`：启动器生成/语法、配置优先级在 Git Bash 下执行；Linux 专用信号/会话/进程树用例本机跳过。
- `tools/test_windows_launcher.py`：中文路径 runner 实际执行、PID 归属检查，使用临时文件和测试自身创建的进程。
- 两轮独立只读复核；发现的显式 root 丢失与符号链接 PID 误判已修复。

测试使用临时目录、虚构 Token、回环随机端口和模拟宿主，不使用真实 ALAS 配置、设备或凭据。旧 `tools/security_api_audit.py` 及 `security_best_practices_report.md` 作为此前诊断记录保留；当前结果以本文件和新回归测试为准。

## 运行端待验证

1. 在 Linux 上运行 `python3 tools/test_linux_launcher.py`：覆盖 setsid/Python fallback、两个菜单启动入口、Ctrl+C、SIGHUP、正常退出、符号链接 root、后台 worker 随显式停止退出。
2. 使用实际 ALAS 验证普通配置及 Maa/Fpy 子模块的启停、更新事件、更新等待/取消、reload 和日志队列。当前证据为宿主源码核对及隔离替身测试。
3. 在 systemd / OpenRC 和真实 SSH 环境验证开机启动、停止、注销策略。服务管理器及系统会话清理可能有独立于终端信号的行为。
4. 在 Windows 实际打包版本验证托盘/设置/悬浮窗及 EXE 自更新。没有构建、替换或运行真实更新 EXE。
5. 更新回滚覆盖可捕获的写入异常；断电/进程强杀并非跨文件事务，持续磁盘故障仍可能阻止回滚，应保留 `.bak` 并检查服务端错误日志。

## 应用改动

从当前源码使用初始化向导重新生成 Runtime，或使用当前源码客户端上传 Runtime。必须保持已有 Token 一致。替换完成后通过启动器重启 ALAS；若更新了 `gyre_runtime_updater.py`，还要选择“重启更新服务”。仅编辑仓库模板不会更新已部署 Runtime。

本轮保持 `X-Alas-Gyre-Token`、现有 URL、同步控制响应、默认监听配置以及主界面布局。新增 409/408/504 失败响应用于区分并发冲突、正文超时和停止超时；调用方应等待状态恢复后再操作，不要把超时当成已停止或已保存。
