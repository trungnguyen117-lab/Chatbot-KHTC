from ..common.config import *
from ..common.processors.docling import convert_docx_to_json, build_graph_documents
from ..common.graph_builder import GraphBuilder

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