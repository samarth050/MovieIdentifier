import base64
import io
import json
import os

from PIL import Image
from openai import OpenAI


class VisionMovieIdentifier:
    """Efficient vision-based movie identification."""

    DEFAULT_MODEL = "gpt-5.6"

    def __init__(self, model=None, max_image_width=1280, jpeg_quality=75):
        self.model = model or self.DEFAULT_MODEL
        self.max_image_width = max_image_width
        self.jpeg_quality = jpeg_quality

    @staticmethod
    def _get_api_key():
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Open Settings and configure the API key."
            )
        return key

    def _encode_image(self, path):
        """Resize/recompress a frame before sending it to reduce API usage."""
        with Image.open(path) as image:
            image = image.convert("RGB")

            if image.width > self.max_image_width:
                ratio = self.max_image_width / image.width
                new_size = (
                    self.max_image_width,
                    max(1, int(image.height * ratio)),
                )
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            image.save(
                buffer,
                format="JPEG",
                quality=self.jpeg_quality,
                optimize=True,
            )

        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    def test_connection(self):
        """Perform a small text-only API request to verify credentials/access."""
        client = OpenAI(api_key=self._get_api_key())

        try:
            response = client.responses.create(
                model=self.model,
                input="Reply with exactly: API connection OK",
                max_output_tokens=20,
            )
            return response.output_text.strip()
        except Exception as exc:
            raise RuntimeError(f"API connection test failed: {exc}") from exc

    @staticmethod
    def _extract_json(text):
        text = (text or "").strip()

        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
            raise

    def identify_from_frames(
        self,
        frames,
        video_info=None,
        progress_callback=None,
    ):
        api_key = self._get_api_key()

        if not frames:
            raise RuntimeError("No representative frames were supplied.")

        client = OpenAI(api_key=api_key)

        duration = (video_info or {}).get("duration", "Unknown")
        resolution = (
            f"{(video_info or {}).get('width', '?')} x "
            f"{(video_info or {}).get('height', '?')}"
        )

        content = [{
            "type": "input_text",
            "text": f"""
Identify the movie shown in these representative screenshots.

The filename is intentionally not provided.

Video duration: {duration}
Video resolution: {resolution}
Screenshots supplied: {len(frames)}

Use all screenshots together. Look for actors, characters, locations,
costumes, props, title/credit text, subtitles, language, time period,
and visual continuity.

Do not invent a title. If the evidence is weak, return a low confidence.

Return ONLY valid JSON:

{{
  "best_match": {{
    "title": "",
    "year": null,
    "confidence": 0,
    "reason": ""
  }},
  "alternatives": [],
  "visual_clues": [],
  "detected_text": [],
  "language": "",
  "country_or_region": "",
  "identification_quality": "high|medium|low"
}}

Confidence: integer 0-100.
At most 3 alternative candidates.
""".strip()
        }]

        total = len(frames)

        for index, frame in enumerate(frames, start=1):
            content.append({
                "type": "input_image",
                "image_url": self._encode_image(frame["path"]),
                "detail": "low",
            })
            if progress_callback:
                progress_callback((index / total) * 50)

        try:
            response = client.responses.create(
                model=self.model,
                input=[{
                    "role": "user",
                    "content": content,
                }],
                max_output_tokens=1000,
            )
        except Exception as exc:
            raise RuntimeError(
                f"The vision-model request failed. OpenAI returned: {exc}"
            ) from exc

        if progress_callback:
            progress_callback(100)

        result = self._extract_json(response.output_text)
        result["_model"] = self.model
        result["_frames_sent"] = len(frames)
        result["_image_width_limit"] = self.max_image_width
        result["_jpeg_quality"] = self.jpeg_quality
        return result
