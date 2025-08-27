from typing import List, Dict, Any
from langchain_neo4j import Neo4jGraph
from langchain_community.graphs.graph_document import GraphDocument

class GraphBuilder:
    def __init__(self, uri: str, username: str, password: str, database: str):
        self.graph = Neo4jGraph(
            url=uri,
            username=username,
            password=password,
            database=database,
            refresh_schema=True
        )
        self.graph.refresh_schema()

    def wipe_graph(self):
        """Wipe all nodes and relationships"""
        self.graph.query("MATCH (n) DETACH DELETE n")

    def import_documents(self, documents: List[GraphDocument], cleanup_query: str = None):
        """Import graph documents with optional cleanup"""
        self.wipe_graph()
        self.graph.add_graph_documents(documents, include_source=False)
        
        if cleanup_query:
            self.graph.query(cleanup_query)
            
        self.graph.refresh_schema()

    def query(self, cypher: str) -> List[Dict[str, Any]]:
        """Execute a Cypher query"""
        return self.graph.query(cypher)