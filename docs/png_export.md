# PNG 保存功能

日期：2026-11-12。状态：保存接口、预览窗口 Save PNG 按钮及终端保存参数已实现。

正式[输入与生成页面](gui_generation.md)也已接入同一保存功能，可在`main_gui.py`中直接输入、生成、保存。

## 1. 使用方式

在项目根目录使用 `.venv` 的 Python。二维码内容仍按基础 V1/L/Mask0、严格 ISO-8859-1 和 17 字节上限处理。

### 1.1 在窗口中保存

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 main_gui.py
```

1. 在窗口中输入文字并点击 **Generate**，成功后点击 **Save PNG**。
2. 选择保存位置，输入文件名。
3. 没有扩展名时补上 `.png`；其他扩展名会提示错误。
4. 目标文件已存在时，确认后才覆盖，默认选项为不覆盖。
5. 保存完成会提示成功。取消或保存失败后，二维码仍可查看，并可再次保存。

窗口保存的是当前二维码 Figure，不包含窗口上的文字标签或按钮。窗口缩放后，导出尺寸也可能变化，二维码仍保持正方形比例和完整白边；图像外围可能包含额外白色区域。

### 1.2 在终端直接保存

```powershell
# 文件夹只需准备一次；保存函数本身不会创建父目录。
New-Item -ItemType Directory -Force outputs

# 只保存，不打开Qt窗口；默认V1为290×290像素。
& '.\.venv\Scripts\python.exe' -X utf8 scripts/preview_qr.py --text "Hello QR" --png-out outputs/hello.png --no-preview

# 明确允许覆盖。
& '.\.venv\Scripts\python.exe' -X utf8 scripts/preview_qr.py --text "Hello QR" --png-out outputs/hello.png --no-preview --overwrite

# 先保存，再打开可继续操作的预览窗口。
& '.\.venv\Scripts\python.exe' -X utf8 scripts/preview_qr.py --text "known" --png-out outputs/known.png
```

`--no-preview` 不加载 PyQt5。它需要 matplotlib 和基础编码依赖；当前完整 `.venv` 已包含这些依赖。`outputs/` 已被项目忽略，不会自动提交用户生成的图片。

### 1.3 参数与退出码

| 参数 | 含义 |
|---|---|
| `--png-out PATH` | 显式保存 PNG；父目录必须存在，文件名须以 .png 结尾，大小写均可 |
| `--overwrite` | 允许替换 --png-out 指定的文件；必须同时提供 --png-out |
| `--no-preview` | 保存后退出，不创建 Qt 应用；必须提供 --png-out |
| `--quiet-zone N` | 白边模块数，至少 4 |
| `--module-pixels N` | Figure 初始每模块像素数，必须为正整数 |

`--offscreen` 和 `--no-preview` 互斥：前者仍创建隐藏 Qt 窗口，后者完全不启动 Qt。

| 退出码 | 含义 |
|---|---|
| 0 | 显式保存成功，或正常关闭预览窗口 |
| 1 | 生成失败，没有最终二维码可保存 |
| 2 | 参数错误 |
| 3 | --png-out 指定的保存操作失败；生成本身仍成功 |

若同时请求预览和命令行保存，保存失败会报告 `ARTIFACT_SAVE_FAILED`，窗口仍能显示生成结果，关闭后返回 3。窗口内按钮的取消或失败只显示反馈，允许重试，不修改生成结果。

## 2. 保存接口

文件：[image_export.py](../qr_app/presentation/image_export.py)。

```python
from pathlib import Path
from qr_app.presentation.image_export import save_figure

artifact = save_figure(figure, Path("outputs/known.png"))
print(artifact.path)        # 实际完整路径，返回前文件已经写完
print(artifact.media_type)  # image/png
```

函数签名：

```python
save_figure(figure, target_path, *, overwrite=False) -> SavedArtifact
```

`SavedArtifact` 是不可变数据类，包含 `path: Path` 和 `media_type: str`。为方便终端和窗口调用，目标路径兼容 str 与 Path。Figure 或参数类型错误抛 TypeError；文件路径、权限、编码或发布失败使用统一的 ArtifactSaveError。

接口不生成二维码、不追加请求或日志、不创建 Qt 应用，也不关闭调用方的 Figure。它通过临时 Agg 后端完成导出并恢复原画布，Qt 窗口可以继续显示和重绘。

## 3. 完整写入与覆盖保护

保存分为两个阶段：

1. 在目标文件同目录创建本次独有的临时文件，将完整 PNG 写完并关闭文件句柄。
2. 再将完整临时文件发布到目标位置。

默认禁止覆盖时，Windows 使用不会替换现有目标的 rename；POSIX 使用排他创建目标链接的方式。即使其他进程在编码过程中创建了同名文件，也会明确失败并保留对方文件。

允许覆盖时使用同目录的原子替换。若编码或替换失败，已有目标不变；首次保存失败不会留下不完整的目标 PNG。临时文件在正常成功或可清理的失败路径中删除。

文件名扩展名和实际格式一致，只输出 PNG。保存显式保留完整 Figure 边界、当前 DPI、白色背景和不透明像素，不受 matplotlib 默认的 tight 裁边、透明背景或其他保存 DPI 设置影响。

## 4. 预览窗口接入

[png_dialog.py](../qr_app/presentation/png_dialog.py) 负责文件选择、一次覆盖确认和成功/失败提示；[preview_qr.py](../scripts/preview_qr.py) 将其接到 Save PNG 按钮。

正式[GenerationPanel](../qr_app/presentation/generation_panel.py)也调用此对话框；输入修改后保存禁用，重新提交成功才保存当前结果。

取消文件对话框不会调用保存函数。保存操作复用当前 Figure，不再次调用 QRService。覆盖确认的默认选择为 No；文件在选择后才被其他进程创建时，保存器仍会保护新文件。

## 5. 本次验证

[png_export_python3139_20261112.json](validation/png_export_python3139_20261112.json) 保留源码哈希、已完成测试摘要、实际导出图、Qt 操作摘要和离线解码输出。测试与 Qt 操作字段明确标注为已执行命令的摘要。

GitHub上传前另有[发布前复验记录](validation/png_export_pre_publish_python3139_20261112.json)，保留31项测试的真实输出、Qt按钮操作输出、五张新导出图的解码结果及编译检查，全部通过；公开PNG样例与新导出图的哈希一致。
该记录同时提供工作文件原始哈希与按仓库LF换行计算的`repository_source_sha256`，供提交后核对；原有记录保留。

### 5.1 单元与入口测试

实际执行 **31 项**，全部通过、没有跳过：

- PNG 保存与命令入口 13 项。
- 保存对话框 5 项。
- 原渲染器回归 13 项。

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest tests.test_image_export tests.test_png_dialog tests.test_renderer -v
```

重点包括真实 PNG 逐像素读回、中文路径、.PNG 大写扩展名、白边完整、覆盖保护、编码中断、替换失败、并发同名文件保护、缺失目录、取消及拒绝覆盖、错误反馈，以及不启动 Qt 的终端保存。保存失败不会把 QR 生成成功改成失败，也不会再次生成。

### 5.2 Qt 画布与按钮

在真实离屏 Qt 事件循环中触发 Save PNG 按钮，使用预设文件选择及消息响应完成保存：

- 按钮确实触发，服务生成 1 次、文件保存 1 次。
- 导出前后的画布对象相同。
- 文件像素与保存前画布完全一致。
- 保存后仍可重绘，窗口正常关闭。

这项验证使用模拟文件选择响应，未代替原生文件对话框的人工操作检查。

### 5.3 完整图像与解码

通过实际 save_figure 导出的 known、We've succeeded!、Latin-1 混合文本、17 个 A 和一个空格共五张 PNG，均为 290×290、不透明黑白图，本机 OpenCV 4.12.0 均解码为原输入。known 的像素与此前独立验证的渲染图一致。

[known 保存样例](validation/png_saved_known_20261112.png) 由本次保存接口实际生成。OpenCV 仍只用于本机离线验证，没有添加运行依赖。

## 6. 后续工作

本次没有重跑Stage1的历史全量测试，也没有进行手机扫码、教学机房或原生文件对话框的人工验收。正式文本输入/生成页面现已实现，接下来补充Information并完成人工验收。
