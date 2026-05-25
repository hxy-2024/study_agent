import hashlib
import math
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("Embedding dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        normalized = " ".join(text.lower().split())
        values: list[float] = []
        for index in range(self._dimension):
            digest = hashlib.sha256(f"{index}:{normalized}".encode("utf-8")).digest()
            integer = int.from_bytes(digest[:8], "big", signed=False)
            values.append((integer / ((1 << 64) - 1)) * 2.0 - 1.0)
        length = math.sqrt(sum(value * value for value in values))
        if length == 0:
            return [0.0 for _ in values]
        return [value / length for value in values]
