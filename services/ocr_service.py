import re
from pathlib import Path

import cv2
import pytesseract


class OCRService:
    """Local OCR using Tesseract. No cloud API required."""

    def __init__(self, tesseract_cmd=None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract_text(self, image_path):
        image = cv2.imread(str(image_path))
        if image is None:
            return ""

        # Upscale and preprocess to improve subtitles/title/credit recognition.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scale = 2
        gray = cv2.resize(
            gray, None, fx=scale, fy=scale,
            interpolation=cv2.INTER_CUBIC
        )
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        threshold = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]

        text1 = pytesseract.image_to_string(gray, config="--psm 6")
        text2 = pytesseract.image_to_string(
            threshold, config="--psm 6"
        )

        return self._clean(text1 + "\n" + text2)

    @staticmethod
    def _clean(text):
        lines = []
        seen = set()
        for raw in text.splitlines():
            line = re.sub(r"\s+", " ", raw).strip()
            if len(line) < 2:
                continue
            key = line.lower()
            if key not in seen:
                seen.add(key)
                lines.append(line)
        return "\n".join(lines)
