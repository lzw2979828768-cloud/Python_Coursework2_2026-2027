# PyQt5 界面框架与交互规划

版本：v1.3　｜　更新日期：2026-11-12　｜　状态：基础生成页、渲染、保存及Information已实现；人工验收待完成

> 当前实施：`main_gui.py`提供正式文本输入、实时字节提示、Generate/Clear input、真实QR显示和Save PNG。
> 草稿、已提交请求和实际结果分开管理，失败清旧图，50项前端测试通过，见[正式生成页面](../docs/gui_generation.md)。
> Information已作为第二个真实页签实现，支持分节、F1、返回及只读说明，58项前端测试通过，见[Information说明](../docs/information.md)。
> 下文保留完整规划；个人扩展页签尚未接入，不将规划中的控件视为已经提供。

用户已确认课堂使用 **PyQt5**。本项目据此采用 **PyQt5 本地桌面GUI**，保留CLI，两者共用一套QR生成服务。四人的真实姓名、能力匹配和任务归属暂缓，本文件按功能模块规划，不指定真实人员。

本文件是编码前参考，不是已实现功能说明或最终评分文档。作业依据见 [05_作业要求汇总.md](05_作业要求汇总.md)，接口见 [02_系统架构与接口规划.md](02_系统架构与接口规划.md)。

输入校验、默认值、空白和自动/手动选择按 [08_输入与自动选择规则.md](08_输入与自动选择规则.md) 细化；日志告知、记录字段、隐私及真实演示证据按 [09_日志隐私与演示证据规范.md](09_日志隐私与演示证据规范.md) 细化。当前开发暂用GitHub，真实人员分配继续待定。

公共签名/字段和责任以 [10_公共接口与修改权限规范.md](10_公共接口与修改权限规范.md) 为细化契约：GUI接收QRService实例的generate_qr方法；请求timestamp是带时区datetime；save_figure不关闭调用方Figure，Qt页面负责画布生命周期。

## 1. 框架结论

| 事项 | 决策 | 依据及边界 |
|---|---|---|
| 形态 | 本地桌面窗口 | 作业允许GUI或网站，不要求同时做两种 |
| 框架 | **PyQt5** | 用户确认课堂使用，符合优先采用课堂工具的要求 |
| 图像 | matplotlib + Qt画布 | 满足作业至少使用matplotlib的要求 |
| 编码入口 | GUI/CLI共用 `generate_qr(QRRequest)` | 界面不重写编码、RS、矩阵、掩码算法 |
| 页面 | 单一主窗口，四个页签 | Generate QR、Generation Steps、Usage Analytics、Information |
| 布局 | 首版采用Python代码与Qt布局管理器 | 不用绝对坐标摆放；便于代码评审和合并 |
| 运行 | 同一进程内调用Python模块 | 不增加网页服务器、浏览器、远程部署和账号系统 |
| 交付 | 源码与已验证依赖 | 先满足机房配置运行，不预先要求打包exe |

**PyQt5负责窗口，matplotlib负责QR和统计图，自编核心负责QR算法。** 采用桌面GUI后，手机通过扫码识别屏幕上的QR，不需要访问本机网站。

### 方案比较

| 方案 | 对本作业的适配点 | 成本/限制 | 本次选择 |
|---|---|---|---|
| PyQt5 | 已有课堂依据；原生文件对话框；可嵌入matplotlib | 管理控件状态、Qt运行库和DPI | **主方案** |
| Streamlit | Python快速搭建网页和图表 | 另核查课程许可；处理脚本重运行与会话；本地Web服务 | 不实施 |
| Panel / Dash | 浏览器图表交互 | 额外学习、许可核查及网页状态设计 | 不实施 |
| Flask + 自编网页 | 页面控制自由 | 还需HTML/CSS、浏览器事件、接口和服务配置 | 不纳入首版 |
| Tkinter | 标准库桌面工具 | 作业明确禁止 | 不使用 |

上述比较针对本项目，不是通用框架排名。本机是否安装某个工具不能代替课堂使用依据。

若课堂主要使用Qt Designer，可在编码前统一选择Designer工作流：保留 `.ui`，记录 `pyuic5` 命令，生成文件与手写业务分开，禁止手改自动生成文件而导致下次生成覆盖。不要混用未提交的本地UI资源。此选择不改变PyQt5框架方向。

## 2. 需求到界面的映射

| 要求 | 页面/功能 | 必须能展示 |
|---|---|---|
| 文本输入、Version1生成 | Generate QR基础模式 | 动态输入，调用真实共享服务 |
| 黑白可扫描图、matplotlib | 结果画布 | 真实手机解码，内容与输入一致 |
| 保存图像 | Save QR + QFileDialog | PNG保存、重开与扫码 |
| 错误处理 | 输入提示、结果错误区 | 字符不支持、容量不足和IO失败 |
| 数据保护、Information | 输入区提示及Information页 | 信息表示、输入管理、完整性、安全、日志行为 |
| 版本/ECC扩展 | 模式、版本/ECC选择、实际参数 | 自动/手动、容量边界 |
| 完整掩码扩展 | Mask选择和评分表 | 八候选、四评分、最优与手动 |
| 步骤扩展 | Generation Steps | 真实轨迹、前后导航、保存某步 |
| 日志扩展 | 请求完成后记录；Usage Analytics | 成功/失败记录、累计统计与图表 |

Stage2先实现Generate QR与Information。其他页签在扩展未接入时隐藏或禁用，明确尚未提供，不能以预制结果冒充已运行功能。最终保留基础模式以复现V1/L/Mask0。

## 3. 主窗口与布局

| 组件 | 职责 |
|---|---|
| `QApplication` | GUI进程仅一个；CLI与导入核心时不创建 |
| `QMainWindow` | 菜单、中心区、状态栏 |
| `QTabWidget` | 四页签，切换不重新生成QR |
| `QVBoxLayout/QHBoxLayout/QFormLayout` | 自适应排列输入、按钮、图像与说明 |
| `QSplitter` | 允许调整输入/结果区域宽度 |
| `QScrollArea` | 小窗口或高DPI时仍能到达控件 |
| `QStatusBar`和持久标签 | 短暂成功提示与持续错误/警告分开 |
| `QFileDialog` | 保存PNG；取消是正常操作 |
| `QMessageBox` | 覆盖/清除历史确认及必要IO错误提示 |

```text
┌───────────────────────────────────────────────────────────────┐
│ QR Application                                  File  Help    │
├───────────────────────────────────────────────────────────────┤
│ Generate QR │ Generation Steps │ Usage Analytics │ Information │
├─────────────────────────────┬─────────────────────────────────┤
│ Text                        │ Last submitted result           │
│ ┌─────────────────────────┐ │ Status / Error / Warning        │
│ │ QPlainTextEdit          │ │                                 │
│ │ 保留实际输入             │ │       matplotlib QR画布          │
│ └─────────────────────────┘ │                                 │
│ Byte information            │ Version / ECC / Mask / Size     │
│ Baseline / Extended         │ Request ID / Logging status     │
│ Version   ECC   Mask        │ [Save QR] [View steps]           │
│ [Generate] [Clear input]    │ Mask scores: N1 N2 N3 N4 Total  │
│ 本地记录与风险提示           │                                 │
├─────────────────────────────┴─────────────────────────────────┤
│ 状态栏；重要警告不只作为短暂消息展示                             │
└───────────────────────────────────────────────────────────────┘
```

线框表示区域关系，不是固定像素设计。初始尺寸可参考1280×800，不能要求所有机房电脑必须使用该分辨率。小窗口可滚动、调整分区；验证Windows 100%、125%、150%及必要时200%缩放，避免按钮、说明和quiet zone被裁切。

界面建议采用清晰英文标签，规划文档使用中文；实现前统一最终语言，不在每个控件上堆叠长双语说明。

## 4. Generate QR页

| 控件 | Qt组件 | 行为规则 |
|---|---|---|
| 文本 | `QPlainTextEdit` | 不自动trim、转小写、删除不支持字符或截断 |
| 字节说明 | `QLabel` | 可编码时显示ISO-8859-1字节数；不可编码时说明原因，不以UTF-8字节数替代 |
| 模式 | `QRadioButton + QButtonGroup` | Baseline/Extended；改变模式不生成 |
| Version | `QComboBox` | Auto、1、2；基础锁定1 |
| ECC | `QComboBox` | Auto、L/M/Q/H；基础锁定L |
| Mask | `QComboBox` | Auto、0..7；基础锁定0 |
| 容量提示 | `QLabel` | 手选组合显示容量，自动模式说明提交时解析 |
| Generate | `QPushButton` | 唯一创建QRRequest的界面操作；每次提交调用一次服务 |
| Clear input | `QPushButton` | 只清空草稿，不清除历史日志 |
| QR画布 | `FigureCanvasQTAgg` | 显示真实成功结果，维持黑白、正方形和quiet zone |
| 结果详情 | 只读标签/文本 | 显示实际版本/ECC/掩码，不把Auto当作实际值 |
| 评分 | 只读表格 | Mask、N1/N2/N3/N4、Total；标出最终使用项 |
| Save QR | `QPushButton` | 仅当前成功结果可用，保存已有结果 |
| View steps | `QPushButton` | 有真实轨迹时开放，切到步骤页 |

用 `itemData/currentData` 保存枚举值，显示文字与程序值分开。掩码0是有效选择，不能将0的假值解释为“没有选择”。

输入提示可预检查，但最终业务校验由服务执行。真正提交到服务的失败请求也要记使用日志；改草稿、选参数、取消保存均不算新的生成请求。

Stage2锁定基础参数；版本扩展和掩码扩展接入并验收后再分别开放相应控件。自动版本/ECC规则沿用架构文档，手选超限不能悄悄换参数。

## 5. 信号、状态和防重复

### 5.1 信号连接

构建控件时连接一次信号，不在生成结束或页签切换时反复 `.connect()`。模式切换批量修改控件时使用更新保护或 `QSignalBlocker` 防止级联回调。

| 事件 | 应执行 | 不应执行 |
|---|---|---|
| `textChanged` | 更新草稿和字符/容量提示，标记旧结果 | 自动编码、追加日志 |
| 参数改变 | 更新草稿、容量和控件启用状态 | 自动生成或覆盖上次结果 |
| Generate点击 | 唯一ID、冻结请求、调用服务、呈现结果 | 再次绑定信号、重复追加记录 |
| 页签切换 | 展示已有数据或按需刷新分析 | 创建QRRequest |
| 步骤导航 | 改索引、重绘快照 | 重跑编码或写日志 |
| Save QR/Save step | 导出当前结果/步骤 | 重新编码或记新请求 |
| Refresh analytics | 读取已有CSV并聚合 | 修改历史、生成QR |

### 5.2 界面状态

| 状态 | 展示与按钮 |
|---|---|
| EMPTY | 无结果，保存/步骤禁用 |
| EDITING | 输入草稿；保留旧结果时持续标“上一次提交结果，尚未按当前输入更新” |
| GENERATING | busy；生成及影响本次请求的编辑暂时禁用，防双击和重入 |
| SUCCESS | 当前QR、实际参数与警告，开放保存/真实步骤 |
| FAILURE | 错误与已完成步骤；禁用最终QR保存，清除或明确隔离旧成功图，防止误用 |

至少区分 `draft_request_fields`、`submitted_request`、`last_result`、`current_step_index`、`busy` 和 `analytics_filter`。草稿不修改已提交请求；展示和保存必须指向同一份真实结果。

生成顺序：检查busy → 复制控件字段并建立唯一request_id/时间 → 标busy并禁用有关编辑 → 调用共享服务 → 用QRResult更新页面与步骤索引 → 在保证恢复的收尾路径中解除busy。

服务负责生成和使用日志，GUI不再额外调用一次UsageLogger。日志状态、导出状态独立呈现：编码成功但日志失败时保留QR，并持续提示记录未保存；不能误报“全部成功”或改成编码失败。

## 6. matplotlib与Qt集成

采用matplotlib官方Qt嵌入方式：`matplotlib.backends.backend_qtagg`的Qt画布与 `matplotlib.figure.Figure`。在加载Qt画布之前明确选用PyQt5绑定，避免环境中其他Qt绑定被自动选中。

| 层 | 责任 |
|---|---|
| 核心 | 提供不含quiet zone的0/1主体矩阵，不导入Qt |
| renderer | 添加quiet zone、绘制/导出，不创建QApplication |
| Qt页面 | 持有FigureCanvas，安排重绘及控件生命周期 |
| 保存 | 使用当前结果/步骤对应图像，不重新生成 |

保留 `render_qr(matrix, render_options) -> Figure`。GUI可补充 `draw_matrix(axes, matrix, render_options) -> None`，在已有Axes上更新，由GUI请求画布重绘。二维码、步骤和分析各自持有画布，不把同一Qt控件放进两个容器，也不随步骤切换累积隐藏画布。

二维码显示约束：

- 白背景、黑模块、等比例、最近邻显示，关闭坐标轴/网格/插值平滑。
- 至少4模块白色quiet zone由绘图显式保证，不依赖窗口留白或自动裁边。
- 优先整数像素模块尺寸；窗口缩放后实际扫码验证。
- QR画布默认不提供平移/裁切工具栏，避免quiet zone被裁掉；统计图按需要另设工具栏。
- 中间图标明“中间步骤，可能不可扫描”，只有最终图提示用于扫码。
- 导入核心、运行CLI或单元测试时不能因为GUI后端被导入而弹窗。

## 7. 其余三个页签

### 7.1 Generation Steps

内容：步骤列表/序号、标题、说明、载荷视图、Previous/Next、Save step。

| 载荷 | 展示 |
|---|---|
| 说明文本 | 只读纯文本 |
| 位串/码字 | 等宽只读文本区或表格，可滚动 |
| 矩阵/掩码/中间图 | matplotlib Qt画布 |
| 评分 | 只读评分表 |
| 失败终点 | 错误与最后完成步骤，不补造后续过程 |

首尾禁用越界导航，显示“第n步/共m步”。保存选定可视化步骤，文件名包含request_id与step_id；文本载荷可另导出文本，不冒充QR图。独立StepVisualizer处理步骤状态，Qt页面负责控件；快照必须独立，最终掩码不能改掉早期矩阵。

### 7.2 Usage Analytics

内容：日期/状态筛选、Refresh、总数/成功/失败/成功率、ECC频数图、成功失败趋势图及少量只读明细。

数据来自 `UsageLogger.summarise(filters)`，以pandas聚合、matplotlib展示。清楚显示筛选、时区和分母；解析前失败的实际ECC为空，单列“未解析”或说明图的排除范围。文件不存在显示暂无记录，字段损坏提示问题且不覆盖原件。

明细默认显示ID、时间、参数和状态，原文按需要查看。日志本身仍须包含作业要求的文本字段；生成前告知本机记录行为、位置、用途、清除办法，使用非敏感演示输入。

若提供Clear history，须与Clear input明显区分，并明确影响、二次确认。刷新统计不算新请求，不增加日志条数。

### 7.3 Information

至少解释：文本→字节→位流→纠错→矩阵→图像的信息模型；字符集和容量限制；基础/扩展及自动选择规则；输入不静默改写；异常反馈；原文日志的记录与清除；钓鱼风险；中间图与最终图的区别。

静态可信说明可用QTextBrowser展示。用户输入用纯文本接口显示，不直接拼为HTML或自动变成可执行内容；本应用不自动访问输入URL，也不声称已验证网址安全。

## 8. 保存与错误反馈

`QFileDialog.getSaveFileName`返回路径和过滤器。取消时路径为空，直接结束；默认PNG，后缀与实际格式一致，保留已有文件覆盖确认。

| 操作/情况 | 规则 |
|---|---|
| 最终QR默认文件名 | `qr_<request_id>.png`，不使用原文作路径 |
| 步骤默认文件名 | `step_<request_id>_<step_id>.png` |
| 默认目录 | 可用 `outputs/qr_images/` / `outputs/steps/`，允许用户选择有权限的位置 |
| 编码不支持/超限 | 清楚解释字符或所选容量，保留输入，不静默改写 |
| 保存取消 | 保留结果，正常结束，不算生成失败 |
| 写入失败 | 保留QR，说明问题，可重选位置；不新增生成记录 |
| 日志失败 | 保留生成状态，持续显示独立警告 |
| 非预期异常 | 用户可理解的安全提示，详细诊断留本地，不铺陈堆栈和内部路径 |

输入实时提示和预计容量不能代替服务最终校验。重要警告使用持续文本，不只在状态栏闪过；常见输入错误不反复弹出阻断对话框。

## 9. 模块落地

```text
main_gui.py                         # 薄入口，启动桌面应用
qr_app/presentation/
  gui.py                           # QApplication、组装、GUIController与事件协调
  main_window.py                   # 主窗口、菜单、页签、状态栏
  generation_panel.py              # 输入、参数、结果、评分与按钮
  steps_panel.py                   # 步骤显示、导航、导出
  analytics_panel.py               # 筛选、概要、图表
  information.py                   # Information页与说明
  renderer.py                      # Qt无关的matplotlib绘图
```

这是拟建结构。Stage2先做主窗口、生成页、Information和渲染，扩展接入时再实现对应页面，不要求一开始创建全部空文件。

GUIController位于gui.py或后续独立模块，负责读控件、构造请求、调用服务、持有结果、更新页面和处理保存。不得实现编码/RS/评分算法，不把QWidget/QFileDialog/QPixmap传入核心、StepVisualizer或UsageLogger。

V1/V2规模较小，首版先同步计算并用busy保护，实测V2+八掩码+完整轨迹后再判断线程需求。出现卡顿才评估QThread：计算在工作线程，Qt控件和画布在主线程更新，通过信号传普通数据；不能随意处理事件导致重入。默认只保留当前结果，不在内存无限累计所有轨迹；关闭时释放画布与引用。

## 10. 环境核查和兼容性

### 10.1 本轮只读观察

以下为2026-11-10当前执行命令的解释器，**不是教学机房运行结果**：

| 项目 | 观察 |
|---|---|
| Python | 3.13.4，与要求3.13.9不同 |
| PyQt5 / PyQt5-Qt5 / PyQt5-sip | 当前解释器未安装 |
| matplotlib | 3.10.7 |
| numpy / pandas | 2.2.6 / 2.3.0 |
| reedsolo | 当前解释器未安装 |

本次没有安装依赖、创建GUI程序或执行扫码测试。

> 2026-11-11 核心环境更新：Python 已升级为 3.13.9，reedsolo 1.7.0 已安装并通过纠错测试；
> 上表保留 11 月 10 日历史观察。PyQt5、Qt 画布与教学机房验证仍未完成，见[RS 验证说明](../docs/error_correction.md)。

> 2026-11-12 界面环境更新：项目内`.venv`已安装PyQt5 5.15.11、Qt5.15.2与matplotlib3.10.7，
> 离屏及Windows原生隐藏窗口的画布、事件循环和自动关闭验证通过。中文目录的Qt插件路径问题已处理。
> 实际环境及记录见[Stage2界面环境](../docs/stage2_gui_environment.md)。下方“候选/尚未执行”保留原规划历史；
> 正式GUI、原生文件对话框人工操作、手机扫码和教学机房仍待后续验收。
>
> 同日渲染更新：matplotlib黑白二维码、至少4模块白边和等比例显示已实现；13项专项测试、5个本机解码样例
> 及Qt离屏预览通过，见[渲染说明](../docs/renderer.md)。
>
> 同日保存更新：独立PNG保存器、预览Save PNG按钮及终端导出已实现，31项相关测试、离屏Qt实际按钮保存
> 及五张导出图本机解码通过，见[PNG保存说明](../docs/png_export.md)。当前预览仍无文本输入框及Information。

### 10.2 候选版本

本轮PyPI元数据显示PyQt5 **5.15.11**，`Requires-Python >=3.8`，提供 `cp38-abi3-win_amd64`及win32 wheel；依赖为 `PyQt5-sip >=12.15,<13`、`PyQt5-Qt5 >=5.15.2,<5.16.0`。

这些是相应Windows架构与CPython稳定ABI的候选包信息，**不代表已在Python 3.13.9与机房验证成功**。使用标准64位CPython 3.13.9及实际机房环境验收后，再锁定整套依赖。如果架构/解释器类型不同，重新核查，不能自动回退为源码编译或改成PyQt6。

PyQt5官方参考页标题仍标v5.15.7，当前包的版本/依赖依据本轮PyPI元数据；不将旧手册的最低Python版本描述当作当前包元数据。

### 10.3 后续验证，尚未执行

1. 核对目标Python确为3.13.9，确认解释器与pip属于同一环境。
2. 优先使用课程环境已有PyQt5；需额外安装时按课程环境与权限规则处理。
3. 如使用pip，可在目标环境评估 `python -m pip install --only-binary=:all: PyQt5==5.15.11`。这是未来命令示例，本次未执行。
4. 记录PyQt5、Qt运行时、sip、matplotlib及核心依赖实际版本，验证QtWidgets、平台插件和Qt画布加载。
5. 验证文件对话框、PNG保存、文本显示、DPI、真实扫码，再记录教学机房配置。
6. 验证通过后写依赖与启动说明。插件冲突先定位当前解释器和Qt绑定，不盲改全局系统环境。

不预先增加PyInstaller、PyQtWebEngine、主题库等非必要依赖。

## 11. 测试与验收

| 自动验证场景 | 期望 |
|---|---|
| 单次Generate/重复点击 | 服务一次、唯一ID一份、日志一条；忙时不重复启动 |
| 改草稿、切页、翻步骤 | 不重新编码，不新增记录，旧结果来源明确 |
| 新请求失败 | 禁用最终图保存，保留真实已完成步骤，不误用旧成功图 |
| 日志失败 | 生成成功状态保留，警告可见 |
| 保存取消/失败 | 不新增请求、不撤销已有QR，可继续操作 |
| 快照与导航 | 首尾不越界，前一步不随后续计算改变 |

优先用unittest和注入的服务/保存器验证独立控制逻辑、状态、调用次数与故障，减少对真实对话框的依赖。Qt控件自动化若需新库，先核查允许范围；无头CI不能替代真实桌面、DPI和手机扫码验收。

人工检查清单：

- [ ] Python 3.13.9中Qt窗口与matplotlib画布可用。
- [ ] 基础模式锁定V1/L/0，成功/失败与CLI一致。
- [ ] 四个页面随真实功能接入，操作不产生重复请求。
- [ ] 窗口预览和导出PNG均能手机扫码，结果与输入一致。
- [ ] 字符/容量/IO错误反馈准确，不丢失输入或误用旧图。
- [ ] 步骤导航、导出、评分表与分析来自真实结果。
- [ ] 小窗口与Windows缩放下关键内容可达，quiet zone完整。
- [ ] Information说明、原文日志行为、清空输入/清除历史含义准确。
- [ ] 关闭重开不假装恢复未持久化的QR，CSV按规则保留。

## 12. 实施顺序与未决事项

建议顺序：目标环境验证 → 主窗口/生成/Information → 接入已完成的基础服务 → 显示/保存/错误与扫码验收 → 接入四项扩展 → 联合演示与最终文档。

已确定：PyQt5、本地桌面形态、保留CLI、共用服务、四页签方向。不新增网站服务，不分配真实人员。

待实测/确认：Python 3.13.9和机房具体依赖；课堂适用的代码布局/Designer方式；最终界面语言；最重场景响应时间、DPI和扫码表现。四人真实分工与能力匹配继续搁置。

## 13. 来源与验证范围

| 来源 | 使用方式 |
|---|---|
| 用户本轮补充“PyQt5” | 课堂工具依据，决定框架方向 |
| [CS2PP_CW2.pdf，第4、11页](../作业原始材料/CS2PP_CW2.pdf) | GUI/网站、禁止Tkinter、matplotlib、保存、Information、机房和Python要求 |
| [PyQt5 Introduction](https://www.riverbankcomputing.com/static/Docs/PyQt5/introduction.html) | PyQt5/Qt5、QtWidgets、Designer；本轮已读取 |
| [PyQt5 Installation](https://www.riverbankcomputing.com/static/Docs/PyQt5/installation.html) | wheel安装、平台与源码构建；本轮已读取 |
| [PyQt5 PyPI元数据](https://pypi.org/pypi/PyQt5/json) | 本轮版本、Python约束、wheel与依赖；不代表运行验收 |
| [matplotlib：Embed in Qt](https://matplotlib.org/stable/gallery/user_interfaces/embedding_in_qt_sgskip.html) | Qt画布、Figure和绑定选择；本轮已读取 |

外部材料用于学习和规划，实施时依实际版本复核。所有窗口、测试、截图、扫码和评分证据仍需团队据真实实现完成；本文件不应直接充当最终评分成果。
