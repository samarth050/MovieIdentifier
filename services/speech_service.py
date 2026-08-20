import time


class SpeechService:
    """Local sampled speech recognition using faster-whisper."""

    def __init__(self, model_name="base", device="cpu", compute_type="int8"):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: python -m pip install faster-whisper"
            ) from exc

        if self._model is None:
            # On the first run Faster-Whisper downloads the model.  Network
            # resets are common with larger files, so retry the whole model
            # construction before showing an actionable error to the user.
            last_error = None
            for attempt in range(1, 4):
                try:
                    self._model = WhisperModel(
                        self.model_name,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 3:
                        time.sleep(attempt)

            if self._model is None:
                raise RuntimeError(
                    "Could not download or load the Faster-Whisper model after "
                    "3 attempts. Check your internet connection, proxy, or firewall, "
                    "then try Analyze & Identify again. "
                    f"Details: {last_error}"
                ) from last_error
        return self._model

    def transcribe_samples(self, samples, progress_callback=None):
        model = self._load()
        all_text = []
        segments = []

        for index, sample in enumerate(samples, start=1):
            try:
                generated, info = model.transcribe(
                    sample["path"],
                    beam_size=3,
                    vad_filter=True,
                )
                generated = list(generated)
            except Exception as exc:
                raise RuntimeError(
                    f"Speech recognition failed for sample {index}: {exc}"
                ) from exc

            sample_text = " ".join(
                seg.text.strip() for seg in generated if seg.text.strip()
            ).strip()

            if sample_text:
                all_text.append(sample_text)

            segments.append({
                "sample": index,
                "start": sample["start"],
                "text": sample_text,
                "language": getattr(info, "language", ""),
            })

            if progress_callback:
                progress_callback(index / len(samples) * 100)

        return {
            "text": "\n".join(all_text),
            "segments": segments,
            "language": next(
                (x["language"] for x in segments if x["language"]), ""
            ),
        }
