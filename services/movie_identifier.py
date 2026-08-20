from services.vision_identifier import VisionMovieIdentifier


class MovieIdentifier:
    def __init__(self, model=None):
        self.vision = VisionMovieIdentifier(model=model)

    @property
    def model(self):
        return self.vision.model

    @model.setter
    def model(self, value):
        self.vision.model = value

    def test_connection(self):
        return self.vision.test_connection()

    def identify(self, frames, video_info=None, progress_callback=None):
        return self.vision.identify_from_frames(
            frames,
            video_info=video_info,
            progress_callback=progress_callback,
        )
