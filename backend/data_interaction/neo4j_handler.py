from neo4j import GraphDatabase

class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_root_with_subitems(self, label=None):
        """
        Lấy các node cấp 0 (root) và danh sách subItems (node con trực tiếp).
        """
        with self.driver.session() as session:
            if label:
                query = f"""
                MATCH (root:{label})
                WHERE NOT ( ()-[:*]->(root) )
                OPTIONAL MATCH (root)-[:HAS_SUBITEM]->(child)
                RETURN root, collect(child.title) as subItems
                """
            else:
                query = """
                MATCH (root)
                WHERE NOT ( ()-[:*]->(root) )
                OPTIONAL MATCH (root)-[:HAS_SUBITEM]->(child)
                RETURN root, collect(child.title) as subItems
                """

            results = session.run(query)
            data = []
            for record in results:
                root = record["root"]
                subitems = record["subItems"]

                data.append({
                    "id": root.get("id"),
                    "title": root.get("title"),
                    "description": root.get("description"),
                    "date": root.get("date"),   # ngày tạo / ngày hiệu lực
                    "subItems": [s for s in subitems if s]  # loại None
                })
            return data

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
