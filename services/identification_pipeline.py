class LocalIdentificationPipeline:
    """Local movie-identification pipeline with optional CLIP."""

    def __init__(self, ocr_service, speech_sampler, speech_service, tmdb_client, candidate_engine, visual_embedder=None, subtitle_service=None):
        self.ocr = ocr_service
        self.speech_sampler = speech_sampler
        self.speech = speech_service
        self.tmdb = tmdb_client
        self.candidates = candidate_engine
        self.visual = visual_embedder
        self.subtitles = subtitle_service

    def run(self, video_path, video_info, frames, filename="", credit_text="", credit_snapshot_paths=None, progress_callback=None, status_callback=None):
        def status(text):
            if status_callback:
                status_callback(text)

        # 0-5 subtitles. This is optional because many files have no text track.
        status("Subtitles: checking embedded and sidecar subtitle tracks...")
        try:
            subtitle_result = self.subtitles.extract(video_path) if self.subtitles else {"text": "", "sources": []}
        except Exception:
            # Subtitle evidence is an enhancement, never a reason to stop the
            # primary OCR/speech/TMDB identification flow.
            subtitle_result = {"text": "", "sources": []}
        subtitle_text = subtitle_result["text"]
        if progress_callback:
            progress_callback(5)

        # 0-25 OCR
        status(f"OCR: analyzing {len(frames)} representative frames...")
        ocr_parts = []
        for index, frame in enumerate(frames, start=1):
            status(f"OCR: frame {index} of {len(frames)}")
            text = self.ocr.extract_text(frame["path"])
            if text:
                ocr_parts.append(text)
            if progress_callback:
                progress_callback(5 + index / len(frames) * 20)
        ocr_text = "\n".join(ocr_parts)

        # 25-60 speech
        status("Speech: preparing 6 audio samples...")
        samples = self.speech_sampler.extract_samples(video_path, video_info, count=6, seconds=30)
        status("Speech: loading Faster-Whisper model (first run may take several minutes)...")
        def speech_progress(v):
            sample = max(1, min(6, int((v / 100) * 6 + 0.999)))
            status(f"Speech: processing sample {sample} of 6")
            if progress_callback:
                progress_callback(25 + v * 0.35)
        speech_result = self.speech.transcribe_samples(samples, progress_callback=speech_progress)
        speech_text = speech_result["text"]

        # 60-80 TMDB
        status("TMDB: generating candidate movie searches...")
        candidates, queries, filename_clues, imdb_matches = self.candidates.generate_candidates(
            ocr_text, speech_text,
            filename=filename,
            credit_text=credit_text,
            subtitle_text=subtitle_text,
            status_callback=status,
        )
        if progress_callback:
            progress_callback(80)

        # 80-100 optional CLIP
        if self.visual is None:
            status("Local visual matching is disabled; ranking by TMDB candidates.")
            scored = [{**c, "visual_score": None} for c in candidates]
            if progress_callback:
                progress_callback(100)
        else:
            status("Visual matching: loading local CLIP model...")
            scored = self._visual_score(candidates, frames, progress_callback, status)

        return {
            "ocr_text": ocr_text,
            "credit_ocr_text": credit_text,
            "credit_snapshot_paths": credit_snapshot_paths or [],
            "subtitle_text": subtitle_text,
            "subtitle_sources": subtitle_result["sources"],
            "filename": filename,
            "filename_clues": filename_clues,
            "speech_text": speech_text,
            "speech_language": speech_result["language"],
            "tmdb_queries": queries,
            "imdb_matches": imdb_matches,
            "candidates": scored,
        }

    def _visual_score(self, candidates, frames, progress_callback, status):
        if not candidates or self.visual is None:
            return [{**c, "visual_score": None} for c in candidates]
        try:
            import requests
            from PIL import Image
            from io import BytesIO
        except ImportError:
            return [{**c, "visual_score": None} for c in candidates]

        valid = []
        for candidate in candidates[:10]:
            url = candidate.get("backdrop_url") or candidate.get("poster_url")
            if not url:
                continue
            try:
                status(f"Visual matching: downloading candidate image for {candidate.get('title','Unknown')}...")
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                image = Image.open(BytesIO(response.content)).convert("RGB")
                valid.append((candidate, image))
            except Exception:
                continue

        if not valid:
            return [{**c, "visual_score": None} for c in candidates]

        import tempfile
        from pathlib import Path
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                paths=[]
                for i,(_,image) in enumerate(valid):
                    path=Path(temp_dir)/f"candidate_{i}.jpg"
                    image.save(path,"JPEG",quality=80)
                    paths.append(path)
                status("Visual matching: embedding movie screenshots and candidates...")
                ce=self.visual.embed_images(paths)
                fe=self.visual.embed_images([x["path"] for x in frames[:6]])
                similarity=self.visual.cosine_similarity(fe,ce)
                result=[]
                for j,(candidate,_) in enumerate(valid):
                    vals=sorted(similarity[:,j].tolist(),reverse=True)[:3]
                    score=sum(vals)/len(vals)
                    result.append({**candidate,"visual_score":round(max(0,min(1,score))*100,1)})
                used={x["id"] for x in result}
                result.extend({**c,"visual_score":None} for c in candidates if c["id"] not in used)
                result.sort(key=lambda x:x["visual_score"] if x["visual_score"] is not None else -1,reverse=True)
                if progress_callback: progress_callback(100)
                return result
        except Exception:
            return [{**c,"visual_score":None} for c in candidates]
