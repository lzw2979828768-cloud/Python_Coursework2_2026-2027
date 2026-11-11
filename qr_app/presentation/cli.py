"""Baseline CLI adapter: one accepted input, one service call, optional export."""

import argparse
import sys

from ..errors import ArtifactSaveError, ErrorCode, QRContractError
from ..models import QRRequest, Source
from ..service import QRService
from .trace_export import quoted, render_report, render_summary, save_report


class _Parser(argparse.ArgumentParser):
    def __init__(self, output, error):
        super().__init__(prog="main_cli.py", allow_abbrev=False,
            description="生成 baseline V1/L/Mask0 QR 矩阵，严格使用 ISO-8859-1。",
            epilog="省略 --text/--stdin 时显示输入菜单。多行输入用单独一行 :end 结束。"
                   "不自动保存使用日志；步骤报告包含输入全文和可逆编码数据。")
        self._output, self._error = output, error

    def _print_message(self, message, file=None):
        if message:
            (self._output if file is sys.stdout else self._error).write(message)


def _remove_submission_newline(text: str) -> str:
    if text.endswith("\n"):
        text = text[:-1]
        if text.endswith("\r"):
            text = text[:-1]
    return text


def _interactive_input(input_stream, output_stream, error_stream) -> tuple[str | None, int]:
    """Collect one submission; menu choices and terminators are never QR data."""
    while True:
        output_stream.write("请选择输入方式：\n1. 单行输入\n2. 多行输入\n0. 退出\n请输入选项：\n")
        output_stream.flush()
        line = input_stream.readline()
        if line == "":
            error_stream.write("未收到选项（EOF），没有提交生成请求。\n")
            return None, 2
        choice = _remove_submission_newline(line).strip()
        if choice == "0":
            output_stream.write("已退出。\n")
            return None, 0
        if choice in ("1", "2"):
            break
        error_stream.write("无效选项，请输入 1、2 或 0。\n")

    if choice == "1":
        output_stream.write("请输入文本（单行，回车提交，保留首尾空格）：\n")
        output_stream.flush()
        line = input_stream.readline()
        if line == "":
            error_stream.write("未收到文本（EOF），没有提交生成请求。\n")
            return None, 2
        return _remove_submission_newline(line), 0

    output_stream.write("请输入多行文本，输入单独一行 :end 结束。\n"
                        "保留行间换行和空格；末行提交回车不计入内容，结束前的空行可保留末尾换行。\n")
    output_stream.flush()
    lines = []
    while True:
        line = input_stream.readline()
        if line == "":
            error_stream.write("多行输入尚未收到 :end 便遇到 EOF，没有提交生成请求。\n")
            return None, 2
        if _remove_submission_newline(line) == ":end":
            return _remove_submission_newline("".join(lines)), 0
        lines.append(line)


def _run(argv, service, input_stream, output_stream, error_stream):
    parser = _Parser(output_stream, error_stream)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--text", metavar="TEXT", help="原样编码参数文本，包括空字符串")
    group.add_argument("--stdin", action="store_true", help="完整读取 UTF-8 标准输入，保留末尾换行")
    parser.add_argument("--show-steps", action="store_true", help="在终端显示完整真实步骤")
    parser.add_argument("--steps-out", metavar="PATH", help="导出 UTF-8 步骤报告；父目录必须已存在")
    parser.add_argument("--overwrite", action="store_true", help="允许替换 --steps-out 指定的已有报告")
    try:
        args = parser.parse_args(argv)
        if args.overwrite and args.steps_out is None:
            parser.error("--overwrite 必须与 --steps-out 一起使用")
    except SystemExit as error:
        return int(error.code)

    if args.text is not None:
        text = args.text
    elif args.stdin:
        text = input_stream.read()
    else:
        text, code = _interactive_input(input_stream, output_stream, error_stream)
        if text is None:
            return code

    request = QRRequest(text=text, source=Source.CLI)
    try:
        result = (QRService() if service is None else service).generate_qr(request)
    except QRContractError:
        error_stream.write("INVALID_REQUEST: CLI 请求不符合公共契约，请联系维护者。\n")
        return 4
    except Exception:
        error_stream.write("INTERNAL_GENERATION_ERROR: 生成服务发生内部错误。\n")
        return 4

    code = 0 if result.generation_success else (
        4 if result.error_code == ErrorCode.INTERNAL_GENERATION_ERROR else 1)
    if not result.generation_success:
        error_stream.write(f"{result.error_code}: {result.error_message}\n")
    # Render once and reuse for display/export; never request a new generation.
    report = render_report(request, result) if args.show_steps or args.steps_out is not None else None
    output_stream.write(report if args.show_steps else render_summary(request, result))
    output_stream.flush()
    if args.steps_out is not None:
        try:
            saved = save_report(report, args.steps_out, overwrite=args.overwrite)
        except ArtifactSaveError as error:
            error_stream.write(f"{error.code}: {error.message} QR 生成状态未改变。\n")
            return 3
        output_stream.write(f"步骤报告已保存 (JSON path): {quoted(str(saved))}\n")
    return code


def main(argv=None, *, service=None, input_stream=None, output_stream=None, error_stream=None) -> int:
    """Return an exit code; injected streams remain owned by the caller."""
    input_stream = sys.stdin if input_stream is None else input_stream
    output_stream = sys.stdout if output_stream is None else output_stream
    error_stream = sys.stderr if error_stream is None else error_stream
    try:
        return _run(argv, service, input_stream, output_stream, error_stream)
    except KeyboardInterrupt:
        error_stream.write("操作已中断。\n")
        return 130
    except (OSError, UnicodeError):
        error_stream.write("CLI_IO_ERROR: 输入或输出失败；标准输入应使用 UTF-8。\n")
        return 3
    except Exception:
        error_stream.write("CLI_INTERNAL_ERROR: 结果展示或导出准备失败，请联系维护者。\n")
        return 4


def configure_stdio() -> None:
    """Only the executable entry point reconfigures process streams."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict",
                               newline="" if stream is sys.stdin else "\n")
