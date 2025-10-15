from ..common.config import *
from ..common.processors.docling import convert_docx_to_json, build_graph_documents
from ..common.graph_builder import GraphBuilder
from pathlib import Path
import json

def process_docling():
    """Import chapter_5.json directly into Neo4j as Knowledge Graph."""
    json_path = Path("./json_output/chapter_5.json")

    if not json_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file JSON: {json_path}")

    print(f"Importing DOCLING JSON directly from: {json_path}")
    graph = GraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)

    cleanup = globals().get("CLEANUP_REMOVE_ID", None)
    try:
        if cleanup:
            print("Cleaning up old nodes using CLEANUP_REMOVE_ID...")
            graph.import_documents(str(json_path), cleanup_query=cleanup)
        else:
            print("CLEANUP_REMOVE_ID not found. Importing without cleanup query...")
            graph.import_documents(str(json_path))
    except Exception as e:
        print(f"❌ Lỗi khi import JSON: {e}")
        raise

    print("✅ Done!")


def query_knowledge(question: str):
    """
    Query Neo4j knowledge graph bằng LLM:
    1. Validate schema & examples.
    2. Build Cypher query bằng Gemini LLM.
    3. Thực thi truy vấn trong Neo4j.
    4. Tóm tắt kết quả bằng LLM.
    """
    import json

    try:
        print("\n=== Starting query processing ===")
        llm = build_llm(GEMINI_MODEL, GOOGLE_API_KEY)

        # ==========================
        # 1. Validate DOCLING_SCHEMA
        # ==========================
        print("\nChecking DOCLING_SCHEMA...")
        print(f"DOCLING_SCHEMA type: {type(DOCLING_SCHEMA)}")
        
        if isinstance(DOCLING_SCHEMA, str):
            schema_text = DOCLING_SCHEMA.strip()
            print("Using original schema string")
        else:
            try:
                # Try to get the string representation from the schema object
                schema_text = str(DOCLING_SCHEMA)
                print("Converted schema to string")
            except:
                # Fallback to a basic schema if conversion fails
                schema_text = """
Node labels & properties:
- :Phamvi
  - code: STRING
  - tableIdx: INTEGER
  - title: STRING
- :Thutuc
  - code: STRING
  - title: STRING
- :Thanhphandutoan
  - name: STRING
- :Hosochungtu
  - name: STRING
- :Ghichu
  - text: STRING

Relationships:
(:Phamvi)-[:HAS_ITEM]->(:Thutuc)
(:Thutuc)-[:REQUIRES]->(:Thanhphandutoan)
(:Thutuc)-[:REQUIRES]->(:Hosochungtu)
(:Thutuc)-[:NOTE]->(:Ghichu)
"""
                print("Using fallback schema")

        # ============================================
        # 2. Validate few-shot examples từ DOCLING_PROMPTS
        # ============================================
        raw_examples = DOCLING_PROMPTS.get("few_shot_examples", [])
        valid_examples = []
        broken_examples = []

        for i, ex in enumerate(raw_examples):
            if not isinstance(ex, dict) or "question" not in ex or "cypher" not in ex:
                broken_examples.append(i)
                continue
            valid_examples.append(ex)

        print(f"[DEBUG] Tổng số ví dụ: {len(raw_examples)} | Hợp lệ: {len(valid_examples)} | Hỏng: {len(broken_examples)}")
        if broken_examples:
            print(f"[WARNING] Ví dụ hỏng tại index: {broken_examples}")

        if not valid_examples:
            return "Không có ví dụ hợp lệ để build prompt. Kiểm tra DOCLING_PROMPTS."

        # ====================================
        # 3. Build Cypher prompt cho LLM
        # ====================================
        print("\nBuilding Cypher prompt...")
        cypher_prompt = build_cypher_prompt(schema_text, valid_examples)
        print("Schema và examples đã load vào prompt.")

        # ====================================
        # 4. Gọi LLM sinh Cypher
        # ====================================
        print("\nGenerating Cypher query...")
        messages = [HumanMessage(content=cypher_prompt.format(question=question))]
        llm_response = llm.invoke(messages).content
        print(f"Raw LLM response:\n{llm_response}")

        # Làm sạch Cypher sinh ra
        cypher = sanitize_cypher(llm_response)
        print(f"\nSanitized Cypher query:\n{cypher}")

        if not cypher:
            print("[WARNING] LLM không trả về Cypher. Thử fallback với 3 ví dụ đầu.")
            fallback_examples = valid_examples[:3]
            fallback_prompt = build_cypher_prompt(schema_text, fallback_examples)
            llm_response = llm.invoke([HumanMessage(content=fallback_prompt.format(question=question))]).content
            cypher = sanitize_cypher(llm_response)
            print(f"[FALLBACK] Cypher mới: {cypher}")

            if not cypher:
                return "Không thể tạo câu truy vấn. LLM không trả về kết quả hợp lệ."

        # Kiểm tra Cypher có phải chỉ đọc không
        if not is_readonly_cypher(cypher):
            return "Không thể tạo câu truy vấn - Câu truy vấn không phải truy vấn chỉ đọc."

        # ====================================
        # 5. Thực thi truy vấn trong Neo4j
        # ====================================
        print("\nExecuting query in Neo4j...")
        try:
            graph = GraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
            results = graph.query(cypher)
            print(f"Query results: {results}")

            if not results:
                return "Không tìm thấy kết quả phù hợp với câu hỏi của bạn."
        except Exception as e:
            print(f"Neo4j Error: {str(e)}")
            return f"Có lỗi khi truy vấn cơ sở dữ liệu: {str(e)}"

        # ====================================
        # 6. Tóm tắt kết quả bằng Gemini
        # ====================================
        formatted_results = format_results(results)
        results_template = DOCLING_PROMPTS.get("results_template", "")

        if not isinstance(results_template, str):
            results_template = str(results_template)

        summary_prompt = results_template.format(
            question=question,
            cypher=cypher,
            results=formatted_results
        )

        print("\nGenerating summary...")
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


# if __name__ == "__main__":
#     # Process documents first if needed
#     should_process = input("Bạn có muốn xử lý lại tài liệu không? (y/N): ").strip().lower()
#     if should_process == 'y':
#         process_docling()
#         print("\nĐã xử lý xong tài liệu!")
   
#     # Start interactive chat
#     chat_loop()



