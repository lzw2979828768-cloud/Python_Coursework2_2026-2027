# CLI 使用与验证

CLI 复用 `QRService.generate_qr()`，固定基础模式 **V1 / L / Mask0 / Byte**。
它显示完整的21×21数值矩阵及真实步骤，不提供 PNG 或 GUI。
标准输入使用 UTF-8 传输；二维码内容仍严格按 ISO-8859-1 编码，容量为17字节。
中文、希腊字母等不支持字符会报错，不会改用 UTF-8 编码二维码。

## 在项目根目录运行

当前已验证的 Python 3.13.9 路径是 `D:\python\python.exe`。

```powershell
# 查看选项，不生成二维码
& 'D:\python\python.exe' main_cli.py --help

# 动态单行输入，回车提交一次；Ctrl+C 中断
& 'D:\python\python.exe' main_cli.py

# 参数输入
& 'D:\python\python.exe' main_cli.py --text "known"

# 同时显示完整编码步骤
& 'D:\python\python.exe' main_cli.py --text "known" --show-steps

# 显式导出；父目录必须已存在
New-Item -ItemType Directory -Force outputs
& 'D:\python\python.exe' main_cli.py --text "known" --steps-out outputs/known_steps.txt

# 已有报告需要显式允许覆盖
& 'D:\python\python.exe' main_cli.py --text "known" --steps-out outputs/known_steps.txt --overwrite
```

成功时应看到 `Generation: SUCCESS`、`Byte length: 5`、`Actual mask: 0`、
`Trace steps: 25`，以及21行、每行21个0/1的矩阵。`0`为白，`1`为黑，矩阵不含 quiet zone。
`--show-steps` 或导出报告还会包含模式/长度位、数据码字、ECC码字、中间矩阵、
保留区 bool 数组以及格式信息等真实快照。

交互输入只去掉一次提交回车，保留首尾空格；空行会作为空输入失败请求提交。
交互 EOF 表示没有提交。`--text` 原样使用参数；以 `-` 开头的文本可写为 `--text=-abc`。
`--text` 与 `--stdin` 互斥，省略它们则进入交互输入。

## 完整标准输入

`--stdin` 读取到 EOF，保留全部 CR、LF、TAB 和末尾空格/换行。文件应为 UTF-8，
不自动去 BOM、不规范化字符，也不把 UTF-8 字节数当作二维码容量。
PowerShell 管道可能添加换行或转换编码；需要精确保留文件时可由 Python 传输原始字节：

```python
from pathlib import Path
import subprocess
import sys

subprocess.run(
    [sys.executable, "main_cli.py", "--stdin"],
    input=Path("input.txt").read_bytes(),
    check=False,
)
```

## 失败与退出码

`From α to ɷ...` 应返回 `UNSUPPORTED_CHARACTER`，不生成矩阵、没有编码步骤；
`Sugarplum_Fairy_Nightmare` 是25字节，应返回 `CAPACITY_EXCEEDED`，仅保留已完成的输入编码步骤。
失败请求也可以用 `--steps-out` 导出原因和部分轨迹，未确定的实际计划/掩码显示为 `null`。
仅有空白的非空输入允许编码，同时显示警告。

| 退出码 | 含义 |
|---|---|
| 0 | 生成成功，或成功显示帮助 |
| 1 | 正常业务失败，如空输入、字符不支持、超容量 |
| 2 | 参数错误，或交互输入尚未提交便遇到 EOF |
| 3 | 输入/输出或报告保存失败；检查独立的生成状态 |
| 4 | 请求契约或内部处理错误 |
| 130 | 用户中断 |

PowerShell 中运行后查看 `$LASTEXITCODE`。生成错误写入 stderr，结果/矩阵写入 stdout。
如果生成和导出均失败，两种原因都会保留，退出码为3。保存失败不会重新生成、覆盖生成结论
或增加日志请求。当前入口未装配使用日志扩展，`Logging: not_enabled` 是正常状态。

## 报告与文件行为

报告为 UTF-8、LF 换行，记录请求 ID、带时区时间、请求参数、实际计划、结果、
错误/警告、日志状态、运行依赖版本和按原顺序采集的步骤。原文以 JSON 字符串显示，
例如换行显示为 `\n`、`ñ` 显示为 `\u00f1`；可以通过 JSON 解析还原。
位串、十六进制码字和完整矩阵不做截断。轨迹关闭时明确显示0步，不补造步骤。

默认不写文件；`--steps-out` 才会持久化报告。报告含原文和可逆数据，请使用适合分享的输入。
默认以独占创建方式保护已有文件；`--overwrite` 在同目录写临时文件，关闭成功后替换，
替换失败时保留旧文件并尝试清理本次临时文件。首次创建若写入中断，可能留下不完整文件，
不能据文件存在认定导出成功。父目录必须已存在，保存错误不会输出底层异常堆栈。
`outputs/`、`tmp/` 已忽略，不作为正式评分证据提交。

## 自动验证

```powershell
& 'D:\python\python.exe' -X utf8 -m unittest tests.test_cli -v
& 'D:\python\python.exe' -X utf8 -m unittest discover -s tests -v
```

CLI 测试覆盖真实服务、完整步骤、失败部分轨迹、输入保真、单次生成/日志调用、
文件覆盖保护、替换失败保留旧文件，以及 Windows 子进程的 UTF-8/CRLF 输入和退出码。
`known` 的终端矩阵还与已保存的独立参考矩阵逐格对比；不需要安装 qrcode/OpenCV。
本机 Python 3.13.9 已通过33项CLI/报告测试、全量130项测试，详见
[发布前复验记录](validation/cli_python3139_20261111_225943.json)。

五份正式 `demo_1.txt` 至 `demo_5.txt`、证据清单、GUI、手机扫码和学校 CI 仍需后续完成。
本轮临时验证导出不替代正式 Stage1 证据。
