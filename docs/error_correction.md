# 数据 Reed–Solomon 纠错与最终位流

实现位置：`qr_app/core/error_correction.py` 的
`build_final_codewords(data_codewords, plan, *, trace=None)`。
公共接口保持 1.0；新增已验证依赖 reedsolo==1.7.0。

## 输入、输出和算法

输入必须是已经完成 Byte 模式填充的数据码字 bytes，V1/L 为 19 个字节，
不是原始文本的 5 个字符或 5 个字节。长度与 plan.data_codewords 不一致时抛 ValueError，
参数类型错误时抛 TypeError。服务会把内部计算故障转为安全错误，并保留此前轨迹。

处理顺序：

1. 按 block_groups 的顺序取得各数据块。
2. 对每块调用 reedsolo，生成该计划规定数量的纠错码字。
3. 分别逐列交织数据块和纠错块；短块耗尽后跳过。
4. 数据交织结果在前、纠错交织结果在后，组成完整码字 bytes。
5. 将码字按高位在前展开为整数位 tuple，再追加版本规定的零余数位。

QR 参数显式固定为 GF(256)、本原多项式 0x11D、generator=2、fcr=0、c_exp=8、nsize=255。
单块的数据加纠错长度不得超过 255，避免库自动分块导致码字数量变化。
库输出的数据前缀和长度也会检查。函数不修改输入、不写文件、不访问界面。

输出 FinalCodewords 包含：

- interleaved_codewords：数据与纠错交织后的 bytes，不包含余数位。
- bitstream：包含版本余数位的 tuple[int, ...]，元素只有整数 0/1。

## known 的结果

19 个数据码字：

```text
40 56 B6 E6 F7 76 E0 EC 11 EC 11 EC 11 EC 11 EC 11 EC 11
```

7 个纠错码字：

```text
EB 90 48 A5 3B 9B 11
```

V1/L 为单块，所以将这两段顺序连接即可得到 26 个码字。
V1 没有余数位，最终位流为 26 × 8 = 208 位。

## 分块规格修正

已实际读取并核对 [Thonky 纠错表](https://www.thonky.com/qr-code-tutorial/error-correction-table)。
原规划中“V2/Q、V2/H 是多块”的表述有误；V1/V2 的八种版本/ECC组合都为单块。
V2/Q 为 22 数据 + 22 ECC，V2/H 为 16 数据 + 28 ECC，均另有 7 个零余数位。
因此 V2 最终为 44 个码字、359 位，余数位不进入 RS 编码。

生产资源表目前仍只有 V1/L；测试参考中保存了已核对的八组规格。
这不表示版本选择扩展已实现。通用分块和不等长交织使用独立小样本验证，
这些小样本不是实际 V1/V2 多块二维码，也没有扩大项目支持的版本范围。

## 真实轨迹

单块调用新增七个步骤：

| step_id | 已完成内容 |
|---|---|
| ecc.block_1.data | 按计划取得的数据块 |
| ecc.block_1.parity | 该块的 RS 纠错码字 |
| ecc.interleaved_data | 数据块交织结果 |
| ecc.interleaved_parity | 纠错块交织结果 |
| ecc.final_codewords | 完整码字序列 |
| ecc.remainder_bits | 实际追加的零余数位，V1 为空 tuple |
| ecc.bitstream | 含余数位的完整位流 |

每个步骤完成后才记录。库中途失败会保留数据分块步骤，不伪造尚未生成的纠错结果。
服务对 known 当前共保留 16 步：前置 2 步、数据编码 7 步、纠错 7 步。
随后因矩阵模块待实现而返回 FEATURE_UNAVAILABLE，matrix=None。

## 自行验证

在项目根目录执行：

```powershell
python -X utf8 -m unittest tests.test_error_correction -v
python -X utf8 -m unittest discover -s tests -v
```

预期为 13 项纠错专项测试、56 项总测试全部通过。
也可以在 Python 3.13.9 中直接调用：

```python
from qr_app.core.byte_encoder import encode_data, encode_text
from qr_app.core.error_correction import build_final_codewords
from qr_app.service import _baseline_plan

plan = _baseline_plan()
data = encode_data(encode_text("known"), plan)
final = build_final_codewords(data.data_codewords, plan)
print(final.interleaved_codewords[-7:].hex(" ").upper())  # EB 90 48 A5 3B 9B 11
print(len(final.interleaved_codewords))                  # 26
print(len(final.bitstream))                             # 208
```

独立依据包括 Thonky 公开的 V1/M 算例及不依赖 reedsolo 的移位有限域乘法、多项式长除法、
零综合征检查。公开算例的数据来自 Alphanumeric 模式，作为 RS 层参考有效；应用仍只做 Byte 模式。
known 的纠错参考由独立算法推导，未用被测 reedsolo 输出生成。

本轮 56 项测试、800 组随机 RS 交叉核验（八组规格、覆盖全部256种字节值）、模块导入、
依赖及编译检查全部通过。真实输出及源码/参考 fixture 哈希见
[纠错验证记录](validation/error_correction_python3139_20261111_202929.json)。
这不替代完整 QR、手机扫码、正式 CI 或团队非作者评审。

下一步实现 build_matrix，消费这里得到的 208 位并构造功能区、保留区与数据落位。
