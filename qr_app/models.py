"""Contract 1.0 data objects; matrices exclude the quiet zone.

Arrays use [row, col], 0 for white and 1 for black. Public objects own
independent snapshots rather than borrowing mutable caller buffers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

import numpy as np

from .errors import QRContractError

SELECTION_POLICY_VERSION = "input_rules_v1"


class Source(StrEnum):
    CLI = "cli"
    GUI = "gui"


class Mode(StrEnum):
    BASELINE = "baseline"
    EXTENDED = "extended"


class Auto(StrEnum):
    AUTO = "auto"


class ECCLevel(StrEnum):
    L = "L"
    M = "M"
    Q = "Q"
    H = "H"


class PayloadType(StrEnum):
    TEXT = "text"
    BITS = "bits"
    CODEWORDS = "codewords"
    MATRIX = "matrix"
    SCORES = "scores"


class LogState(StrEnum):
    NOT_ENABLED = "not_enabled"
    WRITTEN = "written"
    ALREADY_RECORDED = "already_recorded"
    FAILED = "failed"


def freeze_payload(value: Any) -> Any:
    """Snapshot plain data; also retain immutable penalty breakdown values."""
    if isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            raise TypeError("Object arrays are not supported in snapshots")
        copied = value.copy()
        copied.setflags(write=False)
        return copied
    # PenaltyBreakdown is frozen and contains only validated integers.
    if type(value) is PenaltyBreakdown:
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze_payload(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze_payload(item) for item in value)
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return value
    raise TypeError("Snapshots accept only plain data, penalty scores and numeric numpy arrays")


def _matrix_snapshot(value: np.ndarray, *, boolean: bool = False) -> np.ndarray:
    dtype = np.dtype(bool if boolean else np.uint8)
    if not isinstance(value, np.ndarray) or value.dtype != dtype:
        raise ValueError(f"Matrix dtype must be {dtype}")
    if value.ndim != 2 or value.shape[0] != value.shape[1]:
        raise ValueError("Matrix must be square")
    if not boolean and not np.isin(value, (0, 1)).all():
        raise ValueError("Matrix modules must be 0 or 1")
    return freeze_payload(value)


def _positive_int(value: int, name: str, *, allow_zero: bool = False) -> None:
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise ValueError(f"{name} must be a {'nonnegative' if allow_zero else 'positive'} int")


@dataclass(frozen=True)
class QRRequest:
    text: str
    source: Source = Source.CLI
    mode: Mode = Mode.BASELINE
    version: int | Auto = 1
    ecc_level: ECCLevel | Auto = ECCLevel.L
    mask_id: int | Auto = 0
    capture_steps: bool = True
    request_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.options, Mapping):
            raise QRContractError()
        # Values are currently forbidden by the empty options whitelist. Only
        # snapshot the keys so unsupported values can yield INVALID_OPTION.
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


@dataclass(frozen=True)
class BlockGroup:
    block_count: int
    data_codewords_per_block: int

    def __post_init__(self) -> None:
        _positive_int(self.block_count, "block_count")
        _positive_int(self.data_codewords_per_block, "data_codewords_per_block")


@dataclass(frozen=True)
class EncodingPlan:
    version: int
    ecc_level: ECCLevel
    matrix_size: int
    capacity_bytes: int
    data_codewords: int
    ecc_codewords_per_block: int
    block_groups: tuple[BlockGroup, ...]
    total_codewords: int
    remainder_bits: int
    character_count_bits: int

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version not in (1, 2):
            raise ValueError("Only actual versions 1 and 2 are supported")
        if self.ecc_level not in tuple(ECCLevel):
            raise ValueError("EncodingPlan requires an actual ECC level")
        for name in ("matrix_size", "capacity_bytes", "data_codewords",
                     "ecc_codewords_per_block", "total_codewords", "character_count_bits"):
            _positive_int(getattr(self, name), name)
        _positive_int(self.remainder_bits, "remainder_bits", allow_zero=True)
        groups = tuple(self.block_groups)
        if not groups or not all(isinstance(group, BlockGroup) for group in groups):
            raise ValueError("A plan needs BlockGroup entries")
        if self.matrix_size != 17 + 4 * self.version:
            raise ValueError("matrix_size disagrees with version")
        if sum(g.block_count * g.data_codewords_per_block for g in groups) != self.data_codewords:
            raise ValueError("Block groups disagree with data_codewords")
        blocks = sum(g.block_count for g in groups)
        if self.total_codewords != self.data_codewords + blocks * self.ecc_codewords_per_block:
            raise ValueError("Data and ECC counts disagree with total_codewords")
        if self.character_count_bits != 8 or self.remainder_bits != (0 if self.version == 1 else 7):
            raise ValueError("Invalid V1/V2 Byte-mode count or remainder bits")
        # Single Byte segment: four mode bits plus eight character-count bits.
        if self.capacity_bytes != (8 * self.data_codewords - 12) // 8:
            raise ValueError("Byte capacity disagrees with data codeword count")
        object.__setattr__(self, "block_groups", groups)


@dataclass(frozen=True)
class EncodedData:
    byte_length: int
    data_codewords: bytes

    def __post_init__(self) -> None:
        _positive_int(self.byte_length, "byte_length", allow_zero=True)
        if not isinstance(self.data_codewords, bytes):
            raise TypeError("data_codewords must be bytes")


@dataclass(frozen=True)
class FinalCodewords:
    interleaved_codewords: bytes
    bitstream: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.interleaved_codewords, bytes):
            raise TypeError("interleaved_codewords must be bytes")
        bits = tuple(self.bitstream)
        if any(type(bit) is not int or bit not in (0, 1) for bit in bits):
            raise ValueError("bitstream must contain integer bits")
        object.__setattr__(self, "bitstream", bits)


@dataclass(frozen=True)
class MatrixLayout:
    modules: np.ndarray
    reserved_mask: np.ndarray
    version: int

    def __post_init__(self) -> None:
        modules = _matrix_snapshot(self.modules)
        reserved = _matrix_snapshot(self.reserved_mask, boolean=True)
        if type(self.version) is not int or self.version not in (1, 2):
            raise ValueError("Invalid layout version")
        if modules.shape != reserved.shape or modules.shape != (17 + 4 * self.version,) * 2:
            raise ValueError("Layout shapes disagree with version")
        object.__setattr__(self, "modules", modules)
        object.__setattr__(self, "reserved_mask", reserved)


@dataclass(frozen=True)
class PenaltyBreakdown:
    n1: int
    n2: int
    n3: int
    n4: int
    total: int

    def __post_init__(self) -> None:
        for name in ("n1", "n2", "n3", "n4", "total"):
            _positive_int(getattr(self, name), name, allow_zero=True)
        if self.total != self.n1 + self.n2 + self.n3 + self.n4:
            raise ValueError("Penalty total disagrees with N1/N2/N3/N4")


def _scores_snapshot(scores: Mapping[int, PenaltyBreakdown]) -> Mapping[int, PenaltyBreakdown]:
    if scores and set(scores) != set(range(8)):
        raise ValueError("Scores must be empty or contain all eight masks")
    if any(type(key) is not int or not isinstance(value, PenaltyBreakdown)
           for key, value in scores.items()):
        raise ValueError("Scores must map integer mask IDs to PenaltyBreakdown")
    return MappingProxyType(dict(sorted(scores.items())))


@dataclass(frozen=True)
class MaskSelection:
    mask_id: int
    final_matrix: np.ndarray
    penalty_scores: Mapping[int, PenaltyBreakdown] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.mask_id) is not int or self.mask_id not in range(8):
            raise ValueError("Invalid actual mask ID")
        object.__setattr__(self, "final_matrix", _matrix_snapshot(self.final_matrix))
        object.__setattr__(self, "penalty_scores", _scores_snapshot(self.penalty_scores))


@dataclass(frozen=True)
class TraceStep:
    step_id: str
    title: str
    explanation: str
    payload_type: PayloadType
    payload: Any

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str) or not self.step_id:
            raise ValueError("step_id must be nonempty")
        if self.payload_type not in tuple(PayloadType):
            raise ValueError("Unknown trace payload type")
        object.__setattr__(self, "payload", freeze_payload(self.payload))


@dataclass(frozen=True)
class LogStatus:
    state: LogState = LogState.NOT_ENABLED
    error_code: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if self.state not in tuple(LogState):
            raise ValueError("Unknown logging state")
        if self.state == LogState.FAILED:
            if not self.error_code or not self.message:
                raise ValueError("Failed logging requires an error and message")
        elif self.error_code is not None:
            raise ValueError("Successful/disabled logging cannot have an error")


@dataclass(frozen=True)
class QRResult:
    request_id: str
    generation_success: bool
    byte_length: int | None = None
    plan: EncodingPlan | None = None
    matrix: np.ndarray | None = None
    mask_id: int | None = None
    penalty_scores: Mapping[int, PenaltyBreakdown] = field(default_factory=dict)
    trace_steps: tuple[TraceStep, ...] = ()
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
    error_details: Mapping[str, Any] = field(default_factory=dict)
    logging_status: LogStatus = field(default_factory=LogStatus)
    selection_policy_version: str = SELECTION_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.generation_success) is not bool:
            raise ValueError("generation_success must be bool")
        if self.byte_length is not None:
            _positive_int(self.byte_length, "byte_length", allow_zero=True)
        if self.mask_id is not None and (type(self.mask_id) is not int or self.mask_id not in range(8)):
            raise ValueError("Invalid actual mask ID")
        if self.generation_success:
            if self.plan is None or self.matrix is None or self.mask_id is None or self.byte_length is None:
                raise ValueError("Successful generation needs complete actual values")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("Successful generation cannot have a generation error")
        elif self.matrix is not None or not self.error_code or not self.error_message:
            raise ValueError("Failed generation needs an error and no matrix")
        if self.matrix is not None:
            copied = _matrix_snapshot(self.matrix)
            if copied.shape != (self.plan.matrix_size,) * 2:
                raise ValueError("Result matrix disagrees with plan")
            object.__setattr__(self, "matrix", copied)
        steps = tuple(self.trace_steps)
        if len({step.step_id for step in steps}) != len(steps):
            raise ValueError("Duplicate trace step IDs")
        object.__setattr__(self, "trace_steps", steps)
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "penalty_scores", _scores_snapshot(self.penalty_scores))
        object.__setattr__(self, "error_details", freeze_payload(self.error_details))
