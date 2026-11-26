"""Optional local text encoder shared by matching and offline evaluation."""

from pathlib import Path
from threading import Lock
from typing import Sequence


class TextEncoder:
    def __init__(self, directory: Path):
        directory = directory.resolve()
        if not (directory / "model.safetensors").is_file():
            raise ValueError("The local text model must contain model.safetensors")
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            str(directory), device="cpu", local_files_only=True, trust_remote_code=False,
            model_kwargs={"use_safetensors": True},
        )
        self.lock = Lock()

    def encode(self, strings: Sequence[str]):
        with self.lock:
            return self.model.encode(list(strings), normalize_embeddings=True, convert_to_numpy=True)

    def similarities(self, query: str, documents: Sequence[str]) -> list[float]:
        vectors = self.encode([query, *documents])
        return (vectors[1:] @ vectors[0]).clip(0, 1).tolist()
