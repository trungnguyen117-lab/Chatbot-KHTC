from typing import List, Dict, Any, Union
from langchain_neo4j import Neo4jGraph
from langchain_community.graphs.graph_document import GraphDocument
import json, os

JsonInput = Union[List[GraphDocument], str, Dict[str, Any]]


class GraphBuilder:
    def __init__(self, uri: str, username: str, password: str, database: str):
        """Khởi tạo kết nối tới Neo4j"""
        self.graph = Neo4jGraph(
            url=uri,
            username=username,
            password=password,
            database=database
        )
        self.graph.refresh_schema()

    # =========================================================
    # Xóa dữ liệu cũ
    # =========================================================
    def wipe_graph(self):
        """Xoá toàn bộ nodes và relationships trong DB"""
        print("🧹 Wiping all existing nodes and relationships...")
        self.graph.query("MATCH (n) DETACH DELETE n")

    # =========================================================
    # Import dữ liệu (xóa cũ trước)
    # =========================================================
    def import_documents(self, documents: JsonInput, cleanup_query: str = None):
        """Import SAU KHI XOÁ dữ liệu cũ (overwrite mode)."""
        self.wipe_graph()
        nodes, rels = self._extract_nodes_rels_from_json(documents)
        self._bulk_import(nodes, rels)

        if cleanup_query:
            self.graph.query(cleanup_query)

        self.graph.refresh_schema()
        print("✅ Import complete (overwrite mode).")

    # =========================================================
    # Import dữ liệu (merge, không xóa)
    # =========================================================
    def safe_import_documents(self, documents: JsonInput):
        """Import dữ liệu mà KHÔNG xoá dữ liệu cũ (merge mode)."""
        nodes, rels = self._extract_nodes_rels_from_json(documents)
        self._bulk_import(nodes, rels)
        self.graph.refresh_schema()
        print("✅ Import complete (merge mode).")

    # =========================================================
    # Helper chính: đọc JSON và tách nodes / relationships
    # =========================================================
    def _extract_nodes_rels_from_json(self, json_input: JsonInput):
        """Đọc file JSON và trích xuất nodes + relationships"""
        # --- Đọc file hoặc dict ---
        if isinstance(json_input, str):
            path = os.path.expanduser(json_input)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif isinstance(json_input, dict):
            data = json_input
        else:
            raise TypeError("json_input phải là đường dẫn (str) hoặc dict JSON.")

        nodes, rels = [], []

        # ====== Hàm con để thêm node / relationship ======
        def add_node(label: str, nid: str, **props):
            if not nid:
                return
            p = {"id": nid}
            p.update({k: v for k, v in props.items() if v is not None})
            nodes.append({"type": label, "properties": p})

        def add_rel(src_label: str, src_id: str, rtype: str, tgt_label: str, tgt_id: str, **props):
            if not (src_id and tgt_id and rtype):
                return
            rels.append({
                "source_type": src_label, "source_id": src_id,
                "type": rtype,
                "target_type": tgt_label, "target_id": tgt_id,
                "properties": {k: v for k, v in props.items() if v is not None}
            })

        # ====== Node Quytrinh ======
        q = data.get("Quytrinh", {})
        q_code = q.get("code", "1")
        q_id = f"Quytrinh:{q_code}"
        add_node("Quytrinh", q_id,
                 code=q.get("code"),
                 title=q.get("title"),
                 full_title=q.get("full_title"),
                 type=q.get("type"),
                 original_title=q.get("original_title"))

        # ====== Hàm đệ quy xử lý items ======
        def handle_items(items_list, section_code, group_code, parent_label, parent_id, inherited_title=""):
            if not items_list:
                return

            for it in items_list:
                i_label = it.get("label", "Thutuc")
                i_code = it.get("code", "")
                i_title = it.get("title") or inherited_title or "Thủ tục"
                i_cat = (it.get("category") or "").strip()
                i_id = f"{i_label}:{section_code}.{group_code}.{i_code}".rstrip(".")

                # --- Node Thutuc ---
                add_node(i_label, i_id,
                         code=i_code,
                         title=i_title,
                         category=i_cat if i_cat else None,
                         section_code=section_code,
                         group_code=group_code)

                rel_type = "HAS_ITEM" if parent_label != "Thutuc" else "HAS_SUBITEM"
                add_rel(parent_label, parent_id, rel_type, i_label, i_id)

                # --- Category node ---
                cat_id = None
                if i_cat:
                    cat_id = f"category:{section_code}.{group_code}.{i_code}:{i_cat}"
                    add_node("category", cat_id, name=i_cat)
                    add_rel(i_label, i_id, "HAS_CATEGORY", "category", cat_id)

                # --- Budgets ---
                for b in (it.get("budgets") or []):
                    bname = (str(b) if b else "").strip()
                    if not bname:
                        continue
                    b_id = f"budgets:{section_code}.{group_code}.{i_code}:{bname}"
                    add_node("budgets", b_id, name=bname)

                    if cat_id:
                        add_rel("category", cat_id, "HAS_ITEM", "budgets", b_id)
                    else:
                        add_rel(i_label, i_id, "HAS_BUDGET", "budgets", b_id)

                # --- Docs ---
                for d in (it.get("docs") or []):
                    dtitle = (str(d) if d else "").strip()
                    if not dtitle:
                        continue
                    d_id = f"docs:{section_code}.{group_code}.{i_code}:{dtitle}"
                    add_node("docs", d_id, title=dtitle)
                    add_rel(i_label, i_id, "REQUIRES", "docs", d_id)

                # --- Note ---
                note_text = (it.get("note") or "").strip()
                if note_text:
                    n_id = f"note:{section_code}.{group_code}.{i_code}"
                    add_node("note", n_id, description=note_text)
                    add_rel(i_label, i_id, "NOTE", "note", n_id)

                # --- Sub-items (đệ quy) ---
                sub_items = it.get("items") or []
                if sub_items:
                    handle_items(sub_items, section_code, group_code, i_label, i_id, inherited_title=i_title)

        # ====== Section / Group / Item ======
        tables = q.get("tables_structured") or []
        for t_idx, table in enumerate(tables):
            sections = table.get("sections") or []
            for s_idx, section in enumerate(sections):
                s_label = section.get("label", "Phamvi")
                s_code = section.get("code", "")
                s_title = section.get("title", "")
                s_id = f"{s_label}:{s_code}" if s_code else f"{s_label}:{s_title}"

                add_node(s_label, s_id, code=s_code, title=s_title)
                add_rel("Quytrinh", q_id, "HAS_SECTION", s_label, s_id)

                for g_idx, group in enumerate(section.get("groups") or []):
                    g_code = group.get("code", "")
                    g_title = group.get("title", "")
                    handle_items(group.get("items") or [], s_code, g_code, s_label, s_id, inherited_title=g_title)

                print(f"✅ Đã xử lý section {s_code or s_title}")

        print(f"Tổng số nodes: {len(nodes)} | relationships: {len(rels)}")
        return nodes, rels

    # =========================================================
    # Bulk import vào Neo4j
    # =========================================================
    def _bulk_import(self, nodes: List[Dict[str, Any]], rels: List[Dict[str, Any]]):
        """Import hàng loạt nodes & relationships"""
        if nodes:
            print(f"{len(nodes)} nodes...")
            node_query = """
            UNWIND $nodes AS node_data
            CALL apoc.merge.node([node_data.type], {id: node_data.properties.id}, node_data.properties, {})
            YIELD node
            RETURN count(node)
            """
            self.graph.query(node_query, {"nodes": nodes})

        if rels:
            print(f"{len(rels)} relationships...")
            rel_query = """
            UNWIND $rels AS rel_data
            MATCH (a {id: rel_data.source_id})
            MATCH (b {id: rel_data.target_id})
            CALL apoc.merge.relationship(a, rel_data.type, {}, rel_data.properties, b)
            YIELD rel
            RETURN count(rel)
            """
            self.graph.query(rel_query, {"rels": rels})