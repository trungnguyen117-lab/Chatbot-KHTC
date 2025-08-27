from agent.graph_rag.common.config import *
from agent.graph_rag.common.processors.text import build_graph_documents
from agent.graph_rag.common.utils.helpers import load_json
from agent.graph_rag.common.graph_builder import GraphBuilder

def process_text():
    """Process text JSON into structure graph"""
    print(f"Loading JSON: {TEXT_JSON_PATH}")
    data = load_json(TEXT_JSON_PATH)
    
    print("Building graph documents...")
    graph_docs = build_graph_documents(data)
    
    print("Importing to Neo4j...")
    graph = GraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
    graph.import_documents(graph_docs)
    
    print("Done!")

if __name__ == "__main__":
    print(">>> Running process_text() ...")  # test thêm log này
    process_text()
