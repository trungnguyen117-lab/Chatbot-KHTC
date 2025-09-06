import re
import json
from typing import List, Dict, Any, Union
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

def build_llm(model_id: str, api_key: str) -> ChatGoogleGenerativeAI:
    """Initialize a Gemini LLM instance"""
    return ChatGoogleGenerativeAI(
        model=model_id,
        google_api_key=api_key,
        temperature=0
    )

def format_schema() -> str:
    """Returns the fixed schema format."""
    return """
Node labels & properties:
- :Phamvi {code, tableIdx, title}
- :Thutuc {code, title}
- :Thanhphandutoan {name}
- :Hosochungtu {name}
- :Ghichu {text}

Relationships:
(:Phamvi)-[:HAS_ITEM]->(:Thutuc)
(:Thutuc)-[:REQUIRES]->(:Thanhphandutoan)
(:Thutuc)-[:REQUIRES]->(:Hosochungtu)
(:Thutuc)-[:NOTE]->(:Ghichu)
"""

# ---------- Cypher prompt builder ----------
def build_cypher_prompt(schema_text: Union[str, Dict[str, Any]], examples: List[Dict[str, str]]) -> PromptTemplate:
    """Build Cypher query prompt with schema and examples."""
    # Get schema string
    schema = format_schema()

    # Normalize examples into a string block
    example_texts = []
    for ex in examples:
        if "question" in ex and "cypher" in ex:
            example_texts.append(f"Question: {ex['question']}\nCypher:\n{ex['cypher']}")
    example_block = "\n\n".join(example_texts)

    template = """Task: Generate a Cypher statement to query a Neo4j graph.
Rules:
- Use ONLY labels/relationships/properties present in the schema
- READ-ONLY query (MATCH/OPTIONAL MATCH/WHERE/RETURN). Do NOT use CREATE/MERGE/SET/DELETE/CALL
- Output ONLY the Cypher statement (no explanation, no code fences)
- Prefer matching by structural keys: (q.title) + (s.code, s.tableIdx) + (t.code)
- If the question mentions "Công tác phí trong nước", map to Section with code='I' and tableIdx=1

Schema:
{schema}

Examples:
{examples}

Question:
{question}
"""
    return PromptTemplate.from_template(template).partial(
        schema=schema,
        examples=example_block
    )
# ---------- Utilities ----------
def sanitize_cypher(text: str) -> str:
    """Clean up generated Cypher query."""
    if not text:
        return ""
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip())
    text = re.sub(r"(?i)^cypher:\s*", "", text)
    text = text.replace("{{", "{").replace("}}", "}")
    text = re.sub(r";\s*$", "", text)
    return text.strip()

def is_readonly_cypher(query: str) -> bool:
    """Check if query is read-only."""
    return not re.search(r"\b(CREATE|MERGE|DELETE|SET|CALL)\b", query, flags=re.IGNORECASE)

def format_results(results: Any, max_rows: int = 30) -> str:
    """Format query results as JSON string."""
    
    def make_jsonable(val):
        if isinstance(val, (str, int, float, bool)) or val is None:
            return val
        if isinstance(val, (list, tuple)):
            return [make_jsonable(x) for x in val]
        if isinstance(val, dict):
            return {k: make_jsonable(v) for k, v in val.items()}
        return str(val)

    # Handle primitive types
    if isinstance(results, (str, int, float, bool)) or results is None:
        return json.dumps([{"result": results}], ensure_ascii=False, indent=2)
        
    # Handle dictionary
    if isinstance(results, dict):
        return json.dumps([make_jsonable(results)], ensure_ascii=False, indent=2)
        
    # Handle list
    if isinstance(results, list):
        # Dictionary list
        if results and all(isinstance(r, dict) for r in results):
            safe_rows = [
                {k: make_jsonable(v) for k, v in row.items()}
                for row in results[:max_rows]
            ]
            return json.dumps(safe_rows, ensure_ascii=False, indent=2)
        # Other list types
        safe_rows = [{"result": make_jsonable(item)} for item in results[:max_rows]]
        return json.dumps(safe_rows, ensure_ascii=False, indent=2)

    # Handle other types
    return json.dumps([{"result": str(results)}], ensure_ascii=False, indent=2)
