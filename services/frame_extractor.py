import subprocess
import shutil
from pathlib import Path


class FrameExtractor:
    """Extract representative frames from a video using FFmpeg."""

    def __init__(self, output_root="frames"):
        self.output_root = Path(output_root)

    def extract_representative_frames(self, video_path, count=12, progress_callback=None):
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(
                "FFmpeg was not found on PATH. Install FFmpeg and restart VS Code."
            )

        # Get duration through ffprobe so extraction can use exact timestamps.
        from utils.ffmpeg_utils import probe_video
        info = probe_video(video_path)

        duration_text = info.get("duration", "00:00:00")
        h, m, s = [float(x) for x in duration_text.split(":")]
        duration = h * 3600 + m * 60 + s

        if duration <= 0:
            raise RuntimeError("Unable to determine video duration.")

        count = max(4, min(int(count), 30))

        # Avoid the very beginning/end where logos, fade-ins and credits
        # are more common. The exact positions are configurable later.
        percentages = [
            0.05 + (0.90 * i / (count - 1))
            for i in range(count)
        ]

        output_dir = self.output_root / video_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)

        # Remove previous generated frames for this video.
        for old in output_dir.glob("frame_*.jpg"):
            try:
                old.unlink()
            except OSError:
                pass

        frames = []

        for index, percentage in enumerate(percentages, start=1):
            timestamp = duration * percentage
            output_file = output_dir / f"frame_{index:02d}.jpg"

            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "error",
                "-ss", str(timestamp),
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                "-y",
                str(output_file),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0 or not output_file.exists():
                raise RuntimeError(
                    f"Could not extract frame {index}: "
                    + (result.stderr.strip() or "unknown FFmpeg error")
                )

            frames.append({
                "index": index,
                "percentage": percentage * 100,
                "timestamp": timestamp,
                "path": str(output_file.resolve()),
            })

            if progress_callback:
                progress_callback(index / count * 100)

        return frames
