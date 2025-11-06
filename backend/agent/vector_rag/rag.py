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
from .prompt import FALLBACK_PROMPT
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
        
        # === THAY ĐỔI Ở ĐÂY ===
        self.prompt_tmpl = PromptTemplate(PROMPT)
        self.fallback_prompt_tmpl = PromptTemplate(FALLBACK_PROMPT) 
        self.retriever_score_threshold = 0.69
        # === KẾT THÚC THAY ĐỔI ===

        # QueryEngine streaming
        self.query_engine = RAGStringQueryEngine(llm=self.llm)

    def build_prompt(self, query: str, filename: Optional[str] = None) -> str:
        if filename and filename.strip():
            logging.info(f"Building prompt with filename filter: {filename}")
            metadata_filter = self.search.metadata_filter(filename)
        else:
            logging.info("Building prompt without filename filter (search all)")
            metadata_filter = None

        # 1. `results` BÂY GIỜ LÀ List[ScoredPoint] NHỜ SỬA file `retriever.py`
        results = self.search.query_hybrid_search(query, metadata_filter) 

        # === THAY ĐỔI QUAN TRỌNG: Logic kiểm tra score ===
        if not results or results[0].score < self.retriever_score_threshold:
            # 2. KIỂM TRA ĐIỂM SỐ: Nếu rỗng HOẶC điểm thấp hơn ngưỡng
            
            top_score = results[0].score if results else "N/A"
            logging.warning(
                f"FALLBACK TRIGGERED cho câu hỏi: '{query}'. "
                f"Score RRF cao nhất: {top_score} (Ngưỡng: {self.retriever_score_threshold})"
            )
            
            # 3. TRẢ VỀ PROMPT FALLBACK
            return self.fallback_prompt_tmpl.format(query_str=query)
        # === KẾT THÚC THAY ĐỔI ===

        # 4. NẾU ĐIỂM ĐỦ CAO: Tiếp tục RAG bình thường
        logging.info(f"RAG Succeeded: Score {results[0].score} > {self.retriever_score_threshold}")
        
        # 5. TRÍCH XUẤT TEXT từ List[ScoredPoint]
        documents_list = [point.payload['text'] for point in results]

        # 6. Gửi List[str] cho Reranker
        context = "\n\n".join(self.reranker.rerank_documents(query, documents_list))
        
        # 7. SỬ DỤNG PROMPT GỐC
        return self.prompt_tmpl.format(context_str=context, query_str=query)

    def run(self, query: str, filename: Optional[str] = None, stream: bool = True):
        # Hàm build_prompt giờ sẽ tự động trả về 1 trong 2 prompt
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
