"""Backward-compatible entry point that delegates to the single app bootstrap."""

from modules.pdf_to_images.application import run_pdf_to_images_app


if __name__ == "__main__":
    # Keep supporting `python app.py` by forwarding to the same app startup flow.
    run_pdf_to_images_app()
