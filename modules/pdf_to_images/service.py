"""Service layer for reading PDFs and exporting image files."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import fitz
from PIL import Image

from modules.pdf_to_images.models import ExportOptions


def collect_pdf_page_counts(pdf_paths: list[Path]) -> tuple[list[tuple[Path, int]], list[str]]:
    """Inspect selected PDFs and gather each file's page count.

    Args:
        pdf_paths: List of PDF file paths selected by the user.

    Returns:
        A tuple containing:
        - A list of `(pdf_path, page_count)` entries for readable PDFs.
        - A list of error messages for PDFs that could not be opened.
    """

    entries: list[tuple[Path, int]] = []
    errors: list[str] = []

    for pdf_path in pdf_paths:
        try:
            # Open each PDF just long enough to read its page count.
            with fitz.open(pdf_path) as doc:
                entries.append((pdf_path, len(doc)))
        except Exception as exc:  # noqa: BLE001
            # If a PDF cannot be read, capture a user-friendly reason and continue.
            errors.append(f"Skipping '{pdf_path.name}': cannot read PDF ({exc})")

    return entries, errors


def export_pdf_pages(
    pdf_path: Path,
    options: ExportOptions,
    output_subdir: Path,
    on_page_exported: Callable[[int], None] | None = None,
    filename_prefix: str = "",
) -> int:
    """Export every page from one PDF file into image files.

    Args:
        pdf_path: Source PDF path currently being processed.
        options: Export settings (output format, DPI, destination root).
        output_subdir: Folder where this PDF's pages are saved.
        on_page_exported: Optional callback invoked with 1-based page index after each save.
        filename_prefix: Optional string prepended to each image basename (e.g. to avoid
            collisions when several PDFs share one output folder).

    Returns:
        Total number of pages successfully exported for the input PDF.
    """

    exported_count = 0
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            # Convert the PDF page into a Pillow image at the requested DPI.
            image = render_page_to_pil(page, options.dpi)
            filename = f"{filename_prefix}{pdf_path.stem}_page_{page_index:04d}.{options.image_format}"
            output_path = output_subdir / filename
            # Write the image to disk using the selected output format.
            save_image(image, output_path, options.image_format)
            exported_count += 1
            if on_page_exported:
                # Notify callers (usually the UI) so they can update progress text.
                on_page_exported(page_index)

    return exported_count


def render_page_to_pil(page: fitz.Page, dpi: int) -> Image.Image:
    """Render a PyMuPDF page object into a Pillow image.

    Args:
        page: PyMuPDF page object representing one page from a document.
        dpi: Target output resolution; higher values yield larger images.

    Returns:
        A Pillow `Image.Image` instance in RGB or RGBA mode.
    """

    # Convert DPI into a scaling factor because PDF coordinates are 72 DPI based.
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    # Rasterize the vector PDF page into a pixel buffer.
    pix = page.get_pixmap(matrix=matrix)
    if pix.alpha:
        # If alpha is present, preserve transparency.
        return Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    # Otherwise create a standard RGB image.
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def save_image(image: Image.Image, output_path: Path, image_format: str) -> None:
    """Save a Pillow image to disk using supported output formats.

    Args:
        image: Pillow image object to persist.
        output_path: Full file path where the image should be written.
        image_format: Requested output format (`"png"` or `"jpg"`).

    Returns:
        None. The function writes a file and does not return a value.
    """

    if image_format == "jpg":
        # If JPEG is requested, convert RGBA to RGB because JPEG has no alpha channel.
        if image.mode == "RGBA":
            image = image.convert("RGB")
        image.save(output_path, format="JPEG", quality=95)
        return
    # Default to PNG for lossless output and transparency support.
    image.save(output_path, format="PNG")


def unique_subdir(base: Path, preferred_name: str) -> Path:
    """Generate a non-conflicting output subdirectory path.

    Args:
        base: Parent output directory.
        preferred_name: Initial folder name, typically derived from PDF filename.

    Returns:
        A directory path that does not currently exist.
    """

    candidate = base / preferred_name
    if not candidate.exists():
        # If the preferred folder name is free, use it directly.
        return candidate

    suffix = 2
    while True:
        # If a collision exists, append incremental numeric suffixes.
        candidate = base / f"{preferred_name}_{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1
