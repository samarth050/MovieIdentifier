from dataclasses import dataclass

@dataclass
class VideoInfo:
    file_name: str = ""
    file_size: str = ""
    format_name: str = ""
    duration: str = ""
    width: str = ""
    height: str = ""
    video_codec: str = ""
    audio_codec: str = ""
    video_bitrate: str = ""
    audio_bitrate: str = ""
