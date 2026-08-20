class LocalVisualEmbedder:
    """
    Local CLIP image embedding.

    The model is downloaded once by Hugging Face and then cached locally.
    No image is sent to a cloud service.
    """

    MODEL_NAME = "openai/clip-vit-base-patch32"

    def __init__(self, model_name=None):
        self.model_name = model_name or self.MODEL_NAME
        self.processor = None
        self.model = None

    def _load(self):
        if self.model is not None:
            return

        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Local visual embedding dependencies are missing. "
                "Install torch and transformers."
            ) from exc

        self.processor = CLIPProcessor.from_pretrained(
            self.model_name
        )
        self.model = CLIPModel.from_pretrained(
            self.model_name
        )
        self.model.eval()

    def embed_images(self, image_paths):
        self._load()

        import torch
        from PIL import Image

        images = []
        for path in image_paths:
            with Image.open(path) as image:
                images.append(image.convert("RGB"))

        inputs = self.processor(
            images=images,
            return_tensors="pt",
        )

        with torch.no_grad():
            features = self.model.get_image_features(**inputs)

        features = features / features.norm(
            p=2, dim=-1, keepdim=True
        )
        return features.cpu()

    @staticmethod
    def cosine_similarity(a, b):
        import torch
        a = a / a.norm(p=2, dim=-1, keepdim=True)
        b = b / b.norm(p=2, dim=-1, keepdim=True)
        return torch.mm(a, b.T)
