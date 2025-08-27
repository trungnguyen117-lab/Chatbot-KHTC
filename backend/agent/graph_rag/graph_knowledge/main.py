from ..common.config import *
from ..common.processors.docling import convert_docx_to_json, build_graph_documents
from ..common.graph_builder import GraphBuilder
from ..common.llm_helper import *

def process_docling():
    """Process DOCX document into knowledge graph"""
    print(f"Converting DOCX: {DOCLING_INPUT_PATH}")
    data = convert_docx_to_json(DOCLING_INPUT_PATH, DOCLING_OUTPUT_PATH)
    
    print("Building graph documents...")
    graph_docs = build_graph_documents(data)
    
    print("Importing to Neo4j...")
    graph = GraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
    graph.import_documents(graph_docs, cleanup_query=CLEANUP_REMOVE_ID)
    
    print("Done!")

def query_knowledge(question: str):
    """Query the knowledge graph using LLM"""
    try:
        # Initialize LLM
        llm = build_llm(GEMINI_MODEL, GOOGLE_API_KEY)
        
        # Build Cypher prompt
        prompt = build_cypher_prompt(DOCLING_SCHEMA, FEW_SHOT_EXAMPLES)
        
        # Generate and sanitize Cypher query
        messages = [HumanMessage(content=prompt.format(question=question))]
        cypher = sanitize_cypher(llm.invoke(messages).content)
        
        if not cypher or not is_readonly_cypher(cypher):
            return "Không thể tạo câu truy vấn hợp lệ."
        
        print(f"Generated Cypher query:\n{cypher}\n")
        
        # Execute query
        graph = GraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
        results = graph.query(cypher)
        
        if not results:
            return "Không tìm thấy kết quả phù hợp."
        
        # Format results
        formatted_results = format_results(results)
        
        # Generate summary using LLM
        summary_prompt = RESULTS_SUMMARY_TEMPLATE.format(
            question=question,
            cypher=cypher,
            results=formatted_results
        )
        summary = llm.invoke([HumanMessage(content=summary_prompt)]).content
        
        return summary
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return f"Có lỗi xảy ra: {str(e)}"

def chat_loop():
    """Interactive chat loop for querying knowledge graph"""
    print("\nChào mừng bạn đến với hệ thống hỏi đáp về quy trình!")
    print("Gõ 'exit' hoặc 'quit' để thoát.\n")
    
    while True:
        question = input("\nCâu hỏi của bạn: ").strip()
        
        if question.lower() in ['exit', 'quit']:
            print("Tạm biệt!")
            break
            
        if not question:
            print("Vui lòng nhập câu hỏi.")
            continue
            
        try:
            answer = query_knowledge(question)
            print(f"\nTrả lời: {answer}")
        except Exception as e:
            print(f"\nLỗi: {str(e)}")
            print("Vui lòng thử lại với câu hỏi khác.")

if __name__ == "__main__":
    # Process documents first if needed
    should_process = input("Bạn có muốn xử lý lại tài liệu không? (y/N): ").strip().lower()
    if should_process == 'y':
        process_docling()
        print("\nĐã xử lý xong tài liệu!")
    
    # Start interactive chat
    chat_loop()