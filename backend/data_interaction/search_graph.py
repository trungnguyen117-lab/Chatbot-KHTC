from typing import Any, Dict, List
from neo4j import GraphDatabase



def search_normal_graph(self, query: str) -> Dict[str, Any]:
    """
    Tìm kiếm thường trong Graph DB sử dụng exact matching
    """
    with self.driver.session() as session:
        cypher_query = """
        MATCH (p:Thutuc)
        WHERE toLower(p.title) CONTAINS toLower($query)
        OR toLower(p.description) CONTAINS toLower($query)
        RETURN p.id AS id, 
            p.title AS title, 
            p.description AS description, 
            p.type AS type
        ORDER BY p.title
        """
        
        results = session.run(cypher_query, query=query)
        search_results = [dict(record) for record in results]
        
        return {
            "results": search_results,
            "suggestions": self._generate_suggestions_graph(query, "normal"),
            "total": len(search_results),
            "search_mode": "normal"
        }

def search_smart_graph(self, query: str) -> Dict[str, Any]:
    """
    Tìm kiếm thông minh sử dụng relationships và similarity
    """
    with self.driver.session() as session:
        cypher_query = """
        MATCH (p)
        OPTIONAL MATCH (p)-[:HAS_KEYWORD]->(k:Keyword)
        OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
        OPTIONAL MATCH (p)-[:RELATED_TO]->(r)
        WHERE toLower(p.title) CONTAINS toLower($query)
            OR toLower(p.description) CONTAINS toLower($query)
            OR toLower(k.name) CONTAINS toLower($query)
            OR toLower(c.name) CONTAINS toLower($query)
        RETURN p.id as id,
                p.title as title, 
                p.description as description,
                p.type as type,
                collect(DISTINCT k.name) as keywords,
                collect(DISTINCT c.name) as categories,
                collect(DISTINCT r.title) as related_procedures
        ORDER BY size(collect(DISTINCT k.name)) DESC, p.title
        """
        
        results = session.run(cypher_query, query=query)
        search_results = [dict(record) for record in results]
        
        return {
            "results": search_results,
            "suggestions": self._generate_suggestions_graph(query, "smart"),
            "total": len(search_results),
            "search_mode": "smart"
        }

def _generate_suggestions_graph(self, query: str, mode: str) -> List[str]:
    """
    Tạo suggestions dựa trên Graph relationships
    """
    with self.driver.session() as session:
        cypher_query = """
        MATCH (k:Keyword)-[:RELATED_TO]->(related:Keyword)
        WHERE toLower(k.name) CONTAINS toLower($query)
        RETURN collect(DISTINCT related.name) as suggestions
        LIMIT 5
        """
        
        result = session.run(cypher_query, query=query)
        record = result.single()
        if record and record["suggestions"]:
            return record["suggestions"]
        return []

