"""The sole generation flow shared by CLI and future GUI adapters."""

from dataclasses import replace
from datetime import datetime
import json
import logging
from importlib.resources import files
from typing import Protocol
from uuid import UUID

from .core import byte_encoder, error_correction, fixed_mask, matrix_builder
from .errors import ErrorCode, QRContractError, QRGenerationError
from .models import (
    BlockGroup, ECCLevel, EncodingPlan, LogState, LogStatus, MaskSelection,
    MatrixLayout, Mode, PayloadType, QRRequest, QRResult, Source,
)
from .tracing import TraceCollector

_DIAGNOSTICS = logging.getLogger(__name__)
_DIAGNOSTICS.addHandler(logging.NullHandler())


class VersionSelector(Protocol):
    def __call__(
        self, byte_length: int, version: int | str, ecc_level: str, mode: str,
    ) -> EncodingPlan: ...


class MaskSelector(Protocol):
    def __call__(
        self, layout: MatrixLayout, plan: EncodingPlan, mask_id: int | str,
        *, trace: TraceCollector | None = None,
    ) -> MaskSelection: ...


class UsageLogger(Protocol):
    def append_attempt(self, request: QRRequest, result: QRResult) -> LogStatus: ...


def _validate_request(request: QRRequest) -> None:
    """Bad types/identity are caller errors, not normal generation failures."""
    if not isinstance(request, QRRequest):
        raise QRContractError()
    if not isinstance(request.request_id, str):
        raise QRContractError()
    try:
        UUID(request.request_id)
    except (ValueError, AttributeError):
        raise QRContractError("request_id 必须是有效 UUID 字符串。") from None
    if not isinstance(request.text, str):
        raise QRContractError("text 必须是字符串。")
    # datetime-like objects are insufficient: the public field is datetime.
    if not isinstance(request.timestamp, datetime):
        raise QRContractError("timestamp 必须是带时区 datetime。")
    if request.timestamp.tzinfo is None or request.timestamp.utcoffset() is None:
        raise QRContractError("timestamp 必须包含有效时区。")
    if not isinstance(request.source, str) or request.source not in (Source.CLI, Source.GUI):
        raise QRContractError("source 必须是 cli 或 gui。")
    if not isinstance(request.mode, str) or not isinstance(request.ecc_level, str):
        raise QRContractError()
    if type(request.version) is not int and not isinstance(request.version, str):
        raise QRContractError("version 必须是整数或 auto。")
    if type(request.mask_id) is not int and not isinstance(request.mask_id, str):
        raise QRContractError("mask_id 必须是整数或 auto。")
    if type(request.capture_steps) is not bool:
        raise QRContractError("capture_steps 必须是 bool。")


def _baseline_plan() -> EncodingPlan:
    """Load the shared fixed plan, independent of optional extensions."""
    resource = files("qr_app.resources").joinpath("qr_capacity_v1_v2.json")
    entries = json.loads(resource.read_text(encoding="utf-8"))["plans"]
    matches = [entry for entry in entries
               if entry.get("version") == 1 and entry.get("ecc_level") == "L"]
    if len(matches) != 1:
        raise ValueError("Specification must contain exactly one V1/L baseline entry")
    entry = dict(matches[0])
    entry["ecc_level"] = ECCLevel(entry["ecc_level"])
    entry["block_groups"] = tuple(BlockGroup(**group) for group in entry["block_groups"])
    plan = EncodingPlan(**entry)
    if plan.version != 1 or plan.ecc_level != ECCLevel.L:
        raise ValueError("Baseline specification must be V1/L")
    return plan


class QRService:
    def __init__(
        self, *, version_selector: VersionSelector | None = None,
        mask_selector: MaskSelector | None = None,
        usage_logger: UsageLogger | None = None,
    ) -> None:
        for selector in (version_selector, mask_selector):
            if selector is not None and not callable(selector):
                raise TypeError("Selectors must be callable")
        if usage_logger is not None and not callable(getattr(usage_logger, "append_attempt", None)):
            raise TypeError("usage_logger must implement append_attempt")
        self._version_selector = version_selector
        self._mask_selector = mask_selector
        self._usage_logger = usage_logger

    @property
    def capabilities(self) -> frozenset[str]:
        """Only optional capabilities actually assembled at startup."""
        return frozenset(
            name for name, dependency in (
                ("version_ecc", self._version_selector),
                ("mask_selection", self._mask_selector),
                ("usage_logging", self._usage_logger),
            ) if dependency is not None
        )

    def _validate_options(self, request: QRRequest) -> None:
        if (request.mode not in (Mode.BASELINE, Mode.EXTENDED)
                or request.version not in (1, 2, "auto")
                or request.ecc_level not in ("L", "M", "Q", "H", "auto")
                or request.mask_id not in (*range(8), "auto")
                or request.options):
            raise QRGenerationError(ErrorCode.INVALID_OPTION, "请求包含不支持的参数或额外选项。")
        if request.mode == Mode.BASELINE:
            if (request.version, request.ecc_level, request.mask_id) != (1, "L", 0):
                raise QRGenerationError(
                    ErrorCode.MODE_PARAMETER_CONFLICT, "基础模式必须使用 V1/L/Mask0。",
                )
        else:
            if self._version_selector is None:
                raise QRGenerationError(ErrorCode.FEATURE_UNAVAILABLE, "版本与纠错等级扩展尚未接入。")
            if self._mask_selector is None and request.mask_id != 0:
                raise QRGenerationError(ErrorCode.FEATURE_UNAVAILABLE, "完整掩码选择扩展尚未接入。")

    def generate_qr(self, request: QRRequest) -> QRResult:
        """Return business failures with partial trace; raise caller errors.

        Byte-mode data encoding and data ECC are implemented. Matrix building
        and masking remain explicit stubs; valid baseline requests currently
        stop at matrix building with FEATURE_UNAVAILABLE, never a fake QR.
        Each accepted request invokes the optional usage logger once.
        """
        _validate_request(request)
        trace = TraceCollector(request.capture_steps)
        byte_length = None
        plan = None
        warnings: tuple[str, ...] = ()
        try:
            self._validate_options(request)
            if request.text == "":
                raise QRGenerationError(ErrorCode.EMPTY_INPUT, "请输入需要编码的文本。")
            data_bytes = byte_encoder.encode_text(request.text)
            byte_length = len(data_bytes)
            trace.record(
                "input.iso_8859_1", "字符编码", "严格 ISO-8859-1 编码完成，未修改原文。",
                PayloadType.CODEWORDS, data_bytes,
            )
            if request.text.isspace():
                warnings = ("输入仅含空白，扫码软件显示可能不明显。",)
            if request.mode == Mode.BASELINE:
                candidate = _baseline_plan()
            else:
                candidate = self._version_selector(
                    byte_length, request.version, request.ecc_level, request.mode,
                )
            if not isinstance(candidate, EncodingPlan):
                raise TypeError("Selector must return EncodingPlan")
            if ((request.version != "auto" and request.version != candidate.version)
                    or (request.ecc_level != "auto" and request.ecc_level != candidate.ecc_level)):
                raise ValueError("Selector changed a locked parameter")
            if byte_length > candidate.capacity_bytes:
                raise QRGenerationError(
                    ErrorCode.CAPACITY_EXCEEDED, "输入字节数超过所选版本和纠错等级的容量。",
                    {"byte_length": byte_length, "capacity_bytes": candidate.capacity_bytes},
                )
            plan = candidate
            trace.record(
                "plan.selected", "编码计划", "已确认实际版本、纠错等级和容量。",
                PayloadType.TEXT,
                {"version": plan.version, "ecc_level": plan.ecc_level,
                 "byte_length": byte_length, "capacity_bytes": plan.capacity_bytes},
            )
            encoded = byte_encoder.encode_data(data_bytes, plan, trace=trace)
            if encoded.byte_length != byte_length or len(encoded.data_codewords) != plan.data_codewords:
                raise ValueError("Encoded data disagrees with plan")
            final = error_correction.build_final_codewords(encoded.data_codewords, plan, trace=trace)
            if (len(final.interleaved_codewords) != plan.total_codewords
                    or len(final.bitstream) != 8 * plan.total_codewords + plan.remainder_bits):
                raise ValueError("Final codewords disagree with plan")
            layout = matrix_builder.build_matrix(final.bitstream, plan, trace=trace)
            if layout.version != plan.version:
                raise ValueError("Layout version disagrees with plan")
            use_full_selector = request.mode == Mode.EXTENDED and self._mask_selector is not None
            if use_full_selector:
                selected = self._mask_selector(layout, plan, request.mask_id, trace=trace)
            else:
                selected = fixed_mask.apply_fixed_mask_zero(layout, plan, trace=trace)
            if not isinstance(selected, MaskSelection):
                raise TypeError("Mask stage must return MaskSelection")
            if request.mask_id != "auto" and selected.mask_id != request.mask_id:
                raise ValueError("Mask stage changed a locked mask")
            if use_full_selector and len(selected.penalty_scores) != 8:
                raise ValueError("Full mask selection requires all eight scores")
            if not use_full_selector and selected.penalty_scores:
                raise ValueError("Fixed Mask0 must not fabricate scores")
            result = QRResult(
                request_id=request.request_id, generation_success=True,
                byte_length=byte_length, plan=plan, matrix=selected.final_matrix,
                mask_id=selected.mask_id, penalty_scores=selected.penalty_scores,
                trace_steps=trace.steps(), warnings=warnings,
            )
        except QRGenerationError as error:
            result = QRResult(
                request_id=request.request_id, generation_success=False,
                byte_length=byte_length, plan=plan, trace_steps=trace.steps(), warnings=warnings,
                error_code=error.code, error_message=error.message, error_details=error.details,
            )
        except Exception as error:
            # Do not format the exception or traceback: either may contain input,
            # credentials or local paths. Hosts can attach a local handler.
            _DIAGNOSTICS.error("generation_failure id=%s type=%s", request.request_id, type(error).__name__)
            result = QRResult(
                request_id=request.request_id, generation_success=False,
                byte_length=byte_length, plan=plan, trace_steps=trace.steps(), warnings=warnings,
                error_code=ErrorCode.INTERNAL_GENERATION_ERROR,
                error_message="生成过程中发生内部错误，请联系维护者。",
            )
        return self._log_once(request, result)

    def _log_once(self, request: QRRequest, result: QRResult) -> QRResult:
        if self._usage_logger is None:
            return result
        try:
            status = self._usage_logger.append_attempt(request, result)
            if not isinstance(status, LogStatus) or status.state == LogState.NOT_ENABLED:
                raise TypeError("An assembled logger must return a completed logging status")
        except Exception as error:
            _DIAGNOSTICS.error("logging_failure id=%s type=%s", request.request_id, type(error).__name__)
            status = LogStatus(LogState.FAILED, ErrorCode.LOG_WRITE_FAILED, "本次使用记录未能保存。")
        warnings = result.warnings
        if status.state == LogState.FAILED:
            warnings += ("使用记录保存失败，统计可能未包含本次请求。",)
        return replace(result, logging_status=status, warnings=warnings)
