from typing import Any
from altair import Dict
from neo4j import GraphDatabase
from get_available import get_root_with_subitem
from search_graph import search_normal_graph, search_smart_graph

class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_root_with_subitems(self, label=None):
        return get_root_with_subitem(self, label)
    
    def search_procedures_in_graph(query: str, mode: int) -> Dict[str, Any]:
        if mode == 0:
            return search_normal_graph(query)
        else:
            return search_smart_graph(query)