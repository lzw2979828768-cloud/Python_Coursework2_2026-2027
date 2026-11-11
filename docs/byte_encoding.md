# Byte 模式数据码字编码

实现位置：`qr_app/core/byte_encoder.py` 的 `encode_data(data_bytes, plan, *, trace=None)`。
沿用公共契约 1.0，不新增依赖。先调用 encode_text 严格编码，再将 bytes 交给 encode_data。

## 已完成的步骤

| step_id | 记录内容 |
|---|---|
| data.mode_indicator | Byte 模式的 0100 |
| data.character_count | 按计划指定宽度记录实际字节数；当前 V1/V2 为 8 位 |
| data.payload | 按高位在前展开的原始字节位流 |
| data.terminator | 不超过剩余容量的最多 4 个零 |
| data.byte_alignment | 补零至 8 的倍数；记录实际追加的位，允许为空 |
| data.pad_codewords | 从 EC 开始交替追加 EC / 11，填满计划的数据码字容量 |
| data.data_codewords | 完整数据码字 bytes，交给下一阶段生成纠错码字 |

每一步完成后才记录。主体函数不写文件、不修改原文或计划、不追加 ECC 和余数位。
超限抛出 CAPACITY_EXCEEDED，不截断，也不自动换版本。错误参数类型抛 TypeError。
关闭或不传轨迹时输出码字不变。

当前 V1/V2 单一 Byte 段具有 4 位模式、8 位长度和整字节数据；合法输入追加 4 位终止后
恰好字节对齐，因此这一范围的额外字节对齐位为空。函数仍显式完成并记录该检查。
空 bytes 在纯编码层可形成合法空段；服务仍按应用规则拒绝空用户输入。

## known 的独立推导

ASCII/Latin-1 字节是 `6B 6E 6F 77 6E`，输入长度为 5。

| 部分 | 位数 |
|---|---:|
| 模式 0100 | 4 |
| 字节数 00000101 | 8 |
| 5 个输入字节 | 40 |
| 终止 0000 | 4 |
| 额外字节对齐 | 0 |
| 12 个填充码字 | 96 |
| 总计 | 152，即 19 个数据码字 |

最终结果：

```text
40 56 B6 E6 F7 76 E0 EC 11 EC 11 EC 11 EC 11 EC 11 EC 11
```

前七个字节来自模式、长度、输入和终止位的拼接；后十二个字节是 EC/11 交替填充。
17 个 A 刚好装满 V1/L，无填充码字；16 个 A 仅有一个 EC 填充码字；18 字节直接拒绝。

## 测试与验证

```powershell
python -X utf8 -m unittest tests.test_byte_encoder -v
python -X utf8 -m unittest discover -s tests -v
```

Byte 编码实现时新增 10 项编码测试和 1 项接入测试，当时总计 42 项；当前加入 RS 纠错后为 56 项。
`tests/fixtures/byte_mode_vectors.json` 保存手工推导的 known、含零及高位字节、Latin-1
三个完整码字向量，期望值不由被测函数生成。另覆盖容量边界、错误类型、空段、轨迹、
关闭轨迹及显式传入 V2/L 计划的 32/33 字节边界。V2 计划测试不表示版本选择扩展已实现。

服务接入测试用真实 encode_data，并观察真实 ECC 函数及矩阵阶段的输入；它验证 19 个码字被交接，
且后续失败不会丢失已完成轨迹。通用编排测试中的模拟矩阵仍不是 QR 正确性证据。

通过服务自行查看实际结果：

```python
from qr_app.models import QRRequest
from qr_app.service import QRService

result = QRService().generate_qr(QRRequest(text="known"))
step = next(s for s in result.trace_steps if s.step_id == "data.data_codewords")
print(step.step_id)              # data.data_codewords
print(step.payload.hex(" "))     # 上述 19 个码字
print(len(result.trace_steps))   # 16：前置 2 步，加数据编码和 RS 各 7 步
print(result.error_code)         # FEATURE_UNAVAILABLE：当前停止在待实现的矩阵阶段
```

发布前复核通过 42 项测试，并以整数移位/掩码独立反向解析 510 组输出，覆盖全部 256 种字节值、
V1/L 的 0–17 字节与 V2/L 的 0–32 字节。原始数据、模式、长度、终止位和填充均一致。
[发布前验证记录](validation/byte_encoder_pre_publish_python3139_20261111_200618.json)保存实际结果及源码哈希。

## 后续工作

数据码字编码和 build_final_codewords 现已完成，参见[RS 纠错说明](error_correction.md)。
下一步实现矩阵落位，再完成格式信息与 Mask0。当前整体结果仍为失败且 matrix=None，没有可扫码二维码。

参考：[Thonky Data Encoding](https://www.thonky.com/qr-code-tutorial/data-encoding)、
规划 08 的 Byte 容量与输入规则、规划 10 的 bytes/码字/轨迹接口。
本文件是开发说明；五份 Stage1 正式 demo 尚待完整流程实际运行后生成。
