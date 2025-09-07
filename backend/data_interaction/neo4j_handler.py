from altair import Dict
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