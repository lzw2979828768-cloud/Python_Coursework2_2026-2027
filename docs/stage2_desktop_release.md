# 新版桌面应用整合说明

用户已选定柔和极简界面作为正式桌面版本，并授权整合到 `main`。本次采用保留历史的普通 merge 提交；功能分支继续保留。

## 版本与范围

| 分支 | 用途 |
|---|---|
| `main` | 正式使用的新版桌面应用与现有CLI |
| `feature/soft-minimal-ui` | 新版界面完整开发历史与整合验证 |
| `feature/stage2-gui-environment` | 旧版顶部页签界面，含英文提示修复，保留供比较 |

新版包含GUI环境准备、matplotlib二维码渲染、PNG保存、文本输入生成页、Information、柔和极简主题、控件细节、按钮回弹及焦点修复。与原 `main` 比较，编码核心、模型、服务和规格资源未修改。

旧版英文提示修复在新版已有对应实现，因此不重复合并旧版分支。旧版界面基准为 `1f14ba73e7c1a01e19f18b78860af0ae1ecab401`，原 `main` 为 `d672374e059ce9f7b08809247a35f03a2add82a7`；普通合并提交保留原主线作为父提交，未重写历史。

## 运行

在项目根目录执行：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 main_gui.py
```

关闭按钮动画可加 `--reduced-motion`。CLI继续使用 `main_cli.py`。

本机旧版工作目录仍在，可另开终端同时比较：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\tmp\ui_previous\main_gui.py'
```

其他电脑需要旧版时，可在该目录不存在的前提下创建：

```powershell
git worktree add --detach tmp/ui_previous feature/stage2-gui-environment
```

## 整合验证与流程边界

- Windows / Python3.13.9 / 项目 `.venv` 完成210项全量测试，无跳过；其中核心与CLI139项，前端相关71项。
- `pip check` 无依赖冲突，应用和脚本编译通过。验证源码基准为 `b208ea0225ecef8598f2eacc8a636f52991784a4`；整合整理仅更新文档及证据。
- 本机Git可通过SSH同步与推送。GitHub API没有现有登录凭据，不能创建PR，因此本次采用用户授权的普通合并与SSH推送，不宣称已完成PR或另一位成员的技术评审。
- 未修改GitHub分支保护、仓库权限或其他平台设置。

[完整验证记录](validation/pre_merge_full_20261112.json) · [210项测试输出](validation/pre_merge_full_tests_20261112.txt) · [新旧界面说明](soft_minimal_ui.md)

## 后续验收

1. 手机扫描窗口二维码和保存的PNG，核对文字、空格与换行。
2. 在不同显示器、窗口尺寸和显示缩放下人工检查。
3. 在教学机房按依赖文件复现运行，完成Stage2其余验收和正式演示材料。

本次通过完整自动化回归不等同于上述人工验收已完成。后续功能从最新 `main` 另开功能分支；需要回退共享主线时使用新的反向提交，保留现有历史。
