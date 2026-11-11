# Stage1 本机验收与复现

状态：基础功能与本机 Stage1 证据交付完成，可开始 Stage2。此结论限于本机运行与已保存证据，
不代替学校现场演示、机房复验、团队非作者评审或最终评分材料。

## 版本与来源

- 应用源码：`383b76cf9223c96c75ab6f39c43a8fe9ae6119bc`，已发布的 CLI 版本。
- 分支现名：`feature/stage1-evidence`（采集后重命名）；本次增加采集工具、证据与说明，没有修改应用算法或测试。
- 开始采集：`2026-11-11T23:10:43.237479+08:00`。每份报告另有请求UUID及带时区时间。
- 环境：Windows 11，CPython3.13.9（`D:\python\python.exe`）、numpy2.2.6、reedsolo1.7.0。
- 应用与测试源码没有未提交修改（`source_dirty=false`）；采集工具/证据存在未提交改动，
  因此整体工作区为 `working_tree_dirty=true`。两字段范围见 [capture.json](capture.json)。
- 采集执行标签为 `automated_local_capture`，表示本机脚本执行，未指定学生作者或人工评审者。
- 分支标签与采集标签调整记录在 `capture.json.metadata_revision`；五份demo及原始CLI输出未改动。
  采集时的工具哈希保留为 `capture_tool_sha256`，调整后的校验工具哈希另记为 `verification_tool_sha256`。

## B01—B10 对照

| 要求 | 本机结论及证据 |
|---|---|
| B01 动态CLI输入 | `capture.json` 的 `interactive_cli` 记录通过标准输入动态提交 `known` 的实际输出；另有参数输入五次运行及CLI交互边界测试 |
| B02 Byte编码 | demo_1—3保留严格ISO-8859-1、模式位、长度位、载荷、终止/字节对齐/填充步骤；[独立手工向量](../../tests/fixtures/byte_mode_vectors.json)与编码测试通过 |
| B03 Level L RS | demo_1—3保留19数据码字、7ECC码字和26最终码字；[独立RS参考](../../tests/fixtures/rs_reference_vectors.json)及[有限域长除法参考](../../tests/rs_reference.py)对应测试通过 |
| B04 numpy二维矩阵 | demo_1—3的最终矩阵均为uint8、21×21、0白1黑，快照与完整行列可查；核心及CLI测试通过 |
| B05 功能区、数据落位和填充 | demo_1—3逐步保留定位/分隔/时序/dark/保留区/数据落位矩阵；V1无对齐图案；[独立布局参考](../../tests/fixtures/matrix_reference_vectors.json)与矩阵测试通过 |
| B06 自行计算格式纠错 | demo_1—3均输出L/Mask0格式位 `111011111000100`；[32组公开格式参考](../../tests/fixtures/format_mask0_reference_vectors.json)与BCH/双副本写入测试通过；格式纠错未调用reedsolo |
| B07 固定V1/Mask0并输出数组 | 五份报告请求参数固定V1/L/Mask0；三份成功报告实际mask为0，输出21×21数组；known矩阵还逐格对照独立参考 |
| B08 五份带注释过程文件 | [demo_1](demo_1.txt)、[demo_2](demo_2.txt)、[demo_3](demo_3.txt)、[demo_4](demo_4.txt)、[demo_5](demo_5.txt)均为真实CLI原始导出，内含各步Title/Explanation |
| B09 失败前轨迹 | demo_4字符转换未完成，0步；demo_5仅保留完成的字符编码1步。两者无矩阵、实际计划和掩码均为null，不伪造后续结果 |
| B10 阶段文档与证据 | 本说明、[证据入口](../README.md)、[manifest](../manifest.csv)、[采集记录](capture.json)、[CLI指南](../../docs/cli.md)构成本次本机交付 |

本轮重新运行全部130项单元测试并通过，实际输出在 `capture.json.unit_tests`，不是预填的测试结论。
其中的模拟流水线测试仅用于编排；编码正确性另有上述独立码字/布局/最终矩阵参考测试。
本轮不重复声称执行800组离线比较或手机扫码；这些历史检查的范围见
[格式/Mask0历史记录](../../docs/validation/format_mask0_python3139_20261111_221640.json)。

## 怎样阅读五份 demo

前三份成功报告各有25步：输入/计划2步、Byte7步、RS7步、矩阵6步、Mask0/格式3步。
`Input (JSON)`中的非ASCII和控制字符按JSON转义，例如 `\u00f1` 表示 `ñ`，并非改写输入。
所有位串、十六进制码字、bool保留区和uint8矩阵均完整保留，没有截断。

第四项的 `α` 与 `ɷ` 不属于ISO-8859-1；首个不支持字符为从0开始的索引5。
第五项能完成ISO-8859-1转换，但25字节超过基础容量17字节，因此只保留输入编码步骤。
两项均返回CLI业务失败退出码1，导出本身成功。

## 自行核验与复现

在项目根目录运行：

```powershell
# 只核验已有证据，不改写文件或重新生成
& 'D:\python\python.exe' -X utf8 scripts/stage1_evidence.py

# 重新运行所有单元测试
& 'D:\python\python.exe' -X utf8 -m unittest discover -s tests -v

# 现场演示动态输入，输入 known 后回车
& 'D:\python\python.exe' main_cli.py

# 查看完整真实步骤
& 'D:\python\python.exe' main_cli.py --text "known" --show-steps
```

校验脚本检查五个原文、结果/错误、25/25/25/0/1步、矩阵结构、known独立参考矩阵、
六个制品哈希、捕获工具与34个源码/fixture哈希，以及清单和报告的请求ID一致性。
`manifest.csv`不包含自己的哈希，避免自引用；报告和清单使用UTF-8与LF，由`.gitattributes`保留换行。
校验成功不等于重新执行测试；测试重跑使用上面的独立命令。

如只想试用导出，保存到已存在的 `outputs/`，不要覆盖正式demo。
采集命令为 `python -X utf8 scripts/stage1_evidence.py --capture`，它会拒绝已有证据。
需生成新版本时先保留/归档本版，更新源码版本关联后重新采集，不手改现有报告或只重算哈希来掩盖差异。
源码或测试变化后，旧版证据可继续作为历史，但校验脚本会报告当前源码与捕获版本不同。

## 下一阶段

Stage2先实现matplotlib二维码渲染（黑白模块、等比例、quiet zone）和PNG保存，
再接入PyQt5界面、Information说明与错误提示，最后实际手机扫码并在教学机房复验。
当前CLI不显示二维码图片，不保存PNG，不自动写使用CSV；这些功能没有在本阶段声明完成。
