from typing import Any, Dict, List  
from neo4j import GraphDatabase
# from .get_available import get_root_with_subitem
class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_root_with_subitems(self, label: str | None = None):
        query = """
        // Lấy mọi Thủ tục ở độ sâu 1-3 tính từ Phạm vi
        MATCH (q:Quytrinh)-[:HAS_SECTION]->(p)
        MATCH (p)-[:HAS_ITEM|HAS_SUBITEM*1..3]->(root:Thutuc)
        OPTIONAL MATCH (root)-[:HAS_CATEGORY]->(c:category)
        OPTIONAL MATCH (c)-[:HAS_ITEM]->(bc:budgets)
        OPTIONAL MATCH (root)-[:HAS_BUDGET]->(bd:budgets)
        OPTIONAL MATCH (root)-[:REQUIRES]->(d:docs)
        OPTIONAL MATCH (root)-[:NOTE]->(n:note)
        OPTIONAL MATCH (root)-[:HAS_SUBITEM]->(child)

        WITH
            q, p, root,
            collect(DISTINCT c)  AS cats,
            collect(DISTINCT {cat:c, bud:bc}) AS catPairs,
            collect(DISTINCT bd) AS directBudgets,
            [x IN collect(DISTINCT d) WHERE x IS NOT NULL AND coalesce(x.title,'') <> '' |
                { id: elementId(x), title: x.title, type:'docs' }
            ] AS docsItems,
            head([x IN collect(DISTINCT n) WHERE x IS NOT NULL | coalesce(x.description,'')]) AS noteText,
            [x IN collect(DISTINCT child) WHERE x IS NOT NULL AND coalesce(x.title,'') <> '' |
                { id: elementId(x), title: x.title, type:'subitem' }
            ] AS childrenItems

        WITH
            q, p, root, docsItems, noteText, childrenItems, cats, catPairs, directBudgets,
            [cat IN cats WHERE cat IS NOT NULL |
                {
                    id: elementId(cat),
                    title: coalesce(cat.name,''),
                    type: 'category',
                    children: [cp IN catPairs WHERE cp.cat = cat AND cp.bud IS NOT NULL |
                        { id: elementId(cp.bud), title: coalesce(cp.bud.name,''), type:'budget' }
                    ]
                }
            ] AS categoryBlocks,
            [b IN directBudgets WHERE b IS NOT NULL AND coalesce(b.name,'') <> '' |
                { id: elementId(b), title: b.name, type:'budget' }
            ] AS directBudgetItems

        WITH
            q, p, root, docsItems, noteText, childrenItems, categoryBlocks, directBudgetItems,
            CASE WHEN size(categoryBlocks) > 0 THEN categoryBlocks ELSE directBudgetItems END AS budgetBlock,
            [cp IN catPairs WHERE cp.bud IS NOT NULL | coalesce(cp.bud.name,'')] +
            [b IN directBudgets WHERE b IS NOT NULL | coalesce(b.name,'')] AS budgetNamesRaw

        WITH
            q, p, root, docsItems, noteText, childrenItems, budgetBlock,
            reduce(acc = [], x IN [n IN budgetNamesRaw WHERE n <> ''] |
                CASE WHEN x IN acc THEN acc ELSE acc + x END
            ) AS budgetsAll

        RETURN
            elementId(root)                 AS internalId,
            coalesce(root.id, '')           AS id,
            coalesce(root.code, '')         AS code,
            coalesce(root.title, '')        AS title,
            coalesce(root.category, '')     AS category,
            coalesce(noteText, '')          AS note,
            budgetsAll                      AS budgets,
            coalesce(q.full_title, '')      AS quytrinh,
            coalesce(p.title, '')           AS phamvi,
            coalesce(root.section_code, '') AS section_code,
            coalesce(root.group_code, '')   AS group_code,
            (docsItems + childrenItems + budgetBlock) AS subItems
        ORDER BY code, section_code;
        """

        data_raw = []
        with self.driver.session() as session:
            for record in session.run(query):
                rec = record.data()
                sub_items = rec.get("subItems") or []

                # Docs
                docs_ui = [
                    {"id": it["id"], "title": (it["title"] or "").strip(), "label": "docs", "children": []}
                    for it in sub_items
                    if isinstance(it, dict) and it.get("type") == "docs" and it.get("id")
                ]

                # Budgets
                category_blocks = [it for it in sub_items if isinstance(it, dict) and it.get("type") == "category"]
                budgets_ui = []
                if category_blocks:
                    for cat in category_blocks:
                        cat_title = (cat.get("title") or "").strip()
                        if not cat_title:
                            continue
                        children = [
                            {"id": ch["id"], "title": (ch["title"] or "").strip(), "label": "budgets", "children": []}
                            for ch in (cat.get("children") or [])
                            if isinstance(ch, dict) and ch.get("id")
                        ]
                        budgets_ui.append({
                            "id": cat.get("id"),
                            "title": cat_title,
                            "label": "budgets",
                            "children": children
                        })
                else:
                    budgets_ui = [
                        {"id": it["id"], "title": (it["title"] or "").strip(), "label": "budgets", "children": []}
                        for it in sub_items
                        if isinstance(it, dict) and it.get("type") == "budget" and it.get("id")
                    ]

                # Note
                note_text = (rec.get("note") or "").strip()
                note_ui = []
                if note_text:
                    note_ui.append({
                        "id": f"{rec.get('internalId')}_note",
                        "title": note_text,
                        "label": "note",
                        "children": []
                    })

                parent = f"{rec.get('quytrinh') or ''} / {rec.get('phamvi') or ''}".strip().strip(" /")

                data_raw.append({
                    "internalId": rec.get("internalId"),
                    "id": rec.get("id"),
                    "code": rec.get("code") or "",
                    "title": rec.get("title") or "",
                    "parent": parent,
                    "description": "",
                    "date": "",
                    "subItems": docs_ui + budgets_ui + note_ui
                })

        # ✅ Gộp chỉ theo (title + parent)
        grouped = {}
        for item in data_raw:
            key = f"{item['title'].lower()}::{item['parent'].lower()}"
            code = item.get("code") or "(no code)"
            if key not in grouped:
                grouped[key] = {
                    "id": item["internalId"],
                    "title": item["title"],
                    "description": "",
                    "date": "",
                    "parent": item["parent"],
                    "_code_blocks": {}
                }
            if code not in grouped[key]["_code_blocks"]:
                grouped[key]["_code_blocks"][code] = {
                    "id": f"{item['internalId']}::code::{code}",
                    "title": code,
                    "label": "code",
                    "children": []
                }
            grouped[key]["_code_blocks"][code]["children"].extend(item["subItems"])

        # Xuất ra
        data_final = []
        for g in grouped.values():
            codes = list(g["_code_blocks"].values())
            data_final.append({
                "id": g["id"],
                "title": g["title"],
                "description": g["description"],
                "date": g["date"],
                "parent": g["parent"],
                "subItems": codes
            })

        data_final.sort(key=lambda x: (x["parent"].lower(), x["title"].lower()))
        return data_final



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