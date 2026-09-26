# 桌面客户端更新检查（2026-09-26）

## 已确认的问题及修复

1. **Nuitka 版无法进入自动更新。** v1.1.5、v1.2.0、v1.2.3 的更新器只检查 `sys.frozen`；Nuitka 不设置该标志。现在通过模块 `__compiled__` 识别 Nuitka，使用 `sys.argv[0]` 定位用户安装的外层 EXE，避免替换 onefile 临时解包目录中的程序。配置及外部 Runtime 放在安装目录，打包资源仍从解包目录读取。PyInstaller 与源码路径保留各自行为。
2. **后台助手的等待失效。** Windows `timeout /t 2 /nobreak` 在无控制台、标准输入重定向时，本机约 0.12 秒退出并返回 1，提示不支持输入重定向。旧版无限循环会快速重试，前轮加入的次数上限也不能保证等待时长。改用不依赖控制台输入的 PowerShell `Start-Sleep`，保留最多 60 次等待/替换重试。
3. **特殊路径启动失败。** 把含 `%PATH%` 的完整脚本路径交给 `cmd /c` 会触发变量展开。现在指定程序目录为 cwd，以固定文件名启动助手，并用 `/d` 禁止 cmd AutoRun。中文、空格、百分号、感叹号路径已纳入真实后台测试。
4. **助手删除自身后的退出异常。** 特殊路径测试中替换完成后出现 `The batch file cannot be found`。助手现在将启动和退出放在同一条命令中，残留脚本由应用现有的启动清理流程删除，避免新程序与仍在读取脚本的助手发生竞争。

Nuitka 行为依据：[常见问题](https://nuitka.net/user-documentation/common-issue-solutions.html)、[运行时识别说明](https://nuitka.net/user-documentation/tips.html)。

## 发布状态及旧版本恢复

本轮通过 GitHub API 核对：最新正式 Release 仍为 **v1.2.3**，PyInstaller/Nuitka 两种 EXE 和对应 SHA256 文件均存在。此前推送到 main 的修复未发布为新安装包；源码版本号仍为 v1.2.3，因此相同版本号不会提示更新。

旧安装包包含自身的旧更新逻辑，仅推送源码不能修复已安装客户端。当前可先退出旧程序，保留同目录 `config.json` 和 `overlay`，从正式 Release 手动下载替换 EXE；若原来使用 Nuitka 版，可临时使用 PyInstaller 的 `Alas-Gyre.exe`。新修复需在后续更高版本打包发布后才能交付，受旧更新器阻断的用户可能仍需手动替换一次。

本次没有构建 EXE、创建 tag 或发布 Release。尚未取得用户具体版本、构建类型及报错，以上是已确认的代码缺陷，不代表已经复现其机器上的全部原因。客户端 GitHub 请求目前禁用环境代理；若表现为下载超时，还需结合实际网络和错误信息判断。

## 验证

`python -m unittest discover -s tools -p 'test_*.py'`

本机结果：31 项测试，30 项通过、1 项 Linux 专用集成测试跳过。Ruff `F,E9` 和 `git diff --check` 通过。

新增 `tools/test_desktop_updater.py`：模拟 Nuitka 外层/解包路径、PyInstaller 路径、源码拒绝替换 Python；真实启动隐藏 Windows 助手，等待测试进程退出、在目标文件占用期间重试，再替换并执行临时复制的 Windows `where.exe`，最后验证启动清理。下载响应为本地替身，EXE 大小/MZ/SHA256 校验正常执行。

未进行真实 Nuitka/PyInstaller 安装包升级端到端测试；这一步需要后续构建产物。没有访问真实 ALAS 服务或设备。
