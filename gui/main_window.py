import os
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from services.video_analyzer import VideoAnalyzer
from services.frame_extractor import FrameExtractor
from services.ocr_service import OCRService
from services.speech_sampler import SpeechSampler
from services.speech_service import SpeechService
from services.subtitle_service import SubtitleService
from services.visual_embedder import LocalVisualEmbedder
from services.tmdb_client import TMDBClient
from services.tmdb_service import TMDBService
from services.imdb_search_service import IMDbSearchService
from services.candidate_engine import CandidateEngine
from services.identification_pipeline import LocalIdentificationPipeline
from services.local_settings import LocalSettings


class MovieIdentifierApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Movie Identifier — Local")
        self.root.geometry("1150x860")
        self.root.minsize(980, 720)

        self.video_path = tk.StringVar()
        self.status = tk.StringVar(value="Select a movie file to begin.")
        self.progress = tk.DoubleVar(value=0)

        self.settings_store = LocalSettings()
        self.settings = self.settings_store.load()

        self.analyzer = VideoAnalyzer()
        self.frame_extractor = FrameExtractor()

        self.frame_images = []
        self.frame_cards = []
        self.credit_snapshots = []

        self._build_ui()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, padding=(16, 14))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(
            header, text="Movie Identifier",
            font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, sticky="w", padx=(0, 20))

        ttk.Label(
            header, text="Step 2C — Filename + Credits + OCR + Speech + Multi-Source Candidates"
        ).grid(row=0, column=1, sticky="w")

        ttk.Button(
            header, text="Settings", command=self.open_settings
        ).grid(row=0, column=2)

        main = ttk.Frame(self.root, padding=(16, 0, 16, 10))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        file_frame = ttk.LabelFrame(main, text="Movie File", padding=12)
        file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)

        ttk.Entry(file_frame, textvariable=self.video_path).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            file_frame, text="Browse...", command=self.browse
        ).grid(row=0, column=1, padx=(0, 8))
        self.identify_button = ttk.Button(
            file_frame, text="Analyze & Identify",
            command=self.identify_movie
        )
        self.identify_button.grid(row=0, column=2)

        credit_frame = ttk.LabelFrame(main, text="Opening Credits Snapshot(s)", padding=10)
        credit_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        credit_frame.columnconfigure(0, weight=1)

        self.credit_list = tk.Listbox(credit_frame, height=3, selectmode=tk.EXTENDED)
        self.credit_list.grid(row=0, column=0, rowspan=2, sticky="ew", padx=(0, 8))
        credit_buttons = ttk.Frame(credit_frame)
        credit_buttons.grid(row=0, column=1, sticky="ns")
        ttk.Button(credit_buttons, text="Add Snapshot(s)...", command=self.add_credit_snapshots).pack(fill="x", pady=(0, 4))
        ttk.Button(credit_buttons, text="Remove Selected", command=self.remove_credit_snapshots).pack(fill="x", pady=4)
        ttk.Button(credit_buttons, text="Clear All", command=self.clear_credit_snapshots).pack(fill="x", pady=4)
        ttk.Label(credit_frame, text=(
            "Optional but strongly recommended: upload one or more screenshots of the opening credits "
            "(for example, VLCsnap images). OCR from these images is given high priority when generating candidates."
        ), wraplength=850).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        info_frame = ttk.LabelFrame(main, text="Video Information", padding=12)
        info_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)
        info_frame.columnconfigure(3, weight=1)

        self.info_vars = {}
        fields = [
            ("File Name", "file_name"), ("File Size", "file_size"),
            ("Format", "format_name"), ("Duration", "duration"),
            ("Resolution", "resolution"), ("Video Codec", "video_codec"),
            ("Audio Codec", "audio_codec"), ("Video Bitrate", "video_bitrate"),
            ("Audio Bitrate", "audio_bitrate"),
        ]
        for i, (label, key) in enumerate(fields):
            row, col = i // 2, (i % 2) * 2
            self.info_vars[key] = tk.StringVar(value="-")
            ttk.Label(info_frame, text=label + ":").grid(
                row=row, column=col, sticky="w", padx=(0, 8), pady=3
            )
            ttk.Label(info_frame, textvariable=self.info_vars[key]).grid(
                row=row, column=col + 1, sticky="w", padx=(0, 20), pady=3
            )

        notebook = ttk.Notebook(main)
        notebook.grid(row=3, column=0, sticky="nsew")

        gallery_tab = ttk.Frame(notebook)
        result_tab = ttk.Frame(notebook)
        evidence_tab = ttk.Frame(notebook)

        notebook.add(gallery_tab, text="Representative Frames")
        notebook.add(result_tab, text="Movie Result")
        notebook.add(evidence_tab, text="Evidence")

        self._build_gallery(gallery_tab)
        self._build_result(result_tab)
        self._build_evidence(evidence_tab)

        bottom = ttk.Frame(self.root, padding=(16, 0, 16, 12))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Progressbar(bottom, variable=self.progress, maximum=100).grid(
            row=0, column=0, sticky="ew", padx=(0, 10)
        )
        ttk.Label(bottom, textvariable=self.status).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )

    def _build_gallery(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.gallery_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.gallery_frame, anchor="nw"
        )
        self.gallery_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width)
        )
        ttk.Label(
            self.gallery_frame, text="No frames extracted yet.",
            font=("Segoe UI", 11)
        ).grid(row=0, column=0, padx=20, pady=20)

    def _build_result(self, parent):
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(8, weight=1)
        self.best_tmdb_url = ""
        self.best_imdb_url = ""
        self.result_vars = {}
        fields = [
            ("Best Match", "title"), ("Year", "year"),
            ("Confidence", "confidence"), ("Director", "director"),
            ("Genre", "genre"), ("Runtime", "runtime"),
            ("Rating", "rating"), ("TMDB ID", "tmdb_id"),
        ]
        for i, (label, key) in enumerate(fields):
            self.result_vars[key] = tk.StringVar(value="-")
            ttk.Label(parent, text=label + ":", font=("Segoe UI", 10, "bold")).grid(
                row=i, column=0, sticky="nw", padx=(12, 12), pady=4
            )
            ttk.Label(parent, textvariable=self.result_vars[key]).grid(
                row=i, column=1, sticky="nw", pady=4
            )
        ttk.Label(parent, text="Synopsis:", font=("Segoe UI", 10, "bold")).grid(
            row=8, column=0, sticky="nw", padx=(12, 12), pady=(10, 4)
        )
        self.synopsis = tk.Text(parent, height=8, wrap="word", state="disabled")
        self.synopsis.grid(row=8, column=1, sticky="nsew", padx=(0, 12), pady=(10, 4))

        links = ttk.Frame(parent)
        links.grid(row=9, column=1, sticky="w", padx=(0, 12), pady=(6, 12))
        self.tmdb_link_button = ttk.Button(
            links, text="Open TMDB Page", command=self.open_tmdb_page, state="disabled"
        )
        self.tmdb_link_button.pack(side="left", padx=(0, 8))
        self.imdb_link_button = ttk.Button(
            links, text="Open IMDb Page", command=self.open_imdb_page, state="disabled"
        )
        self.imdb_link_button.pack(side="left")

    def _build_evidence(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        self.evidence = tk.Text(parent, wrap="word", state="disabled")
        self.evidence.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=self.evidence.yview)
        scroll.grid(row=0, column=1, sticky="ns", pady=12)
        self.evidence.configure(yscrollcommand=scroll.set)

    def browse(self):
        path = filedialog.askopenfilename(
            title="Select Movie File",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.avi *.mov *.wmv *.m4v *.webm *.ts *.mts *.m2ts"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.video_path.set(path)
            self.progress.set(0)
            self.status.set("Movie selected.")
            self._clear_gallery()
            self._clear_credit_snapshots()
            self._clear_results()

    def add_credit_snapshots(self):
        paths = filedialog.askopenfilenames(
            title="Select Opening Credits Snapshot(s)",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        existing = {os.path.normcase(os.path.abspath(p)) for p in self.credit_snapshots}
        for path in paths:
            key = os.path.normcase(os.path.abspath(path))
            if key not in existing:
                self.credit_snapshots.append(path)
                self.credit_list.insert(tk.END, os.path.basename(path))
                existing.add(key)
        self.status.set(f"{len(self.credit_snapshots)} opening credits snapshot(s) selected.")

    def remove_credit_snapshots(self):
        selected = list(self.credit_list.curselection())
        if not selected:
            return
        for index in reversed(selected):
            self.credit_list.delete(index)
            del self.credit_snapshots[index]
        self.status.set(f"{len(self.credit_snapshots)} opening credits snapshot(s) selected.")

    def clear_credit_snapshots(self):
        self.credit_snapshots.clear()
        if hasattr(self, "credit_list"):
            self.credit_list.delete(0, tk.END)

    def _clear_credit_snapshots(self):
        self.clear_credit_snapshots()

    def identify_movie(self):
        path = self.video_path.get().strip()
        if not path:
            messagebox.showwarning("Movie Identifier", "Please select a movie file first.")
            return

        self.identify_button.config(state="disabled")
        self.progress.set(0)
        self.status.set("Starting local analysis...")
        self._clear_gallery()
        self._clear_results()

        threading.Thread(target=self._worker, args=(path,), daemon=True).start()

    def _worker(self, path):
        try:
            info = self.analyzer.analyze(path)
            if not self.settings.get("tmdb_bearer_token") and not self.settings.get("tmdb_api_key"):
                raise RuntimeError(
                    "TMDB credentials are not configured. Open Settings, "
                    "enter the TMDB API Read Access Token, test it, then Save."
                )
            self.root.after(0, lambda i=info: self._show_video_info(i))

            self.root.after(0, lambda: self.status.set("Extracting representative frames..."))
            frames = self.frame_extractor.extract_representative_frames(
                path, count=12,
                progress_callback=lambda v: self.root.after(
                    0, lambda x=v: self.progress.set(x * 0.10)
                )
            )
            self.root.after(0, lambda f=frames: self._show_frames(f))

            analysis_count = max(2, min(int(self.settings.get("frames_to_analyze", 6)), len(frames)))
            if analysis_count == len(frames):
                analysis_frames = frames
            else:
                indexes = [round(i * (len(frames) - 1) / (analysis_count - 1)) for i in range(analysis_count)]
                analysis_frames = [frames[i] for i in indexes]

            self.root.after(0, lambda n=len(analysis_frames): self.status.set(
                f"Running local analysis on {n} selected frames..."
            ))

            ocr = OCRService()

            credit_text_parts = []
            for idx, snapshot in enumerate(self.credit_snapshots, start=1):
                self.root.after(0, lambda i=idx, n=len(self.credit_snapshots):
                    self.status.set(f"OCR: opening credits snapshot {i} of {n}"))
                text = ocr.extract_text(snapshot)
                if text:
                    credit_text_parts.append(text)
            credit_ocr_text = "\n".join(credit_text_parts)

            sampler = SpeechSampler()

            whisper_model = self.settings["whisper_model"]
            speech = SpeechService(
                model_name=whisper_model,
                device=self.settings["whisper_device"],
                compute_type=self.settings["whisper_compute_type"],
            )

            token = self.settings.get("tmdb_bearer_token", "").strip()
            api_key = self.settings.get("tmdb_api_key", "").strip()
            tmdb = TMDBClient(token=token, api_key=api_key)
            candidates = CandidateEngine(tmdb, imdb_search=IMDbSearchService())

            visual = None
            if self.settings.get("use_visual_embeddings", False):
                visual = LocalVisualEmbedder()

            pipeline = LocalIdentificationPipeline(
                ocr_service=ocr,
                speech_sampler=sampler,
                speech_service=speech,
                tmdb_client=tmdb,
                candidate_engine=candidates,
                visual_embedder=visual,
                subtitle_service=SubtitleService(),
            )

            result = pipeline.run(
                path, info, analysis_frames,
                filename=info.get("file_name") or os.path.basename(path),
                credit_text=credit_ocr_text,
                credit_snapshot_paths=list(self.credit_snapshots),
                progress_callback=lambda v: self.root.after(
                    0, lambda x=v: self.progress.set(10 + x * 0.90)
                ),
                status_callback=lambda message: self.root.after(
                    0, lambda m=message: self.status.set(m)
                ),
            )

            self.root.after(0, lambda r=result: self._show_pipeline_result(r))
            self.root.after(0, lambda: self.status.set("Local identification complete."))

        except Exception as exc:
            message = str(exc)
            self.root.after(0, lambda m=message: self._error(m))
        finally:
            self.root.after(0, lambda: self.identify_button.config(state="normal"))

    def _show_pipeline_result(self, result):
        candidates = result.get("candidates", [])
        best = candidates[0] if candidates else None

        if best:
            details = best
            try:
                token = self.settings.get("tmdb_bearer_token", "").strip()
                api_key = self.settings.get("tmdb_api_key", "").strip()
                if token or api_key:
                    details = TMDBClient(token=token, api_key=api_key).get_movie(best["id"])
            except Exception:
                details = best

            self.result_vars["title"].set(details.get("title") or "-")
            self.result_vars["year"].set(details.get("year") or "-")
            self.result_vars["director"].set(details.get("director") or "-")
            self.result_vars["genre"].set(", ".join(details.get("genres", [])) or "-")
            self.result_vars["runtime"].set(
                f"{details.get('runtime')} min" if details.get("runtime") else "-"
            )
            self.result_vars["rating"].set(
                str(details.get("rating")) if details.get("rating") is not None else "-"
            )
            self.result_vars["tmdb_id"].set(str(details.get("id") or "-"))
            movie_id = best.get("id")
            self.best_tmdb_url = (
                f"https://www.themoviedb.org/movie/{movie_id}" if movie_id else ""
            )
            self.best_imdb_url = best.get("imdb_url") or ""
            self.tmdb_link_button.config(
                state="normal" if self.best_tmdb_url else "disabled"
            )
            self.imdb_link_button.config(
                state="normal" if self.best_imdb_url else "disabled"
            )

            self.synopsis.config(state="normal")
            self.synopsis.delete("1.0", "end")
            self.synopsis.insert("1.0", details.get("overview", ""))
            self.synopsis.config(state="disabled")

        lines = []
        lines.append("LOCAL IDENTIFICATION EVIDENCE")
        lines.append("=" * 70)
        lines.append("")
        lines.append("FILE NAME CLUES:")
        lines.append(result.get("filename") or "(unknown)")
        for clue in result.get("filename_clues", []):
            lines.append("  • " + clue)
        lines.append("")
        lines.append("OPENING CREDITS SNAPSHOT OCR:")
        lines.append(result.get("credit_ocr_text") or "(no credit snapshot supplied / no text detected)")
        lines.append("")
        lines.append("SUBTITLES:")
        sources = result.get("subtitle_sources", [])
        lines.append("Sources: " + (", ".join(sources) if sources else "(no text subtitles found)"))
        lines.append(result.get("subtitle_text") or "(no subtitle text extracted)")
        lines.append("")
        lines.append("MOVIE FRAME OCR:")
        lines.append(result.get("ocr_text") or "(no text detected)")
        lines.append("")
        lines.append("SAMPLED SPEECH:")
        lines.append(result.get("speech_text") or "(no speech detected)")
        lines.append("")
        lines.append("Detected language: " + (result.get("speech_language") or "unknown"))
        lines.append("")
        lines.append("TMDB SEARCH PHRASES:")
        lines.extend("  • " + x for x in result.get("tmdb_queries", []))
        lines.append("")
        lines.append("IMDB CROSS-CHECKS:")
        imdb_matches = result.get("imdb_matches", [])
        if imdb_matches:
            lines.extend(
                f"  • {item.get('title') or 'Unknown'} ({item.get('year') or '?'}) "
                f"[{item.get('imdb_id')}]"
                for item in imdb_matches
            )
        else:
            lines.append("  (No IMDb references found or web search unavailable.)")
        lines.append("")
        lines.append("CANDIDATES:")
        for i, candidate in enumerate(candidates[:10], start=1):
            visual = candidate.get("visual_score")
            visual_text = f"{visual:.1f}%" if visual is not None else "not scored"
            lines.append(
                f"{i}. {candidate.get('title')} ({candidate.get('year') or '?'}) "
                f"| Visual similarity: {visual_text}"
                f"{' | IMDb confirmed' if candidate.get('imdb_evidence') else ''}"
            )

        self.evidence.config(state="normal")
        self.evidence.delete("1.0", "end")
        self.evidence.insert("1.0", "\n".join(lines))
        self.evidence.config(state="disabled")

    def _show_video_info(self, info):
        for key in (
            "file_name", "file_size", "format_name", "duration",
            "video_codec", "audio_codec", "video_bitrate", "audio_bitrate"
        ):
            self.info_vars[key].set(str(info.get(key, "Unknown")))
        self.info_vars["resolution"].set(
            f"{info.get('width', '?')} × {info.get('height', '?')}"
        )

    def _show_frames(self, frames):
        self._clear_gallery()
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return

        columns = 4
        for pos, frame in enumerate(frames):
            image = Image.open(frame["path"])
            image.thumbnail((220, 145))
            photo = ImageTk.PhotoImage(image)
            self.frame_images.append(photo)

            card = ttk.Frame(self.gallery_frame, relief="solid", borderwidth=1, padding=6)
            card.grid(row=pos // columns, column=pos % columns, padx=8, pady=8, sticky="nsew")
            ttk.Label(card, image=photo).pack()
            ttk.Label(
                card,
                text=f"Frame {frame['index']} | {frame['percentage']:.1f}%\n"
                     f"Time: {self._format_seconds(frame['timestamp'])}",
                justify="center"
            ).pack(pady=(5, 0))
            self.frame_cards.append(card)

        for col in range(columns):
            self.gallery_frame.columnconfigure(col, weight=1)

    @staticmethod
    def _format_seconds(seconds):
        seconds = int(seconds)
        return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

    def _clear_gallery(self):
        for widget in self.gallery_frame.winfo_children():
            widget.destroy()
        self.frame_images.clear()
        self.frame_cards.clear()

    def _clear_results(self):
        self.best_tmdb_url = ""
        self.best_imdb_url = ""
        if hasattr(self, "tmdb_link_button"):
            self.tmdb_link_button.config(state="disabled")
        if hasattr(self, "imdb_link_button"):
            self.imdb_link_button.config(state="disabled")
        for var in self.info_vars.values():
            var.set("-")
        for var in self.result_vars.values():
            var.set("-")
        for widget in (self.synopsis, self.evidence):
            widget.config(state="normal")
            widget.delete("1.0", "end")
            widget.config(state="disabled")

    def _open_result_url(self, url, source):
        if not url.startswith("https://"):
            return
        try:
            webbrowser.open_new_tab(url)
            self.status.set(f"Opened {source} in your browser.")
        except Exception as exc:
            messagebox.showerror("Movie Identifier", f"Could not open {source}: {exc}")

    def open_tmdb_page(self):
        self._open_result_url(self.best_tmdb_url, "TMDB")

    def open_imdb_page(self):
        self._open_result_url(self.best_imdb_url, "IMDb")

    def _error(self, message):
        self.progress.set(0)
        self.status.set("Error.")
        messagebox.showerror("Movie Identifier", message)

    def open_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Movie Identifier — Settings")
        dialog.geometry("650x570")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Local Analysis", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(frame, text="Whisper model:").grid(row=1, column=0, sticky="w", pady=6)
        whisper_var = tk.StringVar(value=self.settings.get("whisper_model", "base"))
        ttk.Combobox(frame, textvariable=whisper_var, values=["base", "small"],
                     state="readonly", width=28).grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(frame, text="Frames to analyze:").grid(row=2, column=0, sticky="w", pady=6)
        frames_var = tk.IntVar(value=self.settings.get("frames_to_analyze", 6))
        ttk.Spinbox(frame, from_=2, to=12, textvariable=frames_var, width=10).grid(
            row=2, column=1, sticky="w", pady=6)

        visual_var = tk.BooleanVar(value=self.settings.get("use_visual_embeddings", False))
        ttk.Checkbutton(frame, text="Enable local visual embeddings (CLIP)",
                        variable=visual_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 6))
        ttk.Label(frame, text=(
            "Recommended for the first test: leave CLIP disabled.\n"
            "CLIP downloads a large local model and will be tested after OCR + speech + TMDB work."
        ), wraplength=560).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Separator(frame).grid(row=5, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(frame, text="TMDB", font=("Segoe UI", 12, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttk.Label(frame, text="API Read Access Token:").grid(row=7, column=0, sticky="nw", pady=6)
        token_var = tk.StringVar(value=self.settings.get("tmdb_bearer_token", ""))
        ttk.Entry(frame, textvariable=token_var, show="•", width=52).grid(
            row=7, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text=(
            "Enter the TMDB API Read Access Token (Bearer token). "
            "It is stored locally in settings.json beside main.py in this development version."
        ), wraplength=560).grid(row=8, column=0, columnspan=2, sticky="w", pady=(2, 8))
        ttk.Label(frame, text=f"Configuration file: {self.settings_store.location()}",
                  wraplength=560).grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 8))
        ttk.Button(frame, text="Open Configuration Folder",
                   command=lambda: os.startfile(str(self.settings_store.path.parent))).grid(
            row=10, column=0, sticky="w", pady=(0, 8))

        status = tk.StringVar(value="Not tested")
        ttk.Label(frame, textvariable=status, wraplength=560).grid(
            row=11, column=0, columnspan=2, sticky="w", pady=8)
        buttons = ttk.Frame(frame)
        buttons.grid(row=12, column=0, columnspan=2, sticky="e", pady=(16, 0))

        def set_test_status(message):
            """Update the dialog only while it remains open."""
            if dialog.winfo_exists():
                status.set(message)

        def finish_test():
            # The user can close Settings while its background test is running.
            if dialog.winfo_exists():
                test_button.config(state="normal")

        def test_tmdb():
            token = token_var.get().strip()
            if not token:
                status.set("✗ TMDB token is empty.")
                return
            test_button.config(state="disabled")
            status.set("Testing TMDB connection...")
            def worker():
                try:
                    result = TMDBService(token).test_connection()
                    self.root.after(0, lambda r=result: set_test_status("✓ " + r))
                except Exception as exc:
                    msg = str(exc)
                    self.root.after(0, lambda m=msg: set_test_status("✗ " + m))
                finally:
                    self.root.after(0, finish_test)
            threading.Thread(target=worker, daemon=True).start()

        def save_settings():
            try:
                count = max(2, min(int(frames_var.get()), 12))
            except (tk.TclError, TypeError, ValueError):
                messagebox.showerror("Settings", "Frames to analyze must be a number.")
                return
            self.settings.update({
                "tmdb_bearer_token": token_var.get().strip(),
                "whisper_model": whisper_var.get(),
                "frames_to_analyze": count,
                "use_visual_embeddings": bool(visual_var.get()),
            })
            try:
                self.settings_store.save(self.settings)
            except (OSError, TypeError, ValueError) as exc:
                messagebox.showerror(
                    "Settings",
                    f"Could not save settings.json: {exc}",
                )
                return
            if not self.settings_store.path.exists():
                messagebox.showerror("Settings", "Settings file could not be created.")
                return
            dialog.destroy()

        test_button = ttk.Button(buttons, text="Test TMDB Connection", command=test_tmdb)
        test_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", command=save_settings).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    MovieIdentifierApp().run()
