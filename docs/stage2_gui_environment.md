# Stage 2 第一步：界面环境准备

日期：2026-11-12。结论：本机 Windows x64 / Python 3.13.9 的独立 GUI 环境已配置，离屏与 Windows 原生 Qt 画布验证通过。

本步骤准备窗口和绘图的运行条件，尚未实现二维码渲染器、PNG 保存或正式 GUI。没有重新运行 Stage 1 测试。

## 1. 已完成的工作

1. 使用现有 `D:\python\python.exe` 创建项目内的 `.venv`，不修改原解释器的软件包。
2. 在 `.venv` 安装基础依赖、PyQt5 与 matplotlib，优先使用二进制 wheel。
3. 保存直接依赖声明与完整版本锁定文件。
4. 处理中文目录下 Qt 默认插件路径损坏的问题。
5. 实际创建 QApplication、QMainWindow、FigureCanvasQTAgg，绘制诊断图，运行事件循环并自动关闭。
6. 保存两个平台的真实 JSON 验证记录，执行 `pip check`。

`.venv` 已被原有 `.gitignore` 忽略，不应将虚拟环境目录提交给团队。团队通过锁定文件重建。

## 2. 实际环境

| 项目 | 本机版本 |
|---|---|
| 系统 | Windows 11，64 位 |
| Python | CPython 3.13.9 |
| 项目解释器 | `.venv\Scripts\python.exe` |
| numpy | 2.2.6 |
| reedsolo | 1.7.0 |
| matplotlib | 3.10.7 |
| PyQt5 | 5.15.11 |
| PyQt5-Qt5 | 5.15.2 |
| PyQt5-sip | 12.20.0 |

[requirements-gui.txt](../requirements-gui.txt) 声明本阶段的直接依赖，并引用原有 `requirements.txt`。
[requirements-gui-lock.txt](../requirements-gui-lock.txt) 保存这次安装的全部应用依赖版本，包括传递依赖；目标为本次验证的 Windows x64 / Python 3.13.9，不代表跨操作系统或教学机房验证已完成。

## 3. 后续开发使用哪个 Python

在项目根目录执行命令时，GUI 开发统一使用 `.venv` 的解释器，不要误用裸 `python` 或裸 `pip` 安装到其他环境。

```powershell
Set-Location -LiteralPath 'F:\文件\python\2026-2027大三上\Coursework2'
& '.\.venv\Scripts\python.exe' --version
```

编辑器或 IDE 的项目解释器选择：

```text
F:\文件\python\2026-2027大三上\Coursework2\.venv\Scripts\python.exe
```

无需执行 `Activate.ps1`，直接调用解释器即可，避免 PowerShell 执行策略影响激活脚本。

## 4. 在新电脑重建环境

先安装课程要求的 64 位 CPython 3.13.9，在仓库根目录执行：

```powershell
# 新电脑在项目根目录建立自己的环境；已有 .venv 无需重复创建。
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install --only-binary=:all: -r requirements-gui-lock.txt
& '.\.venv\Scripts\python.exe' -m pip check
```

本机实际使用 `requirements-gui.txt` 完成安装后生成完整锁定文件。上述从锁定文件全新重建的流程供新环境使用，本次没有再重复创建第二套环境验收。

若新电脑没有相应 wheel，应先查明 Python 版本、架构和包源，不直接改用源码编译或更换为 PyQt6。

## 5. 中文路径问题与启动处理

### 5.1 真实遇到的问题

本项目位于中文目录。诊断时，Qt 5.15.2 的默认插件路径显示为：

```text
F:/??/python/2026-2027???/Coursework2/.venv/Lib/site-packages/PyQt5/Qt5/plugins
```

实际 `platforms/qwindows.dll` 和 `platforms/qoffscreen.dll` 已存在，但 Qt 的默认库路径为空。直接创建 QApplication 会阻塞或失败，并出现：

```text
Could not find the Qt platform plugin "windows" in ""
```

这不是 reedsolo、二维码算法或 matplotlib 绘图失败。最初在沙箱外复验也没有消除问题，最终通过显式插件路径解决。

### 5.2 已实现的处理

新增 [qt_environment.py](../qr_app/presentation/qt_environment.py) 的 `configure_qt_environment()`：

- 根据当前环境中 `PyQt5.QtCore` 的真实文件位置找到对应 `Qt5/plugins`。
- 通过 `QCoreApplication.setLibraryPaths()` 传入完整 Unicode 路径，避开损坏的默认路径。
- 仅在当前 Python 进程选择 PyQt5；不写 Windows 系统环境变量，不拷贝 DLL，也不更改项目路径。

后续正式 GUI 启动入口应先准备环境，再导入 Qt 画布、创建 QApplication，例如：

```python
from qr_app.presentation.qt_environment import configure_qt_environment

configure_qt_environment()

from PyQt5.QtWidgets import QApplication
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

# 在正式 GUI 入口继续创建 app、窗口和画布。
```

此处是启动顺序说明，不是已经实现完整 GUI 的声明。普通 CLI 不导入此模块，核心计算不需要 Qt 初始化。

## 6. 环境验证脚本

位置：[scripts/check_gui_environment.py](../scripts/check_gui_environment.py)。

脚本绘制一个 3×3 诊断棋盘图案，该图案不是二维码，不作为扫码证据。默认不显示窗口，自动关闭；需要人工查看时才指定 `--visible`。

### 6.1 离屏验证

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 scripts/check_gui_environment.py
```

### 6.2 Windows 原生插件验证

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 scripts/check_gui_environment.py --platform windows
```

### 6.3 手动打开验证窗口

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 scripts/check_gui_environment.py --platform windows --visible --close-after-ms 10000
```

该命令显示诊断图案与文本，约 10 秒后自动关闭。此可见模式命令供手动检查，本次实际运行的是隐藏窗口模式。

需要保存新记录时，加 `--report` 并提供已存在目录下的新文件名。脚本拒绝覆盖旧报告；返回 0 表示所有已定义检查通过，返回 1 表示检查失败。报告包含脚本和 Qt 启动辅助模块的 SHA-256。

## 7. 本次实际验证结果

| 验证内容 | offscreen | windows |
|---|---|---|
| Python 3.13.9 与 PyQt5 绑定 | 通过 | 通过 |
| 对应平台插件存在并加载 | 通过 | 通过 |
| matplotlib 嵌入 Qt 画布并绘制 RGBA | 通过 | 通过 |
| 画布含实际黑白像素 | 通过 | 通过 |
| 文本设置与读取一致 | 通过 | 通过 |
| draw_event 回调 | 2 次 | 2 次 |
| 事件循环中的定时器执行 | 通过 | 通过 |
| 窗口自动关闭、事件循环正常退出 | 通过 | 通过 |
| pip check | 无依赖冲突 | 无依赖冲突 |
| all_passed | true | true |

原始记录：

- [离屏记录](validation/gui_environment_offscreen_python3139_20261112.json)。
- [Windows 原生记录](validation/gui_environment_windows_python3139_20261112.json)。

记录使用 UTC 时间；例如 Windows 原生验证开始的 `2026-11-11T16:50:45+00:00` 对应北京时间 2026-11-12 00:50:45。

离屏插件记录了字体目录缺失及 `propagateSizeHints` 提示，原始信息保留在报告中；离屏结果用于绘图和事件循环检查，不证明真实桌面的字体显示质量。Windows 原生模式的 `qt_messages` 为空，未报告这些警告。

## 8. 已完成与待完成边界

**第一步环境准备已完成。** 接下来可以实现独立于 Qt 的 matplotlib 二维矩阵渲染器，然后实现 PNG 保存与正式窗口。

本次没有执行或认定以下项目完成：

- Stage 1 在新 `.venv` 中的全量回归测试。
- 二维码图像渲染、quiet zone、PNG 导出功能。
- 正式输入/生成/保存页面与 Information 页面。
- 人工观察可见窗口、中文字体、小窗口与高 DPI 布局验收。
- 手机扫码、教学机房配置、学校 GitLab CI。

这些事项按后续阶段逐项实施；当前环境验证不会替代它们。
