DOCLING_SCHEMA = {
    "nodes": {
        "Quytrinh": {
            "properties": ["title"],
            "relationships": [
                ("HAS_SECTION", "Phamvi")
            ]
        },
        "Phamvi": {
            "properties": ["proc", "tableIdx", "code", "title", "label"],
            "relationships": [
                ("HAS_ITEM", "Thutuc")
            ]
        },
        "Thutuc": {
            "properties": ["proc", "tableIdx", "sectionCode", "code", "title", "label", "level"],
            "relationships": [
                ("REQUIRES", "Thanhphandutoan"),
                ("REQUIRES", "Hosochungtu"),
                ("NOTE", "Ghichu")
            ]
        },
        "Thanhphandutoan": {
            "properties": ["name"],
            "relationships": []
        },
        "Hosochungtu": {
            "properties": ["name"],
            "relationships": []
        },
        "Ghichu": {
            "properties": ["key", "text"],
            "relationships": []
        }
    }
}

DOCLING_PROMPTS = {
    "extract_entities": """
    Phân tích văn bản và trích xuất thông tin theo schema:
    {text}
    
    Schema:
    {schema}
    """,
    
    "few_shot_examples": [
        {
            "question": "Liệt kê tất cả Phạm vi (code, title) của quy trình.",
            "cypher": """
            MATCH (q:Quytrinh {title:'Quy trinh Kiem soat chi va Thanh toan cua UET (03.01.2021)'})-[:HAS_SECTION]->(s:Phamvi)
            RETURN s.code AS code, s.title AS title ORDER BY s.tableIdx, s.code"""
        },
        {
            "question": "Đếm số Thủ tục trong Phạm vi 'I' (bảng thứ 2) của quy trình.",
            "cypher": (
                "MATCH (:Quytrinh {title:'Quy trinh Kiem soat chi va Thanh toan cua UET (03.01.2021)'})"
                "-[:HAS_SECTION]->(s:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc)\n"
                "RETURN count(t)"
            )
        },
        {
            "question": "Liệt kê các Thủ tục (title, code) thuộc Phạm vi 'I' (bảng thứ 2), sắp xếp theo code.",
            "cypher": (
                "MATCH (:Quytrinh {title:'Quy trinh Kiem soat chi va Thanh toan cua UET (03.01.2021)'})"
                "-[:HAS_SECTION]->(s:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc)\n"
                "RETURN t.title AS thuTuc, t.code AS code ORDER BY toInteger(t.code)"
            )
        },
        {
            "question": "Các Thành phần dự toán yêu cầu cho Thủ tục code '1' trong Phạm vi 'I' (bảng thứ 2).",
            "cypher": (
                "MATCH (:Quytrinh {title:'Quy trinh Kiem soat chi va Thanh toan cua UET (03.01.2021)'})"
                "-[:HAS_SECTION]->(:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc {code:'1'})\n"
                "MATCH (t)-[r:REQUIRES]->(tp:Thanhphandutoan)\n"
                "RETURN DISTINCT tp.name AS ten, r.item AS item ORDER BY item"
            )
        },
        {
            "question": "Lấy Hồ sơ chứng từ cho mục item 'a' của Thủ tục code '1' (Phạm vi 'I', bảng thứ 2).",
            "cypher": (
                "MATCH (:Quytrinh {title:'Quy trinh Kiem soat chi va Thanh toan cua UET (03.01.2021)'})"
                "-[:HAS_SECTION]->(:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc {code:'1'})\n"
                "MATCH (t)-[:REQUIRES {item:'a'}]->(hs:Hosochungtu)\n"
                "RETURN DISTINCT hs.name"
            )
        },
        {
            "question": "Tìm các ghi chú (text) cho item 'b' của Thủ tục code '2' trong Phạm vi 'I' (bảng thứ 2).",
            "cypher": (
                "MATCH (:Quytrinh {title:'Quy trinh Kiem soat chi va Thanh toan cua UET (03.01.2021)'})"
                "-[:HAS_SECTION]->(:Phamvi {code:'I', tableIdx:1})-[:HAS_ITEM]->(t:Thutuc {code:'2'})\n"
                "MATCH (t)-[:NOTE {item:'b'}]->(g:Ghichu)\n"
                "RETURN g.text"
            )
        },
    ],
    
    "results_template": """Bạn là trợ lý phân tích dữ liệu.
    Nhiệm vụ: Tóm tắt kết quả truy vấn Neo4j bằng tiếng Việt, súc tích, dễ hiểu.
    ..."""
}