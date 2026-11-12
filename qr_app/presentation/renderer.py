"""Render binary QR matrices with matplotlib, without Qt or file operations."""

from dataclasses import dataclass

from matplotlib.axes import Axes
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
import numpy as np


@dataclass(frozen=True)
class RenderOptions:
    """Display geometry; quiet zone is measured in modules, not pixels."""

    quiet_zone_modules: int = 4
    module_pixels: int = 10

    def __post_init__(self):
        for name in ("quiet_zone_modules", "module_pixels"):
            if type(getattr(self, name)) is not int:
                raise TypeError(f"{name} must be an integer, not bool")
        if self.quiet_zone_modules < 4:
            raise ValueError("quiet_zone_modules must be at least 4")
        if self.module_pixels < 1:
            raise ValueError("module_pixels must be positive")


def _prepare_matrix(matrix, render_options):
    if render_options is None:
        render_options = RenderOptions()
    if not isinstance(render_options, RenderOptions):
        raise TypeError("render_options must be RenderOptions or None")
    if not isinstance(matrix, np.ndarray):
        raise TypeError("matrix must be a numpy array")
    if not (np.issubdtype(matrix.dtype, np.integer) or matrix.dtype == np.bool_):
        raise TypeError("matrix must contain integer or boolean modules")
    if matrix.ndim != 2 or not matrix.shape[0] or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("matrix must be a nonempty square two-dimensional array")
    if not np.isin(matrix, (0, 1)).all():
        raise ValueError("matrix must contain only 0 (white) and 1 (black)")
    # np.pad creates independent storage, even when the input is readonly.
    padded = np.pad(matrix, render_options.quiet_zone_modules,
                    mode="constant", constant_values=0)
    return padded, render_options


def _draw_padded_matrix(axes, padded):
    axes.clear()
    axes.set_facecolor("white")
    axes.imshow(
        padded,
        cmap=ListedColormap(("white", "black")),
        vmin=0,
        vmax=1,
        interpolation="nearest",
        resample=False,
        origin="upper",
        aspect="equal",
    )
    side = padded.shape[0]
    axes.set_xlim(-0.5, side - 0.5)
    axes.set_ylim(side - 0.5, -0.5)
    axes.set_aspect("equal", adjustable="box")
    axes.set_anchor("C")
    axes.set_axis_off()


def render_qr(matrix, render_options=None) -> Figure:
    """Create a square Figure: 0 white, 1 black, with at least 4 white modules.

    At the initial DPI each module occupies module_pixels square pixels.
    No pyplot manager, Qt application, display window or output file is created.
    The caller owns the Figure and may attach an Agg or Qt canvas.
    """
    padded, options = _prepare_matrix(matrix, render_options)
    pixel_side = padded.shape[0] * options.module_pixels
    # A power-of-two DPI represents integer pixel sizes exactly; rounding a
    # slightly oversized bbox can otherwise move the top row by one pixel.
    dpi = 128
    inches = pixel_side / dpi
    figure = Figure(figsize=(inches, inches), dpi=dpi, facecolor="white",
                    edgecolor="white", frameon=True, layout="none")
    axes = figure.add_axes((0, 0, 1, 1))
    _draw_padded_matrix(axes, padded)
    return figure


def draw_matrix(axes, matrix, render_options=None) -> None:
    """Replace only the supplied Axes with an equally scaled, bordered matrix.

    The caller controls Figure size and canvas lifetime. module_pixels sets the
    initial size only in render_qr; drawing here never resizes a GUI's Figure.
    Invalid inputs are rejected before any existing Axes contents are cleared.
    """
    if not isinstance(axes, Axes):
        raise TypeError("axes must be a matplotlib Axes")
    padded, _ = _prepare_matrix(matrix, render_options)
    _draw_padded_matrix(axes, padded)
