from llama_index.core.response_synthesizers import TreeSummarize
from llama_index.core import PromptTemplate
from llama_index.core import Settings
from llama_index.core.query_engine import CustomQueryEngine
from .rerank import Reranking
from .retriever import HybridSearch
from dotenv import load_dotenv
from llama_index.llms.google_genai import GoogleGenAI
from typing import Optional
import logging
import os
from .prompt import PROMPT

load_dotenv()

class RAGStringQueryEngine(CustomQueryEngine):
    llm: GoogleGenAI

    def custom_query(self, prompt: str):
        """Streaming từng token thay vì chờ cả câu trả lời"""
        def generator():
            for event in self.llm.stream_complete(prompt):
                if event.delta:   # token mới
                    yield event.delta
        return generator()


class RAGAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.llm = GoogleGenAI(model=model_name)
        self.search = HybridSearch()
        self.reranker = Reranking()
        self.prompt_tmpl = PromptTemplate(PROMPT)
        # QueryEngine streaming
        self.query_engine = RAGStringQueryEngine(llm=self.llm)

    def build_prompt(self, query: str, filename: Optional[str] = None) -> str:
        if filename and filename.strip():
            logging.info(f"Building prompt with filename filter: {filename}")
            metadata_filter = self.search.metadata_filter(filename)
        else:
            logging.info("Building prompt without filename filter (search all)")
            metadata_filter = None

        results = self.search.query_hybrid_search(query, metadata_filter)

        if not results:
            return self.prompt_tmpl.format(
                context_str="No relevant documents found.", 
                query_str=query
            )

        context = "\n\n".join(self.reranker.rerank_documents(query, results))
        # context = "\n\n".join(results)
        return self.prompt_tmpl.format(context_str=context, query_str=query)

    def run(self, query: str, filename: Optional[str] = None, stream: bool = True):
        prompt = self.build_prompt(query, filename)

        if stream:
            return self.query_engine.query(prompt)  # generator
        else:
            response = self.llm.complete(prompt)  # chờ full
            return response.text

    
if __name__ == "__main__":
    agent = RAGAgent()
    answer = agent.run("Công tác phí nước ngoài", "QT.pdf")
    print(answer)
