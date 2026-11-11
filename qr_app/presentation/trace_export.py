"""Render existing results and save explicit UTF-8 reports; never generate QR data."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import tempfile

import numpy as np

from ..errors import ArtifactSaveError
from ..models import QRRequest, QRResult


def _plain(value):
    """Convert immutable contract snapshots without deepcopying mapping proxies."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.ndarray):
        return {"dtype": str(value.dtype), "shape": list(value.shape), "data": value.tolist()}
    if isinstance(value, bytes):
        return {"length": len(value), "hex": value.hex(" ").upper()}
    if is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def quoted(value) -> str:
    """Escape controls and non-ASCII input for unambiguous, terminal-safe output."""
    return json.dumps(_plain(value), ensure_ascii=True, allow_nan=False, sort_keys=True)


def matrix_text(matrix: np.ndarray) -> str:
    return "\n".join(" ".join(str(int(module)) for module in row) for row in matrix)


def render_summary(request: QRRequest, result: QRResult) -> str:
    lines = [
        f"Request ID: {request.request_id}",
        f"Input (JSON): {quoted(request.text)}",
        f"Generation: {'SUCCESS' if result.generation_success else 'FAILED'}",
        f"Byte length: {quoted(result.byte_length)}",
        "Actual plan: " + quoted(result.plan),
        f"Actual mask: {quoted(result.mask_id)}",
        f"Trace steps: {len(result.trace_steps)}",
        f"Logging: {result.logging_status.state}",
    ]
    for warning in result.warnings:
        lines.append(f"Warning: {warning}")
    if not result.generation_success:
        lines.extend((f"Error code: {result.error_code}",
                      f"Error message: {result.error_message}",
                      f"Error details: {quoted(result.error_details)}"))
    if result.matrix is None:
        lines.append("Final matrix: null")
    else:
        lines.extend((f"Final matrix: dtype={result.matrix.dtype}, shape={result.matrix.shape}, "
                      "0=white, 1=black, no quiet zone", matrix_text(result.matrix)))
    return "\n".join(lines) + "\n"


def render_report(request: QRRequest, result: QRResult) -> str:
    """Export only steps actually captured, including partial failure traces."""
    lines = [
        "QR trace report / schema 1.0 / interface 1.0",
        "Contains original input and reversible encoding data.",
        f"Timestamp: {request.timestamp.isoformat()}",
        f"Source: {request.source}",
        f"Mode: {request.mode}",
        "Requested settings: " + quoted({"version": request.version,
            "ecc_level": request.ecc_level, "mask_id": request.mask_id,
            "capture_steps": request.capture_steps, "options": request.options}),
        f"Selection policy: {result.selection_policy_version}",
        f"Python: {platform.python_implementation()} {platform.python_version()}",
        f"NumPy: {np.__version__}",
        f"reedsolo: {version('reedsolo')}",
        "Logging status: " + quoted(result.logging_status),
        "Penalty scores: " + quoted(result.penalty_scores),
        "",
        render_summary(request, result).rstrip("\n"),
        "",
        f"Captured steps: {len(result.trace_steps)}",
    ]
    for index, step in enumerate(result.trace_steps, 1):
        lines.extend(("", f"[{index:02d}] {step.step_id}", f"Title: {step.title}",
                      f"Explanation: {step.explanation}", f"Payload type: {step.payload_type}"))
        payload = step.payload
        if isinstance(payload, np.ndarray):
            lines.append(f"dtype={payload.dtype}, shape={payload.shape}")
            lines.append(matrix_text(payload))
        elif isinstance(payload, bytes):
            lines.append(f"Codewords ({len(payload)} bytes, hex): {payload.hex(' ').upper()}")
        elif step.payload_type == "bits":
            lines.append(f"Bits ({len(payload)}): {''.join(str(bit) for bit in payload)}")
        else:
            lines.append("Payload (JSON): " + quoted(payload))
    return "\n".join(lines) + "\n"


def save_report(report: str, path: str | Path, *, overwrite: bool = False) -> Path:
    """Do not create parent directories. Replacements are staged beside the target."""
    temporary = None
    try:
        target = Path(path).resolve()
        if not overwrite:
            # Exclusive creation also protects against a check-then-open race.
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(report)
        else:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                    dir=target.parent, prefix=".qr-report-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(report)
            os.replace(temporary, target)
            temporary = None
        return target
    except FileExistsError:
        raise ArtifactSaveError("步骤报告已存在；如需替换，请使用 --overwrite。") from None
    except (OSError, ValueError, UnicodeError):
        raise ArtifactSaveError("步骤报告保存失败；请检查路径、父目录和写入权限。") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass
