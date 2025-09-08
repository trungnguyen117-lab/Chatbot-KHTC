from typing import Any, Dict, List
from neo4j import GraphDatabase

def search_normal_graph(self, query: str) -> Dict[str, Any]:
    """
    Tìm kiếm thường trong Graph DB (CONTAINS) và trả kết quả ở cấp Thutuc.
    id trả về là elementId(t) của Neo4j.
    """
    import unicodedata

    # q1: bản thường; q2: bản NFD (tổ hợp dấu) để tăng xác suất khớp
    q1 = (query or "").strip().lower()
    q2 = unicodedata.normalize("NFD", q1)

    with self.driver.session() as session:
        cypher_query = """
        WITH toLower(trim(toString($q1))) AS q1,
             toLower(trim(toString($q2))) AS q2

        MATCH (proc:Quytrinh)-[:HAS_SECTION]->(sec:Phamvi)-[:HAS_ITEM]->(t:Thutuc)
        OPTIONAL MATCH (t)-[:REQUIRES]->(tp:Thanhphandutoan)
        OPTIONAL MATCH (t)-[:REQUIRES]->(hs:Hosochungtu)
        OPTIONAL MATCH (t)-[:NOTE]->(gh:Ghichu)

        WITH t, proc, sec, q1, q2,
             [x IN collect(DISTINCT toLower(tp.name)) WHERE x IS NOT NULL] AS tpnames,
             [x IN collect(DISTINCT toLower(hs.name)) WHERE x IS NOT NULL] AS hsnames,
             [x IN collect(DISTINCT toLower(gh.text)) WHERE x IS NOT NULL] AS notes

        WITH t, proc, sec, q1, q2, tpnames, hsnames, notes,
             [ toLower(coalesce(t.title,'')),
               toLower(coalesce(t.description,'')),
               toLower(coalesce(sec.title,'')),
               toLower(coalesce(proc.title,'')),
               toLower(coalesce(proc.full_title,'')) ] AS texts

        WHERE (q1 <> '' AND (
                  any(txt IN texts   WHERE txt CONTAINS q1)
               OR any(x   IN tpnames WHERE x   CONTAINS q1)
               OR any(x   IN hsnames WHERE x   CONTAINS q1)
               OR any(x   IN notes   WHERE x   CONTAINS q1)
        )) OR (q2 <> '' AND (
                  any(txt IN texts   WHERE txt CONTAINS q2)
               OR any(x   IN tpnames WHERE x   CONTAINS q2)
               OR any(x   IN hsnames WHERE x   CONTAINS q2)
               OR any(x   IN notes   WHERE x   CONTAINS q2)
        ))

        RETURN DISTINCT
          elementId(t)                 AS id,
          t.title                      AS title,
          coalesce(t.description,'')   AS description,
          t.type                       AS type
        ORDER BY title
        LIMIT 100
        """

        results = session.run(cypher_query, q1=q1, q2=q2)
        search_results = [dict(record) for record in results]

        return {
            "results": search_results,
            "suggestions": self._generate_suggestions_graph(query, "normal"),
            "total": len(search_results),
            "search_mode": "normal",
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

