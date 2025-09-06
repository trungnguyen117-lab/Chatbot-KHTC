from ..common.config import *
from ..common.processors.text import build_graph_documents
from ..common.utils.helpers import load_json
from ..common.graph_builder import GraphBuilder
from ..common.llm_helper import *
from ..common.schema.text_schema import TEXT_SCHEMA, FEW_SHOT_EXAMPLES

def process_text(json_files, reset=False):
    """Process multiple JSON files into structure graph"""
    graph = GraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)

    if reset:
        print("🧹 Đang xoá toàn bộ dữ liệu cũ...")
        graph.wipe_graph()

    for path in json_files:
        print(f"📂 Loading JSON: {path}")
        data = load_json(path)

        print("🔨 Building graph documents...")
        graph_docs = build_graph_documents(data)

        print("📥 Importing to Neo4j...")
        graph.safe_import_documents(graph_docs)

    print("✅ Done!")


def query_knowledge(question: str):
    """Query the knowledge graph using LLM"""
    try:
        llm = build_llm(GEMINI_MODEL, GOOGLE_API_KEY)

        # Build Cypher prompt
        prompt = build_cypher_prompt(
            schema_text=json.dumps(TEXT_SCHEMA, ensure_ascii=False, indent=2),
            examples=FEW_SHOT_EXAMPLES
        )

        # Generate Cypher
        messages = [HumanMessage(content=prompt.format(question=question))]
        cypher = sanitize_cypher(llm.invoke(messages).content)

        if not cypher or not is_readonly_cypher(cypher):
            return "Không thể tạo câu truy vấn hợp lệ."

        print(f"Generated Cypher query:\n{cypher}\n")

        graph = GraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
        results = graph.query(cypher)

        if not results:
            return "Không tìm thấy kết quả phù hợp."

        formatted_results = format_results(results)

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
    print("\n🤖 Chào mừng bạn đến với hệ thống hỏi đáp về quy trình!")
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
    should_process = input("Bạn có muốn xử lý lại tài liệu không? (y/N): ").strip().lower()
    if should_process == 'y':
        reset = input("Bạn có muốn xoá dữ liệu cũ trước khi import? (y/N): ").strip().lower() == 'y'

        # 🟢 Import nhiều JSON
        json_files = [
            "json_text/quytrinh.json",
            "json_text/quyche.json"
        ]
        print("✅ FEW_SHOT_EXAMPLES loaded, số ví dụ:", len(FEW_SHOT_EXAMPLES))
        process_text(json_files, reset=reset)

    chat_loop()
