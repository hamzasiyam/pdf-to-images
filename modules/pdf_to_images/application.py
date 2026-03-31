"""Application bootstrap for running the PDF-to-images GUI."""

from __future__ import annotations

import tkinter as tk

from modules.pdf_to_images.gui import PdfToImagesApp


def run_pdf_to_images_app() -> None:
    """Create the root window and run the PDF-to-images event loop.

    Args:
        None.

    Returns:
        None. This function starts the Tkinter main loop and blocks until close.
    """

    # Create a single root window for this standalone application.
    root = tk.Tk()
    # Build the complete PDF-to-images UI on the root window.
    PdfToImagesApp(root)
    # Enter Tkinter's event loop to keep the window responsive.
    root.mainloop()
