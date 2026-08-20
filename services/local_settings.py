import json
from pathlib import Path


class LocalSettings:
    """Persistent development settings stored beside main.py."""

    def __init__(self, path=None):
        project_root = Path(__file__).resolve().parents[1]
        self.path = Path(path) if path else project_root / "settings.json"

    def load(self):
        defaults = {
            "tmdb_bearer_token": "",
            "tmdb_api_key": "",
            "whisper_model": "base",
            "whisper_device": "cpu",
            "whisper_compute_type": "int8",
            "use_visual_embeddings": False,
            "ocr_enabled": True,
            "speech_enabled": True,
            "frames_to_analyze": 6,
        }
        if not self.path.exists():
            return defaults
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return defaults

        # Migrate earlier development versions automatically.
        if not data.get("tmdb_bearer_token") and data.get("tmdb_token"):
            data["tmdb_bearer_token"] = data["tmdb_token"]

        defaults.update({k: data[k] for k in defaults if k in data})
        return defaults

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        clean = {
            "tmdb_bearer_token": data.get("tmdb_bearer_token", ""),
            "tmdb_api_key": data.get("tmdb_api_key", ""),
            "whisper_model": data.get("whisper_model", "base"),
            "whisper_device": data.get("whisper_device", "cpu"),
            "whisper_compute_type": data.get("whisper_compute_type", "int8"),
            "use_visual_embeddings": bool(data.get("use_visual_embeddings", False)),
            "ocr_enabled": bool(data.get("ocr_enabled", True)),
            "speech_enabled": bool(data.get("speech_enabled", True)),
            "frames_to_analyze": int(data.get("frames_to_analyze", 6)),
        }
        self.path.write_text(json.dumps(clean, indent=2), encoding="utf-8")

    def location(self):
        return str(self.path)
