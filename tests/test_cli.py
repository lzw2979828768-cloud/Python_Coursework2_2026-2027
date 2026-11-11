"""Exercise input boundaries and real service results, without optional QR tools."""

from dataclasses import replace
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from qr_app.errors import ArtifactSaveError, QRContractError
from qr_app.models import LogState, LogStatus, PayloadType, PenaltyBreakdown, QRRequest, TraceStep
from qr_app.presentation.cli import main
from qr_app.presentation.trace_export import matrix_text, render_report, save_report
from qr_app.service import QRService


ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def invoke(self, args, text="", service=None):
        output, errors = io.StringIO(), io.StringIO()
        service = Mock(wraps=QRService()) if service is None else service
        code = main(args, service=service, input_stream=io.StringIO(text),
                    output_stream=output, error_stream=errors)
        return code, output.getvalue(), errors.getvalue(), service

    def test_help_and_bad_arguments_never_generate(self):
        for args, expected in [(["--help"], 0), (["--unknown"], 2),
                (["--text", "a", "--stdin"], 2), (["--text"], 2),
                (["--overwrite"], 2), (["--version", "2"], 2), (["--tex", "a"], 2)]:
            with self.subTest(args=args):
                code, output, errors, service = self.invoke(args)
                self.assertEqual(code, expected)
                self.assertIn("usage:", output if expected == 0 else errors)
                service.generate_qr.assert_not_called()

    def test_interactive_only_removes_submission_newline(self):
        for line, expected in [("  known  \r\n", "  known  "), ("known\n", "known"),
                ("a\t \n", "a\t "), ("known", "known"), ("a\r\r\n", "a\r")]:
            with self.subTest(line=line):
                code, _, errors, service = self.invoke([], "1\n" + line)
                self.assertEqual((code, errors), (0, ""))
                service.generate_qr.assert_called_once()
                self.assertEqual(service.generate_qr.call_args.args[0].text, expected)

    def test_interactive_eof_does_not_submit(self):
        code, _, errors, service = self.invoke([])
        self.assertEqual(code, 2)
        self.assertIn("EOF", errors)
        service.generate_qr.assert_not_called()

    def test_empty_submissions_are_real_failed_requests(self):
        for args, text in [([], "1\n\n"), ([], "2\n:end\n"), (["--text", ""], ""), (["--stdin"], "")]:
            with self.subTest(args=args):
                code, output, errors, service = self.invoke(args, text)
                self.assertEqual(code, 1)
                self.assertIn("EMPTY_INPUT", errors)
                self.assertIn("Actual plan: null", output)
                self.assertIn("Final matrix: null", output)
                service.generate_qr.assert_called_once()
                self.assertEqual(service.generate_qr.call_args.args[0].text, "")

    def test_menu_exit_does_not_generate_or_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cancelled.txt"
            code, output, errors, service = self.invoke(["--steps-out", str(path)], "0\n")
            self.assertEqual((code, errors), (0, ""))
            self.assertIn("已退出", output)
            self.assertNotIn("Request ID:", output)
            service.generate_qr.assert_not_called()
            self.assertFalse(path.exists())

    def test_invalid_menu_choices_retry_without_accepting_requests(self):
        code, output, errors, service = self.invoke([], "\nwrong\n3\n 1 \nknown\n")
        self.assertEqual(code, 0)
        self.assertEqual(errors.count("无效选项"), 3)
        self.assertIn("多行输入", output)
        service.generate_qr.assert_called_once()
        self.assertEqual(service.generate_qr.call_args.args[0].text, "known")

    def test_multiline_preserves_spaces_controls_and_line_endings(self):
        cases = [("  a \nb\t\n:end\n", "  a \nb\t"),
                 ("ñ\r\nb\r\n:end\r\n", "ñ\r\nb"),
                 ("\na\n\n:end\n", "\na\n"),
                 ("a\n\n\n:end\n", "a\n\n"),
                 ("\x00\t\n:end", "\x00\t"),
                 ("\n:end\n", "")]
        for entered, expected in cases:
            with self.subTest(entered=entered):
                code, _, _, service = self.invoke([], "2\n" + entered)
                self.assertEqual(code, 0 if expected else 1)
                service.generate_qr.assert_called_once()
                self.assertEqual(service.generate_qr.call_args.args[0].text, expected)

    def test_only_exact_standalone_terminator_ends_multiline(self):
        text = ":end \n :end\nx:end"
        code, _, errors, service = self.invoke([], "2\n" + text + "\n:end\n")
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(service.generate_qr.call_args.args[0].text, text)

    def test_incomplete_menu_input_never_generates(self):
        for text in ("wrong\n", "1\n", "2\n", "2\nknown\n", "2\nknown"):
            with self.subTest(text=text):
                code, _, errors, service = self.invoke([], text)
                self.assertEqual(code, 2)
                self.assertIn("EOF", errors)
                service.generate_qr.assert_not_called()

    def test_multiline_enforces_the_same_character_and_byte_limits(self):
        cases = [("12345678\n12345678", 0, None),
                 ("12345678\n123456789", 1, "CAPACITY_EXCEEDED"),
                 ("a\nα", 1, "UNSUPPORTED_CHARACTER")]
        for text, expected, error in cases:
            with self.subTest(text=text):
                code, output, errors, service = self.invoke([], "2\n" + text + "\n:end\n")
                self.assertEqual(code, expected)
                self.assertEqual(service.generate_qr.call_args.args[0].text, text)
                service.generate_qr.assert_called_once()
                if error:
                    self.assertIn(error, errors)
                else:
                    self.assertIn("Byte length: 17", output)

    def test_multiline_display_export_and_logging_use_one_request(self):
        logger = Mock()
        logger.append_attempt.return_value = LogStatus(LogState.WRITTEN)
        service = Mock(wraps=QRService(usage_logger=logger))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "multiline.txt"
            code, _, errors, _ = self.invoke(["--show-steps", "--steps-out", str(path)],
                "2\na\nb\n:end\n", service=service)
            self.assertEqual((code, errors), (0, ""))
            service.generate_qr.assert_called_once()
            logger.append_attempt.assert_called_once()
            saved = path.read_text(encoding="utf-8")
            self.assertIn('Input (JSON): "a\\nb"', saved)
            self.assertNotIn(":end", saved)

    def test_text_argument_wins_over_unread_stdin(self):
        source = Mock()
        code = main(["--text", "known"], input_stream=source,
                    output_stream=io.StringIO(), error_stream=io.StringIO())
        self.assertEqual(code, 0)
        source.read.assert_not_called()
        source.readline.assert_not_called()

    def test_stdin_preserves_controls_and_all_lines(self):
        text = ' a\r\nb\n\t\x00 "ñ"\n'
        code, output, errors, service = self.invoke(["--stdin"], text)
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(service.generate_qr.call_args.args[0].text, text)
        displayed = next(line for line in output.splitlines() if line.startswith("Input (JSON): "))
        self.assertEqual(json.loads(displayed.removeprefix("Input (JSON): ")), text)

    def test_five_coursework_cases(self):
        cases = [("known", 0, None, 5, 25), ("We've succeeded!", 0, None, 16, 25),
                 ("~¡256_-_aA&ñ", 0, None, 12, 25),
                 ("From α to ɷ...", 1, "UNSUPPORTED_CHARACTER", None, 0),
                 ("Sugarplum_Fairy_Nightmare", 1, "CAPACITY_EXCEEDED", 25, 1)]
        for text, expected, error, length, steps in cases:
            with self.subTest(text=text):
                code, output, errors, service = self.invoke(["--text", text, "--show-steps"])
                self.assertEqual(code, expected)
                self.assertIn(f"Byte length: {json.dumps(length)}", output)
                self.assertIn(f"Captured steps: {steps}", output)
                service.generate_qr.assert_called_once()
                if error:
                    self.assertIn(error, errors)
                    self.assertIn("Actual mask: null", output)
                    self.assertNotIn("[02]", output)
                else:
                    self.assertEqual(errors, "")
                    self.assertIn("Actual mask: 0", output)

    def test_whitespace_is_not_trimmed(self):
        code, output, _, service = self.invoke(["--text", " \t\r\n"])
        self.assertEqual(code, 0)
        self.assertIn("Warning:", output)
        self.assertEqual(service.generate_qr.call_args.args[0].text, " \t\r\n")

    def test_default_output_matches_real_final_matrix(self):
        result = QRService().generate_qr(QRRequest("known"))
        code, output, errors, _ = self.invoke(["--text", "known"])
        self.assertEqual((code, errors), (0, ""))
        self.assertTrue(output.endswith(matrix_text(result.matrix) + "\n"))
        self.assertEqual(len(output.splitlines()[-21:]), 21)
        self.assertNotIn("Captured steps:", output)

    def test_controls_are_escaped_in_terminal(self):
        _, output, _, _ = self.invoke(["--text", "\x1b[31m\x85"])
        self.assertNotIn("\x1b", output)
        self.assertNotIn("\x85", output)
        self.assertIn(r"\u001b[31m\u0085", output)

    def test_export_and_display_use_one_request_and_one_logging_attempt(self):
        logger = Mock()
        logger.append_attempt.return_value = LogStatus(LogState.WRITTEN)
        service = Mock(wraps=QRService(usage_logger=logger))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "步骤.txt"
            code, output, errors, _ = self.invoke(
                ["--text", "known", "--show-steps", "--steps-out", str(path)], service=service)
            self.assertEqual((code, errors), (0, ""))
            service.generate_qr.assert_called_once()
            logger.append_attempt.assert_called_once()
            saved = path.read_text(encoding="utf-8")
            self.assertTrue(output.startswith(saved))
            self.assertEqual(saved.count("Request ID:"), 1)
            self.assertIn(service.generate_qr.call_args.args[0].request_id, saved)

    def test_export_failure_is_independent_and_does_not_regenerate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exists.txt"
            path.write_text("original", encoding="utf-8")
            code, output, errors, service = self.invoke(["--text", "known", "--steps-out", str(path)])
            self.assertEqual(code, 3)
            self.assertIn("Generation: SUCCESS", output)
            self.assertIn("ARTIFACT_SAVE_FAILED", errors)
            self.assertEqual(path.read_text(), "original")
            service.generate_qr.assert_called_once()

    def test_failed_generation_can_export_its_partial_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failure.txt"
            code, _, errors, _ = self.invoke(["--text", "Sugarplum_Fairy_Nightmare",
                                               "--steps-out", str(path)])
            self.assertEqual(code, 1)
            self.assertIn("CAPACITY_EXCEEDED", errors)
            self.assertIn("Captured steps: 1", path.read_text(encoding="utf-8"))

    def test_explicit_overwrite_replaces_report_without_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "steps.txt"
            path.write_bytes(b"old")
            code, _, errors, service = self.invoke(["--text", "known", "--steps-out", str(path),
                                                    "--overwrite"])
            self.assertEqual((code, errors), (0, ""))
            self.assertIn("Captured steps: 25", path.read_text(encoding="utf-8"))
            service.generate_qr.assert_called_once()

    def test_generation_and_export_failures_both_remain_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing" / "steps.txt"
            code, output, errors, service = self.invoke(["--text", "", "--steps-out", str(path)])
            self.assertEqual(code, 3)
            self.assertIn("Generation: FAILED", output)
            self.assertIn("EMPTY_INPUT", errors)
            self.assertIn("ARTIFACT_SAVE_FAILED", errors)
            service.generate_qr.assert_called_once()

    def test_failed_logging_does_not_turn_success_into_generation_failure(self):
        logger = Mock()
        logger.append_attempt.side_effect = OSError("secret-path")
        code, output, errors, _ = self.invoke(["--text", "known"], service=QRService(usage_logger=logger))
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("Generation: SUCCESS", output)
        self.assertIn("Logging: failed", output)
        self.assertNotIn("secret-path", output)

    def test_service_exceptions_are_safe(self):
        for exception, marker in [(QRContractError("private"), "INVALID_REQUEST"),
                                  (RuntimeError("private"), "INTERNAL_GENERATION_ERROR")]:
            with self.subTest(exception=exception):
                service = Mock()
                service.generate_qr.side_effect = exception
                code, output, errors, _ = self.invoke(["--text", "known"], service=service)
                self.assertEqual(code, 4)
                self.assertIn(marker, errors)
                self.assertNotIn("private", output + errors)
                self.assertNotIn("Traceback", errors)
                service.generate_qr.assert_called_once()

    def test_internal_failure_result_uses_exit_four(self):
        service = Mock()
        service.generate_qr.return_value = QRService(version_selector=None).generate_qr(QRRequest("known"))
        service.generate_qr.return_value = replace(service.generate_qr.return_value,
            generation_success=False, matrix=None, error_code="INTERNAL_GENERATION_ERROR",
            error_message="内部错误")
        code, _, errors, _ = self.invoke(["--text", "known"], service=service)
        self.assertEqual(code, 4)
        self.assertIn("INTERNAL_GENERATION_ERROR", errors)

    def test_interrupt_before_submission_does_not_generate(self):
        source, service = Mock(), Mock()
        source.readline.side_effect = KeyboardInterrupt()
        errors = io.StringIO()
        code = main([], service=service, input_stream=source,
                    output_stream=io.StringIO(), error_stream=errors)
        self.assertEqual(code, 130)
        service.generate_qr.assert_not_called()

    def test_injected_streams_remain_open(self):
        streams = [io.StringIO() for _ in range(3)]
        main(["--text", "known"], input_stream=streams[0],
             output_stream=streams[1], error_stream=streams[2])
        self.assertTrue(all(not stream.closed for stream in streams))

    def test_input_io_failure_does_not_submit_or_expose_exception(self):
        source, service = Mock(), Mock()
        source.read.side_effect = OSError("private-path")
        errors = io.StringIO()
        code = main(["--stdin"], service=service, input_stream=source,
                    output_stream=io.StringIO(), error_stream=errors)
        self.assertEqual(code, 3)
        self.assertIn("CLI_IO_ERROR", errors.getvalue())
        self.assertNotIn("private-path", errors.getvalue())
        service.generate_qr.assert_not_called()


class TraceExportTests(unittest.TestCase):
    def test_report_contains_every_real_step_and_snapshot(self):
        request = QRRequest("known")
        result = QRService().generate_qr(request)
        report = render_report(request, result)
        self.assertEqual(len(result.trace_steps), 25)
        for index, step in enumerate(result.trace_steps, 1):
            self.assertEqual(report.count(f"[{index:02d}] {step.step_id}\n"), 1)
            if isinstance(step.payload, np.ndarray):
                self.assertIn(matrix_text(step.payload), report)
            elif isinstance(step.payload, bytes):
                self.assertIn(step.payload.hex(" ").upper(), report)
            elif step.payload_type == PayloadType.BITS:
                self.assertIn("".join(str(bit) for bit in step.payload), report)
        self.assertIn("dtype=bool, shape=(21, 21)", report)
        self.assertIn("40 56 B6 E6 F7 76 E0 EC 11 EC 11 EC 11 EC 11 EC 11 EC 11", report)
        self.assertIn("111011111000100", report)
        self.assertIn("Python: CPython", report)
        self.assertIn("Logging status:", report)
        self.assertIn("Penalty scores: {}", report)

    def test_disabled_capture_exports_no_invented_steps(self):
        request = QRRequest("known", capture_steps=False)
        report = render_report(request, QRService().generate_qr(request))
        self.assertIn("Captured steps: 0", report)
        self.assertNotIn("[01]", report)
        self.assertIn('"capture_steps": false', report)

    def test_nested_scores_and_mappings_are_serializable(self):
        request = QRRequest("known")
        step = TraceStep("test.score", "评分", "测试数据", PayloadType.SCORES,
                         {0: PenaltyBreakdown(1, 2, 3, 4, 10)})
        result = replace(QRService().generate_qr(request), trace_steps=(step,))
        report = render_report(request, result)
        self.assertIn('"total": 10', report)
        self.assertIn('"0": {', report)

    def test_exact_input_round_trip_in_report(self):
        for text in ["", 'a,\"\t\r\n\x00ñ', "From α to ɷ...", "NA", "NULL", "00123"]:
            with self.subTest(text=text):
                request = QRRequest(text)
                report = render_report(request, QRService().generate_qr(request))
                line = next(line for line in report.splitlines() if line.startswith("Input (JSON): "))
                self.assertEqual(json.loads(line.removeprefix("Input (JSON): ")), text)

    def test_save_utf8_lf_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "steps.txt"
            self.assertEqual(save_report("字符\nñ\n", path), path.resolve())
            self.assertEqual(path.read_bytes(), "字符\nñ\n".encode("utf-8"))
            with self.assertRaises(ArtifactSaveError):
                save_report("replacement", path)
            self.assertEqual(path.read_bytes(), "字符\nñ\n".encode("utf-8"))
            save_report("replacement\n", path, overwrite=True)
            self.assertEqual(path.read_bytes(), b"replacement\n")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_overwrite_replace_failure_preserves_original_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "steps.txt"
            path.write_bytes(b"original")
            with patch("qr_app.presentation.trace_export.os.replace", side_effect=OSError("private")):
                with self.assertRaises(ArtifactSaveError) as caught:
                    save_report("new", path, overwrite=True)
            self.assertNotIn("private", str(caught.exception))
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_missing_parent_and_directory_target_are_safe_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in (Path(directory), Path(directory) / "missing" / "steps.txt"):
                for overwrite in (False, True):
                    with self.subTest(path=path, overwrite=overwrite):
                        with self.assertRaises(ArtifactSaveError):
                            save_report("data", path, overwrite=overwrite)
            self.assertFalse((Path(directory) / "missing").exists())


class EntryPointTests(unittest.TestCase):
    def run_cli(self, args, data=b""):
        return subprocess.run([sys.executable, str(ROOT / "main_cli.py"), *args],
            input=data, capture_output=True, cwd=ROOT, timeout=30)

    def test_utf8_stdin_preserves_crlf_and_latin1(self):
        text = " ñ\r\na\n"
        process = self.run_cli(["--stdin"], text.encode("utf-8"))
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8"))
        output = process.stdout.decode("utf-8")
        line = next(line for line in output.splitlines() if line.startswith("Input (JSON): "))
        self.assertEqual(json.loads(line.removeprefix("Input (JSON): ")), text)
        self.assertIn("Byte length: 6", output)
        self.assertNotIn(b"\r\n", process.stdout)

    def test_utf8_text_argument_and_business_failure_exit_codes(self):
        for text, code, error in [("~¡256_-_aA&ñ", 0, None), ("From α to ɷ...", 1, "UNSUPPORTED_CHARACTER"),
                                  ("", 1, "EMPTY_INPUT")]:
            with self.subTest(text=text):
                process = self.run_cli(["--text", text])
                self.assertEqual(process.returncode, code)
                if error:
                    self.assertIn(error, process.stderr.decode("utf-8"))

    def test_interactive_menu_multiline_and_single_line_in_real_process(self):
        for data, expected in [(b"1\r\nknown\r\n", "known"),
                               ("2\r\nñ\r\nb\r\n:end\r\n".encode("utf-8"), "ñ\r\nb")]:
            with self.subTest(data=data):
                process = self.run_cli([], data)
                self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8"))
                output = process.stdout.decode("utf-8")
                line = next(line for line in output.splitlines() if line.startswith("Input (JSON): "))
                self.assertEqual(json.loads(line.removeprefix("Input (JSON): ")), expected)

    def test_explicit_stdin_does_not_interpret_menu_or_end_marker(self):
        text = "2\n:end\n0\n"
        process = self.run_cli(["--stdin"], text.encode("utf-8"))
        self.assertEqual(process.returncode, 0)
        output = process.stdout.decode("utf-8")
        self.assertNotIn("请选择输入方式", output)
        line = next(line for line in output.splitlines() if line.startswith("Input (JSON): "))
        self.assertEqual(json.loads(line.removeprefix("Input (JSON): ")), text)

    def test_invalid_utf8_stdin_fails_without_traceback(self):
        process = self.run_cli(["--stdin"], b"\xff")
        self.assertEqual(process.returncode, 3)
        self.assertIn("CLI_IO_ERROR", process.stderr.decode("utf-8"))
        self.assertNotIn(b"Traceback", process.stderr)

    def test_real_entry_point_help(self):
        process = self.run_cli(["--help"])
        self.assertEqual(process.returncode, 0)
        self.assertIn("--steps-out", process.stdout.decode("utf-8"))
        self.assertEqual(process.stderr, b"")

    def test_cli_matrix_matches_independent_reference_fixture(self):
        fixture = json.loads((ROOT / "tests/fixtures/format_mask0_reference_vectors.json")
                             .read_text(encoding="utf-8"))
        expected = next(vector for vector in fixture["known_mask0_matrices"]
                        if vector["version"] == 1 and vector["ecc_level"] == "L")
        process = self.run_cli(["--text", "known"])
        self.assertEqual(process.returncode, 0)
        rows = [line.replace(" ", "") for line in process.stdout.decode("utf-8").splitlines()[-21:]]
        self.assertEqual(rows, expected["final_matrix_rows"])


if __name__ == "__main__":
    unittest.main()
