from langchain_core.messages import HumanMessage, SystemMessage

from nia.ai.ollama_client import OllamaClient
from nia.rag.embedding import EmbeddingManager
from nia.rag.vector_store import VectorStore


class RAGEngine:
    def __init__(self):
        self._embedding_manager = EmbeddingManager()
        self._vector_store = VectorStore()
        self._ollama_client = OllamaClient()

    def index_data(
        self, url: str, title: str, content: str, crawled_data_id: str
    ) -> None:
        chunks = self._embedding_manager.chunk_text(content)
        if not chunks:
            return
        embeddings = self._embedding_manager.embed_texts(chunks)
        self._vector_store.delete_vectors(crawled_data_id)
        self._vector_store.add_vectors(
            crawled_data_id, chunks, embeddings, url=url, title=title
        )

    def query(self, question: str) -> dict:
        query_embedding = self._embedding_manager.embed_text(question)
        search_results = self._vector_store.similarity_search(query_embedding, top_k=5)

        if not search_results:
            return {
                "answer": "未找到相关内容，请尝试其他问题。",
                "sources": [],
            }

        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(
                f"[来源{i}] URL: {result['url']}\n标题: {result['title']}\n内容: {result['content_chunk']}"
            )
        context = "\n\n".join(context_parts)

        messages = [
            SystemMessage(
                content="你是一个智能问答助手。请根据提供的参考内容回答用户的问题。"
                "如果参考内容中没有相关信息，请明确说明。"
                "回答时请引用来源编号，例如[来源1]。"
            ),
            HumanMessage(
                content=f"参考内容:\n\n{context}\n\n用户问题: {question}"
            ),
        ]

        answer = self._ollama_client.chat(messages, temperature=0.3)

        sources = []
        seen_ids = set()
        for result in search_results:
            crawled_data_id = result["crawled_data_id"]
            if crawled_data_id not in seen_ids:
                seen_ids.add(crawled_data_id)
                snippet = result["content_chunk"]
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                sources.append(
                    {
                        "url": result["url"],
                        "title": result["title"],
                        "content_snippet": snippet,
                    }
                )

        return {
            "answer": answer,
            "sources": sources,
        }
