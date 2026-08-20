import json
import shutil
import subprocess
from pathlib import Path

def find_ffprobe():
    return shutil.which("ffprobe")

def find_ffmpeg():
    return shutil.which("ffmpeg")

def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024**2:
        return f"{size/1024:.1f} KB"
    if size < 1024**3:
        return f"{size/1024**2:.1f} MB"
    return f"{size/1024**3:.2f} GB"

def format_duration(seconds):
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return "Unknown"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def probe_video(path):
    ffprobe = find_ffprobe()
    if not ffprobe:
        raise RuntimeError("FFprobe was not found on PATH. Install FFmpeg and add its bin folder to PATH.")

    cmd = [
        ffprobe, "-v", "error",
        "-show_entries",
        "format=format_name,duration,bit_rate:stream=index,codec_type,codec_name,width,height,bit_rate",
        "-of", "json",
        str(Path(path))
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "FFprobe could not read the video.")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

    return {
        "file_name": Path(path).name,
        "file_size": format_bytes(Path(path).stat().st_size),
        "format_name": fmt.get("format_name", "Unknown"),
        "duration": format_duration(fmt.get("duration")),
        "width": video.get("width", "Unknown"),
        "height": video.get("height", "Unknown"),
        "video_codec": video.get("codec_name", "Unknown"),
        "audio_codec": audio.get("codec_name", "None"),
        "video_bitrate": video.get("bit_rate", "Unknown"),
        "audio_bitrate": audio.get("bit_rate", "Unknown"),
    }
