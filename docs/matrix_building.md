# 未掩码矩阵构建

实现位置：`qr_app/core/matrix_builder.py` 的 `build_matrix(bitstream, plan, *, trace=None)`。
输入是纠错阶段生成的整数 0/1 tuple，包含版本余数位；输出是 MatrixLayout。
支持计划中已有的 V1/V2，未新增应用依赖或版本选择功能。

## 已完成的内容

- 三个 7×7 定位图案和一模块宽的白色分隔区。
- V1 无对齐图案；V2 在 (18, 18) 放置 5×5 对齐图案。
- 第 6 行、第 6 列的黑白交替时序图案。
- 固定深色模块：(4×version+9, 8)，即 V1 的 (13, 8)、V2 的 (17, 8)。
- 两份格式信息共 30 个位置，预留为白色；实际格式位由后续模块写入。
- 从右下角按双列交替上下扫描，跳过第 6 列和所有保留模块，放入全部输入位。

坐标为 [row, col]，左上角为 (0, 0)。主体不含 quiet zone，也不添加掩码。

| 版本 | 主体尺寸 | 保留模块 | 数据模块/输入位数 |
|---|---|---:|---:|
| V1 | 21×21 | 233 | 208 |
| V2 | 25×25 | 266 | 359，含 7 个余数位 |

输出 modules 的 dtype 为 uint8、值仅为 0/1；reserved_mask 为 bool。
两者都是独立只读副本。函数不修改位流或计划，不读写文件，不调用外部生成器。

错误类型/计划类型抛 TypeError；长度不符、含 bool/非整数位、非 0/1 值、
计划码字数量与实际网格容量不符时抛 ValueError。最后一种错误保留已完成的功能区轨迹，
不会伪造数据落位完成步骤。余数位由纠错阶段生成，这里按输入原样落位。

## 真实步骤

| step_id | 载荷 |
|---|---|
| matrix.finder_patterns | 定位图案及分隔区后的 uint8 矩阵 |
| matrix.alignment_patterns | 完成对齐图案检查/放置后的 uint8 矩阵；V1 明确无此图案 |
| matrix.timing_patterns | 加入时序图案后的 uint8 矩阵 |
| matrix.function_regions | 固定深色模块和格式保留完成后的 uint8 矩阵 |
| matrix.reserved_mask | bool 保留区矩阵，True 表示禁止数据落位和掩码翻转 |
| matrix.data_placed | 完整的未掩码 uint8 数据布局 |

每次记录都立即复制，后续数据落位不会改变早期矩阵。关闭轨迹时输出布局保持一致。
矩阵构建自身有6步；服务对known当前共25步，包括后续格式信息/Mask0的3步。

## 独立参考与验证

测试用静态 fixture 来自本机已有 qrcode 8.2，生成过程没有调用 qr_app：
撤销参考结果的数据区 Mask0，将 30 个格式位置清零，保留固定深色模块，得到对应的未掩码布局。
逐个注入单个置位标记，独立提取 V1/V2 全部 567 个数据位置。结构探针包含余数位置，
不表示带非零余数位的探针是合法 QR。known 参考强制使用单一 Byte 段。

生产代码和常规单元测试都不导入 qrcode；常规测试只读静态 fixture。
qrcode 没有加入 requirements.txt，仅用于本机离线对照。不能将这些中间布局当作扫码证据。

验证已通过：

- 16 项矩阵专项测试：独立完整矩阵、逐位落位、功能区保护、错误输入、只读与轨迹。
- 总计 73 项单元测试，包括真实服务把 MatrixLayout 交给固定掩码阶段的接入验证。
- 800 组独立逐格对照，涵盖八组 V1/V2 规格、全部 256 种字节值。
- 编译、依赖和模块导入检查；应用导入不加载参考生成器或 GUI/分析库。

实际输出、参考来源和源码/fixture SHA-256 见
[矩阵验证记录](validation/matrix_builder_python3139_20261111_211628.json)。

## 自行验证

在项目根目录运行：

```powershell
python -X utf8 -m unittest tests.test_matrix_builder -v
python -X utf8 -m unittest discover -s tests -v
```

预期分别为16项和当前97项测试全部通过。直接调用示例：

```python
from qr_app.core.byte_encoder import encode_data
from qr_app.core.error_correction import build_final_codewords
from qr_app.core.matrix_builder import build_matrix
from qr_app.service import _baseline_plan

plan = _baseline_plan()
data = encode_data(b"known", plan)
final = build_final_codewords(data.data_codewords, plan)
layout = build_matrix(final.bitstream, plan)
print(layout.modules.shape)           # (21, 21)
print(layout.modules.dtype)           # uint8
print(layout.reserved_mask.dtype)     # bool
print(layout.reserved_mask.sum())     # 233
print((~layout.reserved_mask).sum())   # 208
print(layout.modules.flags.writeable) # False
```

## 当前边界与下一步

MatrixLayout仍是未掩码中间布局，保留在matrix.data_placed步骤。后续格式信息与Mask0现已完成，
QRService对有效基线请求返回成功和完整主体，详见[格式/Mask0](format_mask0.md)。
后续仍需CLI、正式demo、渲染/保存和真实手机扫码验收。

规范参考：[Thonky 矩阵落位](https://www.thonky.com/qr-code-tutorial/module-placement-matrix)、
[对齐图案位置](https://www.thonky.com/qr-code-tutorial/alignment-pattern-locations)。
