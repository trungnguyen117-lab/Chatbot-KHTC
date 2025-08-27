from llama_index.core.response_synthesizers import TreeSummarize
from llama_index.core import PromptTemplate
from llama_index.core import Settings
from llama_index.core.query_engine import CustomQueryEngine
from rerank import Reranking
from retriever import HybridSearch
from dotenv import load_dotenv
from llama_index.core.response_synthesizers import BaseSynthesizer
import os
from prompt import PROMPT
from llama_index.llms.google_genai import GoogleGenAI
from typing import Optional
import logging

load_dotenv()

class RAGAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        # Khởi tạo LLM
        self.llm = GoogleGenAI(model=model_name)
        # Response Synthesizer
        self.response_synthesizer = TreeSummarize(llm=self.llm)
        # Search + Rerank
        self.search = HybridSearch()
        self.reranker = Reranking()
        # Prompt template
        self.prompt_tmpl = PromptTemplate(PROMPT)

        # QueryEngine
        self.query_engine = RAGStringQueryEngine(
            llm=self.llm,
            response_synthesizer=self.response_synthesizer,
        )

    def build_prompt(self, query: str, filename: Optional[str] = None) -> str:
        """Tạo prompt từ query + file context"""
        # Handle None filename properly
        if filename and filename.strip():
            logging.info(f"Building prompt with filename filter: {filename}")
            metadata_filter = self.search.metadata_filter(filename)
        else:
            logging.info("Building prompt without filename filter (search all)")
            metadata_filter = None
            
        results = self.search.query_hybrid_search(query, metadata_filter)

        if not results:
            logging.warning("No documents found for query")
            return self.prompt_tmpl.format(
                context_str="No relevant documents found.", 
                query_str=query
            )

        reranked_documents = self.reranker.rerank_documents(query, results)
        context = "\n\n".join(reranked_documents)

        return self.prompt_tmpl.format(context_str=context, query_str=query)

    def run(self, query: str, filename: Optional[str] = None) -> str:
        """Agent xử lý query"""
        logging.info(f"RAGAgent processing query with filename: {filename}")
        
        try:
            prompt = self.build_prompt(query, filename)
            response = self.query_engine.query(prompt)
            return response.response
        except Exception as e:
            logging.error(f"Error in RAGAgent.run: {e}")
            return f"Xin lỗi, tôi gặp lỗi khi xử lý câu hỏi của bạn: {str(e)}"

class RAGStringQueryEngine(CustomQueryEngine):
    llm: GoogleGenAI
    response_synthesizer: BaseSynthesizer

    def custom_query(self, prompt: str) -> str:
        response = self.llm.complete(prompt)
        summary = self.response_synthesizer.get_response(query_str = str(response), text_chunks = str(prompt))

        return str(summary)
    
if __name__ == "__main__":
    agent = RAGAgent()
    answer = agent.run("Công tác phí nước ngoài", "QT.pdf")
    print(answer)
