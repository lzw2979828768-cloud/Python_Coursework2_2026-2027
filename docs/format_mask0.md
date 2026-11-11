# 格式信息 BCH 与固定 Mask0

实现位置：`qr_app/core/format_info.py` 和 `qr_app/core/fixed_mask.py`。
保留现有函数签名，不新增应用依赖。基础服务现在可以生成完整的 V1/L/Mask0 主体矩阵。

## 格式信息编码

`build_format_bits(ecc_level, mask_id)` 返回高位在前的 15 个整数 0/1，类型为 tuple。
ECC 的格式编码是 L=01、M=00、Q=11、H=10；后接 3 位掩码编号，组成 5 位信息。
自行使用生成多项式 0x537 进行 BCH 长除法，拼接 10 位纠错余数后，再与 0x5412 异或。
这里没有调用 reedsolo；数据码字的 RS 与格式信息的 BCH 分别实现。

L/Mask0 的结果：

```text
111011111000100
```

函数支持四种实际 ECC 等级与 0..7 掩码编号的 32 种格式组合。类型错误抛 TypeError，
未知等级/超范围编号抛 ValueError；不接受 bool 冒充掩码编号，不自动规范化字符串。
支持这些格式位不代表八掩码评分扩展已实现。

## 固定 Mask0

`apply_fixed_mask_zero(layout, plan, *, trace=None)`：

1. 检查布局与计划的版本/容量一致，格式位置已保留，固定深色模块为黑色且已保留。
2. 复制主体，仅翻转非保留区中 (row+col)%2==0 的模块。
3. 为计划的实际 ECC 与 Mask0 生成格式信息，写入左上和远端两份共30个预留位置。
4. 返回 MaskSelection：mask_id=0、只读 final_matrix、空 penalty_scores。

坐标写入与返回位序一致，跳过时序位置 (6,8)/(8,6)，不覆盖独立的固定深色模块。
原始 MatrixLayout、保留区和早期轨迹不变。写格式位会有意修改格式预留位置，
与掩码翻转严格跳过保留区是两个不同操作。

新增真实步骤：mask0.applied、mask0.format_bits、mask0.final_matrix。
分别保存格式写入前的掩码矩阵、15位格式码字、写入两份格式后的最终主体。
中途失败保留已完成的步骤，不返回不完整的最终二维码。

## 完整服务结果

```python
from qr_app.models import QRRequest
from qr_app.service import QRService

result = QRService().generate_qr(QRRequest(text="known"))
print(result.generation_success)       # True
print(result.matrix.shape)             # (21, 21)
print(result.mask_id)                  # 0
print(result.error_code)               # None
print(len(result.trace_steps))         # 25
print(result.matrix.flags.writeable)   # False
```

25 步为前置2步、Byte编码7步、RS7步、矩阵6步、Mask0/格式3步。
关闭轨迹不改变输出矩阵；日志未接入时 logging_status=not_enabled。
仅改变请求的 cli/gui 来源字段也会得到相同矩阵，这不是已实现 CLI/GUI 应用的声明。

## 验证

```powershell
python -X utf8 -m unittest tests.test_format_info tests.test_fixed_mask -v
python -X utf8 -m unittest discover -s tests -v
```

预期为21项专项测试、97项总测试全部通过。验证内容包括：

- 实际读取 Thonky 的全部32个公开格式字符串，并与独立工具核对。
- 两份格式信息的位序与坐标、全部八组 V1/V2 实际 ECC 组合的 Mask0 完整矩阵。
- 800组不同长度/字节内容的完整编码结果与 qrcode 8.2 逐格一致，覆盖全部256种字节值。
- 保留区保护、原布局/历史快照不变、Mask0合法值0、评分为空、错误参数及阶段失败。
- 三个可编码作业样例成功；字符不支持、容量超限按原规则失败。

已用本机 OpenCV 4.12 对 known、We've succeeded!、Latin-1混合样例、17个A和一个空格完成解码。
验证时仅在内存中添加4模块白边、每模块10像素；返回主体本身仍不含 quiet zone。
OpenCV 返回 UTF-8 文本字节，Latin-1样例按解码后的原始文本核对；应用的二维码输入编码仍为
ISO-8859-1，原始编码字节另由完整参考矩阵一致性核验。不能把这两种字节表示混为一谈。

qrcode 与 OpenCV 均为本机已有的离线验证工具，未加入 requirements，也不被应用或常规测试导入。
常规单元测试读取独立静态 fixture。实际输出、参考页和源码哈希见
[格式与Mask0验证记录](validation/format_mask0_python3139_20261111_221640.json)。

## 当前仍待完成

基础编码核心、CLI入口与五份正式Stage1 demo现已完成，见[Stage1本机验收](../evidence/stage_1/README.md)。
图像渲染/保存、GUI、教学机房与
真实手机扫码验收仍待后续完成。版本自动选择、完整八掩码评分、步骤界面和使用日志仍属个人扩展。
V2/其他ECC的核心测试使用显式参考计划，没有据此实现生产版本选择策略。

参考：[格式信息算法](https://www.thonky.com/qr-code-tutorial/format-version-information)、
[32个格式字符串](https://www.thonky.com/qr-code-tutorial/format-version-tables)、
[掩码公式](https://www.thonky.com/qr-code-tutorial/mask-patterns)。
