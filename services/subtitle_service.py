import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class SubtitleService:
    """Read local and embedded text subtitles without requiring an online API."""

    SIDECAR_EXTENSIONS = (".srt", ".vtt", ".ass", ".ssa", ".sub", ".txt")
    TEXT_SUBTITLE_CODECS = {"ass", "mov_text", "subrip", "text", "webvtt"}

    def __init__(self, max_characters=12000, max_embedded_tracks=2):
        self.max_characters = max_characters
        self.max_embedded_tracks = max_embedded_tracks

    def extract(self, video_path):
        """Return normalized text and the local subtitle sources that produced it.

        Missing subtitles and bitmap-only subtitle tracks are normal and are not
        errors; frame OCR remains the fallback for those videos.
        """
        path = Path(video_path)
        parts, sources = [], []

        for sidecar in self._sidecar_files(path):
            text = self._read_text_file(sidecar)
            if text:
                parts.append(text)
                sources.append(sidecar.name)

        for label, text in self._embedded_tracks(path):
            if text:
                parts.append(text)
                sources.append(label)

        text = self._combine(parts)
        return {"text": text, "sources": sources}

    def _sidecar_files(self, video_path):
        files = []
        seen = set()
        for extension in self.SIDECAR_EXTENSIONS:
            candidate = video_path.with_suffix(extension)
            if candidate.exists() and candidate.is_file():
                key = candidate.resolve()
                if key not in seen:
                    seen.add(key)
                    files.append(candidate)
        return files

    def _embedded_tracks(self, video_path):
        ffprobe = shutil.which("ffprobe")
        ffmpeg = shutil.which("ffmpeg")
        if not ffprobe or not ffmpeg:
            return []

        try:
            probe = subprocess.run(
                [
                    ffprobe, "-v", "error", "-select_streams", "s",
                    "-show_entries", "stream=index,codec_name:stream_tags=language,title",
                    "-of", "json", str(video_path),
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=20,
                check=False,
            )
            if probe.returncode != 0:
                return []
            import json
            streams = json.loads(probe.stdout).get("streams", [])
        except (OSError, ValueError, subprocess.SubprocessError):
            return []

        text_streams = [
            stream for stream in streams
            if stream.get("codec_name") in self.TEXT_SUBTITLE_CODECS
        ][:self.max_embedded_tracks]
        output = []
        with tempfile.TemporaryDirectory(prefix="movie_identifier_subtitles_") as temp_dir:
            for number, stream in enumerate(text_streams, start=1):
                output_path = Path(temp_dir) / f"track_{number}.srt"
                try:
                    result = subprocess.run(
                        [
                            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(video_path), "-map", f"0:{stream['index']}",
                            str(output_path),
                        ],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=60,
                        check=False,
                    )
                except (OSError, subprocess.SubprocessError):
                    continue
                if result.returncode != 0 or not output_path.exists():
                    continue
                text = self._read_text_file(output_path)
                tags = stream.get("tags") or {}
                language = tags.get("language") or "unknown language"
                title = tags.get("title")
                label = f"Embedded subtitle ({language}{': ' + title if title else ''})"
                if text:
                    output.append((label, text))
        return output

    def _read_text_file(self, path):
        try:
            raw = Path(path).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return ""
        return self._clean(raw)

    def _clean(self, text):
        lines, seen = [], set()
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.isdigit() or "-->" in line:
                continue
            if line.startswith(("[Script Info]", "[V4+ Styles]", "[Events]", "Format:")):
                continue
            if line.startswith("Dialogue:"):
                # ASS dialogue metadata occupies the first nine comma-separated fields.
                fields = line.split(",", 9)
                line = fields[-1] if len(fields) == 10 else ""
            line = re.sub(r"\{[^}]*\}", "", line)
            line = re.sub(r"<[^>]+>", "", line)
            line = html.unescape(line.replace("\\N", " ").replace("\\n", " "))
            line = re.sub(r"\s+", " ", line).strip()
            key = line.casefold()
            if len(line) >= 2 and key not in seen:
                seen.add(key)
                lines.append(line)
        return "\n".join(lines)

    def _combine(self, parts):
        output, seen, remaining = [], set(), self.max_characters
        for part in parts:
            for line in part.splitlines():
                key = line.casefold()
                if key in seen:
                    continue
                if len(line) + 1 > remaining:
                    return "\n".join(output)
                seen.add(key)
                output.append(line)
                remaining -= len(line) + 1
        return "\n".join(output)
