"""Tkinter GUI for converting one or more PDFs to image files."""

from __future__ import annotations

import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from modules.pdf_to_images.models import ExportOptions
from modules.pdf_to_images.service import collect_pdf_page_counts, export_pdf_pages, unique_subdir


def _default_output_dir() -> Path:
    """Resolve a sensible default output directory for exports.

    Args:
        None.

    Returns:
        Path to the user's Downloads folder when available, otherwise home directory.
    """

    downloads_dir = Path.home() / "Downloads"
    if downloads_dir.exists():
        # If Downloads exists, use it as the app default output location.
        return downloads_dir
    # If Downloads cannot be found, fall back to the user's home directory.
    return Path.home()


class PdfToImagesApp:
    """Desktop user interface for PDF page export operations.

    Args:
        root: The top-level Tkinter window (`tk.Tk`) used as this app's main window.

    Returns:
        None. The class constructor initializes state and builds the interface.
    """

    def __init__(self, root: tk.Tk) -> None:
        """Initialize window settings, in-memory state, and UI widgets.

        Args:
            root: Root Tkinter window that hosts all widgets for this application.

        Returns:
            None. This method configures object attributes and calls `_build_ui`.
        """

        self.root = root
        self.root.title("PDF to Images Exporter")
        self.root.geometry("860x620")
        self.root.minsize(760, 520)

        # Store user-selected PDF paths in display order.
        self.pdf_paths: list[Path] = []
        # Track whether an export worker thread is currently running.
        self.is_running = False

        # Tkinter variables keep UI state synchronized with widgets.
        self.output_dir_var = tk.StringVar(value=str(_default_output_dir()))
        self.format_var = tk.StringVar(value="png")
        self.dpi_var = tk.IntVar(value=300)
        self.flat_output_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()

    def _build_ui(self) -> None:
        """Create and arrange every widget in the PDF export window.

        Args:
            None.

        Returns:
            None. Widgets are added directly to the current top-level window.
        """

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        ttk.Label(
            main,
            text="Select one or more PDFs and export every page to images",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        files_frame = ttk.LabelFrame(main, text="PDF files", padding=10)
        files_frame.grid(row=1, column=0, sticky="nsew")
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)

        self.files_listbox = tk.Listbox(files_frame, selectmode=tk.EXTENDED, height=8)
        self.files_listbox.grid(row=0, column=0, sticky="nsew")

        files_buttons = ttk.Frame(files_frame)
        files_buttons.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        ttk.Button(files_buttons, text="Add PDFs...", command=self.add_pdfs).pack(fill="x", pady=(0, 6))
        ttk.Button(files_buttons, text="Remove Selected", command=self.remove_selected).pack(
            fill="x", pady=(0, 6)
        )
        ttk.Button(files_buttons, text="Clear List", command=self.clear_list).pack(fill="x")

        options_frame = ttk.LabelFrame(main, text="Export options", padding=10)
        options_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        options_frame.columnconfigure(1, weight=1)

        ttk.Label(options_frame, text="Output folder:").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8)
        )
        ttk.Entry(options_frame, textvariable=self.output_dir_var).grid(
            row=0, column=1, sticky="ew", pady=(0, 8)
        )
        ttk.Button(options_frame, text="Browse...", command=self.select_output_dir).grid(
            row=0, column=2, padx=(8, 0), pady=(0, 8)
        )

        ttk.Label(options_frame, text="Image format:").grid(row=1, column=0, sticky="w", padx=(0, 8))
        ttk.Combobox(
            options_frame,
            textvariable=self.format_var,
            values=["png", "jpg"],
            state="readonly",
            width=10,
        ).grid(row=1, column=1, sticky="w")

        ttk.Label(options_frame, text="DPI:").grid(row=1, column=2, sticky="e", padx=(8, 8))
        ttk.Spinbox(
            options_frame,
            from_=72,
            to=1200,
            increment=10,
            textvariable=self.dpi_var,
            width=8,
        ).grid(row=1, column=3, sticky="w")

        ttk.Checkbutton(
            options_frame,
            text="Export all PDFs into one folder (no subfolder per PDF)",
            variable=self.flat_output_var,
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        progress_frame = ttk.Frame(main)
        progress_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        progress_frame.columnconfigure(0, weight=1)

        self.progress_bar = ttk.Progressbar(progress_frame, mode="determinate", maximum=100, value=0)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_frame, textvariable=self.status_var).grid(row=1, column=0, sticky="w", pady=(6, 0))

        log_frame = ttk.LabelFrame(main, text="Log", padding=10)
        log_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, wrap="word", height=10, state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(main)
        actions.grid(row=5, column=0, sticky="e", pady=(10, 0))
        self.start_button = ttk.Button(actions, text="Start Export", command=self.start_export)
        self.start_button.pack(side="left")
        ttk.Button(actions, text="Close", command=self.root.destroy).pack(side="left", padx=(8, 0))

    def add_pdfs(self) -> None:
        """Open a file picker and add one or more PDFs to the work list.

        Args:
            None.

        Returns:
            None. Paths are stored in `self.pdf_paths` and shown in the listbox.
        """

        paths = filedialog.askopenfilenames(
            title="Choose PDF files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not paths:
            # If the user cancels the dialog, keep existing state unchanged.
            return

        existing = set()
        for path in self.pdf_paths:
            try:
                # Resolve paths so duplicate file selections can be detected reliably.
                existing.add(path.resolve())
            except OSError:
                # Fall back to raw path if resolution fails (e.g., inaccessible drive).
                existing.add(path)

        for path_str in paths:
            path = Path(path_str)
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved not in existing:
                # If the PDF is new, append it to state and to the duplicate-check set.
                self.pdf_paths.append(path)
                existing.add(resolved)

        # Refresh listbox entries to match the latest in-memory path list.
        self._refresh_pdf_listbox()

    def remove_selected(self) -> None:
        """Remove highlighted PDF entries from the list.

        Args:
            None.

        Returns:
            None. Selected rows are removed from both state and UI.
        """

        selected = list(self.files_listbox.curselection())
        for idx in reversed(selected):
            # Delete from the end first so earlier indexes stay valid.
            del self.pdf_paths[idx]
        self._refresh_pdf_listbox()

    def clear_list(self) -> None:
        """Clear all queued PDF files from memory and UI.

        Args:
            None.

        Returns:
            None. The list becomes empty.
        """

        self.pdf_paths.clear()
        self._refresh_pdf_listbox()

    def select_output_dir(self) -> None:
        """Prompt the user to choose an output directory.

        Args:
            None.

        Returns:
            None. The selected folder is written into `self.output_dir_var`.
        """

        output_dir = filedialog.askdirectory(title="Select output folder")
        if output_dir:
            # If a folder was selected, store it for export use.
            self.output_dir_var.set(output_dir)

    def start_export(self) -> None:
        """Validate user inputs and start the background export workflow.

        Args:
            None.

        Returns:
            None. Starts a daemon thread when validation passes.
        """

        if self.is_running:
            # If an export is already running, ignore extra start requests.
            return

        if not self.pdf_paths:
            # If no PDFs are loaded, show guidance and stop.
            messagebox.showwarning("No PDFs selected", "Please add at least one PDF file.")
            return

        output_dir_raw = self.output_dir_var.get().strip()
        if not output_dir_raw:
            # If output folder is blank, require selection before continuing.
            messagebox.showwarning("Missing output folder", "Please select an output folder.")
            return

        try:
            # Parse DPI from the spinbox variable.
            dpi = int(self.dpi_var.get())
        except (TypeError, ValueError):
            # If parsing fails, ask the user for a valid numeric value.
            messagebox.showerror("Invalid DPI", "DPI must be a number.")
            return

        if dpi < 72 or dpi > 1200:
            # If value is outside supported bounds, prevent export.
            messagebox.showerror("Invalid DPI", "Please choose a DPI between 72 and 1200.")
            return

        image_format = self.format_var.get().lower()
        if image_format not in {"png", "jpg"}:
            # If unsupported format is somehow set, block and show an error.
            messagebox.showerror("Invalid format", "Image format must be png or jpg.")
            return

        # Build immutable export options passed into service-layer functions.
        options = ExportOptions(
            output_dir=Path(output_dir_raw),
            image_format=image_format,
            dpi=dpi,
            flat_output=self.flat_output_var.get(),
        )
        # Lock controls and initialize progress/logging before worker starts.
        self._set_running_state(True)
        self._set_progress(0, 1)
        self._set_status("Starting export...")
        self._log("Export started")

        # Run conversion on a background thread so the UI remains responsive.
        worker = threading.Thread(target=self._run_export, args=(options,), daemon=True)
        worker.start()

    def _run_export(self, options: ExportOptions) -> None:
        """Execute the full export pipeline on a worker thread.

        Args:
            options: Export configuration selected by the user.

        Returns:
            None. Progress and results are communicated back to the UI thread.
        """

        try:
            # Ensure output directory exists before any file writes occur.
            options.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # If folder creation fails, report and stop immediately.
            self.root.after(0, lambda: self._on_export_failed(f"Could not create output folder: {exc}"))
            return

        # Pre-scan PDFs to count pages and collect readability errors.
        pdf_entries, preflight_errors = collect_pdf_page_counts(self.pdf_paths)
        for error in preflight_errors:
            # Queue log updates on the UI thread.
            self.root.after(0, lambda msg=error: self._log(msg))

        total_pages = sum(page_count for _, page_count in pdf_entries)
        if total_pages == 0:
            # If no pages are readable, fail fast with a clear message.
            self.root.after(0, lambda: self._on_export_failed("No readable pages found in selected PDFs."))
            return

        exported_pages = 0
        num_pdfs = len(pdf_entries)
        for pdf_index, (pdf_path, page_count) in enumerate(pdf_entries, start=1):
            if options.flat_output:
                # All images go directly under the chosen output folder.
                subdir = options.output_dir
                # When several PDFs share one folder, prefix basenames so names stay unique.
                filename_prefix = f"{pdf_index:03d}_" if num_pdfs > 1 else ""
            else:
                # Create a dedicated subfolder for this PDF export batch.
                subdir = unique_subdir(options.output_dir, pdf_path.stem)
                subdir.mkdir(parents=True, exist_ok=False)
                filename_prefix = ""

            self.root.after(0, lambda p=pdf_path, c=page_count: self._log(f"Processing '{p.name}' ({c} pages)"))

            try:
                # Export each page and update status text for every page callback.
                count = export_pdf_pages(
                    pdf_path=pdf_path,
                    options=options,
                    output_subdir=subdir,
                    filename_prefix=filename_prefix,
                    on_page_exported=lambda page_idx, p=pdf_path, c=page_count: self.root.after(
                        0, lambda: self._set_status(f"Exporting {p.name} - page {page_idx}/{c}")
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                # If one PDF fails, log it and continue with the next PDF.
                self.root.after(0, lambda p=pdf_path, e=exc: self._log(f"Failed '{p.name}': {e}"))
                continue

            exported_pages += count
            # After each PDF is done, update progress and append completion log.
            self.root.after(
                0,
                lambda p=pdf_path, s=subdir, d=exported_pages, t=total_pages: self._on_pdf_complete(
                    p.name, s, d, t
                ),
            )

        # Notify final completion once every readable PDF has been processed.
        self.root.after(
            0, lambda: self._on_export_finished(f"Export completed. Pages exported: {exported_pages}")
        )

    def _on_pdf_complete(self, pdf_name: str, output_path: Path, done: int, total: int) -> None:
        """Handle UI updates after one PDF finishes exporting.

        Args:
            pdf_name: Friendly source PDF filename for logging.
            output_path: Folder where the PDF's images were saved.
            done: Number of pages exported so far across all PDFs.
            total: Total pages expected across all readable PDFs.

        Returns:
            None. Updates progress bar and log area.
        """

        self._set_progress(done, total)
        self._log(f"Done '{pdf_name}' -> {output_path}")

    def _refresh_pdf_listbox(self) -> None:
        """Synchronize listbox rows with `self.pdf_paths`.

        Args:
            None.

        Returns:
            None. UI list content is fully rebuilt.
        """

        self.files_listbox.delete(0, tk.END)
        for path in self.pdf_paths:
            # Insert one row per stored PDF path.
            self.files_listbox.insert(tk.END, str(path))

    def _log(self, message: str) -> None:
        """Append one line to the on-screen log text widget.

        Args:
            message: Message string to display at the end of the log.

        Returns:
            None. This method mutates text widget contents only.
        """

        # Temporarily enable editing so text can be inserted.
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"{message}\n")
        # Auto-scroll so the latest message remains visible.
        self.log_text.see(tk.END)
        # Disable editing again to keep log read-only for users.
        self.log_text.configure(state="disabled")

    def _set_progress(self, done: int, total: int) -> None:
        """Update progress bar values based on completed and total pages.

        Args:
            done: Number of exported pages completed.
            total: Total pages expected to export.

        Returns:
            None. Progress bar widget values are updated in place.
        """

        if total <= 0:
            # If total is invalid, reset to a safe default state.
            self.progress_bar.configure(value=0, maximum=100)
            return
        # If totals are valid, map progress directly to page counts.
        self.progress_bar.configure(maximum=total, value=done)

    def _set_status(self, text: str) -> None:
        """Set the short status label shown near the progress bar.

        Args:
            text: Human-readable status message for current export phase.

        Returns:
            None. Updates a Tkinter `StringVar`.
        """

        self.status_var.set(text)

    def _set_running_state(self, running: bool) -> None:
        """Toggle running state and start button availability.

        Args:
            running: `True` while export is active, `False` otherwise.

        Returns:
            None. Updates internal flag and start button state.
        """

        self.is_running = running
        # If running, disable "Start Export"; otherwise re-enable it.
        self.start_button.configure(state="disabled" if running else "normal")

    def _on_export_failed(self, message: str) -> None:
        """Handle terminal failure path for export workflow.

        Args:
            message: Error details shown in log and modal dialog.

        Returns:
            None. Resets UI running state and informs the user.
        """

        self._set_running_state(False)
        self._set_status("Failed")
        self._log(message)
        # Show an explicit error dialog so failures are visible immediately.
        messagebox.showerror("Export failed", message)

    def _on_export_finished(self, message: str) -> None:
        """Handle successful completion of the export workflow.

        Args:
            message: Completion summary shown in log and info dialog.

        Returns:
            None. Unlocks UI and informs the user.
        """

        self._set_running_state(False)
        self._set_status("Completed")
        self._log(message)
        # Show a completion dialog so users know work has finished.
        messagebox.showinfo("Done", message)
