# MovieIdentifier — Step 2C

Step 2C adds high-value user supplied evidence to movie identification:

- Current movie filename is parsed and used as a candidate clue.
- One or more opening-credit screenshots can be uploaded (for example, VLCsnap images).
- Tesseract OCR extracts names, studio, director, actor, title and other credit text.
- Credit OCR is prioritized over generic movie-frame OCR and sampled speech when generating candidate searches.
- Existing representative-frame gallery is retained.
- TMDB remains a candidate source; other Step 2C source adapters can consume the same candidate clues.

## Recommended workflow

1. Browse for the movie file.
2. Add one or more opening-credit snapshots.
3. Run Analyze & Identify.
4. Review Filename Clues and Opening Credits OCR in the Evidence tab.
5. Enable CLIP later for visual verification.

The snapshots are not copied or uploaded by this feature; their local paths are passed to Tesseract OCR.
