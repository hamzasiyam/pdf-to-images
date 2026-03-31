"""Single application entry point for the PDF-to-images desktop tool."""

from modules.pdf_to_images.application import run_pdf_to_images_app


if __name__ == "__main__":
    # Start the PDF-to-images GUI directly from one stable entry point.
    run_pdf_to_images_app()
