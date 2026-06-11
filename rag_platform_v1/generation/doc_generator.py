"""
Documentation generator - produces rich professional markdown from retrieved context.
"""
import logging
from typing import Generator, List

from retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

DOC_GEN_PROMPT = """You are a technical documentation expert. Using the provided context, generate rich professional documentation in Markdown format.

Include:
- Clear nested headings (##, ###)
- Tables where relevant
- Code blocks with language tags
- > Callout/Note/Warning blockquotes
- Mermaid diagrams when helpful (use ```mermaid blocks)
- Numbered steps for procedures (SOPs)
- A "Troubleshooting" section if applicable
- A brief summary at the top

Context:
{context}

Topic: {topic}

Generate comprehensive documentation:"""


class DocGenerator:
    def __init__(self, retriever: Retriever, llm_manager):
        self.retriever = retriever
        self.llm = llm_manager

    def generate(
        self,
        topic: str,
        top_k: int = 8,
        max_new_tokens: int = 1024,
        custom_prompt: str = "",
    ) -> Generator[str, None, None]:
        """Generate markdown documentation. Yields text tokens."""
        chunks = self.retriever.retrieve(topic, top_k=top_k)
        context = self.retriever.build_context(chunks)

        if not context:
            yield "⚠️ No relevant context found in the knowledge base for this topic.\n"
            yield "Please ingest relevant documents first.\n"
            return

        prompt_template = custom_prompt if custom_prompt else DOC_GEN_PROMPT
        prompt = prompt_template.format(context=context, topic=topic)

        try:
            for token in self.llm.generate(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=0.4,
                stream=True,
            ):
                yield token
        except Exception as e:
            yield f"\n[Generation error: {e}]"
