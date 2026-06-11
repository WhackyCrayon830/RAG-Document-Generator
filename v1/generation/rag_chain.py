"""
RAG chain - combines retrieval context with LLM generation.
Supports chat mode with source citations and fallback reasoning.
"""
import logging
from typing import Generator, List, Optional

from retrieval.retriever import Retriever, RetrievedChunk

logger = logging.getLogger(__name__)


def build_rag_prompt(
    query: str,
    context: str,
    system_prompt: str,
    chat_history: List[dict] = None,
    has_context: bool = True,
) -> str:
    """Build the full prompt for RAG."""
    history_str = ""
    if chat_history:
        for msg in chat_history[-6:]:  # Last 3 turns
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_str += f"\n{role.capitalize()}: {content}"

    if has_context:
        return f"""{system_prompt}

### Retrieved Context:
{context}

### Conversation History:{history_str}

### Current Question:
{query}

### Answer (cite sources using [Source N] notation):"""
    else:
        return f"""{system_prompt}

NOTE: No relevant documents found in the knowledge base for this question.
Please answer using your general knowledge and clearly indicate this is not from the documents.

### Conversation History:{history_str}

### Current Question:
{query}

### Answer:"""


class RAGChain:
    def __init__(self, retriever: Retriever, llm_manager, system_prompt: str = ""):
        self.retriever = retriever
        self.llm = llm_manager
        self.system_prompt = system_prompt or self._default_prompt()
        self.chat_history: List[dict] = []

    def _default_prompt(self) -> str:
        return """You are an expert technical assistant. Answer questions using ONLY the provided context.
If the context doesn't contain the answer, say so clearly and provide general guidance.
Always cite your sources. Be precise and helpful."""

    def query(
        self,
        question: str,
        top_k: int = 5,
        stream: bool = True,
        max_new_tokens: int = 512,
    ) -> Generator[dict, None, None]:
        """
        Run a RAG query. Yields dicts with keys:
          - type: "sources" | "token" | "done" | "error"
          - data: content
        """
        # Retrieve
        chunks = self.retriever.retrieve(question, top_k=top_k)
        has_context = self.retriever.has_relevant_results(chunks)
        context = self.retriever.build_context(chunks)

        # Yield sources first
        yield {
            "type": "sources",
            "data": chunks,
            "has_context": has_context,
        }

        # Build prompt
        prompt = build_rag_prompt(
            query=question,
            context=context,
            system_prompt=self.system_prompt,
            chat_history=self.chat_history,
            has_context=has_context,
        )

        # Generate
        full_response = ""
        try:
            for token in self.llm.generate(prompt, max_new_tokens=max_new_tokens, stream=stream):
                full_response += token
                yield {"type": "token", "data": token}
        except Exception as e:
            yield {"type": "error", "data": str(e)}
            return

        # Update history
        self.chat_history.append({"role": "user", "content": question})
        self.chat_history.append({"role": "assistant", "content": full_response})

        # Keep history bounded
        if len(self.chat_history) > 20:
            self.chat_history = self.chat_history[-20:]

        yield {"type": "done", "data": full_response}

    def clear_history(self):
        self.chat_history = []
