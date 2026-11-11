# 测试参考数据

byte_mode_vectors.json 包含三组 V1/L 数据码字的完整手工推导向量：known、含零及高位字节、
Latin-1 的 ¡ñ。期望值来自模式/长度/数据/终止/填充字段的独立推导，没有调用被测函数生成。
每组记录输入字节、期望码字、推导说明和规范教程参考；当前另有独立 RS 和未掩码矩阵参考，见下文。

通用编排测试中的模拟矩阵不是合法 QR，不能用作编码正确性或手机扫码证据。

rs_reference_vectors.json 保存实际读取 Thonky 后核对的 V1/V2 单块规格、公开 V1/M 算例及 known 的
独立 RS 参考。公开算例使用 Alphanumeric 数据，在本项目仅作为模式无关的 RS 层参考。
known 的参考 ECC 来自 tests/rs_reference.py 的无查表有限域长除法，没有使用 reedsolo 生成期望值。
通用多块交织使用人工小样本；这些样本不是实际 V1/V2 多块符号。

matrix_reference_vectors.json 来自已有 qrcode 8.2，生成过程不调用 qr_app。撤销参考数据区的 Mask0，
清零30个格式位置，保留深色模块，得到未掩码布局。逐个标记位独立提取208/359个数据位置，
线性索引为 row * matrix_size + col。包含 V1/V2 的 known 完整未掩码矩阵与功能区、保留区。
结构探针包含 V2 余数位置，不声称非零余数位是合法 QR。常规测试只读静态 JSON，不导入 qrcode。

format_mask0_reference_vectors.json 包含实际读取Thonky取得的32个格式字符串，与qrcode 8.2交叉核对；
另包含独立提取的两份格式写入坐标和八组强制Byte/Mask0的known最终矩阵。
生成过程不调用qr_app。常规测试读取静态JSON，不依赖参考生成器或OpenCV。
