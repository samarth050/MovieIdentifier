from utils.ffmpeg_utils import probe_video

class VideoAnalyzer:
    def analyze(self, path):
        return probe_video(path)
