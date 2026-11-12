"""Explicit PNG export, independent of QR generation and Qt dialogs."""

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from matplotlib.figure import Figure

from ..errors import ArtifactSaveError


@dataclass(frozen=True)
class SavedArtifact:
    path: Path
    media_type: str = "image/png"


def save_figure(figure: Figure, target_path: str | Path, *, overwrite: bool = False) -> SavedArtifact:
    """Save a complete PNG without closing the caller's Figure or canvas.

    The parent directory must already exist. Stage the complete image beside
    the destination before publishing; never truncate an existing destination.
    """
    if not isinstance(figure, Figure):
        raise TypeError("figure must be a matplotlib Figure")
    if not isinstance(target_path, (str, Path)):
        raise TypeError("target_path must be a string or Path")
    if type(overwrite) is not bool:
        raise TypeError("overwrite must be bool")

    temporary = None
    try:
        target = Path(target_path).resolve()
        if target.suffix.lower() != ".png":
            raise ArtifactSaveError("请选择以 .png 结尾的文件名。")
        if not target.parent.is_dir() or target.is_dir():
            raise ArtifactSaveError("PNG 保存失败；请选择已存在的文件夹和有效文件名。")
        if target.exists() and not overwrite:
            raise FileExistsError

        with tempfile.NamedTemporaryFile(mode="w+b", dir=target.parent,
                prefix=".qr-png-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            # Explicit full Figure bounds ignore savefig.bbox='tight', keeping
            # the quiet zone intact. savefig restores the original Qt canvas.
            visible = figure.patch.get_visible()
            try:
                figure.patch.set_visible(True)
                figure.savefig(stream, format="png", backend="agg", dpi=figure.dpi,
                               bbox_inches=figure.bbox_inches.frozen(), pad_inches=0,
                               facecolor="white", edgecolor="white", transparent=False)
            finally:
                figure.patch.set_visible(visible)

        if overwrite:
            os.replace(temporary, target)
            temporary = None
        elif os.name == "nt":
            # Windows rename rejects an existing target, including one created
            # after the early existence check. POSIX rename would overwrite it.
            os.rename(temporary, target)
            temporary = None
        else:
            os.link(temporary, target)
        return SavedArtifact(path=target)
    except FileExistsError:
        raise ArtifactSaveError("PNG 文件已存在；请确认覆盖或选择其他文件名。") from None
    except (OSError, ValueError, RuntimeError):
        raise ArtifactSaveError("PNG 保存失败；请检查路径、文件占用和写入权限。") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
