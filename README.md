# QR 基础编码核心（开发入口）

这是依据 `项目规划/10_公共接口与修改权限规范.md` 契约 1.0 建立的开发骨架。
当前已完成 Stage1：共享接口、Byte/RS/矩阵/格式信息/固定 Mask0、CLI、五份正式 demo 与本机验收文档。
真实文件及逐项说明见[Stage1证据入口](evidence/README.md)。
完整开发顺序、模块交接、25步轨迹与历史验证版本见[Stage1开发流程梳理](docs/stage1_development_review.md)。
本文件是开发使用说明，最终评分用 README 和反思仍需团队根据真实实现自行撰写。

## 安装与检查

本次实际验证：Windows、CPython **3.13.9**、numpy **2.2.6**、reedsolo **1.7.0**。
Python 3.13.9 已在当前机器完成升级和验证，教学机房环境仍待验证。环境详情见
[共享骨架开发说明](docs/shared_skeleton.md)。

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

已有 numpy 2.2.6 的当前环境可直接执行：

```powershell
python -m unittest discover -s tests -v
```

Stage1历史测试在现有解释器运行；Stage2已另建项目内`.venv`并安装界面依赖，见下方说明。
尚未在新`.venv`重跑Stage1全量测试。
测试使用标准库 `unittest`，不需要额外安装 pytest。

## Stage2界面环境

第1步环境准备已完成：项目内`.venv`使用Python3.13.9、PyQt5 5.15.11、Qt5.15.2和matplotlib3.10.7。
离屏与Windows原生隐藏窗口均通过画布绘制、事件循环、自动关闭和依赖检查。
已通过显式Unicode插件路径解决中文目录下Qt平台插件无法定位的问题；后续GUI入口先调用
`qr_app.presentation.qt_environment.configure_qt_environment()`。

环境配置、完整依赖锁定、验证记录与后续启动顺序见[Stage2界面环境说明](docs/stage2_gui_environment.md)。
GUI开发使用`.venv\Scripts\python.exe`。可在项目根目录打开约10秒的诊断窗口：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 scripts/check_gui_environment.py --platform windows --visible --close-after-ms 10000
```

该窗口仅验证环境，显示的诊断棋盘不是二维码；真实二维码渲染见下一节。

## Stage2二维码渲染

matplotlib渲染已完成：0白1黑、默认4模块白边、最近邻绘制、正方形比例；默认V1图像为290×290像素。
`qr_app/presentation/renderer.py`提供`RenderOptions`、`render_qr()`和`draw_matrix()`，不修改原矩阵、不自动保存。

在项目根目录打开真实二维码预览：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 scripts/preview_qr.py --text "known"
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest tests.test_renderer -v
```

13项渲染专项测试、5个真实图像的本机OpenCV解码及Qt离屏预览通过。
用法、接口、验证图与边界见[渲染说明](docs/renderer.md)和[本次验证记录](docs/validation/renderer_python3139_20261112.json)。
预览窗口现已提供Save PNG按钮；窗口内文本输入、正式生成页面、Information与手机扫码仍待实施。

## Stage2 PNG保存

PNG保存已实现：在预览窗口点击`Save PNG`选择路径，已有文件确认后才覆盖；取消或失败保留当前二维码。
也可以在终端直接保存：

```powershell
New-Item -ItemType Directory -Force outputs
& '.\.venv\Scripts\python.exe' -X utf8 scripts/preview_qr.py --text "Hello QR" --png-out outputs/hello.png --no-preview
```

再次保存到同名文件需明确加`--overwrite`。父目录必须存在；保存前完整编码到临时文件，失败不会破坏旧文件。
31项保存/对话框/渲染测试、实际Qt按钮保存以及五张导出图的本机解码通过。
接口、覆盖规则和退出码见[PNG保存说明](docs/png_export.md)，实际结果见[验证记录](docs/validation/png_export_python3139_20261112.json)。

## 运行 CLI

在项目根目录使用当前 Python 3.13.9：

```powershell
& 'D:\python\python.exe' main_cli.py
& 'D:\python\python.exe' main_cli.py --text "known"
& 'D:\python\python.exe' main_cli.py --text "known" --show-steps
& 'D:\python\python.exe' main_cli.py --help
```

默认固定 V1/L/Mask0，成功时显示25步计数和完整21×21数值矩阵。
无输入参数启动时先显示菜单：`1`单行、`2`多行、`0`退出。
单行按回车提交，多行用单独一行 `:end` 结束；菜单与结束标记不进入编码内容。
`--steps-out PATH` 可导出 UTF-8 真实步骤报告，父目录须已存在，已有文件需加 `--overwrite`。
`--stdin` 完整读取 UTF-8 标准输入并保留换行；原文不 trim。
当前不自动保存使用日志。详细命令、输入规则和退出码见[CLI 使用说明](docs/cli.md)。

已保存的五份正式demo对应旧版源码383b76c，可使用
`python -X utf8 scripts/stage1_evidence.py --historical` 核验；当前菜单修改的验证另行记录。

## 统一调用

```python
from qr_app.models import QRRequest
from qr_app.service import QRService

service = QRService()
request = QRRequest(text="known", source="cli")
result = service.generate_qr(request)

print(result.generation_success)
print(result.error_code)
print([step.step_id for step in result.trace_steps])
```

当前上述调用返回 True、None，生成完整的 V1/L/Mask0 主体矩阵，尺寸为21×21，
保留25个真实步骤。result.matrix 为只读 uint8 0/1 数组，不含 quiet zone；mask_id=0，
penalty_scores为空。详见[Byte](docs/byte_encoding.md)、[RS](docs/error_correction.md)、
[矩阵](docs/matrix_building.md)与[格式/Mask0](docs/format_mask0.md)。

基础默认值为 V1/L/Mask0，步骤采集默认开启，ID 和带时区时间自动建立。
输入原文不会 trim 或截断。空输入、字符不支持、容量超限分别有明确错误。

调用类型/ID/时间错误抛 `QRContractError`；结构有效的业务失败返回 `QRResult`。
CLI 已调用这个实例方法，未来 GUI 也复用同一流程。

## 主要文件

| 位置 | 当前用途 |
|---|---|
| `qr_app/models.py` | 请求、计划、码字、布局、掩码结果、步骤、日志状态和生成结果 |
| `qr_app/errors.py` | 统一错误码、业务异常、调用异常、独立保存/读取异常 |
| `qr_app/tracing.py` | 每请求轨迹、重复步骤检测、独立只读矩阵和嵌套载荷 |
| `qr_app/service.py` | 参数检查 → 严格编码 → 计划 → 编码/ECC/矩阵/掩码 → 一次日志处理 |
| `qr_app/core/` | 已实现字符转换、数据码字、RS、矩阵、BCH 格式信息与固定 Mask0 |
| `qr_app/resources/qr_capacity_v1_v2.json` | 当前仅有 V1/L 规格，附来源和待复核状态 |
| `qr_app/extensions/` | 预留四项个人扩展位置，当前不自动导入或启用 |
| `main_cli.py` | CLI 启动脚本，UTF-8 标准输入输出 |
| `qr_app/presentation/` | CLI、显式步骤报告、matplotlib渲染及Qt环境准备；正式GUI待实现 |
| `qr_app/presentation/image_export.py` | 独立PNG保存、覆盖保护、实际制品返回 |
| `scripts/preview_qr.py` | Qt二维码预览、Save PNG按钮与终端显式PNG导出 |
| `tests/` | 公共模型、编码/纠错/矩阵与编排测试 |
| `docs/shared_skeleton.md` | 接口接入、实际环境、测试范围及合并前事项 |
| `evidence/` | 五份正式Stage1 demo、运行记录、制品哈希与本机验收说明；扫码证据待Stage2 |
| `scripts/stage1_evidence.py` | Stage1正式证据采集/校验；默认只校验，不覆盖现有文件 |

## 下一步

共享骨架基础版本已发布至 main（43c54dc）；数据码字编码沿用该版本的公共接口。
后续四人同步同一个 main 提交，再各自建立功能分支；公共变更继续按约定进行 PR 和非作者复核。
模块接入顺序和签名见[开发说明](docs/shared_skeleton.md)。

Python 3.13.9 下当前菜单版本通过 **139 项测试**（含42项 CLI/导出测试）、编译和依赖检查。
[当前菜单验证记录](docs/validation/interactive_input_python3139_20261112_000620.json)保留实际输出、真实菜单/参数样例及源码哈希。
旧CLI版本的130项测试与16个模块导入等检查见[历史记录](docs/validation/cli_python3139_20261111_225943.json)；
五个作业样例此前已临时验证；现已真实运行并保存为[五份正式demo](evidence/README.md)，
对应采集记录另包含本轮130项测试实际输出和源码哈希。
核心上一阶段已核对32种公开格式组合、800组完整矩阵，并完成5个本机解码样例，见
[格式/Mask0历史记录](docs/validation/format_mask0_python3139_20261111_221640.json)。
qrcode/OpenCV仅作离线验证，应用和常规测试没有新增依赖。
团队非作者评审、正式 CI 和完整二维码功能仍待完成。

Stage1本机交付已完成；Stage2环境、matplotlib渲染和PNG保存已完成，下一步实现正式PyQt5输入/生成页面、Information和真实手机扫码。
main_cli.py继续输出数值矩阵和步骤报告；图像预览与保存使用scripts/preview_qr.py。
测试中的模拟矩阵仅用于检查编排与故障隔离；Stage1正确性另有独立参考和真实demo支撑。
