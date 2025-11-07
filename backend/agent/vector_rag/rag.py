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
from .prompt import HALLUCINATION_TRIGGERS
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
        self.fallback_prompt_tmpl = PromptTemplate(FALLBACK_PROMPT) 
        self.retriever_score_threshold = 0.69

        self.hallucination_triggers = HALLUCINATION_TRIGGERS

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

        if not results or results[0].score < self.retriever_score_threshold:
            
            top_score = results[0].score if results else "N/A"
            logging.warning(
                f"FALLBACK TRIGGERED cho câu hỏi: '{query}'. "
                f"Score RRF cao nhất: {top_score} (Ngưỡng: {self.retriever_score_threshold})"
            )
            
            return self.fallback_prompt_tmpl.format(query_str=query)

        logging.info(f"RAG Succeeded: Score {results[0].score} > {self.retriever_score_threshold}")
        
        documents_list = [point.payload['text'] for point in results]

        context = "\n\n".join(self.reranker.rerank_documents(query, documents_list))
        
        return self.prompt_tmpl.format(context_str=context, query_str=query)

    def run(self, query: str, filename: Optional[str] = None, stream: bool = True):
        
        prompt = self.build_prompt(query, filename)
        
        is_already_fallback = "### THÔNG BÁO TỪ HỆ THỐNG" in prompt 

        response_text = None
        is_hallucination = False
        
        if not is_already_fallback:
            try:
                response_text = self.llm.complete(prompt).text
            except Exception as e:
                logging.error(f"LLM generation failed: {e}")
                response_text = f"Lỗi: Đã xảy ra sự cố khi tạo câu trả lời RAG. {e}"

            response_text_lower = response_text.lower()
            is_hallucination = any(trigger in response_text_lower for trigger in self.hallucination_triggers)
        
        final_prompt_for_llm_call = None
        
        if is_already_fallback:
            final_prompt_for_llm_call = prompt
            
        elif is_hallucination:
            logging.warning(
                f"FALLBACK (Hallucination Guard): A trigger phrase was detected in the RAG response, initiating fallback protocol. Query: '{query}'"
            )
            final_prompt_for_llm_call = self.fallback_prompt_tmpl.format(query_str=query)
        
        if stream:
            def final_generator():
                if final_prompt_for_llm_call:
                    try:
                        for chunk in self.llm.stream_complete(final_prompt_for_llm_call):
                            if chunk.delta:
                                yield chunk.delta
                    except Exception as e:
                        logging.error(f"Fallback LLM stream failed: {e}")
                        yield f"Lỗi: Đã xảy ra sự cố khi tạo câu trả lời fallback. {e}"
                
                else:
                    chunk_size = 5 
                    for i in range(0, len(response_text), chunk_size):
                        yield response_text[i:i+chunk_size]
                        
            return final_generator() 

        else:
            if final_prompt_for_llm_call:
                try:
                    return self.llm.complete(final_prompt_for_llm_call).text
                except Exception as e:
                    logging.error(f"Fallback LLM complete failed: {e}")
                    return f"Lỗi: Đã xảy ra sự cố khi tạo câu trả lời fallback. {e}"
            
            else:
                return response_text

    
if __name__ == "__main__":
    agent = RAGAgent()
    answer = agent.run("Công tác phí nước ngoài", "QT.pdf")
    print(answer)
