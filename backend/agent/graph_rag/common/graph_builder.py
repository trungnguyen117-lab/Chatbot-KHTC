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
        """Xoá toàn bộ nodes và relationships trong DB"""
        self.graph.query("MATCH (n) DETACH DELETE n")

    def import_documents(self, documents: List[GraphDocument], cleanup_query: str = None):
        """
        Import graph documents SAU KHI XOÁ dữ liệu cũ (overwrite mode).
        Dùng khi muốn chỉ giữ 1 KG duy nhất trong DB.
        """
        self.wipe_graph()
        self.graph.add_graph_documents(documents, include_source=False)

        if cleanup_query:
            self.graph.query(cleanup_query)

        self.graph.refresh_schema()

    def safe_import_documents(self, documents: List[GraphDocument]):
        """Merge tài liệu vào KG mà không xoá dữ liệu cũ.
        - Nếu node/relationship đã tồn tại thì update properties
        - Nếu chưa có thì tạo mới
        """

        def make_jsonable(val):
            if isinstance(val, (str, int, float, bool)) or val is None:
                return val
            if isinstance(val, (list, tuple)):
                return [make_jsonable(x) for x in val]
            if isinstance(val, dict):
                return {k: make_jsonable(v) for k, v in val.items()}
            return str(val)

        for doc in documents:
            # 🟢 Import nodes
            for node in doc.nodes:
                props = {k: make_jsonable(v) for k, v in node.properties.items()}
                self.graph.query(
                    f"""
                    MERGE (n:{node.type} {{id: $id}})
                    SET n += $props
                    """,
                    {"id": str(node.id), "props": props}
                )

            # 🟢 Import relationships
            for rel in doc.relationships:
                props = {k: make_jsonable(v) for k, v in rel.properties.items()}
                self.graph.query(
                    f"""
                    MATCH (a {{id: $source_id}}), (b {{id: $target_id}})
                    MERGE (a)-[r:{rel.type}]->(b)
                    SET r += $props
                    """,
                    {
                        "source_id": str(rel.source.id),   # ✅ lấy id thay vì object
                        "target_id": str(rel.target.id),   # ✅ lấy id thay vì object
                        "props": props
                    }
                )

        self.graph.refresh_schema()

    def query(self, cypher: str) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results"""
        return self.graph.query(cypher)

