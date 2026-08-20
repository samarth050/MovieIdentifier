import shutil
import subprocess
from pathlib import Path


class SpeechSampler:
    """
    Extract a small number of audio clips spread across the movie.

    Default: six 30-second clips. This avoids transcribing the whole movie
    during identification.
    """

    def __init__(self, output_root="audio_samples"):
        self.output_root = Path(output_root)

    @staticmethod
    def _duration_seconds(duration_text):
        h, m, s = [float(x) for x in duration_text.split(":")]
        return h * 3600 + m * 60 + s

    def extract_samples(self, video_path, video_info, count=6, seconds=30):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg was not found on PATH.")

        duration = self._duration_seconds(video_info["duration"])
        count = max(2, min(int(count), 10))
        seconds = max(10, min(int(seconds), 60))

        if duration < seconds + 10:
            count = 2

        # Avoid first/last few percent where logos/credits are common.
        positions = [
            0.08 + (0.84 * i / (count - 1))
            for i in range(count)
        ]

        movie_dir = self.output_root / Path(video_path).stem
        movie_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for index, pct in enumerate(positions, start=1):
            start = max(0, duration * pct)
            out = movie_dir / f"speech_{index:02d}.wav"

            cmd = [
                ffmpeg, "-hide_banner", "-loglevel", "error",
                "-ss", str(start),
                "-i", str(video_path),
                "-t", str(seconds),
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-c:a", "pcm_s16le",
                "-y", str(out),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0 or not out.exists():
                raise RuntimeError(
                    f"Could not extract audio sample {index}: "
                    + (result.stderr.strip() or "unknown FFmpeg error")
                )

            results.append({
                "index": index,
                "percentage": pct * 100,
                "start": start,
                "duration": seconds,
                "path": str(out.resolve()),
            })

        return results
