# 真实运行证据

Stage1 本机功能、五份正式 demo 和阶段文档已完成。证据于2026-11-11真实采集，
应用源码版本为 `383b76cf9223c96c75ab6f39c43a8fe9ae6119bc`。

| 输入原文 | 正式文件 | 实际结果 | 真实步骤 |
|---|---|---|---|
| `known` | [demo_1.txt](stage_1/demo_1.txt) | 成功，5字节，21×21矩阵 | 25 |
| `We've succeeded!` | [demo_2.txt](stage_1/demo_2.txt) | 成功，16字节，21×21矩阵 | 25 |
| `~¡256_-_aA&ñ` | [demo_3.txt](stage_1/demo_3.txt) | 成功，12字节，21×21矩阵 | 25 |
| `From α to ɷ...` | [demo_4.txt](stage_1/demo_4.txt) | `UNSUPPORTED_CHARACTER`；首个不支持字符索引为5 | 0 |
| `Sugarplum_Fairy_Nightmare` | [demo_5.txt](stage_1/demo_5.txt) | `CAPACITY_EXCEEDED`；25字节超过17字节容量 | 1 |

五份 txt 是实际 CLI 导出的原文件，包含原文、参数、结果、各步说明及完整载荷，未手工补写算法步骤。
第四项在严格字符转换时失败，没有完成的编码步骤；第五项完成字符转换后失败，故保留输入码字。
这两个预期失败是正确的基础模式行为。

- [Stage1 验收说明](stage_1/README.md)：B01—B10逐项证据、复现及使用方法。
- [manifest.csv](manifest.csv)：六个运行制品的来源、预期/实际、请求ID、版本、环境与 SHA-256。
- [capture.json](stage_1/capture.json)：五次真实CLI命令/输出/退出码、交互输入检查、130项测试实际输出、34个源码/fixture哈希。

在项目根目录验证，不会重新生成或覆盖 demo：

```powershell
& 'D:\python\python.exe' -X utf8 scripts/stage1_evidence.py --historical
```

预期以 `PASS: 5 exact inputs, 6 artifact hashes` 开头。此命令校验已有证据与记录的383b76c Git源码；
新菜单是后续改动，不用旧记录证明其已测试。不加 `--historical` 时严格比较当前源码，版本不符会明确失败。
若要重新执行单元测试，另运行 `python -X utf8 -m unittest discover -s tests -v`。

采集由本机脚本执行，标签为 `automated_local_capture`；学生个人贡献、组内非作者评审和教师验收分别记录。
分支与采集标签的调整见 `capture.json.metadata_revision`，原始CLI输出和五份demo保持原样。
本次仅使用五个公开作业字符串，没有真实用户日志；清单记录必要的本机路径/环境元数据。
GUI、PNG、手机扫码、教学机房和学校 CI 证据仍待后续完成。
