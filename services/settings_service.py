import json
from pathlib import Path

class SettingsService:
    def __init__(self, path="settings.json"):
        self.path = Path(path)

    def load(self):
        defaults = {"tmdb_token": "", "whisper_model": "base", "frames_to_analyze": 6}
        if not self.path.exists():
            return defaults
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        return {
            "tmdb_token": data.get("tmdb_token", ""),
            "whisper_model": data.get("whisper_model", "base"),
            "frames_to_analyze": int(data.get("frames_to_analyze", 6)),
        }

    def save(self, tmdb_token="", whisper_model="base", frames_to_analyze=6):
        self.path.write_text(json.dumps({
            "tmdb_token": tmdb_token,
            "whisper_model": whisper_model,
            "frames_to_analyze": int(frames_to_analyze),
        }, indent=2), encoding="utf-8")
