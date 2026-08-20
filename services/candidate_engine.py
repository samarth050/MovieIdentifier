import re
from collections import Counter
from pathlib import Path


class CandidateEngine:
    """Generate candidates using filename, opening-credit OCR, movie OCR and speech."""

    STOPWORDS = {
        "the", "and", "that", "this", "you", "your", "are", "was", "for",
        "with", "have", "has", "from", "they", "what", "but", "not", "all",
        "can", "will", "just", "into", "about", "then", "there", "here",
        "who", "how", "why", "where", "when", "been", "were", "his", "her",
        "him", "she", "them", "our", "out", "one", "two", "too", "get",
        "film", "movie", "production", "presents", "present", "starring", "directed",
        "produced", "written", "with", "music", "copyright", "all", "rights",
    }

    RELEASE_TOKENS = {
        "480p", "576p", "720p", "1080p", "2160p", "4k", "8k", "bluray", "brrip",
        "bdrip", "dvdrip", "web-dl", "webdl", "webrip", "hdrip", "hdtv", "remux",
        "x264", "x265", "h264", "h265", "hevc", "avc", "aac", "ac3", "dts",
        "proper", "repack", "remastered", "extended", "unrated", "directors", "director",
        "cut", "limited", "edition", "readnfo", "sample", "internal", "yify", "rarbg",
    }

    def __init__(self, tmdb_client, imdb_search=None):
        self.tmdb = tmdb_client
        self.imdb = imdb_search

    @classmethod
    def filename_clues(cls, filename):
        raw = Path(filename or "").stem
        normalized = re.sub(r"[._\-]+", " ", raw)
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", normalized)
        year = year_match.group(1) if year_match else ""
        title_part = normalized[:year_match.start()] if year_match else normalized
        words = []
        for word in title_part.split():
            low = word.lower()
            if low in cls.RELEASE_TOKENS:
                break
            words.append(word)
        title = re.sub(r"\s+", " ", " ".join(words)).strip(" -")
        if not title:
            title = re.sub(r"\s+", " ", normalized).strip()
        clues = []
        if title:
            clues.append(f"Normalized title: {title}")
        if year:
            clues.append(f"Year: {year}")
        return title, year, clues

    @classmethod
    def useful_phrases(cls, text, max_phrases=8):
        lines = [
            re.sub(r"\s+", " ", x).strip()
            for x in (text or "").splitlines()
            if x.strip()
        ]
        phrases = []
        for line in lines:
            words = line.split()
            if len(words) >= 2:
                phrases.append(line[:100])
        words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or "")
        words = [w for w in words if w.lower() not in cls.STOPWORDS]
        counts = Counter(w.lower() for w in words)
        distinctive = [w for w, _ in counts.most_common(20)]
        for i in range(len(distinctive) - 1):
            phrases.append(f"{distinctive[i]} {distinctive[i + 1]}")
        seen, output = set(), []
        for p in phrases:
            key = p.lower()
            if key not in seen and len(p) >= 3:
                seen.add(key)
                output.append(p)
            if len(output) >= max_phrases:
                break
        return output

    def generate_candidates(self, ocr_text, speech_text, filename="", credit_text="", subtitle_text="", max_candidates=20, status_callback=None):
        title, year, filename_clues = self.filename_clues(filename)
        phrases = []
        if title:
            phrases.append(title)
            if year:
                phrases.append(f"{title} {year}")
        # Opening credits are high-value evidence: put them ahead of generic speech.
        phrases.extend(self.useful_phrases(credit_text, max_phrases=4))
        phrases.extend(self.useful_phrases(subtitle_text, max_phrases=5))
        phrases.extend(self.useful_phrases(ocr_text, max_phrases=3))
        phrases.extend(self.useful_phrases(speech_text, max_phrases=3))

        seen, unique_phrases = set(), []
        for phrase in phrases:
            key = re.sub(r"\s+", " ", phrase).strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique_phrases.append(phrase)

        by_id = {}
        for index, phrase in enumerate(unique_phrases[:12], start=1):
            if status_callback:
                status_callback(f"Candidate search {index} of {min(12, len(unique_phrases))} — {phrase[:70]}")
            for movie in self.tmdb.search_movies(phrase, max_results=5):
                if movie.get("id"):
                    movie = dict(movie)
                    previous = by_id.get(movie["id"], {})
                    # A candidate may be found by several different clues.
                    # Preserve evidence from every query instead of letting a
                    # later, weaker query overwrite an earlier strong match.
                    movie["filename_match"] = previous.get("filename_match", False) or bool(
                        title and title.lower() in (movie.get("title") or "").lower()
                    )
                    movie["filename_year_match"] = previous.get("filename_year_match", False) or bool(
                        year and year == (movie.get("year") or "")
                    )
                    movie["credit_evidence"] = previous.get("credit_evidence", False) or bool(
                        credit_text and phrase in credit_text
                    )
                    movie["subtitle_evidence"] = previous.get("subtitle_evidence", False) or bool(
                        subtitle_text and phrase in subtitle_text
                    )
                    by_id[movie["id"]] = movie
                if len(by_id) >= max_candidates:
                    break
            if len(by_id) >= max_candidates:
                break

        imdb_matches = []
        if self.imdb:
            for index, phrase in enumerate(unique_phrases[:4], start=1):
                if status_callback:
                    status_callback(f"IMDb cross-check {index} of {min(4, len(unique_phrases))} — {phrase[:70]}")
                for imdb_match in self.imdb.search_movies(phrase, max_results=3):
                    if imdb_match["imdb_id"] not in {x["imdb_id"] for x in imdb_matches}:
                        imdb_matches.append(imdb_match)
                    try:
                        movie = self.tmdb.find_by_imdb_id(imdb_match["imdb_id"])
                    except Exception:
                        continue
                    if not movie or not movie.get("id"):
                        continue
                    previous = by_id.get(movie["id"], {})
                    movie["filename_match"] = previous.get("filename_match", False) or bool(
                        title and title.lower() in (movie.get("title") or "").lower()
                    )
                    movie["filename_year_match"] = previous.get("filename_year_match", False) or bool(
                        year and year == (movie.get("year") or "")
                    )
                    movie["credit_evidence"] = previous.get("credit_evidence", False)
                    movie["subtitle_evidence"] = previous.get("subtitle_evidence", False)
                    movie["imdb_evidence"] = True
                    movie["imdb_id"] = imdb_match["imdb_id"]
                    movie["imdb_url"] = imdb_match["url"]
                    by_id[movie["id"]] = movie

        results = list(by_id.values())
        for movie in results:
            score = 0.0
            if movie.get("filename_match"):
                score += 40
            if movie.get("filename_year_match"):
                score += 15
            if movie.get("credit_evidence"):
                score += 20
            if movie.get("subtitle_evidence"):
                score += 25
            if movie.get("imdb_evidence"):
                score += 35
            movie["candidate_score"] = score
        results.sort(key=lambda x: x.get("candidate_score", 0), reverse=True)
        return results, unique_phrases, filename_clues, imdb_matches
