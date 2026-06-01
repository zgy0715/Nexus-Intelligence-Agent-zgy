from langchain_ollama import OllamaEmbeddings

from nia.utils.config import Config


class EmbeddingManager:
    def __init__(self):
        self._embeddings = OllamaEmbeddings(
            base_url=Config.OLLAMA_BASE_URL,
            model=Config.OLLAMA_EMBED_MODEL,
        )

    def embed_text(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if end < len(text):
                last_period = chunk.rfind("。")
                last_newline = chunk.rfind("\n")
                last_space = chunk.rfind(" ")
                split_pos = max(last_period, last_newline, last_space)
                if split_pos > start + chunk_size // 2:
                    chunk = text[start : start + split_pos + 1]
                    end = start + split_pos + 1
            chunks.append(chunk.strip())
            start = end - overlap
            if start <= end - chunk_size:
                start = end
        return [c for c in chunks if c]
