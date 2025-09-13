from typing import Any, Dict, List  
from neo4j import GraphDatabase
# from .get_available import get_root_with_subitem
class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_root_with_subitems(self, label: str | None = None):
        if label:
            query = f"""
            MATCH (root:{label})
            WHERE NOT EXISTS {{ MATCH ()-[:REQUIRES]->(root) }}
            OPTIONAL MATCH (q:Quytrinh)-[:HAS_SECTION]->(p:Phamvi)-[:HAS_ITEM]->(root)

            OPTIONAL MATCH (root)-[:NOTE]->(note:Ghichu)
            OPTIONAL MATCH (root)-[:REQUIRES]->(hs:Hosochungtu)
            OPTIONAL MATCH (tp:Thanhphandutoan)-[:REQUIRES]->(root)

            WITH root, q, p,
                collect({{id: elementId(note), title: coalesce(note.title, note.description, '')}}) +
                collect({{id: elementId(hs),   title: coalesce(hs.title, hs.description, '')}}) +
                collect({{id: elementId(tp),   title: coalesce(tp.name, tp.description, tp.code, '')}}) AS subItems
            RETURN
                elementId(root) AS id,
                elementId(root) AS internalId,
                coalesce(root.title,'') AS title,
                coalesce(root.description,'') AS description,
                coalesce(toString(root.date),'') AS date,
                q.full_title AS quytrinh,
                p.title AS phamvi,
                subItems
            ORDER BY title
            """
        else:
            query = """
            MATCH (root:Thutuc)
            WHERE NOT EXISTS { MATCH ()-[:REQUIRES]->(root) }
            OPTIONAL MATCH (q:Quytrinh)-[:HAS_SECTION]->(p:Phamvi)-[:HAS_ITEM]->(root)

            OPTIONAL MATCH (root)-[:NOTE]->(note:Ghichu)
            OPTIONAL MATCH (root)-[:REQUIRES]->(hs:Hosochungtu)
            OPTIONAL MATCH (tp:Thanhphandutoan)-[:REQUIRES]->(root)

            WITH root, q, p,
                collect({id: elementId(note), title: coalesce(note.title, note.description, '')}) +
                collect({id: elementId(hs),   title: coalesce(hs.title, hs.description, '')}) +
                collect({id: elementId(tp),   title: coalesce(tp.name, tp.description, tp.code, '')}) AS subItems
            RETURN
                elementId(root) AS id,
                coalesce(root.title,'') AS title,
                coalesce(root.description,'') AS description,
                coalesce(toString(root.date),'') AS date,
                q.full_title AS quytrinh,
                p.title AS phamvi,
                subItems
            ORDER BY title
            """

        with self.driver.session() as session:
            results = session.run(query)
            data = []
            for record in results:
                sub_items = []
                for item in (record.get("subItems") or []):
                    if item and item.get("id") and item.get("title"):
                        sub_items.append({
                            "id": item["id"],
                            "title": item["title"]
                        })
                data.append({
                    "id": record.get("id"),
                    "title": record.get("title"),
                    "description": record.get("description"),
                    "date": record.get("date"),
                    "parent": f"{record.get('quytrinh') or ''} / {record.get('phamvi') or ''}",
                    "subItems": sub_items
                })
            return data


    def _generate_suggestions_graph(self, query: str, mode: str) -> List[str]:
        """Generate search suggestions based on the query"""
        suggestions = []
        return suggestions

    def search_normal_graph(self, query: str) -> Dict[str, Any]:
        """
        Tìm kiếm thường trong Graph DB (CONTAINS) và trả kết quả ở cấp Thutuc.
        id trả về là elementId(t) của Neo4j.
        """
        import unicodedata

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
            WHERE toLower(p.title) CONTAINS toLower($q)
            OR toLower(p.description) CONTAINS toLower($q)
            OR toLower(k.name) CONTAINS toLower($q)
            OR toLower(c.name) CONTAINS toLower($q)
            RETURN p.id as id,
                p.title as title, 
                p.description as description,
                p.type as type,
                collect(DISTINCT k.name) as keywords,
                collect(DISTINCT c.name) as categories,
                collect(DISTINCT r.title) as related_procedures
            ORDER BY size(collect(DISTINCT k.name)) DESC, p.title
            """

            results = session.run(cypher_query, q=query)

            search_results = [dict(record) for record in results]
            
            return {
                "results": search_results,
                "suggestions": self._generate_suggestions_graph(query, "smart"),
                "total": len(search_results),
                "search_mode": "smart",
            }

    def get_procedure_detail(self, procedure_id: str):
        procedure_id = procedure_id.strip()
        with self.driver.session() as session:
            try:
                # thử parse sang số để match bằng internal id
                procedure_int = int(procedure_id)
                query = """
                MATCH (p:Thutuc)
                WHERE id(p) = $procedure_int
                OPTIONAL MATCH (p)-[:REQUIRES]->(tp:Thanhphandutoan)
                OPTIONAL MATCH (p)-[:REQUIRES]->(hs:Hosochungtu)
                OPTIONAL MATCH (p)-[:NOTE]->(gc:Ghichu)
                RETURN p,
                       collect(DISTINCT tp) as thanhphandutoans,
                       collect(DISTINCT hs) as hosochungtus,
                       collect(DISTINCT gc) as ghichus
                """
                result = session.run(query, procedure_int=procedure_int).single()
            except ValueError:
            # nếu không phải số → thử elementId hoặc code
                query = """
                MATCH (p:Thutuc)
                WHERE elementId(p) = $procedure_id OR p.code = $procedure_id
                OPTIONAL MATCH (p)-[:REQUIRES]->(tp:Thanhphandutoan)
                OPTIONAL MATCH (p)-[:REQUIRES]->(hs:Hosochungtu)
                OPTIONAL MATCH (p)-[:NOTE]->(gc:Ghichu)
                RETURN p,
                    collect(DISTINCT tp) as thanhphandutoans,
                    collect(DISTINCT hs) as hosochungtus,
                    collect(DISTINCT gc) as ghichus
                """
                result = session.run(query, procedure_id=procedure_id).single()

            if not result:
                return None

            node = result["p"]

            return {
                "id": str(node.id),   # internal id
                "title": node.get("title"),
                "description": node.get("description"),
                "type": node.get("type"),
                "thanhphandutoans": [dict(tp) for tp in result["thanhphandutoans"] if tp],
                "hosochungtus": [dict(hs) for hs in result["hosochungtus"] if hs],
                "ghichus": [dict(gc) for gc in result["ghichus"] if gc],
            }

        return get_root_with_subitem(self, label)

    def search_procedures_in_graph(self, query: str, mode: str | int = "normal") -> Dict[str, Any]:
        # Chuẩn hoá mode
        m = str(mode).strip().lower() if mode is not None else "normal"
        if m in ("smart", "1", "true", "yes"):
            return self.search_smart_graph(query)
        return self.search_normal_graph(query)