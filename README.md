# 共享代码骨架与数据码字编码（开发入口）

这是依据 `项目规划/10_公共接口与修改权限规范.md` 契约 1.0 建立的开发骨架。
当前用于统一四人的字段、调用边界和基础测试；完整 Stage1 二维码算法尚未实现。
本文件是开发使用说明，最终评分用 README 和反思仍需团队根据真实实现自行撰写。

## 安装与检查

本次实际验证：Windows、CPython **3.13.9**、numpy **2.2.6**。
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

当前上述调用的真实结果是 `False`、`FEATURE_UNAVAILABLE`，共保留 9 个真实步骤：
前置字符编码和计划确认 2 步，加数据码字编码 7 步。最后一步 data.data_codewords 包含
known 的 19 个数据码字；当前流程停止在尚未实现的纠错模块，没有可扫码矩阵。
编码细节与自行验证方法见[数据码字编码说明](docs/byte_encoding.md)。

基础默认值为 V1/L/Mask0，步骤采集默认开启，ID 和带时区时间自动建立。
输入原文不会 trim 或截断。空输入、字符不支持、容量超限分别有明确错误。

调用类型/ID/时间错误抛 `QRContractError`；结构有效的业务失败返回 `QRResult`。
CLI 与 GUI 后续都调用这个实例方法，不另写一套生成流程。

## 主要文件

| 位置 | 当前用途 |
|---|---|
| `qr_app/models.py` | 请求、计划、码字、布局、掩码结果、步骤、日志状态和生成结果 |
| `qr_app/errors.py` | 统一错误码、业务异常、调用异常、独立保存/读取异常 |
| `qr_app/tracing.py` | 每请求轨迹、重复步骤检测、独立只读矩阵和嵌套载荷 |
| `qr_app/service.py` | 参数检查 → 严格编码 → 计划 → 编码/ECC/矩阵/掩码 → 一次日志处理 |
| `qr_app/core/` | 已实现严格字符转换和数据码字编码；纠错/矩阵/掩码待实现 |
| `qr_app/resources/qr_capacity_v1_v2.json` | 当前仅有 V1/L 规格，附来源和待复核状态 |
| `qr_app/extensions/` | 预留四项个人扩展位置，当前不自动导入或启用 |
| `qr_app/presentation/` | 预留 CLI/GUI 位置，当前没有界面或启动脚本 |
| `tests/` | 公共模型、轨迹和编排边界测试 |
| `docs/shared_skeleton.md` | 接口接入、实际环境、测试范围及合并前事项 |
| `evidence/` | 预留真实证据目录，当前没有五份 demo 或扫码证据 |

## 下一步

共享骨架基础版本已发布至 main（43c54dc）；数据码字编码沿用该版本的公共接口。
后续四人同步同一个 main 提交，再各自建立功能分支；公共变更继续按约定进行 PR 和非作者复核。
模块接入顺序和签名见[开发说明](docs/shared_skeleton.md)。

Python 3.13.9 下 42 项测试、13 个模块导入、编译和依赖检查均通过。
本地复核修复了评分对象无法记录进轨迹、V1/L 计划依赖资源行序的问题；
[当前验证记录](docs/validation/byte_encoder_pre_publish_python3139_20261111_200618.json)保留实际输出和源码哈希。
发布前额外完成 510 组独立反向解析检查，覆盖所有 256 种字节值及 V1/L、V2/L 的全部合法长度。
团队非作者评审、正式 CI 和完整二维码功能仍待完成。

数据码字编码已完成；Stage1 还需完成 RS 纠错、矩阵落位、格式信息、Mask0、CLI 和五份真实 demo。
测试中的模拟矩阵仅用于检查编排与故障隔离，不代表 QR 编码正确、可扫码或 Stage1 验收通过。
