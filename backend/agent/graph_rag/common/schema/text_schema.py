TEXT_SCHEMA = {
    "nodes": {
        "Document": {
            "properties": ["name", "number_of_pages"],
            "relationships": [
                ("HAS_CHAPTER", "Chapter")
            ]
        },
        "Chapter": {
            "properties": ["name", "number"],
            "relationships": [
                ("HAS_SECTION", "Section")
            ]
        },
        "Section": {
            "properties": ["content", "number"],
            "relationships": [
                ("HAS_SUBSECTION", "Section"),
                ("REFERENCES", "Section")
            ]
        }
    }
}

TEXT_PROMPTS = {
    "extract_entities": """
    Phân tích JSON và trích xuất thông tin theo schema:
    {text}
    
    Schema:
    {schema}
    """,

    "few_shot_examples": [
    {
        "question": "Liệt kê tất cả các Chương trong tài liệu.",
        "cypher": (
            "MATCH (d:Document {name:'Data/Quy trinh Kiem soat chi va Thanh toan cua UET (03.01.2021).docx'})"
            "-[:HAS_CHAPTER]->(c:Chapter) "
            "RETURN c.number AS soChuong, c.name AS tenChuong ORDER BY c.number"
        )
    },
    {
        "question": "Tìm các Mục (Section) trong Chương II.",
        "cypher": (
            "MATCH (:Document)-[:HAS_CHAPTER]->(c:Chapter {number:'II'})-[:HAS_SECTION]->(s:Section) "
            "RETURN s.number AS soMuc, s.name AS tenMuc ORDER BY s.number"
        )
    },
    {
        "question": "Các Tiểu mục (Subsection) thuộc Mục 3. Quy trình quản lý.",
        "cypher": (
            "MATCH (s:Section {name:'3. Quy trình quản lý'})-[:CONTAINS]->(sub:Subsection) "
            "RETURN sub.letter AS kyHieu, sub.name AS tieuMuc ORDER BY sub.letter"
        )
    },
    {
        "question": "Liệt kê tất cả Quy trình (Procedure) trong Chương III.",
        "cypher": (
            "MATCH (:Chapter {number:'III'})-[:HAS_PROCEDURE]->(p:Procedure) "
            "RETURN p.number AS soQuyTrinh, p.name AS tenQuyTrinh ORDER BY p.number"
        )
    },
    {
        "question": "Các bước (Step) trong Quy trình 5. TẠM ỨNG, THANH QUYẾT TOÁN TRONG XÂY DỰNG CƠ BẢN.",
        "cypher": (
            "MATCH (p:Procedure {number:5})-[:HAS_STEP]->(st:Step) "
            "RETURN st.number AS soBuoc, st.name AS tenBuoc ORDER BY st.number"
        )
    },
    {
        "question": "Tìm tất cả nơi có từ 'tạm ứng'.",
        "cypher": (
            "MATCH (n) WHERE toLower(n.name) CONTAINS 'tạm ứng' "
            "RETURN labels(n) AS loaiNode, n.name AS tieuDe"
        )
    }
]
}