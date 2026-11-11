# 测试参考数据

byte_mode_vectors.json 包含三组 V1/L 数据码字的完整手工推导向量：known、含零及高位字节、
Latin-1 的 ¡ñ。期望值来自模式/长度/数据/终止/填充字段的独立推导，没有调用被测函数生成。
每组记录输入字节、期望码字、推导说明和规范教程参考；尚无 ECC 或完整 QR 矩阵参考 fixture。

通用编排测试中的模拟矩阵不是合法 QR，不能用作编码正确性或手机扫码证据。

rs_reference_vectors.json 保存实际读取 Thonky 后核对的 V1/V2 单块规格、公开 V1/M 算例及 known 的
独立 RS 参考。公开算例使用 Alphanumeric 数据，在本项目仅作为模式无关的 RS 层参考。
known 的参考 ECC 来自 tests/rs_reference.py 的无查表有限域长除法，没有使用 reedsolo 生成期望值。
通用多块交织使用人工小样本；这些样本不是实际 V1/V2 多块符号。
