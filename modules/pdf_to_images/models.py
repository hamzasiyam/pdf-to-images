"""Data models shared by the PDF-to-images module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExportOptions:
    """Immutable export configuration for PDF page conversion.

    Args:
        output_dir: Directory where exported images will be written.
        image_format: Output format string, expected values are `"png"` or `"jpg"`.
        dpi: Rendering resolution used to rasterize each PDF page.
        flat_output: When True, write all images directly under ``output_dir`` with no
            per-PDF subfolders.

    Returns:
        None. This dataclass only stores values for other components to consume.
    """

    output_dir: Path
    image_format: str
    dpi: int
    flat_output: bool = False
