# CLI 使用与验证

CLI 复用 `QRService.generate_qr()`，固定基础模式 **V1 / L / Mask0 / Byte**。
它显示完整的21×21数值矩阵及真实步骤，不提供 PNG 或 GUI。
标准输入使用 UTF-8 传输；二维码内容仍严格按 ISO-8859-1 编码，容量为17字节。
中文、希腊字母等不支持字符会报错，不会改用 UTF-8 编码二维码。

## 在项目根目录运行

当前已验证的 Python 3.13.9 路径是 `D:\python\python.exe`。
先在PowerShell切换到项目根目录：

```powershell
Set-Location -LiteralPath 'F:\文件\python\2026-2027大三上\Coursework2'
```

首次使用运行 `main_cli.py`，先选 `1` 单行或 `2` 多行，也可以选择 `0` 退出。
单行输入 `known` 后回车即提交；多行输入用单独一行 `:end` 结束。

```powershell
# 查看选项，不生成二维码
& 'D:\python\python.exe' main_cli.py --help

# 打开单行/多行/退出菜单；Ctrl+C 中断
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

交互菜单如下，输入无效选项会重新提示，不创建生成请求：

```text
请选择输入方式：
1. 单行输入
2. 多行输入
0. 退出
```

选 `1` 后输入一行，按回车提交；首尾空格保留，空行会作为空输入失败请求提交。
选 `2` 后可输入多行，例如：

```text
Hello
QR
:end
```

只有单独一行 `:end` 才结束，它不进入二维码内容。` :end`、`:end ` 和 `x:end` 都是普通内容。
行间原有换行及首尾空格均保留；只去掉最后一行的提交回车。需要保留末尾换行时，在 `:end` 前额外输入空行。
CRLF占2字节、LF占1字节，空格/换行同样计入17字节容量。立即输入 `:end` 会提交空输入并报错。
若文本需要包含单独一行 `:end`，使用下方 `--stdin`；单行文本 `:end` 也可以在模式1或 `--text` 中输入。

选 `0` 以退出码0退出，不生成、不导出。收到不完整输入的EOF时返回2，不提交部分文本；多行无需使用Ctrl+Z结束。
每次运行最多提交一个生成请求，完成后退出，需要再次生成时重新启动。
`--text` 和 `--stdin` 都直接编码，不显示菜单、不识别 `:end`；它们互斥，以 `-` 开头的参数文本可写为 `--text=-abc`。

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
| 0 | 生成成功、成功显示帮助，或菜单选择0退出 |
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
当前菜单版本在本机 Python 3.13.9 下通过42项CLI/报告测试、全量139项测试，详见
[菜单实际验证记录](validation/interactive_input_python3139_20261112_000620.json)。
原CLI的33项/全量130项测试保留为[历史记录](validation/cli_python3139_20261111_225943.json)。

五份正式 `demo_1.txt` 至 `demo_5.txt` 和证据清单已完成，见[正式证据入口](../evidence/README.md)。
五份demo记录的是菜单加入前的源码版本383b76c，保留为真实历史，不覆盖或改写。
运行 `python -X utf8 scripts/stage1_evidence.py --historical` 可核验其原文、步骤、矩阵、文件哈希及当时的Git源码。
不带 `--historical` 则严格比较当前源码，当前菜单/测试更新后会报告版本不同；历史核验通过不代表新代码已测试。
当前只输出数值矩阵和步骤报告；二维码图片、PNG保存、GUI、手机扫码和学校CI仍待后续完成。
