# QR 基础编码核心（开发入口）

这是依据 `项目规划/10_公共接口与修改权限规范.md` 契约 1.0 建立的开发骨架。
当前已完成 Stage1：共享接口、Byte/RS/矩阵/格式信息/固定 Mask0、CLI、五份正式 demo 与本机验收文档。
真实文件及逐项说明见[Stage1证据入口](evidence/README.md)。
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

本次测试在现有解释器运行；新建虚拟环境和重新安装依赖尚未验证。
测试使用标准库 `unittest`，不需要额外安装 pytest。

## 运行 CLI

在项目根目录使用当前 Python 3.13.9：

```powershell
& 'D:\python\python.exe' main_cli.py
& 'D:\python\python.exe' main_cli.py --text "known"
& 'D:\python\python.exe' main_cli.py --text "known" --show-steps
& 'D:\python\python.exe' main_cli.py --help
```

默认固定 V1/L/Mask0，成功时显示25步计数和完整21×21数值矩阵。
`--steps-out PATH` 可导出 UTF-8 真实步骤报告，父目录须已存在，已有文件需加 `--overwrite`。
`--stdin` 完整读取 UTF-8 标准输入并保留换行；原文不 trim。
当前不自动保存使用日志。详细命令、输入规则和退出码见[CLI 使用说明](docs/cli.md)。

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
| `qr_app/presentation/` | CLI 输入/结果展示、显式步骤报告导出；GUI 待实现 |
| `tests/` | 公共模型、编码/纠错/矩阵与编排测试 |
| `docs/shared_skeleton.md` | 接口接入、实际环境、测试范围及合并前事项 |
| `evidence/` | 五份正式Stage1 demo、运行记录、制品哈希与本机验收说明；扫码证据待Stage2 |
| `scripts/stage1_evidence.py` | Stage1正式证据采集/校验；默认只校验，不覆盖现有文件 |

## 下一步

共享骨架基础版本已发布至 main（43c54dc）；数据码字编码沿用该版本的公共接口。
后续四人同步同一个 main 提交，再各自建立功能分支；公共变更继续按约定进行 PR 和非作者复核。
模块接入顺序和签名见[开发说明](docs/shared_skeleton.md)。

Python 3.13.9 下 **130 项测试**（含33项 CLI/导出测试）、16个模块导入、编译和依赖检查均通过。
[当前 CLI 验证记录](docs/validation/cli_python3139_20261111_225943.json)保留发布前复验的实际输出和源码哈希；
五个作业样例此前已临时验证；现已真实运行并保存为[五份正式demo](evidence/README.md)，
对应采集记录另包含本轮130项测试实际输出和源码哈希。
核心上一阶段已核对32种公开格式组合、800组完整矩阵，并完成5个本机解码样例，见
[格式/Mask0历史记录](docs/validation/format_mask0_python3139_20261111_221640.json)。
qrcode/OpenCV仅作离线验证，应用和常规测试没有新增依赖。
团队非作者评审、正式 CI 和完整二维码功能仍待完成。

Stage1本机交付已完成；下一步进入Stage2：图像渲染/PNG保存、PyQt5 GUI和真实手机扫码。
当前CLI输出数值矩阵和步骤报告，尚不显示或保存二维码图片。
测试中的模拟矩阵仅用于检查编排与故障隔离；Stage1正确性另有独立参考和真实demo支撑。
