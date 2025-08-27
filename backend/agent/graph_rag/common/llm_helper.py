import re
import json
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from .schema.docling_schema import DOCLING_SCHEMA, DOCLING_PROMPTS
from .schema.text_schema import TEXT_SCHEMA, TEXT_PROMPTS

def build_llm(model_id: str, api_key: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model_id,
        google_api_key=api_key,
        temperature=0
    )

def build_cypher_prompt(schema_text: str, examples: list) -> PromptTemplate:
    example_block = "\n\n".join(
        f"Câu hỏi: {ex['question']}\nCypher:\n{ex['cypher']}" for ex in examples
    )

    template = """Task: Generate a Cypher statement to query a Neo4j graph.
Rules:
- Use ONLY labels/relationships/properties present in the schema.
- READ-ONLY query (MATCH/OPTIONAL MATCH/WHERE/RETURN). Do NOT use CREATE/MERGE/SET/DELETE/CALL.
- Output ONLY the Cypher statement (no explanation, no code fences).
- Prefer matching by structural keys.

Schema:
{schema}

Examples:
{examples}

Question:
{question}
"""
    return PromptTemplate.from_template(template).partial(examples=example_block)

def sanitize_cypher(text: str) -> str:
    """Clean up generated Cypher query"""
    if not text:
        return ""
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    text = re.sub(r"(?i)^cypher:\s*", "", text)
    text = text.replace("{{", "{").replace("}}", "}")
    text = re.sub(r";\s*$", "", text)
    return text.strip()

def is_readonly_cypher(query: str) -> bool:
    """Check if query is read-only"""
    return not re.search(r"\b(CREATE|MERGE|DELETE|SET|CALL)\b", query, flags=re.IGNORECASE)

def format_results(rows: List[Dict[str, Any]], max_rows: int = 30) -> str:
    """Format query results for display"""
    def make_jsonable(val):
        if isinstance(val, (str, int, float, bool)) or val is None:
            return val
        if isinstance(val, (list, tuple)):
            return [make_jsonable(x) for x in val]
        if isinstance(val, dict):
            return {k: make_jsonable(v) for k, v in val.items()}
        return str(val)

    safe_rows = [{k: make_jsonable(v) for k, v in row.items()} 
                 for row in rows[:max_rows]]
    return json.dumps(safe_rows, ensure_ascii=False, indent=2)

RESULTS_SUMMARY_TEMPLATE = """Bạn là trợ lý phân tích dữ liệu.
Nhiệm vụ: Tóm tắt kết quả truy vấn Neo4j bằng tiếng Việt, súc tích, dễ hiểu.
...
"""

FEW_SHOT_EXAMPLES = [
    {
        "question": "Liệt kê tất cả Phạm vi (code, title) của quy trình.",
        "cypher": """
        MATCH (q:Quytrinh)-[:HAS_SECTION]->(s:Phamvi)
        RETURN s.code AS code, s.title AS title 
        ORDER BY s.tableIdx, s.code
        """
    },
    # Copy các examples khác từ notebook
]