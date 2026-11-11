# 共享骨架开发说明

日期：2026-11-11。契约依据：`项目规划/10_公共接口与修改权限规范.md` 1.0；
输入规则：`input_rules_v1`。当前提供公共基础与 Byte 数据码字编码，不实现个人扩展或最终提交材料。

## 已实现与待实现

已实现请求/结果结构、枚举、错误边界、矩阵/轨迹副本、固定 V1/L 计划、严格
ISO-8859-1 转换、Byte 数据码字编码、输入与选项校验、生成编排、可选扩展装配和单次日志调用边界。
未知 options 键返回 `INVALID_OPTION`，不把 options 当作第二套参数入口。

所有公共字段的单位按契约保持：输入长度是 bytes，码字内容为 bytes，
位流为整数 0/1 tuple，矩阵为 uint8 0/1，保留区为 bool；矩阵按 `[row, col]` 索引，
不包含 quiet zone。Plan 的 data_codewords 是数量，EncodedData 的同名字段是内容。

调用方通过 `QRRequest(...)` 建立请求，使用 `QRService().generate_qr(request)`；
输入值可采用已定义 StrEnum 或对应字符串，整数参数不接受 bool。
请求结构的最终验证在服务边界执行，未知枚举值作为业务参数错误返回。

骨架不产生二维码图像，不导入 GUI，不自动保存轨迹或建立使用 CSV。
未来展示层负责错误展示及诊断 handler 装配；服务当前仅发出 ID 和异常类型的诊断日志，
没有自动创建诊断文件，也不把原文、异常文本或堆栈送进公开结果。

## Stage1 接入顺序

| 文件/函数 | 实现目标 | 固定输入与返回 |
|---|---|---|
| core/byte_encoder.py: encode_data | 已完成：模式/长度/数据、终止、字节对齐、交替填充 | bytes + plan → EncodedData |
| core/error_correction.py: build_final_codewords | reedsolo RS、交织和余数位 | bytes + plan → FinalCodewords |
| core/matrix_builder.py: build_matrix | 功能/保留区、Z 形数据落位 | tuple[int,...] + plan → MatrixLayout |
| core/format_info.py: build_format_bits | 自行生成含纠错和异或的 15 位格式信息 | 实际 ECC + mask_id → tuple[int,...] |
| core/fixed_mask.py: apply_fixed_mask_zero | 复制布局，仅掩码数据区，再写格式信息 | layout + plan → MaskSelection |

除已完成的 encode_data 外，上表其余占位函数统一抛 FEATURE_UNAVAILABLE。
数据码字编码保留 7 个真实步骤，说明见[数据码字编码](byte_encoding.md)。
每个阶段实现时接受可选关键字 `trace=None`，只在真实步骤完成后调用 `trace.record(...)`。
每个步骤由该阶段登记一次；候选专用步骤须带 mask 编号，避免 step_id 冲突。
服务目前只登记 `input.iso_8859_1`、`plan.selected`，算法内不要重复登记这两个 ID。

```python
if trace is not None:
    trace.record(
        "matrix.data_placed", "数据落位", "已完成数据区写入。",
        "matrix", modules,
    )
```

收集器立即复制载荷，数组设为只读；后续应先 copy 再修改。只读用于防止意外修改，
不是针对恶意代码的安全隔离。评分轨迹支持不可变 PenaltyBreakdown 对象及其映射。
不要向轨迹传控件、文件句柄或服务对象。

V1/L 独立于个人版本策略运行。规格表目前只有 V1/L，文件名保留规划路径；
完整 V1/V2 八组数据仍待扩展开发和独立复核，不能认为该表已完整。
服务按 version=1、ecc_level=L 查找唯一基础计划，不依赖资源表行序；缺失或重复条目明确报错。

## 四项扩展怎样接入

`QRService(*, version_selector=None, mask_selector=None, usage_logger=None)` 构造不生成或写文件。

- 版本/ECC：传入 `select_plan(byte_length, version, ecc_level, mode)` 形态的函数。
- 掩码：传入 `select_mask(layout, plan, mask_id, *, trace=None)` 形态的函数。
- 日志：传入具备 `append_attempt(request, result) -> LogStatus` 的对象。
- 步骤展示：消费 `QRResult.trace_steps`，不向服务注入 UI、不重新生成。

`service.capabilities` 是只读 frozenset，按已传入依赖报告
`version_ecc` / `mask_selection` / `usage_logging`。启动端只能装配已真正实现的扩展。
它不表示尚未实现的 Stage1 算法已经可用。

baseline 永远不调用版本/ECC或完整掩码扩展，但可调用日志。
extended 需要版本策略；没有掩码策略时只允许显式 Mask0。
完整掩码扩展即使手动选择也须返回全部八个评分，固定 Mask0 不伪造评分。

日志对每个结构有效的请求（含业务失败）调用一次；调用契约错误不写正常使用记录。
日志失败只改变 logging_status 和提示，不覆盖二维码生成状态。未接日志时为 not_enabled。
保存、翻步骤、刷新统计不属于 generate_qr 调用，后续展示层应自己维护这个边界。

后续增加 renderer、UsageFilter/UsageSummary 等模型时，继续按规划 10 的字段维护；
本轮没有预先实现这些 Stage2/个人功能。真实姓名、学号和功能角色归属仍由团队填写。

## 本次实际环境

| 项目 | 本次状态 |
|---|---|
| 平台 | Windows x64 |
| Python | CPython 3.13.9，当前运行解释器 D:\python\python.exe |
| numpy | 2.2.6，已导入并通过矩阵/轨迹测试 |
| 测试框架 | 标准库 unittest |
| pip check | No broken requirements found |
| Python 3.13.9 / 教学机房 | 当前机器已验证；教学机房待验证 |
| reedsolo / PyQt5 | 当前未安装，算法/GUI接入时单独验证固定版本 |
| matplotlib / pandas | 3.10.7 / 2.3.0，已通过导入检查；骨架不依赖，业务功能未验收 |
| lint / GitLab Runner / 正式 CI | 待选型和配置，当前没有声明 CI 通过 |

requirements.txt 只记录本轮真正使用和验证的 numpy==2.2.6。
未伪造 conda 环境文件，未在依赖里填尚未验证的 reedsolo、Qt 或测试工具版本。
本次未建立干净虚拟环境重新安装；安装命令是复现步骤，不能当作已执行证据。

2026-11-11 已将原 D:\python 环境从 Python 3.13.4 原位升级为 3.13.9，
沿用当前用户安装范围。原有 153 个软件包均保留，版本未变化。
numpy、pandas、matplotlib、scipy、Pillow、scikit-learn、OpenCV 均通过导入检查；
NumPy 原生线性代数检查、pip check、28 项项目基础测试和字节码编译检查均通过。
完整实际输出见[环境验证记录](environment_validation.json)。这不替代教学机房和完整 QR 功能验收。

## 检查命令与范围

完成数据码字编码后使用 D:\python\python.exe（Python 3.13.9）验证：42 项测试、13 个模块导入、
字节码编译和 pip check 均通过；五个真实服务请求均符合当前骨架的预期失败状态。
详细命令、实际输出、请求结果及源码 SHA-256 见
[2026-11-11 共享骨架验证记录](validation/byte_encoder_pre_publish_python3139_20261111_200618.json)。
包含 Latin-1 字符的终端验证采用 Python 的 -X utf8 选项。此结果不表示 QR 算法或 Stage1 已完成。


```powershell
python -m unittest discover -s tests -v
python -m compileall -q qr_app tests
```

基础测试覆盖：规格数量/单位、矩阵和嵌套载荷的独立副本、整数位流、错误优先级、
空白保留、严格 Latin-1、17/18 字节容量边界、阶段中途失败的轨迹、关闭轨迹、
请求复用隔离、可选装配、同一 trace 传递、单次日志调用及日志异常不覆盖生成结论。

`tests/test_service.py` 的 fake_pipeline 是明确标注的测试替身，矩阵不是合法二维码。
它只验证编排；不能替代独立参考码字、矩阵正确性、五份真实 demo 或手机扫码。
这些测试也不替代四个人各自至少三个非平凡扩展测试。

`evidence/` 只有目录占位，五份 demo 尚未生成；不要把手写预期复制成实际运行证据。
本轮新增忽略 outputs/、data/usage/、data/diagnostics/、tmp/ 和 *.log；
没有全局忽略 *.txt / *.csv，后续真实演示文件可以正常入库。

## 共享 main 与后续协作

1. 本版按用户明确指示，在本地复核和检查通过后直接提交 main，作为四人的共同起点。
2. 本次检查是代码与运行复核，团队的非作者评审仍待完成；未配置分支保护或正式 CI。
3. 四人同步同一个 main 提交，再各自建立功能分支。后续公共变更继续按 PR/非作者评审约定处理。
4. 接口变更同步规划 10 和所有调用方；机房复验及完整 QR 验收继续保留为待办。

根目录 README 目前是开发入口，最终评分材料须由团队依据真实实现和课程规则自行完成。
